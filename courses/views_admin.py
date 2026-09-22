import os
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import Http404, JsonResponse
from django.contrib import messages
from django.utils.text import slugify

from subscriptions.views_manual import is_admin_email
from .models import Lecture
from .lecture_storage import (
    upload_lecture_file,
    get_signed_lecture_url,
    delete_lecture_file,
    get_lecture_bucket_name,
)

# Maximum upload limit: 100 MB (104,857,600 bytes)
# Rationale: Provides adequate capacity for 20-50 min compressed 1080p/720p trading lectures
# while avoiding gateway timeouts and excessive memory buffering on server instances.
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024
MAX_UPLOAD_SIZE_MB = 100

ALLOWED_EXTENSIONS = {'.mp4', '.mov', '.webm', '.m4v'}


def is_admin_request(request):
    """Verify authenticated user is authorized as an administrator."""
    user = getattr(request, 'user', None)
    return is_admin_email(user)


def admin_lectures_view(request):
    """
    Main Admin Dashboard for managing course lectures.
    Protected: Only authenticated administrators can access. Returns 404 for non-admins.
    """
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/signin/?next={request.path}")

    if not is_admin_request(request):
        raise Http404("Page not found")

    course_filter = request.GET.get('course', 'all')
    valid_courses = ['all', 'indian_market', 'forex_gold']
    if course_filter not in valid_courses:
        course_filter = 'all'

    if request.method == 'POST':
        # Handle new lecture upload
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        course = request.POST.get('course', '').strip()
        position_raw = request.POST.get('position', '').strip()
        duration_raw = request.POST.get('duration_seconds', '').strip()
        video_file = request.FILES.get('video_file')

        errors = []

        if not title:
            errors.append("Lecture title is required.")
        if course not in ['indian_market', 'forex_gold']:
            errors.append("Please select a valid course (Indian Market Mastery or Forex & Gold Mastery).")
        if not video_file:
            errors.append("A video file (MP4, MOV, or WEBM) is required.")
        else:
            ext = os.path.splitext(video_file.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors.append(f"Invalid video format '{ext}'. Allowed formats: MP4, MOV, WEBM, M4V.")
            if video_file.size > MAX_UPLOAD_SIZE_BYTES:
                file_mb = round(video_file.size / (1024 * 1024), 1)
                errors.append(
                    f"File size ({file_mb} MB) exceeds maximum allowed limit of {MAX_UPLOAD_SIZE_MB} MB. "
                    "Please compress the video or export at 1080p/720p before uploading."
                )

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            try:
                # Compute position
                if position_raw and position_raw.isdigit():
                    position = int(position_raw)
                else:
                    max_pos = Lecture.objects.filter(course=course).count()
                    position = max_pos + 1

                # Compute duration
                duration_seconds = int(duration_raw) if (duration_raw and duration_raw.isdigit()) else 0

                # Generate clean unique storage path
                clean_title_slug = slugify(title)[:35] or 'lecture'
                ext = os.path.splitext(video_file.name)[1].lower() or '.mp4'
                unique_token = uuid.uuid4().hex[:8]
                storage_path = f"{course}/{position:02d}_{clean_title_slug}_{unique_token}{ext}"

                # Upload to Supabase Storage bucket
                success, path_or_err = upload_lecture_file(
                    video_file,
                    storage_path,
                    content_type=video_file.content_type
                )

                if not success:
                    messages.error(request, f"Upload to cloud storage failed: {path_or_err}")
                else:
                    lecture = Lecture.objects.create(
                        title=title,
                        description=description,
                        course=course,
                        position=position,
                        video_path=path_or_err,
                        duration_seconds=duration_seconds,
                    )
                    messages.success(
                        request,
                        f"Lecture '{lecture.title}' uploaded successfully! Saved to private bucket '{get_lecture_bucket_name()}'."
                    )
                    return redirect(f"/admin/lectures/?course={course}")

            except Exception as exc:
                messages.error(request, f"An unexpected error occurred: {str(exc)}")

    # Fetch lectures
    all_lectures = Lecture.objects.all().order_by('course', 'position', 'id')
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
        'total_count': all_lectures.count(),
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
        new_video = request.FILES.get('video_file')

        errors = []
        if not title:
            errors.append("Title is required.")
        if course not in ['indian_market', 'forex_gold']:
            errors.append("Valid course choice is required.")

        if new_video:
            ext = os.path.splitext(new_video.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors.append(f"Invalid video format '{ext}'.")
            if new_video.size > MAX_UPLOAD_SIZE_BYTES:
                file_mb = round(new_video.size / (1024 * 1024), 1)
                errors.append(f"New video ({file_mb} MB) exceeds maximum allowed limit of {MAX_UPLOAD_SIZE_MB} MB.")

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

                # If new video file uploaded, replace old in Supabase
                if new_video:
                    clean_title_slug = slugify(title)[:35] or 'lecture'
                    ext = os.path.splitext(new_video.name)[1].lower() or '.mp4'
                    unique_token = uuid.uuid4().hex[:8]
                    new_storage_path = f"{course}/{lecture.position:02d}_{clean_title_slug}_{unique_token}{ext}"

                    # Delete previous file if exists
                    old_path = lecture.video_path
                    delete_lecture_file(old_path)

                    # Upload replacement
                    success, res_path = upload_lecture_file(
                        new_video,
                        new_storage_path,
                        content_type=new_video.content_type
                    )
                    if not success:
                        messages.error(request, f"Failed to upload replacement video: {res_path}")
                        return redirect(f"/admin/lectures/?course={course}")
                    lecture.video_path = res_path

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
