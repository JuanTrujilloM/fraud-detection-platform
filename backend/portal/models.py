from django.db import models

from autorizaciones.models import Autorizacion
from usuarios.models import Asociado


class Reclamo(models.Model):
    class Estado(models.TextChoices):
        RADICADO = 'RADICADO', 'Radicado'
        EN_REVISION = 'EN_REVISION', 'En revisión'
        RESUELTO = 'RESUELTO', 'Resuelto'

    asociado = models.ForeignKey(Asociado, on_delete=models.PROTECT, related_name='reclamos')
    # Una compra se reporta una sola vez.
    autorizacion = models.OneToOneField(
        Autorizacion, on_delete=models.PROTECT, related_name='reclamo'
    )
    descripcion = models.TextField()
    estado = models.CharField(max_length=11, choices=Estado.choices, default=Estado.RADICADO)
    fecha_radicacion = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'reclamo'
        ordering = ['-fecha_radicacion', '-id']

    def __str__(self):
        return f'#{self.id} {self.estado}'
