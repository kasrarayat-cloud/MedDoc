"""Frontend shell: templates render under the CSP, the approved stylesheet is intact, the customer page's synthetic
fixtures carry the customer contract (client contract customer-2026-11-26, the build specification's section 6 with the
fix passes' line identity, decision ids and download rounds, as ops/verification/customer-contract.json holds it), and
the browser logic's own tests pass (node)."""
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from studio import customer, views
from studio.access import SecurityHeadersMiddleware

ROOT = Path(settings.BASE_DIR)
STATIC = ROOT / 'studio' / 'static' / 'studio'
TEMPLATES = ROOT / 'studio' / 'templates' / 'studio'
CUSTOMER_FIXTURES = ROOT / 'tests' / 'fixtures' / 'customer'
# The owner-approved styles.css (design package, 2026-10-23): its bytes must stay the file's prefix.
APPROVED_CSS_LENGTH = 32785
APPROVED_CSS_SHA256 = '4d68468c74e7b47d80472b9c95c6947189051089349b1559863ded7bd7b047e8'
PLAIN_STATIC = {**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
# The pinned PDF library the review page draws a PDF with (DECISIONS D368): the legacy build of pdfjs-dist 6.5.438 and the
# files it uses, each byte-identical to the npm tarball pdfjs-dist-6.5.438.tgz (sha512 integrity below), and the licence of
# the core-js its legacy build bundles (from core-js-3.51.0.tgz), and nothing else.
PDF_LIB = STATIC / 'lib' / 'pdfjs-6.5.438'
PDF_LIB_NAME = 'studio/lib/pdfjs-6.5.438'
PDF_LIB_INTEGRITY = 'sha512-vg8Pw1x+AFKy4AMDvhuWl5cOYV8d698UoEANoFFhc79hqXDnZQqnOXoxw3HG907WHOg1JYOvLhP756boddFxpA=='
COREJS_INTEGRITY = 'sha512-7bDKx/5jm5MxzsXxc93g6Z2+4ZsuT/MddrfRmTDJNAkWsYWHU8EVNEsBiIEWnMAMCHMmRfUEjkuo3jeNBOIHRw=='
PDF_LIB_SCRIPTS = ('legacy/build/pdf.min.mjs', 'legacy/build/pdf.worker.min.mjs', 'wasm/jbig2_nowasm_fallback.js',
                   'wasm/openjpeg_nowasm_fallback.js')
# The suite's own pin of the library (DECISIONS D368, round 3): the sha256 of every file under PDF_LIB, MANIFEST.json
# included, as the lines "<path> <sha256>\n" sorted by path, hashed together. The checks below read their expectations
# from MANIFEST.json; this one does not, so a changed vendored file - with its manifest entry changed to match - fails
# until this line is changed too, in the open (library_digest).
PDF_LIB_DIGEST = '0a2a90ad83c1c80ba19fc4821e27588f50938c7eda06cc0f23beea8c7aeba0e0'
# core-js's lookup of the global object, as the legacy build bundles it (core-js internals/global-this): the one place
# either legacy file builds a function from a string. It is reached only where globalThis, window, self, global and the
# module's own `this` (undefined in a module) are all missing, which never happens in a browser - and the shell's policy
# has no 'unsafe-eval', so a browser would refuse it anyway. It is allowed by its exact bytes, once per file.
COREJS_GLOBAL_LOOKUP = ('check("object"==typeof globalThis&&globalThis)||check("object"==typeof window&&window)||'
                        'check("object"==typeof self&&self)||check("object"==typeof global&&global)||'
                        'check("object"==typeof this&&this)||function(){return this}()||Function("return this")()')
# Code built from a string, as CODE_FROM_STRINGS reads it in the library's text (D368 rounds 3 and 5, D2): eval named in
# any way (called, or reached as a property: globalThis.eval, x["eval"]); Function called - Function(...), new
# Function(...), self.Function(...), x["Function"](...), Function?.(...) - or used as a tag (Function`...`, new
# Function`...`), passed straight into a call as a value ((0,Function)(...), Reflect.construct(Function, ...)), or called
# through call, apply or bind (Function.call(...), Function?.call(...)); a constructor called with a string literal or used
# as a tag (x.constructor("..."), x.constructor?.("..."), x["constructor"]("..."), x.constructor`...`); and setTimeout or
# setInterval called with a string literal or used as a tag, directly or as a property (setTimeout("..."),
# setTimeout?.("..."), window.setTimeout("..."), window["setTimeout"]("..."), setTimeout`...`). What a text search
# cannot see is not claimed: a value held under another name and called by it (var F = Function; F("..."), or
# [Function][0]("...") and {f: Function}.f("...")), a string held in a variable (setTimeout(code), x.constructor(code)),
# or a name reached by computation (x[name](...)). Those are refused at run time: neither the page's policy nor the
# policy the library's own files are served with (studio.access.SecurityHeadersMiddleware.STATIC_CSP, which binds its
# worker) allows 'unsafe-eval'.
CODE_FROM_STRINGS = re.compile(r'(?<![\w$])eval\b|\[\s*["\'`](?:eval|Function)["\'`]\s*\]'
                               r'|\[\s*["\'`](?:constructor|setTimeout|setInterval)["\'`]\s*\]\s*(?:\?\.\s*)?[(`]'
                               r'|(?<![\w$])Function\s*(?:(?:\?\.\s*)?[(`]|[),]|\??\.\s*(?:call|apply|bind)\b)'
                               r'|\.constructor\s*(?:\?\.\s*)?(?:\(\s*["\'`]|`)'
                               r'|(?<![\w$])set(?:Timeout|Interval)\s*(?:\?\.\s*)?(?:\(\s*["\'`]|`)')
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
# GET /api/session, /api/encounters and /api/encounters/<id>, exactly as the contract file lists them (the build
# specification, section 6, with document.view_media_type, document.converted and the state 'earlier')
CONTRACT = json.loads((ROOT / 'ops' / 'verification' / 'customer-contract.json').read_text(encoding='utf-8'))
ENCOUNTER_KEYS = set(CONTRACT['encounter']['keys'])
DOCUMENT_KEYS = set(CONTRACT['encounter']['keys']['document']['keys'])
CODE_KEYS = set(CONTRACT['types']['code']['keys'])
SESSION_KEYS = set(CONTRACT['session']['keys'])
ROW_KEYS = set(CONTRACT['types']['list_row']['keys'])
STATES = set(CONTRACT['types']['state']['enum'])
LIST_ROW_PDF_MEDIA_TYPE = 'application/pdf'  # a document block's media_type of a PDF upload
# What a customer surface never names (the build specification, section 0): vendor and model names, and the words the
# customer copy never uses.
FORBIDDEN = re.compile(r'(?<![a-z0-9])(?:corti|astra|fable|openai|anthropic|claude|gemini|google)(?![a-z0-9])'
                       r'|\b(?:providers?|models?|tokens?|credits?|vendors?|sha-?256)\b|/ops/', re.IGNORECASE)
INSURANCE = [('medicare', 'Medicare'), ('medicaid', 'Medicaid'), ('commercial', 'Commercial or other'),
             ('unknown', 'Not sure')]
# The server's sentences for a line the second check added (studio/customer.py, FIX-SPEC-2 section 3): with the status
# the second check gave it, or - for a line stored without one - the sentence without a status
ADDED_SENTENCES = {customer.ADDED_BY_CHECK,
                   *(customer.ADDED_WITH_STATUS.format(status=words) for words in customer.CHECK_STATUS_WORDS.values())}


class _Audit(HTMLParser):
    """Collects what the CSP (script-src 'self', no inline handlers) cares about."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.script_sources, self.handlers, self.unsafe_urls, self.external = [], [], [], [], []
        self.inline_script = False
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        for name, value in attrs:
            if name.startswith('on'):
                self.handlers.append(f'{tag}[{name}]')
            if name in {'href', 'src', 'action'} and value:
                lowered = value.strip().lower()
                if lowered.startswith(('javascript:', 'data:text/html', 'vbscript:')):
                    self.unsafe_urls.append(value)
                if lowered.startswith(('http:', 'https:', '//')):
                    self.external.append(value)
        if tag == 'script':
            self.script_sources.append(values.get('src'))
            self._in_script = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self._in_script = False

    def handle_data(self, data):
        if self._in_script and data.strip():
            self.inline_script = True


def _audit(html):
    audit = _Audit()
    audit.feed(html)
    return audit


def _customer(name):
    return json.loads((CUSTOMER_FIXTURES / name).read_text(encoding='utf-8'))


def library_digest(root):
    """PDF_LIB_DIGEST's reading of a library folder: every file's "<path> <sha256>" line, sorted by path, hashed."""
    lines = sorted(f'{path.relative_to(root).as_posix()} {hashlib.sha256(path.read_bytes()).hexdigest()}\n'
                   for path in Path(root).rglob('*') if path.is_file())
    return hashlib.sha256(''.join(lines).encode('utf-8')).hexdigest()


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


@override_settings(STORAGES=PLAIN_STATIC)
class ShellTemplateTests(SimpleTestCase):
    def render_index(self, specialty='Gastroenterology'):
        return render_to_string('studio/index.html', {'release': 'test-release', 'specialty': specialty},
                                request=RequestFactory().get('/'))

    def test_index_renders_static_paths_and_a_csrf_token_from_the_request_alone(self):
        html = self.render_index()
        for path in ('/static/studio/styles.css', '/static/studio/app.js', '/static/studio/favicon.svg'):
            self.assertIn(path, html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertNotRegex(html, r'\{[%{]')

    def test_index_names_the_pinned_pdf_library_on_its_body_and_loads_no_more_scripts(self):
        html = self.render_index()
        body = re.search(r'<body ([^>]*)>', html).group(1)
        self.assertEqual(dict(re.findall(r'(data-pdf-module|data-pdf-worker)="([^"]*)"', body)), {
            'data-pdf-module': f'/static/{PDF_LIB_NAME}/legacy/build/pdf.min.mjs',
            'data-pdf-worker': f'/static/{PDF_LIB_NAME}/legacy/build/pdf.worker.min.mjs'})
        self.assertNotIn('modulepreload', html, 'the library is loaded only when a PDF is viewed')

    def test_index_obeys_the_content_security_policy(self):
        audit = _audit(self.render_index())
        self.assertFalse(audit.inline_script, 'inline script would be blocked by script-src self')
        self.assertEqual(audit.handlers, [])
        self.assertEqual(audit.unsafe_urls, [])
        self.assertEqual(audit.external, [], 'no external fonts, scripts or requests')
        self.assertEqual(audit.script_sources, ['/static/studio/app.js'], 'exactly one same-origin script')

    def test_index_carries_the_live_labels_not_the_design_preview_ones(self):
        html = self.render_index()
        self.assertIn('Synthetic only', html)
        self.assertIn('Original documentation. Clearer decisions.', html)
        self.assertIn('Synthetic documents only · Not for billing', html)
        self.assertIn('This document is synthetic and contains no real patient information.', html)
        self.assertIn('Start coding review', html)
        for preview_only in ('Design preview', 'Explore sample results', 'Northside Practice', 'Fictional examples · No AI processing'):
            self.assertNotIn(preview_only, html)
        self.assertRegex(html, r'<select id="specialty" disabled><option>Gastroenterology</option></select>')
        for family in ('EGD', 'Colonoscopy', 'ERCP', 'Endoscopic ultrasound', 'Sigmoidoscopy'):
            self.assertNotIn(f'<option>{family}', html, 'service families are internal, never a required choice')

    def test_upload_asks_for_the_insurance_with_four_fixed_choices(self):
        html = self.render_index()
        select = re.search(r'<label>Insurance<select id="insurance">(.*?)</select></label>', html)
        self.assertIsNotNone(select, 'the upload dialog labels its insurance select')
        options = re.findall(r'<option value="(\w+)"( selected)?>([^<]+)</option>', select.group(1))
        self.assertEqual([(value, label) for value, _, label in options], INSURANCE)
        self.assertEqual([value for value, selected, _ in options if selected], ['unknown'], 'Not sure until the member chooses')

    def test_every_element_id_the_script_looks_up_exists(self):
        index_ids = set(_audit(self.render_index()).ids)
        script = (STATIC / 'app.js').read_text(encoding='utf-8')
        rendered_ids = set(re.findall(r'id="([A-Za-z][\w-]*)"', script)) | set(re.findall(r"\.id = '([A-Za-z][\w-]*)'", script))
        looked_up = set()
        for selector in re.findall(r"\$\$?\('([^']*)'", script):
            looked_up.update(re.findall(r'#([A-Za-z][\w-]*)', selector))
        missing = sorted(looked_up - index_ids - rendered_ids)
        self.assertEqual(missing, [])
        # the coding review page (2026-11-20): the review dialog's statement is the label #reviewAcknowledgement, its
        # checkbox #reviewAckBox; the addendum dialog and the modifier choice are gone with the old page
        # the fix pass (2026-11-21): the review dialog states the line it decides - its units and modifiers - as #reviewLine
        self.assertTrue({'uploadDialog', 'insurance', 'reviewDialog', 'reviewAcknowledgement', 'reviewAckBox', 'reviewAckText',
                         'reviewLine', 'reviewNote', 'saveReview', 'exportDialog', 'aboutDialog', 'updateNotice',
                         'toast'} <= index_ids)
        self.assertFalse({'addendumDialog', 'reviewModifier', 'reviewModifierField'} & index_ids)
        # the review page's own hooks (section 7) are drawn by the script
        self.assertTrue({'documentViewer', 'quotesPanel', 'questionsPanel', 'sendAnswers', 'codesList', 'notesPanel'} <= rendered_ids)

    def test_login_renders_the_error_escaped_with_csrf_and_the_next_target(self):
        html = render_to_string('studio/login.html', {'error': '<b>Wrong</b> password', 'next': '/#doc/x"y'},
                                request=RequestFactory().get('/login/'))
        self.assertIn('&lt;b&gt;Wrong&lt;/b&gt; password', html)
        self.assertIn('role="alert"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn('name="next" value="/#doc/x&quot;y"', html)
        self.assertIn('Synthetic demonstration · Authorized users only', html)
        self.assertIn('name="username"', html)
        self.assertIn('name="password" type="password"', html)
        audit = _audit(html)
        self.assertFalse(audit.inline_script)
        # one same-origin script: session_news.js (integrated refutation round 1, session-0; tests/test_session_news.py)
        self.assertEqual(audit.script_sources, ['/static/studio/session_news.js'])
        self.assertEqual(audit.handlers, [])
        self.assertEqual(audit.external, [])

    def test_login_without_an_error_shows_no_alert(self):
        html = render_to_string('studio/login.html', {'error': '', 'next': '/'}, request=RequestFactory().get('/login/'))
        self.assertNotIn('role="alert"', html)
        self.assertNotIn('role="status"', html)

    def test_login_says_why_a_session_ended(self):
        # B5, item 5: the sentence the view gives (studio.views._signed_out_notice), as a status, escaped
        html = render_to_string('studio/login.html', {'error': '', 'next': '/', 'notice': 'You were signed out <b>'},
                                request=RequestFactory().get('/login/'))
        self.assertIn('<p class="upload-status" role="status">You were signed out &lt;b&gt;</p>', html)

    def test_the_console_signs_itself_out_and_without_script_moves_away_after_the_operators_limit(self):
        # B5, item 4: ops_session.js on every signed-in console page; without script a refresh ten seconds after the
        # session's own end (studio.sessions.page_config's refresh_seconds: tests.test_sessions.PageConfigTests), and
        # ten seconds after the operators' idle limit where a page is given none
        source = (TEMPLATES / 'ops_base.html').read_text(encoding='utf-8')
        self.assertIn('{% if user.is_authenticated %}<script src="/static/studio/ops_session.js" defer></script>', source)
        self.assertIn('<noscript><meta http-equiv="refresh" content="{{ request.cpt_page.refresh_seconds|default:'
                      f'{settings.SESSION_IDLE_OPERATOR_SECONDS + 10} }}}};url=/login/?reason=idle"></noscript>{{% endif %}}',
                      source)

    def test_release_one_s_pages_obey_the_content_security_policy(self):
        allowed = {'/static/studio/ops_session.js', '/static/studio/ops_second_factor.js'}
        for name in ('ops_base.html', 'ops_login.html', 'ops_second_factor.html', 'ops_enrol.html', 'ops_security.html',
                     'account_security.html', 'login.html', 'index.html'):
            with self.subTest(name):
                audit = _audit((TEMPLATES / name).read_text(encoding='utf-8'))
                self.assertFalse(audit.inline_script)
                self.assertEqual(audit.handlers, [])
                self.assertEqual(audit.unsafe_urls, [])
                self.assertEqual([src for src in audit.script_sources if src not in allowed and '{% static' not in src], [])


class StaticAssetTests(SimpleTestCase):
    def test_stylesheet_keeps_the_approved_design_byte_for_byte(self):
        data = (STATIC / 'styles.css').read_bytes()
        self.assertEqual(hashlib.sha256(data[:APPROVED_CSS_LENGTH]).hexdigest(), APPROVED_CSS_SHA256)

    def test_appended_rules_add_elements_without_redefining_tokens(self):
        appended = (STATIC / 'styles.css').read_bytes()[APPROVED_CSS_LENGTH:].decode('utf-8')
        self.assertNotIn(':root', appended)
        self.assertIsNone(re.search(r'--[\w-]+\s*:', appended), 'design tokens are defined only by the approved rules')

    def test_assets_are_self_contained(self):
        for name in ('styles.css', 'app.js'):
            text = (STATIC / name).read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'https?://|@import|url\(', text), name)
        script = (STATIC / 'app.js').read_text(encoding='utf-8')
        for unsafe in ('eval(', 'new Function', 'document.write', 'insertAdjacentHTML', 'outerHTML'):
            self.assertNotIn(unsafe, script)
        favicon = (STATIC / 'favicon.svg').read_text(encoding='utf-8')
        self.assertTrue(favicon.startswith('<svg xmlns="http://www.w3.org/2000/svg"'))
        self.assertNotIn('<script', favicon)

    def test_the_customer_page_names_no_vendor_model_or_machinery(self):
        for path in (STATIC / 'app.js', STATIC / 'styles.css', TEMPLATES / 'index.html', TEMPLATES / 'login.html'):
            with self.subTest(path.name):
                self.assertEqual(FORBIDDEN.findall(path.read_text(encoding='utf-8')), [])

    def test_the_page_sends_the_client_version_of_this_contract(self):
        script = (STATIC / 'app.js').read_text(encoding='utf-8')
        self.assertIn("const CLIENT_VERSION = 'customer-2026-11-26';", script)
        self.assertRegex(script, r'\[CLIENT_HEADER\]: CLIENT_VERSION')


class CustomerFixtureTests(SimpleTestCase):
    """The customer page's fixtures (tests/fixtures/customer), which its node tests and ops/dev_preview_server.cjs read:
    hand-made, synthetic, and shaped exactly as section 6 serves the customer contract."""

    def encounters(self):
        return {path.name: _customer(path.name) for path in sorted(CUSTOMER_FIXTURES.glob('encounter-*.json'))}

    def test_every_encounter_fixture_has_exactly_the_contract_keys(self):
        docs = self.encounters()
        self.assertEqual(len(docs), 12)
        self.assertEqual(DOCUMENT_KEYS, {'name', 'media_type', 'size', 'kind', 'original_url', 'view_url',
                                         'view_media_type', 'converted', 'view_round'})
        for name, doc in docs.items():
            with self.subTest(name):
                self.assertEqual(set(doc), ENCOUNTER_KEYS)
                self.assertEqual(set(doc['document']), DOCUMENT_KEYS)
                self.assertIn(doc['document']['view_media_type'], ('application/pdf', 'text/plain', None))
                self.assertIs(type(doc['document']['converted']), bool)
                # I1-12: the round whose conversion a Word document's view serves, else none
                self.assertEqual(doc['document']['view_round'],
                                 doc['round']['number'] if doc['document']['converted'] else None)
                self.assertEqual(doc['document']['view_url'] is None, doc['document']['view_media_type'] is None)
                self.assertRegex(doc['id'], UUID)
                self.assertIn(doc['state'], STATES)
                self.assertTrue(doc['title'].startswith('Synthetic '))
                for code in doc['codes']:
                    self.assertEqual(set(code), CODE_KEYS)
        self.assertEqual({doc['state'] for doc in docs.values()}, STATES - {'stopped'})
        # a Word document viewed as the PDF it was converted to, and the earlier review of one never converted
        self.assertEqual([(doc['document']['view_media_type'], doc['document']['converted'])
                          for doc in (docs['encounter-word.json'], docs['encounter-earlier.json'])],
                         [('application/pdf', True), (None, False)])

    def test_session_and_list_fixtures_have_exactly_the_contract_keys(self):
        for name in ('session.json', 'session-agent.json'):
            self.assertEqual(set(_customer(name)), SESSION_KEYS, name)
        self.assertEqual(_customer('session-agent.json')['user']['actor_kind'], 'agent')
        rows = _customer('encounters.json')['encounters']
        self.assertEqual({row['id'] for row in rows}, {doc['id'] for doc in self.encounters().values()})
        for row in rows:
            self.assertEqual(set(row), ROW_KEYS, row['id'])

    def test_the_list_fixtures_are_a_first_page_with_its_total_and_each_rows_opens_pdf(self):
        # release 2 (R2-19, R2-16, R2-24): a list answer is one page - its rows, the next page's cursor (none: the whole
        # list is on it) and the list's total - and a row says opens_pdf when its document's first stored file is a PDF
        # of at most 1 MiB, which is what each encounter fixture's document block shows
        self.assertEqual(set(CONTRACT['list']['keys']), {'encounters', 'next', 'total', 'workspace'})
        listing = _customer('encounters.json')
        self.assertEqual(set(listing), set(CONTRACT['list']['keys']))
        self.assertEqual((listing['next'], listing['total']), (None, len(listing['encounters'])))
        documents = {doc['id']: doc['document'] for doc in self.encounters().values()}
        for row in listing['encounters']:
            document = documents[row['id']]
            with self.subTest(row['id']):
                self.assertIs(row['opens_pdf'], document['kind'] == 'upload' and document['media_type'] == LIST_ROW_PDF_MEDIA_TYPE
                              and document['size'] <= 1024 * 1024)
        self.assertEqual({row['opens_pdf'] for row in listing['encounters']}, {True, False})
        session = _customer('session.json')['workspace']['id']  # the practice the page was read in (I1-2)
        self.assertEqual(listing['workspace'], session)
        self.assertEqual(_customer('encounters-empty.json'), {'encounters': [], 'next': None, 'total': 0, 'workspace': session})

    def test_every_code_row_names_its_line(self):
        # the fix pass, section 1: the coding review's codes are lines L1..Ln in its order, the codes the second check
        # added are M1..Mk after them; a decision names its line, so one code may stand on two lines
        repeated = 0
        for name, doc in self.encounters().items():
            with self.subTest(name):
                lines = [code['line'] for code in doc['codes']]
                listed = [line for line in lines if line.startswith('L')]
                added = [line for line in lines if line.startswith('M')]
                self.assertEqual(lines, listed + added)
                self.assertEqual(listed, [f'L{n}' for n in range(1, len(listed) + 1)])
                self.assertEqual(added, [f'M{n}' for n in range(1, len(added) + 1)])
                for code in doc['codes']:
                    self.assertEqual(code['line'].startswith('M'), code['second_check']['reason'] in ADDED_SENTENCES)
                    # units as the coding review wrote them: a whole number, 0 included, or null (not given)
                    self.assertTrue(code['units'] is None or (type(code['units']) is int and code['units'] >= 0))
                codes = [code['code'] for code in doc['codes']]
                repeated += len(codes) - len(set(codes))
        self.assertGreaterEqual(repeated, 1, 'a fixture lists one code on two lines')
        same = _customer('encounter-same-code.json')
        self.assertEqual([(code['line'], code['code'], code['modifiers'], code['units']) for code in same['codes']
                          if code['code'] == '45380'], [('L3', '45380', [], 1), ('M1', '45380', ['XS'], None)])

    def test_the_fixtures_name_no_vendor_model_or_machinery(self):
        for path in sorted(CUSTOMER_FIXTURES.glob('*.json')):
            with self.subTest(path.name):
                found = [value for value in _strings(_customer(path.name)) if FORBIDDEN.search(value)]
                self.assertEqual(found, [])


class PdfLibraryTests(SimpleTestCase):
    """The PDF library the review page loads for a document viewed as a PDF: pinned, served by this site with its licence,
    loadable under the shell's policy (its modules as JavaScript, through Django and WhiteNoise, after collectstatic with
    the manifest storage the image builds with)."""

    def manifest(self):
        return json.loads((PDF_LIB / 'MANIFEST.json').read_text(encoding='utf-8'))

    def test_every_pinned_file_is_listed_with_its_checksum_and_nothing_else_is_there(self):
        manifest = self.manifest()
        self.assertEqual((manifest['schema'], manifest['name'], manifest['version'], manifest['build'], manifest['license']),
                         ('cpt-studio-third-party@2', 'pdfjs-dist', '6.5.438', 'legacy', 'Apache-2.0'))
        self.assertEqual(manifest['npm_integrity'], PDF_LIB_INTEGRITY)
        self.assertEqual([(item['name'], item['version'], item['license'], item['npm_integrity'], item['in']) for item in manifest['bundled']],
                         [('core-js', '3.51.0', 'MIT', COREJS_INTEGRITY, list(PDF_LIB_SCRIPTS[:2]))])
        listed = {item['path']: item for item in manifest['files']}
        present = {path.relative_to(PDF_LIB).as_posix() for path in PDF_LIB.rglob('*') if path.is_file()}
        self.assertEqual(present, set(listed) | {'MANIFEST.json'})
        for name, item in listed.items():
            with self.subTest(name):
                data = (PDF_LIB / name).read_bytes()
                self.assertEqual((len(data), hashlib.sha256(data).hexdigest()), (item['bytes'], item['sha256']))
                self.assertTrue(item['why'])
                # each file keeps its path in its package (the core-js licence is that package's own LICENSE)
                expected = ('core-js@3.51.0', 'package/LICENSE') if name == 'core-js-3.51.0/LICENSE' else ('pdfjs-dist@6.5.438', f'package/{name}')
                self.assertEqual((item['package'], item['npm_path']), expected)
        self.assertTrue((PDF_LIB / 'LICENSE').read_text(encoding='utf-8').startswith('\n                                 Apache License'))
        corejs = (PDF_LIB / 'core-js-3.51.0' / 'LICENSE').read_text(encoding='utf-8')
        self.assertTrue(corejs.startswith('Copyright (c) 2013–2025 Denis Pushkarev (zloirock.ru)\n'))
        self.assertIn('Permission is hereby granted, free of charge, to any person obtaining a copy', corejs)
        # the legacy build's two files (no modern build/), the two image decoders without WebAssembly and two standard
        # fonts: no source maps, no scripting sandbox, no WebAssembly, no renderer worker
        self.assertEqual(sorted(name for name in listed if not name.split('/')[-1].startswith('LICENSE')), [
            'legacy/build/pdf.min.mjs', 'legacy/build/pdf.worker.min.mjs', 'standard_fonts/FoxitDingbats.pfb',
            'standard_fonts/FoxitSymbol.pfb', 'wasm/jbig2_nowasm_fallback.js', 'wasm/openjpeg_nowasm_fallback.js'])
        self.assertFalse((PDF_LIB / 'build').exists())
        # the licence is of the core-js version the legacy build carries: each file's core-js record names it
        for name in PDF_LIB_SCRIPTS[:2]:
            with self.subTest(name):
                text = (PDF_LIB / name).read_text(encoding='utf-8')
                self.assertEqual(re.findall(r'\.versions=\[\]\)\)\.push\(\{version:"([0-9.]+)"', text), ['3.51.0'])

    def test_the_suite_pins_every_library_file_itself(self):
        # MANIFEST.json is read by the check above; this pin is the suite's own, so a library file changed together with
        # its manifest entry still fails here until PDF_LIB_DIGEST is changed too (D368 round 3, SEC-2)
        self.assertEqual(library_digest(PDF_LIB), PDF_LIB_DIGEST)
        self.assertEqual(len([path for path in PDF_LIB.rglob('*') if path.is_file()]), 14, 'the 13 listed files and the manifest')

    def test_the_library_evaluates_no_code_from_strings(self):
        for name in PDF_LIB_SCRIPTS:
            with self.subTest(name):
                text = (PDF_LIB / name).read_text(encoding='utf-8')
                # core-js's global lookup, once in each legacy file and nowhere else (see COREJS_GLOBAL_LOOKUP)
                self.assertEqual(text.count(COREJS_GLOBAL_LOOKUP), 1 if name.startswith('legacy/') else 0)
                rest = text.replace(COREJS_GLOBAL_LOOKUP, '')
                self.assertEqual([match.group(0) for match in CODE_FROM_STRINGS.finditer(rest)], [])
                self.assertNotIn('sourceMappingURL', text)
        # the allowance is that occurrence alone: the same text with one more call built from a string fails
        planted = (PDF_LIB / PDF_LIB_SCRIPTS[0]).read_text(encoding='utf-8').replace(
            COREJS_GLOBAL_LOOKUP, COREJS_GLOBAL_LOOKUP + ';Function("return 1")()', 1).replace(COREJS_GLOBAL_LOOKUP, '')
        self.assertEqual([match.group(0) for match in CODE_FROM_STRINGS.finditer(planted)], ['Function('])
        for unsafe in ('eval("1")', '(0,eval)("1")', 'globalThis.eval("1")', 'window["eval"]("1")', 'new Function("a")',
                       'Function("return 1")()', 'self.Function("return 1")()', "self['Function']('return 1')()",
                       '(0,Function)("return 1")()', 'Reflect.construct(Function,["return 1"])', 'Function.call(null,"return 1")',
                       'x.constructor("return this")', 'setTimeout("f()")', 'window.setTimeout("f()")', 'setInterval(`f()`)'):
            with self.subTest(unsafe):
                self.assertIsNotNone(CODE_FROM_STRINGS.search(unsafe))
        # round 5 (R3CS-7): the seven forms the round-4 refutation found missed - a tagged template, an optional call, a
        # name in brackets as a string literal - and the same-class forms its checker found, minified as the library is
        missed = ('Function`return this`', 'Function?.("return 1")', 'new Function`a`', 'x["constructor"]("return this")()',
                  'window["setTimeout"]("f()")', 'setTimeout`f()`', 'setTimeout?.("f()")')
        for unsafe in (*missed, 'Function?.call(null,"return this")()', 't.constructor?.("return this")()', 't.constructor`return this`()',
                       'var g=globalThis.Function?.("return this")();', 'o=new Function`return 1`;', "x['Function']('return 1')()",
                       'g=t["constructor"]("return this")();', 'self["setTimeout"]("t()",0);', "self['setInterval']('t()',9);",
                       'setTimeout?.("t()",0);', 'setInterval`t()`;', 'x[ "constructor" ] ?.( "return this" )'):
            with self.subTest(unsafe):
                self.assertIsNotNone(CODE_FROM_STRINGS.search(unsafe))
        # each planted in the worker's own text fails the assertion above
        worker = (PDF_LIB / PDF_LIB_SCRIPTS[1]).read_text(encoding='utf-8').replace(COREJS_GLOBAL_LOOKUP, '')
        for unsafe in missed:
            with self.subTest(planted=unsafe):
                self.assertNotEqual([match.group(0) for match in CODE_FROM_STRINGS.finditer(f'{worker};{unsafe}')], [])
        # what the comment names as unseen stays unseen: a value held under another name and called by it
        for unseen in ('var F=Function;F("return this")()', '[Function][0]("return this")()', '({f:Function}).f("return this")()',
                       'setTimeout(code)', 'x[name]("return this")'):
            with self.subTest(unseen=unseen):
                self.assertIsNone(CODE_FROM_STRINGS.search(unseen))
        # and what the library's own text holds that builds no code is not read as it
        for safe in ('Function.prototype.toString', 'r=e(Function.toString)', '"Function"===e(t)', 'getRaw("Function")',
                     'parseShadingFunction(e)', 'setTimeout(()=>{t()},0)', 'setTimeout(t.resolve,0)', 'new e.prototype.constructor(t)',
                     'isEvalSupported:!1'):
            with self.subTest(safe):
                self.assertIsNone(CODE_FROM_STRINGS.search(safe))

    def test_the_shell_policy_lets_the_library_run_with_no_eval_and_no_webassembly(self):
        csp = dict(part.strip().split(' ', 1) for part in views.INDEX_CSP.split(';'))
        self.assertEqual(csp['script-src'], "'self'", 'the module and its same-origin module worker (worker-src falls back to it)')
        self.assertEqual(csp['connect-src'], "'self'", 'the PDF from the view address')
        self.assertNotIn('worker-src', csp)
        self.assertNotIn('child-src', csp)
        self.assertNotIn('eval', views.INDEX_CSP, "neither 'unsafe-eval' nor 'wasm-unsafe-eval'")
        self.assertEqual(csp['frame-src'], "'self'", "the browser's own viewer, where the library cannot run")

    def test_collectstatic_with_the_manifest_storage_serves_the_library_as_javascript(self):
        # module scripts and module workers are refused when served as another type under nosniff
        with tempfile.TemporaryDirectory() as root, override_settings(STATIC_ROOT=Path(root) / 'static'):
            call_command('collectstatic', interactive=False, verbosity=0)
            html = render_to_string('studio/index.html', {'release': 'test-release'}, request=RequestFactory().get('/'))
            body = re.search(r'<body ([^>]*)>', html).group(1)
            named = dict(re.findall(r'data-pdf-(module|worker)="([^"]*)"', body))
            self.assertEqual(named, {'module': staticfiles_storage.url(f'{PDF_LIB_NAME}/legacy/build/pdf.min.mjs'),
                                     'worker': staticfiles_storage.url(f'{PDF_LIB_NAME}/legacy/build/pdf.worker.min.mjs')})
            for kind, address in named.items():
                with self.subTest(kind):
                    self.assertRegex(address, rf'^/static/{re.escape(PDF_LIB_NAME)}/legacy/build/pdf(\.worker)?\.min\.[0-9a-f]{{12}}\.mjs$')
            # what the worker asks for by name, two folders up from it (the page derives wasmUrl and standardFontDataUrl as
            # ../../wasm/ and ../../standard_fonts/ of the worker): the image decoders without WebAssembly and the fonts
            fallback = f'/static/{PDF_LIB_NAME}/wasm/openjpeg_nowasm_fallback.js'
            font = f'/static/{PDF_LIB_NAME}/standard_fonts/FoxitDingbats.pfb'
            self.assertEqual((urljoin(named['worker'], '../../wasm/openjpeg_nowasm_fallback.js'),
                              urljoin(named['worker'], '../../standard_fonts/FoxitDingbats.pfb')), (fallback, font))
            for address, kind in ((named['module'], 'text/javascript'), (named['worker'], 'text/javascript'),
                                  (fallback, 'text/javascript'), (font, '')):
                with self.subTest(address):
                    response = self.client.get(address)
                    self.assertEqual(response.status_code, 200)
                    if kind:
                        self.assertEqual(response['Content-Type'].split(';')[0], kind)
                    self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
                    data = b''.join(response.streaming_content) if response.streaming else response.content
                    source = PDF_LIB / address.split(f'{PDF_LIB_NAME}/', 1)[1]
                    if source.exists():
                        self.assertEqual(data, source.read_bytes())
                    else:  # a hashed name: the same bytes as the file it names
                        original = re.sub(r'\.[0-9a-f]{12}(\.mjs)$', r'\1', address.split(f'{PDF_LIB_NAME}/', 1)[1])
                        self.assertEqual(data, (PDF_LIB / original).read_bytes())


class StaticHeaderTests(SimpleTestCase):
    """Every static file - the PDF library's module worker above all, which takes its policy from its own script's
    response and parses the uploaded document - carries the site's security headers, its policy with base-uri 'none'
    (studio.access.SecurityHeadersMiddleware.STATIC_CSP, which wraps WhiteNoise), and keeps WhiteNoise's caching; pages and
    data keep theirs; and the dev preview serves the library with exactly the site's headers (D368 round 3, SEC-1).
    Through the full middleware stack, after collectstatic with the manifest storage the image builds with."""

    REQUIRED = {'default-src': "'self'", 'script-src': "'self'", 'connect-src': "'self'", 'object-src': "'none'",
                'base-uri': "'none'"}
    # what a response's transport adds and its validators (the file's time): not the headers held equal
    VOLATILE = {'date', 'etag', 'last-modified', 'connection', 'keep-alive', 'transfer-encoding'}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._root = tempfile.TemporaryDirectory()
        cls._static = override_settings(STATIC_ROOT=Path(cls._root.name) / 'static')
        cls._static.enable()
        call_command('collectstatic', interactive=False, verbosity=0)

    @classmethod
    def tearDownClass(cls):
        cls._static.disable()
        cls._root.cleanup()
        super().tearDownClass()

    def policy(self, response):
        return dict(part.strip().split(' ', 1) for part in response['Content-Security-Policy'].split(';'))

    def test_the_site_headers_wrap_whitenoise(self):
        order = settings.MIDDLEWARE
        self.assertLess(order.index('studio.access.SecurityHeadersMiddleware'), order.index('whitenoise.middleware.WhiteNoiseMiddleware'))
        self.assertEqual(SecurityHeadersMiddleware.STATIC_CSP,
                         SecurityHeadersMiddleware.CSP.replace("base-uri 'self'", "base-uri 'none'"))

    def test_static_files_carry_the_site_policy_and_keep_their_caching(self):
        hashed = {name: staticfiles_storage.url(name) for name in (
            f'{PDF_LIB_NAME}/legacy/build/pdf.worker.min.mjs', f'{PDF_LIB_NAME}/legacy/build/pdf.min.mjs', 'studio/app.js',
            'studio/styles.css', 'studio/favicon.svg')}
        unhashed = [f'/static/{PDF_LIB_NAME}/legacy/build/pdf.worker.min.mjs', f'/static/{PDF_LIB_NAME}/wasm/jbig2_nowasm_fallback.js',
                    f'/static/{PDF_LIB_NAME}/standard_fonts/FoxitDingbats.pfb']
        for address in [*hashed.values(), *unhashed]:
            with self.subTest(address):
                response = self.client.get(address)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Security-Policy'], SecurityHeadersMiddleware.STATIC_CSP)
                policy = self.policy(response)
                for directive, value in self.REQUIRED.items():
                    self.assertEqual(policy[directive], value, directive)
                self.assertNotIn('eval', response['Content-Security-Policy'])
                caching = response['Cache-Control']
                self.assertNotIn('no-store', caching)
                self.assertEqual(caching, 'max-age=315360000, public, immutable' if address in hashed.values() else 'max-age=60, public')
                self.assertEqual((response['X-Content-Type-Options'], response['X-Robots-Tag'], response['Cross-Origin-Opener-Policy']),
                                 ('nosniff', 'noindex, nofollow', 'same-origin'))
                self.assertNotIn('X-Frame-Options', response)
        worker = self.client.get(hashed[f'{PDF_LIB_NAME}/legacy/build/pdf.worker.min.mjs'], HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual((worker['Content-Encoding'], worker['Content-Security-Policy']), ('gzip', SecurityHeadersMiddleware.STATIC_CSP))
        # a /static/ address with no file is Django's 404: the static policy, and nothing cached by force
        with self.assertLogs('django.request', 'WARNING'):
            missing = self.client.get('/static/studio/no-such-file.js')
        self.assertEqual((missing.status_code, missing['Content-Security-Policy']), (404, SecurityHeadersMiddleware.STATIC_CSP))

    def test_the_librarys_retry_addresses_are_served_alike(self):
        # the viewer loads the library again at ?attempt=N after a failure or its 20 s limit (D368 round 3, L1): the same
        # bytes as the file, its type, its immutable caching and the static policy, for the module and its worker alike
        def body(response):
            return b''.join(response.streaming_content) if response.streaming else response.content
        for name in (f'{PDF_LIB_NAME}/legacy/build/pdf.min.mjs', f'{PDF_LIB_NAME}/legacy/build/pdf.worker.min.mjs'):
            address = staticfiles_storage.url(name)
            with self.subTest(name):
                first = self.client.get(address)
                retry = self.client.get(f'{address}?attempt=2')
                self.assertEqual((first.status_code, retry.status_code), (200, 200))
                served, again = body(first), body(retry)  # a streamed body is read once
                self.assertEqual(served, (PDF_LIB / name.split(f'{PDF_LIB_NAME}/', 1)[1]).read_bytes())
                self.assertEqual(again, served)
                for header in ('Content-Type', 'Cache-Control', 'Content-Security-Policy', 'X-Content-Type-Options'):
                    self.assertEqual(retry[header], first[header], header)
                self.assertEqual((retry['Content-Security-Policy'], retry['Cache-Control']),
                                 (SecurityHeadersMiddleware.STATIC_CSP, 'max-age=315360000, public, immutable'))

    def test_pages_and_data_keep_their_own_headers(self):
        for address, status in (('/login/', 200), ('/api/session', 401)):
            with self.subTest(address):
                if status == 200:
                    response = self.client.get(address)
                else:
                    with self.assertLogs('django.request', 'WARNING'):
                        response = self.client.get(address)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response['Content-Security-Policy'], SecurityHeadersMiddleware.CSP)
                self.assertEqual((response['Cache-Control'], response['X-Frame-Options']), ('no-store', 'DENY'))

    def test_the_dev_preview_serves_the_library_with_the_sites_headers(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed; the dev preview needs it')
        # CPT_STUDIO_PREVIEW_PORT keeps a run to the port it was given; else one the system gives
        port = int(os.environ.get('CPT_STUDIO_PREVIEW_PORT') or 0)
        if not port:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
        server = subprocess.Popen([node, str(ROOT / 'ops' / 'dev_preview_server.cjs'), f'--port={port}'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertIn('CPT Studio dev preview', server.stdout.readline())
            # the preview renders the shell with its fixture session's specialty, as the site does (refutation N1-3-3)
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=30) as answer:
                shell = answer.read().decode('utf-8')
            self.assertIn('<select id="specialty" disabled><option>Gastroenterology</option></select>', shell)
            self.assertIn('data-specialty="Gastroenterology"', shell)
            listed = [item['path'] for item in json.loads((PDF_LIB / 'MANIFEST.json').read_text(encoding='utf-8'))['files']]
            for name in listed:
                with self.subTest(name):
                    address = f'/static/{PDF_LIB_NAME}/{name}'
                    site = self.client.get(address)
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}{address}', timeout=30) as answer:
                        preview = {key.lower(): value for key, value in answer.getheaders()}
                        body = answer.read()
                    expected = {key.lower(): value for key, value in site.items()}
                    self.assertEqual({key: value for key, value in preview.items() if key not in self.VOLATILE},
                                     {key: value for key, value in expected.items() if key not in self.VOLATILE})
                    self.assertEqual(body, (PDF_LIB / name).read_bytes())
        finally:
            server.terminate()
            server.wait(timeout=10)
            server.stdout.close()
            server.stderr.close()


class BrowserLogicTests(SimpleTestCase):
    def setUp(self):
        self.node = shutil.which('node')
        if self.node is None:
            self.skipTest('node is not installed; the browser logic tests need it')

    def test_browser_logic_unit_tests_pass(self):
        # node counts a test FILE that registers no tests (an early return, an emptied file) as one passing test,
        # so exit 0 and '# fail 0' prove nothing alone (round 3, evidence:7): every test the file declares must
        # pass, and a named test that guards the page's most exposed surface must be among them.
        # A skipped or todo test is declared and never asserts (round 3, evidence:4), so every declaration form is
        # counted and node must report none skipped and none todo.
        path = ROOT / 'tests' / 'frontend' / 'app.test.cjs'
        declared = len(re.findall(r'(?m)^test(?:\.(?:skip|todo|only))?\(', path.read_text(encoding='utf-8')))
        result = subprocess.run([self.node, '--test', '--test-reporter=tap', str(path)],
                                cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])

        def total(name):
            return [int(n) for n in re.findall(rf'(?m)^# {name} (\d+)$', result.stdout)]
        self.assertGreater(declared, 20)
        self.assertEqual(total('fail')[-1:], [0], result.stdout[-2000:])
        self.assertEqual((total('skipped')[-1:], total('todo')[-1:]), ([0], [0]), result.stdout[-2000:])
        self.assertTrue(total('pass') and total('pass')[-1] >= declared, (total('pass'), declared))
        # moved by the coding review page (2026-11-20): text the coding review writes reaches the customer for the
        # first time, so the guard is now the escaping of that text wherever the page draws it
        self.assertRegex(result.stdout, r'(?m)^ok \d+ - model-written text \(reasons, questions, notes, quotes\) is escaped '
                                        r'wherever it is drawn$')

    def test_scripts_parse(self):
        for path in (STATIC / 'app.js', STATIC / 'ops_session.js', STATIC / 'ops_second_factor.js', STATIC / 'session_news.js',
                     ROOT / 'ops' / 'dev_preview_server.cjs'):
            result = subprocess.run([self.node, '--check', str(path)], capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
