from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest import mock

from courses.models import Category, SubCategory, Video
from subscriptions.models import Subscription

User = get_user_model()


class CoursesTests(TestCase):
    def setUp(self):
        # 1. Create Category Tree with exact 4 subcategories
        self.forex_cat = Category.objects.create(name='Forex', slug='forex', order=1)
        self.indian_market_cat = Category.objects.create(name='Indian Market', slug='indian-market', order=2)
        
        self.commodity_sub = SubCategory.objects.create(parent=self.forex_cat, name='Commodity', slug='commodity', order=1)
        self.futures_sub = SubCategory.objects.create(parent=self.indian_market_cat, name='Futures', slug='futures', order=1)
        self.options_sub = SubCategory.objects.create(parent=self.indian_market_cat, name='Options', slug='options', order=2)
        self.stocks_sub = SubCategory.objects.create(parent=self.indian_market_cat, name='Stock Trading', slug='stock-trading', order=3)
        
        # 2. Create sample lessons (all locked by default)
        self.gold_video = Video.objects.create(
            sub_category=self.commodity_sub,
            title='Gold Trading Strategy',
            slug='gold-trading-strategy',
            duration=900,
            order=1
        )
        self.nifty_futures_video = Video.objects.create(
            sub_category=self.futures_sub,
            title='Nifty Futures Rollover',
            slug='nifty-futures-rollover',
            duration=1200,
            order=1
        )

        # 3. Users
        self.free_user = User.objects.create_user(email='free@test.com', name='Free User', password='Pass123')
        self.subscribed_user = User.objects.create_user(email='pro@test.com', name='Pro User', password='Pass123')
        
        # Give active 60-day subscription to pro user
        Subscription.objects.create(
            user=self.subscribed_user,
            status='ACTIVE',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=60),
            amount_paid=5000.00
        )

    def test_category_video_list_view_for_all_subcategories(self):
        self.client.login(email='free@test.com', password='Pass123')
        
        # Check all 4 subcategories respond 200
        for cat_slug, sub_slug in [
            ('forex', 'commodity'),
            ('indian-market', 'futures'),
            ('indian-market', 'options'),
            ('indian-market', 'stock-trading')
        ]:
            response = self.client.get(reverse('courses:category_videos', args=[cat_slug, sub_slug]))
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['is_subscribed'])

    def test_video_player_locked_for_unsubscribed_user(self):
        self.client.login(email='free@test.com', password='Pass123')
        response = self.client.get(reverse('courses:video_player', args=['forex', 'commodity', self.gold_video.id]))
        # Must strictly redirect to subscription plan / payment page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/subscriptions/pay/pro/', response.url)

    def test_video_player_unlocked_for_subscribed_user(self):
        self.client.login(email='pro@test.com', password='Pass123')
        response = self.client.get(reverse('courses:video_player', args=['forex', 'commodity', self.gold_video.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gold Trading Strategy')

    def test_youtube_embed_url_conversion(self):
        video = Video(video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        self.assertEqual(video.youtube_embed_url, 'https://www.youtube.com/embed/dQw4w9WgXcQ')
        video_short = Video(video_url='https://youtu.be/dQw4w9WgXcQ')
        self.assertEqual(video_short.youtube_embed_url, 'https://www.youtube.com/embed/dQw4w9WgXcQ')

    def test_expired_combo_subscription_denies_vip_access(self):
        expired_combo_user = User.objects.create_user(email='expired_combo@test.com', name='Expired Combo', password='Pass123')
        Subscription.objects.create(
            user=expired_combo_user,
            status='ACTIVE',
            plan_type='combo',
            start_date=timezone.now() - timedelta(days=200),
            end_date=timezone.now() - timedelta(days=50),
            amount_paid=12500.00
        )
        self.client.login(email='expired_combo@test.com', password='Pass123')
        response = self.client.get(reverse('courses:community'))
        self.assertFalse(response.context['has_combo_access'])


class LectureSystemTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin@tradingacademy.com',
            name='Admin User',
            password='AdminPassword123',
            is_staff=True,
            is_superuser=True,
        )
        self.regular_user = User.objects.create_user(
            email='student@example.com',
            name='Student User',
            password='StudentPassword123'
        )
        self.starter_user = User.objects.create_user(
            email='starter@example.com',
            name='Starter User',
            password='StarterPassword123'
        )
        Subscription.objects.create(
            user=self.starter_user,
            status='ACTIVE',
            plan_type='standard',
            plan_name='Indian Market Foundation',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=90),
            amount_paid=3999.00
        )
        self.pro_user = User.objects.create_user(
            email='pro_gold@example.com',
            name='Pro User',
            password='ProPassword123'
        )
        Subscription.objects.create(
            user=self.pro_user,
            status='ACTIVE',
            plan_type='gold_strategy',
            plan_name='Forex Gold Mastery',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=180),
            amount_paid=9999.00
        )
        self.elite_user = User.objects.create_user(
            email='elite@example.com',
            name='Elite User',
            password='ElitePassword123'
        )
        Subscription.objects.create(
            user=self.elite_user,
            status='ACTIVE',
            plan_type='combo',
            plan_name='Complete Trader',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            amount_paid=11999.00
        )

        from courses.models import Lecture
        self.indian_lecture = Lecture.objects.create(
            title='Nifty Breakout Structure',
            course='indian_market',
            position=1,
            video_path='indian_market/01_nifty.mp4',
            duration_seconds=725
        )
        self.forex_lecture = Lecture.objects.create(
            title='XAUUSD London Session Sweep',
            course='forex_gold',
            position=1,
            video_path='forex_gold/01_xauusd.mp4',
            duration_seconds=3665
        )

    def test_lecture_duration_formatting(self):
        self.assertEqual(self.indian_lecture.duration_formatted, '12:05')
        self.assertEqual(self.forex_lecture.duration_formatted, '01:01:05')

    def test_subscription_access_isolation(self):
        # Regular user cannot access either
        self.assertFalse(self.indian_lecture.is_accessible_by(self.regular_user))
        self.assertFalse(self.forex_lecture.is_accessible_by(self.regular_user))

        # Starter user can only access Indian Market
        self.assertTrue(self.indian_lecture.is_accessible_by(self.starter_user))
        self.assertFalse(self.forex_lecture.is_accessible_by(self.starter_user))

        # Pro user can only access Forex Gold
        self.assertFalse(self.forex_lecture.is_accessible_by(self.regular_user))
        self.assertTrue(self.forex_lecture.is_accessible_by(self.pro_user))
        self.assertFalse(self.indian_lecture.is_accessible_by(self.pro_user))

        # Elite user can access both
        self.assertTrue(self.indian_lecture.is_accessible_by(self.elite_user))
        self.assertTrue(self.forex_lecture.is_accessible_by(self.elite_user))

        # Admin / staff can access both
        self.assertTrue(self.indian_lecture.is_accessible_by(self.admin_user))
        self.assertTrue(self.forex_lecture.is_accessible_by(self.admin_user))

    def test_admin_lectures_security_unauthenticated(self):
        response = self.client.get('/admin/lectures/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/signin/', response.url)

    def test_admin_lectures_security_non_admin_gets_404(self):
        self.client.login(email='student@example.com', password='StudentPassword123')
        response = self.client.get('/admin/lectures/')
        self.assertEqual(response.status_code, 404)

    def test_admin_lectures_accessible_by_admin(self):
        self.client.login(email='admin@tradingacademy.com', password='AdminPassword123')
        response = self.client.get('/admin/lectures/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nifty Breakout Structure')
        self.assertContains(response, 'XAUUSD London Session Sweep')

    @mock.patch('courses.views_admin.MAX_UPLOAD_SIZE_BYTES', 50)
    def test_admin_lecture_upload_size_limit(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.login(email='admin@tradingacademy.com', password='AdminPassword123')

        # 200 bytes exceeds patched limit of 50 bytes
        oversized_data = b'0' * 200
        big_file = SimpleUploadedFile("big_video.mp4", oversized_data, content_type="video/mp4")

        response = self.client.post('/admin/lectures/', {
            'title': 'Oversized Lesson',
            'course': 'indian_market',
            'position': 2,
            'video_file': big_file,
        })
        self.assertEqual(response.status_code, 200)
        from courses.models import Lecture
        self.assertFalse(Lecture.objects.filter(title='Oversized Lesson').exists())
        self.assertContains(response, 'exceeds maximum allowed limit')

    def test_admin_lecture_delete(self):
        from courses.models import Lecture
        self.client.login(email='admin@tradingacademy.com', password='AdminPassword123')
        lec = Lecture.objects.create(
            title='Temporary Lesson',
            course='indian_market',
            position=99,
            video_path='local_mock/temp.mp4'
        )
        response = self.client.post(f'/admin/lectures/{lec.id}/delete/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Lecture.objects.filter(id=lec.id).exists())

    def test_lecture_player_paywall_redirect(self):
        # Student user with no subscription is redirected to pay page
        self.client.login(email='student@example.com', password='StudentPassword123')
        response = self.client.get(reverse('courses:lecture_player', args=[self.indian_lecture.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/pay/starter/', response.url)

    def test_lecture_player_subscribed_playback(self):
        # Starter user can watch Indian Market lecture
        self.client.login(email='starter@example.com', password='StarterPassword123')
        response = self.client.get(reverse('courses:lecture_player', args=[self.indian_lecture.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nifty Breakout Structure')
        self.assertContains(response, '<video id="lectureVideoPlayer"')
