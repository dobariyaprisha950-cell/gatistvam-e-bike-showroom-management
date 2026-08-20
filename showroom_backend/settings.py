import os
import dj_database_url
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-local-development-only-change-me'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'yakuza-showroom-management.onrender.com',
]

render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'yakuza',
    'rest_framework',
    'rest_framework.authtoken',  # machine-to-machine auth for branch<->Super Admin API calls
]

# Previously unset, which meant DRF fell back to its own defaults
# (SessionAuthentication/BasicAuthentication + AllowAny). AllowAny meant any
# viewset that forgot to declare permission_classes (this happened -- see
# NotificationViewSet) was reachable without login. IsAuthenticated is now
# the floor for every viewset; TokenAuthentication is added alongside the
# existing session auth so a Super Admin instance can call a branch
# instance's API as a service account instead of a logged-in browser.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ==========================================================================
# BRANCH FEDERATION CONFIG (Super Admin <-> per-branch API, over VPN)
# ==========================================================================
# Each branch runs its own Django install + own local database (see
# DATABASES above -- DATABASE_URL is already per-instance via
# dj_database_url, so nothing changes there for a branch deployment).
#
# A Super Admin instance does NOT read branch data from a local DB. It
# reads a registry of branch API endpoints from environment variables and
# calls each branch's REST API (over the private VPN) using a per-branch
# token (a DRF authtoken issued to a dedicated service account on that
# branch's install). Nothing is hardcoded here -- unconfigured branches are
# simply absent from BRANCH_API_REGISTRY until their env vars are set.
#
# Expected env vars per branch (BRANCH_CODE matches Branch.branch_code):
#   BRANCH_API_URL_<CODE>    e.g. BRANCH_API_URL_JUNAGADH=https://10.20.0.11:8000
#   BRANCH_API_TOKEN_<CODE>  the DRF token for that branch's service account
IS_SUPER_ADMIN_CONSOLE = os.environ.get('IS_SUPER_ADMIN_CONSOLE', 'False').lower() == 'true'
BRANCH_CODE = os.environ.get('BRANCH_CODE', '').strip().upper()

def _build_branch_api_registry():
    registry = {}
    prefix = 'BRANCH_API_URL_'
    for key, url in os.environ.items():
        if not key.startswith(prefix) or not url:
            continue
        code = key[len(prefix):]
        token = os.environ.get(f'BRANCH_API_TOKEN_{code}')
        registry[code] = {'url': url.rstrip('/'), 'token': token}
    return registry

BRANCH_API_REGISTRY = _build_branch_api_registry()

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

ROOT_URLCONF = 'showroom_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'yakuza.context_processors.notification_context',
                'yakuza.context_processors.branch_context_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'showroom_backend.wsgi.application'


# Database
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        ssl_require=not DEBUG,
    )
}

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}