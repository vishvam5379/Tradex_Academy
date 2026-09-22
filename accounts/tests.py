from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class AccountsTests(TestCase):
    def test_create_user_with_referral_code(self):
        user = User.objects.create_user(
            email='testuser@example.com',
            name='Test Trader',
            phone='+919876543210',
            referral_code='TRADER500',
            password='TestPassword123'
        )
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertEqual(user.name, 'Test Trader')
        self.assertEqual(user.referral_code, 'TRADER500')
        self.assertTrue(user.check_password('TestPassword123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.has_active_subscription)

    def test_signup_view_with_referral(self):
        response = self.client.post(reverse('accounts:signup'), {
            'name': 'New Trader',
            'email': 'newtrader@example.com',
            'phone': '+919876543210',
            'referral_code': 'REF2026',
            'password': 'StrongPassword123',
            'confirm_password': 'StrongPassword123'
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='newtrader@example.com')
        self.assertEqual(user.referral_code, 'REF2026')

    def test_signin_view(self):
        User.objects.create_user(
            email='existing@example.com',
            name='Existing Trader',
            password='Password123'
        )
        response = self.client.post(reverse('accounts:signin'), {
            'email': 'existing@example.com',
            'password': 'Password123'
        })
        self.assertEqual(response.status_code, 302)

    def test_profile_view_update(self):
        user = User.objects.create_user(
            email='editprofile@example.com',
            name='Original Name',
            phone='+919876543210',
            password='Password123'
        )
        self.client.login(email='editprofile@example.com', password='Password123')
        
        # GET profile page
        get_res = self.client.get(reverse('accounts:profile'))
        self.assertEqual(get_res.status_code, 200)

        # POST update profile
        post_res = self.client.post(reverse('accounts:profile'), {
            'action': 'update_profile',
            'name': 'Updated Name',
            'email': 'editprofile@example.com',
            'phone': '+919999900000'
        })
        self.assertEqual(post_res.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.name, 'Updated Name')
        self.assertEqual(user.phone, '+919999900000')

    def test_signin_with_none_string_next_url(self):
        User.objects.create_user(
            email='testnone@example.com',
            name='Test None',
            password='Password123'
        )
        # Test literal string "None" in GET query
        response = self.client.post(reverse('accounts:signin') + '?next=None', {
            'email': 'testnone@example.com',
            'password': 'Password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('courses:dashboard'))

        # Test literal string "None" in POST body
        self.client.logout()
        response_post = self.client.post(reverse('accounts:signin'), {
            'email': 'testnone@example.com',
            'password': 'Password123',
            'next': 'None'
        })
        self.assertEqual(response_post.status_code, 302)
        self.assertEqual(response_post.url, reverse('courses:dashboard'))

    def test_signin_redirect_to_pay_plan(self):
        User.objects.create_user(
            email='payuser@example.com',
            name='Pay User',
            password='Password123'
        )
        # Unauthenticated user visits /pay/pro/
        res_pay = self.client.get('/pay/pro/')
        self.assertEqual(res_pay.status_code, 302)
        self.assertIn(reverse('accounts:signin'), res_pay.url)
        self.assertTrue('next=/pay/pro/' in res_pay.url or 'next=%2Fpay%2Fpro%2F' in res_pay.url)

        # Signing in redirects to /pay/pro/
        res_login = self.client.post(reverse('accounts:signin') + '?next=/pay/pro/', {
            'email': 'payuser@example.com',
            'password': 'Password123'
        })
        self.assertEqual(res_login.status_code, 302)
        self.assertEqual(res_login.url, '/pay/pro/')

    def test_signin_redirect_to_admin_payments(self):
        User.objects.create_user(
            email='admin@tradex.com',
            name='Admin User',
            password='Password123'
        )
        # Unauthenticated user visits /admin/payments/
        res_admin = self.client.get('/admin/payments/')
        self.assertEqual(res_admin.status_code, 302)
        self.assertIn(reverse('accounts:signin'), res_admin.url)
        self.assertTrue('next=/admin/payments/' in res_admin.url or 'next=%2Fadmin%2Fpayments%2F' in res_admin.url)

        # Signing in redirects to /admin/payments/
        res_login = self.client.post(reverse('accounts:signin') + '?next=/admin/payments/', {
            'email': 'admin@tradex.com',
            'password': 'Password123'
        })
        self.assertEqual(res_login.status_code, 302)
        self.assertEqual(res_login.url, '/admin/payments/')

    def test_signin_without_next_param_goes_to_dashboard(self):
        User.objects.create_user(
            email='normaluser@example.com',
            name='Normal User',
            password='Password123'
        )
        response = self.client.post(reverse('accounts:signin'), {
            'email': 'normaluser@example.com',
            'password': 'Password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('courses:dashboard'))

    def test_signin_open_redirect_rejected(self):
        User.objects.create_user(
            email='openuser@example.com',
            name='Open User',
            password='Password123'
        )
        # Malicious external redirect attempt
        response = self.client.post(reverse('accounts:signin') + '?next=https://evil.com/phishing', {
            'email': 'openuser@example.com',
            'password': 'Password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('courses:dashboard'))
