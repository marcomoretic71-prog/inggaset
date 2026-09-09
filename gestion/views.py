from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Avg
from .models import Corral, Animal, Pesada, Movimiento, Venta, Baja, Vacuna

def _asegurar_corrales():
    datos = [
        ('recepcion', 50, 1.5, 0, 100, 0.6),
        ('recria_1', 50, 2.0, 100, 150, 0.65),
        ('recria_2', 50, 2.0, 150, 220, 0.8),
        ('terminacion_1', 50, 3.0, 220, 400, 1.3),
        ('terminacion_2', 50, 3.0, 180, 330, 1.4),
    ]
    for nombre, cap, pct, pe, ps, gdpv in datos:
        c, _ = Corral.objects.get_or_create(nombre=nombre, defaults={'capacidad':cap})
        c.capacidad = cap
        c.porcentaje_alimento = pct
        c.peso_entrada = pe
        c.peso_salida = ps
        c.gdpv_esperado = gdpv
        c.kg_objetivo = int(ps)
        c.dias_objetivo = int((ps - pe) / gdpv) if gdpv else 30
        c.save()

def dashboard(request):
    _asegurar_corrales()
    q = request.GET.get('q','').strip()
    base = Animal.objects.filter(activo=True)
    filtrados = base.filter(numero_caravana__icontains=q) if q else base
    total_animales = base.count()
    total_alimento = round(sum(a.alimento_diario_kg for a in base), 1) if total_animales else 0

    datos_corrales = []
    total_listos = 0
    for corral in Corral.objects.all().order_by('nombre'):
        anims = base.filter(corral_actual=corral)
        prom = anims.aggregate(Avg('kg_actual'))['kg_actual__avg'] or 0
        listos = sum(1 for a in anims if a.listo_para_mover)
        total_listos += listos
        datos_corrales.append({
            'corral': corral,
            'count': anims.count(),
            'promedio': round(prom, 1),
            'alimento': round(sum(a.alimento_diario_kg for a in anims), 1),
            'listos': listos,
        })
    return render(request, 'gestion/dashboard.html', {
        'total_animales': total_animales,
        'total_alimento': total_alimento,
        'total_listos': total_listos,
        'datos_corrales': datos_corrales,
        'animales_filtrados': filtrados.select_related('corral_actual').prefetch_related('vacunas_ingreso','pesada_set').order_by('numero_caravana'),
        'todos_los_corrales': Corral.objects.all().order_by('nombre'),
        'ventas_count': Venta.objects.count(),
        'total_facturado': sum(v.kg_venta * v.precio_kg for v in Venta.objects.all()) if Venta.objects.exists() else 0,
        'bajas_count': Baja.objects.count(),
        'bajas_muerte': Baja.objects.filter(motivo='muerte').count(),
        'q': q,
    })


def pesar_rapido(request):
    if request.method == 'POST':
        animal_id = request.POST.get('animal_id')
        peso_str = request.POST.get('peso')
        fecha_str = request.POST.get('fecha')
        
        animal = get_object_or_404(Animal, id=animal_id)
        
        try:
            nuevo_peso = float(peso_str)
        except:
            return redirect('panel')

        # Fecha vinculada
        if fecha_str:
            try:
                anio, mes, dia = map(int, fecha_str.split('-'))
                fecha_pesada = date(anio, mes, dia)
            except:
                fecha_pesada = date.today()
        else:
            fecha_pesada = date.today()

        # 1. Actualiza el animal
        animal.kg_actual = nuevo_peso
        animal.save()

        # 2. Guarda el historial vinculado a esa fecha
        Pesada.objects.create(
            animal=animal,
            peso=nuevo_peso,
            fecha=fecha_pesada
        )

    return redirect('panel')

def mover_rapido(request):
    if request.method == 'POST':
        animal = get_object_or_404(Animal, id=request.POST.get('animal_id'))
        dest = get_object_or_404(Corral, id=request.POST.get('corral_destino'))
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
            animal.activo = False
            animal.save()
        except: pass
    return redirect('dashboard')

def baja_rapida(request):
    if request.method == 'POST':
        animal = get_object_or_404(Animal, id=request.POST.get('animal_id'))
        Baja.objects.create(animal=animal, motivo=request.POST.get('motivo','muerte'), kg_baja=animal.kg_actual, fecha=date.today())
        animal.activo = False
        animal.save()
    return redirect('dashboard')