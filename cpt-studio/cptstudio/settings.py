"""CPT Studio settings.

Every value that differs between environments comes from a ``CPT_STUDIO_*``
environment variable. Nothing here reads another application's environment
file: the deployment passes this service its own variables, and the coding
step's credentials live in a separate protected file named by
``CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE`` (mounted in the worker only).
"""
from decimal import Decimal, InvalidOperation
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
# The site's own security headers wrap WhiteNoise, so static files get them too (DECISIONS D368, round 3): above all the
# PDF library's module worker, which takes its policy from its own script's response, not from the page that starts it.
# The middleware leaves a static file's caching headers to WhiteNoise.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'studio.access.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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

# The live gate's recorded owner authority (ruling file path or id): a live coding send names it, and none is made
# without it (jobs._live_gate).
AUTHORIZATION_REF = _env('AUTHORIZATION_REF', '')
# The Anthropic credentials file (ANTHROPIC_API_KEY and an optional ANTHROPIC_WORKSPACE_ID, read strictly as data by
# studio.fable.credentials at send time; mounted in the worker only, since the web never sends).
ANTHROPIC_CREDENTIALS_FILE = _env('ANTHROPIC_CREDENTIALS_FILE', '')
# The coding step (studio/fable/; BUILD-SPEC 3 and 4): Claude Fable 5.2 reads the original document twice, as the reader
# and as the checker. CODING_MODE 'disabled' (the default) sends nothing; 'replay' reads recorded final messages from
# CODING_REPLAY_DIR by request sha256 and calls nothing; 'live' calls the Anthropic API with the key read at send time
# from ANTHROPIC_CREDENTIALS_FILE (above; mounted in the worker only). CODING_EFFORT is output_config.effort ('max', the
# owner's setting); CODING_READ_TIMEOUT_SECONDS bounds each wait for a byte of the stream (anthropic.Timeout's read).
CODING_MODE = _env('CODING_MODE', 'disabled')
if CODING_MODE not in {'disabled', 'replay', 'live'}:
    raise RuntimeError('CPT_STUDIO_CODING_MODE must be disabled, replay or live.')
CODING_REPLAY_DIR = _env('CODING_REPLAY_DIR', '')
CODING_EFFORT = _env('CODING_EFFORT', 'max')
if CODING_EFFORT not in {'low', 'medium', 'high', 'xhigh', 'max'}:
    raise RuntimeError('CPT_STUDIO_CODING_EFFORT must be low, medium, high, xhigh or max.')
_read_timeout = _env('CODING_READ_TIMEOUT_SECONDS', '900')
if not (_read_timeout.isascii() and _read_timeout.isdigit()) or int(_read_timeout) < 1:
    raise RuntimeError('CPT_STUDIO_CODING_READ_TIMEOUT_SECONDS must be a whole number of seconds, at least 1.')
CODING_READ_TIMEOUT_SECONDS = int(_read_timeout)
# The owner's two figures (class d), one default each here, which the installer gives every container: the most one
# document's revision may cost - every coding run already on it, priced from its usage (a run whose cost is not known
# counts at its reserved worst case), plus the next send's worst case (jobs.spent_usd, fable.pricing.worst_case_usd) -
# and the documents coded at once, which is both the worker's threads and its provider slots (jobs.work, _take_slot).
DOCUMENT_CEILING_USD = _env('DOCUMENT_CEILING_USD', '25')
try:
    _document_ceiling: Decimal | None = Decimal(DOCUMENT_CEILING_USD)
except InvalidOperation:
    _document_ceiling = None
if _document_ceiling is None or not _document_ceiling.is_finite() or _document_ceiling < 0:
    raise RuntimeError('CPT_STUDIO_DOCUMENT_CEILING_USD must be a non-negative amount of US dollars.')
_documents = _env('CONCURRENT_DOCUMENTS', '4')
if not (_documents.isascii() and _documents.isdigit()) or int(_documents) < 1:
    raise RuntimeError('CPT_STUDIO_CONCURRENT_DOCUMENTS must be a whole number of documents, at least 1.')
CONCURRENT_DOCUMENTS = int(_documents)
# A running job no worker thread runs is settled as dead after this long (jobs.mark_stale; a code job has its own
# threshold, jobs.CODE_STALE_SECONDS), and so are a send left 'sending' or 'reserved' and a round left queued or
# running by a stage that no longer runs.
STALE_RUNNING_SECONDS = 600

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    # Request logging can carry document titles in URLs; keep it at WARNING.
    'loggers': {'django.request': {'level': 'WARNING'}},
}
