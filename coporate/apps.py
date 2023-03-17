from django.apps import AppConfig


class CoporateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'coporate'

    def ready(self):
        from . import signals

