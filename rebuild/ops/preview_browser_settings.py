"""Settings only for the isolated private-preview browser regression harness."""
from quillmd.settings import *  # noqa: F403
import os
from pathlib import Path

if (not DATABASES['default']['NAME'].startswith('quillmd_preview_browser_')  # noqa: F405
        or DATABASES['default']['PORT'] != '55439'
        or DATABASES['default']['HOST'] != '127.0.0.1'
        or DATABASES['default']['USER'] != 'quillmd_ci'
        or os.getenv('QUILLMD_ENV_MANAGED') != '1'
        or os.getenv('QUILLMD_AI_MODE') != 'fixture'
        or os.getenv('QUILLMD_EMAIL_MODE') != 'file'):
    raise RuntimeError('Preview browser settings require the dedicated synthetic database and file mail backend.')
QUILLMD_PREVIEW_ORIGIN = 'https://app.quillmd.com:19443'
QUILLMD_APP_BASE_URL = QUILLMD_PREVIEW_ORIGIN
QUILLMD_PREVIEW_AUTH_ENABLED = True
ADMIN_SITE = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
CSRF_TRUSTED_ORIGINS = [QUILLMD_PREVIEW_ORIGIN]
STATIC_ROOT = Path(os.environ['QUILLMD_PREVIEW_BROWSER_STATE']) / 'staticfiles'
MEDIA_ROOT = Path(os.environ['QUILLMD_PREVIEW_BROWSER_STATE']) / 'files'
EMAIL_FILE_PATH = Path(os.environ['QUILLMD_PREVIEW_BROWSER_STATE']) / 'mail'
EMAIL_BACKEND = 'core.email_backend.PrivateFileEmailBackend'
QUILLMD_EMAIL_ALLOWED_RECIPIENTS = ''
RESEND_API_KEY = ''
STRIPE_SECRET_KEY = ''
STRIPE_WEBHOOK_SECRET = ''
AI_MODE = 'fixture'
