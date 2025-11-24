from django.urls import path

from .views import LoginView, MeView, RegisterView, SubscriptionActivationView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='users-register'),
    path('login/', LoginView.as_view(), name='users-login'),
    path('me/', MeView.as_view(), name='users-me'),
    path('subscription/', SubscriptionActivationView.as_view(), name='users-subscription'),
]
