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

from studio.types import canonical_json

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
# The OPERATOR contract (HARNESS.md 7, 12.6; CORE-UX-DESIGN.md 5): encounter detail's harness and permissions, each
# proposal's harness fields, the provider runs and the trace - the operator serializer's own keys, served at
# /ops/api/encounters/<id> and /ops/api/encounters/<id>/trace to platform operators and rendered by the operator console
# (studio/operator/ops.js, tests/operator/ops.test.cjs), which tests.test_harness_api.FrontendContractTests pins against
# the real /ops/ API (refutation r1 FG-5: these had drifted from it, so a fixture taken from the real API was rejected,
# and no frontend test could see a key the API serves). The fixtures in tests/fixtures/api are operator payloads. The
# CUSTOMER contract served at /api/ is CORE-UX-DESIGN.md 7's, pinned key by key by tests.test_customer_surface
# (assert_contract), with its own fixtures in tests/fixtures/customer (tests.test_customer_fixtures).
PARTICIPANTS = ['corti', 'astra', 'fable']
PARTICIPANT_KEYS = {'name', 'label', 'vendor', 'model', 'state', 'detail', 'run_id', 'reused', 'codes',
                    'unlisted_codes', 'unverified_quotes', 'usage', 'usage_basis', 'estimated_cost_usd',
                    'returned_model', 'peer', 'references', 'peer_references'}
PARTICIPANT_STATES = {'not_configured', 'waiting', 'running', 'done', 'refused', 'failed', 'unknown', 'not_sent', 'blocked',
                      'stopped'}
HARNESS_KEYS = {'participants', 'phase', 'reference_validation', 'clarification', 'final'}
PERMISSION_KEYS = {'can_review', 'is_owner', 'can_confirm'}
REFERENCE_VALIDATION_KEYS = {'state', 'detail', 'codes_checked', 'passages', 'sources', 'not_connected'}
# 'failed': the assessment's retrieval failed, said with its note as the detail (refutation r1 parity-1)
# 'not_verified': no installed CMS file applied to the service date (refutation round 2, truth-3), as the harness@2
# fixtures now serve it - their document's two dates of service disagree, so none is established (refutation round 3,
# falsegreen-11: the fixtures' rows are the engine's)
REFERENCE_VALIDATION_STATES = {'waiting', 'done', 'failed', 'not_run', 'not_verified'}
RETRIEVAL_ITEM_KEYS = {'kind', 'source_key', 'release', 'label', 'value', 'page', 'section', 'text'}
PROVIDER_RUN_KEYS = {'id', 'provider', 'mode', 'state', 'http_status', 'latency_ms', 'usage', 'usage_basis',
                     'request_sha256', 'response_sha256', 'reused_from', 'error', 'reconciled', 'created_at', 'purpose',
                     'scope_items', 'requested_model', 'returned_model'}
TRACE_KEYS = {'encounter', 'revision', 'participants', 'assessments', 'retrieval', 'reconciliation'}
TRACE_RUN_KEYS = {'id', 'state', 'sent', 'mode', 'purpose', 'run_identity', 'authorization_ref', 'requested_by',
                  'adapter_version', 'endpoint', 'requested_model', 'returned_model', 'request_id', 'response_id',
                  'http_status', 'latency_ms', 'usage', 'usage_basis', 'estimated_cost_usd', 'request_sha256',
                  'response_sha256', 'response_bytes', 'created_at', 'finished_at', 'error', 'reused_from',
                  'reconciled', 'reading', 'review', 'exchanges'}
READING_KEYS = {'refused', 'problems', 'unverified_quotes', 'date_of_service', 'services', 'codes', 'not_coded', 'questions',
                'extraction_issues', 'references_used'}
# moved by refutation round 5 (R5-ACCOUNT, the session's D12): a row also serves listed_by, the participants that only
# listed a participant's alternative's code with no quote found verbatim, never among its proposers
RECONCILIATION_ROW_KEYS = {'code', 'family', 'bucket', 'status', 'proposed_by', 'listed_by', 'positions',
                           'reference_check', 'approved'}
# The harness fixtures (tests/fixtures/api) were written at b4655e634, before these keys existed. What each shape still
# lacks is stated here rather than accepted silently, until the website package regenerates the fixtures from the
# serializer's output: a regenerated fixture fails these tests until its entry is emptied (refutation r1 FG-5).
# Refutation round 2 (FG2-5) found it still open: regenerated, they become harness@2 payloads, and the tests that draw
# them as payloads served before harness@2 must then build those payloads themselves - left for after the round-2 merge
# (R2-WORDING's report). The participants row's unlisted_codes (truth-11) is the latest key they lack.
FIXTURE_LACKS = {
    'permissions': {'can_confirm'},
    'harness': {'phase'},
    'participant': {'peer', 'references', 'peer_references', 'unlisted_codes'},
    'trace': {'assessments'},
    'trace_run': {'sent', 'mode', 'run_identity', 'authorization_ref', 'requested_by', 'reconciled', 'review',
                  'exchanges'},
    'reading': {'references_used'},
    'reconciliation_row': {'bucket', 'listed_by'},
    'reference_validation': {'detail'},
}
# The harness@2 additions (HARNESS.md 12.6, as studio/serializers.py serves them) the website renders.
PEER_KEYS = {'state', 'detail', 'run_id', 'codes_added', 'unverified_quotes'}
PEER_STATES = {'waiting', 'running', 'stopped', 'done', 'refused', 'failed', 'unknown', 'not_sent', 'blocked',
               'not_configured'}
RETRIEVED_KEYS = {'ref', 'kind', 'source_key', 'release', 'effective_start', 'effective_end', 'tool'}
CANDIDATE_KEYS = {'id', 'clarification_id', 'fact', 'value', 'located_by', 'phase', 'phases', 'runs', 'spans',
                  'sentences', 'verified', 'why', 'attestation'}
CONFIRMATION_KEYS = {'id', 'clarification_id', 'scope', 'fact', 'family', 'proposal_key', 'value', 'spans',
                     'located_by', 'runs', 'confirmed_by', 'confirmed_by_kind', 'attestation', 'created_at',
                     'revision_number', 'current_effect'}
EXCHANGE_KEYS = {'turn', 'state', 'http_status', 'latency_ms', 'usage', 'request_sha256', 'response_sha256',
                 'provider_request_id', 'response_id', 'error', 'tool_calls'}
TOOL_CALL_KEYS = {'call_id', 'tool', 'arguments', 'refs', 'result_sha256', 'executed_at'}
REVIEW_KEYS = {'provider', 'adapter_version', 'review_version', 'requested_model', 'returned_model', 'frozen_inputs',
               'answers', 'positions', 'additional_codes', 'references_used', 'problems', 'refused',
               'unverified_quotes'}
# The exact sentence a confirmation carries with the candidate's value (HARNESS.md 11.3, 12.5), written out here.
ATTESTATION = 'I read this passage in the source document; it documents {value} for this encounter.'


# harness@2's website fixtures (tests/test_frontend_harness2.py generates and checks them against the serializer)
HARNESS2_SCENARIOS = {  # fixture -> (the uuid prefix of its scenario, its title)
    'encounter-harness2-peer.json': ('e2a00000', 'Colonoscopy while the peer reviews run'),
    'encounter-harness2-final.json': ('e2b00000', 'Colonoscopy after peer review'),
    'encounter-harness2-confirmed.json': ('e2c00000', 'Colonoscopy with a confirmed finding'),
    'encounter-harness2-dormant.json': ('e2d00000', 'Colonoscopy after peer review, confirmation offered'),
}
# This release offers no reviewer confirmation (HARNESS.md 12.10, refutation round 3's D7): these two are made with
# STUDIO_OFFER_CONFIRMATIONS=True, as the dormant confirmation path serves them, for that path's rendering tests.
HARNESS2_DORMANT = ('encounter-harness2-confirmed.json', 'encounter-harness2-dormant.json')
HARNESS2_TRACE = 'trace-harness2-final.json'


def candidate_id(question_id, candidate):
    """A candidate's id as studio.candidates computes it: 16 hex of the sha256 of (question id, fact, value, its spans,
    the participants that located it)."""
    identity = canonical_json([question_id, candidate['fact'], candidate['value'],
                               [[span['start'], span['end']] for span in candidate['spans']],
                               sorted(candidate['located_by'])])
    return hashlib.sha256(identity).hexdigest()[:16]

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

    def test_harness_fixtures_carry_the_api_contract(self):
        # harness@1's payloads, as served before harness@2 (the website renders them as before); harness@2's below
        harnessed = {name: doc for name, doc in self.detail_fixtures().items()
                     if 'harness' in doc and 'phase' not in doc['harness']}
        self.assertTrue({'encounter-harness-ready.json', 'encounter-harness-degraded.json',
                         'encounter-processing.json'} <= set(harnessed))
        for name, doc in harnessed.items():
            with self.subTest(name):
                self.assertEqual(set(doc['permissions']), PERMISSION_KEYS - FIXTURE_LACKS['permissions'])
                harness = doc['harness']
                self.assertEqual(set(harness), HARNESS_KEYS - FIXTURE_LACKS['harness'])
                self.assertEqual([item['name'] for item in harness['participants']], PARTICIPANTS)
                for item in harness['participants']:
                    self.assertEqual(set(item), PARTICIPANT_KEYS - FIXTURE_LACKS['participant'])
                    self.assertIn(item['state'], PARTICIPANT_STATES)
                    self.assertTrue(item['run_id'] is None or UUID.match(item['run_id']))
                reference = harness['reference_validation']
                self.assertEqual(set(reference), REFERENCE_VALIDATION_KEYS - FIXTURE_LACKS['reference_validation'])
                self.assertIn(reference['state'], REFERENCE_VALIDATION_STATES)
                self.assertEqual(harness['clarification'], {'open': doc['open_clarifications']})
                self.assertEqual(harness['final'], {'state': doc['state'], 'label': doc['state_label']})
                for proposal in (doc['assessment'] or {}).get('proposals', []):
                    self.assertTrue(set(proposal['proposed_by']) <= set(PARTICIPANTS))
                    self.assertIn(proposal['reference_check']['state'], {'passed', 'attention', 'not_verified'})
                    for participant, position in proposal['participant_positions'].items():
                        self.assertIn(participant, PARTICIPANTS[1:])
                        self.assertEqual(set(position), {'position', 'detail', 'quote'})
                        self.assertIn(position['position'], {'proposed', 'not_proposed', 'advised_not_to_code', 'not_run'})
                        self.assertIn(position['quote'], doc['revision']['text'])  # a quote is the document's own text
                    for item in proposal['retrieval']:
                        self.assertEqual(set(item), RETRIEVAL_ITEM_KEYS)
                        self.assertIn(item['kind'], {'fact', 'passage'})

    def test_trace_fixture_carries_the_api_contract_and_quotes_the_document_exactly(self):
        trace, ready = _fixture('trace-harness-ready.json'), _fixture('encounter-harness-ready.json')
        text = ready['revision']['text']
        self.assertEqual(set(trace), TRACE_KEYS - FIXTURE_LACKS['trace'])
        self.assertEqual((trace['encounter']['id'], trace['revision']['id']), (ready['id'], ready['revision']['id']))
        self.assertEqual([item['name'] for item in trace['participants']], PARTICIPANTS)
        located = 0
        for participant in trace['participants']:
            for run in participant['runs']:
                self.assertEqual(set(run), TRACE_RUN_KEYS - FIXTURE_LACKS['trace_run'])
                if run['reading'] is None:
                    continue
                self.assertEqual(set(run['reading']), READING_KEYS - FIXTURE_LACKS['reading'])
                reading = run['reading']
                items = reading['services'] + reading['codes'] + reading['not_coded'] + reading['questions']
                quotes = [quote for item in items for quote in item['evidence']]
                self.assertEqual(sum(1 for quote in quotes if not quote['spans']), reading['unverified_quotes'])
                for quote in quotes:
                    for span in quote['spans']:
                        self.assertEqual(text[span['start']:span['end']], span['text'])
                        located += 1
        self.assertGreater(located, 5)
        for entry in trace['retrieval']:
            self.assertEqual(set(entry), {'code', 'service_date', 'facts', 'passages', 'lookups', 'notes'})
            for passage in entry['passages']:
                self.assertEqual(set(passage), {'source_key', 'release', 'passage_key', 'section', 'page', 'topic',
                                                'topic_value', 'sha256', 'text'})
                self.assertEqual(hashlib.sha256(passage['text'].encode('utf-8')).hexdigest(), passage['sha256'])
                self.assertTrue(passage['text'].startswith('SYNTHETIC FIXTURE TEXT, not CMS text'))
        self.assertEqual([row['code'] for row in trace['reconciliation']],
                         [proposal['code'] for proposal in ready['assessment']['proposals']])
        for row in trace['reconciliation']:
            self.assertEqual(set(row), RECONCILIATION_ROW_KEYS - FIXTURE_LACKS['reconciliation_row'])

    def test_harness2_fixtures_carry_the_api_contract(self):
        docs = {name: _fixture(name) for name in HARNESS2_SCENARIOS}
        self.assertEqual({name: doc['harness']['phase'] for name, doc in docs.items()},
                         {'encounter-harness2-peer.json': 1, 'encounter-harness2-final.json': 2,
                          'encounter-harness2-confirmed.json': 2, 'encounter-harness2-dormant.json': 2})
        for name, doc in docs.items():
            with self.subTest(name):
                text = doc['revision']['text']
                dormant = name in HARNESS2_DORMANT
                # moved by refutation round 3 (HARNESS.md 12.10): no member may confirm in this release; can_confirm is
                # can_review only on the dormant confirmation path, where this pin stood for every fixture
                self.assertEqual(doc['permissions']['can_confirm'], doc['permissions']['can_review'] and dormant)
                self.assertEqual(set(doc['harness']), {'participants', 'phase', 'reference_validation', 'clarification',
                                                       'final'})
                reference = doc['harness']['reference_validation']
                self.assertEqual(set(reference), REFERENCE_VALIDATION_KEYS)
                self.assertIn(reference['state'], REFERENCE_VALIDATION_STATES)
                # moved by refutation round 3 (falsegreen-11): 'not_verified' says why too (truth-3), as these
                # fixtures now serve it
                self.assertEqual(reference['detail'] != '', reference['state'] in ('failed', 'not_verified'),
                                 reference)
                rows = {row['name']: row for row in doc['harness']['participants']}
                self.assertEqual(list(rows), PARTICIPANTS)
                self.assertEqual(rows['corti']['peer'], {})
                for row in rows.values():
                    self.assertEqual(set(row), PARTICIPANT_KEYS | {'peer', 'references', 'peer_references'})
                    self.assertTrue(not row['peer'] or (set(row['peer']) == PEER_KEYS
                                                        and row['peer']['state'] in PEER_STATES), row['peer'])
                    for field in ('references', 'peer_references'):
                        retrieved = {item['ref'] for item in row[field]['retrieved']}
                        for item in row[field]['retrieved']:
                            self.assertEqual(set(item), RETRIEVED_KEYS)
                        for item in row[field]['used']:
                            # CPT Studio's check against that run's own tool calls: never shown as retrieved otherwise
                            self.assertEqual(set(item), {'ref', 'use', 'retrieved'})
                            self.assertEqual(item['retrieved'], item['ref'] in retrieved, item)
                final = doc['harness']['phase'] == 2
                for clarification in doc['clarifications']:
                    self.assertEqual(set(clarification) - {'candidates', 'confirmation'},
                                     {'id', 'scope', 'proposal_id', 'family', 'fact', 'question', 'reason', 'state'})
                    self.assertTrue(final or not clarification['candidates'],
                                    'only the final assessment has candidates')
                    # moved by refutation round 4 (HARNESS.md 12.10 as amended, the session's D8): this release serves
                    # no candidate at all, where it served each one unchecked, verified false with one fixed why
                    self.assertTrue(dormant or clarification['candidates'] == [], clarification['candidates'])
                    for candidate in clarification['candidates']:
                        self.assertEqual(set(candidate), CANDIDATE_KEYS)
                        self.assertEqual(candidate['clarification_id'], clarification['id'])
                        self.assertEqual(candidate['id'], candidate_id(clarification['id'], candidate))
                        for span in candidate['spans']:
                            self.assertEqual(text[span['start']:span['end']], span['text'])
                        self.assertTrue(set(candidate['located_by']) <= {'astra', 'fable'})
                        self.assertEqual(set(candidate['phases']), set(candidate['located_by']))
                        if candidate['verified']:
                            self.assertEqual((candidate['why'], candidate['attestation']),
                                             ('', ATTESTATION.format(value=candidate['value'])))
                        else:
                            self.assertTrue(candidate['why'] and candidate['attestation'] == '', candidate)
                for confirmation in doc['confirmations']:
                    self.assertEqual(set(confirmation), CONFIRMATION_KEYS)
                    self.assertEqual(confirmation['attestation'], ATTESTATION.format(value=confirmation['value']))
                    for span in confirmation['spans']:
                        self.assertEqual(text[span['start']:span['end']], span['text'])
                for proposal in doc['assessment']['proposals']:
                    self.assertTrue(set(proposal['phases'].values()) <= {'independent', 'peer_review'})
                    self.assertTrue(set(proposal['phases']) <= set(proposal['proposed_by']), proposal['phases'])
                    if proposal['bucket'] != 'alternative' and 'corti' not in proposal['proposed_by']:
                        self.assertIn('Corti did not propose this code.', proposal['rationale'])  # 11.4
        # each scenario shows what it is for
        peer = {row['name']: row['peer'] for row in docs['encounter-harness2-peer.json']['harness']['participants']}
        self.assertEqual((peer['astra']['state'], peer['fable']['state']), ('running', 'waiting'))
        final = docs['encounter-harness2-final.json']
        # moved by refutation round 3 (HARNESS.md 12.10): this release serves every candidate unchecked; the dormant
        # confirmation path's verified flags, which this pin held for the final fixture, are pinned on its own fixture
        # and by falsegreen-11: the questions are the engine's - 45385's extent, 45380's status and extent, the date -
        # where the biopsy the readers leave in doubt has no status candidate that the dormant path verifies
        # and moved by refutation round 4 (D8): it serves none, where it served them unchecked
        self.assertEqual([(c['fact'], [x['verified'] for x in c['candidates']]) for c in final['clarifications']],
                         [('extent', []), ('performed_status', []), ('extent', []), ('service_date', [])])
        dormant = docs['encounter-harness2-dormant.json']
        self.assertEqual([(c['fact'], [x['verified'] for x in c['candidates']]) for c in dormant['clarifications']],
                         [('extent', [True, False]), ('performed_status', [False, False, False]),
                          ('extent', [True, False]), ('service_date', [True])])
        # the same located passages either way: what the dormant path claimed about them is all that differs (moved by
        # refutation round 4, D8: this release serves none of the passages the dormant path offers)

        def passages(doc):
            return sorted((c['fact'], x['value'], x['located_by'], [span['text'] for span in x['spans']])
                          for c in doc['clarifications'] for x in c['candidates'])
        self.assertEqual(passages(final), [])
        self.assertTrue(passages(dormant))
        confirmed = docs['encounter-harness2-confirmed.json']
        [confirmation] = confirmed['confirmations']
        self.assertEqual((confirmation['fact'], confirmation['value'], confirmation['located_by'],
                          confirmation['confirmed_by']), ('extent', 'cecum', ['astra', 'fable'], 'Synthetic Reviewer'))
        snare = next(p for p in confirmed['assessment']['proposals'] if p['code'] == '45385')
        # moved by refutation round 3 (falsegreen-11): the engine's re-assessment reads the confirmed extent, and 45385
        # is still held on the encounter's own question, its date of service; a confirmation approves nothing
        self.assertEqual((snare['confirmed'], snare['status'], snare['decision_state']),
                         ([confirmation['id']], 'needs_clarification', 'undecided'))
        self.assertEqual([c['fact'] for c in confirmed['clarifications'] if c['proposal_id'] == snare['id']], [])
        self.assertIn('service_date', [c['fact'] for c in confirmed['clarifications']])

    def test_harness2_trace_fixture_carries_the_api_contract(self):
        trace, final = _fixture(HARNESS2_TRACE), _fixture('encounter-harness2-final.json')
        text = final['revision']['text']
        self.assertEqual(set(trace), {'encounter', 'revision', 'participants', 'assessments', 'retrieval',
                                      'reconciliation'})
        self.assertEqual(trace['encounter']['id'], final['id'])
        run_keys = TRACE_RUN_KEYS | {'sent', 'mode', 'run_identity', 'authorization_ref', 'requested_by', 'reconciled',
                                     'review', 'exchanges'}
        purposes = []
        for participant in trace['participants']:
            for run in participant['runs']:
                purposes.append((participant['name'], run['purpose']))
                self.assertEqual(set(run), run_keys)
                self.assertTrue(run['reading'] is None or run['review'] is None, 'a run has a reading or a review')
                for exchange in run['exchanges']:
                    self.assertEqual(set(exchange), EXCHANGE_KEYS)
                    for call in exchange['tool_calls']:
                        self.assertEqual(set(call), TOOL_CALL_KEYS)
                if run['review'] is not None:
                    self.assertEqual(set(run['review']), REVIEW_KEYS)
                    quotes = [quote for group in ('answers', 'positions', 'additional_codes')
                              for item in run['review'][group] for quote in item['evidence']]
                    for quote in quotes:
                        for span in quote['spans']:
                            self.assertEqual(text[span['start']:span['end']], span['text'])
        self.assertEqual(purposes, [('corti', 'primary'), ('astra', 'independent'), ('astra', 'peer_review'),
                                    ('fable', 'independent'), ('fable', 'peer_review')])
        self.assertEqual([(a['phase'], a['final'], a['current']) for a in trace['assessments']],
                         [(1, False, False), (2, True, True)])
        for assessment in trace['assessments']:
            self.assertEqual(set(assessment), {'id', 'created_at', 'current', 'phase', 'final', 'frozen'})
            self.assertEqual(sorted(name for name, _ in assessment['frozen']), ['astra', 'corti', 'fable', 'revision'])

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
