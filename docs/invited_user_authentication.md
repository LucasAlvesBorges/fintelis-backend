# Autenticação de Usuários Criados via Convite

Este documento descreve o fluxo completo de autenticação para usuários que foram criados através de convites de membership. Esses usuários têm características especiais que requerem um tratamento diferenciado no processo de login e primeiro acesso.

## Visão Geral

Quando um administrador cria um novo usuário via convite de membership (`POST /api/v1/companies/memberships/invite/` com `new_user`), o sistema:

1. ✅ Cria o usuário com uma senha temporária (mínimo 4 caracteres)
2. ✅ Define automaticamente `must_change_password = true`
3. ✅ Cria o membership na empresa imediatamente
4. ✅ Requer que o usuário troque a senha no primeiro login

**Diferença fundamental**: Usuários criados via convite **já têm membership** e **devem trocar a senha** antes de acessar o sistema normalmente.

## Fluxo Completo

### 1. Criação do Usuário pelo Admin

O administrador cria um novo usuário através do endpoint de convite:

```bash
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

**O que acontece internamente:**

1. O sistema usa `MembershipUserCreateSerializer` para criar o usuário
2. A senha temporária é definida (mínimo 4 caracteres, diferente do registro normal que exige 8)
3. O campo `must_change_password` é automaticamente definido como `true`
4. O usuário é criado e o membership é criado imediatamente
5. O usuário **não precisa** ativar trial/subscription para ter acesso (já é membro de uma empresa)

**Resposta (201 Created):**
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

### 2. Primeiro Login do Usuário Convidado

O usuário faz login usando as credenciais temporárias fornecidas pelo admin:

```bash
POST /api/v1/users/login/
{
  "email": "joao@example.com",
  "password": "1234"
}
```

**Resposta (200 OK):**
```json
{
  "user": {
    "first_name": "João",
    "last_name": "Silva",
    "must_change_password": true
  }
}
```

**Características importantes:**

- ✅ Login é bem-sucedido mesmo com senha temporária (4 caracteres)
- ✅ A resposta **sempre** inclui `must_change_password: true`
- ✅ Tokens de autenticação são gerados e salvos nos cookies
- ⚠️ **O frontend DEVE verificar este flag e forçar a troca de senha**

### 3. Verificação do Status (Endpoint /me)

O frontend deve verificar o status do usuário após o login:

```bash
GET /api/v1/users/me/
```

**Resposta:**
```json
{
  "user": {
    "first_name": "João",
    "last_name": "Silva",
    "must_change_password": true
  }
}
```

**Lógica do Frontend:**

```javascript
// Após login ou verificação de sessão
const response = await fetch('/api/v1/users/me/', {
  credentials: 'include'
});
const data = await response.json();

if (data.user.must_change_password === true) {
  // REDIRECIONAR IMEDIATAMENTE para tela de troca de senha
  // BLOQUEAR acesso a outras funcionalidades
  router.push('/change-password');
}
```

### 4. Troca de Senha Obrigatória

O usuário **deve** trocar a senha antes de acessar qualquer outra funcionalidade:

```bash
POST /api/v1/users/change-password/
{
  "current_password": "1234",
  "new_password": "SenhaForte123!"
}
```

**Validações aplicadas:**

- ✅ Valida que a senha atual está correta
- ✅ Nova senha deve ter **mínimo 8 caracteres** (validações padrão do Django)
- ✅ Nova senha deve ser diferente da atual
- ✅ Aplica todas as regras de `AUTH_PASSWORD_VALIDATORS`

**Resposta de sucesso (200 OK):**
```json
{
  "user": {
    "first_name": "João",
    "last_name": "Silva",
    "must_change_password": false
  }
}
```

**O que acontece internamente:**

1. Sistema valida a senha atual
2. Aplica validações de senha (mínimo 8 caracteres + regras do Django)
3. Grava a nova senha
4. **Define `must_change_password = false`**
5. Retorna o usuário atualizado

### 5. Acesso Normal ao Sistema

Após trocar a senha, o usuário pode acessar o sistema normalmente:

- ✅ `must_change_password` agora é `false`
- ✅ Usuário pode acessar todas as funcionalidades
- ✅ Login futuro usa a nova senha
- ✅ Não precisa mais trocar a senha

## Comparação: Registro Normal vs. Convite

| Aspecto | Registro Normal | Convite de Membership |
|---------|----------------|----------------------|
| **Endpoint** | `POST /api/v1/users/register/` | `POST /api/v1/companies/memberships/invite/` |
| **Senha mínima** | 8 caracteres | 4 caracteres (temporária) |
| **must_change_password** | `false` (padrão) | `true` (forçado) |
| **Membership** | Criado depois (opcional) | Criado imediatamente |
| **Trial/Subscription** | Deve ativar manualmente | Não precisa (já é membro) |
| **Primeiro acesso** | Pode usar normalmente | **DEVE trocar senha** |
| **Quem cria** | Próprio usuário | Admin da empresa |

## Validações e Regras

### Validações de Senha

**Senha temporária (convite):**
- Mínimo **4 caracteres**
- Definida pelo admin
- Usada apenas para primeiro login

**Nova senha (após troca):**
- Mínimo **8 caracteres**
- Deve cumprir `AUTH_PASSWORD_VALIDATORS` do Django
- Não pode ser igual à senha atual
- Deve conter letras, números e caracteres especiais (conforme validações)

### Regras de Acesso

1. **Login com senha temporária:**
   - ✅ Permitido mesmo com senha de 4 caracteres
   - ✅ Retorna `must_change_password: true`
   - ✅ Tokens são gerados normalmente

2. **Acesso ao sistema:**
   - ⚠️ Se `must_change_password = true`, o frontend **deve** bloquear acesso
   - ⚠️ Usuário só pode acessar a tela de troca de senha
   - ✅ Após trocar senha, acesso liberado

3. **Trial/Subscription:**
   - ✅ Usuários criados via convite **não precisam** ativar trial
   - ✅ Já têm membership, então têm acesso à empresa
   - ⚠️ Mas ainda precisam ter trial/subscription ativa para login (regra geral do sistema)

## Exemplo Completo de Fluxo

### Passo a Passo

**1. Admin cria usuário via convite:**
```bash
curl -X POST -b cookies.txt \
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

**2. Usuário recebe credenciais:**
- Email: `joao@example.com`
- Senha temporária: `1234`
- Instruções: "Faça login e troque sua senha"

**3. Usuário faz primeiro login:**
```bash
curl -i -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "email": "joao@example.com",
    "password": "1234"
  }' \
  http://localhost:8000/api/v1/users/login/
```

**Resposta:**
```json
{
  "user": {
    "first_name": "João",
    "last_name": "Silva",
    "must_change_password": true
  }
}
```

**4. Frontend verifica status:**
```bash
curl -b cookies.txt http://localhost:8000/api/v1/users/me/
```

**Resposta:**
```json
{
  "user": {
    "first_name": "João",
    "last_name": "Silva",
    "must_change_password": true
  }
}
```

**5. Frontend redireciona para troca de senha:**
- Bloqueia acesso a outras rotas
- Mostra tela de troca de senha
- Usuário não pode sair até trocar

**6. Usuário troca a senha:**
```bash
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "1234",
    "new_password": "SenhaForte123!"
  }' \
  http://localhost:8000/api/v1/users/change-password/
```

**Resposta:**
```json
{
  "user": {
    "first_name": "João",
    "last_name": "Silva",
    "must_change_password": false
  }
}
```

**7. Frontend libera acesso:**
- `must_change_password` agora é `false`
- Usuário pode acessar todas as funcionalidades
- Redireciona para dashboard/home

## Implementação no Frontend

### Checklist de Implementação

- [ ] Verificar `must_change_password` após login
- [ ] Verificar `must_change_password` ao carregar sessão (`/me`)
- [ ] Bloquear rotas quando `must_change_password = true`
- [ ] Redirecionar para tela de troca de senha
- [ ] Não permitir navegação até trocar senha
- [ ] Após trocar senha, verificar novamente e liberar acesso
- [ ] Mostrar mensagem clara sobre necessidade de trocar senha

### Exemplo de Código (React)

```javascript
// Hook para verificar se deve trocar senha
function useMustChangePassword() {
  const [mustChange, setMustChange] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/users/me/', {
      credentials: 'include'
    })
      .then(res => res.json())
      .then(data => {
        setMustChange(data.user.must_change_password === true);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return { mustChange, loading };
}

// Componente de proteção de rotas
function ProtectedRoute({ children }) {
  const { mustChange, loading } = useMustChangePassword();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && mustChange) {
      navigate('/change-password', { replace: true });
    }
  }, [mustChange, loading, navigate]);

  if (loading) return <Loading />;
  if (mustChange) return null; // Redirecionando...

  return children;
}

// Uso nas rotas
<Route path="/dashboard" element={
  <ProtectedRoute>
    <Dashboard />
  </ProtectedRoute>
} />
```

## Erros Comuns

### Erro: Login falha mesmo com senha correta

**Causa:** Usuário não tem trial/subscription ativa

**Solução:**
```bash
# Ativar trial via Django shell
docker compose exec app python manage.py shell
>>> from apps.users.models import User
>>> user = User.objects.get(email='joao@example.com')
>>> user.start_trial()
```

### Erro: "Senha atual incorreta" ao trocar senha

**Causa:** Senha temporária foi digitada incorretamente

**Solução:** Verificar se a senha temporária está correta ou pedir ao admin para redefinir

### Erro: Nova senha não atende aos requisitos

**Causa:** Nova senha não cumpre validações (mínimo 8 caracteres + regras do Django)

**Solução:** Usar senha mais forte que atenda aos requisitos

## Segurança

### Boas Práticas

1. **Senhas temporárias:**
   - Use senhas simples mas únicas (ex: "Temp1234")
   - Não reutilize senhas temporárias
   - Informe ao usuário que deve trocar imediatamente

2. **Comunicação:**
   - Envie credenciais por canal seguro
   - Informe claramente que é senha temporária
   - Instrua sobre necessidade de troca

3. **Frontend:**
   - **SEMPRE** verifique `must_change_password` após login
   - **NUNCA** permita acesso sem trocar senha quando flag está ativo
   - Mostre mensagem clara sobre necessidade de troca

4. **Backend:**
   - Validações de senha são aplicadas na troca
   - Flag é automaticamente desativado após troca
   - Sistema previne uso de senha temporária após troca

## Resumo do Fluxo

```
┌─────────────────────────────────────────────────────────┐
│ 1. Admin cria usuário via convite                      │
│    → must_change_password = true                        │
│    → Senha temporária (4+ chars)                       │
│    → Membership criado                                 │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Usuário faz primeiro login                           │
│    → Login bem-sucedido                                 │
│    → Resposta: must_change_password = true             │
│    → Tokens gerados                                     │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Frontend verifica /me                                │
│    → must_change_password = true                        │
│    → REDIRECIONA para /change-password                  │
│    → BLOQUEIA outras rotas                              │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Usuário troca senha                                  │
│    → Valida senha atual                                 │
│    → Aplica validações (8+ chars)                      │
│    → Grava nova senha                                  │
│    → must_change_password = false                       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 5. Acesso liberado                                      │
│    → must_change_password = false                       │
│    → Usuário pode acessar sistema                       │
│    → Próximos logins usam nova senha                    │
└─────────────────────────────────────────────────────────┘
```

## Endpoints Relacionados

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/v1/companies/memberships/invite/` | POST | Criar usuário via convite (admin) |
| `/api/v1/users/login/` | POST | Login (retorna `must_change_password`) |
| `/api/v1/users/me/` | GET | Verificar status (inclui `must_change_password`) |
| `/api/v1/users/change-password/` | POST | Trocar senha (desativa flag) |

## Notas Técnicas

- O campo `must_change_password` é um `BooleanField` no modelo `User`
- É definido automaticamente como `true` no `MembershipUserCreateSerializer`
- É desativado automaticamente no `PasswordChangeSerializer` após troca bem-sucedida
- O `UserAuthenticationSerializer` sempre inclui este campo nas respostas
- O sistema não força logout após troca de senha (tokens continuam válidos)

