from rest_framework import serializers
from .models import (
    ProductCategory,
    Product,
    Inventory,
    StockItem,
    InventoryMovement
)


class ProductCategorySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = ProductCategory
        fields = (
            'id',
            'name',
            'company',
            'company_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'company_name')


class ProductSerializer(serializers.ModelSerializer):
    product_category_name = serializers.CharField(source='product_category.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'product_category',
            'product_category_name',
            'min_stock_level',
            'default_cost',
            'company',
            'company_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'product_category_name', 'company_name')


class InventorySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Inventory
        fields = (
            'id',
            'name',
            'company',
            'company_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'company_name')


class StockItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    inventory_name = serializers.CharField(source='inventory.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = StockItem
        fields = (
            'id',
            'company',
            'company_name',
            'product',
            'product_name',
            'inventory',
            'inventory_name',
            'quantity_on_hand',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'product_name', 'inventory_name', 'company_name')


class InventoryMovementSerializer(serializers.ModelSerializer):
    stock_item_product_name = serializers.CharField(source='stock_item.product.name', read_only=True)
    stock_item_inventory_name = serializers.CharField(source='stock_item.inventory.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = InventoryMovement
        fields = (
            'id',
            'stock_item',
            'stock_item_product_name',
            'stock_item_inventory_name',
            'quantity_changed',
            'type',
            'type_display',
            'company',
            'company_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'created_at',
            'updated_at',
            'stock_item_product_name',
            'stock_item_inventory_name',
            'company_name',
            'type_display',
        )

