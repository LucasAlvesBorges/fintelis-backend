from django.conf import settings
from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.companies.models import Invitation
from apps.companies.serializers import InvitationSerializer
from apps.financials.mixins import ActiveCompanyMixin

from .models import User
from .serializers import (
    CompanyTokenObtainSerializer,
    LoginSerializer,
    OperatorSerializer,
    OperatorListSerializer,
    PasswordChangeSerializer,
    RegisterSerializer,
    UserAuthenticationSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        response = Response(
            {"user": UserAuthenticationSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )
        set_auth_cookies(response, str(refresh), str(refresh.access_token))
        return response


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user_data = UserAuthenticationSerializer(serializer.validated_data["user"]).data
        response = Response({"user": user_data})
        set_auth_cookies(
            response,
            serializer.validated_data["refresh"],
            serializer.validated_data["access"],
        )
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_data = UserAuthenticationSerializer(request.user).data
        return Response({"user": user_data})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"user": UserAuthenticationSerializer(user).data})


class CompanyTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CompanyTokenObtainSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        company = serializer.validated_data["company"]
        expires_at = serializer.validated_data["expires_at"]

        response = Response(
            {
                "company_access": token,
                "company": {"id": str(company.id), "name": company.name},
                "expires_at": expires_at,
            },
            status=status.HTTP_201_CREATED,
        )
        set_company_cookie(response, token, expires_at)
        return response


class InvitationPagination(PageNumberPagination):
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 3


class OperatorPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class OperatorListCreateView(ActiveCompanyMixin, ListCreateAPIView):
    """
    Lista e cria operadores da empresa ativa.
    Operadores são usuários sem login, usados para histórico de vendas em caixas/PDV.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = OperatorPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OperatorSerializer
        return OperatorListSerializer

    def get_queryset(self):
        company = self.get_active_company()
        return User.objects.filter(
            user_type=User.UserType.OPERADOR,
            operator_company=company
        ).order_by("first_name", "last_name")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = self.get_active_company()
        return ctx


class OperatorDetailView(ActiveCompanyMixin, RetrieveUpdateDestroyAPIView):
    """
    Recupera, atualiza ou remove um operador da empresa ativa.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OperatorSerializer
    lookup_field = "pk"

    def get_queryset(self):
        company = self.get_active_company()
        return User.objects.filter(
            user_type=User.UserType.OPERADOR,
            operator_company=company
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = self.get_active_company()
        return ctx


class MyInvitationsView(ListAPIView):
    """
    Lista convites relacionados ao usuário autenticado.
    scope=received (default) → convites recebidos (email do usuário).
    scope=sent → convites enviados pelo usuário.
    """


    permission_classes = [IsAuthenticated]
    serializer_class = InvitationSerializer
    pagination_class = InvitationPagination

    def get_queryset(self):
        scope = self.request.query_params.get('scope', 'received')
        if scope == 'sent':
            return Invitation.objects.filter(
                invited_by=self.request.user
            ).select_related('user', 'company', 'invited_by').order_by('-created_at')

        return Invitation.objects.filter(
            email=self.request.user.email
        ).select_related('user', 'company', 'invited_by').order_by('-created_at')


def set_auth_cookies(response, refresh_token: str, access_token: str):
    jwt_settings = settings.SIMPLE_JWT
    cookie_kwargs = {
        "httponly": jwt_settings.get("AUTH_COOKIE_HTTP_ONLY", True),
        "secure": jwt_settings.get("AUTH_COOKIE_SECURE", False),
        "samesite": jwt_settings.get("AUTH_COOKIE_SAMESITE", "Lax"),
    }
    response.set_cookie(
        jwt_settings.get("AUTH_COOKIE", "access_token"),
        access_token,
        max_age=int(jwt_settings["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        **cookie_kwargs,
    )
    response.set_cookie(
        jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        refresh_token,
        max_age=int(jwt_settings["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        **cookie_kwargs,
    )


def set_company_cookie(response, company_token: str, expires_at):
    jwt_settings = settings.SIMPLE_JWT
    cookie_kwargs = {
        "httponly": jwt_settings.get("AUTH_COOKIE_HTTP_ONLY", True),
        "secure": jwt_settings.get("AUTH_COOKIE_SECURE", False),
        "samesite": jwt_settings.get("AUTH_COOKIE_SAMESITE", "Lax"),
    }
    max_age = jwt_settings.get(
        "COMPANY_ACCESS_TOKEN_LIFETIME", jwt_settings["ACCESS_TOKEN_LIFETIME"]
    )
    response.set_cookie(
        jwt_settings.get("COMPANY_AUTH_COOKIE", "company_access_token"),
        company_token,
        max_age=(
            int(max_age.total_seconds()) if hasattr(max_age, "total_seconds") else None
        ),
        **cookie_kwargs,
    )
