"""The Sonnet 5 stage runner's own judge (ops/sonnet5_stages.py) on RETAINED live relations answers, under THIS engine:
the engine's adoption (v3_field_relations.validated), the runner's judge (raw_selection, relation_disagreements, the
frozen replay subprocess, notes_field_outcome) against the frozen expectations, then classify_case.

These need Django (the engine reads settings; the replay runs the candidate's engine in a subprocess), so they run here,
under manage.py test core.tests, and never in the ops modules CI runs with plain `python -m unittest discover -s ops`
(refutation of dfde4fc8, F1: the 020 proof, placed there, failed CI with ImproperlyConfigured). No provider, no network,
no database: the review save and export are not replayed (they need the app path; the workflow tests walk them)."""
import functools
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from core import v3_field_relations as rel
from ops import provider_campaign as pc
from ops import sonnet5_stages as st
from ops.tests import network_guard
from .test_v3_field_relations_contract import ATTEMPT_020_TEXT, raw_result
from .test_v3_field_relations import from_keyed
from .test_v3_ordinary_notes import LIVE

#: The text block of live attempt 019's retained provider response (case N10 on the field-relations path), verbatim:
#: .runtime/v1-sonnet5-campaign/evidence/019/provider-response.body, sha256 fccad9e65b4eac5a…98272770 in that attempt's
#: evidence manifest. Both fields agree with their relations; the stage graded both supported_correct.
ATTEMPT_019_TEXT = ('{"fields":{"v3_1":{"unit_ids":[1],"conflict":false,"option_ids":["v3_1:1"],"context":{"1":"answer",'
                    '"2":"independent"}},"v3_2":{"unit_ids":[2],"conflict":false,"context":{"1":"independent",'
                    '"2":"answer"}}}}')


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


class RetainedJudge(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.inputs = st.frozen_inputs()

    def case(self, case_id):
        case = next(c for c in self.inputs['cases']['cases'] if c['id'] == case_id)
        return case, self.inputs['cases']['forms'][case['form']]['fields']

    def judge(self, case_id, text):
        """(served {key: (status, text)}, graded, findings, details, raw-selection evidence) as the runner judges it.
        `text` is a retained v2 keyed body (verbatim, or edited as a test states); the provider answers in contract v4's
        wire, so it is translated (`from_keyed`: the same selections, relations and options) before anything reads it."""
        text = from_keyed(text)
        case, fields = self.case(case_id)
        with override_settings(**dict(LIVE, **st.steps.PATH_FLAGS['field_relations'])):
            answers = rel.validated(raw_result(case['notes'], fields, text))
            runner = SimpleNamespace(inputs=self.inputs)
            runner.replay = functools.partial(st.Run.replay, runner)
            judge = st.Run.judge_notes(runner, case)
            with tempfile.TemporaryDirectory() as folder:
                graded, findings, details = judge(
                    SimpleNamespace(path='field_relations'), SimpleNamespace(fields=fields),
                    st.steps.field_outcomes(answers), None, None, evidence=Path(folder), reviewed=None,
                    raw={'content': [{'type': 'text', 'text': text}]})
                evidence = json.loads((Path(folder) / 'raw-selection.json').read_text())
        served = {k: (v['status'], v['text']) for k, v in answers.items()}
        return served, graded, findings, details, evidence

    def test_the_retained_020_outcome_is_two_correct_holds_and_does_not_stop_the_stage(self):
        # Live attempt 020 (N13): both fields conflict true with their selected statements marked contrary. The engine
        # used to fail the job (validator_failure: a contract stop of the stage).
        served, graded, findings, details, evidence = self.judge('N13', ATTEMPT_020_TEXT)
        self.assertEqual(served, {'v3_1': ('conflict', ''), 'v3_2': ('conflict', '')})
        self.assertEqual(graded, {'v3_1': 'held_correct', 'v3_2': 'held_correct'})
        self.assertEqual(findings, [])
        for key in ('v3_1', 'v3_2'):
            detail = details['fields'][key]
            # (the frozen replay: this selection — both statements, conflict true — is listed nowhere, so the replay
            # itself would leave it to adjudication; N13 desires a hold on both fields, which is what was adopted)
            self.assertEqual((detail['matched'], detail['replay_verdict'], detail['desired']),
                             ('unlisted', 'adjudicate_by_hand', 'held'))
            self.assertEqual(detail['never_violated'], [])
            self.assertNotIn('served_path_diverged_from_replay', detail)
            self.assertTrue(detail['model_relations_disagree'])          # (recorded; the hold is correct either way)
        self.assertEqual(evidence['relation_disagreements'], ['v3_1', 'v3_2'])
        verdict = pc.classify_case(graded, [])
        self.assertEqual((verdict['verdict'], verdict['stops_stage'], verdict['unsafe'], verdict['contract']),
                         ('usefulness', False, [], []))

    def test_the_retained_019_is_unchanged(self):
        served, graded, findings, details, evidence = self.judge('N10', ATTEMPT_019_TEXT)
        self.assertEqual(served, {'v3_1': ('supported', 'No'), 'v3_2': ('supported', 'none known.')})
        self.assertEqual(graded, {'v3_1': 'supported_correct', 'v3_2': 'supported_correct'})
        self.assertEqual((findings, evidence['relation_disagreements']), ([], []))
        for key in ('v3_1', 'v3_2'):
            self.assertNotIn('served_path_diverged_from_replay', details['fields'][key])
            self.assertFalse(details['fields'][key]['model_relations_disagree'])

    def test_a_hold_because_the_models_relations_disagree_is_the_models_not_an_application_over_hold(self):
        # Refutation of dfde4fc8, F3, verbatim: retained 019 with v3_2's SELECTED unit marked independent. Served held
        # (the record's disagreement); the frozen replay's shape cannot carry a selected unit's relation (it rebuilds
        # every selected unit as 'answer'), so the replay adopts and matched the ACCEPTABLE entry — graded over_held /
        # application_over_hold, blaming the application for the model's own contradiction.
        text = ATTEMPT_019_TEXT.replace('"context":{"1":"independent","2":"answer"}',
                                        '"context":{"1":"independent","2":"independent"}')
        self.assertNotEqual(text, ATTEMPT_019_TEXT)
        served, graded, findings, details, evidence = self.judge('N10', text)
        self.assertEqual(served, {'v3_1': ('supported', 'No'), 'v3_2': ('conflict', '')})
        self.assertEqual(graded, {'v3_1': 'supported_correct', 'v3_2': 'model_relation_disagreement'})
        detail = details['fields']['v3_2']
        self.assertEqual((detail['attribution'], detail['model_relations_disagree']),
                         ('model_relation_disagreement', True))
        self.assertEqual(detail['served_path_diverged_from_replay'], {'replay': ['supported', 'none known.']})
        self.assertEqual(evidence['relation_disagreements'], ['v3_2'])
        verdict = pc.classify_case(graded, findings)
        self.assertEqual((verdict['verdict'], verdict['stops_stage']), ('usefulness', False))
        self.assertEqual(verdict['usefulness'], {'model_relation_disagreement': 1, 'supported_correct': 1})

    def test_an_answer_relation_left_unselected_reaches_the_replay_which_then_holds_it_too(self):
        # v3_2 calls its statement its answer and selects nothing. raw_selection now carries that relation (the replay
        # CAN use an unselected unit's relation), so the replay holds v3_2 exactly as the served path did.
        text = ATTEMPT_019_TEXT.replace('"v3_2":{"unit_ids":[2]', '"v3_2":{"unit_ids":[]')
        self.assertNotEqual(text, ATTEMPT_019_TEXT)
        served, graded, findings, details, evidence = self.judge('N10', text)
        self.assertEqual(served, {'v3_1': ('supported', 'No'), 'v3_2': ('conflict', '')})
        case, fields = self.case('N10')
        with override_settings(**dict(LIVE, **st.steps.PATH_FLAGS['field_relations'])):
            asked, units = st.steps.source_units(case['notes'], fields)
        self.assertEqual(evidence['selection']['v3_2'], {'unit_ids': [], 'conflict': False, 'options': [],
                                                         'relations': {units[1]['quote']: 'answer'}})
        self.assertEqual(graded, {'v3_1': 'supported_correct', 'v3_2': 'model_relation_disagreement'})
        self.assertNotIn('served_path_diverged_from_replay', details['fields']['v3_2'])
        self.assertEqual(details['fields']['v3_2']['attribution'], 'model_relation_disagreement')
