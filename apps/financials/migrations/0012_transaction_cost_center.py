from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0011_costcenter_and_more"),
        ("financials", "0011_payment_method_and_cost_center_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="transactions",
                to="companies.costcenter",
            ),
        ),
    ]
