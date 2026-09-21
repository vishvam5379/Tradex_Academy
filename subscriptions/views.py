import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.conf import settings
from django.contrib import messages

from .models import Subscription
from .utils import create_razorpay_order, verify_razorpay_signature


@login_required
def checkout_view(request):
    """Checkout page supporting multi-tier plans: Indian Market Foundation (₹3,999), Forex Gold Mastery (₹9,999), Complete Trader (₹11,999)."""
    plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
    
    # Selected plan from query param, defaults to combo (best value) or standard
    selected_plan_code = request.GET.get('plan', 'combo')
    if selected_plan_code not in plans:
        selected_plan_code = 'combo'
    
    selected_plan = plans[selected_plan_code]
    price = selected_plan['price']
    duration_days = selected_plan['duration_days']
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    
    # Check if user already has an active subscription
    already_active = request.user.has_active_subscription
    current_sub = request.user.active_subscription

    # Create initial Razorpay order for this session
    order = create_razorpay_order(
        amount_in_rupees=price,
        currency='INR',
        receipt=f"sub_{selected_plan_code}_{request.user.id}_{int(timezone.now().timestamp())}",
        notes={
            'user_id': str(request.user.id),
            'user_email': request.user.email,
            'plan_type': selected_plan_code,
        }
    )

    context = {
        'plans': plans,
        'selected_plan_code': selected_plan_code,
        'selected_plan': selected_plan,
        'price': price,
        'duration_days': duration_days,
        'razorpay_key_id': key_id,
        'razorpay_order_id': order['id'],
        'amount_in_paise': order['amount'],
        'currency': order['currency'],
        'is_mock_order': order.get('is_mock', False),
        'already_active': already_active,
        'current_sub': current_sub,
    }
    return render(request, 'subscriptions/checkout.html', context)


@login_required
@require_POST
def create_order_api(request):
    """API endpoint to generate fresh Razorpay order for a specific plan tier."""
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}
    
    plan_code = data.get('plan', request.GET.get('plan', 'combo'))
    plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
    plan = plans.get(plan_code, plans.get('combo', {'price': 11999}))
    price = plan['price']

    order = create_razorpay_order(
        amount_in_rupees=price,
        currency='INR',
        receipt=f"api_{plan_code}_{request.user.id}_{int(timezone.now().timestamp())}",
        notes={'user_id': str(request.user.id), 'user_email': request.user.email, 'plan_type': plan_code}
    )
    order['plan_code'] = plan_code
    order['plan_name'] = plan.get('name', 'Subscription')
    order['price'] = price
    return JsonResponse(order)


@csrf_exempt
@login_required
@require_POST
def verify_payment_view(request):
    """
    Verifies Razorpay payment signature and activates the selected subscription tier.
    Accepts both JSON payloads and Form POST payloads.
    """
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)
    else:
        data = request.POST

    order_id = data.get('razorpay_order_id')
    payment_id = data.get('razorpay_payment_id')
    signature = data.get('razorpay_signature')
    plan_code = data.get('plan_type', 'standard')

    if not (order_id and payment_id):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'status': 'error', 'message': 'Missing payment credentials'}, status=400)
        messages.error(request, "Incomplete payment data received.")
        return redirect('subscriptions:failed')

    is_valid = verify_razorpay_signature(order_id, payment_id, signature or '')

    if is_valid:
        now = timezone.now()
        plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
        plan_info = plans.get(plan_code, plans.get('combo', {
            'name': 'Complete Trader',
            'price': 11999,
            'duration_days': 365
        }))

        duration_days = plan_info.get('duration_days', 365)
        price = plan_info.get('price', 11999)
        plan_name = f"{plan_info.get('name')} ({duration_days} Days)"

        # Extend if already active, or start fresh from now
        start_date = now
        existing_sub = request.user.active_subscription
        if existing_sub and existing_sub.end_date > now:
            start_date = existing_sub.end_date
            end_date = existing_sub.end_date + timedelta(days=duration_days)
        else:
            end_date = now + timedelta(days=duration_days)

        subscription = Subscription.objects.create(
            user=request.user,
            plan_type=plan_code,
            plan_name=plan_name,
            amount_paid=price,
            currency='INR',
            start_date=start_date,
            end_date=end_date,
            status='ACTIVE',
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature or 'simulated_signature'
        )

        messages.success(request, f"🎉 Payment successful! Your {plan_info.get('name')} subscription is now active.")

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'status': 'success',
                'redirect_url': f'/subscriptions/success/?sub_id={subscription.id}'
            })
        return redirect(f"/subscriptions/success/?sub_id={subscription.id}")
    else:
        messages.error(request, "Payment signature verification failed. Please contact support if your account was debited.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'status': 'error', 'message': 'Signature verification failed'}, status=400)
        return redirect('subscriptions:failed')



@login_required
def payment_success_view(request):
    """Payment success page showing newly activated subscription details."""
    sub_id = request.GET.get('sub_id')
    subscription = None
    if sub_id:
        subscription = Subscription.objects.filter(id=sub_id, user=request.user).first()
    if not subscription:
        subscription = request.user.active_subscription

    return render(request, 'subscriptions/success.html', {
        'subscription': subscription
    })


@login_required
def payment_failed_view(request):
    """Payment failed page."""
    return render(request, 'subscriptions/failure.html', {})


@login_required
def my_subscription_view(request):
    """Subscription status and history page."""
    subscriptions = request.user.subscriptions.all().order_by('-created_at')
    active_sub = request.user.active_subscription
    
    return render(request, 'subscriptions/my_subscription.html', {
        'subscriptions': subscriptions,
        'active_sub': active_sub,
        'has_active_subscription': request.user.has_active_subscription,
        'days_remaining': request.user.subscription_days_remaining,
    })
