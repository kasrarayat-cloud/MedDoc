"""Declared administrator changes (inventory 7A, F2): a second administrator, and an administrator's authenticator
reset — core.admin_authority, `manage.py elevate_additional_admin`, `manage.py reset_admin_mfa`.

Every refusal arm asserts NOTHING CHANGED: the accounts' staff flags and session versions, every authenticator row
(including the last code it accepted and its failure count) and the audit trail are compared whole, before and after.
The repository declarations live in a scratch git checkout, committed the way scripts/run-ruled-mutation.sh requires,
and the door's two variables are passed explicitly. The approver's presence is a current code from the approver's own
authenticator, in a 0600 file. The production door (refutation R5) is exercised in-process with the host facts it
cannot have here stubbed (root, the bootstrap receipt, the RDS description, the CA bundle, the TLS connection), and
once more from a release-shaped copy — rebuild/ alone, no git, no docs, no scripts — in a separate process.
"""
import io
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import admin_authority as authority
from core.models import AuditEvent, User

Refused = authority.Refused

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
PASSWORD = 'Synthetic-Only-administrator-6203!'
GIT = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic Test',
       '-c', 'user.email=synthetic@test.invalid']
NAME = '20261001-quillmd-admin-synthetic.md'


def code(device):
    return str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits)).zfill(6)


class DeclaredChangeFixture(TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='admin-authority-'))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.git('init', '-q')
        (self.root / 'docs' / 'foundation' / 'mutations').mkdir(parents=True)
        (self.root / 'README').write_text('synthetic checkout\n')
        self.git('add', 'README')
        self.git('commit', '-q', '-m', 'Synthetic checkout')
        now = timezone.now()
        self.approver = User.objects.create_user(username='approver', email='approver@synthetic.invalid',
                                                 password=PASSWORD, verified_at=now, is_staff=True)
        self.approver_device = TOTPDevice.objects.create(user=self.approver, name='Approver', confirmed=True)
        self.doctor = User.objects.create_user(username='second', email='second@synthetic.invalid',
                                               password=PASSWORD, verified_at=now)
        self.doctor_device = TOTPDevice.objects.create(user=self.doctor, name='Doctor', confirmed=True)
        self.admin = User.objects.create_user(username='lost-phone', email='lost-phone@synthetic.invalid',
                                              password=PASSWORD, verified_at=now, is_staff=True)
        self.admin_devices = [TOTPDevice.objects.create(user=self.admin, name='Old phone', confirmed=True),
                              TOTPDevice.objects.create(user=self.admin, name='Abandoned', confirmed=False)]
        self.codes = Path(tempfile.mkdtemp(prefix='approver-code-'))
        self.addCleanup(shutil.rmtree, self.codes, True)

    def code_file(self, device=None, value=None, mode=0o600, name='code'):
        """A file holding the approver's CURRENT code (or `value`), mode 0600, as the approver would write it."""
        if value is None:
            device = device or self.approver_device
            device.refresh_from_db()
            value = code(device)
        path = self.codes / name
        path.write_text(value + '\n')
        path.chmod(mode)
        return str(path)

    def git(self, *args):
        return subprocess.run([*GIT, '-C', str(self.root), *args], capture_output=True, check=True)

    def text(self, operation, target, approver=None, reason='Synthetic second administrator for the test roster',
             **override):
        approver = approver or self.approver
        lines = {'operation': operation, 'target_account': str(target.pk), 'target_email': target.email,
                 'approver_account': str(approver.pk), 'approver_email': approver.email, 'reason': reason}
        lines.update(override)
        return '# Declaration — synthetic\n\n' + ''.join(f'{k}: {v}\n' for k, v in lines.items() if v is not None)

    def declare(self, text, name=NAME, commit=True):
        path = self.root / 'docs' / 'foundation' / 'mutations' / name
        path.write_text(text)
        relative = str(path.relative_to(self.root))
        if commit:
            self.git('add', '--', relative)
            self.git('commit', '-q', '-m', 'Synthetic declaration ' + name)
        head = self.git('log', '-1', '--format=%H', '--', relative).stdout.decode().strip()
        return relative, {'RULED_MUTATION_DECLARATION': relative, 'RULED_MUTATION_DECL_COMMIT': head}

    def perform(self, operation, relative, target, environ, code_file=None):
        code_file = self.code_file() if code_file is None else code_file
        return authority.perform(operation, relative, target, code_file or None, repository=self.root,
                                 environ=environ)

    def state(self):
        users = list(User.objects.order_by('pk').values_list('pk', 'is_staff', 'is_superuser', 'is_active',
                                                             'session_version', 'password'))
        devices = list(TOTPDevice.objects.order_by('pk').values_list('pk', 'user_id', 'confirmed', 'key', 'last_t',
                                                                     'throttling_failure_count'))
        return users, devices, AuditEvent.objects.count()

    def assertRefusedUnchanged(self, message, operation, relative, target, environ, code_file=None):
        before = self.state()
        with self.assertRaisesRegex(Refused, message):
            self.perform(operation, relative, target, environ, code_file)
        self.assertEqual(self.state(), before, 'a refused administrator change changed something')

    def assertAbsenceRecorded(self, message, operation, relative, target, environ, code_file, *, reason,
                              counted=True, approver=None):
        """Refutation R7-a: a code that does not prove the approver's presence is refused, and the attempt is RECORDED
        in a transaction of its own — the approver's device throttle counts it and one audit row names the operator,
        the approver and the command — while the act itself is wholly rolled back. Nothing else changes."""
        approver = approver or self.approver
        users, devices, audits = self.state()
        mine = {row[0] for row in devices if row[1] == approver.pk and row[2]}
        with self.assertRaisesRegex(Refused, message):
            self.perform(operation, relative, target, environ, code_file)
        users_after, devices_after, audits_after = self.state()
        self.assertEqual(users_after, users, 'a refused administrator change changed an account')
        for row, after in zip(devices, devices_after):
            if row[0] in mine and counted:
                self.assertEqual(after[:5] + (after[5] - 1,), row, 'the failure was not counted on the approver\'s device')
            else:
                self.assertEqual(after, row, 'a device the attempt did not use changed')
        self.assertEqual(audits_after, audits + 1)
        event = AuditEvent.objects.order_by('-created_at').first()
        self.assertEqual((event.action, event.actor_id, event.target), ('account.admin_change_refused', None,
                                                                       str(approver.pk)))
        details = event.details
        self.assertEqual((details['command'], details['reason'], details['approver'], details['change_target']),
                         (operation, reason, str(approver.pk), str(target)))
        self.assertEqual((details['operator_uid'], details['operator_euid']), (os.getuid(), os.geteuid()))
        # The record names the declaration it was for (round-3 m4: a record without it passed).
        for key in ('door', 'declaration', 'declaration_commit', 'declaration_sha256', 'declaration_key',
                    'act_identity'):
            self.assertTrue(details.get(key), f'the refusal record does not name {key}')
        self.assertEqual(details['declaration'], relative)
        written = Path(code_file).read_text().strip()
        self.assertNotIn(written, json.dumps(details), 'the presented code reached the audit trail')
        return event


class ElevateAdditionalAdministrator(DeclaredChangeFixture):
    def test_positive_control_elevates_signs_out_and_audits_once(self):
        browser = Client()
        browser.force_login(self.doctor)
        self.assertEqual(browser.get('/api/patients/').status_code, 200)
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor))
        result = self.perform(authority.ELEVATE, relative, self.doctor.pk, door)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.is_staff)
        self.assertFalse(self.doctor.is_superuser)
        self.assertEqual(self.doctor.session_version, 1)
        signed_out = browser.get('/api/patients/')
        self.assertEqual((signed_out.status_code, signed_out.url.split('?')[0]), (302, '/login/'),
                         'the clinical session survived elevation')
        event = AuditEvent.objects.get(action='account.admin_elevated')
        self.assertEqual((event.actor_id, event.target), (self.approver.pk, str(self.doctor.pk)))
        self.assertEqual(event.details['declaration'], relative)
        self.assertEqual(event.details['declaration_commit'], door['RULED_MUTATION_DECL_COMMIT'])
        self.assertEqual(len(event.details['declaration_sha256']), 64)
        self.assertEqual(event.details['approver'], str(self.approver.pk))
        self.assertTrue(event.details['sessions_invalidated'])
        self.assertEqual(result['target'], str(self.doctor.pk))
        # R7: the actor is the approver because the approver's code proved presence; the operator is recorded too.
        self.assertEqual(event.details['approver_presence'], 'authenticator code verified')
        self.assertEqual(event.details['approver_device'], self.approver_device.persistent_id)
        self.assertEqual((event.details['operator_uid'], event.details['operator_euid']), (os.getuid(), os.geteuid()))
        self.assertEqual(event.details['door'], 'repository')
        self.assertEqual(event.details['declaration_author'], 'Synthetic Test <synthetic@test.invalid>')
        self.assertEqual(event.details['declaration_committer'], 'Synthetic Test <synthetic@test.invalid>')
        self.approver_device.refresh_from_db()
        self.assertGreater(self.approver_device.last_t, -1, 'the approver\'s code was not consumed')

    def test_without_the_door_nothing_changes(self):
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor))
        self.assertRefusedUnchanged('ruled-mutation door', authority.ELEVATE, relative, self.doctor.pk, {})
        self.assertRefusedUnchanged('ruled-mutation door', authority.ELEVATE, relative, self.doctor.pk,
                                    {'RULED_MUTATION_DECLARATION': relative})

    def test_a_door_opened_for_another_declaration_or_commit_refuses(self):
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor))
        other, other_door = self.declare(self.text(authority.ELEVATE, self.doctor, reason='Another synthetic reason'),
                                         name='20261001-quillmd-admin-other.md')
        self.assertRefusedUnchanged('another declaration', authority.ELEVATE, relative, self.doctor.pk,
                                    {**door, 'RULED_MUTATION_DECLARATION': other})
        self.assertRefusedUnchanged('another commit', authority.ELEVATE, relative, self.doctor.pk,
                                    {**door, 'RULED_MUTATION_DECL_COMMIT': '0' * 40})

    def test_an_uncommitted_or_edited_declaration_refuses(self):
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor), commit=False)
        self.assertRefusedUnchanged('tracked, committed and unmodified', authority.ELEVATE, relative,
                                    self.doctor.pk, door)
        committed, door = self.declare(self.text(authority.ELEVATE, self.doctor), name='20261001-quillmd-admin-b.md')
        (self.root / committed).write_text(self.text(authority.ELEVATE, self.admin))
        self.assertRefusedUnchanged('tracked, committed and unmodified', authority.ELEVATE, committed,
                                    self.doctor.pk, door)

    def test_a_declaration_outside_the_mutations_directory_refuses(self):
        path = self.root / 'docs' / NAME
        path.write_text(self.text(authority.ELEVATE, self.doctor))
        self.git('add', '--', 'docs/' + NAME)
        self.git('commit', '-q', '-m', 'misplaced')
        self.assertRefusedUnchanged('docs/foundation/mutations/', authority.ELEVATE, 'docs/' + NAME,
                                    self.doctor.pk, {'RULED_MUTATION_DECLARATION': 'docs/' + NAME,
                                                     'RULED_MUTATION_DECL_COMMIT': 'f' * 40})

    def test_a_declaration_for_another_operation_or_target_refuses(self):
        relative, door = self.declare(self.text(authority.RESET, self.doctor))
        self.assertRefusedUnchanged('not elevate_additional_admin', authority.ELEVATE, relative, self.doctor.pk, door)
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor), name='20261001-quillmd-admin-c.md')
        self.assertRefusedUnchanged('another target account', authority.ELEVATE, relative, self.admin.pk, door)

    def test_the_approver_cannot_be_the_target(self):
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor, approver=self.doctor))
        self.assertRefusedUnchanged('same account', authority.ELEVATE, relative, self.doctor.pk, door)

    def test_the_approver_must_be_an_administrator(self):
        clinician = User.objects.create_user(username='not-admin', email='not-admin@synthetic.invalid',
                                             password=PASSWORD, verified_at=timezone.now())
        TOTPDevice.objects.create(user=clinician, confirmed=True)
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor, approver=clinician))
        self.assertRefusedUnchanged('not an active, verified administrator', authority.ELEVATE, relative,
                                    self.doctor.pk, door)

    def test_the_approver_must_have_a_confirmed_authenticator(self):
        self.approver_device.confirmed = False
        self.approver_device.save(update_fields=['confirmed'])
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor))
        self.assertRefusedUnchanged('no confirmed authenticator', authority.ELEVATE, relative, self.doctor.pk, door)

    def test_a_missing_target_or_an_email_that_does_not_match_refuses(self):
        ghost = User(pk=uuid.uuid4(), email='ghost@synthetic.invalid')
        relative, door = self.declare(self.text(authority.ELEVATE, ghost))
        self.assertRefusedUnchanged('target account does not exist', authority.ELEVATE, relative, ghost.pk, door)
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor, target_email='other@synthetic.invalid'),
                                      name='20261001-quillmd-admin-d.md')
        self.assertRefusedUnchanged('target account does not exist', authority.ELEVATE, relative, self.doctor.pk, door)

    def test_the_target_must_be_a_verified_mfa_enrolled_non_administrator(self):
        self.doctor_device.delete()
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor))
        self.assertRefusedUnchanged('target has no confirmed authenticator', authority.ELEVATE, relative,
                                    self.doctor.pk, door)
        relative, door = self.declare(self.text(authority.ELEVATE, self.admin), name='20261001-quillmd-admin-e.md')
        self.assertRefusedUnchanged('not an active, verified, non-administrator', authority.ELEVATE, relative,
                                    self.admin.pk, door)

    def test_a_declaration_is_used_once(self):
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor))
        self.perform(authority.ELEVATE, relative, self.doctor.pk, door)
        User.objects.filter(pk=self.doctor.pk).update(is_staff=False)   # demoted later, by whatever means
        self.assertRefusedUnchanged('already been used', authority.ELEVATE, relative, self.doctor.pk, door)

    def test_a_reformatted_copy_of_a_used_repository_declaration_is_refused(self):
        """R5-a for the repository door: another file with the same act, laid out differently, is the same act."""
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor))
        self.perform(authority.ELEVATE, relative, self.doctor.pk, door)
        copy = self.text(authority.ELEVATE, self.doctor).replace('# Declaration — synthetic', '# Copy\n\nMore prose.')
        copy = copy.replace(': ', ':   ')
        relative, door = self.declare(copy, name='20261001-quillmd-admin-copy.md')
        self.assertRefusedUnchanged('same act was already performed', authority.ELEVATE, relative, self.doctor.pk, door)

    def test_the_reason_is_compared_after_unicode_and_whitespace_normalisation(self):
        """Round-3 m2 and R3-3: a copy whose reason differs only in internal whitespace, Unicode composition (NFD
        against NFC) or invisible format characters (a zero-width space) is the same act."""
        reason = 'Synthetic second administrator, Zoë checked the roster'
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor, reason=reason))
        self.perform(authority.ELEVATE, relative, self.doctor.pk, door)
        import unicodedata
        variants = {'doubled spaces': reason.replace(' ', '  '),
                    'decomposed (NFD)': unicodedata.normalize('NFD', reason),
                    'a zero-width space': reason.replace('second', 'sec\u200bond'),
                    'a soft hyphen and a tab': reason.replace('administrator', 'admin\u00adistrator').replace(' ', '\t', 1)}
        for index, (label, variant) in enumerate(variants.items()):
            with self.subTest(variant=label):
                self.assertNotEqual(variant, reason)
                relative, door = self.declare(self.text(authority.ELEVATE, self.doctor, reason=variant),
                                              name=f'20261001-quillmd-admin-variant{index}.md')
                self.assertRefusedUnchanged('same act was already performed', authority.ELEVATE, relative,
                                            self.doctor.pk, door)

    def test_template_placeholders_and_missing_lines_refuse(self):
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor, reason='<FILL why>'))
        self.assertRefusedUnchanged('placeholders', authority.ELEVATE, relative, self.doctor.pk, door)
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor, approver_email=None),
                                      name='20261001-quillmd-admin-f.md')
        self.assertRefusedUnchanged('exactly one `approver_email:`', authority.ELEVATE, relative, self.doctor.pk, door)


class ResetAdministratorAuthenticator(DeclaredChangeFixture):
    def reset(self):
        relative, door = self.declare(self.text(authority.RESET, self.admin,
                                                reason='Lost phone; identity checked on a video call by the approver'))
        return self.perform(authority.RESET, relative, self.admin.pk, door), relative, door

    def test_positive_control_removes_every_authenticator_signs_out_and_audits(self):
        browser = Client()
        browser.force_login(self.admin)
        session = browser.session
        session['otp_device_id'] = self.admin_devices[0].persistent_id
        session.save()
        self.assertEqual(browser.get('/api/patients/').status_code, 200, 'the fixture session is not a working one')
        result, relative, door = self.reset()
        self.admin.refresh_from_db()
        self.assertFalse(TOTPDevice.objects.filter(user=self.admin).exists())
        self.assertEqual(self.admin.session_version, 1)
        signed_out = browser.get('/api/patients/')
        self.assertEqual((signed_out.status_code, signed_out.url.split('?')[0]), (302, '/login/'),
                         'a session opened with the old device survived')
        self.assertEqual(result['devices_removed'], 2)
        event = AuditEvent.objects.get(action='account.admin_mfa_reset')
        self.assertEqual((event.actor_id, event.target, event.details['devices_removed']),
                         (self.approver.pk, str(self.admin.pk), 2))
        self.assertTrue(event.details['sessions_invalidated'])
        self.assertTrue(self.approver_device.__class__.objects.filter(pk=self.approver_device.pk).exists())

    def test_a_clinical_account_is_not_reset_here(self):
        relative, door = self.declare(self.text(authority.RESET, self.doctor))
        self.assertRefusedUnchanged('not an active administrator', authority.RESET, relative, self.doctor.pk, door)

    def test_the_approver_cannot_reset_their_own_authenticator(self):
        relative, door = self.declare(self.text(authority.RESET, self.approver, approver=self.approver))
        self.assertRefusedUnchanged('same account', authority.RESET, relative, self.approver.pk, door)

    def test_an_approver_without_an_authenticator_cannot_approve(self):
        written = self.code_file()   # the approver's code, taken before the authenticator is gone
        TOTPDevice.objects.filter(user=self.approver).delete()
        relative, door = self.declare(self.text(authority.RESET, self.admin))
        self.assertRefusedUnchanged('no confirmed authenticator', authority.RESET, relative, self.admin.pk, door,
                                    code_file=written)

    def test_a_reset_declaration_is_used_once(self):
        self.reset()
        TOTPDevice.objects.create(user=self.admin, name='New phone', confirmed=True)
        relative = 'docs/foundation/mutations/' + NAME
        door = {'RULED_MUTATION_DECLARATION': relative,
                'RULED_MUTATION_DECL_COMMIT': self.git('log', '-1', '--format=%H', '--', relative).stdout.decode().strip()}
        self.assertRefusedUnchanged('already been used', authority.RESET, relative, self.admin.pk, door)

    def test_the_command_prints_no_secret_and_creates_no_key(self):
        old_keys = [device.key for device in self.admin_devices]
        relative, door = self.declare(self.text(authority.RESET, self.admin))
        out, err = io.StringIO(), io.StringIO()
        approver_code = Path(self.code_file()).read_text().strip()
        with patch.object(authority, 'REPOSITORY', self.root), patch.dict('os.environ', door):
            call_command('reset_admin_mfa', '--declaration', relative, '--target', str(self.admin.pk),
                         '--approver-code-file', str(self.codes / 'code'), stdout=out, stderr=err)
        printed = out.getvalue() + err.getvalue()
        result = json.loads(out.getvalue())
        self.assertTrue(result['enrolment_required_at_next_sign_in'])
        self.assertFalse(TOTPDevice.objects.filter(user=self.admin).exists(), 'the command created a key')
        for secret in old_keys + [PASSWORD, self.admin.password, self.admin.email, self.approver.email, approver_code,
                                  self.approver_device.key]:
            self.assertNotIn(secret, printed)
        self.assertNotIn('otpauth', printed)

    def test_the_command_refuses_as_a_command_error_without_changing_anything(self):
        relative, door = self.declare(self.text(authority.RESET, self.admin))
        before = self.state()
        with patch.object(authority, 'REPOSITORY', self.root), patch.dict('os.environ'):
            os.environ.pop('RULED_MUTATION_DECLARATION', None)
            os.environ.pop('RULED_MUTATION_DECL_COMMIT', None)
            with self.assertRaisesRegex(CommandError, 'Administrator change refused: .*ruled-mutation door'):
                call_command('reset_admin_mfa', '--declaration', relative, '--target', str(self.admin.pk),
                             '--approver-code-file', self.code_file(), stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual(self.state(), before)


@override_settings(QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class ReenrolmentAfterADeclaredReset(DeclaredChangeFixture):
    """The reset creates no key; the administrator enrols at their next password sign-in — on the administration
    surface, within the window, once."""

    def sign_in(self, client):
        return client.post('/login/', {'email': self.admin.email, 'password': PASSWORD, 'otp': ''})

    def reset(self):
        relative, door = self.declare(self.text(authority.RESET, self.admin))
        self.perform(authority.RESET, relative, self.admin.pk, door)

    @override_settings(ADMIN_SITE=True)
    def test_the_administrator_enrols_a_new_authenticator_and_reaches_the_console(self):
        self.reset()
        client = Client()
        response = self.sign_in(client)
        self.assertEqual((response.status_code, response.url), (302, '/mfa/'))
        self.assertEqual(client.get('/console/').url, '/mfa/', 'the console opened before enrolment')
        page = client.get('/mfa/')
        self.assertEqual(page.status_code, 200)
        device = TOTPDevice.objects.get(user=self.admin)
        self.assertFalse(device.confirmed)
        self.assertNotIn(device.key, [old.key for old in self.admin_devices], 'an old key came back')
        self.assertEqual(client.post('/mfa/', {'code': code(device)}).status_code, 302)
        self.assertEqual(client.get('/console/').status_code, 200)
        # Once a new authenticator is verified the window is closed: a password alone signs in no more.
        TOTPDevice.objects.filter(user=self.admin).update(confirmed=False)
        self.assertEqual(self.sign_in(Client()).status_code, 200)

    def setup_key(self, client):
        """The base32 secret the setup page shows this session (the otpauth URI's own), and its TOTP code now."""
        import html
        import re
        from base64 import b32decode
        from urllib.parse import parse_qs, urlsplit
        page = client.get('/mfa/')
        self.assertEqual(page.status_code, 200)
        uri = html.unescape(re.search(r'<textarea id="mfa-uri"[^>]*>(.*?)</textarea>', page.content.decode()).group(1))
        secret = parse_qs(urlsplit(uri).query)['secret'][0]
        key = b32decode(secret + '=' * (-len(secret) % 8))
        return secret, str(totp(key, step=30, t0=0, digits=6)).zfill(6)

    @override_settings(ADMIN_SITE=True)
    def test_a_second_window_session_never_learns_the_key_that_is_confirmed(self):
        """Refutation R4, the refuter's two-client scenario: two password-only sessions in the window were shown ONE
        setup key, so the holder of the other session signed in later with the key the administrator confirmed."""
        self.reset()
        other, legit = Client(), Client()
        self.assertEqual(self.sign_in(other).url, '/mfa/')
        other_secret, other_code = self.setup_key(other)
        self.assertEqual(self.sign_in(legit).url, '/mfa/')
        legit_secret, legit_code = self.setup_key(legit)
        self.assertNotEqual(other_secret, legit_secret, 'two window sessions were shown the same setup key')
        self.assertEqual(legit.post('/mfa/', {'code': legit_code}).status_code, 302)
        self.assertEqual(TOTPDevice.objects.filter(user=self.admin, confirmed=True).count(), 1)
        later = Client()
        refused = later.post('/login/', {'email': self.admin.email, 'password': PASSWORD, 'otp': other_code})
        self.assertEqual(refused.status_code, 200, 'the other session\'s key signs in')
        self.assertNotIn('_auth_user_id', later.session)
        self.assertEqual(later.get('/console/').status_code, 302)

    @override_settings(ADMIN_SITE=True)
    def test_every_other_session_ends_when_an_authenticator_is_confirmed(self):
        """Refutation R4: a window session opened before the enrolment survived it, and could still enrol and reach
        the console. Confirming a new authenticator now ends every other session of the account."""
        self.reset()
        stale, legit = Client(), Client()
        self.sign_in(stale)
        _, stale_code = self.setup_key(stale)
        self.sign_in(legit)
        _, legit_code = self.setup_key(legit)
        self.assertEqual(legit.post('/mfa/', {'code': legit_code}).url, '/console/')
        for path in ('/mfa/', '/console/'):
            with self.subTest(path=path):
                response = stale.get(path)
                self.assertEqual((response.status_code, response.url.split('?')[0]), (302, '/login/'))
        self.assertEqual(stale.post('/mfa/', {'code': stale_code}).url.split('?')[0], '/login/')
        # The confirming session continues, on the new session version.
        self.assertEqual(legit.get('/console/').status_code, 200)
        self.assertEqual(User.objects.get(pk=self.admin.pk).session_version, 2)

    @override_settings(ADMIN_SITE=True)
    def test_a_session_keeps_its_own_key_across_reloads(self):
        self.reset()
        client = Client()
        self.sign_in(client)
        first, _ = self.setup_key(client)
        again, current = self.setup_key(client)
        self.assertEqual(first, again, 'a reload of the same session changed its key')
        self.assertEqual(client.post('/mfa/', {'code': current}).url, '/console/')

    @override_settings(ADMIN_SITE=False)
    def test_the_doctor_surface_never_enrols_an_administrator(self):
        self.reset()
        response = self.sign_in(Client())
        self.assertEqual(response.status_code, 200)
        self.assertIn('Sign-in failed', response.content.decode())

    @override_settings(ADMIN_SITE=True)
    def test_the_window_closes(self):
        self.reset()
        later = timezone.now() + authority.ADMIN_REENROLMENT_WINDOW + timedelta(minutes=1)
        with patch.object(authority.timezone, 'now', return_value=later):
            response = self.sign_in(Client())
        self.assertEqual(response.status_code, 200)
        self.assertIn('Sign-in failed', response.content.decode())

    @override_settings(ADMIN_SITE=True)
    def test_control_an_administrator_without_a_declared_reset_still_cannot_sign_in_with_a_password(self):
        TOTPDevice.objects.filter(user=self.admin).delete()
        response = self.sign_in(Client())
        self.assertEqual(response.status_code, 200)
        self.assertIn('Sign-in failed', response.content.decode())


class ApproverPresence(DeclaredChangeFixture):
    """Refutation R7: the approver was named and never consulted. The approver's own current code is now required,
    verified against the approver's confirmed authenticator and consumed."""

    def declared(self, name=NAME, target=None):
        target = target or self.doctor
        return self.declare(self.text(authority.ELEVATE, target), name=name)

    def test_no_code_file_refuses(self):
        relative, door = self.declared()
        self.assertRefusedUnchanged('approver\'s presence is required', authority.ELEVATE, relative,
                                    self.doctor.pk, door, code_file='')

    def unthrottle(self):
        """The backoff a recorded failure starts has passed (django_otp: 1 s, 2 s, 4 s ... after each failure)."""
        TOTPDevice.objects.filter(user=self.approver).update(
            throttling_failure_timestamp=timezone.now() - timedelta(hours=1))

    def test_a_wrong_code_is_refused_recorded_and_the_act_rolled_back(self):
        """Refutation R7-a. This test asserted the opposite until round 2: a wrong code rolled the device's failure
        count back with the act, so codes could be guessed with no backoff and no trace (the refuter demonstrated it
        with this very test). The failure is now counted on the approver's device and recorded, the act is not."""
        relative, door = self.declared()
        wrong = '000000' if code(self.approver_device) != '000000' else '111111'
        self.assertAbsenceRecorded('did not verify', authority.ELEVATE, relative, self.doctor.pk, door,
                                   self.code_file(value=wrong), reason='approver_code_not_verified')
        self.assertFalse(User.objects.get(pk=self.doctor.pk).is_staff)

    def test_the_targets_or_another_administrators_code_is_not_the_approvers(self):
        relative, door = self.declared()
        for device in (self.doctor_device, self.admin_devices[0]):
            with self.subTest(device=device.name):
                self.unthrottle()
                self.assertAbsenceRecorded('did not verify', authority.ELEVATE, relative, self.doctor.pk, door,
                                           self.code_file(device=device), reason='approver_code_not_verified')

    def test_a_throttled_approver_is_refused_even_with_the_right_code(self):
        """The device's own throttle is honoured: inside the backoff a correct code is refused (and recorded, without
        counting again), and the act is not done; once the backoff has passed the same approver is present again."""
        relative, door = self.declared()
        wrong = '000000' if code(self.approver_device) != '000000' else '111111'
        self.assertAbsenceRecorded('did not verify', authority.ELEVATE, relative, self.doctor.pk, door,
                                   self.code_file(value=wrong), reason='approver_code_not_verified')
        self.assertAbsenceRecorded('throttled', authority.ELEVATE, relative, self.doctor.pk, door, self.code_file(),
                                   reason='approver_throttled', counted=False)
        self.assertFalse(User.objects.get(pk=self.doctor.pk).is_staff)
        self.unthrottle()
        self.perform(authority.ELEVATE, relative, self.doctor.pk, door)
        self.assertTrue(User.objects.get(pk=self.doctor.pk).is_staff)
        self.assertEqual(TOTPDevice.objects.get(pk=self.approver_device.pk).throttling_failure_count, 0)

    def test_the_recorded_failure_survives_the_refusal_in_its_own_transaction(self):
        """The record is committed on its own: an act transaction that rolls back does not take it with it."""
        from django.db import connection
        relative, door = self.declared()
        wrong = '000000' if code(self.approver_device) != '000000' else '111111'
        seen = []
        real = authority.record_absence

        def record(*args, **kwargs):
            seen.append(len(connection.savepoint_ids))
            return real(*args, **kwargs)
        outside = len(connection.savepoint_ids)
        with patch.object(authority, 'record_absence', record):
            self.assertAbsenceRecorded('did not verify', authority.ELEVATE, relative, self.doctor.pk, door,
                                       self.code_file(value=wrong), reason='approver_code_not_verified')
        # Called once the act's own transaction has ended: no transaction of perform()'s is open around it.
        self.assertEqual(seen, [outside])

    def test_a_used_code_is_refused_the_second_time(self):
        relative, door = self.declared()
        used = self.code_file()
        self.perform(authority.ELEVATE, relative, self.doctor.pk, door, code_file=used)
        other = User.objects.create_user(username='third', email='third@synthetic.invalid', password=PASSWORD,
                                         verified_at=timezone.now())
        TOTPDevice.objects.create(user=other, name='Third', confirmed=True)
        relative, door = self.declared(name='20261001-quillmd-admin-third.md', target=other)
        self.assertAbsenceRecorded('did not verify', authority.ELEVATE, relative, other.pk, door, used,
                                   reason='approver_code_not_verified')

    def test_a_code_file_others_can_read_or_a_link_refuses(self):
        relative, door = self.declared()
        good = self.code_file()
        link = self.codes / 'link'
        link.symlink_to(good)
        cases = {'group-readable': self.code_file(mode=0o640, name='group'),
                 'world-readable': self.code_file(mode=0o644, name='world'),
                 'a symbolic link': str(link), 'missing': str(self.codes / 'absent'),
                 'not a code': self.code_file(value='12345', name='short'),
                 'more than a code': self.code_file(value='123456 and more', name='long')}
        for label, path in cases.items():
            with self.subTest(case=label):
                self.assertRefusedUnchanged('approver code file', authority.ELEVATE, relative, self.doctor.pk, door,
                                            code_file=path)

    def test_a_link_anywhere_in_the_path_is_refused(self):
        """Refutation R7-b: lstat checked only the last component, so a directory symlink in the path passed."""
        relative, door = self.declared()
        real = self.codes / 'real'
        real.mkdir()
        self.code_file(name='real/code')
        (self.codes / 'via').symlink_to(real)
        (self.codes / 'deeper').mkdir()
        (self.codes / 'deeper' / 'via').symlink_to(real)
        for label, path in (('a directory link in the path', str(self.codes / 'via' / 'code')),
                            ('a link two levels up', str(self.codes / 'deeper' / 'via' / 'code'))):
            with self.subTest(case=label):
                self.assertRefusedUnchanged('approver code file', authority.ELEVATE, relative, self.doctor.pk, door,
                                            code_file=path)
        # Positive control: the same file by its real path is presence.
        self.perform(authority.ELEVATE, relative, self.doctor.pk, door, code_file=str(real / 'code'))
        self.assertTrue(User.objects.get(pk=self.doctor.pk).is_staff)

    def swapped_at_open(self, replacement):
        """Patch os.open so that the code file is replaced by `replacement` (a path) at the moment it is opened —
        after any check made on the path beforehand, as a racing writer would."""
        real_open = os.open

        def swapping_open(path, flags, *args, **kwargs):
            if os.path.basename(os.fsdecode(path)) == 'code' and os.path.exists(replacement):
                os.replace(replacement, self.codes / 'code')
            return real_open(path, flags, *args, **kwargs)
        return patch.object(authority.os, 'open', swapping_open)

    def test_the_open_descriptor_is_judged_not_the_path_checked_earlier(self):
        """Refutation R7-b: the file was lstat-ed, then opened by path, and the descriptor never fstat-ed: a swap in
        between passed the 0600/owner checks."""
        relative, door = self.declared()
        path = self.code_file()
        readable = self.codes / 'readable'
        readable.write_text(Path(path).read_text())
        readable.chmod(0o644)
        with self.swapped_at_open(str(readable)):
            self.assertRefusedUnchanged('approver code file', authority.ELEVATE, relative, self.doctor.pk, door,
                                        code_file=path)

    def refused_without_hanging(self, path, fifo_at, swap=None):
        """approver_code(path) in a thread: it must refuse within 10 s. A blocked open is released by opening the FIFO
        at `fifo_at` for writing, and reported as the failure it is."""
        import threading
        outcome = {}

        def attempt():
            try:
                if swap:
                    with self.swapped_at_open(swap):
                        authority.approver_code(path)
                else:
                    authority.approver_code(path)
                outcome['result'] = 'accepted'
            except Refused as exc:
                outcome['result'] = str(exc)
        worker = threading.Thread(target=attempt, daemon=True)
        worker.start()
        worker.join(10)
        if worker.is_alive():
            os.close(os.open(fifo_at, os.O_WRONLY | os.O_NONBLOCK))
            worker.join(10)
            self.fail('opening the approver code file blocked on a FIFO')
        self.assertIn('approver code file', outcome['result'])

    def test_a_fifo_is_refused_without_hanging(self):
        fifo = self.codes / 'fifo'
        os.mkfifo(fifo, 0o600)
        self.refused_without_hanging(str(fifo), fifo)

    def test_a_fifo_swapped_in_at_open_is_refused_without_hanging(self):
        path = self.code_file()
        fifo = self.codes / 'pipe'
        os.mkfifo(fifo, 0o600)
        self.refused_without_hanging(path, self.codes / 'code', swap=str(fifo))

    def second_phone(self):
        return TOTPDevice.objects.create(user=self.approver, name='Approver second phone', confirmed=True)

    def test_approvals_with_the_second_device_never_count_against_the_first(self):
        """Round-3 R3-1, a real lockout: with two confirmed authenticators, an approval with the SECOND device's code
        tried the first device too, and its failed verify_token committed a failure inside the successful act — five
        approvals left the first phone throttled for 16 s and sign-in (which uses the first device) refused its
        correct code. A successful act leaves every device but the one that verified exactly as it was."""
        second = self.second_phone()
        first_before = TOTPDevice.objects.filter(pk=self.approver_device.pk).values(
            'throttling_failure_count', 'throttling_failure_timestamp', 'last_t').get()
        for round_ in range(3):
            target = User.objects.create_user(username=f'roster-{round_}', email=f'roster-{round_}@synthetic.invalid',
                                              password=PASSWORD, verified_at=timezone.now())
            TOTPDevice.objects.create(user=target, name='Target', confirmed=True)
            relative, door = self.declare(self.text(authority.ELEVATE, target),
                                          name=f'20261001-quillmd-admin-round{round_}.md')
            TOTPDevice.objects.filter(pk=second.pk).update(last_t=-1)   # the next step's code, as half a minute later
            result = self.perform(authority.ELEVATE, relative, target.pk, door, code_file=self.code_file(device=second))
            self.assertEqual(result['approver_presence'], 'verified')
            self.assertTrue(User.objects.get(pk=target.pk).is_staff)
        self.assertEqual(TOTPDevice.objects.filter(pk=self.approver_device.pk).values(
            'throttling_failure_count', 'throttling_failure_timestamp', 'last_t').get(), first_before)
        events = AuditEvent.objects.filter(action='account.admin_elevated').values_list('details__approver_device',
                                                                                         flat=True)
        self.assertEqual(set(events), {second.persistent_id})
        # And the approver signs in with the FIRST phone's correct code, as sign-in (views.login_view) checks it.
        with override_settings(ADMIN_SITE=True, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES):
            self.approver_device.refresh_from_db()
            response = Client().post('/login/', {'email': self.approver.email, 'password': PASSWORD,
                                                 'otp': code(self.approver_device)})
        self.assertEqual((response.status_code, response.url), (302, '/console/'))

    def test_a_wrong_code_counts_on_every_device_it_was_tried_against(self):
        """Round-3 m5: with one device, counting only the first passed. Two devices, both counted."""
        second = self.second_phone()
        relative, door = self.declared()
        wrong = next(value for value in ('000000', '111111', '222222')
                     if value not in (code(self.approver_device), code(second)))
        self.assertAbsenceRecorded('did not verify', authority.ELEVATE, relative, self.doctor.pk, door,
                                   self.code_file(value=wrong), reason='approver_code_not_verified')

    def test_a_file_swapped_after_the_open_is_judged_by_what_was_opened(self):
        """Round-3 m1: with the swap made BEFORE the open, a check of the path after the open still saw the bad file.
        Here the path is replaced AFTER the descriptor is opened: the descriptor holds a mode-0644 file, the path a
        0600 one. Only a check of the open descriptor refuses."""
        relative, door = self.declared()
        good = Path(self.code_file())
        readable, spare = self.codes / 'readable', self.codes / 'spare'
        readable.write_text(good.read_text())
        readable.chmod(0o644)
        spare.write_text(good.read_text())
        spare.chmod(0o600)
        os.replace(readable, good)
        real_open = os.open

        def open_then_swap(path, flags, *args, **kwargs):
            descriptor = real_open(path, flags, *args, **kwargs)
            if os.path.basename(os.fsdecode(path)) == 'code' and spare.exists():
                os.replace(spare, good)
            return descriptor
        with patch.object(authority.os, 'open', open_then_swap):
            self.assertRefusedUnchanged('approver code file', authority.ELEVATE, relative, self.doctor.pk, door,
                                        code_file=str(good))
        self.assertEqual(good.stat().st_mode & 0o777, 0o600, 'the swap did not happen; the test proves nothing')

    def test_a_search_only_directory_is_enough_and_refusals_name_their_cause(self):
        """Round-3 R3-4: the walk opened each directory for READING, which the kernel does not need to reach a file:
        a 0600 file in a 0300 (search-only) directory was refused, with a message blaming links. The walk opens
        directories by path only (O_PATH), and each refusal names its cause."""
        relative, door = self.declared()
        hidden = self.codes / 'search-only'
        hidden.mkdir()
        path = self.code_file(name='search-only/code')
        hidden.chmod(0o300)
        self.addCleanup(hidden.chmod, 0o700)
        closed = self.codes / 'closed'
        closed.mkdir()
        self.code_file(name='closed/code')
        closed.chmod(0o600)
        self.addCleanup(closed.chmod, 0o700)
        (self.codes / 'via').symlink_to(self.codes / 'closed')
        for label, given, cause in (('missing', str(self.codes / 'absent'), 'does not exist'),
                                    ('a link in the path', str(self.codes / 'via' / 'code'), 'symbolic link'),
                                    ('a directory without search permission', str(closed / 'code'), 'permission')):
            with self.subTest(case=label):
                self.assertRefusedUnchanged(cause, authority.ELEVATE, relative, self.doctor.pk, door, code_file=given)
        self.perform(authority.ELEVATE, relative, self.doctor.pk, door, code_file=path)
        self.assertTrue(User.objects.get(pk=self.doctor.pk).is_staff)

    def test_positive_control_the_approvers_current_code_in_a_0600_file_is_presence(self):
        relative, door = self.declared()
        result = self.perform(authority.ELEVATE, relative, self.doctor.pk, door)
        self.assertEqual(result['approver_presence'], 'verified')
        self.assertTrue(User.objects.get(pk=self.doctor.pk).is_staff)


@override_settings(QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class RepeatsAreNotCopies(DeclaredChangeFixture):
    """Round-3 R3-2: keyed on the act alone, a legitimate repeat — the same administrator reset again by the same
    approver after re-enrolling, with the same templated reason — was refused forever, naming the new declaration.
    Single use now binds the act to the target state it left: the SAME declaration is always refused; another
    declaration for the same act is refused as a copy while the target is still as that act left it, and performed once
    the target has changed (re-enrolment). The message says which."""

    REASON = 'Lost phone; identity checked on a video call by the approver'

    def reset(self, name):
        relative, door = self.declare(self.text(authority.RESET, self.admin, reason=self.REASON), name=name)
        TOTPDevice.objects.filter(pk=self.approver_device.pk).update(last_t=-1)   # a fresh code each time
        return relative, door

    def reenrol(self):
        """The administrator re-enrols through the real pages: password-only sign-in in the window, /mfa/."""
        import html
        import re
        from base64 import b32decode
        from urllib.parse import parse_qs, urlsplit
        client = Client()
        with override_settings(ADMIN_SITE=True):
            self.assertEqual(client.post('/login/', {'email': self.admin.email, 'password': PASSWORD,
                                                     'otp': ''}).url, '/mfa/')
            page = client.get('/mfa/').content.decode()
            uri = html.unescape(re.search(r'<textarea id="mfa-uri"[^>]*>(.*?)</textarea>', page).group(1))
            secret = parse_qs(urlsplit(uri).query)['secret'][0]
            key = b32decode(secret + '=' * (-len(secret) % 8))
            self.assertEqual(client.post('/mfa/', {'code': str(totp(key, step=30, t0=0, digits=6)).zfill(6)}).url,
                             '/console/')

    def test_a_copy_is_refused_and_a_genuine_repeat_after_reenrolment_is_performed(self):
        first, door = self.reset('20261001-quillmd-admin-reset-1.md')
        self.perform(authority.RESET, first, self.admin.pk, door)
        second, second_door = self.reset('20261001-quillmd-admin-reset-2.md')
        refused = None
        try:
            self.perform(authority.RESET, second, self.admin.pk, second_door)
        except Refused as exc:
            refused = str(exc)
        self.assertIsNotNone(refused, 'a copy made before anything changed was performed')
        self.assertIn('same act was already performed', refused)
        self.assertIn(first, refused, 'the copy refusal names the declaration that performed the act')
        self.assertNotIn(second, refused, 'the copy refusal names the new declaration as if it had been used')
        self.reenrol()
        # The very same first declaration stays used, whatever has changed since.
        self.assertRefusedUnchanged('already been used', authority.RESET, first, self.admin.pk, door)
        # A new declaration for the same act, after re-enrolment: a genuine repeat.
        TOTPDevice.objects.filter(pk=self.approver_device.pk).update(last_t=-1)
        result = self.perform(authority.RESET, second, self.admin.pk, second_door)
        self.assertEqual(result['devices_removed'], 1)
        self.assertEqual(AuditEvent.objects.filter(action='account.admin_mfa_reset').count(), 2)

    def test_the_approver_is_part_of_the_act(self):
        """Round-3 m3: the same reset approved by ANOTHER administrator, with her own present code, is a decision of
        its own and is performed; dropping the approver from the act would refuse it as a copy."""
        other = User.objects.create_user(username='approver-two', email='approver-two@synthetic.invalid',
                                         password=PASSWORD, verified_at=timezone.now(), is_staff=True)
        other_device = TOTPDevice.objects.create(user=other, name='Approver two', confirmed=True)
        first, door = self.reset('20261001-quillmd-admin-reset-1.md')
        self.perform(authority.RESET, first, self.admin.pk, door)
        relative, door = self.declare(self.text(authority.RESET, self.admin, approver=other, reason=self.REASON),
                                      name='20261001-quillmd-admin-reset-other.md')
        result = self.perform(authority.RESET, relative, self.admin.pk, door,
                              code_file=self.code_file(device=other_device))
        self.assertEqual(result['approver'], str(other.pk))


# ---------------------------------------------------------------------------------------------------------------------
# The production door (refutation R5): bootstrap_first_admin's operator authority, never a git checkout.
# ---------------------------------------------------------------------------------------------------------------------

RELEASE_SHA = 'e' * 40
PROFILE_SHA = 'ab' * 32
RECEIPT = '/var/lib/quillmd-bootstrap/receipt.json'


class _RootOs:
    """os, as production_operator sees it on the production host: root. Every other attribute is the real os."""

    def __getattr__(self, name):
        return getattr(os, name)

    @staticmethod
    def geteuid():
        return 0


def production_declaration(operation, target, approver, reason='Synthetic production roster change, checked by phone',
                           **override):
    from datetime import datetime, timezone as tz
    declaration = {'format': 1, 'operation': authority.PRODUCTION_OPERATION, 'actions': [operation],
                   'release_sha': RELEASE_SHA, 'profile_sha256': PROFILE_SHA,
                   'expires_at': (datetime.now(tz.utc) + timedelta(hours=1)).isoformat(),
                   'database_arn': 'arn:aws:rds:us-east-1:123456789012:db:quillmd-production',
                   'database_resource_id': 'db-SYNTHETIC',
                   'kms_key_arn': 'arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012',
                   'target': {'id': str(target.pk), 'email': target.email},
                   'approver': {'id': str(approver.pk), 'email': approver.email}, 'reason': reason}
    declaration.update(override)
    return declaration


def production_door(app_root, declaration_path=None, commit='d' * 40):
    """The production host's facts this test cannot have — root, the bootstrap receipt, the reviewed profile, the
    pinned CA bundle, the RDS description and the TLS connection — stubbed; everything else is the real door:
    production_operator.authority reads the JSON the door names and binds format, operation, profile, release,
    receipt and expiry; production_context checks the action and the application profile. `declaration_path=None`
    is the door NOT opened."""
    from contextlib import ExitStack
    from decimal import Decimal
    from types import SimpleNamespace
    from django.conf import settings
    from core.management.commands import bootstrap_first_admin as first
    from ops import deployment_profile, production_operator as operator
    profile = SimpleNamespace(sha256=PROFILE_SHA, app_root=Path(app_root), state_root=settings.STATE_DIR,
                              ca_bundle=Path('/synthetic/ca.pem'), ca_bundle_sha256='cd' * 32)

    def private_json(path):
        if str(path) != RECEIPT:
            raise AssertionError('unexpected private file ' + str(path))
        return {'release_sha': RELEASE_SHA, 'profile_sha256': PROFILE_SHA}
    door = {'QUILLMD_DEPLOYMENT_PROFILE': 'production'}
    if declaration_path is not None:
        door.update(RULED_MUTATION_DECLARATION=str(declaration_path), RULED_MUTATION_DECL_COMMIT=commit)
    stack = ExitStack()
    stack.enter_context(patch.object(operator, 'os', _RootOs()))
    stack.enter_context(patch.object(operator, 'private_json', private_json))
    stack.enter_context(patch.object(deployment_profile, 'load_production', return_value=profile))
    stack.enter_context(patch.object(first, 'describe_target', return_value={}))
    stack.enter_context(patch.object(first, 'application_database', return_value=None))
    stack.enter_context(patch('ops.service_launcher.verified_ca_bundle', return_value=None))
    environ = stack.enter_context(patch.dict(os.environ, door))
    for name in ('RULED_MUTATION_DECLARATION', 'RULED_MUTATION_DECL_COMMIT'):
        if declaration_path is None:
            environ.pop(name, None)
    stack.enter_context(override_settings(SYNTHETIC_ONLY=False, QUILLMD_REGISTRATION='invite',
                                          QUILLMD_MFA_REQUIRED_ALL=True, QUILLMD_WELCOME_CREDIT=Decimal('0'),
                                          RELEASE_SHA=RELEASE_SHA))
    return stack


class ProductionDoor(DeclaredChangeFixture):
    def write(self, declaration, name='administrators.json'):
        path = self.codes / name
        path.write_text(json.dumps(declaration))
        return path

    def act(self, operation, path, target, door_path='same', code_file='current'):
        door_path = path if door_path == 'same' else door_path
        with production_door(authority.REBUILD, door_path):
            return authority.perform(operation, str(path), target,
                                     self.code_file() if code_file == 'current' else code_file)

    def refused_unchanged(self, message, operation, path, target, **kwargs):
        before = self.state()
        with self.assertRaisesRegex(Refused, message):
            self.act(operation, path, target, **kwargs)
        self.assertEqual(self.state(), before)

    def test_positive_control_elevation_through_the_production_door(self):
        path = self.write(production_declaration(authority.ELEVATE, self.doctor, self.approver))
        result = self.act(authority.ELEVATE, path, self.doctor.pk)
        self.assertTrue(User.objects.get(pk=self.doctor.pk).is_staff)
        event = AuditEvent.objects.get(action='account.admin_elevated')
        self.assertEqual((event.actor_id, event.details['door'], event.details['declaration_commit'],
                          event.details['release_sha'], event.details['approver_presence']),
                         (self.approver.pk, 'production', 'd' * 40, RELEASE_SHA, 'authenticator code verified'))
        self.assertEqual(result['declaration'], 'administrators.json')

    def test_positive_control_reset_through_the_production_door(self):
        path = self.write(production_declaration(authority.RESET, self.admin, self.approver))
        self.act(authority.RESET, path, self.admin.pk)
        self.assertFalse(TOTPDevice.objects.filter(user=self.admin).exists())
        self.assertEqual(User.objects.get(pk=self.admin.pk).session_version, 1)

    def test_without_the_door_nothing_changes(self):
        path = self.write(production_declaration(authority.ELEVATE, self.doctor, self.approver))
        self.refused_unchanged('production door: declaration_commit', authority.ELEVATE, path, self.doctor.pk,
                               door_path=None)

    def test_the_production_profile_never_falls_back_to_a_repository_declaration(self):
        relative, door = self.declare(self.text(authority.ELEVATE, self.doctor))
        before = self.state()
        with production_door(authority.REBUILD, None), patch.dict(os.environ, door):
            with self.assertRaisesRegex(Refused, 'production door'):
                authority.perform(authority.ELEVATE, relative, self.doctor.pk, self.code_file(),
                                  repository=self.root, environ=door)
        self.assertEqual(self.state(), before)

    def test_each_declaration_fault_refuses(self):
        from datetime import datetime, timezone as tz
        good = production_declaration(authority.ELEVATE, self.doctor, self.approver)
        cases = [
            ('production door: declaration_scope', dict(good, operation='first_admin')),
            ('production door: declaration_scope', dict(good, profile_sha256='ff' * 32)),
            ('production door: declaration_expired',
             dict(good, expires_at=(datetime.now(tz.utc) - timedelta(minutes=1)).isoformat())),
            ('production door: installed_release', dict(good, release_sha='c' * 40)),
            ('production door: declaration_action', dict(good, actions=[authority.RESET])),
            ('exactly one action', dict(good, actions=[authority.ELEVATE, authority.RESET])),
            ('another target account', dict(good, target={'id': str(self.admin.pk), 'email': self.admin.email})),
            ('same account', dict(good, approver={'id': str(self.doctor.pk), 'email': self.doctor.email})),
            ('approver must be', dict(good, approver={'id': str(self.approver.pk)})),
            ('at least 12 characters', dict(good, reason='short')),
        ]
        for index, (message, declaration) in enumerate(cases):
            with self.subTest(message=message, index=index):
                self.refused_unchanged(message, authority.ELEVATE, self.write(declaration, f'd{index}.json'),
                                       self.doctor.pk)

    def test_the_declaration_argument_must_be_the_file_the_door_opened(self):
        named = self.write(production_declaration(authority.ELEVATE, self.doctor, self.approver))
        other = self.write(production_declaration(authority.ELEVATE, self.doctor, self.approver), 'other.json')
        self.refused_unchanged('another file than', authority.ELEVATE, other, self.doctor.pk, door_path=named)

    def test_a_reserialized_or_reissued_copy_of_a_used_declaration_is_refused(self):
        """Refutation R5-a: single use was keyed on the declaration's BYTES, so the same JSON with other whitespace, or
        its keys in another order, was accepted again. It is keyed on the act now — operation, target, approver and
        reason, canonically serialized — so a re-serialized copy, or one re-issued with a new expiry, is refused."""
        from datetime import datetime, timezone as tz
        declaration = production_declaration(authority.ELEVATE, self.doctor, self.approver)
        self.act(authority.ELEVATE, self.write(declaration), self.doctor.pk)
        reordered = dict(reversed(list(declaration.items())))
        later = dict(declaration, expires_at=(datetime.now(tz.utc) + timedelta(hours=2)).isoformat())
        # The same declaration, however serialized, is the same declaration: refused whatever happens later.
        for index, text in enumerate((json.dumps(declaration, indent=2), json.dumps(reordered, separators=(',', ':')),
                                      ' ' + json.dumps(declaration) + '\n\n')):
            with self.subTest(copy=index):
                path = self.codes / f'copy{index}.json'
                path.write_text(text)
                self.refused_unchanged('already been used', authority.ELEVATE, path, self.doctor.pk)
        # A re-issued declaration (new expiry) for the same act, while the target is as that act left it: a copy.
        self.refused_unchanged('same act was already performed', authority.ELEVATE, self.write(later, 'later.json'),
                               self.doctor.pk)
        # Round-3 R3-2, the positive control: once the target's state has changed (demoted, by whatever means), the
        # re-issued declaration is a genuine repeat and is performed; the original one stays used. The approver's
        # current code was consumed by the first act; the next one is the next step's, as half a minute later.
        User.objects.filter(pk=self.doctor.pk).update(is_staff=False)
        TOTPDevice.objects.filter(pk=self.approver_device.pk).update(last_t=-1)
        self.refused_unchanged('already been used', authority.ELEVATE, self.codes / 'copy0.json', self.doctor.pk)
        self.act(authority.ELEVATE, self.codes / 'later.json', self.doctor.pk)
        self.assertTrue(User.objects.get(pk=self.doctor.pk).is_staff)

    def test_a_production_declaration_is_used_once_and_needs_the_approver(self):
        path = self.write(production_declaration(authority.ELEVATE, self.doctor, self.approver))
        self.refused_unchanged('approver\'s presence', authority.ELEVATE, path, self.doctor.pk, code_file=None)
        self.act(authority.ELEVATE, path, self.doctor.pk)
        User.objects.filter(pk=self.doctor.pk).update(is_staff=False)
        self.refused_unchanged('already been used', authority.ELEVATE, path, self.doctor.pk)


from django.test import TransactionTestCase  # noqa: E402

DRIVER = r'''
import io, json, os, sys
release, spec = sys.argv[1], json.loads(sys.argv[2])
sys.path.insert(0, release)
os.chdir(release)
os.environ['DJANGO_SETTINGS_MODULE'] = 'quillmd.settings'
import django
django.setup()
from django.core.management import call_command
from django.core.management.base import CommandError
from core.tests.test_admin_authority import production_door
import core.admin_authority
out = io.StringIO()
argv = [spec['command'], '--declaration', spec['declaration'], '--target', spec['target'],
        '--approver-code-file', spec['code_file']]
try:
    if spec['door'] == 'production':
        with production_door(release, spec['declaration']):
            call_command(*argv, stdout=out)
    elif spec['door'] == 'production-not-opened':
        with production_door(release, None):
            call_command(*argv, stdout=out)
    else:
        call_command(*argv, stdout=out)
    print(json.dumps({'ok': True, 'module': core.admin_authority.__file__, 'out': json.loads(out.getvalue())}))
except CommandError as exc:
    print(json.dumps({'ok': False, 'module': core.admin_authority.__file__, 'error': str(exc)}))
'''


@override_settings(STORAGES=STORAGES)
class ReleaseShapedInstall(TransactionTestCase):
    """Refutation R5, end to end: a copy of what a release carries — rebuild/ alone, as `git archive` of the commit
    builds it (tracked files, plus this tree's not-yet-committed ones, no ignored file) — runs each command in a process
    of its own through the production door, and refuses without it. Its own code is what runs: the door checks that
    production_operator lives in the profile's app_root, which is the copy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.release = Path(tempfile.mkdtemp(prefix='quillmd-release-'))
        listed = subprocess.run(['git', '-C', str(authority.REPOSITORY), 'ls-files', '-z', '--cached', '--others',
                                 '--exclude-standard', '--', 'rebuild'], capture_output=True, check=True).stdout
        for relative in filter(None, listed.decode().split('\0')):
            source = authority.REPOSITORY / relative
            if source.is_file() and not source.is_symlink():
                target = cls.release / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        cls.app = cls.release / 'rebuild'

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.release, True)
        super().tearDownClass()

    def setUp(self):
        now = timezone.now()
        self.approver = User.objects.create_user(username='r-approver', email='r-approver@synthetic.invalid',
                                                 password=PASSWORD, verified_at=now, is_staff=True)
        self.approver_device = TOTPDevice.objects.create(user=self.approver, name='Approver', confirmed=True)
        self.second_approver = User.objects.create_user(username='r-approver-2', email='r-approver-2@synthetic.invalid',
                                                        password=PASSWORD, verified_at=now, is_staff=True)
        self.second_device = TOTPDevice.objects.create(user=self.second_approver, name='Approver 2', confirmed=True)
        self.doctor = User.objects.create_user(username='r-doctor', email='r-doctor@synthetic.invalid',
                                               password=PASSWORD, verified_at=now)
        TOTPDevice.objects.create(user=self.doctor, name='Doctor', confirmed=True)
        self.admin = User.objects.create_user(username='r-admin', email='r-admin@synthetic.invalid',
                                              password=PASSWORD, verified_at=now, is_staff=True)
        TOTPDevice.objects.create(user=self.admin, name='Old phone', confirmed=True)
        self.files = Path(tempfile.mkdtemp(prefix='release-door-'))
        self.addCleanup(shutil.rmtree, self.files, True)

    def run_command(self, command, target, door, declaration, device=None):
        import sys
        from django.db import connection
        device = device or self.approver_device
        code_file = self.files / ('code-' + command)
        device.refresh_from_db()
        code_file.write_text(code(device) + '\n')
        code_file.chmod(0o600)
        driver = self.files / 'driver.py'
        driver.write_text(DRIVER)
        env = {k: v for k, v in os.environ.items() if k not in ('DJANGO_SETTINGS_MODULE',)
               and not k.startswith('RULED_MUTATION_')}
        env.update(QUILLMD_DB_NAME=connection.settings_dict['NAME'], QUILLMD_ENV_MANAGED='1')
        spec = {'command': command, 'declaration': str(declaration), 'target': str(target.pk),
                'code_file': str(code_file), 'door': door}
        done = subprocess.run([sys.executable, '-B', str(driver), str(self.app), json.dumps(spec)], env=env,
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_the_release_is_rebuild_alone(self):
        self.assertEqual(sorted(p.name for p in self.release.iterdir()), ['rebuild'])
        self.assertFalse((self.app / '.git').exists() or (self.release / '.git').exists())
        self.assertTrue((self.app / 'core' / 'admin_authority.py').is_file())
        self.assertFalse((self.app / '.env').exists())

    def test_each_command_runs_through_the_production_door_from_the_release(self):
        # One approver per act: an act consumes the approver's current code, as it must.
        for command, operation, target, approver, device in (
                ('elevate_additional_admin', authority.ELEVATE, self.doctor, self.approver, self.approver_device),
                ('reset_admin_mfa', authority.RESET, self.admin, self.second_approver, self.second_device)):
            with self.subTest(command=command):
                path = self.files / (command + '.json')
                path.write_text(json.dumps(production_declaration(operation, target, approver)))
                done = self.run_command(command, target, 'production', path, device=device)
                self.assertTrue(done['ok'], done)
                self.assertTrue(done['module'].startswith(str(self.app)), done['module'])
                self.assertEqual(done['out']['door'], 'production')
        self.assertTrue(User.objects.get(pk=self.doctor.pk).is_staff)
        self.assertFalse(TOTPDevice.objects.filter(user=self.admin).exists())
        self.assertEqual(sorted(AuditEvent.objects.filter(action__in=authority.ACTIONS.values())
                                .values_list('action', 'actor__username', 'details__door')),
                         [('account.admin_elevated', 'r-approver', 'production'),
                          ('account.admin_mfa_reset', 'r-approver-2', 'production')])

    def test_the_release_refuses_without_the_door_and_has_no_repository_door(self):
        path = self.files / 'elevate.json'
        path.write_text(json.dumps(production_declaration(authority.ELEVATE, self.doctor, self.approver)))
        before = list(User.objects.order_by('pk').values_list('pk', 'is_staff', 'session_version'))
        for door, message in (('production-not-opened', 'production door: declaration_commit'),
                              ('repository', 'docs/foundation/mutations')):
            with self.subTest(door=door):
                done = self.run_command('elevate_additional_admin', self.doctor, door, path)
                self.assertFalse(done['ok'], done)
                self.assertIn(message, done['error'])
        self.assertEqual(list(User.objects.order_by('pk').values_list('pk', 'is_staff', 'session_version')), before)
        self.assertFalse(AuditEvent.objects.filter(action__in=authority.ACTIONS.values()).exists())


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, QUILLMD_MFA_REQUIRED_ALL=True, STORAGES=STORAGES)
class ClinicianEnrolmentKeepsWorking(TestCase):
    """The R4 repair on the clinician path (QUILLMD_MFA_REQUIRED_ALL): the manual key and the QR are this session's,
    a reload keeps them, a wrong code keeps them, and confirming ends the clinician's other sessions only."""

    def setUp(self):
        from core.models import Department, Membership, Organization
        self.clinician = User.objects.create_user(username='enrol-clinician', email='enrol-clinician@synthetic.invalid',
                                                  password=PASSWORD, verified_at=timezone.now())
        department = Department.objects.create(organization=Organization.objects.create(name='Enrol clinic'),
                                               name='Enrol')
        Membership.objects.create(user=self.clinician, department=department, role='clinician')

    def sign_in(self, client):
        response = client.post('/login/', {'email': self.clinician.email, 'password': PASSWORD, 'otp': ''})
        self.assertEqual(response.url, '/mfa/')

    def test_reload_and_a_wrong_code_keep_the_manual_key_and_the_right_code_confirms(self):
        from base64 import b32encode
        client = Client()
        self.sign_in(client)
        first = client.get('/mfa/').context['secret']
        self.assertEqual(client.get('/mfa/').context['secret'], first)
        wrong = client.post('/mfa/', {'code': '000000'})
        self.assertEqual(wrong.status_code, 200)
        self.assertEqual(wrong.context['secret'], first)
        device = TOTPDevice.objects.get(user=self.clinician)
        self.assertEqual(b32encode(device.bin_key).decode().rstrip('='), first.replace(' ', ''))
        TOTPDevice.objects.filter(pk=device.pk).update(throttling_failure_count=0, throttling_failure_timestamp=None)
        self.assertEqual(client.post('/mfa/', {'code': code(device)}).url, '/')
        self.assertEqual(client.get('/').status_code, 200)

    def test_confirming_ends_the_clinicians_other_sessions_and_nobody_elses(self):
        phone, laptop, colleague = Client(), Client(), Client()
        self.sign_in(phone)
        phone.get('/mfa/')
        self.sign_in(laptop)
        laptop.get('/mfa/')
        other = User.objects.create_user(username='enrol-colleague', email='enrol-colleague@synthetic.invalid',
                                         password=PASSWORD, verified_at=timezone.now())
        colleague.force_login(other)
        before = colleague.get('/mfa/').status_code
        device = TOTPDevice.objects.get(user=self.clinician)
        self.assertEqual(laptop.post('/mfa/', {'code': code(device)}).url, '/')
        self.assertEqual(laptop.get('/').status_code, 200)
        self.assertEqual(phone.get('/').url.split('?')[0], '/login/')
        self.assertEqual(colleague.get('/mfa/').status_code, before)
