import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("financials", "0009_alter_category_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "db_table": "payment_method",
                "ordering": ["name"],
            },
        ),
    ]
