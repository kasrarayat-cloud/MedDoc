"""Explicit isolated replay installation; never reads the served .env or secrets."""
from quillmd.settings import *  # noqa: F403
import json

if (not DATABASES['default']['NAME'].startswith('test_')
        or DATABASES['default']['HOST'] != '127.0.0.1'
        or DATABASES['default']['PORT'] != '55449'
        or DATABASES['default']['USER'] != 'quillmd_corti_candidate'
        or os.getenv('QUILLMD_ENV_MANAGED') != '1'
        or AI_MODE != 'fixture' or QUILLMD_EMAIL_MODE != 'file'):
    raise RuntimeError('Corti candidate requires its isolated synthetic database and fixture environment.')
CODING_PROVIDER = os.getenv('QUILLMD_CODING_PROVIDER', 'corti')
CORTI_CODING_MODE = 'replay'
CODING_ALLOW_TEST_FIXTURES = True
fixture = BASE_DIR / 'core/tests/fixtures/corti'
CORTI_REPLAY_FIXTURE = {
    'request': json.loads((fixture / 'request.json').read_text()),
    'response_raw': (fixture / 'response.raw.json').read_text(),
    'response_sha256': '560b4c979bf734a3b6ad6cf2aafaeadfc67226e3c5463da0959bd80181e5dc7f',
    'original_verdict': 'FAIL_RESPONSE_QUALITY_WITH_SELECTED_CODES_PASS',
}
STATIC_ROOT = STATE_DIR / 'staticfiles'
QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED = True
QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED = True
CORTI_CREDENTIALS_FILE = ''
RESEND_API_KEY = STRIPE_SECRET_KEY = STRIPE_WEBHOOK_SECRET = ''
CPT_ENTITLEMENT_MANIFEST = str(STATE_DIR / 'unavailable-cpt/entitlement.json')
