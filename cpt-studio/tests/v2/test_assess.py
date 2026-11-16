"""The assessment of one revision from its settled inventory (docs/gemini-migration/FINAL-V2.md 4.1, 4.3, 4.4, 4.8,
4.9, 4.12, 9.3 and 9.4; step 5a of its 8.1), TEXT-ONLY and SYNTHETIC: engine/assess.py over hand-built settled FactSets
(tests/v2/evaluate_fixtures.py) and over a stored v2 row written by store.row_v2 and read back (tests/v2/test_facts.py's
synthetic colonoscopy), with the caller's own R1 - studio.validation.checks.code_scope and exact_evidence and
studio.participants.peer.code_shaped - and the legacy input records jobs.py already holds (studio.types'
NormalizedResponse, ProviderCode, EvidenceSpan, ParticipantInput ...), which the engine's protocols read as they stand.

What is proved here (the step's done-when, then 9.3's assess row):
- agreement adds proposers and nothing else - the pinned test_agreement_adds_proposers_and_nothing_else, with its v2
  fixture (a READY code and a held one): two participants quoting the same codes change ``proposed_by`` and no other
  field, the fingerprint and the item's fingerprint included; and the same with the participants quoting every code
  from OTHER exact units than the provider's, an excluded code among them (the refutation's P6(a)); P-ADMIT's
  admission, peer-only, unlocated and inexact codes, disagreements, a malformed participant;
- READY never without exact evidence: a code whose quote is not the document's own text, or out of scope, is excluded
  by R1, not reinstatable, and never read by the per-code rule; every READY code of every fixture rests on spans R1
  itself confirmed; the text is read by R1 alone (every character replaced, the outcome byte-identical);
- P-INDEP on the assess fixtures (9.4): perturbing any fact outside a code's requirement closure
  (engine/requirements.dependencies) leaves its status, its item and its held facts unchanged - at the attribute level
  (every attribute no role of the code reads, on every object) and at the object level (every fact but the kind and the
  session of an act no role of the code reads, in a session of another family); 4.9's own example;
- the R6 rows, R7, the considerations, the class rule's wiring (the refutation's P6(b)), ADDON (an add-on held without
  its primary counted - R1, 4.6 or a member's answer leaving it out - and met beside it; the refutation's P1), the
  combination's holds, member answers (bound by the item's fingerprint; each service answer closing the question it
  was given to - P2; a date-of-service answer applied by no one - P8; the applied record's question and asked
  fingerprints - P9), the second review, the records (SERVICES_STUB, INVENTORY_PROBLEMS, the D22
  fields, completeness, event_coding@2), fingerprints over facts (P-DET; the billing context of an E/M or a PC/TC code -
  P3), the 2d hand-off's static pin (facts.effective, never factset), 5.7 measure 4 and ``mypy --strict`` over
  engine/assess.py and engine/measure.py;
- DECISIONS D244's two repairs (D244Tests, over the FactSets RF-HO9 and S4 settle to): R-K8 - a contradicted reach (a
  K8 polarity pair, or pass 1's contradicted claim) asks RANK 1 conflict:examination in the R6:extent and COLFULL rows,
  before anything else those rows read, quoting both sides, worded; a contradicted completion the unmet row rests on
  likewise; a reach that is only unresolved or negated still asks the extent - and Q-S4 option (a) - a completion pass 2
  did not establish keeps the 52|53 consideration on a READY code, whatever value it claims, and never holds or meets
  a requirement; a silent slot (strictly: engine/classes.py's reading, D217) gives none;
- DECISIONS D260 (CompetitionAnswerTests, ReadTimeAgreementTests; repair round w8r's step 5a): a rival a member answered
  "Not documented" leaves the competition at assess, as read time reads it (D249) - a code with no rival left loses its
  competing_codes hold (READY when nothing else holds it, as assessed alone), one with a rival left keeps it naming only
  the rivals left, a competition over a synthetic act (D231 row 5) stays - and "Cannot confirm" leaves the competition
  as it stands; the answers bind in passes and an answer that binds stands; the seam check's scene 677 is pinned:
  43248's status, item and question are equal at assess and at read time (the read-time engine's half needs read time
  to read the competition through engine/assess.compete_without: the step's NOTES, request R1);
- refute-5a-r1 P-1 and P-3 (DecisionCarryTests, AnswerPassTests; the fix round of step 5a): a code the answers' passes
  assess again keeps the fingerprint it has without the answers while its status is unchanged, so a reviewer's
  decision on it carries - carried as review carries it over the rows the renderer persists - and one whose status
  moves takes the fingerprint of what it now is (the decision cleared naming the status); a chain of two passes the
  catalogue's codes reach (em_chain) releases the last rival;
- DECISIONS D270, DQ-2 (OverlayAnswerTests; repair round w9r's step 5a): an overlay-bound "Not documented" - an answer
  the engine does not apply, bound to the code's item by key as read time binds it (a key-bound fact by its key whatever
  fingerprint it carries, an answer with no fingerprint by its key alone; never an answer to the competing question,
  which offers none) - is read at assess for the competition alone, as D260 reads an engine-bound one: refute-5a-r2
  DQ-2's input (99213, 99214 and 45330; "Not documented" to 99214's separate_em question) releases 99213's competing
  hold naming 99214 at assess as at read time, 99213 keeping separate_em, and its control (no answer, or "Cannot
  confirm") keeps the hold; what assess takes out of the competition is what read time takes out over the record made
  before the answer, the rivals' records are read time's live ones, and the answered code keeps the record its answer
  found.
Every document and fact here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import itertools
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation import (ENGINE_VERSION_V2, ENGINE_VERSION_V3, INTERPRETATION_PAIR_V3, INVENTORY_VERSION_V3,
                                   REQUIREMENTS_VERSION)
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import catalogue as CAT
from studio.interpretation.engine import classes as CLS
from studio.interpretation.engine import combination as CO
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine import requirements as RQ
from studio.interpretation.engine import requirements_table as TABLE
from studio.interpretation.engine.types import Fact, FactSet, IdFamily, IsoDate, ItemKind, Outcome, Span
from studio.participants.peer import code_shaped
from studio.types import (EvidenceSpan, LocatedQuote, NormalizedResponse, ParticipantCode, ParticipantInput,
                          ParticipantNotCoded, ParticipantReading, PeerReview, ProviderCode)
from studio.validation import checks
from studio.validation.questions import MemberAnswerInput
from tests.v2 import evaluate_fixtures as EF
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
ENGINE = APP / 'studio' / 'interpretation' / 'engine'
A, Res, State, Reason = ct.Attribute, ct.Result, ct.FactState, ct.Reason
Kind, SessionKind, Landmark, Extent, Device = ct.Kind, ct.SessionKind, ct.Landmark, ct.Extent, ct.Device
sup, X, E, L, Y = EF.sup, EF.X, EF.E, EF.L, EF.Y
DAY = datetime.date(2026, 11, 9)
# A synthetic revision: no words at all, only characters at offsets (the FactSets anchor event n on 100n .. 100n + 60).
TEXT = ''.join(chr(97 + (index * 7) % 26) for index in range(4000))


# --- the caller's inputs ----------------------------------------------------------------------------------------------


class Integrity:
    """The caller's R1, as step 5b hands it in: the allowlisted checks and the participants' code rule, unchanged.
    ``kept`` records every span R1 confirmed, by its offsets (the proof that READY rests on them)."""
    word_runs = None

    def __init__(self) -> None:
        self.kept: set = set()

    def code_scope(self, code):
        return checks.code_scope(code)

    def exact_evidence(self, spans, text, pages):
        kept, dropped = checks.exact_evidence(spans, text, pages)
        self.kept |= {(span.start, span.end) for span in kept}
        return kept, dropped

    def code_shaped(self, value):
        return code_shaped(value)


class Lookup:
    """The prefetched reference lookup: no row for any code (R9: records only)."""

    def lookup(self, code, service_date):
        return SimpleNamespace(pfs=None, mue=None)


def span(n: int, text: str = TEXT) -> EvidenceSpan:
    """Event n's own anchor unit, quoted exactly from ``text``."""
    return EvidenceSpan(0, 100 * n, 100 * n + 60, text[100 * n:100 * n + 60], True)


def wrong(n: int) -> EvidenceSpan:
    """Event n's offsets with words that are not the document's there."""
    return EvidenceSpan(0, 100 * n, 100 * n + 60, 'not the document text at these offsets, by construction' + '.' * 4,
                        True)


def corti(*codes, provider: str = 'corti', text: str = TEXT, roles: tuple = ()) -> NormalizedResponse:
    """The proposal provider's answer: (code, event number or an EvidenceSpan) selected; ``roles``: (code, role)
    listed."""
    items = [ProviderCode('selected', 'CPT', code, '',
                          (where if isinstance(where, EvidenceSpan) else span(where, text),)) for code, where in codes]
    items += [ProviderCode(role, 'CPT', code, '', (span(1, text),)) for code, role in roles]
    return NormalizedResponse(provider, 'synthetic@1', codes=tuple(items))


def quote(n: int, text: str = TEXT) -> LocatedQuote:
    return LocatedQuote('a synthetic quote', (span(n, text),))


def reading(provider: str, codes=(), not_coded=()) -> ParticipantReading:
    return ParticipantReading(provider=provider, adapter_version=f'{provider}@test',
                              reading_version='harness-reading@2', requested_model='model', returned_model='model',
                              codes=tuple(ParticipantCode(code=code, evidence=(quote(n),) if n else ())
                                          for code, n in codes),
                              not_coded=tuple(not_coded))


def participant(provider: str, codes=(), not_coded=(), peer_codes=(), positions=()) -> ParticipantInput:
    first = reading(provider, codes, not_coded)
    if not peer_codes and not positions:
        return ParticipantInput(provider, 'read', first)
    peer = PeerReview(provider=provider, adapter_version=f'{provider}@test', review_version='peer@1',
                      requested_model='model', returned_model='model',
                      additional_codes=tuple(ParticipantCode(code=code, evidence=(quote(n),))
                                             for code, n in peer_codes),
                      positions=tuple(positions))
    return ParticipantInput(provider, 'read', first, peer_state='read', peer=peer)


def dated(R: FactSet, value: datetime.date | None = DAY) -> FactSet:
    """``R`` with its encounter's date of service supported (or silent for None)."""
    fact = sup(IsoDate(value, ct.Precision.DAY)) if value is not None else F.SILENT
    return replace(R, encounter={A.DATE_OF_SERVICE: (fact,)})


ENTERED = AS.MemberContext(setting='office', patient_status='established')


def run(R: FactSet, *codes, date: datetime.date | None = DAY, member: AS.MemberContext = ENTERED, integrity=None,
        text: str = TEXT, participants=(), answers=(), second=None, provider=None, status='succeeded',
        roles: tuple = (), reference=None) -> AS.Assessment:
    """assess_facts over ``R`` (its date of service set from ``date``), the proposal provider selecting ``codes``."""
    return AS.assess_facts(dated(R, date), date_of_service=date, text=text, pages=(),
                           integrity=integrity if integrity is not None else Integrity(), provider_status=status,
                           proposals=provider if provider is not None else corti(*codes, text=text, roles=roles),
                           reference=reference if reference is not None else Lookup(), member=member,
                           label=lambda session: str(session.id), participants=participants, second=second,
                           answers=answers)


def by_code(assessment: AS.Assessment) -> dict:
    return {found.code: found for found in assessment.codes}


def facts_of(found: AS.Assessed) -> list:
    return [(held.fact, held.cause) for held in found.held_facts]


def decision(found: AS.Assessed) -> tuple:
    """A proposal's decision, whatever its key and proposers: its status, item, question, held facts, rivals,
    considerations, trace and fingerprint."""
    return (found.status, found.item, found.question, found.held_facts, found.competes, found.considerations,
            found.trace, found.fingerprint)


def outcome_of(found: AS.Assessed) -> tuple:
    """``decision`` less the fingerprint: what a proposal decides and shows. A code the answers' passes assess again
    keeps the fingerprint it has without the answers while its status is unchanged, so its outcome can equal another
    proposal's while its fingerprint does not."""
    return decision(found)[:-1]


# --- fixtures (settled FactSets; EF's Doc) ----------------------------------------------------------------------------


def two_sessions() -> EF.Doc:
    """A colonoscopy X1 to the cecum (E1) with the cold snare removal E2 of L1 in the sigmoid colon and a forceps
    biopsy E3 of L2 in the transverse colon; an EGD X2 to the second portion of the duodenum (E4) with an antral biopsy
    E5. Codes 45385 and 43239 are READY; 45378 and 43235 are held beside their sessions' acts."""
    doc = EF.colonoscopy()
    doc.lesion(2, lesion_places=[sup(Landmark.TRANSVERSE_COLON)])
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.TRANSVERSE_COLON)], lesion=sup(L(2)))
    doc.session(2, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(4, session=X(2))
    doc.act(5, Kind.BIOPSY, session=X(2), places=[sup(Landmark.GASTRIC_ANTRUM)])
    return doc


TWO = (('45385', 2), ('45380', 3), ('45378', 1), ('43239', 5), ('43235', 4))


def enriched() -> EF.Doc:
    """two_sessions with facts on attributes most codes' rules never read (so P-INDEP has something to perturb): a
    yield, an access outcome, a route, a cause, an other_class and a structure on the acts, a tract, an approach, a
    device reach and stations on the sessions, a lesion's multiplicity and same_as."""
    doc = two_sessions()
    extra = {A.YIELD: (sup(ct.Material.DEBRIS),), A.ACCESS_OUTCOME: (sup(ct.AccessOutcome.ACHIEVED),),
             A.TECHNIQUE_ROUTE: (sup(ct.Route.INTRALUMINAL),), A.CAUSE: (sup(ct.Cause.SPONTANEOUS),),
             A.OTHER_CLASS: (sup(ct.OtherClass.PROCEDURE),), A.TARGET_STRUCTURE: (sup(ct.Structure.WALL),)}
    for event in (E(2), E(3), E(5)):
        doc.events[event] = {**doc.events[event], **extra}
    doc.sessions[X(1)] = {**doc.sessions[X(1)], A.TRACT: (sup(ct.Tract.LOWER),),
                          A.APPROACH: (sup(ct.Approach.TRANSANAL),), A.DEVICE_REACHED: (sup(Extent.CECUM),)}
    doc.sessions[X(2)] = {**doc.sessions[X(2)], A.TRACT: (sup(ct.Tract.UPPER),), A.APPROACH: (sup(ct.Approach.ORAL),),
                          A.STATIONS: (sup(ct.Station.STOMACH),)}
    doc.lesions[L(2)] = {**doc.lesions[L(2)], A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}
    return doc


def egd_dilation() -> EF.Doc:
    """4.9's example: an EGD with a dilation E2 of the distal esophagus whose device is not stated and an antral biopsy
    E3. "A dilation whose device is unknown holds 43249 and nothing else; 43239's biopsy stands.\""""
    doc = EF.egd()
    doc.act(2, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)])
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.GASTRIC_ANTRUM)])
    return doc


def denial_beside_a_snare() -> EF.Doc:
    """EF.colonoscopy (45385 READY on the cold snare E2; 45378 held beside it) with E3, a broad denial of biopsies on
    the date of service whose kind and status words are the whole of its unit (300 .. 360): 45380, citing that unit
    exactly (DENIAL_SPAN), is EXCLUDED by citation (4.6, C-10)."""
    doc = EF.colonoscopy()
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.ALL_OF_KIND),
            kind_words=Span(300, 330), status_words=Span(330, 360))
    return doc


DENIAL_SPAN = EvidenceSpan(0, 300, 360, TEXT[300:360], True)


def office_and_sigmoidoscopy() -> EF.Doc:
    """An office visit X1 (this encounter; the visit E1, its basis total time) and a flexible sigmoidoscopy X2 to the
    sigmoid colon (E2) on the same day: 99213 is held for a separately identifiable visit (C-3), 45330 is READY."""
    doc = EF.Doc()
    doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.TOTAL_TIME))
    doc.session(2, SessionKind.FLEX_SIG, reached=[sup(Extent.SIGMOID_COLON)])
    doc.exam(2, session=X(2))
    return doc


# --- the pinned test: agreement adds proposers and nothing else (4.12; I3) --------------------------------------------


class AgreementTests(SimpleTestCase):
    def test_agreement_adds_proposers_and_nothing_else(self):
        """The v2 fixture: 45385 READY and 45378 held base_included; Astra and Fable each quote both exactly in their
        first readings. Every field but proposed_by is equal - status, held facts, item, fingerprints, evidence, units,
        bucket, trace, considerations - and so is everything the encounter records but the participants' own record."""
        R = EF.colonoscopy().build()
        alone = run(R, ('45385', 2), ('45378', 1))
        agreed = run(R, ('45385', 2), ('45378', 1), participants=(
            participant('astra', [('45385', 2), ('45378', 1)]), participant('fable', [('45385', 2), ('45378', 1)])))
        self.assertEqual({p.code: p.status for p in alone.codes},
                         {'45385': Outcome.READY, '45378': Outcome.NEEDS_CLARIFICATION})
        for before, after in zip(alone.codes, agreed.codes):
            with self.subTest(code=before.code):
                self.assertEqual(before.proposed_by, ('corti',))
                self.assertEqual(after.proposed_by, ('corti', 'astra', 'fable'))
                for field in dataclasses.fields(AS.Assessed):
                    if field.name != 'proposed_by':
                        self.assertEqual(getattr(after, field.name), getattr(before, field.name), field.name)
        for name in ('service_questions', 'coverage', 'event_coding', 'completeness', 'services', 'combination',
                     'alternatives', 'answers', 'earlier_answers', 'second_review'):
            self.assertEqual(getattr(agreed, name), getattr(alone, name), name)
        self.assertEqual([(p.provider, p.state, p.proposed) for p in agreed.participants],
                         [('astra', AS.ParticipantState.READ, 2), ('fable', AS.ParticipantState.READ, 2)])

    def test_agreement_quoted_from_other_units_adds_proposers_and_nothing_else(self):
        """The pinned test's participants quote the provider's own spans, so it cannot see agreement changing the kept
        evidence (the refutation's P6(a), mutant MA). Here each participant quotes every code exactly from ANOTHER unit
        than the provider's: 45385 READY, 45380 EXCLUDED by its cited denial (a merge of the participants' spans into
        its evidence would make the cover partial, a statement_scope hold), 45378 held. Every field but proposed_by is
        equal, and so is everything the encounter records but the participants' own record."""
        R = denial_beside_a_snare().build()
        codes = (('45385', 2), ('45380', DENIAL_SPAN), ('45378', 1))
        alone = run(R, *codes)
        agreed = run(R, *codes, participants=(
            participant('astra', [('45385', 1), ('45380', 1), ('45378', 2)]),
            participant('fable', [('45385', 3), ('45380', 2), ('45378', 3)])))
        self.assertEqual({p.code: p.status for p in alone.codes},
                         {'45385': Outcome.READY, '45380': Outcome.EXCLUDED, '45378': Outcome.NEEDS_CLARIFICATION})
        self.assertEqual(by_code(alone)['45380'].evaluation.exclusion.cover.value, 'citation')
        for before, after in zip(alone.codes, agreed.codes):
            with self.subTest(code=before.code):
                self.assertEqual((before.proposed_by, after.proposed_by), (('corti',), ('corti', 'astra', 'fable')))
                for field in dataclasses.fields(AS.Assessed):
                    if field.name != 'proposed_by':
                        self.assertEqual(getattr(after, field.name), getattr(before, field.name), field.name)
        for name in ('service_questions', 'coverage', 'event_coding', 'completeness', 'services', 'combination',
                     'alternatives', 'answers', 'earlier_answers', 'second_review'):
            self.assertEqual(getattr(agreed, name), getattr(alone, name), name)

    def test_a_peer_review_quote_adds_its_participant_too(self):
        R = EF.colonoscopy().build()
        alone = by_code(run(R, ('45385', 2)))['45385']
        peer = by_code(run(R, ('45385', 2), participants=(participant('astra', peer_codes=[('45385', 2)]),)))['45385']
        self.assertEqual(peer.proposed_by, ('corti', 'astra'))
        self.assertEqual(replace(peer, proposed_by=alone.proposed_by), alone)

    def test_a_first_reading_code_no_proposal_carries_is_admitted_and_read_by_the_per_code_rule(self):
        R = two_sessions().build()
        found = run(R, ('45385', 2), participants=(participant('astra', [('43239', 5)]),))
        admitted = by_code(found)['43239']
        self.assertEqual((admitted.origin, admitted.proposed_by, admitted.status),
                         (AS.Origin.PARTICIPANT, ('astra',), Outcome.READY))
        self.assertFalse(admitted.primary_listed)
        self.assertEqual(admitted.evidence.kept, (Span(500, 560),))
        # the per-code rule decided it: the same record as when the proposal provider selects it
        selected = by_code(run(R, ('45385', 2), ('43239', 5)))['43239']
        self.assertEqual((admitted.status, admitted.held_facts, admitted.item, admitted.fingerprint),
                         (selected.status, selected.held_facts, selected.item, selected.fingerprint))

    def test_peer_only_unlocated_and_inexact_codes_stay_alternatives(self):
        R = two_sessions().build()
        unlocated = ParticipantInput('astra', 'read', reading('astra', [('45380', 0)]))
        inexact = ParticipantInput('fable', 'read', ParticipantReading(
            provider='fable', adapter_version='fable@test', reading_version='harness-reading@2',
            requested_model='model', returned_model='model',
            codes=(ParticipantCode(code='43235', evidence=(LocatedQuote('a quote', (wrong(4),)),)),)))
        peer = participant('astra', peer_codes=[('43239', 5)])
        for given, code, why in ((unlocated, '45380', AS.NotAdded.UNLOCATED),
                                 (inexact, '43235', AS.NotAdded.NO_EVIDENCE), (peer, '43239', AS.NotAdded.PEER_ONLY)):
            with self.subTest(code=code):
                found = run(R, ('45385', 2), participants=(given,))
                self.assertNotIn(code, by_code(found))
                alternative, = [item for item in found.alternatives if item.code == code]
                self.assertEqual((alternative.why, alternative.origin, alternative.key),
                                 (why, AS.Origin.PARTICIPANT, 'altp:0'))

    def test_a_disagreement_is_recorded_and_changes_nothing(self):
        R = EF.colonoscopy().build()
        alone = by_code(run(R, ('45385', 2)))['45385']
        dissent = participant('astra', not_coded=[ParticipantNotCoded(code='45385',
                                                                      reason='not_performed_at_this_encounter',
                                                                      evidence=(quote(2),))])
        found = by_code(run(R, ('45385', 2), participants=(dissent,)))['45385']
        self.assertEqual(found.disagreements, (AS.Disagreement('astra', AS.Phase.INDEPENDENT, Span(200, 260)),))
        self.assertEqual((found.status, found.fingerprint, found.proposed_by), (Outcome.READY, alone.fingerprint,
                                                                                ('corti',)))

    def test_a_malformed_or_repeated_participant_is_read_as_refused(self):
        R = EF.colonoscopy().build()
        broken = ParticipantInput('astra', 'read', None)
        twice = (participant('fable', [('45380', 3)]), participant('fable', [('45380', 3)]))
        found = run(R, ('45385', 2), participants=(broken, *twice))
        self.assertEqual([(p.provider, p.state) for p in found.participants],
                         [('astra', AS.ParticipantState.REFUSED), ('fable', AS.ParticipantState.REFUSED)])
        self.assertEqual(by_code(found)['45385'].proposed_by, ('corti',))
        with self.assertRaises(ValueError):
            run(R, ('45385', 2), participants=(ParticipantInput('', 'read', None),))


# --- R1: READY never without exact evidence (4.1, 5.6) ----------------------------------------------------------------


def corpus():
    """Every fixture assessment of this module's R1 proof: (name, the assessment, its Integrity)."""
    out = []
    for name, doc, codes in (('two sessions', two_sessions(), TWO), ('enriched', enriched(), TWO),
                             ('egd dilation', egd_dilation(), (('43249', 2), ('43239', 3), ('43235', 1))),
                             ('office', office_and_sigmoidoscopy(), (('99213', 1), ('45330', 2)))):
        integrity = Integrity()
        out.append((name, run(doc.build(), *codes, integrity=integrity), integrity))
    return out


class ExactEvidenceTests(SimpleTestCase):
    def test_a_quote_that_is_not_the_documents_text_never_reaches_the_rule(self):
        R = EF.colonoscopy().build()
        good = by_code(run(R, ('45385', 2)))['45385']
        bad = by_code(run(R, ('45385', wrong(2))))['45385']
        self.assertEqual(good.status, Outcome.READY)
        self.assertEqual((bad.status, bad.bucket, bad.reinstatable, bad.evaluation, bad.held_facts, bad.item),
                         (Outcome.EXCLUDED, AS.Bucket.EXCLUDED, False, None, (), None))
        self.assertEqual((bad.evidence.kept, bad.evidence.exact, bad.key), ((), False, 'exc:0'))
        self.assertEqual(bad.evidence.dropped, ('does not match the document text at its offsets',))
        # the same text at other offsets is not the document's own text there either
        moved = EvidenceSpan(0, 230, 290, TEXT[200:260], True)
        self.assertEqual(by_code(run(R, ('45385', moved)))['45385'].status, Outcome.EXCLUDED)

    def test_a_code_out_of_scope_is_excluded_by_r1(self):
        R = EF.colonoscopy().build()
        for code in ('G0105', '0001U', '4525F', 'colon'):
            with self.subTest(code=code):
                found = by_code(run(R, (code, 2)))[code]
                self.assertEqual((found.status, found.reinstatable, found.evaluation), (Outcome.EXCLUDED, False, None))
                self.assertTrue(found.evidence.scope_reason)

    def test_every_ready_code_rests_on_spans_r1_confirmed(self):
        ready = 0
        for name, assessment, integrity in corpus():
            for found in assessment.codes:
                if found.status is not Outcome.READY:
                    continue
                ready += 1
                with self.subTest(fixture=name, code=found.code):
                    self.assertTrue(found.evidence.exact)
                    self.assertTrue(found.evidence.kept)
                    self.assertLessEqual({(kept.start, kept.end) for kept in found.evidence.kept}, integrity.kept)
                    self.assertIsNotNone(found.evaluation)
                    self.assertTrue(found.evaluation.supporting)
        self.assertGreaterEqual(ready, 6)  # the corpus has READY codes to prove it on

    def test_with_r1_keeping_nothing_nothing_is_ready(self):
        class NothingExact(Integrity):
            def exact_evidence(self, spans, text, pages):
                return (), tuple('withheld' for _ in spans)

        for name, doc, codes in (('two sessions', two_sessions(), TWO),
                                 ('office', office_and_sigmoidoscopy(), (('99213', 1), ('45330', 2)))):
            with self.subTest(fixture=name):
                found = run(doc.build(), *codes, integrity=NothingExact())
                self.assertEqual({p.status for p in found.codes}, {Outcome.EXCLUDED})

    def test_the_text_is_read_by_r1_alone(self):
        """P-TEXTFREE at assess (9.4, its assess half): every character of the revision replaced by 'x' and every quote
        with it (same lengths, so R1 still finds each quote at its offsets) leaves the assessment byte-identical."""
        plain = 'x' * len(TEXT)
        for name, doc, codes in (('two sessions', two_sessions(), TWO), ('egd', egd_dilation(), (('43249', 2),))):
            with self.subTest(fixture=name):
                R = doc.build()
                self.assertEqual(AS.digest(run(R, *codes)), AS.digest(run(R, *codes, text=plain)))


# --- P-INDEP on the assess fixtures (4.9, 9.4) ------------------------------------------------------------------------


_ROLE_FAMILY = {RQ.Role.SESSION: IdFamily.SESSION, RQ.Role.ANATOMY: IdFamily.ANATOMY, RQ.Role.LESION: IdFamily.LESION,
                RQ.Role.ENCOUNTER: None,
                **{role: IdFamily.EVENT for role in (RQ.Role.ACT, RQ.Role.EXAMINATION, RQ.Role.VISIT,
                                                     RQ.Role.SESSION_ACT, RQ.Role.COUNTERPART, RQ.Role.WHOLE,
                                                     RQ.Role.STATEMENT, RQ.Role.SAME_DAY_ACT)}}
_TABLES = {IdFamily.EVENT: 'events', IdFamily.SESSION: 'sessions', IdFamily.LESION: 'lesions',
           IdFamily.ANATOMY: 'anatomy'}


def closure(code: str) -> set:
    """(object family, attribute) of every read of ``code``'s requirements (requirements.dependencies, by role)."""
    found = RQ.dependencies(code)
    return {(_ROLE_FAMILY[role], attribute) for role, attributes in found.reads.items() if role in _ROLE_FAMILY
            for attribute in attributes}


def variants(members: tuple) -> list:
    """The perturbations of one attribute's facts: a member dropped, an unresolved member added, and for a single fact
    its value unresolved, silent, contradicted and negated."""
    if not members:
        return []
    first = members[0]
    out = [members[:-1], members + (Fact(Res.UNRESOLVED, first.value, State.SUPPORTED, (), (Reason.APPRAISAL_UNCLEAR,),
                                         first.spans),)]
    if len(members) == 1:
        out += [(Fact(Res.UNRESOLVED, first.value, first.state or State.SUPPORTED, (), (Reason.APPRAISAL_UNCLEAR,),
                      first.spans),), (F.SILENT,)]
        if first.value is not None:
            out += [(Fact(Res.CONTRADICTED, None, State.CONTRADICTED, (first.value,), (Reason.CONTRADICTED_BY_PASS1,),
                          first.spans),),
                    (Fact(Res.NEGATED, first.value, State.NEGATED, (), (), first.spans),)]
    return out


def perturbations(R: FactSet, subjects=None, keep=frozenset()):
    """Every perturbed FactSet: each fact of each object (of ``subjects`` when given), but the attributes in ``keep``,
    each variant whose arity its attribute admits - (family, subject, attribute, variant index, the FactSet)."""
    for family, name in _TABLES.items():
        table = getattr(R, name)
        for subject, attributes in table.items():
            if subjects is not None and subject not in subjects:
                continue
            for attribute, members in attributes.items():
                if attribute in keep:
                    continue
                domain = F.DOMAINS.get((family, attribute))
                for index, new in enumerate(variants(members)):
                    if domain is not None and not domain.many and len(new) != 1:
                        continue
                    changed = dict(table)
                    changed[subject] = {**changed[subject], attribute: new}
                    yield family, subject, attribute, index, replace(R, **{name: changed})


def outcome(found: AS.Assessed) -> tuple:
    """What P-INDEP keeps unchanged: the status, the item - the held fact it asks and its message - and the held facts.
    The item's Fill is compared apart (FillTests): questions.fill reads some slots for display whatever the message."""
    item = (found.item.held, found.item.message) if found.item is not None else None
    return found.status, item, found.held_facts


# The Fill slots questions.fill (step 4a) fills for every item, whether or not its message words them: the held act's
# supported device, place and entry owner, its session's supported tract, stations and reach (the step's NOTES, question
# Q4; request R4).
DISPLAY_SLOTS = frozenset({'device', 'place', 'owner', 'tract', 'stations', 'denied', 'reached', 'stated'})


class IndependenceTests(SimpleTestCase):
    """9.4 P-INDEP over the assembly: no coupling assess adds between codes beyond 4.9's coding relations."""

    def assert_independent(self, doc: EF.Doc, codes: tuple) -> int:
        R = dated(doc.build())
        base = run(R, *codes)
        checked = 0
        for family, subject, attribute, index, changed in perturbations(R):
            after = run(changed, *codes)
            for before in base.codes:
                if (family, attribute) in closure(before.code):
                    continue
                checked += 1
                with self.subTest(code=before.code, subject=str(subject), attribute=attribute.value, variant=index):
                    self.assertEqual(outcome(after.code(before.key)), outcome(before))
        return checked

    def test_a_fact_no_role_of_the_code_reads_never_moves_it(self):
        checked = self.assert_independent(enriched(), TWO)
        checked += self.assert_independent(egd_dilation(), (('43249', 2), ('43239', 3), ('43235', 1)))
        checked += self.assert_independent(office_and_sigmoidoscopy(), (('99213', 1), ('45330', 2)))
        self.assertGreater(checked, 400)  # the fixtures carry facts outside every code's closure

    def test_an_act_of_another_session_no_role_of_the_code_reads_never_moves_it(self):
        """The object level: for each code, every fact but the kind and the session (which decide whether an act fills a
        role) of each act whose kind no role of the code reads, in a session of another family whose kind is supported
        and none of whose acts may be of a kind the code reads, and every fact but the kind of such a session. A base
        code reads every examination as a candidate and 45380 and 43239 every biopsy (4.4's candidates carry no family
        filter), so the second fixture keeps the biopsy in one session only."""
        snare_and_biopsy = EF.colonoscopy()
        snare_and_biopsy.session(2, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        snare_and_biopsy.exam(4, session=X(2))
        snare_and_biopsy.act(5, Kind.BIOPSY, session=X(2), places=[sup(Landmark.GASTRIC_ANTRUM)])
        checked, seen = 0, set()
        for doc, codes in ((enriched(), TWO), (snare_and_biopsy, (('45385', 2), ('43239', 5)))):
            R = dated(doc.build())
            base = run(R, *codes)
            for before in base.codes:
                deps = RQ.dependencies(before.code)
                family = CAT.family_for_code(before.code)
                kinds = set(deps.kinds) | set(deps.statement_kinds)
                sessions = {session for session in R.sessions
                            if F.fact(R, session, A.KIND).result is Res.SUPPORTED
                            and F.fact(R, session, A.KIND).value is not family
                            and not any(F.possibly(F.fact(R, event, A.SESSION), session)
                                        and F.possibly(F.fact(R, event, A.KIND), kind)
                                        for event in R.events for kind in kinds)}
                events = {event for event in R.events if F.fact(R, event, A.SESSION).value in sessions
                          and F.fact(R, event, A.KIND).result is Res.SUPPORTED
                          and F.fact(R, event, A.KIND).value not in kinds}
                if not (events and sessions):
                    continue  # every act of every session may fill a role of this code
                for _, subject, attribute, index, changed in perturbations(R, events | sessions, {A.KIND, A.SESSION}):
                    checked += 1
                    seen.add(before.code)
                    with self.subTest(code=before.code, subject=str(subject), attribute=attribute.value,
                                      variant=index):
                        self.assertEqual(outcome(run(changed, *codes).code(before.key)), outcome(before))
        self.assertGreaterEqual(checked, 150)
        self.assertEqual(seen, {'45385', '43239'})

    def test_4_9s_own_example(self):
        """ "A dilation whose device is unknown holds 43249 and nothing else; 43239's biopsy stands." - and no fact of
        the dilation but its kind and its session moves 43239."""
        R = dated(egd_dilation().build())
        found = by_code(run(R, ('43249', 2), ('43239', 3)))
        self.assertEqual(found['43239'].status, Outcome.READY)
        self.assertEqual(found['43249'].status, Outcome.NEEDS_CLARIFICATION)
        self.assertEqual(facts_of(found['43249']), [('technique', 'reading_unknown')])
        for _, subject, attribute, index, changed in perturbations(R, {E(2)}, {A.KIND, A.SESSION}):
            with self.subTest(attribute=attribute.value, variant=index):
                self.assertEqual(outcome(by_code(run(changed, ('43249', 2), ('43239', 3)))['43239']),
                                 outcome(found['43239']))


class FillTests(SimpleTestCase):
    def test_a_fact_outside_the_closure_moves_only_the_fills_display_slots(self):
        """Under every out-of-closure perturbation of test_a_fact_no_role_of_the_code_reads_never_moves_it, an item's
        Fill differs, when it does, only in the display slots questions.fill fills for every item (DISPLAY_SLOTS): the
        question asked (its held fact and message) never moves. The two found here - an EGD base code's item naming its
        session's stations, a colonoscopy biopsy's naming its session's tract - are recorded (the step's NOTES)."""
        R = dated(enriched().build())
        base = run(R, *TWO)
        moved: set = set()
        for family, subject, attribute, index, changed in perturbations(R):
            after = run(changed, *TWO)
            for before in base.codes:
                if (family, attribute) in closure(before.code) or before.item is None:
                    continue
                now = after.code(before.key).item
                for field in dataclasses.fields(before.item.fill):
                    if getattr(now.fill, field.name) != getattr(before.item.fill, field.name):
                        moved.add((before.code, attribute.value, field.name))
        self.assertLessEqual({slot for _, _, slot in moved}, DISPLAY_SLOTS)
        self.assertEqual(moved, {('43235', 'stations', 'stations'), ('43235', 'stations', 'denied'),
                                 ('45380', 'tract', 'tract')})


# --- R6, R7 and the considerations (4.3, 4.4, 4.7) --------------------------------------------------------------------


class R6Tests(SimpleTestCase):
    def test_r6_extent_an_upper_endoscopys_reach_or_its_stated_incompleteness(self):
        for reached, completion, expected in (
                ([sup(Extent.SECOND_PORTION_DUODENUM)], None, Outcome.READY),
                ([sup(Extent.STATED_DEPTH)], None, Outcome.READY),
                ([], sup(ct.Completion.INCOMPLETE), Outcome.READY),
                ([], sup(ct.Completion.TERMINATED), Outcome.READY),
                ([EF.unres(Extent.DUODENUM)], None, Outcome.NEEDS_CLARIFICATION),
                ([], sup(ct.Completion.COMPLETE), Outcome.NEEDS_CLARIFICATION),
                ([], None, Outcome.NEEDS_CLARIFICATION)):
            with self.subTest(reached=reached, completion=completion):
                doc = EF.Doc()
                attributes = {'reached': reached} if reached else {}
                if completion is not None:
                    attributes['completion'] = completion
                doc.session(1, SessionKind.EGD, **attributes)
                doc.exam(1)
                doc.act(2, Kind.BIOPSY, places=[sup(Landmark.GASTRIC_ANTRUM)])
                found = by_code(run(doc.build(), ('43239', 2)))['43239']
                self.assertEqual(found.status, expected)
                if expected is Outcome.NEEDS_CLARIFICATION:
                    self.assertEqual((found.item.held.fact, found.item.held.rank, found.item.message),
                                     ('extent', 14, Q.MessageId.EXTENT))
                    self.assertEqual((found.item.held.subject, found.item.held.attribute), (X(1), A.REACHED))
        # a completion in doubt with no reach stated: the doubt is what the question rests on
        doubted = EF.Doc()
        doubted.session(1, SessionKind.EGD, completion=EF.unres(ct.Completion.INCOMPLETE))
        doubted.exam(1)
        doubted.act(2, Kind.BIOPSY, places=[sup(Landmark.GASTRIC_ANTRUM)])
        held = by_code(run(doubted.build(), ('43239', 2)))['43239'].item.held
        self.assertEqual((held.attribute, held.result, held.cause), (A.COMPLETION, Res.UNRESOLVED, 'appraisal:unclear'))

    def test_colfull_the_full_reach_an_ileocolic_anastomosis_or_a_stated_incompleteness(self):
        def colon(**attributes):
            doc = EF.Doc()
            doc.session(1, SessionKind.COLONOSCOPY, **attributes)
            doc.exam(1)
            doc.act(2, Kind.SNARE, places=[sup(Landmark.SIGMOID_COLON)], device=sup(Device.COLD_SNARE))
            return doc

        full = colon(reached=[sup(Extent.TERMINAL_ILEUM)])
        short = colon(reached=[sup(Extent.SPLENIC_FLEXURE)])
        stopped = colon(reached=[sup(Extent.SPLENIC_FLEXURE)], completion=sup(ct.Completion.INCOMPLETE))
        unreached = colon(completion=sup(ct.Completion.TERMINATED))  # v1 asked the extent here, and so does v2
        anastomosis, colorectal = colon(), colon()
        for doc, subtype in ((anastomosis, ct.AnastomosisSubtype.ILEOCOLIC),
                             (colorectal, ct.AnastomosisSubtype.COLORECTAL)):
            doc.sessions[X(1)] = {**doc.sessions[X(1)], A.REACHED_ANATOMY: (sup(Y(1)),)}
            doc.entry(1, type=sup(ct.AnatomyType.ANASTOMOSIS), subtype=sup(subtype))
        for name, doc, status, considered in (('full', full, Outcome.READY, ()),
                                              ('short', short, Outcome.NEEDS_CLARIFICATION, ()),
                                              ('incomplete', stopped, Outcome.READY, (AS.Consideration.INCOMPLETE,)),
                                              ('terminated, no reach', unreached, Outcome.NEEDS_CLARIFICATION,
                                               (AS.Consideration.INCOMPLETE,)),
                                              ('ileocolic', anastomosis, Outcome.READY, ()),
                                              ('colorectal', colorectal, Outcome.NEEDS_CLARIFICATION, ())):
            with self.subTest(fixture=name):
                found = by_code(run(doc.build(), ('45385', 2)))['45385']
                self.assertEqual((found.status, found.considerations), (status, considered))
                colfull = [row for row in found.trace if row.requirement == 'COLFULL']
                self.assertEqual(len(colfull), 1)
                if status is Outcome.NEEDS_CLARIFICATION:
                    self.assertEqual(found.item.held.fact, 'extent')
                    self.assertEqual(colfull[0].truth.value, 'U')
        # an established reach short of the cecum fails COLFULL by its rule: the cause names it
        short_item = by_code(run(short.build(), ('45385', 2)))['45385'].item.held
        self.assertEqual((short_item.result, short_item.cause), (Res.SUPPORTED, 'coding_rule:COLFULL'))

    def test_r6_target_an_eus_place_of_the_act_or_of_the_examination(self):
        def eus(act_places=(), exam_places=()):
            doc = EF.Doc()
            doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.UPPER), reached=[sup(Extent.SECOND_PORTION_DUODENUM)],
                        stations=[sup(ct.Station.ESOPHAGUS), sup(ct.Station.STOMACH), sup(ct.Station.DUODENUM)])
            doc.exam(1, places=list(exam_places))
            doc.act(2, Kind.FNA, places=list(act_places))
            return doc

        for name, doc, expected in (('act', eus(act_places=[sup(Landmark.PANCREAS)]), True),
                                    ('examination', eus(exam_places=[sup(Landmark.PANCREAS)]), True),
                                    ('neither', eus(), False)):
            with self.subTest(fixture=name):
                found = by_code(run(doc.build(), ('43242', 2)))['43242']
                held = [held for held in found.held_facts if held.fact == 'target']
                self.assertEqual(not held, expected)
                # the triage's hand-off 1e#3: the full EUS class compares Station values - with all three stations
                # and the duodenum reached, nothing but R6:target can hold 43242
                self.assertEqual(found.status, Outcome.READY if expected else Outcome.NEEDS_CLARIFICATION)

    def test_r6_cannulation_supported_failed_and_unknown(self):
        def ercp(**cannulation):
            doc = EF.Doc()
            doc.session(1, SessionKind.ERCP)
            doc.exam(1)
            if cannulation is not None:
                doc.act(2, Kind.CANNULATION, **cannulation)
            return doc

        achieved = dict(access=sup(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
        failed = dict(access=sup(ct.AccessOutcome.FAILED), duct=sup(ct.Duct.BILIARY),
                      status=sup(ct.Status.ATTEMPTED_NOT_COMPLETED))
        unknown = dict(access=EF.unres(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
        for name, kwargs, held, considered in (('achieved', achieved, False, ()),
                                               ('failed', failed, False, (AS.Consideration.INCOMPLETE,)),
                                               ('unknown', unknown, True, ())):
            with self.subTest(case=name):
                found = by_code(run(ercp(**kwargs).build(), ('43260', 1)))['43260']
                self.assertEqual(any(item.fact == 'cannulation' for item in found.held_facts), held)
                self.assertEqual(found.considerations, considered)
        none = EF.Doc()
        none.session(1, SessionKind.ERCP)
        none.exam(1)
        found = by_code(run(none.build(), ('43260', 1)))['43260']
        self.assertEqual([(held.fact, held.subject) for held in found.held_facts if held.fact == 'cannulation'],
                         [('cannulation', X(1))])

    def test_r6_em_basis_and_the_member_context(self):
        doc = office_and_sigmoidoscopy()
        found = by_code(run(doc.build(), ('99213', 1)))['99213']
        self.assertNotIn('em_basis', [held.fact for held in found.held_facts])
        unstated = EF.Doc()
        unstated.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        unstated.act(1, Kind.EM_VISIT)
        visit = by_code(run(unstated.build(), ('99213', 1)))['99213']
        self.assertEqual([(held.fact, held.rank) for held in visit.held_facts], [('em_basis', 19)])
        # 99417's visit is the em_visit of its prolonged time's session (requirements.Role.VISIT)
        prolonged = EF.Doc()
        prolonged.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        prolonged.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.TOTAL_TIME))
        prolonged.act(2, Kind.EM_PROLONGED)
        self.assertEqual(AS.visits_of(dated(prolonged.build()), (E(2),)), (E(1),))
        # R6:context: member values only (D3); setting first, its sentence naming both when both are missing
        for member, fact, both in ((AS.MemberContext(), 'setting', True),
                                   (AS.MemberContext(setting='office'), 'patient_status', False),
                                   (AS.MemberContext(patient_status='new'), 'setting', False)):
            with self.subTest(member=member):
                found = by_code(run(_office().build(), ('99213', 1), member=member))['99213']
                self.assertEqual((found.item.held.fact, found.item.held.cause, found.item.held.rank),
                                 (fact, 'context_missing', 23))
                self.assertEqual(found.item.fill.both, both)

    def test_r7_the_date_of_service_unknown_holds_every_code_last(self):
        R = two_sessions().build()
        found = run(R, *TWO, date=None)
        self.assertEqual({p.status for p in found.codes}, {Outcome.NEEDS_CLARIFICATION})
        snare = by_code(found)['45385']
        self.assertEqual((snare.item.held.fact, snare.item.held.rank, snare.item.held.cause, snare.item.message),
                         ('service_date', None, 'date_unknown', Q.MessageId.SERVICE_DATE))
        base = by_code(found)['45378']
        self.assertEqual([held.fact for held in base.held_facts], ['base_included', 'service_date'])  # unranked last
        self.assertEqual(base.item.held.fact, 'base_included')
        self.assertIn('R7', [row.requirement for row in snare.trace])

    def test_the_considerations(self):
        found = by_code(run(office_and_sigmoidoscopy().build(), ('99213', 1), ('45330', 2)))
        self.assertEqual(found['99213'].considerations, (AS.Consideration.SEPARATE_EM,))
        self.assertEqual(found['45330'].considerations, ())
        attempted = EF.egd()
        attempted.events[E(1)] = {**attempted.events[E(1)], A.STATUS: (sup(ct.Status.ATTEMPTED_NOT_COMPLETED),)}
        self.assertEqual(by_code(run(attempted.build(), ('43235', 1)))['43235'].considerations,
                         (AS.Consideration.INCOMPLETE,))


# --- DECISIONS D244: R-K8 and Q-S4 (this repair; its NOTES give each probe and the logs) ------------------------------

SIDE_A, SIDE_B = Span(1000, 1060), Span(1100, 1160)  # the two statements of a reach given both polarities (units 10, 11)
CONFLICT = (A.REACHED, X(1), Res.CONTRADICTED, ItemKind.QUESTION, 'reading_contradicted', Reason.CONTRADICTED_BY_PASS1)


def k8_pair(value) -> list:
    """A reach given both polarities as settle stores it (3.1 K8 [R:HO-9], 3.3 row 1): ONE contradicted fact of pass 1
    with both sources kept - two contradicted members of the reach, the supported claim (SIDE_A) and the negated one
    (SIDE_B), the claimed value kept, reason contradicted_by_pass1. RF-HO9 (i)'s FactSet has exactly this shape (the
    repair's logs/probe-ho9-facts-pristine.log): 'The colonoscope was advanced to the cecum.' and 'The cecum was not
    reached because of a stricture.'"""
    return [EF.fact(Res.CONTRADICTED, value, State.SUPPORTED, reasons=(Reason.CONTRADICTED_BY_PASS1,), spans=(SIDE_A,)),
            EF.fact(Res.CONTRADICTED, value, State.NEGATED, reasons=(Reason.CONTRADICTED_BY_PASS1,), spans=(SIDE_B,))]


def scene(family: SessionKind, reached: list, act=None, **session) -> EF.Doc:
    """One session X1 of ``family`` (its examination E1) with ``reached`` as its reach members and ``session``'s other
    facts; ``act``: (kind, place) of a done act E2 in it, or None for the examination alone."""
    doc = EF.Doc()
    doc.session(1, family, **({'reached': reached} if reached else {}), **session)
    doc.exam(1)
    if act is not None:
        doc.act(2, act[0], places=[sup(act[1])])
    return doc


def worded(found: AS.Assessed, text: str = TEXT):
    """The held code's ONE item worded as the renderer words an item that quotes text (D246: wording.build with the
    Slots of its Fill; tests/v2/test_questions.slots): ValueError if wording refuses it."""
    from studio.interpretation import wording
    values = {field.name: getattr(found.item.fill, field.name) for field in dataclasses.fields(Q.Fill)}
    values['bundling'] = wording.Bundling(found.item.fill.bundling.value) if found.item.fill.bundling else None
    return wording.build(wording.Message(found.item.message.value), wording.Slots(**values), text)


class D244Tests(SimpleTestCase):
    """D244's two repairs of step 5a. R-K8: a contradicted reach (the K8 pair) asks RANK 1 conflict:examination in the
    R6:extent and COLFULL rows, as engine/evaluate.py's LOWER row does (4.8 RANK row 1; RF-HO9 (i): 45378 held at rank
    1). Q-S4, option (a), the installed reading: when pass 2 did not establish the completion, the code is READY with
    the 52|53 consideration (S4 (ii): 43260). The pipeline-level cases are tests/v2/test_failure_classes.py's
    KnownDefectTests.test_R_K8 and test_Q_S4 (step 6c's); these are their FactSets, built here."""

    def check_conflict(self, found: AS.Assessed, attribute=A.REACHED, spans=(SIDE_A, SIDE_B), requirement='COLFULL'):
        """``found`` is held, its ONE item RANK 1's conflict:examination about the session's ``attribute`` (a question,
        the reading's cause, contradicted_by_pass1), quoting ``spans``, worded as CONFLICT_ATTRIBUTE about the
        examination of the session's own family; no extent question beside it; the row's trace U with that witness."""
        self.assertEqual(found.status, Outcome.NEEDS_CLARIFICATION)
        self.assertIsNotNone(found.item)
        held = found.item.held
        self.assertEqual((held.fact, held.rank), ('conflict:examination', 1))
        self.assertEqual((held.attribute, held.subject, held.result, held.kind, held.cause, held.reason),
                         (attribute,) + CONFLICT[1:])
        self.assertEqual(held.spans, spans)
        self.assertEqual((found.item.message, found.item.fill.attribute, found.item.fill.act, found.item.fill.family),
                         (Q.MessageId.CONFLICT_ATTRIBUTE, attribute, Kind.EXAMINATION, found.family))
        self.assertNotIn('extent', [fact for fact, _ in facts_of(found)])  # rank 14 never stands in for it
        rows = [row for row in found.trace if row.requirement == requirement]
        self.assertEqual([(row.truth.value, row.subject, row.witness) for row in rows], [('U', X(1), held)])

    def test_r_k8_rf_ho9_i_a_reach_given_both_polarities_holds_45378_at_rank_1(self):
        """RF-HO9 (i)'s FactSet: a colonoscopy whose reach is a K8 pair and whose completion is silent; 45378 was held
        on ``extent`` at rank 14 (cause reading_contradicted) and is now held at RANK 1 on conflict:examination, its
        only held fact, its item quoting both statements."""
        doc = scene(SessionKind.COLONOSCOPY, k8_pair(Extent.CECUM), encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        found = by_code(run(doc.build(), ('45378', 1)))['45378']
        self.check_conflict(found)
        self.assertEqual(len(found.held_facts), 1)
        self.assertEqual(set(found.item.fill.statements), {(SIDE_A,), (SIDE_B,)})
        self.assertEqual(found.considerations, ())

    def test_r_k8_the_r6_extent_rows_ask_it_too_and_pass_1s_contradicted_claim_is_one(self):
        """R6:extent (egd, flex_sig) asks a K8 pair at RANK 1 as COLFULL does; pass 1's own contradicted claim (its
        sides its options, its value None: EF.contra) is a contradicted reach too, quoting its own span."""
        for name, doc, code, wanted in (
                ('egd', scene(SessionKind.EGD, k8_pair(Extent.DUODENUM), (Kind.BIOPSY, Landmark.GASTRIC_ANTRUM)),
                 '43239', 'R6:extent'),
                ('flex_sig', scene(SessionKind.FLEX_SIG, k8_pair(Extent.SIGMOID_COLON),
                                   (Kind.BIOPSY, Landmark.SIGMOID_COLON)), '45331', 'R6:extent')):
            with self.subTest(family=name):
                self.check_conflict(by_code(run(doc.build(), (code, 2)))[code], requirement=wanted)
        sides = EF.contra(Extent.CECUM, Extent.ASCENDING_COLON, spans=(SIDE_A,))
        found = by_code(run(scene(SessionKind.COLONOSCOPY, [sides]).build(), ('45378', 1)))['45378']
        self.check_conflict(found, spans=(SIDE_A,))

    def test_r_k8_the_contradiction_is_asked_before_anything_else_the_row_reads(self):
        """As LOWER asks a contradicted point first (evaluate._lower_reach), a contradicted reach is never dismissed
        (3.3 row 1): another supported point in the full reach, an ileocolic anastomosis reached, a supported
        incompleteness beside a supported reach (COLFULL's established-otherwise arm), and R6:extent's supported point
        or stated termination each leave the code held at RANK 1 (the repair's NOTES, question Q-K8a)."""
        ileocolic = scene(SessionKind.COLONOSCOPY, k8_pair(Extent.CECUM))
        ileocolic.sessions[X(1)] = {**ileocolic.sessions[X(1)], A.REACHED_ANATOMY: (sup(Y(1)),)}
        ileocolic.entry(1, type=sup(ct.AnatomyType.ANASTOMOSIS), subtype=sup(ct.AnastomosisSubtype.ILEOCOLIC))
        for name, doc, code, requirement in (
                ('a full point beside it', scene(SessionKind.COLONOSCOPY,
                                                 [sup(Extent.TERMINAL_ILEUM)] + k8_pair(Extent.CECUM)), '45378',
                 'COLFULL'),
                ('an ileocolic anastomosis', ileocolic, '45378', 'COLFULL'),
                ('incomplete beside a reach', scene(SessionKind.COLONOSCOPY,
                                                    [sup(Extent.SPLENIC_FLEXURE)] + k8_pair(Extent.CECUM),
                                                    completion=sup(ct.Completion.INCOMPLETE)), '45378', 'COLFULL'),
                ('an egd reach beside it', scene(SessionKind.EGD,
                                                 [sup(Extent.SECOND_PORTION_DUODENUM)] + k8_pair(Extent.DUODENUM)),
                 '43235', 'R6:extent'),
                ('an egd stated terminated', scene(SessionKind.EGD, k8_pair(Extent.DUODENUM),
                                                   completion=sup(ct.Completion.TERMINATED)), '43235', 'R6:extent')):
            with self.subTest(beside=name):
                self.check_conflict(by_code(run(doc.build(), (code, 1)))[code], requirement=requirement)

    def test_r_k8_a_reach_that_is_not_contradicted_still_asks_the_extent(self):
        """RF-HO9 (ii)'s FactSet (the reach unresolved: pass 2 contradicts it) and an established negated reach alone
        keep R6's extent question at rank 14, with their own causes: only a contradicted fact moves to RANK 1."""
        for name, member, cause in (('unresolved', EF.unres(Extent.CECUM, Reason.APPRAISAL_CONTRADICTS, spans=(SIDE_A,)),
                                     'appraisal:contradicts'),
                                    ('negated', EF.neg(Extent.CECUM, spans=(SIDE_B,)), 'coding_rule:COLFULL')):
            with self.subTest(reach=name):
                found = by_code(run(scene(SessionKind.COLONOSCOPY, [member]).build(), ('45378', 1)))['45378']
                held = found.item.held
                self.assertEqual((held.fact, held.rank, held.attribute, held.cause), ('extent', 14, A.REACHED, cause))
                self.assertEqual(found.item.message, Q.MessageId.EXTENT)

    def test_r_k8_a_contradicted_completion_the_unmet_row_rests_on_asks_rank_1(self):
        """4.8 RANK row 1 includes a doubt with basis conflict: an R6:extent row with no reach stated rests on its
        completion, and a contradicted completion - pass 1's contradicted claim, or an empty slot a conflict doubt
        names (state None: never silence, D217) - asks conflict:examination about the completion at RANK 1 (question
        Q-K8b); beside a supported reach the row is met and the completion is no requirement - READY, its 52|53
        consideration Q-S4's (the completion is not established)."""
        claimed = EF.contra(ct.Completion.COMPLETE, ct.Completion.TERMINATED, spans=(SIDE_A, SIDE_B))
        empty = Fact(Res.CONTRADICTED, None, None, (ct.Completion.COMPLETE, ct.Completion.TERMINATED),
                     (Reason.CONTRADICTED_BY_PASS1,), (SIDE_A, SIDE_B))
        for name, sides in (('a contradicted claim', claimed), ('an empty slot a conflict doubt names', empty)):
            with self.subTest(completion=name):
                unmet = by_code(run(scene(SessionKind.EGD, [], (Kind.BIOPSY, Landmark.GASTRIC_ANTRUM),
                                          completion=sides).build(), ('43239', 2)))['43239']
                self.check_conflict(unmet, attribute=A.COMPLETION, requirement='R6:extent')
                self.assertEqual(unmet.considerations, (AS.Consideration.INCOMPLETE,))
                met = by_code(run(scene(SessionKind.EGD, [sup(Extent.SECOND_PORTION_DUODENUM)],
                                        (Kind.BIOPSY, Landmark.GASTRIC_ANTRUM), completion=sides).build(),
                                  ('43239', 2)))['43239']
                self.assertEqual((met.status, met.held_facts, met.considerations),
                                 (Outcome.READY, (), (AS.Consideration.INCOMPLETE,)))

    def test_a_silent_slot_is_silence_alone(self):
        """silent_slot is engine/classes.py's reading of the completion slot (D217; refute-4c-r1 A): only no claim, an
        unknown result, no option and silence its only reason is silent. An empty slot a doubt names is not: the
        unmet R6 row rests on it (the completion asked, carrying the doubt's reason) where facts.silent - the claim's
        state alone - read it as silence and asked an unstated reach."""
        silent = (F.SILENT, Fact(Res.UNKNOWN, None, None, (), (Reason.SILENT,), ()))
        not_silent = (Fact(Res.UNKNOWN, None, None, (ct.Completion.COMPLETE,), (Reason.SILENT,), (SIDE_A,)),
                      Fact(Res.UNKNOWN, None, None, (), (Reason.SILENT, Reason.DOUBT_UNCLEAR), ()),
                      Fact(Res.UNKNOWN, None, None, (), (Reason.DOUBT_STATED,), (SIDE_A,)),
                      Fact(Res.UNRESOLVED, None, None, (), (Reason.SESSION_INCONSISTENT,), ()),
                      Fact(Res.UNKNOWN, None, None, (), (), ()), EF.unres(ct.Completion.COMPLETE))
        self.assertEqual([AS.silent_slot(found) for found in silent], [True, True])
        self.assertEqual([AS.silent_slot(found) for found in not_silent], [False] * len(not_silent))
        doubt = Fact(Res.UNKNOWN, None, None, (ct.Completion.INCOMPLETE,), (Reason.DOUBT_STATED,), (SIDE_A,))
        found = by_code(run(scene(SessionKind.EGD, [], (Kind.BIOPSY, Landmark.GASTRIC_ANTRUM),
                                  completion=doubt).build(), ('43239', 2)))['43239']
        held = found.item.held
        self.assertEqual((held.fact, held.rank, held.attribute, held.result, held.cause, held.reason),
                         ('extent', 14, A.COMPLETION, Res.UNKNOWN, 'reading_unknown', Reason.DOUBT_STATED))
        self.assertIn(SIDE_A, held.spans)
        self.assertEqual(found.considerations, (AS.Consideration.INCOMPLETE,))

    def test_r_k8_the_conflict_item_is_worded_quoting_each_side(self):
        """Every item the engine makes is worded (D246's P-WORDED): the reach's and the completion's conflicts word as
        CONFLICT_ATTRIBUTE, each side's own statement quoted, never refused."""
        reach = by_code(run(scene(SessionKind.COLONOSCOPY, k8_pair(Extent.CECUM)).build(), ('45378', 1)))['45378']
        sides = EF.contra(ct.Completion.COMPLETE, ct.Completion.INCOMPLETE, spans=(SIDE_A, SIDE_B))
        completion = by_code(run(scene(SessionKind.EGD, [], (Kind.BIOPSY, Landmark.GASTRIC_ANTRUM),
                                       completion=sides).build(), ('43239', 2)))['43239']
        for name, found in (('reach', reach), ('completion', completion)):
            with self.subTest(conflict=name):
                item = worded(found)
                self.assertEqual((item.fact, item.kind), ('conflict:examination', ItemKind.QUESTION))
                for side in (SIDE_A, SIDE_B):
                    self.assertIn(TEXT[side.start:side.end], item.question)

    def test_q_s4_ii_a_completion_pass_2_did_not_establish_keeps_the_52_53_consideration(self):
        """S4's FactSets (a terminated ERCP; 43260 reads no completion, so no variant holds it): (i) supported
        terminated, 52|53; (ii) the misfiled 'complete' pass 2 contradicted, its control 'incomplete' not rejected -
        unresolved complete, options (incomplete), the pipeline's exact fact (logs/probe-s4-facts-pristine.log) - READY
        WITH 52|53 (it was READY with none: S4's dropped consideration); (iii) the shared misreading, supported complete:
        none (a residual). D244's words: "When completion pass 2 did not establish completion, the code is READY with
        the 52|53 consideration" - so every completion that is not established and not silent keeps it, whatever value
        it claims and however pass 2 answered its control (the misfiled 'complete' with its control rejected too), an
        empty slot a doubt names included (D217: a doubt is never silence); an established one gives it when it is
        incomplete or terminated as engine/classes.py reads it (supported so, or denied complete: question Q-S4c); a
        silent slot, a supported complete, and a denial of incomplete or of terminated give none."""
        INCOMPLETE = (AS.Consideration.INCOMPLETE,)
        cases = (
            ('S4 (i): supported terminated', sup(ct.Completion.TERMINATED), INCOMPLETE),
            ('S4 (ii): pass 2 contradicts complete, control not rejected',
             EF.unres(ct.Completion.COMPLETE, Reason.APPRAISAL_CONTRADICTS, options=(ct.Completion.INCOMPLETE,)),
             INCOMPLETE),
            ('S4 (iii): supported complete', sup(ct.Completion.COMPLETE), ()),
            ('supported incomplete', sup(ct.Completion.INCOMPLETE), INCOMPLETE),
            ('pass 2 contradicts complete, control rejected too',
             EF.unres(ct.Completion.COMPLETE, Reason.APPRAISAL_CONTRADICTS), INCOMPLETE),
            ('pass 2 unclear on complete, control rejected', EF.unres(ct.Completion.COMPLETE, Reason.APPRAISAL_UNCLEAR),
             INCOMPLETE),
            ('a failed check on complete', EF.unres(ct.Completion.COMPLETE, Reason.GEOMETRY_STATEMENT), INCOMPLETE),
            ('unresolved terminated', EF.unres(ct.Completion.TERMINATED), INCOMPLETE),
            ('doubted complete, read terminated', EF.doubted(ct.Completion.COMPLETE, ct.Completion.TERMINATED),
             INCOMPLETE),
            ('doubted complete, no other reading', EF.doubted(ct.Completion.COMPLETE), INCOMPLETE),
            ('contradicted complete or incomplete', EF.contra(ct.Completion.COMPLETE, ct.Completion.INCOMPLETE),
             INCOMPLETE),
            ('an empty slot a doubt names, read incomplete',
             Fact(Res.UNKNOWN, None, None, (ct.Completion.INCOMPLETE,), (Reason.DOUBT_STATED,), (SIDE_A,)), INCOMPLETE),
            ('an empty slot a doubt names, no reading', Fact(Res.UNKNOWN, None, None, (), (Reason.DOUBT_UNCLEAR,), ()),
             INCOMPLETE),
            ('denied complete', EF.neg(ct.Completion.COMPLETE), INCOMPLETE),
            ('denied terminated', EF.neg(ct.Completion.TERMINATED), ()),
            ('denied incomplete', EF.neg(ct.Completion.INCOMPLETE), ()),
            ('silent slot', F.SILENT, ()),
            ('no completion fact', None, ()))
        for name, completion, considered in cases:
            with self.subTest(completion=name):
                doc = EF.Doc()
                doc.session(1, SessionKind.ERCP, **({'completion': completion} if completion is not None else {}))
                doc.exam(1)
                doc.act(2, Kind.CANNULATION, access=sup(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
                found = by_code(run(doc.build(), ('43260', 1)))['43260']
                self.assertEqual((found.status, found.held_facts, found.item), (Outcome.READY, (), None))
                self.assertEqual(found.considerations, considered)
                self.assertEqual(AS.stopped_short(F.fact(dated(doc.build()), X(1), A.COMPLETION)), bool(considered))

    def test_q_s4_never_a_hold_and_never_a_requirement_met(self):
        """The Q-S4 reading is a consideration only: beside a full reach a colonoscopy code is READY with 52|53; a
        completion pass 2 did not establish never meets R6:extent's stated-incompleteness arm (EGD, no reach: extent,
        resting on the completion) nor COLFULL's established-otherwise arm (a short reach: extent), each held with
        52|53 kept."""
        INCOMPLETE = (AS.Consideration.INCOMPLETE,)
        full = scene(SessionKind.COLONOSCOPY, [sup(Extent.CECUM)], completion=EF.unres(ct.Completion.TERMINATED))
        found = by_code(run(full.build(), ('45378', 1)))['45378']
        self.assertEqual((found.status, found.considerations), (Outcome.READY, INCOMPLETE))
        egd = scene(SessionKind.EGD, [], (Kind.BIOPSY, Landmark.GASTRIC_ANTRUM),
                    completion=EF.unres(ct.Completion.INCOMPLETE))
        short = scene(SessionKind.COLONOSCOPY, [sup(Extent.SPLENIC_FLEXURE)],
                      completion=EF.unres(ct.Completion.INCOMPLETE))
        for name, doc, code, attribute in (('egd', egd, '43239', A.COMPLETION), ('short', short, '45378', A.REACHED)):
            with self.subTest(row=name):
                found = by_code(run(doc.build(), (code, 2 if code == '43239' else 1)))[code]
                self.assertEqual((found.status, found.item.held.fact, found.item.held.rank, found.item.held.attribute),
                                 (Outcome.NEEDS_CLARIFICATION, 'extent', 14, attribute))
                self.assertEqual([row.truth.value for row in found.trace if row.requirement in ('R6:extent', 'COLFULL')],
                                 ['U'])
                self.assertEqual(found.considerations, INCOMPLETE)


def _office() -> EF.Doc:
    doc = EF.Doc()
    doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.MEDICAL_DECISION_MAKING))
    return doc


def push_enteroscopy() -> EF.Doc:
    """An oral push enteroscopy X1 reaching the jejunum, stated complete, with a jejunal biopsy E2: the jejunal class
    (44361) fits it, the ileal class (44377) does not reach (4.3's ENT row; the refutation's P6(b))."""
    doc = EF.Doc()
    doc.session(1, SessionKind.ENTEROSCOPY, approach=sup(ct.Approach.ORAL), reached=[sup(Extent.JEJUNUM)],
                completion=sup(ct.Completion.COMPLETE))
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, places=[sup(Landmark.JEJUNUM)])
    return doc


class ClassRuleTests(SimpleTestCase):
    def test_the_class_rule_holds_an_enteroscopy_code_its_class_does_not_fit(self):
        """assess appends classes.enteroscopy_hold over E* (4.4; step 4c's R4, O17's extra= wiring): 44377's class
        witnesses are its held facts and its item, and nothing else holds it; 44361, whose class fits, is READY (4c's
        R7: an enteroscopy fixture expecting a jejunal code READY)."""
        R = dated(push_enteroscopy().build())
        jejunal = by_code(run(R, ('44361', 2)))['44361']
        ileal = by_code(run(R, ('44377', 2)))['44377']
        self.assertEqual((jejunal.status, jejunal.held_facts), (Outcome.READY, ()))
        witnesses = CLS.enteroscopy_hold('44377', ileal.evaluation.supporting, R)
        self.assertTrue(witnesses)
        self.assertEqual(ileal.evaluation.held_facts, ())  # the per-code rule alone would leave it READY
        self.assertEqual((ileal.status, ileal.held_facts), (Outcome.NEEDS_CLARIFICATION, Q.ranked(witnesses, R)))
        self.assertEqual((ileal.item.held.fact, ileal.item.held.subject), ('extent', X(1)))
        self.assertIn(ileal.item.held, witnesses)


# --- ADDON (4.3's row: its primary counted; the refutation's P1) ------------------------------------------------------


def ercp(stone: bool = True) -> EF.Doc:
    """An ERCP X1 with its examination E1, a biliary cannulation E2 achieved, a cholangioscopy E3 and a sphincterotomy
    E4 of the bile duct and, with ``stone``, a stone extraction E5 from it whose yield is not stated (43264 is held by
    YIELD's question)."""
    doc = EF.Doc()
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    doc.act(2, Kind.CANNULATION, access=sup(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
    doc.act(3, Kind.CHOLANGIOSCOPY, duct=sup(ct.Duct.BILIARY))
    doc.act(4, Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY))
    if stone:
        doc.act(5, Kind.STONE_EXTRACTION, duct=sup(ct.Duct.BILIARY))
    return doc


def office_prolonged() -> EF.Doc:
    """An office visit E1 (total time) with its prolonged time E2 in the same session (this encounter)."""
    doc = EF.Doc()
    doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.TOTAL_TIME))
    doc.act(2, Kind.EM_PROLONGED)
    return doc


def manometry() -> EF.Doc:
    doc = EF.Doc()
    doc.session(1, SessionKind.MOTILITY)
    doc.act(1, Kind.MANOMETRY)
    return doc


def addon_facts(found: AS.Assessed) -> list:
    return [held for held in found.held_facts if held.cause == AS.ADDON_CAUSE]


class AddonTests(SimpleTestCase):
    def assert_addon_hold(self, found: AS.Assessed) -> None:
        """``found`` is held, ADDON's one witness among its held facts and its trace's ADDON row U."""
        self.assertEqual(found.status, Outcome.NEEDS_CLARIFICATION)
        self.assertEqual(len(addon_facts(found)), 1, [(held.fact, held.cause) for held in found.held_facts])
        held = addon_facts(found)[0]
        self.assertEqual((held.fact, held.rank, held.kind, held.subject, held.attribute, held.result, held.cause),
                         ('performed_status', 4, ItemKind.QUESTION, None, None, None, 'coding_rule:ADDON'))
        self.assertEqual(held.spans, found.evidence.kept)
        self.assertIn(('ADDON', 'U'), [(row.requirement, row.truth.value) for row in found.trace])

    def test_an_add_on_without_its_primary_is_held_never_ready(self):
        """4.3's ADDON row: 91013, 43273 and 99417, each proposed with its act supported and no primary counted, are
        held with the row's one item (the refutation's P1: each was READY)."""
        for name, doc, code, event in (('91013', manometry(), '91013', 1), ('43273', ercp(stone=False), '43273', 3),
                                       ('99417', office_prolonged(), '99417', 2)):
            with self.subTest(code=name):
                found = by_code(run(doc.build(), (code, event)))[code]
                self.assertTrue(found.evaluation.supporting)
                self.assertEqual(found.evaluation.held_facts, ())  # the per-code rule alone would leave it READY
                self.assert_addon_hold(found)
                self.assertEqual(found.item.held, addon_facts(found)[0])
                # DECISIONS D284 (build list B7): its own message, ADDON, from the codes alone
                self.assertEqual(found.item.message, Q.MessageId.ADDON)
        # D284 (B7): 99417 beside 99213, a code of its family that is not one of its primaries - the same item
        # (its sentence naming the primaries is pinned through the renderer: test_questions.D284AddonItems)
        found = by_code(run(office_prolonged().build(), ('99213', 1), ('99417', 2)))['99417']
        self.assert_addon_hold(found)
        self.assertEqual(found.item.message, Q.MessageId.ADDON)

    def test_an_add_on_beside_its_primary_meets_the_row(self):
        """A primary counted - READY or held - meets the row: 43273 beside 43262 READY; 99417 beside 99215 READY, and
        99215 READY beside it (DECISIONS D255: an add-on never includes another code under the base rules - repair
        r4d's request R4, applied by the integration)."""
        for doc, primary, addon in ((ercp(stone=False), ('43262', 4), ('43273', 3)),
                                    (office_prolonged(), ('99215', 1), ('99417', 2))):
            with self.subTest(addon=addon[0]):
                found = by_code(run(doc.build(), primary, addon))
                self.assertEqual(found[addon[0]].status, Outcome.READY)
                self.assertIn(('ADDON', 'T'), [(row.requirement, row.truth.value) for row in found[addon[0]].trace])
                self.assertFalse(addon_facts(found[addon[0]]))
        # 91013 beside 91010: the row is met; the two compete for the one manometry (combination's; question P7)
        pair = by_code(run(manometry().build(), ('91010', 1), ('91013', 1)))
        self.assertFalse(addon_facts(pair['91013']))
        self.assertEqual([held.fact for held in pair['91013'].held_facts], ['competing_codes'])

    def test_a_code_of_its_family_that_is_not_its_primary_does_not_meet_it(self):
        """The primaries are each add-on's own (ADDON_PRIMARIES), never any code of its family: 99417 beside 99213 and
        91013 beside 91020 are held by the row."""
        office = by_code(run(office_prolonged().build(), ('99213', 1), ('99417', 2)))['99417']
        self.assert_addon_hold(office)
        motility = by_code(run(manometry().build(), ('91020', 1), ('91013', 1)))['91013']
        self.assert_addon_hold(motility)

    def test_a_primary_r1_or_an_exclusion_leaves_out_is_not_counted(self):
        """Counted is proposed, admitted by R1 and not excluded: 43264 quoted with words that are not the document's
        (R1), or EXCLUDED by its cited denial (4.6), leaves 43273 with no primary."""
        r1 = run(ercp().build(), ('43264', wrong(5)), ('43273', 3))
        self.assertEqual(by_code(r1)['43264'].status, Outcome.EXCLUDED)
        self.assert_addon_hold(by_code(r1)['43273'])
        denied = ercp(stone=False)
        denied.act(6, Kind.STONE_EXTRACTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.ALL_OF_KIND),
                    kind_words=Span(600, 630), status_words=Span(630, 660))
        cited = run(denied.build(), ('43264', EvidenceSpan(0, 600, 660, TEXT[600:660], True)), ('43273', 3))
        self.assertIsNotNone(by_code(cited)['43264'].evaluation.exclusion)
        self.assert_addon_hold(by_code(cited)['43273'])

    def test_a_primary_a_members_answer_excludes_no_longer_counts(self):
        """43273 beside 43264, which YIELD holds: READY. "Not documented" on 43264's item excludes it, and 43273 is held
        by the row (a second pass; fail-closed - the step's NOTES, question QA3); an answer to 43273's new item then
        excludes it too, and both answers are recorded applied."""
        R = ercp().build()
        before = by_code(run(R, ('43264', 5), ('43273', 3)))
        self.assertEqual((before['43264'].status, before['43273'].status), (Outcome.NEEDS_CLARIFICATION, Outcome.READY))
        given = answer(before['43264'])
        after = run(R, ('43264', 5), ('43273', 3), answers=(given,))
        self.assertEqual(by_code(after)['43264'].status, Outcome.EXCLUDED)
        addon = by_code(after)['43273']
        self.assert_addon_hold(addon)
        self.assertEqual(addon.item.held, addon_facts(addon)[0])
        self.assertEqual([(item.answer, item.code) for item in after.answers], [('a1', '43264')])
        both = run(R, ('43264', 5), ('43273', 3), answers=(given, answer(addon, answer_id='a2')))
        self.assertEqual({p.code: p.status for p in both.codes}, {'43264': Outcome.EXCLUDED, '43273': Outcome.EXCLUDED})
        self.assertEqual([(item.answer, item.code) for item in both.answers], [('a1', '43264'), ('a2', '43273')])
        self.assertEqual(both.earlier_answers, ())

    def test_d80s_sedation_add_on_keeps_its_one_item(self):
        """99153 is held by D80 before any group is read (no supporting act), so the row adds nothing: its item stays
        recognised_only, alone or beside 99152."""
        sedation = EF.Doc()
        sedation.session(1, SessionKind.SEDATION)
        sedation.act(1, Kind.MODERATE_SEDATION)
        for codes in ((('99153', 1),), (('99152', 1), ('99153', 1))):
            with self.subTest(codes=codes):
                found = by_code(run(sedation.build(), *codes))['99153']
                self.assertEqual((found.item.held.cause, found.item.message),
                                 ('coding_rule:recognised_only', Q.MessageId.RECOGNISED_ONLY))
                self.assertFalse(addon_facts(found))

    def test_the_primary_table_names_every_add_on_and_only_codes_of_its_family(self):
        """ADDON_PRIMARIES' add-ons are exactly the catalogue's add-ons and the requirement table's ADDON codes; each
        primary is a catalogue code of the add-on's family and is no add-on itself (so a second pass settles ADDON)."""
        tagged = {code for code, row in TABLE.CODES.items() if TABLE.Tag.ADDON in row.tags}
        addons = {code for code, profile in CAT.CODES.items() if profile.addon}
        self.assertEqual(set(AS.ADDON_PRIMARIES), tagged)
        self.assertEqual(tagged, addons)
        for addon, found in AS.ADDON_PRIMARIES.items():
            with self.subTest(addon=addon):
                self.assertTrue(found)
                for primary in found:
                    self.assertIn(primary, CAT.CODES)
                    self.assertIs(CAT.CODES[primary].family, CAT.CODES[addon].family)
                    self.assertFalse(CAT.CODES[primary].addon)
                self.assertEqual(AS.primaries(str(addon)), frozenset(str(code) for code in found))
        self.assertEqual(AS.primaries('45385'), frozenset())
        self.assertIsNone(AS.addon_hold('45385', (), ()))


# --- the combination (4.7), member answers (4.8) and the second review (D10) ------------------------------------------


def one_dilation() -> EF.Doc:
    doc = EF.egd()
    doc.act(2, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)], device=sup(Device.BALLOON))
    return doc


class CombinationTests(SimpleTestCase):
    def test_two_codes_for_one_act_compete_and_the_base_code_is_held_beside_its_acts(self):
        found = by_code(run(one_dilation().build(), ('43249', 2), ('43233', 2), ('43235', 1)))
        for code, rival in (('43249', '43233'), ('43233', '43249')):
            with self.subTest(code=code):
                self.assertEqual(found[code].competes, (rival,))
                self.assertEqual(found[code].item.held.fact, 'competing_codes')
        self.assertEqual(found['43235'].item.held.fact, 'base_included')
        self.assertEqual(found['43235'].item.kind, ItemKind.EXPLANATION)

    def test_the_same_day_visit_is_held_beside_the_procedure_with_the_25_consideration(self):
        found = run(office_and_sigmoidoscopy().build(), ('99213', 1), ('45330', 2))
        self.assertTrue(found.combination.day.procedure_day)
        visit = by_code(found)['99213']
        self.assertEqual((visit.item.held.fact, visit.item.held.cause), ('separate_em', 'coding_rule:same_day_em'))
        self.assertEqual(visit.considerations, (AS.Consideration.SEPARATE_EM,))
        documented = office_and_sigmoidoscopy()
        documented.events[E(1)] = {**documented.events[E(1)],
                                   A.VISIT_SEPARATELY_IDENTIFIABLE: (sup(ct.Separate.STATED),)}
        released = by_code(run(documented.build(), ('99213', 1), ('45330', 2)))['99213']
        self.assertEqual((released.status, released.considerations), (Outcome.READY, (AS.Consideration.SEPARATE_EM,)))


def answer(found: AS.Assessed, value='not_documented', question=None, answer_id='a1', fact=None) -> MemberAnswerInput:
    return MemberAnswerInput(code=found.code, family=AS.family_slug(found.family),
                             fact=fact if fact is not None else found.item.held.fact, value=value,
                             question=found.question if question is None else question, answer_id=answer_id)


class MemberAnswerTests(SimpleTestCase):
    def test_an_answer_to_the_item_as_asked_excludes_its_code_and_nothing_else(self):
        R = egd_dilation().build()
        before = run(R, ('43249', 2), ('43239', 3))
        held = by_code(before)['43249']
        after = run(R, ('43249', 2), ('43239', 3), answers=(answer(held),))
        answered = by_code(after)['43249']
        self.assertEqual((answered.status, answered.bucket, answered.reinstatable),
                         (Outcome.EXCLUDED, AS.Bucket.EXCLUDED, False))
        self.assertEqual(answered.answered, AS.Answered('technique', AS.Answer.NOT_DOCUMENTED, ('a1',)))
        self.assertNotEqual(answered.fingerprint, held.fingerprint)
        self.assertEqual(by_code(after)['43239'], by_code(before)['43239'])
        self.assertEqual([(item.answer, item.scope, item.proposals) for item in after.answers],
                         [('a1', AS.Scope.PROPOSAL, (held.key,))])

    def test_a_rival_answered_not_documented_leaves_the_competition(self):
        """DECISIONS D260 (read time's D249 reading; the seam check's scene 677, at assess): one esophageal dilation
        whose device is not stated - 43249 (balloon) and 43248 (guide wire) each ask the technique and compete for the
        act. "Not documented" on 43249's item excludes it - its item, question and held facts as the answer found them
        (the answer stands) - and takes it out of the competition: 43248 has no rival left and loses its
        competing_codes hold, nothing else moved (its technique item, rank 10, asked before the competition's 22, its
        question and its status unchanged), exactly as assess gives 43248 proposed alone - but for its fingerprint,
        which stays the one it has without the answer, so a reviewer's decision on it carries (refute-5a-r1 P-1:
        DecisionCarryTests); the combination the renderer words items over (D246) names no rival for it. (Before D260
        43248 kept the hold here and read time released it with no decision: the seam check's one open finding.)"""
        R = egd_dilation().build()
        before = by_code(run(R, ('43249', 2), ('43248', 2)))
        self.assertEqual([before[code].item.held.fact for code in ('43249', '43248')], ['technique', 'technique'])
        self.assertEqual([held.fact for held in before['43248'].held_facts], ['technique', 'competing_codes'])
        found = run(R, ('43249', 2), ('43248', 2), answers=(answer(before['43249']),))
        after = by_code(found)
        gone = after['43249']
        self.assertEqual((gone.status, gone.bucket, gone.reinstatable), (Outcome.EXCLUDED, AS.Bucket.EXCLUDED, False))
        self.assertEqual(gone.answered, AS.Answered('technique', AS.Answer.NOT_DOCUMENTED, ('a1',)))
        self.assertEqual((gone.item, gone.question, gone.held_facts),
                         (before['43249'].item, before['43249'].question, before['43249'].held_facts))
        rival = after['43248']
        self.assertEqual(rival.competes, ())
        self.assertEqual(rival.held_facts, tuple(held for held in before['43248'].held_facts
                                                 if held.cause != 'coding_rule:competing_codes'))
        self.assertEqual((rival.status, rival.item, rival.question),
                         (Outcome.NEEDS_CLARIFICATION, before['43248'].item, before['43248'].question))
        self.assertEqual(rival.fingerprint, before['43248'].fingerprint)  # its status held: a decision on it carries
        alone = by_code(run(R, ('43248', 2)))['43248']
        self.assertEqual(outcome_of(rival), outcome_of(alone))
        self.assertNotEqual(alone.fingerprint, rival.fingerprint)  # kept from before the answer, not alone's
        self.assertNotIn(rival.key, found.combination.competes)
        self.assertEqual([held.fact for held in found.combination.held[rival.key]], [])
        self.assertEqual([(item.answer, item.code) for item in found.answers], [('a1', '43249')])
        # a competing_codes answer is never the engine's (v1's engine_reads) - and D270's DQ-2 reading leaves it out
        # too: the competing question offers no answer (OverlayAnswerTests). DECISIONS D283 (G1-01, option (c))
        # restates its record: applied by nothing (not_applied), as read time binds none to it either
        rivals = by_code(run(one_dilation().build(), ('43249', 2), ('43233', 2)))
        given = answer(rivals['43233'])
        self.assertEqual(given.fact, 'competing_codes')
        found = run(one_dilation().build(), ('43249', 2), ('43233', 2), answers=(given,))
        self.assertEqual([item.why for item in found.earlier_answers], [AS.Unbound.NOT_APPLIED])
        self.assertEqual(found.codes, run(one_dilation().build(), ('43249', 2), ('43233', 2)).codes)

    def test_answers_the_engine_does_not_bind(self):
        R = egd_dilation().build()
        held = by_code(run(R, ('43249', 2), ('43235', 1)))
        dilation, base = held['43249'], held['43235']
        cases = (
            (answer(dilation, question='0' * 64, answer_id='a2'), AS.Unbound.ASKED_DIFFERENTLY),  # a pre-v2 fingerprint
            (answer(dilation, question='', answer_id='a3'), AS.Unbound.OVERLAY_READ),  # no fingerprint: the overlay's
            (answer(base, answer_id='a4'), AS.Unbound.OVERLAY_READ),  # base_included is key-bound: the overlay's
            (answer(dilation, fact='extent', answer_id='a5'), AS.Unbound.NO_LONGER_ASKED),
        )
        for given, why in cases:
            with self.subTest(why=why, answer=given.answer_id):
                found = run(R, ('43249', 2), ('43235', 1), answers=(given,))
                self.assertEqual([item.why for item in found.earlier_answers], [why])
                self.assertEqual({p.status for p in found.codes}, {Outcome.NEEDS_CLARIFICATION})
        # the encounter's date of service is settled by a date, never by an answer excluding a code - nor by the
        # overlay: the record says no one applies it (the refutation's P8; the step's NOTES, question QS1)
        undated = by_code(run(R, ('43239', 3), date=None))['43239']
        self.assertEqual(undated.item.held.fact, 'service_date')
        for given in (answer(undated, answer_id='a7'), answer(undated, question='', answer_id='a8')):
            with self.subTest(answer=given.answer_id):
                refused = run(R, ('43239', 3), date=None, answers=(given,))
                self.assertEqual(by_code(refused)['43239'].status, Outcome.NEEDS_CLARIFICATION)
                self.assertEqual([item.why for item in refused.earlier_answers], [AS.Unbound.NOT_APPLIED])
        unknown = MemberAnswerInput(code='43249', family='gi.egd', fact='technique', value='confirmed',
                                    question=dilation.question, answer_id='a6')
        self.assertEqual(run(R, ('43249', 2), answers=(unknown,)).earlier_answers, ())  # no value a question takes

    def test_a_service_answer_closes_its_service_question(self):
        doc = EF.Doc()
        doc.session(1, SessionKind.EGD)
        doc.exam(1)
        found = run(doc.build())  # no code asks the done EGD's extent: D125's service question asks it
        extent, = [item for item in found.service_questions if item.item.item.fact == 'extent']
        self.assertEqual((extent.item.session, extent.closed), (X(1), ()))
        given = MemberAnswerInput(code='', family='gi.egd', fact='extent', value='cannot_confirm',
                                  question=extent.question, answer_id='s1')
        closed = run(doc.build(), answers=(given,))
        self.assertEqual([item.closed for item in closed.service_questions if item.item.item.fact == 'extent'],
                         [('s1',)])
        self.assertEqual([(item.answer, item.scope) for item in closed.answers], [('s1', AS.Scope.SERVICE)])
        self.assertIn('1 open question', found.completeness['reasons'])
        self.assertNotIn('1 open question', closed.completeness['reasons'])
        # with a code asking it, the code's item asks it and no service question repeats it (D89)
        asked = run(doc.build(), ('43235', 1))
        self.assertEqual(by_code(asked)['43235'].item.held.fact, 'extent')
        self.assertFalse([item for item in asked.service_questions if item.item.item.fact == 'extent'])

    def test_each_service_answer_closes_the_question_it_was_given_to(self):
        """Two done EGDs that state no extent ask two service questions of one (family, fact), each its own fingerprint.
        DECISIONS D283 (G3-16, option (b); 5b Q1): a service answer binds as read time binds the key - by the FIRST
        question's fingerprint (review.stored_service_questions) - so an answer with it closes every question of the
        key not yet closed, one carrying another question's fingerprint is asked differently (recorded, never applied
        nowhere), an answer naming only questions already closed is recorded as not applied, and an answer recorded
        with no fingerprint closes every question of its (family, fact) not yet closed."""
        doc = EF.Doc()
        for n in (1, 2):
            doc.session(n, SessionKind.EGD)
            doc.exam(n, session=X(n))
        R = doc.build()
        found = run(R)
        first, second = [item for item in found.service_questions if item.item.item.fact == 'extent']
        self.assertEqual((first.item.session, second.item.session), (X(1), X(2)))
        self.assertNotEqual(first.question, second.question)

        def given(answer_id, question):
            return MemberAnswerInput(code='', family='gi.egd', fact='extent', value='not_documented', question=question,
                                     answer_id=answer_id)

        def closed(assessment):
            return [item.closed for item in assessment.service_questions if item.item.item.fact == 'extent']

        one = run(R, answers=(given('s1', first.question),))
        self.assertEqual(closed(one), [('s1',), ('s1',)])
        self.assertEqual([(item.answer, item.scope) for item in one.answers], [('s1', AS.Scope.SERVICE)])
        self.assertEqual(one.earlier_answers, ())
        self.assertIn('2 open questions', found.completeness['reasons'])
        self.assertFalse([reason for reason in one.completeness['reasons'] if 'open question' in reason])
        other = run(R, answers=(given('s2', second.question),))
        self.assertEqual(closed(other), [(), ()])
        self.assertEqual([(item.answer, item.why) for item in other.earlier_answers],
                         [('s2', AS.Unbound.ASKED_DIFFERENTLY)])
        again = run(R, answers=(given('s1', first.question), given('s2', second.question), given('s3', first.question)))
        self.assertEqual(closed(again), [('s1',), ('s1',)])
        self.assertEqual([(item.answer, item.why) for item in again.earlier_answers],
                         [('s2', AS.Unbound.ASKED_DIFFERENTLY), ('s3', AS.Unbound.NOT_APPLIED)])
        keyed = run(R, answers=(given('s1', ''), given('s2', '')))
        self.assertEqual(closed(keyed), [('s1',), ('s1',)])
        self.assertEqual([(item.answer, item.why) for item in keyed.earlier_answers], [('s2', AS.Unbound.NOT_APPLIED)])

    def test_the_applied_record_names_the_question_each_answer_was_bound_to(self):
        """completeness member_answers' applied entries carry the answer's fingerprint and the fingerprint of the
        question it closed (v1's 'question' and 'asked'), which answers.py binds a new answer to (refutation cycle 3,
        C3-4; the refutation's P9)."""
        R = egd_dilation().build()
        held = by_code(run(R, ('43249', 2), ('43239', 3)))['43249']
        found = run(R, ('43249', 2), ('43239', 3), answers=(answer(held),))
        entry, = found.completeness['member_answers']['applied']
        self.assertEqual((entry['answer'], entry['scope'], entry['code'], entry['proposals']),
                         ('a1', 'proposal', '43249', [held.key]))
        self.assertEqual((entry['question'], entry['asked']), (held.question, held.question))
        service = EF.Doc()
        service.session(1, SessionKind.EGD)
        service.exam(1)
        question, = [item.question for item in run(service.build()).service_questions]
        keyed = MemberAnswerInput(code='', family='gi.egd', fact='extent', value='cannot_confirm', question='',
                                  answer_id='s1')
        entry, = run(service.build(), answers=(keyed,)).completeness['member_answers']['applied']
        self.assertEqual((entry['scope'], entry['question'], entry['asked']), ('service', '', question))


# --- DECISIONS D260: a rival a member answered "Not documented" leaves the competition at assess, as at read time ---


def members_of(found: AS.Assessment) -> dict:
    """The combination members engine/assess built for ``found``: every counted proposal - selected, or excluded by a
    member's answer (still counted, session decision (e)) - with its routed family, matched session, E*, origin,
    procedural and supported, as assess_facts builds them."""
    return {p.key: CO.Member(key=p.key, code=p.code, family=p.family, session=p.session,
                             supporting=p.evaluation.supporting, origin=p.origin.value,
                             procedural=AS.procedural(SimpleNamespace(family=p.family, evaluation=p.evaluation), p.pfs),
                             supported=bool(p.evaluation.supporting and not p.evaluation.held_facts))
            for p in found.codes if p.bucket is AS.Bucket.SELECTED or p.answered is not None}


def synthetic_rivals() -> EF.Doc:
    """DECISIONS D231 row 5 beside an answered rival: a colonoscopy X1 with the cold snare E2 (45385) and a forceps
    biopsy E3 (45380) and an unlisted act of no kind carded X1 (units 900 .. 960) - either code may account for it, so
    the two compete over it - and an EGD X2 (E4) with one dilation E5 of the distal esophagus whose device is not
    stated (43249 and 43248 compete over it)."""
    doc = EF.colonoscopy()
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.TRANSVERSE_COLON)])
    doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.ACT, None, X(1), Span(900, 960)))
    doc.session(2, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(4, session=X(2))
    doc.act(5, Kind.DILATION, session=X(2), places=[sup(Landmark.DISTAL_ESOPHAGUS)])
    return doc


SYNTHETIC_CODES = (('45385', 2), ('45380', 3), ('43249', 5), ('43248', 5))
COMPETING = 'coding_rule:competing_codes'


class CompetitionAnswerTests(SimpleTestCase):
    """DECISIONS D260 (the seam check's open finding; 5c's Q2 option (b); read time's D249 reading in
    interpretation/overlay.py): engine/assess removes from the competition a code a member answered "Not documented";
    the remaining code's competing hold is released when no rival is left, and kept naming only the rivals left when
    one is. "Cannot confirm" leaves the competition as it stands (D249's words, as read time reads them; D262)."""

    def answered(self, R, codes, value, code='43249', **kw):
        """(the assessment with no answer, the assessment with a member's ``value`` to ``code``'s item as asked)."""
        plain = run(R, *codes, **kw)
        return plain, run(R, *codes, answers=(answer(by_code(plain)[code], value=value),), **kw)

    def test_a_rival_answered_cannot_confirm_stays_in_the_competition(self):
        """Scene 677's input with "Cannot confirm" on 43249's technique: 43249 is EXCLUDED, but it stays in the
        competition, so 43248 keeps its competing_codes hold naming 43249 - its whole record unchanged - and the
        combination is the unanswered one."""
        plain, found = self.answered(egd_dilation().build(), (('43249', 2), ('43248', 2)), 'cannot_confirm')
        after = by_code(found)
        self.assertEqual((after['43249'].status, after['43249'].answered.value),
                         (Outcome.EXCLUDED, AS.Answer.CANNOT_CONFIRM))
        self.assertEqual(after['43248'], by_code(plain)['43248'])
        self.assertEqual((after['43248'].competes, facts_of(after['43248'])[-1]), (('43249',), ('competing_codes',
                                                                                               COMPETING)))
        self.assertEqual(found.combination, plain.combination)

    def test_with_no_rival_left_the_remaining_code_is_ready_as_assessed_alone(self):
        """43213 (dilation of the esophagus by any device) beside 43249 on the one dilation is held by the competition
        alone. "Not documented" on 43249's technique takes 43249 out: 43213 is READY at assess with no item and no
        question - exactly as assess gives 43213 proposed alone. "Cannot confirm" leaves it held by the competition."""
        R = egd_dilation().build()
        codes = (('43249', 2), ('43213', 2))
        plain, found = self.answered(R, codes, 'not_documented')
        self.assertEqual(facts_of(by_code(plain)['43213']), [('competing_codes', COMPETING)])
        released = by_code(found)['43213']
        self.assertEqual((released.status, released.item, released.question, released.held_facts, released.competes),
                         (Outcome.READY, None, '', (), ()))
        self.assertEqual(decision(released), decision(by_code(run(R, ('43213', 2)))['43213']))
        self.assertEqual(by_code(found)['43249'].status, Outcome.EXCLUDED)
        _, kept = self.answered(R, codes, 'cannot_confirm')
        self.assertEqual(by_code(kept)['43213'], by_code(plain)['43213'])

    def test_with_a_rival_left_the_hold_names_only_the_rivals_left(self):
        """Three codes for the one dilation: "Not documented" on 43249's item leaves 43248 and 43233 competing with each
        other, each keeping its competing_codes hold naming the other alone - exactly as assess gives the pair 43248 and
        43233 proposed without 43249 (the competition read without it)."""
        R = egd_dilation().build()
        _, found = self.answered(R, (('43249', 2), ('43248', 2), ('43233', 2)), 'not_documented')
        pair = by_code(run(R, ('43248', 2), ('43233', 2)))
        after = by_code(found)
        for code, rival in (('43248', '43233'), ('43233', '43248')):
            with self.subTest(code=code):
                self.assertEqual(after[code].competes, (rival,))
                self.assertEqual(found.combination.competes[after[code].key], (rival,))
                self.assertEqual(decision(after[code]), decision(pair[code]))

    def test_answers_on_two_rivals_each_stand_and_only_not_documented_leaves(self):
        """Both answers bind to the items as asked and each stands (EXCLUDED, its item and question as asked). With
        "Not documented" on 43249 and 43248, 43233 has no rival left: its competing hold goes, its technique item stays.
        With "Cannot confirm" on 43248, 43248 stays in the competition: 43233 keeps its hold naming 43248 alone."""
        R = egd_dilation().build()
        codes = (('43249', 2), ('43248', 2), ('43233', 2))
        plain = by_code(run(R, *codes))
        for second, rivals in (('not_documented', ()), ('cannot_confirm', ('43248',))):
            with self.subTest(second=second):
                given = (answer(plain['43249']), answer(plain['43248'], value=second, answer_id='a2'))
                found = run(R, *codes, answers=given)
                after = by_code(found)
                for code, value in (('43249', 'not_documented'), ('43248', second)):
                    self.assertEqual((after[code].status, after[code].answered.value.value),
                                     (Outcome.EXCLUDED, value))
                    self.assertEqual((after[code].item, after[code].question), (plain[code].item, plain[code].question))
                left = after['43233']
                self.assertEqual((left.status, left.item, left.competes),
                                 (Outcome.NEEDS_CLARIFICATION, plain['43233'].item, rivals))
                self.assertEqual([fact for fact, _ in facts_of(left)],
                                 ['technique'] + (['competing_codes'] if rivals else []))
                self.assertEqual([(item.answer, item.code) for item in found.answers],
                                 [('a1', '43249'), ('a2', '43248')])

    def test_every_combination_of_answers_on_one_act(self):
        """Four codes for the one dilation of the distal esophagus, every combination of no answer, "Not documented"
        and "Cannot confirm" on their items (81 assessments). An answered code is EXCLUDED with its item and question as
        asked; the competition is exactly the codes not answered "Not documented": every other counted code competes
        with each of them, in proposal order (the combination's record, and the held hold of each code no answer
        excluded), and a code with no rival left has no competing hold."""
        R = egd_dilation().build()
        codes = ('43249', '43248', '43233', '43220')
        plain = by_code(run(R, *[(code, 2) for code in codes]))
        values = (None, 'not_documented', 'cannot_confirm')
        for chosen in itertools.product(values, repeat=len(codes)):
            given = tuple(answer(plain[code], value=value, answer_id=f'a{index}')
                          for index, (code, value) in enumerate(zip(codes, chosen)) if value is not None)
            found = run(R, *[(code, 2) for code in codes], answers=given)
            after = by_code(found)
            competing = [code for code, value in zip(codes, chosen) if value != 'not_documented']
            with self.subTest(answers=chosen):
                for code, value in zip(codes, chosen):
                    rivals = tuple(other for other in competing if other != code) if code in competing else None
                    self.assertEqual(found.combination.competes.get(after[code].key), rivals or None)
                    if value is not None:
                        self.assertEqual((after[code].status, after[code].answered.value.value),
                                         (Outcome.EXCLUDED, value))
                        self.assertEqual((after[code].item, after[code].question),
                                         (plain[code].item, plain[code].question))
                        continue
                    self.assertEqual((after[code].status, after[code].item), (Outcome.NEEDS_CLARIFICATION,
                                                                              plain[code].item))
                    self.assertEqual(after[code].competes, rivals)
                    self.assertEqual([cause for _, cause in facts_of(after[code])].count(COMPETING), 1 if rivals else 0)

    def test_a_competition_over_a_synthetic_act_stays_when_another_rival_is_answered(self):
        """D231 row 5 beside D260: "Not documented" on 43249 releases 43248 and nothing else - 45385 and 45380 still
        compete over the unlisted act of no kind (their competing holds quoting its unit 900 .. 960), as combine's own
        competition over the codes left gives it. Read time's competition must read the synthetic acts' claims too (the
        step's NOTES, request R1: overlay's own reading dropped them)."""
        R = synthetic_rivals().build()
        plain, found = self.answered(R, SYNTHETIC_CODES, 'not_documented')
        after = by_code(found)
        self.assertEqual((after['43248'].competes, facts_of(after['43248'])), ((), [('technique', 'reading_unknown')]))
        for code, rival in (('45385', '45380'), ('45380', '45385')):
            with self.subTest(code=code):
                self.assertEqual(after[code], by_code(plain)[code])
                self.assertEqual(after[code].competes, (rival,))
                hold, = [held for held in after[code].held_facts if held.cause == COMPETING]
                self.assertIn(Span(900, 960), hold.spans)
        self.assertEqual(found.combination.unlisted_contested, plain.combination.unlisted_contested)

    def test_compete_without_is_combines_competition_over_the_members_left(self):
        """compete_without (the one function read time is asked to read, request R1): nothing out, or an out key that
        is no member, gives the combination itself; with 43249 out of synthetic_rivals its competition records and
        holds are exactly combine's over the members left (43249 holds no other rule there: no base, within or
        same-day record), and the assessment answered "Not documented" on 43249 carries that combination. The answered
        code itself competes with nothing."""
        R = synthetic_rivals().build()
        plain, found = self.answered(R, SYNTHETIC_CODES, 'not_documented')
        members = members_of(plain)
        acts = AS.session_acts(plain.event_coding)
        self.assertEqual(CO.combine(tuple(members.values()), acts, dated(R)), plain.combination)
        for out in ((), ('sel:9',)):
            with self.subTest(out=out):
                self.assertIs(AS.compete_without(plain.combination, members, out, dated(R)), plain.combination)
        out = by_code(plain)['43249'].key
        without = AS.compete_without(plain.combination, members, {out}, dated(R))
        left = CO.combine(tuple(member for key, member in members.items() if key != out), acts, dated(R))
        self.assertEqual((dict(without.competes), dict(without.contested), dict(without.unlisted_contested)),
                         (dict(left.competes), dict(left.contested), dict(left.unlisted_contested)))
        self.assertEqual({key: held for key, held in without.held.items() if key != out}, dict(left.held))
        self.assertEqual([held.cause for held in without.held[out]], [])
        self.assertEqual((without.claims, without.bases, without.day, without.reviews),
                         (plain.combination.claims, plain.combination.bases, plain.combination.day,
                          plain.combination.reviews))
        self.assertEqual(found.combination, without)

    def test_compete_without_keeps_combines_order_after_a_base_hold(self):
        """Three office visit codes on one visit, nothing entered: each is held by the base rule (21) and the
        competition (22). With 99215 out, 99213's holds stay in combine's order - the base hold (combine's, over every
        member: 99215 still counts there) first, then the competing hold naming 99214 alone."""
        R = _office().build()
        plain = run(R, ('99213', 1), ('99214', 1), ('99215', 1), member=AS.MemberContext())
        members = members_of(plain)
        keys = {p.code: p.key for p in plain.codes}
        without = AS.compete_without(plain.combination, members, {keys['99215']}, dated(R))
        for code, rival in (('99213', '99214'), ('99214', '99213')):
            with self.subTest(code=code):
                held = without.held[keys[code]]
                self.assertEqual([found.cause for found in held], ['coding_rule:base_included', COMPETING])
                self.assertEqual(held[0], plain.combination.held[keys[code]][0])
                self.assertEqual(held[1], CO.competing_hold(without.contested[keys[code]], dated(R)))
                self.assertEqual(without.competes[keys[code]], (rival,))


# The scenes D260 moves, each assessed with a member's answer to 43249's item as asked: (name, the settled inventory's
# builder, the codes proposed). Scene 677 first.
D260_SCENES = (
    ('scene 677', egd_dilation, (('43249', 2), ('43248', 2))),
    ('no rival left', egd_dilation, (('43249', 2), ('43213', 2))),
    ('a rival left', egd_dilation, (('43249', 2), ('43248', 2), ('43233', 2))),
    ('a synthetic act', synthetic_rivals, SYNTHETIC_CODES),
)
ANSWERS = ('not_documented', 'cannot_confirm')


class ReadTimeAgreementTests(SimpleTestCase):
    """The pin of the seam check's scene 677 (DECISIONS D260: "the stored record and read time then agree, and scene
    677 becomes a pin"): test_assess's egd_dilation, 43249 and 43248 proposed, a member's answer to 43249's technique
    read at assess - each answer. 43248's status, item and question are equal at assess and at read time: the record
    persisted as the renderer persists it (tests/v2/test_overlay.persist), read by overlay.review_view with no decision,
    and by the read-time engine (overlay.recount over the engine's own counted codes). The same holds for every scene
    D260 moves (D260_SCENES) and every code in it."""

    @staticmethod
    def case(build, codes, value):
        from tests.v2 import test_overlay as TO  # imported here: test_overlay imports this module

        held = by_code(run(build().build(), *codes))['43249']
        return TO.Case(build().build(), *codes, answers=(answer(held, value=value),))

    def test_scene_677_read_time_shows_assesss_status_and_question(self):
        """With no decision the view of 43248 is its stored proposal: assess's status, the question the renderer words
        from assess's item (jobs.word_item over the Assessment's combination, D246) stored and shown, nothing
        recomputed, stale, added or released; 43249 reads detail unavailable with its answer. Then every code of every
        scene D260 moves, each answer: the view's status and questions are the stored ones, nothing recomputed or
        stale."""
        from studio import jobs
        from studio.interpretation import overlay

        name, build, codes = D260_SCENES[0]
        for value in ANSWERS:
            with self.subTest(scene=name, value=value):
                case = self.case(build, codes, value)
                assessed = by_code(case.assessment)['43248']
                rows = {row.code: row for row in case.rows}
                views = case.views()
                spec = jobs.word_item(assessed.item, assessed.key, case.assessment.combination, case.R, TEXT,
                                      family=AS.family_slug(assessed.family))
                worded = [(spec.fact, spec.question, spec.reason)]
                view = views[rows['43248'].key]
                self.assertEqual(view.status, assessed.status.value)
                self.assertEqual([(q['fact'], q['question'], q['reason']) for q in rows['43248'].questions], worded)
                self.assertEqual([(q['fact'], q['question'], q['reason']) for q in view.questions], worded)
                self.assertEqual((view.recomputed, view.stale, view.added, view.released), ((), (), (), ()))
                gone = views[rows['43249'].key]
                self.assertEqual((gone.status, gone.reason, gone.answer),
                                 ('excluded', overlay.DETAIL_UNAVAILABLE, value))
        for name, build, codes in D260_SCENES:
            for value in ANSWERS:
                case = self.case(build, codes, value)
                views = case.views()
                for row in case.rows:
                    with self.subTest(scene=name, value=value, code=row.code):
                        view = views[row.key]
                        self.assertEqual(view.status, row.status)
                        self.assertEqual((view.recomputed, view.stale, view.added, view.released), ((), (), (), ()))
                        if row.code != '43249':
                            self.assertEqual(view.questions, row.questions)

    def test_scene_677_the_read_time_engine_reproduces_assess(self):
        """The read-time engine over the engine's own counted codes reproduces 43248's held facts and item exactly - and
        every selected code's in every scene D260 moves, each answer - and both of its combinations are the
        Assessment's: read time reads the competition without the codes the engine excluded by a "Not documented"
        answer, through engine/assess.compete_without, which reads the synthetic acts' claims too (the step's NOTES,
        request R1; without it the stored record is not reproduced and read time recomputes nothing, fail-closed)."""
        from studio.interpretation import overlay

        for name, build, codes in D260_SCENES:
            for value in ANSWERS:
                with self.subTest(scene=name, value=value):
                    case = self.case(build, codes, value)
                    try:
                        found = case.recount()
                    except overlay.RecordMismatch as exc:
                        self.fail(f'read time does not reproduce the stored record ({exc}): request R1 of step 5a '
                                  '(w8r)')
                    for assessed in case.assessment.codes:
                        if assessed.bucket is not AS.Bucket.SELECTED:
                            continue
                        live = found.live[assessed.key]
                        self.assertEqual((live.item, live.held, live.holds),
                                         (assessed.item, assessed.held_facts,
                                          case.assessment.combination.held[assessed.key]), assessed.code)
                        self.assertEqual((live.moved, live.added, live.released, live.worded), (False, (), (), None))
                    self.assertEqual((found.joined, found.stored_joined), (case.assessment.combination,) * 2)


# --- refute-5a-r1 P-1 and P-3: a decision on a code another code's answer moved carries while its status is unchanged;
# the answers' passes past the first re-assessment ---


def rendered(assessment: AS.Assessment, R: FactSet) -> dict:
    """Every proposal of ``assessment`` (assessed over ``R`` as ``run`` dates it) as the renderer persists it -
    jobs._render_code, as jobs._render_v2 calls it - and as review's carry reads the stored row, by code."""
    from studio import jobs
    from studio.types import to_jsonable

    out = {}
    for found in assessment.codes:
        p = jobs._render_code(found, combination=assessment.combination, R=dated(R), text=TEXT, pages=(),
                              context_values={}, refs={}, sources=(), day=DAY, active={}, provider='corti')
        out[p.code] = SimpleNamespace(key=p.key, code=p.code, bucket=p.bucket, status=p.status,
                                      profile_version=p.profile_version, family=p.family, units=p.units,
                                      reinstatable=p.reinstatable, fingerprint=p.fingerprint,
                                      evidence=to_jsonable(list(p.evidence)), checks=to_jsonable(list(p.checks)))
    return out


def carried(old, new: dict, action: str = 'reject') -> tuple:
    """(the code of the row a reviewer's ``action`` on the stored row ``old`` carries onto in the rendered assessment
    ``new``, or None; why it does not, as review words it): exactly review._carry_decisions' carry - its candidates by
    fingerprint, then review._carry_target - under one engine."""
    from studio import review

    made = SimpleNamespace(action=action, proposal_fingerprint=old.fingerprint)
    rows = list(new.values())
    candidates = [row for row in rows if row.fingerprint == made.proposal_fingerprint]
    target, problem = review._carry_target(made, old, candidates, rows, True)
    return (target.code if target is not None else None), problem


class DecisionCarryTests(SimpleTestCase):
    """refute-5a-r1 P-1 (the installed release's rule, studio/validation/engine.py, refutation cycle 4, answers 1;
    AMENDMENT-1 6.4: a change the fingerprint does not carry keeps the decision): a code the answers' passes assess
    again - another code's answer moved its competition or its ADDON row - keeps the fingerprint it has without the
    answers while its status is unchanged, so a reviewer's decision on it carries across the AGAIN recompute that reads
    the answer, and back when the answer is withdrawn; a code whose status moves takes the fingerprint of what it now
    is, and a decision made on the other status is cleared naming the status. Carried as review carries it, over the
    rows the renderer persists."""

    def test_a_decision_on_the_rival_scene_677_releases_carries_both_ways(self):
        """Scene 677: a reviewer rejects 43248 on the assessment without the answer; the AGAIN recompute reads the
        member's "Not documented" to 43249's technique and releases 43248's competing hold - and nothing it shows: it
        still needs clarification on its technique question. The rejection carries onto it, and one made after the
        answer carries back once the answer is withdrawn. "Cannot confirm" moves nothing of 43248's: it carries. The
        answered 43249 itself moves to the excluded list: a decision on it never carries. (Before this repair the
        rejection was cleared as "depends on a context value that changed", which no context value had.)"""
        R = egd_dilation().build()
        codes = (('43249', 2), ('43248', 2))
        plain = run(R, *codes)
        for value in ANSWERS:
            with self.subTest(value=value):
                again = run(R, *codes, answers=(answer(by_code(plain)['43249'], value=value),))
                one, two = rendered(plain, R), rendered(again, R)
                self.assertEqual((one['43248'].status, two['43248'].status), ('needs_clarification',) * 2)
                self.assertEqual(carried(one['43248'], two), ('43248', ''))
                self.assertEqual(carried(two['43248'], one), ('43248', ''))  # the answer withdrawn
                self.assertEqual(carried(one['43249'], two),
                                 (None, 'the list of 43249 changed from selected to excluded'))

    def test_a_decision_on_a_rival_whose_status_moves_is_cleared_naming_the_status(self):
        """43213 beside 43249, held by the competition alone: "Not documented" on 43249's technique releases it to
        READY, so it takes the fingerprint 43213 proposed alone has, and a rejection made without the answer is cleared
        naming the status that changed, as the installed release clears it; an approval made on READY is cleared the
        same way once the answer is withdrawn. "Cannot confirm" leaves it held: the decision carries."""
        R = egd_dilation().build()
        codes = (('43249', 2), ('43213', 2))
        plain = run(R, *codes)
        again = run(R, *codes, answers=(answer(by_code(plain)['43249']),))
        released = by_code(again)['43213']
        self.assertEqual(released.status, Outcome.READY)
        self.assertEqual(released.fingerprint, by_code(run(R, ('43213', 2)))['43213'].fingerprint)
        self.assertNotEqual(released.fingerprint, by_code(plain)['43213'].fingerprint)
        one, two = rendered(plain, R), rendered(again, R)
        self.assertEqual(carried(one['43213'], two),
                         (None, 'the status of 43213 changed from Needs clarification to Ready for review'))
        self.assertEqual(carried(two['43213'], one, action='approve'),
                         (None, 'the status of 43213 changed from Ready for review to Needs clarification'))
        kept = rendered(run(R, *codes, answers=(answer(by_code(plain)['43249'], value='cannot_confirm'),)), R)
        self.assertEqual(carried(one['43213'], kept), ('43213', ''))

    def test_every_code_a_pass_assesses_again_keeps_its_fingerprint_while_its_status_holds(self):
        """Every selected code no answer excluded, in every scene D260 moves and in the chain of passes (em_chain), each
        answer: the fingerprint it has without the answers while its status is unchanged, another once its status
        moved - whatever else the passes moved (its held facts, its rivals, its item: 99417's below)."""
        scenes = [(name, build, codes, (('43249', value),)) for name, build, codes in D260_SCENES for value in ANSWERS]
        scenes += [('em_chain', em_chain, CHAIN, (('99215', 'not_documented'),))]
        for name, build, codes, given in scenes:
            R = build().build()
            plain = by_code(run(R, *codes))
            found = run(R, *codes, answers=tuple(answer(plain[code], value=value, answer_id=f'a{index}')
                                                 for index, (code, value) in enumerate(given)))
            moved = 0
            for p in found.codes:
                if p.answered is not None or p.bucket is not AS.Bucket.SELECTED:
                    continue
                with self.subTest(scene=name, answers=given, code=p.code):
                    before = plain[p.code]
                    moved += outcome_of(p) != outcome_of(before)
                    if p.status is before.status:
                        self.assertEqual(p.fingerprint, before.fingerprint)
                    else:
                        self.assertNotEqual(p.fingerprint, before.fingerprint)
            if given[-1][1] == 'not_documented':  # a scene whose passes move nothing proves nothing here
                with self.subTest(scene=name, answers=given):
                    self.assertGreater(moved, 0)


def em_chain() -> EF.Doc:
    """An office visit X1 (this encounter): the visit E1, its basis unresolved (em_basis, rank 19), its prolonged time
    E2, and an unlisted act of no kind carded X1 (units 900 .. 960). D231 row 5: every counted code of the visit may
    account for that act, so they all compete for it, and an E/M code beside it asks its date relation first
    (event_time, rank 6, an item the engine reads)."""
    doc = EF.Doc()
    doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT, basis=EF.unres(ct.EmBasis.TOTAL_TIME))
    doc.act(2, Kind.EM_PROLONGED)
    doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.ACT, None, X(1), Span(900, 960)))
    return doc


# 99215 (99417's primary), 99417 (its add-on) and 99214 in em_chain.
CHAIN = (('99215', 1), ('99417', 2), ('99214', 1))


class AnswerPassTests(SimpleTestCase):
    """The answers' passes past the first re-assessment (refute-5a-r1 P-3: no test reached them, so a loop stopping
    after one pass survived every target): a chain the catalogue's codes reach (em_chain), each pass's codes assessed
    again, the answers bound again over them, the last pass's competition the Assessment's."""

    def test_a_chain_of_two_passes_releases_the_last_rival(self):
        """99215, 99417 and 99214 compete for the unlisted act and each asks the date relation. A1, "Not documented" to
        99215's item, excludes 99215. The first pass reads 99417's ADDON row without its primary - 99417 is held by the
        row and asks it, a new item (performed_status, rank 4), keeping its fingerprint (its status held) - and the
        competition without 99215: 99214 and 99417 compete with each other alone. A2, an answer to 99417's new item
        (alone it binds nothing: that item is not asked without A1), binds only on the re-binding and excludes 99417;
        "Not documented" takes it out of the competition too, so a SECOND pass releases 99214's competing hold - no
        rival left, its item, status and fingerprint those it has without the answers. "Cannot confirm" leaves 99417 in
        the competition: 99214 keeps its hold, naming 99417 alone."""
        R = em_chain().build()
        plain = run(R, *CHAIN)
        before = by_code(plain)
        self.assertEqual({code: (p.status, p.item.held.fact, p.competes) for code, p in before.items()},
                         {'99215': (Outcome.NEEDS_CLARIFICATION, 'event_time', ('99214', '99417')),
                          '99417': (Outcome.NEEDS_CLARIFICATION, 'event_time', ('99215', '99214')),
                          '99214': (Outcome.NEEDS_CLARIFICATION, 'event_time', ('99215', '99417'))})
        a1 = answer(before['99215'])
        asked = by_code(run(R, ('99417', 2), ('99214', 1)))['99417']  # 99417's item with no primary counted
        self.assertEqual((asked.item.held.fact, asked.item.held.cause), ('performed_status', AS.ADDON_CAUSE))
        lone = run(R, *CHAIN, answers=(answer(asked, answer_id='a2'),))
        self.assertEqual([(item.answer, item.why) for item in lone.earlier_answers],
                         [('a2', AS.Unbound.NO_LONGER_ASKED)])
        self.assertEqual(lone.codes, plain.codes)
        first = by_code(run(R, *CHAIN, answers=(a1,)))
        addon = first['99417']
        self.assertEqual((addon.status, addon.item, addon.question, addon.competes),
                         (Outcome.NEEDS_CLARIFICATION, asked.item, asked.question, ('99214',)))
        self.assertEqual(addon.fingerprint, before['99417'].fingerprint)
        self.assertEqual((first['99214'].competes, first['99214'].fingerprint),
                         (('99417',), before['99214'].fingerprint))
        for value, rivals in (('not_documented', ()), ('cannot_confirm', ('99417',))):
            with self.subTest(value=value):
                found = run(R, *CHAIN, answers=(a1, answer(asked, value=value, answer_id='a2')))
                after = by_code(found)
                self.assertEqual([(item.answer, item.code) for item in found.answers],
                                 [('a1', '99215'), ('a2', '99417')])
                self.assertEqual(found.earlier_answers, ())
                self.assertEqual((after['99417'].status, after['99417'].answered),
                                 (Outcome.EXCLUDED, AS.Answered('performed_status', AS.Answer(value), ('a2',))))
                self.assertEqual((after['99417'].item, after['99417'].question), (asked.item, asked.question))
                left = after['99214']
                self.assertEqual((left.status, left.item, left.question, left.fingerprint),
                                 (Outcome.NEEDS_CLARIFICATION, before['99214'].item, before['99214'].question,
                                  before['99214'].fingerprint))
                self.assertEqual((left.competes, found.combination.competes.get(left.key)), (rivals, rivals or None))
                self.assertEqual([cause for _, cause in facts_of(left)].count(COMPETING), 1 if rivals else 0)
                self.assertEqual([held.cause for held in found.combination.held[left.key]].count(COMPETING),
                                 1 if rivals else 0)


# --- DECISIONS D283's assess half (G1-02, G1-03 with C7's correction): one implementation of the answers' passes -----


class D279SessionViewTests(SimpleTestCase):
    """refute-f3e-r1 F1 (critical; AMENDMENT-2 4.3.3 a and 4.4 [R:truth-T1]), through engine/assess: an EGD X1 (its
    examination E1 done today, the second portion of the duodenum reached) beside an upper EUS X2 whose only examination
    E2 is done today, E2's session slot overfilled with X1 written stated and X1 written denied. Read alone, the denial
    leaves E2 possibly in the EUS and holds 43235 within it (base_within); the statement alone places E2 in the EGD and
    leaves 43235 READY. As built the view carried X1 in its options and nothing in negated_values, so every possibility
    reader read it as the statement alone: 43235 READY beside a same-day EUS - a false READY, since the true reading
    (E2 in X2) holds it. Each possibility reader now reads every view as a written denial (facts.open_denial; the step's
    NOTES question Q1R), so the view holds 43235 as the denial does: never stronger than a written fact read alone."""

    def assess(self, e2_session: Fact) -> object:
        doc = EF.Doc()
        doc.session(1, SessionKind.EGD, tract=sup(ct.Tract.UPPER), reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)])
        doc.session(2, SessionKind.EUS, tract=sup(ct.Tract.UPPER))
        doc.exam(1, device=sup(ct.Device.ENDOSCOPE))
        doc.exam(2, session=e2_session, device=sup(ct.Device.ENDOSCOPE))
        return by_code(run(doc.build(), ('43235', 1)))['43235']

    def test_a_view_of_one_session_written_both_ways_holds_43235_within_the_eus(self):
        within = ('base_included', CO.WITHIN_CAUSE)

        def view(*written):
            return Fact(ct.Result.UNRESOLVED, None, ct.FactState.CONTRADICTED, tuple(dict.fromkeys(v for _s, v in written)),
                        (ct.Reason.SLOT_OVERFULL,), (EF.unit(2),))  # nothing only denied: negated_values empty

        S_, N_ = ct.FactState.SUPPORTED, ct.FactState.NEGATED
        for name, e2_session, held in (
                ('the true reading: E2 in X2', sup(X(2)), within),
                ('the denial read alone', Fact(ct.Result.UNRESOLVED, X(1), N_, (), (ct.Reason.SLOT_OVERFULL,),
                                               (EF.unit(2),)), within),
                ('the statement read alone', Fact(ct.Result.UNRESOLVED, X(1), S_, (), (ct.Reason.SLOT_OVERFULL,),
                                                  (EF.unit(2),)), None),
                ('the view of X1 stated and X1 denied', view((S_, X(1)), (N_, X(1))), within),
                ('the view of X1 denied and X1 stated', view((N_, X(1)), (S_, X(1))), within)):
            with self.subTest(name):
                found = self.assess(e2_session)
                if held is None:
                    self.assertEqual((found.status, found.item), (Outcome.READY, None))
                else:
                    self.assertEqual(found.status, Outcome.NEEDS_CLARIFICATION)
                    self.assertEqual((found.item.held.fact, found.item.held.cause), held)


class D286AddOnReadTimeTests(SimpleTestCase):
    """DECISIONS D286 ruling E (G3-12), B12's overlay pin: an act of a kind a COUNTED add-on covers, and no non-add-on code
    of the family, is accounted by that add-on - so the read-time engine, which counts what the reviewer keeps, holds
    43260 base_included again once 43273 is rejected (the unlisted cholangioscopy read by base rule (c), as without the
    add-on), and keeps it free of that hold while 43273 is kept."""

    def test_with_43273_rejected_43260_is_held_base_included(self):
        from studio.interpretation import overlay
        from tests.v2 import test_overlay as TO  # imported here: test_overlay imports this module

        built = EF.Doc()
        built.session(1, SessionKind.ERCP)
        built.exam(1)
        built.act(2, Kind.CANNULATION, access=EF.sup(ct.AccessOutcome.ACHIEVED), duct=EF.sup(ct.Duct.BILIARY))
        built.act(3, Kind.CHOLANGIOSCOPY, duct=EF.sup(ct.Duct.BILIARY))
        built.unlisted.append(EF.unlisted(ct.UnlistedWhat.ACT, Kind.CHOLANGIOSCOPY, EF.X(1), Span(900, 940)))
        case = TO.Case(built.build(), ('43260', 1), ('43273', 3))
        self.assertEqual({p.code: p.status for p in case.assessment.codes},
                         {'43260': Outcome.READY, '43273': Outcome.READY})
        keys = {row.code: row.key for row in case.rows}
        kept = case.recount()
        rejected = case.recount(counted=[key for key in case.engine_keys if key != keys['43273']])
        self.assertIsInstance(rejected, overlay.Recount)
        self.assertNotIn(CO.BASE_CAUSE, [held.cause for held in kept.joined.held.get(keys['43260'], ())])
        self.assertIn(CO.BASE_CAUSE, [held.cause for held in rejected.joined.held.get(keys['43260'], ())])


class D283AnswerPasses(SimpleTestCase):
    """DECISIONS D283 items 1-2 (refute-5a-r1 P-1, P-4; refute-5c-r1 P4-P6; refute-consistency C7): in each pass of the
    answers the ADDON count leaves out every code an engine-read answer excluded and every primary an overlay-bound
    answer of either value binds (accumulated); the competition leaves out every code an overlay-bound "Not documented"
    binds in that pass (recomputed); a code whose ADDON row the pass moves is read again, and its answer binds only the
    item it then presents - an answer that no longer binds is recorded no longer asked. engine/assess.answer_pass and
    read_again are that rule, the one implementation read time calls too (step f6's half)."""

    def test_answer_pass_and_read_again_are_the_rule(self):
        nd, cc = AS.Answer.NOT_DOCUMENTED, AS.Answer.CANNOT_CONFIRM
        first = AS.answer_pass({'k1': nd}, {'k2': cc, 'k3': nd})
        self.assertEqual((first.out, first.withdrawn, first.uncounted),
                         (frozenset({'k1', 'k3'}), frozenset({'k3'}), frozenset({'k1', 'k2', 'k3'})))
        second = AS.answer_pass({'k1': nd}, {'k2': cc}, first)  # k3's answer binds no more: back in the competition
        self.assertEqual((second.out, second.withdrawn, second.uncounted),
                         (frozenset({'k1'}), frozenset(), frozenset({'k1', 'k2', 'k3'})))  # uncounted accumulates
        self.assertFalse(AS.read_again('k1', first, excluded=True, competition_moved=True, addon_moved=True))
        self.assertFalse(AS.read_again('k3', first, excluded=False, competition_moved=True, addon_moved=False))
        self.assertTrue(AS.read_again('k3', first, excluded=False, competition_moved=False, addon_moved=True))
        self.assertTrue(AS.read_again('k2', first, excluded=False, competition_moved=True, addon_moved=False))
        self.assertFalse(AS.read_again('k2', first, excluded=False, competition_moved=False, addon_moved=False))

    def test_g1_02_a_taken_add_on_whose_addon_row_moves_is_read_again(self):
        """G1-02 (S2, I2's residual): em_chain, a1 "Not documented" to 99215's item as asked (engine-read: 99215
        excluded) and a2 "Not documented" to 99417's item with no fingerprint (overlay-read). 99417 is read again once
        its ADDON row moves: its item is the ADDON row's (performed_status, coding_rule:ADDON), a2 binds nothing and is
        recorded no longer asked, and 99417 is back in the competition with 99214 (as built: 99417 frozen with its
        event_time item and out of the competition, 99214 alone)."""
        R = em_chain().build()
        before = by_code(run(R, *CHAIN))
        a1, a2 = answer(before['99215']), answer(before['99417'], question='', answer_id='a2')
        found = run(R, *CHAIN, answers=(a1, a2))
        after = by_code(found)
        self.assertEqual((after['99417'].status, after['99417'].item.held.fact, after['99417'].item.held.cause,
                          after['99417'].competes), (Outcome.NEEDS_CLARIFICATION, 'performed_status', AS.ADDON_CAUSE,
                                                     ('99214',)))
        self.assertEqual(after['99214'].competes, ('99417',))
        self.assertEqual([(item.answer, item.code) for item in found.answers], [('a1', '99215')])
        self.assertEqual([(item.answer, item.code, item.why) for item in found.earlier_answers],
                         [('a2', '99417', AS.Unbound.NO_LONGER_ASKED)])

    def test_g1_03_an_overlay_bound_answer_on_the_only_primary_holds_the_add_on(self):
        """G1-03 (S3; 5a Q3 option (b), both values): office_prolonged (99215, 99214, 99417), "Not documented" or
        "Cannot confirm" to 99215's base question (overlay-bound): 99215 is not counted for ADDON, so 99417 is held by its
        ADDON row (as built READY, an add-on approvable with no counted primary); without the answer 99417 is READY."""
        R = office_prolonged().build()
        codes = (('99215', 1), ('99214', 1), ('99417', 2))
        plain = by_code(run(R, *codes, member=ENTERED))
        self.assertEqual((plain['99417'].status, plain['99215'].item.held.fact), (Outcome.READY, 'base_included'))
        for value in ('not_documented', 'cannot_confirm'):
            with self.subTest(value=value):
                found = run(R, *codes, member=ENTERED, answers=(answer(plain['99215'], value=value),))
                addon = by_code(found)['99417']
                self.assertEqual((addon.status, addon.item.held.fact, addon.item.held.cause),
                                 (Outcome.NEEDS_CLARIFICATION, 'performed_status', AS.ADDON_CAUSE))
                self.assertEqual([item.why for item in found.earlier_answers], [AS.Unbound.OVERLAY_READ])

    def test_c7_an_office_visit_its_prolonged_time_and_a_sigmoidoscopy(self):
        """C7's scene: an office visit, its prolonged time and a same-day flexible sigmoidoscopy; 99215, 99417, 45330;
        "Not documented" to both separate_em items (overlay-bound). 99215's answer uncounts it for ADDON, so 99417's row
        moves: 99417 is read again, its item the ADDON row's, and its own separate_em answer binds nothing - recorded no
        longer asked, as read time lists it (as built on g1's prototype read time read 99417 detail unavailable by that
        answer while the record held it)."""
        doc = office_and_sigmoidoscopy()
        doc.act(3, Kind.EM_PROLONGED, session=X(1))
        R = doc.build()
        codes = (('99215', 1), ('99417', 3), ('45330', 2))
        plain = by_code(run(R, *codes, member=ENTERED))
        self.assertEqual({code: p.item.held.fact if p.item else None for code, p in plain.items()},
                         {'99215': 'separate_em', '99417': 'separate_em', '45330': None})
        given = (answer(plain['99215'], answer_id='a1'), answer(plain['99417'], answer_id='a2'))
        found = run(R, *codes, member=ENTERED, answers=given)
        after = by_code(found)
        self.assertEqual((after['99417'].status, after['99417'].item.held.cause),
                         (Outcome.NEEDS_CLARIFICATION, AS.ADDON_CAUSE))
        self.assertEqual(after['45330'].status, Outcome.READY)
        self.assertEqual([(item.answer, item.why) for item in found.earlier_answers],
                         [('a1', AS.Unbound.OVERLAY_READ), ('a2', AS.Unbound.NO_LONGER_ASKED)])

    def test_the_passes_end_on_every_answer_combination(self):
        """AnswerPassTests' termination over D283's scenes: every subset of the codes' items answered, either value, as
        asked or with no fingerprint, on em_chain, office_prolonged and C7's scene - the passes end, every answer is
        recorded exactly once (applied or not), and no code is assessed again more often than there are answers and
        codes (each pass needs a newly excluded or uncounted code)."""
        doc = office_and_sigmoidoscopy()
        doc.act(3, Kind.EM_PROLONGED, session=X(1))
        scenes = ((em_chain().build(), CHAIN, AS.MemberContext()),
                  (office_prolonged().build(), (('99215', 1), ('99214', 1), ('99417', 2)), ENTERED),
                  (doc.build(), (('99215', 1), ('99417', 3), ('45330', 2)), ENTERED))
        runs = 0
        for R, codes, member in scenes:
            plain = by_code(run(R, *codes, member=member))
            asked = [p for p in plain.values() if p.item is not None]
            for size in range(1, len(asked) + 1):
                for chosen in itertools.combinations(asked, size):
                    for value in ('not_documented', 'cannot_confirm'):
                        for question in (None, ''):
                            given = tuple(answer(p, value=value, question=question, answer_id=f'a{index}')
                                          for index, p in enumerate(chosen))
                            with mock.patch.object(AS, '_assessed', wraps=AS._assessed) as again:
                                found = run(R, *codes, member=member, answers=given)
                            recorded = [item.answer for item in found.answers] + [
                                item.answer for item in found.earlier_answers]
                            self.assertEqual(sorted(recorded), sorted(item.answer_id for item in given))
                            self.assertLessEqual(again.call_count, len(codes) * (len(given) + 2))
                            runs += 1
        self.assertGreater(runs, 40)


# --- DECISIONS D270 (DQ-2): an overlay-bound "Not documented" read at assess for the competition alone, as read time
# reads it (repair round w9r's step 5a) ---


# refute-5a-r2 DQ-2's input: an office visit beside a same-day flexible sigmoidoscopy; 99213 and 99214 compete for the
# one visit, each asking the separately identifiable visit (separate_em, key-bound: the overlay's), and 45330 is READY.
OFFICE_DAY = (('99213', 1), ('99214', 1), ('45330', 2))


def stored_fingerprints(assessment: AS.Assessment, R: FactSet) -> dict:
    """{member key (code, family, fact): fingerprint} of the item every proposal of ``assessment`` (assessed over ``R``
    as ``run`` dates it) stores, as the renderer persists it (jobs._render_code: support['item'] and
    support['question']) and review reads it (review.stored_questions; DECISIONS D259): what read time binds a member's
    answer by, with no decision."""
    from studio import jobs, review

    rows = [jobs._render_code(found, combination=assessment.combination, R=dated(R), text=TEXT, pages=(),
                              context_values={}, refs={}, sources=(), day=DAY, active={}, provider='corti')
            for found in assessment.codes]
    proposals = [SimpleNamespace(position=index, support=p.support, bucket=p.bucket, code=p.code, family=p.family)
                 for index, p in enumerate(rows)]
    return review.stored_questions(SimpleNamespace(engine_version=ENGINE_VERSION_V2), proposals)


def read_time(build, codes, given, member: AS.MemberContext = ENTERED, answered=()):
    """Read time over the record of ``codes`` made with the answers ``answered`` (none: the record made before
    ``given``), with ``given`` standing and no decision: (the keys read time takes out of the competition, the live
    records of the read-time engine with them out - None over a record made with answers -, the views). The answers
    review binds - validation questions.bind over the stored item fingerprints, as review.answer_states binds them
    (key-bound facts by their key) - are applied by overlay.review_view, which reads a code whose stored question one
    names "Not documented" detail unavailable and out of the competition (DECISIONS D249); overlay.recount gives the
    engine's live records with those codes out. (Over a record made with an overlay-bound answer the read-time engine
    reproduces the stored record only with step 5c's half of D270, DQ-2's restore: this step's NOTES, request R1.)"""
    from studio.interpretation import overlay
    from studio.validation import questions as VQ
    from tests.v2 import test_overlay as TO  # imported here: test_overlay imports this module

    case = TO.Case(build().build(), *codes, member=member, answers=tuple(answered))
    bound, _ = VQ.bind(given, stored_fingerprints(case.assessment, build().build()))
    views = case.views(answers=[{'code': item.code, 'family': item.family, 'fact': item.fact, 'value': item.value}
                                for item in bound])
    out = {row.key for row in case.rows if views[row.key].reason == overlay.DETAIL_UNAVAILABLE
           and views[row.key].answer == 'not_documented' and not overlay.answered_by_engine(row)[0]}
    if answered:
        return out, None, views
    # DECISIONS D283 item 3: every recount that reproduces a record reads the codes assess left out of its ADDON
    # count, derived from the stored record by one function (overlay.assessed_uncounted)
    found = overlay.recount(case.rows, case.engine_keys, case.engine_keys, case.coding, case.R, member=case.member,
                            out_of_competition=out,
                            uncounted=overlay.assessed_uncounted(case.completeness, case.rows))
    return out, found.live, views


def taken_out(found: AS.Assessment, given) -> set:
    """The keys engine/assess took out of the competition in ``found`` (assessed with ``given``): the codes an answer it
    applied excluded "Not documented" (D260) and the selected codes an overlay-bound "Not documented" binds (D270)."""
    engine = {p.key for p in found.codes if p.answered is not None and p.answered.value is AS.Answer.NOT_DOCUMENTED}
    pairs = [(item, AS.Answer(item.value)) for item in given]
    return engine | {key for key, value in AS.overlay_bound(found.codes, pairs).items()
                     if value is AS.Answer.NOT_DOCUMENTED}


class OverlayAnswerTests(SimpleTestCase):
    """DECISIONS D270, DQ-2 option (b) (refute-5a-r2 DQ-2; 5a-2 Q2; TRIAGE G2-10): engine/assess reads an overlay-bound
    "Not documented" - a member's answer the engine does not apply, bound to the code's item by key as read time binds
    it - for the competition alone, as D260 reads an engine-bound one: the code leaves the competition, so a rival with
    no rival left loses its competing hold and one with a rival left names only the rivals left; the answered code keeps
    the record its answer found (never assessed again: read time binds the answer to the same item), it is never
    excluded here (read time reads it detail unavailable) and the answer stays recorded as the overlay's. So the stored
    record and read time agree: what assess takes out of the competition is what read time takes out over the record
    made before the answer, and the rivals' records are read time's live ones."""

    def test_dq2_a_not_documented_to_99214s_separate_em_releases_99213s_competing_hold_as_at_read_time(self):
        """refute-5a-r2 DQ-2's input (its probe c05): "Not documented" to 99214's separate_em question as asked. Before
        D270 assess kept 99213's competing hold naming 99214 while read time released it with no decision. Now 99213's
        competing hold naming 99214 is released at assess - its competes empty, the Assessment's combination naming no
        rival for it - and 99213 keeps separate_em: still held, its item, question, considerations and fingerprint
        unchanged (its status held), its held facts those without the competing hold. 99214 keeps the record its answer
        found and 45330 is untouched; the answer stays recorded as read by the overlay, never applied here. As at read
        time: over the record made before the answer read time takes 99214 out and releases exactly that hold
        (overlay.recount's live record of 99213 is assess's new one); over the record made with it, 99213's view is
        that record - nothing released, recomputed or stale - and 99214 reads detail unavailable."""
        from studio.interpretation import overlay

        R = office_and_sigmoidoscopy().build()
        plain = run(R, *OFFICE_DAY)
        before = by_code(plain)
        for code, rival in (('99213', '99214'), ('99214', '99213')):
            self.assertEqual((before[code].status, before[code].item.held.fact, before[code].competes),
                             (Outcome.NEEDS_CLARIFICATION, 'separate_em', (rival,)))
            self.assertEqual([fact for fact, _ in facts_of(before[code])],
                             ['separate_em', 'base_included', 'competing_codes'])
        given = answer(before['99214'])
        self.assertFalse(AS.engine_reads(given))  # a key-bound fact: the read-time overlay's (v1's engine_reads)
        found = run(R, *OFFICE_DAY, answers=(given,))
        after = by_code(found)
        kept = after['99213']
        self.assertEqual(kept.competes, ())
        self.assertNotIn(kept.key, found.combination.competes)
        self.assertEqual([held.cause for held in found.combination.held[kept.key]].count(COMPETING), 0)
        self.assertEqual(kept.held_facts, tuple(held for held in before['99213'].held_facts if held.cause != COMPETING))
        self.assertEqual([fact for fact, _ in facts_of(kept)], ['separate_em', 'base_included'])
        self.assertEqual((kept.status, kept.item, kept.question, kept.considerations, kept.fingerprint),
                         (Outcome.NEEDS_CLARIFICATION, before['99213'].item, before['99213'].question,
                          before['99213'].considerations, before['99213'].fingerprint))
        self.assertEqual((kept.item.held.fact, kept.item.held.cause), ('separate_em', 'coding_rule:same_day_em'))
        self.assertEqual(after['99214'], before['99214'])
        self.assertEqual(after['45330'], before['45330'])
        self.assertEqual(found.answers, ())
        self.assertEqual([(item.answer, item.code, item.why) for item in found.earlier_answers],
                         [('a1', '99214', AS.Unbound.OVERLAY_READ)])
        # read time over the record made before the answer: it binds the answer (by its key) and releases the hold
        out, live, views = read_time(office_and_sigmoidoscopy, OFFICE_DAY, (given,))
        self.assertEqual(out, {before['99214'].key})
        self.assertEqual((live[kept.key].held, live[kept.key].item), (kept.held_facts, kept.item))
        self.assertEqual((views[kept.key].released, views[kept.key].recomputed),
                         (('competing_codes',), ('proposals.competing',)))
        # read time over the record made with it: the stored record stands as assess wrote it
        _, _, views = read_time(office_and_sigmoidoscopy, OFFICE_DAY, (given,), answered=(given,))
        view = views[kept.key]
        self.assertEqual((view.status, [q['fact'] for q in view.questions]), ('needs_clarification', ['separate_em']))
        self.assertEqual((view.released, view.recomputed, view.stale, view.added), ((), (), (), ()))
        gone = views[after['99214'].key]
        self.assertEqual((gone.status, gone.reason, gone.answer), ('excluded', overlay.DETAIL_UNAVAILABLE,
                                                                    'not_documented'))

    def test_dq2_control_with_no_answer_the_competing_hold_stays(self):
        """The control: with no answer 99213 keeps its competing hold naming 99214 (its competes, its last held fact and
        the Assessment's combination), overlay_bound binds nothing, and read time releases nothing. An answer that is
        not "Not documented" - "Cannot confirm" to the same question - moves nothing either (D260's reading)."""
        R = office_and_sigmoidoscopy().build()
        plain = run(R, *OFFICE_DAY)
        found = by_code(plain)
        held = found['99213']
        self.assertEqual((held.status, held.competes), (Outcome.NEEDS_CLARIFICATION, ('99214',)))
        self.assertEqual(facts_of(held)[-1], ('competing_codes', COMPETING))
        self.assertEqual(plain.combination.competes[held.key], ('99214',))
        self.assertEqual(AS.overlay_bound(plain.codes, ()), {})
        out, live, views = read_time(office_and_sigmoidoscopy, OFFICE_DAY, ())
        self.assertEqual(out, set())
        self.assertEqual((live[held.key].held, views[held.key].released, views[held.key].recomputed),
                         (held.held_facts, (), ()))
        unavailable = answer(found['99214'], value='cannot_confirm')
        confirmed = run(R, *OFFICE_DAY, answers=(unavailable,))
        self.assertEqual((confirmed.codes, confirmed.combination), (plain.codes, plain.combination))
        self.assertEqual([(item.answer, item.why) for item in confirmed.earlier_answers],
                         [('a1', AS.Unbound.OVERLAY_READ)])
        out, live, views = read_time(office_and_sigmoidoscopy, OFFICE_DAY, (unavailable,))
        self.assertEqual(out, set())
        self.assertEqual((live[held.key].held, views[held.key].released), (held.held_facts, ()))

    def test_dq2_assess_binds_an_overlay_answer_as_read_time_binds_it(self):
        """Every way read time binds by key, or does not bind, an answer the engine does not apply (validation
        questions.bind over the item fingerprint the code stores, then the overlay's key): a key-bound fact by its key
        whatever fingerprint it carries (as asked, a pre-v2 one, none); an answer with no fingerprint by its key alone
        (the earlier form; scene 677's technique); never one whose family or fact is not the item's (no longer asked),
        nor "Cannot confirm", nor one to another fact that carries another fingerprint (asked differently: scene 677's
        technique with a pre-v2 fingerprint, which the engine records so; a competing_codes answer). For each, the codes
        assess takes out of the competition are the codes read time takes out over the record made before the answer,
        every code's record at assess is read time's live record, and a code an overlay-bound answer took out keeps the
        record its answer found."""
        def variant(found, **kw):
            fields_ = dict(code=found.code, family=AS.family_slug(found.family), fact=found.item.held.fact,
                           value='not_documented', question=found.question, answer_id='a1')
            fields_.update(kw)
            return MemberAnswerInput(**fields_)

        from tests.v2 import test_overlay as TO  # imported here: test_overlay imports this module

        cases = (
            ('office: as asked', office_and_sigmoidoscopy, OFFICE_DAY, ENTERED, lambda by: (variant(by['99214']),),
             {'99214'}),
            ('office: a pre-v2 fingerprint', office_and_sigmoidoscopy, OFFICE_DAY, ENTERED,
             lambda by: (variant(by['99214'], question='0' * 64),), {'99214'}),
            ('office: no fingerprint', office_and_sigmoidoscopy, OFFICE_DAY, ENTERED,
             lambda by: (variant(by['99214'], question=''),), {'99214'}),
            ('office: to 99213', office_and_sigmoidoscopy, OFFICE_DAY, ENTERED, lambda by: (variant(by['99213']),),
             {'99213'}),
            ('office: another family', office_and_sigmoidoscopy, OFFICE_DAY, ENTERED,
             lambda by: (variant(by['99214'], family='gi.colonoscopy'),), set()),
            ('office: a fact its item does not ask', office_and_sigmoidoscopy, OFFICE_DAY, ENTERED,
             lambda by: (variant(by['99214'], fact='base_included'),), set()),
            ('office: cannot confirm', office_and_sigmoidoscopy, OFFICE_DAY, ENTERED,
             lambda by: (variant(by['99214'], value='cannot_confirm'),), set()),
            ('two visits: base_included', TO.two_visits, (('99213', 1), ('99214', 1)), AS.MemberContext(),
             lambda by: (variant(by['99214']),), {'99214'}),
            ('scene 677: technique with no fingerprint', egd_dilation, (('43249', 2), ('43248', 2)), ENTERED,
             lambda by: (variant(by['43249'], question=''),), {'43249'}),
            ('one dilation: competing_codes asked differently', one_dilation, (('43249', 2), ('43233', 2)), ENTERED,
             lambda by: (variant(by['43233'], question='0' * 64),), set()),
            ('scene 677: technique asked differently', egd_dilation, (('43249', 2), ('43248', 2)), ENTERED,
             lambda by: (variant(by['43249'], question='0' * 64),), set()),
        )
        asked_differently = {'scene 677: technique asked differently'}  # the engine reads it and records it so
        # DECISIONS D283: the competing question's answer is applied by nothing (G1-01), and an overlay-read answer that
        # binds no item a selected code presents is no longer asked, as read time lists it (item 1; questions.bind)
        not_applied = {'one dilation: competing_codes asked differently'}
        no_longer_asked = {'office: another family', 'office: a fact its item does not ask'}
        for name, build, codes, member, make, expected in cases:
            with self.subTest(case=name):
                plain = run(build().build(), *codes, member=member)
                before = by_code(plain)
                given = make(before)
                found = run(build().build(), *codes, member=member, answers=given)
                out, live, _ = read_time(build, codes, given, member=member)
                self.assertEqual({plain.code(key).code for key in out}, expected)
                self.assertEqual(taken_out(found, given), out)
                for p in found.codes:
                    if p.key in out:
                        self.assertEqual(p, before[p.code])  # the answered code: as its answer found it
                    elif p.bucket is AS.Bucket.SELECTED:
                        self.assertEqual((p.held_facts, p.item), (live[p.key].held, live[p.key].item), p.code)
                        self.assertEqual(p.competes, tuple(found.combination.competes.get(p.key, ())))
                if not expected:
                    self.assertEqual(found.codes, plain.codes)
                why = (AS.Unbound.ASKED_DIFFERENTLY if name in asked_differently
                       else AS.Unbound.NOT_APPLIED if name in not_applied
                       else AS.Unbound.NO_LONGER_ASKED if name in no_longer_asked else AS.Unbound.OVERLAY_READ)
                self.assertEqual([(item.answer, item.why) for item in found.earlier_answers], [('a1', why)])

    def test_dq2_with_a_rival_left_the_hold_names_only_the_rivals_left_and_binds_beside_an_applied_answer(self):
        """Three E/M codes for the one visit beside the sigmoidoscopy: "Not documented" to 99214's and 99215's
        separate_em leaves 99213 no rival (its competing hold released); "Not documented" to 99214's and "Cannot
        confirm" to 99215's leaves 99213 competing with 99215 alone - as read time reads both. And beside an answer
        the engine applies: three codes for scene 677's dilation, "Not documented" to 43249's technique as asked
        (applied: 43249 excluded) and to 43248's with no fingerprint (the overlay's: 43248 keeps its record) leaves
        43233 no rival, as read time reads it."""
        office = (('99213', 1), ('99214', 1), ('99215', 1), ('45330', 2))
        plain = by_code(run(office_and_sigmoidoscopy().build(), *office))
        self.assertEqual(plain['99213'].competes, ('99214', '99215'))
        for second, rivals in (('not_documented', ()), ('cannot_confirm', ('99215',))):
            with self.subTest(second=second):
                given = (answer(plain['99214']), answer(plain['99215'], value=second, answer_id='a2'))
                found = run(office_and_sigmoidoscopy().build(), *office, answers=given)
                after = by_code(found)
                out, live, _ = read_time(office_and_sigmoidoscopy, office, given)
                self.assertEqual(taken_out(found, given), out)
                left = after['99213']
                self.assertEqual((left.status, left.item, left.competes),
                                 (Outcome.NEEDS_CLARIFICATION, plain['99213'].item, rivals))
                self.assertEqual((left.held_facts, left.item), (live[left.key].held, live[left.key].item))
                self.assertEqual(after['99214'], plain['99214'])
                self.assertEqual({p.status for p in found.codes if p.bucket is AS.Bucket.EXCLUDED}, set())
        three = (('43249', 2), ('43248', 2), ('43233', 2))
        plain = by_code(run(egd_dilation().build(), *three))
        given = (answer(plain['43249']), answer(plain['43248'], question='', answer_id='a2'))
        found = run(egd_dilation().build(), *three, answers=given)
        after = by_code(found)
        self.assertEqual((after['43249'].status, after['43249'].answered.value), (Outcome.EXCLUDED,
                                                                                  AS.Answer.NOT_DOCUMENTED))
        self.assertEqual(after['43248'], plain['43248'])
        self.assertEqual((after['43233'].competes, [fact for fact, _ in facts_of(after['43233'])]), ((), ['technique']))
        out, live, _ = read_time(egd_dilation, three, given)
        self.assertEqual(taken_out(found, given), out)
        self.assertEqual((after['43233'].held_facts, after['43233'].item),
                         (live[after['43233'].key].held, live[after['43233'].key].item))
        self.assertEqual([(item.answer, item.code) for item in found.answers], [('a1', '43249')])
        self.assertEqual([(item.answer, item.why) for item in found.earlier_answers],
                         [('a2', AS.Unbound.OVERLAY_READ)])

    def test_dq2_an_answer_to_the_competing_question_is_not_read_at_assess(self):
        """The competing question offers no answer (studio/answers.py: codes competing for one act are settled by
        rejecting one, P-ADMIT2), so D270's reading leaves an answer to it out whatever it carries - as asked, or with
        no fingerprint: the assessment is the one made without it (43249 keeps its competing hold naming 43233), the
        answer recorded as applied by nothing (DECISIONS D283, G1-01 option (c), restating this pin's "the overlay's":
        read time binds none to it either - review.answer_states lists it not_applied, F6's half - and the competing
        hold is settled by the reviewer's rejection, D270 DQ-3)."""
        R = one_dilation().build()
        plain = run(R, ('43249', 2), ('43233', 2))
        rivals = by_code(plain)
        self.assertEqual((rivals['43249'].competes, rivals['43233'].item.held.fact), (('43233',), 'competing_codes'))
        for question in (None, ''):
            with self.subTest(question=question):
                given = answer(rivals['43233'], question=question)
                self.assertEqual(AS.overlay_bound(plain.codes, [(given, AS.Answer.NOT_DOCUMENTED)]), {})
                found = run(R, ('43249', 2), ('43233', 2), answers=(given,))
                self.assertEqual((found.codes, found.combination), (plain.codes, plain.combination))
                self.assertEqual([(item.answer, item.why) for item in found.earlier_answers],
                                 [('a1', AS.Unbound.NOT_APPLIED)])  # D283 (G1-01)

    def test_the_key_bound_facts_are_reviews_own(self):
        """The engine's key-bound facts (read without a fingerprint, as read time binds them) are
        studio.validation.questions.KEY_BOUND_FACTS, which questions.bind reads: one rule, two readers."""
        from studio.validation import questions as VQ

        self.assertEqual(AS._KEY_BOUND_FACTS, frozenset(VQ.KEY_BOUND_FACTS))
        self.assertLess(AS._KEY_BOUND_FACTS, AS._OVERLAY_FACTS)
        # and the engine's own rule, requirements.KEY_BOUND (rules_canonical's 'key_bound'): three spellings, one rule
        # (DECISIONS D290, G4-04)
        self.assertEqual(AS._KEY_BOUND_FACTS, frozenset(RQ.fact_key(fact) for fact in RQ.KEY_BOUND))


class SecondReviewTests(SimpleTestCase):
    def test_a_code_accounting_for_an_unresolved_act_is_added_others_stay_alternatives(self):
        R = two_sessions().build()
        second = corti(('43239', 5), ('45385', 2), ('45390', 3), provider='corti')
        found = run(R, ('45385', 2), second=second)
        added = by_code(found)['43239']
        self.assertEqual((added.origin, added.status, added.proposed_by),
                         (AS.Origin.SECOND_REVIEW, Outcome.READY, ('corti',)))
        self.assertEqual(found.second_review.added, ('43239',))
        why = {item.code: item.why for item in found.alternatives if item.origin is AS.Origin.SECOND_REVIEW}
        self.assertEqual(why, {'45385': AS.NotAdded.CARRIED, '45390': AS.NotAdded.NOT_LEFT})


# --- the records (FINAL 12; 5.7 measure 9; 9.3's assess row) ----------------------------------------------------------


class RecordTests(SimpleTestCase):
    def test_services_stub_and_inventory_problems_are_v1s_for_the_rollback_image(self):
        from studio.interpretation import assess as v1  # the retired module, read here only to pin the copy

        self.assertEqual(AS.INVENTORY_PROBLEMS, v1.INVENTORY_PROBLEMS)
        self.assertEqual(dict(AS.SERVICES_STUB, version=v1.SERVICES_STUB['version']),
                         {key: tuple(value) if isinstance(value, list) else value
                          for key, value in v1.SERVICES_STUB.items()})
        self.assertEqual(AS.SERVICES_STUB['version'], ENGINE_VERSION_V3)  # AMENDMENT-2 8.1: the writer's label
        found = run(two_sessions().build(), *TWO)
        self.assertEqual(dict(found.services), {'version': ENGINE_VERSION_V3, 'services': [], 'conflicts': [],
                                                'attributions': [], 'problems': []})
        self.assertEqual(found.completeness['inventory_problems'], list(v1.INVENTORY_PROBLEMS))

    def test_the_d22_fields(self):
        found = run(two_sessions().build(), *TWO)
        # AMENDMENT-2 8.1 [R:replay-R4]: every writer on the current path writes the _V3 labels - the pair, the
        # inventory, the engine (and event_coding@3) - and REQUIREMENTS_VERSION, which DECISIONS D292 moves with E1j's
        # read-set (the integration's label)
        self.assertEqual(dict(found.versions), {'interpretation': INTERPRETATION_PAIR_V3,
                                                'inventory': INVENTORY_VERSION_V3,
                                                'requirements': REQUIREMENTS_VERSION, 'engine': ENGINE_VERSION_V3})
        self.assertEqual((AS.ENGINE_VERSION, INTERPRETATION_PAIR_V3, INVENTORY_VERSION_V3),
                         ('cpt-studio-events@3', 'gemini-events@3/appraisal@2', 'gemini-inventory@3'))
        self.assertEqual(found.event_coding['version'], ENGINE_VERSION_V3)
        self.assertNotEqual(ENGINE_VERSION_V3, ENGINE_VERSION_V2)  # a new label beside v2's, never in its place

    def test_completeness_and_event_coding(self):
        found = run(two_sessions().build(), *TWO)
        self.assertLessEqual({'state', 'reasons', 'statement', 'unresolved_items', 'bundled', 'not_listed', 'covered',
                              'included_by', 'inventory_problems', 'event_coding'}, set(found.completeness))
        self.assertNotIn('member_answers', found.completeness)
        self.assertEqual(found.completeness['event_coding'], found.event_coding)
        self.assertEqual(set(found.event_coding['codes']), {p.key for p in found.codes if p.evaluation is not None})
        sessions = AS.session_acts(found.event_coding)
        self.assertEqual(set(sessions), {X(1), X(2)})
        self.assertIn(E(2), sessions[X(1)].reportable)

    def test_the_family_slug_and_the_listed_code_bound_equal_their_originals(self):
        from studio.interpretation import wording
        from studio.interpretation.engine import derive

        for family in SessionKind:
            self.assertEqual(AS.family_slug(family), derive.family_slug(family))
        self.assertEqual(AS.MAX_LISTED_CODE, wording.MAX_LISTED_CODE)

    def test_an_unknown_provider_status_or_a_missing_answer_raise(self):
        R = EF.colonoscopy().build()
        with self.assertRaises(ValueError):
            run(R, ('45385', 2), status='sent')
        with self.assertRaises(ValueError):
            AS.assess_facts(dated(R), date_of_service=DAY, text=TEXT, pages=(), integrity=Integrity(),
                            provider_status='succeeded', proposals=None, reference=Lookup(), member=ENTERED,
                            label=str)
        failed = run(R, ('45385', 2), status='failed')
        self.assertEqual((failed.codes, failed.completeness['state']), ((), 'incomplete'))


# --- fingerprints over facts (D7; 9.3; P-DET) -------------------------------------------------------------------------


class FingerprintTests(SimpleTestCase):
    def test_identical_inputs_give_a_byte_identical_assessment(self):
        R = two_sessions().build()
        self.assertEqual(AS.digest(run(R, *TWO)), AS.digest(run(R, *TWO)))

    def test_the_fingerprint_moves_with_a_fact_the_decision_read_and_never_with_a_proposer(self):
        R = EF.colonoscopy().build()
        base = by_code(run(R, ('45385', 2)))['45385']
        doc = EF.colonoscopy()
        doc.events[E(2)] = {**doc.events[E(2)], A.TECHNIQUE_DEVICE: (sup(Device.HOT_SNARE),)}
        moved = by_code(run(doc.build(), ('45385', 2)))['45385']
        self.assertEqual(moved.status, Outcome.READY)
        self.assertNotEqual(moved.fingerprint, base.fingerprint)
        named = by_code(run(R, ('45385', 2), provider=corti(('45385', 2), provider='another')))['45385']
        self.assertEqual((named.proposed_by, named.fingerprint), (('another',), base.fingerprint))

    def test_the_fingerprint_carries_the_billing_context_an_em_or_a_pctc_code_reads(self):
        """v1's _relevant_context, which FINAL-V2 6.5's "context values" and AMENDMENT-1 6.4 rest on (a change of a
        carried value clears the code's decision): an E/M code's fingerprint carries the billing context, and so does a
        code whose PFS row carries separate 26 and TC rows (the PC/TC consideration reads it) - the refutation's P3. A
        code whose row splits nothing, or that has no row, does not move with it."""
        class Rows(Lookup):
            def __init__(self, rows):
                self.rows = rows

            def lookup(self, code, service_date):
                found = self.rows.get(code)
                return SimpleNamespace(pfs=None if found is None else {'global_days': '000', 'modifier_rows': found},
                                       mue=None)

        def prints(doc, code, event, rows):
            out = set()
            for billing in ('professional', 'facility', ''):
                member = AS.MemberContext(setting='office', patient_status='established', billing_context=billing)
                found = by_code(run(doc.build(), (code, event), member=member, reference=Rows(rows)))[code]
                self.assertEqual(found.status, Outcome.READY)
                out.add(found.fingerprint)
            return len(out)

        self.assertEqual(AS.split_components({'modifier_rows': ['26', 'TC']}), True)
        for rows in ({'modifier_rows': ['26']}, {'modifier_rows': []}, {}, None, {'modifier_rows': '26TC'}):
            self.assertFalse(AS.split_components(rows), rows)
        self.assertEqual(prints(manometry(), '91010', 1, {'91010': ['26', 'TC']}), 3)
        self.assertEqual(prints(_office(), '99213', 1, {}), 3)
        self.assertEqual(prints(manometry(), '91010', 1, {'91010': ['53']}), 1)
        self.assertEqual(prints(manometry(), '91010', 1, {}), 1)
        self.assertEqual(prints(EF.colonoscopy(), '45385', 2, {'45385': ['53']}), 1)

    def test_no_document_string_reaches_the_assessment(self):
        """Every string of an assessment is CPT Studio's own (codes, keys, fact keys, causes, versions, R1's scope
        words, fixed completeness sentences, the provider's name, fingerprints) or a session label the caller gave:
        none is a slice of the revision."""
        found = run(two_sessions().build(), *TWO)
        slices = {TEXT[100 * n:100 * n + 60] for n in range(1, 30)}
        data = AS.jsonable(found)
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, str):
                self.assertNotIn(item, slices)
                if len(item) >= 12:
                    self.assertNotIn(item, TEXT)
            elif isinstance(item, dict):
                stack += list(item.keys()) + list(item.values())
            elif isinstance(item, list):
                stack += item


# --- the boundary (2d's hand-off R8, 5.7 measures 4 and 5) ------------------------------------------------------------


class BoundaryTests(SimpleTestCase):
    def test_assess_builds_the_factset_with_effective_never_factset(self):
        """The triage's hand-off 2d:R8 (S3 hazard 5): assess re-judges L1 against the effective date; the stored
        factset() is never read."""
        tree = ast.parse((ENGINE / 'assess.py').read_text(encoding='utf-8'))
        called = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                  and node.func.value.id == 'facts_'}
        self.assertIn('effective', called)
        self.assertNotIn('factset', called)
        names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertNotIn('factset', names)

    def test_the_two_modules_keep_measure_4_and_import_no_legacy_module(self):
        for name in ('assess', 'measure'):
            with self.subTest(module=name):
                source = (ENGINE / f'{name}.py').read_text(encoding='utf-8')
                self.assertEqual(measure_4(source, engine=True), [])
                imported = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
                imported |= {alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import)
                             for alias in node.names}
                legacy = ('studio.validation', 'studio.gi', 'studio.participants', 'studio.types',
                          'studio.interpretation.wording')
                self.assertFalse({module for module in imported if module and module.startswith(legacy)})

    def test_the_end_to_end_entry_reads_the_stored_row_through_effective(self):
        """assess over store.textfree_v2's view of a stored row equals assess_facts over facts.effective of it."""
        from tests.v2 import test_facts as TF

        content = TF.colonoscopy()
        view = TF.view(content)

        def line(n):
            at = TF.unit_span(n)
            return EvidenceSpan(0, at.start, at.end, TF.TEXT[at.start:at.end], True)

        proposals = NormalizedResponse('corti', 'synthetic@1', codes=tuple(
            ProviderCode('selected', 'CPT', code, '', (line(n),)) for code, n in (('45385', 6), ('45378', 5))))
        kwargs = dict(date_of_service=DAY, text=TF.TEXT, pages=(), integrity=Integrity(), provider_status='succeeded',
                      proposals=proposals, reference=Lookup(), member=ENTERED, label=str)
        found = AS.assess(inventory=view, **kwargs)
        self.assertEqual(AS.digest(found), AS.digest(AS.assess_facts(F.effective(view, DAY), **kwargs)))
        self.assertEqual([p.code for p in found.codes], ['45385', '45378'])
        self.assertTrue(all(p.evaluation is not None for p in found.codes))

    def test_mypy_strict_passes_on_both_modules_and_refuses_a_string_operation_on_a_value(self):
        def mypy(*arguments):
            return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull, *arguments],
                                  capture_output=True, text=True, timeout=600, cwd=APP)

        result = mypy('studio/interpretation/engine/assess.py', 'studio/interpretation/engine/measure.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 2 source files', result.stdout)
        probe = mypy('-c', 'from studio.interpretation.engine.assess import Assessed\n'
                           'def probe(found: Assessed) -> bool:\n'
                           '    return found.status.startswith("r")\n')
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)
        self.assertIn('has no attribute "startswith"', probe.stdout)


class D293DanglingSessionTests(SimpleTestCase):
    """DECISIONS D293 (refute-f3e-r2 N1): a session fact that is not established and that engine/combination reads as
    naming any session - an overfilled slot's merged view, or a negated claim left open - keeps every id it names that
    the FactSet does not hold (a dangling id: settle's I4) in ``possible_sessions``, first, as a single unestablished
    claim of that id does (DECISIONS D227 R2-2): its family read stays fail-closed, so the reading is never narrower
    than its written facts read alone (AMENDMENT-2 4.3.3 a, 4.4). Before the rule the views dropped the id: 43239 READY
    beside a rival 45380, and 99214 READY beside a possible procedure of the day, where the stated written fact read
    alone holds each. Synthetic FactSets only (refute-f3e-r2's probes q5 and q6)."""

    @staticmethod
    def shapes(unit: int) -> dict:
        from tests.v2.test_combination import overfilled
        S_, N_ = State.SUPPORTED, State.NEGATED
        dangling = (Reason.REFERENCE_INVALID,)
        return {'alone: X9 stated, unresolved': Fact(Res.UNRESOLVED, X(9), S_, (), dangling, (EF.unit(unit),)),
                'alone: not in X9, unresolved': Fact(Res.UNRESOLVED, X(9), N_, (), dangling, (EF.unit(unit),)),
                'view [X9 S, X9 S]': overfilled((S_, X(9)), (S_, X(9))),
                'view [X9 S, X1 S]': overfilled((S_, X(9)), (S_, X(1))),
                'view [X9 N, X1 S]': overfilled((N_, X(9)), (S_, X(1)))}

    @staticmethod
    def egd(e3_session: Fact) -> FactSet:
        """An EGD X1 (E1), its established cold-forceps biopsy E2 in the antrum (43239's act), and a second cold-forceps
        biopsy E3 in the gastric body whose session fact is ``e3_session``."""
        doc = EF.egd()
        doc.act(2, Kind.BIOPSY, places=[sup(Landmark.GASTRIC_ANTRUM)], device=sup(Device.COLD_FORCEPS))
        doc.act(3, Kind.BIOPSY, session=e3_session, places=[sup(Landmark.GASTRIC_BODY)],
                device=sup(Device.COLD_FORCEPS))
        return doc.build()

    @staticmethod
    def office(e2_session: Fact) -> FactSet:
        """An office visit X1 (this encounter, its visit E1 by medical decision making) and a counseling act E2 done
        today whose session fact is ``e2_session``: only its session's family can make it a procedure of the day."""
        doc = EF.Doc()
        doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.MEDICAL_DECISION_MAKING))
        doc.act(2, Kind.OTHER, session=e2_session, other_class=sup(ct.OtherClass.COUNSELING))
        return doc.build()

    def test_a_dangling_id_keeps_the_rival_family_open(self):
        control = self.egd(sup(X(1)))
        self.assertEqual(CO.possible_sessions(control, E(3)), (X(1),))
        self.assertEqual(by_code(run(control, ('43239', 2), ('45380', 7)))['43239'].status.value, 'ready')
        for label, fact in self.shapes(3).items():
            with self.subTest(label):
                R = self.egd(fact)
                self.assertEqual(CO.possible_sessions(R, E(3))[0], X(9))
                self.assertTrue(CO.may_be_of_family(R, E(3), SessionKind.COLONOSCOPY))
                found = by_code(run(R, ('43239', 2), ('45380', 7)))['43239']
                self.assertEqual(found.status.value, 'needs_clarification')
                self.assertEqual((found.item.held.fact, found.item.held.cause),
                                 ('competing_codes', 'coding_rule:competing_codes'))
                self.assertIn('45380', list(found.competes))

    def test_a_dangling_id_keeps_a_possible_procedure_of_the_day(self):
        control = self.office(sup(X(1)))
        self.assertFalse(CO._procedural_family(control, E(2)))
        self.assertEqual(by_code(run(control, ('99214', 1)))['99214'].status.value, 'ready')
        for label, fact in self.shapes(2).items():
            with self.subTest(label):
                R = self.office(fact)
                self.assertTrue(CO._procedural_family(R, E(2)))
                found = by_code(run(R, ('99214', 1)))['99214']
                self.assertEqual(found.status.value, 'needs_clarification')
                self.assertEqual((found.item.held.fact, found.item.held.cause),
                                 ('separate_em', 'coding_rule:same_day_em'))

    def test_an_id_the_factset_holds_adds_no_session(self):
        """The rule keeps only ids the FactSet does not hold: a view of held sessions reads every session, as before."""
        from tests.v2.test_combination import overfilled
        R = self.egd(overfilled((State.SUPPORTED, X(1)), (State.NEGATED, X(1))))
        self.assertEqual(CO.possible_sessions(R, E(3)), tuple(R.sessions))
