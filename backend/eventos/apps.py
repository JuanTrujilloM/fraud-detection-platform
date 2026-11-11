from django.apps import AppConfig


class EventosConfig(AppConfig):
    name = 'eventos'

    def ready(self):
        from eventos import checks  # noqa: F401 - registra el chequeo del log de eventos
