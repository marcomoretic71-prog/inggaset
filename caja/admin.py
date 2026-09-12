from django.contrib import admin
from .models import MovimientoCaja, Persona

@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo', 'categoria', 'responsable', 'monto', 'descripcion')
    list_filter = ('tipo', 'categoria', 'responsable', 'fecha')
    search_fields = ('descripcion', 'responsable__nombre')
    date_hierarchy = 'fecha'