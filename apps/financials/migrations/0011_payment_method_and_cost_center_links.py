from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0011_costcenter_and_more"),
        ("financials", "0010_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="payment_method",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="transactions",
                to="financials.paymentmethod",
            ),
        ),
        migrations.AddField(
            model_name="bill",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bills",
                to="companies.costcenter",
            ),
        ),
        migrations.AddField(
            model_name="income",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="incomes",
                to="companies.costcenter",
            ),
        ),
        migrations.AddField(
            model_name="recurringbill",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="recurring_bills",
                to="companies.costcenter",
            ),
        ),
        migrations.AddField(
            model_name="recurringincome",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="recurring_incomes",
                to="companies.costcenter",
            ),
        ),
    ]
