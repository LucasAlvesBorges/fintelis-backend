from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import authenticate
from django.db import transaction

from apps.users.models import User
from apps.companies.models import Company, Membership
from apps.financials.models import (
    Bank,
    BankAccount,
    Category,
    Transaction,
    Bill,
    Income,
    RecurringBill,
    RecurringIncome,
    FrequencyChoices,
)
from apps.contacts.models import Contact


class Command(BaseCommand):
    ## docker compose exec app python manage.py populate_financial_data
    help = "Popula dados mockados de financials para uma empresa selecionada"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        # 1. Solicitar email e senha
        email = input("Email do usuário: ").strip()
        password = input("Senha: ").strip()

        # 2. Autenticar usuário
        user = authenticate(username=email, password=password)
        if not user:
            self.stdout.write(self.style.ERROR("Credenciais inválidas."))
            return

        # 3. Listar empresas do usuário
        memberships = Membership.objects.filter(user=user).select_related("company")
        if not memberships.exists():
            self.stdout.write(self.style.ERROR("Usuário não possui empresas associadas."))
            return

        companies = [m.company for m in memberships]
        self.stdout.write("\nEmpresas disponíveis:")
        for idx, company in enumerate(companies, 1):
            self.stdout.write(f"  {idx}. {company.name} (ID: {company.id})")

        # 4. Selecionar empresa
        while True:
            try:
                choice = int(input("\nSelecione o número da empresa: ").strip())
                if 1 <= choice <= len(companies):
                    selected_company = companies[choice - 1]
                    break
                else:
                    self.stdout.write(self.style.ERROR("Número inválido. Tente novamente."))
            except ValueError:
                self.stdout.write(self.style.ERROR("Por favor, digite um número válido."))

        self.stdout.write(f"\n✓ Empresa selecionada: {selected_company.name}")

        # 5. Criar dados mockados
        with transaction.atomic():
            self._create_mock_data(selected_company)
            self.stdout.write(self.style.SUCCESS("\n✓ Dados mockados criados com sucesso!"))

    def _create_mock_data(self, company: Company):
        """Cria dados mockados para a empresa"""
        today = date.today()

        # 1. Criar ou obter BankAccount
        bank = Bank.objects.filter(is_active=True).first()
        if not bank:
            self.stdout.write(self.style.WARNING("Nenhum banco ativo encontrado. Criando banco mockado..."))
            bank = Bank.objects.create(
                code="999",
                name="Banco Mockado",
                is_active=True
            )

        bank_account, created = BankAccount.objects.get_or_create(
            company=company,
            name="Conta Principal",
            defaults={
                "bank": bank,
                "type": BankAccount.Types.CONTA_CORRENTE,
                "initial_balance": Decimal("10000.00"),
                "current_balance": Decimal("10000.00"),
            }
        )
        if created:
            self.stdout.write(f"  ✓ Conta bancária criada: {bank_account.name}")
        else:
            self.stdout.write(f"  ✓ Conta bancária existente: {bank_account.name}")

        # 2. Criar Categories
        cat_receita, _ = Category.objects.get_or_create(
            company=company,
            name="Vendas",
            type=Category.Types.RECEITA,
            defaults={"parent": None}
        )
        cat_despesa, _ = Category.objects.get_or_create(
            company=company,
            name="Despesas Operacionais",
            type=Category.Types.DESPESA,
            defaults={"parent": None}
        )
        self.stdout.write(f"  ✓ Categorias criadas/verificadas")

        # 3. Criar Contacts
        cliente, _ = Contact.objects.get_or_create(
            company=company,
            name="Cliente Exemplo LTDA",
            defaults={
                "type": Contact.Types.CLIENTE,
                "email": "cliente@example.com",
                "phone": "11999999999",
                "tax_id": "12345678000199",
            }
        )
        fornecedor, _ = Contact.objects.get_or_create(
            company=company,
            name="Fornecedor Exemplo ME",
            defaults={
                "type": Contact.Types.FORNECEDOR,
                "email": "fornecedor@example.com",
                "phone": "11888888888",
                "tax_id": "98765432000111",
            }
        )
        self.stdout.write(f"  ✓ Contatos criados/verificados")

        # 4. Criar Transactions
        transactions_data = [
            {
                "description": "Venda de produto A",
                "amount": Decimal("5000.00"),
                "type": Transaction.Types.RECEITA,
                "transaction_date": today - timedelta(days=5),
                "category": cat_receita,
                "contact": cliente,
            },
            {
                "description": "Venda de produto B",
                "amount": Decimal("3000.00"),
                "type": Transaction.Types.RECEITA,
                "transaction_date": today - timedelta(days=3),
                "category": cat_receita,
                "contact": cliente,
            },
            {
                "description": "Pagamento de fornecedor",
                "amount": Decimal("1500.00"),
                "type": Transaction.Types.DESPESA,
                "transaction_date": today - timedelta(days=2),
                "category": cat_despesa,
                "contact": fornecedor,
            },
            {
                "description": "Despesa administrativa",
                "amount": Decimal("800.00"),
                "type": Transaction.Types.DESPESA,
                "transaction_date": today - timedelta(days=1),
                "category": cat_despesa,
            },
        ]

        created_transactions = []
        for tx_data in transactions_data:
            tx = Transaction.objects.create(
                company=company,
                bank_account=bank_account,
                **tx_data
            )
            created_transactions.append(tx)

        self.stdout.write(f"  ✓ {len(created_transactions)} transações criadas")

        # 5. Criar Bills (contas a pagar)
        bills_data = [
            {
                "description": "Conta de energia",
                "amount": Decimal("450.00"),
                "due_date": today + timedelta(days=10),
                "status": Bill.Status.A_VENCER,
                "category": cat_despesa,
                "contact": fornecedor,
            },
            {
                "description": "Aluguel",
                "amount": Decimal("2000.00"),
                "due_date": today + timedelta(days=15),
                "status": Bill.Status.A_VENCER,
                "category": cat_despesa,
            },
            {
                "description": "Fornecedor - Material",
                "amount": Decimal("1200.00"),
                "due_date": today - timedelta(days=5),
                "status": Bill.Status.QUITADA,
                "category": cat_despesa,
                "contact": fornecedor,
            },
        ]

        created_bills = []
        for bill_data in bills_data:
            bill = Bill.objects.create(company=company, **bill_data)
            created_bills.append(bill)
            # Se quitada, criar transaction de pagamento
            if bill.status == Bill.Status.QUITADA:
                payment_tx = Transaction.objects.create(
                    company=company,
                    bank_account=bank_account,
                    category=bill.category,
                    description=f"Pagamento - {bill.description}",
                    amount=bill.amount,
                    type=Transaction.Types.DESPESA,
                    transaction_date=bill.due_date,
                    contact=bill.contact,
                )
                bill.payment_transaction = payment_tx
                bill.save(update_fields=["payment_transaction"])

        self.stdout.write(f"  ✓ {len(created_bills)} contas a pagar criadas")

        # 6. Criar Incomes (contas a receber)
        incomes_data = [
            {
                "description": "Faturamento cliente A",
                "amount": Decimal("4000.00"),
                "due_date": today + timedelta(days=7),
                "status": Income.Status.PENDENTE,
                "category": cat_receita,
                "contact": cliente,
            },
            {
                "description": "Faturamento cliente B",
                "amount": Decimal("2500.00"),
                "due_date": today + timedelta(days=12),
                "status": Income.Status.PENDENTE,
                "category": cat_receita,
                "contact": cliente,
            },
            {
                "description": "Recebimento antecipado",
                "amount": Decimal("6000.00"),
                "due_date": today - timedelta(days=3),
                "status": Income.Status.RECEBIDO,
                "category": cat_receita,
                "contact": cliente,
            },
        ]

        created_incomes = []
        for income_data in incomes_data:
            income = Income.objects.create(company=company, **income_data)
            created_incomes.append(income)
            # Se recebido, criar transaction de recebimento
            if income.status == Income.Status.RECEBIDO:
                payment_tx = Transaction.objects.create(
                    company=company,
                    bank_account=bank_account,
                    category=income.category,
                    description=f"Recebimento - {income.description}",
                    amount=income.amount,
                    type=Transaction.Types.RECEITA,
                    transaction_date=income.due_date,
                    contact=income.contact,
                )
                income.payment_transaction = payment_tx
                income.save(update_fields=["payment_transaction"])

        self.stdout.write(f"  ✓ {len(created_incomes)} contas a receber criadas")

        # 7. Criar RecurringBills
        recurring_bills_data = [
            {
                "description": "Assinatura mensal - Software",
                "amount": Decimal("299.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": today - timedelta(days=30),
                "next_due_date": today + timedelta(days=5),
                "is_active": True,
                "category": cat_despesa,
            },
            {
                "description": "Internet mensal",
                "amount": Decimal("150.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": today - timedelta(days=60),
                "next_due_date": today + timedelta(days=8),
                "is_active": True,
                "category": cat_despesa,
            },
        ]

        created_recurring_bills = []
        for rb_data in recurring_bills_data:
            rb = RecurringBill.objects.create(company=company, **rb_data)
            created_recurring_bills.append(rb)

        self.stdout.write(f"  ✓ {len(created_recurring_bills)} despesas recorrentes criadas")

        # 8. Criar RecurringIncomes
        recurring_incomes_data = [
            {
                "description": "Assinatura cliente mensal",
                "amount": Decimal("1000.00"),
                "frequency": FrequencyChoices.MONTHLY,
                "start_date": today - timedelta(days=45),
                "next_due_date": today + timedelta(days=10),
                "is_active": True,
                "category": cat_receita,
            },
        ]

        created_recurring_incomes = []
        for ri_data in recurring_incomes_data:
            ri = RecurringIncome.objects.create(company=company, **ri_data)
            created_recurring_incomes.append(ri)

        self.stdout.write(f"  ✓ {len(created_recurring_incomes)} receitas recorrentes criadas")

        # Atualizar saldo da conta
        bank_account.refresh_from_db()
        self.stdout.write(f"\n  💰 Saldo atual da conta: R$ {bank_account.current_balance:,.2f}")

