from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('companies', '0003_remove_company_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='legal_document',
            field=models.FileField(blank=True, null=True, upload_to='company_docs/legal/'),
        ),
        migrations.AddField(
            model_name='company',
            name='owner_cnh_document',
            field=models.FileField(blank=True, null=True, upload_to='company_docs/cnh/'),
        ),
        migrations.AddField(
            model_name='company',
            name='proof_of_address_document',
            field=models.FileField(blank=True, null=True, upload_to='company_docs/address/'),
        ),
        migrations.AddField(
            model_name='company',
            name='supplemental_documents',
            field=models.FileField(blank=True, null=True, upload_to='company_docs/support/'),
        ),
        migrations.AddField(
            model_name='company',
            name='type',
            field=models.CharField(default='other', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='company',
            name='verification_notes',
            field=models.TextField(blank=True, default=''),
        ),
    ]
