import os
from django.core.wsgi import get_wsgi_application
from decouple import config

# Check If Environment is Production or Development

if config('env', '') == 'prod':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'citbank.settings.prod')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'citbank.settings.dev')


application = get_wsgi_application()
