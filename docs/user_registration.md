## Fluxo de criação de conta e ativação

1. **Cadastro do usuário**  
   - Endpoint: `POST /api/v1/users/register/`  
   - Campos: `first_name`, `last_name`, `email`, `phone_number`, `password` (mín. 8 chars).  
   - Resposta: objeto `user` e cookies `access_token`/`refresh_token` (HttpOnly) já gravados.
   - Trial: **não inicia automaticamente**; o usuário precisa escolher entre iniciar o período gratuito de 15 dias ou assinar um plano.
   - JSON de exemplo:

```json
{
  "first_name": "Ana",
  "last_name": "Silva",
  "email": "ana@empresa.com",
  "phone_number": "+55 11 99999-0000",
  "password": "senha-super-segura"
}
```

2. **Criação de empresa + membership**  
   - Use o endpoint de criação de empresa (ex.: `POST /api/v1/companies/`) com os dados da companhia.  
   - O backend cria a empresa e o membership vinculando o usuário autenticado à nova empresa.
   - JSON de exemplo:

```json
{
  "name": "Empresa Demo",
  "cnpj": "12.345.678/0001-99",
  "email": "contato@empresa.com"
}
```

3. **Escolha do plano ou início do período gratuito**  
   - Endpoint: `POST /api/v1/users/subscription/` (autenticado, com cookies).  
   - Para iniciar o trial de 15 dias: enviar `{ "start_trial": true }`. Trial só pode ser usado uma vez e não inicia automaticamente no cadastro.  
   - Para assinar um plano: enviar `{ "plan": "<monthly|quarterly|semiannual|annual>" }`.  
   - Planos atuais (Pix):  
     - 1 mês: R$500  
     - 3 meses: R$1500  
     - 6 meses: R$3000  
     - 1 ano: R$6000  
   - Após o trial ou após o vencimento do plano, o login exige assinatura ativa (`subscription_active`/`subscription_expires_at`). Caso contrário, o backend retorna erro informando que o trial expirou ou a assinatura está inativa.
   - JSON de exemplo para trial:

```json
{ "start_trial": true }
```

   - JSON de exemplo para plano:

```json
{ "plan": "monthly" }
```

### Detalhamento do endpoint de assinatura (`POST /api/v1/users/subscription/`)
- **Auth**: requer cookies `access_token`/`refresh_token` (usar `credentials: 'include'`/`withCredentials: true`).
- **Headers**: `Content-Type: application/json`.
- **Body** (exclusivo — envie apenas um dos dois):
  - Trial: `{ "start_trial": true }`
  - Plano: `{ "plan": "monthly" | "quarterly" | "semiannual" | "annual" }`
- **Respostas de sucesso (200)**:
  - Trial:

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

  - Plano:

    ```json
    {
      "user": { "first_name": "Ana", "last_name": "Silva" },
      "subscription": {
        "active": true,
        "plan": "monthly",
        "subscription_expires_at": "2024-06-20T12:00:00Z",
        "trial_ends_at": null,
        "message": "Plano monthly ativado."
      }
    }
    ```
- **Erros (400)**:
  - Enviou trial e plano juntos: `"Escolha trial ou plano, não ambos."`
  - Não enviou nenhum: `"Envie start_trial=true ou selecione um plano."`
  - Trial já usado: `"Trial já iniciado ou utilizado."`
  - Plano inválido: erro de validação do DRF para campo `plan`.
- **Validade**:
  - Trial: 15 dias a partir da ativação.
  - Planos: expiração calculada pelo backend (30/90/180/365 dias).
  - Login é permitido se `trial_ends_at` estiver no futuro **ou** se `subscription_active` for `true` e `subscription_expires_at` ainda não tiver passado.

### Observações de implementação no frontend (React admin panel)
- Sempre enviar requisições com cookies: `credentials: 'include'` ou `withCredentials: true`.
- Para checar sessão: `GET /api/v1/users/me/` (retorna 200 se o usuário ainda tem acesso; `401` se expirar).
- Ao expirar o trial, apresente a seleção de plano e processe o pagamento conforme as opções acima; só então ative a assinatura para liberar novos logins.
