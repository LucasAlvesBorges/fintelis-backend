import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction as db_transaction
from django.db.models import F

from apps.companies.models import Company


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Garantimos que regras cross-model rodem sempre
        self.full_clean()
        return super().save(*args, **kwargs)


class FrequencyChoices(models.TextChoices):
    DAILY = 'daily', 'Diário'
    WEEKLY = 'weekly', 'Semanal'
    MONTHLY = 'monthly', 'Mensal'
    QUARTERLY = 'quarterly', 'Trimestral'
    YEARLY = 'yearly', 'Anual'


class BankAccount(TimeStampedModel):
    class Types(models.TextChoices):
        CONTA_CORRENTE = 'conta_corrente', 'Conta Corrente'
        CONTA_POUPANCA = 'conta_poupanca', 'Conta Poupança'
        BANCO_CREDITOS = 'banco_de_creditos', 'Banco de Créditos'
        CARTEIRA_DIGITAL = 'carteira_digital', 'Carteira Digital'
        COFRE = 'cofre', 'Cofre'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=25, choices=Types.choices)
    initial_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'bank_account'
        ordering = ['company__name', 'name']

    def __str__(self):
        return f'{self.name} ({self.company})'

    def save(self, *args, **kwargs):
        if self._state.adding and (self.current_balance is None or self.current_balance == 0):
            self.current_balance = self.initial_balance
        super().save(*args, **kwargs)


class CashRegister(TimeStampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='cash_registers',
    )
    name = models.CharField(max_length=100)
    default_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name='cash_registers',
    )

    class Meta:
        db_table = 'cash_register'
        ordering = ['company__name', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'],
                name='uniq_cash_register_company_name',
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.default_bank_account
            and self.company_id
            and self.default_bank_account.company_id != self.company_id
        ):
            raise ValidationError(
                {'default_bank_account': 'Bank account must belong to the same company.'}
            )

    def __str__(self):
        return f'{self.name} ({self.company})'


class Category(TimeStampedModel):
    class Types(models.TextChoices):
        RECEITA = 'receita', 'Receita'
        DESPESA = 'despesa', 'Despesa'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='categories',
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=Types.choices)

    class Meta:
        db_table = 'category'
        ordering = ['company__name', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name', 'type'],
                name='uniq_category_company_name_type',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'


class Transaction(TimeStampedModel):
    class Types(models.TextChoices):
        RECEITA = 'receita', 'Receita'
        DESPESA = 'despesa', 'Despesa'
        TRANSFERENCIA_INTERNA = 'transferencia_interna', 'Transferência Interna'
        TRANSFERENCIA_EXTERNA = 'transferencia_externa', 'Transferência Externa'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name='transactions',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='transactions',
        null=True,
        blank=True,
    )
    cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.SET_NULL,
        related_name='transactions',
        null=True,
        blank=True,
    )
    linked_transaction = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        related_name='reverse_linked_transaction',
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    type = models.CharField(max_length=25, choices=Types.choices)
    transaction_date = models.DateField()

    class Meta:
        db_table = 'transaction'
        ordering = ['-transaction_date', '-id']

    def clean(self):
        super().clean()
        self._validate_company_scope()
        self._validate_category_type_alignment()
        self._validate_cash_register_destination()
        self._validate_linked_transaction()

    def save(self, *args, **kwargs):
        with db_transaction.atomic():
            previous = None
            if self.pk:
                previous = (
                    Transaction.objects.select_for_update()
                    .filter(pk=self.pk)
                    .only('bank_account_id', 'amount', 'type')
                    .first()
                )
            super().save(*args, **kwargs)
            self._sync_bank_account_balance(previous)

    def delete(self, *args, **kwargs):
        with db_transaction.atomic():
            instance = (
                Transaction.objects.select_for_update()
                .filter(pk=self.pk)
                .only('bank_account_id', 'amount', 'type')
                .first()
            )
            if instance:
                self._update_bank_account_balance(
                    instance.bank_account_id,
                    -self._compute_balance_delta(instance.type, instance.amount),
                )
        return super().delete(*args, **kwargs)

    def _validate_company_scope(self):
        errors = {}
        if self.bank_account and self.bank_account.company_id != self.company_id:
            errors['bank_account'] = 'Bank account must belong to the same company.'
        if self.cash_register and self.cash_register.company_id != self.company_id:
            errors['cash_register'] = 'Cash register must belong to the same company.'
        if self.category and self.category.company_id != self.company_id:
            errors['category'] = 'Category must belong to the same company.'
        if errors:
            raise ValidationError(errors)

    def _validate_category_type_alignment(self):
        if not self.category:
            return
        if self.type in {
            self.Types.TRANSFERENCIA_EXTERNA,
            self.Types.TRANSFERENCIA_INTERNA,
        }:
            raise ValidationError({'category': 'Transfer transactions cannot have category.'})
        if self.category.type != self.type:
            raise ValidationError(
                {'category': 'Category type must match transaction type.'}
            )

    def _validate_cash_register_destination(self):
        if not self.cash_register:
            return
        if self.bank_account_id != self.cash_register.default_bank_account_id:
            raise ValidationError(
                {
                    'bank_account': (
                        'Bank account must match the default destination of the cash register.'
                    )
                }
            )

    def _validate_linked_transaction(self):
        if not self.linked_transaction:
            return
        if self.linked_transaction_id == self.id:
            raise ValidationError(
                {'linked_transaction': 'Transaction cannot link to itself.'}
            )
        if self.linked_transaction.company_id != self.company_id:
            raise ValidationError(
                {'linked_transaction': 'Linked transaction must belong to the same company.'}
            )
        transfer_types = {
            self.Types.TRANSFERENCIA_INTERNA,
            self.Types.TRANSFERENCIA_EXTERNA,
        }
        if self.type not in transfer_types:
            raise ValidationError(
                {
                    'type': (
                        'Only transfer transactions may reference a linked transaction.'
                    )
                }
            )
        if self.linked_transaction.type not in transfer_types:
            raise ValidationError(
                {
                    'linked_transaction': (
                        'Linked transaction must represent a transfer movement.'
                    )
                }
            )

    def __str__(self):
        return f'{self.description} ({self.get_type_display()})'

    # Balance helpers -------------------------------------------------

    def _sync_bank_account_balance(self, previous: 'Transaction | None'):
        if previous:
            self._update_bank_account_balance(
                previous.bank_account_id,
                -self._compute_balance_delta(previous.type, previous.amount),
            )
        self._update_bank_account_balance(
            self.bank_account_id,
            self._compute_balance_delta(self.type, self.amount),
        )

    def _update_bank_account_balance(self, bank_account_id, delta: Decimal):
        if not bank_account_id or delta == 0:
            return
        BankAccount.objects.filter(pk=bank_account_id).update(
            current_balance=F('current_balance') + delta
        )

    @staticmethod
    def _compute_balance_delta(tx_type: str, amount: Decimal) -> Decimal:
        if amount in (None, 0):
            return Decimal('0')
        if tx_type in {
            Transaction.Types.RECEITA,
            Transaction.Types.TRANSFERENCIA_INTERNA,
        }:
            return amount
        if tx_type in {
            Transaction.Types.DESPESA,
            Transaction.Types.TRANSFERENCIA_EXTERNA,
        }:
            return -amount
        return Decimal('0')


class Bill(TimeStampedModel):
    class Status(models.TextChoices):
        A_VENCER = 'a_vencer', 'A Vencer'
        QUITADA = 'quitada', 'Quitada'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='bills',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='bills',
        null=True,
        blank=True,
    )
    payment_transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        related_name='bill_payment',
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.A_VENCER)

    class Meta:
        db_table = 'bill'
        ordering = ['-due_date', '-id']

    def clean(self):
        super().clean()
        errors = {}
        if self.category:
            if self.category.company_id != self.company_id:
                errors['category'] = 'Category must belong to the same company.'
            elif self.category.type != Category.Types.DESPESA:
                errors['category'] = 'Bills must reference an expense category.'
        if self.payment_transaction:
            if self.payment_transaction.company_id != self.company_id:
                errors['payment_transaction'] = 'Transaction must belong to the same company.'
            if self.payment_transaction.type != Transaction.Types.DESPESA:
                errors['payment_transaction'] = (
                    'Bill payments must reference an expense transaction.'
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.description} ({self.get_status_display()})'


class Income(TimeStampedModel):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        RECEBIDO = 'recebido', 'Recebido'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='incomes',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='incomes',
        null=True,
        blank=True,
    )
    payment_transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        related_name='income_payment',
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)

    class Meta:
        db_table = 'income'
        ordering = ['-due_date', '-id']

    def clean(self):
        super().clean()
        errors = {}
        if self.category:
            if self.category.company_id != self.company_id:
                errors['category'] = 'Category must belong to the same company.'
            elif self.category.type != Category.Types.RECEITA:
                errors['category'] = 'Income must reference a revenue category.'
        if self.payment_transaction:
            if self.payment_transaction.company_id != self.company_id:
                errors['payment_transaction'] = 'Transaction must belong to the same company.'
            if self.payment_transaction.type != Transaction.Types.RECEITA:
                errors['payment_transaction'] = (
                    'Income receipts must reference a revenue transaction.'
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.description} ({self.get_status_display()})'


class RecurringBill(TimeStampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='recurring_bills',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='recurring_bills',
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FrequencyChoices.choices)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_due_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'recurring_bill'
        ordering = ['company__name', 'next_due_date']

    def clean(self):
        super().clean()
        errors = {}
        if self.category:
            if self.category.company_id != self.company_id:
                errors['category'] = 'Category must belong to the same company.'
            elif self.category.type != Category.Types.DESPESA:
                errors['category'] = 'Recurring bills must reference an expense category.'
        if self.end_date and self.end_date < self.start_date:
            errors['end_date'] = 'End date cannot be earlier than the start date.'
        if self.next_due_date < self.start_date:
            errors['next_due_date'] = 'Next due date must be on or after the start date.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.description} ({self.frequency})'


class RecurringIncome(TimeStampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='recurring_incomes',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='recurring_incomes',
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FrequencyChoices.choices)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_due_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'recurring_income'
        ordering = ['company__name', 'next_due_date']

    def clean(self):
        super().clean()
        errors = {}
        if self.category:
            if self.category.company_id != self.company_id:
                errors['category'] = 'Category must belong to the same company.'
            elif self.category.type != Category.Types.RECEITA:
                errors['category'] = 'Recurring incomes must reference a revenue category.'
        if self.end_date and self.end_date < self.start_date:
            errors['end_date'] = 'End date cannot be earlier than the start date.'
        if self.next_due_date < self.start_date:
            errors['next_due_date'] = 'Next due date must be on or after the start date.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.description} ({self.frequency})'
