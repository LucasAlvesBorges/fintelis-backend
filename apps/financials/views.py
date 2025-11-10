from django.db import transaction as db_transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.companies.models import Company, Membership

from .models import (
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
    BankAccountSerializer,
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
)


class ActiveCompanyMixin:
    """
    Helper mixin that resolves the active company either from an attribute injected
    by middleware or from the X-Company-ID header / query params. It also validates
    that the authenticated user belongs to that company via Membership.
    """

    def get_active_company(self) -> Company:
        if hasattr(self.request, '_cached_active_company'):
            return self.request._cached_active_company

        company = getattr(self.request, 'active_company', None)
        if company:
            self._ensure_membership(company)
            self.request._cached_active_company = company
            return company

        company_id = (
            self.request.headers.get('X-Company-ID')
            or self.request.query_params.get('company_id')
            or self.request.data.get('company_id')
            or self.request.data.get('company')
        )
        if not company_id:
            raise ValidationError('Active company not provided. Use the X-Company-ID header or set request.active_company.')

        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist as exc:
            raise ValidationError('Company not found.') from exc

        self._ensure_membership(company)
        self.request._cached_active_company = company
        return company

    def _ensure_membership(self, company: Company) -> None:
        user = self.request.user
        if not user or not user.is_authenticated:
            raise PermissionDenied('Authentication required.')
        if not Membership.objects.filter(company=company, user=user).exists():
            raise PermissionDenied('You do not belong to this company.')


class IsCompanyMember(permissions.BasePermission):
    """
    Ensures requests include an active company and that the user belongs to it.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # get_active_company raises ValidationError or PermissionDenied with useful messages.
        view.get_active_company()
        return True


class CompanyScopedViewSet(ActiveCompanyMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    company_field = 'company'

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self.get_active_company()
        return queryset.filter(**{self.company_field: company})

    def perform_create(self, serializer):
        serializer.save(**{self.company_field: self.get_active_company()})

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context['company'] = self.get_active_company()
        except (ValidationError, PermissionDenied):
            pass
        return context


class BankAccountViewSet(CompanyScopedViewSet):
    queryset = BankAccount.objects.all().select_related('company')
    serializer_class = BankAccountSerializer


class CashRegisterViewSet(CompanyScopedViewSet):
    queryset = CashRegister.objects.all().select_related('company', 'default_bank_account')
    serializer_class = CashRegisterSerializer


class CategoryViewSet(CompanyScopedViewSet):
    queryset = Category.objects.all().select_related('company')
    serializer_class = CategorySerializer


class TransactionViewSet(CompanyScopedViewSet):
    queryset = Transaction.objects.all().select_related(
        'company',
        'bank_account',
        'category',
        'cash_register',
        'linked_transaction',
    )
    serializer_class = TransactionSerializer

    @action(detail=False, methods=['post'], url_path='transfer')
    def transfer(self, request):
        serializer = TransferSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        company = self.get_active_company()

        description = data.get('description') or 'Transferência entre contas'

        with db_transaction.atomic():
            outgoing = Transaction.objects.create(
                company=company,
                bank_account=data['from_bank_account'],
                description=f'Saída: {description}',
                amount=data['amount'],
                type=Transaction.Types.TRANSFERENCIA_EXTERNA,
                transaction_date=data['transaction_date'],
            )
            incoming = Transaction.objects.create(
                company=company,
                bank_account=data['to_bank_account'],
                description=f'Entrada: {description}',
                amount=data['amount'],
                type=Transaction.Types.TRANSFERENCIA_INTERNA,
                transaction_date=data['transaction_date'],
                linked_transaction=outgoing,
            )
            outgoing.linked_transaction = incoming
            outgoing.save(update_fields=['linked_transaction', 'updated_at'])

        response_serializer = self.get_serializer([outgoing, incoming], many=True)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class BillViewSet(CompanyScopedViewSet):
    queryset = Bill.objects.all().select_related('company', 'category', 'payment_transaction')
    serializer_class = BillSerializer

    @action(detail=True, methods=['post'], url_path='record-payment')
    def record_payment(self, request, pk=None):
        bill = self.get_object()
        if bill.status == Bill.Status.QUITADA:
            raise ValidationError('This bill is already settled.')

        serializer = BillPaymentSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        description = data.get('description') or f'Pagamento - {bill.description}'

        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                company=bill.company,
                bank_account=data['bank_account'],
                category=bill.category,
                description=description,
                amount=bill.amount,
                type=Transaction.Types.DESPESA,
                transaction_date=data['transaction_date'],
            )
            bill.payment_transaction = transaction
            bill.status = Bill.Status.QUITADA
            bill.save(update_fields=['payment_transaction', 'status', 'updated_at'])

        return Response(self.get_serializer(bill).data, status=status.HTTP_200_OK)


class IncomeViewSet(CompanyScopedViewSet):
    queryset = Income.objects.all().select_related('company', 'category', 'payment_transaction')
    serializer_class = IncomeSerializer

    @action(detail=True, methods=['post'], url_path='record-payment')
    def record_payment(self, request, pk=None):
        income = self.get_object()
        if income.status == Income.Status.RECEBIDO:
            raise ValidationError('This income is already settled.')

        serializer = IncomePaymentSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        description = data.get('description') or f'Recebimento - {income.description}'

        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                company=income.company,
                bank_account=data['bank_account'],
                category=income.category,
                description=description,
                amount=income.amount,
                type=Transaction.Types.RECEITA,
                transaction_date=data['transaction_date'],
            )
            income.payment_transaction = transaction
            income.status = Income.Status.RECEBIDO
            income.save(update_fields=['payment_transaction', 'status', 'updated_at'])

        return Response(self.get_serializer(income).data, status=status.HTTP_200_OK)


class RecurringBillViewSet(CompanyScopedViewSet):
    queryset = RecurringBill.objects.all().select_related('company', 'category')
    serializer_class = RecurringBillSerializer


class RecurringIncomeViewSet(CompanyScopedViewSet):
    queryset = RecurringIncome.objects.all().select_related('company', 'category')
    serializer_class = RecurringIncomeSerializer
