from .base import *
from pathlib import Path
from datetime import timedelta

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['api.citmfb.com', 'api.bankpro.ng']

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
CORS_ALLOWED_ORIGINS = [
    "https://api.citmfb.com",
    "https://api.moneyfieldmfb.com",
    "https://admin.citmfb.com",
    "https://admin.moneyfieldmfb.com",
    "https://ibank.citmfb.com",
    "https://ibank.moneyfieldmfb.com",
    "https://api.bankpro.ng",
    "https://ibank.kcmfb.com",
    "https://administrator.kcmfb.com",
]

# CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Set the SECURE_PROXY_SSL_HEADER to indicate that the application is behind a proxy
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Ensure all requests are redirected to HTTPS
# SECURE_SSL_REDIRECT = True

# Prevent site from being loaded in iFrame
X_FRAME_OPTIONS = 'DENY'

# CSP
# CSP_DEFAULT_SRC = ("'self'",)

# Prevent MIME-sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True

# BANK ONE API CREDENTIALS
BANK_ONE_VERSION = env('BANK_ONE_VERSION')
BANK_ONE_BASE_URL = env('BANK_ONE_BASE_URL')
BANK_ONE_3PS_URL = env('BANK_ONE_3PS_URL')

# TM SAAS
TM_BASE_URL = env('TM_BASE_URL')
TM_MANAGER_SERVICE_URL = env('TM_MANAGER_SERVICE_URL')

# GRAYLOG
GRAYLOG_ENDPOINT = env('GRAYLOG_ENDPOINT')
GRAYLOG_HEADERS = True

# BANK_FLEX
BANK_FLEX_BASE_URL = env('BANK_FLEX_BASE_URL')

# BANK_ONE BANKS
BANK_ONE_BANKS = env('BANK_ONE_BANKS')

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

# PAYATTITUDE
PAYATTITUDE_BASE_URL = env('PAYATTITUDE_BASE_URL')
PAYATTITUDE_KEY = env('PAYATTITUDE_KEY')
PAYATTITUDE_SETTLEMENT_ACCOUNT = env('PAYATTITUDE_SETTLEMENT_ACCOUNT')



