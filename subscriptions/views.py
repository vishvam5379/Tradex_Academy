import os
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.utils import timezone
from django.conf import settings
from django.contrib import messages

from .models import Subscription, Order
from .utils import (
    create_razorpay_order,
    verify_razorpay_signature,
    create_razorpay_payment_link,
    verify_razorpay_webhook_signature
)


@login_required
def initiate_upi_payment(request, plan_key=None):
    """
    Select Plan -> Payment Link (UPI only)
    1. Requires login.
    2. Reads plan key, looks up price on server, creates Order record with status 'created'.
    3. Creates Razorpay UPI Payment Link (POST /v1/payment_links with upi_link: true).
    4. Redirects to returned short_url.
    Blocks duplicate active subscription for the same plan.
    """
    plan = plan_key or request.GET.get('plan', 'starter')
    payment_mode = (os.getenv('PAYMENT_MODE') or getattr(settings, 'PAYMENT_MODE', 'razorpay')).lower().strip()
    if payment_mode == 'manual_upi':
        from .views_manual import normalize_plan_key
        return redirect('subscriptions:manual_checkout', plan_key=normalize_plan_key(plan))

    plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})

    normalized_key = plan.lower().strip()
    if normalized_key in ['standard', 'starter']:
        normalized_key = 'starter'
    elif normalized_key in ['gold_strategy', 'pro']:
        normalized_key = 'pro'
    elif normalized_key in ['combo', 'elite']:
        normalized_key = 'elite'
    else:
        normalized_key = 'starter'

    plan_info = plans.get(normalized_key, plans.get('starter'))
    price = plan_info['price']
    plan_name = plan_info['name']

    # Block duplicate active subscription for same plan
    active_sub = getattr(request.user, 'active_subscription', None)
    if active_sub and active_sub.is_currently_active:
        sub_plan = active_sub.plan_type.lower()
        if sub_plan == normalized_key or sub_plan in ['elite', 'combo']:
            messages.info(request, f"You already have active access to {plan_name}.")
            return redirect('courses:dashboard')

    # Create Order record
    order = Order.objects.create(
        user=request.user,
        plan=normalized_key,
        amount=price,
        currency='INR',
        status='created'
    )

    callback_url = request.build_absolute_uri(f"/dashboard/?order={order.id}")

    link = create_razorpay_payment_link(
        amount_in_rupees=price,
        reference_id=order.id,
        user=request.user,
        callback_url=callback_url,
        plan_key=normalized_key,
        plan_name=plan_name
    )

    order.gateway_order_id = link.get('id')
    order.short_url = link.get('short_url')
    order.save(update_fields=['gateway_order_id', 'short_url'])

    if link.get('short_url'):
        return redirect(link['short_url'])

    return redirect(f"/dashboard/?order={order.id}")


@login_required
def order_status_api(request, order_id):
    """
    Returns payment status of an order for client-side verification polling.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return JsonResponse({
        'status': order.status,
        'order_id': order.id,
        'plan': order.plan,
        'paid_at': order.paid_at.isoformat() if order.paid_at else None
    })


@csrf_exempt
@require_POST
def razorpay_webhook_view(request):
    """
    Razorpay Webhook: The ONLY authority that activates or extends access.
    1. Reads RAW body and verifies X-Razorpay-Signature header via HMAC SHA256.
    2. Handles payment_link.paid and payment.captured events.
    3. Finds Order, verifies amount & currency, idempotently marks paid.
    4. Creates or extends Subscription (start = now, expiry = now + validity days; or extends from current expiry).
    5. Returns 200 quickly.
    """
    body_bytes = request.body
    signature = request.headers.get('X-Razorpay-Signature') or request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')

    if not verify_razorpay_webhook_signature(body_bytes, signature):
        return HttpResponseBadRequest("Invalid signature")

    try:
        data = json.loads(body_bytes.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    event = data.get('event')
    payload_data = data.get('payload', {})

    plink_entity = payload_data.get('payment_link', {}).get('entity', {})
    payment_entity = payload_data.get('payment', {}).get('entity', {})

    ref_id = plink_entity.get('reference_id') or payment_entity.get('notes', {}).get('order_id')
    payment_id = payment_entity.get('id') or plink_entity.get('payment_id')
    plink_id = plink_entity.get('id') or payment_entity.get('order_id')

    order = None
    if ref_id and str(ref_id).isdigit():
        order = Order.objects.filter(id=int(ref_id)).first()
    if not order and plink_id:
        order = Order.objects.filter(gateway_order_id=plink_id).first()
    if not order and payment_entity.get('notes', {}).get('order_id'):
        note_oid = payment_entity.get('notes', {}).get('order_id')
        if str(note_oid).isdigit():
            order = Order.objects.filter(id=int(note_oid)).first()

    if not order:
        return HttpResponse("Order not found or ignored", status=200)

    now = timezone.now()

    if event in ['payment_link.paid', 'payment.captured']:
        if order.status == 'paid':
            return HttpResponse("Already paid", status=200)

        amount_paid_paise = payment_entity.get('amount') or plink_entity.get('amount_paid')
        expected_paise = int(order.amount * 100)
        currency = payment_entity.get('currency') or plink_entity.get('currency', 'INR')

        if currency != 'INR' or (amount_paid_paise and int(amount_paid_paise) != expected_paise):
            order.status = 'failed'
            order.save(update_fields=['status'])
            return HttpResponse("Amount or currency mismatch", status=200)

        order.status = 'paid'
        order.paid_at = now
        if payment_id:
            order.gateway_payment_id = payment_id
        order.save(update_fields=['status', 'paid_at', 'gateway_payment_id'])

        plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
        plan_info = plans.get(order.plan, {})
        duration_days = plan_info.get('duration_days', 90)
        plan_name = f"{plan_info.get('name', order.plan.title())} ({duration_days} Days)"

        existing_sub = Subscription.objects.filter(
            user=order.user,
            status='ACTIVE',
            end_date__gt=now
        ).order_by('-end_date').first()

        if existing_sub:
            existing_sub.end_date = existing_sub.end_date + timedelta(days=duration_days)
            existing_sub.plan_type = order.plan
            existing_sub.plan_name = plan_name
            existing_sub.amount_paid = order.amount
            if payment_id:
                existing_sub.razorpay_payment_id = payment_id
            existing_sub.save()
        else:
            Subscription.objects.create(
                user=order.user,
                plan_type=order.plan,
                plan_name=plan_name,
                amount_paid=order.amount,
                currency='INR',
                start_date=now,
                end_date=now + timedelta(days=duration_days),
                status='ACTIVE',
                razorpay_order_id=order.gateway_order_id,
                razorpay_payment_id=payment_id,
                razorpay_signature='verified_via_webhook'
            )

        return HttpResponse("Payment processed successfully", status=200)

    elif event in ['payment_link.expired']:
        if order.status != 'paid':
            order.status = 'expired'
            order.save(update_fields=['status'])
        return HttpResponse("Link marked expired", status=200)

    elif event in ['payment.failed']:
        if order.status != 'paid':
            order.status = 'failed'
            order.save(update_fields=['status'])
        return HttpResponse("Payment marked failed", status=200)

    return HttpResponse("Event ignored", status=200)


@login_required
def checkout_view(request):
    """
    Redirects checkout requests to UPI payment flow:
    - 'manual_upi': goes to manual checkout page
    - 'razorpay': goes to Razorpay UPI link flow
    """
    plan = request.GET.get('plan', 'starter')
    payment_mode = (os.getenv('PAYMENT_MODE') or getattr(settings, 'PAYMENT_MODE', 'razorpay')).lower().strip()
    if payment_mode == 'manual_upi':
        from .views_manual import normalize_plan_key
        return redirect('subscriptions:manual_checkout', plan_key=normalize_plan_key(plan))
    return redirect(f"/subscriptions/pay/?plan={plan}")


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
