"""Frontend shell: templates render under the CSP, the approved stylesheet is intact,
the synthetic API fixtures stay exact, and the browser logic's own tests pass (node)."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timedelta, timezone as dt_timezone
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from studio import jobs, models, review, serializers
from studio.types import ClarificationSpec, ExtractionResult, canonical_json, sha256_json
from studio.validation import checks as validation_checks
from tests import test_harness2_api as h2
from tests.support import factories as f
from tests.support import pipeline_factories as pf

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
# The harness@1 API contract the website renders (HARNESS.md 7): encounter detail's harness and permissions, each
# proposal's harness fields, and the owner's trace.
PARTICIPANTS = ['corti', 'astra', 'fable']
PARTICIPANT_KEYS = {'name', 'label', 'vendor', 'model', 'state', 'detail', 'run_id', 'reused', 'codes', 'unverified_quotes',
                    'usage', 'usage_basis', 'estimated_cost_usd', 'returned_model'}
PARTICIPANT_STATES = {'not_configured', 'waiting', 'running', 'done', 'refused', 'failed', 'unknown', 'not_sent', 'blocked',
                      'stopped'}
RETRIEVAL_ITEM_KEYS = {'kind', 'source_key', 'release', 'label', 'value', 'page', 'section', 'text'}
TRACE_RUN_KEYS = {'id', 'state', 'purpose', 'adapter_version', 'endpoint', 'requested_model', 'returned_model', 'request_id',
                  'response_id', 'http_status', 'latency_ms', 'usage', 'usage_basis', 'estimated_cost_usd', 'request_sha256',
                  'response_sha256', 'response_bytes', 'created_at', 'finished_at', 'error', 'reused_from', 'reading'}
READING_KEYS = {'refused', 'problems', 'unverified_quotes', 'date_of_service', 'services', 'codes', 'not_coded', 'questions',
                'extraction_issues'}
# The harness@2 additions (HARNESS.md 12.6, as studio/serializers.py serves them) the website renders.
PEER_KEYS = {'state', 'detail', 'run_id', 'codes_added', 'unverified_quotes'}
PEER_STATES = {'waiting', 'running', 'stopped', 'done', 'refused', 'failed', 'unknown', 'not_sent', 'blocked',
               'not_configured'}
RETRIEVED_KEYS = {'ref', 'kind', 'source_key', 'release', 'effective_start', 'effective_end', 'tool'}
CANDIDATE_KEYS = {'id', 'clarification_id', 'fact', 'value', 'located_by', 'phase', 'phases', 'runs', 'spans', 'verified',
                  'why', 'attestation'}
CONFIRMATION_KEYS = {'id', 'clarification_id', 'scope', 'fact', 'family', 'proposal_key', 'value', 'spans', 'located_by',
                     'runs', 'confirmed_by', 'confirmed_by_kind', 'attestation', 'created_at', 'revision_number'}
EXCHANGE_KEYS = {'turn', 'state', 'http_status', 'latency_ms', 'usage', 'request_sha256', 'response_sha256',
                 'provider_request_id', 'response_id', 'error', 'tool_calls'}
TOOL_CALL_KEYS = {'call_id', 'tool', 'arguments', 'refs', 'result_sha256', 'executed_at'}
REVIEW_KEYS = {'provider', 'adapter_version', 'review_version', 'requested_model', 'returned_model', 'frozen_inputs',
               'answers', 'positions', 'additional_codes', 'references_used', 'problems', 'refused', 'unverified_quotes'}
# The exact sentence a confirmation carries with the candidate's value (HARNESS.md 11.3, 12.5), written out here.
ATTESTATION = 'I read this passage in the source document; it documents {value} for this encounter.'


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
                self.assertEqual(set(doc['permissions']), {'can_review', 'is_owner'})
                harness = doc['harness']
                self.assertEqual(set(harness), {'participants', 'reference_validation', 'clarification', 'final'})
                self.assertEqual([item['name'] for item in harness['participants']], PARTICIPANTS)
                for item in harness['participants']:
                    self.assertEqual(set(item), PARTICIPANT_KEYS)
                    self.assertIn(item['state'], PARTICIPANT_STATES)
                    self.assertTrue(item['run_id'] is None or UUID.match(item['run_id']))
                reference = harness['reference_validation']
                self.assertEqual(set(reference), {'state', 'codes_checked', 'passages', 'sources', 'not_connected'})
                self.assertIn(reference['state'], {'waiting', 'done', 'not_run'})
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
        self.assertEqual(set(trace), {'encounter', 'revision', 'participants', 'retrieval', 'reconciliation'})
        self.assertEqual((trace['encounter']['id'], trace['revision']['id']), (ready['id'], ready['revision']['id']))
        self.assertEqual([item['name'] for item in trace['participants']], PARTICIPANTS)
        located = 0
        for participant in trace['participants']:
            for run in participant['runs']:
                self.assertEqual(set(run), TRACE_RUN_KEYS)
                if run['reading'] is None:
                    continue
                self.assertEqual(set(run['reading']), READING_KEYS)
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
            self.assertEqual(set(row), {'code', 'family', 'status', 'proposed_by', 'positions', 'reference_check', 'approved'})

    def test_harness2_fixtures_carry_the_api_contract(self):
        docs = {name: _fixture(name) for name in HARNESS2_SCENARIOS}
        self.assertEqual({name: doc['harness']['phase'] for name, doc in docs.items()},
                         {'encounter-harness2-peer.json': 1, 'encounter-harness2-final.json': 2,
                          'encounter-harness2-confirmed.json': 2})
        for name, doc in docs.items():
            with self.subTest(name):
                text = doc['revision']['text']
                self.assertEqual(doc['permissions']['can_confirm'], doc['permissions']['can_review'])
                self.assertEqual(set(doc['harness']), {'participants', 'phase', 'reference_validation', 'clarification',
                                                       'final'})
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
                    self.assertTrue(final or not clarification['candidates'], 'only the final assessment has candidates')
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
        self.assertEqual([(c['fact'], [x['verified'] for x in c['candidates']]) for c in final['clarifications']],
                         [('extent', [True, False]), ('performed_status', [True, True, True]),
                          ('service_date', [True])])
        confirmed = docs['encounter-harness2-confirmed.json']
        [confirmation] = confirmed['confirmations']
        self.assertEqual((confirmation['fact'], confirmation['value'], confirmation['located_by'],
                          confirmation['confirmed_by']), ('extent', 'cecum', ['astra', 'fable'], 'Synthetic Reviewer'))
        snare = next(p for p in confirmed['assessment']['proposals'] if p['code'] == '45385')
        self.assertEqual((snare['confirmed'], snare['status'], snare['decision_state']),
                         ([confirmation['id']], 'ready', 'undecided'))  # a confirmation approves nothing
        self.assertNotIn('extent', [c['fact'] for c in confirmed['clarifications']])

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


# --- harness@2 (HARNESS.md 11-12): the website's fixtures are the serializer's own output ------------------------------
#
# The encounter-harness2-*.json fixtures and trace-harness2-final.json are made here, by studio.serializers, from the
# rows harness@2 records (tests/test_harness2_api.py's Harness2Case: the real adapters' stored requests, replayed response
# bytes the real readers read, exchanges, tool calls, the assessments' participant entries and a confirmation recorded
# through the real endpoint), never written from API.md's prose. CPT_STUDIO_WRITE_FIXTURES=1 writes them again, with
# stable ids and times; otherwise the committed files must carry exactly the keys, at every level, that the serializer
# emits now, so a change to the API that the website was not built for fails here.

WRITE_FIXTURES = os.environ.get('CPT_STUDIO_WRITE_FIXTURES') == '1'
HARNESS2_SCENARIOS = {  # fixture -> (the uuid prefix of its scenario, its title)
    'encounter-harness2-peer.json': ('e2a00000', 'Colonoscopy while the peer reviews run'),
    'encounter-harness2-final.json': ('e2b00000', 'Colonoscopy after peer review'),
    'encounter-harness2-confirmed.json': ('e2c00000', 'Colonoscopy with a confirmed finding'),
}
HARNESS2_TRACE = 'trace-harness2-final.json'
UUID_TEXT = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
TIME_TEXT = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})')
FIXTURE_TIME = datetime(2026, 11, 1, 9, 0, tzinfo=dt_timezone.utc)
TERMINAL_JOBS = {models.Job.SUCCEEDED, models.Job.FAILED, models.Job.UNKNOWN, models.Job.CANCELLED}
PHASE1_JOBS = (models.Job.EXTRACT, models.Job.ANALYZE, models.Job.PREDICT, models.Job.ASTRA, models.Job.FABLE,
               models.Job.ASSESS)
PHASE2_JOBS = (models.Job.ASTRA_PEER, models.Job.FABLE_PEER, models.Job.ASSESS)


def shape(value, path=''):
    """Every (path, type) a JSON value carries - the keys at every level ('[]' for a list's items) and each leaf's type -
    so two payloads compare by their shape, never by their ids, times or hashes."""
    if isinstance(value, dict):
        out = {(path or '.', 'object')}
        for key, item in value.items():
            out |= shape(item, f'{path}.{key}')
        return out
    if isinstance(value, list):
        out = {(path or '.', 'array')}
        for item in value:
            out |= shape(item, f'{path}[]')
        return out
    return {(path or '.', type(value).__name__)}


def candidate_id(question_id, candidate):
    """A candidate's id as studio.candidates computes it: 16 hex of the sha256 of (question id, fact, value, its spans,
    the participants that located it)."""
    identity = canonical_json([question_id, candidate['fact'], candidate['value'],
                               [[span['start'], span['end']] for span in candidate['spans']],
                               sorted(candidate['located_by'])])
    return hashlib.sha256(identity).hexdigest()[:16]


class StableIds:
    """Stable ids and times for the generated fixtures: each uuid of a scenario becomes <prefix>-0000-4000-8000-<n> in the
    order it first appears, each distinct time FIXTURE_TIME plus its rank among all of them (their order kept), and each
    candidate id is computed again from its question's new id, exactly as studio.candidates computes it."""

    def __init__(self, texts):
        found = sorted({datetime.fromisoformat(value.replace('Z', '+00:00')): value
                        for text in texts for value in TIME_TEXT.findall(text)}.items())
        self.times = {}
        for rank, (_, value) in enumerate(found):
            self.times.setdefault(value, (FIXTURE_TIME + timedelta(seconds=rank)).strftime('%Y-%m-%dT%H:%M:%SZ'))
        self.uuids = {}

    def __call__(self, text, prefix):
        def uuid_of(match):
            value = match.group(0)
            if value not in self.uuids:
                count = sum(1 for known in self.uuids.values() if known.startswith(prefix)) + 1
                self.uuids[value] = f'{prefix}-0000-4000-8000-{count:012x}'
            return self.uuids[value]
        data = json.loads(TIME_TEXT.sub(lambda m: self.times[m.group(0)], UUID_TEXT.sub(uuid_of, text)))
        for clarification in data.get('clarifications') or [] if isinstance(data, dict) else []:
            for candidate in clarification.get('candidates') or []:
                candidate['id'] = candidate_id(clarification['id'], candidate)
        return data


@override_settings(ASTRA_MODE='replay', FABLE_MODE='replay')
class Harness2FixtureTests(h2.Harness2Case):
    """Three encounters as harness@2 records them, serialized: one whose peer reviews are running (assess #1 current,
    Astra's peer stage in flight, Fable's waiting), one after both peer reviews (assess #2, three open questions with their
    candidates), and one whose extent question a reviewer confirmed, with the re-assessment that read it."""

    def setUp(self):  # the parent's setUp builds one encounter; these tests build each scenario as the pipeline records it
        self.ws = f.workspace()
        self.owner = self.person('owner', 'Synthetic Owner', models.Membership.OWNER)
        self.reviewer = self.person('reviewer', 'Synthetic Reviewer', models.Membership.REVIEWER)

    def person(self, username, label, role):
        user = models.User.objects.create_user(username=username, password='synthetic-pass-123!',
                                               actor_kind=models.User.HUMAN, display_name=label)
        models.Membership.objects.create(user=user, workspace=self.ws, role=role)
        return user

    # --- the rows, as Harness2Case.setUp records them --------------------------------------------------------------

    def first_reading_of(self, name):
        """Fable's first reading proposes 45385 only, so 45380 is first proposed by Fable in its peer review."""
        data = h2.first_reading(name)
        if name == 'fable':
            data['codes'] = [item for item in data['codes'] if item['code'] != '45380']
        return data

    def entry(self, name, *, peer=False):
        """Harness2Case's 12.3 entry, with the codes and not-coded items jobs._participant_record records: each with its
        first located quote, as the screen states a participant's positions from them."""
        record = jobs._participant_record(name, 'read', self.runs[name], self.readings[name], '')
        return {**super().entry(name, peer=peer), 'codes': record['codes'], 'not_coded': record['not_coded']}

    def peer_answer(self, name):
        answer = super().peer_answer(name)
        if name == 'fable':
            answer['additional_codes'] = [{'code': '45380', 'modifiers': [], 'units': 1, 'service_ids': ['s1'],
                                           'basis': 'The report records a polyp biopsied with cold forceps.',
                                           'evidence': [h2.RECTUM_QUOTE], 'confidence': 'medium'}]
        return answer

    def phase1(self, title):
        self.encounter = f.encounter(self.ws, self.reviewer, title=title)
        self.revision = f.pasted_revision(self.encounter, self.reviewer, h2.NOTE, extract=False)
        f.record(self.revision, ExtractionResult(status='ok', method='paste', text=h2.NOTE, pages=h2.PAGES))
        self.revision.refresh_from_db()
        self.context = pf.context(self.encounter, self.revision)
        self.corti = pf.provider_run(self.encounter, self.revision)
        self.now = timezone.now()
        self.adapters = {name: h2.ADAPTERS[name]('/nonexistent/never-read.env') for name in h2.ADAPTERS}
        self.runs, self.readings, self.requests = {}, {}, {}
        for name in h2.ADAPTERS:
            request = self.adapters[name].build_request(h2.NOTE, h2.PAGES, 'paste', None)
            data = (h2.astra_with if name == 'astra' else h2.fable_with)(self.first_reading_of(name))
            run = self.make_run(name, request, data, purpose=models.ProviderRun.INDEPENDENT)
            calls = [('cms_code_facts', {'codes': ['45385'], 'date_of_service': ''}, h2.FACTS_RESULT, [h2.FACT_REF])]
            self.exchanges(run, request.body, data, calls if name == 'astra' else [])
            self.runs[name], self.requests[name] = run, request
            self.readings[name] = self.adapters[name].read(request, data, frozenset(review.run_refs(run)))
        self.frozen = sorted([['astra', sha256_json(self.readings['astra'])], ['corti', self.corti.response_sha256],
                              ['fable', sha256_json(self.readings['fable'])],
                              ['revision', self.revision.text_sha256]])
        self.jobs(PHASE1_JOBS)
        self.first = self.save([self.entry(name) for name in h2.ADAPTERS], self.result_of(1))

    def phase2(self):
        self.peer_runs, self.reviews = {}, {}
        for name in h2.ADAPTERS:
            self.peer_review(name)
        self.jobs(PHASE2_JOBS)
        self.final = self.save([self.entry(name, peer=True) for name in h2.ADAPTERS], self.result_of(2))
        self.questions = {c.fact: c for c in self.final.clarifications.all()}

    def jobs(self, kinds, state=models.Job.SUCCEEDED):
        for kind in kinds:
            done = state in TERMINAL_JOBS
            pf.job(self.encounter, self.revision, kind, state, context=self.context,
                   provider_run=None if kind in (models.Job.EXTRACT, models.Job.ANALYZE) else self.corti,
                   started_at=timezone.now(), finished_at=timezone.now() if done else None)

    def save(self, entries, result):
        self.encounter.refresh_from_db()
        assessment = review.persist_assessment(
            encounter=self.encounter, revision=self.revision, context=self.context,
            routing_run=pf.routing(self.revision), provider_run=self.corti, result=result, participants=entries,
            retrieval=self.retrieval())
        review.refresh_state(self.encounter)
        return assessment

    def retrieval(self):
        """The reconciliation's own retrieval (Assessment.retrieval), never a participant's: synthetic stand-in text."""
        def passage(key, section, page, topic, value, body):
            text = f'SYNTHETIC FIXTURE TEXT, not CMS text: {body}'
            return {'source_key': 'cms-ncci-policy-manual-2026-ch6', 'release': 'Revision 1/1/2026', 'passage_key': key,
                    'section': section, 'page': page, 'topic': topic, 'topic_value': value,
                    'sha256': h2.sha(text.encode('utf-8')), 'text': text}

        def fact(code, field, value, **extra):
            return {'source_key': 'cms-pfs-rvu26d', 'release': 'RVU26D', 'effective': ['2026-10-01', '2026-12-31'],
                    'sha256': h2.sha(b'synthetic pfs file'), 'field': field, 'value': value, **extra}
        rule = passage('vi-c-3', 'Chapter VI, section C: Endoscopic Services', 'VI-14', 'pfs.endo_base', '',
                       'stands in for the rule that a surgical endoscopy includes the diagnostic endoscopy.')
        return [{'code': code, 'service_date': '2026-10-21',
                 'facts': [fact(code, 'status', 'A'), fact(code, 'mult_proc', '3'), fact(code, 'endo_base', '45378')],
                 'passages': [rule], 'lookups': [f'pfs {code} 2026-10-21', 'passages pfs.endo_base'],
                 'notes': ['NCCI procedure-to-procedure edits are not connected, so code pairs are not verified.']}
                for code in ('45385', '45380')]

    def result_of(self, phase, confirmation=None):
        """The assessment as the engine words it: Corti's snare removal, which every participant also proposed in its
        first reading, and the biopsy no decidable proposal carries - Astra's in its first reading and, in phase 2,
        Fable's after peer review - with Astra's peer-review code listed apart; held by the extent, the biopsy's status
        and the date of service. ``confirmation``: the extent, confirmed and read by a re-assessment."""
        extent = pf.clarification('extent', family='gi.colonoscopy', proposal_key='sel:0',
                                  question='Colonoscopy: confirm the furthest extent reached.',
                                  reason='The extent reached is not documented; the Colonoscopy profile requires it.')
        status = pf.clarification('performed_status', family='gi.colonoscopy', proposal_key='sel:1',
                                  question='Colonoscopy: confirm whether 45380 was performed at this encounter.',
                                  reason='Whether the biopsy was performed at this encounter is in doubt.')
        date_question = ClarificationSpec(scope='encounter', fact='service_date', question='Confirm the date of service.',
                                          reason='The date of service is in question.')
        proposers = ['astra', 'fable'] if phase == 2 else ['astra']
        phases = {'astra': 'independent', 'fable': 'peer_review'} if phase == 2 else {'astra': 'independent'}
        who = 'Astra (independent participant) and Fable after peer review' if phase == 2 else (
            'Astra (independent participant)')
        snare_support = {'origin': 'primary', 'proposed_by': ['corti', 'astra', 'fable'],
                         'phases': {'astra': 'independent', 'fable': 'independent'}}
        snare = pf.proposal('sel:0', '45385', ['was removed with a cold snare'], text=h2.NOTE,
                            status='needs_clarification', clarifications=(extent,),
                            rationale='A polyp removed with a cold snare is documented as performed on the service date.')
        checks = None
        if confirmation is not None:
            words = (f"confirmed from Astra's and Fable's located passage by {confirmation.confirmed_by.label()}")
            quoted = validation_checks.quoted_passages([span['text'] for span in confirmation.spans])
            item = (f'{validation_checks.fact_label("extent")} of 45385 (sel:0) = {confirmation.value}, {words} '
                    f'({quoted})')
            checks = (pf.check('extraction.status', 'pass', 'Text extraction'),
                      pf.check('service_date', 'pass', 'Service date documented'),
                      validation_checks.confirmations_applied_check([item]))
            snare = replace(snare, status='ready', clarifications=(),
                            rationale=f'{snare.rationale} Extent reached: {confirmation.value}, {words} ({quoted}).')
            snare_support = {**snare_support, 'confirmed': [str(confirmation.pk)]}
        snare = replace(snare, support=snare_support)
        biopsy = replace(pf.proposal('sel:1', '45380', [h2.RECTUM_QUOTE], text=h2.NOTE, status='needs_clarification',
                                     clarifications=(status,),
                                     rationale=f'Proposed by {who}; Corti did not propose this code.'),
                         support={'origin': 'participant', 'proposed_by': proposers, 'phases': phases})
        proposals = [snare, biopsy]
        if phase == 2:
            proposals.append(replace(
                pf.proposal('altp:0', '45381', [], text=h2.NOTE, bucket='alternative', checks=(),
                            exclusion_reason='Proposed by Astra after peer review, but not added as a proposal: its '
                                             'quote does not show the coded act. Alternatives cannot be approved.',
                            rationale='Proposed by Astra after peer review; not added as a proposal: its quote does '
                                      'not show the coded act. Informational only.'),
                support={'origin': 'participant', 'proposed_by': ['astra'], 'phases': {'astra': 'peer_review'}}))
        result = pf.result(*proposals, clarifications=(date_question,),
                           **({'encounter_checks': checks} if checks is not None else {}))
        # the documented-service reading: one colonoscopy whose extent the readers did not establish (the question)
        services = {'services': [{'id': 'S1', 'family': 'gi.colonoscopy', 'kind': 'colonoscopy', 'status': 'performed',
                                  'completion': 'complete', 'extent': '', 'acts': []}]}
        return replace(result, services=services, completeness={'covered': {'S1': ['45385', '45380']}})

    def confirm_extent(self):
        """The reviewer confirms the verified extent candidate through the real endpoint; the re-assessment it queues
        (built by the pipeline package) is recorded here as the assessment that read the confirmation."""
        candidate = self.verified('extent')
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            response = self.confirm('extent', candidate)
        self.assertEqual(response.status_code, 201, response.content)
        confirmation = models.FindingConfirmation.objects.get(clarification=self.questions['extent'])
        self.jobs((models.Job.ASSESS,))
        self.save([self.entry(name, peer=True) for name in h2.ADAPTERS], self.result_of(2, confirmation))
        return confirmation

    # --- the scenarios, serialized ------------------------------------------------------------------------------------

    def detail(self, user):
        self.encounter.refresh_from_db()
        membership = models.Membership.objects.get(user=user, workspace=self.ws)
        return serializers.encounter_detail(self.encounter, membership), serializers.encounter_summary(self.encounter)

    def scenarios(self):
        """{fixture: (prefix, detail JSON, list row JSON)} and the final scenario's trace, as the API serves them."""
        out = {}
        prefix, title = HARNESS2_SCENARIOS['encounter-harness2-peer.json']
        self.phase1(title)
        self.jobs((models.Job.ASTRA_PEER,), models.Job.RUNNING)
        review.refresh_state(self.encounter)
        out['encounter-harness2-peer.json'] = (prefix, *self.detail(self.reviewer))
        prefix, title = HARNESS2_SCENARIOS['encounter-harness2-final.json']
        self.phase1(title)
        self.phase2()
        out['encounter-harness2-final.json'] = (prefix, *self.detail(self.owner))
        trace = serializers.trace_json(self.encounter)
        prefix, title = HARNESS2_SCENARIOS['encounter-harness2-confirmed.json']
        self.phase1(title)
        self.phase2()
        self.confirm_extent()
        out['encounter-harness2-confirmed.json'] = (prefix, *self.detail(self.reviewer))
        return out, trace

    def test_the_harness2_fixtures_are_what_the_serializer_emits(self):
        generated, trace = self.scenarios()
        texts = {name: (json.dumps(detail, ensure_ascii=False), json.dumps(row, ensure_ascii=False))
                 for name, (_, detail, row) in generated.items()}
        stable = StableIds([text for pair in texts.values() for text in pair] + [json.dumps(trace)])
        details, rows = {}, {}
        for name, (prefix, _, _) in generated.items():
            details[name], rows[name] = stable(texts[name][0], prefix), stable(texts[name][1], prefix)
        details[HARNESS2_TRACE] = stable(json.dumps(trace, ensure_ascii=False),
                                         HARNESS2_SCENARIOS['encounter-harness2-final.json'][0])
        listing = _fixture('encounters.json')
        kept = [row for row in listing['encounters'] if row['id'] not in {row['id'] for row in rows.values()}]
        if WRITE_FIXTURES:
            for name, data in details.items():
                (FIXTURES / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
            new = sorted(rows.values(), key=lambda row: row['created_at'], reverse=True)
            (FIXTURES / 'encounters.json').write_text(
                json.dumps({'encounters': new + kept}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        for name, data in details.items():
            with self.subTest(name):
                committed = _fixture(name)
                self.assertEqual(sorted(shape(committed) ^ shape(data)), [],
                                 f'{name} no longer has the shape the serializer emits; regenerate it with '
                                 'CPT_STUDIO_WRITE_FIXTURES=1 and build the website for the change')
        listed = {row['id']: row for row in _fixture('encounters.json')['encounters']}
        for name, row in rows.items():
            with self.subTest(f'encounters.json {name}'):
                self.assertIn(row['id'], listed)
                self.assertEqual(sorted(shape(listed[row['id']]) ^ shape(row)), [])
                self.assertEqual(listed[row['id']]['state'], row['state'])
