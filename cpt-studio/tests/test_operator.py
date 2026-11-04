"""Platform-operator access and diagnostics (CORE-UX-DESIGN.md 5; R4-api-leak-surface 6.2, 6.4, 6.6(6)).

The authorization matrix for every /ops/ URL and the removed customer URLs (the trace, the reconciliation): every
non-operator - signed out, a viewer, reviewer or owner of the workspace, another workspace's owner, a revoked operator
- gets exactly what an unknown URL gets; an operator without a membership and an operator who is also an owner get the
diagnostics. A grant comes only from the management command, and no workspace role ever makes an operator. The console
(ops.html, ops.js, ops.css) is today's website, served by a gated view, and its node suite runs here.
"""
import hashlib
import inspect
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, get_resolver

from studio import models, operator, reports, serializers
from tests.support import factories as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC, _audit
from tests.test_harness_pipeline import BOTH, HarnessCase
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_pipeline import LIVE

ROOT = Path(settings.BASE_DIR)
CONSOLE = ROOT / 'studio' / 'operator'
UNKNOWN = '/ops/api/no-such-operator-route'
# the console's stylesheet: a byte copy of the website's studio/static/studio/styles.css at c9f20a148, frozen with it
OPS_CSS_SHA256 = 'c3bfa4ede6d0fe061df336f19b6daa2d36cf145e95678b0e75eb43556f167e55'


@override_settings(**LIVE, **BOTH, STORAGES=PLAIN_STATIC)
class MatrixTests(HarnessCase):
    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        self.viewer = f.member(self.ws, f.user('viewer'), role=models.Membership.VIEWER)
        self.outsider = f.member(f.workspace('Another synthetic practice'), f.user('outsider'),
                                 role=models.Membership.OWNER)
        self.operator = f.user('platform-operator')
        ops.grant(self.operator)
        self.revoked = f.user('former-operator')
        ops.grant(self.revoked)
        operator.revoke(self.revoked, 'Synthetic test: this grant ended.', 'tests')
        self.owner_operator = f.member(self.ws, f.user('owner-operator'), role=models.Membership.OWNER)
        ops.grant(self.owner_operator)
        upload = SimpleUploadedFile('synthetic-office-note.txt', OFFICE_NOTE.encode('utf-8'), content_type='text/plain')
        response = self.client.post('/api/encounters', {'file': upload, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        self.encounter_id = response.json()['id']
        drain()
        self.report = reports.generate(self.encounter(self.encounter_id), 'draft', 'txt', self.reviewer)
        self.run = self.runs_of(self.encounter_id, 'corti')[0]

    def as_user(self, user):
        client = Client(enforce_csrf_checks=False)
        if user is not None:
            client.force_login(user)
        return client

    def requests(self):
        e, r = self.encounter_id, self.report.pk
        note = {'provider_run_id': str(self.run.pk), 'note': 'Synthetic reconciliation note for the matrix.'}
        return [('GET', '/ops/', None), ('GET', '/ops/assets/ops.js', None), ('GET', '/ops/assets/ops.css', None),
                ('GET', '/ops/api/session', None), ('GET', '/ops/api/encounters', None),
                ('GET', f'/ops/api/encounters/{e}', None), ('GET', f'/ops/api/encounters/{e}/trace', None),
                ('GET', f'/ops/api/encounters/{e}/reports', None),
                ('POST', f'/ops/api/encounters/{e}/reports', {'kind': 'draft', 'fmt': 'csv'}),
                ('GET', f'/ops/api/encounters/{e}/original', None), ('GET', f'/ops/api/reports/{r}/download', None),
                ('POST', f'/ops/api/encounters/{e}/reconcile', note),
                ('POST', f'/ops/api/encounters/{e}', {}), ('DELETE', f'/ops/api/encounters/{e}/trace', None)]

    def send(self, client, method, path, body):
        if method == 'GET':
            return client.get(path)
        if method == 'DELETE':
            return client.delete(path)
        return client.post(path, data=json.dumps(body or {}), content_type='application/json')

    def test_every_operator_url_answers_every_non_operator_as_an_unknown_url(self):
        for user in (None, self.viewer, self.reviewer, self.owner, self.outsider, self.revoked):
            client = self.as_user(user)
            unknown = client.get(UNKNOWN)
            self.assertEqual(unknown.status_code, 404)
            for method, path, body in self.requests():
                with self.subTest(user=getattr(user, 'username', 'anonymous'), method=method, path=path):
                    response = self.send(client, method, path, body)
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual((response.content, response['Content-Type']),
                                     (unknown.content, unknown['Content-Type']))
        self.assertFalse(models.ReportArtifact.objects.filter(audience='operator').exclude(pk=self.report.pk).exists())
        self.assertFalse(models.ProviderRun.objects.filter(reconciled_at__isnull=False).exists())

    def test_operators_get_the_diagnostics_with_or_without_a_membership(self):
        expected = {'/ops/': 200, '/ops/assets/ops.js': 200, '/ops/assets/ops.css': 200}
        for user in (self.operator, self.owner_operator):
            client = self.as_user(user)
            for method, path, body in self.requests():
                with self.subTest(user=user.username, method=method, path=path):
                    response = self.send(client, method, path, body)
                    if method == 'DELETE' or (method == 'POST' and path.endswith(self.encounter_id)):
                        self.assertEqual(response.status_code, 405)  # an operator learns the method, nobody else
                    elif path.endswith('/reconcile'):
                        self.assertEqual((response.status_code, response.json()['error']),
                                         (409, 'Only an unreconciled unknown outcome can be reconciled.'))
                    elif method == 'POST':
                        self.assertEqual(response.status_code, 201, response.content)
                    else:
                        self.assertEqual(response.status_code, expected.get(path, 200), response.content[:300])

    def test_the_removed_customer_trace_and_reconcile_urls_answer_404_to_everyone(self):
        for user in (None, self.viewer, self.reviewer, self.owner, self.outsider, self.operator, self.owner_operator):
            client = self.as_user(user)
            unknown = client.get('/api/no-such-route')
            trace = client.get(f'/api/encounters/{self.encounter_id}/trace')
            reconcile = client.post(f'/api/encounters/{self.encounter_id}/reconcile', data=json.dumps(
                {'provider_run_id': str(self.run.pk), 'note': 'Synthetic note for a removed route.'}),
                content_type='application/json')
            for response in (trace, reconcile):
                self.assertEqual((response.status_code, response.content), (404, unknown.content))

    def test_an_operator_who_is_also_an_owner_reads_the_customer_contract_at_api(self):
        from tests.test_customer_surface import OPERATOR_ONLY, assert_contract

        client = self.as_user(self.owner_operator)
        doc = client.get(f'/api/encounters/{self.encounter_id}').json()
        assert_contract(self, doc)
        self.assertFalse(OPERATOR_ONLY & set(doc))
        full = client.get(f'/ops/api/encounters/{self.encounter_id}').json()
        self.assertTrue({'harness', 'provider_runs', 'assessment', 'activity'} <= set(full))

    def test_the_operator_payload_is_today_s_full_serializer(self):
        client = self.as_user(self.owner_operator)
        served = client.get(f'/ops/api/encounters/{self.encounter_id}').json()
        encounter = self.encounter(self.encounter_id)
        membership = models.Membership.objects.get(user=self.owner_operator, workspace=self.ws)
        direct = json.loads(json.dumps(serializers.encounter_detail(encounter, membership)))
        self.assertEqual(served, direct)
        self.assertTrue(models.AuditEvent.objects.filter(event=operator.VIEWED, actor=self.owner_operator).exists())
        # an operator with no membership reads it read-only: no action, no stop, no ask
        bare = self.as_user(self.operator).get(f'/ops/api/encounters/{self.encounter_id}').json()
        self.assertEqual(bare['permissions'], {'can_review': False, 'is_owner': False, 'can_confirm': False})
        self.assertTrue(all(p['allowed_actions'] == [] for p in bare['assessment']['proposals']))
        trace = self.as_user(self.operator).get(f'/ops/api/encounters/{self.encounter_id}/trace').json()
        self.assertEqual(trace, json.loads(json.dumps(serializers.trace_json(encounter))))

    def test_operator_reads_are_audited_once_per_window_and_never_shown_to_customers(self):
        client = self.as_user(self.operator)
        for _ in range(3):
            self.assertEqual(client.get(f'/ops/api/encounters/{self.encounter_id}').status_code, 200)
        client.get(f'/ops/api/encounters/{self.encounter_id}/trace')
        client.get(f'/ops/api/reports/{self.report.pk}/download')
        views = models.AuditEvent.objects.filter(event=operator.VIEWED, actor=self.operator)
        self.assertEqual(sorted(event.data['view'] for event in views), ['detail', 'download', 'trace'])
        self.assertEqual({event.encounter_id for event in views}, {self.encounter(self.encounter_id).pk})
        for user in (self.owner, self.reviewer, self.viewer):
            activity = self.as_user(user).get(f'/api/encounters/{self.encounter_id}').json()['activity']
            self.assertEqual([e for e in activity if 'operator' in json.dumps(e).lower()], [])
        # the access log is its own record: the encounter's activity is never changed by an operator's look at it
        events = [e['event'] for e in client.get(f'/ops/api/encounters/{self.encounter_id}').json()['activity']]
        self.assertNotIn(operator.VIEWED, events)
        self.assertEqual(serializers.OPERATOR_VIEWED, operator.VIEWED)

    def test_the_console_and_its_assets_are_served_to_operators_only_from_outside_static(self):
        client = self.as_user(self.operator)
        page = client.get('/ops/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('csrfmiddlewaretoken', page.content.decode())
        script = client.get('/ops/assets/ops.js')
        self.assertEqual(script.content, (CONSOLE / 'ops.js').read_bytes())
        self.assertEqual((script['Content-Type'], script['Cache-Control'], script['X-Content-Type-Options']),
                         ('text/javascript; charset=utf-8', 'no-store', 'nosniff'))
        style = client.get('/ops/assets/ops.css')
        self.assertEqual(style.content, (CONSOLE / 'ops.css').read_bytes())
        self.assertEqual(Client().get('/static/studio/ops.js').status_code, 404)

    def test_the_operator_report_and_the_reconciliation_are_operator_work(self):
        client = self.as_user(self.operator)
        made = client.post(f'/ops/api/encounters/{self.encounter_id}/reports',
                           data=json.dumps({'kind': 'draft', 'fmt': 'txt'}), content_type='application/json')
        self.assertEqual(made.status_code, 201, made.content)
        artifact = models.ReportArtifact.objects.get(pk=made.json()['id'])
        self.assertEqual((artifact.audience, made.json()['download_url']),
                         ('operator', f'/ops/api/reports/{artifact.pk}/download'))
        self.assertIn(reports.FORMAT_VERSION, bytes(artifact.content).decode())
        generated = models.AuditEvent.objects.filter(event='report.generated', data__report=str(artifact.pk)).get()
        self.assertEqual(generated.data['audience'], 'operator')
        for user in (self.owner, self.reviewer):
            self.assertEqual(self.as_user(user).get(f'/api/reports/{artifact.pk}/download').status_code, 404)
            activity = self.as_user(user).get(f'/api/encounters/{self.encounter_id}').json()['activity']
            self.assertEqual(sum(1 for e in activity if e['event'] == 'report_created'), 0)


@override_settings(STORAGES=PLAIN_STATIC)  # the URL sweep renders the shell and the login page
class GrantTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.tmp = Path(tempfile.mkdtemp(dir=settings.STATE_DIR))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.reason = self.tmp / 'reason.txt'
        self.reason.write_text('Synthetic platform operator for the diagnostics tests.\n', encoding='utf-8')

    def test_a_workspace_role_never_makes_an_operator_and_a_grant_survives_every_role(self):
        user = f.member(self.ws, f.user('member'), role=models.Membership.VIEWER)
        membership = models.Membership.objects.get(user=user)
        for role in (models.Membership.REVIEWER, models.Membership.OWNER, models.Membership.VIEWER):
            membership.role = role
            membership.save()
            self.assertFalse(operator.is_operator(user), role)
        ops.grant(user)
        for role, active in ((models.Membership.OWNER, True), (models.Membership.VIEWER, False)):
            membership.role, membership.active = role, active
            membership.save()
            self.assertTrue(operator.is_operator(user), role)
        operator.revoke(user, 'Synthetic test: revoked.', 'tests')
        self.assertFalse(operator.is_operator(user))
        user.is_active = False
        user.save()
        ops.grant(user)
        self.assertFalse(operator.is_operator(user), 'an inactive account is never an operator')

    def test_is_operator_reads_no_membership(self):
        user = f.user('reader')
        ops.grant(user)
        names = set(operator.is_operator.__code__.co_names)  # every global and attribute the function's code reads
        self.assertIn('OperatorGrant', names)
        self.assertFalse({name for name in names if 'membership' in name.lower()}, names)
        with self.assertNumQueries(1):
            self.assertTrue(operator.is_operator(user))

    def test_grant_operator_records_one_grant_from_the_reason_file(self):
        user = f.user('alice')
        call_command('grant_operator', username='alice', reason_file=str(self.reason), by='synthetic admin', stdout=_out())
        grant = models.OperatorGrant.objects.get(user=user)
        self.assertEqual((grant.reason, grant.granted_by),
                         ('Synthetic platform operator for the diagnostics tests.', 'synthetic admin'))
        out = _out()
        call_command('grant_operator', username='alice', reason_file=str(self.reason), stdout=out)
        self.assertIn('already holds operator access', out.getvalue())
        self.assertEqual(models.OperatorGrant.objects.filter(user=user).count(), 1)
        self.assertTrue(operator.is_operator(user))

    def test_grant_operator_refuses_and_records_nothing(self):
        f.user('bob')
        empty = self.tmp / 'empty.txt'
        empty.write_text('   \n', encoding='utf-8')
        inactive = f.user('carol')
        inactive.is_active = False
        inactive.save()
        for username, reason, words in (('nobody-here', self.reason, 'No account is named'),
                                        ('bob', self.tmp / 'missing.txt', 'cannot be read'),
                                        ('bob', empty, 'empty'), ('carol', self.reason, 'not active')):
            with self.subTest(username=username, reason=reason.name), self.assertRaisesRegex(CommandError, words):
                call_command('grant_operator', username=username, reason_file=str(reason), stdout=_out())
        self.assertFalse(models.OperatorGrant.objects.exists())

    def test_revoke_operator_ends_the_grant_and_refuses_without_one(self):
        user = f.user('dave')
        ops.grant(user)
        call_command('revoke_operator', username='dave', reason_file=str(self.reason), by='synthetic admin',
                     stdout=_out())
        revocation = models.OperatorRevocation.objects.get(grant__user=user)
        self.assertEqual(revocation.revoked_by, 'synthetic admin')
        self.assertFalse(operator.is_operator(user))
        self.assertEqual(models.OperatorGrant.objects.filter(user=user).count(), 1)  # the grant row stays
        for username in ('dave', 'nobody-here'):
            with self.assertRaises(CommandError):
                call_command('revoke_operator', username=username, reason_file=str(self.reason), stdout=_out())
        self.assertEqual(models.OperatorRevocation.objects.count(), 1)

    def test_grants_and_revocations_are_append_only(self):
        grant = ops.grant(f.user('erin'))
        grant.reason = 'changed'
        with self.assertRaises(Exception):
            grant.save()
        with self.assertRaises(Exception):
            models.OperatorGrant.objects.all().delete()

    def test_no_url_records_a_grant(self):
        """Statically: no view module of the URLconf names the grant or its writer; behaviourally: an owner and an operator
        posting to every URL pattern record none."""
        modules = set()
        for pattern in get_resolver().url_patterns:
            if isinstance(pattern, URLPattern):
                modules.add(inspect.getmodule(pattern.callback))
        for module in modules:
            source = inspect.getsource(module)
            if module is operator:
                source = source.replace(inspect.getsource(operator.grant), '').replace(
                    inspect.getsource(operator.revoke), '')
            self.assertNotRegex(source, r'OperatorGrant\.objects\.create|OperatorRevocation\.objects\.create|'
                                        r'operator\.grant\(|\bgrant\(', module.__name__)
        writers = [path.relative_to(ROOT) for path in (ROOT / 'studio').rglob('*.py')
                   if re.search(r'operator\.grant\(|OperatorGrant\.objects\.create', path.read_text(encoding='utf-8'))]
        self.assertEqual(sorted(map(str, writers)), ['studio/management/commands/grant_operator.py', 'studio/operator.py'])
        owner = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        platform = f.user('platform')
        ops.grant(platform)
        before = models.OperatorGrant.objects.count()
        for user in (owner, platform):
            client = Client(enforce_csrf_checks=False)
            client.force_login(user)
            for pattern in get_resolver().url_patterns:
                route = str(pattern.pattern).replace('<uuid:encounter_id>', '00000000-0000-4000-8000-000000000001') \
                    .replace('<uuid:report_id>', '00000000-0000-4000-8000-000000000002') \
                    .replace('<uuid:clarification_id>', '00000000-0000-4000-8000-000000000003')
                if route in ('logout/',):
                    continue
                client.post('/' + route, data=json.dumps({'username': user.username, 'reason': 'x' * 20}),
                            content_type='application/json')
        self.assertEqual(models.OperatorGrant.objects.count(), before)
        self.assertFalse(operator.is_operator(owner))


@override_settings(STORAGES=PLAIN_STATIC)
class LoginTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()

    def login(self, username, next_url=None):
        data = {'username': username, 'password': 'synthetic-pass-123!'}
        if next_url:
            data['next'] = next_url
        return Client().post('/login/', data)

    def test_an_operator_without_a_membership_signs_in_and_lands_on_the_diagnostics(self):
        user = f.user('ops-agent', actor_kind=models.User.AGENT)
        ops.grant(user)
        response = self.login('ops-agent')
        self.assertEqual((response.status_code, response['Location']), (302, '/ops/'))
        client = Client()
        client.force_login(user)
        self.assertEqual(client.get('/')['Location'], '/ops/')
        self.assertEqual(client.get('/api/session').status_code, 404)  # no workspace of their own
        self.assertEqual(client.get('/ops/api/session').json()['role'], 'operator')
        asked = self.login('ops-agent', '/ops/#doc/x')
        self.assertEqual(asked['Location'], '/ops/#doc/x')

    def test_a_member_operator_lands_where_members_land(self):
        user = f.member(self.ws, f.user('owner'), role=models.Membership.OWNER)
        ops.grant(user)
        self.assertEqual(self.login('owner')['Location'], '/')
        client = Client()
        client.force_login(user)
        self.assertEqual(client.get('/').status_code, 200)

    def test_without_a_membership_or_a_grant_sign_in_is_refused_as_before(self):
        f.user('stranger')
        revoked = f.user('former')
        ops.grant(revoked)
        operator.revoke(revoked, 'Synthetic test: revoked.', 'tests')
        for username in ('stranger', 'former'):
            response = self.login(username)
            self.assertEqual(response.status_code, 400, username)
            self.assertIn('The username or password is not correct.', response.content.decode())


class ConsoleTemplateTests(SimpleTestCase):
    """ops.html is the console's own shell: CSP-clean, one script (/ops/assets/ops.js), and every element its script
    looks up."""

    def render(self):
        from django.template.loader import render_to_string
        from django.test import RequestFactory
        with override_settings(STORAGES=PLAIN_STATIC):
            return render_to_string('studio/ops.html', {'release': 'test-release'}, request=RequestFactory().get('/ops/'))

    def test_the_console_obeys_the_content_security_policy_with_one_script(self):
        html = self.render()
        audit = _audit(html)
        self.assertFalse(audit.inline_script)
        self.assertEqual(audit.handlers, [])
        self.assertEqual(audit.unsafe_urls, [])
        self.assertEqual(audit.external, [])
        self.assertEqual(audit.script_sources, ['/ops/assets/ops.js'])
        self.assertIn('href="/ops/assets/ops.css"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertNotIn('/static/studio/app.js', html)

    def test_every_element_id_the_console_looks_up_exists(self):
        ids = set(_audit(self.render()).ids)
        script = (CONSOLE / 'ops.js').read_text(encoding='utf-8')
        rendered = set(re.findall(r'id="([A-Za-z][\w-]*)"', script)) | set(re.findall(r"\.id = '([A-Za-z][\w-]*)'", script))
        looked_up = set()
        for selector in re.findall(r"\$\$?\('([^']*)'", script):
            looked_up.update(re.findall(r'#([A-Za-z][\w-]*)', selector))
        self.assertEqual(sorted(looked_up - ids - rendered), [])

    def test_the_console_is_the_website_with_its_api_base_switched(self):
        script = (CONSOLE / 'ops.js').read_text(encoding='utf-8')
        self.assertNotRegex(script.replace('/ops/api/', ''), r'/api/')
        self.assertIn(r'const REPORT_URL = /^\/ops\/api\/reports\/', script)
        self.assertEqual(hashlib.sha256((CONSOLE / 'ops.css').read_bytes()).hexdigest(), OPS_CSS_SHA256)
        for unsafe in ('eval(', 'new Function', 'document.write', 'insertAdjacentHTML', 'outerHTML'):
            self.assertNotIn(unsafe, script)
        self.assertIsNone(re.search(r'https?://|@import|url\(', script))


class ConsoleLogicTests(SimpleTestCase):
    """tests/operator/ops.test.cjs - the website's node suite, copied with the console - passes in full."""

    def setUp(self):
        self.node = shutil.which('node')
        if self.node is None:
            self.skipTest('node is not installed; the console logic tests need it')

    def test_console_logic_unit_tests_pass(self):
        path = ROOT / 'tests' / 'operator' / 'ops.test.cjs'
        declared = len(re.findall(r'(?m)^test(?:\.(?:skip|todo|only))?\(', path.read_text(encoding='utf-8')))
        result = subprocess.run([self.node, '--test', '--test-reporter=tap', str(path)],
                                cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])

        def total(name):
            return [int(n) for n in re.findall(rf'(?m)^# {name} (\d+)$', result.stdout)]
        self.assertGreater(declared, 20)
        self.assertEqual(total('fail')[-1:], [0], result.stdout[-2000:])
        self.assertEqual((total('skipped')[-1:], total('todo')[-1:]), ([0], [0]), result.stdout[-2000:])
        self.assertTrue(total('pass') and total('pass')[-1] >= declared, (total('pass'), declared))
        self.assertRegex(result.stdout, r'(?m)^ok \d+ - the trace link is shown on every console page')

    def test_the_console_script_parses(self):
        result = subprocess.run([self.node, '--check', str(CONSOLE / 'ops.js')], capture_output=True, text=True,
                                timeout=60, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


class MigrationTests(SimpleTestCase):
    def test_the_operator_migration_is_additive_for_the_rolling_install(self):
        from ops import install
        verdict = install.migration_verdict((ROOT / 'studio' / 'migrations' / '0009_cux_operator.py').read_text())
        self.assertEqual(verdict, {'safe': True, 'why': [
            'reportartifact.audience: NOT NULL with a database default (db_default)',
            'OperatorGrant: a new table no older revision reads', 'OperatorRevocation: a new table no older revision reads']})


def _out():
    import io
    return io.StringIO()
