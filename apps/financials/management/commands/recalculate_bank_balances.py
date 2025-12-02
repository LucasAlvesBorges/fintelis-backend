from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.db.models import F

from apps.financials.models import BankAccount, Transaction


class Command(BaseCommand):
    """
    Recalcula os saldos de todas as contas bancárias baseado nas transações existentes.
    Útil para corrigir saldos que não foram atualizados antes da correção do método save().
    
    Uso:
        docker-compose exec app python manage.py recalculate_bank_balances
        docker-compose exec app python manage.py recalculate_bank_balances --company-id {uuid}
    """
    help = "Recalcula os saldos de todas as contas bancárias baseado nas transações"

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=str,
            help='ID da empresa para recalcular apenas suas contas (opcional)',
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        
        # Resetar todos os saldos para o saldo inicial
        if company_id:
            accounts = BankAccount.objects.filter(company_id=company_id)
            self.stdout.write(f"Recalculando saldos para empresa {company_id}...")
        else:
            accounts = BankAccount.objects.all()
            self.stdout.write("Recalculando saldos de todas as contas bancárias...")
        
        total_accounts = accounts.count()
        updated_count = 0
        
        with db_transaction.atomic():
            for account in accounts:
                # Resetar para saldo inicial
                account.current_balance = account.initial_balance
                account.save(update_fields=['current_balance'])
                
                # Recalcular baseado em todas as transações
                transactions = Transaction.objects.filter(
                    bank_account=account
                ).order_by('transaction_date', 'id')
                
                current_balance = account.initial_balance
                for tx in transactions:
                    delta = Transaction._compute_balance_delta(tx.type, tx.amount)
                    current_balance += delta
                
                # Atualizar o saldo final
                BankAccount.objects.filter(pk=account.pk).update(
                    current_balance=current_balance
                )
                
                # Recarregar para obter o valor calculado
                account.refresh_from_db()
                
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ {account.name} ({account.company.name}): "
                        f"Saldo recalculado para {account.current_balance}"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Recalculo concluído! {updated_count}/{total_accounts} contas atualizadas."
            )
        )

