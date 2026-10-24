"""Frontend shell: templates render under the CSP, the approved stylesheet is intact,
the synthetic API fixtures stay exact, and the browser logic's own tests pass (node)."""
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

ROOT = Path(settings.BASE_DIR)
STATIC = ROOT / 'studio' / 'static' / 'studio'
TEMPLATES = ROOT / 'studio' / 'templates' / 'studio'
FIXTURES = ROOT / 'tests' / 'fixtures' / 'api'
# The owner-approved styles.css (design package, 2026-10-23): its bytes must stay the file's prefix.
APPROVED_CSS_LENGTH = 32785
APPROVED_CSS_SHA256 = '4d68468c74e7b47d80472b9c95c6947189051089349b1559863ded7bd7b047e8'
PLAIN_STATIC = {**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
DETAIL_KEYS = {'id', 'title', 'state', 'state_label', 'created_at', 'created_by', 'permissions', 'revision', 'context',
               'routing', 'pipeline', 'provider_runs', 'assessment', 'clarifications', 'decisions', 'readiness',
               'reports', 'activity'}


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


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


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
        self.assertEqual(audit.script_sources, ['/static/studio/app.js'])

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

    def test_every_element_id_the_script_looks_up_exists(self):
        index_ids = set(_audit(self.render_index()).ids)
        script = (STATIC / 'app.js').read_text(encoding='utf-8')
        rendered_ids = set(re.findall(r'id="([A-Za-z][\w-]*)"', script)) | set(re.findall(r"\.id = '([A-Za-z][\w-]*)'", script))
        looked_up = set()
        for selector in re.findall(r"\$\$?\('([^']*)'", script):
            looked_up.update(re.findall(r'#([A-Za-z][\w-]*)', selector))
        missing = sorted(looked_up - index_ids - rendered_ids)
        self.assertEqual(missing, [])
        self.assertTrue({'uploadDialog', 'reviewDialog', 'contextDialog', 'addendumDialog', 'exportDialog', 'aboutDialog', 'toast'} <= index_ids)

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


class FixtureTests(SimpleTestCase):
    def detail_fixtures(self):
        return {path.name: _fixture(path.name) for path in sorted(FIXTURES.glob('encounter-*.json'))}

    def test_fixture_evidence_and_pages_are_exact_code_point_spans(self):
        for name, doc in self.detail_fixtures().items():
            if name == 'encounter-adversarial.json':
                continue
            with self.subTest(name):
                self.assertTrue(DETAIL_KEYS <= set(doc))
                text, pages = doc['revision']['text'], doc['revision']['pages']
                previous = 0
                for page in pages:
                    self.assertTrue(previous <= page['start'] <= page['end'] <= len(text))
                    previous = page['end']
                for proposal in (doc['assessment'] or {}).get('proposals', []):
                    self.assertTrue(UUID.match(proposal['id']))
                    for span in proposal['evidence']:
                        self.assertEqual(text[span['start']:span['end']], span['text'])
                        self.assertTrue(span['exact'])
                for fact in doc['context']['facts'].values():
                    for span in fact['evidence']:
                        self.assertEqual(text[span['start']:span['end']], span['text'])
                self.assertIn('SYNTHETIC TEST DOCUMENT', text or 'SYNTHETIC TEST DOCUMENT')

    def test_adversarial_fixture_keeps_its_deliberate_defects(self):
        doc = _fixture('encounter-adversarial.json')
        text = doc['revision']['text']
        spans = doc['assessment']['proposals'][0]['evidence']
        inexact = [span for span in spans if not span['exact'] or text[span['start']:span['end']] != span['text']]
        self.assertEqual(len(inexact), 3)
        self.assertIn('<img', doc['title'])
        self.assertTrue(any(ord(ch) > 0xFFFF for ch in text), 'astral characters exercise code-point offsets')

    def test_list_fixture_matches_the_detail_fixtures(self):
        details = {doc['id']: doc for doc in self.detail_fixtures().values()}
        rows = _fixture('encounters.json')['encounters']
        self.assertEqual({row['id'] for row in rows}, set(details))
        for row in rows:
            self.assertEqual(row['state'], details[row['id']]['state'])

    def test_session_fixtures_label_agent_users(self):
        agent, human = _fixture('session-agent.json'), _fixture('session.json')
        self.assertEqual(agent['user']['actor_kind'], 'agent')
        self.assertTrue(agent['user']['label'].endswith('(automated agent)'))
        self.assertEqual(human['user']['actor_kind'], 'human')
        self.assertTrue(agent['synthetic_only'] and human['synthetic_only'])


class BrowserLogicTests(SimpleTestCase):
    def setUp(self):
        self.node = shutil.which('node')
        if self.node is None:
            self.skipTest('node is not installed; the browser logic tests need it')

    def test_browser_logic_unit_tests_pass(self):
        # node counts a test FILE that registers no tests (an early return, an emptied file) as one passing test,
        # so exit 0 and '# fail 0' prove nothing alone (round 3, evidence:7): every test the file declares must
        # pass, and a named test that guards an agent-review label must be among them.
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
        self.assertRegex(result.stdout, r'(?m)^ok \d+ - an agent reinstatement behind a human decision labels the '
                                        r'reviewed export as agent review$')

    def test_scripts_parse(self):
        for path in (STATIC / 'app.js', ROOT / 'ops' / 'dev_preview_server.cjs'):
            result = subprocess.run([self.node, '--check', str(path)], capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
