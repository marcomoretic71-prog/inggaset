from django import forms
from django.contrib import admin
from django.utils import timezone
from.models import Animal, Corral, Vacuna, Venta, Movimiento
from datetime import date

# --- Form para que vacunas aparezcan con checkbox ---
class AnimalForm(forms.ModelForm):
    class Meta:
        model = Animal
        fields = ['numero_caravana','categoria','kg_ingreso','corral_actual','fecha_ingreso','vacunas_ingreso','activo']
        widgets = {
            'vacunas_ingreso': forms.CheckboxSelectMultiple()
        }

class MovimientoInline(admin.TabularInline):
    model = Movimiento
    extra = 0
    readonly_fields = ('fecha', 'corral_origen', 'corral_destino', 'peso_en_movimiento')
    can_delete = False
    ordering = ('-fecha',)

@admin.register(Corral)
class CorralAdmin(admin.ModelAdmin):
    list_display = ('nombre_bonito','capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado','dias_objetivo')
    list_editable = ('capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado','dias_objetivo')
    fields = ('nombre','capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado')

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    form = AnimalForm
    list_display = ('numero_caravana','categoria','kg_actual','corral_actual','fecha_ingreso_corral','dias_en_corral','listo_para','activo')
    list_filter = ('corral_actual','categoria','activo')
    list_per_page = 100
    search_fields = ('numero_caravana',)
    actions = ['mover_a_recepcion', 'mover_a_recria_1', 'mover_a_recria_2', 'mover_a_terminacion_1', 'mover_a_terminacion_2']
    # ACÁ SAQUÉ kg_actual para que no aparezca al cargar
    fields = ('numero_caravana','categoria','kg_ingreso','corral_actual','fecha_ingreso_corral','fecha_ingreso','vacunas_ingreso','activo')
    readonly_fields = ('fecha_ingreso_corral',)
    inlines = [MovimientoInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.kg_actual = obj.kg_ingreso
            obj.fecha_ingreso_corral = date.today()
            obj.fecha_ingreso = date.today()
        else:
            if 'corral_actual' in form.changed_data:
                animal_viejo = Animal.objects.get(pk=obj.pk)
                origen = animal_viejo.corral_actual
                destino = obj.corral_actual
                if origen!= destino:
                    Movimiento.objects.create(
                        animal=obj,
                        corral_origen=origen,
                        corral_destino=destino,
                        peso_en_movimiento=obj.kg_actual,
                        fecha=date.today()
                    )
                    obj.fecha_ingreso_corral = date.today()
        super().save_model(request, obj, form, change)

    def get_corral(self, nombre):
        return Corral.objects.filter(nombre=nombre).first()

    def _mover_masivo(self, request, queryset, nombre_corral):
        corral_destino = self.get_corral(nombre_corral)
        if not corral_destino:
            return
        count = 0
        for animal in queryset:
            if animal.corral_actual!= corral_destino:
                Movimiento.objects.create(
                    animal=animal,
                    corral_origen=animal.corral_actual,
                    corral_destino=corral_destino,
                    peso_en_movimiento=animal.kg_actual,
                    fecha=date.today()
                )
                animal.corral_actual = corral_destino
                animal.fecha_ingreso_corral = date.today()
                animal.save()
                count += 1
        self.message_user(request, f'{count} animales movidos a {corral_destino.nombre_bonito} el {date.today().strftime("%d/%m/%Y")}')

    @admin.action(description='Mover seleccionados a Recepción')
    def mover_a_recepcion(self, request, queryset): self._mover_masivo(request, queryset, 'recepcion')
    @admin.action(description='Mover seleccionados a Recría 1')
    def mover_a_recria_1(self, request, queryset): self._mover_masivo(request, queryset, 'recria_1')
    @admin.action(description='Mover seleccionados a Recría 2')
    def mover_a_recria_2(self, request, queryset): self._mover_masivo(request, queryset, 'recria_2')
    @admin.action(description='Mover seleccionados a Terminación 1')
    def mover_a_terminacion_1(self, request, queryset): self._mover_masivo(request, queryset, 'terminacion_1')
    @admin.action(description='Mover seleccionados a Terminación 2')
    def mover_a_terminacion_2(self, request, queryset): self._mover_masivo(request, queryset, 'terminacion_2')

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('animal','kg_venta','precio_kg','fecha')

@admin.register(Vacuna)
class VacunaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('animal','corral_origen','corral_destino','peso_en_movimiento','fecha')
    list_filter = ('corral_destino','fecha','corral_origen')
    search_fields = ('animal__numero_caravana',)
    date_hierarchy = 'fecha'

# Orden del menú
Venta._meta.verbose_name_plural = "03 Ventas"
Vacuna._meta.verbose_name_plural = "04 Vacunas"
Corral._meta.verbose_name_plural = "01 Corrals"
Animal._meta.verbose_name_plural = "02 Animals"
Movimiento._meta.verbose_name_plural = "05 Movimientos"
