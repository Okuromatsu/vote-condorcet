"""
Django project settings for Condorcet Voting System
====================================================

Configuration file for Django project. Contains database settings, security
configurations, installed apps, middleware, and deployment settings.

Security features enabled:
- CSRF protection
- XSS prevention via template escaping
- SQL injection prevention via ORM
- Secure cookie settings
- Security headers (HSTS, X-Frame-Options, CSP)
"""

import os
import sys
from pathlib import Path
from decouple import config # pyright: ignore[reportMissingImports]
import dj_database_url # pyright: ignore[reportMissingImports]

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap5',
    'voting',  # Our main voting app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # i18n language selection
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # CSRF protection
    'voting.middleware.CsrfExemptLocalhost',  # Allow localhost CSRF in development
    'voting.middleware.DuplicateVoteMiddleware',  # Track voter sessions and prevent duplicates
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # Clickjacking protection
    'voting.middleware.SecurityHeadersMiddleware',  # Custom security headers
]

ROOT_URLCONF = 'condorcet_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'voting', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csrf',  # CSRF token in context
                'django.template.context_processors.i18n',  # i18n language context
            ],
        },
    },
]

WSGI_APPLICATION = 'condorcet_project.wsgi.application'

# Database configuration
# Default: SQLite (development)
# Production: PostgreSQL (set DATABASE_URL environment variable)
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    # Production: Use PostgreSQL via dj-database-url
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Development: Use SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db', 'db.sqlite3'),
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
LANGUAGE_CODE = 'en'
LANGUAGES = [
    ('en', 'English'),
    ('fr', 'Français'),
    ('es', 'Español'),
]
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Site configuration
SITE_URL = config('SITE_URL', default='http://localhost:8000').rstrip('/')
SITE_NAME = 'Condorcet Vote'

# Use simpler storage for development to avoid manifest issues
# Only use CompressedManifestStaticFilesStorage after running collectstatic in production
# Check if we are in a build process (dummy secret key)
IS_BUILD_PROCESS = SECRET_KEY == 'dummy-key-for-build'

if DEBUG or IS_BUILD_PROCESS:
    # Development or Build: Use simple storage (no manifest required)
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    # Production: Use whitenoise with manifest for efficiency
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================================
# SECURITY SETTINGS (CRITICAL FOR PRODUCTION)
# ============================================================================

# Trust the X-Forwarded-Proto header coming from the proxy (Traefik)
# This is required to prevent infinite redirect loops when running behind a proxy
SECURE_PROXY_SSL_HEADER = config('SECURE_PROXY_SSL_HEADER', default=None)
if SECURE_PROXY_SSL_HEADER:
    SECURE_PROXY_SSL_HEADER = tuple(SECURE_PROXY_SSL_HEADER.split(','))

# Only set to False in production (DEBUG must be False)
if not DEBUG:
    # Force HTTPS
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
    SECURE_BROWSER_XSS_FILTER = config('SECURE_BROWSER_XSS_FILTER', default=True, cast=bool)
    SESSION_COOKIE_SAMESITE = config('SESSION_COOKIE_SAMESITE', default='Strict')
    CSRF_COOKIE_SAMESITE = config('CSRF_COOKIE_SAMESITE', default='Strict')
    SECURE_CONTENT_SECURITY_POLICY = {
        'default-src': ("'self'",),
        'script-src': ("'self'", "'unsafe-inline'"),  # Consider removing unsafe-inline
        'style-src': ("'self'", "'unsafe-inline'"),
    }
else:
    # Development: Allow all cookies without strict security
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
    SESSION_COOKIE_SAMESITE = config('SESSION_COOKIE_SAMESITE', default='Lax')
    CSRF_COOKIE_SAMESITE = config('CSRF_COOKIE_SAMESITE', default='Lax')

# Session & Cookie settings
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=1209600, cast=int)  # 2 weeks
SESSION_COOKIE_HTTPONLY = config('SESSION_COOKIE_HTTPONLY', default=True, cast=bool)
CSRF_COOKIE_HTTPONLY = config('CSRF_COOKIE_HTTPONLY', default=True, cast=bool)

# Security Headers
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=True, cast=bool)
X_FRAME_OPTIONS = config('X_FRAME_OPTIONS', default='DENY')  # Prevent clickjacking

# CORS configuration (adjust for your domain)
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:8000'
).split(',')

# CSRF Trusted Origins (required for POST requests from localhost in development)
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000'
).split(',')

# CSRF settings
# In development, allow missing Referer header (null origin issue)
if DEBUG:
    CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000', 'http://localhost:3000']
    # Don't require Referer header in development
    CSRF_USE_SESSIONS = True

# Crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Logging configuration
# For production: Use file logging with logs/ directory created beforehand
# For development: Use console logging only
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} - {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO' if not DEBUG else 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Note: For production file logging, create logs/ directory and add FileHandler:
# - mkdir -p logs/
# - Then uncomment and modify the logging configuration above
