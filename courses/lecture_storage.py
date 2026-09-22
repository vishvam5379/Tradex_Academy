import os
import re
import requests
from django.conf import settings


def get_supabase_lecture_storage_config():
    """
    Extract Supabase URL, key, and the private lecture video bucket name from environment.
    Defaults bucket name to 'lecture-videos'.
    """
    url = (os.getenv('SUPABASE_URL') or getattr(settings, 'SUPABASE_URL', '')).rstrip('/')
    if not url:
        db_host = os.getenv('DB_HOST') or getattr(settings, 'DB_HOST', '')
        if 'supabase.co' in db_host:
            match = re.search(r'db\.([a-zA-Z0-9_-]+)\.supabase\.co', db_host)
            if match:
                ref = match.group(1)
                url = f"https://{ref}.supabase.co"

    key = (
        os.getenv('SUPABASE_SERVICE_ROLE_KEY') or
        os.getenv('SUPABASE_KEY') or
        getattr(settings, 'SUPABASE_KEY', '')
    ).strip()

    bucket = (
        os.getenv('LECTURE_VIDEO_BUCKET') or
        getattr(settings, 'LECTURE_VIDEO_BUCKET', 'lecture-videos')
    ).strip()

    return url, key, bucket


def get_lecture_bucket_name():
    """Return the bucket name configured for lecture videos."""
    _, _, bucket = get_supabase_lecture_storage_config()
    return bucket


def create_signed_upload_url(file_path, expires_in=7200):
    """
    Generates a signed upload URL from Supabase Storage allowing direct browser PUT uploads.
    Bypasses Vercel/Django completely for the file transfer payload.
    Returns (success: bool, signed_url_or_error: str, token: str or None).
    """
    if not file_path:
        return False, "File path is required", None

    supabase_url, supabase_key, bucket = get_supabase_lecture_storage_config()

    if not supabase_url or not supabase_key:
        # Dev / fallback local mock upload URL
        return True, f"/mock-upload/{bucket}/{file_path}", "mock_token"

    sign_endpoint = f"{supabase_url}/storage/v1/object/upload/sign/{bucket}/{file_path}"
    headers = {
        'Authorization': f"Bearer {supabase_key}",
        'apiKey': supabase_key,
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            sign_endpoint,
            headers=headers,
            json={'upsert': True},
            timeout=15
        )
        if response.status_code in [200, 201]:
            data = response.json()
            rel_or_full = data.get('url') or data.get('signedURL') or data.get('signedUrl')
            token = data.get('token', '')
            if rel_or_full:
                if rel_or_full.startswith('http://') or rel_or_full.startswith('https://'):
                    full_upload_url = rel_or_full
                elif rel_or_full.startswith('/storage/v1/'):
                    full_upload_url = f"{supabase_url}{rel_or_full}"
                elif rel_or_full.startswith('/'):
                    full_upload_url = f"{supabase_url}/storage/v1{rel_or_full}"
                else:
                    full_upload_url = f"{supabase_url}/storage/v1/{rel_or_full}"

                return True, full_upload_url, token
            return False, f"Supabase Storage returned unexpected response: {data}", None
        else:
            return False, f"Supabase Storage upload-sign error ({response.status_code}): {response.text}", None
    except Exception as exc:
        return False, str(exc), None


def upload_lecture_file(uploaded_file, file_path, content_type=None):
    """
    Uploads video file bytes to the private Supabase Storage bucket via REST API.
    Returns (success: bool, path_or_error: str).
    """
    supabase_url, supabase_key, bucket = get_supabase_lecture_storage_config()

    if not supabase_url or not supabase_key:
        # Dev / fallback local mock path
        return True, f"local_mock/{file_path}"

    target_url = f"{supabase_url}/storage/v1/object/{bucket}/{file_path}"
    ct = content_type or getattr(uploaded_file, 'content_type', 'video/mp4') or 'video/mp4'

    headers = {
        'Authorization': f"Bearer {supabase_key}",
        'apiKey': supabase_key,
        'Content-Type': ct,
        'x-upsert': 'true',
    }

    try:
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
        else:
            file_data = uploaded_file

        response = requests.post(target_url, headers=headers, data=file_data, timeout=120)
        if response.status_code in [200, 201]:
            return True, file_path
        else:
            return False, f"Supabase Storage error ({response.status_code}): {response.text}"
    except Exception as exc:
        return False, str(exc)


def get_signed_lecture_url(video_path, expires_in=3600):
    """
    Requests a short-lived signed URL from Supabase Storage for private playback.
    Default expiry is 3600 seconds (1 hour).
    Returns signed URL string or None.
    """
    if not video_path:
        return None

    if video_path.startswith('local_mock/'):
        return f"/mock-media/{video_path}"

    supabase_url, supabase_key, bucket = get_supabase_lecture_storage_config()
    if not supabase_url or not supabase_key:
        return f"https://mock-storage.supabase.co/{bucket}/{video_path}?token=mock_signed_{expires_in}"

    sign_endpoint = f"{supabase_url}/storage/v1/object/sign/{bucket}/{video_path}"
    headers = {
        'Authorization': f"Bearer {supabase_key}",
        'apiKey': supabase_key,
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            sign_endpoint,
            headers=headers,
            json={'expiresIn': int(expires_in)},
            timeout=15
        )
        if response.status_code in [200, 201]:
            data = response.json()
            signed_path = data.get('signedURL')
            if signed_path:
                return f"{supabase_url}/storage/v1{signed_path}"
    except Exception:
        pass

    return None


def delete_lecture_file(video_path):
    """
    Deletes the video object from the private Supabase Storage bucket.
    Returns (success: bool, message: str).
    """
    if not video_path or video_path.startswith('local_mock/'):
        return True, "Mock file deleted"

    supabase_url, supabase_key, bucket = get_supabase_lecture_storage_config()
    if not supabase_url or not supabase_key:
        return True, "No Supabase credentials configured; skipped remote deletion"

    delete_url = f"{supabase_url}/storage/v1/object/{bucket}/{video_path}"
    headers = {
        'Authorization': f"Bearer {supabase_key}",
        'apiKey': supabase_key,
    }

    try:
        response = requests.delete(delete_url, headers=headers, timeout=15)
        if response.status_code in [200, 204]:
            return True, "Object deleted successfully"
        else:
            return False, f"Supabase Storage delete error ({response.status_code}): {response.text}"
    except Exception as exc:
        return False, str(exc)
