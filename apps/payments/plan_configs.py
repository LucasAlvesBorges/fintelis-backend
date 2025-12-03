"""
Exemplo de uso das configurações de planos centralizadas.

Todos os valores (preços, frequências, duração) estão definidos em:
    apps.payments.models.SubscriptionPlanType.get_config()
"""

from .models import SubscriptionPlanType

# ============================================================================
# EXEMPLOS DE USO
# ============================================================================

def example_get_plan_value():
    """Exemplo: Obter valor de um plano"""
    monthly_amount = SubscriptionPlanType.MONTHLY.get_amount()
    print(f"Plano Mensal: R$ {monthly_amount}")  # R$ 500.00
    
    annual_amount = SubscriptionPlanType.ANNUAL.get_amount()
    print(f"Plano Anual: R$ {annual_amount}")  # R$ 6000.00


def example_get_plan_label_with_price():
    """Exemplo: Obter label com preço formatado"""
    display = SubscriptionPlanType.MONTHLY.get_display_with_price()
    print(display)  # "Mensal - R$ 500.00"


def example_get_full_config():
    """Exemplo: Obter configuração completa de um plano"""
    config = SubscriptionPlanType.get_config('monthly')
    print(f"""
    Plano: {config['reason']}
    Valor: R$ {config['amount']}
    Frequência: {config['frequency']} {config['frequency_type']}
    Dia de cobrança: {config['billing_day']}
    Duração: {config['duration_days']} dias
    """)


def example_list_all_plans():
    """Exemplo: Listar todos os planos disponíveis"""
    all_configs = SubscriptionPlanType.get_all_configs()
    
    for plan_type, config in all_configs.items():
        print(f"{plan_type}: R$ {config['amount']} ({config['duration_days']} dias)")


def example_use_in_serializer():
    """Exemplo: Usar em serializer para API"""
    from rest_framework import serializers
    
    class PlanSerializer(serializers.Serializer):
        plan_type = serializers.ChoiceField(choices=SubscriptionPlanType.choices)
        
        def to_representation(self, instance):
            config = SubscriptionPlanType.get_config(instance.plan_type)
            return {
                'type': instance.plan_type,
                'label': SubscriptionPlanType(instance.plan_type).label,
                'amount': str(config['amount']),
                'frequency': config['frequency'],
                'frequency_type': config['frequency_type'],
                'duration_days': config['duration_days'],
            }


def example_use_in_template():
    """Exemplo: Usar em template/frontend"""
    plans_for_frontend = []
    
    for plan_type in SubscriptionPlanType:
        config = SubscriptionPlanType.get_config(plan_type.value)
        plans_for_frontend.append({
            'id': plan_type.value,
            'name': plan_type.label,
            'display': plan_type.get_display_with_price(),
            'price': float(config['amount']),
            'frequency': config['frequency'],
            'frequency_type': config['frequency_type'],
            'duration_days': config['duration_days'],
        })
    
    # Retornar para API ou template
    return plans_for_frontend


def example_calculate_discount():
    """Exemplo: Calcular desconto para planos longos"""
    monthly = SubscriptionPlanType.get_config('monthly')
    annual = SubscriptionPlanType.get_config('annual')
    
    monthly_price = monthly['amount']
    annual_price = annual['amount']
    
    # Preço se pagasse mensalmente por 12 meses
    total_if_monthly = monthly_price * 12
    
    # Economia anual
    savings = total_if_monthly - annual_price
    discount_percentage = (savings / total_if_monthly) * 100
    
    print(f"""
    Pagamento mensal (12 meses): R$ {total_if_monthly}
    Pagamento anual: R$ {annual_price}
    Economia: R$ {savings} ({discount_percentage:.1f}%)
    """)


# ============================================================================
# COMO ALTERAR OS VALORES DOS PLANOS
# ============================================================================

"""
Para alterar preços ou configurações:

1. Edite apenas: apps/payments/models.py
2. Dentro da classe SubscriptionPlanType
3. No método get_config()
4. Altere o dicionário configs

Exemplo:
    configs = {
        cls.MONTHLY.value: {
            'amount': Decimal('600.00'),  # ← Altere aqui
            ...
        },
    }

Todos os lugares que usam o valor serão atualizados automaticamente:
- Views
- Admin
- Serializers
- Frontend (via API)
"""


# ============================================================================
# MIGRAÇÃO DE CÓDIGO ANTIGO
# ============================================================================

"""
ANTES (espalhado):
    # Em views.py
    plan_configs = {
        'monthly': {'amount': Decimal('500.00')},
    }
    
    # Em models.py
    MONTHLY = "monthly", "Mensal (R$500)"

DEPOIS (centralizado):
    # Tudo em models.py
    config = SubscriptionPlanType.get_config('monthly')
    amount = config['amount']  # Decimal('500.00')
"""

