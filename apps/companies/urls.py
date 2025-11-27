from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyViewSet,
    MembershipDetailAPIView,
    MembershipListCreateAPIView,
    MembershipCompanyListAPIView,
    MembershipCompanyDetailAPIView,
    MembershipInviteAPIView,
    UserSearchAPIView,
    InvitationListCreateAPIView,
    InvitationAcceptRejectAPIView,
)

router = DefaultRouter()
# Expose company endpoints directly under /api/v1/companies/
router.register('', CompanyViewSet, basename='companies')

urlpatterns = [
    path('memberships/', MembershipListCreateAPIView.as_view(), name='memberships-list'),
    path('memberships/current/', MembershipCompanyListAPIView.as_view(), name='memberships-current'),
    path('memberships/current/<uuid:pk>/', MembershipCompanyDetailAPIView.as_view(), name='memberships-current-detail'),
    path('memberships/invite/', MembershipInviteAPIView.as_view(), name='memberships-invite'),
    path('memberships/<uuid:pk>/', MembershipDetailAPIView.as_view(), name='memberships-detail'),
    path('users/search/', UserSearchAPIView.as_view(), name='users-search'),
    path('invitations/', InvitationListCreateAPIView.as_view(), name='invitations-list-create'),
    path('invitations/<uuid:pk>/<str:action>/', InvitationAcceptRejectAPIView.as_view(), name='invitations-accept-reject'),
    *router.urls,
]
