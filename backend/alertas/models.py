from django.conf import settings
from django.db import models


class Alerta(models.Model):
    class Tipo(models.TextChoices):
        RIESGO_ALTO_MODELO = 'RIESGO_ALTO_MODELO', 'Riesgo alto del modelo'
        PRUEBA_TARJETAS = 'PRUEBA_TARJETAS', 'Prueba de tarjetas'

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        CONFIRMADA_FRAUDE = 'CONFIRMADA_FRAUDE', 'Fraude confirmado'
        DESCARTADA = 'DESCARTADA', 'Descartada'

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    autorizacion = models.ForeignKey(
        'autorizaciones.Autorizacion',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='alertas',
    )
    tarjeta = models.ForeignKey(
        'tarjetas.Tarjeta', on_delete=models.PROTECT, null=True, blank=True, related_name='alertas'
    )
    comercio = models.ForeignKey(
        'usuarios.Comercio', on_delete=models.PROTECT, null=True, blank=True, related_name='alertas'
    )
    descripcion = models.TextField()
    estado = models.CharField(max_length=17, choices=Estado.choices, default=Estado.PENDIENTE)
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='alertas_resueltas',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    # Columna de marca de agua: la ingesta por batch extrae lo que cambió desde la última corrida.
    fecha_actualizacion = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        db_table = 'alerta'
        ordering = ['-fecha_creacion', '-id']
        indexes = [models.Index(fields=['estado', '-fecha_creacion'], name='alerta_estado_fecha')]

    def __str__(self):
        return f'#{self.id} {self.tipo} {self.estado}'
