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

    def test_password_reset_view(self):
        res = self.client.get(reverse('accounts:password_reset'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Forgot password')
