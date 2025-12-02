from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from rest_framework import serializers
import uuid


class NotificationSerializer(serializers.ModelSerializer):
    link_to_stock_item = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "is_read",
            "created_at",
            "link_to_stock_item",
        ]


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Get company from query param or fallback to all user companies
        company_id = self.request.query_params.get("company")
        user_companies = self.request.user.memberships.values_list("company", flat=True)

        if company_id:
            # Ensure user has access to this company
            # Convert string UUID to UUID object for comparison if needed,
            # but values_list returns UUID objects usually.
            try:
                target_company_uuid = uuid.UUID(company_id)
                if target_company_uuid in user_companies:
                    return Notification.objects.filter(company_id=company_id).order_by(
                        "-created_at"
                    )
            except ValueError:
                pass  # Invalid UUID string
            return Notification.objects.none()

        return Notification.objects.filter(company__in=user_companies).order_by(
            "-created_at"
        )

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"status": "marked as read"})
