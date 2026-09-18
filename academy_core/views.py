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
