from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone


class Category(models.Model):
    """Top-level Market category (e.g., Forex, Indian Market)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='chart-candlestick', help_text='Icon identifier (lucide/fontawesome style)')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    """Sub-category leaf (e.g. Spot Gold under Forex; Futures, Options, Stock Trading under Indian Market)"""
    TIER_CHOICES = [
        ('standard', 'Standard Academy (₹5,000)'),
        ('gold_strategy', 'Gold Strategy + Indicator (₹10,000)'),
    ]

    parent = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    badge = models.CharField(max_length=50, blank=True, help_text='e.g., Special Indicator ₹10,000, F&O, Equity')
    tier_required = models.CharField(max_length=50, choices=TIER_CHOICES, default='standard', help_text='Subscription tier required to unlock')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sub-Category'
        verbose_name_plural = 'Sub-Categories'
        unique_together = ('parent', 'slug')
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent.name} → {self.name}"

    @property
    def total_videos(self):
        return self.videos.count()

    @property
    def total_duration_minutes(self):
        total_seconds = sum(video.duration for video in self.videos.all())
        return round(total_seconds / 60)

    def is_accessible_by(self, user):
        """Check if given user has access to this subcategory curriculum"""
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        for sub in user.subscriptions.filter(status='ACTIVE', end_date__gt=timezone.now()):
            if sub.grants_access_to(self.tier_required):
                return True
        return False



class Video(models.Model):
    """Course Video Lesson"""
    sub_category = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    description = models.TextField(blank=True)
    
    # Hybrid Video Hosting support: URL/Stream link or direct upload
    video_url = models.URLField(max_length=500, blank=True, help_text='External video streaming URL (YouTube Unlisted, Vimeo, Cloudflare Stream, S3)')
    video_file = models.FileField(upload_to='courses/videos/', blank=True, null=True, help_text='Direct video file upload')
    
    # Thumbnails
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True, null=True)
    thumbnail_url = models.URLField(max_length=500, blank=True, help_text='Alternative image URL for thumbnail')
    
    duration = models.PositiveIntegerField(default=600, help_text='Duration in seconds (e.g. 900 for 15 mins)')
    order = models.PositiveIntegerField(default=0)
    is_free_preview = models.BooleanField(default=False, help_text='Allow non-subscribers to preview this video')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Video Lesson'
        verbose_name_plural = 'Video Lessons'
        ordering = ['order', 'id']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.sub_category.name}] {self.title}"

    @property
    def duration_formatted(self):
        """Returns MM:SS or HH:MM:SS format"""
        minutes, seconds = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def get_thumbnail_src(self):
        if self.thumbnail:
            return self.thumbnail.url
        if self.thumbnail_url:
            return self.thumbnail_url
        return "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80"


class WatchProgress(models.Model):
    """Track user's watching progress per video"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watch_history')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='progress_records')
    last_position_seconds = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'video')
        verbose_name = 'Watch Progress'
        verbose_name_plural = 'Watch Progress'

    def __str__(self):
        return f"{self.user.email} - {self.video.title} ({'Done' if self.completed else 'In-progress'})"


class CommunityChannel(models.Model):
    """Telegram-style Channels inside Combo Master Community"""
    CHANNEL_TYPES = [
        ('announcements', '📢 Announcements (Mentor Only)'),
        ('setups', '📊 Trade Setups'),
        ('general', '💬 General Discussion'),
        ('trading', '🎓 Trading Discussion'),
    ]

    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    channel_type = models.CharField(max_length=50, choices=CHANNEL_TYPES, default='general')
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=50, default='message-square')
    order = models.PositiveIntegerField(default=0)
    is_mentor_only_posting = models.BooleanField(default=False, help_text='Only staff/mentors can post in this channel')

    class Meta:
        verbose_name = 'Community Channel'
        verbose_name_plural = 'Community Channels'
        ordering = ['order', 'id']

    def __str__(self):
        return self.name


class CommunityMessage(models.Model):
    """Telegram-style message inside a Community Channel"""
    channel = models.ForeignKey(CommunityChannel, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_messages')
    
    content = models.TextField()
    is_mentor_post = models.BooleanField(default=False)
    
    # Structured Trade Setup Details (Used for Trade Setup Channel posts)
    is_trade_setup = models.BooleanField(default=False)
    setup_symbol = models.CharField(max_length=100, blank=True, help_text='e.g. XAUUSD BUY SETUP')
    setup_entry = models.CharField(max_length=100, blank=True)
    setup_sl = models.CharField(max_length=100, blank=True)
    setup_tp1 = models.CharField(max_length=100, blank=True)
    setup_tp2 = models.CharField(max_length=100, blank=True)
    setup_chart_text = models.TextField(blank=True, help_text='Chart analysis notes')

    image_url = models.URLField(max_length=500, blank=True)
    parent_reply = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    is_pinned = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Community Message'
        verbose_name_plural = 'Community Messages'
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.channel.name}] {self.user.email}: {self.content[:30]}"

