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
from pathlib import Path

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


#: Attributes only an HTTP request carries: a parameter (or a name assigned from one) that is used with any of them, or
#: is named `request`, is treated as a request.
REQUEST_ATTRIBUTES = {'META', 'method', 'user', 'GET', 'POST', 'COOKIES', 'FILES', 'session', 'headers', 'path_info',
                      'get_host', 'is_secure', 'resolver_match', 'urlconf', 'body', 'content_type'}
#: What carries SCRIPT_NAME: the attribute and the calls built on it.
FULL_PATH = {'path'}
FULL_PATH_CALLS = {'get_full_path', 'build_absolute_uri'}


def full_path_reads(source):
    """[(function qualname, line, what)] for every read of a request's full path (request.path, get_full_path(),
    build_absolute_uri()) in `source`, whatever the request variable is called: a function's parameters and the names
    assigned from them are requests when the function uses them as one (REQUEST_ATTRIBUTES) or names them `request`."""
    import ast
    found = []

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                name = getattr(child, 'name', '<lambda>')
                examine(child, scope + [name])
                visit(child, scope + [name])
            elif isinstance(child, ast.ClassDef):
                visit(child, scope + [child.name])
            else:
                visit(child, scope)

    def examine(function, scope):
        # (never `self`: a handler object is not a Django request, e.g. ops/preview_browser_tls.py's
        # BaseHTTPRequestHandler, whose .path is the raw request target)
        names = {arg.arg for arg in function.args.args + function.args.kwonlyargs + function.args.posonlyargs} - {'self', 'cls'}
        body = list(ast.walk(function))
        requests = {name for name in names if name == 'request'}
        for node in body:
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.attr in REQUEST_ATTRIBUTES and node.value.id in names):
                requests.add(node.value.id)
        changed = True
        while changed:   # aliases, both ways: `request = rq` makes rq a request, and `rq = request` the same
            changed = False
            for node in body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
                    targets = {target.id for target in node.targets if isinstance(target, ast.Name)}
                    group = targets | {node.value.id}
                    if (group & requests or 'request' in targets) and not group <= requests:
                        requests |= group
                        changed = True
        for node in body:
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in requests:
                if node.attr in FULL_PATH:
                    found.append(('.'.join(scope), node.lineno, node.value.id + '.' + node.attr))
                elif node.attr in FULL_PATH_CALLS:
                    found.append(('.'.join(scope), node.lineno, node.value.id + '.' + node.attr + '()'))
    visit(ast.parse(source), [])
    return found


class NoGateReadsTheFullPath(TestCase):
    """A census of every application module in rebuild/ (round-3 R3-5: the line census caught only the literal text
    `request.path` in three folders; get_full_path() and a request variable called `rq` reopened the SCRIPT_NAME bypass
    and passed it). Parsed, not grepped: every read of a request's full path, under any name, is listed, and only the
    reads that build a location to RETURN to are allowed. The behaviour tests above are the gates' own proof; this
    catches the next gate written against the full path.

    Templates read request.path only for a sign-in link's `next` (register.html, clinic_invite.html)."""

    #: Each allowed read and HOW MANY times it occurs: a second read in an allowed function is a new read (the
    #: preview gate's own sign-in check spelled get_full_path() passed a set-based census beside the allowed one).
    ALLOWED = {
        # where the sign-in redirect returns the browser to
        ('core/middleware.py', 'AccessMiddleware.__call__', 'request.path'): 1,
        # the page the private-preview sign-in resumes after the gate (a destination, checked by safe_destination)
        ('core/preview_access.py', 'PreviewAccessMiddleware.__call__', 'request.get_full_path()'): 1,
    }

    def census(self):
        from collections import Counter
        root = Path(__file__).resolve().parents[2]
        skip = {'.venv', 'node_modules', '.runtime', 'staticfiles', 'tests', '__pycache__'}
        found = Counter()
        scanned = 0
        for path in sorted(root.rglob('*.py')):
            relative = path.relative_to(root)
            if skip & set(relative.parts) or path.name.startswith('test_'):
                continue
            scanned += 1
            for scope, _, what in full_path_reads(path.read_text()):
                found[(str(relative), scope, what)] += 1
        return found, scanned

    def test_only_return_locations_read_the_full_path(self):
        found, scanned = self.census()
        self.assertGreater(scanned, 100, 'the census scanned almost nothing')
        self.assertEqual(dict(found), self.ALLOWED)

    def test_positive_control_the_census_sees_the_shapes_round_3_used(self):
        """m9 and m10 of round 3, and two more spellings, each found in a synthetic middleware."""
        shapes = {
            'm9': "class M:\n    def __call__(self, request):\n        path = request.get_full_path().split('?')[0]\n"
                  "        return path in SAFE and request.user\n",
            'm10': "class M:\n    def __call__(self, rq):\n        request = rq\n        path = rq.path\n"
                   "        return self.get_response(request)\n",
            'another name': "def gate(r):\n    if r.method == 'GET' and r.path.startswith('/static/'):\n        return 1\n",
            'absolute uri': "def gate(request):\n    return request.build_absolute_uri()\n",
        }
        for label, source in shapes.items():
            with self.subTest(shape=label):
                self.assertTrue(full_path_reads(source), f'the census missed {label}')
        self.assertEqual(full_path_reads("def gate(request):\n    return request.path_info\n"), [])
        self.assertEqual(full_path_reads("def run(declaration):\n    return declaration.path\n"), [])
