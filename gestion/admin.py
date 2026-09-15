from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Animal, Corral, Vacuna, Venta, Movimiento, Baja, normalizar_caravana
from datetime import date

class MovimientoInline(admin.TabularInline):
    model = Movimiento
    extra = 0
    readonly_fields = ('fecha', 'corral_origen', 'corral_destino', 'peso_en_movimiento')
    can_delete = False
    ordering = ('-fecha',)

class AnimalForm(forms.ModelForm):
    class Meta:
        model = Animal
        fields = ['numero_caravana','categoria','kg_ingreso','corral_actual','vacunas_ingreso','fecha_ingreso','activo']
        widgets = {
            'vacunas_ingreso': forms.CheckboxSelectMultiple
        }

    def clean_numero_caravana(self):
        raw = self.cleaned_data.get('numero_caravana', '')
        norm = normalizar_caravana(raw)
        if not norm:
            raise ValidationError("Ingresá un número de caravana válido.")
        qs = Animal.objects.filter(numero_caravana=norm)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            existente = qs.first()
            if existente.activo:
                corral = existente.corral_actual.nombre_bonito if existente.corral_actual else "sin corral"
                raise ValidationError(f"❌ La caravana {norm} YA EXISTE: está activa en {corral} con {existente.kg_actual}kg. No se puede cargar duplicada.")
            else:
                venta = Venta.objects.filter(animal=existente).first()
                if venta:
                    raise ValidationError(f"❌ La caravana {norm} ya fue VENDIDA el {venta.fecha} por ${venta.precio_kg}/kg. No se puede reutilizar.")
                baja = Baja.objects.filter(animal=existente).first()
                if baja:
                    raise ValidationError(f"❌ La caravana {norm} ya fue dada de BAJA el {baja.fecha} ({baja.motivo}). No se puede reutilizar.")
                raise ValidationError(f"❌ La caravana {norm} ya existe en el sistema (inactiva). No se puede reutilizar.")
        return norm

@admin.register(Corral)
class CorralAdmin(admin.ModelAdmin):
    list_display = ('nombre_bonito','capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado','dias_objetivo')
    list_editable = ('capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado','dias_objetivo')
    fields = ('nombre','capacidad','porcentaje_alimento','peso_entrada','peso_salida','gdpv_esperado','dias_objetivo')

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    form = AnimalForm
    list_display = ('numero_caravana','categoria','kg_actual','corral_actual','fecha_ingreso_corral','dias_en_corral','listo_para','activo')
    list_filter = ('corral_actual','categoria','activo')
    list_per_page = 100
    search_fields = ('numero_caravana',)
    readonly_fields = ('fecha_ingreso_corral',)
    inlines = [MovimientoInline]

    def save_model(self, request, obj, form, change):
        # El bloqueo ya está en clean_numero_caravana + model clean
        if not change:
            obj.kg_actual = obj.kg_ingreso
            obj.fecha_ingreso_corral = date.today()
        try:
            obj.full_clean()
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            # Mostrar el error bonito en el admin
            from django.contrib import messages
            for field, errs in e.message_dict.items():
                for err in errs:
                    self.message_user(request, err, level=messages.ERROR)
            # No guardar
            return

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
        self.message_user(request, f'{count} animales movidos a {corral_destino.nombre_bonito}')

    @admin.action(description='Mover a Recepción')
    def mover_a_recepcion(self, request, queryset): self._mover_masivo(request, queryset, 'recepcion')
    @admin.action(description='Mover a Recría 1')
    def mover_a_recria_1(self, request, queryset): self._mover_masivo(request, queryset, 'recria_1')
    @admin.action(description='Mover a Recría 2')
    def mover_a_recria_2(self, request, queryset): self._mover_masivo(request, queryset, 'recria_2')
    @admin.action(description='Mover a Terminación 1')
    def mover_a_terminacion_1(self, request, queryset): self._mover_masivo(request, queryset, 'terminacion_1')
    @admin.action(description='Mover a Terminación 2')
    def mover_a_terminacion_2(self, request, queryset): self._mover_masivo(request, queryset, 'terminacion_2')
    @admin.action(description='Mover a Venta')
    def mover_a_venta(self, request, queryset): self._mover_masivo(request, queryset, 'venta')

    actions = ['mover_a_recepcion', 'mover_a_recria_1', 'mover_a_recria_2', 'mover_a_terminacion_1', 'mover_a_terminacion_2', 'mover_a_venta']

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

Venta._meta.verbose_name_plural = "03 Ventas"
Vacuna._meta.verbose_name_plural = "04 Vacunas"
Corral._meta.verbose_name_plural = "01 Corrals"
Animal._meta.verbose_name_plural = "02 Animals"
Movimiento._meta.verbose_name_plural = "05 Movimientos"
