"""Release 2's paged lists and search (RELEASE-2-SPEC R2-19, R2-20, R2-16's opens_pdf, R2-24's 409; lane S): GET
/api/encounters?list=documents|queue|recent[&before=<cursor>] serves one page of a list, and POST /api/encounters/search
pages the practice's documents whose row holds the words. Release 1's list_rows is kept here verbatim as the oracle: the
pages of a mixed practice, joined, are its rows in its order, and the queue's pages are its queue - so a page is release
1's row and rule, read a page at a time. Synthetic practices, titles and rows only."""
from __future__ import annotations

import json
import uuid
from datetime import timedelta

from django.db import connection
from django.db.models import Exists, OuterRef
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import client_contract, customer, models, paging, rate, read_audit, request_meta
from tests.support import coding as f
from tests.test_cux_client_contract import RELEASE_1_BUILD
from tests.test_frontend import PLAIN_STATIC
from tests.test_read_audit import member_client

Round, Revision, SourceFile = models.CodingRound, models.SourceRevision, models.SourceFile
Record = models.AccessRecord
PDF, DOCX, TEXT = customer.PDF, customer.DOCX, customer.TEXT
MIB = 1024 * 1024
LIST = '/api/encounters'


# --- the oracle: release 1's GET /api/encounters (studio/customer.py at 9ee0c85be), verbatim --------------------------

def _with_rounds(queryset):
    return queryset.annotate(has_round=Exists(Round.objects.filter(encounter_id=OuterRef('pk'))))


def release_1_list_rows(membership) -> list:
    """GET /api/encounters: the workspace's encounters, newest first."""
    c = customer
    rows = _with_rounds(c.live(membership.workspace.encounters.select_related('current_revision'))).order_by('-created_at')
    out = []
    for encounter in rows:
        value = c.stored_state(encounter, encounter.has_round)
        out.append({'id': str(encounter.pk), 'title': encounter.title, 'state': value,
                    'state_label': c.STATE_LABELS.get(value, value), 'service_date': c.service_date(encounter),
                    'insurance': c.insurance(encounter), 'created_at': c.iso(encounter.created_at),
                    'kind': c.document_kind(encounter)})
    return out


def release_1_order(rows) -> list:
    """Release 1's rows in its order made total: created_at descending, then id descending (R2-19: today's order plus a
    tie-break; release 1 left two documents made in one microsecond in no stated order)."""
    stamps = {row['id']: models.Encounter.objects.values_list('created_at', flat=True).get(pk=row['id']) for row in rows}
    return sorted(rows, key=lambda row: (stamps[row['id']], uuid.UUID(row['id'])), reverse=True)


def release_1_queue(rows) -> list:
    """Release 1's Review queue: the page filtered the whole list by its state (app.js inQueue: QUEUE_STATES)."""
    return [row for row in rows if row['state'] in customer.QUEUE_STATES]


def opens_pdf_expected(encounter_id) -> bool:
    """R2-16: the first stored file (customer.original_file's order) is a PDF of at most 1 MiB."""
    first = SourceFile.objects.filter(encounter_id=encounter_id).order_by('uploaded_at', 'pk').first()
    return first is not None and first.media_type == PDF and first.size <= MIB


# --- a mixed practice ----------------------------------------------------------------------------------------------

_files = iter(range(10 ** 9))


def stored_file(encounter, by, media_type, size):
    """A SourceFile row (no bytes are stored: the list reads the row only)."""
    return SourceFile.objects.create(encounter=encounter, original_name=f'synthetic-{next(_files)}.bin',
                                     media_type=media_type, size=size, sha256='0' * 64,
                                     storage_name=f'{encounter.workspace_id}/list-{uuid.uuid4()}', uploaded_by=by)


def revision(encounter, by, kind, source=None):
    number = Revision.objects.filter(encounter=encounter).count() + 1
    rev = Revision.objects.create(encounter=encounter, number=number, kind=kind, source_file=source,
                                  pasted_text='Synthetic pasted note.' if kind == Revision.PASTE else '',
                                  synthetic_attested_by=by, synthetic_attested_at=timezone.now(), created_by=by)
    models.Encounter.objects.filter(pk=encounter.pk).update(current_revision=rev)
    return rev


def coding_round(encounter, rev, stored_state, round_state=Round.DONE):
    number = Round.objects.filter(encounter=encounter).count() + 1
    Round.objects.create(encounter=encounter, revision=rev, number=number, trigger=Round.UPLOAD, context={},
                         state=round_state)
    models.Encounter.objects.filter(pk=encounter.pk).update(state=stored_state)


# Each a shape of document a practice can hold (a list row's every rule meets one): (kind of revision, files as
# (media type, size), a round with the stored state, user_values, a tombstone).
SHAPES = (
    ('upload', [(PDF, 1673)], 'ready', {'service_date': '2026-11-02', 'insurance': 'medicare'}, False),
    ('paste', [], 'awaiting_answer', {'insurance': 'medicaid'}, False),
    ('upload', [(TEXT, 376)], None, {'service_date': '2026-02-29', 'insurance': 'commercial'}, False),  # no round
    ('addendum', [(PDF, 900)], 'needs_review', {}, False),  # an earlier system's addendum, with a file
    ('addendum', [], 'reviewed', {'insurance': 'unknown'}, False),  # and without one
    (None, [], None, {}, False),  # no revision, no file, no round
    (None, [(PDF, 2 * MIB)], 'no_codes', {'service_date': '2024-02-29'}, False),  # a PDF over 1 MiB
    ('upload', [(PDF, MIB)], 'reviewed', {'service_date': '2026-11-06', 'insurance': 'medicare'}, False),  # exactly 1 MiB
    ('upload', [(PDF, MIB + 1)], 'ready', {}, False),
    ('upload', [(DOCX, 2484)], 'needs_review', {'service_date': '2026-11-09', 'insurance': 'commercial'}, False),
    ('upload', [(TEXT, 300), (PDF, 1200)], 'processing', {}, False),  # the first file is the text
    ('upload', [(PDF, 1200), (TEXT, 300)], 'stopped', {'insurance': 'medicaid'}, False),
    ('paste', [], 'failed', ['service_date', '2026-11-02'], False),  # user_values that are not an object
    ('paste', [], 'ready', 'a string', False),
    ('upload', [(PDF, 1673)], 'awaiting_answer', {'service_date': 20261106, 'insurance': 5}, False),
    ('paste', [], 'needs_review', {'service_date': '', 'insurance': 'MEDICARE'}, False),
    ('upload', [(PDF, 1673)], 'ready', {'service_date': '2026-11-02'}, True),  # a tombstone
    ('paste', [], None, {'insurance': None, 'service_date': None}, True),  # another
    ('upload', [(PDF, 1673)], 'no round: ready', {'insurance': 'medicare'}, False),  # a queue state, no round: earlier
)


def mixed_practice(ws, by, count, *, title='Synthetic list note'):
    """``count`` live documents of ``ws``, made one after another (each its own created_at), cycling through SHAPES -
    and among them the tombstones the cycle reaches, destroyed as a disposal leaves them. The live ones, newest first."""
    made, index = [], -1
    while len(made) < count:
        index += 1
        kind, files, stored, values, tombstone = SHAPES[index % len(SHAPES)]
        enc = models.Encounter.objects.create(workspace=ws, title=f'{title} {index:04d}', created_by=by,
                                              user_values=values)
        sources = [stored_file(enc, by, media_type, size) for media_type, size in files]
        rev = revision(enc, by, kind, sources[0] if sources and kind == 'upload' else None) if kind else None
        if stored is not None and stored.startswith('no round: '):  # a stored state, and no coding round
            models.Encounter.objects.filter(pk=enc.pk).update(state=stored.removeprefix('no round: '))
        elif stored is not None:
            if rev is None:
                rev = Revision.objects.create(encounter=enc, number=1, kind=Revision.ADDENDUM, synthetic_attested_by=by,
                                              synthetic_attested_at=timezone.now(), created_by=by)  # not current
            coding_round(enc, rev, stored)
        if tombstone:
            models.Encounter.objects.filter(pk=enc.pk).update(destroyed_at=timezone.now(), title='', state='destroyed')
        else:
            made.append(enc)
    return made[::-1]


def membership_of(user):
    return models.Membership.objects.select_related('workspace', 'workspace__category').get(user=user)


@override_settings(STORAGES=PLAIN_STATIC)
class ListCase(TestCase):
    def setUp(self):
        self.ws = f.workspace('Synthetic list practice')
        self.reviewer = f.member(self.ws)
        self.member = member_client(self.reviewer)
        self.other_ws = f.workspace('Synthetic other practice')
        self.outsider = f.member(self.other_ws)

    def page(self, which=None, before=None, client=None, status=200):
        query = '&'.join(part for part in (f'list={which}' if which else '', f'before={before}' if before else '')
                         if part)
        answer = (client or self.member).get(LIST + (f'?{query}' if query else ''))
        self.assertEqual(answer.status_code, status, answer.content[:300])
        self.assertEqual(answer['Cache-Control'], 'no-store')
        return answer.json()

    def walk(self, which='documents', client=None):
        """Every page of a list, in order: (rows joined, the pages)."""
        pages, before = [], None
        while True:
            page = self.page(which, before, client)
            pages.append(page)
            before = page['next']
            if before is None:
                return [row for item in pages for row in item['encounters']], pages
            self.assertLessEqual(len(pages), 200)


class PagedListTests(ListCase):
    """R2-19: over a mixed practice of 0, 1, 50, 51 and 117 documents, the pages joined are release 1's rows - every key
    but opens_pdf, in its order - and the queue's pages its queue."""

    def check(self, count):
        made = mixed_practice(self.ws, self.reviewer, count)
        oracle = release_1_order(release_1_list_rows(membership_of(self.reviewer)))
        self.assertEqual([row['id'] for row in oracle], [str(enc.pk) for enc in made])
        joined, pages = self.walk()
        self.assertEqual([{key: value for key, value in row.items() if key != 'opens_pdf'} for row in joined], oracle)
        self.assertEqual([row['opens_pdf'] for row in joined], [opens_pdf_expected(row['id']) for row in joined])
        self.assertEqual([len(page['encounters']) for page in pages],
                         [50] * (len(oracle) // 50) + ([len(oracle) % 50] if len(oracle) % 50 or not oracle else []))
        self.assertEqual(pages[0]['total'], len(oracle))  # exact on the first page
        self.assertTrue(all(page['total'] is None for page in pages[1:]))  # null on a later page
        queue, queue_pages = self.walk('queue')
        self.assertEqual([{key: value for key, value in row.items() if key != 'opens_pdf'} for row in queue],
                         release_1_queue(oracle))
        self.assertEqual(queue_pages[0]['total'], len(release_1_queue(oracle)))
        recent = self.page('recent')
        self.assertEqual((recent['encounters'], recent['next'], recent['total']), (joined[:5], None, None))
        session = self.member.get('/api/session').json()['counts']
        self.assertEqual(session, {'documents': len(oracle), 'queue': len(release_1_queue(oracle))})
        return oracle

    def test_no_documents(self):
        self.check(0)
        self.assertEqual(self.page(), {'encounters': [], 'next': None, 'total': 0, 'workspace': str(self.ws.pk)})

    def test_one_document(self):
        self.check(1)

    def test_fifty_documents_are_one_page(self):
        self.assertEqual(len(self.check(50)), 50)
        self.assertIsNone(self.page()['next'])

    def test_fifty_one_documents_are_two_pages(self):
        self.assertEqual(len(self.check(51)), 51)
        self.assertEqual(len(self.page(before=self.page()['next'])['encounters']), 1)

    def test_one_hundred_and_seventeen_documents(self):
        self.assertEqual(len(self.check(117)), 117)
        self.assertTrue(models.Encounter.objects.filter(workspace=self.ws, destroyed_at__isnull=False).exists())

    def test_every_shape_was_listed(self):
        oracle = self.check(len(SHAPES) * 3)
        self.assertEqual({row['kind'] for row in oracle}, {'upload', 'paste'})
        self.assertEqual({row['state'] for row in oracle} - {'earlier'}, set(customer.state.LABELS))
        self.assertIn('earlier', {row['state'] for row in oracle})
        self.assertEqual({row['service_date'] for row in oracle}, {None, '2026-11-02', '2026-02-29', '2024-02-29',
                                                                    '2026-11-06', '2026-11-09'})
        joined, _pages = self.walk()
        self.assertEqual({row['opens_pdf'] for row in joined}, {True, False})

    def test_two_documents_made_in_one_microsecond_across_a_page_edge_appear_once_each(self):
        made = mixed_practice(self.ws, self.reviewer, 60)
        moment = timezone.now() - timedelta(days=1)
        tied = made[49:51]  # the last row of page one and the first of page two
        models.Encounter.objects.filter(pk__in=[enc.pk for enc in tied]).update(created_at=moment)
        newer = made[:49]
        for offset, enc in enumerate(reversed(newer)):
            models.Encounter.objects.filter(pk=enc.pk).update(created_at=moment + timedelta(seconds=offset + 1))
        for offset, enc in enumerate(made[51:]):
            models.Encounter.objects.filter(pk=enc.pk).update(created_at=moment - timedelta(seconds=offset + 1))
        joined, pages = self.walk()
        ids = [row['id'] for row in joined]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {str(enc.pk) for enc in made})
        edge = sorted((str(enc.pk) for enc in tied), key=uuid.UUID, reverse=True)
        self.assertEqual([pages[0]['encounters'][-1]['id'], pages[1]['encounters'][0]['id']], edge)  # id breaks the tie
        self.assertEqual(ids, [row['id'] for row in release_1_order(release_1_list_rows(membership_of(self.reviewer)))])

    def test_a_tie_of_six_across_the_page_edge_keeps_the_id_order_whatever_the_plan(self):
        # the order is created_at, then id: with the index (which holds both) and without it - a sequential scan and a
        # sort, where rows of one created_at come in no order of their own - the pages are the same, each row once
        made = mixed_practice(self.ws, self.reviewer, 47)
        moment = timezone.now() - timedelta(days=1)
        for offset, enc in enumerate(reversed(made)):
            models.Encounter.objects.filter(pk=enc.pk).update(created_at=moment + timedelta(seconds=offset + 1))
        tied = [models.Encounter.objects.create(id=uuid.UUID(int=index + 1), workspace=self.ws, created_by=self.reviewer,
                                                title=f'Synthetic tied note {index}') for index in range(6)]
        models.Encounter.objects.filter(pk__in=[enc.pk for enc in tied]).update(created_at=moment)  # rows 48 to 53
        expected = [str(enc.pk) for enc in made] + [str(enc.pk) for enc in reversed(tied)]
        for plan in ('the index', 'a sort'):
            with self.subTest(plan=plan):
                with connection.cursor() as cursor:
                    for name in ('enable_indexscan', 'enable_bitmapscan', 'enable_indexonlyscan'):
                        cursor.execute(f'SET {name} = {"on" if plan == "the index" else "off"}')
                try:
                    joined, pages = self.walk()
                finally:
                    with connection.cursor() as cursor:
                        for name in ('enable_indexscan', 'enable_bitmapscan', 'enable_indexonlyscan'):
                            cursor.execute(f'RESET {name}')
                self.assertEqual([row['id'] for row in joined], expected)
                self.assertEqual([len(page['encounters']) for page in pages], [50, 3])

    def test_tombstones_never_appear_in_any_list_or_page(self):
        made = mixed_practice(self.ws, self.reviewer, 120)
        gone = set(models.Encounter.objects.filter(workspace=self.ws, destroyed_at__isnull=False)
                   .values_list('pk', flat=True))
        self.assertTrue(gone)
        for which in ('documents', 'queue', 'recent'):
            joined, _pages = self.walk(which) if which != 'recent' else (self.page('recent')['encounters'], None)
            self.assertFalse({str(pk) for pk in gone} & {row['id'] for row in joined}, which)
        self.assertEqual(self.page()['total'], len(made))

    def test_another_practices_cursor_shows_only_ones_own_rows(self):
        mine = mixed_practice(self.ws, self.reviewer, 70)
        theirs = mixed_practice(self.other_ws, self.outsider, 70, title='Synthetic other note')
        outsider = member_client(self.outsider)
        their_cursor = self.page(client=outsider)['next']
        self.assertIsNotNone(their_cursor)
        shown = self.page(before=their_cursor)['encounters']
        self.assertTrue(shown)
        self.assertLessEqual({row['id'] for row in shown}, {str(enc.pk) for enc in mine})
        self.assertFalse({row['id'] for row in shown} & {str(enc.pk) for enc in theirs})

    def test_a_row_with_a_round_whose_stored_state_is_none_of_todays_is_drawn_computed_and_left_out_of_the_queue(self):
        # R2-19's recorded risk: release 1 drew it computed and the page's queue read that state; the queue list reads
        # the stored state (the app phase recomputes every stored state at each install: none exists afterwards)
        enc = f.encounter(self.ws, self.reviewer, title='Synthetic note with an old stored state')
        rev = revision(enc, self.reviewer, 'paste')
        Round.objects.create(encounter=enc, revision=rev, number=1, trigger=Round.UPLOAD, context={}, state=Round.DONE,
                             codes=[{'line': 'L1', 'code': '45385', 'status': 'ready'}])
        models.Encounter.objects.filter(pk=enc.pk).update(state='ready_for_review')
        (row,) = self.page()['encounters']
        self.assertEqual((row['state'], row['state_label']), ('ready', 'Ready for approval'))  # computed, as release 1
        self.assertEqual(row, {**release_1_list_rows(membership_of(self.reviewer))[0], 'opens_pdf': False})
        self.assertEqual(self.page('queue')['encounters'], [])


class OpensPdfTests(ListCase):
    def test_opens_pdf_is_true_exactly_for_a_first_file_that_is_a_pdf_of_at_most_one_mib(self):
        cases = {(PDF, 1): True, (PDF, MIB): True, (PDF, MIB + 1): False, (TEXT, 10): False, (DOCX, 10): False,
                 (PDF + ';x', 10): False}
        made = {}
        for (media_type, size), expected in cases.items():
            enc = f.encounter(self.ws, self.reviewer, title=f'Synthetic {media_type} {size}')
            revision(enc, self.reviewer, 'upload', stored_file(enc, self.reviewer, media_type, size))
            made[str(enc.pk)] = expected
        second = f.encounter(self.ws, self.reviewer, title='Synthetic text then a PDF')
        revision(second, self.reviewer, 'upload', stored_file(second, self.reviewer, TEXT, 10))
        stored_file(second, self.reviewer, PDF, 10)
        made[str(second.pk)] = False  # only the first file counts, as customer.original_file reads it
        pasted = f.encounter(self.ws, self.reviewer, title='Synthetic paste')
        revision(pasted, self.reviewer, 'paste')
        made[str(pasted.pk)] = False
        rows = self.page()['encounters']
        self.assertEqual({row['id']: row['opens_pdf'] for row in rows}, made)
        self.assertTrue(all(type(row['opens_pdf']) is bool for row in rows))


class ListErrorTests(ListCase):
    def test_an_unknown_list_or_an_unreadable_cursor_answers_400_and_records_nothing(self):
        made = mixed_practice(self.ws, self.reviewer, 60)
        good = self.page()['next']
        position = paging.parse(good)
        undashed = f'{good.split("~")[0]}~{position[1].hex}'  # the same position, not written as the API writes it
        unknown = {'error': 'That list is not available.', 'details': {}}
        unreadable = {'error': 'That part of the list could not be read. Open the list again.', 'details': {}}
        before = Record.objects.count()
        for query, said in (('list=everything', unknown), ('list=', unknown), ('list=Documents', unknown),
                            ('list=documents&list=queue', unknown), ('list=search', unknown),
                            ('before=yesterday', unreadable), ('before=', unreadable), (f'before={undashed}', unreadable),
                            ('before=20261126T101500.123456Z~0b7f3a52', unreadable),
                            ('before=20261332T101500.123456Z~0b7f3a52-9c1e-4d2a-8f61-2a9e5d0c4b17', unreadable),
                            (f'list=recent&before={good}', unreadable), (f'before={good}&before={good}', unreadable)):
            with self.subTest(query=query):
                answer = self.member.get(f'{LIST}?{query}')
                self.assertEqual((answer.status_code, answer.json()), (400, said))
        self.assertEqual(Record.objects.count(), before)
        self.assertFalse(models.RateWindow.objects.filter(scope='list.member').exists())  # refused before the limit
        self.assertEqual(len(self.page(before=good)['encounters']), len(made) - 50)  # the control: the cursor reads

    def test_head_and_other_methods_serve_nothing(self):
        mixed_practice(self.ws, self.reviewer, 3)
        before = Record.objects.count()
        for method in ('head', 'put', 'delete'):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.member, method)(LIST).status_code, 405)
        self.assertEqual(Record.objects.count(), before)


class OutdatedPageTests(ListCase):
    def test_release_1s_page_is_told_to_reload_on_every_list_call_before_any_read(self):
        # R2-24: a page of release 1 left open across the switch would read a page as the whole list: each list call,
        # a later page, and the search are answered 409 client_outdated, reading and recording nothing
        mixed_practice(self.ws, self.reviewer, 60)
        cursor = self.page()['next']
        old = member_client(self.reviewer, **{client_contract.WSGI_KEY: RELEASE_1_BUILD})
        before = (Record.objects.count(), models.RateWindow.objects.count())
        for path in (LIST, f'{LIST}?list=documents', f'{LIST}?list=queue', f'{LIST}?list=recent',
                     f'{LIST}?list=documents&before={cursor}', f'{LIST}?before={cursor}'):
            with self.subTest(path=path):
                answer = old.get(path)
                self.assertEqual((answer.status_code, answer.json()), (409, client_contract.OUTDATED))
        self.assertEqual((Record.objects.count(), models.RateWindow.objects.count()), before)


# --- statements: constant in the practice's size (C1, D-R2-26) --------------------------------------------------------

def bulk_practice(ws, by, count, *, queue_every=3):
    """``count`` documents of ``ws`` made in bulk - one in ``queue_every`` with a coding round and a stored queue state,
    a quarter with a PDF - each its own created_at, for the statement counts and the plans."""
    now = timezone.now()
    encounters = models.Encounter.objects.bulk_create(
        [models.Encounter(workspace=ws, title=f'Synthetic bulk note {n}', created_by=by,
                          state='ready' if n % queue_every == 0 else ('reviewed', 'needs_review')[n % 2])
         for n in range(count)], batch_size=2000)
    for offset, enc in enumerate(encounters):
        enc.created_at = now - timedelta(seconds=offset)
    models.Encounter.objects.bulk_update(encounters, ['created_at'], batch_size=2000)
    revisions = Revision.objects.bulk_create(
        [Revision(encounter=enc, number=1, kind=Revision.UPLOAD if n % 4 == 0 else Revision.PASTE,
                  synthetic_attested_by=by, synthetic_attested_at=now, created_by=by)
         for n, enc in enumerate(encounters)], batch_size=2000)
    for enc, rev in zip(encounters, revisions):
        enc.current_revision = rev
    models.Encounter.objects.bulk_update(encounters, ['current_revision'], batch_size=2000)
    Round.objects.bulk_create([Round(encounter=enc, revision=rev, number=1, trigger=Round.UPLOAD, context={},
                                     state=Round.DONE) for n, (enc, rev) in enumerate(zip(encounters, revisions))
                               if n % queue_every == 0], batch_size=2000)
    SourceFile.objects.bulk_create([SourceFile(encounter=enc, original_name='synthetic.pdf', media_type=PDF, size=4448,
                                               sha256='0' * 64, storage_name=f'{ws.pk}/bulk-{uuid.uuid4()}',
                                               uploaded_by=by)
                                    for n, enc in enumerate(encounters) if n % 4 == 0], batch_size=2000)
    return encounters


@override_settings(STORAGES=PLAIN_STATIC)
class ListStatementTests(TestCase):
    """C1: a first or a later list page is at most 13 statements per request, the same at 51 documents as at 5,000 (one
    page and more); the list builder's own (customer.list_page) at most 4. Release 1's list request took 10."""

    @classmethod
    def setUpTestData(cls):
        cls.small_ws, cls.large_ws = f.workspace('Synthetic small practice'), f.workspace('Synthetic large practice')
        cls.small_user, cls.large_user = f.member(cls.small_ws), f.member(cls.large_ws)
        bulk_practice(cls.small_ws, cls.small_user, 51, queue_every=1)  # every one waiting: the queue has a page too
        bulk_practice(cls.large_ws, cls.large_user, 5000, queue_every=1)

    def statements(self, client, path):
        with CaptureQueriesContext(connection) as seen:
            answer = client.get(path)
        self.assertEqual(answer.status_code, 200, answer.content[:200])
        return len(seen.captured_queries), answer.json()

    def builder(self, user, which, before=None):
        membership = membership_of(user)
        with CaptureQueriesContext(connection) as seen:
            customer.list_page(membership, which, before)
        return len(seen.captured_queries)

    def test_each_page_is_the_same_number_of_statements_at_51_and_5000_documents(self):
        counted = {}
        for name, user in (('small', self.small_user), ('large', self.large_user)):
            client = member_client(user)
            first, page = self.statements(client, f'{LIST}?list=documents')
            later, _ = self.statements(client, f'{LIST}?list=documents&before={page["next"]}')
            queue, queued = self.statements(client, f'{LIST}?list=queue')
            recent, _ = self.statements(client, f'{LIST}?list=recent')
            counted[name] = {'first': first, 'later': later, 'queue': queue, 'recent': recent,
                             'builder first': self.builder(user, 'documents'),
                             'builder later': self.builder(user, 'documents', page['next']),
                             'builder queue': self.builder(user, 'queue'),
                             'builder recent': self.builder(user, 'recent')}
        self.assertEqual(counted['small'], counted['large'])
        for key, value in counted['large'].items():
            with self.subTest(statements=key):
                self.assertLessEqual(value, 4 if key.startswith('builder') else 13)
        self.assertEqual(counted['large']['builder first'], 4)  # its rows, rounds, files and the COUNT (more follow)
        self.assertEqual(counted['large']['builder later'], 3)  # no COUNT on a later page

    def test_a_whole_list_on_its_first_page_pays_no_count(self):
        ws = f.workspace('Synthetic fifty practice')
        user = f.member(ws)
        bulk_practice(ws, user, 50)
        self.assertEqual(self.builder(user, 'documents'), 3)
        count, page = self.statements(member_client(user), LIST)
        self.assertEqual((page['next'], page['total'], len(page['encounters'])), (None, 50, 50))
        self.assertLessEqual(count, 12)


class ListPlanTests(TestCase):
    """At 20,000 documents (one practice of 2,000 among them: a minority of the table), each statement of a list page and
    of the session reads an index - the documents page studio_enc_ws_time, the queue page studio_enc_ws_queue - and
    never scans studio_encounter, studio_codinground or studio_sourcefile, the COUNTs included (here, a practice of 2,000
    among 20,000; D-R2-37 holds a whole list's COUNT to its time, not to an index: a practice nearer half the table may
    be read whole until VACUUM, and PlanAtEighteenThousandTests holds the practice that is most of the table).
    tests/test_r1_repair_s.py reads the reads page the same way."""

    @classmethod
    def setUpTestData(cls):
        cls.ws = f.workspace('Synthetic planned practice')
        cls.user = f.member(cls.ws)
        bulk_practice(cls.ws, cls.user, 2000)
        others = f.workspace('Synthetic other practices')
        bulk_practice(others, f.member(others), 18000)
        with connection.cursor() as cursor:
            for table in ('studio_encounter', 'studio_codinground', 'studio_sourcefile', 'studio_sourcerevision'):
                cursor.execute(f'ANALYZE {table}')

    def plans(self, which, before=None):
        membership = membership_of(self.user)
        with CaptureQueriesContext(connection) as seen:
            page = customer.list_page(membership, which, before)
        found = []
        for item in seen.captured_queries:
            with connection.cursor() as cursor:
                cursor.execute('EXPLAIN ' + item['sql'])
                found.append((item['sql'], '\n'.join(row[0] for row in cursor.fetchall())))
        return page, found

    def test_every_statement_of_a_list_page_reads_an_index(self):
        self.assertEqual(models.Encounter.objects.count(), 20000)
        page, _ = self.plans('documents')
        for which, before, index in (('documents', None, 'studio_enc_ws_time'), ('queue', None, 'studio_enc_ws_queue'),
                                     ('documents', page['next'], 'studio_enc_ws_time')):
            with self.subTest(list=which, later=before is not None):
                _page, found = self.plans(which, before)
                self.assertEqual(len(found), 3 + (before is None))
                rows_sql, rows_plan = found[0]
                self.assertIn('LIMIT 51', rows_sql)
                self.assertIn(index, rows_plan)
                if which == 'documents':  # the flags are read apart, over the page's ids - never in the rows' statement
                    self.assertNotIn('studio_codinground', rows_sql)
                    self.assertNotIn('studio_sourcefile', rows_sql)
                for sql, plan in found:  # the rows, their rounds, their files and the first page's COUNT
                    for table in ('studio_encounter', 'studio_codinground', 'studio_sourcefile'):
                        self.assertNotIn(f'Seq Scan on {table}', plan, (sql[:120], plan[:1500]))

    def test_the_sessions_two_counts_read_an_index(self):
        membership = membership_of(self.user)
        with CaptureQueriesContext(connection) as seen:
            counts = customer.session_json(self.user, membership)['counts']
        self.assertEqual(counts, {'documents': 2000, 'queue': 667})  # one in three waits, with its round
        statements = [item['sql'] for item in seen.captured_queries]
        self.assertEqual(sum(sql.startswith('SELECT COUNT(*)') for sql in statements), 2)
        for sql in statements:
            with connection.cursor() as cursor:
                cursor.execute('EXPLAIN ' + sql)
                plan = '\n'.join(row[0] for row in cursor.fetchall())
            for table in ('studio_encounter', 'studio_codinground', 'studio_sourcefile'):
                self.assertNotIn(f'Seq Scan on {table}', plan, (sql[:120], plan[:1500]))


# --- the search (R2-20) --------------------------------------------------------------------------------------------

import base64  # noqa: E402 - this section's own imports
import contextlib  # noqa: E402
import io  # noqa: E402
import logging  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import urllib.parse  # noqa: E402
from importlib import import_module  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

from django.conf import settings  # noqa: E402
from django.contrib.sessions.models import Session  # noqa: E402

SEARCH = '/api/encounters/search'
# Every table a read, an event, a limit or a session writes, which a search's words must never reach (integrated
# refutation round 1, phileak-0 and phileak-2: the whole row of each, never only its free-text fields).
SEARCH_MARKER_TABLES = (models.AccessRecord, models.AccessRecordRepeat, models.SecurityEvent, models.AuditEvent,
                        models.RateWindow, models.SessionAccountLink)


def search_marker_forms(word: str) -> set:
    """Every form of ``word`` a no-leak guard looks for (integrated refutation round 1, phileak-0), as the bench's
    markerForms reads a marker (ops/bench/bench.cjs, records[4]): the word as typed and case-folded, and its base64 and
    base64url cores at the three byte alignments (the characters the word's bytes alone decide, wherever it starts)."""
    forms = {word, word.casefold()}
    data = word.encode('utf-8')
    for pad in range(3):
        encoded = base64.b64encode(b'\0' * pad + data).decode('ascii')
        core = encoded[-(-pad * 4 // 3):(pad + len(data)) * 4 // 3]
        forms |= {core, core.replace('+', '-').replace('/', '_')}
    return forms


UUID_SHAPE = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'


def answer_retry(answer) -> int:
    """A 429's whole seconds to wait, as its body and its Retry-After give them (the same number)."""
    seconds = answer.json()['retry_after']
    assert isinstance(seconds, int) and 0 < seconds <= 60 and answer['Retry-After'] == str(seconds), answer.items()
    return seconds


def search_answer_headers(answer, sign_in) -> dict:
    """The headers a search's answer carries, every one with its fixed value or an id (the sign-in reference)."""
    from studio import access
    return {'Content-Type': 'application/json', 'Content-Length': str(len(answer.content)), 'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin', 'Content-Security-Policy': access.SecurityHeadersMiddleware.CSP,
            'X-Frame-Options': 'DENY', 'Cross-Origin-Opener-Policy': 'same-origin', 'Vary': 'Cookie',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()', 'X-Robots-Tag': 'noindex, nofollow',
            'X-CPT-Actor': str(sign_in)}


def every_row() -> dict:
    """Every row of every table the project and Django keep, read through each model's base manager: {table: {pk: {column:
    value}}} - what a search's closed-world check compares as a whole (integrated refutation round 2, I2-3)."""
    from django.apps import apps
    rows = {}
    for model in apps.get_models(include_auto_created=True):
        pk = model._meta.pk.attname
        rows[model._meta.db_table] = {str(row[pk]): row for row in model._base_manager.values()}
    return rows


def rows_changed(before, after) -> dict:
    """{table: {'added': [row], 'removed': [row], 'changed': [(pk, {column: (before, after)})]}} for each table whose rows
    are not what they were: rows added, rows gone, and every column that moved."""
    out = {}
    for table in sorted(set(before) | set(after)):
        old, new = before.get(table, {}), after.get(table, {})
        added = [new[key] for key in sorted(set(new) - set(old))]
        removed = [old[key] for key in sorted(set(old) - set(new))]
        changed = [(key, {column: (old[key].get(column), new[key][column]) for column in new[key]
                          if old[key].get(column) != new[key][column]})
                   for key in sorted(set(old) & set(new)) if old[key] != new[key]]
        if added or removed or changed:
            out[table] = {'added': added, 'removed': removed, 'changed': changed}
    return out


def search_marker_hits(texts, words) -> list:
    """[(form, the text's index)] of every form of each of ``words`` in ``texts``: each text read as it is and percent-
    and plus-decoded; the word's own forms matched case-folded, a base64 core as written (its case is its content)."""
    hits = []
    for index, text in enumerate(texts):
        readings = {text, urllib.parse.unquote_plus(text)}
        folded = {reading.casefold() for reading in readings}
        for word in words:
            plain = {word, word.casefold()}
            for form in sorted(search_marker_forms(word)):
                if (form in plain and any(form.casefold() in reading for reading in folded)) or \
                        (form not in plain and any(form in reading for reading in readings)):
                    hits.append((form, index))
    return hits
ROW_TEXT = Path(settings.BASE_DIR) / 'tests' / 'frontend' / 'row_text.cjs'
LOWER_TABLE = Path(settings.BASE_DIR) / 'tests' / 'frontend' / 'lower_table.cjs'
# Awkward rows (R2-20's property test): titles a browser and PostgreSQL may lower-case or trim differently, SQL's own
# characters, ligatures, emoji, JavaScript's white space at either end, the longest title; dates that are and are not a
# calendar date the page reads; insurance and user_values of every odd shape.
AWKWARD_TITLES = ['Synthetic EGD report', 'ÉCHO Müller', 'straße 12', 'ΑΣΚΛΗΠΙΟΣ σημείωση', 'İstanbul note',
                  'ÅNGSTRÖM', 'KKelvin', 'a%b_c\\d', "O'Neil <b>&amp; \"quoted\" `tick`", '  ', '', '﻿BOM title﻿',
                  'polyp', 'x' * 160, 'Ready for approval copy', 'note 2026-11-06', 'ﬁne ligature', 'ＦＵＬＬ', 'tab\tinside',
                  'emoji 🙂 note', 'naïve Café', 'ǅ title', 'Ω Ohm', 'ſ long s', 'ŉ', 'ΰ', 'Ⅷ roman', 'Ⓐ circled',
                  '　ideographic ', '᠎mongolian᠎', 'Σ', 'όροςΣ', 'i̇ dotted', "'; DROP TABLE x; --"]
AWKWARD_DATES = ['2026-11-06', '2026-02-28', '2024-02-29', '2026-02-29', '2026-02-30', '2026-04-31', '2026-12-31',
                 '1999-01-01', '0099-01-01', '0100-01-01', '0001-01-01', '2000-02-29', '1900-02-29', '20261106',
                 '2026-W45-5', 'not a date', '', None, 20261106, {'a': 1}, ' 2026-11-06', '2026-11-06 ', '2026-13-01',
                 '2026-00-10', '2026-10-00', '٢٠٢٦-١١-٠٦', '9999-12-31', '2026-11-6', '2026-11-06\n', '1000-10-10']
AWKWARD_INSURANCE = ['medicare', 'medicaid', 'commercial', 'unknown', None, 'MEDICARE', 5, 'other', ['medicare']]


def awkward_practice(ws, by, count, seed=20261126):
    """``count`` live documents of every awkward shape (and a few tombstones), made one after another."""
    chance = random.Random(seed)
    states = list(customer.state.LABELS)
    for index in range(count + count // 20):
        values = {}
        if chance.random() < .9:
            values['service_date'] = chance.choice(AWKWARD_DATES)
        if chance.random() < .9:
            values['insurance'] = chance.choice(AWKWARD_INSURANCE)
        if chance.random() < .04:
            values = chance.choice([[], 'text', 5, ['service_date']])
        title = (chance.choice(AWKWARD_TITLES) + chance.choice(['', '', f' {index}', ' up', ' P']))[:160]
        enc = models.Encounter.objects.create(workspace=ws, title=title, created_by=by, user_values=values)
        kind = chance.choice(['upload', 'paste', 'addendum', None])
        source = stored_file(enc, by, PDF, 1673) if chance.random() < .4 else None
        rev = revision(enc, by, kind, source if kind == 'upload' else None) if kind else None
        if rev is not None and chance.random() < .7:
            coding_round(enc, rev, chance.choice(states))
        if index % 21 == 20:
            models.Encounter.objects.filter(pk=enc.pk).update(destroyed_at=timezone.now(), state='destroyed')


def node_rows(rows, queries):
    node = shutil.which('node')
    done = subprocess.run([node, str(ROW_TEXT)], input=json.dumps({'rows': rows, 'queries': queries}),
                          capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def node_lowered() -> dict:
    """{code point: [code points]} for every code point node's JavaScript lower-cases (tests/frontend/lower_table.cjs):
    a stand-in for the page's browser, with node's own tables (its ICU, which the test host or CI's runner sets), never
    a member's browser's, which may be newer (browser_lowered, CHROMIUM_153_NEWER)."""
    done = subprocess.run([shutil.which('node'), str(LOWER_TABLE)], capture_output=True, text=True, timeout=300,
                          check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    return {int(point): pieces for point, pieces in json.loads(done.stdout)['lowered'].items()}


def browser_lowered() -> tuple:
    """({engine: {code point: [code points]}}, {engine: why it is absent}) for the Chromium builds present on the test
    host - the walk's own and the newest installed in Playwright's browser folder (tests/frontend/lower_table.cjs
    --browsers, each on a blank page with every request refused): the tables the page's own rule reads in them."""
    done = subprocess.run([shutil.which('node'), str(LOWER_TABLE), '--browsers'], capture_output=True, text=True,
                          timeout=600, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    found = json.loads(done.stdout)
    return ({engine['name']: {int(point): pieces for point, pieces in engine['lowered'].items()}
             for engine in found['engines']}, {engine['name']: engine['why'] for engine in found['absent']})


# The 28 letters Chromium 153.0.8010.12 (ICU 78, Unicode 17.0) lower-cases that node 22.22.0 and Chromium 147 (ICU 77.1,
# Unicode 16.0) do not - U+A7CE, U+A7D2, U+A7D4 and Beria Erfe's U+16EA0-U+16EB8 - each to the small letter it gives:
# measured over every code point in lane S's refutation round 2 (search[0]) and again for this table. Committed, so
# SearchLetterTests holds the server to them where no such browser is installed, CI among them (D-R2-42).
CHROMIUM_153_NEWER = {
    '\ua7ce': '\ua7cf', '\ua7d2': '\ua7d3', '\ua7d4': '\ua7d5',
    '\U00016ea0': '\U00016ebb', '\U00016ea1': '\U00016ebc', '\U00016ea2': '\U00016ebd', '\U00016ea3': '\U00016ebe',
    '\U00016ea4': '\U00016ebf', '\U00016ea5': '\U00016ec0', '\U00016ea6': '\U00016ec1', '\U00016ea7': '\U00016ec2',
    '\U00016ea8': '\U00016ec3', '\U00016ea9': '\U00016ec4', '\U00016eaa': '\U00016ec5', '\U00016eab': '\U00016ec6',
    '\U00016eac': '\U00016ec7', '\U00016ead': '\U00016ec8', '\U00016eae': '\U00016ec9', '\U00016eaf': '\U00016eca',
    '\U00016eb0': '\U00016ecb', '\U00016eb1': '\U00016ecc', '\U00016eb2': '\U00016ecd', '\U00016eb3': '\U00016ece',
    '\U00016eb4': '\U00016ecf', '\U00016eb5': '\U00016ed0', '\U00016eb6': '\U00016ed1', '\U00016eb7': '\U00016ed2',
    '\U00016eb8': '\U00016ed3',
}


def database_lowered() -> dict:
    """{code point: [code points]} for every code point the search's lower() changes (PostgreSQL's pg_c_utf8)."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT point, low FROM (SELECT point, lower(chr(point) COLLATE "pg_c_utf8") AS low '
                       'FROM generate_series(1, 1114111) AS point WHERE point NOT BETWEEN 55296 AND 57343) AS letters '
                       'WHERE low <> chr(point)')
        return {point: [ord(piece) for piece in low] for point, low in cursor.fetchall()}


def sql_row_texts(ws) -> dict:
    """{id: the row's text as the search reads it} for every live document of ``ws`` (customer.search_row_text_sql)."""
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT e.id, {customer.search_row_text_sql()} FROM {customer.search_from_sql()} '
                       'WHERE e.workspace_id = %(workspace)s AND e.destroyed_at IS NULL',
                       {'workspace': ws.pk, 'space': customer.JS_WHITE_SPACE})
        return {str(pk): text for pk, text in cursor.fetchall()}


def searched(membership, words) -> list:
    """Every page of a search for ``words``, joined: the ids found, newest first."""
    out, before = [], None
    while True:
        page = customer.search_page(membership, words, before)
        assert page['total'] is None
        out += [row['id'] for row in page['encounters']]
        before = page['next']
        if before is None:
            return out


class SearchCase(ListCase):
    def search(self, text, before=None, client=None, status=200, **extra):
        body = {'text': text, 'before': before, **extra}
        answer = (client or self.member).post(SEARCH, data=json.dumps(body), content_type='application/json')
        self.assertEqual(answer.status_code, status, answer.content[:300])
        self.assertEqual(answer['Cache-Control'], 'no-store')
        return answer.json()

    def assert_a_search_leaves_only_ids_counts_and_fixed_words(self, before, after, session_before, found, refused,
                                                                logged, printed, marked, now):
        """The closed-world half of the no-leak test (integrated refutation round 2, I2-3): every row of every table, the
        member's session, the two answers' headers and cookies, every log record and everything printed, compared as a
        whole with what a served search (found) and a refused one (refused, over the member's limit) may leave."""
        from tests.test_read_audit import REQUEST_ID
        self.maxDiff = None
        member, practice = self.reviewer.pk, self.ws.pk
        sign_in = uuid.UUID(str(session_before[request_meta.SESSION_SIGN_IN_REF]))
        changed = rows_changed(before, after)
        # the served search's one read record, the refused one's one event, and the member's list.member window: nothing
        # else in any table, no row changed or removed anywhere (the session's own row included)
        record, = changed.pop('studio_accessrecord', {}).get('added') or [None]
        self.assertIsNotNone(record, changed)
        self.assertRegex(str(record.pop('id')), UUID_SHAPE)
        self.assertEqual(record, {
            'created_at': now, 'host': request_meta.CPT, 'view': read_audit.MEMBER_LIST, 'actor_id': member,
            'actor_kind': 'human', 'actor_role': models.Membership.REVIEWER, 'workspace_id': practice,
            'encounter_ids': [str(marked.pk)], 'export_id': None, 'count': 1, 'as_of': now,
            'filters': {'list': 'search', 'before': None}, 'reason': '', 'outcome': Record.SERVED, 'client': '127.0.0.1',
            'sign_in_ref': sign_in, 'request_id': REQUEST_ID})
        event, = changed.pop('studio_securityevent', {}).get('added') or [None]
        self.assertIsNotNone(event, changed)
        self.assertRegex(str(event.pop('id')), UUID_SHAPE)
        self.assertEqual(event, {
            'created_at': now, 'event': 'list.rate_limited', 'actor_id': member, 'actor_label': '', 'subject_id': member,
            'workspace_id': practice, 'data': {'scope': 'list.member', 'limit': 1, 'window_seconds': 60},
            'client': '127.0.0.1', 'sign_in_ref': sign_in, 'request_id': REQUEST_ID})
        windows = changed.pop('studio_ratewindow', {})
        self.assertEqual([{column: value for column, value in row.items() if column != 'id'} for row in windows.get('added', [])],
                         [{'scope': 'list.member', 'key': str(member), 'window_start': rate.window_start(60), 'count': 2,
                           'last_at': now}], windows)
        self.assertEqual((windows.get('removed'), windows.get('changed')), ([], []))
        self.assertEqual(changed, {}, 'nothing else, anywhere')
        # the session: what it was, nothing added or changed
        self.assertEqual(dict(self.member.session.items()), session_before)
        # the answers: exactly these headers, each with its fixed value or an id; no cookie
        for answer, extra in ((found, {}), (refused, {'Retry-After': str(answer_retry(refused))})):
            self.assertEqual(dict(answer.items()), {**search_answer_headers(answer, sign_in), **extra}, answer.status_code)
            self.assertEqual(list(answer.cookies), [], answer.status_code)
        # the log: the refused answer's one line, the method and the path only; nothing printed
        self.assertEqual([(name, level, msg, args, exc) for name, level, msg, args, exc in logged],
                         [('django.request', 'WARNING', '%s: %s', ('Too Many Requests', SEARCH), None)])
        self.assertEqual(printed, '')


class SearchPropertyTests(SearchCase):
    """The server's row text is the page's own (app.js documentRow, run by node over the rows the API served), and for
    random pieces of those texts the server finds what the page's rule finds - or more, only on rows or words holding a
    sigma or a dotted I - and never fewer."""

    def setUp(self):
        super().setUp()
        if shutil.which('node') is None:
            self.skipTest('node is not here: the page cannot be run')

    def test_the_server_reads_the_pages_text_and_finds_what_its_rule_finds(self):
        awkward_practice(self.ws, self.reviewer, 300)
        rows, _pages = self.walk()
        self.assertEqual(len(rows), 300)
        chance = random.Random(1450)
        page_texts = node_rows(rows, [])['texts']
        queries = set()
        for text in page_texts:
            for _ in range(2):
                start = chance.randrange(len(text))
                piece = text[start:min(len(text), start + chance.randint(1, 14))]
                queries.add(chance.choice([piece, piece.upper(), piece.lower(), piece.title(), f' {piece} ']))
        queries |= {'c', 'polyp', 'polypu', 'copyuploaded', 'medicareready', 'reviewnot entered', '6 nov 2026',
                    'nov 2026', '29 feb 2024', '29 feb 2026', '30 feb 2026', '1 jan 100', '10 oct 1000', 'i̇', 'istanbul',
                    'İSTANBUL', 'ασ', 'ας', 'ΑΣΚΛΗΠΙΟΣ', 'σ', 'ς', 'Σ', 'zzz', '%', '_', '\\', "'", '<b>', '&amp;', '·',
                    ' · ', 'ss', 'ß', 'k', 'ﬁ', 'fi', 'ＦＵＬＬ', 'full', '🙂', 'x' * 161, 'ω', 'ŉ', 'ʼn', 'ⅷ', 'ⓐ', 'ǆ',
                    'untitled document', 'earlier review', 'not entered', "drop table", '᠎', 'mongolian',
                    '`tick`', '"quoted"', 'ideographic'}
        queries = sorted(query for query in queries if customer.search_words(query))
        page = node_rows(rows, queries)
        self.assertEqual(page['texts'], page_texts)
        server = sql_row_texts(self.ws)
        computed = {row['id'] for row in rows if row['state'] not in customer.state.LABELS and row['state'] != 'earlier'}
        self.assertFalse(computed)  # every stored state is one of today's: the text is the page's exactly
        self.assertEqual({row['id']: server[row['id']] for row in rows},
                         {row['id']: text for row, text in zip(rows, page_texts)})
        membership = membership_of(self.reviewer)
        order = [row['id'] for row in rows]
        texts = dict(zip(order, page_texts))
        exact = more = 0
        for query, wanted in zip(queries, page['found']):
            words = customer.search_words(query)
            if customer.search_length(words) > customer.SEARCH_MAX_CHARS:
                continue
            with self.subTest(query=query):
                found = searched(membership, words)
                self.assertEqual(found, [item for item in order if item in set(found)])  # newest first, each once
                self.assertLessEqual(set(wanted), set(found))  # never fewer than the page's rule
                extra = set(found) - set(wanted)
                for item in extra:  # more only where a letter lower-cases by its neighbours or into two
                    self.assertTrue(any(ch in texts[item] + words for ch in customer.SEARCH_FOLDED), (query, texts[item]))
                exact, more = exact + (not extra), more + bool(extra)
        self.assertGreater(exact, 400)
        self.assertGreater(more, 0)  # the superset was met, so the rule above was tested


class SearchLetterTests(SearchCase):
    """The page lower-cases with its browser's tables, the search with PostgreSQL 17's pg_c_utf8 (Unicode 15.1). Read
    over every code point in each engine present - node (a stand-in; here 22.22.0, Unicode 16.0), the walk's Chromium
    (here 147, Unicode 16.0) and the newest Chromium installed (here 153, Unicode 17.0), one that is absent skipped by
    name - and against a committed table of Chromium 153's newer letters (CHROMIUM_153_NEWER, held where no browser is
    installed), each differs from the database only where the search folds: every letter it alone lower-cases is in
    customer.SEARCH_NEWER, to the same small letter, and U+0130 is the one letter both lower-case, differently. An
    engine on a later Unicode release, an ICU upgrade or a PostgreSQL upgrade fails here and names its letters. These
    are the test host's engines, never a member's browser: one on a Unicode release newer than all of them can
    lower-case a letter the search does not fold, until SEARCH_NEWER is extended (D-R2-42; API.md's known limits). And
    each pair of SEARCH_NEWER - its partners the browsers' own, never Python's (Unicode 15.0) - is found in either case
    by either letter."""

    def setUp(self):
        super().setUp()
        if shutil.which('node') is None:
            self.skipTest('node is not here: the page cannot be run')

    def test_the_browser_and_the_database_lower_case_alike_except_where_the_search_folds(self):
        database = database_lowered()
        browsers, absent = browser_lowered()
        for engine, page in {'node': node_lowered(), **browsers}.items():
            with self.subTest(engine=engine):
                only_page = {chr(point): ''.join(map(chr, page[point])) for point in set(page) - set(database)}
                # each letter only this engine lower-cases is folded, to the letter it gives; an older engine
                # lower-cases fewer, and its page finds fewer than the search, which "never fewer" allows
                self.assertLessEqual(only_page.items(), customer.SEARCH_NEWER.items(), sorted(
                    f'U+{ord(letter):04X}' for letter, small in only_page.items()
                    if customer.SEARCH_NEWER.get(letter) != small))
                self.assertEqual(set(database) - set(page), set())  # nothing the database alone lower-cases
                self.assertEqual({point for point in set(page) & set(database) if page[point] != database[point]},
                                 {0x130})
                self.assertEqual((page[0x130], database[0x130]), ([0x69, 0x307], [0x69]))  # i and the dot above, or i
                # the dot above is the one character a lower case adds, so customer.search_length is the same before
                # and after
                self.assertEqual({point for point, pieces in page.items() if len(pieces) != 1}, {0x130})
        for engine, why in absent.items():  # an engine not installed on this host is skipped, by name
            with self.subTest(engine=engine):
                self.skipTest(why)
        # Chromium 153's newer letters, committed: held where no such browser is installed (CI among them)
        self.assertLessEqual(CHROMIUM_153_NEWER.items(), customer.SEARCH_NEWER.items(), sorted(
            f'U+{ord(letter):04X}' for letter, small in CHROMIUM_153_NEWER.items()
            if customer.SEARCH_NEWER.get(letter) != small))
        # the fold of words holding all of them: each letter of FROM to the letter at its place in TO, and the dot last,
        # past TO's end (dropped)
        fold_from, fold_to = customer.search_fold(''.join(customer.SEARCH_NEWER))
        self.assertEqual(dict(zip(fold_from, fold_to)), {'\u03c2': '\u03c3', **customer.SEARCH_NEWER})
        self.assertEqual((len(fold_from) - len(fold_to), fold_from[-1]), (1, '\u0307'))

    def test_each_letter_only_the_browser_lower_cases_is_found_in_either_case(self):
        pairs = sorted(customer.SEARCH_NEWER.items())  # each newer capital and its small letter, the browsers' (above)
        titles = {}
        for capital, small in pairs:  # one title in each case
            titles[capital] = {str(f.encounter(self.ws, self.reviewer, title=f'Synthetic {letter} letter note').pk)
                               for letter in (capital, small)}
        rows, _pages = self.walk()
        queries = [(letter, capital) for capital, small in pairs for letter in (capital, small)]
        membership = membership_of(self.reviewer)
        for (query, capital), node_found in zip(queries, node_rows(rows, [query for query, _ in queries])['found']):
            with self.subTest(letter=f'U+{ord(query):04X}'):
                found = set(searched(membership, query))
                # the letter's title in either case: what the page's rule finds in a browser that lower-cases it
                self.assertEqual(found, titles[capital])
                self.assertLessEqual(set(node_found), found)  # and never fewer than node's rule finds


class SearchTests(SearchCase):
    def test_the_answer_is_the_lists_shape_newest_first_with_no_total(self):
        made = mixed_practice(self.ws, self.reviewer, 30)
        answer = self.search('list note')
        self.assertEqual(set(answer), {'encounters', 'next', 'total', 'workspace'})
        self.assertEqual(answer['workspace'], str(self.ws.pk))
        self.assertEqual((answer['next'], answer['total']), (None, None))
        joined, _pages = self.walk()
        self.assertEqual(answer['encounters'], joined)  # every row holds the words: the whole list, rows identical
        self.assertEqual(len(answer['encounters']), len(made))

    def test_results_page_by_50_from_the_cursor_each_once(self):
        mixed_practice(self.ws, self.reviewer, 120)
        mixed_practice(self.ws, self.reviewer, 10, title='Synthetic other words')
        pages, before = [], None
        while True:
            page = self.search('list note', before)
            pages.append(page)
            before = page['next']
            if before is None:
                break
        self.assertEqual([len(page['encounters']) for page in pages], [50, 50, 20])
        ids = [row['id'] for page in pages for row in page['encounters']]
        self.assertEqual(len(ids), len(set(ids)))
        listed, _ = self.walk()
        self.assertEqual(ids, [row['id'] for row in listed if 'list note' in row['title'].lower()])
        self.assertTrue(all(page['total'] is None for page in pages))

    def test_a_tie_of_six_across_the_page_edge_keeps_the_id_order_whatever_the_plan(self):
        # the search pages in the list's order - created_at, then id: with the index and without it (a sequential scan
        # and a sort, where rows of one created_at come in no order of their own) the pages are the same, each row once
        made = mixed_practice(self.ws, self.reviewer, 47)
        moment = timezone.now() - timedelta(days=1)
        for offset, enc in enumerate(reversed(made)):
            models.Encounter.objects.filter(pk=enc.pk).update(created_at=moment + timedelta(seconds=offset + 1))
        tied = [models.Encounter.objects.create(id=uuid.UUID(int=index + 1), workspace=self.ws, created_by=self.reviewer,
                                                title=f'Synthetic list note tied {index}') for index in range(6)]
        models.Encounter.objects.filter(pk__in=[enc.pk for enc in tied]).update(created_at=moment)  # rows 48 to 53
        expected = [str(enc.pk) for enc in made] + [str(enc.pk) for enc in reversed(tied)]
        for plan in ('the index', 'a sort'):
            with self.subTest(plan=plan):
                with connection.cursor() as cursor:
                    for name in ('enable_indexscan', 'enable_bitmapscan', 'enable_indexonlyscan'):
                        cursor.execute(f'SET {name} = {"on" if plan == "the index" else "off"}')
                try:
                    pages, before = [], None
                    while True:
                        pages.append(self.search('list note', before))
                        before = pages[-1]['next']
                        if before is None or len(pages) > 5:
                            break
                finally:
                    with connection.cursor() as cursor:
                        for name in ('enable_indexscan', 'enable_bitmapscan', 'enable_indexonlyscan'):
                            cursor.execute(f'RESET {name}')
                self.assertEqual([row['id'] for page in pages for row in page['encounters']], expected)
                self.assertEqual([len(page['encounters']) for page in pages], [50, 3])

    def test_another_practice_and_tombstones_are_never_found(self):
        mine = f.encounter(self.ws, self.reviewer, title='Synthetic polypectomy note')
        f.encounter(self.other_ws, self.outsider, title='Synthetic polypectomy note of another practice')
        gone = f.encounter(self.ws, self.reviewer, title='Synthetic polypectomy note destroyed')
        models.Encounter.objects.filter(pk=gone.pk).update(destroyed_at=timezone.now())  # its title kept, for the test
        self.assertEqual([row['id'] for row in self.search('polypectomy')['encounters']], [str(mine.pk)])
        their_cursor = paging.cursor_of(timezone.now() + timedelta(days=1), uuid.uuid4())
        self.assertEqual([row['id'] for row in self.search('polypectomy', their_cursor)['encounters']], [str(mine.pk)])

    def test_words_made_of_sql_match_only_themselves(self):
        plain = f.encounter(self.ws, self.reviewer, title='Synthetic plain note')
        marked = f.encounter(self.ws, self.reviewer, title="Synthetic 50% _x_ a\\b O'Neil note")
        for words, expected in (('%', [marked]), ('_', [marked]), ('\\', [marked]), ("'", [marked]),
                                ("O'Neil", [marked]), ('%x%', []), ('_x_', [marked]), ("' OR '1'='1", []),
                                ('note', [marked, plain]), ('*', []), ('.', [])):
            with self.subTest(words=words):
                self.assertEqual([row['id'] for row in self.search(words)['encounters']],
                                 [str(enc.pk) for enc in expected])

    def test_blank_or_non_text_words_answer_400_and_record_nothing(self):
        f.encounter(self.ws, self.reviewer, title='Synthetic note')
        required = {'error': 'Type the words to search for.', 'details': {}}
        before = (Record.objects.count(), models.RateWindow.objects.count())
        for text in ('', '   ', '　 ﻿', None, 5, ['note'], {'text': 'note'}, True):
            with self.subTest(text=text):
                self.assertEqual(self.search(text, status=400), required)
        answer = self.member.post(SEARCH, data=json.dumps({'before': None}), content_type='application/json')
        self.assertEqual((answer.status_code, answer.json()), (400, required))
        for body, content_type in (('note', 'text/plain'), ('[1, 2]', 'application/json'), ('{', 'application/json')):
            with self.subTest(body=body):
                self.assertEqual(self.member.post(SEARCH, data=body, content_type=content_type).status_code, 400)
        unreadable = {'error': 'That part of the list could not be read. Open the list again.', 'details': {}}
        for cursor in ('yesterday', 5, '', ['20261126T101500.123456Z~0b7f3a52-9c1e-4d2a-8f61-2a9e5d0c4b17']):
            with self.subTest(cursor=cursor):
                self.assertEqual(self.search('note', cursor, status=400), unreadable)
        self.assertEqual((Record.objects.count(), models.RateWindow.objects.count()), before)

    def test_too_long_or_unstorable_words_are_an_empty_page_recorded_with_count_0(self):
        self.enterContext(mock.patch.object(timezone, 'now', return_value=timezone.now()))  # one UTC day for the repeats
        f.encounter(self.ws, self.reviewer, title='Synthetic note')
        for words in ('n' * 241, 'note\x00', 'note\ud800', '\ud800'):
            with self.subTest(words=repr(words)), mock.patch.object(customer, 'search_page') as asked:
                self.assertEqual(self.search(words), {'encounters': [], 'next': None, 'total': None,
                                                       'workspace': str(self.ws.pk)})
                asked.assert_not_called()
        with mock.patch.object(customer, 'search_page', wraps=customer.search_page) as asked:
            self.assertEqual(self.search('n' * 240)['encounters'], [])  # at the bound: searched
        asked.assert_called_once()
        # each an empty page recorded with count 0 - the same page each time, so one row and its repeats
        (row,) = Record.objects.filter(view=read_audit.MEMBER_LIST)
        self.assertEqual((row.count, row.encounter_ids, row.filters), (0, [], {'list': 'search', 'before': None}))
        self.assertEqual(models.AccessRecordRepeat.objects.get(record_id=row.pk).repeats, 4)

    def test_the_fold_reads_only_the_newer_letters_the_words_hold(self):
        # translate reads FROM for every character of every row, so a search folds only the newer letters its words hold,
        # in either case: one they do not hold cannot take part in a match (SearchLetterTests finds each in either case)
        self.assertEqual(customer.search_fold('\u03b1\u03c3'), ('\u03c2\u0307', '\u03c3'))
        self.assertEqual(customer.search_fold('i\u0307 note'), ('\u03c2\u0307', '\u03c3'))
        self.assertEqual(customer.search_fold('x\u1c89'), ('\u03c2\u1c89\u0307', '\u03c3\u1c8a'))  # a capital
        self.assertEqual(customer.search_fold('\u0264 \U00010d70'),  # small letters: their capitals are folded
                         ('\u03c2\ua7cb\U00010d50\u0307', '\u03c3\u0264\U00010d70'))

    def test_the_words_are_counted_without_the_combining_dot_above(self):
        # the page lower-cases a dotted capital I to two characters (i and U+0307; SearchLetterTests), so 121 of them
        # typed lower-case are 242 characters its rule matches: counted without the dot they are 121 - searched, found,
        # as when typed as capitals; more than 240 letters, dots or none, are still an empty page, unsearched
        dotted = f.encounter(self.ws, self.reviewer, title='\u0130' * 121)
        for words in ('i\u0307' * 121, '\u0130' * 121):
            with self.subTest(words=f'{len(words)} characters'):
                self.assertEqual([row['id'] for row in self.search(words)['encounters']], [str(dotted.pk)])
        for words, length, read in (('n' * 241, 241, False), ('n' * 241 + '\u0307', 241, False),
                                    ('n' * 240 + '\u0307' * 3, 240, True)):
            with self.subTest(words=f'{len(words)} characters'):
                self.assertEqual(customer.search_length(words), length)
                with mock.patch.object(customer, 'search_page', wraps=customer.search_page) as asked:
                    self.assertEqual(self.search(words), {'encounters': [], 'next': None, 'total': None,
                                                           'workspace': str(self.ws.pk)})
                self.assertEqual(asked.called, read)
        membership = membership_of(self.reviewer)  # search_page's own guard counts the same way
        self.assertEqual(searched(membership, 'i\u0307' * 121), [str(dotted.pk)])
        with self.assertRaises(ValueError):
            customer.search_page(membership, 'n' * 241 + '\u0307')

    def test_a_get_or_head_answers_405_and_the_search_needs_the_csrf_token(self):
        self.assertEqual(self.member.get(SEARCH).status_code, 405)
        self.assertEqual(self.member.head(SEARCH).status_code, 405)
        strict = member_client(self.reviewer, enforce_csrf_checks=True)
        refused = strict.post(SEARCH, data=json.dumps({'text': 'note'}), content_type='application/json')
        self.assertEqual(refused.status_code, 403)
        self.assertFalse(Record.objects.filter(view=read_audit.MEMBER_LIST).exists())

    def test_a_marker_searched_for_is_in_no_record_event_log_or_header(self):
        # every form of the words (search_marker_hits: as typed, case-folded, percent- and plus-decoded, base64 and
        # base64url) in every row of SEARCH_MARKER_TABLES, the session store decoded, the answers' headers and cookies,
        # every log record as the console handler formats it - its exception text included - and what was printed
        # (integrated refutation round 1, phileak-0 and phileak-2)
        now = self.enterContext(mock.patch.object(timezone, 'now', return_value=timezone.now()))()  # one window
        marked = f.encounter(self.ws, self.reviewer, title='Synthetic ZZ-SEARCH-MARKER note')
        seen, logged, printed = [], [], io.StringIO()
        formatter = logging.Formatter()

        class Keep(logging.Handler):
            def emit(self, record):
                seen.append(f'{formatter.format(record)} {record.args!r}')
                logged.append((record.name, record.levelname, record.msg, record.args, record.exc_info))
        keep = Keep(level=logging.DEBUG)
        root = logging.getLogger()
        root.addHandler(keep)
        previous = root.level
        root.setLevel(logging.DEBUG)
        self.assertEqual(self.member.get(LIST).status_code, 200)  # the client's handler built before anything is watched
        before = every_row()
        session_before = dict(self.member.session.items())
        try:
            with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
                found = self.member.post(SEARCH, data=json.dumps({'text': 'zz-search-marker', 'before': None}),
                                         content_type='application/json')
                with self.settings(LIST_PAGES_LIMIT_PER_MEMBER=(1, 60)):  # and a refused one
                    refused = self.member.post(SEARCH, data=json.dumps({'text': 'zz-search-marker'}),
                                               content_type='application/json')
        finally:
            root.removeHandler(keep)
            root.setLevel(previous)
        self.assertEqual((found.status_code, refused.status_code), (200, 429))
        self.assertEqual(len(found.json()['encounters']), 1)
        # integrated refutation round 2, I2-3 (failclosed-1): CLOSED WORLD - what the two searches left anywhere is
        # compared as a whole with what they may leave (ids, counts, times and fixed words), so no form of the words,
        # derived however (hex, a digest, base32, ...), can hide in a row, a session, a header or a log record; the
        # form checks below are the second line
        self.assert_a_search_leaves_only_ids_counts_and_fixed_words(before, every_row(), session_before, found, refused,
                                                                   logged, printed.getvalue(), marked, now)
        stored = [json.dumps(list(table.objects.values()), default=str) for table in SEARCH_MARKER_TABLES]
        store = import_module(settings.SESSION_ENGINE).SessionStore()
        sessions = list(Session.objects.all())
        self.assertTrue(sessions)  # the member's own session is read, decoded
        for row in sessions:
            stored += [row.session_data, json.dumps(store.decode(row.session_data), default=str)]
        for answer in (found, refused):
            stored.append(json.dumps(dict(answer.items())))
            stored.append(json.dumps([morsel.OutputString() for morsel in answer.cookies.values()]))  # Set-Cookie
        stored += [json.dumps(seen), printed.getvalue()]
        self.assertTrue(models.SecurityEvent.objects.filter(event='list.rate_limited').exists())
        self.assertEqual(search_marker_hits(stored, ('zz-search-marker', 'search-marker')), [])
        # the control: each form, written where a guard reads, is found
        for form in sorted(search_marker_forms('zz-search-marker')):
            with self.subTest(form=form):
                self.assertTrue(search_marker_hits([json.dumps({'reason': form})], ('zz-search-marker',)))
                self.assertTrue(search_marker_hits([urllib.parse.quote_plus(form)], ('zz-search-marker',)))

    def test_searches_count_toward_the_members_limit_and_a_first_page_does_not(self):
        f.encounter(self.ws, self.reviewer, title='Synthetic note')
        moment = timezone.now()
        with self.settings(LIST_PAGES_LIMIT_PER_MEMBER=(2, 60)), mock.patch.object(timezone, 'now', return_value=moment):
            self.search('note')
            self.search('note')
            with mock.patch.object(customer, 'search_page', wraps=customer.search_page) as built:
                answer = self.member.post(SEARCH, data=json.dumps({'text': 'note'}), content_type='application/json')
            listed = self.member.get(LIST)
        built.assert_not_called()  # refused unread: the refused search never ran
        self.assertEqual((answer.status_code, answer.json()['error'], listed.status_code), (429, 'rate_limited', 200))
        self.assertEqual(models.SecurityEvent.objects.filter(event='list.rate_limited').count(), 1)


class PracticeNamedTests(SearchCase):
    """Integrated refutation round 1, exact-0 (I1-2): a member active in two practices - the oldest active membership
    is the one read, on every request - whose access to it is turned off between a list's pages, or a search's. Every
    page and search answer names the practice it was read in, as its member.list record does, so the page can tell
    another practice's page from its own list's (the page then draws none of it: app.js, I1-2)."""

    def setUp(self):
        super().setUp()
        models.Membership.objects.create(user=self.reviewer, workspace=self.other_ws, role=models.Membership.REVIEWER)
        self.ids = {'A': set(), 'B': set()}
        for _ in range(60):  # interleaved by created_at, so A's cursor has B's older rows to page to
            for name, ws, title in (('A', self.ws, 'Synthetic list note'), ('B', self.other_ws, 'Synthetic B list note')):
                self.ids[name] |= {str(enc.pk) for enc in mixed_practice(ws, self.reviewer, 1, title=title)}
        self.names = {'A': str(self.ws.pk), 'B': str(self.other_ws.pk)}

    def access_to_a(self, active):
        models.Membership.objects.filter(user=self.reviewer, workspace=self.ws).update(active=active)

    def read_in(self, answer, practice, *, rows_given=True):
        """The answer names ``practice``, its rows are that practice's, and its record names both."""
        record = models.AccessRecord.objects.filter(view=read_audit.MEMBER_LIST).latest('created_at')
        rows = {row['id'] for row in answer['encounters']}
        self.assertEqual(answer['workspace'], self.names[practice])
        self.assertTrue((rows or not rows_given) and rows <= self.ids[practice], practice)
        self.assertEqual((str(record.workspace_id), set(record.encounter_ids)), (self.names[practice], rows))

    def test_each_page_and_search_names_the_practice_it_was_read_in_across_an_access_change(self):
        first = self.page('documents')
        self.read_in(first, 'A')
        self.access_to_a(False)  # A's owner turns the member's access to A off: B is read now, with A's cursor
        self.read_in(self.page('documents', before=first['next']), 'B')
        self.read_in(self.search('list note'), 'B')  # a first search, too
        self.access_to_a(True)  # and back: the oldest active membership, A, is read again
        found = self.search('list note')
        self.read_in(found, 'A')
        self.access_to_a(False)
        self.read_in(self.search('list note', before=found['next']), 'B')
        self.read_in(self.page('queue'), 'B', rows_given=False)
        recent = self.page('recent')
        self.assertEqual(recent['workspace'], self.names['B'])


@override_settings(STORAGES=PLAIN_STATIC)
class SearchStatementTests(ListStatementTests):
    """C1: a search is at most 14 statements per request, a first page and a later one, the same at 51 and 5,000
    documents; its builder's own (customer.search_page) at most 4."""

    def test_each_page_is_the_same_number_of_statements_at_51_and_5000_documents(self):  # the lists' own, not run here
        pass

    def test_a_whole_list_on_its_first_page_pays_no_count(self):  # likewise
        pass

    def searches(self, client, before=None):
        with CaptureQueriesContext(connection) as seen:
            answer = client.post(SEARCH, data=json.dumps({'text': 'Synthetic bulk', 'before': before}),
                                 content_type='application/json')
        self.assertEqual(answer.status_code, 200)
        return len(seen.captured_queries), answer.json()

    def test_a_search_is_the_same_number_of_statements_at_51_and_5000_documents(self):
        counted = {}
        for name, user in (('small', self.small_user), ('large', self.large_user)):
            client = member_client(user)
            first, page = self.searches(client)
            later, _ = self.searches(client, page['next'])
            membership = membership_of(user)
            with CaptureQueriesContext(connection) as own:
                customer.search_page(membership, 'Synthetic bulk', page['next'])
            counted[name] = {'first': first, 'later': later, 'builder': len(own.captured_queries)}
        self.assertEqual(counted['small'], counted['large'])
        self.assertLessEqual(counted['large']['first'], 14)
        self.assertLessEqual(counted['large']['later'], 14)
        self.assertEqual(counted['large']['builder'], 3)  # the search, then the page's rounds and files


class SearchPlanTests(ListPlanTests):
    def test_every_statement_of_a_list_page_reads_an_index(self):  # ListPlanTests' own, not run again here
        pass

    def test_the_sessions_two_counts_read_an_index(self):  # likewise
        pass

    def test_the_search_reads_studio_enc_ws_time_and_scans_no_table(self):
        membership = membership_of(self.user)
        for words in ('zzz-no-such-words', 'Synthetic bulk note 1', 'σ'):
            with self.subTest(words=words):
                with CaptureQueriesContext(connection) as seen:
                    customer.search_page(membership, words)
                sql = seen.captured_queries[0]['sql']
                self.assertIn('strpos(', sql)
                with connection.cursor() as cursor:
                    cursor.execute('EXPLAIN ' + sql)
                    plan = '\n'.join(row[0] for row in cursor.fetchall())
                shape = '\n'.join(line for line in plan.splitlines() if 'Filter:' not in line)[:2000]  # the nodes only
                self.assertIn('studio_enc_ws_time', plan, shape)
                for table in ('studio_encounter', 'studio_codinground', 'studio_sourcefile', 'studio_sourcerevision'):
                    self.assertNotIn(f'Seq Scan on {table}', plan, shape)


# Section 8's bench shape (lane M's ops/bench/benchdata.py STATE_MIX, "a live-like mix of today's derived states"): of
# 1,000 documents, 30 ready, 15 needs_review and 5 awaiting_answer - about one in twenty waits - 30 failed, 20 no_codes
# and 900 reviewed; each document has its finished round.
LIVE_STATE_MIX = (['ready'] * 30 + ['needs_review'] * 15 + ['awaiting_answer'] * 5 + ['failed'] * 30 + ['no_codes'] * 20
                  + ['reviewed'] * 900)


def live_like_practice(ws, by, count, *, seed):
    """``count`` documents of ``ws`` shaped like live's and like section 8's bench: each with its revision and its
    finished coding round, a state of LIVE_STATE_MIX, a quarter with a PDF first file, each its own created_at (the
    first newest) - made in bulk, for the plans at a practice that is most of the table."""
    chance = random.Random(seed)
    now = timezone.now()
    insurance = ('medicare', 'medicaid', 'commercial', 'unknown')
    encounters = models.Encounter.objects.bulk_create(
        [models.Encounter(workspace=ws, title=f'Synthetic GI note {n:05d} colonoscopy with biopsy', created_by=by,
                          state=chance.choice(LIVE_STATE_MIX),
                          user_values={'service_date': '2026-11-02', 'insurance': chance.choice(insurance)})
         for n in range(count)], batch_size=2000)
    revisions = Revision.objects.bulk_create(
        [Revision(encounter=enc, number=1, kind=Revision.UPLOAD if n % 4 == 0 else Revision.PASTE,
                  synthetic_attested_by=by, synthetic_attested_at=now, created_by=by)
         for n, enc in enumerate(encounters)], batch_size=2000)
    Round.objects.bulk_create([Round(encounter=enc, revision=rev, number=1, trigger=Round.UPLOAD, context={},
                                     state=Round.DONE) for enc, rev in zip(encounters, revisions)], batch_size=2000)
    SourceFile.objects.bulk_create([SourceFile(encounter=enc, original_name='synthetic.pdf', media_type=PDF, size=4448,
                                               sha256='0' * 64, storage_name=f'{ws.pk}/live-{uuid.uuid4()}',
                                               uploaded_by=by)
                                    for n, enc in enumerate(encounters) if n % 4 == 0], batch_size=2000)
    table, revision_table = models.Encounter._meta.db_table, Revision._meta.db_table
    with connection.cursor() as cursor:  # its current revision, and its own created_at: one statement each
        cursor.execute(f'UPDATE {table} e SET current_revision_id = r.id FROM {revision_table} r '
                       'WHERE r.encounter_id = e.id AND e.workspace_id = %s', [ws.pk])
        cursor.execute(f"UPDATE {table} e SET created_at = %s - n.k * interval '1 second' FROM (SELECT id, "
                       f'row_number() OVER (ORDER BY title) AS k FROM {table} WHERE workspace_id = %s) n '
                       'WHERE n.id = e.id', [now, ws.pk])


class PlanAtEighteenThousandTests(TransactionTestCase):
    """D-R2-37 (RELEASE-2-SPEC R2-19's tests, R2-23's acceptance, section 8's plans): at one practice of 18,000 documents
    among 20,000 - most of the table - shaped like live's (live_like_practice) and committed, so VACUUM can run: after
    ANALYZE alone (the state right after a seed) and again after VACUUM ANALYZE, every statement that reads a page - its
    rows, round flags and first files, the documents' and the queue's, first and later - and the search reads by an index:
    no Seq Scan on studio_encounter, studio_codinground or studio_sourcefile (nor the revisions, for the search). An
    exact COUNT of a whole list - the two first pages' totals and session_json's two counts - cannot avoid reading the
    practice when it is most of the table, so it is held to its time instead: at most 20 ms, the best of five (planning
    and execution, as EXPLAIN ANALYZE reports them), and it reads no whole rounds or files table either. The first state
    is ANALYZE's alone, controlled and checked: autovacuum is off on the four tables for the test (an autovacuum of the
    rounds inside the build let the EXISTS mutant R1-13 pass here; lane S refutation round 2, plans[1]), and no page of
    the rounds is marked all-visible until the second state's VACUUM, which marks them."""

    COUNT_MS = 20

    def autovacuum_back(self, tables):
        with connection.cursor() as cursor:
            for table in tables:
                cursor.execute(f'ALTER TABLE {table} RESET (autovacuum_enabled)')

    def rounds_all_visible(self) -> int:
        """The rounds table's pages the visibility map marks all-visible, as the planner reads them (relallvisible, set
        by ANALYZE and VACUUM: 0 until a VACUUM has marked a page)."""
        with connection.cursor() as cursor:
            cursor.execute('SELECT relallvisible FROM pg_class WHERE oid = to_regclass(%s)', ['studio_codinground'])
            return cursor.fetchone()[0]

    def explain(self, sql):
        """(the plan EXPLAIN ANALYZE reports for ``sql``, its planning and execution time in ms)."""
        with connection.cursor() as cursor:
            cursor.execute('EXPLAIN (ANALYZE, TIMING OFF) ' + sql)
            lines = [row[0] for row in cursor.fetchall()]
        took = [float(line.split(':')[1].split()[0]) for line in lines
                if line.startswith(('Planning Time:', 'Execution Time:'))]
        self.assertEqual(len(took), 2, lines[-3:])
        return '\n'.join(lines), sum(took)

    def test_at_one_practice_of_18000_pages_and_searches_read_an_index_and_each_count_is_held_to_its_time(self):
        tables = ('studio_encounter', 'studio_codinground', 'studio_sourcefile', 'studio_sourcerevision')
        with connection.cursor() as cursor:  # 'after ANALYZE' is ANALYZE's alone: no autovacuum reaches the seed first
            for table in tables:
                cursor.execute(f'ALTER TABLE {table} SET (autovacuum_enabled = false)')
        self.addCleanup(self.autovacuum_back, tables)
        ws, others = f.workspace('Synthetic practice of 18,000'), f.workspace('Synthetic other practices')
        user = f.member(ws)
        live_like_practice(ws, user, 18000, seed=18000)
        live_like_practice(others, f.member(others), 2000, seed=2000)
        self.assertEqual(models.Encounter.objects.count(), 20000)
        membership = membership_of(user)
        waiting = models.Encounter.objects.filter(workspace=ws, state__in=customer.QUEUE_STATES).count()
        self.assertTrue(700 < waiting < 1100, waiting)  # about one in twenty, each with its round
        for state, command in (('after ANALYZE', 'ANALYZE'), ('after VACUUM ANALYZE', 'VACUUM ANALYZE')):
            with connection.cursor() as cursor:
                for table in tables:
                    cursor.execute(f'{command} {table}')
            if command == 'ANALYZE':  # the state checked, not assumed: no VACUUM has reached the rounds of the seed
                self.assertEqual(self.rounds_all_visible(), 0, state)
            else:  # and the reading sees a VACUUM when one has run
                self.assertGreater(self.rounds_all_visible(), 0, state)
            with CaptureQueriesContext(connection) as seen:
                documents = customer.list_page(membership, 'documents')
                customer.list_page(membership, 'documents', documents['next'])
                queue = customer.list_page(membership, 'queue')
                customer.list_page(membership, 'queue', queue['next'])
                counts = customer.session_json(user, membership)['counts']
                for words in ('zzz-no-such-words', 'note 01234 colonoscopy', '\u03c3'):
                    customer.search_page(membership, words)
            self.assertEqual((documents['total'], queue['total'], counts), (18000, waiting,
                                                                             {'documents': 18000, 'queue': waiting}))
            statements = [item['sql'] for item in seen.captured_queries]
            self.assertEqual(sum(sql.startswith('SELECT COUNT(*)') for sql in statements), 4)
            self.assertEqual(sum('strpos(' in sql for sql in statements), 3)
            for sql in statements:
                plan, took = self.explain(sql)
                with self.subTest(state=state, statement=sql[:100]):
                    if sql.startswith('SELECT COUNT(*)'):
                        best = min([took] + [self.explain(sql)[1] for _ in range(4)])
                        self.assertLessEqual(best, self.COUNT_MS, plan)
                        tables = ('studio_codinground', 'studio_sourcefile')
                    else:
                        tables = ('studio_encounter', 'studio_codinground', 'studio_sourcefile') + (
                            ('studio_sourcerevision',) if 'strpos(' in sql else ())
                        if 'LIMIT 51' in sql:  # a page's or the search's rows: along the practice's own index
                            self.assertTrue('studio_enc_ws_time' in plan or 'studio_enc_ws_queue' in plan, plan[:2000])
                    for table in tables:
                        self.assertNotIn(f'Seq Scan on {table}', plan, plan[:2000])


class SearchOutdatedPageTests(SearchCase):
    def test_release_1s_page_is_told_to_reload_on_the_search_before_any_read(self):
        f.encounter(self.ws, self.reviewer, title='Synthetic note')
        old = member_client(self.reviewer, **{client_contract.WSGI_KEY: RELEASE_1_BUILD})
        before = (Record.objects.count(), models.RateWindow.objects.count())
        answer = old.post(SEARCH, data=json.dumps({'text': 'note'}), content_type='application/json')
        self.assertEqual((answer.status_code, answer.json()), (409, client_contract.OUTDATED))
        self.assertEqual((Record.objects.count(), models.RateWindow.objects.count()), before)
