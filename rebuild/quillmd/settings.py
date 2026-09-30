from pathlib import Path
import os
import json
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
from quillmd import application_profile as _profile
BASE_DIR = Path(__file__).resolve().parent.parent
# systemd reads the operator-owned EnvironmentFile before dropping to the
# dedicated identity. That identity deliberately cannot open the source file.
if os.getenv('QUILLMD_ENV_MANAGED') != '1':
    load_dotenv(BASE_DIR / '.env')
STATE_DIR = Path(os.getenv('QUILLMD_STATE_DIR', str(BASE_DIR / '.runtime')))
if not STATE_DIR.is_absolute():
    raise RuntimeError('Application state directory must be absolute.')
SECRET_KEY = os.environ['QUILLMD_SECRET_KEY']
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver', 'app.quillmd.com', 'admin.quillmd.com']
ADMIN_SITE = os.getenv('QUILLMD_ADMIN_SITE', '0') == '1'
# V1 application profile. Every default keeps the private synthetic system exactly as it was;
# an unrecognised value refuses instead of selecting a mode. See docs/rebuild/v1/application-settings.md.
try:
    QUILLMD_DATA_MODE=_profile.choice(os.environ,'QUILLMD_DATA_MODE',_profile.DATA_MODES,'synthetic')
    QUILLMD_REGISTRATION=_profile.choice(os.environ,'QUILLMD_REGISTRATION',_profile.REGISTRATION_MODES,'open')
    QUILLMD_STRIPE_MODE=_profile.choice(os.environ,'QUILLMD_STRIPE_MODE',_profile.STRIPE_MODES,'test')
    QUILLMD_MFA_REQUIRED_ALL=_profile.flag(os.environ,'QUILLMD_MFA_REQUIRED_ALL','0')
    QUILLMD_WELCOME_CREDIT=_profile.welcome_credit(os.environ)
    QUILLMD_DEEPGRAM_SMART_FORMAT=_profile.choice(os.environ,'QUILLMD_DEEPGRAM_SMART_FORMAT',_profile.BOOLEAN_WORDS,'false')
    # None: synthetic mode with the setting unset sends no mip_opt_out parameter, the request as before V1.
    QUILLMD_DEEPGRAM_MIP_OPT_OUT=_profile.deepgram_mip_opt_out(os.environ,QUILLMD_DATA_MODE)
except _profile.ProfileError as exc:
    raise ImproperlyConfigured(str(exc)) from None
# Deliberate release gate. 'real' is accepted only with the production-required settings below.
SYNTHETIC_ONLY = QUILLMD_DATA_MODE == 'synthetic'
RELEASE_SHA = os.getenv('QUILLMD_RELEASE_SHA', 'development-unrecorded')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','django_otp','django_otp.plugins.otp_totp','core']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','core.disposition.RestoreQuarantineMiddleware','core.preview_access.PreviewAccessMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django_otp.middleware.OTPMiddleware','django.contrib.messages.middleware.MessageMiddleware','core.middleware.AccessMiddleware']
ROOT_URLCONF = 'quillmd.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','core.context.common']}}]
WSGI_APPLICATION = 'quillmd.wsgi.application'
DATABASES = {'default':{'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('QUILLMD_DB_NAME','quillmd_fresh'),'USER':os.getenv('QUILLMD_DB_USER','quillmd_fresh'),'PASSWORD':os.environ['QUILLMD_DB_PASSWORD'],'HOST':os.getenv('QUILLMD_DB_HOST','127.0.0.1'),'PORT':os.getenv('QUILLMD_DB_PORT','55438'),'CONN_MAX_AGE':60}}
AUTH_USER_MODEL = 'core.User'
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
PASSWORD_HASHERS = ['django.contrib.auth.hashers.Argon2PasswordHasher','django.contrib.auth.hashers.PBKDF2PasswordHasher']
LANGUAGE_CODE='en-us'
TIME_ZONE='UTC'
USE_I18N=True
USE_TZ=True
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
STATICFILES_DIRS=[BASE_DIR/'static']
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'quillmd.static_storage.PublicCompressedManifestStaticFilesStorage','OPTIONS':{'file_permissions_mode':0o644,'directory_permissions_mode':0o755}}}
MEDIA_ROOT=STATE_DIR/'files'
FILE_UPLOAD_PERMISSIONS=0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS=0o700
DATA_UPLOAD_MAX_MEMORY_SIZE=20*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE=0
# Existing large drafts must remain reviewable if generation is switched off.
# Bound the whole review form (up to1500 mapped fields); body-size limits still apply.
DATA_UPLOAD_MAX_NUMBER_FIELDS=16000
SESSION_COOKIE_NAME='quillmd_admin_session' if ADMIN_SITE else 'quillmd_doctor_session'
CSRF_COOKIE_NAME='quillmd_admin_csrf' if ADMIN_SITE else 'quillmd_doctor_csrf'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Strict'
CSRF_COOKIE_SAMESITE='Strict'
SESSION_COOKIE_SECURE=os.getenv('QUILLMD_HTTPS','0')=='1'
CSRF_COOKIE_SECURE=SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT=SESSION_COOKIE_SECURE
# Only enable behind the approved loopback proxy, which overwrites this header.
# The administrator surface honours it only when it is also served over HTTPS: today that surface
# is reached by an SSH tunnel straight to its loopback port, where nothing overwrites the header,
# while the shared environment file sets QUILLMD_TRUST_PROXY=1 for the doctor's proxy. With
# QUILLMD_HTTPS=1 a tunnel cannot serve it at all (every request redirects to https), so the only
# working admin deployment is behind a TLS-terminating proxy, and ignoring that proxy's header is
# what made admin.quillmd.com redirect to itself and refuse HTTPS form posts.
QUILLMD_TRUST_PROXY=os.getenv('QUILLMD_TRUST_PROXY','0')=='1' and (not ADMIN_SITE or SESSION_COOKIE_SECURE)
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https') if QUILLMD_TRUST_PROXY else None
SESSION_COOKIE_AGE=1800
PASSWORD_RESET_TIMEOUT=1800
SESSION_SAVE_EVERY_REQUEST=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY='same-origin'
X_FRAME_OPTIONS='DENY'
LOGIN_URL='/login/'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
# Word contract for NEW template inspections: 'legacy' (v1/v2 tables, placeholders, tab lines) or 'v3' (every
# structure, clinician-reviewed mapping). Stored mappings always fill under the contract that made them.
QUILLMD_WORD_ENGINE=os.getenv('QUILLMD_WORD_ENGINE','legacy')
QUILLMD_LAYOUT_SOCKET=os.getenv('QUILLMD_LAYOUT_SOCKET','')
QUILLMD_LAYOUT_SERVICE_UID=os.getenv('QUILLMD_LAYOUT_SERVICE_UID','')
QUILLMD_MAPPING_ASSISTANCE=os.getenv('QUILLMD_MAPPING_ASSISTANCE','0')=='1'
# Separate admission: exposing offline review is never authority for provider spending.
QUILLMD_MAPPING_ASSISTANCE_LIVE=os.getenv('QUILLMD_MAPPING_ASSISTANCE_LIVE','0')=='1'
if QUILLMD_WORD_ENGINE not in ('legacy','v3'):
    raise ImproperlyConfigured("QUILLMD_WORD_ENGINE must be 'legacy' or 'v3'.")
QUILLMD_EMAIL_MODE=os.getenv('QUILLMD_EMAIL_MODE','file')
EMAIL_BACKEND='core.email_backend.ResendEmailBackend' if QUILLMD_EMAIL_MODE=='resend' else 'core.email_backend.PrivateFileEmailBackend'
EMAIL_FILE_PATH=STATE_DIR/'mail'
DEFAULT_FROM_EMAIL='QuillMD <no-reply@quillmd.com>'
QUILLMD_APP_BASE_URL=os.getenv('QUILLMD_APP_BASE_URL','http://localhost:9130')
QUILLMD_EMAIL_FROM=os.getenv('QUILLMD_EMAIL_FROM','')
QUILLMD_EMAIL_VERIFIED_DOMAIN=os.getenv('QUILLMD_EMAIL_VERIFIED_DOMAIN','')
QUILLMD_RESEND_ENV_FILE=os.getenv('QUILLMD_RESEND_ENV_FILE','')
QUILLMD_EMAIL_ALLOWED_RECIPIENTS=os.getenv('QUILLMD_EMAIL_ALLOWED_RECIPIENTS','')
QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME=os.getenv('QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME','')
QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD=os.getenv('QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD','')
QUILLMD_PREVIEW_AUTH_ENABLED=os.getenv('QUILLMD_PREVIEW_AUTH_ENABLED','0')=='1' and not ADMIN_SITE
QUILLMD_PREVIEW_ORIGIN='https://app.quillmd.com:9443'  # Fixed edge; isolated tests may override this setting.
CSRF_FAILURE_VIEW='core.preview_access.csrf_failure'
RESEND_API_KEY=os.getenv('RESEND_API_KEY','')
# API keys remain in the private environment; application logs omit payloads.
AI_MODE=os.getenv('QUILLMD_AI_MODE','fixture')
AI_PROVIDER=os.getenv('QUILLMD_AI_PROVIDER','anthropic')
AI_MODEL=os.getenv('QUILLMD_AI_MODEL','gpt-4.1-mini')
AI_INPUT_RATE=os.getenv('QUILLMD_AI_INPUT_RATE','')
AI_OUTPUT_RATE=os.getenv('QUILLMD_AI_OUTPUT_RATE','')
AI_CACHED_RATE=os.getenv('QUILLMD_AI_CACHED_RATE','')
# Request profile (core.generation.request_profile). Read ONLY when QUILLMD_AI_MODEL is claude-sonnet-5: the listed
# legacy Claude models (core.generation.LEGACY_CLAUDE_MODELS, claude-sonnet-4-6 included) keep the pre-profile request
# byte for byte and ignore the first two. With provider anthropic any other model id is refused before any request, and
# with provider openai any Claude model id is; with either, an id that is empty, padded or not a plain id is. NOTE: the
# defaults above (anthropic + gpt-4.1-mini) are a refused pair, so a live deployment must set QUILLMD_AI_MODEL; fixture
# mode sends nothing and is unaffected.
# Thinking 'disabled' | 'adaptive'; effort 'low' | 'medium' | 'high'. Unset inference geography sends no inference_geo.
AI_THINKING=os.getenv('QUILLMD_AI_THINKING','disabled')
AI_EFFORT=os.getenv('QUILLMD_AI_EFFORT','medium')
AI_INFERENCE_GEO=os.getenv('QUILLMD_AI_INFERENCE_GEO','')
# Narrative notes on the qualified WM IOV form (docs/rebuild/wm-narrative-design.md). OFF by default: a candidate, not
# enabled for doctors, and not live-verified. Shared generation/review changes have separate acceptance evidence;
# a disabled WM flag does not establish their behavior or discharge the required ordinary-note workflow.
WM_NARRATIVE=os.getenv('QUILLMD_WM_NARRATIVE','0')=='1'
# Prepared only: exact-model context qualification is still a release gate.
V3_HISTORY_CONTEXT=os.getenv('QUILLMD_V3_HISTORY_CONTEXT','0')=='1'
V3_GENERATION_BATCHES=os.getenv('QUILLMD_V3_GENERATION_BATCHES','0')=='1'
# The field-relations v2 contract is the ordinary-notes contract of a live claude-sonnet-5 deployment: unset, it is on
# exactly for live anthropic claude-sonnet-5 (application_profile.field_relations); set, it decides as before.
V3_FIELD_RELATIONS=_profile.field_relations(os.environ)
# Stored relation drafts are honoured unless the variable is set to something other than '1' (L3:R3-5).
V3_FIELD_RELATIONS_RECORDS=_profile.field_relations_records(os.environ)
# Retained provider-shaped narrative responses, keyed by the sha256 of the notes. Read ONLY in fixture mode, never live.
AI_REPLAY_DIR=os.getenv('QUILLMD_AI_REPLAY_DIR','')
STRIPE_SECRET_KEY=os.getenv('STRIPE_SECRET_KEY','')
STRIPE_WEBHOOK_SECRET=os.getenv('STRIPE_WEBHOOK_SECRET','')
STRIPE_LIVE_ENABLED=QUILLMD_STRIPE_MODE=='live'
# Who may change Department.organization_pays — i.e. which balance a department is billed to.
# OFF by default and deliberately: the instruction is that this belongs to an explicitly
# authorized platform owner / billing role, and this deployment has not established one.
# Granting it also requires the account to be a superuser; see core.admin_console.may_change_payer.
QUILLMD_PAYER_ROLE_GRANTED=os.getenv('QUILLMD_PAYER_ROLE_GRANTED','0')=='1'
CPT_LICENSE_ID=os.getenv('CPT_LICENSE_ID','')
CPT_LICENSE_EXPIRY=os.getenv('CPT_LICENSE_EXPIRY','')
LOGGING={'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},'root':{'handlers':['console'],'level':'WARNING'},'loggers':{'django.request':{'handlers':['console'],'level':'CRITICAL','propagate':False}}}

LOGGING['filters'] = {'preview_csrf_redaction': {'()': 'core.preview_logging.PreviewCSRFLogFilter'}}
LOGGING['loggers']['django.security.csrf'] = {'handlers': ['console'], 'level': 'WARNING', 'propagate': False, 'filters': ['preview_csrf_redaction']}

SECURE_HSTS_SECONDS=31536000 if SESSION_COOKIE_SECURE else 0

# Refuse to start rather than serve real patient data, or take live payments, half-configured.
# The messages name settings, never their values.
_refusals=[]
if QUILLMD_DATA_MODE=='real':
    _refusals+=_profile.real_mode_problems(os.environ,allowed_hosts=ALLOWED_HOSTS,session_cookie_secure=SESSION_COOKIE_SECURE,csrf_cookie_secure=CSRF_COOKIE_SECURE,email_mode=QUILLMD_EMAIL_MODE,app_base_url=QUILLMD_APP_BASE_URL,stripe_mode=QUILLMD_STRIPE_MODE,stripe_secret_key=STRIPE_SECRET_KEY)
if QUILLMD_STRIPE_MODE=='live':
    _refusals+=_profile.stripe_live_problems(os.environ,allowed_hosts=ALLOWED_HOSTS,secret_key=STRIPE_SECRET_KEY,webhook_secret=STRIPE_WEBHOOK_SECRET,app_base_url=QUILLMD_APP_BASE_URL)
if _refusals:
    raise ImproperlyConfigured('QuillMD refuses to start: '+'; '.join(_refusals)+'.')

# Preparation cannot release quarantine or grant destruction authority.
RESTORE_QUARANTINE = os.getenv('QUILLMD_RESTORE_QUARANTINE', '0') != '0'
RESTORE_INSTANCE_ID = os.getenv('QUILLMD_RESTORE_INSTANCE_ID', '')
# No keys, schedule or executable authority ship with the product. Tombstones
# remain enforced when execution is disabled; turning a feature off is no release.
DISPOSITION_ENABLED = os.getenv('QUILLMD_DISPOSITION_ENABLED', '0') == '1'
DISPOSITION_NAMESPACE = os.getenv('QUILLMD_DISPOSITION_NAMESPACE', '')
DISPOSITION_AUTHORITY_KEYS = json.loads(os.getenv('QUILLMD_DISPOSITION_AUTHORITY_KEYS', '{}'))
DISPOSITION_CHECKPOINT_KEYS = json.loads(os.getenv('QUILLMD_DISPOSITION_CHECKPOINT_KEYS', '{}'))
DISPOSITION_JOURNAL_KEYS = json.loads(os.getenv('QUILLMD_DISPOSITION_JOURNAL_KEYS', '{}'))
DISPOSITION_JOURNAL_KEY_ID = os.getenv('QUILLMD_DISPOSITION_JOURNAL_KEY_ID', '')
DISPOSITION_JOURNAL_PRIVATE_KEY = os.getenv('QUILLMD_DISPOSITION_JOURNAL_PRIVATE_KEY', '')
DISPOSITION_JOURNAL_PATH = os.getenv('QUILLMD_DISPOSITION_JOURNAL_PATH', '')
