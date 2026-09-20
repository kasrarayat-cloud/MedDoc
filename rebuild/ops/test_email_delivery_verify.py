"""Controlled email runner regression checks; no network, mail or application DB."""
import importlib.util
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import httpx

SPEC = importlib.util.spec_from_file_location('email_delivery_verify', Path(__file__).resolve().parents[1] / 'email-delivery-verify.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

RECIPIENT = 'controlled@approved-mail.example.org'
DEPARTMENT = '9df47064-b779-4992-906d-d7efdf54135b'
ACCOUNT = '8c3473be-7096-4b02-b292-11a4baf6332e'
RELEASE = 'a' * 40


class AuthorizationTests(unittest.TestCase):
    def records(self):
        browser = {'origin': runner.BASE, 'reachable': True, 'confirmed_by': 'owner',
                   'confirmed_at': runner.now(), 'evidence_reference': 'owner receipt 20260920'}
        authorization = {'origin': runner.BASE, 'release': RELEASE, 'recipient': RECIPIENT,
                         'department_id': DEPARTMENT, 'checked_at': runner.now(),
                         'evidence_reference': 'protected baseline.json',
                         'invitation': {'recipient_absent': True},
                         'recovery': {'account_id': ACCOUNT, 'verified': True, 'is_staff': False,
                                      'department_id': DEPARTMENT, 'role': 'employee', 'invitation_accepted': True}}
        return browser, authorization

    def authorize(self, browser, authorization, stage='invitation'):
        with patch.object(runner, 'private_read', side_effect=[browser, authorization]):
            return runner.execution_authorization(Path('/unused'), RECIPIENT, DEPARTMENT, RELEASE, stage)

    def test_exact_owner_browser_and_absent_recipient_evidence_accepted_without_receipt_claim(self):
        result = self.authorize(*self.records())
        self.assertTrue(result['owner_browser_reachability']['confirmed'])
        self.assertNotIn('inbox_receipt_confirmed', result)
        self.assertNotIn(RECIPIENT, str(result))

    def test_missing_unconfirmed_wrong_origin_and_stale_browser_evidence_refused(self):
        for change in ({'reachable': False}, {'confirmed_by': 'operator'},
                       {'origin': 'https://attacker.invalid'}, {'confirmed_at': '2000-01-01T00:00:00+00:00'},
                       {'confirmed_at': '2999-01-01T00:00:00+00:00'}, {'confirmed_at': '2026-09-20'}):
            browser, authorization = self.records()
            browser.update(change)
            with self.subTest(change=change), self.assertRaises(runner.Refusal):
                self.authorize(browser, authorization)

    def test_existing_recipient_or_wrong_scope_release_evidence_refused(self):
        for field, value in [('recipient', 'someone-else@example.org'), ('department_id', ACCOUNT),
                             ('release', 'b' * 40), ('invitation', {'recipient_absent': False})]:
            browser, authorization = self.records()
            authorization[field] = value
            with self.subTest(field=field), self.assertRaises(runner.Refusal):
                self.authorize(browser, authorization)

    def test_recovery_requires_independently_verified_nonstaff_employee_acceptance(self):
        self.authorize(*self.records(), stage='recovery')
        for field, value in [('account_id', 'not-a-uuid'), ('verified', False), ('is_staff', True),
                             ('role', 'owner'), ('department_id', ACCOUNT), ('invitation_accepted', False)]:
            browser, authorization = self.records()
            authorization['recovery'][field] = value
            with self.subTest(field=field), self.assertRaises(runner.Refusal):
                self.authorize(browser, authorization, stage='recovery')

    def test_evidence_reference_must_not_be_a_token_url(self):
        browser, authorization = self.records()
        browser['evidence_reference'] = runner.BASE + '/invite/sensitive/'
        with self.assertRaises(runner.Refusal):
            self.authorize(browser, authorization)


class PrivateOriginTests(unittest.TestCase):
    def test_access_credentials_require_the_exact_approved_origin(self):
        for origin in ('http://app.quillmd.com:9443', 'https://app.quillmd.com',
                       'https://app.quillmd.com:9443.attacker.invalid', runner.BASE + '/'):
            with self.subTest(origin=origin), patch.object(runner, 'private_read', return_value={
                    'origin': origin, 'username': 'synthetic', 'password': 'synthetic-only'}), self.assertRaises(runner.Refusal):
                runner.private_access(Path('/unused'))
        with patch.object(runner, 'private_read', return_value={
                'origin': runner.BASE, 'username': 'synthetic', 'password': 'synthetic-only'}):
            self.assertEqual(runner.private_access(Path('/unused')), {'username': 'synthetic', 'password': 'synthetic-only'})

    def test_client_enforces_tls_and_never_sends_basic_credentials(self):
        with patch.object(runner.httpx, 'Client') as client, patch.object(runner.preview_http, 'authenticate') as login, patch.object(runner.preview_http, 'sign_out') as logout:
            auth = {'username': 'synthetic', 'password': 'synthetic-only'}
            with runner.private_client(auth):
                pass
            options = client.call_args.kwargs
            self.assertEqual(options['base_url'], runner.BASE)
            self.assertNotIn('auth', options)
            self.assertIs(options['verify'], True)
            self.assertIs(options['follow_redirects'], False)
            self.assertIs(options['trust_env'], False)
            login.assert_called_once()
            logout.assert_called_once()

    def probe(self, public_status=302, location='/preview/sign-in/?flow=' + 'a' * 64, challenge=None, auth_status=200, body=None):
        seen = []
        auth = {'username': 'synthetic', 'password': 'synthetic-only'}
        def client(client_auth=None):
            def handler(request):
                seen.append((str(request.url), client_auth is not None, bool(request.headers.get('authorization'))))
                if client_auth is None:
                    headers = {'location': location}
                    if challenge is not None:
                        headers['www-authenticate'] = challenge
                    return httpx.Response(public_status, headers=headers)
                return httpx.Response(auth_status, json=body or {'release': RELEASE, 'data_mode': 'synthetic-only', 'surface': 'doctor'}, headers={'location': 'https://attacker.invalid'})
            return httpx.Client(base_url=runner.BASE, transport=httpx.MockTransport(handler), follow_redirects=False)
        with patch.object(runner, 'private_client', side_effect=client):
            runner.private_https_health(auth, RELEASE)
        return seen

    def test_private_gate_proves_form_redirect_and_exact_authenticated_release(self):
        self.assertEqual(self.probe(), [(runner.BASE + '/health/', False, False), (runner.BASE + '/health/', True, False)])

    def test_public_access_external_return_basic_challenge_or_wrong_release_never_pass(self):
        for changes in ({'public_status': 200}, {'public_status': 401}, {'challenge': 'Basic realm="Private"'},
                        {'location': 'https://attacker.invalid/preview/sign-in/'}, {'location': '/login/'},
                        {'auth_status': 302}, {'body': {'release': 'b' * 40, 'data_mode': 'synthetic-only', 'surface': 'doctor'}},
                        {'body': {'release': RELEASE, 'data_mode': 'real-patients', 'surface': 'doctor'}}):
            with self.subTest(changes=changes), self.assertRaises(runner.Refusal):
                self.probe(**changes)


class SubmissionTests(unittest.TestCase):
    def page(self, departments):
        return SimpleNamespace(selects={'department': departments, 'role': [('employee', 'Employee')]}, csrf='synthetic-csrf')

    def test_missing_pinned_xray_department_never_posts(self):
        for options in ([(ACCOUNT, 'X-ray')], [(DEPARTMENT, 'Ultrasound')],
                        [(DEPARTMENT, 'X-ray'), (DEPARTMENT, 'X-ray')]):
            client = unittest.mock.Mock()
            with self.subTest(options=options), patch.object(runner, 'fetch', return_value=self.page(options)), self.assertRaises(runner.Refusal):
                runner.invite(client, RECIPIENT, DEPARTMENT)
            client.post.assert_not_called()

    def test_invitation_posts_only_pinned_department_and_employee_then_recognizes_acceptance(self):
        client = unittest.mock.Mock()
        client.post.return_value.status_code = 302
        after = SimpleNamespace(notices=['Invitation submitted to the email provider. Inbox delivery is not yet confirmed.'],
                                rows=[], csrf='synthetic-csrf')
        with patch.object(runner, 'fetch', side_effect=[self.page([(DEPARTMENT, 'X-ray')]), after]):
            outcome = runner.invite(client, RECIPIENT, DEPARTMENT)
        self.assertEqual(client.post.call_args.kwargs['data']['department'], DEPARTMENT)
        self.assertEqual(client.post.call_args.kwargs['data']['role'], 'employee')
        self.assertEqual(client.post.call_args.kwargs['headers']['Referer'], runner.BASE + '/team/')
        self.assertEqual(runner.require_submission('invitation', outcome), 'provider-accepted')

    def test_failed_unknown_rate_limited_or_outbox_invitation_cannot_pass(self):
        for status, outcome in ((429, 'rate-limited'), (302, 'delivery-failed'), (302, 'no-recognised-notice'),
                                (302, 'private-outbox-only'), (200, 'rejected')):
            with self.subTest(outcome=outcome), self.assertRaises(runner.Refusal):
                runner.require_submission('invitation', {'invitation_http_status': status, 'invitation_outcome': outcome})

    def test_recovery_acknowledgement_does_not_claim_provider_acceptance_or_receipt(self):
        outcome = {'recovery_http_status': 200, 'recovery_page_acknowledged': True, 'recovery_page_reports_live_delivery': True}
        self.assertEqual(runner.require_submission('recovery', outcome), 'request-acknowledged-provider-outcome-not-proved')
        for change in ({'recovery_http_status': 429}, {'recovery_page_acknowledged': False}, {'recovery_page_reports_live_delivery': False}):
            with self.subTest(change=change), self.assertRaises(runner.Refusal):
                runner.require_submission('recovery', {**outcome, **change})

    def test_both_is_not_a_supported_stage(self):
        self.assertEqual(runner.STAGES, ('invitation', 'recovery'))

    def test_exclusive_attempt_evidence_cannot_replace_an_existing_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'attempt.execution-lock'
            runner.write_private(path, {'attempt': 'synthetic', 'started_at': runner.now()})
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                runner.write_private(path, {'attempt': 'replacement'})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class MainOutcomeTests(unittest.TestCase):
    def test_failed_provider_outcome_is_preserved_and_main_cannot_return_green(self):
        self.main_case('delivery-failed', expected_pass=False)

    def test_successful_submission_keeps_delivery_receipt_and_workflow_unconfirmed(self):
        self.main_case('accepted-by-provider', expected_pass=True)

    def main_case(self, outcome, expected_pass):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            permanent = Path(directory) / 'rebuild'
            runtime = permanent / '.runtime'
            runtime.mkdir(parents=True, mode=0o700)
            stack.enter_context(patch.object(runner, 'PERMANENT', permanent))
            stack.enter_context(patch.object(runner, '__file__', str(permanent / 'email-delivery-verify.py')))
            stack.enter_context(patch.object(runner.sys, 'prefix', str(permanent / '.venv')))
            stack.enter_context(patch.object(runner.sys, 'argv', ['email-delivery-verify.py', '--release', RELEASE,
                '--recipient', RECIPIENT, '--recipient-confirmation', runner.CONFIRMATION,
                '--department', DEPARTMENT, '--attempt', 'synthetic-check', '--stage', 'invitation', '--execute']))
            stack.enter_context(patch.object(runner, 'private_read', return_value={'doctor': {}}))
            stack.enter_context(patch.object(runner, 'settings_probe', return_value={
                'resend_mode': True, 'configured': True, 'app_base_url_matches_private_https': True, 'sender_domain': '',
                'provider_domain_status': {'readable': False}}))
            stack.enter_context(patch.object(runner, 'execution_authorization', return_value={'matched': True}))
            stack.enter_context(patch.object(runner, 'private_access', return_value=object()))
            stack.enter_context(patch.object(runner, 'private_https_health'))
            stack.enter_context(patch.object(runner, 'private_client'))
            stack.enter_context(patch.object(runner, 'health'))
            stack.enter_context(patch.object(runner, 'login'))
            stack.enter_context(patch.object(runner, 'logout'))
            send = stack.enter_context(patch.object(runner, 'invite', return_value={
                'invitation_http_status': 302, 'invitation_outcome': outcome, 'csrf': 'synthetic-csrf'}))
            with redirect_stdout(io.StringIO()):
                if expected_pass:
                    runner.main()
                else:
                    with self.assertRaises(runner.Refusal):
                        runner.main()
            files = list(runtime.glob('*.json'))
            self.assertEqual(len(files), 1)
            report = json.loads(files[0].read_text())
            self.assertEqual(report['passed'], expected_pass)
            self.assertTrue(report['executed'])
            self.assertEqual(report['pass_scope'], 'submission-checks-only')
            self.assertEqual(report['invitation_outcome']['invitation_outcome'], outcome)
            for key in ('provider_delivery_confirmed', 'inbox_receipt_confirmed', 'application_flow_completed'):
                self.assertIs(report[key], False)
            self.assertNotIn('synthetic-csrf', files[0].read_text())
            self.assertNotIn(RECIPIENT, files[0].read_text())
            send.assert_called_once()
            original = files[0].read_bytes()
            # The preserved original report must prevent a second submission.
            with self.assertRaises(runner.Refusal):
                runner.main()
            send.assert_called_once()
            self.assertEqual(files[0].read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
