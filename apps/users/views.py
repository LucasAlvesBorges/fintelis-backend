from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, RegisterSerializer, UserAuthenticationSerializer


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
