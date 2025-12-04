import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True




class Company(TimeStampedModel):
    """
    Modelo de empresa (multi-tenant).
    
    Para informações sobre planos de assinatura, veja apps.payments.models.SubscriptionPlanType
    Histórico de assinaturas está disponível via relacionamento: company.subscriptions
    """
    name = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    
    # Assinatura (gerenciada pelo app payments)
    subscription_active = models.BooleanField(
        default=False,
        verbose_name='Assinatura Ativa',
        help_text='Se a empresa tem assinatura ativa (paga ou em trial). Histórico completo em subscriptions.'
    )
    subscription_started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Início da Assinatura',
        help_text='Data de início da assinatura ativa. Expiração calculada via Subscription.'
    )
    subscription_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Assinatura expira em',
        help_text='Data de expiração da assinatura ativa. Calculada como: start_date + duração do plano.'
    )

    class Meta:
        db_table = "company"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def has_active_access(self) -> bool:
        """
        Verifica se a empresa tem acesso ativo (trial ou assinatura paga).
        Usa subscription_expires_at diretamente.
        """
        if not self.subscription_active:
            return False
        
        if self.subscription_expires_at:
            return timezone.now() <= self.subscription_expires_at
        
        return True
    
    @property
    def active_subscription(self):
        """Retorna a assinatura ativa mais recente."""
        return self.subscriptions.filter(
            status__in=['authorized', 'pending']
        ).order_by('-start_date', '-created_at').first()
    
    def has_trial(self) -> bool:
        """Verifica se a empresa já teve um trial."""
        return self.subscriptions.filter(is_trial=True).exists()


class CostCenter(TimeStampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="cost_centers",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, editable=False)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        db_table = "cost_center"
        ordering = ["company__name", "code"]
        unique_together = ("company", "code")

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.company_id:
            raise ValueError("Company is required for cost center creation.")
        if self.parent_id and self.parent.company_id != self.company_id:
            raise ValueError(
                "Parent cost center must belong to the same company."
            )
        if not self.code:
            self.code = self._generate_next_code()
        super().save(*args, **kwargs)

    def _generate_next_code(self) -> str:
        base_qs = CostCenter.objects.filter(company=self.company)

        if self.parent:
            sibling_codes = base_qs.filter(parent=self.parent).values_list(
                "code", flat=True
            )
            sibling_numbers = [
                n
                for n in (
                    self._extract_last_segment(code) for code in sibling_codes
                )
                if n is not None
            ]
            next_number = (max(sibling_numbers) if sibling_numbers else 0) + 1
            return f"{self.parent.code}.{next_number}"

        root_codes = base_qs.filter(parent__isnull=True).values_list(
            "code", flat=True
        )
        root_numbers = [
            n
            for n in (self._extract_first_segment(code) for code in root_codes)
            if n is not None
        ]
        next_number = (max(root_numbers) if root_numbers else 0) + 1
        return str(next_number)

    @staticmethod
    def _extract_first_segment(code: str):
        try:
            return int(str(code).split(".")[0])
        except (ValueError, AttributeError, IndexError):
            return None

    @staticmethod
    def _extract_last_segment(code: str):
        try:
            return int(str(code).split(".")[-1])
        except (ValueError, AttributeError, IndexError):
            return None


class Membership(TimeStampedModel):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        FINANCIALS = "financials", "Financeiro"
        INVENTORY_MANAGER = "stock_manager", "Gerenciador de Inventario"
        HUMAN_RESOURCES = "human_resources", "Recursos Humanos"
        ACCOUNTABILITY = "accountability", "Contador"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=50, choices=Roles.choices)

    class Meta:
        db_table = "membership"
        unique_together = ("user", "company")
        ordering = ["company__name", "user__email"]

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.role})"


class Invitation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        ACCEPTED = "accepted", "Aceito"
        REJECTED = "rejected", "Recusado"
        EXPIRED = "expired", "Expirado"

    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        FINANCIALS = "financials", "Financeiro"
        INVENTORY_MANAGER = "stock_manager", "Gerenciador de Inventario"
        HUMAN_RESOURCES = "human_resources", "Recursos Humanos"
        ACCOUNTABILITY = "accountability", "Contador"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invitations",
        null=True,
        blank=True,
        help_text="Usuário existente convidado. Se None, é um convite para email não cadastrado.",
    )
    email = models.EmailField(
        max_length=255,
        help_text="Email do usuário convidado. Usado para buscar usuário existente ou criar novo.",
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
        related_name="sent_invitations",
        help_text="Admin que enviou o convite.",
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "invitation"
        # Permite apenas um convite pendente por email/empresa
        constraints = [
            models.UniqueConstraint(
                fields=["company", "email"],
                condition=Q(status="pending"),
                name="unique_pending_invitation_per_company_email",
            )
        ]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"Convite para {self.email} @ {self.company} ({self.status})"
