from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, Payment


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer para planos de assinatura.
    """

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "preapproval_plan_id",
            "reason",
            "subscription_plan_type",
            "transaction_amount",
            "currency_id",
            "frequency",
            "frequency_type",
            "repetitions",
            "billing_day",
            "free_trial_frequency",
            "free_trial_frequency_type",
            "init_point",
            "back_url",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "preapproval_plan_id",
            "init_point",
            "created_at",
        ]


class CreateSubscriptionPlanSerializer(serializers.Serializer):
    """
    Serializer para criar plano de assinatura no Mercado Pago.
    """

    subscription_plan_type = serializers.ChoiceField(
        choices=["monthly", "quarterly", "semiannual", "annual"]
    )
    back_url = serializers.URLField()
    billing_day = serializers.IntegerField(
        min_value=1,
        max_value=28,
        required=False,
        default=10,
        help_text="Dia do mês para cobrança (1-28). Padrão: 10",
    )


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer para assinaturas.
    """

    plan_details = SubscriptionPlanSerializer(source="plan", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "company",
            "company_name",
            "plan",
            "plan_details",
            "preapproval_id",
            "external_reference",
            "payer_email",
            "status",
            "is_trial",
            "start_date",
            "next_payment_date",
            "end_date",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "preapproval_id",
            "external_reference",
            "status",
            "is_trial",
            "start_date",
            "next_payment_date",
            "end_date",
            "created_at",
        ]


class CreateSubscriptionSerializer(serializers.Serializer):
    """
    Serializer para criar assinatura no Mercado Pago.
    Agora redireciona para checkout do Mercado Pago, não processa cartão diretamente.
    """

    company_id = serializers.UUIDField()
    plan_id = serializers.CharField(
        help_text="UUID do plano ou tipo de plano (monthly, quarterly, semiannual, annual)"
    )  # Aceita tanto UUID quanto string do tipo de plano
    payer_email = serializers.EmailField(
        required=False,
        help_text="Email do pagador (opcional - será usado o email do usuário logado se não fornecido)",
    )
    billing_day = serializers.IntegerField(
        min_value=1, max_value=28, required=False, default=10
    )
    # card_data não é mais necessário - o checkout do Mercado Pago processa o cartão


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer para pagamentos.
    """

    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "company",
            "company_name",
            "payment_id",
            "transaction_id",
            "code",
            "amount",
            "subscription_plan",
            "payment_method",
            "status",
            "created_at",
            "completed_at",
            "expires_at",
        ]
        read_only_fields = [
            "id",
            "payment_id",
            "transaction_id",
            "status",
            "created_at",
            "completed_at",
        ]


