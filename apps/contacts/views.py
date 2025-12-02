from decimal import Decimal

from django.db.models import Sum
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.financials.models import Bill, Income, RecurringBill, RecurringIncome, Transaction
from apps.financials.permissions import IsCompanyMember
from apps.financials.serializers import (
    BillSerializer,
    IncomeSerializer,
    RecurringBillSerializer,
    RecurringIncomeSerializer,
    TransactionSerializer,
)
from apps.financials.views import CompanyScopedViewSet
from .models import Contact
from .serializers import ContactSerializer


class ContactDetailsPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 5


class ContactViewSet(CompanyScopedViewSet):
    queryset = Contact.objects.all().select_related("company")
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    @action(detail=True, methods=["get"], url_path="details")
    def details(self, request, pk=None):
        """
        Retorna detalhes do fornecedor/cliente incluindo:
        - Informações do contato
        - Transações associadas (com paginação de 5 itens)
        - Contas a pagar (bills) associadas (com paginação de 5 itens)
        - Contas a receber (incomes) associadas (com paginação de 5 itens)
        - Contas recorrentes a pagar (recurring bills) associadas (com paginação de 5 itens)
        - Contas recorrentes a receber (recurring incomes) associadas (com paginação de 5 itens)
        """
        contact = self.get_object()
        company = self.get_active_company()
        
        # Verificar se o contato pertence à empresa ativa
        if contact.company_id != company.id:
            raise ValidationError({"detail": "Contato não pertence à empresa ativa."})
        
        # Paginação
        paginator = ContactDetailsPagination()
        transactions_page = int(request.query_params.get("transactions_page", 1))
        bills_page = int(request.query_params.get("bills_page", 1))
        incomes_page = int(request.query_params.get("incomes_page", 1))
        recurring_bills_page = int(request.query_params.get("recurring_bills_page", 1))
        recurring_incomes_page = int(request.query_params.get("recurring_incomes_page", 1))
        page_size = paginator.page_size
        
        # Buscar transações associadas ao contato
        transactions_qs = (
            contact.transactions.all()
            .select_related("category", "contact", "payment_method", "cost_center", "bank_account", "bank_account__bank")
            .order_by("-created_at", "-transaction_date", "-id")
        )
        total_transactions = transactions_qs.count()
        transactions_start = (transactions_page - 1) * page_size
        transactions_end = transactions_start + page_size
        transactions = transactions_qs[transactions_start:transactions_end]
        transactions_total_pages = (total_transactions + page_size - 1) // page_size if total_transactions > 0 else 1
        
        # Buscar contas a pagar (bills) associadas ao contato
        bills_qs = (
            contact.bills.all()
            .select_related("category", "contact", "cost_center", "payment_transaction", "payment_transaction__bank_account")
            .order_by("-due_date", "-id")
        )
        total_bills = bills_qs.count()
        bills_start = (bills_page - 1) * page_size
        bills_end = bills_start + page_size
        bills = bills_qs[bills_start:bills_end]
        bills_total_pages = (total_bills + page_size - 1) // page_size if total_bills > 0 else 1
        
        # Buscar contas a receber (incomes) associadas ao contato
        incomes_qs = (
            contact.incomes.all()
            .select_related("category", "contact", "cost_center", "payment_transaction", "payment_transaction__bank_account")
            .order_by("-due_date", "-id")
        )
        total_incomes = incomes_qs.count()
        incomes_start = (incomes_page - 1) * page_size
        incomes_end = incomes_start + page_size
        incomes = incomes_qs[incomes_start:incomes_end]
        incomes_total_pages = (total_incomes + page_size - 1) // page_size if total_incomes > 0 else 1
        
        # Buscar contas recorrentes a pagar (recurring bills) associadas ao contato
        # Como RecurringBill não tem relacionamento direto com Contact, vamos buscar
        # através das transactions que têm o contact e estão relacionadas a RecurringBillPayment
        recurring_bills_ids = (
            Transaction.objects.filter(contact=contact)
            .exclude(recurring_bill_payments__isnull=True)
            .values_list("recurring_bill_payments__recurring_bill_id", flat=True)
            .distinct()
        )
        recurring_bills_qs = (
            RecurringBill.objects.filter(id__in=recurring_bills_ids, company=company)
            .select_related("category", "cost_center")
            .order_by("-next_due_date", "-id")
        )
        total_recurring_bills = recurring_bills_qs.count()
        recurring_bills_start = (recurring_bills_page - 1) * page_size
        recurring_bills_end = recurring_bills_start + page_size
        recurring_bills = recurring_bills_qs[recurring_bills_start:recurring_bills_end]
        recurring_bills_total_pages = (total_recurring_bills + page_size - 1) // page_size if total_recurring_bills > 0 else 1
        
        # Buscar contas recorrentes a receber (recurring incomes) associadas ao contato
        # Como RecurringIncome não tem relacionamento direto com Contact, vamos buscar
        # através das transactions que têm o contact e estão relacionadas a RecurringIncomeReceipt
        recurring_incomes_ids = (
            Transaction.objects.filter(contact=contact)
            .exclude(recurring_income_receipts__isnull=True)
            .values_list("recurring_income_receipts__recurring_income_id", flat=True)
            .distinct()
        )
        recurring_incomes_qs = (
            RecurringIncome.objects.filter(id__in=recurring_incomes_ids, company=company)
            .select_related("category", "cost_center")
            .order_by("-next_due_date", "-id")
        )
        total_recurring_incomes = recurring_incomes_qs.count()
        recurring_incomes_start = (recurring_incomes_page - 1) * page_size
        recurring_incomes_end = recurring_incomes_start + page_size
        recurring_incomes = recurring_incomes_qs[recurring_incomes_start:recurring_incomes_end]
        recurring_incomes_total_pages = (total_recurring_incomes + page_size - 1) // page_size if total_recurring_incomes > 0 else 1
        
        # Resumo financeiro
        total_receitas = transactions_qs.filter(type=Transaction.Types.RECEITA).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_despesas = transactions_qs.filter(
            type__in=[Transaction.Types.DESPESA, Transaction.Types.TRANSFERENCIA_EXTERNA, Transaction.Types.ESTORNO]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_bills_amount = bills_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_incomes_amount = incomes_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        
        return Response({
            "contact": ContactSerializer(contact, context=self.get_serializer_context()).data,
            "summary": {
                "total_receitas": total_receitas,
                "total_despesas": total_despesas,
                "total_bills": total_bills_amount,
                "total_incomes": total_incomes_amount,
                "total_transactions": total_transactions,
                "total_bills_count": total_bills,
                "total_incomes_count": total_incomes,
                "total_recurring_bills": total_recurring_bills,
                "total_recurring_incomes": total_recurring_incomes,
            },
            "transactions": {
                "items": TransactionSerializer(transactions, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": transactions_page,
                    "page_size": page_size,
                    "total_pages": transactions_total_pages,
                    "total_items": total_transactions,
                    "has_next": transactions_page < transactions_total_pages,
                    "has_previous": transactions_page > 1,
                },
            },
            "bills": {
                "items": BillSerializer(bills, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": bills_page,
                    "page_size": page_size,
                    "total_pages": bills_total_pages,
                    "total_items": total_bills,
                    "has_next": bills_page < bills_total_pages,
                    "has_previous": bills_page > 1,
                },
            },
            "incomes": {
                "items": IncomeSerializer(incomes, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": incomes_page,
                    "page_size": page_size,
                    "total_pages": incomes_total_pages,
                    "total_items": total_incomes,
                    "has_next": incomes_page < incomes_total_pages,
                    "has_previous": incomes_page > 1,
                },
            },
            "recurring_bills": {
                "items": RecurringBillSerializer(recurring_bills, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": recurring_bills_page,
                    "page_size": page_size,
                    "total_pages": recurring_bills_total_pages,
                    "total_items": total_recurring_bills,
                    "has_next": recurring_bills_page < recurring_bills_total_pages,
                    "has_previous": recurring_bills_page > 1,
                },
            },
            "recurring_incomes": {
                "items": RecurringIncomeSerializer(recurring_incomes, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": recurring_incomes_page,
                    "page_size": page_size,
                    "total_pages": recurring_incomes_total_pages,
                    "total_items": total_recurring_incomes,
                    "has_next": recurring_incomes_page < recurring_incomes_total_pages,
                    "has_previous": recurring_incomes_page > 1,
                },
            },
        })
