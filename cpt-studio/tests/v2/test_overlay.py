"""Read time of a design v2 assessment (docs/gemini-migration/FINAL-V2.md 4.8 "Read time", 6.5 and 9.3's read-time row;
step 5c of its 8.1): interpretation/overlay.py over stored v2 records, TEXT-ONLY and SYNTHETIC.

What is proved here (the step's done-when, "read time equals assess time on every fixture", then 9.3):
- every fixture: engine/assess's Assessment is written as the stored v2 record the overlay reads (``persist``: the
  module docstring's contract), and at read time, with no decision and no answer, every view equals its stored proposal
  (status, checks, questions; nothing recomputed or stale), the read-time engine reproduces each code's held facts, item
  and combination holds (``recount``), ``counted_codes`` gives the coverage's counted codes, and
  ``reviewed_completeness`` with nothing reinstated gives the stored completeness back key for key;
- decisions: a rejection recomputes the combination over the counted set exactly as assess computes it over the same
  codes (a base hold released, a competing hold released, a released item giving way to the next, worded as assess
  words it); a reinstatement's added hold read time cannot word holds the code, stale (fail-closed);
- the stored row path (test_facts' colonoscopy written by store.row_v2): overlay.reading is engine/facts.effective's
  FactSet, so assess and read time read identical inputs (the hand-off 2d:R8 pinned statically: effective, never
  factset);
- fail-closed: event_coding@1 (a v1 row) and every other shape is unreadable; a record that is not v2's, a tampered
  record the engine's own counted set does not reproduce, and no FactSet each recompute nothing, the moved holds marked
  stale;
- the TEXT_FREE messages read no text (the only items read time words afresh), the copies of review_view pinned by AST,
  and FINAL-V2 5.7 measure 4's rules over overlay.py and readers.py;
- DECISIONS D254 rule 2 (ActNoKindNamesTests): an act no kind names (kind other, or a kind not established) is named by
  Kind.OTHER in every act slot item_slots fills and in the base blocker's names - the integration's I2 extended from
  SEPARATE_EM to all of them, I1 kept - so the renderer words each such item and read time words it as assess does
  (R3C1-01's contradicted kind, 5b F1's EUS act of kind other, the same-day act, r4d P4's kindless unlisted act); one
  test asserts step r3c's words for the label ("another act");
- repair round w9r: DECISIONS D267 (D267KindTests: a kind not SUPPORTED - refute-5c-r1 P2's four states - is named
  "another act"; a supported kind keeps its label), D268's read-time half (D268AddonTests: a primary rejected or
  answered away holds its add-on by the ADDON row, never approvable alone, reinstating it releases the add-on - the
  lead's probe among them; the stored rows reproduced, and a stored competing or ADDON hold the inventory does not give
  refused) and D270 (D270AnswerTests: DQ-3, a rival rejected whatever it was answered leaves the competition; DQ-2, the
  engine's own competition reads without a code assess took out by an overlay-bound "Not documented", and a decision
  that unbinds the answer restores the competition); each with its reverse decision. One test, named with step 5a,
  asserts its assess half (green with 5a in the integrated tree, its recount passing the standing answer).
Every document and fact here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import textwrap
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio import jobs, review
from studio.interpretation import ENGINE_VERSION_V2, ENGINE_VERSION_V3, dates, overlay, wording
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import combination, coverage
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine.types import HeldFact, ItemKind, Result
from studio.validation import checks, review_view
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2.test_evaluate import denial_event
from tests.v2.test_types import RETIRED, measure_4

APP = Path(__file__).resolve().parents[2]
Kind, Landmark, SessionKind = ct.Kind, ct.Landmark, ct.SessionKind
UNWORDED = 'A question the renderer could not word (this test writes it so).'

# CPT Studio's own sentences, written out from wording.py's builders: read time's words are compared with these, never
# with read time's own item_slots (the refutation's problem 04).
OFFICE_EM = 'Office / outpatient evaluation and management'
SETTING_BOTH_QUESTION = (f'{OFFICE_EM}: confirm the place of service (for example office or hospital outpatient) and '
                         'whether the patient is new or established.')
SETTING_BOTH_REASON = ('The place of service and whether the patient is new or established are not entered for this '
                       f'encounter; the {OFFICE_EM} profile requires them.')
PATIENT_STATUS_QUESTION = f'{OFFICE_EM}: confirm whether the patient is new or established.'
PATIENT_STATUS_REASON = ('Whether the patient is new or established is not entered for this encounter; the '
                         f'{OFFICE_EM} profile requires it.')
HELD = 'Held for the reviewer, not excluded.'
EDITS = 'internal profile rule; NCCI procedure-to-procedure edits are not connected'


def base_codes(code: str, service: str, codes: str) -> tuple[str, str]:
    """BASE_EXPLAINED's codes form, written out."""
    return (f'Is {code} reported separately from {codes} for this examination?',
            f'The documented {service} has interventions that {codes} account for; its diagnostic examination is '
            f'normally included in them ({EDITS}). {HELD}')


def label(session) -> str:
    """test_assess.run's completeness label (the session id): read time is given the label assess was given."""
    return str(session.id)


# --- the stored v2 record, as the renderer writes it (overlay's module docstring; this step's request R1) -------------

def _slots(item, key, joined, R):
    found = overlay.item_slots(item, key, joined, R)
    if found is not None:
        return found
    values = {field.name: getattr(item.fill, field.name) for field in fields(Q.Fill)}
    values['bundling'] = wording.Bundling(item.fill.bundling.value) if item.fill.bundling is not None else None
    return wording.Slots(**values)


def words(item, key, assessment, R, text=TA.TEXT):
    """The item's question and reason as the renderer words them (wording.build; UNWORDED where wording refuses its
    slots - the message gaps this step's NOTES record)."""
    try:
        worded = wording.build(wording.Message(item.message.value), _slots(item, key, assessment.combination, R), text)
    except ValueError:
        return item.held.fact, UNWORDED, UNWORDED
    return worded.fact, worded.question, worded.reason


def counts(assessment, R, label=label) -> dict:
    """The assessment's own counts as engine/assess computes them (its open items, unverified attributes, provider
    state and conflicts - this test's own mirror of assess's sums, independent of the overlay), checked to reproduce the
    stored reasons exactly (coverage.completeness over the same coverage). Step 5a records only the conflicts; the
    overlay derives the rest (overlay.assessment_counts), and these are what it must find."""
    open_items = sum(1 for p in assessment.codes if p.bucket is AS.Bucket.SELECTED and p.item is not None
                     and p.item.held.rank is not None)
    open_items += sum(1 for found in assessment.service_questions if not found.closed)
    open_items += 1 if assessment.date_of_service is None else 0
    unverified = len({(held.subject, held.attribute) for p in assessment.codes
                      if p.evaluation is not None and p.evaluation.exclusion is None
                      for held in p.evaluation.held_facts
                      if held.result in (Result.UNRESOLVED, Result.UNKNOWN, Result.CONTRADICTED)})
    found = {'open_questions': open_items, 'unverified': unverified,
             'provider_ok': assessment.provider_status is AS.ProviderStatus.SUCCEEDED,
             'conflicts': assessment.completeness['conflicts']}
    again = coverage.completeness(assessment.coverage, coverage.sessions(R), open_questions=open_items,
                                  provider_ok=found['provider_ok'], conflicts=found['conflicts'], label=label,
                                  unverified=unverified)
    assert again['reasons'] == assessment.completeness['reasons'], (again['reasons'], assessment.completeness)
    return found


def recorded(completeness, assessment, R, label=label) -> dict:
    """``completeness`` with the structured counts this step's request R2 asks step 5a to record (assess's own:
    ``counts``; ``label`` the one assess was given), as a later record would carry them."""
    return {**completeness, **counts(assessment, R, label)}


def persist(assessment, R, text=TA.TEXT):
    """(stored rows, completeness) of ``assessment`` as the renderer persists a v2 assessment and the database gives it
    back (JSON): every proposal's record (event_reading, held_facts, kept_words, procedural, origin, competes,
    reinstatement waits, the member-answer marker), its kept evidence, its one item as its open question - but the date
    of service's item, the encounter's own question (FINAL-V2 4.8; step 5a's request R1), which no code asks. The
    completeness is exactly what engine/assess records (step 5a: no open_questions, unverified or provider_ok)."""
    rows = []
    for p in assessment.codes:
        slug = AS.family_slug(p.family)
        questions_, holds = [], []
        if p.item is not None and p.bucket is AS.Bucket.SELECTED and p.item.message is not Q.MessageId.SERVICE_DATE:
            fact, question, reason = words(p.item, p.key, assessment, R, text)
            questions_.append({'id': f'q-{p.key}', 'scope': 'proposal', 'family': slug, 'fact': fact,
                               'question': question, 'reason': reason})
            holds.append(fact)
        support = {'event_reading': overlay.RECORD_VERSION, 'held_facts': AS.jsonable(p.held_facts),
                   'kept_words': AS.jsonable(p.evidence.runs) if p.evidence.runs is not None else None,
                   'procedural': AS.procedural(SimpleNamespace(family=p.family, evaluation=p.evaluation), p.pfs),
                   'origin': p.origin.value, 'competes': list(p.competes), 'summary': f'summary of {p.code}',
                   # the renderer's record of the item (jobs._render_code), which overlay.assessed_out reads
                   'item': ({'message': p.item.message.value, 'fact': p.item.held.fact,
                             'kind': p.item.held.kind.value} if p.item is not None else None)}
        found_checks = []
        if p.bucket is AS.Bucket.EXCLUDED and p.reinstatable:
            waits = [{'fact': held.fact, 'question': f'Approval waits for {held.fact}.'} for held in p.waits]
            support['reinstatement_waits'] = waits
            found_checks.append({'id': overlay.REINSTATEMENT_CHECK, 'label': 'Approval after reinstatement',
                                 'status': 'warn' if waits else 'pass', 'detail': '', 'source': ''})
        if p.answered is not None:
            support['answered'] = {'fact': p.answered.fact, 'value': p.answered.value.value,
                                   'answers': list(p.answered.answers)}
        evidence = [{'start': span.start, 'end': span.end, 'text': text[span.start:span.end]}
                    for span in p.evidence.kept]
        rows.append(overlay.Stored(key=p.key, code=p.code, family=slug, bucket=p.bucket.value, status=p.status.value,
                                   reinstatable=p.reinstatable, units=p.units, checks=tuple(found_checks),
                                   holds=tuple(holds), questions=tuple(questions_),
                                   support=json.loads(json.dumps(support)), evidence=tuple(evidence)))
    completeness = json.loads(json.dumps(dict(assessment.completeness)))
    return rows, completeness


class Case:
    """One fixture assessed (its date of service ``date``, None for unknown), persisted and read back."""

    def __init__(self, R, *codes, member=TA.ENTERED, date=TA.DAY, **kw):
        self.R = TA.dated(R, date)
        self.member = member
        self.assessment = TA.run(R, *codes, member=member, date=date, **kw)
        self.rows, self.completeness = persist(self.assessment, self.R)
        self.coding = overlay.read_coding(self.completeness)

    @property
    def engine_keys(self):
        return [p.key for p in self.assessment.codes if p.bucket is AS.Bucket.SELECTED or p.answered is not None]

    def views(self, decisions=None, **kw):
        return overlay.review_view(self.rows, decisions or {}, completeness=kw.pop('completeness', self.completeness),
                                   facts=kw.pop('facts', self.R), member=kw.pop('member', self.member), **kw)

    def recount(self, counted=None, **kw):
        """The read-time engine over ``counted`` (the engine's own codes by default), the engine's own competition read
        without the codes assess took out of it by an overlay-bound "Not documented" (overlay.assessed_out, as
        review_view reads it: DECISIONS D270 DQ-2) and its ADDON row without the codes assess left out of its count
        (overlay.assessed_uncounted, the one derivation from the stored record: DECISIONS D283 item 3)."""
        kw.setdefault('uncounted', overlay.assessed_uncounted(self.completeness, self.rows))
        return overlay.recount(self.rows, self.engine_keys if counted is None else counted, self.engine_keys,
                               self.coding, self.R, member=self.member,
                               assessed=overlay.assessed_out(self.completeness, self.rows), **kw)


def two_visits() -> EF.Doc:
    """An office visit X1 (this encounter; the visit E1, total time): 99213 and 99214 each hold the other (base) and
    compete for the one visit; nothing entered, so each also waits for the setting (23)."""
    doc = EF.Doc()
    doc.session(1, SessionKind.OFFICE_EM, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.TOTAL_TIME))
    return doc


def unknown_dilation() -> EF.Doc:
    """An EGD with one dilation of the distal esophagus whose device is not stated: 43249 and 43248 each ask the
    technique and compete (step 5a's Q2 input)."""
    doc = EF.egd()
    doc.act(2, Kind.DILATION, places=[EF.sup(Landmark.DISTAL_ESOPHAGUS)])
    return doc


# DECISIONS D254 rule 2's inputs (ActNoKindNamesTests): an act no kind names - engine/questions.act_kind gives
# Kind.OTHER (D267; it gave none before)

CONTRADICTED_KIND = EF.contra(Kind.SNARE, Kind.BIOPSY)  # pass 1 filed both (FINAL-V2 1.3): the kind's value is None


def contradicted_act() -> EF.Doc:
    """refute-r3c-r1 R3C1-01 (its probe p07): a colonoscopy X1 to the cecum, its examination E1 established, and one
    act E2 in X1 whose kind pass 1 filed contradicted: 45378 alone is held base_included on the act in doubt."""
    doc = EF.Doc()
    doc.session(1, SessionKind.COLONOSCOPY, reached=[EF.sup(ct.Extent.CECUM)])
    doc.exam(1)
    doc.act(2, CONTRADICTED_KIND, places=[EF.sup(Landmark.SIGMOID_COLON)])
    return doc


def eus_other_act() -> EF.Doc:
    """refute-5b-r1 F1 (its probes p2 and p2b): an upper EUS X1 (this encounter; stations the esophagus, the stomach
    and the duodenum; reached the second portion of the duodenum), its examination E1 at the pancreas and one act E2 of
    kind other there, done today by the team: D137 lists it as reportable, so 43259 is held base_explained."""
    doc = EF.Doc()
    doc.session(1, SessionKind.EUS, tract=EF.sup(ct.Tract.UPPER), encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER),
                stations=[EF.sup(station) for station in (ct.Station.ESOPHAGUS, ct.Station.STOMACH,
                                                          ct.Station.DUODENUM)],
                reached=[EF.sup(ct.Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(1, places=[EF.sup(Landmark.PANCREAS)])
    doc.act(2, Kind.OTHER, places=[EF.sup(Landmark.PANCREAS)])
    return doc


def office_and_unnamed_act(*, exam: bool, kind=CONTRADICTED_KIND) -> EF.Doc:
    """refute-r3c-r1 p06, and the integration's I2 input: an office visit X1 (this encounter; the visit E1) and a
    same-day flexible sigmoidoscopy X2 to the sigmoid colon whose act E3 no kind names - of a contradicted kind (a
    possible act of the day) or of kind other (a done act); with ``exam`` its examination E2 is filed (a done act)."""
    doc = EF.Doc()
    doc.session(1, SessionKind.OFFICE_EM, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.MEDICAL_DECISION_MAKING))
    doc.session(2, SessionKind.FLEX_SIG, reached=[EF.sup(ct.Extent.SIGMOID_COLON)])
    if exam:
        doc.exam(2, session=EF.X(2))
    doc.act(3, kind, session=EF.X(2), places=[EF.sup(Landmark.SIGMOID_COLON)])
    return doc


def office_and_undated_colonoscopy() -> EF.Doc:
    """I1's input: an office visit X1 and a colonoscopy X2 to the cecum whose examination E2 and cold snare E3 have no
    date relation (the day's undatable acts, which SEPARATE_EM lists in no slot): the day has no act to list."""
    doc = EF.Doc()
    doc.session(1, SessionKind.OFFICE_EM, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.MEDICAL_DECISION_MAKING))
    doc.session(2, SessionKind.COLONOSCOPY, reached=[EF.sup(ct.Extent.CECUM)])
    doc.exam(2, session=EF.X(2), date=None)
    doc.lesion(1, lesion_places=[EF.sup(Landmark.SIGMOID_COLON)])
    doc.act(3, Kind.SNARE, session=EF.X(2), places=[EF.sup(Landmark.SIGMOID_COLON)], lesion=EF.sup(EF.L(1)),
            device=EF.sup(ct.Device.COLD_SNARE), date=None)
    return doc


def kindless_entry_colonoscopy() -> EF.Doc:
    """refute-r4d-r2 P4's S2c: a colonoscopy X1 to the cecum (E1) and one kept unlisted act of no kind carded to X1
    (3.2.6 rule 3): 45378 alone is held base_included on the synthetic act."""
    doc = EF.colonoscopy(snare=False)
    doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.ACT, None, EF.X(1), EF.Span(3000, 3040)))
    return doc


def kindless_entry_feeding_tube() -> EF.Doc:
    """refute-r4d-r2 P4's S1: an EGD X1 (E1) beside a feeding-tube session X3 with no filed event, and one kept unlisted
    act of no kind carded to X3 (D231 row 3): 43235 alone is held base_included on the synthetic act."""
    doc = EF.egd()
    doc.session(3, SessionKind.FEEDING_TUBE)
    doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.ACT, None, EF.X(3), EF.Span(3000, 3040)))
    return doc


def fixtures():
    """Every fixture of this module: (name, a fresh FactSet builder, the codes, the member context)."""
    return (
        ('two sessions', TA.two_sessions, TA.TWO, TA.ENTERED),
        ('enriched', TA.enriched, TA.TWO, TA.ENTERED),
        ('egd dilation', TA.egd_dilation, (('43249', 2), ('43239', 3), ('43235', 1)), TA.ENTERED),
        ('office', TA.office_and_sigmoidoscopy, (('99213', 1), ('45330', 2)), TA.ENTERED),
        ('one dilation', TA.one_dilation, (('43249', 2), ('43248', 2)), TA.ENTERED),
        ('rule (a) base', lambda: EF.colonoscopy(snare=False), (('45378', 1), ('45385', 1)), TA.ENTERED),
        ('unknown dilation', unknown_dilation, (('43249', 2), ('43248', 2)), TA.ENTERED),
        ('two visits', two_visits, (('99213', 1), ('99214', 1)), AS.MemberContext()),
        ('colonoscopy', EF.colonoscopy, (('45385', 2), ('45378', 1)), TA.ENTERED),
        # DECISIONS D254 rule 2's inputs: each item naming an act no kind names is worded, read as assessed
        ('act of contradicted kind (R3C1-01)', contradicted_act, (('45378', 1),), TA.ENTERED),
        ('eus act of kind other (5b F1)', eus_other_act, (('43259', 1), ('64530', 2)), TA.ENTERED),
        ('eus act of kind other beside 43242', eus_other_act, (('43259', 1), ('43242', 2)), TA.ENTERED),
        ('same-day act of contradicted kind (p06)', lambda: office_and_unnamed_act(exam=True),
         (('99213', 1), ('45330', 2)), TA.ENTERED),
        ('kindless unlisted act (r4d S2c)', kindless_entry_colonoscopy, (('45378', 1),), TA.ENTERED),
    )


def cases():
    return [(name, Case(build().build(), *codes, member=member)) for name, build, codes, member in fixtures()]


DATES = (TA.DAY, None)  # the date of service established, and not established (its item the encounter's question)


def dated_cases():
    """Every fixture at each of DATES: (name, date, Case)."""
    return [(name, date, Case(build().build(), *codes, member=member, date=date))
            for name, build, codes, member in fixtures() for date in DATES]


# --- read time equals assess time, on every fixture ------------------------------------------------------------------

class ReadEqualsAssessTests(SimpleTestCase):
    def test_with_no_decision_every_view_is_its_stored_proposal(self):
        for name, date, case in dated_cases():
            views = case.views()
            for p in case.rows:
                with self.subTest(fixture=name, date=date, code=p.code):
                    view = views[p.key]
                    self.assertEqual((view.status, view.checks, view.questions), (p.status, p.checks, p.questions))
                    self.assertEqual((view.recomputed, view.stale, view.added, view.released, view.blocker),
                                     ((), (), (), (), ''))

    def test_the_read_time_engine_reproduces_every_codes_held_facts_item_and_holds(self):
        for name, date, case in dated_cases():
            found = case.recount()
            for p in case.assessment.codes:
                if p.bucket is not AS.Bucket.SELECTED:
                    continue
                with self.subTest(fixture=name, date=date, code=p.code):
                    live = found.live[p.key]
                    self.assertEqual(live.held, p.held_facts)
                    self.assertEqual((live.item, live.stored_item), (p.item, p.item))
                    self.assertEqual(live.holds, case.assessment.combination.held[p.key])
                    self.assertEqual((live.moved, live.added, live.released, live.worded), (False, (), (), None))
            self.assertEqual((found.joined, found.stored_joined), (case.assessment.combination,) * 2)

    def test_the_counted_codes_and_the_reviewed_coverage_are_the_assessments_own(self):
        """The stored completeness is exactly what step 5a records (no open_questions, unverified or provider_ok): read
        time derives the assessment's own counts as assess counted them, and with nothing reinstated its reviewed
        coverage is the stored completeness key for key (no count written into it)."""
        for name, date, case in dated_cases():
            with self.subTest(fixture=name, date=date):
                self.assertFalse({'open_questions', 'unverified', 'provider_ok'} & set(case.completeness))
                counted = overlay.counted_codes(case.rows, set(), case.R)
                self.assertEqual([item.key for item in counted], case.engine_keys)
                own = overlay.assessment_counts(case.completeness, case.R, case.rows, label=label)
                self.assertEqual(own, counts(case.assessment, case.R))
                members = case.recount().members
                reviewed = overlay.reviewed_coverage(case.completeness, case.R, counted, (), own,
                                                     members=tuple(members.values()), label=label)
                self.assertEqual(reviewed, {**case.completeness, 'reinstated': []})

    def test_a_rejection_recomputes_the_combination_as_assess_does_over_the_same_codes(self):
        """For each fixture, at each of DATES, and each selected code, the reviewer's rejection of that code leaves
        every other code with the held facts, item, status and question words assess gives it when the code is not
        proposed at all (the renderer's words of that assessment)."""
        for name, build, codes, member in fixtures():
            for date in DATES:
                whole = Case(build().build(), *codes, member=member, date=date)
                for rejected in [p for p in whole.assessment.codes if p.bucket is AS.Bucket.SELECTED]:
                    rest = [pair for pair in codes if pair[0] != rejected.code]
                    if not rest or len(rest) != len(codes) - 1:
                        continue
                    alone = Case(build().build(), *rest, member=member, date=date)
                    views = whole.views({rejected.key: 'reject'})
                    found = whole.recount([key for key in whole.engine_keys if key != rejected.key])
                    for p in whole.assessment.codes:
                        if p.key == rejected.key or p.bucket is not AS.Bucket.SELECTED:
                            continue
                        expected = next(other for other in alone.assessment.codes if other.code == p.code)
                        stored = next(row for row in alone.rows if row.code == p.code)
                        with self.subTest(fixture=name, date=date, rejected=rejected.code, code=p.code):
                            live = found.live[p.key]
                            self.assertEqual(live.held, expected.held_facts)
                            self.assertEqual(live.item, expected.item)
                            self.assertEqual(views[p.key].status, expected.status.value)
                            self.assertEqual([(q['fact'], q['question'], q['reason']) for q in views[p.key].questions],
                                             [(q['fact'], q['question'], q['reason']) for q in stored.questions])

    def test_a_released_item_gives_way_to_the_next_worded_as_assess_words_it(self):
        """Two visit codes: each is held by the base rule (21), the competition (22) and the setting (23, nothing
        entered). Rejecting 99214 releases both of 99213's combination holds, and its item becomes the member-context
        setting question naming the patient status too - exactly 99213 assessed alone."""
        case = Case(two_visits().build(), ('99213', 1), ('99214', 1), member=AS.MemberContext())
        alone = Case(two_visits().build(), ('99213', 1), member=AS.MemberContext())
        key = case.rows[0].key
        view = case.views({case.rows[1].key: 'reject'})[key]
        # the rule (a) base question: a recorded gap before DECISIONS D246, worded by its codes form since (repair r3c's
        # request R2, applied by the integration)
        self.assertEqual(case.rows[0].questions[0]['question'],
                         'Is 99213 reported separately from 99214 for this examination?')
        self.assertEqual((view.status, view.released), ('needs_clarification', ('base_included', 'competing_codes')))
        self.assertEqual(view.recomputed, (overlay.BASE_CHECK, overlay.COMPETING_CHECK))
        self.assertEqual([(q['fact'], q['question'], q['reason']) for q in view.questions],
                         [(q['fact'], q['question'], q['reason']) for q in alone.rows[0].questions])
        # Fill.both: both values missing - CPT Studio's fixed sentences, written out (never read time's own words)
        self.assertEqual([(q['scope'], q['fact'], q['question'], q['reason']) for q in view.questions], [(
            'proposal', 'setting', SETTING_BOTH_QUESTION, SETTING_BOTH_REASON)])
        self.assertEqual(view.stale, ())

    def test_a_rejection_releases_a_rule_a_base_hold_and_a_competing_hold(self):
        base = Case(EF.colonoscopy(snare=False).build(), ('45378', 1), ('45385', 1))
        released = base.views({base.rows[1].key: 'reject'})[base.rows[0].key]
        self.assertEqual((released.status, released.questions, released.released), ('ready', (), ('base_included',)))
        dilation = Case(unknown_dilation().build(), ('43249', 2), ('43248', 2))
        kept = dilation.views({dilation.rows[1].key: 'reject'})[dilation.rows[0].key]
        # the competing hold (22) is released below the technique question (10), which stays the item, as stored
        self.assertEqual((kept.status, kept.released, kept.questions), ('needs_clarification', ('competing_codes',),
                                                                         dilation.rows[0].questions))

    def test_a_member_answer_lifts_no_hold_but_the_competition(self):
        """Session decision (e): an answered code still counts, so the base hold it makes stands; DECISIONS D249: an
        answer that it is not documented takes it out of the competition, so its rival's competing hold is released
        (no rival is left). 99213 stays held (the base rule and the setting), its stored question standing."""
        case = Case(two_visits().build(), ('99213', 1), ('99214', 1), member=AS.MemberContext())
        first, second = case.rows
        answered = case.views(answers=[{'code': '99214', 'family': second.family, 'fact': 'base_included',
                                        'value': 'not_documented'}])
        self.assertEqual(answered[second.key].reason, overlay.DETAIL_UNAVAILABLE)
        view = answered[first.key]
        self.assertEqual((view.status, view.added, view.released, view.recomputed, view.stale),
                         ('needs_clarification', (), ('competing_codes',), (overlay.COMPETING_CHECK,), ()))
        self.assertEqual(view.questions, first.questions)  # the base item stands, as stored


class RenamedTests(SimpleTestCase):
    """An item that stays while the codes or acts its words name moved (``overlay._renamed``): read time words it
    again, as assess words it over the remaining codes - a rejected code is never named; CPT Studio's sentences
    written out."""

    def test_a_rejected_intervention_is_no_longer_named_by_the_base_question(self):
        case = Case(TA.two_sessions().build(), *TA.TWO)
        by = {p.code: p for p in case.rows}
        self.assertEqual((by['45378'].questions[0]['question'], by['45378'].questions[0]['reason']),
                         base_codes('45378', 'colonoscopy', '45385, 45380'))
        view = case.views({by['45385'].key: 'reject'})[by['45378'].key]
        self.assertEqual((view.status, view.added, view.released, view.recomputed, view.stale),
                         ('needs_clarification', (), (), (overlay.BASE_CHECK,), ()))
        self.assertEqual([(q['scope'], q['fact'], q['question'], q['reason']) for q in view.questions],
                         [('proposal', 'base_included', *base_codes('45378', 'colonoscopy', '45380'))])
        live = case.recount([key for key in case.engine_keys if key != by['45385'].key]).live[by['45378'].key]
        self.assertEqual((live.moved, live.worded.question), (False, base_codes('45378', 'colonoscopy', '45380')[0]))
        # the other session's base, which names nothing the rejection moved, stands as stored
        other = case.views({by['45385'].key: 'reject'})[by['43235'].key]
        self.assertEqual((other.questions, other.recomputed), (by['43235'].questions, ()))

    def test_once_no_intervention_code_is_left_the_base_names_the_act(self):
        case = Case(EF.colonoscopy().build(), ('45385', 2), ('45378', 1))
        by = {p.code: p for p in case.rows}
        view = case.views({by['45385'].key: 'reject'})[by['45378'].key]
        self.assertEqual([(q['fact'], q['question'], q['reason']) for q in view.questions], [(
            'base_included', 'Is 45378 reported separately from snare removal for this examination?',
            'The documented colonoscopy includes snare removal, which this diagnostic code does not account for '
            f'(internal profile rule). {HELD}')])
        self.assertEqual((view.status, view.recomputed), ('needs_clarification', (overlay.BASE_CHECK,)))

    def test_a_renamed_item_read_time_cannot_word_keeps_its_stored_question_stale_and_held(self):
        """Fail-closed: wording refusing the renamed item's slots (simulated) leaves the stored question, marked stale,
        and the code held - never READY, never asked in words naming a rejected code as if they were current."""
        case = Case(TA.two_sessions().build(), *TA.TWO)
        by = {p.code: p for p in case.rows}
        real = wording.build

        def refuse(message, slots, text):
            if message is wording.Message.BASE_EXPLAINED:
                raise ValueError('refused')
            return real(message, slots, text)

        with mock.patch.object(overlay.wording, 'build', side_effect=refuse):
            view = case.views({by['45385'].key: 'reject'})[by['45378'].key]
        self.assertEqual((view.status, view.stale, view.recomputed, view.questions),
                         ('needs_clarification', (overlay.BASE_CHECK,), (), by['45378'].questions))


class DateItemTests(SimpleTestCase):
    """The refutation's problem 03: the date of service's item is the encounter's own question (FINAL-V2 4.8:
    "service_date | encounter scope"), which the renderer asks once and assess counts once - never a code's."""

    def case(self):
        """Two visit codes, the date of service not established: each is held by the base rule and the competition,
        which outrank the date; 99213 assessed alone presents the date's item."""
        return (Case(two_visits().build(), ('99213', 1), ('99214', 1), date=None),
                Case(two_visits().build(), ('99213', 1), date=None))

    def test_a_code_whose_item_gives_way_to_the_date_keeps_no_question_of_its_own(self):
        case, alone = self.case()
        first, second = case.rows
        self.assertEqual(alone.assessment.codes[0].item.message, Q.MessageId.SERVICE_DATE)
        self.assertEqual((alone.rows[0].status, alone.rows[0].questions), ('needs_clarification', ()))
        self.assertEqual([q['fact'] for q in first.questions], ['base_included'])
        view = case.views({second.key: 'reject'})[first.key]
        self.assertEqual((view.status, view.questions, view.released, view.recomputed, view.stale),
                         ('needs_clarification', (), ('base_included', 'competing_codes'),
                          (overlay.BASE_CHECK, overlay.COMPETING_CHECK), ()))
        live = case.recount([first.key]).live[first.key]
        self.assertEqual((live.item.message, live.moved), (Q.MessageId.SERVICE_DATE, True))

    def test_no_answer_binds_to_the_date_or_to_the_item_it_replaced(self):
        case, _ = self.case()
        first, second = case.rows
        base = [{'code': '99213', 'family': first.family, 'fact': 'base_included', 'value': 'not_documented'}]
        self.assertEqual(case.views(answers=base)[first.key].reason, overlay.DETAIL_UNAVAILABLE)  # presented: binds
        released = case.views({second.key: 'reject'}, answers=base)[first.key]
        self.assertEqual((released.reason, released.status), ('', 'needs_clarification'))
        date = [{'code': '99213', 'family': first.family, 'fact': 'service_date', 'value': 'cannot_confirm'}]
        self.assertEqual(case.views({second.key: 'reject'}, answers=date)[first.key].reason, '')


class TextFreeWordsTests(SimpleTestCase):
    """The refutation's problem 04: the words read time gives each TEXT_FREE message it can meet (item_slots over the
    engine's own combination records), against CPT Studio's sentences written out here."""

    def words(self, item, key, joined, R):
        slots = overlay.item_slots(item, key, joined, R)
        self.assertIsNotNone(slots)
        built = wording.build(wording.Message(item.message.value), slots, '')
        return built.fact, built.question, built.reason

    def test_a_competing_item_names_the_rival_never_the_code(self):
        assessment = TA.run(TA.one_dilation().build(), ('43249', 2), ('43233', 2))
        R = TA.dated(TA.one_dilation().build())
        for p, rival in zip(assessment.codes, ('43233', '43249')):
            with self.subTest(code=p.code):
                self.assertEqual(p.item.message, Q.MessageId.COMPETING)
                self.assertEqual(self.words(p.item, p.key, assessment.combination, R), (
                    'competing_codes',
                    f'{p.code} and {rival} are proposed for the same documented act. Reject the code or codes the '
                    'documentation does not support; the one left is then ready for review.',
                    f'{p.code} and {rival} are each proposed for one same documented act of the upper endoscopy. CPT '
                    'Studio does not choose between them: each is held for the reviewer, not excluded, until the '
                    'others are rejected.'))

    def test_a_base_explanation_names_the_codes_that_account_for_the_session(self):
        assessment = TA.run(TA.two_sessions().build(), *TA.TWO)
        R = TA.dated(TA.two_sessions().build())
        found = {p.code: p for p in assessment.codes}
        for code, service, codes in (('45378', 'colonoscopy', '45385, 45380'), ('43235', 'upper endoscopy', '43239')):
            with self.subTest(code=code):
                p = found[code]
                self.assertEqual(self.words(p.item, p.key, assessment.combination, R),
                                 ('base_included', *base_codes(code, service, codes)))

    def test_a_base_question_names_the_acts_in_doubt(self):
        doc = EF.colonoscopy(snare=False)
        doc.act(2, Kind.SNARE, places=[EF.sup(Landmark.SIGMOID_COLON)], status=EF.unres(ct.Status.PERFORMED))
        assessment = TA.run(doc.build(), ('45378', 1))
        p = assessment.codes[0]
        self.assertEqual(p.item.message, Q.MessageId.BASE_INCLUDED)
        self.assertEqual(self.words(p.item, p.key, assessment.combination, TA.dated(doc.build())), (
            'base_included', 'Is 45378 reported separately from snare removal (stated in doubt) for this examination?',
            'The documented colonoscopy includes snare removal (stated in doubt), which this diagnostic code does not '
            f'account for (internal profile rule). {HELD}'))

    def test_a_base_within_item_names_the_eus_code(self):
        from tests.v2 import test_combination as TC

        R = TA.dated(TC.egd_eus())
        joined = combination.combine([TC.member('sel:0', '43235', TC.X1, (TC.E1,)),
                                      TC.member('sel:1', '43242', TC.X2, (TC.E3,))],
                                     {TC.X1: combination.SessionActs(),
                                      TC.X2: combination.SessionActs(reportable=(TC.E3,))}, R)
        held = joined.held['sel:0'][0]
        self.assertEqual(held.cause, combination.WITHIN_CAUSE)
        item = Q.Item(held=held, message=Q.MessageId.BASE_WITHIN, fill=Q.Fill(code='43235', family=SessionKind.EGD))
        self.assertEqual(self.words(item, 'sel:0', joined, R), (
            'base_included', 'Is 43235 reported separately from 43242 for this examination?',
            'The documented upper endoscopy is the endoscopic portion of the endoscopic ultrasound documented with it, '
            'which 43242 accounts for; that examination is normally included in it, not reported separately '
            f'({EDITS}). {HELD}'))

    def test_a_same_day_visit_item_names_the_same_day_acts(self):
        assessment = TA.run(TA.office_and_sigmoidoscopy().build(), ('99213', 1), ('45330', 2))
        p = assessment.codes[0]
        self.assertEqual((p.code, p.item.message), ('99213', Q.MessageId.SEPARATE_EM))
        self.assertEqual(self.words(p.item, p.key, assessment.combination,
                                    TA.dated(TA.office_and_sigmoidoscopy().build())), (
            'separate_em', wording.SEPARATE_EM_QUESTION,
            'Examination is documented as performed on the same date; a significant, separately identifiable E/M '
            'service is not established by this document.'))

    def test_the_member_context_items_read_time_presents_after_a_rejection(self):
        for member, expected in ((AS.MemberContext(), ('setting', SETTING_BOTH_QUESTION, SETTING_BOTH_REASON)),
                                 (AS.MemberContext(setting='office'),
                                  ('patient_status', PATIENT_STATUS_QUESTION, PATIENT_STATUS_REASON))):
            with self.subTest(member=member):
                case = Case(two_visits().build(), ('99213', 1), ('99214', 1), member=member)
                view = case.views({case.rows[1].key: 'reject'})[case.rows[0].key]
                self.assertEqual([(q['fact'], q['question'], q['reason']) for q in view.questions], [expected])

    def test_the_date_item_is_worded_for_the_encounter_only(self):
        """item_slots still words a plain date item (the encounter's question, for the renderer); read time never
        gives it to a code (DateItemTests)."""
        case = Case(two_visits().build(), ('99213', 1), date=None)
        p = case.assessment.codes[0]
        self.assertEqual(self.words(p.item, p.key, case.assessment.combination, case.R),
                         ('service_date', wording.SERVICE_DATE_QUESTION, wording.SERVICE_DATE_REASON))


class CountsTests(SimpleTestCase):
    """The refutation's problem 01: the assessment's own counts, which step 5a's completeness does not record
    (open_questions, unverified, provider_ok), are derived at read time (overlay.assessment_counts) as assess counted
    them; recorded ones (request R2) are read; nothing that fails to reproduce the stored completeness is believed."""

    def test_the_counts_step_5a_does_not_record_are_derived_as_assess_counted_them(self):
        provider_down = Case(two_visits().build(), ('99213', 1), status='failed')
        for name, date, case in [*dated_cases(), ('provider failed', TA.DAY, provider_down)]:
            with self.subTest(fixture=name, date=date):
                self.assertEqual(overlay.assessment_counts(case.completeness, case.R, case.rows, label=label),
                                 counts(case.assessment, case.R))
        self.assertFalse(counts(provider_down.assessment, provider_down.R)['provider_ok'])

    def test_recorded_counts_are_read_when_they_reproduce_the_record(self):
        case = Case(TA.two_sessions().build(), *TA.TWO, date=None)
        own = counts(case.assessment, case.R)
        self.assertTrue(own['open_questions'] and own['unverified'] is not None)
        stored = recorded(case.completeness, case.assessment, case.R)
        self.assertEqual(overlay.assessment_counts(stored, case.R, case.rows, label=label), own)
        for name, wrong in (('open questions', {'open_questions': own['open_questions'] + 1}),
                            ('provider', {'provider_ok': not own['provider_ok']}),
                            ('unverified', {'unverified': own['unverified'] + 1})):
            with self.subTest(recorded=name), self.assertRaises(overlay.UnreadableCounts):
                overlay.assessment_counts({**stored, **wrong}, case.R, case.rows, label=label)
        # a record carrying a count in part (not all of COUNTS): the counts are derived, and the part must agree
        self.assertEqual(overlay.assessment_counts({**case.completeness, 'open_questions': own['open_questions']},
                                                   case.R, case.rows, label=label), own)
        for name, part in (('another open-question count', {'open_questions': own['open_questions'] + 1}),
                           ('a provider state that is no bool', {'provider_ok': int(own['provider_ok'])})):
            with self.subTest(part=name), self.assertRaises(overlay.UnreadableCounts):
                overlay.assessment_counts({**case.completeness, **part}, case.R, case.rows, label=label)

    def test_a_completeness_no_counts_reproduce_is_unreadable(self):
        case = Case(TA.two_sessions().build(), *TA.TWO)
        stored = case.completeness
        for name, broken in (('a reason added', {**stored, 'reasons': [*stored['reasons'], '9 open questions']}),
                             ('a reason dropped', {**stored, 'reasons': stored['reasons'][1:]}),
                             ('another statement', {**stored, 'statement': stored['statement'] + ' '}),
                             ('another conflict count', {**stored, 'conflicts': stored['conflicts'] + 1}),
                             ('no conflict count', {k: v for k, v in stored.items() if k != 'conflicts'}),
                             ('no completeness', None)):
            with self.subTest(name), self.assertRaises(overlay.UnreadableCounts):
                overlay.assessment_counts(broken, case.R, case.rows, label=label)
        # another label than the renderer's (step 5a's request R1: session_label) reproduces nothing where it words
        listed = Case(TA.office_and_sigmoidoscopy().build(), ('45330', 2))  # D134: the visit is not listed
        self.assertTrue(any('not listed as unresolved' in reason for reason in listed.completeness['reasons']))
        with self.assertRaises(overlay.UnreadableCounts):
            overlay.assessment_counts(listed.completeness, listed.R, listed.rows)

    def test_the_counts_of_an_assessment_that_read_a_members_answer_are_derived_as_assess_counted_them(self):
        """The refutation's R2-04 (DECISIONS D249; mutant MR3 drops the answered code from the codes the counts are
        derived over): 4.9's EGD, its dilation's device not stated (43249 asks the technique) beside an antral biopsy
        (43239). A member answers 43249's technique question and the engine reads the answer: 43249 is EXCLUDED with
        the answer's marker. Assess reconciled its selections before the answers, so 43249 still covers the dilation in
        the stored coverage, and read time derives assess's own counts - both answers, the date known or not."""
        for date in DATES:
            first = Case(TA.egd_dilation().build(), ('43249', 2), ('43239', 3), date=date)
            held = next(p for p in first.assessment.codes if p.code == '43249')
            self.assertEqual(held.item.held.fact, 'technique')
            for value in ('not_documented', 'cannot_confirm'):
                case = Case(TA.egd_dilation().build(), ('43249', 2), ('43239', 3), date=date,
                            answers=(TA.answer(held, value=value),))
                with self.subTest(date=date, value=value):
                    answered = next(row for row in case.rows if row.code == '43249')
                    self.assertEqual((answered.bucket, overlay.answered_by_engine(answered)), ('excluded',
                                                                                             ('technique', value)))
                    self.assertFalse({'open_questions', 'unverified', 'provider_ok'} & set(case.completeness))
                    self.assertEqual(overlay.assessment_counts(case.completeness, case.R, case.rows, label=label),
                                     counts(case.assessment, case.R))
                    # nothing reinstated: the reviewed coverage over the codes the engine counted is the stored one
                    reviewed = overlay.reviewed_coverage(
                        case.completeness, case.R, overlay.counted_codes(case.rows, set(), case.R), (),
                        counts(case.assessment, case.R), members=tuple(case.recount().members.values()), label=label)
                    self.assertEqual(reviewed, {**case.completeness, 'reinstated': []})

    def test_a_reinstated_procedure_makes_the_date_a_procedure_day_in_the_reviewed_coverage(self):
        """D134 at read time: an office visit with no code is unresolved (no proposal) only on a date with no
        procedure; a counted procedural code makes the date a procedure day (combination.procedure_day over the
        counted members), so the reviewed coverage reads the visit as not listed instead."""
        case = Case(two_visits().build(), ('99213', 1))
        own = counts(case.assessment, case.R)
        procedure = combination.Member(key='exc:0', code='45378', family=SessionKind.COLONOSCOPY, procedural=True,
                                       supported=True)
        plain = overlay.reviewed_coverage(case.completeness, case.R, [], (), own, members=(), label=label)
        day = overlay.reviewed_coverage(case.completeness, case.R, [], [('45378', 'gi.colonoscopy')], own,
                                        members=(procedure,), label=label)
        self.assertEqual([(item['service'], item['reason']) for item in plain['unresolved_items']],
                         [('X1', 'no_proposal')])
        self.assertEqual((day['unresolved_items'], [item['service'] for item in day['not_listed']]), ([], ['X1']))


class AnsweredRivalTests(SimpleTestCase):
    """DECISIONS D249 (5a's Q2, its request R7 to 5c): at read time a member's answer that a rival is not documented
    removes it from the competition, and the remaining code's competing hold is released when no rival is left. The
    answered code still counts for every other hold (session decision (e)); an answer of "Cannot confirm" leaves the
    competition as it stands (the ruling names "not documented": the fail-closed reading, the step's NOTES question).

    DECISIONS D283, G1-01 option (c) (build list B15; restated in AMENDMENT-2's build, step f6): an answer to the
    COMPETING question binds nothing, at assess or at read time - the competing hold is settled by the reviewer's
    rejection (D270 DQ-3) - so the tests that took a rival out by answering its competing question now take it out by
    the rejection the hold's own sentence asks for, or by an answer to another of its items (the technique, here: a
    rank above the competition's, so the answer binds the item its code presents in every pass)."""

    @staticmethod
    def answer(row, value='not_documented', fact=None):
        return [{'code': row.code, 'family': row.family, 'fact': fact or row.questions[0]['fact'], 'value': value}]

    def test_an_answer_the_engine_read_takes_its_code_out_of_the_competition(self):
        """One dilation whose device is not stated: 43249 and 43248 each ask the technique and compete. The engine read
        a member's "Not documented" to 43248's technique question: 43248 is EXCLUDED and, by DECISIONS D260, assess took
        it out of the competition as read time does (D249): the stored 43249 has no competing hold and no rival. At
        read time, with no decision, nothing is released or recomputed: 43249 reads as stored, held on its own
        technique question, and the read-time engine reproduces its record."""
        first = Case(unknown_dilation().build(), ('43249', 2), ('43248', 2))
        held = next(p for p in first.assessment.codes if p.code == '43248')
        case = Case(unknown_dilation().build(), ('43249', 2), ('43248', 2), answers=(TA.answer(held),))
        by = {row.code: row for row in case.rows}
        self.assertEqual(overlay.answered_by_engine(by['43248']), ('technique', 'not_documented'))
        stored = next(p for p in case.assessment.codes if p.code == '43249')
        self.assertNotIn('competing_codes', [found.fact for found in stored.held_facts])  # assess released it (D260)
        self.assertEqual((stored.competes, by['43249'].support.get('competes', [])), ((), []))
        views = case.views()
        self.assertEqual(views[by['43248'].key].reason, overlay.DETAIL_UNAVAILABLE)
        view = views[by['43249'].key]
        self.assertEqual((view.status, view.added, view.released, view.recomputed, view.stale),
                         ('needs_clarification', (), (), (), ()))
        self.assertEqual(view.questions, by['43249'].questions)  # the technique item, as stored
        live = case.recount().live[stored.key]
        self.assertEqual((live.held, live.item), (stored.held_facts, stored.item))

    def test_with_no_rival_left_the_remaining_code_is_ready_as_assess_gives_it_alone(self):
        """One balloon dilation proposed as 43249 and 43233, each held by the competition alone. D283 G1-01 (c): a
        member's answer to 43233's competing question binds nothing - 43233 stays in review and 43249's competing hold
        stands, as stored, for either value. The reviewer's rejection of 43233 (D270 DQ-3) takes it out: 43249 has no
        rival left and reads READY with no question - as assess gives 43249 proposed alone."""
        case = Case(TA.one_dilation().build(), ('43249', 2), ('43233', 2))
        alone = Case(TA.one_dilation().build(), ('43249', 2))
        first, rival = case.rows
        self.assertEqual([q['fact'] for q in first.questions], ['competing_codes'])
        for value in ('not_documented', 'cannot_confirm'):
            with self.subTest(value=value):
                views = case.views(answers=self.answer(rival, value))
                self.assertEqual((views[rival.key].reason, views[rival.key].answer), ('', ''))
                self.assertEqual((views[first.key].status, views[first.key].questions, views[first.key].released,
                                  views[first.key].stale), ('needs_clarification', first.questions, (), ()))
        view = case.views({rival.key: 'reject'})[first.key]
        self.assertEqual((view.status, view.questions, view.released, view.recomputed, view.stale),
                         ('ready', (), ('competing_codes',), (overlay.COMPETING_CHECK,), ()))
        self.assertEqual((alone.rows[0].status, alone.rows[0].questions), (view.status, view.questions))
        # an approval of 43249 is no longer blocked by a hold it no longer has
        self.assertEqual(case.views({first.key: 'approve', rival.key: 'reject'})[first.key].blocker, '')

    def test_with_a_rival_left_the_hold_stays_naming_the_rivals_left(self):
        """Three codes for one balloon dilation; the reviewer's rejection of 43220 (D283 G1-01 (c): never an answer to
        its competing question) takes it out: 43249 still competes with 43233, held, and its question names 43233
        alone - exactly as assess words 43249 beside 43233."""
        case = Case(TA.one_dilation().build(), ('43249', 2), ('43233', 2), ('43220', 2))
        pair = Case(TA.one_dilation().build(), ('43249', 2), ('43233', 2))
        by = {row.code: row for row in case.rows}
        self.assertIn('43220', by['43249'].questions[0]['question'])
        unchanged = case.views(answers=self.answer(by['43220']))[by['43249'].key]  # the answer binds nothing
        self.assertEqual((unchanged.questions, unchanged.recomputed), (by['43249'].questions, ()))
        view = case.views({by['43220'].key: 'reject'})[by['43249'].key]
        expected = next(row for row in pair.rows if row.code == '43249')
        self.assertEqual((view.status, view.released, view.stale), ('needs_clarification', (), ()))
        self.assertEqual([(q['fact'], q['question'], q['reason']) for q in view.questions],
                         [(q['fact'], q['question'], q['reason']) for q in expected.questions])
        self.assertNotIn('43220', view.questions[0]['question'])

    def test_an_answer_that_binds_stands_when_its_own_item_is_released(self):
        """Both rivals of one dilation whose device is not stated (each asks its technique and competes) answered on
        their technique item, by key (the overlay's to bind in each pass, D283): each answer binds the item its code
        presents in every pass - the technique outranks the competition, so the release one answer causes never moves
        the other code's item - and each code stays out (detail unavailable): no code flips back into review."""
        case = Case(unknown_dilation().build(), ('43249', 2), ('43248', 2))
        by = {row.code: row for row in case.rows}
        first, rival = by['43249'], by['43248']
        self.assertEqual([q['fact'] for q in first.questions], ['technique'])
        for values in (('not_documented', 'not_documented'), ('cannot_confirm', 'not_documented')):
            with self.subTest(values=values):
                views = case.views(answers=self.answer(first, values[0]) + self.answer(rival, values[1]))
                self.assertEqual([(views[row.key].reason, views[row.key].answer) for row in (first, rival)],
                                 [(overlay.DETAIL_UNAVAILABLE, value) for value in values])

    def test_cannot_confirm_leaves_the_competition_as_it_stands(self):
        """The fail-closed reading of D249's "not documented": "Cannot confirm" takes the answered code out of review
        (detail unavailable) but not out of the competition, so the rival keeps its competing hold, as stored - read
        by the overlay (an answer to 43248's technique item, by key: D283's competing question binds no answer) or by
        the engine."""
        case = Case(unknown_dilation().build(), ('43249', 2), ('43248', 2))
        by = {row.code: row for row in case.rows}
        first, rival = by['43249'], by['43248']
        views = case.views(answers=self.answer(rival, 'cannot_confirm'))
        self.assertEqual(views[rival.key].reason, overlay.DETAIL_UNAVAILABLE)
        view = views[first.key]
        self.assertEqual((view.status, view.released, view.questions), ('needs_clarification', (), first.questions))
        held = next(p for p in Case(unknown_dilation().build(), ('43249', 2), ('43248', 2)).assessment.codes
                    if p.code == '43248')
        engine = Case(unknown_dilation().build(), ('43249', 2), ('43248', 2),
                      answers=(TA.answer(held, value='cannot_confirm'),))
        by = {row.code: row for row in engine.rows}
        self.assertEqual(overlay.answered_by_engine(by['43248']), ('technique', 'cannot_confirm'))
        kept = engine.views()[by['43249'].key]
        self.assertEqual((kept.status, kept.released, kept.recomputed), ('needs_clarification', (), ()))

    def test_nothing_recomputed_leaves_the_stored_record_as_assess_released_it(self):
        """Fail-closed: with no FactSet (or an event coding that is not @2) read time recomputes nothing. An answer the
        engine read was already taken out of the competition by assess (DECISIONS D260), so the stored record names no
        rival and holds no competing hold: the code stays held on its own question, as stored, and nothing is marked
        stale (the stale mark is for a rival the overlay's own answer took out, which assess never read)."""
        held = next(p for p in Case(unknown_dilation().build(), ('43249', 2), ('43248', 2)).assessment.codes
                    if p.code == '43248')
        case = Case(unknown_dilation().build(), ('43249', 2), ('43248', 2), answers=(TA.answer(held),))
        by = {row.code: row for row in case.rows}
        v1 = {**case.completeness,
              'event_coding': {**case.completeness['event_coding'], 'version': 'cpt-studio-events@1'}}
        for name, kw in (('no FactSet', {'facts': None}), ('event_coding@1', {'completeness': v1})):
            with self.subTest(name):
                view = case.views(**kw)[by['43249'].key]
                self.assertEqual((view.status, view.released, view.questions, view.stale),
                                 ('needs_clarification', (), by['43249'].questions, ()))


# --- DECISIONS D246: the one completeness label -----------------------------------------------------------------------

X1 = EF.X(1)
# coverage.completeness's sentence of one session not listed, for every session kind and a kind not established, worded
# with overlay.session_label (the one label: the renderer passes it to assess, read time words with it): CPT Studio's
# sentences, written out. The step's NOTES print all 17.
NOT_LISTED = ('Coding for this encounter is incomplete: 1 documented service without a supported proposal and not '
              'listed as unresolved: {}.')
LABELS = {
    SessionKind.OFFICE_EM: 'office / outpatient visit', SessionKind.EGD: 'upper endoscopy',
    SessionKind.ENTEROSCOPY: 'enteroscopy', SessionKind.COLONOSCOPY: 'colonoscopy',
    SessionKind.FLEX_SIG: 'flexible sigmoidoscopy', SessionKind.EUS: 'endoscopic ultrasound', SessionKind.ERCP: 'ERCP',
    SessionKind.CAPSULE: 'capsule endoscopy', SessionKind.MOTILITY: 'manometry',
    SessionKind.REFLUX: 'pH / impedance study', SessionKind.ANORECTAL: 'anorectal testing',
    SessionKind.FEEDING_TUBE: 'feeding-tube procedure',
    # the five with no SESSION_SERVICES entry (D246: they read well in the sentence, never a profile's title)
    SessionKind.SEDATION: 'moderate sedation', SessionKind.EM_OTHER: 'visit in another setting',
    SessionKind.OTHER_GI: 'other GI service', SessionKind.NOT_GI: 'service outside the GI profiles',
    None: 'service whose kind is not established',
}


class SessionLabelTests(SimpleTestCase):
    def test_every_kind_reads_well_in_the_completeness_sentence(self):
        self.assertEqual(set(LABELS), {*SessionKind, None})  # 16 kinds and a kind not established: 17
        for kind, expected in LABELS.items():
            with self.subTest(kind=getattr(kind, 'value', kind)):
                session = coverage.Session(id=X1, kind=kind, done=True)
                self.assertEqual(overlay.session_label(session), expected)
                found = coverage.completeness(coverage.Coverage(not_listed=[session]), {X1: session}, open_questions=0,
                                              provider_ok=True, conflicts=0, label=overlay.session_label)
                self.assertEqual(found['statement'], NOT_LISTED.format(expected))

    def test_a_service_kind_is_named_by_its_service_and_the_five_others_by_their_phrases(self):
        services, unnamed = set(wording.SESSION_SERVICES), set(overlay.UNNAMED_SERVICE_LABELS)
        self.assertEqual((services | unnamed, services & unnamed), (set(SessionKind), set()))
        self.assertEqual(unnamed, {SessionKind.SEDATION, SessionKind.EM_OTHER, SessionKind.OTHER_GI,
                                   SessionKind.NOT_GI})
        for kind in SessionKind:
            with self.subTest(kind=kind.value):
                label_ = overlay.session_label(coverage.Session(id=X1, kind=kind))
                if kind in services:
                    self.assertEqual(label_, wording.service_phrase(kind))
                else:  # never the profile's capitalised title inside the sentence (v1's and the old reading's)
                    self.assertNotEqual(label_, wording.profile_label(kind))
                    self.assertEqual(label_[:1], label_[:1].lower())
        self.assertEqual(overlay.session_label(coverage.Session(id=X1, kind=None)), overlay.UNESTABLISHED_SERVICE_LABEL)

    def test_two_sessions_not_listed_are_named_in_one_list(self):
        sessions = {X1: coverage.Session(id=X1, kind=SessionKind.SEDATION, done=True),
                    EF.X(2): coverage.Session(id=EF.X(2), kind=None, done=True)}
        found = coverage.completeness(coverage.Coverage(not_listed=list(sessions.values())), sessions, open_questions=0,
                                      provider_ok=True, conflicts=0, label=overlay.session_label)
        self.assertEqual(found['reasons'], ['2 documented services without a supported proposal and not listed as '
                                            'unresolved: moderate sedation, service whose kind is not established'])

    def test_read_time_reproduces_a_reason_assess_worded_with_the_one_label(self):
        """D134's office visit beside a same-day sigmoidoscopy, only 45330 proposed: assess words the visit not listed
        with overlay.session_label (the renderer's label, D246), and read time derives the counts from that record with
        its default label; a record worded with another label is not reproduced (UnreadableCounts: the L2 hazard)."""
        R = TA.dated(TA.office_and_sigmoidoscopy().build())
        assessment = AS.assess_facts(R, date_of_service=TA.DAY, text=TA.TEXT, pages=(), integrity=TA.Integrity(),
                                     provider_status='succeeded', proposals=TA.corti(('45330', 2)),
                                     reference=TA.Lookup(), member=TA.ENTERED, label=overlay.session_label)
        rows, completeness = persist(assessment, R)
        self.assertIn('1 documented service without a supported proposal and not listed as unresolved: office / '
                      'outpatient visit', completeness['reasons'])
        self.assertEqual(overlay.assessment_counts(completeness, R, rows),
                         counts(assessment, R, label=overlay.session_label))
        with self.assertRaises(overlay.UnreadableCounts):
            overlay.assessment_counts(completeness, R, rows, label=lambda session: 'a documented service')


class ModifierReviewTests(SimpleTestCase):
    def case(self):
        """two_sessions with L1 established distinct from L2: 45385's snare (L1) and 45380's biopsy (L2) in one
        session make each a separate-lesion modifier review (combination.modifier_review)."""
        doc = TA.two_sessions()
        doc.lesions[EF.L(1)] = {**doc.lesions.get(EF.L(1), {}), ct.Attribute.DISTINCT_FROM: (EF.sup(EF.L(2)),)}
        # DECISIONS D302 RF2C-L1 (round r2e): a written distinct_from sets two lesions apart only when both are
        # established single, so the two lesions are filed single (no multiplicity was filed before r2e)
        for lesion in (EF.L(1), EF.L(2)):
            doc.lesions[lesion] = {**doc.lesions.get(lesion, {}),
                                   ct.Attribute.MULTIPLICITY: (EF.sup(ct.Multiplicity.SINGLE),)}
        return Case(doc.build(), *TA.TWO)

    def test_the_review_is_the_combinations_over_the_effective_set_worded_from_values(self):
        case = self.case()
        snare, biopsy = case.rows[0], case.rows[1]
        found = case.views()[snare.key].modifier_review
        engine = case.assessment.combination.reviews[snare.key]
        self.assertEqual((found['kind'], found['codes'], found['service'], found['options']),
                         ('distinct_lesion', ['45385', '45380'], str(engine.session), ['59', 'XS']))
        self.assertEqual(found['text'], checks.distinct_lesion_review_text(
            '45385', ['snare removal at the sigmoid colon'], [('45380', ['forceps biopsy at the transverse colon'])],
            ''))
        self.assertEqual(found['lesions'], {'45385': ['the lesion at the sigmoid colon'],
                                            '45380': ['the lesion at the transverse colon']})
        # dropped once the other code leaves the effective set, and with no FactSet nothing is offered
        self.assertIsNone(case.views({biopsy.key: 'reject'})[snare.key].modifier_review)
        self.assertIsNone(case.views(facts=None)[snare.key].modifier_review)
        # an approval with a modifier the review no longer offers is blocked
        approved = case.views({biopsy.key: 'reject', snare.key: review_view.Decided('approve', ('XS',))})[snare.key]
        self.assertIn('modifier review no longer applies', approved.blocker)

    def test_the_claims_manual_example_is_cited_from_the_retrieval_trace(self):
        case = self.case()
        retrieval = [{'code': '45380', 'passages': [{'passage_key': overlay.CLAIMS_EXAMPLE_PASSAGE,
                                                      'topic': overlay.CLAIMS_EXAMPLE_TOPIC, 'release': 'R1',
                                                      'source_key': 'not-bundled', 'section': '13', 'page': '4'}]}]
        cited = case.views(retrieval=retrieval)[case.rows[0].key].modifier_review
        self.assertEqual((cited['sources'][0]['release'], cited['sources'][0]['title']), ('R1', ''))
        self.assertIn('R1', cited['text'])


class AnswerBindingTests(SimpleTestCase):
    def test_an_answer_to_a_released_item_no_longer_binds(self):
        case = Case(two_visits().build(), ('99213', 1), ('99214', 1), member=AS.MemberContext())
        first, second = case.rows
        answer = [{'code': '99213', 'family': first.family, 'fact': first.questions[0]['fact'],
                   'value': 'not_documented'}]
        self.assertEqual(case.views(answers=answer)[first.key].reason, overlay.DETAIL_UNAVAILABLE)
        # 99214 rejected: 99213's base item is released and its item is the setting question - the answer given to the
        # base question binds to nothing now
        released = case.views({second.key: 'reject'}, answers=answer)[first.key]
        self.assertEqual((released.reason, released.status), ('', 'needs_clarification'))
        self.assertEqual([q['fact'] for q in released.questions], ['setting'])
        # an answer to the item it presents now binds
        setting = [{'code': '99213', 'family': first.family, 'fact': 'setting', 'value': 'cannot_confirm'}]
        self.assertEqual(case.views({second.key: 'reject'}, answers=setting)[first.key].reason,
                         overlay.DETAIL_UNAVAILABLE)

    def test_an_answer_to_a_stale_question_binds_only_when_it_asks_the_live_items_fact(self):
        """The refutation's problem 05 (fail-closed): when read time recomputed a code's item and cannot word it, the
        stored question stands, stale; an answer to it binds only when it asks the fact the code's item now holds (as
        assess binds an answer to the item it presents) - one about another fact excludes nothing, the code stays
        held. (45378 is READY beside 45386, excluded by a cited denial; reinstating 45386 holds it by rule (a), an item
        no message worded before DECISIONS D246 - its codes form words it now, so nothing is stale here and the binding
        half is what this input still proves. The stored questions are written here: one about another fact, one about
        base_included.)"""
        case = ReinstatementTests().excluded_case()
        by = {p.code: p for p in case.rows}
        for fact, binds in (('extent', False), ('base_included', True)):
            with self.subTest(stored_question=fact):
                asked = {'id': 'q-1', 'scope': 'proposal', 'family': by['45378'].family, 'fact': fact,
                         'question': 'A stored question.', 'reason': 'Its reason.'}
                rows = [replace(p, questions=(asked,)) if p.code == '45378' else p for p in case.rows]
                answer = [{'code': '45378', 'family': by['45378'].family, 'fact': fact, 'value': 'not_documented'}]

                def view(decisions):
                    return overlay.review_view(rows, decisions, completeness=case.completeness, facts=case.R,
                                               member=case.member, answers=answer)[by['45378'].key]

                self.assertEqual(view({}).reason, overlay.DETAIL_UNAVAILABLE)  # the question presented: it binds
                found = view({by['45386'].key: 'reinstate'})
                # DECISIONS D246 (BASE_INCLUDED's codes form; repair r3c's request R2, applied by the integration): read
                # time words the recomputed rule (a) item now, so nothing is stale on this input and the live item's
                # question is presented; the binding is as before - only an answer to base_included binds
                self.assertEqual((found.reason == overlay.DETAIL_UNAVAILABLE, found.stale), (binds, ()))
                if not binds:
                    self.assertEqual((found.status, [q['fact'] for q in found.questions]),
                                     ('needs_clarification', ['base_included']))


class ReinstatementTests(SimpleTestCase):
    def excluded_case(self):
        """45378 READY beside 45386, EXCLUDED and reinstatable by 4.6: it cites a current broad denial of dilation
        within the denial's own words (test_evaluate's Exclusion fixture)."""
        doc = EF.colonoscopy(snare=False)
        denial_event(doc)
        cited = TA.EvidenceSpan(0, 300, 325, TA.TEXT[300:325], True)
        return Case(doc.build(), ('45378', 1), ('45386', cited))

    def test_a_reinstated_code_adds_the_hold_it_makes_and_an_unwordable_one_holds_the_code(self):
        case = self.excluded_case()
        by = {p.code: p for p in case.rows}
        self.assertEqual((by['45386'].bucket, by['45386'].reinstatable, by['45378'].status),
                         ('excluded', True, 'ready'))
        views = case.views({by['45386'].key: 'reinstate'})
        base = views[by['45378'].key]
        # 45386 counted beside it holds 45378 by rule (a), never READY; DECISIONS D246's BASE_INCLUDED codes form words
        # the hold (it was a base question no message worded, held and marked stale; repair r3c's request R2, applied
        # by the integration)
        self.assertEqual((base.status, base.added, base.withheld_by), ('needs_clarification', ('base_included',),
                                                                       overlay.BASE_CHECK))
        self.assertEqual(base.stale, ())
        self.assertEqual([(q['fact'], q['question'], q['reason']) for q in base.questions], [(
            'base_included', 'Is 45378 reported separately from 45386 for this examination?',
            '45386 is also proposed for the documented colonoscopy; 45378 is normally not reported separately from it '
            '(internal profile rule; NCCI procedure-to-procedure edits are not connected). Held for the reviewer, not '
            'excluded.')])
        reinstated = views[by['45386'].key]
        # its stored gate passes and nothing holds it: it reads as stored (excluded, reinstated), approvable after the
        # reinstatement, as review_view reads one
        self.assertEqual((reinstated.active, reinstated.status, reinstated.reinstatement_clear),
                         (True, 'excluded', True))
        # nothing reinstated: as stored
        self.assertEqual(case.views()[by['45378'].key].status, 'ready')


class RaisedAtReadTimeTests(SimpleTestCase):
    """DECISIONS D252 (the integration owner's seam check, round w7r; the integration's fix of the combination, repair
    r4a-2's request R6): read time recomputes a held code's item as evaluate.item gives it at assess - with what
    evaluate knows of the holds it raised beside the FactSet (questions.Raised) - so XCHG's same-duct item and 3.2.6
    rule 2's unlisted-evidence item are assess's own. Without it read time named DUCT for SAME_DUCT, and DOUBT or
    SYNTHETIC_ACT for UNLISTED_EVIDENCE (the seam check: 154 of 10,193 scenes)."""

    def test_assess_and_read_time_name_one_item(self):
        from tests.v2.test_evaluate import UnlistedOnEvidence, stent_placement

        for name, R, message in (
                ('XCHG beside an unlisted removal (refute-4a-r2 p10)', stent_placement(Kind.STENT_REMOVAL).build(),
                 Q.MessageId.SAME_DUCT),
                ("3.2.6 rule 2: the unlisted removal on 43274's evidence", UnlistedOnEvidence.exchange(),
                 Q.MessageId.UNLISTED_EVIDENCE)):
            with self.subTest(name):
                case = Case(R, ('43274', 2))
                [found] = [p for p in case.assessment.codes if p.code == '43274']
                live = case.recount().live[found.key]
                self.assertEqual((live.item.message, found.item.message), (message, message))
                self.assertEqual((live.item, live.held), (found.item, found.held_facts))


class W8rCombinationTests(SimpleTestCase):
    """The integration's fixes of round w8r's combination (w8r/final NOTES): step 5a's request R1 (D260: read time's
    engine reads the competition as engine/assess.compete_without does) completed for refute-5a-r2's P-A, and repair
    r3c's request R2 (D257: BASE_WITHIN's whole named by its family, stated as possibly performed when it is)."""

    def test_p_a_a_cannot_confirm_beside_a_not_documented_rival_over_two_acts_is_reproduced(self):
        """refute-5a-r2 P-A: em_chain (99215, 99417 and 99214 over the visit E1 and an unlisted act; a colonoscopy
        beside, 45378 held base_included by 45385), a member's "Not documented" to 99215's item and "Cannot confirm"
        to 99214's (each order). engine/assess never assesses an answered code again, so its record keeps the
        competing hold its answer found; read time's engine reproduces every stored record all the same (before the
        fix: RecordMismatch, and nothing recomputed for the whole assessment), and a rejection of 45385 recomputes
        45378's base hold as with the one answer alone - never stale."""
        doc = TA.em_chain()
        doc.session(2, SessionKind.COLONOSCOPY, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER),
                    reached=[EF.sup(ct.Extent.CECUM)])
        doc.exam(3, session=EF.X(2))
        doc.lesion(1, lesion_places=[EF.sup(ct.Landmark.SIGMOID_COLON)])
        doc.act(4, Kind.SNARE, session=EF.X(2), places=[EF.sup(ct.Landmark.SIGMOID_COLON)], lesion=EF.sup(EF.L(1)),
                device=EF.sup(ct.Device.COLD_SNARE))
        codes = (('99215', 1), ('99417', 2), ('99214', 1), ('45378', 3), ('45385', 4))
        plain = TA.by_code(TA.run(doc.build(), *codes))
        self.assertEqual(plain['45378'].item.held.cause, combination.BASE_CAUSE)  # held by 45385's base rule
        for first, second in (('not_documented', 'cannot_confirm'), ('cannot_confirm', 'not_documented')):
            with self.subTest(first=first, second=second):
                given = (TA.answer(plain['99215'], value=first, answer_id='a1'),
                         TA.answer(plain['99214'], value=second, answer_id='a2'))
                case = Case(doc.build(), *codes, answers=given)
                found = TA.by_code(case.assessment)
                self.assertEqual((found['99215'].status, found['99214'].status), (AS.Outcome.EXCLUDED,) * 2)
                case.recount()  # reproduced: no RecordMismatch
                keys = {row.code: row.key for row in case.rows}
                view = case.views()[keys['45378']]
                self.assertEqual((view.recomputed, view.stale), ((), ()))
                view = case.views({keys['45385']: 'reject'})[keys['45378']]
                self.assertEqual((view.recomputed, view.stale), (('services.base_included',), ()))

    def test_d257_base_within_names_the_wholes_family_and_states_a_whole_only_possibly_done(self):
        """D257 at read time and in the renderer (item_slots, both): the whole named by its own family; stated as
        possibly performed on the date of service, its performance not established, exactly when no whole of the
        record is established done (combination.session_done) - an EUS done whose fit is only possible (its tract
        only possibly upper: refute-r3c-r1 F2) keeps v1's sentence, never "its performance is not established"."""
        from tests.v2 import test_combination as TC

        done = ('The documented upper endoscopy is the endoscopic portion of the endoscopic ultrasound documented with '
                'it, which 43242 accounts for;')
        possible = ('The documented upper endoscopy may be the endoscopic portion of the endoscopic ultrasound '
                    'documented with it, possibly performed on the date of service (its performance is not '
                    'established), which 43242 accounts for;')
        unresolved = TC.act(Kind.EXAMINATION, TC.X2, places=(EF.sup(ct.Landmark.PANCREAS),),
                            status=EF.unres(ct.Status.PERFORMED))
        for name, R, established, whole_possible, opening in (
                ('an established EUS', TC.egd_eus(), True, False, done),
                ('an EUS done, its tract only possibly upper', TC.egd_eus(tract=EF.unres(ct.Tract.UPPER)), False,
                 False, done),
                ('an EUS whose examination is only possibly done', TC.egd_eus(eus_exam=unresolved), False, True,
                 possible)):
            with self.subTest(name):
                R = TA.dated(R)
                joined = combination.combine([TC.member('sel:0', '43235', TC.X1, (TC.E1,)),
                                              TC.member('sel:1', '43242', TC.X2, (TC.E3,))],
                                             {TC.X1: combination.SessionActs(),
                                              TC.X2: combination.SessionActs(reportable=(TC.E3,))}, R)
                self.assertEqual(joined.within['sel:0'].established, established)
                held = joined.held['sel:0'][0]
                item = Q.Item(held=held, message=Q.MessageId.BASE_WITHIN,
                              fill=Q.Fill(code='43235', family=SessionKind.EGD))
                slots = overlay.item_slots(item, 'sel:0', joined, R)
                self.assertEqual((slots.whole_family, slots.whole_possible), (SessionKind.EUS, whole_possible))
                reason = wording.build(wording.Message.BASE_WITHIN, slots, '').reason
                self.assertTrue(reason.startswith(opening), reason)


# --- DECISIONS D254 rule 2: an act no kind names is named by Kind.OTHER in every act slot ----------------------------

R3C_LABEL = 'another act'  # step r3c's words for the label of an act no kind names (D254 rule 2: with its article)


def _tokens(sentence: str) -> list[str]:
    return [token.strip('.,;:()“”?') for token in sentence.split()]


class ActNoKindNamesTests(SimpleTestCase):
    """DECISIONS D254 rule 2 (refute-r3c-r1 R3C1-01, refute-5b-r1 F1, refute-r4d-r2 P4; the lead's VERIFY.md): an act no
    kind names - kind other, or a kind not established, for which engine/questions.act_kind gives Kind.OTHER (D267;
    it gave none before), and an unlisted entry of no kind - is named by Kind.OTHER in every slot item_slots fills
    (the base items' acts, the same-day acts listed and possible) and in the base blocker's names (overlay._kinds,
    _unlisted_kinds): the integration's I2, extended from SEPARATE_EM to all of them; I1 kept (D262). Before, such an
    act was dropped, an item naming only it was refused by wording, jobs.word_item raised and the whole document
    failed to assess (L1's mechanism). For each shape: the slots name Kind.OTHER, the renderer (jobs.word_item, as
    _render_code calls it) words the item, and read time words it as assess does."""

    def read_as_assessed(self, case, code):
        """``code``'s item in ``case`` (assessed, persisted, read back): the renderer's words are its stored question;
        read time words the item identically (overlay._words over the read-time engine's own combination); with no
        decision review_view presents the stored question, nothing recomputed or stale, and the read-time engine
        reproduces the code's held facts and item. Returns the renderer's (fact, question, reason)."""
        p = next(found for found in case.assessment.codes if found.code == code)
        row = next(stored for stored in case.rows if stored.key == p.key)
        spec = jobs.word_item(p.item, p.key, case.assessment.combination, case.R, TA.TEXT,
                              family=AS.family_slug(p.family))
        renderer = (spec.fact, spec.question, spec.reason)
        self.assertEqual([(q['fact'], q['question'], q['reason']) for q in row.questions], [renderer])
        found = case.recount()
        live = found.live[p.key]
        self.assertEqual((live.held, live.item, live.worded), (p.held_facts, p.item, None))
        again = overlay._words(live.item, p.key, found.joined, case.R)
        self.assertIsNotNone(again)
        self.assertEqual((again.fact, again.question, again.reason), renderer)
        view = case.views()[p.key]
        self.assertEqual((view.status, view.questions, view.recomputed, view.stale),
                         (row.status, row.questions, (), ()))
        return renderer

    def test_r3c1_01_an_act_of_contradicted_kind_is_named_by_kind_other_in_the_base_question(self):
        """45378 alone beside the act of contradicted kind (p07), and 45330 beside 99213 and a same-day flexible
        sigmoidoscopy whose act's kind is contradicted (p06): base_included on the act in doubt, named by Kind.OTHER -
        before, listed and codes were both empty and wording refused."""
        for name, doc, codes, code, act, family in (
                ('p07: 45378 alone', contradicted_act(), (('45378', 1),), '45378', EF.E(2), SessionKind.COLONOSCOPY),
                ('p06: 45330 beside 99213', office_and_unnamed_act(exam=True), (('99213', 1), ('45330', 2)), '45330',
                 EF.E(3), SessionKind.FLEX_SIG)):
            with self.subTest(name):
                case = Case(doc.build(), *codes)
                p = next(found for found in case.assessment.codes if found.code == code)
                base = case.assessment.combination.bases[p.key]
                self.assertEqual(p.item.message, Q.MessageId.BASE_INCLUDED)
                self.assertEqual((base.doubted, base.unlisted, base.named_codes), ((act,), (), ()))
                self.assertIs(Q.act_kind(case.R, act, ()), Kind.OTHER)
                self.assertEqual(overlay.item_slots(p.item, p.key, case.assessment.combination, case.R),
                                 wording.Slots(code=code, family=family, listed=(Kind.OTHER,), codes=()))
                self.read_as_assessed(case, code)

    def test_5b_f1_an_eus_act_of_kind_other_is_named_by_kind_other_in_the_base_explanation(self):
        """43259 alone, and 43259 with 64530 (p2, p2b): base_explained on the reportable act of kind other (D137) with
        no code to name, named by Kind.OTHER - before, codes and listed were both empty and wording refused."""
        for codes in ((('43259', 1),), (('43259', 1), ('64530', 2))):
            with self.subTest(codes=codes):
                case = Case(eus_other_act().build(), *codes)
                p = next(found for found in case.assessment.codes if found.code == '43259')
                base = case.assessment.combination.bases[p.key]
                self.assertEqual(p.item.message, Q.MessageId.BASE_EXPLAINED)
                self.assertEqual((base.reportable, base.named_codes), ((EF.E(2),), ()))
                self.assertIs(Q.act_kind(case.R, EF.E(2), ()), Kind.OTHER)
                self.assertEqual(overlay.item_slots(p.item, p.key, case.assessment.combination, case.R),
                                 wording.Slots(code='43259', family=SessionKind.EUS, codes=(), listed=(Kind.OTHER,)))
                self.read_as_assessed(case, '43259')

    def test_5b_f1_read_time_words_the_base_explanation_afresh_as_assess_words_it_alone(self):
        """43259 beside 43242: the base explanation names 43242 (BASE_EXPLAINED's codes form, written out). The reviewer
        rejects 43242, so read time words the item afresh over the act of kind other - exactly 43259 assessed alone (its
        stored question). Before, wording refused the renamed item, and the stored question naming the rejected 43242
        stood, marked stale."""
        case = Case(eus_other_act().build(), ('43259', 1), ('43242', 2))
        alone = Case(eus_other_act().build(), ('43259', 1))
        first, second = case.rows
        self.assertEqual((first.questions[0]['question'], first.questions[0]['reason']),
                         base_codes('43259', wording.service_phrase(SessionKind.EUS), '43242'))
        view = case.views({second.key: 'reject'})[first.key]
        self.assertEqual((view.status, view.recomputed, view.stale, view.added, view.released),
                         ('needs_clarification', (overlay.BASE_CHECK,), (), (), ()))
        self.assertEqual([(q['fact'], q['question'], q['reason']) for q in view.questions],
                         [(q['fact'], q['question'], q['reason']) for q in alone.rows[0].questions])
        found = case.recount([first.key])
        self.assertEqual(overlay.item_slots(found.live[first.key].item, first.key, found.joined, case.R),
                         wording.Slots(code='43259', family=SessionKind.EUS, codes=(), listed=(Kind.OTHER,)))

    def test_the_same_day_act_no_kind_names_is_named_by_kind_other_in_the_separate_visit_item(self):
        """99213 beside a same-day flexible sigmoidoscopy whose act E3 no kind names: SEPARATE_EM's slots name it by
        Kind.OTHER wherever it falls - a done act (kind other) in listed, a possible act (a contradicted kind) in
        possible - beside the examination's own kind when the examination is filed (before, the act was named only
        when the day had nothing else to name: I2, now extended by D254 rule 2), and give the same-day codes only when
        the day has no act to list (I1: an act no kind names is now an act to list)."""
        for name, doc, codes, listed, possible, same_day in (
                ("I2's input: a done act of kind other", office_and_unnamed_act(exam=False, kind=Kind.OTHER),
                 (('99213', 1),), (Kind.OTHER,), (), ()),
                ("I2's input: a possible act of contradicted kind", office_and_unnamed_act(exam=False),
                 (('99213', 1),), (), (Kind.OTHER,), ()),
                ('beside the examination: a done act of kind other', office_and_unnamed_act(exam=True, kind=Kind.OTHER),
                 (('99213', 1),), (Kind.EXAMINATION, Kind.OTHER), (), ()),
                ('beside the examination: a possible act of contradicted kind', office_and_unnamed_act(exam=True),
                 (('99213', 1), ('45330', 2)), (Kind.EXAMINATION,), (Kind.OTHER,), ()),
                ('beside a counted code: the act is listed, never the code', office_and_unnamed_act(exam=False),
                 (('99213', 1), ('45330', 3)), (), (Kind.OTHER,), ()),
                ("I1's input: no act to list, the counted codes", office_and_undated_colonoscopy(),
                 (('99213', 1), ('45385', 3), ('45378', 2)), (), (), ('45385', '45378'))):
            with self.subTest(name):
                case = Case(doc.build(), *codes)
                p = next(found for found in case.assessment.codes if found.code == '99213')
                self.assertEqual(p.item.message, Q.MessageId.SEPARATE_EM)
                self.assertEqual(overlay.item_slots(p.item, p.key, case.assessment.combination, case.R),
                                 wording.Slots(code='99213', family=SessionKind.OFFICE_EM, listed=listed,
                                               possible=possible, codes=same_day))
                self.read_as_assessed(case, '99213')

    def test_the_possible_acts_and_the_undatable_entries_are_one_slot_each_kind_once(self):
        """SEPARATE_EM's possible slot reads the day's possible acts and its undatable unlisted entries as one slot,
        each kind once, as I2 named a day of such acts by one Kind.OTHER: a possible act of contradicted kind beside an
        unlisted entry of no kind is one Kind.OTHER, and a possible snare beside an unlisted snare one Kind.SNARE. The
        procedure day is written here (combination.ProcedureDay over the FactSet's own ids), so the slot is read
        whichever item the engine presents first."""
        case = Case(office_and_unnamed_act(exam=False).build(), ('99213', 1))
        p = case.assessment.codes[0]
        self.assertEqual(p.item.message, Q.MessageId.SEPARATE_EM)
        day = combination.ProcedureDay(possible=(SessionKind.FLEX_SIG,), possible_acts=(EF.E(3),),
                                       undatable_unlisted=(0,))
        for kind, entry, expected in ((CONTRADICTED_KIND, None, (Kind.OTHER,)), (Kind.SNARE, Kind.SNARE, (Kind.SNARE,)),
                                      (CONTRADICTED_KIND, Kind.SNARE, (Kind.OTHER, Kind.SNARE))):
            with self.subTest(act=kind, entry=entry):
                doc = office_and_unnamed_act(exam=False, kind=kind)
                doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.ACT, entry, None, EF.Span(3000, 3040)))
                slots = overlay.item_slots(p.item, p.key, replace(case.assessment.combination, day=day),
                                           TA.dated(doc.build()))
                self.assertEqual((slots.listed, slots.possible, slots.codes), ((), expected, ()))

    def test_r4d_p4_a_kindless_unlisted_act_is_named_by_kind_other_in_the_base_question(self):
        """An unlisted act of no kind carded to the colonoscopy beside 45378 alone (S2c), or to a feeding-tube session
        beside 43235 alone (S1): base_included on the synthetic act, named by Kind.OTHER (_unlisted_kinds) - before,
        listed and codes were both empty and wording refused."""
        for name, doc, code, family in (('S2c', kindless_entry_colonoscopy(), '45378', SessionKind.COLONOSCOPY),
                                        ('S1', kindless_entry_feeding_tube(), '43235', SessionKind.EGD)):
            with self.subTest(name):
                case = Case(doc.build(), (code, 1))
                p = case.assessment.codes[0]
                base = case.assessment.combination.bases[p.key]
                self.assertEqual(p.item.message, Q.MessageId.BASE_INCLUDED)
                self.assertEqual((case.R.unlisted[0].kind, base.doubted, base.unlisted, base.named_codes),
                                 (None, (), (0,), ()))
                self.assertEqual(overlay.item_slots(p.item, p.key, case.assessment.combination, case.R),
                                 wording.Slots(code=code, family=family, listed=(Kind.OTHER,), codes=()))
                self.read_as_assessed(case, code)

    def test_the_base_blocker_names_an_act_no_kind_names(self):
        """overlay._base_of - the names _held_blocker gives the approval a base rule now holds - names the act no kind
        names by Kind.OTHER's label, never nothing (before: ('included', ()), and the blocker read "the documented
        colonoscopy includes , which this diagnostic code does not account for")."""
        for name, doc, code in (('R3C1-01', contradicted_act(), '45378'), ('5b F1', eus_other_act(), '43259'),
                                ('r4d S2c', kindless_entry_colonoscopy(), '45378')):
            with self.subTest(name):
                case = Case(doc.build(), (code, 1))
                key = case.rows[0].key
                found = case.recount()
                # D254 rule 2's one label (repair r3c's wording.kind_words; v1's event_kind_label keeps 'act'): the
                # integration's restatement - the test asserted Kind.OTHER's v1 label, which r3c left unchanged
                self.assertEqual(overlay._base_of(found.live[key], found.joined, key, case.R),
                                 ('included', (wording.kind_words(Kind.OTHER),)))

    def test_r3c_an_act_no_kind_names_is_worded_another_act_with_its_article(self):
        """Step r3c's words for D254 rule 2's label (repair r3c of round w8r: "another act", its article included;
        before it wording labelled Kind.OTHER 'act', with no article: R3C1-03). Every item above, the renderer's and
        read time's alike, names the act "another act" in its question or its reason and never by the bare label; so
        does read time's own base blocker."""
        sentences = []
        for name, doc, codes, code in (
                ('R3C1-01', contradicted_act(), (('45378', 1),), '45378'),
                ('p06', office_and_unnamed_act(exam=True), (('99213', 1), ('45330', 2)), '45330'),
                ('5b F1', eus_other_act(), (('43259', 1),), '43259'),
                ('5b F1 with 64530', eus_other_act(), (('43259', 1), ('64530', 2)), '43259'),
                ("I2's done act", office_and_unnamed_act(exam=False, kind=Kind.OTHER), (('99213', 1),), '99213'),
                ("I2's possible act", office_and_unnamed_act(exam=False), (('99213', 1),), '99213'),
                ('beside the examination', office_and_unnamed_act(exam=True), (('99213', 1),), '99213'),
                ('r4d S2c', kindless_entry_colonoscopy(), (('45378', 1),), '45378'),
                ('r4d S1', kindless_entry_feeding_tube(), (('43235', 1),), '43235')):
            _, question, reason = self.read_as_assessed(Case(doc.build(), *codes), code)
            sentences += [(name, question), (name, reason)]
        case = Case(eus_other_act().build(), ('43259', 1), ('43242', 2))
        view = case.views({case.rows[1].key: 'reject'})[case.rows[0].key]
        sentences += [('read time, 43242 rejected', q[part]) for q in view.questions for part in ('question', 'reason')]
        case = Case(contradicted_act().build(), ('45378', 1))
        p, found = case.rows[0], case.recount()
        held = overlay._base_of(found.live[p.key], found.joined, p.key, case.R)
        sentences.append(('the base blocker', overlay._held_blocker(p, held, case.rows,
                                                                    overlay._service(p, case.coding, None))))
        # D254 rule 2 labels an act wherever wording turns a kind into words: each item names it "another act" in its
        # question or its reason (SEPARATE_EM's question is v1's constant and names no act: its reason names it - the
        # integration's restatement, refute-5c-r1 P1), and no sentence names it by the bare label
        named: dict[str, list[str]] = {}
        for name, sentence in sentences:
            named.setdefault(name, []).append(sentence)
            with self.subTest(name, sentence=sentence):
                self.assertNotIn('act', _tokens(sentence.lower().replace(R3C_LABEL, '')))
        for name, group in named.items():
            with self.subTest(name, sentences=group):
                self.assertIn(R3C_LABEL, ' '.join(group).lower())


# --- repair round w9r: DECISIONS D267, D268 and D270 at read time -----------------------------------------------------

def proposal_of(row: overlay.Stored) -> SimpleNamespace:
    """``row`` as review._actions reads a Proposal (its bucket, status, reinstatement and checks), its kept evidence the
    exact spans of test_assess's text (context 0), so the product's own action rule says whether it is approvable."""
    return SimpleNamespace(bucket=row.bucket, status=row.status, reinstatable=row.reinstatable, checks=list(row.checks),
                           evidence=[{**span, 'context_index': 0, 'exact': True} for span in row.evidence])


def ercp_cholangioscopy() -> EF.Doc:
    """The lead's probe v8_addon_act (refute-r4d-r1 V8R4D1-1, TRIAGE G2-08): an ERCP X1 with its examination E1, a
    biliary cannulation E2 achieved and a cholangioscopy E3 of the bile duct - 43273's supporting act."""
    doc = EF.Doc()
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    doc.act(2, Kind.CANNULATION, access=EF.sup(ct.AccessOutcome.ACHIEVED), duct=EF.sup(ct.Duct.BILIARY))
    doc.act(3, Kind.CHOLANGIOSCOPY, duct=EF.sup(ct.Duct.BILIARY))
    return doc


ADDON_PAIR = (('43260', 1), ('43273', 3))  # the lead's probe's codes: 43260 (43273's primary), 43273 (cholangioscopy)


def denied_stone_ercp() -> EF.Doc:
    """test_assess's ercp(stone=False) with E6, a broad denial of stone extraction whose kind and status words are its
    whole unit (600 .. 660): 43264 citing that unit (DENIED_STONE) is EXCLUDED by citation, reinstatable, so 43273 has
    no primary counted and its ADDON row holds it (test_assess.AddonTests)."""
    doc = TA.ercp(stone=False)
    doc.act(6, Kind.STONE_EXTRACTION, status=EF.neg(ct.Status.PERFORMED), breadth=EF.sup(ct.Breadth.ALL_OF_KIND),
            kind_words=EF.Span(600, 630), status_words=EF.Span(630, 660))
    return doc


DENIED_STONE = TA.EvidenceSpan(0, 600, 660, TA.TEXT[600:660], True)
OFFICE_ADDON = (('99215', 1), ('99214', 1), ('99417', 2))  # test_assess.office_prolonged: 99215 and 99214 compete


def addon_holds(held) -> list:
    return [found for found in held if found.cause == AS.ADDON_CAUSE]


class D268AddonTests(SimpleTestCase):
    """DECISIONS D268's read-time half (refute-r4d-r1 V8R4D1-1, high; TRIAGE G2-08): read time applies the ADDON row as
    engine/assess does (D260's agreement). A primary the reviewer rejects - or a member's answer excludes - is no longer
    counted, so an add-on whose every counted primary is gone is held by the row's witness (coding_rule:ADDON) and is
    not approvable alone; reinstating the primary releases it.

    DECISIONS D284, G3-15 (build list B7; restated in AMENDMENT-2's build, step f6): the row's item is worded by its own
    message, ADDON, from the codes alone (TEXT_FREE: the add-on and its primaries, engine/assess.primaries) - so read
    time words it afresh: the view's questions carry the ADDON question (with its message, which customer_api reads),
    ``recomputed`` names the row (ADDON_CHECK) and nothing is stale. (Before, the item was STATUS's, which quotes the
    document: the stored question stood, marked stale.)"""

    def test_the_leads_probe_a_rejected_primary_holds_its_add_on_and_it_is_not_approvable(self):
        """The lead's probe: 43260 and 43273 proposed, 43273 READY on the cholangioscopy (its primary counted). With
        43260 rejected, 43273 is held by its ADDON row - its held facts and item exactly 43273's assessed alone - and
        the product offers no approval; an approval taken before is blocked. The reverse decision (none): ready and
        approvable, as stored."""
        case = Case(ercp_cholangioscopy().build(), *ADDON_PAIR)
        alone = TA.by_code(TA.run(ercp_cholangioscopy().build(), ('43273', 3)))['43273']
        by = {row.code: row for row in case.rows}
        addon, primary = by['43273'], by['43260']
        self.assertEqual((addon.status, addon.questions), ('ready', ()))
        self.assertEqual(addon_holds(alone.held_facts), [AS.addon_hold('43273', (), alone.evidence.kept)])
        view = case.views()[addon.key]  # the reverse decision: no decision, its primary counted
        self.assertEqual((view.status, view.added, view.stale, view.blocker), ('ready', (), (), ''))
        self.assertEqual(review._actions(proposal_of(addon), None, TA.TEXT, view=view), [review.APPROVE, review.REJECT])
        rejected = {primary.key: 'reject'}
        view = case.views(rejected)[addon.key]
        worded = wording.build(wording.Message.ADDON, wording.Slots(code='43273', family=alone.item.fill.family,
                                                                    codes=tuple(sorted(AS.primaries('43273')))), '')
        self.assertIs(alone.item.message, Q.MessageId.ADDON)
        self.assertEqual((view.status, view.questions, view.added, view.released, view.recomputed, view.stale),
                         ('needs_clarification', ({'id': '', 'scope': 'proposal', 'family': addon.family,
                                                   'fact': worded.fact, 'question': worded.question,
                                                   'reason': worded.reason, 'message': 'addon'},),
                          ('performed_status',), (), (overlay.ADDON_CHECK,), ()))
        self.assertIn('43260', worded.question)  # it names the primaries, from the codes alone
        self.assertEqual(view.same_day_held, False)
        self.assertEqual(review._actions(proposal_of(addon), None, TA.TEXT, view=view), [review.REJECT])
        live = case.recount([addon.key]).live[addon.key]
        self.assertEqual((live.held, live.item), (alone.held_facts, alone.item))
        self.assertEqual(addon_holds(live.holds), addon_holds(alone.held_facts))
        self.assertEqual((live.stored_holds, live.moved), ((), True))
        approved = case.views({**rejected, addon.key: 'approve'})[addon.key]
        self.assertEqual(approved.blocker, '43273 was approved, but it now needs clarification; revoke the approval')
        # an approval of 43260 counts it as the primary: 43273 stays ready
        self.assertEqual(case.views({primary.key: 'approve'})[addon.key].status, 'ready')

    def test_reinstating_the_primary_releases_the_add_on(self):
        """43264 EXCLUDED by its cited denial (reinstatable) leaves 43273 with no primary: assess holds it by the row.
        The reviewer reinstates 43264: the row is met, its hold released, and 43273 has no hold left - ready, its
        stored question dropped. The reverse decision (none): held as stored, nothing recomputed."""
        case = Case(denied_stone_ercp().build(), ('43264', DENIED_STONE), ('43273', 3))
        by = {row.code: row for row in case.rows}
        addon, primary = by['43273'], by['43264']
        self.assertEqual((primary.bucket, primary.reinstatable), ('excluded', True))
        stored = TA.by_code(case.assessment)['43273']
        self.assertEqual([held.cause for held in stored.held_facts], [AS.ADDON_CAUSE])
        view = case.views()[addon.key]
        self.assertEqual((view.status, view.questions, view.recomputed, view.stale),
                         ('needs_clarification', addon.questions, (), ()))
        view = case.views({primary.key: 'reinstate'})[addon.key]
        self.assertEqual((view.status, view.questions, view.added, view.released, view.recomputed, view.stale),
                         ('ready', (), (), ('performed_status',), (overlay.ADDON_CHECK,), ()))
        live = case.recount(case.engine_keys + [primary.key]).live[addon.key]
        self.assertEqual((live.held, live.item, live.holds), ((), None, ()))
        self.assertEqual(addon_holds(live.stored_holds), addon_holds(stored.held_facts))

    def test_an_answer_that_excludes_the_last_primary_holds_the_add_on(self):
        """An office visit with prolonged time: 99215 and 99214 compete for the visit (each held by the base rule),
        99417 READY beside 99215. A member's answer to 99215's base question - the overlay's to apply - excludes 99215
        at read time ("Not documented" and "Cannot confirm" alike): the ADDON row counts no answered code (as
        engine/assess counts none), so 99417 is held by it, never approvable alone, and is never held as a same-day
        visit by it. The reverse (no answer): ready. A rejection of 99215 holds 99417 the same way."""
        case = Case(TA.office_prolonged().build(), *OFFICE_ADDON)
        by = {row.code: row for row in case.rows}
        addon, primary = by['99417'], by['99215']
        self.assertEqual((addon.status, [q['fact'] for q in primary.questions]), ('ready', ['base_included']))
        self.assertEqual(case.views()[addon.key].status, 'ready')
        for value in ('not_documented', 'cannot_confirm'):
            with self.subTest(value=value):
                answers = [{'code': '99215', 'family': primary.family, 'fact': 'base_included', 'value': value}]
                views = case.views(answers=answers)
                self.assertEqual(views[primary.key].reason, overlay.DETAIL_UNAVAILABLE)
                view = views[addon.key]
                self.assertEqual((view.status, view.added, view.recomputed, view.stale, view.same_day_held),
                                 ('needs_clarification', ('performed_status',), (overlay.ADDON_CHECK,), (), False))
                self.assertEqual([q.get('message') for q in view.questions], ['addon'])  # B7: worded afresh
                self.assertEqual(review._actions(proposal_of(addon), None, TA.TEXT, view=view), [review.REJECT])
        view = case.views({primary.key: 'reject'})[addon.key]
        self.assertEqual((view.status, view.added, view.recomputed, view.stale, view.same_day_held),
                         ('needs_clarification', ('performed_status',), (overlay.ADDON_CHECK,), (), False))

    def test_where_nothing_can_be_recomputed_a_rejected_primary_still_holds_the_add_on(self):
        """Fail-closed with no FactSet (DECISIONS D268; overlay._addon_unrecomputed, from the codes alone): a rejection
        that leaves an add-on with no primary is a hold a decision adds, which the stale stored record does not carry -
        the add-on is held, stale, not approvable; a reinstated primary would release the stored hold, which stands,
        stale. The reverse decisions (none): as stored."""
        case = Case(ercp_cholangioscopy().build(), *ADDON_PAIR)
        by = {row.code: row for row in case.rows}
        addon = by['43273']
        self.assertEqual(case.views(facts=None)[addon.key].status, 'ready')
        view = case.views({by['43260'].key: 'reject'}, facts=None)[addon.key]
        self.assertEqual((view.status, view.questions, view.stale), ('needs_clarification', (), (overlay.ADDON_CHECK,)))
        self.assertEqual(review._actions(proposal_of(addon), None, TA.TEXT, view=view), [review.REJECT])
        denied = Case(denied_stone_ercp().build(), ('43264', DENIED_STONE), ('43273', 3))
        by = {row.code: row for row in denied.rows}
        view = denied.views({by['43264'].key: 'reinstate'}, facts=None)[by['43273'].key]
        self.assertEqual((view.status, view.questions, view.stale),
                         ('needs_clarification', by['43273'].questions, (overlay.ADDON_CHECK,)))
        self.assertEqual(denied.views(facts=None)[by['43273'].key].stale, ())

    def test_a_reinstated_add_on_its_row_holds_is_never_approvable(self):
        """An add-on excluded and reinstatable (its record the renderer's shape for an exclusion: no held facts, a
        passing reinstatement gate), reinstated beside its counted primary: the row is met and the reinstatement may be
        approved. With the primary rejected too, the row holds it: needs clarification, its reinstatement not clear,
        approval withheld by the row (ADDON_CHECK), so review offers no approval."""
        case = Case(ercp_cholangioscopy().build(), *ADDON_PAIR)
        by = {row.code: row for row in case.rows}
        gate = {'id': overlay.REINSTATEMENT_CHECK, 'label': 'Approval after reinstatement', 'status': 'pass',
                'detail': '', 'source': ''}
        excluded = replace(by['43273'], bucket='excluded', status='excluded', reinstatable=True, checks=(gate,),
                           support={**by['43273'].support, 'held_facts': [], 'item': None})
        rows = [by['43260'], excluded]
        reinstate = SimpleNamespace(action='reinstate')

        def view(decisions):
            return overlay.review_view(rows, decisions, completeness=case.completeness, facts=case.R,
                                       member=case.member)[excluded.key]

        met = view({excluded.key: 'reinstate'})
        self.assertEqual((met.reinstatement_clear, met.withheld_by, met.added), (True, '', ()))
        self.assertIn(review.APPROVE, review._actions(proposal_of(excluded), reinstate, TA.TEXT, view=met))
        held = view({excluded.key: 'reinstate', by['43260'].key: 'reject'})
        self.assertEqual((held.status, held.reinstatement_clear, held.withheld_by, held.added),
                         ('needs_clarification', False, overlay.ADDON_CHECK, ('performed_status',)))
        self.assertNotIn(review.APPROVE, review._actions(proposal_of(excluded), reinstate, TA.TEXT, view=held))

    def test_the_rows_are_reproduced_and_a_stored_hold_the_inventory_does_not_give_is_refused(self):
        """The engine's own counted set reproduces a stored ADDON hold (assess's last pass: its codes no answer
        excluded); ONE rule for every hold read time recomputes (DECISIONS D283, G3-32 option (b); build list B20): a
        stored hold of a cause read time recomputes that the inventory does not give - an ADDON hold removed from a held
        add-on or added to a ready one, a competing hold whose rival is not proposed, and a base, base-within or same-day
        hold added to a code the engine does not hold so - is a record that is not reproduced (RecordMismatch: nothing
        is recomputed from it), never a hold carried beside the recomputed ones (a hold REMOVED from a stored record
        already fails the ranked comparison)."""
        denied = Case(denied_stone_ercp().build(), ('43264', DENIED_STONE), ('43273', 3))
        by = {row.code: row for row in denied.rows}
        stored = TA.by_code(denied.assessment)['43273']
        live = denied.recount().live[by['43273'].key]
        self.assertEqual((live.held, live.holds, live.stored_holds), (stored.held_facts,) * 3)
        pair = Case(ercp_cholangioscopy().build(), *ADDON_PAIR)
        ready = next(row for row in pair.rows if row.code == '43273')
        planted = AS.jsonable(AS.addon_hold('43273', (), stored.evidence.kept))
        dilation = Case(TA.one_dilation().build(), ('43249', 2), ('43233', 2))
        first = dilation.rows[0]
        self.assertIn('competing_codes', [found['fact'] for found in first.support['held_facts']])
        # B20: a base, base-within and same-day hold planted on a code the engine does not hold so (a colonoscopy's
        # 45385 alone), each in the form the combination stores it (engine/assess.jsonable of a HeldFact of the cause)
        alone = Case(EF.colonoscopy().build(), ('45385', 2))
        [snare] = alone.rows
        self.assertEqual(snare.status, 'ready')
        tampered = {}
        for cause, fact in ((combination.BASE_CAUSE, 'base_included'), (combination.WITHIN_CAUSE, 'base_included'),
                            (combination.SAME_DAY_CAUSE, 'separate_em')):
            held = HeldFact(fact=fact, attribute=None, subject=None, result=None, kind=ItemKind.QUESTION, cause=cause,
                            reason=None, spans=(), rank=None)
            tampered[cause] = [replace(snare, support={**snare.support, 'held_facts': [AS.jsonable(held)]})]
        for name, case, rows, counted in (
                ('the ADDON hold removed', denied,
                 [replace(by['43273'], support={**by['43273'].support, 'held_facts': []}), by['43264']], None),
                ('an ADDON hold added', pair,
                 [row if row is not ready else replace(ready, support={**ready.support, 'held_facts': [planted]})
                  for row in pair.rows], None),
                ('a competing hold whose rival is not proposed', dilation, [first], [first.key]),
                ('a base hold added', alone, tampered[combination.BASE_CAUSE], None),
                ('a base-within hold added', alone, tampered[combination.WITHIN_CAUSE], None),
                ('a same-day hold added', alone, tampered[combination.SAME_DAY_CAUSE], None)):
            with self.subTest(name):
                keys = counted if counted is not None else case.engine_keys
                with self.assertRaises(overlay.RecordMismatch):
                    overlay.recount(rows, keys, keys, case.coding, case.R, member=case.member,
                                    uncounted=overlay.assessed_uncounted(case.completeness, rows))
        # the control: the untampered record is reproduced, and the rule is every cause read time recomputes
        overlay.recount(alone.rows, alone.engine_keys, alone.engine_keys, alone.coding, alone.R, member=alone.member)
        self.assertEqual(overlay._RECOMPUTED, frozenset(overlay._RULE_IDS))
        self.assertEqual(overlay._RECOMPUTED, frozenset({combination.BASE_CAUSE, combination.WITHIN_CAUSE,
                                                        combination.COMPETING_CAUSE, combination.SAME_DAY_CAUSE,
                                                        AS.ADDON_CAUSE}))


def office_with_denied_biopsy() -> EF.Doc:
    """D270 DQ-2's read-time half on an input where a decision unbinds the answer: two_visits (99213 and 99214, each
    held by the base rule and the competition for the one visit) beside a colonoscopy X2 whose only event is E3, a broad
    denial of biopsies (test_assess's DENIAL_SPAN unit, 300 .. 360): 45380 citing it is EXCLUDED by citation,
    reinstatable, and nothing makes the date a procedure day - until the reviewer reinstates 45380."""
    doc = two_visits()
    doc.session(2, SessionKind.COLONOSCOPY, reached=[EF.sup(ct.Extent.CECUM)])
    doc.act(3, Kind.BIOPSY, session=EF.X(2), status=EF.neg(ct.Status.PERFORMED), breadth=EF.sup(ct.Breadth.ALL_OF_KIND),
            kind_words=EF.Span(300, 330), status_words=EF.Span(330, 360))
    return doc


VISITS_AND_DENIAL = (('99213', 1), ('99214', 1), ('45380', TA.DENIAL_SPAN))


class R2AReadTimeAddonCountTests(SimpleTestCase):
    """DECISIONS D294 RD-2 at read time (repair r2, builder R2A): read time counts the ADDON row's primaries as assess
    does (engine/assess.addon_uncounted, the one rule): a primary that a statement may exclude is not counted over the
    engine's own set, so the stored ADDON hold of an add-on beside such a primary is reproduced (never a RecordMismatch)
    and kept live - and, over the reviewer's set, a primary the reviewer reinstated counts (D268: test_overlay's
    D268AddonTests.test_reinstating_the_primary_releases_the_add_on)."""

    def test_an_add_on_beside_a_primary_a_statement_may_exclude_stays_held_at_read_time(self):
        doc = denied_stone_ercp()
        doc.events[EF.E(6)] = {**doc.events[EF.E(6)], ct.Attribute.SCOPE_BREADTH: (EF.unres(ct.Breadth.ALL_OF_KIND),)}
        case = Case(doc.build(), ('43264', DENIED_STONE), ('43273', 3))
        by = {row.code: row for row in case.rows}
        addon, primary = by['43273'], by['43264']
        self.assertEqual((primary.bucket, primary.status, addon.status),
                         ('selected', 'needs_clarification', 'needs_clarification'))
        stored = TA.by_code(case.assessment)['43273']
        self.assertEqual([held.cause for held in stored.held_facts], [AS.ADDON_CAUSE])
        live = case.recount().live[addon.key]  # the engine's own set reproduces the stored record
        self.assertEqual((live.held, live.item), (stored.held_facts, stored.item))
        self.assertEqual(addon_holds(live.holds), addon_holds(stored.held_facts))
        view = case.views()[addon.key]
        self.assertEqual((view.status, view.added, view.released, view.stale), ('needs_clarification', (), (), ()))


def released_by_assess(case: Case, key: str, *, frozen: bool) -> tuple[list, dict]:
    """(rows, completeness) of ``case`` - assessed with a member's overlay-bound "Not documented" to ``key``'s item -
    as DECISIONS D270 DQ-2's assess half records it (step 5a: assess reads that answer for the competition alone, as
    D260 reads an engine-bound one, never excluding the code): the competition read without ``key`` through
    engine/assess.compete_without, the one implementation, each code's competing hold and rivals replaced by that
    competition's - ``key``'s own record kept as its answer found it when ``frozen`` (as assess keeps an answered
    code's), or assessed again. This step's tree predates step 5a, so the record is written here."""
    A = case.assessment
    released = AS.compete_without(A.combination, TA.members_of(A), frozenset({key}), case.R)
    codes = []
    for p in A.codes:
        if p.bucket is not AS.Bucket.SELECTED or (frozen and p.key == key):
            codes.append(p)
            continue
        kept = [found for found in p.held_facts if found.cause != combination.COMPETING_CAUSE]
        kept += [found for found in released.held.get(p.key, ()) if found.cause == combination.COMPETING_CAUSE]
        codes.append(replace(p, held_facts=Q.ranked(kept, case.R), competes=tuple(released.competes.get(p.key, ()))))
    return persist(replace(A, codes=tuple(codes), combination=released), case.R)


class D270AnswerTests(SimpleTestCase):
    """DECISIONS D270: assess, read time and the customer's account agree on answers - DQ-3 (refute-5a-r2 DQ-3; TRIAGE
    G2-09): a rival the reviewer rejects leaves the competition whatever it was answered, "Cannot confirm" included, so
    the competition hold's own sentence is true (D260's effect, "Cannot confirm" keeps the hold until a decision,
    stays); DQ-2 (refute-5a-r2 DQ-2; TRIAGE G2-10): the engine's own competition reads without a code assess took out
    by an overlay-bound "Not documented" (overlay.assessed_out, from the stored record), and a decision that unbinds the
    answer restores the competition."""

    @staticmethod
    def cannot_confirm(codes):
        held = TA.by_code(TA.run(TA.egd_dilation().build(), *codes))['43249']
        return Case(TA.egd_dilation().build(), *codes, answers=(TA.answer(held, value='cannot_confirm'),))

    def test_dq3_rejecting_a_rival_answered_cannot_confirm_releases_the_remaining_code(self):
        """refute-5a-r2 DQ-3's input: egd_dilation, 43249 and 43213 (held by the competition alone), "Cannot confirm"
        read at assess on 43249's technique. With no decision 43213 keeps its competing hold (D260's effect, as stored).
        The reviewer rejects 43249: 43213's competing hold is released, and it is ready with no question - as assess
        gives 43213 proposed alone - and approvable; the rejected rival stays out of review. The reverse decision
        (none): held again, as stored."""
        case = self.cannot_confirm((('43249', 2), ('43213', 2)))
        alone = Case(TA.egd_dilation().build(), ('43213', 2))
        by = {row.code: row for row in case.rows}
        rival, remaining = by['43249'], by['43213']
        self.assertEqual(overlay.answered_by_engine(rival), ('technique', 'cannot_confirm'))
        self.assertTrue(overlay.counts(rival, overlay._decided('reject')))  # counted whatever its decision
        view = case.views()[remaining.key]
        self.assertEqual((view.status, view.questions, view.released, view.recomputed, view.stale),
                         ('needs_clarification', remaining.questions, (), (), ()))
        self.assertEqual([q['fact'] for q in view.questions], ['competing_codes'])
        views = case.views({rival.key: 'reject'})
        view = views[remaining.key]
        self.assertEqual((view.status, view.questions, view.released, view.recomputed, view.stale),
                         ('ready', (), ('competing_codes',), (overlay.COMPETING_CHECK,), ()))
        self.assertEqual((alone.rows[0].status, alone.rows[0].questions), (view.status, view.questions))
        self.assertEqual(review._actions(proposal_of(remaining), None, TA.TEXT, view=view),
                         [review.APPROVE, review.REJECT])
        self.assertEqual(case.views({rival.key: 'reject', remaining.key: 'approve'})[remaining.key].blocker, '')
        self.assertEqual((views[rival.key].reason, views[rival.key].decision), (overlay.DETAIL_UNAVAILABLE, 'reject'))
        live = case.recount(out_of_competition=[rival.key]).live[remaining.key]
        self.assertEqual((live.held, live.item), ((), None))

    def test_dq3_with_a_rival_left_the_hold_names_the_rivals_left(self):
        """Three codes for the one dilation, 43213 held by the competition alone, "Cannot confirm" on 43249's
        technique: the reviewer rejects 43249, and 43213's competing hold stays, worded again naming 43233 alone -
        exactly as assess words 43213 beside 43233."""
        case = self.cannot_confirm((('43249', 2), ('43213', 2), ('43233', 2)))
        pair = Case(TA.egd_dilation().build(), ('43213', 2), ('43233', 2))
        by = {row.code: row for row in case.rows}
        self.assertIn('43249', by['43213'].questions[0]['question'])
        view = case.views({by['43249'].key: 'reject'})[by['43213'].key]
        expected = next(row for row in pair.rows if row.code == '43213')
        self.assertEqual((view.status, view.released, view.stale), ('needs_clarification', (), ()))
        self.assertEqual([(q['fact'], q['question'], q['reason']) for q in view.questions],
                         [(q['fact'], q['question'], q['reason']) for q in expected.questions])
        self.assertNotIn('43249', view.questions[0]['question'])

    def test_dq3_where_nothing_can_be_recomputed_the_stored_hold_is_marked_stale(self):
        """Fail-closed with no FactSet: the rejected rival's release cannot be recomputed, so 43213's stored competing
        hold stands, marked stale (overlay._rival_out); with no decision nothing is stale."""
        case = self.cannot_confirm((('43249', 2), ('43213', 2)))
        by = {row.code: row for row in case.rows}
        view = case.views({by['43249'].key: 'reject'}, facts=None)[by['43213'].key]
        self.assertEqual((view.status, view.questions, view.stale),
                         ('needs_clarification', by['43213'].questions, (overlay.COMPETING_CHECK,)))
        self.assertEqual(case.views(facts=None)[by['43213'].key].stale, ())

    def test_d249_where_nothing_can_be_recomputed_an_answer_the_overlay_binds_marks_the_stored_hold_stale(self):
        """The module docstring's UNREADABLE paragraph, made true: with no FactSet a member's "Not documented" the
        overlay binds to 43248's technique item takes 43248 out of the competition, whose release cannot be
        recomputed - 43249's stored competing hold stands, marked stale. (Before, the last pass's answers never
        reached overlay._rival_out, and nothing was marked.) The reverse (no answer): nothing stale. An answer to the
        competing question binds nothing (D283 G1-01 (c)): nothing stale either."""
        case = Case(unknown_dilation().build(), ('43249', 2), ('43248', 2))
        by = {row.code: row for row in case.rows}
        first, rival = by['43249'], by['43248']
        self.assertIn(combination.COMPETING_CAUSE, [found['cause'] for found in first.support['held_facts']])
        answers = [{'code': rival.code, 'family': rival.family, 'fact': 'technique', 'value': 'not_documented'}]
        view = case.views(answers=answers, facts=None)[first.key]
        self.assertEqual((view.status, view.questions, view.stale),
                         ('needs_clarification', first.questions, (overlay.COMPETING_CHECK,)))
        self.assertEqual(case.views(facts=None)[first.key].stale, ())
        competing = [{'code': rival.code, 'family': rival.family, 'fact': 'competing_codes', 'value': 'not_documented'}]
        self.assertEqual(case.views(answers=competing, facts=None)[first.key].stale, ())

    def test_5a_dq2_assess_and_read_time_agree_on_an_overlay_bound_not_documented(self):
        """D270 DQ-2 option (b), with step 5a (assess reads an overlay-bound "Not documented" for the competition
        alone). refute-5a-r2 DQ-2's input: office_and_sigmoidoscopy, 99213, 99214 and 45330, a member's "Not
        documented" to 99214's separate_em question read at assess (the overlay's fact: recorded as read by the review
        overlay). Assess takes 99214 out of the competition, so 99213 is stored with no competing hold and no rival;
        read time, with the answer standing, presents every code as stored - nothing recomputed, released or stale -
        and its engine reproduces the record (the engine's own competition read without 99214: overlay.assessed_out),
        its reviewer's competition read without 99214 too while the answer binds (D249: review_view passes it as
        ``out_of_competition``; with no answer standing, D270's restore would give 99213 its competing hold back - the
        integration's fix of this test, refute-5c-r1 P1 = refute-5a-r1 P-3)."""
        codes = (('99213', 1), ('99214', 1), ('45330', 2))
        plain = TA.by_code(TA.run(TA.office_and_sigmoidoscopy().build(), *codes))
        given = TA.answer(plain['99214'])
        self.assertEqual(given.fact, 'separate_em')
        case = Case(TA.office_and_sigmoidoscopy().build(), *codes, answers=(given,))
        by = {row.code: row for row in case.rows}
        self.assertEqual(overlay.assessed_out(case.completeness, case.rows), frozenset({by['99214'].key}))
        stored = TA.by_code(case.assessment)
        self.assertNotIn(combination.COMPETING_CAUSE, [found.cause for found in stored['99213'].held_facts],
                         'step 5a: assess reads the overlay-bound "Not documented" for the competition (D270 DQ-2)')
        self.assertEqual(stored['99213'].competes, ())
        standing = [{'code': given.code, 'family': given.family, 'fact': given.fact, 'value': given.value}]
        views = case.views(answers=standing)
        for row in case.rows:
            with self.subTest(code=row.code):
                view = views[row.key]
                if row.code == '99214':
                    self.assertEqual((view.reason, view.answer), (overlay.DETAIL_UNAVAILABLE, 'not_documented'))
                    continue
                self.assertEqual((view.status, view.questions), (row.status, row.questions))
                self.assertEqual((view.recomputed, view.released, view.stale, view.added), ((), (), (), ()))
        found = case.recount(out_of_competition=[by['99214'].key])  # the answer standing, as review_view passes it
        self.assertEqual(found.live[by['99213'].key].held, stored['99213'].held_facts)
        self.assertEqual(found.stored_joined, case.assessment.combination)

    def test_dq2_a_decision_that_unbinds_the_answer_restores_the_competition(self):
        """D270 DQ-2's read-time half: two visit codes compete for the one visit; a member's "Not documented" to 99214's
        base question - the overlay's fact - is read at assess, which records the competition released (written here
        as step 5a's assess will write it: ``released_by_assess``, 99214's record kept as its answer found it or
        assessed again). With the answer standing read time reproduces that record and presents it as stored. The
        reviewer reinstates 45380, which makes the date a possible procedure day: 99214's item moves to the same-day
        question, so the base answer binds nothing, 99214 is back in review and read time restores the competition -
        each visit code's competing hold added back as the competition gives it with no answer read, recomputed. The
        reverse decision (none): the release stands, as stored."""
        plain = Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL)
        by = {row.code: row for row in plain.rows}
        self.assertEqual((by['45380'].bucket, by['45380'].reinstatable), ('excluded', True))
        self.assertEqual([q['fact'] for q in by['99214'].questions], ['base_included'])
        held = TA.by_code(plain.assessment)['99214']
        given = TA.answer(held)
        case = Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL, answers=(given,))
        standing = [{'code': given.code, 'family': given.family, 'fact': given.fact, 'value': given.value}]
        for frozen in (False, True):
            with self.subTest(frozen=frozen):
                rows, completeness = released_by_assess(case, held.key, frozen=frozen)
                keyed = {row.code: row for row in rows}
                visit, answered = keyed['99213'], keyed['99214']
                self.assertEqual(overlay.assessed_out(completeness, rows), frozenset({answered.key}))
                self.assertNotIn('competing_codes', [found['fact'] for found in visit.support['held_facts']])

                def views(decisions):
                    return overlay.review_view(rows, decisions, completeness=completeness, facts=case.R,
                                               member=case.member, answers=standing)

                still = views({})  # the reverse decision: none - the release stands, as stored
                self.assertEqual((still[answered.key].reason, still[visit.key].status, still[visit.key].questions),
                                 (overlay.DETAIL_UNAVAILABLE, visit.status, visit.questions))
                self.assertEqual((still[visit.key].recomputed, still[visit.key].added, still[visit.key].stale),
                                 ((), (), ()))
                # the engine's own competition reads without 99214 (the record reproduced), and so does the reviewer's
                # while its answer binds: nothing moved
                found = overlay.recount(rows, case.engine_keys, case.engine_keys, overlay.read_coding(completeness),
                                        case.R, member=case.member, out_of_competition=[answered.key],
                                        assessed=overlay.assessed_out(completeness, rows),
                                        uncounted=overlay.assessed_uncounted(completeness, rows))
                live = found.live[visit.key]
                self.assertNotIn(combination.COMPETING_CAUSE, [h.cause for h in live.held])
                self.assertEqual((live.holds, live.moved), (live.stored_holds, False))
                restored = views({keyed['45380'].key: 'reinstate'})
                for row in (visit, answered):
                    view = restored[row.key]
                    self.assertEqual((view.reason, view.status), ('', 'needs_clarification'))
                    self.assertIn('competing_codes', view.added)
                    self.assertIn(overlay.COMPETING_CHECK, view.recomputed)
                    self.assertEqual([q['fact'] for q in view.questions], ['separate_em'])
                reinstated = overlay.recount(rows, [*case.engine_keys, keyed['45380'].key], case.engine_keys,
                                             overlay.read_coding(completeness), case.R, member=case.member,
                                             assessed=overlay.assessed_out(completeness, rows),
                                             uncounted=overlay.assessed_uncounted(completeness, rows))
                for row in (visit, answered):
                    self.assertEqual([h for h in reinstated.live[row.key].holds
                                      if h.cause == combination.COMPETING_CAUSE],
                                     [h for h in plain.assessment.combination.held[row.key]
                                      if h.cause == combination.COMPETING_CAUSE])

    def test_dq2_the_reviewed_coverage_of_a_reinstatement_reads_the_release_assess_recorded(self):
        """readers.EventReader's reviewed coverage (FINAL-V2 6.5) re-runs read time's engine over the record: given the
        codes assess took out of its competition (overlay.assessed_out), the record of D270 DQ-2's assess half is
        reproduced and the reinstated 45380 is counted - without them the record is not reproduced and the coverage
        cannot be re-run (readers.unreadable would then block the reinstatement, UNREADABLE). The assessment here is an
        object carrying the stored record and its FactSet (EventReader.reading's cache), no database row."""
        from studio.interpretation import readers

        held = TA.by_code(Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL).assessment)['99214']
        case = Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL, answers=(TA.answer(held),))
        rows, completeness = released_by_assess(case, held.key, frozen=False)
        assessment = SimpleNamespace(engine_version=ENGINE_VERSION_V3, completeness=completeness, retrieval=(),
                                     context_id=None, pk='synthetic', _v2_read_facts=case.R)
        found = readers.EventReader()._recounted_coverage(assessment, completeness, rows, [('45380', 'gi.colonoscopy')])
        self.assertIsNotNone(found)
        self.assertEqual(found['reinstated'], ['45380'])
        with self.assertRaises(overlay.RecordMismatch):  # the engine's own competition read with every code in it
            overlay.recount(rows, case.engine_keys, case.engine_keys, overlay.read_coding(completeness), case.R,
                            member=case.member)

    def test_dq2_where_nothing_can_be_recomputed_the_answer_stays_bound_to_the_stored_question(self):
        """Fail-closed with no FactSet: nothing is recomputed, so the answer binds to 99214's stored question and its
        code stays out of review whatever the decisions; the record's release stands, the moved holds marked stale -
        never a code back in review beside a competition read time could not restore."""
        held = TA.by_code(Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL).assessment)['99214']
        given = TA.answer(held)
        case = Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL, answers=(given,))
        rows, completeness = released_by_assess(case, held.key, frozen=False)
        keyed = {row.code: row for row in rows}
        standing = [{'code': given.code, 'family': given.family, 'fact': given.fact, 'value': given.value}]
        views = overlay.review_view(rows, {keyed['45380'].key: 'reinstate'}, completeness=completeness, facts=None,
                                    member=case.member, answers=standing)
        self.assertEqual(views[keyed['99214'].key].reason, overlay.DETAIL_UNAVAILABLE)
        visit = views[keyed['99213'].key]
        self.assertEqual((visit.status, visit.questions, visit.stale),
                         ('needs_clarification', keyed['99213'].questions, (overlay.BASE_CHECK,)))

    def test_assessed_out_reads_the_stored_record_alone(self):
        """overlay.assessed_out: an answer recorded as read by the review overlay, "Not documented", bound by code,
        family and fact to a selected code's stored item - the renderer's record of the item, else its open question;
        never one recorded otherwise, "Cannot confirm", to another fact, or with no record at all (empty)."""
        held = TA.by_code(Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL).assessment)['99214']
        for value, why, fact, expected in (('not_documented', 'read_by_the_review_overlay', 'base_included', True),
                                           ('cannot_confirm', 'read_by_the_review_overlay', 'base_included', False),
                                           ('not_documented', 'asked_differently', 'base_included', False),
                                           ('not_documented', 'read_by_the_review_overlay', 'setting', False)):
            with self.subTest(value=value, why=why, fact=fact):
                case = Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL,
                            answers=(TA.answer(held, value=value),))
                completeness = copy.deepcopy(case.completeness)
                entry = completeness['member_answers']['earlier'][0]
                entry.update(why=why, fact=fact)
                found = overlay.assessed_out(completeness, case.rows)
                self.assertEqual(found, frozenset({held.key}) if expected else frozenset())
                # the open question is read when the record of the item is not there (an older row)
                bare = [replace(row, support={key: item for key, item in row.support.items() if key != 'item'})
                        for row in case.rows]
                self.assertEqual(overlay.assessed_out(completeness, bare), found)
        plain = Case(office_with_denied_biopsy().build(), *VISITS_AND_DENIAL)
        self.assertEqual(overlay.assessed_out(plain.completeness, plain.rows), frozenset())
        self.assertEqual(overlay.assessed_out(None, plain.rows), frozenset())


# DECISIONS D267: refute-5c-r1 P2's four kind states - a kind that is not SUPPORTED names the act as "another act"
KIND_STATES = (
    ('negated snare', EF.neg(Kind.SNARE)),
    ('unresolved, its state negated', EF.fact(Result.UNRESOLVED, Kind.SNARE, ct.FactState.NEGATED,
                                              reasons=(ct.Reason.APPRAISAL_UNCLEAR,))),
    ('doubted between snare and biopsy', EF.doubted(Kind.SNARE, Kind.SNARE, Kind.BIOPSY)),
    ('unresolved snare', EF.unres(Kind.SNARE)),
)


def act_of_kind(kind) -> EF.Doc:
    """refute-5c-r1 P2's input (its probe v85c1_kind_states): a colonoscopy X1 (its examination E1) and one act E2 in X1
    at the sigmoid colon whose kind fact is ``kind``: 45378 alone is held base_included on the act in doubt."""
    doc = EF.colonoscopy(snare=False)
    doc.act(2, kind, places=[EF.sup(Landmark.SIGMOID_COLON)])
    return doc


class D267KindTests(SimpleTestCase):
    """DECISIONS D267 (refute-5c-r1 P2 = 5c Q4; TRIAGE G2-18): D254 rule 2 reaches every kind that is not SUPPORTED -
    negated, doubted, unresolved, contradicted, silent: such an act is Kind.OTHER, "another act", in item_slots and in
    every slot ``_kinds`` fills, as step r4a's act_kind names it - never the value its kind claims (a negated snare is
    no snare removal). A SUPPORTED kind keeps its own label (the reverse)."""

    def test_p2s_four_kind_states_are_named_another_act(self):
        """Each of P2's four states, 45378 alone: base_included, its slots naming Kind.OTHER; the renderer's words are
        its stored question, they say "another act" and never "snare", and read time words the item identically."""
        for name, kind in KIND_STATES:
            with self.subTest(name):
                case = Case(act_of_kind(kind).build(), ('45378', 1))
                p = case.assessment.codes[0]
                self.assertEqual(p.item.message, Q.MessageId.BASE_INCLUDED)
                self.assertEqual(case.assessment.combination.bases[p.key].doubted, (EF.E(2),))
                self.assertEqual(overlay.item_slots(p.item, p.key, case.assessment.combination, case.R),
                                 wording.Slots(code='45378', family=SessionKind.COLONOSCOPY, listed=(Kind.OTHER,),
                                               codes=()))
                _, question, reason = ActNoKindNamesTests.read_as_assessed(self, case, '45378')
                self.assertIn(R3C_LABEL, question.lower())
                self.assertNotIn('snare', (question + reason).lower())
                found = case.recount()
                self.assertEqual(overlay._base_of(found.live[p.key], found.joined, p.key, case.R),
                                 ('included', (wording.kind_words(Kind.OTHER),)))

    def test_a_supported_kind_keeps_its_own_label(self):
        """The reverse: the same act with its kind SUPPORTED is named by its kind - done (BASE_EXPLAINED's act) and with
        its status in doubt (BASE_INCLUDED's), "snare removal"."""
        case = Case(act_of_kind(Kind.SNARE).build(), ('45378', 1))
        p = case.assessment.codes[0]
        slots = overlay.item_slots(p.item, p.key, case.assessment.combination, case.R)
        self.assertEqual((p.item.message, slots.listed), (Q.MessageId.BASE_EXPLAINED, (Kind.SNARE,)))
        doubted = EF.colonoscopy(snare=False)
        doubted.act(2, Kind.SNARE, status=EF.unres(ct.Status.PERFORMED), places=[EF.sup(Landmark.SIGMOID_COLON)])
        case = Case(doubted.build(), ('45378', 1))
        p = case.assessment.codes[0]
        self.assertEqual(p.item.message, Q.MessageId.BASE_INCLUDED)
        self.assertEqual(overlay.item_slots(p.item, p.key, case.assessment.combination, case.R).listed, (Kind.SNARE,))
        _, question, _ = ActNoKindNamesTests.read_as_assessed(self, case, '45378')
        self.assertIn('snare removal', question)

    def test_the_same_day_slots_name_an_act_of_a_kind_not_supported_another_act(self):
        """SEPARATE_EM's possible slot (the same-day acts): 99213 beside a same-day flexible sigmoidoscopy whose act's
        kind is doubted between snare and biopsy is worded naming Kind.OTHER, read as assessed."""
        doc = office_and_unnamed_act(exam=False, kind=EF.doubted(Kind.SNARE, Kind.SNARE, Kind.BIOPSY))
        case = Case(doc.build(), ('99213', 1))
        p = case.assessment.codes[0]
        self.assertEqual(p.item.message, Q.MessageId.SEPARATE_EM)
        slots = overlay.item_slots(p.item, p.key, case.assessment.combination, case.R)
        self.assertEqual((slots.listed, slots.possible, slots.codes), ((), (Kind.OTHER,), ()))
        ActNoKindNamesTests.read_as_assessed(self, case, '99213')


# --- the stored row path: assess and read time read one FactSet -------------------------------------------------------

class W9rCombinationTests(SimpleTestCase):
    """The integration's fixes of the combination in round w9r (step 5a's assess with step 5c's read time): read time's
    engine reproduces every record assess makes with an overlay-read answer (DECISIONS D252, D270 DQ-2), so it never
    refuses the whole assessment (RecordMismatch: nothing recomputed, a reinstatement blocked UNREADABLE)."""

    def competing_case(self, **kw):
        """one_dilation (43249 and 43233 compete for the one dilation, each asking the competition) beside a
        colonoscopy whose broad biopsy denial excludes 45380 (reinstatable); a member's "Not documented" to 43233's
        competing question, read at assess (recorded as read by the review overlay; only a record made before the door
        refused such answers carries one)."""
        def doc():
            d = TA.one_dilation()
            d.session(2, SessionKind.COLONOSCOPY, reached=[EF.sup(ct.Extent.CECUM)])
            d.act(3, Kind.BIOPSY, session=EF.X(2), status=EF.neg(ct.Status.PERFORMED),
                  breadth=EF.sup(ct.Breadth.ALL_OF_KIND), kind_words=EF.Span(300, 330), status_words=EF.Span(330, 360))
            return d
        codes = (('43249', 2), ('43233', 2), ('45380', TA.DENIAL_SPAN))
        given = TA.answer(TA.by_code(TA.run(doc().build(), *codes))['43233'], **kw)
        self.assertEqual(given.fact, 'competing_codes')
        return Case(doc().build(), *codes, answers=(given,)), given

    def test_i1_an_answer_to_the_competing_question_takes_nothing_out_of_the_engines_competition(self):
        """refute-5c-r1 P2 = refute-5a-r1 P-2: engine/assess never reads an answer to the competing question (step 5a's
        question Q1 as built), so overlay.assessed_out never names its code: the engine's own competition keeps 43233,
        the record is reproduced, and a reinstatement's reviewed coverage is re-run, never UNREADABLE. Before the fix:
        assessed_out named 43233 and every read raised RecordMismatch (43249 stale, coverage None). D283 G1-01 (c)
        (restated in AMENDMENT-2's build, step f6): read time binds the answer to nothing either - every view equals
        its stored record, 43233 stays in review - and the reviewer's rejection of 43233 releases 43249 (D270 DQ-3)."""
        from studio.interpretation import readers
        for kw in ({}, {'question': ''}):
            with self.subTest(fingerprint='as asked' if not kw else 'none'):
                case, given = self.competing_case(**kw)
                by = {row.code: row for row in case.rows}
                self.assertEqual(overlay.assessed_out(case.completeness, case.rows), frozenset())
                stored = TA.by_code(case.assessment)
                self.assertIn(combination.COMPETING_CAUSE, [found.cause for found in stored['43249'].held_facts])
                case.recount()  # reproduced: no RecordMismatch
                standing = [{'code': given.code, 'family': given.family, 'fact': given.fact, 'value': given.value,
                             'question': given.question}]
                views = case.views(answers=standing)
                for row in case.rows:
                    self.assertEqual((views[row.key].status, views[row.key].reason, views[row.key].recomputed,
                                      views[row.key].stale), (row.status, '', (), ()), row.code)
                rejected = case.views({by['43233'].key: 'reject'}, answers=standing)[by['43249'].key]
                self.assertEqual((rejected.status, rejected.released), ('ready', ('competing_codes',)))
                assessment = SimpleNamespace(engine_version=ENGINE_VERSION_V3, completeness=case.completeness,
                                             retrieval=(), context_id=None, pk='synthetic', _v2_read_facts=case.R)
                found = readers.EventReader()._recounted_coverage(assessment, case.completeness, case.rows,
                                                                  [('45380', by['45380'].family)])
                self.assertIsNotNone(found)

    def test_i2_an_add_on_taken_out_beside_an_answer_that_excludes_its_primary_is_reproduced(self):
        """refute-5a-r1 P-1 = refute-5c-r1 P6: em_chain (99215, 99417, 99214); a1 "Not documented" to 99215's item as
        asked (the engine reads it: 99215 EXCLUDED, 99417's only primary gone), a2 "Not documented" to 99417's item
        with no fingerprint (the earlier form, bound by the overlay's key).

        Restated by DECISIONS D283, G1-02 (build list B16): a code an overlay-bound "Not documented" takes out of the
        competition is read again when its ADDON row moves, at assess as at read time. Its ADDON row moves (its only
        primary excluded), so 99417 is stored with the ADDON row's item (coding_rule:ADDON), a2 no longer binds it
        (recorded no longer asked), and 99417 is back in the competition with 99214. overlay.assessed_out names
        nothing; the record is reproduced, its ADDON hold CHECKED (a taken code's ADDON hold is no longer exempt:
        overlay._unchecked); read time with a2 standing and no decision equals the record - nothing added, released,
        recomputed or stale - and 99417 is never ready at read time."""
        plain = TA.by_code(TA.run(TA.em_chain().build(), *TA.CHAIN))
        a1 = TA.answer(plain['99215'], answer_id='a1')
        a2 = TA.answer(plain['99417'], question='', answer_id='a2')
        case = Case(TA.em_chain().build(), *TA.CHAIN, answers=(a1, a2))
        by = {row.code: row for row in case.rows}
        stored = TA.by_code(case.assessment)
        self.assertEqual((stored['99417'].item.held.cause, stored['99417'].item.message),
                         (overlay.ADDON_CAUSE, Q.MessageId.ADDON))
        self.assertEqual(stored['99417'].competes, ('99214',))
        self.assertEqual(stored['99214'].competes, ('99417',))
        self.assertEqual([(entry.answer, entry.why) for entry in case.assessment.earlier_answers if entry.answer == 'a2'],
                         [('a2', AS.Unbound.NO_LONGER_ASKED)])
        self.assertEqual(overlay.assessed_out(case.completeness, case.rows), frozenset())
        self.assertEqual(overlay.assessed_uncounted(case.completeness, case.rows), frozenset({by['99215'].key}))
        self.assertEqual(overlay._unchecked(False, True), frozenset({combination.COMPETING_CAUSE}))
        case.recount()  # reproduced: no RecordMismatch, the ADDON hold checked
        standing = [{'code': a.code, 'family': a.family, 'fact': a.fact, 'value': a.value} for a in (a2,)]
        views = case.views(answers=standing)
        for row in case.rows:
            with self.subTest(code=row.code):
                view = views[row.key]
                if overlay.answered_by_engine(row)[0]:
                    self.assertEqual(view.reason, overlay.DETAIL_UNAVAILABLE)
                    continue
                self.assertEqual((view.status, view.added, view.released, view.recomputed, view.stale),
                                 (row.status, (), (), (), ()))
        for decisions in ({}, {by['99214'].key: 'reject'}):
            with self.subTest(decisions=sorted(decisions.values())):
                view = case.views(decisions, answers=standing)[by['99417'].key]
                self.assertNotEqual(view.status, 'ready')
        # a planted record of the taken code without its ADDON hold (the frozen record the round before kept) is not
        # reproduced: the hold is checked now - RecordMismatch, nothing recomputed (fail-closed)
        support = by['99417'].support
        frozen = [found for found in support['held_facts'] if found.get('cause') != overlay.ADDON_CAUSE]
        self.assertLess(len(frozen), len(support['held_facts']))
        planted = [row if row.key != by['99417'].key else replace(row, support={**support, 'held_facts': frozen})
                   for row in case.rows]
        with self.assertRaises(overlay.RecordMismatch):
            overlay.recount(planted, case.engine_keys, case.engine_keys, case.coding, case.R, member=case.member,
                            assessed=overlay.assessed_out(case.completeness, planted),
                            uncounted=overlay.assessed_uncounted(case.completeness, planted))


def c7_scene() -> EF.Doc:
    """refute-consistency C7's scene: an office visit X1 (this encounter; the visit E1, its basis total time), its
    prolonged time E3, and a flexible sigmoidoscopy X2 to the sigmoid colon (E2) on the same day: 99215 and 99417 each
    ask the separately identifiable visit (separate_em), 45330 is READY."""
    doc = TA.office_and_sigmoidoscopy()
    doc.act(3, TA.Kind.EM_PROLONGED, session=TA.X(1))
    return doc


C7_CODES = (('99215', 1), ('99417', 3), ('45330', 2))
PROLONGED_CODES = (('99215', 1), ('99214', 1), ('99417', 2))


def gate6_separate_em():
    """test_gate6's 99417 scene in which 99215 and 99417 each ask the separately identifiable visit: the perturbation
    C3+SEP, state F, of 99417's baseline (an office visit with its prolonged time) - the scene g1's prototype read
    differently before and with the answers (DECISIONS D283 item 2; judge/logs/f10c-g1all-2mod.json)."""
    from tests.v2 import test_gate6 as G

    [requirement] = [found for found in G.RQ.requirements_of('99417') if found.value == 'C3+SEP']
    built, _ = G.perturb('99417', requirement, 'F')
    return built


class D283ReadTimeTests(SimpleTestCase):
    """DECISIONS D283 items 1-3 at read time (G1-02 and G1-03 with C7's and C8's corrections; build list B16):
    overlay.review_view's answer passes call engine/assess.answer_pass, the implementation assess calls, so the stored
    record, read time over it, and read time over the record made BEFORE the answers (the AGAIN not yet run) give one
    view (D252, D270). For each named scene and answer plan:
    - the record made with the answers is reproduced (overlay.recount with the derived sets: no RecordMismatch);
    - read time over it, the answers standing and no decision, equals it - every code an answer does not leave detail
      unavailable keeps its stored status, nothing added, released, recomputed or stale;
    - read time over the record made before the answers, the same answers standing, gives every code the same status
      and reason;
    - the passes end well inside their bound (engine/assess.answer_pass is called fewer times than the loop allows)."""

    def agree(self, R_of, codes, given, member=TA.ENTERED, date=TA.DAY):
        """The four properties above over ``R_of()`` (a FactSet each call) with ``given`` (MemberAnswerInputs), passed
        as review passes the standing answers (each with its fingerprint); returns (the with-record Case, its views)."""
        from unittest import mock

        before = Case(R_of(), *codes, member=member, date=date)
        found = Case(R_of(), *codes, member=member, date=date, answers=given)
        found.recount()  # reproduced: no RecordMismatch
        standing = [{'code': g.code, 'family': g.family, 'fact': g.fact, 'value': g.value, 'question': g.question}
                    for g in given]
        with mock.patch.object(AS, 'answer_pass', wraps=AS.answer_pass) as passes:
            views = found.views(answers=standing)
        self.assertLess(passes.call_count, 2 * len(found.rows) + 5)  # settled before the bound (fail-closed beyond)
        for row in found.rows:
            view = views[row.key]
            if view.reason == overlay.DETAIL_UNAVAILABLE:
                continue
            self.assertEqual((view.status, view.added, view.released, view.recomputed, view.stale),
                             (row.status, (), (), (), ()), row.code)
        earlier = before.views(answers=standing)
        by_code = {row.code: earlier[row.key] for row in before.rows}
        for row in found.rows:
            self.assertEqual((views[row.key].status, views[row.key].reason),
                             (by_code[row.code].status, by_code[row.code].reason), row.code)
        return found, views

    def test_s3_an_overlay_bound_answer_on_the_only_primary_holds_99417_at_both_halves(self):
        """The integration's S3 (G1-03; also test_combination's 99215 base_included scene, AddOnCodes: 99215 beside
        99214 and 99417 on one office visit with its prolonged time): "Not documented" or "Cannot confirm" to 99215's
        base question, bound by the overlay. 99215 is counted for ADDON at neither half: the record holds 99417 by its
        ADDON row (its item the row's own message) and read time equals it; without the answer 99417 is READY."""
        plain = TA.by_code(TA.run(TA.office_prolonged().build(), *PROLONGED_CODES))
        self.assertEqual((plain['99417'].status, plain['99215'].item.held.fact), (TA.Outcome.READY, 'base_included'))
        for value in ('not_documented', 'cannot_confirm'):
            with self.subTest(value=value):
                given = (TA.answer(plain['99215'], value=value),)
                found, views = self.agree(lambda: TA.office_prolonged().build(), PROLONGED_CODES, given)
                addon = TA.by_code(found.assessment)['99417']
                self.assertEqual((addon.status, addon.item.held.cause, addon.item.message),
                                 (TA.Outcome.NEEDS_CLARIFICATION, AS.ADDON_CAUSE, Q.MessageId.ADDON))
                by = {row.code: row for row in found.rows}
                self.assertEqual(overlay.assessed_uncounted(found.completeness, found.rows), frozenset({by['99215'].key}))
                self.assertEqual(views[by['99215'].key].reason, overlay.DETAIL_UNAVAILABLE)

    def test_c7_an_office_visit_its_prolonged_time_and_a_same_day_sigmoidoscopy(self):
        """C7's scene, "Not documented" to both separate_em items, and every pair of values: 99215's answer uncounts it
        for ADDON, so 99417's row moves - read again, its item the ADDON row's, its own answer binding nothing at assess
        (recorded no longer asked) and at read time alike (before the fix read time bound it: 99417 detail unavailable
        while the record held it). 45330 stays READY."""
        plain = TA.by_code(TA.run(c7_scene().build(), *C7_CODES))
        self.assertEqual({code: p.item.held.fact if p.item else None for code, p in plain.items()},
                         {'99215': 'separate_em', '99417': 'separate_em', '45330': None})
        for first in ('not_documented', 'cannot_confirm'):
            for second in ('not_documented', 'cannot_confirm'):
                with self.subTest(values=(first, second)):
                    given = (TA.answer(plain['99215'], value=first, answer_id='a1'),
                             TA.answer(plain['99417'], value=second, answer_id='a2'))
                    found, views = self.agree(lambda: c7_scene().build(), C7_CODES, given)
                    by = {row.code: row for row in found.rows}
                    self.assertEqual((by['99417'].status, views[by['99417'].key].status, views[by['99417'].key].reason),
                                     ('needs_clarification', 'needs_clarification', ''))
                    stored = TA.by_code(found.assessment)['99417']
                    self.assertEqual((stored.item.held.cause, stored.item.message), (AS.ADDON_CAUSE, Q.MessageId.ADDON))
                    self.assertEqual(views[by['99417'].key].questions, by['99417'].questions)  # as stored
                    self.assertEqual([(entry.answer, entry.why) for entry in found.assessment.earlier_answers],
                                     [('a1', AS.Unbound.OVERLAY_READ), ('a2', AS.Unbound.NO_LONGER_ASKED)])
                    self.assertEqual(views[by['45330'].key].status, 'ready')

    def test_gate6s_99417_and_99215_each_answered_on_separate_em(self):
        """test_gate6's scene (gate6_separate_em): 99417 and 99215 each answered on their own separate_em item, every
        pair of values - on g1's prototype read time over the record made with the answers held 99417 and over the
        record made before them read it detail unavailable (4 "read before vs with differs"); now one view."""
        built = gate6_separate_em()
        plain = TA.by_code(TA.run(built.doc.build(), *built.codes, date=built.date, member=built.member))
        self.assertEqual({code: p.item.held.fact for code, p in plain.items()},
                         {'99215': 'separate_em', '99417': 'separate_em'})
        for first in ('not_documented', 'cannot_confirm'):
            for second in ('not_documented', 'cannot_confirm'):
                with self.subTest(values=(first, second)):
                    given = (TA.answer(plain['99417'], value=first, answer_id='a1'),
                             TA.answer(plain['99215'], value=second, answer_id='a2'))
                    found, views = self.agree(lambda: built.doc.build(), built.codes, given, member=built.member,
                                              date=built.date)
                    by = {row.code: row for row in found.rows}
                    self.assertNotEqual(views[by['99417'].key].status, 'ready')

    def test_the_passes_end_and_agree_on_every_answer_combination(self):
        """AnswerPassTests' read-time half: every subset of the held codes' items answered, either value, as asked or
        with no fingerprint, on em_chain, office_prolonged and C7's scene - read time agrees with the record and with
        the record made before the answers, and its passes end inside their bound."""
        import itertools

        scenes = ((TA.em_chain, TA.CHAIN, AS.MemberContext()), (TA.office_prolonged, PROLONGED_CODES, TA.ENTERED),
                  (c7_scene, C7_CODES, TA.ENTERED))
        runs = 0
        for doc, codes, member in scenes:
            plain = TA.by_code(TA.run(doc().build(), *codes, member=member))
            asked = [p for p in plain.values() if p.item is not None]
            for size in range(1, len(asked) + 1):
                for chosen in itertools.combinations(asked, size):
                    for value in ('not_documented', 'cannot_confirm'):
                        for question in (None, ''):
                            given = tuple(TA.answer(p, value=value, question=question, answer_id=f'a{index}')
                                          for index, p in enumerate(chosen))
                            with self.subTest(scene=doc.__name__, codes=[p.code for p in chosen], value=value,
                                              fingerprint=question is None):
                                self.agree(lambda: doc().build(), codes, given, member=member)
                            runs += 1
        self.assertGreater(runs, 40)

    def test_no_add_on_is_the_primary_of_an_add_on(self):
        """overlay.assessed_uncounted's stated limit (this step's NOTES, question Q-UNCOUNTED): only an add-on's item
        moves between the passes (its ADDON row), so the set derived from the last pass's record equals the one assess
        accumulated while no add-on is a primary of an add-on - pinned here, so a catalogue change that makes one fails
        the gate rather than the reproduction."""
        addons = {str(code) for code in AS.ADDON_PRIMARIES}
        self.assertEqual(addons, {'43273', '91013', '99153', '99417'})
        for addon, primaries in AS.ADDON_PRIMARIES.items():
            with self.subTest(addon=addon):
                self.assertTrue(primaries)
                self.assertEqual({str(code) for code in primaries} & addons, set())
                self.assertEqual(AS.primaries(str(addon)) & addons, frozenset())


class StoredRowTests(SimpleTestCase):
    def test_reading_is_effective_over_the_stored_row_and_reproduces_assess(self):
        from tests.v2 import test_facts as TF

        content = TF.colonoscopy()
        view = TF.view(content)
        day = TA.DAY  # the colonoscopy's own date of service, 2026-11-09
        R = overlay.reading(view, day)
        self.assertEqual(R, F.effective(view, day))
        at = TF.unit_span(6)
        proposals = TA.NormalizedResponse('corti', 'synthetic@1', codes=(TA.ProviderCode(
            'selected', 'CPT', '45385', '', (TA.EvidenceSpan(0, at.start, at.end, TF.TEXT[at.start:at.end], True),)),))
        assessment = AS.assess(inventory=view, date_of_service=day, text=TF.TEXT, pages=(), integrity=TA.Integrity(),
                               provider_status='succeeded', proposals=proposals, reference=TA.Lookup(),
                               member=TA.ENTERED, label=label)
        rows, completeness = persist(assessment, R, TF.TEXT)
        views = overlay.review_view(rows, {}, completeness=completeness, facts=R, member=TA.ENTERED)
        for p in rows:
            self.assertEqual((views[p.key].status, views[p.key].questions), (p.status, p.questions))
        found = overlay.recount(rows, [p.key for p in rows], [p.key for p in rows], overlay.read_coding(completeness),
                                R, member=TA.ENTERED)
        self.assertEqual(found.live[rows[0].key].held, assessment.codes[0].held_facts)
        # another effective date re-judges L1 as assess would: never the stored inventory as settled
        later = overlay.reading(view, '2026-12-01')
        self.assertEqual(later, F.effective(view, '2026-12-01'))
        self.assertNotEqual(later, R)

    def test_the_overlay_builds_its_factset_with_effective_never_factset(self):
        """The triage's hand-off 2d:R8 (and 2d:D16): a static pin over overlay.py."""
        tree = ast.parse((APP / 'studio' / 'interpretation' / 'overlay.py').read_text(encoding='utf-8'))
        called = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                  and node.func.value.id == 'facts_'}
        self.assertIn('effective', called)
        self.assertNotIn('factset', called)
        names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertNotIn('factset', names)


# --- fail-closed ------------------------------------------------------------------------------------------------------

class FailClosedTests(SimpleTestCase):
    def test_only_event_coding_at_2_in_its_shape_is_read(self):
        case = Case(TA.two_sessions().build(), *TA.TWO)
        coding = case.completeness['event_coding']
        self.assertIs(overlay.read_coding(case.completeness), coding)
        session = next(iter(coding['sessions']))
        code = next(iter(coding['codes']))
        broken = {
            'no record': {},
            'v1 (event_coding@1)': {'event_coding': {**coding, 'version': 'cpt-studio-events@1'}},
            'a later version': {'event_coding': {**coding, 'version': 'cpt-studio-events@4'}},
            'no lesions': {'event_coding': {**coding, 'lesions': None}},
            'a session keyed by a family': {'event_coding': {**coding, 'sessions': {'gi.colonoscopy': {}}}},
            'a session flag that is no bool': {'event_coding': {**coding, 'sessions': {
                **coding['sessions'], session: {**coding['sessions'][session], 'done': 'yes'}}}},
            'an entry of another shape': {'event_coding': {**coding, 'sessions': {
                **coding['sessions'], session: {**coding['sessions'][session], 'reportable': [{'event': 'E2'}]}}}},
            'a code without its events': {'event_coding': {**coding, 'codes': {code: {'session': None,
                                                                                      'lesions': []}}}},
            'a lesion of v1': {'event_coding': {**coding, 'lesions': {'L1': {'label': 'x', 'distinct_from': []}}}},
        }
        for name, value in broken.items():
            with self.subTest(name):
                with self.assertRaises(overlay.UnreadableCoding):
                    overlay.read_coding(value)
                self.assertIsNone(overlay.coding_of(value))
        # AMENDMENT-2 8.1 [R:replay-R4]: both design v2 families are read - @3, what the engine writes now, and @2, a
        # record stored before it, read as stored
        self.assertEqual(coding['version'], ENGINE_VERSION_V3)
        for version in (ENGINE_VERSION_V2, ENGINE_VERSION_V3):
            with self.subTest(read=version):
                value = {'event_coding': {**coding, 'version': version}}
                self.assertEqual(overlay.read_coding(value)['version'], version)

    def test_an_unreadable_coding_record_or_factset_recomputes_nothing_and_marks_the_moved_holds_stale(self):
        case = Case(EF.colonoscopy(snare=False).build(), ('45378', 1), ('45385', 1))
        base, other = case.rows
        tampered_rows = [replace(base, support={**base.support, 'held_facts': []}), other]
        foreign_rows = [replace(base, support={**base.support, 'event_reading': 'cpt-studio-events@1'}), other]
        for name, kw in (('event_coding@1', {'completeness': {**case.completeness, 'event_coding': {
                              **case.completeness['event_coding'], 'version': 'cpt-studio-events@1'}}}),
                         ('no FactSet', {'facts': None}),
                         ('a record the engine does not reproduce', {'rows': tampered_rows}),
                         ('a record of another engine', {'rows': foreign_rows})):
            with self.subTest(name):
                rows = kw.pop('rows', case.rows)
                views = overlay.review_view(rows, {other.key: 'reject'}, completeness=kw.pop(
                    'completeness', case.completeness), facts=kw.pop('facts', case.R), member=case.member)
                view = views[base.key]
                self.assertEqual((view.status, view.released, view.questions), (base.status, (), base.questions))
                self.assertEqual(view.stale, (overlay.BASE_CHECK,))
        with self.assertRaises(overlay.RecordMismatch):
            overlay.recount(tampered_rows, [base.key], case.engine_keys, case.coding, case.R)
        with self.assertRaises(overlay.UnreadableRecord):
            overlay.recount(foreign_rows, [base.key], case.engine_keys, case.coding, case.R)

    def test_an_unreadable_record_keeps_its_endoscopic_check_as_stored(self):
        """The refutation's problem 10: a record read time cannot read whole (here event_coding@1, as every v1 row) is
        read AS STORED - its endoscopic-family check too, marked stale where the decisions moved what it reads; a record
        read whole has it recomputed over the effective set."""
        from studio.reference.store import PFS

        case = Case(EF.colonoscopy().build(), ('45385', 2), ('45378', 1))
        stored_checks = ({'id': overlay.PRESENCE_CHECK, 'label': 'presence', 'status': 'pass', 'detail': '',
                          'source': ''},
                         {'id': overlay.ENDOSCOPIC_CHECK, 'label': 'Endoscopic family combination', 'status': 'warn',
                          'detail': 'as stored', 'source': ''})
        rows = [replace(p, checks=stored_checks) for p in case.rows]
        snare, base = rows
        retrieval = [{'code': '45385', 'facts': [{'field': 'pfs.endo_base', 'value': '45378', 'source_key': 'pfs-1'}]},
                     {'code': '45378', 'facts': [{'field': 'pfs.endo_base', 'value': '', 'source_key': 'pfs-1'}]}]
        sources = [{'key': 'pfs-1', 'kind': PFS, 'release': 'synthetic', 'title': 'synthetic'}]
        v1 = {**case.completeness, 'event_coding': {**case.completeness['event_coding'],
                                                    'version': 'cpt-studio-events@1'}}
        for name, completeness, recomputed in (('read whole', case.completeness, True), ('event_coding@1', v1, False)):
            with self.subTest(name):
                view = overlay.review_view(rows, {snare.key: 'reject'}, completeness=completeness, retrieval=retrieval,
                                           reference_sources=sources, service_date=TA.DAY, facts=case.R,
                                           member=case.member)[base.key]
                check = next(c for c in view.checks if c['id'] == overlay.ENDOSCOPIC_CHECK)
                self.assertEqual((overlay.ENDOSCOPIC_CHECK in view.recomputed, overlay.ENDOSCOPIC_CHECK in view.stale,
                                  check == stored_checks[1]), (recomputed, not recomputed, not recomputed))

    def test_a_stored_record_is_read_whole_or_not_at_all(self):
        case = Case(TA.two_sessions().build(), *TA.TWO)
        row = case.rows[1]
        self.assertEqual(overlay.read_record(row).held, tuple(case.assessment.codes[1].held_facts))
        held = row.support['held_facts'][0]
        for name, support, evidence in (
                ('another engine', {**row.support, 'event_reading': 'x@1'}, row.evidence),
                ('a held fact missing a field', {**row.support, 'held_facts': [{
                    k: v for k, v in held.items() if k != 'cause'}]}, row.evidence),
                ('a held fact of an unknown kind', {**row.support, 'held_facts': [{**held, 'kind': 'maybe'}]},
                 row.evidence),
                ('runs that are no pairs', {**row.support, 'kept_words': [1, 2]}, row.evidence),
                ('a procedural mark that is no bool', {**row.support, 'procedural': 'yes'}, row.evidence),
                ('a selected code with no held facts', {k: v for k, v in row.support.items() if k != 'held_facts'},
                 row.evidence),
                ('evidence that is no offsets', row.support, ({'start': 'a', 'end': 3},))):
            with self.subTest(name):
                with self.assertRaises(overlay.UnreadableRecord):
                    overlay.read_record(replace(row, support=support, evidence=evidence))

    def test_the_stored_counts_are_read_structured_never_from_the_sentences(self):
        """reviewed_completeness reads the counts a record carries (request R2) as structured values; a record
        without them is read by readers.EventReader through assessment_counts (CountsTests)."""
        case = Case(TA.two_sessions().build(), *TA.TWO)
        stored = recorded(case.completeness, case.assessment, case.R)
        counted = overlay.counted_codes(case.rows, set(), case.R)
        self.assertEqual(overlay.reviewed_completeness(stored, case.R, counted, (), label=label,
                                                       members=tuple(case.recount().members.values())),
                         {**stored, 'reinstated': []})
        for name in overlay.COUNTS:
            with self.subTest(missing=name):
                missing = {key: value for key, value in stored.items() if key != name}
                with self.assertRaises(overlay.UnreadableCounts):
                    overlay.reviewed_completeness(missing, case.R, counted, ())
        with self.assertRaises(overlay.UnreadableCounts):
            overlay.reviewed_completeness({**stored, 'open_questions': '3'}, case.R, counted, ())
        with self.assertRaises(overlay.UnreadableCounts):
            overlay.reviewed_completeness(case.completeness, case.R, counted, ())  # step 5a's record carries none


# --- the text-free words, the copies, the boundary --------------------------------------------------------------------

class WordsTests(SimpleTestCase):
    def test_the_text_free_messages_read_no_text(self):
        """Each TEXT_FREE message builds the same words over any revision text (its builder reads codes, kinds and the
        family only), so read time words it with no text: two different texts, one Slots."""
        texts = ('a' * 400, ''.join(chr(97 + (index * 5) % 26) for index in range(400)))
        span = ct.Span(10, 40)
        rich = dict(code='45378', family=SessionKind.COLONOSCOPY, words=(span,), lesion=(span,),
                    whole_words=(span,), approach_words=(span,), listed=(Kind.SNARE,), possible=(Kind.BIOPSY,),
                    codes=('45385',), both=True)
        for message in overlay.TEXT_FREE:
            with self.subTest(message=message.value):
                slots = wording.Slots(**rich)
                built = [wording.build(wording.Message(message.value), slots, text) for text in texts]
                self.assertEqual(built[0], built[1])
                self.assertEqual(built[0], wording.build(wording.Message(message.value), slots,
                                                         'x' * 400))

    def test_the_copies_are_review_views_modulo_their_declared_seams(self):
        seams = {'_held_blocker': {'checks._join': 'wording.join', 'reconcile.service_label': '_session_label'},
                 'answered_by_engine': {'engine.answered_away': 'questions.answered_away',
                                        'engine.ANSWERED_SUPPORT': 'questions.ANSWERED_SUPPORT'},
                 '_example_passage': {'checks.CLAIMS_EXAMPLE_PASSAGE': 'CLAIMS_EXAMPLE_PASSAGE',
                                      'checks.CLAIMS_EXAMPLE_TOPIC': 'CLAIMS_EXAMPLE_TOPIC'}}
        for name in ('stored_from', '_decided', 'proposal_answers', 'answered_by_engine', 'counts', 'decidable',
                     '_find', '_question', '_reinstatement_clear', '_sources', '_passage_sources', '_example_passage',
                     '_held_blocker'):
            with self.subTest(name=name):
                legacy = _rewrite(seams.get(name, {})).visit(_tree(getattr(review_view, name)))
                self.assertEqual(ast.dump(legacy), ast.dump(_tree(getattr(overlay, name))))
        for name in ('APPROVE', 'REJECT', 'REINSTATE', 'REVOKE', 'SELECTED', 'EXCLUDED', 'READY',
                     'NEEDS_CLARIFICATION', 'STATUS_EXCLUDED', 'BASE_CHECK', 'BASE_FACT', 'ENDOSCOPIC_CHECK',
                     'REINSTATEMENT_CHECK', 'PRESENCE_CHECK', 'DATE_CHECK', 'SAME_DAY_EM_GATE', 'SEPARATE_EM_FACT',
                     'DETAIL_UNAVAILABLE', 'ANSWER_WORDS', 'MODIFIER_REVIEW', 'DATE_WAIT', 'DOCUMENTATION_FACT',
                     'DOCUMENTATION_QUESTION'):
            with self.subTest(constant=name):
                self.assertEqual(getattr(overlay, name), getattr(review_view, name))
        self.assertEqual(overlay.DISTINCT_LESION_NOT_CHECKED, checks.DISTINCT_LESION_NOT_CHECKED)
        self.assertEqual((overlay.CLAIMS_EXAMPLE_CODES, overlay.CLAIMS_EXAMPLE_PASSAGE, overlay.CLAIMS_EXAMPLE_TOPIC),
                         (checks.CLAIMS_EXAMPLE_CODES, checks.CLAIMS_EXAMPLE_PASSAGE, checks.CLAIMS_EXAMPLE_TOPIC))
        self.assertEqual(overlay.UNREADABLE_BLOCKER, review.UNREADABLE_EVENTS_BLOCKER)
        self.assertEqual(overlay._USER, dates.USER)
        # AMENDMENT-2 8.1: the engine's own coding is written at @3, and both design v2 families are read
        self.assertEqual((overlay.CODING_VERSION, overlay.READ_CODINGS), (ENGINE_VERSION_V3,
                                                                         (ENGINE_VERSION_V2, ENGINE_VERSION_V3)))
        self.assertEqual((overlay.COMPETING_CHECK, overlay.COMPETING_FACT), ('proposals.competing', 'competing_codes'))
        # _pfs_rows reads the field's prefix by a slice: the same rows as review_view's
        retrieval = [{'code': '45385', 'facts': [{'field': 'pfs.global_days', 'value': '000', 'source_key': 's'},
                                                 {'field': 'mue.units', 'value': 1}]}, {'code': '45378', 'facts': []},
                     {'code': '', 'facts': []}, 'junk']
        self.assertEqual(overlay._pfs_rows(retrieval), review_view._pfs_rows(retrieval))

    def test_the_member_context_is_the_member_values_only(self):
        facts = {'setting': {'value': 'office', 'origin': 'user'},
                 'patient_status': {'value': 'new', 'origin': 'document'},
                 'billing_context': {'value': None, 'origin': 'missing'}}
        self.assertEqual(overlay.member_context(facts), AS.MemberContext(setting='office'))
        self.assertEqual(overlay.member_context(None), AS.MemberContext())


class BoundaryTests(SimpleTestCase):
    def test_overlay_and_readers_keep_words_never_decide(self):
        """FINAL-V2 5.7 measure 4's WordsNeverDecide rules as tests/v2/test_types.measure_4 states them (imports, no
        str method on a non-literal receiver, no membership test against a string) over the two read-time modules
        (step 6a's guard scans them too)."""
        for name in ('overlay', 'readers'):
            with self.subTest(module=name):
                source = (APP / 'studio' / 'interpretation' / f'{name}.py').read_text(encoding='utf-8')
                found = [problem for problem in measure_4(source, engine=True)
                         if 'module-level word list' not in problem]
                self.assertEqual(found, [])
                tree = ast.parse(source)
                read = {(node.value.attr if isinstance(node.value, ast.Attribute) else getattr(node.value, 'id', ''),
                         node.attr) for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
                self.assertFalse({('revision', 'text'), ('reading', 'text')} & read)

    def test_the_overlay_imports_no_retired_module(self):
        source = (APP / 'studio' / 'interpretation' / 'overlay.py').read_text(encoding='utf-8')
        imported = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        names = set()
        for node in imported:
            if isinstance(node, ast.ImportFrom):
                names |= {f'{node.module}.{alias.name}' for alias in node.names} | {node.module or ''}
            else:
                names |= {alias.name for alias in node.names}
        retired = {f'studio.interpretation.{name}' for name in RETIRED}
        self.assertFalse(names & retired, names & retired)


def _tree(fn):
    return ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0]


class _rewrite(ast.NodeTransformer):  # noqa: N801
    def __init__(self, seams):
        self.seams = {tuple(old.split('.')): new for old, new in seams.items()}

    def visit_Attribute(self, node):
        parts, value = [], node
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            dotted = tuple([value.id] + list(reversed(parts)))
            if dotted in self.seams:
                return ast.parse(self.seams[dotted], mode='eval').body
        return self.generic_visit(node)
