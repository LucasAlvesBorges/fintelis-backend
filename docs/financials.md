# Fintelis – APIs do Módulo Financeiro

Este documento complementa o `doc.md` e descreve como consumir as APIs expostas em `/api/v1/financials/`. Todos os endpoints são compatíveis com JSON e seguem as regras multi-tenant descritas na seção 5 do documento principal.

---

## Requisitos Comuns

- **Autenticação**: `Authorization: Bearer <JWT>`. O login e refresh continuam sendo feitos via `/api/v1/users/`.
- **Empresa Ativa**: toda requisição precisa informar a empresa corrente. Utilize o header `X-Company-ID: <company_id>`. (Caso um middleware injete `request.active_company`, o header torna-se opcional, mas o client não deve depender disso.)
- **Escopo**: qualquer ID enviado no corpo (bank_account, category, etc.) deve pertencer à mesma empresa ativa. Violações retornam `403` ou `400` com detalhes.
- **Respostas**: seguem o padrão DRF (`HTTP 200/201` com o serializer completo, `204` sem corpo em deleções, erros com `{"detail": "..."}"`).

---

## Sumário de Endpoints

| Recurso | Método | Path | Observações |
| --- | --- | --- | --- |
| Banks | GET | `/api/v1/financials/banks/` | Catálogo global (código, nome, logo SVG); somente leitura |
| BankAccount | GET/POST | `/api/v1/financials/bank-accounts/` | CRUD; `bank` opcional vinculado ao catálogo |
| CashRegister | GET/POST | `/api/v1/financials/cash-registers/` | `default_bank_account` deve ser da mesma empresa |
| Category | GET/POST | `/api/v1/financials/categories/` | Hierárquica (`parent`); tipo igual ao pai |
| Transaction | GET/POST | `/api/v1/financials/transactions/` | PDV, transferências, `contact`, estorno |
| Transaction Transfer | POST | `/api/v1/financials/transactions/transfer/` | Cria duas transações linkadas atômicas |
| Transaction Refund | POST | `/api/v1/financials/transactions/{id}/refund/` | Estorno parcial/total de receitas |
| Bill | GET/POST | `/api/v1/financials/bills/` | `contact` fornecedor/ambos; status `a_vencer`/`quitada` |
| Bill Payment | POST | `/api/v1/financials/bills/{id}/record-payment/` | Cria `Transaction` do tipo `despesa` |
| Income | GET/POST | `/api/v1/financials/incomes/` | `contact` cliente/ambos; status `pendente`/`recebido` |
| Income Payment | POST | `/api/v1/financials/incomes/{id}/record-payment/` | Cria `Transaction` do tipo `receita` |
| RecurringBill | GET/POST | `/api/v1/financials/recurring-bills/` | Moldes para contas a pagar |
| RecurringIncome | GET/POST | `/api/v1/financials/recurring-incomes/` | Moldes para contas a receber |

---

## Bancos globais (`/banks/`)

- Catálogo independente de empresa: `code`, `name`, `cnpj` (opcional), `is_active`, `logo` (FileField SVG).
- Logos são servidas via `MEDIA_URL` (em dev, já exposto quando DEBUG=True).
- Seed: coloque SVGs em `media/bank_logos_source/{code}.svg` e rode `python manage.py seed_banks`. Códigos suportados: 001, 033, 041, 070, 077, 104, 208, 212, 237, 260, 290, 318, 336, 341, 422, 4225 (PAN), 655, 707, 748, 756, 9997 (PicPay), 999 (créditos bilhetagem).

---

## Bank Accounts (`/bank-accounts/`)

### Campos
```json
{
  "id": 1,
  "company": 10,
  "bank": null,
  "name": "Itau CC",
  "type": "conta_corrente",
  "initial_balance": "5000.00",
  "created_at": "2025-11-10T13:00:00Z",
  "updated_at": "2025-11-10T13:00:00Z"
}
```

### Exemplo de criação
```bash
curl -X POST /api/v1/financials/bank-accounts/ \
  -H "Authorization: Bearer <token>" \
  -H "X-Company-ID: 10" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Banco de Crédito",
    "type": "banco_de_creditos",
    "initial_balance": "25000.00"
  }'
```

- Para vincular ao catálogo, envie `bank: <id retornado em /banks/>`.

---

## Cash Registers (`/cash-registers/`)

Use para modelar PDVs. O campo `default_bank_account` define o destino obrigatório das transações originadas nesse caixa.

### Exemplo
```json
{
  "name": "Caixa 1",
  "default_bank_account": 3
}
```

---

## Categories (`/categories/`)

- `type`: `receita` ou `despesa`.
- Hierárquica: `parent` opcional; o pai deve ser da mesma empresa e ter o mesmo `type`.
- Únicas por `(company, parent, name, type)`.
- Código numérico gerado automaticamente pelo backend:
  - Raiz recebe o próximo inteiro disponível na empresa (`1`, `2`, ...).
  - Filhos herdam o código do pai e acrescentam `.<n>` conforme ordem de criação (`1.1`, `1.2`, ...).
  - Campo `code` é único por empresa e retornado nas respostas; não precisa ser enviado no payload.

---

## Transactions (`/transactions/`)

### Campos relevantes
- `bank_account`: obrigatório para todas as transações; em transações de PDV é preenchido automaticamente com o `default_bank_account`.
- `cash_register`: opcional, somente para movimentos iniciados em PDV.
- `category`: obrigatório para receitas/despesas; proibido para transferências.
- `contact`: opcional; deve pertencer à mesma empresa.
- `type`: `receita`, `despesa`, `transferencia_interna`, `transferencia_externa`, `estorno`.
- `linked_transaction`: preenchido automaticamente em transferências para apontar o par correspondente.
- `related_transaction`: preenchido em estornos para apontar a transação original.

### Criando uma transação de PDV
```bash
curl -X POST /api/v1/financials/transactions/ \
  -H "Authorization: Bearer <token>" \
  -H "X-Company-ID: 10" \
  -d '{
    "cash_register": 5,
    "description": "Venda de bilhetes",
    "amount": "180.00",
    "type": "receita",
    "transaction_date": "2025-11-10",
    "category": 8
  }'
```
> O backend injeta `bank_account` com base no caixa informado.

### Transferências entre contas

Endpoint dedicado: `POST /api/v1/financials/transactions/transfer/`

Payload:
```json
{
  "from_bank_account": 3,
  "to_bank_account": 7,
  "amount": "1200.00",
  "transaction_date": "2025-11-10",
  "description": "Reserva mensal"
}
```

Resultado: duas transações são criadas atômicamente (saída `transferencia_externa` e entrada `transferencia_interna`) e ficam mutuamente associadas via `linked_transaction`.

---

### Estorno de transação

Endpoint: `POST /api/v1/financials/transactions/{id}/refund/`

Regras:
- Apenas receitas podem ser estornadas; não estorne estornos.
- Valor do estorno deve ser > 0 e não pode exceder o saldo disponível (`amount original - soma dos estornos`).
- O estorno herda conta/categoria/caixa/contato da transação original.

Payload:
```json
{
  "amount": "2000.00",
  "description": "Devolução parcial"
}
```

Resposta: retorna a nova transação `type="estorno"` com `related_transaction` apontando para a original.

---

## Bills (`/bills/`)

Representa contas a pagar.

### Campos
```json
{
  "id": 55,
  "category": 12,
  "description": "Aluguel novembro",
  "amount": "3500.00",
  "due_date": "2025-11-30",
  "status": "a_vencer",
  "payment_transaction": null,
  "contact": 32
}
```
- `contact`: opcional; se informado, precisa ser fornecedor ou ambos. Rejeita contato de outra empresa ou `type=cliente`.

### Registrar pagamento
`POST /api/v1/financials/bills/{id}/record-payment/`

Payload:
```json
{
  "bank_account": 3,
  "transaction_date": "2025-11-05",
  "description": "PIX aluguel"
}
```

Efeitos:
1. Cria uma `Transaction` de `despesa` com o mesmo valor.
2. Relaciona a transação no campo `payment_transaction`.
3. Atualiza `status` para `quitada`.

---

## Incomes (`/incomes/`)

Semelhante aos Bills, porém para contas a receber.

### Registrar recebimento
`POST /api/v1/financials/incomes/{id}/record-payment/`

Payload:
```json
{
  "bank_account": 7,
  "transaction_date": "2025-11-12",
  "description": "Receita contrato ACME"
}
```

Cria `Transaction` de `receita` e marca o `Income` como `recebido`.
- `contact`: opcional; deve ser cliente ou ambos. Rejeita `type=fornecedor`.

---

## Recorrências

### Recurring Bills (`/recurring-bills/`)
Campos principais:
- `frequency`: `daily`, `weekly`, `monthly`, `quarterly`, `yearly`.
- `start_date`, `end_date` (opcional), `next_due_date`, `is_active`.

O job diário (Celery Beat) procura moldes com `is_active=true` e `next_due_date <= hoje` para gerar `Bill` automaticamente:
1. Copia `description`, `amount`, `category`.
2. Cria um `Bill` com `status='a_vencer'`.
3. Atualiza `next_due_date` somando a frequência.
4. Se o novo `next_due_date` ultrapassar `end_date`, ativa `is_active=false`.

### Recurring Incomes (`/recurring-incomes/`)
Mesma lógica, mas gera registros em `Income` com `status='pendente'`.

---

## Boas Práticas do Cliente

1. **Sempre** envie `X-Company-ID` (ou garanta `request.active_company`). Sem isso a API retorna `400`.
2. Trate códigos `403` como falta de vínculo (usuário não pertence à empresa) ou falta de permissão.
3. Para listagens onde o front precisa dividir grupos (por conta, caixa, categoria), prefira agregar no lado do cliente até que endpoints específicos de dashboards estejam disponíveis.
4. Ao consumir transferências, ignore tipos `transferencia_interna` e `transferencia_externa` em relatórios de receita/despesa, conforme regra 5.3 do `doc.md`.
5. Para conciliações, utilize `linked_transaction` para saber que duas transações representam a mesma transferência.

---

## Exemplos de Erros

| HTTP | body | Significado |
| --- | --- | --- |
| 400 | `{"detail": "Active company not provided..."}` | Header ausente |
| 400 | `{"category": ["Transfer transactions cannot use categories."]}` | Payload violando regra de transferência |
| 403 | `{"detail": "You do not belong to this company."}` | Usuário não é membro |

---

Para detalhes de campos adicionais (tipos, choices e validações), consulte `apps/financials/models.py`. Este documento será atualizado conforme novas actions forem adicionadas (ex: relatórios ou filtros avançados).
