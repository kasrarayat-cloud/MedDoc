"""The stage runner's pure parts (ops/sonnet5_stages.py), offline, without a database: the fixed plans, the mapping
unsafe rules, the notes field classes, the relations-path stop rule, the provider-selection reader and the offline
`plan` command. The end-to-end sends are in test_sonnet5_stages.py (QA server)."""
import json
import os
import subprocess
import sys
import unittest
import unittest.mock
from decimal import Decimal
from pathlib import Path

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

    def test_plan_prints_every_send_its_bound_and_the_worst_case_against_the_limits(self):
        # (the live ledger, read-only: a stage whose latest decision is a failure plans only that failure's unsent
        # sends; one never failed plans all of them)
        for stage, count in (('mapping', 10),):
            with self.subTest(stage=stage):
                report = self.plan(stage)
                full = [s.id for s in st.plan_sends(stage, st.frozen_inputs())]
                if report['remainder'] is not None:
                    count = len(report['remainder']['sends'])
                    self.assertEqual([row['id'] for row in report['order']], report['remainder']['sends'])
                    self.assertTrue(set(report['remainder']['sends']) <= set(full))
                    self.assertFalse(set(report['remainder']['sends']) & set(report['remainder']['already_made']))
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
        cls.scratch = Path(tempfile.mkdtemp(prefix='stage-read-back-'))
        cls.inputs = st.frozen_inputs()
        cls.forms = st.build_forms(cls.scratch / 'forms', 'ordinary_notes', cls.inputs)
        cls.cases = {c['id']: c for c in cls.inputs['cases']['cases']}

    @classmethod
    def tearDownClass(cls):
        __import__('shutil').rmtree(cls.scratch, True)

    def case(self, case_id):
        """(the form, its fields, what a clinician saved: each desired-supported field its first desired text, every
        other field left blank and reviewed)."""
        case = self.cases[case_id]
        fields = self.inputs['cases']['forms'][case['form']]['fields']
        saved = {}
        for f in fields:
            ae = case['fields'][f['key']]['app_adoption_expectation']
            if ae['desired'] == 'supported':
                saved[f['key']] = {'status': 'supported', 'text': ae['desired_texts'][0], 'reviewed': True}
            else:
                saved[f['key']] = {'status': 'left_blank', 'text': '', 'reviewed': True}
        return self.forms[case['form']], fields, saved

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
        original, fields, saved = self.case('N06')
        self.assertEqual(saved['v3_10']['status'], 'left_blank')
        exported = self.export(original, fields, {**v3_mapping.fill_answers(fields, saved), 'v3_10': True})
        result = st.export_read_back(original, exported, fields, saved)
        self.assertEqual(self.problems(result), ['v3_10'])

    def test_a_checkbox_the_blank_form_prints_ticked_follows_the_stated_rule(self):
        # core.v3_mapping.fill_answers: a checkbox reviewed and left blank is exported UNTICKED even when the blank form
        # prints it ticked; one never reviewed keeps what the form prints. (A synthetic variant of r1-11 whose consent
        # box is printed ticked, inspected afresh.)
        from core import v3_mapping
        from documents import word_v3 as w
        original = rezip(self.forms['r1-11'], 'word/document.xml', replaced_once(
            '<w:t>☐</w:t></w:r><w:r><w:t xml:space="preserve"> Consent obtained'.encode(),
            '<w:t>☒</w:t></w:r><w:r><w:t xml:space="preserve"> Consent obtained'.encode()))
        fields = w.inspect(original)['fields']
        box = next(f for f in fields if f['kind'] == 'checkbox')
        self.assertEqual(box.get('printed_ticked'), [0])
        saved = {f['key']: {'status': 'left_blank', 'text': '', 'reviewed': True} for f in fields}
        unticked = self.honest(original, fields, saved)
        result = st.export_read_back(original, unticked, fields, saved)
        self.assertEqual((result['problems'], result['fields'][box['key']]['read']), ([], [False]))
        kept = self.export(original, fields, {k: v for k, v in v3_mapping.fill_answers(fields, saved).items()
                                              if k != box['key']})
        self.assertEqual(self.problems(st.export_read_back(original, kept, fields, saved)), [box['key']])
        never_reviewed = {**saved, box['key']: {'status': 'held', 'text': '', 'reviewed': False}}
        self.assertTrue(st.export_read_back(original, kept, fields, never_reviewed)['passed'])
        self.assertEqual(self.problems(st.export_read_back(original, unticked, fields, never_reviewed)), [box['key']])

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


class RawSelectionTests(unittest.TestCase):
    """C2: the model's own selection is read from the provider message only (never from the adopted answers)."""

    def test_a_message_without_exactly_one_text_block_is_refused(self):
        for message in ({'content': []}, {'content': [{'type': 'text', 'text': '{}'}, {'type': 'text', 'text': '{}'}]}):
            with self.subTest(message=message), self.assertRaises(pc.Refused):
                st.raw_selection(message, [], '', 'default')

    def test_the_keyed_relations_answer_reads_into_the_replays_unchanged_shape(self):
        # (N13's frozen form and notes; the keyed wire the repaired contract returns, members in any order)
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
        message = {'content': [{'type': 'text', 'text': json.dumps(body)}]}
        selection = st.raw_selection(message, fields, case['notes'], 'field_relations')
        self.assertEqual(set(selection), {first, other})
        self.assertEqual(selection[first], {'unit_ids': [ids[0]], 'conflict': False, 'options': [],
                                            'relations': {units[1]['quote']: 'contrary'}})
        self.assertEqual(selection[other], {'unit_ids': [], 'conflict': True, 'options': [], 'relations': {}})
        # (the frozen replay's own reader of this shape: offline_replay adopt(), unchanged)
        for bad in ({'fields': [{'key': first, 'unit_ids': [], 'conflict': False, 'option_ids': [], 'context': []}]},
                    {'fields': {first: body['fields'][first]}}):
            with self.subTest(bad=bad), self.assertRaises(pc.Refused):
                st.raw_selection({'content': [{'type': 'text', 'text': json.dumps(bad)}]}, fields, case['notes'],
                                 'field_relations')
        default = {'fields': [{'key': first, 'unit_ids': [ids[0]], 'conflict': False}]}
        self.assertEqual(st.raw_selection({'content': [{'type': 'text', 'text': json.dumps(default)}]}, fields,
                                          case['notes'], 'default'),
                         {first: {'unit_ids': [ids[0]], 'conflict': False}})


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


if __name__ == '__main__':
    unittest.main()
