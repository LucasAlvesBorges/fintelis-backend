from django.contrib import admin

from .models import Company, CostCenter, Membership, Invitation


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "cnpj",
        "email",
        "subscription_active",
        "subscription_plan",
        "has_active_access",
        "created_at",
    )
    list_filter = ("subscription_active", "subscription_plan", "created_at")
    search_fields = ("name", "cnpj", "email")
    readonly_fields = ("created_at", "updated_at", "has_active_access")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    
    fieldsets = (
        (None, {"fields": ("name", "cnpj", "email")}),
        (
            "Subscription",
            {
                "fields": (
                    "subscription_active",
                    "subscription_plan",
                    "subscription_expires_at",
                    "trial_ends_at",
                    "mercadopago_subscription_id",
                    "has_active_access",
                ),
                "description": "Subscription and trial information.",
            },
        ),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    def has_active_access(self, obj):
        return obj.has_active_access

    has_active_access.boolean = True
    has_active_access.short_description = "Acesso Ativo"


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "company", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__email", "company__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "user",
        "company",
        "role",
        "status",
        "invited_by",
        "responded_at",
        "created_at",
    )
    list_filter = ("status", "role", "created_at", "responded_at")
    search_fields = (
        "email",
        "user__email",
        "user__first_name",
        "user__last_name",
        "company__name",
        "invited_by__email",
    )
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Informações do Convite",
            {
                "fields": ("company", "email", "user", "role", "status"),
            },
        ),
        (
            "Quem Convidou",
            {
                "fields": ("invited_by",),
            },
        ),
        (
            "Resposta",
            {
                "fields": ("responded_at",),
                "description": "Data/hora em que o convite foi aceito ou recusado.",
            },
        ),
        (
            "Auditoria",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    raw_id_fields = ("user", "company", "invited_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def get_readonly_fields(self, request, obj=None):
        """Torna responded_at readonly se o convite já foi respondido"""
        readonly = list(self.readonly_fields)
        if obj and obj.status != Invitation.Status.PENDING and obj.responded_at:
            # Se já foi respondido, não pode editar responded_at
            readonly.append("responded_at")
        return readonly


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "company", "parent", "created_at")
    list_filter = ("company",)
    search_fields = ("code", "name", "company__name")
    raw_id_fields = ("company", "parent")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("company__name", "code")
