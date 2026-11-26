"""A record of every view and download of a document (release 1, C1; studio.read_audit): one AccessRecord per read,
written before the answer is served, holding ids, counts and fixed words only; a read whose row cannot be written answers
503 with the fixed sentence and no PHI (the seeded markers ZZ-TITLE-MARKER and ZZ-TEXT-MARKER never appear in it); a read
of another practice's document is the same 404 with a refused row; the page's poll repeats at most once a minute per
sign-in; HEAD is served by none of these views (405), so it is never served unrecorded. Every AuditEvent carries the
request's client, sign-in reference and request id. The console's reads are held here too (the ops.* kinds). Synthetic
data only."""
import json
import uuid
from datetime import timedelta
from unittest import mock

from django.db import DatabaseError, connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from studio import audit, customer, models, read_audit, request_meta
from tests.support import coding as f
from tests.support import operator as ops
from tests.support import rounds as r
from tests.test_frontend import PLAIN_STATIC

Round, Record = models.CodingRound, models.AccessRecord
TITLE_MARKER, TEXT_MARKER = 'ZZ-TITLE-MARKER', 'ZZ-TEXT-MARKER'
REQUEST_ID = '0123456789abcdef0123456789abcdef'
CPT = 'cpt.quillmd.com'
TEXT_MEDIA = 'text/plain'


def member_client(user, host=CPT, **extra):
    """A client signed in as ``user`` at the cpt door, with the session keys the door writes (a sign-in reference)."""
    client = Client(HTTP_HOST=host, HTTP_X_REQUEST_ID=REQUEST_ID, **extra)
    client.force_login(user)
    return ops.mark_signed_in(client, door=request_meta.CPT)


def write_fails():
    """Every AccessRecord write fails, as a full disk or a lost connection would make it."""
    return mock.patch.object(Record.objects, 'create', side_effect=DatabaseError('synthetic write failure'))


@override_settings(STORAGES=PLAIN_STATIC)
class ReadCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.enc = self.done(title=f'{TITLE_MARKER} synthetic colonoscopy note')
        self.text = f.encounter(self.ws, self.reviewer, title=f'{TITLE_MARKER} synthetic text note')
        f.upload(self.text, self.reviewer, data=f'SYNTHETIC NOTE {TEXT_MARKER} polyp removed.'.encode(),
                 filename='synthetic-note.txt', media_type=TEXT_MEDIA)
        self.member = member_client(self.reviewer)

    def rows(self, **filters):
        return list(Record.objects.filter(**filters).order_by('created_at', 'pk'))

    def report(self):
        made = self.member.post(f'/api/encounters/{self.enc.pk}/reports', data=json.dumps(
            {'kind': 'draft', 'fmt': 'pdf', 'round': 1}), content_type='application/json')
        self.assertEqual(made.status_code, 201, made.content)
        return models.ExportArtifact.objects.get(pk=made.json()['id'])

    def reads(self):
        """Every member read of a document, each with the kind it records."""
        export = self.report()
        return {
            read_audit.MEMBER_LIST: '/api/encounters',
            read_audit.MEMBER_DETAIL: f'/api/encounters/{self.text.pk}',
            read_audit.MEMBER_INLINE: f'/api/encounters/{self.text.pk}/original?view=1',
            read_audit.MEMBER_DOWNLOAD: f'/api/encounters/{self.text.pk}/original',
            read_audit.MEMBER_REPORT_DOWNLOAD: f'/api/reports/{export.pk}/download',
        }


class MemberReadTests(ReadCase):
    def test_each_kind_of_read_writes_exactly_one_row_with_its_ids(self):
        export = self.report()
        cases = (
            # release 2 (R2-21): a list's row names the documents of the page it served, newest first
            ('/api/encounters', read_audit.MEMBER_LIST, [str(self.text.pk), str(self.enc.pk)], None),
            (f'/api/encounters/{self.enc.pk}', read_audit.MEMBER_DETAIL, [str(self.enc.pk)], None),
            (f'/api/encounters/{self.enc.pk}/original?view=1', read_audit.MEMBER_INLINE, [str(self.enc.pk)], None),
            (f'/api/encounters/{self.enc.pk}/original', read_audit.MEMBER_DOWNLOAD, [str(self.enc.pk)], None),
            (f'/api/reports/{export.pk}/download', read_audit.MEMBER_REPORT_DOWNLOAD, [str(self.enc.pk)], export.pk),
        )
        for url, kind, encounter_ids, export_id in cases:
            with self.subTest(kind=kind):
                before = Record.objects.count()
                self.assertEqual(self.member.get(url).status_code, 200)
                self.assertEqual(Record.objects.count(), before + 1)
                row = Record.objects.latest('created_at')
                self.assertEqual((row.view, row.encounter_ids, row.export_id, row.workspace_id, row.outcome),
                                 (kind, encounter_ids, export_id, self.ws.pk, read_audit.SERVED))
                self.assertEqual((row.actor_id, row.actor_kind, row.actor_role, row.host),
                                 (self.reviewer.pk, 'human', 'reviewer', 'cpt'))
                self.assertEqual((row.client, row.request_id), ('127.0.0.1', REQUEST_ID))
                self.assertEqual(row.sign_in_ref, uuid.UUID(self.member.session[request_meta.SESSION_SIGN_IN_REF]))
                self.assertNotIn(TITLE_MARKER, json.dumps([row.filters, row.reason]))

    def test_the_list_records_the_practice_the_time_and_how_many_rows_it_showed(self):
        # release 2 (R2-21, rewritten in the open): a list is served a page at a time, so its row names the documents of
        # the page it served, in the order shown, with the list and the cursor it was asked with - here the whole
        # practice, which fits on one page
        before = timezone.now()
        shown = self.member.get('/api/encounters').json()['encounters']
        row = Record.objects.get(view=read_audit.MEMBER_LIST)
        self.assertEqual((row.count, row.workspace_id, row.encounter_ids),
                         (len(shown), self.ws.pk, [item['id'] for item in shown]))
        self.assertEqual(row.encounter_ids, [str(self.text.pk), str(self.enc.pk)])
        self.assertEqual(row.filters, {'list': 'documents', 'before': None})
        self.assertEqual(row.count, self.ws.encounters.count())
        self.assertTrue(before <= row.as_of <= timezone.now())

    def test_every_call_records_again_and_downloads_record_their_format(self):
        for _ in range(3):
            self.assertEqual(self.member.get(f'/api/encounters/{self.text.pk}/original').status_code, 200)
            self.assertEqual(self.member.get(f'/api/encounters/{self.text.pk}').status_code, 200)
        self.assertEqual(len(self.rows(view=read_audit.MEMBER_DOWNLOAD)), 3)
        self.assertEqual(len(self.rows(view=read_audit.MEMBER_DETAIL)), 3)
        self.assertEqual({tuple(row.filters.items()) for row in self.rows(view=read_audit.MEMBER_DOWNLOAD)},
                         {(('format', 'original'),)})

    def test_a_poll_writes_at_most_one_row_a_minute_per_sign_in_and_document(self):
        url = f'/api/encounters/{self.enc.pk}'
        start = timezone.now()  # clear of UTC midnight, never earlier than now: a poll leans only on a row of its own day
        if (start + timedelta(minutes=2)).date() != start.date():  # (refutation round 2, phi-3's class)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1, seconds=30)
        with mock.patch.object(timezone, 'now', return_value=start):
            for _ in range(5):
                self.assertEqual(self.member.get(url, HTTP_X_CPT_POLL='1').status_code, 200)
        self.assertEqual(len(self.rows(view=read_audit.MEMBER_DETAIL)), 1)
        with mock.patch.object(timezone, 'now', return_value=start + timedelta(seconds=59)):
            self.member.get(url, HTTP_X_CPT_POLL='1')
        self.assertEqual(len(self.rows(view=read_audit.MEMBER_DETAIL)), 1)
        with mock.patch.object(timezone, 'now', return_value=start + timedelta(seconds=61)):
            self.member.get(url, HTTP_X_CPT_POLL='1')
        self.assertEqual(len(self.rows(view=read_audit.MEMBER_DETAIL)), 2)
        # another sign-in of the same person polls on its own count, and a request that is no poll always records
        other = member_client(self.reviewer)
        with mock.patch.object(timezone, 'now', return_value=start + timedelta(seconds=62)):
            other.get(url, HTTP_X_CPT_POLL='1')
            self.member.get(url)
        self.assertEqual(len(self.rows(view=read_audit.MEMBER_DETAIL)), 4)

    def test_head_is_served_by_none_of_the_reads_so_nothing_goes_unrecorded(self):
        # Django answers HEAD through the view: these views answer it 405 with no body (require_GET; the list's own
        # method check), so a HEAD serves no byte of PHI and needs no row. A view that ever serves HEAD must record it.
        for kind, url in self.reads().items():
            before = Record.objects.count()
            with self.subTest(kind=kind):
                answer = self.member.head(url)
                self.assertEqual((answer.status_code, answer.content), (405, b''))
                self.assertNotIn('Content-Disposition', answer)
                self.assertEqual(Record.objects.count(), before)

    def test_another_practices_document_is_the_same_404_with_a_refused_row(self):
        outsider = member_client(self.outsider)
        export = self.report()
        missing = uuid.uuid4()
        for url, kind in ((f'/api/encounters/{self.enc.pk}', read_audit.MEMBER_DETAIL),
                          (f'/api/encounters/{self.enc.pk}/original', read_audit.MEMBER_DOWNLOAD),
                          (f'/api/encounters/{self.enc.pk}/original?view=1', read_audit.MEMBER_INLINE),
                          (f'/api/reports/{export.pk}/download', read_audit.MEMBER_REPORT_DOWNLOAD)):
            with self.subTest(kind=kind):
                refused = outsider.get(url)
                absent = outsider.get(url.replace(str(self.enc.pk), str(missing)).replace(str(export.pk), str(missing)))
                self.assertEqual((refused.status_code, refused.content), (absent.status_code, absent.content))
                self.assertEqual(refused.status_code, 404)
                row = Record.objects.filter(view=kind, actor_id=self.outsider.pk).get()
                self.assertEqual((row.outcome, row.encounter_ids, row.workspace_id, row.actor_role),
                                 (read_audit.REFUSED, [str(self.enc.pk)], self.ws.pk, ''))
        self.assertFalse(Record.objects.filter(encounter_ids__contains=[str(missing)]).exists())  # a missing one: no row
        # a refused row that cannot be written changes nothing in the answer
        with write_fails():
            self.assertEqual(outsider.get(f'/api/encounters/{self.enc.pk}').status_code, 404)

    def test_the_rows_hold_ids_counts_and_fixed_words_never_titles_names_or_text(self):
        for url in self.reads().values():
            self.member.get(url)
        stored = json.dumps([{key: str(value) for key, value in row.__dict__.items() if not key.startswith('_')}
                             for row in Record.objects.all()])
        for marker in (TITLE_MARKER, TEXT_MARKER, 'synthetic-note', 'Synthetic colonoscopy'):
            self.assertNotIn(marker, stored)


class FailClosedTests(ReadCase):
    def test_a_read_whose_row_cannot_be_written_answers_503_and_shows_nothing(self):
        reads = self.reads()
        with write_fails():
            for kind, url in reads.items():
                with self.subTest(kind=kind):
                    answer = self.member.get(url)
                    self.assertEqual(answer.status_code, 503)
                    self.assertEqual(answer.json(), {'error': read_audit.NOT_RECORDED, 'details': {}})
                    for marker in (TITLE_MARKER, TEXT_MARKER):
                        self.assertNotIn(marker.encode(), answer.content)
                    self.assertNotIn('Content-Disposition', answer)
        self.assertFalse(Record.objects.exists())
        for kind, url in reads.items():  # the control: written again, each read serves its data
            with self.subTest(control=kind):
                self.assertEqual(self.member.get(url).status_code, 200)

    def test_a_poll_whose_first_row_cannot_be_written_shows_nothing_either(self):
        with write_fails():
            answer = self.member.get(f'/api/encounters/{self.enc.pk}', HTTP_X_CPT_POLL='1')
        self.assertEqual(answer.status_code, 503)
        self.assertNotIn(TITLE_MARKER.encode(), answer.content)


class AuditEventRequestTests(ReadCase):
    def test_an_event_a_request_causes_carries_its_client_sign_in_and_request_id(self):
        export = self.report()
        event = models.AuditEvent.objects.get(event='export.created', data__export=str(export.pk))
        self.assertEqual((event.client, event.request_id), ('127.0.0.1', REQUEST_ID))
        self.assertEqual(event.sign_in_ref, uuid.UUID(self.member.session[request_meta.SESSION_SIGN_IN_REF]))

    def test_an_event_written_outside_a_request_leaves_them_empty(self):
        event = audit.record(self.ws, 'coding.round_done', encounter=self.enc, actor=None, round='x')
        event.refresh_from_db()
        self.assertEqual((event.client, event.sign_in_ref, event.request_id), (None, None, None))


class ActivityQueryTests(ReadCase):
    def test_the_documents_activity_reads_only_the_events_it_shows_in_sql(self):
        audit.record(self.ws, 'export.reused', encounter=self.enc, actor=self.reviewer, export='x')
        audit.record(self.ws, 'operator.viewed', encounter=self.enc, actor=self.reviewer, view='detail')
        with CaptureQueriesContext(connection) as queries:
            activity = customer.activity_json(self.enc)
        reads = [query['sql'] for query in queries.captured_queries if '"studio_auditevent"' in query['sql']]
        self.assertEqual(len(reads), 1)
        self.assertIn('"studio_auditevent"."event" IN (', reads[0])
        for name in customer.ACTIVITY_EVENTS:
            self.assertIn(f"'{name}'", reads[0])
        self.assertNotIn("'export.reused'", reads[0])
        self.assertTrue(activity)


class ConsoleReadCase(ReadCase):
    def setUp(self):
        super().setUp()
        self.operator_user = f.user('platform-operator')
        self.ops = ops.admin_client(self.operator_user, HTTP_X_REQUEST_ID=REQUEST_ID)

    def open_content(self, encounter):
        answer = self.ops.post(f'/ops/encounters/{encounter.pk}/content', {'reason': 'failed_processing',
                                                                           'reference': 'INC-7'})
        self.assertEqual(answer.status_code, 303)

    def console_reads(self):
        """Every console read, with the kind it records: (method, path, body)."""
        return {
            read_audit.OPS_LIST: ('get', '/ops/', None),
            read_audit.OPS_WORKSPACE: ('get', f'/ops/workspaces/{self.ws.pk}', None),
            read_audit.OPS_SPENDING: ('get', '/ops/spending', None),
            read_audit.OPS_ACTIVITY: ('get', '/ops/activity', None),
            read_audit.OPS_DETAIL: ('get', f'/ops/encounters/{self.text.pk}', None),
            read_audit.OPS_CONTENT_OPEN: ('post', f'/ops/encounters/{self.text.pk}/content',
                                          {'reason': 'practice_check', 'reference': 'REQ-12'}),
            read_audit.OPS_ORIGINAL: ('get', f'/ops/encounters/{self.text.pk}/original', None),
            read_audit.OPS_READS: ('get', '/ops/activity/reads', None),
        }


class ConsoleReadTests(ConsoleReadCase):
    def test_each_console_read_writes_exactly_one_row(self):
        self.open_content(self.text)
        for kind, (method, path, body) in self.console_reads().items():
            with self.subTest(kind=kind):
                before = Record.objects.filter(view=kind).count()
                answer = getattr(self.ops, method)(path, body) if body else getattr(self.ops, method)(path)
                self.assertIn(answer.status_code, (200, 303))
                self.assertEqual(Record.objects.filter(view=kind).count(), before + 1)
                row = Record.objects.filter(view=kind).latest('created_at')
                self.assertEqual((row.actor_id, row.actor_role, row.host, row.outcome, row.request_id),
                                 (self.operator_user.pk, 'operator', 'admin', read_audit.SERVED, REQUEST_ID))
                self.assertEqual(row.sign_in_ref, uuid.UUID(self.ops.session[request_meta.SESSION_SIGN_IN_REF]))

    def test_the_rows_name_what_each_page_showed(self):
        self.open_content(self.text)
        for _kind, (method, path, body) in self.console_reads().items():
            getattr(self.ops, method)(path, body) if body else getattr(self.ops, method)(path)
        listed = Record.objects.get(view=read_audit.OPS_LIST)
        self.assertEqual(set(listed.encounter_ids), {str(self.enc.pk), str(self.text.pk)})
        self.assertEqual((listed.count, listed.workspace_id), (2, None))
        self.assertEqual(Record.objects.get(view=read_audit.OPS_WORKSPACE).workspace_id, self.ws.pk)
        self.assertEqual(Record.objects.get(view=read_audit.OPS_SPENDING).encounter_ids, [str(self.enc.pk)])
        opened = Record.objects.filter(view=read_audit.OPS_CONTENT_OPEN).latest('created_at')
        self.assertEqual((opened.reason, opened.encounter_ids), ('practice_check: REQ-12', [str(self.text.pk)]))
        original = Record.objects.get(view=read_audit.OPS_ORIGINAL)
        self.assertEqual((original.encounter_ids, original.filters), ([str(self.text.pk)], {'format': 'original'}))
        self.assertEqual(Record.objects.get(view=read_audit.OPS_READS).filters,
                         {'account': None, 'workspace': None, 'kind': None, 'day': None, 'before': None})

    def test_head_is_served_by_no_console_read_so_nothing_goes_unrecorded(self):
        self.open_content(self.text)
        for kind, (method, path, _body) in self.console_reads().items():
            if method != 'get':
                continue
            before = Record.objects.count()
            with self.subTest(kind=kind):
                answer = self.ops.head(path)
                self.assertEqual((answer.status_code, answer.content), (405, b''))
                self.assertNotIn('Content-Disposition', answer)
                self.assertEqual(Record.objects.count(), before)

    def test_a_refusal_answering_a_practices_page_records_that_read_first(self):
        answer = self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'back': str(self.ws.pk),
                                                   'username': 'X', 'role': 'viewer',
                                                   'requested_by': 'Synthetic ticket 7'})
        self.assertEqual(answer.status_code, 400)
        self.assertEqual(Record.objects.filter(view=read_audit.OPS_WORKSPACE, workspace_id=self.ws.pk).count(), 1)
        with write_fails():
            again = self.ops.post('/ops/people/add', {'workspace': str(self.ws.pk), 'back': str(self.ws.pk),
                                                      'username': 'X', 'role': 'viewer',
                                                      'requested_by': 'Synthetic ticket 7'})
        self.assertEqual((again.status_code, again.content.decode()), (503, read_audit.NOT_RECORDED))

    def test_the_reads_page_lists_rows_by_account_practice_kind_and_day(self):
        # one moment clear of UTC midnight, never earlier than now (refutation round 3, regression-8's class, as the poll
        # test above): the reads are filed under their UTC day, so a midnight between them and today's page on the real
        # clock filed them under yesterday
        start = timezone.now()
        if (start + timedelta(minutes=2)).date() != start.date():
            start = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1, seconds=30)
        with mock.patch.object(timezone, 'now', return_value=start):
            self.member.get('/api/encounters')
            self.member.get(f'/api/encounters/{self.enc.pk}')
            member_client(self.outsider).get(f'/api/encounters/{self.enc.pk}')  # refused
            page = self.ops.get('/ops/activity/reads').content.decode()
            for text in ('member.list · cpt', 'member.detail · cpt', 'chip bad">Refused', str(self.enc.pk)[:8],
                         self.reviewer.username, self.outsider.username, REQUEST_ID):
                with self.subTest(text=text):
                    self.assertIn(text, page)
            self.assertNotIn(TITLE_MARKER, page)
            only = self.ops.get(f'/ops/activity/reads?account={self.outsider.pk}').content.decode()
            self.assertIn('chip bad">Refused', only)
            self.assertNotIn('member.list · cpt', only)
            kind = self.ops.get('/ops/activity/reads?kind=member.list').content.decode()
            self.assertIn('member.list · cpt', kind)
            self.assertNotIn('chip bad">Refused', kind)
            today = timezone.now().date().isoformat()
            self.assertIn(str(self.enc.pk)[:8], self.ops.get(f'/ops/activity/reads?day={today}').content.decode())
            self.assertNotIn(str(self.enc.pk)[:8], self.ops.get('/ops/activity/reads?day=2001-01-01').content.decode())
            self.assertEqual(self.ops.get('/ops/activity/reads?day=2001-13-40&kind=x&account=y').status_code, 200)
            # opening the page is itself recorded, with what it was asked for
            asked = Record.objects.filter(view=read_audit.OPS_READS, filters__account=str(self.outsider.pk)).get()
            self.assertEqual(asked.filters['kind'], None)


class ConsoleFailClosedTests(ConsoleReadCase):
    def test_a_console_read_whose_row_cannot_be_written_answers_503_and_shows_nothing(self):
        self.open_content(self.text)
        reads = self.console_reads()
        with write_fails():
            for kind, (method, path, body) in reads.items():
                with self.subTest(kind=kind):
                    answer = getattr(self.ops, method)(path, body) if body else getattr(self.ops, method)(path)
                    self.assertEqual((answer.status_code, answer.content.decode()), (503, read_audit.NOT_RECORDED))
                    self.assertNotIn('Content-Disposition', answer)

    def test_content_whose_opening_cannot_be_recorded_stays_closed(self):
        with write_fails():
            answer = self.ops.post(f'/ops/encounters/{self.text.pk}/content', {'reason': 'failed_processing',
                                                                               'reference': 'INC-7'})
        self.assertEqual(answer.status_code, 503)
        self.assertEqual(self.ops.get(f'/ops/encounters/{self.text.pk}/original').status_code, 403)
        self.assertNotIn(TITLE_MARKER, self.ops.get(f'/ops/encounters/{self.text.pk}').content.decode())


# --- release 2, R2-21: the list record names the documents of its page -------------------------------------------------

from django.conf import settings  # noqa: E402 - this section's own imports

from studio import paging  # noqa: E402

LIST = '/api/encounters'


class R2ListRecordTests(ReadCase):
    """Each page of a list served writes one member.list row naming exactly the documents it showed, in order, with its
    list and cursor (filters), its count and when it was read - before it leaves (503 when it cannot be written). A
    repeat is counted only when it showed the same documents in the same order; a later page first counts toward the
    member's limit (R2-21; D-R2-13)."""

    def setUp(self):
        super().setUp()
        for index in range(58):  # 60 documents: a first page of 50 and a later page of 10
            f.encounter(self.ws, self.reviewer, title=f'{TITLE_MARKER} synthetic page note {index:02d}')

    def start(self):
        """Now, or half a minute after the next UTC midnight when that is under two minutes away (a repeat is counted
        only on a record of its own UTC day): never earlier than now, as a session's times never are."""
        now = timezone.now()
        if (now + timedelta(minutes=2)).date() != now.date():
            return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1, seconds=30)
        return now

    def at(self, start, seconds=0):
        return mock.patch.object(timezone, 'now', return_value=start + timedelta(seconds=seconds))

    def lists(self):
        return self.rows(view=read_audit.MEMBER_LIST)

    def test_each_list_and_a_later_page_write_one_row_naming_exactly_their_documents(self):
        first = self.member.get(LIST).json()
        self.assertEqual(len(first['encounters']), 50)
        (row,) = self.lists()
        self.assertEqual((row.encounter_ids, row.count, row.filters),
                         ([item['id'] for item in first['encounters']], 50, {'list': 'documents', 'before': None}))
        for path, filters in ((f'{LIST}?list=documents', None),  # no list is documents: the same read, counted
                              (f'{LIST}?list=queue', {'list': 'queue', 'before': None}),
                              (f'{LIST}?list=recent', {'list': 'recent', 'before': None}),
                              (f'{LIST}?before={first["next"]}', {'list': 'documents', 'before': first['next']}),
                              (f'{LIST}?list=documents&before={first["next"]}', None)):
            with self.subTest(path=path):
                started, before = timezone.now(), set(Record.objects.values_list('pk', flat=True))
                answer = self.member.get(path)
                self.assertEqual(answer.status_code, 200)
                new = Record.objects.exclude(pk__in=before)
                if filters is None:  # the same page again, within the minute: counted on its row
                    self.assertFalse(new.exists())
                    continue
                (row,) = new
                page = answer.json()['encounters']
                self.assertEqual((row.view, row.outcome, row.workspace_id), (read_audit.MEMBER_LIST, read_audit.SERVED,
                                                                             self.ws.pk))
                self.assertEqual(row.encounter_ids, [item['id'] for item in page])
                self.assertEqual((row.count, row.filters), (len(page), filters))
                self.assertTrue(started <= row.as_of <= row.created_at)
        later = Record.objects.get(filters__before=first['next'])
        self.assertEqual(len(later.encounter_ids), 10)
        self.assertEqual(models.AccessRecordRepeat.objects.get(record_id=later.pk).repeats, 1)
        self.assertEqual(models.AccessRecordRepeat.objects.get(record_id=row.pk).repeats, 1)

    def test_two_pages_of_one_size_are_two_records_and_a_new_document_is_named(self):
        # the finding's reproduction (R2-21), by GETs: page A; a new document arrives first, the fiftieth leaves: page B,
        # page B again; the new document is destroyed: page A again. Release 1's rule (count and filters alike) made it
        # one record and three repeats, naming the new document nowhere.
        start = self.start()
        with self.at(start):
            page_a = [row['id'] for row in self.member.get(LIST).json()['encounters']]
        with self.at(start, 1):
            arrived = f.encounter(self.ws, self.reviewer, title=f'{TITLE_MARKER} synthetic newest note')
        with self.at(start, 2):
            page_b = [row['id'] for row in self.member.get(LIST).json()['encounters']]
        with self.at(start, 3):
            self.member.get(LIST)
        models.Encounter.objects.filter(pk=arrived.pk).update(destroyed_at=start, title='')
        with self.at(start, 5):
            self.assertEqual([row['id'] for row in self.member.get(LIST).json()['encounters']], page_a)
        self.assertEqual(page_b, [str(arrived.pk)] + page_a[:49])
        records = self.lists()
        self.assertEqual([row.encounter_ids for row in records], [page_a, page_b])
        self.assertEqual([models.AccessRecordRepeat.objects.get(record_id=row.pk).repeats for row in records], [1, 1])
        self.assertTrue(any(str(arrived.pk) in row.encounter_ids for row in records))

    def test_a_page_that_differs_only_in_order_or_in_its_cursor_is_its_own_record(self):
        start = self.start()
        with self.at(start):
            first = self.member.get(LIST).json()
        one, two = first['encounters'][0]['id'], first['encounters'][1]['id']
        times = dict(models.Encounter.objects.filter(pk__in=[one, two]).values_list('pk', 'created_at'))
        models.Encounter.objects.filter(pk=one).update(created_at=times[uuid.UUID(two)])
        models.Encounter.objects.filter(pk=two).update(created_at=times[uuid.UUID(one)])
        with self.at(start, 1):
            again = self.member.get(LIST).json()
        shown = [row['id'] for row in again['encounters']]
        self.assertEqual((set(shown), shown[:2]), ({row['id'] for row in first['encounters']}, [two, one]))
        # the same later rows by two cursors: the last row's own, and one naming its time with the lowest id
        moment, _key = paging.parse(again['next'])
        other = paging.cursor_of(moment, uuid.UUID(int=0))
        with self.at(start, 2):
            by_row = self.member.get(f'{LIST}?before={again["next"]}').json()['encounters']
        with self.at(start, 3):
            by_time = self.member.get(f'{LIST}?before={other}').json()['encounters']
        self.assertEqual(by_row, by_time)
        records = self.lists()
        self.assertEqual(len(records), 4)
        self.assertFalse(models.AccessRecordRepeat.objects.exists())
        self.assertEqual([row.filters['before'] for row in records], [None, None, again['next'], other])

    def test_a_page_whose_row_cannot_be_written_answers_503_and_shows_nothing(self):
        first = self.member.get(LIST).json()
        Record.objects.all()._raw_delete(Record.objects.db)
        with write_fails():
            for path in (LIST, f'{LIST}?list=queue', f'{LIST}?list=recent', f'{LIST}?before={first["next"]}'):
                with self.subTest(path=path):
                    answer = self.member.get(path)
                    self.assertEqual((answer.status_code, answer.json()), (503, {'error': read_audit.NOT_RECORDED,
                                                                                 'details': {}}))
                    self.assertNotIn(TITLE_MARKER.encode(), answer.content)
        self.assertFalse(Record.objects.exists())
        self.assertEqual(self.member.get(f'{LIST}?before={first["next"]}').status_code, 200)  # the control

    def test_later_pages_over_the_members_limit_are_refused_unread_and_unrecorded(self):
        start = self.start()  # every read at one moment: one UTC day, and one window of the limit
        with self.settings(LIST_PAGES_LIMIT_PER_MEMBER=(3, 60)), self.at(start):
            first = self.member.get(LIST).json()
            later = f'{LIST}?before={first["next"]}'
            served = [self.member.get(later).status_code for _ in range(3)]
            before = Record.objects.count()
            refused = [self.member.get(later) for _ in range(2)]
            first_pages = [self.member.get(path).status_code for path in (LIST, f'{LIST}?list=recent')]
        self.assertEqual(served, [200, 200, 200])
        for answer in refused:
            self.assertEqual((answer.status_code, answer.json()['error']), (429, 'rate_limited'))
            self.assertEqual(answer['Retry-After'], str(answer.json()['retry_after']))
            self.assertNotIn(TITLE_MARKER.encode(), answer.content)
        # no row for a refused page; after them, the first page repeats the first read (counted on its row) and the
        # Overview's recent five are a row of their own
        self.assertEqual(Record.objects.count(), before + 1)
        self.assertEqual(Record.objects.filter(filters={'list': 'recent', 'before': None}).count(), 1)
        events = models.SecurityEvent.objects.filter(event='list.rate_limited')
        self.assertEqual(events.count(), 1)  # the window's first refusal only
        self.assertEqual((events.get().data['scope'], events.get().data['limit'], events.get().workspace_id),
                         ('list.member', 3, self.ws.pk))
        self.assertEqual(first_pages, [200, 200])  # a first page and the Overview pay no count
        self.assertEqual(settings.LIST_PAGES_LIMIT_PER_MEMBER, (120, 60))

    def test_the_reads_page_names_the_pages_documents_by_reference_and_counts_the_rest(self):
        page = self.member.get(LIST).json()['encounters']
        auditor = ops.admin_client(f.user('r2-reads-auditor'), HTTP_X_REQUEST_ID=REQUEST_ID)
        body = auditor.get(f'/ops/activity/reads?kind={read_audit.MEMBER_LIST}').content.decode()
        for row in page[:8]:
            self.assertIn(row['id'][:8], body)
        self.assertIn('and 42 more', body)
        self.assertIn('50 shown', body)
        self.assertIn('list documents', body)
        self.assertNotIn(TITLE_MARKER, body)
