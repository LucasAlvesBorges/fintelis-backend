from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/companies/", include("apps.companies.urls")),
    path("api/v1/inventory/", include("apps.inventory.urls")),
    path("api/v1/financials/", include("apps.financials.urls")),
    path("api/v1/dashboards/", include("apps.dashboards.urls")),
    path("api/v1/contacts/", include("apps.contacts.urls")),
    path("api/v1/reports/", include("apps.reports.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
