from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.companies.models import Company, Membership
from .authentication import CompanyAccessToken
from .models import User, name_validator


class UserAuthenticationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "must_change_password", "user_type")


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer para registro de usuários da plataforma.
    Apenas usuários do tipo PLATAFORMA podem se registrar via este endpoint.
    """
    password = serializers.CharField(write_only=True, min_length=8)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(validators=[name_validator])
    last_name = serializers.CharField(validators=[name_validator])

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "password")

    def create(self, validated_data):
        password = validated_data.pop("password")
        # Força o tipo de usuário como PLATAFORMA para registro
        validated_data["user_type"] = User.UserType.PLATAFORMA
        user = User.objects.create_user(password=password, **validated_data)
        return user

    def validate_first_name(self, value):
        return " ".join(value.split())

    def validate_last_name(self, value):
        return " ".join(value.split())


class MembershipUserCreateSerializer(RegisterSerializer):
    """
    Serializer para criação de usuários via convite de membership.
    Cria usuários do tipo PLATAFORMA com senha temporária.
    """
    password = serializers.CharField(write_only=True, min_length=4)

    class Meta(RegisterSerializer.Meta):
        fields = RegisterSerializer.Meta.fields

    def create(self, validated_data):
        # Força o tipo de usuário como PLATAFORMA para convites
        validated_data["user_type"] = User.UserType.PLATAFORMA
        user = super().create(validated_data)
        user.must_change_password = True
        user.save(update_fields=["must_change_password"])
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer para login de usuários da plataforma.
    Apenas usuários do tipo PLATAFORMA podem fazer login.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(request=request, username=email, password=password)
        if not user:
            raise serializers.ValidationError("Credenciais inválidas.")
        
        # Verifica se o usuário é do tipo PLATAFORMA
        if user.user_type != User.UserType.PLATAFORMA:
            raise serializers.ValidationError(
                "Este tipo de usuário não pode fazer login na plataforma."
            )

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

        # Regras flexíveis: apenas exige que nova senha seja diferente da atual
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {"new_password": "Nova senha deve ser diferente da atual."}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user


class OperatorSerializer(serializers.ModelSerializer):
    """
    Serializer para criação e listagem de usuários operadores.
    Operadores não têm login, apenas first_name e last_name são obrigatórios.
    São usados para histórico de vendas em caixas/PDV.
    """
    first_name = serializers.CharField(validators=[name_validator])
    last_name = serializers.CharField(validators=[name_validator])

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "user_type", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "user_type", "created_at", "updated_at")

    def validate_first_name(self, value):
        return " ".join(value.split())

    def validate_last_name(self, value):
        return " ".join(value.split())

    def create(self, validated_data):
        company = self.context.get("company")
        if not company:
            raise serializers.ValidationError(
                {"company": "Empresa ativa é obrigatória para criar operadores."}
            )
        
        user = User.objects.create_operator(
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            company=company,
        )
        return user


class OperatorListSerializer(serializers.ModelSerializer):
    """
    Serializer para listagem de operadores com informações resumidas.
    """
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "full_name", "is_active", "created_at")
        read_only_fields = fields
