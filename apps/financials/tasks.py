from __future__ import annotations

import calendar
from datetime import date, timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Bill, Income, RecurringBill, RecurringIncome


@shared_task(name='financials.generate_recurring_bills')
def generate_recurring_bills() -> int:
    """Create Bill entries for every active RecurringBill due today."""
    today = timezone.localdate()
    created = 0
    queryset = RecurringBill.objects.filter(is_active=True, next_due_date__lte=today)
    for template in queryset.select_related('company', 'category', 'cost_center', 'contact'):
        with transaction.atomic():
            Bill.objects.create(
                company=template.company,
                category=template.category,
                cost_center=template.cost_center,
                contact=template.contact,
                description=template.description,
                amount=template.amount,
                due_date=template.next_due_date,
            )
            _advance_recurring_template(template)
            created += 1
    return created


@shared_task(name='financials.generate_recurring_incomes')
def generate_recurring_incomes() -> int:
    """Create Income entries for every active RecurringIncome due today."""
    today = timezone.localdate()
    created = 0
    queryset = RecurringIncome.objects.filter(is_active=True, next_due_date__lte=today)
    for template in queryset.select_related('company', 'category', 'cost_center', 'contact'):
        with transaction.atomic():
            Income.objects.create(
                company=template.company,
                category=template.category,
                cost_center=template.cost_center,
                contact=template.contact,
                description=template.description,
                amount=template.amount,
                due_date=template.next_due_date,
            )
            _advance_recurring_template(template)
            created += 1
    return created


def _advance_recurring_template(template):
    new_date = _calculate_next_due_date(template.next_due_date, template.frequency)
    template.next_due_date = new_date
    if template.end_date and new_date > template.end_date:
        template.is_active = False
    template.save(update_fields=['next_due_date', 'is_active', 'updated_at'])


def _calculate_next_due_date(current: date, frequency: str) -> date:
    if frequency == 'daily':
        return current + timedelta(days=1)
    if frequency == 'weekly':
        return current + timedelta(weeks=1)
    if frequency == 'monthly':
        return _add_months(current, 1)
    if frequency == 'quarterly':
        return _add_months(current, 3)
    if frequency == 'yearly':
        return _add_months(current, 12)
    return current


def _add_months(original: date, months: int) -> date:
    month = original.month - 1 + months
    year = original.year + month // 12
    month = month % 12 + 1
    day = min(original.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
