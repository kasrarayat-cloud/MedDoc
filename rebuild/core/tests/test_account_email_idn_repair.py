"""The account email rule's refutation findings on a4eef20f (v1 close-out, email), one class per finding.

  F2     A row stored before the rule with a Unicode domain (main stored the address as typed) was found by no spelling
         once the lookup doors used the A-label: sign-in and recovery failed, and a second account could be created for
         its mailbox. The lookup doors (core.forms.accounts_at) now also reach such a row: by its own spelling, and by
         every spelling of its domain when IDNA2003 (the codec its mail went out through) and the rule name one domain.
         Because a lookup can now reach more than one row, its order is pinned: the row stored exactly as typed, then the
         row stored exactly as the lookup key, then by primary key (on a4eef20f a legacy 'ſam@…' row whose primary key
         sorted first answered for 'sam@…', so sam could not sign in).
  R1-F1  A respelling the database's UPPER() equates with an account's address ('b@synthetic.ınvalid', 'ſam@…') reached
         the account with a fresh per-address bucket (pre-existing). The limit now follows the account reached.
  F3     The recovery and resend limits were not proved shared by the spellings of one domain (a test gap).
  F1     An A-label IDNA2008 disallows but IDNA2003 registered (xn--n3h.net is ☃.net) was refused where an address is
         chosen, though accepted before the rule: an existing account there could not be invited.
  R1-F2  A domain mixing a U-label with an ASCII label IDNA2008 reserves ('ab--cd') was refused, while its all-ASCII
         spelling was accepted: the U-label spelling of a stored address did not reach it.
  R1-F3  Three spellings of one IPv6 literal were three accounts (pre-existing).

RED on a4eef20f: every test below fails there except those marked "control" and OneLimitForEverySpelling (F3 is a test
gap: it fails when either limit is keyed on the typed spelling). Synthetic addresses only; delivery is patched.
"""
import uuid
from unittest.mock import patch

from django import forms as django_forms
from django.test import Client, override_settings
from django.utils import timezone

from core import forms as account_forms
from core.forms import account_email
from core.models import ClinicInvitation, Invitation, LoginAttempt, User, Verification
from core.tests.test_account_email_idn import A, ACCOUNT_EMAIL_BAD_DOMAIN, EXISTS, IdnFormsMixin
from core.tests.test_account_email_rule import AccountDoors, PASSWORD, registration

# Looked up by name so the module also loads on a4eef20f, where each test then fails on its own (RED).
ACCOUNT_EMAIL_IP_LITERAL = getattr(account_forms, 'ACCOUNT_EMAIL_IP_LITERAL', '<no IPv6 literal rule on this tree>')

WRONG = 'not-the-password-repair-1'
TOO_MANY = 'Too many sign-in attempts'
FAILED = 'Sign-in failed'
LEGACY = 'leg@bücher.example'
LEGACY_A = 'leg@xn--bcher-kva.example'


class RepairMixin(IdnFormsMixin):
    def legacy(self, email, verified=True, **fields):
        """An account stored before the rule, as the views stored it: username = email, as typed (not create_user, which
        would NFKC-normalise the username), with a usable password."""
        account = User.objects.create(username=email, email=email, verified_at=timezone.now() if verified else None, **fields)
        account.set_password(PASSWORD)
        account.save()
        return account

    def stored(self, typed):
        """The stored form, or the refusal as text: a refusal is compared, not raised, so it fails an assertion."""
        try:
            return account_email(typed)
        except django_forms.ValidationError as refusal:
            return 'REFUSED: ' + ' '.join(refusal.messages)

    def sign_in(self, email, password=PASSWORD):
        """(response, the signed-in account's pk as a string or None)."""
        client = Client()
        response = client.post('/login/', {'email': email, 'password': password})
        return response, client.session.get('_auth_user_id')

    def recovery(self, *typed):
        with patch('core.recovery.deliver_account_email') as delivery:
            for email in typed:
                self.assertEqual(Client().post('/recovery/', {'email': email}).status_code, 200)
        return [call.args[2] for call in delivery.call_args_list]

    def resend(self, *typed):
        with patch('core.recovery.deliver_account_email') as delivery:
            for email in typed:
                self.assertEqual(Client().post('/verification/resend/', {'email': email}).status_code, 200)
        return [call.args[2] for call in delivery.call_args_list]


class LegacyUnicodeDomainAccounts(RepairMixin, AccountDoors):
    """F2. On a4eef20f: every sign-in 200 'Sign-in failed', recovery mailed nothing, and registering the U-label created
    'leg@xn--bcher-kva.example' beside the legacy row."""

    def test_every_spelling_of_its_domain_signs_in_to_the_legacy_account(self):
        account = self.legacy(LEGACY)
        for spelling in (LEGACY, 'LEG@BÜCHER.EXAMPLE', 'leg@ｂüｃｈｅｒ.example', 'leg@bücher.example', LEGACY_A,
                         'LEG@XN--BCHER-KVA.EXAMPLE'):                    # 6 sign-ins: under the account's limit of 8
            with self.subTest(spelling=spelling):
                response, signed_in = self.sign_in(spelling)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(signed_in, str(account.pk))

    def test_recovery_by_either_form_mails_the_stored_address(self):
        self.legacy(LEGACY)
        self.assertEqual(self.recovery(LEGACY, LEGACY_A), [LEGACY, LEGACY])

    def test_verification_resend_by_either_form_reissues_for_an_unverified_legacy_account(self):
        account = self.legacy(LEGACY, verified=False)
        self.assertEqual(self.resend(LEGACY, LEGACY_A), [LEGACY, LEGACY])
        self.assertEqual(Verification.objects.filter(user=account).count(), 2)

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_no_spelling_registers_a_second_account_for_its_mailbox(self):
        self.legacy(LEGACY)
        for spelling in (LEGACY, LEGACY_A, 'leg@ｂüｃｈｅｒ.example', 'LEG@BÜCHER.EXAMPLE'):
            with self.subTest(spelling=spelling):
                self.assertContains(Client().post('/register/', registration(spelling)), EXISTS, status_code=200)
        self.assertEqual(User.objects.filter(email__in=[LEGACY, LEGACY_A]).count(), 1)

    @override_settings(QUILLMD_REGISTRATION='invite')
    def test_no_invitation_creates_a_second_account_for_its_mailbox(self):
        self.legacy(LEGACY)
        for link in (self.department_invitation(LEGACY_A), self.clinic_invitation(LEGACY_A)):
            with self.subTest(link=link.split('/')[2]):
                response = self.accept(link, LEGACY_A)
                self.assertEqual(response.status_code, 200)
                self.assertIn(EXISTS, ' '.join(response.context['form'].errors['email']))
        self.assertEqual(User.objects.filter(email__in=[LEGACY, LEGACY_A]).count(), 1)
        self.assertIsNone(Invitation.objects.get(email=LEGACY_A).accepted_at)
        self.assertIsNone(ClinicInvitation.objects.get(email=LEGACY_A).accepted_at)

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_a_legacy_long_s_local_part_with_a_unicode_domain_answers_as_the_rule_says(self):
        """RA-LOW-1's 'ſam@…' answers for 'sam@…' (the database's UPPER()), here with the domain in its own letters."""
        account = self.legacy('ſam@bücher.example')
        for spelling in ('sam@bücher.example', 'sam@xn--bcher-kva.example'):
            with self.subTest(spelling=spelling):
                self.assertContains(Client().post('/register/', registration(spelling)), EXISTS, status_code=200)
                self.assertEqual(self.sign_in(spelling)[1], str(account.pk))
        self.assertFalse(User.objects.filter(email='sam@xn--bcher-kva.example').exists())

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_a_domain_the_two_standards_name_differently_is_reached_only_by_its_own_spelling(self):
        """'faß' is fass under IDNA2003 (Django's mail path) and xn--fa-hia under the rule: which one the account was
        verified at is not established, so neither A-label reaches it; its own spelling still does, as before."""
        account = self.legacy('dev@faß.example')
        response, signed_in = self.sign_in('dev@faß.example')
        self.assertEqual((response.status_code, signed_in), (302, str(account.pk)))
        for other in ('dev@xn--fa-hia.example', 'dev@fass.example'):
            with self.subTest(other=other):
                response, signed_in = self.sign_in(other)
                self.assertContains(response, FAILED, status_code=200)
                self.assertIsNone(signed_in)
                self.assertEqual(self.recovery(other), [])
        self.assertEqual(self.recovery('dev@faß.example'), ['dev@faß.example'])
        self.assertContains(Client().post('/register/', registration('dev@faß.example')), EXISTS, status_code=200)

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_a_legacy_domain_stored_with_a_trailing_full_stop_is_the_same_name(self):
        """EmailValidator admitted 'bücher.example。' and main stored it as typed: the fully qualified spelling of
        bücher.example. On a4eef20f (and before) only that spelling reached it and the A-label registered beside it."""
        account = self.legacy('dot@bücher.example\u3002')
        for spelling in ('dot@bücher.example\u3002', 'dot@bücher.example', 'dot@xn--bcher-kva.example'):
            with self.subTest(spelling=spelling):
                self.assertEqual(self.sign_in(spelling)[1], str(account.pk))
        for spelling in ('dot@bücher.example', 'dot@xn--bcher-kva.example'):
            with self.subTest(register=spelling):
                self.assertContains(Client().post('/register/', registration(spelling)), EXISTS, status_code=200)
        self.assertEqual(User.objects.filter(email__startswith='dot@').count(), 1)

    def test_a_legacy_account_and_its_a_label_twin_each_keep_the_spelling_that_reached_it(self):
        """The rule before this one let an A-label account be registered beside a legacy one (both trees). Each still
        signs in by the spelling that reached it before; any other spelling reaches the one stored as the lookup key."""
        legacy, twin = self.legacy(LEGACY), self.legacy(LEGACY_A)
        for spelling, expected in ((LEGACY, legacy), (LEGACY_A, twin), ('leg@ｂüｃｈｅｒ.example', twin)):
            with self.subTest(spelling=spelling):
                self.assertEqual(self.sign_in(spelling)[1], str(expected.pk))

    def test_each_address_signs_in_to_its_own_account_beside_a_legacy_long_s_twin(self):
        """The lookup prefers the account stored exactly as its key. On a4eef20f every door took the first of the two rows
        email__iexact returns by primary key (a random UUID; fixed here so the legacy row sorts first), so 'sam@…' reached
        the legacy 'ſam@…' account and failed on sam's own password."""
        long_s = self.legacy('ſam@synthetic.invalid', id=uuid.UUID(int=1))
        ordinary = User.objects.create_user(username='sam@synthetic.invalid', email='sam@synthetic.invalid',
                                            password='Synthetic-Other-5530!private', verified_at=timezone.now(),
                                            id=uuid.UUID(int=2))
        self.assertEqual(self.sign_in('sam@synthetic.invalid', 'Synthetic-Other-5530!private')[1], str(ordinary.pk))
        self.assertEqual(self.sign_in('ſam@synthetic.invalid')[1], str(long_s.pk))

    def test_control_recovery_keeps_djangos_own_comparison(self):
        """Control (passes on a4eef20f): a dotless-ı respelling reaches the account by the database's UPPER() but not by
        Django's NFKC case-insensitive comparison, so recovery mails nothing for it."""
        self.verified('b@synthetic.invalid')
        self.assertEqual(self.recovery('b@synthetic.ınvalid'), [])

    def test_control_a_unicode_spelling_never_reaches_an_ascii_account_of_another_name(self):
        """Control (passes on a4eef20f): ıbm is not ibm, and a legacy row of another domain is not reached."""
        self.verified('a@ibm.example')
        self.legacy('a@bücher.example')
        response, signed_in = self.sign_in('a@ıbm.example')
        self.assertContains(response, FAILED, status_code=200)
        self.assertEqual(self.recovery('a@ıbm.example', 'a@example.org'), [])


class LimitFollowsTheAccount(RepairMixin, AccountDoors):
    """R1-F1. On a4eef20f each respelling below reached the account with its own fresh bucket of 8 sign-in guesses (3
    recovery or resend mails); identical before the IDN change."""
    #: (the account, a respelling the database's UPPER() equates with it that the rule refuses)
    PAIRS = (('b@synthetic.invalid', 'b@synthetic.ınvalid'), (A, 'ſam@xn--bcher-kva.example'),
             ('ann@example.clinic', 'ann@example.clınic'))

    def exhaust(self, spelling):
        for _ in range(8):
            self.assertContains(self.sign_in(spelling, WRONG)[0], FAILED, status_code=200)

    def test_eight_guesses_by_the_address_close_every_respelling(self):
        for account, respelling in self.PAIRS:
            with self.subTest(account=account):
                LoginAttempt.objects.all().delete()        # the per-client limit is 40 per 10 minutes
                self.verified(account)
                self.exhaust(account)
                response, signed_in = self.sign_in(respelling)
                self.assertContains(response, TOO_MANY, status_code=200)
                self.assertIsNone(signed_in)

    def test_eight_guesses_by_a_respelling_close_the_address(self):
        for account, respelling in self.PAIRS:
            with self.subTest(account=account):
                LoginAttempt.objects.all().delete()
                self.verified(account)
                self.exhaust(respelling)
                self.assertContains(self.sign_in(account)[0], TOO_MANY, status_code=200)

    def test_control_another_account_keeps_its_own_limit(self):
        self.verified('b@synthetic.invalid')
        other = self.verified('c@synthetic.invalid')
        self.exhaust('b@synthetic.ınvalid')
        self.assertEqual(self.sign_in('c@synthetic.invalid')[1], str(other.pk))

    def test_a_respelling_shares_the_recovery_limit(self):
        self.verified(A)
        self.assertEqual(self.recovery(A, A, A, 'ſam@xn--bcher-kva.example'), [A, A, A])

    def test_a_respelling_shares_the_resend_limit(self):
        User.objects.create_user(username='b@synthetic.invalid', email='b@synthetic.invalid', password=PASSWORD)
        self.assertEqual(self.resend(*['b@synthetic.invalid'] * 3, 'b@synthetic.ınvalid'), ['b@synthetic.invalid'] * 3)


class OneLimitForEverySpelling(RepairMixin, AccountDoors):
    """F3 (a test gap: a4eef20f passes). Four spellings of one domain against a limit of 3: a limit keyed on the typed
    spelling mails 4 times."""
    SPELLINGS = ('sam@bücher.example', 'sam@BÜCHER.EXAMPLE', 'sam@b­ücher.example', A)

    def test_recovery(self):
        self.verified(A)
        self.assertEqual(self.recovery(*self.SPELLINGS), [A, A, A])

    def test_verification_resend(self):
        User.objects.create_user(username=A, email=A, password=PASSWORD)
        self.assertEqual(self.resend(*self.SPELLINGS), [A, A, A])


class Idna2003Labels(RepairMixin, AccountDoors):
    """F1. On a4eef20f both issuances answered 200 'Enter a valid domain' for an existing account at leg@xn--n3h.net, and
    registration refused new@xn--n3h.net and new@xn--i-7iq.ws; all were accepted before the rule."""

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_an_address_at_an_idna2003_name_can_register(self):
        for email in ('new@xn--n3h.net', 'new@xn--i-7iq.ws', 'NEW@XN--LS8H.LA'):
            with self.subTest(email=email):
                self.assertEqual(Client().post('/register/', registration(email)).status_code, 302)
                self.assertTrue(User.objects.filter(email=email.lower(), username=email.lower()).exists())

    def test_an_existing_account_at_such_a_name_can_be_invited(self):
        self.verified('leg@xn--n3h.net')
        department, clinic = self.issue('leg@xn--n3h.net')
        self.assertEqual((department.status_code, clinic.status_code), (302, 302))
        self.assertEqual(Invitation.objects.get().email, 'leg@xn--n3h.net')
        self.assertEqual(ClinicInvitation.objects.get().email, 'leg@xn--n3h.net')

    def test_control_an_a_label_valid_under_idna2008_alone_is_still_accepted(self):
        """Control (passes on a4eef20f): IDNA2003 is an alternative, not a second condition. xn--fa-hia (faß) and
        xn--nxasmm1c (βόλος) do not round-trip under IDNA2003."""
        for email in ('a@xn--fa-hia.de', 'a@xn--nxasmm1c.gr'):
            with self.subTest(email=email):
                self.assertEqual(self.stored(email), email)
                self.assertTrue(all(form.is_valid() for form in self.every_form(email)))

    def test_control_its_own_letters_and_malformed_a_labels_are_still_refused(self):
        """Control (passes on a4eef20f)."""
        field = django_forms.EmailField()
        for email in ('a@☃.net', 'a@i❤.ws', 'a@xn--zz.example', 'a@xn---bbk.example', 'a@xn--a.example',
                      'a@xn--zz.bücher.example'):
            self.assertEqual(field.clean(email), email)
            for form in self.every_form(email):
                with self.subTest(email=email, form=type(form).__name__):
                    self.assertFalse(form.is_valid())
                    self.assertIn(ACCOUNT_EMAIL_BAD_DOMAIN, ' '.join(form.errors['email']))


class MixedLabels(RepairMixin, AccountDoors):
    """R1-F2. On a4eef20f the U-label spelling of 'sam@ab--cd.xn--bcher-kva.example' was refused (hyphens in the third
    and fourth positions of the ASCII label) and did not reach the account."""
    STORED = 'sam@ab--cd.xn--bcher-kva.example'

    def test_each_label_is_stored_as_its_ascii_spelling_is(self):
        for typed, stored in (('sam@ab--cd.bücher.example', self.STORED), ('SAM@AB--CD.BÜCHER.EXAMPLE', self.STORED),
                              ('sam@ａｂ--cd.bücher.example', self.STORED), ('sam@ａb--cd.example', 'sam@ab--cd.example'),
                              ('a@xn--n3h.bücher.example', 'a@xn--n3h.xn--bcher-kva.example')):
            with self.subTest(typed=typed):
                self.assertEqual(self.stored(typed), stored)
                self.assertEqual(self.stored(stored), stored)

    def test_the_unicode_spelling_signs_in_to_the_account(self):
        account = self.verified(self.STORED)
        self.assertEqual(self.sign_in('sam@ab--cd.bücher.example')[1], str(account.pk))

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_the_unicode_spelling_is_refused_as_the_existing_account(self):
        self.verified(self.STORED)
        self.assertContains(Client().post('/register/', registration('sam@ab--cd.bücher.example')), EXISTS, status_code=200)
        self.assertEqual(User.objects.filter(email__startswith='sam@ab--cd').count(), 1)


class Ipv6Literals(RepairMixin, AccountDoors):
    """R1-F3. On a4eef20f (and before) sam@[::1], sam@[0:0:0:0:0:0:0:1] and sam@[0000::0001] were three accounts."""
    LONGER = ('sam@[0:0:0:0:0:0:0:1]', 'sam@[0000::0001]', 'sam@[0:0::1]', 'sam@[::0001]', 'sam@[::ffff:127.0.0.1]')

    @override_settings(QUILLMD_REGISTRATION='open')
    def test_one_account_per_address(self):
        self.assertEqual(Client().post('/register/', registration('sam@[::1]')).status_code, 302)
        for spelling in self.LONGER:
            with self.subTest(spelling=spelling):
                LoginAttempt.objects.all().delete()        # the registration limit is 5 per client address
                response = Client().post('/register/', registration(spelling))
                self.assertEqual(response.status_code, 200)
                self.assertIn(ACCOUNT_EMAIL_IP_LITERAL, ' '.join(response.context['form'].errors['email']))
        self.assertEqual(list(User.objects.filter(email__startswith='sam@[').values_list('email', flat=True)), ['sam@[::1]'])

    def test_every_form_and_both_issuances_refuse_a_longer_spelling(self):
        for form in self.every_form('sam@[0:0:0:0:0:0:0:1]'):
            with self.subTest(form=type(form).__name__):
                self.assertFalse(form.is_valid())
                self.assertIn(ACCOUNT_EMAIL_IP_LITERAL, ' '.join(form.errors['email']))
        department, clinic = self.issue('sam@[0:0:0:0:0:0:0:1]')
        self.assertEqual((department.status_code, clinic.status_code), (200, 200))
        self.assertFalse(Invitation.objects.exists())
        self.assertFalse(ClinicInvitation.objects.exists())

    def test_control_the_shortest_form_is_a_fixed_point(self):
        """Control (passes on a4eef20f)."""
        field = django_forms.EmailField()
        for typed, stored in (('sam@[::1]', 'sam@[::1]'), ('Sam@[2001:DB8::1]', 'sam@[2001:db8::1]'),
                              ('sam@[127.0.0.1]', 'sam@[127.0.0.1]')):
            with self.subTest(typed=typed):
                self.assertEqual(self.stored(typed), stored)
                self.assertEqual(self.stored(stored), stored)
                self.assertEqual(field.clean(stored), stored)

    def test_control_an_account_stored_in_a_longer_spelling_still_signs_in_by_it(self):
        """Control (passes on a4eef20f): a refused spelling keeps its old lookup key."""
        account = self.legacy('old@[0:0:0:0:0:0:0:1]')
        self.assertEqual(self.sign_in('OLD@[0:0:0:0:0:0:0:1]')[1], str(account.pk))
