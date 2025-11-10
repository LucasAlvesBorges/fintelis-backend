from django.contrib import admin

from .models import Company, Membership


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'cnpj', 'email', 'created_at', 'updated_at')
    search_fields = ('name', 'cnpj', 'email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'cnpj', 'email')}),
        ('Audit', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'company', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__email', 'company__name')
    readonly_fields = ('created_at', 'updated_at')
