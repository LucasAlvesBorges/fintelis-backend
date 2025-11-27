from datetime import timedelta

from django.contrib.auth import authenticate, password_validation
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.companies.models import Company, Membership
from .authentication import CompanyAccessToken
from .models import User, name_validator


class UserAuthenticationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "must_change_password")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(validators=[name_validator])
    last_name = serializers.CharField(validators=[name_validator])

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "password")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user

    def validate_first_name(self, value):
        return " ".join(value.split())

    def validate_last_name(self, value):
        return " ".join(value.split())


class MembershipUserCreateSerializer(RegisterSerializer):
    password = serializers.CharField(write_only=True, min_length=4)

    class Meta(RegisterSerializer.Meta):
        fields = RegisterSerializer.Meta.fields

    def create(self, validated_data):
        user = super().create(validated_data)
        user.must_change_password = True

        # Herda assinatura/trial do usuário que está criando o convite (pai)
        invited_by = self.context.get("invited_by")
        if invited_by:
            # Copia trial se o usuário pai tem trial ativo
            if invited_by.trial_ends_at and invited_by.has_active_access:
                from django.utils import timezone
                from datetime import timedelta

                # Calcula o tempo restante do trial do pai
                remaining_days = (invited_by.trial_ends_at - timezone.now()).days
                if remaining_days > 0:
                    user.trial_ends_at = timezone.now() + timedelta(days=remaining_days)

        # Se não herdou nada e não tem trial/subscription, ativa trial padrão
        if not user.trial_ends_at:
            user.start_trial()

        user.save(
            update_fields=["must_change_password", "trial_ends_at", "trial_ends_at"]
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(request=request, username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        if not user.has_active_access:
            raise serializers.ValidationError("Período de teste expirado.")

        attrs["user"] = user
        refresh = RefreshToken.for_user(user)
        attrs["refresh"] = str(refresh)
        attrs["access"] = str(refresh.access_token)
        return attrs


class CompanyTokenObtainSerializer(serializers.Serializer):
    company_id = serializers.UUIDField()

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        company_id = attrs["company_id"]

        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist as exc:
            raise serializers.ValidationError("Empresa não encontrada.") from exc

        if not Membership.objects.filter(user=user, company=company).exists():
            raise serializers.ValidationError("Usuário não pertence a esta empresa.")

        token = CompanyAccessToken.for_user(user)
        token["company_id"] = str(company.id)
        attrs["token"] = str(token)
        attrs["company"] = company
        attrs["expires_at"] = token["exp"]
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "Senha atual incorreta."}
            )

        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {"new_password": "Nova senha deve ser diferente da atual."}
            )

        password_validation.validate_password(attrs["new_password"], user=user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user
