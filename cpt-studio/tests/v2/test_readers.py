"""The read-time dispatch of design v2 (docs/gemini-migration/FINAL-V2.md 6.2, 6.5 and 9.3's read-time row; step 5c of
its 8.1): interpretation/readers.py's EventReader over database rows - a cpt-studio-events@2 assessment read from its
event_coding@2 and the frozen settled inventory (store.load_v2 at every shipped version pair, store.textfree_v2,
overlay.reading), and a cpt-studio-events@1 assessment (a test instance's v1 row) read AS STORED under the label
legacy_record and blocked. Synthetic rows only (tests/v2/test_facts.py's colonoscopy, written by store.row_v2); nothing
is sent.

What is proved here (the step's done-when):
- read time equals assess time: the FactSet the reader loads is engine/facts.effective's over the stored row with the
  date of service the assessment was made with, and every view of the stored assessment equals its stored proposal;
  nothing is unreadable;
- every shipped v2 inventory version is read as stored [R:MO-5]: a row stored under an earlier pair store.READ_VERSIONS
  still lists reads as the current one does, and a pair it does not list is unreadable;
- a v1 row is read as stored and blocked: its views are its stored rows whatever the decisions (stale where they moved
  a hold), the reader labels its reads legacy_record (so a v1 row is never read under new_path), readiness adds the
  UNREADABLE blocker, a reinstatement's reviewed coverage says it was not re-run, and label_of labels its encounter
  legacy_record;
- a v2 inventory that cannot be read (another response than the stored one) blocks a reinstatement and its coverage
  says so, and a reinstated code's coverage is otherwise re-run by the engine over the frozen inventory.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from studio import interpretation, models, review
from studio.interpretation import overlay, readers, sentinel, store
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import facts as F
from studio.types import sha256_json
from tests.support import factories as f
from tests.v2 import test_assess as TA
from tests.v2 import test_facts as TF
from tests.v2 import test_overlay as TO
from tests.v2.test_overlay import persist

DAY = datetime.date(2026, 11, 9)
FIRST, SECOND = b'{"synthetic": "pass 1"}', b'{"synthetic": "pass 2"}'
USAGE = {'promptTokenCount': 5000, 'candidatesTokenCount': 900, 'totalTokenCount': 5900}


def cite(n: int) -> TA.EvidenceSpan:
    at = TF.unit_span(n)
    return TA.EvidenceSpan(0, at.start, at.end, TF.TEXT[at.start:at.end], True)


CODES = (('45385', cite(6)), ('45378', cite(5)))


class V2World:
    """One v2 encounter: the revision TF.TEXT, pass 1's and the appraisal's runs, the v2 inventory written by
    store.row_v2 from TF.colonoscopy() (at store's default pair unless ``versions`` names one of store.READ_VERSIONS),
    its gemini-context@2, the engine's assessment over the stored row persisted as the renderer persists it
    (tests/v2/test_overlay.persist: its completeness exactly what step 5a records, worded with the renderer's label,
    overlay.session_label - step 5a's request R1) at the engine version engine/assess writes (``engine_version``:
    AS.ENGINE_VERSION by default, step f5's request R1: the engine's own label, AMENDMENT-2 8.1; ``record_version`` a
    record another release wrote, its rows' event_reading and its coding's version), and the encounter pointing at
    both.
    ``record``: (completeness, the engine's Assessment, R) -> the completeness stored instead (a later record's).
    ``answered``: (code, value) of a member's answer the engine reads at assess - given to that code's one item as the
    engine asked it (its fingerprint from the same assessment made without it), so the code is EXCLUDED with the
    answer's marker, as an assessment recomputed after the answer records it."""

    def __init__(self, codes=CODES, *, excluded=None, transform=None, sentinel_record=None, record=None,
                 answered=None, versions=None, engine_version=None, record_version=None):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.user)
        self.rev = f.pasted_revision(self.enc, self.user, TF.TEXT)
        self.first = self.run(interpretation.PURPOSE, FIRST)
        self.second = self.run(interpretation.APPRAISAL_PURPOSE, SECOND)
        content = TF.colonoscopy()
        fields = store.row_v2(encounter_id=self.enc.pk, revision_id=self.rev.pk, provider_run_id=self.first.pk,
                              appraisal_run_id=self.second.pk, revision_text=TF.TEXT, text_sha256=self.rev.text_sha256,
                              request_sha256=self.first.request_sha256, response_sha256=self.first.response_sha256,
                              appraisal_request_sha256=self.second.request_sha256,
                              appraisal_response_sha256=self.second.response_sha256, events=content,
                              verification=TF.report(len(content['unlisted'])), versions=versions)
        self.fields = json.loads(json.dumps(fields))
        if transform is not None:
            self.fields = transform(self.fields)
        created = models.EventInventory.objects.create(**self.fields)
        self.inventory = models.EventInventory.objects.get(pk=created.pk)  # its foreign keys as the database gives them
        facts = {'service_date': {'name': 'service_date', 'value': DAY.isoformat(), 'origin': 'document',
                                  'evidence': [], 'note': ''},
                 'setting': {'name': 'setting', 'value': 'office', 'origin': 'user', 'evidence': [], 'note': ''},
                 'patient_status': {'name': 'patient_status', 'value': 'established', 'origin': 'user',
                                    'evidence': [], 'note': ''}}
        self.context = models.EncounterContext.objects.create(
            encounter=self.enc, revision=self.rev, facts=facts, version=interpretation.CONTEXT_VERSION_V2,
            sha256=sha256_json(facts), event_inventory=self.inventory)
        routing = models.RoutingRun.objects.create(revision=self.rev, version=interpretation.ROUTING_VERSION_V2,
                                                   result={}, sha256='1' * 64)
        view = store.textfree_v2(store.load_v2(self.fields, text_sha256=self.rev.text_sha256,
                                               response_sha256=self.first.response_sha256,
                                               appraisal_response_sha256=self.second.response_sha256))
        self.view = view
        self.R = F.effective(view, DAY)
        proposals = TA.NormalizedResponse('corti', 'synthetic@1', codes=tuple(
            TA.ProviderCode('selected', 'CPT', code, '', (span,)) for code, span in codes))
        def assess(answers=()):
            return AS.assess(inventory=view, date_of_service=DAY, text=TF.TEXT, pages=(), integrity=TA.Integrity(),
                             provider_status='succeeded', proposals=proposals, reference=TA.Lookup(),
                             member=AS.MemberContext(setting='office', patient_status='established'),
                             label=overlay.session_label, answers=answers)

        answers = ()
        if answered is not None:
            code, value = answered
            asked = next(p for p in assess().codes if p.code == code)
            answers = (TA.answer(asked, value=value),)
        self.engine = assess(answers)
        rows, completeness = persist(self.engine, self.R, TF.TEXT)
        if record_version is not None:  # a record a release wrote at another engine version (its rows and coding)
            rows = [dataclasses.replace(row, support={**row.support, 'event_reading': record_version}) for row in rows]
            completeness = {**completeness,
                            'event_coding': {**completeness['event_coding'], 'version': record_version}}
        if record is not None:
            completeness = json.loads(json.dumps(record(completeness, self.engine, self.R)))
        if excluded is not None:
            rows.append(excluded)
        self.rows = rows
        record = None
        if sentinel_record is not None:  # the D22 record a v2 assessment carries (interpretation/report.py)
            from studio.interpretation import report

            record = report.interpretation_record(inventory=self.inventory, context=self.context,
                                                  member_date_state={'state': 'agrees'},
                                                  sentinel_record=dict(sentinel_record))
        self.assessment = models.Assessment.objects.create(
            encounter=self.enc, revision=self.rev, context=self.context, routing=routing,
            profiles_version='gi-profiles@test', engine_version=engine_version or AS.ENGINE_VERSION,
            completeness=completeness, retrieval=[], reference_sources=[], sha256='0' * 64,
            event_inventory=self.inventory, interpretation=record)
        self.proposals = {}
        for position, row in enumerate(rows):
            proposal = models.Proposal.objects.create(
                assessment=self.assessment, key=row.key, bucket=row.bucket, code=row.code, code_kind='CPT',
                family=row.family, profile_version='gi-profiles@test', status=row.status,
                reinstatable=row.reinstatable, evidence=list(row.evidence), checks=list(row.checks), units=row.units,
                fingerprint='f' * 64, position=position, support=dict(row.support))
            self.proposals[row.code] = proposal
            for question in row.questions:
                models.Clarification.objects.create(
                    encounter=self.enc, assessment=self.assessment, proposal=proposal, scope=question['scope'],
                    family=question['family'], fact=question['fact'], question=question['question'],
                    reason=question['reason'])
        self.enc.current_assessment, self.enc.current_context = self.assessment, self.context
        self.enc.save(update_fields=['current_assessment', 'current_context', 'updated_at'])

    def run(self, purpose, body):
        request = {'contents': [{'parts': [{'text': 'synthetic'}]}], 'purpose': purpose}
        return models.ProviderRun.objects.create(
            encounter=self.enc, revision=self.rev, provider=interpretation.PROVIDER,
            adapter_version=interpretation.ADAPTER_VERSION_V2, purpose=purpose, request_sha256=sha256_json(request),
            request_body=request, contexts=[], state='succeeded', sent=True, http_status=200, response_bytes=body,
            response_sha256=hashlib.sha256(body).hexdigest(), usage=dict(USAGE),
            requested_model=interpretation.MODEL, returned_model=interpretation.MODEL)

    def fresh(self):
        return models.Assessment.objects.get(pk=self.assessment.pk)

    def decide(self, code, action):
        proposal = self.proposals[code]
        return models.Decision.objects.create(encounter=self.enc, assessment=self.assessment, revision=self.rev,
                                              proposal=proposal, action=action, reviewer=self.user,
                                              reviewer_kind=models.User.HUMAN)


def excluded_row(key='exc:0', code='45386') -> overlay.Stored:
    """An excluded, reinstatable v2 proposal (its record the renderer's shape: no held facts, a passing gate)."""
    at = TF.unit_span(6)
    return overlay.Stored(key=key, code=code, family='gi.colonoscopy', bucket='excluded', status='excluded',
                          reinstatable=True, units=1,
                          checks=({'id': overlay.REINSTATEMENT_CHECK, 'label': 'Approval after reinstatement',
                                   'status': 'pass', 'detail': '', 'source': ''},),
                          holds=(), questions=(),
                          support={'event_reading': interpretation.ENGINE_VERSION_V3, 'kept_words': None,
                                   'procedural': True, 'origin': 'primary', 'competes': [],
                                   'reinstatement_waits': []},
                          evidence=({'start': at.start, 'end': at.end, 'text': TF.TEXT[at.start:at.end]},))


class V2ReadTests(TestCase):
    def test_a_v2_row_is_read_from_its_frozen_inventory_and_reads_as_assessed(self):
        world = V2World()
        assessment = world.fresh()
        reader = readers.for_assessment(assessment)
        self.assertEqual((reader.kind, reader.branch(assessment)), (readers.EVENTS, readers.V2))
        self.assertEqual(reader.reading(assessment), world.R)  # facts.effective over the stored row, its own date
        self.assertEqual(reader.member(assessment), AS.MemberContext(setting='office', patient_status='established'))
        views = review.effective_view(assessment)
        for row in world.rows:
            with self.subTest(code=row.code):
                view = views[row.key]
                self.assertEqual((view.status, [q['question'] for q in view.questions]),
                                 (row.status, [q['question'] for q in row.questions]))
                self.assertEqual((view.recomputed, view.stale), ((), ()))
        self.assertFalse(reader.unreadable(assessment))
        self.assertEqual(review.reviewed_completeness(assessment), assessment.completeness)
        self.assertNotIn(review.UNREADABLE_EVENTS_BLOCKER, review._assessment_blockers(world.enc, assessment))
        # X2's kind was left unclear by pass 2 (TF.colonoscopy): no family is named for it
        self.assertEqual([row['family'] for row in reader.services_list(assessment)], ['gi.colonoscopy', ''])

    def test_a_reinstated_codes_coverage_is_re_run_by_the_engine_over_the_frozen_inventory(self):
        world = V2World(excluded=excluded_row())
        assessment = world.fresh()
        world.decide('45386', models.Decision.REINSTATE)
        reader = readers.for_assessment(assessment)
        self.assertFalse(reader.unreadable(assessment, [('45386', 'gi.colonoscopy')]))
        reviewed = review.reviewed_completeness(assessment)
        rows = [overlay.stored_from(p, ()) for p in assessment.proposals.order_by('position')]
        counted = overlay.counted_codes(rows, {'exc:0'}, world.R)
        members = overlay.recount(rows, [item.key for item in counted], [row.key for row in rows[:2]],
                                  overlay.read_coding(assessment.completeness), world.R,
                                  assessed=overlay.assessed_out(assessment.completeness, rows),
                                  uncounted=overlay.assessed_uncounted(assessment.completeness, rows)).members
        own = overlay.assessment_counts(assessment.completeness, world.R, rows)
        self.assertEqual(own, TO.counts(world.engine, world.R, label=overlay.session_label))
        expected = overlay.reviewed_coverage(assessment.completeness, world.R, counted,
                                             [('45386', 'gi.colonoscopy')], own, members=tuple(members.values()))
        self.assertEqual(reviewed, expected)
        self.assertEqual(reviewed['reinstated'], ['45386'])
        self.assertNotIn(overlay.UNREADABLE_COVERAGE_REASON, reviewed['reasons'])

    @staticmethod
    def actions(world):
        assessment = world.fresh()
        membership = models.Membership.objects.filter(workspace=world.ws, user=world.user).first()
        return {code: review.allowed_actions(models.Proposal.objects.get(pk=proposal.pk), assessment, membership)
                for code, proposal in world.proposals.items()}

    def test_a_reinstatement_on_a_v2_assessment_as_step_5a_records_it_is_re_run_not_blocked(self):
        """The refutation's problem 01: step 5a's completeness records no open_questions, unverified or provider_ok.
        A reinstatement on such an assessment is re-run over the frozen inventory with the counts read time derives
        (overlay.assessment_counts) - exactly as with the counts recorded (request R2): the same reviewed coverage, no
        UNREADABLE blocker, the same actions (never revoke-only)."""
        derived = V2World(excluded=excluded_row())
        self.assertFalse({'open_questions', 'unverified', 'provider_ok'} & set(derived.fresh().completeness))
        recorded = V2World(excluded=excluded_row(), record=lambda completeness, engine, R: TO.recorded(
            completeness, engine, R, label=overlay.session_label))
        self.assertEqual(self.actions(derived), self.actions(recorded))
        for world in (derived, recorded):
            world.decide('45386', models.Decision.REINSTATE)
        for name, world in (('as step 5a records it', derived), ('its counts recorded', recorded)):
            with self.subTest(name):
                assessment = world.fresh()
                reader = readers.for_assessment(assessment)
                self.assertFalse(reader.unreadable(assessment, [('45386', 'gi.colonoscopy')]))
                self.assertNotIn(review.UNREADABLE_EVENTS_BLOCKER, review._assessment_blockers(world.enc, assessment))
                reviewed = review.reviewed_completeness(assessment)
                self.assertEqual(reviewed['reinstated'], ['45386'])
                self.assertNotIn(overlay.UNREADABLE_COVERAGE_REASON, reviewed['reasons'])
        after = self.actions(derived)
        self.assertEqual(after, self.actions(recorded))
        self.assertNotEqual(after['45386'], [review.REVOKE])
        self.assertTrue(after['45385'])
        counted = ('open_questions', 'unverified', 'provider_ok')
        self.assertEqual(review.reviewed_completeness(derived.fresh()),
                         {key: value for key, value in review.reviewed_completeness(recorded.fresh()).items()
                          if key not in counted})

    def test_a_reinstatement_beside_a_members_answer_read_at_assess_is_re_run_not_blocked(self):
        """The refutation's R2-04 (DECISIONS D249; mutant MR3): the doubted tattoo's code 45381 (cited at S8) is held
        with an item the engine reads, and a member answered it "Not documented" before the assessment was made, so the
        engine EXCLUDED it with the answer's marker. A reviewer reinstates 45386: the counts are derived with 45381
        counted where assess counted it, so the reinstatement is re-run over the frozen inventory - not blocked, its
        coverage counting 45386, and the answered code still detail unavailable."""
        world = V2World(CODES + (('45381', cite(8)),), excluded=excluded_row(), answered=('45381', 'not_documented'))
        answered = next(p for p in world.engine.codes if p.code == '45381')
        self.assertEqual((answered.bucket, answered.answered.fact),
                         (AS.Bucket.EXCLUDED, 'performed_status'))
        self.assertFalse({'open_questions', 'unverified', 'provider_ok'} & set(world.fresh().completeness))
        world.decide('45386', models.Decision.REINSTATE)
        assessment = world.fresh()
        reader = readers.for_assessment(assessment)
        rows = [overlay.stored_from(p, ()) for p in assessment.proposals.order_by('position')]
        self.assertEqual(overlay.assessment_counts(assessment.completeness, world.R, rows),
                         TO.counts(world.engine, world.R, label=overlay.session_label))
        self.assertFalse(reader.unreadable(assessment, [('45386', 'gi.colonoscopy')]))
        self.assertNotIn(review.UNREADABLE_EVENTS_BLOCKER, review._assessment_blockers(world.enc, assessment))
        reviewed = review.reviewed_completeness(assessment)
        self.assertEqual(reviewed['reinstated'], ['45386'])
        self.assertNotIn(overlay.UNREADABLE_COVERAGE_REASON, reviewed['reasons'])
        views = review.effective_view(assessment)
        self.assertEqual((views['exc:0'].active, views[world.proposals['45381'].key].reason),
                         (True, overlay.DETAIL_UNAVAILABLE))

    def test_a_completeness_no_counts_reproduce_blocks_a_reinstatement(self):
        """Fail-closed: a stored completeness that no counts reproduce over the engine's own counted set (here a reason
        the engine never wrote) is not believed: a reinstatement on it is blocked and its coverage says why."""
        world = V2World(excluded=excluded_row(), record=lambda completeness, engine, R: {
            **completeness, 'reasons': [*completeness['reasons'], '2 open questions']})
        world.decide('45386', models.Decision.REINSTATE)
        assessment = world.fresh()
        reader = readers.for_assessment(assessment)
        self.assertTrue(reader.unreadable(assessment, [('45386', 'gi.colonoscopy')]))
        self.assertIn(review.UNREADABLE_EVENTS_BLOCKER, review._assessment_blockers(world.enc, assessment))
        self.assertEqual(review.reviewed_completeness(assessment)['reasons'][-1], overlay.UNREADABLE_COVERAGE_REASON)
        self.assertFalse(reader.unreadable(assessment))  # nothing reinstated: nothing re-run, nothing blocked

    def test_every_shipped_v2_inventory_version_is_read_as_stored(self):
        """[R:MO-5]: a row stored under an earlier pair READ_VERSIONS still lists reads exactly as under the current
        pair (simulated: an earlier pair beside the current one, with the current shapes); a pair it does not list
        is unreadable, never read with another pair's rules."""
        store._v2()
        current = store.READ_VERSIONS[-1]
        earlier = ('gemini-events@2/appraisal@0', current[1])
        name = 'gemini-events@2/appraisal@0+inventory@2'

        def stored_earlier(fields):
            fields = dict(fields, interpretation_version=earlier[0])
            fields['verification'] = dict(fields['verification'], label=name)
            fields['sha256'] = store.content_sha256_v2(fields)
            return fields

        with mock.patch.object(store, 'READ_VERSIONS', (earlier, current)), \
                mock.patch.dict(store._V2_SHAPES, {earlier: store._V2_SHAPES[current]}), \
                mock.patch.dict(store._V2_LABELS, {earlier: name}):
            world = V2World(transform=stored_earlier, versions=current)
            assessment = world.fresh()
            reader = readers.for_assessment(assessment)
            self.assertEqual(assessment.event_inventory.interpretation_version, earlier[0])
            self.assertEqual(reader.reading(assessment), world.R)
            self.assertFalse(reader.unreadable(assessment, [('45378', 'gi.colonoscopy')]))
            views = review.effective_view(assessment)
            self.assertEqual([views[row.key].status for row in world.rows], [row.status for row in world.rows])
        # the same row once its pair is no longer listed: unreadable, and a reinstatement is blocked
        assessment = world.fresh()
        reader = readers.for_assessment(assessment)
        self.assertIsNone(reader.reading(assessment))
        self.assertTrue(reader.unreadable(assessment, [('45378', 'gi.colonoscopy')]))

    def test_an_inventory_that_cannot_be_read_blocks_a_reinstatement_and_its_coverage_says_so(self):
        world = V2World(excluded=excluded_row())
        models.ProviderRun.objects.filter(pk=world.second.pk).update(response_bytes=b'another answer')
        world.decide('45386', models.Decision.REINSTATE)
        assessment = world.fresh()
        reader = readers.for_assessment(assessment)
        self.assertIsNone(reader.reading(assessment))
        self.assertTrue(reader.unreadable(assessment, [('45386', 'gi.colonoscopy')]))
        self.assertFalse(reader.unreadable(assessment))  # nothing reinstated: nothing re-run, nothing blocked
        reviewed = review.reviewed_completeness(assessment)
        self.assertEqual(reviewed['reasons'][-1], overlay.UNREADABLE_COVERAGE_REASON)
        self.assertEqual(reviewed['state'], 'incomplete')
        self.assertIn(review.UNREADABLE_EVENTS_BLOCKER, review._assessment_blockers(world.enc, assessment))

    def test_an_assessment_of_design_v2s_first_labels_is_read_as_stored(self):
        """AMENDMENT-2 8.1 [R:replay-R4]: every reader of a stored row accepts both design v2 families - a row stored
        before AMENDMENT-2 (its inventory at the @2 pair, its assessment, records and coding at cpt-studio-events@2) is
        read as stored: the V2 branch, its FactSet read, every view its stored proposal, nothing unreadable, a
        reinstatement's coverage re-run, and the fingerprint binding of D259 kept (review.stored_questions)."""
        world = V2World(excluded=excluded_row(), versions=store.READ_VERSIONS[0],
                        engine_version=interpretation.ENGINE_VERSION_V2, record_version=interpretation.ENGINE_VERSION_V2)
        assessment = world.fresh()
        self.assertEqual((assessment.engine_version, assessment.event_inventory.interpretation_version,
                          assessment.completeness['event_coding']['version']),
                         (interpretation.ENGINE_VERSION_V2, interpretation.INTERPRETATION_PAIR,
                          interpretation.ENGINE_VERSION_V2))
        reader = readers.for_assessment(assessment)
        self.assertEqual(reader.branch(assessment), readers.V2)
        self.assertEqual(reader.reading(assessment), world.R)
        views = review.effective_view(assessment)
        for row in world.rows:
            with self.subTest(code=row.code):
                self.assertEqual((views[row.key].status, views[row.key].recomputed, views[row.key].stale),
                                 (row.status, (), ()))
        self.assertFalse(reader.unreadable(assessment))
        world.decide('45386', models.Decision.REINSTATE)
        self.assertFalse(reader.unreadable(world.fresh(), [('45386', 'gi.colonoscopy')]))
        proposals = list(assessment.proposals.all())
        self.assertEqual(review.stored_questions(assessment, proposals),
                         review.stored_questions(SimpleNamespace(engine_version=interpretation.ENGINE_VERSION_V3),
                                                 proposals))
        # the control: a later events version (@4) is not read
        assessment.engine_version = 'cpt-studio-events@4'
        self.assertEqual(readers.for_assessment(assessment).branch(assessment), readers.UNKNOWN)
        self.assertEqual(review.stored_questions(assessment, proposals), {})

    def test_the_operators_section_names_both_runs(self):
        world = V2World()
        section = readers.for_assessment(world.fresh()).interpretation_section(world.fresh())
        self.assertEqual((section['run']['id'], section['appraisal_run']['id']),
                         (str(world.first.pk), str(world.second.pk)))
        self.assertEqual(section['usage']['usage']['totalTokenCount'], 2 * USAGE['totalTokenCount'])


# --- the V1 branch: a v1 row read as stored and blocked (FINAL-V2 6.2) ------------------------------------------------

V1_CODING = {'version': interpretation.ENGINE_VERSION, 'sessions': {'gi.colonoscopy': {
    'family': 'gi.colonoscopy', 'event': 'E1', 'part_of': '', 'label': 'colonoscopy', 'kind': 'colonoscopy',
    'unresolved': False, 'done': True, 'incomplete': False, 'examinations': ['E1'],
    'reportable': [{'event': 'E2', 'kind': 'snare', 'label': 'snare removal', 'lesion': 'L1',
                    'describe': 'snare removal of the polyp'}], 'doubted': []}},
    'codes': {'k-base': {'session': 'gi.colonoscopy', 'events': ['E1'], 'lesions': []},
              'k-snare': {'session': 'gi.colonoscopy', 'events': ['E2'], 'lesions': ['L1']}},
    'lesions': {'L1': {'label': 'polyp', 'distinct_from': []}}}


class V1RowTests(TestCase):
    def v1_world(self):
        ws = f.workspace()
        user = f.member(ws)
        enc = f.encounter(ws, user)
        rev = f.pasted_revision(enc, user, TF.TEXT)
        facts = {'service_date': {'value': DAY.isoformat(), 'origin': 'document', 'evidence': [], 'note': ''}}
        context = models.EncounterContext.objects.create(encounter=enc, revision=rev, facts=facts,
                                                         version=interpretation.CONTEXT_VERSION,
                                                         sha256=sha256_json(facts))
        routing = models.RoutingRun.objects.create(revision=rev, version=interpretation.ROUTING_VERSION, result={},
                                                   sha256='2' * 64)
        assessment = models.Assessment.objects.create(
            encounter=enc, revision=rev, context=context, routing=routing, profiles_version='gi-profiles@test',
            engine_version=interpretation.ENGINE_VERSION, sha256='0' * 64,
            completeness={'event_coding': V1_CODING, 'covered': {'gi.colonoscopy': ['45385', '45378']},
                          'reasons': [], 'state': 'complete_pending_review'})
        base = models.Proposal.objects.create(
            assessment=assessment, key='k-base', bucket='selected', code='45378', code_kind='CPT',
            family='gi.colonoscopy', profile_version='p', status='needs_clarification', fingerprint='f' * 64,
            position=0, checks=[{'id': overlay.BASE_CHECK, 'label': 'base', 'status': 'warn', 'detail': 'held',
                                 'source': ''}], support={'summary': 'stored'})
        snare = models.Proposal.objects.create(
            assessment=assessment, key='k-snare', bucket='selected', code='45385', code_kind='CPT',
            family='gi.colonoscopy', profile_version='p', status='ready', fingerprint='e' * 64, position=1)
        models.Clarification.objects.create(encounter=enc, assessment=assessment, proposal=base, scope='proposal',
                                            family='gi.colonoscopy', fact='base_included',
                                            question='Is 45378 reported separately from 45385?', reason='held')
        enc.current_assessment, enc.current_context = assessment, context
        enc.save(update_fields=['current_assessment', 'current_context', 'updated_at'])
        return SimpleNamespace(enc=enc, assessment=assessment, base=base, snare=snare, user=user, rev=rev)

    def test_a_v1_row_is_read_as_stored_under_legacy_record_and_blocked(self):
        world = self.v1_world()
        assessment = models.Assessment.objects.get(pk=world.assessment.pk)
        reader = readers.for_assessment(assessment)
        self.assertEqual((reader.kind, reader.branch(assessment)), (readers.EVENTS, readers.V1))
        seen = []
        real = sentinel.relabel

        def spy(label_):
            seen.append(label_)
            return real(label_)

        models.Decision.objects.create(encounter=world.enc, assessment=assessment, revision=world.rev,
                                       proposal=world.snare, action=models.Decision.REJECT, reviewer=world.user,
                                       reviewer_kind=models.User.HUMAN)
        with mock.patch.object(sentinel, 'relabel', side_effect=spy):
            views = review.effective_view(assessment)
            services = reader.services_list(assessment)
        self.assertTrue(seen)
        self.assertEqual(set(seen), {sentinel.LEGACY_RECORD})  # never new_path
        base = views['k-base']
        # read as stored: the rejection of 45385 recomputes nothing (event_coding@1 is unreadable), the base hold stands
        # as stored and is marked stale
        self.assertEqual((base.status, base.released, [c['id'] for c in base.checks]),
                         ('needs_clarification', (), [overlay.BASE_CHECK]))
        self.assertEqual(base.stale, (overlay.BASE_CHECK,))
        self.assertEqual([q['question'] for q in base.questions], ['Is 45378 reported separately from 45385?'])
        self.assertEqual(services, [{'id': 'gi.colonoscopy', 'family': 'gi.colonoscopy', 'status': 'performed'}])
        # blocked: UNREADABLE, so readiness adds the blocker and only a revoke stays
        self.assertTrue(reader.unreadable(assessment))
        self.assertIn(review.UNREADABLE_EVENTS_BLOCKER, review._assessment_blockers(world.enc, assessment))
        self.assertTrue(review._events_unreadable(assessment))
        self.assertIsNone(reader.reading(assessment))
        reviewed = reader.reviewed_completeness(assessment, assessment.completeness, [world.base, world.snare],
                                                [('45378', 'gi.colonoscopy')])
        self.assertEqual(reviewed['reasons'][-1], overlay.UNREADABLE_COVERAGE_REASON)
        self.assertEqual(readers.label_of(models.Encounter.objects.get(pk=world.enc.pk)), sentinel.LEGACY_RECORD)

    def test_a_v1_row_reads_no_v1_reader_and_no_retired_module(self):
        world = self.v1_world()
        assessment = models.Assessment.objects.get(pk=world.assessment.pk)
        with mock.patch.object(store._v1_reader, 'load', side_effect=AssertionError('v1 reader')), \
                mock.patch.object(store, 'load', side_effect=AssertionError('v1 reader')):
            review.effective_view(assessment)
            readers.for_assessment(assessment).unreadable(assessment)
            readers.for_assessment(assessment).services_section(assessment, assessment.completeness)


class LabelTests(SimpleTestCase):
    def test_the_label_follows_the_events_version(self):
        v2 = SimpleNamespace(engine_version=interpretation.ENGINE_VERSION_V2)
        v1 = SimpleNamespace(engine_version=interpretation.ENGINE_VERSION)
        later = SimpleNamespace(engine_version='cpt-studio-events@4')
        legacy = SimpleNamespace(engine_version='cpt-studio-validation@10')
        context2 = SimpleNamespace(version=interpretation.CONTEXT_VERSION_V2)
        context1 = SimpleNamespace(version=interpretation.CONTEXT_VERSION)
        old = SimpleNamespace(version='gi-context@5')
        rows = ((v2, context2, sentinel.NEW_PATH), (v1, context1, sentinel.LEGACY_RECORD),
                (later, context2, sentinel.NEW_PATH), (legacy, context2, sentinel.LEGACY_RECORD),
                (None, context2, sentinel.NEW_PATH), (None, context1, sentinel.LEGACY_RECORD),
                (None, old, sentinel.LEGACY_RECORD), (None, None, sentinel.NEW_PATH))
        for assessment, context, expected in rows:
            encounter = SimpleNamespace(current_assessment=assessment, current_assessment_id=1 if assessment else None,
                                        current_context=context, current_context_id=1 if context else None)
            with self.subTest(assessment=assessment, context=context):
                self.assertEqual(readers.label_of(encounter), expected)

    def test_each_branch_of_the_event_reader(self):
        # AMENDMENT-2 8.1 [R:replay-R4]: the V2 branch reads both design v2 families - @3, what engine/assess writes now,
        # and @2, rows stored before it, read as stored - and a later events version (@4) is not read
        for version, branch in ((interpretation.ENGINE_VERSION_V3, readers.V2),
                                (interpretation.ENGINE_VERSION_V2, readers.V2),
                                (interpretation.ENGINE_VERSION, readers.V1), ('cpt-studio-events@4', readers.UNKNOWN)):
            with self.subTest(version=version):
                row = SimpleNamespace(engine_version=version, completeness={}, event_inventory_id=None)
                reader = readers.for_assessment(row)
                self.assertIsInstance(reader, readers.EventReader)
                self.assertEqual(reader.branch(row), branch)
                self.assertTrue(reader.unreadable(row))  # no coding: unreadable at every branch
        self.assertEqual(readers.READ_ENGINES, (interpretation.ENGINE_VERSION_V2, interpretation.ENGINE_VERSION_V3))
        self.assertEqual(readers.READ_CONTEXTS, (interpretation.CONTEXT_VERSION_V2,))  # contexts unchanged by 8.1
        # the overlay reads both families' codings and records, and writes the engine's own
        self.assertEqual(overlay.READ_CODINGS, readers.READ_ENGINES)
        self.assertEqual(overlay.READ_RECORDS, readers.READ_ENGINES)
        self.assertEqual((overlay.CODING_VERSION, overlay.RECORD_VERSION),
                         (interpretation.ENGINE_VERSION_V3, interpretation.ENGINE_VERSION_V3))
        self.assertEqual(overlay.CODING_VERSION, AS.ENGINE_VERSION)  # what the engine writes is what is read
