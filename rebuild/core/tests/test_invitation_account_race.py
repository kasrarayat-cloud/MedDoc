"""R-A: two requests that create the same new account at the same moment.

Residual 1 of the final default-path refutation on d9fa3249: two DIFFERENT still-valid invitations for one address
that has no account yet, accepted at the same instant. Both acceptances pass RegisterForm's unique-email check before
either commits; the later account insert then waits on the unique index and fails with an IntegrityError when the
first commits. RED on 8e3dcfd0: invite_accept and clinic_invitations.accept let it through as HTTP 500. The same
shape exists in /register/ (open mode only; real mode is invitation-only): two submissions of one address.

The race is made deterministic, not probabilistic: each request runs on its own thread and database connection, and
both wait at a barrier immediately before their `INSERT INTO "core_user"`, so both have passed validation and both are
inside their transaction (holding their own invitation's row lock) when the inserts are released together.

Decision (the sequential case is the specification): accepting the second invitation after the first committed already
answers 200 and asks the person to sign in, because an unauthenticated form may not attach an invitation to an
existing account. The concurrent loser gets the same handled answer: its transaction rolled back whole, so there is
one account, its invitation is unused and still valid, and signing in and reopening it joins the account the first
acceptance created. An IntegrityError that is not this race is still reported as a defect (500).

Real PostgreSQL, synthetic accounts only; no email, provider or network request is made.
"""
import threading
from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError, connection
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone

from core import clinic_invitations
from core.email_delivery import Delivery
from core.models import (AuditEvent, ClinicInvitation, Department, Invitation, LedgerEntry, Membership, Organization,
                         User, Wallet)
from core.security import digest, token
from core.tests.test_retention_flow_locks import in_thread

PASSWORD = 'Synthetic-Only-4821!private'
ADDRESS = 'new-clinician@synthetic.invalid'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
REFUSAL = 'This invitation has not been used'


def paused_before_account_insert(barrier):
    """An execute wrapper: hold this connection right before it inserts an account until every racer is there too."""
    def wrapper(execute, sql, params, many, context):
        if sql.startswith('INSERT INTO "core_user"'):
            barrier.wait(30)
        return execute(sql, params, many, context)
    return wrapper


def at_the_same_moment(*requests):
    """Run each request on its own thread and connection, releasing their account inserts together."""
    barrier = threading.Barrier(len(requests))

    def racing(request):
        def run():
            with connection.execute_wrapper(paused_before_account_insert(barrier)):
                return request()
        return run
    started = [in_thread(racing(request)) for request in requests]
    for thread, _ in started:
        thread.join(60)
        assert not thread.is_alive(), 'a synthetic request never finished'
    return [outcome for _, outcome in started]


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES, QUILLMD_REGISTRATION='invite')
class InvitationRaceFixture(TransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='platform-admin@synthetic.invalid', email='platform-admin@synthetic.invalid',
                                              verified_at=timezone.now(), is_staff=True)
        self.owner = User.objects.create_user(username='owner@synthetic.invalid', email='owner@synthetic.invalid',
                                              verified_at=timezone.now())
        organization = Organization.objects.create(name='Synthetic race clinic')
        self.front_desk = Department.objects.create(organization=organization, name='Synthetic front desk')
        self.imaging = Department.objects.create(organization=organization, name='Synthetic imaging')
        for department in (self.front_desk, self.imaging):
            Membership.objects.create(user=self.owner, department=department, role='owner')

    def department_invitation(self, department):
        raw = token()
        invitation = Invitation.objects.create(email=ADDRESS, department=department, role='clinician', invited_by=self.owner,
                                               token_hash=digest(raw), expires_at=timezone.now() + timedelta(days=1))
        return invitation, f'/invite/{raw}/'

    def clinic_invitation(self, name):
        invitation, raw = clinic_invitations.issue(self.admin, ADDRESS, name, 'Synthetic main practice')
        return invitation, f'/invite/clinic/{raw}/'

    @staticmethod
    def submit(link):
        def post():
            client = Client(raise_request_exception=False)
            return client.post(link, {'email': ADDRESS, 'first_name': 'Synthetic', 'last_name': 'Clinician',
                                      'password1': PASSWORD, 'password2': PASSWORD, 'synthetic_only': 'on'})
        return post

    def race(self, first, second):
        """Accept two invitations at the same moment; return (winner, loser) as (invitation, link, response)."""
        audit_before = set(AuditEvent.objects.values_list('pk', flat=True))
        outcomes = at_the_same_moment(self.submit(first[1]), self.submit(second[1]))
        for outcome in outcomes:
            self.assertNotIn('error', outcome, outcome.get('error'))
        codes = sorted(outcome['value'].status_code for outcome in outcomes)
        self.assertEqual(codes, [200, 302], [getattr(outcome['value'], 'exc_info', None) for outcome in outcomes])
        # The pre-existing audit trail is untouched: nothing was rewritten or lost by the rolled-back acceptance.
        self.assertTrue(audit_before <= set(AuditEvent.objects.values_list('pk', flat=True)))
        ranked = sorted(zip((first, second), outcomes), key=lambda pair: pair[1]['value'].status_code, reverse=True)
        (winner, won), (loser, lost) = ranked
        self.assertEqual(won['value']['Location'], '/login/')
        self.assertContains(lost['value'], REFUSAL, status_code=200)
        self.assertContains(lost['value'], 'This email already has an account.', status_code=200)
        return winner[0], loser[0]

    def assert_one_account(self):
        account = User.objects.get(email__iexact=ADDRESS)
        self.assertIsNotNone(account.verified_at)
        self.assertEqual(Wallet.objects.filter(user=account).count(), 2)
        self.assertEqual(LedgerEntry.objects.filter(key=f'welcome:{account.pk}').count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='credit.welcome', actor=account).count(), 1)
        return account

    def assert_unused(self, invitation):
        invitation.refresh_from_db()
        self.assertIsNone(invitation.accepted_at)
        self.assertFalse(AuditEvent.objects.filter(target=str(invitation.pk), action__endswith='invitation_accepted').exists())

    def sign_in_and_accept(self, account, link):
        """The sequential path the refusal points to: sign in as the account just created, reopen the invitation."""
        client = Client()
        client.force_login(account)
        response = client.post(link, {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/login/')


class TwoInvitationsForOneNewAddress(InvitationRaceFixture):
    def test_two_department_invitations_accepted_at_the_same_moment(self):
        front = self.department_invitation(self.front_desk)
        imaging = self.department_invitation(self.imaging)
        winner, loser = self.race(front, imaging)
        account = self.assert_one_account()
        self.assertEqual(list(Membership.objects.filter(user=account).values_list('department', flat=True)), [winner.department_id])
        winner.refresh_from_db()
        self.assertIsNotNone(winner.accepted_at)
        self.assertEqual(AuditEvent.objects.filter(action='department.invitation_accepted', target=str(winner.pk)).count(), 1)
        self.assert_unused(loser)
        # The refused invitation is still valid and joins the account the first acceptance created.
        self.sign_in_and_accept(account, dict([front, imaging])[loser])
        self.assertEqual(set(Membership.objects.filter(user=account).values_list('department', flat=True)),
                         {self.front_desk.pk, self.imaging.pk})
        self.assertEqual(User.objects.filter(email__iexact=ADDRESS).count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(key=f'welcome:{account.pk}').count(), 1)

    def test_two_clinic_invitations_accepted_at_the_same_moment(self):
        north = self.clinic_invitation('Synthetic North clinic')
        south = self.clinic_invitation('Synthetic South clinic')
        winner, loser = self.race(north, south)
        account = self.assert_one_account()
        winner.refresh_from_db()
        self.assertEqual(winner.accepted_by, account)
        # Only the winner's organization exists: the refused acceptance left no organization, department or membership.
        self.assertEqual(list(Organization.objects.exclude(name='Synthetic race clinic').values_list('name', flat=True)),
                         [winner.organization_name])
        self.assertFalse(Organization.objects.filter(name=loser.organization_name).exists())
        self.assertEqual(Membership.objects.filter(user=account).count(), 1)
        self.assert_unused(loser)
        self.assertIsNone(ClinicInvitation.objects.get(pk=loser.pk).organization)
        self.sign_in_and_accept(account, dict([north, south])[loser])
        self.assertTrue(Membership.objects.filter(user=account, role='owner', department__organization__name=loser.organization_name).exists())
        self.assertEqual(User.objects.filter(email__iexact=ADDRESS).count(), 1)

    def test_a_department_and_a_clinic_invitation_accepted_at_the_same_moment(self):
        department = self.department_invitation(self.front_desk)
        clinic = self.clinic_invitation('Synthetic cross clinic')
        winner, loser = self.race(department, clinic)
        account = self.assert_one_account()
        self.assertEqual(Membership.objects.filter(user=account).count(), 1)
        self.assert_unused(loser)
        self.sign_in_and_accept(account, dict([department, clinic])[loser])
        self.assertEqual(Membership.objects.filter(user=account).count(), 2)
        self.assertEqual(User.objects.filter(email__iexact=ADDRESS).count(), 1)


def paused_before_invitation_lock(barrier):
    """An execute wrapper: hold this connection right before it locks the invitation row until every racer is there too."""
    def wrapper(execute, sql, params, many, context):
        if sql.startswith('SELECT') and 'FOR UPDATE' in sql and ('FROM "core_invitation"' in sql or 'FROM "core_clinicinvitation"' in sql):
            barrier.wait(30)
        return execute(sql, params, many, context)
    return wrapper


#: RR2-ACC-3: what the second of two simultaneous acceptances of ONE invitation reads.
ALREADY_ACCEPTED = 'This invitation has already been accepted'


class OneInvitationAcceptedTwiceAtOnce(InvitationRaceFixture):
    """RR2-ACC-3. The same invitation submitted twice at the same moment (two tabs, or a double submit the page's
    data-submit-once did not stop). Both requests pass validation (no account yet) and wait for the invitation's row lock;
    the first accepts and creates the account, the second then finds the invitation used. RED on d5367521: the second
    answered a bare 404 (Http404 raised under the lock), saying nothing about the account its own address now has.
    Decision: the second is told the invitation was already accepted and to sign in, on the sign-in page; it wrote
    nothing. Deterministic: both requests are held at a barrier right before the row lock."""

    def race_one(self, link):
        barrier = threading.Barrier(2)

        def submit():
            with connection.execute_wrapper(paused_before_invitation_lock(barrier)):
                client = Client(raise_request_exception=False)
                return client.post(link, {'email': ADDRESS, 'first_name': 'Synthetic', 'last_name': 'Clinician',
                                          'password1': PASSWORD, 'password2': PASSWORD, 'synthetic_only': 'on'}, follow=True)
        started = [in_thread(submit) for _ in range(2)]
        for thread, _ in started:
            thread.join(60)
            self.assertFalse(thread.is_alive(), 'a synthetic request never finished')
        outcomes = [outcome for _, outcome in started]
        for outcome in outcomes:
            self.assertNotIn('error', outcome, outcome.get('error'))
        responses = [outcome['value'] for outcome in outcomes]
        self.assertEqual([response.status_code for response in responses], [200, 200],
                         [getattr(response, 'exc_info', None) for response in responses])
        for response in responses:
            self.assertEqual(response.redirect_chain, [('/login/', 302)])
        told = [response for response in responses if ALREADY_ACCEPTED in response.content.decode()]
        self.assertEqual(len(told), 1)
        self.assertContains(told[0], 'the account for this email address exists')
        return responses

    def test_one_department_invitation_accepted_twice_at_the_same_moment(self):
        invitation, link = self.department_invitation(self.front_desk)
        self.race_one(link)
        account = self.assert_one_account()
        self.assertEqual(Membership.objects.filter(user=account).count(), 1)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
        self.assertEqual(AuditEvent.objects.filter(action='department.invitation_accepted', target=str(invitation.pk)).count(), 1)

    def test_one_clinic_invitation_accepted_twice_at_the_same_moment(self):
        invitation, link = self.clinic_invitation('Synthetic single clinic')
        self.race_one(link)
        account = self.assert_one_account()
        invitation.refresh_from_db()
        self.assertEqual(invitation.accepted_by, account)
        self.assertEqual(Organization.objects.filter(name='Synthetic single clinic').count(), 1)
        self.assertEqual(Membership.objects.filter(user=account).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action='clinic.invitation_accepted', target=str(invitation.pk)).count(), 1)


class OtherIntegrityErrorsStayDefects(InvitationRaceFixture):
    """The handler is for the account race only. An IntegrityError while no account exists afterwards is a defect and is
    reported as one (500), its transaction rolled back as before."""

    def assert_reported(self, link, point):
        with patch(point, side_effect=IntegrityError('synthetic unrelated constraint')):
            response = self.submit(link)()
        self.assertEqual(response.status_code, 500)
        self.assertFalse(User.objects.filter(email__iexact=ADDRESS).exists())

    def test_department_invitation(self):
        invitation, link = self.department_invitation(self.front_desk)
        self.assert_reported(link, 'core.views.welcome_credit')
        self.assert_unused(invitation)

    def test_clinic_invitation(self):
        invitation, link = self.clinic_invitation('Synthetic defect clinic')
        self.assert_reported(link, 'core.clinic_invitations.welcome_credit')
        self.assert_unused(invitation)


@override_settings(ADMIN_SITE=False, QUILLMD_PREVIEW_AUTH_ENABLED=False, STORAGES=STORAGES, QUILLMD_REGISTRATION='open')
class TwoRegistrationsForOneAddress(TransactionTestCase):
    """The same race in /register/ (open mode; real mode answers 404 there): the address submitted twice at once."""

    def register(self):
        client = Client(raise_request_exception=False)
        return client.post('/register/', {'email': ADDRESS, 'first_name': 'Synthetic', 'last_name': 'Clinician',
                                          'password1': PASSWORD, 'password2': PASSWORD, 'synthetic_only': 'on'})

    def test_two_registrations_at_the_same_moment_create_one_account(self):
        with patch('core.views.verification_mail', return_value=Delivery(status='outbox')) as mail:
            outcomes = at_the_same_moment(self.register, self.register)
        for outcome in outcomes:
            self.assertNotIn('error', outcome, outcome.get('error'))
        responses = sorted((outcome['value'] for outcome in outcomes), key=lambda response: response.status_code)
        self.assertEqual([response.status_code for response in responses], [200, 302],
                         [getattr(response, 'exc_info', None) for response in responses])
        self.assertContains(responses[0], 'An account with this email address already exists.')
        account = User.objects.get(email__iexact=ADDRESS)
        self.assertEqual(mail.call_count, 1)
        self.assertEqual(AuditEvent.objects.filter(action='account.register').count(), 1)
        self.assertEqual(account.verification_set.count(), 1)

    def test_an_unrelated_integrity_error_is_still_a_defect(self):
        real = __import__('core.views', fromlist=['audit']).audit

        def audit(actor, action, *args, **kwargs):
            if action == 'account.register':
                raise IntegrityError('synthetic unrelated constraint')
            return real(actor, action, *args, **kwargs)
        with patch('core.views.verification_mail', return_value=Delivery(status='outbox')), \
                patch('core.views.audit', side_effect=audit):
            self.assertEqual(self.register().status_code, 500)
        self.assertFalse(User.objects.filter(email__iexact=ADDRESS).exists())
