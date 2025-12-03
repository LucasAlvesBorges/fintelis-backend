import uuid
from django.db import models
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
                'reason': 'Plano Mensal Fintelis',
                'amount': Decimal('500.00'),
                'frequency': 1,
                'frequency_type': 'months',
                'billing_day': billing_day,
                'duration_days': 30,
            },
            cls.QUARTERLY.value: {
                'reason': 'Plano Trimestral Fintelis',
                'amount': Decimal('1500.00'),
                'frequency': 3,
                'frequency_type': 'months',
                'billing_day': billing_day,
                'duration_days': 90,
            },
            cls.SEMIANNUAL.value: {
                'reason': 'Plano Semestral Fintelis',
                'amount': Decimal('3000.00'),
                'frequency': 6,
                'frequency_type': 'months',
                'billing_day': billing_day,
                'duration_days': 180,
            },
            cls.ANNUAL.value: {
                'reason': 'Plano Anual Fintelis',
                'amount': Decimal('6000.00'),
                'frequency': 12,
                'frequency_type': 'months',
                'billing_day': billing_day,
                'duration_days': 365,
            },
        }
        return configs.get(plan_type, {})
    
    @classmethod
    def get_all_configs(cls):
        """Retorna configurações de todos os planos."""
        return {
            plan_type.value: cls.get_config(plan_type.value)
            for plan_type in cls
        }
    
    def get_amount(self):
        """Retorna o valor do plano."""
        return self.get_config(self.value)['amount']
    
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
        verbose_name='ID do Plano no Mercado Pago',
        help_text='ID retornado pelo Mercado Pago ao criar o plano'
    )
    
    # Informações do plano
    reason = models.CharField(
        max_length=255,
        verbose_name='Descrição do Plano',
        help_text='Descrição que aparece no checkout'
    )
    
    subscription_plan_type = models.CharField(
        max_length=20,
        choices=SubscriptionPlanType.choices,
        verbose_name='Tipo de Plano'
    )
    
    transaction_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Valor da Transação'
    )
    
    currency_id = models.CharField(
        max_length=3,
        default='BRL',
        verbose_name='Moeda'
    )
    
    # Configurações de recorrência
    frequency = models.IntegerField(
        verbose_name='Frequência',
        help_text='Quantidade de tempo entre cobranças'
    )
    
    frequency_type = models.CharField(
        max_length=20,
        choices=[
            ('days', 'Dias'),
            ('months', 'Meses'),
        ],
        verbose_name='Tipo de Frequência'
    )
    
    repetitions = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Repetições',
        help_text='Número de cobranças (null = infinito)'
    )
    
    billing_day = models.IntegerField(
        verbose_name='Dia de Cobrança',
        help_text='Dia do mês para cobrança (1-28)'
    )
    
    # Trial gratuito
    free_trial_frequency = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Duração do Trial'
    )
    
    free_trial_frequency_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('days', 'Dias'),
            ('months', 'Meses'),
        ],
        verbose_name='Tipo de Duração do Trial'
    )
    
    # URLs e metadados
    init_point = models.URLField(
        verbose_name='Link de Checkout',
        help_text='URL para redirecionar o cliente ao checkout'
    )
    
    back_url = models.URLField(
        verbose_name='URL de Retorno',
        help_text='URL para retornar após checkout'
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Ativo'),
            ('inactive', 'Inativo'),
        ],
        default='active',
        verbose_name='Status'
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Resposta completa da API
    mercadopago_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Resposta do Mercado Pago'
    )
    
    class Meta:
        db_table = 'subscription_plan'
        ordering = ['-created_at']
        verbose_name = 'Plano de Assinatura'
        verbose_name_plural = 'Planos de Assinatura'
    
    def __str__(self):
        return f"{self.reason} - R$ {self.transaction_amount}"


class Subscription(models.Model):
    """
    Modelo para armazenar assinaturas criadas no Mercado Pago.
    Gerencia o relacionamento entre empresa e plano de assinatura.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        AUTHORIZED = 'authorized', 'Autorizado'
        PAUSED = 'paused', 'Pausado'
        CANCELLED = 'cancelled', 'Cancelado'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Empresa'
    )
    
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name='Plano'
    )
    
    # Mercado Pago ID
    preapproval_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='ID da Assinatura no Mercado Pago'
    )
    
    payer_email = models.EmailField(
        verbose_name='Email do Pagador'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Status'
    )
    
    # Datas
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Início'
    )
    
    next_payment_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Próxima Data de Pagamento'
    )
    
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Término'
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Resposta completa da API
    mercadopago_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Resposta do Mercado Pago'
    )
    
    class Meta:
        db_table = 'subscription'
        ordering = ['-created_at']
        verbose_name = 'Assinatura'
        verbose_name_plural = 'Assinaturas'
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['preapproval_id']),
        ]
    
    def __str__(self):
        return f"Subscription {self.preapproval_id} - {self.company.name}"
    
    def activate(self):
        """Ativa a assinatura e atualiza a empresa."""
        self.status = self.Status.AUTHORIZED
        self.save()
        
        # Atualizar empresa
        self.company.subscription_active = True
        self.company.subscription_plan = self.plan.subscription_plan_type
        self.company.mercadopago_subscription_id = self.preapproval_id
        self.company.save()
    
    def cancel(self):
        """Cancela a assinatura."""
        self.status = self.Status.CANCELLED
        self.end_date = timezone.now()
        self.save()
        
        # Atualizar empresa
        self.company.subscription_active = False
        self.company.mercadopago_subscription_id = None
        self.company.save()


class Payment(models.Model):
    """
    Modelo para armazenar histórico de pagamentos de assinaturas.
    Registra cada pagamento individual realizado.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        COMPLETED = 'completed', 'Completo'
        FAILED = 'failed', 'Falhou'
        EXPIRED = 'expired', 'Expirado'
        REFUNDED = 'refunded', 'Reembolsado'
    
    class PaymentMethod(models.TextChoices):
        PIX = 'pix', 'PIX'
        CREDIT_CARD = 'credit_card', 'Cartão de Crédito'
        DEBIT_CARD = 'debit_card', 'Cartão de Débito'
        BANK_SLIP = 'bank_slip', 'Boleto Bancário'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Empresa'
    )
    
    # Informações do pagamento
    payment_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='ID do Pagamento',
        help_text='ID gerado pelo gateway de pagamento'
    )
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='ID da Transação',
        help_text='ID da transação confirmada'
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Valor'
    )
    
    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlanType.choices,
        verbose_name='Plano de Assinatura'
    )
    
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.PIX,
        verbose_name='Método de Pagamento'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Status'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Criado em'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completado em'
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Expira em',
        help_text='Data de expiração do link de pagamento'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )
    
    # Dados adicionais
    pix_code = models.TextField(
        blank=True,
        null=True,
        verbose_name='Código PIX',
        help_text='Copia e cola ou dados do QR Code'
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Resposta do Gateway',
        help_text='Resposta completa do gateway de pagamento'
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name='Observações'
    )
    
    class Meta:
        db_table = 'payment'
        ordering = ['-created_at']
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['payment_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Payment {self.payment_id} - {self.company.name} - {self.get_status_display()}"
    
    def mark_as_completed(self, transaction_id=None):
        """
        Marca o pagamento como completo e atualiza a assinatura da empresa.
        """
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if transaction_id:
            self.transaction_id = transaction_id
        self.save()
        
        # Atualizar assinatura da empresa
        self.company.subscription_active = True
        self.company.subscription_plan = self.subscription_plan
        
        # Calcular data de expiração baseada no plano
        from datetime import timedelta
        plan_config = SubscriptionPlanType.get_config(self.subscription_plan)
        duration_days = plan_config.get('duration_days', 30)
        self.company.subscription_expires_at = timezone.now() + timedelta(days=duration_days)
        
        self.company.save()
    
    def mark_as_failed(self, reason=None):
        """
        Marca o pagamento como falho.
        """
        self.status = self.Status.FAILED
        if reason:
            self.notes = reason
        self.save()
