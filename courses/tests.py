from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

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
        # Must strictly redirect to subscription plan / checkout page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/subscriptions/checkout/', response.url)

    def test_video_player_unlocked_for_subscribed_user(self):
        self.client.login(email='pro@test.com', password='Pass123')
        response = self.client.get(reverse('courses:video_player', args=['forex', 'commodity', self.gold_video.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gold Trading Strategy')
