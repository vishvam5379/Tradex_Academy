from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from courses.models import CommunityChannel, CommunityMessage

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed Telegram-style Community Channels and Messages'

    def handle(self, *args, **options):
        self.stdout.write('Seeding Community Channels & Messages...')

        # Get or create admin / mentor user
        mentor = User.objects.filter(is_superuser=True).first()
        if not mentor:
            mentor = User.objects.filter(email='pro_trader@example.com').first()
        if not mentor:
            mentor, _ = User.objects.get_or_create(
                email='mentor@tradex.com',
                defaults={'name': 'Senior Mentor (Tradex)', 'is_staff': True}
            )

        pro_user = User.objects.filter(email='pro_trader@example.com').first()
        if not pro_user:
            pro_user = mentor

        # Create Channels
        announcements_ch, _ = CommunityChannel.objects.get_or_create(
            slug='announcements',
            defaults={
                'name': '📢 Announcements',
                'channel_type': 'announcements',
                'description': 'Official updates & market news (Mentor only)',
                'icon': 'megaphone',
                'order': 1,
                'is_mentor_only_posting': True,
            }
        )

        setups_ch, _ = CommunityChannel.objects.get_or_create(
            slug='trade-setups',
            defaults={
                'name': '📊 Trade Setups',
                'channel_type': 'setups',
                'description': 'High probability Gold (XAUUSD) & Indian Market setups',
                'icon': 'trending-up',
                'order': 2,
                'is_mentor_only_posting': False,
            }
        )

        general_ch, _ = CommunityChannel.objects.get_or_create(
            slug='general',
            defaults={
                'name': '💬 General Discussion',
                'channel_type': 'general',
                'description': 'Chat with fellow traders & mentors',
                'icon': 'message-circle',
                'order': 3,
                'is_mentor_only_posting': False,
            }
        )

        trading_ch, _ = CommunityChannel.objects.get_or_create(
            slug='trading-discussion',
            defaults={
                'name': '🎓 Trading Discussion',
                'channel_type': 'trading',
                'description': 'Forex Gold Strategy & price action Q&A',
                'icon': 'graduation-cap',
                'order': 4,
                'is_mentor_only_posting': False,
            }
        )

        # Clear existing messages to prevent duplicates on re-seed
        CommunityMessage.objects.all().delete()

        # 1. Seed Announcements
        CommunityMessage.objects.create(
            channel=announcements_ch,
            user=mentor,
            is_mentor_post=True,
            is_pinned=True,
            content="🔥 Welcome to the ₹12,500 Combo Master Private VIP Community!\n\nThis channel is reserved exclusively for active Combo Master members. Daily Gold (XAUUSD) setups, Indian Market F&O signals, and institutional market breakdowns will be posted here live."
        )

        # 2. Seed Trade Setups (matching exact prompt image format)
        setup_msg = CommunityMessage.objects.create(
            channel=setups_ch,
            user=mentor,
            is_mentor_post=True,
            is_trade_setup=True,
            setup_symbol="🟡 XAUUSD BUY SETUP",
            setup_entry="2650 - 2655",
            setup_sl="2640",
            setup_tp1="2665",
            setup_tp2="2675",
            setup_chart_text="Price approaching key 4H demand zone after liquidity sweep of London session lows. Look for bullish 5-minute candle confirmation before entry.",
            content="📊 New High Probability Trade Setup posted for Gold (XAUUSD)."
        )

        # User reply to trade setup
        reply1 = CommunityMessage.objects.create(
            channel=setups_ch,
            user=pro_user,
            is_mentor_post=False,
            parent_reply=setup_msg,
            content="Is this setup still active?"
        )

        # Mentor reply
        CommunityMessage.objects.create(
            channel=setups_ch,
            user=mentor,
            is_mentor_post=True,
            parent_reply=reply1,
            content="Yes, setup is active. Price is currently testing 2652 entry zone."
        )

        # Additional Trade Setup for Indian Market
        CommunityMessage.objects.create(
            channel=setups_ch,
            user=mentor,
            is_mentor_post=True,
            is_trade_setup=True,
            setup_symbol="🇮🇳 NIFTY 50 OCT FUT (BUY / CALL)",
            setup_entry="25,320",
            setup_sl="25,240",
            setup_tp1="25,450",
            setup_tp2="25,560",
            setup_chart_text="Nifty bouncing off 20 EMA on 15m timeframe with heavy institutional buying in Banking sector. Trail SL once TP1 is hit.",
            content="🇮🇳 Nifty Futures Breakout Setup."
        )

        # 3. Seed General Discussion
        CommunityMessage.objects.create(
            channel=general_ch,
            user=pro_user,
            is_mentor_post=False,
            content="Good morning everyone! Looking forward to today's US NFP news release."
        )

        CommunityMessage.objects.create(
            channel=general_ch,
            user=mentor,
            is_mentor_post=True,
            content="Morning traders! Make sure to manage risk carefully around news events. Check out the latest Gold analysis in #trade-setups."
        )

        # 4. Seed Trading Discussion
        CommunityMessage.objects.create(
            channel=trading_ch,
            user=pro_user,
            is_mentor_post=False,
            content="The Pure Price Action Gold Strategy from Lesson 3 worked perfectly yesterday on the 15m chart!"
        )

        CommunityMessage.objects.create(
            channel=trading_ch,
            user=mentor,
            is_mentor_post=True,
            content="Excellent execution! Patience in waiting for liquidity sweeps is 90% of the edge in Gold trading."
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded Telegram-style Community Channels & Messages!'))
