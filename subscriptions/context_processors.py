from django.conf import settings
from .models import Subscription, ManualPayment, UserNotification
from .views_manual import is_admin_email


def subscription_context(request):
    """Context processor providing current user subscription status, notifications, and pricing config."""
    context = {
        'SUBSCRIPTION_PRICE': getattr(settings, 'SUBSCRIPTION_PRICE', 3999),
        'SUBSCRIPTION_DURATION_DAYS': getattr(settings, 'SUBSCRIPTION_DURATION_DAYS', 90),
        'RAZORPAY_KEY_ID': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'user_has_active_subscription': False,
        'active_subscription': None,
        'user_has_combo_access': False,
        'is_manual_upi_admin': False,
        'payment_mode': getattr(settings, 'PAYMENT_MODE', 'manual_upi'),
        'manual_upi_id': getattr(settings, 'MANUAL_UPI_ID', '9313858614@ibl'),
        'manual_upi_phone': getattr(settings, 'MANUAL_UPI_PHONE', '9313858614'),
        'user_notifications': [],
        'unread_notifications_count': 0,
        'pending_manual_payment': None,
        'approved_manual_payment': None,
    }

    if request.user.is_authenticated:
        try:
            active_sub = getattr(request.user, 'active_subscription', None)
            if active_sub:
                context['user_has_active_subscription'] = True
                context['active_subscription'] = active_sub
            
            context['user_has_combo_access'] = bool(
                request.user.is_staff or 
                request.user.is_superuser or 
                (active_sub and active_sub.plan_type in ['combo', 'elite'] and active_sub.is_currently_active)
            )
            context['is_manual_upi_admin'] = is_admin_email(request.user)

            # Notifications
            unread_qs = request.user.notifications.filter(is_read=False).order_by('-created_at')
            context['unread_notifications_count'] = unread_qs.count()
            context['user_notifications'] = list(unread_qs[:5])

            # Pending manual payment for banner
            context['pending_manual_payment'] = request.user.manual_payments.filter(status='pending').order_by('-created_at').first()
            # Most recent approved payment
            context['approved_manual_payment'] = request.user.manual_payments.filter(status='approved').order_by('-reviewed_at').first()

        except Exception:
            pass

    return context
