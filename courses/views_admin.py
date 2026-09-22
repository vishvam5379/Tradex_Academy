import os
import json
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import Http404, JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.utils.text import slugify

from subscriptions.views_manual import is_admin_email
from .models import Lecture
from .lecture_storage import (
    create_signed_upload_url,
    upload_lecture_file,
    get_signed_lecture_url,
    delete_lecture_file,
    get_lecture_bucket_name,
)

# Maximum upload limit: 500 MB (524,288,000 bytes)
# Direct browser-to-Supabase upload bypasses Vercel's 4.5MB serverless payload limit.
MAX_UPLOAD_SIZE_MB = 500
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {'.mp4', '.mov', '.webm', '.m4v'}


def is_admin_request(request):
    """Verify authenticated user is authorized as an administrator."""
    user = getattr(request, 'user', None)
    return is_admin_email(user)


@require_POST
def admin_lecture_upload_url_api(request):
    """
    Generates a Supabase Storage signed upload URL for direct browser-to-Supabase upload.
    Bypasses Vercel entirely for the file transfer payload.
    Protected: Admin only.
    """
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/signin/?next=/admin/lectures/")

    if not is_admin_request(request):
        raise Http404("Page not found")

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    filename = data.get('filename', '').strip()
    course = data.get('course', '').strip()
    title = data.get('title', '').strip()
    file_size = data.get('file_size')

    if not filename:
        return JsonResponse({'success': False, 'error': 'Filename is required.'}, status=400)

    if course not in ['indian_market', 'forex_gold']:
        return JsonResponse({'success': False, 'error': 'Please select a valid course.'}, status=400)

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse({
            'success': False,
            'error': f"Invalid video format '{ext}'. Allowed formats: MP4, MOV, WEBM, M4V."
        }, status=400)

    if file_size is not None:
        try:
            size_int = int(file_size)
            if size_int > MAX_UPLOAD_SIZE_BYTES:
                size_mb = round(size_int / (1024 * 1024), 1)
                return JsonResponse({
                    'success': False,
                    'error': f"File size ({size_mb} MB) exceeds maximum allowed limit of {MAX_UPLOAD_SIZE_MB} MB."
                }, status=400)
        except (ValueError, TypeError):
            pass

    # Target path: lectures/<course>/<uuid>[_<slug>].<ext>
    clean_uuid = uuid.uuid4().hex
    title_slug = slugify(title)[:40]
    if title_slug:
        target_path = f"lectures/{course}/{clean_uuid}_{title_slug}{ext}"
    else:
        target_path = f"lectures/{course}/{clean_uuid}{ext}"

    success, signed_url, token = create_signed_upload_url(target_path, expires_in=7200)
    if not success:
        return JsonResponse({'success': False, 'error': signed_url}, status=500)

    return JsonResponse({
        'success': True,
        'signed_url': signed_url,
        'signed_upload_url': signed_url,
        'token': token,
        'video_path': target_path,
        'target_video_path': target_path,
        'bucket': get_lecture_bucket_name(),
    })


@require_POST
def admin_lecture_confirm_api(request):
    """
    Creates a Lecture database record after successful direct browser upload to Supabase.
    Django receives only metadata and the pre-uploaded storage video_path.
    Protected: Admin only.
    """
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/signin/?next=/admin/lectures/")

    if not is_admin_request(request):
        raise Http404("Page not found")

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    course = data.get('course', '').strip()
    position_raw = data.get('position')
    duration_raw = data.get('duration_seconds')
    video_path = data.get('video_path', '').strip()

    if not title:
        return JsonResponse({'success': False, 'error': 'Lecture title is required.'}, status=400)

    if course not in ['indian_market', 'forex_gold']:
        return JsonResponse({'success': False, 'error': 'Valid course choice is required.'}, status=400)

    if not video_path:
        return JsonResponse({'success': False, 'error': 'Video storage path is required.'}, status=400)

    # Server-side extension re-validation
    ext = os.path.splitext(video_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse({'success': False, 'error': f"Invalid video extension '{ext}'."}, status=400)

    try:
        if position_raw and str(position_raw).isdigit():
            position = int(position_raw)
        else:
            max_pos = Lecture.objects.filter(course=course).count()
            position = max_pos + 1

        duration_seconds = int(duration_raw) if (duration_raw and str(duration_raw).isdigit()) else 0

        lecture = Lecture.objects.create(
            title=title,
            description=description,
            course=course,
            position=position,
            video_path=video_path,
            duration_seconds=duration_seconds,
        )

        messages.success(
            request,
            f"Lecture '{lecture.title}' uploaded successfully! Registered in database and stored in '{get_lecture_bucket_name()}'."
        )

        return JsonResponse({
            'success': True,
            'lecture_id': lecture.id,
            'title': lecture.title,
            'course': lecture.course,
            'video_path': lecture.video_path,
            'redirect_url': f"/admin/lectures/?course={course}",
        })
    except Exception as exc:
        return JsonResponse({'success': False, 'error': f"Failed to register lecture: {str(exc)}"}, status=500)


def admin_lectures_view(request):
    """
    Main Admin Dashboard for managing course lectures.
    Protected: Only authenticated administrators can access. Returns 404 for non-admins.
    Uploads are handled asynchronously via direct-to-Supabase endpoints (upload-url and confirm).
    """
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/signin/?next={request.path}")

    if not is_admin_request(request):
        raise Http404("Page not found")

    course_filter = request.GET.get('course', 'all')
    valid_courses = ['all', 'indian_market', 'forex_gold']
    if course_filter not in valid_courses:
        course_filter = 'all'

    # Reject legacy direct multipart file POSTs to avoid any Vercel payload limit issues
    if request.method == 'POST':
        messages.warning(
            request,
            "Direct form POSTs are disabled. Video files must be uploaded via the direct browser-to-Supabase flow."
        )
        return redirect(f"/admin/lectures/?course={course_filter}")

    # Fetch lectures
    try:
        all_lectures = list(Lecture.objects.all().order_by('course', 'position', 'id'))
    except Exception:
        all_lectures = []

    indian_market_lectures = [l for l in all_lectures if l.course == 'indian_market']
    forex_gold_lectures = [l for l in all_lectures if l.course == 'forex_gold']

    # Generate preview URLs for admin view
    for l in all_lectures:
        l.preview_url = get_signed_lecture_url(l.video_path, expires_in=1800)

    total_duration_secs = sum(l.duration_seconds for l in all_lectures)
    tot_mins, tot_secs = divmod(total_duration_secs, 60)
    tot_hours, tot_mins = divmod(tot_mins, 60)
    total_duration_str = f"{tot_hours}h {tot_mins}m" if tot_hours > 0 else f"{tot_mins} mins"

    stats = {
        'total_count': len(all_lectures),
        'indian_market_count': len(indian_market_lectures),
        'forex_gold_count': len(forex_gold_lectures),
        'total_duration_str': total_duration_str,
        'bucket_name': get_lecture_bucket_name(),
        'max_size_mb': MAX_UPLOAD_SIZE_MB,
    }

    context = {
        'course_filter': course_filter,
        'indian_market_lectures': indian_market_lectures,
        'forex_gold_lectures': forex_gold_lectures,
        'all_lectures': all_lectures,
        'stats': stats,
    }

    return render(request, 'courses/admin_lectures.html', context)


def admin_lecture_edit_view(request, lecture_id):
    """
    Edit an existing lecture's metadata and optionally replace its video file.
    Protected: Only authenticated administrators can access.
    """
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/signin/?next=/admin/lectures/")

    if not is_admin_request(request):
        raise Http404("Page not found")

    lecture = get_object_or_404(Lecture, id=lecture_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        course = request.POST.get('course', '').strip()
        position_raw = request.POST.get('position', '').strip()
        duration_raw = request.POST.get('duration_seconds', '').strip()
        new_video_path = request.POST.get('new_video_path', '').strip()

        errors = []
        if not title:
            errors.append("Title is required.")
        if course not in ['indian_market', 'forex_gold']:
            errors.append("Valid course choice is required.")

        # Reject legacy direct multipart file POSTs to avoid Vercel payload limit issues
        if request.FILES.get('video_file'):
            messages.warning(
                request,
                "Direct multipart video uploads are disabled. Please use the direct browser upload in the admin interface."
            )
            return redirect(f"/admin/lectures/?course={course if course in ['indian_market', 'forex_gold'] else 'all'}")

        if new_video_path:
            ext = os.path.splitext(new_video_path)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors.append(f"Invalid video format '{ext}'.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            try:
                lecture.title = title
                lecture.description = description
                lecture.course = course
                if position_raw and position_raw.isdigit():
                    lecture.position = int(position_raw)
                if duration_raw and duration_raw.isdigit():
                    lecture.duration_seconds = int(duration_raw)

                # If new video path provided via direct upload, replace old in Supabase
                if new_video_path:
                    ext = os.path.splitext(new_video_path)[1].lower()
                    if ext in ALLOWED_EXTENSIONS:
                        old_path = lecture.video_path
                        if old_path and old_path != new_video_path:
                            delete_lecture_file(old_path)
                        lecture.video_path = new_video_path

                lecture.save()
                messages.success(request, f"Lecture '{lecture.title}' updated successfully.")
                return redirect(f"/admin/lectures/?course={lecture.course}")
            except Exception as exc:
                messages.error(request, f"Error updating lecture: {str(exc)}")

    return redirect(f"/admin/lectures/?course={lecture.course}")


@require_POST
def admin_lecture_delete_view(request, lecture_id):
    """
    Deletes a lecture from both the database and the Supabase Storage bucket.
    Protected: Only authenticated administrators can access.
    """
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/signin/?next=/admin/lectures/")

    if not is_admin_request(request):
        raise Http404("Page not found")

    lecture = get_object_or_404(Lecture, id=lecture_id)
    course = lecture.course
    title = lecture.title
    video_path = lecture.video_path

    try:
        # Delete from Supabase Storage
        delete_lecture_file(video_path)

        # Delete database row
        lecture.delete()
        messages.success(request, f"Lecture '{title}' was permanently deleted from database and storage.")
    except Exception as exc:
        messages.error(request, f"Error deleting lecture '{title}': {str(exc)}")

    return redirect(f"/admin/lectures/?course={course}")


def admin_lecture_signed_url_api(request, lecture_id):
    """
    API endpoint returning fresh signed URL for admin previewing.
    Protected: Admin only.
    """
    if not is_admin_request(request):
        raise Http404("Page not found")

    lecture = get_object_or_404(Lecture, id=lecture_id)
    signed_url = get_signed_lecture_url(lecture.video_path, expires_in=1800)

    if not signed_url:
        return JsonResponse({'success': False, 'error': 'Failed to generate signed URL'}, status=400)

    return JsonResponse({
        'success': True,
        'title': lecture.title,
        'course': lecture.course,
        'signed_url': signed_url,
    })
