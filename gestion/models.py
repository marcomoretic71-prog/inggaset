from datetime import date
from django.db import models

class Vacuna(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self): return self.nombre

class Corral(models.Model):
    NOMBRES = [
        ('recepcion', 'Recepción'),
        ('recria_1', 'Recría 1'),
        ('recria_2', 'Recría 2'),
        ('terminacion_1', 'Terminación 1'),
        ('terminacion_2', 'Terminación 2'),
    ]
    nombre = models.CharField(max_length=20, choices=NOMBRES, unique=True)
    capacidad = models.IntegerField(default=50)
    porcentaje_alimento = models.FloatField(default=2.0, verbose_name="% alimento")
    peso_entrada = models.FloatField(default=0)
    peso_salida = models.FloatField(default=0)
    gdpv_esperado = models.FloatField(default=0.8)
    dias_objetivo = models.IntegerField(default=30)
    kg_objetivo = models.IntegerField(default=250)

    def save(self, *args, **kwargs):
        if self.peso_salida:
            self.kg_objetivo = int(self.peso_salida)
        if self.peso_salida and self.gdpv_esperado and self.peso_salida > self.peso_entrada:
            try:
                self.dias_objetivo = int((self.peso_salida - self.peso_entrada) / self.gdpv_esperado)
            except:
                pass
        super().save(*args, **kwargs)

    @property
    def nombre_bonito(self):
        return dict(self.NOMBRES).get(self.nombre, self.nombre)

    @property
    def es_terminacion(self):
        return self.nombre in ['terminacion_1', 'terminacion_2']

    def __str__(self):
        return self.nombre_bonito

class Animal(models.Model):
    CATEGORIAS = [
        ('macho', 'Macho'),
        ('hembra', 'Hembra'),
        ('castrado', 'Castrado'),
        ('vaquillona', 'Vaquillona'),
        ('vaca', 'Vaca'),
        ('toro', 'Toro'),
        ('novillo', 'Novillo'),
        ('macho_entero', 'Macho entero'),
    ]
    numero_caravana = models.CharField(max_length=20, unique=True)
    categoria = models.CharField(max_length=15, choices=CATEGORIAS, default='macho')
    kg_ingreso = models.FloatField(default=150)
    kg_actual = models.FloatField(default=150)
    corral_actual = models.ForeignKey(Corral, on_delete=models.SET_NULL, null=True)
    vacunas_ingreso = models.ManyToManyField(Vacuna, blank=True)
    fecha_ingreso_corral = models.DateField(default=date.today)
    fecha_ingreso = models.DateField(default=date.today)
    activo = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.kg_actual:
            self.kg_actual = self.kg_ingreso
        super().save(*args, **kwargs)

    @property
    def dias_en_corral(self):
        return (date.today() - self.fecha_ingreso_corral).days if self.fecha_ingreso_corral else 0

    @property
    def ganancia_diaria(self):
        dias = (date.today() - self.fecha_ingreso).days
        if dias > 0:
            return round((self.kg_actual - self.kg_ingreso) / dias, 2)
        return 0

    @property
    def alimento_diario_kg(self):
        if not self.corral_actual:
            return 0
        return round(self.kg_actual * self.corral_actual.porcentaje_alimento / 100, 2)

    @property
    def kg_faltantes(self):
        if not self.corral_actual or self.corral_actual.peso_salida == 0:
            return 0
        falta = self.corral_actual.peso_salida - self.kg_actual
        if falta < 0:
            falta = 0
        return round(falta, 1)

    @property
    def dias_restantes_estimados(self):
        if not self.corral_actual or self.corral_actual.gdpv_esperado == 0:
            return 0
        if self.kg_faltantes <= 0:
            return 0
        return int(self.kg_faltantes / self.corral_actual.gdpv_esperado)

    @property
    def es_terminacion(self):
        if not self.corral_actual:
            return False
        return self.corral_actual.es_terminacion

    def _cumple_salida(self):
        if not self.corral_actual:
            return False
        por_kg = False
        if self.corral_actual.peso_salida:
            por_kg = self.kg_actual >= self.corral_actual.peso_salida
        por_dias = False
        if self.corral_actual.dias_objetivo:
            por_dias = self.dias_en_corral >= self.corral_actual.dias_objetivo
        return por_kg or por_dias

    @property
    def listo_para_mover(self):
        if self.es_terminacion:
            return False
        return self._cumple_salida()

    @property
    def listo_para_venta(self):
        if not self.es_terminacion:
            return False
        return self._cumple_salida()

    @property
    def listo_para(self):
        if self.listo_para_venta:
            return 'venta'
        if self.listo_para_mover:
            return 'mover'
        return None

    def __str__(self):
        return self.numero_caravana

class Pesada(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE)
    peso = models.FloatField()
    fecha = models.DateField(default=date.today)

class Movimiento(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='movimientos')
    corral_origen = models.ForeignKey(Corral, on_delete=models.SET_NULL, null=True, related_name='origen')
    corral_destino = models.ForeignKey(Corral, on_delete=models.SET_NULL, null=True, related_name='destino')
    peso_en_movimiento = models.FloatField(default=0)
    fecha = models.DateField(default=date.today)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        origen = self.corral_origen.nombre_bonito if self.corral_origen else "Ingreso"
        destino = self.corral_destino.nombre_bonito if self.corral_destino else "-"
        return f"{self.animal.numero_caravana}: {origen} -> {destino} ({self.fecha})"

class Venta(models.Model):
    animal = models.OneToOneField(Animal, on_delete=models.CASCADE)
    kg_venta = models.FloatField()
    precio_kg = models.FloatField()
    comprador = models.CharField(max_length=100, blank=True)
    fecha = models.DateField(default=date.today)

class Baja(models.Model):
    MOTIVOS = [('muerte','Muerte'),('descarte','Descarte'),('enfermedad','Enfermedad'),('otro','Otro')]
    animal = models.OneToOneField(Animal, on_delete=models.CASCADE, related_name='baja')
    motivo = models.CharField(max_length=20, choices=MOTIVOS, default='muerte')
    observacion = models.CharField(max_length=200, blank=True)
    kg_baja = models.FloatField()
    fecha = models.DateField(default=date.today)