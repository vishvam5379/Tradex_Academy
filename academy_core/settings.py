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

# Base allowed hosts: always include Vercel domains, local dev, and test runner
base_hosts = ['.vercel.app', '.now.sh', 'localhost', '127.0.0.1', '[::1]', 'testserver']
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
    'django.contrib.sites',

    # Django Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Custom apps
    'accounts.apps.AccountsConfig',
    'courses.apps.CoursesConfig',
    'subscriptions.apps.SubscriptionsConfig',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
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
# Local Development: USE_SQLITE=True uses SQLite
# Production: USE_SQLITE=False uses Supabase PostgreSQL (via DB_* env vars or DATABASE_URL)
IS_VERCEL = 'VERCEL' in os.environ or os.getenv('IS_VERCEL', 'False').lower() in ('true', '1', 'yes')

database_url = (os.getenv('DATABASE_URL') or '').strip()
raw_use_sqlite = os.getenv('USE_SQLITE')
db_host = (os.getenv('DB_HOST') or '').strip()
db_user = (os.getenv('DB_USER') or 'postgres').strip()

# Check if remote database credentials (Supabase) are provided
has_remote_db = bool(database_url or db_host)

if raw_use_sqlite is not None:
    USE_SQLITE = raw_use_sqlite.lower() in ('true', '1', 'yes')
else:
    # If not explicitly specified, use SQLite locally unless a remote DB is configured
    USE_SQLITE = not has_remote_db

# On Vercel, if USE_SQLITE=False was set but no Supabase host was configured, fall back to SQLite to prevent crashing
if IS_VERCEL and not USE_SQLITE and not has_remote_db:
    USE_SQLITE = True

# Django's test runner should never create/drop tables on the remote database.
if 'test' in sys.argv:
    USE_SQLITE = True

# Supabase direct host (db.<project>.supabase.co) resolves to IPv6 only.
# AWS Lambda / Vercel does not support outbound IPv6, which causes:
# psycopg2.OperationalError: Cannot assign requested address
# Automatically adapt to Supabase's IPv4 connection pooler in ap-southeast-2 with pooler username.
if 'db.boqxnyjlqsyhnjkfddjk.supabase.co' in db_host:
    db_host = 'aws-0-ap-southeast-2.pooler.supabase.com'
    if db_user == 'postgres':
        db_user = 'postgres.boqxnyjlqsyhnjkfddjk'

if database_url and 'db.boqxnyjlqsyhnjkfddjk.supabase.co' in database_url:
    database_url = database_url.replace(
        'db.boqxnyjlqsyhnjkfddjk.supabase.co',
        'aws-0-ap-southeast-2.pooler.supabase.com'
    ).replace('://postgres:', '://postgres.boqxnyjlqsyhnjkfddjk:')

if USE_SQLITE:
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
elif database_url:
    try:
        import dj_database_url
        DATABASES = {
            'default': dj_database_url.config(
                default=database_url,
                conn_max_age=0 if IS_VERCEL else 60,
                conn_health_checks=True,
                ssl_require=True,
            )
        }
        # Ensure sslmode is required for Supabase
        DATABASES['default'].setdefault('OPTIONS', {})['sslmode'] = 'require'
    except Exception as e:
        print(f"Warning: Failed to parse DATABASE_URL ({e}), falling back to SQLite")
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': str(BASE_DIR / 'db.sqlite3'),
            }
        }
else:
    # Supabase PostgreSQL via individual environment variables
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'postgres'),
            'USER': db_user,
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': db_host,
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': 0 if IS_VERCEL else 60,
            'OPTIONS': {
                'sslmode': 'require',
            },
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

# Authentication Backends (supports email login and Django Allauth social accounts)
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'accounts.backends.EmailAuthBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
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

# Auth URLs (named routes — dashboard lives at /dashboard/, not /courses/dashboard/)
LOGIN_URL = 'accounts:signin'
LOGIN_REDIRECT_URL = 'courses:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:signin'

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Tradex Academy <noreply@tradex.academy>')

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
RAZORPAY_KEY_ID = (os.getenv('RAZORPAY_KEY_ID') or '').strip() or 'rzp_test_placeholder_key_id'
RAZORPAY_KEY_SECRET = (os.getenv('RAZORPAY_KEY_SECRET') or '').strip() or 'mock_secret_key'
RAZORPAY_WEBHOOK_SECRET = (os.getenv('RAZORPAY_WEBHOOK_SECRET') or '').strip()
RAZORPAY_CURRENCY = (os.getenv('RAZORPAY_CURRENCY') or '').strip() or 'INR'

def _safe_int_env(name, default):
    val = (os.getenv(name) or '').strip()
    try:
        return int(val) if val else default
    except ValueError:
        return default

SUBSCRIPTION_PLANS = {
    'starter': {
        'code': 'starter',
        'name': 'Indian Market Foundation',
        'price': _safe_int_env('PLAN_STARTER_PRICE', 3999),
        'duration_days': 90,
        'description': 'Learn to read charts and analyse stocks with a clear method.',
        'badge': 'Core Curriculum',
        'course_slug': 'indian-market',
    },
    'pro': {
        'code': 'pro',
        'name': 'Forex Gold Mastery',
        'price': _safe_int_env('PLAN_PRO_PRICE', 9999),
        'duration_days': 180,
        'description': 'A complete, repeatable system for trading gold on any timeframe.',
        'badge': 'Forex Gold System',
        'course_slug': 'forex',
    },
    'elite': {
        'code': 'elite',
        'name': 'Complete Trader',
        'price': _safe_int_env('PLAN_ELITE_PRICE', 11999),
        'duration_days': 365,  # 12 Months
        'description': 'Everything in both courses plus bonuses, for a full year.',
        'badge': '12 Months Access',
        'course_slug': 'all',
    },
}

# Compatibility aliases
SUBSCRIPTION_PLANS['standard'] = SUBSCRIPTION_PLANS['starter']
SUBSCRIPTION_PLANS['gold_strategy'] = SUBSCRIPTION_PLANS['pro']
SUBSCRIPTION_PLANS['combo'] = SUBSCRIPTION_PLANS['elite']

PLAN_ACCESS_MAPPING = {
    'starter': ['indian-market'],
    'standard': ['indian-market'],
    'pro': ['forex'],
    'gold_strategy': ['forex'],
    'elite': ['indian-market', 'forex'],
    'combo': ['indian-market', 'forex'],
}


SUBSCRIPTION_PRICE = SUBSCRIPTION_PLANS['standard']['price']
SUBSCRIPTION_DURATION_DAYS = 90

# Payment Flow Mode: 'manual_upi' (Direct QR + UTR verification) or 'razorpay' (Automated webhook payment links)
PAYMENT_MODE = (os.getenv('PAYMENT_MODE') or 'manual_upi').lower().strip()
MANUAL_UPI_ID = (os.getenv('MANUAL_UPI_ID') or '9313858614@ibl').strip()
MANUAL_UPI_NAME = (os.getenv('MANUAL_UPI_NAME') or 'Tradex Academy').strip()
MANUAL_UPI_PHONE = (os.getenv('MANUAL_UPI_PHONE') or '9313858614').strip()
ADMIN_EMAILS = (os.getenv('ADMIN_EMAILS') or 'sukhadiyavishvam22@gmail.com,200.vishvam.newljit@gmail.com,admin@tradex.com').strip()

# Google OAuth 2.0 Settings
GOOGLE_CLIENT_ID = (os.getenv('GOOGLE_CLIENT_ID') or '').strip()
GOOGLE_CLIENT_SECRET = (os.getenv('GOOGLE_CLIENT_SECRET') or '').strip()
GOOGLE_REDIRECT_URI = (os.getenv('GOOGLE_REDIRECT_URI') or '').strip()

# Email (used by password reset, etc.)
# Without this, Django defaults to SMTP on localhost:25, which does not exist
# on Vercel and crashes the password-reset flow with a connection error.
EMAIL_HOST = (os.getenv('EMAIL_HOST') or '').strip()
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = _safe_int_env('EMAIL_PORT', 587)
    EMAIL_HOST_USER = (os.getenv('EMAIL_HOST_USER') or '').strip()
    EMAIL_HOST_PASSWORD = (os.getenv('EMAIL_HOST_PASSWORD') or '').strip()
    EMAIL_USE_TLS = (os.getenv('EMAIL_USE_TLS', 'True')).lower() in ('true', '1', 'yes')
    DEFAULT_FROM_EMAIL = (os.getenv('DEFAULT_FROM_EMAIL') or EMAIL_HOST_USER or 'no-reply@tradexacademy.com')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'no-reply@tradexacademy.com'
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID)

# Django Allauth Configuration
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_LOGOUT_REDIRECT_URL = '/accounts/signin/'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https' if IS_VERCEL else 'http'

# Social Account Configuration
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# Custom Adapters for Custom User Model
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.CustomSocialAccountAdapter'
ACCOUNT_ADAPTER = 'accounts.adapters.CustomAccountAdapter'

# Google OAuth 2.0 Provider Configuration for Allauth
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': GOOGLE_CLIENT_ID,
            'secret': GOOGLE_CLIENT_SECRET,
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
        'FETCH_USERINFO': True,
    }
}

