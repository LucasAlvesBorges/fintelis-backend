# Boas Práticas de Segurança - Sistema de Pagamentos

## 🔒 Arquitetura Segura Implementada

### Princípio Fundamental
**O frontend NUNCA deve ter acesso a chaves de API de gateways de pagamento.**

---

## ✅ O que fizemos CERTO

### 1. **Backend Processa Tudo**
- ✅ Frontend apenas **coleta** dados do cartão
- ✅ Frontend envia dados para backend via **HTTPS**
- ✅ Backend cria token do cartão usando chave **privada**
- ✅ Backend processa pagamento no Mercado Pago
- ✅ Chaves de API nunca são expostas ao cliente

### 2. **Variáveis de Ambiente Seguras**
```env
# ✅ Backend (.env) - CORRETO
MERCADOPAGO_ACCESS_TOKEN=TEST-123456789-...  # Chave PRIVADA

# ✅ Frontend (.env) - CORRETO
VITE_API_URL=http://localhost:8000/api/v1    # Apenas URL da API
```

### 3. **Fluxo Seguro de Pagamento**
```
Cliente (Browser)
    ↓ [HTTPS]
    ↓ (dados do cartão)
    ↓
Backend (Servidor)
    ↓ [API do Mercado Pago]
    ↓ (usando chave privada)
    ↓
Mercado Pago
```

---

## ❌ O que NÃO fazer (Evitamos isso)

### 1. **NUNCA exponha chaves no Frontend**
```javascript
// ❌ ERRADO - NUNCA FAÇA ISSO!
const mp = new MercadoPago('TEST-sua-chave-publica')
```

### 2. **NUNCA use SDK de pagamento no Frontend**
```javascript
// ❌ ERRADO - NUNCA FAÇA ISSO!
import { loadMercadoPago } from '@mercadopago/sdk-js'
```

### 3. **NUNCA coloque chaves em variáveis de ambiente do Frontend**
```env
# ❌ ERRADO - NUNCA FAÇA ISSO!
VITE_MERCADOPAGO_PUBLIC_KEY=TEST-abc123...
VITE_MERCADOPAGO_ACCESS_TOKEN=TEST-123456...
```

**Por quê?** Qualquer variável `VITE_*` é exposta no bundle JavaScript e pode ser vista por qualquer usuário via DevTools.

---

## 🛡️ Proteções Implementadas

### 1. **Transmissão Segura**
- Dados do cartão trafegam via **HTTPS**
- Backend valida todos os campos antes de processar
- Serializers do DRF validam tipos e formatos

### 2. **Isolamento de Credenciais**
- `MERCADOPAGO_ACCESS_TOKEN` está **APENAS** no servidor
- Impossível acessar via JavaScript do navegador
- Não aparece em logs ou respostas de API

### 3. **Validação em Camadas**
```python
# Frontend - Validação básica
if (!formData.cardNumber || formData.cardNumber.length < 13) {
    errors.cardNumber = 'Número do cartão inválido'
}

# Backend - Validação robusta
class CardDataSerializer(serializers.Serializer):
    card_number = serializers.CharField(max_length=19, min_length=13)
    # ... mais validações
```

---

## 📊 Comparação: Antes vs Depois

| Aspecto | ❌ Implementação Insegura | ✅ Implementação Atual |
|---------|---------------------------|------------------------|
| **SDK no Frontend** | Sim (vulnerável) | Não (seguro) |
| **Chave Pública exposta** | Sim (risco) | Não (protegido) |
| **Tokenização** | Frontend | Backend |
| **Acesso à API MP** | Direto do browser | Apenas servidor |
| **Chave Privada** | Potencialmente exposta | Isolada no servidor |
| **Auditoria** | Difícil | Centralizada no backend |

---

## 🔍 Como Verificar se está Seguro

### 1. **Verifique o Bundle do Frontend**
```bash
cd web
npm run build
grep -r "MERCADOPAGO" dist/
# Deve retornar VAZIO (nenhuma chave encontrada)
```

### 2. **Inspecione Variáveis de Ambiente**
```bash
# Frontend
cat web/.env
# Deve conter APENAS: VITE_API_URL

# Backend
cat api-fintelis/.env
# Deve conter: MERCADOPAGO_ACCESS_TOKEN
```

### 3. **Teste no DevTools**
1. Abra o navegador
2. Pressione F12 (DevTools)
3. Vá em Console
4. Digite: `console.log(import.meta.env)`
5. **Não deve aparecer** nenhuma chave do Mercado Pago

---

## 🚨 Alertas de Segurança

### Se você ver isso, CORRIJA IMEDIATAMENTE:

#### ⚠️ Alerta 1: Chave no Frontend
```javascript
// 🚨 VULNERABILIDADE CRÍTICA
const MERCADOPAGO_KEY = 'TEST-123456...'
```
**Solução:** Remova e mova para backend.

#### ⚠️ Alerta 2: Variável VITE exposta
```env
# 🚨 VULNERABILIDADE CRÍTICA
VITE_MERCADOPAGO_PUBLIC_KEY=TEST-abc123...
```
**Solução:** Remova do `.env` do frontend.

#### ⚠️ Alerta 3: SDK carregado no Cliente
```html
<!-- 🚨 VULNERABILIDADE CRÍTICA -->
<script src="https://sdk.mercadopago.com/js/v2"></script>
```
**Solução:** Remova o script do HTML.

---

## 📝 Checklist de Segurança

Antes de fazer deploy em produção:

- [ ] Frontend **NÃO** tem chaves de API
- [ ] Frontend **NÃO** carrega SDK do Mercado Pago
- [ ] Backend usa **HTTPS** (TLS/SSL)
- [ ] `MERCADOPAGO_ACCESS_TOKEN` está no `.env` do **backend**
- [ ] `.env` está no `.gitignore`
- [ ] Credenciais de **teste** foram trocadas por **produção**
- [ ] Webhook está configurado no painel do Mercado Pago
- [ ] Logs **não** mostram dados de cartão completos
- [ ] Rate limiting está ativo nas rotas de pagamento
- [ ] CORS está configurado corretamente

---

## 🎯 Conclusão

A implementação atual segue as **melhores práticas** de segurança da indústria:

✅ **PCI DSS Compliance:** Dados de cartão não são armazenados
✅ **Separation of Concerns:** Frontend UI, Backend lógica
✅ **Least Privilege:** Frontend tem acesso mínimo necessário
✅ **Defense in Depth:** Múltiplas camadas de validação

**Resultado:** Sistema seguro e pronto para produção! 🔒

