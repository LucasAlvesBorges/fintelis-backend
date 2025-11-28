import getpass

from django.contrib.auth import authenticate
from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company, CostCenter
from apps.users.models import User


class Command(BaseCommand):
    ## docker-compose exec app python manage.py seed_cost_centers
    help = "Preenche centros de custos padrão para uma empresa específica ou para todas."

    DEFAULT_STRUCTURE = [
        {
            "name": "Administracao",
            "children": [
                {"name": "Recursos Humanos"},
                {
                    "name": "Dep. Financeiro",
                    "children": [
                        {"name": "Repasse Creditos Bilhetagem"},
                    ],
                },
            ],
        },
        {
            "name": "Departamento Comercial",
            "children": [
                {"name": "Marketing"},
                {
                    "name": "Vendas",
                    "children": [
                        {"name": "Venda Passe Estudantil"},
                        {"name": "Venda Vale Transporte"},
                        {"name": "Venda Passe Facil"},
                        {"name": "Venda Capinhas"},
                    ],
                },
            ],
        },
        {
            "name": "Departamento Tecnico",
            "children": [
                {"name": "Desenvolvimento"},
                {"name": "Suporte Tecnico"},
            ],
        },
    ]

    def handle(self, *args, **options):
        user = self._prompt_and_authenticate()
        companies = (
            Company.objects.filter(memberships__user=user)
            .distinct()
            .order_by("name")
        )
        if not companies.exists():
            raise CommandError("Nenhuma empresa encontrada para este usuário.")

        selected_companies = self._prompt_company_selection(companies)
        created_total = 0
        for company in selected_companies:
            created = self._ensure_structure(company, self.DEFAULT_STRUCTURE)
            created_total += created
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{company.name}] centros de custos processados. Criados: {created}."
                )
            )

        self.stdout.write(
            self.style.NOTICE(f"Total de centros criados: {created_total}.")
        )

    def _prompt_and_authenticate(self) -> User:
        email = input("Email: ").strip()
        password = getpass.getpass("Senha: ")
        user = authenticate(email=email, password=password)
        if not user:
            raise CommandError("Credenciais inválidas.")
        if not user.is_active:
            raise CommandError("Usuário inativo.")
        return user

    def _prompt_company_selection(self, companies):
        self.stdout.write("Empresas disponíveis:")
        for idx, company in enumerate(companies, start=1):
            self.stdout.write(f"{idx}. {company.name} ({company.id})")
        choice = input(
            "Selecione o número da empresa ou 'all' para todas [all]: "
        ).strip()
        if not choice or choice.lower() == "all":
            return list(companies)
        try:
            idx = int(choice)
        except ValueError as exc:
            raise CommandError("Seleção inválida.") from exc
        if idx < 1 or idx > companies.count():
            raise CommandError("Número fora do intervalo.")
        return [companies[idx - 1]]

    def _ensure_structure(self, company: Company, nodes, parent=None) -> int:
        created_count = 0
        for node in nodes:
            name = node["name"]
            cost_center, created = CostCenter.objects.get_or_create(
                company=company,
                name=name,
                parent=parent,
            )
            if created:
                created_count += 1

            children = node.get("children") or []
            if children:
                created_count += self._ensure_structure(
                    company, children, parent=cost_center
                )
        return created_count
