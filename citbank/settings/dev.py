import django_heroku
from .base import *
from decouple import config
import dj_database_url

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'ae6c628d540ddbfbfb7fc53287189b085cd39fdf333a863c1eb84eab7661'

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
        'NAME': 'citbank_db',
        'USER': 'citbank',
        'PASSWORD': 'citbank',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# BANK ONE API CREDENTIALS
BANK_ONE_AUTH_TOKEN = "405a3250-6758-4f16-a1a2-021029ed8bfb"
BANK_ONE_VERSION = "2"
BANK_ONE_BASE_URL = "https://staging.mybankone.com/BankOneWebAPI/api"

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=60),
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer', 'Token',),
}


# Activate Django-Heroku.
django_heroku.settings(locals())

