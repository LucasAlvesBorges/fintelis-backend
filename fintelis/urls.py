from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/users/', include('apps.users.urls')), 
    path('api/v1/companies/', include('apps.companies.urls')),
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/financials/', include('apps.financials.urls')),
]
