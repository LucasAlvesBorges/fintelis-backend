from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    ## docker compose exec app python manage.py setup_financial_tasks --hour 1 --minute 0


    help = 'Create or refresh Celery Beat tasks for recurring financial entries.'

    def add_arguments(self, parser):
        parser.add_argument('--hour', type=int, default=1, help='Hour (0-23) to run the tasks. Default: 1AM.')
        parser.add_argument('--minute', type=int, default=0, help='Minute (0-59) to run the tasks. Default: 00.')

    def handle(self, *args, **options):
        hour = options['hour']
        minute = options['minute']
        tzname = getattr(settings, 'TIME_ZONE', timezone.get_current_timezone_name())

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=str(minute),
            hour=str(hour),
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
            timezone=tzname,
        )

        tasks = [
            (
                'Generate Recurring Bills',
                'financials.generate_recurring_bills',
            ),
            (
                'Generate Recurring Incomes',
                'financials.generate_recurring_incomes',
            ),
        ]

        created = 0
        for name, task in tasks:
            obj, created_flag = PeriodicTask.objects.update_or_create(
                name=name,
                defaults={'task': task, 'crontab': schedule, 'enabled': True},
            )
            created += int(created_flag)
            self.stdout.write(self.style.SUCCESS(f'Configured periodic task: {obj.name}'))

        self.stdout.write(self.style.SUCCESS(f'Finished. {created} task(s) newly created, {len(tasks) - created} updated.'))
