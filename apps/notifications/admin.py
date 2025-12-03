from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'is_read', 'created_at', 'link_to_stock_item')
    list_filter = ('is_read', 'created_at', 'company')
    search_fields = ('title', 'message', 'company__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    list_editable = ('is_read',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'company', 'title', 'message')
        }),
        ('Relacionamentos', {
            'fields': ('link_to_stock_item',)
        }),
        ('Status', {
            'fields': ('is_read',)
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at')
        }),
    )
