"""Frontend shell: templates render under the CSP, the approved stylesheet is intact, the customer page's synthetic
fixtures carry the customer contract (client contract customer-2026-11-22, the build specification's section 6 with the
fix passes' line identity, decision ids and download rounds, as ops/verification/customer-contract.json holds it), and
the browser logic's own tests pass (node)."""
import hashlib
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from studio import customer

ROOT = Path(settings.BASE_DIR)
STATIC = ROOT / 'studio' / 'static' / 'studio'
TEMPLATES = ROOT / 'studio' / 'templates' / 'studio'
CUSTOMER_FIXTURES = ROOT / 'tests' / 'fixtures' / 'customer'
# The owner-approved styles.css (design package, 2026-10-23): its bytes must stay the file's prefix.
APPROVED_CSS_LENGTH = 32785
APPROVED_CSS_SHA256 = '4d68468c74e7b47d80472b9c95c6947189051089349b1559863ded7bd7b047e8'
PLAIN_STATIC = {**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
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
    def render_index(self):
        return render_to_string('studio/index.html', {'release': 'test-release'}, request=RequestFactory().get('/'))

    def test_index_renders_static_paths_and_a_csrf_token_from_the_request_alone(self):
        html = self.render_index()
        for path in ('/static/studio/styles.css', '/static/studio/app.js', '/static/studio/favicon.svg'):
            self.assertIn(path, html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertNotRegex(html, r'\{[%{]')

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
        self.assertEqual(audit.script_sources, [])
        self.assertEqual(audit.handlers, [])
        self.assertEqual(audit.external, [])

    def test_login_without_an_error_shows_no_alert(self):
        html = render_to_string('studio/login.html', {'error': '', 'next': '/'}, request=RequestFactory().get('/login/'))
        self.assertNotIn('role="alert"', html)


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
        self.assertIn("const CLIENT_VERSION = 'customer-2026-11-22';", script)
        self.assertRegex(script, r'\[CLIENT_HEADER\]: CLIENT_VERSION')


class CustomerFixtureTests(SimpleTestCase):
    """The customer page's fixtures (tests/fixtures/customer), which its node tests and ops/dev_preview_server.cjs read:
    hand-made, synthetic, and shaped exactly as section 6 serves the customer contract."""

    def encounters(self):
        return {path.name: _customer(path.name) for path in sorted(CUSTOMER_FIXTURES.glob('encounter-*.json'))}

    def test_every_encounter_fixture_has_exactly_the_contract_keys(self):
        docs = self.encounters()
        self.assertEqual(len(docs), 11)
        self.assertEqual(DOCUMENT_KEYS, {'name', 'media_type', 'size', 'kind', 'original_url', 'view_url',
                                         'view_media_type', 'converted'})
        for name, doc in docs.items():
            with self.subTest(name):
                self.assertEqual(set(doc), ENCOUNTER_KEYS)
                self.assertEqual(set(doc['document']), DOCUMENT_KEYS)
                self.assertIn(doc['document']['view_media_type'], ('application/pdf', 'text/plain', None))
                self.assertIs(type(doc['document']['converted']), bool)
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
        for path in (STATIC / 'app.js', ROOT / 'ops' / 'dev_preview_server.cjs'):
            result = subprocess.run([self.node, '--check', str(path)], capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
