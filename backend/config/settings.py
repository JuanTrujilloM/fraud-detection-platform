"""Configuración de la plataforma OLTP. Todo lo que cambia por entorno viene de variables."""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _lista(nombre: str) -> list[str]:
    return [valor.strip() for valor in os.environ.get(nombre, '').split(',') if valor.strip()]


def _requerida(nombre: str, valor_debug: str) -> str:
    """Exige la variable fuera de DEBUG; en desarrollo usa un valor inofensivo."""
    valor = os.environ.get(nombre)
    if valor:
        return valor
    if DEBUG:
        return valor_debug
    raise ImproperlyConfigured(f'Falta la variable de entorno {nombre}')


DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() == 'true'
SECRET_KEY = _requerida('DJANGO_SECRET_KEY', 'solo-para-desarrollo-local')
ALLOWED_HOSTS = _lista('DJANGO_ALLOWED_HOSTS') or (['*'] if DEBUG else [])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'usuarios',
    'tarjetas',
    'autorizaciones',
    'alertas',
    'portal',
    'eventos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'coopandina'),
        'USER': os.environ.get('POSTGRES_USER', 'coopandina'),
        'PASSWORD': _requerida('POSTGRES_PASSWORD', 'coopandina'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
    }
}

AUTH_USER_MODEL = 'usuarios.Usuario'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'COERCE_DECIMAL_TO_STRING': False,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(hours=12),
    'UPDATE_LAST_LOGIN': True,
    'SIGNING_KEY': _requerida('JWT_SECRET_KEY', 'solo-para-desarrollo-local-jwt-32-bytes'),
}

# Autorizador
UMBRAL_RECHAZO_MODELO = float(os.environ.get('UMBRAL_RECHAZO_MODELO', '0.85'))
UMBRAL_ALERTA_MODELO = float(os.environ.get('UMBRAL_ALERTA_MODELO', '0.60'))
TIEMPO_LIMITE_MODELO_MS = int(os.environ.get('TIEMPO_LIMITE_MODELO_MS', '300'))
# Valor que devuelve obtener_probabilidad mientras no haya modelo entrenado.
MODELO_PROBABILIDAD_FIJA = float(os.environ.get('MODELO_PROBABILIDAD_FIJA', '0.02'))
# Llave del HMAC de los CVV. Va aparte de SECRET_KEY para poder rotar esa sin invalidar tarjetas.
CVV_HMAC_KEY = _requerida('CVV_HMAC_KEY', 'solo-para-desarrollo-local-cvv')

# Proxies de confianza delante de Gunicorn: 0 directo, 1 detrás de Vite.
NUM_PROXIES = int(os.environ.get('NUM_PROXIES', '0'))

# Log de eventos de negocio: el puente con la ingesta por streaming.
EVENTOS_LOG_PATH = Path(os.environ.get('EVENTOS_LOG_PATH', BASE_DIR / 'logs' / 'eventos.log'))
EVENTOS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'solo_mensaje': {'format': '%(message)s'},
        'tecnico': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'},
    },
    'handlers': {
        'consola': {'class': 'logging.StreamHandler', 'formatter': 'tecnico'},
        'eventos': {
            # No es seguro entre procesos: por eso Gunicorn corre con un worker y varios hilos.
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': EVENTOS_LOG_PATH,
            'when': 'midnight',
            'utc': True,
            'backupCount': 30,
            'encoding': 'utf-8',
            'delay': True,
            'formatter': 'solo_mensaje',
        },
    },
    'root': {'handlers': ['consola'], 'level': 'INFO'},
    'loggers': {
        'eventos': {'handlers': ['eventos'], 'level': 'INFO', 'propagate': False},
    },
}
