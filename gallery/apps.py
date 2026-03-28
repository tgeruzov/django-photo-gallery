from django.apps import AppConfig


class GalleryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gallery"

    def ready(self):
        # Регистрируем signal handlers при старте приложения.
        from . import signals  # noqa: F401
