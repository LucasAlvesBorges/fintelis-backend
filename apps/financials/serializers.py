import calendar
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

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
from apps.contacts.models import Contact
from .models import FrequencyChoices


class CompanyContextMixin:
    company_filtered_fields: tuple[str, ...] = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get("company")
        if not company:
            return
        for field_name in self.company_filtered_fields:
            field = self.fields.get(field_name)
            if not field:
                continue
            queryset = getattr(field, "queryset", None)
            if queryset is None:
                continue
            self.fields[field_name].queryset = queryset.filter(company=company)


class CompanyScopedModelSerializer(CompanyContextMixin, serializers.ModelSerializer):
    pass


class CompanyScopedSerializer(CompanyContextMixin, serializers.Serializer):
    pass


def _add_months(base_date: date, months: int) -> date:
    month = base_date.month - 1 + months
    year = base_date.year + month // 12
    month = month % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_due_date(current: date, frequency: str) -> date | None:
    if not current:
        return None
    if frequency == FrequencyChoices.DAILY:
        return current + timedelta(days=1)
    if frequency == FrequencyChoices.WEEKLY:
        return current + timedelta(days=7)
    if frequency == FrequencyChoices.MONTHLY:
        return _add_months(current, 1)
    if frequency == FrequencyChoices.QUARTERLY:
        return _add_months(current, 3)
    if frequency == FrequencyChoices.YEARLY:
        return _add_months(current, 12)
    return None


def _build_schedule_dates(start: date | None, frequency: str, end: date | None, *, months_horizon: int = 12):
    if not start:
        return []
    horizon = end or _add_months(start, months_horizon)
    dates = []
    current = start
    while current and current <= horizon:
        dates.append(current)
        current = _next_due_date(current, frequency)
    return dates


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = (
            "id",
            "code",
            "name",
            "cnpj",
            "logo",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BankAccountSerializer(CompanyScopedModelSerializer):
    bank_details = BankSerializer(source="bank", read_only=True)

    class Meta:
        model = BankAccount
        fields = (
            "id",
            "company",
            "bank",
            "bank_details",
            "name",
            "description",
            "type",
            "initial_balance",
            "current_balance",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "company",
            "current_balance",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "bank": {"required": False, "allow_null": True},
        }


class CashRegisterSerializer(CompanyScopedModelSerializer):
    company_filtered_fields = ("default_bank_account",)

    class Meta:
        model = CashRegister
        fields = (
            "id",
            "company",
            "name",
            "default_bank_account",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "company", "created_at", "updated_at")


class CategorySerializer(CompanyScopedModelSerializer):
    company_filtered_fields = ("parent",)

    class Meta:
        model = Category
        fields = (
            "id",
            "company",
            "code",
            "parent",
            "name",
            "type",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "company", "code", "created_at", "updated_at")
        extra_kwargs = {
            "parent": {"required": False, "allow_null": True},
        }


class TransactionSerializer(CompanyScopedModelSerializer):
    company_filtered_fields = (
        "bank_account",
        "category",
        "cash_register",
        "contact",
        "cost_center",
    )
    company_name = serializers.CharField(source="company.name", read_only=True)
    bank_account_name = serializers.CharField(source="bank_account.name", read_only=True, allow_null=True)
    category_name = serializers.CharField(source="category.name", read_only=True, allow_null=True)
    contact_name = serializers.CharField(source="contact.name", read_only=True, allow_null=True)
    cash_register_name = serializers.CharField(source="cash_register.name", read_only=True, allow_null=True)
    cost_center_name = serializers.CharField(source="cost_center.name", read_only=True, allow_null=True)
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True, allow_null=True)
    order_code = serializers.CharField(read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id",
            "company",
            "company_name",
            "bank_account",
            "bank_account_name",
            "category",
            "category_name",
            "cash_register",
            "cash_register_name",
            "contact",
            "contact_name",
            "cost_center",
            "cost_center_name",
            "payment_method",
            "payment_method_name",
            "order",
            "order_code",
            "related_transaction",
            "linked_transaction",
            "description",
            "amount",
            "type",
            "transaction_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "company",
            "company_name",
            "bank_account_name",
            "category_name",
            "cash_register_name",
            "contact_name",
            "cost_center_name",
            "payment_method_name",
            "order",
            "order_code",
            "linked_transaction",
            "related_transaction",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "bank_account": {"required": False, "allow_null": True},
            "category": {"required": False, "allow_null": True},
            "cash_register": {"required": False, "allow_null": True},
            "contact": {"required": False, "allow_null": True},
            "cost_center": {"required": False, "allow_null": True},
            "payment_method": {"required": False, "allow_null": True},
            "order": {"read_only": True},
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        amount = attrs.get("amount")
        if amount is not None and amount <= 0:
            raise serializers.ValidationError(
                {"amount": "Amount must be greater than zero."}
            )

        tx_type = attrs.get("type")
        cash_register = attrs.get("cash_register")
        bank_account = attrs.get("bank_account")

        if cash_register and not bank_account:
            attrs["bank_account"] = cash_register.default_bank_account

        if tx_type in {
            Transaction.Types.TRANSFERENCIA_INTERNA,
            Transaction.Types.TRANSFERENCIA_EXTERNA,
        }:
            if attrs.get("category"):
                raise serializers.ValidationError(
                    {"category": "Transfer transactions cannot use categories."}
                )
            if attrs.get("cash_register"):
                raise serializers.ValidationError(
                    {
                        "cash_register": "Transfer transactions cannot reference cash registers."
                    }
                )

        return attrs


class TransactionRefundSerializer(CompanyScopedSerializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    description = serializers.CharField(max_length=255, allow_blank=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        original: Transaction = self.context["original_transaction"]
        if original.type != Transaction.Types.RECEITA:
            raise serializers.ValidationError(
                "Apenas transações de receita podem ser estornadas."
            )
        if original.related_transaction_id:
            raise serializers.ValidationError(
                "Não é possível estornar uma transação que já é estorno."
            )

        if attrs["amount"] <= 0:
            raise serializers.ValidationError(
                {"amount": "O valor do estorno deve ser maior que zero."}
            )

        already_refunded = original.get_total_refunded()
        remaining = original.amount - already_refunded
        if attrs["amount"] > remaining:
            raise serializers.ValidationError(
                {
                    "amount": f"O valor excede o saldo disponível para estorno (R$ {remaining})."
                }
            )
        return attrs


class BillSerializer(CompanyScopedModelSerializer):
    company_filtered_fields = ("category", "contact", "cost_center")
    company_name = serializers.CharField(source="company.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, allow_null=True)
    contact_name = serializers.CharField(source="contact.name", read_only=True, allow_null=True)
    cost_center_name = serializers.CharField(source="cost_center.name", read_only=True, allow_null=True)
    order_code = serializers.CharField(read_only=True)

    class Meta:
        model = Bill
        fields = (
            "id",
            "company",
            "company_name",
            "category",
            "category_name",
            "contact",
            "contact_name",
            "cost_center",
            "cost_center_name",
            "order",
            "order_code",
            "payment_transaction",
            "description",
            "amount",
            "due_date",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "company",
            "company_name",
            "category_name",
            "contact_name",
            "cost_center_name",
            "order",
            "order_code",
            "payment_transaction",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "contact": {"required": False, "allow_null": True},
            "cost_center": {"required": False, "allow_null": True},
            "order": {"read_only": True},
        }


class IncomeSerializer(CompanyScopedModelSerializer):
    company_filtered_fields = ("category", "contact", "cost_center")
    company_name = serializers.CharField(source="company.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, allow_null=True)
    contact_name = serializers.CharField(source="contact.name", read_only=True, allow_null=True)
    cost_center_name = serializers.CharField(source="cost_center.name", read_only=True, allow_null=True)
    order_code = serializers.CharField(read_only=True)

    class Meta:
        model = Income
        fields = (
            "id",
            "company",
            "company_name",
            "category",
            "category_name",
            "contact",
            "contact_name",
            "cost_center",
            "cost_center_name",
            "order",
            "order_code",
            "payment_transaction",
            "description",
            "amount",
            "due_date",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "company",
            "company_name",
            "category_name",
            "contact_name",
            "cost_center_name",
            "order",
            "order_code",
            "payment_transaction",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "contact": {"required": False, "allow_null": True},
            "cost_center": {"required": False, "allow_null": True},
            "order": {"read_only": True},
        }


class RecurringBillSerializer(CompanyScopedModelSerializer):
    company_filtered_fields = ("category", "cost_center")
    company_name = serializers.CharField(source="company.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, allow_null=True)
    cost_center_name = serializers.CharField(source="cost_center.name", read_only=True, allow_null=True)
    order_code = serializers.CharField(read_only=True)

    class Meta:
        model = RecurringBill
        fields = (
            "id",
            "company",
            "company_name",
            "category",
            "category_name",
            "cost_center",
            "cost_center_name",
            "order",
            "order_code",
            "description",
            "amount",
            "frequency",
            "start_date",
            "end_date",
            "next_due_date",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "company",
            "company_name",
            "category_name",
            "cost_center_name",
            "order",
            "order_code",
            "created_at",
            "updated_at",
        )

    def _regenerate_payments(self, instance: RecurringBill):
        today = timezone.localdate()
        base_qs = RecurringBillPayment.objects.filter(recurring_bill=instance)
        existing_paid_dates = set(
            base_qs.exclude(status=RecurringBillPayment.Status.PENDENTE).values_list("due_date", flat=True)
        )
        base_qs.filter(status=RecurringBillPayment.Status.PENDENTE, due_date__gte=today).delete()

        start = instance.next_due_date or instance.start_date
        schedule_dates = _build_schedule_dates(start, instance.frequency, instance.end_date, months_horizon=12)
        to_create = []
        for due in schedule_dates:
            if due in existing_paid_dates:
                continue
            to_create.append(
                RecurringBillPayment(
                    company=instance.company,
                    recurring_bill=instance,
                    due_date=due,
                    amount=instance.amount,
                    status=RecurringBillPayment.Status.PENDENTE,
                )
            )
        if to_create:
            RecurringBillPayment.objects.bulk_create(to_create, ignore_conflicts=True)

    def create(self, validated_data):
        company = self.context.get("company")
        if company:
            validated_data["company"] = company
        with transaction.atomic():
            instance = super().create(validated_data)
            self._regenerate_payments(instance)
        return instance

    def update(self, instance, validated_data):
        schedule_fields = {"amount", "frequency", "start_date", "end_date", "next_due_date"}
        should_regen = any(field in validated_data for field in schedule_fields)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if should_regen:
                self._regenerate_payments(instance)
        return instance


class RecurringIncomeSerializer(CompanyScopedModelSerializer):
    company_filtered_fields = ("category", "cost_center")
    company_name = serializers.CharField(source="company.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, allow_null=True)
    cost_center_name = serializers.CharField(source="cost_center.name", read_only=True, allow_null=True)
    order_code = serializers.CharField(read_only=True)

    class Meta:
        model = RecurringIncome
        fields = (
            "id",
            "company",
            "company_name",
            "category",
            "category_name",
            "cost_center",
            "cost_center_name",
            "order",
            "order_code",
            "description",
            "amount",
            "frequency",
            "start_date",
            "end_date",
            "next_due_date",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "company",
            "company_name",
            "category_name",
            "cost_center_name",
            "order",
            "order_code",
            "created_at",
            "updated_at",
        )

    def _regenerate_receipts(self, instance: RecurringIncome):
        today = timezone.localdate()
        base_qs = RecurringIncomeReceipt.objects.filter(recurring_income=instance)
        existing_received_dates = set(
            base_qs.exclude(status=RecurringIncomeReceipt.Status.PENDENTE).values_list("due_date", flat=True)
        )
        base_qs.filter(status=RecurringIncomeReceipt.Status.PENDENTE, due_date__gte=today).delete()

        start = instance.next_due_date or instance.start_date
        schedule_dates = _build_schedule_dates(start, instance.frequency, instance.end_date, months_horizon=12)
        to_create = []
        for due in schedule_dates:
            if due in existing_received_dates:
                continue
            to_create.append(
                RecurringIncomeReceipt(
                    company=instance.company,
                    recurring_income=instance,
                    due_date=due,
                    amount=instance.amount,
                    status=RecurringIncomeReceipt.Status.PENDENTE,
                )
            )
        if to_create:
            RecurringIncomeReceipt.objects.bulk_create(to_create, ignore_conflicts=True)

    def create(self, validated_data):
        company = self.context.get("company")
        if company:
            validated_data["company"] = company
        with transaction.atomic():
            instance = super().create(validated_data)
            self._regenerate_receipts(instance)
        return instance

    def update(self, instance, validated_data):
        schedule_fields = {"amount", "frequency", "start_date", "end_date", "next_due_date"}
        should_regen = any(field in validated_data for field in schedule_fields)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if should_regen:
                self._regenerate_receipts(instance)
        return instance


class BillPaymentSerializer(CompanyScopedSerializer):
    company_filtered_fields = ("bank_account",)

    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all()
    )
    transaction_date = serializers.DateField()
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )


class IncomePaymentSerializer(CompanyScopedSerializer):
    company_filtered_fields = ("bank_account",)

    bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all()
    )
    transaction_date = serializers.DateField()
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )


class TransferSerializer(CompanyScopedSerializer):
    company_filtered_fields = ("from_bank_account", "to_bank_account")

    from_bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all()
    )
    to_bank_account = serializers.PrimaryKeyRelatedField(
        queryset=BankAccount.objects.all()
    )
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    transaction_date = serializers.DateField()
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["from_bank_account"] == attrs["to_bank_account"]:
            raise serializers.ValidationError(
                {
                    "to_bank_account": "Origin and destination accounts must be different."
                }
            )
        if attrs["amount"] <= 0:
            raise serializers.ValidationError(
                {"amount": "Amount must be greater than zero."}
            )
        return attrs
