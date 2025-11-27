# Sistema de Convites de Parceiros

Este documento descreve o sistema completo de convites para adicionar usuários como membros de empresas. O sistema permite que administradores convidem usuários existentes ou novos para se juntarem à empresa, com a possibilidade de aceitar ou recusar o convite.

## Visão Geral

O sistema de convites permite:
- **Buscar usuários** por email para verificar se já existem na plataforma
- **Criar convites pendentes** para usuários existentes ou novos
- **Listar convites** da empresa ativa
- **Aceitar convites** (cria automaticamente o membership)
- **Recusar convites** (marca como rejeitado)

### Características Principais

- ✅ Convites pendentes que podem ser aceitos ou recusados
- ✅ Suporte para usuários existentes e emails não cadastrados
- ✅ Validação: apenas um convite pendente por email/empresa
- ✅ Segurança: apenas o usuário convidado pode aceitar/recusar
- ✅ Integração automática: ao aceitar, cria o membership automaticamente
- ✅ Rastreamento: registra quem convidou e quando foi respondido

## Modelo de Dados

### Invitation

O modelo `Invitation` armazena os convites com os seguintes campos:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID | Identificador único do convite |
| `company` | ForeignKey | Empresa que está convidando |
| `user` | ForeignKey (nullable) | Usuário existente (se encontrado pelo email) |
| `email` | EmailField | Email do usuário convidado |
| `role` | CharField | Papel do usuário na empresa |
| `status` | CharField | Status do convite (pending, accepted, rejected, expired) |
| `invited_by` | ForeignKey | Admin que enviou o convite |
| `responded_at` | DateTime (nullable) | Data/hora em que o convite foi respondido |
| `created_at` | DateTime | Data de criação |
| `updated_at` | DateTime | Data de última atualização |

### Status do Convite

- **pending**: Convite pendente, aguardando resposta
- **accepted**: Convite aceito, membership criado
- **rejected**: Convite recusado pelo usuário
- **expired**: Convite expirado (futuro)

### Roles Disponíveis

- `admin` - Administrador
- `financials` - Financeiro
- `stock_manager` - Gerenciador de Estoque
- `human_resources` - Recursos Humanos
- `accountability` - Contador

## Endpoints

### 1. Buscar Usuário por Email

Busca um usuário na plataforma pelo email para verificar se já existe e se já é membro da empresa.

**Endpoint:** `GET /api/v1/companies/users/search/?email=<email>`

**Permissões:** Apenas admins da empresa ativa

**Headers obrigatórios:**
- `Authorization: Bearer <access_token>` ou cookies de autenticação
- `X-Company-Token: <company_access_token>` ou cookie `company_access_token`

**Parâmetros:**
- `email` (query string, obrigatório): Email do usuário a buscar

**Resposta de sucesso (200 OK):**
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

**Resposta quando usuário não encontrado (404 Not Found):**
```json
{
  "detail": "Usuário não encontrado com este email."
}
```

**Resposta quando email não fornecido (400 Bad Request):**
```json
{
  "detail": "Parâmetro email é obrigatório."
}
```

**Exemplo de uso:**
```bash
curl -b cookies.txt \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  "http://localhost:8000/api/v1/companies/users/search/?email=joao@example.com"
```

### 2. Criar Convite

Cria um novo convite pendente para um usuário. Funciona tanto para usuários existentes quanto para emails não cadastrados.

**Endpoint:** `POST /api/v1/companies/invitations/`

**Permissões:** Apenas admins da empresa ativa

**Headers obrigatórios:**
- `Authorization: Bearer <access_token>` ou cookies de autenticação
- `X-Company-Token: <company_access_token>` ou cookie `company_access_token`
- `Content-Type: application/json`

**Body (JSON):**
```json
{
  "email": "joao@example.com",
  "role": "financials"
}
```

**Campos:**
- `email` (string, obrigatório): Email do usuário a convidar
- `role` (string, obrigatório): Um dos roles disponíveis

**Resposta de sucesso (201 Created):**
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

**Nota:** Se o usuário não existir, `user` e `user_details` serão `null`. O sistema tentará encontrar o usuário pelo email automaticamente.

**Erros comuns:**

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

**400 Bad Request - Empresa não encontrada:**
```json
{
  "company": ["Empresa ativa não encontrada. Envie o X-Company-Token ou cookie company_access_token."]
}
```

**403 Forbidden - Sem permissão:**
```json
{
  "detail": "You do not have permission to manage invitations for this company."
}
```

**Exemplo de uso:**
```bash
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  -d '{
    "email": "joao@example.com",
    "role": "financials"
  }' \
  http://localhost:8000/api/v1/companies/invitations/
```

### 3. Listar Convites

Lista todos os convites da empresa ativa, ordenados por data de criação (mais recentes primeiro).

**Endpoint:** `GET /api/v1/companies/invitations/`

**Permissões:** Apenas admins da empresa ativa

**Headers obrigatórios:**
- `Authorization: Bearer <access_token>` ou cookies de autenticação
- `X-Company-Token: <company_access_token>` ou cookie `company_access_token`

**Resposta de sucesso (200 OK):**
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
  },
  {
    "id": "97a47aa0-5329-4d32-a661-7a3f36201e8a",
    "company": "dfda954d-2c6e-4bb9-9b8e-e775262842d9",
    "company_name": "Viação Borges",
    "user": null,
    "user_details": null,
    "email": "novo@example.com",
    "role": "stock_manager",
    "status": "accepted",
    "invited_by": "f63cd941-4265-4020-8cc0-d06a0ebf63b5",
    "invited_by_name": "Lucas Alves Borges",
    "created_at": "2025-11-27T00:19:00.216956-03:00",
    "updated_at": "2025-11-27T00:19:05.123456-03:00",
    "responded_at": "2025-11-27T00:19:05.123456-03:00"
  }
]
```

**Exemplo de uso:**
```bash
curl -b cookies.txt \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  http://localhost:8000/api/v1/companies/invitations/
```

### 4. Aceitar Convite

Aceita um convite pendente e cria automaticamente o membership na empresa. Apenas o usuário convidado pode aceitar seu próprio convite.

**Endpoint:** `POST /api/v1/companies/invitations/<uuid>/accept/`

**Permissões:** Apenas o usuário autenticado que recebeu o convite (email deve corresponder)

**Headers obrigatórios:**
- `Authorization: Bearer <access_token>` ou cookies de autenticação
- `Content-Type: application/json`

**Parâmetros:**
- `<uuid>` (path): ID do convite a aceitar

**Resposta de sucesso (201 Created):**
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

**Erros comuns:**

**404 Not Found - Convite não encontrado:**
```json
{
  "detail": "Convite não encontrado."
}
```

**400 Bad Request - Convite já foi respondido:**
```json
{
  "detail": "Este convite já foi aceito."
}
```

**400 Bad Request - Usuário já é membro:**
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

**Exemplo de uso:**
```bash
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/companies/invitations/118423cd-0125-486b-959e-5732d79761a3/accept/
```

### 5. Recusar Convite

Recusa um convite pendente. Apenas o usuário convidado pode recusar seu próprio convite.

**Endpoint:** `POST /api/v1/companies/invitations/<uuid>/reject/`

**Permissões:** Apenas o usuário autenticado que recebeu o convite (email deve corresponder)

**Headers obrigatórios:**
- `Authorization: Bearer <access_token>` ou cookies de autenticação
- `Content-Type: application/json`

**Parâmetros:**
- `<uuid>` (path): ID do convite a recusar

**Resposta de sucesso (200 OK):**
```json
{
  "detail": "Convite recusado com sucesso."
}
```

**Erros comuns:**

**404 Not Found - Convite não encontrado:**
```json
{
  "detail": "Convite não encontrado."
}
```

**400 Bad Request - Convite já foi respondido:**
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

**Exemplo de uso:**
```bash
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/companies/invitations/118423cd-0125-486b-959e-5732d79761a3/reject/
```

## Fluxo Completo

### Cenário 1: Convidar Usuário Existente

Este é o cenário mais comum: um usuário que já tem conta na plataforma recebe um convite para se juntar a uma empresa.

1. **Admin busca usuário por email (opcional, mas recomendado):**
   ```bash
   GET /api/v1/companies/users/search/?email=joao@example.com
   ```
   - Retorna dados do usuário e `is_member: false` (se não for membro)
   - Permite verificar se o usuário existe antes de convidar

2. **Admin cria convite:**
   ```bash
   POST /api/v1/companies/invitations/
   {
     "email": "joao@example.com",
     "role": "financials"
   }
   ```
   - Sistema **encontra automaticamente** o usuário pelo email
   - Convite é criado com `status: pending` e `user` **já preenchido**
   - O campo `user` no convite contém o UUID do usuário existente
   - O campo `user_details` mostra os dados completos do usuário

3. **Usuário recebe notificação** (implementação futura)
   - Email ou notificação in-app informando sobre o convite

4. **Usuário faz login** na plataforma
   - Usa suas credenciais normais (não precisa de senha temporária)
   - Login funciona normalmente, sem necessidade de trocar senha

5. **Usuário aceita o convite:**
   ```bash
   POST /api/v1/companies/invitations/<uuid>/accept/
   ```
   - Sistema valida que o email do usuário autenticado corresponde ao email do convite
   - Sistema cria o membership automaticamente com o role definido
   - Convite é atualizado para `status: accepted`
   - `responded_at` é preenchido com timestamp atual
   - Retorna o membership criado

**Características importantes:**
- ✅ Usuário **não precisa** trocar senha (já tem conta ativa)
- ✅ Sistema vincula automaticamente o usuário ao convite na criação
- ✅ Validação de segurança: apenas o usuário com o email do convite pode aceitar
- ✅ Membership é criado imediatamente ao aceitar

### Cenário 2: Convidar Email Não Cadastrado

1. **Admin cria convite para email não cadastrado:**
   ```bash
   POST /api/v1/companies/invitations/
   {
     "email": "novo@example.com",
     "role": "stock_manager"
   }
   ```
   - Sistema não encontra usuário, então `user` fica `null`
   - Convite é criado com `status: pending`

2. **Usuário se cadastra** na plataforma com o email `novo@example.com`

3. **Usuário faz login**

4. **Usuário aceita o convite:**
   ```bash
   POST /api/v1/companies/invitations/<uuid>/accept/
   ```
   - Sistema atualiza o convite vinculando o `user`
   - Sistema cria o membership automaticamente
   - Convite é atualizado para `status: accepted`

### Cenário 3: Usuário Recusa o Convite

1. **Admin cria convite**

2. **Usuário faz login**

3. **Usuário recusa o convite:**
   ```bash
   POST /api/v1/companies/invitations/<uuid>/reject/
   ```
   - Convite é atualizado para `status: rejected`
   - `responded_at` é preenchido
   - **Nenhum membership é criado**

## Validações e Regras

### Validações ao Criar Convite

- ✅ Apenas admins da empresa ativa podem criar convites
- ✅ Email deve ser válido
- ✅ Role deve ser um dos valores permitidos
- ✅ Não pode haver múltiplos convites pendentes para o mesmo email/empresa
- ✅ Usuário não pode já ser membro da empresa
- ✅ Empresa deve ser resolvida via token/cookie

### Validações ao Aceitar/Recusar

- ✅ Apenas o usuário convidado pode aceitar/recusar (email deve corresponder)
- ✅ Convite deve estar com status `pending`
- ✅ Ao aceitar, verifica se usuário já não é membro (evita duplicação)
- ✅ Se o convite não tinha `user` definido, vincula automaticamente ao aceitar

### Constraints do Banco de Dados

- **Unique Constraint**: Apenas um convite pendente por email/empresa
  - Permite múltiplos convites históricos (aceitos/rejeitados)
  - Impede spam de convites para o mesmo email

### Segurança

- **Autenticação obrigatória**: Todos os endpoints requerem autenticação
- **Permissões de admin**: Apenas admins podem criar/listar convites
- **Validação de propriedade**: Apenas o destinatário pode aceitar/recusar
- **Validação de email**: Sistema verifica que o email do usuário autenticado corresponde ao email do convite

## Estados e Transições

```
[pending] ──aceita──> [accepted] ──> Cria Membership
    │
    └──recusa──> [rejected]
```

### Transições de Estado

1. **pending → accepted**
   - Quando usuário aceita o convite
   - Cria membership automaticamente
   - Preenche `responded_at`

2. **pending → rejected**
   - Quando usuário recusa o convite
   - Não cria membership
   - Preenche `responded_at`

3. **pending → expired** (futuro)
   - Quando convite expira (implementação futura)
   - Não cria membership

## Integração com Membership

Quando um convite é aceito:

1. Sistema verifica se já existe membership (evita duplicação)
2. Cria novo `Membership` com:
   - `user`: Usuário que aceitou
   - `company`: Empresa do convite
   - `role`: Role definido no convite
3. Atualiza convite para `status: accepted`
4. Preenche `responded_at` com timestamp atual

## Exemplos Práticos

### Exemplo 1: Fluxo Completo - Admin Convidando Usuário Existente

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

# 3. Buscar usuário (opcional, mas recomendado)
curl -b cookies.txt \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  "http://localhost:8000/api/v1/companies/users/search/?email=joao@example.com"

# 4. Criar convite para usuário existente
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  -d '{"email":"joao@example.com","role":"financials"}' \
  http://localhost:8000/api/v1/companies/invitations/

# Resposta mostra que o usuário foi encontrado:
# {
#   "user": "uuid-do-usuario",
#   "user_details": { ... },
#   "email": "joao@example.com",
#   ...
# }
```

**5. Usuário existente faz login e aceita o convite:**

```bash
# Login do usuário convidado
curl -i -c user_cookies.txt -b user_cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"email":"joao@example.com","password":"senha-do-usuario"}' \
  http://localhost:8000/api/v1/users/login/

# Aceitar convite
curl -X POST -b user_cookies.txt \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/companies/invitations/<uuid-do-convite>/accept/

# Resposta: Membership criado automaticamente
```

### Exemplo 2: Usuário Aceitando Convite

```bash
# 1. Login como usuário convidado
curl -i -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"email":"joao@example.com","password":"senha123"}' \
  http://localhost:8000/api/v1/users/login/

# 2. Aceitar convite
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/companies/invitations/<uuid-do-convite>/accept/
```

### Exemplo 3: Listar Todos os Convites da Empresa

```bash
curl -b cookies.txt \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Company-Token: <company_access_token>" \
  http://localhost:8000/api/v1/companies/invitations/
```

## Mensagens de Erro Comuns

| Erro | Causa | Solução |
|------|-------|---------|
| `Parâmetro email é obrigatório` | Email não fornecido na busca | Fornecer parâmetro `email` na query string |
| `Usuário não encontrado com este email` | Email não existe na plataforma | Verificar email ou criar usuário primeiro |
| `Este usuário já é membro desta empresa` | Tentativa de convidar membro existente | Usar endpoint de atualização de membership |
| `Já existe um convite pendente para este email` | Convite pendente já existe | Aguardar resposta ou cancelar convite anterior |
| `Empresa ativa não encontrada` | Token de empresa não enviado | Enviar `X-Company-Token` ou cookie `company_access_token` |
| `You do not have permission` | Usuário não é admin | Apenas admins podem gerenciar convites |
| `Você não tem permissão para responder este convite` | Email não corresponde | Usuário deve estar logado com o email do convite |
| `Este convite já foi aceito/recusado` | Convite já foi respondido | Verificar status do convite |

## Boas Práticas

1. **Sempre buscar usuário antes de convidar**: Use o endpoint de busca para verificar se o usuário existe e se já é membro
2. **Validar email antes de criar convite**: Garanta que o email está correto
3. **Notificar usuário**: Após criar convite, notifique o usuário (implementação futura)
4. **Limpar convites antigos**: Considere implementar limpeza de convites expirados
5. **Monitorar convites pendentes**: Use a listagem para acompanhar convites não respondidos

## Notas Técnicas

- O sistema tenta encontrar o usuário automaticamente pelo email ao criar o convite
- Se o usuário não existir, o convite é criado com `user: null`
- Quando o usuário aceita um convite sem `user` definido, o sistema vincula automaticamente
- O campo `invited_by_name` é calculado dinamicamente (first_name + last_name)
- Convites aceitos criam membership automaticamente em uma transação atômica
- O sistema previne criação de múltiplos memberships para o mesmo usuário/empresa

## Futuras Melhorias

- [ ] Expiração automática de convites pendentes
- [ ] Notificações por email quando convite é criado
- [ ] Endpoint para cancelar convites pendentes (admin)
- [ ] Filtros na listagem (por status, role, etc.)
- [ ] Paginação na listagem de convites
- [ ] Histórico completo de convites por usuário

