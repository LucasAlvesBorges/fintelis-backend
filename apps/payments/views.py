from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.companies.models import Company
from .models import SubscriptionPlan, SubscriptionPlanType, Subscription, Payment
from .serializers import (
    SubscriptionPlanSerializer,
    CreateSubscriptionPlanSerializer,
    SubscriptionSerializer,
    CreateSubscriptionSerializer,
    PaymentSerializer,
    PaymentIntentSerializer,
    PaymentConfirmationSerializer,
)
from .mercadopago_service import get_mercadopago_service


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para visualizar planos de assinatura.
    """
    queryset = SubscriptionPlan.objects.filter(status='active')
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'], url_path='available', permission_classes=[])
    def available_plans(self, request):
        """
        Retorna os tipos de planos disponíveis com suas configurações.
        Não requer autenticação.
        
        GET /api/v1/payments/plans/available/
        """
        plans = []
        for plan_type in SubscriptionPlanType:
            config = SubscriptionPlanType.get_config(plan_type.value)
            
            # Mapear periodo em português
            period_map = {
                'monthly': 'mês',
                'quarterly': 'trimestre',
                'semiannual': 'semestre',
                'annual': 'ano'
            }
            
            # Mapear descrição
            description_map = {
                'monthly': 'Ideal para começar',
                'quarterly': 'Melhor custo-benefício',
                'semiannual': 'Para o longo prazo',
                'annual': 'Máxima economia'
            }
            
            # Mapear features
            features_map = {
                'monthly': ['Acesso completo', 'Suporte por email', 'Atualizações incluídas'],
                'quarterly': ['Acesso completo', 'Suporte prioritário', 'Atualizações incluídas'],
                'semiannual': ['Acesso completo', 'Suporte prioritário', 'Atualizações incluídas'],
                'annual': ['Acesso completo', 'Suporte VIP', 'Atualizações incluídas']
            }
            
            plans.append({
                'id': plan_type.value,
                'name': plan_type.label,
                'price': str(int(config['amount'])),  # Remove decimais para display
                'period': period_map.get(plan_type.value, ''),
                'description': description_map.get(plan_type.value, ''),
                'features': features_map.get(plan_type.value, []),
                'popular': plan_type.value == 'quarterly',  # Trimestral é o popular
                'amount': float(config['amount']),
                'frequency': config['frequency'],
                'duration_days': config['duration_days']
            })
        
        return Response(plans)
    
    @action(detail=False, methods=['post'], url_path='create')
    def create_plan(self, request):
        """
        Cria um novo plano de assinatura no Mercado Pago.
        
        POST /api/v1/payments/plans/create/
        Body: {
            "subscription_plan_type": "monthly",
            "back_url": "https://yoursite.com/success"
        }
        """
        serializer = CreateSubscriptionPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan_type = serializer.validated_data['subscription_plan_type']
        back_url = serializer.validated_data['back_url']
        
        # Obter configuração centralizada do plano
        config = SubscriptionPlanType.get_config(plan_type)
        
        try:
            # Criar plano no Mercado Pago
            mp_service = get_mercadopago_service()
            mp_response = mp_service.create_preapproval_plan(
                reason=config['reason'],
                transaction_amount=config['amount'],
                frequency=config['frequency'],
                frequency_type=config['frequency_type'],
                billing_day=config['billing_day'],
                back_url=back_url,
                free_trial_frequency=15,  # 15 dias de trial
                free_trial_frequency_type='days',
            )
            
            # Salvar plano no banco de dados
            plan = SubscriptionPlan.objects.create(
                preapproval_plan_id=mp_response['id'],
                reason=config['reason'],
                subscription_plan_type=plan_type,
                transaction_amount=config['amount'],
                currency_id='BRL',
                frequency=config['frequency'],
                frequency_type=config['frequency_type'],
                billing_day=config['billing_day'],
                free_trial_frequency=15,
                free_trial_frequency_type='days',
                init_point=mp_response['init_point'],
                back_url=back_url,
                status='active',
                mercadopago_response=mp_response,
            )
            
            return Response(
                SubscriptionPlanSerializer(plan).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para gerenciar assinaturas.
    """
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtra assinaturas do usuário autenticado."""
        user = self.request.user
        company_ids = user.memberships.values_list('company_id', flat=True)
        return Subscription.objects.filter(company_id__in=company_ids)
    
    @action(detail=False, methods=['post'], url_path='create')
    def create_subscription(self, request):
        """
        Cria uma nova assinatura no Mercado Pago.
        
        POST /api/v1/payments/subscriptions/create/
        Body: {
            "company_id": "uuid",
            "plan_id": "uuid",
            "payer_email": "email@example.com",
            "card_token_id": "token_123" (opcional)
        }
        """
        serializer = CreateSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        company_id = serializer.validated_data['company_id']
        plan_id = serializer.validated_data['plan_id']
        payer_email = serializer.validated_data['payer_email']
        card_token_id = serializer.validated_data.get('card_token_id')
        
        try:
            # Verificar se empresa existe
            company = Company.objects.get(pk=company_id)
            plan = SubscriptionPlan.objects.get(pk=plan_id)
            
            # Criar assinatura no Mercado Pago
            mp_service = get_mercadopago_service()
            mp_response = mp_service.create_preapproval(
                preapproval_plan_id=plan.preapproval_plan_id,
                payer_email=payer_email,
                card_token_id=card_token_id,
            )
            
            # Salvar assinatura no banco de dados
            subscription = Subscription.objects.create(
                company=company,
                plan=plan,
                preapproval_id=mp_response['id'],
                payer_email=payer_email,
                status=mp_response.get('status', 'pending'),
                mercadopago_response=mp_response,
            )
            
            # Atualizar empresa com ID do plano
            company.mercadopago_preapproval_plan_id = plan.preapproval_plan_id
            company.mercadopago_subscription_id = mp_response['id']
            company.save()
            
            return Response(
                {
                    'subscription': SubscriptionSerializer(subscription).data,
                    'init_point': mp_response.get('init_point'),
                },
                status=status.HTTP_201_CREATED
            )
        
        except Company.DoesNotExist:
            return Response(
                {'error': 'Empresa não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': 'Plano não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_subscription(self, request, pk=None):
        """
        Cancela uma assinatura.
        
        POST /api/v1/payments/subscriptions/{id}/cancel/
        """
        subscription = self.get_object()
        
        try:
            # Cancelar no Mercado Pago
            mp_service = get_mercadopago_service()
            mp_service.update_preapproval(
                preapproval_id=subscription.preapproval_id,
                status='cancelled',
            )
            
            # Atualizar no banco
            subscription.cancel()
            
            return Response(
                {'message': 'Assinatura cancelada com sucesso'},
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PaymentViewSet(viewsets.ViewSet):
    """
    ViewSet para gerenciar pagamentos e assinaturas.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='create-intent')
    def create_payment_intent(self, request):
        """
        Cria uma intenção de pagamento para assinatura.
        
        POST /api/v1/payments/create-intent/
        Body: {
            "company_id": "uuid",
            "amount": "500.00",
            "subscription_plan": "monthly"
        }
        """
        serializer = PaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # TODO: Integrar com gateway de pagamento (PIX, cartão, etc.)
        # Por enquanto, apenas retorna dados mockados
        
        return Response({
            'payment_id': 'mock_payment_id_12345',
            'status': 'pending',
            'amount': serializer.validated_data['amount'],
            'subscription_plan': serializer.validated_data['subscription_plan'],
            'pix_code': 'MOCK_PIX_CODE_AQUI',  # QR Code ou copia-e-cola
            'expires_at': '2025-12-04T00:00:00Z',  # Expira em 24h
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='confirm')
    def confirm_payment(self, request):
        """
        Confirma um pagamento realizado.
        
        POST /api/v1/payments/confirm/
        Body: {
            "payment_id": "payment_123",
            "status": "completed",
            "transaction_id": "txn_456"
        }
        """
        serializer = PaymentConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # TODO: Validar pagamento com gateway
        # TODO: Atualizar Company.subscription_active e subscription_expires_at
        
        return Response({
            'message': 'Payment confirmed successfully',
            'payment_id': serializer.validated_data['payment_id'],
            'status': serializer.validated_data['status'],
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='status/(?P<payment_id>[^/.]+)')
    def payment_status(self, request, payment_id=None):
        """
        Consulta o status de um pagamento.
        
        GET /api/v1/payments/status/{payment_id}/
        """
        # TODO: Consultar status real no gateway de pagamento
        
        return Response({
            'payment_id': payment_id,
            'status': 'pending',  # pending, completed, failed, expired
            'amount': '500.00',
            'created_at': '2025-12-03T12:00:00Z',
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='history')
    def payment_history(self, request):
        """
        Lista histórico de pagamentos do usuário.
        
        GET /api/v1/payments/history/
        """
        # TODO: Buscar histórico real de pagamentos do banco de dados
        
        return Response({
            'payments': [
                {
                    'payment_id': 'pay_001',
                    'amount': '500.00',
                    'status': 'completed',
                    'subscription_plan': 'monthly',
                    'created_at': '2025-11-03T12:00:00Z',
                    'completed_at': '2025-11-03T12:30:00Z',
                },
                {
                    'payment_id': 'pay_002',
                    'amount': '1500.00',
                    'status': 'completed',
                    'subscription_plan': 'quarterly',
                    'created_at': '2025-10-03T12:00:00Z',
                    'completed_at': '2025-10-03T12:45:00Z',
                },
            ]
        }, status=status.HTTP_200_OK)
