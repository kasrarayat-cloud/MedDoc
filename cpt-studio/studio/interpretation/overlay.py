"""The read-time overlay of a design v2 assessment (docs/gemini-migration/FINAL-V2.md 4.8 "Read time", 6.2, 6.5 and 9.3;
step 5c of its 8.1; the slice S11 overlay of design/FINAL.md 8.1, rewired): the stored rows of an assessment the
events engine made at cpt-studio-events@2 or @3 (AMENDMENT-2 8.1: READ_RECORDS), as its CURRENT decisions and member
answers leave them, recomputed at read time from the persisted inventory by the engine's own functions. Pure: stored
rows, decisions, answers and the FactSet in, views out - no database, no clock, no provider, and no document text (the FactSet holds none; FINAL-V2 1.7,
D188).

**What it reads** (FINAL-V2 6.5): ``completeness['event_coding']`` at the versions of ``READ_CODINGS`` ONLY (both design
v2 families, @2 and @3, AMENDMENT-2 8.1; the writer writes ``CODING_VERSION``, engine/coverage.CODING_VERSION, @3) - @1
and any other version are UNREADABLE, fail-closed - and the FactSet of the frozen settled inventory the
assessment was made from, built here by ``reading`` with engine/facts.effective against the effective date of service
the assessment was made with (never facts.factset: the triage's hand-off 2d:R8), so assess and read time have identical
inputs (S3's hazard 5: no date re-judge skipped, no text read). readers.EventReader loads the row through store.load_v2
(checked against the revision text's sha256 and both runs' response bytes) and store.textfree_v2 (D188) and hands the
view here.

**The stored v2 record** (what this module reads of one cpt-studio-events@2 proposal; the renderer that persists the
engine's Assessment writes it - this step's NOTES, request R1): the Proposal's code, key, family slug, bucket, status,
reinstatable, checks and ``evidence`` (R1's kept spans, read as offsets); and in ``support``: ``event_reading``
(cpt-studio-events@2), ``held_facts`` (FINAL-V2 4.8: every held fact, ranked, as engine/assess.jsonable writes a
HeldFact), ``kept_words`` (the kept spans' letter-or-digit runs, [start, end] pairs, or null: assess's
Evidence.runs), ``procedural`` (assess.procedural), ``origin``, ``competes``, ``reinstatement_waits`` ([{fact,
question}], v1's structured form), ``summary`` and the member-answer marker (questions.ANSWERED_SUPPORT). A record this
release cannot read whole is UNREADABLE (``read_record``): nothing is recomputed from it.

**Read time** (FINAL-V2 4.8): with no decision and no answer every view equals its stored proposal - an assessment
that read an overlay-bound answer for the competition (DECISIONS D270 DQ-2) with that answer standing, as it read it:
with the answer gone the competition it released is restored. On every read
that has the FactSet, ``recount`` runs the per-code rule again over the persisted inventory for every counted code
(engine/evaluate.decide, pure; ``counted_codes`` gives the same to the coverage), the combination - base_included,
base_within, competing_codes and the same-day holds, engine/combination.combine, the function assess runs (one
implementation) - and engine/assess's ADDON row (DECISIONS D268: engine/assess.addon_hold, the function assess's row
calls) over the engine's own counted set and over the reviewer's; it is refused whole (fail-closed: stored stands,
marked stale where the counted set moved) when the engine's own counted set does not reproduce a stored record - a
stored competing or ADDON hold it does not give is never carried as a hold read time does not recompute. The ADDON row
reads the codes assess counts for it: a primary the reviewer rejects, or a member's answer binds (read by the engine,
or bound here, of either value: DECISIONS D283, G1-03), is no longer counted, so an add-on whose every counted primary
is gone is held by the row (coding_rule:ADDON) - its item the row's own message, ADDON, worded from the codes alone
(``TEXT_FREE``: DECISIONS D284, G3-15), so read time words it afresh (``recomputed``, never stale), the add-on held and
never approvable alone - and reinstating a primary releases it. Once the decisions move the COUNTED set (a rejection, a
reinstatement), each code's stored ``held_facts`` lose the cross-code holds of the engine's own set and gain those of
the reviewer's at their rank (engine/questions.ranked), and
the code presents the first live item on its binding (engine/questions.item over engine/evaluate.groups: the binding
reads the per-code rule's witnesses only, so it never moves); a released item gives way to the next. An item that stays
but whose words name the combination's records (the codes a base rule names, a competition's rivals, the same-day acts)
is worded again when those records moved, so a rejected code is never named (``_renamed``). The date of service's item
is the encounter's own question (FINAL-V2 4.8: "service_date | encounter scope"; the renderer asks it once, at
encounter scope): a code whose live item it is keeps no question of its own, and stays held. The separate-lesion
modifier review is the combination's over the effective set, on every read. A changed item is worded by wording.build
only for the messages whose sentence reads no document text (``TEXT_FREE``: the base, within, competing, same-day
separate-visit, member-context, plain date and ADDON items, its slots filled from the combination's own records and,
for ADDON, from the codes alone); any other
changed item keeps the stored question and is marked stale (the code stays held). A member's answer binds to the item a
code presents: once read time has recomputed a code's item, an answer binds only to a question about that item's fact -
an answer to a stale question about another fact binds nothing (assess would not apply it either; the code stays held,
never excluded by it). Member answers lift no hold (session decision (e), L7-01) but the competition's: at read time a
member's answer that a code is not documented - read by the engine (its marker) or applied here - removes that code
from the competition (DECISIONS D249, 5a's Q2), so a rival with no other rival left loses its competing hold, and one
with a rival left keeps it, naming the rivals left (engine/assess.compete_without, the one implementation assess
reads too: DECISIONS D260); the answered code still counts for every other hold but the ADDON row, which counts no
code an answer binds, of either value, as assess counts none (DECISIONS D283, G1-03). The answers' passes are
engine/assess.answer_pass, the ONE implementation assess calls too (D283 items 1-2; ``review_view``'s passes): an
answer the engine reads (by its question's fingerprint) excludes its code and stands; an overlay-bound answer binds the
item its code presents in each pass - so a code whose ADDON row a pass moves is read again, and its answer binds only
the item it then presents (C7's correction) - and the competition leaves out the codes an overlay-bound "Not
documented" binds in that pass, the ADDON count every code an answer has bound, accumulated so the passes end. An
answer to the competing question binds nothing, at assess or here (D283, G1-01 option (c)): the competing hold is
settled by the reviewer's rejection (D270 DQ-3). "Cannot confirm" leaves the competition as it stands until a decision
(D260's effect): a
rival the reviewer rejects leaves the competition whatever it was answered (DECISIONS D270 DQ-3: an engine-answered
code counts whatever its decision, so its rejection takes it out of the competition alone), so the competition hold's
own sentence - "reject the code the documentation does not support; the one left is then ready for review" - is true.
An overlay-bound "Not documented" that assess read for the competition (DECISIONS D270 DQ-2: ``assessed_out``, read
from the stored record) takes its code out of the engine's own competition, and an overlay-bound answer of either value
assess read for the ADDON row leaves its code out of the engine's own ADDON count (D283 item 3: ``assessed_uncounted``,
the one derivation from the stored record), so read time reproduces what assess recorded; the reviewer's competition
and ADDON count take a code out only while its answer binds now, so a decision that unbinds it restores both.

**The seams of FINAL 8.1, at v2**: ``coding_of`` (event_coding@2's shape); ``_service`` (the session a code is matched
to, coverage.session_of over the FactSet; event_coding@2's codes record without one); the base, within, competing and
same-day holds (engine/combination); the modifier review (combination.modifier_review over the effective set, worded
from enumeration values: no word of the document); ``summary`` and ``_reinstatement_waits`` (the stored structured
records). Kept verbatim from review_view (tests/v2/test_overlay.py pins each AST): stored_from, _decided,
proposal_answers, answered_by_engine, counts, decidable, _find, _question, _reinstatement_clear, _sources,
_passage_sources, _example_passage and _held_blocker (seams wording.join and _session_label); _pfs_rows reads the field
prefix by a slice instead of str.startswith (FINAL-V2 5.7 measure 4).

**UNREADABLE** (FINAL 8.1, hazard 5: a quiet None never decides a new-path record): an event coding that cannot be read
(absent, another version - @1 included -, another shape), a stored record that cannot be read, or an inventory that
cannot be read (no FactSet given) recomputes nothing: every stored check (the endoscopic-family check included) and
question stands as stored, and the holds and checks the counted set moved are marked stale (so is a stored competing
hold whose rival a member's answer, or a rejection, took out of the competition, D249, D270: its release is not
recomputed; and an answer is bound to the stored questions, so one assess read for the competition stays bound).
readers.EventReader.unreadable adds UNREADABLE_BLOCKER - nothing is approved or exported until the code is assessed
again - for an event coding that cannot be read (every v1 row), and, while a reviewer has reinstated a code, for
anything the reinstatement's holds and reviewed coverage are re-run from (a reinstatement can add a hold). A rejection
alone is not blocked on an inventory that cannot be read: a rejection only releases or swaps combination holds, so the
stale stored holds it leaves are the fail-closed reading - and the one hold it can add, the ADDON row of an add-on whose
last primary it rejects (DECISIONS D268), holds that add-on here, stale, never approvable alone
(``_addon_unrecomputed``, from the codes alone).

**reviewed_completeness** (FINAL-V2 6.5): the documented-event coverage as the review leaves it - engine/coverage's
reconcile and completeness over the FactSet with the reinstated codes counted (``counted_codes``) and the procedure day
of the counted set (combination.procedure_day) - with the assessment's own open questions, provider state, conflicts
and unverified attributes (``assessment_counts``; a completeness whose event coding is not of READ_CODINGS - a v1
row's - is refused before anything is read, UnreadableCoding): the structured counts the stored completeness records
(this step's request R2), else derived without reading a sentence - the conflicts are the stored completeness's own
count, the unverified attributes assess's count over the engine's own counted codes (their evaluations made again), and
the open questions and the provider state the one pair under which coverage.completeness over the engine's own counted
set reproduces the stored completeness exactly. A record nothing reproduces is unreadable (fail-closed). Step 5a's
completeness records only the conflicts, so a reinstatement is re-run, never blocked, on what it records. A session not
listed is named by ``session_label``, the ONE label (DECISIONS D246): the renderer passes it to assess, so read time
reproduces the reason assess wrote.

**What it never does**: read SourceRevision.text or any text, parse an EventInventory, parse check prose, import a
retired v1 module (FINAL-V2 5.0, 5.7 measure 4: WordsNeverDecide scans this file), call a function of the legacy reader,
choose a modifier, or read a participant. Its views are review_view's own dataclasses (Stored, Decided, View): their
generated methods are not the legacy reader's code, and every consumer reads one View shape whichever reader made it.
"""
from __future__ import annotations

import datetime
import functools
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from types import MappingProxyType, SimpleNamespace
from typing import Any, Optional, cast

from studio.code_shapes import UNAVAILABLE_ANSWERS, _field, service_answers  # R-2: review_view's own objects
from studio.interpretation import ENGINE_VERSION_V2, ENGINE_VERSION_V3, wording
from studio.interpretation.contract.types import Attribute, Kind, Landmark, Reason, Result, SessionKind
from studio.interpretation.engine import assess as engine_assess
from studio.interpretation.engine import catalogue, combination, coverage, evaluate
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import questions as engine_questions
from studio.interpretation.engine.types import Evaluation, FactSet, HeldFact, Id, IdFamily, ItemKind, Span
from studio.reference.store import PFS
from studio.types import CodeReference, ReferenceSourceInfo, to_jsonable
from studio.validation import checks, questions
# FINAL 8.1: the overlay's rows and views are review_view's own dataclasses - only these three names, whose methods are
# dataclass-generated (co_filename '<string>', never in the sentinel's deny set): every consumer reads one View shape.
# Re-exported by name (readers.py reads overlay.Decided and overlay.Stored).
from studio.validation.review_view import Decided as Decided, Stored as Stored, View as View

# review_view's constants, copied (tests/v2/test_overlay.py pins each equal to its original)
APPROVE, REJECT, REINSTATE, REVOKE, CONFIRM = 'approve', 'reject', 'reinstate', 'revoke', 'confirm'
SELECTED, EXCLUDED, ALTERNATIVE = 'selected', 'excluded', 'alternative'
READY, NEEDS_CLARIFICATION, STATUS_EXCLUDED = 'ready', 'needs_clarification', 'excluded'
BASE_CHECK, BASE_FACT = 'services.base_included', 'base_included'
ENDOSCOPIC_CHECK = 'pfs.endoscopic_base'
REINSTATEMENT_CHECK = 'review.reinstatement'
PRESENCE_CHECK = 'pfs.presence'
DATE_CHECK = wording.PROPOSAL_DATE_CHECK.id
SAME_DAY_EM_GATE = 'em.same_day_if_reinstated'
SAME_DAY_PROCEDURE = 'review.same_day_em'
SEPARATE_EM_FACT = 'separate_em'
DETAIL_UNAVAILABLE = 'detail_unavailable'
ANSWER_WORDS = {'not_documented': 'not documented', 'cannot_confirm': 'cannot be confirmed'}
MODIFIER_REVIEW = 'distinct_lesion'
COMPETING_CHECK, COMPETING_FACT = 'proposals.competing', 'competing_codes'  # v1 combination's (pinned equal)
DATE_WAIT = 'the date of service is not established for this encounter.'
DOCUMENTATION_FACT = 'documentation'
DOCUMENTATION_QUESTION = 'Complete the documentation this reinstated code needs before it can be approved.'
# checks.py's constants the copies read, copied (pinned equal): the new package names checks.py only by FINAL 7.1's names
CLAIMS_EXAMPLE_CODES = frozenset({'45380', '45385'})
CLAIMS_EXAMPLE_PASSAGE = 'item-13-example'
CLAIMS_EXAMPLE_TOPIC = 'claims.multiple_endoscopy'
# checks.DISTINCT_LESION_NOT_CHECKED (copied, pinned equal): what the modifier review says it does not check
DISTINCT_LESION_NOT_CHECKED = ('NCCI procedure-to-procedure edits', 'payer modifier policy')

# The event_coding version the writer writes now (engine/coverage.CODING_VERSION: cpt-studio-events@3 since AMENDMENT-2's
# labels, 8.1), and every version this reader reads (AMENDMENT-2 8.1 [R:replay-R4]: a reader of a stored row accepts both
# design v2 families - an @2 record, stored before AMENDMENT-2, is read as stored, the engine running over it at read time
# as over an @3 one, and a record it does not reproduce is refused, fail-closed); any other version is unreadable.
CODING_VERSION = coverage.CODING_VERSION
READ_CODINGS = (ENGINE_VERSION_V2, ENGINE_VERSION_V3)
# FINAL 8.1: the readiness blocker of a new-path assessment whose record of the documented events cannot be read.
UNREADABLE_BLOCKER = ("This assessment's record of the documented events could not be read; it cannot be approved or "
                      'exported until it is assessed again.')
# The coverage reason of a reviewed coverage that could not be re-run (readers.EventReader.reviewed_completeness): the
# coverage stands as the assessment recorded it, without the reinstated codes, and readiness adds UNREADABLE_BLOCKER
# (readers.EventReader.unreadable), so the block it states is enforced. A clause, as every completeness reason is.
UNREADABLE_COVERAGE_REASON = ("this assessment's record of the documented events could not be read, so the coverage "
                              'shown does not count the reinstated codes; it cannot be approved or exported until it is '
                              'assessed again')
# The reinstatement wait the engine records for an unknown date of service: the encounter's own date question asks it
# of every code, so it is never asked of a reinstated code again (review_view's DATE_WAIT rule).
DATE_WAIT_FACT = 'service_date'
# The stored record's own version (support['event_reading']): the engine that wrote it - RECORD_VERSION, what the renderer
# writes now (AMENDMENT-2 8.1: @3), and READ_RECORDS, every version read (both design v2 families, as READ_CODINGS).
RECORD_VERSION = ENGINE_VERSION_V3
READ_RECORDS = (ENGINE_VERSION_V2, ENGINE_VERSION_V3)
# The structured counts reviewed_completeness reads of the stored completeness (FINAL-V2 6.5; this step's request R2):
# the assessment's own open questions, unverified attributes and provider state, never parsed from its sentences.
COUNTS = ('open_questions', 'unverified', 'provider_ok', 'conflicts')
_PFS_PREFIX = 'pfs.'
# studio.types.to_jsonable is untyped (a legacy helper): this module's own code calls it through this typed name (the
# verbatim copies call it by its own name, as review_view does)
_jsonable: Callable[[object], Any] = to_jsonable
SETTING_FACT = 'setting'  # the member-context item whose sentence names the patient status too when both are missing
# The member values the rules read (D3: never the document; engine/derive.py's member facts) and the origin a member's
# value is recorded with (interpretation/dates.USER, pinned equal by test).
MEMBER_FACTS = ('setting', 'patient_status', 'billing_context')
_USER = 'user'
# The member answer that a detail of a code is not documented (engine/assess.Answer.NOT_DOCUMENTED, one of
# code_shapes.UNAVAILABLE_ANSWERS; pinned equal by test). At read time it removes the code it answers from the
# competition (DECISIONS D249, 5a's Q2): the remaining code's competing hold is released when no rival is left.
NOT_DOCUMENTED = 'not_documented'
# both answer values (engine/assess.Answer: not documented, cannot confirm; code_shapes.UNAVAILABLE_ANSWERS)
_ANSWER_VALUES = frozenset(answer.value for answer in engine_assess.Answer)
# How completeness names a session whose kind names no service (DECISIONS D246; wording.SESSION_SERVICES has no entry
# for these four kinds): a noun phrase in lower case that reads in completeness's list as the twelve services' labels do
# ("... not listed as unresolved: colonoscopy, moderate sedation"), never a profile's capitalised title inside the
# sentence. CPT Studio's own display words (tests/v2/test_overlay.py pins every kind's sentence, written out).
UNNAMED_SERVICE_LABELS: Mapping[SessionKind, str] = MappingProxyType({
    SessionKind.SEDATION: 'moderate sedation', SessionKind.EM_OTHER: 'visit in another setting',
    SessionKind.OTHER_GI: 'other GI service', SessionKind.NOT_GI: 'service outside the GI profiles'})
# ... and a session whose kind is not established (DECISIONS D246).
UNESTABLISHED_SERVICE_LABEL = 'service whose kind is not established'

# The messages whose sentence reads no document text (wording.MESSAGES' builders for them read codes, kinds and the
# family only - tests/v2/test_overlay.py proves each builds the same words over any text): the only items read time
# words afresh. SERVICE_DATE only when it quotes no statement - and only for the encounter's renderer: its item is the
# encounter's own question, which read time asks of no code (review_view).
# DECISIONS D284 (build list B7, G3-15): the ADDON row's own message, worded from the codes alone (the add-on and its
# primaries: engine/assess.primaries), so an ADDON hold read time recomputes is worded and listed ``recomputed``, never
# ``stale``.
TEXT_FREE = frozenset({engine_questions.MessageId.BASE_INCLUDED, engine_questions.MessageId.BASE_EXPLAINED,
                       engine_questions.MessageId.BASE_WITHIN, engine_questions.MessageId.COMPETING,
                       engine_questions.MessageId.SEPARATE_EM, engine_questions.MessageId.SETTING,
                       engine_questions.MessageId.PATIENT_STATUS, engine_questions.MessageId.SERVICE_DATE,
                       engine_questions.MessageId.ADDON})
# The ADDON row of engine/assess (4.3's code-specific row "43273, 91013, 99153, 99417 | its primary counted"), which
# read time applies as assess does (DECISIONS D268): its hold's cause, and the id a view's ``recomputed`` and ``stale``
# name it by - its own cause, since v1 had no add-on rule and so no v1 check id names it (operator data: the consumers
# print the ids only in the operator's report and read nothing else of them but whether a list is empty).
ADDON_CAUSE = engine_assess.ADDON_CAUSE
ADDON_CHECK = engine_assess.ADDON_CAUSE
# The check ids a recomputed hold is named by in a view's ``recomputed`` and ``stale`` (v1's, which the consumers read):
# base and base-within, competing, and the same-day rule; and the ADDON row's own (ADDON_CHECK).
_RULE_IDS = {combination.BASE_CAUSE: BASE_CHECK, combination.WITHIN_CAUSE: BASE_CHECK,
             combination.COMPETING_CAUSE: COMPETING_CHECK, combination.SAME_DAY_CAUSE: SAME_DAY_EM_GATE,
             ADDON_CAUSE: ADDON_CHECK}
# The holds read time recomputes across codes, whose stored form is never carried as one read time does not recompute -
# ONE rule for every cause read time recomputes (DECISIONS D283, G3-32 option (b); build list B20): a stored base,
# base-within, competing, same-day or ADDON hold that the engine's own counted set does not give is a record that is not
# reproduced (RecordMismatch), never a hold carried beside the recomputed ones - a carried hold is one no decision can
# release, and it would hide an assess/read-time disagreement from the seam check (D252). Every cause _RULE_IDS names.
_RECOMPUTED = frozenset(_RULE_IDS)
# The member answers' record a stored completeness carries (engine/assess's member_answers: each answer it was given and
# did not apply, with why) and the reason it gives an answer to a fact the review overlay applies (engine/assess
# Unbound.OVERLAY_READ): the answers ``assessed_out`` reads.
_OVERLAY_READ = engine_assess.Unbound.OVERLAY_READ.value


class UnreadableCoding(ValueError):
    """completeness['event_coding'] is absent, of another version, or not in the shape this release reads."""


class UnreadableRecord(ValueError):
    """A stored proposal's v2 record (module docstring) is absent or not in the shape this release reads."""


# --- the versioned reader of event_coding@2 (FINAL-V2 6.5; step 4b's record) ------------------------------------------

_SESSION_IDS = ('event', 'part_of', 'possibly_part_of')
_SESSION_FLAGS = ('unresolved', 'done', 'incomplete')
_SESSION_LISTS = ('examinations', 'possible', 'events')
_ENTRY_KEYS = frozenset({'event', 'kind', 'lesion', 'unlisted'})
_CODE_KEYS = frozenset({'session', 'events', 'lesions'})
_LESION_KEYS = frozenset({'places', 'multiplicity', 'distinct_from', 'same_as'})


def _is_id(value: object, letter: str = '') -> bool:
    if not isinstance(value, str):
        return False
    try:
        found = Id.parse(value)
    except ValueError:
        return False
    return not letter or found.family.value == letter


def _ids_of(value: object, letter: str) -> bool:
    return isinstance(value, list) and all(_is_id(item, letter) for item in value)


def _enum_value(value: object, enum: type[Enum]) -> bool:
    try:
        enum(value)
    except ValueError:
        return False
    return True


def _entry_ok(entry: object) -> bool:
    if not isinstance(entry, Mapping) or set(entry) != _ENTRY_KEYS:
        return False
    event, unlisted = entry['event'], entry['unlisted']
    if event is None:
        if type(unlisted) is not int or unlisted < 0:
            return False
    elif not _is_id(event, 'E') or unlisted is not None:
        return False
    return ((entry['kind'] is None or _enum_value(entry['kind'], Kind))
            and (entry['lesion'] is None or _is_id(entry['lesion'], 'L')))


def read_coding(completeness: object) -> Mapping[str, Any]:
    """completeness['event_coding'] as this release reads it, checked: a version of READ_CODINGS (@2 or @3; AMENDMENT-2
    8.1), and every session, code and lesion record in event_coding's shape, the same at both versions
    (engine/coverage.event_coding: sessions keyed by session id with their
    kind, examination, part_of, flags, events and reportable and doubted entries {event, kind, lesion, unlisted}; codes
    {session, events, lesions}; lesions {places, multiplicity, distinct_from, same_as}). Raises UnreadableCoding; never
    returns a partial record."""
    coding = completeness.get('event_coding') if isinstance(completeness, Mapping) else None
    if not isinstance(coding, Mapping):
        raise UnreadableCoding('The assessment records no event coding.')
    if coding.get('version') not in READ_CODINGS:
        raise UnreadableCoding(f'This release reads event coding {" and ".join(READ_CODINGS)} only.')
    sessions, codes, lesions = coding.get('sessions'), coding.get('codes'), coding.get('lesions')
    if not (isinstance(sessions, Mapping) and isinstance(codes, Mapping) and isinstance(lesions, Mapping)):
        raise UnreadableCoding('The event coding has no sessions, codes or lesions.')
    for sid, session in sessions.items():
        if not (_is_id(sid, 'X') and isinstance(session, Mapping)
                and all(session.get(name) is None or _enum_value(session.get(name), SessionKind)
                        for name in ('family', 'kind'))
                and session.get('family') == session.get('kind')
                and all(session.get(name) is None or _is_id(session.get(name)) for name in _SESSION_IDS)
                and all(type(session.get(name)) is bool for name in _SESSION_FLAGS)
                and all(_ids_of(session.get(name), 'E') for name in _SESSION_LISTS)):
            raise UnreadableCoding('A session of the event coding is not in the shape this release reads.')
        for part in ('reportable', 'doubted'):
            entries = session.get(part)
            if not isinstance(entries, list) or not all(_entry_ok(entry) for entry in entries):
                raise UnreadableCoding("A session's events are not in the shape this release reads.")
    for key, entry in codes.items():
        if not (isinstance(key, str) and key and isinstance(entry, Mapping) and set(entry) == _CODE_KEYS
                and (entry['session'] is None or _is_id(entry['session'], 'X'))
                and _ids_of(entry['events'], 'E') and _ids_of(entry['lesions'], 'L')):
            raise UnreadableCoding('A code of the event coding is not in the shape this release reads.')
    for lid, lesion in lesions.items():
        if not (_is_id(lid, 'L') and isinstance(lesion, Mapping) and set(lesion) == _LESION_KEYS
                and isinstance(lesion['places'], list) and all(_enum_value(p, Landmark) for p in lesion['places'])
                and _ids_of(lesion['distinct_from'], 'L') and _ids_of(lesion['same_as'], 'L')):
            raise UnreadableCoding('A lesion of the event coding is not in the shape this release reads.')
    return coding


def coding_of(completeness: object) -> Optional[Mapping[str, Any]]:
    """read_coding, or None when the record cannot be read (the overlay then fails closed)."""
    try:
        return read_coding(completeness)
    except UnreadableCoding:
        return None


# --- the frozen inventory as the engine reads it (FINAL-V2 6.5; hand-off 2d:R8) ---------------------------------------

def reading(view: object, effective_date: object) -> FactSet:
    """The FactSet of the frozen settled inventory: ``view`` is store.textfree_v2's view of the row store.load_v2 read
    and checked (D188), ``effective_date`` the effective date of service the assessment was made with (None when
    unknown). engine/facts.effective, exactly as engine/assess.assess builds it, so assess and read time have identical
    inputs; never facts.factset (the triage's hand-off 2d:R8). Raises facts.FactSetError (a ValueError) for a view it
    cannot read whole."""
    return facts_.effective(view, effective_date)


def member_context(facts: object) -> engine_assess.MemberContext:
    """The member context an assessment was made with (engine/assess.MemberContext, D3): the setting, the patient
    status and the billing context its context records as entered by a member (engine/derive.py's member facts: a
    value with the user origin), '' where none is. The renderer's assess builds its MemberContext the same way (this
    step's request R1), so read time reads the values assess read."""
    out = {}
    for name in MEMBER_FACTS:
        fact = facts.get(name) if isinstance(facts, Mapping) else None
        value = fact.get('value') if isinstance(fact, Mapping) and fact.get('origin') == _USER else None
        out[name] = value if isinstance(value, str) else ''
    return engine_assess.MemberContext(**out)


# --- the stored v2 record of one proposal (module docstring; request R1) ----------------------------------------------

_HELD_KEYS = frozenset({'fact', 'attribute', 'subject', 'result', 'kind', 'cause', 'reason', 'spans', 'rank'})


def _span(value: object) -> Span:
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        raise UnreadableRecord('A stored span is a [start, end] pair.')
    try:
        return Span(value[0], value[1])
    except ValueError:
        raise UnreadableRecord('A stored span is a [start, end] pair of offsets.') from None


def _held_fact(value: object) -> HeldFact:
    """One stored held fact (engine/assess.jsonable's form of an engine HeldFact), read back. UnreadableRecord for
    anything else."""
    if not isinstance(value, Mapping) or set(value) != _HELD_KEYS:
        raise UnreadableRecord('A stored held fact is not in the shape this release reads.')
    try:
        if not isinstance(value['fact'], str) or not value['fact'] or not isinstance(value['cause'], str):
            raise ValueError('fact and cause')
        rank = value['rank']
        if rank is not None and type(rank) is not int:
            raise ValueError('rank')
        spans = value['spans']
        if not isinstance(spans, list):
            raise ValueError('spans')
        return HeldFact(fact=value['fact'],
                        attribute=None if value['attribute'] is None else Attribute(value['attribute']),
                        subject=None if value['subject'] is None else Id.parse(value['subject']),
                        result=None if value['result'] is None else Result(value['result']),
                        kind=ItemKind(value['kind']), cause=value['cause'],
                        reason=None if value['reason'] is None else Reason(value['reason']),
                        spans=tuple(_span(item) for item in spans), rank=rank)
    except (ValueError, TypeError):
        raise UnreadableRecord('A stored held fact is not in the shape this release reads.') from None


@dataclass(frozen=True)
class Record:
    """One stored v2 proposal as the read-time engine reads it: its key and code, its family (catalogue.family_for_code,
    as assess routes it), R1's kept spans, their runs (None: C-10's fail-closed reading), whether it is a procedure
    (None when the record does not say: the stored retrieval's PFS row decides, as assess's lookup did), its origin and,
    for a code the engine evaluated, its stored held facts (FINAL-V2 4.8), None for an exclusion."""
    key: str
    code: str
    family: SessionKind
    kept: tuple[Span, ...]
    kept_words: Optional[tuple[Span, ...]]
    procedural: Optional[bool]
    origin: str
    held: Optional[tuple[HeldFact, ...]]


def read_record(p: Stored) -> Record:
    """The stored v2 record of ``p`` (module docstring), checked. UnreadableRecord when it is not one: another engine's
    support, kept spans that are not offsets, a held fact or a run of the wrong shape."""
    support = p.support if isinstance(p.support, Mapping) else {}
    if support.get('event_reading') not in READ_RECORDS:
        raise UnreadableRecord(f'The proposal was not recorded by {" or ".join(READ_RECORDS)}.')
    kept: list[Span] = []
    for item in p.evidence or ():
        start, end = (item.get('start'), item.get('end')) if isinstance(item, Mapping) else (None, None)
        if type(start) is not int or type(end) is not int or not 0 <= start < end:
            raise UnreadableRecord("A proposal's kept evidence is not a list of revision offsets.")
        if Span(start, end) not in kept:
            kept.append(Span(start, end))
    runs = support.get('kept_words')
    if runs is not None and not isinstance(runs, list):
        raise UnreadableRecord("A proposal's kept runs are not [start, end] pairs.")
    procedural = support.get('procedural')
    if procedural is not None and type(procedural) is not bool:
        raise UnreadableRecord("A proposal's procedural mark is not true or false.")
    origin = support.get('origin', '')
    held = support.get('held_facts')
    if held is not None and not isinstance(held, list):
        raise UnreadableRecord("A proposal's held facts are not a list.")
    if p.bucket == SELECTED and held is None:
        raise UnreadableRecord('A selected proposal records its held facts (FINAL-V2 4.8).')
    return Record(key=p.key, code=p.code, family=catalogue.family_for_code(p.code), kept=tuple(kept),
                  kept_words=None if runs is None else tuple(_span(item) for item in runs),
                  procedural=procedural, origin=origin if isinstance(origin, str) else '',
                  held=None if held is None else tuple(_held_fact(item) for item in held))


# --- copied verbatim from review_view (FINAL 8.1; pinned by AST) ------------------------------------------------------
# mypy --strict: the copies keep review_view's signatures and bodies, which the AST pins compare (annotations are part
# of the tree), so each line mypy would refuse for an annotation the original lacks, or for a call into an untyped
# legacy helper (studio.types.to_jsonable, code_shapes._field), carries a type: ignore naming that one error code.

def stored_from(proposal, clarifications=None) -> Stored:  # type: ignore[no-untyped-def]
    """A Stored row from a Proposal (or any object with its fields) and that proposal's Clarification rows (objects with
    scope, family, fact, question, reason, state and pk), or from an engine ProposalAssessment, whose ClarificationSpecs
    are its own and all open (as persisting them leaves them)."""
    if clarifications is None:
        own = getattr(proposal, 'clarifications', ())
        clarifications = own if isinstance(own, (list, tuple)) else ()
    questions, holds = [], []
    for row in clarifications:
        if getattr(row, 'scope', '') == 'proposal':
            holds.append(row.fact)
        if getattr(row, 'state', 'open') == 'open':
            questions.append({'id': str(getattr(row, 'pk', '') or ''), 'scope': row.scope, 'family': row.family,
                              'fact': row.fact, 'question': row.question, 'reason': row.reason})
    return Stored(key=proposal.key, code=proposal.code, family=proposal.family, bucket=proposal.bucket,
                  status=proposal.status, reinstatable=bool(proposal.reinstatable), units=proposal.units,
                  checks=tuple(to_jsonable(list(proposal.checks or ()))),  # type: ignore[no-untyped-call]
                  holds=tuple(holds), questions=tuple(questions),
                  support=to_jsonable(dict(proposal.support or {})),  # type: ignore[no-untyped-call]
                  evidence=tuple(to_jsonable(list(proposal.evidence or ()))),  # type: ignore[no-untyped-call]
                  id=str(getattr(proposal, 'pk', '') or ''))


def _decided(value) -> Decided:  # type: ignore[no-untyped-def]
    if isinstance(value, Decided):
        return value
    if isinstance(value, str):
        return Decided(value)
    return Decided(str(getattr(value, 'action', '')), tuple(getattr(value, 'modifiers', None) or ()))


def proposal_answers(answers) -> dict:  # type: ignore[no-untyped-def, type-arg]
    """{(code, family, fact): value} of the current member answers given for a code (P5 binds an answer to the code,
    family and fact it was asked of, never to a key) that leave its detail unavailable."""
    out = {}  # type: ignore[var-annotated]
    for answer in answers or ():
        code, value = _field(answer, 'code') or '', _field(answer, 'value') or ''  # type: ignore[no-untyped-call]
        if code and value in UNAVAILABLE_ANSWERS:
            out.setdefault((str(code), str(_field(answer, 'family') or ''),  # type: ignore[no-untyped-call]
                            str(_field(answer, 'fact') or '')), value)  # type: ignore[no-untyped-call]
    return out


def answered_by_engine(p: Stored) -> tuple[str, str]:
    """(fact, value) of the member answer the engine excluded ``p`` by (engine.answered_away: completion repair
    2026-11-06, the answers read as an input), ('', '') for any other code."""
    if not questions.answered_away(p):
        return '', ''
    marker = (p.support or {}).get(questions.ANSWERED_SUPPORT) or {}
    return str(marker.get('fact') or ''), str(marker.get('value') or '')


def counts(p: Stored, decided: Optional[Decided]) -> bool:
    """Whether ``p`` is decided like a code that is billed, before any member answer: a selected code not rejected, or
    an excluded, reinstatable code with a current reinstatement (or the approval that rests on one). A code the engine
    excluded by a member's answer counts as the selected code it was (session decision (e): its presence still holds
    every code it held), exactly as one this overlay leaves detail_unavailable does."""
    action = decided.action if decided is not None else ''
    if answered_by_engine(p)[0]:
        return True
    if p.bucket == SELECTED:
        return action != REJECT
    return p.bucket == EXCLUDED and p.reinstatable and action in (REINSTATE, APPROVE)


def decidable(p: Stored) -> bool:
    """review.decidable: selected, or excluded and reinstatable."""
    return p.bucket == SELECTED or (p.bucket == EXCLUDED and p.reinstatable)


def _find(items, check_id) -> Optional[int]:  # type: ignore[no-untyped-def]
    return next((i for i, item in enumerate(items) if item.get('id') == check_id), None)


def _question(spec, *, ident='') -> dict:  # type: ignore[no-untyped-def, type-arg]
    return {'id': ident, 'scope': spec.scope, 'family': spec.family, 'fact': spec.fact, 'question': spec.question,
            'reason': spec.reason}


def _reinstatement_clear(p: Stored) -> bool:
    """Its stored review.reinstatement check passes (review._reinstatement_clear: fail-closed, no check is no pass)."""
    return any(c.get('id') == REINSTATEMENT_CHECK and c.get('status') == 'pass' for c in p.checks)


def _pfs_rows(retrieval: Any) -> dict[str, Optional[dict[str, Any]]]:
    """code -> the PFS row the assessment's own retrieval trace recorded for it (each 'pfs.<field>' fact, with its
    source key), None for a traced code with no PFS row. A failed retrieval traces no code. (review_view's, with the
    field's prefix read by a slice, not str.startswith: FINAL-V2 5.7 measure 4.)"""
    rows: dict[str, Optional[dict[str, Any]]] = {}
    for entry in retrieval or ():
        if not isinstance(entry, Mapping) or not isinstance(entry.get('code'), str) or not entry.get('code'):
            continue
        row: dict[str, Any] = {}
        for fact in entry.get('facts') or ():
            field = fact.get('field') if isinstance(fact, Mapping) else None
            if isinstance(field, str) and field[:len(_PFS_PREFIX)] == _PFS_PREFIX:
                row[field[len(_PFS_PREFIX):]] = fact.get('value')
                row['source_key'] = fact.get('source_key')
        rows[entry['code']] = row or None
    return rows


def _sources(reference_sources) -> tuple:  # type: ignore[no-untyped-def, type-arg]
    fields = ReferenceSourceInfo.__dataclass_fields__
    return tuple(ReferenceSourceInfo(**{name: str(entry.get(name) or '') for name in fields})
                 for entry in reference_sources or () if isinstance(entry, Mapping) and entry.get('key')
                 and entry.get('kind'))


@functools.lru_cache(maxsize=1)
def _passage_sources() -> dict:  # type: ignore[type-arg]
    """(source key, release) -> (title, effective start) of each CMS passage source this release ships
    (studio/reference/data): the citation names the source and the date its window opens."""
    from studio.reference import passages  # local import: only a modifier review's citation reads it
    sources = {}
    for path in passages.bundled_files():
        try:
            source = passages.read_data_file(path).source
        except Exception:  # noqa: BLE001 - a file this release cannot read names no title, and its citation shows none
            continue
        sources[(source['key'], source['release'])] = (source['title'], str(source.get('effective_start') or ''))
    return sources


def _example_passage(codes: Sequence[str], retrieval) -> Optional[Mapping]:  # type: ignore[no-untyped-def, type-arg]
    """The claims-manual example passage the assessment's retrieval recorded for one of ``codes``, or None."""
    for entry in retrieval or ():
        if not isinstance(entry, Mapping) or entry.get('code') not in codes:
            continue
        for passage in entry.get('passages') or ():
            if (isinstance(passage, Mapping) and passage.get('passage_key') == CLAIMS_EXAMPLE_PASSAGE
                    and passage.get('topic') == CLAIMS_EXAMPLE_TOPIC and passage.get('release')):
                return passage
    return None


def _held_blocker(p: Stored, held, counted: Sequence[Stored], service) -> str:  # type: ignore[no-untyped-def]
    """The readiness blocker of an approval a base rule now holds (D14); ``held``: _bases's (rule, codes) over the
    ``counted`` set, which names the codes that hold it."""
    rule, held = held if held else ('included', ())
    held = tuple(held or ())
    if rule == 'within':
        return (f'{p.code} was approved, but its examination is the endoscopic portion of the endoscopic ultrasound '
                'documented with it and is normally included in it; revoke the approval')
    if held and all(other[:1].isdigit() for other in held):
        by_code = {other.code: other for other in counted}
        reinstated = all(by_code.get(code) is not None and by_code[code].bucket == EXCLUDED for code in held)
        one = len(held) == 1
        verb = ('was reinstated' if one else 'were reinstated') if reinstated else ('is selected' if one else
                                                                                     'are selected')
        return (f'{p.code} was approved, but {wording.join(list(held))} {verb}: its diagnostic examination is normally '
                f'included in {"that intervention" if one else "those interventions"}; revoke one of the decisions')
    name = _session_label(service) if service is not None else 'service'
    return (f'{p.code} was approved, but the documented {name} includes {wording.join(list(held))}, which this '
            'diagnostic code does not account for; revoke the approval')


# --- the seams (FINAL 8.1 at v2): each reads what the engine stored, or recomputes it with the engine ----------------

def _session(coding: Optional[Mapping[str, Any]], session_id: object) -> Optional[dict[str, Any]]:
    """The session ``session_id`` of ``coding`` with its id, or None."""
    record = (coding.get('sessions') or {}).get(session_id) if coding is not None and session_id else None
    return {**record, 'id': session_id} if isinstance(record, Mapping) else None


def _family_session(coding: Mapping[str, Any], family: SessionKind) -> Optional[dict[str, Any]]:
    """The session of ``family`` the coding documents - one done when there is one (coverage.session_of's rule) - or
    None."""
    found = [sid for sid, record in (coding.get('sessions') or {}).items() if record.get('kind') == family.value]
    done = [sid for sid in found if coding['sessions'][sid].get('done')]
    return _session(coding, (done or found or [''])[0])


def _session_label(session: object) -> str:
    """A session's label: the service its kind names (wording.service_phrase over the session kind; event_coding@2
    carries no words, P9)."""
    kind = session.get('kind') if isinstance(session, Mapping) else None
    return wording.service_phrase(SessionKind(kind)) if isinstance(kind, str) and _enum_value(kind, SessionKind) \
        else 'service'


def _service(p: Stored, coding: Optional[Mapping[str, Any]], decided: Optional[Decided]) -> Optional[dict[str, Any]]:
    """The session ``p`` was matched to (event_coding@2's record of its code), or - for a code a reviewer reinstated
    whose own record names none - the session of its family the coding documents; None otherwise, and with no
    coding."""
    if coding is None:
        return None
    session_id = ((coding.get('codes') or {}).get(p.key) or {}).get('session')
    if session_id:
        return _session(coding, session_id)
    if p.bucket == EXCLUDED and decided is not None and decided.action in (REINSTATE, APPROVE):
        try:
            return _family_session(coding, catalogue.family_for_code(p.code))
        except ValueError:
            return None
    return None


def _reinstatement_waits(p: Stored) -> tuple[dict[str, Any], ...]:
    """The questions an excluded code's approval waits for once it is reinstated, from the engine's STRUCTURED record
    (support['reinstatement_waits']: [{fact, question}] - never the check's prose), each as a dict {id: '', scope,
    family, fact, question, reason}; () when its stored review.reinstatement check passes. The date of service's wait is
    the encounter's own question and is not asked again (review_view's DATE_WAIT rule). A check that withholds approval
    with no structured wait recorded - or a record this release cannot read - asks for the documentation itself
    (DOCUMENTATION_FACT): fail-closed, the code is asked and held, never shown as ready."""
    if _reinstatement_clear(p):
        return ()
    check = next((c for c in p.checks if c.get('id') == REINSTATEMENT_CHECK), None)
    detail = str((check or {}).get('detail') or '')
    reason = detail or 'Approval after reinstatement is not established for this code.'
    stored = (p.support or {}).get('reinstatement_waits')
    waits = stored if isinstance(stored, (list, tuple)) else ()
    readable = all(isinstance(wait, Mapping) and isinstance(wait.get('fact'), str) and wait['fact']
                   and isinstance(wait.get('question'), str) and wait['question'] for wait in waits)
    asked: list[tuple[str, str]] = []
    dated = False
    for wait in (waits if readable else ()):
        if wait['fact'] == DATE_WAIT_FACT:
            dated = True
        elif (wait['fact'], wait['question']) not in asked:
            asked.append((wait['fact'], wait['question']))
    if not asked and not dated:
        asked.append((DOCUMENTATION_FACT, DOCUMENTATION_QUESTION))
    return tuple({'id': '', 'scope': 'proposal', 'family': p.family, 'fact': fact, 'question': question,
                  'reason': reason} for fact, question in asked)


def summary(p: Stored) -> str:
    """The stored sentence of CPT Studio's own reading of the documented events ``p`` was matched to (support['summary'],
    the engine's renderer's); '' when none was stored. Nothing is recomputed."""
    value = (p.support or {}).get('summary')
    return value if isinstance(value, str) else ''


# --- the read-time engine (FINAL-V2 4.8 "Read time"; step 4d's request R3) --------------------------------------------

@dataclass(frozen=True)
class Live:
    """What the read-time engine gives one code of the reviewer's counted set: its live held facts (FINAL-V2 4.8:
    ranked), its live item (the first on its binding) and the item it was stored with; ``holds`` and ``stored_holds``
    its cross-code holds over the reviewer's counted set and over the engine's own - the combination's, then the ADDON
    row's (DECISIONS D268: engine/assess's ADDON row, which counts no code a member's answer excluded); ``member`` the
    combination member it was read as; ``worded`` the live item in CPT Studio's words when it changed - another item
    (``moved``), or the same item whose words the combination's moved records name (``renamed``) - and read time can
    word it (None otherwise)."""
    held: tuple[HeldFact, ...]
    item: Optional[engine_questions.Item]
    stored_item: Optional[engine_questions.Item]
    holds: tuple[HeldFact, ...]
    stored_holds: tuple[HeldFact, ...]
    member: combination.Member
    worded: Optional[wording.Worded]

    @property
    def moved(self) -> bool:
        """The live item is not the one the assessment presented (FINAL-V2 4.8: a released item gave way, or an added
        hold outranks it)."""
        return self.item != self.stored_item

    @property
    def added(self) -> tuple[HeldFact, ...]:
        return tuple(held for held in self.holds if held not in self.stored_holds)

    @property
    def released(self) -> tuple[HeldFact, ...]:
        return tuple(held for held in self.stored_holds if held not in self.holds)


@dataclass(frozen=True)
class Recount:
    """The read-time engine over the reviewer's counted set (``recount``): each counted code's Live, ``joined`` the
    combination over the counted set and ``stored_joined`` over the engine's own, the counted set's members and the
    evaluations of every code it read."""
    live: Mapping[str, Live]
    joined: combination.Combination
    stored_joined: combination.Combination
    members: Mapping[str, combination.Member]
    evaluations: Mapping[str, Evaluation]


class RecordMismatch(ValueError):
    """The engine's own counted set, recomputed over the persisted inventory, does not reproduce a stored record: the
    record or the inventory is not what the assessment was made from, and nothing is recomputed from it."""


def _procedural(record: Record, evaluation: Evaluation, pfs: Mapping[str, Optional[dict[str, Any]]]) -> bool:
    """Whether the code is a procedure, as assess decided it: the stored mark, else engine/assess.procedural over the
    stored retrieval's PFS row (no row counts, fail-closed, as assess's lookup with none)."""
    if record.procedural is not None:
        return record.procedural
    # engine/assess.procedural reads a selection's family and evaluation only: this record stands in for one
    selection = cast(Any, SimpleNamespace(family=record.family, evaluation=evaluation))
    return engine_assess.procedural(selection, pfs.get(record.code))


def counted_codes(proposals: Iterable[Any], reinstated_keys: Collection[str], R: FactSet) -> list[coverage.Counted]:
    """coverage.Counted of every code the review counts - the selected ones, the ones the engine excluded by a member's
    answer (the engine counted them: assess's reconciliation reads its selections before the answers), and the
    reinstated ones (``reinstated_keys``) - each with its supporting and read events as the per-code rule decides them
    over ``R`` from the code's own stored exact evidence: the evaluation the engine made, made again by the engine
    (engine/evaluate.decide over the persisted inventory read with facts.effective; pure). ``proposals``: Stored rows
    or Proposals. Raises UnreadableRecord for a record this release cannot read."""
    out = []
    for proposal in proposals:
        reinstated = proposal.key in reinstated_keys
        if not (proposal.bucket == SELECTED or questions.answered_away(proposal) or reinstated):
            continue
        record = read_record(proposal if isinstance(proposal, Stored) else stored_from(proposal, ()))
        evaluation = evaluate.decide(record.code, record.kept, R, kept_words=record.kept_words)
        out.append(coverage.Counted(key=record.key, code=record.code, family=record.family,
                                    supporting=evaluation.supporting, read=_read_events(evaluation)))
    return out


def _read_events(evaluation: Evaluation) -> tuple[Id, ...]:
    """The events a code's decision read (coverage.Counted.read, as engine/assess._counted_of records it): its bound
    candidates, then its held facts' events, each once."""
    read = list(evaluation.bindings.values())
    read += [held.subject for held in evaluation.held_facts
             if held.subject is not None and held.subject.family is IdFamily.EVENT]
    return tuple(dict.fromkeys(read))


def _members(records: Sequence[Record], keys: Iterable[str], R: FactSet, sessions_: Mapping[Id, coverage.Session],
             evaluations: Mapping[str, Evaluation],
             pfs: Mapping[str, Optional[dict[str, Any]]]) -> dict[str, combination.Member]:
    """The combination members of ``keys`` (assess's Members: the routed family, the matched session -
    coverage.session_of over the FactSet -, E*, the origin, procedural, supported when E* is not empty and the per-code
    rule holds nothing), in the stored rows' order."""
    wanted = set(keys)
    out: dict[str, combination.Member] = {}
    for record in records:
        if record.key not in wanted:
            continue
        evaluation = evaluations[record.key]
        supporting = evaluation.supporting
        out[record.key] = combination.Member(
            key=record.key, code=record.code, family=record.family,
            session=coverage.session_of(sessions_, record.family, supporting), supporting=supporting,
            origin=record.origin, procedural=_procedural(record, evaluation, pfs),
            supported=bool(supporting and not evaluation.held_facts))
    return out


def _without(held: Sequence[HeldFact], *taken: Iterable[HeldFact]) -> list[HeldFact]:
    out = list(held)
    for group in taken:
        for found in group:
            if found in out:
                out.remove(found)
    return out


def _unchecked(frozen: bool, taken: bool) -> frozenset[str]:
    """The causes of a stored code's holds that the reproduction check leaves out (``recount``), DECISIONS D283's
    exemptions (G1-02, with C8's correction; build list B16): for a code the engine excluded by a member's answer
    (``frozen``) its competing and ADDON holds - engine/assess never assesses it again (_bind_in_passes, read_again), so
    its record keeps both as its answer found them and the later passes need not reproduce them; for a code assess took
    out of the competition by an overlay-bound "Not documented" (``taken``, D270 DQ-2) its competing hold alone - it
    competes with nothing in the engine's own competition, and engine/assess assesses it again whenever the answers move
    its ADDON row (read_again), so its record's ADDON hold is the last pass's and is checked; none for any other code."""
    if frozen:
        return frozenset({combination.COMPETING_CAUSE, ADDON_CAUSE})
    return frozenset({combination.COMPETING_CAUSE}) if taken else frozenset()


def _stored_item_facts(p: Stored) -> tuple[str, ...]:
    """The fact of the item ``p`` was stored with: the renderer's record of it (support['item']['fact'],
    jobs._render_code) when there is one, else the facts of its open proposal-scope questions (the item's question, as
    the renderer asks it); () for a code stored with no item."""
    support = p.support if isinstance(p.support, Mapping) else {}
    item = support.get('item')
    if isinstance(item, Mapping):
        fact = item.get('fact')
        return (fact,) if isinstance(fact, str) and fact else ()
    return tuple(str(q.get('fact') or '') for q in p.questions if q.get('scope') == 'proposal' and q.get('fact'))


def _assessed_reads(completeness: object, rows: Sequence[Stored]) -> tuple[tuple[str, str, str], ...]:
    """The ONE derivation, from the stored record alone, of the overlay-bound answers engine/assess read (DECISIONS D283
    item 3 and G3-17; D270 DQ-2): (answer id, the key of the selected code it binds, its value) for each answer the
    stored completeness's member answers record lists as given to assess and left to the overlay ('earlier', why
    read_by_the_review_overlay), bound by its code, family and fact to a selected code's stored item
    (``_stored_item_facts``) - never an answer to the competing question (COMPETING_FACT), which engine/assess.
    overlay_bound never reads (D283, G1-01). engine/assess records an overlay-read answer so only while it binds the item
    its code presents in the last pass (an answer whose code's item moved is recorded no_longer_asked), so these are
    the answers its last pass bound. () for a record with no member answers, or one not in that shape. Pure."""
    record = completeness.get('member_answers') if isinstance(completeness, Mapping) else None
    entries = record.get('earlier') if isinstance(record, Mapping) else None
    if not isinstance(entries, list):
        return ()
    read: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
    for entry in entries:
        if (isinstance(entry, Mapping) and entry.get('why') == _OVERLAY_READ and entry.get('value') in _ANSWER_VALUES
                and all(isinstance(entry.get(name), str) and entry.get(name) for name in ('code', 'family', 'fact'))
                and entry.get('fact') != COMPETING_FACT):
            answer = entry.get('answer')
            read.setdefault((entry['code'], entry['family'], entry['fact']), []).append(
                (answer if isinstance(answer, str) else '', entry['value']))
    out: list[tuple[str, str, str]] = []
    for p in rows:
        if p.bucket != SELECTED:
            continue
        for fact in _stored_item_facts(p):
            out += [(answer, p.key, value) for answer, value in read.get((p.code, p.family, fact), ())]
    return tuple(out)


def assessed_out(completeness: object, rows: Sequence[Stored]) -> frozenset[str]:
    """The keys of the codes engine/assess took out of its competition by a member's "Not documented" it read for the
    competition (DECISIONS D270 DQ-2 option (b): an answer to a fact the review overlay applies, which assess reads as
    D260 reads an engine-bound one, never excluding the code): each answer of ``_assessed_reads`` (the one derivation)
    with the value not_documented - never an answer to the competing question (COMPETING_FACT), which
    engine/assess.overlay_bound never reads, so such a code stays in the engine's own competition and D249 binds the
    answer for the reviewer's alone (the integration's fix of the combination: refute-5c-r1 P2 = refute-5a-r1 P-2; 5a's
    question Q1 as built). Read from the stored record alone - never from the answers the review binds now - so the
    engine's own competition reproduces what assess recorded whatever the decisions now unbind (``recount``). Empty for
    a record with no member answers, or one not in that shape: the engine's own competition then keeps every code, and
    a record whose competition assess released is not reproduced (fail-closed). Pure."""
    return frozenset(key for _, key, value in _assessed_reads(completeness, rows) if value == NOT_DOCUMENTED)


def assessed_uncounted(completeness: object, rows: Sequence[Stored]) -> frozenset[str]:
    """The keys of the codes engine/assess left out of its ADDON count (DECISIONS D283 G1-03 and item 3; build list
    B16), derived from the stored record by this ONE function - every recount that reproduces a record reads it
    (``recount(..., uncounted=)``: _recount_or_none, readers.EventReader, the seam harness and the tests): every code an
    engine-read answer excluded (its marker, ``answered_by_engine``) and every selected code an overlay-bound answer of
    EITHER value binds (``_assessed_reads``: "Not documented" and "Cannot confirm" alike, G1-03) - so the engine's own
    ADDON row counts what assess counted, and an add-on whose every primary such an answer binds is held by its row at
    both halves (D268). Pure.

    Its limit, stated (this step's NOTES, question Q-UNCOUNTED): engine/assess accumulates the set over its passes, and
    its record names the overlay-bound answers of the LAST pass only; a code an overlay-bound answer bound in an earlier
    pass whose item a later pass moved is recorded no_longer_asked, so it is not named here. Only an add-on's item moves
    so (its ADDON row; a competing hold, rank 22, outranks only the member context, which no answer binds), and no
    add-on is the primary of an add-on in this catalogue (tests/v2/test_overlay pins that), so the derived set counts
    what assess counted; a record it ever failed to reproduce is a RecordMismatch - nothing recomputed, fail-closed."""
    engine = {p.key for p in rows if answered_by_engine(p)[0]}
    return frozenset(engine | {key for _, key, _ in _assessed_reads(completeness, rows)})


def assessed_answers(completeness: object, rows: Sequence[Stored]) -> frozenset[str]:
    """The ids of the overlay-bound member answers engine/assess READ (DECISIONS D283, G3-17 with RS-4's and C5's
    correction; build list B19), from the same derivation ``assessed_out`` and ``assessed_uncounted`` read
    (``_assessed_reads``), so they cannot drift: an answer that took a code out of its competition (a "Not documented",
    D270 DQ-2), and an answer of either value that left a PRIMARY out of the ADDON count - a code some add-on among the
    selected rows is reported with (engine/assess.primaries; G1-03). review._reads_a_withdrawn_answer holds readiness
    at STALE_ANSWER_BLOCKER while one of them no longer stands, until the recompute. An answer assess did not read moves
    nothing - one asked differently or no longer asked (never listed read_by_the_review_overlay), one to the competing
    question, or a "Cannot confirm" that binds no primary.

    r2 (DECISIONS D294, WORDS-F7): the add-ons whose primaries are read are every add-on assess passed - a selected one
    AND one its own answer excluded (``answered_by_engine``: assess counted it, and it presented the ADDON item the
    primary's answer made before its own answer bound) - so an answer assess read for the ADDON count is named whatever
    became of the add-on, and its withdrawal holds readiness until the recompute. Pure."""
    primary_codes = {code for p in rows if p.bucket == SELECTED or answered_by_engine(p)[0]
                     for code in engine_assess.primaries(p.code)}
    codes = {p.key: p.code for p in rows}
    return frozenset(answer for answer, key, value in _assessed_reads(completeness, rows)
                     if answer and (value == NOT_DOCUMENTED or codes.get(key) in primary_codes))


def _addon(record: Record, evaluation: Evaluation, counted: Collection[str]) -> tuple[HeldFact, ...]:
    """engine/assess's ADDON row of ``record`` over the codes it counts (``counted``): its one witness (engine/assess
    addon_hold, the function assess's row calls) when the code is an add-on with a supporting act none of whose
    primaries is counted, else nothing - with no supporting act SUPPORT already holds it, and assess's row adds nothing
    (engine/assess._addon_row's rule)."""
    if not evaluation.supporting:
        return ()
    found = engine_assess.addon_hold(record.code, counted, record.kept)
    return () if found is None else (found,)


def recount(rows: Sequence[Stored], counted_keys: Iterable[str], engine_keys: Iterable[str],
            coding: Mapping[str, Any], R: FactSet, *, retrieval: Any = (),
            member: Optional[engine_assess.MemberContext] = None, out_of_competition: Iterable[str] = (),
            answered: Iterable[str] = (), assessed: Iterable[str] = (), uncounted: Iterable[str] = ()) -> Recount:
    """The read-time engine (module docstring) over ``rows`` (one assessment's stored rows), the reviewer's counted set
    ``counted_keys`` and the engine's own ``engine_keys`` (its selected codes and those it excluded by a member's
    answer): the per-code rule run again for each (engine/evaluate.decide), the combination over each set
    (combination.combine with event_coding@2's sessions, engine/assess.session_acts), the ADDON row over each set
    (DECISIONS D268), and each counted code's live held facts and item. ``member``: the member context the assessment
    was made with (engine/assess.MemberContext; it decides whether a member-context item names both missing values).

    The competition, through engine/assess.compete_without (one implementation): ``out_of_competition`` are the counted
    codes out of the reviewer's competition - those a member's answer says are not documented as the overlay binds it
    now (DECISIONS D249) and a rival the reviewer rejects whatever it was answered (D270 DQ-3) - read without them and
    without the codes the engine excluded by a "Not documented" answer; the engine's own combination is assess's,
    read without the latter (D260) and without ``assessed``, the codes assess took out by a "Not documented" it read
    for the competition alone (D270 DQ-2: ``assessed_out``, from the stored record) - the record it must reproduce.
    So when a decision unbinds such an answer, the reviewer's competition has the code back: read time restores the
    competition the stored record released.

    The ADDON row (engine/assess's, as assess reads it; DECISIONS D283 G1-03): over the engine's own set it counts the
    codes assess counted - none of ``uncounted``, the codes assess left out of its ADDON count, derived from the stored
    record by ONE function (``assessed_uncounted``: an engine-read answer's exclusion, and an overlay-bound answer of
    either value), nor any code the engine excluded by an answer (its marker) - and over the reviewer's the counted codes
    no answer takes out of review - neither the engine's (their marker) nor ``answered`` (read time's own: the codes an
    answer has bound in its passes, accumulated, engine/assess.answer_pass's ``uncounted``): a primary the reviewer
    rejects, or an answer binds, no longer counts, so an add-on whose every counted primary is gone is held by the row's
    witness (coding_rule:ADDON), and reinstating a primary releases it. A primary that some statement may exclude is
    not counted (DECISIONS D294 RD-2: engine/assess.addon_uncounted, the rule assess's count reads) - over the engine's
    own set always, over the reviewer's unless the reviewer reinstated it.

    Raises UnreadableRecord for a record it cannot read and RecordMismatch when the engine's own counted set does not
    reproduce a stored code's held facts: ONE rule for every hold read time recomputes (DECISIONS D283, G3-32 option
    (b); ``_RECOMPUTED``) - a stored base, base-within, competing, same-day or ADDON hold the engine's own counted set
    does not give is never carried as a hold read time does not recompute."""
    counted = [key for key in dict.fromkeys(counted_keys)]
    engine = [key for key in dict.fromkeys(engine_keys)]
    by_key = {p.key: p for p in rows}
    records = [read_record(by_key[key]) for key in by_key if key in set(counted) | set(engine)]
    evaluations = {record.key: evaluate.decide(record.code, record.kept, R, kept_words=record.kept_words)
                   for record in records}
    sessions_ = coverage.sessions(R)
    pfs = _pfs_rows(retrieval)
    acts = engine_assess.session_acts(coding)
    stored_members = _members(records, engine, R, sessions_, evaluations, pfs)
    members = _members(records, counted, R, sessions_, evaluations, pfs)
    # DECISIONS D260: engine/assess reads the competition without the codes a member answered "Not documented", so the
    # engine's own combination reproduces the stored record only with the answers the engine read taken out the same
    # way - and, by D270 DQ-2, the overlay-bound ones assess read for the competition alone (``assessed``); the
    # reviewer's competition keeps the engine's out too (D249), with the overlay's own answers as they bind now and the
    # rivals the reviewer rejects (``out_of_competition``)
    engine_answered = frozenset(p.key for p in rows if answered_by_engine(p)[0])
    engine_out = frozenset(p.key for p in rows
                           if p.key in stored_members and answered_by_engine(p)[1] == NOT_DOCUMENTED)
    taken = frozenset(assessed)
    before = engine_assess.compete_without(combination.combine(tuple(stored_members.values()), acts, R),
                                           stored_members, engine_out | taken, R)
    after = engine_assess.compete_without(combination.combine(tuple(members.values()), acts, R), members,
                                          frozenset(out_of_competition) | engine_out, R)
    # DECISIONS D268: the codes the ADDON row counts - over the engine's own set its codes no answer excluded (assess's
    # last pass: the counted codes less those a member's answer excluded), over the reviewer's the counted codes no
    # answer takes out of review (the engine's marker or the overlay's own, ``answered``)
    # DECISIONS D294 RD-2: a primary of an add-on here that some statement may exclude is not counted, as assess counted
    # it (engine/assess.addon_uncounted, the one rule assess's count reads) - in the engine's own set always, in the
    # reviewer's unless the reviewer reinstated it (an exclusion the reviewer undid: DECISIONS D268, reinstating a
    # primary releases its add-on)
    wanted = frozenset(primary for record in records for primary in engine_assess.primaries(record.code))
    unsure = frozenset(record.key for record in records if record.code in wanted
                       and engine_assess.addon_uncounted(record.code, record.kept, R, record.kept_words))
    reinstated = frozenset(counted) - frozenset(engine)
    left_out = engine_answered | frozenset(uncounted) | unsure  # D283 G1-03: what assess left out of its ADDON count
    engine_addon = frozenset(found.code for key, found in stored_members.items() if key not in left_out)
    gone = engine_answered | frozenset(answered) | (unsure - reinstated)
    review_addon = frozenset(found.code for key, found in members.items() if key not in gone)
    live: dict[str, Live] = {}
    for record in records:
        if record.key not in members:
            continue
        evaluation = evaluations[record.key]
        own = tuple(evaluation.held_facts)
        stored_combo = tuple(before.held.get(record.key, ())) + (
            _addon(record, evaluation, engine_addon) if record.key in stored_members else ())
        combo = tuple(after.held.get(record.key, ())) + _addon(record, evaluation, review_addon)
        # the item as engine/assess words it: evaluate.item's groups AND what evaluate knows of the holds it raised
        # beside the FactSet (questions.Raised: 3.2.6 rule 2's entries, XCHG's two acts, the synthetic acts), decide
        # being pure - without them read time named another item than assess for SAME_DUCT and UNLISTED_EVIDENCE (the
        # integration's D252 seam check; the integration's fix of the combination, repair r4a-2's request R6)
        decided = evaluate._decide(record.code, record.kept, R, record.kept_words)
        groups = evaluate._groups(decided, evaluation)
        code_facts = evaluate.code_facts(record.code)
        if record.held is not None and record.key in stored_members:
            stored = tuple(record.held)
            # a code the engine excluded by a member's answer is never assessed again (engine/assess._bind_in_passes):
            # its record keeps the competing hold the competition gave when its answer bound, which the later passes'
            # competition (D260) need not reproduce - so its competing hold is left out of the reproduction check (the
            # integration's fix of the combination: refute-5a-r2 P-A, a "Cannot confirm" on one rival beside a "Not
            # documented" on another over two acts) - and so is its ADDON hold, which the later passes' counted set need
            # not reproduce either (DECISIONS D268); a code assess took out of the competition by an overlay-bound "Not
            # documented" (D270 DQ-2) competes with nothing in the engine's own competition, so its competing hold is
            # left out the same way - but not its ADDON hold: engine/assess assesses it again whenever the answers move
            # its ADDON row (DECISIONS D283, G1-02 with C8's correction: engine/assess.read_again), so that hold is the
            # last pass's and is checked (``_unchecked``)
            unchecked = _unchecked(record.key in engine_answered, record.key in taken)
            checked = tuple(found for found in stored if found.cause not in unchecked)
            reproduced = tuple(found for found in stored_combo if found.cause not in unchecked)
            rest = [found for found in _without(_without(checked, own), reproduced) if found.cause not in _RECOMPUTED]
            if engine_questions.ranked((*own, *rest, *reproduced), R) != engine_questions.ranked(checked, R):
                raise RecordMismatch(f'The stored record of {record.code} is not what the inventory gives.')
        else:  # a reinstated exclusion: no held fact was recorded for it (assess's excluded codes carry none)
            stored, rest = (), []
        held = engine_questions.ranked((*own, *rest, *combo), R)
        stored_item = _item(stored, groups, code_facts, R, evaluation.supporting, member, decided.raised)
        item = _item(held, groups, code_facts, R, evaluation.supporting, member, decided.raised)
        changed = item != stored_item or _renamed(item, record.key, before, after, R)
        worded = _words(item, record.key, after, R) if item is not None and changed else None
        live[record.key] = Live(held=held, item=item, stored_item=stored_item, holds=combo, stored_holds=stored_combo,
                                member=members[record.key], worded=worded)
    return Recount(live=live, joined=after, stored_joined=before, members=members, evaluations=evaluations)


def _item(held: Sequence[HeldFact], groups: Sequence[engine_questions.Group], code_facts: engine_questions.CodeFacts,
          R: FactSet, supporting: Sequence[Id], member: Optional[engine_assess.MemberContext],
          raised: Optional[engine_questions.Raised] = None) -> Optional[engine_questions.Item]:
    """A held code's ONE item as engine/assess._assessed chooses it: the first held fact on its binding
    (engine/questions.item with evaluate's ``raised``, as evaluate.item gives it), else - with held facts left - its
    first (D182: one item per held code), and a member-context setting item naming both missing values (Fill.both)
    when the patient status is not entered."""
    if not held:
        return None
    found = engine_questions.item(held, groups, code_facts, R, supporting, raised=raised)
    if found is None:
        found = engine_questions.item(held, (), code_facts, R, supporting)
    if found is not None and found.held.fact == SETTING_FACT and member is not None and not member.patient_status:
        found = replace(found, fill=replace(found.fill, both=True))
    return found


def _named_kind(kind: Optional[Kind]) -> Kind:
    """The kind an item names an act by (DECISIONS D254 rule 2): an act no kind names - engine/questions.act_kind gives
    Kind.OTHER for a kind other or not supported (D267; it gave none before), and an unlisted entry may name none - is
    named by Kind.OTHER, the one label wording gives such an act everywhere (step r3c's words); every other kind is
    itself."""
    return Kind.OTHER if kind is None else kind


def _act_kind(R: FactSet, event: Id) -> Kind:
    """The kind an item names the act ``event`` by (DECISIONS D267: D254 rule 2 reaches every kind that is not
    SUPPORTED): an act whose kind fact is not supported - negated, doubted, unresolved, contradicted or silent - is
    Kind.OTHER, "another act", never the value its kind claims (a negated snare is no snare removal); a supported kind
    is named as engine/questions.act_kind names it (its catalogue kind, Kind.OTHER for a kind other: ``_named_kind``) -
    the reading step r4a's act_kind gives, so the Fill and these slots keep one label. An enumeration test over the
    fact's result: no word is read."""
    if facts_.fact(R, event, Attribute.KIND).result is not Result.SUPPORTED:
        return Kind.OTHER
    return _named_kind(engine_questions.act_kind(R, event, ()))


def _kinds(R: FactSet, events: Iterable[Id]) -> tuple[Kind, ...]:
    """The kinds an item names acts by (``_act_kind``), each once, in order: every act is named, one no kind names - a
    kind other, or a kind not SUPPORTED (DECISIONS D267) - by Kind.OTHER (D254 rule 2: the integration's I2 reading,
    extended from SEPARATE_EM to every slot this fills - the base items' acts, the same-day acts listed and possible,
    the base blocker's)."""
    return tuple(dict.fromkeys(_act_kind(R, event) for event in events))


def _unlisted_kinds(R: FactSet, indices: Iterable[int]) -> tuple[Kind, ...]:
    """The kinds the unlisted entries ``indices`` (FactSet.unlisted) name, each once, in order: an entry that names no
    kind is named by Kind.OTHER (D254 rule 2, as ``_kinds``)."""
    return tuple(dict.fromkeys(_named_kind(R.unlisted[index].kind) for index in indices if index < len(R.unlisted)))


def _whole_kind(R: FactSet, session: Id) -> Optional[SessionKind]:
    """A base-within record's whole session's family (DECISIONS D257): its kind when supported, else None."""
    found = facts_.fact(R, session, Attribute.KIND)
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, SessionKind) else None


def item_slots(item: engine_questions.Item, key: str, joined: combination.Combination,
               R: FactSet) -> Optional[wording.Slots]:
    """The slots a TEXT_FREE item is worded from (wording.Slots), its codes and acts read from the combination's own
    records - the base rule's named codes (D177(1)) and acts, the within rule's codes, the competition's rivals, the
    procedure day's acts - and its family and member context from the item's Fill. An act no kind names - a kind other,
    or a kind not SUPPORTED (DECISIONS D267) - is named by Kind.OTHER in every act slot (DECISIONS D254 rule 2;
    ``_kinds``, ``_unlisted_kinds``). None when the item is not TEXT_FREE, or a date item that quotes a statement: read
    time words it only when its sentence reads no text."""
    message, fill, held = item.message, item.fill, item.held
    if message not in TEXT_FREE:
        return None
    code, family = fill.code, fill.family
    if message is engine_questions.MessageId.ADDON:
        # DECISIONS D284 (build list B7): the add-on and the codes it is reported with (engine/assess.primaries, as the
        # ADDON row reads them), from the codes alone - a true absence form when the table names none
        return wording.Slots(code=code, family=family, codes=tuple(sorted(engine_assess.primaries(code))))
    if held.cause == combination.BASE_CAUSE:
        base = joined.bases.get(key)
        if base is None:
            return None
        if message is engine_questions.MessageId.BASE_INCLUDED:
            listed = _kinds(R, base.doubted) + _unlisted_kinds(R, base.unlisted)
            return wording.Slots(code=code, family=family, listed=tuple(dict.fromkeys(listed)),
                                 codes=base.named_codes)
        return wording.Slots(code=code, family=family, codes=base.named_codes,
                             listed=() if base.named_codes else _kinds(R, base.reportable))
    if held.cause == combination.WITHIN_CAUSE:
        within = joined.within.get(key)
        if within is None:
            return None
        # DECISIONS D257 (repair r3c's request R2, applied by the integration): BASE_WITHIN names the whole by its own
        # family - the supported kind of the record's whole sessions when they are one family, else none (wording:
        # "another procedure") - and states a whole only possibly done as possibly performed on the date of service, its
        # performance not established: no whole of the record is established done (combination.session_done; read
        # from the whole's performance as D257 words it, not from the fit - refute-r3c-r1 F2)
        kinds = {_whole_kind(R, whole) for whole in within.wholes}
        whole_family = next(iter(kinds)) if len(kinds) == 1 else None
        return wording.Slots(code=code, family=family, codes=within.within, whole_family=whole_family,
                             whole_possible=not any(combination.session_done(R, whole) for whole in within.wholes))
    if held.cause == combination.COMPETING_CAUSE:
        rivals = joined.competes.get(key)
        return None if not rivals else wording.Slots(code=code, family=family, codes=tuple(rivals))
    if message is engine_questions.MessageId.SEPARATE_EM:
        day = joined.day
        # every same-day act is named, one no kind names by Kind.OTHER (DECISIONS D254 rule 2: the integration's I2 -
        # which named the acts of a day made only by such acts so - extended to every day; D262), each kind once in its
        # slot: the possible acts and the undatable unlisted entries are one slot, as I2 named them
        listed = _kinds(R, day.done_acts)
        possible = tuple(dict.fromkeys(_kinds(R, day.possible_acts) + _unlisted_kinds(R, day.undatable_unlisted)))
        # D246's codes form (wording: the same-day codes, when the day has no act to list): the procedure day's counted
        # procedural codes, given only then, so an item with acts keeps exactly its slots (the integration's fix of the
        # combination, I1, D262; repair r3c's R3, step 5c's R2)
        codes = () if listed or possible else tuple(other for other in day.codes if other != code)
        return wording.Slots(code=code, family=family, listed=listed, possible=possible, codes=codes)
    if message is engine_questions.MessageId.SERVICE_DATE:
        return None if fill.statements else wording.Slots()
    if message in (engine_questions.MessageId.SETTING, engine_questions.MessageId.PATIENT_STATUS):
        return wording.Slots(code=code, family=family, both=fill.both)
    return None


def _renamed(item: Optional[engine_questions.Item], key: str, before: combination.Combination,
             after: combination.Combination, R: FactSet) -> bool:
    """Whether ``item`` - the same item over both counted sets - would be worded with other slots over the reviewer's
    counted set (``after``) than over the engine's own (``before``): the codes a base rule or a within rule names, a
    competition's rivals, the acts a base or a same-day rule names, read from the combination's records (item_slots).
    Its stored words then name what the decisions moved (a rejected code), and read time words it again, or marks it
    stale when it cannot."""
    return item is not None and item_slots(item, key, after, R) != item_slots(item, key, before, R)


def _encounter_item(item: Optional[engine_questions.Item]) -> bool:
    """The item is the date of service's: the encounter's own question (FINAL-V2 4.8: "service_date | encounter scope";
    assess counts it once, and the renderer asks it once, at encounter scope), never a question of a code's own."""
    return item is not None and item.message is engine_questions.MessageId.SERVICE_DATE


def _words(item: engine_questions.Item, key: str, joined: combination.Combination,
           R: FactSet) -> Optional[wording.Worded]:
    """A changed item in CPT Studio's words (wording.build over item_slots), with no document text: None when its
    sentence would read text, or wording refuses its slots (fail-closed: the code keeps its stored question, held)."""
    slots = item_slots(item, key, joined, R)
    if slots is None:
        return None
    try:
        return wording.build(wording.Message(item.message.value), slots, '')
    except ValueError:
        return None


# --- the separate-lesion modifier review over the effective set (combination.modifier_review) -------------------------

def _act_words(R: FactSet, event: Id) -> str:
    """An act as the modifier review names it, from enumeration values only: its kind's label, at its lesion's first
    supported place (wording.event_kind_label, wording.landmark_label)."""
    kind = engine_questions.act_kind(R, event, ())
    label = wording.event_kind_label(kind.value) if kind is not None else 'act'
    lesion = facts_.fact(R, event, Attribute.TARGET_LESION)
    place = None
    if lesion.result is Result.SUPPORTED and isinstance(lesion.value, Id):
        place = next((found.value for found in facts_.members(R, lesion.value, Attribute.PLACES)
                      if found.result is Result.SUPPORTED and isinstance(found.value, Landmark)), None)
    named = wording.landmark_label(place.value) if place is not None else ''
    return f'{label} at the {named}' if named else label


def _lesion_words(R: FactSet, lesion: Id) -> str:
    place = next((found.value for found in facts_.members(R, lesion, Attribute.PLACES)
                  if found.result is Result.SUPPORTED and isinstance(found.value, Landmark)), None)
    named = wording.landmark_label(place.value) if place is not None else ''
    return f'the lesion at the {named}' if named else 'a documented lesion'


def _modifier_review(p: Stored, members: Mapping[str, combination.Member], R: Optional[FactSet],
                     retrieval: Any) -> Optional[dict[str, Any]]:
    """The separate-lesion modifier review of ``p`` over the effective set's ``members`` (combination.modifier_review:
    its own acts on supported lesions, another code of its session whose lesions are each established distinct from its
    own), in review_view._modifier_review's shape and with its claims-manual citation. None when none applies, and
    with no FactSet (nothing is offered on what cannot be read). Options 59 or XS; nothing is chosen here."""
    member = members.get(p.key)
    if member is None or R is None:
        return None
    found = combination.modifier_review(R, member, tuple(members.values()))
    if found is None:
        return None
    codes = [p.code] + [partner.code for partner in found.partners]
    cited = None
    if p.code in CLAIMS_EXAMPLE_CODES and any(code in CLAIMS_EXAMPLE_CODES and code != p.code for code in codes):
        cited = _example_passage(sorted(CLAIMS_EXAMPLE_CODES & set(codes)), retrieval)
    sources = []
    if cited is not None:
        key, release = str(cited.get('source_key') or ''), str(cited.get('release') or '')
        # the title of a source this release bundles; a source it does not bundle has none here - its key is never a
        # title (refutation round 2, L4-4)
        title, effective_start = _passage_sources().get((key, release), ('', ''))
        sources.append({'key': key, 'title': title, 'release': release, 'effective_start': effective_start,
                        'section': str(cited.get('section') or ''), 'page': str(cited.get('page') or ''),
                        'passage_key': str(cited.get('passage_key') or '')})
    here = [_act_words(R, event) for event in found.acts]
    pair = [(partner.code, [_act_words(R, event) for event in partner.acts]) for partner in found.partners]
    lesions = {p.code: [_lesion_words(R, lesion) for lesion in found.lesions]}
    for partner in found.partners:
        lesions[partner.code] = [_lesion_words(R, lesion) for lesion in partner.lesions]
    return {'kind': MODIFIER_REVIEW, 'codes': codes, 'service': str(found.session), 'lesions': lesions,
            'options': [option.value for option in found.options],
            'text': checks.distinct_lesion_review_text(p.code, here, pair, sources[0]['release'] if sources else ''),
            'sources': sources, 'not_checked': list(DISTINCT_LESION_NOT_CHECKED)}


# --- the orchestration (review_view.review_view, ported; FINAL 8.1, FINAL-V2 4.8) -------------------------------------

_POSITIONAL = frozenset({combination.BASE_CAUSE, combination.WITHIN_CAUSE, combination.COMPETING_CAUSE})


def _rule_id(held: HeldFact) -> str:
    """The check id a cross-code hold is named by in ``recomputed`` and ``stale`` (v1's ids, which the consumers read):
    its rule's, the ADDON row's own (ADDON_CHECK, DECISIONS D268), or the same-day gate's for a same-day hold
    (separate_em, or an event_time the combination raised)."""
    return _RULE_IDS.get(held.cause, SAME_DAY_EM_GATE)


def _same_day(held: HeldFact) -> bool:
    """A same-day hold of the combination (separate_em, event_time): every cross-code hold but base, within, competing
    and the ADDON row's (DECISIONS D268: an add-on of the office family held by its row is not held by the same-day
    rule)."""
    return held.cause not in _POSITIONAL and held.cause != ADDON_CAUSE


def _base_of(live: Optional[Live], joined: Optional[combination.Combination], key: str,
             R: Optional[FactSet]) -> Optional[tuple[str, tuple[str, ...]]]:
    """(rule, names) of the base rule that holds ``key`` over the counted set - ('within', its wholes' codes) or
    ('included', its named codes, else the kinds of the acts it names) - None when none does (review_view._bases'
    shape, which _held_blocker reads)."""
    if live is None or joined is None or R is None:
        return None
    causes = {held.cause for held in live.holds}
    if combination.BASE_CAUSE in causes and key in joined.bases:
        found = joined.bases[key]
        if found.named_codes:
            return 'included', found.named_codes
        kinds = _kinds(R, (*found.reportable, *found.doubted)) + _unlisted_kinds(R, found.unlisted)
        # D254 rule 2's one label for an act no kind names (wording.kind_words: repair r3c's function, its article
        # included; v1's event_kind_label keeps 'act' - the integration's fix of the combination, step 5c's R1)
        return 'included', tuple(dict.fromkeys(wording.kind_words(kind) for kind in kinds))
    if combination.WITHIN_CAUSE in causes and key in joined.within:
        return 'within', joined.within[key].within
    return None


def _stale_ids(p: Stored) -> list[str]:
    """The holds a counted set that moved may have changed on ``p`` when nothing could be recomputed: the rules its
    stored questions name (base, competing, the same-day visit), by v1's ids."""
    out = []
    for question in p.questions:
        fact = question.get('fact')
        if fact == BASE_FACT:
            out.append(BASE_CHECK)
        elif fact == COMPETING_FACT:
            out.append(COMPETING_CHECK)
        elif fact == SEPARATE_EM_FACT:
            out.append(SAME_DAY_EM_GATE)
    return out


def _proposal_questions(questions_: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [q for q in questions_ if q.get('scope') != 'proposal']


def _answerable(live: Live, stored: Sequence[Any]) -> list[Any]:
    """The facts a member's answer binds to on a code whose item read time recomputed (``stored``: the facts of its
    stored questions): none once its item is released or is the encounter's date question (no answer settles the date:
    engine/assess.engine_reads); the item's own once read time worded it; else - the stored question stands, stale - a
    stored question only when it asks the live item's own fact. An answer to a stale question about another fact binds
    nothing (assess, over the same counted set, would not apply it: the code stays held, never excluded by it)."""
    if live.item is None or _encounter_item(live.item):
        return []
    if live.worded is not None:
        return [live.worded.fact]
    if _released_item(live):  # r2 (D294, WORDS-F2): the live item is asked in fixed words (_unworded_question)
        return [live.item.held.fact]
    return [fact for fact in stored if fact == live.item.held.fact]


def _bound_form(p: Stored, live: Optional[Live], reworded: bool, fact: str) -> str:
    """r2 (DECISIONS D294): the member form of the question an answer to ``fact`` binds on ``p`` - the live item's where
    read time asks it (worded, or in fixed words where its released hold gave way: ``_answerable``), else the stored
    question's of that fact (wording.asked_form over the record's item), '' for a reinstatement's wait."""
    if (live is not None and reworded and live.item is not None and fact == live.item.held.fact
            and (live.worded is not None or _released_item(live))):
        return _live_form(live)
    return next((wording.asked_form(q, p.support) for q in p.questions
                 if q.get('scope') == 'proposal' and q.get('fact') == fact), '')


def _engine_form(p: Stored) -> str:
    """The member form of the question a member's answer the engine read excluded ``p`` on (answered_by_engine): its
    record's item, which engine/assess bound the answer to by its fingerprint, when the item is of the answered fact."""
    item = (p.support or {}).get('item') if isinstance(p.support, Mapping) else None
    fact = answered_by_engine(p)[0]
    return wording.recorded_form(item) if isinstance(item, Mapping) and item.get('fact') == fact else ''


def _released_item(live: Live) -> bool:
    """r2 (DECISIONS D294, WORDS-F2): whether the recount released the hold the stored item rests on - a cross-code hold
    of the stored record (the combination's or the ADDON row's) that the counted set no longer gives - while the code
    is still held by another item: nothing read time shows may rest on the released hold."""
    return (live.stored_item is not None and live.item is not None
            and live.stored_item.held not in live.held)


def _live_form(live: Live) -> str:
    """The member form of the live item (wording.member_form over its message and the slots its Fill gives)."""
    if live.item is None:
        return ''
    fill = live.item.fill
    return wording.member_form(wording.Message(live.item.message.value),
                               wording.Slots(act=fill.act, family=fill.family))


# r2 (D294, WORDS-F2): each conflict key a held fact can carry (conflict:<kind>, RANK row 1), by its kind - read by key,
# never by a string operation on a value (FINAL-V2 5.7 measure 4)
_CONFLICT_KEYS: Mapping[str, Kind] = MappingProxyType({f'conflict:{kind.value}': kind for kind in Kind})


def _fact_sentence(fact: str, form: str = '') -> str:
    """CPT Studio's fixed sentence for a held fact's key, naming no cause and quoting nothing: what read time asks of an
    item it cannot word (``_unworded_question``) - an item of a member form by its form's own words
    (wording.FORM_MISSING: never its key's where the key's row asks something else, D294 - "in which procedure the act
    was done" is never said of a route or tract whose procedure is known, D267), else the fact in the member's own words
    (wording.MISSING for the facts of D181 and the new path, else studio.validation.questions.missing), a conflict's act
    by its one label (D254 rule 2: 'another act' for a kind that names none)."""
    missing = wording.FORM_MISSING.get(form)
    if missing is not None:
        return f'CPT Studio could not confirm from the document {missing}.'
    kind = _CONFLICT_KEYS.get(fact)
    if kind is not None:
        about = (questions.missing('conflict:', wording.kind_words(kind)) if wording.named_kind(kind) else
                 f'which statement about {wording.NO_KIND_LABEL} is right for this date')
    else:
        about = wording.MISSING.get(fact) or questions.missing(fact)
    return f'A detail is needed: {about}.'


def _unworded_question(p: Stored, live: Live) -> dict[str, Any]:
    """r2 (D294, WORDS-F2): the question of a live item read time cannot word, given way to by a released hold: its fact,
    its message and its form, in CPT Studio's fixed sentence for its key (``_fact_sentence``)."""
    item = cast(engine_questions.Item, live.item)  # _released_item: a live item
    form = _live_form(live)
    words = _fact_sentence(item.held.fact, form)
    return {'id': '', 'scope': 'proposal', 'family': p.family, 'fact': item.held.fact, 'question': words,
            'reason': words, 'message': item.message.value, 'form': form}


def _recount_or_none(rows: Sequence[Stored], counted: Iterable[str], engine: Iterable[str],
                     coding: Optional[Mapping[str, Any]], facts: Optional[FactSet], retrieval: Any,
                     member: Optional[engine_assess.MemberContext], out: Iterable[str], answered: Iterable[str] = (),
                     assessed: Iterable[str] = (), uncounted: Iterable[str] = ()) -> Optional[Recount]:
    """recount, or None when the coding or the FactSet cannot be read, or a record cannot be read or is not reproduced
    by the engine's own counted set: nothing is then recomputed (fail-closed). ``uncounted``: assessed_uncounted of the
    stored record (DECISIONS D283 item 3)."""
    if coding is None or facts is None:
        return None
    try:
        return recount(rows, counted, engine, coding, facts, retrieval=retrieval, member=member,
                       out_of_competition=out, answered=answered, assessed=assessed, uncounted=uncounted)
    except (ValueError, LookupError, TypeError):  # UnreadableRecord, RecordMismatch, a record the engine cannot read
        return None


def _competition_moved(found: Recount) -> bool:
    """Whether the reviewer's competition differs from the engine's own over one counted set (DECISIONS D249: a code out
    of the competition; D270: a rival the reviewer rejects, a code back in it when a decision unbinds the answer assess
    read): a competing hold, or the rivals one names."""
    return (found.joined.held != found.stored_joined.held
            or found.joined.competes != found.stored_joined.competes)


def _addon_moved(found: Recount) -> bool:
    """Whether a counted code's ADDON row differs over the reviewer's counted set from over the engine's own (DECISIONS
    D268: a primary rejected, excluded by an answer, or reinstated)."""
    return any(held.cause == ADDON_CAUSE for live in found.live.values() for held in (*live.added, *live.released))


def _rejected(decided: Optional[Decided]) -> bool:
    return decided is not None and decided.action == REJECT


def _addon_unrecomputed(p: Stored, engine_counted: Collection[str], review_counted: Collection[str]) -> str:
    """Where nothing could be recomputed (DECISIONS D268, fail-closed): how the ADDON row of ``p`` - an add-on, by
    engine/assess.primaries - moved between the codes it counts over the engine's own set (``engine_counted``: its
    selected codes) and over the reviewer's (``review_counted``: the counted codes no answer took out of review) -
    'held' when one of its primaries counted and none counts now (a hold read time cannot add: the add-on is held,
    stale, never approvable alone), 'released' when none counted and one counts now (the stored hold stands, stale),
    '' otherwise."""
    primaries = engine_assess.primaries(p.code)
    if not primaries:
        return ''
    had, has = bool(primaries & frozenset(engine_counted)), bool(primaries & frozenset(review_counted))
    return 'held' if had and not has else 'released' if has and not had else ''


def _rival_out(p: Stored, out_codes: Collection[str]) -> bool:
    """Whether a code ``p``'s stored record names as its rival (support['competes']) is out of the competition
    (DECISIONS D249): read where nothing could be recomputed, so its stored competing hold is marked stale."""
    rivals = (p.support or {}).get('competes') if isinstance(p.support, Mapping) else None
    return isinstance(rivals, list) and any(isinstance(code, str) and code in out_codes for code in rivals)


def _engine_read_keys(answers: Any) -> frozenset[tuple[str, str, str]]:
    """The (code, family, fact) keys of the standing answers engine/assess reads itself (engine/assess.engine_reads, the
    one rule: a code and its question's fingerprint, to a fact neither key-bound nor competing_codes nor the encounter's
    date) - read time treats such an answer as assess does, an exclusion that stands once bound (DECISIONS D283); every
    other answer is the overlay's, bound by its key in each pass. An answer that carries no fingerprint (the earlier
    form, or a caller that gives none) is the overlay's."""
    out = set()
    for answer in answers or ():
        code, family, fact = (str(_field(answer, name) or '') for name in ('code', 'family', 'fact'))  # type: ignore[no-untyped-call]
        question = str(_field(answer, 'question') or '')  # type: ignore[no-untyped-call]
        if code and engine_assess.engine_reads(cast(Any, SimpleNamespace(code=code, question=question, fact=fact))):
            out.add((code, family, fact))
    return frozenset(out)


def _values(bound: Mapping[str, tuple[str, str]]) -> dict[str, engine_assess.Answer]:
    """{key: engine/assess.Answer} of read time's bindings {key: (fact, value)} (a value no question takes is left out,
    as engine/assess._answers_of leaves it out)."""
    out: dict[str, engine_assess.Answer] = {}
    for key, (_, value) in bound.items():
        try:
            out[key] = engine_assess.Answer(value)
        except ValueError:
            continue
    return out


def review_view(stored: Sequence[Stored], decisions: Mapping[str, Any], *, completeness: object = None,
                retrieval: Any = (), reference_sources: Any = (), service_date: Optional[datetime.date] = None,
                answers: Any = (), facts: Optional[FactSet] = None,
                member: Optional[engine_assess.MemberContext] = None) -> dict[str, View]:
    """{proposal key: View} of ``stored`` (one v2 assessment's proposals, in their stored order) under ``decisions``
    ({key: current action, a Decided, or a Decision}) and ``answers`` (the current member answers: mappings or objects
    with code, family, fact and value), as review_view.review_view reads a legacy assessment, with the seams of the
    module docstring. ``completeness``: Assessment.completeness, whose event_coding@2 the seams read (an unreadable one
    fails closed); ``facts``: the frozen inventory's FactSet (``reading``; None when it cannot be read: fail-closed);
    ``member``: the member context the assessment was made with (engine/assess.MemberContext); ``retrieval``,
    ``reference_sources``, ``service_date``: as review_view's."""
    rows = list(stored)
    decided = {key: _decided(value) for key, value in (decisions or {}).items()}
    coding = coding_of(completeness)
    answered, closed = proposal_answers(answers), service_answers(answers)
    service = {p.key: _service(p, coding, decided.get(p.key)) for p in rows}
    # The COUNTED set: the codes as the current decisions leave them - selected and not rejected, or reinstated - whatever
    # a member answered. Every hold reads it (session decision (e); refutation round 2, L7-01) - but the competition: a
    # member's answer that a code is not documented removes it from the competition at read time (DECISIONS D249).
    candidates = [p for p in rows if counts(p, decided.get(p.key))]
    counted = {p.key for p in candidates}
    selected = {p.key for p in rows if p.bucket == SELECTED}
    engine_counted = selected | {p.key for p in rows if answered_by_engine(p)[0]}
    engine_keys = [p.key for p in rows if p.key in engine_counted]
    counted_moved = counted != engine_counted
    # DECISIONS D249 (5a's Q2): a member's answer that a code is not documented takes it out of the reviewer's
    # competition (below, by answer_pass). D270 DQ-3: a rival the reviewer rejects leaves the competition whatever it was answered ("Cannot confirm"
    # included) - an engine-answered code counts whatever its decision (``counts``: session decision (e)), so its
    # rejection takes it out alone, which makes the competition hold's own sentence true; with no decision a "Cannot
    # confirm" keeps the hold (D260's effect). (A rejected code that was not answered is not counted at all.)
    rejected_answered = {p.key for p in rows if answered_by_engine(p)[0] and _rejected(decided.get(p.key))}
    # DECISIONS D270 DQ-2 and D283 item 3: what assess read for its own competition and its own ADDON count, from the
    # stored record alone (the engine's own combination reproduces it; the reviewer's reads read time's own binding)
    assessed = assessed_out(completeness, rows)
    uncounted_record = assessed_uncounted(completeness, rows)
    # DECISIONS D283 items 1-2 (build list B16): read time's answer passes apply assess's ONE rule
    # (engine/assess.answer_pass, the implementation both halves call). Each pass: the competition leaves out every code
    # an answer the engine reads excluded "Not documented" and every code an overlay-bound "Not documented" binds IN THIS
    # PASS (recomputed, so a code whose answer no longer binds is back in it - D270 DQ-2's restore); the ADDON row counts
    # no code an answer has bound, of either value, accumulated over the passes so that they end (G1-03). An answer the
    # engine reads (engine/assess.engine_reads: by its question's fingerprint) excludes its code and stands - assess never
    # reads such a code again; an overlay-bound answer binds the item its code presents IN EACH PASS, so a code whose
    # ADDON row a pass moves is read again and its answer binds only the item it then presents (C7's correction: assess
    # and read time alike) - never "an answer that binds stands" for it.
    reads = _engine_read_keys(answers)
    stands: dict[str, tuple[str, str]] = {p.key: answered_by_engine(p) for p in rows if answered_by_engine(p)[0]}
    bound_now: dict[str, tuple[str, str]] = {}
    # r2 (DECISIONS D294): the member form of the question each binding answers (``_bound_form``), which the view of a
    # code an answer leaves detail_unavailable carries (View.answered_form) for the row that shows the answer in effect
    answered_forms: dict[str, str] = {p.key: _engine_form(p) for p in rows if p.key in stands}
    passed: Optional[engine_assess.AnswerPass] = None
    found: Optional[Recount] = None
    live_of: Mapping[str, Live] = {}
    for _ in range(2 * len(rows) + 4):  # the passes end (bindings of an add-on are lost at most once); bounded anyway
        passed = engine_assess.answer_pass(_values(stands), _values(bound_now), passed)
        out = set(passed.out) | rejected_answered
        # FINAL-V2 4.8: the read-time engine over the counted set, from the frozen inventory; a record or an inventory
        # that cannot be read, or that the engine's own counted set does not reproduce, recomputes nothing (fail-closed)
        found = _recount_or_none(rows, [p.key for p in candidates], engine_keys, coding, facts, retrieval, member, out,
                                 passed.uncounted, assessed, uncounted_record)
        live_of = found.live if found is not None and (counted_moved or _competition_moved(found)
                                                       or _addon_moved(found)) else {}
        # the codes whose item stays but whose words name what the decisions moved (a rejected code, a released act)
        renamed_keys = ({key for key, live in live_of.items()
                         if not live.moved and _renamed(live.item, key, found.stored_joined, found.joined, facts)}
                        if found is not None and facts is not None else set())
        # Member answers, bound to the item the code presents now, or to its stored questions where nothing was
        # recomputed: an answer the engine reads stands once bound; an overlay-bound one is bound again each pass
        next_stands: dict[str, tuple[str, str]] = dict(stands)
        next_bound: dict[str, tuple[str, str]] = {}
        for p in rows:
            if p.key in stands:
                continue
            live = live_of.get(p.key)
            open_facts = [q.get('fact') for q in p.questions if q.get('scope') == 'proposal']
            if live is not None and (live.moved or p.key in renamed_keys):
                open_facts = _answerable(live, open_facts)
            if p.key in counted and p.bucket == EXCLUDED:
                open_facts += [q['fact'] for q in _reinstatement_waits(p)]
            # DECISIONS D283, G1-01 option (c): an answer to the competing question binds nothing, at assess or at
            # read time (engine/assess.overlay_bound never reads one) - the competing hold is settled by the
            # reviewer's rejection (D270 DQ-3), never by an answer
            by = next(((fact, answered[(p.code, p.family, fact)]) for fact in open_facts
                       if fact != COMPETING_FACT and answered.get((p.code, p.family, fact))), ('', ''))
            if by[0]:
                (next_stands if (p.code, p.family, by[0]) in reads else next_bound)[p.key] = by
                answered_forms[p.key] = _bound_form(p, live, live is not None and (live.moved or p.key in renamed_keys),
                                                    by[0])
        settled = next_stands == stands and next_bound == bound_now
        stands, bound_now = next_stands, next_bound
        if found is None or settled:
            break
    else:  # not reached on a record the engine made (the passes end); fail-closed: nothing recomputed
        found, live_of = None, {}
    # the pass the last binding leaves (the bindings of the last pass, which the loop ended on): the competition's and
    # the ADDON count's sets - kept so, where nothing was recomputed, a rival this pass's answers took out of the
    # competition still marks the stored hold that names it stale (``_rival_out``)
    passed = engine_assess.answer_pass(_values(stands), _values(bound_now), passed)
    out = set(passed.out) | rejected_answered
    unavailable: dict[str, tuple[str, str]] = {**stands, **bound_now}
    out_codes = {p.code for p in rows if p.key in out}
    # The EFFECTIVE set: the counted codes still in review, which the combination readings that hold nothing read.
    effective = [p for p in candidates if p.key not in unavailable]
    # DECISIONS D268 where nothing could be recomputed: the codes the ADDON row counts over the engine's own set (its
    # selected codes) and over the reviewer's (the effective codes)
    addon_engine = {p.code for p in rows if p.bucket == SELECTED}
    addon_review = {p.code for p in effective}
    keys = {p.key for p in effective}
    moved = keys != selected
    effective_members = {key: found.members[key] for key in found.members if key in keys} if found is not None else {}
    pfs = _pfs_rows(retrieval)
    sources = _sources(reference_sources)
    pfs_keys = {s.key for s in sources if s.kind == PFS}
    pfs_complete = all((pfs.get(p.code) or {}).get('source_key') in pfs_keys for p in rows
                       if decidable(p) and any(c.get('id') == PRESENCE_CHECK and c.get('status') == 'pass'
                                               for c in p.checks))
    active_rows = combination.endoscopic_rows((p.code, pfs.get(p.code)) for p in effective)
    views = {}
    for p in rows:
        d = decided.get(p.key)
        action = d.action if d is not None else ''
        chosen = tuple(d.modifiers) if d is not None and action == APPROVE else ()
        if p.key in unavailable:
            fact, value = unavailable[p.key]
            words = ANSWER_WORDS.get(value, 'unavailable')
            views[p.key] = View(
                key=p.key, code=p.code, bucket=p.bucket, decision=action, active=p.key in counted,
                status=STATUS_EXCLUDED,
                reason=DETAIL_UNAVAILABLE, checks=tuple(dict(c) for c in p.checks), questions=(), added=(),
                released=(), withheld_by='', reinstatement_clear=False, same_day_held=False,
                blocker=(f'{p.code} was approved, but a detail it needs was answered as {words}: revoke the approval'
                         if action == APPROVE else ''),
                recomputed=(), stale=(), modifier_review=None, modifiers=chosen, summary=summary(p),
                answer=value, answered=fact, answered_form=answered_forms.get(p.key, ''))
            continue
        items = [dict(c) for c in p.checks]
        questions_ = [dict(q) for q in p.questions
                      if not (q.get('scope') != 'proposal' and (q.get('family'), q.get('fact')) in closed)]
        added, released, recomputed, stale = [], [], [], []
        active = p.key in keys
        stored_clear = _reinstatement_clear(p)
        live = live_of.get(p.key) if active else None
        status = p.status
        base_added = same_day = addon_held = False
        if live is not None:
            changed = (*live.added, *live.released)
            added += [held.fact for held in live.added]
            released += [held.fact for held in live.released]
            base_added = any(held.cause in (combination.BASE_CAUSE, combination.WITHIN_CAUSE) for held in live.added)
            same_day = p.family in _EM_SLUGS and any(_same_day(held) for held in live.added)
            # DECISIONS D268: an add-on its ADDON row holds over the counted set is never approvable alone
            addon_held = any(held.cause == ADDON_CAUSE for held in live.held)
            reworded = live.moved or p.key in renamed_keys
            if reworded and (live.item is None or _encounter_item(live.item)):
                # released, or given way to the date of service's item - the encounter's own question (4.8): the code
                # keeps no question of its own (held while the date is unknown)
                questions_ = _proposal_questions(questions_)
                recomputed += [_rule_id(held) for held in changed]
            elif reworded and live.worded is not None:
                # the live question carries its item's message (DECISIONS D284, build list B7: customer_api chooses the
                # ADDON row's fixed sentence by it, never by the fact key it shares with the status row; r2, D294: so do
                # the member's row and the door - a TEXT_FREE message's form is its message's, wording.asked_form)
                questions_ = _proposal_questions(questions_) + [{
                    'id': '', 'scope': 'proposal', 'family': p.family, 'fact': live.worded.fact,
                    'question': live.worded.question, 'reason': live.worded.reason,
                    'message': live.item.message.value if live.item is not None else ''}]
                recomputed += [_rule_id(held) for held in changed] or (
                    [_rule_id(live.item.held)] if live.item is not None else [])
            elif reworded and _released_item(live):
                # r2 (DECISIONS D294, WORDS-F2): the recount released the hold the stored item rests on, so nothing
                # shown rests on it - the stored question is no longer the code's open question, whether or not the
                # next item can be worded; the live item, which read time cannot word, is asked in CPT Studio's fixed
                # sentence for its fact key, with its fact, message and form (the customer's sentence and the member's
                # row are chosen from the live holds: customer_api, answers), an answer binds to it (``_answerable``),
                # and the released hold is listed recomputed, never stale (a hold the decisions ADDED, which read time
                # cannot word, stays stale as before)
                questions_ = _proposal_questions(questions_) + [_unworded_question(p, live)]
                recomputed += [_rule_id(held) for held in live.released]
                stale += [_rule_id(held) for held in live.added]
            elif reworded:  # a changed item read time cannot word: the stored question stands, marked stale (held)
                stale += [_rule_id(held) for held in changed] or (
                    _stale_ids(p) or [BASE_CHECK] if live.moved or live.item is None else [_rule_id(live.item.held)])
            else:
                recomputed += [_rule_id(held) for held in changed]
            if p.bucket == SELECTED:
                status = NEEDS_CLARIFICATION if live.held else READY
                if reworded and live.item is not None and live.worded is None:
                    status = NEEDS_CLARIFICATION
        elif active and counted_moved:
            stale += _stale_ids(p)
        elif active and found is None and _rival_out(p, out_codes):
            stale.append(COMPETING_CHECK)  # D249's release could not be recomputed: the stored hold stands, stale
        if live is None and active and found is None:
            # DECISIONS D268, fail-closed where nothing could be recomputed: a primary rejected or answered away is a
            # hold a decision ADDS, which a stale stored record does not carry - the add-on is held, never approvable
            # alone; a primary reinstated would release the stored hold, which stands - both marked stale
            addon = _addon_unrecomputed(p, addon_engine, addon_review)
            if addon:
                stale.append(ADDON_CHECK)
            if addon == 'held':
                addon_held = True
                if p.bucket == SELECTED:
                    status = NEEDS_CLARIFICATION
        # a reinstated exclusion is asked what its stored gate says its approval waits for (refutation round 2, L3-8)
        waits = _reinstatement_waits(p) if p.bucket == EXCLUDED and active else ()
        for wait in waits:
            questions_.append(dict(wait))
            added.append(wait['fact'])
        if decidable(p):
            at = _find(items, ENDOSCOPIC_CHECK)
            if at is not None and items[at].get('status') != 'not_verified':
                row = pfs.get(p.code)
                # recomputed only from a record read whole (``found``): an unreadable one - every v1 row - is read as
                # stored, its check marked stale where the decisions moved what it reads
                if found is not None and pfs_complete and row and row.get('source_key') in pfs_keys:
                    ref = CodeReference(code=p.code, pfs=row, applicable_sources=(str(row['source_key']),))
                    rows_ = cast(Mapping[str, dict[Any, Any]], active_rows)
                    new = _jsonable(checks.endoscopic_check(p.code, ref, rows_, sources, service_date))
                    if new != items[at]:
                        items[at] = new
                        recomputed.append(ENDOSCOPIC_CHECK)
                elif moved:
                    stale.append(ENDOSCOPIC_CHECK)
        if p.bucket == EXCLUDED and active and (base_added or not stored_clear or (live is not None and live.held)
                                                or addon_held):
            # a reinstated exclusion whose approval waits on a question, or that a hold of the counted set holds, needs
            # clarification: never ready
            status = NEEDS_CLARIFICATION
        withheld = ''
        if p.bucket == SELECTED and active and not action and base_added and status == NEEDS_CLARIFICATION:
            withheld = BASE_CHECK
        elif p.bucket == EXCLUDED and action == REINSTATE:
            withheld = (REINSTATEMENT_CHECK if not stored_clear else BASE_CHECK if base_added
                        else ADDON_CHECK if addon_held else SAME_DAY_EM_GATE if same_day else '')
        review = _modifier_review(p, effective_members, facts if found is not None else None, retrieval) \
            if active else None
        held = _base_of(live, found.joined if found is not None else None, p.key, facts)
        blocker = ''
        if action == APPROVE:
            if (p.bucket == SELECTED and status == NEEDS_CLARIFICATION and held and base_added) or (
                    p.bucket == EXCLUDED and base_added):
                blocker = _held_blocker(p, held, candidates, service.get(p.key))
            elif status == NEEDS_CLARIFICATION:
                blocker = f'{p.code} was approved, but it now needs clarification; revoke the approval'
            elif chosen and (review is None or any(m not in review['options'] for m in chosen)):
                blocker = (f'{p.code} was approved with modifier {", ".join(chosen)}, but the separate-lesion '
                           'modifier review no longer applies to it; revoke the approval and decide it again')
        views[p.key] = View(
            key=p.key, code=p.code, bucket=p.bucket, decision=action, active=active, status=status, reason='',
            checks=tuple(items), questions=tuple(questions_), added=tuple(dict.fromkeys(added)),
            released=tuple(dict.fromkeys(released)), withheld_by=withheld,
            reinstatement_clear=stored_clear and not base_added and not addon_held, same_day_held=same_day,
            blocker=blocker, recomputed=tuple(dict.fromkeys(recomputed)), stale=tuple(dict.fromkeys(stale)),
            modifier_review=review,
            modifiers=chosen, summary=summary(p), answer='')
    return views


_EM_SLUGS = frozenset(engine_assess.family_slug(family) for family in catalogue.EM_FAMILIES)


# --- the documented-event coverage as the review leaves it (FINAL-V2 6.5) ---------------------------------------------

def session_label(session: coverage.Session) -> str:
    """How completeness names a session not listed (coverage.completeness's ``label``): the service its kind names
    (wording.service_phrase over wording.SESSION_SERVICES); for a kind that names no service (sedation, an E/M of
    another setting, another GI service, a service outside the GI profiles) and for a kind not established, a noun
    phrase that reads in completeness's list as a service's label does (UNNAMED_SERVICE_LABELS,
    UNESTABLISHED_SERVICE_LABEL). The ONE label (DECISIONS D246): the renderer passes this function to the engine, so
    assess and read time word a session not listed alike, and read time reproduces the stored reason."""
    kind = session.kind
    if kind is None:
        return UNESTABLISHED_SERVICE_LABEL
    if wording.SESSION_SERVICES.get(kind):
        return wording.service_phrase(kind)
    return UNNAMED_SERVICE_LABELS.get(kind) or wording.service_phrase(kind)


class UnreadableCounts(ValueError):
    """The stored completeness does not record its own counts in the structured form reviewed_completeness reads, or
    (assessment_counts) no counts reproduce it over the engine's own counted set."""


def stored_counts(completeness: object) -> dict[str, Any]:
    """The assessment's own counts (COUNTS), as the stored completeness records them: open_questions, unverified and
    conflicts non-negative integers, provider_ok true or false. UnreadableCounts otherwise - never parsed from its
    sentences (FINAL-V2 5.7 measure 4)."""
    found: dict[str, Any] = ({name: completeness.get(name) for name in COUNTS} if isinstance(completeness, Mapping)
                             else {})
    if not (all(type(found.get(name)) is int and found[name] >= 0
                for name in ('open_questions', 'unverified', 'conflicts'))
            and type(found.get('provider_ok')) is bool):
        raise UnreadableCounts('The stored completeness does not record its own counts.')
    return found


# The results that leave a held fact's attribute unverified (engine/assess's count behind completeness's unverified
# reason, coverage.UNVERIFIED_REASON).
_UNVERIFIED_RESULTS = frozenset({Result.UNRESOLVED, Result.UNKNOWN, Result.CONTRADICTED})


def _reproduces(completeness: Mapping[str, Any], found: coverage.Coverage, sessions_: Mapping[Id, coverage.Session],
                own: Mapping[str, Any], label: Callable[[coverage.Session], str]) -> bool:
    """Whether coverage.completeness over ``found`` with the counts ``own`` gives the stored ``completeness`` exactly:
    every key it writes (the state, the reasons, the statement, the services, the unresolved and the conflicts)."""
    again = coverage.completeness(found, sessions_, open_questions=own['open_questions'],
                                  provider_ok=own['provider_ok'], conflicts=own['conflicts'], label=label,
                                  unverified=own['unverified'])
    return all(completeness.get(key) == value for key, value in again.items())


def assessment_counts(completeness: object, R: FactSet, rows: Sequence[Stored], *, retrieval: object = (),
                      label: Callable[[coverage.Session], str] = session_label) -> dict[str, Any]:
    """The assessment's own counts (COUNTS) its reviewed coverage keeps (FINAL-V2 6.5; v1 kept them too): the ones the
    stored completeness records (stored_counts; this step's request R2), else derived - never from a sentence:

    - conflicts: the stored completeness's own count (coverage.completeness writes it);
    - unverified: engine/assess's count - the (subject, attribute) pairs the held facts of the engine's own counted
      codes (``rows`` selected, or excluded by a member's answer) leave unresolved, unknown or contradicted - their
      evaluations made again over ``R`` (engine/evaluate.decide over each stored record);
    - provider_ok and open_questions: the one pair under which coverage.completeness over the engine's own counted set
      (coverage.reconcile with that set's procedure day, as assess reconciled it) reproduces the stored completeness
      exactly. open_questions is at most what assess can count: a question per counted code, per in-doubt act and per
      session, and the encounter's date question.

    Either way the counts must reproduce the stored completeness over the engine's own counted set: UnreadableCounts
    when they do not (a record this release does not reproduce: nothing is re-run from it, fail-closed),
    UnreadableRecord for a stored record it cannot read. ``retrieval``: the assessment's retrieval trace (the PFS rows
    a code's procedure mark falls back to); ``label``: how the renderer named a session not listed (session_label).
    Pure."""
    if not isinstance(completeness, Mapping):
        raise UnreadableCounts('The assessment records no completeness.')
    read_coding(completeness)  # FINAL-V2 6.5: an event coding not @2 (a v1 row's @1 among them) is UnreadableCoding
    conflicts = completeness.get('conflicts')
    if type(conflicts) is not int or conflicts < 0:
        raise UnreadableCounts('The stored completeness does not count its conflicts.')
    records = [read_record(p) for p in rows if p.bucket == SELECTED or questions.answered_away(p)]
    evaluations = {record.key: evaluate.decide(record.code, record.kept, R, kept_words=record.kept_words)
                   for record in records}
    sessions_ = coverage.sessions(R)
    members = _members(records, [record.key for record in records], R, sessions_, evaluations, _pfs_rows(retrieval))
    day = combination.procedure_day(R, tuple(combination.ProceduralCode(member.code, member.family, member.procedural,
                                                                         member.supported)
                                             for member in members.values()))
    found = coverage.reconcile(R, [coverage.Counted(key=record.key, code=record.code, family=record.family,
                                                    supporting=evaluations[record.key].supporting,
                                                    read=_read_events(evaluations[record.key])) for record in records],
                               procedure_day=bool(day.done), sessions_=sessions_)
    try:
        recorded = stored_counts(completeness)
    except UnreadableCounts:
        recorded = None
    if recorded is not None:
        if not _reproduces(completeness, found, sessions_, recorded, label):
            raise UnreadableCounts('The stored counts do not give the stored completeness.')
        return recorded
    unverified = len({(held.subject, held.attribute) for evaluation in evaluations.values()
                      if evaluation.exclusion is None for held in evaluation.held_facts
                      if held.result in _UNVERIFIED_RESULTS})
    bound = len(records) + len(found.in_doubt) + len(sessions_) + 1
    for provider_ok in (True, False):
        for open_questions in range(bound + 1):
            own = {'open_questions': open_questions, 'unverified': unverified, 'provider_ok': provider_ok,
                   'conflicts': conflicts}
            if _reproduces(completeness, found, sessions_, own, label):
                # a count the record carries in part (not all of COUNTS) must agree, or the record is not believed
                if any(name in completeness and (type(completeness[name]) is not type(own[name])
                                                 or completeness[name] != own[name]) for name in COUNTS):
                    raise UnreadableCounts('A count the stored completeness records is not what it gives.')
                return own
    raise UnreadableCounts('The stored completeness is not what its own counted codes give.')


def reviewed_completeness(completeness: Mapping[str, Any], R: FactSet, counted: Sequence[coverage.Counted],
                          reinstated: Iterable[tuple[str, str]], *, members: Iterable[combination.Member] = (),
                          label: Callable[[coverage.Session], str] = session_label) -> dict[str, Any]:
    """The coverage the assessment recorded (``completeness``) as the review leaves it (reviewed_coverage), with the
    assessment's own counts as the stored completeness records them (stored_counts: this step's request R2). Pure;
    raises UnreadableCoding for a completeness whose event coding is not of READ_CODINGS (FINAL-V2 6.5: a v1 row's @1 is
    refused before anything is read), UnreadableCounts when the counts are not recorded - readers.EventReader derives
    them for a record that does not carry them (assessment_counts) and calls reviewed_coverage."""
    read_coding(completeness)
    return reviewed_coverage(completeness, R, counted, reinstated, stored_counts(completeness), members=members,
                             label=label)


def reviewed_coverage(completeness: Mapping[str, Any], R: FactSet, counted: Sequence[coverage.Counted],
                      reinstated: Iterable[tuple[str, str]], own: Mapping[str, Any], *,
                      members: Iterable[combination.Member] = (),
                      label: Callable[[coverage.Session], str] = session_label) -> dict[str, Any]:
    """The coverage the assessment recorded (``completeness``) as the review leaves it: engine/coverage.reconcile over
    the frozen FactSet ``R`` with ``counted`` (counted_codes: the reinstated codes among them) and the procedure day of
    the counted ``members`` (combination.procedure_day: a reinstated procedural code makes the date a procedure day, as
    assess's combination does), and coverage.completeness over it, worded as the engine words it (``label``, the
    renderer's). ``reinstated``: (code, family) of the reinstated codes. The open questions, the provider's state, the
    conflicts and the unverified attributes are the assessment's own (``own``: assessment_counts' or stored_counts'),
    never written into the result unless the stored completeness records them. The second-review mark is
    coverage.unresolved_record's own. Pure; UnreadableCoding for a completeness whose event coding is not of
    READ_CODINGS (FINAL-V2 6.5; AMENDMENT-2 8.1)."""
    read_coding(completeness)
    sessions_ = coverage.sessions(R)
    day = combination.procedure_day(R, tuple(combination.ProceduralCode(member.code, member.family, member.procedural,
                                                                         member.supported) for member in members))
    found = coverage.reconcile(R, counted, procedure_day=bool(day.done), sessions_=sessions_)
    fresh = coverage.completeness(found, sessions_, open_questions=own['open_questions'],
                                  provider_ok=own['provider_ok'], conflicts=own['conflicts'], label=label,
                                  unverified=own['unverified'])
    return {**completeness, **fresh,
            'unresolved_items': coverage.unresolved_record(found.unresolved),
            'bundled': coverage.bundled_record(found.bundled),
            'not_listed': [{'service': str(session.id), 'family': session.kind.value if session.kind is not None
                            else None} for session in found.not_listed],
            'covered': {str(session): list(codes) for session, codes in found.covered.items()},
            'included_by': {str(session): list(codes)
                            for session, codes in coverage.included_by(sessions_, found.covered).items()},
            'reinstated': list(dict.fromkeys(code for code, _ in reinstated))}
