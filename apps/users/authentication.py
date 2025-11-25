from datetime import timedelta

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import Token

from apps.companies.models import Company, Membership


class CookieJWTAuthentication(JWTAuthentication):
    """
    Allows JWTs provided via HttpOnly cookies to authenticate API requests.
    Falls back to standard Authorization headers when present.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'))
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


class CompanyAccessToken(Token):
    """
    Short-lived token that binds a user to a specific company.
    """

    token_type = 'company_access'

    @property
    def lifetime(self):
        default_lifetime = getattr(api_settings, 'ACCESS_TOKEN_LIFETIME', timedelta(minutes=15))
        return settings.SIMPLE_JWT.get('COMPANY_ACCESS_TOKEN_LIFETIME', default_lifetime)


class CompanyJWTAuthentication(JWTAuthentication):
    """
    Authenticates via a company-bound token (header X-Company-Token or cookie).
    Sets request.active_company when valid and still verifies membership on each call.
    """

    token_class = CompanyAccessToken

    def authenticate(self, request):
        raw_token = self._get_company_token(request)
        if not raw_token:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except InvalidToken as exc:
            # If the cookie/header carried a non-company token, let other authenticators handle it.
            if "Not a company access token." in str(exc) or "Token has wrong type" in str(exc):
                return None
            raise

        if validated_token is None:
            return None
        user = self.get_user(validated_token)

        company_id = validated_token.get('company_id')
        if not company_id:
            raise InvalidToken('Company id missing from token.')

        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist as exc:
            raise InvalidToken('Company referenced in token no longer exists.') from exc

        if not Membership.objects.filter(user=user, company=company).exists():
            raise InvalidToken('User no longer belongs to this company.')

        request.active_company = company
        request._cached_active_company = company
        return user, validated_token

    def get_validated_token(self, raw_token):
        validated = super().get_validated_token(raw_token)
        if validated.get('token_type') != CompanyAccessToken.token_type:
            return None
        return validated

    def _get_company_token(self, request):
        header_token = request.headers.get('X-Company-Token')
        if header_token:
            return header_token
        cookie_name = settings.SIMPLE_JWT.get('COMPANY_AUTH_COOKIE', 'company_access_token')
        return request.COOKIES.get(cookie_name)
