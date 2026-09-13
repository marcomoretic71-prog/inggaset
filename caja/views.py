from django.shortcuts import render, redirect
from django.db.models import Sum
from .models import MovimientoCaja, Persona
from datetime import date

def caja_dashboard(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        responsable_id = request.POST.get('responsable') or request.POST.get('persona')
        monto = request.POST.get('monto')
        categoria = request.POST.get('categoria') or 'OTROS'
        descripcion = request.POST.get('descripcion')
        fecha_str = request.POST.get('fecha')
        
        if monto and responsable_id:
            try:
                fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()
            except:
                fecha = date.today()
            
            MovimientoCaja.objects.create(
                tipo=tipo,
                responsable_id=responsable_id,
                monto=monto,
                categoria=categoria,
                descripcion=descripcion or '',
                fecha=fecha
            )
        return redirect('caja_dashboard')

    # Filtros
    responsable_filtro = request.GET.get('persona_filtro') or request.GET.get('responsable_filtro')
    categoria_filtro = request.GET.get('categoria')
    mes_filtro = request.GET.get('mes')

    movimientos = MovimientoCaja.objects.select_related('responsable').order_by('-fecha','-id')
    
    if responsable_filtro:
        movimientos = movimientos.filter(responsable_id=responsable_filtro)
    if categoria_filtro:
        movimientos = movimientos.filter(categoria=categoria_filtro)
    if mes_filtro:
        try:
            movimientos = movimientos.filter(fecha__month=int(mes_filtro))
        except:
            pass

    movimientos_list = movimientos[:100]

    # Totales sin filtro
    total_ingresos_all = MovimientoCaja.objects.filter(tipo='INGRESO').aggregate(s=Sum('monto'))['s'] or 0
    total_egresos_all = MovimientoCaja.objects.filter(tipo='EGRESO').aggregate(s=Sum('monto'))['s'] or 0

    # Egresos por responsable
    egresos_qs = MovimientoCaja.objects.filter(tipo='EGRESO').exclude(responsable__isnull=True)
    if categoria_filtro:
        egresos_qs = egresos_qs.filter(categoria=categoria_filtro)
    if mes_filtro:
        try:
            egresos_qs = egresos_qs.filter(fecha__month=int(mes_filtro))
        except:
            pass
    
    egresos_por_persona_raw = egresos_qs.values('responsable__nombre').annotate(total=Sum('monto')).order_by('-total')
    
    # Compatibilidad con template que espera persona__nombre
    egresos_por_persona = []
    for e in egresos_por_persona_raw:
        egresos_por_persona.append({
            'persona__nombre': e['responsable__nombre'],
            'total': e['total']
        })

    # Egresos por categoria
    egresos_por_categoria = MovimientoCaja.objects.filter(tipo='EGRESO').values('categoria').annotate(total=Sum('monto')).order_by('-total')

    # Balance por persona
    balance_por_persona = []
    for p in Persona.objects.all().order_by('nombre'):
        ing = MovimientoCaja.objects.filter(responsable=p, tipo='INGRESO').aggregate(s=Sum('monto'))['s'] or 0
        egr = MovimientoCaja.objects.filter(responsable=p, tipo='EGRESO').aggregate(s=Sum('monto'))['s'] or 0
        if ing or egr:
            balance_por_persona.append({
                'persona__nombre': p.nombre,
                'id': p.id,
                'ing': ing,
                'egr': egr,
                'total': ing - egr
            })

    context = {
        'movimientos': movimientos_list,
        'personas': Persona.objects.all().order_by('nombre'),
        'total_ingresos': total_ingresos_all,
        'total_egresos': total_egresos_all,
        'saldo': total_ingresos_all - total_egresos_all,
        'ingresos_count': MovimientoCaja.objects.filter(tipo='INGRESO').count(),
        'egresos_count': MovimientoCaja.objects.filter(tipo='EGRESO').count(),
        'egresos_por_persona': egresos_por_persona,
        'egresos_por_categoria': egresos_por_categoria,
        'balance_por_persona': balance_por_persona,
        'persona_filtro': responsable_filtro,
        'categoria_filtro': categoria_filtro,
        'categorias': MovimientoCaja.CATEGORIAS,
    }
    return render(request, 'caja/dashboard.html', context)
