from django.contrib import admin

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


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'type', 'initial_balance', 'current_balance', 'created_at')
    search_fields = ('name', 'company__name')
    list_filter = ('type', 'company')
    ordering = ('company__name', 'name')


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'default_bank_account', 'created_at')
    search_fields = ('name', 'company__name')
    list_filter = ('company',)
    ordering = ('company__name', 'name')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'type', 'created_at')
    search_fields = ('name', 'company__name')
    list_filter = ('type', 'company')
    ordering = ('company__name', 'name')


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
        'linked_transaction',
    )
    autocomplete_fields = (
        'company',
        'bank_account',
        'cash_register',
        'category',
        'linked_transaction',
    )
    search_fields = ('description', 'company__name')
    list_filter = ('type', 'transaction_date', 'company')
    date_hierarchy = 'transaction_date'


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('description', 'company', 'status', 'amount', 'due_date')
    autocomplete_fields = ('company', 'category', 'payment_transaction')
    search_fields = ('description', 'company__name')
    list_filter = ('status', 'due_date', 'company')
    date_hierarchy = 'due_date'


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('description', 'company', 'status', 'amount', 'due_date')
    autocomplete_fields = ('company', 'category', 'payment_transaction')
    search_fields = ('description', 'company__name')
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
