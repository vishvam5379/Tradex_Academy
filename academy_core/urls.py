from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from academy_core.views import health_check
from accounts import views as accounts_views
from subscriptions import views as subscriptions_views
from subscriptions import views_manual
from courses import views_admin

# Disable Django admin's greedy final catch-all regex so custom /admin/* routes are never swallowed
admin.site.final_catch_all_view = False

urlpatterns = [
    path('healthz/', health_check, name='health_check'),

    # Manual UPI Admin Verification dashboard (supports trailing-slash and slashless requests)
    path('admin/payments/', views_manual.admin_payments_view, name='root_admin_payments'),
    path('admin/payments', views_manual.admin_payments_view),
    path('admin/payments/<int:payment_id>/approve/', views_manual.admin_payment_approve_view, name='root_admin_payment_approve'),
    path('admin/payments/<int:payment_id>/reject/', views_manual.admin_payment_reject_view, name='root_admin_payment_reject'),

    # Admin Lecture Management (Supabase Storage Videos) - direct paths before Django admin
    path('admin/lectures/', views_admin.admin_lectures_view, name='admin_lectures'),
    path('admin/lectures', views_admin.admin_lectures_view),
    path('admin/lectures/<int:lecture_id>/edit/', views_admin.admin_lecture_edit_view, name='admin_lecture_edit'),
    path('admin/lectures/<int:lecture_id>/delete/', views_admin.admin_lecture_delete_view, name='admin_lecture_delete'),
    path('admin/lectures/<int:lecture_id>/signed-url/', views_admin.admin_lecture_signed_url_api, name='admin_lecture_signed_url'),

    path('admin/', admin.site.urls),

    # Custom auth must be registered before allauth so /accounts/signup/, /login/,
    # and /logout/ are not swallowed by django-allauth's own views.
    path('accounts/', include('accounts.urls', namespace='accounts')),

    # Google OAuth 2.0 endpoints matching credentials registered in Google Cloud
    path('accounts/google/login/', accounts_views.google_login_view, name='google_login'),
    path('accounts/google/callback/', accounts_views.google_callback_view, name='google_callback'),
    path('accounts/google/login/callback/', accounts_views.google_callback_view, name='google_callback_allauth'),

    path('accounts/', include('allauth.urls')),
    path('pay/<str:plan_key>/', views_manual.manual_checkout_view, name='root_pay_plan'),
    path('checkout/', subscriptions_views.checkout_view, name='root_checkout'),
    path('checkout/<str:plan_key>/', views_manual.manual_checkout_view, name='root_manual_checkout'),
    path('subscriptions/', include('subscriptions.urls', namespace='subscriptions')),
    path('api/payments/webhook/', include('subscriptions.urls_webhook')),
    path('api/orders/<int:order_id>/status/', subscriptions_views.order_status_api, name='api_order_status_root'),
    path('', include('courses.urls', namespace='courses')),
]

handler400 = 'academy_core.views.bad_request_handler'
handler500 = 'academy_core.views.server_error_handler'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
