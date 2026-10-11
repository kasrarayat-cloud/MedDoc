from pathlib import Path
import os
from dotenv import load_dotenv
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
SYNTHETIC_ONLY = True  # Deliberate release gate; requires verified processing controls to change.
RELEASE_SHA = os.getenv('QUILLMD_RELEASE_SHA', 'development-unrecorded')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','django_otp','django_otp.plugins.otp_totp','core']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','core.preview_access.AccountOriginMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django_otp.middleware.OTPMiddleware','django.contrib.messages.middleware.MessageMiddleware','core.middleware.AccessMiddleware']
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
DATA_UPLOAD_MAX_NUMBER_FIELDS=3000
SESSION_COOKIE_NAME='quillmd_admin_session' if ADMIN_SITE else 'quillmd_doctor_session'
CSRF_COOKIE_NAME='quillmd_admin_csrf' if ADMIN_SITE else 'quillmd_doctor_csrf'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Strict'
CSRF_COOKIE_SAMESITE='Strict'
SESSION_COOKIE_SECURE=os.getenv('QUILLMD_HTTPS','0')=='1'
CSRF_COOKIE_SECURE=SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT=SESSION_COOKIE_SECURE
# Only enable behind the approved loopback proxy, which overwrites this header.
QUILLMD_TRUST_PROXY=os.getenv('QUILLMD_TRUST_PROXY','0')=='1'
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https') if QUILLMD_TRUST_PROXY and not ADMIN_SITE else None
SESSION_COOKIE_AGE=1800
PASSWORD_RESET_TIMEOUT=1800
SESSION_SAVE_EVERY_REQUEST=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY='same-origin'
X_FRAME_OPTIONS='DENY'
LOGIN_URL='/login/'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
QUILLMD_EMAIL_MODE=os.getenv('QUILLMD_EMAIL_MODE','file')
EMAIL_BACKEND='core.email_backend.ResendEmailBackend' if QUILLMD_EMAIL_MODE=='resend' else 'core.email_backend.PrivateFileEmailBackend'
EMAIL_FILE_PATH=STATE_DIR/'mail'
DEFAULT_FROM_EMAIL='QuillMD <no-reply@quillmd.com>'
QUILLMD_APP_BASE_URL=os.getenv('QUILLMD_APP_BASE_URL','http://localhost:9130')
QUILLMD_EMAIL_FROM=os.getenv('QUILLMD_EMAIL_FROM','')
QUILLMD_EMAIL_VERIFIED_DOMAIN=os.getenv('QUILLMD_EMAIL_VERIFIED_DOMAIN','')
QUILLMD_RESEND_ENV_FILE=os.getenv('QUILLMD_RESEND_ENV_FILE','')
QUILLMD_EMAIL_ALLOWED_RECIPIENTS=os.getenv('QUILLMD_EMAIL_ALLOWED_RECIPIENTS','')
QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED=os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED','0')=='1'
QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED=os.getenv('QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED','0')=='1'
CSRF_FAILURE_VIEW='core.preview_access.csrf_failure'
RESEND_API_KEY=os.getenv('RESEND_API_KEY','')
# API keys remain in the private environment; application logs omit payloads.
AI_MODE=os.getenv('QUILLMD_AI_MODE','fixture')
AI_PROVIDER=os.getenv('QUILLMD_AI_PROVIDER','anthropic')
AI_MODEL=os.getenv('QUILLMD_AI_MODEL','gpt-4.1-mini')
AI_INPUT_RATE=os.getenv('QUILLMD_AI_INPUT_RATE','')
AI_OUTPUT_RATE=os.getenv('QUILLMD_AI_OUTPUT_RATE','')
AI_CACHED_RATE=os.getenv('QUILLMD_AI_CACHED_RATE','')
WORD_PREPARATION_ENABLED=os.getenv('QUILLMD_WORD_PREPARATION_ENABLED','0')=='1'
# Purposeful follow-up SHA3f1f99421f07c72370a030a57174d5f5c9194ac6b3b8b7292e42a7bb4b3a3895.
# Includes the retained first unknown request; no old attempt is reset or replayed.
# Exact WM output follow-up SHA812817c06f8b5d686e4aa93a1662409e7d48d56d08870659a3d0d9851b4b5add.
# The eighth attempt/final two sends belong only to the pinned WM original.
WORD_PREPARATION_MAX_RUNS=8
WORD_PREPARATION_MAX_FORMS=6
WORD_PREPARATION_MAX_SENDS=14
# Reserve $0.40 of the $2 purposeful pilot for its two note requests and one ASR.
WORD_PREPARATION_BUDGET_USD='1.60'
# A separately recorded finite delivery campaign. Empty defaults cannot reopen
# the closed pilot; exact scope and actor supplement are checked in code/SQL.
WORD_PREPARATION_CAMPAIGN=os.getenv('QUILLMD_WORD_PREPARATION_CAMPAIGN','')
WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256=os.getenv('QUILLMD_WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256','')
# Explicit prospective authority; empty settings preserve every historical finite gate.
TESTING_AUTHORITY_MODE=os.getenv('QUILLMD_TESTING_AUTHORITY_MODE','')
TESTING_AUTHORITY_ID=os.getenv('QUILLMD_TESTING_AUTHORITY_ID','')
TESTING_AUTHORITY_SHA256=os.getenv('QUILLMD_TESTING_AUTHORITY_SHA256','')
STRIPE_SECRET_KEY=os.getenv('STRIPE_SECRET_KEY','')
STRIPE_WEBHOOK_SECRET=os.getenv('STRIPE_WEBHOOK_SECRET','')
STRIPE_LIVE_ENABLED=False
# Who may change Department.organization_pays — i.e. which balance a department is billed to.
# OFF by default and deliberately: the instruction is that this belongs to an explicitly
# authorized platform owner / billing role, and this deployment has not established one.
# Granting it also requires the account to be a superuser; see core.admin_console.may_change_payer.
QUILLMD_PAYER_ROLE_GRANTED=os.getenv('QUILLMD_PAYER_ROLE_GRANTED','0')=='1'
CPT_LICENSE_ID=os.getenv('CPT_LICENSE_ID','')
CPT_LICENSE_EXPIRY=os.getenv('CPT_LICENSE_EXPIRY','')
LOGGING={'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},'root':{'handlers':['console'],'level':'WARNING'},'loggers':{'django.request':{'handlers':['console'],'level':'CRITICAL','propagate':False}}}

LOGGING['filters'] = {'account_csrf_redaction': {'()': 'core.preview_logging.AccountCSRFLogFilter'}}
LOGGING['loggers']['django.security.csrf'] = {'handlers': ['console'], 'level': 'WARNING', 'propagate': False, 'filters': ['account_csrf_redaction']}

SECURE_HSTS_SECONDS=31536000 if SESSION_COOKIE_SECURE else 0
