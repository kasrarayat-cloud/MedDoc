"""The administrator surface behind a TLS-terminating proxy (admin.quillmd.com).

Reproduces the investigator's probe (scratchpad v1/accounts/admin_tls_probe.py, 2026-09-27): with
QUILLMD_ADMIN_SITE=1, QUILLMD_HTTPS=1 and QUILLMD_TRUST_PROXY=1, settings forced the proxy header off,
so a proxied HTTPS request looked like plain HTTP. SecurityMiddleware answered it with a 301 to the
same URL — forever — and an HTTPS form post failed CSRF's origin check with 403.

Settings are computed at import, so every case runs in a fresh interpreter. No database is used.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase

REBUILD = Path(__file__).resolve().parents[2]

PROBE = r'''
import json, os
import django
django.setup()
from django.conf import settings
from django.test import RequestFactory
from django.middleware.security import SecurityMiddleware
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.http import HttpResponse
host = os.environ['PROBE_HOST']
rf = RequestFactory()
get = rf.get('/console/', HTTP_HOST=host, HTTP_X_FORWARDED_PROTO='https')
redirect = SecurityMiddleware(lambda r: HttpResponse('ok')).process_request(get)
seed = rf.get('/', HTTP_HOST=host)
token = get_token(seed)
post = rf.post('/console/platform-costs/', {'csrfmiddlewaretoken': token}, HTTP_HOST=host,
               HTTP_X_FORWARDED_PROTO='https', HTTP_ORIGIN='https://' + host)
post.COOKIES[settings.CSRF_COOKIE_NAME] = seed.META['CSRF_COOKIE']
csrf = CsrfViewMiddleware(lambda r: HttpResponse('ok'))
csrf.process_request(post)
refused = csrf.process_view(post, lambda r: HttpResponse('ok'), (), {})
print(json.dumps({'is_secure': get.is_secure(),
                  'redirect': [redirect.status_code, redirect.url] if redirect else None,
                  'csrf': 'pass' if refused is None else refused.status_code,
                  'header': settings.SECURE_PROXY_SSL_HEADER}))
'''


def probe(admin, https, trust):
    host = 'admin.quillmd.com' if admin == '1' else 'app.quillmd.com'
    env = {'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_SECRET_KEY': 'synthetic-settings-check',
           'QUILLMD_DB_PASSWORD': 'unused-synthetic-check', 'DJANGO_SETTINGS_MODULE': 'quillmd.settings',
           'QUILLMD_ADMIN_SITE': admin, 'QUILLMD_HTTPS': https, 'QUILLMD_TRUST_PROXY': trust,
           'PROBE_HOST': host, 'PATH': os.environ.get('PATH', '')}
    result = subprocess.run([sys.executable, '-B', '-c', PROBE], cwd=REBUILD, env=env,
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise AssertionError(result.stderr[-2000:])
    return json.loads(result.stdout.strip().splitlines()[-1])


class AdminSurfaceBehindTlsProxy(SimpleTestCase):
    def test_admin_honours_the_proxy_header_when_served_over_https(self):
        """The investigator's failing case: now secure, no self-redirect, and the HTTPS post passes CSRF."""
        result = probe(admin='1', https='1', trust='1')
        self.assertEqual(result, {'is_secure': True, 'redirect': None, 'csrf': 'pass',
                                  'header': ['HTTP_X_FORWARDED_PROTO', 'https']})

    def test_doctor_surface_control_is_unchanged(self):
        self.assertEqual(probe(admin='0', https='1', trust='1'),
                         {'is_secure': True, 'redirect': None, 'csrf': 'pass',
                          'header': ['HTTP_X_FORWARDED_PROTO', 'https']})

    def test_admin_over_the_ssh_tunnel_still_ignores_the_header(self):
        """Today's deployment: plain HTTP to the loopback port, with TRUST_PROXY=1 in the shared environment
        file for the doctor's proxy. Nothing overwrites the header on that path, so it stays untrusted."""
        result = probe(admin='1', https='0', trust='1')
        self.assertIsNone(result['header'])
        self.assertFalse(result['is_secure'])
        self.assertIsNone(result['redirect'])

    def test_admin_without_proxy_trust_still_insists_on_https(self):
        """Without QUILLMD_TRUST_PROXY the header is never believed, so a proxied request is still plain
        HTTP to Django and is redirected: the setting, not the header, decides."""
        result = probe(admin='1', https='1', trust='0')
        self.assertIsNone(result['header'])
        self.assertFalse(result['is_secure'])
        self.assertEqual(result['redirect'], [301, 'https://admin.quillmd.com/console/'])
