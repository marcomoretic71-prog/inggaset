from django.urls import path
from .views import caja_dashboard

urlpatterns = [
    path('', caja_dashboard, name='caja_dashboard'),
]
