import traceback
from django.http import HttpResponse, JsonResponse
from django.conf import settings


def health_check(request):
    return JsonResponse({
        'status': 'ok',
        'host': request.get_host(),
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'is_vercel': getattr(settings, 'IS_VERCEL', False),
    })


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
