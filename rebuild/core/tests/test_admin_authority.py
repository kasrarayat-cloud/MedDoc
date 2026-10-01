"""Declared administrator changes (inventory 7A, F2): a second administrator, and an administrator's authenticator
reset — core.admin_authority, `manage.py elevate_additional_admin`, `manage.py reset_admin_mfa`.

Every refusal arm asserts NOTHING CHANGED: the accounts' staff flags and session versions, every authenticator row and
the audit trail are compared whole, before and after. The declarations live in a scratch git checkout, committed the
way scripts/run-ruled-mutation.sh requires, and the door's two variables are passed explicitly.
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
from ops.provider_campaign import Refused

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

    def perform(self, operation, relative, target, environ):
        return authority.perform(operation, relative, target, repository=self.root, environ=environ)

    def state(self):
        users = list(User.objects.order_by('pk').values_list('pk', 'is_staff', 'is_superuser', 'is_active',
                                                             'session_version', 'password'))
        devices = list(TOTPDevice.objects.order_by('pk').values_list('pk', 'user_id', 'confirmed', 'key'))
        return users, devices, AuditEvent.objects.count()

    def assertRefusedUnchanged(self, message, operation, relative, target, environ):
        before = self.state()
        with self.assertRaisesRegex(Refused, message):
            self.perform(operation, relative, target, environ)
        self.assertEqual(self.state(), before, 'a refused administrator change changed something')


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
        TOTPDevice.objects.filter(user=self.approver).delete()
        relative, door = self.declare(self.text(authority.RESET, self.admin))
        self.assertRefusedUnchanged('no confirmed authenticator', authority.RESET, relative, self.admin.pk, door)

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
        with patch.object(authority, 'REPOSITORY', self.root), patch.dict('os.environ', door):
            call_command('reset_admin_mfa', '--declaration', relative, '--target', str(self.admin.pk),
                         stdout=out, stderr=err)
        printed = out.getvalue() + err.getvalue()
        result = json.loads(out.getvalue())
        self.assertTrue(result['enrolment_required_at_next_sign_in'])
        self.assertFalse(TOTPDevice.objects.filter(user=self.admin).exists(), 'the command created a key')
        for secret in old_keys + [PASSWORD, self.admin.password, self.admin.email, self.approver.email]:
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
                             stdout=io.StringIO(), stderr=io.StringIO())
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
