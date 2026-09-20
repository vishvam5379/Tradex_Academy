import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Register PyMySQL as MySQLdb before Django loads the DB backend
try:
    import pymysql
    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.install_as_MySQLdb()
except Exception:
    pass


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load .env file
load_dotenv(BASE_DIR / '.env')

# Quick-start development settings - unsuitable for production
# Prioritizes SECRET_KEY, falls back to DJANGO_SECRET_KEY, with a safe development fallback
_env_secret = (os.getenv('SECRET_KEY') or os.getenv('DJANGO_SECRET_KEY') or '').strip()
SECRET_KEY = _env_secret if _env_secret else 'django-insecure-dev-fallback-key-change-in-production'

DEBUG = (os.getenv('DJANGO_DEBUG') or os.getenv('DEBUG', 'False')).lower() in ('true', '1', 'yes')

# Base allowed hosts: always include Vercel domains and local dev
base_hosts = ['.vercel.app', '.now.sh', 'localhost', '127.0.0.1', '[::1]']
allowed_hosts_env = os.getenv('ALLOWED_HOSTS')
if allowed_hosts_env and allowed_hosts_env != '*':
    ALLOWED_HOSTS = list(set(base_hosts + [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]))
else:
    ALLOWED_HOSTS = base_hosts + ['*']


CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://*.now.sh',
    'http://127.0.0.1',
    'http://localhost',
]
csrf_origins_env = os.getenv('CSRF_TRUSTED_ORIGINS')
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS.extend([o.strip() for o in csrf_origins_env.split(',') if o.strip()])

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
# Supports DATABASE_URL (for Supabase/Neon/Railway/TiDB/Aiven) or DB_* env vars or SQLite fallback
IS_VERCEL = 'VERCEL' in os.environ or os.getenv('IS_VERCEL', 'False').lower() in ('true', '1', 'yes')

database_url = (os.getenv('DATABASE_URL') or '').strip()
raw_use_sqlite = os.getenv('USE_SQLITE')
db_host = (os.getenv('DB_HOST') or '').strip()

# Detect whether a valid remote database host is supplied
has_remote_db = bool(database_url or (db_host and db_host.lower() not in ('127.0.0.1', 'localhost', '')))

if raw_use_sqlite is not None:
    USE_SQLITE = raw_use_sqlite.lower() in ('true', '1', 'yes')
else:
    USE_SQLITE = not has_remote_db

# On Vercel, MySQL on localhost/127.0.0.1 cannot run; gracefully fall back to SQLite if no remote host is provided
if IS_VERCEL and not USE_SQLITE and not has_remote_db:
    USE_SQLITE = True

if database_url:
    try:
        import dj_database_url
        DATABASES = {
            'default': dj_database_url.config(
                default=database_url,
                conn_max_age=600,
                conn_health_checks=True,
            )
        }
    except Exception as e:
        print(f"Warning: Failed to parse DATABASE_URL ({e}), falling back to SQLite")
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': str(BASE_DIR / 'db.sqlite3'),
            }
        }
elif not USE_SQLITE and has_remote_db:
    db_options = {
        'charset': 'utf8mb4',
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    }
    if os.getenv('DB_SSL', 'False').lower() in ('true', '1', 'yes') or os.getenv('DB_SSL_CA'):
        ssl_config = {}
        if os.getenv('DB_SSL_CA'):
            ssl_config['ca'] = os.getenv('DB_SSL_CA')
        db_options['ssl'] = ssl_config

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'trading_academy'),
            'USER': os.getenv('DB_USER', 'root'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': db_host,
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': db_options,
        }
    }
else:
    if IS_VERCEL:
        tmp_db = Path('/tmp/db.sqlite3')
        base_db = BASE_DIR / 'db.sqlite3'
        if not tmp_db.exists() and base_db.exists():
            try:
                import shutil
                shutil.copyfile(str(base_db), str(tmp_db))
            except Exception as e:
                print(f"Notice: SQLite copy to /tmp skipped: {e}")
        db_path = str(tmp_db) if tmp_db.exists() else str(base_db)
    else:
        db_path = str(BASE_DIR / 'db.sqlite3')

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': db_path,
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
WHITENOISE_MANIFEST_STRICT = False

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

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
RAZORPAY_KEY_ID = (os.getenv('RAZORPAY_KEY_ID') or '').strip() or 'rzp_test_mock_key_id'
RAZORPAY_KEY_SECRET = (os.getenv('RAZORPAY_KEY_SECRET') or '').strip() or 'mock_secret_key'
RAZORPAY_CURRENCY = (os.getenv('RAZORPAY_CURRENCY') or '').strip() or 'INR'

def _safe_int_env(name, default):
    val = (os.getenv(name) or '').strip()
    try:
        return int(val) if val else default
    except ValueError:
        return default

SUBSCRIPTION_PLANS = {
    'standard': {
        'code': 'standard',
        'name': 'Standard Trading Academy',
        'price': _safe_int_env('PLAN_STANDARD_PRICE', 5000),
        'duration_days': 60,
        'description': 'Full access to Indian Market (Futures, Options, Stock Trading) and Spot Gold fundamentals.',
        'badge': 'Standard Pass (2 Months)',
    },
    'gold_strategy': {
        'code': 'gold_strategy',
        'name': 'Forex Gold Strategy + Strategy Indicator',
        'price': _safe_int_env('PLAN_GOLD_PRICE', 10000),
        'duration_days': 60,
        'description': 'Specialized institutional Forex Gold Strategy curriculum based on pure price action plus exclusive proprietary Strategy Indicator.',
        'badge': 'Special Strategy & Indicator (2 Months)',
    },
    'combo': {
        'code': 'combo',
        'name': 'Combined Master Access (Full Bundle)',
        'price': _safe_int_env('PLAN_COMBO_PRICE', 12500),
        'duration_days': 150,  # 5 Months
        'description': 'Complete all-in-one access for 5 months: Includes BOTH ₹5,000 Standard Content and ₹10,000 Forex Gold Strategy & Indicator + VIP Community Access for regular Gold trade setups.',
        'badge': 'Best Value • 5 Months + VIP Community',
    },
}


SUBSCRIPTION_PRICE = SUBSCRIPTION_PLANS['standard']['price']
SUBSCRIPTION_DURATION_DAYS = 60

