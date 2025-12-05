"""
Management command para criar planos de assinatura no Mercado Pago e salvá-los no banco.

Usage:
    python manage.py create_subscription_plans
    
    # Recriar planos existentes
    python manage.py create_subscription_plans --recreate
    
    # Criar apenas planos específicos
    python manage.py create_subscription_plans --plans monthly quarterly
    
    # Criar planos com PIX habilitado
    python manage.py create_subscription_plans --enable-pix
    
    # Combinar opções
    python manage.py create_subscription_plans --enable-pix --recreate
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.payments.models import SubscriptionPlan, SubscriptionPlanType
from apps.payments.mercadopago_service import get_mercadopago_service


class Command(BaseCommand):
    help = 'Cria planos de assinatura no Mercado Pago e salva no banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--recreate',
            action='store_true',
            help='Recria os planos mesmo se já existirem (desativa os antigos)',
        )
        parser.add_argument(
            '--plans',
            nargs='+',
            choices=['monthly', 'quarterly', 'semiannual', 'annual'],
            help='Criar apenas planos específicos',
        )
        parser.add_argument(
            '--billing-day',
            type=int,
            default=10,
            help='Dia do mês para cobrança (1-28). Padrão: 10',
        )
        parser.add_argument(
            '--back-url',
            type=str,
            default='https://64bfd926763a.ngrok-free.app/subscription',
            help='URL de retorno após checkout',
        )
        parser.add_argument(
            '--enable-pix',
            action='store_true',
            help='Habilitar PIX como método de pagamento nos planos (padrão: habilitado)',
        )
        parser.add_argument(
            '--disable-pix',
            action='store_true',
            help='Desabilitar PIX como método de pagamento nos planos',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando criação de planos de assinatura'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        
        # Verificar se o token está configurado
        if not settings.MERCADOPAGO_ACCESS_TOKEN:
            raise CommandError(
                '❌ MERCADOPAGO_ACCESS_TOKEN não está configurado. '
                'Configure no arquivo .env antes de continuar.'
            )
        
        # Verificar se é token de teste
        token = settings.MERCADOPAGO_ACCESS_TOKEN
        if token.startswith('APP_USR-'):
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  ATENÇÃO: Você está usando credenciais de PRODUÇÃO.\n'
                    '   Para testes, use credenciais de TESTE (começam com TEST-).\n'
                    '   Obtenha em: https://www.mercadopago.com.br/developers/panel/credentials\n'
                )
            )
            confirm = input('Deseja continuar mesmo assim? (s/N): ')
            if confirm.lower() != 's':
                self.stdout.write(self.style.ERROR('❌ Operação cancelada'))
                return
        elif token.startswith('TEST-'):
            self.stdout.write(self.style.SUCCESS('✅ Usando credenciais de TESTE'))
        
        self.stdout.write('')
        
        # Determinar quais planos criar
        plans_to_create = options['plans'] or ['monthly', 'quarterly', 'semiannual', 'annual']
        billing_day = options['billing_day']
        back_url = options['back_url']
        recreate = options['recreate']
        # PIX habilitado por padrão, a menos que --disable-pix seja usado
        enable_pix = not options['disable_pix']  # True por padrão, False apenas se --disable-pix
        
        self.stdout.write(f'📋 Planos a criar: {", ".join(plans_to_create)}')
        self.stdout.write(f'📅 Dia de cobrança: {billing_day}')
        self.stdout.write(f'🔗 URL de retorno: {back_url}')
        self.stdout.write(f'💳 PIX habilitado: {"Sim" if enable_pix else "Não"}')
        self.stdout.write('')
        
        # Criar cada plano
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for plan_type in plans_to_create:
            try:
                result = self._create_plan(
                    plan_type=plan_type,
                    billing_day=billing_day,
                    back_url=back_url,
                    recreate=recreate,
                    enable_pix=enable_pix
                )
                
                if result == 'created':
                    created_count += 1
                elif result == 'skipped':
                    skipped_count += 1
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ Erro ao criar plano {plan_type}: {str(e)}')
                )
                if options['verbosity'] >= 2:
                    import traceback
                    self.stdout.write(traceback.format_exc())
        
        # Resumo
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('📊 Resumo'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'✅ Planos criados: {created_count}')
        self.stdout.write(f'⏭️  Planos ignorados: {skipped_count}')
        self.stdout.write(f'❌ Erros: {error_count}')
        self.stdout.write('')
        
        # Listar planos no banco
        all_plans = SubscriptionPlan.objects.filter(status='active').order_by('subscription_plan_type')
        if all_plans.exists():
            self.stdout.write(self.style.SUCCESS('📦 Planos ativos no banco de dados:'))
            for plan in all_plans:
                self.stdout.write(
                    f'  • {plan.subscription_plan_type}: R$ {plan.transaction_amount} '
                    f'(ID: {plan.preapproval_plan_id})'
                )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Processo concluído!'))

    def _create_plan(self, plan_type, billing_day, back_url, recreate, enable_pix=False):
        """Cria um plano específico."""
        
        self.stdout.write('')
        self.stdout.write(f'📝 Processando plano: {plan_type.upper()}')
        self.stdout.write('-' * 40)
        
        # Obter configuração do plano
        config = SubscriptionPlanType.get_config(plan_type)
        
        if not config:
            raise CommandError(f'Configuração não encontrada para o plano: {plan_type}')
        
        self.stdout.write(f'  Descrição: {config["reason"]}')
        self.stdout.write(f'  Valor: R$ {config["amount"]}')
        self.stdout.write(f'  Frequência: a cada {config["frequency"]} {config["frequency_type"]}')
        
        # Verificar se já existe
        existing_plan = SubscriptionPlan.objects.filter(
            subscription_plan_type=plan_type,
            status='active'
        ).first()
        
        if existing_plan and not recreate:
            self.stdout.write(
                self.style.WARNING(
                    f'  ⏭️  Plano já existe (ID: {existing_plan.preapproval_plan_id}). '
                    f'Use --recreate para recriar.'
                )
            )
            return 'skipped'
        
        # Desativar plano antigo se existir e --recreate foi usado
        if existing_plan and recreate:
            self.stdout.write(f'  🔄 Desativando plano antigo...')
            existing_plan.status = 'inactive'
            existing_plan.save()
        
        # Criar plano no Mercado Pago
        self.stdout.write('  🌐 Criando plano no Mercado Pago...')
        self.stdout.write(f'     Valor: R$ {config["amount"]}')
        self.stdout.write(f'     Frequência: a cada {config["frequency"]} {config["frequency_type"]}')
        self.stdout.write(f'     Cobrança: no dia da primeira compra')
        if enable_pix:
            self.stdout.write(f'     Métodos de pagamento: Cartão de Crédito, Débito e PIX')
        
        try:
            mp_service = get_mercadopago_service()
            
            # Validar valores antes de enviar
            if float(config['amount']) > 4000:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠️  Valor R$ {config["amount"]} excede limite de R$ 4.000,00'
                    )
                )
            
            # Criar plano com PIX se habilitado
            mp_response = mp_service.create_preapproval_plan(
                reason=config['reason'],
                transaction_amount=config['amount'],
                frequency=config['frequency'],
                frequency_type=config['frequency_type'],
                back_url=back_url,
                enable_pix=enable_pix,
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'  ✅ Plano criado no Mercado Pago (ID: {mp_response["id"]})')
            )
            
        except Exception as e:
            error_msg = str(e)
            self.stdout.write(self.style.ERROR(f'  ❌ Erro: {error_msg}'))
            
            # Dar dicas baseadas no erro
            if 'frequency' in error_msg.lower():
                self.stdout.write(
                    self.style.WARNING(
                        '  💡 Dica: Verifique se a frequência está no formato correto.'
                    )
                )
            elif 'amount' in error_msg.lower() or '4000' in error_msg:
                self.stdout.write(
                    self.style.WARNING(
                        '  💡 Dica: O valor máximo permitido é R$ 4.000,00 por transação.'
                    )
                )
            elif 'unauthorized' in error_msg.lower():
                self.stdout.write(
                    self.style.WARNING(
                        '  💡 Dica: Use credenciais de TESTE para desenvolvimento.'
                    )
                )
            
            raise CommandError(f'Erro ao criar plano no Mercado Pago: {error_msg}')
        
        # Salvar no banco de dados
        self.stdout.write('  💾 Salvando no banco de dados...')
        
        plan = SubscriptionPlan.objects.create(
            preapproval_plan_id=mp_response['id'],
            reason=config['reason'],
            subscription_plan_type=plan_type,
            transaction_amount=config['amount'],
            currency_id='BRL',
            frequency=config['frequency'],
            frequency_type=config['frequency_type'],
            billing_day=None,  # Cobra no dia da primeira compra
            init_point=mp_response.get('init_point', ''),
            back_url=back_url,
            status='active',
            mercadopago_response=mp_response,
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'  ✅ Plano salvo no banco (UUID: {plan.id})')
        )
        
        return 'created'

