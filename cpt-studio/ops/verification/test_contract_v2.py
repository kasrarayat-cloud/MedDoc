"""The customer contract's FINAL-V2 amendment 1 keys and vocabulary (ops/verification/customer-contract.json; AMENDMENT-1.md
section 10's 6b row: "the contract's new keys and vocabulary (`updating`, the update block), the client version"), held
to the server's own sources and to the differential check of 11.3 (ops/verification/what_changed.py), whose output must
be a 'what_changed' the contract accepts. No Django, no database, no network.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops/verification -p 'test_*.py' -v
"""
import ast
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPS = HERE.parent
APP = OPS.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


sc = load('cpt_contract_v2_scan', OPS / 'scan_customer.py')
wc = load('cpt_contract_v2_what_changed', HERE / 'what_changed.py')
CONTRACT = json.loads((HERE / 'customer-contract.json').read_text(encoding='utf-8'))
ENCOUNTER = CONTRACT['encounter']['keys']


def literal(path, name):
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f'{name} is not a literal of {path}')


class AmendmentKeysTests(unittest.TestCase):
    def test_the_encounter_carries_the_four_new_keys_and_each_export_its_revision(self):
        for key in ('update', 'earlier_codes', 'what_changed', 'decision_history'):
            self.assertIn(key, ENCOUNTER, key)
        types = ENCOUNTER  # the encounter's own keys, each with its type
        self.assertEqual(types['update']['keys']['state']['enum'], ['updating', 'failed', 'stopped', 'paused',
                                                                    'being_confirmed'])
        self.assertEqual(types['update']['keys']['kind']['enum'], ['details', 'documentation', 'check'])  # A21: check
        self.assertEqual(types['what_changed']['keys']['decisions']['items']['keys']['outcome']['enum'],
                         ['kept', 'kept_then_cleared', 'kept_then_changed', 'cleared'])  # 6.2 step 4's four
        self.assertEqual(types['what_changed']['keys']['codes']['items']['keys']['change']['enum'],
                         ['added', 'removed', 'status', 'units', 'detail'])
        self.assertEqual(types['reports']['items']['keys']['revision'], 'integer')
        self.assertIn('retry_update', types['progress']['keys']['error']['keys']['action']['enum'])

    def test_updating_is_a_state_a_phase_and_a_label_of_the_vocabulary(self):
        vocabulary = CONTRACT['vocabulary']
        self.assertEqual(vocabulary['states']['updating'], 'Updating codes')  # 5.1's state label
        self.assertIn('updating', vocabulary['phases'])
        self.assertIn('updating', CONTRACT['types']['state']['enum'])
        self.assertIn('updating', ENCOUNTER['progress']['keys']['phase']['enum'])
        self.assertEqual(vocabulary['answer_after_update'], 'You can answer this once the codes are updated.')  # 5.1(3)

    def test_the_tools_name_the_servers_current_client_build(self):
        version = literal(APP / 'studio' / 'client_contract.py', 'VERSION')
        login = (OPS / 'verify_login.py').read_text(encoding='utf-8')
        self.assertIn(f"CLIENT_HEADER, CLIENT_VERSION = 'X-CPT-Studio-Client', '{version}'", login)
        browser = (OPS / 'verify_browser.cjs').read_text(encoding='utf-8')
        self.assertIn(f"const CLIENT_HEADERS = {{ 'X-CPT-Studio-Client': '{version}' }};", browser)

    def test_the_differential_checks_output_is_a_what_changed_the_contract_accepts(self):
        rows = {'schema': wc.ROWS_SCHEMA, 'fresh': True, 'current_assessment': 'N', 'current_context': 'C2',
                'assessments': {
                    'E': {'created_at': '2026-11-12T10:00:00+00:00', 'revision': 'r1', 'context': 'C1',
                          'engine_version': 'cpt-studio-validation@10', 'clarifications': [],
                          'proposals': [{'id': 'e1', 'code': '45380', 'bucket': 'selected', 'status': 'ready',
                                         'units': 1, 'position': 0, 'reinstatable': False, 'answered_away': False,
                                         'answers': [], 'family': 'gi.colonoscopy', 'other_reason': None}]},
                    'N': {'created_at': '2026-11-12T12:00:00+00:00', 'revision': 'r1', 'context': 'C2',
                          'engine_version': 'cpt-studio-events@2', 'clarifications': [], 'proposals': []}},
                'contexts': {'C1': {'created_at': '2026-11-12T09:00:00+00:00', 'revision': 'r1', 'version': 'gi-context@5',
                                    'facts': {}, 'earlier_assessment': None},
                             'C2': {'created_at': '2026-11-12T11:00:00+00:00', 'revision': 'r1',
                                    'version': 'gemini-context@2', 'facts': {}, 'earlier_assessment': 'E'}},
                'revisions': {'r1': {'number': 1}},
                'decisions': [{'id': 'd1', 'assessment': 'E', 'proposal': 'e1', 'code': '45380', 'action': 'approve',
                               'carried_from': None, 'sequence': 1}],
                'invalidations': [{'decision': 'd1', 'by_context': 'C2', 'by_revision': None}],
                'member_answers': [{'id': 'a1', 'revision': 'r1', 'answered_at': '2026-11-12T10:30:00+00:00',
                                    'standing': True}]}
        found = wc.compute(rows, wc.product_words(APP))
        self.assertEqual(found['unjudged'], [])
        value = found['what_changed']
        self.assertEqual([item['outcome'] for item in value['decisions']], ['cleared'])
        self.assertEqual(sc.shape_problems(value, ENCOUNTER['what_changed']), [])
        self.assertEqual(sc.shape_problems(None, ENCOUNTER['what_changed']), [])  # null unless fresh with an E
        broken = dict(value, codes=[{'code': '45380', 'change': 'moved', 'text': 'x'}])
        self.assertTrue(sc.shape_problems(broken, ENCOUNTER['what_changed']))

    def test_the_new_keys_are_scanned_like_every_other_customer_string(self):
        # a provider name or a machinery key in the new blocks is a hit (the denylist reads every key and value)
        ctx = sc.scan_context()
        hits = sc.scan_json({'what_changed': {'details': ['Read again by gemini_unknown']},
                             'update': {'changes': [], 'appraisal_run': 'x'}}, ctx)
        self.assertEqual(sorted({hit['id'] for hit in hits}), ['forbidden_key', 'provider_name'])
        self.assertTrue(re.fullmatch(r'customer-\d{4}-\d{2}-\d{2}', literal(APP / 'studio' / 'client_contract.py',
                                                                             'VERSION')))


if __name__ == '__main__':
    unittest.main()
