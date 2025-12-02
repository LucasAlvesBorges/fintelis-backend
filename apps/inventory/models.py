import uuid

from django.db import models
from django.conf import settings
from apps.companies.models import Company, TimeStampedModel


class ProductCategory(TimeStampedModel):
    """Categoria de Produto"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="product_categories"
    )

    class Meta:
        db_table = "product_category"
        unique_together = ("company", "name")
        ordering = ["company", "name"]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Product(TimeStampedModel):
    """O Catálogo Mestre de Produtos"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    product_category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    min_stock_level = models.BigIntegerField(default=0)
    default_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="products"
    )

    class Meta:
        db_table = "products"
        unique_together = ("company", "name")
        ordering = ["company", "name"]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Inventory(TimeStampedModel):
    """Estoque (Local)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="inventories"
    )

    class Meta:
        db_table = "inventory"
        ordering = ["company", "name"]
        verbose_name_plural = "Inventories"

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class StockItem(TimeStampedModel):
    """Pivô: Produto + Local + Quantidade"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="stock_items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stock_items"
    )
    inventory = models.ForeignKey(
        Inventory, on_delete=models.CASCADE, related_name="stock_items"
    )
    quantity_on_hand = models.BigIntegerField(default=0)
    min_stock_level = models.BigIntegerField(
        default=0,
        help_text="Estoque mínimo específico para este produto neste inventário",
    )

    class Meta:
        db_table = "stock_item"
        unique_together = ("company", "product", "inventory")
        ordering = ["company", "product", "inventory"]

    def __str__(self):
        return f"{self.product.name} - {self.inventory.name} ({self.quantity_on_hand})"


class InventoryMovement(TimeStampedModel):
    """O Histórico (Kardex)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class MovementType(models.TextChoices):
        IN_PURCHASE = "in_purchase", "Entrada - Compra"
        IN_ADJUSTMENT = "in_adjustment", "Entrada - Ajuste"
        IN_TRANSFER = "in_transfer", "Entrada - Transferência"
        OUT_SALE = "out_sale", "Saída - Venda"
        OUT_ADJUSTMENT = "out_adjustment", "Saída - Ajuste"
        OUT_TRANSFER = "out_transfer", "Saída - Transferência"
        OUT_LOSS = "out_loss", "Saída - Perda"

    stock_item = models.ForeignKey(
        StockItem, on_delete=models.CASCADE, related_name="movements"
    )
    quantity_changed = models.BigIntegerField()
    type = models.CharField(max_length=255, choices=MovementType.choices)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="inventory_movements"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
    )

    # Campos para transferências entre inventários
    related_inventory = models.ForeignKey(
        Inventory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="related_movements",
        help_text="Inventário de destino (para OUT_TRANSFER) ou origem (para IN_TRANSFER)",
    )
    transfer_reference = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID que vincula os dois movimentos (saída e entrada) da mesma transferência",
    )

    class Meta:
        db_table = "inventory_movements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.stock_item.product.name} - {self.get_type_display()} ({self.quantity_changed:+d})"

    @classmethod
    def create_transfer(cls, product, from_inventory, to_inventory, quantity, company):
        """
        Cria uma transferência completa entre dois inventários.

        Args:
            product: O produto a ser transferido
            from_inventory: Inventário de origem
            to_inventory: Inventário de destino
            quantity: Quantidade a transferir (valor positivo)
            company: Empresa

        Returns:
            tuple: (movimento_saida, movimento_entrada)

        Raises:
            ValueError: Se a quantidade for inválida ou se não houver estoque suficiente
        """
        from django.db import transaction

        if quantity <= 0:
            raise ValueError("A quantidade deve ser maior que zero")

        # Busca ou cria o StockItem de origem
        stock_item_from, _ = StockItem.objects.get_or_create(
            company=company,
            product=product,
            inventory=from_inventory,
            defaults={"quantity_on_hand": 0},
        )

        # Verifica se há estoque suficiente
        if stock_item_from.quantity_on_hand < quantity:
            raise ValueError(
                f"Estoque insuficiente. Disponível: {stock_item_from.quantity_on_hand}, "
                f"Solicitado: {quantity}"
            )

        # Busca ou cria o StockItem de destino
        stock_item_to, _ = StockItem.objects.get_or_create(
            company=company,
            product=product,
            inventory=to_inventory,
            defaults={"quantity_on_hand": 0},
        )

        # Gera um UUID único para vincular os dois movimentos
        transfer_ref = uuid.uuid4()

        with transaction.atomic():
            # Cria o movimento de saída
            movement_out = cls.objects.create(
                stock_item=stock_item_from,
                quantity_changed=-quantity,
                type=cls.MovementType.OUT_TRANSFER,
                company=company,
                related_inventory=to_inventory,
                transfer_reference=transfer_ref,
            )

            # Atualiza o estoque de origem
            stock_item_from.quantity_on_hand -= quantity
            stock_item_from.save()

            # Cria o movimento de entrada
            movement_in = cls.objects.create(
                stock_item=stock_item_to,
                quantity_changed=quantity,
                type=cls.MovementType.IN_TRANSFER,
                company=company,
                related_inventory=from_inventory,
                transfer_reference=transfer_ref,
            )

            # Atualiza o estoque de destino
            stock_item_to.quantity_on_hand += quantity
            stock_item_to.save()

        return movement_out, movement_in
