# Documento de Especificação Técnica: Fintelis SaaS (v7)

## 1. Visão Geral do Projeto

O Fintelis é um SaaS ERP (Enterprise Resource Planning) Multi-Tenant projetado para gerenciar as finanças e o inventário de pequenas e médias empresas. Sua arquitetura multi-tenant (multi-empresa) é um requisito central, permitindo que um único usuário (ex: um contador) gerencie múltiplas empresas (`Company`) com um único login (`User`).

O sistema é dividido em dois módulos principais: **Financeiro** e **Inventário**, suportados por um sistema de **Notificações** unificado.

A arquitetura financeira distingue **Contas Bancárias** (`bank_account`), que são os destinos do dinheiro, de **Caixas/PDVs** (`cash_register`), que são os processadores de transações de balcão.

## 2. Arquitetura da Stack (Não Funcional)

A IA deve gerar código compatível com a seguinte stack:

* **Backend:** Django Rest Framework (DRF)
* **Banco de Dados:** PostgreSQL
* **Filas Assíncronas:** Django Celery
* **Broker / Cache:** Redis
* **Containerização:** Docker

## 3. Banco de Dados (Fonte da Verdade)

A IA deve usar o seguinte esquema SQL (PostgreSQL v7) como a fonte da verdade absoluta para todos os `models.py`.

```sql
-- Fintelis SaaS - Diagrama Final (v7)
-- Lógica: PDV ("cash_register") separado de "bank_account"

-- 0. TABELA DE USUÁRIO
CREATE TABLE "user" (
    "id" BIGSERIAL PRIMARY KEY,
    "first_name" VARCHAR(150) NOT NULL UNIQUE,
    "last_name" VARCHAR(150) NOT NULL UNIQUE,
    "email" VARCHAR(255) NOT NULL
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
    "type" VARCHAR(50) NOT NULL, -- Ex: 'checking', 'savings'
    "initial_balance" DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- O "Processador" do dinheiro (Caixas/PDV) - NOVA TABELA
CREATE TABLE "cash_register" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "name" VARCHAR(100) NOT NULL, -- Ex: "Caixa 1 - Bilhetagem"
    
    -- O "destino" do dinheiro processado neste caixa
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
    "type" VARCHAR(10) NOT NULL, -- 'revenue', 'expense'
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
    
    -- NOVA COLUNA (Opcional): O Processador
    "cash_register_id" BIGINT NULL REFERENCES "cash_register" ("id"), 
    
    "description" VARCHAR(255) NOT NULL,
    "amount" DECIMAL(15, 2) NOT NULL,
    "type" VARCHAR(10) NOT NULL, -- 'revenue', 'expense'
    "transaction_date" DATE NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- Contas a Pagar (A Promessa)
CREATE TABLE "bill" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "category_id" BIGINT NULL REFERENCES "category" ("id"),
    "payment_transaction_id" BIGINT NULL REFERENCES "transaction" ("id"),
    "description" VARCHAR(255) NOT NULL,
    "amount" DECIMAL(15, 2) NOT NULL,
    "due_date" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL, -- Ex: 'open', 'paid'
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT (now())
);

-- Contas a Receber (A Promessa)
CREATE TABLE "income" (
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "category_id" BIGINT NULL REFERENCES "category" ("id"),
    "payment_transaction_id" BIGINT NULL REFERENCES "transaction" ("id"),
    "description" VARCHAR(255) NOT NULL,
    "amount" DECIMAL(15, 2) NOT NULL,
    "due_date" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL, -- Ex: 'sent', 'paid'
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

CREATE TABLE "inventory" ( -- Estoque
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
    "id" BIGSERIAL PRIMARY KEY,
    "company_id" BIGINT NOT NULL REFERENCES "company" ("id"),
    "message" TEXT NOT NULL,
    "is_read" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT (now()),
    "link_to_bill_id" BIGINT NULL REFERENCES "bill" ("id"),
    "link_to_income_id" BIGINT NULL REFERENCES "income" ("id"),
    "link_to_stock_item_id" BIGINT NULL REFERENCES "stock_item" ("id")
);

4. Alocação de Apps no Django

A IA deve organizar o projeto da seguinte forma. Todos os models.py devem ser criados nos apps designados abaixo:

    users (App)

        User (Modelo customizado, herdando de AbstractUser, login com email)

    companies (App)

        Company

        Membership

    financials (App)

        BankAccount (O Destino: Banco, Cofre)

        CashRegister (O Processador: Caixa/PDV)

        Category (Categoria Financeira)

        Transaction

        Bill

        Income

    inventory (App)

        ProductCategory (Categoria de Produto)

        Product

        InventoryLocation

        StockItem

        InventoryMovement

    notifications (App)

        Notification

    dashboards (App)

        Sem modelos. Apenas ViewSets e Serializers (read-only) que consomem dados de outros apps.

    reports (App)

        Sem modelos. Apenas Views ou Tasks (Celery) para gerar e disparar downloads (PDF, CSV).

5. Regras de Negócio Fundamentais (Lógica Crítica)

A IA deve implementar as seguintes lógicas de negócio:

5.1. A Regra de Ouro: Multi-Tenancy (Isolamento de Dados)

    Regra: Um User (autenticado) SÓ PODE ver ou criar dados da Company que está "ativa" em sua sessão.

    Implementação:

        Todos os ViewSets (ModelViewSet) de financials, inventory e notifications devem ter um permission_classes que verifica se o request.user é membro da Company (via Membership).

        Todos os ViewSets devem sobrescrever get_queryset() para filtrar os resultados pelo company_id ativo. Ex: self.queryset.filter(company=request.active_company).

        Todos os ViewSets devem sobrescrever perform_create() para injetar automaticamente o company_id ativo no novo objeto. Ex: serializer.save(company=request.active_company).

5.2. Lógica de Ponto de Venda (PDV) vs. Banco

    Regra: O sistema deve diferenciar a Origem/Processador (o CashRegister) do Destino (o BankAccount).

    Implementação:

        Transação de Caixa (PDV): Ao criar uma Transaction originada de um PDV (ex: "Caixa 1"), a API deve receber o cash_register_id (ex: ID 10). O bank_account_id da transação deve ser preenchido automaticamente com o default_bank_account_id (ex: ID 1) associado a esse caixa.

        Transação Direta: Ao criar uma Transaction direta (ex: PIX, TED), o cash_register_id deve ser NULL e o bank_account_id é fornecido diretamente pelo usuário.

        Relatórios: Os relatórios devem permitir agrupar SUM(amount) por bank_account_id (Saldo da Conta) e, separadamente, por cash_register_id (Vendas do Caixa).

5.3. A Lógica de "Baixa" Financeira (Atomicidade)

    Regra: O ato de "pagar" um Bill ou "receber" um Income deve ser uma transação atômica (@transaction.atomic).

    Fluxo (Pagar Bill):

        O usuário deve acionar uma action customizada no DRF (ex: POST /api/financials/bills/{id}/record_payment/).

        O payload deve conter o bank_account_id (de onde o dinheiro saiu) e a transaction_date. (O cash_register_id aqui será NULL).

        A lógica deve: a. Criar uma Transaction (tipo expense) com o valor do Bill e o bank_account_id. b. Mudar o status do Bill para paid. c. Salvar o ID da nova Transaction no campo payment_transaction_id do Bill.

    Fluxo (Receber Income):

        Mesma lógica acima (ex: POST /api/financials/income/{id}/record_payment/), mas: a. Cria uma Transaction (tipo revenue). b. Muda o status do Income para paid. c. Associa o payment_transaction_id do Income.

5.4. A Lógica de Movimentação de Estoque (Kardex)

    Regra: O campo quantity_on_hand na tabela StockItem é a fonte da verdade para a quantidade. Este campo NÃO é alterado diretamente.

    Implementação:

        Para alterar o estoque (ex: dar entrada de +10), a API deve criar um novo registro em inventory_movements (ex: quantity_changed=10).

        Imediatamente após (via signal post_save ou em uma classe de Serviço), a lógica deve atualizar o StockItem correspondente (stock_item_id).

        A atualização deve usar F() para evitar race conditions: stock_item.quantity_on_hand = F('quantity_on_hand') + movement.quantity_changed stock_item.save(update_fields=['quantity_on_hand'])

5.5. A Lógica de Alertas (Assíncrona e Instantânea)

    Alertas Financeiros:

        Implementação: Uma task agendada do Celery (rodando 1x por dia).

        Lógica: A task escaneia todos os Bill e Income com status 'open'/'sent' cuja due_date esteja próxima (ex: D-5).

        Ação: Cria um registro na tabela Notification para cada item encontrado.

    Alertas de Estoque:

        Implementação: Instantânea, acionada pela Lógica 5.4 (Movimentação de Estoque).

        Lógica: Após stock_item.save(), o backend deve verificar: if stock_item.quantity_on_hand <= stock_item.product.min_stock_level:

        Ação: Se for verdade (e não houver alerta não lido), cria um Notification com link_to_stock_item_id.