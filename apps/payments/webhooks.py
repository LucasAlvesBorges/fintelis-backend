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


@api_view(["POST", "GET"])
@permission_classes([AllowAny])  # Mercado Pago não envia autenticação
def mercadopago_webhook(request):
    """
    Webhook para receber notificações do Mercado Pago.

    POST /api/v1/payments/webhook/mercadopago/
    GET /api/v1/payments/webhook/mercadopago/?type=payment&data.id=123

    Formatos suportados:
    1. Query params (GET): ?type=payment&data.id=123
    2. JSON body (POST): {"type": "payment", "data": {"id": "123"}}
    3. JSON body com action: {"action": "payment.created", "type": "payment", "data": {"id": "123"}}

    Tipos de notificação:
    - preapproval: Mudanças em assinaturas
    - authorized_payment: Pagamento autorizado
    - payment: Mudanças em pagamentos
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Log da requisição recebida
        logger.info(
            f"Webhook recebido: method={request.method}, data={request.data}, query_params={request.query_params}"
        )

        # Extrair dados da notificação
        # Formato 1: Query params (GET)
        notification_type = request.query_params.get("type")
        notification_id = request.query_params.get("data.id")

        # Formato 2: JSON body (POST)
        if not notification_type:
            notification_type = request.data.get("type")

        if not notification_id:
            # Tentar extrair do body em diferentes formatos
            data_obj = request.data.get("data", {})
            if isinstance(data_obj, dict):
                notification_id = data_obj.get("id")
            else:
                notification_id = request.data.get("data.id")

        # Se ainda não encontrou, tentar action (formato alternativo)
        if not notification_type and request.data.get("action"):
            action = request.data.get("action", "")
            if "payment" in action:
                notification_type = "payment"
            elif "preapproval" in action:
                notification_type = "preapproval"

        logger.info(
            f"Notificação extraída: type={notification_type}, id={notification_id}"
        )

        if not notification_type or not notification_id:
            logger.warning(
                f"Webhook incompleto: type={notification_type}, id={notification_id}"
            )
            return Response(
                {
                    "error": "Missing notification type or id",
                    "received_data": {
                        "type": notification_type,
                        "id": notification_id,
                        "body": request.data,
                        "query_params": dict(request.query_params),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Processar notificação de assinatura
        if notification_type in ["preapproval", "subscription_preapproval"]:
            logger.info(f"Processando notificação de assinatura: {notification_id}")
            handle_preapproval_notification(notification_id)

        # Processar notificação de pagamento
        # subscription_authorized_payment = pagamento autorizado de uma assinatura
        elif notification_type in [
            "authorized_payment",
            "payment",
            "subscription_authorized_payment",
        ]:
            logger.info(f"Processando notificação de pagamento: {notification_id}")
            # Para subscription_authorized_payment, o ID pode ser do preapproval, não do payment
            if notification_type == "subscription_authorized_payment":
                handle_subscription_authorized_payment(notification_id)
            else:
                handle_payment_notification(notification_id)
        else:
            logger.warning(f"Tipo de notificação desconhecido: {notification_type}")
            # Ainda retorna 200 OK para evitar reenvios
            return Response(
                {"status": "ok", "warning": f"Unknown type: {notification_type}"},
                status=status.HTTP_200_OK,
            )

        return Response({"status": "ok", "processed": True}, status=status.HTTP_200_OK)

    except Exception as e:
        # Log do erro (em produção, usar logging adequado)
        logger.error(f"Erro no webhook: {str(e)}", exc_info=True)
        return Response(
            {"error": str(e), "received_data": request.data},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def handle_preapproval_notification(preapproval_id: str):
    """
    Processa notificação de mudança em assinatura.
    """
    import logging
    from datetime import timedelta
    from django.utils import timezone
    from dateutil import parser

    logger = logging.getLogger(__name__)

    try:
        # Buscar assinatura no Mercado Pago
        mp_service = get_mercadopago_service()
        mp_data = mp_service.get_preapproval(preapproval_id)

        logger.info(f"Dados da assinatura do MP: {mp_data}")

        # Buscar ou criar assinatura no banco
        try:
            subscription = Subscription.objects.get(preapproval_id=preapproval_id)
            old_status = subscription.status
        except Subscription.DoesNotExist:
            # Tentar buscar subscription pendente de várias formas
            external_reference = mp_data.get("external_reference")
            preapproval_plan_id = mp_data.get("preapproval_plan_id")
            payer_email = mp_data.get("payer_email", "")
            subscription = None
            
            # Estratégia 1: Buscar por external_reference (se disponível)
            if external_reference:
                try:
                    subscription = Subscription.objects.filter(
                        external_reference=external_reference,
                        preapproval_id__startswith="pending_"
                    ).order_by("-created_at").first()
                    
                    if subscription:
                        logger.info(f"Subscription pendente encontrada por external_reference: {subscription.id}")
                        subscription.preapproval_id = preapproval_id
                        old_status = subscription.status
                except Exception as e:
                    logger.warning(f"Erro ao buscar subscription por external_reference: {str(e)}")
            
            # Estratégia 2: Buscar por preapproval_plan_id e payer_email (se não encontrou por external_reference)
            if not subscription and preapproval_plan_id and payer_email:
                try:
                    from .models import SubscriptionPlan
                    plan = SubscriptionPlan.objects.get(preapproval_plan_id=preapproval_plan_id)
                    
                    subscription = Subscription.objects.filter(
                        plan=plan,
                        payer_email=payer_email,
                        preapproval_id__startswith="pending_",
                        status="pending"
                    ).order_by("-created_at").first()
                    
                    if subscription:
                        logger.info(f"Subscription pendente encontrada por plano e email: {subscription.id}")
                        subscription.preapproval_id = preapproval_id
                        if external_reference:
                            subscription.external_reference = external_reference
                        old_status = subscription.status
                except Exception as e:
                    logger.warning(f"Erro ao buscar subscription por plano e email: {str(e)}")
            
            # Estratégia 3: Buscar apenas por preapproval_plan_id (última tentativa)
            if not subscription and preapproval_plan_id:
                try:
                    from .models import SubscriptionPlan
                    plan = SubscriptionPlan.objects.get(preapproval_plan_id=preapproval_plan_id)
                    
                    subscription = Subscription.objects.filter(
                        plan=plan,
                        preapproval_id__startswith="pending_",
                        status="pending"
                    ).order_by("-created_at").first()
                    
                    if subscription:
                        logger.info(f"Subscription pendente encontrada por plano: {subscription.id}")
                        subscription.preapproval_id = preapproval_id
                        if external_reference:
                            subscription.external_reference = external_reference
                        if payer_email:
                            subscription.payer_email = payer_email
                        old_status = subscription.status
                except Exception as e:
                    logger.warning(f"Erro ao buscar subscription por plano: {str(e)}")
            
            # Se não encontrou subscription pendente, tentar criar nova
            if not subscription:
                logger.info(f"Criando subscription para preapproval_id {preapproval_id}")
                
                # Buscar plano pelo preapproval_plan_id (obrigatório)
                if not preapproval_plan_id:
                    logger.error(f"preapproval_plan_id não encontrado no preapproval {preapproval_id}")
                    raise Exception("preapproval_plan_id é obrigatório para criar subscription")
                
                from .models import SubscriptionPlan
                try:
                    plan = SubscriptionPlan.objects.get(preapproval_plan_id=preapproval_plan_id)
                except SubscriptionPlan.DoesNotExist:
                    logger.error(f"Plano {preapproval_plan_id} não encontrado")
                    raise Exception(f"Plano {preapproval_plan_id} não encontrado")
                
                # Tentar buscar empresa pelo external_reference (se disponível)
                company = None
                if external_reference:
                    from apps.companies.models import Company
                    try:
                        company = Company.objects.get(id=external_reference)
                    except Company.DoesNotExist:
                        logger.warning(f"Empresa {external_reference} não encontrada, criando subscription sem empresa")
                
                # Se não tem external_reference, tentar buscar empresa mais recente que usa este plano
                if not company:
                    # Buscar subscriptions existentes deste plano para inferir a empresa
                    existing_subscriptions = Subscription.objects.filter(
                        plan=plan,
                        status__in=["authorized", "pending"]
                    ).order_by("-created_at")
                    
                    if existing_subscriptions.exists():
                        # Usar a empresa da subscription mais recente deste plano
                        company = existing_subscriptions.first().company
                        external_reference = str(company.id)
                        logger.info(f"Usando empresa inferida: {company.name} (ID: {company.id})")
                    else:
                        logger.error(f"Não foi possível determinar a empresa para o preapproval {preapproval_id}")
                        # Criar subscription sem empresa (será atualizada depois)
                        # Mas precisamos de uma empresa, então vamos buscar qualquer empresa ativa
                        from apps.companies.models import Company
                        company = Company.objects.filter(is_active=True).first()
                        if not company:
                            raise Exception("Nenhuma empresa encontrada para criar subscription")
                        logger.warning(f"Usando empresa padrão: {company.name} (ID: {company.id})")
                
                    # Criar subscription
                    mp_status = mp_data.get("status", "pending")
                    # Se status é authorized, definir start_date
                    start_date = None
                    if mp_status == "authorized":
                        start_date = timezone.now()
                    
                    subscription = Subscription.objects.create(
                        company=company,
                        plan=plan,
                        preapproval_id=preapproval_id,
                        external_reference=external_reference or str(company.id),
                        payer_email=payer_email,
                        status=mp_status,
                        start_date=start_date,
                        is_trial=False,  # Trial será criado via método create_trial
                        mercadopago_response=mp_data,
                    )
                    old_status = None  # Nova subscription, não tem status anterior
                    logger.info(f"Subscription criada: {subscription.id} para empresa {company.name}")
        
        subscription.status = mp_data.get("status", subscription.status)
        
        # Se status mudou para authorized e não tem start_date, definir agora
        if subscription.status == Subscription.Status.AUTHORIZED and not subscription.start_date:
            subscription.start_date = timezone.now()

        # Atualizar payer_email se vier preenchido
        mp_email = mp_data.get("payer_email")
        if mp_email and mp_email.strip():
            subscription.payer_email = mp_email

        # Extrair start_date de auto_recurring se não tiver
        auto_recurring = mp_data.get("auto_recurring", {})
        if not subscription.start_date and auto_recurring.get("start_date"):
            try:
                subscription.start_date = parser.parse(auto_recurring["start_date"])
                logger.info(f"Start date extraída: {subscription.start_date}")
            except Exception as e:
                logger.error(f"Erro ao fazer parse de start_date: {e}")

        # Atualizar/calcular next_payment_date
        mp_next_date = mp_data.get("next_payment_date")
        if mp_next_date:
            try:
                parsed_next_date = parser.parse(mp_next_date)
                # Se for no futuro, usar. Caso contrário, calcular baseado no plano
                if parsed_next_date > timezone.now():
                    subscription.next_payment_date = parsed_next_date
                else:
                    # Calcular baseado no plano
                    if subscription.start_date:
                        if subscription.plan.frequency_type == "months":
                            subscription.next_payment_date = (
                                subscription.start_date
                                + timedelta(days=subscription.plan.frequency * 30)
                            )
                        else:
                            subscription.next_payment_date = (
                                subscription.start_date
                                + timedelta(days=subscription.plan.frequency)
                            )
                logger.info(f"Next payment date: {subscription.next_payment_date}")
            except Exception as e:
                logger.error(f"Erro ao processar next_payment_date: {e}")

        # Atualizar end_date se disponível
        if mp_data.get("end_date"):
            try:
                subscription.end_date = parser.parse(mp_data["end_date"])
            except:
                pass

        subscription.mercadopago_response = mp_data
        subscription.save()

        logger.info(
            f"Assinatura atualizada: status={subscription.status}, start={subscription.start_date}, next={subscription.next_payment_date}"
        )

        # Se status mudou para autorizado, ativar assinatura
        if (
            subscription.status == Subscription.Status.AUTHORIZED
            and old_status != Subscription.Status.AUTHORIZED
        ):
            subscription.activate()  # Já atualiza subscription_expires_at na company
            logger.info(
                f"Assinatura {preapproval_id} ativada para empresa {subscription.company.name} até {subscription.expires_at}"
            )

        # Se status mudou para cancelado, desativar
        elif subscription.status == Subscription.Status.CANCELLED:
            subscription.cancel()
            logger.info(f"Assinatura {preapproval_id} cancelada")

    except Subscription.DoesNotExist:
        logger.error(f"Assinatura {preapproval_id} não encontrada no banco de dados")
    except Exception as e:
        logger.error(
            f"Erro ao processar notificação de assinatura: {str(e)}", exc_info=True
        )
        raise


def handle_subscription_authorized_payment(notification_id: str):
    """
    Processa notificação de pagamento autorizado de uma assinatura.
    O ID pode ser do preapproval (assinatura) ou do payment.
    Primeiro tenta buscar como payment, se não encontrar, busca como preapproval.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        mp_service = get_mercadopago_service()
        
        # Estratégia 1: Tentar buscar como payment primeiro
        try:
            mp_payment = mp_service.get_payment(notification_id)
            logger.info(f"ID {notification_id} é um payment. Processando como pagamento normal.")
            handle_payment_notification(notification_id)
            return
        except Exception as e:
            if (
                "404" in str(e)
                or "not_found" in str(e).lower()
                or "not found" in str(e).lower()
            ):
                logger.info(f"ID {notification_id} não é um payment. Tentando buscar como preapproval...")
            else:
                raise e
        
        # Estratégia 2: Buscar como preapproval e então buscar pagamentos relacionados
        try:
            preapproval_data = mp_service.get_preapproval(notification_id)
            preapproval_id = preapproval_data.get("id")
            status = preapproval_data.get("status")
            
            logger.info(f"Preapproval encontrado: {preapproval_id}, status: {status}")
            
            # Buscar subscription no banco
            try:
                subscription = Subscription.objects.get(preapproval_id=preapproval_id)
                logger.info(f"Subscription encontrada: {subscription.id} para empresa {subscription.company.name}")
                
                # Se a subscription está autorizada, buscar pagamentos recentes relacionados
                if status == "authorized":
                    # Buscar pagamentos recentes da empresa relacionados a esta subscription
                    from datetime import timedelta
                    recent_date = timezone.now() - timedelta(hours=24)
                    
                    # Buscar payment mais recente da empresa que ainda não foi processado
                    recent_payment = Payment.objects.filter(
                        company=subscription.company,
                        subscription_plan=subscription.plan.subscription_plan_type,
                        status__in=[Payment.Status.PENDING, Payment.Status.COMPLETED],
                        created_at__gte=recent_date
                    ).order_by("-created_at").first()
                    
                    if recent_payment:
                        logger.info(f"Payment recente encontrado: {recent_payment.payment_id}")
                        # Verificar status no Mercado Pago
                        try:
                            mp_payment = mp_service.get_payment(recent_payment.payment_id)
                            payment_status = mp_payment.get("status")
                            
                            if payment_status == "approved" and recent_payment.status != Payment.Status.COMPLETED:
                                # Atualizar payment e ativar assinatura
                                from .models import SubscriptionPlanType
                                
                                recent_payment.status = Payment.Status.COMPLETED
                                recent_payment.completed_at = timezone.now()
                                recent_payment.gateway_response = mp_payment
                                recent_payment.save()
                                
                                # Renovar assinatura se já está autorizada, senão ativar
                                if subscription.status == Subscription.Status.AUTHORIZED:
                                    expires_at = subscription.renew()
                                    logger.info(f"✅ Assinatura RENOVADA para empresa {subscription.company.name} até {expires_at} via subscription_authorized_payment")
                                    print(f"✅ Assinatura RENOVADA para empresa {subscription.company.name}")
                                else:
                                    # Se não está autorizada, ativar
                                    subscription.status = Subscription.Status.AUTHORIZED
                                    subscription.activate()
                                    subscription.save()
                                    logger.info(f"✅ Assinatura ativada para empresa {subscription.company.name} via subscription_authorized_payment")
                                    print(f"✅ Assinatura ativada para empresa {subscription.company.name}")
                        except Exception as e:
                            logger.warning(f"Erro ao buscar payment {recent_payment.payment_id}: {str(e)}")
                    else:
                        # Se não encontrou payment recente, apenas atualizar subscription
                        subscription.status = status
                        subscription.mercadopago_response = preapproval_data
                        subscription.save()
                        
                        if status == "authorized":
                            # Renovar se já está autorizada, senão ativar
                            if subscription.status == Subscription.Status.AUTHORIZED:
                                expires_at = subscription.renew()
                                logger.info(f"✅ Assinatura RENOVADA para empresa {subscription.company.name} até {expires_at} (sem payment específico)")
                                print(f"✅ Assinatura RENOVADA para empresa {subscription.company.name}")
                            else:
                                # Se não está autorizada, ativar
                                if not subscription.start_date:
                                    subscription.start_date = timezone.now()
                                subscription.status = Subscription.Status.AUTHORIZED
                                subscription.activate()
                                subscription.save()
                                logger.info(f"✅ Assinatura ativada para empresa {subscription.company.name} (sem payment específico)")
                                print(f"✅ Assinatura ativada para empresa {subscription.company.name}")
                else:
                    # Apenas atualizar status da subscription
                    subscription.status = status
                    subscription.mercadopago_response = preapproval_data
                    subscription.save()
                    logger.info(f"Status da subscription atualizado para: {status}")
                    
            except Subscription.DoesNotExist:
                logger.warning(f"Subscription com preapproval_id {preapproval_id} não encontrada no banco")
                # Chamar handle_preapproval_notification para criar/atualizar subscription
                handle_preapproval_notification(notification_id)
                
        except Exception as e:
            if (
                "404" in str(e)
                or "not_found" in str(e).lower()
                or "not found" in str(e).lower()
            ):
                logger.error(f"ID {notification_id} não encontrado nem como payment nem como preapproval")
            else:
                raise e
                
    except Exception as e:
        logger.error(f"Erro ao processar subscription_authorized_payment: {str(e)}", exc_info=True)
        raise


def handle_payment_notification(payment_id: str):
    """
    Processa notificação de pagamento (PIX, Cartão, etc).
    Atualiza status do pagamento e ativa assinatura quando aprovado.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Buscar pagamento no Mercado Pago
        mp_service = get_mercadopago_service()
        try:
            mp_payment = mp_service.get_payment(payment_id)
        except Exception as e:
            if (
                "404" in str(e)
                or "not_found" in str(e).lower()
                or "not found" in str(e).lower()
            ):
                logger.warning(
                    f"Pagamento {payment_id} não encontrado no Mercado Pago."
                )
                return
            raise e

        payment_status = mp_payment.get("status")
        mercadopago_payment_id = str(mp_payment.get("id"))
        operation_type = mp_payment.get("operation_type", "")

        logger.info(
            f"Processando pagamento {mercadopago_payment_id} - Status: {payment_status}, Operation: {operation_type}"
        )
        print(
            f"Processando pagamento {mercadopago_payment_id} - Status: {payment_status}"
        )

        # Extrair preapproval_id e external_reference do pagamento (antes de buscar no banco)
        preapproval_id = mp_payment.get("preapproval_id")
        if not preapproval_id:
            preapproval_id = mp_payment.get("metadata", {}).get("preapproval_id")
        if not preapproval_id:
            point_of_interaction = mp_payment.get("point_of_interaction", {})
            transaction_data = point_of_interaction.get("transaction_data", {})
            subscription_id_from_transaction = transaction_data.get("subscription_id")
            if subscription_id_from_transaction:
                preapproval_id = subscription_id_from_transaction
                logger.info(f"subscription_id encontrado no transaction_data: {preapproval_id}")
        
        external_reference = mp_payment.get("external_reference")
        
        # Variáveis para armazenar company e subscription encontradas
        company = None
        subscription = None

        # Buscar pagamento no banco de dados
        try:
            payment = Payment.objects.get(payment_id=mercadopago_payment_id)
            # Se payment já existe, obter company dele
            company = payment.company
            
            # Tentar buscar subscription relacionada se ainda não foi encontrada
            if preapproval_id:
                try:
                    subscription = Subscription.objects.get(preapproval_id=preapproval_id)
                    logger.info(f"Subscription encontrada para payment existente: {subscription.preapproval_id}")
                except Subscription.DoesNotExist:
                    pass
        except Payment.DoesNotExist:
            # Pagamento não existe localmente, pode ser de uma assinatura recorrente
            # Criar novo registro de pagamento
            print(
                f"Pagamento {mercadopago_payment_id} não encontrado, criando novo registro"
            )
            print(f"Dados do pagamento: {mp_payment}")

            # Tentar encontrar a empresa pela assinatura
            # preapproval_id e external_reference já foram extraídos acima

            # Estratégia 0: Buscar subscription diretamente pelo preapproval_id (se encontrado)
            if preapproval_id:
                try:
                    subscription = Subscription.objects.get(preapproval_id=preapproval_id)
                    company = subscription.company
                    logger.info(f"Subscription encontrada via preapproval_id: {preapproval_id}, empresa: {company.name}")
                    print(f"✅ Subscription encontrada: {preapproval_id}, empresa: {company.name}")
                except Subscription.DoesNotExist:
                    logger.warning(f"Subscription {preapproval_id} não encontrada no banco")
                    subscription = None

            # Estratégia 1: Buscar por external_reference + validar email (MAIS SEGURO)
            # External reference contém o UUID da empresa
            if not subscription and external_reference:
                try:
                    from apps.companies.models import Company

                    company = Company.objects.get(id=external_reference)

                    # VALIDAÇÃO: Verificar se email corresponde
                    payer_email = mp_payment.get("payer", {}).get("email")
                    if payer_email:
                        # Buscar subscription com external_reference E email correspondente
                        subscription = (
                            Subscription.objects.filter(
                                company=company,
                                external_reference=external_reference,
                                payer_email=payer_email,
                                status__in=["authorized", "pending"],
                            )
                            .order_by("-created_at")
                            .first()
                        )

                        if subscription:
                            print(
                                f"✅ Empresa encontrada via external_reference + email: {company.name}"
                            )
                            logger.info(
                                f"Empresa {company.name} encontrada via external_reference {external_reference} e email {payer_email}"
                            )
                        else:
                            # Se não encontrou com email, buscar apenas por external_reference
                            subscription = (
                                Subscription.objects.filter(
                                    company=company,
                                    external_reference=external_reference,
                                    status__in=["authorized", "pending"],
                                )
                                .order_by("-created_at")
                                .first()
                            )

                            if subscription:
                                print(
                                    f"✅ Empresa encontrada via external_reference (email não correspondeu): {company.name}"
                                )
                                logger.warning(
                                    f"Email {payer_email} não corresponde ao da subscription {subscription.payer_email}"
                                )
                    else:
                        # Sem email, buscar apenas por external_reference
                        subscription = (
                            Subscription.objects.filter(
                                company=company,
                                external_reference=external_reference,
                                status__in=["authorized", "pending"],
                            )
                            .order_by("-created_at")
                            .first()
                        )

                        if subscription:
                            print(
                                f"✅ Empresa encontrada via external_reference: {company.name}"
                            )
                            logger.info(
                                f"Empresa {company.name} encontrada via external_reference {external_reference}"
                            )
                except Company.DoesNotExist:
                    logger.warning(
                        f"Empresa com external_reference {external_reference} não encontrada"
                    )
                    external_reference = None  # Continuar com outras estratégias

            # Se não encontrou subscription nem company ainda, tentar buscar de várias formas
            if not subscription and not company and not preapproval_id and not external_reference:
                payer_email = mp_payment.get("payer", {}).get("email")
                payer_id = mp_payment.get("payer", {}).get("id")
                operation_type = mp_payment.get("operation_type", "")

                print(f"Pagamento sem preapproval_id, tentando buscar empresa...")
                print(f"  Email: {payer_email}")
                print(f"  Payer ID: {payer_id}")
                print(f"  Operation: {operation_type}")

                company = None
                subscription = None

                try:
                    from django.utils import timezone
                    from datetime import timedelta

                    # Estratégia 1: Buscar subscription por email (últimas 24h) - MAIS SEGURO
                    if payer_email:
                        recent_date = timezone.now() - timedelta(hours=24)

                        subscription = (
                            Subscription.objects.filter(
                                payer_email=payer_email,
                                status__in=["authorized", "pending"],
                                created_at__gte=recent_date,
                            )
                            .order_by("-created_at")
                            .first()
                        )

                        if subscription:
                            company = subscription.company
                            print(
                                f"✅ Empresa encontrada via subscription (email match): {company.name}"
                            )
                            logger.info(
                                f"Empresa {company.name} encontrada via email {payer_email}"
                            )

                    # Estratégia 2: Se é validação de cartão, buscar por email + tempo muito recente (últimos 10 min)
                    # Validação cruzada: email DEVE corresponder + subscription muito recente
                    if (
                        not company
                        and operation_type == "card_validation"
                        and payer_email
                    ):
                        very_recent = timezone.now() - timedelta(minutes=10)

                        subscription = (
                            Subscription.objects.filter(
                                payer_email=payer_email,  # ✅ VALIDAÇÃO: Email deve corresponder
                                status__in=["authorized", "pending"],
                                created_at__gte=very_recent,
                            )
                            .order_by("-created_at")
                            .first()
                        )

                        if subscription:
                            company = subscription.company
                            print(
                                f"✅ Empresa encontrada via validação de cartão (email + tempo): {company.name}"
                            )
                            logger.info(
                                f"Empresa {company.name} encontrada para validação via subscription {subscription.preapproval_id}"
                            )

                    # Estratégia 3: Buscar usuário e sua empresa através de membership
                    if not company and payer_email:
                        from apps.users.models import User

                        user = User.objects.filter(email=payer_email).first()

                        if user:
                            # Buscar membership do usuário
                            membership = user.memberships.first()
                            if membership:
                                company = membership.company
                                print(
                                    f"✅ Empresa encontrada via membership: {company.name}"
                                )
                                logger.info(
                                    f"Empresa {company.name} encontrada via membership do usuário {payer_email}"
                                )

                                # Tentar encontrar subscription dessa empresa com esse email
                                subscription = (
                                    Subscription.objects.filter(
                                        company=company,
                                        payer_email=payer_email,
                                        status__in=["authorized", "pending"],
                                    )
                                    .order_by("-created_at")
                                    .first()
                                )

                    # Estratégia 4: Se ainda não encontrou e é validação, buscar subscription pendente da empresa do membership
                    # Mas APENAS se já encontramos a empresa via membership (não buscar "mais recente" sem validação)
                    if (
                        not company
                        and operation_type == "card_validation"
                        and payer_email
                    ):
                        from apps.users.models import User

                        user = User.objects.filter(email=payer_email).first()

                        if user:
                            membership = user.memberships.first()
                            if membership:
                                # Buscar subscription pendente dessa empresa específica
                                subscription = (
                                    Subscription.objects.filter(
                                        company=membership.company,
                                        status="pending",
                                        created_at__gte=timezone.now()
                                        - timedelta(minutes=10),
                                    )
                                    .order_by("-created_at")
                                    .first()
                                )

                                if subscription:
                                    company = membership.company
                                    print(
                                        f"✅ Empresa encontrada via membership + subscription pendente: {company.name}"
                                    )
                                    logger.info(
                                        f"Empresa {company.name} encontrada via membership + subscription pendente"
                                    )

                    # ❌ REMOVIDO: Buscar "mais recente" sem validação (muito perigoso)
                    # Isso poderia ativar a empresa errada se múltiplas empresas criarem assinaturas simultaneamente

                    if not company:
                        print(
                            f"❌ Não foi possível encontrar empresa para este pagamento"
                        )
                        print(f"   Email: {payer_email}")
                        print(f"   Payer ID: {payer_id}")
                        print(f"   Operation: {operation_type}")
                        return

                    # Determinar subscription_plan
                    subscription_plan = "monthly"  # Default
                    if subscription:
                        subscription_plan = subscription.plan.subscription_plan_type

                    # Criar Payment
                    payment = Payment.objects.create(
                        company=company,
                        payment_id=mercadopago_payment_id,
                        transaction_id=mp_payment.get("id"),
                        amount=mp_payment.get("transaction_amount", 0),
                        subscription_plan=subscription_plan,
                        payment_method=_map_payment_method(
                            mp_payment.get("payment_type_id")
                        ),
                        status=_map_payment_status(payment_status),
                        gateway_response=mp_payment,
                    )

                    print(f"✅ Payment criado para empresa {company.name}")

                except Exception as e:
                    print(f"❌ Erro ao buscar empresa: {str(e)}")
                    import traceback

                    traceback.print_exc()
                    return
            else:
                # Tem preapproval_id OU external_reference OU subscription já encontrada
                # Se não encontrou subscription ainda, tentar buscar pelo preapproval_id
                if not subscription and preapproval_id:
                    try:
                        subscription = Subscription.objects.get(
                            preapproval_id=preapproval_id
                        )
                        company = subscription.company
                        logger.info(f"Subscription encontrada via preapproval_id (segunda tentativa): {preapproval_id}, empresa: {company.name}")
                        print(f"✅ Subscription encontrada: {preapproval_id}, empresa: {company.name}")
                    except Subscription.DoesNotExist:
                        logger.warning(f"Assinatura {preapproval_id} não encontrada")

                # Se encontrou assinatura, criar pagamento vinculado
                if subscription:
                    payment = Payment.objects.create(
                        company=subscription.company,
                        payment_id=mercadopago_payment_id,
                        transaction_id=mp_payment.get("id"),
                        amount=mp_payment.get("transaction_amount", 0),
                        subscription_plan=subscription.plan.subscription_plan_type,
                        payment_method=_map_payment_method(
                            mp_payment.get("payment_type_id")
                        ),
                        status=_map_payment_status(payment_status),
                        gateway_response=mp_payment,
                    )
                    logger.info(f"Payment criado para subscription {subscription.preapproval_id}, empresa {subscription.company.name}")
                    print(f"✅ Payment criado para subscription {subscription.preapproval_id}")
                # Se não tem assinatura mas tem company (via external_reference), criar pagamento
                elif company:
                    # Tentar inferir plano
                    plan_type = "monthly"
                    sub = (
                        Subscription.objects.filter(company=company)
                        .order_by("-created_at")
                        .first()
                    )
                    if sub:
                        plan_type = sub.plan.subscription_plan_type

                    payment = Payment.objects.create(
                        company=company,
                        payment_id=mercadopago_payment_id,
                        transaction_id=mp_payment.get("id"),
                        amount=mp_payment.get("transaction_amount", 0),
                        subscription_plan=plan_type,
                        payment_method=_map_payment_method(
                            mp_payment.get("payment_type_id")
                        ),
                        status=_map_payment_status(payment_status),
                        gateway_response=mp_payment,
                    )
                    print(
                        f"✅ Payment criado para empresa {company.name} (via external_reference)"
                    )
                else:
                    print(
                        f"Não foi possível criar pagamento: assinatura {preapproval_id} não encontrada e empresa não identificada."
                    )
                    return

        # Atualizar status do pagamento
        old_status = payment.status
        payment.status = _map_payment_status(payment_status)
        payment.transaction_id = mp_payment.get("id")
        payment.gateway_response = mp_payment

        # Se pagamento foi aprovado
        if payment_status == "approved" and old_status != Payment.Status.COMPLETED:
            from datetime import timedelta
            from .models import SubscriptionPlanType

            payment.status = Payment.Status.COMPLETED
            payment.completed_at = timezone.now()

            # Ativar/renovar assinatura da empresa
            company = payment.company
            config = SubscriptionPlanType.get_config(payment.subscription_plan)

            # Buscar subscription relacionada
            # Reutilizar subscription já encontrada anteriormente, se disponível
            if not subscription:
                # Tentar buscar pelo preapproval_id novamente (pode ter sido criado entre a criação do payment e agora)
                preapproval_id_for_search = preapproval_id
                
                # Se não tem preapproval_id, buscar no transaction_data
                if not preapproval_id_for_search:
                    point_of_interaction = mp_payment.get("point_of_interaction", {})
                    transaction_data = point_of_interaction.get("transaction_data", {})
                    subscription_id_from_transaction = transaction_data.get("subscription_id")
                    if subscription_id_from_transaction:
                        preapproval_id_for_search = subscription_id_from_transaction
                        logger.info(f"subscription_id encontrado no transaction_data (aprovado): {preapproval_id_for_search}")
                
                if preapproval_id_for_search:
                    try:
                        subscription = Subscription.objects.get(preapproval_id=preapproval_id_for_search)
                        logger.info(f"Subscription encontrada via preapproval_id (aprovado): {preapproval_id_for_search}")
                    except Subscription.DoesNotExist:
                        logger.warning(f"Subscription {preapproval_id_for_search} não encontrada após aprovação")
                
                external_reference = mp_payment.get("external_reference")

            # Estratégia 1: Buscar por external_reference + validar email (MAIS SEGURO)
            # External reference contém o UUID da empresa
            if external_reference:
                try:
                    from apps.companies.models import Company

                    company_from_ref = Company.objects.get(id=external_reference)

                    # VALIDAÇÃO: Verificar se email corresponde
                    payer_email = mp_payment.get("payer", {}).get("email")
                    if payer_email:
                        # Buscar subscription com external_reference E email correspondente
                        subscription = (
                            Subscription.objects.filter(
                                company=company_from_ref,
                                external_reference=external_reference,
                                payer_email=payer_email,
                                status__in=["authorized", "pending"],
                            )
                            .order_by("-created_at")
                            .first()
                        )

                        if subscription:
                            logger.info(
                                f"Subscription encontrada via external_reference + email (empresa {company_from_ref.name})"
                            )
                        else:
                            # Se não encontrou com email, buscar apenas por external_reference
                            subscription = (
                                Subscription.objects.filter(
                                    company=company_from_ref,
                                    external_reference=external_reference,
                                    status__in=["authorized", "pending"],
                                )
                                .order_by("-created_at")
                                .first()
                            )

                            if subscription:
                                logger.warning(
                                    f"Subscription encontrada mas email não corresponde: {payer_email} vs {subscription.payer_email}"
                                )
                    else:
                        # Sem email, buscar apenas por external_reference
                        subscription = (
                            Subscription.objects.filter(
                                company=company_from_ref,
                                external_reference=external_reference,
                                status__in=["authorized", "pending"],
                            )
                            .order_by("-created_at")
                            .first()
                        )

                        if subscription:
                            logger.info(
                                f"Subscription encontrada via external_reference (empresa {company_from_ref.name})"
                            )

                    if not subscription:
                        logger.warning(
                            f"Subscription não encontrada para empresa {external_reference}"
                        )
                except Company.DoesNotExist:
                    logger.warning(
                        f"Empresa com external_reference {external_reference} não encontrada"
                    )

            # Estratégia 2: Buscar por preapproval_id
            if not subscription and preapproval_id:
                try:
                    subscription = Subscription.objects.get(
                        preapproval_id=preapproval_id
                    )
                    logger.info(
                        f"Subscription encontrada via preapproval_id: {preapproval_id}"
                    )
                except Subscription.DoesNotExist:
                    logger.warning(
                        f"Subscription {preapproval_id} não encontrada para payment {mercadopago_payment_id}"
                    )

            # Estratégia 3: Buscar pela empresa do payment (fallback)
            if not subscription:
                # Buscar subscription mais recente da empresa
                subscription = (
                    Subscription.objects.filter(
                        company=company, status__in=["authorized", "pending"]
                    )
                    .order_by("-created_at")
                    .first()
                )

                if subscription:
                    logger.info(
                        f"Subscription encontrada via empresa: {subscription.preapproval_id}"
                    )

            # Se tem subscription relacionada, usar método activate() ou renew() conforme necessário
            if subscription:
                # Se subscription ainda não está autorizada, ativar (primeira vez)
                if subscription.status != Subscription.Status.AUTHORIZED:
                    subscription.status = Subscription.Status.AUTHORIZED
                    subscription.activate()  # Ativa subscription e atualiza company (incluindo expires_at)
                    expires_at = subscription.expires_at
                    logger.info(
                        f"Subscription {subscription.preapproval_id} ativada após pagamento confirmado até {expires_at}"
                    )
                else:
                    # Se já está autorizada, RENOVAR (estender a partir da expiração atual)
                    expires_at = subscription.renew()
                    logger.info(
                        f"✅ Subscription {subscription.preapproval_id} RENOVADA para {company.name} até {expires_at}"
                    )
                    print(
                        f"✅ Assinatura RENOVADA para {company.name} até {expires_at}"
                    )
                
                logger.info(
                    f"✅ Pagamento confirmado! Assinatura {'ativada' if subscription.status == Subscription.Status.AUTHORIZED else 'renovada'} para {company.name} até {expires_at}"
                )
                print(
                    f"✅ Pagamento confirmado! Assinatura ativada/renovada para {company.name} até {expires_at}"
                )
            else:
                # Se não tem subscription, criar uma nova (caso raro - pagamento sem subscription)
                logger.warning(
                    f"Pagamento aprovado mas subscription não encontrada para empresa {company.name}. Criando subscription..."
                )
                # Buscar plano pelo tipo
                from .models import SubscriptionPlan
                plan = SubscriptionPlan.objects.filter(
                    subscription_plan_type=payment.subscription_plan,
                    status='active'
                ).first()
                
                if plan:
                    # Criar subscription temporária
                    import time
                    temp_preapproval_id = f"payment_{mercadopago_payment_id}_{int(time.time())}"
                    subscription = Subscription.objects.create(
                        company=company,
                        plan=plan,
                        preapproval_id=temp_preapproval_id,
                        payer_email=mp_payment.get("payer", {}).get("email", company.email),
                        status=Subscription.Status.AUTHORIZED,
                        is_trial=False,
                        start_date=timezone.now(),
                        external_reference=str(company.id),
                    )
                    subscription.activate()
                    logger.info(f"Subscription criada para pagamento sem subscription: {subscription.preapproval_id}")
                else:
                    logger.error(f"Plano {payment.subscription_plan} não encontrado. Não foi possível criar subscription.")

        # Se pagamento foi recusado ou cancelado
        elif payment_status in ["rejected", "cancelled", "refunded"]:
            payment.status = _map_payment_status(payment_status)
            payment.save()
            
            # Obter company do payment se disponível
            payment_company = payment.company if hasattr(payment, 'company') and payment.company else None
            
            logger.warning(
                f"Pagamento {payment_status}: {mercadopago_payment_id} para empresa {payment_company.name if payment_company else 'desconhecida'}"
            )
            print(f"❌ Pagamento {payment_status}: {mercadopago_payment_id}")
            
            # Buscar subscription relacionada se ainda não foi encontrada
            if not subscription:
                # Tentar buscar pelo preapproval_id novamente
                if preapproval_id:
                    try:
                        subscription = Subscription.objects.get(preapproval_id=preapproval_id)
                        logger.info(f"Subscription encontrada para pagamento recusado: {subscription.preapproval_id}")
                    except Subscription.DoesNotExist:
                        pass
                
                # Se ainda não encontrou, buscar por external_reference
                if not subscription:
                    external_ref = mp_payment.get("external_reference")
                    if external_ref:
                        try:
                            from apps.companies.models import Company
                            company_from_ref = Company.objects.get(id=external_ref)
                            subscription = (
                                Subscription.objects.filter(
                                    company=company_from_ref,
                                    external_reference=external_ref,
                                )
                                .order_by("-created_at")
                                .first()
                            )
                            if subscription:
                                logger.info(f"Subscription encontrada via external_reference para pagamento recusado")
                        except Exception as e:
                            logger.warning(f"Erro ao buscar subscription via external_reference: {str(e)}")
            
            # Se encontrou subscription, verificar se deve suspender/cancelar
            if subscription:
                # Se é um pagamento recorrente recusado (subscription já estava autorizada)
                if subscription.status == Subscription.Status.AUTHORIZED:
                    # Verificar quantos pagamentos foram recusados recentemente
                    from datetime import timedelta
                    recent_date = timezone.now() - timedelta(days=30)
                    
                    failed_payments_count = Payment.objects.filter(
                        company=subscription.company,
                        subscription_plan=subscription.plan.subscription_plan_type,
                        status=Payment.Status.FAILED,
                        created_at__gte=recent_date
                    ).count()
                    
                    logger.info(
                        f"Pagamentos falhados nos últimos 30 dias para subscription {subscription.preapproval_id}: {failed_payments_count}"
                    )
                    
                    # Se múltiplos pagamentos falharam, suspender a subscription
                    if failed_payments_count >= 3:
                        logger.warning(
                            f"⚠️ Múltiplos pagamentos falharam ({failed_payments_count}). Suspender subscription {subscription.preapproval_id}"
                        )
                        # Atualizar status da subscription para pending (suspender)
                        subscription.status = Subscription.Status.PENDING
                        subscription.save()
                        
                        # Suspender assinatura da empresa (mas não cancelar completamente)
                        subscription.company.subscription_active = False
                        subscription.company.save()
                        
                        logger.warning(
                            f"Subscription {subscription.preapproval_id} suspensa devido a múltiplos pagamentos falhados"
                        )
                        print(f"⚠️ Subscription suspensa: {failed_payments_count} pagamentos falharam")
                    else:
                        logger.info(
                            f"Pagamento recusado, mas subscription mantida ativa (falhas: {failed_payments_count}/3)"
                        )
                # Se é o primeiro pagamento recusado (subscription ainda pendente)
                elif subscription.status == Subscription.Status.PENDING:
                    logger.info(
                        f"Primeiro pagamento recusado para subscription pendente {subscription.preapproval_id}. Mantendo como pendente."
                    )
                    # Manter subscription como pending - pode ser tentativa de pagamento que falhou
                    # O usuário pode tentar novamente
                # Se subscription já estava cancelada
                elif subscription.status == Subscription.Status.CANCELLED:
                    logger.info(
                        f"Pagamento recusado para subscription já cancelada {subscription.preapproval_id}"
                    )
            else:
                # Se não encontrou subscription, apenas logar
                logger.warning(
                    f"Pagamento recusado mas subscription não encontrada para payment {mercadopago_payment_id}"
                )
            
            # Se é reembolso (refunded), verificar se deve cancelar subscription
            if payment_status == "refunded" and subscription:
                logger.warning(
                    f"⚠️ Pagamento reembolsado para subscription {subscription.preapproval_id}. Considerar cancelamento."
                )
                # Não cancelar automaticamente - pode ser reembolso parcial ou por solicitação do usuário
                # Mas atualizar status da subscription para pending
                if subscription.status == Subscription.Status.AUTHORIZED:
                    subscription.status = Subscription.Status.PENDING
                    subscription.company.subscription_active = False
                    subscription.company.save()
                    subscription.save()
                    logger.warning(
                        f"Subscription {subscription.preapproval_id} suspensa devido a reembolso"
                    )
        
        else:
            # Outros status (pending, in_process, etc) - apenas salvar
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
        "pending": Payment.Status.PENDING,
        "approved": Payment.Status.COMPLETED,
        "authorized": Payment.Status.COMPLETED,
        "in_process": Payment.Status.PENDING,
        "in_mediation": Payment.Status.PENDING,
        "rejected": Payment.Status.FAILED,
        "cancelled": Payment.Status.FAILED,
        "refunded": Payment.Status.REFUNDED,
        "charged_back": Payment.Status.REFUNDED,
    }
    return status_map.get(mp_status, Payment.Status.PENDING)


def _map_payment_method(payment_type_id: str) -> str:
    """
    Mapeia tipo de pagamento do Mercado Pago para método do modelo Payment.
    """
    method_map = {
        "credit_card": Payment.PaymentMethod.CREDIT_CARD,
        "debit_card": Payment.PaymentMethod.DEBIT_CARD,
        "bank_transfer": Payment.PaymentMethod.PIX,  # PIX é um tipo de transferência
        "ticket": Payment.PaymentMethod.BANK_SLIP,
    }
    return method_map.get(payment_type_id, Payment.PaymentMethod.PIX)
