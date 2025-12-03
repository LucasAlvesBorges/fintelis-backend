#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"
COOKIES_FILE="test_cookies.txt"

echo -e "${BLUE}=== Teste da API Financial Data ===${NC}\n"

# 1. Login
echo -e "${YELLOW}1. Fazendo login...${NC}"
LOGIN_RESPONSE=$(curl -s -c "$COOKIES_FILE" -X POST "${BASE_URL}/api/v1/users/login/" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "lucasborgia33@gmail.com",
    "password": "Lucas@123"
  }')

echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"

# Extrair tokens dos cookies (formato Netscape cookie file)
# As linhas começam com #HttpOnly, então pegamos a última coluna
ACCESS_TOKEN=$(grep 'access_token' "$COOKIES_FILE" 2>/dev/null | awk '{print $NF}' | head -1)
REFRESH_TOKEN=$(grep 'refresh_token' "$COOKIES_FILE" 2>/dev/null | awk '{print $NF}' | head -1)

if [ -z "$ACCESS_TOKEN" ]; then
  echo -e "${RED}Erro: Não foi possível obter o access token dos cookies${NC}"
  echo "Conteúdo do arquivo de cookies:"
  cat "$COOKIES_FILE"
  exit 1
fi

echo -e "${GREEN}✓ Access token obtido dos cookies${NC}\n"

# 2. Obter company token
echo -e "${YELLOW}2. Obtendo company token...${NC}"
COMPANY_ID="c8ffdb92-2e9d-4bd5-aa05-c06adb85cafb"

COMPANY_TOKEN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/users/company-token/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"company_id\": \"${COMPANY_ID}\"}")

echo "$COMPANY_TOKEN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$COMPANY_TOKEN_RESPONSE"

COMPANY_TOKEN=$(echo "$COMPANY_TOKEN_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('company_access', ''))" 2>/dev/null)

if [ -z "$COMPANY_TOKEN" ]; then
  echo -e "${RED}Erro: Não foi possível obter o company token${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Company token obtido${NC}\n"

# 3. Salvar tokens em arquivo (adicionar ao arquivo de cookies existente)
echo -e "${YELLOW}3. Salvando tokens em ${COOKIES_FILE}...${NC}"
{
  echo "# Tokens extraídos"
  echo "ACCESS_TOKEN=${ACCESS_TOKEN}"
  echo "REFRESH_TOKEN=${REFRESH_TOKEN}"
  echo "COMPANY_TOKEN=${COMPANY_TOKEN}"
  echo "COMPANY_ID=${COMPANY_ID}"
} >> "$COOKIES_FILE"

echo -e "${GREEN}✓ Tokens salvos em ${COOKIES_FILE}${NC}\n"

# 4. Testar GET da API
echo -e "${YELLOW}4. Testando GET /api/v1/financials/data/?type=bills...${NC}"
GET_RESPONSE=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=bills&page=1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

echo "$GET_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"✓ Total de items: {data.get('summary', {}).get('total_items', 0)}\")
    print(f\"✓ Página: {data.get('pagination', {}).get('page', 'N/A')}\")
    if data.get('items'):
        first_item = data['items'][0]
        print(f\"✓ Primeiro item: {first_item.get('description', 'N/A')} (ID: {first_item.get('id', 'N/A')[:8]}...)\")
        print(f\"✓ Status: {first_item.get('status', 'N/A')}\")
        print(f\"✓ Valor: R$ {first_item.get('amount', 'N/A')}\")
except Exception as e:
    print(f\"Erro ao processar resposta: {e}\")
    print(sys.stdin.read())
" || echo "$GET_RESPONSE"

echo ""

# 5. Buscar um item pendente para testar POST
echo -e "${YELLOW}5. Buscando um bill pendente para testar POST...${NC}"
BILL_ITEM=$(echo "$GET_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for item in data.get('items', []):
        if item.get('status') == 'a_vencer' and not item.get('payment_transaction'):
            print(item.get('id'))
            break
except:
    pass
")

if [ -z "$BILL_ITEM" ]; then
  echo -e "${RED}Erro: Não foi encontrado um bill pendente${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Bill encontrado: ${BILL_ITEM}${NC}\n"

# 6. Buscar uma conta bancária
echo -e "${YELLOW}6. Buscando uma conta bancária...${NC}"
BANK_ACCOUNTS_RESPONSE=$(curl -s -X GET "${BASE_URL}/api/v1/financials/bank-accounts/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

BANK_ACCOUNT_ID=$(echo "$BANK_ACCOUNTS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list) and len(data) > 0:
        print(data[0].get('id'))
    elif isinstance(data, dict) and 'results' in data and len(data['results']) > 0:
        print(data['results'][0].get('id'))
except:
    pass
")

if [ -z "$BANK_ACCOUNT_ID" ]; then
  echo -e "${RED}Erro: Não foi encontrada uma conta bancária${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Conta bancária encontrada: ${BANK_ACCOUNT_ID}${NC}\n"

# 7. Verificar saldo antes
echo -e "${YELLOW}7. Verificando saldo da conta bancária antes...${NC}"
BANK_ACCOUNT_DETAILS=$(curl -s -X GET "${BASE_URL}/api/v1/financials/bank-accounts/${BANK_ACCOUNT_ID}/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}")

BALANCE_BEFORE=$(echo "$BANK_ACCOUNT_DETAILS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('current_balance', '0'))
except:
    print('0')
")

echo -e "${GREEN}✓ Saldo antes: R$ ${BALANCE_BEFORE}${NC}\n"

# 8. Testar POST para criar transação
echo -e "${YELLOW}8. Testando POST /api/v1/financials/data/ para criar transação...${NC}"
POST_DATA=$(cat <<EOF
{
  "uuid": "${BILL_ITEM}",
  "type": "bills",
  "bank_account": "${BANK_ACCOUNT_ID}",
  "transaction_date": "$(date +%Y-%m-%d)",
  "description": "Teste de pagamento via API"
}
EOF
)

echo "Payload:"
echo "$POST_DATA" | python3 -m json.tool

POST_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/data/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" \
  -H "Content-Type: application/json" \
  -d "$POST_DATA")

echo -e "\nResposta:"
echo "$POST_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$POST_RESPONSE"

# Verificar se foi criado com sucesso
if echo "$POST_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'item' in data and 'payment_transaction' in data:
        print('SUCCESS')
    else:
        print('ERROR')
except:
    print('ERROR')
" | grep -q "SUCCESS"; then
  echo -e "\n${GREEN}✓ Transação criada com sucesso!${NC}"
  
  # 9. Verificar saldo depois
  echo -e "\n${YELLOW}9. Verificando saldo da conta bancária depois...${NC}"
  BANK_ACCOUNT_DETAILS_AFTER=$(curl -s -X GET "${BASE_URL}/api/v1/financials/bank-accounts/${BANK_ACCOUNT_ID}/" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Company-Id: ${COMPANY_ID}")
  
  BALANCE_AFTER=$(echo "$BANK_ACCOUNT_DETAILS_AFTER" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('current_balance', '0'))
except:
    print('0')
  ")
  
  echo -e "${GREEN}✓ Saldo depois: R$ ${BALANCE_AFTER}${NC}"
  
  # Calcular diferença
  DIFF=$(python3 -c "
before = float('$BALANCE_BEFORE')
after = float('$BALANCE_AFTER')
print(f'{after - before:.2f}')
" 2>/dev/null || echo "0")
  
  echo -e "${GREEN}✓ Diferença: R$ ${DIFF}${NC}"
  
  if [ "$(echo "$DIFF < 0" | bc -l 2>/dev/null || echo "0")" = "1" ]; then
    echo -e "${GREEN}✓ Saldo foi reduzido corretamente (despesa)${NC}"
  fi
else
  echo -e "\n${RED}✗ Erro ao criar transação${NC}"
  exit 1
fi

echo -e "\n${BLUE}=== Teste concluído ===${NC}"

