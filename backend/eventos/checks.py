from pathlib import Path

from django.conf import settings
from django.core.checks import Error, register


@register()
def verificar_log_de_eventos(app_configs, **kwargs):
    ruta = Path(settings.EVENTOS_LOG_PATH)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, 'a', encoding='utf-8'):
            pass
    except OSError as error:
        return [
            Error(
                f'No se puede escribir el log de eventos en {ruta}: {error.strerror or error}.',
                hint=(
                    'Revisa que la carpeta exista y que el usuario de la aplicación pueda '
                    'escribir en ella (EVENTOS_LOG_PATH). Sin ese archivo se pierden todos los '
                    'eventos que lee la ingesta por streaming.'
                ),
                id='eventos.E001',
            )
        ]
    return []