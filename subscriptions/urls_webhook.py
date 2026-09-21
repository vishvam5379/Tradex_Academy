from django.urls import path
from subscriptions.views import razorpay_webhook_view

urlpatterns = [
    path('', razorpay_webhook_view, name='direct_webhook'),
]
