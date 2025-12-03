"""
Django command to set a company to trial mode.
"""
from django.core.management.base import BaseCommand
from apps.companies.models import Company


class Command(BaseCommand):
    help = 'Set a company to trial mode'

    def add_arguments(self, parser):
        parser.add_argument('company_id', type=str, help='Company UUID')

    def handle(self, *args, **options):
        company_id = options['company_id']
        
        try:
            company = Company.objects.get(pk=company_id)
            
            # Start trial
            company.start_trial()
            
            # Make sure subscription is not active
            company.subscription_active = False
            company.subscription_plan = None
            company.subscription_expires_at = None
            company.mercadopago_subscription_id = None
            company.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully set company "{company.name}" to trial mode.\n'
                    f'Trial ends at: {company.trial_ends_at}'
                )
            )
            
        except Company.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Company with ID {company_id} not found')
            )

