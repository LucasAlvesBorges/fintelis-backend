import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


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


class Invitation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        ACCEPTED = 'accepted', 'Aceito'
        REJECTED = 'rejected', 'Recusado'
        EXPIRED = 'expired', 'Expirado'

    class Roles(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        FINANCIALS = 'financials', 'Financeiro'
        INVENTORY_MANAGER = 'stock_manager', 'Gerenciador de Inventario'
        HUMAN_RESOURCES = 'human_resources', 'Recursos Humanos'
        ACCOUNTABILITY = 'accountability', 'Contador'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invitations',
        null=True,
        blank=True,
        help_text='Usuário existente convidado. Se None, é um convite para email não cadastrado.',
    )
    email = models.EmailField(
        max_length=255,
        help_text='Email do usuário convidado. Usado para buscar usuário existente ou criar novo.',
    )
    role = models.CharField(max_length=50, choices=Roles.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invitations',
        help_text='Admin que enviou o convite.',
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'invitation'
        # Permite apenas um convite pendente por email/empresa
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'email'],
                condition=Q(status='pending'),
                name='unique_pending_invitation_per_company_email'
            )
        ]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f'Convite para {self.email} @ {self.company} ({self.status})'
