"""Every access gate decides on PATH_INFO, the path Django resolves (refutation round 2, the R1 sibling).

request.path is SCRIPT_NAME + PATH_INFO, and SCRIPT_NAME is a client header gunicorn honours (the refuter's p2 probe).
A gate that reads request.path can therefore be shown one path while Django serves another:

  RestoreQuarantineMiddleware  a SAFE path or a /static/ prefix made of SCRIPT_NAME: SCRIPT_NAME '/login' + PATH_INFO '/'
                               is '/login/' (safe) while the dashboard is served; SCRIPT_NAME '/static' + '/api/patients/'
                               starts with '/static/' while the patient API answers — during a restore quarantine.
  PreviewAccessMiddleware      SCRIPT_NAME '/preview/sign-in' + PATH_INFO '/' is the sign-in page to the gate while the
                               application serves its dashboard — without a preview grant.

Each test asserts the gate holds for a SCRIPT_NAME-shifted request, with the unshifted request as its positive control
(the same gate, the same caller, the same resolved path).
"""
import uuid

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import User
from core.tests.test_preview_access import EDGE, SETTINGS as PREVIEW
from core.tests.test_security import SyntheticFixture

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
QUARANTINED = 'Restored target quarantined'


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class RestoreQuarantineHoldsWhateverTheScriptName(SyntheticFixture, TestCase):
    def setUp(self):
        self.user = self.make_scope('quarantine')[0]
        self.client = Client(raise_request_exception=False)
        self.client.force_login(self.user)

    def quarantine(self):
        return override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=str(uuid.uuid4()))

    def test_positive_control_the_quarantine_refuses_clinical_paths(self):
        with self.quarantine():
            for path in ('/', '/api/patients/', '/patients/'):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 503)
                    self.assertContains(response, QUARANTINED, status_code=503)
            self.assertEqual(self.client.get('/health/').status_code, 200)

    def test_a_script_name_that_spells_a_safe_or_static_path_does_not_lift_it(self):
        cases = [('/login', '/'), ('/health', '/'), ('/mfa', '/'), ('/static', '/api/patients/'),
                 ('/static', '/patients/'), ('/static/x', '/'), ('/preview/sign-in', '/')]
        with self.quarantine():
            for script, path in cases:
                with self.subTest(script=script, path=path):
                    response = self.client.get(path, SCRIPT_NAME=script)
                    self.assertEqual(response.wsgi_request.path, script + path)
                    self.assertEqual(response.status_code, 503)

    def test_positive_control_a_shifted_safe_path_is_still_safe(self):
        """Decided on PATH_INFO, a SCRIPT_NAME no longer refuses a path that is safe."""
        with self.quarantine():
            self.assertEqual(self.client.get('/health/', SCRIPT_NAME='/x').status_code, 200)


@override_settings(**PREVIEW)
class PreviewGateHoldsWhateverTheScriptName(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='preview-doctor', email='preview-doctor@synthetic.invalid',
                                             verified_at=timezone.now())

    def test_a_script_name_spelling_the_sign_in_page_does_not_pass_the_gate(self):
        for signed_in in (False, True):
            client = Client(raise_request_exception=False)
            if signed_in:
                client.force_login(self.user)
            for script in ('/preview/sign-in', '/preview/sign-out'):
                with self.subTest(signed_in=signed_in, script=script):
                    response = client.get('/', SCRIPT_NAME=script, **EDGE)
                    self.assertEqual(response.wsgi_request.path, script + '/')
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response['Location'].startswith('/preview/sign-in/?flow='), response['Location'])

    def test_positive_control_the_gate_lets_its_own_sign_in_page_through(self):
        self.assertEqual(Client().get('/preview/sign-in/', **EDGE).status_code, 200)
        response = Client().get('/', **EDGE)
        self.assertTrue(response['Location'].startswith('/preview/sign-in/?flow='))


class NoGateReadsRequestPath(TestCase):
    """A static census, so the next gate written against request.path is caught: the only remaining reads of
    request.path in application code are the places that build a location to RETURN to, never a decision."""

    ALLOWED = {('core/middleware.py', 'return redirect_to_login(request.path if request.method'),
               ('core/middleware.py', 'request.path is SCRIPT_NAME + PATH_INFO'),
               ('core/middleware.py', 'asked for, request.path, as before'),
               ('core/preview_logging.py', 'capability-bearing request.path')}

    def test_request_path_is_read_only_to_build_a_return_location(self):
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        found = set()
        for folder in ('core', 'quillmd', 'documents'):
            for path in sorted((root / folder).rglob('*.py')):
                if 'tests' in path.relative_to(root).parts or path.name.startswith('test_'):
                    continue
                for line in path.read_text().splitlines():
                    if re.search(r'request\.path\b(?!_info)', line):
                        relative = str(path.relative_to(root))
                        match = next((allowed for name, allowed in self.ALLOWED if name == relative and allowed in line),
                                     None)
                        found.add((relative, match or line.strip()))
        unexpected = sorted(item for item in found if item not in self.ALLOWED)
        self.assertEqual(unexpected, [])
        self.assertEqual(len(found), len(self.ALLOWED), 'a recorded exception no longer exists: update ALLOWED')
