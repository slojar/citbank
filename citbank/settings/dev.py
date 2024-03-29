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

CORS_ALLOW_ALL_ORIGINS = True
# CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': "citbank_db",
        'USER': "citbank",
        'PASSWORD': "citbank",
        'HOST': "localhost",
        'PORT': "5432",
    }
}

# BANK ONE API CREDENTIALS
BANK_ONE_AUTH_TOKEN = env('BANK_ONE_AUTH_TOKEN')
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
TM_CLIENT_ID = env('TM_CLIENT_ID')
TM_BASE_URL = env('TM_BASE_URL')

SERVICE_CHARGE = env('SERVICE_CHARGE')

# Activate Django-Heroku.
django_heroku.settings(locals())

