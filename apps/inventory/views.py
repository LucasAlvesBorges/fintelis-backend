from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from apps.companies.models import Membership
from .models import (
    ProductCategory,
    Product,
    Inventory,
    StockItem,
    InventoryMovement
)
from .serializers import (
    ProductCategorySerializer,
    ProductSerializer,
    InventorySerializer,
    StockItemSerializer,
    InventoryMovementSerializer
)


class ProductCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ProductCategory.objects.none()
        # Filtra por empresas que o usuário tem acesso
        return ProductCategory.objects.filter(
            company__memberships__user=user
        ).select_related('company').distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise PermissionDenied('Authentication required.')
        company = serializer.validated_data['company']
        self._ensure_company_access(company)
        serializer.save()

    def perform_update(self, serializer):
        company = serializer.instance.company
        self._ensure_company_access(company)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_company_access(instance.company)
        instance.delete()

    def _ensure_company_access(self, company):
        membership = Membership.objects.filter(
            company=company,
            user=self.request.user
        ).first()
        if membership is None:
            raise PermissionDenied('You do not have access to this company.')


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Product.objects.none()
        # Filtra por empresas que o usuário tem acesso
        return Product.objects.filter(
            company__memberships__user=user
        ).select_related('company', 'product_category').distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise PermissionDenied('Authentication required.')
        company = serializer.validated_data['company']
        self._ensure_company_access(company)
        serializer.save()

    def perform_update(self, serializer):
        company = serializer.instance.company
        self._ensure_company_access(company)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_company_access(instance.company)
        instance.delete()

    def _ensure_company_access(self, company):
        membership = Membership.objects.filter(
            company=company,
            user=self.request.user
        ).first()
        if membership is None:
            raise PermissionDenied('You do not have access to this company.')


class InventoryViewSet(viewsets.ModelViewSet):
    serializer_class = InventorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Inventory.objects.none()
        # Filtra por empresas que o usuário tem acesso
        return Inventory.objects.filter(
            company__memberships__user=user
        ).select_related('company').distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise PermissionDenied('Authentication required.')
        company = serializer.validated_data['company']
        self._ensure_company_access(company)
        serializer.save()

    def perform_update(self, serializer):
        company = serializer.instance.company
        self._ensure_company_access(company)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_company_access(instance.company)
        instance.delete()

    def _ensure_company_access(self, company):
        membership = Membership.objects.filter(
            company=company,
            user=self.request.user
        ).first()
        if membership is None:
            raise PermissionDenied('You do not have access to this company.')


class StockItemViewSet(viewsets.ModelViewSet):
    serializer_class = StockItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return StockItem.objects.none()
        # Filtra por empresas que o usuário tem acesso
        return StockItem.objects.filter(
            company__memberships__user=user
        ).select_related('company', 'product', 'inventory').distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise PermissionDenied('Authentication required.')
        company = serializer.validated_data['company']
        self._ensure_company_access(company)
        serializer.save()

    def perform_update(self, serializer):
        company = serializer.instance.company
        self._ensure_company_access(company)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_company_access(instance.company)
        instance.delete()

    def _ensure_company_access(self, company):
        membership = Membership.objects.filter(
            company=company,
            user=self.request.user
        ).first()
        if membership is None:
            raise PermissionDenied('You do not have access to this company.')


class InventoryMovementViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryMovementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return InventoryMovement.objects.none()
        # Filtra por empresas que o usuário tem acesso
        return InventoryMovement.objects.filter(
            company__memberships__user=user
        ).select_related('company', 'stock_item', 'stock_item__product', 'stock_item__inventory').distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise PermissionDenied('Authentication required.')
        company = serializer.validated_data['company']
        self._ensure_company_access(company)
        
        # Atualiza a quantidade do item de estoque
        stock_item = serializer.validated_data['stock_item']
        quantity_changed = serializer.validated_data['quantity_changed']
        stock_item.quantity_on_hand += quantity_changed
        stock_item.save()
        
        serializer.save()

    def perform_update(self, serializer):
        company = serializer.instance.company
        self._ensure_company_access(company)
        
        # Reverte a movimentação antiga e aplica a nova
        old_movement = serializer.instance
        old_quantity = old_movement.quantity_changed
        old_stock_item = old_movement.stock_item
        
        # Reverte quantidade antiga
        old_stock_item.quantity_on_hand -= old_quantity
        old_stock_item.save()
        
        # Aplica nova quantidade
        new_quantity = serializer.validated_data.get('quantity_changed', old_quantity)
        new_stock_item = serializer.validated_data.get('stock_item', old_stock_item)
        new_stock_item.quantity_on_hand += new_quantity
        new_stock_item.save()
        
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_company_access(instance.company)
        
        # Reverte a movimentação ao deletar
        stock_item = instance.stock_item
        stock_item.quantity_on_hand -= instance.quantity_changed
        stock_item.save()
        
        instance.delete()

    def _ensure_company_access(self, company):
        membership = Membership.objects.filter(
            company=company,
            user=self.request.user
        ).first()
        if membership is None:
            raise PermissionDenied('You do not have access to this company.')
