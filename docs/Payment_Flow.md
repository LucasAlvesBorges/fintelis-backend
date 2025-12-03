# Fluxo de Pagamento - Mercado Pago

## Visão Geral

O sistema de pagamento do Fintelis suporta dois métodos:
1. **Cartão de Crédito/Débito** - Assinatura recorrente automática
2. **PIX** - Pagamento único que requer renovação manual

---

## 1. Fluxo de Pagamento com Cartão de Crédito

### Frontend (`web/src/pages/Payment/Checkout.jsx`)

```javascript
// 1. Coletar dados do cartão (frontend apenas coleta, não processa)
const [expMonth, expYear] = formData.expirationDate.split('/')
const docNumberClean = formData.docNumber.replace(/\D/g, '')

// 2. Enviar dados do cartão para backend processar com segurança
const response = await subscriptionService.createSubscription({
  company_id: company.id,
  plan_id: selectedPlan.id,
  payer_email: formData.email,
  billing_day: formData.billingDay,
  card_data: {
    card_number: formData.cardNumber.replace(/\s/g, ''),
    cardholder_name: formData.cardholderName,
    expiration_month: expMonth,
    expiration_year: '20' + expYear,
    security_code: formData.securityCode,
    identification_type: docNumberClean.length === 11 ? 'CPF' : 'CNPJ',
    identification_number: docNumberClean
  }
})
```

**⚠️ IMPORTANTE:** O frontend **NUNCA** usa chaves de API do Mercado Pago. Todo o processamento é feito no backend de forma segura.

### Backend (`api-fintelis/apps/payments/views.py`)

```python
# SubscriptionViewSet.create_subscription()

# 1. Receber dados do cartão do frontend (via HTTPS)
company = Company.objects.get(pk=company_id)
plan = SubscriptionPlan.objects.get(pk=plan_id)
card_data = validated_data['card_data']

# 2. Criar token do cartão no Mercado Pago (backend faz isso)
mp_service = get_mercadopago_service()
card_token_response = mp_service.create_card_token(
    card_number=card_data['card_number'],
    cardholder_name=card_data['cardholder_name'],
    expiration_month=card_data['expiration_month'],
    expiration_year=card_data['expiration_year'],
    security_code=card_data['security_code'],
    identification_type=card_data['identification_type'],
    identification_number=card_data['identification_number'],
)

# 3. Criar assinatura no Mercado Pago com token
mp_response = mp_service.create_preapproval(
    preapproval_plan_id=plan.preapproval_plan_id,
    payer_email=payer_email,
    card_token_id=card_token_response['id'],
)

# 4. Salvar assinatura no banco
subscription = Subscription.objects.create(
    company=company,
    plan=plan,
    preapproval_id=mp_response['id'],
    payer_email=payer_email,
    status=mp_response['status'],
    mercadopago_response=mp_response
)

# 5. Atualizar empresa
company.mercadopago_subscription_id = mp_response['id']
company.save()
```

**🔒 SEGURANÇA:** O backend usa a chave **privada** do Mercado Pago que nunca é exposta ao frontend.

---

## 2. Fluxo de Pagamento com PIX

### Frontend (`web/src/pages/Payment/Checkout.jsx`)

```javascript
// 1. Solicitar criação de pagamento PIX (pagamento único, não precisa de billing_day)
const response = await subscriptionService.createPixPayment({
  company_id: company.id,
  plan_type: selectedPlan.id,
  payer_email: formData.email
  // billing_day não é necessário para PIX (pagamento único)
})

// 2. Exibir QR Code e código PIX
<PixQRCode 
  pixCode={response.pix_code}
  qrCodeBase64={response.qr_code_base64}
/>

// 3. Polling para verificar status (ou aguardar webhook)
const checkStatus = setInterval(async () => {
  const status = await subscriptionService.checkPaymentStatus(response.payment_id)
  if (status === 'completed') {
    clearInterval(checkStatus)
    showSuccessMessage()
  }
}, 5000) // Verifica a cada 5 segundos
```

### Backend (`api-fintelis/apps/payments/views.py`)

```python
# Nova action para PIX
@action(detail=False, methods=['post'], url_path='create-pix')
def create_pix_payment(self, request):
    """
    Cria pagamento PIX único no Mercado Pago.
    Não é recorrente - requer renovação manual.
    """
    company_id = request.data.get('company_id')
    plan_type = request.data.get('plan_type')
    payer_email = request.data.get('payer_email')
    # billing_day não é necessário para PIX (pagamento único)
    
    company = Company.objects.get(pk=company_id)
    plan = SubscriptionPlan.objects.get(pk=plan_id)
    config = SubscriptionPlanType.get_config(plan.subscription_plan_type, billing_day)
    
    # Criar pagamento PIX no Mercado Pago
    mp_service = get_mercadopago_service()
    payment_data = {
        'transaction_amount': float(config['amount']),
        'description': config['reason'],
        'payment_method_id': 'pix',
        'payer': {
            'email': payer_email,
        }
    }
    
    mp_response = mp_service.create_payment(payment_data)
    
    # Salvar pagamento
    payment = Payment.objects.create(
        company=company,
        payment_id=mp_response['id'],
        amount=config['amount'],
        subscription_plan=plan.subscription_plan_type,
        payment_method=Payment.PaymentMethod.PIX,
        status=Payment.Status.PENDING,
        pix_code=mp_response['point_of_interaction']['transaction_data']['qr_code'],
        gateway_response=mp_response
    )
    
    return Response({
        'payment_id': payment.id,
        'pix_code': mp_response['point_of_interaction']['transaction_data']['qr_code'],
        'qr_code_base64': mp_response['point_of_interaction']['transaction_data']['qr_code_base64'],
        'expiration_date': mp_response['date_of_expiration']
    })
```

### Webhook Handler (`api-fintelis/apps/payments/webhooks.py`)

```python
class MercadoPagoWebhookView(APIView):
    def post(self, request):
        # Quando PIX é pago, Mercado Pago envia notificação
        event_type = request.data.get('type')
        
        if event_type == 'payment':
            payment_id = request.data.get('data', {}).get('id')
            
            # Buscar detalhes do pagamento
            mp_service = get_mercadopago_service()
            payment_info = mp_service.get_payment(payment_id)
            
            # Atualizar status no banco
            payment = Payment.objects.get(payment_id=payment_id)
            
            if payment_info['status'] == 'approved':
                payment.status = Payment.Status.COMPLETED
                payment.transaction_id = payment_info.get('transaction_id')
                payment.save()
                
                # Ativar assinatura da empresa
                company = payment.company
                company.subscription_active = True
                company.subscription_plan = payment.subscription_plan
                company.subscription_expires_at = timezone.now() + timedelta(
                    days=SubscriptionPlanType.get_config(payment.subscription_plan)['duration_days']
                )
                company.save()
```

---

## 3. Diferenças entre Métodos

### Cartão de Crédito
- ✅ **Recorrente automático**: Mercado Pago cobra automaticamente
- ✅ **Gestão simplificada**: Cliente não precisa renovar manualmente
- ✅ **Preapproval Plan**: Usa o sistema de assinaturas do MP
- ❌ **Requer dados sensíveis**: Cartão, CVV, etc

### PIX
- ✅ **Simples e rápido**: Pagamento instantâneo
- ✅ **Sem dados sensíveis**: Não precisa de cartão
- ✅ **Amplamente aceito**: Todo banco brasileiro suporta
- ❌ **Não é recorrente**: Cada pagamento precisa de novo QR Code
- ❌ **Requer renovação manual**: Cliente precisa pagar todo mês/trimestre/etc

---

## 4. Campos Necessários

### Cartão de Crédito (Recorrente):
- `company_id` (UUID) ✅
- `plan_id` (UUID) ✅
- `payer_email` (string) ✅
- `billing_day` (int: 1, 5, 10, 15, 20, 25) ✅ **Obrigatório para assinatura recorrente**
- `card_data` (object) ✅
  - `card_number` (string)
  - `cardholder_name` (string)
  - `expiration_month` (string)
  - `expiration_year` (string)
  - `security_code` (string)
  - `identification_type` (string: 'CPF' | 'CNPJ')
  - `identification_number` (string)

### PIX (Pagamento Único):
- `company_id` (UUID) ✅
- `plan_type` (string) ✅
- `payer_email` (string) ✅
- `billing_day` ❌ **NÃO necessário** (PIX é pagamento único, não recorrente)

---

## 5. Próximos Passos para Implementação

### Frontend:
1. ✅ Interface para escolher método (PIX ou Cartão) - **CONCLUÍDO**
2. ✅ Formulário condicional baseado no método - **CONCLUÍDO**
3. ✅ Carregar SDK do Mercado Pago via CDN - **CONCLUÍDO**
4. ✅ Implementar criação de token do cartão - **CONCLUÍDO**
5. ✅ Implementar exibição de QR Code PIX - **CONCLUÍDO**
6. ✅ Implementar polling para verificar pagamento PIX - **CONCLUÍDO**

### Backend:
1. ✅ Modelo Payment suporta PIX e Cartão - **CONCLUÍDO**
2. ✅ Serializer aceita billing_day - **CONCLUÍDO**
3. ✅ Criar endpoint `/payments/subscriptions/create-pix/` - **CONCLUÍDO**
4. ✅ Atualizar webhook para processar pagamentos PIX - **CONCLUÍDO**
5. ✅ Adicionar método no MercadoPagoService para criar pagamento PIX - **CONCLUÍDO**

---

## 6. Variáveis de Ambiente Necessárias

### Backend (`api-fintelis/.env`):
```env
MERCADOPAGO_ACCESS_TOKEN=TEST-123456789-seu-access-token-aqui
FRONTEND_URL=http://localhost:5173
```

### Frontend (`web/.env`):
```env
VITE_API_URL=http://localhost:8000/api/v1
```

**🔒 IMPORTANTE DE SEGURANÇA:**
- **NUNCA** coloque chaves do Mercado Pago no frontend
- O `ACCESS_TOKEN` é **secreto** e deve estar **APENAS** no backend
- A `PUBLIC_KEY` **NÃO É NECESSÁRIA** nesta implementação
- Todo processamento de pagamento é feito no backend via HTTPS

---

## 7. Configuração e Instalação

### Passo 1: Configurar Variáveis de Ambiente

1. **Backend** - Adicione ao `api-fintelis/.env`:
```env
MERCADOPAGO_ACCESS_TOKEN=TEST-123456789-seu-token
MERCADOPAGO_PUBLIC_KEY=TEST-abc123-sua-chave-publica
```

2. **Frontend** - Adicione ao `web/.env`:
```env
VITE_MERCADOPAGO_PUBLIC_KEY=TEST-abc123-sua-chave-publica
```

### Passo 2: Testar Integração

1. **Criar Plano de Assinatura:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/plans/create/ \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_plan_type": "monthly",
    "back_url": "http://localhost:5173/subscription",
    "billing_day": 10
  }'
```

2. **Testar Pagamento PIX:**
   - Acesse `/payment/checkout`
   - Selecione PIX
   - Preencha os dados
   - Gere o QR Code
   - Use app de teste do Mercado Pago para pagar

3. **Testar Cartão de Crédito:**
   - Cartões de teste: https://www.mercadopago.com.br/developers/pt/docs/testing/test-cards
   - Exemplo: `5031 4332 1540 6351` (Mastercard aprovado)

### Passo 3: Configurar Webhook (Produção)

1. Acesse o painel do Mercado Pago
2. Vá em "Notificações > Webhooks"
3. Adicione a URL: `https://seu-dominio.com/api/v1/payments/webhook/mercadopago/`
4. Selecione eventos: `payment` e `preapproval`

## 8. Estrutura de Resposta Esperada

### Cartão (Preapproval):
```json
{
  "subscription_id": "uuid",
  "preapproval_id": "abc123",
  "status": "authorized",
  "init_point": "https://mercadopago.com/...",
  "next_payment_date": "2025-01-10"
}
```

### PIX (Payment):
```json
{
  "payment_id": "uuid",
  "pix_code": "00020126580014br.gov.bcb.pix...",
  "qr_code_base64": "iVBORw0KGgoAAAANS...",
  "expiration_date": "2025-12-05T23:59:59Z",
  "status": "pending"
}
```

