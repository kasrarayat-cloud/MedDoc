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
            ('/api/encounters', read_audit.MEMBER_LIST, [], None),
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
        before = timezone.now()
        shown = self.member.get('/api/encounters').json()['encounters']
        row = Record.objects.get(view=read_audit.MEMBER_LIST)
        self.assertEqual((row.count, row.workspace_id, row.encounter_ids), (len(shown), self.ws.pk, []))
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
        start = timezone.now()
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
