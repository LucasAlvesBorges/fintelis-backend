from django.contrib import admin

from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'type', 'tax_id', 'email', 'phone', 'created_at')
    search_fields = ('name', 'fantasy_name', 'company__name', 'tax_id', 'email', 'phone')
    list_filter = ('type', 'company')
    ordering = ('company__name', 'name')
    autocomplete_fields = ('company',)
