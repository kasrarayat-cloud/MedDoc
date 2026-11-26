"""The customer contract's two readers held to each other (FG-E): ops/walk.cjs shapeProblems - what the browser walk
holds every customer JSON it reads to - and ops/scan_customer.py shape_problems - what the scanner and the Django suite
hold the server to - give the same sentences for the same payload, on ops/verification/customer-contract.json, for a
conforming payload of each kind and for every way one can differ (a key added at any depth, a key missing, a value of
another type, a word outside an enum, a null where none is allowed, past the bound of 60). So a reader cannot drift from
the other, and the walk cannot be green on a payload the server's own tests would refuse.

Known reading difference, left out on purpose: JavaScript's JSON reads 1.0 as the integer 1 and writes 1e21 as '1e+21',
so a float with no fraction where the contract has an integer, and numbers of 21 digits or more, read differently. The
server writes neither (studio.customer serves integers as integers).

Needs node (the walk's runtime, as CI has it); skipped, never passed, without it. No network, no Django, no database.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_walk_contract.py' -v
"""
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

OPS = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


sc = load('f3_walk_contract_scan', OPS / 'scan_customer.py')
CONTRACT = sc.CONTRACT
# The walk's reader, run by node on cases read from stdin: [[schema, value], ...] -> [[problem, ...], ...]
WALK_READER = ("const walk = require(process.argv[1]);"
               "const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
               "process.stdout.write(JSON.stringify(cases.map(([schema, value]) => "
               "walk.shapeProblems(value, walk.contract()[schema]))));")
LINES = 'line' in CONTRACT['types']['code']['keys']  # LINE IDENTITY: lane F1a's contract lists each row's line
QUESTION_LINES = 'lines' in CONTRACT['types']['question']['keys']  # and each question's lines (FIX-SPEC section 3)
DECISION_IDS = 'id' in CONTRACT['types']['decision']['keys']  # DECISION IDS: a decision shown carries its id (FIX-SPEC-2 5)


def code_row(code, status, line, **extra):
    row = {'code': code, 'units': 1, 'modifiers': [], 'status': status, 'status_label': 'Ready for approval',
           'reason': f'{code} is documented.', 'second_check': {'agrees': True, 'reason': 'Agreed.'}, 'question': None,
           'quotes': [{'text': 'A synthetic quoted passage.', 'page': 1}], 'decision': None,
           'allowed_actions': ['approve', 'reject'], **extra}
    return {'line': line, **row} if LINES else row


def encounter():
    eid = 'e5c1d3a2-1111-4222-8333-944455556666'
    return {
        'id': eid, 'title': 'Synthetic colonoscopy note', 'created_at': '2026-11-20T10:00:00Z',
        'updated_at': '2026-11-20T10:05:00+00:00', 'state': 'ready', 'state_label': 'Ready for approval',
        'permissions': {'can_review': True},
        'document': {'name': 'synthetic-note.pdf', 'media_type': 'application/pdf', 'size': 1024, 'kind': 'upload',
                     'original_url': f'/api/encounters/{eid}/original',
                     'view_url': f'/api/encounters/{eid}/original?view=1', 'view_media_type': 'application/pdf',
                     'converted': False},
        'context': {'service_date': '2026-11-02', 'insurance': 'medicare'},
        'progress': {'phase': 'done', 'busy': False, 'started_at': '2026-11-20T10:00:01.123Z',
                     'finished_at': '2026-11-20T10:04:59Z', 'server_time': '2026-11-20T10:05:30Z', 'message': '',
                     'can_stop': False, 'can_resume': False, 'can_retry': False, 'error': None},
        'round': {'number': 1, 'trigger': 'upload', 'finished_at': '2026-11-20T10:04:59Z'},
        'codes': [code_row('45385', 'ready', 'L1'),
                  code_row('45380', 'needs_answer', 'L2', status_label='Needs your answer', allowed_actions=[],
                           question='Was a biopsy taken from a separate site?', units=None)],
        'questions': [{'id': 'q1', 'text': 'Was a biopsy taken from a separate site?', 'codes': ['45380'],
                       **({'lines': ['L2']} if QUESTION_LINES else {})}],
        'answers': [{'question': 'Was it?', 'answer': 'Yes.', 'by': 'Coder1', 'at': '2026-11-20T10:03:00Z'}],
        'notes': ['The note is not signed.'],
        'readiness': {'draft': True, 'approved': False, 'blockers': ['No code has been approved.']},
        # the PDF report, the only one made since 2026-11-21, listed newest first beside a TXT made before that: an
        # earlier export stays listed as made (the contract's fmt keeps txt and csv for those)
        'reports': [{'id': 'r2', 'kind': 'draft', 'fmt': 'pdf', 'filename': 'CPT-Studio-draft-r1-20261121T100700.pdf',
                     'generated_at': '2026-11-21T10:07:00Z', 'download_url': '/api/reports/r2/download',
                     'current': True},
                    {'id': 'r1', 'kind': 'draft', 'fmt': 'txt', 'filename': 'x.txt',
                     'generated_at': '2026-11-20T10:06:00Z', 'download_url': '/api/reports/r1/download',
                     'current': True}],
        'activity': [{'at': '2026-11-20T10:00:00Z', 'text': 'Uploaded.'}],
    }


def session():
    return {'user': {'id': 'u1', 'label': 'Coder1', 'initials': 'C', 'actor_kind': 'human'},
            'workspace': {'id': 'w1', 'name': 'Gastroenterology', 'specialty': 'Gastroenterology'}, 'role': 'reviewer',
            'can_review': True, 'can_manage_team': False,
            'acknowledgement': 'I reviewed this code against the document.', 'counts': {'documents': 1, 'queue': 0}}


def listing():
    # release 2 (R2-19, R2-24): one page of a list, its next cursor and the list's total; each row's opens_pdf
    return {'encounters': [{'id': 'e1', 'title': 'Synthetic', 'state': 'processing', 'state_label': 'Processing',
                            'service_date': None, 'insurance': 'unknown', 'created_at': '2026-11-20T10:00:00Z',
                            'kind': 'paste', 'opens_pdf': False}], 'next': None, 'total': 1, 'workspace': 'w1'}


def mutated(make, change):
    value = make()
    change(value)
    return value


def cases():
    """[schema, value] pairs: each kind as served, and every way a payload can differ from its contract."""
    out = [['encounter', encounter()], ['session', session()], ['list', listing()],
           # what the contract allows to be null, null: still no difference
           ['encounter', mutated(encounter, lambda e: e.update(round=None, codes=[], reports=[]))]]
    changes = [
        lambda e: e.update(internal_round_id='x'),
        lambda e: e['document'].update(storage_hint='x'),
        lambda e: e['progress'].update(phase_detail='x'),
        lambda e: e['codes'][0].update(decision={**({'id': 'd1'} if DECISION_IDS else {}), 'action': 'approve',
                                                 'by': 'R', 'at': '2026-11-20T10:06:00Z', 'note': '',
                                                 'acknowledgement': 'x'}),
        *([lambda e: e['codes'][0].update(decision={'action': 'approve', 'by': 'R', 'at': '2026-11-20T10:06:00Z',
                                                    'note': ''})] if DECISION_IDS else []),  # a decision without its id
        lambda e: e['document'].pop('view_media_type'),
        lambda e: e['codes'][1].pop('quotes'),
        lambda e: e['document'].update(kind='txt'),
        lambda e: e['document'].update(kind='üpload'),  # a word outside the enum, written as json.dumps writes it
        lambda e: e['document'].update(kind=1.5),
        lambda e: e['document'].update(kind=1e-07),
        lambda e: e['document'].update(kind=None),
        lambda e: e['document'].update(kind=['upload']),
        lambda e: e['document'].update(kind={'a': 'b', 'c': [1, True, None]}),
        lambda e: e['context'].update(insurance=True),
        lambda e: e['progress'].update(server_time=None),
        lambda e: e['progress'].update(server_time='2026-11-20 10:05:30'),
        lambda e: e['progress'].update(error={'text': 'x', 'code': 1}),
        lambda e: e['progress'].update(busy='no'),
        lambda e: e['codes'][0]['quotes'][0].update(page='one'),
        lambda e: e['codes'][0].update(second_check='agrees'),
        lambda e: e['codes'][0].update(units=1.5),
        lambda e: e['codes'][0].update(modifiers='25'),
        lambda e: e['codes'][0].update(modifiers=[25]),
        lambda e: e['codes'][0].update(allowed_actions=['approve', 'escalate']),
        lambda e: e.update(codes={'0': {}}),
        lambda e: e.update(codes=['45385']),
        lambda e: e.update(round={'number': 1, 'trigger': 'upload'}),
        lambda e: e.update(round=5),
        lambda e: e.update(title=None),
        lambda e: e.update(notes=[1, 'x']),
        lambda e: e.update(activity=[{'at': 'yesterday', 'text': 'x'}]),
        lambda e: e['context'].update(service_date='14/10/2026'),
        lambda e: e['readiness'].update(draft='yes'),
        lambda e: e['reports'][0].update(fmt='docx'),  # a format outside the contract's
        lambda e: e.update(**{f'extra_{index:02d}': index for index in range(70)}),  # past the bound of 60
        lambda e: e.update(naïve='x'),
    ]
    out += [['encounter', mutated(encounter, change)] for change in changes]
    out += [['session', mutated(session, lambda s: s.pop('counts'))],
            ['session', mutated(session, lambda s: s.update(role='admin'))],
            ['session', mutated(session, lambda s: s['user'].update(actor_kind='robot', token='t'))],
            ['list', mutated(listing, lambda r: r['encounters'][0].update(kind='upload', extra=1))],
            ['list', mutated(listing, lambda r: r.update(encounters=None))],
            ['list', 'not an object']]
    return out


class ContractReadersAgreeTests(unittest.TestCase):
    def setUp(self):
        self.node = shutil.which('node')
        if self.node is None:
            self.skipTest('node is not here: the walk cannot be run')

    def walk_problems(self, battery):
        done = subprocess.run([self.node, '-e', WALK_READER, str(OPS / 'walk.cjs')], input=json.dumps(battery),
                              capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        return json.loads(done.stdout)

    def test_a_conforming_payload_of_each_kind_has_no_difference_for_either_reader(self):
        battery = cases()[:4]
        python = [sc.shape_problems(copy.deepcopy(value), CONTRACT[schema]) for schema, value in battery]
        self.assertEqual(python, [[], [], [], []])
        self.assertEqual(self.walk_problems(battery), python)

    def test_both_readers_give_the_same_sentences_for_every_difference(self):
        battery = cases()
        python = [sc.shape_problems(copy.deepcopy(value), CONTRACT[schema]) for schema, value in battery]
        walk = self.walk_problems(battery)
        self.assertEqual(len(walk), len(battery))
        for (schema, value), expected, found in zip(battery, python, walk):
            with self.subTest(schema=schema, value=json.dumps(value)[:120]):
                self.assertEqual(found, expected)
        # and the battery is not vacuous: every changed payload differs from its contract, one by more than 60
        self.assertTrue(all(problems for problems in python[4:]))
        self.assertGreater(max(len(problems) for problems in python), 60)


if __name__ == '__main__':
    unittest.main()
