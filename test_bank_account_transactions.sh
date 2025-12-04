#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"
COOKIES_FILE="test_cookies.txt"

echo -e "${BLUE}=== Teste: Transações nos Detalhes da Bank Account ===${NC}\n"

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

# 3. Buscar uma bank account
echo -e "${YELLOW}3. Buscando bank account...${NC}"
BANK_ACCOUNT_UUID=$(curl -s -X GET "${BASE_URL}/api/v1/financials/bank-accounts/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d, list) and d else d.get('results', [{}])[0].get('id', ''))" 2>/dev/null)

if [ -z "$BANK_ACCOUNT_UUID" ]; then
  echo -e "${RED}Erro: Não foi possível encontrar uma bank account${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Bank account encontrada: ${BANK_ACCOUNT_UUID:0:8}...${NC}\n"

# 4. Contar transações antes
echo -e "${YELLOW}4. Contando transações antes dos testes...${NC}"
TRANSACTIONS_BEFORE=$(curl -s -X GET "${BASE_URL}/api/v1/financials/bank-accounts/${BANK_ACCOUNT_UUID}/details/?transactions_page=1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('transactions', {}).get('items', [])))" 2>/dev/null)

echo -e "Transações antes: ${TRANSACTIONS_BEFORE}\n"

# 5. Testar com recurring_bill_payment
echo -e "${YELLOW}5. Testando com recurring_bill_payment...${NC}"
RECURRING_PAYMENT_UUID=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_bill_payments&status=pendente&page=1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "import sys, json; d=json.load(sys.stdin); items = d.get('items', []); print(items[0]['id'] if items else '')" 2>/dev/null)

if [ -n "$RECURRING_PAYMENT_UUID" ]; then
  echo "Recurring payment UUID: ${RECURRING_PAYMENT_UUID:0:8}..."
  
  POST_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/data/" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Company-Id: ${COMPANY_ID}" \
    -H "Content-Type: application/json" \
    -d "{
      \"uuid\": \"${RECURRING_PAYMENT_UUID}\",
      \"type\": \"recurring_bill_payments\",
      \"bank_account\": \"${BANK_ACCOUNT_UUID}\",
      \"transaction_date\": \"$(date +%Y-%m-%d)\"
    }")
  
  TRANSACTION_UUID=$(echo "$POST_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('transaction', {}).get('id', '') if d.get('transaction') else '')" 2>/dev/null)
  
  if [ -n "$TRANSACTION_UUID" ]; then
    echo -e "${GREEN}✓ Transação criada: ${TRANSACTION_UUID:0:8}...${NC}"
    
    sleep 1
    
    # Verificar se aparece nos detalhes
    FOUND=$(curl -s -X GET "${BASE_URL}/api/v1/financials/bank-accounts/${BANK_ACCOUNT_UUID}/details/?transactions_page=1" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
transactions = d.get('transactions', {}).get('items', [])
found = [t for t in transactions if t.get('id') == '${TRANSACTION_UUID}']
print('SIM' if found else 'NAO')
" 2>/dev/null)
    
    if [ "$FOUND" = "SIM" ]; then
      echo -e "${GREEN}✓ Transação encontrada nos detalhes da bank account!${NC}\n"
    else
      echo -e "${RED}✗ Transação NÃO encontrada nos detalhes${NC}\n"
    fi
  else
    echo -e "${YELLOW}⚠ Não foi possível criar transação${NC}\n"
  fi
else
  echo -e "${YELLOW}⚠ Nenhum recurring_bill_payment pendente encontrado${NC}\n"
fi

# 6. Testar com recurring_income_receipt
echo -e "${YELLOW}6. Testando com recurring_income_receipt...${NC}"
RECURRING_RECEIPT_UUID=$(curl -s -X GET "${BASE_URL}/api/v1/financials/data/?type=recurring_income_receipts&status=pendente&page=1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "import sys, json; d=json.load(sys.stdin); items = d.get('items', []); print(items[0]['id'] if items else '')" 2>/dev/null)

if [ -n "$RECURRING_RECEIPT_UUID" ]; then
  echo "Recurring receipt UUID: ${RECURRING_RECEIPT_UUID:0:8}..."
  
  POST_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/financials/data/" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Company-Id: ${COMPANY_ID}" \
    -H "Content-Type: application/json" \
    -d "{
      \"uuid\": \"${RECURRING_RECEIPT_UUID}\",
      \"type\": \"recurring_income_receipts\",
      \"bank_account\": \"${BANK_ACCOUNT_UUID}\",
      \"transaction_date\": \"$(date +%Y-%m-%d)\"
    }")
  
  TRANSACTION_UUID=$(echo "$POST_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('transaction', {}).get('id', '') if d.get('transaction') else '')" 2>/dev/null)
  
  if [ -n "$TRANSACTION_UUID" ]; then
    echo -e "${GREEN}✓ Transação criada: ${TRANSACTION_UUID:0:8}...${NC}"
    
    sleep 1
    
    # Verificar se aparece nos detalhes
    FOUND=$(curl -s -X GET "${BASE_URL}/api/v1/financials/bank-accounts/${BANK_ACCOUNT_UUID}/details/?transactions_page=1" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
transactions = d.get('transactions', {}).get('items', [])
found = [t for t in transactions if t.get('id') == '${TRANSACTION_UUID}']
print('SIM' if found else 'NAO')
" 2>/dev/null)
    
    if [ "$FOUND" = "SIM" ]; then
      echo -e "${GREEN}✓ Transação encontrada nos detalhes da bank account!${NC}\n"
    else
      echo -e "${RED}✗ Transação NÃO encontrada nos detalhes${NC}\n"
    fi
  else
    echo -e "${YELLOW}⚠ Não foi possível criar transação${NC}\n"
  fi
else
  echo -e "${YELLOW}⚠ Nenhum recurring_income_receipt pendente encontrado${NC}\n"
fi

# 7. Resumo final
echo -e "${YELLOW}7. Resumo final...${NC}"
TRANSACTIONS_AFTER=$(curl -s -X GET "${BASE_URL}/api/v1/financials/bank-accounts/${BANK_ACCOUNT_UUID}/details/?transactions_page=1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Id: ${COMPANY_ID}" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('transactions', {}).get('items', [])))" 2>/dev/null)

echo -e "Transações depois: ${TRANSACTIONS_AFTER}"
echo -e "${BLUE}=== Teste Concluído ===${NC}"

