from django.urls import path

from .views import (
    ChangePasswordView,
    CompanyTokenView,
    LoginView,
    MeView,
    MyInvitationsView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="users-register"),
    path("login/", LoginView.as_view(), name="users-login"),
    path("me/", MeView.as_view(), name="users-me"),
    path("company-token/", CompanyTokenView.as_view(), name="users-company-token"),
    path(
        "change-password/", ChangePasswordView.as_view(), name="users-change-password"
    ),
    path("my-invitations/", MyInvitationsView.as_view(), name="users-my-invitations"),
]
