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
    RecurringIncome,
    Transaction,
)
from apps.contacts.models import Contact


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
