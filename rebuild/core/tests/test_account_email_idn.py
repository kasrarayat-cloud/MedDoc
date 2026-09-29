"""An internationalized DOMAIN in an account address (v1 close-out, email): accepted in its own letters, stored as its A-label.

The address is stored ASCII: the part before "@" as typed in ASCII, lowercased; the domain in its lowercase A-label form
(idna 3.19: UTS46 mapping, non-transitional, STD3 rules, IDNA2008 validity). Every spelling of one domain (U-label,
case, fullwidth, NFD, soft hyphen, typed A-label) reaches the ONE account, at every door that chooses an address AND
every door that looks one up, and shares one per-address sign-in limit; two different domains never share an account.
The stored form is a fixed point of the rule and of the email field, so it can be typed back (and prefilled) at every door.

RED on debaefd9 (the rule before this change): the tests below fail there, except the unchanged-behaviour controls.
"""
import io
import json
from datetime import timedelta
from unittest.mock import patch

from django import forms as django_forms
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core import forms as account_forms
from core.forms import ClinicInvitationForm, InvitationForm, RegisterForm, account_email
from core.models import (ClinicInvitation, Department, Invitation, LoginAttempt, Membership, Organization, User,
                         Verification)
from core.security import digest, token
from core.tests.test_account_email_rule import AccountDoors, PASSWORD, registration

# Looked up by name so the module also loads on the tree before this change, where each test then fails on its own (RED).
ACCOUNT_EMAIL_BAD_DOMAIN = getattr(account_forms, 'ACCOUNT_EMAIL_BAD_DOMAIN', '<no domain rule on this tree>')
account_lookup_email = getattr(account_forms, 'account_lookup_email', lambda value: (value or '').strip().lower())

U = 'sam@bücher.example'
A = 'sam@xn--bcher-kva.example'
#: Every one names A's domain under UTS46: upper case, fullwidth letters, NFD (u + U+0308), a soft hyphen, the A-label.
SPELLINGS = ('sam@BÜCHER.EXAMPLE', 'sam@ｂüｃｈｅｒ.example', 'sam@bu\u0308cher.example', 'sam@b\u00adücher.example',
             'SAM@XN--BCHER-KVA.example', 'Sam@xn--bcher-kva.EXAMPLE', U, A)
ASCII_REFUSAL = 'Enter the email address in ASCII characters'
TOO_LONG = 'at most 150 characters'
EXISTS = 'An account with this email address already exists.'
#: A CJK domain: 93 characters as typed with a 40-character local part, 195 once stored as A-labels.
CJK = '.'.join(['乙亀仏伝候兜冴刃剣劇勅勧匠卑', '垣堕塀墨壇壮奪嫁宵寡寧尋岳巡', '弔彫徴忌怠恒恭悔慨憂慶戒扶抗']) + '.example'
#: Each passes Django's email field as typed; none may be stored.
INVALID_DOMAINS = {
    'invalid Punycode': 'xn--zz.example',
    'non-canonical (fake) A-label': 'xn---bbk.example',
    # An A-label IDNA2008 disallows but IDNA2003 decodes ('xn--n3h' is U+2603) is accepted typed as an A-label, as before
    # the rule (F1, test_account_email_idn_repair.Idna2003Labels); typed in its own letters it is refused:
    'disallowed code point typed in its own letters': '\u2603.example',
    'ZWNJ between Latin letters (CONTEXTJ)': 'ab\u200ccd.example',
    'bidi rule': 'a\u0627.example',
    'leading combining mark': '\u0301abc.example',
    'disallowed symbol': '♥.example',
    'label over 63 octets once converted': 'ü' * 60 + '.example',
    'empty label from ideographic full stops': 'bücher。。example.org',
    'trailing dot from an ideographic full stop': 'bücher.example。',
    'trailing dot from a fullwidth full stop': 'bücher.example．',
    # The converted form is one the email field itself refuses, so it could never be typed back or prefilled.
    'digits-only top-level label once converted': 'example.１２３',
    'top-level label with a digit once converted': 'example.co²',
    'top-level A-label with a hyphen': 'bücher.ñandú',
}


class IdnFormsMixin:
    def every_form(self, email):
        department = InvitationForm({'department': self.department.pk, 'email': email, 'role': 'clinician'}, user=self.owner)
        clinic = ClinicInvitationForm({'email': email, 'organization_name': 'Synthetic clinic', 'department_name': 'Main'})
        return RegisterForm(registration(email)), department, clinic

    def verified(self, email=A):
        return User.objects.create_user(username=email, email=email, password=PASSWORD, verified_at=timezone.now())


class IdnDomainReachesOneAccount(IdnFormsMixin, AccountDoors):
    @override_settings(QUILLMD_REGISTRATION='open')
    def test_register_in_unicode_stores_the_a_label_and_every_spelling_is_that_account(self):
        self.assertEqual(Client().post('/register/', registration(U)).status_code, 302)
        self.assertTrue(User.objects.filter(email=A, username=A).exists())
        for spelling in SPELLINGS:
            with self.subTest(spelling=spelling):
                self.assertContains(Client().post('/register/', registration(spelling)), EXISTS, status_code=200)
        self.assertEqual(User.objects.count(), 3)          # the admin, the owner and the one new account

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_register_the_a_label_then_unicode_is_the_same_account(self):
        self.assertEqual(Client().post('/register/', registration('SAM@XN--BCHER-KVA.EXAMPLE')).status_code, 302)
        self.assertTrue(User.objects.filter(email=A, username=A).exists())
        self.assertContains(Client().post('/register/', registration(U)), EXISTS, status_code=200)
        self.assertEqual(self.accounts(A), 1)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_both_invitations_issued_in_unicode_are_stored_as_the_a_label(self):
        department, clinic = self.issue(U)
        self.assertEqual((department.status_code, clinic.status_code), (302, 302))
        self.assertEqual(Invitation.objects.get().email, A)
        self.assertEqual(ClinicInvitation.objects.get().email, A)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_a_department_invitation_is_accepted_with_either_form(self):
        for local, typed_domain in (('p1', 'bücher.example'), ('p2', 'xn--bcher-kva.example'), ('p3', 'ＢÜＣＨＥＲ.example')):
            with self.subTest(typed=typed_domain):
                stored = f'{local}@xn--bcher-kva.example'
                link = self.department_invitation(stored)
                response = self.accept(link, f'{local}@{typed_domain}')
                self.assertEqual(response.status_code, 302)
                account = User.objects.get(email=stored, username=stored)
                self.assertTrue(Membership.objects.filter(user=account, department=self.department).exists())
                self.assertIsNotNone(Invitation.objects.get(email=stored).accepted_at)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_a_clinic_invitation_is_accepted_with_either_form(self):
        for local, typed_domain in (('c1', 'bücher.example'), ('c2', 'xn--bcher-kva.example')):
            with self.subTest(typed=typed_domain):
                stored = f'{local}@xn--bcher-kva.example'
                response = self.accept(self.clinic_invitation(stored), f'{local}@{typed_domain}')
                self.assertEqual(response.status_code, 302)
                self.assertTrue(User.objects.filter(email=stored, username=stored).exists())
                self.assertIsNotNone(ClinicInvitation.objects.get(email=stored).accepted_at)

    def test_sign_in_with_every_spelling_reaches_the_one_account(self):
        self.verified()
        for spelling in SPELLINGS[:7]:                     # 7 sign-ins: under the per-address limit of 8
            with self.subTest(spelling=spelling):
                self.assertEqual(Client().post('/login/', {'email': spelling, 'password': PASSWORD}).status_code, 302)

    def test_the_per_address_sign_in_limit_is_shared_by_every_spelling(self):
        """Without one key, each spelling is a fresh bucket of 8 guesses against the same account."""
        self.verified()
        wrong = ('sam@bücher.example', 'sam@BÜCHER.EXAMPLE', 'sam@ｂüｃｈｅｒ.example', 'sam@bu\u0308cher.example',
                 'sam@b\u00adücher.example', 'sam@b\u00ad\u00adücher.example', 'sam@b\u00ad\u00ad\u00adücher.example',
                 'SAM@XN--BCHER-KVA.example')
        for spelling in wrong:
            self.assertContains(Client().post('/login/', {'email': spelling, 'password': 'not-the-password-1'}),
                                'Sign-in failed', status_code=200)
        response = Client().post('/login/', {'email': 'sam@b\u00ad\u00ad\u00ad\u00adücher.example', 'password': PASSWORD})
        self.assertContains(response, 'Too many sign-in attempts', status_code=200)

    def test_recovery_with_either_form_mails_the_stored_address(self):
        self.verified()
        with patch('core.recovery.deliver_account_email') as delivery:
            for typed in (U, 'SAM@XN--BCHER-KVA.example'):
                self.assertEqual(Client().post('/recovery/', {'email': typed}).status_code, 200)
        self.assertEqual([call.args[2] for call in delivery.call_args_list], [A, A])

    def test_verification_resend_with_either_form_reissues_for_the_account(self):
        user = User.objects.create_user(username=A, email=A, password=PASSWORD)
        with patch('core.recovery.deliver_account_email') as delivery:
            for typed in (U, A):
                self.assertEqual(Client().post('/verification/resend/', {'email': typed}).status_code, 200)
        self.assertEqual([call.args[2] for call in delivery.call_args_list], [A, A])
        self.assertEqual(Verification.objects.filter(user=user).count(), 2)

    def test_the_stored_form_is_a_fixed_point(self):
        """Of the rule, of the lookup key, AND of the email field: the prefilled invitation address, sign-in by the stored
        address and bootstrap_first_admin's canonical == declared check all depend on it."""
        field = django_forms.EmailField()
        for typed in SPELLINGS + ('a@faß.de', 'a@βόλος.gr', 'a@ශ්\u200dරී.example', 'a@ıbm.example', 'a@İbm.example',
                                  'a@ab--cd.xn--bcher-kva.example', 'a@пример.рф', 'a@例え.テスト'):
            with self.subTest(typed=typed):
                stored = account_email(typed)
                self.assertTrue(stored.isascii())
                self.assertEqual(account_email(stored), stored)
                self.assertEqual(account_lookup_email(stored), stored)
                self.assertEqual(field.clean(stored), stored)

    def test_a_legacy_address_the_rule_now_refuses_still_signs_in_by_its_old_key(self):
        """A refused input keeps exactly its old lookup key: an account stored before the rule with an invalid "xn--"
        label (the rule now refuses it where an address is chosen) still reaches its account at every lookup door."""
        legacy = 'leg@xn--zz.example'
        user = User.objects.create(username=legacy, email=legacy, verified_at=timezone.now())
        user.set_password(PASSWORD)
        user.save()
        self.assertEqual(Client().post('/login/', {'email': 'LEG@xn--zz.example', 'password': PASSWORD}).status_code, 302)
        with patch('core.recovery.deliver_account_email') as delivery:
            self.assertEqual(Client().post('/recovery/', {'email': legacy}).status_code, 200)
        self.assertEqual([call.args[2] for call in delivery.call_args_list], [legacy])

    def test_the_lookup_key_of_every_ascii_input_is_unchanged(self):
        """Every ASCII input the email field admits keeps today's key (stripped, lowercased), accepted by the rule or not."""
        for typed in (' Sam.Smith@Synthetic.Invalid ', 'SAM@XN--BCHER-KVA.EXAMPLE', 'a@xn--zz.example', 'a@XN---BBK.example',
                      '"sam"@synthetic.invalid', 'a' * 151 + '@synthetic.invalid', 'a@[127.0.0.1]', 'a@localhost',
                      'a@ab--cd.example'):
            with self.subTest(typed=typed):
                self.assertEqual(account_lookup_email(typed), typed.strip().lower())


class IdnDomainRefusals(IdnFormsMixin, AccountDoors):
    def test_a_non_ascii_local_part_is_still_refused_at_every_form(self):
        for email in ('ſam@bücher.example', 'ıan@xn--bcher-kva.example', 'ſam@synthetic.invalid', '\u212aate@bücher.example'):
            for form in self.every_form(email):
                with self.subTest(email=email, form=type(form).__name__):
                    self.assertFalse(form.is_valid())
                    self.assertIn(ASCII_REFUSAL, ' '.join(form.errors['email']))

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_two_different_domains_stay_two_accounts(self):
        pairs = (('faß.de', 'fass.de', 'xn--fa-hia.de'), ('ıbm.example', 'ibm.example', 'xn--bm-gpa.example'),
                 ('İbm.example', 'ibm.example', 'xn--ibm-8dc.example'), ('рaypal.example', 'paypal.example', 'xn--aypal-uye.example'),
                 ('βόλος.example', 'βόλοσ.example', 'xn--nxasmm1c.example'))
        for index, (unicode_domain, other_domain, expected) in enumerate(pairs):
            with self.subTest(pair=(unicode_domain, other_domain)):
                LoginAttempt.objects.all().delete()        # the registration limit is 5 per client address per 10 minutes
                first, second = f'd{index}@{unicode_domain}', f'd{index}@{other_domain}'
                self.assertEqual(Client().post('/register/', registration(first)).status_code, 302)
                self.assertEqual(Client().post('/register/', registration(second)).status_code, 302)
                self.assertTrue(User.objects.filter(email=f'd{index}@{expected}').exists())
                self.assertEqual(User.objects.filter(email__startswith=f'd{index}@').count(), 2)

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_fullwidth_spellings_are_the_ascii_account_not_a_new_one(self):
        self.assertEqual(Client().post('/register/', registration('sam@example.org')).status_code, 302)
        for spelling in ('sam@ｅｘａｍｐｌｅ.org', 'sam@exam\u00adple.org', 'sam@EXAMPLE.ORG'):
            with self.subTest(spelling=spelling):
                self.assertContains(Client().post('/register/', registration(spelling)), EXISTS, status_code=200)
        self.assertEqual(self.accounts('sam@example.org'), 1)

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_the_trailing_dot_spelling_is_refused_not_a_second_account(self):
        self.assertEqual(Client().post('/register/', registration(U)).status_code, 302)
        for spelling in ('sam@bücher.example。', 'sam@bücher.example．', 'sam@bücher.example｡'):
            with self.subTest(spelling=spelling):
                response = Client().post('/register/', registration(spelling))
                self.assertEqual(response.status_code, 200)
                self.assertIn(ACCOUNT_EMAIL_BAD_DOMAIN, ' '.join(response.context['form'].errors['email']))
        self.assertEqual(User.objects.filter(email__startswith='sam@xn--bcher-kva.example').count(), 1)

    def test_an_address_over_the_columns_once_converted_is_refused_at_every_form(self):
        email = 'a' * 40 + '@' + CJK
        self.assertLessEqual(len(email), 150)
        for form in self.every_form(email):
            with self.subTest(form=type(form).__name__):
                self.assertFalse(form.is_valid())
                self.assertIn(TOO_LONG, ' '.join(form.errors['email']))

    def test_exactly_the_column_length_once_converted_is_accepted_and_one_more_is_refused(self):
        domain_a = '@xn--bcher-kva.example'
        fits = 'a' * (150 - len(domain_a)) + '@bücher.example'
        self.assertEqual(len(account_email(fits)), 150)
        for form in self.every_form(fits):
            with self.subTest(form=type(form).__name__, length=150):
                self.assertTrue(form.is_valid(), form.errors)
        for form in self.every_form('a' + fits):
            with self.subTest(form=type(form).__name__):
                self.assertFalse(form.is_valid())
                self.assertIn(TOO_LONG, ' '.join(form.errors['email']))

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_invalid_domains_are_refused_and_nothing_is_written(self):
        field = django_forms.EmailField()
        for reason, domain in INVALID_DOMAINS.items():
            email = 'bad@' + domain
            with self.subTest(reason=reason, door='email field'):
                self.assertEqual(field.clean(email), email)   # the refusal is the rule's, not the field's
            for form in self.every_form(email):
                with self.subTest(reason=reason, form=type(form).__name__):
                    self.assertFalse(form.is_valid())
                    self.assertIn(ACCOUNT_EMAIL_BAD_DOMAIN, ' '.join(form.errors['email']))
            with self.subTest(reason=reason, door='issuance'):
                department, clinic = self.issue(email)
                self.assertEqual((department.status_code, clinic.status_code), (200, 200))
        self.assertFalse(Invitation.objects.exists())
        self.assertFalse(ClinicInvitation.objects.exists())

    def test_ascii_domains_without_an_a_label_are_unchanged(self):
        for typed in (' Sam.Smith@Synthetic.Invalid ', 'a@ab--cd.example', 'a@[127.0.0.1]', 'a@localhost', 'a@XN--BCHER-KVA.example'):
            with self.subTest(typed=typed):
                self.assertEqual(account_email(typed), typed.strip().lower())


class AccountEmailAudit(TestCase):
    """manage.py account_email_audit: the install precondition, answered with counts only, in a read-only transaction."""

    def audit(self):
        """(printed output, the report it holds, the refusal message or None)."""
        output = io.StringIO()
        try:
            call_command('account_email_audit', stdout=output)
        except CommandError as refusal:
            return output.getvalue(), json.loads(output.getvalue()), str(refusal)
        return output.getvalue(), json.loads(output.getvalue()), None

    def setUp(self):
        self.issuer = User.objects.create_user(username='issuer@synthetic.invalid', email='issuer@synthetic.invalid')
        organization = Organization.objects.create(name='Synthetic audit organization')
        self.department = Department.objects.create(organization=organization, name='Synthetic audit desk')

    def invitation(self, email):
        return Invitation.objects.create(email=email, department=self.department, invited_by=self.issuer,
                                         token_hash=digest(token()), expires_at=timezone.now() + timedelta(days=1))

    def clinic_invitation(self, email):
        return ClinicInvitation.objects.create(email=email, organization_name='Synthetic audit clinic', department_name='Main',
                                               invited_by=self.issuer, token_hash=digest(token()),
                                               expires_at=timezone.now() + timedelta(days=1))

    def test_a_database_inside_the_rule_is_clean_and_exits_zero(self):
        User.objects.create(username=A, email=A)
        self.invitation('p@xn--bcher-kva.example')
        self.clinic_invitation('c@synthetic.invalid')
        _, report, refusal = self.audit()
        self.assertIsNone(refusal)
        self.assertEqual(report, {'clean': True, 'tables': {
            'core_user': {'rows': 2, 'non_ascii': 0, 'ascii_not_normalised': 0},
            'core_invitation': {'rows': 1, 'non_ascii': 0, 'ascii_not_normalised': 0},
            'core_clinicinvitation': {'rows': 1, 'non_ascii': 0, 'ascii_not_normalised': 0}}})

    def test_rows_outside_the_rule_are_counted_the_exit_refuses_and_no_address_is_printed(self):
        # Stored as the views stored them before the rule (create, not create_user: no username normalisation).
        User.objects.create(username='leg@bücher.example', email='leg@bücher.example')           # non-ASCII
        User.objects.create(username='ſpare@synthetic.invalid', email='spare@synthetic.invalid')  # non-ASCII username
        User.objects.create(username='old@xn--zz.example', email='old@xn--zz.example')           # invalid A-label
        User.objects.create(username='"q"@synthetic.invalid', email='"q"@synthetic.invalid')     # quoted
        self.invitation('i@bücher.example')                                                      # non-ASCII
        self.invitation('Mixed@Synthetic.invalid')                                               # not lowercased
        self.invitation('ok@xn--bcher-kva.example')
        self.clinic_invitation('c@ｂüｃｈｅｒ.example')                                              # non-ASCII
        printed, report, refusal = self.audit()
        self.assertEqual(report, {'clean': False, 'tables': {
            'core_user': {'rows': 5, 'non_ascii': 2, 'ascii_not_normalised': 2},
            'core_invitation': {'rows': 3, 'non_ascii': 1, 'ascii_not_normalised': 1},
            'core_clinicinvitation': {'rows': 1, 'non_ascii': 1, 'ascii_not_normalised': 0}}})
        self.assertIn('outside the account email rule', refusal or '<no refusal: exit status 0>')
        for fragment in ('@', 'xn--', 'bücher', 'ｂüｃｈｅｒ', 'synthetic', 'leg', 'spare', 'mixed', 'ok'):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, printed.lower())
                self.assertNotIn(fragment, refusal.lower())

    def test_the_audit_reads_in_a_read_only_transaction_it_rolls_back(self):
        User.objects.create(username='leg@bücher.example', email='leg@bücher.example')
        before = list(User.objects.order_by('pk').values())
        with CaptureQueriesContext(connection) as queries:
            self.audit()
        statements = [query['sql'].strip() for query in queries.captured_queries]
        reads = [sql for sql in statements if not sql.upper().startswith(('SAVEPOINT', 'RELEASE SAVEPOINT', 'ROLLBACK TO SAVEPOINT'))]
        self.assertEqual(reads[0], 'SET TRANSACTION READ ONLY')
        self.assertEqual(len(reads), 4)                    # one read per table
        self.assertTrue(all(sql.upper().startswith('SELECT') for sql in reads[1:]), reads)
        self.assertTrue(any(sql.upper().startswith('ROLLBACK TO SAVEPOINT') for sql in statements), statements)
        self.assertEqual(list(User.objects.order_by('pk').values()), before)
        # The read-only mode ended with the audit's own rolled-back savepoint: this test's transaction still writes.
        User.objects.create(username='after@synthetic.invalid', email='after@synthetic.invalid')

    def test_a_write_inside_the_audit_is_refused_by_the_database(self):
        """The READ ONLY transaction is the mechanism, not a convention: a write attempted inside it fails, and fails as
        PostgreSQL's read_only_sql_transaction (SQLSTATE 25006), not for any other reason. The write is one that succeeds
        in an ordinary transaction (the positive control, below)."""
        from core.management.commands import account_email_audit as command
        refusals = []

        def writing_counts(model, columns):
            if model is User:
                try:
                    User.objects.filter(email='leg@bücher.example').update(first_name='Rewritten')
                except DatabaseError as error:
                    refusals.append(getattr(error.__cause__, 'sqlstate', None))
                    raise
            return {'rows': 0, 'non_ascii': 0, 'ascii_not_normalised': 0}

        User.objects.create(username='leg@bücher.example', email='leg@bücher.example', first_name='Synthetic')
        output = io.StringIO()
        with patch.object(command, 'table_counts', writing_counts):
            with self.assertRaisesMessage(CommandError, 'account_email_audit_refused; nothing was written'):
                call_command('account_email_audit', stdout=output)
        self.assertEqual(refusals, ['25006'])
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(User.objects.get(email='leg@bücher.example').first_name, 'Synthetic')
        # Positive control: the same write outside the audit succeeds.
        self.assertEqual(User.objects.filter(email='leg@bücher.example').update(first_name='Rewritten'), 1)
