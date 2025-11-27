# Guia de Integração Frontend - Sistema de Convites

Este documento explica o fluxo completo de uso dos endpoints de convites, incluindo todos os parâmetros necessários e respostas esperadas.

## Visão Geral do Fluxo

```
1. ADMIN ENVIA CONVITE
   POST /api/v1/companies/invitations/
   → Cria convite pendente

2. USUÁRIO RECEBE CONVITE
   (Notificação ou busca de convites pendentes)

3. USUÁRIO ACEITA OU RECUSA
   POST /api/v1/companies/invitations/<uuid>/accept/
   POST /api/v1/companies/invitations/<uuid>/reject/
   → Cria membership (se aceitar) ou marca como recusado
```

## 1. Enviar Convite (Admin)

### Endpoint
```
POST /api/v1/companies/invitations/
```

### Headers Obrigatórios
- `Authorization: Bearer <access_token>` ou cookies de autenticação
- `X-Company-Token: <company_access_token>` ou cookie `company_access_token`
- `Content-Type: application/json`

### Permissões
- ✅ Usuário autenticado
- ✅ Usuário deve ser **admin** da empresa ativa

### Request Body
```json
{
  "email": "usuario@example.com",
  "role": "financials"
}
```

**Campos:**
- `email` (string, obrigatório): Email do usuário a convidar
- `role` (string, obrigatório): Um dos valores:
  - `"admin"` - Administrador
  - `"financials"` - Financeiro
  - `"stock_manager"` - Gerenciador de Estoque
  - `"human_resources"` - Recursos Humanos
  - `"accountability"` - Contador

### Response (201 Created)
```json
{
  "id": "118423cd-0125-486b-959e-5732d79761a3",
  "company": "dfda954d-2c6e-4bb9-9b8e-e775262842d9",
  "company_name": "Viação Borges",
  "user": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
  "user_details": {
    "id": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
    "first_name": "João",
    "last_name": "Silva",
    "email": "joao@example.com",
    "phone_number": "11999999999"
  },
  "email": "joao@example.com",
  "role": "financials",
  "status": "pending",
  "invited_by": "f63cd941-4265-4020-8cc0-d06a0ebf63b5",
  "invited_by_name": "Lucas Alves Borges",
  "created_at": "2025-11-27T00:19:06.003409-03:00",
  "updated_at": "2025-11-27T00:19:06.003418-03:00",
  "responded_at": null
}
```

**Observações:**
- Se o usuário **já existe** na plataforma, `user` e `user_details` estarão preenchidos
- Se o email **não está cadastrado**, `user` e `user_details` serão `null`
- O campo `status` sempre será `"pending"` ao criar

### Erros

**400 Bad Request - Usuário já é membro:**
```json
{
  "email": ["Este usuário já é membro desta empresa."]
}
```

**400 Bad Request - Convite pendente já existe:**
```json
{
  "email": ["Já existe um convite pendente para este email nesta empresa."]
}
```

**403 Forbidden - Sem permissão:**
```json
{
  "detail": "You do not have permission to manage invitations for this company."
}
```

## 2. Buscar Usuário Antes de Convidar (Opcional)

### Endpoint
```
GET /api/v1/companies/users/search/?email=<email>
```

### Headers Obrigatórios
- `Authorization: Bearer <access_token>` ou cookies
- `X-Company-Token: <company_access_token>` ou cookie

### Permissões
- ✅ Usuário autenticado
- ✅ Usuário deve ser **admin** da empresa ativa

### Query Parameters
- `email` (obrigatório): Email do usuário a buscar

### Response (200 OK)
```json
{
  "id": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
  "first_name": "João",
  "last_name": "Silva",
  "email": "joao@example.com",
  "phone_number": "11999999999",
  "is_member": false
}
```

**404 Not Found** se usuário não existe:
```json
{
  "detail": "Usuário não encontrado com este email."
}
```

**400 Bad Request** se email não fornecido:
```json
{
  "detail": "Parâmetro email é obrigatório."
}
```

## 3. Listar Convites da Empresa (Admin)

### Endpoint
```
GET /api/v1/companies/invitations/
```

### Headers Obrigatórios
- `Authorization: Bearer <access_token>` ou cookies
- `X-Company-Token: <company_access_token>` ou cookie

### Permissões
- ✅ Usuário autenticado
- ✅ Usuário deve ser **admin** da empresa ativa

### Response (200 OK)
```json
[
  {
    "id": "118423cd-0125-486b-959e-5732d79761a3",
    "company": "dfda954d-2c6e-4bb9-9b8e-e775262842d9",
    "company_name": "Viação Borges",
    "user": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
    "user_details": {
      "id": "c7e0ed76-5371-4ea7-82a5-fbe6ad551247",
      "first_name": "João",
      "last_name": "Silva",
      "email": "joao@example.com",
      "phone_number": "11999999999"
    },
    "email": "joao@example.com",
    "role": "financials",
    "status": "pending",
    "invited_by": "f63cd941-4265-4020-8cc0-d06a0ebf63b5",
    "invited_by_name": "Lucas Alves Borges",
    "created_at": "2025-11-27T00:19:06.003409-03:00",
    "updated_at": "2025-11-27T00:19:06.003418-03:00",
    "responded_at": null
  }
]
```

**Ordenação:** Mais recentes primeiro (`-created_at`)

## 4. Como o Usuário Descobre os Convites?

**⚠️ IMPORTANTE:** Atualmente, o sistema **não tem** um endpoint específico para o usuário listar seus próprios convites recebidos.

**Opções disponíveis:**
1. **Notificação in-app** quando convite é criado (implementar no frontend/backend)
2. **Polling** verificando periodicamente se há convites pendentes
3. **Endpoint futuro sugerido:** `GET /api/v1/users/my-invitations/`

**Validação:** O usuário só pode aceitar/recusar convites onde `invitation.email === user.email`

## 5. Aceitar Convite (Usuário Convidado)

### Endpoint
```
POST /api/v1/companies/invitations/<uuid>/accept/
```

### Headers Obrigatórios
- `Authorization: Bearer <access_token>` ou cookies
- `Content-Type: application/json`

### Permissões
- ✅ Usuário autenticado
- ✅ **Email do usuário autenticado deve corresponder ao email do convite**
- ✅ Convite deve estar com status `"pending"`

### Path Parameters
- `<uuid>`: ID do convite a aceitar

### Request Body
Vazio (não precisa enviar dados)

### Response (201 Created)
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
  "created_at": "2025-11-27T00:20:00.123456-03:00",
  "updated_at": "2025-11-27T00:20:00.123456-03:00"
}
```

**O que acontece:**
- ✅ Membership é criado automaticamente
- ✅ Convite é atualizado para `status: "accepted"`
- ✅ `responded_at` é preenchido

### Erros

**404 Not Found:**
```json
{
  "detail": "Convite não encontrado."
}
```

**400 Bad Request - Já foi respondido:**
```json
{
  "detail": "Este convite já foi aceito."
}
```

**400 Bad Request - Já é membro:**
```json
{
  "detail": "Você já é membro desta empresa."
}
```

**403 Forbidden - Sem permissão:**
```json
{
  "detail": "Você não tem permissão para responder este convite."
}
```

## 6. Recusar Convite (Usuário Convidado)

### Endpoint
```
POST /api/v1/companies/invitations/<uuid>/reject/
```

### Headers Obrigatórios
- `Authorization: Bearer <access_token>` ou cookies
- `Content-Type: application/json`

### Permissões
- ✅ Usuário autenticado
- ✅ **Email do usuário autenticado deve corresponder ao email do convite**
- ✅ Convite deve estar com status `"pending"`

### Path Parameters
- `<uuid>`: ID do convite a recusar

### Request Body
Vazio (não precisa enviar dados)

### Response (200 OK)
```json
{
  "detail": "Convite recusado com sucesso."
}
```

**O que acontece:**
- ✅ Convite é atualizado para `status: "rejected"`
- ✅ `responded_at` é preenchido
- ❌ **Nenhum membership é criado**

### Erros

**404 Not Found:**
```json
{
  "detail": "Convite não encontrado."
}
```

**400 Bad Request - Já foi respondido:**
```json
{
  "detail": "Este convite já foi recusado."
}
```

**403 Forbidden - Sem permissão:**
```json
{
  "detail": "Você não tem permissão para responder este convite."
}
```

## 7. Estados do Convite

### Status Possíveis

| Status | Descrição | Ação Permitida |
|--------|-----------|----------------|
| `pending` | Aguardando resposta | Aceitar ou Recusar |
| `accepted` | Convite aceito | Nenhuma (já processado) |
| `rejected` | Convite recusado | Nenhuma (já processado) |
| `expired` | Convite expirado | Nenhuma (futuro) |

### Validações Importantes

1. **Apenas convites `pending` podem ser aceitos/recusados**
2. **Apenas o usuário com o email do convite pode responder**
3. **Se o usuário já é membro, não pode aceitar novamente** (mas o sistema trata isso graciosamente)

## 8. Fluxo Completo

### Cenário 1: Admin convida usuário existente

1. **Admin busca usuário (opcional):**
   ```
   GET /api/v1/companies/users/search/?email=joao@example.com
   → Retorna: { id, email, is_member: false }
   ```

2. **Admin cria convite:**
   ```
   POST /api/v1/companies/invitations/
   Headers: Authorization, X-Company-Token
   Body: { "email": "joao@example.com", "role": "financials" }
   → Retorna: { id, email, status: "pending", user: {...} }
   ```

3. **Sistema notifica usuário** (implementar no frontend/backend)

4. **Usuário faz login** e descobre o convite

5. **Usuário aceita convite:**
   ```
   POST /api/v1/companies/invitations/<uuid>/accept/
   Headers: Authorization
   → Retorna: { id, company, role, ... } (membership criado)
   ```

### Cenário 2: Admin convida email não cadastrado

1. **Admin cria convite:**
   ```
   POST /api/v1/companies/invitations/
   Headers: Authorization, X-Company-Token
   Body: { "email": "novo@example.com", "role": "stock_manager" }
   → Retorna: { id, email, status: "pending", user: null }
   ```

2. **Usuário se cadastra** na plataforma com o email `novo@example.com`

3. **Usuário faz login**

4. **Usuário aceita convite:**
   ```
   POST /api/v1/companies/invitations/<uuid>/accept/
   Headers: Authorization
   → Retorna: { id, company, role, ... } (membership criado)
   → Sistema vincula automaticamente o user ao convite
   ```

### Cenário 3: Usuário recusa convite

1. **Admin cria convite**

2. **Usuário faz login**

3. **Usuário recusa convite:**
   ```
   POST /api/v1/companies/invitations/<uuid>/reject/
   Headers: Authorization
   → Retorna: { "detail": "Convite recusado com sucesso." }
   → Convite marcado como rejected, nenhum membership criado
   ```

## 9. Resumo de Endpoints

| Método | Endpoint | Descrição | Permissão | Headers Necessários |
|--------|----------|-----------|-----------|---------------------|
| POST | `/api/v1/companies/invitations/` | Criar convite | Admin | Authorization, X-Company-Token |
| GET | `/api/v1/companies/invitations/` | Listar convites da empresa | Admin | Authorization, X-Company-Token |
| GET | `/api/v1/companies/users/search/?email=...` | Buscar usuário | Admin | Authorization, X-Company-Token |
| POST | `/api/v1/companies/invitations/<uuid>/accept/` | Aceitar convite | Usuário convidado | Authorization |
| POST | `/api/v1/companies/invitations/<uuid>/reject/` | Recusar convite | Usuário convidado | Authorization |

## 10. Validações e Regras

### Ao Criar Convite

- ✅ Apenas admins da empresa ativa podem criar
- ✅ Email deve ser válido
- ✅ Role deve ser um dos valores permitidos
- ✅ Não pode haver múltiplos convites pendentes para o mesmo email/empresa
- ✅ Usuário não pode já ser membro da empresa
- ✅ Empresa deve ser resolvida via token/cookie

### Ao Aceitar/Recusar

- ✅ Apenas o usuário convidado pode aceitar/recusar (email deve corresponder)
- ✅ Convite deve estar com status `pending`
- ✅ Ao aceitar, verifica se usuário já não é membro (evita duplicação)
- ✅ Se o convite não tinha `user` definido, vincula automaticamente ao aceitar

### Segurança

- ✅ Autenticação obrigatória em todos os endpoints
- ✅ Validação de propriedade: apenas o destinatário pode aceitar/recusar
- ✅ Validação de email: sistema verifica que o email do usuário autenticado corresponde ao email do convite
- ✅ Permissões de admin: apenas admins podem criar/listar convites

## 11. Estrutura de Dados

### Invitation Object
```json
{
  "id": "uuid",
  "company": "uuid",
  "company_name": "string",
  "user": "uuid | null",
  "user_details": {
    "id": "uuid",
    "first_name": "string",
    "last_name": "string",
    "email": "string",
    "phone_number": "string"
  } | null,
  "email": "string",
  "role": "string",
  "status": "pending | accepted | rejected | expired",
  "invited_by": "uuid",
  "invited_by_name": "string",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "responded_at": "ISO 8601 datetime | null"
}
```

### Membership Object (retornado ao aceitar)
```json
{
  "id": "uuid",
  "user": "uuid",
  "user_details": {
    "id": "uuid",
    "first_name": "string",
    "last_name": "string",
    "email": "string",
    "phone_number": "string"
  },
  "company": "uuid",
  "company_name": "string",
  "role": "string",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

## 12. Observações Importantes

1. **Company Token:** Sempre necessário para endpoints de admin (criar/listar convites)
2. **Email Matching:** Usuário só pode aceitar/recusar convites onde seu email corresponde ao email do convite
3. **Status Pending:** Apenas convites pendentes podem ser aceitos/recusados
4. **Membership Automático:** Ao aceitar, o membership é criado automaticamente
5. **User Linking:** Se o convite não tinha `user` definido (email não cadastrado), o sistema vincula automaticamente ao aceitar
