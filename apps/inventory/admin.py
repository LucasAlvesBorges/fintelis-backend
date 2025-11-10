from django.contrib import admin
from .models import (
    ProductCategory,
    Product,
    Inventory,
    StockItem,
    InventoryMovement
)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'created_at')
    list_filter = ('company', 'created_at')
    search_fields = ('name', 'company__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_category', 'company', 'min_stock_level', 'default_cost', 'created_at')
    list_filter = ('company', 'product_category', 'created_at')
    search_fields = ('name', 'company__name', 'product_category__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'created_at')
    list_filter = ('company', 'created_at')
    search_fields = ('name', 'company__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'inventory', 'company', 'quantity_on_hand', 'created_at')
    list_filter = ('company', 'inventory', 'created_at')
    search_fields = ('product__name', 'inventory__name', 'company__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ('stock_item', 'type', 'quantity_changed', 'company', 'created_at')
    list_filter = ('type', 'company', 'created_at')
    search_fields = ('stock_item__product__name', 'stock_item__inventory__name', 'company__name')
    readonly_fields = ('created_at', 'updated_at')
