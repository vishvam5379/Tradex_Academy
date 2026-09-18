import os
from pathlib import Path
from dotenv import load_dotenv

import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load .env file
load_dotenv(BASE_DIR / '.env')

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-trading-academy-secret-key-change-in-prod-2026!')

DEBUG = True

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://*.now.sh',
    'http://127.0.0.1',
    'http://localhost',
]

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Custom apps
    'accounts.apps.AccountsConfig',
    'courses.apps.CoursesConfig',
    'subscriptions.apps.SubscriptionsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'academy_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'courses.context_processors.sidebar_categories',
                'subscriptions.context_processors.subscription_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'academy_core.wsgi.application'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Database Configuration
# Uses MySQL if USE_SQLITE is False, otherwise SQLite
USE_SQLITE = os.getenv('USE_SQLITE', 'True').lower() in ('true', '1', 'yes')

IS_VERCEL = 'VERCEL' in os.environ or os.getenv('IS_VERCEL', 'False').lower() in ('true', '1', 'yes')

if USE_SQLITE:
    if IS_VERCEL:
        tmp_db = Path('/tmp') / 'db.sqlite3'
        base_db = BASE_DIR / 'db.sqlite3'
        if not tmp_db.exists() and base_db.exists():
            import shutil
            try:
                shutil.copy2(base_db, tmp_db)
            except Exception:
                pass
        db_path = tmp_db if tmp_db.exists() else base_db
    else:
        db_path = BASE_DIR / 'db.sqlite3'

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': db_path,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'trading_academy'),
            'USER': os.getenv('DB_USER', 'root'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', '127.0.0.1'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            }
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Authentication Backends (supports login via email)
AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_USE_FINDERS = True

# Media files (Thumbnails, Video files)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Auth URLs
LOGIN_URL = 'accounts:signin'
LOGIN_REDIRECT_URL = 'courses:dashboard'
LOGOUT_REDIRECT_URL = 'courses:landing'

# Message Tags mapping to Tailwind/Modern alert classes
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# Razorpay & Multi-Tier Subscription Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_mock_key_id')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'mock_secret_key')
RAZORPAY_CURRENCY = os.getenv('RAZORPAY_CURRENCY', 'INR')

SUBSCRIPTION_PLANS = {
    'standard': {
        'code': 'standard',
        'name': 'Standard Trading Academy',
        'price': int(os.getenv('PLAN_STANDARD_PRICE', '5000')),
        'duration_days': 60,
        'description': 'Full access to Indian Market (Futures, Options, Stock Trading) and Spot Gold fundamentals.',
        'badge': 'Standard Pass (2 Months)',
    },
    'gold_strategy': {
        'code': 'gold_strategy',
        'name': 'Forex Gold Strategy + Strategy Indicator',
        'price': int(os.getenv('PLAN_GOLD_PRICE', '10000')),
        'duration_days': 60,
        'description': 'Specialized institutional Forex Gold Strategy curriculum based on pure price action plus exclusive proprietary Strategy Indicator.',
        'badge': 'Special Strategy & Indicator (2 Months)',
    },
    'combo': {
        'code': 'combo',
        'name': 'Combined Master Access (Full Bundle)',
        'price': int(os.getenv('PLAN_COMBO_PRICE', '12500')),
        'duration_days': 150,  # 5 Months
        'description': 'Complete all-in-one access for 5 months: Includes BOTH ₹5,000 Standard Content and ₹10,000 Forex Gold Strategy & Indicator + VIP Community Access for regular Gold trade setups.',
        'badge': 'Best Value • 5 Months + VIP Community',
    },
}


SUBSCRIPTION_PRICE = SUBSCRIPTION_PLANS['standard']['price']
SUBSCRIPTION_DURATION_DAYS = 60

