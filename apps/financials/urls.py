from rest_framework.routers import DefaultRouter

from .views import (
    BankAccountViewSet,
    BillViewSet,
    CashRegisterViewSet,
    CategoryViewSet,
    IncomeViewSet,
    RecurringBillViewSet,
    RecurringIncomeViewSet,
    TransactionViewSet,
)

router = DefaultRouter()
router.register('bank-accounts', BankAccountViewSet, basename='bank-accounts')
router.register('cash-registers', CashRegisterViewSet, basename='cash-registers')
router.register('categories', CategoryViewSet, basename='categories')
router.register('transactions', TransactionViewSet, basename='transactions')
router.register('bills', BillViewSet, basename='bills')
router.register('incomes', IncomeViewSet, basename='incomes')
router.register('recurring-bills', RecurringBillViewSet, basename='recurring-bills')
router.register('recurring-incomes', RecurringIncomeViewSet, basename='recurring-incomes')

urlpatterns = router.urls
