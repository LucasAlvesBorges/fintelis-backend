from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StockItem
from apps.notifications.models import Notification


@receiver(post_save, sender=StockItem)
def check_stock_levels(sender, instance, created, **kwargs):
    """
    Verifica se o nível de estoque está abaixo do mínimo e cria uma notificação.
    """
    # Use StockItem.min_stock_level as this is the specific threshold for this inventory location
    min_level = instance.min_stock_level

    # If min_level is 0, maybe we shouldn't alert? Or maybe we should if stock is < 0?
    # Assuming min_level 0 means "alert when 0".

    if instance.quantity_on_hand <= min_level:
        # Check if there is already an unread notification for this item
        has_unread = Notification.objects.filter(
            link_to_stock_item=instance, is_read=False
        ).exists()

        if not has_unread:
            Notification.objects.create(
                company=instance.company,
                title="Alerta de Estoque Baixo",
                message=f"O produto {instance.product.name} (Estoque: {instance.inventory.name}) atingiu o nível mínimo ({min_level}). Quantidade atual: {instance.quantity_on_hand}.",
                link_to_stock_item=instance,
                is_read=False,
            )
