from django.db import models

from autorizaciones.models import Autorizacion
from usuarios.models import Asociado


class Reclamo(models.Model):
    class Estado(models.TextChoices):
        RADICADO = 'RADICADO', 'Radicado'
        EN_REVISION = 'EN_REVISION', 'En revisión'
        RESUELTO = 'RESUELTO', 'Resuelto'

    class Resultado(models.TextChoices):
        FRAUDE = 'FRAUDE', 'Fraude'
        NO_FRAUDE = 'NO_FRAUDE', 'No es fraude'

    asociado = models.ForeignKey(Asociado, on_delete=models.PROTECT, related_name='reclamos')
    # Una compra se reporta una sola vez.
    autorizacion = models.OneToOneField(
        Autorizacion, on_delete=models.PROTECT, related_name='reclamo'
    )
    descripcion = models.TextField()
    estado = models.CharField(max_length=11, choices=Estado.choices, default=Estado.RADICADO)
    # Lo define el analista al resolver; null mientras el reclamo siga abierto.
    resultado = models.CharField(  # noqa: DJ001 - null significa 'sin resolver' en la ingesta
        max_length=9, choices=Resultado.choices, null=True, blank=True
    )
    fecha_radicacion = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'reclamo'
        ordering = ['-fecha_radicacion', '-id']

    def __str__(self):
        return f'#{self.id} {self.estado}'
