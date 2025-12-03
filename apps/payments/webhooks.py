"""
Webhooks para receber notificações do Mercado Pago sobre assinaturas.
Documentação: https://www.mercadopago.com.br/developers/pt/docs/subscriptions/integration-configuration/notifications
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone

from .models import Subscription, Payment
from .mercadopago_service import get_mercadopago_service


@api_view(['POST'])
@permission_classes([AllowAny])  # Mercado Pago não envia autenticação
def mercadopago_webhook(request):
    """
    Webhook para receber notificações do Mercado Pago.
    
    POST /api/v1/payments/webhook/mercadopago/
    
    Tipos de notificação:
    - preapproval: Mudanças em assinaturas
    - authorized_payment: Pagamento autorizado
    - payment: Mudanças em pagamentos
    """
    try:
        # Extrair dados da notificação
        notification_type = request.query_params.get('type') or request.data.get('type')
        notification_id = request.query_params.get('data.id') or request.data.get('data', {}).get('id')
        
        if not notification_type or not notification_id:
            return Response(
                {'error': 'Missing notification type or id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Processar notificação de assinatura
        if notification_type == 'preapproval':
            handle_preapproval_notification(notification_id)
        
        # Processar notificação de pagamento
        elif notification_type in ['authorized_payment', 'payment']:
            handle_payment_notification(notification_id)
        
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        # Log do erro (em produção, usar logging adequado)
        print(f"Erro no webhook: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def handle_preapproval_notification(preapproval_id: str):
    """
    Processa notificação de mudança em assinatura.
    """
    try:
        # Buscar assinatura no Mercado Pago
        mp_service = get_mercadopago_service()
        mp_data = mp_service.get_preapproval(preapproval_id)
        
        # Atualizar assinatura no banco
        subscription = Subscription.objects.get(preapproval_id=preapproval_id)
        subscription.status = mp_data.get('status', subscription.status)
        subscription.payer_email = mp_data.get('payer_email', subscription.payer_email)
        
        # Atualizar datas
        if mp_data.get('start_date'):
            subscription.start_date = mp_data['start_date']
        if mp_data.get('next_payment_date'):
            subscription.next_payment_date = mp_data['next_payment_date']
        if mp_data.get('end_date'):
            subscription.end_date = mp_data['end_date']
        
        subscription.mercadopago_response = mp_data
        subscription.save()
        
        # Se status mudou para autorizado, ativar assinatura
        if subscription.status == Subscription.Status.AUTHORIZED:
            subscription.activate()
        
        # Se status mudou para cancelado, desativar
        elif subscription.status == Subscription.Status.CANCELLED:
            subscription.cancel()
    
    except Subscription.DoesNotExist:
        print(f"Assinatura {preapproval_id} não encontrada no banco de dados")
    except Exception as e:
        print(f"Erro ao processar notificação de assinatura: {str(e)}")
        raise


def handle_payment_notification(payment_id: str):
    """
    Processa notificação de pagamento (PIX, Cartão, etc).
    Atualiza status do pagamento e ativa assinatura quando aprovado.
    """
    try:
        # Buscar pagamento no Mercado Pago
        mp_service = get_mercadopago_service()
        mp_payment = mp_service.get_payment(payment_id)
        
        payment_status = mp_payment.get('status')
        mercadopago_payment_id = str(mp_payment.get('id'))
        
        print(f"Processando pagamento {mercadopago_payment_id} - Status: {payment_status}")
        
        # Buscar pagamento no banco de dados
        try:
            payment = Payment.objects.get(payment_id=mercadopago_payment_id)
        except Payment.DoesNotExist:
            # Pagamento não existe localmente, pode ser de uma assinatura recorrente
            # Criar novo registro de pagamento
            print(f"Pagamento {mercadopago_payment_id} não encontrado, criando novo registro")
            
            # Tentar encontrar a empresa pela assinatura
            preapproval_id = mp_payment.get('preapproval_id')
            if preapproval_id:
                try:
                    subscription = Subscription.objects.get(preapproval_id=preapproval_id)
                    
                    payment = Payment.objects.create(
                        company=subscription.company,
                        payment_id=mercadopago_payment_id,
                        transaction_id=mp_payment.get('id'),
                        amount=mp_payment.get('transaction_amount', 0),
                        subscription_plan=subscription.plan.subscription_plan_type,
                        payment_method=_map_payment_method(mp_payment.get('payment_type_id')),
                        status=_map_payment_status(payment_status),
                        gateway_response=mp_payment
                    )
                except Subscription.DoesNotExist:
                    print(f"Assinatura {preapproval_id} não encontrada")
                    return
            else:
                print(f"Pagamento sem preapproval_id, não foi possível criar registro")
                return
        
        # Atualizar status do pagamento
        old_status = payment.status
        payment.status = _map_payment_status(payment_status)
        payment.transaction_id = mp_payment.get('id')
        payment.gateway_response = mp_payment
        
        # Se pagamento foi aprovado
        if payment_status == 'approved' and old_status != Payment.Status.COMPLETED:
            from datetime import timedelta
            from .models import SubscriptionPlanType
            
            payment.status = Payment.Status.COMPLETED
            payment.completed_at = timezone.now()
            
            # Ativar/renovar assinatura da empresa
            company = payment.company
            config = SubscriptionPlanType.get_config(payment.subscription_plan)
            
            # Se já tem assinatura ativa, estender. Caso contrário, ativar nova
            if company.subscription_active and company.subscription_expires_at:
                # Estender a partir da data de expiração atual
                company.subscription_expires_at += timedelta(days=config['duration_days'])
            else:
                # Ativar nova assinatura
                company.subscription_active = True
                company.subscription_plan = payment.subscription_plan
                company.subscription_expires_at = timezone.now() + timedelta(days=config['duration_days'])
            
            company.save()
            
            print(f"Assinatura ativada/renovada para {company.name} até {company.subscription_expires_at}")
        
        # Se pagamento foi recusado ou cancelado
        elif payment_status in ['rejected', 'cancelled', 'refunded']:
            payment.status = _map_payment_status(payment_status)
            print(f"Pagamento {payment_status}: {mercadopago_payment_id}")
        
        payment.save()
        
        # TODO: Enviar email/notificação para o usuário sobre o status do pagamento
    
    except Exception as e:
        print(f"Erro ao processar notificação de pagamento: {str(e)}")
        raise


def _map_payment_status(mp_status: str) -> str:
    """
    Mapeia status do Mercado Pago para status do modelo Payment.
    """
    status_map = {
        'pending': Payment.Status.PENDING,
        'approved': Payment.Status.COMPLETED,
        'authorized': Payment.Status.COMPLETED,
        'in_process': Payment.Status.PENDING,
        'in_mediation': Payment.Status.PENDING,
        'rejected': Payment.Status.FAILED,
        'cancelled': Payment.Status.FAILED,
        'refunded': Payment.Status.REFUNDED,
        'charged_back': Payment.Status.REFUNDED,
    }
    return status_map.get(mp_status, Payment.Status.PENDING)


def _map_payment_method(payment_type_id: str) -> str:
    """
    Mapeia tipo de pagamento do Mercado Pago para método do modelo Payment.
    """
    method_map = {
        'credit_card': Payment.PaymentMethod.CREDIT_CARD,
        'debit_card': Payment.PaymentMethod.DEBIT_CARD,
        'bank_transfer': Payment.PaymentMethod.PIX,  # PIX é um tipo de transferência
        'ticket': Payment.PaymentMethod.BANK_SLIP,
    }
    return method_map.get(payment_type_id, Payment.PaymentMethod.PIX)

