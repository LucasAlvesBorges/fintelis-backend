from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
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

    def get_queryset(self):
        queryset = super().get_queryset()
        inventory_id = self.request.query_params.get("inventory")
        if inventory_id:
            queryset = queryset.filter(stock_item__inventory=inventory_id)

        stock_item_id = self.request.query_params.get("stock_item")
        if stock_item_id:
            queryset = queryset.filter(stock_item_id=stock_item_id)

        return queryset

    def perform_create(self, serializer):
        company = self.get_active_company()

        # Atualiza a quantidade do item de estoque
        stock_item = serializer.validated_data["stock_item"]
        quantity_changed = serializer.validated_data["quantity_changed"]
        stock_item.quantity_on_hand += quantity_changed
        stock_item.save()

        serializer.save(company=company, user=self.request.user)

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

    @action(detail=False, methods=["post"], url_path="transfer")
    def transfer(self, request):
        """
        Endpoint para criar transferências entre inventários.
        Espera: stock_item (ID), destination_inventory (ID), quantity (int)
        """
        company = self.get_active_company()

        stock_item_id = request.data.get("stock_item")
        destination_inventory_id = request.data.get("destination_inventory")
        quantity = request.data.get("quantity")

        # Validações
        if not all([stock_item_id, destination_inventory_id, quantity]):
            return Response(
                {
                    "error": "Campos obrigatórios: stock_item, destination_inventory, quantity"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(quantity)
            if quantity <= 0:
                return Response(
                    {"error": "A quantidade deve ser maior que zero"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "Quantidade inválida"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Busca o stock_item
        try:
            stock_item = StockItem.objects.get(id=stock_item_id, company=company)
        except StockItem.DoesNotExist:
            return Response(
                {"error": "Item de estoque não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Busca o inventário de destino
        try:
            destination_inventory = Inventory.objects.get(
                id=destination_inventory_id, company=company
            )
        except Inventory.DoesNotExist:
            return Response(
                {"error": "Inventário de destino não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verifica se não está transferindo para o mesmo inventário
        if stock_item.inventory.id == destination_inventory.id:
            return Response(
                {"error": "Não é possível transferir para o mesmo inventário"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cria a transferência usando o método do modelo
        try:
            movement_out, movement_in = InventoryMovement.create_transfer(
                product=stock_item.product,
                from_inventory=stock_item.inventory,
                to_inventory=destination_inventory,
                quantity=quantity,
                company=company,
            )

            # Serializa os movimentos para retornar
            serializer = self.get_serializer([movement_out, movement_in], many=True)

            return Response(
                {
                    "message": "Transferência realizada com sucesso",
                    "movements": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Erro ao processar transferência: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
