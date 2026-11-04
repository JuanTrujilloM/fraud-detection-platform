from django.db import models
from django.utils import timezone

from tarjetas.models import Tarjeta
from usuarios.models import Comercio


class Autorizacion(models.Model):
    class Canal(models.TextChoices):
        PRESENCIAL = 'PRESENCIAL', 'Presencial'
        EN_LINEA = 'EN_LINEA', 'En línea'

    class ModoLectura(models.TextChoices):
        CHIP = 'CHIP', 'Chip'
        BANDA = 'BANDA', 'Banda'
        DIGITADA = 'DIGITADA', 'Digitada'

    class Resultado(models.TextChoices):
        APROBADA = 'APROBADA', 'Aprobada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    class MotivoRechazo(models.TextChoices):
        COMERCIO_BLOQUEADO = 'COMERCIO_BLOQUEADO', 'Comercio bloqueado'
        CANAL_NO_PERMITIDO = 'CANAL_NO_PERMITIDO', 'Canal no permitido'
        TARJETA_INEXISTENTE = 'TARJETA_INEXISTENTE', 'Tarjeta inexistente'
        TARJETA_BLOQUEADA = 'TARJETA_BLOQUEADA', 'Tarjeta bloqueada'
        TARJETA_CANCELADA = 'TARJETA_CANCELADA', 'Tarjeta cancelada'
        DATOS_INVALIDOS = 'DATOS_INVALIDOS', 'Datos inválidos'
        TARJETA_VENCIDA = 'TARJETA_VENCIDA', 'Tarjeta vencida'
        CVV_INVALIDO = 'CVV_INVALIDO', 'CVV inválido'
        CUPO_INSUFICIENTE = 'CUPO_INSUFICIENTE', 'Cupo insuficiente'
        RIESGO_ALTO = 'RIESGO_ALTO', 'Riesgo alto'

    tarjeta = models.ForeignKey(Tarjeta, on_delete=models.PROTECT, related_name='autorizaciones')
    comercio = models.ForeignKey(Comercio, on_delete=models.PROTECT, related_name='autorizaciones')
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    canal = models.CharField(max_length=10, choices=Canal.choices)
    modo_lectura = models.CharField(max_length=8, choices=ModoLectura.choices)
    resultado = models.CharField(max_length=9, choices=Resultado.choices)
    motivo_rechazo = models.CharField(  # noqa: DJ001 - null significa "sin rechazo" en la ingesta
        max_length=20, choices=MotivoRechazo.choices, null=True, blank=True
    )
    probabilidad_fraude = models.FloatField(
        null=True, blank=True, help_text='Null si no se consultó el modelo o no respondió.'
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    fecha_hora = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'autorizacion'
        ordering = ['-fecha_hora', '-id']
        indexes = [
            models.Index(fields=['tarjeta', '-fecha_hora'], name='autorizacion_tarjeta_fecha'),
            models.Index(fields=['comercio', '-fecha_hora'], name='autorizacion_comercio_fecha'),
        ]

    def __str__(self):
        return f'#{self.id} {self.resultado} {self.monto}'
