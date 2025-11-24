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

### Sessão atual (`GET /api/v1/users/me/`)

Sem body. Retorna 200 com o mesmo objeto `user` enquanto o cookie `access_token` for válido. Se o cookie tiver expirado ou sido removido, retorna `401`. Útil para validar se o usuário ainda está autenticado quando a aplicação carrega ou após um refresh.

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
4. **Expiração**: quando o `access_token` expirar (~12h) e o `refresh_token` (~24h), a API retornará `401`. Neste momento o frontend deve redirecionar o usuário para a tela de login e repetir o fluxo. (Não há endpoint de refresh separado neste projeto; utilizar `GET /api/v1/users/me/` para verificar a sessão e, em caso de `401`, forçar novo login.)

Seguindo esses passos o painel admin React compartilha automaticamente a sessão do usuário com a API, aproveitando a autenticação baseada em cookies do backend.
