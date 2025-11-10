import uuid

from django.db import models
from apps.companies.models import Company, TimeStampedModel


class ProductCategory(TimeStampedModel):
    """Categoria de Produto"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='product_categories'
    )

    class Meta:
        db_table = 'product_category'
        unique_together = ('company', 'name')
        ordering = ['company', 'name']

    def __str__(self):
        return f'{self.name} ({self.company.name})'


class Product(TimeStampedModel):
    """O Catálogo Mestre de Produtos"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    product_category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    min_stock_level = models.BigIntegerField(default=0)
    default_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='products'
    )

    class Meta:
        db_table = 'products'
        unique_together = ('company', 'name')
        ordering = ['company', 'name']

    def __str__(self):
        return f'{self.name} ({self.company.name})'


class Inventory(TimeStampedModel):
    """Estoque (Local)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='inventories'
    )

    class Meta:
        db_table = 'inventory'
        ordering = ['company', 'name']
        verbose_name_plural = 'Inventories'

    def __str__(self):
        return f'{self.name} ({self.company.name})'


class StockItem(TimeStampedModel):
    """Pivô: Produto + Local + Quantidade"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    quantity_on_hand = models.BigIntegerField(default=0)

    class Meta:
        db_table = 'stock_item'
        unique_together = ('company', 'product', 'inventory')
        ordering = ['company', 'product', 'inventory']

    def __str__(self):
        return f'{self.product.name} - {self.inventory.name} ({self.quantity_on_hand})'


class InventoryMovement(TimeStampedModel):
    """O Histórico (Kardex)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class MovementType(models.TextChoices):
        IN_PURCHASE = 'in_purchase', 'Entrada - Compra'
        IN_ADJUSTMENT = 'in_adjustment', 'Entrada - Ajuste'
        IN_TRANSFER = 'in_transfer', 'Entrada - Transferência'
        OUT_SALE = 'out_sale', 'Saída - Venda'
        OUT_ADJUSTMENT = 'out_adjustment', 'Saída - Ajuste'
        OUT_TRANSFER = 'out_transfer', 'Saída - Transferência'
        OUT_LOSS = 'out_loss', 'Saída - Perda'

    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    quantity_changed = models.BigIntegerField()
    type = models.CharField(max_length=255, choices=MovementType.choices)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='inventory_movements'
    )

    class Meta:
        db_table = 'inventory_movements'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.stock_item.product.name} - {self.get_type_display()} ({self.quantity_changed:+d})'
