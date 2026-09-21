from django.conf import settings
from .models import Subscription
from .views_manual import is_admin_email


def subscription_context(request):
    """Context processor providing current user subscription status and pricing config."""
    context = {
        'SUBSCRIPTION_PRICE': getattr(settings, 'SUBSCRIPTION_PRICE', 3999),
        'SUBSCRIPTION_DURATION_DAYS': getattr(settings, 'SUBSCRIPTION_DURATION_DAYS', 90),
        'RAZORPAY_KEY_ID': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'user_has_active_subscription': False,
        'active_subscription': None,
        'user_has_combo_access': False,
        'is_manual_upi_admin': False,
        'payment_mode': getattr(settings, 'PAYMENT_MODE', 'razorpay'),
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
                (active_sub and active_sub.plan_type == 'combo' and active_sub.is_currently_active)
            )
            context['is_manual_upi_admin'] = is_admin_email(request.user)
        except Exception:
            pass

    return context
