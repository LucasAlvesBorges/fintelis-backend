from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.financials.models import Transaction


def _invalidate_month_cache(company_id, date, *, expense=False, revenue=False):
    """Remove cache entries for the given company/month/year."""
    if not company_id or not date:
        return
    keys = []
    if expense:
        keys.append(f"dashboard:expenses:{company_id}:{date.year}:{date.month}")
    if revenue:
        keys.append(f"dashboard:revenues:{company_id}:{date.year}:{date.month}")
    if not keys:
        return

    def _delete():
        cache.delete_many(keys)

    transaction.on_commit(_delete)


@receiver(pre_save, sender=Transaction)
def dashboards_cache_pre_save(sender, instance: Transaction, **kwargs):
    if not instance.pk:
        return
    try:
        previous = Transaction.objects.only("transaction_date", "company_id", "type").get(pk=instance.pk)
    except Transaction.DoesNotExist:
        return
    instance._dashboard_cache_previous = {
        "company_id": previous.company_id,
        "date": previous.transaction_date,
        "type": previous.type,
    }


@receiver(post_save, sender=Transaction)
def dashboards_cache_post_save(sender, instance: Transaction, created: bool, **kwargs):
    invalidate_expense = instance.type == Transaction.Types.DESPESA
    invalidate_revenue = instance.type == Transaction.Types.RECEITA

    if created:
        if invalidate_expense or invalidate_revenue:
            _invalidate_month_cache(
                instance.company_id,
                instance.transaction_date,
                expense=invalidate_expense,
                revenue=invalidate_revenue,
            )
        return

    previous = getattr(instance, "_dashboard_cache_previous", None)
    if previous:
        if previous["type"] == Transaction.Types.DESPESA:
            _invalidate_month_cache(previous["company_id"], previous["date"], expense=True)
        if previous["type"] == Transaction.Types.RECEITA:
            _invalidate_month_cache(previous["company_id"], previous["date"], revenue=True)

    if invalidate_expense or invalidate_revenue:
        _invalidate_month_cache(
            instance.company_id,
            instance.transaction_date,
            expense=invalidate_expense,
            revenue=invalidate_revenue,
        )


@receiver(post_delete, sender=Transaction)
def dashboards_cache_post_delete(sender, instance: Transaction, **kwargs):
    if instance.type in (Transaction.Types.DESPESA, Transaction.Types.RECEITA):
        _invalidate_month_cache(
            instance.company_id,
            instance.transaction_date,
            expense=instance.type == Transaction.Types.DESPESA,
            revenue=instance.type == Transaction.Types.RECEITA,
        )
