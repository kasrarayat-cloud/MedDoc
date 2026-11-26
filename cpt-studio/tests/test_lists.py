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
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import client_contract, customer, models, paging, read_audit
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
        self.assertEqual(self.page(), {'encounters': [], 'next': None, 'total': 0})

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
    """At 20,000 documents (one practice of 2,000 among them), each statement of a list page reads an index - the
    documents page studio_enc_ws_time, the queue page studio_enc_ws_queue - and never scans studio_encounter,
    studio_codinground or studio_sourcefile (tests/test_r1_repair_s.py reads the reads page the same way)."""

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
                for sql, plan in found:
                    for table in ('studio_encounter', 'studio_codinground', 'studio_sourcefile'):
                        self.assertNotIn(f'Seq Scan on {table}', plan, (sql[:120], plan[:1500]))


# --- the search (R2-20) --------------------------------------------------------------------------------------------

import logging  # noqa: E402 - this section's own imports
import random  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

from django.conf import settings  # noqa: E402

SEARCH = '/api/encounters/search'
ROW_TEXT = Path(settings.BASE_DIR) / 'tests' / 'frontend' / 'row_text.cjs'
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
            if len(words) > customer.SEARCH_MAX_CHARS:
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


class SearchTests(SearchCase):
    def test_the_answer_is_the_lists_shape_newest_first_with_no_total(self):
        made = mixed_practice(self.ws, self.reviewer, 30)
        answer = self.search('list note')
        self.assertEqual(set(answer), {'encounters', 'next', 'total'})
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
        f.encounter(self.ws, self.reviewer, title='Synthetic note')
        for words in ('n' * 241, 'note\x00', 'note\ud800', '\ud800'):
            with self.subTest(words=repr(words)), mock.patch.object(customer, 'search_page') as asked:
                self.assertEqual(self.search(words), {'encounters': [], 'next': None, 'total': None})
                asked.assert_not_called()
        with mock.patch.object(customer, 'search_page', wraps=customer.search_page) as asked:
            self.assertEqual(self.search('n' * 240)['encounters'], [])  # at the bound: searched
        asked.assert_called_once()
        # each an empty page recorded with count 0 - the same page each time, so one row and its repeats
        (row,) = Record.objects.filter(view=read_audit.MEMBER_LIST)
        self.assertEqual((row.count, row.encounter_ids, row.filters), (0, [], {'list': 'search', 'before': None}))
        self.assertEqual(models.AccessRecordRepeat.objects.get(record_id=row.pk).repeats, 4)

    def test_a_get_or_head_answers_405_and_the_search_needs_the_csrf_token(self):
        self.assertEqual(self.member.get(SEARCH).status_code, 405)
        self.assertEqual(self.member.head(SEARCH).status_code, 405)
        strict = member_client(self.reviewer, enforce_csrf_checks=True)
        refused = strict.post(SEARCH, data=json.dumps({'text': 'note'}), content_type='application/json')
        self.assertEqual(refused.status_code, 403)
        self.assertFalse(Record.objects.filter(view=read_audit.MEMBER_LIST).exists())

    def test_a_marker_searched_for_is_in_no_record_event_log_or_header(self):
        f.encounter(self.ws, self.reviewer, title='Synthetic ZZ-SEARCH-MARKER note')
        seen = []

        class Keep(logging.Handler):
            def emit(self, record):
                seen.append(f'{record.getMessage()} {record.args!r}')
        keep = Keep(level=logging.DEBUG)
        root = logging.getLogger()
        root.addHandler(keep)
        previous = root.level
        root.setLevel(logging.DEBUG)
        try:
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
        stored = json.dumps([[str(value) for value in row.__dict__.values()] for row in
                             [*Record.objects.all(), *models.SecurityEvent.objects.all(), *models.RateWindow.objects.all()]])
        for answer in (found, refused):
            stored += json.dumps(dict(answer.items()))
        stored += json.dumps(seen)
        self.assertTrue(models.SecurityEvent.objects.filter(event='list.rate_limited').exists())
        for marker in ('zz-search-marker', 'ZZ-SEARCH-MARKER', 'search-marker'):
            self.assertNotIn(marker, stored)

    def test_searches_count_toward_the_members_limit_and_a_first_page_does_not(self):
        f.encounter(self.ws, self.reviewer, title='Synthetic note')
        moment = timezone.now()
        with self.settings(LIST_PAGES_LIMIT_PER_MEMBER=(2, 60)), mock.patch.object(timezone, 'now', return_value=moment):
            self.search('note')
            self.search('note')
            answer = self.member.post(SEARCH, data=json.dumps({'text': 'note'}), content_type='application/json')
            listed = self.member.get(LIST)
        self.assertEqual((answer.status_code, answer.json()['error'], listed.status_code), (429, 'rate_limited', 200))
        self.assertEqual(models.SecurityEvent.objects.filter(event='list.rate_limited').count(), 1)


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


class SearchOutdatedPageTests(SearchCase):
    def test_release_1s_page_is_told_to_reload_on_the_search_before_any_read(self):
        f.encounter(self.ws, self.reviewer, title='Synthetic note')
        old = member_client(self.reviewer, **{client_contract.WSGI_KEY: RELEASE_1_BUILD})
        before = (Record.objects.count(), models.RateWindow.objects.count())
        answer = old.post(SEARCH, data=json.dumps({'text': 'note'}), content_type='application/json')
        self.assertEqual((answer.status_code, answer.json()), (409, client_contract.OUTDATED))
        self.assertEqual((Record.objects.count(), models.RateWindow.objects.count()), before)
