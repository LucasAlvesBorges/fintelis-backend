"""
Script para popular dados de exemplo no módulo de inventário.

COMANDOS DE USO:
    # Popular dados para a primeira empresa do banco
    python manage.py populate_inventory

    # Popular dados para uma empresa específica
    python manage.py populate_inventory --company-id 1

    # Limpar dados existentes antes de popular
    python manage.py populate_inventory --clear

    # Combinar opções
    python manage.py populate_inventory --company-id 1 --clear

    # Via Docker
    docker-compose exec app python manage.py populate_inventory
    docker-compose exec app python manage.py populate_inventory --company-id 1 --clear
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from apps.companies.models import Company
from apps.inventory.models import (
    ProductCategory,
    Product,
    Inventory,
    StockItem,
    InventoryMovement
)


class Command(BaseCommand):
    help = 'Popula dados de exemplo no módulo de inventário'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID da empresa para popular os dados (se não informado, usa a primeira empresa)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpa os dados existentes antes de popular',
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        clear = options.get('clear', False)

        # Obtém ou cria a empresa
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Empresa com ID {company_id} não encontrada.')
                )
                return
        else:
            company = Company.objects.first()
            if not company:
                self.stdout.write(
                    self.style.ERROR('Nenhuma empresa encontrada. Crie uma empresa primeiro.')
                )
                return

        self.stdout.write(
            self.style.SUCCESS(f'Populando dados para a empresa: {company.name}')
        )

        if clear:
            self.stdout.write(self.style.WARNING('Limpando dados existentes...'))
            InventoryMovement.objects.filter(company=company).delete()
            StockItem.objects.filter(company=company).delete()
            Product.objects.filter(company=company).delete()
            ProductCategory.objects.filter(company=company).delete()
            Inventory.objects.filter(company=company).delete()

        with transaction.atomic():
            # 1. Criar categorias de produtos
            self.stdout.write('Criando categorias de produtos...')
            categories_data = [
                {'name': 'Informática'},
                {'name': 'Bilhetagem'},
                {'name': 'Papelaria'},
                {'name': 'Limpeza'},
                {'name': 'Escritório'},
            ]

            categories = {}
            for cat_data in categories_data:
                category, created = ProductCategory.objects.get_or_create(
                    company=company,
                    name=cat_data['name'],
                    defaults=cat_data
                )
                categories[cat_data['name']] = category
                if created:
                    self.stdout.write(f'  ✓ Categoria criada: {category.name}')

            # 2. Criar produtos
            self.stdout.write('Criando produtos...')
            products_data = [
                {
                    'name': 'Cartão Vale Transporte',
                    'category': 'Bilhetagem',
                    'min_stock_level': 100,
                    'default_cost': Decimal('5.50'),
                },
                {
                    'name': 'Notebook Dell',
                    'category': 'Informática',
                    'min_stock_level': 5,
                    'default_cost': Decimal('3500.00'),
                },
                {
                    'name': 'Mouse Logitech',
                    'category': 'Informática',
                    'min_stock_level': 20,
                    'default_cost': Decimal('89.90'),
                },
                {
                    'name': 'Teclado Mecânico',
                    'category': 'Informática',
                    'min_stock_level': 15,
                    'default_cost': Decimal('250.00'),
                },
                {
                    'name': 'Papel A4',
                    'category': 'Papelaria',
                    'min_stock_level': 50,
                    'default_cost': Decimal('25.00'),
                },
                {
                    'name': 'Caneta Esferográfica',
                    'category': 'Papelaria',
                    'min_stock_level': 200,
                    'default_cost': Decimal('2.50'),
                },
                {
                    'name': 'Detergente',
                    'category': 'Limpeza',
                    'min_stock_level': 30,
                    'default_cost': Decimal('8.90'),
                },
                {
                    'name': 'Cadeira Ergonômica',
                    'category': 'Escritório',
                    'min_stock_level': 10,
                    'default_cost': Decimal('850.00'),
                },
            ]

            products = {}
            for prod_data in products_data:
                category = categories.get(prod_data['category'])
                product, created = Product.objects.get_or_create(
                    company=company,
                    name=prod_data['name'],
                    defaults={
                        'product_category': category,
                        'min_stock_level': prod_data['min_stock_level'],
                        'default_cost': prod_data['default_cost'],
                    }
                )
                products[prod_data['name']] = product
                if created:
                    self.stdout.write(f'  ✓ Produto criado: {product.name}')

            # 3. Criar inventários (locais de estoque)
            self.stdout.write('Criando inventários...')
            inventories_data = [
                {'name': 'Estoque Principal'},
                {'name': 'Estoque TI'},
                {'name': 'Estoque Bilhetagem'},
                {'name': 'Estoque Secundário'},
            ]

            inventories = {}
            for inv_data in inventories_data:
                inventory, created = Inventory.objects.get_or_create(
                    company=company,
                    name=inv_data['name'],
                    defaults=inv_data
                )
                inventories[inv_data['name']] = inventory
                if created:
                    self.stdout.write(f'  ✓ Inventário criado: {inventory.name}')

            # 4. Criar itens de estoque
            self.stdout.write('Criando itens de estoque...')
            stock_items_data = [
                # Estoque Principal
                {'product': 'Cartão Vale Transporte', 'inventory': 'Estoque Principal', 'quantity': 500},
                {'product': 'Papel A4', 'inventory': 'Estoque Principal', 'quantity': 200},
                {'product': 'Caneta Esferográfica', 'inventory': 'Estoque Principal', 'quantity': 500},
                {'product': 'Detergente', 'inventory': 'Estoque Principal', 'quantity': 100},
                {'product': 'Cadeira Ergonômica', 'inventory': 'Estoque Principal', 'quantity': 25},
                # Estoque TI
                {'product': 'Notebook Dell', 'inventory': 'Estoque TI', 'quantity': 10},
                {'product': 'Mouse Logitech', 'inventory': 'Estoque TI', 'quantity': 50},
                {'product': 'Teclado Mecânico', 'inventory': 'Estoque TI', 'quantity': 30},
                # Estoque Bilhetagem
                {'product': 'Cartão Vale Transporte', 'inventory': 'Estoque Bilhetagem', 'quantity': 1000},
                # Estoque Secundário
                {'product': 'Papel A4', 'inventory': 'Estoque Secundário', 'quantity': 100},
                {'product': 'Caneta Esferográfica', 'inventory': 'Estoque Secundário', 'quantity': 300},
            ]

            stock_items = {}
            for stock_data in stock_items_data:
                product = products.get(stock_data['product'])
                inventory = inventories.get(stock_data['inventory'])
                
                if not product or not inventory:
                    continue

                stock_item, created = StockItem.objects.get_or_create(
                    company=company,
                    product=product,
                    inventory=inventory,
                    defaults={'quantity_on_hand': stock_data['quantity']}
                )
                stock_items[f"{product.name}_{inventory.name}"] = stock_item
                if created:
                    self.stdout.write(
                        f'  ✓ Item de estoque criado: {product.name} em {inventory.name} '
                        f'(Qtd: {stock_data["quantity"]})'
                    )

            # 5. Criar movimentações de inventário (histórico)
            self.stdout.write('Criando movimentações de inventário...')
            movements_data = [
                # Entradas
                {
                    'stock_item': 'Cartão Vale Transporte_Estoque Principal',
                    'quantity': 500,
                    'type': InventoryMovement.MovementType.IN_PURCHASE,
                },
                {
                    'stock_item': 'Notebook Dell_Estoque TI',
                    'quantity': 10,
                    'type': InventoryMovement.MovementType.IN_PURCHASE,
                },
                {
                    'stock_item': 'Mouse Logitech_Estoque TI',
                    'quantity': 50,
                    'type': InventoryMovement.MovementType.IN_PURCHASE,
                },
                {
                    'stock_item': 'Cartão Vale Transporte_Estoque Bilhetagem',
                    'quantity': 1000,
                    'type': InventoryMovement.MovementType.IN_PURCHASE,
                },
                # Saídas
                {
                    'stock_item': 'Cartão Vale Transporte_Estoque Principal',
                    'quantity': -50,
                    'type': InventoryMovement.MovementType.OUT_SALE,
                },
                {
                    'stock_item': 'Mouse Logitech_Estoque TI',
                    'quantity': -5,
                    'type': InventoryMovement.MovementType.OUT_SALE,
                },
                {
                    'stock_item': 'Papel A4_Estoque Principal',
                    'quantity': -20,
                    'type': InventoryMovement.MovementType.OUT_SALE,
                },
                # Ajustes
                {
                    'stock_item': 'Caneta Esferográfica_Estoque Principal',
                    'quantity': 10,
                    'type': InventoryMovement.MovementType.IN_ADJUSTMENT,
                },
                {
                    'stock_item': 'Detergente_Estoque Principal',
                    'quantity': -5,
                    'type': InventoryMovement.MovementType.OUT_ADJUSTMENT,
                },
            ]

            for mov_data in movements_data:
                stock_item = stock_items.get(mov_data['stock_item'])
                if not stock_item:
                    continue

                movement = InventoryMovement.objects.create(
                    stock_item=stock_item,
                    quantity_changed=mov_data['quantity'],
                    type=mov_data['type'],
                    company=company,
                )
                self.stdout.write(
                    f'  ✓ Movimentação criada: {movement.stock_item.product.name} '
                    f'({movement.get_type_display()}) - {mov_data["quantity"]:+d}'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Dados populados com sucesso para a empresa: {company.name}\n'
                f'  - Categorias: {ProductCategory.objects.filter(company=company).count()}\n'
                f'  - Produtos: {Product.objects.filter(company=company).count()}\n'
                f'  - Inventários: {Inventory.objects.filter(company=company).count()}\n'
                f'  - Itens de Estoque: {StockItem.objects.filter(company=company).count()}\n'
                f'  - Movimentações: {InventoryMovement.objects.filter(company=company).count()}'
            )
        )

