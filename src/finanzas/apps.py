from django.apps import AppConfig


class FinanzasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "finanzas"
    verbose_name = "Finanzas"

    def ready(self):
        # Register signal handlers for attendance-payment integration.
        from . import signals  # noqa: F401
