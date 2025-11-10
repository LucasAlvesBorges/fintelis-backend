import uuid

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Company(TimeStampedModel):
    name = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)

    class Meta:
        db_table = 'company'
        ordering = ['name']

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    class Roles(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        FINANCIALS = 'financials', 'Financeiro'
        INVENTORY_MANAGER = 'stock_manager', 'Gerenciador de Inventario'
        HUMAN_RESOURCES = 'human_resources', 'Recursos Humanos'
        ACCOUNTABILITY = 'accountability', 'Contador'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    role = models.CharField(max_length=50, choices=Roles.choices)

    class Meta:
        db_table = 'membership'
        unique_together = ('user', 'company')
        ordering = ['company__name', 'user__email']

    def __str__(self):
        return f'{self.user} @ {self.company} ({self.role})'
