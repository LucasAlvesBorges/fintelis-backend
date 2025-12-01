from decimal import Decimal
from datetime import timedelta
from collections import defaultdict

from django.db.models import Case, CharField, F, Sum, Value, When
from django.db.models.functions import Coalesce, ExtractMonth, TruncDate
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.financials.mixins import ActiveCompanyMixin
from apps.financials.models import (
    Bill,
    Category,
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


class ReportPagination(PageNumberPagination):
    """Paginação padrão para relatórios: 10 itens por página."""
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def _parse_month_year(request):
    """Resolve month/year from query params, defaulting to the current month/year."""
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
    """Soma o campo amount de um queryset."""
    total = qs.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


class ExpensesByCategoryReportView(ActiveCompanyMixin, APIView):
    """
    Relatório detalhado de despesas por categoria.
    Retorna as transações de despesa com dados tabelados e paginados.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    pagination_class = ReportPagination

    def get(self, request):
        company = self.get_active_company()
        month, year = _parse_month_year(request)

        # Filtrar transações de despesa do período
        expenses_qs = Transaction.objects.filter(
            company=company,
            type=Transaction.Types.DESPESA,
            transaction_date__year=year,
            transaction_date__month=month,
        ).select_related("category", "category__parent", "contact", "bank_account", "cash_register")

        # Calcular totais ANTES da paginação
        total_expenses = expenses_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_records = expenses_qs.count()

        # Agrupar por categoria para resumo
        categories_summary = (
            expenses_qs.annotate(
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
        for row in categories_summary:
            amount = row["total"] or Decimal("0")
            percentage = (
                float((amount / total_expenses) * Decimal("100"))
                if total_expenses
                else 0.0
            )
            categories.append({
                "category_id": str(row["parent_id"]) if row["parent_id"] else None,
                "category_name": row["parent_name"],
                "amount": amount,
                "percentage": round(percentage, 2),
            })

        # Paginar os itens detalhados
        paginator = self.pagination_class()
        expenses_ordered = expenses_qs.order_by("-transaction_date", "-created_at")
        page = paginator.paginate_queryset(expenses_ordered, request, view=self)

        items = []
        for tx in page:
            items.append({
                "id": str(tx.id),
                "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
                "description": tx.description,
                "amount": tx.amount,
                "category_id": str(tx.category_id) if tx.category_id else None,
                "category_name": tx.category.name if tx.category else "Sem categoria",
                "parent_category_name": tx.category.parent.name if tx.category and tx.category.parent else None,
                "contact_id": str(tx.contact_id) if tx.contact_id else None,
                "contact_name": tx.contact.name if tx.contact else None,
                "bank_account_name": tx.bank_account.name if tx.bank_account else None,
                "cash_register_name": tx.cash_register.name if tx.cash_register else None,
            })

        return Response({
            "currency": "BRL",
            "year": year,
            "month": month,
            "month_name": MONTH_NAMES_PT.get(month, ""),
            "summary": {
                "total_expenses": total_expenses,
                "total_records": total_records,
                "categories": categories,
            },
            "pagination": {
                "page": paginator.page.number,
                "page_size": paginator.page_size,
                "total_pages": paginator.page.paginator.num_pages,
                "total_items": total_records,
                "has_next": paginator.page.has_next(),
                "has_previous": paginator.page.has_previous(),
            },
            "items": items,
        })


class RevenuesByDayReportView(ActiveCompanyMixin, APIView):
    """
    Relatório detalhado de receitas por dia.
    Retorna as transações de receita com dados tabelados e paginados.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    pagination_class = ReportPagination

    def get(self, request):
        company = self.get_active_company()
        month, year = _parse_month_year(request)

        # Filtrar transações de receita do período
        revenues_qs = Transaction.objects.filter(
            company=company,
            type=Transaction.Types.RECEITA,
            transaction_date__year=year,
            transaction_date__month=month,
        ).select_related("category", "category__parent", "contact", "bank_account", "cash_register")

        # Calcular totais ANTES da paginação
        total_revenue = revenues_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_records = revenues_qs.count()

        # Agrupar por dia para resumo
        days_summary = (
            revenues_qs.annotate(date=TruncDate("transaction_date"))
            .values("date")
            .annotate(total=Sum("amount"))
            .order_by("date")
        )

        days = []
        for row in days_summary:
            if row["date"]:
                days.append({
                    "date": row["date"].isoformat(),
                    "day": row["date"].day,
                    "label": f"{row['date'].day:02d} {MONTH_NAMES_PT.get(row['date'].month, '')}",
                    "amount": row["total"] or Decimal("0"),
                })

        # Paginar os itens detalhados
        paginator = self.pagination_class()
        revenues_ordered = revenues_qs.order_by("-transaction_date", "-created_at")
        page = paginator.paginate_queryset(revenues_ordered, request, view=self)

        items = []
        for tx in page:
            items.append({
                "id": str(tx.id),
                "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
                "description": tx.description,
                "amount": tx.amount,
                "category_id": str(tx.category_id) if tx.category_id else None,
                "category_name": tx.category.name if tx.category else "Sem categoria",
                "contact_id": str(tx.contact_id) if tx.contact_id else None,
                "contact_name": tx.contact.name if tx.contact else None,
                "bank_account_name": tx.bank_account.name if tx.bank_account else None,
                "cash_register_name": tx.cash_register.name if tx.cash_register else None,
            })

        return Response({
            "currency": "BRL",
            "year": year,
            "month": month,
            "month_name": MONTH_NAMES_PT.get(month, ""),
            "summary": {
                "total_revenue": total_revenue,
                "total_records": total_records,
                "days": days,
            },
            "pagination": {
                "page": paginator.page.number,
                "page_size": paginator.page_size,
                "total_pages": paginator.page.paginator.num_pages,
                "total_items": total_records,
                "has_next": paginator.page.has_next(),
                "has_previous": paginator.page.has_previous(),
            },
            "items": items,
        })


class ReceivablesReportView(ActiveCompanyMixin, APIView):
    """
    Relatório detalhado de contas a receber.
    Inclui Income e RecurringIncomeReceipt pendentes.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    pagination_class = ReportPagination

    def get(self, request):
        company = self.get_active_company()
        today = timezone.localdate()
        month = today.month
        year = today.year

        # Filtro opcional por status
        status_filter = request.query_params.get("status")  # overdue, open, current_month

        # Income pendentes
        incomes_pending = Income.objects.filter(
            company=company, status=Income.Status.PENDENTE
        ).select_related("category", "contact")

        # RecurringIncomeReceipt pendentes
        receipts_pending = RecurringIncomeReceipt.objects.filter(
            company=company, status=RecurringIncomeReceipt.Status.PENDENTE
        ).select_related("recurring_income", "recurring_income__category")

        # Evitar duplicatas
        receipts_pending_dates = set(receipts_pending.values_list("due_date", flat=True))
        incomes_pending = incomes_pending.exclude(due_date__in=receipts_pending_dates)

        # Calcular totais ANTES de aplicar filtros de status
        total_overdue = (
            _sum_amount(incomes_pending.filter(due_date__lt=today)) +
            _sum_amount(receipts_pending.filter(due_date__lt=today))
        )
        total_open = _sum_amount(incomes_pending) + _sum_amount(receipts_pending)
        total_current_month = (
            _sum_amount(incomes_pending.filter(due_date__year=year, due_date__month=month)) +
            _sum_amount(receipts_pending.filter(due_date__year=year, due_date__month=month))
        )

        # Aplicar filtro de status se especificado
        if status_filter == "overdue":
            incomes_pending = incomes_pending.filter(due_date__lt=today)
            receipts_pending = receipts_pending.filter(due_date__lt=today)
        elif status_filter == "current_month":
            incomes_pending = incomes_pending.filter(due_date__year=year, due_date__month=month)
            receipts_pending = receipts_pending.filter(due_date__year=year, due_date__month=month)

        # Combinar e ordenar os itens
        items_list = []

        for income in incomes_pending:
            items_list.append({
                "id": str(income.id),
                "type": "income",
                "description": income.description,
                "amount": income.amount,
                "due_date": income.due_date.isoformat() if income.due_date else None,
                "is_overdue": income.due_date < today if income.due_date else False,
                "category_name": income.category.name if income.category else None,
                "contact_name": income.contact.name if income.contact else None,
                "status": income.status,
            })

        for receipt in receipts_pending:
            items_list.append({
                "id": str(receipt.id),
                "type": "recurring_income_receipt",
                "description": receipt.recurring_income.description if receipt.recurring_income else None,
                "amount": receipt.amount,
                "due_date": receipt.due_date.isoformat() if receipt.due_date else None,
                "is_overdue": receipt.due_date < today if receipt.due_date else False,
                "category_name": receipt.recurring_income.category.name if receipt.recurring_income and receipt.recurring_income.category else None,
                "contact_name": None,  # RecurringIncome não tem contact
                "status": receipt.status,
            })

        # Ordenar por due_date
        items_list.sort(key=lambda x: x["due_date"] or "9999-99-99")
        total_records = len(items_list)

        # Paginação manual
        paginator = self.pagination_class()
        page_number = int(request.query_params.get("page", 1))
        page_size = paginator.page_size
        start_idx = (page_number - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items_list[start_idx:end_idx]
        total_pages = (total_records + page_size - 1) // page_size if total_records > 0 else 1

        return Response({
            "currency": "BRL",
            "year": year,
            "month": month,
            "filter": status_filter or "all",
            "summary": {
                "receivables_overdue": total_overdue,
                "receivables_open": total_open,
                "receivables_open_current_month": total_current_month,
            },
            "pagination": {
                "page": page_number,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_items": total_records,
                "has_next": page_number < total_pages,
                "has_previous": page_number > 1,
            },
            "items": page_items,
        })


class PayablesReportView(ActiveCompanyMixin, APIView):
    """
    Relatório detalhado de contas a pagar.
    Inclui Bill e RecurringBillPayment pendentes.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    pagination_class = ReportPagination

    def get(self, request):
        company = self.get_active_company()
        today = timezone.localdate()
        month = today.month
        year = today.year

        # Filtro opcional por status
        status_filter = request.query_params.get("status")  # overdue, open, current_month

        # Bill pendentes
        bills_pending = Bill.objects.filter(
            company=company, status=Bill.Status.A_VENCER
        ).select_related("category", "contact")

        # RecurringBillPayment pendentes
        recurring_bills_pending = RecurringBillPayment.objects.filter(
            company=company, status=RecurringBillPayment.Status.PENDENTE
        ).select_related("recurring_bill", "recurring_bill__category")

        # Evitar duplicatas
        recurring_bills_dates = set(recurring_bills_pending.values_list("due_date", flat=True))
        bills_pending = bills_pending.exclude(due_date__in=recurring_bills_dates)

        # Calcular totais ANTES de aplicar filtros de status
        total_overdue = (
            _sum_amount(bills_pending.filter(due_date__lt=today)) +
            _sum_amount(recurring_bills_pending.filter(due_date__lt=today))
        )
        total_open = _sum_amount(bills_pending) + _sum_amount(recurring_bills_pending)
        total_current_month = (
            _sum_amount(bills_pending.filter(due_date__year=year, due_date__month=month)) +
            _sum_amount(recurring_bills_pending.filter(due_date__year=year, due_date__month=month))
        )

        # Aplicar filtro de status se especificado
        if status_filter == "overdue":
            bills_pending = bills_pending.filter(due_date__lt=today)
            recurring_bills_pending = recurring_bills_pending.filter(due_date__lt=today)
        elif status_filter == "current_month":
            bills_pending = bills_pending.filter(due_date__year=year, due_date__month=month)
            recurring_bills_pending = recurring_bills_pending.filter(due_date__year=year, due_date__month=month)

        # Combinar e ordenar os itens
        items_list = []

        for bill in bills_pending:
            items_list.append({
                "id": str(bill.id),
                "type": "bill",
                "description": bill.description,
                "amount": bill.amount,
                "due_date": bill.due_date.isoformat() if bill.due_date else None,
                "is_overdue": bill.due_date < today if bill.due_date else False,
                "category_name": bill.category.name if bill.category else None,
                "contact_name": bill.contact.name if bill.contact else None,
                "status": bill.status,
            })

        for payment in recurring_bills_pending:
            items_list.append({
                "id": str(payment.id),
                "type": "recurring_bill_payment",
                "description": payment.recurring_bill.description if payment.recurring_bill else None,
                "amount": payment.amount,
                "due_date": payment.due_date.isoformat() if payment.due_date else None,
                "is_overdue": payment.due_date < today if payment.due_date else False,
                "category_name": payment.recurring_bill.category.name if payment.recurring_bill and payment.recurring_bill.category else None,
                "contact_name": None,  # RecurringBill não tem contact
                "status": payment.status,
            })

        # Ordenar por due_date
        items_list.sort(key=lambda x: x["due_date"] or "9999-99-99")
        total_records = len(items_list)

        # Paginação manual
        paginator = self.pagination_class()
        page_number = int(request.query_params.get("page", 1))
        page_size = paginator.page_size
        start_idx = (page_number - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items_list[start_idx:end_idx]
        total_pages = (total_records + page_size - 1) // page_size if total_records > 0 else 1

        return Response({
            "currency": "BRL",
            "year": year,
            "month": month,
            "filter": status_filter or "all",
            "summary": {
                "payables_overdue": total_overdue,
                "payables_open": total_open,
                "payables_open_current_month": total_current_month,
            },
            "pagination": {
                "page": page_number,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_items": total_records,
                "has_next": page_number < total_pages,
                "has_previous": page_number > 1,
            },
            "items": page_items,
        })


class TransactionsReportView(ActiveCompanyMixin, APIView):
    """
    Relatório detalhado de todas as transações (receitas e despesas).
    Usado para visualizar os dados da projeção financeira.
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    pagination_class = ReportPagination

    def get(self, request):
        company = self.get_active_company()

        # Parse window (15, 30 ou 90 dias)
        raw_window = request.query_params.get("window")
        window = 30
        if raw_window:
            try:
                window = int(raw_window)
                if window not in {15, 30, 90}:
                    window = 30
            except (TypeError, ValueError):
                window = 30

        # Filtro por tipo
        type_filter = request.query_params.get("type")  # receita, despesa

        today = timezone.localdate()
        start_date = today - timedelta(days=window - 1)

        # Filtrar transações do período
        transactions_qs = Transaction.objects.filter(
            company=company,
            transaction_date__gte=start_date,
            transaction_date__lte=today,
            type__in=[Transaction.Types.RECEITA, Transaction.Types.DESPESA],
        ).select_related("category", "category__parent", "contact", "bank_account", "cash_register")

        # Aplicar filtro de tipo
        if type_filter == "receita":
            transactions_qs = transactions_qs.filter(type=Transaction.Types.RECEITA)
        elif type_filter == "despesa":
            transactions_qs = transactions_qs.filter(type=Transaction.Types.DESPESA)

        # Calcular totais ANTES da paginação
        totals = transactions_qs.aggregate(
            total_receitas=Sum(
                Case(
                    When(type=Transaction.Types.RECEITA, then=F("amount")),
                    default=Value(Decimal("0")),
                )
            ),
            total_despesas=Sum(
                Case(
                    When(type=Transaction.Types.DESPESA, then=F("amount")),
                    default=Value(Decimal("0")),
                )
            ),
        )

        total_receitas = totals["total_receitas"] or Decimal("0")
        total_despesas = totals["total_despesas"] or Decimal("0")
        saldo_liquido = total_receitas - total_despesas
        total_records = transactions_qs.count()

        # Paginar os itens
        paginator = self.pagination_class()
        transactions_ordered = transactions_qs.order_by("-transaction_date", "-created_at")
        page = paginator.paginate_queryset(transactions_ordered, request, view=self)

        items = []
        for tx in page:
            items.append({
                "id": str(tx.id),
                "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
                "type": tx.type,
                "type_display": "Receita" if tx.type == Transaction.Types.RECEITA else "Despesa",
                "description": tx.description,
                "amount": tx.amount,
                "signed_amount": tx.amount if tx.type == Transaction.Types.RECEITA else -tx.amount,
                "category_id": str(tx.category_id) if tx.category_id else None,
                "category_name": tx.category.name if tx.category else "Sem categoria",
                "parent_category_name": tx.category.parent.name if tx.category and tx.category.parent else None,
                "contact_id": str(tx.contact_id) if tx.contact_id else None,
                "contact_name": tx.contact.name if tx.contact else None,
                "bank_account_name": tx.bank_account.name if tx.bank_account else None,
                "cash_register_name": tx.cash_register.name if tx.cash_register else None,
            })

        return Response({
            "currency": "BRL",
            "window_days": window,
            "start_date": start_date.isoformat(),
            "end_date": today.isoformat(),
            "filter": type_filter or "all",
            "summary": {
                "total_receitas": total_receitas,
                "total_despesas": total_despesas,
                "saldo_liquido": saldo_liquido,
                "total_records": total_records,
            },
            "pagination": {
                "page": paginator.page.number,
                "page_size": paginator.page_size,
                "total_pages": paginator.page.paginator.num_pages,
                "total_items": total_records,
                "has_next": paginator.page.has_next(),
                "has_previous": paginator.page.has_previous(),
            },
            "items": items,
        })


class DREReportView(ActiveCompanyMixin, APIView):
    """
    Demonstrativo de Resultado do Exercício (DRE).
    Agrega transações por categoria hierárquica e mês.
    
    Estrutura:
    - (+) Receita Bruta
    - (-) Deduções Sobre Vendas
    - (=) Receita Líquida
    - (-) Custos Variáveis
    - (=) Margem de Contribuição
    - (-) Custos Fixos
    - (=) Resultado Operacional
    """

    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get(self, request):
        company = self.get_active_company()
        
        # Ano do relatório (padrão: ano atual)
        year = request.query_params.get("year")
        if year:
            try:
                year = int(year)
            except (TypeError, ValueError):
                raise ValidationError("year deve ser um inteiro.")
        else:
            year = timezone.localdate().year

        # Buscar todas as categorias da empresa organizadas hierarquicamente
        all_categories = Category.objects.filter(company=company).order_by("code")
        
        # Mapear categorias
        categories_map = {cat.id: cat for cat in all_categories}
        
        # Separar categorias raiz (sem pai)
        root_categories = [cat for cat in all_categories if cat.parent_id is None]
        
        # Buscar transações do ano agrupadas por categoria e mês
        transactions_by_category_month = (
            Transaction.objects.filter(
                company=company,
                transaction_date__year=year,
            )
            .values("category_id", "type")
            .annotate(
                month=ExtractMonth("transaction_date"),
                total=Sum("amount"),
            )
            .order_by("category_id", "month")
        )

        # Criar dicionário de totais: {category_id: {month: amount}}
        category_month_totals = defaultdict(lambda: defaultdict(Decimal))
        for row in transactions_by_category_month:
            cat_id = row["category_id"]
            month = row["month"]
            amount = row["total"] or Decimal("0")
            category_month_totals[cat_id][month] = amount

        # Função para calcular totais de uma categoria (incluindo filhos)
        def get_category_totals(category_id):
            totals = defaultdict(Decimal)
            
            # Adicionar totais diretos da categoria
            if category_id in category_month_totals:
                for month, amount in category_month_totals[category_id].items():
                    totals[month] += amount
            
            # Adicionar totais dos filhos
            for cat in all_categories:
                if cat.parent_id == category_id:
                    child_totals = get_category_totals(cat.id)
                    for month, amount in child_totals.items():
                        totals[month] += amount
            
            return totals

        # Função para construir linha do DRE
        def build_row(code, name, category_id=None, row_type="category", indent=0, sign="+"):
            monthly = {}
            yearly_total = Decimal("0")
            
            if category_id:
                totals = get_category_totals(category_id)
                for month in range(1, 13):
                    amount = totals.get(month, Decimal("0"))
                    monthly[month] = amount
                    yearly_total += amount
            
            return {
                "code": code,
                "name": name,
                "row_type": row_type,  # category, subcategory, subtotal, total
                "indent": indent,
                "sign": sign,  # +, -, =
                "monthly": monthly,
                "yearly_total": yearly_total,
                "av_percent": None,  # Será calculado depois
            }

        # Construir estrutura do DRE
        rows = []
        
        # Separar receitas e despesas
        revenue_categories = [cat for cat in root_categories if cat.type == Category.Types.RECEITA]
        expense_categories = [cat for cat in root_categories if cat.type == Category.Types.DESPESA]

        # (+) RECEITA BRUTA
        receita_bruta_row = build_row(None, "Receita Bruta", row_type="subtotal", sign="+")
        receita_bruta_totals = defaultdict(Decimal)
        
        for cat in revenue_categories:
            # Adicionar categoria pai
            cat_totals = get_category_totals(cat.id)
            row = build_row(cat.code, cat.name, cat.id, row_type="category", indent=1)
            rows.append(row)
            
            # Somar para receita bruta
            for month, amount in cat_totals.items():
                receita_bruta_totals[month] += amount
            
            # Adicionar subcategorias
            subcategories = [c for c in all_categories if c.parent_id == cat.id]
            for subcat in subcategories:
                sub_row = build_row(subcat.code, subcat.name, subcat.id, row_type="subcategory", indent=2)
                rows.append(sub_row)

        # Atualizar receita bruta
        for month in range(1, 13):
            receita_bruta_row["monthly"][month] = receita_bruta_totals.get(month, Decimal("0"))
        receita_bruta_row["yearly_total"] = sum(receita_bruta_totals.values())
        
        # Inserir linha de receita bruta no início
        rows.insert(0, receita_bruta_row)

        # Posição para inserir deduções (após receitas)
        deduction_insert_pos = len(rows)

        # (-) DEDUÇÕES SOBRE VENDAS (categorias de despesa que são deduções)
        # Por convenção, categorias com "deduc" ou "imposto" no nome são deduções
        deducoes_row = build_row(None, "Deduções Sobre Vendas", row_type="subtotal", sign="-")
        deducoes_totals = defaultdict(Decimal)
        deducoes_categories = []
        
        for cat in expense_categories:
            cat_name_lower = cat.name.lower()
            if "deduc" in cat_name_lower or "imposto" in cat_name_lower:
                deducoes_categories.append(cat)
                cat_totals = get_category_totals(cat.id)
                for month, amount in cat_totals.items():
                    deducoes_totals[month] += amount

        for month in range(1, 13):
            deducoes_row["monthly"][month] = deducoes_totals.get(month, Decimal("0"))
        deducoes_row["yearly_total"] = sum(deducoes_totals.values())
        
        rows.insert(deduction_insert_pos, deducoes_row)
        
        # Adicionar categorias de deduções
        for cat in deducoes_categories:
            row = build_row(cat.code, cat.name, cat.id, row_type="category", indent=1)
            deduction_insert_pos += 1
            rows.insert(deduction_insert_pos, row)

        # (=) RECEITA LÍQUIDA
        receita_liquida_row = build_row(None, "Receita Líquida", row_type="total", sign="=")
        for month in range(1, 13):
            receita_liquida_row["monthly"][month] = (
                receita_bruta_row["monthly"].get(month, Decimal("0")) -
                deducoes_row["monthly"].get(month, Decimal("0"))
            )
        receita_liquida_row["yearly_total"] = receita_bruta_row["yearly_total"] - deducoes_row["yearly_total"]
        rows.append(receita_liquida_row)

        # (-) CUSTOS VARIÁVEIS (categorias com "variáv" no nome)
        custos_variaveis_row = build_row(None, "Custos Variáveis", row_type="subtotal", sign="-")
        custos_variaveis_totals = defaultdict(Decimal)
        custos_variaveis_categories = []
        
        for cat in expense_categories:
            cat_name_lower = cat.name.lower()
            if "variáv" in cat_name_lower or "variav" in cat_name_lower:
                custos_variaveis_categories.append(cat)
                cat_totals = get_category_totals(cat.id)
                for month, amount in cat_totals.items():
                    custos_variaveis_totals[month] += amount

        for month in range(1, 13):
            custos_variaveis_row["monthly"][month] = custos_variaveis_totals.get(month, Decimal("0"))
        custos_variaveis_row["yearly_total"] = sum(custos_variaveis_totals.values())
        rows.append(custos_variaveis_row)
        
        # Adicionar categorias de custos variáveis
        for cat in custos_variaveis_categories:
            row = build_row(cat.code, cat.name, cat.id, row_type="category", indent=1)
            rows.append(row)
            # Subcategorias
            subcategories = [c for c in all_categories if c.parent_id == cat.id]
            for subcat in subcategories:
                sub_row = build_row(subcat.code, subcat.name, subcat.id, row_type="subcategory", indent=2)
                rows.append(sub_row)

        # (=) MARGEM DE CONTRIBUIÇÃO
        margem_contribuicao_row = build_row(None, "Margem de Contribuição", row_type="total", sign="=")
        for month in range(1, 13):
            margem_contribuicao_row["monthly"][month] = (
                receita_liquida_row["monthly"].get(month, Decimal("0")) -
                custos_variaveis_row["monthly"].get(month, Decimal("0"))
            )
        margem_contribuicao_row["yearly_total"] = (
            receita_liquida_row["yearly_total"] - custos_variaveis_row["yearly_total"]
        )
        rows.append(margem_contribuicao_row)

        # (=) % MARGEM DE CONTRIBUIÇÃO
        margem_percent_row = build_row(None, "% Margem de Contribuição", row_type="percent", sign="=")
        for month in range(1, 13):
            receita = receita_bruta_row["monthly"].get(month, Decimal("0"))
            margem = margem_contribuicao_row["monthly"].get(month, Decimal("0"))
            if receita > 0:
                margem_percent_row["monthly"][month] = round(float(margem / receita * 100), 2)
            else:
                margem_percent_row["monthly"][month] = 0
        
        if receita_bruta_row["yearly_total"] > 0:
            margem_percent_row["yearly_total"] = round(
                float(margem_contribuicao_row["yearly_total"] / receita_bruta_row["yearly_total"] * 100), 2
            )
        else:
            margem_percent_row["yearly_total"] = 0
        rows.append(margem_percent_row)

        # (-) CUSTOS FIXOS (todas as despesas que não são deduções nem custos variáveis)
        custos_fixos_row = build_row(None, "Custos Fixos", row_type="subtotal", sign="-")
        custos_fixos_totals = defaultdict(Decimal)
        custos_fixos_categories = []
        
        excluded_ids = {cat.id for cat in deducoes_categories + custos_variaveis_categories}
        
        for cat in expense_categories:
            if cat.id not in excluded_ids:
                custos_fixos_categories.append(cat)
                cat_totals = get_category_totals(cat.id)
                for month, amount in cat_totals.items():
                    custos_fixos_totals[month] += amount

        for month in range(1, 13):
            custos_fixos_row["monthly"][month] = custos_fixos_totals.get(month, Decimal("0"))
        custos_fixos_row["yearly_total"] = sum(custos_fixos_totals.values())
        rows.append(custos_fixos_row)
        
        # Adicionar categorias de custos fixos
        for cat in custos_fixos_categories:
            row = build_row(cat.code, cat.name, cat.id, row_type="category", indent=1)
            rows.append(row)
            # Subcategorias
            subcategories = [c for c in all_categories if c.parent_id == cat.id]
            for subcat in subcategories:
                sub_row = build_row(subcat.code, subcat.name, subcat.id, row_type="subcategory", indent=2)
                rows.append(sub_row)

        # (=) RESULTADO OPERACIONAL
        resultado_operacional_row = build_row(None, "Resultado Operacional", row_type="total", sign="=")
        for month in range(1, 13):
            resultado_operacional_row["monthly"][month] = (
                margem_contribuicao_row["monthly"].get(month, Decimal("0")) -
                custos_fixos_row["monthly"].get(month, Decimal("0"))
            )
        resultado_operacional_row["yearly_total"] = (
            margem_contribuicao_row["yearly_total"] - custos_fixos_row["yearly_total"]
        )
        rows.append(resultado_operacional_row)

        # Calcular AV% (Análise Vertical) - percentual em relação à receita bruta
        for row in rows:
            if row["row_type"] != "percent" and receita_bruta_row["yearly_total"] > 0:
                row["av_percent"] = round(
                    float(row["yearly_total"] / receita_bruta_row["yearly_total"] * 100), 2
                )

        # Converter monthly para lista ordenada
        for row in rows:
            monthly_list = []
            for month in range(1, 13):
                monthly_list.append({
                    "month": month,
                    "month_name": MONTH_NAMES_PT.get(month, ""),
                    "value": row["monthly"].get(month, Decimal("0") if row["row_type"] != "percent" else 0),
                })
            row["monthly"] = monthly_list

        return Response({
            "currency": "BRL",
            "year": year,
            "columns": [
                {"key": "description", "label": "Descrição"},
                *[{"key": f"month_{m}", "label": MONTH_NAMES_PT.get(m, "").capitalize()} for m in range(1, 13)],
                {"key": "yearly_total", "label": str(year)},
                {"key": "av_percent", "label": "AV%"},
            ],
            "rows": rows,
            "summary": {
                "receita_bruta": receita_bruta_row["yearly_total"],
                "deducoes": deducoes_row["yearly_total"],
                "receita_liquida": receita_liquida_row["yearly_total"],
                "custos_variaveis": custos_variaveis_row["yearly_total"],
                "margem_contribuicao": margem_contribuicao_row["yearly_total"],
                "custos_fixos": custos_fixos_row["yearly_total"],
                "resultado_operacional": resultado_operacional_row["yearly_total"],
            },
        })
