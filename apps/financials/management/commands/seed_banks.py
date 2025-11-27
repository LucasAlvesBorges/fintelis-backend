from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.financials.models import Bank


class Command(BaseCommand):
    help = 'Cria/atualiza bancos globais e anexa logos SVG a partir de media/bank_logos_source.'
    ## docker-compose exec app python manage.py seed_banks

    def handle(self, *args, **options):
        base_svg_dir = Path(settings.MEDIA_ROOT) / 'bank_logos_source'
        if not base_svg_dir.exists():
            self.stderr.write(self.style.WARNING(f'Pasta de logos não encontrada: {base_svg_dir}'))

        banks = [
            {'code': '001', 'name': 'Banco do Brasil S.A.'},
            {'code': '033', 'name': 'Banco Santander (Brasil) S.A.'},
            {'code': '041', 'name': 'Banrisul S.A.'},
            {'code': '070', 'name': 'BRB - Banco de Brasília S.A.'},
            {'code': '077', 'name': 'Banco Inter S.A.'},
            {'code': '104', 'name': 'Caixa Econômica Federal'},
            {'code': '208', 'name': 'Banco BTG Pactual S.A.'},
            {'code': '212', 'name': 'Banco Original S.A.'},
            {'code': '237', 'name': 'Banco Bradesco S.A.'},
            {'code': '260', 'name': 'Nu Pagamentos S.A. (Nubank)'},
            {'code': '290', 'name': 'PagSeguro Internet S.A. (PagBank)'},
            {'code': '318', 'name': 'Banco BMG S.A.'},
            {'code': '336', 'name': 'Banco C6 S.A.'},
            {'code': '341', 'name': 'Itaú Unibanco S.A.'},
            {'code': '422', 'name': 'Banco Safra S.A.'},
            {'code': '4225', 'name': 'Banco Pan S.A.'},  # usando código interno para diferenciar logo
            {'code': '655', 'name': 'Banco Votorantim S.A. (BV)'},
            {'code': '707', 'name': 'Banco Daycoval S.A.'},
            {'code': '748', 'name': 'Sicredi'},
            {'code': '756', 'name': 'Sicoob'},
            {'code': '9997', 'name': 'PicPay Banco S.A.'},  # código custom para logo
            {'code': '999', 'name': 'Banco de Créditos Bilhetagem Eletrônica'},
        ]

        for bank_data in banks:
            bank, _ = Bank.objects.update_or_create(
                code=bank_data['code'],
                defaults={'name': bank_data['name'], 'is_active': True},
            )

            logo_path = base_svg_dir / f"{bank.code}.svg"
            if logo_path.exists():
                target_filename = f"{bank.code}.svg"
                upload_dir = bank.logo.field.upload_to.rstrip('/')

                # Evita gerar nomes aleatórios (_xxxx) em re-seeds: remove o arquivo atual e o path esperado
                if bank.logo:
                    bank.logo.storage.delete(bank.logo.name)
                bank.logo.storage.delete(f"{upload_dir}/{target_filename}")

                with logo_path.open('rb') as logo_file:
                    bank.logo.save(target_filename, ContentFile(logo_file.read()), save=True)
                self.stdout.write(self.style.SUCCESS(f'{bank.code} - logo atualizada de {logo_path.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'{bank.code} - logo não encontrada em {logo_path}, mantendo valor atual.'))

        self.stdout.write(self.style.SUCCESS('Seed de bancos concluído.'))
