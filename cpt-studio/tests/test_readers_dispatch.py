"""Read time on the new path (Gemini migration slice S11; design/FINAL.md 8.2, 8.3 and 10.3, as design/ADJUDICATION.md
R-2 and R-6 amend them; DECISIONS D17 and D22): the one dispatch, every consumer, the scopes and the write gates.

- R-2: the code-shape helpers unchanged consumers call are RE-HOMED into studio/code_shapes.py and imported back by the
  legacy modules with identity preserved (``is``, never equality); each moved definition is pinned by sha256 to its text
  in the legacy module at 070fa0a75 (the rollback image's), the legacy modules define none of them, their code lives in
  code_shapes.py, and the sentinel's deny set holds none of it.
- FINAL 8.2: readers.for_assessment dispatches on the engine label; each reader refuses the other's rows.
- FINAL 8.3: every consumer, run on new-path encounters in several states (a held code and a ready code, a decision, a
  member's answer, a reinstated code), executes no code of the legacy reader - the sentinel in strict mode, CALL-level
  checks on - and the same consumers on a legacy encounter read through the legacy reader under its own label.
- FINAL 10.3 and R-6: a request naming an encounter runs under that encounter's label, one naming none under 'other' with
  its rows labelled each; reads record and never refuse; the decision, member-answer and report write gates refuse on a
  planted legacy execution, record the trip and write nothing; a report or member-answer write is decided again from
  its LOCKED row, and refused when a reading that finished since its request read the encounter moved it (review
  finding 3).
- FINAL 8.1: an unreadable record blocks readiness - the event coding, and (review finding 2) the frozen event inventory
  a reinstated code's reviewed coverage is re-run over, whose coverage then says so in one clause.
- FINAL 3.1: the operator's interpretation section on the console's detail, the trace (review finding 4) and the report;
  and a Corti code that cannot be listed said on a new-path console and report with no legacy execution (finding 5).
- D22: the customer's JSON and exports name no provider or model (gemini, google, the model id), while argon plasma
  coagulation stays GI vocabulary.

Synthetic data only, no network: Gemini is the replay interpreter over a recording written for each test, Corti an
in-process fake (tests.test_pipeline_assess_events.EventsCase).
"""
import ast
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone
from django.test import Client, SimpleTestCase, TestCase

from studio import (answers, api, code_shapes, customer_api, interpretation, jobs, models, operator, progress, reports,
                    review, serializers)
from studio.gi import cues
from studio.interpretation import adapter, overlay, readers, sentinel
from studio.validation import engine, reconcile, review_view
from tests.support import factories as f
from tests.support import operator as ops
from tests.support import pipeline_factories as pf
from tests.test_interpretation_events import COLONOSCOPE, POLYP, exam, reached
from tests.test_interpretation_identity import a, act, sc
from tests.test_pipeline_assess_events import (TWO_CODES, EventsCase, document, envelope, legacy_encounter,
                                               two_procedures)

APP = Path(__file__).resolve().parents[1]
# ADJUDICATION R-2's helpers, with the module each came from and the sha256 of its definition's source lines there
REHOMED = {
    'studio/validation/reconcile.py': {
        'ACT_LABELS': '7287ab50d131f5511e3bf7b9bbd225557b9f3af420eeca5e6430b889c5376984',
        'SERVICE_LABELS': 'd9d2a306b6e297ff4019a93ab8c4f3116af7b9e2eef163b391872ef00c74dff1',
        'act_label': '170a62fe92b285f026efe01c2c1c2086cb1254a97d8d889f526fb856677e2f52',
        'kind_label': 'b5efb1bee8c56ffd1dc38fd7c745b5296b5680c71574e632f72e6188d95bc4ef',
    },
    'studio/validation/review_view.py': {
        'UNAVAILABLE_ANSWERS': '7d8b1e4a0ab87b305aa7ad8a548ca07a25987abec16b5dfdce3e7b886e29b31e',
        '_field': '652d55bf6f3f07e4a33393452f4b0b4985fa49e5b9cb062e9f68a80b802e5d76',
        'service_answers': 'c5a2c474f6791269186c796fa08e17fbc42492bdb8f60433e52c47eb6c2b8603',
    },
    'studio/validation/engine.py': {
        'MAX_LISTED_CODE': '7ad2afc0326dce8c9c40c237ff63208a2d72a2d1635e4c3cc08735205d4048e0',
        '_listable': '55094337449fdcc74a52fe16963edc203d7c67cb2416902520987650c52c5c47',
        'participant_listable': 'd28dfc0f5393096d0809a72c950cfe38efe1fb46791e58882a6051afdc2ccacc',
        'participant_unlisted_count': 'c45f22488362daf6603e676e681061543120e4abac45bf0973fae8fcc556d93a',
        'participant_unlisted_codes': '767093170efe68c6cb4f8d494dd9140ddb899a64e6561ba8d6d779e7111f6e08',
    },
}
MODULES = {'studio/validation/reconcile.py': reconcile, 'studio/validation/review_view.py': review_view,
           'studio/validation/engine.py': engine}
FUNCTIONS = ('act_label', 'kind_label', '_field', 'service_answers', '_listable', 'participant_listable',
             'participant_unlisted_count', 'participant_unlisted_codes')
ACK = review.ACKNOWLEDGEMENTS['human']
PROVIDER_WORDS = ('gemini', 'google', interpretation.MODEL)


def definitions(source: str) -> dict:
    """{name: its source lines} of every module-level function and single-name assignment of ``source``."""
    lines = source.splitlines(keepends=True)
    out = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef):
            out[node.name] = ''.join(lines[node.lineno - 1:node.end_lineno])
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = ''.join(lines[node.lineno - 1:node.end_lineno])
    return out


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# --- R-2: the re-homed helpers -----------------------------------------------------------------------------------------

class RehomedHelperTests(SimpleTestCase):
    def test_every_rehomed_name_is_code_shapes_own_object_in_its_legacy_module(self):
        for path, names in REHOMED.items():
            for name in names:
                with self.subTest(module=path, name=name):
                    self.assertIs(getattr(MODULES[path], name), getattr(code_shapes, name))

    def test_each_definition_is_moved_verbatim_from_the_baseline(self):
        # each pin is the sha256 of the definition's source lines in its legacy module at 070fa0a75 (taken from that
        # text when the move was made, and unchanged in the files since: the rollback image's), so the moved code is
        # byte for byte the code every legacy record was read with; no git history is read here (a CI clone may have none)
        here = definitions((APP / 'studio' / 'code_shapes.py').read_text(encoding='utf-8'))
        for path, names in REHOMED.items():
            for name, pinned in names.items():
                with self.subTest(module=path, name=name):
                    self.assertEqual(sha(here[name]), pinned)

    def test_the_legacy_modules_define_none_of_them_and_import_them_back_once(self):
        for path, names in REHOMED.items():
            tree = ast.parse((APP / path).read_text(encoding='utf-8'))
            with self.subTest(module=path):
                defined = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                           and node.name in names]
                stored = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
                          and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in names]
                self.assertEqual((defined, stored), ([], []))
                found = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                         and node.module == 'studio.code_shapes']
                self.assertEqual(len(found), 1)
                self.assertEqual(sorted(alias.name for alias in found[0].names), sorted(names))

    def test_their_code_lives_in_code_shapes_and_is_never_denied(self):
        status = sentinel.install()
        self.assertEqual(status['state'], 'ok', status['reason'])
        armed = sentinel.deny_set()
        home = (APP / 'studio' / 'code_shapes.py').resolve()
        for name in FUNCTIONS:
            fn = getattr(code_shapes, name)
            with self.subTest(name=name):
                self.assertEqual(Path(fn.__code__.co_filename).resolve(), home)
                self.assertNotIn(id(fn.__code__), armed)
        with sentinel.strict('the re-homed helpers'):
            self.assertEqual(reconcile.act_label('snare'), 'snare removal')
            self.assertEqual(reconcile.kind_label('egd'), 'upper endoscopy')
            self.assertEqual(review_view.service_answers([{'code': '', 'family': 'gi.egd', 'fact': 'extent',
                                                            'value': 'not_documented'}]), {('gi.egd', 'extent')})
            self.assertTrue(engine._listable('45385'))
            self.assertFalse(engine.participant_listable('W/LES(S)'))
            self.assertEqual(engine.participant_unlisted_count([SimpleNamespace(code='45385-59')]), 1)
            self.assertIn('cannot be listed', engine.participant_unlisted_codes(2))

    def test_the_moved_names_keep_the_legacy_modules_working(self):
        # a name the legacy modules read from their own globals reads the one object (reconcile.mention_label reads
        # SERVICE_LABELS and ACT_LABELS; review_view.proposal_answers reads _field and UNAVAILABLE_ANSWERS)
        self.assertEqual(reconcile.mention_label('peg'), 'gastrostomy (PEG) placement')
        self.assertEqual(review_view.proposal_answers([{'code': '45385', 'family': 'gi.colonoscopy', 'fact': 'extent',
                                                        'value': 'cannot_confirm'}]),
                         {('45385', 'gi.colonoscopy', 'extent'): 'cannot_confirm'})
        self.assertEqual(engine.MAX_LISTED_CODE, 10)


# --- FINAL 8.2: the one dispatch, and mutual refusal ------------------------------------------------------------------

class DispatchTests(SimpleTestCase):
    def test_the_engine_label_chooses_the_reader(self):
        for version, reader in (('cpt-studio-events@1', readers.EventReader), ('cpt-studio-events@2', readers.EventReader),
                                ('cpt-studio-validation@10', readers.LegacyReader), ('', readers.LegacyReader),
                                (None, readers.LegacyReader)):
            with self.subTest(version=version):
                self.assertIsInstance(readers.for_assessment(SimpleNamespace(engine_version=version)), reader)

    def test_each_reader_refuses_the_other_engines_rows(self):
        new = SimpleNamespace(engine_version='cpt-studio-events@1', completeness={}, services={}, event_inventory_id=None)
        old = SimpleNamespace(engine_version='cpt-studio-validation@10', completeness={}, services={'services': []})
        calls = (('views', ([], {}, {}),), ('services_list', ()), ('unreadable', ()), ('interpretation_section', ()),
                 ('overlay_inputs', ([], {}, {}, None)))
        for reader, foreign in ((readers.EventReader(), old), (readers.LegacyReader(), new)):
            for name, args in calls:
                with self.subTest(reader=reader.kind, method=name), self.assertRaises(readers.WrongReader):
                    getattr(reader, name)(foreign, *args)
        with self.assertRaises(readers.WrongReader):
            readers.EventReader().reviewed_completeness(old, {'covered': {}}, [], [('45378', 'gi.colonoscopy')])
        with self.assertRaises(readers.WrongReader):
            readers.LegacyReader().reviewed_completeness(new, {'covered': {}}, [], [('45378', 'gi.colonoscopy')])
        self.assertTrue(issubclass(readers.WrongReader, ValueError))

    def test_each_reader_labels_its_rows(self):
        new = SimpleNamespace(engine_version='cpt-studio-events@1', completeness={'event_coding': None})
        old = SimpleNamespace(engine_version='cpt-studio-validation@10', services={'services': []})
        seen = {}

        def spy(label):
            seen.setdefault('labels', []).append(label)
            return real(label)

        real = sentinel.relabel
        with mock.patch.object(sentinel, 'relabel', side_effect=spy):
            readers.for_assessment(new).services_list(new)
            readers.for_assessment(old).services_list(old)
        self.assertEqual(seen['labels'], [sentinel.NEW_PATH, sentinel.LEGACY_RECORD])

    def test_the_label_of_an_encounter_follows_its_assessment_then_its_context(self):
        events = SimpleNamespace(engine_version='cpt-studio-events@1')
        legacy = SimpleNamespace(engine_version='cpt-studio-validation@10')
        gemini, old = SimpleNamespace(version='gemini-context@1'), SimpleNamespace(version='gi-context@5')
        rows = ((events, old, sentinel.NEW_PATH), (legacy, gemini, sentinel.LEGACY_RECORD),
                (None, gemini, sentinel.NEW_PATH), (None, old, sentinel.LEGACY_RECORD), (None, None, sentinel.NEW_PATH))
        for assessment, context, label in rows:
            encounter = SimpleNamespace(current_assessment=assessment, current_assessment_id=1 if assessment else None,
                                        current_context=context, current_context_id=1 if context else None)
            with self.subTest(assessment=assessment, context=context):
                self.assertEqual(readers.label_of(encounter), label)


# --- FINAL 8.3: every consumer, on new-path encounters, runs no code of the legacy reader -------------------------------

def read_everything(case, encounter, membership, user):
    """Every read-time consumer of FINAL 8.3 (and the R-2 helpers' callers) over ``encounter``, as the pages, the API,
    the operator console and the reports call them; returns what they served, for the caller's own checks."""
    encounter = models.Encounter.objects.get(pk=encounter.pk)
    assessment = review.live_assessment(encounter)
    current = review.current_decisions(assessment)
    proposals = list(assessment.proposals.order_by('position'))
    views = review.effective_view(assessment, current)
    served = {'views': views}
    review.question_pairs(assessment, proposals, views)
    review.answer_states(assessment, current)
    review.asked_fingerprints(assessment, current)
    served['completeness'] = review.reviewed_completeness(assessment, current)
    review.act_index(assessment.services)
    review.approved_items(assessment)
    served['readiness'] = review.readiness(encounter)
    review.coding_completeness(encounter)
    review.open_questions_of(assessment, views)
    review.refresh_state(encounter)
    for proposal in proposals:
        review.allowed_actions(proposal, assessment, membership, views)
        review.approve_withheld_by(proposal, assessment, current, views)
        review.evidence_spans(proposal, assessment.revision.text, assessment.revision.pages, {})
    answers.service_date_block(encounter)
    answers.details_needed(encounter, assessment, views)
    answers.saved_answers(assessment)
    answers.earlier_answers(encounter, assessment)
    progress.encounter_progress(encounter)
    progress.checks_summary(encounter)
    served['customer'] = customer_api.encounter_json(encounter, membership)
    served['list_row'] = customer_api.list_row(encounter)
    served['session'] = customer_api.session_json(user, membership)
    served['operator'] = serializers.encounter_detail(encounter, membership)
    serializers.encounter_summary(encounter)
    serializers.trace_json(encounter)
    snap = reports.snapshot(encounter, reports.DRAFT)
    served['operator_txt'] = reports.render_txt(snap)
    reports.render_csv(snap)
    customer = reports.customer_snapshot(encounter, reports.DRAFT)
    served['customer_txt'] = reports.CUSTOMER_RENDERERS['txt'](customer, {'at': '', 'by': ''})
    served['customer_csv'] = reports.CUSTOMER_RENDERERS['csv'](customer, {'at': '', 'by': ''})
    reports.customer_marker_digest(encounter)
    return served


DENIAL = 'No polyp was removed today.'
DENIED_CODES = (('45378', COLONOSCOPE), ('45385', DENIAL))  # Corti's on denied_removal(): 45385 cites the denial


def denied_removal():
    """A colonoscopy to the cecum and a broad current denial of any removal, which 45385 cites: the events engine
    excludes it (FINAL 7.5, reinstatable) and 45378 is ready - until a reviewer reinstates 45385 (D14 on the new path)."""
    return document({'P1': COLONOSCOPE, 'P2': DENIAL}, events=[
        exam(), act('E3', 'P2', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                    scope=sc('all_of_kind', 'No', ['P2']), time=a('current_encounter', 'today', ['P2']))],
        reach=[reached()])


class NewPathCase(EventsCase):
    corti_groups = (TWO_CODES, DENIED_CODES)

    def setUp(self):
        super().setUp()
        self.membership = models.Membership.objects.get(user=self.user, workspace=self.ws)

    def new_path_encounter(self, scenario=two_procedures):
        encounter, _ = self.upload(scenario)
        self.settle()
        encounter.refresh_from_db()
        self.assertTrue(interpretation.is_new_assessment(encounter.current_assessment))
        return encounter

    def settle(self):
        ran = self.drain()
        self.assertTrue(all(job.state == models.Job.SUCCEEDED for job in ran), [(j.kind, j.error) for j in ran])
        return ran

    def proposal_of(self, encounter, code):
        encounter.refresh_from_db()
        return encounter.current_assessment.proposals.exclude(bucket='alternative').get(code=code)

    def decide(self, encounter, code, action):
        encounter.refresh_from_db()
        return review.record_decision(encounter=encounter, proposal=self.proposal_of(encounter, code), action=action,
                                      user=self.user, membership=self.membership,
                                      acknowledgement=ACK if action == 'approve' else '')


class NewPathConsumerTests(NewPathCase):
    """FINAL 8.3 and 10.4(1) for read time: every consumer, on new-path encounters, in strict mode."""

    def test_every_consumer_reads_a_new_path_encounter_with_no_legacy_execution(self):
        encounter = self.new_path_encounter()
        with sentinel.strict('S11 read time: a new-path encounter, no decision') as opened:
            served = read_everything(self, encounter, self.membership, self.user)
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0)
        statuses = {view.code: view.status for view in served['views'].values() if view.bucket != 'alternative'}
        self.assertEqual(statuses, {'43239': 'ready', '45385': 'needs_clarification'})

    def test_the_instrument_is_live_a_planted_legacy_call_in_a_consumer_trips_it(self):
        encounter = self.new_path_encounter()
        real = customer_api.limitations

        def planted(*args):
            reconcile.mention_label('snare')  # a legacy reader's function, as a consumer that bypassed the dispatch
            return real(*args)

        with mock.patch.object(customer_api, 'limitations', side_effect=planted), \
                self.assertRaises(AssertionError) as caught, sentinel.strict('S11 positive control'):
            read_everything(self, encounter, self.membership, self.user)
        self.assertIn('studio/validation/reconcile.py', str(caught.exception))

    def test_a_decision_and_its_readers_run_no_legacy_code(self):
        encounter = self.new_path_encounter()
        with sentinel.strict('S11 a decision on a new-path assessment') as opened:
            decision = self.decide(encounter, '43239', 'approve')
            served = read_everything(self, encounter, self.membership, self.user)
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0)
        self.assertEqual(decision.action, 'approve')
        self.assertEqual(served['views'][decision.proposal.key].decision, 'approve')

    def test_a_member_answer_its_recompute_and_its_withdrawal_run_no_legacy_code(self):
        encounter = self.new_path_encounter()
        rows = answers.details_needed(encounter, review.live_assessment(encounter))
        row = next(item for item in rows if '45385' in item['affects'] and 'not_documented' in item['allow'])
        with sentinel.strict('S11 a member answer on a new-path revision') as opened:
            saved = answers.save_details(encounter, self.user, [{'id': row['id'], 'fact': row['fact'],
                                                                 'value': 'not_documented'}])
            read_everything(self, encounter, self.membership, self.user)
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0)
        self.assertTrue(saved['answer_ids'])
        self.settle()  # the recompute (AGAIN): a new new-path assessment that read the answer
        with sentinel.strict('S11 the recomputed assessment') as opened:
            served = read_everything(self, encounter, self.membership, self.user)
            answer = models.MemberAnswer.objects.get(pk=saved['answer_ids'][0])
            answers.revoke_answer(encounter, self.user, answer.pk)
            read_everything(self, encounter, self.membership, self.user)
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0)
        excluded = [view for view in served['views'].values() if view.code == '45385']
        self.assertTrue(excluded and excluded[0].status == 'excluded', excluded)

    def test_a_reinstated_exclusion_holds_the_base_and_its_coverage_is_read_again_with_no_legacy_code(self):
        encounter = self.new_path_encounter(denied_removal)
        excluded = self.proposal_of(encounter, '45385')
        self.assertEqual((excluded.bucket, excluded.reinstatable), ('excluded', True))
        self.assertEqual(self.proposal_of(encounter, '45378').status, 'ready')
        with sentinel.strict('S11 a reinstated exclusion on a new-path assessment') as opened:
            self.decide(encounter, '45385', 'reinstate')
            served = read_everything(self, encounter, self.membership, self.user)
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0)
        views = {view.code: view for view in served['views'].values() if view.bucket != 'alternative'}
        # D14 on the new path: the reinstated therapeutic code holds the base code beside it (withheld from approval);
        # its own stored gate is clear (its extent is verified), so it reads as stored and may be approved - review_view's
        # rule for a reinstated code
        self.assertEqual((views['45378'].status, views['45378'].added), ('needs_clarification', ('base_included',)))
        self.assertEqual((views['45385'].status, views['45385'].reinstatement_clear, views['45385'].withheld_by),
                         ('excluded', True, ''))
        self.assertIn('approve', review.allowed_actions(self.proposal_of(encounter, '45385'),
                                                        review.live_assessment(encounter), self.membership))
        self.assertEqual(served['completeness']['reinstated'], ['45385'])
        self.assertIn('45385', served['completeness']['covered']['gi.colonoscopy'])

    def test_every_write_of_a_member_runs_no_legacy_code(self):
        encounter = self.new_path_encounter()
        with sentinel.strict('S11 the writes') as opened:
            self.decide(encounter, '43239', 'approve')
            self.decide(encounter, '45385', 'reject')
            for kind, fmt in ((reports.DRAFT, 'txt'), (reports.DRAFT, 'csv')):
                reports.generate(encounter, kind, fmt, self.user)
                reports.generate_customer(encounter, kind, fmt, self.user)
            ready = customer_api.readiness(encounter)
            self.assertTrue(ready['approved'], ready['blockers'])
            reports.generate_customer(encounter, reports.APPROVED, 'txt', self.user)
            reports.generate(encounter, reports.REVIEWED, 'txt', self.user)
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0)
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())


@mock.patch.dict('os.environ', {})
class NewPathParticipantConsumerTests(NewPathCase):
    """The operator report's peer-review sections (phase 2) on a new-path final assessment: the located passages' pages
    are read without studio.candidates (reports._paging)."""

    def test_the_final_assessment_with_peer_reviews_runs_no_legacy_code(self):
        from django.test import override_settings

        with override_settings(ASTRA_MODE='replay', FABLE_MODE='replay'):
            encounter = self.new_path_encounter()
            self.assertEqual(review.assessment_phase(encounter.current_assessment), 2)
            with sentinel.strict('S11 a new-path final assessment with peer reviews') as opened:
                served = read_everything(self, encounter, self.membership, self.user)
            self.assertEqual(opened.count(sentinel.NEW_PATH), 0)
        self.assertIn(b'PEER REVIEW', served['operator_txt'])


LONG = '45385-SYNTHETIC-LONG-VALUE'  # longer than any code a proposal holds: counted, never named (I9)
UNLISTED_ONE = ('It returned 1 code that cannot be listed: empty, or longer than 10 characters (a CPT code has five). '
                'It is not shown and never truncated.')


class NewPathUnlistedCodeTests(NewPathCase):
    """Review finding 5: Corti returns a code it cannot list on a new-path encounter. The console's Corti row and the
    operator's report say the engine's sentence for it from the events engine's own copy (serializers.
    corti_unlisted_words(events=True): interpretation.wording.unlisted_codes), never by checks.unlisted_codes, which the
    sentinel denies on the new path - so the consumer matrix runs with zero new_path executions, and states it."""
    corti_groups = ((*TWO_CODES, (LONG, POLYP)),)

    def test_the_unlisted_sentence_is_said_on_the_console_and_in_the_report_with_no_legacy_code(self):
        encounter = self.new_path_encounter()
        with sentinel.strict('S11 a Corti code that cannot be listed, on a new-path encounter') as opened:
            served = read_everything(self, encounter, self.membership, self.user)
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0)
        row = next(item for item in served['operator']['harness']['participants'] if item['name'] == 'corti')
        self.assertEqual((row['unlisted_codes'], row['codes']), (1, ['43239', '45385']))
        self.assertTrue(row['detail'].endswith(f'. {UNLISTED_ONE}'), row['detail'])
        self.assertIn(f'    Not listed: {UNLISTED_ONE}'.encode(), served['operator_txt'])
        self.assertNotIn(LONG, json.dumps(served['operator']))
        self.assertNotIn(LONG.encode(), served['operator_txt'])


# --- the legacy reader keeps reading the legacy records, under its own label --------------------------------------------

class LegacyConsumerTests(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        self.assessment = pf.assess(self.s.encounter, pf.standard_result())
        self.membership = models.Membership.objects.get(user=self.s.reviewer, workspace=self.s.workspace)

    def test_a_legacy_assessment_is_read_by_the_legacy_overlay_exactly_as_before(self):
        self.assertIsInstance(readers.for_assessment(self.assessment), readers.LegacyReader)
        # today's call, made directly: the stored rows, the legacy services record, review_view.review_view
        proposals = list(self.assessment.proposals.all())
        rows = {}
        for clarification in self.assessment.clarifications.all():
            if clarification.proposal_id:
                rows.setdefault(clarification.proposal_id, []).append(clarification)
        stored = [review_view.stored_from(p, rows.get(p.pk, [])) for p in proposals]
        from studio.jobs import context_service_date
        direct = review_view.review_view(stored, {}, services=self.assessment.services,
                                         retrieval=self.assessment.retrieval,
                                         reference_sources=self.assessment.reference_sources,
                                         service_date=context_service_date(self.assessment.context))
        self.assertEqual(review.effective_view(self.assessment), direct)

    def test_its_legacy_executions_are_labelled_legacy_record_even_inside_a_new_path_scope(self):
        with sentinel.call_checks(), sentinel.scope(sentinel.NEW_PATH, entry='a legacy row read in a new_path scope') \
                as opened:
            review.effective_view(self.assessment)
            review.readiness(self.s.encounter)
            customer_api.encounter_json(self.s.encounter, self.membership)
        self.assertEqual(opened.count(sentinel.NEW_PATH), 0, opened.describe())
        self.assertGreater(opened.count(sentinel.LEGACY_RECORD), 0)  # the archived reader served its own record

    def test_a_write_on_a_legacy_assessment_is_never_gated(self):
        real = review.refresh_state

        def planted(encounter):
            cues.page_number_line('3')  # a legacy execution inside the write: no gate on a legacy row
            return real(encounter)

        proposal = self.assessment.proposals.get(key='sel:0')
        with mock.patch.object(review, 'refresh_state', side_effect=planted), \
                sentinel.scope(sentinel.NEW_PATH, entry='a legacy decision in a new_path scope'):
            decision = review.record_decision(encounter=self.s.encounter, proposal=proposal, action='reject',
                                              user=self.s.reviewer, membership=self.membership)
        self.assertEqual(decision.action, 'reject')
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())


# --- FINAL 10.3 and R-6: scopes, labels, reads that record and writes that refuse ---------------------------------------

class ScopeTests(NewPathCase):
    def setUp(self):
        super().setUp()
        self.client_ = Client()
        self.client_.force_login(self.user)

    def scopes_of(self, call):
        """The (label, entry) of every scope opened while ``call`` runs, outermost first."""
        opened, real = [], sentinel.scope

        def spy(label, *, entry):
            opened.append((label, entry))
            return real(label, entry=entry)

        with mock.patch.object(sentinel, 'scope', side_effect=spy):
            response = call()
        return response, opened

    def test_a_request_naming_a_new_path_encounter_runs_under_new_path(self):
        encounter = self.new_path_encounter()
        response, opened = self.scopes_of(lambda: self.client_.get(f'/api/encounters/{encounter.pk}'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(opened[0], (sentinel.NEW_PATH, 'web:studio.api.encounter_detail'))
        report = reports.generate_customer(encounter, reports.DRAFT, 'txt', self.user)
        response, opened = self.scopes_of(lambda: self.client_.get(f'/api/reports/{report.pk}/download'))
        self.assertEqual((response.status_code, opened[0]), (200, (sentinel.NEW_PATH, 'web:studio.api.download_report')))

    def test_a_request_naming_a_legacy_encounter_runs_under_legacy_record(self):
        s = pf.scenario()
        pf.assess(s.encounter, pf.standard_result())
        client = Client()
        client.force_login(s.reviewer)
        response, opened = self.scopes_of(lambda: client.get(f'/api/encounters/{s.encounter.pk}'))
        self.assertEqual((response.status_code, opened[0]), (200, (sentinel.LEGACY_RECORD,
                                                                   'web:studio.api.encounter_detail')))

    def test_a_request_naming_no_encounter_runs_under_other_and_labels_each_row(self):
        encounter = self.new_path_encounter()
        s = pf.scenario()
        pf.assess(s.encounter, pf.standard_result())
        models.Membership.objects.create(user=self.user, workspace=s.workspace, role=models.Membership.REVIEWER)
        labels, real = [], readers.labelled

        def spy(fn, row, *args, **kwargs):
            labels.append((row.pk, readers.label_of(row)))
            return real(fn, row, *args, **kwargs)

        with mock.patch.object(readers, 'labelled', side_effect=spy):
            response, opened = self.scopes_of(lambda: self.client_.get('/api/encounters'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(opened[0], (sentinel.OTHER, 'web:studio.api.encounters'))
            self.assertIn((encounter.pk, sentinel.NEW_PATH), labels)
            labels.clear()
            response, opened = self.scopes_of(lambda: self.client_.get('/api/session'))
            self.assertEqual((response.status_code, opened[0]), (200, (sentinel.OTHER, 'web:studio.api.session')))
            self.assertIn((encounter.pk, sentinel.NEW_PATH), labels)
        operator_user = f.user('operator-s11')
        ops.grant(operator_user)
        client = Client()
        client.force_login(operator_user)
        with mock.patch.object(readers, 'labelled', side_effect=spy):
            labels.clear()
            response, opened = self.scopes_of(lambda: client.get('/ops/api/encounters'))
        self.assertEqual((response.status_code, opened[0]), (200, (sentinel.OTHER, 'web:studio.operator.encounters')))
        self.assertIn((encounter.pk, sentinel.NEW_PATH), labels)
        self.assertIn((s.encounter.pk, sentinel.LEGACY_RECORD), labels)

    def test_every_url_pattern_runs_in_a_scope(self):
        from django.urls import URLPattern, get_resolver

        patterns = [pattern for pattern in get_resolver().url_patterns if isinstance(pattern, URLPattern)]
        self.assertTrue(patterns)
        for pattern in patterns:
            with self.subTest(route=str(pattern.pattern)):
                self.assertIs(getattr(pattern.callback, '__wrapped__', None) is not None, True)
                self.assertEqual(pattern.callback.__code__.co_qualname, 'web_scope.<locals>.scoped')

    def test_a_read_that_ran_legacy_code_records_the_trip_and_still_answers(self):
        encounter = self.new_path_encounter()
        real = customer_api.limitations

        def planted(*args):
            reconcile.mention_label('snare')
            return real(*args)

        with mock.patch.object(customer_api, 'limitations', side_effect=planted):
            response = self.client_.get(f'/api/encounters/{encounter.pk}')
        self.assertEqual(response.status_code, 200)  # reads never refuse (FINAL 10.3)
        [trip] = models.AuditEvent.objects.filter(event=sentinel.TRIPPED, encounter=encounter)
        self.assertEqual((trip.data['reason'], trip.data['refused'], trip.data['label'], trip.data['entry']),
                         ('executed', False, sentinel.NEW_PATH, 'web:studio.api.encounter_detail'))

    def planted_refresh(self):
        real = review.refresh_state

        def planted(encounter):
            reconcile.mention_label('snare')  # a legacy execution inside the write, before its commit
            return real(encounter)

        return mock.patch.object(review, 'refresh_state', side_effect=planted)

    def assert_refused(self, response, entry, encounter):
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], sentinel.MESSAGES['executed'])
        trips = list(models.AuditEvent.objects.filter(event=sentinel.TRIPPED, encounter=encounter))
        self.assertEqual([(t.data['entry'], t.data['refused'], t.data['reason']) for t in trips],
                         [(entry, True, 'executed')])
        self.assertTrue(any('studio/validation/reconcile.py' in line for line in trips[0].data['executed']))

    def test_the_decision_gate_refuses_and_records_nothing_but_the_trip(self):
        encounter = self.new_path_encounter()
        proposal = self.proposal_of(encounter, '43239')
        with self.planted_refresh():
            response = self.client_.post(f'/api/encounters/{encounter.pk}/decisions',
                                         data=json.dumps({'proposal_id': str(proposal.pk), 'action': 'approve',
                                                          'acknowledgement': ACK}),
                                         content_type='application/json')
        self.assert_refused(response, review.DECISION_GATE, encounter)
        self.assertFalse(models.Decision.objects.filter(encounter=encounter).exists())
        # the same decision with nothing planted is recorded
        response = self.client_.post(f'/api/encounters/{encounter.pk}/decisions',
                                     data=json.dumps({'proposal_id': str(proposal.pk), 'action': 'approve',
                                                      'acknowledgement': ACK}), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)

    def test_the_member_answer_gate_refuses_and_records_nothing_but_the_trip(self):
        encounter = self.new_path_encounter()
        rows = answers.details_needed(encounter, review.live_assessment(encounter))
        row = next(item for item in rows if '45385' in item['affects'] and 'not_documented' in item['allow'])
        with self.planted_refresh():
            response = self.client_.post(f'/api/encounters/{encounter.pk}/details',
                                         data=json.dumps({'answers': [{'id': row['id'], 'fact': row['fact'],
                                                                       'value': 'not_documented'}]}),
                                         content_type='application/json')
        self.assert_refused(response, answers.ANSWER_GATE, encounter)
        self.assertFalse(models.MemberAnswer.objects.filter(encounter=encounter).exists())
        self.assertFalse(models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED).exists())

    def test_the_report_gates_refuse_and_store_nothing(self):
        encounter = self.new_path_encounter()
        real = reports.snapshot_digest

        def planted(snap):
            reconcile.mention_label('snare')
            return real(snap)

        with mock.patch.object(reports, 'snapshot_digest', side_effect=planted):
            with self.assertRaises(sentinel.Tripped):
                reports.generate(encounter, reports.DRAFT, 'txt', self.user)
        real_marker = reports.customer_marker_digest

        def planted_marker(encounter_):
            reconcile.mention_label('snare')
            return real_marker(encounter_)

        with mock.patch.object(reports, 'customer_marker_digest', side_effect=planted_marker):
            response = self.client_.post(f'/api/encounters/{encounter.pk}/reports',
                                         data=json.dumps({'kind': 'draft', 'fmt': 'txt'}),
                                         content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(models.ReportArtifact.objects.filter(encounter=encounter).exists())
        entries = sorted(t.data['entry'] for t in models.AuditEvent.objects.filter(event=sentinel.TRIPPED,
                                                                                   encounter=encounter))
        self.assertEqual(entries, sorted([reports.CUSTOMER_REPORT_GATE, reports.OPERATOR_REPORT_GATE]))

    def test_a_process_that_cannot_count_refuses_new_path_writes(self):
        encounter = self.new_path_encounter()
        proposal = self.proposal_of(encounter, '43239')
        with mock.patch.object(sentinel, 'refusal', return_value='unavailable'):
            response = self.client_.post(f'/api/encounters/{encounter.pk}/decisions',
                                         data=json.dumps({'proposal_id': str(proposal.pk), 'action': 'approve',
                                                          'acknowledgement': ACK}), content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], sentinel.MESSAGES['unavailable'])
        self.assertFalse(models.Decision.objects.filter(encounter=encounter).exists())


def planted(target, name):
    """``target.name`` patched to run a legacy reader's function first (as a consumer that bypassed the dispatch)."""
    real = getattr(target, name)

    def call(*args, **kwargs):
        reconcile.mention_label('snare')
        return real(*args, **kwargs)

    return mock.patch.object(target, name, side_effect=call)


class GateUnderTheLockTests(NewPathCase):
    """FINAL 10.3, decided under the row lock (review finding 3). A report or member-answer write opens its scope from
    the encounter its request read; a reading that finished before the write took its row lock - here a legacy
    encounter's first interpretation (FINAL 9) - moved the row to the new path. The gate is decided again from the
    LOCKED row and the write is refused (readers.MOVED, a 409) before anything is computed or written: before the fix it
    was made from the new-path assessment with no gate, a planted legacy execution and all. The member's retry is
    decided from the row as it then stands."""

    def read_then_interpreted(self):
        """(the encounter as it stands, the same row as a request read it before its lock): a legacy encounter
        (tests.test_pipeline_assess_events.legacy_encounter), read; then a member's context save has its revision's
        first interpretation run, to a new-path assessment."""
        encounter, revision, _, _ = legacy_encounter(self.ws, self.user)
        stale = models.Encounter.objects.get(pk=encounter.pk)
        jobs.change_context(encounter, self.user, {'setting': 'asc'})
        value, _ = two_procedures()
        request = adapter.build_request(revision.text, jobs._participant_pages(revision),
                                        jobs._participant_document(revision)[0])
        folder = Path(self.replay) / adapter.NAME
        folder.mkdir(exist_ok=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(envelope(value))
        self.settle()
        encounter.refresh_from_db()
        self.assertTrue(interpretation.is_new_assessment(review.live_assessment(encounter)))
        # the request's row still reads as the legacy record it was: its gates open no scope
        self.assertEqual((readers.label_of(stale), reports._new_path(stale)), (sentinel.LEGACY_RECORD, False))
        return encounter, stale

    def test_the_reports_are_decided_from_the_locked_row(self):
        encounter, stale = self.read_then_interpreted()
        with planted(reports, 'customer_marker_digest'), self.assertRaises(readers.PathMoved) as moved:
            reports.generate_customer(stale, reports.DRAFT, 'txt', self.user)
        self.assertEqual(str(moved.exception), readers.MOVED)
        with planted(reports, 'snapshot_digest'), self.assertRaises(readers.PathMoved):
            reports.generate(stale, reports.DRAFT, 'txt', self.user)
        self.assertFalse(models.ReportArtifact.objects.filter(encounter=encounter).exists())
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())  # refused before any work
        self.assertEqual(customer_api.customer_error(readers.MOVED), readers.MOVED)  # the 409's own words
        # the retry, from the row as it stands: gated, so the same planted execution is refused and on record
        with planted(reports, 'customer_marker_digest'), self.assertRaises(sentinel.Tripped):
            reports.generate_customer(encounter, reports.DRAFT, 'txt', self.user)
        self.assertFalse(models.ReportArtifact.objects.filter(encounter=encounter).exists())
        self.assertEqual([t.data['entry'] for t in models.AuditEvent.objects.filter(event=sentinel.TRIPPED)],
                         [reports.CUSTOMER_REPORT_GATE])
        self.assertEqual(reports.generate_customer(encounter, reports.DRAFT, 'txt', self.user).encounter_id,
                         encounter.pk)

    def test_a_scope_opened_for_the_new_path_is_refused_once_the_locked_row_left_it(self):
        # the other direction of the same rule: the request read a new-path encounter, and before the write's lock a new
        # revision (an addendum not read yet) left the row with no live assessment - the new_path scope the write opened
        # does not fit the row it would read, so nothing is made from it
        encounter = self.new_path_encounter()
        stale = models.Encounter.objects.get(pk=encounter.pk)
        f.pasted_revision(encounter, self.user, 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - ADDENDUM\n',
                          extract=False)
        self.assertEqual((reports._new_path(stale), reports._new_path(models.Encounter.objects.get(pk=encounter.pk))),
                         (True, False))
        for make in (reports.generate_customer, reports.generate):
            with self.subTest(make=make.__name__), self.assertRaises(readers.PathMoved):
                make(stale, reports.DRAFT, 'txt', self.user)
        self.assertFalse(models.ReportArtifact.objects.filter(encounter=encounter).exists())

    def test_a_member_answer_and_its_withdrawal_are_decided_from_the_locked_row(self):
        encounter, stale = self.read_then_interpreted()
        rows = answers.details_needed(encounter, review.live_assessment(encounter))
        row = next(item for item in rows if '45385' in item['affects'] and 'not_documented' in item['allow'])
        given = [{'id': row['id'], 'fact': row['fact'], 'value': 'not_documented'}]
        with planted(review, 'refresh_state'), self.assertRaises(jobs.Refused) as refused:
            answers.save_details(stale, self.user, given)
        self.assertEqual(str(refused.exception), readers.MOVED)
        self.assertFalse(models.MemberAnswer.objects.filter(encounter=encounter).exists())
        self.assertFalse(models.Job.objects.filter(encounter=encounter, state=models.Job.QUEUED).exists())
        saved = answers.save_details(encounter, self.user, given)  # the retry, from the row as it stands
        self.assertTrue(saved['answer_ids'])
        self.settle()  # the recompute the answer queued
        with planted(review, 'refresh_state'), self.assertRaises(jobs.Refused) as refused:
            answers.revoke_answer(stale, self.user, saved['answer_ids'][0])
        self.assertEqual(str(refused.exception), readers.MOVED)
        self.assertFalse(models.MemberAnswerRevocation.objects.filter(answer__encounter=encounter).exists())
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())


# --- D22: no provider or model is named to a customer -------------------------------------------------------------------

class CustomerNamesNoProviderTests(NewPathCase):
    def test_the_denylist_refuses_the_interpreters_provider_and_model_and_keeps_argon(self):
        for text in ('Read by Gemini.', 'gemini-4-argon', 'Google read it', 'GEMINI', 'the gemini-4 model'):
            with self.subTest(text=text):
                self.assertEqual(customer_api.plain(text), '')
        for text in ('Argon plasma coagulation of the antral vascular ectasia.', 'argon beam'):
            with self.subTest(text=text):
                self.assertEqual(customer_api.plain(text), text)

    def test_the_customer_json_and_exports_of_a_new_path_encounter_name_no_provider_or_model(self):
        encounter = self.new_path_encounter()
        self.decide(encounter, '43239', 'approve')
        self.decide(encounter, '45385', 'reject')
        client = Client()
        client.force_login(self.user)
        bodies = [client.get(f'/api/encounters/{encounter.pk}').content, client.get('/api/encounters').content,
                  client.get('/api/session').content]
        for kind in ('draft', 'approved'):
            for fmt in ('txt', 'csv'):
                created = client.post(f'/api/encounters/{encounter.pk}/reports',
                                      data=json.dumps({'kind': kind, 'fmt': fmt}), content_type='application/json')
                self.assertEqual(created.status_code, 201, created.content)
                bodies.append(client.get(created.json()['download_url']).content)
        payload = json.loads(bodies[0])
        self.assertIn(customer_api.EVENTS_READING, payload['limitations'])
        for body in bodies:
            lowered = body.decode('utf-8').lower()
            with self.subTest(body=lowered[:60]):
                self.assertEqual([word for word in PROVIDER_WORDS if word in lowered], [])


class UnreadableRecordTests(NewPathCase):
    """FINAL 8.1: a new-path assessment whose event coding this release cannot read is never approved or exported until
    it is assessed again - readiness says why, in the member's words too, and the approved export is refused."""

    def test_readiness_blocks_and_the_member_is_told(self):
        encounter = self.new_path_encounter()
        self.decide(encounter, '43239', 'approve')
        self.decide(encounter, '45385', 'reject')
        self.assertTrue(review.readiness(encounter)['reviewed'])
        with mock.patch.object(readers.EventReader, 'unreadable', return_value=True):
            ready = review.readiness(encounter)
            customer = customer_api.readiness(encounter)
            with self.assertRaises(reports.CustomerExportNotReady):
                reports.generate_customer(encounter, reports.APPROVED, 'txt', self.user)
        self.assertEqual((ready['reviewed'], ready['blockers']), (False, [review.UNREADABLE_EVENTS_BLOCKER]))
        self.assertEqual((customer['approved'], customer['blockers']),
                         (False, [customer_api.BLOCKER_EXACT[review.UNREADABLE_EVENTS_BLOCKER]]))
        self.assertFalse(models.ReportArtifact.objects.filter(encounter=encounter).exists())

    def test_d50_no_decision_but_a_revoke_is_taken_on_a_record_this_release_cannot_read(self):
        """D50 (the S17 refutation, finding 15): the blocker's promise is enforced on the decision path. With the event
        coding unreadable (a version this release does not read, written as a later release would), a READY code offers
        no approve and no reject, a decision is refused, and an approval taken before stays revocable."""
        encounter = self.new_path_encounter()
        self.decide(encounter, '43239', 'approve')
        assessment = review.live_assessment(encounter)
        completeness = dict(assessment.completeness)
        completeness['event_coding'] = dict(completeness['event_coding'], version='cpt-studio-event-coding@999')
        with connection.cursor() as cursor:  # as a later release would have written it: the rows are immutable here
            cursor.execute('UPDATE studio_assessment SET completeness = %s WHERE id = %s',
                           [json.dumps(completeness), assessment.pk])
        encounter.refresh_from_db()
        assessment = review.live_assessment(encounter)
        self.assertIsNone(overlay.coding_of(assessment.completeness))
        self.assertIn(review.UNREADABLE_EVENTS_BLOCKER, review.readiness(encounter)['blockers'])
        decided, open_ = self.proposal_of(encounter, '43239'), self.proposal_of(encounter, '45385')
        self.assertEqual(review.allowed_actions(decided, assessment, self.membership), [review.REVOKE])
        self.assertEqual(review.allowed_actions(open_, assessment, self.membership), [])
        for action in ('approve', 'reject'):
            with self.subTest(action=action), self.assertRaises(ValidationError):
                self.decide(encounter, '45385', action)
        self.assertFalse(models.Decision.objects.filter(encounter=encounter, proposal__code='45385').exists())
        self.decide(encounter, '43239', 'revoke')  # a decision taken before stays revocable
        self.assertEqual(review.allowed_actions(self.proposal_of(encounter, '43239'), review.live_assessment(encounter),
                                                self.membership), [])

    def test_a_reinstated_codes_coverage_that_cannot_be_re_run_blocks_what_it_says_it_blocks(self):
        # review finding 2: the frozen event inventory a reinstated code's coverage is re-run over cannot be read (an
        # inventory version this release no longer reads, run bytes or a text sha256 that do not match: EventReader.
        # reading gives None). The coverage shown is the recorded one, without the reinstated code, and says so in one
        # clause; readiness blocks, so the approval and the exports are withheld, as that clause says. Before the fix,
        # readiness passed (reviewed, no blocker) beside a coverage reason claiming the block, ending '..'.
        encounter = self.new_path_encounter(denied_removal)
        self.decide(encounter, '45385', 'reinstate')
        self.decide(encounter, '45385', 'approve')
        self.decide(encounter, '45378', 'reject')
        self.assertEqual(review.readiness(encounter), {'draft': True, 'reviewed': True, 'blockers': []})  # it reads
        with mock.patch.object(readers.EventReader, 'reading', return_value=None):
            ready = review.readiness(encounter)
            customer = customer_api.readiness(encounter)
            coding = review.coding_completeness(encounter)
            completeness = review.reviewed_completeness(review.live_assessment(encounter))
            with self.assertRaises(reports.CustomerExportNotReady):
                reports.generate_customer(encounter, reports.APPROVED, 'txt', self.user)
            with self.assertRaises(reports.ReportNotReady) as refused:
                reports.generate(encounter, reports.REVIEWED, 'txt', self.user)
        self.assertEqual((ready['reviewed'], ready['blockers']), (False, [review.UNREADABLE_EVENTS_BLOCKER]))
        self.assertEqual((customer['approved'], customer['blockers']),
                         (False, [customer_api.BLOCKER_EXACT[review.UNREADABLE_EVENTS_BLOCKER]]))
        self.assertFalse(models.ReportArtifact.objects.filter(encounter=encounter).exists())
        self.assertEqual((completeness['state'], completeness['reasons'][-1], completeness['statement']),
                         ('incomplete', overlay.UNREADABLE_COVERAGE_REASON,
                          'Coding for this encounter is incomplete: ' + '; '.join(completeness['reasons']) + '.'))
        self.assertNotIn('45385', completeness['covered'].get('gi.colonoscopy', []))  # the recorded coverage, as said
        self.assertEqual(coding['state'], 'incomplete')
        self.assertIn(f'{overlay.UNREADABLE_COVERAGE_REASON}. Supported proposals stay available', coding['statement'])
        for said in (coding['statement'], completeness['statement'], str(refused.exception)):
            with self.subTest(said=said[:40]):
                self.assertNotIn('..', said)


class OperatorSectionTests(NewPathCase):
    """FINAL 3.1 and 8.3: the operator's interpretation section on the console's detail and in the operator's report -
    the D22 record, the event inventory, the Gemini run with its usage and estimated cost, the routing stand-in labelled
    as derived - and a legacy encounter's console and report as they were."""

    def setUp(self):
        super().setUp()
        self.operator_user = f.user('operator-s11-section')
        ops.grant(self.operator_user)
        self.operator_client = Client()
        self.operator_client.force_login(self.operator_user)

    def test_the_console_and_the_report_carry_the_interpretation_section(self):
        encounter = self.new_path_encounter()
        payload = self.operator_client.get(f'/ops/api/encounters/{encounter.pk}').json()
        section = payload['assessment']['interpretation']
        assessment = review.live_assessment(encounter)
        self.assertEqual((section['engine'], section['engine_version'], section['problems']),
                         ('events', 'cpt-studio-events@1', []))
        self.assertEqual(section['record']['sentinel']['legacy_calls'], 0)
        self.assertEqual((section['inventory']['id'], section['inventory']['state']),
                         (str(assessment.event_inventory_id), 'read'))
        self.assertEqual((section['run']['provider'], section['run']['requested_model'], section['run']['state']),
                         ('gemini', interpretation.MODEL, 'succeeded'))
        # a replayed answer reports no new usage and is priced at nothing (interpretation.replay): never an invoice
        self.assertEqual((section['run']['usage'], section['run']['estimated_cost']), ({}, None))
        self.assertTrue(section['inventory']['events']['events'])  # the stored events, with their attribute states
        routing = payload['routing']
        self.assertEqual((routing['version'], routing['derived'], routing['inventory']),
                         (interpretation.ROUTING_VERSION, True, str(assessment.event_inventory_id)))
        created = self.operator_client.post(f'/ops/api/encounters/{encounter.pk}/reports',
                                            data=json.dumps({'kind': 'draft', 'fmt': 'txt'}),
                                            content_type='application/json')
        self.assertEqual(created.status_code, 201, created.content)
        text = bytes(models.ReportArtifact.objects.get(pk=created.json()['id']).content).decode('utf-8')
        self.assertIn('\nINTERPRETATION\n', text)
        self.assertIn(f'  Event inventory: {assessment.event_inventory_id} · read', text)
        self.assertIn('  Legacy-call sentinel: 0 legacy calls recorded', text)
        self.assertIn(f'Read by {reports.EVENTS_INVENTORY_VERSION}', text)

    def test_the_trace_carries_the_interpretation_section(self):
        # review finding 4 (FINAL 3.1: the section on the detail, the trace and the report): the trace names the Gemini
        # run that decided every new-path code - its request identity, models, usage, cost and response hash - and the
        # event inventory read from it
        encounter = self.new_path_encounter()
        response = self.operator_client.get(f'/ops/api/encounters/{encounter.pk}/trace')
        self.assertEqual(response.status_code, 200, response.content)
        section = response.json()['interpretation']
        detail = self.operator_client.get(f'/ops/api/encounters/{encounter.pk}').json()
        self.assertEqual(section, detail['assessment']['interpretation'])
        inventory = models.EventInventory.objects.select_related('provider_run').get(
            pk=review.live_assessment(encounter).event_inventory_id)
        run = inventory.provider_run
        self.assertEqual((section['inventory']['id'], section['inventory']['sha256']), (str(inventory.pk),
                                                                                       inventory.sha256))
        self.assertEqual((section['run']['id'], section['run']['request_sha256'], section['run']['response_sha256'],
                          section['run']['requested_model'], section['run']['returned_model']),
                         (str(run.pk), run.request_sha256, run.response_sha256, interpretation.MODEL,
                          run.returned_model))
        self.assertEqual(set(section['run']), {'id', 'provider', 'purpose', 'state', 'sent', 'http_status',
                                               'requested_model', 'returned_model', 'adapter_version',
                                               'request_sha256', 'response_sha256', 'usage', 'estimated_cost',
                                               'reused_from', 'started_at', 'finished_at', 'latency_ms'})

    def test_a_legacy_encounter_s_console_and_report_are_as_they_were(self):
        s = pf.scenario()
        pf.assess(s.encounter, pf.standard_result())
        payload = self.operator_client.get(f'/ops/api/encounters/{s.encounter.pk}').json()
        self.assertEqual(payload['assessment']['interpretation'],
                         {'engine': 'legacy', 'engine_version': pf.ENGINE_VERSION, 'record': None})
        self.assertFalse(payload['routing']['derived'])
        trace = self.operator_client.get(f'/ops/api/encounters/{s.encounter.pk}/trace').json()
        self.assertEqual(set(trace), {'encounter', 'revision', 'participants', 'assessments', 'retrieval',
                                      'reconciliation'})  # as it was: no interpretation key on a legacy trace
        snap = reports.snapshot(s.encounter, reports.DRAFT)
        self.assertNotIn('interpretation', snap)
        self.assertNotIn(b'\nINTERPRETATION\n', reports.render_txt(snap))


class SwitchBackHazardTests(NewPathCase):
    """DECISIONS D51 (the S17 refutation, finding 13; the S17 rollback test D15): the installer's in-image reads behind
    a switch-back - a reinstatement on a new-path assessment is named ('reinstatement': no older overlay adds the hold
    it brings back), and the encounters this revision wrote a record for since its pair was created are listed
    (touched_since), so a switch-back refuses only on what this revision wrote that the previous one would mishandle."""

    def hazards(self):
        from tests.test_repairs_r1_m import install, run_app_script
        return run_app_script(install.UNDO_HAZARDS_READ, {})['hazards']

    def touched(self, since):
        from tests.test_repairs_r1_m import install, run_app_script
        return set(run_app_script(install.TOUCHED_SINCE_READ, {'since': since.isoformat()})['touched'])

    def test_a_reinstatement_on_a_new_path_assessment_is_named_until_it_is_revoked(self):
        encounter = self.new_path_encounter(denied_removal)
        self.assertNotIn('reinstatement', self.hazards().get(str(encounter.pk), []))  # control: nothing reinstated
        self.decide(encounter, '45385', 'reinstate')
        self.assertIn('reinstatement', self.hazards()[str(encounter.pk)])
        self.decide(encounter, '45385', 'revoke')
        self.assertNotIn('reinstatement', self.hazards().get(str(encounter.pk), []))

    def test_touched_lists_an_encounter_only_for_a_record_created_since(self):
        encounter = self.new_path_encounter()
        later = timezone.now() + timedelta(seconds=1)
        self.assertNotIn(str(encounter.pk), self.touched(later))  # nothing created since
        self.assertIn(str(encounter.pk), self.touched(timezone.now() - timedelta(hours=1)))
        mark = timezone.now()
        self.decide(encounter, '43239', 'approve')
        self.assertIn(str(encounter.pk), self.touched(mark))  # a decision recorded since
