from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from subscriptions.models import Subscription

User = get_user_model()


class SubscriptionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='subscriber@test.com',
            name='Subscriber Test',
            password='Password123'
        )

    def test_subscription_active_and_expiry_logic(self):
        # 1. Active subscription within 90 days
        sub = Subscription.objects.create(
            user=self.user,
            status='ACTIVE',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=90),
            amount_paid=3999.00
        )
        self.assertTrue(sub.is_currently_active)
        self.assertTrue(self.user.has_active_subscription)
        self.assertGreaterEqual(self.user.subscription_days_remaining, 89)

        # 2. Expired subscription (end_date in past)
        sub.end_date = timezone.now() - timedelta(days=1)
        sub.save()
        self.assertFalse(sub.is_currently_active)
        self.assertFalse(self.user.has_active_subscription)
        self.assertEqual(self.user.subscription_days_remaining, 0)

    def test_verify_payment_endpoint(self):
        self.client.login(email='subscriber@test.com', password='Password123')
        
        payload = {
            'razorpay_order_id': 'order_sim_test_123',
            'razorpay_payment_id': 'pay_sim_test_456',
            'razorpay_signature': 'simulated_signature'
        }
        
        response = self.client.post(
            reverse('subscriptions:verify_payment'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        # Verify database record
        self.assertTrue(self.user.has_active_subscription)
        new_sub = self.user.active_subscription
        self.assertIsNotNone(new_sub)
        self.assertEqual(new_sub.amount_paid, 3999.00)
        self.assertEqual(new_sub.razorpay_order_id, 'order_sim_test_123')
        self.assertEqual(new_sub.status, 'ACTIVE')
        self.assertGreater(new_sub.end_date, timezone.now() + timedelta(days=88))

    def test_checkout_and_my_subscription_views(self):
        self.client.login(email='subscriber@test.com', password='Password123')
        
        # Checkout page
        res_checkout = self.client.get(reverse('subscriptions:checkout'))
        self.assertEqual(res_checkout.status_code, 200)
        self.assertContains(res_checkout, '3,999')
        self.assertContains(res_checkout, '11,999')

        # My Subscription page
        res_my_sub = self.client.get(reverse('subscriptions:my_subscription'))
        self.assertEqual(res_my_sub.status_code, 200)
