"""A practice owner sees the team and can turn a person off (release 1, C4; ADM-14, REG-9; owner decision D15: owners
only). GET api/members lists everyone with a membership in the owner's practice - automated and operator-added accounts
included - with no password or hash; POST api/members/<id>/access {"active": false|true} sets that membership's access,
this practice only, never the account's; the owner's own membership and the last active owner are refused; a person
with no other active membership is signed out everywhere; each change writes an AuditEvent naming the owner. The shapes
are the contract's (ops/verification/customer-contract.json: members, member_access, the session's can_manage_team), which
Lane 2's Team panel is built against. Synthetic data only."""
import json
import threading
import uuid
from datetime import timedelta, timezone as dt_timezone

from django.contrib.sessions.models import Session
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone

from studio import api, models
from tests.support import coding as f
from tests.support import operator as ops
from tests.support import rounds as r

Membership, User = models.Membership, models.User
CPT = 'cpt.quillmd.com'
MEMBER_KEYS = {'id', 'name', 'login', 'role', 'active', 'account_active', 'kind', 'last_sign_in', 'must_change_password',
               'you', 'can_change'}


def signed_in(user):
    """A client signed in as ``user`` at the cpt door (the session keys the door writes)."""
    client = Client(HTTP_HOST=CPT)
    client.force_login(user)
    return ops.mark_signed_in(client, door='cpt')


def iso(moment):
    """A time as the contract carries it: UTC, to the second, with Z."""
    return moment.astimezone(dt_timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def sessions_of(user):
    return sum(1 for item in Session.objects.all() if item.get_decoded().get('_auth_user_id') == str(user.pk))


class MembersCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.owner = f.member(self.ws, role=Membership.OWNER)
        self.sc = r.scan_customer()

    def access(self, client, user, active):
        return client.post(f'/api/members/{user.pk}/access', data=json.dumps({'active': active}),
                           content_type='application/json')


class ListTests(MembersCase):
    def test_an_owner_sees_everyone_with_a_membership_and_nothing_secret(self):
        operator_added = f.member(self.ws, role=Membership.VIEWER)
        ops.grant(operator_added)  # an operator who is also a member is listed as a member
        Membership.objects.filter(user=self.viewer).update(active=False)
        User.objects.filter(pk=self.reviewer.pk).update(password_change_required_at=timezone.now())
        models.LoginAttempt.objects.create(username=self.reviewer.username, client='198.51.100.7', succeeded=True)
        latest = models.LoginAttempt.objects.create(username=self.reviewer.username, client='198.51.100.7',
                                                    succeeded=True)
        models.LoginAttempt.objects.create(username=self.reviewer.username, client='198.51.100.7', succeeded=False)
        answer = signed_in(self.owner).get('/api/members')
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(self.sc.shape_problems(answer.json(), self.sc.CONTRACT['members']), [])
        rows = {row['login']: row for row in answer.json()['members']}
        self.assertEqual(set(rows), {self.owner.username, self.reviewer.username, self.viewer.username,
                                     self.agent.username, operator_added.username})  # never another practice's
        for row in rows.values():
            self.assertEqual(set(row), MEMBER_KEYS)
        self.assertEqual((rows[self.agent.username]['kind'], rows[self.reviewer.username]['kind']), ('automated', 'person'))
        self.assertEqual(rows[self.viewer.username]['active'], False)
        self.assertEqual(rows[self.reviewer.username]['must_change_password'], True)
        self.assertEqual(rows[self.owner.username]['must_change_password'], False)
        latest.refresh_from_db()
        self.assertEqual(rows[self.reviewer.username]['last_sign_in'],
                         iso(latest.created_at))
        self.assertIsNone(rows[self.viewer.username]['last_sign_in'])
        self.assertEqual((rows[self.owner.username]['you'], rows[self.owner.username]['can_change']), (True, False))
        self.assertEqual(rows[self.reviewer.username]['can_change'], True)
        body = answer.content.decode()
        for secret in ('pbkdf2', 'argon2', '"password"', self.outsider.username, 'synthetic-pass-123!'):
            self.assertNotIn(secret, body)
        self.assertEqual([hit for hit in self.sc.scan_json(answer.json(), self.sc.scan_context())
                          if hit['severity'] == 'hard'], [])

    def test_reviewers_viewers_and_strangers_are_refused(self):
        for label, user in (('reviewer', self.reviewer), ('viewer', self.viewer), ('agent', self.agent)):
            client = signed_in(user)
            with self.subTest(label):
                listed = client.get('/api/members')
                self.assertEqual((listed.status_code, listed.json()['error']), (403, api.OWNERS_ONLY))
                changed = self.access(client, self.viewer, False)
                self.assertEqual(changed.status_code, 403)
        self.assertEqual(Client(HTTP_HOST=CPT).get('/api/members').status_code, 401)
        self.assertTrue(Membership.objects.get(user=self.viewer).active)
        self.assertFalse(models.AuditEvent.objects.filter(event__startswith='member.').exists())

    def test_the_session_says_who_may_manage_the_team(self):
        self.assertTrue(signed_in(self.owner).get('/api/session').json()['can_manage_team'])
        self.assertFalse(signed_in(self.reviewer).get('/api/session').json()['can_manage_team'])
        self.assertFalse(signed_in(self.viewer).get('/api/session').json()['can_manage_team'])


class AccessTests(MembersCase):
    def test_an_owner_turns_a_reviewer_off_who_loses_the_practice_at_the_next_request(self):
        reviewer = signed_in(self.reviewer)
        self.assertEqual(reviewer.get('/api/session').status_code, 200)
        answer = self.access(signed_in(self.owner), self.reviewer, False)
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(self.sc.shape_problems(answer.json(), self.sc.CONTRACT['member_access']), [])
        self.assertEqual((answer.json()['member']['login'], answer.json()['member']['active']),
                         (self.reviewer.username, False))
        self.assertFalse(Membership.objects.get(user=self.reviewer).active)
        self.assertTrue(User.objects.get(pk=self.reviewer.pk).is_active)  # never the account itself
        self.assertNotEqual(reviewer.get('/api/session').status_code, 200)
        self.assertEqual(sessions_of(self.reviewer), 0)  # it was their only practice: every session ended
        event = models.AuditEvent.objects.get(event='member.access_off')
        self.assertEqual((event.workspace_id, event.actor_id, event.encounter_id), (self.ws.pk, self.owner.pk, None))
        self.assertEqual((event.data['user'], event.data['role'], event.data['sessions_ended']),
                         (str(self.reviewer.pk), Membership.REVIEWER, 1))
        back = self.access(signed_in(self.owner), self.reviewer, True)
        self.assertEqual((back.status_code, back.json()['member']['active']), (200, True))
        self.assertTrue(Membership.objects.get(user=self.reviewer).active)
        self.assertEqual(models.AuditEvent.objects.filter(event='member.access_on').count(), 1)
        again = self.access(signed_in(self.owner), self.reviewer, True)  # nothing to change: nothing recorded
        self.assertEqual(again.status_code, 200)
        self.assertEqual(models.AuditEvent.objects.filter(event__startswith='member.').count(), 2)

    def test_a_person_in_two_practices_keeps_the_other_one(self):
        Membership.objects.create(user=self.reviewer, workspace=self.other_ws, role=Membership.VIEWER)
        reviewer = signed_in(self.reviewer)
        self.access(signed_in(self.owner), self.reviewer, False)
        self.assertTrue(User.objects.get(pk=self.reviewer.pk).is_active)
        self.assertTrue(Membership.objects.get(user=self.reviewer, workspace=self.other_ws).active)
        self.assertEqual(sessions_of(self.reviewer), 1)
        self.assertEqual(reviewer.get('/api/session').json()['workspace']['id'], str(self.other_ws.pk))
        self.assertNotIn('sessions_ended', models.AuditEvent.objects.get(event='member.access_off').data)

    def test_the_owner_cannot_turn_off_themself(self):
        answer = self.access(signed_in(self.owner), self.owner, False)
        self.assertEqual((answer.status_code, answer.json()['error']), (409, api.OWN_ACCESS))
        self.assertTrue(Membership.objects.get(user=self.owner).active)

    def test_the_last_active_owner_is_never_turned_off(self):
        # two owners at once: each request began while both were active owners; the one decided second finds the
        # other already off, so turning that last active owner off is refused (the change is decided under one lock)
        second = f.member(self.ws, role=Membership.OWNER)
        first_membership = Membership.objects.get(user=self.owner)
        stale = Membership.objects.get(user=second)  # the second owner's request, read before the first one's change
        self.assertEqual(self.access(signed_in(self.owner), second, False).status_code, 200)
        with self.assertRaises(api.ApiError) as refused:
            api._set_member_access(stale, self.owner.pk, False, second)
        self.assertEqual((refused.exception.status, refused.exception.message), (409, api.LAST_OWNER))
        first_membership.refresh_from_db()
        self.assertTrue(first_membership.active)
        self.assertEqual(Membership.objects.filter(workspace=self.ws, role=Membership.OWNER, active=True).count(), 1)

    def test_another_practices_person_is_not_found(self):
        answer = self.access(signed_in(self.owner), self.outsider, False)
        self.assertEqual(answer.status_code, 404)
        self.assertTrue(Membership.objects.get(user=self.outsider).active)
        missing = signed_in(self.owner).post(f'/api/members/{uuid.uuid4()}/access', data=json.dumps({'active': False}),
                                             content_type='application/json')
        self.assertEqual(missing.status_code, 404)

    def test_the_body_must_say_true_or_false(self):
        client = signed_in(self.owner)
        for body in ({}, {'active': 'false'}, {'active': 0}, {'active': None}):
            with self.subTest(body=body):
                answer = client.post(f'/api/members/{self.reviewer.pk}/access', data=json.dumps(body),
                                     content_type='application/json')
                self.assertEqual((answer.status_code, answer.json()['error']), (400, api.ACTIVE_REQUIRED))
        self.assertEqual(client.get(f'/api/members/{self.reviewer.pk}/access').status_code, 405)
        self.assertTrue(Membership.objects.get(user=self.reviewer).active)

    def test_the_csrf_check_holds(self):
        strict = Client(HTTP_HOST=CPT, enforce_csrf_checks=True)
        strict.force_login(self.owner)
        ops.mark_signed_in(strict, door='cpt')
        self.assertEqual(self.access(strict, self.reviewer, False).status_code, 403)
        self.assertTrue(Membership.objects.get(user=self.reviewer).active)

    def test_the_owners_change_shows_in_the_practices_activity(self):
        self.access(signed_in(self.owner), self.viewer, False)
        operator_user = f.user('platform-operator')
        page = ops.admin_client(operator_user).get(f'/ops/activity?workspace={self.ws.pk}').content.decode()
        self.assertIn('Access turned off by an owner', page)
        self.assertIn(self.owner.label(), page)


class ConcurrentOwnersTests(TransactionTestCase):
    """Two owners turning each other off at the same moment: the changes are decided one at a time under the
    practice's lock, so the practice always keeps an active owner."""

    def test_two_owners_turning_each_other_off_leave_one_active(self):
        ws = f.workspace('Synthetic concurrent practice')
        first, second = f.member(ws, role=Membership.OWNER), f.member(ws, role=Membership.OWNER)
        stale = {first.pk: Membership.objects.get(user=first), second.pk: Membership.objects.get(user=second)}
        barrier, results = threading.Barrier(2), {}

        def turn_off(owner, other):
            try:
                barrier.wait(timeout=10)
                api._set_member_access(stale[owner.pk], other.pk, False, owner)
                results[owner.pk] = 'changed'
            except api.ApiError as exc:
                results[owner.pk] = exc.status
            finally:
                connection.close()

        threads = [threading.Thread(target=turn_off, args=(first, second)),
                   threading.Thread(target=turn_off, args=(second, first))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(sorted(map(str, results.values())), ['409', 'changed'])
        self.assertEqual(Membership.objects.filter(workspace=ws, role=Membership.OWNER, active=True).count(), 1)


class LastSignInTests(MembersCase):
    def test_an_old_sign_in_of_another_account_with_the_same_name_in_another_case_is_not_read(self):
        models.LoginAttempt.objects.create(username=self.reviewer.username.upper(), client='198.51.100.7',
                                           succeeded=True)
        row = {item['login']: item for item in signed_in(self.owner).get('/api/members').json()['members']}
        self.assertIsNone(row[self.reviewer.username]['last_sign_in'])
        old = timezone.now() - timedelta(days=400)
        attempt = models.LoginAttempt.objects.create(username=self.reviewer.username, client='198.51.100.7',
                                                     succeeded=True)
        models.LoginAttempt.objects.filter(pk=attempt.pk).update(created_at=old)
        row = {item['login']: item for item in signed_in(self.owner).get('/api/members').json()['members']}
        self.assertEqual(row[self.reviewer.username]['last_sign_in'], iso(old))
