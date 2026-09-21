from django.urls import path
from . import views
from . import views_manual

app_name = 'subscriptions'

urlpatterns = [
    path('pay/', views.initiate_upi_payment, name='initiate_upi_payment'),
    path('pay/<str:plan_key>/', views.initiate_upi_payment, name='initiate_upi_payment_plan'),
    path('checkout/<str:plan_key>/', views_manual.manual_checkout_view, name='manual_checkout'),
    path('admin/payments/', views_manual.admin_payments_view, name='admin_payments'),
    path('admin/payments/<int:payment_id>/approve/', views_manual.admin_payment_approve_view, name='admin_payment_approve'),
    path('admin/payments/<int:payment_id>/reject/', views_manual.admin_payment_reject_view, name='admin_payment_reject'),
    path('api/order-status/<int:order_id>/', views.order_status_api, name='order_status_api'),
    path('api/orders/<int:order_id>/status/', views.order_status_api, name='api_order_status'),
    path('webhook/', views.razorpay_webhook_view, name='webhook'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('create-order/', views.create_order_api, name='create_order'),
    path('verify-payment/', views.verify_payment_view, name='verify_payment'),
    path('success/', views.payment_success_view, name='success'),
    path('failed/', views.payment_failed_view, name='failed'),
    path('my-subscription/', views.my_subscription_view, name='my_subscription'),
]
