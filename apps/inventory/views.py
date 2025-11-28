from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.companies.models import Membership
from apps.financials.mixins import ActiveCompanyMixin
from apps.financials.permissions import IsCompanyMember
from .models import ProductCategory, Product, Inventory, StockItem, InventoryMovement
from .serializers import (
    ProductCategorySerializer,
    ProductSerializer,
    InventorySerializer,
    StockItemSerializer,
    InventoryMovementSerializer,
)


class CompanyScopedViewSet(ActiveCompanyMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    company_field = "company"

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self.get_active_company()
        return queryset.filter(**{self.company_field: company})

    def perform_create(self, serializer):
        serializer.save(**{self.company_field: self.get_active_company()})

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context["company"] = self.get_active_company()
        except (ValidationError, PermissionDenied):
            pass
        return context


class ProductCategoryViewSet(CompanyScopedViewSet):
    queryset = ProductCategory.objects.all().select_related("company")
    serializer_class = ProductCategorySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        inventory_id = self.request.query_params.get("inventory_id")
        if inventory_id:
            queryset = queryset.filter(
                products__stock_items__inventory_id=inventory_id
            ).distinct()
        return queryset


class ProductViewSet(CompanyScopedViewSet):
    queryset = Product.objects.all().select_related("company", "product_category")
    serializer_class = ProductSerializer


class InventoryViewSet(CompanyScopedViewSet):
    queryset = Inventory.objects.all().select_related("company")
    serializer_class = InventorySerializer


class StockItemViewSet(CompanyScopedViewSet):
    queryset = StockItem.objects.all().select_related("company", "product", "inventory")
    serializer_class = StockItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        inventory_id = self.request.query_params.get("inventory")
        if inventory_id:
            queryset = queryset.filter(inventory_id=inventory_id)
        return queryset


class InventoryMovementViewSet(CompanyScopedViewSet):
    queryset = InventoryMovement.objects.all().select_related(
        "company", "stock_item", "stock_item__product", "stock_item__inventory"
    )
    serializer_class = InventoryMovementSerializer

    def perform_create(self, serializer):
        company = self.get_active_company()

        # Atualiza a quantidade do item de estoque
        stock_item = serializer.validated_data["stock_item"]
        quantity_changed = serializer.validated_data["quantity_changed"]
        stock_item.quantity_on_hand += quantity_changed
        stock_item.save()

        serializer.save(company=company)

    def perform_update(self, serializer):
        # Ensure company access is checked via get_active_company in parent/mixin,
        # but here we need to handle the stock logic.
        # The mixin doesn't override perform_update, so we are good to go,
        # but we should ensure the instance belongs to the active company.
        # The get_queryset filtering handles the read access.

        # Reverte a movimentação antiga e aplica a nova
        old_movement = serializer.instance
        old_quantity = old_movement.quantity_changed
        old_stock_item = old_movement.stock_item

        # Reverte quantidade antiga
        old_stock_item.quantity_on_hand -= old_quantity
        old_stock_item.save()

        # Aplica nova quantidade
        new_quantity = serializer.validated_data.get("quantity_changed", old_quantity)
        new_stock_item = serializer.validated_data.get("stock_item", old_stock_item)
        new_stock_item.quantity_on_hand += new_quantity
        new_stock_item.save()

        serializer.save()

    def perform_destroy(self, instance):
        # Reverte a movimentação ao deletar
        stock_item = instance.stock_item
        stock_item.quantity_on_hand -= instance.quantity_changed
        stock_item.save()

        instance.delete()
