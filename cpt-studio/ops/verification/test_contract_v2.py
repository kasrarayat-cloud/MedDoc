"""The customer contract of the Fable coding build (ops/verification/customer-contract.json; BUILD-SPEC section 6, client
contract customer-2026-11-26), held to itself, to the tools that read it and to the client build they name. The Django
suite holds the server to the same file (tests/test_api_customer.py, through ops/scan_customer.py's readers). No Django,
no database, no network.

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
CONTRACT = json.loads((HERE / 'customer-contract.json').read_text(encoding='utf-8'))
ENCOUNTER = CONTRACT['encounter']['keys']


def literal(path, name):
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f'{name} is not a literal of {path}')


class ContractTests(unittest.TestCase):
    def test_the_vocabulary_and_the_types_name_the_same_states_phases_and_statuses(self):
        vocabulary, types = CONTRACT['vocabulary'], CONTRACT['types']
        self.assertEqual(list(vocabulary['states']), types['state']['enum'])
        self.assertEqual(vocabulary['phases'], ENCOUNTER['progress']['keys']['phase']['enum'])
        self.assertEqual(list(vocabulary['code_statuses']), types['code']['keys']['status']['enum'])
        self.assertEqual(list(vocabulary['insurance']), types['insurance']['enum'])
        # BUILD-SPEC 5's eight states and their labels, and 'earlier': an encounter with no coding round
        self.assertEqual(vocabulary['states'], {
            'processing': 'Processing', 'stopped': 'Stopped', 'failed': 'Could not finish',
            'awaiting_answer': 'Questions for you', 'needs_review': 'Needs your review', 'ready': 'Ready for approval',
            'reviewed': 'Reviewed', 'no_codes': 'No codes found', 'earlier': 'Earlier review'})

    def test_every_reference_names_a_type_the_contract_defines(self):
        def refs(node):
            if isinstance(node, dict):
                if 'ref' in node:
                    yield node['ref']
                for value in node.values():
                    yield from refs(value)
            elif isinstance(node, list):
                for value in node:
                    yield from refs(value)
        named = set(refs({key: CONTRACT[key] for key in ('types', 'session', 'list', 'encounter', 'members',
                                                          'member_access', 'rate_limited')}))
        self.assertTrue(named)
        self.assertLessEqual(named, set(CONTRACT['types']))

    def test_no_key_of_the_earlier_contract_is_served(self):
        # the earlier pipeline's update, what-changed and history blocks, its proposals and its trace are gone
        for key in ('update', 'earlier_codes', 'what_changed', 'decision_history', 'proposals', 'service_date', 'trace'):
            self.assertNotIn(key, ENCOUNTER, key)
        self.assertEqual(sorted(ENCOUNTER), sorted([
            'id', 'title', 'created_at', 'updated_at', 'state', 'state_label', 'permissions', 'document', 'context',
            'progress', 'round', 'codes', 'questions', 'answers', 'notes', 'readiness', 'reports', 'activity']))

    def test_the_tools_name_the_servers_current_client_build(self):
        version = literal(APP / 'studio' / 'client_contract.py', 'VERSION')
        self.assertTrue(re.fullmatch(r'customer-\d{4}-\d{2}-\d{2}', version))
        login = (OPS / 'verify_login.py').read_text(encoding='utf-8')
        self.assertIn(f"CLIENT_HEADER, CLIENT_VERSION = 'X-CPT-Studio-Client', '{version}'", login)
        walk = (OPS / 'walk.cjs').read_text(encoding='utf-8')
        self.assertIn(f"const CLIENT_HEADERS = {{ 'X-CPT-Studio-Client': '{version}' }};", walk)

    def test_release_one_adds_the_team_and_the_limit_answer(self):
        # RELEASE-1-SPEC C4 and C5: the session's can_manage_team, GET api/members and POST api/members/<id>/access (the
        # shapes Lane 2's Team panel is built against) and the 429 answer, each exactly these keys
        self.assertEqual(CONTRACT['session']['keys']['can_manage_team'], 'boolean')
        member = CONTRACT['types']['member']['keys']
        self.assertEqual(sorted(member), sorted(['id', 'label', 'username', 'role', 'active', 'actor_kind', 'last_sign_in',
                                                 'password_change_required']))
        self.assertEqual(member['actor_kind'], {'enum': ['human', 'agent']})
        self.assertEqual(member['last_sign_in'], 'iso?')
        self.assertEqual(CONTRACT['members'], {'keys': {'members': {'items': {'ref': 'member'}}}})
        self.assertEqual(CONTRACT['member_access'], {'keys': {'member': {'ref': 'member'}}})
        self.assertEqual(CONTRACT['rate_limited'], {'keys': {'error': {'enum': ['rate_limited']},
                                                             'retry_after': 'integer'}})
        # the member's username key (the lead's shape, which Lane 2's Team panel reads) is the one key of the type the
        # denylist forbids elsewhere: a reader of this payload exempts it, and nothing else of it is forbidden
        denylist = json.loads((HERE / 'customer-denylist.json').read_text(encoding='utf-8'))
        self.assertEqual(set(member) & set(denylist['forbidden_keys']), {'username'})
        self.assertEqual(sc.shape_problems({'error': 'rate_limited', 'retry_after': 42}, CONTRACT['rate_limited']), [])
        self.assertTrue(sc.shape_problems({'error': 'rate_limited'}, CONTRACT['rate_limited']))

    def test_release_two_pages_the_list_and_says_which_rows_open_a_pdf(self):
        # RELEASE-2-SPEC R2-19, R2-16 and R2-24: a list answer is one page - its rows, the next page's cursor and, on a
        # first page, the list's total, each nullable - and each row says whether its first stored file is a small PDF
        self.assertEqual(CONTRACT['list'], {'keys': {'encounters': {'items': {'ref': 'list_row'}}, 'next': 'string?',
                                                     'total': 'integer?', 'workspace': 'string'}})
        row = CONTRACT['types']['list_row']['keys']
        self.assertEqual(sorted(row), sorted(['id', 'title', 'state', 'state_label', 'service_date', 'insurance',
                                              'created_at', 'kind', 'opens_pdf']))
        self.assertEqual(row['opens_pdf'], 'boolean')
        page = {'encounters': [], 'next': '20261126T101500.123456Z~0b7f3a52-9c1e-4d2a-8f61-2a9e5d0c4b17', 'total': None,
                'workspace': 'fa000000-0000-4000-8000-000000000002'}  # the practice it was read in (I1-2)
        self.assertEqual(sc.shape_problems(page, CONTRACT['list']), [])
        self.assertEqual(sc.shape_problems({**page, 'next': None, 'total': 0}, CONTRACT['list']), [])
        self.assertEqual(sc.shape_problems({**page, 'workspace': None}, CONTRACT['list']),
                         ['$.workspace: null where the contract has string'])
        # release 1's whole-list answer is now a difference: a reader of it would take a page for the whole practice
        self.assertEqual(sc.shape_problems({'encounters': []}, CONTRACT['list']),
                         ['$.next: missing (the contract lists it)', '$.total: missing (the contract lists it)',
                          '$.workspace: missing (the contract lists it)'])
        self.assertTrue(sc.shape_problems({'encounters': [], 'next': 5, 'total': '1'}, CONTRACT['list']))
        denylist = json.loads((HERE / 'customer-denylist.json').read_text(encoding='utf-8'))
        self.assertFalse({'next', 'total', 'opens_pdf'} & set(denylist['forbidden_keys']))
        self.assertIn('POST /api/encounters/search', CONTRACT['about'])

    def test_a_vendor_or_a_machinery_key_in_a_customer_payload_is_a_hit(self):
        # the denylist reads every key and every value of what the contract serves
        ctx = sc.scan_context()
        hits = sc.scan_json({'codes': [{'reason': 'Read by claude-fable-5-2.', 'reader_run': 'x'}]}, ctx)
        found = {hit['id'] for hit in hits}
        self.assertIn('forbidden_key', found)
        self.assertIn('model_id', found)
        self.assertEqual(sc.scan_json({'codes': [{'reason': 'Biopsies were taken (page 1).'}]}, ctx), [])


if __name__ == '__main__':
    unittest.main()
