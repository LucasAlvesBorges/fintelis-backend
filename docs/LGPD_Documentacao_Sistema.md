# Documentação LGPD - Sistema Fintelis
## Documento para Elaboração de Termos e Condições e Política de Privacidade

**Data de Criação:** 03/12/2025  
**Versão:** 1.0  
**Sistema:** Fintelis - SaaS ERP Multi-Tenant

---

## 1. IDENTIFICAÇÃO DO SISTEMA

### 1.1 Descrição Geral
O **Fintelis** é um sistema SaaS (Software as a Service) de ERP voltado para gestão financeira e de inventário de pequenas e médias empresas, operando em modelo **multi-tenant** (multi-empresa).

### 1.2 Arquitetura Tecnológica
- **Backend:** Django Rest Framework (DRF) 4.2.7
- **Banco de Dados:** PostgreSQL 15
- **Cache/Fila:** Redis 7
- **Containerização:** Docker
- **Processamento Assíncrono:** Celery 5.3.6

---

## 2. DADOS PESSOAIS COLETADOS

### 2.1 Dados de Usuários da Plataforma (Tipo: PLATAFORMA)

#### 2.1.1 Dados de Cadastro
| Campo | Tipo | Obrigatório | Finalidade | Sensibilidade |
|-------|------|-------------|------------|---------------|
| `first_name` | String (150 char) | Sim | Identificação do usuário | Pessoal |
| `last_name` | String (150 char) | Sim | Identificação do usuário | Pessoal |
| `email` | Email (255 char) | Sim | Autenticação e comunicação | Pessoal |
| `phone_number` | String (20 char) | Não | Comunicação secundária | Pessoal |
| `password` | Hash (128 char) | Sim | Autenticação | Sensível - Criptografado |
| `id` | UUID | Automático | Identificação única | Técnico |
| `created_at` | DateTime | Automático | Auditoria | Técnico |
| `updated_at` | DateTime | Automático | Auditoria | Técnico |

**Validações Aplicadas:**
- Nome e sobrenome: Apenas letras e espaços (Regex: `^[A-Za-zÀ-ÖØ-öø-ÿ]+(?: [A-Za-zÀ-ÖØ-öø-ÿ]+)*$`)
- Email: Validação RFC 5322
- Senha: Hash usando algoritmo Django (PBKDF2 + SHA256)

#### 2.1.2 Dados de Sessão e Autenticação
| Campo | Tipo | Armazenamento | Finalidade |
|-------|------|---------------|------------|
| `access_token` | JWT | Cookie HttpOnly | Autenticação de sessão (12h) |
| `refresh_token` | JWT | Cookie HttpOnly | Renovação de sessão (24h) |
| `company_access_token` | JWT | Cookie HttpOnly | Vinculação empresa-usuário (12h) |

**Configurações de Segurança dos Cookies:**
- `HttpOnly`: True (não acessível via JavaScript)
- `Secure`: Configurável por ambiente
- `SameSite`: Lax (proteção CSRF)

### 2.2 Dados de Operadores (Tipo: OPERADOR)

Usuários operadores são criados para registro de vendas/operações, **sem capacidade de login**.

| Campo | Obrigatório | Finalidade |
|-------|-------------|------------|
| `first_name` | Sim | Identificação em histórico de vendas |
| `last_name` | Sim | Identificação em histórico de vendas |
| `email` | Não | Email placeholder gerado automaticamente |
| `operator_company` | Sim | Vínculo com empresa específica |

**Observação:** Operadores não possuem senha utilizável (`set_unusable_password()`).

### 2.3 Dados de Membros (Membership)

Vínculo entre usuários e empresas no sistema multi-tenant.

| Campo | Finalidade |
|-------|------------|
| `user_id` | Identificação do usuário |
| `company_id` | Identificação da empresa |
| `role` | Controle de permissões (admin, financials, stock_manager, human_resources, accountability) |
| `created_at` / `updated_at` | Auditoria |

---

## 3. DADOS EMPRESARIAIS COLETADOS

### 3.1 Dados da Empresa (Company)

| Campo | Tipo | Obrigatório | Finalidade | Sensibilidade |
|-------|------|-------------|------------|---------------|
| `name` | String (255) | Sim | Razão social da empresa | Empresarial |
| `cnpj` | String (255) | Sim | Identificação fiscal (Brasil) | Empresarial - Público |
| `email` | Email (255) | Sim | Contato corporativo | Empresarial |
| `trial_ends_at` | DateTime | Não | Controle de período trial (15 dias) | Comercial |
| `subscription_active` | Boolean | Sim | Status de assinatura ativa | Comercial |
| `subscription_expires_at` | DateTime | Não | Validade da assinatura | Comercial |
| `subscription_plan` | Enum | Não | Plano contratado (monthly, quarterly, semiannual, annual) | Comercial |
| `id` | UUID | Automático | Identificação única | Técnico |
| `created_at` / `updated_at` | DateTime | Automático | Auditoria | Técnico |

**Validação CNPJ:**
- Frontend: Formatação automática (XX.XXX.XXX/XXXX-XX)
- Frontend: Validação de dígitos verificadores
- Backend: Unicidade por empresa

### 3.2 Centros de Custo (CostCenter)

| Campo | Finalidade |
|-------|------------|
| `company_id` | Vínculo com empresa (multi-tenant) |
| `name` | Nome do centro de custo |
| `code` | Código hierárquico gerado automaticamente |
| `parent_id` | Hierarquia de centros de custo |

### 3.3 Convites (Invitation)

| Campo | Finalidade | Retenção |
|-------|------------|----------|
| `company_id` | Empresa que enviou o convite | Permanente |
| `user_id` | Usuário existente convidado (se aplicável) | Permanente |
| `email` | Email do convidado | Permanente |
| `role` | Função oferecida | Permanente |
| `status` | Estado (pending, accepted, rejected, expired) | Permanente |
| `invited_by` | Usuário que enviou o convite | Permanente |
| `responded_at` | Data/hora da resposta | Permanente |

---

## 4. DADOS TRANSACIONAIS/OPERACIONAIS

### 4.1 Módulo Financeiro

#### 4.1.1 Bancos e Contas Bancárias (BankAccount)
- `company_id` (vínculo multi-tenant)
- `bank_details` (relacionamento com cadastro de bancos)
- `name`, `type` (conta_corrente, conta_poupanca, banco_de_creditos, caixinha_banco)
- `current_balance` (saldo atual - calculado)
- `description`

#### 4.1.2 Transações Financeiras (Transaction)
| Categoria | Dados Coletados |
|-----------|-----------------|
| **Identificação** | `id`, `company_id`, `created_at`, `updated_at` |
| **Classificação** | `type` (receita, despesa, transferencia), `category_id`, `cost_center_id` |
| **Valores** | `amount`, `date`, `due_date`, `paid` |
| **Relacionamentos** | `bank_account_id`, `cash_register_id`, `contact_id`, `payment_method_id` |
| **Documentação** | `description`, `attachment` (arquivos em `media/`) |
| **Recorrência** | `recurring_bill_id`, `recurring_income_id` |
| **Auditoria** | `related_transaction_id` (estornos), `linked_transaction_id` (transferências) |

**Observação:** Todas as transações são vinculadas obrigatoriamente a uma `company_id` (isolamento multi-tenant).

#### 4.1.3 Caixas/PDVs (CashRegister)
- `company_id`, `name`, `current_balance`, `location`

#### 4.1.4 Categorias Financeiras (Category)
- `company_id`, `name`, `code`, `type` (receita, despesa), `parent_id` (hierarquia)

#### 4.1.5 Métodos de Pagamento (PaymentMethod)
- `name` (14 métodos padrão: Dinheiro, PIX, Débito, Crédito, etc.)

### 4.2 Módulo de Inventário

#### 4.2.1 Estoques (Inventory)
- `company_id`, `name`, `description`, `is_store_inventory`

#### 4.2.2 Itens de Estoque (StockItem)
- `company_id`, `inventory_id`, `name`, `sku`, `barcode`
- `current_quantity`, `cost_price`, `sell_price`
- `min_stock_level` (para alertas)

#### 4.2.3 Movimentações de Estoque (InventoryMovement)
| Campo | Finalidade |
|-------|------------|
| `company_id` | Isolamento multi-tenant |
| `inventory_id`, `stock_item_id` | Identificação do movimento |
| `type` | entrada, saida, transferencia, ajuste, venda |
| `quantity`, `cost_price` | Valores do movimento |
| `user_id` | Usuário que executou (auditoria) |
| `related_inventory_id` | Destino em transferências |
| `transaction_id` | Vínculo com transação financeira (vendas) |
| `description`, `date` | Documentação |

### 4.3 Módulo de Contatos

#### 4.3.1 Contatos (Contact)
| Campo | Finalidade | Sensibilidade |
|-------|------------|---------------|
| `company_id` | Isolamento multi-tenant | Técnico |
| `name` | Razão social | Empresarial |
| `fantasy_name` | Nome fantasia | Empresarial |
| `tax_id` | CPF/CNPJ | Empresarial - Público |
| `email` | Contato | Empresarial |
| `phone` | Contato | Empresarial |
| `type` | cliente, fornecedor, ambos | Classificação |

### 4.4 Módulo de Notificações

#### 4.4.1 Notificações (Notification)
| Campo | Finalidade |
|-------|------------|
| `company_id` | Destinatário (empresa) |
| `title`, `message` | Conteúdo da notificação |
| `is_read` | Status de leitura |
| `link_to_stock_item_id` | Referência a alertas de estoque |
| `created_at`, `updated_at` | Timestamps |

**Tipos de Notificações:**
- **Alertas de Estoque:** Gerados automaticamente quando `current_quantity ≤ min_stock_level`
- **Sistema:** Notificações administrativas

---

## 5. FINALIDADES DO TRATAMENTO DE DADOS

### 5.1 Bases Legais (Art. 7º LGPD)

| Finalidade | Base Legal LGPD | Dados Envolvidos |
|------------|-----------------|------------------|
| **Prestação do serviço ERP** | Execução de contrato (Art. 7º, V) | Todos os dados empresariais e operacionais |
| **Autenticação e segurança** | Execução de contrato (Art. 7º, V) | Email, senha (hash), tokens JWT |
| **Controle de acesso multi-empresa** | Legítimo interesse (Art. 7º, IX) | Membership, company_access_token |
| **Comunicações administrativas** | Execução de contrato (Art. 7º, V) | Email, phone_number |
| **Auditoria e histórico** | Obrigação legal/regulatória (Art. 7º, II) | created_at, updated_at, user_id em movimentos |
| **Cobrança e gestão de assinatura** | Execução de contrato (Art. 7º, V) | Dados de subscription, trial |
| **Alertas de estoque** | Legítimo interesse (Art. 7º, IX) | Notificações vinculadas a stock_items |

### 5.2 Detalhamento de Finalidades

#### 5.2.1 Gestão Financeira
- Registro e controle de transações financeiras (receitas, despesas, transferências)
- Cálculo de saldos bancários em tempo real
- Geração de relatórios financeiros
- Controle de contas a pagar e receber
- Gestão de fluxo de caixa

#### 5.2.2 Gestão de Inventário
- Controle de entrada e saída de produtos
- Rastreabilidade de movimentações
- Alertas automáticos de estoque mínimo
- Precificação e custeio
- Transferências entre estoques

#### 5.2.3 Controle de Acesso
- Autenticação de usuários (JWT com cookies HttpOnly)
- Autorização baseada em funções (roles: admin, financials, etc.)
- Isolamento de dados por empresa (multi-tenant)
- Auditoria de ações por usuário

#### 5.2.4 Relacionamento com Clientes/Fornecedores
- Cadastro de contatos empresariais
- Vinculação de transações a contatos
- Histórico de relacionamento comercial

---

## 6. ARMAZENAMENTO E SEGURANÇA

### 6.1 Infraestrutura de Dados

#### 6.1.1 Banco de Dados
- **Sistema:** PostgreSQL 15
- **Localização:** Servidor containerizado (Docker)
- **Acesso:** Credenciais via variáveis de ambiente
- **Backup:** Responsabilidade da hospedagem
- **Isolamento:** Multi-tenant com filtro por `company_id` em todas as consultas

#### 6.1.2 Cache e Filas
- **Sistema:** Redis 7
- **Uso:** Cache de dashboards, fila de tarefas assíncronas (Celery)
- **Dados Armazenados:** Dados temporários de performance (não sensíveis)
- **Expiração:** Configurável por chave (padrão: invalidação por evento)

#### 6.1.3 Arquivos (Media)
- **Armazenamento:** Sistema de arquivos local (`/media/`)
- **Conteúdo:** Anexos de transações, logos de bancos
- **Acesso:** Protegido por autenticação Django
- **Observação:** Não há armazenamento em nuvem externa no momento

### 6.2 Medidas de Segurança Implementadas

#### 6.2.1 Criptografia
| Componente | Método |
|------------|--------|
| **Senhas** | Hash PBKDF2 + SHA256 (Django default) |
| **Tokens JWT** | Assinatura HMAC-SHA256 |
| **Conexões** | HTTPS (configurável via proxy reverso) |
| **Banco de Dados** | Conexão via TLS (configurável) |

#### 6.2.2 Controle de Acesso
- **Autenticação:** JWT obrigatório para todas as rotas (exceto registro/login)
- **Autorização:** Verificação de `Membership` antes de acessar dados de empresa
- **Isolamento:** Filtro automático por `company_id` em todos os ViewSets
- **Validação:** Nível de modelo impede associação de dados entre empresas diferentes

#### 6.2.3 Proteção CSRF
- **Middleware:** `CsrfViewMiddleware` ativo
- **SameSite Cookies:** Configurado como `Lax`

#### 6.2.4 Validação de Entrada
- **Serializers DRF:** Validação de tipos e formatos
- **Métodos clean():** Validação de regras de negócio no modelo
- **Regex Validators:** Nomes, CNPJs, emails

#### 6.2.5 Proteção contra Ataques Comuns
- **SQL Injection:** ORM Django com prepared statements
- **XSS:** Sanitização automática de templates Django
- **Clickjacking:** Middleware `XFrameOptionsMiddleware`
- **CORS:** Lista whitelist de origens permitidas

### 6.3 Auditoria e Logs

#### 6.3.1 Timestamps Automáticos
Todos os modelos possuem:
- `created_at`: Data de criação
- `updated_at`: Data de última modificação

#### 6.3.2 Rastreabilidade de Ações
- **InventoryMovement:** Campo `user_id` registra quem executou
- **Invitation:** Campo `invited_by` registra quem convidou
- **Transaction:** Histórico completo de alterações via signals

#### 6.3.3 Cache Invalidation Signals
- Signals Django invalidam cache quando dados financeiros são alterados
- Garantia de consistência entre cache e banco de dados

---

## 7. COMPARTILHAMENTO DE DADOS

### 7.1 Compartilhamento Interno (Dentro do Sistema)

| Situação | Dados Compartilhados | Justificativa |
|----------|---------------------|---------------|
| **Multi-tenant entre membros** | Dados empresariais de uma Company são compartilhados com todos os Members | Funcionamento do sistema colaborativo |
| **Convites de usuários** | Email do convidado é compartilhado com admin que enviou convite | Gestão de acesso |
| **Auditoria de movimentos** | Nome do usuário em InventoryMovement | Rastreabilidade |

### 7.2 Compartilhamento Externo

**IMPORTANTE:** O sistema **NÃO compartilha dados com terceiros** no estado atual da implementação.

- ❌ Não há integração com APIs externas de pagamento
- ❌ Não há envio de dados para serviços de analytics externos
- ❌ Não há integração com redes sociais
- ❌ Não há exportação automática de dados para parceiros
- ⚠️ **Futura implementação:** Possível integração com gateway de pagamento (requer atualização dos Termos)

### 7.3 Autoridades e Obrigações Legais

O sistema pode compartilhar dados quando:
- **Ordem judicial:** Determinação legal de autoridade competente
- **Obrigação fiscal:** Requisição de órgãos tributários (dados já são públicos no caso de CNPJ)
- **Defesa legal:** Processos judiciais envolvendo a plataforma

---

## 8. DIREITOS DOS TITULARES (Arts. 17 a 22 LGPD)

### 8.1 Direitos Garantidos

| Direito | Implementação Atual | Como Exercer |
|---------|---------------------|--------------|
| **Confirmação de tratamento** | ✅ Documentado neste documento | Contato via suporte |
| **Acesso aos dados** | ✅ API `/api/v1/users/me/` retorna dados do usuário | Autenticado na plataforma |
| **Correção de dados** | ✅ APIs PUT/PATCH em todos os recursos | Interface da plataforma |
| **Anonimização/bloqueio** | ⚠️ Não implementado | Contato via suporte |
| **Eliminação de dados** | ⚠️ Não implementado (soft delete necessário) | Contato via suporte |
| **Portabilidade** | ⚠️ Não implementado (exportação JSON/CSV) | Contato via suporte |
| **Informação sobre compartilhamento** | ✅ Documentado (não há compartilhamento externo) | Este documento |
| **Revogação de consentimento** | ✅ Usuário pode desativar conta | Interface ou suporte |
| **Oposição ao tratamento** | ✅ Cancelamento de conta encerra tratamento | Interface ou suporte |

### 8.2 Mecanismos de Atualização/Correção

#### 8.2.1 Dados de Usuário
- **Endpoint:** `PUT /api/v1/users/me/`
- **Campos editáveis:** `first_name`, `last_name`, `phone_number`
- **Não editáveis:** `email` (chave de autenticação), `password` (via endpoint específico)

#### 8.2.2 Dados de Empresa
- **Endpoint:** `PUT /api/v1/companies/{id}/`
- **Permissão:** Apenas membros com role `admin`
- **Campos editáveis:** `name`, `email`, `cnpj` (com validação)

#### 8.2.3 Dados Transacionais
- **Edição:** Disponível via API para recursos não finalizados
- **Auditoria:** Alterações registradas via `updated_at`

### 8.3 Exclusão de Conta e Dados

**⚠️ ATENÇÃO - IMPLEMENTAÇÃO PENDENTE:**

O sistema **atualmente não possui** mecanismo automatizado de exclusão completa de dados. Recomenda-se:

1. **Implementar soft delete:** Adicionar campo `deleted_at` em modelos sensíveis
2. **Anonimização:** Substituir dados pessoais por valores genéricos
3. **Período de carência:** 30 dias para reversão antes de exclusão definitiva
4. **Logs de exclusão:** Auditoria de solicitações de exclusão

**Prazo LGPD:** Até 15 dias para atender solicitação de exclusão (Art. 18, VI).

---

## 9. RETENÇÃO DE DADOS

### 9.1 Períodos de Retenção Recomendados

| Tipo de Dado | Período | Base Legal |
|--------------|---------|------------|
| **Dados cadastrais** | Durante contrato + 5 anos | Código Civil (prescrição) |
| **Transações financeiras** | Durante contrato + 5 anos | Legislação tributária (Receita Federal) |
| **Movimentos de estoque** | Durante contrato + 5 anos | Legislação tributária |
| **Logs de acesso** | 6 meses | Legítimo interesse (segurança) |
| **Dados de operadores** | Durante vínculo + 5 anos | Legislação trabalhista |
| **Convites expirados/recusados** | 1 ano | Legítimo interesse |
| **Notificações lidas** | 90 dias | Legítimo interesse |

### 9.2 Dados Mantidos Após Cancelamento

Após cancelamento da assinatura:
- **Dados financeiros/contábeis:** Mantidos por 5 anos (obrigação legal)
- **Dados de usuário:** Mantidos por 5 anos vinculados às transações
- **Anonimização:** Após período legal, dados pessoais devem ser anonimizados

### 9.3 Trial Period

- **Duração:** 15 dias (configurável em `settings.py`)
- **Dados coletados:** Idênticos ao período pago
- **Exclusão em caso de não conversão:** Recomenda-se oferecer opção de exclusão após 30 dias do fim do trial

---

## 10. COOKIES E TECNOLOGIAS DE RASTREAMENTO

### 10.1 Cookies Utilizados

| Nome | Tipo | Duração | Finalidade | Categoria LGPD |
|------|------|---------|------------|----------------|
| `access_token` | HttpOnly | 12 horas | Autenticação de sessão | Estritamente necessário |
| `refresh_token` | HttpOnly | 24 horas | Renovação de token | Estritamente necessário |
| `company_access_token` | HttpOnly | 12 horas | Vinculação empresa ativa | Estritamente necessário |
| `sessionid` | Django Session | Sessão | Sessão Django (fallback) | Estritamente necessário |
| `csrftoken` | Segurança | Sessão | Proteção CSRF | Estritamente necessário |

**Observações:**
- ✅ Todos os cookies são **estritamente necessários** (dispensam consentimento - Art. 11, II, 'a' LGPD)
- ✅ Configurados como `HttpOnly` (não acessíveis via JavaScript)
- ✅ `SameSite=Lax` (proteção CSRF)
- ❌ **Não há cookies de rastreamento/analytics/marketing**

### 10.2 Local Storage / Session Storage

**Frontend (React):**
- Possível armazenamento de preferências de UI (tema, idioma)
- **Não armazena dados sensíveis** (tokens são em HttpOnly cookies)
- Recomenda-se auditoria do código frontend para confirmar

### 10.3 Cache do Navegador

- **Recursos estáticos:** Imagens, CSS, JS (não contêm dados pessoais)
- **API responses:** Não são cacheadas no navegador (headers Cache-Control)

---

## 11. TRANSFERÊNCIA INTERNACIONAL DE DADOS

### 11.1 Status Atual

**❌ NÃO HÁ transferência internacional de dados** no estado atual da implementação.

- Todos os servidores estão no Brasil (ou devem estar)
- Não há CDN internacional
- Não há serviços de cloud externos (AWS, Azure, etc.)

### 11.2 Recomendações para Futura Expansão

Se houver necessidade de transferência internacional:
1. **Adequação a país adequado:** Preferir países com nível adequado de proteção (ANPD)
2. **Cláusulas contratuais padrão:** Acordo com provedores internacionais
3. **Atualizar Política de Privacidade:** Informar claramente aos usuários
4. **Consentimento específico:** Se transferência não for necessária para serviço

---

## 12. INCIDENTES DE SEGURANÇA

### 12.1 Obrigações LGPD (Art. 48)

Em caso de **incidente de segurança** que possa gerar risco ou dano aos titulares:

1. **Comunicar ANPD:**
   - Prazo: "Em prazo razoável" (interpretação: até 2 dias úteis)
   - Conteúdo: Descrição do incidente, dados afetados, medidas técnicas adotadas

2. **Comunicar Titular:**
   - Quando houver risco de dano relevante
   - Linguagem clara e acessível
   - Informar medidas para reversão/mitigação

### 12.2 Medidas Preventivas Implementadas

- ✅ Senhas hashadas (não reversíveis)
- ✅ Tokens JWT com expiração curta
- ✅ Isolamento multi-tenant (vazamento afeta apenas uma empresa)
- ✅ Validação de entrada (previne injeção)
- ⚠️ **Recomenda-se:** Implementar logs de acesso para detecção de anomalias
- ⚠️ **Recomenda-se:** Implementar rate limiting (proteção DDoS)
- ⚠️ **Recomenda-se:** Implementar backup automatizado com criptografia

---

## 13. ENCARREGADO DE DADOS (DPO)

### 13.1 Designação Obrigatória (Art. 41 LGPD)

O controlador deve indicar um **Encarregado de Dados Pessoais (Data Protection Officer - DPO)**.

**Responsabilidades:**
- Aceitar reclamações e comunicações dos titulares
- Prestar esclarecimentos sobre tratamento de dados
- Receber comunicações da ANPD
- Orientar funcionários sobre boas práticas de proteção de dados

**Publicidade:**
- Nome e contato devem estar na **Política de Privacidade**
- Recomenda-se email dedicado: `dpo@fintelis.com.br` ou `privacidade@fintelis.com.br`

### 13.2 Documentação Interna Recomendada

O DPO deve manter:
1. **Registro de Atividades de Tratamento (ROPA):** Este documento serve como base
2. **Relatório de Impacto (RIPD):** Para tratamentos de alto risco (se aplicável)
3. **Logs de solicitações de titulares:** Prazos de resposta, ações tomadas
4. **Registro de incidentes:** Datas, ações corretivas, notificações enviadas

---

## 14. CONFORMIDADE COM OUTRAS LEGISLAÇÕES

### 14.1 Código Civil e Comercial

- **Prescrição:** 5 anos para ações relacionadas a contratos (Art. 206, §5º)
- **Justifica:** Manutenção de dados transacionais por 5 anos

### 14.2 Legislação Tributária

- **IN RFB 1.594/2015:** Prazo de 5 anos para guarda de documentos fiscais
- **Justifica:** Retenção de transações financeiras, emissão de notas (se aplicável)

### 14.3 Marco Civil da Internet (Lei 12.965/2014)

- **Logs de acesso:** Guarda obrigatória de 6 meses (para provedores de conexão/aplicação)
- **Aplicabilidade:** Sistema não é provedor de conexão, mas boas práticas recomendam logs

### 14.4 Código de Defesa do Consumidor (CDC)

- **Direito de arrependimento:** 7 dias para contratos online (se aplicável a assinaturas)
- **Cláusulas abusivas:** Termos devem ser claros e equilibrados
- **Transparência:** Informações sobre planos, preços e renovação automática

---

## 15. ARQUITETURA TÉCNICA E SEGURANÇA

### 15.1 Diagrama de Fluxo de Dados (Simplificado)

```
[Usuário Browser]
    ↓ HTTPS
[Frontend React] → Cookie HttpOnly (access_token)
    ↓ API Requests (JWT no header)
[Backend Django DRF]
    ├─ Middleware: CORS, CSRF, Auth
    ├─ ViewSets: Filtro por company_id
    ↓
[PostgreSQL 15] → Dados persistentes
[Redis 7] → Cache temporário
[Celery] → Tarefas assíncronas (alertas de estoque)
```

### 15.2 Camadas de Segurança

1. **Transporte:** HTTPS (TLS 1.2+)
2. **Autenticação:** JWT com refresh token
3. **Autorização:** Verificação de Membership antes de cada operação
4. **Isolamento:** Filtro `company_id` em todos os querysets
5. **Validação:** Serializers DRF + métodos clean() nos modelos
6. **Criptografia:** Senhas hashadas com PBKDF2 + SHA256

### 15.3 Dependências de Segurança

| Pacote | Versão | Finalidade de Segurança |
|--------|--------|------------------------|
| Django | 4.2.7 | Framework com práticas seguras built-in |
| djangorestframework-simplejwt | 5.3.1 | Autenticação JWT |
| django-cors-headers | 4.4.0 | Proteção CORS |
| psycopg[binary] | 3.1.12 | Driver PostgreSQL (prepared statements) |

**⚠️ Recomendação:** Manter dependências atualizadas para correções de segurança.

---

## 16. CONSENTIMENTO E BASES LEGAIS

### 16.1 Situações Onde NÃO É Necessário Consentimento

✅ **Sistema Fintelis opera majoritariamente sem consentimento explícito**, pois:

1. **Execução de contrato (Art. 7º, V):**
   - Cadastro de usuário: necessário para criar conta
   - Dados empresariais: necessários para prestação do serviço ERP
   - Transações financeiras: essência do serviço contratado

2. **Legítimo interesse (Art. 7º, IX):**
   - Auditoria de ações (segurança do sistema)
   - Alertas de estoque (benefício ao usuário)
   - Cache de dados (performance do sistema)

3. **Obrigação legal (Art. 7º, II):**
   - Guarda de dados fiscais (Receita Federal)
   - Guarda de dados contábeis (Código Civil)

### 16.2 Situações Onde Consentimento É Necessário

⚠️ **Futuras funcionalidades que EXIGEM consentimento:**

1. **Marketing via email:** Envio de newsletters, promoções (não implementado)
2. **Compartilhamento com parceiros:** Integrações não essenciais (não implementado)
3. **Uso de dados para IA/ML:** Treinamento de modelos (não implementado)
4. **Cookies não essenciais:** Analytics, publicidade (não implementado)

**Recomendação:** Se implementar essas funcionalidades, criar checkbox de opt-in no cadastro.

---

## 17. CHECKLIST DE IMPLEMENTAÇÕES PENDENTES

### 17.1 Críticas (Alta Prioridade)

- [ ] **Designar DPO oficial:** Nome e contato público
- [ ] **Endpoint de exclusão de conta:** Com anonimização de dados
- [ ] **Política de Privacidade completa:** Baseada neste documento
- [ ] **Termos de Uso:** Com cláusulas de responsabilidade
- [ ] **Procedimento de resposta a incidentes:** Documentado e testado
- [ ] **Backup automatizado:** Com criptografia e teste de restauração

### 17.2 Importantes (Média Prioridade)

- [ ] **Exportação de dados (portabilidade):** JSON/CSV de todos os dados do usuário
- [ ] **Soft delete:** Implementar `deleted_at` em modelos principais
- [ ] **Logs de acesso:** Sistema de auditoria de login/ações sensíveis
- [ ] **Rate limiting:** Proteção contra ataques de força bruta
- [ ] **2FA (autenticação de dois fatores):** Opcional para usuários
- [ ] **Criptografia de anexos:** Arquivos em `media/` criptografados em disco

### 17.3 Desejáveis (Baixa Prioridade)

- [ ] **Dashboard de privacidade:** Usuário visualiza dados coletados
- [ ] **Histórico de alterações:** Log completo de edições em dados sensíveis
- [ ] **Notificação de alteração de senha:** Email automático
- [ ] **Inativação automática:** Contas sem uso há X meses
- [ ] **Auditoria de dependências:** Scan automático de vulnerabilidades (Dependabot)

---

## 18. PONTOS DE ATENÇÃO PARA OS TERMOS

### 18.1 Cláusulas Obrigatórias

Os **Termos e Condições** devem incluir:

1. **Identificação do Controlador:**
   - Razão social, CNPJ, endereço
   - Contato do DPO

2. **Definição de Papéis:**
   - Controlador: [Nome da empresa responsável pelo Fintelis]
   - Operador: Não há (sistema não compartilha dados com terceiros)

3. **Descrição do Tratamento:**
   - Quais dados são coletados (Seção 2 deste documento)
   - Para quê são usados (Seção 5 deste documento)
   - Base legal de cada tratamento (Tabela na Seção 5.1)

4. **Direitos dos Titulares:**
   - Listagem completa (Seção 8 deste documento)
   - Como exercer cada direito (emails, formulários)

5. **Retenção de Dados:**
   - Prazos específicos (Seção 9 deste documento)
   - Justificativa legal de cada prazo

6. **Segurança:**
   - Medidas implementadas (Seção 6.2 deste documento)
   - Procedimento em caso de incidente (Seção 12 deste documento)

7. **Cookies:**
   - Lista completa (Seção 10.1 deste documento)
   - Finalidade de cada cookie
   - Dispensa de consentimento (todos são estritamente necessários)

8. **Transferência Internacional:**
   - Confirmar que NÃO há (Seção 11 deste documento)
   - Cláusula de atualização caso haja no futuro

9. **Alterações nos Termos:**
   - Como usuário será notificado
   - Prazo para aceite de novos termos

10. **Cancelamento e Exclusão:**
    - Procedimento para solicitar
    - Prazos de atendimento (15 dias LGPD)
    - Dados que serão mantidos (obrigação legal)

### 18.2 Linguagem Recomendada

- ✅ Clara, objetiva e em português
- ✅ Evitar juridiquês excessivo
- ✅ Usar exemplos práticos
- ✅ Destacar direitos dos usuários em seção separada
- ✅ Incluir data de última atualização no topo

### 18.3 Aceitação dos Termos

**No cadastro:**
```
[ ] Li e aceito os Termos de Uso e a Política de Privacidade.
```

**Observação:** Checkbox deve ser opt-in (não pré-marcada).

---

## 19. CONTATO E EXERCÍCIO DE DIREITOS

### 19.1 Canais Recomendados

Sugestão de estrutura para Política de Privacidade:

```
Para exercer seus direitos previstos na LGPD, entre em contato:

📧 Email: privacidade@fintelis.com.br
📧 DPO: [nome do encarregado] - dpo@fintelis.com.br
📍 Endereço: [Endereço físico da empresa]
🕐 Prazo de resposta: Até 15 dias úteis
```

### 19.2 Procedimentos Internos

Ao receber solicitação de titular:

1. **Validação de identidade:** Confirmar que solicitante é titular dos dados
2. **Registro da solicitação:** Protocolo interno com data/hora
3. **Análise jurídica:** Verificar viabilidade e prazos legais
4. **Execução:** Realizar ação solicitada (acesso, correção, exclusão)
5. **Resposta formal:** Email ou carta com confirmação
6. **Arquivo:** Manter registro por 5 anos (comprovação de conformidade)

---

## 20. CONSIDERAÇÕES FINAIS

### 20.1 Status de Conformidade Atual

**Pontos Positivos:**
- ✅ Arquitetura multi-tenant com isolamento robusto
- ✅ Senhas criptografadas com algoritmos seguros
- ✅ Tokens JWT com expiração curta
- ✅ Não há compartilhamento externo de dados
- ✅ Cookies estritamente necessários (sem analytics/marketing)
- ✅ Validação de entrada em múltiplas camadas
- ✅ Auditoria parcial (timestamps, user_id em movimentos)

**Pontos de Atenção:**
- ⚠️ Falta endpoint de exclusão completa de dados
- ⚠️ Falta sistema de portabilidade (exportação completa)
- ⚠️ Falta logs de acesso/auditoria avançada
- ⚠️ Falta Política de Privacidade e Termos formais
- ⚠️ Falta designação oficial de DPO

### 20.2 Próximos Passos Recomendados

1. **Imediato (0-30 dias):**
   - Redigir Política de Privacidade baseada neste documento
   - Redigir Termos de Uso com cláusulas de responsabilidade
   - Designar DPO (pode ser membro da equipe)
   - Implementar checkbox de aceitação no cadastro

2. **Curto Prazo (1-3 meses):**
   - Implementar endpoint de exclusão/anonimização
   - Criar sistema de exportação de dados (portabilidade)
   - Documentar procedimento de resposta a incidentes
   - Implementar backup automatizado

3. **Médio Prazo (3-6 meses):**
   - Sistema de logs de acesso
   - Rate limiting e proteção DDoS
   - 2FA opcional para usuários
   - Auditoria de segurança por terceiro

### 20.3 Manutenção da Conformidade

- **Revisão anual:** Política de Privacidade e Termos de Uso
- **Treinamento:** Equipe deve conhecer obrigações LGPD
- **Monitoramento:** Acompanhar mudanças na legislação (ANPD)
- **Atualização de dependências:** Patches de segurança mensais
- **Testes de invasão:** Anualmente ou após mudanças críticas

---

## ANEXO A: GLOSSÁRIO LGPD

| Termo | Definição Legal (Lei 13.709/2018) |
|-------|-----------------------------------|
| **Dado pessoal** | Informação relacionada a pessoa natural identificada ou identificável |
| **Dado sensível** | Origem racial, opinião política, saúde, genética, biometria, orientação sexual |
| **Titular** | Pessoa natural a quem se referem os dados pessoais |
| **Controlador** | Quem toma decisões sobre o tratamento (Fintelis) |
| **Operador** | Quem realiza o tratamento em nome do controlador (não aplicável) |
| **Encarregado (DPO)** | Canal de comunicação entre controlador, titulares e ANPD |
| **Tratamento** | Toda operação com dados (coleta, armazenamento, uso, eliminação) |
| **Anonimização** | Processo que torna impossível a identificação do titular |

---

## ANEXO B: TABELA DE RISCOS E MITIGAÇÕES

| Risco LGPD | Probabilidade | Impacto | Mitigação Implementada | Mitigação Pendente |
|------------|---------------|---------|------------------------|-------------------|
| Vazamento de senhas | Baixa | Crítico | Hash PBKDF2, tokens com expiração | 2FA, logs de acesso |
| Acesso não autorizado entre empresas | Baixa | Alto | Filtro company_id obrigatório | Auditoria de queries N+1 |
| Perda de dados (servidor) | Média | Crítico | - | Backup automatizado |
| Ataque DDoS | Média | Médio | - | Rate limiting, CDN |
| Não cumprimento de solicitação LGPD | Alta | Alto | - | Endpoint de exclusão |
| Retenção excessiva de dados | Média | Médio | Timestamps para auditoria | Rotina de limpeza automatizada |
| Incidente não notificado | Baixa | Alto | - | Procedimento documentado |

---

**DOCUMENTO ELABORADO PARA AUXILIAR NA CONFORMIDADE COM A LEI Nº 13.709/2018 (LGPD)**

**Observação Legal:** Este documento é uma referência técnica. A redação final dos Termos de Uso e Política de Privacidade deve ser revisada por advogado especializado em Direito Digital e Proteção de Dados.

---

**Versão:** 1.0  
**Data:** 03/12/2025  
**Atualização recomendada:** Anual ou quando houver mudanças significativas no sistema

