from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.companies.models import Company, Membership
from apps.users.authentication import CompanyAccessToken


class ActiveCompanyMixin:
    """
    Resolve the active company from middleware-injected context or request data
    and enforce membership on every request.
    """

    def get_active_company(self) -> Company:
        if hasattr(self.request, "_cached_active_company"):
            return self.request._cached_active_company

        company = getattr(self.request, "active_company", None)
        if company:
            self._ensure_membership(company)
            self.request._cached_active_company = company
            return company

        # Try resolving from the company token header/cookie explicitly.
        token_company = self._get_company_from_token()
        if token_company:
            self._ensure_membership(token_company)
            self.request._cached_active_company = token_company
            return token_company

        company_id = (
            self.request.headers.get("X-Company-ID")
            or self.request.query_params.get("company_id")
            or self.request.data.get("company_id")
            or self.request.data.get("company")
        )

        if not company_id:
            # Fallback: pick the first membership as a default.
            if self.request.user and self.request.user.is_authenticated:
                membership = Membership.objects.filter(user=self.request.user).first()
                if membership:
                    self.request._cached_active_company = membership.company
                    return membership.company

            raise ValidationError(
                "Active company not provided. Use the X-Company-ID header or ensure user has a membership."
            )

        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist as exc:
            raise ValidationError("Company not found.") from exc

        self._ensure_membership(company)
        self.request._cached_active_company = company
        return company

    def _ensure_membership(self, company: Company) -> None:
        user = self.request.user
        if not user or not user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        if not Membership.objects.filter(company=company, user=user).exists():
            raise PermissionDenied("You do not belong to this company.")

    def _get_company_from_token(self):
        raw_token = (
            self.request.headers.get("X-Company-Token")
            or self.request.COOKIES.get(
                settings.SIMPLE_JWT.get("COMPANY_AUTH_COOKIE", "company_access_token")
            )
        )
        if not raw_token:
            return None

        try:
            validated = CompanyAccessToken(raw_token)
        except InvalidToken as exc:
            raise ValidationError("Invalid company token.") from exc

        company_id = validated.get("company_id")
        if not company_id:
            raise ValidationError("Invalid company token: missing company_id.")

        try:
            return Company.objects.get(pk=company_id)
        except Company.DoesNotExist as exc:
            raise ValidationError("Company not found.") from exc
