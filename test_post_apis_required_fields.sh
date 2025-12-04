#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"
COOKIES_FILE="test_cookies.txt"

echo -e "${BLUE}=== Teste das APIs POST - Campos Obrigatórios ===${NC}\n"

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

# 3. Buscar category e cost_center
echo -e "${YELLOW}3. Buscando category e cost_center...${NC}"
CATEGORY_UUID=$(curl -s -X GET "${BASE_URL}/api/v1/financials/categories/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
# API retorna {'despesas': [...], 'receitas': [...]}
if isinstance(d, dict):
    despesas = d.get('despesas', [])
    if despesas:
        print(despesas[0]['id'])
    else:
        receitas = d.get('receitas', [])
        if receitas:
            print(receitas[0]['id'])
elif isinstance(d, list):
    print(d[0]['id'] if d else '')
else:
    results = d.get('results', [])
    print(results[0]['id'] if results else '')
" 2>/dev/null)

# Buscar cost_center via shell do Django
COST_CENTER_UUID=$(docker-compose exec -T app python manage.py shell -c "
from apps.companies.models import CostCenter
from apps.companies.models import Company
company = Company.objects.get(id='${COMPANY_ID}')
cost_center = CostCenter.objects.filter(company=company).first()
if cost_center:
    print(cost_center.id)
else:
    # Criar um cost center padrão
    cost_center = CostCenter.objects.create(company=company, name='Administração')
    print(cost_center.id)
" 2>/dev/null | tail -1 | tr -d '\r\n')

if [ -z "$CATEGORY_UUID" ] || [ -z "$COST_CENTER_UUID" ]; then
  echo -e "${RED}Erro: Não foi possível encontrar category ou cost_center${NC}"
  echo "Category UUID: $CATEGORY_UUID"
  echo "Cost Center UUID: $COST_CENTER_UUID"
  exit 1
fi

echo -e "${GREEN}✓ Category: ${CATEGORY_UUID:0:8}...${NC}"
echo -e "${GREEN}✓ Cost Center: ${COST_CENTER_UUID:0:8}...${NC}\n"

# 4. Testar POST Bill sem category/cost_center (deve falhar)
echo -e "${YELLOW}4. Testando POST Bill SEM category e cost_center (deve falhar)...${NC}"
BILL_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/bills/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Teste Bill sem category",
    "amount": "100.00",
    "due_date": "2025-12-31"
  }')

if echo "$BILL_RESPONSE" | grep -q "obrigat\|required\|category\|cost_center"; then
  echo -e "${GREEN}✓ Validação funcionando - erro retornado corretamente${NC}"
  echo "$BILL_RESPONSE" | python3 -m json.tool 2>/dev/null | head -10
else
  echo -e "${RED}✗ Validação NÃO funcionou - deveria ter retornado erro${NC}"
  echo "$BILL_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$BILL_RESPONSE"
fi

echo ""

# 5. Testar POST Bill COM category e cost_center (deve funcionar)
echo -e "${YELLOW}5. Testando POST Bill COM category e cost_center (deve funcionar)...${NC}"
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

# 6. Testar POST Income sem category/cost_center (deve falhar)
echo -e "${YELLOW}6. Testando POST Income SEM category e cost_center (deve falhar)...${NC}"
INCOME_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/incomes/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Teste Income sem category",
    "amount": "200.00",
    "due_date": "2025-12-31"
  }')

if echo "$INCOME_RESPONSE" | grep -q "obrigat\|required\|category\|cost_center"; then
  echo -e "${GREEN}✓ Validação funcionando - erro retornado corretamente${NC}"
  echo "$INCOME_RESPONSE" | python3 -m json.tool 2>/dev/null | head -10
else
  echo -e "${RED}✗ Validação NÃO funcionou - deveria ter retornado erro${NC}"
  echo "$INCOME_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$INCOME_RESPONSE"
fi

echo ""

# 7. Buscar category de receita
echo -e "${YELLOW}7. Buscando category de receita...${NC}"
REVENUE_CATEGORY_UUID=$(curl -s -X GET "${BASE_URL}/api/v1/financials/categories/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
# API retorna {'despesas': [...], 'receitas': [...]}
if isinstance(d, dict):
    receitas = d.get('receitas', [])
    if receitas:
        print(receitas[0]['id'])
    else:
        despesas = d.get('despesas', [])
        if despesas:
            print(despesas[0]['id'])
elif isinstance(d, list):
    for item in d:
        if item.get('type') == 'receita':
            print(item['id'])
            break
else:
    results = d.get('results', [])
    for item in results:
        if item.get('type') == 'receita':
            print(item['id'])
            break
" 2>/dev/null)

if [ -z "$REVENUE_CATEGORY_UUID" ]; then
  echo -e "${YELLOW}⚠ Nenhuma category de receita encontrada, usando a mesma${NC}"
  REVENUE_CATEGORY_UUID="$CATEGORY_UUID"
fi

echo -e "${GREEN}✓ Revenue Category: ${REVENUE_CATEGORY_UUID:0:8}...${NC}\n"

# 8. Testar POST Income COM category e cost_center (deve funcionar)
echo -e "${YELLOW}8. Testando POST Income COM category e cost_center (deve funcionar)...${NC}"
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

# 9. Testar POST RecurringBill sem category/cost_center (deve falhar)
echo -e "${YELLOW}9. Testando POST RecurringBill SEM category e cost_center (deve falhar)...${NC}"
RECURRING_BILL_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/recurring-bills/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Teste RecurringBill sem category",
    "amount": "300.00",
    "frequency": "monthly",
    "start_date": "2025-01-01",
    "next_due_date": "2025-02-01"
  }')

if echo "$RECURRING_BILL_RESPONSE" | grep -q "obrigat\|required\|category\|cost_center"; then
  echo -e "${GREEN}✓ Validação funcionando - erro retornado corretamente${NC}"
  echo "$RECURRING_BILL_RESPONSE" | python3 -m json.tool 2>/dev/null | head -10
else
  echo -e "${RED}✗ Validação NÃO funcionou - deveria ter retornado erro${NC}"
  echo "$RECURRING_BILL_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RECURRING_BILL_RESPONSE"
fi

echo ""

# 10. Testar POST RecurringBill COM category e cost_center (deve funcionar)
echo -e "${YELLOW}10. Testando POST RecurringBill COM category e cost_center (deve funcionar)...${NC}"
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

# 11. Testar POST RecurringIncome sem category/cost_center (deve falhar)
echo -e "${YELLOW}11. Testando POST RecurringIncome SEM category e cost_center (deve falhar)...${NC}"
RECURRING_INCOME_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/recurring-incomes/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Teste RecurringIncome sem category",
    "amount": "400.00",
    "frequency": "monthly",
    "start_date": "2025-01-01",
    "next_due_date": "2025-02-01"
  }')

if echo "$RECURRING_INCOME_RESPONSE" | grep -q "obrigat\|required\|category\|cost_center"; then
  echo -e "${GREEN}✓ Validação funcionando - erro retornado corretamente${NC}"
  echo "$RECURRING_INCOME_RESPONSE" | python3 -m json.tool 2>/dev/null | head -10
else
  echo -e "${RED}✗ Validação NÃO funcionou - deveria ter retornado erro${NC}"
  echo "$RECURRING_INCOME_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RECURRING_INCOME_RESPONSE"
fi

echo ""

# 12. Testar POST RecurringIncome COM category e cost_center (deve funcionar)
echo -e "${YELLOW}12. Testando POST RecurringIncome COM category e cost_center (deve funcionar)...${NC}"
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
echo -e "${BLUE}=== Testes Concluídos ===${NC}"

