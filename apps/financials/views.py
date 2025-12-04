import hashlib
import json
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction as db_transaction
from django.db.models import Q, Sum, Case, When, IntegerField
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone

from apps.companies.models import CostCenter
from .mixins import ActiveCompanyMixin
from .models import (
    Bank,
    BankAccount,
    Bill,
    CashRegister,
    Category,
    Income,
    PaymentMethod,
    RecurringBill,
    RecurringBillPayment,
    RecurringIncome,
    RecurringIncomeReceipt,
    Transaction,
)
from .serializers import (
    BankSerializer,
    BankAccountSerializer,
    BankAccountTransferSerializer,
    BillPaymentSerializer,
    BillSerializer,
    CashRegisterSerializer,
    CategorySerializer,
    FinancialDataTransactionSerializer,
    IncomePaymentSerializer,
    IncomeSerializer,
    PaymentMethodSerializer,
    RecurringBillSerializer,
    RecurringBillPaymentSerializer,
    RecurringIncomeSerializer,
    RecurringIncomeReceiptSerializer,
    TransactionSerializer,
    TransferSerializer,
    TransactionRefundSerializer,
    BankAccountWithdrawSerializer,
)
from .permissions import IsCompanyMember


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


class BankViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Bank.objects.filter(is_active=True).order_by("code")
    serializer_class = BankSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentMethodViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para listar métodos de pagamento."""
    queryset = PaymentMethod.objects.all().order_by("name")
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]


class BankAccountDetailsPagination(PageNumberPagination):
    """Paginação para detalhes da conta bancária: 5 itens por página."""
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 5


class BankAccountViewSet(CompanyScopedViewSet):
    queryset = BankAccount.objects.all().select_related("company", "bank")
    serializer_class = BankAccountSerializer

    @action(detail=False, methods=["get"], url_path="total-balance")
    def total_balance(self, request):
        """
        Retorna o total do saldo de todas as contas bancárias,
        excluindo contas do tipo 'banco_de_creditos'.
        """
        company = self.get_active_company()
        accounts = BankAccount.objects.filter(
            company=company
        ).exclude(
            type=BankAccount.Types.BANCO_CREDITOS
        )
        
        total = accounts.aggregate(
            total=Sum("current_balance")
        )["total"] or Decimal("0")
        
        return Response({
            "total_balance": total
        })

    @action(detail=True, methods=["get"], url_path="details")
    def details(self, request, pk=None):
        account = self.get_object()
        
        # Paginação
        paginator = BankAccountDetailsPagination()
        
        # Query parameters para paginação
        transactions_page = int(request.query_params.get("transactions_page", 1))
        incomes_page = int(request.query_params.get("incomes_page", 1))
        bills_page = int(request.query_params.get("bills_page", 1))
        page_size = paginator.page_size
        
        # Filtro por tipo de transação
        transactions_type = request.query_params.get("transactions_type")
        if transactions_type:
            if transactions_type not in [Transaction.Types.RECEITA, Transaction.Types.DESPESA]:
                raise ValidationError(
                    {"transactions_type": "Deve ser 'receita' ou 'despesa'."}
                )
        
        # Histórico de transações (com paginação e filtro)
        # Ordenar pela última transação que ocorreu: por created_at (mais recente primeiro), depois por transaction_date
        transactions_qs = (
            account.transactions.all()
            .select_related("category", "contact", "payment_method", "cost_center")
            .order_by("-created_at", "-transaction_date", "-id")
        )
        
        # Aplicar filtro por tipo se fornecido
        if transactions_type:
            transactions_qs = transactions_qs.filter(type=transactions_type)
        
        total_transactions = transactions_qs.count()
        transactions_start = (transactions_page - 1) * page_size
        transactions_end = transactions_start + page_size
        transactions = transactions_qs[transactions_start:transactions_end]
        transactions_total_pages = (total_transactions + page_size - 1) // page_size if total_transactions > 0 else 1
        
        # Contas a receber pagas nesta conta (com paginação)
        incomes_qs = (
            Income.objects.filter(payment_transaction__bank_account=account)
            .select_related("category", "contact", "cost_center")
            .order_by("-due_date", "-id")
        )
        total_incomes = incomes_qs.count()
        incomes_start = (incomes_page - 1) * page_size
        incomes_end = incomes_start + page_size
        incomes = incomes_qs[incomes_start:incomes_end]
        incomes_total_pages = (total_incomes + page_size - 1) // page_size if total_incomes > 0 else 1
        
        # Contas a pagar pagas nesta conta (com paginação)
        bills_qs = (
            Bill.objects.filter(payment_transaction__bank_account=account)
            .select_related("category", "contact", "cost_center")
            .order_by("-due_date", "-id")
        )
        total_bills = bills_qs.count()
        bills_start = (bills_page - 1) * page_size
        bills_end = bills_start + page_size
        bills = bills_qs[bills_start:bills_end]
        bills_total_pages = (total_bills + page_size - 1) // page_size if total_bills > 0 else 1
        
        # Estatísticas e resumo
        transactions_stats_qs = account.transactions.all()
        
        # Total de receitas
        total_receitas = transactions_stats_qs.filter(
            type=Transaction.Types.RECEITA
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Total de despesas
        total_despesas = transactions_stats_qs.filter(
            type__in=[Transaction.Types.DESPESA, Transaction.Types.TRANSFERENCIA_EXTERNA]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Total de transferências recebidas
        total_transferencias_recebidas = transactions_stats_qs.filter(
            type=Transaction.Types.TRANSFERENCIA_INTERNA
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Total de transferências enviadas
        total_transferencias_enviadas = transactions_stats_qs.filter(
            type=Transaction.Types.TRANSFERENCIA_EXTERNA
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        # Contas a receber pendentes (não pagas)
        incomes_pendentes = Income.objects.filter(
            company=account.company,
            status=Income.Status.PENDENTE
        ).exclude(payment_transaction__isnull=False).count()
        
        # Contas a pagar pendentes (não pagas)
        bills_pendentes = Bill.objects.filter(
            company=account.company,
            status=Bill.Status.A_VENCER
        ).exclude(payment_transaction__isnull=False).count()
        
        return Response(
            {
                "account": BankAccountSerializer(account, context=self.get_serializer_context()).data,
                "summary": {
                    "current_balance": account.current_balance,
                    "initial_balance": account.initial_balance,
                    "total_receitas": total_receitas,
                    "total_despesas": total_despesas,
                    "total_transferencias_recebidas": total_transferencias_recebidas,
                    "total_transferencias_enviadas": total_transferencias_enviadas,
                    "incomes_pendentes": incomes_pendentes,
                    "bills_pendentes": bills_pendentes,
                },
                "transactions": {
                    "items": TransactionSerializer(transactions, many=True, context=self.get_serializer_context()).data,
                    "pagination": {
                        "page": transactions_page,
                        "page_size": page_size,
                        "total_pages": transactions_total_pages,
                        "total_items": total_transactions,
                        "has_next": transactions_page < transactions_total_pages,
                        "has_previous": transactions_page > 1,
                    },
                },
                "incomes": {
                    "items": IncomeSerializer(incomes, many=True, context=self.get_serializer_context()).data,
                    "pagination": {
                        "page": incomes_page,
                        "page_size": page_size,
                        "total_pages": incomes_total_pages,
                        "total_items": total_incomes,
                        "has_next": incomes_page < incomes_total_pages,
                        "has_previous": incomes_page > 1,
                    },
                },
                "bills": {
                    "items": BillSerializer(bills, many=True, context=self.get_serializer_context()).data,
                    "pagination": {
                        "page": bills_page,
                        "page_size": page_size,
                        "total_pages": bills_total_pages,
                        "total_items": total_bills,
                        "has_next": bills_page < bills_total_pages,
                        "has_previous": bills_page > 1,
                    },
                },
            }
        )

    @action(detail=True, methods=["post"], url_path="withdraw")
    def withdraw(self, request, pk=None):
        account = self.get_object()
        serializer = BankAccountWithdrawSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        description = data.get("description") or "Retirada"
        tx_date = data.get("transaction_date") or timezone.now().date()

        tx = Transaction.objects.create(
            company=account.company,
            bank_account=account,
            category=data.get("category"),
            description=description,
            amount=data["amount"],
            type=Transaction.Types.DESPESA,
            transaction_date=tx_date,
        )
        return Response(
            TransactionSerializer(tx, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="transfer")
    def transfer(self, request, pk=None):
        """
        Transferência de saldo desta conta para outra conta bancária.
        Facilita o uso da transferência especificando apenas a conta de destino.
        Suporta dedução percentual do valor transferido.
        """
        from_account = self.get_object()
        company = self.get_active_company()
        
        serializer = BankAccountTransferSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        original_amount = data["amount"]
        deduction_percentage = data.get("deduction_percentage") or Decimal("0")
        deduction_amount = ((original_amount * deduction_percentage) / Decimal("100")).quantize(Decimal("0.01"))
        final_amount = (original_amount - deduction_amount).quantize(Decimal("0.01"))

        description = data.get("description") or "Transferência entre contas"
        
        # Descrição com informação de dedução se houver
        if deduction_percentage > 0:
            outgoing_description = f"Saída: {description} (Dedução: {deduction_percentage}% = {deduction_amount:.2f})"
            incoming_description = f"Entrada: {description} (Valor líquido após dedução de {deduction_percentage}%)"
        else:
            outgoing_description = f"Saída: {description}"
            incoming_description = f"Entrada: {description}"

        with db_transaction.atomic():
            # Transação de saída: valor original
            outgoing = Transaction.objects.create(
                company=company,
                bank_account=from_account,
                description=outgoing_description,
                amount=original_amount,
                type=Transaction.Types.TRANSFERENCIA_EXTERNA,
                transaction_date=data["transaction_date"],
            )
            # Transação de entrada: valor após dedução
            incoming = Transaction.objects.create(
                company=company,
                bank_account=data["to_bank_account"],
                description=incoming_description,
                amount=final_amount,
                type=Transaction.Types.TRANSFERENCIA_INTERNA,
                transaction_date=data["transaction_date"],
                linked_transaction=outgoing,
            )
            outgoing.linked_transaction = incoming
            outgoing.save(update_fields=["linked_transaction", "updated_at"])

        response_serializer = TransactionSerializer(
            [outgoing, incoming], many=True, context=self.get_serializer_context()
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class CashRegisterViewSet(CompanyScopedViewSet):
    queryset = CashRegister.objects.all().select_related(
        "company", "default_bank_account", "default_bank_account__bank"
    )
    serializer_class = CashRegisterSerializer

    @action(detail=True, methods=["get"], url_path="details")
    def details(self, request, pk=None):
        """
        Retorna detalhes do caixa/PDV incluindo:
        - Informações do caixa
        - Transações associadas (com paginação de 5 itens)
        - Ordenação por última transação (created_at)
        """
        cash_register = self.get_object()
        company = self.get_active_company()
        
        # Verificar se o caixa pertence à empresa ativa
        if cash_register.company_id != company.id:
            raise ValidationError({"detail": "Caixa não pertence à empresa ativa."})
        
        # Paginação
        paginator = BankAccountDetailsPagination()
        transactions_page = int(request.query_params.get("transactions_page", 1))
        page_size = paginator.page_size
        
        # Buscar transações associadas ao caixa
        # Como são sempre receitas, não precisamos filtrar por tipo
        transactions_qs = (
            cash_register.transactions.all()
            .select_related("category", "contact", "payment_method", "cost_center", "bank_account", "bank_account__bank")
            .order_by("-created_at", "-transaction_date", "-id")
        )
        
        # Paginação
        total_transactions = transactions_qs.count()
        transactions_start = (transactions_page - 1) * page_size
        transactions_end = transactions_start + page_size
        transactions = transactions_qs[transactions_start:transactions_end]
        transactions_total_pages = (total_transactions + page_size - 1) // page_size if total_transactions > 0 else 1
        
        # Resumo
        total_receitas = transactions_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_transactions_count = total_transactions
        
        return Response({
            "cash_register": CashRegisterSerializer(cash_register, context=self.get_serializer_context()).data,
            "summary": {
                "total_receitas": total_receitas,
                "total_transactions": total_transactions_count,
            },
            "transactions": {
                "items": TransactionSerializer(transactions, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": transactions_page,
                    "page_size": page_size,
                    "total_pages": transactions_total_pages,
                    "total_items": total_transactions,
                    "has_next": transactions_page < transactions_total_pages,
                    "has_previous": transactions_page > 1,
                },
            },
        })


class CategoryViewSet(CompanyScopedViewSet):
    queryset = Category.objects.all().select_related("company", "parent")
    serializer_class = CategorySerializer

    def _get_all_related_category_ids(self, category):
        """
        Retorna uma lista com o ID da categoria e todos os IDs das subcategorias (recursivamente).
        """
        category_ids = [category.id]
        
        # Buscar todas as subcategorias diretas
        subcategories = Category.objects.filter(parent=category)
        for subcat in subcategories:
            # Recursivamente buscar subcategorias das subcategorias
            category_ids.extend(self._get_all_related_category_ids(subcat))
        
        return category_ids

    @action(detail=True, methods=["get"], url_path="details")
    def details(self, request, pk=None):
        """
        Retorna detalhes da categoria incluindo:
        - Informações da categoria
        - Transações associadas (com paginação de 5 itens)
        - Filtro por tipo de transação (receita/despesa)
        - Ordenação por última transação (created_at)
        """
        category = self.get_object()
        company = self.get_active_company()
        
        # Verificar se a categoria pertence à empresa ativa
        if category.company_id != company.id:
            raise ValidationError({"detail": "Categoria não pertence à empresa ativa."})
        
        # Paginação
        paginator = BankAccountDetailsPagination()
        transactions_page = int(request.query_params.get("transactions_page", 1))
        page_size = paginator.page_size
        
        # Filtro por tipo de transação
        transactions_type = request.query_params.get("transactions_type")
        if transactions_type:
            if transactions_type not in [Transaction.Types.RECEITA, Transaction.Types.DESPESA]:
                raise ValidationError(
                    {"transactions_type": "Deve ser 'receita' ou 'despesa'."}
                )
        
        # Buscar todas as categorias relacionadas (a categoria e todas as subcategorias)
        related_category_ids = self._get_all_related_category_ids(category)
        
        # Buscar transações associadas à categoria e suas subcategorias
        transactions_qs = (
            Transaction.objects.filter(category_id__in=related_category_ids, company=company)
            .select_related("category", "contact", "payment_method", "cost_center", "bank_account", "bank_account__bank")
            .order_by("-created_at", "-transaction_date", "-id")
        )
        
        # Aplicar filtro por tipo se fornecido
        if transactions_type:
            transactions_qs = transactions_qs.filter(type=transactions_type)
        
        # Paginação
        total_transactions = transactions_qs.count()
        transactions_start = (transactions_page - 1) * page_size
        transactions_end = transactions_start + page_size
        transactions = transactions_qs[transactions_start:transactions_end]
        transactions_total_pages = (total_transactions + page_size - 1) // page_size if total_transactions > 0 else 1
        
        # Resumo (sem filtro de tipo para mostrar totais gerais)
        all_transactions_for_summary = Transaction.objects.filter(
            category_id__in=related_category_ids, company=company
        )
        total_receitas = all_transactions_for_summary.filter(
            type=Transaction.Types.RECEITA
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_despesas = all_transactions_for_summary.filter(
            type__in=[Transaction.Types.DESPESA, Transaction.Types.TRANSFERENCIA_EXTERNA, Transaction.Types.ESTORNO]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_transactions_count = all_transactions_for_summary.count()
        
        # Informações sobre subcategorias
        subcategories = Category.objects.filter(parent=category).order_by("code", "name")
        subcategories_data = CategorySerializer(subcategories, many=True, context=self.get_serializer_context()).data
        
        return Response({
            "category": CategorySerializer(category, context=self.get_serializer_context()).data,
            "subcategories": subcategories_data,
            "summary": {
                "total_receitas": total_receitas,
                "total_despesas": total_despesas,
                "total_transactions": total_transactions_count,
                "subcategories_count": len(subcategories_data),
            },
            "transactions": {
                "items": TransactionSerializer(transactions, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": transactions_page,
                    "page_size": page_size,
                    "total_pages": transactions_total_pages,
                    "total_items": total_transactions,
                    "has_next": transactions_page < transactions_total_pages,
                    "has_previous": transactions_page > 1,
                },
            },
        })

    def list(self, request, *args, **kwargs):
        """
        Retorna categorias organizadas hierarquicamente por tipo:
        - Categorias de Despesas -> Categoria Pai -> Filhos
        - Categorias de Receitas -> Categoria Pai -> Filhos
        """
        company = self.get_active_company()
        categories = Category.objects.filter(company=company).select_related("parent").order_by("type", "code")
        
        # Organizar por tipo
        despesas = []
        receitas = []
        
        # Separar categorias pai e filhas
        parent_categories = {}
        all_categories = {}
        
        for category in categories:
            all_categories[str(category.id)] = category
            if category.parent is None:
                # É uma categoria pai
                parent_categories[str(category.id)] = {
                    "id": str(category.id),
                    "company": str(category.company_id),
                    "code": category.code,
                    "parent": None,
                    "name": category.name,
                    "type": category.type,
                    "created_at": category.created_at.isoformat(),
                    "updated_at": category.updated_at.isoformat(),
                    "subcategories": [],
                }
        
        # Adicionar subcategorias às categorias pai
        for category in categories:
            if category.parent:
                parent_id = str(category.parent_id)
                if parent_id in parent_categories:
                    parent_categories[parent_id]["subcategories"].append({
                        "id": str(category.id),
                        "company": str(category.company_id),
                        "code": category.code,
                        "parent": parent_id,
                        "name": category.name,
                        "type": category.type,
                        "created_at": category.created_at.isoformat(),
                        "updated_at": category.updated_at.isoformat(),
                        "subcategories": [],
                    })
        
        # Organizar por tipo
        for cat_data in parent_categories.values():
            if cat_data["type"] == Category.Types.DESPESA:
                despesas.append(cat_data)
            elif cat_data["type"] == Category.Types.RECEITA:
                receitas.append(cat_data)
        
        # Ordenar por código
        despesas.sort(key=lambda x: x["code"] or "")
        receitas.sort(key=lambda x: x["code"] or "")
        
        # Ordenar subcategorias por código
        for cat in despesas + receitas:
            cat["subcategories"].sort(key=lambda x: x["code"] or "")
        
        return Response({
            "despesas": despesas,
            "receitas": receitas,
        })


class TransactionViewSet(CompanyScopedViewSet):
    queryset = Transaction.objects.all().select_related(
        "company",
        "bank_account",
        "bank_account__bank",
        "category",
        "cost_center",
        "cash_register",
        "linked_transaction",
        "contact",
        "payment_method",
    )
    serializer_class = TransactionSerializer


    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        original = self.get_object()
        serializer = TransactionRefundSerializer(
            data=request.data,
            context={
                "company": self.get_active_company(),
                "original_transaction": original,
            },
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with db_transaction.atomic():
            refund = Transaction.objects.create(
                company=original.company,
                bank_account=original.bank_account,
                category=original.category,
                cash_register=original.cash_register,
                contact=original.contact,
                description=f"Estorno: {data['description']}",
                amount=data["amount"],
                type=Transaction.Types.ESTORNO,
                transaction_date=timezone.now().date(),
                related_transaction=original,
            )

        return Response(
            TransactionSerializer(refund, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class BillViewSet(CompanyScopedViewSet):
    queryset = Bill.objects.all().select_related(
        "company",
        "category",
        "payment_transaction",
        "contact",
        "cost_center",
    )
    serializer_class = BillSerializer

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        bill = self.get_object()
        if bill.status == Bill.Status.QUITADA:
            raise ValidationError("This bill is already settled.")

        serializer = BillPaymentSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        description = data.get("description") or f"Pagamento - {bill.description}"

        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                company=bill.company,
                bank_account=data["bank_account"],
                category=bill.category,
                description=description,
                amount=bill.amount,
                type=Transaction.Types.DESPESA,
                transaction_date=data["transaction_date"],
            )
            bill.payment_transaction = transaction
            bill.status = Bill.Status.QUITADA
            bill.save(update_fields=["payment_transaction", "status", "updated_at"])

        return Response(self.get_serializer(bill).data, status=status.HTTP_200_OK)


class IncomeViewSet(CompanyScopedViewSet):
    queryset = Income.objects.all().select_related(
        "company",
        "category",
        "payment_transaction",
        "contact",
        "cost_center",
    )
    serializer_class = IncomeSerializer

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        income = self.get_object()
        if income.status == Income.Status.RECEBIDO:
            raise ValidationError("This income is already settled.")

        serializer = IncomePaymentSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        description = data.get("description") or f"Recebimento - {income.description}"

        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                company=income.company,
                bank_account=data["bank_account"],
                category=income.category,
                description=description,
                amount=income.amount,
                type=Transaction.Types.RECEITA,
                transaction_date=data["transaction_date"],
            )
            income.payment_transaction = transaction
            income.status = Income.Status.RECEBIDO
            income.save(update_fields=["payment_transaction", "status", "updated_at"])

        return Response(self.get_serializer(income).data, status=status.HTTP_200_OK)


class RecurringBillViewSet(CompanyScopedViewSet):
    queryset = RecurringBill.objects.all().select_related(
        "company", "category", "cost_center", "contact"
    )
    serializer_class = RecurringBillSerializer


class RecurringIncomeViewSet(CompanyScopedViewSet):
    queryset = RecurringIncome.objects.all().select_related(
        "company", "category", "cost_center", "contact"
    )
    serializer_class = RecurringIncomeSerializer


class FinancialDataPagination(PageNumberPagination):
    """Paginação padrão para o endpoint unificado de dados financeiros."""
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class FinancialDataView(ActiveCompanyMixin, APIView):
    """
    Endpoint unificado para visualização de dados financeiros.
    
    Combina Income, Bill, RecurringBill, RecurringIncome, 
    RecurringBillPayment e RecurringIncomeReceipt em uma única API.
    
    Query Parameters:
    -----------------
    - type (required): Tipo de dado a buscar. Valores aceitos:
        - incomes: Contas a receber
        - bills: Contas a pagar
        - recurring_bills: Contas recorrentes a pagar
        - recurring_incomes: Contas recorrentes a receber
        - recurring_bill_payments: Pagamentos de contas recorrentes
        - recurring_income_receipts: Recebimentos de contas recorrentes
    
    - uuid (optional): UUID de um item específico para ver detalhes completos.
    
    - page (optional, default=1): Número da página para paginação.
    
    - search (optional): Filtro de busca com formato "campo#valor".
        Exemplos:
        - category#vendas: Filtra por categoria com nome "vendas"
        - cost_center#administracao: Filtra por centro de custo "administracao"
        - status#pendente: Filtra por status "pendente"
        - description#aluguel: Filtra por descrição contendo "aluguel"
        
        Múltiplos filtros podem ser combinados separados por vírgula:
        - category#vendas,cost_center#marketing
    
    - status (optional): Filtro direto por status (pendente, quitada, recebido).
    
    - category_id (optional): Filtro por ID da categoria.
    
    - cost_center_id (optional): Filtro por ID do centro de custo.
    
    - date_from (optional): Data inicial (YYYY-MM-DD) para filtrar por due_date.
    
    - date_to (optional): Data final (YYYY-MM-DD) para filtrar por due_date.
    
    Response:
    ---------
    - Se uuid é fornecido: Retorna detalhes completos do item.
    - Se uuid não é fornecido: Retorna lista paginada com 10 itens por página.
    
    Cache:
    ------
    Resultados são cacheados por 60 segundos no Redis para melhorar performance.
    O cache é invalidado automaticamente quando os parâmetros de busca mudam.
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    
    def get_serializer_context(self):
        """Retorna o contexto para serializers."""
        context = {
            "request": self.request,
        }
        try:
            context["company"] = self.get_active_company()
        except (ValidationError, PermissionDenied):
            pass
        return context
    
    VALID_TYPES = {
        "incomes": {
            "model": Income,
            "serializer": IncomeSerializer,
            "select_related": ["company", "category", "contact", "cost_center", "payment_transaction", "payment_transaction__bank_account"],
            "has_status": True,
            "status_field": "status",
        },
        "bills": {
            "model": Bill,
            "serializer": BillSerializer,
            "select_related": ["company", "category", "contact", "cost_center", "payment_transaction", "payment_transaction__bank_account"],
            "has_status": True,
            "status_field": "status",
        },
        "recurring_bills": {
            "model": RecurringBill,
            "serializer": RecurringBillSerializer,
            "select_related": ["company", "category", "cost_center", "contact"],
            "has_status": False,
        },
        "recurring_incomes": {
            "model": RecurringIncome,
            "serializer": RecurringIncomeSerializer,
            "select_related": ["company", "category", "cost_center", "contact"],
            "has_status": False,
        },
        "recurring_bill_payments": {
            "model": RecurringBillPayment,
            "serializer": RecurringBillPaymentSerializer,
            "select_related": ["company", "recurring_bill", "recurring_bill__category", "recurring_bill__cost_center", "recurring_bill__contact", "transaction", "transaction__bank_account"],
            "has_status": True,
            "status_field": "status",
        },
        "recurring_income_receipts": {
            "model": RecurringIncomeReceipt,
            "serializer": RecurringIncomeReceiptSerializer,
            "select_related": ["company", "recurring_income", "recurring_income__category", "recurring_income__cost_center", "recurring_income__contact", "transaction", "transaction__bank_account"],
            "has_status": True,
            "status_field": "status",
        },
    }
    
    CACHE_TTL = 60  # 60 segundos
    
    def _generate_cache_key(self, company_id: str, data_type: str, params: dict) -> str:
        """Gera uma chave de cache única baseada nos parâmetros."""
        params_str = json.dumps(params, sort_keys=True, default=str)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
        return f"financial_data:{company_id}:{data_type}:{params_hash}"
    
    def _invalidate_cache(self, company_id: str, data_type: str):
        """
        Invalida todo o cache relacionado a um tipo de dado específico para uma empresa.
        Usa versionamento de cache: incrementa a versão, o que automaticamente invalida
        todos os caches antigos porque a versão faz parte da chave.
        
        Também invalida tipos relacionados:
        - bills/incomes: também invalida transactions
        - recurring_bill_payments: também invalida recurring_bills e transactions
        - recurring_income_receipts: também invalida recurring_incomes e transactions
        """
        # Invalidar o tipo específico
        version_key = f"financial_data_version:{company_id}:{data_type}"
        try:
            current_version = cache.get(version_key, 0)
            cache.set(version_key, current_version + 1, timeout=None)  # Sem timeout
        except Exception:
            pass  # Se falhar, não é crítico
        
        # Invalidar tipos relacionados
        related_types = []
        
        if data_type in ["bills", "incomes"]:
            # Bills e incomes criam transactions, então invalidar transactions também
            related_types.append("transactions")
        elif data_type == "recurring_bill_payments":
            # Payments criam transactions e afetam o recurring_bill pai
            related_types.extend(["transactions", "recurring_bills"])
        elif data_type == "recurring_income_receipts":
            # Receipts criam transactions e afetam o recurring_income pai
            related_types.extend(["transactions", "recurring_incomes"])
        
        # Invalidar versões dos tipos relacionados
        for related_type in related_types:
            related_version_key = f"financial_data_version:{company_id}:{related_type}"
            try:
                current_version = cache.get(related_version_key, 0)
                cache.set(related_version_key, current_version + 1, timeout=None)
            except Exception:
                pass
    
    def _parse_search_filters(self, search_param: str) -> dict:
        """
        Parseia o parâmetro de busca no formato 'campo#valor,campo2#valor2'.
        
        Retorna um dicionário com os filtros.
        Suporta tanto '#' quanto '%23' (URL encoded).
        """
        filters = {}
        if not search_param:
            return filters
        
        # Normalizar: substituir %23 por # caso venha codificado
        search_param = search_param.replace("%23", "#")
        
        for part in search_param.split(","):
            part = part.strip()
            if not part:
                continue
            
            # Verificar se tem separador #
            if "#" not in part:
                # Se não tem #, pode ser um valor simples para busca geral
                # Por enquanto, ignoramos valores sem #
                continue
            
            # Dividir pelo primeiro # encontrado
            parts = part.split("#", 1)
            if len(parts) != 2:
                continue
            
            field, value = parts
            field = field.strip().lower()
            value = value.strip()
            
            # Validar que ambos têm valor
            if field and value:
                filters[field] = value
        
        return filters
    
    def _apply_filters(self, queryset, data_type: str, request):
        """Aplica filtros ao queryset baseado nos parâmetros da request."""
        company = self.get_active_company()
        config = self.VALID_TYPES[data_type]
        
        # Filtro por empresa (sempre aplicado)
        queryset = queryset.filter(company=company)
        
        # Filtro por status
        status_param = request.query_params.get("status")
        if status_param and config.get("has_status"):
            queryset = queryset.filter(**{config["status_field"]: status_param})
        
        # Filtro por categoria
        category_id = request.query_params.get("category_id")
        if category_id:
            if data_type in ["recurring_bill_payments"]:
                queryset = queryset.filter(recurring_bill__category_id=category_id)
            elif data_type in ["recurring_income_receipts"]:
                queryset = queryset.filter(recurring_income__category_id=category_id)
            else:
                queryset = queryset.filter(category_id=category_id)
        
        # Filtro por centro de custo
        cost_center_id = request.query_params.get("cost_center_id")
        if cost_center_id:
            if data_type in ["recurring_bill_payments"]:
                queryset = queryset.filter(recurring_bill__cost_center_id=cost_center_id)
            elif data_type in ["recurring_income_receipts"]:
                queryset = queryset.filter(recurring_income__cost_center_id=cost_center_id)
            else:
                queryset = queryset.filter(cost_center_id=cost_center_id)
        
        # Filtro por data
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(due_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(due_date__lte=date_to)
        
        # Filtro de busca avançada (campo#valor)
        search_param = request.query_params.get("search")
        if search_param:
            # Decodificar URL se necessário (caso o # venha como %23)
            from urllib.parse import unquote
            search_param = unquote(search_param)
            
            search_filters = self._parse_search_filters(search_param)
            
            for field, value in search_filters.items():
                if field == "category":
                    if data_type in ["recurring_bill_payments"]:
                        queryset = queryset.filter(recurring_bill__category__name__icontains=value)
                    elif data_type in ["recurring_income_receipts"]:
                        queryset = queryset.filter(recurring_income__category__name__icontains=value)
                    else:
                        queryset = queryset.filter(category__name__icontains=value)
                
                elif field == "cost_center":
                    if data_type in ["recurring_bill_payments"]:
                        queryset = queryset.filter(recurring_bill__cost_center__name__icontains=value)
                    elif data_type in ["recurring_income_receipts"]:
                        queryset = queryset.filter(recurring_income__cost_center__name__icontains=value)
                    else:
                        queryset = queryset.filter(cost_center__name__icontains=value)
                
                elif field == "description":
                    if data_type in ["recurring_bill_payments"]:
                        queryset = queryset.filter(recurring_bill__description__icontains=value)
                    elif data_type in ["recurring_income_receipts"]:
                        queryset = queryset.filter(recurring_income__description__icontains=value)
                    else:
                        queryset = queryset.filter(description__icontains=value)
                
                elif field == "status" and config.get("has_status"):
                    queryset = queryset.filter(**{config["status_field"]: value})
                
                elif field == "contact":
                    if data_type in ["incomes", "bills"]:
                        queryset = queryset.filter(contact__name__icontains=value)
        
        return queryset
    
    def _get_ordering(self, data_type: str, queryset):
        """
        Aplica ordenação apropriada para cada tipo.
        Ordena por: status pendente primeiro, depois por próximo vencimento (crescente).
        """
        config = self.VALID_TYPES[data_type]
        
        if data_type in ["bills"]:
            # Bills: pendente primeiro, depois por due_date crescente
            queryset = queryset.annotate(
                status_order=Case(
                    When(status=Bill.Status.A_VENCER, then=0),
                    When(status=Bill.Status.QUITADA, then=1),
                    default=1,
                    output_field=IntegerField(),
                )
            )
            return queryset.order_by("status_order", "due_date", "id")
        
        elif data_type in ["incomes"]:
            # Incomes: pendente primeiro, depois por due_date crescente
            queryset = queryset.annotate(
                status_order=Case(
                    When(status=Income.Status.PENDENTE, then=0),
                    When(status=Income.Status.RECEBIDO, then=1),
                    default=1,
                    output_field=IntegerField(),
                )
            )
            return queryset.order_by("status_order", "due_date", "id")
        
        elif data_type in ["recurring_bill_payments"]:
            # Payments: pendente primeiro, depois por due_date crescente
            queryset = queryset.annotate(
                status_order=Case(
                    When(status=RecurringBillPayment.Status.PENDENTE, then=0),
                    When(status=RecurringBillPayment.Status.QUITADA, then=1),
                    default=1,
                    output_field=IntegerField(),
                )
            )
            return queryset.order_by("status_order", "due_date", "id")
        
        elif data_type in ["recurring_income_receipts"]:
            # Receipts: pendente primeiro, depois por due_date crescente
            queryset = queryset.annotate(
                status_order=Case(
                    When(status=RecurringIncomeReceipt.Status.PENDENTE, then=0),
                    When(status=RecurringIncomeReceipt.Status.RECEBIDO, then=1),
                    default=1,
                    output_field=IntegerField(),
                )
            )
            return queryset.order_by("status_order", "due_date", "id")
        
        elif data_type in ["recurring_bills", "recurring_incomes"]:
            # Recurring bills/incomes: ordenar por next_due_date crescente (mais próximo primeiro)
            return queryset.order_by("next_due_date", "id")
        
        else:
            # Fallback: ordenar por due_date crescente
            return queryset.order_by("due_date", "id")
    
    def _get_detail_response(self, instance, data_type: str, request) -> dict:
        """Retorna detalhes completos de um item específico."""
        config = self.VALID_TYPES[data_type]
        serializer = config["serializer"](instance, context={"request": request, "company": self.get_active_company()})
        
        response_data = {
            "type": data_type,
            "item": serializer.data,
        }
        
        # Adicionar informações extras para tipos específicos
        if data_type == "incomes" and instance.payment_transaction:
            response_data["payment_transaction"] = TransactionSerializer(
                instance.payment_transaction,
                context={"request": request, "company": self.get_active_company()}
            ).data
        
        elif data_type == "bills" and instance.payment_transaction:
            response_data["payment_transaction"] = TransactionSerializer(
                instance.payment_transaction,
                context={"request": request, "company": self.get_active_company()}
            ).data
        
        elif data_type == "recurring_bills":
            # Incluir resumo de pagamentos
            payments = RecurringBillPayment.objects.filter(
                recurring_bill=instance, company=instance.company
            )
            pending = payments.filter(status=RecurringBillPayment.Status.PENDENTE)
            paid = payments.filter(status=RecurringBillPayment.Status.QUITADA)
            
            response_data["payments_summary"] = {
                "total_payments": payments.count(),
                "pending_count": pending.count(),
                "paid_count": paid.count(),
                "total_pending": pending.aggregate(total=Sum("amount"))["total"] or Decimal("0"),
                "total_paid": paid.aggregate(total=Sum("amount"))["total"] or Decimal("0"),
            }
            
            # Incluir próximas 5 instâncias de pagamentos (ordenadas por due_date, próximas primeiro)
            # Filtrar apenas pagamentos futuros ou do dia atual
            today = timezone.localdate()
            next_payments = (
                payments.filter(due_date__gte=today)
                .select_related("recurring_bill", "recurring_bill__category", "recurring_bill__contact", "transaction", "transaction__bank_account")
                .order_by("due_date", "id")
                [:5]
            )
            response_data["next_payments"] = RecurringBillPaymentSerializer(
                next_payments, many=True, context={"request": request, "company": self.get_active_company()}
            ).data
        
        elif data_type == "recurring_incomes":
            # Incluir resumo de recebimentos
            receipts = RecurringIncomeReceipt.objects.filter(
                recurring_income=instance, company=instance.company
            )
            pending = receipts.filter(status=RecurringIncomeReceipt.Status.PENDENTE)
            received = receipts.filter(status=RecurringIncomeReceipt.Status.RECEBIDO)
            
            response_data["receipts_summary"] = {
                "total_receipts": receipts.count(),
                "pending_count": pending.count(),
                "received_count": received.count(),
                "total_pending": pending.aggregate(total=Sum("amount"))["total"] or Decimal("0"),
                "total_received": received.aggregate(total=Sum("amount"))["total"] or Decimal("0"),
            }
            
            # Incluir próximas 5 instâncias de recebimentos (ordenadas por due_date, próximas primeiro)
            # Filtrar apenas recebimentos futuros ou do dia atual
            today = timezone.localdate()
            next_receipts = (
                receipts.filter(due_date__gte=today)
                .select_related("recurring_income", "recurring_income__category", "recurring_income__contact", "transaction", "transaction__bank_account")
                .order_by("due_date", "id")
                [:5]
            )
            response_data["next_receipts"] = RecurringIncomeReceiptSerializer(
                next_receipts, many=True, context={"request": request, "company": self.get_active_company()}
            ).data
        
        elif data_type == "recurring_bill_payments" and instance.transaction:
            response_data["transaction"] = TransactionSerializer(
                instance.transaction,
                context={"request": request, "company": self.get_active_company()}
            ).data
        
        elif data_type == "recurring_income_receipts" and instance.transaction:
            response_data["transaction"] = TransactionSerializer(
                instance.transaction,
                context={"request": request, "company": self.get_active_company()}
            ).data
        
        return response_data
    
    def _get_summary(self, queryset, data_type: str) -> dict:
        """Gera resumo estatístico do queryset."""
        config = self.VALID_TYPES[data_type]
        total_count = queryset.count()
        total_amount = queryset.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        summary = {
            "total_items": total_count,
            "total_amount": total_amount,
        }
        
        # Adicionar estatísticas de status se aplicável
        if config.get("has_status"):
            status_field = config["status_field"]
            if data_type in ["incomes"]:
                summary["pendente_count"] = queryset.filter(**{status_field: Income.Status.PENDENTE}).count()
                summary["recebido_count"] = queryset.filter(**{status_field: Income.Status.RECEBIDO}).count()
            elif data_type in ["bills"]:
                summary["a_vencer_count"] = queryset.filter(**{status_field: Bill.Status.A_VENCER}).count()
                summary["quitada_count"] = queryset.filter(**{status_field: Bill.Status.QUITADA}).count()
            elif data_type in ["recurring_bill_payments"]:
                summary["pendente_count"] = queryset.filter(**{status_field: RecurringBillPayment.Status.PENDENTE}).count()
                summary["quitada_count"] = queryset.filter(**{status_field: RecurringBillPayment.Status.QUITADA}).count()
            elif data_type in ["recurring_income_receipts"]:
                summary["pendente_count"] = queryset.filter(**{status_field: RecurringIncomeReceipt.Status.PENDENTE}).count()
                summary["recebido_count"] = queryset.filter(**{status_field: RecurringIncomeReceipt.Status.RECEBIDO}).count()
        
        return summary
    
    def get(self, request):
        """
        GET /api/v1/financials/data/
        
        Retorna dados financeiros filtrados e paginados.
        """
        # Validar tipo
        data_type = request.query_params.get("type")
        if not data_type:
            return Response(
                {
                    "error": "Parâmetro 'type' é obrigatório.",
                    "valid_types": list(self.VALID_TYPES.keys()),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if data_type not in self.VALID_TYPES:
            return Response(
                {
                    "error": f"Tipo '{data_type}' inválido.",
                    "valid_types": list(self.VALID_TYPES.keys()),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        config = self.VALID_TYPES[data_type]
        company = self.get_active_company()
        
        # Verificar se é busca por UUID específico
        uuid_param = request.query_params.get("uuid")
        if uuid_param:
            try:
                instance = config["model"].objects.select_related(
                    *config["select_related"]
                ).get(id=uuid_param, company=company)
                
                return Response(self._get_detail_response(instance, data_type, request))
            
            except config["model"].DoesNotExist:
                return Response(
                    {"error": f"Item não encontrado com UUID: {uuid_param}"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        
        # Verificar versão do cache para invalidar se necessário
        version_key = f"financial_data_version:{company.id}:{data_type}"
        cache_version = cache.get(version_key, 0)
        
        # Gerar chave de cache incluindo a versão
        cache_params = {
            "type": data_type,
            "page": request.query_params.get("page", 1),
            "status": request.query_params.get("status"),
            "category_id": request.query_params.get("category_id"),
            "cost_center_id": request.query_params.get("cost_center_id"),
            "date_from": request.query_params.get("date_from"),
            "date_to": request.query_params.get("date_to"),
            "search": request.query_params.get("search"),
            "version": cache_version,  # Incluir versão na chave
        }
        cache_key = self._generate_cache_key(str(company.id), data_type, cache_params)
        
        # Tentar buscar do cache
        cached_response = cache.get(cache_key)
        if cached_response:
            return Response(cached_response)
        
        # Construir queryset
        queryset = config["model"].objects.select_related(*config["select_related"])
        queryset = self._apply_filters(queryset, data_type, request)
        queryset = self._get_ordering(data_type, queryset)
        
        # Gerar resumo (antes da paginação)
        summary = self._get_summary(queryset, data_type)
        
        # Paginação
        paginator = FinancialDataPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = config["serializer"](
                page, 
                many=True, 
                context={"request": request, "company": company}
            )
            
            response_data = {
                "type": data_type,
                "summary": summary,
                "items": serializer.data,
                "pagination": {
                    "page": int(request.query_params.get("page", 1)),
                    "page_size": paginator.page_size,
                    "total_pages": paginator.page.paginator.num_pages,
                    "total_items": paginator.page.paginator.count,
                    "has_next": paginator.page.has_next(),
                    "has_previous": paginator.page.has_previous(),
                },
                "available_filters": {
                    "type": list(self.VALID_TYPES.keys()),
                    "search_fields": ["category", "cost_center", "description", "status", "contact"],
                    "search_format": "campo#valor (ex: category#vendas,cost_center#marketing)",
                },
            }
            
            # Cachear resposta
            cache.set(cache_key, response_data, self.CACHE_TTL)
            
            return Response(response_data)
        
        # Fallback se paginação falhar
        serializer = config["serializer"](
            queryset[:10], 
            many=True, 
            context={"request": request, "company": company}
        )
        
        return Response({
            "type": data_type,
            "summary": summary,
            "items": serializer.data,
        })
    
    def post(self, request):
        """
        POST /api/v1/financials/data/
        
        Cria uma transação a partir de um item financeiro (bill, income, recurring_bill_payment, recurring_income_receipt).
        
        Body:
        -----
        {
            "uuid": "uuid-do-item",
            "type": "bills" | "incomes" | "recurring_bill_payments" | "recurring_income_receipts",
            "bank_account": "uuid-da-conta-bancaria",
            "transaction_date": "YYYY-MM-DD",
            "description": "Descrição opcional",
            "payment_method": "uuid-do-metodo-pagamento (opcional)"
        }
        
        Response:
        ---------
        Retorna o item atualizado com a transação criada.
        """
        serializer = FinancialDataTransactionSerializer(
            data=request.data,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        item_uuid = data["uuid"]
        item_type = data["type"]
        company = self.get_active_company()
        
        # Validar tipo
        if item_type not in self.VALID_TYPES:
            return Response(
                {
                    "error": f"Tipo '{item_type}' inválido.",
                    "valid_types": ["bills", "incomes", "recurring_bill_payments", "recurring_income_receipts"],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        config = self.VALID_TYPES[item_type]
        
        # Buscar o item
        try:
            item = config["model"].objects.select_related(
                *config["select_related"]
            ).get(id=item_uuid, company=company)
        except config["model"].DoesNotExist:
            return Response(
                {"error": f"Item não encontrado com UUID: {item_uuid}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Verificar se já tem transação
        if item_type == "bills":
            if item.status == Bill.Status.QUITADA:
                return Response(
                    {"error": "Esta conta já foi quitada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if item.payment_transaction:
                return Response(
                    {"error": "Esta conta já possui uma transação de pagamento."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif item_type == "incomes":
            if item.status == Income.Status.RECEBIDO:
                return Response(
                    {"error": "Esta conta já foi recebida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if item.payment_transaction:
                return Response(
                    {"error": "Esta conta já possui uma transação de recebimento."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif item_type == "recurring_bill_payments":
            if item.status == RecurringBillPayment.Status.QUITADA:
                return Response(
                    {"error": "Este pagamento já foi quitado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if item.transaction:
                return Response(
                    {"error": "Este pagamento já possui uma transação."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif item_type == "recurring_income_receipts":
            if item.status == RecurringIncomeReceipt.Status.RECEBIDO:
                return Response(
                    {"error": "Este recebimento já foi recebido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if item.transaction:
                return Response(
                    {"error": "Este recebimento já possui uma transação."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        # Extrair dados do item para pré-preencher a transação
        with db_transaction.atomic():
            # Determinar tipo de transação e descrição
            if item_type in ["bills", "recurring_bill_payments"]:
                transaction_type = Transaction.Types.DESPESA
                if item_type == "bills":
                    default_description = f"Pagamento - {item.description}"
                    category = item.category
                    cost_center = item.cost_center
                    contact = item.contact
                else:  # recurring_bill_payments
                    default_description = f"Pagamento - {item.recurring_bill.description}"
                    category = item.recurring_bill.category
                    cost_center = item.recurring_bill.cost_center
                    contact = item.recurring_bill.contact
            else:  # incomes, recurring_income_receipts
                transaction_type = Transaction.Types.RECEITA
                if item_type == "incomes":
                    default_description = f"Recebimento - {item.description}"
                    category = item.category
                    cost_center = item.cost_center
                    contact = item.contact
                else:  # recurring_income_receipts
                    default_description = f"Recebimento - {item.recurring_income.description}"
                    category = item.recurring_income.category
                    cost_center = item.recurring_income.cost_center
                    contact = item.recurring_income.contact
            
            description = data.get("description") or default_description
            
            # Criar transação
            # Nota: O método save() do modelo Transaction automaticamente atualiza
            # o current_balance da conta bancária através de _sync_bank_account_balance()
            transaction = Transaction.objects.create(
                company=company,
                bank_account=data["bank_account"],
                category=category,
                cost_center=cost_center,
                contact=contact,
                payment_method=data.get("payment_method"),
                description=description,
                amount=item.amount,
                type=transaction_type,
                transaction_date=data["transaction_date"],
            )
            
            # Atualizar o item
            if item_type == "bills":
                item.payment_transaction = transaction
                item.status = Bill.Status.QUITADA
                item.save(update_fields=["payment_transaction", "status", "updated_at"])
            elif item_type == "incomes":
                item.payment_transaction = transaction
                item.status = Income.Status.RECEBIDO
                item.save(update_fields=["payment_transaction", "status", "updated_at"])
            elif item_type == "recurring_bill_payments":
                item.transaction = transaction
                item.status = RecurringBillPayment.Status.QUITADA
                item.paid_on = data["transaction_date"]
                item.save(update_fields=["transaction", "status", "paid_on", "updated_at"])
            elif item_type == "recurring_income_receipts":
                item.transaction = transaction
                item.status = RecurringIncomeReceipt.Status.RECEBIDO
                item.received_on = data["transaction_date"]
                item.save(update_fields=["transaction", "status", "received_on", "updated_at"])
        
        # Invalidar cache para o tipo de dado modificado
        self._invalidate_cache(str(company.id), item_type)
        
        # Retornar detalhes atualizados do item
        item.refresh_from_db()
        return Response(
            self._get_detail_response(item, item_type, request),
            status=status.HTTP_201_CREATED,
        )
    
    def put(self, request):
        """
        PUT /api/v1/financials/data/
        
        Atualiza um recurring_bill ou recurring_income.
        Parcelas pendentes futuras são atualizadas com os novos dados.
        Parcelas já pagas/recebidas permanecem inalteradas.
        
        Body:
        -----
        {
            "uuid": "uuid-do-item",
            "type": "recurring_bills" | "recurring_incomes",
            "description": "Nova descrição",
            "amount": 1500.00,
            "frequency": "monthly",
            "category": "uuid-da-categoria",
            "cost_center": "uuid-do-centro-de-custo",
            "contact": "uuid-do-contato",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "next_due_date": "YYYY-MM-DD",
            "is_active": true
        }
        """
        return self._handle_update(request, partial=False)
    
    def patch(self, request):
        """
        PATCH /api/v1/financials/data/
        
        Atualiza parcialmente um recurring_bill ou recurring_income.
        Parcelas pendentes futuras são atualizadas com os novos dados.
        Parcelas já pagas/recebidas permanecem inalteradas.
        """
        return self._handle_update(request, partial=True)
    
    def _handle_update(self, request, partial=False):
        """Lógica compartilhada para PUT e PATCH."""
        item_uuid = request.data.get("uuid")
        item_type = request.data.get("type")
        
        if not item_uuid:
            return Response(
                {"error": "Campo 'uuid' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not item_type:
            return Response(
                {"error": "Campo 'type' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Apenas recurring_bills e recurring_incomes podem ser atualizados
        allowed_types = ["recurring_bills", "recurring_incomes"]
        if item_type not in allowed_types:
            return Response(
                {
                    "error": f"Tipo '{item_type}' não suporta atualização.",
                    "allowed_types": allowed_types,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        config = self.VALID_TYPES[item_type]
        company = self.get_active_company()
        
        # Buscar o item
        try:
            item = config["model"].objects.select_related(
                *config["select_related"]
            ).get(id=item_uuid, company=company)
        except config["model"].DoesNotExist:
            return Response(
                {"error": f"Item não encontrado com UUID: {item_uuid}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Preparar dados para o serializer (remover uuid e type)
        update_data = request.data.copy()
        update_data.pop("uuid", None)
        update_data.pop("type", None)
        
        # Serializar e validar
        serializer = config["serializer"](
            item,
            data=update_data,
            partial=partial,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        
        # O serializer já possui a lógica de regenerar payments/receipts
        # quando campos de agendamento são alterados
        with db_transaction.atomic():
            item = serializer.save()
            
            # Atualizar o amount das parcelas pendentes futuras
            if "amount" in update_data:
                today = timezone.localdate()
                if item_type == "recurring_bills":
                    RecurringBillPayment.objects.filter(
                        recurring_bill=item,
                        company=company,
                        status=RecurringBillPayment.Status.PENDENTE,
                        due_date__gte=today
                    ).update(amount=item.amount)
                else:  # recurring_incomes
                    RecurringIncomeReceipt.objects.filter(
                        recurring_income=item,
                        company=company,
                        status=RecurringIncomeReceipt.Status.PENDENTE,
                        due_date__gte=today
                    ).update(amount=item.amount)
        
        # Invalidar cache
        self._invalidate_cache(str(company.id), item_type)
        # Também invalidar o cache dos payments/receipts relacionados
        if item_type == "recurring_bills":
            self._invalidate_cache(str(company.id), "recurring_bill_payments")
        else:
            self._invalidate_cache(str(company.id), "recurring_income_receipts")
        
        # Retornar detalhes atualizados
        item.refresh_from_db()
        return Response(
            self._get_detail_response(item, item_type, request),
            status=status.HTTP_200_OK,
        )
    
    def delete(self, request):
        """
        DELETE /api/v1/financials/data/
        
        Remove um recurring_bill ou recurring_income.
        
        IMPORTANTE:
        - Parcelas pendentes futuras são removidas.
        - Parcelas já pagas/recebidas são mantidas para histórico
          (a referência ao recurring é definida como NULL).
        
        Query Parameters:
        -----------------
        - uuid (required): UUID do item a ser deletado.
        - type (required): "recurring_bills" ou "recurring_incomes".
        """
        item_uuid = request.query_params.get("uuid")
        item_type = request.query_params.get("type")
        
        if not item_uuid:
            return Response(
                {"error": "Parâmetro 'uuid' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not item_type:
            return Response(
                {"error": "Parâmetro 'type' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Apenas recurring_bills e recurring_incomes podem ser deletados
        allowed_types = ["recurring_bills", "recurring_incomes"]
        if item_type not in allowed_types:
            return Response(
                {
                    "error": f"Tipo '{item_type}' não suporta deleção via esta API.",
                    "allowed_types": allowed_types,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        config = self.VALID_TYPES[item_type]
        company = self.get_active_company()
        
        # Buscar o item
        try:
            item = config["model"].objects.get(id=item_uuid, company=company)
        except config["model"].DoesNotExist:
            return Response(
                {"error": f"Item não encontrado com UUID: {item_uuid}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        today = timezone.localdate()
        
        with db_transaction.atomic():
            if item_type == "recurring_bills":
                # Deletar apenas parcelas pendentes futuras
                RecurringBillPayment.objects.filter(
                    recurring_bill=item,
                    company=company,
                    status=RecurringBillPayment.Status.PENDENTE,
                    due_date__gte=today
                ).delete()
                
                # Parcelas já quitadas terão recurring_bill=NULL após o delete do item
                # (devido ao on_delete=SET_NULL)
            else:  # recurring_incomes
                # Deletar apenas parcelas pendentes futuras
                RecurringIncomeReceipt.objects.filter(
                    recurring_income=item,
                    company=company,
                    status=RecurringIncomeReceipt.Status.PENDENTE,
                    due_date__gte=today
                ).delete()
                
                # Parcelas já recebidas terão recurring_income=NULL após o delete do item
            
            # Deletar o item principal
            item.delete()
        
        # Invalidar cache
        self._invalidate_cache(str(company.id), item_type)
        if item_type == "recurring_bills":
            self._invalidate_cache(str(company.id), "recurring_bill_payments")
        else:
            self._invalidate_cache(str(company.id), "recurring_income_receipts")
        
        return Response(
            {"message": f"Item deletado com sucesso. Parcelas já pagas/recebidas foram mantidas para histórico."},
            status=status.HTTP_200_OK,
        )
