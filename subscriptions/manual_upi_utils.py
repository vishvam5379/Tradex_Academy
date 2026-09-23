import os
import io
import base64
import re
import urllib.parse
import logging
import traceback
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

QRCODE_IMPORT_ERROR = None
try:
    import qrcode
    import qrcode.image.svg
except Exception as e:
    qrcode = None
    QRCODE_IMPORT_ERROR = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
    print(f"[UPI_QR_ERROR] Failed to import qrcode: {QRCODE_IMPORT_ERROR}", flush=True)


def get_upi_config():
    """Retrieve UPI payee configuration from environment or settings."""
    upi_id = os.getenv('MANUAL_UPI_ID') or getattr(settings, 'MANUAL_UPI_ID', '')
    payee_name = os.getenv('MANUAL_UPI_NAME') or getattr(settings, 'MANUAL_UPI_NAME', '')
    upi_phone = os.getenv('MANUAL_UPI_PHONE') or getattr(settings, 'MANUAL_UPI_PHONE', '')
    return upi_id.strip(), payee_name.strip(), upi_phone.strip()


def generate_upi_deep_link(upi_id, payee_name, amount, plan_key, user_id=None):
    """
    Format: upi://pay?pa=<MANUAL_UPI_ID>&pn=<MANUAL_UPI_NAME>&am=<amount>&cu=INR&tn=TRADEX-<plan_key>
    Uses quote_via=quote and safe='@' so pa retains literal '@' and pn uses '%20' for UPI app compatibility.
    """
    note = f"TRADEX-{plan_key}"
    amt_str = f"{float(amount):.2f}".rstrip('0').rstrip('.') if float(amount).is_integer() else f"{float(amount):.2f}"
    params = [
        ('pa', (upi_id or '').strip()),
        ('pn', (payee_name or '').strip()),
        ('am', amt_str),
        ('cu', 'INR'),
        ('tn', note),
    ]
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe='@')
    return f"upi://pay?{query_string}"


def generate_upi_qr_data_uri(upi_uri):
    """
    Generate an offline QR Code as a data URI (SVG preferred, PNG fallback).
    No 3rd party external service receives user or payment data.
    Uses pure-Python SVG (ElementTree) to avoid C-extension/Pillow dependency failures on serverless runtimes like Vercel.
    """
    global qrcode
    if not upi_uri:
        err = "[UPI_QR_ERROR] Empty upi_uri passed to generate_upi_qr_data_uri."
        print(err, flush=True)
        logger.error(err)
        return ""

    if qrcode is None:
        try:
            import qrcode as _qr
            import qrcode.image.svg
            qrcode = _qr
        except Exception as e_dyn:
            err = f"[UPI_QR_ERROR] qrcode package is NOT available at runtime. Import exception was: {QRCODE_IMPORT_ERROR or e_dyn}"
            print(err, flush=True)
            logger.error(err)
            return ""

    # Primary: SVG via SvgPathImage (100% pure Python ElementTree, ZERO Pillow, ZERO C-libraries)
    try:
        import qrcode.image.svg
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(upi_uri)
        qr.make(fit=True)

        img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        buffer = io.BytesIO()
        img.save(buffer)
        b64_encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/svg+xml;base64,{b64_encoded}"
    except Exception as e_svg:
        err_svg = f"[UPI_QR_ERROR] SvgPathImage generation failed: {type(e_svg).__name__}: {e_svg}\n{traceback.format_exc()}"
        print(err_svg, flush=True)
        logger.error(err_svg)

    # Fallback: Try Pillow PNG if SVG failed
    try:
        qr = qrcode.QRCode(
            version=None,
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
    except Exception as e_png:
        err_png = f"[UPI_QR_ERROR] Pillow PNG generation failed: {type(e_png).__name__}: {e_png}\n{traceback.format_exc()}"
        print(err_png, flush=True)
        logger.error(err_png)

    return ""


def get_supabase_storage_config():
    """Extract Supabase URL, key, and bucket name from environment."""
    raw_url = os.getenv('SUPABASE_URL') or getattr(settings, 'SUPABASE_URL', '')
    raw_url = str(raw_url).strip().strip('\'"')

    url = ''
    if raw_url:
        from urllib.parse import urlparse
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
        os.getenv('SUPABASE_STORAGE_BUCKET') or
        getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'payment-screenshots')
    ).strip().strip('\'"').strip('/')

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

    clean_path = str(file_path).strip().strip('\'"').lstrip('/')
    target_url = f"{supabase_url}/storage/v1/object/{bucket}/{clean_path}"
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

    clean_path = str(screenshot_path).strip().strip('\'"').lstrip('/')
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
