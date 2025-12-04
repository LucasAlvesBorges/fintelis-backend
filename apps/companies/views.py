from django.db import transaction
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

from .models import Company, Membership, Invitation
from .serializers import (
    CompanySerializer,
    MembershipSerializer,
    InvitationSerializer,
    InvitationCreateSerializer,
    UserSearchSerializer,
    SubscriptionActivationSerializer,
)
from apps.financials.mixins import ActiveCompanyMixin

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
            # Criar trial via Subscription.create_trial()
            from apps.payments.models import Subscription
            try:
                subscription = Subscription.create_trial(company)
                message = "Trial de 14 dias iniciado."
            except ValueError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Ativar plano pago (isso deve ser feito via checkout/pagamento)
            # Por enquanto, apenas retornar erro informando que precisa fazer checkout
            return Response(
                {
                    "error": "Para ativar um plano pago, use o checkout de pagamento.",
                    "message": "Acesse /payment/checkout para escolher e pagar um plano."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Recarregar company para ter os dados atualizados
        company.refresh_from_db()
        
        subscription = company.active_subscription
        
        return Response(
            {
                "company": CompanySerializer(company).data,
                "subscription": {
                    "active": company.subscription_active,
                    "plan": subscription.plan.subscription_plan_type if subscription else None,
                    "is_trial": subscription.is_trial if subscription else False,
                    "subscription_started_at": company.subscription_started_at,
                    "subscription_expires_at": company.subscription_expires_at,
                    "message": message,
                },
            }
        )
