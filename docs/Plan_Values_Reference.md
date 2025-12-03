# 📋 Referência de Valores dos Planos

## ✅ ÚNICA Fonte da Verdade

Todos os valores estão centralizados em:

```python
api-fintelis/apps/payments/models.py
└── class SubscriptionPlanType
    └── método get_config()
```

---

## 💰 Valores Atuais dos Planos

| Plano | Valor | Frequência | Duração | Dia Cobrança |
|-------|-------|------------|---------|--------------|
| **Mensal** | R$ 500,00 | 1 mês | 30 dias | Dia 10 |
| **Trimestral** | R$ 1.500,00 | 3 meses | 90 dias | Dia 10 |
| **Semestral** | R$ 3.000,00 | 6 meses | 180 dias | Dia 10 |
| **Anual** | R$ 6.000,00 | 12 meses | 365 dias | Dia 10 |

### Economia nos Planos Longos

- **Anual vs 12x Mensal**: R$ 6.000 vs R$ 6.000 (mesma coisa - considere adicionar desconto!)
- **Trimestral vs 3x Mensal**: R$ 1.500 vs R$ 1.500
- **Semestral vs 6x Mensal**: R$ 3.000 vs R$ 3.000

> 💡 **Sugestão**: Adicione descontos para planos longos (ex: Anual por R$ 5.500)

---

## 🔧 Como Alterar os Valores

### Passo 1: Edite o arquivo de modelos

```bash
api-fintelis/apps/payments/models.py
```

### Passo 2: Localize a classe SubscriptionPlanType

```python
class SubscriptionPlanType(models.TextChoices):
    # ...
    
    @classmethod
    def get_config(cls, plan_type):
        configs = {
            cls.MONTHLY.value: {
                'reason': 'Plano Mensal Fintelis',
                'amount': Decimal('500.00'),  # ← ALTERE AQUI
                'frequency': 1,
                'frequency_type': 'months',
                'billing_day': 10,
                'duration_days': 30,
            },
            # ... outros planos
        }
        return configs.get(plan_type, {})
```

### Passo 3: Altere os valores desejados

**Exemplo - Adicionar desconto de 10% no plano anual:**

```python
cls.ANNUAL.value: {
    'reason': 'Plano Anual Fintelis',
    'amount': Decimal('5400.00'),  # Era 6000, agora 10% off
    'frequency': 12,
    'frequency_type': 'months',
    'billing_day': 10,
    'duration_days': 365,
},
```

### Passo 4: Reinicie o servidor

```bash
# Se estiver rodando, reinicie
docker-compose restart app
# ou
python manage.py runserver
```

**⚠️ IMPORTANTE:** Planos já criados no Mercado Pago **não serão alterados automaticamente**. Apenas novos planos criados após a alteração terão os novos valores.

---

## 📖 Como Usar os Valores no Código

### 1. Obter valor de um plano

```python
from apps.payments.models import SubscriptionPlanType

# Obter apenas o valor
amount = SubscriptionPlanType.MONTHLY.get_amount()
# Retorna: Decimal('500.00')

# Obter configuração completa
config = SubscriptionPlanType.get_config('monthly')
# Retorna: {'reason': '...', 'amount': Decimal('500.00'), ...}
```

### 2. Listar todos os planos (para API)

```python
from apps.payments.models import SubscriptionPlanType

# Em uma view ou serializer
plans = []
for plan_type in SubscriptionPlanType:
    config = SubscriptionPlanType.get_config(plan_type.value)
    plans.append({
        'id': plan_type.value,
        'name': plan_type.label,
        'price': float(config['amount']),
        'frequency': config['frequency'],
        'duration_days': config['duration_days'],
    })

# Retornar para frontend
return Response({'plans': plans})
```

### 3. Usar em templates/admin

```python
from apps.payments.models import SubscriptionPlanType

# Obter label com preço
display = SubscriptionPlanType.MONTHLY.get_display_with_price()
# Retorna: "Mensal - R$ 500.00"
```

### 4. Calcular descontos

```python
monthly_config = SubscriptionPlanType.get_config('monthly')
annual_config = SubscriptionPlanType.get_config('annual')

monthly_price = monthly_config['amount']
annual_price = annual_config['amount']

# Se pagasse 12 meses separados
total_monthly = monthly_price * 12  # R$ 6000

# Economia
savings = total_monthly - annual_price  # R$ 0 (sem desconto ainda)
```

---

## 🗂️ Estrutura de Arquivos

```
api-fintelis/apps/payments/
├── models.py                    ← DEFINIÇÃO DOS VALORES (FONTE DA VERDADE)
│   └── SubscriptionPlanType
│       ├── MONTHLY, QUARTERLY, SEMIANNUAL, ANNUAL
│       ├── get_config(plan_type) → dict com valores
│       ├── get_all_configs() → todos os planos
│       ├── get_amount() → apenas o valor
│       └── get_display_with_price() → label formatado
│
├── views.py                     ← USA os valores de models.py
│   └── config = SubscriptionPlanType.get_config(plan_type)
│
├── serializers.py               ← USA os valores de models.py
├── admin.py                     ← USA os valores de models.py
└── plan_configs.py              ← EXEMPLOS de uso (documentação)
```

---

## 🎯 Vantagens da Centralização

### ✅ Antes (Ruim - Espalhado)

```python
# Em models.py
MONTHLY = "monthly", "Mensal (R$500)"

# Em views.py  
plan_configs = {
    'monthly': {'amount': Decimal('500.00')},
}

# Se mudar preço: precisa alterar 2 lugares ❌
```

### ✅ Depois (Bom - Centralizado)

```python
# Apenas em models.py
configs = {
    cls.MONTHLY.value: {
        'amount': Decimal('500.00'),
    }
}

# Se mudar preço: altera 1 lugar ✅
```

### Benefícios

1. **Consistência**: Impossível ter valores diferentes em lugares diferentes
2. **Manutenção**: Alterar valor em um único lugar
3. **Documentação**: Código autodocumentado com métodos claros
4. **Testabilidade**: Fácil criar testes unitários
5. **Escalabilidade**: Adicionar novos planos é simples

---

## 📊 Endpoints da API que Usam os Valores

| Endpoint | Usa Valores Para |
|----------|------------------|
| `GET /api/v1/payments/plans/` | Listar planos com preços |
| `POST /api/v1/payments/plans/create/` | Criar plano no MP com valores |
| `POST /api/v1/payments/subscriptions/create/` | Criar assinatura com valor |
| `GET /api/v1/companies/{id}/` | Mostrar plano atual da empresa |

---

## 🧪 Exemplos de Teste

```python
# test_plan_values.py
from decimal import Decimal
from apps.payments.models import SubscriptionPlanType

def test_monthly_plan_value():
    """Testa se o valor do plano mensal está correto"""
    config = SubscriptionPlanType.get_config('monthly')
    assert config['amount'] == Decimal('500.00')
    assert config['duration_days'] == 30

def test_all_plans_have_values():
    """Testa se todos os planos têm valores definidos"""
    for plan_type in SubscriptionPlanType:
        config = SubscriptionPlanType.get_config(plan_type.value)
        assert 'amount' in config
        assert config['amount'] > 0

def test_annual_plan_has_discount():
    """Testa se plano anual tem desconto (se implementar)"""
    monthly = SubscriptionPlanType.get_config('monthly')
    annual = SubscriptionPlanType.get_config('annual')
    
    yearly_if_monthly = monthly['amount'] * 12
    yearly_price = annual['amount']
    
    # Deve ter algum desconto
    assert yearly_price < yearly_if_monthly
```

---

## 🔄 Fluxo de Atualização de Valores

```
1. Desenvolvedor altera valor
   ↓ (em models.py)
2. Código é deployado
   ↓
3. Servidor reinicia
   ↓
4. Novo plano é criado via API
   ↓ (POST /plans/create/)
5. Mercado Pago recebe novo valor
   ↓
6. Plano criado com valor atualizado
   ↓
7. Frontend busca planos via API
   ↓
8. Usuário vê novo preço
```

**Observação:** Planos antigos no MP continuam com valores antigos. Para alterar, você precisa:
- Criar novo plano com novos valores
- Desativar plano antigo (status = 'inactive')
- Migrar assinaturas existentes (se necessário)

---

## 📝 Checklist de Alteração de Valores

- [ ] Editar `apps/payments/models.py`
- [ ] Alterar valores no método `get_config()`
- [ ] Executar testes: `python manage.py test apps.payments`
- [ ] Verificar se valores fazem sentido (descontos, proporcionalidade)
- [ ] Commitar alteração com mensagem clara
- [ ] Deploy da alteração
- [ ] Criar novos planos no MP (via API ou admin)
- [ ] Testar criação de assinatura com novos valores
- [ ] Atualizar documentação de preços (se houver site/landing page)
- [ ] Notificar equipe de vendas sobre mudança de preços

---

## 🆘 Troubleshooting

### "Os valores não mudaram no Mercado Pago"

**Causa:** Planos já criados no MP não mudam automaticamente.

**Solução:** 
1. Crie novos planos via API:
   ```bash
   POST /api/v1/payments/plans/create/
   ```
2. Desative planos antigos no admin Django
3. Atualize `init_point` nos links de checkout

### "Erro ao criar plano: valor inválido"

**Causa:** Mercado Pago tem valor mínimo (ex: R$ 1,00).

**Solução:** Certifique-se que `amount >= 1.00`

### "Frontend mostra valores antigos"

**Causa:** Cache do browser ou API não atualizada.

**Solução:**
1. Limpar cache do browser (Ctrl+Shift+R)
2. Verificar resposta da API no DevTools
3. Reiniciar servidor backend

---

**Última atualização:** Dezembro 2025  
**Versão:** 1.0

