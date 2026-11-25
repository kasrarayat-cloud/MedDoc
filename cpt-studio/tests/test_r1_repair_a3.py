"""Refutation round 3 of release 1, repair builder a3's repairs, each pinned by its finding's own input
(refute-r3/findings-round3.json).

rows-0  known_address's LIMIT 1 lookups (LoginAttemptQuerySet.signed_in_from) were planned as a sequential scan of
        all of LoginAttempt when one name held most of the table and the request's address was common in it: the
        planner multiplies the two shares as if they were independent, expects thousands of matches, and costs a scan
        that stops at the first one as cheaper than the index; nothing matched, so the scan read every row - on every
        attempt for that name while its delay was armed, before the password is checked. Each statement is now ordered
        by its partial index's own columns: the key's statement in an order no other index gives, the older rows'
        statement in one that only indexes leading with the name give, so a plan that does not read that index in its
        order must sort every matching row before its first. The same class in latest_sign_ins (the members list):
        where one name holds the rows, its per-name lookup was planned as a backward scan by time, which read every row
        for a member who never signed in; it is ordered by the name first now. Every answer is the one round 2's
        statements give.

Synthetic accounts, practices and rows only. Each table here holds at most 30,000 rows, so ANALYZE reads every row and
the plans do not depend on its sample; inside a test's transaction no page is all-visible, the state that makes a scan
look cheapest beside an index."""
from __future__ import annotations

import re
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Max
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import models, request_meta, throttle
from tests.support import coding as f
from tests.test_frontend import PLAIN_STATIC

LA = models.LoginAttempt
CPT_HOST = 'cpt.quillmd.com'
PREPARED, ARMER, NEVER = '192.0.2.77', '198.51.100.9', '203.0.113.240'  # common in the table / arms the delay / unused
HOMES = ('203.0.113.11', '203.0.113.12', '203.0.113.13', '203.0.113.14')  # the owner's own sign-ins
HOMES_SQL = "(ARRAY['" + "','".join(HOMES) + "'])[g %% 4 + 1]"
OTHERS_SQL = dict(name_sql="'synthetic-member-' || (g %% 300)", client_sql="'198.51.100.' || (g %% 200 + 20)",
                  ok_sql='(g %% 3 <> 0)')
KEY_INDEX, KEYLESS_INDEX = 'studio_login_name_key_ok', 'studio_login_name_keyless'
SIGNED_IN_INDEX = 'studio_login_name_signed_in'
NAME_ADDRESS_INDEX = LA._meta.indexes[0].name  # (username, client, created_at), every row: it leads with the name


def explain(sql, *, analyze=False):
    with connection.cursor() as cursor:
        cursor.execute(('EXPLAIN (ANALYZE, BUFFERS OFF) ' if analyze else 'EXPLAIN ') + sql)
        return '\n'.join(row[0] for row in cursor.fetchall())


def insert_rows(*, keyed, name_sql, client_sql, ok_sql, count, params=(), span=89 * 86400, age=0):
    """``count`` LoginAttempt rows created over ``span`` seconds ending ``age`` seconds ago, the oldest first on disk:
    as Door.record writes them (``keyed``: door, outcome, reference and the client's key - for these IPv4 addresses the
    address itself), or as the revision before release 1 wrote them (succeeded alone, no key). ``name_sql``,
    ``client_sql`` and ``ok_sql`` are SQL over g, the row's number (1 to count)."""
    when = f"now() - (({age} + ({count} + 1 - g) * {span}::float8 / {count}) * interval '1 second')"
    with connection.cursor() as cursor:
        if keyed:
            cursor.execute('INSERT INTO studio_loginattempt (username, client, client_key, succeeded, door, outcome, '
                           f"sign_in_ref, created_at) SELECT {name_sql}, {client_sql}, {client_sql}, {ok_sql}, 'cpt', "
                           f"CASE WHEN {ok_sql} THEN 'signed_in' ELSE 'unknown_account' END, gen_random_uuid(), {when} "
                           f'FROM generate_series(1, {count}) g', list(params))
        else:
            cursor.execute('INSERT INTO studio_loginattempt (username, client, succeeded, created_at) SELECT '
                           f'{name_sql}, {client_sql}, {ok_sql}, {when} FROM generate_series(1, {count}) g',
                           list(params))


def fresh_table():
    """An empty LoginAttempt (TRUNCATE: a new file, so no page of an earlier shape is counted), inside the test's
    transaction, which rolls it back."""
    with connection.cursor() as cursor:
        cursor.execute('TRUNCATE studio_loginattempt')
    models.RateWindow.objects.all().delete()


def analyze():
    with connection.cursor() as cursor:
        cursor.execute('ANALYZE studio_loginattempt')


def scans_of(plan):
    return [line for line in plan.splitlines() if re.search(r'Scan.* on studio_loginattempt', line)]


class _RolledBack(Exception):
    """Rolls back the savepoint indexes_giving_the_order drops its indexes in."""


def indexes_giving_the_order(test, sql):
    """The indexes the planner reads ``sql`` in order of (fully, or in part under an Incremental Sort) as each one it
    chose is dropped in turn - in a savepoint rolled back, on the test database only - and the plan it falls back on
    when no index left gives any of that order: that plan sorts every matching row before its first (a Sort)."""
    dropped, plan = [], explain(sql)
    while not re.search(r'->  Sort ', plan):
        used = re.findall(r'Scan(?: Backward)? using (\w+) on studio_loginattempt', plan)
        test.assertEqual(len(used), 1, plan)
        test.assertLess(len(dropped), 6, plan)
        dropped.append(used[0])
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    for name in dropped:
                        cursor.execute(f'DROP INDEX {name}')
                plan = explain(sql)
                raise _RolledBack
        except _RolledBack:
            pass
    return dropped, plan


def a2_signed_in_from(username, client_key, since, client=''):
    """aacf52b5's LoginAttemptQuerySet.signed_in_from, verbatim in effect (round 2's two EXISTS statements): the answer
    the repaired read must still give."""
    if not client_key:
        return False
    signed_in = LA.objects.filter(username=username, succeeded=True, created_at__gte=since)
    if signed_in.filter(client_key=client_key).exists():
        return True
    spellings = [text for text in dict.fromkeys(LA.spellings_of(client_key, client)) if LA.key_of(text) == client_key]
    return bool(spellings) and signed_in.filter(client_key__isnull=True, client__in=spellings).exists()


# --- rows-0: known_address is read by its index whatever the rows' distribution ---------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class KnownAddressPlanTests(TestCase):
    """The finding's input, scaled to 30,000 rows (avail-5's shape: one owner's own sign-ins hold 84% of LoginAttempt,
    and someone's failed attempts of typed names from one address 8.4%; the owner never signed in from it), the
    verifier's (the owner 52.6%, the address 39.5%), and uniform rows (300 names over 200 addresses), each written as
    release 1 writes rows and as the revision before it did."""

    SHAPES = ('finding', 'balanced', 'uniform')

    def setUp(self):
        self.ws = f.workspace('Synthetic practice A3 known address')
        self.owner = f.member(self.ws, role=models.Membership.OWNER)

    def seed(self, shape, *, keyed):
        fresh_table()
        owner = self.owner.username
        if shape == 'finding':
            insert_rows(keyed=keyed, name_sql='%s', client_sql=HOMES_SQL, ok_sql='true', count=25_200, params=[owner])
            insert_rows(keyed=keyed, count=2_280, **OTHERS_SQL)
            insert_rows(keyed=keyed, name_sql="'typed-name-' || g", client_sql=f"'{PREPARED}'", ok_sql='false',
                        count=2_520)
        elif shape == 'balanced':
            insert_rows(keyed=keyed, name_sql='%s', client_sql=HOMES_SQL, ok_sql='true', count=15_780, params=[owner])
            insert_rows(keyed=keyed, name_sql="'typed-name-' || g", client_sql=f"'{PREPARED}'", ok_sql='false',
                        count=11_850)
            insert_rows(keyed=keyed, count=2_370, **OTHERS_SQL)
        else:  # uniform: the owner one name of 300 (from HOMES[2]), PREPARED one address of 200 the owner never used
            insert_rows(keyed=keyed,
                        name_sql="CASE WHEN g %% 300 = 7 THEN %s ELSE 'synthetic-member-' || (g %% 300) END",
                        client_sql=f"CASE WHEN g %% 300 = 7 THEN '{HOMES[2]}' WHEN g %% 200 = 9 THEN '{PREPARED}' "
                                   "ELSE '198.51.100.' || (g %% 200) END",
                        ok_sql='(g %% 3 <> 0 OR g %% 300 = 7)', count=30_000, params=[owner])
        analyze()
        self.assertFalse(LA.objects.filter(username=owner, client=PREPARED).exists())

    def door(self, address):
        return throttle.Door(RequestFactory().post('/login/', REMOTE_ADDR=address), request_meta.CPT,
                             self.owner.username)

    def statements(self, address, known):
        """Door.known_address() for ``address`` answers ``known``, as round 2's statements do; the statements it ran."""
        door = self.door(address)
        with CaptureQueriesContext(connection) as seen:
            self.assertEqual(door.known_address(), known)
        since = timezone.now() - timedelta(days=settings.KNOWN_DEVICE_DAYS)
        self.assertEqual(a2_signed_in_from(door.username, door.client_key, since, door.client), known)
        return [item['sql'] for item in seen.captured_queries]

    def assert_read_by(self, sql, index):
        plan = explain(sql, analyze=True)
        self.assertNotIn('Seq Scan', plan)
        self.assertNotIn('Rows Removed by Filter', plan)
        (scan,) = scans_of(plan)
        self.assertIn(f'using {index} ', scan, plan)
        self.assertRegex(scan, r'actual time=\S+ rows=[01] loops=1\)', plan)  # the first row in index order answers

    def test_each_statement_is_read_by_its_index_in_the_findings_shape_the_verifiers_and_uniform_rows(self):
        for keyed in (True, False):
            for shape in self.SHAPES:
                with self.subTest(shape=shape, rows='keyed' if keyed else 'older revision'):
                    self.seed(shape, keyed=keyed)
                    for address, known in ((PREPARED, False), (HOMES[2], True), (NEVER, False)):
                        statements = self.statements(address, known)
                        self.assertEqual(len(statements), 1 if known and keyed else 2, statements)
                        self.assert_read_by(statements[0], KEY_INDEX)
                        if len(statements) == 2:
                            self.assert_read_by(statements[1], KEYLESS_INDEX)

    def test_no_index_but_its_own_gives_the_keys_statement_its_order(self):
        # drop studio_login_name_key_ok and no index is left to read the statement in its order: the plan sorts every
        # matching row first - never a scan that stops at the first match, the plan the finding met
        for shape in ('finding', 'balanced'):
            with self.subTest(shape=shape):
                self.seed(shape, keyed=True)
                (sql, _) = self.statements(PREPARED, False)
                dropped, plan = indexes_giving_the_order(self, sql)
                self.assertEqual(dropped, [KEY_INDEX], plan)
                self.assertNotIn('Incremental Sort', plan)

    def test_only_indexes_that_lead_with_the_name_give_the_older_rows_statement_its_order(self):
        # the older rows' statement: an index that leads with the address or the time (studio_login_client_time,
        # studio_login_time, studio_login_result_time) never gives its order; each one that does leads with the name and
        # holds every row studio_login_name_keyless holds (so it reads more rows, never fewer)
        self.assertEqual(LA._meta.indexes[0].fields, ['username', 'client', 'created_at'])
        for shape in ('finding', 'balanced'):
            with self.subTest(shape=shape):
                self.seed(shape, keyed=False)
                (_, sql) = self.statements(PREPARED, False)
                dropped, plan = indexes_giving_the_order(self, sql)
                self.assertEqual(dropped[0], KEYLESS_INDEX, plan)
                self.assertLessEqual(set(dropped), {KEYLESS_INDEX, NAME_ADDRESS_INDEX, SIGNED_IN_INDEX}, plan)

    def test_the_findings_attempts_through_the_door_read_the_indexes(self):
        # the finding end to end: five wrong passwords from one address arm the owner's delay; each further attempt for
        # the owner's name from the typed names' address is refused before the password is checked, and its
        # known_address statements read their indexes, one row at most
        for keyed in (True, False):
            with self.subTest(rows='keyed' if keyed else 'older revision'):
                self.seed('finding', keyed=keyed)
                client = Client(HTTP_HOST=CPT_HOST)
                for _ in range(settings.SIGNIN_USER_DELAY_AFTER):
                    client.post('/login/', {'username': self.owner.username, 'password': 'not the password'},
                                REMOTE_ADDR=ARMER)
                with CaptureQueriesContext(connection) as seen:
                    answer = client.post('/login/', {'username': self.owner.username, 'password': 'not the password'},
                                         REMOTE_ADDR=PREPARED)
                self.assertEqual(answer.status_code, 400)
                self.assertIn('Too many attempts. Wait', answer.content.decode())
                reads = [item['sql'] for item in seen.captured_queries
                         if 'FROM "studio_loginattempt"' in item['sql'] and '"client_key"' in item['sql']]
                self.assertEqual(len(reads), 2, reads)
                self.assert_read_by(reads[0], KEY_INDEX)
                self.assert_read_by(reads[1], KEYLESS_INDEX)

    def test_every_answer_is_round_twos(self):
        # the IPv4, IPv6 /64 and older-revision cases a2 pinned, and those around them: what the repaired statements
        # answer is what round 2's two EXISTS statements answer, for every address and name asked
        now = timezone.now()
        name = self.owner.username
        rows = (  # (username, client, succeeded, written with its key, days ago)
            (name, '203.0.113.21', True, True, 1), (name, '2001:db8:1:2::5', True, True, 30),
            (name, '::ffff:192.0.2.51', True, True, 2), (name, '192.0.2.83', False, True, 1),
            (name, '192.0.2.86', True, True, settings.KNOWN_DEVICE_DAYS + 1),
            ('somebody-else', '192.0.2.84', True, True, 1),
            (name, '198.51.100.22', True, False, 3), (name, '::ffff:198.51.100.23', True, False, 4),
            (name, '2001:db8:7:8::9', True, False, 5), (name, 'not-an-address', True, False, 6))
        made = [(LA(username=username, client=address, succeeded=succeeded,
                    client_key=LA.key_of(address) if keyed else None, door='cpt' if keyed else None,
                    outcome=(LA.SIGNED_IN if succeeded else LA.WRONG_PASSWORD) if keyed else None),
                 now - timedelta(days=days)) for username, address, succeeded, keyed, days in rows]
        LA.objects.bulk_create([row for row, _ in made])
        for row, at in made:
            LA.objects.filter(pk=row.pk).update(created_at=at)
        since = now - timedelta(days=settings.KNOWN_DEVICE_DAYS)
        asked = ('203.0.113.21', '::ffff:203.0.113.21', '::ffff:cb00:7115', '2001:db8:1:2::abcd', '2001:db8:1:3::5',
                 '192.0.2.51', '::ffff:192.0.2.51', '192.0.2.83', '192.0.2.84', '192.0.2.86', '198.51.100.22',
                 '::ffff:198.51.100.22', '198.51.100.23', '::ffff:198.51.100.23', '2001:db8:7:8::9',
                 '2001:db8:7:8::10', '2001:DB8:7:8:0:0:0:9', 'not-an-address', '', NEVER, '::1')
        answers = set()
        for address in asked:
            key = request_meta.client_key(RequestFactory().get('/', REMOTE_ADDR=address))
            for username in (name, 'somebody-else', name.upper()):
                with self.subTest(address=address, username=username):
                    answer = LA.objects.signed_in_from(username, key, since, client=address)
                    self.assertEqual(answer, a2_signed_in_from(username, key, since, address))
                    answers.add(answer)
        self.assertEqual(answers, {True, False})  # both answers were asked for


# --- the same class in latest_sign_ins: the members list's last sign-ins ----------------------------------------------

@override_settings(STORAGES=PLAIN_STATIC)
class LatestSignInsPlanTests(TestCase):
    """avail-5's shape on the members list: the owner's own sign-ins are every row of LoginAttempt (30,000, the oldest
    first), and two members never signed in. The correlated lookup's estimate for each name is the table's rows over
    the names' count - every row, here - so a backward scan by time looked as cheap as the name's own index, and for a
    member who never signed in it read every row (refutation round 3; round 2's single statement, phi-0)."""

    def setUp(self):
        self.ws = f.workspace('Synthetic practice A3 members')
        # names of an e-mail's length (each index entry holds its name: the shorter the names, the nearer the costs)
        self.owner, self.invited, self.other = (f.user(f'synthetic.{who}.a3@example.org')
                                                for who in ('owner', 'invited', 'other'))  # two never signed in
        for person, role in ((self.owner, models.Membership.OWNER), (self.invited, models.Membership.REVIEWER),
                             (self.other, models.Membership.REVIEWER)):
            models.Membership.objects.create(user=person, workspace=self.ws, role=role)
        fresh_table()
        insert_rows(keyed=True, name_sql='%s', client_sql=HOMES_SQL, ok_sql='true', count=30_000,
                    params=[self.owner.username])
        analyze()
        self.names = [self.owner.username, self.invited.username, self.other.username]

    def statement(self):
        with CaptureQueriesContext(connection) as seen:
            answer = LA.objects.latest_sign_ins(self.names)
        (sql,) = [item['sql'] for item in seen.captured_queries]
        return answer, sql

    def test_each_names_last_sign_in_is_one_row_of_its_index(self):
        answer, sql = self.statement()
        shipped = dict(LA.objects.filter(succeeded=True, username__in=self.names).values('username')
                       .annotate(last=Max('created_at')).values_list('username', 'last'))  # every succeeded row
        self.assertEqual(answer, shipped)
        self.assertEqual(list(answer), [self.owner.username])
        plan = explain(sql, analyze=True)
        self.assertNotIn('Rows Removed by Filter', plan)
        (scan,) = scans_of(plan)
        self.assertIn(f'using {SIGNED_IN_INDEX} ', scan, plan)
        self.assertRegex(scan, r'actual time=\S+ rows=[01] loops=3\)', plan)

    def test_only_indexes_that_lead_with_the_name_give_its_order(self):
        _, sql = self.statement()
        dropped, plan = indexes_giving_the_order(self, sql)
        self.assertEqual(dropped[0], SIGNED_IN_INDEX, plan)
        self.assertLessEqual(set(dropped), {SIGNED_IN_INDEX, NAME_ADDRESS_INDEX}, plan)
