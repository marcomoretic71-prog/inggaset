from django.urls import path
from .views import caja_dashboard
from .pdf_caja import informe_pdf_caja

urlpatterns = [
    path('', caja_dashboard, name='caja_dashboard'),
    path('pdf/', informe_pdf_caja, name='informe_pdf_caja'),
]