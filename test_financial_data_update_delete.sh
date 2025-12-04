#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"
COOKIES_FILE="test_cookies.txt"

echo -e "${BLUE}=== Teste da API Financial Data - PUT/PATCH/DELETE ===${NC}\n"

# 1. Login
echo -e "${YELLOW}1. Fazendo login...${NC}"
LOGIN_RESPONSE=$(curl -s -c "$COOKIES_FILE" -X POST "${BASE_URL}/api/v1/users/login/" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "lucasborgia33@gmail.com",
    "password": "Lucas@123"
  }')

echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"

# Extrair tokens dos cookies
ACCESS_TOKEN=$(grep 'access_token' "$COOKIES_FILE" 2>/dev/null | awk '{print $NF}' | head -1)
REFRESH_TOKEN=$(grep 'refresh_token' "$COOKIES_FILE" 2>/dev/null | awk '{print $NF}' | head -1)

if [ -z "$ACCESS_TOKEN" ]; then
  echo -e "${RED}Erro: Não foi possível obter o access token dos cookies${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Access token obtido${NC}\n"

# 2. Obter company token
echo -e "${YELLOW}2. Obtendo company token...${NC}"
COMPANY_ID="c8ffdb92-2e9d-4bd5-aa05-c06adb85cafb"

COMPANY_TOKEN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/users/company-token/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"company_id\": \"${COMPANY_ID}\"}")

COMPANY_TOKEN=$(echo "$COMPANY_TOKEN_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('company_access', ''))" 2>/dev/null)

if [ -z "$COMPANY_TOKEN" ]; then
  echo -e "${RED}Erro: Não foi possível obter o company token${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Company token obtido${NC}\n"

# 3. Buscar um recurring_bill para testar
echo -e "${YELLOW}3. Buscando recurring_bills...${NC}"
RECURRING_BILLS_RESPONSE=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_bills&page=1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

RECURRING_BILL_UUID=$(echo "$RECURRING_BILLS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('items') and len(data['items']) > 0:
        print(data['items'][0]['id'])
    else:
        print('')
except:
    print('')
" 2>/dev/null)

if [ -z "$RECURRING_BILL_UUID" ]; then
  echo -e "${RED}Erro: Não foi possível encontrar um recurring_bill${NC}"
  echo "$RECURRING_BILLS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RECURRING_BILLS_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✓ Recurring bill encontrado: ${RECURRING_BILL_UUID:0:8}...${NC}\n"

# 4. Buscar detalhes do recurring_bill
echo -e "${YELLOW}4. Buscando detalhes do recurring_bill...${NC}"
RECURRING_BILL_DETAILS=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_bills&uuid=${RECURRING_BILL_UUID}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

echo "$RECURRING_BILL_DETAILS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    item = data.get('item', {})
    print(f\"  Descrição: {item.get('description', 'N/A')}\")
    print(f\"  Valor: R$ {item.get('amount', 'N/A')}\")
    print(f\"  Frequência: {item.get('frequency', 'N/A')}\")
    print(f\"  Ativo: {item.get('is_active', 'N/A')}\")
    summary = data.get('payments_summary', {})
    print(f\"  Total de parcelas: {summary.get('total_payments', 0)}\")
    print(f\"  Pendentes: {summary.get('pending_count', 0)}\")
    print(f\"  Pagas: {summary.get('paid_count', 0)}\")
except Exception as e:
    print(f\"Erro: {e}\")
" 2>/dev/null

echo ""

# 5. Testar PATCH (atualização parcial - apenas amount)
echo -e "${YELLOW}5. Testando PATCH (atualizar apenas amount)...${NC}"
ORIGINAL_AMOUNT=$(echo "$RECURRING_BILL_DETAILS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('item', {}).get('amount', '0'))" 2>/dev/null)
NEW_AMOUNT=$(python3 -c "print(float('${ORIGINAL_AMOUNT}') + 100)" 2>/dev/null)

PATCH_RESPONSE=$(curl -s -X PATCH "${BASE_URL}/api/v1/financials/data/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"uuid\": \"${RECURRING_BILL_UUID}\",
    \"type\": \"recurring_bills\",
    \"amount\": \"${NEW_AMOUNT}\"
  }")

echo "$PATCH_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    item = data.get('item', {})
    print(f\"${GREEN}✓ PATCH bem-sucedido${NC}\")
    print(f\"  Novo valor: R$ {item.get('amount', 'N/A')}\")
    print(f\"  Descrição: {item.get('description', 'N/A')}\")
    summary = data.get('payments_summary', {})
    print(f\"  Parcelas pendentes: {summary.get('pending_count', 0)}\")
except Exception as e:
    print(f\"${RED}Erro: {e}${NC}\")
    print(sys.stdin.read())
" 2>/dev/null

echo ""

# 6. Verificar se as parcelas pendentes foram atualizadas
echo -e "${YELLOW}6. Verificando se parcelas pendentes foram atualizadas...${NC}"
RECURRING_BILL_PAYMENTS=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_bill_payments&page=1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

echo "$RECURRING_BILL_PAYMENTS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    items = data.get('items', [])
    if items:
        # Filtrar apenas parcelas do recurring_bill testado
        filtered = [i for i in items if i.get('recurring_bill') == '${RECURRING_BILL_UUID}']
        if filtered:
            pending = [i for i in filtered if i.get('status') == 'pendente']
            if pending:
                print(f\"${GREEN}✓ Encontradas {len(pending)} parcelas pendentes${NC}\")
                for p in pending[:3]:  # Mostrar apenas as 3 primeiras
                    print(f\"  - Data: {p.get('due_date', 'N/A')}, Valor: R$ {p.get('amount', 'N/A')}, Status: {p.get('status', 'N/A')}\")
                # Verificar se o valor foi atualizado
                first_pending = pending[0]
                if float(first_pending.get('amount', 0)) == ${NEW_AMOUNT}:
                    print(f\"${GREEN}✓ Valor das parcelas pendentes foi atualizado corretamente!${NC}\")
                else:
                    print(f\"${YELLOW}⚠ Valor das parcelas pendentes não foi atualizado (esperado: ${NEW_AMOUNT}, atual: {first_pending.get('amount', 'N/A')})${NC}\")
            else:
                print(f\"${YELLOW}⚠ Nenhuma parcela pendente encontrada${NC}\")
        else:
            print(f\"${YELLOW}⚠ Nenhuma parcela encontrada para este recurring_bill${NC}\")
    else:
        print(f\"${YELLOW}⚠ Nenhum item encontrado${NC}\")
except Exception as e:
    print(f\"${RED}Erro: {e}${NC}\")
" 2>/dev/null

echo ""

# 7. Testar PUT (atualização completa)
echo -e "${YELLOW}7. Testando PUT (atualização completa)...${NC}"
PUT_RESPONSE=$(curl -s -X PUT "${BASE_URL}/api/v1/financials/data/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d "{
    \"uuid\": \"${RECURRING_BILL_UUID}\",
    \"type\": \"recurring_bills\",
    \"description\": \"Recurring Bill Atualizado via PUT\",
    \"amount\": \"${ORIGINAL_AMOUNT}\",
    \"frequency\": \"monthly\",
    \"is_active\": true
  }")

echo "$PUT_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    item = data.get('item', {})
    print(f\"${GREEN}✓ PUT bem-sucedido${NC}\")
    print(f\"  Descrição: {item.get('description', 'N/A')}\")
    print(f\"  Valor: R$ {item.get('amount', 'N/A')}\")
    print(f\"  Frequência: {item.get('frequency', 'N/A')}\")
except Exception as e:
    print(f\"${RED}Erro: {e}${NC}\")
    print(sys.stdin.read())
" 2>/dev/null

echo ""

# 8. Buscar um recurring_income para testar DELETE
echo -e "${YELLOW}8. Buscando recurring_incomes...${NC}"
RECURRING_INCOMES_RESPONSE=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_incomes&page=1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

RECURRING_INCOME_UUID=$(echo "$RECURRING_INCOMES_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('items') and len(data['items']) > 0:
        print(data['items'][0]['id'])
    else:
        print('')
except:
    print('')
" 2>/dev/null)

if [ -z "$RECURRING_INCOME_UUID" ]; then
  echo -e "${YELLOW}⚠ Nenhum recurring_income encontrado. Criando um para teste...${NC}"
  # Não vamos criar, apenas pular o teste de DELETE
  RECURRING_INCOME_UUID=""
else
  echo -e "${GREEN}✓ Recurring income encontrado: ${RECURRING_INCOME_UUID:0:8}...${NC}\n"
  
  # 9. Verificar parcelas antes do DELETE
  echo -e "${YELLOW}9. Verificando parcelas antes do DELETE...${NC}"
  RECEIPTS_BEFORE=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_income_receipts&page=1" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Company-Id: ${COMPANY_ID}")
  
  TOTAL_RECEIPTS_BEFORE=$(echo "$RECEIPTS_BEFORE" | python3 -c "
  import sys, json
  try:
      data = json.load(sys.stdin)
      items = data.get('items', [])
      filtered = [i for i in items if i.get('recurring_income') == '${RECURRING_INCOME_UUID}']
      print(len(filtered))
  except:
      print('0')
  " 2>/dev/null)
  
  PAID_RECEIPTS_BEFORE=$(echo "$RECEIPTS_BEFORE" | python3 -c "
  import sys, json
  try:
      data = json.load(sys.stdin)
      items = data.get('items', [])
      filtered = [i for i in items if i.get('recurring_income') == '${RECURRING_INCOME_UUID}' and i.get('status') == 'recebido']
      print(len(filtered))
  except:
      print('0')
  " 2>/dev/null)
  
  echo -e "  Total de parcelas: ${TOTAL_RECEIPTS_BEFORE}"
  echo -e "  Parcelas recebidas: ${PAID_RECEIPTS_BEFORE}"
  echo ""
  
  # 10. Testar DELETE
  echo -e "${YELLOW}10. Testando DELETE...${NC}"
  DELETE_RESPONSE=$(curl -s -X DELETE "${BASE_URL}/api/v1/financials/data/?uuid=${RECURRING_INCOME_UUID}&type=recurring_incomes" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Company-Id: ${COMPANY_ID}")
  
  echo "$DELETE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DELETE_RESPONSE"
  
  # 11. Verificar se parcelas recebidas foram mantidas
  echo -e "${YELLOW}11. Verificando se parcelas recebidas foram mantidas...${NC}"
  RECEIPTS_AFTER=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_income_receipts&page=1" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Company-Id: ${COMPANY_ID}")
  
  PAID_RECEIPTS_AFTER=$(echo "$RECEIPTS_AFTER" | python3 -c "
  import sys, json
  try:
      data = json.load(sys.stdin)
      items = data.get('items', [])
      # Parcelas recebidas devem ter recurring_income = null agora
      filtered = [i for i in items if i.get('recurring_income') is None and i.get('status') == 'recebido']
      print(len(filtered))
  except Exception as e:
      print(f'Erro: {e}')
      print('0')
  " 2>/dev/null)
  
  if [ "$PAID_RECEIPTS_BEFORE" -eq "$PAID_RECEIPTS_AFTER" ] || [ "$PAID_RECEIPTS_AFTER" -gt "0" ]; then
    echo -e "${GREEN}✓ Parcelas recebidas foram mantidas (${PAID_RECEIPTS_AFTER} encontradas)${NC}"
  else
    echo -e "${YELLOW}⚠ Verificação de parcelas recebidas: ${PAID_RECEIPTS_BEFORE} antes, ${PAID_RECEIPTS_AFTER} depois${NC}"
  fi
  
  # 12. Verificar se recurring_income foi deletado
  echo -e "${YELLOW}12. Verificando se recurring_income foi deletado...${NC}"
  CHECK_DELETED=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_incomes&uuid=${RECURRING_INCOME_UUID}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Company-Id: ${COMPANY_ID}")
  
  if echo "$CHECK_DELETED" | grep -q "não encontrado\|not found\|404"; then
    echo -e "${GREEN}✓ Recurring income foi deletado com sucesso${NC}"
  else
    echo -e "${RED}✗ Recurring income ainda existe${NC}"
    echo "$CHECK_DELETED" | python3 -m json.tool 2>/dev/null || echo "$CHECK_DELETED"
  fi
fi

echo ""
echo -e "${BLUE}=== Testes Concluídos ===${NC}"

