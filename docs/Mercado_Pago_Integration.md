# Integração Mercado Pago - Assinaturas

## Documentação da Integração de Assinaturas com Mercado Pago

**Data:** 03/12/2025  
**Versão:** 1.0

---

## 1. VISÃO GERAL

Esta integração permite que o sistema Fintelis crie e gerencie planos de assinatura recorrente através do Mercado Pago.

### 1.1 Funcionalidades Implementadas

- ✅ Criação de planos de assinatura
- ✅ Criação de assinaturas para empresas
- ✅ Webhook para receber notificações de pagamento
- ✅ Cancelamento de assinaturas
- ✅ Trial gratuito de 15 dias
- ✅ Suporte a múltiplos planos (Mensal, Trimestral, Semestral, Anual)

---

## 2. CONFIGURAÇÃO

### 2.1 Variáveis de Ambiente

Adicione as seguintes variáveis no arquivo `.env`:

```bash
# Mercado Pago - Credenciais de Teste
MERCADOPAGO_ACCESS_TOKEN=TEST-7288159-030320-c8c9b4b932d0fd9b22-691
MERCADOPAGO_PUBLIC_KEY=TEST-your-public-key

# Mercado Pago - Credenciais de Produção (quando disponível)
# MERCADOPAGO_ACCESS_TOKEN=APP_USR-your-production-token
# MERCADOPAGO_PUBLIC_KEY=APP_USR-your-production-public-key
```

### 2.2 Instalação de Dependências

```bash
pip install mercadopago==2.2.1
```

### 2.3 Migração do Banco de Dados

```bash
python manage.py makemigrations payments
python manage.py makemigrations companies
python manage.py migrate
```

---

## 3. MODELOS DE DADOS

### 3.1 SubscriptionPlan

Armazena os planos de assinatura criados no Mercado Pago.

**Campos principais:**
- `preapproval_plan_id`: ID do plano no Mercado Pago
- `reason`: Descrição do plano
- `subscription_plan_type`: Tipo (monthly, quarterly, semiannual, annual)
- `transaction_amount`: Valor da cobrança
- `frequency` / `frequency_type`: Frequência de cobrança
- `init_point`: URL do checkout Mercado Pago

### 3.2 Subscription

Armazena as assinaturas ativas das empresas.

**Campos principais:**
- `company`: Empresa assinante
- `plan`: Plano contratado
- `preapproval_id`: ID da assinatura no Mercado Pago
- `status`: pending, authorized, paused, cancelled
- `next_payment_date`: Próxima data de cobrança

### 3.3 Company (atualizado)

Novos campos adicionados:
- `mercadopago_preapproval_plan_id`: ID do plano no MP
- `mercadopago_subscription_id`: ID da assinatura ativa no MP

---

## 4. API ENDPOINTS

### 4.1 Listar Planos Disponíveis

```http
GET /api/v1/payments/plans/
Authorization: Bearer {token}
```

**Resposta:**
```json
[
  {
    "id": "uuid",
    "preapproval_plan_id": "2c938084726fca480172750000000000",
    "reason": "Plano Mensal Fintelis - R$ 500",
    "subscription_plan_type": "monthly",
    "transaction_amount": "500.00",
    "frequency": 1,
    "frequency_type": "months",
    "init_point": "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_plan_id=...",
    "status": "active"
  }
]
```

### 4.2 Criar Novo Plano

```http
POST /api/v1/payments/plans/create/
Authorization: Bearer {token}
Content-Type: application/json

{
  "subscription_plan_type": "monthly",
  "back_url": "https://yoursite.com/success"
}
```

**Resposta:** 201 Created

### 4.3 Criar Assinatura para Empresa

```http
POST /api/v1/payments/subscriptions/create/
Authorization: Bearer {token}
Content-Type: application/json

{
  "company_id": "uuid-da-empresa",
  "plan_id": "uuid-do-plano",
  "payer_email": "cliente@example.com"
}
```

**Resposta:**
```json
{
  "subscription": {
    "id": "uuid",
    "preapproval_id": "abc123",
    "status": "pending",
    ...
  },
  "init_point": "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_id=..."
}
```

**Fluxo:**
1. Backend cria assinatura no MP
2. Retorna `init_point` (URL do checkout)
3. Frontend redireciona usuário para o checkout
4. Usuário preenche dados de pagamento no MP
5. MP redireciona para `back_url` após conclusão
6. MP envia webhook com status da assinatura

### 4.4 Cancelar Assinatura

```http
POST /api/v1/payments/subscriptions/{id}/cancel/
Authorization: Bearer {token}
```

**Resposta:** 200 OK

### 4.5 Listar Assinaturas da Empresa

```http
GET /api/v1/payments/subscriptions/
Authorization: Bearer {token}
```

---

## 5. WEBHOOKS

### 5.1 Configurar Webhook no Mercado Pago

1. Acesse: https://www.mercadopago.com.br/developers/panel/app
2. Selecione sua aplicação
3. Vá em "Webhooks"
4. Adicione a URL: `https://seu-dominio.com/api/v1/payments/webhook/mercadopago/`
5. Selecione eventos:
   - `preapproval` (mudanças em assinaturas)
   - `authorized_payment` (pagamentos autorizados)

### 5.2 Endpoint do Webhook

```http
POST /api/v1/payments/webhook/mercadopago/
Content-Type: application/json

{
  "type": "preapproval",
  "data": {
    "id": "abc123"
  }
}
```

**Processamento:**
1. Recebe notificação do MP
2. Busca dados atualizados da assinatura
3. Atualiza status no banco de dados
4. Se status = `authorized`, ativa assinatura da empresa
5. Se status = `cancelled`, desativa assinatura

---

## 6. PLANOS DISPONÍVEIS

| Plano | Valor | Frequência | Billing Day | Trial |
|-------|-------|------------|-------------|-------|
| Mensal | R$ 500 | 1 mês | Dia 10 | 15 dias |
| Trimestral | R$ 1.500 | 3 meses | Dia 10 | 15 dias |
| Semestral | R$ 3.000 | 6 meses | Dia 10 | 15 dias |
| Anual | R$ 6.000 | 12 meses | Dia 10 | 15 dias |

**Observações:**
- `billing_day`: Dia do mês para cobrança (sempre dia 10)
- `free_trial`: 15 dias gratuitos para testar
- `currency_id`: BRL (Real Brasileiro)

---

## 7. FLUXO DE ASSINATURA

### 7.1 Fluxo Completo

```
1. [Frontend] Usuário escolhe plano
   ↓
2. [Backend] POST /api/v1/payments/subscriptions/create/
   ↓
3. [Backend] Cria assinatura no Mercado Pago
   ↓
4. [Backend] Retorna init_point (URL do checkout)
   ↓
5. [Frontend] Redireciona para init_point
   ↓
6. [Mercado Pago] Usuário preenche dados de pagamento
   ↓
7. [Mercado Pago] Redireciona para back_url
   ↓
8. [Mercado Pago] Envia webhook para backend
   ↓
9. [Backend] Processa webhook e ativa assinatura
   ↓
10. [Backend] Atualiza Company.subscription_active = True
```

### 7.2 Diagrama de Estados da Assinatura

```
[pending] → [authorized] → [paused] → [cancelled]
    ↓            ↓
  [cancelled] [cancelled]
```

---

## 8. TESTES

### 8.1 Cartões de Teste

Use os cartões de teste do Mercado Pago:

| Cartão | Número | CVV | Validade | Resultado |
|--------|--------|-----|----------|-----------|
| Mastercard | 5031 4332 1540 6351 | 123 | 11/25 | Aprovado |
| Visa | 4235 6477 2802 5682 | 123 | 11/25 | Aprovado |
| Mastercard | 5031 7557 3453 0604 | 123 | 11/25 | Recusado |

**Documentação completa:** https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/additional-content/test-cards

### 8.2 Testar Webhook Localmente

Use ngrok para expor localhost:

```bash
ngrok http 8000
```

Configure a URL do webhook no painel do MP:
```
https://your-ngrok-url.ngrok.io/api/v1/payments/webhook/mercadopago/
```

---

## 9. SEGURANÇA

### 9.1 Validação de Webhook

**⚠️ IMPORTANTE:** Em produção, implemente validação de assinatura do webhook:

```python
# Verificar se requisição vem realmente do Mercado Pago
# Documentação: https://www.mercadopago.com.br/developers/pt/docs/subscriptions/integration-configuration/notifications
```

### 9.2 Tokens de Acesso

- **Teste:** Começam com `TEST-`
- **Produção:** Começam com `APP_USR-`
- **Nunca commitar** tokens em repositórios públicos
- Usar variáveis de ambiente

---

## 10. ADMIN DJANGO

### 10.1 Gerenciar Planos

Acesse: `/admin/payments/subscriptionplan/`

**Ações disponíveis:**
- Visualizar planos criados
- Ver init_point para compartilhar
- Desativar planos (status = inactive)

### 10.2 Gerenciar Assinaturas

Acesse: `/admin/payments/subscription/`

**Ações disponíveis:**
- Visualizar todas as assinaturas
- Ativar manualmente (action: "Ativar assinaturas selecionadas")
- Cancelar manualmente (action: "Cancelar assinaturas selecionadas")
- Ver próxima data de pagamento

---

## 11. TROUBLESHOOTING

### 11.1 Erro: "MERCADOPAGO_ACCESS_TOKEN não configurado"

**Solução:** Adicione a variável no `.env`:
```bash
MERCADOPAGO_ACCESS_TOKEN=TEST-your-token
```

### 11.2 Webhook não está sendo recebido

**Checklist:**
- [ ] URL do webhook está correta no painel do MP
- [ ] Servidor está acessível publicamente (use ngrok para testes)
- [ ] Eventos corretos estão selecionados (preapproval, authorized_payment)
- [ ] Verificar logs do servidor

### 11.3 Assinatura não ativa após pagamento

**Possíveis causas:**
- Webhook não foi processado
- Status no MP ainda está "pending"
- Erro no processamento do webhook (verificar logs)

**Solução manual:**
1. Acesse `/admin/payments/subscription/`
2. Selecione a assinatura
3. Use action "Ativar assinaturas selecionadas"

---

## 12. PRÓXIMOS PASSOS

### 12.1 Melhorias Futuras

- [ ] Implementar validação de assinatura do webhook
- [ ] Adicionar logs estruturados (ex: Sentry)
- [ ] Criar dashboard de métricas de assinaturas
- [ ] Implementar retry automático para webhooks falhados
- [ ] Adicionar notificações por email (assinatura ativa, cancelada, pagamento recebido)
- [ ] Implementar upgrade/downgrade de planos
- [ ] Adicionar cupons de desconto

### 12.2 Produção

Antes de ir para produção:
1. Trocar tokens de teste por tokens de produção
2. Configurar webhook em produção
3. Testar fluxo completo com cartão real
4. Implementar monitoramento de webhooks
5. Configurar backup de dados de assinaturas

---

## 13. REFERÊNCIAS

- **API Mercado Pago:** https://www.mercadopago.com.br/developers/pt/reference/subscriptions/_preapproval_plan/post
- **Documentação de Assinaturas:** https://www.mercadopago.com.br/developers/pt/docs/subscriptions/integration-configuration
- **SDK Python:** https://github.com/mercadopago/sdk-python
- **Cartões de Teste:** https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/additional-content/test-cards

---

**Documento criado para auxiliar na integração e manutenção do sistema de assinaturas.**

