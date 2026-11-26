"""Refutation round 2 of release 1, repair builder a2's repairs (sign-in rows, the members list, the key step's lookup, a
read repeated over midnight), each pinned by its finding's own input (refute-r2/findings-round2.json).

phi-3         a member's list read repeated just after midnight UTC was counted on the previous day's record, so the new
              day's reads page said 'No read recorded for this choice'. A repeat is now counted only on a record of its
              own UTC day - the day the reads page files a read under.
              The same class for the document poll (TEC-9 (4), the lead's item 3): a poll writes no row within
              READ_AUDIT_DETAIL_DEDUPE_SECONDS of a read of the same sign-in only on that read's own UTC day.
phi-0         GET /api/members ran one LoginAttempt query per membership (about 1 ms each). The practice's last sign-ins
              are now one statement, one index lookup a name, whatever the membership count and the rows a name holds.
phi-1         the admin door's key step read and settled its LoginAttempt by sign_in_ref, which no index covered: a
              sequential scan of the whole table. A partial index over the pending rows now serves both statements.
regression-1  a known address (throttle check e) was read from the name's newest 1,000 successful sign-ins only, so an
              office older than those was no longer known and others' failures delayed the doctor there. Each row now
              carries its client's key, so any sign-in of the name from that IPv4 address or IPv6 /64 within
              KNOWN_DEVICE_DAYS is found by one index lookup; an older revision's rows, which carry none, are read by
              their address.

Synthetic accounts, practices, titles and rows only."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest import mock

from django.conf import settings
from django.db import connection
from django.db.models import Max
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import customer, models, read_audit, request_meta, second_factor, throttle
from tests.support import coding as f
from tests.support import operator as ops
from tests.test_frontend import PLAIN_STATIC
from tests.test_read_audit import ReadCase, member_client
from tests.test_second_factor import admin_client, enrolled_operator, options_of, password_step

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
        # release 2 (R2-21): the record names the documents the page showed, newest first, and the list it was
        self.assertEqual(first.encounter_ids, [str(pk) for pk in models.Encounter.objects.filter(workspace=self.ws)
                                               .order_by('-created_at', '-pk').values_list('pk', flat=True)])
        self.assertEqual(first.filters, {'list': 'documents', 'before': None})
        self.assertIn('read again 2 times by this sign-in, the last at 2026-11-21 12:00:40',
                      self.page('?day=2026-11-21'))



class DetailPollDayTests(ReadCase):
    """phi-3's class for the document's poll (TEC-9 (4)): a poll (X-CPT-Poll: 1) of a document this sign-in read within
    READ_AUDIT_DETAIL_DEDUPE_SECONDS writes no row of its own - only when that read is of the poll's own UTC day, the day
    the reads page files a read under. The finding's shape: the document read at 23:59:40, polled at 23:59:50 and again
    at 00:00:20 the next day."""

    def details(self):
        return [row.created_at for row in models.AccessRecord.objects.filter(
            view=read_audit.MEMBER_DETAIL, actor_id=self.reviewer.pk).order_by('created_at', 'pk')]

    def member_at(self, moment):
        with at(moment):  # signed in a moment before its reads (a session's times are never in the future)
            return member_client(self.reviewer)

    def read_at(self, member, moment, *, poll=True):
        with at(moment):
            answer = member.get(f'/api/encounters/{self.text.pk}', **({'HTTP_X_CPT_POLL': '1'} if poll else {}))
        self.assertEqual(answer.status_code, 200)

    def day_rows(self, day):
        auditor = ops.admin_client(f.user(f'a2-poll-auditor-{day}'))
        body = auditor.get(f'/ops/activity/reads?day={day}&kind=member.detail').content.decode()
        return body.count('Document<br>')  # a member.detail row (the kind's label, then a break)

    def test_a_poll_just_after_midnight_is_a_read_of_the_new_day(self):
        evening = datetime(2026, 11, 20, 23, 59, 40, tzinfo=UTC)
        member = self.member_at(evening - timedelta(seconds=5))
        self.read_at(member, evening, poll=False)  # the document opened at 23:59:40
        self.read_at(member, evening + timedelta(seconds=10))  # polled at 23:59:50: no row of its own
        self.read_at(member, evening + timedelta(seconds=40))  # polled at 00:00:20 on the 21st: a row of the 21st
        self.assertEqual(self.details(), [evening, evening + timedelta(seconds=40)])
        self.assertEqual((self.day_rows('2026-11-20'), self.day_rows('2026-11-21')), (1, 1))

    def test_the_poll_boundary_is_the_reads_pages_own_to_the_microsecond(self):
        evening = datetime(2026, 11, 20, 23, 59, 30, tzinfo=UTC)
        member = self.member_at(evening - timedelta(seconds=5))
        self.read_at(member, evening, poll=False)
        self.read_at(member, datetime(2026, 11, 20, 23, 59, 59, 999999, tzinfo=UTC))  # the 20th's last moment: no row
        midnight = datetime(2026, 11, 21, tzinfo=UTC)
        self.read_at(member, midnight)  # the 21st's first moment: a row of the 21st
        self.assertEqual(self.details(), [evening, midnight])

    def test_a_poll_within_one_day_still_writes_at_most_one_row_a_minute(self):
        noon = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
        member = self.member_at(noon - timedelta(seconds=5))
        self.read_at(member, noon, poll=False)
        for second in (20, 59):
            self.read_at(member, noon + timedelta(seconds=second))
        self.assertEqual(self.details(), [noon])
        self.read_at(member, noon + timedelta(seconds=61))  # past the minute: a row of its own
        self.assertEqual(self.details(), [noon, noon + timedelta(seconds=61)])

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


# --- phi-1: the admin door's key step finds its pending row by an index -------------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class PendingSettleIndexTests(TestCase):
    """The finding's input, scaled: LoginAttempt holds 20,000 rows, each with its own sign-in reference as Door.record
    writes one for every attempt; an operator's password step at the admin door leaves its pending row, and the key step
    settles it - signed in (complete_sign_in: an UPDATE), or failed at the fifth wrong key (note_failure: a SELECT, then
    an UPDATE). Each statement that reads LoginAttempt by sign_in_ref is planned on the pending rows' index."""

    WRONG_ORIGIN = 'https://x.example'

    def setUp(self):
        self.operator, self.key = enrolled_operator('a2-pending-operator')
        outcomes = (models.LoginAttempt.SIGNED_IN, models.LoginAttempt.WRONG_PASSWORD, models.LoginAttempt.NO_ACCESS)
        models.LoginAttempt.objects.bulk_create([models.LoginAttempt(
            username=f'synthetic-{index % 50}', client=f'198.51.100.{index % 200}', door='cpt',
            outcome=outcomes[index % 3], succeeded=index % 3 == 0, sign_in_ref=uuid.uuid4())
            for index in range(20_000)], batch_size=5000)
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE studio_loginattempt')

    def pending(self):
        client = admin_client()
        first = password_step(client, self.operator)
        self.assertEqual((first.status_code, first['Location']), (302, '/login/second-factor'))
        return client, client.session[second_factor.PENDING]['ref']

    def key_step(self, client, **assertion):
        credential = json.dumps(self.key.assertion(options_of(client), **assertion))
        with CaptureQueriesContext(connection) as seen:
            answer = client.post('/login/second-factor', {'credential': credential})
        return answer, [item['sql'] for item in seen.captured_queries
                        if 'studio_loginattempt' in item['sql'] and '"sign_in_ref"' in item['sql']]

    def assert_on_the_pending_index(self, statements):
        self.assertTrue(statements)
        for sql in statements:
            with self.subTest(sql=sql[:60]):
                plan = explain(sql)  # the plan only: the statement is not run again
                self.assertNotIn('Seq Scan', plan)
                self.assertIn('studio_login_pending_ref', plan)

    def test_the_key_step_settles_its_attempt_by_the_pending_rows_index(self):
        client, ref = self.pending()
        answer, statements = self.key_step(client)
        self.assertEqual(answer.status_code, 302)
        self.assertNotEqual(answer['Location'], '/login/?reason=key')
        self.assertEqual(models.LoginAttempt.objects.get(sign_in_ref=ref).outcome, models.LoginAttempt.SIGNED_IN)
        self.assertEqual([sql.split()[0] for sql in statements], ['UPDATE'])
        self.assert_on_the_pending_index(statements)

    def test_the_fifth_wrong_key_settles_its_attempt_by_the_pending_rows_index(self):
        client, ref = self.pending()
        for _ in range(settings.SECOND_FACTOR_ATTEMPTS - 1):
            answer, statements = self.key_step(client, origin=self.WRONG_ORIGIN)
            self.assertEqual((answer.status_code, statements), (400, []))
        answer, statements = self.key_step(client, origin=self.WRONG_ORIGIN)
        self.assertEqual((answer.status_code, answer['Location']), (302, '/login/?reason=key'))
        self.assertEqual(models.LoginAttempt.objects.get(sign_in_ref=ref).outcome,
                         models.LoginAttempt.SECOND_FACTOR_FAILED)
        self.assertEqual([sql.split()[0] for sql in statements], ['SELECT', 'UPDATE'])
        self.assert_on_the_pending_index(statements)


# --- regression-1: a known address is any sign-in of the name from that client key, however many the name made ------------

PASSWORD = 'synthetic-pass-123!'  # tests.support.coding.user's
OFFICE, HOME, THIEF, NEVER_USED = '203.0.113.21', '198.51.100.22', '192.0.2.23', '203.0.113.200'
CPT_HOST = 'cpt.quillmd.com'


def keyed_attempt(username, client, **fields):
    """A successful sign-in row as release 1 writes it (LoginAttempt.save writes its client's key; bulk rows name it)."""
    return models.LoginAttempt(username=username, client=client, client_key=models.LoginAttempt.key_of(client),
                               succeeded=True, door='cpt', outcome=models.LoginAttempt.SIGNED_IN, **fields)


def older_attempt(username, client):
    """A successful sign-in row as the revision before release 1 wrote it: succeeded alone, no key, no door."""
    return models.LoginAttempt(username=username, client=client, succeeded=True)


@override_settings(STORAGES=PLAIN_STATIC)
class KnownAddressTests(TestCase):
    """The finding's input: the doctor signed in from the office 89 (or 30) days ago - inside KNOWN_DEVICE_DAYS - and
    1,000 times since from home; someone elsewhere arms the username delay with five wrong passwords; the doctor, back at
    the office in a browser without the device cookie, types the right password."""

    def setUp(self):
        self.ws = f.workspace()
        self.doctor = f.member(self.ws, role=models.Membership.REVIEWER)
        self.name = self.doctor.username

    def seed(self, office, office_days, home_count, *, made=keyed_attempt, home=HOME):
        """One sign-in from ``office`` ``office_days`` ago, then ``home_count`` from ``home``, spread evenly from an hour
        after it to an hour ago (each newer than the office's), every row made by ``made``."""
        models.LoginAttempt.objects.all().delete()
        models.RateWindow.objects.all().delete()
        now = timezone.now()
        office_at = now - timedelta(days=office_days)
        (row,) = models.LoginAttempt.objects.bulk_create([made(self.name, office)])
        models.LoginAttempt.objects.filter(pk=row.pk).update(created_at=office_at)
        models.LoginAttempt.objects.bulk_create([made(self.name, home) for _ in range(home_count)], batch_size=2000)
        first, last = office_at + timedelta(hours=1), now - timedelta(hours=1)
        step = (last - first) / max(1, home_count - 1)
        with connection.cursor() as cursor:
            cursor.execute('UPDATE studio_loginattempt AS t SET created_at = %s + (r.n - 1) * %s FROM '
                           '(SELECT id, row_number() OVER (ORDER BY id) AS n FROM studio_loginattempt WHERE id <> %s) '
                           'AS r WHERE t.id = r.id', [first, step, row.pk])
        newer = models.LoginAttempt.objects.filter(username=self.name, succeeded=True, created_at__gt=office_at)
        self.assertEqual(newer.count(), home_count)  # every home sign-in is newer than the office's

    def attempt(self, address, password=PASSWORD):
        return Client(HTTP_HOST=CPT_HOST).post('/login/', {'username': self.name, 'password': password},
                                               REMOTE_ADDR=address)

    def arm(self):
        for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
            self.assertEqual(self.attempt(THIEF, 'not the password at all').status_code, 400)

    def assert_signs_in(self, address):
        answer = self.attempt(address)
        self.assertEqual((answer.status_code, answer.get('Location')), (302, '/'), answer.content[:200])

    def assert_delayed(self, address):
        answer = self.attempt(address)
        self.assertEqual(answer.status_code, 400)
        self.assertIn('Too many attempts. Wait', answer.content.decode())

    def test_an_office_older_than_the_names_newest_thousand_sign_ins_is_known(self):
        for made in (keyed_attempt, older_attempt):
            for office_days, home_count in ((89, 1000), (30, 1000), (30, 1500)):
                with self.subTest(made=made.__name__, office_days=office_days, home_count=home_count):
                    self.seed(OFFICE, office_days, home_count, made=made)
                    self.arm()
                    self.assert_signs_in(OFFICE)
                    self.assert_delayed(NEVER_USED)  # the control: the delay really is armed

    def test_another_address_of_the_offices_ipv6_slash_64_is_known_and_another_slash_64_is_not(self):
        office, sibling = '2001:db8:1:2::5', '2001:db8:1:2:abcd:ef01:2345:6789'  # one /64, two addresses
        self.seed(office, 30, 1500, home='2001:db8:77:1::9')
        self.arm()
        self.assert_signs_in(sibling)
        self.assert_delayed('2001:db8:1:3::5')  # the next /64
        self.assert_delayed('2001:db8:1::5')  # 2001:db8:1:0::/64, whose text shares the office's start
        # a row an older revision wrote carries no key: it is found by its own address, at any age in the window and
        # behind any number of newer rows; another address of its /64 is not (the one thing this read leaves out), and
        # is again from the /64's first sign-in that release 1 records
        self.seed(office, 30, 1500, made=older_attempt, home='2001:db8:77:1::9')
        self.arm()
        self.assert_delayed(sibling)
        self.assert_signs_in(office)
        self.assert_signs_in(sibling)

    def test_an_ipv4_mapped_address_is_its_ipv4_address_both_ways(self):
        for made in (keyed_attempt, older_attempt):
            for stored, requested in (('::ffff:203.0.113.21', OFFICE), (OFFICE, '::ffff:203.0.113.21')):
                with self.subTest(made=made.__name__, stored=stored):
                    self.seed(stored, 30, 1000, made=made)
                    self.arm()
                    self.assert_signs_in(requested)

    def test_what_a_known_address_still_never_is(self):
        self.seed(OFFICE, settings.KNOWN_DEVICE_DAYS + 1, 10)  # too long ago
        models.LoginAttempt.objects.bulk_create([
            models.LoginAttempt(username=self.name, client='192.0.2.83', client_key='192.0.2.83', succeeded=False,
                                door='cpt', outcome=models.LoginAttempt.WRONG_PASSWORD),  # a failure is no sign-in
            keyed_attempt('somebody-else', '192.0.2.84'),  # another name's sign-in
            models.LoginAttempt(username=self.name, client='192.0.2.85', client_key='192.0.2.85', succeeded=False,
                                door='admin', outcome=models.LoginAttempt.SECOND_FACTOR_PENDING)])  # never settled
        self.arm()
        for address in (OFFICE, '192.0.2.83', '192.0.2.84', '192.0.2.85'):
            with self.subTest(address=address):
                self.assert_delayed(address)
        self.assert_signs_in(HOME)

    def test_every_attempt_the_doors_write_carries_its_client_key(self):
        cases = (('2001:db8:5:6::7', PASSWORD), ('192.0.2.50', 'not the password'), ('::ffff:192.0.2.51', PASSWORD))
        for address, password in cases:
            self.attempt(address, password)
        Client(HTTP_HOST=CPT_HOST).post('/login/', {'username': 'nobody-at-all', 'password': 'x'},
                                        REMOTE_ADDR='not-an-address')
        operator, key = enrolled_operator('a2-key-operator')
        client = admin_client()
        self.assertEqual(client.post('/login/', {'username': operator.username, 'password': PASSWORD},
                                     REMOTE_ADDR='2001:db8:9:9::1')['Location'], '/login/second-factor')
        credential = json.dumps(key.assertion(options_of(client)))
        self.assertEqual(client.post('/login/second-factor', {'credential': credential}).status_code, 302)
        rows = list(models.LoginAttempt.objects.order_by('pk'))
        self.assertEqual([row.outcome for row in rows],
                         ['signed_in', 'wrong_password', 'signed_in', 'unknown_account', 'signed_in'])
        for row in rows:
            with self.subTest(client=row.client):
                self.assertIsNotNone(row.client_key)
                self.assertEqual(row.client_key, throttle.key_of_address(row.client))
        self.assertEqual([row.client_key for row in rows[:3]], ['2001:db8:5:6::/64', '192.0.2.50', '192.0.2.51'])
        self.assertEqual(len(rows[3].client_key), 64)  # no address: its keyed hash, never the text
        for text in ('192.0.2.1', '2001:DB8:0:0:1::1', '::ffff:c000:201', '::1', '', 'not-an-address', '1.2.3.04'):
            with self.subTest(text=text):
                self.assertEqual(models.LoginAttempt.key_of(text), throttle.key_of_address(text))

    def door(self, address):
        return throttle.Door(RequestFactory().post('/login/', REMOTE_ADDR=address), request_meta.CPT, self.name)

    def reads(self, address, known):
        """Door.known_address() for ``address`` answers ``known``; [(the index its scan read, the rows it read)] for each
        statement it ran, EXPLAIN (ANALYZE)d."""
        with CaptureQueriesContext(connection) as seen:
            self.assertEqual(self.door(address).known_address(), known)
        found = []
        for item in seen.captured_queries:
            plan = explain(item['sql'], analyze=True)
            scans = [line for line in plan.splitlines() if re.search(r'Scan.* on studio_loginattempt', line)]
            self.assertEqual(len(scans), 1, plan)
            index = re.search(r'using (\w+)', scans[0])
            found.append((index.group(1) if index else scans[0].split()[1],
                          int(re.search(r'actual time=\S+ rows=(\d+) loops=1\)', scans[0]).group(1))))
        return found

    def test_the_known_address_read_is_one_index_row_however_many_times_the_name_signed_in(self):
        rows = [keyed_attempt(self.name, f'198.51.100.{index % 200}') for index in range(20_000)]
        rows += [older_attempt(f'older-{index % 40}', '192.0.2.60') for index in range(2_000)]  # others' older rows
        rows += [older_attempt(self.name, OFFICE), older_attempt(self.name, '2001:db8:1:2::5')]  # two of the doctor's
        models.LoginAttempt.objects.bulk_create(rows, batch_size=5000)
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE studio_loginattempt')
        key, by_address = 'studio_login_name_key_ok', 'studio_login_name_keyless'
        cases = (  # (address, known, [(index, rows read)] of each statement)
            ('198.51.100.7', True, [(key, 1)]),  # a row release 1 wrote
            (OFFICE, True, [(key, 0), (by_address, 1)]),  # an older revision's row, by its address
            ('::ffff:203.0.113.21', True, [(key, 0), (by_address, 1)]),  # the same, IPv4-mapped
            ('2001:db8:1:2::5', True, [(key, 0), (by_address, 1)]),  # an older revision's IPv6 row, its own address
            ('2001:db8:1:2::77', False, [(key, 0), (by_address, 0)]),  # another address of that /64
            (NEVER_USED, False, [(key, 0), (by_address, 0)]),
            ('2001:db8:9:9::1', False, [(key, 0), (by_address, 0)]))
        for address, known, expected in cases:
            with self.subTest(address=address):
                self.assertEqual(self.reads(address, known), expected)

    def test_an_older_revisions_rows_are_read_by_one_lookup_however_many(self):
        # avail-5's shape, written as an older revision writes rows (no key): 20,000 of the doctor's own sign-ins from
        # one IPv6 /64 and the office (IPv4, and another IPv6 /64) signed in from before all of them; each read is one
        # equality lookup that reads at most one row
        rows = [older_attempt(self.name, OFFICE), older_attempt(self.name, '2001:db8:1:2::5')]
        rows += [older_attempt(self.name, f'2001:db8:77:1::{index % 500 + 1:x}') for index in range(20_000)]
        models.LoginAttempt.objects.bulk_create(rows, batch_size=5000)
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE studio_loginattempt')
        by_address = 'studio_login_name_keyless'
        for address, known in ((OFFICE, True), (NEVER_USED, False), ('2001:db8:1:2::5', True),
                               ('2001:db8:77:1::1f4', True), ('2001:db8:77:1::abc', False), ('2001:db8:1:2::9', False)):
            with self.subTest(address=address):
                self.assertEqual(self.reads(address, known)[1:], [(by_address, int(known))])
        models.LoginAttempt.objects.bulk_create([keyed_attempt(self.name, '2001:db8:1:2::abcd')])  # one sign-in now
        self.assertEqual(self.reads('2001:db8:1:2::9', True), [('studio_login_name_key_ok', 1)])
