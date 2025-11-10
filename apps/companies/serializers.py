from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.users.serializers import RegisterSerializer
from .models import Company, Membership

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'phone_number')
        read_only_fields = fields


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            'id',
            'name',
            'cnpj',
            'email',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class MembershipSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    user_details = UserSummarySerializer(source='user', read_only=True)
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())
    company_name = serializers.CharField(source='company.name', read_only=True)
    new_user = RegisterSerializer(write_only=True, required=False)

    class Meta:
        model = Membership
        fields = (
            'id',
            'user',
            'user_details',
            'new_user',
            'company',
            'company_name',
            'role',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'user_details', 'company_name')

    def validate(self, attrs):
        if not attrs.get('user') and not attrs.get('new_user'):
            raise serializers.ValidationError('Provide an existing user or new_user payload.')
        return attrs

    def create(self, validated_data):
        new_user_data = validated_data.pop('new_user', None)
        if new_user_data:
            user_serializer = RegisterSerializer(data=new_user_data)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
            validated_data['user'] = user
        return super().create(validated_data)
