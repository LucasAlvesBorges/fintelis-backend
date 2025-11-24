import uuid

from django.db import models
from django.core.exceptions import ValidationError

from apps.companies.models import Company


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Contact(TimeStampedModel):
    class Types(models.TextChoices):
        CLIENTE = 'cliente', 'Cliente'
        FORNECEDOR = 'fornecedor', 'Fornecedor'
        AMBOS = 'ambos', 'Ambos'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=255)
    fantasy_name = models.CharField(max_length=255, null=True, blank=True)
    tax_id = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    type = models.CharField(max_length=20, choices=Types.choices)

    class Meta:
        db_table = 'contact'
        unique_together = ('company', 'tax_id')
        ordering = ['company__name', 'name']

    def clean(self):
        super().clean()
        errors = {}
        if not self.name:
            errors['name'] = 'Nome é obrigatório.'
        if self.tax_id == '':
            self.tax_id = None
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'
