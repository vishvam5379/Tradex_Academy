import os
import io
import base64
import re
import urllib.parse
import requests
from django.conf import settings

try:
    import qrcode
except ImportError:
    qrcode = None


def get_upi_config():
    """Retrieve UPI payee configuration from environment or settings."""
    upi_id = os.getenv('MANUAL_UPI_ID') or getattr(settings, 'MANUAL_UPI_ID', '')
    payee_name = os.getenv('MANUAL_UPI_NAME') or getattr(settings, 'MANUAL_UPI_NAME', '')
    upi_phone = os.getenv('MANUAL_UPI_PHONE') or getattr(settings, 'MANUAL_UPI_PHONE', '')
    return upi_id.strip(), payee_name.strip(), upi_phone.strip()


def generate_upi_deep_link(upi_id, payee_name, amount, plan_key, user_id=None):
    """
    Format: upi://pay?pa=<MANUAL_UPI_ID>&pn=<MANUAL_UPI_NAME>&am=<amount>&cu=INR&tn=TRADEX-<plan_key>
    """
    note = f"TRADEX-{plan_key}"
    params = {
        'pa': upi_id,
        'pn': payee_name,
        'am': f"{float(amount):.2f}",
        'cu': 'INR',
        'tn': note,
    }
    query_string = urllib.parse.urlencode(params)
    return f"upi://pay?{query_string}"


def generate_upi_qr_data_uri(upi_uri):
    """
    Generate an offline QR Code as a base64 PNG data URI.
    No 3rd party external service receives user or payment data.
    """
    if qrcode is None:
        return ""

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64_encoded}"


def get_supabase_storage_config():
    """Extract Supabase URL, key, and bucket name from environment."""
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
        os.getenv('SUPABASE_STORAGE_BUCKET') or
        getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'payment-screenshots')
    ).strip()

    return url, key, bucket


def upload_screenshot_to_supabase(uploaded_file, file_path):
    """
    Uploads file bytes to a private Supabase Storage bucket via REST API.
    Returns (success: bool, path_or_error: str).
    """
    supabase_url, supabase_key, bucket = get_supabase_storage_config()

    if not supabase_url or not supabase_key:
        # Dev / fallback local mock path
        return True, f"local_mock/{file_path}"

    target_url = f"{supabase_url}/storage/v1/object/{bucket}/{file_path}"
    headers = {
        'Authorization': f"Bearer {supabase_key}",
        'apiKey': supabase_key,
        'Content-Type': uploaded_file.content_type or 'application/octet-stream',
        'x-upsert': 'true',
    }

    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        response = requests.post(target_url, headers=headers, data=file_bytes, timeout=15)
        if response.status_code in [200, 201]:
            return True, file_path
        else:
            return False, f"Supabase Storage error: {response.text}"
    except Exception as exc:
        return False, str(exc)


def get_signed_screenshot_url(screenshot_path, expires_in=300):
    """
    Requests a short-lived (e.g. 5 min) signed URL from Supabase Storage for private viewing.
    """
    if not screenshot_path:
        return None

    if screenshot_path.startswith('local_mock/'):
        return None

    supabase_url, supabase_key, bucket = get_supabase_storage_config()
    if not supabase_url or not supabase_key:
        return None

    sign_endpoint = f"{supabase_url}/storage/v1/object/sign/{bucket}/{screenshot_path}"
    headers = {
        'Authorization': f"Bearer {supabase_key}",
        'apiKey': supabase_key,
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            sign_endpoint,
            headers=headers,
            json={'expiresIn': expires_in},
            timeout=10
        )
        if response.status_code in [200, 201]:
            data = response.json()
            signed_path = data.get('signedURL')
            if signed_path:
                return f"{supabase_url}/storage/v1{signed_path}"
    except Exception:
        pass

    return None
