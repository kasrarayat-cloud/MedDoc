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
# The harness's independent participants (HARNESS.md 8), each configured on its own: one unavailable blocks only its own
# stage. Their models and endpoints are code constants (studio/participants/), never settings.
ASTRA_MODE = _env('ASTRA_MODE', 'disabled')
FABLE_MODE = _env('FABLE_MODE', 'disabled')
for _name, _mode in (('ASTRA', ASTRA_MODE), ('FABLE', FABLE_MODE)):
    if _mode not in {'disabled', 'replay', 'live'}:
        raise RuntimeError(f'CPT_STUDIO_{_name}_MODE must be disabled, replay or live.')
OPENAI_CREDENTIALS_FILE = _env('OPENAI_CREDENTIALS_FILE', '')
ANTHROPIC_CREDENTIALS_FILE = _env('ANTHROPIC_CREDENTIALS_FILE', '')
PARTICIPANT_REPLAY_DIR = _env('PARTICIPANT_REPLAY_DIR', '')
# The interpreter (studio/interpretation/), configured on its own: 'disabled' sends nothing and pauses both reading
# stages (FINAL 11.2); 'replay' reads recorded answers by request sha256 and is labelled REPLAY; 'live' calls the
# provider. Since DECISIONS D275 the interpreter is Claude Fable 5.2 (docs/gemini-migration/AMENDMENT-2.md 1.11): live,
# it reads CPT Studio's existing Anthropic credential, ANTHROPIC_CREDENTIALS_FILE above (ANTHROPIC_API_KEY and an
# optional ANTHROPIC_WORKSPACE_ID, parsed strictly as data by the participants' credentials rules; the Fable
# participant's file, mounted in the worker only, since the web never sends: D14), and in replay it reads
# GEMINI_REPLAY_DIR/anthropic/, whose gemini/ folder keeps Gemini's recordings. The mode and replay settings keep their
# historical names: they set the interpreter whatever its provider. GEMINI_CREDENTIALS_FILE (GEMINI_API_KEY only) is
# read by the dormant Gemini adapter alone (studio/interpretation/adapter.py), never on the interpreter's path. The
# models and endpoints are code constants (fable_adapter.py; adapter.py), never settings.
GEMINI_MODE = _env('GEMINI_MODE', 'disabled')
if GEMINI_MODE not in {'disabled', 'replay', 'live'}:
    raise RuntimeError('CPT_STUDIO_GEMINI_MODE must be disabled, replay or live.')
GEMINI_CREDENTIALS_FILE = _env('GEMINI_CREDENTIALS_FILE', '')
GEMINI_REPLAY_DIR = _env('GEMINI_REPLAY_DIR', '')
# Release scope after refutation round 3 (HARNESS.md 12.10, the session's D7): this release offers no reviewer
# confirmation of a participant's located passage. A code-level literal, deliberately never read from the environment or
# an installer file, so no variable, file or member action turns it on; only a test's override_settings does, for the
# dormant confirmation path's own tests (studio.review.confirmations_offered reads it, and only the literal True is on).
STUDIO_OFFER_CONFIRMATIONS = False

# Bounded execution.
EXTRACTION_TIMEOUT_SECONDS = int(_env('EXTRACTION_TIMEOUT_SECONDS', '240'))
MAX_PDF_PAGES = int(_env('MAX_PDF_PAGES', '40'))
PROVIDER_CONNECT_TIMEOUT_SECONDS = 10
PROVIDER_READ_TIMEOUT_SECONDS = 120
PROVIDER_MAX_REQUEST_BYTES = 512_000
PROVIDER_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
# A participant reads the whole document and writes a structured reading, so it is given longer than Corti; the send
# deadline stays below STALE_RUNNING_SECONDS and the worker's stop timeout (ops/install.py) stays above it. A request
# may carry a PDF original (base64) beside the text: at most the 15 MiB upload limit, so 24 MiB bounds the body.
PARTICIPANT_CONNECT_TIMEOUT_SECONDS = 10
PARTICIPANT_READ_TIMEOUT_SECONDS = 300
PARTICIPANT_SEND_DEADLINE_SECONDS = 330
PARTICIPANT_MAX_REQUEST_BYTES = 24 * 1024 * 1024
PARTICIPANT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
# harness@2 (HARNESS.md 11.2): a participant phase may call CPT Studio's reference tools, so one run is a loop of at
# most PARTICIPANT_MAX_EXCHANGES HTTP exchanges, each read within PARTICIPANT_EXCHANGE_READ_TIMEOUT_SECONDS, the whole
# loop within PARTICIPANT_LOOP_DEADLINE_SECONDS - below STALE_RUNNING_SECONDS, so a live loop is never swept as dead.
PARTICIPANT_MAX_EXCHANGES = 4
PARTICIPANT_EXCHANGE_READ_TIMEOUT_SECONDS = 240
PARTICIPANT_LOOP_DEADLINE_SECONDS = 540
PARTICIPANT_MAX_TOOL_RESULT_BYTES = 256 * 1024  # one tool result, as returned to the participant
# The interpreter's one exchange per pass (D12): pass 1, the interpretation, and pass 2, the appraisal (design v2's
# second call, docs/gemini-migration/FINAL-V2.md 7.4), each a stream from Claude Fable 5.2 (DECISIONS D275), connected
# as the participants' and timed by these, which no caller's deadline stretches (AMENDMENT-2 1.12; D289's G2-01). The
# send deadline is fable_adapter.MAX_TOKENS - 128,000 output tokens, thinking included - at 100 tokens per second, 13.5%
# below the slowest measured rate (115.6), plus 40 s for the connection, the prefill and the stream's tail: 1,320 s. An
# answer cut off at MAX_TOKENS inside it is TOO_LONG; a stream the deadline cuts before Anthropic ends it is UNKNOWN,
# its bytes kept and no usage recorded (a reconcile, and an encounter-wide block until then). The read timeout bounds
# each wait for a byte of the stream and never cuts before the deadline: up to 40,743 thinking tokens were measured
# before the first text, and no gap between events has been measured yet. Each pass's stage (JOB_DEADLINE_SECONDS below)
# covers its send, the 15 s kept for recording its outcome (jobs.LOOP_RECORDING_SECONDS) and 45 s of the stage's own
# work, and ends before its stale-stage threshold (STALE_RUNNING_SECONDS_BY_KIND below). A recorded send whose output
# rate falls below 110 tokens per second re-derives the deadline as 128,000 tokens at 80% of that rate plus 40 s, with
# every bound that follows it. D49's 480 s read and 510 s deadline stay only as the dormant Gemini adapter's own module
# constants (studio/interpretation/adapter.py), which send nothing on the interpreter's path.
INTERPRETER_SEND_DEADLINE_SECONDS = 1320  # AMENDMENT-2 1.12
INTERPRETER_READ_TIMEOUT_SECONDS = 1320
APPRAISER_SEND_DEADLINE_SECONDS = 1320  # AMENDMENT-2 1.12, as pass 1's
APPRAISER_READ_TIMEOUT_SECONDS = 1320
# The most bytes one interpreter response may carry (AMENDMENT-2 1.12): the raw stream holds one JSON event per delta,
# so it is larger than its answer, and its bytes per output token are unmeasured; a 128,000-token stream above this at
# the measured rate raises the cap before the next send.
INTERPRETER_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
# The size bound (D4, FINAL C9 as DECISIONS D25 sets it from the S16 measurement): a revision longer than this, or with
# more pages, is not sent to the interpreter, and its stage says so plainly. Measured on the 179 FRESH answers of
# 2026-11-10: output tokens = 2,173 + 1.081 x input characters (residual p99 3,593); the 14 runs at 19,398-19,460
# characters gave 21,201-25,036 tokens, at most 76% of the first build's maxOutputTokens (32,768). 20,000 characters is
# the edge of the measured range, where the fit plus the p99 residual predicts 27,378 tokens (84%); it refuses none of
# the 86 live texts (the longest 19,398). An answer cut off at the limit anyway is refused as too long (C5). The pages
# equal MAX_PDF_PAGES' default. DECISIONS D278 keeps both for Claude Fable 5.2, whose output maximum
# (fable_adapter.MAX_TOKENS) and per-request claim bound (claims.CLAIM_BOUND_V3) are sized for them.
INTERPRET_MAX_CHARS = 20_000
INTERPRET_MAX_PAGES = 40
# The assess stage routes the document again (validation's span readings read that routing's analysis) and then
# validates, so it has the analyze stage's time and memory and as much again for the validation: a document the analyze
# stage read within its limits is never sent and then left unassessed for repeating that work (round 7 bounded:1). A
# participant's stage - its first reading's or its peer review's - is one tool loop (HARNESS.md 12.1): its deadline
# covers the loop's 540 s (PARTICIPANT_LOOP_DEADLINE_SECONDS) and the 15 s kept for recording its outcome
# (jobs.LOOP_RECORDING_SECONDS), with 25 s for the stage's own work before the loop - a stage that has used more
# reserves and sends nothing and is queued again (jobs._check_loop_time) - and it ends 20 s before STALE_RUNNING_SECONDS
# (600), where the stale-stage sweep takes a stage for dead, so a live stage is never swept. The worker's stop timeout
# (ops/install.py, 600 s) outlasts it. The interpret and appraise stages (the interpreter's two passes, AMENDMENT-2
# 1.12) have 1,380 s each: the 1,320 s send, the 15 s recording and 45 s of the stage's own work. They end 60 s before
# their own stale threshold (STALE_RUNNING_SECONDS_BY_KIND below), and the worker's stop timeout (ops/install.py
# STOP_SECONDS['worker'], 1,500 s by 1.12) outlasts them, so a deploy lets a reading finish.
JOB_DEADLINE_SECONDS = {'extract': 300, 'analyze': 60, 'predict': 180, 'assess': 120, 'review2': 180,
                        'astra': 580, 'fable': 580, 'astra_peer': 580, 'fable_peer': 580, 'interpret': 1380,
                        'appraise': 1380}
# Routing and context extraction run in a forked child under these (studio/bounded.py): the stage's deadline
# above, this growth of address space past what the worker already uses, and a shorter wall clock when a
# member's context change runs the extraction inside a web request.
BOUNDED_MEMORY_BYTES = 512 * 1024 * 1024
ASSESS_MEMORY_BYTES = BOUNDED_MEMORY_BYTES + 256 * 1024 * 1024  # the assess child's: routing's, and validation's
CONTEXT_REQUEST_SECONDS = 15
STALE_RUNNING_SECONDS = 600
# The stale-stage threshold of the interpreter's two reading stages (AMENDMENT-2 1.12 [R:connector-CONN-7]), above their
# 1,380 s stage deadline; every other kind keeps STALE_RUNNING_SECONDS. Read per kind by jobs.mark_stale's periodic
# sweep and by jobs._check_loop_time, whose budget would otherwise stop at 600 s and queue every reading stage again
# before its 1,320 s send; the worker's first sweep at its start settles every running stage whatever its age, since at
# most one worker runs.
STALE_RUNNING_SECONDS_BY_KIND = {'interpret': 1440, 'appraise': 1440}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    # Request logging can carry document titles in URLs; keep it at WARNING.
    'loggers': {'django.request': {'level': 'WARNING'}},
}
