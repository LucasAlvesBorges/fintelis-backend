## 1. Visão Geral do Projeto

O Fintelis é um SaaS ERP (Enterprise Resource Planning) Multi-Tenant projetado para gerenciar as finanças e o inventário de pequenas e médias empresas. Sua arquitetura multi-tenant (multi-empresa) é um requisito central, permitindo que um único usuário (ex: um contador) gerencie múltiplas empresas (`Company`) com um único login (`User`).

O sistema é dividido em dois módulos principais: **Financeiro** e **Inventário**, suportados por um sistema de **Notificações** unificado.

A arquitetura financeira é robusta, suportando:
1.  **Destinos** do dinheiro (`bank_account` - Bancos, Cofres).
2.  **Processadores** de transações (`cash_register` - Caixas/PDVs).
3.  **Transferências** entre contas (com rastreabilidade).
4.  **Automação** de lançamentos (`recurring_bill`, `recurring_income`).

## 2. Arquitetura da Stack (Não Funcional)

A IA deve gerar código compatível com a seguinte stack:

* **Backend:** Django Rest Framework (DRF)
* **Banco de Dados:** PostgreSQL
* **Filas Assíncronas:** Django Celery
* **Broker / Cache:** Redis
* **Containerização:** Docker

## 3. Banco de Dados (Fonte da Verdade)

A IA deve usar o seguinte esquema SQL (PostgreSQL v10) como a fonte da verdade absoluta para todos os `models.py`.

```sql
-- Fintelis SaaS - Diagrama Final (v10)
-- Adições: Transferências (linked_transaction_id) e Recorrências.
-- Baseado nos models.py (v9) do usuário (PT-BR choices).

-- 0. TABELA DE USUÁRIO
CREATE TABLE "user" (
    "id" BIGSERIAL PRIMARY KEY,
    "first_name" VARCHAR(150) NOT NULL,
    "last_name" VARCHAR(150) NOT NULL,
    "email" VARCHAR(255) NOT NULL UNIQUE, -- Email é o login
    "password" VARCHAR(128) NOT NULL -- Assumindo que o Django gerencia isso
);

-- 1. ENTIDADE DE MULTI-TENANCY
CREATE TABLE "company" (
    "id" BIGSERIAL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "cnpj" VARCHAR(255) NOT NULL,
    "email" VARCHAR(255) NOT NULL,
    "type" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- 2. ACESSO E PERMISSÕES
CREATE TABLE "membership" (
    "id" BIGSERIAL PRIMARY KEY,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id"),
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "role" VARCHAR(50) NOT NULL, -- Ex: 'admin', 'finance', 'inventory'
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    UNIQUE ("user_id", "company_id")
);

-- =======================================
-- MÓDULO: FINANCEIRO (ATUALIZADO)
-- =======================================

-- O "Destino" do dinheiro (Contas e Carteiras)
CREATE TABLE "bank_account" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "name" VARCHAR(100) NOT NULL, -- Ex: "Itau", "Banco de Crédito"
    "type" VARCHAR(25) NOT NULL, -- 'conta_corrente', 'banco_de_creditos', etc.
    "initial_balance" DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- O "Processador" do dinheiro (Caixas/PDV)
CREATE TABLE "cash_register" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "name" VARCHAR(100) NOT NULL, -- Ex: "Caixa 1 - Bilhetagem"
    "default_bank_account_id" BIGINT NOT NULL REFERENCES "bank_account" ("id"),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    UNIQUE("company_id", "name")
);

-- Categoria Financeira
CREATE TABLE "category" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "name" VARCHAR(100) NOT NULL, -- Ex: "Aluguel", "Venda de Bilhetagem"
    "type" VARCHAR(10) NOT NULL, -- 'receita', 'despesa'
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    UNIQUE("company_id", "name", "type")
);

-- O Fato (Extrato) - TABELA ATUALIZADA
CREATE TABLE "transaction" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "bank_account_id" BIGINT NOT NULL REFERENCES "bank_account" ("id"), -- O Destino
    "category_id" BIGINT NULL REFERENCES "category" ("id"),
    "cash_register_id" BIGINT NULL REFERENCES "cash_register" ("id"), -- O Processador
    
    -- *** NOVA COLUNA (Para Transferências) ***
    "linked_transaction_id" BIGINT NULL UNIQUE REFERENCES "transaction"("id") ON DELETE SET NULL,

    "description" VARCHAR(255) NOT NULL,
    "amount" DECIMAL(15, 2) NOT NULL,
    
    -- Choices em PT-BR (conforme models.py)
    "type" VARCHAR(25) NOT NULL, -- 'receita', 'despesa', 'transferencia_interna', 'transferencia_externa'
    
    "transaction_date" DATE NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- Contas a Pagar (A Promessa)
CREATE TABLE "bill" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "category_id" BIGINT NULL REFERENCES "category" ("id"),
    "payment_transaction_id" BIGINT NULL UNIQUE REFERENCES "transaction" ("id"),
    "description" VARCHAR(255) NOT NULL,
    "amount" DECIMAL(15, 2) NOT NULL,
    "due_date" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL, -- 'a_vencer', 'quitada'
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- Contas a Receber (A Promessa)
CREATE TABLE "income" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "category_id" BIGINT NULL REFERENCES "category" ("id"),
    "payment_transaction_id" BIGINT NULL UNIQUE REFERENCES "transaction" ("id"),
    "description" VARCHAR(255) NOT NULL,
    "amount" DECIMAL(15, 2) NOT NULL,
    "due_date" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL, -- 'pendente', 'recebido'
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- *** NOVA TABELA (Recorrência) ***
CREATE TABLE "recurring_bill" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "category_id" BIGINT NULL REFERENCES "category" ("id"),
    "description" VARCHAR(255) NOT NULL,
    "amount" DECIMAL(15, 2) NOT NULL,
    "frequency" VARCHAR(20) NOT NULL, -- Ex: 'monthly', 'quarterly'
    "start_date" DATE NOT NULL,
    "end_date" DATE NULL,
    "next_due_date" DATE NOT NULL,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- *** NOVA TABELA (Recorrência) ***
CREATE TABLE "recurring_income" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "category_id" BIGINT NULL REFERENCES "category" ("id"),
    "description" VARCHAR(255) NOT NULL,
    "amount" DECIMAL(15, 2) NOT NULL,
    "frequency" VARCHAR(20) NOT NULL, -- Ex: 'monthly'
    "start_date" DATE NOT NULL,
    "end_date" DATE NULL,
    "next_due_date" DATE NOT NULL,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);


-- =======================================
-- MÓDULO: INVENTÁRIO (MULTI-ESTOQUE)
-- =======================================

CREATE TABLE "product_category" ( -- Categoria de Produto
    "id" BIGSERIAL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL, -- Ex: "Informática", "Bilhetagem"
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    UNIQUE("company_id", "name")
);

CREATE TABLE "products" ( -- O Catálogo Mestre de Produtos
    "id" BIGSERIAL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL, -- Ex: "Cartão Vale Transporte"
    "product_category_id" BIGINT NULL REFERENCES "product_category" ("id"),
    "min_stock_level" BIGINT NOT NULL DEFAULT 0, -- Limite mínimo de alerta
    "default_cost" DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    UNIQUE("company_id", "name")
);

CREATE TABLE "inventory" ( -- Estoque (Local)
    "id" BIGSERIAL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL, -- Ex: "Estoque TI", "Estoque Bilhetagem"
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

CREATE TABLE "stock_item" ( -- Pivô: Produto + Local + Quantidade
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "product_id" BIGINT NOT NULL REFERENCES "products" ("id"),
    "inventory_id" BIGINT NOT NULL REFERENCES "inventory" ("id"),
    "quantity_on_hand" BIGINT NOT NULL DEFAULT 0, -- A quantidade atual
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    UNIQUE("company_id", "product_id", "inventory_id")
);

CREATE TABLE "inventory_movements" ( -- O Histórico (Kardex)
    "id" BIGSERIAL PRIMARY KEY,
    "stock_item_id" BIGINT NOT NULL REFERENCES "stock_item" ("id"), -- Aponta para o item
    "quantity_changed" BIGINT NOT NULL, -- Ex: +10 (compra), -2 (venda)
    "type" VARCHAR(255) NOT NULL, -- Ex: 'in_purchase', 'out_sale'
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- =======================================
-- MÓDULO: NOTIFICAÇÕES
-- =======================================

CREATE TABLE "notification" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "title" VARCHAR(255) NOT NULL,
    "message" TEXT NOT NULL,
    "is_read" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "link_to_stock_item_id" UUID NULL REFERENCES "stock_item" ("id")
);
````

-----

## 4\. Alocação de Apps no Django

A IA deve organizar o projeto da seguinte forma. Todos os `models.py` devem ser criados nos apps designados abaixo:

  * **`users`** (App)

      * `User` (Modelo customizado, herdando de `AbstractUser`, `USERNAME_FIELD = 'email'`)

  * **`companies`** (App)

      * `Company`
      * `Membership`

  * **`financials`** (App)

      * `BankAccount` (O Destino: Banco, Cofre)
      * `CashRegister` (O Processador: Caixa/PDV)
      * `Category` (Categoria Financeira)
      * `Transaction`
      * `Bill`
      * `Income`
      * `RecurringBill` **(Novo)**
      * `RecurringIncome` **(Novo)**

  * **`inventory`** (App)

      * `ProductCategory` (Categoria de Produto)
      * `Product`
      * `Inventory` (O local do estoque)
      * `StockItem`
      * `InventoryMovement`

  * **`notifications`** (App)

      * `Notification`

  * **`dashboards`** (App)

      * *Sem modelos*. Apenas ViewSets e Serializers (read-only) que consomem dados de outros apps.

  * **`reports`** (App)

      * *Sem modelos*. Apenas Views ou Tasks (Celery) para gerar e disparar downloads (PDF, CSV).

-----

## 5\. Regras de Negócio Fundamentais (Lógica Crítica)

A IA deve implementar as seguintes lógicas de negócio:

### 5.1. A Regra de Ouro: Multi-Tenancy (Isolamento de Dados)

  * **Regra:** Um `User` (autenticado) SÓ PODE ver ou criar dados da `Company` que está "ativa" em sua sessão.
  * **Implementação:**
      * Todos os ViewSets (`ModelViewSet`) de `financials`, `inventory` e `notifications` **devem** ter um `permission_classes` que verifica se o `request.user` é membro da `Company` (via `Membership`).
      * Todos os ViewSets **devem** sobrescrever `get_queryset()` para filtrar os resultados pelo `company_id` ativo. Ex: `self.queryset.filter(company=request.active_company)`.
      * Todos os ViewSets **devem** sobrescrever `perform_create()` para injetar automaticamente o `company_id` ativo no novo objeto. Ex: `serializer.save(company=request.active_company)`.
      * **Validação (Nível de Modelo):** Conforme os métodos `clean()` fornecidos, a lógica deve validar que todos os objetos relacionados (`bank_account`, `category`, `cash_register`) pertencem à mesma `company_id` da transação principal.

### 5.2. Lógica de Ponto de Venda (PDV) vs. Banco

  * **Regra:** O sistema deve diferenciar a Origem/Processador (o `CashRegister`) do Destino (o `BankAccount`).
  * **Implementação:**
      * **Transação de Caixa (PDV):** Ao criar uma `Transaction` originada de um PDV (ex: "Caixa 1"), a API deve receber o `cash_register_id` (ex: ID 10).
      * **Validação (Nível de Modelo):** A lógica (`Transaction.clean`) deve **garantir** que o `bank_account_id` da transação seja *exatamente igual* ao `default_bank_account_id` associado ao `cash_register_id`.
      * **Transação Direta:** Ao criar uma `Transaction` direta (ex: PIX, TED), o `cash_register_id` deve ser `NULL` e o `bank_account_id` é fornecido diretamente pelo usuário.
      * **Relatórios:** Os relatórios (`dashboards`, `reports`) devem permitir agrupar `SUM(amount)` por `bank_account_id` (Saldo da Conta) e, separadamente, por `cash_register_id` (Vendas do Caixa).

### 5.3. Lógica de Transferência Bancária (NOVO)

  * **Regra:** Uma transferência entre contas (`bank_account`) não é `receita` nem `despesa`. Deve ser registrada como dois lançamentos atômicos.
  * **Implementação:**
    1.  O usuário aciona uma *action* (ex: `POST /api/financials/transfer/`).
    2.  O *payload* deve conter `from_bank_account_id`, `to_bank_account_id`, `amount`, `date`.
    3.  A lógica deve rodar em `@transaction.atomic`.
    4.  **Criar Transação de Saída (A):**
          * `bank_account_id = from_bank_account_id`
          * `type = 'transferencia_externa'`
          * `amount = amount`
    5.  **Criar Transação de Entrada (B):**
          * `bank_account_id = to_bank_account_id`
          * `type = 'transferencia_interna'`
          * `amount = amount`
          * `linked_transaction_id = ID da Transação A` (para rastreabilidade)
    6.  **Relatórios:** Os apps `dashboards` e `reports` devem **EXCLUIR** os tipos `transferencia_interna` e `transferencia_externa` dos cálculos de Receita e Despesa.

### 5.4. A Lógica de "Baixa" Financeira (Atomicidade)

  * **Regra:** O ato de "pagar" um `Bill` ou "receber" um `Income` deve ser uma transação atômica (`@transaction.atomic`).
  * **Fluxo (Pagar `Bill`):**
    1.  O usuário deve acionar uma *action* customizada no DRF (ex: `POST /api/financials/bills/{id}/record_payment/`).
    2.  O *payload* deve conter o `bank_account_id` (de onde o dinheiro saiu) e a `transaction_date`.
    3.  A lógica deve:
        a. Criar uma `Transaction` (tipo `despesa`) com o valor do `Bill` e o `bank_account_id`.
        b. Mudar o `status` do `Bill` para `quitada`.
        c. Salvar a `Transaction` criada no campo `payment_transaction` (OneToOne) do `Bill`.
  * **Fluxo (Receber `Income`):**
    1.  Mesma lógica acima (ex: `POST /api/financials/income/{id}/record_payment/`), mas:
        a. Cria uma `Transaction` (tipo `receita`).
        b. Muda o `status` do `Income` para `recebido`.
        c. Associa o `payment_transaction` do `Income`.
  * **Validação (Nível de Modelo):** A lógica (`Bill.clean`, `Income.clean`) deve garantir que a `payment_transaction` associada tenha o `type` correto (`despesa` para Bill, `receita` para Income).

### 5.5. A Lógica de Movimentação de Estoque (Kardex)

  * **Regra:** O campo `quantity_on_hand` na tabela `StockItem` é a fonte da verdade para a quantidade. Este campo **NÃO** é alterado diretamente.
  * **Implementação:**
    1.  Para alterar o estoque (ex: dar entrada de +10), a API deve criar um novo registro em `inventory_movements` (ex: `quantity_changed=10`).
    2.  **Imediatamente após** (via `signal` `post_save` ou em uma classe de Serviço), a lógica deve atualizar o `StockItem` correspondente (`stock_item_id`).
    3.  A atualização deve usar `F()` para evitar *race conditions*:
        `stock_item.quantity_on_hand = F('quantity_on_hand') + movement.quantity_changed`
        `stock_item.save(update_fields=['quantity_on_hand'])`

### 5.6. Lógica de Contas Recorrentes (NOVO)

  * **Implementação:** Uma *task* agendada do **Celery Beat** (rodando 1x por dia).
  * **Lógica:**
    1.  A task escaneia `RecurringBill` e `RecurringIncome` onde `is_active = true` E `next_due_date <= today`.
    2.  Para cada "molde" encontrado, o job deve:
        a. Criar um novo `Bill` (com `status='a_vencer'`) ou `Income` (com `status='pendente'`) baseado nos dados do molde.
        b. Calcular a *nova* `next_due_date` (ex: `next_due_date` + 1 mês, ou `quarterly`, etc.).
        c. Atualizar o molde (`recurring_bill`) com a nova `next_due_date`.
        d. Se a nova `next_due_date` ultrapassar o `end_date` (se houver), definir `is_active = false`.

### 5.7. A Lógica de Alertas (Assíncrona e Instantânea)

  * **Alertas Financeiros:**
      * **Implementação:** Uma *task* agendada do **Celery Beat** (rodando 1x por dia).
      * **Lógica:** A task escaneia todos os `Bill` com `status = 'a_vencer'` e `Income` com `status = 'pendente'` cuja `due_date` esteja próxima (ex: D-5).
      * **Ação:** Cria um registro na tabela `Notification` para cada item encontrado (se já não houver um alerta ativo).
  * **Alertas de Estoque:**
      * **Implementação:** **Instantânea**, acionada via signal `post_save` no modelo `StockItem` (após qualquer atualização de `quantity_on_hand`).
      * **Lógica:** Após `stock_item.save()`, o signal `check_stock_levels` verifica:
        `if stock_item.quantity_on_hand <= stock_item.min_stock_level:`
        * **Nota:** O `min_stock_level` é específico para cada `StockItem` (produto + inventário), permitindo níveis mínimos diferentes por local de estoque.
      * **Ação:** Se a condição for verdadeira, o sistema verifica se já existe uma notificação *não lida* (`is_read=False`) para este `stock_item`. Se não existir, cria um `Notification` com:
        * `company`: A empresa do `stock_item`
        * `title`: "Alerta de Estoque Baixo"
        * `message`: Contém o nome do produto, nome do inventário, nível mínimo e quantidade atual
        * `link_to_stock_item`: Referência ao `StockItem` que gerou o alerta
        * `is_read`: `False` (padrão)
      * **Prevenção de Duplicatas:** O sistema evita criar múltiplas notificações não lidas para o mesmo item, garantindo que apenas uma notificação ativa exista por `StockItem` abaixo do nível mínimo.
