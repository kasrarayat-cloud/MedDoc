"""CPT Studio settings.

Every value that differs between environments comes from a ``CPT_STUDIO_*``
environment variable. Nothing here reads another application's environment
file: the deployment passes this service its own variables, and provider
credentials live in a separate protected file named by
``CPT_STUDIO_CORTI_CREDENTIALS_FILE``.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name, default=None, *, required=False):
    value = os.getenv(f'CPT_STUDIO_{name}', default)
    if required and not value:
        raise RuntimeError(f'CPT_STUDIO_{name} must be set.')
    return value


def _flag(name, default='0'):
    return _env(name, default) == '1'


# Deliberate release gate. Synthetic-only is a constant, never a setting:
# changing it requires a recorded owner decision and real processing controls.
SYNTHETIC_ONLY = True

SECRET_KEY = _env('SECRET_KEY', required=True)
DEBUG = False
ALLOWED_HOSTS = ['cpt.quillmd.com', 'localhost', '127.0.0.1', 'testserver']
CSRF_TRUSTED_ORIGINS = ['https://cpt.quillmd.com']
RELEASE_SHA = _env('RELEASE_SHA', 'development-unrecorded')

STATE_DIR = Path(_env('STATE_DIR', str(BASE_DIR / '.runtime')))
if not STATE_DIR.is_absolute():
    raise RuntimeError('CPT_STUDIO_STATE_DIR must be an absolute path.')
ORIGINALS_DIR = STATE_DIR / 'originals'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'studio',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'studio.access.SecurityHeadersMiddleware',
]
ROOT_URLCONF = 'cptstudio.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
    ]},
}]
WSGI_APPLICATION = 'cptstudio.wsgi.application'

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': _env('DB_NAME', 'cptstudio'),
    'USER': _env('DB_USER', 'cptstudio'),
    'PASSWORD': _env('DB_PASSWORD', ''),
    'HOST': _env('DB_HOST', '127.0.0.1'),
    'PORT': _env('DB_PORT', '55451'),
    'CONN_MAX_AGE': 60,
    # One test database per concurrent test run: two runs sharing a name
    # destroy each other's database.
    'TEST': {'NAME': f"test_cptstudio_{_env('TEST_DB_SUFFIX', 'default')}"},
}}

AUTH_USER_MODEL = 'studio.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]
LOGIN_URL = '/login/'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Uploads stream to a temporary file; the original store copies the bytes
# exactly once and never rewrites them.
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PASTE_CHARS = 400_000
# A document naming procedures more often than this is not read (the analyze stage fails with a plain message and
# nothing is sent): each mention is read in its list window, and "EUS, EUS, ..." overran the analyze stage from about
# 40,000 characters (round 7 declared:8, bounded:1, bounded:3). A real report names them a few dozen times.
MAX_SERVICE_MENTIONS = 1000
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 0
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700

SESSION_COOKIE_NAME = 'cptstudio_session'
CSRF_COOKIE_NAME = 'cptstudio_csrf'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it to send the X-CSRFToken header
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
HTTPS = _flag('HTTPS')
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
# Only behind the loopback nginx proxy, which overwrites this header.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if _flag('TRUST_PROXY') else None
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# Login throttling: attempts per (username, client) inside the window.
LOGIN_THROTTLE_ATTEMPTS = 8
LOGIN_THROTTLE_WINDOW_SECONDS = 15 * 60

# Provider adapters. 'disabled' sends nothing; 'replay' uses recorded
# responses and is labelled REPLAY everywhere; 'live' calls the provider.
PROVIDER_MODE = _env('PROVIDER_MODE', 'disabled')
if PROVIDER_MODE not in {'disabled', 'replay', 'live'}:
    raise RuntimeError('CPT_STUDIO_PROVIDER_MODE must be disabled, replay or live.')
CORTI_CREDENTIALS_FILE = _env('CORTI_CREDENTIALS_FILE', '')
REPLAY_DIR = _env('REPLAY_DIR', '')
# The recorded owner authority a live send is bound to (ruling file path or id).
AUTHORIZATION_REF = _env('AUTHORIZATION_REF', '')

# Bounded execution.
EXTRACTION_TIMEOUT_SECONDS = int(_env('EXTRACTION_TIMEOUT_SECONDS', '240'))
MAX_PDF_PAGES = int(_env('MAX_PDF_PAGES', '40'))
PROVIDER_CONNECT_TIMEOUT_SECONDS = 10
PROVIDER_READ_TIMEOUT_SECONDS = 120
PROVIDER_MAX_REQUEST_BYTES = 512_000
PROVIDER_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
# The assess stage routes the document again (validation's span readings read that routing's analysis) and then
# validates, so it has the analyze stage's time and memory and as much again for the validation: a document the analyze
# stage read within its limits is never sent and then left unassessed for repeating that work (round 7 bounded:1).
JOB_DEADLINE_SECONDS = {'extract': 300, 'analyze': 60, 'predict': 180, 'assess': 120, 'review2': 180}
# Routing and context extraction run in a forked child under these (studio/bounded.py): the stage's deadline
# above, this growth of address space past what the worker already uses, and a shorter wall clock when a
# member's context change runs the extraction inside a web request.
BOUNDED_MEMORY_BYTES = 512 * 1024 * 1024
ASSESS_MEMORY_BYTES = BOUNDED_MEMORY_BYTES + 256 * 1024 * 1024  # the assess child's: routing's, and validation's
CONTEXT_REQUEST_SECONDS = 15
STALE_RUNNING_SECONDS = 600

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    # Request logging can carry document titles in URLs; keep it at WARNING.
    'loggers': {'django.request': {'level': 'WARNING'}},
}
