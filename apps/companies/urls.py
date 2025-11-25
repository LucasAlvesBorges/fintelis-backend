from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyViewSet,
    MembershipDetailAPIView,
    MembershipListCreateAPIView,
)

router = DefaultRouter()
# Expose company endpoints directly under /api/v1/companies/
router.register('', CompanyViewSet, basename='companies')

urlpatterns = [
    path('memberships/', MembershipListCreateAPIView.as_view(), name='memberships-list'),
    path('memberships/<uuid:pk>/', MembershipDetailAPIView.as_view(), name='memberships-detail'),
    *router.urls,
]
