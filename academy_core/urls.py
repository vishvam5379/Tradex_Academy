from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from academy_core.views import health_check
from allauth.socialaccount.providers.google import views as google_views

urlpatterns = [
    path('healthz/', health_check, name='health_check'),
    path('admin/', admin.site.urls),

    # Custom auth must be registered before allauth so /accounts/signup/, /login/,
    # and /logout/ are not swallowed by django-allauth's own views.
    path('accounts/', include('accounts.urls', namespace='accounts')),

    # Keep the previous Google callback path working with credentials already
    # registered in Google Cloud as /accounts/google/callback/.
    path('accounts/google/login/', google_views.oauth2_login, name='google_login'),
    path('accounts/google/callback/', google_views.oauth2_callback, name='google_callback'),
    path('accounts/google/login/callback/', google_views.oauth2_callback, name='google_callback_allauth'),

    path('accounts/', include('allauth.urls')),
    path('subscriptions/', include('subscriptions.urls', namespace='subscriptions')),
    path('', include('courses.urls', namespace='courses')),
]

handler400 = 'academy_core.views.bad_request_handler'
handler500 = 'academy_core.views.server_error_handler'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
