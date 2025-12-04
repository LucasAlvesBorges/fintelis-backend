"""
Comando para criar dados mockados de contas recorrentes (RecurringBill e RecurringIncome)
com seus respectivos payments e receipts para testes.

Uso:
    docker-compose exec app python manage.py seed_recurring_data
    docker-compose exec app python manage.py seed_recurring_data --company-id <uuid>
    docker-compose exec app python manage.py seed_recurring_data --months 6
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.companies.models import Company, CostCenter
from apps.contacts.models import Contact
from apps.financials.models import (
    Category,
    RecurringBill,
    RecurringBillPayment,
    RecurringIncome,
    RecurringIncomeReceipt,
)
from apps.financials.models import FrequencyChoices


def _add_months(base_date: date, months: int) -> date:
    """Adiciona meses a uma data."""
    month = base_date.month - 1 + months
    year = base_date.year + month // 12
    month = month % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_due_date(current: date, frequency: str) -> date | None:
    """Calcula a próxima data de vencimento baseada na frequência."""
    if not current:
        return None
    if frequency == FrequencyChoices.DAILY:
        return current + timedelta(days=1)
    if frequency == FrequencyChoices.WEEKLY:
        return current + timedelta(days=7)
    if frequency == FrequencyChoices.MONTHLY:
        return _add_months(current, 1)
    if frequency == FrequencyChoices.QUARTERLY:
        return _add_months(current, 3)
    if frequency == FrequencyChoices.YEARLY:
        return _add_months(current, 12)
    return None


class Command(BaseCommand):
    help = "Cria dados mockados de contas recorrentes com payments e receipts para testes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-id",
            type=str,
            help="ID da empresa para criar os dados. Se não fornecido, usa a primeira empresa encontrada.",
        )
        parser.add_argument(
            "--months",
            type=int,
            default=12,
            help="Número de meses de histórico para gerar (padrão: 12)",
        )

    def handle(self, *args, **options):
        company_id = options.get("company_id")
        months = options.get("months", 12)

        # Buscar empresa
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                raise CommandError(f"Empresa com ID {company_id} não encontrada.")
        else:
            company = Company.objects.first()
            if not company:
                raise CommandError("Nenhuma empresa encontrada. Crie uma empresa primeiro.")

        self.stdout.write(
            self.style.SUCCESS(f"Criando dados mockados para empresa: {company.name}")
        )

        # Buscar categorias
        expense_category = Category.objects.filter(
            company=company, type=Category.Types.DESPESA
        ).first()
        revenue_category = Category.objects.filter(
            company=company, type=Category.Types.RECEITA
        ).first()

        if not expense_category:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhuma categoria de despesa encontrada. Criando categoria padrão..."
                )
            )
            expense_category = Category.objects.create(
                company=company,
                name="Despesas Operacionais",
                type=Category.Types.DESPESA,
            )

        if not revenue_category:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhuma categoria de receita encontrada. Criando categoria padrão..."
                )
            )
            revenue_category = Category.objects.create(
                company=company, name="Vendas", type=Category.Types.RECEITA
            )

        # Buscar cost centers
        cost_center = CostCenter.objects.filter(company=company).first()
        
        if not cost_center:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum centro de custo encontrado. Criando centro de custo padrão..."
                )
            )
            cost_center = CostCenter.objects.create(
                company=company,
                name="Administração",
            )

        # Buscar contacts (fornecedores para bills, clientes para incomes)
        all_contacts = list(Contact.objects.filter(company=company))
        
        if not all_contacts:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum contato encontrado. Recurring bills e incomes serão criados sem contact."
                )
            )
            supplier_contacts = []
            customer_contacts = []
        else:
            # Distribuir contacts: primeiros para bills (fornecedores), restantes para incomes (clientes)
            mid_point = len(all_contacts) // 2
            supplier_contacts = all_contacts[:mid_point] if mid_point > 0 else all_contacts[:1]
            customer_contacts = all_contacts[mid_point:] if mid_point > 0 else all_contacts[:1]
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Encontrados {len(all_contacts)} contatos: {len(supplier_contacts)} para bills, {len(customer_contacts)} para incomes"
                )
            )

        with transaction.atomic():
            # Criar Recurring Bills
            recurring_bills = self._create_recurring_bills(
                company, expense_category, cost_center, months, supplier_contacts
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Criadas {len(recurring_bills)} contas recorrentes a pagar"
                )
            )

            # Criar Recurring Incomes
            recurring_incomes = self._create_recurring_incomes(
                company, revenue_category, cost_center, months, customer_contacts
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Criadas {len(recurring_incomes)} contas recorrentes a receber"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Dados mockados criados com sucesso para {company.name}!"
            )
        )
        self.stdout.write(
            f"   - {len(recurring_bills)} Recurring Bills com payments"
        )
        self.stdout.write(
            f"   - {len(recurring_incomes)} Recurring Incomes com receipts"
        )

    def _create_recurring_bills(self, company, category, cost_center, months, contacts=None):
        """Cria recurring bills com payments."""
        today = timezone.localdate()
        start_date = today - timedelta(days=months * 30)
        contacts = contacts or []

        recurring_bills_data = [
            {
                "description": "Assinatura mensal - Software de Gestão",
                "amount": Decimal("299.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": 0,  # Índice do contact a usar
            },
            {
                "description": "Internet mensal",
                "amount": Decimal("150.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": 0,
            },
            {
                "description": "Aluguel mensal",
                "amount": Decimal("2000.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": 1,
            },
            {
                "description": "Folha de pagamento",
                "amount": Decimal("15000.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": None,  # Sem contact (interno)
            },
            {
                "description": "Manutenção trimestral - Equipamentos",
                "amount": Decimal("500.00"),
                "frequency": FrequencyChoices.QUARTERLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": 2,
            },
        ]

        recurring_bills = []
        for data in recurring_bills_data:
            # Calcular next_due_date baseado na frequência
            next_due = self._calculate_next_due_date(
                data["start_date"], data["frequency"], today
            )

            # Selecionar contact se disponível
            contact = None
            if data.get("contact_index") is not None and contacts:
                contact_index = data["contact_index"] % len(contacts) if contacts else None
                if contact_index is not None:
                    contact = contacts[contact_index]

            recurring_bill = RecurringBill.objects.create(
                company=company,
                category=category,
                cost_center=cost_center,
                contact=contact,
                description=data["description"],
                amount=data["amount"],
                frequency=data["frequency"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                next_due_date=next_due,
                is_active=True,
            )

            # Gerar payments para os últimos meses
            self._generate_payments(recurring_bill, months)
            recurring_bills.append(recurring_bill)

        return recurring_bills

    def _create_recurring_incomes(self, company, category, cost_center, months, contacts=None):
        """Cria recurring incomes com receipts."""
        today = timezone.localdate()
        start_date = today - timedelta(days=months * 30)
        contacts = contacts or []

        recurring_incomes_data = [
            {
                "description": "Aluguel recebido - Sala comercial",
                "amount": Decimal("3000.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": 0,  # Índice do contact a usar
            },
            {
                "description": "Receita recorrente - Cliente Premium",
                "amount": Decimal("5000.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": 0,
            },
            {
                "description": "Licenciamento anual - Software",
                "amount": Decimal("12000.00"),
                "frequency": FrequencyChoices.YEARLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": 1,
            },
            {
                "description": "Receita semanal - Serviços",
                "amount": Decimal("800.00"),
                "frequency": FrequencyChoices.WEEKLY,
                "start_date": start_date,
                "end_date": None,
                "contact_index": None,  # Sem contact específico
            },
        ]

        recurring_incomes = []
        for data in recurring_incomes_data:
            # Calcular next_due_date baseado na frequência
            next_due = self._calculate_next_due_date(
                data["start_date"], data["frequency"], today
            )

            # Selecionar contact se disponível
            contact = None
            if data.get("contact_index") is not None and contacts:
                contact_index = data["contact_index"] % len(contacts) if contacts else None
                if contact_index is not None:
                    contact = contacts[contact_index]

            recurring_income = RecurringIncome.objects.create(
                company=company,
                category=category,
                cost_center=cost_center,
                contact=contact,
                description=data["description"],
                amount=data["amount"],
                frequency=data["frequency"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                next_due_date=next_due,
                is_active=True,
            )

            # Gerar receipts para os últimos meses
            self._generate_receipts(recurring_income, months)
            recurring_incomes.append(recurring_income)

        return recurring_incomes

    def _calculate_next_due_date(self, start_date, frequency, today):
        """Calcula a próxima data de vencimento baseada na frequência."""
        current = start_date
        while current <= today:
            next_date = _next_due_date(current, frequency)
            if not next_date:
                break
            current = next_date
        return current

    def _generate_payments(self, recurring_bill, months):
        """Gera payments para uma recurring bill."""
        today = timezone.localdate()
        start_date = recurring_bill.start_date
        end_date = recurring_bill.end_date or (today + timedelta(days=months * 30))

        payments = []
        current_date = start_date

        while current_date <= end_date and len(payments) < (months * 2):
            # Criar payment
            payment = RecurringBillPayment.objects.create(
                company=recurring_bill.company,
                recurring_bill=recurring_bill,
                due_date=current_date,
                amount=recurring_bill.amount,
                status=(
                    RecurringBillPayment.Status.QUITADA
                    if current_date < today
                    else RecurringBillPayment.Status.PENDENTE
                ),
                paid_on=current_date if current_date < today else None,
            )
            payments.append(payment)

            # Calcular próxima data
            current_date = self._add_frequency(current_date, recurring_bill.frequency)
            if current_date is None:
                break

        return payments

    def _generate_receipts(self, recurring_income, months):
        """Gera receipts para uma recurring income."""
        today = timezone.localdate()
        start_date = recurring_income.start_date
        end_date = recurring_income.end_date or (today + timedelta(days=months * 30))

        receipts = []
        current_date = start_date

        while current_date <= end_date and len(receipts) < (months * 2):
            # Criar receipt
            receipt = RecurringIncomeReceipt.objects.create(
                company=recurring_income.company,
                recurring_income=recurring_income,
                due_date=current_date,
                amount=recurring_income.amount,
                status=(
                    RecurringIncomeReceipt.Status.RECEBIDO
                    if current_date < today
                    else RecurringIncomeReceipt.Status.PENDENTE
                ),
                received_on=current_date if current_date < today else None,
            )
            receipts.append(receipt)

            # Calcular próxima data
            current_date = self._add_frequency(current_date, recurring_income.frequency)
            if current_date is None:
                break

        return receipts

    def _add_frequency(self, current_date, frequency):
        """Adiciona a frequência à data atual."""
        return _next_due_date(current_date, frequency)

