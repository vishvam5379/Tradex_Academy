from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from courses.models import Category, SubCategory, Video
from subscriptions.models import Subscription
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds initial course categories (Forex -> Spot Gold & Forex Gold Strategy + Indicator; Indian Market -> Futures, Options, Stock Trading) and lessons.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Trading Academy Course Data..."))

        # Clean old obsolete subcategories if any
        SubCategory.objects.filter(slug='commodity').delete()
        SubCategory.objects.filter(slug='futures-options').delete()

        # 1. Create Top-level Categories
        forex_cat, _ = Category.objects.get_or_create(
            slug='forex',
            defaults={
                'name': 'Forex',
                'description': 'Global currency exchange mechanics, spot gold liquidity models, and specialized algorithmic gold strategies.',
                'icon': 'globe',
                'order': 1
            }
        )

        indian_market_cat, _ = Category.objects.get_or_create(
            slug='indian-market',
            defaults={
                'name': 'Indian Market',
                'description': 'Master the Indian financial markets: NSE/BSE stock trading, Nifty/BankNifty derivative structures, and price action.',
                'icon': 'trending-up',
                'order': 2
            }
        )

        # 2. Create Sub-Categories
        # Forex -> Spot Gold (Standard Tier)
        spot_gold_sub, _ = SubCategory.objects.get_or_create(
            parent=forex_cat,
            slug='spot-gold',
            defaults={
                'name': 'Spot Gold (XAU/USD)',
                'badge': 'Precious Metals',
                'tier_required': 'standard',
                'description': 'Deep-dive trading methodologies strictly dedicated to Spot Gold (XAU/USD), London & NY session sweeps, and Dollar index correlations.',
                'order': 1
            }
        )
        spot_gold_sub.name = 'Spot Gold (XAU/USD)'
        spot_gold_sub.badge = 'Precious Metals'
        spot_gold_sub.tier_required = 'standard'
        spot_gold_sub.description = 'Deep-dive trading methodologies strictly dedicated to Spot Gold (XAU/USD), London & NY session sweeps, and Dollar index correlations.'
        spot_gold_sub.save()

        # Forex -> Special Forex Gold Strategy + Strategy Indicator (Special Tier ₹10,000)
        gold_strategy_sub, _ = SubCategory.objects.get_or_create(
            parent=forex_cat,
            slug='forex-gold-strategy',
            defaults={
                'name': 'Forex Gold Strategy & Strategy Indicator',
                'badge': 'Special Strategy & Indicator',
                'tier_required': 'gold_strategy',
                'description': 'Proprietary Forex Gold Strategy based on pure price action movement, custom Strategy Indicator algorithms, PineScript rules, and London Killzone execution.',
                'order': 2
            }
        )
        gold_strategy_sub.name = 'Forex Gold Strategy & Strategy Indicator'
        gold_strategy_sub.badge = 'Special Strategy & Indicator'
        gold_strategy_sub.tier_required = 'gold_strategy'
        gold_strategy_sub.description = 'Proprietary Forex Gold Strategy based on pure price action movement, custom Strategy Indicator algorithms, PineScript rules, and London Killzone execution.'
        gold_strategy_sub.save()


        # Indian Market -> Futures (Standard Tier)
        futures_sub, _ = SubCategory.objects.get_or_create(
            parent=indian_market_cat,
            slug='futures',
            defaults={
                'name': 'Futures',
                'badge': 'Index & Stock Futures',
                'tier_required': 'standard',
                'description': 'Futures contract mechanics, basis spread, rollover analysis, cost of carry, and hedging strategies for Nifty/BankNifty.',
                'order': 1
            }
        )
        futures_sub.tier_required = 'standard'
        futures_sub.save()

        # Indian Market -> Options (Standard Tier)
        options_sub, _ = SubCategory.objects.get_or_create(
            parent=indian_market_cat,
            slug='options',
            defaults={
                'name': 'Options',
                'badge': 'Greeks & Expiry Models',
                'tier_required': 'standard',
                'description': 'Option Greeks (Delta, Gamma, Theta, Vega), Open Interest (OI) analysis, Put-Call Ratio (PCR), and weekly expiry scalping.',
                'order': 2
            }
        )
        options_sub.tier_required = 'standard'
        options_sub.save()

        # Indian Market -> Stock Trading (Standard Tier)
        stocks_sub, _ = SubCategory.objects.get_or_create(
            parent=indian_market_cat,
            slug='stock-trading',
            defaults={
                'name': 'Stock Trading',
                'badge': 'Equities & Swing',
                'tier_required': 'standard',
                'description': 'Price action mastery, breakout trading, volume spread analysis, swing setups, and risk-reward optimization for Indian equities.',
                'order': 3
            }
        )
        stocks_sub.tier_required = 'standard'
        stocks_sub.save()

        # 3. Real video lectures are managed dynamically by admins via /admin/lectures/
        # Demo/placeholder video lessons have been removed.

        # 4. Create Demo Admin & Users
        admin_user, _ = User.objects.get_or_create(
            email='admin@tradingacademy.com',
            defaults={
                'name': 'Academy Admin',
                'phone': '+91 99999 88888',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('Admin@123456')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        # User 1: Combined All-Access (₹12,500 - 5 Months + VIP Community)
        demo_subscribed_user, _ = User.objects.get_or_create(
            email='pro_trader@example.com',
            defaults={
                'name': 'Rahul Sharma (Complete Trader)',
                'phone': '+91 98765 43210',
            }
        )
        demo_subscribed_user.set_password('Trader@123')
        demo_subscribed_user.save()

        Subscription.objects.update_or_create(
            user=demo_subscribed_user,
            status='ACTIVE',
            defaults={
                'plan_type': 'combo',
                'plan_name': 'Complete Trader (12 Months)',
                'amount_paid': 11999.00,
                'currency': 'INR',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=365),
                'razorpay_order_id': 'order_demo_combo_123',
                'razorpay_payment_id': 'pay_demo_combo_123',
                'razorpay_signature': 'sig_demo_combo_123',
            }
        )


        # User 2: Forex Gold Mastery (₹9,999)
        gold_user, _ = User.objects.get_or_create(
            email='gold_trader@example.com',
            defaults={
                'name': 'Vikram Mehta (Forex Gold Mastery)',
                'phone': '+91 98222 33344',
            }
        )
        gold_user.set_password('Gold@123')
        gold_user.save()

        Subscription.objects.update_or_create(
            user=gold_user,
            status='ACTIVE',
            defaults={
                'plan_type': 'gold_strategy',
                'plan_name': 'Forex Gold Mastery (₹9,999)',
                'amount_paid': 9999.00,
                'currency': 'INR',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=180),
                'razorpay_order_id': 'order_demo_gold_123',
                'razorpay_payment_id': 'pay_demo_gold_123',
                'razorpay_signature': 'sig_demo_gold_123',
            }
        )

        # User 3: Indian Market Foundation (₹3,999)
        standard_user, _ = User.objects.get_or_create(
            email='standard_trader@example.com',
            defaults={
                'name': 'Karan Patel (Indian Market Foundation)',
                'phone': '+91 97111 22233',
            }
        )
        standard_user.set_password('Standard@123')
        standard_user.save()

        Subscription.objects.update_or_create(
            user=standard_user,
            status='ACTIVE',
            defaults={
                'plan_type': 'standard',
                'plan_name': 'Indian Market Foundation (₹3,999)',
                'amount_paid': 3999.00,
                'currency': 'INR',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=90),
                'razorpay_order_id': 'order_demo_std_123',
                'razorpay_payment_id': 'pay_demo_std_123',
                'razorpay_signature': 'sig_demo_std_123',
            }
        )

        # User 4: Free User (No subscription)
        demo_free_user, _ = User.objects.get_or_create(
            email='free_user@example.com',
            defaults={
                'name': 'Amit Verma',
                'phone': '+91 91234 56789',
            }
        )
        demo_free_user.set_password('Free@123')
        demo_free_user.save()

        self.stdout.write(self.style.SUCCESS("[OK] Successfully seeded Trading Academy categories, lessons, and multi-tier demo users!"))
        self.stdout.write(self.style.SUCCESS("  - Admin: admin@tradingacademy.com / Admin@123456"))
        self.stdout.write(self.style.SUCCESS("  - Complete Trader (Rs. 11,999): pro_trader@example.com / Trader@123"))
        self.stdout.write(self.style.SUCCESS("  - Forex Gold Mastery (Rs. 9,999): gold_trader@example.com / Gold@123"))
        self.stdout.write(self.style.SUCCESS("  - Indian Market Foundation (Rs. 3,999): standard_trader@example.com / Standard@123"))
        self.stdout.write(self.style.SUCCESS("  - Free User: free_user@example.com / Free@123"))


