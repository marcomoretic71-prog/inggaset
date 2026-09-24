from django.urls import path
from . import views
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('alta-animal/', views.alta_animal, name='alta_animal'),
    path('pesar-rapido/', views.pesar_rapido, name='pesar_rapido'),
    path('mover-rapido/', views.mover_rapido, name='mover_rapido'),
    path('mover-masivo/', views.mover_masivo, name='mover_masivo'),
    path('vender-rapido/', views.vender_rapido, name='vender_rapido'),
    path('baja-rapida/', views.baja_rapida, name='baja_rapida'),
    path('informe-pdf/', views.informe_pdf, name='informe_pdf'),
    path('importar-excel/', views.importar_excel, name='importar_excel'),
]
