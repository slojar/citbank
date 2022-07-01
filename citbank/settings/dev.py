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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR/'uploads/'


# BANK ONE API CREDENTIALS
BANK_ONE_AUTH_TOKEN = "405a3250-6758-4f16-a1a2-021029ed8bfb"
BANK_ONE_VERSION = "2"
BANK_ONE_BASE_URL = "https://staging.mybankone.com/BankOneWebAPI/api"

# CIT
CIT_INSTITUTION_CODE = "100321"
CIT_MFB_CODE = "100125"
CIT_EMAIL_FROM = "support@citmfb.com"

# Temporal FIX for Email Sending
EMAIL_FROM = 'CIT MFB <noreply@citmfb.com>'
EMAIL_HOST = 'smtp.mailgun.org'
EMAIL_PORT = 587
EMAIL_HOST_USER = 'postmaster@wealthexinvestment.com'
EMAIL_HOST_PASSWORD = 'b515562100d40e8e7762b1ffce379331-adf6de59-0172ca35'
EMAIL_USE_TLS = True

# GrayLog config
# GRAYLOG_ENDPOINT: str = "http://127.0.0.1:12202/gelf"

# Activate Django-Heroku.
django_heroku.settings(locals())

