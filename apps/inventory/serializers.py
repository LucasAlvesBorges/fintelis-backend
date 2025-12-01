from rest_framework import serializers
from .models import ProductCategory, Product, Inventory, StockItem, InventoryMovement


class ProductCategorySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = ProductCategory
        fields = (
            "id",
            "name",
            "company",
            "company_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "company_name", "company")


class ProductSerializer(serializers.ModelSerializer):
    product_category_name = serializers.CharField(
        source="product_category.name", read_only=True
    )
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "product_category",
            "product_category_name",
            "min_stock_level",
            "default_cost",
            "company",
            "company_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "product_category_name",
            "company_name",
            "company",
        )


class InventorySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Inventory
        fields = (
            "id",
            "name",
            "company",
            "company_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "company_name", "company")


class StockItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    product_category_name = serializers.CharField(
        source="product.product_category.name", read_only=True
    )
    default_cost = serializers.DecimalField(
        source="product.default_cost", max_digits=15, decimal_places=2, read_only=True
    )
    inventory_name = serializers.CharField(source="inventory.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = StockItem
        fields = (
            "id",
            "company",
            "company_name",
            "product",
            "product_id",
            "product_name",
            "product_category_name",
            "min_stock_level",
            "default_cost",
            "inventory",
            "inventory_name",
            "quantity_on_hand",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "product_id",
            "product_name",
            "product_category_name",
            "default_cost",
            "inventory_name",
            "company_name",
            "company",
        )

    def validate(self, attrs):
        company = self.context.get("company")
        if company:
            product = attrs.get("product")
            inventory = attrs.get("inventory")
            # Check if we are creating (no instance) or updating (instance present)
            # If updating, exclude self
            qs = StockItem.objects.filter(
                company=company, product=product, inventory=inventory
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "Este produto já está cadastrado neste estoque."
                        ]
                    }
                )
        return attrs


class InventoryMovementSerializer(serializers.ModelSerializer):
    stock_item_product_name = serializers.CharField(
        source="stock_item.product.name", read_only=True
    )
    stock_item_inventory_name = serializers.CharField(
        source="stock_item.inventory.name", read_only=True
    )
    stock_item_inventory_id = serializers.UUIDField(
        source="stock_item.inventory.id", read_only=True
    )
    company_name = serializers.CharField(source="company.name", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = (
            "id",
            "stock_item",
            "stock_item_product_name",
            "stock_item_inventory_name",
            "stock_item_inventory_id",
            "quantity_changed",
            "type",
            "type_display",
            "company",
            "company_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "stock_item_product_name",
            "stock_item_inventory_name",
            "company_name",
            "type_display",
            "company",
        )
