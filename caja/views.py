from django.shortcuts import render, redirect
from django.db.models import Sum
from .models import MovimientoCaja, Persona
from datetime import date

def caja_dashboard(request):
    # POST: crear movimiento rápido
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        persona_id = request.POST.get('persona')
        monto = request.POST.get('monto')
        descripcion = request.POST.get('descripcion')
        fecha_str = request.POST.get('fecha')
        
        if monto and persona_id:
            try:
                fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()
            except:
                fecha = date.today()
                
            MovimientoCaja.objects.create(
                tipo=tipo,
                persona_id=persona_id,
                monto=monto,
                descripcion=descripcion or ('Ingreso' if tipo=='INGRESO' else 'Gasto'),
                fecha=fecha
            )
        return redirect('caja_dashboard')

    # Filtros GET
    persona_filtro = request.GET.get('persona_filtro')
    mes_filtro = request.GET.get('mes')

    movimientos = MovimientoCaja.objects.select_related('persona').order_by('-fecha','-id')
    if persona_filtro:
        movimientos = movimientos.filter(persona_id=persona_filtro)
    if mes_filtro:
        movimientos = movimientos.filter(fecha__month=mes_filtro)

    movimientos_list = movimientos[:50]

    # Totales generales (sin filtro)
    total_ingresos_all = MovimientoCaja.objects.filter(tipo='INGRESO').aggregate(s=Sum('monto'))['s'] or 0
    total_egresos_all = MovimientoCaja.objects.filter(tipo='EGRESO').aggregate(s=Sum('monto'))['s'] or 0

    # Gráficos - filtrado
    egresos_por_persona = movimientos.filter(tipo='EGRESO').values('persona__nombre').annotate(total=Sum('monto')).order_by('-total')
    
    balance_por_persona = []
    for p in Persona.objects.all().order_by('nombre'):
        ing = MovimientoCaja.objects.filter(persona=p, tipo='INGRESO').aggregate(s=Sum('monto'))['s'] or 0
        egr = MovimientoCaja.objects.filter(persona=p, tipo='EGRESO').aggregate(s=Sum('monto'))['s'] or 0
        if ing or egr:
            balance_por_persona.append({'persona__nombre': p.nombre, 'total': ing - egr, 'ing': ing, 'egr': egr})

    context = {
        'movimientos': movimientos_list,
        'personas': Persona.objects.all().order_by('nombre'),
        'total_ingresos': total_ingresos_all,
        'total_egresos': total_egresos_all,
        'saldo': total_ingresos_all - total_egresos_all,
        'ingresos_count': MovimientoCaja.objects.filter(tipo='INGRESO').count(),
        'egresos_count': MovimientoCaja.objects.filter(tipo='EGRESO').count(),
        'egresos_por_persona': egresos_por_persona,
        'balance_por_persona': balance_por_persona,
        'persona_filtro': persona_filtro,
    }
    return render(request, 'caja/dashboard.html', context)
