from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, Payment


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer para planos de assinatura.
    """
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'preapproval_plan_id',
            'reason',
            'subscription_plan_type',
            'transaction_amount',
            'currency_id',
            'frequency',
            'frequency_type',
            'repetitions',
            'billing_day',
            'free_trial_frequency',
            'free_trial_frequency_type',
            'init_point',
            'back_url',
            'status',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'preapproval_plan_id',
            'init_point',
            'created_at',
        ]


class CreateSubscriptionPlanSerializer(serializers.Serializer):
    """
    Serializer para criar plano de assinatura no Mercado Pago.
    """
    subscription_plan_type = serializers.ChoiceField(
        choices=['monthly', 'quarterly', 'semiannual', 'annual']
    )
    back_url = serializers.URLField()
    billing_day = serializers.IntegerField(
        min_value=1,
        max_value=28,
        required=False,
        default=10,
        help_text='Dia do mês para cobrança (1-28). Padrão: 10'
    )


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer para assinaturas.
    """
    plan_details = SubscriptionPlanSerializer(source='plan', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id',
            'company',
            'company_name',
            'plan',
            'plan_details',
            'preapproval_id',
            'payer_email',
            'status',
            'start_date',
            'next_payment_date',
            'end_date',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'preapproval_id',
            'status',
            'start_date',
            'next_payment_date',
            'end_date',
            'created_at',
        ]


class CardDataSerializer(serializers.Serializer):
    """
    Serializer para dados do cartão de crédito/débito.
    """
    card_number = serializers.CharField(max_length=19, min_length=13)
    cardholder_name = serializers.CharField(max_length=255)
    expiration_month = serializers.CharField(max_length=2)
    expiration_year = serializers.CharField(max_length=4)
    security_code = serializers.CharField(max_length=4, min_length=3)
    identification_type = serializers.ChoiceField(choices=['CPF', 'CNPJ'])
    identification_number = serializers.CharField(max_length=14)


class CreateSubscriptionSerializer(serializers.Serializer):
    """
    Serializer para criar assinatura no Mercado Pago.
    """
    company_id = serializers.UUIDField()
    plan_id = serializers.UUIDField()
    payer_email = serializers.EmailField()
    billing_day = serializers.IntegerField(
        min_value=1,
        max_value=28,
        required=False,
        default=10
    )
    card_data = CardDataSerializer(
        required=True,
        help_text='Dados do cartão de crédito/débito'
    )


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer para pagamentos.
    """
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'company',
            'company_name',
            'payment_id',
            'transaction_id',
            'amount',
            'subscription_plan',
            'payment_method',
            'status',
            'created_at',
            'completed_at',
            'expires_at',
        ]
        read_only_fields = [
            'id',
            'payment_id',
            'transaction_id',
            'status',
            'created_at',
            'completed_at',
        ]


class PaymentIntentSerializer(serializers.Serializer):
    """
    Serializer para criação de intenção de pagamento.
    """
    company_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    subscription_plan = serializers.ChoiceField(
        choices=['monthly', 'quarterly', 'semiannual', 'annual']
    )


class PaymentConfirmationSerializer(serializers.Serializer):
    """
    Serializer para confirmação de pagamento.
    """
    payment_id = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=['pending', 'completed', 'failed'])
    transaction_id = serializers.CharField(max_length=255, required=False)


class CreatePixPaymentSerializer(serializers.Serializer):
    """
    Serializer para criação de pagamento PIX.
    """
    company_id = serializers.UUIDField(required=True)
    plan_type = serializers.ChoiceField(
        choices=['monthly', 'quarterly', 'semiannual', 'annual'],
        required=True
    )
    payer_email = serializers.EmailField(required=True)
    billing_day = serializers.IntegerField(
        min_value=1,
        max_value=28,
        required=False,
        default=10
    )

