from django.contrib import admin
from .models import SubscriptionPlan, Subscription, Payment


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "reason",
        "subscription_plan_type",
        "transaction_amount",
        "frequency",
        "frequency_type",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "subscription_plan_type",
        "frequency_type",
        "created_at",
    )
    search_fields = (
        "reason",
        "preapproval_plan_id",
    )
    readonly_fields = (
        "id",
        "preapproval_plan_id",
        "init_point",
        "created_at",
        "updated_at",
        "mercadopago_response",
    )
    list_per_page = 25
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Plan Information",
            {
                "fields": (
                    "reason",
                    "subscription_plan_type",
                    "transaction_amount",
                    "currency_id",
                    "status",
                )
            },
        ),
        (
            "Recurrence Settings",
            {
                "fields": (
                    "frequency",
                    "frequency_type",
                    "repetitions",
                    "billing_day",
                )
            },
        ),
        (
            "Free Trial",
            {
                "fields": (
                    "free_trial_frequency",
                    "free_trial_frequency_type",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Mercado Pago",
            {
                "fields": (
                    "preapproval_plan_id",
                    "init_point",
                    "back_url",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Technical Data",
            {
                "fields": ("mercadopago_response",),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "preapproval_id",
        "external_reference",
        "company",
        "plan",
        "payer_email",
        "status",
        "is_trial",
        "start_date",
        "next_payment_date",
        "created_at",
    )
    list_filter = (
        "status",
        "is_trial",
        "created_at",
        "start_date",
    )
    search_fields = (
        "preapproval_id",
        "external_reference",
        "company__name",
        "company__cnpj",
        "payer_email",
    )
    readonly_fields = (
        "id",
        "preapproval_id",
        "external_reference",
        "created_at",
        "updated_at",
        "mercadopago_response",
    )
    raw_id_fields = ("company", "plan")
    list_per_page = 25
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Subscription Information",
            {
                "fields": (
                    "company",
                    "plan",
                    "preapproval_id",
                    "external_reference",
                    "payer_email",
                    "status",
                    "is_trial",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "start_date",
                    "next_payment_date",
                    "end_date",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Technical Data",
            {
                "fields": ("mercadopago_response",),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["activate_subscriptions", "cancel_subscriptions"]

    def activate_subscriptions(self, request, queryset):
        for subscription in queryset:
            subscription.activate()
        self.message_user(request, f"{queryset.count()} subscriptions activated.")

    activate_subscriptions.short_description = "Activate selected subscriptions"

    def cancel_subscriptions(self, request, queryset):
        for subscription in queryset:
            subscription.cancel()
        self.message_user(request, f"{queryset.count()} subscriptions cancelled.")

    cancel_subscriptions.short_description = "Cancel selected subscriptions"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment_id",
        "code",
        "company",
        "amount",
        "subscription_plan",
        "payment_method",
        "status",
        "created_at",
        "completed_at",
    )
    list_filter = (
        "status",
        "payment_method",
        "subscription_plan",
        "created_at",
    )
    search_fields = (
        "payment_id",
        "transaction_id",
        "code",
        "company__name",
        "company__cnpj",
    )
    readonly_fields = (
        "id",
        "code",
        "created_at",
        "updated_at",
        "gateway_response",
    )
    raw_id_fields = ("company",)
    list_per_page = 25
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    fieldsets = (
        ("Company Information", {"fields": ("company",)}),
        (
            "Payment Information",
            {
                "fields": (
                    "payment_id",
                    "transaction_id",
                    "code",
                    "amount",
                    "subscription_plan",
                    "payment_method",
                    "status",
                )
            },
        ),
        (
            "PIX Data",
            {
                "fields": ("pix_code",),
                "classes": ("collapse",),
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "completed_at",
                    "expires_at",
                    "updated_at",
                )
            },
        ),
        (
            "Additional Information",
            {
                "fields": ("notes", "gateway_response"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of payments (audit only)
        return request.user.is_superuser
