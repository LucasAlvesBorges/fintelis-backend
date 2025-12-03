from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import Q, Sum
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from django.utils import timezone

from .mixins import ActiveCompanyMixin
from .models import (
    Bank,
    BankAccount,
    Bill,
    CashRegister,
    Category,
    Income,
    RecurringBill,
    RecurringIncome,
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
    IncomePaymentSerializer,
    IncomeSerializer,
    RecurringBillSerializer,
    RecurringIncomeSerializer,
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
        "company", "category", "cost_center"
    )
    serializer_class = RecurringBillSerializer


class RecurringIncomeViewSet(CompanyScopedViewSet):
    queryset = RecurringIncome.objects.all().select_related(
        "company", "category", "cost_center"
    )
    serializer_class = RecurringIncomeSerializer
