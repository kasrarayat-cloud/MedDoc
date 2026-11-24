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
# admin.quillmd.com serves the operator console alone (owner direction 2026-11-23, D396; studio.hosts chooses its urlconf)
ADMIN_HOST = 'admin.quillmd.com'
ALLOWED_HOSTS = ['cpt.quillmd.com', ADMIN_HOST, 'localhost', '127.0.0.1', 'testserver']
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
    'studio.hosts.HostUrlconfMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # release 1 (RELEASE-1-SPEC 3.2; B3, B4, B5, A2): the session policy, which reads the signed-in user
    'studio.sessions.SessionPolicyMiddleware',
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
# A password's minimum length (release 1, B4; OWNER DECISION D26: NIST SP 800-63B-4's minimum for a password used
# alone). The validators run where a password is set - the console, provisioning, the installer, the account page -
# never at sign-in, so an existing shorter password still signs in until its owner changes it.
PASSWORD_MIN_LENGTH = 15
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': PASSWORD_MIN_LENGTH}},
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

# Django's database store over the same django_session table, which also keeps which accounts each session names, so
# ending one account's sessions reads that account's own (refutation round 1 of release 1, avail-0; studio.session_store)
SESSION_ENGINE = 'studio.session_store'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it to send the X-CSRFToken header
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
HTTPS = _flag('HTTPS')
# B6: under HTTPS the __Host- prefix makes the browser refuse a cookie of the name that is not Secure, Path=/ and
# host-only, so a sibling quillmd.com site on the shared host cannot set one that shadows CPT Studio's. The prefix
# needs Secure, so without HTTPS (tests, the loopback port) the names stay as they were. Domain stays unset, the path '/'.
SESSION_COOKIE_NAME = '__Host-cptstudio_session' if HTTPS else 'cptstudio_session'
CSRF_COOKIE_NAME = '__Host-cptstudio_csrf' if HTTPS else 'cptstudio_csrf'
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
# Only behind the loopback nginx proxy, which overwrites this header.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if _flag('TRUST_PROXY') else None
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# --- Release 1: the security and HIPAA items (RELEASE-1-SPEC 3.2) -------------------------------------------------------
# Every policy value here is a constant of the release, like the figures above: changing one is a release, which keeps
# it reviewable. The owner decisions (RELEASE-1-SPEC section 8) stand at their recommended answers until the owner rules.

# B5, automatic sign-out (OWNER DECISION D1): a session's idle limit and its cap, by who holds it; the warning before the
# idle limit; and how often a session's last activity is written.
SESSION_IDLE_MEMBER_SECONDS = 15 * 60
SESSION_IDLE_OPERATOR_SECONDS = 10 * 60
SESSION_MAX_MEMBER_SECONDS = 8 * 60 * 60  # today's 8 hours (SESSION_COOKIE_AGE)
SESSION_MAX_OPERATOR_SECONDS = 8 * 60 * 60
SESSION_IDLE_WARNING_SECONDS = 2 * 60
SESSION_ACTIVITY_WRITE_SECONDS = 60
# Refutation round 1 (avail-0): the live sessions one account holds of each kind - signed in, a checked password waiting
# for its key at the admin door, a setup under way (studio.session_store). A new one beyond it ends that account's oldest
# of the same kind, so one account's own sign-ins cannot grow the session table without bound, and a pending sign-in -
# made with a password alone - never ends a signed-in session.
SESSION_LIVE_PER_ACCOUNT = 20

# B1, sign-in slows down instead of locking anyone out (OWNER DECISIONS D6, D23): the window; failures per (username,
# address) that refuse that pair; failures per username before its delay starts, the delay's base (doubled per further
# failure) and its ceiling; failed attempts per address (an IPv6 /64) that refuse the address; how long a device or an
# address that signed in before skips the delay. They replace the earlier LOGIN_THROTTLE_* lockout (removed in release 1:
# nothing reads it; an older revision reads its own settings).
SIGNIN_WINDOW_SECONDS = 15 * 60
SIGNIN_PAIR_LIMIT = 10
SIGNIN_USER_DELAY_AFTER = 5
SIGNIN_DELAY_BASE_SECONDS = 30
SIGNIN_DELAY_MAX_SECONDS = 15 * 60
SIGNIN_CLIENT_LIMIT = 50
KNOWN_DEVICE_DAYS = 90

# B4 (OWNER DECISION D31): how long a password staff set stays usable before its owner replaces it, counted from the
# must-change flag; after that it is refused exactly like a wrong password.
STAFF_PASSWORD_UNUSED_SECONDS = 72 * 60 * 60

# B2, the operator's second factor (OWNER DECISION D3): WebAuthn bound to the admin host exactly (never quillmd.com,
# which sibling sites share); how long a checked password waits for the key; how recent the key must be for an act that
# changes who can see what (the step-up); the attempts per window; how long a setup code lives; the recovery codes.
WEBAUTHN_RP_ID = ADMIN_HOST
WEBAUTHN_ORIGIN = 'https://' + ADMIN_HOST
WEBAUTHN_RP_NAME = 'CPT Studio console'
SECOND_FACTOR_PENDING_SECONDS = 5 * 60
SECOND_FACTOR_STEP_UP_SECONDS = 5 * 60
SECOND_FACTOR_ATTEMPTS = 5
ENROLMENT_CODE_SECONDS = 30 * 60
RECOVERY_CODE_COUNT = 10

# C1: a member's poll of a document writes at most one read record per session and document in this many seconds.
READ_AUDIT_DETAIL_DEDUPE_SECONDS = 60
# Refutation round 1 (avail-3): a member's list read that repeats one of the same session (and address, practice, count
# and filters) made within this many seconds is counted on that record (AccessRecordRepeat) instead of writing its own.
READ_AUDIT_LIST_REPEAT_SECONDS = 60
# C2 (OWNER DECISION D24): how long an operator's opening of one document's content lasts, in that session only.
CONTENT_GRANT_SECONDS = 15 * 60
# C5 and D2 (OWNER DECISION D8): (requests, per seconds) - report creations per member and per practice, uploads per
# member, bundles per member; over a limit the answer is 429. The largest bundle (D2) keeps every answer inside nginx's
# in-memory buffers (A3).
EXPORT_LIMIT_PER_MEMBER = (10, 10 * 60)
EXPORT_LIMIT_PER_WORKSPACE = (60, 60 * 60)
UPLOAD_LIMIT_PER_MEMBER = (30, 10 * 60)
BUNDLE_LIMIT_PER_MEMBER = (10, 10 * 60)
BUNDLE_MAX_BYTES = 24 * 1024 * 1024

# E3: the converter service's socket, which the installer mounts, and whether a Word conversion must go through it (a
# converter that cannot be reached then fails the document as busy; nothing is converted inside the worker).
CONVERTER_SOCKET = _env('CONVERTER_SOCKET', '')
CONVERTER_REQUIRED = _flag('CONVERTER_REQUIRED')

# F1 (OWNER DECISION D16): originals, converted PDFs and report PDFs sealed with their practice's own key - built, and
# off. Turning it on is a release, never an environment flip: a revision older than release 1 cannot read a sealed file,
# so it is turned on only where no switch-back to one can be needed (the new server). The key-encryption key is
# CPT_STUDIO_FILES_KEK, from the protected environment file FILES_KEK_FILE names or from the process environment, never
# from the database (studio.file_crypto).
FILES_ENCRYPTION = 'off'
FILES_KEK_FILE = _env('FILES_KEK_FILE', '')
# D5 (OWNER DECISION D18): the malware scan of uploads, built for release 1b, and clamd's socket when it runs.
MALWARE_SCAN = 'off'
CLAMD_SOCKET = _env('CLAMD_SOCKET', '')
for _switch, _state in (('FILES_ENCRYPTION', FILES_ENCRYPTION), ('MALWARE_SCAN', MALWARE_SCAN)):
    if _state not in {'off', 'on'}:
        raise RuntimeError(f'{_switch} must be off or on.')

# B7: /health/ answers a request that came through nginx with the first 16 hex characters of
# sha256(HEALTH_DIGEST_PREFIX + RELEASE_SHA) in place of the release.
HEALTH_DIGEST_PREFIX = 'cpt-studio-release:'

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
