"""Refutation round 2 of release 1, repair builder a2's repairs (sign-in rows, the members list, the key step's lookup, a
read repeated over midnight), each pinned by its finding's own input (refute-r2/findings-round2.json).

phi-3         a member's list read repeated just after midnight UTC was counted on the previous day's record, so the new
              day's reads page said 'No read recorded for this choice'. A repeat is now counted only on a record of its
              own UTC day - the day the reads page files a read under.
phi-0         GET /api/members ran one LoginAttempt query per membership (about 1 ms each). The practice's last sign-ins
              are now one statement, one index lookup a name, whatever the membership count and the rows a name holds.

Synthetic accounts, practices, titles and rows only."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest import mock

from django.db import connection
from django.db.models import Max
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import customer, models, read_audit
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_read_audit import member_client

UTC = dt_timezone.utc
LIST = '/api/encounters'
LIST_ROW = 'Document list<br>'  # a member.list row on the reads page (ops_activity_reads.html: the kind, then a break)
NO_READ = 'No read recorded'


def at(moment):
    return mock.patch.object(timezone, 'now', return_value=moment)


# --- phi-3: a list read repeated over midnight is a record of its own day ------------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class ListRepeatDayTests(TestCase):
    """The finding's input: one session lists its practice at 23:59:50 UTC and again at 00:00:20, inside
    READ_AUDIT_LIST_REPEAT_SECONDS; an operator then reads the reads page of each day."""

    def setUp(self):
        self.ws = f.workspace('Synthetic practice A2 repeats')
        self.reviewer = f.member(self.ws)
        f.encounter(self.ws, self.reviewer, title='ZZ-A2-TITLE-A synthetic note')
        f.encounter(self.ws, self.reviewer, title='ZZ-A2-TITLE-B synthetic note')
        self.auditor = ops.admin_client(f.user('a2-repeat-auditor'))

    def lists(self):
        return list(models.AccessRecord.objects.filter(view=read_audit.MEMBER_LIST, actor_id=self.reviewer.pk)
                    .order_by('created_at', 'pk'))

    def page(self, query):
        answer = self.auditor.get('/ops/activity/reads' + query)
        self.assertEqual(answer.status_code, 200)
        return answer.content.decode()

    def member_at(self, moment):
        with at(moment):  # signed in a moment before its reads (a session's times are never in the future)
            return member_client(self.reviewer)

    def list_at(self, member, moment):
        with at(moment):
            answer = member.get(LIST)
        self.assertEqual(answer.status_code, 200)
        return answer

    def test_a_list_read_repeated_just_after_midnight_is_a_record_of_the_new_day(self):
        evening = datetime(2026, 11, 20, 23, 59, 40, tzinfo=UTC)
        member = self.member_at(evening)
        self.list_at(member, evening + timedelta(seconds=10))  # 23:59:50 on the 20th
        second = self.list_at(member, evening + timedelta(seconds=40))  # 00:00:20 on the 21st, 30 s later
        self.assertIn(b'ZZ-A2-TITLE-A', second.content)  # the practice's list was served again
        rows = self.lists()
        self.assertEqual([row.created_at for row in rows],
                         [evening + timedelta(seconds=10), evening + timedelta(seconds=40)])
        self.assertFalse(models.AccessRecordRepeat.objects.filter(record_id__in=[row.pk for row in rows]).exists())
        # what an auditor reads: each day's page holds that day's read, by account, by kind and unfiltered
        for query in (f'?day=2026-11-21&account={self.reviewer.pk}', '?day=2026-11-21&kind=member.list',
                      '?day=2026-11-21', f'?day=2026-11-20&account={self.reviewer.pk}'):
            with self.subTest(query=query):
                body = self.page(query)
                self.assertEqual(body.count(LIST_ROW), 1)
                self.assertNotIn(NO_READ, body)
                self.assertNotIn('read again', body)
        self.assertIn('2026-11-21 00:00:20', self.page('?day=2026-11-21'))
        self.assertNotIn('2026-11-21 00:00:20', self.page('?day=2026-11-20'))

    def test_the_day_boundary_is_the_reads_pages_own_to_the_microsecond(self):
        evening = datetime(2026, 11, 20, 23, 59, 30, tzinfo=UTC)
        member = self.member_at(evening - timedelta(seconds=5))
        self.list_at(member, evening)
        self.list_at(member, datetime(2026, 11, 20, 23, 59, 59, 999999, tzinfo=UTC))  # the last moment of the 20th
        (first,) = self.lists()
        repeat = models.AccessRecordRepeat.objects.get(record_id=first.pk)
        self.assertEqual((repeat.repeats, repeat.last_at), (1, datetime(2026, 11, 20, 23, 59, 59, 999999, tzinfo=UTC)))
        midnight = datetime(2026, 11, 21, tzinfo=UTC)
        self.list_at(member, midnight)  # the first moment of the 21st: a record of its own, filed under the 21st
        self.assertEqual([row.created_at for row in self.lists()], [evening, midnight])
        self.assertEqual(models.AccessRecordRepeat.objects.get().repeats, 1)
        self.assertEqual(self.page('?day=2026-11-21').count(LIST_ROW), 1)
        body = self.page('?day=2026-11-20')
        self.assertEqual(body.count(LIST_ROW), 1)
        self.assertIn('read again 1 time by this sign-in, the last at 2026-11-20 23:59:59', body)

    def test_a_repeat_within_one_day_is_still_counted_on_its_record(self):
        noon = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
        member = self.member_at(noon - timedelta(seconds=5))
        for second in (0, 20, 40):
            self.list_at(member, noon + timedelta(seconds=second))
        (first,) = self.lists()
        repeat = models.AccessRecordRepeat.objects.get(record_id=first.pk)
        self.assertEqual((repeat.repeats, repeat.last_at), (2, noon + timedelta(seconds=40)))
        self.assertIn('read again 2 times by this sign-in, the last at 2026-11-21 12:00:40',
                      self.page('?day=2026-11-21'))


# --- phi-0: the practice's last sign-ins in one statement -----------------------------------------------------------------

def shipped_last_sign_ins(usernames) -> dict:
    """3048931b5's customer.last_sign_ins, verbatim: one aggregate over every succeeded row of the names - the answer the
    members list must still give."""
    return dict(models.LoginAttempt.objects.filter(succeeded=True, username__in=list(usernames)).values('username')
                .annotate(last=Max('created_at')).values_list('username', 'last'))


def explain(sql, *, analyze=False):
    with connection.cursor() as cursor:
        cursor.execute(('EXPLAIN (ANALYZE, BUFFERS OFF) ' if analyze else 'EXPLAIN ') + sql)
        return '\n'.join(row[0] for row in cursor.fetchall())


@override_settings(STORAGES=PLAIN_STATIC)
class MembersLastSignInTests(TestCase):
    """The finding's input: GET /api/members by a practice's owner, for practices of 5 and 60 memberships."""

    def practice(self, size):
        ws = f.workspace(f'Synthetic practice A2 members {size}')
        owner = f.member(ws, role=models.Membership.OWNER)
        people = [owner, *(f.member(ws) for _ in range(size - 1))]
        now = timezone.now()
        rows = []
        for index, person in enumerate(people[:-1]):  # the last person never signed in
            rows += [models.LoginAttempt(username=person.username, client='203.0.113.9', succeeded=True, door='cpt',
                                         outcome=models.LoginAttempt.SIGNED_IN) for _ in range(3)]
            rows.append(models.LoginAttempt(username=person.username, client='192.0.2.9', succeeded=False, door='cpt',
                                            outcome=models.LoginAttempt.WRONG_PASSWORD))  # never a sign-in
        models.LoginAttempt.objects.bulk_create(rows, batch_size=2000)
        with connection.cursor() as cursor:  # each row at its own time over the last 30 days; the failures newest
            cursor.execute("UPDATE studio_loginattempt SET created_at = %s - (id %% 997) * interval '43 minutes' "
                           "- (CASE WHEN succeeded THEN interval '1 hour' ELSE interval '0' END)", [now])
        client = Client(HTTP_HOST='cpt.quillmd.com')
        client.force_login(owner)
        ops.mark_signed_in(client, door='cpt')
        return client, people

    def members(self, client):
        with CaptureQueriesContext(connection) as seen:
            answer = client.get('/api/members')
        self.assertEqual(answer.status_code, 200)
        statements = [item['sql'] for item in seen.captured_queries if 'studio_loginattempt' in item['sql']]
        return answer.json()['members'], statements

    def test_the_members_list_reads_its_last_sign_ins_in_one_statement_whatever_the_practice_size(self):
        for size in (5, 60):
            with self.subTest(size=size):
                client, people = self.practice(size)
                members, statements = self.members(client)
                self.assertEqual(len(statements), 1, statements)
                expected = shipped_last_sign_ins(person.username for person in people)
                self.assertEqual(len(expected), size - 1)
                self.assertEqual({row['username']: row['last_sign_in'] for row in members},
                                 {person.username: customer.iso(expected.get(person.username)) for person in people})
                self.assertIsNone(next(row for row in members if row['username'] == people[-1].username)['last_sign_in'])

    def test_that_statement_reads_one_row_a_name_by_its_index_however_many_rows_a_name_holds(self):
        client, people = self.practice(5)
        owner = people[0]
        models.LoginAttempt.objects.bulk_create(  # the owner's own sign-ins hold most of the table (avail-5's shape)
            [models.LoginAttempt(username=owner.username, client=f'203.0.113.{index % 200}', succeeded=True,
                                 door='cpt', outcome=models.LoginAttempt.SIGNED_IN) for index in range(20_000)],
            batch_size=5000)
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE studio_loginattempt')
        members, (sql,) = self.members(client)
        self.assertEqual(len(members), 5)
        plan = explain(sql, analyze=True)
        self.assertNotIn('Seq Scan on studio_loginattempt', plan)
        scans = [line for line in plan.splitlines() if re.search(r'Scan.* on studio_loginattempt', line)]
        self.assertTrue(scans, plan)
        for line in scans:  # each name's lookup: the newest succeeded row alone, by the partial index
            self.assertIn('studio_login_name_signed_in', line)
            self.assertRegex(line, r'actual time=\S+ rows=[01] loops=5\)', plan)
        self.assertEqual(customer.last_sign_ins([owner.username, 'never-signed-in', owner.username]),
                         shipped_last_sign_ins([owner.username]))
