import os
import re
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import Http404, HttpResponseBadRequest
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from .models import Subscription, ManualPayment
from .manual_upi_utils import (
    get_upi_config,
    generate_upi_deep_link,
    generate_upi_qr_data_uri,
    upload_screenshot_to_supabase,
    get_signed_screenshot_url,
)


def is_admin_email(user):
    """
    Checks on the SERVER if the user is authenticated and their email
    is listed in the ADMIN_EMAILS environment variable (comma-separated).
    """
    if not user or not user.is_authenticated or not user.email:
        return False
    admin_emails_raw = os.getenv('ADMIN_EMAILS') or getattr(settings, 'ADMIN_EMAILS', '')
    admin_emails = [e.strip().lower() for e in admin_emails_raw.split(',') if e.strip()]
    return user.email.strip().lower() in admin_emails


def normalize_plan_key(raw_key):
    key = (raw_key or 'starter').lower().strip()
    if key in ['standard', 'starter']:
        return 'starter'
    if key in ['gold_strategy', 'pro']:
        return 'pro'
    if key in ['combo', 'elite']:
        return 'elite'
    return 'starter'


@login_required
def manual_checkout_view(request, plan_key):
    """
    Manual UPI Checkout page:
    1. Shows plan details (name, price, validity).
    2. Displays UPI QR code and 'Pay with UPI App' deep link button.
    3. Handles submission of 12-digit UTR, optional screenshot, and payer UPI ID.
    4. Enforces duplicate check and rate limits.
    """
    plan_code = normalize_plan_key(plan_key)
    plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
    plan_info = plans.get(plan_code, plans.get('starter'))

    price = plan_info['price']
    plan_name = plan_info['name']
    validity_days = plan_info['duration_days']

    # Duplicate checks:
    # 1. Active subscription covering same plan
    active_subs = request.user.subscriptions.filter(status='ACTIVE', end_date__gt=timezone.now())
    for sub in active_subs:
        if sub.grants_access_to(plan_code):
            messages.info(request, f"You already have active access to {plan_name}.")
            return redirect('courses:dashboard')

    # 2. Pending verification request for same plan
    pending_payment = ManualPayment.objects.filter(
        user=request.user,
        plan_key=plan_code,
        status='pending'
    ).first()
    if pending_payment:
        messages.info(
            request,
            f"You already have a payment under verification for {plan_name} (UTR: {pending_payment.utr})."
        )
        return redirect('courses:dashboard')

    upi_id, payee_name = get_upi_config()
    upi_deep_link = generate_upi_deep_link(
        upi_id=upi_id,
        payee_name=payee_name,
        amount=price,
        plan_key=plan_code,
        user_id=request.user.id
    )
    qr_data_uri = generate_upi_qr_data_uri(upi_deep_link)

    if request.method == 'POST':
        # Rate limit: Max 5 submissions per user per hour
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_count = ManualPayment.objects.filter(
            user=request.user,
            created_at__gte=one_hour_ago
        ).count()
        if recent_count >= 5:
            messages.error(request, "Too many submission attempts. Please wait an hour before submitting again.")
            return redirect('subscriptions:manual_checkout', plan_key=plan_code)

        raw_utr = request.POST.get('utr', '').strip()
        payer_upi_id = request.POST.get('payer_upi_id', '').strip()

        # Validate UTR: required, exactly 12 digits
        clean_utr = re.sub(r'\s+', '', raw_utr)
        if not re.match(r'^\d{12}$', clean_utr):
            messages.error(request, "Please enter a valid 12-digit UPI transaction reference / UTR number.")
            return render(request, 'subscriptions/manual_checkout.html', {
                'plan_code': plan_code,
                'plan_name': plan_name,
                'price': price,
                'validity_days': validity_days,
                'upi_id': upi_id,
                'payee_name': payee_name,
                'upi_deep_link': upi_deep_link,
                'qr_data_uri': qr_data_uri,
                'entered_utr': raw_utr,
                'entered_payer_upi': payer_upi_id,
            })

        # Enforce unique constraint
        if ManualPayment.objects.filter(utr=clean_utr).exists():
            messages.error(request, "This UTR / transaction reference has already been submitted.")
            return render(request, 'subscriptions/manual_checkout.html', {
                'plan_code': plan_code,
                'plan_name': plan_name,
                'price': price,
                'validity_days': validity_days,
                'upi_id': upi_id,
                'payee_name': payee_name,
                'upi_deep_link': upi_deep_link,
                'qr_data_uri': qr_data_uri,
                'entered_utr': raw_utr,
                'entered_payer_upi': payer_upi_id,
            })

        # Handle optional screenshot upload (JPG/PNG/WEBP, max 2MB)
        screenshot_path = None
        if 'screenshot' in request.FILES:
            file_obj = request.FILES['screenshot']
            if file_obj.size > 2 * 1024 * 1024:
                messages.error(request, "Payment screenshot must be smaller than 2 MB.")
                return render(request, 'subscriptions/manual_checkout.html', {
                    'plan_code': plan_code,
                    'plan_name': plan_name,
                    'price': price,
                    'validity_days': validity_days,
                    'upi_id': upi_id,
                    'payee_name': payee_name,
                    'upi_deep_link': upi_deep_link,
                    'qr_data_uri': qr_data_uri,
                    'entered_utr': raw_utr,
                    'entered_payer_upi': payer_upi_id,
                })

            ext = os.path.splitext(file_obj.name)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                messages.error(request, "Only JPG, PNG, or WEBP image formats are supported for screenshot.")
                return render(request, 'subscriptions/manual_checkout.html', {
                    'plan_code': plan_code,
                    'plan_name': plan_name,
                    'price': price,
                    'validity_days': validity_days,
                    'upi_id': upi_id,
                    'payee_name': payee_name,
                    'upi_deep_link': upi_deep_link,
                    'qr_data_uri': qr_data_uri,
                    'entered_utr': raw_utr,
                    'entered_payer_upi': payer_upi_id,
                })

            timestamp_str = int(timezone.now().timestamp())
            target_filename = f"user_{request.user.id}_{clean_utr}_{timestamp_str}{ext}"
            ok, res_path = upload_screenshot_to_supabase(file_obj, target_filename)
            if ok:
                screenshot_path = res_path

        # Create pending ManualPayment record
        ManualPayment.objects.create(
            user=request.user,
            plan_key=plan_code,
            amount=price,
            status='pending',
            utr=clean_utr,
            payer_upi_id=payer_upi_id or None,
            screenshot_path=screenshot_path
        )

        messages.success(
            request,
            f"Payment details for {plan_name} submitted successfully! Your access will be activated once verified."
        )
        return redirect('courses:dashboard')

    return render(request, 'subscriptions/manual_checkout.html', {
        'plan_code': plan_code,
        'plan_name': plan_name,
        'price': price,
        'validity_days': validity_days,
        'upi_id': upi_id,
        'payee_name': payee_name,
        'upi_deep_link': upi_deep_link,
        'qr_data_uri': qr_data_uri,
    })


@login_required
def admin_payments_view(request):
    """
    Private Admin page for reviewing manual UPI payments.
    Accessible ONLY to users whose email is in ADMIN_EMAILS. Returns 404 for all others.
    """
    if not is_admin_email(request.user):
        raise Http404("Page not found")

    status_filter = request.GET.get('status', 'pending')
    valid_statuses = ['pending', 'approved', 'rejected', 'all']
    if status_filter not in valid_statuses:
        status_filter = 'pending'

    queryset = ManualPayment.objects.select_related('user', 'reviewed_by').all()
    if status_filter != 'all':
        queryset = queryset.filter(status=status_filter)

    payments_data = []
    for p in queryset:
        signed_url = get_signed_screenshot_url(p.screenshot_path) if p.screenshot_path else None
        payments_data.append({
            'obj': p,
            'signed_screenshot_url': signed_url,
        })

    counts = {
        'pending': ManualPayment.objects.filter(status='pending').count(),
        'approved': ManualPayment.objects.filter(status='approved').count(),
        'rejected': ManualPayment.objects.filter(status='rejected').count(),
        'all': ManualPayment.objects.count(),
    }

    return render(request, 'subscriptions/admin_payments.html', {
        'payments_data': payments_data,
        'current_status': status_filter,
        'counts': counts,
    })


@login_required
@require_POST
def admin_payment_approve_view(request, payment_id):
    """
    Approve manual payment, set reviewed_at and reviewed_by, and create or extend subscription.
    Idempotent: approving twice does not double-extend.
    """
    if not is_admin_email(request.user):
        raise Http404("Page not found")

    payment = get_object_or_404(ManualPayment, id=payment_id)

    with transaction.atomic():
        payment = ManualPayment.objects.select_for_update().get(id=payment_id)
        if payment.status == 'approved':
            messages.info(request, f"Payment #{payment.id} is already approved.")
            return redirect('subscriptions:admin_payments')

        plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
        plan_info = plans.get(payment.plan_key, plans.get('starter'))
        duration_days = plan_info['duration_days']
        now = timezone.now()

        payment.status = 'approved'
        payment.reviewed_at = now
        payment.reviewed_by = request.user
        payment.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])

        # Activate or extend subscription
        # If user has an active subscription, extend from its current end_date
        existing_sub = Subscription.objects.filter(
            user=payment.user,
            status='ACTIVE',
            end_date__gt=now
        ).order_by('-end_date').first()

        if existing_sub:
            existing_sub.end_date = existing_sub.end_date + timedelta(days=duration_days)
            # If newly approved plan is higher tier, update plan_type
            if payment.plan_key in ['elite', 'combo'] or existing_sub.plan_type in ['starter', 'standard']:
                existing_sub.plan_type = payment.plan_key
                existing_sub.plan_name = plan_info['name']
            existing_sub.amount_paid = (existing_sub.amount_paid or 0) + payment.amount
            existing_sub.save()
        else:
            Subscription.objects.create(
                user=payment.user,
                plan_type=payment.plan_key,
                plan_name=plan_info['name'],
                amount_paid=payment.amount,
                currency='INR',
                start_date=now,
                end_date=now + timedelta(days=duration_days),
                status='ACTIVE',
                razorpay_order_id=f"manual_{payment.utr}",
                razorpay_payment_id=f"utr_{payment.utr}",
                razorpay_signature='manual_approved'
            )

    messages.success(
        request,
        f"Payment #{payment.id} (UTR: {payment.utr}) approved! Access unlocked for {payment.user.email}."
    )
    return redirect('subscriptions:admin_payments')


@login_required
@require_POST
def admin_payment_reject_view(request, payment_id):
    """
    Reject manual payment with a reason. No subscription is granted.
    """
    if not is_admin_email(request.user):
        raise Http404("Page not found")

    payment = get_object_or_404(ManualPayment, id=payment_id)
    reason = request.POST.get('reject_reason', '').strip() or 'Payment reference not found or amount incorrect.'

    with transaction.atomic():
        payment = ManualPayment.objects.select_for_update().get(id=payment_id)
        payment.status = 'rejected'
        payment.reject_reason = reason
        payment.reviewed_at = timezone.now()
        payment.reviewed_by = request.user
        payment.save(update_fields=['status', 'reject_reason', 'reviewed_at', 'reviewed_by'])

    messages.warning(request, f"Payment #{payment.id} marked as rejected.")
    return redirect('subscriptions:admin_payments')
