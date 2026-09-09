from django import forms
from django.contrib import admin
from .models import Animal, Corral, Vacuna, Venta

# --- Form para que vacunas aparezcan con checkbox ---
class AnimalForm(forms.ModelForm):
    class Meta:
        model = Animal
        fields = ['numero_caravana','categoria','kg_ingreso','corral_actual','vacunas_ingreso']
        widgets = {
            'vacunas_ingreso': forms.CheckboxSelectMultiple
        }

@admin.register(Corral)
class CorralAdmin(admin.ModelAdmin):
    list_display = ('nombre_bonito','capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado','dias_objetivo')
    list_editable = ('capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado','dias_objetivo')
    fields = ('nombre','capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado')

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    form = AnimalForm
    list_display = ('numero_caravana','categoria','kg_actual','corral_actual','activo')
    list_filter = ('corral_actual','categoria')
    fields = ('numero_caravana','categoria','kg_ingreso','corral_actual','vacunas_ingreso')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.kg_actual = obj.kg_ingreso
        super().save_model(request, obj, form, change)

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('animal','kg_venta','precio_kg','fecha')

@admin.register(Vacuna)
class VacunaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

# Orden del menú
Venta._meta.verbose_name_plural = "03 Ventas"
Vacuna._meta.verbose_name_plural = "04 Vacunas"
Corral._meta.verbose_name_plural = "01 Corrals"
Animal._meta.verbose_name_plural = "02 Animals"