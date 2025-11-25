from datetime import timedelta

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.companies.models import Company, Membership
from .authentication import CompanyAccessToken
from .models import User, name_validator

class UserAuthenticationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ( 'first_name', 'last_name')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(validators=[name_validator])
    last_name = serializers.CharField(validators=[name_validator])

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'password')

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user

    def validate_first_name(self, value):
        return ' '.join(value.split())

    def validate_last_name(self, value):
        return ' '.join(value.split())


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get('request')
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(request=request, username=email, password=password)
        if not user:
            raise serializers.ValidationError('Invalid credentials.')
        if not user.has_active_access:
            raise serializers.ValidationError('Assinatura inativa ou período de teste expirado.')

        attrs['user'] = user
        refresh = RefreshToken.for_user(user)
        attrs['refresh'] = str(refresh)
        attrs['access'] = str(refresh.access_token)
        return attrs


class SubscriptionActivationSerializer(serializers.Serializer):
    start_trial = serializers.BooleanField(required=False, default=False)
    plan = serializers.ChoiceField(
        choices=User.SubscriptionPlan.choices,
        required=False,
        allow_blank=False,
        allow_null=True,
    )

    def validate(self, attrs):
        start_trial = attrs.get('start_trial') or False
        plan = attrs.get('plan')
        user = self.context['request'].user

        if start_trial and plan:
            raise serializers.ValidationError('Escolha trial ou plano, não ambos.')
        if not start_trial and not plan:
            raise serializers.ValidationError('Envie start_trial=true ou selecione um plano.')

        if start_trial:
            if user.trial_ends_at:
                raise serializers.ValidationError('Trial já iniciado ou utilizado.')
            return attrs

        plan_durations = {
            User.SubscriptionPlan.MONTHLY: timedelta(days=30),
            User.SubscriptionPlan.QUARTERLY: timedelta(days=90),
            User.SubscriptionPlan.SEMIANNUAL: timedelta(days=180),
            User.SubscriptionPlan.ANNUAL: timedelta(days=365),
        }

        expires_at = timezone.now() + plan_durations[plan]
        attrs['subscription_expires_at'] = expires_at
        return attrs


class CompanyTokenObtainSerializer(serializers.Serializer):
    company_id = serializers.UUIDField()

    def validate(self, attrs):
        request = self.context['request']
        user = request.user
        company_id = attrs['company_id']

        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist as exc:
            raise serializers.ValidationError('Empresa não encontrada.') from exc

        if not Membership.objects.filter(user=user, company=company).exists():
            raise serializers.ValidationError('Usuário não pertence a esta empresa.')

        token = CompanyAccessToken.for_user(user)
        token['company_id'] = str(company.id)
        attrs['token'] = str(token)
        attrs['company'] = company
        attrs['expires_at'] = token['exp']
        return attrs
