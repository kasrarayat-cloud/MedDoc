"""Unit tests for ops/scan_customer.py: the shared denylist and contract readers, and a loopback stand-in for the customer
surface the scanner signs in to and reads.

The stand-in serves synthetic payloads of the Fable coding build's customer contract (ops/verification/
customer-contract.json; built here - the session, the list, an encounter with its quotes, its original and view, its
exports, the page and its one script), answers 404 on every /ops/ URL and on every removed one, and signs the session in
and out as studio/views.py does (verify_login.py's tests hold that contract). Each leak the scanner must catch is a
switch on it. Nothing leaves the loopback.

The PDF export (the physician report, 2026-11-21) is read as its text, never its bytes: the stand-in's PDF and the
reader's own cases are small synthetic PDFs drawn here with ReportLab's canvas (invariant, Helvetica), which the
service installs (requirements.txt); the scanner reads them with pypdf (requirements-dev.txt).

    cd cpt-studio && python3 -B -m unittest discover -s ops -p 'test_verify_scan_customer.py' -v
"""
import functools
import importlib.util
import io
import json
import os
import re
import secrets
import sys
import tempfile
import threading
import unittest
import unittest.mock
from contextlib import redirect_stderr, redirect_stdout
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
import urllib.parse  # noqa: E402 - release 2: the cursor as the scan writes it

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_scan_customer', HERE / 'scan_customer.py')
sc = importlib.util.module_from_spec(_spec)
sys.modules['cpt_scan_customer'] = sc
_spec.loader.exec_module(sc)

USERNAME, PASSWORD = 'review-agent', 'Synthetic-scan pass&+%<>"é-2026'
ENCOUNTER_ID = 'f6000000-0000-4000-8000-0000000000a1'
SECOND_ID = 'f6000000-0000-4000-8000-0000000000a2'  # release 2: the second page's document (R2-24's --all)
NEXT_PAGE = f'20261120T071000.000000Z~{ENCOUNTER_ID}'  # the first page's next cursor
VIEW_TAG = '"0b7f3a52-9c1e-4d2a-8f61-2a9e5d0c4b17"'  # an ETag as release 2's view carries it (R2-15)
DRAFT_ID, APPROVED_ID = 'f6000000-0000-4000-8000-0000000000d1', 'f6000000-0000-4000-8000-0000000000d2'
PDF_ID = 'f6000000-0000-4000-8000-0000000000d3'
QUOTE = 'Cold forceps biopsies were taken from the gastric antrum.'
# DECISION IDS (FIX-SPEC-2 section 5): a current decision carries its id once the contract lists it (lane G1)
DECISION_IDS = 'id' in sc.CONTRACT['types']['decision']['keys']
DECISION_ID = 'f6000000-0000-4000-8000-0000000000e1'


def session_json() -> dict:
    return {'user': {'id': 'fa000000-0000-4000-8000-000000000001', 'label': 'Review agent', 'initials': 'RA',
                     'actor_kind': 'agent'},
            'workspace': {'id': 'fa000000-0000-4000-8000-000000000002', 'name': 'Gastroenterology',
                          'specialty': 'Gastroenterology'},
            'role': 'reviewer', 'can_review': True, 'can_manage_team': False,
            'acknowledgement': 'I read the whole source document. This synthetic review is not clinical approval.',
            'counts': {'documents': 1, 'queue': 0}}


def encounter_json() -> dict:
    """A synthetic encounter as the customer API serves it: one code approved, its quote cited from the document."""
    base = f'/api/encounters/{ENCOUNTER_ID}/original'
    return {
        'id': ENCOUNTER_ID, 'title': 'Synthetic EGD with biopsy', 'created_at': '2026-11-20T07:10:00Z',
        'updated_at': '2026-11-20T07:55:00Z', 'state': 'reviewed', 'state_label': 'Reviewed',
        'permissions': {'can_review': True},
        'document': {'name': 'synthetic-egd.pdf', 'media_type': 'application/pdf', 'size': 1673, 'kind': 'upload',
                     'original_url': base, 'view_url': f'{base}?view=1', 'view_media_type': 'application/pdf',
                     'converted': False},
        'context': {'service_date': '2026-11-02', 'insurance': 'medicare'},
        'progress': {'phase': 'done', 'busy': False, 'started_at': '2026-11-20T07:31:05Z',
                     'finished_at': '2026-11-20T07:38:40Z', 'server_time': '2026-11-20T08:10:00Z', 'message': '',
                     'can_stop': False, 'can_resume': False, 'can_retry': False, 'error': None},
        'round': {'number': 1, 'trigger': 'upload', 'finished_at': '2026-11-20T07:38:40Z'},
        'codes': [{'line': 'L1', 'code': '43239', 'units': 1, 'modifiers': [], 'status': 'ready',
                   'status_label': 'Ready for approval',
                   'reason': 'Biopsies were taken during the upper endoscopy (page 1).',
                   'second_check': {'agrees': True, 'reason': 'The biopsy is documented on page 1.'},
                   'question': None, 'quotes': [{'text': QUOTE, 'page': 1}],
                   'decision': {**({'id': DECISION_ID} if DECISION_IDS else {}), 'action': 'approve', 'by': 'Review agent',
                                'at': '2026-11-20T07:52:10Z', 'note': ''},
                   'allowed_actions': ['revoke']}],
        'questions': [], 'answers': [], 'notes': [],
        'readiness': {'draft': True, 'approved': True, 'blockers': []},
        'reports': [{'id': DRAFT_ID, 'kind': 'draft', 'fmt': 'txt', 'filename': 'synthetic-egd-draft.txt',
                     'generated_at': '2026-11-20T07:53:00Z', 'download_url': f'/api/reports/{DRAFT_ID}/download',
                     'current': True},
                    {'id': APPROVED_ID, 'kind': 'approved', 'fmt': 'csv', 'filename': 'synthetic-egd-approved.csv',
                     'generated_at': '2026-11-20T07:54:00Z', 'download_url': f'/api/reports/{APPROVED_ID}/download',
                     'current': True},
                    {'id': PDF_ID, 'kind': 'approved', 'fmt': 'pdf', 'filename': 'synthetic-egd-approved.pdf',
                     'generated_at': '2026-11-20T07:54:30Z', 'download_url': f'/api/reports/{PDF_ID}/download',
                     'current': True}],
        'activity': [{'at': '2026-11-20T07:52:10Z', 'text': 'Review agent approved L1 43239.'}]}


def pdf_bytes(*pages, **info) -> bytes:
    """A small synthetic PDF drawn with ReportLab's canvas (invariant, so the same bytes every time; Helvetica): each of
    ``pages`` a list of the lines drawn on it; ``info`` its document information (title, author, subject, creator,
    producer, keywords: the canvas's setters)."""
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    drawing = canvas.Canvas(buffer, invariant=1)
    for key, value in info.items():
        getattr(drawing, f'set{key.capitalize()}')(value)
    for lines in pages:
        drawing.setFont('Helvetica', 11)
        for number, line in enumerate(lines):
            drawing.drawString(72, 720 - 16 * number, line)
        drawing.showPage()
    drawing.save()
    return buffer.getvalue()


# The approved PDF in miniature, as the physician report draws it: its running header, the code row, the evidence page
# with the quotation wrapped over two lines, the footer. Its metadata is the report's own.
PDF_PAGES = (
    ['QuillMD', 'CPT STUDIO', 'APPROVED CODES', 'Synthetic EGD with biopsy · F6000000 · Coding review 1',
     'Approved CPT codes', '01   43239   Approved by Review agent   UNITS 1   Approved', '20 Nov 2026, 07:52 UTC',
     'Line L1 · Modifiers: none', 'Synthetic data · Not for billing or claims'],
    ['THE REASONS, IN THE RECORD', 'Every approved code has a source.', '01   43239  /  Approved by Review agent',
     '“Cold forceps biopsies were taken', 'from the gastric antrum.”', 'Page 1',
     'Reason: Biopsies were taken during the upper endoscopy (page 1).', 'Report format',
     'PDF · cpt-studio-customer-export@3', 'Synthetic data · Not for billing or claims'])
PDF_INFO = {'title': 'CPT Studio approved codes F6000000 r1', 'author': 'QuillMD CPT Studio',
            'subject': 'CPT coding summary', 'creator': 'QuillMD CPT Studio', 'producer': 'QuillMD CPT Studio',
            'keywords': ''}


REPORT_FONT = HERE.parent / 'studio' / 'report_fonts' / 'DejaVuSans.ttf'  # the report's own fallback font


def ttf_pdf_bytes(*pages) -> bytes:
    """As pdf_bytes, drawn in the report's bundled TrueType font (DejaVu Sans, embedded as a subset with its own
    ToUnicode map), so a character Helvetica's encoding cannot carry - an invisible format character - reaches the text
    layer as itself, as it would from the report's renderer."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    if 'ScanTestSans' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ScanTestSans', str(REPORT_FONT)))
    buffer = io.BytesIO()
    drawing = canvas.Canvas(buffer, invariant=1)
    for lines in pages:
        drawing.setFont('ScanTestSans', 11)
        for number, line in enumerate(lines):
            drawing.drawString(72, 720 - 16 * number, line)
        drawing.showPage()
    drawing.save()
    return buffer.getvalue()


def report_pages(*bodies, identity='Synthetic EGD with biopsy · F6000000 · Coding review 1') -> list:
    """Pages as the physician report draws them (studio/physician_pdf.py): its running header and footer first on every
    page - the brand, the status line, the identity line, the footer note, the reference with "<page> of <pages>" -
    then the page's own lines ``bodies[n]``."""
    total = len(bodies)
    return [['QuillMD', 'CPT STUDIO', 'DRAFT · REVIEW REQUIRED', identity, 'Synthetic data · Not for billing or claims',
             f'CPT-F6000000 · r1   /   {number:02d} of {total:02d}', *body]
            for number, body in enumerate(bodies, start=1)]


@functools.lru_cache(maxsize=None)
def approved_pdf(leak: str = '') -> bytes:
    """The stand-in's approved PDF; ``leak`` 'text' adds a model name and its usage to its evidence page, 'metadata'
    names a vendor as its author."""
    pages = [list(page) for page in PDF_PAGES]
    if leak == 'text':
        pages[1].insert(6, 'Read by claude-fable-5-2 (12,000 tokens).')
    info = {**PDF_INFO, 'author': 'Anthropic'} if leak == 'metadata' else PDF_INFO
    return pdf_bytes(*pages, **info)


EXPORTS = {
    DRAFT_ID: ('SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\nCPT STUDIO — CODES — DRAFT, NOT APPROVED\n'
               'Encounter: Synthetic EGD with biopsy\n\n43239 x1 - Ready for approval\n'
               '  Biopsies were taken during the upper endoscopy (page 1).\n'
               f'  Quote (page 1): "{QUOTE}"\nLimitations\n  The coding review can be wrong.\n'
               'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\n'),
    APPROVED_ID: ('"kind","code","units","modifiers","status","reason","quotes","decision","decided_by","decided_at"\r\n'
                  '"banner","SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS","","","","","","","",""\r\n'
                  f'"code","43239","1","","ready","Biopsies were taken (page 1).","{QUOTE} (page 1)","approved",'
                  '"Review agent","2026-11-20T07:52:10Z"\r\n'),
}
CONTENT_TYPES = {'txt': 'text/plain; charset=utf-8', 'csv': 'text/csv; charset=utf-8'}  # as studio.exports serves them


class SharedReaderTests(unittest.TestCase):
    def test_the_denylist_vectors_hold_in_this_reader_as_in_the_walk_s(self):
        ctx = sc.scan_context()
        self.assertGreaterEqual(len(sc.DENYLIST['vectors']), 20)
        for vector in sc.DENYLIST['vectors']:
            with self.subTest(text=vector['text']):
                self.assertEqual(sorted({hit['id'] for hit in sc.scan_text(vector['text'], ctx, vector['surface'])}), vector['hits'])

    def test_the_readers_are_ascii_only_as_javascript_reads_them(self):
        # Python's re.I alone folds the long s and the Kelvin sign onto s and k; JavaScript 'gi' does not
        ctx = sc.scan_context()
        self.assertEqual(sc.scan_text('\u017fha256', ctx, 'dom'), [])  # 'ſ' is no 's'
        self.assertEqual(sorted({h['id'] for h in sc.scan_text('sha256', ctx, 'dom')}), ['sha256'])  # the control
        self.assertEqual(sc.scan_text('to\u212aens', ctx, 'dom'), [])  # the Kelvin sign is no 'k'
        self.assertTrue(sc.scan_text('tokens', ctx, 'dom'))  # the control

    def test_the_payloads_hold_to_the_contract_and_each_difference_is_named(self):
        self.assertEqual(sc.shape_problems(encounter_json(), sc.CONTRACT['encounter']), [])
        self.assertEqual(sc.shape_problems(session_json(), sc.CONTRACT['session']), [])
        enc = encounter_json()
        enc['codes'][0]['vendor'] = 'Anthropic'
        enc['codes'][0]['units'] = True
        del enc['readiness']['blockers']
        enc['state'] = 'needs_clarification'
        problems = sc.shape_problems(enc, sc.CONTRACT['encounter'])
        for want in ('$.codes[0].vendor: not in the customer contract', '$.codes[0].units: boolean where the contract has integer',
                     '$.readiness.blockers: missing (the contract lists it)', '$.state: "needs_clarification" is not one of'):
            self.assertTrue(any(problem.startswith(want) for problem in problems), (want, problems))
        session = session_json()
        session['provider_mode'] = 'live'
        session['user']['username'] = 'review-agent'
        self.assertEqual(sorted(sc.shape_problems(session, sc.CONTRACT['session'])),
                         ['$.provider_mode: not in the customer contract', '$.user.username: not in the customer contract'])

    def test_deny_values_are_identifier_shaped_and_read_by_the_denylists_paths(self):
        self.assertEqual(sc.harvest({'a': [{'b': ['x1']}, {'b': ['y2']}]}, 'a[].b[]'), ['x1', 'y2'])
        self.assertEqual(sc.harvest({'f': [['n', 'h1'], ['m', 'h2']]}, 'f[].1'), ['h1', 'h2'])
        paths = {'encounter': ['runs[].id', 'runs[].model'], 'trace': ['calls[].request_id']}
        view = {'runs': [{'id': 'c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d', 'model': 'claude-fable-5-2'},
                         {'id': 'short', 'model': 'Corti'}]}
        with unittest.mock.patch.dict(sc.DENYLIST, {'deny_value_paths': paths}):
            values = sc.deny_values_from(view, {'calls': [{'request_id': 'req_fable0123456789'}]})
        self.assertEqual(values, ['c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d', 'claude-fable-5-2', 'req_fable0123456789'])
        self.assertEqual(sc.deny_values_from(view), [])  # the build's own denylist names no path: nothing is harvested

    def test_files_are_scanned_cell_by_cell_and_line_by_line_with_the_document_s_own_quotations_set_aside(self):
        ctx = sc.scan_context(sc.quotations(encounter_json()))
        self.assertEqual(ctx.document_text, QUOTE)
        for report in encounter_json()['reports']:
            if report['fmt'] != 'pdf':  # the PDF is read as its text (PdfReaderTests)
                self.assertEqual(sc.scan_file(EXPORTS[report['id']], ctx, report['filename'], report['fmt']), [],
                                 report['id'])
        csv_text = EXPORTS[APPROVED_ID]
        self.assertEqual(csv_text.count(',"approved",'), 1)
        leaked = csv_text.replace(',"approved",', ',"approved (claude-fable-5-2)",', 1)
        self.assertLessEqual({'model_id', 'provider_name'}, {h['id'] for h in sc.scan_file(leaked, ctx, 'x.csv', 'csv')})
        # a quotation of the document is set aside only while it is one: the same words outside quotes are scanned
        self.assertEqual(sc.scan_file(f'"{QUOTE}"', ctx, 'q.txt', 'txt'), [])
        # SEC-S4: a modifier is part of the code line, never a quotation - scanned whole even where a quote holds it
        named = encounter_json()
        named['codes'][0]['quotes'] = [{'text': 'Dr. Claude Example removed the polyp.', 'page': 1}]
        named['codes'][0]['modifiers'] = ['Claude']
        quoted = sc.scan_context(sc.quotations(named))
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_json(named, quoted)],
                         [('provider_name', '$.codes[0].modifiers[0]')])
        named['codes'][0]['modifiers'] = ['PT']
        self.assertEqual(sc.scan_json(named, quoted), [])  # the quote itself stays the document's
        self.assertTrue(sc.NEVER_QUOTED.search('$.codes[3].modifiers[12]'))
        self.assertIsNone(sc.NEVER_QUOTED.search('$.codes[0].quotes[0].text'))
        self.assertEqual(sc.csv_rows('a,"b ""c"", d"\r\n1,2\n'), [['a', 'b "c", d'], ['1', '2']])
        self.assertEqual(sc.scan_headers([('Content-Security-Policy', "script-src 'sha256-x'")], ctx, 'GET /'), [])
        self.assertEqual(sorted({h['id'] for h in sc.scan_headers([('X-Content-SHA256', 'ab' * 32)], ctx, 'GET /x')}), ['long_hex', 'sha256'])


class PdfReaderTests(unittest.TestCase):
    """A PDF export is read as the text pypdf extracts from each page, line by line under the TXT rules, and as its
    document information values - never as its bytes; a PDF that cannot be read is a scan problem, never a pass."""

    def test_a_clean_pdf_is_read_page_by_page_with_its_metadata_and_passes(self):
        data = approved_pdf()
        self.assertTrue(sc.is_pdf(data))
        reading = sc.read_pdf(data)
        self.assertEqual(len(reading.pages), 2)
        self.assertIn('Approved by Review agent', reading.pages[0])
        self.assertIn('“Cold forceps biopsies were taken\nfrom the gastric antrum.”', reading.pages[1])
        self.assertLessEqual({'Title', 'Author', 'Subject', 'Creator', 'Producer', 'Keywords'}, set(reading.metadata))
        self.assertEqual(reading.metadata['Title'], PDF_INFO['title'])
        ctx = sc.scan_context(sc.quotations(encounter_json()))
        self.assertEqual(sc.scan_pdf(reading, ctx, 'approved.pdf'), [])

    def test_a_quotation_is_set_aside_only_while_it_is_the_documents_own_words(self):
        document = ('Dr. Claude Example removed the polyp with a cold snare.\n'
                    'The specimen was sent by Dr. Claude Example.')
        # two quotations wrapped over two lines (the name on the first line of one, the last line of the other), the
        # reason that names the same doctor, and a quotation on one line
        reading = sc.read_pdf(pdf_bytes(['“Dr. Claude Example removed', 'the polyp with a cold snare.”',
                                         '“The specimen was sent', 'by Dr. Claude Example.”', 'Page 2',
                                         'Reason: the note names Dr. Claude Example.',
                                         'Also quoted: “Dr. Claude Example removed” (page 2)']))
        hits = sc.scan_pdf(reading, sc.scan_context(document), 'q.pdf')
        self.assertEqual([(hit['id'], hit['where']) for hit in hits], [('provider_name', 'q.pdf page 1 line 6')])
        # with no document text nothing is a quotation: the quoted name is scanned too
        bare = sc.scan_pdf(reading, sc.scan_context(), 'q.pdf')
        self.assertEqual([(hit['id'], hit['where']) for hit in bare],
                         [('provider_name', f'q.pdf page 1 line {line}') for line in (1, 4, 6, 7)])
        # white space is compared squeezed: the PDF prints a stored line break or run of spaces as one space
        spaced = sc.scan_context('Dr. Claude\nExample   removed  the polyp')
        self.assertEqual(sc.scan_pdf(sc.read_pdf(pdf_bytes(['“Dr. Claude Example removed the polyp”'])), spaced, 'q.pdf'), [])

    def test_a_denylisted_word_in_the_text_or_the_metadata_is_found(self):
        ctx = sc.scan_context(sc.quotations(encounter_json()))
        text = sc.scan_pdf(sc.read_pdf(approved_pdf('text')), ctx, 'approved.pdf')
        self.assertEqual(sorted({(hit['id'], hit['where']) for hit in text}),
                         [(rule, 'approved.pdf page 2 line 7') for rule in ('interpreter_model', 'model_id',
                                                                             'provider_name', 'token')])
        metadata = sc.scan_pdf(sc.read_pdf(approved_pdf('metadata')), ctx, 'approved.pdf')
        self.assertEqual([(hit['id'], hit['where']) for hit in metadata], [('provider_name', 'approved.pdf metadata Author')])
        # metadata is never a quotation of the document, even when the document holds the same word
        named = sc.scan_pdf(sc.read_pdf(pdf_bytes(['Approved CPT codes'], author='Claude')), sc.scan_context('Dr. Claude'),
                            'n.pdf')
        self.assertEqual([(hit['id'], hit['where']) for hit in named], [('provider_name', 'n.pdf metadata Author')])

    def test_a_phrase_the_layout_broke_over_two_lines_is_found_once(self):
        reading = sc.read_pdf(pdf_bytes(['Reason: its own tool', 'calls retrieved 4 passages.', 'Read by Claude',
                                         'Fable checked it.']))
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(reading, sc.scan_context(), 'x.pdf')],
                         [('tool_call', 'x.pdf page 1 lines 1-2'), ('provider_name', 'x.pdf page 1 line 3'),
                          ('provider_name', 'x.pdf page 1 line 4')])
        one_line = sc.read_pdf(pdf_bytes(['Reason: its own tool calls retrieved 4 passages.']))
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(one_line, sc.scan_context(), 'x.pdf')],
                         [('tool_call', 'x.pdf page 1 line 1')])
        # L6-3: a quotation set aside does not cut the product's wording apart - the lines on either side of it are
        # neighbours, as on one line the words around a quotation are
        apart = sc.read_pdf(pdf_bytes(['Reason: its own tool', '“the polyp was', 'removed”', 'calls retrieved 4 passages.']))
        self.assertEqual([(hit['id'], hit['where']) for hit in
                          sc.scan_pdf(apart, sc.scan_context('the polyp was removed'), 'x.pdf')],
                         [('tool_call', 'x.pdf page 1 lines 1-4')])
        inline = sc.read_pdf(pdf_bytes(['Reason: its own tool “the polyp was removed” calls retrieved 4 passages.']))
        self.assertEqual([(hit['id'], hit['where']) for hit in
                          sc.scan_pdf(inline, sc.scan_context('the polyp was removed'), 'x.pdf')],
                         [('tool_call', 'x.pdf page 1 line 1')])

    def test_only_the_text_inside_a_printed_quotation_is_set_aside(self):
        """L3-2: a code line's modifier "Claude", wrapped onto a line of its own, is the product's wording even though a
        quotation of the document holds the same word - it is scanned; the quotation itself, wrapped over two lines,
        is not."""
        document = 'Dr. Claude Example removed the polyp with a cold snare'
        lines = ['01   45385   Ready for approval   UNITS 1   Decision needed',
                 'Line L1 · Modifiers: 59, XS, XU, PT, KX, GA, RT,', 'Claude', 'Evidence 01',
                 'THE REASONS, IN THE RECORD', '01   45385  /  Ready for approval',
                 '“Dr. Claude Example removed the polyp with a', 'cold snare”', 'Page 2',
                 'Reason: A polyp was removed by cold snare.']
        reading = sc.read_pdf(pdf_bytes(lines))
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(reading, sc.scan_context(document), 'x.pdf')],
                         [('provider_name', 'x.pdf page 1 line 3')])
        # the control: the modifier dropped, nothing is found - the quotation's "Dr. Claude Example" stays set aside
        clean = sc.read_pdf(pdf_bytes([line for line in lines if line != 'Claude']))
        self.assertEqual(sc.scan_pdf(clean, sc.scan_context(document), 'x.pdf'), [])
        # the same-page case of L6-3: a reason's last word wrapped onto a line whose words a quotation also holds
        # ("calls." beside the quotation "The nurse calls.") is the reason's, read joined to the line before it
        nurse = sc.read_pdf(pdf_bytes(['“The nurse calls.”', 'Page 2', 'Reason: synthetic synthetic synthetic tool',
                                       'calls.']))
        self.assertEqual([(hit['id'], hit['where']) for hit in
                          sc.scan_pdf(nurse, sc.scan_context('The nurse calls.'), 'x.pdf')],
                         [('tool_call', 'x.pdf page 1 lines 3-4')])
        # an opening mark that starts no quotation of the document is the product's: the words after it are scanned,
        # and a later quotation is still set aside
        stray = sc.read_pdf(pdf_bytes(['Reason: the note says “read by Claude', '“Dr. Claude Example removed the polyp',
                                       'with a cold snare”', 'Page 2']))
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(stray, sc.scan_context(document), 'x.pdf')],
                         [('provider_name', 'x.pdf page 1 line 1')])
        # a quotation whose own words hold a closing mark is followed to its end, not cut at that mark
        quoted = sc.read_pdf(pdf_bytes(['“He said “fine” and Dr. Claude', 'Example removed the polyp”', 'Page 2']))
        self.assertEqual(sc.scan_pdf(quoted, sc.scan_context('He said “fine” and Dr. Claude Example removed the polyp'),
                                     'x.pdf'), [])

    def test_a_phrase_cut_by_a_page_break_is_read_as_one_over_the_running_header_and_footer(self):
        """L6-3: the running header and footer every page repeats are read as lines of their own; the body is one
        stream over the pages, so the last line of product wording on a page is joined to the first of the next, and a
        quotation continued over a page break is set aside whole."""
        filler = ' '.join(f'w{n:03d}' for n in range(498, 518))
        pages = report_pages(['THE ENCOUNTER, AT A GLANCE', 'CPT coding summary'],
                             ['THE REASONS, IN THE RECORD', 'Reason: The coding review notes', f'{filler} tool'],
                             ['calls w521 w522 w523.', 'DOCUMENTATION NOTES'])
        reading = sc.read_pdf(pdf_bytes(*pages))
        self.assertEqual(reading.pages[1].split('\n')[:6], pages[1][:6])  # the running lines lead the page
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(reading, sc.scan_context(), 'x.pdf')],
                         [('tool_call', 'x.pdf page 2 line 9 to page 3 line 7')])
        self.assertEqual(sc._running_count([page.split('\n') for page in reading.pages]), 6)
        # the control: the same words on one page, as a reader would read them
        joined = sc.read_pdf(pdf_bytes(['Reason: The coding review notes', f'{filler} tool calls w521 w522 w523.']))
        self.assertEqual([hit['id'] for hit in sc.scan_pdf(joined, sc.scan_context(), 'x.pdf')], ['tool_call'])
        # a quotation the page break cuts is set aside whole, and the reason after it is still read
        document = 'Dr. Claude Example removed the polyp with a cold snare'
        cut = report_pages(['THE REASONS, IN THE RECORD', '01   45385  /  Ready for approval',
                            '“Dr. Claude Example removed the polyp'], ['with a cold snare”', 'Page 2',
                                                                         'Reason: read by Claude.'])
        reading = sc.read_pdf(pdf_bytes(*cut))
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(reading, sc.scan_context(document), 'x.pdf')],
                         [('provider_name', 'x.pdf page 2 line 9')])
        # the running lines are still scanned, on every page: an identity line naming a vendor is found on each
        named = sc.read_pdf(pdf_bytes(*report_pages(['Approved CPT codes'], ['Every approved code has a source.'],
                                                    identity='Claude review · F6000000 · Coding review 1')))
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(named, sc.scan_context(), 'x.pdf')],
                         [('provider_name', 'x.pdf page 1 line 4'), ('provider_name', 'x.pdf page 2 line 4')])
        # a page whose own number differs is still the same running footer; a line that differs ends the running lines
        self.assertEqual(sc._running_count([['A', 'r1 / 01 of 02', 'x'], ['A', 'r1 / 02 of 02', 'y']]), 2)
        self.assertEqual(sc._running_count([['A ', 'r1   /   01 of 02', 'x'], ['A', 'r1 / 02  of 02 ', 'y']]), 2)
        self.assertEqual(sc._running_count([['A', 'r1 / 02 of 02', 'x'], ['A', 'r1 / 02 of 02', 'y']]), 1)
        self.assertEqual(sc._running_count([['A', 'B']]), 0)  # one page: nothing repeats

    def test_an_invisible_character_inside_a_name_is_read_as_the_reader_sees_it(self):
        """L3-1: a format character the report draws with no ink, inside a vendor name, does not hide it - the PDF's
        text is read with every default-ignorable or format character deleted and every control character as a space."""
        reading = sc.read_pdf(ttf_pdf_bytes(['Reason: Cl\u200eaude read the snare.']))
        self.assertIn('Cl\u200eaude', reading.pages[0])  # the mark is in the text layer, as the renderer drew it
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(reading, sc.scan_context(), 'x.pdf')],
                         [('provider_name', 'x.pdf page 1 line 1')])
        # each mark the report's font draws as nothing, through a real PDF
        drawn = ('\u200f', '\u202a', '\u202b', '\u202c', '\u202d', '\u202e', '\u034f', '\u2061', '\u2062', '\u2063',
                 '\u2064', '\ufe00', '\ufe0f', '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff', '\u00ad')
        for mark in drawn:
            with self.subTest(mark=f'U+{ord(mark):04X}'):
                reading = sc.read_pdf(ttf_pdf_bytes([f'Reason: Gem{mark}ini read the snare.']))
                self.assertEqual([hit['id'] for hit in sc.scan_pdf(reading, sc.scan_context(), 'x.pdf')],
                                 ['provider_name'])
        # and every one the finding names, as pypdf would read it from a font that has it (the isolates and the Arabic
        # letter mark included)
        for mark in drawn + ('\u200e', '\u2066', '\u2067', '\u2068', '\u2069', '\u061c', '\U000e0041'):
            with self.subTest(text_mark=f'U+{ord(mark):04X}'):
                self.assertEqual([hit['id'] for hit in sc.scan_pdf(sc.PdfReading([f'Op{mark}enAI saw it.'], {}),
                                                                   sc.scan_context(), 'x.pdf')], ['provider_name'])
        # a C0 or C1 control character is read as a space: it separates words, it never joins them
        self.assertEqual(sc.visible('Cl\x01aude\x85read\x9fit\tnow'), 'Cl aude read it now')
        controls = sc.PdfReading(['Reason: its own tool\x01calls returned.'], {})
        self.assertEqual([hit['id'] for hit in sc.scan_pdf(controls, sc.scan_context(), 'x.pdf')], ['tool_call'])
        # the document information is read the same way
        meta = sc.PdfReading(['Approved CPT codes'], {'Author': 'Cl\u200baude'})
        self.assertEqual([(hit['id'], hit['where']) for hit in sc.scan_pdf(meta, sc.scan_context(), 'x.pdf')],
                         [('provider_name', 'x.pdf metadata Author')])
        # a quotation of the document is still recognised when the document holds an invisible character the
        # report does not print
        self.assertEqual(sc.scan_pdf(sc.PdfReading(['“Dr. Claude Example”'], {}),
                                     sc.scan_context('Dr. Cl\u200baude Example'), 'x.pdf'), [])
        # a page whose only text is invisible gives no text a reader can see: not read, never a pass
        with self.assertRaisesRegex(sc.Unreadable, 'no text could be read from page 1'):
            sc.read_pdf(ttf_pdf_bytes(['\u200b\u200d\u2060']))

    def test_the_trailer_id_is_never_read_so_its_hex_never_trips_long_hex(self):
        data = approved_pdf()
        self.assertRegex(data, rb'/ID\s*\[\s*<[0-9a-fA-F]{32}>')  # the PDF's identifier: 32 hex characters
        # read as bytes, as a TXT is, a clean PDF would fail on it
        self.assertIn('long_hex', {hit['id'] for hit in sc.scan_file(data.decode('utf-8', 'replace'), sc.scan_context(),
                                                                     'raw', 'txt')})
        self.assertEqual(sc.scan_pdf(sc.read_pdf(data), sc.scan_context(), 'approved.pdf'), [])
        # the rule still holds on what the PDF shows: a hash drawn on its page is found
        drawn = sc.scan_pdf(sc.read_pdf(pdf_bytes([f'Digest {"ab" * 32}'])), sc.scan_context(), 'h.pdf')
        self.assertEqual([(hit['id'], hit['where']) for hit in drawn], [('long_hex', 'h.pdf page 1 line 1')])

    def test_a_body_that_claims_to_be_a_pdf_and_cannot_be_read_fails_closed(self):
        clean = approved_pdf()
        pointer = re.search(rb'startxref\s+(\d+)', clean)
        # one pypdf would have to repair (its cross-reference pointer moved) is not read either: strict mode
        repaired = clean[:pointer.start(1)] + str(int(pointer.group(1)) + 5).encode() + clean[pointer.end(1):]
        for body in (b'%PDF-1.7\nnot a PDF at all\n', clean[:len(clean) // 2], b'', EXPORTS[DRAFT_ID].encode('utf-8'),
                     repaired):
            with self.subTest(body=body[:24]):
                with self.assertRaisesRegex(sc.Unreadable, r'^pypdf could not read it as a PDF \(\w+\)$'):
                    sc.read_pdf(body)
        with unittest.mock.patch.dict(sys.modules, {'pypdf': None}):
            with self.assertRaisesRegex(sc.Unreadable, 'pypdf is not installed'):
                sc.read_pdf(clean)
        self.assertEqual(len(sc.read_pdf(clean).pages), 2)  # the control
        self.assertTrue(sc.is_pdf(b'%PDF-1.4 opens as one', 'text/plain'))
        self.assertTrue(sc.is_pdf(b'served as one', 'Application/PDF; charset=binary'))
        self.assertFalse(sc.is_pdf(b'plain words', 'text/plain; charset=utf-8'))
        self.assertFalse(sc.is_pdf(b' %PDF-1.4 not at the start'))

    def test_a_pdf_holding_what_the_scan_does_not_read_fails_closed(self):
        from reportlab.pdfgen import canvas

        def drawn(add):
            buffer = io.BytesIO()
            drawing = canvas.Canvas(buffer, invariant=1)
            drawing.setFont('Helvetica', 11)
            drawing.drawString(72, 720, 'Approved CPT codes')
            add(drawing)
            drawing.showPage()
            drawing.save()
            return buffer.getvalue()

        def link(drawing):
            drawing.linkURL('https://example.invalid/', (72, 700, 200, 730))

        def bookmark(drawing):
            drawing.bookmarkPage('codes')
            drawing.addOutlineEntry('Codes', 'codes')

        def form(drawing):
            drawing.beginForm('mark')
            drawing.drawString(0, 0, 'Approved')
            drawing.endForm()
            drawing.doForm('mark')

        def page_labels(drawing):  # L3-7: a viewer shows "Claude Fable 1" in its page box; no page holds the words
            drawing.addPageLabel(0, prefix='Claude Fable ')

        for add, what in ((link, 'annotations on page 1'), (bookmark, 'bookmarks'),
                          (form, 'an image or form object on page 1'), (page_labels, 'page labels')):
            with self.subTest(what=what):
                with self.assertRaisesRegex(sc.Unreadable, re.escape(what)):
                    sc.read_pdf(drawn(add))
        self.assertEqual(sc.read_pdf(drawn(lambda drawing: None)).pages[0].strip(), 'Approved CPT codes')  # the control
        with self.assertRaisesRegex(sc.Unreadable, 'no text could be read from page 2'):
            sc.read_pdf(pdf_bytes(['Approved CPT codes'], []))


# --- a loopback stand-in for the customer surface ------------------------------------------------------------------

class StubSite:
    """The customer surface on 127.0.0.1, from the synthetic payloads; ``leak`` switches on each broken shape."""

    def __init__(self, **leak):
        self.leak = leak
        self.sessions, self.log = set(), []
        self.encounter = encounter_json()
        self.id = self.encounter['id']
        self.reports = dict(EXPORTS)
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                stub.handle(self, b'')

            def do_POST(self):
                stub.handle(self, self.rfile.read(int(self.headers.get('Content-Length') or 0)))

        class Server(ThreadingHTTPServer):
            daemon_threads = True

        self.server = Server(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def send(self, request, status, body, content_type='application/json', headers=()):
        data = body if isinstance(body, bytes) else (json.dumps(body) if not isinstance(body, str) else body).encode('utf-8')
        request.send_response(status)
        request.send_header('Content-Type', content_type)
        request.send_header('Content-Length', str(len(data)))
        for name, value in headers:
            request.send_header(name, value)
        request.end_headers()
        request.wfile.write(data)

    def handle(self, request, body):
        cookies = {name: morsel.value for name, morsel in SimpleCookie(request.headers.get('Cookie', '')).items()}
        self.log.append((request.command, request.path))
        signed = cookies.get('cptstudio_session') in self.sessions
        route = (request.command, request.path)
        if route == ('GET', '/login/'):
            token = secrets.token_hex(16)
            page = ('<html><body><form class="login-form" method="post" action="">'
                    f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}"><input name="username">'
                    '<input name="password" type="password"><button type="submit">Sign in</button></form></body></html>')
            return self.send(request, 200, page, 'text/html', [('Set-Cookie', f'cptstudio_csrf={token}; Path=/')])
        if route == ('POST', '/login/'):
            form = {key: values[0] for key, values in parse_qs(body.decode()).items()}
            if form.get('username') != USERNAME or form.get('password') != PASSWORD:
                return self.send(request, 200, '<p class="form-error">Wrong.</p>', 'text/html')
            session = secrets.token_hex(16)
            self.sessions.add(session)
            return self.send(request, 302, b'', 'text/html', [('Location', '/'), ('Set-Cookie', f'cptstudio_session={session}; Path=/')])
        if route == ('POST', '/logout/'):
            self.sessions.discard(cookies.get('cptstudio_session'))
            return self.send(request, 302, b'', 'text/html', [('Location', '/login/'),
                                                              ('Set-Cookie', 'cptstudio_session=""; Max-Age=0; Path=/')])
        if not signed:
            return self.send(request, 401, {'error': 'Sign in to continue.'})
        if route == ('GET', '/'):
            scripts = '<script defer src="/static/studio/app.js"></script>' + ('<script src="/static/studio/extra.js"></script>' if self.leak.get('two_scripts') else '')
            return self.send(request, 200, f'<!doctype html><html><head><link rel="stylesheet" href="/static/studio/styles.css">{scripts}</head>'
                                           '<body><main id="main"></main></body></html>', 'text/html')
        if route == ('GET', '/static/studio/app.js'):
            code = "const api = path => fetch(path); const token = readCookie('cptstudio_csrf');"
            return self.send(request, 200, code + (" const LABEL = 'Claude';" if self.leak.get('bundle_name') else ''), 'text/javascript')
        if route in (('GET', '/static/studio/styles.css'), ('GET', '/static/studio/extra.js')):
            return self.send(request, 200, 'main { margin: 0; }', 'text/css')
        paged = self.leak.get('two_pages') or self.leak.get('short_list')
        if route == ('GET', '/api/session'):
            session = session_json()
            if self.leak.get('session_mode'):
                session['provider_mode'] = 'live'
            if paged:  # the practice holds two documents
                session['counts'] = {'documents': 2, 'queue': 0}
            return self.send(request, 200, session)
        if request.command == 'GET' and request.path.split('?')[0] == '/api/encounters':
            row = {'id': self.id, 'title': self.encounter['title'], 'state': 'reviewed', 'state_label': 'Reviewed',
                   'service_date': '2026-11-02', 'insurance': 'medicare', 'created_at': self.encounter['created_at'],
                   'kind': 'upload', 'opens_pdf': True}
            if request.path == '/api/encounters':  # the first page: release 2's next and total
                more = bool(self.leak.get('two_pages'))
                return self.send(request, 200, {'encounters': [row], 'next': NEXT_PAGE if more else None,
                                                'total': 2 if more else 1})
            if self.leak.get('refused') and request.path != '/api/encounters':  # the list limit (R2-21): 429
                self.leak['refused'] -= 1
                wait = self.leak.get('retry_after', '1')
                return self.send(request, 429, {'error': 'rate_limited', 'retry_after': 1},
                                 headers=[('Retry-After', wait)] if wait is not None else [])
            if self.leak.get('two_pages') and parse_qs(request.path.split('?', 1)[1]) == {'before': [NEXT_PAGE]}:
                return self.send(request, 200, {'encounters': [{**row, 'id': SECOND_ID}], 'next': None, 'total': None})
            return self.send(request, 400, {'error': 'That part of the list could not be read. Open the list again.',
                                            'details': {}})
        ids = (self.id, SECOND_ID) if self.leak.get('two_pages') else (self.id,)
        for listed in ids:
            if route in (('GET', f'/api/encounters/{listed}/original'), ('GET', f'/api/encounters/{listed}/original?view=1')):
                headers = [('X-Content-SHA256', 'cd' * 32)] if self.leak.get('original_hash') else []
                if route[1].endswith('?view=1') and self.leak.get('etag'):
                    headers.append(('ETag', self.leak['etag']))
                return self.send(request, 200, b'%PDF-1.4 synthetic ' + b'0' * (3 * 1024 * 1024), 'application/pdf', headers)
        if self.leak.get('two_pages') and route == ('GET', f'/api/encounters/{SECOND_ID}'):
            enc = json.loads(json.dumps(self.encounter).replace(self.id, SECOND_ID))
            return self.send(request, 200, enc)
        if route == ('GET', f'/api/encounters/{self.id}'):
            enc = json.loads(json.dumps(self.encounter))
            if self.leak.get('vendor_key'):
                enc['codes'][0]['vendor'] = 'Anthropic'
            if self.leak.get('run_id'):
                enc['codes'][0]['reason'] = 'Read in run c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d.'
            return self.send(request, 200, enc)
        if request.command == 'GET' and request.path.startswith('/api/reports/') and request.path.endswith('/download'):
            report = request.path.split('/')[3]
            listed = next((item for item in self.encounter['reports'] if item['id'] == report), None)
            if listed is None:
                return self.send(request, 404, {'error': 'Not found.'})
            headers = [('X-Content-SHA256', 'ab' * 32)] if self.leak.get('hash_header') else []
            if listed['fmt'] == 'pdf':
                if self.leak.get('pdf_plain'):  # listed as a PDF, served as plain text: still a PDF that cannot be read
                    return self.send(request, 200, EXPORTS[DRAFT_ID], CONTENT_TYPES['txt'], headers)
                leak = 'text' if self.leak.get('pdf_leak') else 'metadata' if self.leak.get('pdf_meta_leak') else ''
                body = b'%PDF-1.7\n% not a readable PDF\n' if self.leak.get('pdf_broken') else approved_pdf(leak)
                return self.send(request, 200, body, 'text/plain' if self.leak.get('pdf_as_text') else 'application/pdf',
                                 headers)
            text = self.reports[report]
            # the TXT export leaks (the CSV has no Limitations line); the leak case expects scan.file to fail on it
            leaked = text.replace('\nLimitations', '\nUSAGE\n  claude-fable-5-2: 12,000 tokens\n\nLimitations', 1) if self.leak.get('report_leak') else text
            return self.send(request, 200, leaked, CONTENT_TYPES[listed['fmt']], headers)
        if request.command == 'GET' and request.path.startswith('/ops/'):
            if self.leak.get('ops_open') and request.path == f'/ops/encounters/{self.id}':
                return self.send(request, 200, '<h1>Runs</h1><p>reader claude-fable-5-2</p>', 'text/html')
            return self.send(request, 404, {'error': 'Not found.'})
        if route == ('GET', f'/api/encounters/{self.id}/trace'):
            return self.send(request, 200 if self.leak.get('trace_open') else 404, {'error': 'Not found.'})
        return self.send(request, 404, {'error': 'Not found.'})


class ScanRunTests(unittest.TestCase):
    def run_scan(self, *extra, site=None, credentials=None):
        site = site or StubSite()
        self.addCleanup(site.close)
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        if credentials is None:
            credentials = Path(folder) / 'customer.json'
            credentials.write_text(json.dumps({'username': USERNAME, 'password': PASSWORD}))
            os.chmod(credentials, 0o600)
        out = Path(folder) / 'out'
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = sc.main(['--base-url', site.base, '--credentials', str(credentials), '--out', str(out), *extra])
        evidence = json.loads((out / sc.EVIDENCE_NAME).read_text()) if (out / sc.EVIDENCE_NAME).exists() else None
        return code, evidence, stdout.getvalue() + stderr.getvalue(), site

    def statuses(self, evidence):
        return {item['id']: item['status'] for item in evidence['checks']}

    def test_a_clean_customer_surface_passes_with_get_requests_only_and_the_session_is_signed_out(self):
        code, evidence, printed, site = self.run_scan('--all')
        self.assertEqual(code, 0, printed)
        self.assertEqual(evidence['result'], 'pass')
        self.assertTrue(evidence['only_get_beyond_sign_in_and_out'])
        self.assertEqual([m for m, _ in site.log if m == 'POST'], ['POST', 'POST'])  # sign-in, sign-out
        statuses = self.statuses(evidence)
        short = site.id[:8]
        for check in ('session.contract', 'customer.list_contract', f'customer.contract.{short}', f'authorization.{short}', 'bundle.one_script',
                      'scan.json', 'scan.header', 'scan.file', 'scan.bundle', 'logout.session_refused'):
            self.assertEqual(statuses.get(check), 'pass', check)
        for check in (f'original.{short}', f'view.{short}', f'report.{short}.draft.txt', f'report.{short}.approved.csv',
                      f'report.{short}.approved.pdf', f'report.{short}.approved.pdf.text'):
            self.assertEqual(statuses.get(check), 'pass', check)
        self.assertEqual(evidence['encounters'], [{'id': site.id, 'status': 200, 'operator_view': False, 'reports': 3}])
        read = next(item['reason'] for item in evidence['checks'] if item['id'] == f'report.{short}.approved.pdf.text')
        self.assertIn('read as a PDF, 2 page(s) of text and 9 document information value(s) scanned', read)
        # every operator page and every removed URL was asked for, and answered 404
        asked = {path for method, path in site.log if method == 'GET'}
        for template in sc.OPS_GET_PATHS + sc.REMOVED_PATHS:
            self.assertIn(template.format(id=site.id), asked)
        self.assertNotIn(PASSWORD, json.dumps(evidence))
        self.assertNotIn(PASSWORD, printed)

    def test_each_leak_fails_the_check_it_exists_for(self):
        cases = [
            ({'vendor_key': True}, ['scan.json', 'customer.contract.{short}']),
            ({'ops_open': True}, ['authorization.{short}', 'scan.json']),
            ({'trace_open': True}, ['authorization.{short}']),
            ({'hash_header': True}, ['report.{short}.draft.txt', 'scan.header']),
            ({'report_leak': True}, ['scan.file']),
            ({'pdf_leak': True}, ['scan.file']),
            ({'pdf_meta_leak': True}, ['scan.file']),
            ({'pdf_broken': True}, ['report.{short}.approved.pdf.text']),
            ({'bundle_name': True}, ['scan.bundle']),
            ({'two_scripts': True}, ['bundle.one_script']),
            ({'session_mode': True}, ['session.contract']),
        ]
        for leak, wanted in cases:
            with self.subTest(leak=leak):
                code, evidence, printed, site = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(**leak))
                self.assertEqual(code, 1, printed)
                failed = {item['id'] for item in evidence['checks'] if item['status'] == 'fail'}
                for check in wanted:
                    self.assertIn(check.format(short=site.id[:8]), failed, (leak, sorted(failed)))

    def test_all_follows_the_lists_pages_and_scans_every_document_listed(self):
        # release 2 (R2-24): the list is paged; --all follows each page's next with ?before=, GET only, and holds every
        # page to the contract - so a practice of two pages is scanned whole, and the read is checked against the session
        code, evidence, printed, site = self.run_scan('--all', site=StubSite(two_pages=True))
        self.assertEqual(code, 0, printed)
        statuses = self.statuses(evidence)
        for check in ('customer.list_contract', 'customer.list_contract.page2', 'customer.list_complete',
                      f'customer.contract.{ENCOUNTER_ID[:8]}', f'customer.contract.{SECOND_ID[:8]}'):
            self.assertEqual(statuses.get(check), 'pass', check)
        self.assertEqual([item['id'] for item in evidence['encounters']], [ENCOUNTER_ID, SECOND_ID])
        asked = [path for method, path in site.log if method == 'GET' and path.startswith('/api/encounters?')]
        self.assertEqual(asked, [f'/api/encounters?before={urllib.parse.quote(NEXT_PAGE, safe="")}'])
        self.assertTrue(evidence['only_get_beyond_sign_in_and_out'])
        # --limit stops the pages: one document wanted, one page read, and that is complete
        code, evidence, printed, site = self.run_scan('--all', '--limit', '1', site=StubSite(two_pages=True))
        self.assertEqual((code, self.statuses(evidence).get('customer.list_complete')), (0, 'pass'), printed)
        self.assertFalse([path for method, path in site.log if path.startswith('/api/encounters?')])
        self.assertEqual([item['id'] for item in evidence['encounters']], [ENCOUNTER_ID])

    def test_all_waits_out_the_list_limit_on_a_later_page_and_asks_for_it_again(self):
        # release 2 (R2-21): each later page counts toward the member's list limit (120 a minute), so a practice of more
        # than about 6,000 documents meets a 429 inside a minute; the scan waits as Retry-After says and asks for the
        # same page again - GET only, at most twice a page - and a correct server passes
        later = f'/api/encounters?before={urllib.parse.quote(NEXT_PAGE, safe="")}'
        waited = []
        with unittest.mock.patch.object(sc.time, 'sleep', side_effect=waited.append):
            code, evidence, printed, site = self.run_scan('--all', site=StubSite(two_pages=True, refused=1))
        self.assertEqual(code, 0, printed)
        statuses = self.statuses(evidence)
        self.assertEqual((statuses.get('customer.list_contract.page2'), statuses.get('customer.list_complete')),
                         ('pass', 'pass'))
        self.assertEqual([path for method, path in site.log if path.startswith('/api/encounters?')], [later, later])
        self.assertEqual(waited, [1])
        self.assertTrue(evidence['only_get_beyond_sign_in_and_out'])
        # refused three times, or with a Retry-After the scan does not wait out (none, 0, over 61 s): the page fails
        for leak, gets, sleeps in (({'refused': 3}, 3, [1, 1]), ({'refused': 1, 'retry_after': None}, 1, []),
                                   ({'refused': 1, 'retry_after': '0'}, 1, []),
                                   ({'refused': 1, 'retry_after': '62'}, 1, [])):
            with self.subTest(leak=leak):
                waited.clear()
                with unittest.mock.patch.object(sc.time, 'sleep', side_effect=waited.append):
                    code, evidence, printed, site = self.run_scan('--all', site=StubSite(two_pages=True, **leak))
                self.assertEqual(code, 1, printed)
                statuses = self.statuses(evidence)
                self.assertEqual((statuses.get('customer.list_contract.page2'), statuses.get('customer.list_complete')),
                                 ('fail', 'fail'))
                self.assertEqual([path for method, path in site.log if path.startswith('/api/encounters?')],
                                 [later] * gets)
                self.assertEqual(waited, sleeps)

    def test_all_fails_when_the_list_holds_fewer_documents_than_the_session_counts(self):
        code, evidence, printed, _site = self.run_scan('--all', site=StubSite(short_list=True))
        self.assertEqual(code, 1, printed)
        statuses = self.statuses(evidence)
        self.assertEqual(statuses.get('customer.list_complete'), 'fail')
        self.assertIn('read 1 document(s)', next(item['reason'] for item in evidence['checks']
                                                  if item['id'] == 'customer.list_complete'))
        # without --all nothing is followed or counted: the named document alone
        code, evidence, printed, _site = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(short_list=True))
        self.assertEqual(code, 0, printed)
        self.assertNotIn('customer.list_complete', self.statuses(evidence))

    def test_an_api_answers_etag_is_absent_or_a_quoted_uuid_and_never_a_hash(self):
        for tag in (VIEW_TAG, f'W/{VIEW_TAG}'):
            with self.subTest(tag=tag):
                code, evidence, printed, _site = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(etag=tag))
                self.assertEqual((code, self.statuses(evidence).get('scan.header')), (0, 'pass'), printed)
        for tag in (f'"{"ab" * 32}"', f'"{"ab" * 8}"', VIEW_TAG.strip('"'), '"x"'):
            with self.subTest(tag=tag):
                code, evidence, printed, _site = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(etag=tag))
                self.assertEqual((code, self.statuses(evidence).get('scan.header')), (1, 'fail'), printed)
                self.assertIn('etag_shape', json.dumps(evidence['hits']['header']))
        self.assertEqual(sc.etag_hits([('ETag', f'"{"ab" * 32}"')], '/static/studio/app.0123456789ab.js'), [])

    def test_a_pdf_export_is_scanned_as_its_text_and_one_that_cannot_be_read_fails_the_run(self):
        check = f'report.{ENCOUNTER_ID[:8]}.approved.pdf.text'

        def failed(evidence):
            return {item['id']: item['reason'] for item in evidence['checks'] if item['status'] == 'fail'}

        # served as text/plain, it is still read as the PDF it says it is
        code, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(pdf_as_text=True))
        self.assertEqual(code, 0, printed)
        self.assertIn('read as a PDF, 2 page(s)', next(c['reason'] for c in evidence['checks'] if c['id'] == check))
        # a body that claims to be a PDF - served as one, opening as one, or listed as one - and cannot be read fails
        # the run; it is never scanned as text instead, so it never passes
        for leak in ('pdf_broken', 'pdf_plain'):
            with self.subTest(leak=leak):
                code, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(**{leak: True}))
                self.assertEqual(code, 1)
                self.assertEqual(list(failed(evidence)), [check])
                self.assertIn('pypdf could not read it as a PDF', failed(evidence)[check])
                self.assertIn('it was not scanned', failed(evidence)[check])
        # a Python without pypdf cannot read it either: the same failure, never a pass
        with unittest.mock.patch.dict(sys.modules, {'pypdf': None}):
            code, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID)
        self.assertEqual(code, 1)
        self.assertEqual(list(failed(evidence)), [check])
        self.assertIn('pypdf is not installed', failed(evidence)[check])
        # the leaks are found where the PDF shows them, with their page and line or their metadata entry
        code, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(pdf_leak=True))
        self.assertEqual(code, 1)
        self.assertIn('approved.pdf page 2 line 7', {hit['where'] for hit in evidence['hits']['file']})
        code, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(pdf_meta_leak=True))
        self.assertEqual([(hit['id'], hit['where']) for hit in evidence['hits']['file']],
                         [('provider_name', 'approved.pdf metadata Author')])

    def test_an_uploaded_original_and_its_view_are_read_for_their_headers_only_whatever_their_size(self):
        code, evidence, printed, site = self.run_scan('--encounter', ENCOUNTER_ID)
        self.assertEqual(code, 0, printed)
        statuses = {c['id']: c['status'] for c in evidence['checks']}
        self.assertEqual((statuses[f'original.{ENCOUNTER_ID[:8]}'], statuses[f'view.{ENCOUNTER_ID[:8]}']), ('pass', 'pass'))
        # a source hash on the original's download (and so on its view) is a customer-facing hash
        code, evidence, printed, site = self.run_scan('--encounter', ENCOUNTER_ID, site=StubSite(original_hash=True))
        self.assertEqual(code, 1)
        wheres = [h['where'] for h in evidence['hits']['header'] if h['id'] == 'long_hex']
        self.assertTrue(any(where.endswith('/original header X-Content-SHA256') for where in wheres), wheres)
        self.assertTrue(any('?view=1' in where for where in wheres), wheres)

    def test_the_operator_view_s_identifiers_are_looked_for_when_the_denylist_names_their_paths(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        (folder / f'{ENCOUNTER_ID}.json').write_text(json.dumps({'runs': [{'id': 'c0ffee00-0002-4a5b-8c6d-7e8f9a0b1c2d'}]}))
        with unittest.mock.patch.dict(sc.DENYLIST, {'deny_value_paths': {'encounter': ['runs[].id'], 'trace': []}}):
            code, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID, '--operator-json', str(folder),
                                                       site=StubSite(run_id=True))
            self.assertEqual(code, 1)
            hits = evidence['hits']['json']
            self.assertTrue(any(hit['id'] == 'deny_value' for hit in hits), hits)
            self.assertEqual(evidence['encounters'][0]['operator_view'], True)
            clean, evidence, printed, _ = self.run_scan('--encounter', ENCOUNTER_ID, '--operator-json', str(folder))
            self.assertEqual(clean, 0, printed)

    def test_usage_errors_are_refused_before_any_request(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        loose = folder / 'loose.json'
        loose.write_text(json.dumps({'username': USERNAME, 'password': PASSWORD}))
        os.chmod(loose, 0o644)
        site = StubSite()
        code, evidence, printed, _ = self.run_scan(site=site, credentials=loose)
        self.assertEqual((code, evidence), (2, None))
        self.assertIn('mode 0644', printed)
        self.assertEqual(site.log, [])
        code, evidence, printed, _ = self.run_scan('--encounter', 'not-an-id')
        self.assertEqual((code, evidence), (2, None))
        self.assertIn('not an encounter id', printed)
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(sc.main(['--base-url', 'http://example.com', '--credentials', str(loose), '--out', str(folder / 'o')]), 2)
        self.assertIn('plain http', stderr.getvalue())

    def test_a_refused_sign_in_scans_nothing(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(folder, ignore_errors=True))
        wrong = folder / 'wrong.json'
        wrong.write_text(json.dumps({'username': USERNAME, 'password': 'not-the-password'}))
        os.chmod(wrong, 0o600)
        code, evidence, printed, site = self.run_scan(credentials=wrong)
        self.assertEqual(code, 1)
        self.assertEqual([path for _, path in site.log], ['/login/', '/login/'])
        self.assertEqual({item['id']: item['status'] for item in evidence['checks']}, {'login.signed_in': 'fail'})


class HostCookieTests(unittest.TestCase):
    """Release 1 (B6): over https the server's session cookie is __Host-cptstudio_session; the scan reads that name (the
    stub site above serves plain http, where the names are the plain ones)."""

    def test_an_https_sign_in_is_read_by_the_host_prefixed_session_cookie(self):
        origin = 'https://cpt.example.test'
        form = ('<html><body><form class="login-form" method="post" action="">'
                '<input type="hidden" name="csrfmiddlewaretoken" value="t0k3n"><input name="username">'
                '<input name="password" type="password"><button type="submit">Sign in</button></form></body></html>')

        class FakeTransport:
            def __init__(self, session_name):
                self.session_name, self.sent = session_name, []

            def send(self, method, path, *, headers, body=None, read_body=True):
                self.sent.append((method, path))
                if (method, path) == ('GET', '/login/'):
                    return sc.login.Response(200, None, ['__Host-cptstudio_csrf=t0k3n; Path=/; Secure; SameSite=Strict'],
                                          'text/html', form.encode())
                if (method, path) == ('POST', '/login/'):
                    return sc.login.Response(302, '/', [f'{self.session_name}=s1; HttpOnly; Path=/; Secure; SameSite=Strict'],
                                          'text/html', b'')
                if (method, path) == ('POST', '/logout/'):
                    return sc.login.Response(302, '/login/', [f'{self.session_name}=""; Max-Age=0; Path=/; Secure'],
                                          'text/html', b'')
                return sc.login.Response(401, None, [], 'application/json', b'{"error": "Sign in to continue."}')

        class FakeScanner:  # the scans themselves are the stub site's tests above: here only the sign-in matters
            def __init__(self, transport, origin, jar):
                self.checks, self.hits = [], {'json': [], 'header': [], 'file': [], 'bundle': []}

            def bundle(self, base):
                return None

            def json_get(self, where, base):
                return sc.login.Response(401, None, [], 'application/json', b'{}'), None

        signed = FakeTransport('__Host-cptstudio_session')
        with unittest.mock.patch.object(sc, 'Scanner', FakeScanner):
            out = sc.run(signed, origin, USERNAME, PASSWORD, [], False, 0, None)
        checks = {item['id']: item['status'] for item in out['checks']}
        self.assertEqual(checks.get('login.signed_in'), 'pass', out['checks'])
        self.assertTrue(out['signed_in'])
        self.assertEqual(checks.get('logout.cookie_cleared'), 'pass')  # the sign-out deleted the __Host- cookie
        # a server whose session cookie is not the one its CSRF cookie names has not signed the scan in
        mixed = FakeTransport('cptstudio_session')
        out = sc.run(mixed, origin, USERNAME, PASSWORD, [], False, 0, None)
        self.assertEqual({item['id']: item['status'] for item in out['checks']}, {'login.signed_in': 'fail'})
        self.assertFalse(out['signed_in'])
        self.assertEqual(mixed.sent, [('GET', '/login/'), ('POST', '/login/')])

    def test_after_a_switch_back_the_plain_names_over_https_are_read(self):
        # refutation, rollback lens B-9: a revision before release 1 sets cptstudio_csrf and cptstudio_session over
        # https; the scan reads the names the server set, never the scheme's
        origin = 'https://cpt.example.test'
        form = ('<html><body><form class="login-form" method="post" action="">'
                '<input type="hidden" name="csrfmiddlewaretoken" value="t0k3n"><input name="username">'
                '<input name="password" type="password"><button type="submit">Sign in</button></form></body></html>')

        class R0Transport:
            def send(self, method, path, *, headers, body=None, read_body=True):
                if (method, path) == ('GET', '/login/'):
                    return sc.login.Response(200, None, ['cptstudio_csrf=t0k3n; Path=/; Secure'], 'text/html',
                                             form.encode())
                if (method, path) == ('POST', '/login/'):
                    return sc.login.Response(302, '/', ['cptstudio_session=s0; HttpOnly; Path=/; Secure'], 'text/html',
                                             b'')
                if (method, path) == ('POST', '/logout/'):
                    return sc.login.Response(302, '/login/', ['cptstudio_session=""; Max-Age=0; Path=/'], 'text/html',
                                             b'')
                return sc.login.Response(401, None, [], 'application/json', b'{}')

        class FakeScanner:
            def __init__(self, transport, origin, jar):
                self.checks, self.hits = [], {'json': [], 'header': [], 'file': [], 'bundle': []}

            def bundle(self, base):
                return None

            def json_get(self, where, base):
                return sc.login.Response(401, None, [], 'application/json', b'{}'), None
        with unittest.mock.patch.object(sc, 'Scanner', FakeScanner):
            out = sc.run(R0Transport(), origin, USERNAME, PASSWORD, [], False, 0, None)
        checks = {item['id']: item['status'] for item in out['checks']}
        self.assertEqual((checks.get('login.signed_in'), checks.get('logout.cookie_cleared')), ('pass', 'pass'))
        self.assertTrue(out['signed_in'])


if __name__ == '__main__':
    unittest.main()
