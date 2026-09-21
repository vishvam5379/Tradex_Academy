from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import json
import hmac
import hashlib

from subscriptions.models import Subscription, Order
from courses.models import Category, SubCategory, Video

User = get_user_model()


class SubscriptionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='subscriber@test.com',
            name='Subscriber Test',
            password='Password123'
        )
        self.other_user = User.objects.create_user(
            email='other@test.com',
            name='Other User',
            password='Password123'
        )

    def test_subscription_active_and_expiry_logic(self):
        # 1. Active subscription within 90 days
        sub = Subscription.objects.create(
            user=self.user,
            plan_type='starter',
            plan_name='Indian Market Foundation',
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

    def test_initiate_upi_payment_creates_order_and_redirects(self):
        self.client.login(email='subscriber@test.com', password='Password123')
        response = self.client.get(reverse('subscriptions:initiate_upi_payment_plan', args=['starter']))
        
        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(user=self.user, plan='starter').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.amount, 3999.00)
        self.assertEqual(order.currency, 'INR')
        self.assertEqual(order.status, 'created')

    def test_initiate_upi_payment_blocks_duplicate_active_subscription(self):
        self.client.login(email='subscriber@test.com', password='Password123')
        # Create active subscription for starter
        Subscription.objects.create(
            user=self.user,
            plan_type='starter',
            plan_name='Indian Market Foundation',
            status='ACTIVE',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=90),
            amount_paid=3999.00
        )
        response = self.client.get(reverse('subscriptions:initiate_upi_payment_plan', args=['starter']))
        self.assertRedirects(response, reverse('courses:dashboard'))
        # No new order should be created
        self.assertEqual(Order.objects.filter(user=self.user).count(), 0)

    def test_order_status_api(self):
        self.client.login(email='subscriber@test.com', password='Password123')
        order = Order.objects.create(
            user=self.user,
            plan='pro',
            amount=9999.00,
            status='created'
        )
        url = reverse('subscriptions:order_status_api', args=[order.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'created')
        self.assertEqual(data['order_id'], order.id)

        # Check other user cannot view this order
        self.client.login(email='other@test.com', password='Password123')
        res_forbidden = self.client.get(url)
        self.assertEqual(res_forbidden.status_code, 404)

    def test_razorpay_webhook_signature_and_activation(self):
        # Create order
        order = Order.objects.create(
            user=self.user,
            plan='starter',
            amount=3999.00,
            status='created',
            gateway_order_id='plink_test_123'
        )

        secret = 'test_webhook_secret'
        with self.settings(RAZORPAY_WEBHOOK_SECRET=secret):
            webhook_payload = {
                'event': 'payment_link.paid',
                'payload': {
                    'payment_link': {
                        'entity': {
                            'id': 'plink_test_123',
                            'reference_id': str(order.id),
                            'amount': 399900,
                            'currency': 'INR',
                            'payment_id': 'pay_test_999'
                        }
                    },
                    'payment': {
                        'entity': {
                            'id': 'pay_test_999',
                            'amount': 399900,
                            'currency': 'INR',
                            'notes': {'order_id': str(order.id)}
                        }
                    }
                }
            }
            body_bytes = json.dumps(webhook_payload).encode('utf-8')

            # 1. Invalid signature test
            res_bad = self.client.post(
                reverse('subscriptions:webhook'),
                data=body_bytes,
                content_type='application/json',
                HTTP_X_RAZORPAY_SIGNATURE='invalid_signature'
            )
            self.assertEqual(res_bad.status_code, 400)
            order.refresh_from_db()
            self.assertEqual(order.status, 'created')

            # 2. Valid signature test
            valid_sig = hmac.new(secret.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()
            res_good = self.client.post(
                reverse('subscriptions:webhook'),
                data=body_bytes,
                content_type='application/json',
                HTTP_X_RAZORPAY_SIGNATURE=valid_sig
            )
            self.assertEqual(res_good.status_code, 200)

            order.refresh_from_db()
            self.assertEqual(order.status, 'paid')
            self.assertIsNotNone(order.paid_at)

            # Subscription created
            sub = Subscription.objects.filter(user=self.user, status='ACTIVE').first()
            self.assertIsNotNone(sub)
            self.assertEqual(sub.plan_type, 'starter')
            self.assertTrue(sub.is_currently_active)

            # 3. Idempotent re-send: should not double-create
            sub_count_before = Subscription.objects.filter(user=self.user).count()
            res_idempotent = self.client.post(
                reverse('subscriptions:webhook'),
                data=body_bytes,
                content_type='application/json',
                HTTP_X_RAZORPAY_SIGNATURE=valid_sig
            )
            self.assertEqual(res_idempotent.status_code, 200)
            self.assertEqual(Subscription.objects.filter(user=self.user).count(), sub_count_before)

    def test_video_access_control(self):
        # Create categories and subcategories
        cat_indian = Category.objects.create(name='Indian Market', slug='indian-market')
        subcat_indian = SubCategory.objects.create(
            parent=cat_indian,
            name='Futures Trading',
            slug='futures',
            tier_required='standard'
        )
        video_indian = Video.objects.create(
            sub_category=subcat_indian,
            title='Intro to Futures',
            slug='intro-to-futures',
            video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        )

        cat_forex = Category.objects.create(name='Forex', slug='forex')
        subcat_forex = SubCategory.objects.create(
            parent=cat_forex,
            name='Gold Strategy',
            slug='gold-strategy',
            tier_required='gold_strategy'
        )
        video_forex = Video.objects.create(
            sub_category=subcat_forex,
            title='Gold Execution',
            slug='gold-execution',
            video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        )

        # Logged in user without subscription is blocked
        self.client.login(email='subscriber@test.com', password='Password123')
        url_indian = reverse('courses:video_player', args=['indian-market', 'futures', video_indian.id])
        res_blocked = self.client.get(url_indian)
        self.assertEqual(res_blocked.status_code, 302)
        self.assertIn('/subscriptions/pay/starter/', res_blocked.url)

        # Grant Starter subscription (access to Indian market, blocked from Forex)
        Subscription.objects.create(
            user=self.user,
            plan_type='starter',
            status='ACTIVE',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=90),
            amount_paid=3999.00
        )
        res_allowed_indian = self.client.get(url_indian)
        self.assertEqual(res_allowed_indian.status_code, 200)

        url_forex = reverse('courses:video_player', args=['forex', 'gold-strategy', video_forex.id])
        res_blocked_forex = self.client.get(url_forex)
        self.assertEqual(res_blocked_forex.status_code, 302)
        self.assertIn('/subscriptions/pay/pro/', res_blocked_forex.url)

