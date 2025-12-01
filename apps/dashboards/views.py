from decimal import Decimal
from datetime import timedelta

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


def _parse_window(request):
    raw = request.query_params.get("window")
    if raw is None:
        return 30
    try:
        window = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError("window deve ser um inteiro (15, 30 ou 90).") from exc
    if window not in {15, 30, 90}:
        raise ValidationError("window deve ser um de: 15, 30 ou 90 dias.")
    return window


PROJECTION_METHODS = {"linear", "moving_average", "weighted_average"}


def _parse_method(request):
    """Parse o método de projeção do request."""
    method = request.query_params.get("method", "moving_average")
    if method not in PROJECTION_METHODS:
        raise ValidationError(
            f"method deve ser um de: {', '.join(sorted(PROJECTION_METHODS))}"
        )
    return method


def _linear_regression(y_values: list[Decimal]) -> tuple[Decimal, Decimal]:
    """
    Retorna (slope, intercept) de uma regressão linear simples sobre y_values.
    x são índices 0..n-1. Retorna Decimal para manter precisão.
    """
    n = len(y_values)
    if n < 2:
        return Decimal("0"), y_values[0] if y_values else Decimal("0")
    
    # Calcular médias usando Decimal
    mean_x = Decimal(sum(range(n))) / Decimal(n)
    mean_y = sum(y_values) / Decimal(n)
    
    # Calcular numerador e denominador
    num = sum(
        (Decimal(x) - mean_x) * (y - mean_y) 
        for x, y in zip(range(n), y_values)
    )
    den = sum((Decimal(x) - mean_x) ** 2 for x in range(n))
    
    if den == 0:
        return Decimal("0"), mean_y
    
    slope = num / den
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _moving_average(y_values: list[Decimal]) -> Decimal:
    """
    Calcula a média móvel simples dos valores.
    Retorna um valor constante para projeção estável.
    """
    if not y_values:
        return Decimal("0")
    return sum(y_values) / Decimal(len(y_values))


def _weighted_average(y_values: list[Decimal], decay: float = 0.9) -> Decimal:
    """
    Calcula a média ponderada exponencial (mais peso para dados recentes).
    decay: fator de decaimento (0.9 = 90% do peso para dados recentes)
    """
    if not y_values:
        return Decimal("0")
    
    n = len(y_values)
    weights = [Decimal(str(decay ** (n - 1 - i))) for i in range(n)]
    total_weight = sum(weights)
    
    if total_weight == 0:
        return Decimal("0")
    
    weighted_sum = sum(w * v for w, v in zip(weights, y_values))
    return weighted_sum / total_weight


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


class FinancialProjectionView(ActiveCompanyMixin, APIView):
    """
    Projeção financeira com duas linhas paralelas: realizado vs previsto.
    Ambas as linhas cobrem o mesmo período para comparação visual.
    
    Métodos de projeção disponíveis:
    - linear: regressão linear (pode ser instável com dados voláteis)
    - moving_average: média móvel simples (mais estável, padrão)
    - weighted_average: média ponderada exponencial (mais peso para dados recentes)
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get(self, request):
        company = self.get_active_company()
        window = _parse_window(request)
        method = _parse_method(request)

        today = timezone.localdate()
        # Período histórico: últimos N dias
        history_start = today - timedelta(days=window - 1)
        # Período total: histórico + projeção futura (2x window)
        end_date = today + timedelta(days=window)
        total_days = window * 2

        # Buscar transações do período histórico
        qs = Transaction.objects.filter(
            company=company,
            transaction_date__gte=history_start,
            transaction_date__lte=today,
            type__in=[Transaction.Types.RECEITA, Transaction.Types.DESPESA],
        ).annotate(
            date=TruncDate("transaction_date"),
            signed_amount=Case(
                When(type=Transaction.Types.RECEITA, then=F("amount")),
                When(type=Transaction.Types.DESPESA, then=-F("amount")),
                default=Value(Decimal("0")),
            ),
        )

        # Agregar valores diários realizados
        daily_net_map = {
            row["date"]: row["total"]
            for row in qs.values("date")
            .annotate(total=Sum("signed_amount"))
            .order_by("date")
        }

        # Coletar valores históricos para projeção
        history_dates = [history_start + timedelta(days=i) for i in range(window)]
        daily_values_history = []
        for dt in history_dates:
            net = daily_net_map.get(dt, Decimal("0"))
            daily_values_history.append(net)

        # Calcular parâmetros de projeção baseado no método escolhido
        if method == "linear":
            slope, intercept = _linear_regression(daily_values_history)
        elif method == "moving_average":
            avg_daily = _moving_average(daily_values_history)
        elif method == "weighted_average":
            avg_daily = _weighted_average(daily_values_history)

        # Construir array de dias com ambas as linhas
        days = []
        realized_cumulative = Decimal("0")
        predicted_cumulative = Decimal("0")

        for day_idx in range(total_days):
            current_date = history_start + timedelta(days=day_idx)
            is_future = current_date > today

            # Calcular valor previsto baseado no método
            if method == "linear":
                predicted_daily = intercept + slope * Decimal(day_idx)
            else:
                # moving_average e weighted_average usam valor constante
                predicted_daily = avg_daily

            predicted_daily_rounded = predicted_daily.quantize(Decimal("0.01"))
            predicted_cumulative += predicted_daily_rounded

            if is_future:
                # Dia futuro: só tem previsão, não tem realizado
                days.append({
                    "date": current_date.isoformat(),
                    "realized_daily": None,
                    "realized_cumulative": None,
                    "predicted_daily": predicted_daily_rounded,
                    "predicted_cumulative": predicted_cumulative.quantize(Decimal("0.01")),
                })
            else:
                # Dia passado ou hoje: tem realizado e previsão
                realized_daily = daily_net_map.get(current_date, Decimal("0"))
                realized_cumulative += realized_daily

                days.append({
                    "date": current_date.isoformat(),
                    "realized_daily": realized_daily.quantize(Decimal("0.01")),
                    "realized_cumulative": realized_cumulative.quantize(Decimal("0.01")),
                    "predicted_daily": predicted_daily_rounded,
                    "predicted_cumulative": predicted_cumulative.quantize(Decimal("0.01")),
                })

        payload = {
            "currency": "BRL",
            "window_days": window,
            "method": method,
            "start_date": history_start.isoformat(),
            "end_date": end_date.isoformat(),
            "today": today.isoformat(),
            "total_days": total_days,
            "days": days,
        }
        return Response(payload)
