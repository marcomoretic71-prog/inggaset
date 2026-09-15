from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
import re

# --- UTIL NORMALIZAR CARAVANA ---
def normalizar_caravana(valor: str) -> str:
    """Deja solo digitos, saca espacios y ceros a la izquierda. 000123 -> 123"""
    if not valor:
        return ""
    v = str(valor).strip()
    v = re.sub(r'\D', '', v)  # solo numeros
    v = v.lstrip('0') or '0'
    return v

class Vacuna(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.nombre

class Corral(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre interno")
    capacidad = models.IntegerField(default=0)
    porcentaje_alimento = models.FloatField(default=2.0, verbose_name="% de Alimento")
    peso_entrada = models.FloatField(default=0)
    peso_salida = models.FloatField(default=0)
    gdpv_esperado = models.FloatField(default=0)
    dias_objetivo = models.IntegerField(default=0)
    kg_objetivo = models.IntegerField(default=0, verbose_name="Kg Objetivo")

    @property
    def nombre_bonito(self):
        return self.nombre.replace('_', ' ').title()

    @property
    def es_terminacion(self):
        return 'terminacion' in self.nombre

    def __str__(self): return self.nombre_bonito
    class Meta:
        verbose_name_plural = "01 Corrals"

class Animal(models.Model):
    CATEGORIAS = [
        ('ternero', 'Ternero'),
        ('ternera', 'Ternera'),
        ('novillo', 'Novillo'),
        ('vaquillona', 'Vaquillona'),
        ('vaca', 'Vaca'),
        ('toro', 'Toro'),
        ('hembra', 'Hembra'),
        ('mej', 'MEJ'),
    ]

    numero_caravana = models.CharField(max_length=20, unique=True, verbose_name="N° Caravana", db_index=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='ternero')
    kg_ingreso = models.FloatField(verbose_name="Kg Ingreso", default=80)
    kg_actual = models.FloatField(verbose_name="Kg Actual", blank=True, null=True)
    corral_actual = models.ForeignKey(Corral, on_delete=models.SET_NULL, null=True, related_name="animales", verbose_name="Corral Actual")
    vacunas_ingreso = models.ManyToManyField(Vacuna, blank=True)
    fecha_ingreso = models.DateField(default=date.today)
    fecha_ingreso_corral = models.DateField(default=date.today)
    activo = models.BooleanField(default=True)

    def clean(self):
        super().clean()
        norm = normalizar_caravana(self.numero_caravana)
        if not norm:
            raise ValidationError({"numero_caravana": "Ingresá un número de caravana válido."})
        self.numero_caravana = norm
        qs = Animal.objects.filter(numero_caravana=norm)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            existente = qs.first()
            if existente.activo:
                corral = existente.corral_actual.nombre_bonito if existente.corral_actual else "sin corral"
                raise ValidationError({"numero_caravana": f"❌ La caravana {norm} YA EXISTE: está activa en {corral} con {existente.kg_actual}kg. No se puede cargar duplicada."})
            else:
                # ver si fue venta
                if Venta.objects.filter(animal=existente).exists():
                    v = Venta.objects.filter(animal=existente).first()
                    raise ValidationError({"numero_caravana": f"❌ La caravana {norm} ya fue VENDIDA el {v.fecha} por ${v.precio_kg}/kg. No se puede reutilizar."})
                if Baja.objects.filter(animal=existente).exists():
                    b = Baja.objects.filter(animal=existente).first()
                    raise ValidationError({"numero_caravana": f"❌ La caravana {norm} ya fue dada de BAJA el {b.fecha} ({b.motivo}). No se puede reutilizar."})
                raise ValidationError({"numero_caravana": f"❌ La caravana {norm} ya existe en el sistema (inactiva). No se puede reutilizar."})

    @property
    def alimento_diario_kg(self):
        try:
            pct = self.corral_actual.porcentaje_alimento if self.corral_actual else 0
            if pct == 0 or self.corral_actual.nombre == 'venta':
                return 0
            return round((self.kg_actual or 0) * pct / 100, 1)
        except:
            return 0

    @property
    def kg_faltantes(self):
        if self.corral_actual and self.corral_actual.peso_salida and self.corral_actual.peso_salida > 0:
            falta = self.corral_actual.peso_salida - (self.kg_actual or 0)
            return round(max(0, falta), 1)
        return 0

    @property
    def listo_para_mover(self):
        if self.corral_actual and self.corral_actual.nombre == 'venta':
            return False
        if self.corral_actual and self.corral_actual.peso_salida > 0:
            return (self.kg_actual or 0) >= self.corral_actual.peso_salida
        return False

    @property
    def listo_para(self):
        if not self.corral_actual:
            return "-"
        if self.corral_actual.nombre == 'venta':
            return "venta"
        if self.kg_faltantes <= 0 and self.corral_actual.peso_salida > 0:
            if 'terminacion' in self.corral_actual.nombre:
                return "venta"
            else:
                return "mover"
        return f"Faltan {self.kg_faltantes}kg"

    @property
    def dias_en_corral(self):
        if self.fecha_ingreso_corral:
            return (date.today() - self.fecha_ingreso_corral).days
        return 0

    @property
    def dias_restantes_estimados(self):
        if self.corral_actual and self.corral_actual.gdpv_esperado and self.corral_actual.gdpv_esperado > 0:
            if self.kg_faltantes > 0:
                return int(self.kg_faltantes / self.corral_actual.gdpv_esperado)
        return 0

    def save(self, *args, **kwargs):
        self.numero_caravana = normalizar_caravana(self.numero_caravana)
        if not self.kg_actual:
            self.kg_actual = self.kg_ingreso
        # validación que bloquea duplicado con mensaje bonito
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_caravana} - {self.kg_actual}Kg"

    class Meta:
        verbose_name_plural = "02 Animals"
        ordering = ['numero_caravana']

class Pesada(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name="pesada_set")
    fecha = models.DateField(default=date.today)
    peso = models.FloatField()
    observaciones = models.CharField(max_length=200, blank=True)
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # evita loop de full_clean
        Animal.objects.filter(pk=self.animal.pk).update(kg_actual=self.peso)
    def __str__(self): return f"Pesada {self.animal.numero_caravana} - {self.peso}Kg"
    class Meta:
        verbose_name_plural = "Pesadas"
        ordering = ['-fecha']

class Baja(models.Model):
    MOTIVOS = [('muerte','muerte'), ('MUERTE','Muerte'), ('VENTA','Venta'), ('OTRO','Otro'), ('descarte','Descarte'), ('enfermedad','Enfermedad'), ('otro','Otro')]
    animal = models.ForeignKey(Animal, on_delete=models.PROTECT)
    fecha = models.DateField(default=date.today)
    motivo = models.CharField(max_length=20, choices=MOTIVOS, default='muerte')
    kg_baja = models.FloatField(default=0, verbose_name="Kg a la baja")
    observaciones = models.TextField(blank=True)
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.animal.activo:
            Animal.objects.filter(pk=self.animal.pk).update(activo=False)
    def __str__(self): return f"Baja {self.animal.numero_caravana} - {self.motivo}"
    class Meta:
        verbose_name_plural = "Bajas"

class Movimiento(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name="movimientos")
    corral_origen = models.ForeignKey(Corral, on_delete=models.SET_NULL, null=True, blank=True, related_name="salidas")
    corral_destino = models.ForeignKey(Corral, on_delete=models.SET_NULL, null=True, blank=True, related_name="entradas")
    peso_en_movimiento = models.FloatField(null=True, blank=True)
    fecha = models.DateField(default=date.today)
    def __str__(self): return f"{self.animal.numero_caravana} {self.corral_origen} -> {self.corral_destino}"
    class Meta:
        verbose_name_plural = "05 Movimientos"
        ordering = ['-fecha']

class Venta(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.PROTECT, verbose_name="Animal Vendido")
    kg_venta = models.FloatField()
    precio_kg = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateField(default=date.today)

    @property
    def total_venta(self): return float(self.kg_venta) * float(self.precio_kg)

    def save(self, *args, **kwargs):
        es_nueva = self._state.adding
        super().save(*args, **kwargs)
        if self.animal.activo:
            Animal.objects.filter(pk=self.animal.pk).update(activo=False)
        if es_nueva:
            try:
                from caja.models import MovimientoCaja
                total = float(self.kg_venta) * float(self.precio_kg)
                if not MovimientoCaja.objects.filter(descripcion__icontains=f"Venta {self.animal.numero_caravana}").exists():
                    MovimientoCaja.objects.create(
                        fecha=self.fecha,
                        tipo='INGRESO',
                        categoria='VENTA_HACIENDA',
                        monto=total,
                        descripcion=f"Venta {self.animal.numero_caravana} - {self.kg_venta}kg x ${self.precio_kg}"
                    )
            except Exception as e:
                print(f"Error caja: {e}")

    def __str__(self): return f"Venta {self.animal.numero_caravana}"
    class Meta:
        verbose_name_plural = "03 Ventas"
