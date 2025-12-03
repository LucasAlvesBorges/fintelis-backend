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
    Processa notificação de pagamento de assinatura.
    """
    try:
        # Buscar pagamento no Mercado Pago
        mp_service = get_mercadopago_service()
        # Note: Usar sdk.payment().get(payment_id) para buscar dados do pagamento
        
        # Aqui você pode:
        # 1. Registrar o pagamento no modelo Payment
        # 2. Atualizar a data de expiração da assinatura
        # 3. Enviar notificação para o usuário
        
        print(f"Pagamento recebido: {payment_id}")
    
    except Exception as e:
        print(f"Erro ao processar notificação de pagamento: {str(e)}")
        raise

