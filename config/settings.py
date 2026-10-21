import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from .environment import database_config
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
VERCEL = os.getenv('VERCEL') == '1'
if VERCEL and DEBUG:
    raise ImproperlyConfigured('Vercel requiere DEBUG=False.')
SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'solo-desarrollo-local-no-usar-en-produccion'
    else:
        raise ImproperlyConfigured('Configure SECRET_KEY o DEBUG=True para desarrollo local.')
ALLOWED_HOSTS = [s.strip() for s in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if s.strip()]
CSRF_TRUSTED_ORIGINS = [s.strip() for s in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if s.strip()]
if not DEBUG:
    if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(('django-insecure-', 'solo-desarrollo-')):
        raise ImproperlyConfigured('Configure una SECRET_KEY aleatoria de producción de al menos 50 caracteres.')
    if not os.getenv('ALLOWED_HOSTS') or not ALLOWED_HOSTS or any('*' in h or h.startswith('.') for h in ALLOWED_HOSTS):
        raise ImproperlyConfigured('Configure ALLOWED_HOSTS con dominios explícitos, sin comodines.')
    if not CSRF_TRUSTED_ORIGINS or any(not s.startswith('https://') or '*' in s for s in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured('Configure CSRF_TRUSTED_ORIGINS con orígenes HTTPS explícitos.')
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','control']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
MIDDLEWARE.insert(2, 'control.middleware.LimitesPlataformaMiddleware')
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': database_config(BASE_DIR, DEBUG)}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.' + n} for n in ['UserAttributeSimilarityValidator','MinimumLengthValidator','CommonPasswordValidator','NumericPasswordValidator']]
LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True
DATE_FORMAT = 'd/m/Y'
TIME_FORMAT = 'H:i'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG else
                  'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = 'login'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 3600 if not DEBUG else 0
SECURE_REFERRER_POLICY = 'same-origin'
# Confiar en el encabezado de protocolo solo dentro del proxy de Vercel.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if VERCEL else None
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# 5000 decisiones de fila, 5 campos cada una; carga XLSX limitada a 10 MB.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 30050
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Vercel admite 4,5 MB por solicitud/respuesta; dejar margen multipart.
XLSX_UPLOAD_MAX_BYTES = 4_000_000 if VERCEL else 10 * 1024 * 1024
HTTP_REQUEST_MAX_BYTES = 4_250_000 if VERCEL else None
HTTP_RESPONSE_MAX_BYTES = 4_000_000 if VERCEL else None
