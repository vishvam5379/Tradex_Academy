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
    Select Plan -> Manual UPI Payment (/pay/<plan_key>/).
    Directs user directly to manual UPI QR verification flow.
    Razorpay payment link creation is completely disabled.
    """
    plan = plan_key or request.GET.get('plan', 'starter')
    from .views_manual import normalize_plan_key
    return redirect('root_pay_plan', plan_key=normalize_plan_key(plan))


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
    Checkout page supporting multi-tier plans with Order summary card.
    The 'Pay ₹X via UPI' button links directly to /pay/<plan_key>/.
    Razorpay orders are completely disabled.
    """
    plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
    
    plan = request.GET.get('plan', 'starter')
    from .views_manual import normalize_plan_key
    selected_plan_code = normalize_plan_key(plan)
    if selected_plan_code not in plans:
        selected_plan_code = 'starter'
    
    selected_plan = plans[selected_plan_code]
    price = selected_plan['price']
    duration_days = selected_plan['duration_days']
    
    already_active = request.user.has_active_subscription
    current_sub = request.user.active_subscription

    context = {
        'plans': plans,
        'selected_plan_code': selected_plan_code,
        'selected_plan': selected_plan,
        'price': price,
        'duration_days': duration_days,
        'payment_mode': 'manual_upi',
        'already_active': already_active,
        'current_sub': current_sub,
    }

    return render(request, 'subscriptions/checkout.html', context)


@login_required
@require_POST
def create_order_api(request):
    """API endpoint disabled. Manual UPI flow active via /pay/<plan_key>/."""
    return JsonResponse({'error': 'Razorpay checkout is disabled. Use manual UPI payment flow at /pay/<plan_key>/.'}, status=400)


@csrf_exempt
@login_required
@require_POST
def verify_payment_view(request):
    """API endpoint disabled. Manual UPI verification active via /admin/payments/."""
    return JsonResponse({'error': 'Razorpay verification is disabled. Use manual UPI payment flow at /pay/<plan_key>/.'}, status=400)


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
