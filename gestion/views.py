from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Avg, Sum
from django.http import HttpResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from .models import Corral, Animal, Pesada, Movimiento, Venta, Baja, Vacuna, normalizar_caravana
import pandas as pd

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

# --- NUEVO: ALTA INDIVIDUAL CON BLOQUEO ---
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

        # BLOQUEO DUPLICADO ANTES DE GUARDAR
        existente = Animal.objects.filter(numero_caravana=norm).first()
        if existente:
            if existente.activo:
                corral = existente.corral_actual.nombre_bonito if existente.corral_actual else "sin corral"
                messages.error(request, f"❌ BLOQUEADO: La caravana {norm} YA EXISTE. Está activa en {corral} con {existente.kg_actual}kg. No se puede cargar duplicada.")
            else:
                venta = Venta.objects.filter(animal=existente).first()
                if venta:
                    messages.error(request, f"❌ BLOQUEADO: La caravana {norm} ya fue VENDIDA el {venta.fecha}. No se puede reutilizar.")
                else:
                    baja = Baja.objects.filter(animal=existente).first()
                    if baja:
                        messages.error(request, f"❌ BLOQUEADO: La caravana {norm} ya fue dada de BAJA ({baja.motivo}) el {baja.fecha}.")
                    else:
                        messages.error(request, f"❌ BLOQUEADO: La caravana {norm} ya existe (inactiva). No se puede reutilizar.")
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
            animal.full_clean()
            animal.save()
            vac_ids = request.POST.getlist('vacunas')
            if vac_ids:
                animal.vacunas_ingreso.set(vac_ids)
            Pesada.objects.create(animal=animal, peso=kg, fecha=date.today(), observaciones="Ingreso")
            messages.success(request, f"✅ Caravana {norm} creada correctamente en {corral.nombre_bonito} con {kg}kg")
            return redirect('dashboard')
        except ValidationError as e:
            err = "; ".join([f"{', '.join(v)}" for v in e.message_dict.values()])
            messages.error(request, f"❌ {err}")
            return redirect('alta_animal')
        except Exception as ex:
            messages.error(request, f"❌ Error inesperado: {ex}")
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
    # Busca normalizado también
    q_norm = normalizar_caravana(q) if q else ""
    if q:
        # busca por caravana original o normalizada
        if q_norm and q_norm != q:
            filtrados = base.filter(numero_caravana__icontains=q) | base.filter(numero_caravana__icontains=q_norm)
        else:
            filtrados = base.filter(numero_caravana__icontains=q)
    else:
        filtrados = base
    total_animales = base.count()
    total_alimento = round(sum(a.alimento_diario_kg for a in base), 1) if total_animales else 0
    datos_corrales = []
    total_listos = 0
    for corral in Corral.objects.all().order_by('nombre'):
        anims = base.filter(corral_actual=corral)
        prom = anims.aggregate(Avg('kg_actual'))['kg_actual__avg'] or 0
        listos = sum(1 for a in anims if a.listo_para == 'venta' or a.listo_para == 'mover')
        listos_venta = sum(1 for a in anims if a.listo_para == 'venta')
        total_listos += listos_venta
        datos_corrales.append({
            'corral': corral, 'count': anims.count(), 'promedio': round(prom, 1),
            'alimento': round(sum(a.alimento_diario_kg for a in anims), 1), 'listos': listos,
        })

    saldo_caja = None
    try:
        from caja.models import MovimientoCaja
        ing = MovimientoCaja.objects.filter(tipo='INGRESO').aggregate(s=Sum('monto'))['s'] or 0
        egr = MovimientoCaja.objects.filter(tipo='EGRESO').aggregate(s=Sum('monto'))['s'] or 0
        saldo_caja = ing - egr
    except Exception:
        saldo_caja = None

    return render(request, 'gestion/dashboard.html', {
        'total_animales': total_animales, 'total_alimento': total_alimento, 'total_listos': total_listos,
        'datos_corrales': datos_corrales,
        'animales_filtrados': filtrados.select_related('corral_actual').prefetch_related('vacunas_ingreso','pesada_set','movimientos').order_by('fecha_ingreso_corral', 'numero_caravana'),
        'todos_los_corrales': Corral.objects.all().order_by('nombre'),
        'ventas_count': Venta.objects.count(),
        'total_facturado': sum(float(v.kg_venta) * float(v.precio_kg) for v in Venta.objects.all()) if Venta.objects.exists() else 0,
        'bajas_count': Baja.objects.count(), 'bajas_muerte': Baja.objects.filter(motivo='muerte').count(), 'q': q,
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
    p.setFont("Helvetica-Bold", 16)
    p.drawString(2*cm, alto - 2*cm, "IngGaset - Informe de Rodeo")
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, alto - 2.7*cm, f"Fecha: {date.today().strftime('%d/%m/%Y')} | Total animales activos: {Animal.objects.filter(activo=True).count()}")
    y = alto - 4*cm
    p.setFont("Helvetica-Bold", 8)
    p.drawString(1.5*cm, y, "CARAVANA")
    p.drawString(4*cm, y, "PESO")
    p.drawString(6*cm, y, "CORRAL")
    p.drawString(9.5*cm, y, "FECHA MOV.")
    p.drawString(12.5*cm, y, "DIAS")
    p.drawString(14*cm, y, "ESTADO")
    p.line(1.5*cm, y-0.2*cm, 19*cm, y-0.2*cm)
    p.setFont("Helvetica", 8)
    y -= 0.6*cm
    animales = Animal.objects.filter(activo=True).select_related('corral_actual').order_by('corral_actual__nombre', 'fecha_ingreso_corral')
    for animal in animales:
        if y < 2.5*cm:
            p.showPage()
            y = alto - 2*cm
        estado = "VENTA" if animal.listo_para == 'venta' else ("MOVER" if animal.listo_para == 'mover' else f"Faltan {animal.kg_faltantes}kg")
        p.drawString(1.5*cm, y, str(animal.numero_caravana))
        p.drawString(4*cm, y, f"{animal.kg_actual} kg")
        p.drawString(6*cm, y, str(animal.corral_actual.nombre_bonito if animal.corral_actual else '-'))
        p.drawString(9.5*cm, y, animal.fecha_ingreso_corral.strftime('%d/%m/%Y'))
        p.drawString(12.5*cm, y, f"{animal.dias_en_corral}d")
        p.drawString(14*cm, y, str(estado))
        y -= 0.5*cm
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

                # BLOQUEO DENTRO DEL MISMO EXCEL
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

                # Si ya existe en BD, actualiza peso pero no crea duplicado
                try:
                    animal_existente = Animal.objects.filter(numero_caravana=caravana).first()
                    if animal_existente:
                        # si está activo, solo actualiza
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
                    animal.full_clean()
                    animal.save()
                    Pesada.objects.create(animal=animal, peso=peso, fecha=date.today())
                    creados += 1
                except ValidationError:
                    # bloqueado por duplicado real
                    duplicados_en_excel += 1
                    continue

            total = Animal.objects.filter(activo=True).count()
            msg = f'¡Listo! {creados} nuevos, {actualizados} actualizados. Total activo: {total}'
            if duplicados_en_excel:
                msg += f' | {duplicados_en_excel} duplicados bloqueados dentro del excel o ya existentes'
            messages.success(request, msg)
        except Exception as e:
            messages.error(request, f'Error al importar: {e}')
    return redirect('dashboard')

