#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"
COOKIES_FILE="test_cookies.txt"

echo -e "${BLUE}=== Teste CRUD Cost Center ===${NC}\n"

# 1. Login
echo -e "${YELLOW}1. Fazendo login...${NC}"
LOGIN_RESPONSE=$(curl -s -c "$COOKIES_FILE" -X POST "${BASE_URL}/api/v1/users/login/" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "lucasborgia33@gmail.com",
    "password": "Lucas@123"
  }')

ACCESS_TOKEN=$(grep 'access_token' "$COOKIES_FILE" 2>/dev/null | awk '{print $NF}' | head -1)
COMPANY_ID="c8ffdb92-2e9d-4bd5-aa05-c06adb85cafb"

if [ -z "$ACCESS_TOKEN" ]; then
  echo -e "${RED}Erro: Não foi possível obter o access token${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Login realizado${NC}\n"

# 2. Obter company token
echo -e "${YELLOW}2. Obtendo company token...${NC}"
COMPANY_TOKEN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/users/company-token/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"company_id\": \"${COMPANY_ID}\"}")

echo -e "${GREEN}✓ Company token obtido${NC}\n"

# 3. GET - Listar cost centers
echo -e "${YELLOW}3. GET - Listando cost centers...${NC}"
GET_RESPONSE=$(curl -s -X GET "${BASE_URL}/api/v1/companies/cost-centers/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

if echo "$GET_RESPONSE" | grep -q "\"id\""; then
  echo -e "${GREEN}✓ Cost centers listados com sucesso${NC}"
  echo "$GET_RESPONSE" | python3 -m json.tool 2>/dev/null | head -20
else
  echo -e "${YELLOW}⚠ Nenhum cost center encontrado ou resposta diferente${NC}"
  echo "$GET_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$GET_RESPONSE"
fi

echo ""

# 4. POST - Criar cost center
echo -e "${YELLOW}4. POST - Criando cost center...${NC}"
POST_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/companies/cost-centers/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Teste Cost Center CRUD"
  }')

if echo "$POST_RESPONSE" | grep -q "\"id\""; then
  COST_CENTER_UUID=$(echo "$POST_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id', ''))" 2>/dev/null)
  COST_CENTER_CODE=$(echo "$POST_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('code', ''))" 2>/dev/null)
  echo -e "${GREEN}✓ Cost center criado com sucesso${NC}"
  echo -e "  ID: ${COST_CENTER_UUID:0:8}..."
  echo -e "  Code: ${COST_CENTER_CODE}"
  echo "$POST_RESPONSE" | python3 -m json.tool 2>/dev/null
else
  echo -e "${RED}✗ Erro ao criar cost center${NC}"
  echo "$POST_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$POST_RESPONSE"
  exit 1
fi

echo ""

# 5. GET - Buscar cost center específico
echo -e "${YELLOW}5. GET - Buscando cost center específico...${NC}"
GET_DETAIL_RESPONSE=$(curl -s -X GET "${BASE_URL}/api/v1/companies/cost-centers/${COST_CENTER_UUID}/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

if echo "$GET_DETAIL_RESPONSE" | grep -q "\"id\""; then
  echo -e "${GREEN}✓ Cost center encontrado${NC}"
  echo "$GET_DETAIL_RESPONSE" | python3 -m json.tool 2>/dev/null
else
  echo -e "${RED}✗ Erro ao buscar cost center${NC}"
  echo "$GET_DETAIL_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$GET_DETAIL_RESPONSE"
fi

echo ""

# 6. PATCH - Atualizar cost center
echo -e "${YELLOW}6. PATCH - Atualizando cost center...${NC}"
PATCH_RESPONSE=$(curl -s -X PATCH "${BASE_URL}/api/v1/companies/cost-centers/${COST_CENTER_UUID}/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Teste Cost Center CRUD - Atualizado"
  }')

if echo "$PATCH_RESPONSE" | grep -q "\"id\""; then
  echo -e "${GREEN}✓ Cost center atualizado com sucesso${NC}"
  echo "$PATCH_RESPONSE" | python3 -m json.tool 2>/dev/null
else
  echo -e "${RED}✗ Erro ao atualizar cost center${NC}"
  echo "$PATCH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$PATCH_RESPONSE"
fi

echo ""

# 7. PUT - Atualizar cost center (full update)
echo -e "${YELLOW}7. PUT - Atualizando cost center (full update)...${NC}"
PUT_RESPONSE=$(curl -s -X PUT "${BASE_URL}/api/v1/companies/cost-centers/${COST_CENTER_UUID}/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Teste Cost Center CRUD - PUT\"
  }")

if echo "$PUT_RESPONSE" | grep -q "\"id\""; then
  echo -e "${GREEN}✓ Cost center atualizado com PUT${NC}"
  echo "$PUT_RESPONSE" | python3 -m json.tool 2>/dev/null
else
  echo -e "${RED}✗ Erro ao atualizar cost center com PUT${NC}"
  echo "$PUT_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$PUT_RESPONSE"
fi

echo ""

# 8. DELETE - Deletar cost center
echo -e "${YELLOW}8. DELETE - Deletando cost center...${NC}"
DELETE_RESPONSE=$(curl -s -w "\nHTTP Status: %{http_code}\n" -X DELETE "${BASE_URL}/api/v1/companies/cost-centers/${COST_CENTER_UUID}/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

HTTP_STATUS=$(echo "$DELETE_RESPONSE" | grep "HTTP Status" | awk '{print $3}')

if [ "$HTTP_STATUS" = "204" ] || [ "$HTTP_STATUS" = "200" ]; then
  echo -e "${GREEN}✓ Cost center deletado com sucesso${NC}"
else
  echo -e "${RED}✗ Erro ao deletar cost center (Status: $HTTP_STATUS)${NC}"
  echo "$DELETE_RESPONSE"
fi

echo ""
echo -e "${BLUE}=== Teste CRUD Cost Center Concluído ===${NC}\n"

# Agora vamos testar os POSTs de income, bill, etc.
echo -e "${BLUE}=== Teste POSTs com Cost Center Obrigatório ===${NC}\n"

# 9. Buscar category e criar cost center para os testes
echo -e "${YELLOW}9. Buscando category e criando cost center para testes...${NC}"
CATEGORY_UUID=$(curl -s -X GET "${BASE_URL}/api/v1/financials/categories/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if isinstance(d, dict):
    despesas = d.get('despesas', [])
    if despesas:
        print(despesas[0]['id'])
    else:
        receitas = d.get('receitas', [])
        if receitas:
            print(receitas[0]['id'])
" 2>/dev/null)

# Criar cost center para os testes
COST_CENTER_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/companies/cost-centers/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cost Center para Testes"
  }')

COST_CENTER_UUID=$(echo "$COST_CENTER_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id', ''))" 2>/dev/null)

if [ -z "$CATEGORY_UUID" ] || [ -z "$COST_CENTER_UUID" ]; then
  echo -e "${RED}Erro: Não foi possível encontrar category ou criar cost_center${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Category: ${CATEGORY_UUID:0:8}...${NC}"
echo -e "${GREEN}✓ Cost Center: ${COST_CENTER_UUID:0:8}...${NC}\n"

# 10. Testar POST Bill COM category e cost_center
echo -e "${YELLOW}10. Testando POST Bill COM category e cost_center...${NC}"
BILL_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/bills/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"Teste Bill com category e cost_center\",
    \"amount\": \"100.00\",
    \"due_date\": \"2025-12-31\",
    \"category\": \"${CATEGORY_UUID}\",
    \"cost_center\": \"${COST_CENTER_UUID}\"
  }")

if echo "$BILL_RESPONSE" | grep -q "\"id\""; then
  BILL_UUID=$(echo "$BILL_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id', ''))" 2>/dev/null)
  echo -e "${GREEN}✓ Bill criado com sucesso: ${BILL_UUID:0:8}...${NC}"
else
  echo -e "${RED}✗ Erro ao criar Bill${NC}"
  echo "$BILL_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$BILL_RESPONSE"
fi

echo ""

# 11. Buscar category de receita
REVENUE_CATEGORY_UUID=$(curl -s -X GET "${BASE_URL}/api/v1/financials/categories/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if isinstance(d, dict):
    receitas = d.get('receitas', [])
    if receitas:
        print(receitas[0]['id'])
    else:
        despesas = d.get('despesas', [])
        if despesas:
            print(despesas[0]['id'])
" 2>/dev/null)

# 12. Testar POST Income COM category e cost_center
echo -e "${YELLOW}12. Testando POST Income COM category e cost_center...${NC}"
INCOME_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/incomes/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"Teste Income com category e cost_center\",
    \"amount\": \"200.00\",
    \"due_date\": \"2025-12-31\",
    \"category\": \"${REVENUE_CATEGORY_UUID}\",
    \"cost_center\": \"${COST_CENTER_UUID}\"
  }")

if echo "$INCOME_RESPONSE" | grep -q "\"id\""; then
  INCOME_UUID=$(echo "$INCOME_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id', ''))" 2>/dev/null)
  echo -e "${GREEN}✓ Income criado com sucesso: ${INCOME_UUID:0:8}...${NC}"
else
  echo -e "${RED}✗ Erro ao criar Income${NC}"
  echo "$INCOME_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$INCOME_RESPONSE"
fi

echo ""

# 13. Testar POST RecurringBill COM category e cost_center
echo -e "${YELLOW}13. Testando POST RecurringBill COM category e cost_center...${NC}"
RECURRING_BILL_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/recurring-bills/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"Teste RecurringBill com category e cost_center\",
    \"amount\": \"300.00\",
    \"frequency\": \"monthly\",
    \"start_date\": \"2025-01-01\",
    \"next_due_date\": \"2025-02-01\",
    \"category\": \"${CATEGORY_UUID}\",
    \"cost_center\": \"${COST_CENTER_UUID}\"
  }")

if echo "$RECURRING_BILL_RESPONSE" | grep -q "\"id\""; then
  RECURRING_BILL_UUID=$(echo "$RECURRING_BILL_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id', ''))" 2>/dev/null)
  echo -e "${GREEN}✓ RecurringBill criado com sucesso: ${RECURRING_BILL_UUID:0:8}...${NC}"
else
  echo -e "${RED}✗ Erro ao criar RecurringBill${NC}"
  echo "$RECURRING_BILL_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RECURRING_BILL_RESPONSE"
fi

echo ""

# 14. Testar POST RecurringIncome COM category e cost_center
echo -e "${YELLOW}14. Testando POST RecurringIncome COM category e cost_center...${NC}"
RECURRING_INCOME_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/recurring-incomes/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"Teste RecurringIncome com category e cost_center\",
    \"amount\": \"400.00\",
    \"frequency\": \"monthly\",
    \"start_date\": \"2025-01-01\",
    \"next_due_date\": \"2025-02-01\",
    \"category\": \"${REVENUE_CATEGORY_UUID}\",
    \"cost_center\": \"${COST_CENTER_UUID}\"
  }")

if echo "$RECURRING_INCOME_RESPONSE" | grep -q "\"id\""; then
  RECURRING_INCOME_UUID=$(echo "$RECURRING_INCOME_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id', ''))" 2>/dev/null)
  echo -e "${GREEN}✓ RecurringIncome criado com sucesso: ${RECURRING_INCOME_UUID:0:8}...${NC}"
else
  echo -e "${RED}✗ Erro ao criar RecurringIncome${NC}"
  echo "$RECURRING_INCOME_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RECURRING_INCOME_RESPONSE"
fi

echo ""
echo -e "${BLUE}=== Todos os Testes Concluídos ===${NC}"

