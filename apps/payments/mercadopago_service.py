"""
Serviço de integração com Mercado Pago para assinaturas.
Documentação: https://www.mercadopago.com.br/developers/pt/reference/subscriptions/_preapproval_plan/post
"""
import os
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
        access_token = os.environ.get('MERCADOPAGO_ACCESS_TOKEN')
        if not access_token:
            raise ValueError('MERCADOPAGO_ACCESS_TOKEN não configurado no ambiente')
        
        self.sdk = mercadopago.SDK(access_token)
    
    def create_preapproval_plan(
        self,
        reason: str,
        transaction_amount: Decimal,
        frequency: int,
        frequency_type: str,
        billing_day: int,
        back_url: str,
        repetitions: int = None,
        free_trial_frequency: int = None,
        free_trial_frequency_type: str = None,
    ) -> Dict[str, Any]:
        """
        Cria um plano de assinatura no Mercado Pago.
        
        Args:
            reason: Descrição do plano (ex: "Plano Mensal Fintelis")
            transaction_amount: Valor da cobrança
            frequency: Frequência de cobrança (ex: 1)
            frequency_type: Tipo de frequência ("months" ou "days")
            billing_day: Dia do mês para cobrança (1-28)
            back_url: URL de retorno após checkout
            repetitions: Número de cobranças (None = infinito)
            free_trial_frequency: Duração do trial gratuito
            free_trial_frequency_type: Tipo de duração do trial
        
        Returns:
            Dict com resposta do Mercado Pago
        """
        plan_data = {
            "reason": reason,
            "auto_recurring": {
                "frequency": frequency,
                "frequency_type": frequency_type,
                "transaction_amount": float(transaction_amount),
                "currency_id": "BRL",
                "billing_day": billing_day,
                "billing_day_proportional": False,
            },
            "back_url": back_url,
        }
        
        # Adicionar repetições se especificado
        if repetitions:
            plan_data["auto_recurring"]["repetitions"] = repetitions
        
        # Adicionar trial gratuito se especificado
        if free_trial_frequency and free_trial_frequency_type:
            plan_data["auto_recurring"]["free_trial"] = {
                "frequency": free_trial_frequency,
                "frequency_type": free_trial_frequency_type,
            }
        
        # Métodos de pagamento permitidos
        plan_data["payment_methods_allowed"] = {
            "payment_types": [
                {"id": "credit_card"},
                {"id": "debit_card"},
            ],
            "payment_methods": []
        }
        
        # Criar plano via API
        response = self.sdk.preapproval_plan().create(plan_data)
        
        if response["status"] not in [200, 201]:
            raise Exception(f"Erro ao criar plano: {response}")
        
        return response["response"]
    
    def get_preapproval_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Busca um plano de assinatura por ID.
        
        Args:
            plan_id: ID do plano no Mercado Pago
        
        Returns:
            Dict com dados do plano
        """
        response = self.sdk.preapproval_plan().get(plan_id)
        
        if response["status"] != 200:
            raise Exception(f"Erro ao buscar plano: {response}")
        
        return response["response"]
    
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
        
        response = self.sdk.preapproval_plan().update(plan_id, update_data)
        
        if response["status"] != 200:
            raise Exception(f"Erro ao atualizar plano: {response}")
        
        return response["response"]
    
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
                    "number": identification_number
                }
            },
            "security_code": security_code,
            "expiration_month": int(expiration_month),
            "expiration_year": int(expiration_year),
        }
        
        response = self.sdk.card_token().create(card_data)
        
        if response["status"] not in [200, 201]:
            raise Exception(f"Erro ao criar token do cartão: {response}")
        
        return response["response"]
    
    def create_preapproval(
        self,
        preapproval_plan_id: str,
        payer_email: str,
        card_token_id: str = None,
        back_url: str = None,
    ) -> Dict[str, Any]:
        """
        Cria uma assinatura (preapproval) para um plano.
        
        Args:
            preapproval_plan_id: ID do plano criado
            payer_email: Email do pagador
            card_token_id: Token do cartão (opcional, se não usar checkout)
            back_url: URL de retorno (opcional)
        
        Returns:
            Dict com resposta do Mercado Pago
        """
        subscription_data = {
            "preapproval_plan_id": preapproval_plan_id,
            "payer_email": payer_email,
            "status": "pending",
        }
        
        if card_token_id:
            subscription_data["card_token_id"] = card_token_id
        
        if back_url:
            subscription_data["back_url"] = back_url
        
        response = self.sdk.preapproval().create(subscription_data)
        
        if response["status"] not in [200, 201]:
            raise Exception(f"Erro ao criar assinatura: {response}")
        
        return response["response"]
    
    def get_preapproval(self, preapproval_id: str) -> Dict[str, Any]:
        """
        Busca uma assinatura por ID.
        
        Args:
            preapproval_id: ID da assinatura no Mercado Pago
        
        Returns:
            Dict com dados da assinatura
        """
        response = self.sdk.preapproval().get(preapproval_id)
        
        if response["status"] != 200:
            raise Exception(f"Erro ao buscar assinatura: {response}")
        
        return response["response"]
    
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
        
        response = self.sdk.preapproval().update(preapproval_id, update_data)
        
        if response["status"] != 200:
            raise Exception(f"Erro ao atualizar assinatura: {response}")
        
        return response["response"]
    
    def search_preapprovals(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Busca assinaturas com filtros.
        
        Args:
            filters: Filtros de busca (ex: {"payer_email": "email@example.com"})
        
        Returns:
            Dict com lista de assinaturas
        """
        response = self.sdk.preapproval().search(filters=filters or {})
        
        if response["status"] != 200:
            raise Exception(f"Erro ao buscar assinaturas: {response}")
        
        return response["response"]
    
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
            }
        }
        
        # Adicionar identificação se fornecida
        if payer_identification_type and payer_identification_number:
            payment_data["payer"]["identification"] = {
                "type": payer_identification_type,
                "number": payer_identification_number
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

