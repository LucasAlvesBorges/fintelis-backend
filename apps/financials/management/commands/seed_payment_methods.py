from django.core.management.base import BaseCommand

from apps.financials.models import PaymentMethod


class Command(BaseCommand):
    help = 'Cria métodos de pagamento padrão no sistema.'
    ## docker-compose exec app python manage.py seed_payment_methods

    PAYMENT_METHODS = [
        'Boleto',
        'Carnê',
        'Cartão Crédito',
        'Cartão de Débito',
        'Cheque',
        'DARF',
        'Depósito em Conta Corrente',
        'Dinheiro',
        'Duplicata',
        'Débito em Conta',
        'Fatura',
        'Fatura / Duplicata',
        'Nota Promissória',
        'Outros',
    ]

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0

        for method_name in self.PAYMENT_METHODS:
            payment_method, created = PaymentMethod.objects.get_or_create(
                name=method_name
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Criado: {method_name}')
                )
            else:
                existing_count += 1
                self.stdout.write(
                    self.style.WARNING(f'→ Já existe: {method_name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nConcluído! Criados: {created_count}, Já existentes: {existing_count}'
            )
        )

