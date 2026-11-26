"""Release 2's server halves of the viewer (RELEASE-2-SPEC R2-15 and R2-17; lane S). R2-15: the in-page view of a stored
PDF carries ETag, a UUID-shaped value derived with the site's key from the sign-in, the document and the stored file's
recorded sha256 - never a hash - and a re-open that names it is answered 304, recorded first as member.inline with
{"shown_from": "page_memory"}, with no body and no stored file read; a row that cannot be written answers 503, never 304.
R2-17: the page shell carries GET /api/session's payload in <body data-session-json>. Synthetic data only."""
from __future__ import annotations

import hashlib
import html
import json
import re
import uuid
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from studio import api, customer, models, read_audit, record_bundle, request_meta, storage
from studio.storage import store_original
from tests.support import coding as f
from tests.support import rounds as r
from tests.test_frontend import PLAIN_STATIC
from tests.test_read_audit import TEXT_MARKER, TITLE_MARKER, ReadCase, member_client, write_fails

Record = models.AccessRecord
UUID_TAG = re.compile(r'"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"')
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
CONVERTED = b'%PDF-1.7\n% a synthetic conversion of a Word file\n%%EOF\n'
CONVERTED_AGAIN = b'%PDF-1.7\n% another synthetic conversion of the Word file\n%%EOF\n'


class ViewerCase(ReadCase):
    """ReadCase's practice: ``enc`` a coded PDF upload, ``text`` a text upload; ``member`` signed in at the cpt door."""

    def view_url(self, encounter):
        return f'/api/encounters/{encounter.pk}/original?view=1'

    def view(self, encounter, client=None, tag=None, **extra):
        headers = {'HTTP_IF_NONE_MATCH': tag} if tag is not None else {}
        return (client or self.member).get(self.view_url(encounter), **headers, **extra)

    def inline_rows(self, encounter=None):
        rows = self.rows(view=read_audit.MEMBER_INLINE)
        return [row for row in rows if encounter is None or row.encounter_ids == [str(encounter.pk)]]

    def stored_sha(self, encounter):
        return customer.original_file(encounter).sha256


class ViewTagTests(ViewerCase):
    def test_the_tag_is_uuid_shaped_never_the_files_hash_and_the_answer_stays_no_store(self):
        first = self.view(self.enc)
        self.assertEqual(first.status_code, 200)
        tag = first['ETag']
        self.assertRegex(tag, UUID_TAG)
        digest = self.stored_sha(self.enc)
        self.assertEqual(digest, hashlib.sha256(first.content).hexdigest())
        bare = tag.strip('"').replace('-', '')
        for piece in (digest, digest[:16], digest[:32], digest[-16:]):
            self.assertNotIn(piece, bare)
            self.assertNotIn(piece, tag)
        self.assertEqual(first['Cache-Control'], 'no-store')
        self.assertEqual(self.view(self.enc)['ETag'], tag)  # the same sign-in, document and file: the same tag
        self.assertEqual(api.view_tag(mock.Mock(session={request_meta.SESSION_SIGN_IN_REF: str(uuid.uuid4())}),
                                      self.enc, customer.view_source(self.enc)).count('-'), 4)

    def test_a_304_has_no_body_reads_no_file_and_writes_one_member_inline_row_shown_from_page_memory(self):
        tag = self.view(self.enc)['ETag']
        before = len(self.inline_rows(self.enc))
        with mock.patch.object(storage, '_read_bytes', wraps=storage._read_bytes) as reads:
            held = self.view(self.enc, tag=tag)
        self.assertEqual(held.status_code, 304)
        self.assertEqual(held.content, b'')
        self.assertNotIn('Content-Type', held)
        self.assertNotIn('Content-Disposition', held)
        self.assertEqual(held['ETag'], tag)
        self.assertEqual(held['Cache-Control'], 'no-store')
        self.assertEqual(reads.call_count, 0)
        rows = self.inline_rows(self.enc)
        self.assertEqual(len(rows), before + 1)
        self.assertEqual((rows[-1].filters, rows[-1].outcome, rows[-1].workspace_id),
                         ({'shown_from': 'page_memory'}, read_audit.SERVED, self.ws.pk))
        self.assertEqual(rows[0].filters, {})  # the 200 before it: bytes sent, recorded as release 1 recorded it
        with mock.patch.object(storage, '_read_bytes', wraps=storage._read_bytes) as reads:
            self.assertEqual(self.view(self.enc).status_code, 200)  # the control: a 200 reads the file
        self.assertEqual(reads.call_count, 1)

    def test_each_later_reopen_writes_another_row_and_the_weak_form_matches(self):
        tag = self.view(self.enc)['ETag']
        for header in (tag, f'W/{tag}', f'"other", W/{tag}', f'{tag}, "x"'):
            with self.subTest(header=header):
                self.assertEqual(self.view(self.enc, tag=header).status_code, 304)
        rows = self.inline_rows(self.enc)
        self.assertEqual(len(rows), 5)
        self.assertEqual([row.filters for row in rows[1:]], [{'shown_from': 'page_memory'}] * 4)

    def test_a_row_that_cannot_be_written_answers_503_never_304(self):
        tag = self.view(self.enc)['ETag']
        with write_fails():
            answer = self.view(self.enc, tag=tag)
        self.assertEqual(answer.status_code, 503)
        self.assertEqual(answer.json(), {'error': read_audit.NOT_RECORDED, 'details': {}})
        self.assertNotIn('ETag', answer)
        self.assertEqual(len(self.inline_rows(self.enc)), 1)
        self.assertEqual(self.view(self.enc, tag=tag).status_code, 304)  # the control

    def test_another_tag_star_another_sign_in_or_another_document_answers_200(self):
        tag = self.view(self.enc)['ETag']
        other_sign_in = member_client(self.reviewer)  # the same person, another sign-in
        pdf_two = self.done(title=f'{TITLE_MARKER} another synthetic PDF note')
        for name, answer in (
                ('another tag', self.view(self.enc, tag=f'"{uuid.uuid4()}"')),
                ('star', self.view(self.enc, tag='*')),
                ('not a tag', self.view(self.enc, tag=tag.strip('"'))),
                ('another sign-in', self.view(self.enc, client=other_sign_in, tag=tag)),
                ('another document', self.view(pdf_two, tag=tag))):
            with self.subTest(case=name):
                self.assertEqual(answer.status_code, 200)
                self.assertEqual(answer.content[:5], b'%PDF-')
        self.assertNotEqual(self.view(self.enc, client=other_sign_in)['ETag'], tag)
        self.assertNotEqual(self.view(pdf_two)['ETag'], tag)

    def test_another_practice_answers_404_with_a_refused_row(self):
        tag = self.view(self.enc)['ETag']
        outsider = member_client(self.outsider)
        refused = self.view(self.enc, client=outsider, tag=tag)
        missing = outsider.get(f'/api/encounters/{uuid.uuid4()}/original?view=1', HTTP_IF_NONE_MATCH=tag)
        self.assertEqual((refused.status_code, refused.content), (missing.status_code, missing.content))
        self.assertEqual(refused.status_code, 404)
        self.assertNotIn('ETag', refused)
        row = Record.objects.get(view=read_audit.MEMBER_INLINE, actor_id=self.outsider.pk)
        self.assertEqual((row.outcome, row.encounter_ids), (read_audit.REFUSED, [str(self.enc.pk)]))

    def test_a_destroyed_document_or_a_member_turned_off_answers_404(self):
        tag = self.view(self.enc)['ETag']
        models.Membership.objects.filter(user=self.reviewer, workspace=self.ws).update(active=False)
        self.assertEqual(self.view(self.enc, tag=tag).status_code, 404)
        models.Membership.objects.filter(user=self.reviewer, workspace=self.ws).update(active=True)
        self.assertEqual(self.view(self.enc, tag=tag).status_code, 304)  # the control
        models.Encounter.objects.filter(pk=self.enc.pk).update(destroyed_at=timezone.now())
        self.assertEqual(self.view(self.enc, tag=tag).status_code, 404)
        rows = self.inline_rows(self.enc)
        self.assertEqual([(row.outcome, row.filters) for row in rows if row.outcome == read_audit.SERVED],
                         [(read_audit.SERVED, {}), (read_audit.SERVED, {'shown_from': 'page_memory'})])
        # access off reads as another practice's document: the same 404, with a refused row (release 1's rule)
        self.assertEqual([row.outcome for row in rows if row.outcome == read_audit.REFUSED], [read_audit.REFUSED])

    def test_text_and_paste_views_carry_no_tag_and_are_always_sent(self):
        pasted = self.encounter(title=f'{TITLE_MARKER} synthetic pasted note', pdf=False)
        for encounter in (self.text, pasted):
            with self.subTest(view=encounter.title):
                first = self.view(encounter)
                self.assertEqual(first.status_code, 200)
                self.assertNotIn('ETag', first)
                self.assertEqual(self.view(encounter, tag='*').status_code, 200)
        self.assertIn(TEXT_MARKER.encode(), self.view(self.text).content)

    def test_a_poll_marked_reopen_records_moves_no_activity_and_an_idle_session_answers_401(self):
        tag = self.view(self.enc)['ETag']
        start = timezone.now()
        last_active = self.member.session[request_meta.SESSION_LAST_ACTIVE]
        for second in range(5):
            with mock.patch.object(timezone, 'now', return_value=start + timedelta(minutes=2 + second)):
                answer = self.view(self.enc, tag=tag, HTTP_X_CPT_POLL='1')
            self.assertEqual(answer.status_code, 304)
        self.assertEqual(self.member.session[request_meta.SESSION_LAST_ACTIVE], last_active)
        self.assertEqual(len(self.inline_rows(self.enc)), 6)  # the poll dedupe is the detail's alone: 5 rows
        with mock.patch.object(timezone, 'now', return_value=start + timedelta(minutes=20)):
            idle = self.view(self.enc, tag=tag, HTTP_X_CPT_POLL='1')
        self.assertEqual((idle.status_code, idle.json()['error']), (401, 'signed_out'))
        self.assertEqual(len(self.inline_rows(self.enc)), 6)

    def test_head_stays_405(self):
        tag = self.view(self.enc)['ETag']
        for headers in ({}, {'HTTP_IF_NONE_MATCH': tag}):
            answer = self.member.head(self.view_url(self.enc), **headers)
            self.assertEqual((answer.status_code, answer.content), (405, b''))
        self.assertEqual(len(self.inline_rows(self.enc)), 1)

    def test_the_bundle_still_reads_a_paste(self):
        pasted = self.encounter(title=f'{TITLE_MARKER} synthetic pasted note', pdf=False)
        self.assertEqual(customer.view_content(pasted), (f.NOTE.encode('utf-8'), customer.TEXT_SERVED,
                                                         'pasted-text.txt'))
        with mock.patch.object(customer, 'view_content', wraps=customer.view_content) as read:
            answer = self.member.get(f'/api/encounters/{pasted.pk}/bundle')
        self.assertEqual(answer.status_code, 200, answer.content[:200])
        self.assertTrue(read.called)
        self.assertTrue(record_bundle)  # the bundle's own module still reads it through view_content


class ConvertedViewTagTests(ViewerCase):
    def word(self):
        enc = f.encounter(self.ws, self.reviewer, title=f'{TITLE_MARKER} synthetic Word note')
        f.upload(enc, self.reviewer, data=b'PK\x03\x04 synthetic Word bytes', filename='synthetic-note.docx',
                 media_type=DOCX)
        return enc

    def convert(self, enc, data):
        round_ = r.write_round(enc, codes=[r.row('45385', 'ready')])
        name, digest, _size = store_original(enc.workspace_id, data, 'converted.pdf')
        models.CodingRound.objects.filter(pk=round_.pk).update(view_pdf_storage_name=name, view_pdf_sha256=digest)

    def test_a_word_documents_view_is_tagged_by_its_conversion_and_a_newer_one_is_sent(self):
        enc = self.word()
        self.assertEqual(self.view(enc).status_code, 404)  # no conversion yet: nothing to show
        self.convert(enc, CONVERTED)
        first = self.view(enc)
        self.assertEqual((first.status_code, first.content), (200, CONVERTED))
        tag = first['ETag']
        self.assertRegex(tag, UUID_TAG)
        self.assertEqual(self.view(enc, tag=tag).status_code, 304)
        self.convert(enc, CONVERTED_AGAIN)  # a newer round converted it again: its recorded hash changed
        again = self.view(enc, tag=tag)
        self.assertEqual((again.status_code, again.content), (200, CONVERTED_AGAIN))
        self.assertNotEqual(again['ETag'], tag)


@override_settings(STORAGES=PLAIN_STATIC)
class ShellSessionTests(ViewerCase):
    def test_the_shell_carries_the_session_the_api_answers(self):
        shell = self.member.get('/')
        self.assertEqual(shell.status_code, 200)
        self.assertEqual(shell['Cache-Control'], 'no-store')
        body = shell.content.decode()
        found = re.search(r'<body [^>]*data-session-json="([^"]*)"', body)
        self.assertIsNotNone(found)
        carried = json.loads(html.unescape(found.group(1)))
        self.assertEqual(carried, self.member.get('/api/session').json())
        self.assertEqual(carried['counts'], {'documents': 2, 'queue': 1})
        self.assertNotIn(TITLE_MARKER, body)  # no document is named: the payload holds none
        self.assertFalse(Record.objects.exists())  # and the shell records no read
        self.assertIn('data-entrance', body)
