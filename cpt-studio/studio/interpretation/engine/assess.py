"""The assessment of one revision from its settled inventory (docs/gemini-migration/FINAL-V2.md 4.1, 4.3, 4.4, 4.7, 4.8,
4.12 and 9.3; step 5a of 8.1; cpt-studio-events@2): v1's studio/interpretation/assess.py forked into engine/, its
readers deleted and its inputs rewired to the typed, text-free FactSet. It assembles, per proposed code, R1 (the
proposer's quote is the document's own text), the per-code rule (engine/evaluate.py, R2-R5 and the code-specific rows),
R6, the class rule (engine/classes.py), the bundling (engine/coverage.py), the combination (engine/combination.py), R7
(the date of service) and R9 (the reference rows, records only), ranks every held fact (4.8) and sets the status:
EXCLUDED (R1, an exclusion of 4.6, or a member's answer), NEEDS_CLARIFICATION (any held fact, the date of service
unknown among them), else READY.

**What it reads.** ``assess`` reads store.textfree_v2's view of the stored row through facts.effective (L1 re-judged
against the effective date of service; DECISIONS D188 and the triage's hand-offs 2d:D16 and 2d:R8: never facts.factset)
and hands that FactSet to ``assess_facts``, the assembly every caller shares. The revision ``text`` is read for
integrity only (4.1's "R1 is the one integrity use of the text in assessment"; 5.6's allowlist row "engine/assess.py ->
checks.code_scope, checks.exact_evidence"): it is passed, unread, to the caller's ``Integrity`` - the allowlisted
validation checks (code_scope, exact_evidence), the participants' one code-shape rule (code_shaped) and, when given,
the letter-or-digit runs of a kept span (word_runs, step 4a's request R1) - and to nothing else. The per-code rule, the
combination, coverage and questions never receive it. Those checks are handed in rather than imported because their
modules are no ``mypy --strict`` modules (studio.validation.checks, studio.participants.peer: 1,289 and 385 errors in
the modules an import would follow); this module stays inside the typed engine (5.7 measure 5).

**R6** (4.3's second table, the rows engine/evaluate.py leaves to assess, its module docstring): over the sessions of
the code's supporting acts (E*), each row T, U (a question, rank 14, 12, 16 or 19) or met in its "established
otherwise" form:
- R6:extent (egd, enteroscopy, flex_sig): a reached point supported (stated_depth counts), or completion supported
  incomplete or terminated; otherwise ``extent``;
- COLFULL (every colonoscopy code): a reached point supported in catalogue.COLONOSCOPY_FULL_REACH, or reached_anatomy
  supported naming an anatomy entry whose subtype is supported in COLONOSCOPY_FULL_SUBTYPES (D38, D44, D57, D63);
  established otherwise - completion supported incomplete or terminated, beside a supported reach (v1's _reach: "a
  stated incomplete examination keeps its reach"; with no reach stated v1 asked it, and so does this) - it holds
  nothing and the 52/53 consideration stands (the established-otherwise column: "completion incomplete: 52/53"; the
  step's NOTES, question Q3); otherwise ``extent``;
- in both rows a contradicted reach - a reached point contradicted, a K8 polarity pair (3.1 K8 [R:HO-9]: "asked at rank
  1") or pass 1's contradicted claim - asks RANK 1 ``conflict:examination`` (4.8 RANK row 1; a session's fact is its
  examination's, D225 P7), a question about the reach quoting each contradicted point's own spans, BEFORE anything else
  the row reads, as engine/evaluate.py's LOWER row asks it (DECISIONS D244 R-K8; this repair's NOTES, question Q-K8a);
  and a contradicted completion the unmet row rests on - an empty slot a conflict doubt names included (silent_slot,
  D217) - asks RANK 1 too, about the completion (4.8 RANK row 1: "a doubt with basis conflict" included; question
  Q-K8b);
- R6:target (eus): a supported place of a supporting act or of a done examination of its session; otherwise
  ``target``;
- R6:cannulation (ercp): a cannulation of the session (its kind and session supported) with its status supported
  performed or begun, its access_outcome and its duct supported; failed is the D107 52/53 consideration, achieved after
  failed attempts nothing; otherwise ``cannulation``;
- R6:em_basis (office_em): visit.basis supported on the code's visit - an em_visit of E*, or for 99417 the em_visit of
  its act's session (requirements.Role.VISIT); otherwise ``em_basis``;
- R6:context (office_em): member-entered setting and patient status (D3: never the document); otherwise ``setting``
  (its sentence names patient status too when both are missing: the item's Fill.both) or ``patient_status``, rank 23,
  cause context_missing.
With no supporting act the session rows hold nothing more: SUPPORT already holds the code, and its item ranks first.

**ADDON** (4.3's row "43273, 91013, 99153, 99417 | its primary counted"; Appendix A's tag; engine/evaluate.py leaves it
to assess): an add-on code with a supporting act is T when one of its primaries (``ADDON_PRIMARIES``: the catalogue codes
of its family CPT reports it with) is counted - proposed, admitted by R1, not excluded, and not excluded by a member's
answer (the answers' passes recompute an add-on whose every counted primary an answer excluded) - else U: its witness
(``addon_hold``) is code-level, as D80's and D197's are (performed_status at RANK's status row, subject, attribute and
result None, the kept spans), a question (4.3 puts the row's non-T in its "unmet" column), cause coding_rule:ADDON. The
design names neither the primary sets nor the item ("as today"; v1 has no add-on rule): both are the narrowest
fail-closed reading, recorded as the refutation-round step's NOTES questions. With no supporting act SUPPORT already holds
the code (and D80 holds 99153 before any group is read), so the row adds nothing there.

**The class rule, the bundling and the combination** are called, never re-implemented (steps 4a's R2, 4b's R4, 4d's R2,
O17's ``extra=`` wiring): classes.enteroscopy_hold and coverage.bundling over E*, appended to the held facts through
evaluate.item(..., extra=...), which keeps 4.8's one item; combination.combine over the counted codes (Member: the
routed family, the matched session - coverage.session_of -, E*, the origin, procedural over the PFS row as v1's
_procedural, supported when E* is not empty and the per-code rule holds nothing) with event_coding@2's sessions as
SessionActs (step 4d's R1, converted here from coverage.event_coding's own record: one derivation), its held facts
appended before ranking. The considerations (4.4; 4.7's rows): 52/53 (a session of the code whose completion is
established incomplete or terminated - supported so, or denied complete, as engine/classes.py reads it (D217) - or, by
DECISIONS D244 Q-S4 option (a), the installed reading, not established and not silent, whatever value it claims
(``stopped_short``); an examination or a supporting act supported attempted_not_completed; or a cannulation supported
failed), 25 (an E/M code on a procedure day), 59/XS (combination's modifier review); PC/TC is the PFS row's (R9), worded
by the renderer from the row. R7: with no effective date of service every code holds the encounter-scope service_date
(unranked, cause date_unknown).

**Participants** (4.12, P-ADMIT and I3, unchanged): a code a participant's frozen FIRST reading proposes, in scope,
quoted with an exact span, that no decidable proposal carries is evaluated by the same per-code rule from that
participant's spans (origin participant); a code a decidable proposal carries adds the participants that quoted it
exactly (first reading or peer review) to ``proposed_by`` AND NOTHING ELSE - no readiness rule reads a proposer, and
the fingerprint names none (tests/v2/test_assess.py, test_agreement_adds_proposers_and_nothing_else); a code proposed
only in peer review, or located but never exactly, or never located, stays an alternative. A participant's advice that
a code was not performed here, or its peer dispute, is a disagreement record on that code, never a status. The second
review (D10): a code it selected becomes a proposal (origin second_review) only when it is not excluded and its E*
intersects the events of the marked no_proposal and not_covered items the other proposals leave.

**Member answers** (4.8: "unchanged"; D7, D182): the engine reads an answer that names its code and its question's
fingerprint, to a fact neither key-bound (base_included, separate_em) nor competing_codes - those are the read-time
overlay's, as in v1 - nor the encounter-scope service_date, which a member settles by entering the date (an answer to it
is recorded as applied by nothing, never as the overlay's). It binds to the code's ONE item when the code, its family's
slug, the item's fact key and the item's fingerprint (``question_fingerprint``, FORM cpt-studio-question@2: v2 items have
new fingerprints, so a pre-v2 answer is asked differently) all match; "Not documented" or "Cannot confirm" then EXCLUDES
that code (not reinstatable). It confirms no fact and releases no hold of its own (4.8, D182): the answered code stays
counted in the combination's base, within and same-day rules and in the coverage (session decision (e)). Two readings
leave it out:
- ADDON: an answered code is no longer counted for ADDON, so an add-on whose every counted primary an answer excluded is
  held (fail-closed);
- the competition (DECISIONS D260, read time's D249 reading in interpretation/overlay.py): a code a member answered
  "Not documented" leaves the competition (``compete_without``), so a rival with no other rival left loses its
  competing_codes hold, and one with a rival left keeps it, naming only the rivals left; "Cannot confirm" leaves the
  competition as it stands (D249's "not documented", the fail-closed reading, as read time reads it).
An answer the engine does not read is the review overlay's (recorded as read by it): read time binds it and reads the
code detail unavailable, which assess never does. DECISIONS D270 (DQ-2) reads one bound by key for the competition
alone, as D260 reads one the engine applies, so the stored record and read time agree (``overlay_bound``): an answer
read time binds by its (code, family, fact) key alone (studio.validation.questions.bind) - to a key-bound fact
(base_included, separate_em) whatever fingerprint it carries, or with no fingerprint (the earlier form) - bound to a
selected code whose ONE item has that key, and "Not documented" takes that code out of the competition exactly as above.
Never an answer to the competing question, which offers no answer (codes competing for one act are settled by rejecting
one: studio/answers.py, P-ADMIT2), nor to the date of service. Nothing else reads it: the code stays selected with its
item (read time shows it detail unavailable), it is still counted for ADDON and every other rule, and "Cannot confirm"
moves nothing.
None of these readings moves the answered code itself: a code an answer took out of the competition or excluded is never
assessed again - an excluded code's answer stands, and an overlay-bound one keeps the record its answer found, so read
time binds the answer to the same item. The answers are bound in passes: every code whose ADDON row or competition the
answers moved is assessed again over the counted set and the competition the answers leave (keeping the fingerprint it
has without the answers while its status is unchanged: the next paragraph), and the answers are bound again over the
result - never a code an answer excluded or took out of the competition, whose answer was given to the item it presented
and stands, so no code flips back into review. A further pass follows only a code newly excluded or newly out of the
competition, and those only grow, so the passes end: at most one pass per newly excluded code (an overlay binding
counted as one), never one pass per proposal - a code can be assessed again in more than one pass (em_chain's 99214,
tests/v2/test_assess.AnswerPassTests: narrowed by the first pass, released by the second). A service answer (no code)
closes the service questions it was given to - those its fingerprint names, or, with none, every question of its
(family, fact) - each question by the first answer that names it; a later answer naming only questions already closed is
recorded as not applied (v1's record).

**Fingerprints over facts** (``fingerprint``): the sha256 of the engine and requirement versions, the code, its family,
its units, its kept evidence as offsets, its status, its evaluation, ranked held facts, item, answer and
considerations, the facts of its supporting acts and their sessions, the member values its decision depends on (v1's
_relevant_context: the setting, the patient status and the billing context of an E/M code, and the billing context of a
code whose PFS row carries separate professional and technical rows, which the PC/TC consideration reads) and the date
of service - never a proposer or an origin, so agreement cannot move it, and never a word: a decision carries across an
AGAIN recompute over the same inventory and never across interpretations (D7). One exception, the installed release's
rule for an answer's cross-code effects (studio/validation/engine.py, refutation cycle 4, answers 1; AMENDMENT-1 6.4: a
change the fingerprint does not carry keeps the decision): a code the answers' passes assess again only because another
code's answer moved its competition or its ADDON row keeps the fingerprint it has without the answers while its status
is unchanged (``_kept_fingerprint``), so a reviewer's decision on it carries across the recompute that reads the answer
(on the seam check's scene 677, 43248 keeps its decision while only its competing hold goes); a code whose status moves
takes the fingerprint of what it now is (the status is a fingerprint input, FINAL-V2 6.5).

**The D22 fields** (FINAL-V2 5.7 measure 9): the assessment records the versions that made it (``versions``: the engine,
cpt-studio-events@2, the requirement table, and the inventory pair it read); the sentinel's record (legacy_calls,
retired_calls) is the caller's (interpretation/report.py, measured by engine/measure.py). SERVICES_STUB and
INVENTORY_PROBLEMS are written exactly as v1 wrote them for the rollback image (FINAL 12; FINAL-V2 6.4), the stub's
version this engine's.

**What it returns** is an ``Assessment``: typed and text-free, every proposal's outcome, item, held facts, trace and
fingerprint, the alternatives, the service questions, coverage, event_coding@2, completeness and the records above. It
is no studio.types.AssessmentResult: the sentences (each item through wording.build, the checks, the rationale) are
step 3c's wording, built after the decision by a renderer outside engine/ (the step's NOTES, request R1).

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library, the
package's labels, contract/types.py, contract/jsonschema.py and engine's catalogue, classes, combination, coverage,
evaluate, facts, pairing, questions, requirements, requirements_table and types only - no retired v1 module (5.0), none
of contract's text modules, not wording - holds no word, phrase or marker list (every module-level collection holds
enumeration members), never reads the text it passes to R1 and returns no document string. ``mypy --strict`` passes
over it.
"""
from __future__ import annotations

import datetime
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum, unique
from types import MappingProxyType
from typing import Protocol, TypeVar

from studio.interpretation import ENGINE_VERSION_V2, INTERPRETATION_PAIR, INVENTORY_VERSION_V2, REQUIREMENTS_VERSION
from studio.interpretation.contract.jsonschema import canonical, sha256_of
from studio.interpretation.contract.types import (AccessOutcome, Attribute, Completion, Extent, Kind, Reason, Result,
                                                  SessionKind, Status)
from studio.interpretation.engine import catalogue, classes, combination, coverage, evaluate, pairing, questions
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import (Evaluation, Fact, FactSet, HeldFact, Id, IdFamily, IsoDate, ItemKind,
                                                Outcome, Span)

_A = Attribute
_Q = ItemKind.QUESTION
_E = TypeVar('_E', bound=Enum)

ENGINE_VERSION = ENGINE_VERSION_V2  # Assessment.engine_version of an assessment made here
MAX_LISTED_CODE = 10  # wording.MAX_LISTED_CODE: what a stored proposal code holds; codes are never truncated
QUESTION_FORM = 'cpt-studio-question@2'  # the fingerprint form of a v2 item (studio.validation.questions.FORM is @1)
# FINAL 4.3 (v1's): what the new path writes into the legacy services slot, and the sentence that freezes the old
# image's read-time reconciliation (FINAL 12.2). The stub's keys are the legacy record's field names - an output shape,
# never compared with any text - written by keyword, so this module holds no string list; its version is this engine's.
SERVICES_STUB: Mapping[str, object] = MappingProxyType(dict(version=ENGINE_VERSION_V2, services=(), conflicts=(),
                                                            attributions=(), problems=()))
INVENTORY_PROBLEMS = ('This assessment was made by a later release from an event inventory; this release does not '
                      're-read it.',)


def services_stub() -> dict[str, object]:
    """Assessment.services as v1 wrote it: the stub with fresh, empty lists (``SERVICES_STUB``)."""
    return {key: ([] if isinstance(value, tuple) else value) for key, value in SERVICES_STUB.items()}


# --- the vocabulary of the inputs and the records (CPT Studio's own codes, as enumerations) ---------------------------


@unique
class ProviderStatus(Enum):
    """The proposal provider's outcome (v1's PROVIDER_STATUSES)."""
    SUCCEEDED = 'succeeded'
    NOT_RUN = 'not_run'
    FAILED = 'failed'
    UNKNOWN = 'unknown'


@unique
class ProviderRole(Enum):
    """A code's role in a provider's list (studio.types.ProviderCode.role)."""
    SELECTED = 'selected'
    CANDIDATE = 'candidate'
    ALTERNATIVE = 'alternative'


@unique
class ParticipantState(Enum):
    """A participant's state (studio.types.PARTICIPANT_STATES)."""
    READ = 'read'
    REFUSED = 'refused'
    FAILED = 'failed'
    UNKNOWN = 'unknown'
    NOT_SENT = 'not_sent'
    BLOCKED = 'blocked'
    NOT_CONFIGURED = 'not_configured'
    NOT_RUN = 'not_run'


@unique
class Advice(Enum):
    """The not-coded reason a participant gives that the engine reads (types.NOT_CODED_REASONS' first)."""
    NOT_PERFORMED_HERE = 'not_performed_at_this_encounter'


@unique
class Position(Enum):
    """The peer-review position the engine reads (a dispute)."""
    DISPUTES = 'disputes'


@unique
class Phase(Enum):
    """When a participant advised against a code: its independent reading, or peer review (v1's INDEPENDENT,
    PEER_REVIEW)."""
    INDEPENDENT = 'independent'
    PEER_REVIEW = 'peer_review'


@unique
class Origin(Enum):
    """Who proposed a code (v1's support.origin): the proposal provider, a participant's first reading, the second
    review."""
    PRIMARY = 'primary'
    PARTICIPANT = 'participant'
    SECOND_REVIEW = 'second_review'


@unique
class Bucket(Enum):
    """Where a proposal is listed (Proposal.bucket)."""
    SELECTED = 'selected'
    EXCLUDED = 'excluded'
    ALTERNATIVE = 'alternative'


@unique
class Consideration(Enum):
    """A modifier consideration (4.4: "52/53, 25, 59/XS, PC/TC"; 9.1 codes[].considerations): never a status, never an
    assignment. PC/TC is the PFS row's and is worded from it by the renderer (R9: the references are records)."""
    INCOMPLETE = '52|53'
    SEPARATE_EM = '25'
    DISTINCT_LESION = '59|XS'


@unique
class NotAdded(Enum):
    """Why a listed code is an alternative, never a proposal: the provider's other roles; R1 (out of scope, no exact
    passage, never located); a peer-review code; and the second review's merge (a primary proposal carries it, no
    catalogue profile, nothing it accounts for was left unresolved, its acts are excluded)."""
    LISTED = 'listed'
    OUT_OF_SCOPE = 'out_of_scope'
    NO_EVIDENCE = 'no_evidence'
    UNLOCATED = 'unlocated'
    PEER_ONLY = 'peer_only'
    CARRIED = 'carried'
    NO_PROFILE = 'no_profile'
    NOT_LEFT = 'not_left'
    EXCLUDED = 'excluded'


@unique
class Answer(Enum):
    """The member answers a question takes (studio.validation.questions.UNAVAILABLE; D7): the detail is unavailable from
    the document. Neither confirms a fact."""
    NOT_DOCUMENTED = 'not_documented'
    CANNOT_CONFIRM = 'cannot_confirm'


@unique
class Unbound(Enum):
    """Why a standing answer applies to no item of this assessment (v1's bind and record)."""
    NO_LONGER_ASKED = 'no_longer_asked'
    ASKED_DIFFERENTLY = 'asked_differently'
    NOT_APPLIED = 'not_applied'
    OVERLAY_READ = 'read_by_the_review_overlay'


@unique
class Scope(Enum):
    """Where an answer applied: a proposal's item, or a service question."""
    PROPOSAL = 'proposal'
    SERVICE = 'service'


def _member(enum: type[_E], value: object) -> _E | None:
    """``value`` as a member of ``enum``, or None when it is none (a value read from a record, never document text)."""
    for member in enum:
        if member.value == value:
            return member
    return None


# --- the inputs: what the caller hands in, read only through these protocols ----------------------------------------


class Offsets(Protocol):
    """A kept evidence span as R1's check returns it (studio.types.EvidenceSpan): its offsets, the only part read."""

    @property
    def start(self) -> int: ...

    @property
    def end(self) -> int: ...


class Integrity(Protocol):
    """R1 and the participants' code rule (4.1, 4.12, 5.6), the one use of the revision text in assessment: the caller's
    studio.validation.checks.code_scope and exact_evidence (the FINAL 7.1 allowlist) and studio.participants.peer's
    code_shaped. ``word_runs`` - the letter-or-digit runs of a kept span, C-10's ``kept_words`` (step 4a's request R1, a
    SingleCharacterGeometry function of contract/geometry.py, step 1c) - may be None: C-10 then reads every offset of a
    kept span (fail-closed)."""

    def code_scope(self, code: str) -> tuple[str, str]: ...

    def exact_evidence(self, spans: Sequence[object], text: str,
                       pages: Sequence[object]) -> tuple[Sequence[Offsets], Sequence[object]]: ...

    def code_shaped(self, value: object) -> bool: ...

    @property
    def word_runs(self) -> Callable[[str, Span], Sequence[Span]] | None: ...


class ProviderCodeInput(Protocol):
    """One code a provider listed (studio.types.ProviderCode): its role, code and evidence spans."""

    @property
    def role(self) -> str: ...

    @property
    def code(self) -> str: ...

    @property
    def evidence(self) -> Sequence[object]: ...


class ProviderInput(Protocol):
    """A provider's normalized answer (studio.types.NormalizedResponse): its name, codes and whether it was refused."""

    @property
    def provider(self) -> str: ...

    @property
    def codes(self) -> Sequence[ProviderCodeInput]: ...

    @property
    def refused(self) -> bool: ...


class QuoteInput(Protocol):
    """A participant's located quote (studio.types.LocatedQuote): its exact occurrences."""

    @property
    def spans(self) -> Sequence[object]: ...


class ParticipantCodeInput(Protocol):
    """A participant's code (studio.types.ParticipantCode) and its quotes."""

    @property
    def code(self) -> str: ...

    @property
    def evidence(self) -> Sequence[QuoteInput]: ...


class NotCodedInput(Protocol):
    """A participant's not-coded code (studio.types.ParticipantNotCoded) and its reason."""

    @property
    def code(self) -> str: ...

    @property
    def reason(self) -> str: ...

    @property
    def evidence(self) -> Sequence[QuoteInput]: ...


class PositionInput(Protocol):
    """A peer review's position on a code (studio.types.CodePosition)."""

    @property
    def code(self) -> str: ...

    @property
    def position(self) -> str: ...

    @property
    def evidence(self) -> Sequence[QuoteInput]: ...


class ReadingInput(Protocol):
    """A participant's frozen first reading (studio.types.ParticipantReading)."""

    @property
    def provider(self) -> str: ...

    @property
    def refused(self) -> bool: ...

    @property
    def codes(self) -> Sequence[ParticipantCodeInput]: ...

    @property
    def not_coded(self) -> Sequence[NotCodedInput]: ...


class PeerInput(Protocol):
    """A participant's peer review (studio.types.PeerReview)."""

    @property
    def provider(self) -> str: ...

    @property
    def refused(self) -> bool: ...

    @property
    def additional_codes(self) -> Sequence[ParticipantCodeInput]: ...

    @property
    def positions(self) -> Sequence[PositionInput]: ...


class ParticipantInput(Protocol):
    """One configured participant (studio.types.ParticipantInput), in stage order."""

    @property
    def provider(self) -> str: ...

    @property
    def state(self) -> str: ...

    @property
    def reading(self) -> ReadingInput | None: ...

    @property
    def peer_state(self) -> str: ...

    @property
    def peer(self) -> PeerInput | None: ...


class AnswerInput(Protocol):
    """A member's standing answer (studio.validation.questions.MemberAnswerInput)."""

    @property
    def code(self) -> str: ...

    @property
    def family(self) -> str: ...

    @property
    def fact(self) -> str: ...

    @property
    def value(self) -> str: ...

    @property
    def question(self) -> str: ...

    @property
    def answer_id(self) -> str: ...


class ReferenceRows(Protocol):
    """A code's reference rows at the date of service (studio.reference CodeReference): its PFS and MUE rows."""

    @property
    def pfs(self) -> Mapping[str, object] | None: ...

    @property
    def mue(self) -> Mapping[str, object] | None: ...


class Lookup(Protocol):
    """The reference lookup (studio.reference.store's, prefetched for the bounded child)."""

    def lookup(self, code: str, service_date: datetime.date | None) -> ReferenceRows: ...


@dataclass(frozen=True, slots=True)
class MemberContext:
    """The member-entered context the rules read (D3: never the document): the setting, the patient status and the
    billing context as entered, '' when not entered. R6:context reads whether the first two were entered; the
    fingerprint records the values a code's rules read."""
    setting: str = ''
    patient_status: str = ''
    billing_context: str = ''


# --- the records ------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Evidence:
    """R1's verdict on a proposal's quotes (4.1): checks.code_scope's code kind and reason ('' in scope), the exact
    evidence kept as revision offsets, the reasons the other spans were dropped (CPT Studio's own), and the
    letter-or-digit runs of the kept spans (``runs``; None: not computed, and C-10 then reads every offset)."""
    code_kind: str
    scope_reason: str
    kept: tuple[Span, ...]
    dropped: tuple[str, ...]
    runs: tuple[Span, ...] | None = None

    @property
    def exact(self) -> bool:
        """In scope with exact evidence: the per-code rule may read the code (v1's decidable)."""
        return not self.scope_reason and bool(self.kept)


@dataclass(frozen=True, slots=True)
class Trace:
    """One requirement row of a code (9.1 codes[].trace): the requirement (a requirements.Requirement's or a Tag's
    value: SUP.3, COLFULL, R6:extent, R7), its Truth, the act or session it was read on (None: the code or the
    encounter), and its first witness (None for T)."""
    requirement: str
    truth: evaluate.Truth
    subject: Id | None
    witness: HeldFact | None


@dataclass(frozen=True, slots=True)
class Answered:
    """The member answer that excluded a code: the fact its item was about, the answer and every answer id bound."""
    fact: str
    value: Answer
    answers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Disagreement:
    """A participant's advice against a decidable code (participants.disagree; never a status): who, when, and the
    offsets of its first exact quote."""
    provider: str
    phase: Phase
    span: Span


@dataclass(frozen=True)
class Assessed:
    """One proposal (selected or excluded; v1's ProposalAssessment, text-free). ``key`` 'sel:<n>' or 'exc:<n>';
    ``family`` the routed family; ``origin`` and ``proposed_by`` who proposed it (operator data; nothing reads them);
    ``bucket`` and ``status``; ``units`` how many times the provider selected it; ``evidence`` R1's verdict;
    ``reinstatable`` (an exclusion of 4.6 is, R1 and a member's answer are not); ``session`` the session it is matched
    to; ``evaluation`` the per-code rule's (None when R1 refused it); ``held_facts`` every held fact, ranked (4.8);
    ``item`` its one clarification (None when nothing holds it); ``waits`` what would still hold an excluded code if a
    reviewer reinstated it (v1's reinstatement_waits); ``answered`` the member answer that excluded it;
    ``considerations``; ``competes`` the rival codes left in the competition (D40; by D260 a code a member answered
    "Not documented" is none); ``disagreements``; ``primary_listed`` whether the proposal provider listed the code too
    (a participant's code's rationale names it); ``trace`` its requirement rows; ``pfs`` and ``mue`` its R9 reference
    rows (records only); ``fingerprint`` (module docstring); ``question`` its item's fingerprint ('' for none)."""
    key: str
    code: str
    family: SessionKind
    origin: Origin
    proposed_by: tuple[str, ...]
    bucket: Bucket
    status: Outcome
    units: int
    evidence: Evidence
    reinstatable: bool
    session: Id | None
    evaluation: Evaluation | None
    held_facts: tuple[HeldFact, ...]
    item: questions.Item | None
    waits: tuple[HeldFact, ...]
    answered: Answered | None
    considerations: tuple[Consideration, ...]
    competes: tuple[str, ...]
    disagreements: tuple[Disagreement, ...]
    primary_listed: bool
    trace: tuple[Trace, ...]
    pfs: Mapping[str, object] | None
    mue: Mapping[str, object] | None
    fingerprint: str
    question: str


@dataclass(frozen=True, slots=True)
class Alternative:
    """A code listed and never proposed (bucket alternative, informational): its key ('alt:<n>', 'alt2:<n>' for the
    second review's, 'altp:<n>' for a participant's), code, family, origin, who listed it, why it is no proposal, its
    provider role (None for a participant's) and R1's verdict on its quotes."""
    key: str
    code: str
    family: SessionKind
    origin: Origin
    proposed_by: tuple[str, ...]
    why: NotAdded
    role: ProviderRole | None
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class ServiceQuestion:
    """A service-scope item (coverage.ServiceItem; it holds nothing) with its fingerprint and the answers that closed
    it."""
    item: coverage.ServiceItem
    question: str
    closed: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerApplied:
    """A standing answer this assessment applied (v1's member_answers.applied)."""
    answer: str
    scope: Scope
    code: str
    family: str
    fact: str
    value: Answer
    proposals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerEarlier:
    """A standing answer this assessment applied to nothing, and why (v1's member_answers.earlier)."""
    answer: str
    code: str
    family: str
    fact: str
    value: Answer
    why: Unbound


@dataclass(frozen=True, slots=True)
class ParticipantRecord:
    """One configured participant as read (participants.summary's facts): its state and how many codes its first
    reading proposed with an exact passage."""
    provider: str
    state: ParticipantState
    proposed: int


@dataclass(frozen=True, slots=True)
class SecondReviewRecord:
    """The bounded second review's merge (D10): refused, the codes added as proposals and listed only, the unresolved
    items its added codes account for, and how many of its codes were not in a code's shape."""
    refused: bool
    added: tuple[str, ...]
    listed: tuple[str, ...]
    accounts_for: tuple[coverage.Item, ...]
    unlisted: int


@dataclass(frozen=True)
class Assessment:
    """The assessment of one revision (module docstring): ``versions`` (the D22 fields), the effective
    ``date_of_service`` and the document's date fact, the provider status, the proposals (``codes``, selected then
    excluded, in key order) and ``alternatives``, the ``service_questions``, ``coverage`` (reconcile over the counted
    codes), the ``combination`` (combine's over the counted codes, its competition read without a code a member
    answered "Not documented", the engine reading the answer or the overlay binding it: ``compete_without``, D260 and
    D270's DQ-2), ``event_coding`` (event_coding@2), ``completeness`` and ``services`` as Assessment stores them, the
    member answers applied and not, the participants, the second review, and how many provider codes were not in a
    code's shape."""
    versions: Mapping[str, str]
    date_of_service: datetime.date | None
    date_fact: Fact
    provider_status: ProviderStatus
    codes: tuple[Assessed, ...]
    alternatives: tuple[Alternative, ...]
    service_questions: tuple[ServiceQuestion, ...]
    coverage: coverage.Coverage
    combination: combination.Combination
    event_coding: Mapping[str, object]
    completeness: Mapping[str, object]
    services: Mapping[str, object]
    answers: tuple[AnswerApplied, ...]
    earlier_answers: tuple[AnswerEarlier, ...]
    participants: tuple[ParticipantRecord, ...]
    second_review: SecondReviewRecord | None
    unlisted_codes: int

    def code(self, key: str) -> Assessed:
        """The proposal with ``key``. KeyError for none."""
        for found in self.codes:
            if found.key == key:
                return found
        raise KeyError(key)


def versions() -> dict[str, str]:
    """The D22 fields an assessment carries (9.1 versions): the inventory pair read, the inventory version, the
    requirement table and the engine."""
    return {'interpretation': INTERPRETATION_PAIR, 'inventory': INVENTORY_VERSION_V2,
            'requirements': REQUIREMENTS_VERSION, 'engine': ENGINE_VERSION_V2}


# --- canonical data (fingerprints, P-DET) -----------------------------------------------------------------------------


def jsonable(value: object) -> object:
    """``value`` as JSON data, deterministically: an Enum as its value, an Id as pass 1's form, a Span as [start, end],
    a date as ISO, an IsoDate as pass 1's form, a dataclass as its fields, a mapping as [key, value] pairs in canonical
    order (keys may be tuples or enumeration members), a set in canonical order. TypeError for anything else."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return jsonable(value.value)
    if isinstance(value, Id):
        return str(value)
    if isinstance(value, Span):
        return [value.start, value.end]
    if isinstance(value, IsoDate):
        return value.iso
    if isinstance(value, datetime.date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        pairs = [[jsonable(key), jsonable(item)] for key, item in value.items()]
        return sorted(pairs, key=lambda pair: canonical(pair[0]))
    if isinstance(value, (frozenset, set)):
        return sorted((jsonable(item) for item in value), key=canonical)
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    raise TypeError(f'{type(value).__name__} is not assessment data.')


def digest(assessment: Assessment) -> str:
    """The sha256 of ``assessment`` as canonical JSON data (P-DET: identical inputs give byte-identical
    assessments)."""
    return sha256_of(jsonable(assessment))


def family_slug(family: SessionKind) -> str:
    """A family's gi.profiles slug (engine/derive.family_slug's rule, pinned equal by test): gi.<value>, gi.other and
    gi.unsupported. The member key of an answer names it."""
    if family is SessionKind.OTHER_GI:
        return 'gi.other'
    if family is SessionKind.NOT_GI:
        return 'gi.unsupported'
    return f'gi.{family.value}'


def question_fingerprint(code: str, family: SessionKind, item: questions.Item) -> str:
    """The fingerprint of a code's one item (QUESTION_FORM): its code, family, fact key, message, kind, subject, rank,
    the spans it quotes and the Fill its sentence is built from - every part the question shows, text-free. An answer
    binds to the item only when it carries this fingerprint."""
    return sha256_of({'form': QUESTION_FORM, 'scope': Scope.PROPOSAL.value, 'code': code,
                      'family': family_slug(family), 'fact': item.held.fact, 'message': item.message.value,
                      'kind': item.kind.value, 'subject': jsonable(item.held.subject), 'rank': item.held.rank,
                      'spans': jsonable(item.held.spans), 'fill': jsonable(item.fill)})


def service_fingerprint(found: coverage.ServiceItem) -> str:
    """The fingerprint of a service item (QUESTION_FORM, scope service): its family, fact key, subject, rank and the
    spans it quotes."""
    family = family_slug(found.family) if found.family is not None else ''
    return sha256_of({'form': QUESTION_FORM, 'scope': Scope.SERVICE.value, 'code': '', 'family': family,
                      'fact': found.item.fact, 'kind': found.item.kind.value, 'subject': jsonable(found.item.subject),
                      'rank': found.item.rank, 'spans': jsonable(found.item.spans),
                      'event': jsonable(found.event), 'unlisted': found.unlisted})


# --- R1: the proposer's quote is the document's own text (4.1) --------------------------------------------------------


def _listable(code: object) -> bool:
    """engine._listable (v1's): a code string a stored proposal can hold."""
    return isinstance(code, str) and 0 < len(code) <= MAX_LISTED_CODE


def _offsets(found: Iterable[Offsets]) -> tuple[Span, ...]:
    """The kept spans as revision offsets, each once, in order."""
    out: list[Span] = []
    for span in found:
        start, end = span.start, span.end
        if type(start) is not int or type(end) is not int or not 0 <= start < end:
            raise ValueError('R1 kept a span that has no revision offsets.')
        if Span(start, end) not in out:
            out.append(Span(start, end))
    return tuple(out)


def admit(code: str, spans: Sequence[object], text: str, pages: Sequence[object], integrity: Integrity) -> Evidence:
    """R1 for one proposal (4.1): ``code``'s scope (checks.code_scope) and its exact evidence (checks.exact_evidence
    over ``spans``, the provider's evidence items, against ``text``), with the kept spans' letter-or-digit runs when the
    caller computes them. The text goes to ``integrity`` alone."""
    code_kind, scope_reason = integrity.code_scope(code)
    kept, dropped = integrity.exact_evidence(list(spans), text, pages)
    offsets = _offsets(kept)
    word_runs = integrity.word_runs
    runs: tuple[Span, ...] | None = None
    if word_runs is not None:
        runs = tuple(dict.fromkeys(run for span in offsets for run in word_runs(text, span)))
    return Evidence(code_kind=str(code_kind), scope_reason=str(scope_reason), kept=offsets,
                    dropped=tuple(str(problem) for problem in dropped), runs=runs)


# --- one selection (v1's _Selection) ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Selection:
    """One proposed code before the encounter is assembled: its code, how many times it was selected, R1's verdict,
    its routed family, its origin and proposers, whether the proposal provider listed it, the per-code rule's
    evaluation when R1 admitted it, and whether its PFS row splits the professional and technical components (``pctc``:
    its fingerprint then carries the billing context, set once the reference rows are read)."""
    code: str
    units: int
    evidence: Evidence
    family: SessionKind
    origin: Origin = Origin.PRIMARY
    proposers: tuple[str, ...] = ()
    primary_listed: bool = True
    evaluation: Evaluation | None = None
    pctc: bool = False

    @property
    def decidable(self) -> bool:
        return self.evaluation is not None

    @property
    def excluded(self) -> bool:
        return self.evaluation is None or self.evaluation.exclusion is not None


def _evaluated(selection: _Selection, R: FactSet) -> _Selection:
    if not selection.evidence.exact:
        return selection
    evaluation = evaluate.decide(selection.code, selection.evidence.kept, R, kept_words=selection.evidence.runs)
    return replace(selection, evaluation=evaluation)


def _merge_selected(codes: Sequence[ProviderCodeInput]) -> list[list[ProviderCodeInput]]:
    """engine._merge_selected (v1's): selected codes grouped by code, in order of first appearance."""
    groups: dict[str, list[ProviderCodeInput]] = {}
    for item in codes:
        if _member(ProviderRole, item.role) is ProviderRole.SELECTED:
            groups.setdefault(item.code, []).append(item)
    return list(groups.values())


def _select(group: Sequence[ProviderCodeInput], text: str, pages: Sequence[object], integrity: Integrity,
            R: FactSet, origin: Origin = Origin.PRIMARY) -> _Selection:
    code = group[0].code
    evidence = admit(code, [span for item in group for span in item.evidence], text, pages, integrity)
    selection = _Selection(code=code, units=len(group), evidence=evidence, family=catalogue.family_for_code(code),
                           origin=origin)
    return _evaluated(selection, R)


def _keys(selections: Sequence[_Selection]) -> list[str]:
    """engine._keys (v1's): 'sel:<n>' or 'exc:<n>', counted within its bucket in selection order."""
    counts = {Bucket.SELECTED: 0, Bucket.EXCLUDED: 0}
    out = []
    for selection in selections:
        bucket = Bucket.EXCLUDED if selection.excluded else Bucket.SELECTED
        out.append(f"{'exc' if bucket is Bucket.EXCLUDED else 'sel'}:{counts[bucket]}")
        counts[bucket] += 1
    return out


# --- the participants (P-ADMIT, 4.12; v1's _Participants) -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Usable:
    provider: str
    state: ParticipantState
    reading: ReadingInput | None
    peer: PeerInput | None


def _well_formed(reading: object) -> bool:
    """Whether a participant's reading can be read whole: every code a string and every quote's spans a sequence (v1's
    _well_formed, read by shape)."""
    try:
        codes = list(getattr(reading, 'codes', ())) + list(getattr(reading, 'not_coded', ()))
        codes += list(getattr(reading, 'additional_codes', ())) + list(getattr(reading, 'positions', ()))
        for item in codes:
            if not isinstance(getattr(item, 'code'), str):
                return False
            for quote in getattr(item, 'evidence'):
                list(getattr(quote, 'spans'))
        return isinstance(getattr(reading, 'provider'), str) and not getattr(reading, 'refused')
    except (AttributeError, TypeError):
        return False


def _usable_inputs(participants: Sequence[ParticipantInput]) -> tuple[_Usable, ...]:
    """The participants as CPT Studio reads them, in the order given (the caller's stage order): a malformed or refused
    reading is read as refused, never raised on (I10); an input that names no participant raises (the caller's contract
    violation)."""
    given: dict[str, list[ParticipantInput]] = {}
    for p in participants:
        if not isinstance(p.provider, str) or not p.provider:
            raise ValueError('A participant input names its participant.')
        given.setdefault(p.provider, []).append(p)
    out = []
    for name, entries in given.items():
        p = entries[0]
        state = _member(ParticipantState, p.state)
        reading = p.reading
        if len(entries) > 1 or state is None or (state is ParticipantState.READ and (
                reading is None or not _well_formed(reading) or reading.provider != name)):
            out.append(_Usable(name, ParticipantState.REFUSED, None, None))
            continue
        peer = p.peer if (state is ParticipantState.READ and _member(ParticipantState, p.peer_state)
                          is ParticipantState.READ and p.peer is not None and _well_formed(p.peer)
                          and p.peer.provider == name) else None
        out.append(_Usable(name, state, reading if state is ParticipantState.READ else None, peer))
    return tuple(out)


class _Harness:
    """The participants' codes as CPT Studio reads them (v1's _Participants): only exact slices of the revision text
    are evidence (I7); nothing a participant wrote in its own words reaches the result."""

    def __init__(self, participants: Sequence[ParticipantInput], text: str, pages: Sequence[object],
                 integrity: Integrity) -> None:
        self.inputs = _usable_inputs(participants)
        self.revision, self.pages, self.integrity = text, pages, integrity
        self.first: dict[str, dict[str, dict[Span, Span]]] = {}
        self.located: dict[str, list[str]] = {}
        self.peer: dict[str, dict[str, dict[Span, Span]]] = {}
        self.advised: dict[str, list[Disagreement]] = {}
        self.order: list[str] = []
        for p in self.inputs:
            if p.reading is None:
                continue
            for code_item in p.reading.codes:
                self._said(code_item.code, p.provider, code_item.evidence, self.first)
            for not_coded in p.reading.not_coded:
                if _member(Advice, not_coded.reason) is Advice.NOT_PERFORMED_HERE and \
                        integrity.code_shaped(not_coded.code):
                    self._advice(not_coded.code, p.provider, Phase.INDEPENDENT, not_coded.evidence)
            if p.peer is not None:
                for code_item in p.peer.additional_codes:
                    self._said(code_item.code, p.provider, code_item.evidence, self.peer)
                for position in p.peer.positions:
                    if _member(Position, position.position) is Position.DISPUTES and \
                            integrity.code_shaped(position.code):
                        self._advice(position.code, p.provider, Phase.PEER_REVIEW, position.evidence)

    def _exact(self, quotes: Sequence[QuoteInput]) -> tuple[Span, ...]:
        spans = [span for quote in quotes for span in quote.spans]
        kept, _ = self.integrity.exact_evidence(spans, self.revision, self.pages)
        return _offsets(kept)

    def _said(self, code: str, name: str, quotes: Sequence[QuoteInput],
              into: dict[str, dict[str, dict[Span, Span]]]) -> None:
        if not self.integrity.code_shaped(code):
            return
        if code not in self.order:
            self.order.append(code)
        if any(len(quote.spans) for quote in quotes):
            self.located.setdefault(code, []).append(name)
        good = self._exact(quotes)
        if good:
            found = into.setdefault(code, {}).setdefault(name, {})
            for span in good:
                found.setdefault(span, span)

    def _advice(self, code: str, name: str, phase: Phase, quotes: Sequence[QuoteInput]) -> None:
        good = self._exact(quotes)
        if good:
            self.advised.setdefault(code, []).append(Disagreement(name, phase, good[0]))

    def proposers(self, code: str) -> tuple[str, ...]:
        """The participants that quoted ``code`` exactly, in their first reading or in peer review, in stage order."""
        return tuple(p.provider for p in self.inputs if self.first.get(code, {}).get(p.provider)
                     or self.peer.get(code, {}).get(p.provider))

    def merge(self, selections: list[_Selection], R: FactSet) -> tuple[list[_Selection], list[Alternative]]:
        """(the selections with each decidable code's participants recorded and the admitted codes after them, the
        participants' alternatives 'altp:<n>')."""
        carried = {s.code for s in selections if s.decidable}
        out = [replace(s, proposers=self.proposers(s.code)) if s.decidable and self.proposers(s.code) else s
               for s in selections]
        primary_any = {s.code for s in selections}
        alternatives: list[Alternative] = []
        for code in self.order:
            if code in carried:
                continue
            first = [p.provider for p in self.inputs if self.first.get(code, {}).get(p.provider)]
            names = first or list(self.proposers(code)) or list(dict.fromkeys(self.located.get(code, ())))
            code_kind, scope_reason = self.integrity.code_scope(code)
            why: NotAdded | None = None
            if scope_reason:
                why = NotAdded.OUT_OF_SCOPE
            elif not self.located.get(code):
                why = NotAdded.UNLOCATED
            elif not first and self.peer.get(code):
                why = NotAdded.PEER_ONLY
            elif not first:
                why = NotAdded.NO_EVIDENCE
            spans: dict[Span, Span] = {}
            for name in names:
                spans.update(self.first.get(code, {}).get(name, {}))
                if why is not None:
                    spans.update(self.peer.get(code, {}).get(name, {}))
            kept = tuple(sorted(spans))
            evidence = Evidence(code_kind=str(code_kind), scope_reason=str(scope_reason), kept=kept, dropped=())
            if why is not None:
                alternatives.append(Alternative(key=f'altp:{len(alternatives)}', code=code,
                                                family=catalogue.family_for_code(code), origin=Origin.PARTICIPANT,
                                                proposed_by=tuple(names), why=why, role=None, evidence=evidence))
                continue
            word_runs = self.integrity.word_runs
            runs = None if word_runs is None else tuple(dict.fromkeys(run for span in kept
                                                                      for run in word_runs(self.revision, span)))
            selection = _Selection(code=code, units=1, evidence=replace(evidence, runs=runs),
                                   family=catalogue.family_for_code(code), origin=Origin.PARTICIPANT,
                                   proposers=tuple(first), primary_listed=code in primary_any)
            out.append(_evaluated(selection, R))
        return out, alternatives

    def disagreements(self, code: str) -> tuple[Disagreement, ...]:
        return tuple(self.advised.get(code, ()))

    def records(self) -> tuple[ParticipantRecord, ...]:
        return tuple(ParticipantRecord(p.provider, p.state, sum(1 for code in self.order
                                                                if self.first.get(code, {}).get(p.provider)))
                     for p in self.inputs)


# --- the second review (FINAL 7.10, D10) ------------------------------------------------------------------------------


_MARKED: frozenset[coverage.ItemReason] = frozenset({coverage.ItemReason.NO_PROPOSAL, coverage.ItemReason.NOT_COVERED})


def _counted_of(selections: Sequence[_Selection], keys: Sequence[str]) -> list[coverage.Counted]:
    """The counted codes as coverage reads them: each selection that is not excluded, its E* and the acts its decision
    read (its bound candidates, then its held facts' events)."""
    out = []
    for key, s in zip(keys, selections):
        if s.excluded or s.evaluation is None:
            continue
        read = [event for event in s.evaluation.bindings.values()]
        read += [held.subject for held in s.evaluation.held_facts
                 if held.subject is not None and held.subject.family is IdFamily.EVENT]
        out.append(coverage.Counted(key=key, code=s.code, family=s.family, supporting=s.evaluation.supporting,
                                    read=tuple(dict.fromkeys(read))))
    return out


def _second_review(second: ProviderInput, selections: list[_Selection], text: str, pages: Sequence[object],
                   integrity: Integrity, R: FactSet, reader: coverage.Reader,
                   sessions_: Mapping[Id, coverage.Session]) -> tuple[list[_Selection], list[Alternative],
                                                                      SecondReviewRecord]:
    """A code the second review SELECTED becomes a proposal (origin second_review) only when it is not excluded and its
    E* intersects the events of the marked no_proposal and not_covered items the other proposals leave; every other
    code it lists is an alternative, with why. Nothing is promoted and nothing is invented (v1's _second_review)."""
    day = combination.procedure_day(R, ())
    cov = coverage.reconcile(reader, _counted_of(selections, _keys(selections)), procedure_day=bool(day.done),
                             sessions_=sessions_)
    marked = [item for index, item in enumerate(cov.unresolved)
              if index < coverage.SECOND_REVIEW_CHECKED and item.reason in _MARKED]
    have = {s.code for s in selections if s.decidable}
    listable = [c for c in second.codes if _listable(c.code)] if not second.refused else []
    added: list[_Selection] = []
    listed: list[tuple[ProviderCodeInput, NotAdded, Evidence]] = []
    accounted: list[coverage.Item] = []
    for group in _merge_selected(listable):
        code = group[0].code
        if code in have:
            listed.append((group[0], NotAdded.CARRIED, admit(code, group[0].evidence, text, pages, integrity)))
            continue
        candidate = _select(group, text, pages, integrity, R, Origin.SECOND_REVIEW)
        supporting = set(candidate.evaluation.supporting) if candidate.evaluation is not None else set()
        covered = [item for item in marked if supporting & set(item.events)]
        if covered and not candidate.excluded:
            added.append(candidate)
            have.add(code)
            accounted += [item for item in covered if item not in accounted]
            continue
        why = (NotAdded.OUT_OF_SCOPE if candidate.evidence.scope_reason
               else NotAdded.NO_EVIDENCE if not candidate.evidence.kept
               else NotAdded.NO_PROFILE if catalogue.code_profile(code) is None
               else NotAdded.EXCLUDED if candidate.excluded else NotAdded.NOT_LEFT)
        listed.append((group[0], why, candidate.evidence))
    alternatives = [Alternative(key=f'alt2:{index}', code=item.code, family=catalogue.family_for_code(item.code),
                                origin=Origin.SECOND_REVIEW, proposed_by=(second.provider,), why=why,
                                role=ProviderRole.SELECTED, evidence=evidence)
                    for index, (item, why, evidence) in enumerate(listed)]
    for item in (c for c in listable if _member(ProviderRole, c.role) is not ProviderRole.SELECTED):
        alternatives.append(Alternative(key=f'alt2:{len(alternatives)}', code=item.code,
                                        family=catalogue.family_for_code(item.code), origin=Origin.SECOND_REVIEW,
                                        proposed_by=(second.provider,), why=NotAdded.LISTED,
                                        role=_member(ProviderRole, item.role),
                                        evidence=admit(item.code, item.evidence, text, pages, integrity)))
    record = SecondReviewRecord(refused=bool(second.refused), added=tuple(s.code for s in added),
                                listed=tuple(item.code for item, _, _ in listed), accounts_for=tuple(accounted),
                                unlisted=len(second.codes) - len(listable) if not second.refused else 0)
    return list(selections) + added, alternatives, record


# --- R6 (4.3's second table: the rows assess appends) -----------------------------------------------------------------


_EXTENT_ITEM = rq.Item(rq.Rank.EXTENT, rq.FactKey.EXTENT)
_CONFLICT_ITEM = rq.Item(rq.Rank.CONFLICT, rq.FactKey.CONFLICT)  # 4.8 RANK row 1: conflict:<kind>, a contradicted fact
_TARGET_ITEM = rq.Item(rq.Rank.TARGET, rq.FactKey.TARGET)
_CANNULATION_ITEM = rq.Item(rq.Rank.CANNULATION, rq.FactKey.CANNULATION)
_EM_BASIS_ITEM = rq.Item(rq.Rank.EM_BASIS, rq.FactKey.EM_BASIS)
_SETTING_ITEM = rq.Item(rq.Rank.MEMBER_CONTEXT, rq.FactKey.SETTING)
_STATUS_ITEM = rq.Item(rq.Rank.MEMBER_CONTEXT, rq.FactKey.PATIENT_STATUS)
_STOPPED_SHORT: frozenset[Completion] = frozenset({Completion.INCOMPLETE, Completion.TERMINATED})
_BEGUN: frozenset[Status] = frozenset({Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED})
_R7 = 'R7'  # the date of service requirement's trace id (rq.Requirement.R7_R9's R7 half; R9 is records only)


@dataclass(frozen=True, slots=True)
class _Row:
    requirement: str
    truth: evaluate.Truth
    subject: Id | None
    witnesses: tuple[HeldFact, ...] = ()
    incomplete: bool = False

    def trace(self) -> Trace:
        return Trace(self.requirement, self.truth, self.subject, self.witnesses[0] if self.witnesses else None)


def _key(item: rq.Item) -> str:
    return rq.fact_key(item.fact)


def _rank(item: rq.Item) -> int | None:
    return item.rank.value if item.rank is not None else None


def _witness(rule: Tag, item: rq.Item, attribute: Attribute | None, subject: Id | None, found: Fact | None,
             spans: Sequence[Span]) -> HeldFact:
    """A U requirement's witness (4.2): its item, the fact it rests on (its result, its first reason; with no fact, a
    silent slot) and its cause - the fact's reading cause when it is not established (questions.cause_of), else the
    rule's own (coding_rule:<the tag>, e.g. a supported reach short of COLFULL's)."""
    resting = found if found is not None else facts_.SILENT
    cause = f'coding_rule:{rule.value}' if facts_.established(resting) else questions.cause_of(resting)
    return HeldFact(fact=_key(item), attribute=attribute, subject=subject, result=resting.result, kind=_Q,
                    cause=cause, reason=resting.reasons[0] if resting.reasons else None,
                    spans=tuple(sorted(set(spans))), rank=_rank(item))


def _supported_id(found: Fact) -> Id | None:
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, Id) else None


def sessions_of(R: FactSet, events: Iterable[Id]) -> tuple[Id, ...]:
    """The sessions ``events`` are supported in, each once, in order (the code's sessions, 4.3 row 6)."""
    found = (_supported_id(facts_.fact(R, event, _A.SESSION)) for event in events)
    return tuple(dict.fromkeys(session for session in found if session is not None
                               and session.family is IdFamily.SESSION))


def _examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The events established as ``session``'s examination: kind supported examination, session supported it - a
    digital examination excepted (FINAL 5.6 E13, DECISIONS D265: questions.digital_examination; R6 never quotes the
    DRE's sentence as the session's examination)."""
    return tuple(event for event in R.events if facts_.holds(facts_.fact(R, event, _A.KIND), Kind.EXAMINATION)
                 and facts_.holds(facts_.fact(R, event, _A.SESSION), session)
                 and not questions.digital_examination(R, event))


def _session_spans(R: FactSet, session: Id) -> tuple[Span, ...]:
    """What a session's R6 question quotes: its examinations' anchors (coverage.service_extent_questions' reading)."""
    return tuple(sorted({unit for event in _examinations(R, session) for unit in questions.anchor_units(R, event)}))


def _resting(found: Sequence[Fact], fallback: Fact) -> Fact:
    """The fact a U row rests on: the first of ``found`` that is not purely silent, else ``fallback``."""
    return next((fact for fact in found if not facts_.silent(fact)), fallback)


def _conflict(session: Id, attribute: Attribute, found: Sequence[Fact], R: FactSet) -> HeldFact:
    """The witness of an R6:extent or COLFULL row that a contradicted fact of ``session`` holds (4.8 RANK row 1: "a
    contradicted required fact (a doubt with basis conflict and a K8 polarity pair included)"; DECISIONS D244 R-K8):
    conflict:examination - a session's fact is its examination's, which the item names (D225 P7), as
    engine/evaluate.py's LOWER row asks a contradicted reach - at RANK 1, a question about ``attribute`` (the reach, or
    the completion), resting on the first of ``found`` (its result and first reason; its cause the reading's,
    questions.cause_of: reading_contradicted), quoting every contradicted fact's own spans - a K8 pair's two statements,
    so the item quotes both sides - else the session's examinations' anchors."""
    first = found[0]
    spans = tuple(sorted({span for fact in found for span in fact.spans})) or _session_spans(R, session)
    return HeldFact(fact=rq.fact_key(rq.FactKey.CONFLICT, Kind.EXAMINATION), attribute=attribute, subject=session,
                    result=first.result, kind=_Q, cause=questions.cause_of(first),
                    reason=first.reasons[0] if first.reasons else None, spans=spans, rank=_rank(_CONFLICT_ITEM))


def _extent_row(tag: Tag, R: FactSet, session: Id) -> _Row:
    """R6:extent (a reached point supported, or completion supported incomplete or terminated) and COLFULL (a reached
    point in the full colonoscopy reach, or an ileocolic reached anatomy; completion stopped short beside a supported
    reach is its established-otherwise form: no hold, the 52/53 consideration) over one session. A contradicted reached
    point (a K8 pair, pass 1's contradicted claim) is asked first, at RANK 1, whatever else the row reads - as
    engine/evaluate.py's LOWER row asks it (D244 R-K8): a contradiction is never dismissed (3.3 row 1), so no other
    point, stated incompleteness or anatomy meets the row beside it. An unmet row resting on a contradicted completion
    asks RANK 1 too (``_conflict``)."""
    reached = facts_.members(R, session, _A.REACHED)
    completion = facts_.fact(R, session, _A.COMPLETION)
    contradicted = tuple(member for member in reached if member.result is Result.CONTRADICTED)
    if contradicted:
        return _Row(tag.value, evaluate.Truth.U, session, (_conflict(session, _A.REACHED, contradicted, R),))
    stopped = completion.result is Result.SUPPORTED and completion.value in _STOPPED_SHORT
    if tag is Tag.R6_EXTENT:
        if any(member.result is Result.SUPPORTED and isinstance(member.value, Extent) for member in reached) or stopped:
            return _Row(tag.value, evaluate.Truth.T, session)
    else:
        if any(member.result is Result.SUPPORTED and member.value in catalogue.COLONOSCOPY_FULL_REACH
               for member in reached):
            return _Row(tag.value, evaluate.Truth.T, session)
        anatomy = _supported_id(facts_.fact(R, session, _A.REACHED_ANATOMY))
        if anatomy is not None:
            subtype = facts_.fact(R, anatomy, _A.SUBTYPE)
            if subtype.result is Result.SUPPORTED and subtype.value in catalogue.COLONOSCOPY_FULL_SUBTYPES:
                return _Row(tag.value, evaluate.Truth.T, session)
        if stopped and any(member.result is Result.SUPPORTED for member in reached):
            return _Row(tag.value, evaluate.Truth.F, session, incomplete=True)  # v1: an incomplete exam keeps its reach
    # the reach the row asks for, unless only a completion in doubt is stated: then the doubt it rests on - an empty
    # completion slot a doubt names included (silent_slot: a doubt is never silence, D217), so a conflict doubt naming
    # it is read here and asked at RANK 1
    doubted = not silent_slot(completion) and not facts_.established(completion)
    resting = _resting(reached, completion if doubted else facts_.SILENT)
    attribute = _A.COMPLETION if doubted and resting is completion else _A.REACHED
    if resting.result is Result.CONTRADICTED:  # only the completion here: a contradicted reach was asked above
        return _Row(tag.value, evaluate.Truth.U, session, (_conflict(session, attribute, (resting,), R),))
    spans = _session_spans(R, session) + tuple(resting.spans)
    return _Row(tag.value, evaluate.Truth.U, session,
                (_witness(tag, _EXTENT_ITEM, attribute, session, resting, spans),))


def _target_row(R: FactSet, supporting: Sequence[Id], sessions: Sequence[Id]) -> _Row:
    """R6:target (eus): a supported place of a supporting act or of an examination of its session."""
    exams = tuple(event for session in sessions for event in _examinations(R, session))
    places: list[tuple[Id, Fact]] = [(event, member) for event in (*supporting, *exams)
                                     for member in facts_.members(R, event, _A.TARGET_PLACES)]
    if any(member.result is Result.SUPPORTED for _, member in places):
        return _Row(Tag.R6_TARGET.value, evaluate.Truth.T, supporting[0] if supporting else None)
    subject = supporting[0] if supporting else (exams[0] if exams else None)
    resting = next((member for _, member in places), facts_.SILENT)
    spans = questions.anchor_units(R, subject) + tuple(resting.spans)
    return _Row(Tag.R6_TARGET.value, evaluate.Truth.U, subject,
                (_witness(Tag.R6_TARGET, _TARGET_ITEM, _A.TARGET_PLACES, subject, resting, spans),))


def _cannulation_row(R: FactSet, session: Id) -> _Row:
    """R6:cannulation (ercp) over one session: a cannulation of it with its status supported performed or begun and its
    access_outcome and duct supported; access_outcome failed is the D107 52/53 consideration."""
    cannulations = [event for event in R.events if facts_.holds(facts_.fact(R, event, _A.KIND), Kind.CANNULATION)
                    and facts_.holds(facts_.fact(R, event, _A.SESSION), session)]
    for event in cannulations:
        status = facts_.fact(R, event, _A.STATUS)
        outcome = facts_.fact(R, event, _A.ACCESS_OUTCOME)
        duct = facts_.fact(R, event, _A.TARGET_DUCT)
        if (status.result is Result.SUPPORTED and status.value in _BEGUN and outcome.result is Result.SUPPORTED
                and duct.result is Result.SUPPORTED):
            failed = outcome.value is AccessOutcome.FAILED
            return _Row(Tag.R6_CANNULATION.value, evaluate.Truth.F if failed else evaluate.Truth.T, event,
                        incomplete=failed)
    if not cannulations:
        return _Row(Tag.R6_CANNULATION.value, evaluate.Truth.U, session,
                    (_witness(Tag.R6_CANNULATION, _CANNULATION_ITEM, None, session, None,
                              _session_spans(R, session)),))
    event = cannulations[0]
    for attribute in (_A.STATUS, _A.ACCESS_OUTCOME, _A.TARGET_DUCT):
        found = facts_.fact(R, event, attribute)
        if found.result is not Result.SUPPORTED or (attribute is _A.STATUS and found.value not in _BEGUN):
            spans = questions.anchor_units(R, event) + tuple(found.spans)
            return _Row(Tag.R6_CANNULATION.value, evaluate.Truth.U, event,
                        (_witness(Tag.R6_CANNULATION, _CANNULATION_ITEM, attribute, event, found, spans),))
    return _Row(Tag.R6_CANNULATION.value, evaluate.Truth.T, event)  # unreachable: the first loop met it


def visits_of(R: FactSet, supporting: Sequence[Id]) -> tuple[Id, ...]:
    """The code's visits (requirements.Role.VISIT): the em_visit events of E*, then the em_visit events supported in the
    sessions of E* (99417's: its prolonged time's visit), each once."""
    own = [event for event in supporting if facts_.holds(facts_.fact(R, event, _A.KIND), Kind.EM_VISIT)]
    sessions = sessions_of(R, supporting)
    beside = [event for event in R.events if facts_.holds(facts_.fact(R, event, _A.KIND), Kind.EM_VISIT)
              and _supported_id(facts_.fact(R, event, _A.SESSION)) in sessions]
    return tuple(dict.fromkeys(own + beside))


def _em_basis_row(R: FactSet, supporting: Sequence[Id]) -> _Row:
    """R6:em_basis (office_em): visit.basis supported on the code's visit (combination.visit_basis)."""
    visits = visits_of(R, supporting)
    found = combination.visit_basis(R, visits)
    if found is not None:
        return _Row(Tag.R6_EM_BASIS.value, evaluate.Truth.T, found.event)
    subject = visits[0] if visits else (supporting[0] if supporting else None)
    fact = facts_.fact(R, subject, _A.VISIT_BASIS) if subject is not None else None
    spans = questions.anchor_units(R, subject) + (tuple(fact.spans) if fact is not None else ())
    return _Row(Tag.R6_EM_BASIS.value, evaluate.Truth.U, subject,
                (_witness(Tag.R6_EM_BASIS, _EM_BASIS_ITEM, _A.VISIT_BASIS, subject, fact, spans),))


def _context_row(member: MemberContext) -> _Row:
    """R6:context (office_em): the member-entered setting and patient status (D3). Its witness is member context: no
    fact, cause context_missing."""
    for item, entered in ((_SETTING_ITEM, member.setting), (_STATUS_ITEM, member.patient_status)):
        if not entered:
            held = HeldFact(fact=_key(item), attribute=None, subject=None, result=None, kind=_Q,
                            cause=questions.CONTEXT_MISSING, reason=None, spans=(), rank=_rank(item))
            return _Row(Tag.R6_CONTEXT.value, evaluate.Truth.U, None, (held,))
    return _Row(Tag.R6_CONTEXT.value, evaluate.Truth.T, None)


def r6_rows(code: str, supporting: Sequence[Id], R: FactSet, member: MemberContext) -> tuple[_Row, ...]:
    """Every R6 row of ``code`` over its supporting acts ``supporting`` (module docstring), in its tags' order."""
    out: list[_Row] = []
    sessions = sessions_of(R, supporting)
    for tag in rq.spec(code).tags:
        if tag in (Tag.R6_EXTENT, Tag.COLFULL):
            out += [_extent_row(tag, R, session) for session in sessions]
        elif tag is Tag.R6_TARGET and supporting:
            out.append(_target_row(R, supporting, sessions))
        elif tag is Tag.R6_CANNULATION:
            out += [_cannulation_row(R, session) for session in sessions]
        elif tag is Tag.R6_EM_BASIS and supporting:
            out.append(_em_basis_row(R, supporting))
        elif tag is Tag.R6_CONTEXT:
            out.append(_context_row(member))
    return tuple(out)


def r7_row(date_of_service: datetime.date | None, R: FactSet) -> _Row:
    """R7: the date of service known (document or member). Unknown, every code holds the encounter-scope service_date
    (unranked; cause date_unknown), resting on the document's date fact."""
    if date_of_service is not None:
        return _Row(_R7, evaluate.Truth.T, None)
    found = facts_.fact(R, None, _A.DATE_OF_SERVICE)
    held = HeldFact(fact=rq.fact_key(rq.FactKey.SERVICE_DATE), attribute=_A.DATE_OF_SERVICE, subject=None,
                    result=found.result, kind=_Q, cause=questions.DATE_UNKNOWN,
                    reason=found.reasons[0] if found.reasons else None, spans=tuple(sorted(set(found.spans))),
                    rank=None)
    return _Row(_R7, evaluate.Truth.U, None, (held,))


# --- ADDON (4.3's code-specific row: "43273, 91013, 99153, 99417 | its primary counted"; module docstring) ------------

# Each catalogue add-on (catalogue.Profile.addon; requirements_table's Tag.ADDON) -> the catalogue codes it is reported
# with: CPT's "use in conjunction with" codes for it, restricted to the catalogue's codes of its family. The design names
# the row and no primary set; this is the narrowest correct one (fail-closed: an add-on beside a code of its family that
# is not its primary is held, never READY) - the step's NOTES, question QA1. Code numbers only, no word.
ADDON_PRIMARIES: Mapping[int, frozenset[int]] = MappingProxyType({
    43273: frozenset({43260, 43261, 43262, 43263, 43264, 43265, 43274, 43275, 43276, 43277, 43278}),
    91013: frozenset({91010}),
    99153: frozenset({99152}),
    99417: frozenset({99205, 99215, 99245}),
})
ADDON_CAUSE = f'coding_rule:{Tag.ADDON.value}'  # the cause of an unmet ADDON row (4.4's coding_rule:<id>)
_ADDON_ITEM = rq.Item(rq.Rank.STATUS, rq.FactKey.PERFORMED_STATUS)  # D80's and D197's code-level row (RANK row 4)


def primaries(code: str) -> frozenset[str]:
    """The codes ``code`` is reported with when it is an add-on (``ADDON_PRIMARIES``, as code strings); empty for any
    other code."""
    found = catalogue.number(code)
    return frozenset(str(primary) for primary in ADDON_PRIMARIES.get(found, frozenset())) if found is not None \
        else frozenset()


def addon_hold(code: str, counted: Iterable[str], kept: Sequence[Span]) -> HeldFact | None:
    """4.3's ADDON row of ``code`` over the ``counted`` codes: None when ``code`` carries no ADDON tag or one of its
    primaries is counted (T); otherwise its witness (U) - code-level, as D80's and D197's holds are (performed_status at
    RANK's status row; subject, attribute and result None: D189's hold about no single fact), a question, cause
    coding_rule:ADDON, quoting the code's kept spans. An add-on the table names no primary for is never met
    (fail-closed). The read-time overlay recounts with it over a reviewer's counted set (the step's NOTES, request
    R7)."""
    if Tag.ADDON not in rq.spec(code).tags:
        return None
    if primaries(code) & frozenset(counted):
        return None
    return HeldFact(fact=_key(_ADDON_ITEM), attribute=None, subject=None, result=None, kind=_Q, cause=ADDON_CAUSE,
                    reason=None, spans=tuple(sorted(set(kept))), rank=_rank(_ADDON_ITEM))


def _addon_row(code: str, supporting: Sequence[Id], counted: Iterable[str], kept: Sequence[Span]) -> _Row | None:
    """The ADDON row of a code with supporting acts (None for a code without the tag, or with no supporting act:
    SUPPORT, or D80, already holds it)."""
    if not supporting or Tag.ADDON not in rq.spec(code).tags:
        return None
    held = addon_hold(code, counted, kept)
    if held is None:
        return _Row(Tag.ADDON.value, evaluate.Truth.T, None)
    return _Row(Tag.ADDON.value, evaluate.Truth.U, None, (held,))


def _addon_moved(found: Assessed, counted: frozenset[str], live: frozenset[str]) -> bool:
    """Whether a selected proposal no answer excluded has an ADDON row met over ``counted`` (every counted code) and
    unmet over ``live`` (those no answer excluded): an add-on the answers' passes assess again."""
    if found.answered is not None or found.bucket is not Bucket.SELECTED or found.evaluation is None:
        return False
    before = _addon_row(found.code, found.evaluation.supporting, counted, found.evidence.kept)
    after = _addon_row(found.code, found.evaluation.supporting, live, found.evidence.kept)
    return before is not None and after is not None and before.truth is not after.truth


# --- the considerations (4.4; 4.7's 52/53, same-day E/M and modifier review rows) -------------------------------------


def silent_slot(found: Fact) -> bool:
    """A SILENT slot, strictly - engine/classes.py's reading of the same completion fact (D217; refute-4c-r1 A): no claim
    (state None), result unknown, nothing left possible beside it (no option) and silence its only reason. An empty
    slot a doubt names (its reason, its readings kept as options), a contradicted one and one a check failed on are NOT
    silent: facts.silent reads the claim's state alone, which an empty slot a doubt names shares with silence."""
    return (found.state is None and found.result is Result.UNKNOWN and not found.options and bool(found.reasons)
            and all(reason is Reason.SILENT for reason in found.reasons))


def stopped_short(completion: Fact) -> bool:
    """Whether a session's completion gives the 52/53 consideration (4.7's row: "completion incomplete or terminated").
    - Established: incomplete or terminated as engine/classes.py reads the same fact (D217: "supported incomplete or
      terminated, or denied complete" - every value a denied complete leaves is stopped short; this repair's NOTES,
      question Q-S4c); supported complete, and a denial of incomplete or of terminated (each leaves complete possible),
      give none.
    - Not established - unresolved (pass 2 did not establish it, or a check failed), or doubted or contradicted by pass
      1, an empty slot a doubt names included - it gives the consideration WHATEVER value it claims: DECISIONS D244
      Q-S4, option (a), the installed reading ("When completion pass 2 did not establish completion, the code is READY
      with the 52|53 consideration"), so S4 (ii)'s misfiled "complete", which pass 2 did not establish, keeps it however
      pass 2 answered its control (S4's "dropped consideration (52/53)"; the NOTES, deviation 1).
    - A silent slot (``silent_slot``) states nothing and gives none.
    Never a hold and never a requirement met: R6:extent's and COLFULL's arms read only a supported completion."""
    if facts_.established(completion):
        if completion.result is Result.SUPPORTED:
            return completion.value in _STOPPED_SHORT
        return completion.value is Completion.COMPLETE
    return not silent_slot(completion)


def _incomplete(R: FactSet, supporting: Sequence[Id], sessions: Sequence[Id]) -> bool:
    """4.7's 52/53 row: a session of the code whose completion gives it (``stopped_short``: established incomplete or
    terminated, or, by D244 Q-S4, not established and not silent); an examination of it, or a supporting act, supported
    attempted_not_completed; or a cannulation of it supported failed (D61, D71, D107, C-9)."""
    for session in sessions:
        if stopped_short(facts_.fact(R, session, _A.COMPLETION)):
            return True
        for event in R.events:
            if not facts_.holds(facts_.fact(R, event, _A.SESSION), session):
                continue
            kind = facts_.fact(R, event, _A.KIND)
            if facts_.holds(kind, Kind.EXAMINATION) and facts_.holds(facts_.fact(R, event, _A.STATUS),
                                                                     Status.ATTEMPTED_NOT_COMPLETED):
                return True
            if facts_.holds(kind, Kind.CANNULATION) and facts_.holds(facts_.fact(R, event, _A.ACCESS_OUTCOME),
                                                                     AccessOutcome.FAILED):
                return True
    return any(facts_.holds(facts_.fact(R, event, _A.STATUS), Status.ATTEMPTED_NOT_COMPLETED) for event in supporting)


def considerations(key: str, selection: _Selection, R: FactSet, sessions: Sequence[Id],
                   joined: combination.Combination | None, rows: Sequence[_Row]) -> tuple[Consideration, ...]:
    """A counted code's considerations (module docstring), in 4.4's order; none for an excluded code."""
    if selection.excluded or selection.evaluation is None:
        return ()
    out: list[Consideration] = []
    supporting = selection.evaluation.supporting
    if any(row.incomplete for row in rows) or _incomplete(R, supporting, sessions):
        out.append(Consideration.INCOMPLETE)
    if joined is not None and selection.family in catalogue.EM_FAMILIES and joined.day.procedure_day:
        out.append(Consideration.SEPARATE_EM)
    if joined is not None and key in joined.reviews:
        out.append(Consideration.DISTINCT_LESION)
    return tuple(out)


# --- the per-code assembly (4.4) --------------------------------------------------------------------------------------


_ZERO_GLOBAL = 'XXX'  # a PFS row's global period of a code that is no procedure (v1's engine._procedural)


def procedural(selection: _Selection, pfs: Mapping[str, object] | None) -> bool:
    """engine._procedural (v1's): a non-E/M code of a procedural family, or with a global period other than XXX; a code
    with no PFS row counts (fail-closed). An excluded code is none."""
    if selection.family in catalogue.EM_FAMILIES or selection.evaluation is None:
        return False
    if selection.family in catalogue.PROCEDURAL_FAMILIES:
        return True
    return not pfs or pfs.get('global_days') != _ZERO_GLOBAL


_PROFESSIONAL_ROW = '26'  # a PFS row's professional-component modifier row (v1's checks.pctc_consideration)
_TECHNICAL_ROW = 'TC'  # its technical-component modifier row


def split_components(pfs: Mapping[str, object] | None) -> bool:
    """Whether a code's PFS row carries separate professional (26) and technical (TC) rows - v1's
    checks.pctc_consideration's test, read from the reference record (R9), never from the document: the codes whose
    PC/TC consideration reads the member's billing context, so their fingerprint carries it (v1's
    _relevant_context)."""
    rows = pfs.get('modifier_rows') if pfs else None
    if not isinstance(rows, (list, tuple)):
        return False
    return any(row == _PROFESSIONAL_ROW for row in rows) and any(row == _TECHNICAL_ROW for row in rows)


def session_acts(coding: Mapping[str, object]) -> dict[Id, combination.SessionActs]:
    """event_coding@2's sessions as combination.SessionActs (step 4d's R1, converted here from coverage's own record,
    one derivation): each session's reportable and doubted act ids; an unlisted entry (event None) is read by the
    combination from the FactSet."""
    out: dict[Id, combination.SessionActs] = {}
    sessions = coding.get('sessions')
    if not isinstance(sessions, Mapping):
        raise ValueError('event_coding@2 lists its sessions.')
    for label, record in sessions.items():
        if not isinstance(label, str) or not isinstance(record, Mapping):
            raise ValueError('event_coding@2 lists each session by its id.')

        def acts(name: str) -> tuple[Id, ...]:
            entries = record.get(name)
            if not isinstance(entries, Sequence):
                raise ValueError(f'event_coding@2 lists a session\'s {name} acts.')
            found = []
            for entry in entries:
                event = entry.get('event') if isinstance(entry, Mapping) else None
                if isinstance(event, str):
                    found.append(Id.parse(event))
            return tuple(found)

        out[Id.parse(label)] = combination.SessionActs(reportable=acts('reportable'), doubted=acts('doubted'))
    return out


def _trace(code: str, R: FactSet, evaluation: Evaluation, rows: Sequence[_Row]) -> tuple[Trace, ...]:
    """9.1's trace of a decided code: SUPPORT's rows and the code-specific rows on each supporting act, SUPPORT's on
    each bound candidate, then the R6 and R7 rows."""
    out: list[Trace] = []
    link = catalogue.code_link(code)
    groups = catalogue.requirements(link) if link.linked else ()
    bound = set(evaluation.bindings.values())
    for group in groups:
        for event in evaluate.candidates(R, group):
            if event not in evaluation.supporting and event not in bound:
                continue
            for row in evaluate.support(code, group, R, event).rows:
                out.append(Trace(row.requirement.value, row.truth, event, row.witnesses[0] if row.witnesses else None))
            if event in evaluation.supporting:
                for row in evaluate.code_rows(code, group, R, event):
                    out.append(Trace(row.requirement.value, row.truth, event,
                                     row.witnesses[0] if row.witnesses else None))
    out += [row.trace() for row in rows]
    return tuple(out)


def _facts_of(R: FactSet, subject: Id) -> object:
    table = R.events if subject.family is IdFamily.EVENT else R.sessions
    return jsonable(table.get(subject, {}))


def fingerprint(selection: _Selection, status: Outcome, held: Sequence[HeldFact], item: questions.Item | None,
                answered: Answered | None, found: Sequence[Consideration], R: FactSet, member: MemberContext,
                date_of_service: datetime.date | None) -> str:
    """The fingerprint over facts (module docstring): never a proposer or an origin, never a word."""
    evaluation = selection.evaluation
    supporting = evaluation.supporting if evaluation is not None else ()
    basis = {str(event): _facts_of(R, event) for event in supporting}
    basis.update({str(session): _facts_of(R, session) for session in sessions_of(R, supporting)})
    em = selection.family in catalogue.EM_FAMILIES
    context = {'setting': member.setting if em else None, 'patient_status': member.patient_status if em else None,
               'billing_context': member.billing_context if em or selection.pctc else None}
    return sha256_of(jsonable({
        'engine': ENGINE_VERSION_V2, 'requirements': REQUIREMENTS_VERSION, 'code': selection.code,
        'family': selection.family, 'units': selection.units, 'kept': selection.evidence.kept,
        'in_scope': not selection.evidence.scope_reason, 'status': status, 'evaluation': evaluation,
        'held': tuple(held), 'item': (item.held, item.message, item.fill) if item is not None else None,
        'answered': answered, 'considerations': tuple(found), 'facts': basis, 'context': context,
        'date_of_service': date_of_service}))


@dataclass(frozen=True)
class _Encounter:
    """What every proposal reads of the encounter: the FactSet, its coverage reader and sessions, the date of service,
    the member context, the reference rows, the combination over the counted codes, the proposal provider's name and
    the codes ADDON counts (the counted codes, less those a member's answer excluded, in the answers' passes); in a
    pass, ``joined`` is the combination with the competition the answers leave (``compete_without``, D260 and D270's
    DQ-2)."""
    R: FactSet
    reader: coverage.Reader
    sessions: Mapping[Id, coverage.Session]
    date_of_service: datetime.date | None
    member: MemberContext
    refs: Mapping[str, ReferenceRows]
    joined: combination.Combination
    members: Mapping[str, combination.Member]
    primary: str
    counted: frozenset[str] = frozenset()


def _matched(selection: _Selection, sessions_: Mapping[Id, coverage.Session]) -> Id | None:
    supporting = selection.evaluation.supporting if selection.evaluation is not None else ()
    return coverage.session_of(sessions_, selection.family, supporting)


def _assessed(key: str, selection: _Selection, enc: _Encounter, disagreements: tuple[Disagreement, ...]) -> Assessed:
    """One proposal assembled (4.4): the per-code rule's evaluation, R6, ADDON, the class rule, the bundling, the
    combination and R7 appended, ranked, the one item, the status, the considerations and the fingerprint."""
    R = enc.R
    refs = enc.refs.get(selection.code)
    pfs, mue = (refs.pfs, refs.mue) if refs is not None else (None, None)
    evaluation = selection.evaluation
    session = _matched(selection, enc.sessions)
    if evaluation is None:  # R1 refused it: excluded, not reinstatable, nothing more read (v1's _excluded_early)
        status = Outcome.EXCLUDED
        return Assessed(key=key, code=selection.code, family=selection.family, origin=selection.origin,
                        proposed_by=proposed_by(selection, enc.primary), bucket=Bucket.EXCLUDED, status=status,
                        units=selection.units, evidence=selection.evidence, reinstatable=False, session=None,
                        evaluation=None, held_facts=(), item=None, waits=(), answered=None, considerations=(),
                        competes=(),
                        disagreements=disagreements, primary_listed=selection.primary_listed, trace=(), pfs=None,
                        mue=None, fingerprint=fingerprint(selection, status, (), None, None, (), R, enc.member,
                                                          enc.date_of_service), question='')
    supporting = evaluation.supporting
    rows = r6_rows(selection.code, supporting, R, enc.member)
    addon = _addon_row(selection.code, supporting, enc.counted, selection.evidence.kept)
    if addon is not None:  # 4.3's ADDON, after the R6 rows (the code-specific rows' order) and before R7
        rows = (*rows, addon)
    r7 = r7_row(enc.date_of_service, R)
    trace = _trace(selection.code, R, evaluation, (*rows, r7))
    if evaluation.exclusion is not None:  # 4.6: excluded, reinstatable; what would still hold it, kept (v1's waits)
        status = Outcome.EXCLUDED
        waits = questions.ranked([held for row in (*rows, r7) for held in row.witnesses], R)
        return Assessed(key=key, code=selection.code, family=selection.family, origin=selection.origin,
                        proposed_by=proposed_by(selection, enc.primary), bucket=Bucket.EXCLUDED, status=status,
                        units=selection.units, evidence=selection.evidence, reinstatable=True, session=session,
                        evaluation=evaluation, held_facts=(), item=None, waits=waits, answered=None,
                        considerations=(), competes=(),
                        disagreements=disagreements, primary_listed=selection.primary_listed, trace=trace, pfs=pfs,
                        mue=mue, fingerprint=fingerprint(selection, status, (), None, None, (), R, enc.member,
                                                         enc.date_of_service), question='')
    extra: list[HeldFact] = [held for row in rows for held in row.witnesses]
    extra += classes.enteroscopy_hold(selection.code, supporting, R)
    extra += coverage.bundling(selection.code, supporting, enc.reader)
    extra += enc.joined.held.get(key, ())
    extra += r7.witnesses
    extra = list(dict.fromkeys(extra))
    held = questions.ranked((*evaluation.held_facts, *extra), R)
    item = evaluate.item(selection.code, selection.evidence.kept, R, evaluation, extra=extra,
                         kept_words=selection.evidence.runs)
    if item is None and held:  # one item per held code (4.8, D182), whatever the binding leaves on it
        item = questions.item(held, (), evaluate.code_facts(selection.code), R, supporting)
    if item is not None and item.held.fact == _key(_SETTING_ITEM) and not enc.member.patient_status:
        item = replace(item, fill=replace(item.fill, both=True))  # R6:context: its sentence names both
    status = Outcome.NEEDS_CLARIFICATION if held else Outcome.READY
    sessions = tuple(dict.fromkeys((*sessions_of(R, supporting), *((session,) if session is not None else ()))))
    found = considerations(key, selection, R, sessions, enc.joined, rows)
    return Assessed(key=key, code=selection.code, family=selection.family, origin=selection.origin,
                    proposed_by=proposed_by(selection, enc.primary), bucket=Bucket.SELECTED, status=status,
                    units=selection.units, evidence=selection.evidence, reinstatable=False, session=session,
                    evaluation=evaluation, held_facts=held, item=item, waits=(), answered=None, considerations=found,
                    competes=tuple(enc.joined.competes.get(key, ())), disagreements=disagreements,
                    primary_listed=selection.primary_listed, trace=trace, pfs=pfs, mue=mue,
                    fingerprint=fingerprint(selection, status, held, item, None, found, R, enc.member,
                                            enc.date_of_service),
                    question=question_fingerprint(selection.code, selection.family, item) if item is not None else '')


# --- member answers (4.8: unchanged; D7, D182) ------------------------------------------------------------------------


_OVERLAY_FACTS: frozenset[str] = frozenset({rq.fact_key(rq.FactKey.BASE_INCLUDED), rq.fact_key(rq.FactKey.SEPARATE_EM),
                                            rq.fact_key(rq.FactKey.COMPETING_CODES)})
# The key-bound facts (studio.validation.questions.KEY_BOUND_FACTS; FINAL-V2 4.8: "the key-bound facts (base_included,
# separate_em), which bind by key"): read time binds an answer to one by its (code, family, fact) key whatever
# fingerprint it carries (questions.bind) - the overlay words their questions anew with each review decision.
_KEY_BOUND_FACTS: frozenset[str] = frozenset({rq.fact_key(rq.FactKey.BASE_INCLUDED),
                                              rq.fact_key(rq.FactKey.SEPARATE_EM)})
# The encounter-scope date of service (4.8: "service_date | encounter scope, as today"): a member settles it by entering
# the date, never by an answer that would exclude a code whose only hold it is.
_ENCOUNTER_FACT = rq.fact_key(rq.FactKey.SERVICE_DATE)
# The competing question (4.8 RANK 22): it offers no answer - codes competing for one act are settled by rejecting one
# (studio/answers.py, P-ADMIT2) - so no answer to it is read at assess (``overlay_bound``).
_COMPETING_FACT = rq.fact_key(rq.FactKey.COMPETING_CODES)


def engine_reads(answer: AnswerInput) -> bool:
    """v1's _MemberAnswers.engine_reads: an answer naming its code and its question's fingerprint, to a fact neither
    key-bound nor competing_codes (those are the read-time overlay's) - nor the encounter-scope service_date, which no
    answer settles."""
    return (bool(answer.code and answer.question) and answer.fact not in _OVERLAY_FACTS
            and answer.fact != _ENCOUNTER_FACT)


def _answers_of(given: Sequence[AnswerInput]) -> list[tuple[AnswerInput, Answer]]:
    """The standing answers that hold an answer value, in v1's order (id, code, family, fact, value, question); an
    answer naming no value a question takes is left out (v1's bind)."""
    out = []
    for answer in given:
        for name in ('code', 'family', 'fact', 'value', 'question', 'answer_id'):
            if not isinstance(getattr(answer, name), str):
                raise ValueError('A member answer names its code, family, fact, value, question and id as text.')
        value = _member(Answer, answer.value)
        if value is not None:
            out.append((answer, value))
    return sorted(out, key=lambda pair: (pair[0].answer_id, pair[0].code, pair[0].family, pair[0].fact,
                                         pair[0].value, pair[0].question))


def _apply_answers(proposals: list[Assessed], answers: Sequence[tuple[AnswerInput, Answer]], R: FactSet,
                   member: MemberContext, date_of_service: datetime.date | None,
                   selections: Mapping[str, _Selection]) -> tuple[list[Assessed], list[AnswerApplied],
                                                                   list[AnswerEarlier]]:
    """Each engine-read answer bound to the item it was given to (module docstring): its code EXCLUDED, nothing else
    moved."""
    asked: dict[tuple[str, str, str], tuple[str, list[str]]] = {}
    for p in proposals:
        if p.bucket is Bucket.SELECTED and p.item is not None:
            slot = asked.setdefault((p.code, family_slug(p.family), p.item.held.fact), (p.question, []))
            slot[1].append(p.key)
    bound: dict[str, list[tuple[AnswerInput, Answer]]] = {}
    applied: list[AnswerApplied] = []
    earlier: list[AnswerEarlier] = []
    for answer, value in answers:
        if not answer.code:
            continue  # a service answer: _close_services
        if not engine_reads(answer):
            # the encounter-scope date of service is settled by a date, by nobody's answer: never the overlay's either
            why = Unbound.NOT_APPLIED if answer.fact == _ENCOUNTER_FACT else Unbound.OVERLAY_READ
            earlier.append(AnswerEarlier(answer.answer_id, answer.code, answer.family, answer.fact, value, why))
            continue
        found = asked.get((answer.code, answer.family, answer.fact))
        if found is None:
            earlier.append(AnswerEarlier(answer.answer_id, answer.code, answer.family, answer.fact, value,
                                         Unbound.NO_LONGER_ASKED))
            continue
        question, keys = found
        if answer.question != question:
            earlier.append(AnswerEarlier(answer.answer_id, answer.code, answer.family, answer.fact, value,
                                         Unbound.ASKED_DIFFERENTLY))
            continue
        for key in keys:
            bound.setdefault(key, []).append((answer, value))
        applied.append(AnswerApplied(answer.answer_id, Scope.PROPOSAL, answer.code, answer.family, answer.fact, value,
                                     tuple(keys)))
    out = []
    for p in proposals:
        given = bound.get(p.key)
        if not given or p.item is None:
            out.append(p)
            continue
        answered = Answered(fact=p.item.held.fact, value=given[0][1],
                            answers=tuple(sorted({answer.answer_id for answer, _ in given})))
        selection = selections[p.key]
        status = Outcome.EXCLUDED
        out.append(replace(p, bucket=Bucket.EXCLUDED, status=status, reinstatable=False, answered=answered,
                           fingerprint=fingerprint(selection, status, p.held_facts, p.item, answered,
                                                   p.considerations, R, member, date_of_service)))
    return out, applied, earlier


def overlay_bound(proposals: Sequence[Assessed], answers: Sequence[tuple[AnswerInput, Answer]]) -> dict[str, Answer]:
    """{key: answer value} of every selected proposal a member's answer bound by key binds as read time binds it
    (DECISIONS D270, DQ-2; module docstring, "Member answers"): an answer with a code that read time binds to a question
    by its (code, family, fact) key alone (studio.validation.questions.bind) - one to a key-bound fact, whatever
    fingerprint it carries, or one that carries no fingerprint (the earlier form) - which the engine therefore never
    reads (``engine_reads``), bound to every selected proposal whose ONE item has that code, family slug and fact key:
    the question the renderer stores for it, which the overlay binds the answer to. Never an answer to the encounter's
    date of service (no code asks it: the date item is the encounter's question) or to the competing question (the
    competing question offers no answer: codes competing for one act are settled by rejecting one - studio/answers.py,
    P-ADMIT2; this step's NOTES, question Q1). Each proposal is bound by the first answer that binds it (the answers'
    order). Read for the competition alone: the caller takes a proposal bound "Not documented" out of the competition
    and moves nothing else of it."""
    asked: dict[tuple[str, str, str], list[str]] = {}
    for p in proposals:
        if p.bucket is Bucket.SELECTED and p.item is not None:
            asked.setdefault((p.code, family_slug(p.family), p.item.held.fact), []).append(p.key)
    bound: dict[str, Answer] = {}
    for answer, value in answers:
        by_key = answer.fact in _KEY_BOUND_FACTS or not answer.question
        if not answer.code or not by_key or answer.fact == _ENCOUNTER_FACT or answer.fact == _COMPETING_FACT:
            continue  # a service answer, one bound by its fingerprint (the engine's), the date's or the competition's
        for key in asked.get((answer.code, answer.family, answer.fact), ()):  # not asked: read time binds it to none
            bound.setdefault(key, value)
    return bound


def compete_without(joined: combination.Combination, members: Mapping[str, combination.Member],
                    out: Collection[str], R: FactSet) -> combination.Combination:
    """``joined`` (combination.combine over ``members``, in combine's member order) with the competition read again
    without the members whose keys are in ``out`` - the codes a member answered "Not documented", the engine reading the
    answer (DECISIONS D260, read time's D249 reading) or the overlay binding it (D270, DQ-2: ``overlay_bound``; module
    docstring, "Member answers"). The competition is combine's own rule, read over the claims combine recorded for the
    members left: combination.competition and combination.contested over the documented acts' claims, and the same rule
    over the synthetic acts' claims (DECISIONS D231 row 5, as combine reads both: a member's rivals are the union, in
    that order). Each member's competing_codes hold is replaced by the one that
    competition gives (combination.competing_hold, quoting only the acts and synthetic acts it still shares), in
    combine's order (base or within, competing, then the same-day holds). A member whose every rival is out has no
    competing hold left (a member that is out has none either: it competes with nothing); one with a rival left keeps
    its hold, naming only the rivals left. Every other record - claims, bases, within, the procedure day, statements,
    reviews - is combine's over every member: the answered code still counts there (session decision (e)). ``joined``
    itself when no member is out. Read time is asked to read the same function over the same members (the step's
    NOTES, request R1)."""
    if not any(key in members for key in out):
        return joined
    left = [member for member in members.values() if member.key not in out]
    entries = [(member.key, member.code, member.origin, joined.claims[member.key]) for member in left]
    synthetic = [(member.key, member.code, member.origin, joined.unlisted_claims.get(member.key, ()))
                 for member in left]
    # combine's own rule: competition/contested over the documented acts, its generic helpers over the synthetic acts'
    # indices (DECISIONS D231 row 5) - one implementation, read through its names as I3 reads evaluate's (D262)
    filed_rivals, synthetic_rivals = combination.competition(entries), combination._rivals(synthetic)
    competes = {member.key: tuple(dict.fromkeys(filed_rivals.get(member.key, ())
                                                + synthetic_rivals.get(member.key, ())))
                for member in left if member.key in filed_rivals or member.key in synthetic_rivals}
    shared, shared_unlisted = combination.contested(entries), combination._shared(synthetic)
    held: dict[str, tuple[HeldFact, ...]] = {}
    for key, items in joined.held.items():
        kept = [found for found in items if found.cause != combination.COMPETING_CAUSE]
        if key in competes:
            first = kept[0].cause if kept else None
            at = 1 if first in (combination.BASE_CAUSE, combination.WITHIN_CAUSE) else 0
            kept.insert(at, combination.competing_hold(shared.get(key, ()), R, shared_unlisted.get(key, ())))
        held[key] = tuple(kept)
    return replace(joined, competes=competes, contested=shared, unlisted_contested=shared_unlisted, held=held)


def _moved(found: Assessed, was: _Encounter, now: _Encounter) -> bool:
    """Whether a selected proposal no answer excluded reads another competition, or another ADDON row, over ``now`` (the
    counted set and the competition the answers leave) than over ``was`` (the encounter it was assessed with): the
    proposals a pass assesses again (module docstring, "Member answers"), but those an overlay-bound "Not documented"
    took out of the competition, which ``_bind_in_passes`` leaves as their answer found them. The assembly reads the
    combination only through the code's own holds and rivals and the procedure day and modifier reviews, which
    ``compete_without`` never moves, so these are exact."""
    if found.answered is not None or found.bucket is not Bucket.SELECTED or found.evaluation is None:
        return False
    key = found.key
    if (was.joined.held.get(key, ()) != now.joined.held.get(key, ())
            or was.joined.competes.get(key, ()) != now.joined.competes.get(key, ())):
        return True
    return _addon_moved(found, was.counted, now.counted)


def _kept_fingerprint(found: Assessed, before: Assessed) -> Assessed:
    """``found`` - a proposal a pass assessed again because the answers moved its competition or its ADDON row - with
    the fingerprint of ``before``, the same proposal assessed without the answers, while its status is unchanged (module
    docstring, "Fingerprints over facts"): another code's answer reaches it through a cross-code rule alone, so a
    reviewer's decision on it carries across the AGAIN recompute that reads the answer (review._carry_decisions finds
    its candidates by fingerprint), as the installed release carries it (studio/validation/engine.py,
    _MemberAnswers.apply, refutation cycle 4, answers 1: "another code's checks read again without an answered code keep
    that code's fingerprint") and as AMENDMENT-1 6.4 reads the fingerprint (a change it does not carry keeps the
    decision). Once its status moves (a rival released to READY, an add-on held), it keeps the fingerprint of what it
    now is: the status is a fingerprint input (FINAL-V2 6.5), so a decision made on the other status never carries onto
    it, and the decision is cleared naming the status that changed (review._what_differs)."""
    if found.status is before.status:
        return replace(found, fingerprint=before.fingerprint)
    return found


def _bind_in_passes(unanswered: list[Assessed], given: Sequence[tuple[AnswerInput, Answer]], enc: _Encounter,
                    by_key: Mapping[str, _Selection]) -> tuple[list[Assessed], list[Assessed], list[AnswerApplied],
                                                               list[AnswerEarlier], _Encounter]:
    """The member answers bound in passes (module docstring, "Member answers"): (the proposals, the proposals before the
    answers - each code assessed again in a pass replaced -, the answers applied and not, and the encounter of the last
    pass, whose combination is the Assessment's). Each pass reads the codes the answers excluded - none counts for
    ADDON, and those answered "Not documented" leave the competition (``compete_without``) - and the codes an
    overlay-bound "Not documented" binds (``overlay_bound``, DECISIONS D270's DQ-2), which leave the competition and
    nothing else; every other proposal that moved (``_moved``) is assessed again over that encounter - keeping the
    fingerprint it has without the answers while its status is unchanged (``_kept_fingerprint``) - and the answers are
    bound again over the result. A code an answer excluded or took out of the competition is never assessed again (its
    answer stands: an overlay-bound code keeps the item read time binds its answer to), so those codes only grow and a
    further pass follows only a new one: at most one pass per newly excluded code (an overlay binding counted as one),
    while one proposal can be assessed again in several passes (em_chain's 99214: narrowed, then released)."""
    R, member, date_of_service = enc.R, enc.member, enc.date_of_service
    first = {p.key: p for p in unanswered}  # every proposal as assessed without the answers
    proposals, applied, earlier = _apply_answers(unanswered, given, R, member, date_of_service, by_key)
    assessed_with = {p.key: enc for p in unanswered}
    withdrawn: set[str] = set()  # the codes an overlay-bound "Not documented" took out of the competition: each stands
    while True:
        excluded = [p for p in proposals if p.answered is not None]
        withdrawn |= {key for key, value in overlay_bound(proposals, given).items() if value is Answer.NOT_DOCUMENTED}
        out = frozenset(p.key for p in excluded if p.answered is not None and p.answered.value is Answer.NOT_DOCUMENTED)
        current = replace(enc, counted=enc.counted - frozenset(p.code for p in excluded),
                          joined=compete_without(enc.joined, enc.members, out | withdrawn, R))
        again = {p.key for p in proposals if p.key not in withdrawn and _moved(p, assessed_with[p.key], current)}
        if not again:
            return proposals, unanswered, applied, earlier, current
        unanswered = [_kept_fingerprint(_assessed(p.key, by_key[p.key], current, p.disagreements), first[p.key])
                      if p.key in again else p for p in unanswered]
        assessed_with.update((key, current) for key in again)
        proposals, applied, earlier = _apply_answers(unanswered, given, R, member, date_of_service, by_key)


def _close_services(service_items: Sequence[ServiceQuestion], answers: Sequence[tuple[AnswerInput, Answer]]
                    ) -> tuple[list[ServiceQuestion], list[AnswerApplied], list[AnswerEarlier]]:
    """Each service answer (no code) bound by v1's bind to the service questions it was given to - those of its (family,
    fact) asked with its fingerprint, or every one of them for an answer recorded with none - closing each question it
    is the first answer to (answers in v1's order). An answer every question of which an earlier answer closed is
    recorded as not applied (v1's record); one whose (family, fact) is not asked, or asked only with other
    fingerprints, as no longer asked or asked differently. Nothing is excluded."""
    asked: dict[tuple[str, str], list[int]] = {}
    for index, found in enumerate(service_items):
        family = family_slug(found.item.family) if found.item.family is not None else ''
        asked.setdefault((family, found.item.item.fact), []).append(index)
    closed: dict[int, list[str]] = {}
    applied: list[AnswerApplied] = []
    earlier: list[AnswerEarlier] = []
    for answer, value in answers:
        if answer.code:
            continue
        indices = asked.get((answer.family, answer.fact), [])
        matching = [index for index in indices if not answer.question
                    or service_items[index].question == answer.question]
        if not indices or not matching:
            earlier.append(AnswerEarlier(answer.answer_id, '', answer.family, answer.fact, value,
                                         Unbound.NO_LONGER_ASKED if not indices else Unbound.ASKED_DIFFERENTLY))
            continue
        fresh = [index for index in matching if index not in closed]
        if not fresh:  # every question it answers was closed by an earlier answer: bound, applied to nothing (v1)
            earlier.append(AnswerEarlier(answer.answer_id, '', answer.family, answer.fact, value, Unbound.NOT_APPLIED))
            continue
        for index in fresh:
            closed[index] = [answer.answer_id]
        applied.append(AnswerApplied(answer.answer_id, Scope.SERVICE, '', answer.family, answer.fact, value, ()))
    out = [replace(found, closed=tuple(closed.get(index, ()))) for index, found in enumerate(service_items)]
    return out, applied, earlier


# --- the entry --------------------------------------------------------------------------------------------------------


def assess(*, inventory: object, date_of_service: datetime.date | None, text: str, pages: Sequence[object],
           integrity: Integrity, provider_status: str, proposals: ProviderInput | None, reference: Lookup,
           member: MemberContext, label: Callable[[coverage.Session], str],
           participants: Sequence[ParticipantInput] = (), second: ProviderInput | None = None,
           answers: Sequence[AnswerInput] = ()) -> Assessment:
    """The assessment of one revision from its stored v2 inventory (module docstring). ``inventory``:
    store.textfree_v2's view of the row (DECISIONS D188), read through facts.effective against ``date_of_service`` - the
    effective date of service by member precedence (interpretation/dates.py, engine/derive.py), None when unknown.
    ``text`` and ``pages``: the revision's, read by ``integrity`` alone (R1). ``provider_status`` and ``proposals``: the
    proposal provider's outcome and normalized answer (read only when it succeeded). ``reference``: the prefetched
    reference lookup (R9). ``member``: the member-entered context (D3). ``label``: how completeness names a session not
    listed (step 3c's wording; coverage.completeness). ``participants``, ``second`` and ``answers``: the configured
    participants, the bounded second review and the standing member answers."""
    R = facts_.effective(inventory, date_of_service)
    return assess_facts(R, date_of_service=date_of_service, text=text, pages=pages, integrity=integrity,
                        provider_status=provider_status, proposals=proposals, reference=reference, member=member,
                        label=label, participants=participants, second=second, answers=answers)


def assess_facts(R: FactSet, *, date_of_service: datetime.date | None, text: str, pages: Sequence[object],
                 integrity: Integrity, provider_status: str, proposals: ProviderInput | None, reference: Lookup,
                 member: MemberContext, label: Callable[[coverage.Session], str],
                 participants: Sequence[ParticipantInput] = (), second: ProviderInput | None = None,
                 answers: Sequence[AnswerInput] = ()) -> Assessment:
    """``assess`` over a FactSet ``R`` the caller built with facts.effective (the assembly every caller shares; tests
    hand it a settled FactSet). Pure: identical inputs give an identical Assessment (P-DET)."""
    status = _member(ProviderStatus, provider_status)
    if status is None:
        raise ValueError(f'Unknown provider status {provider_status!r}.')
    response = proposals if status is ProviderStatus.SUCCEEDED else None
    if status is ProviderStatus.SUCCEEDED and response is None:
        raise ValueError('A succeeded provider status needs its normalized response.')
    reader = coverage.Reader(R)
    sessions_ = coverage.sessions(R)
    harness = _Harness(participants, text, pages, integrity) if participants else None
    given = _answers_of(answers)
    selections: list[_Selection] = []
    alternatives: list[Alternative] = []
    second_record: SecondReviewRecord | None = None
    unlisted = 0
    if response is not None and not response.refused:
        listable = [c for c in response.codes if _listable(c.code)]
        unlisted = len(response.codes) - len(listable)
        selections = [_select(group, text, pages, integrity, R) for group in _merge_selected(listable)]
        if second is not None:
            selections, second_alternatives, second_record = _second_review(second, selections, text, pages,
                                                                             integrity, R, reader, sessions_)
        else:
            second_alternatives = []
        alternatives = [Alternative(key=f'alt:{index}', code=item.code, family=catalogue.family_for_code(item.code),
                                    origin=Origin.PRIMARY, proposed_by=(response.provider,), why=NotAdded.LISTED,
                                    role=_member(ProviderRole, item.role),
                                    evidence=admit(item.code, item.evidence, text, pages, integrity))
                        for index, item in enumerate(c for c in listable
                                                     if _member(ProviderRole, c.role) is not ProviderRole.SELECTED)]
        alternatives += second_alternatives
    if harness is not None:
        selections, participant_alternatives = harness.merge(selections, R)
        alternatives += participant_alternatives
    keys = _keys(selections)
    refs = {s.code: reference.lookup(s.code, date_of_service) for s in selections if s.decidable}
    # a code whose PFS row splits the components: its fingerprint carries the billing context (v1's _relevant_context)
    selections = [replace(s, pctc=split_components(refs[s.code].pfs)) if s.code in refs else s for s in selections]
    by_key = dict(zip(keys, selections))
    counted = [(key, s) for key, s in zip(keys, selections) if not s.excluded and s.evaluation is not None]
    coding = coverage.event_coding(reader, sessions_, {key: (_matched(s, sessions_), s.evaluation.supporting)
                                                        for key, s in zip(keys, selections)
                                                        if s.evaluation is not None})
    members = {key: combination.Member(key=key, code=s.code, family=s.family, session=_matched(s, sessions_),
                                       supporting=s.evaluation.supporting if s.evaluation is not None else (),
                                       origin=s.origin.value,
                                       procedural=procedural(s, refs[s.code].pfs if s.code in refs else None),
                                       supported=bool(s.evaluation is not None and s.evaluation.supporting
                                                      and not s.evaluation.held_facts))
               for key, s in counted}
    joined = combination.combine(tuple(members.values()), session_acts(coding), R)
    enc = _Encounter(R=R, reader=reader, sessions=sessions_, date_of_service=date_of_service, member=member,
                     refs=refs, joined=joined, members=members,
                     primary=response.provider if response is not None else '',
                     counted=frozenset(s.code for _, s in counted))
    proposals_ = [_assessed(key, s, enc, harness.disagreements(s.code) if harness is not None and s.decidable else ())
                  for key, s in zip(keys, selections)]
    proposals_ = [p for p in proposals_ if p.bucket is Bucket.SELECTED] + \
                 [p for p in proposals_ if p.bucket is Bucket.EXCLUDED]
    # the answers, bound in passes (module docstring, "Member answers"): ADDON counts no code a member's answer excluded
    # (fail-closed), and a code a member answered "Not documented" leaves the competition (DECISIONS D260, as read time
    # reads it, D249) - an overlay-bound answer included, read for the competition alone (D270, DQ-2); every code either
    # moves is assessed again and the answers are bound again over the result (an add-on's or a released rival's own
    # answer binds to its new item)
    proposals_, unanswered, applied, earlier, enc = _bind_in_passes(list(proposals_), given, enc, by_key)
    # the reconciliation counts every code the decisions leave selected, a code a member's answer excluded included: a
    # member's answer never releases what its code's presence covers or holds (v1's assess)
    final = coverage.reconcile(reader, _counted_of(selections, keys), procedure_day=bool(joined.day.done),
                               sessions_=sessions_)
    asked = {(p.item.held.subject, p.item.held.fact) for p in unanswered if p.item is not None}
    holding = tuple(dict.fromkeys(p.item.held.subject for p in unanswered if p.item is not None
                                  and p.item.held.subject is not None
                                  and p.item.held.subject.family is IdFamily.EVENT))
    service_items = coverage.in_doubt_questions(reader, final, asked, holding)
    service_items += coverage.service_extent_questions(reader, sessions_, asked)
    services_ = [ServiceQuestion(found, service_fingerprint(found)) for found in service_items]
    services_, service_applied, service_earlier = _close_services(services_, given)
    applied += service_applied
    earlier += service_earlier
    open_items = sum(1 for p in proposals_ if p.bucket is Bucket.SELECTED and p.item is not None
                     and p.item.held.rank is not None)
    open_items += sum(1 for found in services_ if not found.closed) + (1 if date_of_service is None else 0)
    unverified = {(held.subject, held.attribute) for _, s in counted if s.evaluation is not None
                  for held in s.evaluation.held_facts if held.result in (Result.UNRESOLVED, Result.UNKNOWN,
                                                                          Result.CONTRADICTED)}
    conflicts = sum(1 for event in R.events for pair in reader.pairs(event)  # pairing.pairs, by act, cached
                    if pair.relation is pairing.Relation.CONTRADICTION)
    complete = dict(coverage.completeness(final, sessions_, open_questions=open_items,
                                          provider_ok=response is not None and not response.refused,
                                          conflicts=conflicts, label=label, unverified=len(unverified)))
    complete.update(_completeness_records(final, sessions_, coding, applied, earlier, given, services_))
    participants_record = harness.records() if harness is not None else ()
    return Assessment(versions=MappingProxyType(versions()), date_of_service=date_of_service,
                      date_fact=facts_.fact(R, None, _A.DATE_OF_SERVICE), provider_status=status,
                      codes=tuple(proposals_), alternatives=tuple(alternatives), service_questions=tuple(services_),
                      coverage=final, combination=enc.joined, event_coding=MappingProxyType(dict(coding)),
                      completeness=MappingProxyType(complete), services=MappingProxyType(services_stub()),
                      answers=tuple(applied), earlier_answers=tuple(earlier), participants=participants_record,
                      second_review=second_record, unlisted_codes=unlisted)


def proposed_by(selection: _Selection, primary: str) -> tuple[str, ...]:
    """Who proposed a code (v1's ``[PRIMARY] + proposers``): the proposal provider first for a code it or its second
    review selected, then the participants that quoted it exactly, each once. Agreement adds names here and nothing
    else (4.12)."""
    first = (primary,) if primary and selection.origin is not Origin.PARTICIPANT else ()
    return tuple(dict.fromkeys(first + selection.proposers))


def _applied_record(applied: Sequence[AnswerApplied], given: Sequence[tuple[AnswerInput, Answer]],
                    services_: Sequence[ServiceQuestion]) -> list[dict[str, object]]:
    """The member answers' applied record (v1's record): each AnswerApplied's fields, plus the fingerprint the answer
    carries (``question``) and the fingerprint of the question it was bound to (``asked``: a proposal's item, which a
    bound answer carries; the first service question it closed) - which answers.py binds a new answer to (refutation
    cycle 3, C3-4)."""
    carried = {answer.answer_id: answer.question for answer, _ in given}
    closed: dict[str, str] = {}
    for found in services_:
        for answer_id in found.closed:
            closed.setdefault(answer_id, found.question)
    out: list[dict[str, object]] = []
    for entry in applied:
        record = {field.name: jsonable(getattr(entry, field.name)) for field in fields(entry)}
        record['question'] = carried.get(entry.answer, '')
        record['asked'] = closed.get(entry.answer, '') if entry.scope is Scope.SERVICE else carried.get(entry.answer, '')
        out.append(record)
    return out


def _completeness_records(final: coverage.Coverage, sessions_: Mapping[Id, coverage.Session],
                          coding: Mapping[str, object], applied: Sequence[AnswerApplied],
                          earlier: Sequence[AnswerEarlier], given: Sequence[tuple[AnswerInput, Answer]],
                          services_: Sequence[ServiceQuestion] = ()) -> dict[str, object]:
    """v1's completeness additions, text-free: the unresolved items, the bundled acts, the sessions not listed, the
    covered sessions, the sessions read as part of another, INVENTORY_PROBLEMS, event_coding@2 and, with standing
    answers, the member answers' record (``_applied_record``'s applied entries)."""
    out: dict[str, object] = {
        'unresolved_items': coverage.unresolved_record(final.unresolved),
        'bundled': coverage.bundled_record(final.bundled),
        'not_listed': [{'service': str(session.id), 'family': session.kind.value if session.kind is not None else None}
                       for session in final.not_listed],
        'covered': {str(session): list(codes) for session, codes in final.covered.items()},
        'included_by': {str(session): list(codes)
                        for session, codes in coverage.included_by(sessions_, final.covered).items()},
        'inventory_problems': list(INVENTORY_PROBLEMS),
        'event_coding': coding,
    }
    if given:
        out['member_answers'] = {'form': QUESTION_FORM, 'applied': _applied_record(applied, given, services_),
                                 'earlier': jsonable(tuple(earlier))}
    return out
