from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.UUIDField"
    name = "apps.inventory"

    def ready(self):
        import apps.inventory.signals
