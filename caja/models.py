from django.db import models
from datetime import date

class Persona(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "00 Personas / Responsables"

class MovimientoCaja(models.Model):
    TIPO_CHOICES = [
        ('INGRESO', 'Ingreso'),
        ('EGRESO', 'Egreso'),
    ]
    CATEGORIAS = [
        ('VENTA_HACIENDA', 'Venta de Hacienda'),
        ('COMPRA_HACIENDA', 'Compra de Hacienda'),
        ('SANIDAD', 'Sanidad / Vacunas'),
        ('ALIMENTACION', 'Alimentación'),
        ('COMBUSTIBLE', 'Combustible'),
        ('PERSONAL', 'Personal'),
        ('MANTENIMIENTO', 'Mantenimiento'),
        ('OTROS', 'Otros'),
    ]

    fecha = models.DateField(default=date.today, verbose_name="Fecha")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='OTROS')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    responsable = models.ForeignKey(Persona, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Quién hizo el gasto")
    descripcion = models.CharField(max_length=255, blank=True, verbose_name="Descripción")

    def __str__(self):
        return f"{self.fecha} - {self.tipo} ${self.monto} - {self.responsable}"

    class Meta:
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "06 Caja"
        ordering = ['-fecha', '-id']