from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    CompanyTokenObtainSerializer,
    LoginSerializer,
    RegisterSerializer,
    SubscriptionActivationSerializer,
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
        response = Response({'user': UserAuthenticationSerializer(user).data}, status=status.HTTP_201_CREATED)
        set_auth_cookies(response, str(refresh), str(refresh.access_token))
        return response


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user_data = UserAuthenticationSerializer(serializer.validated_data['user']).data
        response = Response({'user': user_data})
        set_auth_cookies(
            response,
            serializer.validated_data['refresh'],
            serializer.validated_data['access'],
        )
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_data = UserAuthenticationSerializer(request.user).data
        return Response({'user': user_data})


class SubscriptionActivationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubscriptionActivationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = request.user

        if serializer.validated_data.get('start_trial'):
            user.start_trial()
            message = 'Trial de 15 dias iniciado.'
        else:
            plan = serializer.validated_data['plan']
            expires_at = serializer.validated_data['subscription_expires_at']
            user.subscription_plan = plan
            user.subscription_active = True
            user.subscription_expires_at = expires_at
            user.save(update_fields=['subscription_plan', 'subscription_active', 'subscription_expires_at'])
            message = f'Plano {plan} ativado.'

        return Response({
            'user': UserAuthenticationSerializer(user).data,
            'subscription': {
                'active': user.subscription_active,
                'plan': user.subscription_plan,
                'subscription_expires_at': user.subscription_expires_at,
                'trial_ends_at': user.trial_ends_at,
                'message': message,
            },
        })


class CompanyTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CompanyTokenObtainSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        company = serializer.validated_data['company']
        expires_at = serializer.validated_data['expires_at']

        response = Response(
            {
                'company_access': token,
                'company': {'id': str(company.id), 'name': company.name},
                'expires_at': expires_at,
            },
            status=status.HTTP_201_CREATED,
        )
        set_company_cookie(response, token, expires_at)
        return response


def set_auth_cookies(response, refresh_token: str, access_token: str):
    jwt_settings = settings.SIMPLE_JWT
    cookie_kwargs = {
        'httponly': jwt_settings.get('AUTH_COOKIE_HTTP_ONLY', True),
        'secure': jwt_settings.get('AUTH_COOKIE_SECURE', False),
        'samesite': jwt_settings.get('AUTH_COOKIE_SAMESITE', 'Lax'),
    }
    response.set_cookie(
        jwt_settings.get('AUTH_COOKIE', 'access_token'),
        access_token,
        max_age=int(jwt_settings['ACCESS_TOKEN_LIFETIME'].total_seconds()),
        **cookie_kwargs,
    )
    response.set_cookie(
        jwt_settings.get('AUTH_COOKIE_REFRESH', 'refresh_token'),
        refresh_token,
        max_age=int(jwt_settings['REFRESH_TOKEN_LIFETIME'].total_seconds()),
        **cookie_kwargs,
    )


def set_company_cookie(response, company_token: str, expires_at):
    jwt_settings = settings.SIMPLE_JWT
    cookie_kwargs = {
        'httponly': jwt_settings.get('AUTH_COOKIE_HTTP_ONLY', True),
        'secure': jwt_settings.get('AUTH_COOKIE_SECURE', False),
        'samesite': jwt_settings.get('AUTH_COOKIE_SAMESITE', 'Lax'),
    }
    max_age = jwt_settings.get('COMPANY_ACCESS_TOKEN_LIFETIME', jwt_settings['ACCESS_TOKEN_LIFETIME'])
    response.set_cookie(
        jwt_settings.get('COMPANY_AUTH_COOKIE', 'company_access_token'),
        company_token,
        max_age=int(max_age.total_seconds()) if hasattr(max_age, 'total_seconds') else None,
        **cookie_kwargs,
    )
