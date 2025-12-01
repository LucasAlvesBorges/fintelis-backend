from django.urls import path

from .views import (
    DREReportView,
    ExpensesByCategoryReportView,
    PayablesReportView,
    ReceivablesReportView,
    RevenuesByDayReportView,
    TransactionsReportView,
)

urlpatterns = [
    path(
        "expenses/by-category/",
        ExpensesByCategoryReportView.as_view(),
        name="report-expenses-by-category",
    ),
    path(
        "revenues/by-day/",
        RevenuesByDayReportView.as_view(),
        name="report-revenues-by-day",
    ),
    path(
        "receivables/",
        ReceivablesReportView.as_view(),
        name="report-receivables",
    ),
    path(
        "payables/",
        PayablesReportView.as_view(),
        name="report-payables",
    ),
    path(
        "transactions/",
        TransactionsReportView.as_view(),
        name="report-transactions",
    ),
    path(
        "dre/",
        DREReportView.as_view(),
        name="report-dre",
    ),
]

