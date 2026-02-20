"""
Django settings for dukalink project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Get current ngrok URL from environment or use default
NGROK_URL = os.environ.get('NGROK_URL', 'https://3793-197-139-58-10.ngrok-free.app')

# ALLOWED_HOSTS configuration
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.ngrok-free.app',  # Allow all ngrok subdomains
    '3793-197-139-58-10.ngrok-free.app',  # Your specific ngrok URL
    'railway.app',
    'dukalink-production.up.railway.app',
    
]

# Add any additional hosts from environment variable
env_hosts = os.environ.get('ALLOWED_HOSTS', '')
if env_hosts:
    ALLOWED_HOSTS.extend([h.strip() for h in env_hosts.split(',') if h.strip()])

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://*.ngrok-free.app',
    'https://*.railway.app',  # Add this
    'https://*.up.railway.app',  # Add this
    NGROK_URL,
]

# Add any additional CSRF origins from environment
env_csrf = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if env_csrf:
    CSRF_TRUSTED_ORIGINS.extend([h.strip() for h in env_csrf.split(',') if h.strip()])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic',  # Add this before Django's staticfiles
    

    # Local apps
    'accounts',
    'products',
    'orders',
    'payments',
    'dashboard',
    'shops',
    'admin_dashboard',
    'pages',
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

ROOT_URLCONF = 'dukalink.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'dukalink.wsgi.application'

# Database - Use PostgreSQL on Railway, SQLite locally
import dj_database_url

# Check if we're on Railway (has DATABASE_URL environment variable)
if os.environ.get('DATABASE_URL'):
    # Production - PostgreSQL on Railway
    DATABASES = {
        'default': dj_database_url.config(
            conn_max_age=600,
            ssl_require=True
        )
    }
else:
    # Local development - SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'  # Changed to Nairobi timezone
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
# Create static directory if it doesn't exist (fixes the warning)
import os
if not os.path.exists(BASE_DIR / 'static'):
    os.makedirs(BASE_DIR / 'static')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Login URL
LOGIN_URL = 'accounts:login'

# ============================================
# M-PESA CONFIGURATION - LOADED FROM .env
# ============================================

# API Credentials
MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET')
MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY')

# Business Details
MPESA_BUSINESS_SHORTCODE = os.environ.get('MPESA_BUSINESS_SHORTCODE', '174379')
MPESA_LNM_SHORTCODE = os.environ.get('MPESA_LNM_SHORTCODE', '174379')
MPESA_TRANSACTION_TYPE = os.environ.get('MPESA_TRANSACTION_TYPE', 'CustomerPayBillOnline')

# Environment
MPESA_ENVIRONMENT = os.environ.get('MPESA_ENVIRONMENT', 'sandbox')

# Base API URL based on environment
if MPESA_ENVIRONMENT == 'production':
    MPESA_BASE_URL = 'https://api.safaricom.co.ke'
else:
    MPESA_BASE_URL = 'https://sandbox.safaricom.co.ke'

# Callback URLs - Use ngrok for local development
if DEBUG and NGROK_URL:
    MPESA_CALLBACK_URL = f"{NGROK_URL}/payments/mpesa-callback/"
    MPESA_TIMEOUT_URL = f"{NGROK_URL}/payments/mpesa-timeout/"
    MPESA_RESULT_URL = f"{NGROK_URL}/payments/mpesa-result/"
else:
    MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL', 'https://your-domain.com/payments/mpesa-callback/')
    MPESA_TIMEOUT_URL = os.environ.get('MPESA_TIMEOUT_URL', 'https://your-domain.com/payments/mpesa-timeout/')
    MPESA_RESULT_URL = os.environ.get('MPESA_RESULT_URL', 'https://your-domain.com/payments/mpesa-result/')

# ============================================
# EMAIL CONFIGURATION
# ============================================
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')

DEFAULT_FROM_EMAIL = 'DukaLink <noreply@dukalink.com>'
CONTACT_EMAIL = 'support@dukalink.com'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'