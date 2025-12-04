from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

from .models import Company, CostCenter, Membership, Invitation
from .serializers import (
    CompanySerializer,
    CostCenterSerializer,
    MembershipSerializer,
    InvitationSerializer,
    InvitationCreateSerializer,
    UserSearchSerializer,
    SubscriptionActivationSerializer,
)
from apps.financials.mixins import ActiveCompanyMixin
from apps.financials.models import (
    Bill,
    Income,
    RecurringBill,
    RecurringIncome,
    Transaction,
)
from apps.financials.permissions import IsCompanyMember
from apps.financials.serializers import (
    BillSerializer,
    IncomeSerializer,
    RecurringBillSerializer,
    RecurringIncomeSerializer,
    TransactionSerializer,
)

User = get_user_model()


def _is_company_admin(user, company):
    """
    Considera admin quem tem membership admin ou é superuser/staff.
    """
    if user.is_superuser or user.is_staff:
        return True
    membership = Membership.objects.filter(company=company, user=user).first()
    return membership and membership.role == Membership.Roles.ADMIN


def _flatten_errors(detail):
    """
    Converte erros DRF (dict/list/str) em lista simples de mensagens de texto.
    Útil para respostas legíveis no frontend.
    """
    if isinstance(detail, str):
        return [detail]
    if isinstance(detail, list):
        messages = []
        for item in detail:
            messages.extend(_flatten_errors(item))
        return messages
    if isinstance(detail, dict):
        messages = []
        for key, value in detail.items():
            for msg in _flatten_errors(value):
                messages.append(f"{key}: {msg}")
        return messages
    return [str(detail)]


class CompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Company.objects.none()
        return Company.objects.filter(memberships__user=user).distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        with transaction.atomic():
            company = serializer.save()
            Membership.objects.get_or_create(
                user=self.request.user,
                company=company,
                defaults={"role": Membership.Roles.ADMIN},
            )


class MembershipListCreateAPIView(ListCreateAPIView):
    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Membership.objects.none()
        # Return only the memberships of the current user to avoid leaking other users' roles.
        return Membership.objects.filter(user=user).select_related("user", "company")

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        self._ensure_company_admin(company)
        serializer.save()

    def _ensure_company_admin(self, company):
        if not _is_company_admin(self.request.user, company):
            raise PermissionDenied(
                "You do not have permission to manage memberships for this company."
            )


class MembershipInviteAPIView(ActiveCompanyMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        company = self.get_active_company()
        self._ensure_company_admin(company)

        serializer = MembershipSerializer(
            data=request.data,
            context={"request": request, "company": company},
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            messages = _flatten_errors(exc.detail)
            return Response(
                {
                    "detail": "Erro de validação ao convidar usuário.",
                    "errors": exc.detail,
                    "messages": messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = serializer.save(company=company)
        return Response(
            MembershipSerializer(membership).data, status=status.HTTP_201_CREATED
        )

    def _ensure_company_admin(self, company):
        if not _is_company_admin(self.request.user, company):
            raise PermissionDenied(
                "You do not have permission to manage memberships for this company."
            )

class MembershipPagination(PageNumberPagination):
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 3


class InvitationPagination(PageNumberPagination):
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 3


class CostCenterDetailsPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 5

class MembershipPagination(PageNumberPagination):
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 3


class InvitationPagination(PageNumberPagination):
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 3


class MembershipCompanyListAPIView(ActiveCompanyMixin, ListAPIView):
    """
    Lista todos os usuários/memberships da empresa ativa.
    Requer o caller ser admin dessa empresa.
    """

    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MembershipPagination

    def get_queryset(self):
        company = self.get_active_company()
        self._ensure_company_admin(company)
        return (
            Membership.objects.filter(company=company)
            .exclude(user=self.request.user)
            .select_related('user', 'company')
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "_cached_active_company", None)
        return ctx

    def _ensure_company_admin(self, company):
        if not _is_company_admin(self.request.user, company):
            raise PermissionDenied(
                "You do not have permission to manage memberships for this company."
            )


class MembershipCompanyDetailAPIView(ActiveCompanyMixin, RetrieveUpdateDestroyAPIView):
    """
    Recupera/atualiza/remove um membership da empresa ativa.
    Requer o caller ser admin dessa empresa.
    """

    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        company = self.get_active_company()
        self._ensure_company_admin(company)
        return Membership.objects.filter(company=company).select_related(
            "user", "company"
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "_cached_active_company", None)
        return ctx

    def perform_update(self, serializer):
        company = self.get_active_company()
        self._ensure_company_admin(company)
        serializer.save(company=company)

    def perform_destroy(self, instance):
        company = self.get_active_company()
        self._ensure_company_admin(company)
        instance.delete()

    def _ensure_company_admin(self, company):
        if not _is_company_admin(self.request.user, company):
            raise PermissionDenied(
                "You do not have permission to manage memberships for this company."
            )


class MembershipDetailAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Membership.objects.none()
        # Restrict to memberships owned by the current user.
        return Membership.objects.filter(user=user).select_related("user", "company")

    def perform_update(self, serializer):
        company = serializer.instance.company
        self._ensure_company_admin(company)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_company_admin(instance.company)
        instance.delete()

    def _ensure_company_admin(self, company):
        if not _is_company_admin(self.request.user, company):
            raise PermissionDenied(
                "You do not have permission to manage memberships for this company."
            )


class UserSearchAPIView(ActiveCompanyMixin, APIView):
    """
    Busca usuários por email para convite.
    Apenas admins da empresa ativa podem buscar.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = self.get_active_company()
        self._ensure_company_admin(company)

        email = request.query_params.get("email")
        if not email:
            return Response(
                {"detail": "Parâmetro email é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
            serializer = UserSearchSerializer(
                user, context={"request": request, "company": company}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {"detail": "Usuário não encontrado com este email."},
                status=status.HTTP_404_NOT_FOUND,
            )

    def _ensure_company_admin(self, company):
        if not _is_company_admin(self.request.user, company):
            raise PermissionDenied(
                "You do not have permission to search users for this company."
            )


class InvitationListCreateAPIView(ActiveCompanyMixin, ListCreateAPIView):
    """
    Lista convites da empresa ativa ou cria um novo convite.
    Apenas admins podem criar convites.
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = InvitationPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return InvitationCreateSerializer
        return InvitationSerializer

    def get_queryset(self):
        scope = self.request.query_params.get('scope', 'sent')
        if scope == 'received':
            return Invitation.objects.filter(
                email=self.request.user.email
            ).select_related('user', 'company', 'invited_by').order_by('-created_at')

        company = self.get_active_company()
        self._ensure_company_admin(company)
        return (
            Invitation.objects.filter(company=company)
            .select_related("user", "company", "invited_by")
            .order_by("-created_at")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        company = self.get_active_company()
        ctx["company"] = company
        return ctx

    def create(self, request, *args, **kwargs):
        company = self.get_active_company()
        self._ensure_company_admin(company)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        # Retorna usando InvitationSerializer para incluir todos os campos
        response_serializer = InvitationSerializer(
            invitation, context=self.get_serializer_context()
        )
        # get_success_headers espera uma instância ou dict com 'id', não precisa passar nada
        headers = {}
        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def _ensure_company_admin(self, company):
        if not _is_company_admin(self.request.user, company):
            raise PermissionDenied(
                "You do not have permission to manage invitations for this company."
            )


class InvitationAcceptRejectAPIView(APIView):
    """
    Aceita ou recusa um convite.
    Apenas o usuário convidado pode aceitar/recusar.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, action):
        """
        action: 'accept' ou 'reject'
        """
        if action not in ["accept", "reject"]:
            return Response(
                {"detail": 'Ação inválida. Use "accept" ou "reject".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            invitation = Invitation.objects.get(pk=pk)
        except Invitation.DoesNotExist:
            return Response(
                {"detail": "Convite não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verifica se o convite está pendente
        if invitation.status != Invitation.Status.PENDING:
            return Response(
                {
                    "detail": f"Este convite já foi {invitation.get_status_display().lower()}."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verifica se o usuário autenticado é o destinatário do convite
        user_email = request.user.email
        if invitation.email != user_email:
            # Se o convite tem user definido, verifica também pelo user
            if invitation.user and invitation.user != request.user:
                return Response(
                    {"detail": "Você não tem permissão para responder este convite."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            elif not invitation.user:
                return Response(
                    {"detail": "Você não tem permissão para responder este convite."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Atualiza o user do convite se ainda não estava definido
        if not invitation.user:
            invitation.user = request.user
            invitation.save(update_fields=["user"])

        if action == "accept":
            return self._accept_invitation(invitation, request.user)
        else:
            return self._reject_invitation(invitation, request.user)

    def _accept_invitation(self, invitation, user):
        """Aceita o convite e cria o membership"""
        with transaction.atomic():
            # Verifica se já existe membership (pode ter sido criado entre o convite e a resposta)
            if Membership.objects.filter(
                company=invitation.company, user=user
            ).exists():
                invitation.status = Invitation.Status.ACCEPTED
                invitation.responded_at = timezone.now()
                invitation.save(update_fields=["status", "responded_at"])
                return Response(
                    {"detail": "Você já é membro desta empresa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Cria o membership
            membership = Membership.objects.create(
                company=invitation.company,
                user=user,
                role=invitation.role,
            )

            # Atualiza o convite
            invitation.status = Invitation.Status.ACCEPTED
            invitation.responded_at = timezone.now()
            invitation.save(update_fields=["status", "responded_at"])

            serializer = MembershipSerializer(membership)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _reject_invitation(self, invitation, user):
        """Recusa o convite"""
        invitation.status = Invitation.Status.REJECTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

        return Response(
            {"detail": "Convite recusado com sucesso."},
            status=status.HTTP_200_OK,
        )


class CostCenterViewSet(ActiveCompanyMixin, viewsets.ModelViewSet):
    queryset = CostCenter.objects.all().select_related("company", "parent")
    serializer_class = CostCenterSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

    def get_queryset(self):
        company = self.get_active_company()
        return self.queryset.filter(company=company)

    def perform_create(self, serializer):
        serializer.save(company=self.get_active_company())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["company"] = self.get_active_company()
        return context

    @action(detail=True, methods=["get"], url_path="details")
    def details(self, request, pk=None):
        """
        Retorna detalhes do centro de custo com movimentações associadas
        (transações, contas a pagar/receber e recorrentes), paginadas em 5 itens.
        """
        cost_center = self.get_object()
        company = self.get_active_company()

        if cost_center.company_id != company.id:
            raise ValidationError({"detail": "Centro de custo não pertence à empresa ativa."})

        paginator = CostCenterDetailsPagination()
        transactions_page = int(request.query_params.get("transactions_page", 1))
        bills_page = int(request.query_params.get("bills_page", 1))
        incomes_page = int(request.query_params.get("incomes_page", 1))
        recurring_bills_page = int(request.query_params.get("recurring_bills_page", 1))
        recurring_incomes_page = int(request.query_params.get("recurring_incomes_page", 1))
        page_size = paginator.page_size

        transactions_qs = (
            cost_center.transactions.all()
            .select_related(
                "category",
                "contact",
                "payment_method",
                "cost_center",
                "bank_account",
                "bank_account__bank",
            )
            .order_by("-created_at", "-transaction_date", "-id")
        )
        total_transactions = transactions_qs.count()
        transactions_start = (transactions_page - 1) * page_size
        transactions_end = transactions_start + page_size
        transactions = transactions_qs[transactions_start:transactions_end]
        transactions_total_pages = (total_transactions + page_size - 1) // page_size if total_transactions > 0 else 1

        bills_qs = (
            cost_center.bills.all()
            .select_related(
                "category",
                "contact",
                "cost_center",
                "payment_transaction",
                "payment_transaction__bank_account",
            )
            .order_by("-due_date", "-id")
        )
        total_bills = bills_qs.count()
        bills_start = (bills_page - 1) * page_size
        bills_end = bills_start + page_size
        bills = bills_qs[bills_start:bills_end]
        bills_total_pages = (total_bills + page_size - 1) // page_size if total_bills > 0 else 1

        incomes_qs = (
            cost_center.incomes.all()
            .select_related(
                "category",
                "contact",
                "cost_center",
                "payment_transaction",
                "payment_transaction__bank_account",
            )
            .order_by("-due_date", "-id")
        )
        total_incomes = incomes_qs.count()
        incomes_start = (incomes_page - 1) * page_size
        incomes_end = incomes_start + page_size
        incomes = incomes_qs[incomes_start:incomes_end]
        incomes_total_pages = (total_incomes + page_size - 1) // page_size if total_incomes > 0 else 1

        recurring_bills_ids = (
            Transaction.objects.filter(cost_center=cost_center, company=company)
            .exclude(recurring_bill_payments__isnull=True)
            .values_list("recurring_bill_payments__recurring_bill_id", flat=True)
            .distinct()
        )
        recurring_bills_qs = (
            RecurringBill.objects.filter(id__in=recurring_bills_ids, company=company)
            .select_related("category", "cost_center")
            .order_by("-next_due_date", "-id")
        )
        total_recurring_bills = recurring_bills_qs.count()
        recurring_bills_start = (recurring_bills_page - 1) * page_size
        recurring_bills_end = recurring_bills_start + page_size
        recurring_bills = recurring_bills_qs[recurring_bills_start:recurring_bills_end]
        recurring_bills_total_pages = (total_recurring_bills + page_size - 1) // page_size if total_recurring_bills > 0 else 1

        recurring_incomes_ids = (
            Transaction.objects.filter(cost_center=cost_center, company=company)
            .exclude(recurring_income_receipts__isnull=True)
            .values_list("recurring_income_receipts__recurring_income_id", flat=True)
            .distinct()
        )
        recurring_incomes_qs = (
            RecurringIncome.objects.filter(id__in=recurring_incomes_ids, company=company)
            .select_related("category", "cost_center")
            .order_by("-next_due_date", "-id")
        )
        total_recurring_incomes = recurring_incomes_qs.count()
        recurring_incomes_start = (recurring_incomes_page - 1) * page_size
        recurring_incomes_end = recurring_incomes_start + page_size
        recurring_incomes = recurring_incomes_qs[recurring_incomes_start:recurring_incomes_end]
        recurring_incomes_total_pages = (total_recurring_incomes + page_size - 1) // page_size if total_recurring_incomes > 0 else 1

        total_receitas = transactions_qs.filter(type=Transaction.Types.RECEITA).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_despesas = transactions_qs.filter(
            type__in=[Transaction.Types.DESPESA, Transaction.Types.TRANSFERENCIA_EXTERNA, Transaction.Types.ESTORNO]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_bills_amount = bills_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_incomes_amount = incomes_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return Response({
            "cost_center": CostCenterSerializer(cost_center, context=self.get_serializer_context()).data,
            "summary": {
                "total_receitas": total_receitas,
                "total_despesas": total_despesas,
                "total_bills": total_bills_amount,
                "total_incomes": total_incomes_amount,
                "total_transactions": total_transactions,
                "total_bills_count": total_bills,
                "total_incomes_count": total_incomes,
                "total_recurring_bills": total_recurring_bills,
                "total_recurring_incomes": total_recurring_incomes,
            },
            "transactions": {
                "items": TransactionSerializer(transactions, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": transactions_page,
                    "page_size": page_size,
                    "total_pages": transactions_total_pages,
                    "total_items": total_transactions,
                    "has_next": transactions_page < transactions_total_pages,
                    "has_previous": transactions_page > 1,
                },
            },
            "bills": {
                "items": BillSerializer(bills, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": bills_page,
                    "page_size": page_size,
                    "total_pages": bills_total_pages,
                    "total_items": total_bills,
                    "has_next": bills_page < bills_total_pages,
                    "has_previous": bills_page > 1,
                },
            },
            "incomes": {
                "items": IncomeSerializer(incomes, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": incomes_page,
                    "page_size": page_size,
                    "total_pages": incomes_total_pages,
                    "total_items": total_incomes,
                    "has_next": incomes_page < incomes_total_pages,
                    "has_previous": incomes_page > 1,
                },
            },
            "recurring_bills": {
                "items": RecurringBillSerializer(recurring_bills, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": recurring_bills_page,
                    "page_size": page_size,
                    "total_pages": recurring_bills_total_pages,
                    "total_items": total_recurring_bills,
                    "has_next": recurring_bills_page < recurring_bills_total_pages,
                    "has_previous": recurring_bills_page > 1,
                },
            },
            "recurring_incomes": {
                "items": RecurringIncomeSerializer(recurring_incomes, many=True, context=self.get_serializer_context()).data,
                "pagination": {
                    "page": recurring_incomes_page,
                    "page_size": page_size,
                    "total_pages": recurring_incomes_total_pages,
                    "total_items": total_recurring_incomes,
                    "has_next": recurring_incomes_page < recurring_incomes_total_pages,
                    "has_previous": recurring_incomes_page > 1,
                },
            },
        })


class SubscriptionActivationView(ActiveCompanyMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        company = self.get_active_company()
        request.active_company = company

        if not _is_company_admin(request.user, company):
            raise PermissionDenied(
                "Apenas administradores podem gerenciar a assinatura da empresa."
            )

        serializer = SubscriptionActivationSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get("start_trial"):
            company.start_trial()
            message = "Trial de 15 dias iniciado."
        else:
            plan = serializer.validated_data["plan"]
            expires_at = serializer.validated_data["subscription_expires_at"]
            company.subscription_plan = plan
            company.subscription_active = True
            company.subscription_expires_at = expires_at
            company.save(
                update_fields=[
                    "subscription_plan",
                    "subscription_active",
                    "subscription_expires_at",
                ]
            )
            message = f"Plano {plan} ativado."

        return Response(
            {
                "company": CompanySerializer(company).data,
                "subscription": {
                    "active": company.subscription_active,
                    "plan": company.subscription_plan,
                    "subscription_expires_at": company.subscription_expires_at,
                    "trial_ends_at": company.trial_ends_at,
                    "message": message,
                },
            }
        )
