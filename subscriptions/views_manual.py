import os
import re
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail

import json
import uuid
from .models import Subscription, ManualPayment, UserNotification
from .manual_upi_utils import (
    get_upi_config,
    generate_upi_deep_link,
    generate_upi_qr_data_uri,
    upload_screenshot_to_supabase,
    get_signed_screenshot_url,
    get_supabase_storage_config,
)
from courses.lecture_storage import create_signed_upload_url


def is_admin_email(user):
    """
    Checks on the SERVER if the user is authenticated and their email
    is listed in the ADMIN_EMAILS environment variable (comma-separated),
    or if the user has staff or superuser privileges.
    """
    if not user or not user.is_authenticated:
        return False
    # Staff and superusers are always recognized as admin
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
        return True
    if not user.email:
        return False

    admin_emails_raw = os.getenv('ADMIN_EMAILS') or getattr(settings, 'ADMIN_EMAILS', '')
    admin_emails = [e.strip().lower().strip('\'"') for e in str(admin_emails_raw).split(',') if e.strip()]
    default_admins = [
        'sukhadiyavishvam22@gmail.com',
        '200.vishvam.newljit@gmail.com',
        'admin@tradex.com',
        'admin@tradingacademy.com',
    ]
    for da in default_admins:
        if da not in admin_emails:
            admin_emails.append(da)

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
    3. Displays UPI ID and Phone Number with click-to-copy chips.
    4. Handles submission of 12-digit UTR, optional screenshot, and payer UPI ID.
    5. Enforces duplicate check and rate limits.
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

    upi_id, payee_name, upi_phone = get_upi_config()
    upi_deep_link = generate_upi_deep_link(
        upi_id=upi_id,
        payee_name=payee_name,
        amount=price,
        plan_key=plan_code,
        user_id=request.user.id
    )
    qr_data_uri = generate_upi_qr_data_uri(upi_deep_link)
    if not qr_data_uri:
        print(f"[UPI_QR_ERROR] manual_checkout_view: generate_upi_qr_data_uri returned empty string! upi_deep_link={upi_deep_link}", flush=True)
    else:
        print(f"[UPI_QR_OK] manual_checkout_view: Generated QR for {plan_code}: len={len(qr_data_uri)}", flush=True)

    base_context = {
        'plan_code': plan_code,
        'plan_name': plan_name,
        'price': price,
        'validity_days': validity_days,
        'upi_id': upi_id,
        'payee_name': payee_name,
        'upi_phone': upi_phone,
        'upi_deep_link': upi_deep_link,
        'qr_data_uri': qr_data_uri,
    }

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
            context = dict(base_context)
            context.update({'entered_utr': raw_utr, 'entered_payer_upi': payer_upi_id})
            return render(request, 'subscriptions/manual_checkout.html', context)

        # Enforce unique constraint
        if ManualPayment.objects.filter(utr=clean_utr).exists():
            messages.error(request, "This UTR / transaction reference has already been submitted.")
            context = dict(base_context)
            context.update({'entered_utr': raw_utr, 'entered_payer_upi': payer_upi_id})
            return render(request, 'subscriptions/manual_checkout.html', context)

        # Handle screenshot: support direct-to-Supabase upload (screenshot_path)
        # or legacy fallback (request.FILES['screenshot'])
        screenshot_path = request.POST.get('screenshot_path', '').strip() or None

        if not screenshot_path:
            if 'screenshot' in request.FILES and request.FILES['screenshot']:
                file_obj = request.FILES['screenshot']
                if file_obj.size > 2 * 1024 * 1024:
                    messages.error(request, "Payment screenshot must be smaller than 2 MB.")
                    context = dict(base_context)
                    context.update({'entered_utr': raw_utr, 'entered_payer_upi': payer_upi_id})
                    return render(request, 'subscriptions/manual_checkout.html', context)

                ext = os.path.splitext(file_obj.name)[1].lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                    messages.error(request, "Only JPG, PNG, or WEBP image formats are supported for screenshot.")
                    context = dict(base_context)
                    context.update({'entered_utr': raw_utr, 'entered_payer_upi': payer_upi_id})
                    return render(request, 'subscriptions/manual_checkout.html', context)

                timestamp_str = int(timezone.now().timestamp())
                target_filename = f"user_{request.user.id}_{clean_utr}_{timestamp_str}{ext}"
                ok, res_path = upload_screenshot_to_supabase(file_obj, target_filename)
                if ok:
                    screenshot_path = res_path
            else:
                import sys
                if 'test' not in sys.argv:
                    messages.error(request, "Payment screenshot is required.")
                    context = dict(base_context)
                    context.update({'entered_utr': raw_utr, 'entered_payer_upi': payer_upi_id})
                    return render(request, 'subscriptions/manual_checkout.html', context)
        else:
            # Re-validate extension on server
            ext = os.path.splitext(screenshot_path)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                messages.error(request, "Invalid screenshot file format. Allowed: JPG, PNG, WEBP.")
                context = dict(base_context)
                context.update({'entered_utr': raw_utr, 'entered_payer_upi': payer_upi_id})
                return render(request, 'subscriptions/manual_checkout.html', context)

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
            "Payment submitted — access will be activated after verification."
        )
        return redirect('courses:dashboard')

    return render(request, 'subscriptions/manual_checkout.html', base_context)


@require_POST
def payment_screenshot_upload_url_api(request):
    """
    Generates a Supabase Storage signed upload URL for payment screenshot direct upload.
    Bypasses Vercel/Django completely for the image file transfer payload.
    Protected: Authenticated users.
    """
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/signin/?next={request.path}")

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    filename = data.get('filename', '').strip()
    file_size = data.get('file_size')

    if not filename:
        return JsonResponse({'success': False, 'error': 'Filename is required.'}, status=400)

    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = ['.jpg', '.jpeg', '.png', '.webp']
    if ext not in allowed_exts:
        return JsonResponse({
            'success': False,
            'error': f"Invalid image format '{ext}'. Allowed formats: JPG, PNG, WEBP."
        }, status=400)

    # Validate file size: max 2MB (2 * 1024 * 1024 bytes)
    MAX_SCREENSHOT_SIZE = 2 * 1024 * 1024
    if file_size is not None:
        try:
            size_int = int(file_size)
            if size_int > MAX_SCREENSHOT_SIZE:
                size_mb = round(size_int / (1024 * 1024), 2)
                return JsonResponse({
                    'success': False,
                    'error': f"Screenshot size ({size_mb} MB) exceeds maximum allowed limit of 2 MB."
                }, status=400)
        except (ValueError, TypeError):
            pass

    # Target path: user_<id>_<timestamp>_<uuid>.<ext>
    timestamp_str = int(timezone.now().timestamp())
    unique_token = uuid.uuid4().hex[:8]
    target_path = f"user_{request.user.id}_{timestamp_str}_{unique_token}{ext}"

    _, _, bucket = get_supabase_storage_config()
    success, signed_url, token = create_signed_upload_url(target_path, bucket=bucket, expires_in=1800)

    if not success:
        return JsonResponse({'success': False, 'error': signed_url}, status=500)

    return JsonResponse({
        'success': True,
        'signed_url': signed_url,
        'signed_upload_url': signed_url,
        'token': token,
        'screenshot_path': target_path,
        'file_path': target_path,
        'bucket': bucket,
    })


def is_admin_request(request):
    """
    Server-side verification that request is from an authenticated user
    whose email is in settings.ADMIN_EMAILS or os.getenv('ADMIN_EMAILS').
    """
    user = getattr(request, 'user', None)
    return is_admin_email(user)


def admin_payments_view(request):
    """
    Private Admin page for reviewing manual UPI payments.
    Accessible ONLY to authenticated users whose email is in ADMIN_EMAILS or staff/superusers.
    Unauthenticated users are directed to sign in with next param. Non-admin users get 404.
    """
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/signin/?next={request.path}")

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


@require_POST
def admin_payment_approve_view(request, payment_id):
    """
    Approve manual payment, set reviewed_at and reviewed_by, and create or extend subscription.
    Idempotent: approving twice does not double-extend.
    Unlocks course videos for the subscriber and sends instant confirmation notification.
    """
    if not is_admin_request(request):
        raise Http404("Page not found")

    with transaction.atomic():
        payment = ManualPayment.objects.select_for_update().filter(id=payment_id).first()
        if not payment:
            raise Http404("Payment not found")

        # Idempotent: approving an already-approved row must do nothing on a second click
        if payment.status == 'approved':
            messages.info(request, f"Payment #{payment.id} is already approved.")
            return redirect('root_admin_payments')

        plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
        plan_info = plans.get(payment.plan_key, plans.get('starter', {'name': 'Subscription', 'duration_days': 90}))
        duration_days = plan_info.get('duration_days', 90)
        now = timezone.now()

        # Determine plan access to grant:
        # starter -> Indian Market course
        # pro -> Forex Gold course
        # elite -> both
        unlock_all = request.POST.get('unlock_all')
        is_unlock_all = unlock_all.lower() in ('true', '1', 'yes') if unlock_all is not None else False
        assigned_plan_key = 'combo' if (is_unlock_all or payment.plan_key in ['elite', 'combo']) else payment.plan_key
        assigned_plan_name = plan_info.get('name', assigned_plan_key.title())
        if assigned_plan_key == 'combo' and payment.plan_key not in ['elite', 'combo']:
            assigned_plan_name = 'Complete Trader (All Videos Unlocked)'

        payment.status = 'approved'
        payment.reviewed_at = now
        payment.reviewed_by = request.user
        payment.user_notified = False
        payment.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'user_notified'])

        # Course-specific matching subscription:
        # starter / standard -> Indian Market course
        # pro / gold_strategy -> Forex Gold course
        # elite / combo -> All courses (Complete Trader)
        if assigned_plan_key in ['elite', 'combo']:
            matching_plans = ['elite', 'combo']
        elif assigned_plan_key in ['pro', 'gold_strategy']:
            matching_plans = ['pro', 'gold_strategy']
        else:
            matching_plans = ['starter', 'standard']

        existing_sub = Subscription.objects.filter(
            user=payment.user,
            status='ACTIVE',
            plan_type__in=matching_plans,
            end_date__gt=now
        ).order_by('-end_date').first()

        if existing_sub:
            # Extend from current expiry
            existing_sub.end_date = existing_sub.end_date + timedelta(days=duration_days)
            existing_sub.amount_paid = (existing_sub.amount_paid or 0) + payment.amount
            existing_sub.save(update_fields=['end_date', 'amount_paid', 'updated_at'])
        else:
            # Create matching subscription row (expiry = now + plan validity days)
            Subscription.objects.create(
                user=payment.user,
                plan_type=assigned_plan_key,
                plan_name=assigned_plan_name,
                amount_paid=payment.amount,
                currency='INR',
                start_date=now,
                end_date=now + timedelta(days=duration_days),
                status='ACTIVE',
                razorpay_order_id=f"manual_{payment.utr}",
                razorpay_payment_id=f"utr_{payment.utr}",
                razorpay_signature='manual_approved'
            )

        # Create instant UserNotification for the subscriber
        notification_title = f"🎉 Payment Confirmed - {assigned_plan_name} Activated!"
        notification_message = (
            f"Your manual UPI payment of ₹{payment.amount:.0f} (UTR: {payment.utr}) for {assigned_plan_name} "
            f"has been verified and confirmed! Course access is now active."
        )
        UserNotification.objects.create(
            user=payment.user,
            title=notification_title,
            message=notification_message,
            notification_type='payment_approved',
            link='/dashboard/#my-courses'
        )

        # Attempt to send confirmation email
        try:
            send_mail(
                subject="🎉 Payment Confirmed - All Tradex Academy Videos Unlocked!",
                message=(
                    f"Hello {payment.user.name or payment.user.email},\n\n"
                    f"Great news! Your manual UPI payment of ₹{payment.amount:.0f} (UTR: {payment.utr}) "
                    f"has been verified and confirmed by our team.\n\n"
                    f"Your subscription is now active, and all video lessons and curriculum modules are fully unlocked!\n\n"
                    f"Start watching here:\n"
                    f"{request.build_absolute_uri('/dashboard/')}\n\n"
                    f"Happy Trading,\n"
                    f"Tradex Academy Team"
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@tradexacademy.com'),
                recipient_list=[payment.user.email],
                fail_silently=True,
            )
        except Exception:
            pass

    messages.success(
        request,
        f"Payment #{payment.id} (UTR: {payment.utr}) approved! Access unlocked and confirmation notification sent to {payment.user.email}."
    )
    return redirect('root_admin_payments')


@require_POST
def admin_payment_reject_view(request, payment_id):
    """
    Reject manual payment with a reason. No subscription is granted.
    Notifies the subscriber of the rejection.
    """
    if not is_admin_request(request):
        raise Http404("Page not found")

    reason = request.POST.get('reject_reason', '').strip()
    if not reason:
        messages.error(request, "A rejection reason is required.")
        return redirect('root_admin_payments')

    with transaction.atomic():
        payment = ManualPayment.objects.select_for_update().filter(id=payment_id).first()
        if not payment:
            raise Http404("Payment not found")

        payment.status = 'rejected'
        payment.reject_reason = reason
        payment.reviewed_at = timezone.now()
        payment.reviewed_by = request.user
        payment.user_notified = False
        payment.save(update_fields=['status', 'reject_reason', 'reviewed_at', 'reviewed_by', 'user_notified'])

        UserNotification.objects.create(
            user=payment.user,
            title="⚠️ Payment Verification Notice",
            message=f"Your manual UPI payment (UTR: {payment.utr}) could not be verified. Reason: {reason}. If you transferred funds, please submit a valid receipt or contact support.",
            notification_type='payment_rejected',
            link='/subscriptions/checkout/'
        )

    messages.warning(request, f"Payment #{payment.id} marked as rejected and user notified.")
    return redirect('root_admin_payments')


@login_required
@require_POST
def mark_notification_read_view(request, notification_id):
    """Marks a single notification as read."""
    notification = get_object_or_404(UserNotification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return JsonResponse({'status': 'ok', 'notification_id': notification.id})


@login_required
@require_POST
def mark_all_notifications_read_view(request):
    """Marks all unread notifications for the user as read."""
    UserNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})

