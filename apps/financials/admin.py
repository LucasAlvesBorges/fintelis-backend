from django.contrib import admin

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


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)
    ordering = ('code',)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'bank', 'type', 'initial_balance', 'current_balance', 'created_at')
    search_fields = ('name', 'company__name', 'bank__name', 'bank__code')
    list_filter = ('type', 'company', 'bank')
    ordering = ('company__name', 'name')
    autocomplete_fields = ('bank',)


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'default_bank_account', 'created_at')
    search_fields = ('name', 'company__name')
    list_filter = ('company',)
    ordering = ('company__name', 'name')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'company', 'type', 'parent', 'created_at')
    search_fields = ('code', 'name', 'company__name')
    list_filter = ('type', 'company', 'parent')
    ordering = ('company__name', 'code', 'name')
    autocomplete_fields = ('parent',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'description',
        'company',
        'type',
        'amount',
        'transaction_date',
        'bank_account',
        'cash_register',
        'contact',
        'linked_transaction',
    )
    autocomplete_fields = (
        'company',
        'bank_account',
        'cash_register',
        'category',
        'contact',
        'linked_transaction',
    )
    search_fields = ('description', 'company__name')
    list_filter = ('type', 'transaction_date', 'company')
    date_hierarchy = 'transaction_date'


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('description', 'company', 'status', 'amount', 'due_date', 'contact')
    autocomplete_fields = ('company', 'category', 'payment_transaction', 'contact')
    search_fields = ('description', 'company__name', 'contact__name')
    list_filter = ('status', 'due_date', 'company')
    date_hierarchy = 'due_date'


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('description', 'company', 'status', 'amount', 'due_date', 'contact')
    autocomplete_fields = ('company', 'category', 'payment_transaction', 'contact')
    search_fields = ('description', 'company__name', 'contact__name')
    list_filter = ('status', 'due_date', 'company')
    date_hierarchy = 'due_date'


@admin.register(RecurringBill)
class RecurringBillAdmin(admin.ModelAdmin):
    list_display = (
        'description',
        'company',
        'amount',
        'frequency',
        'next_due_date',
        'is_active',
    )
    autocomplete_fields = ('company', 'category')
    search_fields = ('description', 'company__name')
    list_filter = ('frequency', 'is_active', 'company')
    date_hierarchy = 'next_due_date'


@admin.register(RecurringIncome)
class RecurringIncomeAdmin(admin.ModelAdmin):
    list_display = (
        'description',
        'company',
        'amount',
        'frequency',
        'next_due_date',
        'is_active',
    )
    autocomplete_fields = ('company', 'category')
    search_fields = ('description', 'company__name')
    list_filter = ('frequency', 'is_active', 'company')
    date_hierarchy = 'next_due_date'
