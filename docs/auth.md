## Autenticação baseada em cookies

O backend expõe endpoints REST sob `/api/v1/users/` para cadastro e login. Ambos respondem com um objeto `user` e, principalmente, gravam dois cookies HttpOnly (`access_token` e `refresh_token`) responsáveis pela autenticação via `CookieJWTAuthentication`. O frontend não precisa gerenciar JWT manualmente, mas **deve sempre enviar requisições com `credentials` habilitado** para que os cookies sejam incluídos.

### Cadastro (`POST /api/v1/users/register/`)

| Campo          | Tipo      | Obrigatório | Observações                                    |
| -------------- | --------- | ----------- | ---------------------------------------------- |
| `first_name`   | string    | Sim         | Validação de nome (apenas caracteres válidos). |
| `last_name`    | string    | Sim         | Idem acima.                                    |
| `email`        | string    | Sim         | Será usado como login.                         |
| `phone_number` | string    | Não         | Pode ser vazio.                                |
| `password`     | string    | Sim         | Mínimo de 8 caracteres.                        |

Resposta (201):

```json
{
  "user": {
    "first_name": "Ana",
    "last_name": "Silva"
  }
}
```

Os cookies são definidos com:

- `access_token`: vence em 12 horas.
- `refresh_token`: vence em 24 horas.
- `HttpOnly`, `SameSite=Lax` e, por padrão, `Secure=false` (ajustável em `SIMPLE_JWT`).

### Login (`POST /api/v1/users/login/`)

Request body:

```json
{
  "email": "ana@empresa.com",
  "password": "********"
}
```

Resposta (200) idêntica à de cadastro, com o mesmo par de cookies sendo atualizado. Em caso de credenciais inválidas o backend retorna `400` com a mensagem `Invalid credentials.`.

#### Regras de assinatura/trial

- O trial **não é iniciado automaticamente**; o usuário precisa optar por ele via API. Quando iniciado, dura 15 dias e popula `trial_ends_at`.
- O login só é permitido enquanto o trial estiver válido ou houver uma assinatura ativa. Caso contrário, a API devolve `400` com `Assinatura inativa ou período de teste expirado.`.
- Planos atuais (pagamento via Pix):
  - 1 mês: R$500
  - 3 meses: R$1500
  - 6 meses: R$3000
  - 1 ano: R$6000

#### Ativação de trial ou plano (`POST /api/v1/users/subscription/`)

- Autenticado (cookies). Envie **um** dos dois formatos:
  - Iniciar trial:  
    ```json
    { "start_trial": true }
    ```
  - Ativar plano:  
    ```json
    { "plan": "monthly" }
    ```
- Se `start_trial` e `plan` forem enviados juntos, a API retorna erro. Trial só pode ser iniciado uma vez por usuário.
- Resposta (200) inclui `user` e objeto `subscription` com: `active`, `plan`, `subscription_expires_at`, `trial_ends_at`, `message`. Exemplo para trial:

```json
{
  "user": { "first_name": "Ana", "last_name": "Silva" },
  "subscription": {
    "active": false,
    "plan": null,
    "subscription_expires_at": null,
    "trial_ends_at": "2024-06-04T12:00:00Z",
    "message": "Trial de 15 dias iniciado."
  }
}
```

### Sessão atual (`GET /api/v1/users/me/`)

Sem body. Retorna 200 com o mesmo objeto `user` enquanto o cookie `access_token` for válido. Se o cookie tiver expirado ou sido removido, retorna `401`. Útil para validar se o usuário ainda está autenticado quando a aplicação carrega ou após um refresh.

## Empresa ativa via token assinado

Após login, o frontend precisa selecionar a empresa ativa. Para isso existe um token curto que amarra `user + company_id` e é verificado em cada requisição.

- **Gerar token de empresa**: `POST /api/v1/users/company-token/`  
  Body:
  ```json
  { "company_id": "<uuid_da_empresa>" }
  ```
  Requer usuário autenticado e membership na empresa. Resposta (201):
  ```json
  {
    "company_access": "<token>",
    "company": { "id": "<uuid>", "name": "Empresa X" },
    "expires_at": 1736290000
  }
  ```
  O backend também grava o token no cookie HttpOnly `company_access_token` (vida útil ~12 horas, configurável em `SIMPLE_JWT.COMPANY_ACCESS_TOKEN_LIFETIME`).

- **Enviar nas chamadas**: use **um** dos dois:
  - Header: `X-Company-Token: <token>`
  - Cookie já definido (`company_access_token`) com `credentials: 'include'` / `withCredentials: true`.

- **Validação**: o backend checa a assinatura, expiração e membership a cada request. Se o usuário perder acesso à empresa, o token passa a ser rejeitado mesmo antes do vencimento.

- **Troca de empresa**: chame novamente `POST /api/v1/users/company-token/` com outro `company_id` para emitir um novo token/cookie.

### Fluxo completo de login + escolha de empresa

1. **Login**: `POST /api/v1/users/login/` com email/senha, com `credentials: 'include'`/`withCredentials: true`. O backend grava `access_token` e `refresh_token` como cookies HttpOnly.
2. **Buscar empresas do usuário**:
   - `GET /api/v1/companies/` para listar empresas onde o usuário é membro (ou)
   - `GET /api/v1/companies/memberships/` para listar memberships com detalhes.
3. **Escolher empresa**: o frontend exibe a lista; o usuário escolhe uma. Se o usuário tiver só uma empresa, pode-se pular a seleção e usar a única disponível.
4. **Emitir token de empresa**: `POST /api/v1/users/company-token/` com o `company_id` selecionado. O backend devolve `company_access` e grava `company_access_token` (cookie).
5. **Chamar APIs multi-tenant**: enviar `X-Company-Token` ou deixar o cookie `company_access_token` seguir com `credentials: 'include'`. `ActiveCompanyMixin` lerá o token e aplicará o escopo da empresa em todos os ViewSets multi-empresa.
6. **Trocar de empresa**: repita o passo 4 com outro `company_id`.
7. **Expiração**: o token de empresa expira rápido (~15 min). Renove pelo passo 4. Se login expirar, repita o passo 1.

### Como consumir a API no React Admin Panel

1. **Defina a base**: configure uma variável (por exemplo `const API_URL = process.env.REACT_APP_API_URL;`) apontando para a origem do backend (`https://api.fintelis.com` etc).
2. **Envie requisições com cookies**:
   - `fetch`: 

     ```js
     await fetch(`${API_URL}/api/v1/users/login/`, {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       credentials: 'include', // garante que os cookies HttpOnly venham e voltem
       body: JSON.stringify({ email, password }),
     });
     ```

   - `axios`:

     ```js
     axios.post(`${API_URL}/api/v1/users/register/`, payload, { withCredentials: true });
     ```

3. **Chamadas autenticadas**: após login/cadastro bem-sucedido, toda requisição para outros endpoints (`/api/v1/financials/...`, `/api/v1/companies/...`, etc.) deve continuar usando `credentials: 'include'`/`withCredentials: true`. Os cookies serão enviados automaticamente e o DRF validará o `access_token`. Não é necessário (nem possível) ler os cookies HttpOnly no JavaScript.
4. **Empresa ativa**: depois do login, faça `POST /api/v1/users/company-token/` com o `company_id` escolhido e envie `X-Company-Token` (ou deixe o cookie `company_access_token` ser enviado). Sem esse token, os endpoints multi-tenant retornarão erro de empresa ausente ou 403.
5. **Expiração**: quando o `access_token` expirar (~12h) e o `refresh_token` (~24h), a API retornará `401`. Neste momento o frontend deve redirecionar o usuário para a tela de login e repetir o fluxo. Quando o token de empresa expirar (~15 min), renove com outro `POST /api/v1/users/company-token/` mantendo o mesmo `company_id` ou trocando-o.

Seguindo esses passos o painel admin React compartilha automaticamente a sessão do usuário com a API, aproveitando a autenticação baseada em cookies do backend.
