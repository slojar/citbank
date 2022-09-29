from .base import *
from pathlib import Path
from datetime import timedelta

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['api.citmfb.com']

# DATABASE
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

# CORS
# CORS_ALLOWED_ORIGINS = [
#     "http://api.citmfb.com",
#     "https://api.citmfb.com",
# ]

CORS_ALLOW_ALL_ORIGINS = True
# CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# BANK ONE API CREDENTIALS
BANK_ONE_AUTH_TOKEN = env('BANK_ONE_AUTH_TOKEN')
BANK_ONE_VERSION = env('BANK_ONE_VERSION')
BANK_ONE_BASE_URL = env('BANK_ONE_BASE_URL')
BANK_ONE_3PS_URL = env('BANK_ONE_3PS_URL')

# TM SAAS
TM_CLIENT_ID = env('TM_CLIENT_ID')
TM_BASE_URL = env('TM_BASE_URL')

SERVICE_CHARGE = env('SERVICE_CHARGE')

# GRAYLOG
GRAYLOG_ENDPOINT = env('GRAYLOG_ENDPOINT')
GRAYLOG_HEADERS = True

# JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=2),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer', "Token"),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

