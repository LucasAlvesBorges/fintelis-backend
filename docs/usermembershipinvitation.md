## Fluxo de convites de usuários e redefinição de senha

Este guia descreve como um administrador de uma empresa cria novos usuários, os convida para a empresa e força a troca de senha no primeiro acesso.

### Visão geral
- **Quem pode convidar**: apenas membros `admin` da empresa.
- **Escopo da empresa**: todas as chamadas usam o token/cookie de empresa (`X-Company-Token` ou `company_access_token`) para garantir que o convite seja emitido para a empresa ativa.
- **Senha temporária**: o admin define uma senha inicial (mínimo 4 caracteres para convites). O backend marca `must_change_password=true`.
- **Primeiro login**: o convidado deve trocar a senha imediatamente; após a troca, `must_change_password` passa a `false`.

### Endpoints envolvidos
- Criar convite (cria usuário e membership na empresa ativa):  
  `POST /api/v1/companies/memberships/invite/`
- Listar todos os usuários/memberships da empresa ativa (admin):  
  `GET /api/v1/companies/memberships/current/`
- Detalhar/atualizar/excluir membership da empresa ativa (admin):  
  `GET|PUT|PATCH|DELETE /api/v1/companies/memberships/current/<uuid:pk>/`
- Login:  
  `POST /api/v1/users/login/`
- Troca de senha (após o primeiro login):  
  `POST /api/v1/users/change-password/`
- Sessão atual (para ler `must_change_password`):  
  `GET /api/v1/users/me/`

### 1) Admin convida um usuário

Requisitos: estar autenticado e ser `admin` da empresa ativa (enviar `X-Company-Token` ou cookie de empresa).

**Dois cenários possíveis:**
- **Criar novo usuário**: use o campo `new_user` com os dados do usuário
- **Convidar usuário existente**: use o campo `user` com o UUID do usuário já cadastrado na plataforma

#### Fluxo completo

**1.1) Login e obtenção de tokens**

Primeiro, faça login para obter os tokens de autenticação:
```bash
curl -i -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"senha123"}' \
  http://localhost:8000/api/v1/users/login/
```

**1.2) Obter token de empresa**

Em seguida, obtenha o token da empresa ativa:
```bash
curl -i -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"company_id":"uuid-da-empresa"}' \
  http://localhost:8000/api/v1/users/company-token/
```

O token será salvo no cookie `company_access_token` e também retornado no JSON da resposta.

**1.3) Criar convite**

Você pode criar um novo usuário ou convidar um usuário que já existe na plataforma. Veja as opções abaixo:

#### Opção A: Criar novo usuário
```bash
curl -i -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  -d '{
    "role": "financials",
    "new_user": {
      "first_name": "João",
      "last_name": "Silva",
      "email": "joao@example.com",
      "phone_number": "11999999999",
      "password": "1234"
    }
  }' \
  http://localhost:8000/api/v1/companies/memberships/invite/
```

**JSON Request:**
```json
POST /api/v1/companies/memberships/invite/
{
  "role": "financials",
  "new_user": {
    "first_name": "João",
    "last_name": "Silva",
    "email": "joao@example.com",
    "phone_number": "11999999999",
    "password": "1234"
  }
}
```

**JSON Request - Convidar usuário existente:**
```json
POST /api/v1/companies/memberships/invite/
{
  "role": "stock_manager",
  "user": "uuid-do-usuario-existente"
}
```

**Curl - Convidar usuário existente:**
```bash
curl -i -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  -d '{
    "role": "stock_manager",
    "user": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247"
  }' \
  http://localhost:8000/api/v1/companies/memberships/invite/
```

#### Response - Sucesso (201 Created)
```json
{
  "id": "4558df86-83da-4abb-874c-836d7eccceb2",
  "user": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
  "user_details": {
    "id": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
    "first_name": "João",
    "last_name": "Silva",
    "email": "joao@example.com",
    "phone_number": "11999999999"
  },
  "company": "dfda954d-2c6e-4bb9-9b8e-e775262842d9",
  "company_name": "Viação Borges",
  "role": "financials",
  "created_at": "2025-11-27T00:00:15.272131-03:00",
  "updated_at": "2025-11-27T00:00:15.272137-03:00"
}
```

#### Opção B: Convidar usuário existente

Para convidar um usuário que já está cadastrado na plataforma, você precisa do **UUID** do usuário. Veja como obter:

**Como encontrar o UUID de um usuário:**

1. **Buscar por email** (se você tiver acesso a listagem de usuários):
   - Use o endpoint de busca/listagem de usuários (se disponível)
   - Ou consulte diretamente no banco de dados

2. **O usuário já é membro de outra empresa:**
   - Liste os memberships do usuário para obter seu UUID
   - O UUID do usuário está no campo `user` de qualquer membership

3. **Via resposta de outros endpoints:**
   - O UUID do usuário geralmente aparece em respostas de endpoints que retornam dados de usuário

**Exemplo completo - Convidar usuário existente:**

```bash
# 1. Obter o UUID do usuário (exemplo: de uma resposta anterior ou busca)
USER_UUID="c7e0ed76-5371-4ea7-82a5-fbe6ad551247"

# 2. Enviar convite usando o UUID
curl -i -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  -d "{
    \"role\": \"stock_manager\",
    \"user\": \"${USER_UUID}\"
  }" \
  http://localhost:8000/api/v1/companies/memberships/invite/
```

**Diferenças importantes entre criar novo usuário e convidar existente:**

| Aspecto | Criar novo (`new_user`) | Convidar existente (`user`) |
|---------|------------------------|----------------------------|
| Campo usado | `new_user` (objeto) | `user` (UUID string) |
| Senha temporária | Sim, definida pelo admin | Não aplicável (usuário já tem senha) |
| `must_change_password` | `true` (forçado) | Não alterado (mantém valor atual) |
| Email | Deve ser único (novo) | Usuário já existe com esse email |
| Quando usar | Usuário ainda não tem conta | Usuário já está na plataforma |

**Notas importantes:**
- A empresa é resolvida automaticamente pelo token/cookie de empresa; **não é necessário** enviar `company` no payload.
- Para vincular um usuário existente, envie `{"role": "...", "user": "<user_uuid>"}` no lugar de `new_user`.
- O usuário criado via `new_user` terá `must_change_password=true` automaticamente.
- Usuários existentes convidados **não** terão `must_change_password` alterado (mantém o valor atual).
- O campo `user_details` contém informações resumidas do usuário associado ao membership.
- ⚠️ **Importante**: Um usuário não pode ter múltiplos memberships na mesma empresa. Se tentar convidar um usuário que já é membro, retornará erro de validação.

#### Parâmetros aceitos

**Headers/cookies obrigatórios:**
- **Autenticação**: 
  - Cookies: `access_token` e `refresh_token` (obtidos no login)
  - Ou header: `Authorization: Bearer <access_token>`
- **Empresa ativa**: 
  - Header: `X-Company-Token: <company_access_token>`
  - Ou cookie: `company_access_token` (obtido via `/api/v1/users/company-token/`)
  
  ⚠️ **Importante**: Se não enviar o token de empresa, o backend retorna erro: `company: Empresa ativa não encontrada. Envie o X-Company-Token ou cookie company_access_token.`

**Body (JSON):**
- `role` (string, **obrigatório**): um dos valores:
  - `admin` - Administrador
  - `financials` - Financeiro
  - `stock_manager` - Gerenciador de Estoque
  - `human_resources` - Recursos Humanos
  - `accountability` - Contador

- **Criação de novo usuário** (use **um** destes blocos):
  - `new_user` (objeto, opcional): cria o usuário antes de criar o membership
    - `first_name` (string, obrigatório)
    - `last_name` (string, obrigatório)
    - `email` (string, obrigatório, deve ser único)
    - `phone_number` (string, opcional)
    - `password` (string, obrigatório; mínimo 4 caracteres para convite)
  - ou `user` (UUID, opcional): ID de um usuário já existente no sistema

#### Erros comuns

**400 Bad Request - Validação falhou:**
```json
{
  "detail": "Erro de validação ao convidar usuário.",
  "errors": {
    "user": ["Este campo é obrigatório."],
    "company": ["Este campo é obrigatório."]
  },
  "messages": [
    "user: Este campo é obrigatório.",
    "company: Este campo é obrigatório."
  ]
}
```
**Causa**: Token de empresa não foi enviado ou é inválido.

**400 Bad Request - Usuário/email já existe:**
```json
{
  "detail": "Erro de validação ao convidar usuário.",
  "errors": {
    "new_user": {
      "email": ["user with this email already exists."]
    }
  },
  "messages": ["new_user.email: user with this email already exists."]
}
```

**400 Bad Request - Senha muito curta:**
```json
{
  "detail": "Erro de validação ao convidar usuário.",
  "errors": {
    "new_user": {
      "password": ["Ensure this field has at least 4 characters."]
    }
  }
}
```

**400 Bad Request - Role inválido:**
```json
{
  "detail": "Erro de validação ao convidar usuário.",
  "errors": {
    "role": ["\"invalid_role\" is not a valid choice."]
  }
}
```

**400 Bad Request - Nem user nem new_user enviados:**
```json
{
  "detail": "Erro de validação ao convidar usuário.",
  "errors": {
    "user": ["Envie o campo user (UUID de usuário existente) ou o bloco new_user com dados do usuário a criar."]
  }
}
```

**403 Forbidden - Sem permissão:**
```json
{
  "detail": "You do not have permission to manage memberships for this company."
}
```
**Causa**: O usuário autenticado não é admin da empresa ativa.

**400 Bad Request - Usuário não encontrado:**
```json
{
  "detail": "Erro de validação ao convidar usuário.",
  "errors": {
    "user": ["Invalid pk \"uuid-invalido\" - object does not exist."]
  }
}
```
**Causa**: O UUID do usuário fornecido não existe no sistema.

### 2) Login do usuário convidado

O usuário convidado faz login usando as credenciais temporárias fornecidas pelo admin.

#### Request
```bash
curl -i -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "email": "joao@example.com",
    "password": "1234"
  }' \
  http://localhost:8000/api/v1/users/login/
```

```json
POST /api/v1/users/login/
{
  "email": "joao@example.com",
  "password": "1234"
}
```

#### Response
```json
{
  "user": {
    "first_name": "João",
    "last_name": "Silva",
    "must_change_password": true
  }
}
```

**Importante**: 
- A resposta inclui `user.must_change_password=true`.
- O frontend **deve** forçar a troca de senha antes de permitir qualquer outra ação.
- Os tokens de autenticação são salvos nos cookies `access_token` e `refresh_token`.

### 3) Trocar a senha no primeiro acesso

Após o login, o usuário deve trocar a senha temporária por uma senha segura.

#### Request
```bash
curl -i -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "1234",
    "new_password": "SenhaForte123!"
  }' \
  http://localhost:8000/api/v1/users/change-password/
```

```json
POST /api/v1/users/change-password/
{
  "current_password": "1234",
  "new_password": "SenhaForte123!"
}
```

#### Response - Sucesso (200 OK)
```json
{
  "user": {
    "first_name": "João",
    "last_name": "Silva",
    "must_change_password": false
  }
}
```

**Validações aplicadas:**
- Valida que a senha atual está correta
- Aplica validações de senha padrão (mínimo 8 caracteres + regras do `AUTH_PASSWORD_VALIDATORS`)
- Verifica que a nova senha é diferente da atual
- Zera o flag `must_change_password` e retorna o `user` atualizado

**Erro comum - Senha atual incorreta:**
```json
{
  "current_password": ["Senha atual incorreta."]
}
```

**Erro comum - Nova senha igual à atual:**
```json
{
  "new_password": ["Nova senha deve ser diferente da atual."]
}
```

### 4) Como encontrar usuários existentes para convidar

Se você precisa convidar um usuário que já existe na plataforma, primeiro precisa obter o UUID desse usuário. Aqui estão algumas formas:

#### 4.1) Listar membros de outras empresas

Se o usuário já é membro de outra empresa (e você tem acesso), você pode obter o UUID dele:

```bash
# Listar memberships de outra empresa (se você for admin dela)
curl -b cookies.txt \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  http://localhost:8000/api/v1/companies/memberships/current/
```

A resposta incluirá o campo `user` com o UUID de cada membro:
```json
[
  {
    "id": "...",
    "user": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",  // <- UUID do usuário
    "user_details": {
      "id": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
      "first_name": "João",
      "last_name": "Silva",
      "email": "joao@example.com"
    },
    "role": "financials",
    ...
  }
]
```

#### 4.2) Via resposta de outros endpoints

Muitos endpoints que retornam dados de usuário incluem o UUID no campo `id` ou `user`. Por exemplo:
- Endpoints de autenticação
- Endpoints de perfil
- Endpoints que retornam dados de membros

#### 4.3) Buscar por email (se disponível)

Se houver um endpoint de busca de usuários por email, você pode usá-lo para encontrar o UUID. Caso contrário, você precisará consultar diretamente o banco de dados ou ter acesso administrativo.

#### 4.4) Exemplo prático completo

```bash
# 1. Login como admin
curl -i -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"senha123"}' \
  http://localhost:8000/api/v1/users/login/

# 2. Obter company token
curl -i -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"company_id":"uuid-da-empresa"}' \
  http://localhost:8000/api/v1/users/company-token/

# 3. Extrair tokens
ACCESS_TOKEN=$(grep -E 'access_token' cookies.txt | tail -1 | awk '{print $7}')
COMPANY_TOKEN=$(grep -E 'company_access_token' cookies.txt | tail -1 | awk '{print $7}')

# 4. Listar membros de outra empresa para obter UUIDs (se você for admin)
# Ou usar um UUID conhecido
USER_UUID="c7e0ed76-5371-4ea7-82a5-fbe6ad551247"

# 5. Convidar o usuário existente
curl -i -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Company-Token: ${COMPANY_TOKEN}" \
  -d "{
    \"role\": \"stock_manager\",
    \"user\": \"${USER_UUID}\"
  }" \
  http://localhost:8000/api/v1/companies/memberships/invite/
```

**Resposta de sucesso:**
```json
{
  "id": "novo-membership-uuid",
  "user": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
  "user_details": {
    "id": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
    "first_name": "João",
    "last_name": "Silva",
    "email": "joao@example.com",
    "phone_number": "11999999999"
  },
  "company": "dfda954d-2c6e-4bb9-9b8e-e775262842d9",
  "company_name": "Viação Borges",
  "role": "stock_manager",
  "created_at": "2025-11-27T00:00:15.272131-03:00",
  "updated_at": "2025-11-27T00:00:15.272137-03:00"
}
```

### 5) Sessão e enforcement no frontend

#### Verificar status do usuário
Use `GET /api/v1/users/me/` para obter informações da sessão atual, incluindo `must_change_password`:

```bash
curl -b cookies.txt http://localhost:8000/api/v1/users/me/
```

```json
GET /api/v1/users/me/
```

**Response:**
```json
{
  "id": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
  "email": "joao@example.com",
  "first_name": "João",
  "last_name": "Silva",
  "must_change_password": true,
  ...
}
```

**Lógica do frontend:**
- Se `must_change_password === true`, redirecione imediatamente para a tela de troca de senha
- Bloqueie acesso a outras funcionalidades até que a senha seja alterada
- Após a troca de senha, `must_change_password` será `false` e o usuário pode acessar o sistema normalmente

#### Gerenciar membros da empresa (apenas admin)

**Listar todos os membros:**
```bash
curl -b cookies.txt \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  http://localhost:8000/api/v1/companies/memberships/current/
```

```json
GET /api/v1/companies/memberships/current/
```

**Detalhar/atualizar/excluir membro:**
```bash
# GET - Obter detalhes
curl -b cookies.txt \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  http://localhost:8000/api/v1/companies/memberships/current/<uuid:pk>/

# PUT/PATCH - Atualizar role
curl -X PATCH -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  -d '{"role": "admin"}' \
  http://localhost:8000/api/v1/companies/memberships/current/<uuid:pk>/

# DELETE - Remover membro
curl -X DELETE -b cookies.txt \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  http://localhost:8000/api/v1/companies/memberships/current/<uuid:pk>/
```

**Importante para chamadas multi-empresa:**
- Sempre garanta que um token/cookie de empresa válido esteja presente
- Caso contrário, convites serão rejeitados ou atribuídos à empresa errada
- Use `X-Company-Token` no header ou o cookie `company_access_token`

### Regras e mensagens importantes

#### Permissões
- ✅ Convite só é aceito se o caller for **admin** da empresa ativa; caso contrário, retorna `403 Forbidden`.
- ✅ Apenas admins podem listar, atualizar ou remover membros da empresa.

#### Resolução da empresa
- ✅ A empresa é resolvida automaticamente via:
  1. Token no header `X-Company-Token`
  2. Cookie `company_access_token`
  3. Middleware que injeta `active_company` no request (quando disponível)
- ❌ Se `company` não puder ser resolvida (sem token de empresa), a API retorna erro de validação: `company: Empresa ativa não encontrada. Envie o X-Company-Token ou cookie company_access_token.`

#### Validações de senha
- **Senha do convite**: mínimo **4 caracteres** (permitido apenas para convites)
- **Senha após login**: deve cumprir as validações padrão:
  - Mínimo **8 caracteres**
  - Regras do `AUTH_PASSWORD_VALIDATORS` do Django
  - Não pode ser igual à senha atual

#### Validações de email
- O email deve ser único no sistema
- Se tentar criar um usuário com email já existente, use `user: <uuid>` em vez de `new_user`
- **Dica**: Se você receber erro de email duplicado ao tentar criar um novo usuário, significa que o usuário já existe. Nesse caso, busque o UUID do usuário e use `user: <uuid>` para convidá-lo.

#### Validações de membership
- Um usuário não pode ter múltiplos memberships na mesma empresa (constraint `unique_together` no modelo)
- Se tentar convidar um usuário que já é membro da empresa, retornará erro de validação:
  ```json
  {
    "detail": "Erro de validação ao convidar usuário.",
    "errors": {
      "non_field_errors": ["The fields user, company must make a unique set."]
    }
  }
  ```
- Para atualizar o role de um membro existente, use `PATCH /api/v1/companies/memberships/current/<uuid:pk>/` em vez de criar um novo convite

#### Fluxo completo resumido
1. ✅ Admin faz login → obtém `access_token`
2. ✅ Admin obtém `company_access_token` → identifica empresa ativa
3. ✅ Admin cria convite → novo usuário é criado com `must_change_password=true`
4. ✅ Usuário convidado faz login → recebe `must_change_password=true` na resposta
5. ✅ Frontend força troca de senha → usuário não pode acessar outras funcionalidades
6. ✅ Usuário troca senha → `must_change_password` vira `false`
7. ✅ Usuário pode acessar o sistema normalmente
