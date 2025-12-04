from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.users.serializers import MembershipUserCreateSerializer
from .models import Company, CostCenter, Membership, Invitation

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "phone_number")
        read_only_fields = fields


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "cnpj",
            "email",
            "created_at",
            "updated_at",
            "subscription_active",
            "subscription_plan",
            "subscription_expires_at",
            "trial_ends_at",
            "has_active_access",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "subscription_active",
            "subscription_expires_at",
            "trial_ends_at",
            "has_active_access",
        )


class CostCenterSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True)

    class Meta:
        model = CostCenter
        fields = (
            "id",
            "company",
            "name",
            "code",
            "parent",
            "parent_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "company",
            "code",
            "parent_name",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "parent": {"required": False, "allow_null": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get("company")
        parent_field = self.fields.get("parent")
        if company and parent_field and getattr(parent_field, "queryset", None) is not None:
            self.fields["parent"].queryset = parent_field.queryset.filter(company=company)


class MembershipSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    user_details = UserSummarySerializer(source="user", read_only=True)
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), required=False, allow_null=True
    )
    company_name = serializers.CharField(source="company.name", read_only=True)
    new_user = MembershipUserCreateSerializer(write_only=True, required=False)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = Membership
        fields = (
            "id",
            "user",
            "user_details",
            "new_user",
            "company",
            "company_name",
            "role",
            "role_display",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "user_details",
            "company_name",
            "role_display",
        )
        extra_kwargs = {
            "user": {"required": False, "allow_null": True},
            "company": {"required": False, "allow_null": True},
        }

    def to_internal_value(self, data):
        """
        Adiciona valores None para user e company quando não estão no payload,
        para evitar que o DRF valide como obrigatórios antes do validate().
        """
        # Se company vem do contexto, adiciona None temporariamente para passar na validação
        if data is not serializers.empty and isinstance(data, dict):
            context_company = self.context.get("company")
            has_new_user = "new_user" in data

            # Se company não está no payload mas vem do contexto, adiciona None temporariamente
            if context_company and "company" not in data:
                data = data.copy()
                data["company"] = None

            # Se user não está no payload mas new_user está, adiciona None temporariamente
            if has_new_user and "user" not in data:
                data = data.copy()
                data["user"] = None

        return super().to_internal_value(data)

    def validate(self, attrs):
        # Primeiro, tenta obter a company do contexto (vem do ActiveCompanyMixin)
        context_company = self.context.get("company")
        if context_company:
            # Force company to active company when provided via context to avoid cross-company creations.
            attrs["company"] = context_company

        # Valida se company foi definida (via contexto ou payload)
        if not attrs.get("company"):
            instance_company = getattr(self.instance, "company", None)
            if instance_company:
                attrs["company"] = instance_company
            else:
                raise serializers.ValidationError(
                    {
                        "company": "Empresa ativa não encontrada. Envie o X-Company-Token ou cookie company_access_token."
                    }
                )

        # Valida se user foi fornecido (direto ou via new_user)
        if not attrs.get("user") and not attrs.get("new_user"):
            raise serializers.ValidationError(
                {
                    "user": "Envie o campo user (UUID de usuário existente) ou o bloco new_user com dados do usuário a criar."
                }
            )

        company = attrs.get("company")
        if company and not company.has_active_access:
            raise serializers.ValidationError(
                {
                    "company": "Assinatura inativa ou trial expirado. Ative o plano da empresa para enviar convites."
                }
            )

        return attrs

    def create(self, validated_data):
        new_user_data = validated_data.pop("new_user", None)
        if new_user_data:
            # Passa o usuário que está criando o convite no contexto
            # para que o novo usuário herde a assinatura/trial
            invited_by = (
                self.context.get("request").user
                if self.context.get("request")
                else None
            )
            user_serializer = MembershipUserCreateSerializer(
                data=new_user_data, context={"invited_by": invited_by}
            )
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
            validated_data["user"] = user
        return super().create(validated_data)


class InvitationSerializer(serializers.ModelSerializer):
    user_details = UserSummarySerializer(source="user", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    invited_by_name = serializers.SerializerMethodField()

    def get_invited_by_name(self, obj):
        if obj.invited_by:
            return f"{obj.invited_by.first_name} {obj.invited_by.last_name}"
        return None

    class Meta:
        model = Invitation
        fields = (
            "id",
            "company",
            "company_name",
            "user",
            "user_details",
            "email",
            "role",
            "status",
            "invited_by",
            "invited_by_name",
            "created_at",
            "updated_at",
            "responded_at",
        )
        read_only_fields = (
            "id",
            "status",
            "invited_by",
            "invited_by_name",
            "created_at",
            "updated_at",
            "responded_at",
            "user_details",
            "company_name",
        )


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(choices=Invitation.Roles.choices, required=True)

    def validate(self, attrs):
        email = attrs["email"]
        company = self.context.get("company")
        user = self.context.get("request").user

        if not company:
            raise serializers.ValidationError(
                {
                    "company": "Empresa ativa não encontrada. Envie o X-Company-Token ou cookie company_access_token."
                }
            )

        # Verifica se já existe membership para este email/empresa
        try:
            user_obj = User.objects.get(email=email)
            if Membership.objects.filter(company=company, user=user_obj).exists():
                raise serializers.ValidationError(
                    {"email": "Este usuário já é membro desta empresa."}
                )
        except User.DoesNotExist:
            pass

        # Verifica se já existe convite pendente para este email/empresa
        if Invitation.objects.filter(
            company=company, email=email, status=Invitation.Status.PENDING
        ).exists():
            raise serializers.ValidationError(
                {
                    "email": "Já existe um convite pendente para este email nesta empresa."
                }
            )

        attrs["company"] = company
        attrs["invited_by"] = user
        return attrs

    def create(self, validated_data):
        email = validated_data["email"]
        company = validated_data["company"]
        role = validated_data["role"]
        invited_by = validated_data["invited_by"]

        # Tenta encontrar usuário existente pelo email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = None

        invitation = Invitation.objects.create(
            company=company,
            user=user,
            email=email,
            role=role,
            invited_by=invited_by,
            status=Invitation.Status.PENDING,
        )
        return invitation


class UserSearchSerializer(serializers.ModelSerializer):
    """Serializer para busca de usuários por email"""

    is_member = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "phone_number", "is_member")
        read_only_fields = fields

    def get_is_member(self, obj):
        company = self.context.get("company")
        if company:
            return Membership.objects.filter(company=company, user=obj).exists()
        return False


class SubscriptionActivationSerializer(serializers.Serializer):
    from apps.payments.models import SubscriptionPlanType
    
    start_trial = serializers.BooleanField(required=False, default=False)
    plan = serializers.ChoiceField(
        choices=SubscriptionPlanType.choices,
        required=False,
        allow_blank=False,
        allow_null=True,
    )

    def validate(self, attrs):
        start_trial = attrs.get("start_trial") or False
        plan = attrs.get("plan")
        request = self.context.get("request")
        company = getattr(request, "active_company", None)

        if not company:
            raise serializers.ValidationError("Empresa ativa não encontrada.")

        if start_trial and plan:
            raise serializers.ValidationError("Escolha trial ou plano, não ambos.")
        if not start_trial and not plan:
            raise serializers.ValidationError(
                "Envie start_trial=true ou selecione um plano."
            )

        if start_trial:
            if company.trial_ends_at:
                raise serializers.ValidationError("Trial já iniciado ou utilizado.")
            return attrs

        # Usar configuração centralizada de duração dos planos
        from apps.payments.models import SubscriptionPlanType
        config = SubscriptionPlanType.get_config(plan)
        duration_days = config.get('duration_days', 30)
        
        expires_at = timezone.now() + timedelta(days=duration_days)
        attrs["subscription_expires_at"] = expires_at
        return attrs
