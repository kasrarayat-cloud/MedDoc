"""HTTPS mount for the existing isolated Corti replay; no native settings change."""
from ops.corti_candidate_settings import *  # noqa: F403

PREFIX = '/synthetic/corti'
FORCE_SCRIPT_NAME = PREFIX
STATIC_URL = PREFIX + '/static/'
WHITENOISE_STATIC_PREFIX = '/static/'
ALLOWED_HOSTS = ['app.quillmd.com']
QUILLMD_APP_BASE_URL = 'https://app.quillmd.com' + PREFIX
QUILLMD_TRUST_PROXY = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_NAME = 'quillmd_corti_session'
CSRF_COOKIE_NAME = 'quillmd_corti_csrf'
SESSION_COOKIE_PATH = CSRF_COOKIE_PATH = PREFIX + '/'
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = None
SESSION_COOKIE_SAMESITE = CSRF_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_HTTPONLY = True
SECURE_SSL_REDIRECT = True
CSRF_TRUSTED_ORIGINS = []
CSRF_FAILURE_VIEW = 'core.corti_prefix.csrf_failure'
LOGIN_URL = PREFIX + '/login/'
LOGIN_REDIRECT_URL = PREFIX + '/'
# The default fallback message cookie is named globally; keep it in this
# candidate's independently keyed/path-scoped session instead.
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
MIDDLEWARE = ['core.corti_prefix.CortiPrefixMiddleware', *MIDDLEWARE]
