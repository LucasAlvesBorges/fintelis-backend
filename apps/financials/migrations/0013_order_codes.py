from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("financials", "0012_transaction_cost_center"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="order",
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="bill",
            name="order",
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="income",
            name="order",
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="recurringbill",
            name="order",
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="recurringincome",
            name="order",
            field=models.PositiveIntegerField(editable=False, null=True),
        ),
        migrations.AddConstraint(
            model_name="transaction",
            constraint=models.UniqueConstraint(
                condition=models.Q(("order__isnull", False)),
                fields=("company", "order"),
                name="uniq_transaction_company_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="bill",
            constraint=models.UniqueConstraint(
                condition=models.Q(("order__isnull", False)),
                fields=("company", "order"),
                name="uniq_bill_company_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="income",
            constraint=models.UniqueConstraint(
                condition=models.Q(("order__isnull", False)),
                fields=("company", "order"),
                name="uniq_income_company_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="recurringbill",
            constraint=models.UniqueConstraint(
                condition=models.Q(("order__isnull", False)),
                fields=("company", "order"),
                name="uniq_recurring_bill_company_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="recurringincome",
            constraint=models.UniqueConstraint(
                condition=models.Q(("order__isnull", False)),
                fields=("company", "order"),
                name="uniq_recurring_income_company_order",
            ),
        ),
    ]
