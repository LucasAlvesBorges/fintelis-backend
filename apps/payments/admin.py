from django.contrib import admin
from django.utils.html import format_html
from .models import SubscriptionPlan, Subscription, Payment


class PaymentInline(admin.TabularInline):
    """Inline para mostrar payments relacionados a uma subscription."""
    model = Payment
    extra = 0
    readonly_fields = (
        "id",
        "payment_id",
        "transaction_id",
        "code",
        "amount",
        "subscription_plan",
        "payment_method",
        "status",
        "created_at",
        "completed_at",
    )
    fields = (
        "payment_id",
        "amount",
        "payment_method",
        "status",
        "created_at",
        "completed_at",
    )
    can_delete = False
    show_change_link = True


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
        "preapproval_id",
        "external_reference",
        "company_link",
        "plan_link",
        "payer_email",
        "status",
        "is_trial",
        "start_date",
        "next_payment_date",
        "payments_count",
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
        "payments_count",
        "company_link",
        "plan_link",
    )
    list_per_page = 25
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    inlines = [PaymentInline]
    
    def payments_count(self, obj):
        """Mostra quantidade de payments relacionados."""
        count = obj.payments.count()
        if count > 0:
            return format_html(
                '<a href="{}?subscription__id__exact={}">{} pagamento(s)</a>',
                f"/admin/payments/payment/",
                obj.id,
                count
            )
        return "0"
    payments_count.short_description = "Pagamentos"
    
    def company_link(self, obj):
        """Mostra link para a empresa."""
        if obj.company:
            return format_html(
                '<a href="/admin/companies/company/{}/change/">{}</a>',
                obj.company.id,
                obj.company.name
            )
        return "-"
    company_link.short_description = "Empresa"
    
    def plan_link(self, obj):
        """Mostra link para o plano."""
        if obj.plan:
            return format_html(
                '<a href="/admin/payments/subscriptionplan/{}/change/">{}</a>',
                obj.plan.id,
                obj.plan.reason
            )
        return "-"
    plan_link.short_description = "Plano"

    fieldsets = (
        (
            "Subscription Information",
            {
                "fields": (
                    "company_link",
                    "plan_link",
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
        "payment_id",
        "code",
        "company_link",
        "subscription_link",
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
        "subscription",
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
        "company_link",
        "subscription_link",
    )
    list_per_page = 25
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    fieldsets = (
        ("Company Information", {"fields": ("company_link",)}),
        (
            "Subscription Information",
            {"fields": ("subscription_link",)},
        ),
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

    def company_link(self, obj):
        """Mostra link para a empresa."""
        if obj.company:
            return format_html(
                '<a href="/admin/companies/company/{}/change/">{}</a>',
                obj.company.id,
                obj.company.name
            )
        return "-"
    company_link.short_description = "Empresa"
    
    def subscription_link(self, obj):
        """Mostra link para a assinatura."""
        if obj.subscription:
            return format_html(
                '<a href="/admin/payments/subscription/{}/change/">{}</a>',
                obj.subscription.id,
                obj.subscription.preapproval_id
            )
        return "-"
    subscription_link.short_description = "Assinatura"

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of payments (audit only)
        return request.user.is_superuser
