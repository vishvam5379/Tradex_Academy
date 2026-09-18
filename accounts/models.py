from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField('Email Address', unique=True, db_index=True)
    name = models.CharField('Full Name', max_length=150)
    phone = models.CharField('Phone Number', max_length=20, blank=True, null=True)
    referral_code = models.CharField('Referral Code', max_length=50, blank=True, null=True)
    
    is_active = models.BooleanField('Active', default=True)
    is_staff = models.BooleanField('Staff Status', default=False)
    date_joined = models.DateTimeField('Date Joined', default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.name} ({self.email})"

    @property
    def has_active_subscription(self):
        """Check if user has an active, unexpired subscription"""
        return self.subscriptions.filter(
            status='ACTIVE',
            end_date__gt=timezone.now()
        ).exists()

    @property
    def active_subscription(self):
        """Returns the most recent active subscription or None"""
        return self.subscriptions.filter(
            status='ACTIVE',
            end_date__gt=timezone.now()
        ).order_by('-end_date').first()

    @property
    def subscription_days_remaining(self):
        """Calculates days remaining on current active subscription"""
        sub = self.active_subscription
        if not sub:
            return 0
        diff = sub.end_date - timezone.now()
        return max(0, diff.days + (1 if diff.seconds > 0 else 0))
