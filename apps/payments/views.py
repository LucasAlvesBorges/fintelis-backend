import logging
import traceback

from django.conf import settings

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

    @action(detail=False, methods=["post"], url_path="create-pix")
    def create_pix_payment(self, request):
        """
        Cria um pagamento único via PIX no Mercado Pago.
        Não é recorrente - requer renovação manual.

        POST /api/v1/payments/subscriptions/create-pix/
        Body: {
            "company_id": "uuid",
            "plan_type": "monthly",
            "payer_email": "email@example.com",
            "billing_day": 10
        }
        """
        company_id = request.data.get("company_id")
        plan_type = request.data.get("plan_type")
        # Usar email do usuário logado, não do request
        payer_email = (
            request.user.email
            if request.user.is_authenticated
            else request.data.get("payer_email")
        )
        billing_day = request.data.get("billing_day", 10)

        if not all([company_id, plan_type]):
            return Response(
                {"error": "company_id e plan_type são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not payer_email:
            return Response(
                {
                    "error": "Email do pagador é obrigatório. Faça login ou forneça payer_email."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Verificar se empresa existe
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                return Response(
                    {"error": "Empresa não encontrada"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            except Exception as e:
                return Response(
                    {"error": f"Erro ao buscar empresa: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Obter configuração do plano
            try:
                config = SubscriptionPlanType.get_config(
                    plan_type, billing_day=billing_day
                )
                if not config:
                    return Response(
                        {
                            "error": f'Plano "{plan_type}" não encontrado. Planos disponíveis: monthly, quarterly, semiannual, annual'
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception as e:
                return Response(
                    {"error": f"Erro ao obter configuração do plano: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Criar pagamento PIX no Mercado Pago
            try:
                mp_service = get_mercadopago_service()
            except ValueError as e:
                # Erro específico de configuração do Mercado Pago
                error_msg = str(e)
                if "MERCADOPAGO_ACCESS_TOKEN" in error_msg:
                    return Response(
                        {
                            "error": "MERCADOPAGO_ACCESS_TOKEN não configurado no ambiente. Configure a variável de ambiente MERCADOPAGO_ACCESS_TOKEN."
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                return Response(
                    {"error": f"Erro de configuração do Mercado Pago: {error_msg}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            except Exception as e:
                return Response(
                    {"error": f"Erro ao inicializar serviço Mercado Pago: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Criar pagamento no Mercado Pago
            try:
                logger.info(
                    f'Criando pagamento PIX: amount={config["amount"]}, email={payer_email}'
                )
                mp_response = mp_service.create_payment(
                    transaction_amount=config["amount"],
                    description=config["reason"],
                    payment_method_id="pix",
                    payer_email=payer_email,
                )
                logger.info(
                    f'Resposta do Mercado Pago recebida: {mp_response.get("id") if mp_response else "None"}'
                )
                # Log completo da resposta para debug (apenas em desenvolvimento)
                if settings.DEBUG:
                    import json

                    logger.debug(
                        f"Resposta completa do Mercado Pago: {json.dumps(mp_response, indent=2, default=str)}"
                    )
            except Exception as e:
                logger.error(
                    f"Erro ao criar pagamento no Mercado Pago: {str(e)}", exc_info=True
                )
                return Response(
                    {"error": f"Erro ao criar pagamento no Mercado Pago: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validar resposta do Mercado Pago
            if not mp_response:
                logger.error("Resposta do Mercado Pago está vazia")
                return Response(
                    {"error": "Resposta vazia do Mercado Pago"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            if "id" not in mp_response:
                logger.error(f"Resposta do Mercado Pago não contém ID: {mp_response}")
                return Response(
                    {
                        "error": f"Resposta inválida do Mercado Pago. Resposta recebida: {str(mp_response)[:200]}"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Extrair dados do PIX antes de salvar
            pix_code = None
            qr_code_base64 = None
            try:
                point_of_interaction = mp_response.get("point_of_interaction", {})
                transaction_data = point_of_interaction.get("transaction_data", {})
                pix_code = transaction_data.get("qr_code")
                qr_code_base64 = transaction_data.get("qr_code_base64")

                logger.info(
                    f"Dados PIX extraídos: pix_code={bool(pix_code)}, qr_code_base64={bool(qr_code_base64)}"
                )
            except Exception as e:
                logger.error(f"Erro ao extrair dados PIX: {str(e)}", exc_info=True)
                # Continuar mesmo sem dados PIX, mas logar o erro

            # Salvar pagamento no banco
            try:
                # Verificar se já existe um pagamento com esse ID
                existing_payment = Payment.objects.filter(
                    payment_id=str(mp_response["id"])
                ).first()
                if existing_payment:
                    logger.warning(
                        f'Pagamento com ID {mp_response["id"]} já existe. Retornando existente.'
                    )
                    payment = existing_payment
                else:
                    payment = Payment.objects.create(
                        company=company,
                        payment_id=str(mp_response["id"]),
                        amount=config["amount"],
                        subscription_plan=plan_type,
                        payment_method=Payment.PaymentMethod.PIX,
                        status=Payment.Status.PENDING,
                        pix_code=pix_code,
                        gateway_response=mp_response,
                    )
                    logger.info(f"Pagamento salvo no banco: {payment.id}")
            except Exception as e:
                logger.error(
                    f"Erro ao salvar pagamento no banco: {str(e)}", exc_info=True
                )
                error_msg = str(e)
                # Verificar se é erro de duplicação
                if (
                    "unique constraint" in error_msg.lower()
                    or "duplicate" in error_msg.lower()
                ):
                    logger.warning(
                        f"Pagamento duplicado detectado, tentando buscar existente"
                    )
                    try:
                        payment = Payment.objects.get(payment_id=str(mp_response["id"]))
                        logger.info(f"Pagamento existente encontrado: {payment.id}")
                    except Payment.DoesNotExist:
                        return Response(
                            {"error": f"Erro ao salvar pagamento: {error_msg}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                else:
                    return Response(
                        {"error": f"Erro ao salvar pagamento: {error_msg}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            # Extrair dados do PIX
            pix_data = mp_response.get("point_of_interaction", {}).get(
                "transaction_data", {}
            )

            return Response(
                {
                    "payment_id": str(payment.id),
                    "mercadopago_payment_id": mp_response["id"],
                    "status": mp_response.get("status", "pending"),
                    "pix_code": pix_data.get("qr_code"),
                    "qr_code_base64": pix_data.get("qr_code_base64"),
                    "expiration_date": mp_response.get("date_of_expiration"),
                    "amount": float(config["amount"]),
                    "description": config["reason"],
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            # Captura qualquer erro não tratado acima
            error_trace = traceback.format_exc()
            logger.error(
                f"Erro inesperado ao criar pagamento PIX: {str(e)}\n{error_trace}"
            )

            return Response(
                {
                    "error": f"Erro inesperado ao processar pagamento. Verifique os logs do servidor para mais detalhes."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False, methods=["get"], url_path="check-payment/(?P<payment_id>[^/.]+)"
    )
    def check_payment_status(self, request, payment_id=None):
        """
        Verifica o status de um pagamento PIX.

        GET /api/v1/payments/subscriptions/check-payment/{payment_id}/
        """
        try:
            payment = Payment.objects.get(pk=payment_id)

            # Buscar status atualizado no Mercado Pago
            mp_service = get_mercadopago_service()
            mp_response = mp_service.get_payment(payment.payment_id)

            # Atualizar status local se mudou
            new_status = mp_response["status"]
            if new_status == "approved" and payment.status != Payment.Status.COMPLETED:
                payment.status = Payment.Status.COMPLETED
                payment.transaction_id = mp_response.get("id")
                payment.save()

                # Ativar assinatura da empresa via Subscription
                # Buscar subscription relacionada ao payment
                company = payment.company
                
                # Buscar subscription mais recente da empresa
                from .models import Subscription
                subscription = Subscription.objects.filter(
                    company=company,
                    plan__subscription_plan_type=payment.subscription_plan,
                    status__in=[Subscription.Status.AUTHORIZED, Subscription.Status.PENDING]
                ).order_by('-created_at').first()
                
                from django.utils import timezone
                
                if subscription:
                    # Se subscription existe, ativar
                    if not subscription.start_date:
                        subscription.start_date = timezone.now()
                    if subscription.status != Subscription.Status.AUTHORIZED:
                        subscription.status = Subscription.Status.AUTHORIZED
                    subscription.activate()
                    subscription.save()
                else:
                    # Se não tem subscription, apenas marcar como ativa (será criada pelo webhook)
                    company.subscription_active = True
                    if not company.subscription_started_at:
                        company.subscription_started_at = timezone.now()
                    company.save()

            return Response(
                {
                    "payment_id": str(payment.id),
                    "status": payment.status,
                    "mercadopago_status": new_status,
                    "amount": float(payment.amount),
                    "paid_at": mp_response.get("date_approved"),
                }
            )

        except Payment.DoesNotExist:
            return Response(
                {"error": "Pagamento não encontrado"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentViewSet(viewsets.ViewSet):
    """
    ViewSet para gerenciar pagamentos e assinaturas.
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="create-intent")
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

        return Response(
            {
                "payment_id": "mock_payment_id_12345",
                "status": "pending",
                "amount": serializer.validated_data["amount"],
                "subscription_plan": serializer.validated_data["subscription_plan"],
                "pix_code": "MOCK_PIX_CODE_AQUI",  # QR Code ou copia-e-cola
                "expires_at": "2025-12-04T00:00:00Z",  # Expira em 24h
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="confirm")
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
        # Nota: Atualização de Company.subscription_active e subscription_expires_at
        # é feita automaticamente via webhook quando o pagamento é aprovado

        return Response(
            {
                "message": "Payment confirmed successfully",
                "payment_id": serializer.validated_data["payment_id"],
                "status": serializer.validated_data["status"],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="status/(?P<payment_id>[^/.]+)")
    def payment_status(self, request, payment_id=None):
        """
        Consulta o status de um pagamento.

        GET /api/v1/payments/status/{payment_id}/
        """
        # TODO: Consultar status real no gateway de pagamento

        return Response(
            {
                "payment_id": payment_id,
                "status": "pending",  # pending, completed, failed, expired
                "amount": "500.00",
                "created_at": "2025-12-03T12:00:00Z",
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="history")
    def payment_history(self, request):
        """
        Lista histórico de pagamentos do usuário.

        GET /api/v1/payments/history/
        """
        # TODO: Buscar histórico real de pagamentos do banco de dados

        return Response(
            {
                "payments": [
                    {
                        "payment_id": "pay_001",
                        "amount": "500.00",
                        "status": "completed",
                        "subscription_plan": "monthly",
                        "created_at": "2025-11-03T12:00:00Z",
                        "completed_at": "2025-11-03T12:30:00Z",
                    },
                    {
                        "payment_id": "pay_002",
                        "amount": "1500.00",
                        "status": "completed",
                        "subscription_plan": "quarterly",
                        "created_at": "2025-10-03T12:00:00Z",
                        "completed_at": "2025-10-03T12:45:00Z",
                    },
                ]
            },
            status=status.HTTP_200_OK,
        )
