"""DECISIONS D243 (docs/gemini-migration/DECISIONS.md, 2026-11-14; step q02): the class B and class C test ids of the
waves 5-6 merge gate, and the test-only v2 builder their class C rows come from (tests/v2_replay.py over
tests/v2_documents.py). SYNTHETIC: fictional documents and clinicians; nothing is sent.

What is proved here (the step's done-when):
- ClassCTests: every one of the 40 class C ids resolves to a test method marked ``v2_replay.applied``, in a class whose
  set-up starts design v2's path in replay for a marked test instead of the v1 chain (tests.test_pipeline_api.
  RecordedInterpretation, tests.test_pipeline_assess_events.EventsCase); no class C test names the v1 chain;
- PathTests: on that path the v1 chain's seam is closed (jobs._v1_chain False, the retired code objects armed), v1's
  interpreter is refused, design v2's interpreter is the scripted one, and an unmarked test of the same class still
  takes the v1 chain (the control); the checks made when a marked test ends fail on a document asked for with no answer
  and on a REAL v1 row - a cpt-studio-events@1 assessment or a gemini-events@1 inventory - and pass beside a legacy
  assessment and a v2 inventory (the control; refute-q02-r1 Q02-5);
- S11Tests (DECISIONS D243 with D251: O20's R9): the nine S11 tests of tests/test_readers_dispatch.py run under
  sentinel.strict(..., retired=True), every one that reads an encounter on design v2's path, beside R9's positive
  control (a planted RETIRED call trips the instrument); no strict() there is left as v1's instrument;
- ClassBTests: the 19 class B subtests are gone from the five retired-module suites, each suite's docstring cites
  D243, and nothing of those suites but the removed units changed (each suite's other tests are still there);
- DocumentTests: each v2 document is its v1 fixture document with one line added (its clinician), and each answer is
  read by pass 1's strict reader and checked with no finding; no Corti quote differs from the v1 fixture's - the
  denial's 45385 quote is v1's again, its stop included (DECISIONS D261: C-10 is given the kept evidence's
  letter-or-digit runs; refute-q02-r2 Q02R2-3);
- InterpreterTests: the registry answers exactly the text registered, the same answer twice is one registration and
  another answer for a registered text is refused.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import textwrap
from pathlib import Path
from typing import Any

from django.db import transaction
from django.test import SimpleTestCase, TestCase

from studio import interpretation, jobs, models
from studio.interpretation import adapter, sentinel
from studio.interpretation.contract import checks, extract_read, segment
from tests import v2_documents, v2_replay
from tests.support import pipeline_factories as pf

APP = Path(__file__).resolve().parents[1]

# D243's class C ids (build-v2/w56r/final/logs/gate2-classes.txt, "Q-02 C"): module, class, method
CLASS_C = (
    ('tests.test_cux_queue_recheck', 'RecheckTests',
     'test_a_re_check_is_offered_where_one_can_be_asked_and_only_to_a_member_who_may_ask'),
    ('tests.test_cux_queue_recheck', 'RecheckTests', 'test_no_re_check_is_offered_where_nothing_is_open_or_while_processing'),
    ('tests.test_cux_r3_progress', 'QueuedRecheckTests', 'test_a_re_check_of_what_is_still_open_waits_for_the_next_step'),
    ('tests.test_harness2_r2_parity', 'ConfiguredRepersistTests',
     'test_a_resume_after_the_stale_sweep_keeps_the_recorded_final_assessment'),
    ('tests.test_harness2_r4_conf', 'CodeQuestionTests',
     'test_a_question_about_a_code_holds_that_code_which_can_still_be_rejected'),
    ('tests.test_harness2_r5_row', 'AfterRejectionTests',
     'test_every_code_rejected_and_the_encounter_reviewed_the_row_says_only_what_is_open'),
    ('tests.test_harness2_r5_row', 'CortiOnlyTests',
     'test_a_rejected_code_whose_question_is_still_open_the_row_says_only_what_is_open'),
    ('tests.test_pipeline_api', 'PipelineApiTests', 'test_addendum_creates_revision_and_invalidates_decisions'),
    ('tests.test_pipeline_assess_events', 'AgainTests',
     'test_a_retained_re_assessment_re_reads_the_final_by_id_and_sends_nothing'),
    ('tests.test_pipeline_assess_events', 'AgainTests',
     'test_decisions_carry_across_an_answer_recompute_and_nothing_is_sent'),
    ('tests.test_readers_dispatch', 'CustomerNamesNoProviderTests',
     'test_the_customer_json_and_exports_of_a_new_path_encounter_name_no_provider_or_model'),
    ('tests.test_readers_dispatch', 'GateUnderTheLockTests',
     'test_a_member_answer_and_its_withdrawal_are_decided_from_the_locked_row'),
    ('tests.test_readers_dispatch', 'NewPathConsumerTests', 'test_a_decision_and_its_readers_run_no_legacy_code'),
    ('tests.test_readers_dispatch', 'NewPathConsumerTests',
     'test_a_reinstated_exclusion_holds_the_base_and_its_coverage_is_read_again_with_no_legacy_code'),
    ('tests.test_readers_dispatch', 'NewPathConsumerTests', 'test_every_write_of_a_member_runs_no_legacy_code'),
    ('tests.test_readers_dispatch', 'ScopeTests', 'test_a_process_that_cannot_count_refuses_new_path_writes'),
    ('tests.test_readers_dispatch', 'ScopeTests', 'test_a_read_that_ran_legacy_code_records_the_trip_and_still_answers'),
    ('tests.test_readers_dispatch', 'ScopeTests', 'test_a_request_naming_a_new_path_encounter_runs_under_new_path'),
    ('tests.test_readers_dispatch', 'ScopeTests', 'test_a_request_naming_no_encounter_runs_under_other_and_labels_each_row'),
    ('tests.test_readers_dispatch', 'ScopeTests', 'test_the_decision_gate_refuses_and_records_nothing_but_the_trip'),
    ('tests.test_readers_dispatch', 'ScopeTests', 'test_the_member_answer_gate_refuses_and_records_nothing_but_the_trip'),
    ('tests.test_readers_dispatch', 'SwitchBackHazardTests',
     'test_a_reinstatement_on_a_new_path_assessment_is_named_until_it_is_revoked'),
    ('tests.test_readers_dispatch', 'SwitchBackHazardTests',
     'test_d59_a_reinstated_code_approved_afterwards_stays_named_until_its_decision_is_revoked'),
    ('tests.test_readers_dispatch', 'SwitchBackHazardTests',
     'test_d59_a_reinstated_code_approved_with_its_base_undecided_stays_named_and_a_rejection_clears_it'),
    ('tests.test_readers_dispatch', 'SwitchBackHazardTests',
     'test_d59_an_image_without_review_reinstated_codes_reads_the_same_rule'),
    ('tests.test_readers_dispatch', 'SwitchBackHazardTests',
     'test_d59_the_note_counts_the_new_path_encounters_holding_an_excluded_code_a_reviewer_can_reinstate'),
    ('tests.test_readers_dispatch', 'SwitchBackHazardTests',
     'test_touched_lists_an_encounter_only_for_a_record_created_since'),
    ('tests.test_readers_dispatch', 'UnreadableRecordTests',
     'test_a_reinstated_codes_coverage_that_cannot_be_re_run_blocks_what_it_says_it_blocks'),
    ('tests.test_readers_dispatch', 'UnreadableRecordTests',
     'test_d50_no_decision_but_a_revoke_is_taken_on_a_record_this_release_cannot_read'),
    ('tests.test_readers_dispatch', 'UnreadableRecordTests', 'test_readiness_blocks_and_the_member_is_told'),
    ('tests.test_repairs_7c8_p1reports', 'PendingReviewSaysWhatIsMissingTests',
     'test_a_partly_decided_set_counts_what_still_needs_a_decision'),
    ('tests.test_repairs_7c8_p1reports', 'PendingReviewSaysWhatIsMissingTests',
     'test_every_proposal_decided_is_never_told_it_needs_a_decision'),
    ('tests.test_repairs_ec5_reportruns', 'HeldRunReadsAsHeldTests',
     'test_a_member_date_held_after_a_finished_request_is_held_not_failed'),
    ('tests.test_repairs_ec5_reportruns', 'HeldRunReadsAsHeldTests', 'test_a_member_date_held_at_upload_is_held_not_failed'),
    ('tests.test_repairs_ec5_reportruns', 'HeldRunReadsAsHeldTests',
     'test_control_a_request_that_could_not_be_built_still_reads_failed'),
    ('tests.test_repairs_gi2_reports', 'TheOriginOfASecondReviewCodeIsSaidTests',
     'test_a_rejected_second_review_code_keeps_its_origin_line'),
    ('tests.test_repairs_gi2_reports', 'TheOriginOfASecondReviewCodeIsSaidTests',
     'test_control_a_rejected_primary_code_has_none_and_the_approved_one_keeps_its_own'),
    ('tests.test_repairs_gi2_reports', 'TheOriginOfASecondReviewCodeIsSaidTests',
     'test_the_screen_marks_the_alternatives_the_second_review_listed'),
    ('tests.test_repairs_r3_pipeline', 'NonStringIdentifiersTests', 'test_a_string_identifier_still_works'),
    ('tests.v2.test_update_api', 'TriggerV1ApiTests',
     'test_u10_during_the_update_a_decision_is_refused_and_after_it_one_answers_201'),
)
V1_NAMES = ('v1_chain', 'retired_unarmed', 'RecordedReplayInterpreter', 'get_interpreter', 'build_request')


def method_of(module, cls, name):
    return getattr(getattr(importlib.import_module(module), cls), name)


class ClassCTests(SimpleTestCase):
    def test_there_are_forty_ids_each_marked_and_taken_off_the_v1_chain_by_its_class(self):
        from tests.test_pipeline_api import RecordedInterpretation
        from tests.test_pipeline_assess_events import EventsCase

        self.assertEqual(len(CLASS_C), 40)
        self.assertEqual(len(set(CLASS_C)), 40)
        for module, cls, name in CLASS_C:
            with self.subTest(test=f'{module}.{cls}.{name}'):
                test_class = getattr(importlib.import_module(module), cls)
                self.assertTrue(getattr(method_of(module, cls, name), v2_replay.MARK, False))
                self.assertTrue(issubclass(test_class, (RecordedInterpretation, EventsCase)))

    def test_no_class_c_test_names_the_v1_chain(self):
        for module, cls, name in CLASS_C:
            source = textwrap.dedent(inspect.getsource(method_of(module, cls, name)))
            names = {node.id for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Name)}
            names |= {node.attr for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Attribute)}
            with self.subTest(test=f'{module}.{cls}.{name}'):
                self.assertEqual(sorted(names & set(V1_NAMES)), [])

    def test_the_mark_reads_the_running_method_only(self):
        class Marked(SimpleTestCase):
            @v2_replay.applied
            def test_marked(self):
                pass

            def test_unmarked(self):
                pass

        self.assertTrue(v2_replay.marked(Marked('test_marked')))
        self.assertFalse(v2_replay.marked(Marked('test_unmarked')))


class PathTests(TestCase):
    def test_on_the_path_the_v1_chain_is_closed_and_v1s_interpreter_refused(self):
        interpreter = v2_replay.start(self, ((v2_documents.TWO_PROCEDURES, v2_documents.two_procedures_answer),))
        self.assertFalse(jobs._v1_chain())
        self.assertTrue(sentinel.retired_armed())
        self.assertIs(adapter.get_interpreter_v2(), interpreter)
        with self.assertRaises(AssertionError) as refused:
            adapter.get_interpreter()
        self.assertEqual(str(refused.exception), v2_replay.V1_BUILT)
        self.assertNotEqual(interpretation.HEALTH_THRESHOLDS_SHA256, '')

    def test_the_control_an_unmarked_test_of_a_class_c_class_keeps_the_v1_chain(self):
        from tests.test_pipeline_api import PipelineApiTests

        case = PipelineApiTests('test_an_upload_here_takes_the_production_chain')
        self.assertFalse(v2_replay.marked(case))
        case._set_up_the_recorder()
        try:
            self.assertTrue(jobs._v1_chain())
            self.assertFalse(sentinel.retired_armed())
        finally:
            case.doCleanups()
        marked = PipelineApiTests('test_addendum_creates_revision_and_invalidates_decisions')
        self.assertTrue(v2_replay.marked(marked))

    def ended(self, interpreter):
        """The checks a marked test's end makes, run on a stand-in test case: (failed, message)."""
        outer = self

        class Case:
            def fail(self, message):
                raise AssertionError(message)

            def assertEqual(self, first, second, message=None):  # noqa: N802 - unittest's naming
                outer.assertEqual(first, second, message)

        try:
            v2_replay._ended(Case(), interpreter)
        except AssertionError as caught:
            return True, str(caught)
        return False, ''

    def test_the_end_fails_on_a_document_asked_for_with_no_answer(self):
        interpreter = v2_replay._interpreter_class()()
        self.assertEqual(self.ended(interpreter), (False, ''))
        interpreter.unrecorded.append(v2_documents.v1_twin(v2_documents.TWO_PROCEDURES))
        failed, said = self.ended(interpreter)
        self.assertTrue(failed)
        self.assertIn('no synthetic answer', said)

    def ended_with(self, *rows):
        """``ended`` with ``rows`` (row makers) written first and rolled back after: (failed, message)."""
        class Rollback(Exception):
            pass

        try:
            with transaction.atomic():
                for make in rows:
                    make()
                raise Rollback(self.ended(v2_replay._interpreter_class()()))
        except Rollback as caught:
            return caught.args[0]

    def rows(self):
        """Row makers over one synthetic legacy encounter: an assessment at an engine version, an event inventory at an
        interpretation version - REAL rows (refute-q02-r1 Q02-5: a mocked filter cannot fail for a wrong version)."""
        s = pf.scenario()
        routing, run = pf.routing(s.revision), pf.provider_run(s.encounter, s.revision)

        def assessment(version):
            return lambda: models.Assessment.objects.create(
                encounter=s.encounter, revision=s.revision, context=s.context, routing=routing,
                profiles_version='synthetic', engine_version=version, sha256='0' * 64)

        def inventory(version, inventory_version):
            return lambda: models.EventInventory.objects.create(
                encounter=s.encounter, revision=s.revision, provider_run=run, interpretation_version=version,
                inventory_version=inventory_version, text_sha256='0' * 64, request_sha256='0' * 64,
                response_sha256='0' * 64, state=models.EventInventory.READ, events={}, encounter_facts={},
                open_questions=[], verification={}, sha256='0' * 64)

        return assessment, inventory

    def test_the_end_fails_on_a_v1_row(self):
        assessment, inventory = self.rows()
        for what, row in (('a cpt-studio-events@1 assessment', assessment(interpretation.ENGINE_VERSION)),
                          ('a gemini-events@1 inventory', inventory(interpretation.INTERPRETATION_VERSION,
                                                                     interpretation.INVENTORY_VERSION))):
            with self.subTest(row=what):
                failed, said = self.ended_with(row)
                self.assertTrue(failed, what)
                self.assertIn("a v1 row was written on design v2's path in replay", said)

    def test_the_control_the_end_passes_beside_a_legacy_assessment_and_a_v2_inventory(self):
        assessment, inventory = self.rows()
        self.assertEqual(self.ended_with(assessment(pf.ENGINE_VERSION),
                                         assessment(interpretation.ENGINE_VERSION_V2),
                                         inventory(interpretation.INTERPRETATION_PAIR,
                                                   interpretation.INVENTORY_VERSION_V2)), (False, ''))


# DECISIONS D243 with D251 ("O20's R9 is D243"; step 6a's request R9, refutation 6a-r1 F2): the nine S11 tests of
# tests/test_readers_dispatch.py that tests/test_guard_static.py's STRICT_V1_INSTRUMENT pinned as v1's instrument (the
# default strict, the RETIRED kind unarmed), each now under strict(..., retired=True) and, but the re-homed helpers'
# check (which reads no encounter), on design v2's path; and the positive control R9 adds (class, method)
S11 = (
    ('RehomedHelperTests', 'test_their_code_lives_in_code_shapes_and_is_never_denied'),
    ('NewPathConsumerTests', 'test_every_consumer_reads_a_new_path_encounter_with_no_legacy_execution'),
    ('NewPathConsumerTests', 'test_the_instrument_is_live_a_planted_legacy_call_in_a_consumer_trips_it'),
    ('NewPathConsumerTests', 'test_a_decision_and_its_readers_run_no_legacy_code'),
    ('NewPathConsumerTests', 'test_a_member_answer_its_recompute_and_its_withdrawal_run_no_legacy_code'),
    ('NewPathConsumerTests',
     'test_a_reinstated_exclusion_holds_the_base_and_its_coverage_is_read_again_with_no_legacy_code'),
    ('NewPathConsumerTests', 'test_every_write_of_a_member_runs_no_legacy_code'),
    ('NewPathParticipantConsumerTests', 'test_the_final_assessment_with_peer_reviews_runs_no_legacy_code'),
    ('NewPathUnlistedCodeTests',
     'test_the_unlisted_sentence_is_said_on_the_console_and_in_the_report_with_no_legacy_code'),
)
S11_RETIRED_CONTROL = ('NewPathConsumerTests', 'test_the_instrument_is_live_a_planted_retired_call_in_a_consumer_trips_it')
S11_NO_ENCOUNTER = ('RehomedHelperTests', 'test_their_code_lives_in_code_shapes_and_is_never_denied')


def strict_calls(function: ast.FunctionDef) -> list:
    """Each ``sentinel.strict(...)`` call in ``function``: whether it passes retired=True."""
    return [any(item.arg == 'retired' and isinstance(item.value, ast.Constant) and item.value.value is True
                for item in node.keywords)
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'strict'
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'sentinel']


class S11Tests(SimpleTestCase):
    def test_every_s11_check_counts_the_retired_kind_and_reads_design_v2s_rows(self):
        from tests.test_guard_static import v1_instrument_uses
        from tests.test_pipeline_assess_events import EventsCase

        path = APP / 'tests' / 'test_readers_dispatch.py'
        source = path.read_text(encoding='utf-8')
        self.assertEqual(v1_instrument_uses(source), [])  # no strict() there is v1's instrument
        tree = ast.parse(source)
        methods = {(cls.name, item.name): item for cls in tree.body if isinstance(cls, ast.ClassDef)
                   for item in cls.body if isinstance(item, ast.FunctionDef)}
        module = importlib.import_module('tests.test_readers_dispatch')
        self.assertEqual(len(S11), 9)
        every = [(key, call) for key, item in methods.items() for call in strict_calls(item)]
        self.assertEqual({key for key, _ in every}, {*S11, S11_RETIRED_CONTROL})  # no other strict() in the module
        for key in (*S11, S11_RETIRED_CONTROL):
            cls, name = key
            with self.subTest(test=f'{cls}.{name}'):
                calls = strict_calls(methods[key])
                self.assertTrue(calls)
                self.assertTrue(all(calls), calls)  # retired=True on every strict() of the test
                method = getattr(getattr(module, cls), name)
                if key == S11_NO_ENCOUNTER:
                    self.assertFalse(issubclass(getattr(module, cls), EventsCase))  # reads no encounter
                    continue
                self.assertTrue(getattr(method, v2_replay.MARK, False))  # its rows: design v2's path in replay
                self.assertTrue(issubclass(getattr(module, cls), EventsCase))

    def test_the_retired_control_plants_the_sentinels_own_retired_probe(self):
        source = textwrap.dedent(inspect.getsource(getattr(
            importlib.import_module('tests.test_readers_dispatch').NewPathConsumerTests, S11_RETIRED_CONTROL[1])))
        self.assertIn('sentinel.PROBE_CALL_RETIRED', source)
        module, name, _ = sentinel.PROBE_CALL_RETIRED
        self.assertIn(module, sentinel.RETIRED_MODULES)  # a RETIRED module's function, not a legacy one
        self.assertTrue(callable(getattr(importlib.import_module(module), name)))


# the five suites, their removed units and a test each keeps (nothing else changed)
CLASS_B = {
    'tests/test_interpretation_r3_integration_d87.py': {
        'gone': ('D87PossibleExaminationIsNoFactSource',
                 'test_d87_43253_beside_a_possible_examination_naming_the_pancreas_asks_the_structure_examined',
                 'test_d87_43240_beside_a_possible_examination_naming_the_pancreas_asks_the_structure_examined'),
        'kept': ('test_d87_no_stent_was_placed_beside_the_stent_placement_asks_conflict_stent',
                 'test_d87_a_broad_denial_beside_a_possible_examination_asks_its_scope'), 'subtests': 12},
    'tests/test_interpretation_r5c_egd.py': {
        'gone': ('test_d142_the_eus_gastroenterostomy_stent_beside_43259_is_listed',),
        'kept': ('test_d142_rf5_a_stent_removal_beside_43239_is_listed_not_covered',
                 'test_d142_never_an_act_a_proposed_code_covers'), 'subtests': 3},
    'tests/test_interpretation_r5c_currency.py': {
        'gone': ('test_d134_the_read_time_overlay_keeps_the_assessments_reading',),
        'kept': ('test_d130_record_a_possible_procedure_with_a_documented_statement_releases_the_e_m',), 'subtests': 2},
    'tests/test_interpretation_r5_egd.py': {
        'gone': ('test_d118_the_competing_hold_is_released_once_the_other_code_is_rejected',),
        'kept': ('test_d118_a_savary_dilation_whose_site_is_unread_competes',), 'subtests': 1},
    'tests/test_interpretation_r5d_currency.py': {
        'gone': ('test_d144_the_other_readers_of_labels_and_possible_are_unchanged',),
        'kept': ('test_d144_recorded_an_act_of_kind_other_whose_procedure_is_unknown',), 'subtests': 1},
}


class ClassBTests(SimpleTestCase):
    def test_the_nineteen_subtests_are_gone_and_each_suite_cites_d243(self):
        self.assertEqual(sum(item['subtests'] for item in CLASS_B.values()), 19)
        for path, item in CLASS_B.items():
            tree = ast.parse((APP / path).read_text(encoding='utf-8'))
            defined = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
            with self.subTest(suite=path):
                self.assertIn('DECISIONS D243', ast.get_docstring(tree))
                self.assertEqual(sorted(set(item['gone']) & defined), [])
                self.assertEqual(sorted(set(item['kept']) - defined), [])

    def test_the_rf5_test_keeps_its_listing_subtest_and_loses_only_the_read_time_one(self):
        source = (APP / 'tests/test_interpretation_r5c_egd.py').read_text(encoding='utf-8')
        self.assertNotIn("subTest(part='and at read time')", source)
        self.assertIn("subTest(part='listed not covered, with the second-review mark')", source)


V1_DOCUMENTS = {
    'TWO_PROCEDURES': lambda: importlib.import_module('tests.test_pipeline_assess_events').two_procedures()[1],
    'DENIED_REMOVAL': lambda: importlib.import_module('tests.test_readers_dispatch').denied_removal()[1],
    'OFFICE_NOTE': lambda: importlib.import_module('tests.test_pipeline_api').OFFICE_NOTE,
    'COLONOSCOPY': lambda: importlib.import_module('tests.test_repairs_7c8_p1reports').COLONOSCOPY,
    'TWO_EXTENTS': lambda: importlib.import_module('tests.test_harness2_pipeline').TWO_EXTENTS,
    'COLON': lambda: importlib.import_module('tests.test_harness2_r5_row').COLON,
}
ANSWERS = {'TWO_PROCEDURES': v2_documents.two_procedures_answer, 'DENIED_REMOVAL': v2_documents.denied_removal_answer,
           'OFFICE_NOTE': v2_documents.office_note_answer, 'COLONOSCOPY': v2_documents.colonoscopy_answer,
           'TWO_EXTENTS': v2_documents.two_extents_answer, 'COLON': v2_documents.colon_answer}


class DocumentTests(SimpleTestCase):
    def test_each_v2_document_is_its_v1_document_with_its_clinician_named(self):
        for name, v1 in V1_DOCUMENTS.items():
            text = getattr(v2_documents, name)
            with self.subTest(document=name):
                self.assertEqual(v2_documents.v1_twin(text), v1())
                added = [line for line in text.split('\n') if line not in v1().split('\n')]
                self.assertIn(added, ([v2_documents.ENDOSCOPIST], [v2_documents.CLINICIAN]))

    def test_each_answer_is_read_strictly_and_checked_with_no_finding(self):
        import json

        for name, build in ANSWERS.items():
            text = getattr(v2_documents, name)
            found = extract_read.read(json.dumps(build()), len(segment.units(text)))
            with self.subTest(document=name):
                self.assertNotIsInstance(found, extract_read.Refusal)
                self.assertEqual(checks.check(text, (), found).findings, {})

    def test_each_providers_quote_is_in_its_v2_document(self):
        for text, codes in ((v2_documents.TWO_PROCEDURES, v2_documents.TWO_CODES),
                            (v2_documents.DENIED_REMOVAL, v2_documents.DENIED_CODES)):
            for code, quote in codes:
                with self.subTest(code=code):
                    self.assertIn(quote, text)
        self.assertIn(v2_documents.VISIT_TIME, v2_documents.OFFICE_NOTE)

    def test_no_provider_quote_differs_from_v1(self):
        # DECISIONS D261 (2026-11-14; step q02's Q3, refute-q02-r2 Q02R2-3): no Corti quote of the class C fixtures
        # differs from the v1 fixture's - DENIED_CODES' 45385 is v1's again, the denial with its stop. Assess hands C-10
        # (FINAL-V2 4.6 condition 4) the kept evidence's letter-or-digit runs as kept_words (contract/geometry.word_runs
        # through jobs._Integrity.word_runs; D261's note, step 5b), so a quote that reaches past the statement only by
        # its stop covers it, and the seven reinstatement tests of tests/test_readers_dispatch.py read 45385 excluded
        # on v1's quote. In round w7r this test pinned the one quote that differed (the stop dropped); D261 restates it
        dispatch = importlib.import_module('tests.test_readers_dispatch')
        events = importlib.import_module('tests.test_pipeline_assess_events')
        self.assertEqual(dict(v2_documents.DENIED_CODES)['45385'], 'No polyp was removed today.')  # its stop included
        self.assertEqual(v2_documents.DENIED_CODES, dispatch.DENIED_CODES)  # 45378's and 45385's, quote for quote
        self.assertEqual(v2_documents.TWO_CODES, events.TWO_CODES)
        self.assertEqual(v2_documents.POLYP, dispatch.POLYP)  # the quote NewPathUnlistedCodeTests' v2 group adds
        self.assertEqual(('99213', v2_documents.VISIT_TIME),
                         importlib.import_module('tests.test_repairs_ec5_reportruns').VISIT)
        # every class of the class C modules that gives a marked test Corti groups of its own (v2_corti_groups) gives
        # it its v1 groups, quote for quote; the three that do so today are found (the scan is not vacuous)
        found: dict[str, Any] = {}
        for module in sorted({module for module, _, _ in CLASS_C}):
            for value in vars(importlib.import_module(module)).values():
                if isinstance(value, type) and 'v2_corti_groups' in vars(value):
                    found[f'{value.__module__}.{value.__qualname__}'] = value
        self.assertLessEqual({'tests.test_pipeline_assess_events.EventsCase', 'tests.test_readers_dispatch.NewPathCase',
                              'tests.test_readers_dispatch.NewPathUnlistedCodeTests'}, set(found))
        for name, cls in sorted(found.items()):
            with self.subTest(cls=name):
                self.assertEqual(cls.v2_corti_groups, cls.corti_groups)


class InterpreterTests(SimpleTestCase):
    def test_the_registry_answers_one_text_and_refuses_another_answer_for_it(self):
        interpreter = v2_replay._interpreter_class()(((v2_documents.COLON, v2_documents.colon_answer),))
        interpreter.register(v2_documents.COLON, v2_documents.colon_answer)  # the same answer again: one registration
        interpreter.register(v2_documents.COLON, v2_documents.colon_answer())  # equal content: the same
        self.assertEqual(list(interpreter.answers), [v2_documents.COLON])
        with self.assertRaises(AssertionError):
            interpreter.register(v2_documents.COLON, v2_documents.two_extents_answer)
        self.assertNotIn(v2_documents.v1_twin(v2_documents.COLON), interpreter.answers)
