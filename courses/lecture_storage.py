import os
import sys
import re
import requests
from urllib.parse import urlparse
from django.conf import settings


def get_supabase_lecture_storage_config():
    """
    Extract Supabase URL, key, and the private lecture video bucket name from environment.
    Defaults bucket name to 'lecture-videos'.
    Guarantees the URL is stripped of any path suffix (such as /rest/v1) and strictly points
    to the Supabase project origin (https://<project-ref>.supabase.co).
    """
    raw_url = os.getenv('SUPABASE_URL') or getattr(settings, 'SUPABASE_URL', '')
    raw_url = str(raw_url).strip().strip('\'"')

    url = ''
    if raw_url:
        parsed = urlparse(raw_url)
        if parsed.scheme and parsed.netloc:
            url = f"{parsed.scheme}://{parsed.netloc}"
        else:
            url = raw_url.split('/rest')[0].split('/storage')[0].rstrip('/')

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
    ).strip().strip('\'"')

    bucket = (
        os.getenv('LECTURE_VIDEO_BUCKET') or
        os.getenv('SUPABASE_STORAGE_BUCKET') or
        getattr(settings, 'LECTURE_VIDEO_BUCKET', '') or
        getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'lecture-videos')
    ).strip().strip('\'"').strip('/')

    if not bucket:
        bucket = 'lecture-videos'

    return url, key, bucket


def get_lecture_bucket_name():
    """Return the bucket name configured for lecture videos."""
    _, _, bucket = get_supabase_lecture_storage_config()
    return bucket


def create_signed_upload_url(file_path, bucket=None, expires_in=7200):
    """
    Generates a signed upload URL from Supabase Storage allowing direct browser PUT uploads.
    Bypasses Vercel/Django completely for the file transfer payload.
    Supports any configured Supabase bucket (e.g. 'lecture-videos', 'payment-screenshots').
    Returns (success: bool, signed_url_or_error: str, token: str or None).
    """
    if not file_path:
        return False, "File path is required", None

    supabase_url, supabase_key, default_bucket = get_supabase_lecture_storage_config()
    target_bucket = (bucket or default_bucket).strip().strip('\'"').strip('/')
    clean_path = str(file_path).strip().strip('\'"').lstrip('/')

    if not supabase_url or not supabase_key:
        # If in local debug mode or running unit tests, return mock URL for testing.
        # In production (DEBUG=False and not testing), fail explicitly so the browser never attempts to PUT large payloads to Vercel!
        is_test = 'test' in sys.argv or getattr(settings, 'TESTING', False)
        is_debug = getattr(settings, 'DEBUG', False)
        if is_debug or is_test:
            return True, f"/mock-upload/{target_bucket}/{clean_path}", "mock_token"
        return False, "Supabase Storage credentials (SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY) are not configured in environment variables.", None

    sign_endpoint = f"{supabase_url}/storage/v1/object/upload/sign/{target_bucket}/{clean_path}"
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

    clean_path = str(file_path).strip().strip('\'"').lstrip('/')
    target_url = f"{supabase_url}/storage/v1/object/{bucket}/{clean_path}"
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

    clean_path = str(video_path).strip().strip('\'"').lstrip('/')
    sign_endpoint = f"{supabase_url}/storage/v1/object/sign/{bucket}/{clean_path}"
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

    clean_path = str(video_path).strip().strip('\'"').lstrip('/')
    delete_url = f"{supabase_url}/storage/v1/object/{bucket}/{clean_path}"
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
