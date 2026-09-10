from django.urls import path
from . import views
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pesar-rapido/', views.pesar_rapido, name='pesar_rapido'),
    path('mover-rapido/', views.mover_rapido, name='mover_rapido'),
    path('vender-rapido/', views.vender_rapido, name='vender_rapido'),
    path('baja-rapida/', views.baja_rapida, name='baja_rapida'),
    path('informe-pdf/', views.informe_pdf, name='informe_pdf'),
    path('importar-excel/', views.importar_excel, name='importar_excel'),
]