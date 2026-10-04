"""The stage runner's pure parts (ops/sonnet5_stages.py), offline, without a database: the fixed plans, the mapping
unsafe rules, the notes field classes, the relations-path stop rule, the provider-selection reader, the offline
`plan` command (checked against the live ledger's OWN failure record), the remainder, the stage pass rule across runs
(a remainder never passes over an earlier stop) and the interruption path (an ordinary exception leaves the failure,
with what it did not send, to the stage decision). The end-to-end sends are in test_sonnet5_stages.py (QA server)."""
import json
import os
import subprocess
import sys
import unittest
import unittest.mock
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from ops import provider_campaign as pc
from ops import sonnet5_stages as st
from . import network_guard

REPOSITORY = Path(__file__).resolve().parents[3]


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


class PlanTests(unittest.TestCase):
    """C1/C2/C3: the fixed, recorded order of every send, from the frozen inputs alone."""

    @classmethod
    def setUpClass(cls):
        cls.inputs = st.frozen_inputs()

    def test_the_mapping_plan_is_every_frozen_form_in_order_then_the_f6a_and_f6b_encounters(self):
        sends = st.plan_sends('mapping', self.inputs)
        self.assertEqual([s.id for s in sends],
                         ['mapping:f1-guidance-confirmation', 'mapping:f2-leave-checkboxes',
                          'mapping:f2b-leave-checkboxes-owner', 'mapping:f3-selection-instructions',
                          'mapping:f4-exam-grid', 'mapping:f5-negative-controls', 'mapping:f6a-long-answer',
                          'mapping:f6b-admin-missing', 'generation:f6a-long-answer', 'generation:f6b-admin-missing'])
        self.assertEqual({s.pricing_key for s in sends}, {'mapping'})
        self.assertEqual([s.index for s in sends], list(range(1, 11)))
        # (R3: f6b's administrative note is sent — the frozen map's own source_note)
        self.assertIn('eye-test appointment', self.inputs['maps']['f6b-admin-missing']['source_note']['text'])

    def test_the_notes_plan_sends_default_groups_first_and_every_relations_send_last(self):
        sends = st.plan_sends('ordinary_notes', self.inputs)
        self.assertEqual(len(sends), 21)
        cases = {c['id']: c for c in self.inputs['cases']['cases']}
        order = [(s.path, s.group, cases[s.case]['primary_class']) for s in sends]
        default = [row for row in order if row[0] == 'default']
        self.assertEqual(order[:14], default)                           # (every default send before any relations send)
        self.assertEqual({row[0] for row in order[14:]}, {'field_relations'})
        groups = [row[1] for row in default]
        self.assertEqual(groups, sorted(groups, key=['usefulness', 'held_ambiguity', 'side_denial_correction',
                                                     'contradiction'].index))
        for path, group, cls in default:
            self.assertIn(cls, dict(st.NOTES_GROUPS)[group])
        for send in sends:
            self.assertEqual(send.pricing_key, {'default': 'ordinary_notes',
                                                'field_relations': 'ordinary_notes_field_relations'}[send.path])
            self.assertEqual(send.form, cases[send.case]['form'])
        self.assertEqual(sorted(s.case for s in sends if s.path == 'field_relations'),
                         sorted(c for c, case in cases.items() if 'field_relations' in case['send_paths']))

    def test_a_case_whose_marking_contradicts_its_send_paths_is_refused(self):
        import copy
        inputs = copy.deepcopy(self.inputs)
        inputs['cases']['cases'][0]['requires_field_relations'] = 'yes'
        with self.assertRaises(pc.Refused):
            st.plan_sends('ordinary_notes', inputs)
        with self.assertRaises(pc.Refused):
            st.plan_sends('model_check', self.inputs)

    def test_the_stage_settings_are_the_deployed_equivalent_path(self):
        for stage in st.STAGES:
            flags = st.STAGE_FLAGS[stage]
            self.assertEqual(flags['QUILLMD_WORD_ENGINE'], 'v3')
            self.assertEqual(flags['QUILLMD_LAYOUT_SOCKET'], '')
            self.assertEqual({flags[n] for n in ('QUILLMD_WM_NARRATIVE', 'QUILLMD_V3_HISTORY_CONTEXT',
                                                 'QUILLMD_V3_GENERATION_BATCHES', 'QUILLMD_V3_FIELD_RELATIONS')}, {'0'})
        self.assertEqual((st.STAGE_FLAGS['mapping']['QUILLMD_MAPPING_ASSISTANCE'],
                          st.STAGE_FLAGS['mapping']['QUILLMD_MAPPING_ASSISTANCE_LIVE']), ('1', '1'))
        self.assertEqual((st.STAGE_FLAGS['ordinary_notes']['QUILLMD_MAPPING_ASSISTANCE'],
                          st.STAGE_FLAGS['ordinary_notes']['QUILLMD_MAPPING_ASSISTANCE_LIVE']), ('0', '0'))


def graded(areas=(), controls=(), false_fields=()):
    return {'areas': [dict(a) for a in areas], 'controls': [dict(c) for c in controls],
            'false_fields': [dict(f) for f in false_fields]}


class MappingFindingTests(unittest.TestCase):
    """C1: the mapping stage's UNSAFE rules, judged against the frozen grader's grading of the deterministic fields."""
    RIGHT = graded([{'id': 'A1', 'outcome': 'right'}, {'id': 'A2', 'outcome': 'wrong', 'problems': ["label names 'x'"]}],
                   [{'id': 'C1', 'type': 'not_an_answer', 'outcome': 'right'},
                    {'id': 'C2', 'type': 'must_refuse', 'outcome': 'right'},
                    {'id': 'C3', 'type': 'must_refuse', 'outcome': 'wrong'},
                    {'id': 'C4', 'type': 'must_hold', 'outcome': 'right'},
                    {'id': 'C5', 'type': 'must_refuse', 'outcome': 'right', 'applies_to': ['A1']}])

    def codes(self, proposal):
        return sorted((f['code'], f['item']) for f in st.mapping_findings(proposal, self.RIGHT))

    def test_the_deterministic_mapping_itself_is_not_unsafe(self):
        self.assertEqual(self.codes(self.RIGHT), [])

    def test_a_harmful_change_accepted_without_a_review_record_stops(self):
        proposal = graded([{'id': 'A1', 'outcome': 'wrong', 'problems': ['kind choice, expected text']},
                           {'id': 'A2', 'outcome': 'wrong', 'problems': ["label names 'x'"]}], self.RIGHT['controls'])
        self.assertEqual(self.codes(proposal), [('harmful_change_unreviewed', 'A1')])
        # (a HELD area is not wrong: the grader already made it held_safe when a record reaches the field)
        held = graded([{'id': 'A1', 'outcome': 'held_safe'}], self.RIGHT['controls'])
        self.assertEqual(self.codes(held), [])
        # (made non-answerable is the safe direction: a usefulness loss, never a stop)
        safe = graded([{'id': 'A1', 'outcome': 'wrong', 'problems': ['not answerable (write_protected=True, kind=text)']}])
        self.assertEqual(self.codes(safe), [])
        # (the grader reports a field made non-answerable WITH the consequences it implies, such as the kind it no
        # longer has; a field nobody can answer cannot carry a wrong answer, so those companions do not make it a stop —
        # refutation F2, which found f6b's all-missing form stopping the stage this way)
        companions = graded([{'id': 'A1', 'outcome': 'wrong', 'problems': [
            'kind none, expected long_text (accepted [\'long_text\', \'text\'])',
            'not answerable (write_protected=True, kind=none, reason=\'not an answer\')']}])
        self.assertEqual(self.codes(companions), [])

    def test_a_wrong_destination_left_unheld_stops_even_when_the_deterministic_mapping_had_it(self):
        for problem in ('anchored at b/p[1], expected the answer paragraph b/p[2]', 'anchored on preserved text at b/p[1]',
                        'box refs [], expected [x]', 'the field also covers A2',
                        "target cell rewrites the first paragraph, which holds preserved text 'x'"):
            with self.subTest(problem=problem):
                proposal = graded([{'id': 'A2', 'outcome': 'wrong', 'problems': [problem]}])
                deterministic = graded([{'id': 'A2', 'outcome': 'wrong', 'problems': [problem]}])
                self.assertEqual([f['code'] for f in st.mapping_findings(proposal, deterministic)], ['wrong_destination'])
        for kind in ('not_an_answer', 'must_hold'):
            with self.subTest(kind=kind):
                proposal = graded([], [{'id': 'C9', 'type': kind, 'outcome': 'wrong'}])
                self.assertEqual([f['code'] for f in st.mapping_findings(proposal, proposal)], ['wrong_destination'])
        extra = graded(false_fields=[{'key': 'v3_9', 'slot': 'b/p[0]', 'outcome': 'false_field'},
                                     {'key': 'v3_8', 'slot': 'b/p[1]', 'outcome': 'false_field_held'}])
        self.assertEqual([(f['code'], f['item']) for f in st.mapping_findings(extra, extra)],
                         [('wrong_destination', 'false:v3_9')])

    def test_a_protected_area_made_answerable_stops_and_one_left_answerable_is_recorded(self):
        made = graded(self.RIGHT['areas'], [{'id': 'C2', 'type': 'must_refuse', 'outcome': 'wrong'}] + self.RIGHT['controls'][2:])
        self.assertEqual(self.codes(made), [('protected_area_answered', 'C2')])
        # C3 was already answerable deterministically (the tracked engine defect, N8): kept, not a stop
        self.assertEqual(self.codes(graded(self.RIGHT['areas'], self.RIGHT['controls'])), [])

    def test_a_broken_side_pair_stops(self):
        # (the side pair is a must_refuse control with applies_to; the grader's row does not say so, the map does)
        proposal = graded(self.RIGHT['areas'], self.RIGHT['controls'][:4] + [
            {'id': 'C5', 'type': 'must_refuse', 'outcome': 'wrong', 'problems': ['side']}])
        self.assertEqual([(f['code'], f['item']) for f in st.mapping_findings(proposal, self.RIGHT, {'C5'})],
                         [('wrong_side', 'C5')])
        self.assertEqual([f['code'] for f in st.mapping_findings(proposal, proposal, {'C5'})], [])

    def test_the_outcomes_feed_the_case_verdict(self):
        outcomes = st.mapping_outcomes(graded([{'id': 'A1', 'outcome': 'right'}], [{'id': 'C1', 'type': 'x',
                                                                                     'outcome': 'held_safe'}],
                                              [{'key': 'v3_9', 'outcome': 'false_field', 'slot': 's'}]))
        self.assertEqual(outcomes, {'A1': 'right', 'C1': 'held_safe', 'false:v3_9': 'false_field'})
        self.assertEqual(pc.classify_case(outcomes, [])['unsafe'], ['wrong_destination'])


def expectation(cls='V', desired='supported', texts=None, never=(), acceptable=None, forbidden=None):
    ae = {'desired': desired}
    if texts is not None:
        ae['desired_texts'] = list(texts)
    if never:
        ae['never'] = list(never)
    return {'class': cls, 'app_adoption_expectation': ae,
            'raw_model_expectation': {'acceptable': acceptable or [{'units': ['A.'], 'conflict': False}],
                                      'forbidden': forbidden or []}}


class NotesFieldOutcomeTests(unittest.TestCase):
    """C2: each field's outcome class from the LIVE adoption, the review save, the frozen expectation and the frozen
    replay's matched entry."""
    FIELD = {'key': 'v3_1', 'kind': 'text'}

    def outcome(self, exp, adopted, reviewed=None, matched='acceptable', index=0):
        reviewed = adopted if reviewed is None else reviewed
        return st.notes_field_outcome(exp, self.FIELD, adopted, reviewed, {'matched': matched, 'index': index})[0]

    def test_supported_held_and_over_held(self):
        exp = expectation(texts=['A.'])
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'A.'}), 'supported_correct')
        self.assertEqual(self.outcome(exp, {'status': 'held', 'text': ''}), 'over_held')
        self.assertEqual(self.outcome(expectation(desired='held'), {'status': 'held', 'text': ''}), 'held_correct')
        self.assertEqual(self.outcome(expectation(desired='missing'), {'status': 'missing', 'text': ''}), 'held_correct')

    def test_a_leak_is_unsafe_and_named_for_the_field_class(self):
        for cls, unsafe in (('V', 'unsupported_accepted'), ('SIDE', 'wrong_side_adopted'),
                            ('DENIAL', 'wrong_denial_adopted'), ('CONTRADICTION', 'contradiction_adopted'),
                            ('CORRECTION', 'unsupported_accepted'), ('M', 'unsupported_accepted')):
            with self.subTest(cls=cls):
                self.assertEqual(self.outcome(expectation(cls, desired='held'), {'status': 'supported', 'text': 'x'}),
                                 unsafe)

    def test_a_forbidden_selection_adopted_is_unsafe_even_where_the_field_may_be_supported(self):
        exp = expectation(forbidden=[{'units': ['B.'], 'conflict': False, 'app_should': 'model_dependent'}], texts=['A.'])
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'B.'}, matched='forbidden'),
                         'unsupported_accepted')
        # (held, the same forbidden selection is a model error the application caught — never an over-hold)
        self.assertEqual(self.outcome(exp, {'status': 'held', 'text': ''}, matched='forbidden'), 'held_correct')
        # (and where the field names no desired text, only the forbidden match can say the adoption is wrong)
        open_text = expectation(forbidden=[{'units': ['B.'], 'conflict': False, 'app_should': 'not_supported'}])
        self.assertEqual(self.outcome(open_text, {'status': 'supported', 'text': 'B.'}, matched='forbidden'),
                         'unsupported_accepted')
        self.assertEqual(self.outcome(open_text, {'status': 'supported', 'text': 'A.'}), 'supported_correct')

    def test_a_held_model_error_is_a_correct_hold_and_an_unlisted_hold_is_never_auto_scored(self):
        # The frozen README's scoring: step 4 — a forbidden (or wrong unlisted) selection is a MODEL error, and an
        # application over-hold is an ACCEPTABLE selection held where `desired` is supported; step 2 — an unlisted
        # response is adjudicated by hand, never auto-scored. (Refutation F1: both were tallied as over_held.)
        exp = expectation(forbidden=[{'units': ['B.', 'A.'], 'conflict': False, 'app_should': 'not_supported'}],
                          texts=['A.'])
        blank = {'status': 'left_blank', 'text': ''}
        for status in ('held', 'missing'):
            with self.subTest(status=status):
                held = {'status': status, 'text': ''}
                outcome, details = st.notes_field_outcome(exp, self.FIELD, held, blank,
                                                          {'matched': 'forbidden', 'index': 0, 'verdict': 'caught'})
                self.assertEqual((outcome, details['attribution']), ('held_correct', 'model_error_caught'))
                self.assertEqual((details['matched'], details['replay_verdict']), ('forbidden', 'caught'))
                outcome, details = st.notes_field_outcome(exp, self.FIELD, held, blank,
                                                          {'matched': 'unlisted', 'index': None,
                                                           'verdict': 'adjudicate_by_hand'})
                self.assertEqual((outcome, details['attribution']), ('held_unadjudicated', 'adjudicate_by_hand'))
                outcome, details = st.notes_field_outcome(exp, self.FIELD, held, blank,
                                                          {'matched': 'acceptable', 'index': 0, 'verdict': 'over_hold'})
                self.assertEqual((outcome, details['attribution']), ('over_held', 'application_over_hold'))
        # where the field must not be supported, a hold is right whatever the model chose (the application's own call)
        self.assertEqual(self.outcome(expectation(desired='held'), {'status': 'held', 'text': ''}, matched='unlisted',
                                      index=None), 'held_correct')
        # an unadjudicated hold is recorded usefulness evidence: it never stops the stage and is never unsafe
        verdict = pc.classify_case({'v3_1': 'held_unadjudicated', 'v3_2': 'held_correct'}, [])
        self.assertEqual((verdict['stops_stage'], verdict['unsafe']), (False, []))
        self.assertEqual(verdict['usefulness'], {'held_correct': 1, 'held_unadjudicated': 1})

    def test_a_hold_caused_by_the_models_own_relation_disagreement_is_attributed_to_the_model(self):
        # Refutation of dfde4fc8, F3: a field the served path held because the MODEL's selection disagrees with its own
        # relations was graded over_held / application_over_hold whenever the frozen replay (which cannot carry a
        # selected unit's relation) matched an acceptable entry. It is the model's contradiction, caught.
        exp = expectation(forbidden=[{'units': ['B.'], 'conflict': False, 'app_should': 'not_supported'}], texts=['A.'])
        blank = {'status': 'left_blank', 'text': ''}
        for status in ('held', 'missing', 'conflict'):
            held = {'status': status, 'text': ''}
            for matched, index, verdict in (('acceptable', 0, 'as_desired'), ('unlisted', None, 'adjudicate_by_hand')):
                with self.subTest(status=status, matched=matched):
                    outcome, details = st.notes_field_outcome(exp, self.FIELD, held, blank,
                                                              {'matched': matched, 'index': index, 'verdict': verdict},
                                                              model_disagrees=True)
                    self.assertEqual((outcome, details['attribution'], details['model_relations_disagree']),
                                     ('model_relation_disagreement', 'model_relation_disagreement', True))
                    # (without the disagreement the same hold is still what it was)
                    outcome, details = st.notes_field_outcome(exp, self.FIELD, held, blank,
                                                              {'matched': matched, 'index': index, 'verdict': verdict})
                    self.assertEqual(outcome, {'acceptable': 'over_held', 'unlisted': 'held_unadjudicated'}[matched])
                    self.assertFalse(details['model_relations_disagree'])
            # a FORBIDDEN selection held is already the model's error: unchanged
            outcome, details = st.notes_field_outcome(exp, self.FIELD, held, blank,
                                                      {'matched': 'forbidden', 'index': 0, 'verdict': 'caught'},
                                                      model_disagrees=True)
            self.assertEqual((outcome, details['attribution']), ('held_correct', 'model_error_caught'))
        # where the field must not be supported, a hold is right whatever the model said; an adoption is still unsafe
        self.assertEqual(st.notes_field_outcome(expectation(desired='held'), self.FIELD, {'status': 'held', 'text': ''},
                                                None, {'matched': 'unlisted', 'index': None},
                                                model_disagrees=True)[0], 'held_correct')
        self.assertEqual(st.notes_field_outcome(expectation(desired='held'), self.FIELD,
                                                {'status': 'supported', 'text': 'x'}, None,
                                                {'matched': 'unlisted', 'index': None}, model_disagrees=True)[0],
                         'unsupported_accepted')
        # the new outcome is usefulness evidence: never unsafe, never a stop
        verdict = pc.classify_case({'v3_1': 'model_relation_disagreement', 'v3_2': 'supported_correct'}, [])
        self.assertEqual((verdict['verdict'], verdict['stops_stage'], verdict['unsafe']), ('usefulness', False, []))

    def test_a_never_item_is_unsafe(self):
        exp = expectation('DENIAL', never=['Yes'], texts=['No'])
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'Yes.'}), 'wrong_denial_adopted')
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'No'}), 'supported_correct')
        quoted = expectation('CONTRADICTION', desired='held', never=["supported 'none.'"])
        self.assertEqual(st.never_violations(quoted['app_adoption_expectation']['never'],
                                             {'status': 'supported', 'text': 'none.'}, self.FIELD)[0], ["supported 'none.'"])
        hits, prose = st.never_violations(['text without "as needed"', 'checked'], {'status': 'supported', 'text': 'x'},
                                          {'kind': 'checkbox'})
        self.assertEqual((hits, prose), (['checked'], ['text without "as needed"']))

    def test_an_unlisted_adopted_text_no_desired_text_allows_is_unsafe(self):
        exp = expectation(texts=['A.'])
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'Z.'}, matched='unlisted', index=None),
                         'unsupported_accepted')
        # an acceptable selection whose text follows another stripping convention is still correct (recorded)
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'Z.'}), 'supported_correct')

    def test_entry_level_desired_outcomes(self):
        exp = expectation(desired='held', acceptable=[{'units': ['A.'], 'conflict': True},
                                                      {'units': [], 'conflict': False, 'desired': 'usefulness_loss'},
                                                      {'units': ['A.'], 'conflict': False, 'desired': 'not_asserted'}])
        self.assertEqual(self.outcome(exp, {'status': 'missing', 'text': ''}, index=1), 'usefulness_loss')
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'A.'}, index=2), 'recorded_not_asserted')
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'A.'}, index=0), 'unsupported_accepted')

    def test_a_review_that_changes_the_adopted_value_is_a_clinician_correction_unless_unsafe(self):
        exp = expectation(texts=['A.'])
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'A.'}, {'status': 'missing', 'text': ''}),
                         'clinician_correction')
        leak = expectation(desired='held')
        self.assertEqual(self.outcome(leak, {'status': 'supported', 'text': 'x'}, {'status': 'missing', 'text': ''}),
                         'unsupported_accepted')
        # "Leave blank — reviewed" on a held field is a recorded decision, not a correction; an edit is one
        self.assertEqual(self.outcome(leak, {'status': 'held', 'text': ''}, {'status': 'left_blank', 'text': ''}),
                         'held_correct')
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'A.'}, {'status': 'supported', 'text': 'A.'}),
                         'supported_correct')
        self.assertEqual(self.outcome(exp, {'status': 'supported', 'text': 'A.'}, {'status': 'edited', 'text': 'A.'}),
                         'clinician_correction')


class StopRuleTests(unittest.TestCase):
    """C2: unsafe output stops a DEFAULT-path send's stage; on the paused relations path it is veto evidence; a contract
    failure stops either."""

    def test_the_stop_rule(self):
        unsafe = pc.classify_case({'v3_1': 'contradiction_adopted'}, [])
        contract = pc.classify_case({'v3_1': 'held_correct'}, ['wrong_served_model'])
        both = pc.classify_case({'v3_1': 'contradiction_adopted'}, ['reconciliation'])
        fine = pc.classify_case({'v3_1': 'over_held'}, [])
        self.assertEqual(st.stop_decision(unsafe, 'default'), (True, 'unsafe'))
        self.assertEqual(st.stop_decision(unsafe, 'mapping'), (True, 'unsafe'))
        self.assertEqual(st.stop_decision(unsafe, 'field_relations'), (False, 'veto_evidence'))
        self.assertEqual(st.stop_decision(contract, 'field_relations'), (True, 'contract'))
        self.assertEqual(st.stop_decision(both, 'field_relations'), (True, 'unsafe'))
        self.assertEqual(st.stop_decision(fine, 'default'), (False, None))


class PlanCommandTests(unittest.TestCase):
    """C3: `plan --stage mapping|ordinary_notes` offline — a fresh process with no credential, no network (sockets are
    never needed: the database host is a non-existent socket directory and any connection attempt is refused), and no
    database; it prints the fixed order, each send's maximum and bound, and the stage worst case against the remaining
    limits (the ledger read without its lock)."""

    def plan(self, stage):
        env = {'PATH': '/usr/bin:/bin', 'TMPDIR': '/tmp', 'HOME': '/tmp', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        done = subprocess.run([sys.executable, '-B', 'ops/sonnet5_qa.py', 'plan', '--stage', stage], cwd=REPOSITORY / 'rebuild',
                              capture_output=True, text=True, timeout=900, env=env)
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        return json.loads(done.stdout)

    @staticmethod
    def ledger_decision(stage):
        """The live ledger's own record of `stage`, read straight from its files (never through the code under test):
        (the latest failure's summary or None, [(attempt number, send id) of the stage's attempts])."""
        ledger = pc.LIVE_ROOT / 'ledger'

        def number(path):
            tail = path.stem.rsplit('-', 1)[-1]
            return int(tail) if tail.isdigit() else 1
        failures = sorted(ledger.glob(f'stage-{stage}-failed*.json'), key=number)
        passed = (ledger / f'stage-{stage}-passed.json').exists()
        latest = json.loads(failures[-1].read_text()) if failures and not passed else None
        attempts = [json.loads(p.read_text()) for p in sorted(ledger.glob('[0-9][0-9][0-9]-attempt.json'))]
        return (latest or {}).get('summary'), [(a['number'], (a.get('send') or {}).get('id')) for a in attempts
                                               if a.get('stage') == stage]

    def test_plan_prints_every_send_its_bound_and_the_worst_case_against_the_limits(self):
        # (the live ledger, read-only: a stage whose latest decision is a failure plans only that failure's unsent
        # sends; one never failed plans all of them). The expected sends come from the LEDGER'S OWN failure record,
        # read from its files here — never from the report, which would only compare the plan with itself (refutation
        # F4-PLAN-CLI-TEST-TAUTOLOGICAL).
        for stage, count in (('mapping', 10),):
            with self.subTest(stage=stage):
                report = self.plan(stage)
                full = [s.id for s in st.plan_sends(stage, st.frozen_inputs())]
                summary, attempts = self.ledger_decision(stage)
                if summary is not None:
                    expected = [send for send in full if send in summary['not_sent']]
                    self.assertEqual(expected, summary['not_sent'])              # (the record lists them in plan order)
                    count = len(expected)
                    self.assertIsNotNone(report['remainder'])
                    self.assertEqual([row['id'] for row in report['order']], expected)
                    self.assertEqual(report['remainder']['sends'], expected)
                    self.assertEqual(report['remainder']['already_made'], sorted({send for _, send in attempts}))
                    # a send that stopped the stage is never sent again, so the stage can never pass (refutation F1):
                    # every stopping row the record carries is reported, and then the plan says the stage cannot pass
                    stopped = {(row['attempt'], row['send']['id']) for row in summary['sends']
                               if row.get('stops_stage') and row.get('attempt')}
                    self.assertLessEqual(stopped, {(e['attempt'], e['send']) for e in report['earlier_stops']})
                    self.assertEqual(report['can_pass'], not report['earlier_stops'])
                    if stopped:
                        self.assertFalse(report['can_pass'])
                else:
                    self.assertIsNone(report['remainder'])
                self.assertEqual((report['stage'], report['sends'], len(report['order'])), (stage, count, count))
                self.assertTrue(all(row['pricing_version_is_declared'] for row in report['order']))
                bounds = [Decimal(row['bound_x1_1']) for row in report['order']]
                for row in report['order']:
                    self.assertEqual(Decimal(row['bound_x1_1']), Decimal(row['maximum_cost']) * Decimal('1.1'))
                self.assertEqual(Decimal(report['stage_worst_case']), sum(bounds, Decimal(0)))
                self.assertEqual(report['worst_case_fits'],
                                 Decimal(report['stage_worst_case']) <= Decimal(report['stage_remaining'])
                                 and Decimal(report['stage_worst_case']) <= Decimal(report['total_remaining']))
                self.assertEqual((report['credential_read'], report['network'], report['database']),
                                 (False, 'none', 'none'))

    def test_without_an_amendment_the_notes_plan_refuses_at_the_field_relations_version(self):
        # the repaired relations contract (v2) no longer prices at the declared v1 field-relations version: whether the
        # plan is the whole stage or the remainder of its failure, the first relations send refuses (nothing planned)
        done = subprocess.run([sys.executable, '-B', 'ops/sonnet5_qa.py', 'plan', '--stage', 'ordinary_notes'],
                              cwd=REPOSITORY / 'rebuild', capture_output=True, text=True, timeout=900,
                              env={'PATH': '/usr/bin:/bin', 'TMPDIR': '/tmp', 'HOME': '/tmp', 'LANG': 'C.UTF-8',
                                   'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(done.returncode, 2, done.stderr[-3000:])
        self.assertIn('field_relations: the application prices', done.stderr)
        self.assertIn('not the declared ordinary_notes_field_relations', done.stderr)

    def test_an_amendment_is_for_the_notes_stage_and_the_plan_and_run_commands_only(self):
        env = {'PATH': '/usr/bin:/bin', 'TMPDIR': '/tmp', 'HOME': '/tmp', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        for argv, fragment in ((['plan', '--stage', 'mapping', '--amendment', '/nonexistent.md'], 'ordinary_notes stage only'),
                               (['plan', '--amendment', '/nonexistent.md'], 'ordinary_notes stage only'),
                               (['status', '--amendment', '/nonexistent.md'], 'Only plan and run')):
            with self.subTest(argv=argv):
                done = subprocess.run([sys.executable, '-B', 'ops/sonnet5_qa.py', *argv], cwd=REPOSITORY / 'rebuild',
                                      capture_output=True, text=True, timeout=300, env=env)
                self.assertEqual(done.returncode, 2, done.stderr[-2000:])
                self.assertIn(fragment, done.stderr)

    def test_an_unknown_stage_is_refused(self):
        done = subprocess.run([sys.executable, '-B', 'ops/sonnet5_qa.py', 'plan', '--stage', 'holdout'],
                              cwd=REPOSITORY / 'rebuild', capture_output=True, text=True, timeout=300,
                              env={'PATH': '/usr/bin:/bin', 'TMPDIR': '/tmp', 'HOME': '/tmp', 'LANG': 'C.UTF-8'})
        self.assertEqual(done.returncode, 2)
        self.assertIn('No stage runner', done.stderr)


class FrozenInputTests(unittest.TestCase):
    """C3: nothing is read from the diagnostics — and so nothing is planned, graded or sent — unless the freeze holds and
    the recorded self-test belongs to it; a grader or replay whose output does not carry this freeze is refused."""

    def test_a_frozen_file_that_differs_refuses_before_anything(self):
        real = st.freeze_check.listed()
        altered = dict(real, **{'grade_app_path.py': 'f' * 64})
        with unittest.mock.patch.object(st.freeze_check, 'listed', return_value=altered):
            with self.assertRaises(pc.Refused) as caught:
                st.frozen_inputs()
        self.assertIn('grade_app_path.py', str(caught.exception))

    def test_a_self_test_record_of_another_freeze_refuses(self):
        real = st.freeze_check.verify()
        with unittest.mock.patch.object(st.freeze_check, 'verify', return_value={**real, 'manifest_sha256': 'e' * 64}):
            with self.assertRaises(pc.Refused) as caught:
                st.frozen_inputs()
        self.assertIn('self-test', str(caught.exception))

    def test_grader_and_replay_output_must_carry_this_freeze(self):
        import tempfile
        from types import SimpleNamespace
        inputs = st.frozen_inputs()
        scratch = Path(tempfile.mkdtemp(prefix='stage-provenance-'))
        self.addCleanup(__import__('shutil').rmtree, scratch, True)
        (scratch / 'output.json').write_text(json.dumps({'fields': [], 'review': {}}))
        (scratch / 'det.json').write_text('[]')
        (scratch / 'expr.json').write_text('{}')
        good = SimpleNamespace(inputs=inputs)
        graded = st.Run.grade(good, 'f6b-admin-missing', scratch / 'output.json', scratch / 'det.json',
                              scratch / 'expr.json', scratch / 'graded.json')
        self.assertEqual(graded['provenance']['manifest_sha256'], inputs['freeze']['manifest_sha256'])
        other = SimpleNamespace(inputs={**inputs, 'freeze': {**inputs['freeze'], 'manifest_sha256': 'e' * 64}})
        with self.assertRaises(pc.Refused) as caught:
            st.Run.grade(other, 'f6b-admin-missing', scratch / 'output.json', scratch / 'det.json',
                         scratch / 'expr.json', scratch / 'graded-2.json')
        self.assertIn('provenance', str(caught.exception))
        evidence = scratch / 'evidence'
        evidence.mkdir(mode=0o700)
        replayed = st.Run.replay(good, 'N01', 'default', {}, evidence)
        self.assertEqual(replayed['provenance']['inputs']['cases'],
                         st.freeze_check.sha256(st.NOTES_DIR / 'cases.json'))
        evidence = scratch / 'evidence-2'
        evidence.mkdir(mode=0o700)
        with self.assertRaises(pc.Refused) as caught:
            st.Run.replay(other, 'N01', 'default', {}, evidence)
        self.assertIn('provenance', str(caught.exception))


class EncounterJudgementTests(unittest.TestCase):
    """C1: after f6a and f6b are generated, the export is judged with the engine's own readers: f6b (an administrative
    note) must fill NOTHING — any filled destination is an unsupported answer; f6a's long answer, when adopted, must be
    exported WHOLE — a partial one is a data-loss failure."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from types import SimpleNamespace
        cls.scratch = Path(tempfile.mkdtemp(prefix='stage-encounter-'))
        cls.inputs = st.frozen_inputs()
        cls.forms = st.build_forms(cls.scratch / 'forms', 'mapping', cls.inputs)
        cls.stage_run = SimpleNamespace(inputs=cls.inputs)
        cls.Namespace = SimpleNamespace

    @classmethod
    def tearDownClass(cls):
        __import__('shutil').rmtree(cls.scratch, True)

    def judge(self, form, answers, outcomes):
        from documents import word_v3 as w
        original = self.forms[form]
        fields = w.inspect(original)['fields']
        exported = w.fill(original, fields, answers) if answers else original
        send = st.Send(9, f'generation:{form}', 'generation', form, 'mapping_encounter', 'encounters', None, 'mapping')
        version = self.Namespace(fields=fields)
        return fields, st.Run.judge_encounter(self.stage_run, send, version, outcomes, exported, original)

    def test_the_administrative_form_must_fill_nothing(self):
        from documents import word_v3 as w
        fields = w.inspect(self.forms['f6b-admin-missing'])['fields']
        site = next(f for f in fields if f['label'].startswith('Wound site'))
        _, (verdict, findings, details) = self.judge('f6b-admin-missing', {}, {})
        self.assertEqual((findings, details['destinations_changed']), ([], []))
        self.assertEqual(set(verdict.values()), {'held_correct'})
        _, (verdict, findings, details) = self.judge('f6b-admin-missing', {site['key']: 'Left shin'},
                                                     {site['key']: {'status': 'supported', 'text': 'Left shin'}})
        self.assertEqual(details['destinations_changed'], [site['key']])
        self.assertEqual([f['code'] for f in findings], ['adopted_without_source_support'])
        self.assertEqual(verdict[site['key']], 'unsupported_accepted')
        self.assertEqual(pc.classify_case(verdict, [f['code'] for f in findings])['verdict'], 'unsafe')

    def test_an_adopted_long_answer_must_be_exported_whole(self):
        from documents import word_v3 as w
        answer = self.inputs['long_answer']
        fields = w.inspect(self.forms['f6a-long-answer'])['fields']
        key = next(f['key'] for f in fields if f['locator']['slot'].startswith('b/tbl[0]/tr[1]/tc[0]'))
        _, (verdict, findings, details) = self.judge('f6a-long-answer', {key: answer},
                                                     {key: {'status': 'supported', 'text': answer}})
        self.assertEqual((verdict[key], findings, details['long_answer']['whole']), ('supported_correct', [], True))
        part = answer[:2000]
        _, (verdict, findings, details) = self.judge('f6a-long-answer', {key: part},
                                                     {key: {'status': 'supported', 'text': part}})
        self.assertEqual((verdict[key], details['long_answer']['whole']), ('supported_incomplete', False))
        self.assertEqual([f['code'] for f in findings], ['export_verification_failed'])
        _, (verdict, findings, details) = self.judge('f6a-long-answer', {}, {key: {'status': 'held', 'text': ''}})
        self.assertEqual((verdict[key], findings, details['long_answer']['adopted']), ('over_held', [], False))


def rezip(data, part, edit):
    """`data` with one member's bytes passed through `edit` (every other member copied as it is, in order)."""
    import io
    import zipfile
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            content = source.read(info.filename)
            target.writestr(info, edit(content) if info.filename == part else content)
    return out.getvalue()


def replaced_once(old, new):
    """An edit that replaces exactly one occurrence of `old`, and proves it did (a scripted edit asserts its count)."""
    def edit(content):
        assert content.count(old) == 1, (old, content.count(old))
        changed = content.replace(old, new)
        assert changed != content
        return changed
    return edit


class ExportReadBackTests(unittest.TestCase):
    """Refutation EXPORT-CHECK-DOES-NOT-READ: the frozen app-path check skipped held and blank fields, called a choice or
    checkbox written without reading its mark, and never looked at the rest of word/document.xml. The stage's own
    read-back reads the export with the engine's readers against what the clinician SAVED — independently of the
    product's writer (core.v3_mapping.fill_answers is never called by it)."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from ops import standing_qa_notes_review as review
        cls.scratch = Path(tempfile.mkdtemp(prefix='stage-read-back-'))
        cls.inputs = st.frozen_inputs()
        cls.forms = st.build_forms(cls.scratch / 'forms', 'ordinary_notes', cls.inputs)
        cls.cases = {c['id']: c for c in cls.inputs['cases']['cases']}
        cls.consent_review = review.frozen(review.MANIFEST_SHA256)
        cls.reviewed_inputs = review.inputs_with_review(cls.inputs, cls.consent_review)

    @classmethod
    def tearDownClass(cls):
        __import__('shutil').rmtree(cls.scratch, True)

    def case(self, case_id):
        """(the form, its fields, what a clinician saved: each desired-supported field its first desired text, every
        other field left blank and reviewed)."""
        case = self.cases[case_id]
        # The explicit prospective exclusion preserves the frozen original
        # and gold answers. Its human-owned Consent control is not exported.
        fields = self.reviewed_inputs['cases']['forms'][case['form']]['fields']
        saved = {}
        for f in fields:
            ae = case['fields'][f['key']]['app_adoption_expectation']
            if ae['desired'] == 'supported':
                saved[f['key']] = {'status': 'supported', 'text': ae['desired_texts'][0], 'reviewed': True}
            else:
                saved[f['key']] = {'status': 'left_blank', 'text': '', 'reviewed': True}
        return self.forms[case['form']], fields, saved

    def ordinary_checkbox(self, checked=False):
        """Independent ordinary control; the frozen Consent original stays human-owned."""
        import io
        from docx import Document
        from documents import word_v3 as w
        document = Document()
        document.add_paragraph(('☒' if checked else '☐') + ' Smoker')
        stream = io.BytesIO()
        document.save(stream)
        original = stream.getvalue()
        fields = w.inspect(original)['fields']
        box, = [f for f in fields if f['kind'] == 'checkbox']
        self.assertFalse(box.get('write_protected'))
        saved = {f['key']: {'status': 'left_blank', 'text': '', 'reviewed': True} for f in fields}
        return original, fields, box, saved

    def export(self, original, fields, written):
        from documents import word_v3 as w
        return w.fill(original, fields, written)

    def honest(self, original, fields, saved):
        from core import v3_mapping
        return self.export(original, fields, v3_mapping.fill_answers(fields, saved))

    def problems(self, result):
        return sorted({p['where'] for p in result['problems']})

    def test_an_honest_export_of_every_frozen_case_reads_back_as_saved(self):
        for case_id in sorted(self.cases):
            with self.subTest(case=case_id):
                original, fields, saved = self.case(case_id)
                result = st.export_read_back(original, self.honest(original, fields, saved), fields, saved)
                self.assertEqual(result['problems'], [])
                self.assertTrue(result['passed'])
                self.assertEqual(set(result['fields']), {f['key'] for f in fields})

    def test_a_choice_mark_that_is_not_the_saved_answer_fails(self):
        from core import v3_mapping
        original, fields, saved = self.case('N04')
        self.assertEqual(saved['v3_6']['text'], 'No')
        written = v3_mapping.fill_answers(fields, saved)
        for name, changed in (('the other option ticked', {**written, 'v3_6': 'Yes'}),
                              ('no option ticked', {k: v for k, v in written.items() if k != 'v3_6'})):
            with self.subTest(name):
                exported = self.export(original, fields, changed)
                result = st.export_read_back(original, exported, fields, saved)
                self.assertFalse(result['passed'])
                self.assertEqual(self.problems(result), ['v3_6'])
                # (the frozen check passes both: it never reads the mark — which is why the stage reads it itself)
                frozen = st.steps.export_verification(original, exported, fields, saved)
                self.assertTrue(frozen['workflow_success'])

    def test_a_held_or_blank_field_that_holds_text_fails(self):
        from core import v3_mapping
        original, fields, saved = self.case('N11')
        self.assertEqual(saved['v3_2'], {'status': 'left_blank', 'text': '', 'reviewed': True})
        exported = self.export(original, fields, {**v3_mapping.fill_answers(fields, saved), 'v3_2': 'penicillin.'})
        result = st.export_read_back(original, exported, fields, saved)
        self.assertFalse(result['passed'])
        self.assertIn('v3_2', self.problems(result))
        self.assertTrue(st.steps.export_verification(original, exported, fields, saved)['workflow_success'])
        # a supported answer whose status says it is not the clinician's answer is not an answer either
        unsaid = {**saved, 'v3_1': {**saved['v3_1'], 'status': 'left_blank'}}
        result = st.export_read_back(original, self.honest(original, fields, saved), fields, unsaid)
        self.assertIn('v3_1', self.problems(result))

    def test_a_checkbox_reviewed_and_left_blank_must_be_unticked(self):
        from core import v3_mapping
        original, fields, box, saved = self.ordinary_checkbox()
        self.assertEqual(saved[box['key']]['status'], 'left_blank')
        exported = self.export(original, fields, {**v3_mapping.fill_answers(fields, saved), box['key']: True})
        result = st.export_read_back(original, exported, fields, saved)
        self.assertEqual(self.problems(result), [box['key']])

    def test_a_checkbox_the_blank_form_prints_ticked_follows_the_stated_rule(self):
        # Ordinary checkbox review unticks; an unreviewed control preserves its
        # printed mark. The distinct protected Consent rule is tested below.
        from core import v3_mapping
        original, fields, box, saved = self.ordinary_checkbox(checked=True)
        self.assertEqual(box.get('printed_ticked'), [0])
        unticked = self.honest(original, fields, saved)
        result = st.export_read_back(original, unticked, fields, saved)
        self.assertEqual((result['problems'], result['fields'][box['key']]['read']), ([], [False]))
        kept = self.export(original, fields, {k: v for k, v in v3_mapping.fill_answers(fields, saved).items()
                                              if k != box['key']})
        self.assertEqual(self.problems(st.export_read_back(original, kept, fields, saved)), [box['key']])
        never_reviewed = {**saved, box['key']: {'status': 'held', 'text': '', 'reviewed': False}}
        self.assertTrue(st.export_read_back(original, kept, fields, never_reviewed)['passed'])
        self.assertEqual(self.problems(st.export_read_back(original, unticked, fields, never_reviewed)), [box['key']])

    def test_frozen_consent_exclusion_preserves_original_and_refuses_direct_ticks(self):
        import hashlib
        from core import v3_mapping
        from documents import word_v3 as w
        original, fields, saved = self.case('N06')
        frozen = self.inputs['cases']['forms']['r1-11']['fields']
        self.assertEqual(hashlib.sha256(original).hexdigest(), self.consent_review['source_sha256'])
        consent = next(f for f in fields if f['key'] == self.consent_review['field_key'])
        self.assertTrue(consent['write_protected'])
        self.assertNotIn(consent['key'], v3_mapping.fill_answers(fields, saved))
        for tick in (False, True):
            with self.subTest(tick=tick), self.assertRaises(w.V3Failure) as caught:
                self.export(original, frozen, {consent['key']: tick})
            self.assertEqual(caught.exception.code, 'protected_signing_area')
        exported = self.honest(original, fields, saved)
        result = st.export_read_back(original, exported, fields, saved)
        self.assertTrue(result['passed'])
        self.assertFalse(result['fields'][consent['key']]['set_by_export'])

    def test_reviewed_protected_checkbox_keeps_printed_mark_and_rejects_automatic_answer(self):
        from documents import word_v3 as w
        original = rezip(self.forms['r1-11'], 'word/document.xml', replaced_once(
            '<w:t>☐</w:t></w:r><w:r><w:t xml:space="preserve"> Consent obtained'.encode(),
            '<w:t>☒</w:t></w:r><w:r><w:t xml:space="preserve"> Consent obtained'.encode()))
        fields = w.inspect(original)['fields']
        box = next(f for f in fields if f['kind'] == 'checkbox')
        self.assertTrue(box['write_protected'])
        self.assertEqual(box['label'], 'Consent obtained')
        saved = {f['key']: {'status': 'left_blank', 'text': '', 'reviewed': True} for f in fields}
        kept = self.honest(original, fields, saved)
        result = st.export_read_back(original, kept, fields, saved)
        self.assertEqual(result['problems'], [])
        self.assertEqual(result['fields'][box['key']]['read'], [True])
        self.assertFalse(result['fields'][box['key']]['set_by_export'])
        wrong = {**saved, box['key']: {'status': 'supported', 'text': '☒', 'reviewed': True}}
        self.assertEqual(self.problems(st.export_read_back(original, kept, fields, wrong)), [box['key']])
        erased = rezip(kept, 'word/document.xml', replaced_once(
            '<w:t>☒</w:t></w:r><w:r><w:t xml:space="preserve"> Consent obtained'.encode(),
            '<w:t>☐</w:t></w:r><w:r><w:t xml:space="preserve"> Consent obtained'.encode()))
        self.assertEqual(self.problems(st.export_read_back(original, erased, fields, saved)), [box['key']])

    def test_protected_scalars_read_original_entries_and_reject_changed_or_removed_content(self):
        original, fields, _ = self.case('N01')
        field = next(f for f in fields if f['key'] == 'v3_1')
        existing = self.export(original, fields, {field['key']: 'Existing human text'})
        changed = self.export(original, fields, {field['key']: 'Incorrect protected answer'})
        # Both exports use the same inspected physical target. Protection here
        # is the checker input; no signing/admission guard is bypassed.
        blank = {'status': 'left_blank', 'text': '', 'reviewed': True}
        for kind in ('text', 'long_text', 'date', 'time'):
            with self.subTest(kind=kind):
                protected = {**field, 'kind': kind, 'write_protected': True}
                answers = {field['key']: blank}
                kept = st.export_read_back(existing, existing, [protected], answers)
                self.assertTrue(kept['passed'], kept['problems'])
                self.assertEqual(kept['fields'][field['key']]['read'], 'Existing human text')
                for bad in (changed, original):
                    failed = st.export_read_back(existing, bad, [protected], answers)
                    self.assertFalse(failed['passed'])
                    self.assertIn(field['key'], self.problems(failed))
                proposed = {field['key']: {'status': 'supported', 'text': 'Incorrect protected answer',
                                           'reviewed': True}}
                for output in (existing, changed):
                    failed = st.export_read_back(existing, output, [protected], proposed)
                    self.assertFalse(failed['passed'])
                    self.assertFalse(failed['fields'][field['key']]['set_by_export'])
                    self.assertEqual(failed['fields'][field['key']]['expected'], 'Existing human text')
                    self.assertIn(field['key'], self.problems(failed))
        ordinary = st.export_read_back(original, changed, [field], {
            field['key']: {'status': 'supported', 'text': 'Incorrect protected answer', 'reviewed': True}})
        self.assertTrue(ordinary['passed'], ordinary['problems'])

    def test_a_written_text_that_is_not_the_saved_one_fails(self):
        from core import v3_mapping
        original, fields, saved = self.case('N04')
        exported = self.export(original, fields, {**v3_mapping.fill_answers(fields, saved), 'v3_5': 'amoxicillin.'})
        self.assertEqual(self.problems(st.export_read_back(original, exported, fields, saved)), ['v3_5'])

    def test_printed_content_changed_outside_the_written_fields_fails(self):
        original, fields, saved = self.case('N10')
        honest = self.honest(original, fields, saved)
        for name, edit in (('a printed label deleted', replaced_once(b'>Allergies', b'>')),
                           ('a paragraph added', replaced_once(b'<w:sectPr', b'<w:p><w:r><w:t>Added.</w:t></w:r></w:p>'
                                                                            b'<w:sectPr'))):
            with self.subTest(name):
                exported = rezip(honest, 'word/document.xml', edit)
                result = st.export_read_back(original, exported, fields, saved)
                self.assertFalse(result['passed'])
                self.assertEqual([p['where'] for p in result['problems'] if p['where'] not in {f['key'] for f in fields}],
                                 ['outside the written fields'])
                self.assertTrue(st.steps.export_verification(original, exported, fields, saved)['workflow_success'])

    def test_an_unreadable_export_fails_and_is_not_a_crash(self):
        original, fields, saved = self.case('N10')
        result = st.export_read_back(original, b'not a document', fields, saved)
        self.assertFalse(result['passed'])
        self.assertEqual(self.problems(result), ['export'])


    def test_complete_multiline_saved_value_keeps_the_original_false_negative(self):
        original, fields, saved = self.case('N01')
        text = 'to start amitriptyline 10 mg at night.\nShe will follow up in six weeks.'
        saved['v3_9'] = {'status': 'supported', 'text': text, 'reviewed': True}
        exported = self.honest(original, fields, saved)
        result, reading = st.saved_export_verification(original, exported, fields, saved)
        self.assertFalse(result['frozen_export_verification']['workflow_success'])
        self.assertTrue(result['workflow_success'])
        self.assertIn('v3_9', result['visible_break_readback_corrections'])
        for key in result['visible_break_readback_corrections']:
            self.assertEqual(reading['fields'][key]['read'], saved[key]['text'])
        self.assertEqual(reading['fields']['v3_9']['read'], text)

    def test_complete_saved_tab_is_read_as_a_tab(self):
        original, fields, saved = self.case('N01')
        text = 'Synthetic medication\t10 mg\nSynthetic follow-up\t6 weeks'
        saved['v3_9'] = {'status': 'supported', 'text': text, 'reviewed': True}
        result, reading = st.saved_export_verification(original, self.honest(original, fields, saved), fields, saved)
        self.assertTrue(result['workflow_success'])
        self.assertEqual(reading['fields']['v3_9']['read'], text)

    def test_a_break_replaced_by_a_space_cannot_correct_the_frozen_failure(self):
        from core import v3_mapping
        original, fields, saved = self.case('N01')
        saved['v3_9'] = {'status': 'supported', 'text': 'First sentence.\nSecond sentence.', 'reviewed': True}
        written = v3_mapping.fill_answers(fields, saved)
        for replacement in ('First sentence. Second sentence.', 'First sentence.',
                            'Second sentence.\nFirst sentence.', 'First sentence.\nWrong sentence.'):
            with self.subTest(replacement=replacement):
                exported = self.export(original, fields, {**written, 'v3_9': replacement})
                result, reading = st.saved_export_verification(original, exported, fields, saved)
                self.assertFalse(result['workflow_success'])
                self.assertFalse(result['supported_answers_in_their_fields']['v3_9'])
                self.assertNotIn('v3_9', result['visible_break_readback_corrections'])

    def test_complete_multiline_text_in_another_field_cannot_pass(self):
        from core import v3_mapping
        original, fields, saved = self.case('N01')
        text = 'First sentence.\nSecond sentence.'
        saved['v3_9'] = {'status': 'supported', 'text': text, 'reviewed': True}
        written = v3_mapping.fill_answers(fields, saved)
        exported = self.export(original, fields, {**written, 'v3_9': 'Wrong destination value.', 'v3_7': text})
        result, reading = st.saved_export_verification(original, exported, fields, saved)
        self.assertFalse(result['workflow_success'])
        self.assertEqual(result['visible_break_readback_corrections'], {})

    def test_correct_multiline_value_with_wrong_marks_still_refuses(self):
        from core import v3_mapping
        original, fields, saved = self.case('N01')
        saved['v3_9'] = {'status': 'supported', 'text': 'First sentence.\nSecond sentence.', 'reviewed': True}
        exported = self.export(original, fields, {**v3_mapping.fill_answers(fields, saved), 'v3_6': 'Yes'})
        result, reading = st.saved_export_verification(original, exported, fields, saved)
        self.assertFalse(result['workflow_success'])
        self.assertIn('v3_6', self.problems(reading))
        self.assertEqual(result['visible_break_readback_corrections'], {})

    def test_correct_multiline_value_with_a_changed_question_still_refuses(self):
        import io
        from zipfile import ZipFile
        from lxml import etree
        original, fields, saved = self.case('N01')
        saved['v3_9'] = {'status': 'supported', 'text': 'First sentence.\nSecond sentence.', 'reviewed': True}
        stream = io.BytesIO()
        with ZipFile(io.BytesIO(self.honest(original, fields, saved))) as source, ZipFile(stream, 'w') as out:
            for item in source.infolist():
                raw = source.read(item.filename)
                if item.filename == 'word/document.xml':
                    root = etree.fromstring(raw)
                    question = root.xpath('.//w:tr[1]/w:tc[1]//w:t', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
                    self.assertTrue(question)
                    question[0].text = 'Changed neighboring question'
                    raw = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                out.writestr(item, raw)
        result, reading = st.saved_export_verification(original, stream.getvalue(), fields, saved)
        self.assertFalse(result['workflow_success'])
        self.assertIn('outside the written fields', self.problems(reading))
        self.assertEqual(result['visible_break_readback_corrections'], {})


def positional(body):
    """The engine's wire (contract v4) of a body written keyed (field key -> entry, context unit ID -> relation), test
    code only: a list of answers naming their keys, each context the partition of its units by relation."""
    def partition(context):
        lists = {name: [] for name in ('answer', 'qualifier', 'contrary', 'unresolved', 'independent')}
        for unit, relation in sorted(context.items(), key=lambda pair: int(pair[0])):
            lists[relation].append(int(unit))
        return lists
    return {'fields': [{'key': key, **{k: v for k, v in entry.items() if k != 'context'},
                        'context': partition(entry['context'])} for key, entry in body['fields'].items()]}


class RawSelectionTests(unittest.TestCase):
    """C2: the model's own selection is read from the provider message only (never from the adopted answers)."""

    def test_a_message_without_exactly_one_text_block_is_refused(self):
        for message in ({'content': []}, {'content': [{'type': 'text', 'text': '{}'}, {'type': 'text', 'text': '{}'}]}):
            with self.subTest(message=message), self.assertRaises(pc.Refused):
                st.raw_selection(message, [], '', 'default')

    def test_the_relations_answer_reads_into_the_replays_unchanged_shape(self):
        # (N13's frozen form and notes; the v4 wire the contract returns, fields in any order, each context the partition
        # of its units; written keyed here and translated by `positional`)
        inputs = st.frozen_inputs()
        case = next(c for c in inputs['cases']['cases'] if c['id'] == 'N13')
        fields = inputs['cases']['forms'][case['form']]['fields']
        asked, units = st.steps.source_units(case['notes'], fields)
        first, other = asked[0]['key'], asked[1]['key']
        ids = [u['id'] for u in units]
        body = {'fields': {other: {'unit_ids': [], 'conflict': True, 'context': {str(i): 'independent' for i in ids}},
                           first: {'unit_ids': [ids[0]], 'conflict': False,
                                   'context': {**{str(i): 'independent' for i in reversed(ids[1:])},
                                               str(ids[0]): 'answer', str(ids[1]): 'contrary'}}}}
        message = {'content': [{'type': 'text', 'text': json.dumps(positional(body))}]}
        selection = st.raw_selection(message, fields, case['notes'], 'field_relations')
        self.assertEqual(set(selection), {first, other})
        self.assertEqual(selection[first], {'unit_ids': [ids[0]], 'conflict': False, 'options': [],
                                            'relations': {units[1]['quote']: 'contrary'}})
        self.assertEqual(selection[other], {'unit_ids': [], 'conflict': True, 'options': [], 'relations': {}})
        # (the frozen replay's own reader of this shape: offline_replay adopt(), unchanged)
        for bad in ({'fields': [{'key': first, 'unit_ids': [], 'conflict': False, 'option_ids': [], 'context': []}]},
                    positional({'fields': {first: body['fields'][first]}}),
                    body):                                                   # (v2's keyed shape: refused)
            with self.subTest(bad=bad), self.assertRaises(pc.Refused):
                st.raw_selection({'content': [{'type': 'text', 'text': json.dumps(bad)}]}, fields, case['notes'],
                                 'field_relations')
        default = {'fields': [{'key': first, 'unit_ids': [ids[0]], 'conflict': False}]}
        self.assertEqual(st.raw_selection({'content': [{'type': 'text', 'text': json.dumps(default)}]}, fields,
                                          case['notes'], 'default'),
                         {first: {'unit_ids': [ids[0]], 'conflict': False}})

    def test_an_answer_relation_left_unselected_is_carried_and_a_disagreement_is_named(self):
        # Refutation of dfde4fc8, F3. The frozen replay rebuilds every SELECTED unit as 'answer' and every other unit
        # from `relations` (default independent), so an unselected unit's relation is the one thing it can use: an
        # 'answer' there used to be dropped (the replay then read an agreeing field the served path held). A selected
        # unit's own relation cannot reach the replay at all; relation_disagreements names the fields whose selection
        # disagrees with their relations, from the model's own answer, so the judge attributes that hold to the model.
        inputs = st.frozen_inputs()
        case = next(c for c in inputs['cases']['cases'] if c['id'] == 'N13')
        fields = inputs['cases']['forms'][case['form']]['fields']
        asked, units = st.steps.source_units(case['notes'], fields)
        first, other = asked[0]['key'], asked[1]['key']
        ids = [u['id'] for u in units]

        def message(first_entry, other_entry=None):
            body = {'fields': {first: first_entry, other: other_entry or {
                'unit_ids': [], 'conflict': False, 'context': {str(i): 'independent' for i in ids}}}}
            return {'content': [{'type': 'text', 'text': json.dumps(positional(body))}]}
        agreeing = {'unit_ids': [ids[0]], 'conflict': False,
                    'context': {**{str(i): 'independent' for i in ids}, str(ids[0]): 'answer', str(ids[1]): 'contrary'}}
        unselected_answer = {**agreeing, 'context': {**agreeing['context'], str(ids[2]): 'answer'}}
        selected_independent = {**agreeing, 'context': {**agreeing['context'], str(ids[0]): 'independent'}}
        selected_qualifier = {**agreeing, 'context': {**agreeing['context'], str(ids[0]): 'qualifier'}}
        cases = ((agreeing, {units[1]['quote']: 'contrary'}, set()),
                 (unselected_answer, {units[1]['quote']: 'contrary', units[2]['quote']: 'answer'}, {first}),
                 (selected_independent, {units[1]['quote']: 'contrary'}, {first}),
                 (selected_qualifier, {units[1]['quote']: 'contrary'}, set()))           # (a qualifier agrees)
        for entry, relations, disagreeing in cases:
            with self.subTest(context=entry['context']):
                self.assertEqual(st.raw_selection(message(entry), fields, case['notes'], 'field_relations')[first],
                                 {'unit_ids': [ids[0]], 'conflict': False, 'options': [], 'relations': relations})
                self.assertEqual(st.relation_disagreements(message(entry), fields, case['notes'], 'field_relations'),
                                 disagreeing)
        self.assertEqual(st.relation_disagreements(message(unselected_answer, selected_independent), fields,
                                                   case['notes'], 'field_relations'), {first, other})
        # (the default path returns no relations, so it can name no disagreement; a malformed answer is refused)
        default = {'content': [{'type': 'text', 'text': json.dumps({'fields': [{'key': first, 'unit_ids': [ids[0]],
                                                                                  'conflict': False}]})}]}
        self.assertEqual(st.relation_disagreements(default, fields, case['notes'], 'default'), set())
        with self.assertRaises(pc.Refused):
            st.relation_disagreements({'content': [{'type': 'text', 'text': '{"fields": {}}'}]}, fields, case['notes'],
                                      'field_relations')


class PendingSendsTests(unittest.TestCase):
    """REMAINDER: once a stage has failed (and until it passes) it sends ONLY what its latest failure recorded as not
    sent; a send with an attempt is never sent again; a failure that cannot say what it did not send refuses."""

    @classmethod
    def setUpClass(cls):
        import io
        from .test_provider_campaign import REAL_DECLARATION
        cls.inputs = st.frozen_inputs()
        cls.declaration = pc.declared(REAL_DECLARATION, repository=REPOSITORY, out=io.StringIO())

    def campaign(self, **kwargs):
        from .test_sonnet5_amendment_plan import live_shape
        return pc.Campaign(self.declaration, live_shape(self, self.declaration, **kwargs))

    def pending(self, campaign, stage='ordinary_notes'):
        return st.pending_sends(campaign, stage, st.plan_sends(stage, self.inputs))

    def test_the_live_failures_remainder_is_its_six_unsent_relations_sends(self):
        from .test_sonnet5_amendment_plan import UNSENT
        for reopened in (False, True):
            with self.subTest(reopened=reopened):
                sends, remainder = self.pending(self.campaign(reopened=reopened))
                self.assertEqual([s.id for s in sends], UNSENT)
                self.assertEqual({s.path for s in sends}, {'field_relations'})
                self.assertEqual([s.index for s in sends], [16, 17, 18, 19, 20, 21])      # (their places in the plan)
                self.assertEqual(remainder['sends'], UNSENT)
                self.assertEqual(len(remainder['already_made']), 15)
                self.assertIn('notes:N02:field_relations', remainder['already_made'])
                self.assertFalse(set(UNSENT) & set(remainder['already_made']))

    def test_a_stage_that_never_failed_or_has_passed_plans_everything(self):
        from .test_provider_campaign import scratch
        fresh = pc.Campaign(self.declaration, scratch(self))
        sends, remainder = self.pending(fresh)
        self.assertEqual((len(sends), remainder), (21, None))
        campaign = self.campaign(reopened=True)
        campaign.ledger.acquire()
        campaign.ledger.write_stage('ordinary_notes', 'passed', {'summary': {}})
        campaign.ledger.release()
        self.assertEqual(len(self.pending(campaign)[0]), 21)                  # (admission refuses a passed stage anyway)

    def test_a_send_with_an_attempt_is_never_sent_again(self):
        from .test_sonnet5_amendment_plan import UNSENT
        campaign = self.campaign(not_sent=UNSENT + ['notes:N02:field_relations'],
                                 extra_attempted=['notes:N02:field_relations'])
        with self.assertRaises(pc.Refused) as caught:
            self.pending(campaign)
        self.assertIn('notes:N02:field_relations already has an attempt', str(caught.exception))

    def edited_failure(self, edit):
        from .test_sonnet5_amendment_plan import live_shape
        root = live_shape(self, self.declaration)
        path = root / 'ledger' / 'stage-ordinary_notes-failed-1.json'
        record = json.loads(path.read_text())
        edit(record)
        os.chmod(path, 0o600)
        path.unlink()
        pc.write_new(path, record)
        return pc.Campaign(self.declaration, root)

    def test_a_failure_that_cannot_say_what_it_did_not_send_refuses(self):
        cases = {
            'no summary (a settled interruption)': (lambda r: r.pop('summary'), 'no readable list'),
            'no not_sent': (lambda r: r['summary'].pop('not_sent'), 'no readable list'),
            'nothing unsent': (lambda r: r['summary'].update(not_sent=[]), 'no remainder'),
            'an unknown send': (lambda r: r['summary']['not_sent'].append('notes:N99:default'), 'does not have'),
            'a send listed twice': (lambda r: r['summary']['not_sent'].append(r['summary']['not_sent'][0]), 'does not have'),
            'a planned send dropped': (lambda r: r['summary']['not_sent'].pop(), 'neither made nor lists'),
        }
        for name, (edit, fragment) in cases.items():
            with self.subTest(name=name), self.assertRaises(pc.Refused) as caught:
                self.pending(self.edited_failure(edit))
            self.assertIn(fragment, str(caught.exception))

    def test_an_attempt_that_records_no_send_refuses(self):
        campaign = self.campaign()
        path = campaign.ledger.dir / '005-attempt.json'
        record = json.loads(path.read_text()); record.pop('send')
        path.unlink(); pc.write_new(path, record)
        with self.assertRaises(pc.Refused) as caught:
            self.pending(campaign)
        self.assertIn('records no send', str(caught.exception))

    def test_a_mapping_encounter_never_runs_without_its_forms_mapping_send(self):
        from .test_provider_campaign import attempt, limits_record, scratch, terms_record, usage
        plan = [s.id for s in st.plan_sends('mapping', self.inputs)]
        for made, expected in ((['mapping:f1-guidance-confirmation'], plan[1:]),              # (the live mapping failure)
                               (plan[:7], None)):                                              # (f6a mapped, its encounter not)
            with self.subTest(made=len(made)):
                campaign = pc.Campaign(self.declaration, scratch(self))
                ledger = campaign.ledger
                ledger.acquire()
                d = self.declaration
                ledger.write_attempt(attempt(1, campaign=d.campaign, authority=d.authority_id, limits=limits_record(d),
                                             terms=terms_record(d)))
                ledger.write_outcome(1, {'class': 'completed', 'usage': usage()})
                ledger.write_stage('model_check', 'passed', {'attempt': 1})
                for number, send in enumerate(made, 2):
                    record = attempt(number, 'mapping', campaign=d.campaign, authority=d.authority_id,
                                     limits=limits_record(d), terms=terms_record(d))
                    record['send'] = {'id': send}
                    ledger.write_attempt(record)
                    ledger.write_outcome(number, {'class': 'completed', 'usage': usage()})
                ledger.write_stage('mapping', 'failed', {'reasons': ['synthetic'], 'summary': {
                    'plan': plan, 'not_sent': [s for s in plan if s not in made], 'sends': []}})
                ledger.release()
                if expected is None:
                    with self.assertRaises(pc.Refused) as caught:
                        self.pending(campaign, 'mapping')
                    self.assertIn('needs its form', str(caught.exception))
                else:
                    self.assertEqual([s.id for s in self.pending(campaign, 'mapping')[0]], expected)


class StagePassTests(unittest.TestCase):
    """REMAINDER, refutations F1 and F1-REMAINDER-FALSE-PASS: a remainder completes a stage's EVIDENCE, never its pass.
    The stage passes only when no attempt of any of its runs stopped it or ended with no decision recording how
    (sonnet5_stages.earlier_stops). A send that stopped the stage is never sent again, so after one the stage can never
    pass: a clean remainder is decided `failed`, naming the earlier stop, with nothing left unsent. Only a stage whose
    earlier failure stopped BEFORE an attempt (nothing was sent for it) can still pass on its remainder. The remainder
    itself — what is sent — is unchanged: exactly the latest failure's not_sent. Synthetic ledgers in temporary
    directories; nothing real is read or written (the live-ledger test only reads)."""

    SECRET = 'sk-ant-api03-SYNTHETIC-OFFLINE-PASS-TEST-000000000000000000000000000000000000-PPPPPPPP'

    @classmethod
    def setUpClass(cls):
        cls.inputs = st.frozen_inputs()
        cls.plan = [s.id for s in st.plan_sends('ordinary_notes', cls.inputs)]

    def setUp(self):
        from .test_provider_campaign import declaration, scratch
        self.root = scratch(self)
        self.declaration = declaration()
        self.campaign = pc.Campaign(self.declaration, self.root)
        self.ledger = self.campaign.ledger
        self.ledger.acquire()
        self.addCleanup(self.ledger.release)
        self.write('model_check')
        self.ledger.write_stage('model_check', 'passed', {'attempt': 1})

    def write(self, stage, send=None, outcome='completed', job_state='succeeded'):
        from .test_provider_campaign import attempt, limits_record, usage
        number = len(self.ledger.rows()) + 1
        record = attempt(number, stage, '0.2332', limits=limits_record(self.declaration))
        if send:
            record['send'] = {'id': send}
        self.ledger.write_attempt(record)
        self.ledger.write_outcome(number, {'class': outcome, 'job_state': job_state,
                                           **({'usage': usage()} if outcome == 'completed' else {})})
        return number

    @staticmethod
    def row(send, number, stops=False, recorded_as=None):
        """A per-send record as Run.finish writes it into the stage summary."""
        return {'send': {'id': send}, 'attempt': number, 'stops_stage': stops, 'recorded_as': recorded_as,
                'findings': [{'code': 'validator_failure', 'why': 'synthetic'}] if stops else []}

    def record_failure(self, plan, rows, not_sent, reasons=('synthetic stop',)):
        self.ledger.write_stage('ordinary_notes', 'failed', {'reasons': list(reasons), 'summary': {
            'plan': plan, 'sends': rows, 'not_sent': not_sent}})

    def reopen(self):
        number = self.ledger.stage_state('ordinary_notes')['failures']
        self.ledger.write_reopen('ordinary_notes', number, {'ledger_attempts': len(self.ledger.rows()),
                                                           'repair_commit': '1' * 40})

    def first_run(self, made, stopper=None, recorded_as='contract', rows_for=None):
        """Attempts for `made` (`stopper`, if made, stopped the stage), failure 1 listing every other planned send as not
        sent, then reopening 1. `rows_for`: the sends the failure records a per-send row for (default: all made)."""
        rows = []
        for send in made:
            number = self.write('ordinary_notes', send)
            if rows_for is None or send in rows_for:
                rows.append(self.row(send, number, send == stopper, recorded_as if send == stopper else None))
        self.record_failure(self.plan, rows, [s for s in self.plan if s not in made])
        self.reopen()

    def run_of(self, records):
        return SimpleNamespace(ledger=self.ledger, stage='ordinary_notes', sends=records, veto_evidence=[],
                               inputs={'freeze': {'manifest_sha256': 'synthetic'}}, root=self.root, secret=self.SECRET,
                               declaration=SimpleNamespace(credential_file=str(self.root / 'no-credential')))

    def pending(self):
        return st.pending_sends(self.campaign, 'ordinary_notes', st.plan_sends('ordinary_notes', self.inputs))

    def clean_remainder(self):
        """The remainder, every send made once and clean, then the stage decision."""
        sends, remainder = self.pending()
        records = [self.row(send.id, self.write('ordinary_notes', send.id)) for send in sends]
        return [s.id for s in sends], st.decide_stage(self.run_of(records), sends, [], [], {'remainder': remainder})

    def assert_cannot_pass(self, result, stoppers):
        self.assertEqual(result['verdict'], 'FAIL')
        state = self.ledger.stage_state('ordinary_notes')
        self.assertEqual(state['state'], 'failed')
        self.assertIsNone(state['passed'])
        failure = state['failed'][-1]
        self.assertEqual(failure['summary']['not_sent'], [])
        self.assertEqual([e['send'] for e in failure['summary']['earlier_stops']], stoppers)
        self.assertTrue(any('cannot pass' in reason and all(s in reason for s in stoppers)
                            for reason in failure['reasons']), failure['reasons'])
        # nothing is left to send: a further reopening has no remainder, and admission refuses the failed stage
        with self.assertRaises(pc.Refused) as caught:
            self.pending()
        self.assertIn('no remainder', str(caught.exception))
        with self.assertRaises(pc.Refused):
            self.campaign.admit('ordinary_notes', '0.01', runner_commit='2' * 40)

    def test_a_clean_remainder_after_the_live_stop_is_failed_never_passed(self):
        # the live shape: 14 default sends and N02:field_relations made, N02:field_relations stopped the stage
        from .test_sonnet5_amendment_plan import UNSENT
        self.first_run([s for s in self.plan if s not in UNSENT], stopper='notes:N02:field_relations')
        sent, result = self.clean_remainder()
        self.assertEqual(sent, UNSENT)                                # (the remainder is unchanged: the six)
        self.assert_cannot_pass(result, ['notes:N02:field_relations'])

    def test_an_unsafe_default_stop_is_never_passed_over(self):
        # refutation F1 scenario B: N05:default stops as UNSAFE; the remainder is everything after it, never N05 itself
        made = self.plan[:self.plan.index('notes:N05:default') + 1]
        self.first_run(made, stopper='notes:N05:default', recorded_as='unsafe')
        sent, result = self.clean_remainder()
        self.assertEqual(sent, self.plan[len(made):])
        self.assert_cannot_pass(result, ['notes:N05:default'])

    def test_a_shrinking_remainder_never_passes(self):
        # refutation F1-REMAINDER-FALSE-PASS (3): each remainder run's first send stops it; the last one runs clean
        from .test_sonnet5_amendment_plan import UNSENT
        self.first_run([s for s in self.plan if s not in UNSENT], stopper='notes:N02:field_relations')
        stoppers = ['notes:N02:field_relations']
        while True:
            sends, remainder = self.pending()
            if len(sends) == 1:
                break
            first = sends[0].id
            number = self.write('ordinary_notes', first, job_state='failed')
            st.decide_stage(self.run_of([self.row(first, number, True, 'contract')]), sends,
                            [f'{first}: synthetic stop'], [s.id for s in sends[1:]], {'remainder': remainder})
            stoppers.append(first)
            self.reopen()
        self.assertEqual(len(stoppers), 6)
        sent, result = self.clean_remainder()
        self.assertEqual(sent, ['notes:N16:field_relations'])
        self.assert_cannot_pass(result, stoppers)

    def test_a_not_sent_outcome_that_stopped_the_stage_is_never_passed_over(self):
        # refutation F1-REMAINDER-FALSE-PASS (4): an attempt that ended not_sent (no request) and stopped the stage
        from .test_sonnet5_amendment_plan import UNSENT
        self.first_run([s for s in self.plan if s not in UNSENT], stopper='notes:N02:field_relations')
        sends, remainder = self.pending()
        number = self.write('ordinary_notes', sends[0].id, outcome='not_sent', job_state='failed')
        st.decide_stage(self.run_of([self.row(sends[0].id, number, True, 'contract')]), sends,
                        [f'{sends[0].id}: ended not_sent'], [s.id for s in sends[1:]], {'remainder': remainder})
        self.reopen()
        sent, result = self.clean_remainder()
        self.assertNotIn(sends[0].id, sent)                           # (it has an attempt: never sent again)
        self.assert_cannot_pass(result, ['notes:N02:field_relations', sends[0].id])

    def test_an_earlier_attempt_no_decision_records_blocks_the_pass(self):
        # an earlier attempt whose run recorded no per-send row (an interrupted or settled run) cannot be shown clean
        defaults = [s for s in self.plan if s.endswith(':default')]
        self.first_run(defaults, rows_for=defaults[1:])
        sent, result = self.clean_remainder()
        self.assertEqual(sent, [s for s in self.plan if s.endswith(':field_relations')])
        self.assert_cannot_pass(result, [defaults[0]])
        failure = self.ledger.stage_state('ordinary_notes')['failed'][-1]
        self.assertIn('no decision of the stage records how it ended', failure['summary']['earlier_stops'][0]['why'])

    def test_a_row_that_names_another_send_or_names_an_attempt_twice_is_not_clean(self):
        # an attempt is clean only when exactly one row names it, for the send the attempt records, not stopping
        defaults = [s for s in self.plan if s.endswith(':default')]
        numbers = [self.write('ordinary_notes', send) for send in defaults]
        rows = [self.row(send, number) for send, number in zip(defaults, numbers)]
        rows[0] = self.row(defaults[1], numbers[0])                    # (attempt 2's row names another send)
        rows.append(self.row(defaults[2], numbers[2]))                 # (attempt 4 named twice)
        self.record_failure(self.plan, rows, [s for s in self.plan if s not in defaults])
        self.reopen()
        _, result = self.clean_remainder()
        self.assert_cannot_pass(result, [defaults[0], defaults[2]])
        whys = [e['why'] for e in self.ledger.stage_state('ordinary_notes')['failed'][-1]['summary']['earlier_stops']]
        self.assertEqual(whys, ['its decision records it for another send',
                                'more than one decision of the stage records it'])

    def test_a_stop_before_any_attempt_still_lets_the_remainder_pass(self):
        # nothing was sent for the stopping send (stopped before its attempt was written): it is in the remainder, and
        # a remainder that runs clean completes the whole plan, each send made once — a pass that was earned
        defaults = [s for s in self.plan if s.endswith(':default')]
        self.first_run(defaults)
        sent, result = self.clean_remainder()
        self.assertEqual(sent, [s for s in self.plan if s.endswith(':field_relations')])
        self.assertEqual(result['verdict'], 'PASS', result['reasons'])
        state = self.ledger.stage_state('ordinary_notes')
        self.assertEqual(state['state'], 'passed')
        self.assertEqual(state['passed']['summary']['earlier_stops'], [])
        made = [a['send']['id'] for a, _ in self.ledger.rows() if a['stage'] == 'ordinary_notes']
        self.assertEqual(sorted(made), sorted(self.plan))              # (every planned send exactly once)

    def test_the_live_ledgers_earlier_stops_are_the_stops_its_failures_record(self):
        # The live ledger, read-only (the stage functions read it; nothing is written, no lock is taken). The expected
        # stops are read from the ledger's OWN stage-failure files, not hard-coded (refutation of dfde4fc8, F7: a later
        # recorded stop — attempt 20 — failed a test that named only attempt 17): every per-send row a failure records
        # as stopping the stage, and every attempt of the stage that no row names. The stops already recorded when this
        # test was written can never disappear from the ledger (it only appends).
        ledger = pc.Ledger(pc.LIVE_ROOT / 'ledger')
        if not ledger.dir.is_dir():
            self.skipTest('no live ledger on this host')
        for stage, recorded_before in (('mapping', [('mapping:f1-guidance-confirmation', 2)]),
                                       ('ordinary_notes', [('notes:N02:field_relations', 17),
                                                           ('notes:N13:field_relations', 20)])):
            with self.subTest(stage=stage):
                rows = {}
                for path in sorted(ledger.dir.glob(f'stage-{stage}-failed-*.json')):
                    for row in (json.loads(path.read_text()).get('summary') or {}).get('sends') or []:
                        rows.setdefault(row['attempt'], []).append(row)
                attempts = sorted((json.loads(path.read_text()) for path in ledger.dir.glob('[0-9][0-9][0-9]-attempt.json')),
                                  key=lambda a: a['number'])
                expected = [(a['send']['id'], a['number']) for a in attempts if a.get('stage') == stage
                            and (len(rows.get(a['number'], [])) != 1 or rows[a['number']][0]['stops_stage'] is not False)]
                self.assertTrue(set(recorded_before) <= set(expected), expected)
                self.assertEqual([(e['send'], e['attempt']) for e in st.earlier_stops(ledger, stage)], expected)


class InterruptionTests(unittest.TestCase):
    """Refutation F2: an ordinary exception inside a send, after its attempt was written, no longer fails the stage on
    the spot (which left a failure that recorded nothing it did not send, so a reopening had no remainder and the stage
    stuck open): the attempt gets its outcome, and the stage decision records the failure WITH the sends not made. An
    interruption that ends the process still fails the stage at once (it cannot be decided later)."""

    def setUp(self):
        from .test_provider_campaign import attempt, declaration, limits_record, scratch, usage
        self.inputs = st.frozen_inputs()
        self.plan = st.plan_sends('ordinary_notes', self.inputs)
        self.root = scratch(self)
        self.campaign = pc.Campaign(declaration(), self.root)
        self.ledger = self.campaign.ledger
        self.ledger.acquire()
        self.addCleanup(self.ledger.release)
        self.ledger.write_attempt(attempt(1, limits=limits_record(declaration())))
        self.ledger.write_outcome(1, {'class': 'completed', 'usage': usage()})
        self.ledger.write_stage('model_check', 'passed', {'attempt': 1})
        record = attempt(2, 'ordinary_notes', '0.2332', limits=limits_record(declaration()))
        record['send'] = self.plan[0].record()
        self.ledger.write_attempt(record)                          # (in flight: no outcome yet)
        self.attempt = record
        self.run = SimpleNamespace(ledger=self.ledger, stage='ordinary_notes', sends=[], veto_evidence=[],
                                   inputs={'freeze': {'manifest_sha256': 'synthetic'}}, root=self.root,
                                   secret=StagePassTests.SECRET,
                                   declaration=SimpleNamespace(credential_file=str(self.root / 'no-credential')))

    def test_an_ordinary_exception_leaves_the_decision_and_its_remainder_to_the_stage(self):
        record, stops = st.Run.interrupted(self.run, self.plan[0], self.attempt, self.root,
                                           pc.Refused('The frozen replay refused or failed (1)'))
        self.assertTrue(stops)
        self.assertEqual(self.ledger.rows()[1][1]['class'], 'uncertain')          # (the outcome is recorded)
        self.assertEqual(self.ledger.stage_state('ordinary_notes')['state'], 'open')   # (not failed on the spot)
        not_sent = [s.id for s in self.plan[1:]]
        result = st.decide_stage(self.run, self.plan, ['notes:N01:default: interrupted'], not_sent, {})
        self.assertEqual(result['verdict'], 'FAIL')
        failure = self.ledger.stage_state('ordinary_notes')['failed'][-1]
        self.assertEqual((failure['summary']['not_sent'], failure['summary']['sends'][0]['recorded_as']),
                         (not_sent, 'interrupted'))
        self.ledger.write_reopen('ordinary_notes', 1, {'ledger_attempts': 2, 'repair_commit': '1' * 40})
        sends, remainder = st.pending_sends(self.campaign, 'ordinary_notes', self.plan)
        self.assertEqual([s.id for s in sends], not_sent)                    # (the stage can go on, once repaired)
        self.assertEqual(remainder['already_made'], [self.plan[0].id])

    def test_an_interruption_that_ends_the_process_still_fails_the_stage_at_once(self):
        with self.assertRaises(KeyboardInterrupt):
            st.Run.interrupted(self.run, self.plan[0], self.attempt, self.root, KeyboardInterrupt())
        state = self.ledger.stage_state('ordinary_notes')
        self.assertEqual(state['state'], 'failed')
        self.assertNotIn('summary', state['failed'][-1])
        # (that failure cannot say what it did not send: a reopening is refused for it — test_provider_campaign
        # ReopenTests — rather than leaving the stage open with nothing it could send)
        with self.assertRaises(pc.Refused) as caught:
            st.pending_sends(self.campaign, 'ordinary_notes', self.plan)
        self.assertIn('no readable list', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
