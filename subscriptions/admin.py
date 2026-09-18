from django.contrib import admin
from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan_name', 'amount_paid', 'status_badge', 'start_date', 'end_date', 'days_remaining', 'created_at')
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('user__email', 'user__name', 'razorpay_order_id', 'razorpay_payment_id')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    def status_badge(self, obj):
        return obj.status
    status_badge.short_description = 'Status'
