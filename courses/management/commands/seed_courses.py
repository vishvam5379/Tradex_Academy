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

        # 3. Create Sample Video Lessons
        lessons_data = [
            # Spot Gold Lessons (Pure Gold Focus, No Crude Oil)
            {
                'sub': spot_gold_sub,
                'title': 'Spot Gold (XAU/USD) Fundamentals & US Dollar (DXY) Correlation',
                'slug': 'spot-gold-fundamentals-dollar-correlation',
                'description': 'Understand how the US Dollar Index, Federal Reserve rate expectations, and global yields dictate Spot Gold trend cycles.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1610375461246-83df859d849d?auto=format&fit=crop&w=800&q=80',
                'duration': 1420,
                'order': 1,
            },
            {
                'sub': spot_gold_sub,
                'title': 'London & New York Session Gold Liquidity Sweeps',
                'slug': 'london-ny-session-gold-liquidity-sweeps',
                'description': 'How institutional algorithms hunt stop orders at session opens (08:00 GMT London / 13:30 GMT NY) and trigger major intraday reversals in Gold.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80',
                'duration': 1680,
                'order': 2,
            },
            {
                'sub': spot_gold_sub,
                'title': 'Spot Gold Support & Resistance Pivot Breakout Blueprint',
                'slug': 'spot-gold-pivot-breakout-blueprint',
                'description': 'Trading high-probability breakout expansions using dynamic 4-hour key levels, Daily open pivots, and Asian range boundaries in Gold.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1642543492481-44e81e3914a7?auto=format&fit=crop&w=800&q=80',
                'duration': 1350,
                'order': 3,
            },
            {
                'sub': spot_gold_sub,
                'title': 'Risk Management, Lot Sizing & ATR Parameters for Gold',
                'slug': 'risk-management-lot-sizing-atr-gold',
                'description': 'Accurate pip value calculations for XAU/USD, Average True Range (ATR) stop positioning, and preserving trading capital during high-volatility news events.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=800&q=80',
                'duration': 1120,
                'order': 4,
            },

            # Special Forex Gold Strategy & Strategy Indicator Lessons (Special Curriculum)
            {
                'sub': gold_strategy_sub,
                'title': 'Proprietary Forex Gold Strategy Framework & Indicator Setup',
                'slug': 'proprietary-forex-gold-strategy-indicator-setup',
                'description': 'Introduction to the proprietary institutional Forex Gold Strategy. Setup and calibration of the custom Strategy Indicator on TradingView and MetaTrader.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1642790551116-18e150f248e5?auto=format&fit=crop&w=800&q=80',
                'duration': 2100,
                'order': 1,
            },
            {
                'sub': gold_strategy_sub,
                'title': 'Algorithmic Indicator Signals, Filter Rules & Volume Confluence',
                'slug': 'algorithmic-indicator-signals-filter-rules',
                'description': 'Deep-dive into the Strategy Indicator buy/sell signals, momentum confirmation filters, and how to eliminate false breakout signals during choppy consolidations.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80',
                'duration': 2350,
                'order': 2,
            },
            {
                'sub': gold_strategy_sub,
                'title': 'London Killzone Gold Scalping & Institutional Order Flow',
                'slug': 'london-killzone-gold-scalping-order-flow',
                'description': 'Execute high-probability 1-minute and 5-minute Gold scalps using the Strategy Indicator during peak London volume influx.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackSeeTheWorld.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=800&q=80',
                'duration': 1980,
                'order': 3,
            },
            {
                'sub': gold_strategy_sub,
                'title': 'Pure Price Action Gold Expansion & Core Gold Movement Strategy',
                'slug': 'pure-price-action-gold-expansion-movement-strategy',
                'description': 'Master the core pure price action strategy dictating how Gold moves across sessions without relying on complex indicator noise.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=800&q=80',
                'duration': 2240,
                'order': 4,
            },
            {
                'sub': gold_strategy_sub,
                'title': 'Live Trade Case Studies, Backtesting Data & Risk Engine',
                'slug': 'live-trade-case-studies-backtesting-gold',
                'description': 'Detailed breakdown of 50+ backtested live trade scenarios with exact indicator trigger points, stop placements, and compound growth metrics.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WhatCarCanYouGetForAGrand.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1610375461246-83df859d849d?auto=format&fit=crop&w=800&q=80',
                'duration': 2600,
                'order': 5,
            },


            # Futures Lessons
            {
                'sub': futures_sub,
                'title': 'Futures Contract Fundamentals: Margins & Mark-to-Market',
                'slug': 'futures-contract-fundamentals-margins-mtm',
                'description': 'Understand initial margin, SPAN + Exposure margin requirements, and how daily MTM settlement operates for index futures.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=800&q=80',
                'duration': 1540,
                'order': 1,
            },
            {
                'sub': futures_sub,
                'title': 'Rollover Data Analysis & Expiry Week Settlement',
                'slug': 'rollover-data-analysis-expiry-settlement',
                'description': 'How institutional desks roll positions between contract months, calculating cost of carry and spot-futures arbitrage.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyBlazes.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80',
                'duration': 1890,
                'order': 2,
            },
            {
                'sub': futures_sub,
                'title': 'Index Futures Breakout Strategies & VWAP Trend Following',
                'slug': 'index-futures-breakout-vwap-trend-following',
                'description': 'Intraday execution framework for Nifty and BankNifty futures using anchored VWAP and cumulative volume delta.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1535320903710-d993d3d77d29?auto=format&fit=crop&w=800&q=80',
                'duration': 1720,
                'order': 3,
            },

            # Options Lessons
            {
                'sub': options_sub,
                'title': 'Option Greeks Unlocked: Delta, Gamma, Theta & Vega',
                'slug': 'option-greeks-unlocked-delta-gamma-theta-vega',
                'description': 'A visual mathematical breakdown of Option Greeks and how time decay (Theta) impacts option buyers vs sellers on expiry day.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1642790551116-18e150f248e5?auto=format&fit=crop&w=800&q=80',
                'duration': 2100,
                'order': 1,
            },
            {
                'sub': options_sub,
                'title': 'Open Interest (OI) & PCR Analysis for Nifty/BankNifty',
                'slug': 'open-interest-pcr-analysis-nifty-banknifty',
                'description': 'Decipher institutional positioning through Put-Call Ratio (PCR) trends, Max Pain theory, and strike concentration.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackSeeTheWorld.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80',
                'duration': 1980,
                'order': 2,
            },
            {
                'sub': options_sub,
                'title': 'Option Selling: Iron Condors & Strangles with Adjustments',
                'slug': 'option-selling-iron-condors-strangles-adjustments',
                'description': 'Non-directional options selling frameworks for compounding weekly income with built-in risk hedges and rolling strategies.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=800&q=80',
                'duration': 2400,
                'order': 3,
            },

            # Stock Trading Lessons
            {
                'sub': stocks_sub,
                'title': 'Price Action Mastery: Market Structure, BOS & Order Blocks',
                'slug': 'price-action-mastery-market-structure-bos-order-blocks',
                'description': 'Identify true institutional footprints on daily and 15-minute charts using Break of Structure (BOS) and supply/demand zones.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1642543492481-44e81e3914a7?auto=format&fit=crop&w=800&q=80',
                'duration': 1950,
                'order': 1,
            },
            {
                'sub': stocks_sub,
                'title': 'Volume Spread Analysis (VSA) & Institutional Accumulation',
                'slug': 'volume-spread-analysis-institutional-accumulation',
                'description': 'Spot smart money absorption, fake breakouts, and high-volume spring candles before retail traders enter.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WhatCarCanYouGetForAGrand.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=800&q=80',
                'duration': 1620,
                'order': 2,
            },
            {
                'sub': stocks_sub,
                'title': 'Swing Trading Bluechip & Midcap Breakouts',
                'slug': 'swing-trading-bluechip-midcap-breakouts',
                'description': 'Screening Nifty 500 stocks for Cup & Handle, Stage 2 uptrends, and multi-week consolidation expansions.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
                'thumbnail_url': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80',
                'duration': 1480,
                'order': 3,
            },
        ]

        for item in lessons_data:
            Video.objects.update_or_create(
                sub_category=item['sub'],
                slug=item['slug'],
                defaults={
                    'title': item['title'],
                    'description': item['description'],
                    'video_url': item['video_url'],
                    'thumbnail_url': item['thumbnail_url'],
                    'duration': item['duration'],
                    'order': item['order'],
                    'is_free_preview': False,
                }
            )

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
                'name': 'Rahul Sharma (Combo Master)',
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
                'plan_name': 'Combined Master Access (5 Months + VIP Community)',
                'amount_paid': 12500.00,
                'currency': 'INR',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=150),
                'razorpay_order_id': 'order_demo_combo_123',
                'razorpay_payment_id': 'pay_demo_combo_123',
                'razorpay_signature': 'sig_demo_combo_123',
            }
        )


        # User 2: Gold Strategy + Indicator Only (₹10,000)
        gold_user, _ = User.objects.get_or_create(
            email='gold_trader@example.com',
            defaults={
                'name': 'Vikram Mehta (Gold Strategy)',
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
                'plan_name': 'Forex Gold Strategy + Strategy Indicator (₹10,000)',
                'amount_paid': 10000.00,
                'currency': 'INR',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=60),
                'razorpay_order_id': 'order_demo_gold_123',
                'razorpay_payment_id': 'pay_demo_gold_123',
                'razorpay_signature': 'sig_demo_gold_123',
            }
        )

        # User 3: Standard Academy Only (₹5,000)
        standard_user, _ = User.objects.get_or_create(
            email='standard_trader@example.com',
            defaults={
                'name': 'Karan Patel (Standard Pass)',
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
                'plan_name': 'Standard Trading Academy (₹5,000)',
                'amount_paid': 5000.00,
                'currency': 'INR',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=60),
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
        self.stdout.write(self.style.SUCCESS("  - Combo (Rs. 12,500): pro_trader@example.com / Trader@123"))
        self.stdout.write(self.style.SUCCESS("  - Gold Strategy (Rs. 10,000): gold_trader@example.com / Gold@123"))
        self.stdout.write(self.style.SUCCESS("  - Standard (Rs. 5,000): standard_trader@example.com / Standard@123"))
        self.stdout.write(self.style.SUCCESS("  - Free User: free_user@example.com / Free@123"))


