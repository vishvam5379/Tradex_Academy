from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('create-order/', views.create_order_api, name='create_order'),
    path('verify-payment/', views.verify_payment_view, name='verify_payment'),
    path('success/', views.payment_success_view, name='success'),
    path('failed/', views.payment_failed_view, name='failed'),
    path('my-subscription/', views.my_subscription_view, name='my_subscription'),
]
