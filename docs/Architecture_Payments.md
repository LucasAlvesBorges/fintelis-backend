# Arquitetura do Sistema de Pagamentos

## Separação de Responsabilidades

### 1. App `companies` - Dados da Empresa

O modelo `Company` mantém apenas o **estado atual** da assinatura:

```python
class Company(TimeStampedModel):
    # ... outros campos ...
    
    # Estado da assinatura (gerenciado pelo app payments)
    subscription_active: bool          # Se tem acesso ativo
    subscription_expires_at: datetime  # Quando expira
    subscription_plan: str             # Qual plano (monthly, quarterly, etc)
    mercadopago_subscription_id: str   # ID no Mercado Pago (opcional)
```

**Responsabilidades:**
- ✅ Armazenar estado atual da assinatura
- ✅ Verificar se empresa tem acesso (`has_active_access`)
- ✅ Gerenciar período de trial
- ❌ NÃO define os tipos de planos
- ❌ NÃO gerencia pagamentos

### 2. App `payments` - Gestão de Assinaturas

O app `payments` é responsável por **toda a lógica de assinaturas**:

```python
# Definição centralizada dos tipos de planos
class SubscriptionPlanType(models.TextChoices):
    MONTHLY = "monthly", "Mensal (R$500)"
    QUARTERLY = "quarterly", "Trimestral (R$1500)"
    SEMIANNUAL = "semiannual", "Semestral (R$3000)"
    ANNUAL = "annual", "Anual (R$6000)"

# Templates de planos no Mercado Pago
class SubscriptionPlan(models.Model):
    preapproval_plan_id: str  # ID no MP
    subscription_plan_type: str  # Referência ao SubscriptionPlanType
    transaction_amount: Decimal
    frequency: int
    init_point: str  # URL do checkout

# Assinaturas ativas das empresas
class Subscription(models.Model):
    company: ForeignKey  # Qual empresa
    plan: ForeignKey     # Qual plano
    preapproval_id: str  # ID no MP
    status: str          # pending, authorized, cancelled
    
    def activate(self):
        """Ativa assinatura e atualiza Company"""
        self.company.subscription_active = True
        self.company.subscription_plan = self.plan.subscription_plan_type
        self.company.save()

# Histórico de pagamentos individuais
class Payment(models.Model):
    company: ForeignKey
    subscription_plan: str  # Referência ao SubscriptionPlanType
    amount: Decimal
    status: str
```

**Responsabilidades:**
- ✅ Definir tipos de planos disponíveis (`SubscriptionPlanType`)
- ✅ Criar planos no Mercado Pago (`SubscriptionPlan`)
- ✅ Gerenciar assinaturas (`Subscription`)
- ✅ Registrar pagamentos (`Payment`)
- ✅ Atualizar estado da empresa quando assinatura muda

---

## Fluxo de Dados

### Criação de Assinatura

```
1. Frontend solicita criação
   ↓
2. PaymentViewSet.create_subscription()
   ↓
3. Cria Subscription no banco
   ↓
4. Cria assinatura no Mercado Pago
   ↓
5. Retorna init_point para checkout
   ↓
6. Usuário paga no Mercado Pago
   ↓
7. Webhook recebe notificação
   ↓
8. Subscription.activate() é chamado
   ↓
9. Company.subscription_active = True
```

### Verificação de Acesso

```
1. Request chega ao backend
   ↓
2. Middleware verifica Company
   ↓
3. Company.has_active_access() é chamado
   ↓
4. Verifica:
   - Trial ainda válido? ✓
   - Assinatura ativa? ✓
   - Assinatura não expirou? ✓
   ↓
5. Permite ou nega acesso
```

---

## Importação Entre Apps

### ✅ Correto: payments → companies

```python
# Em apps/payments/models.py
class Subscription(models.Model):
    company = models.ForeignKey(
        'companies.Company',  # String reference (evita import circular)
        on_delete=models.CASCADE,
    )
```

### ✅ Correto: companies → payments (tipos)

```python
# Em apps/companies/serializers.py (se necessário)
from apps.payments.models import SubscriptionPlanType

class CompanySerializer(serializers.ModelSerializer):
    subscription_plan_display = serializers.SerializerMethodField()
    
    def get_subscription_plan_display(self, obj):
        if obj.subscription_plan:
            return SubscriptionPlanType(obj.subscription_plan).label
        return None
```

### ❌ Evitar: Dependência circular

```python
# EVITAR: companies/models.py importando payments/models.py
# e payments/models.py importando companies/models.py

# Use string references em ForeignKeys:
company = models.ForeignKey('companies.Company', ...)
```

---

## Vantagens desta Arquitetura

### 1. **Separação Clara de Responsabilidades**
- `companies`: Estado atual (o que a empresa tem)
- `payments`: Gestão de assinaturas (como a empresa conseguiu)

### 2. **Facilita Mudanças Futuras**
- Trocar Mercado Pago por outro gateway? Apenas muda `payments`
- Adicionar novos planos? Apenas atualiza `SubscriptionPlanType`
- Mudar lógica de trial? Apenas muda `Company.has_active_access`

### 3. **Evita Duplicação**
- `SubscriptionPlanType` é a **única fonte da verdade** para tipos de planos
- Outros apps importam de `payments` quando necessário

### 4. **Testabilidade**
- Pode testar `payments` sem depender de `companies`
- Pode testar `Company.has_active_access` sem depender de Mercado Pago

---

## Exemplo de Uso

### No Admin Django

```python
# apps/companies/admin.py
from apps.payments.models import SubscriptionPlanType

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'subscription_plan', 'subscription_active')
    
    def get_subscription_plan_display(self, obj):
        if obj.subscription_plan:
            return SubscriptionPlanType(obj.subscription_plan).label
        return '-'
```

### Em Serializers

```python
# apps/companies/serializers.py
from apps.payments.models import SubscriptionPlanType

class CompanySerializer(serializers.ModelSerializer):
    subscription_plan_choices = serializers.SerializerMethodField()
    
    def get_subscription_plan_choices(self, obj):
        return [
            {'value': choice[0], 'label': choice[1]}
            for choice in SubscriptionPlanType.choices
        ]
```

### Em Views

```python
# apps/companies/views.py
from apps.payments.models import SubscriptionPlanType

class CompanyViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['get'])
    def subscription_info(self, request, pk=None):
        company = self.get_object()
        
        return Response({
            'active': company.subscription_active,
            'plan': company.subscription_plan,
            'plan_label': SubscriptionPlanType(company.subscription_plan).label if company.subscription_plan else None,
            'expires_at': company.subscription_expires_at,
        })
```

---

## Checklist de Migração

Após as mudanças, execute:

- [ ] `python manage.py makemigrations companies`
- [ ] `python manage.py makemigrations payments`
- [ ] `python manage.py migrate`
- [ ] Testar criação de assinatura
- [ ] Testar webhook do Mercado Pago
- [ ] Verificar admin Django

---

## Resumo

| Conceito | Onde Está | Propósito |
|----------|-----------|-----------|
| **Tipos de Planos** | `payments.SubscriptionPlanType` | Definição centralizada |
| **Estado da Assinatura** | `companies.Company` | O que a empresa tem agora |
| **Templates de Planos** | `payments.SubscriptionPlan` | Planos criados no MP |
| **Assinaturas Ativas** | `payments.Subscription` | Relacionamento empresa-plano |
| **Histórico de Pagamentos** | `payments.Payment` | Registro de transações |

**Princípio:** `companies` sabe **o quê**, `payments` sabe **como**.

