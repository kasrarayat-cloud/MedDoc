"""RA-LOW-1: one rule for an account's email address, at every door that creates an account.

The database's case-insensitive uniqueness is `UniqueConstraint(Lower('email'))` (PostgreSQL lower()); every lookup of an
account by address is `email__iexact` (PostgreSQL UPPER()); the views compare with Python's str.lower(), and the email
backend's allowlist with str.casefold(). The four agree on ASCII and disagree elsewhere: lower('ſ') is 'ſ' while
upper('ſ') is 'S', so 'ſam@…' passes the unique index beside 'sam@…' and both answer the same iexact lookup — two
accounts for one address, and a sign-in that picks either. Django's EmailValidator admits exactly four non-ASCII
letters in a local part (ſ, ı, İ and the Kelvin sign U+212A), and only because Python's re.IGNORECASE folds them onto its
ASCII character class; every other non-ASCII local part (ß, fullwidth letters) is already refused.

The rule (core.forms.account_email): an account address is ASCII, stripped and lowercased — the one set on which every
comparison above agrees. Nothing is folded or rewritten into a different address, because the stored address is where
the account's mail goes. An internationalized domain is entered in its ASCII ("xn--") form. And an address that the
lookup rule already matches to an account (for example a legacy 'ſam@…' row) is refused for a new account.

RED on 61c5cc8f: every door below created the second account.

The second refutation of the residuals (RR2, docs/rebuild/v1/residuals-assessment-20260929.md) found two more addresses
the rule let through:

  * RR2-ACC-1: an address longer than the account's username column (150 characters; the address IS the username) passed
    every form, and every door answered 500 (a DataError on the insert). An address of 255 to 320 characters also passed
    both invitation forms (Django's form field allows 320) and failed on the invitation's own column at issuance.
  * RR2-ACC-2: a quoted local part ("sam"@…, or "s\\am"@…) is valid to Django's EmailValidator and names the same mailbox
    as sam@… (RFC 5321), but no comparison equates the two strings: a second account was created beside sam@….

RED on d5367521: every test in AccountEmailBounds and QuotedLocalPart below failed.
"""
import os
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import clinic_invitations
from core.email_delivery import Delivery
from core.forms import ClinicInvitationForm, InvitationForm, RegisterForm
from core.management.commands import bootstrap_first_admin
from core.models import ClinicInvitation, Department, Invitation, Membership, Organization, User
from core.security import digest, token
from ops.production_operator import OperatorError

PASSWORD = 'Synthetic-Only-4821!private'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
ORDINARY = 'sam@synthetic.invalid'
#: Twins of ORDINARY that PostgreSQL's UPPER() (the iexact lookup) equates with it and lower() (the unique index) does not.
LONG_S = 'ſam@synthetic.invalid'
NOT_ASCII = ('ſam@synthetic.invalid', 'ıan@synthetic.invalid', 'İan@synthetic.invalid',
             '\u212aate@synthetic.invalid',  # the Kelvin sign
             'sam@bücher.example')
ASCII_REFUSAL = 'Enter the email address in ASCII characters'
#: RR2-ACC-1: the username column, which holds the address, is 150 characters.
TOO_LONG = 'at most 150 characters'
#: RR2-ACC-2: quoted twins of ORDINARY, each accepted by Django's EmailValidator.
QUOTED = ('"sam"@synthetic.invalid', '"s\\am"@synthetic.invalid', '"SAM"@synthetic.invalid')
QUOTED_REFUSAL = 'without quotation marks'


def registration(email):
    return {'email': email, 'first_name': 'Synthetic', 'last_name': 'Person', 'password1': PASSWORD,
            'password2': PASSWORD, 'synthetic_only': 'on'}


def address(length, domain='@synthetic.invalid'):
    """An address Django's EmailValidator accepts, exactly `length` characters long."""
    return 'a' * (length - len(domain)) + domain


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES)
class AccountDoors(TestCase):
    """Every door that chooses an account's address: registration, both acceptances and both issuances."""

    def setUp(self):
        self.admin = User.objects.create_user(username='platform-admin@synthetic.invalid', email='platform-admin@synthetic.invalid',
                                              verified_at=timezone.now(), is_staff=True)
        self.owner = User.objects.create_user(username='owner@synthetic.invalid', email='owner@synthetic.invalid',
                                              verified_at=timezone.now())
        organization = Organization.objects.create(name='Synthetic rule clinic')
        self.department = Department.objects.create(organization=organization, name='Synthetic front desk')
        Membership.objects.create(user=self.owner, department=self.department, role='owner')

    def accounts(self, email):
        return User.objects.filter(email__iexact=email).count()

    def refused(self, response, reason):
        """An invitation page that refused to create the account. The lookup already answers with an account, so the page
        shows the existing-account notice (sign in) in place of the form; the form's own refusal is the reason."""
        self.assertContains(response, 'This email already has an account.', status_code=200)
        self.assertIn(reason, ' '.join(response.context['form'].errors['email']))

    def legacy_account(self, email):
        """An account created before this rule existed, stored as the account views stored it: username = email, as typed
        (create_user would NFKC-normalize the username, which the views never did)."""
        return User.objects.create(username=email, email=email, verified_at=timezone.now())

    def department_invitation(self, email):
        """An invitation row as issuance stored it before this rule (issuance now refuses the address)."""
        raw = token()
        Invitation.objects.create(email=email, department=self.department, role='clinician', invited_by=self.owner,
                                  token_hash=digest(raw), expires_at=timezone.now() + timedelta(days=1))
        return f'/invite/{raw}/'

    def clinic_invitation(self, email):
        raw = token()
        ClinicInvitation.objects.create(email=email, organization_name='Synthetic twin clinic', department_name='Main',
                                        token_hash=digest(raw), expires_at=timezone.now() + timedelta(days=1),
                                        invited_by=self.admin)
        return f'/invite/clinic/{raw}/'

    def issue(self, email):
        """Issue a department invitation (as the owner, /team/) and a clinic-owner invitation (as a platform administrator,
        /console/clinic-invitations/) to `email`; return both responses. Delivery is replaced: nothing is sent."""
        owner = Client(raise_request_exception=False)
        owner.force_login(self.owner)
        device = TOTPDevice.objects.create(user=self.admin, name='Synthetic authenticator', confirmed=True)
        console = Client(raise_request_exception=False)
        console.force_login(self.admin)
        session = console.session
        session['otp_device_id'] = device.persistent_id
        session.save()
        with patch('core.email_delivery.deliver_account_email', return_value=Delivery(status='outbox')), \
                override_settings(QUILLMD_REGISTRATION='invite'):
            department = owner.post('/team/', {'department': self.department.pk, 'email': email, 'role': 'clinician'})
            clinic = console.post('/console/clinic-invitations/', {'email': email, 'organization_name': 'Synthetic long clinic',
                                                                   'department_name': 'Main'})
        device.delete()
        return department, clinic

    def accept(self, link, email):
        """Accept an invitation as a new account (no signed-in session); a 500 is returned, not raised."""
        return Client(raise_request_exception=False).post(link, registration(email))


class AccountEmailRule(AccountDoors):
    # The ſ case, at every door.

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_register_refuses_the_long_s_twin_of_an_existing_account(self):
        self.legacy_account(ORDINARY)
        response = Client().post('/register/', registration(LONG_S))
        self.assertContains(response, ASCII_REFUSAL, status_code=200)
        self.assertEqual(self.accounts(ORDINARY), 1)

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_register_refuses_an_address_a_legacy_long_s_account_already_answers(self):
        self.legacy_account(LONG_S)
        response = Client().post('/register/', registration(ORDINARY))
        self.assertContains(response, 'An account with this email address already exists.', status_code=200)
        self.assertEqual(self.accounts(ORDINARY), 1)
        self.assertFalse(User.objects.filter(email=ORDINARY).exists())

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_department_invitation_cannot_create_the_long_s_twin(self):
        self.legacy_account(ORDINARY)
        link = self.department_invitation(LONG_S)
        response = Client().post(link, registration(LONG_S))
        self.refused(response, ASCII_REFUSAL)
        self.assertEqual(self.accounts(ORDINARY), 1)
        self.assertIsNone(Invitation.objects.get(email=LONG_S).accepted_at)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_department_invitation_cannot_create_an_account_a_legacy_long_s_account_answers(self):
        self.legacy_account(LONG_S)
        link = self.department_invitation(ORDINARY)
        response = Client().post(link, registration(ORDINARY))
        self.refused(response, 'An account with this email address already exists.')
        self.assertEqual(self.accounts(ORDINARY), 1)
        self.assertIsNone(Invitation.objects.get(email=ORDINARY).accepted_at)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_clinic_invitation_cannot_create_the_long_s_twin(self):
        self.legacy_account(ORDINARY)
        link = self.clinic_invitation(LONG_S)
        response = Client().post(link, registration(LONG_S))
        self.refused(response, ASCII_REFUSAL)
        self.assertEqual(self.accounts(ORDINARY), 1)
        self.assertIsNone(ClinicInvitation.objects.get(email=LONG_S).accepted_at)
        self.assertFalse(Organization.objects.filter(name='Synthetic twin clinic').exists())

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_clinic_invitation_cannot_create_an_account_a_legacy_long_s_account_answers(self):
        self.legacy_account(LONG_S)
        link = self.clinic_invitation(ORDINARY)
        response = Client().post(link, registration(ORDINARY))
        self.refused(response, 'An account with this email address already exists.')
        self.assertEqual(self.accounts(ORDINARY), 1)
        self.assertIsNone(ClinicInvitation.objects.get(email=ORDINARY).accepted_at)

    def test_invitations_are_not_issued_to_an_address_no_account_may_have(self):
        for email in NOT_ASCII:
            with self.subTest(email=email):
                department = InvitationForm({'department': self.department.pk, 'email': email, 'role': 'clinician'}, user=self.owner)
                self.assertFalse(department.is_valid())
                self.assertIn(ASCII_REFUSAL, ' '.join(department.errors['email']))
                clinic = ClinicInvitationForm({'email': email, 'organization_name': 'Synthetic clinic', 'department_name': 'Main'})
                self.assertFalse(clinic.is_valid())
                self.assertIn(ASCII_REFUSAL, ' '.join(clinic.errors['email']))

    def test_every_account_form_refuses_every_address_outside_the_rule(self):
        for email in NOT_ASCII:
            with self.subTest(email=email):
                form = RegisterForm(registration(email))
                self.assertFalse(form.is_valid())
                self.assertIn(ASCII_REFUSAL, ' '.join(form.errors['email']))

    # The ordinary cases stay as they were.

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_an_ordinary_address_is_stored_lowercased_and_its_case_variant_refused(self):
        response = Client().post('/register/', registration(' Sam.Smith@Synthetic.Invalid '))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='sam.smith@synthetic.invalid', username='sam.smith@synthetic.invalid').exists())
        again = Client().post('/register/', registration('SAM.SMITH@synthetic.invalid'))
        self.assertEqual(again.status_code, 200)
        self.assertIn('email', again.context['form'].errors)
        self.assertEqual(self.accounts('sam.smith@synthetic.invalid'), 1)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_an_ordinary_invitation_still_creates_its_account(self):
        link = self.department_invitation('new.clinician@synthetic.invalid')
        response = Client().post(link, registration('New.Clinician@synthetic.invalid'))
        self.assertEqual(response.status_code, 302)
        account = User.objects.get(email='new.clinician@synthetic.invalid')
        self.assertTrue(Membership.objects.filter(user=account, department=self.department, active=True).exists())
        invitation, raw = clinic_invitations.issue(self.admin, 'Clinic.Owner@Synthetic.Invalid', 'Synthetic owner clinic', 'Main')
        self.assertEqual(invitation.email, 'clinic.owner@synthetic.invalid')
        response = Client().post(f'/invite/clinic/{raw}/', registration('clinic.owner@synthetic.invalid'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.accounts('clinic.owner@synthetic.invalid'), 1)


class AccountEmailBounds(AccountDoors):
    """RR2-ACC-1. The address is the account's username (views set username = email), a 150-character column; the email
    and invitation columns hold 254. RED on d5367521: 151 to 254 characters passed every form and every account door
    answered 500 (DataError); 255 to 320 passed both invitation forms and issuance answered 500."""

    def test_every_form_that_chooses_an_address_refuses_one_longer_than_the_account_columns(self):
        for length in (151, 254, 300, 320):
            email = address(length)
            with self.subTest(length=length):
                register = RegisterForm(registration(email))
                self.assertFalse(register.is_valid())
                if length <= 254:  # beyond the email column Django's own max_length refuses it first
                    self.assertIn(TOO_LONG, ' '.join(register.errors['email']))
                department = InvitationForm({'department': self.department.pk, 'email': email, 'role': 'clinician'}, user=self.owner)
                self.assertFalse(department.is_valid())
                self.assertIn(TOO_LONG, ' '.join(department.errors['email']))
                clinic = ClinicInvitationForm({'email': email, 'organization_name': 'Synthetic clinic', 'department_name': 'Main'})
                self.assertFalse(clinic.is_valid())
                self.assertIn(TOO_LONG, ' '.join(clinic.errors['email']))

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_register_refuses_an_address_longer_than_the_account_columns(self):
        for length in (151, 254):
            email = address(length)
            with self.subTest(length=length):
                response = Client(raise_request_exception=False).post('/register/', registration(email))
                self.assertEqual(response.status_code, 200)
                self.assertIn(TOO_LONG, ' '.join(response.context['form'].errors['email']))
                self.assertFalse(User.objects.filter(email__iexact=email).exists())

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_an_invitation_issued_before_the_bound_creates_no_account_and_stays_unused(self):
        for length in (151, 254):
            email = address(length)
            for kind, link in (('department', self.department_invitation(email)), ('clinic', self.clinic_invitation(email))):
                model = Invitation if kind == 'department' else ClinicInvitation
                before = list(model.objects.filter(email=email).values())
                with self.subTest(length=length, kind=kind):
                    response = self.accept(link, email)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(TOO_LONG, ' '.join(response.context['form'].errors['email']))
                    self.assertFalse(User.objects.filter(email__iexact=email).exists())
                    self.assertEqual(list(model.objects.filter(email=email).values()), before)
                    self.assertFalse(Organization.objects.filter(name='Synthetic twin clinic').exists())
                model.objects.filter(email=email).delete()

    def test_no_invitation_is_issued_to_an_address_longer_than_the_account_columns(self):
        for length in (151, 300):
            email = address(length)
            with self.subTest(length=length):
                department, clinic = self.issue(email)
                for response in (department, clinic):
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(TOO_LONG, ' '.join(response.context['form'].errors['email']))
                self.assertFalse(Invitation.objects.filter(email=email).exists())
                self.assertFalse(ClinicInvitation.objects.filter(email=email).exists())

    def test_an_address_of_exactly_the_column_length_still_creates_its_account(self):
        """Control: the bound is the column, not tighter. 150 characters is issued, accepted and registered."""
        email = address(150)
        department, clinic = self.issue(email)
        self.assertEqual((department.status_code, clinic.status_code), (302, 302))
        invitation = Invitation.objects.get(email=email)
        raw = token()
        Invitation.objects.filter(pk=invitation.pk).update(token_hash=digest(raw))
        with override_settings(QUILLMD_REGISTRATION='invite'):
            response = self.accept(f'/invite/{raw}/', email)
        self.assertEqual(response.status_code, 302)
        account = User.objects.get(email=email)
        self.assertEqual((account.username, len(account.username)), (email, 150))
        self.assertTrue(Membership.objects.filter(user=account, department=self.department).exists())
        other = address(150, '@other.synthetic.invalid')
        with override_settings(QUILLMD_REGISTRATION='open'):
            self.assertEqual(Client().post('/register/', registration(other)).status_code, 302)
        self.assertTrue(User.objects.filter(email=other, username=other).exists())


class QuotedLocalPart(AccountDoors):
    """RR2-ACC-2. "sam"@… and sam@… are one mailbox and two strings. RED on d5367521: the quoted twin created a second
    account at /register/ and at both invitation doors, and both invitation forms issued to it."""

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_register_refuses_the_quoted_twin_of_an_existing_account(self):
        self.legacy_account(ORDINARY)
        for email in QUOTED:
            with self.subTest(email=email):
                response = Client().post('/register/', registration(email))
                self.assertEqual(response.status_code, 200)
                self.assertIn(QUOTED_REFUSAL, ' '.join(response.context['form'].errors['email']))
                self.assertEqual(User.objects.count(), 3)  # the administrator, the owner and ORDINARY

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_neither_invitation_creates_the_quoted_twin(self):
        self.legacy_account(ORDINARY)
        email = QUOTED[0]
        for kind, link in (('department', self.department_invitation(email)), ('clinic', self.clinic_invitation(email))):
            model = Invitation if kind == 'department' else ClinicInvitation
            before = list(model.objects.filter(email=email).values())
            with self.subTest(kind=kind):
                response = self.accept(link, email)
                self.assertEqual(response.status_code, 200)
                self.assertIn(QUOTED_REFUSAL, ' '.join(response.context['form'].errors['email']))
                self.assertEqual(User.objects.count(), 3)
                self.assertEqual(list(model.objects.filter(email=email).values()), before)

    def test_every_form_that_chooses_an_address_refuses_a_quoted_local_part(self):
        for email in QUOTED:
            with self.subTest(email=email):
                register = RegisterForm(registration(email))
                self.assertFalse(register.is_valid())
                self.assertIn(QUOTED_REFUSAL, ' '.join(register.errors['email']))
                department = InvitationForm({'department': self.department.pk, 'email': email, 'role': 'clinician'}, user=self.owner)
                self.assertFalse(department.is_valid())
                self.assertIn(QUOTED_REFUSAL, ' '.join(department.errors['email']))
                clinic = ClinicInvitationForm({'email': email, 'organization_name': 'Synthetic clinic', 'department_name': 'Main'})
                self.assertFalse(clinic.is_valid())
                self.assertIn(QUOTED_REFUSAL, ' '.join(clinic.errors['email']))

    def test_no_invitation_is_issued_to_a_quoted_local_part(self):
        department, clinic = self.issue(QUOTED[0])
        for response in (department, clinic):
            self.assertEqual(response.status_code, 200)
            self.assertIn(QUOTED_REFUSAL, ' '.join(response.context['form'].errors['email']))
        self.assertFalse(Invitation.objects.exists())
        self.assertFalse(ClinicInvitation.objects.exists())


class FirstAdministratorEmailRule(TestCase):
    """The administrator-creation door: bootstrap_first_admin creates the first account (and only when there is none)."""

    def setUp(self):
        secret = patch.object(bootstrap_first_admin, 'private_json', return_value={'password': 'Synthetic-only-passphrase-8492!'})
        secret.start()
        self.addCleanup(secret.stop)
        env = patch.dict(os.environ, {'RULED_MUTATION_DECL_COMMIT': 'b' * 40})
        env.start()
        self.addCleanup(env.stop)
        self.profile = SimpleNamespace(operator_directory=Path('/synthetic/operator'), sha256='ab' * 32)
        self.declaration = {'release_sha': 'a' * 40}

    def create(self, email):
        return bootstrap_first_admin.bootstrap('create', self.profile, self.declaration, uuid.uuid4(), email)

    def test_an_address_outside_the_rule_is_refused_before_any_account_exists(self):
        for email in ('ſowner@example.org', 'Owner@example.org', 'owner@bücher.example'):
            with self.subTest(email=email):
                with self.assertRaisesRegex(OperatorError, 'first_admin_email'):
                    self.create(email)
                self.assertFalse(User.objects.exists())

    def test_an_ordinary_address_creates_the_first_account(self):
        self.assertEqual(self.create('owner@example.org')['created'], True)
        self.assertEqual(User.objects.get().email, 'owner@example.org')

    def test_an_address_too_long_or_quoted_is_refused_by_name_before_any_account_exists(self):
        """RR2-ACC-1 and RR2-ACC-2 at this door. RED on d5367521: the long address raised DataError from the insert, not
        the command's own refusal; the quoted address created the account."""
        for email in (address(151, '@example.org'), '"owner"@example.org'):
            with self.subTest(email=email):
                with self.assertRaisesRegex(OperatorError, 'first_admin_email'):
                    self.create(email)
                self.assertFalse(User.objects.exists())

    def test_an_address_of_exactly_the_column_length_creates_the_first_account(self):
        email = address(150, '@example.org')
        self.assertEqual(self.create(email)['created'], True)
        self.assertEqual(User.objects.get().username, email)
