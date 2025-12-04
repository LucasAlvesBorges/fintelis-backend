#!/bin/bash

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Teste de Transaction com/sem Cash Register"
echo "=========================================="
echo ""

# 1. Login
echo "1. Fazendo login..."
LOGIN_RESPONSE=$(curl -s -c "test_cookies.txt" -X POST "http://localhost:8000/api/v1/users/login/" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "lucasborgia33@gmail.com",
    "password": "Lucas@123"
  }')

ACCESS_TOKEN=$(grep 'access_token' test_cookies.txt 2>/dev/null | awk '{print $NF}' | head -1)

if [ -z "$ACCESS_TOKEN" ]; then
  echo -e "${RED}Erro: Falha no login${NC}"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✓ Login realizado com sucesso${NC}"
echo ""

# 2. Obter company token
echo "2. Obtendo company token..."
COMPANY_ID="c8ffdb92-2e9d-4bd5-aa05-c06adb85cafb"
COMPANY_TOKEN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/users/company-token/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"company_id\": \"${COMPANY_ID}\"}")

if [ -z "$COMPANY_ID" ]; then
  echo -e "${RED}Erro: Falha ao obter company ID${NC}"
  echo "Response: $COMPANY_TOKEN_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✓ Company ID: $COMPANY_ID${NC}"
echo ""

# 3. Buscar dados necessários
echo "3. Buscando dados necessários..."

# Buscar bank account
BANK_ACCOUNT_ID=$(curl -s -X GET "http://localhost:8000/api/v1/financials/bank-accounts/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Company-Id: $COMPANY_ID" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)

# Buscar cash register
CASH_REGISTER_ID=$(curl -s -X GET "http://localhost:8000/api/v1/financials/cash-registers/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Company-Id: $COMPANY_ID" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)

# Buscar category (receita)
CATEGORY_ID=$(curl -s -X GET "http://localhost:8000/api/v1/financials/categories/?type=receita" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Company-Id: $COMPANY_ID" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)

# Buscar cost center
COST_CENTER_ID=$(curl -s -X GET "http://localhost:8000/api/v1/companies/cost-centers/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Company-Id: $COMPANY_ID" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)

echo "Bank Account ID: $BANK_ACCOUNT_ID"
echo "Cash Register ID: $CASH_REGISTER_ID"
echo "Category ID: $CATEGORY_ID"
echo "Cost Center ID: $COST_CENTER_ID"
echo ""

# 4. Teste 1: Criar Transaction RECEITA com bank_account (sem cash_register)
echo "=========================================="
echo "TESTE 1: Transaction RECEITA com bank_account (sem cash_register)"
echo "=========================================="

TRANSACTION_1_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/v1/financials/transactions/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Company-Id: $COMPANY_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"Venda única - Teste sem PDV\",
    \"amount\": \"100.00\",
    \"type\": \"receita\",
    \"transaction_date\": \"2025-01-15\",
    \"bank_account\": \"$BANK_ACCOUNT_ID\",
    \"category\": \"$CATEGORY_ID\",
    \"cost_center\": \"$COST_CENTER_ID\"
  }")

HTTP_CODE_1=$(echo "$TRANSACTION_1_RESPONSE" | tail -n1)
BODY_1=$(echo "$TRANSACTION_1_RESPONSE" | sed '$d')

if [ "$HTTP_CODE_1" = "201" ]; then
  echo -e "${GREEN}✓ Transaction criada com sucesso${NC}"
  echo "$BODY_1" | python3 -m json.tool 2>/dev/null || echo "$BODY_1"
else
  echo -e "${RED}✗ Erro ao criar transaction (HTTP $HTTP_CODE_1)${NC}"
  echo "$BODY_1" | python3 -m json.tool 2>/dev/null || echo "$BODY_1"
fi
echo ""

# 5. Teste 2: Criar Transaction RECEITA com cash_register (sem bank_account)
if [ -n "$CASH_REGISTER_ID" ]; then
  echo "=========================================="
  echo "TESTE 2: Transaction RECEITA com cash_register (sem bank_account)"
  echo "=========================================="

  TRANSACTION_2_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/v1/financials/transactions/" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "X-Company-Id: $COMPANY_ID" \
    -H "Content-Type: application/json" \
    -d "{
      \"description\": \"Venda única - Teste com PDV\",
      \"amount\": \"150.00\",
      \"type\": \"receita\",
      \"transaction_date\": \"2025-01-15\",
      \"cash_register\": \"$CASH_REGISTER_ID\",
      \"category\": \"$CATEGORY_ID\",
      \"cost_center\": \"$COST_CENTER_ID\"
    }")

  HTTP_CODE_2=$(echo "$TRANSACTION_2_RESPONSE" | tail -n1)
  BODY_2=$(echo "$TRANSACTION_2_RESPONSE" | sed '$d')

  if [ "$HTTP_CODE_2" = "201" ]; then
    echo -e "${GREEN}✓ Transaction criada com sucesso (bank_account preenchido automaticamente)${NC}"
    echo "$BODY_2" | python3 -m json.tool 2>/dev/null || echo "$BODY_2"
    
    # Verificar se bank_account foi preenchido
    AUTO_BANK_ACCOUNT=$(echo "$BODY_2" | python3 -c "import sys, json; print(json.load(sys.stdin).get('bank_account', ''))" 2>/dev/null)
    if [ -n "$AUTO_BANK_ACCOUNT" ]; then
      echo -e "${GREEN}✓ bank_account foi preenchido automaticamente: $AUTO_BANK_ACCOUNT${NC}"
    else
      echo -e "${RED}✗ bank_account não foi preenchido automaticamente${NC}"
    fi
  else
    echo -e "${RED}✗ Erro ao criar transaction (HTTP $HTTP_CODE_2)${NC}"
    echo "$BODY_2" | python3 -m json.tool 2>/dev/null || echo "$BODY_2"
  fi
  echo ""
else
  echo -e "${YELLOW}⚠ Cash Register não encontrado, pulando teste 2${NC}"
  echo ""
fi

# 6. Teste 3: Criar Transaction RECEITA com cash_register (sem contact)
if [ -n "$CASH_REGISTER_ID" ]; then
  echo "=========================================="
  echo "TESTE 3: Transaction RECEITA com cash_register (sem contact)"
  echo "=========================================="

  TRANSACTION_3_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/v1/financials/transactions/" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "X-Company-Id: $COMPANY_ID" \
    -H "Content-Type: application/json" \
    -d "{
      \"description\": \"Venda única - Teste sem contact\",
      \"amount\": \"200.00\",
      \"type\": \"receita\",
      \"transaction_date\": \"2025-01-15\",
      \"cash_register\": \"$CASH_REGISTER_ID\",
      \"category\": \"$CATEGORY_ID\",
      \"cost_center\": \"$COST_CENTER_ID\"
    }")

  HTTP_CODE_3=$(echo "$TRANSACTION_3_RESPONSE" | tail -n1)
  BODY_3=$(echo "$TRANSACTION_3_RESPONSE" | sed '$d')

  if [ "$HTTP_CODE_3" = "201" ]; then
    echo -e "${GREEN}✓ Transaction criada com sucesso (sem contact)${NC}"
    echo "$BODY_3" | python3 -m json.tool 2>/dev/null || echo "$BODY_3"
    
    # Verificar se contact é null
    CONTACT_VALUE=$(echo "$BODY_3" | python3 -c "import sys, json; d=json.load(sys.stdin); print('null' if d.get('contact') is None else d.get('contact'))" 2>/dev/null)
    if [ "$CONTACT_VALUE" = "null" ] || [ -z "$CONTACT_VALUE" ]; then
      echo -e "${GREEN}✓ contact está null (correto para venda no caixa)${NC}"
    else
      echo -e "${YELLOW}⚠ contact não está null: $CONTACT_VALUE${NC}"
    fi
  else
    echo -e "${RED}✗ Erro ao criar transaction (HTTP $HTTP_CODE_3)${NC}"
    echo "$BODY_3" | python3 -m json.tool 2>/dev/null || echo "$BODY_3"
  fi
  echo ""
else
  echo -e "${YELLOW}⚠ Cash Register não encontrado, pulando teste 3${NC}"
  echo ""
fi

# 7. Teste 4: Erro - sem bank_account e sem cash_register
echo "=========================================="
echo "TESTE 4: Erro esperado - sem bank_account e sem cash_register"
echo "=========================================="

TRANSACTION_4_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/v1/financials/transactions/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Company-Id: $COMPANY_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"Venda única - Teste erro\",
    \"amount\": \"50.00\",
    \"type\": \"receita\",
    \"transaction_date\": \"2025-01-15\",
    \"category\": \"$CATEGORY_ID\",
    \"cost_center\": \"$COST_CENTER_ID\"
  }")

HTTP_CODE_4=$(echo "$TRANSACTION_4_RESPONSE" | tail -n1)
BODY_4=$(echo "$TRANSACTION_4_RESPONSE" | sed '$d')

if [ "$HTTP_CODE_4" = "400" ]; then
  echo -e "${GREEN}✓ Erro esperado retornado corretamente (HTTP 400)${NC}"
  echo "$BODY_4" | python3 -m json.tool 2>/dev/null || echo "$BODY_4"
else
  echo -e "${RED}✗ Erro inesperado (HTTP $HTTP_CODE_4)${NC}"
  echo "$BODY_4" | python3 -m json.tool 2>/dev/null || echo "$BODY_4"
fi
echo ""

# 8. Teste 5: Financial Data API - Verificar se ainda funciona
echo "=========================================="
echo "TESTE 5: Financial Data API - Verificar se ainda funciona"
echo "=========================================="

# Buscar um income pendente
INCOME_ID=$(curl -s -X GET "http://localhost:8000/api/v1/financials/data/?type=incomes" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Company-Id: $COMPANY_ID" | python3 -c "import sys, json; d=json.load(sys.stdin); items=d.get('incomes', {}).get('items', []); print(items[0]['id'] if items and items[0].get('status') != 'recebido' else '')" 2>/dev/null)

if [ -n "$INCOME_ID" ]; then
  echo "Income ID encontrado: $INCOME_ID"
  echo ""
  
  # Tentar criar transação via Financial Data API
  FINANCIAL_DATA_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/v1/financials/data/" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "X-Company-Id: $COMPANY_ID" \
    -H "Content-Type: application/json" \
    -d "{
      \"uuid\": \"$INCOME_ID\",
      \"type\": \"incomes\",
      \"bank_account\": \"$BANK_ACCOUNT_ID\",
      \"transaction_date\": \"2025-01-15\",
      \"description\": \"Teste Financial Data API\"
    }")

  HTTP_CODE_FD=$(echo "$FINANCIAL_DATA_RESPONSE" | tail -n1)
  BODY_FD=$(echo "$FINANCIAL_DATA_RESPONSE" | sed '$d')

  if [ "$HTTP_CODE_FD" = "200" ] || [ "$HTTP_CODE_FD" = "201" ]; then
    echo -e "${GREEN}✓ Financial Data API funcionando corretamente${NC}"
    echo "$BODY_FD" | python3 -m json.tool 2>/dev/null | head -30 || echo "$BODY_FD" | head -30
  else
    echo -e "${RED}✗ Erro na Financial Data API (HTTP $HTTP_CODE_FD)${NC}"
    echo "$BODY_FD" | python3 -m json.tool 2>/dev/null || echo "$BODY_FD"
  fi
else
  echo -e "${YELLOW}⚠ Nenhum income pendente encontrado para teste${NC}"
fi
echo ""

echo "=========================================="
echo "Testes concluídos!"
echo "=========================================="

