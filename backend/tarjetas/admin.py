from django import forms
from django.contrib import admin

from tarjetas.cvv import hashear_cvv
from tarjetas.models import Bloqueo, Tarjeta


class TarjetaAdminForm(forms.ModelForm):
    """Pide el CVV en claro solo para hashearlo; el hash nunca se muestra."""

    cvv = forms.RegexField(
        regex=r'^\d{3,4}$',
        required=False,
        widget=forms.PasswordInput,
        help_text='Requerido al crear. Déjalo vacío para conservar el actual.',
    )
    cupo_disponible = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        help_text='Vacío al crear: toma el cupo total.',
    )

    class Meta:
        model = Tarjeta
        fields = [
            'asociado',
            'numero',
            'cvv',
            'franquicia',
            'fecha_vencimiento',
            'tiene_chip',
            'cupo_total',
            'cupo_disponible',
            'fecha_emision',
            'estado',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estado = self.fields['estado']
        if self.instance.pk and self.instance.estado == Tarjeta.Estado.BLOQUEADA:
            estado.disabled = True
            estado.help_text = 'Bloqueada: el bloqueo se levanta desde la consola del analista.'
        else:
            estado.choices = [
                (valor, texto)
                for valor, texto in estado.choices
                if valor != Tarjeta.Estado.BLOQUEADA
            ]
            estado.help_text = 'Para bloquear una tarjeta usa la consola del analista.'

    def clean(self):
        datos = super().clean()
        if not self.instance.pk and not datos.get('cvv'):
            self.add_error('cvv', 'El CVV es requerido al crear la tarjeta.')
        if self.instance.pk and 'numero' in self.changed_data and not datos.get('cvv'):
            self.add_error('cvv', 'Cambiaste el número de la tarjeta: ingresa el CVV de nuevo.')
        if datos.get('cupo_disponible') is None:
            if self.instance.pk:
                self.add_error('cupo_disponible', 'Este campo es requerido.')
            else:
                datos['cupo_disponible'] = datos.get('cupo_total')
        total, disponible = datos.get('cupo_total'), datos.get('cupo_disponible')
        if total is not None and disponible is not None and disponible > total:
            self.add_error('cupo_disponible', 'El cupo disponible no puede superar al cupo total.')
        return datos

    def save(self, commit=True):
        tarjeta = super().save(commit=False)
        cvv = self.cleaned_data.get('cvv')
        if cvv:
            tarjeta.cvv_hash = hashear_cvv(tarjeta.numero, cvv)
        if commit:
            tarjeta.save()
        return tarjeta


@admin.register(Tarjeta)
class TarjetaAdmin(admin.ModelAdmin):
    form = TarjetaAdminForm
    list_display = ('id', 'ultimos_4', 'franquicia', 'asociado', 'cupo_disponible', 'estado')
    list_filter = ('estado', 'franquicia')
    search_fields = ('ultimos_4', 'asociado__numero_documento')
    raw_id_fields = ('asociado',)


@admin.register(Bloqueo)
class BloqueoAdmin(admin.ModelAdmin):
    """Historial de solo lectura: los bloqueos se aplican y levantan desde la consola."""

    list_display = ('id', 'tipo', 'tarjeta', 'comercio', 'origen', 'fecha_inicio', 'fecha_fin')
    list_filter = ('tipo', 'origen')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
