from rest_framework.routers import DefaultRouter

from .views import (
    ProductCategoryViewSet,
    ProductViewSet,
    InventoryViewSet,
    StockItemViewSet,
    InventoryMovementViewSet
)

router = DefaultRouter()
router.register('product-categories', ProductCategoryViewSet, basename='product-categories')
router.register('products', ProductViewSet, basename='products')
router.register('inventories', InventoryViewSet, basename='inventories')
router.register('stock-items', StockItemViewSet, basename='stock-items')
router.register('inventory-movements', InventoryMovementViewSet, basename='inventory-movements')

urlpatterns = router.urls

