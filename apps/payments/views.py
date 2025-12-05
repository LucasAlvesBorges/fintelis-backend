import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.companies.models import Company
from .models import SubscriptionPlan, SubscriptionPlanType, Subscription
from .serializers import (
    SubscriptionPlanSerializer,
    CreateSubscriptionPlanSerializer,
    SubscriptionSerializer,
    CreateSubscriptionSerializer,
)
from .mercadopago_service import get_mercadopago_service

logger = logging.getLogger(__name__)


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para visualizar planos de assinatura.
    """

    queryset = SubscriptionPlan.objects.filter(status="active")
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="available", permission_classes=[])
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
                "monthly": "mês",
                "quarterly": "trimestre",
                "semiannual": "semestre",
                "annual": "ano",
            }

            # Mapear descrição
            description_map = {
                "monthly": "Ideal para começar",
                "quarterly": "Melhor custo-benefício",
                "semiannual": "Para o longo prazo",
                "annual": "Máxima economia",
            }

            # Mapear features
            features_map = {
                "monthly": [
                    "Acesso completo",
                    "Suporte por email",
                    "Atualizações incluídas",
                ],
                "quarterly": [
                    "Acesso completo",
                    "Suporte prioritário",
                    "Atualizações incluídas",
                ],
                "semiannual": [
                    "Acesso completo",
                    "Suporte prioritário",
                    "Atualizações incluídas",
                ],
                "annual": ["Acesso completo", "Suporte VIP", "Atualizações incluídas"],
            }

            plans.append(
                {
                    "id": plan_type.value,
                    "name": plan_type.label,
                    "price": str(int(config["amount"])),  # Remove decimais para display
                    "period": period_map.get(plan_type.value, ""),
                    "description": description_map.get(plan_type.value, ""),
                    "features": features_map.get(plan_type.value, []),
                    "popular": plan_type.value == "quarterly",  # Trimestral é o popular
                    "amount": float(config["amount"]),
                    "frequency": config["frequency"],
                    "duration_days": config["duration_days"],
                }
            )

        return Response(plans)

    @action(detail=False, methods=["post"], url_path="create")
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

        plan_type = serializer.validated_data["subscription_plan_type"]
        back_url = serializer.validated_data["back_url"]
        billing_day = serializer.validated_data.get("billing_day", 10)

        # Obter configuração centralizada do plano com billing_day dinâmico
        config = SubscriptionPlanType.get_config(plan_type, billing_day=billing_day)

        try:
            # Criar plano no Mercado Pago
            mp_service = get_mercadopago_service()
            mp_response = mp_service.create_preapproval_plan(
                reason=config["reason"],
                transaction_amount=config["amount"],
                frequency=config["frequency"],
                frequency_type=config["frequency_type"],
                billing_day=config["billing_day"],
                back_url=back_url,
                free_trial_frequency=15,  # 15 dias de trial
                free_trial_frequency_type="days",
            )

            # Salvar plano no banco de dados
            plan = SubscriptionPlan.objects.create(
                preapproval_plan_id=mp_response["id"],
                reason=config["reason"],
                subscription_plan_type=plan_type,
                transaction_amount=config["amount"],
                currency_id="BRL",
                frequency=config["frequency"],
                frequency_type=config["frequency_type"],
                billing_day=config["billing_day"],
                free_trial_frequency=15,
                free_trial_frequency_type="days",
                init_point=mp_response["init_point"],
                back_url=back_url,
                status="active",
                mercadopago_response=mp_response,
            )

            return Response(
                SubscriptionPlanSerializer(plan).data, status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para gerenciar assinaturas.
    """

    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra assinaturas do usuário autenticado."""
        user = self.request.user
        company_ids = user.memberships.values_list("company_id", flat=True)
        return Subscription.objects.filter(company_id__in=company_ids)

    @action(detail=False, methods=["post"], url_path="create")
    def create_subscription(self, request):
        """
        Cria uma nova assinatura no Mercado Pago.
        Redireciona o usuário para a página de checkout do Mercado Pago.

        POST /api/v1/payments/subscriptions/create/
        Body: {
            "company_id": "uuid",
            "plan_id": "uuid",
            "payer_email": "email@example.com"
        }
        """
        logger.info(
            f"Recebida requisição de criação de assinatura: {request.data.keys()}"
        )

        # Criar serializer sem card_data (não é mais necessário)
        serializer_data = request.data.copy()
        # Remover card_data se existir (não será mais usado)
        serializer_data.pop("card_data", None)
        
        # Criar serializer simplificado
        from rest_framework import serializers
        class SimpleSubscriptionSerializer(serializers.Serializer):
            company_id = serializers.UUIDField()
            plan_id = serializers.CharField()
            payer_email = serializers.EmailField(required=False)

        serializer = SimpleSubscriptionSerializer(data=serializer_data)
        if not serializer.is_valid():
            logger.error(f"Erro de validação: {serializer.errors}")
            return Response(
                {"error": "Dados inválidos", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company_id = serializer.validated_data["company_id"]
        plan_id = serializer.validated_data["plan_id"]
        
        # Usar email do usuário logado se disponível, senão usar do request
        payer_email = None
        if request.user.is_authenticated and request.user.email:
            payer_email = request.user.email

        if not payer_email:
            payer_email = serializer.validated_data.get("payer_email")
        if not payer_email:
            return Response(
                {
                    "error": "Email do pagador é obrigatório. Faça login ou forneça payer_email."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Verificar se empresa existe
            company = Company.objects.get(pk=company_id)

            # Verificar se usuário tem acesso à empresa
            if request.user.is_authenticated:
                from apps.companies.models import Membership

                has_access = Membership.objects.filter(
                    user=request.user, company=company
                ).exists()
                if not has_access:
                    return Response(
                        {
                            "error": "Você não tem permissão para criar assinatura para esta empresa."
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

            # Buscar plano - pode ser UUID ou plan_type (monthly, quarterly, etc)
            plan = None

            # Verificar se é um tipo de plano válido (string)
            valid_plan_types = ["monthly", "quarterly", "semiannual", "annual"]
            if plan_id in valid_plan_types:
                # Buscar por subscription_plan_type
                plan = SubscriptionPlan.objects.filter(
                    subscription_plan_type=plan_id, status="active"
                ).first()
            else:
                # Tentar buscar por UUID
                try:
                    plan = SubscriptionPlan.objects.get(pk=plan_id, status="active")
                except (SubscriptionPlan.DoesNotExist, ValueError):
                    pass

            if not plan:
                logger.error(f"Plano não encontrado: {plan_id}")
                return Response(
                    {
                        "error": f'Plano "{plan_id}" não encontrado no banco de dados.',
                        "hint": "Execute: docker-compose exec app python manage.py create_subscription_plans",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Tentar criar preapproval sem card_token_id para obter init_point personalizado
            # Se falhar, usar o init_point do plano diretamente
            mp_service = get_mercadopago_service()
            
            # Obter URL de retorno do frontend
            from django.conf import settings
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            back_url = f"{frontend_url}/payment/success"
            
            init_point = None
            subscription = None
            
            # Verificar se já existe uma subscription pendente para esta empresa e plano
            # Buscar por preapproval_id que começa com "pending_" (subscriptions temporárias)
            existing_pending = Subscription.objects.filter(
                company=company,
                plan=plan,
                external_reference=str(company.id),
                status="pending",
                preapproval_id__startswith="pending_"
            ).order_by("-created_at").first()
            
            # Verificar se o plano existe no Mercado Pago antes de tentar criar preapproval
            # Se o plano não existir, usar init_point diretamente sem tentar criar preapproval
            plan_exists = False
            try:
                mp_plan_data = mp_service.get_preapproval_plan(plan.preapproval_plan_id)
                plan_exists = True
                logger.info(f"Plano {plan.preapproval_plan_id} encontrado no Mercado Pago")
            except Exception as e:
                error_msg = str(e)
                # Verificar se é erro 404 (plano não existe)
                if "404" in error_msg or "does not exist" in error_msg.lower() or "not found" in error_msg.lower() or "template" in error_msg.lower():
                    logger.info(f"Plano {plan.preapproval_plan_id} não existe no Mercado Pago. Usando init_point do plano diretamente.")
                    plan_exists = False
                else:
                    # Outro tipo de erro - pode ser temporário, mas vamos usar fallback por segurança
                    logger.warning(f"Erro ao verificar plano {plan.preapproval_plan_id} no Mercado Pago: {error_msg}. Usando init_point do plano.")
                    plan_exists = False
            
            # Tentar criar preapproval sem card_token_id apenas se o plano existir
            if plan_exists:
                try:
                    logger.info(f"Tentando criar preapproval para plano {plan.preapproval_plan_id}, empresa {company.id}")
                    mp_response = mp_service.create_preapproval(
                        preapproval_plan_id=plan.preapproval_plan_id,
                        payer_email=payer_email,
                        card_token_id=None,  # Sem token
                        back_url=back_url,
                        external_reference=str(company.id),
                    )
                    
                    init_point = mp_response.get("init_point")
                    if init_point:
                        logger.info(f"init_point obtido do preapproval: {init_point}")
                        # Atualizar subscription existente ou criar nova
                        if existing_pending:
                            existing_pending.preapproval_id = mp_response["id"]
                            existing_pending.payer_email = payer_email
                            existing_pending.status = mp_response.get("status", "pending")
                            existing_pending.mercadopago_response = mp_response
                            existing_pending.save()
                            subscription = existing_pending
                            logger.info(f"Subscription existente atualizada: {subscription.id}")
                        else:
                            # Criar subscription com o preapproval_id real
                            from django.utils import timezone
                            subscription = Subscription.objects.create(
                                company=company,
                                plan=plan,
                                preapproval_id=mp_response["id"],
                                external_reference=str(company.id),
                                payer_email=payer_email,
                                status=mp_response.get("status", "pending"),
                                mercadopago_response=mp_response,
                            )
                            logger.info(f"Subscription criada: {subscription.id}")
                    else:
                        logger.warning("Preapproval criado mas init_point não retornado, usando init_point do plano")
                except Exception as e:
                    error_msg = str(e)
                    # Verificar se é erro relacionado ao plano não existir
                    if "does not exist" in error_msg.lower() or "404" in error_msg or "not found" in error_msg.lower():
                        logger.warning(f"Plano não existe no Mercado Pago. Usando init_point do plano diretamente.")
                    elif "card_token_id" in error_msg.lower():
                        # Erro esperado quando não há card_token_id - sistema usa fallback normalmente
                        logger.debug(f"Preapproval sem card_token_id não suportado, usando init_point do plano (comportamento esperado): {error_msg}")
                    else:
                        logger.warning(f"Erro ao criar preapproval sem card_token_id: {error_msg}")
                    plan_exists = False  # Marcar como não existente para usar fallback
            
            # Fallback: usar init_point do plano
            if not init_point:
                logger.info("Usando init_point do plano diretamente")
                
                if not plan.init_point:
                    logger.error(f"Plano {plan.id} não tem init_point configurado")
                    return Response(
                        {"error": "Plano não configurado corretamente. Entre em contato com o suporte."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                
                init_point = plan.init_point
                
                # Reutilizar subscription pendente existente ou criar nova com ID único
                if existing_pending:
                    subscription = existing_pending
                    logger.info(f"Reutilizando subscription pendente existente: {subscription.id}")
                else:
                    # Criar subscription temporária com ID único
                    import uuid
                    from django.utils import timezone
                    temp_id = f"pending_{uuid.uuid4()}"
                    subscription = Subscription.objects.create(
                        company=company,
                        plan=plan,
                        preapproval_id=temp_id,  # ID único temporário
                        external_reference=str(company.id),
                        payer_email=payer_email,
                        status="pending",
                        mercadopago_response={},
                    )
                    logger.info(f"Subscription temporária criada: {subscription.id} com preapproval_id={temp_id}")
            
            if not init_point:
                logger.error("Não foi possível obter init_point")
                return Response(
                    {"error": "Erro ao gerar link de checkout. Tente novamente."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "subscription": SubscriptionSerializer(subscription).data if subscription else None,
                    "init_point": init_point,
                    "requires_redirect": True,
                    "message": "Redirecionando para checkout do Mercado Pago...",
                    "plan_id": str(plan.id),
                    "company_id": str(company.id),
                },
                status=status.HTTP_200_OK,
            )

        except Company.DoesNotExist:
            return Response(
                {"error": "Empresa não encontrada"}, status=status.HTTP_404_NOT_FOUND
            )
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {"error": "Plano não encontrado"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erro ao criar assinatura: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="cancel")
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
                status="cancelled",
            )

            # Atualizar no banco
            subscription.cancel()

            return Response(
                {"message": "Assinatura cancelada com sucesso"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate_subscription(self, request, pk=None):
        """
        Reativa uma assinatura cancelada.

        POST /api/v1/payments/subscriptions/{id}/reactivate/
        """
        subscription = self.get_object()

        if subscription.status != subscription.Status.CANCELLED:
            return Response(
                {"error": "Apenas assinaturas canceladas podem ser reativadas"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Reativar no Mercado Pago
            mp_service = get_mercadopago_service()
            mp_service.update_preapproval(
                preapproval_id=subscription.preapproval_id,
                status="authorized",
            )

            # Reativar no banco
            subscription.status = subscription.Status.AUTHORIZED
            subscription.end_date = None
            subscription.save()

            # Reativar empresa se ainda está dentro do período de expiração
            from django.utils import timezone
            if subscription.company.subscription_expires_at and timezone.now() < subscription.company.subscription_expires_at:
                subscription.company.subscription_active = True
                subscription.company.save()
                # Usar método activate para garantir que tudo está correto
                subscription.activate()
            else:
                # Se expirou, apenas atualizar status da subscription
                # A empresa permanecerá inativa até novo pagamento
                pass

            return Response(
                {"message": "Assinatura reativada com sucesso"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Erro ao reativar assinatura: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
