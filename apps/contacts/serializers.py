from rest_framework import serializers

from .models import Contact


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = (
            'id',
            'company',
            'name',
            'fantasy_name',
            'tax_id',
            'email',
            'phone',
            'type',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'company', 'created_at', 'updated_at')
