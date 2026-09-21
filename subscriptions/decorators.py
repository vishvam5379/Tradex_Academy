from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse


def subscription_required(view_func):
    """
    Decorator that checks whether the logged-in user has an active, unexpired subscription.
    If unauthenticated, redirects to login page.
    If unsubscribed or expired, redirects to the checkout / subscription page.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please sign in to access course lessons.")
            return redirect(f"{reverse('accounts:signin')}?next={request.path}")

        if not request.user.has_active_subscription:
            messages.warning(
                request,
                "🔒 This course content requires an active subscription. Unlock access starting at ₹3,999 / 90 days."
            )
            return redirect(f"{reverse('subscriptions:checkout')}?next={request.path}")

        return view_func(request, *args, **kwargs)
    return _wrapped_view
