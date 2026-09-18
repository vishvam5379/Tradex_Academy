from django.conf import settings
from .models import Subscription


def subscription_context(request):
    """Context processor providing current user subscription status and pricing config."""
    context = {
        'SUBSCRIPTION_PRICE': getattr(settings, 'SUBSCRIPTION_PRICE', 5000),
        'SUBSCRIPTION_DURATION_DAYS': getattr(settings, 'SUBSCRIPTION_DURATION_DAYS', 60),
        'RAZORPAY_KEY_ID': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'user_has_active_subscription': False,
        'active_subscription': None,
        'user_has_combo_access': False,
    }

    if request.user.is_authenticated:
        active_sub = request.user.active_subscription
        if active_sub:
            context['user_has_active_subscription'] = True
            context['active_subscription'] = active_sub
        
        context['user_has_combo_access'] = bool(
            request.user.is_staff or 
            request.user.is_superuser or 
            (active_sub and active_sub.plan_type == 'combo' and active_sub.is_currently_active)
        )

    return context
