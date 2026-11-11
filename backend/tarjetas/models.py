from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q

from usuarios.models import Asociado, Comercio


class Tarjeta(models.Model):
    class Franquicia(models.TextChoices):
        VISA = 'VISA', 'Visa'
        MASTERCARD = 'MASTERCARD', 'Mastercard'

    class Estado(models.TextChoices):
        ACTIVA = 'ACTIVA', 'Activa'
        BLOQUEADA = 'BLOQUEADA', 'Bloqueada'
        CANCELADA = 'CANCELADA', 'Cancelada'

    asociado = models.ForeignKey(Asociado, on_delete=models.PROTECT, related_name='tarjetas')
    # Número completo porque los datos son sintéticos; en producción se tokenizaría (PCI DSS).
    numero = models.CharField(
        max_length=19,
        unique=True,
        validators=[RegexValidator(r'^\d{13,19}$', 'Debe tener entre 13 y 19 dígitos.')],
    )
    ultimos_4 = models.CharField(max_length=4, editable=False)
    franquicia = models.CharField(max_length=10, choices=Franquicia.choices)
    fecha_vencimiento = models.DateField(help_text='Último día del mes de vencimiento.')
    cvv_hash = models.CharField(max_length=64, editable=False)
    tiene_chip = models.BooleanField(default=True)
    cupo_total = models.DecimalField(max_digits=14, decimal_places=2)
    cupo_disponible = models.DecimalField(max_digits=14, decimal_places=2)
    fecha_emision = models.DateField()
    estado = models.CharField(
        max_length=9,
        choices=Estado.choices,
        default=Estado.ACTIVA,
        help_text='Acceso rápido. Para bloquear con historial usa la consola del analista.',
    )
    # Columna de marca de agua: la ingesta por batch extrae lo que cambió desde la última corrida.
    fecha_actualizacion = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        db_table = 'tarjeta'
        ordering = ['id']
        constraints = [
            models.CheckConstraint(
                condition=Q(cupo_disponible__gte=0), name='tarjeta_cupo_no_negativo'
            ),
            models.CheckConstraint(
                condition=Q(cupo_disponible__lte=F('cupo_total')),
                name='tarjeta_cupo_disponible_no_excede_total',
            ),
        ]

    def __str__(self):
        return f'{self.get_franquicia_display()} •••• {self.ultimos_4}'

    def save(self, *args, **kwargs):
        self.ultimos_4 = self.numero[-4:]
        super().save(*args, **kwargs)

    @property
    def bin(self) -> str:
        return self.numero[:6]


class Bloqueo(models.Model):
    """Historial de bloqueos; el estado de Tarjeta y Comercio es el acceso rápido."""

    class Tipo(models.TextChoices):
        TARJETA = 'TARJETA', 'Tarjeta'
        COMERCIO = 'COMERCIO', 'Comercio'

    class Origen(models.TextChoices):
        ASOCIADO = 'ASOCIADO', 'Asociado'
        ANALISTA = 'ANALISTA', 'Analista'
        MODELO = 'MODELO', 'Modelo'
        STREAMING = 'STREAMING', 'Streaming'

    tipo = models.CharField(max_length=8, choices=Tipo.choices)
    tarjeta = models.ForeignKey(
        Tarjeta, on_delete=models.PROTECT, null=True, blank=True, related_name='bloqueos'
    )
    comercio = models.ForeignKey(
        Comercio, on_delete=models.PROTECT, null=True, blank=True, related_name='bloqueos'
    )
    origen = models.CharField(max_length=9, choices=Origen.choices)
    motivo = models.CharField(max_length=255)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bloqueos',
        help_text='Null si fue automático.',
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True, help_text='Null mientras esté vigente.')

    class Meta:
        db_table = 'bloqueo'
        ordering = ['-fecha_inicio']
        constraints = [
            # Afecta a una tarjeta o a un comercio, nunca a ambos ni a ninguno.
            models.CheckConstraint(
                condition=(
                    Q(tipo='TARJETA', tarjeta__isnull=False, comercio__isnull=True)
                    | Q(tipo='COMERCIO', comercio__isnull=False, tarjeta__isnull=True)
                ),
                name='bloqueo_tarjeta_o_comercio',
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=F('fecha_inicio')),
                name='bloqueo_fechas_coherentes',
            ),
            # Solo un bloqueo vigente por objetivo: así cada levantamiento es inequívoco.
            models.UniqueConstraint(
                fields=['tarjeta'],
                condition=Q(fecha_fin__isnull=True, tarjeta__isnull=False),
                name='bloqueo_vigente_unico_tarjeta',
            ),
            models.UniqueConstraint(
                fields=['comercio'],
                condition=Q(fecha_fin__isnull=True, comercio__isnull=False),
                name='bloqueo_vigente_unico_comercio',
            ),
        ]

    def __str__(self):
        return f'{self.tipo} {self.tarjeta_id or self.comercio_id} ({self.origen})'
