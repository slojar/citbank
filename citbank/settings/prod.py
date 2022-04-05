from pathlib import Path
from .base import *
from datetime import timedelta

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'cd72d3a96e01cbcc294c50f34efd7d9b9939f1e13f0729cd603fbfd45fd64674e1cf43c3a64ea8a6b6fd3a9fe3'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
print("----------------------- Running Production on Environment -------------------------------------")

ALLOWED_HOSTS = ["*"]

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# Simple JWT

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=60),
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer', 'Token',),
}

# CORS

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:80",
    "http://localhost",
]

CORS_ALLOW_ALL_ORIGINS = True
# CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
}