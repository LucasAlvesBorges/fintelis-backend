from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = (
        "id",
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "must_change_password",
        "is_staff",
        "is_active",
        "has_active_access",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "must_change_password",
    )
    search_fields = ("email", "first_name", "last_name", "phone_number")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone_number")}),
        (
            "Security",
            {
                "fields": ("must_change_password",),
                "description": "Controle de segurança e senha do usuário.",
            },
        ),
        (
            "Trial",
            {
                "fields": ("trial_ends_at",),
                "description": "Informações sobre trial do usuário.",
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at", "last_login", "has_active_access")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    def has_active_access(self, obj):
        """Exibe se o usuário tem acesso ativo (trial ou subscription)"""
        return obj.has_active_access

    has_active_access.boolean = True
    has_active_access.short_description = "Acesso Ativo"
