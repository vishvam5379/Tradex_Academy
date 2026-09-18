from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from academy_core.views import health_check

urlpatterns = [
    path('healthz/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('subscriptions/', include('subscriptions.urls', namespace='subscriptions')),
    path('', include('courses.urls', namespace='courses')),
]

handler400 = 'academy_core.views.bad_request_handler'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
