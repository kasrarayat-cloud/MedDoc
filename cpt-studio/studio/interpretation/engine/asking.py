"""Round r3's question planner (DECISIONS D306-D308, D320; build-v2/a2b/r3/design/DESIGN-v2.md a.4, b, b.9, e.2-e.3;
CENSUS-v2): which of the engine's reading doubts Fable is asked about, in which requests, beside which calibration item.
Built in round r3's build on int3 (087538cd8) from the probe prototype (build-v2/a2b/r3/probe), with the rulings
D317-D319 and D323 (the port's findings) the build carries.

``plan(R, asked_before)`` (a.4): for every candidate code (whatif.candidate_codes) and every positive candidate of it,
each what-if witness is mapped to its census row (``classify``): a READING row gives one or more question specs (the
value rule, ``_values``), any other row (BILLING, ABSENT, CODER, FABLE, a family this build does not ship) gives none
and BLOCKS the candidate - the releasable filter, by effect: a candidate one of whose witnesses no answer can release
is never released through that candidate, so its other witnesses are asked only where they serve another releasable
candidate. Specs are deduplicated by content key and never re-asked (``asked_before``). An empty plan is the fixed
point.

The families shipped (DECISIONS D320: the ones the probe validated; every claim the release direction, every control
its EXACT negation, rendered by contract/question_claims.py): Q-REL (b.1: a statement or a kept unlisted entry does not
take an act's occurrence away - R1, R2, C7b-other, U1 - asked in the NARROWEST relation exact for the statement's class
and status, DECISIONS D318 (3) and its second addendum: question_claims.relation_form, read by ``question_form`` for
every question in ``described_spec`` - an established denial "does not deny", an open denial "does not deny or cast
doubt on", an established plan "does not plan or recommend", any other statement "does not concern"; never the concern
form where a narrower exact one exists: the repair pass's RA-4), Q-FACT (b.2: one value of one attribute - F1-F5, A3,
C2a, C6, F8, F11, F12; and the row-7 possible examination's tie, census gap G1 below), Q-ONLESION (b.4: R3/R4 where the
target row's SAME rests on the statement's lesions' places alone: ``_onlesion_spec``, DECISIONS D323 F1) and Q-ABSORB
(b.7: U3, U4). NOT shipped (DECISIONS D320, D323 O1): Q-LESION (b.3's re-ask of the fact request's lesion pairs: the
planner asks no lesion-pair question; ``lesion_pair_specs`` is kept as the prototype built it and read by nothing
here), Q-GROUP (F6, cards_indistinct), Q-KIND (F7, an umbrella's method), F9 (the date of service), U2 and A3's
narrowing - each blocks its candidate, fail-closed, and is counted by name. The colonoscopy route table (DECISIONS D310
(1), evaluate._row_colon_route) is a BILLING table whose facts are READING: its approach and anatomy-type questions
carry their facts' reading causes and have no question template here (the value rule blocks them: 'no question
template'), its established failure is B5 and its no-stoma hold ABSENT - so a through-stoma code on a document naming
no stoma is never released through any answer.

Census gap G1 (found by the what-if on C-C2MEM-023; D306 addendum (a): every reading-uncertainty hold is asked): row 7
reads every event that MAY be the session's examination; one not established as the session's examination (its session
or its kind open) that fails rows 2-5 holds every code of the session (coding_rule:examination, or its open facts). Its
release is the tie itself: Q-FACT "This act was not done during session {X}." with its exact negation; every row-7
witness about that event maps to that one question. DECISIONS D315 (6), D320: asked only of an examination whose status
is ESTABLISHED performed or planned - never of one attempted, or whose status is in doubt (for an attempt, "not done
during session X" is true as worded while the engine's fact - not X's examination - is false).

``calibration_pool(R)`` (b.9): question-form items whose true answer is the HOLDING direction, from the fact pass's own
CONTROLLED judgments (FactSet.controlled: established with the contrary control rejected): K1 the plain negation of an
established value, K2 an exclusive alternative of it, K3 a claimed pair whose covers claim the fact pass supported, K4
an act's established target lesion negated - and, DECISIONS D310 (4), K3's second source: the pairs SAME on every row
from established facts (``same_pairs``). DECISIONS D319 (the owner's decision): every question request carries EXACTLY
ONE calibration item (``calibration_count`` is CALIBRATION_COUNT, 1), a known-false claim with its exact negation;
``draw`` takes it deterministically - a negative-form item of the first family the request asks that has one, else
any negative-form item, else any item; a covers K3 never (it is drawn only beside a K1, and one item leaves no room).
``partition`` (e.3) cuts a round's questions into requests of at most QUESTION_BOUND claims, each with its own item;
nothing is dropped. THE PLANNER'S INVARIANT (DECISIONS D323 F4): a request whose restricted pool cannot give its one
item is uncalibrated - refused at plan time (``UncalibratedRequest``) and never sent, where before it failed settle's
H5 only after the paid send.

DECISIONS D314 (THE CLASS): every question form and every calibration item takes its sentence from the fact pass's own
form for (object class, attribute, state) (contract/question_claims: claims.FORMS keyed by claims.object_class's class,
read here on the settled facts by ``event_class``), and each form declares the classes and statuses its sentence is
exact for. ``describe`` reads every subject's class and status; a question whose form is not exact for them is never
asked - its witness is blocked with a census reason 'D314 (...)', the held fact stays held (``described_spec``); the
one form whose fact is the not-done reading, G1's fact.session.not, is declared for an act of any status. K1, K2 and
K4 - every act-form calibration item - are drawn only from an act established performed (``performed_act``: an exact
negation is exact only under its presupposition, and "This act was (not) done <q>" presupposes the act was done).

DECISIONS D315 (the presupposition on the item's OBJECT): a calibration item is known false only if it is false under
every reading of EACH object it names, not only of its subject. K2's alternative session is drawn only between two
EXCLUSIVE sessions that TOOK PLACE (``exclusive_sessions``, read by the K2 draw only): each an endoscopic procedure
session (``procedure_session``: its kind supported among PROCEDURE_SESSION_KINDS - DECISIONS D317 (4): that IS
catalogue.ENDOSCOPIC_FAMILIES, the one table - at least one act established performed held in it, no part_of_session
claim), and - D317 (4) - the two of ESTABLISHED DIFFERENT DATES or SEPARATE ENCOUNTERS (``separate_occasions``: two
procedure sessions of one kind filed for one examination give no K2). K4 is drawn only for an act whose part_of is
silent - done to the lesion in its own right; a lift, an adjunct, a step or an access takes its object from the act it
is a part of.

DECISIONS D317 (1), THE MEMBER LINE: an item is drawn only where its truth turns on no member line - no statement that
gives another performer or author to the acts on one side of it. The fact pass represents such a statement as a
PART of the document whose performer or author it doubts toward another (a section whose performer or owner fact is
not established and reads another value: pass 1's doubt about the section and its acts, a contradiction's side) -
and pass 2 keeps the line itself as a kept unlisted entry beyond those parts; ``member_line_side`` reads THAT (never a
word of the note): the side of the nearest kept unlisted entry beyond every such part, to the document's edge, with
the parts themselves - or, where no entry locates the line, the parts alone. An item naming any object (its act, a
session's card, a lesion) told there is not drawn.

FINAL-V2 5.7 measure 4 (DECISIONS D323 F3): no stored string decides here by a word test. A held fact's cause is read
typed (whatif.cause_of: CPT Studio's own labels, read through a table the engine's own builders make from its
enumerations), the calibration kinds and K3 sources are StrEnums, the stored names of the document and of the
unlisted entries are read through their Enums (``Named``, ``_Mark``), and the engine pin reads its modules as modules.

DECISIONS D324 (the repair after the adversarial pass over int4): (3) Q-ABSORB names only PERFORMED acts (``_acts_of``,
re-checked by ``eligible``: L1-01); (8) the plan's cost (L7-A7-PLAN-COST) - every what-if it repeats per value or per
witness reads ONE evaluation per FactSet (``_Context``: each world built once with one Reader, each candidate evaluated
over it once, every world evaluated for all its candidates in a row by ``prefetch``; the Q-ONLESION what-if once per
pair; a relation witness's pairs read from the plan's one Reader, whatif._EventPairs), and no per-value what-if is paid
for a filter that cannot drop a value (A3's silent reach: ``_silent_reach_values`` reads the code's own reach tables).

DECISIONS D328 (2) (finding R3D-L1-1): a statement-act pair's relation is ONE proposition across the pair families
(Q-REL, Q-ONLESION, Q-LESION). A release of the pair through one family stands only when every question asked of the
same pair, in any family, request or round, got the release direction on both its claim and its control in an
answered, healthy request (contract/settle.exclusive holds the rest, question_conflict); so the planner asks a pair
through another family only when no earlier answer about the pair holds it (``_Context.unheld``: settle.PairAnswers over
the row's question records so far, the pairs a question is asked of read on the plan's FactSet - a Q-ONLESION (A, L) is
asked of every pair of A whose statement may name L). A witness one of whose questions is so held is blocked
(PAIR_HELD), and its held fact stays held for the coder.

Text-free and pure: ids, enumeration members and stored value strings only; ``engine_digest`` pins the modules the plan
reads (QUESTION_ENGINE_SHA256_V3)."""
from __future__ import annotations

import calendar
import datetime
import hashlib
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum, StrEnum, unique
from pathlib import Path
from types import ModuleType

from studio.interpretation.contract import question_claims as qc
from studio.interpretation.contract.types import (AnastomosisSubtype, Attribute, DateRelation, EncounterRelation,
                                                  Extent, FactState, Kind, Landmark, Multiplicity, Owner, Performer,
                                                  Precision, Reason, Result, SessionKind, Status, UnlistedWhat)
from studio.interpretation.engine import anatomy, catalogue, coverage, evaluate, pairing, questions, whatif
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import Fact, FactSet, HeldFact, Id, IdFamily, IsoDate, Span

_A = Attribute

# --- the constants (pinned with the question request: DESIGN-v2 h) ------------------------------------------------------

# DECISIONS D319 (the owner's decision, class a): EXACTLY ONE calibration item per question request - a known-false claim
# with its exact negation, drawn from the restricted pool after every D314, D315 and D317 rule and the member-line guard
# (b.9's C = max(4, ceil(q / 4)) is superseded). CALIBRATION_POOL_MIN is the same one item, re-derived with it: a
# request whose restricted pool cannot give its one item is UNCALIBRATED, as before - and since D323 (F4) the planner
# refuses it at plan time (``UncalibratedRequest``), never sent. H5 reads the same condition after the send: settle's
# CALIBRATION_FLOOR is 1 (fewer than one item: uncalibrated), which the settle owner sets beside this (this lane's
# question); H2 is unchanged (the item's false claim supported refuses its request).
CALIBRATION_COUNT = 1
CALIBRATION_MIN = CALIBRATION_COUNT
CALIBRATION_POOL_MIN = CALIBRATION_COUNT

# QUESTION_BOUND (DESIGN-v2 e.2; DECISIONS D313, D318 (2) and its first addendum): floor(85% x 128,000 / t_q / 2) x 2
# claims per question request, t_q the output tokens per question claim MEASURED at effort max - each question request's
# output over its claims, the largest, rounded up - derived in exact integer arithmetic (claims.claim_bound_derivation's
# manner). Measured, every question request of the paid probe at effort max (their usage in the batches' MANIFEST
# question runs, anthropic-project/pairs/r3-probe-1 and r3-probe-2; NOTES of this lane show the records):
#   step 1 short, r3-probe-1 (A-v3.F3all): bba52c33... 55,219 output tokens over 12 claims (4,601.58 -> 4,602);
#   step 1 long, r3-probe-2 (A-note8.F3long): bcd2cbb2... 105,999 over 20 (5,299.95 -> 5,300), 0879b0fc... 71,896 over
#   20 (3,594.80 -> 3,595) and 8ac5eaf6... 94,976 over 16 (5,936 exactly).
# t_q = 5,936 (8ac5eaf6's), 85% x 128,000 = 108,800 output tokens a request, 108,800 // 5,936 = 18 claims (5,936 x 18 =
# 106,848; 19 would expect 112,784). D318's addendum: the rounding is a PAIR, 2 claims (a claim and its control) - e.2's
# "floor(... / 10) x 10" is superseded, since it would give 10 (one question and its item a request) for no gain in
# safety: the 85% margin is the safety, and an overrun is split and sent again (e.4). So QUESTION_BOUND = 18: with
# D319's one calibration item, 8 questions and their item a request (2 x (8 + 1) = 18). The bound SIZES requests; it
# never drops or limits a question (D306 second addendum (d)): a round's questions go in as many requests as they need
# (``partition``, e.3), and an output overrun is halved and sent again (``split``, e.4). QUESTION_BOUND_PROVISIONAL (100
# claims, t_q assumed 1,000) is the value the prototype planned with before any measurement, kept as the record.
QUESTION_BOUND_PROVISIONAL = 100
QUESTION_BOUND_OUTPUT_TOKENS = 128_000  # e.1: the question request's max_tokens (question_claims.QUESTION_MAX_TOKENS)
QUESTION_BOUND_MARGIN = (85, 100)  # e.2: a request's expected output at or under 85% of the output maximum
QUESTION_BOUND_ROUNDING = 2  # D318's first addendum: a claim and its control
# (output tokens, claims) of each question request measured at effort max: r3-probe-1's one request, r3-probe-2's three
QUESTION_BOUND_MEASURED: tuple[tuple[int, int], ...] = ((55_219, 12), (105_999, 20), (71_896, 20), (94_976, 16))


@dataclass(frozen=True, slots=True)
class QuestionBoundDerivation:
    """QUESTION_BOUND's derivation (the comment above): t_q, the claims within the margin at t_q, and the bound."""
    tokens_per_claim: int
    capacity: int
    bound: int


def question_bound_derivation(measured: Sequence[tuple[int, int]] = QUESTION_BOUND_MEASURED,
                              output_tokens: int = QUESTION_BOUND_OUTPUT_TOKENS) -> QuestionBoundDerivation:
    """e.2's bound from measured figures, in exact integer arithmetic. RuntimeError when no request could carry even one
    question with its calibration item (2 x (1 + CALIBRATION_COUNT) claims): asking would then need a bound the model's
    output cannot hold - the owner's (class b), never a reason to drop a question."""
    if not measured or any(tokens < 0 or claims <= 0 for tokens, claims in measured):
        raise RuntimeError('QUESTION_BOUND needs at least one measured question request with claims')
    tokens_per_claim = max(-(-tokens // claims) for tokens, claims in measured)
    numerator, denominator = QUESTION_BOUND_MARGIN
    capacity = output_tokens * numerator // denominator // max(tokens_per_claim, 1)
    bound = capacity // QUESTION_BOUND_ROUNDING * QUESTION_BOUND_ROUNDING
    if bound < 2 * (1 + CALIBRATION_COUNT):
        raise RuntimeError(f'QUESTION_BOUND {bound} cannot carry one question with its calibration (t_q '
                           f'{tokens_per_claim}): the owner\'s (class b)')
    return QuestionBoundDerivation(tokens_per_claim=tokens_per_claim, capacity=capacity, bound=bound)


QUESTION_BOUND = question_bound_derivation().bound


def question_bound_document() -> dict[str, object]:
    """QUESTION_BOUND with its figures (DESIGN-v2 e.2: pinned as QUESTION_BOUND_SHA256_V3, question_claims.pins)."""
    derived = question_bound_derivation()
    return {'question_bound': QUESTION_BOUND, 'tokens_per_claim': derived.tokens_per_claim,
            'capacity': derived.capacity, 'measured': [list(item) for item in QUESTION_BOUND_MEASURED],
            'output_tokens': QUESTION_BOUND_OUTPUT_TOKENS, 'margin': list(QUESTION_BOUND_MARGIN),
            'rounding': QUESTION_BOUND_ROUNDING, 'provisional': QUESTION_BOUND_PROVISIONAL}


@unique
class Family(Enum):
    """A question's family (DESIGN-v2 b)."""
    Q_REL = 'Q-REL'
    Q_FACT = 'Q-FACT'
    Q_LESION = 'Q-LESION'
    Q_ONLESION = 'Q-ONLESION'
    Q_ABSORB = 'Q-ABSORB'


@unique
class Named(StrEnum):
    """A question's stored subject that names no object of the FactSet (CPT Studio's own record word, read through this
    Enum, never by a word test): the encounter."""
    DOCUMENT = 'document'


@unique
class _Mark(StrEnum):
    """The marks of the stored names a question gives what is no Id (CPT Studio's own records): 'u:<index>' a kept
    unlisted entry (stored with its typed index: ``unlisted_index``), 'acts:<session id or "document">' the acts an
    unlisted entry may re-tell (Q-ABSORB)."""
    UNLISTED = 'u:'
    ACTS = 'acts:'


UNLISTED_PREFIX = _Mark.UNLISTED.value
ACTS_PREFIX = _Mark.ACTS.value


def _after(stored: str, mark: _Mark) -> str | None:
    """What follows ``mark`` in a stored name that begins with it - its head read through the Enum (_Mark), never a
    word test - else None."""
    head = len(mark.value)
    try:
        found = _Mark(stored[:head])
    except ValueError:
        return None
    return stored[head:] if found is mark else None


def unlisted_index(subjects: tuple[str, ...]) -> int | None:
    """The kept unlisted entry a question names ('u:<index>' among its subjects), stored beside the subjects as a typed
    index so that the engine's fold (facts._answered) reads no string."""
    for subject in subjects:
        rest = _after(subject, _Mark.UNLISTED)
        if rest is not None and rest.isdigit():
            return int(rest)
    return None


@unique
class CalibrationKind(StrEnum):
    """b.9's calibration item kinds (a StrEnum: its value is the word a stored record carries): K1 the plain negation of
    an established value, K2 an exclusive alternative of it, K3 a Q-REL pair, K4 an act's established target lesion
    negated."""
    K1 = 'K1'
    K2 = 'K2'
    K3 = 'K3'
    K4 = 'K4'


# b.9's polarity: the negative-form kinds (the release claims of every relation family are negative)
NEGATIVE_KINDS: frozenset[CalibrationKind] = frozenset({CalibrationKind.K1, CalibrationKind.K3, CalibrationKind.K4})


@unique
class K3Source(StrEnum):
    """A K3 item's source (b.9): COVERS a claimed pair whose covers claim the fact pass supported (C7a: UNCONTROLLED,
    so drawn only beside a K1), SAME a pair SAME on every row from established facts (DECISIONS D310 (4): no companion);
    NONE for every other kind."""
    NONE = ''
    COVERS = 'covers'
    SAME = 'same'


@dataclass(frozen=True, slots=True)
class WitnessRecord:
    """The witness a question serves (stored with it: DESIGN-v2 h events.questions[].witnesses)."""
    code: str
    fact: str
    attribute: str | None
    subject: str | None
    cause: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class QuestionSpec:
    """One question (DESIGN-v2 a.4): ``family``, ``form`` (a key of contract/question_claims.QUESTION_TEMPLATES; a
    Q-REL spec is built in the concern form and described_spec hands it the narrowest exact form, question_form - so
    every planned spec, its key and its record carry the form it is asked in), ``subjects`` (stored forms: 'E3', 'X1',
    'L2', 'u:0'), ``attribute`` and ``value`` (its stored string, '' for none),
    ``negated`` (the release direction negates the value), ``names`` (the objects the claim names, in order: one required
    passage each, b.0), ``value_passage`` ('' | 'frame' | 'source' | 'section_head' | 'own': b.0's value passage,
    ``value_passage_of``), ``acts`` (the
    acts a Q-ABSORB names), ``census`` (the census row that asked it) and ``witnesses``."""
    family: Family
    form: str
    subjects: tuple[str, ...]
    attribute: Attribute | None
    value: str
    negated: bool
    names: tuple[str, ...]
    value_passage: str = ''
    acts: tuple[str, ...] = ()
    census: str = ''
    witnesses: tuple[WitnessRecord, ...] = ()
    # DECISIONS D314: each subject's (object class, status) as the planner read it (describe) - the request writes the
    # form's sentence only when the form is exact for them (question_claims.check_exact); never part of the key
    described: tuple[qc.Described | None, ...] = ()

    @property
    def key(self) -> str:
        """The content key (a.4's deduplication): family, form, subjects, attribute, value, negation."""
        return '|'.join((self.family.value, self.form, ','.join(self.subjects),
                         self.attribute.value if self.attribute is not None else '', self.value,
                         'not' if self.negated else ''))


@dataclass(frozen=True, slots=True)
class CalibrationSpec:
    """One calibration item (b.9): ``kind`` K1-K4 (CalibrationKind; a plain value is read into it), rendered exactly as a
    question of ``family`` and ``form`` is; its CLAIM's correct answer is contradicts (the holding direction) and its
    control's supports. ``source``: a K3's (K3Source)."""
    kind: CalibrationKind
    family: Family
    form: str
    subjects: tuple[str, ...]
    attribute: Attribute | None
    value: str
    negated: bool
    names: tuple[str, ...]
    value_passage: str = ''
    source: K3Source = K3Source.NONE
    described: tuple[qc.Described | None, ...] = ()  # DECISIONS D314: as QuestionSpec.described; never part of the key

    def __post_init__(self) -> None:
        object.__setattr__(self, 'kind', CalibrationKind(self.kind))
        object.__setattr__(self, 'source', K3Source(self.source))

    @property
    def key(self) -> str:
        return '|'.join((self.kind.value, self.family.value, self.form, ','.join(self.subjects),
                         self.attribute.value if self.attribute is not None else '', self.value,
                         'not' if self.negated else ''))

    @property
    def negative(self) -> bool:
        """b.9's polarity: K1, K3 and K4 are negative-form items (NEGATIVE_KINDS)."""
        return self.kind in NEGATIVE_KINDS


@dataclass(frozen=True, slots=True)
class Plan:
    """A round's plan: the specs in order (``order``), the codes each serves, and the not-asked witnesses counted by
    census reason (for the gate's report)."""
    specs: tuple[QuestionSpec, ...]
    serves: Mapping[str, frozenset[str]]
    blocked: Mapping[str, int]
    releasable: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class RequestPlan:
    """One question request of a round (e.3): its questions, its calibration item (DECISIONS D319: exactly one) and the
    seed of its interleaving. ``partition`` and ``split`` never give one without its item (``UncalibratedRequest``)."""
    questions: tuple[QuestionSpec, ...]
    calibration: tuple[CalibrationSpec, ...]
    seed: str

    @property
    def claims(self) -> int:
        return 2 * (len(self.questions) + len(self.calibration))

    @property
    def calibrated(self) -> bool:
        """The request carries its calibration (DECISIONS D319, D323 F4): at least CALIBRATION_POOL_MIN items - H5's
        condition, read before any send."""
        return len(self.calibration) >= CALIBRATION_POOL_MIN


UNCALIBRATED = 'question_health:uncalibrated'  # settle's H5 reason: the same outcome, refused before the send


class UncalibratedRequest(RuntimeError):
    """DECISIONS D323 F4, the planner's invariant: a question request whose restricted pool cannot give its calibration
    item is refused at PLAN time and never sent (before it, settle's H5 refused it only after the paid send). ``refused``:
    each refused request's questions (they stay unresolved, ``reason`` - settle's H5 reason - as before); ``requests``:
    the round's requests that carry their item. A stage that catches it records the refused questions unresolved and
    sends only ``requests``; one that does not stops before any send (fail-closed)."""

    def __init__(self, refused: tuple[tuple[QuestionSpec, ...], ...], requests: tuple[RequestPlan, ...] = ()) -> None:
        self.refused = refused
        self.requests = requests
        self.reason = UNCALIBRATED
        super().__init__(f'{len(refused)} question request(s) without a calibration item: refused at plan time, never '
                         f'sent ({UNCALIBRATED}; DECISIONS D323 F4)')


def check_calibrated(request: RequestPlan) -> RequestPlan:
    """The send-side guard of the same invariant (DECISIONS D323 F4): ``request`` when it carries its calibration item,
    else UncalibratedRequest - for a stage or builder to call on a request it is about to send, whatever made it."""
    if not request.calibrated:
        raise UncalibratedRequest(((*request.questions,),))
    return request


# --- the census (CENSUS-v2 section 1) -----------------------------------------------------------------------------------

# C6: a cross-object conflict - ONE set (round r3's integration int5, the fold lane's Q-F5 (c)): it IS engine/facts.CONFLICTS,
# read off the fold's typed reason table (DECISIONS D324 (4): K4's anatomy_conflict is a fixed-table check, never a
# reading, so it is no conflict a question may settle), pinned identical by tests/v2/test_r3c_int5
_CONFLICTS: frozenset[Reason] = facts_.CONFLICTS
_CF = whatif.CauseFamily
# C2a: the fact pass left no usable verdict (appraisal:missing, appraisal:detached) - the verdicts a cause names
_C2A_VERDICTS: frozenset[Enum] = frozenset({questions.Coherence.MISSING, questions.Coherence.DETACHED})
# a fact Fable already judged in the fact pass and did not support (C2b): never re-asked (DESIGN-v2 b) - every appraisal
# reason of 3.3 row 9 (questions.APPRAISAL_CAUSES: contradicts, unclear, qualified, incoherent) but C2a's two. ONE set
# (round r3's integration, the engine lane's Q-R3): it IS engine/facts.JUDGED, which the fold and _askable_open read,
# pinned equal to those reasons by tests/v2/test_r3b_engine (asking's own derivation of it is gone)
_C2B: frozenset[Reason] = facts_.JUDGED
# the reasons of an INTEGRITY failure: the words are not where pass 1 said - its source is never a passage (b.0)
INTEGRITY: frozenset[Reason] = frozenset({
    Reason.UNIT_UNKNOWN, Reason.WORDS_NOT_IN_UNITS, Reason.WORDS_NOT_BOUNDED, Reason.UNITS_NOT_CONSECUTIVE,
    Reason.SOURCE_TOO_LONG, Reason.ANCHOR_WORDS, Reason.REFERENCE_INVALID})
# F5: an unestablished fact pass 1 filed QUALIFIED (its reason one of the qualified:<q> reasons)
_QUALIFIED: frozenset[Reason] = frozenset({
    Reason.QUALIFIED_HEDGED, Reason.QUALIFIED_CONDITIONAL, Reason.QUALIFIED_REPORTED, Reason.QUALIFIED_PARTIAL,
    Reason.QUALIFIED_NAMED_ONLY, Reason.QUALIFIED_RESTATEMENT_ONLY, Reason.QUALIFIED_REFERENCE_ONLY})
_PAIR_FACTS = (_A.STATUS, _A.KIND, _A.SESSION, _A.DATE_RELATION, _A.PERFORMER, _A.SCOPE_BREADTH, _A.TARGET_LESION,
               _A.TECHNIQUE_DEVICE)
# F2's attributes with one satisfying value (CENSUS-v2 1.3 F2) and the frame-inherited ones (b.0's value passage)
_ONE_VALUE: Mapping[Attribute, object] = {_A.ENTRY: Owner.DOCUMENTING_CLINICIAN,
                                          _A.DATE_RELATION: DateRelation.ON_DATE_OF_SERVICE,
                                          _A.PERFORMER: Performer.DOCUMENTING_TEAM}
_FRAME = frozenset({_A.ENTRY, _A.DATE_RELATION, _A.PERFORMER})
_SESSION_VALUE = frozenset({_A.REACHED, _A.DEVICE_REACHED, _A.REACHED_ANATOMY, _A.STATIONS})


def value_passage_of(attribute: Attribute) -> str:
    """b.0's value passage of a Q-FACT form (or a calibration item rendered as one) asking ``attribute``: 'frame' for
    the frame-inherited attributes (entry, date relation, performer), 'source' for a session's reach, 'section_head'
    for an act's places, and - DECISIONS D325 (4), finding L3P-2: every question's passages hold where the asked value
    was established - 'own' for EVERY other form: the asked fact's own integrity-passed sources, a REQUIRED value
    passage wherever one of them lies outside the subject's card (contract/question_claims._Geometry.value; a value
    with no source outside the subject's card changes nothing), named by the claim line's value field and exempt from
    the heading ban as the frame's is. Before it, those forms had no value passage: the words where pass 1 established
    the asked value lay in no passage, so a right proof quoting them was voided and a hollow proof - the act's own
    words alone - established the value (B-fb10's visit basis, for both of its values)."""
    if attribute in _FRAME:
        return 'frame'
    if attribute in _SESSION_VALUE:
        return 'source'
    if attribute is _A.TARGET_PLACES:
        return 'section_head'
    return 'own'
# the attributes a Q-FACT may be asked of (b.2's table: every one has a plain template and its exact negation)
FACT_ATTRIBUTES = frozenset({_A.ENTRY, _A.DATE_RELATION, _A.PERFORMER, _A.PERFORMER_PERSON, _A.SESSION,
                             _A.TARGET_LESION, _A.TARGET_PLACES, _A.TECHNIQUE_DEVICE, _A.PURPOSE, _A.TARGET_DUCT,
                             _A.REACHED, _A.REACHED_ANATOMY, _A.STATIONS, _A.VISIT_BASIS, _A.PART_OF, _A.CAUSE})
# b.2's table gives the part link and the cause ONLY their separation forms (F11 "not done as part of another act",
# F12 "not caused by another act of this procedure": _bundling_spec): the value rule never asks one of their values
_SEPARATION_ONLY = frozenset({_A.PART_OF, _A.CAUSE})


@dataclass(frozen=True, slots=True)
class Mapped:
    """A witness's census reading: ``specs`` (READING: the questions that may release it), or ``blocked`` (the census
    reason no answer releases it). ``row`` the census row."""
    row: str
    specs: tuple[QuestionSpec, ...] = ()
    blocked: str = ''


def _stored(subject: Id | None) -> str | None:
    return str(subject) if subject is not None else None


def _record(code: str, held: HeldFact) -> WitnessRecord:
    return WitnessRecord(code=code, fact=held.fact, attribute=held.attribute.value if held.attribute else None,
                         subject=_stored(held.subject), cause=held.cause, reason=held.reason.value if held.reason else None)


def _value_of(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _contradicted(R: FactSet, event: Id) -> bool:
    """C1 for a pair side: a fact the pairing rows read (or the status, the kind, a place) contradicted by pass 1."""
    for attribute in _PAIR_FACTS:
        if facts_.fact(R, event, attribute).result is Result.CONTRADICTED:
            return True
    return any(member.result is Result.CONTRADICTED for member in facts_.members(R, event, _A.TARGET_PLACES))


def _denies_or_doubts(R: FactSet, statement: Id) -> bool:
    """C7b-denial: the statement's status negated (filed or established) or doubted."""
    status = facts_.fact(R, statement, _A.STATUS)
    return (status.result is Result.NEGATED or status.state is FactState.NEGATED
            or any(reason in (Reason.DOUBT_STATED, Reason.DOUBT_UNCLEAR) for reason in status.reasons))


def _covers_supported(R: FactSet, statement: Id, act: Id) -> bool:
    return any(member.value == act and member.result is Result.SUPPORTED
               for member in facts_.members(R, statement, _A.SCOPE_COVERS))


def _rel_spec(R: FactSet, code: str, held: HeldFact, pair: pairing.Pair) -> Mapped:
    """Q-REL (b.1) for one relation pair, or the census reason it is not asked."""
    if _contradicted(R, pair.statement) or _contradicted(R, pair.act):
        return Mapped('C1', blocked='C1')
    if pair.claimed:
        if _covers_supported(R, pair.statement, pair.act):
            return Mapped('C7a', blocked='C7a')
        if _denies_or_doubts(R, pair.statement):
            return Mapped('C7b-denial', blocked='C7b-denial')
    row = 'C7b-other' if pair.claimed else ('R2' if pair.possible else 'R1')
    # built in the concern form, the family's broadest; described_spec hands it the narrowest exact one (question_form)
    spec = QuestionSpec(Family.Q_REL, 'rel', (str(pair.statement), str(pair.act)), None, '', False,
                        (str(pair.statement), str(pair.act)), census=row, witnesses=(_record(code, held),))
    return Mapped(row, (spec,))


def _single_target_lesions(R: FactSet, statement: Id) -> tuple[Id, ...] | None:
    """The lesions a statement's single or listed target names (supported), None when it names none established."""
    lesion = facts_.fact(R, statement, _A.TARGET_LESION)
    found = [lesion.value] if lesion.result is Result.SUPPORTED and isinstance(lesion.value, Id) else []
    for member in facts_.members(R, statement, _A.SCOPE_TARGETS):
        if member.result is Result.SUPPORTED and isinstance(member.value, Id):
            found.append(member.value)
        elif not facts_.silent(member):
            return None
    return tuple(dict.fromkeys(found)) or None


def _whole_places(members: Sequence[Fact]) -> frozenset[Landmark] | None:
    """A place list's whole set when established (every member established, the supported members' places, one at least:
    the target row's reading), else None."""
    known = frozenset(member.value for member in members
                      if member.result is Result.SUPPORTED and isinstance(member.value, Landmark))
    return known if members and known and all(facts_.established(member) for member in members) else None


ONLESION_ACT_PLACES = "R3/R4 (the act's places are not established: an answer could not set it apart)"
ONLESION_STATEMENT_PLACES = "R3/R4 (the statement's own places are not established)"
ONLESION_BEYOND = ("R3/R4 (a place of the statement beyond its lesions' places holds the act's place: the SAME rests on "
                   "more than the lesions - DECISIONS D316 QB, D323 F1)")
ONLESION_CONTROL = ("R3/R4 (a place pair control asked of the statement or the act is not rejected: an answer could not "
                    "set it apart - DECISIONS D311, D323 F1)")
# round r3's integration (the engine lane's Q1, the ask lane's Q6): the release arm's OWN what-if is a necessary
# condition - pairing.not_on_sets_apart, so the planner follows every reading of the arm (D316 QB, R2E-QB-ANAT's
# anatomy and structure targets included) and never asks a question no true answer could release by
ONLESION_ARM = ('R3/R4 (an established not-on would not set the pair apart: pairing.not_on_sets_apart - DECISIONS D311, '
                'D316, D323 F1)')
# round r3's integration (the engine lane's Q-R2, R3BE-RF2's planner half): a pair the fact pass JUDGED (its act-lesion
# record a reason outside facts.PAIR_ASKABLE, or held unestablished with no record) is never re-asked - the fold refuses
# its answer (facts.pair_judged), so the question could only cost
ONLESION_JUDGED = 'C2b (FABLE: the fact pass judged the act-lesion pair - facts.pair_judged)'
# DECISIONS D328 (2) (finding R3D-L1-1): a statement-act pair's relation is ONE proposition across the pair families, so
# a pair is asked through another family (or another proposition) only when no earlier answer about it holds it - an
# answer whose reading is not the release direction on both members would hold the new answer's release anyway
# (contract/settle.exclusive, ``pair_held``), so the question could only cost; its witness is blocked and its held fact
# stays held for the coder
PAIR_FAMILIES: frozenset[Family] = frozenset({Family.Q_REL, Family.Q_ONLESION, Family.Q_LESION})
PAIR_HELD = 'D328 (2) (an earlier answer about the pair holds it: settle.pair_held)'


def _onlesion_unanswerable(R: FactSet, statement: Id, act: Id, lesions: Sequence[Id]) -> str:
    """DECISIONS D323 F1, the planner's side: '' where the target row's SAME between ``statement`` and ``act`` rests on
    the statement's lesions' places ALONE - so an established "not done to lesion L" for each of them is exactly what
    its one release arm (pairing._apart_from_unnamed under D311's class rule and D316's QB guard) needs - else the census
    reason it does not:
    - the act's whole place set established (otherwise the act may be anywhere and nothing sets it apart, 4.11);
    - the statement's own place list (its target places and a segment's range) established, and NO place of it beyond
      the places its lesions are established at holds a place of the act (anatomy.compatible): D316's QB - a denial
      placed at its lesion's place AND at the whole colon still covers a tattoo there, so the note contradicts itself
      whatever the lesion answer says;
    - every place pair control asked of EITHER object rejected (facts.apart_by_controls' every-control scan, D220 and
      D236; RFL2-1: an act-direction control pass 2 supported - "This act was done in the descending colon." - keeps the
      pair together whatever the answer).
    Read so, the planner never asks a question whose established answer the one arm could not read as a release (the
    releasable filter, by effect); it reads only what pass 1 filed and pass 2 established, never the note."""
    act_places = _whole_places(facts_.members(R, act, _A.TARGET_PLACES))
    if act_places is None:
        return ONLESION_ACT_PLACES
    own = list(facts_.members(R, statement, _A.TARGET_PLACES))
    segment = facts_.members(R, statement, _A.SCOPE_SEGMENT)
    if not all(facts_.established(member) for member in (*own, *segment)):
        return ONLESION_STATEMENT_PLACES
    places = {member.value for member in own if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)}
    ends = [member.value for member in segment if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)]
    if segment:
        if len(segment) != 2 or len(ends) != 2:
            return ONLESION_STATEMENT_PLACES
        places |= pairing.segment_range(ends[0], ends[1])
    lesion_places = {member.value for lesion in lesions for member in facts_.members(R, lesion, _A.PLACES)
                     if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)}
    if any(anatomy.compatible(place, held) for place in places - lesion_places for held in act_places):
        return ONLESION_BEYOND
    if not facts_.apart_by_controls(R, statement, act, _A.TARGET_PLACES, (), ()):
        return ONLESION_CONTROL
    if not pairing.not_on_sets_apart(R, statement, act):
        return ONLESION_ARM
    return ''


def _onlesion_spec(R: FactSet, code: str, held: HeldFact, pair: pairing.Pair,
                   judged: Mapping[tuple[Id, Id], frozenset[Reason]] | None = None,
                   unanswerable: Callable[[Id, Id, Sequence[Id]], str] | None = None) -> Mapped:
    """R3/R4 (b.4): Q-ONLESION when the target row's SAME rests on the statement's lesions' places alone - the
    statement's single or listed target names a lesion, the act's names none (silent), and (DECISIONS D323 F1) the
    places and controls ``_onlesion_unanswerable`` reads leave the established answers exactly what the release arm
    needs; else CODER (a genuine doubt or contradiction of the act) or the census reason the answer could release
    nothing. ``unanswerable``: the plan's memo of ``_onlesion_unanswerable`` (``_Context.onlesion_unanswerable``: its
    what-if FactSet built once per (statement, act) per plan, DECISIONS D324 (8)); the function itself without one."""
    lesions = _single_target_lesions(R, pair.statement)
    act_lesion = facts_.fact(R, pair.act, _A.TARGET_LESION)
    if lesions is None or not facts_.silent(act_lesion) or pair.result(pairing.Row.TARGET) is not pairing.RowResult.SAME:
        return Mapped('R3/R4', blocked='R3/R4 genuine (CODER)')
    if _contradicted(R, pair.act):
        return Mapped('C1', blocked='C1')
    why = (unanswerable(pair.statement, pair.act, lesions) if unanswerable is not None
           else _onlesion_unanswerable(R, pair.statement, pair.act, lesions))
    if why:
        return Mapped('R3/R4', blocked=why)
    if any(facts_.pair_judged(R, judged or {}, pair.act, lesion) for lesion in lesions):
        return Mapped('C2b', blocked=ONLESION_JUDGED)
    specs = []
    for lesion in lesions:
        multiplicity = facts_.fact(R, lesion, _A.MULTIPLICITY)
        form = 'onlesion' if facts_.holds(multiplicity, Multiplicity.SINGLE) else 'onlesion.group'
        specs.append(QuestionSpec(Family.Q_ONLESION, form, (str(pair.act), str(lesion)), _A.TARGET_LESION,
                                  str(lesion), True, (str(pair.act), str(lesion)), census='R3/R4',
                                  witnesses=(_record(code, held),)))
    return Mapped('R3/R4', tuple(specs))


def event_class(R: FactSet, event: Id) -> rq.ObjectClass:
    """DECISIONS D314: the fact pass's object class of an event (claims.object_class, 3.2.1, read on the settled facts):
    STATEMENT when pass 1 filed its status negated (pairing.filed_as_statement - the one reading of it), else ACT. Read
    by _acts_of (a statement is no act an entry re-tells), performed_act and describe."""
    return rq.ObjectClass.STATEMENT if pairing.filed_as_statement(R, event) else rq.ObjectClass.ACT


def performed_act(R: FactSet, event: Id) -> bool:
    """DECISIONS D314: an event whose object class is ACT (event_class, the class _acts_of reads) and whose status is
    ESTABLISHED performed - the act was done. THE predicate of every act-form calibration item (K1, K2, K4:
    calibration_pool): "This act was (not) done ..." presupposes the act was done, so of a denial, a plan, an attempt or
    an act whose status is in doubt both sides flip together and the item is no longer known false."""
    return (event_class(R, event) is rq.ObjectClass.ACT
            and facts_.holds(facts_.fact(R, event, _A.STATUS), Status.PERFORMED))


_EVENT_STATUS: tuple[tuple[Status, qc.SubjectStatus], ...] = (
    (Status.PERFORMED, qc.SubjectStatus.PERFORMED), (Status.PLANNED, qc.SubjectStatus.PLANNED),
    (Status.ATTEMPTED_NOT_COMPLETED, qc.SubjectStatus.ATTEMPTED))
_UNLISTED_STATUS: Mapping[UnlistedWhat, qc.SubjectStatus] = {
    UnlistedWhat.ACT: qc.SubjectStatus.TELLS, UnlistedWhat.DENIAL: qc.SubjectStatus.DENIES,
    UnlistedWhat.DOUBT: qc.SubjectStatus.DOUBTS}


def event_status(R: FactSet, event: Id) -> qc.SubjectStatus:
    """DECISIONS D314: an event's status as a question's subject - DENIED (established negated), PERFORMED, PLANNED or
    ATTEMPTED (established at that value), else IN_DOUBT (unresolved, doubted, contradicted, unknown, silent, an open
    denial)."""
    status = facts_.fact(R, event, _A.STATUS)
    if status.result is Result.NEGATED:
        return qc.SubjectStatus.DENIED
    for value, found in _EVENT_STATUS:
        if facts_.holds(status, value):
            return found
    return qc.SubjectStatus.IN_DOUBT


def describe(R: FactSet, stored: str) -> qc.Described | None:
    """DECISIONS D314: the (object class, status) a question's subject is read as - an event by event_class and
    event_status; a kept unlisted entry ('u:<index>') by what it is (UnlistedWhat); a lesion by its multiplicity (SINGLE
    only when established single); a session, an anatomy entry and the encounter ('document') with no status. None for
    a subject the FactSet does not hold (never buildable)."""
    if stored == Named.DOCUMENT:
        return (qc.SubjectClass.ENCOUNTER, qc.SubjectStatus.NONE)
    index = unlisted_index((stored,))
    if index is not None:
        if 0 <= index < len(R.unlisted):
            return (qc.SubjectClass.UNLISTED, _UNLISTED_STATUS[R.unlisted[index].what])
        return None
    try:
        subject = Id.parse(stored)
    except ValueError:
        return None
    if subject.family is IdFamily.EVENT:
        if subject not in R.events:
            return None
        return (qc.SubjectClass(event_class(R, subject).value), event_status(R, subject))
    if subject.family is IdFamily.LESION:
        if subject not in R.lesions:
            return None
        single = facts_.holds(facts_.fact(R, subject, _A.MULTIPLICITY), Multiplicity.SINGLE)
        return (qc.SubjectClass.LESION, qc.SubjectStatus.SINGLE if single else qc.SubjectStatus.NOT_SINGLE)
    held = {IdFamily.SESSION: (R.sessions, qc.SubjectClass.SESSION),
            IdFamily.ANATOMY: (R.anatomy, qc.SubjectClass.ANATOMY)}.get(subject.family)
    if held is None or subject not in held[0]:
        return None
    return (held[1], qc.SubjectStatus.NONE)


def question_form(spec: QuestionSpec, described: Sequence[qc.Described | None]) -> str | None:
    """DECISIONS D318 (3) and its second addendum (the repair pass's RA-4): the form ``spec`` is ASKED in - the NARROWEST
    form exact for its subjects' descriptions, derived by contract/question_claims, ONE source, never a form the planner
    fixes. Q-REL's forms are several readings of one fact (the pair INDEPENDENT: a denial asks whether it denies the
    act, an open denial whether it denies it or casts doubt on it, a plan whether it plans or recommends it, any other
    statement whether it concerns it), so its form is question_claims.relation_form of the pair's (statement, act)
    descriptions - None when no form is exact for them; every other family's form names the fact and value it asks
    (one plain form per fact-pass FORMS key: question_claims' declaration) and is kept as built."""
    if spec.family is Family.Q_REL:
        return qc.relation_form(described)
    return spec.form


def described_spec(R: FactSet, spec: QuestionSpec) -> tuple[QuestionSpec | None, str]:
    """DECISIONS D314: ``spec`` with each subject's description (describe), in the form it is asked in (question_form,
    D318 (3): the narrowest exact form question_claims derives), or None and the census reason when no form of it is
    exact for them (question_claims.inexact: for a Q-REL pair, the concern form's reason, which the narrow forms' sides
    lie inside) - the held fact then stays held, never asked in a wrong sentence. Every question of a plan passes here
    (_exact_mapped) before any key, request or record reads it."""
    found = tuple(describe(R, stored) for stored in spec.subjects)
    form = question_form(spec, found) or spec.form
    why = qc.inexact(form, found)
    if why is not None:
        return None, f'D314 ({why})'
    return replace(spec, form=form, described=found), ''


def _exact_mapped(R: FactSet, item: Mapped) -> Mapped:
    """A witness's questions, each described (D314) - or the witness blocked whole by the first that is not exact."""
    if not item.specs:
        return item
    out = []
    for spec in item.specs:
        found, why = described_spec(R, spec)
        if found is None:
            return Mapped(item.row, blocked=why)
        out.append(found)
    return Mapped(item.row, tuple(out))


def _folds(R: FactSet, spec: QuestionSpec) -> bool:
    """Whether the fold (facts._fact_answer, through facts.folds) would apply an established answer to the Q-FACT
    question ``spec`` over ``R``: its fact answerable, its value not ruled out by an earlier negation answer, and every
    fixed-table check that reads the fact re-run with the answer in it (DECISIONS D324 (4))."""
    if spec.attribute is None:
        return False
    subject = facts_._subject_of(spec.subjects[0]) if spec.subjects else None
    if subject is None and spec.subjects and spec.subjects[0] != Named.DOCUMENT.value:
        return False
    return facts_.folds(R, subject, spec.attribute, spec.value, spec.negated)


def _folded_mapped(R: FactSet, item: Mapped) -> Mapped:
    """DECISIONS D324 (4) (round r3's integration int5, the fold lane's Q-F5 (d) and (f)): what the fold never folds is
    never asked. A Q-FACT question whose established answer the fold would refuse over the plan's FactSet (``_folds``:
    the fact not answerable, its value ruled out by an earlier negation, or a fixed-table check re-run with the answer
    in it failing - L1-02's reach among them) is dropped from its witness; a witness all of whose questions are dropped
    is blocked - no answer could release it - so the releasable filter reads it as it reads any blocked witness, and
    its held fact stays held. Every other family's question is kept as it is."""
    if not item.specs:
        return item
    kept = tuple(spec for spec in item.specs if spec.family is not Family.Q_FACT or _folds(R, spec))
    if len(kept) == len(item.specs):
        return item
    if not kept:
        return Mapped(item.row, blocked=f'{item.row} (the fold would refuse its answer: facts.folds)')
    return Mapped(item.row, kept)


def _acts_of(R: FactSet, session: Id | None) -> tuple[str, ...]:
    """The acts a kept unlisted entry may re-tell (b.7): the events of its session (every event that may be in it), or
    of the document when it names none - DECISIONS D324 (3), Q-ABSORB names only PERFORMED acts (L1-01): an event is
    listed only when ``performed_act`` holds (its object class ACT and its status ESTABLISHED performed), the predicate
    of every act-form calibration item (D314) and the class reading of denials this list always applied (a statement
    filed as one - negated status: event_class - is no act). A planned, attempted or in-doubt act is not listed, so an
    entry that tells or doubts it reads as "an act that is none of" the listed acts: the absorb claim is then false as
    worded and a true answer cannot absorb the entry (3.2.6 rule 3 refuses that absorption too: a planned or attempted
    event absorbs no unlisted act)."""
    out = []
    for event in R.events:
        if not performed_act(R, event):
            continue
        if session is None or session not in R.sessions or facts_.possibly(facts_.fact(R, event, _A.SESSION), session):
            out.append(str(event))
    return tuple(out)


def _absorb_spec(R: FactSet, code: str, held: HeldFact, index: int) -> Mapped:
    """Q-ABSORB (b.7) for kept unlisted entry ``index``: "This statement tells or doubts no act other than acts {A1},
    ..., {An}." over its session's PERFORMED acts (``_acts_of``; DECISIONS D324 (3)). Where no such list can be built -
    no act established performed that the entry may re-tell - the question is not asked and the entry holds."""
    entry = R.unlisted[index]
    acts = _acts_of(R, entry.session)
    if not acts:
        return Mapped('U3', blocked='U3 (no act to re-tell)')
    scope = str(entry.session) if entry.session is not None and entry.session in R.sessions else Named.DOCUMENT.value
    spec = QuestionSpec(Family.Q_ABSORB, 'absorb', (f'{UNLISTED_PREFIX}{index}',), None, '', False,
                        (f'{UNLISTED_PREFIX}{index}', f'{ACTS_PREFIX}{scope}'), acts=acts, census='U3',
                        witnesses=(_record(code, held),))
    return Mapped('U3', (spec,))


def _entry_index(R: FactSet, entry: object) -> int | None:
    for index, found in enumerate(R.unlisted):
        if found is entry or found == entry:
            return index
    return None


def _fact_spec(code: str, held: HeldFact, subject: Id | None, attribute: Attribute, value: object, row: str,
               negated: bool = False, form: str | None = None, names: tuple[str, ...] | None = None) -> QuestionSpec:
    stored = _stored(subject)
    subjects = (stored,) if stored is not None else (Named.DOCUMENT.value,)
    return QuestionSpec(Family.Q_FACT, form or f'fact.{attribute.value}', subjects, attribute, _value_of(value), negated,
                        names if names is not None else subjects, value_passage=value_passage_of(attribute), census=row,
                        witnesses=(_record(code, held),))


def _session_of(R: FactSet, event: Id) -> Id | None:
    found = facts_.fact(R, event, _A.SESSION)
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, Id) else None


def _rule_or_unread(held: HeldFact) -> bool:
    """A witness whose cause is a coding rule's (an established-value failure: B5) - or a label the cause table does not
    read, taken as one (fail-closed: the value rule then asks no value that leaves it standing)."""
    return whatif.cause_of(held).family in (_CF.CODING_RULE, _CF.OTHER)


# One what-if world of the value rule (DECISIONS D324 (8)): the fact (subject, attribute) established at a value - its
# key the subject, the attribute and the value's stored string - and that FactSet with its ONE coverage Reader, or None
# when the object is not held (_established_at).
_WorldKey = tuple[Id | None, Attribute, str]
_World = tuple[FactSet, coverage.Reader]


class _Context:
    """One plan's shared readings (DECISIONS D324 (8), the plan's cost): the FactSet and its ONE coverage Reader - its
    pairs, unlisted pairs and bundles, each computed once per plan and read by every candidate and every relation
    witness (whatif) - and the value rule's what-if worlds: each (subject, attribute, value) FactSet built ONCE, with
    ONE Reader of its own, and each candidate's witnesses over it evaluated ONCE, however many values, witnesses and
    codes ask about it (``moves``)."""

    def __init__(self, R: FactSet, events: Mapping[str, object] | None = None) -> None:
        self.R = R
        self.reader = coverage.Reader(R)
        self._worlds: dict[_WorldKey, _World | None] = {}
        self._evaluated: dict[tuple[_WorldKey, str, tuple[Kind, ...], Id], tuple[whatif.Witness, ...]] = {}
        self._onlesion: dict[tuple[Id, Id], str] = {}
        # while ``prefetch`` records: each what-if world's arguments and the candidates that ask it, in first-asked order
        self._recording: dict[_WorldKey, tuple[tuple[Id | None, Attribute, object],
                                               dict[tuple[str, tuple[Kind, ...], Id], whatif.Candidate]]] | None = None
        # the row's act-lesion records by (act, lesion) (facts.act_lesion_reasons): what pair_judged reads
        self.judged = facts_.act_lesion_reasons(events) if events is not None else {}
        # DECISIONS D328 (2): the row's question records so far (events.questions), read once per plan by contract/
        # settle.PairAnswers (built when a pair-family question is first planned), and each planned pair-family
        # question's verdict of ``unheld`` by its content key
        self.questions: tuple[Mapping[str, object], ...] = tuple(
            item for item in facts_._stored_list(events.get('questions')) if isinstance(item, Mapping)
        ) if events is not None else ()
        self._answers: object = None
        self._held: dict[str, bool] = {}

    def unheld(self, item: Mapped, before: frozenset[str]) -> Mapped:
        """DECISIONS D328 (2), the planner's half: ``item`` as it is, or its witness blocked whole (PAIR_HELD) when one of
        its pair-family questions not asked before would be asked of a pair an earlier answer holds - contract/settle.
        PairAnswers.holds over the row's question records so far, the pairs read on the plan's FactSet. A question asked
        before is never asked again (``plan``), so it is left to the plan as before."""
        if not item.specs or not self.questions:
            return item
        from studio.interpretation.contract import settle

        for spec in item.specs:
            if spec.family not in PAIR_FAMILIES or spec.key in before:
                continue
            held = self._held.get(spec.key)
            if held is None:
                if not isinstance(self._answers, settle.PairAnswers):
                    self._answers = settle.PairAnswers(self.questions, self.R)
                held = self._held[spec.key] = self._answers.holds(_record_fields(spec))
            if held:
                return Mapped(item.row, blocked=PAIR_HELD)
        return item

    def onlesion_unanswerable(self, statement: Id, act: Id, lesions: Sequence[Id]) -> str:
        """``_onlesion_unanswerable`` over the plan's FactSet, once per (statement, act) - its lesions are the
        statement's own (``_single_target_lesions`` on R), and its what-if (pairing.not_on_sets_apart: R with the
        not-on answers assumed, a FactSet of its own) is evaluated once per plan however many codes and witnesses read
        the pair (DECISIONS D324 (8))."""
        key = (statement, act)
        found = self._onlesion.get(key)
        if found is None:
            found = _onlesion_unanswerable(self.R, statement, act, lesions)
            self._onlesion[key] = found
        return found

    def world(self, subject: Id | None, attribute: Attribute, value: object) -> tuple[_WorldKey, _World | None]:
        """The what-if world of (subject, attribute) established at ``value``: built once per plan, with its own Reader
        (never another FactSet's), None when the object is not held."""
        key: _WorldKey = (subject, attribute, _value_of(value))
        if key not in self._worlds:
            changed = _established_at(self.R, subject, attribute, value)
            self._worlds[key] = None if changed is None else (changed, coverage.Reader(changed))
        return key, self._worlds[key]

    def witnesses_in(self, key: _WorldKey, world: _World, candidate: whatif.Candidate) -> tuple[whatif.Witness, ...]:
        """``candidate``'s witnesses over the world ``key`` - evaluated once per (world, code, group, event), through
        the world's own Reader."""
        memo = (key, candidate.code, candidate.group, candidate.event)
        found = self._evaluated.get(memo)
        if found is None:
            changed, reader = world
            found = whatif.candidate_witnesses(changed, candidate.code, candidate.group, candidate.event, reader)
            self._evaluated[memo] = found
        return found

    def prefetch(self, candidates: Iterable[whatif.Candidate]) -> None:
        """Evaluate, world by world, every what-if the classification of ``candidates``' witnesses asks (DECISIONS D324
        (8)): the classification is run once RECORDING (``moves`` notes each (world, candidate) and evaluates nothing;
        which what-ifs a witness asks never depends on another what-if's outcome), then each world is built once and
        evaluated for all its candidates in a row - so the engine's per-FactSet readings of a world (its pairs, its
        lesions' findings) are built once for it, never once per candidate while other worlds are read in between. The
        plan's own classification then reads every what-if from the memo. Its results are the same with or without
        this (a what-if it did not record is evaluated when asked)."""
        recorded: dict[_WorldKey, tuple[tuple[Id | None, Attribute, object], dict[tuple[str, tuple[Kind, ...], Id],
                                                                               whatif.Candidate]]] = {}
        self._recording = recorded
        try:
            for candidate in candidates:
                for witness in candidate.witnesses:
                    classify(self, candidate, witness)
        finally:
            self._recording = None
        for key, (made, asking_) in recorded.items():
            _key, world = self.world(*made)
            if world is None:
                continue
            for candidate in asking_.values():
                self.witnesses_in(key, world, candidate)

    def moves(self, candidate: whatif.Candidate, held: HeldFact, subject: Id | None, attribute: Attribute,
              value: object) -> bool:
        """The value rule's test (b.2: "ask v only when establishing v moves the witness toward T"): the candidate's
        witnesses recomputed over R with that fact established at ``value`` (the world, ``witnesses_in``: one
        evaluation per FactSet, DECISIONS D324 (8)) no longer hold this witness (its fact key, attribute and subject)
        AND hold no established-value failure (a coding_rule cause: B5) on its subject and attribute in its place - a
        value that makes the row FAIL (the CAUSE row's act_of_this_session or prophylaxis, read as bundled under
        another fact key) moves the witness toward F, never toward T. While ``prefetch`` records, the what-if is only
        noted (the answer given then is never read)."""
        if self._recording is not None:
            key = (subject, attribute, _value_of(value))
            entry = self._recording.setdefault(key, ((subject, attribute, value), {}))
            entry[1].setdefault((candidate.code, candidate.group, candidate.event), candidate)
            return True
        key, world = self.world(subject, attribute, value)
        if world is None:
            return False
        again = self.witnesses_in(key, world, candidate)
        return not any(w.held.attribute == held.attribute and w.held.subject == held.subject
                       and (w.held.fact == held.fact or _rule_or_unread(w.held)) for w in again)


def _record_fields(spec: QuestionSpec) -> dict[str, object]:
    """A planned question in the fields its stored record carries (contract/settle.settle_questions): family, form,
    subjects, attribute, value and negation - what settle.pair_held reads of it."""
    return {'family': spec.family.value, 'form': spec.form, 'subjects': list(spec.subjects),
            'attribute': spec.attribute.value if spec.attribute is not None else None, 'value': spec.value,
            'negated': spec.negated}


def _established_at(R: FactSet, subject: Id | None, attribute: Attribute, value: object) -> FactSet | None:
    """R with (subject, attribute) established at ``value`` - for a list attribute, its member of that value (added when
    absent) - for the value rule's moves-check; None when the object is not held."""
    domain = facts_.DOMAINS.get((subject.family if subject is not None else None, attribute))
    if domain is None:
        return None
    made = Fact(result=Result.SUPPORTED, value=value, state=FactState.SUPPORTED, options=(), reasons=(), spans=())  # type: ignore[arg-type]
    if subject is None:
        held = dict(R.encounter)
        held[attribute] = (made,)
        return replace(R, encounter=held)
    name = {IdFamily.EVENT: 'events', IdFamily.SESSION: 'sessions', IdFamily.LESION: 'lesions',
            IdFamily.SECTION: 'sections', IdFamily.ANATOMY: 'anatomy', IdFamily.PERSON: 'people'}.get(subject.family)
    if name is None:
        return None
    objects = getattr(R, name)
    if subject not in objects:
        return None
    held = dict(objects[subject])
    if domain.many:
        members = list(held.get(attribute, ()))
        at = next((index for index, member in enumerate(members) if member.value == value), None)
        if at is None:
            members.append(made)
        else:
            members[at] = replace(made, spans=members[at].spans, cited=members[at].cited)
        held[attribute] = tuple(members)
    else:
        current = held.get(attribute, (facts_.SILENT,))[0]
        held[attribute] = (replace(made, spans=current.spans, cited=current.cited, inherited_from=current.inherited_from),)
    return replace(R, **{name: {**objects, subject: held}})


def _askable_open(found: Fact) -> bool:
    """A fact a question may be asked of (b.2's value rule): not established; not contradicted unless by a cross-object
    conflict (C6); not judged by the fact pass (C2b); its object located (C4); and not demoted by L1's date check
    (literal_mismatch, literal_unchecked: a check of the act's own date words, never a reading). ONE predicate with
    settle's re-check (``eligible``) and the fold (round r3's integration, the engine lane's Q-R1 and Q-R3):
    engine/facts.answerable - so the planner never asks what no answer could ever establish (R3BE-RF1's planner half)."""
    return facts_.answerable(found)


def _claimed_values(found: Fact, with_options: bool) -> tuple[object, ...]:
    values = [found.value] if found.value is not None else []
    if with_options:
        values += [option for option in found.options if option not in values]
    return tuple(values)


def _fact_of(R: FactSet, held: HeldFact) -> Fact | None:
    if held.attribute is None:
        return None
    domain = facts_.DOMAINS.get((held.subject.family if held.subject is not None else None, held.attribute))
    if domain is None:
        return None
    if domain.many:
        members = facts_.members(R, held.subject, held.attribute)
        open_ = [member for member in members if not facts_.established(member)]
        return open_[0] if open_ else (members[0] if members else facts_.SILENT)
    return facts_.fact(R, held.subject, held.attribute)


def _family_sessions(R: FactSet, code: str) -> tuple[Id, ...]:
    family = catalogue.code_link(code).family
    if not isinstance(family, SessionKind):
        return ()
    return tuple(session for session in R.sessions if facts_.holds(facts_.fact(R, session, _A.KIND), family))


_EXTENT_ORDER: Mapping[Extent, int] = {extent: number for number, extent in enumerate(Extent)}


def _reach_values(code: str) -> tuple[Extent, ...]:
    """The reaches that satisfy a code's extent row: COLFULL's full colonoscopy reach; R6:extent's any reached point."""
    if Tag.COLFULL in rq.spec(code).tags:
        return tuple(sorted(catalogue.COLONOSCOPY_FULL_REACH, key=lambda item: _EXTENT_ORDER[item]))
    return tuple(Extent)


def _silent_reach_values(code: str) -> tuple[Extent, ...]:
    """A3's values for a SILENT reach list (round r3's integration, the second refutation's ASK2-1, the class rule: every
    value a question asks is one its subject's own family can hold, read from the catalogue's billing tables, never every
    member of an enumeration): COLFULL's full colonoscopy reach (catalogue.COLONOSCOPY_FULL_REACH), as before;
    R6:extent's points (any reached point satisfies its row) only where the code's own family reaches - every Extent
    whose region (anatomy.region) is one catalogue.FAMILY_REACH (K3's table) gives catalogue.family_for_code(code); a
    family the table holds no reach for gives none (the witness stays held, its census reason B5).

    DECISIONS D324 (8) (the plan's cost: no per-value what-if is paid for a filter that cannot drop a value - ASK2-1's
    moves filter goes): an enteroscopy code's CLASS reads the reach too (classes' REACH part: a point of its class's
    reach, catalogue.ENTEROSCOPY_CLASS_REACH - "not including ileum" for the jejunal class, the ileal points for the
    deeper ones - and nothing beyond it), so its values are only the family's points its class's reach table holds:
    every value given here then satisfies every row that reads the reach when established, which the moves filter
    tested per value and per candidate (it dropped exactly the others: the jejunal class's ileal points and the small
    bowel, the deeper classes' jejunum and small bowel). Pinned over every code of the catalogue by the filter's own
    what-if (tests/v2/test_r3c_ask). ``_outer_reach`` keeps only the outermost of them."""
    if Tag.COLFULL in rq.spec(code).tags:
        return _reach_values(code)
    regions = catalogue.FAMILY_REACH.get(catalogue.family_for_code(code), frozenset())
    found = tuple(extent for extent in Extent if anatomy.region(extent) in regions)
    exam_class = catalogue.code_class(code)
    if exam_class is None:
        return found
    needed = catalogue.ENTEROSCOPY_CLASS_REACH[exam_class]
    return tuple(extent for extent in found if extent in needed)


def _outer_reach(values: Sequence[Extent]) -> tuple[Extent, ...]:
    """ASK2-1: the values no other of ``values`` contains (anatomy.contains), in Extent order. Each value given here
    moves the witness toward T (b.2's value rule, necessary: ``_silent_reach_values`` gives no other - DECISIONS D324
    (8)), and pass 1's reach is "at its furthest point or on its way beyond it", so a deeper point the endoscope reached
    establishes the outer point that contains it: asking the outer points alone loses no release, and an EGD with a
    silent reach list asks the esophagus, the stomach and the duodenum - one request - never the enumeration's fifty-one
    (about $36 reserved for a short note)."""
    return tuple(sorted((value for value in values
                         if not any(other is not value and anatomy.contains(other, value) for other in values)),
                        key=lambda item: _EXTENT_ORDER[item]))


def _full_anatomy(R: FactSet) -> tuple[Id, ...]:
    return tuple(entry for entry in R.anatomy
                 if facts_.fact(R, entry, _A.SUBTYPE).result is Result.SUPPORTED
                 and facts_.fact(R, entry, _A.SUBTYPE).value in catalogue.COLONOSCOPY_FULL_SUBTYPES)


def _extent_specs(ctx: _Context, candidate: whatif.Candidate, held: HeldFact, row: str) -> Mapped:
    """F8 / A3 on a session's extent row (b.2 value rule): each reached member the row needs that is unestablished for an
    F1-F5, C2a or C6 reason (its claimed value; a doubt's readings), and, for COLFULL, the reached anatomy - silent, an
    anatomy entry whose established subtype satisfies the row - each a question; with a silent reach list, every
    satisfying reach (A3). None asked: blocked."""
    R, session = ctx.R, held.subject
    if session is None or session.family is not IdFamily.SESSION:
        return Mapped(row, blocked='B5')
    wanted = set(_reach_values(candidate.code))
    specs: list[QuestionSpec] = []
    reached = facts_.members(R, session, _A.REACHED)
    for member in reached:
        if not _askable_open(member):
            continue
        for value in _claimed_values(member, True):
            if value in wanted:
                specs.append(_fact_spec(candidate.code, held, session, _A.REACHED, value, 'F8'))
    anatomy_fact = facts_.fact(R, session, _A.REACHED_ANATOMY)
    if Tag.COLFULL in rq.spec(candidate.code).tags and _askable_open(anatomy_fact):
        entries = _full_anatomy(R) if facts_.silent(anatomy_fact) else tuple(
            value for value in _claimed_values(anatomy_fact, True) if value in _full_anatomy(R))
        for entry in entries:
            specs.append(_fact_spec(candidate.code, held, session, _A.REACHED_ANATOMY, entry, 'F8'))
    if not reached and not specs:
        # ASK2-1: the family's own points, the outermost of them. DECISIONS D324 (8): no per-value what-if - every value
        # _silent_reach_values gives satisfies each row that reads the reach (the moves filter could drop none of them)
        for value in _outer_reach(_silent_reach_values(candidate.code)):
            specs.append(_fact_spec(candidate.code, held, session, _A.REACHED, value, 'A3'))
    if not specs:
        return Mapped(row, blocked='B5 (no reach to ask)')
    return Mapped(row, tuple(specs))


def _values_spec(ctx: _Context, candidate: whatif.Candidate, held: HeldFact, row: str, with_options: bool) -> Mapped:
    """The value rule for a claimed (or doubted) fact (F1, F3, F4, F5, C2a, C6): each value pass 1 claimed (with the
    doubt's readings, or the conflicting readings) that moves the witness toward T, one question each. C6's row (a
    cross-object conflict) reads the one askable test too (round r3's integration int5, the fold lane's Q-F5 (c)):
    facts.answerable already answers a fact contradicted by a conflict, and a fact a fixed-table check demoted beside
    one is never folded (DECISIONS D324 (4)), so it is never asked."""
    R = ctx.R
    attribute = held.attribute
    if attribute is None or attribute not in FACT_ATTRIBUTES:
        return Mapped(row, blocked=f'{row} (no question template for {attribute.value if attribute else "-"})')
    if attribute in _SEPARATION_ONLY:
        return Mapped(row, blocked=f'{row} (no value template for {attribute.value}: asked only in its separation form)')
    found = _fact_of(R, held)
    if found is None:
        return Mapped(row, blocked=f'{row} (no fact)')
    if not _askable_open(found):
        return Mapped(row, blocked=f'{row} (the fact is not askable)')
    specs = []
    for value in _claimed_values(found, with_options):
        if ctx.moves(candidate, held, held.subject, attribute, value):
            specs.append(_fact_spec(candidate.code, held, held.subject, attribute, value, row))
    if not specs:
        return Mapped(row, blocked=f'{row} (no satisfying value)')
    return Mapped(row, tuple(specs))


def _silent_spec(ctx: _Context, candidate: whatif.Candidate, held: HeldFact) -> Mapped:
    """F2 / A3 on a silent slot (b.2 value rule): ENTRY, the date relation and the performer have one satisfying value;
    the act's own session the code family's sessions (one: F2; several: A3); the reach rows are _extent_specs'. Any
    other silent slot is ABSENT (CENSUS-v2 A3 is built for the reach, the reached anatomy and the session only)."""
    R, attribute = ctx.R, held.attribute
    if attribute in _ONE_VALUE:
        value = _ONE_VALUE[attribute]
        if ctx.moves(candidate, held, held.subject, attribute, value):
            return Mapped('F2', (_fact_spec(candidate.code, held, held.subject, attribute, value, 'F2'),))
        return Mapped('F2', blocked='F2 (no satisfying value)')
    if attribute is _A.SESSION and held.subject == candidate.event:
        sessions = [session for session in _family_sessions(R, candidate.code)
                    if ctx.moves(candidate, held, held.subject, attribute, session)]
        if sessions:
            row = 'F2' if len(sessions) == 1 else 'A3'
            return Mapped(row, tuple(_fact_spec(candidate.code, held, held.subject, _A.SESSION, session, row,
                                                names=(str(held.subject), str(session))) for session in sessions))
        return Mapped('F2', blocked='F2 (no session of the family)')
    if attribute in (_A.REACHED, _A.REACHED_ANATOMY):
        return _extent_specs(ctx, candidate, held, 'A3')
    return Mapped('A3', blocked=f'ABSENT (silent {attribute.value if attribute else "-"}: not asked)')


# DECISIONS D315 (6), D320: G1 is asked only of an examination ESTABLISHED performed or planned - of an attempt, "This
# act was not done during session X." is true as worded while the engine's fact (not X's examination) is false; of an
# act whose status is in doubt (it may be an attempt) it may be. ONE source (round r3's integration, the ask lane's Q3):
# that exact set is contract/question_claims' declaration for fact.session.not (DONE_OR_PLANNED_ACT, D314 (1)'s
# mechanism), read by D314's own check (described_spec) for every subject - an attempt, an act in doubt and a denial
# alike leave G1 unasked with its D314 census reason. The planner keeps no second copy of the set.


def _row7_tie(ctx: _Context, candidate: whatif.Candidate, held: HeldFact) -> Mapped | None:
    """Census gap G1 (module docstring): a row-7 witness about an event that MAY be the candidate's session's
    examination without being established as it - released by "This act was not done during session {X}." (Q-FACT,
    the release direction a negation, its exact negation the control). None when the witness is not that. Asked only
    of an examination whose status is established performed or planned (DECISIONS D315 (6)): question_claims' declared
    set for fact.session.not, which D314's check (described_spec) reads - of any other the witness is blocked with its
    D314 census reason and the held fact stays held."""
    R = ctx.R
    exam = held.subject
    if exam is None or exam.family is not IdFamily.EVENT or exam == candidate.event:
        return None
    session = _session_of(R, candidate.event)
    if session is None:
        return None
    if exam not in evaluate.examinations(R, session) or evaluate.is_examination_of(R, exam, session):
        return None
    tie = facts_.fact(R, exam, _A.SESSION)
    if not facts_.answerable(tie):  # int5, the fold lane's Q-F5 (a): what the fold never folds is never asked
        return Mapped('G1', blocked='G1 (tie contradicted, established or not answerable)')
    spec = _fact_spec(candidate.code, held, exam, _A.SESSION, session, 'G1', negated=True, form='fact.session.not',
                      names=(str(exam), str(session)))
    return Mapped('G1', (spec,))


def _bundling_spec(ctx: _Context, candidate: whatif.Candidate, held: HeldFact) -> Mapped | None:
    """F11 / F12 (b.2's part-link, cause and lift-purpose rows; b.8's silent links): a bundling doubt on a part's part_of,
    cause or purpose, asked in the release direction - the part_of's universal negation, the cause's negation and the
    hemostasis premise's negation, the lift purpose's negation. None for any other bundling witness."""
    R, part, attribute = ctx.R, held.subject, held.attribute
    cause = whatif.cause_of(held)
    open_ = (cause.family is _CF.READING_UNKNOWN or (cause.family is _CF.UNESTABLISHED and cause.reason is not None)
             or (cause.family is _CF.APPRAISAL and cause.verdict in _C2A_VERDICTS))
    if part is None or part.family is not IdFamily.EVENT or not open_:
        return None
    if attribute in (_A.PART_OF, _A.PART_RELATION):
        # a part_relation doubt is a conjunct of the same by-part arm: "not part of another act" makes the arm F, so it
        # is released by the same question (coverage._lift's and _adjunct's by-part arms)
        found = facts_.fact(R, part, _A.PART_OF)
        if found.result is Result.CONTRADICTED or not facts_.answerable(found):  # int5, Q-F5 (b)
            return Mapped('F11', blocked='F11 (link established or contradicted)')
        return Mapped('F11', (_fact_spec(candidate.code, held, part, _A.PART_OF, None, 'F11', negated=True,
                                         form='fact.part_link.any'),))
    if attribute in (_A.CAUSE, _A.CAUSE_EVENT):
        found = facts_.fact(R, part, _A.CAUSE)
        if found.result is Result.CONTRADICTED or not facts_.answerable(found):  # int5, Q-F5 (b)
            return Mapped('F12', blocked='F12 (cause established or contradicted)')
        specs = [_fact_spec(candidate.code, held, part, _A.CAUSE, 'act_of_this_session', 'F12', negated=True,
                            form='fact.cause.not')]
        purpose = facts_.fact(R, part, _A.PURPOSE)
        if purpose.result is not Result.CONTRADICTED and facts_.answerable(purpose):  # int5, Q-F5 (b)
            specs.append(_fact_spec(candidate.code, held, part, _A.PURPOSE, 'hemostasis', 'F12', negated=True,
                                    form='fact.hemostasis.not'))
        return Mapped('F12', tuple(specs))
    if attribute is _A.PURPOSE:
        found = facts_.fact(R, part, _A.PURPOSE)
        if found.result is Result.CONTRADICTED or not facts_.answerable(found):  # int5, Q-F5 (b)
            return Mapped('F11', blocked='F11 (purpose established or contradicted)')
        return Mapped('F11', (_fact_spec(candidate.code, held, part, _A.PURPOSE, 'lift_for_resection', 'F11',
                                         negated=True, form='fact.lift.not'),))
    return None


def classify(ctx: _Context, candidate: whatif.Candidate, witness: whatif.Witness) -> Mapped:
    """One witness's census row (CENSUS-v2 section 1) and its questions (module docstring). The witness's cause is read
    typed (whatif.cause_of), in the prototype's order; a cause the table does not read is blocked first (fail-closed)."""
    R, held, code = ctx.R, witness.held, candidate.code
    cause = whatif.cause_of(held)
    family = cause.family
    if family is _CF.OTHER:
        return Mapped('X', blocked=f'unclassified ({held.cause})')
    if family is _CF.RELATION:
        if not witness.pairs:
            return Mapped('R?', blocked='relation without its pair')
        unresolved = cause.possible_statement or cause.relation is pairing.Relation.UNRESOLVED
        held_apart = cause.possible_statement or cause.relation in (pairing.Relation.DOUBT,
                                                                     pairing.Relation.CONTRADICTION)
        out: list[QuestionSpec] = []
        for pair in witness.pairs:
            if any(Reason.ANCHOR_INVALID in facts_.fact(R, side, _A.KIND).reasons
                   for side in (pair.statement, pair.act) if isinstance(side, Id) and side in R.events):
                return Mapped('C4', blocked='C4 (a side of the pair does not locate: anchor_invalid)')
            if witness.source is whatif.WitnessSource.BUNDLING or (
                    held.attribute is _A.STATUS and witness.source is not whatif.WitnessSource.SUPPORT):
                return Mapped('C3', blocked='C3 (the whole\'s status)')
            if unresolved and pair.relation is pairing.Relation.UNRESOLVED:
                mapped = _rel_spec(R, code, held, pair)
            elif held_apart:
                mapped = _onlesion_spec(R, code, held, pair, ctx.judged, ctx.onlesion_unanswerable)
            else:
                return Mapped('R?', blocked=f'relation {cause.relation.value if cause.relation else "-"}')
            if not mapped.specs:
                return mapped
            out.extend(mapped.specs)
        return Mapped(out[0].census, tuple(out))
    if family is _CF.UNLISTED:
        if witness.unlisted:
            specs = []
            for item in witness.unlisted:  # the concern form until described_spec narrows it (question_form)
                specs.append(QuestionSpec(Family.Q_REL, 'rel', (f'{UNLISTED_PREFIX}{item.index}', str(item.act)), None,
                                          '', False, (f'{UNLISTED_PREFIX}{item.index}', str(item.act)), census='U1',
                                          witnesses=(_record(code, held),)))
            return Mapped('U1', tuple(specs))
        if witness.entries:
            specs = []
            for entry in witness.entries:
                index = _entry_index(R, entry)
                if index is None:
                    return Mapped('U?', blocked='unlisted entry not found')
                mapped = _absorb_spec(R, code, held, index)
                if not mapped.specs:
                    return mapped
                specs.extend(mapped.specs)
            return Mapped('U3', tuple(specs))
        return Mapped('U2', blocked='U2 (rule 2 on the kept evidence: no proposal at question time)')
    if family is _CF.READING_CONTRADICTED:
        return Mapped('C1', blocked='C1')
    if family is _CF.APPRAISAL:
        if cause.verdict in _C2A_VERDICTS:
            tie = _row7_tie(ctx, candidate, held)
            if tie is not None:
                return tie
            return _values_spec(ctx, candidate, held, 'C2a', False)
        return Mapped('C2b', blocked='C2b (FABLE: Fable already judged it)')
    if family is _CF.CONTEXT_MISSING:
        return Mapped('A2', blocked='A2 (member context)')
    if family is _CF.DATE_UNKNOWN:
        return Mapped('F9', blocked='F9/A4 (the date of service: not built in the prototype)')
    if witness.source is whatif.WitnessSource.BUNDLING:
        found = _bundling_spec(ctx, candidate, held)
        if found is not None:
            return found
    if family is _CF.CODING_RULE:
        rule = cause.rule
        if rule is questions.Rule.UMBRELLA:
            return Mapped('F7', blocked='F7 (Q-KIND: not built in the prototype)')
        if rule in (Tag.COLFULL, Tag.R6_EXTENT):
            return _extent_specs(ctx, candidate, held, 'F8')
        if rule is questions.Rule.EXAMINATION:
            tie = _row7_tie(ctx, candidate, held)
            if tie is not None:
                return tie
            return Mapped('B5', blocked='B5 (an established examination fails row 7)')
        if rule is questions.Rule.NOT_DOCUMENTED:
            return Mapped('A1', blocked='A1')
        if rule is questions.Rule.STOMA_ROUTE:  # D310 (1): the colonoscopy route table (evaluate._row_colon_route)
            if held.attribute is _A.TYPE and held.result is None:
                return Mapped('A1', blocked='ABSENT (no anatomy entry may be a stoma: the route table)')
            return Mapped('B5', blocked='B5 (an established approach fails the route table)')
        if rule is questions.Rule.STATEMENT_SCOPE:
            return Mapped('C5', blocked='C5')
        return Mapped('B', blocked=f'BILLING ({cause.label})')
    if held.attribute is _A.STATUS:
        return Mapped('C3', blocked='C3 (whether the act happened)')
    if held.attribute is _A.KIND:
        tie = _row7_tie(ctx, candidate, held)
        if tie is not None:
            return tie
        return Mapped('F7', blocked='F7 (a kind not established: Q-KIND not built in the prototype)')
    tie = _row7_tie(ctx, candidate, held)
    if tie is not None:
        return tie
    if family is _CF.UNESTABLISHED and cause.reason is not None:
        why = cause.reason
        if why is Reason.ANCHOR_INVALID:
            return Mapped('C4', blocked='C4')
        if why is Reason.CARDS_INDISTINCT:
            return Mapped('F6', blocked='F6 (Q-GROUP: not built in the prototype)')
        if held.reason in _CONFLICTS:
            return _values_spec(ctx, candidate, held, 'C6', True)
        if why in _QUALIFIED:
            return _values_spec(ctx, candidate, held, 'F5', False)
        if why is Reason.UNAPPRAISED:
            return _values_spec(ctx, candidate, held, 'F4', False)
        if held.attribute in (_A.REACHED, _A.REACHED_ANATOMY):
            return _extent_specs(ctx, candidate, held, 'F1')
        return _values_spec(ctx, candidate, held, 'F1', False)
    if family is _CF.READING_UNKNOWN:
        if held.reason is Reason.SILENT:
            return _silent_spec(ctx, candidate, held)
        return _values_spec(ctx, candidate, held, 'F3', True)
    return Mapped('X', blocked=f'unclassified ({held.cause})')


# --- the plan (a.4) -----------------------------------------------------------------------------------------------------


def _merged(found: QuestionSpec, other: QuestionSpec) -> QuestionSpec:
    witnesses = tuple(dict.fromkeys((*found.witnesses, *other.witnesses)))
    return replace(found, witnesses=witnesses)


def _order_key(R: FactSet, spec: QuestionSpec) -> tuple:
    """e.3's order: the first object's place (events in pass 1's order, then sessions, lesions, unlisted entries),
    then the content key."""
    order = {str(event): index for index, event in enumerate(R.events)}
    base = len(order)
    order.update({str(session): base + index for index, session in enumerate(R.sessions)})
    base = len(order)
    order.update({str(lesion): base + index for index, lesion in enumerate(R.lesions)})
    first = spec.subjects[0] if spec.subjects else ''
    index = unlisted_index((first,))
    place = 100000 + index if index is not None else order.get(first, 200000)
    return (place, spec.key)


def lesion_pair_specs(events: Mapping[str, object] | None, R: FactSet) -> tuple[QuestionSpec, ...]:
    """b.3: the fact request's lesion pairs (events.lesion_pairs) re-asked as Q-LESION with proof - those the fact pass
    established (proof is what is missing), left without a usable verdict (appraisal_missing, appraisal_detached) or
    dropped at its bound (unappraised); never one it judged in the holding direction or abstained on. DECISIONS D320 and
    D323 O1: Q-LESION is NOT shipped (never sent to Fable) and b.3 is reverted - the fact pass's lesion pairs establish
    as on int3 - so ``plan`` asks no lesion-pair question and calls this nowhere; it is kept as the prototype built it,
    read by nothing in the build."""
    if not events:
        return ()
    claims = {item.get('id'): item for item in events.get('claims') or () if isinstance(item, Mapping)}
    out = []
    for item in events.get('lesion_pairs') or ():
        if not isinstance(item, Mapping):
            continue
        reasons = set(item.get('reasons') or ())
        if item.get('result') != Result.SUPPORTED.value and not reasons <= {'appraisal_missing', 'appraisal_detached',
                                                                            'unappraised'}:
            continue
        claim = claims.get(item.get('claim')) if item.get('claim') is not None else None
        form = claim.get('template') if isinstance(claim, Mapping) else 'lesion.distinct_from'
        lesion, other = str(item.get('lesion')), str(item.get('other'))
        out.append(QuestionSpec(Family.Q_LESION, str(form), (lesion, other), _A.DISTINCT_FROM, other, False,
                                (lesion, other), census='P1-LESION'))
    return tuple(out)


def names_carded(names: Iterable[str], acts: Iterable[str], carded: Callable[[str], bool]) -> bool:
    """Every object a question or calibration item names has a card in the fact request (its passage exists): the
    document always; 'acts:<scope>' through the acts it names."""
    for name in names:
        if name == Named.DOCUMENT:
            continue
        if _after(name, _Mark.ACTS) is not None:
            if not all(carded(act) for act in acts):
                return False
        elif not carded(name):
            return False
    return True


C4_NO_CARD = 'C4 (an object the question names has no card in the fact request: it does not locate)'


def plan(R: FactSet, asked_before: Iterable[str] = (), events: Mapping[str, object] | None = None,
         carded: Callable[[str], bool] | None = None) -> Plan:
    """One round's plan over R (module docstring; a.4): the questions of every releasable candidate of every candidate
    code, deduplicated, none asked before. ``events`` (the row's text-free events): since DECISIONS D323 O1 no
    lesion-pair question (Q-LESION, b.3) is asked; since round r3's integration its act-lesion records are read, so no
    Q-ONLESION question is asked over a pair the fact pass judged (facts.pair_judged; the engine lane's Q-R2).
    ``carded`` (the stage's: question_claims.carded) answers whether an object has a card in the fact request; a
    witness whose question would name an object with none is C4 - it has no passage, so no proof could ever locate (an
    event whose anchor failed I3 is never carded) - and never reaches a request."""
    before = frozenset(asked_before)
    ctx = _Context(R, events)
    specs: dict[str, QuestionSpec] = {}
    serves: dict[str, set[str]] = {}
    blocked: Counter[str] = Counter()
    releasable: Counter[str] = Counter()
    # DECISIONS D324 (8): every candidate's witnesses over R once (the plan's one Reader), then every what-if world the
    # classification asks evaluated world by world (``_Context.prefetch``) before the classification reads them
    candidates = [(code, whatif.witnesses(R, code, ctx.reader)) for code in whatif.candidate_codes(R)]
    ctx.prefetch(candidate for _code, found in candidates for candidate in found)
    for code, found in candidates:
        for candidate in found:
            mapped = [classify(ctx, candidate, witness) for witness in candidate.witnesses]
            if carded is not None:
                mapped = [Mapped('C4', blocked=C4_NO_CARD) if item.specs and not all(
                    names_carded(spec.names, spec.acts, carded) for spec in item.specs) else item for item in mapped]
            # DECISIONS D314: a question whose form is not exact for its subjects' class and status is never asked: the
            # witness is blocked with its census reason (the held fact stays held), never put in a wrong sentence
            mapped = [_exact_mapped(R, item) for item in mapped]
            # DECISIONS D324 (4) (int5, the fold lane's Q-F5): what the fold never folds is never asked (or paid for)
            mapped = [_folded_mapped(R, item) for item in mapped]
            # DECISIONS D328 (2): a pair is asked through another family only when no earlier answer about it holds it
            mapped = [ctx.unheld(item, before) for item in mapped]
            stops = [item.blocked for item in mapped if item.blocked]
            if stops:
                for stop in dict.fromkeys(stops):
                    blocked[stop] += 1
                continue
            if not candidate.witnesses:
                continue
            releasable[code] += 1
            for item in mapped:
                for spec in item.specs:
                    if spec.key in before:
                        continue
                    specs[spec.key] = _merged(specs[spec.key], spec) if spec.key in specs else spec
                    serves.setdefault(spec.key, set()).add(code)
    ordered = tuple(sorted(specs.values(), key=lambda spec: _order_key(R, spec)))
    return Plan(specs=ordered, serves={key: frozenset(codes) for key, codes in serves.items()},
                blocked=dict(blocked), releasable=dict(releasable))


# --- calibration (b.9) --------------------------------------------------------------------------------------------------

# K1's attributes (b.9): an act's date relation on the date of service, entry, performer and session - each item's FORM is
# the fact pass's own for (the event's object class, the attribute, supported): question_claims.form_of, never an
# attribute-only table (DECISIONS D314)
_K1_ATTRIBUTES: tuple[Attribute, ...] = (_A.DATE_RELATION, _A.ENTRY, _A.PERFORMER, _A.SESSION)


# DECISIONS D315 (1): the session kinds of an endoscopic procedure - the only kinds a K2 item's two sessions may have.
# DECISIONS D317 (4): ONE table - it IS catalogue.ENDOSCOPIC_FAMILIES (the families an endoscope examines in a session),
# never a copy that could drift from it (pinned with ``is``).
PROCEDURE_SESSION_KINDS: frozenset[SessionKind] = catalogue.ENDOSCOPIC_FAMILIES


def procedure_session(R: FactSet, session: Id) -> bool:
    """DECISIONS D315 (1): a session that TOOK PLACE as an endoscopic procedure of its own - all three:
    - its kind is SUPPORTED and one of PROCEDURE_SESSION_KINDS (EGD, enteroscopy, colonoscopy, flexible sigmoidoscopy,
      EUS, ERCP);
    - at least one act established performed (``performed_act``) has its session fact holding this session;
    - it has no part_of_session claim (silent).
    Why, the presupposition on the OBJECT: K2 says "This act was done during session X." of an act whose established
    session is another. That is known false only when X is another session that took place AND excludes the act's own.
    A session that never took place (its examination denied, a planned future session) makes the claim false only by
    its presupposition - a reader of intent may take X for the act's own procedure and support it. A sedation service,
    an office or other visit of the same encounter, a non-GI or unsettled session (its kind unresolved or not a
    procedure), or a part of another session may CONTAIN the act, so the claim can be true. Read by exclusive_sessions
    alone (the K2 draw)."""
    kind = facts_.fact(R, session, _A.KIND)
    if kind.result is not Result.SUPPORTED or kind.value not in PROCEDURE_SESSION_KINDS:
        return False
    if not facts_.silent(facts_.fact(R, session, _A.PART_OF_SESSION)):
        return False
    return any(performed_act(R, event) and facts_.holds(facts_.fact(R, event, _A.SESSION), session)
               for event in R.events)


# One act's established occasion (DECISIONS D317 (4)): its date relation and its date, each when established supported
_Occasion = tuple[DateRelation | None, IsoDate | None]


def _occasions(R: FactSet, session: Id) -> tuple[_Occasion, ...]:
    """The established occasions of the acts established performed in ``session`` (``performed_act``, its session
    fact holding it): each act's date relation and date where pass 2 established them (supported) - an act whose
    occasion is not established adds none."""
    out: list[_Occasion] = []
    for event in R.events:
        if not (performed_act(R, event) and facts_.holds(facts_.fact(R, event, _A.SESSION), session)):
            continue
        relation = facts_.fact(R, event, _A.DATE_RELATION)
        date = facts_.fact(R, event, _A.DATE)
        found = (relation.value if relation.result is Result.SUPPORTED and isinstance(relation.value, DateRelation)
                 else None,
                 date.value if date.result is Result.SUPPORTED and isinstance(date.value, IsoDate) else None)
        if found != (None, None):
            out.append(found)
    return tuple(out)


def _period(date: IsoDate) -> tuple[datetime.date, datetime.date]:
    """The days an IsoDate at its precision may be: the day; the month's days; the year's days."""
    day = date.value
    if date.precision is Precision.DAY:
        return day, day
    if date.precision is Precision.MONTH:
        return day, datetime.date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
    return day, datetime.date(day.year, 12, 31)


def _apart_in_time(one: _Occasion, other: _Occasion) -> bool:
    """Two established occasions on different dates: their date relations established and different (the date of
    service, an earlier date, a later date exclude each other), or their dates established and their periods disjoint
    at the precision each is stated at."""
    if one[0] is not None and other[0] is not None and one[0] is not other[0]:
        return True
    if one[1] is not None and other[1] is not None:
        first, second = _period(one[1]), _period(other[1])
        return first[1] < second[0] or second[1] < first[0]
    return False


def separate_occasions(R: FactSet, own: Id, other: Id) -> bool:
    """DECISIONS D317 (4): two sessions of ESTABLISHED DIFFERENT DATES or SEPARATE ENCOUNTERS - their encounter facts
    both supported and different (this encounter, a separate one), or each with an established occasion (``_occasions``)
    and every occasion of one apart from every occasion of the other (``_apart_in_time``). Two procedure sessions of one
    kind filed for one examination - or two of the same day in one encounter - meet neither: no K2 between them. Read
    by exclusive_sessions alone."""
    encounters = [facts_.fact(R, session, _A.ENCOUNTER) for session in (own, other)]
    if all(found.result is Result.SUPPORTED and isinstance(found.value, EncounterRelation) for found in encounters) and \
            encounters[0].value is not encounters[1].value:
        return True
    mine, theirs = _occasions(R, own), _occasions(R, other)
    return bool(mine) and bool(theirs) and all(_apart_in_time(one, two) for one in mine for two in theirs)


def exclusive_sessions(R: FactSet, own: Id, other: Id) -> bool:
    """DECISIONS D315 (1), THE ONE PREDICATE of K2's alternative: ``other`` may be named in "This act was done during
    session {other}." of an act whose established session is ``own`` only when the two are different sessions and BOTH
    are procedure sessions that took place (``procedure_session``) - two exclusive sessions that took place, so the
    claim is false under every reading of each session it names - and (DECISIONS D317 (4)) of established different
    dates or separate encounters (``separate_occasions``). Read by the K2 draw only (calibration_pool)."""
    return (own != other and procedure_session(R, own) and procedure_session(R, other)
            and separate_occasions(R, own, other))


# --- DECISIONS D317 (1): the member line ----------------------------------------------------------------------------------

_END = 1 << 62  # past the end of any revision: a side that runs to the document's end
_Range = tuple[int, int]  # [start, end) in the revision's offsets
# the kept unlisted entries that may BE such a statement: one that doubts or tells acts (a denial gives no performer)
_LINE_KINDS: frozenset[UnlistedWhat] = frozenset({UnlistedWhat.DOUBT, UnlistedWhat.ACT})


def _reads_another(found: Fact, documenting: Enum) -> bool:
    """A performer or owner fact whose documenting reading some statement CONTESTS toward another: NOT established,
    holding readings beside its claim (its options: a doubt's readings, a contradiction's sides, a contrary control left
    unrejected), and among its claim and those readings BOTH the documenting value and another one - the part (or act)
    may be the documenting clinician's or another's. Not a member line: a plain claim of another owner or performer that
    no statement contests (an outside-history part claimed other_facility, an administrative footer - pass 2 never
    appraises a section's facts, so they stay unresolved); readings that are all another's (an outside act filed both
    other_clinician and other_facility: done by someone else either way); an established fact - the documenting one, or
    another the fact pass settled. Their acts' items are drawn from established documenting values only, which none of
    them contests."""
    if facts_.established(found):
        return False
    readings = [value for value in (found.value, *found.options) if value is not None]  # one alone is never both
    return any(value is documenting for value in readings) and any(value is not documenting for value in readings)


def _start(R: FactSet, section: Id) -> int | None:
    """Where a section begins: the first offset of its role fact's sources (its heading), else of its owner fact's,
    else of any of its facts'; None when none has a source (it is placed nowhere)."""
    facts = R.sections.get(section, {})
    for attribute in (_A.ROLE, _A.OWNER):
        spans = [span for found in facts.get(attribute, ()) for span in found.spans]
        if spans:
            return min(span.start for span in spans)
    spans = [span for values in facts.values() for found in values for span in found.spans]
    return min(span.start for span in spans) if spans else None


def member_line_side(R: FactSet) -> tuple[_Range, ...]:
    """DECISIONS D317 (1): where the statements that give another performer or author to the acts on one side of them
    are told, and that side - read from the fact pass's representation, never a word of the note:
    - the PARTS such a statement contests: each section whose performer or owner reads another (``_reads_another``:
      pass 1's doubt about the section and its acts, or a contradiction's side) - its extent, from its start to the next
      section's - and each act whose performer or entry reads another, its anchor;
    - the LINE: pass 2 keeps the statement itself as a kept unlisted entry beyond them (one that doubts or tells acts:
      _LINE_KINDS; a denial gives no performer). The nearest such entry after every contested part's start gives the
      side BEFORE it (from the document's start), the nearest one wholly before them the side after it (to the
      document's end); both, when entries stand on both sides; none, when no entry stands beyond them - the parts alone
      are then the side (no entry locates the line).
    A contested section that cannot be placed leaves the whole document the side (fail-closed). () when no section or
    act reads another: no member line."""
    performer, owner = Performer.DOCUMENTING_TEAM, Owner.DOCUMENTING_CLINICIAN
    contested = [section for section in R.sections
                 if _reads_another(facts_.fact(R, section, _A.PERFORMER), performer)
                 or _reads_another(facts_.fact(R, section, _A.OWNER), owner)]
    acts = [event for event in R.events
            if _reads_another(facts_.fact(R, event, _A.PERFORMER), performer)
            or _reads_another(facts_.fact(R, event, _A.ENTRY), owner)]
    if not contested and not acts:
        return ()
    starts = {section: _start(R, section) for section in R.sections}
    if any(starts[section] is None for section in contested):
        return ((0, _END),)
    placed = sorted(start for start in starts.values() if start is not None)
    parts: list[_Range] = []
    for section in contested:
        start = starts[section]
        assert start is not None
        later = [found for found in placed if found > start]
        parts.append((start, later[0] if later else _END))
    marks = [part[0] for part in parts]
    for event in acts:
        anchor = R.anchors.get(event)
        for span in (anchor.units if anchor is not None else ()):
            parts.append((span.start, span.end))
            marks.append(span.start)
    if not marks:
        return ((0, _END),)
    first, last = min(marks), max(marks)
    lines = [entry for entry in R.unlisted if entry.units and entry.what in _LINE_KINDS]
    after = [min(span.start for span in entry.units) for entry in lines if min(span.start for span in entry.units) > last]
    before = [max(span.end for span in entry.units) for entry in lines if max(span.end for span in entry.units) <= first]
    side = list(parts)
    if after:
        side.append((0, min(after)))
    if before:
        side.append((max(before), _END))
    return tuple(sorted(set(side)))


def _told(R: FactSet, name: str) -> tuple[Span, ...]:
    """Where an object a calibration item names is told, as its card shows it (contract/claims card_units): an act's
    anchor; a session's examination's anchor (pass 1's examination claim, in any state), else its kind fact's sources; a
    lesion's facts' sources. () for a name that is no object (the encounter, a value)."""
    try:
        subject = Id.parse(name)
    except ValueError:
        return ()
    if subject.family is IdFamily.EVENT:
        anchor = R.anchors.get(subject)
        return anchor.units if anchor is not None else ()
    if subject.family is IdFamily.SESSION:
        exam = facts_.fact(R, subject, _A.EXAMINATION).value
        anchor = R.anchors.get(exam) if isinstance(exam, Id) else None
        if anchor is not None:
            return anchor.units
        return facts_.fact(R, subject, _A.KIND).spans
    if subject.family is IdFamily.LESION:
        return tuple(span for values in R.lesions.get(subject, {}).values() for found in values for span in found.spans)
    return ()


def on_member_line_side(R: FactSet, item: CalibrationSpec, side: Sequence[_Range]) -> bool:
    """DECISIONS D317 (1): whether a calibration item's truth may turn on a member line - some object it names (its
    act, a session it names, a lesion it names) is told on a member line's side (``member_line_side``). Such an item is
    never drawn: an item is drawn only where its truth turns on no member line."""
    return any(span.start < end and start < span.end for name in item.names for span in _told(R, name)
               for start, end in side)


def _k_form(family: Family, R: FactSet, event: Id, attribute: Attribute) -> str:
    """The form of an act-form calibration item (D314): the family's plain form for (event_class, attribute,
    supported). RuntimeError where there is none - a defect of the tables, never data."""
    form = qc.form_of(family.value, event_class(R, event), attribute, FactState.SUPPORTED)
    if form is None:
        raise RuntimeError(f'no {family.value} form for ({event_class(R, event).value}, {attribute.value}, supported)')
    return form


def calibration_pool(R: FactSet) -> tuple[CalibrationSpec, ...]:
    """Every calibration item R's CONTROLLED facts give (b.9): K1 the plain negation of an established value (the act's
    date relation on the date of service, entry, performer, session), K2 an exclusive alternative (another session
    where the act's session is established), K3 a claimed pair whose covers claim the fact pass supported (source
    'covers') and - DECISIONS D310 (4), b.9's second source - every pair SAME on every row from established facts
    (``same_pairs``, source 'same'), K4 an act's established target lesion negated.

    DECISIONS D314: K1, K2 and K4 - every act-form item - are drawn ONLY from an event whose object class is ACT and whose
    status is ESTABLISHED performed (``performed_act``, the one predicate, on the class reading _acts_of shares): "This
    act was not done on the date of service." of a DENIAL of a procedure that day is TRUE as worded (step 1 long's
    request 2 asked it of A-note8's E8), so a correct answer was a breach refusing the whole request. Each item's form is
    the fact pass's own for (object class, attribute, state) (``_k_form``) and carries its subjects' descriptions; an
    item its form is not exact for is a defect (RuntimeError, never a silent drop). K3 keeps its statement form and its
    own sources.

    DECISIONS D315 - every OBJECT an item names, under every reading of it: K2's alternative is drawn only where
    ``exclusive_sessions`` holds (the act's own established session and the alternative both procedure sessions that
    took place: on A-note8, "This act was done during session X5." of the clips A24 - its cards; X5 the moderate
    sedation the endoscopist did not give - is false only by its presupposition, and a reader of intent may support
    it); K4 only for an act whose part_of is SILENT (done to the lesion in its own right: "This act was not done to
    lesion L8." of the lift injected beneath L8 for its resection turns on the part link, not on the act).

    DECISIONS D317: K2's two sessions also of established different dates or separate encounters (exclusive_sessions,
    through separate_occasions); and THE MEMBER LINE - no item whose truth may turn on a statement that gives another
    performer or author to the acts on one side of it: an item naming any object told on such a statement's side
    (member_line_side, on_member_line_side) is not drawn (C-C2MEM-023's "All of the above was done by her previous
    gastroenterologist." contested 24 K1 items of the D315 pool - the entry and date of acts above it, the session of
    acts below it named by a session told above it). DECISIONS D319: the request draws ONE item from what remains."""
    out: list[CalibrationSpec] = []
    for event in R.events:
        stored = str(event)
        if performed_act(R, event):
            act = describe(R, stored)
            for attribute in _K1_ATTRIBUTES:
                found = facts_.fact(R, event, attribute)
                if (event, attribute) not in R.controlled or found.result is not Result.SUPPORTED:
                    continue
                value = found.value
                if attribute in _ONE_VALUE and value != _ONE_VALUE[attribute]:
                    continue
                form = _k_form(Family.Q_FACT, R, event, attribute)
                names = (stored, str(value)) if attribute is _A.SESSION else (stored,)
                passage = value_passage_of(attribute)  # DECISIONS D324 (9), D325 (4): rendered as its questions are
                out.append(CalibrationSpec(CalibrationKind.K1, Family.Q_FACT, form, (stored,), attribute,
                                           _value_of(value), True, names, passage, described=(act,)))
                if attribute is _A.SESSION:
                    for other in R.sessions:
                        if exclusive_sessions(R, value, other):  # DECISIONS D315 (1): the one predicate
                            out.append(CalibrationSpec(CalibrationKind.K2, Family.Q_FACT, form, (stored,), _A.SESSION,
                                                       str(other), False, (stored, str(other)),
                                                       value_passage_of(_A.SESSION), described=(act,)))
            lesion = facts_.fact(R, event, _A.TARGET_LESION)
            if ((event, _A.TARGET_LESION) in R.controlled and lesion.result is Result.SUPPORTED
                    and isinstance(lesion.value, Id)
                    and facts_.silent(facts_.fact(R, event, _A.PART_OF))):  # DECISIONS D315 (2): in its own right
                multiplicity = facts_.fact(R, lesion.value, _A.MULTIPLICITY)
                form = (_k_form(Family.Q_ONLESION, R, event, _A.TARGET_LESION)
                        if facts_.holds(multiplicity, Multiplicity.SINGLE) else 'onlesion.group')
                out.append(CalibrationSpec(CalibrationKind.K4, Family.Q_ONLESION, form, (stored, str(lesion.value)),
                                           _A.TARGET_LESION, str(lesion.value), True, (stored, str(lesion.value)),
                                           described=(act, describe(R, str(lesion.value)))))
        for member in facts_.members(R, event, _A.SCOPE_COVERS):
            act_id = member.value
            if member.result is Result.SUPPORTED and isinstance(act_id, Id) and act_id in R.events and act_id != event:
                out.append(CalibrationSpec(CalibrationKind.K3, Family.Q_REL, 'rel', (stored, str(act_id)), None, '',
                                           False, (stored, str(act_id)), source=K3Source.COVERS,
                                           described=(describe(R, stored), describe(R, str(act_id)))))
    for statement, act_id in same_pairs(R):  # b.9's second K3 source (DECISIONS D310 (4))
        out.append(CalibrationSpec(CalibrationKind.K3, Family.Q_REL, 'rel', (str(statement), str(act_id)), None, '',
                                   False, (str(statement), str(act_id)), source=K3Source.SAME,
                                   described=(describe(R, str(statement)), describe(R, str(act_id)))))
    side = member_line_side(R)  # DECISIONS D317 (1): the member line's side, read once for the whole pool
    unique: dict[str, CalibrationSpec] = {}
    for item in out:  # one item per content key; a pair both sources give is the SAME-rows item (no K1 companion)
        if side and on_member_line_side(R, item, side):
            continue
        if unique.get(item.key) is None or item.source is K3Source.SAME:
            unique[item.key] = item
    for item in unique.values():  # DECISIONS D314: every item is rendered by a form exact for its subjects
        why = qc.inexact(item.form, item.described)
        if why is not None:
            raise RuntimeError(f'calibration item {item.key}: {why} (DECISIONS D314)')
    return tuple(unique.values())


def same_pairs(R: FactSet) -> tuple[tuple[Id, Id], ...]:
    """b.9's second K3 source (DECISIONS D310 (4)): the statement-act pairs SAME on every row of 4.5 from ESTABLISHED
    facts only - every row SAME, both events' kinds supported AND THE SAME KIND, both statuses established, both
    sessions supported and the same session (so no row is SAME by a default: C-8's single-compatible-session SAME, an
    act-filed possible statement's breadth), the statement's status negated (an established denial) or its date relation
    or performer established as another (pairing.is_statement on established facts). Such a statement concerns the act on
    every row the engine reads, so "This statement does not concern act {A}." is known false - a holding-direction Q-REL
    item that needs no K1 beside it (its rows are the fact pass's own controlled judgments, not pass 1's covers).
    THE SAME KIND, not only kinds that pair: pairing pairs a statement with every act its kind MAY be (a tattoo and an
    injection share one act, 4.5), a fail-closed possibility, never an established sameness - "No carbon-particle tattoo
    was placed into the resection bed." pairs SAME on every row with the saline LIFT injected beneath that lesion
    (A-note8's and C-C2MEM-023's E30 and E20), and a correct reader says it does not concern the lift: as a calibration
    item it would read a right answer as a breach and refuse the whole request."""
    out: list[tuple[Id, Id]] = []
    for pair in pairing.pairs(R):
        statement, act = pair.statement, pair.act
        if not all(result is pairing.RowResult.SAME for _, result in pair.rows):
            continue
        sides = (statement, act)
        kinds = [facts_.fact(R, side, _A.KIND) for side in sides]
        if not all(found.result is Result.SUPPORTED for found in kinds) or kinds[0].value != kinds[1].value:
            continue
        if not all(facts_.established(facts_.fact(R, side, _A.STATUS)) for side in sides):
            continue
        sessions = [facts_.fact(R, side, _A.SESSION) for side in sides]
        if not all(found.result is Result.SUPPORTED for found in sessions) or sessions[0].value != sessions[1].value:
            continue
        out.append((statement, act))
    return tuple(out)


def _rank(seed: str, key: str) -> str:
    return hashlib.sha256(f'{seed}|{key}'.encode('utf-8')).hexdigest()


def calibration_count(questions: int) -> int:
    """DECISIONS D319: exactly CALIBRATION_COUNT (one) calibration item per question request, whatever its number of
    questions (b.9's max(4, ceil(q / 4)) superseded)."""
    return CALIBRATION_COUNT


def _needs_k1(item: CalibrationSpec) -> bool:
    """b.9: a K3 item from pass 1's covers (UNCONTROLLED) is drawn only beside at least one K1 item; the SAME-rows K3
    needs no companion. With one item a request (D319) there is no room beside it: a covers K3 is never drawn."""
    return item.kind is CalibrationKind.K3 and item.source is not K3Source.SAME


def draw(pool: Sequence[CalibrationSpec], questions: Sequence[QuestionSpec], seed: str) -> tuple[CalibrationSpec, ...]:
    """A request's calibration (b.9; DECISIONS D310 (4), D319), drawn deterministically from the pool ordered by
    sha256(seed | key), ``calibration_count`` items in all (one; fewer only when the usable pool is smaller):
    1. for each family the request asks, in question order, one same-family item where the pool has one - a
       NEGATIVE-form one where the family has one (b.9's polarity: at least half the items negative-form, so the one item
       is negative wherever the pool allows), the SAME-rows K3 before a covers K3, a covers K3 only where a K1 can be
       drawn beside it;
    2. a K1 beside any covers K3 drawn (step 1's), counted in the items - with one item a covers K3 always gives way to
       its K1;
    3. negative-form items (K1, K3, K4) until at least half are negative, then the rest, in the seeded order - a covers
       K3 only once a K1 is drawn;
    4. a covers K3 left with no K1 is dropped and the draw REFILLED from what remains (so the count and the polarity
       quota hold whenever the pool can give them).
    Disjoint from the questions: a calibration item concerns an established fact, a question an unestablished one."""
    wanted = calibration_count(len(questions))
    asked = {spec.key for spec in questions}
    ordered = sorted((item for item in pool if item.key not in asked), key=lambda item: _rank(seed, item.key))
    has_k1 = any(item.kind is CalibrationKind.K1 for item in ordered)
    usable = [item for item in ordered if has_k1 or not _needs_k1(item)]
    chosen: list[CalibrationSpec] = []

    def take(item: CalibrationSpec) -> None:
        if item not in chosen and len(chosen) < wanted:
            chosen.append(item)
            if _needs_k1(item) and not any(found.kind is CalibrationKind.K1 for found in chosen):
                k1 = next((found for found in usable if found.kind is CalibrationKind.K1 and found not in chosen), None)
                if k1 is not None:
                    if len(chosen) >= wanted:  # no room for its companion: the covers K3 gives way
                        chosen.remove(item)
                    chosen.append(k1)

    for family in dict.fromkeys(spec.family for spec in questions):
        same_family = [item for item in usable if item.family is family and item not in chosen]
        negative = [item for item in same_family if item.negative]
        candidates = negative or same_family
        preferred = next((item for item in candidates if not _needs_k1(item)), None)
        found = preferred if preferred is not None else (candidates[0] if candidates else None)
        if found is not None:
            take(found)
    for item in usable:
        if len(chosen) >= wanted:
            break
        negatives = sum(1 for found in chosen if found.negative)
        if item in chosen or (negatives * 2 < wanted and not item.negative):
            continue
        take(item)
    for item in usable:  # the polarity quota cannot be met: fill from what remains
        if len(chosen) >= wanted:
            break
        take(item)
    if any(_needs_k1(item) for item in chosen) and not any(item.kind is CalibrationKind.K1 for item in chosen):
        chosen = [item for item in chosen if not _needs_k1(item)]  # a covers K3 never stands alone: drop, then refill
        for item in usable:
            if len(chosen) >= wanted:
                break
            if item not in chosen and not _needs_k1(item):
                chosen.append(item)
    return tuple(chosen)


def request_seed(questions: Sequence[QuestionSpec], round_: int) -> str:
    return hashlib.sha256('\n'.join([str(round_), *(spec.key for spec in questions)]).encode('utf-8')).hexdigest()


def _chunks(specs: Sequence[QuestionSpec], bound: int) -> list[list[QuestionSpec]]:
    """e.3's cut: the round's questions, in plan order, in consecutive chunks whose claims - 2 per question, 2 per
    calibration item (``calibration_count``) - stay within ``bound``."""
    out: list[list[QuestionSpec]] = []
    chunk: list[QuestionSpec] = []
    for spec in specs:
        if chunk and 2 * (len(chunk) + 1) + 2 * calibration_count(len(chunk) + 1) > bound:
            out.append(chunk)
            chunk = []
        chunk.append(spec)
    if chunk:
        out.append(chunk)
    return out


def _requests(chunks: Sequence[Sequence[QuestionSpec]], pool: Sequence[CalibrationSpec],
              round_: int) -> tuple[RequestPlan, ...]:
    """Each chunk with its own calibration (``_request``) - THE PLANNER'S INVARIANT (DECISIONS D323 F4): when any chunk's
    restricted pool cannot give its item, UncalibratedRequest, naming every such chunk's questions (refused, never
    sent, unresolved as H5 leaves them) and carrying the requests that do have their item; never a request without
    one."""
    made = [_request(chunk, pool, round_) for chunk in chunks]
    refused = tuple(request.questions for request in made if not request.calibrated)
    if refused:
        raise UncalibratedRequest(refused, tuple(request for request in made if request.calibrated))
    return tuple(made)


def partition(specs: Sequence[QuestionSpec], pool: Sequence[CalibrationSpec], round_: int,
              bound: int = QUESTION_BOUND) -> tuple[RequestPlan, ...]:
    """e.3: the round's questions, in plan order, cut greedily into consecutive chunks whose claims - 2 per question, 2
    per calibration item, one item a request (D319) - stay within ``bound``; each chunk draws its own calibration
    seeded by its own content. Every question is in exactly one request (P-NODROP). A request whose pool cannot give
    its item is refused here (UncalibratedRequest: DECISIONS D323 F4), never returned."""
    return _requests(_chunks(specs, bound), pool, round_)


def split(request: RequestPlan, pool: Sequence[CalibrationSpec], round_: int) -> tuple[RequestPlan, ...]:
    """e.4: an overrun request's questions re-partitioned into two halves, cut at the middle question, each with its own
    calibration (UncalibratedRequest, as ``partition``, where a half's pool cannot give its item); () for a request of
    one question (it stays unresolved: question_request_failed:too_long)."""
    if len(request.questions) <= 1:
        return ()
    middle = len(request.questions) // 2
    return _requests((request.questions[:middle], request.questions[middle:]), pool, round_)


def _request(chunk: Sequence[QuestionSpec], pool: Sequence[CalibrationSpec], round_: int) -> RequestPlan:
    seed = request_seed(chunk, round_)
    return RequestPlan(tuple(chunk), draw(pool, chunk, seed), seed)


# --- eligibility, re-checked by settle (d.2 row 1) -----------------------------------------------------------------------


def eligible(spec: QuestionSpec, R: FactSet) -> bool:
    """d.2 row 1: the question still applies to the settled facts (R_base): a fact question's fact still unestablished
    and not contradicted for another reason than a conflict; a Q-REL pair still paired and not INDEPENDENT, no pass-1
    contradiction in it, a claimed pair only as C7b-other; a lesion pair's lesions both held; an absorption's entry
    held and every act its list names established performed (DECISIONS D324 (3))."""
    subjects = [facts_._subject_of(item) for item in spec.subjects]
    index = unlisted_index(spec.subjects)
    if spec.family is Family.Q_FACT:
        subject = subjects[0] if subjects else None
        if spec.attribute is None:
            return False
        domain = facts_.DOMAINS.get((subject.family if subject is not None else None, spec.attribute))
        if domain is None:
            return False
        # one predicate with the planner and the fold (round r3's integration, the engine lane's Q-R1; int5, the fold
        # lane's Q-F5 (e), DECISIONS D324 (4)): the fold's own rule, facts.folds - answerable, the value not ruled out,
        # the fixed-table checks re-run - so an answer the fold refuses is never recorded established and left unfolded
        return _folds(R, spec)
    if spec.family is Family.Q_REL:
        statement, act = subjects
        if not isinstance(act, Id):
            return False
        if index is not None:
            return 0 <= index < len(R.unlisted)
        if not isinstance(statement, Id) or not pairing.paired(R, statement, act):
            return False
        pair = pairing.relation(R, statement, act)
        if pair.relation is pairing.Relation.INDEPENDENT or _contradicted(R, statement) or _contradicted(R, act):
            return False
        return not pair.claimed or (not _covers_supported(R, statement, act) and not _denies_or_doubts(R, statement))
    if spec.family is Family.Q_ONLESION:
        act, lesion = subjects
        return (isinstance(act, Id) and isinstance(lesion, Id) and act in R.events and lesion in R.lesions
                and facts_.silent(facts_.fact(R, act, _A.TARGET_LESION)))
    if spec.family is Family.Q_LESION:
        return all(isinstance(item, Id) and item in R.lesions for item in subjects)
    if spec.family is Family.Q_ABSORB:
        # DECISIONS D324 (3): its act list names only acts established performed (the planner's _acts_of), re-checked
        # against the settled facts - a question whose list names any other act (a plan, an attempt, an act in doubt,
        # a statement, an object R does not hold) or no act at all is never established
        return (index is not None and 0 <= index < len(R.unlisted) and bool(spec.acts)
                and all(_performed_named(R, act) for act in spec.acts))
    return False


def _performed_named(R: FactSet, stored: str) -> bool:
    """A stored act name (a Q-ABSORB question's list) that names an event R holds, established performed
    (``performed_act``)."""
    try:
        event = Id.parse(stored)
    except ValueError:
        return False
    return event.family is IdFamily.EVENT and event in R.events and performed_act(R, event)


# --- the engine pin (DESIGN-v2 h: QUESTION_ENGINE_SHA256_V3) -------------------------------------------------------------

def engine_modules() -> tuple[ModuleType, ...]:
    """Every module the plan reads (QUESTION_ENGINE_SHA256_V3): the question claims, settle, the engine's modules and the
    store - named by the modules themselves (imported here, where every one is loaded), never as a list of words
    (FINAL-V2 5.7 measure 4: DECISIONS D323 F3)."""
    from studio.interpretation import store
    from studio.interpretation.contract import question_claims, settle
    from studio.interpretation.engine import (anatomy, asking, assess, catalogue, classes, combination, coverage,
                                              evaluate, facts, pairing, questions, reading, requirements,
                                              requirements_table, types, whatif)
    return (question_claims, settle, anatomy, asking, assess, catalogue, classes, combination, coverage, evaluate, facts,
            pairing, questions, reading, requirements, requirements_table, types, whatif, store)


def engine_digest() -> str:
    """The sha256 of every engine module the plan reads (``engine_modules``), sorted by name - each module's path under
    studio/interpretation without its suffix ('engine/asking', 'store'), its source's sha256 - so a changed module
    moves it (QUESTION_ENGINE_SHA256_V3)."""
    root = Path(__file__).resolve().parents[1]
    paths = sorted((path.relative_to(root).with_suffix('').as_posix(), path)
                   for path in (Path(module.__file__ or '').resolve() for module in engine_modules()))
    digest = hashlib.sha256()
    for name, path in paths:
        digest.update(name.encode('utf-8') + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()
