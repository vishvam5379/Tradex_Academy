from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Order(models.Model):
    """Payment / Order record tracking payment link lifecycle"""
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    plan = models.CharField(max_length=50, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Server-enforced amount in INR
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', db_index=True)
    gateway_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)  # Razorpay Payment Link ID (plink_...)
    gateway_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)  # Razorpay Payment ID (pay_...)
    short_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.user.email} - {self.plan} ({self.status})"


class Subscription(models.Model):
    """User Subscription Plan Record"""
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('PENDING', 'Pending Verification'),
        ('FAILED', 'Payment Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PLAN_TYPE_CHOICES = [
        ('starter', 'Indian Market Foundation (₹3,999)'),
        ('pro', 'Forex Gold Mastery (₹9,999)'),
        ('elite', 'Complete Trader (₹11,999)'),
        ('standard', 'Indian Market Foundation (₹3,999)'),
        ('gold_strategy', 'Forex Gold Mastery (₹9,999)'),
        ('combo', 'Complete Trader (₹11,999)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan_type = models.CharField(max_length=50, choices=PLAN_TYPE_CHOICES, default='elite', db_index=True)
    plan_name = models.CharField(max_length=100, default='Complete Trader (12 Months)')
    
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=3999.00)
    currency = models.CharField(max_length=10, default='INR')
    
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    
    # Razorpay Details
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Default end_date: 365 days for elite/combo, 180 days for pro/gold_strategy, 90 days for starter/standard
        if not self.end_date and self.start_date:
            plan_key = self.plan_type.lower()
            if plan_key in ['elite', 'combo']:
                days = 365
            elif plan_key in ['pro', 'gold_strategy']:
                days = 180
            else:
                days = 90
            self.end_date = self.start_date + timedelta(days=days)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.plan_name} ({self.status})"

    @property
    def is_currently_active(self):
        """Dynamic check: must have ACTIVE status and end_date in future"""
        return self.status == 'ACTIVE' and bool(self.end_date and self.end_date > timezone.now())

    @property
    def is_active(self):
        return self.is_currently_active

    @property
    def expiry_date(self):
        return self.end_date

    def grants_access_to(self, course_or_tier):
        """
        Check if this subscription tier covers the required curriculum tier or course slug.
        - 'elite' or 'combo' covers everything ('indian-market', 'forex', 'starter', 'pro', 'elite')
        - 'pro' or 'gold_strategy' covers 'forex' and 'gold_strategy' / 'pro'
        - 'starter' or 'standard' covers 'indian-market' and 'standard' / 'starter'
        """
        if not self.is_currently_active:
            return False
        
        plan_key = self.plan_type.lower()
        if plan_key in ['elite', 'combo']:
            return True
        
        target = str(course_or_tier).lower()
        if plan_key in ['pro', 'gold_strategy']:
            return target in ['forex', 'gold_strategy', 'pro']
        if plan_key in ['starter', 'standard']:
            return target in ['indian-market', 'standard', 'starter']
        return False

    @property
    def days_remaining(self):
        """Number of full days left before expiry"""
        if not self.is_currently_active:
            return 0
        diff = self.end_date - timezone.now()
        return max(0, diff.days + (1 if diff.seconds > 0 else 0))

    @property
    def validity_percentage_left(self):
        """Percentage of the validity remaining for progress bars"""
        if not self.is_currently_active or not self.start_date or not self.end_date:
            return 0
        total_duration = (self.end_date - self.start_date).total_seconds()
        remaining = (self.end_date - timezone.now()).total_seconds()
        if total_duration <= 0:
            return 0
        return min(100, max(0, round((remaining / total_duration) * 100)))


class ManualPayment(models.Model):
    """
    Manual UPI Payment record submitted by user with UTR and optional screenshot.
    Reviewed and approved/rejected by Admin via /admin/payments/.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='manual_payments'
    )
    plan_key = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    utr = models.CharField(max_length=50, unique=True, help_text='12-digit UPI transaction reference')
    payer_upi_id = models.CharField(max_length=100, blank=True, null=True)
    screenshot_path = models.CharField(max_length=500, blank=True, null=True, help_text='Supabase Storage file path')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_manual_payments'
    )
    reject_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'manual_payments'
        ordering = ['-created_at']
        verbose_name = 'Manual Payment'
        verbose_name_plural = 'Manual Payments'

    def __str__(self):
        return f"ManualPayment #{self.id} - {self.user.email} - {self.plan_key} ({self.status}) - UTR: {self.utr}"

    @property
    def plan_name(self):
        plans = getattr(settings, 'SUBSCRIPTION_PLANS', {})
        return plans.get(self.plan_key, {}).get('name', self.plan_key.title())

