from django.db.models import Sum
from django.http import HttpResponse
from .models import MovimientoCaja, Persona
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

def informe_pdf_caja(request):
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

    total_ing = movimientos.filter(tipo='INGRESO').aggregate(s=Sum('monto'))['s'] or 0
    total_egr = movimientos.filter(tipo='EGRESO').aggregate(s=Sum('monto'))['s'] or 0
    saldo = total_ing - total_egr

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Informe_Caja_{date.today()}.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    ancho, alto = A4

    p.setFont("Helvetica-Bold", 14)
    p.drawString(1.5*cm, alto - 1.5*cm, "IngGaset - Caja Chica - Informe")

    filtro_txt = []
    if responsable_filtro:
        try:
            per = Persona.objects.get(id=responsable_filtro)
            filtro_txt.append(f"Persona: {per.nombre}")
        except:
            pass
    if mes_filtro:
        filtro_txt.append(f"Mes: {mes_filtro}")
    if categoria_filtro:
        filtro_txt.append(f"Categoria: {categoria_filtro}")
    filtro_str = " | ".join(filtro_txt) if filtro_txt else "Todos los movimientos"

    p.setFont("Helvetica", 9)
    p.drawString(1.5*cm, alto - 2.1*cm, f"Fecha: {date.today().strftime('%d/%m/%Y')} | {filtro_str}")
    p.setFont("Helvetica-Bold", 9)
    p.drawString(1.5*cm, alto - 2.6*cm, f"INGRESOS: ${total_ing:,.0f} | EGRESOS: ${total_egr:,.0f} | SALDO: ${saldo:,.0f}")

    y = alto - 3.5*cm
    x_fecha = 1.5*cm
    x_tipo = 3.5*cm
    x_quien = 5.0*cm
    x_cat = 7.5*cm
    x_det = 10.2*cm
    x_monto = 16.5*cm

    def cabecera(y_pos):
        p.setFont("Helvetica-Bold", 6.5)
        p.drawString(x_fecha, y_pos, "FECHA")
        p.drawString(x_tipo, y_pos, "TIPO")
        p.drawString(x_quien, y_pos, "QUIEN")
        p.drawString(x_cat, y_pos, "CATEGORIA")
        p.drawString(x_det, y_pos, "DETALLE")
        p.drawString(x_monto, y_pos, "MONTO")
        p.line(1.5*cm, y_pos-0.2*cm, 19.5*cm, y_pos-0.2*cm)
        p.setFont("Helvetica", 6.5)
        return y_pos - 0.6*cm

    y = cabecera(y)

    for mov in movimientos:
        if y < 2*cm:
            p.showPage()
            y = alto - 1.5*cm
            y = cabecera(y)
        quien = mov.responsable.nombre if mov.responsable else '-'
        if len(quien) > 12:
            quien = quien[:11]
        cat = mov.categoria.replace('_',' ')[:12]
        detalle = (mov.descripcion or '')[:38]
        monto_txt = f"${mov.monto:,.0f}"
        if mov.tipo == 'EGRESO':
            monto_txt = f"-{monto_txt}"
            p.setFillColorRGB(0.7, 0.1, 0.1)
        else:
            p.setFillColorRGB(0.1, 0.4, 0.2)
        
        p.drawString(x_fecha, y, mov.fecha.strftime('%d/%m/%Y'))
        p.setFillColorRGB(0,0,0)
        p.drawString(x_tipo, y, mov.tipo[:3])
        p.drawString(x_quien, y, quien)
        p.drawString(x_cat, y, cat)
        p.drawString(x_det, y, detalle)
        p.drawString(x_monto, y, monto_txt)
        y -= 0.38*cm

    p.showPage()
    p.save()
    return response