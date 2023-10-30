import django_heroku
from .base import *
from decouple import config
import dj_database_url

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:80",
    "http://localhost",
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
SECURE_SSL_REDIRECT = True

# Prevent site from being loaded in iFrame
X_FRAME_OPTIONS = 'DENY'

# CSP
# CSP_DEFAULT_SRC = ("'self'",)

# Prevent MIME-sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True


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

# BANK_FLEX
BANK_FLEX_BASE_URL = env('BANK_FLEX_BASE_URL')

# BANK_ONE BANKS
BANK_ONE_BANKS = env('BANK_ONE_BANKS')

# Activate Django-Heroku.
django_heroku.settings(locals())
