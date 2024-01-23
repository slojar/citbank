import django_heroku
from .base import *
from decouple import config
import dj_database_url

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:3000",
    "http://localhost:5000",
    "http://localhost:5050",
    "https://api-bankpro.tm-dev.xyz",
    "https://cit-corporate.netlify.app",
    "https://moneyfield-staging.vercel.app"
]

# CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Set the SECURE_PROXY_SSL_HEADER to indicate that the application is behind a proxy
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Ensure all requests are redirected to HTTPS
# SECURE_SSL_REDIRECT = True

# Prevent site from being loaded in iFrame
# X_FRAME_OPTIONS = 'DENY'

# CSP
# CSP_DEFAULT_SRC = ("'self'",)

# Prevent MIME-sniffing
# SECURE_CONTENT_TYPE_NOSNIFF = True


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': env('DATABASE_NAME'),
        'USER': env('DATABASE_USER'),
        'PASSWORD': env('DATABASE_PASSWORD'),
        'HOST': env('DATABASE_HOST'),
        'PORT': env('DATABASE_PORT'),
    }
}

# BANK ONE API CREDENTIALS
BANK_ONE_VERSION = env('BANK_ONE_VERSION')
BANK_ONE_BASE_URL = env('BANK_ONE_BASE_URL')
BANK_ONE_3PS_URL = env('BANK_ONE_3PS_URL')

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=60),
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer', 'Token',),
}

# TM SAAS
TM_BASE_URL = env('TM_BASE_URL')
TM_MANAGER_SERVICE_URL = env('TM_MANAGER_SERVICE_URL')
TM_VERIFICATION_URL = env('TM_VERIFICATION_URL')

# BANK_FLEX
BANK_FLEX_BASE_URL = env('BANK_FLEX_BASE_URL')

# BANK_ONE BANKS
BANK_ONE_BANKS = env('BANK_ONE_BANKS')

# PAYATTITUDE
PAYATTITUDE_BASE_URL = env('PAYATTITUDE_BASE_URL')
PAYATTITUDE_KEY = env('PAYATTITUDE_KEY')
PAYATTITUDE_SETTLEMENT_ACCOUNT = env('PAYATTITUDE_SETTLEMENT_ACCOUNT')

# Activate Django-Heroku.
django_heroku.settings(locals())
