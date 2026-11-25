"""The physician PDF report (owner directive 2026-11-21; studio.physician_report, studio.physician_pdf, exports.PDF).

Synthetic data only. Every PDF is made through the API as the page makes it and read back with pypdf: what a draft and an
approved report list (only saved approvals in the approved one), the true review record, nothing inferred for a field
the record does not hold, the evidence and its locators, markup in saved text printed and never followed, no provider
call and no write but the export row and its audit row, the same saved state giving the same document, a PDF that cannot
be made storing nothing, and tenancy. Set CPT_PDF_DUMP_DIR to keep each scenario's PDF for a page-by-page look (the
visual pagination check); nothing is written otherwise."""
import io
import json
import os
import socket
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from pypdf import PdfReader

from studio import exports, models, physician_pdf, state
from studio.fable import client as fable_client
from tests.support import rounds as r

Export = models.ExportArtifact
DUMP = os.environ.get('CPT_PDF_DUMP_DIR')


def text_of(data: bytes) -> list:
    """Each page's extracted text."""
    return [page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages]


def flat(pages) -> str:
    return ' '.join(' '.join(pages).split())


@override_settings(EXPORT_LIMIT_PER_MEMBER=(10_000, 600), EXPORT_LIMIT_PER_WORKSPACE=(10_000, 3600))  # C5: layout cases, not limits
class PhysicianReportCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.client = self.client_for(self.reviewer)

    # --- helpers -------------------------------------------------------------------------------------------------------

    def post(self, path, body, client=None):
        return (client or self.client).post(path, data=json.dumps(body), content_type='application/json')

    def make(self, enc, kind, *, client=None, round_number=None, name=None):
        number = round_number if round_number is not None else state.latest_round(enc).number
        return self.post(f'/api/encounters/{enc.pk}/reports', {'kind': kind, 'fmt': 'pdf', 'round': number},
                         client=client)

    def pdf(self, enc, kind, *, client=None, name=None):
        made = self.make(enc, kind, client=client)
        self.assertIn(made.status_code, (200, 201), made.content)  # release 1, C5: a current report is the stored copy
        body = made.json()
        self.assertEqual(body['fmt'], 'pdf')
        self.assertTrue(body['filename'].endswith('.pdf'))
        got = (client or self.client).get(body['download_url'])
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', got['Content-Disposition'])
        self.assertIn('no-store', got['Cache-Control'])
        data = got.content
        self.assertTrue(data.startswith(b'%PDF-'), data[:20])
        self.assertIn(b'%%EOF', data[-64:])
        if DUMP and name:
            Path(DUMP).mkdir(parents=True, exist_ok=True)
            (Path(DUMP) / f'{name}.pdf').write_bytes(data)
        return data, body

    def mixed_round(self, enc):
        return r.write_round(enc, codes=[
            r.row('45385', 'ready', units=1, modifiers=[], reason='A 9 mm polyp was removed with a cold snare.',
                  check_reason='The snare is documented.'),
            r.row('45380', 'needs_review', units=1, modifiers=['59'], reason='A separate lesion was biopsied.',
                  agrees=False, check_reason='The biopsy site is not clearly separate.'),
            r.row('45378', 'needs_answer', units=1, question='Was the cecum reached?',
                  reason='A diagnostic colonoscopy is documented.')],
            questions=[{'id': 'q1', 'text': 'Was the cecum reached?', 'codes': ['45378'], 'source': 'reader'}],
            problems=['Bowel preparation quality was not recorded.'],
            citations={'L1': [{'text': 'removed with a cold snare', 'page': 2, 'source': 'reader'}],
                       'L2': [{'text': 'a separate area was biopsied with forceps', 'page': 3, 'source': 'reader'}]})

    # --- what a draft and an approved report say ------------------------------------------------------------------------

    def test_a_draft_lists_every_line_its_decision_and_what_still_needs_one(self):
        enc = self.encounter()
        self.mixed_round(enc)
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve').status_code, 201)
        data, _ = self.pdf(enc, 'draft', name='draft-mixed')
        pages = text_of(data)
        text = flat(pages)
        for words in ('DRAFT · REVIEW REQUIRED', 'CPT coding summary', '45385', '45380', '45378',
                      'Ready for approval', 'Needs your review', 'Needs your answer', 'Decision needed', 'Answer needed',
                      'Question: Was the cecum reached?', '1 code line has no saved decision: 45380 (L2).',
                      'Bowel preparation quality was not recorded.', 'Second check: disagrees.',
                      'Synthetic data · Not for billing or claims', 'Medicare', '2 Nov 2026',
                      'removed with a cold snare', 'Page 2', 'Modifiers: 59', 'Modifiers: none'):
            self.assertIn(words, text)
        self.assertIn(f'Approved by {self.reviewer.label()}', text)
        self.assertIn(self.ws.category.name, text)  # the specialty, as saved
        self.assertRegex(text, r'\d{1,2} [A-Z][a-z]{2} \d{4}, \d\d:\d\d UTC')
        # 3 suggested, 2 open (45380 undecided, 45378 awaiting an answer); pypdf reads the values row, then the labels
        self.assertIn('03 02 Pending Suggested codes Open review items Review status', text)
        for page in pages:  # status and page numbering on every page
            self.assertIn('DRAFT · REVIEW REQUIRED', page)
            self.assertRegex(page, rf'0\d of 0{len(pages)}')

    def test_an_approved_report_lists_only_current_approvals_with_their_record(self):
        enc = self.encounter()
        self.mixed_round(enc)
        self.decide(enc, 'L1', '45385', 'approve')
        self.decide(enc, 'L2', '45380', 'reject')
        data, _ = self.pdf(enc, 'approved', name='approved-one')
        text = flat(text_of(data))
        self.assertIn('APPROVED CODES', text)
        self.assertIn('45385', text)
        self.assertNotIn('45380', text)  # rejected
        self.assertNotIn('45378', text)  # awaiting an answer
        self.assertNotIn('Was the cecum reached?', text)  # questions belong to the draft
        self.assertNotIn('Second check', text)
        self.assertIn(f'Approved by {self.reviewer.label()}', text)
        self.assertRegex(text, r'01 02 \d{1,2} [A-Z][a-z]{2} \d{4} Approved code Not approved, not listed Latest approval')
        self.assertNotIn(exports.AGENT_LINE, text)

    def test_an_undone_approval_is_not_an_approval(self):
        enc = self.encounter()
        self.mixed_round(enc)
        self.decide(enc, 'L1', '45385', 'approve')
        self.decide(enc, 'L2', '45380', 'approve')
        self.decide(enc, 'L2', '45380', 'revoke')
        text = flat(text_of(self.pdf(enc, 'approved')[0]))
        self.assertIn('45385', text)
        self.assertNotIn('45380', text)

    def test_an_agent_approval_says_it_is_not_clinical_approval(self):
        enc = self.encounter()
        self.mixed_round(enc)
        self.decide(enc, 'L1', '45385', 'approve', user=self.agent, kind='agent')
        for kind in ('approved', 'draft'):
            text = flat(text_of(self.pdf(enc, kind, name=f'agent-{kind}')[0]))
            self.assertIn(exports.AGENT_LINE, text)
            self.assertIn('Reviewbot (automated agent)', text)

    def test_with_no_approval_the_approved_pdf_is_refused_and_nothing_is_stored(self):
        enc = self.encounter()
        self.mixed_round(enc)
        before = Export.objects.count()
        refused = self.make(enc, 'approved')
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(refused.json()['details']['blockers'], ['No code has been approved.'])
        self.assertEqual(Export.objects.count(), before)
        text = flat(text_of(self.pdf(enc, 'draft', name='draft-none-approved')[0]))
        self.assertIn('No saved approval', text)
        self.assertIn('Not yet reviewed', text)

    def test_a_round_with_no_codes_says_so(self):
        enc = self.encounter()
        r.write_round(enc, codes=[])
        text = flat(text_of(self.pdf(enc, 'draft', name='draft-no-codes')[0]))
        self.assertIn('The coding review found no CPT code to report for this document.', text)
        self.assertIn('00 00 Complete Suggested codes Open review items Review status', text)

    # --- nothing inferred ------------------------------------------------------------------------------------------------

    def test_a_field_the_record_does_not_hold_is_marked_not_guessed(self):
        enc = self.encounter(pdf=False, service_date=None, insurance='unknown', title='Pasted synthetic note')
        r.write_round(enc, codes=[
            r.row('45378', 'needs_review', units=None, modifiers=None, reason='', evidence=[]),
            r.row('45385', 'ready', evidence=[{'quote': 'the polyp was snared', 'page': None}])])
        text = flat(text_of(self.pdf(enc, 'draft', name='draft-missing')[0]))
        self.assertIn('Not recorded', text)  # the date of service
        # insurance 'unknown' is stored for "Not sure" and for no answer alike: it reads as the TXT and the page say it
        self.assertIn('Not recorded Not given Synthetic coding', text)
        self.assertNotIn('Not sure', text)
        self.assertIn('Not given', text)  # units
        self.assertIn('Modifiers: not given', text)
        self.assertIn('No excerpt', text)
        self.assertIn('No excerpt from the document was saved for this code.', text)
        self.assertIn('Text document · no page numbers', text)
        self.assertNotIn('Page 1', text)
        self.assertNotIn('Patient', text)  # the record has no patient field, so the report shows none
        # an uncited line's evidence is the coding review's own quotation, and says so
        self.assertIn("The coding review's quotation, not checked against the document", text)

    def test_a_long_case_flows_over_pages_with_every_code_and_footer(self):
        enc = self.encounter()
        long_reason = ('The procedure note documents the service in detail, including the site, the instrument and '
                       'the completed technique. ') * 4
        codes = [r.row(f'4{5300 + n}', 'needs_review', units=n % 3 + 1,
                       reason=long_reason, check_reason='Checked against the whole note. ' * 3) for n in range(14)]
        citations = {f'L{n + 1}': [{'text': ('An exact passage quoted from the synthetic document that runs long '
                                             'enough to wrap over several lines of the evidence box. ') * (2 + n % 4),
                                    'page': n + 1, 'source': 'reader'}] for n in range(14)}
        r.write_round(enc, codes=codes, citations=citations)
        data, _ = self.pdf(enc, 'draft', name='draft-long')
        pages = text_of(data)
        self.assertGreater(len(pages), 2)
        text = flat(pages)
        for item in codes:
            self.assertIn(item['code'], text)
        for number, page in enumerate(pages, start=1):
            self.assertIn(f'{number:02d} of {len(pages):02d}', page)

    def test_the_excerpt_claim_is_true_of_what_is_printed(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', evidence=[]), r.row('45380', 'needs_review', evidence=[])])
        text = flat(text_of(self.pdf(enc, 'draft', name='draft-no-excerpts')[0]))
        self.assertIn('None was saved for these codes', text)
        self.assertNotIn('Exact words from the document', text)  # no excerpt is printed, so none is claimed
        self.assertNotIn('Every suggestion has a source.', text)
        other = self.encounter()
        r.write_round(other, codes=[r.row('45385', 'ready')],
                      citations={'L1': [{'text': 'removed with a cold snare', 'page': None, 'source': 'reader'}]})
        text = flat(text_of(self.pdf(other, 'draft')[0]))
        self.assertIn('Exact words from the document', text)
        self.assertNotIn('with their pages', text)  # a citation without a page is not claimed to have one
        self.assertIn('Page not given', text)

    def test_a_character_the_design_font_lacks_is_drawn_in_every_header_too(self):
        enc = self.encounter(title='Synthetic note ∆ ✓ Ж')
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        pages = text_of(self.pdf(enc, 'draft', name='draft-fallback-title')[0])
        for page in pages:
            self.assertIn('Synthetic note ∆ ✓ Ж', ' '.join(page.split()))
            self.assertNotIn('\x00', page)

    def test_a_usual_specialty_is_never_broken_mid_word(self):
        models.Category.objects.filter(pk=self.ws.category_id).update(name='Gastroenterology')
        enc = self.encounter(insurance='commercial')
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        text = flat(text_of(self.pdf(enc, 'draft', name='draft-specialty')[0]))
        self.assertIn('Gastroenterology', text)
        self.assertIn('Commercial or other', text)

    # --- safety ----------------------------------------------------------------------------------------------------------

    def test_markup_in_saved_text_is_printed_and_never_followed(self):
        enc = self.encounter(title='<b>Bold</b> & "quoted" <img src="http://169.254.169.254/latest">')
        r.write_round(enc, codes=[r.row('45385', 'ready',
                                        reason='<img src="http://169.254.169.254/x.png"/> <a href="http://e.invalid">x</a>',
                                        check_reason='<font name="Courier">changed</font>')],
                      citations={'L1': [{'text': 'snare <br/> & <para>removed</para> ∆ Ω µ → ≥', 'page': 2,
                                         'source': 'reader'}]})
        with mock.patch.object(socket, 'create_connection', side_effect=AssertionError('network used')), \
                mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('network used')):
            data, _ = self.pdf(enc, 'draft', name='draft-markup')
        text = flat(text_of(data))
        self.assertIn('<img src="http://169.254.169.254/x.png"/>', text)
        self.assertIn('<a href="http://e.invalid">x</a>', text)
        self.assertIn('<font name="Courier">changed</font>', text)
        self.assertIn('snare <br/> & <para>removed</para> ∆ Ω µ → ≥', text)
        self.assertIn('<b>Bold</b> & "quoted"', text)

    def test_making_a_pdf_calls_no_provider_and_writes_only_the_export_and_its_audit_row(self):
        enc = self.encounter()
        self.mixed_round(enc)
        self.decide(enc, 'L1', '45385', 'approve')
        enc.refresh_from_db()
        counts = {model: model.objects.count() for model in
                  (models.CodeDecision, models.CodingRound, models.CodingAnswer, models.Encounter, models.AuditEvent,
                   Export)}
        state_before, updated_before = enc.state, enc.updated_at
        with mock.patch.object(fable_client, 'coder', side_effect=AssertionError('a provider was called')):
            self.pdf(enc, 'approved')
        enc.refresh_from_db()
        for model, before in counts.items():
            expected = before + 1 if model in (models.AuditEvent, Export) else before
            self.assertEqual(model.objects.count(), expected, model.__name__)
        self.assertEqual((enc.state, enc.updated_at), (state_before, updated_before))
        export = Export.objects.latest('created_at')
        self.assertEqual((export.fmt, export.kind), ('pdf', 'approved'))
        event = models.AuditEvent.objects.filter(event='export.created').latest('created_at')
        self.assertEqual((event.data['fmt'], event.data['kind'], event.data['export']), ('pdf', 'approved',
                                                                                         str(export.pk)))

    def test_no_vendor_or_model_name_reaches_the_pdf(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready', reason='Claude Fable 5.2 and Gemini read the snare.',
                                        check_reason='Anthropic agrees.')],
                      problems=['GPT-5 could not tell the site.'])
        data, _ = self.pdf(enc, 'draft')
        text = flat(text_of(data)).lower()
        for name in ('claude', 'fable', 'gemini', 'anthropic', 'gpt', 'openai', 'reportlab'):
            self.assertNotIn(name, text)
        metadata = PdfReader(io.BytesIO(data)).metadata
        for value in (metadata or {}).values():
            for name in ('claude', 'fable', 'gemini', 'anthropic', 'reportlab'):
                self.assertNotIn(name, str(value).lower())

    def test_the_same_saved_state_gives_the_same_document(self):
        enc = self.encounter()
        self.mixed_round(enc)
        round_ = state.latest_round(enc)
        current = state.current_decisions(round_)

        def render(moment):
            # release 1, C5: asked again through the API, a current report is the stored copy, so the same saved state
            # is rendered here as exports.create renders it
            return exports.render_pdf(exports.snapshot(enc, round_, current, 'draft', self.reviewer, moment), enc, round_)
        moment = datetime(2026, 11, 21, 14, 2, 9, tzinfo=dt_timezone.utc)
        first, second = render(moment), render(moment)
        self.assertEqual(first, second)
        third = render(datetime(2026, 11, 22, 9, 30, 0, tzinfo=dt_timezone.utc))
        a, b = flat(text_of(first)), flat(text_of(third))
        self.assertNotEqual(a, b)  # the Prepared line names when it was made
        self.assertEqual(a.replace('21 Nov 2026, 14:02 UTC', 'T'), b.replace('22 Nov 2026, 09:30 UTC', 'T'))
        made, again = self.make(enc, 'draft'), self.make(enc, 'draft')
        self.assertEqual((made.status_code, again.status_code, again.json()['id']), (201, 200, made.json()['id']))

    def test_a_pdf_that_cannot_be_made_stores_nothing_and_says_so(self):
        enc = self.encounter()
        self.mixed_round(enc)
        before = (Export.objects.count(), models.AuditEvent.objects.filter(event='export.created').count())
        with mock.patch.object(physician_pdf, 'render_report', side_effect=RuntimeError('boom')):
            refused = self.make(enc, 'draft')
        self.assertEqual(refused.status_code, 503)
        self.assertEqual(refused.json()['error'], exports.PDF_NOT_MADE)
        self.assertNotIn('boom', refused.content.decode())
        with mock.patch.object(physician_pdf, 'render_report', return_value=b''):
            self.assertEqual(self.make(enc, 'draft').status_code, 503)
        self.assertEqual((Export.objects.count(), models.AuditEvent.objects.filter(event='export.created').count()),
                         before)

    # --- tenancy and staleness -------------------------------------------------------------------------------------------

    def test_another_workspace_a_signed_out_caller_and_a_stale_round_are_refused(self):
        enc = self.encounter()
        self.mixed_round(enc)
        _, body = self.pdf(enc, 'draft')
        outsider = self.client_for(self.outsider)
        self.assertEqual(self.make(enc, 'draft', client=outsider).status_code, 404)
        self.assertEqual(outsider.get(body['download_url']).status_code, 404)
        from django.test import Client
        anonymous = Client()
        self.assertEqual(anonymous.get(body['download_url']).status_code, 401)
        self.assertEqual(self.make(enc, 'draft', client=anonymous).status_code, 401)
        self.assertEqual(self.make(enc, 'draft', round_number=state.latest_round(enc).number + 1).status_code, 409)
        viewer = self.client_for(self.viewer)  # any member may make an export (exports.create)
        self.assertIn(self.make(enc, 'draft', client=viewer).status_code, (200, 201))  # C5: perhaps the stored copy

    def test_an_earlier_pdf_stays_listed_and_served_as_stored(self):
        enc = self.encounter()
        self.mixed_round(enc)
        data, body = self.pdf(enc, 'draft')
        self.decide(enc, 'L1', '45385', 'approve')
        listed = self.client.get(f'/api/encounters/{enc.pk}').json()['reports']
        mine = next(item for item in listed if item['id'] == body['id'])
        self.assertFalse(mine['current'])
        self.assertEqual(self.client.get(body['download_url']).content, data)
