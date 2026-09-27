"""QUILLMD_REGISTRATION=invite: /register/ closed, clinic owners invited from the console.

And QUILLMD_WELCOME_CREDIT: the one-time promotional grant, unchanged at its default.
Synthetic accounts only; email goes to a temporary private outbox.
"""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import re
import tempfile

from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import (AuditEvent, ClinicInvitation, Department, Invitation, LedgerEntry, Membership,
                         Organization, User, Wallet)
from core.security import digest

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
PASSWORD = 'Synthetic-Only-4821!private'


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES, QUILLMD_EMAIL_MODE='file',
                   EMAIL_BACKEND='core.email_backend.PrivateFileEmailBackend')
class InviteFixture(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.outbox = Path(directory.name)
        mail = override_settings(EMAIL_FILE_PATH=self.outbox, QUILLMD_APP_BASE_URL='http://localhost:9130')
        mail.enable()
        self.addCleanup(mail.disable)
        self.admin = User.objects.create_user(username='platform-admin', email='platform-admin@synthetic.invalid',
                                              verified_at=timezone.now(), is_staff=True)
        self.device = TOTPDevice.objects.create(user=self.admin, name='Synthetic authenticator', confirmed=True)
        self.console = Client()
        self.console.force_login(self.admin)
        session = self.console.session
        session['otp_device_id'] = self.device.persistent_id
        session.save()

    def mail(self):
        return '\n'.join(path.read_text() for path in sorted(self.outbox.glob('*.log')))

    def invite(self, email='owner@clinic.invalid', organization='Synthetic Vein Clinic', department='Vascular lab'):
        return self.console.post('/console/clinic-invitations/', {'email': email, 'organization_name': organization,
                                                                  'department_name': department})

    def link(self):
        return re.findall(r'http://localhost:9130(/invite/clinic/[^\s/]+/)', self.mail())[-1]

    def accept(self, link, email='owner@clinic.invalid', client=None, **extra):
        return (client or Client()).post(link, {'email': email, 'first_name': 'Synthetic', 'last_name': 'Owner',
                                                'password1': PASSWORD, 'password2': PASSWORD, 'synthetic_only': 'on', **extra})


class RegistrationClosesInInviteMode(InviteFixture):
    def test_open_mode_is_unchanged(self):
        self.assertEqual(self.client.get('/register/').status_code, 200)
        self.assertContains(self.client.get('/login/'), 'href="/register/"')

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_register_answers_404_and_is_not_offered(self):
        self.assertEqual(self.client.get('/register/').status_code, 404)
        response = self.client.post('/register/', {'email': 'walk-in@synthetic.invalid', 'first_name': 'Walk', 'last_name': 'In',
                                                   'password1': PASSWORD, 'password2': PASSWORD, 'synthetic_only': 'on'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(User.objects.filter(email='walk-in@synthetic.invalid').exists())
        self.assertNotContains(self.client.get('/login/'), '/register/')

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_department_invitations_are_unchanged_in_invite_mode(self):
        owner = User.objects.create_user(username='dept-owner', email='dept-owner@synthetic.invalid', verified_at=timezone.now())
        department = Department.objects.create(organization=Organization.objects.create(name='Existing clinic'), name='Front desk')
        Membership.objects.create(user=owner, department=department, role='owner')
        self.client.force_login(owner)
        self.assertEqual(self.client.post('/team/', {'department': department.pk, 'email': 'nurse@synthetic.invalid',
                                                     'role': 'employee'}).status_code, 302)
        link = re.findall(r'http://localhost:9130(/invite/[^\s/]+/)', self.mail())[-1]
        self.assertEqual(self.accept(link, email='nurse@synthetic.invalid').status_code, 302)
        self.assertTrue(Membership.objects.filter(user__email='nurse@synthetic.invalid', department=department,
                                                  role='employee').exists())


@override_settings(QUILLMD_REGISTRATION='invite')
class InviteClinicOwner(InviteFixture):
    def test_staff_invite_records_a_hashed_seven_day_token_and_audits_without_the_address(self):
        before = timezone.now()
        response = self.invite()
        self.assertEqual(response.status_code, 302)
        invitation = ClinicInvitation.objects.get()
        raw = self.link().split('/')[-2]
        self.assertEqual(invitation.token_hash, digest(raw))
        self.assertNotIn(raw, invitation.token_hash)
        self.assertEqual((invitation.email, invitation.organization_name, invitation.department_name),
                         ('owner@clinic.invalid', 'Synthetic Vein Clinic', 'Vascular lab'))
        self.assertAlmostEqual(invitation.expires_at - before, timedelta(days=7), delta=timedelta(minutes=1))
        event = AuditEvent.objects.get(action='admin.clinic_invitation_created')
        self.assertEqual((event.actor, event.target), (self.admin, str(invitation.pk)))
        self.assertNotIn('owner@clinic.invalid', str(event.details))
        self.assertNotIn('Synthetic Vein Clinic', self.mail())

    def test_accepting_creates_the_organization_department_owner_and_one_welcome_credit(self):
        self.invite()
        link = self.link()
        self.assertContains(Client().get(link), 'Set up Synthetic Vein Clinic')
        self.assertEqual(self.accept(link).status_code, 302)
        owner = User.objects.get(email='owner@clinic.invalid')
        self.assertIsNotNone(owner.verified_at)
        membership = Membership.objects.get(user=owner)
        self.assertEqual((membership.role, membership.department.name, membership.department.organization.name),
                         ('owner', 'Vascular lab', 'Synthetic Vein Clinic'))
        invitation = ClinicInvitation.objects.get()
        self.assertEqual((invitation.accepted_by, invitation.organization), (owner, membership.department.organization))
        self.assertEqual(LedgerEntry.objects.get(key=f'welcome:{owner.pk}').amount, Decimal('10'))
        self.assertTrue(AuditEvent.objects.filter(action='clinic.invitation_accepted', target=str(invitation.pk)).exists())
        # Single use.
        self.assertEqual(Client().get(link).status_code, 404)
        self.assertEqual(self.accept(link, email='owner@clinic.invalid').status_code, 404)
        self.assertEqual(Organization.objects.filter(name='Synthetic Vein Clinic').count(), 1)
        # The new owner can now invite colleagues the ordinary way.
        member = Client()
        member.force_login(owner)
        self.assertContains(member.get('/team/'), 'Create invitation')

    def test_the_invited_address_is_required(self):
        self.invite()
        response = self.accept(self.link(), email='someone-else@clinic.invalid')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='someone-else@clinic.invalid').exists())
        self.assertFalse(Organization.objects.filter(name='Synthetic Vein Clinic').exists())

    def test_an_existing_account_must_sign_in_as_the_invited_address(self):
        existing = User.objects.create_user(username='owner@clinic.invalid', email='owner@clinic.invalid', password=PASSWORD,
                                            verified_at=timezone.now())
        stranger = User.objects.create_user(username='stranger', email='stranger@synthetic.invalid', verified_at=timezone.now())
        self.invite()
        link = self.link()
        self.assertContains(Client().get(link), 'This email already has an account.')
        wrong = Client()
        wrong.force_login(stranger)
        self.assertEqual(wrong.post(link).status_code, 403)
        right = Client()
        right.force_login(existing)
        self.assertEqual(right.post(link).status_code, 302)
        self.assertTrue(Membership.objects.filter(user=existing, role='owner', department__name='Vascular lab').exists())
        self.assertFalse(Membership.objects.filter(user=stranger).exists())

    def test_revoked_and_expired_invitations_grant_nothing(self):
        self.invite(email='revoked@clinic.invalid')
        revoked_link = self.link()
        invitation = ClinicInvitation.objects.get(email='revoked@clinic.invalid')
        self.assertEqual(self.console.post(f'/console/clinic-invitations/{invitation.pk}/revoke/').status_code, 302)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.revoked_at)
        self.assertEqual(invitation.status(), 'revoked')
        self.assertTrue(AuditEvent.objects.filter(action='admin.clinic_invitation_revoked', target=str(invitation.pk)).exists())
        self.assertEqual(Client().get(revoked_link).status_code, 404)
        self.assertEqual(self.accept(revoked_link, email='revoked@clinic.invalid').status_code, 404)

        self.invite(email='late@clinic.invalid')
        late_link = self.link()
        ClinicInvitation.objects.filter(email='late@clinic.invalid').update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.accept(late_link, email='late@clinic.invalid').status_code, 404)
        self.assertFalse(User.objects.filter(email__in=['revoked@clinic.invalid', 'late@clinic.invalid']).exists())

    def test_an_invitation_does_not_outlive_its_issuers_authority(self):
        self.invite()
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        self.assertEqual(self.accept(self.link()).status_code, 409)
        self.assertFalse(User.objects.filter(email='owner@clinic.invalid').exists())
        self.assertIsNone(ClinicInvitation.objects.get().accepted_at)

    def test_only_mfa_verified_staff_reach_the_console_action(self):
        clinician = User.objects.create_user(username='clinician', email='clinician@synthetic.invalid', verified_at=timezone.now())
        self.client.force_login(clinician)
        self.assertEqual(self.client.get('/console/clinic-invitations/').status_code, 404)
        self.assertEqual(self.client.post('/console/clinic-invitations/', {'email': 'x@clinic.invalid', 'organization_name': 'X',
                                                                           'department_name': 'Y'}).status_code, 404)
        unverified = Client()
        unverified.force_login(self.admin)  # staff, but no OTP verification in this session
        self.assertRedirects(unverified.get('/console/clinic-invitations/'), '/mfa/', fetch_redirect_response=False)
        self.assertFalse(ClinicInvitation.objects.exists())
        self.assertContains(self.console.get('/console/'), 'href="/console/clinic-invitations/"')
        self.assertContains(self.console.get('/console/organizations/'), 'Invite clinic owner')


class CreatingNeedsInviteMode(InviteFixture):
    def test_open_mode_refuses_to_create_and_hides_the_navigation(self):
        self.assertEqual(self.invite().status_code, 404)
        self.assertFalse(ClinicInvitation.objects.exists())
        self.assertNotContains(self.console.get('/console/'), '/console/clinic-invitations/')
        self.assertNotContains(self.console.get('/console/organizations/'), 'Invite clinic owner')
        self.assertContains(self.console.get('/console/clinic-invitations/'), 'QUILLMD_REGISTRATION=open')


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class WelcomeCreditSetting(TestCase):
    def verify(self):
        from core.models import Verification
        from core.security import token
        user = User.objects.create_user(username='new@synthetic.invalid', email='new@synthetic.invalid', first_name='New')
        raw = token()
        Verification.objects.create(user=user, token_hash=digest(raw), expires_at=timezone.now() + timedelta(hours=1))
        self.client.post(f'/verify/{raw}/')
        return user

    def test_default_is_the_ten_dollar_grant_as_before(self):
        user = self.verify()
        entry = LedgerEntry.objects.get(key=f'welcome:{user.pk}')
        self.assertEqual((entry.amount, entry.description), (Decimal('10'), 'One $10 personal welcome credit after verification'))
        self.assertEqual(Wallet.objects.get(user=user, kind='promo').balance, Decimal('10'))

    @override_settings(QUILLMD_WELCOME_CREDIT=Decimal('25'))
    def test_a_configured_amount_is_granted_once(self):
        user = self.verify()
        entry = LedgerEntry.objects.get(key=f'welcome:{user.pk}')
        self.assertEqual((entry.amount, entry.description), (Decimal('25'), 'One $25 personal welcome credit after verification'))
        from core.billing import welcome_credit
        welcome_credit(user)
        self.assertEqual(LedgerEntry.objects.filter(kind='welcome', wallet__user=user).count(), 1)

    def test_the_console_sums_recorded_grants_without_restating_todays_setting(self):
        """R4: 'Promotional credit granted' is a historical sum. Its entries keep the amount they were granted at, so
        its definition must not state a per-account amount from today's setting: at 0 or 25 that contradicted the $10."""
        from core import admin_console
        self.verify()  # One $10 entry, at the default.
        definitions = set()
        for value in (Decimal('10'), Decimal('0'), Decimal('25')):
            with self.subTest(setting=value), override_settings(QUILLMD_WELCOME_CREDIT=value):
                row = next(row for row in admin_console.business_overview({'filters': {}})['flow']
                           if row['label'] == 'Promotional credit granted')
                definitions.add(row['definition'])
                self.assertEqual(row['amount'], Decimal('10'))
                self.assertIsNone(re.search(r'\$\s*\d', row['definition']), row['definition'])
        self.assertEqual(len(definitions), 1, definitions)

    @override_settings(QUILLMD_WELCOME_CREDIT=Decimal('0'))
    def test_zero_grants_nothing_and_promises_nothing(self):
        self.assertNotContains(self.client.get('/register/'), 'welcome credit')
        user = self.verify()
        self.assertFalse(LedgerEntry.objects.filter(kind='welcome').exists())
        self.assertEqual(Wallet.objects.get(user=user, kind='promo').balance, Decimal('0'))
        self.assertTrue(Membership.objects.filter(user=user, role='owner').exists())


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES, QUILLMD_REGISTRATION='invite')
class VerificationInInviteMode(TestCase):
    """An account registered before sign-up closed can still prove its mailbox, but verification no longer
    creates a personal organization: that is the self-service onboarding invite mode closes."""

    def test_verification_proves_the_mailbox_and_creates_nothing(self):
        from core.models import Verification
        from core.security import token
        user = User.objects.create_user(username='legacy@synthetic.invalid', email='legacy@synthetic.invalid', first_name='Legacy')
        raw = token()
        Verification.objects.create(user=user, token_hash=digest(raw), expires_at=timezone.now() + timedelta(hours=1))
        self.assertNotContains(self.client.get(f'/verify/{raw}/'), 'welcome credit')
        self.assertRedirects(self.client.post(f'/verify/{raw}/'), '/login/', fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertIsNotNone(user.verified_at)
        self.assertFalse(Membership.objects.filter(user=user).exists())
        self.assertFalse(Organization.objects.exists())
        self.assertFalse(LedgerEntry.objects.filter(kind='welcome').exists())
        self.assertFalse(AuditEvent.objects.get(action='account.verified').details['workspace_created'])
