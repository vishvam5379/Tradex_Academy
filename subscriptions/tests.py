from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import json
import hmac
import hashlib

from subscriptions.models import Subscription, Order, ManualPayment, UserNotification
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

    def test_initiate_upi_payment_redirects_to_pay_plan(self):
        self.client.login(email='subscriber@test.com', password='Password123')
        response = self.client.get(reverse('subscriptions:initiate_upi_payment_plan', args=['starter']))
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/pay/starter/')
        # No Razorpay order should be created
        self.assertEqual(Order.objects.filter(user=self.user, plan='starter').count(), 0)

    def test_create_order_api_disabled(self):
        self.client.login(email='subscriber@test.com', password='Password123')
        res = self.client.post(
            reverse('subscriptions:create_order'),
            data=json.dumps({'plan': 'pro'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('Razorpay checkout is disabled', res.json().get('error', ''))

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


class ManualUPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='student@test.com',
            name='Student Test',
            password='Password123'
        )
        self.admin_user = User.objects.create_user(
            email='admin@tradex.com',
            name='Tradex Admin',
            password='Password123'
        )
        self.other_user = User.objects.create_user(
            email='hacker@test.com',
            name='Random User',
            password='Password123'
        )

    def test_manual_checkout_anonymous_redirects_to_login(self):
        url = reverse('subscriptions:manual_checkout', args=['starter'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/signin/', response.url)

    def test_manual_checkout_renders_qr_and_details(self):
        self.client.login(email='student@test.com', password='Password123')
        url = reverse('subscriptions:manual_checkout', args=['starter'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Indian Market Foundation')
        self.assertContains(response, 'data:image/png;base64,')
        self.assertContains(response, 'upi://pay?')

    def test_manual_checkout_blocks_active_subscription(self):
        self.client.login(email='student@test.com', password='Password123')
        Subscription.objects.create(
            user=self.user,
            plan_type='starter',
            plan_name='Indian Market Foundation',
            status='ACTIVE',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=90),
            amount_paid=3999.00
        )
        url = reverse('subscriptions:manual_checkout', args=['starter'])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('courses:dashboard'))

    def test_manual_checkout_invalid_utr_validation(self):
        self.client.login(email='student@test.com', password='Password123')
        url = reverse('subscriptions:manual_checkout', args=['starter'])
        
        # Non 12-digit UTR
        response = self.client.post(url, {'utr': '12345', 'payer_upi_id': 'student@okaxis'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a valid 12-digit UPI transaction reference')
        self.assertEqual(ManualPayment.objects.count(), 0)

        # Non-numeric UTR
        response = self.client.post(url, {'utr': '12345678ABCD', 'payer_upi_id': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a valid 12-digit UPI transaction reference')
        self.assertEqual(ManualPayment.objects.count(), 0)

    def test_manual_checkout_valid_submission_creates_pending(self):
        self.client.login(email='student@test.com', password='Password123')
        url = reverse('subscriptions:manual_checkout', args=['starter'])
        response = self.client.post(url, {
            'utr': '987654321012',
            'payer_upi_id': 'student@okhdfc'
        })
        self.assertRedirects(response, reverse('courses:dashboard'))

        payment = ManualPayment.objects.filter(user=self.user, utr='987654321012').first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.plan_key, 'starter')
        self.assertEqual(payment.amount, 3999.00)
        self.assertEqual(payment.payer_upi_id, 'student@okhdfc')

    def test_manual_checkout_blocks_duplicate_utr(self):
        ManualPayment.objects.create(
            user=self.other_user,
            plan_key='starter',
            amount=3999.00,
            status='pending',
            utr='112233445566'
        )
        self.client.login(email='student@test.com', password='Password123')
        url = reverse('subscriptions:manual_checkout', args=['starter'])
        response = self.client.post(url, {'utr': '112233445566'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This UTR / transaction reference has already been submitted.')

    def test_admin_payments_security(self):
        # 1. Anonymous gets redirect to login
        url = reverse('subscriptions:admin_payments')
        res_anon = self.client.get(url)
        self.assertEqual(res_anon.status_code, 302)

        # 2. Non-admin user gets 404
        self.client.login(email='hacker@test.com', password='Password123')
        res_forbidden = self.client.get(url)
        self.assertEqual(res_forbidden.status_code, 404)

        # 3. Admin user in ADMIN_EMAILS gets 200
        self.client.login(email='admin@tradex.com', password='Password123')
        with self.settings(ADMIN_EMAILS='admin@tradex.com'):
            res_admin = self.client.get(url)
            self.assertEqual(res_admin.status_code, 200)
            self.assertContains(res_admin, 'Manual UPI Payments')

    def test_admin_payment_approval_flow(self):
        payment = ManualPayment.objects.create(
            user=self.user,
            plan_key='starter',
            amount=3999.00,
            status='pending',
            utr='998877665544'
        )

        approve_url = reverse('subscriptions:admin_payment_approve', args=[payment.id])

        # Non-admin cannot approve
        self.client.login(email='hacker@test.com', password='Password123')
        res = self.client.post(approve_url)
        self.assertEqual(res.status_code, 404)

        # Admin approves
        self.client.login(email='admin@tradex.com', password='Password123')
        with self.settings(ADMIN_EMAILS='admin@tradex.com'):
            res_approve = self.client.post(approve_url)
            self.assertRedirects(res_approve, reverse('subscriptions:admin_payments'))

            payment.refresh_from_db()
            self.assertEqual(payment.status, 'approved')
            self.assertEqual(payment.reviewed_by, self.admin_user)
            self.assertIsNotNone(payment.reviewed_at)

            # Subscription created
            sub = Subscription.objects.filter(user=self.user, status='ACTIVE').first()
            self.assertIsNotNone(sub)
            self.assertEqual(sub.plan_type, 'starter')
            self.assertTrue(sub.is_currently_active)

            # Notification created for user
            notif = UserNotification.objects.filter(user=self.user, notification_type='payment_approved').first()
            self.assertIsNotNone(notif)
            self.assertIn('Payment Confirmed', notif.title)
            self.assertFalse(notif.is_read)

            # Idempotent: approve again should not double extend
            end_date_before = sub.end_date
            self.client.post(approve_url)
            sub.refresh_from_db()
            self.assertEqual(sub.end_date, end_date_before)

    def test_admin_payment_approval_with_unlock_all(self):
        payment = ManualPayment.objects.create(
            user=self.user,
            plan_key='starter',
            amount=3999.00,
            status='pending',
            utr='112233445566'
        )
        approve_url = reverse('subscriptions:admin_payment_approve', args=[payment.id])
        self.client.login(email='admin@tradex.com', password='Password123')
        with self.settings(ADMIN_EMAILS='admin@tradex.com'):
            res = self.client.post(approve_url, {'unlock_all': 'true'})
            self.assertRedirects(res, reverse('subscriptions:admin_payments'))
            sub = Subscription.objects.filter(user=self.user, status='ACTIVE').first()
            self.assertIsNotNone(sub)
            self.assertEqual(sub.plan_type, 'combo')

    def test_admin_payment_rejection_flow(self):
        payment = ManualPayment.objects.create(
            user=self.user,
            plan_key='starter',
            amount=3999.00,
            status='pending',
            utr='554433221100'
        )

        reject_url = reverse('subscriptions:admin_payment_reject', args=[payment.id])

        # Admin rejects
        self.client.login(email='admin@tradex.com', password='Password123')
        with self.settings(ADMIN_EMAILS='admin@tradex.com'):
            res = self.client.post(reject_url, {'reject_reason': 'UTR not found in bank credits'})
            self.assertRedirects(res, reverse('subscriptions:admin_payments'))

            payment.refresh_from_db()
            self.assertEqual(payment.status, 'rejected')
            self.assertEqual(payment.reject_reason, 'UTR not found in bank credits')
            self.assertEqual(payment.reviewed_by, self.admin_user)

            # User receives no subscription
            self.assertEqual(Subscription.objects.filter(user=self.user).count(), 0)

            # Rejection notification created
            notif = UserNotification.objects.filter(user=self.user, notification_type='payment_rejected').first()
            self.assertIsNotNone(notif)
            self.assertIn('Verification Notice', notif.title)

    def test_payment_mode_routing_to_manual_checkout(self):
        self.client.login(email='student@test.com', password='Password123')
        with self.settings(PAYMENT_MODE='manual_upi'):
            res = self.client.get(reverse('subscriptions:initiate_upi_payment_plan', args=['starter']))
            self.assertRedirects(res, reverse('root_pay_plan', args=['starter']))

            res_checkout = self.client.get(reverse('subscriptions:checkout') + '?plan=starter')
            self.assertEqual(res_checkout.status_code, 200)
            self.assertContains(res_checkout, 'Pay ₹3999 via UPI')
            self.assertContains(res_checkout, '/pay/starter/')
            self.assertContains(res_checkout, 'Secure UPI payment')
            self.assertContains(res_checkout, 'UPI payments only')
            self.assertContains(res_checkout, 'Access activated after payment verification')
            self.assertNotContains(res_checkout, 'checkout.razorpay.com')

    def test_plan_specific_access_isolation(self):
        cat_indian = Category.objects.create(name='Indian Market', slug='indian-market')
        subcat_indian = SubCategory.objects.create(parent=cat_indian, name='IM Basics', slug='im-basics', tier_required='standard')
        cat_forex = Category.objects.create(name='Forex', slug='forex')
        subcat_forex = SubCategory.objects.create(parent=cat_forex, name='Forex Basics', slug='fx-basics', tier_required='gold_strategy')

        # 1. Approving starter unlocks ONLY Indian Market, NOT Forex
        payment_starter = ManualPayment.objects.create(
            user=self.user,
            plan_key='starter',
            amount=3999.00,
            status='pending',
            utr='123456789012'
        )
        self.client.login(email='admin@tradex.com', password='Password123')
        with self.settings(ADMIN_EMAILS='admin@tradex.com'):
            self.client.post(reverse('subscriptions:admin_payment_approve', args=[payment_starter.id]))
            self.assertTrue(subcat_indian.is_accessible_by(self.user))
            self.assertFalse(subcat_forex.is_accessible_by(self.user))

        # Reset user subscriptions
        self.user.subscriptions.all().delete()

        # 2. Approving pro unlocks ONLY Forex, NOT Indian Market
        payment_pro = ManualPayment.objects.create(
            user=self.user,
            plan_key='pro',
            amount=9999.00,
            status='pending',
            utr='123456789013'
        )
        with self.settings(ADMIN_EMAILS='admin@tradex.com'):
            self.client.post(reverse('subscriptions:admin_payment_approve', args=[payment_pro.id]))
            self.assertFalse(subcat_indian.is_accessible_by(self.user))
            self.assertTrue(subcat_forex.is_accessible_by(self.user))

        # Reset
        self.user.subscriptions.all().delete()

        # 3. Approving elite unlocks BOTH
        payment_elite = ManualPayment.objects.create(
            user=self.user,
            plan_key='elite',
            amount=11999.00,
            status='pending',
            utr='123456789014'
        )
        with self.settings(ADMIN_EMAILS='admin@tradex.com'):
            self.client.post(reverse('subscriptions:admin_payment_approve', args=[payment_elite.id]))
            self.assertTrue(subcat_indian.is_accessible_by(self.user))
            self.assertTrue(subcat_forex.is_accessible_by(self.user))

        # 4. Rejecting unlocks nothing
        self.user.subscriptions.all().delete()
        payment_rejected = ManualPayment.objects.create(
            user=self.user,
            plan_key='starter',
            amount=3999.00,
            status='pending',
            utr='123456789015'
        )
        with self.settings(ADMIN_EMAILS='admin@tradex.com'):
            self.client.post(reverse('subscriptions:admin_payment_reject', args=[payment_rejected.id]), {'reject_reason': 'Invalid UTR'})
            self.assertFalse(subcat_indian.is_accessible_by(self.user))
            self.assertFalse(subcat_forex.is_accessible_by(self.user))
            self.assertEqual(self.user.subscriptions.filter(status='ACTIVE').count(), 0)

    def test_dashboard_pending_and_rejected_cards(self):
        self.client.login(email='student@test.com', password='Password123')
        payment = ManualPayment.objects.create(
            user=self.user,
            plan_key='starter',
            amount=3999.00,
            status='pending',
            utr='998877665511'
        )
        res = self.client.get(reverse('courses:dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Payment under verification')
        self.assertContains(res, '998877665511')

        # Now test rejected state
        payment.status = 'rejected'
        payment.reject_reason = 'Invalid reference number'
        payment.reviewed_at = timezone.now()
        payment.save()

        res_rej = self.client.get(reverse('courses:dashboard'))
        self.assertEqual(res_rej.status_code, 200)
        self.assertContains(res_rej, 'Payment Verification Rejected')
        self.assertContains(res_rej, 'Invalid reference number')
        self.assertContains(res_rej, 'Try again')

    def test_notification_read_api(self):
        notif = UserNotification.objects.create(
            user=self.user,
            title='Test Alert',
            message='Test message content',
            is_read=False
        )
        self.client.login(email=self.user.email, password='Password123')
        read_url = reverse('subscriptions:mark_notification_read', args=[notif.id])
        res = self.client.post(read_url)
        self.assertEqual(res.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

        # Mark all read
        notif2 = UserNotification.objects.create(user=self.user, title='Alert 2', message='Msg 2', is_read=False)
        read_all_url = reverse('subscriptions:mark_all_notifications_read')
        res_all = self.client.post(read_all_url)
        self.assertEqual(res_all.status_code, 200)
        notif2.refresh_from_db()
        self.assertTrue(notif2.is_read)


