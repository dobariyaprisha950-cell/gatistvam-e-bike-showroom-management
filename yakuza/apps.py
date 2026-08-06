from django.apps import AppConfig


class YakuzaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'yakuza'
    verbose_name = 'GATISTVAM E-Bike System Management'

    def ready(self):
        import yakuza.signals  # noqa