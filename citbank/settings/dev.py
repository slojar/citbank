from pathlib import Path
from .base import *
from decouple import config
from datetime import timedelta

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'ae6c628d540ddbfbfb7fc53287189b085cd39fdf333a863c1eb84eab7661'


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

print("----------------------- Running Development on Environment ------------------------------")


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

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=60),
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer', 'Token',),
}
