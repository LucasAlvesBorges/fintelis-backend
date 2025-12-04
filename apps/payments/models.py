import uuid
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SubscriptionPlanType(models.TextChoices):
    """
    Tipos de planos de assinatura disponíveis.
    Centralizado em payments para evitar duplicação.

    Uso:
        SubscriptionPlanType.MONTHLY.value  # "monthly"
        SubscriptionPlanType.MONTHLY.label  # "Mensal"
        SubscriptionPlanType.get_config('monthly')  # Dict com valores
    """

    MONTHLY = "monthly", "Mensal"
    QUARTERLY = "quarterly", "Trimestral"
    SEMIANNUAL = "semiannual", "Semestral"
    ANNUAL = "annual", "Anual"

    @classmethod
    def get_config(cls, plan_type, billing_day=10):
        """
        Retorna configuração completa do plano.

        Args:
            plan_type: str - Tipo do plano (monthly, quarterly, etc)
            billing_day: int - Dia do mês para cobrança (1-28). Padrão: 10

        Returns:
            dict com: reason, amount, frequency, frequency_type, billing_day, duration_days
        """
        from decimal import Decimal

        # Configuração de Valores dos Planos
        configs = {
            cls.MONTHLY.value: {
                "reason": "Plano Mensal Fintelis",
                "amount": Decimal("500.00"),
                "frequency": 1,
                "frequency_type": "months",
                "duration_days": 30,
            },
            cls.QUARTERLY.value: {
                "reason": "Plano Trimestral Fintelis",
                "amount": Decimal("1400.00"),  # ~R$467/mês - economia de ~7%
                "frequency": 3,  # A cada 3 meses
                "frequency_type": "months",
                "duration_days": 90,
            },
            cls.SEMIANNUAL.value: {
                "reason": "Plano Semestral Fintelis",
                "amount": Decimal("2700.00"),  # R$450/mês - economia de 10%
                "frequency": 6,  # A cada 6 meses
                "frequency_type": "months",
                "duration_days": 180,
            },
            cls.ANNUAL.value: {
                "reason": "Plano Anual Fintelis",
                "amount": Decimal("3900.00"),  # R$325/mês - economia de 35%
                "frequency": 12,  # A cada 12 meses
                "frequency_type": "months",
                "duration_days": 365,
            },
        }
        return configs.get(plan_type, {})

    @classmethod
    def get_all_configs(cls):
        """Retorna configurações de todos os planos."""
        return {plan_type.value: cls.get_config(plan_type.value) for plan_type in cls}

    def get_amount(self):
        """Retorna o valor do plano."""
        return self.get_config(self.value)["amount"]

    def get_display_with_price(self):
        """Retorna label com preço formatado."""
        config = self.get_config(self.value)
        return f"{self.label} - R$ {config['amount']}"


class SubscriptionPlan(models.Model):
    """
    Modelo para armazenar planos de assinatura criados no Mercado Pago.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Mercado Pago IDs
    preapproval_plan_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="ID do Plano no Mercado Pago",
        help_text="ID retornado pelo Mercado Pago ao criar o plano",
    )

    # Informações do plano
    reason = models.CharField(
        max_length=255,
        verbose_name="Descrição do Plano",
        help_text="Descrição que aparece no checkout",
    )

    subscription_plan_type = models.CharField(
        max_length=20,
        choices=SubscriptionPlanType.choices,
        verbose_name="Tipo de Plano",
    )

    transaction_amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Valor da Transação"
    )

    currency_id = models.CharField(max_length=3, default="BRL", verbose_name="Moeda")

    # Configurações de recorrência
    frequency = models.IntegerField(
        verbose_name="Frequência", help_text="Quantidade de tempo entre cobranças"
    )

    frequency_type = models.CharField(
        max_length=20,
        choices=[
            ("days", "Dias"),
            ("months", "Meses"),
        ],
        verbose_name="Tipo de Frequência",
    )

    repetitions = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Repetições",
        help_text="Número de cobranças (null = infinito)",
    )

    billing_day = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Dia de Cobrança",
        help_text="Dia fixo do mês para cobrança (1-28). Se None, cobra no dia da primeira compra",
    )

    # Trial gratuito
    free_trial_frequency = models.IntegerField(
        null=True, blank=True, verbose_name="Duração do Trial"
    )

    free_trial_frequency_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ("days", "Dias"),
            ("months", "Meses"),
        ],
        verbose_name="Tipo de Duração do Trial",
    )

    # URLs e metadados
    init_point = models.URLField(
        verbose_name="Link de Checkout",
        help_text="URL para redirecionar o cliente ao checkout",
    )

    back_url = models.URLField(
        verbose_name="URL de Retorno", help_text="URL para retornar após checkout"
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Ativo"),
            ("inactive", "Inativo"),
        ],
        default="active",
        verbose_name="Status",
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Resposta completa da API
    mercadopago_response = models.JSONField(
        default=dict, blank=True, verbose_name="Resposta do Mercado Pago"
    )

    class Meta:
        db_table = "subscription_plan"
        ordering = ["-created_at"]
        verbose_name = "Plano de Assinatura"
        verbose_name_plural = "Planos de Assinatura"

    def __str__(self):
        return f"{self.reason} - R$ {self.transaction_amount}"


class Subscription(models.Model):
    """
    Modelo para armazenar assinaturas criadas no Mercado Pago.
    Gerencia o relacionamento entre empresa e plano de assinatura.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        AUTHORIZED = "authorized", "Autorizado"
        PAUSED = "paused", "Pausado"
        CANCELLED = "cancelled", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name="Empresa",
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name="Plano",
    )

    # Mercado Pago ID
    preapproval_id = models.CharField(
        max_length=255, unique=True, verbose_name="ID da Assinatura no Mercado Pago"
    )

    external_reference = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Código de Referência Externa",
        help_text="Código usado para identificar a assinatura no webhook (ex: company_id)",
    )

    payer_email = models.EmailField(verbose_name="Email do Pagador")

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Status",
    )
    
    # Tipo de assinatura
    is_trial = models.BooleanField(
        default=False,
        verbose_name="É Trial",
        help_text="Se esta assinatura é um período de trial gratuito (14 dias)"
    )

    # Datas
    start_date = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Início",
        help_text="Data de início da assinatura. Expiração = start_date + duração do plano"
    )

    next_payment_date = models.DateTimeField(
        null=True, blank=True, verbose_name="Próxima Data de Pagamento"
    )

    end_date = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Término"
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Resposta completa da API
    mercadopago_response = models.JSONField(
        default=dict, blank=True, verbose_name="Resposta do Mercado Pago"
    )

    class Meta:
        db_table = "subscription"
        ordering = ["-created_at"]
        verbose_name = "Assinatura"
        verbose_name_plural = "Assinaturas"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["preapproval_id"]),
            models.Index(fields=["company", "is_trial"]),
        ]
        constraints = [
            # Garantir que cada empresa só pode ter um trial ativo
            models.UniqueConstraint(
                fields=["company"],
                condition=Q(is_trial=True) & (Q(status="authorized") | Q(status="pending")),
                name="unique_active_trial_per_company",
            )
        ]

    def __str__(self):
        trial_label = " [TRIAL]" if self.is_trial else ""
        return f"Subscription {self.preapproval_id} - {self.company.name}{trial_label}"

    @property
    def expires_at(self):
        """
        Calcula data de expiração baseada em start_date + duração do plano.
        Para trial: 14 dias
        Para planos pagos: duração do plano (duration_days)
        """
        if not self.start_date:
            return None
        
        from datetime import timedelta
        from .models import SubscriptionPlanType
        
        if self.is_trial:
            # Trial sempre tem 14 dias
            return self.start_date + timedelta(days=14)
        
        # Para planos pagos, usar duration_days do plano
        plan_config = SubscriptionPlanType.get_config(self.plan.subscription_plan_type)
        duration_days = plan_config.get("duration_days", 30)
        return self.start_date + timedelta(days=duration_days)

    def activate(self, start_date=None):
        """
        Ativa a assinatura e atualiza a empresa.
        Se a assinatura já está ativa, não reseta o start_date.
        
        Args:
            start_date: Data de início (opcional). Se None e não tem start_date, usa timezone.now()
        """
        self.status = self.Status.AUTHORIZED
        
        # Definir start_date apenas se não foi definido (não resetar em renovações)
        if not self.start_date:
            self.start_date = start_date or timezone.now()
        
        self.save()

        # Calcular expiração
        expires_at = self.expires_at

        # Atualizar empresa
        self.company.subscription_active = True
        # Só atualizar subscription_started_at se não estava definido (primeira ativação)
        if not self.company.subscription_started_at:
            self.company.subscription_started_at = self.start_date
        self.company.subscription_expires_at = expires_at
        self.company.save()
    
    def renew(self):
        """
        Renova a assinatura estendendo a partir da data de expiração atual.
        Usado quando um pagamento recorrente é aprovado para uma assinatura já ativa.
        
        Returns:
            datetime: Nova data de expiração calculada
        """
        from datetime import timedelta
        
        self.status = self.Status.AUTHORIZED
        
        # Se não tem start_date, definir agora (primeira vez)
        if not self.start_date:
            self.start_date = timezone.now()
        
        # Calcular nova data de expiração
        # Se já tem uma data de expiração na company e ainda não expirou, estender a partir dela
        # Caso contrário, calcular a partir do start_date
        if self.company.subscription_expires_at and timezone.now() < self.company.subscription_expires_at:
            # Renovar a partir da data de expiração atual (extensão)
            base_date = self.company.subscription_expires_at
            logger.info(f"Renovando assinatura a partir da data de expiração atual: {base_date}")
        else:
            # Se expirou ou não tem data, calcular a partir do start_date (nova ativação)
            base_date = self.start_date
            logger.info(f"Renovando assinatura a partir do start_date (expirou ou primeira vez): {base_date}")
        
        # Calcular duração do plano
        if self.is_trial:
            duration_days = 14
        else:
            # SubscriptionPlanType já está importado no topo do arquivo
            plan_config = SubscriptionPlanType.get_config(self.plan.subscription_plan_type)
            duration_days = plan_config.get("duration_days", 30)
        
        # Calcular nova expiração
        new_expires_at = base_date + timedelta(days=duration_days)
        
        self.save()
        
        # Atualizar empresa
        self.company.subscription_active = True
        self.company.subscription_expires_at = new_expires_at
        # Não alterar subscription_started_at em renovações (mantém a data original)
        self.company.save()
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Assinatura {self.preapproval_id} renovada: {base_date} + {duration_days} dias = {new_expires_at}")
        
        return new_expires_at

    def cancel(self):
        """Cancela a assinatura."""
        self.status = self.Status.CANCELLED
        self.end_date = timezone.now()
        self.save()

        # Verificar se há outra assinatura ativa (excluindo esta)
        has_other_active = self.company.subscriptions.exclude(
            id=self.id
        ).filter(
            status__in=[self.Status.AUTHORIZED, self.Status.PENDING]
        ).exists()
        
        # Se não há outra assinatura ativa, desativar empresa
        if not has_other_active:
            self.company.subscription_active = False
            self.company.subscription_started_at = None
            self.company.subscription_expires_at = None
            self.company.save()
        else:
            # Se há outra assinatura ativa, atualizar dados da empresa com a mais recente
            other_subscription = self.company.subscriptions.exclude(
                id=self.id
            ).filter(
                status__in=[self.Status.AUTHORIZED, self.Status.PENDING]
            ).order_by('-start_date', '-created_at').first()
            
            if other_subscription:
                self.company.subscription_started_at = other_subscription.start_date
                self.company.subscription_expires_at = other_subscription.expires_at
                self.company.save()
    
    @classmethod
    def create_trial(cls, company):
        """
        Cria uma assinatura de trial de 14 dias para a empresa.
        Garante que cada empresa só pode ter um trial.
        
        Args:
            company: Instância de Company
            
        Returns:
            Subscription criada
            
        Raises:
            ValueError: Se a empresa já possui um trial
        """
        # Verificar se a empresa já tem um trial
        existing_trial = cls.objects.filter(
            company=company,
            is_trial=True
        ).exists()
        
        if existing_trial:
            raise ValueError(f"Empresa {company.name} já possui um trial. Cada empresa só pode ter um trial.")
        
        # Criar plano de trial (não precisa estar no Mercado Pago)
        # Usar um plano mensal como base, mas será marcado como trial
        monthly_plan = SubscriptionPlan.objects.filter(
            subscription_plan_type=SubscriptionPlanType.MONTHLY.value,
            status='active'
        ).first()
        
        if not monthly_plan:
            raise ValueError("Plano mensal não encontrado. Execute create_subscription_plans primeiro.")
        
        # Criar subscription de trial
        import time
        trial_id = f"trial_{company.id}_{int(time.time())}"
        subscription = cls.objects.create(
            company=company,
            plan=monthly_plan,
            preapproval_id=trial_id,
            payer_email=company.email,
            status=cls.Status.AUTHORIZED,
            is_trial=True,
            start_date=timezone.now(),
        )
        
        # Ativar na empresa
        subscription.activate()
        
        return subscription


class Payment(models.Model):
    """
    Modelo para armazenar histórico de pagamentos de assinaturas.
    Registra cada pagamento individual realizado.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        COMPLETED = "completed", "Completo"
        FAILED = "failed", "Falhou"
        EXPIRED = "expired", "Expirado"
        REFUNDED = "refunded", "Reembolsado"

    class PaymentMethod(models.TextChoices):
        PIX = "pix", "PIX"
        CREDIT_CARD = "credit_card", "Cartão de Crédito"
        DEBIT_CARD = "debit_card", "Cartão de Débito"
        BANK_SLIP = "bank_slip", "Boleto Bancário"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Empresa",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        related_name="payments",
        null=True,
        blank=True,
        verbose_name="Assinatura",
        help_text="Assinatura à qual este pagamento pertence (para pagamentos recorrentes)"
    )

    # Informações do pagamento
    payment_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="ID do Pagamento",
        help_text="ID gerado pelo gateway de pagamento",
    )
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID da Transação",
        help_text="ID da transação confirmada",
    )

    code = models.CharField(
        max_length=255,
        unique=True,
        default=uuid.uuid4,
        verbose_name="Código Único do Pagamento",
        help_text="Código único gerado automaticamente para o pagamento",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")

    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlanType.choices,
        verbose_name="Plano de Assinatura",
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.PIX,
        verbose_name="Método de Pagamento",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Status",
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Criado em")
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Completado em"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expira em",
        help_text="Data de expiração do link de pagamento",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Dados adicionais
    pix_code = models.TextField(
        blank=True,
        null=True,
        verbose_name="Código PIX",
        help_text="Copia e cola ou dados do QR Code",
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Resposta do Gateway",
        help_text="Resposta completa do gateway de pagamento",
    )

    notes = models.TextField(blank=True, verbose_name="Observações")

    class Meta:
        db_table = "payment"
        ordering = ["-created_at"]
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["payment_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Payment {self.payment_id} - {self.company.name} - {self.get_status_display()}"

    def mark_as_completed(self, transaction_id=None):
        """
        Marca o pagamento como completo.
        A atualização da assinatura da empresa é feita via webhook quando o pagamento é aprovado.
        """
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if transaction_id:
            self.transaction_id = transaction_id
        self.save()

    def mark_as_failed(self, reason=None):
        """
        Marca o pagamento como falho.
        """
        self.status = self.Status.FAILED
        if reason:
            self.notes = reason
        self.save()
