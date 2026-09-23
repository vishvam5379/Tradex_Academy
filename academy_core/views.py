import os
import traceback
from django.http import HttpResponse, JsonResponse
from django.conf import settings


def health_check(request):
    data = {
        'status': 'ok',
        'host': request.get_host(),
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'is_vercel': getattr(settings, 'IS_VERCEL', False),
        'vercel_git_commit_sha': os.getenv('VERCEL_GIT_COMMIT_SHA', 'unknown'),
    }
    # Diagnostic test for UPI QR generation
    try:
        from subscriptions.manual_upi_utils import (
            get_upi_config,
            generate_upi_deep_link,
            generate_upi_qr_data_uri,
            QRCODE_IMPORT_ERROR,
        )
        upi_id, payee, phone = get_upi_config()
        link = generate_upi_deep_link(upi_id or '9313858614@ibl', payee or 'Tradex Academy', 3999, 'starter')
        qr_uri = generate_upi_qr_data_uri(link)
        data['qr_diagnostics'] = {
            'qrcode_import_error': QRCODE_IMPORT_ERROR,
            'test_link': link,
            'qr_len': len(qr_uri),
            'qr_prefix': qr_uri[:45] if qr_uri else '',
            'success': bool(qr_uri),
        }
    except Exception as e:
        data['qr_diagnostics'] = {
            'exception': f"{type(e).__name__}: {str(e)}",
            'traceback': traceback.format_exc(),
            'success': False,
        }
    return JsonResponse(data)


def bad_request_handler(request, exception=None):
    detail = str(exception) if exception else "SuspiciousOperation detected"
    host = request.headers.get('host', 'unknown')
    return HttpResponse(f"Bad Request (400): {detail} [Host: {host}]", status=400)


def server_error_handler(request):
    error_trace = traceback.format_exc()
    return HttpResponse(
        f"<html><body style='padding:20px; font-family:monospace;'><h2 style='color:#b91c1c;'>Tradex Academy 500 Debug:</h2><pre style='background:#fef2f2; border:1px solid #f87171; padding:15px; border-radius:6px; overflow:auto;'>{error_trace}</pre></body></html>",
        status=500
    )
