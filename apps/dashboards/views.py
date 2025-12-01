from decimal import Decimal

from django.core.cache import cache
from django.db.models import Case, CharField, F, Sum, Value, When
from django.db.models.functions import Coalesce, ExtractDay, TruncDate
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.financials.mixins import ActiveCompanyMixin
from apps.financials.models import (
    Bill,
    Income,
    RecurringBillPayment,
    RecurringIncomeReceipt,
    Transaction,
)
from apps.financials.permissions import IsCompanyMember


MONTH_NAMES_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}


# TTL curto para dashboards, evita custo de reprocessar filtros em cada hit.
CACHE_TIMEOUT = 900  # 15 minutos


def _parse_month_year(request):
    """
    Resolve month/year from query params, defaulting to the current month/year.
    """
    today = timezone.localdate()
    month = request.query_params.get("month") or today.month
    year = request.query_params.get("year") or today.year
    try:
        month = int(month)
        year = int(year)
    except (TypeError, ValueError) as exc:
        raise ValidationError("month e year devem ser inteiros.") from exc
    if month < 1 or month > 12:
        raise ValidationError("month deve estar entre 1 e 12.")
    return month, year


def _sum_amount(qs):
    total = qs.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


class ExpenseBreakdownView(ActiveCompanyMixin, APIView):
    """
    Agrupa despesas por categoria pai para o gráfico de pizza.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get(self, request):
        company = self.get_active_company()
        month, year = _parse_month_year(request)

        cache_key = f"dashboard:expenses:{company.id}:{year}:{month}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        expenses = Transaction.objects.filter(
            company=company,
            type=Transaction.Types.DESPESA,
            transaction_date__year=year,
            transaction_date__month=month,
        )

        total_expenses = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")

        breakdown = (
            expenses.annotate(
                parent_id=Coalesce("category__parent_id", "category_id"),
                parent_name=Case(
                    When(category__isnull=True, then=Value("Sem categoria")),
                    When(category__parent__isnull=False, then=F("category__parent__name")),
                    default=F("category__name"),
                    output_field=CharField(),
                ),
            )
            .values("parent_id", "parent_name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        categories = []
        for row in breakdown:
            amount = row["total"] or Decimal("0")
            percentage = (
                float((amount / total_expenses) * Decimal("100"))
                if total_expenses
                else 0.0
            )
            categories.append(
                {
                    "category_id": str(row["parent_id"]) if row["parent_id"] else None,
                    "category_name": row["parent_name"],
                    "amount": amount,
                    "percentage": round(percentage, 2),
                }
            )

        payload = {
            "currency": "BRL",
            "year": year,
            "month": month,
            "total_expenses": total_expenses,
            "categories": categories,
        }
        cache.set(cache_key, payload, CACHE_TIMEOUT)
        return Response(payload)


class RevenueByDayView(ActiveCompanyMixin, APIView):
    """
    Soma receitas por dia dentro do mês para o gráfico de barras.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get(self, request):
        company = self.get_active_company()
        month, year = _parse_month_year(request)

        cache_key = f"dashboard:revenues:{company.id}:{year}:{month}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        revenues = Transaction.objects.filter(
            company=company,
            type=Transaction.Types.RECEITA,
            transaction_date__year=year,
            transaction_date__month=month,
        )

        totals = (
            revenues.annotate(
                date=TruncDate("transaction_date"),
                day=ExtractDay("transaction_date"),
            )
            .values("date", "day")
            .annotate(total=Sum("amount"))
            .order_by("day")
        )

        days = []
        for row in totals:
            amount = row["total"] or Decimal("0")
            label = ""
            if row["date"]:
                month_name = MONTH_NAMES_PT.get(row["date"].month, "")
                label = f"{row['day']:02d} {month_name}".strip()
            days.append(
                {
                    "date": row["date"].isoformat(),
                    "day": row["day"],
                    "label": label,
                    "amount": amount,
                }
            )

        total_revenue = revenues.aggregate(total=Sum("amount"))["total"] or Decimal("0")

        payload = {
            "currency": "BRL",
            "year": year,
            "month": month,
            "total_revenue": total_revenue,
            "days": days,
        }
        cache.set(cache_key, payload, CACHE_TIMEOUT)
        return Response(payload)


class FinancialHealthSummaryView(ActiveCompanyMixin, APIView):
    
    """
    Valores agregados para contas a receber/pagar (atrasos e em aberto).
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get(self, request):
        company = self.get_active_company()
        today = timezone.localdate()
        month = today.month
        year = today.year

        receipts_pending = RecurringIncomeReceipt.objects.filter(
            company=company, status=RecurringIncomeReceipt.Status.PENDENTE
        )
        receipts_pending_dates = set(
            receipts_pending.values_list("due_date", flat=True)
        )
        incomes_pending = (
            Income.objects.filter(company=company, status=Income.Status.PENDENTE)
            .exclude(due_date__in=receipts_pending_dates)
        )

        receivables_overdue = _sum_amount(
            incomes_pending.filter(due_date__lt=today)
        ) + _sum_amount(receipts_pending.filter(due_date__lt=today))

        receivables_open = _sum_amount(incomes_pending) + _sum_amount(
            receipts_pending
        )

        receivables_open_month = _sum_amount(
            incomes_pending.filter(due_date__year=year, due_date__month=month)
        ) + _sum_amount(
            receipts_pending.filter(due_date__year=year, due_date__month=month)
        )

        recurring_bills_pending = RecurringBillPayment.objects.filter(
            company=company, status=RecurringBillPayment.Status.PENDENTE
        )
        recurring_bills_dates = set(
            recurring_bills_pending.values_list("due_date", flat=True)
        )
        bills_pending = (
            Bill.objects.filter(company=company, status=Bill.Status.A_VENCER)
            .exclude(due_date__in=recurring_bills_dates)
        )

        payables_overdue = _sum_amount(
            bills_pending.filter(due_date__lt=today)
        ) + _sum_amount(
            recurring_bills_pending.filter(due_date__lt=today)
        )

        payload = {
            "currency": "BRL",
            "year": year,
            "month": month,
            "receivables_overdue": receivables_overdue,
            "receivables_open": receivables_open,
            "receivables_open_current_month": receivables_open_month,
            "payables_overdue": payables_overdue,
        }
        return Response(payload)
