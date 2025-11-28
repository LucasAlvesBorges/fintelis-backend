from django.urls import path

from .views import ExpenseBreakdownView, RevenueByDayView

urlpatterns = [
    path(
        "expenses/by-category/",
        ExpenseBreakdownView.as_view(),
        name="dashboard-expenses-by-category",
    ),
    path(
        "revenues/by-day/",
        RevenueByDayView.as_view(),
        name="dashboard-revenues-by-day",
    ),
]
