from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


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
        ('standard', 'Indian Market Foundation (₹3,999)'),
        ('gold_strategy', 'Forex Gold Mastery (₹9,999)'),
        ('combo', 'Complete Trader (₹11,999)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan_type = models.CharField(max_length=50, choices=PLAN_TYPE_CHOICES, default='combo', db_index=True)
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
        # Default end_date: 365 days (12 months) for combo, 180 days (6 months) for gold_strategy, 90 days for standard
        if not self.end_date and self.start_date:
            days = 365 if self.plan_type == 'combo' else (180 if self.plan_type == 'gold_strategy' else 90)
            self.end_date = self.start_date + timedelta(days=days)
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.user.email} - {self.plan_name} ({self.status})"

    @property
    def is_currently_active(self):
        """Dynamic check: must have ACTIVE status and end_date in future"""
        return self.status == 'ACTIVE' and bool(self.end_date and self.end_date > timezone.now())

    def grants_access_to(self, tier_required):
        """
        Check if this subscription tier covers the required curriculum tier.
        - 'combo' covers everything ('standard', 'gold_strategy', 'combo')
        - 'gold_strategy' covers 'gold_strategy'
        - 'standard' covers 'standard'
        """
        if not self.is_currently_active:
            return False
        if self.plan_type == 'combo':
            return True
        return self.plan_type == tier_required


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
