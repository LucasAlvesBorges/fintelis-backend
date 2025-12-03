from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BankViewSet,
    BankAccountViewSet,
    BillViewSet,
    CashRegisterViewSet,
    CategoryViewSet,
    FinancialDataView,
    IncomeViewSet,
    PaymentMethodViewSet,
    RecurringBillViewSet,
    RecurringIncomeViewSet,
    TransactionViewSet,
)

router = DefaultRouter()
router.register('banks', BankViewSet, basename='banks')
router.register('bank-accounts', BankAccountViewSet, basename='bank-accounts')
router.register('cash-registers', CashRegisterViewSet, basename='cash-registers')
router.register('categories', CategoryViewSet, basename='categories')
router.register('payment-methods', PaymentMethodViewSet, basename='payment-methods')
router.register('transactions', TransactionViewSet, basename='transactions')
router.register('bills', BillViewSet, basename='bills')
router.register('incomes', IncomeViewSet, basename='incomes')
router.register('recurring-bills', RecurringBillViewSet, basename='recurring-bills')
router.register('recurring-incomes', RecurringIncomeViewSet, basename='recurring-incomes')

urlpatterns = [
    path('data/', FinancialDataView.as_view(), name='financial-data'),
] + router.urls
