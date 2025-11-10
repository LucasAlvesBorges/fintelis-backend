from django.db import transaction
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .models import Company, Membership
from .serializers import CompanySerializer, MembershipSerializer


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
            raise PermissionDenied('Authentication required.')
        with transaction.atomic():
            company = serializer.save()
            Membership.objects.get_or_create(
                user=self.request.user,
                company=company,
                defaults={'role': Membership.Roles.ADMIN},
            )


class MembershipViewSet(viewsets.ModelViewSet):
    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Membership.objects.none()
        return Membership.objects.filter(company__memberships__user=user).select_related('user', 'company')

    def perform_create(self, serializer):
        company = serializer.validated_data['company']
        self._ensure_company_admin(company)
        serializer.save()

    def perform_update(self, serializer):
        company = serializer.instance.company
        self._ensure_company_admin(company)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_company_admin(instance.company)
        instance.delete()

    def _ensure_company_admin(self, company):
        membership = Membership.objects.filter(company=company, user=self.request.user).first()
        if membership is None or membership.role != Membership.Roles.ADMIN:
            raise PermissionDenied('You do not have permission to manage memberships for this company.')
