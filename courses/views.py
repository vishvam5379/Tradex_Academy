from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, Http404
from django.contrib import messages
from django.utils import timezone
import json

from .models import Category, SubCategory, Video, WatchProgress, CommunityChannel, CommunityMessage, Lecture
from .lecture_storage import get_signed_lecture_url


def user_has_combo_access(user):
    """Helper function to check if user has active Complete Trader (₹11,999) subscription or staff privileges."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    active_sub = getattr(user, 'active_subscription', None)
    return bool(active_sub and active_sub.plan_type == 'combo' and active_sub.is_currently_active)



def landing_page(request):
    """Public landing page showcasing the academy, curriculum, and subscription plan."""
    try:
        categories = Category.objects.prefetch_related('subcategories__videos').all().order_by('order')
        total_videos = Video.objects.count()
        total_subcategories = SubCategory.objects.count()
        preview_videos = Video.objects.filter(is_free_preview=True)[:3]
    except Exception:
        categories = []
        total_videos = 0
        total_subcategories = 0
        preview_videos = []

    return render(request, 'courses/landing.html', {
        'categories': categories,
        'total_videos': total_videos,
        'total_subcategories': total_subcategories,
        'preview_videos': preview_videos,
    })


@login_required
def dashboard_home(request):
    """LMS Dashboard matching the requested subscription, courses, community, and payment layout."""
    subcategories = SubCategory.objects.select_related('parent').prefetch_related('videos').all().order_by('order')
    
    subcategories_data = []
    for sub in subcategories:
        is_accessible = sub.is_accessible_by(request.user)
        v_count = sub.videos.count()
        c_count = WatchProgress.objects.filter(user=request.user, video__sub_category=sub, completed=True).count()
        progress_pct = round((c_count / v_count * 100)) if v_count > 0 else 0
        
        # Get first video for continue button
        first_video = sub.videos.order_by('order', 'id').first()
        
        subcategories_data.append({
            'obj': sub,
            'is_accessible': is_accessible,
            'video_count': v_count,
            'completed_count': c_count,
            'progress_pct': progress_pct,
            'first_video': first_video,
        })
    
    # Recent watch progress
    recent_watched = WatchProgress.objects.filter(
        user=request.user
    ).select_related('video', 'video__sub_category', 'video__sub_category__parent').order_by('-updated_at').first()
    
    # Active & all payments
    active_sub = request.user.active_subscription
    if not active_sub:
        active_sub = request.user.subscriptions.filter(status='ACTIVE').order_by('-end_date').first()

    if not active_sub and (request.user.is_staff or request.user.is_superuser):
        from subscriptions.models import Subscription
        from datetime import timedelta
        now = timezone.now()
        active_sub, _ = Subscription.objects.get_or_create(
            user=request.user,
            status='ACTIVE',
            defaults={
                'plan_type': 'combo',
                'plan_name': 'Complete Trader',
                'amount_paid': 11999.00,
                'start_date': now,
                'end_date': now + timedelta(days=365)
            }
        )

    all_payments = request.user.subscriptions.all().order_by('-created_at')
    last_payment = all_payments.filter(status='ACTIVE').first() or all_payments.first()

    # Calculate days remaining
    if active_sub and active_sub.end_date:
        diff = active_sub.end_date - timezone.now()
        days_remaining = max(0, diff.days + (1 if diff.seconds > 0 else 0))
    else:
        days_remaining = 0

    # Community Access restriction: Only ₹11,999 Complete Trader Users (or staff/superusers)
    has_combo_access = bool(
        request.user.is_staff or 
        request.user.is_superuser or 
        (active_sub and active_sub.plan_type == 'combo' and active_sub.is_currently_active)
    )

    # Exclusive Community Trade Setups & Analysis Data
    todays_setups = [
        {
            'id': 1,
            'market': 'Forex',
            'symbol': 'XAU/USD (Gold Spot)',
            'type': 'BUY LIMIT / LONG',
            'entry': '2,580.50 - 2,582.00',
            'sl': '2,572.00',
            'tp1': '2,595.00',
            'tp2': '2,610.00',
            'rr': '1 : 3.2',
            'status': 'ACTIVE',
            'time': 'Today, 09:15 AM',
            'timeframe': '15m / 1h',
            'strategy': 'Pure Price Action & Gold Movement Strategy',
            'notes': 'Gold holding key demand zone after London session sweep. Look for bullish candle confirmation on 5m chart.',
            'badge': 'HIGH PROBABILITY',
        },
        {
            'id': 2,
            'market': 'Indian Market',
            'symbol': 'NIFTY 50 OCT FUT',
            'type': 'BUY / CALL',
            'entry': '25,320',
            'sl': '25,240',
            'tp1': '25,450',
            'tp2': '25,560',
            'rr': '1 : 2.8',
            'status': 'ACTIVE',
            'time': 'Today, 10:30 AM',
            'timeframe': '15m',
            'strategy': 'Opening Range Breakout & VWAP Rejection',
            'notes': 'Nifty bouncing off 20 EMA with volume spike. Trail stop loss to cost once TP1 is achieved.',
            'badge': 'BREAKOUT',
        },
    ]

    forex_setups = [
        {
            'id': 101,
            'symbol': 'XAU/USD (Gold)',
            'type': 'BUY / LONG',
            'entry': '2,580.50',
            'sl': '2,572.00',
            'tp': '2,610.00',
            'timeframe': '1h',
            'strategy': 'Forex Gold Movement Strategy (₹10,000 Module)',
            'status': 'ACTIVE',
            'date': 'Today',
        },
        {
            'id': 102,
            'symbol': 'EUR/USD',
            'type': 'SELL / SHORT',
            'entry': '1.10850',
            'sl': '1.11120',
            'tp': '1.10200',
            'timeframe': '4h',
            'strategy': 'Session High Liquidity Sweep',
            'status': 'ACTIVE',
            'date': 'Yesterday',
        },
    ]

    indian_setups = [
        {
            'id': 201,
            'symbol': 'BANKNIFTY 52000 CE',
            'type': 'BUY / LONG',
            'entry': '₹340',
            'sl': '₹290',
            'tp': '₹480',
            'timeframe': '5m / 15m',
            'strategy': 'Options Buying Momentum',
            'status': 'ACTIVE',
            'date': 'Today',
        },
        {
            'id': 202,
            'symbol': 'RELIANCE FUT',
            'type': 'BUY / LONG',
            'entry': '₹2,980',
            'sl': '₹2,950',
            'tp': '₹3,050',
            'timeframe': 'Daily',
            'strategy': 'Stock Futures Swing Strategy',
            'status': 'ACTIVE',
            'date': 'Yesterday',
        },
    ]

    mentor_analysis = [
        {
            'title': 'Gold Spot (XAU/USD) Weekly Bias & Macro Structure',
            'date': '17 Sep 2026',
            'author': 'Senior Mentor (Tradex)',
            'content': 'Gold is currently trading inside a prime accumulation channel on the 4H timeframe. Watch for price action confirmation near 2,580 before entering long toward 2,610+.',
            'key_levels': 'Key Support: 2,575 | Key Resistance: 2,605 & 2,620',
        },
        {
            'title': 'Indian Market Outlook: Nifty & Bank Nifty Expiry Strategy',
            'date': '16 Sep 2026',
            'author': 'Senior Mentor (Tradex)',
            'content': 'Bank Nifty has formed a higher-low structure on the 15-minute timeframe. Options buyers should focus on pullback entries near VWAP rather than chasing green candles.',
            'key_levels': 'Nifty Resistance: 25,500 | Bank Nifty Support: 51,800',
        },
    ]

    previous_setups = [
        {
            'symbol': 'XAU/USD (Gold)',
            'type': 'BUY LONG',
            'entry': '2,545.00',
            'exit': '2,585.00',
            'pips_pts': '+400 Pips (+4.0%)',
            'rr': '1 : 4.0',
            'outcome': 'TARGET 2 HIT ✅',
            'date': '15 Sep 2026',
        },
        {
            'symbol': 'NIFTY FUT',
            'type': 'BUY LONG',
            'entry': '25,100',
            'exit': '25,280',
            'pips_pts': '+180 Points',
            'rr': '1 : 3.0',
            'outcome': 'TARGET 2 HIT ✅',
            'date': '14 Sep 2026',
        },
        {
            'symbol': 'BANKNIFTY 51500 CE',
            'type': 'BUY CALL',
            'entry': '₹280',
            'exit': '₹420',
            'pips_pts': '+140 Points (+50%)',
            'rr': '1 : 2.8',
            'outcome': 'TARGET 1 HIT ✅',
            'date': '12 Sep 2026',
        },
    ]

    channels = CommunityChannel.objects.all().order_by('order')
    community_messages = CommunityMessage.objects.select_related('user', 'channel', 'parent_reply', 'parent_reply__user').order_by('created_at')

    active_subscriptions = list(request.user.subscriptions.filter(status='ACTIVE', end_date__gt=timezone.now()).order_by('-created_at'))
    pending_order_id = request.GET.get('order')
    manual_payments = request.user.manual_payments.all().order_by('-created_at')

    # Real Admin-Managed Lectures from Supabase Storage
    indian_market_lectures = list(Lecture.objects.filter(course='indian_market').order_by('position', 'id'))
    forex_gold_lectures = list(Lecture.objects.filter(course='forex_gold').order_by('position', 'id'))

    active_plan_types = [s.plan_type.lower() for s in active_subscriptions] if active_subscriptions else []
    if active_sub and active_sub.plan_type:
        active_plan_types.append(active_sub.plan_type.lower())

    can_access_indian_market = bool(
        request.user.is_staff or request.user.is_superuser or
        any(p in ['standard', 'starter', 'combo', 'elite'] for p in active_plan_types)
    )
    can_access_forex_gold = bool(
        request.user.is_staff or request.user.is_superuser or
        any(p in ['gold_strategy', 'pro', 'combo', 'elite'] for p in active_plan_types)
    )

    return render(request, 'courses/dashboard.html', {
        'subcategories_data': subcategories_data,
        'has_subscription': bool(active_sub and active_sub.end_date and active_sub.is_currently_active),
        'active_sub': active_sub,
        'active_subscriptions': active_subscriptions,
        'pending_order_id': pending_order_id,
        'days_remaining': days_remaining,
        'recent_watched': recent_watched,
        'last_payment': last_payment,
        'all_payments': all_payments,
        'manual_payments': manual_payments,
        'has_combo_access': has_combo_access,
        'channels': channels,
        'community_messages': community_messages,
        'indian_market_lectures': indian_market_lectures,
        'forex_gold_lectures': forex_gold_lectures,
        'can_access_indian_market': can_access_indian_market,
        'can_access_forex_gold': can_access_forex_gold,
    })



@login_required
def category_video_list(request, category_slug, subcategory_slug):
    """
    Video listing page for leaf categories:
    - Forex -> Spot Gold (XAU/USD)
    - Forex -> Forex Gold Strategy & Strategy Indicator
    - Indian Market -> Futures
    - Indian Market -> Options
    - Indian Market -> Stock Trading
    """
    category = get_object_or_404(Category, slug=category_slug)
    subcategory = get_object_or_404(SubCategory, parent=category, slug=subcategory_slug)
    videos = subcategory.videos.all().order_by('order', 'id')
    
    is_subscribed = subcategory.is_accessible_by(request.user)
    recommended_plan = 'pro' if (subcategory.tier_required in ('gold_strategy', 'pro') or category.slug == 'forex') else 'starter'
    
    # User's watched video IDs
    watched_video_ids = set(
        WatchProgress.objects.filter(user=request.user, completed=True).values_list('video_id', flat=True)
    )

    return render(request, 'courses/category_videos.html', {
        'category': category,
        'subcategory': subcategory,
        'videos': videos,
        'is_subscribed': is_subscribed,
        'recommended_plan': recommended_plan,
        'watched_video_ids': watched_video_ids,
    })


@login_required
def video_player(request, category_slug, subcategory_slug, video_id):
    """
    Video player page with tier-aware server-side paywall validation.
    Restricts access if user doesn't have an active subscription covering this tier.
    """
    category = get_object_or_404(Category, slug=category_slug)
    subcategory = get_object_or_404(SubCategory, parent=category, slug=subcategory_slug)
    video = get_object_or_404(Video, id=video_id, sub_category=subcategory)
    
    is_subscribed = subcategory.is_accessible_by(request.user)

    # Server-side paywall verification: check active subscription covering this course
    if not is_subscribed:
        plan_code = 'pro' if (subcategory.tier_required in ('gold_strategy', 'pro') or category.slug == 'forex') else 'starter'
        messages.warning(
            request,
            "Active subscription required to watch this lecture."
        )
        return redirect(f"/subscriptions/pay/{plan_code}/")

    # All playlist videos in this subcategory
    playlist_videos = subcategory.videos.all().order_by('order', 'id')
    
    # Next & Previous video links
    video_list = list(playlist_videos)
    current_index = video_list.index(video) if video in video_list else -1
    prev_video = video_list[current_index - 1] if current_index > 0 else None
    next_video = video_list[current_index + 1] if current_index >= 0 and current_index < len(video_list) - 1 else None

    # Track watch progress
    progress, _ = WatchProgress.objects.get_or_create(user=request.user, video=video)

    return render(request, 'courses/video_player.html', {
        'category': category,
        'subcategory': subcategory,
        'video': video,
        'playlist_videos': playlist_videos,
        'prev_video': prev_video,
        'next_video': next_video,
        'progress': progress,
        'is_subscribed': is_subscribed,
    })


@login_required
@require_POST
def mark_video_complete_api(request, video_id):
    """AJAX endpoint to toggle lesson completion status."""
    video = get_object_or_404(Video, id=video_id)
    if not video.sub_category.is_accessible_by(request.user):
        return JsonResponse({'status': 'error', 'message': 'Active subscription required.'}, status=403)

    progress, _ = WatchProgress.objects.get_or_create(user=request.user, video=video)
    progress.completed = not progress.completed
    progress.save()

    return JsonResponse({
        'status': 'success',
        'completed': progress.completed,
        'video_id': video.id
    })


@login_required
def community_view(request):
    """
    Dedicated Telegram-style Community page.
    Restricted strictly to users with active ₹11,999 Complete Trader plan or staff/superusers.
    """
    has_combo = user_has_combo_access(request.user)
    channels = CommunityChannel.objects.all().order_by('order')
    active_channel_slug = request.GET.get('channel', 'trade-setups')
    active_channel = channels.filter(slug=active_channel_slug).first() or channels.first()

    messages_qs = []
    if has_combo and active_channel:
        messages_qs = CommunityMessage.objects.filter(channel=active_channel).select_related('user', 'parent_reply', 'parent_reply__user').order_by('created_at')

    return render(request, 'courses/community.html', {
        'has_combo_access': has_combo,
        'channels': channels,
        'active_channel': active_channel,
        'messages_list': messages_qs,
    })


@login_required
def api_get_community_messages(request, channel_slug):
    """Fetch messages for a specific community channel (AJAX API)."""
    if not user_has_combo_access(request.user):
        return JsonResponse({'status': 'error', 'message': 'Community access is restricted to active Complete Trader members.'}, status=403)
    
    channel = get_object_or_404(CommunityChannel, slug=channel_slug)
    messages_qs = CommunityMessage.objects.filter(channel=channel).select_related('user', 'parent_reply', 'parent_reply__user').order_by('created_at')

    data = []
    for msg in messages_qs:
        data.append({
            'id': msg.id,
            'user_name': msg.user.name or msg.user.email.split('@')[0],
            'user_email': msg.user.email,
            'is_mentor': msg.is_mentor_post or msg.user.is_staff or msg.user.is_superuser,
            'content': msg.content,
            'is_trade_setup': msg.is_trade_setup,
            'setup_symbol': msg.setup_symbol,
            'setup_entry': msg.setup_entry,
            'setup_sl': msg.setup_sl,
            'setup_tp1': msg.setup_tp1,
            'setup_tp2': msg.setup_tp2,
            'setup_chart_text': msg.setup_chart_text,
            'created_at': msg.created_at.strftime('%I:%M %p'),
            'date': msg.created_at.strftime('%d %b %Y'),
            'parent_reply_id': msg.parent_reply_id,
            'parent_user_name': (msg.parent_reply.user.name or msg.parent_reply.user.email.split('@')[0]) if msg.parent_reply else None,
            'parent_content': msg.parent_reply.content[:60] if msg.parent_reply else None,
        })

    return JsonResponse({
        'status': 'success',
        'channel': {'slug': channel.slug, 'name': channel.name, 'is_mentor_only': channel.is_mentor_only_posting},
        'messages': data
    })


@login_required
@require_POST
def api_send_community_message(request, channel_slug):
    """Post a new message in a community channel."""
    if not user_has_combo_access(request.user):
        return JsonResponse({'status': 'error', 'message': 'Community access is restricted to active Complete Trader members.'}, status=403)

    channel = get_object_or_404(CommunityChannel, slug=channel_slug)

    # Check if channel is mentor-only posting
    is_staff = request.user.is_staff or request.user.is_superuser
    if channel.is_mentor_only_posting and not is_staff:
        return JsonResponse({'status': 'error', 'message': 'Only staff/mentors can post in Announcements.'}, status=403)

    try:
        payload = json.loads(request.body) if request.body else request.POST
    except json.JSONDecodeError:
        payload = request.POST

    content = payload.get('content', '').strip()
    is_trade_setup = bool(payload.get('is_trade_setup')) and is_staff
    
    if not content and not is_trade_setup:
        return JsonResponse({'status': 'error', 'message': 'Message content cannot be empty.'}, status=400)

    parent_reply_id = payload.get('parent_reply_id')
    parent_reply = None
    if parent_reply_id:
        parent_reply = CommunityMessage.objects.filter(id=parent_reply_id, channel=channel).first()

    msg = CommunityMessage.objects.create(
        channel=channel,
        user=request.user,
        content=content or f"📊 Trade Setup: {payload.get('setup_symbol', '')}",
        is_mentor_post=is_staff,
        is_trade_setup=is_trade_setup,
        setup_symbol=payload.get('setup_symbol', ''),
        setup_entry=payload.get('setup_entry', ''),
        setup_sl=payload.get('setup_sl', ''),
        setup_tp1=payload.get('setup_tp1', ''),
        setup_tp2=payload.get('setup_tp2', ''),
        setup_chart_text=payload.get('setup_chart_text', ''),
        parent_reply=parent_reply
    )

    return JsonResponse({
        'status': 'success',
        'message': {
            'id': msg.id,
            'user_name': msg.user.name or msg.user.email.split('@')[0],
            'is_mentor': msg.is_mentor_post or is_staff,
            'content': msg.content,
            'is_trade_setup': msg.is_trade_setup,
            'setup_symbol': msg.setup_symbol,
            'setup_entry': msg.setup_entry,
            'setup_sl': msg.setup_sl,
            'setup_tp1': msg.setup_tp1,
            'setup_tp2': msg.setup_tp2,
            'setup_chart_text': msg.setup_chart_text,
            'created_at': msg.created_at.strftime('%I:%M %p'),
            'parent_reply_id': msg.parent_reply_id,
        }
    })


@login_required
@require_POST
def api_delete_community_message(request, message_id):
    """Delete a community message (staff or author only)."""
    msg = get_object_or_404(CommunityMessage, id=message_id)
    if not (request.user.is_staff or request.user.is_superuser or msg.user == request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
    
    msg.delete()
    return JsonResponse({'status': 'success', 'message_id': message_id})


@login_required
def lecture_player_view(request, lecture_id, course_slug=None):
    """
    Dedicated video player for real admin-managed lectures stored in Supabase.
    Performs server-side active subscription verification:
      - Starter / Standard -> Indian Market Mastery
      - Pro / Gold Strategy -> Forex & Gold Mastery
      - Elite / Combo -> All courses
      - Staff / Superuser -> All courses
    Generates a secure, short-lived signed URL for playback (never exposes permanent bucket URL).
    """
    lecture = get_object_or_404(Lecture, id=lecture_id)

    if not lecture.is_accessible_by(request.user):
        plan_code = 'pro' if lecture.course == 'forex_gold' else 'starter'
        course_name = lecture.get_course_display()
        messages.warning(
            request,
            f"Active subscription required to watch '{lecture.title}'. Upgrade to the {course_name} plan to unlock."
        )
        return redirect(f"/pay/{plan_code}/")

    signed_url = get_signed_lecture_url(lecture.video_path, expires_in=3600)

    # Playlist of lectures in the same course
    course_lectures = list(Lecture.objects.filter(course=lecture.course).order_by('position', 'id'))
    current_index = course_lectures.index(lecture) if lecture in course_lectures else -1
    prev_lecture = course_lectures[current_index - 1] if current_index > 0 else None
    next_lecture = course_lectures[current_index + 1] if 0 <= current_index < len(course_lectures) - 1 else None

    return render(request, 'courses/lecture_player.html', {
        'lecture': lecture,
        'signed_url': signed_url,
        'course_lectures': course_lectures,
        'prev_lecture': prev_lecture,
        'next_lecture': next_lecture,
        'course_name': lecture.get_course_display(),
        'current_index_human': current_index + 1 if current_index >= 0 else 1,
        'total_lectures': len(course_lectures),
    })


@login_required
def course_lectures_view(request, course_slug):
    """
    Displays the complete syllabus/curriculum of real lectures for a given course.
    """
    if course_slug not in ['indian_market', 'forex_gold']:
        raise Http404("Course not found")

    lectures = list(Lecture.objects.filter(course=course_slug).order_by('position', 'id'))
    course_name = "Indian Market Mastery" if course_slug == 'indian_market' else "Forex & Gold Mastery"
    recommended_plan = 'starter' if course_slug == 'indian_market' else 'pro'

    dummy_lecture = Lecture(course=course_slug)
    has_access = dummy_lecture.is_accessible_by(request.user)

    return render(request, 'courses/course_lectures.html', {
        'course_slug': course_slug,
        'course_name': course_name,
        'lectures': lectures,
        'has_access': has_access,
        'recommended_plan': recommended_plan,
        'total_count': len(lectures),
    })

