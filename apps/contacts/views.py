from rest_framework import permissions, viewsets

from apps.financials.permissions import IsCompanyMember
from apps.financials.views import CompanyScopedViewSet
from .models import Contact
from .serializers import ContactSerializer


class ContactViewSet(CompanyScopedViewSet):
    queryset = Contact.objects.all().select_related('company')
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]

# Create your views here.
