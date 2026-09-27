"""Only isolated synthetic application fixtures; guard mocks are never live proof."""
from decimal import Decimal
import io
import os
from pathlib import Path
from types import SimpleNamespace
import uuid
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from core.management.commands import bootstrap_first_admin as command
from core.models import User, Wallet, Organization, AuditEvent, Verification
from core.security import digest
from ops.production_operator import OperatorError


class FirstAdminTests(TestCase):
    def setUp(self):
        self.identity = uuid.uuid4()
        self.email = 'owner@example.org'
        self.profile = SimpleNamespace(operator_directory=Path('/synthetic/operator'), sha256='ab' * 32)
        self.declaration = {'release_sha': 'a' * 40}
        self.context = (self.profile, self.declaration, self.identity, self.email)
        self.secret = patch.object(command, 'private_json', return_value={'password': 'Synthetic-only-passphrase-8492!'})
        self.secret.start(); self.addCleanup(self.secret.stop)
        self.env = patch.dict(os.environ, {'RULED_MUTATION_DECL_COMMIT': 'b' * 40})
        self.env.start(); self.addCleanup(self.env.stop)

    def run_action(self, action):
        return command.bootstrap(action, *self.context)

    def test_create_has_no_clinic_credit_verification_mfa_or_staff(self):
        result = self.run_action('create')
        user = User.objects.get(pk=self.identity)
        self.assertEqual(user.email, self.email)
        self.assertTrue(user.check_password('Synthetic-only-passphrase-8492!'))
        self.assertFalse(user.is_staff or user.is_superuser or user.verified_at)
        self.assertFalse(Wallet.objects.exists() or Organization.objects.exists() or TOTPDevice.objects.exists())
        self.assertEqual(result['email_sent'], False)
        self.assertEqual(AuditEvent.objects.get(action='account.bootstrap_created').target, str(user.pk))

    def test_repeat_create_refuses_without_resetting_password_or_user(self):
        self.run_action('create')
        before = User.objects.get().password
        with self.assertRaisesRegex(OperatorError, 'bootstrap_user_exists'):
            self.run_action('create')
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().password, before)

    def test_elevation_requires_both_mailbox_and_confirmed_mfa(self):
        self.run_action('create')
        with self.assertRaisesRegex(OperatorError, 'bootstrap_user_state'):
            self.run_action('elevate')
        user = User.objects.get(); user.verified_at = timezone.now(); user.save(update_fields=['verified_at'])
        device = TOTPDevice.objects.create(user=user, confirmed=False)
        with self.assertRaisesRegex(OperatorError, 'bootstrap_mfa_required'):
            self.run_action('elevate')
        device.confirmed = True; device.save(update_fields=['confirmed'])
        self.assertTrue(self.run_action('elevate')['sessions_invalidated'])
        user.refresh_from_db()
        self.assertTrue(user.is_staff); self.assertFalse(user.is_superuser)
        self.assertEqual(user.session_version, 1)
        self.assertFalse(Wallet.objects.exists())
        with self.assertRaisesRegex(OperatorError, 'bootstrap_user_state'):
            self.run_action('elevate')

    def test_foreign_clinical_state_refuses_creation(self):
        Organization.objects.create(name='Synthetic existing clinic')
        with self.assertRaisesRegex(OperatorError, 'bootstrap_database_not_empty'):
            self.run_action('create')
        self.assertFalse(User.objects.exists())

    def test_multiple_or_unrelated_account_cannot_be_elevated(self):
        self.run_action('create')
        User.objects.create_user(username='second', email='second@example.org')
        with self.assertRaisesRegex(OperatorError, 'bootstrap_user_count'):
            self.run_action('elevate')
        self.assertFalse(User.objects.filter(is_staff=True).exists())

    def test_inspect_reconciles_repeat_without_mutation(self):
        self.assertFalse(self.run_action('inspect')['exists'])
        self.run_action('create')
        before = AuditEvent.objects.count()
        self.assertEqual(self.run_action('inspect'), {'exists': True, 'sole_user': True,
                         'verified': False, 'staff': False, 'confirmed_mfa': False})
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_public_verification_and_mfa_enrollment_path_remains_usable(self):
        self.run_action('create')
        user = User.objects.get()
        raw = 'synthetic-mailbox-proof'
        Verification.objects.create(user=user, token_hash=digest(raw), expires_at=timezone.now()+timezone.timedelta(hours=1))
        with self.settings(QUILLMD_REGISTRATION='invite', QUILLMD_MFA_REQUIRED_ALL=True,
                           STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
                                     'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}}):
            self.assertEqual(self.client.post('/verify/'+raw+'/').status_code, 302)
            result = self.client.post('/login/', {'email': self.email, 'password': 'Synthetic-only-passphrase-8492!'})
            self.assertRedirects(result, '/mfa/', fetch_redirect_response=False)
            self.assertEqual(self.client.get('/mfa/').status_code, 200)
        self.assertFalse(Wallet.objects.exists())

    def test_unactivated_real_guard_refuses_before_bootstrap(self):
        with patch.object(command, 'bootstrap') as bootstrap:
            with self.assertRaises(CommandError):
                call_command('bootstrap_first_admin', 'create', stdout=io.StringIO())
        bootstrap.assert_not_called()
