"""
Serviço de integração com Mercado Pago para assinaturas.
Documentação: https://www.mercadopago.com.br/developers/pt/reference/subscriptions/_preapproval_plan/post
"""

import os
import requests
import mercadopago
from decimal import Decimal
from typing import Dict, Any


class MercadoPagoService:
    """
    Serviço para gerenciar assinaturas no Mercado Pago.
    """

    def __init__(self):
        """
        Inicializa o SDK do Mercado Pago com o access token.
        """
        access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
        if not access_token:
            raise ValueError("MERCADOPAGO_ACCESS_TOKEN não configurado no ambiente")

        self.access_token = access_token
        self.sdk = mercadopago.SDK(access_token)
        self.base_url = "https://api.mercadopago.com"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def create_preapproval_plan(
        self,
        reason: str,
        transaction_amount: Decimal,
        frequency: int,
        frequency_type: str,
        back_url: str,
        billing_day: int = None,
        repetitions: int = None,
        free_trial_frequency: int = None,
        free_trial_frequency_type: str = None,
    ) -> Dict[str, Any]:
        """
        Cria um plano de assinatura no Mercado Pago.

        Baseado na documentação oficial:
        https://www.mercadopago.com.br/developers/pt/reference/subscriptions/_preapproval_plan/post

        Args:
            reason: Descrição do plano (ex: "Plano Mensal Fintelis")
            transaction_amount: Valor da cobrança
            frequency: Frequência de cobrança (ex: 1, 3, 6, 12 meses)
            frequency_type: Tipo de frequência ("months" ou "days")
            back_url: URL de retorno após checkout
            billing_day: [OPCIONAL] Dia fixo do mês para cobrança (1-28).
                        Se None, cobra no dia da primeira compra
            repetitions: Número de cobranças (None = infinito)
            free_trial_frequency: Duração do trial gratuito
            free_trial_frequency_type: Tipo de duração do trial

        Returns:
            Dict com resposta do Mercado Pago
        """
        # Estrutura conforme documentação oficial
        plan_data = {
            "reason": reason,
            "auto_recurring": {
                "frequency": int(frequency),
                "frequency_type": frequency_type,
                "transaction_amount": float(transaction_amount),
                "currency_id": "BRL",
            },
            "back_url": back_url,
        }

        # Adicionar billing_day apenas se especificado
        # IMPORTANTE: quando billing_day está presente, frequency DEVE ser 1
        if billing_day is not None:
            plan_data["auto_recurring"]["billing_day"] = int(billing_day)
            plan_data["auto_recurring"]["billing_day_proportional"] = False

        # Adicionar repetições se especificado (opcional)
        if repetitions:
            plan_data["auto_recurring"]["repetitions"] = int(repetitions)

        # Adicionar trial gratuito se especificado (opcional)
        if free_trial_frequency and free_trial_frequency_type:
            plan_data["auto_recurring"]["free_trial"] = {
                "frequency": int(free_trial_frequency),
                "frequency_type": free_trial_frequency_type,
            }

        # Métodos de pagamento permitidos (opcional, mas recomendado)
        plan_data["payment_methods_allowed"] = {
            "payment_types": [
                {"id": "credit_card"},
                {"id": "debit_card"},
            ],
            "payment_methods": [],
        }

        # Criar plano via API REST direta
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Log dos dados enviados para debug
            logger.info(f'Criando plano no Mercado Pago: {plan_data.get("reason")}')
            logger.debug(f"Dados do plano: {plan_data}")

            response = requests.post(
                f"{self.base_url}/preapproval_plan",
                json=plan_data,
                headers=self.headers,
                timeout=30,
            )

            # Log da resposta
            logger.info(f"Status da resposta: {response.status_code}")

            if response.status_code not in [200, 201]:
                error_data = response.json() if response.text else {}
                logger.error(f"Erro do Mercado Pago: {error_data}")

                # Extrair mensagem de erro mais clara
                error_message = error_data.get("message", str(error_data))
                if "cause" in error_data:
                    causes = error_data.get("cause", [])
                    if causes and isinstance(causes, list):
                        error_message = causes[0].get("description", error_message)

                raise Exception(
                    f"Erro ao criar plano no Mercado Pago (status {response.status_code}): {error_message}"
                )

            result = response.json()
            logger.info(f'Plano criado com sucesso: {result.get("id")}')
            return result

        except requests.exceptions.Timeout:
            raise Exception("Timeout ao conectar com Mercado Pago. Tente novamente.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão com Mercado Pago: {str(e)}")

    def get_preapproval_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Busca um plano de assinatura por ID.

        Args:
            plan_id: ID do plano no Mercado Pago

        Returns:
            Dict com dados do plano
            
        Raises:
            Exception: Se o plano não existir (404) ou houver outro erro
        """
        try:
            response = requests.get(
                f"{self.base_url}/preapproval_plan/{plan_id}", headers=self.headers
            )

            if response.status_code == 404:
                error_data = response.json() if response.text else {}
                raise Exception(f"Plano não encontrado: {error_data}")
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise Exception(f"Erro ao buscar plano (status {response.status_code}): {error_data}")

            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão com Mercado Pago: {str(e)}")

    def update_preapproval_plan(self, plan_id: str, status: str) -> Dict[str, Any]:
        """
        Atualiza o status de um plano de assinatura.

        Args:
            plan_id: ID do plano no Mercado Pago
            status: Novo status ("active" ou "inactive")

        Returns:
            Dict com resposta do Mercado Pago
        """
        update_data = {"status": status}

        try:
            response = requests.put(
                f"{self.base_url}/preapproval_plan/{plan_id}",
                json=update_data,
                headers=self.headers,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise Exception(f"Erro ao atualizar plano: {error_data}")

            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão com Mercado Pago: {str(e)}")

    def create_card_token(
        self,
        card_number: str,
        cardholder_name: str,
        expiration_month: str,
        expiration_year: str,
        security_code: str,
        identification_type: str,
        identification_number: str,
    ) -> Dict[str, Any]:
        """
        Cria um token de cartão de crédito/débito no Mercado Pago.

        Args:
            card_number: Número do cartão
            cardholder_name: Nome do titular
            expiration_month: Mês de expiração (MM)
            expiration_year: Ano de expiração (YYYY)
            security_code: Código de segurança (CVV)
            identification_type: Tipo de documento (CPF ou CNPJ)
            identification_number: Número do documento

        Returns:
            Dict com token do cartão
        """
        card_data = {
            "card_number": card_number,
            "cardholder": {
                "name": cardholder_name,
                "identification": {
                    "type": identification_type,
                    "number": identification_number,
                },
            },
            "security_code": security_code,
            "expiration_month": int(expiration_month),
            "expiration_year": int(expiration_year),
        }

        # Usar API REST direta para criar token
        # SDK pode estar usando endpoint antigo ou incompatível
        try:
            response = requests.post(
                f"{self.base_url}/v1/card_tokens",
                json=card_data,
                headers=self.headers,
                params={"public_key": os.environ.get("MERCADOPAGO_PUBLIC_KEY")},
            )

            if response.status_code not in [200, 201]:
                raise Exception(f"Erro ao criar token do cartão: {response.text}")

            return response.json()
        except Exception as e:
            raise Exception(f"Erro ao criar token do cartão: {str(e)}")

    def create_preapproval(
        self,
        preapproval_plan_id: str,
        payer_email: str,
        card_token_id: str = None,
        back_url: str = None,
        external_reference: str = None,
    ) -> Dict[str, Any]:
        """
        Cria uma assinatura (preapproval) para um plano.

        Args:
            preapproval_plan_id: ID do plano criado
            payer_email: Email do pagador (recomendado, mas não obrigatório)
            card_token_id: Token do cartão (opcional, se não usar checkout)
            back_url: URL de retorno (opcional)
            external_reference: Código de referência externa (ex: UUID da subscription ou company_id)

        Returns:
            Dict com resposta do Mercado Pago

        Nota: O auto_recurring (incluindo transaction_amount e start_date) já está definido
        no preapproval_plan. Não devemos enviá-lo aqui para evitar erro de validação.
        """

        subscription_data = {
            "preapproval_plan_id": preapproval_plan_id,
            "status": "pending",
        }

        # Email não é tecnicamente obrigatório, mas é recomendado
        if payer_email:
            subscription_data["payer_email"] = payer_email

        if card_token_id:
            subscription_data["card_token_id"] = card_token_id

        if back_url:
            subscription_data["back_url"] = back_url

        # External reference ajuda a identificar a subscription/empresa no webhook
        if external_reference:
            subscription_data["external_reference"] = external_reference

        # NOTA: Não enviamos auto_recurring aqui porque ele já está definido no preapproval_plan
        # O Mercado Pago processa o pagamento imediatamente quando card_token_id é fornecido
        # Se precisar de start_date customizado, deve ser configurado no plano, não na assinatura

        try:
            response = requests.post(
                f"{self.base_url}/preapproval",
                json=subscription_data,
                headers=self.headers,
            )

            if response.status_code not in [200, 201]:
                error_data = response.json() if response.text else {}
                raise Exception(f"Erro ao criar assinatura: {error_data}")

            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão com Mercado Pago: {str(e)}")

    def get_preapproval(self, preapproval_id: str) -> Dict[str, Any]:
        """
        Busca uma assinatura por ID.

        Args:
            preapproval_id: ID da assinatura no Mercado Pago

        Returns:
            Dict com dados da assinatura
        """
        try:
            response = requests.get(
                f"{self.base_url}/preapproval/{preapproval_id}", headers=self.headers
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise Exception(f"Erro ao buscar assinatura: {error_data}")

            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão com Mercado Pago: {str(e)}")

    def update_preapproval(
        self,
        preapproval_id: str,
        status: str = None,
        reason: str = None,
    ) -> Dict[str, Any]:
        """
        Atualiza uma assinatura (ex: pausar, cancelar).

        Args:
            preapproval_id: ID da assinatura
            status: Novo status ("paused", "cancelled", "authorized")
            reason: Motivo da atualização

        Returns:
            Dict com resposta do Mercado Pago
        """
        update_data = {}

        if status:
            update_data["status"] = status

        if reason:
            update_data["reason"] = reason

        try:
            response = requests.put(
                f"{self.base_url}/preapproval/{preapproval_id}",
                json=update_data,
                headers=self.headers,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise Exception(f"Erro ao atualizar assinatura: {error_data}")

            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão com Mercado Pago: {str(e)}")

    def search_preapprovals(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Busca assinaturas com filtros.

        Args:
            filters: Filtros de busca (ex: {"payer_email": "email@example.com"})

        Returns:
            Dict com lista de assinaturas
        """
        try:
            response = requests.get(
                f"{self.base_url}/preapproval/search",
                params=filters or {},
                headers=self.headers,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise Exception(f"Erro ao buscar assinaturas: {error_data}")

            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão com Mercado Pago: {str(e)}")

    def create_payment(
        self,
        transaction_amount: Decimal,
        description: str,
        payment_method_id: str,
        payer_email: str,
        payer_identification_type: str = None,
        payer_identification_number: str = None,
    ) -> Dict[str, Any]:
        """
        Cria um pagamento único (não recorrente) no Mercado Pago.
        Usado para PIX e outros métodos de pagamento único.

        Args:
            transaction_amount: Valor do pagamento
            description: Descrição do pagamento
            payment_method_id: ID do método ('pix', 'bolbancario', etc)
            payer_email: Email do pagador
            payer_identification_type: Tipo de documento ('CPF' ou 'CNPJ')
            payer_identification_number: Número do documento

        Returns:
            Dict com resposta do Mercado Pago incluindo QR Code para PIX
        """
        payment_data = {
            "transaction_amount": float(transaction_amount),
            "description": description,
            "payment_method_id": payment_method_id,
            "payer": {
                "email": payer_email,
            },
        }

        # External reference pode ser adicionado aqui também se necessário

        # Adicionar identificação se fornecida
        if payer_identification_type and payer_identification_number:
            payment_data["payer"]["identification"] = {
                "type": payer_identification_type,
                "number": payer_identification_number,
            }

        response = self.sdk.payment().create(payment_data)

        if response["status"] not in [200, 201]:
            raise Exception(f"Erro ao criar pagamento: {response}")

        return response["response"]

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Busca um pagamento por ID.

        Args:
            payment_id: ID do pagamento no Mercado Pago

        Returns:
            Dict com dados do pagamento
        """
        response = self.sdk.payment().get(payment_id)

        if response["status"] != 200:
            raise Exception(f"Erro ao buscar pagamento: {response}")

        return response["response"]

    def create_preference(
        self,
        items: list,
        payer_email: str,
        back_urls: Dict[str, str] = None,
        auto_return: str = "approved",
        external_reference: str = None,
    ) -> Dict[str, Any]:
        """
        Cria uma preferência de pagamento (Checkout Pro) no Mercado Pago.
        Usado para redirecionar o usuário para a página de checkout do Mercado Pago.

        Args:
            items: Lista de itens a serem pagos. Cada item deve ter:
                {
                    "title": "Nome do produto",
                    "quantity": 1,
                    "unit_price": 100.00
                }
            payer_email: Email do pagador
            back_urls: URLs de retorno após pagamento. Ex:
                {
                    "success": "https://yoursite.com/success",
                    "failure": "https://yoursite.com/failure",
                    "pending": "https://yoursite.com/pending"
                }
            auto_return: Comportamento após pagamento ("approved" ou "all")
            external_reference: Código de referência externa (ex: UUID da subscription ou company_id)

        Returns:
            Dict com resposta do Mercado Pago incluindo init_point (URL do checkout)
        """
        preference_data = {
            "items": items,
            "payer": {
                "email": payer_email,
            },
            "auto_return": auto_return,
        }

        if back_urls:
            preference_data["back_urls"] = back_urls

        if external_reference:
            preference_data["external_reference"] = external_reference

        # Configurar para aceitar apenas cartão de crédito/débito
        preference_data["payment_methods"] = {
            "excluded_payment_types": [
                {"id": "ticket"},  # Excluir boleto
                {"id": "bank_transfer"},  # Excluir transferência bancária
            ],
            "excluded_payment_methods": [],
            "installments": 12,  # Máximo de parcelas
        }

        try:
            response = requests.post(
                f"{self.base_url}/checkout/preferences",
                json=preference_data,
                headers=self.headers,
                timeout=30,
            )

            if response.status_code not in [200, 201]:
                error_data = response.json() if response.text else {}
                raise Exception(f"Erro ao criar preferência: {error_data}")

            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão com Mercado Pago: {str(e)}")


# Singleton instance
_mercadopago_service = None


def get_mercadopago_service() -> MercadoPagoService:
    """
    Retorna instância singleton do serviço Mercado Pago.
    """
    global _mercadopago_service
    if _mercadopago_service is None:
        _mercadopago_service = MercadoPagoService()
    return _mercadopago_service
