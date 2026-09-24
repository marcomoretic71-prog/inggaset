from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Avg, Sum
from django.http import HttpResponse
from django.contrib import messages
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from .models import Corral, Animal, Pesada, Movimiento, Venta, Baja, Vacuna
import pandas as pd
import re

def normalizar_caravana(valor: str) -> str:
    if not valor: return ""
    v = str(valor).strip()
    v = re.sub(r'\D', '', v)
    v = v.lstrip('0') or '0'
    return v

def _asegurar_corrales():
    datos = [
        ('recepcion', 50, 1.5, 0, 100, 0.6),
        ('recria_1', 50, 2.0, 100, 150, 0.65),
        ('recria_2', 50, 2.0, 150, 220, 0.8),
        ('terminacion_1', 50, 3.0, 220, 400, 1.3),
        ('terminacion_2', 50, 3.0, 180, 330, 1.4),
        ('venta', 500, 0, 0, 0, 0.1),
    ]
    for nombre, cap, pct, pe, ps, gdpv in datos:
        c, _ = Corral.objects.get_or_create(nombre=nombre, defaults={'capacidad':cap})
        c.capacidad = cap
        c.porcentaje_alimento = pct
        c.peso_entrada = pe
        c.peso_salida = ps
        c.gdpv_esperado = gdpv
        if nombre == 'venta':
            c.kg_objetivo = 0
            c.dias_objetivo = 0
        else:
            c.kg_objetivo = int(ps)
            c.dias_objetivo = int((ps - pe) / gdpv) if gdpv else 30
        c.save()

def alta_animal(request):
    _asegurar_corrales()
    if request.method == 'POST':
        caravana_raw = request.POST.get('numero_caravana','').strip()
        categoria = request.POST.get('categoria','ternero')
        kg_raw = request.POST.get('kg_ingreso','80')
        corral_id = request.POST.get('corral_actual')
        norm = normalizar_caravana(caravana_raw)
        if not norm:
            messages.error(request, f"❌ Caravana inválida: '{caravana_raw}'")
            return redirect('alta_animal')
        existente = Animal.objects.filter(numero_caravana=norm).first()
        if existente:
            if existente.activo:
                corral = existente.corral_actual.nombre_bonito if existente.corral_actual else "sin corral"
                messages.error(request, f"❌ BLOQUEADO: La caravana {norm} YA EXISTE. Está activa en {corral} con {existente.kg_actual}kg. No se puede cargar duplicada.")
            else:
                venta = Venta.objects.filter(animal=existente).first()
                if venta:
                    messages.error(request, f"❌ BLOQUEADO: La caravana {norm} ya fue VENDIDA el {venta.fecha}.")
                else:
                    baja = Baja.objects.filter(animal=existente).first()
                    if baja:
                        messages.error(request, f"❌ BLOQUEADO: La caravana {norm} ya fue dada de BAJA ({baja.motivo}) el {baja.fecha}.")
                    else:
                        messages.error(request, f"❌ BLOQUEADO: La caravana {norm} ya existe (inactiva).")
            return redirect('alta_animal')
        try:
            kg = float(str(kg_raw).replace(',', '.'))
        except:
            kg = 80
        corral = get_object_or_404(Corral, id=corral_id) if corral_id else Corral.objects.first()
        try:
            animal = Animal(
                numero_caravana=norm,
                categoria=categoria,
                kg_ingreso=kg,
                kg_actual=kg,
                corral_actual=corral,
                fecha_ingreso_corral=date.today(),
                fecha_ingreso=date.today(),
                activo=True
            )
            animal.save()
            vac_ids = request.POST.getlist('vacunas')
            if vac_ids:
                animal.vacunas_ingreso.set(vac_ids)
            Pesada.objects.create(animal=animal, peso=kg, fecha=date.today(), observaciones="Ingreso")
            messages.success(request, f"✅ Caravana {norm} creada correctamente en {corral.nombre_bonito} con {kg}kg")
            return redirect('dashboard')
        except Exception as ex:
            messages.error(request, f"❌ Error: {ex}")
            return redirect('alta_animal')
    return render(request, 'gestion/alta_animal.html', {
        'corrales': Corral.objects.all().order_by('nombre'),
        'vacunas': Vacuna.objects.all(),
        'categorias': Animal.CATEGORIAS,
    })

def dashboard(request):
    _asegurar_corrales()
    q = request.GET.get('q','').strip()
    base = Animal.objects.filter(activo=True)
    q_norm = normalizar_caravana(q) if q else ""
    if q:
        if q_norm and q_norm != q:
            filtrados = base.filter(numero_caravana__icontains=q) | base.filter(numero_caravana__icontains=q_norm)
        else:
            filtrados = base.filter(numero_caravana__icontains=q)
    else:
        filtrados = base

    # NUEVO: agrupado por corral, mayor a menor peso dentro de cada corral
    animales_por_corral = []
    total_listos = 0
    for corral in Corral.objects.all().order_by('nombre'):
        anims_qs = base.filter(corral_actual=corral).select_related('corral_actual').prefetch_related('vacunas_ingreso','pesada_set','movimientos').order_by('-kg_actual')
        # Si hay búsqueda, filtrar también por corral
        if q:
            anims_qs = anims_qs.filter(id__in=filtrados.values_list('id', flat=True))
        if not anims_qs.exists() and q:
            continue
        prom = base.filter(corral_actual=corral).aggregate(Avg('kg_actual'))['kg_actual__avg'] or 0
        if not q:
            # promedio solo de ese corral, no del filtrado
            prom = anims_qs.aggregate(Avg('kg_actual'))['kg_actual__avg'] or 0
        listos = sum(1 for a in anims_qs if a.listo_para == 'venta' or a.listo_para == 'mover')
        listos_venta = sum(1 for a in anims_qs if a.listo_para == 'venta')
        total_listos += listos_venta if not q else 0
        # Para el acordeon, si hay búsqueda, dejarlo expandido
        animales_por_corral.append({
            'corral': corral,
            'animales': anims_qs,
            'count': anims_qs.count(),
            'promedio': round(prom, 1),
            'alimento': round(sum(a.alimento_diario_kg for a in anims_qs), 1),
            'listos': listos,
            'expandido': True if q else False,
        })

    total_animales = base.count()
    total_alimento = round(sum(a.alimento_diario_kg for a in base), 1) if total_animales else 0

    saldo_caja = None
    try:
        from caja.models import MovimientoCaja
        ing = MovimientoCaja.objects.filter(tipo='INGRESO').aggregate(s=Sum('monto'))['s'] or 0
        egr = MovimientoCaja.objects.filter(tipo='EGRESO').aggregate(s=Sum('monto'))['s'] or 0
        saldo_caja = ing - egr
    except Exception:
        saldo_caja = None

    return render(request, 'gestion/dashboard.html', {
        'total_animales': total_animales,
        'total_alimento': total_alimento,
        'total_listos': total_listos,
        'datos_corrales': animales_por_corral,  # ahora viene agrupado
        'animales_por_corral': animales_por_corral,
        'animales_filtrados': filtrados.select_related('corral_actual').prefetch_related('vacunas_ingreso','pesada_set','movimientos').order_by('-kg_actual'),
        'todos_los_corrales': Corral.objects.all().order_by('nombre'),
        'ventas_count': Venta.objects.count(),
        'total_facturado': sum(float(v.kg_venta) * float(v.precio_kg) for v in Venta.objects.all()) if Venta.objects.exists() else 0,
        'bajas_count': Baja.objects.count(),
        'bajas_muerte': Baja.objects.filter(motivo='muerte').count(),
        'q': q,
        'saldo_caja': saldo_caja,
    })

def pesar_rapido(request):
    if request.method == 'POST':
        animal_id = request.POST.get('animal_id')
        peso_str = request.POST.get('peso')
        fecha_str = request.POST.get('fecha')
        animal = get_object_or_404(Animal, id=animal_id)
        try: nuevo_peso = float(peso_str)
        except: return redirect('dashboard')
        if fecha_str:
            try:
                anio, mes, dia = map(int, fecha_str.split('-'))
                fecha_pesada = date(anio, mes, dia)
            except: fecha_pesada = date.today()
        else: fecha_pesada = date.today()
        animal.kg_actual = nuevo_peso
        animal.save()
        Pesada.objects.create(animal=animal, peso=nuevo_peso, fecha=fecha_pesada)
    return redirect('dashboard')

def mover_rapido(request):
    if request.method == 'POST':
        animal = get_object_or_404(Animal, id=request.POST.get('animal_id'))
        dest = get_object_or_404(Corral, id=request.POST.get('corral_destino'))
        if animal.corral_actual!= dest:
            Movimiento.objects.create(animal=animal, corral_origen=animal.corral_actual, corral_destino=dest, peso_en_movimiento=animal.kg_actual, fecha=date.today())
            animal.corral_actual = dest
            animal.fecha_ingreso_corral = date.today()
            animal.save()
    return redirect('dashboard')

def mover_masivo(request):
    """ NUEVO: mover varias caravanas a la vez, con peso y destino individual opcional """
    if request.method == 'POST':
        animal_ids = request.POST.getlist('animal_ids')
        if not animal_ids:
            messages.error(request, "❌ No seleccionaste ninguna caravana")
            return redirect('dashboard')
        
        corral_global_id = request.POST.get('corral_destino_global')
        corral_global = None
        if corral_global_id:
            try:
                corral_global = Corral.objects.get(id=corral_global_id)
            except:
                corral_global = None

        movidos = 0
        pesados = 0
        for aid in animal_ids:
            try:
                animal = Animal.objects.get(id=aid, activo=True)
            except Animal.DoesNotExist:
                continue

            # Peso individual si viene: peso_{id}
            peso_key = f'peso_{aid}'
            nuevo_peso_raw = request.POST.get(peso_key, '').strip()
            if nuevo_peso_raw:
                try:
                    np = float(nuevo_peso_raw.replace(',', '.'))
                    if np > 0 and np != animal.kg_actual:
                        animal.kg_actual = np
                        Pesada.objects.create(animal=animal, peso=np, fecha=date.today(), observaciones="Pesada masiva")
                        pesados += 1
                except:
                    pass

            # Destino individual: destino_{id} o global
            destino_key = f'destino_{aid}'
            dest_id = request.POST.get(destino_key) or (corral_global.id if corral_global else None)
            if dest_id:
                try:
                    dest = Corral.objects.get(id=dest_id)
                    if animal.corral_actual_id != dest.id:
                        Movimiento.objects.create(
                            animal=animal,
                            corral_origen=animal.corral_actual,
                            corral_destino=dest,
                            peso_en_movimiento=animal.kg_actual,
                            fecha=date.today()
                        )
                        animal.corral_actual = dest
                        animal.fecha_ingreso_corral = date.today()
                        movidos += 1
                except Corral.DoesNotExist:
                    pass

            animal.save()

        messages.success(request, f"✅ Masivo: {len(animal_ids)} seleccionadas • {pesados} pesadas • {movidos} movidas")
    return redirect('dashboard')

def vender_rapido(request):
    if request.method == 'POST':
        animal = get_object_or_404(Animal, id=request.POST.get('animal_id'))
        try:
            kg = float(request.POST.get('kg_venta'))
            precio = float(request.POST.get('precio_kg'))
            Venta.objects.create(animal=animal, kg_venta=kg, precio_kg=precio, fecha=date.today())
        except Exception as e:
            print(f"Error venta: {e}")
    return redirect('dashboard')

def baja_rapida(request):
    if request.method == 'POST':
        animal = get_object_or_404(Animal, id=request.POST.get('animal_id'))
        Baja.objects.create(animal=animal, motivo=request.POST.get('motivo','muerte'), kg_baja=animal.kg_actual, fecha=date.today())
    return redirect('dashboard')

def informe_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Informe_IngGaset_{date.today()}.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    ancho, alto = A4
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1.5*cm, alto - 1.5*cm, "IngGaset - Informe de Rodeo")
    p.setFont("Helvetica", 9)
    p.drawString(1.5*cm, alto - 2.1*cm, f"Fecha: {date.today().strftime('%d/%m/%Y')} | Total: {Animal.objects.filter(activo=True).count()} animales | Orden: Por Corral / Mayor a menor peso")
    
    y = alto - 3*cm
    x_caravana = 1.5*cm
    x_peso = 5.5*cm
    x_corral = 7.5*cm
    x_fecha = 10.8*cm
    x_dias = 13.2*cm
    x_estado = 14.7*cm
    
    def dibujar_cabecera(y_pos):
        p.setFont("Helvetica-Bold", 7)
        p.drawString(x_caravana, y_pos, "CARAVANA")
        p.drawString(x_peso, y_pos, "PESO")
        p.drawString(x_corral, y_pos, "CORRAL")
        p.drawString(x_fecha, y_pos, "FECHA MOV.")
        p.drawString(x_dias, y_pos, "DIAS")
        p.drawString(x_estado, y_pos, "ESTADO")
        p.line(1.5*cm, y_pos-0.15*cm, 19.5*cm, y_pos-0.15*cm)
        p.setFont("Helvetica", 7)
        return y_pos - 0.5*cm

    y = dibujar_cabecera(y)
    
    corrales_orden = Corral.objects.all().order_by('nombre')
    
    for corral in corrales_orden:
        animales_corral = Animal.objects.filter(activo=True, corral_actual=corral).select_related('corral_actual').order_by('-kg_actual')
        if not animales_corral.exists():
            continue
        if y < 3*cm:
            p.showPage()
            y = alto - 1.5*cm
            y = dibujar_cabecera(y)
        p.setFont("Helvetica-Bold", 8)
        p.setFillColorRGB(0.92, 0.92, 0.92)
        p.rect(1.5*cm, y-0.1*cm, 18*cm, 0.55*cm, fill=1, stroke=0)
        p.setFillColorRGB(0,0,0)
        p.drawString(1.6*cm, y+0.05*cm, f"{corral.nombre_bonito.upper()} ({animales_corral.count()} animales) - mayor a menor peso")
        y -= 0.7*cm
        p.setFont("Helvetica", 7)
        for animal in animales_corral:
            if y < 2*cm:
                p.showPage()
                y = alto - 1.5*cm
                y = dibujar_cabecera(y)
                p.setFont("Helvetica-Bold", 8)
                p.setFillColorRGB(0.92, 0.92, 0.92)
                p.rect(1.5*cm, y-0.1*cm, 18*cm, 0.55*cm, fill=1, stroke=0)
                p.setFillColorRGB(0,0,0)
                p.drawString(1.6*cm, y+0.05*cm, f"{corral.nombre_bonito.upper()} (cont.) - mayor a menor")
                y -= 0.7*cm
                p.setFont("Helvetica", 7)
            estado = "VENTA" if animal.listo_para == 'venta' else ("MOVER" if animal.listo_para == 'mover' else f"Faltan {animal.kg_faltantes}kg")
            corral_nombre = animal.corral_actual.nombre_bonito if animal.corral_actual else '-'
            if len(corral_nombre) > 14:
                corral_nombre = corral_nombre[:13]
            p.drawString(x_caravana, y, str(animal.numero_caravana))
            p.drawString(x_peso, y, f"{animal.kg_actual}kg")
            p.drawString(x_corral, y, str(corral_nombre))
            p.drawString(x_fecha, y, animal.fecha_ingreso_corral.strftime('%d/%m/%Y'))
            p.drawString(x_dias, y, f"{animal.dias_en_corral}d")
            p.drawString(x_estado, y, str(estado))
            y -= 0.42*cm
    
    p.showPage()
    p.save()
    return response

def importar_excel(request):
    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        archivo = request.FILES['archivo_excel']
        try:
            xls = pd.ExcelFile(archivo)
            df = pd.read_excel(archivo, sheet_name=xls.sheet_names[0], dtype=str)
            df.columns = [str(c).lower().strip() for c in df.columns]
            corral_default = Corral.objects.first()
            if not corral_default:
                _asegurar_corrales()
                corral_default = Corral.objects.first()
            creados = 0
            actualizados = 0
            duplicados_en_excel = 0
            vistos_en_excel = set()
            for _, row in df.iterrows():
                caravana_raw = str(row.get('nro caravana', row.get('caravana', ''))).strip()
                if not caravana_raw or 'caravana' in caravana_raw.lower() or caravana_raw.lower() == 'nan':
                    continue
                caravana = normalizar_caravana(caravana_raw)
                if not caravana or len(caravana) < 1:
                    continue
                if caravana in vistos_en_excel:
                    duplicados_en_excel += 1
                    continue
                vistos_en_excel.add(caravana)
                peso_raw = str(row.get('kilo', row.get('peso', '0'))).replace(',', '.')
                try: peso = float(peso_raw)
                except: peso = 80
                if peso <= 0: peso = 80
                sexo = str(row.get('sexo', '')).lower()
                if 'h' in sexo or 'f' in sexo: categoria = 'hembra'
                elif 'mej' in sexo: categoria = 'mej'
                elif 'castr' in sexo: categoria = 'novillo'
                elif 'toro' in sexo: categoria = 'toro'
                elif 'vaca' in sexo: categoria = 'vaca'
                else: categoria = 'ternero'
                try:
                    animal_existente = Animal.objects.filter(numero_caravana=caravana).first()
                    if animal_existente:
                        if animal_existente.activo and animal_existente.kg_actual != peso:
                            animal_existente.kg_actual = peso
                            animal_existente.save()
                            Pesada.objects.create(animal=animal_existente, peso=peso, fecha=date.today())
                            actualizados += 1
                        continue
                    animal = Animal(
                        numero_caravana=caravana,
                        kg_actual=peso,
                        kg_ingreso=peso,
                        categoria=categoria,
                        corral_actual=corral_default,
                        activo=True,
                        fecha_ingreso_corral=date.today()
                    )
                    animal.save()
                    Pesada.objects.create(animal=animal, peso=peso, fecha=date.today())
                    creados += 1
                except Exception:
                    duplicados_en_excel += 1
                    continue
            total = Animal.objects.filter(activo=True).count()
            msg = f'¡Listo! {creados} nuevos, {actualizados} actualizados. Total activo: {total}'
            if duplicados_en_excel:
                msg += f' | {duplicados_en_excel} duplicados bloqueados'
            messages.success(request, msg)
        except Exception as e:
            messages.error(request, f'Error al importar: {e}')
    return redirect('dashboard')
