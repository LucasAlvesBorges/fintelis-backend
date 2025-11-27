# Fluxo completo: Registro de novo parceiro

Este guia descreve o passo a passo para que um novo usuário se cadastre na plataforma, crie sua própria empresa, obtenha o token da empresa (company token) e ative o plano gratuito (trial de 15 dias).

> **Pré-requisitos**
> - Backend rodando (`docker compose up app`)
> - Base limpa ou sem e-mail duplicado
> - Executar sempre na ordem abaixo

---

## 1. Registrar o usuário (`POST /api/v1/users/register/`)

```json
{
  "first_name": "Novo",
  "last_name": "Parceiro",
  "email": "novo.parceiro+001@example.com",
  "phone_number": "11999999999",
  "password": "SenhaForte123"
}
```

- Resposta `201` já traz os cookies `access_token` e `refresh_token`; não é necessário fazer login.
- Esses cookies devem ser reutilizados nas próximas chamadas usando `-b cookies.txt -c cookies.txt` no `curl` (ou equivalente no frontend).

---

## 2. Criar a empresa (`POST /api/v1/companies/`)

Headers obrigatórios:
- `Authorization: Bearer <access_token>` (o token definido no cookie também é aceito automaticamente sem header explícito ao usar o mesmo arquivo de cookies).

Body exemplo:
```json
{
  "name": "Empresa Trial Fluxo",
  "cnpj": "12345678000199",
  "email": "financeiro+trial@example.com"
}
```

Resultado:
- O usuário recém-criado passa a ser admin dessa empresa.
- Guarde o `id` retornado (ex.: `1a7c83bb-6443-4079-a6b6-c5e752a4f1c9`).

---

## 3. Obter o company token (`POST /api/v1/users/company-token/`)

Headers:
- `Authorization: Bearer <access_token>`

Body:
```json
{
  "company_id": "1a7c83bb-6443-4079-a6b6-c5e752a4f1c9"
}
```

Resposta `201`:
- Retorna `company_access` e grava o cookie `company_access_token`.
- Esse token identifica qual empresa está ativa nas requisições que dependem de contexto (por exemplo, convites e assinatura). Sempre envie como header `X-Company-Token` ou reutilize o cookie salvo.

---

## 4. Ativar o plano gratuito da empresa (`POST /api/v1/companies/subscription/`)

Headers:
- `Authorization: Bearer <access_token>`
- `X-Company-Token: <company_access_token>` (ou o cookie `company_access_token`)

Body para iniciar o trial:
```json
{ "start_trial": true }
```

Resposta `200`:
- Retorna os dados da empresa e o bloco `subscription` com `trial_ends_at`, confirmando o trial de 15 dias.
- Caso precise ativar um plano pago em vez do trial, envie `{"plan": "monthly"}` (ou qualquer valor de `Company.SubscriptionPlan`); o serializer calcula `subscription_expires_at`.

---

## Dicas rápidas

- Sempre reutilize o arquivo de cookies entre as chamadas `curl` para manter autenticação e o `company_access_token`.
- Se a chamada de subscription retornar `400 {"non_field_errors":["Empresa ativa não encontrada."]}`, significa que o `company_token` não foi enviado/armazenado corretamente. Refaça o passo 3 antes do passo 4.
- Apenas usuários **admins** da empresa conseguem ativar trial ou planos.

