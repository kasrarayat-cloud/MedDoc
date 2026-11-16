"""Settle (docs/gemini-migration/FINAL-V2.md 1.5, 1.7, 3.1's cross-object rules, 3.2.3-3.2.6, 3.3, 3.4 and 3.6; step 3a
of 8.1; AMENDMENT-2 4.3.5 and DECISIONS D292's U3, step f3s): ``settle(read, checked, claim_set, indistinct, appraisal,
usage, appraisal_version=...)`` combines pass 1's answer, the deterministic checks, the claim set and pass 2's answer
into ONE result per fact - per act for an inherited fact - and gives the content of one EventInventory row (``Settled``:
its ``events`` and its ``verification`` report, which store.row_v2 binds to the revision, both runs and the claim list),
or ``Unhealthy`` when 3.2.6's health refuses the appraisal whole.

**What settle reads, and never does.** It reads its inputs as data: extract_read's ReadAnswer (pass 1, with the reader's
item-level findings), contract/checks.check's Checked (every other check of 3.1: geometry, consistency, the closures, the
section places and the located words, DECISIONS D206), claims.py's ClaimSet (which claim appraises which fact) with the
request's indistinct card groups, and appraise_read's ReadAppraisal (pass 2, every verdict bound to its claim's content
key). It never segments, locates, measures or reads document text (5.7 WordsNeverDecide binds this module): the one text
it carries is the revision's own slice inside a LocatedWords that geometry made and Checked holds, copied whole.

**The truth table** (3.3, ``decide``), for each fact, in this order; the first row that holds gives the result:
1. pass 1's claim is contradicted and every side's sources pass S2 and I1-I3 (the reader's shape, unit and length
   findings and geometry's location of each source); or a doubt with basis conflict names the fact; or K8 joins it (a
   supported and a negated member of one value, Checked.joined): ``contradicted``, contradicted_by_pass1 - never
   appraised, never dismissed. A contradicted claim whose side fails integrity goes on down the table (row 4: it stays a
   doubt, never appraised);
2. a doubt with basis stated or unclear names the fact: ``unknown``, doubt_stated / doubt_unclear, the claimed value kept
   (the doubt's readings stay in events.doubts for ``possibly``, 4.2) [R:HO-1][R:CO-1];
3. the slot is empty: ``unknown``, silent;
4. any check of S2, I1-I4, G1-G6, K1-K8 or L1 failed (Checked.findings, the reader's own included): ``unresolved``, its
   reasons;
5. Q1, a qualifier but approximate: ``unresolved``, qualified:<q>;
6. no claim appraises the fact - it is not in CLAIMED, or claims.py left it unclaimed (ClaimSet.unclaimed: no template,
   a partner, a control it cannot write, ...; the integration's hand-off from 2c-2: Unclaimable.CONTROL and PARTNER
   settle unappraised), or the claim it shares with another fact is bound to that fact (below; the one control two
   facts read is a session's reach and its reached_anatomy's, DECISIONS D244's R-ANAT), or a fact its result also
   rests on has no per-act claim (a restates role: the owner of the section R lies in, below; its own pair is kept
   with it): ``unresolved``, unappraised [J];
7. the event's card reads alike another's while their claimed values of the attribute differ (the request's indistinct
   groups, 3.2.3 [R:CO-7]): ``unresolved``, cards_indistinct;
8. the appraisal pair is established (3.2.3's coherence table, ``appraise``: the claim supported with no qualifier but
   approximate - a supports verdict naming another is read as qualified (DECISIONS D186), and approximate, which is
   recorded and never lowers (1.3), is not read by that demotion (DECISIONS D224) - attached yes, an evidence unit
   attached (3.2.5), and its control, when it has one, contradicted): ``supported`` or ``negated``, as pass 1's claim
   is, pass 2's approximate kept in the stored appraisal;
9. otherwise: ``unresolved``, the appraisal's reason - appraisal_missing, appraisal_qualified:<q> (for a supports
   verdict D186 demotes, each qualifier it names but approximate; for a qualified verdict, each it names, approximate
   included - D224 changes D186's demotion only; appraisal_qualified for a qualified verdict naming none, D186),
   appraisal_unclear, appraisal_contradicts (an uninformative pair, both contradicted, is counted apart),
   appraisal_detached, control_incoherent; a control left with no verdict is appraisal_missing. Pass 2's counter
   evidence is stored with the appraisal, and an unrejected control's value stays possible (4.2 [R:HO-3]).

The reasons of rows 1-5 are the row's own and every finding on the fact (hand-off 1c:R6: a fact's reasons are a set), so
a check that failed on a doubted, silent or contradicted fact is still counted; rows 6-9 give their own reason.

**An overfilled slot** (AMENDMENT-2 4.3.5; read under gemini-events@3, 4.3.1): each written fact carries the reader's
slot_overfull, a reason in none of GEOMETRY_REASONS, LITERAL_REASONS and CONSISTENCY_REASONS, so integrity's ("an
unforeseen reason fails integrity"), and row 4 makes it UNRESOLVED with no change to the table (rows 1-2 still take a
contradicted written fact with passing sides, a conflict doubt or K8, and a stated or unclear doubt, first: a written
fact is never established either way). The slot is stored as its written facts, each settled - more than one stored
fact at a slot key, which the store accepts only under gemini-inventory@3 and only when every one carries slot_overfull
(4.3.6) - and the engine reads them as the merged view (4.3.3). The inherited per-act fact of an overfilled section slot
(an act's date relation, performer or performer_person) is likewise one per-act fact per written section fact, its claim
inherited_from the section, unresolved with the same reason. Every other read of a single-valued attribute here - the
drop rule's session of an absorbing event - reads extract_read.merged's view: never a supported value, so an unlisted
entry naming a session is kept (fail-closed). Pass 2's
verdict stays with the fact it was given for whatever row settled it - a fact claims.py claimed though rows 1-5 settle it
(K8's joined members, a fact D200's object-less doubt names, which claims.py does not read yet) keeps it and is not
lifted by it - so pass 2's doubt about a filing is never discarded (3.2.3 [R:HO-3]).

**Inheritance** (1.5, 3.3). An act's effective date relation, performer and performer_person are its own slot when that
is not empty; otherwise its containing section's occasion, performer and performer_person (a statement's date relation
only: its performer is its own, when named, 3.2.1); its entry is always its anchor section's owner. The containing
section is Checked.containing's (G4's edge). Such a fact is stored PER ACT, its claim the section's with
``inherited_from`` the section: steps 1-5 read the section's fact - its findings, its doubts, its sides - shared by its
acts, together with the act's own findings on that attribute (G4, L1's per-event rule, the anchor rule) and the doubts
that name the act's own attribute (which apply to the act's fact alone); steps 6-9 read the per-act claim. An act whose
anchor is attached to no section inherits nothing: its effective fact is silent (unknown), with G4's inherit_unattached
among its reasons. The literals stored with an inherited date relation are L1's per-act ones (the section's occasion's
and the act's own date's, DECISIONS D193), else the section's. A restatement's role is stored as its own fact, and settle
never sets an entry to a value no claim appraised: the move of an entry through an established ``restates`` role (1.5
[R:SC-D]) is the engine's to read from the role (requirements' SUP.5 reads entry and the role together), so a restates
role carries the move's conditions - rows 1-5 on the owner of the section R lies in (and every doubt naming the act's
entry) beside its own, R attached to a section, that owner given as the documenting clinician - and, since no claim of
the request appraises that owner for the act (3.2.1 claims no section fact), it is never established: its pair is kept
with it and it settles unappraised until a ruling adds such a claim (the step's notes' question; 1.5 then makes
event_entry a question, never the explanation).

**The cross-object rules of 3.1** arrive as data: an invalid anchor through Checked.findings (anchor_invalid on every
fact of the event); a section's owner, occasion and performer through inheritance (steps 1-5 on the section's fact); a
session's kind through the session's own kind fact, which is its acts' family (the engine reads it there; settle copies
nothing across); every doubt to the facts it names - extract_read.ReadDoubt.named (a malformed doubt every attribute of
its objects), a doubt about an act's inherited attribute to its effective fact, and DECISIONS D200's object-less
malformed doubt to every fact of each event Checked.objectless_doubts names, or, when it names none, kept as an unlisted
doubt with no kind and no session (3.2.6 rule 4).

**The date of service** (DECISIONS D187) is one settled fact: stated is supported, with its value and sources; several is
contradicted, each candidate date an option with its own sources (row 1); not_stated is silent (row 3). Its checks are
the generic ones: integrity failed whenever any side failed, literal L1's verdict over every side (the integration's
O13).

**The stored claims** (1.7): every claim of the request, in its seeded order, with its role (``ClaimRole``: claim,
control, pair_control, completeness, completeness_control), the attribute it is about and pass 2's verdict beside its
content key [R:MO-5]. A claim several facts share (part_of and part_relation; a breadth and its excepted acts; a
segment's two places) is bound to ONE of them - the first whose value is the claim's, and none when no entry's value is
- because the store reads a claim for one fact only, and only for the fact whose value it states; the others settle
unappraised (row 6), fail-closed, though their own pair may be established (a REQUEST in the step's notes: each fact its
own claim, or the store reading a shared claim per fact). A control that a claim's content also makes a pair control is
stored in the control role. A lesion pair claim (DECISIONS D296) is stored in the claim role and its sameness control in
the control role, and ``lesion_pairs`` records each pair's outcome: supported only when the coherence table establishes
it. One control is read by two facts (DECISIONS D244's R-ANAT): 3.2.3 writes a reached_anatomy's
control in its session's reach form (claims.CONTROLS: "In session {X} the endoscope did not reach the {point at anatomy
Y}") - since DECISIONS D292's U3 the opposite of the reached_anatomy's own claim under gemini-appraisal@2 ("In session
{X} the endoscope itself reached anatomy {Y}."; @1's claim, "The furthest point in session {X} was at anatomy {Y}.",
keeps its recorded bytes) - so when the session's reach names that point from the same units, the reach's own control
and the reached_anatomy's are one claim of the request (claims.py makes one claim of one content), and that control
appraises both facts (SHARED_CONTROL): each fact reads its own claim with it and each pair goes through the coherence
table. The share is pinned to the reach's own sentence (SHARED_FORM, the form the reach's control rule renders): a
control of any other form is never read by two facts, so a reached_anatomy control reworded away from the reach's
sentence stops sharing (fail-closed) instead of being read twice. It is
STORED once, in the reach's appraisal - the attribute 3.2.3 writes it in - since the store reads a claim for one fact
only (store._v2_verdicts_bound): the reached_anatomy borrows it (``borrowing``) and stores its own claim and verdict
with no control, its result and reasons those of the pair it read, while the claim list keeps the control with pass
2's verdict on it. One verdict on it is read once (``pair_read``): the reached_anatomy's established pair counts only
beside the reach's established pair, since 3.2.3's first row is the only one that reads the control's rejection as one
(contradicted beside its claim it is uninformative; beside an unclear, qualified, detached or missing verdict on the
claim it is not read); otherwise the reached_anatomy settles control_incoherent - the fail-closed reading, a question in
the step's notes. Any other control read twice, a third reader, a reader in another session, or a control that is also
a claim, a pair control or a completeness claim keeps the rule above.

**Unlisted statements** (3.2.6 [R:SC-A][R:HO-6]). An entry is dropped only when an event whose valid anchor or valid
restatement includes one of its units has the same nature (act: a supported performed status; denial: a negated
performed one, 1.4's "not done"; doubt: a doubt of pass 1 names the event - a planned or attempted event is neither an
act nor a denial, the fail-closed reading), a compatible kind (equal, or one an umbrella of the other,
engine/catalogue.UMBRELLAS) and, when pass 2 names a session card, that session (an entry naming an unknown session card
is kept). An anchor I3 failed absorbs nothing, nor does a restatement G6 ignores (Checked.restatements). An event whose
supported kind is no Kind - S2's empty value on a supported fact, an item-level finding with which 1.8 keeps the answer
(shape_inconsistent) - has no compatible kind, so it absorbs nothing (DECISIONS D229: fail-closed, never a raise).
Every other entry is kept and stored; every dropped entry is reported with the event that absorbed it. The units of an
object-less doubt kept as an unlisted doubt (D200) are the ones the segmentation has (an unknown unit id is not
stored).

**Health** (3.2.6 [R:HO-4]), measured before anything is settled, over the request and pass 2's answer alone:
control acceptance - the controls not rejected (any verdict but contradicts, or none) over the claim/control pairs
(pair controls excluded: hand-off 2c#12), refused above CONTROL_ACCEPTANCE_REFUSED_ABOVE with at least
CONTROL_ACCEPTANCE_AT_LEAST pairs (a yes-sayer); establishment - the non-control claims established over all of them,
refused below ESTABLISHMENT_REFUSED_BELOW with at least ESTABLISHMENT_AT_LEAST claims (a no-sayer, a detached or
degenerate answer); completeness - the claims with no verdict over all claims of the request, refused above
COMPLETENESS_REFUSED_ABOVE. Each threshold is an exact fraction, compared with integers. The thresholds are pinned by
label (health_document; HEALTH_THRESHOLDS_SHA256 under gemini-appraisal@1, HEALTH_THRESHOLDS_SHA256_V3 under @2, in
studio/interpretation/__init__.py, 2.5 and AMENDMENT-2 8.2): no appraisal is settled under thresholds nobody pinned
(check_pin, with the appraisal label the caller names). A refused appraisal is never a row (7.5): settle returns
Unhealthy, which the stage records on the appraisal run.

**The report** (1.7 verification, closed records: hand-off 1d#2): counts per attribute and result, the reasons counted,
each doubt and the facts it was applied to, the health measures, the pairs' coherence, the unlisted statements kept and
dropped, and both runs' usage (integer token counts only, P9). store.row_v2 completes it with the bindings. Its
records, the stored claim's and ClaimRole are contract/types' (DECISIONS D229), named here too, and the store closes
the stored report to them.

**What settle never does** (3.4, 3.5, 3.6): it never creates, sets or changes a value, never lifts a fact a check, a
doubt or a qualifier demoted, never lets pass 2 resolve a doubt or dismiss a contradiction, and never decides what a
word means. It imports no text module (segment, geometry, fold, date_literals), no regular-expression module and no v1
module, holds no word list (NoWordLists) and calls no string method; the only membership tests on strings are in closed
vocabularies of its own - the enumerations' values (P9's filter of a doubt's readings; an event's kind looked up in
KINDS) and claims.py's template ids (a control's attribute) - never against document words.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from typing import Any

from studio import interpretation
from studio.interpretation.contract import claims, jsonschema
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract.appraise_read import ReadAppraisal, ReadUnlisted, ReadVerdict, UnlistedFinding
from studio.interpretation.contract.extract_read import (OBJECT_LETTERS, Cited, DateOfService, FactKey, ReadAnswer,
                                                         ReadCitation, ReadFact, ReadMember, is_id, iso_date, merged,
                                                         partial_date)
from studio.interpretation.contract.types import (Appraisal, Attached, Attribute, Checked, Checks, CheckStatus,
                                                  ControlVerdict, DateState, Doubt, DoubtAbout, DoubtBasis, Fact,
                                                  FactState, Kind, Link, Owner, Qualifier, Qualifier2, Reason,
                                                  RestatementRole, Result, SettledClaim, SettledFact, SettledOption,
                                                  SettledSource, Source, Status, StoredLiteral, Unlisted, UnlistedWhat,
                                                  Verdict, VerdictValue)
from studio.interpretation.engine import catalogue
# settle's stored records and the closed lists inside them live in contract/types (DECISIONS D229: w34 O4 and
# O5, hand-offs 1d#2 and 1d#6), where the store reads them; each is named here as well, so settle.<name> is
# the very same object it was
from studio.interpretation.contract.types import ClaimRole as ClaimRole
from studio.interpretation.contract.types import Coherence as Coherence
from studio.interpretation.contract.types import DoubtApplied as DoubtApplied
from studio.interpretation.contract.types import Dropped as Dropped
from studio.interpretation.contract.types import Health as Health
from studio.interpretation.contract.types import HealthRefusal as HealthRefusal
from studio.interpretation.contract.types import PairOutcome as PairOutcome
from studio.interpretation.contract.types import Report as Report
from studio.interpretation.contract.types import StoredClaim as StoredClaim
from studio.interpretation.contract.types import StoredCompleteness as StoredCompleteness
from studio.interpretation.contract.types import StoredVerdict as StoredVerdict
from studio.interpretation.contract.types import UnlistedReport as UnlistedReport
from studio.interpretation.contract.types import Usage as Usage
from studio.interpretation.contract.types import Usages as Usages

Family = xs.Family
A = Attribute

# --- the closed list settle keeps (ClaimRole, PairOutcome and HealthRefusal are contract/types', DECISIONS D229) ----


@unique
class UsageCount(Enum):
    """The token counts a run's usage records, by the key the provider's usageMetadata gives each (report.USAGE_KEYS):
    the report stores these integers only, never a string (P9)."""
    PROMPT = 'promptTokenCount'
    CANDIDATES = 'candidatesTokenCount'
    THOUGHTS = 'thoughtsTokenCount'
    TOTAL = 'totalTokenCount'
    CACHED = 'cachedContentTokenCount'
    TOOL_USE_PROMPT = 'toolUsePromptTokenCount'


# --- the health thresholds (3.2.6 [R:HO-4]; pinned: 2.5) -------------------------------------------------------------

# Each a fraction (numerator, denominator), compared with integers. 3.2.6's values, which D3's distributions may move
# (each move a DECISIONS entry and a recomputed pin, D202).
CONTROL_ACCEPTANCE_REFUSED_ABOVE = (1, 2)
CONTROL_ACCEPTANCE_AT_LEAST = 4
ESTABLISHMENT_REFUSED_BELOW = (1, 2)
ESTABLISHMENT_AT_LEAST = 4
COMPLETENESS_REFUSED_ABOVE = (1, 10)


def health_document() -> dict[str, object]:
    """The health thresholds' canonical form, whose sha256 the integration owner pins (HEALTH_THRESHOLDS_SHA256)."""
    return {'control_acceptance': {'refused_above': list(CONTROL_ACCEPTANCE_REFUSED_ABOVE),
                                   'at_least_pairs': CONTROL_ACCEPTANCE_AT_LEAST,
                                   'not_rejected': 'any verdict but contradicts, or none',
                                   'over': 'claim and control pairs, pair controls excluded'},
            'establishment': {'refused_below': list(ESTABLISHMENT_REFUSED_BELOW),
                              'at_least_claims': ESTABLISHMENT_AT_LEAST,
                              'over': 'the non-control claims, a claim established when every pair it is in is'},
            'completeness': {'refused_above': list(COMPLETENESS_REFUSED_ABOVE),
                             'over': 'every claim of the request, a missing or repeated verdict having none'}}


def health_pins() -> dict[str, str]:
    """The health thresholds' pin under each appraisal label settle reads (AMENDMENT-2 8.1-8.2 [R:replay-R1]): one pin
    per label, since gemini-appraisal@1 has recordings (D202); read from studio/interpretation/__init__.py when
    asked."""
    return {interpretation.APPRAISAL_VERSION: interpretation.HEALTH_THRESHOLDS_SHA256,
            interpretation.APPRAISAL_VERSION_V3: interpretation.HEALTH_THRESHOLDS_SHA256_V3}


def check_pin(version: str = interpretation.APPRAISAL_VERSION) -> None:
    """RuntimeError unless the health thresholds are byte for byte what the appraisal label ``version`` pins (2.5; the
    read.check_pin pattern; AMENDMENT-2 8.1: each label checks its own pin). An empty pin (the placeholder until the
    integration owner writes it) is refused too: no appraisal is settled under thresholds nobody pinned; and so is a
    label settle does not read. Until the first recording under the label a changed threshold needs only its pin
    recomputed (DECISIONS D202)."""
    pins = health_pins()
    if version not in pins:
        raise RuntimeError('Settle reads appraisals of gemini-appraisal@1 and gemini-appraisal@2 only; no other label '
                           'is settled.')
    pinned = pins[version]
    if not pinned:
        raise RuntimeError(f'The health thresholds of {version} have no pin yet; no appraisal is settled under them.')
    if jsonschema.sha256_of(health_document()) != pinned:
        raise RuntimeError(f'The health thresholds no longer match the {version} pin; a changed threshold needs its pin '
                           'recomputed before the first recording under the label (DECISIONS D202).')


# --- the tables settle reads (enumeration members only) ----------------------------------------------------------------

_R = Reason
# The check each finding belongs to (1.7 checks): geometry (G1-G6), the date literal (L1), consistency (K1-K8), Q1;
# every other finding is integrity's (S2, I1-I4 and the anchor rule) - so an unforeseen reason fails integrity.
GEOMETRY_REASONS: frozenset[Reason] = frozenset({
    _R.GEOMETRY_STATEMENT, _R.GEOMETRY_SECTION, _R.GEOMETRY_FRAME, _R.GEOMETRY_PLACING, _R.GEOMETRY_DOCUMENT_FRAME,
    _R.GEOMETRY_ANTECEDENT, _R.GEOMETRY_OTHER_STATEMENT, _R.SECTION_ORDER, _R.SECTION_START_UNLOCATED,
    _R.TARGET_DETACHED, _R.INHERIT_UNATTACHED, _R.EXTENT_INFERRED})
LITERAL_REASONS: frozenset[Reason] = frozenset({_R.LITERAL_MISMATCH, _R.LITERAL_UNCHECKED})
CONSISTENCY_REASONS: frozenset[Reason] = frozenset({
    _R.STRUCTURE_SCOPE, _R.STRUCTURE_YIELD, _R.STRUCTURE_ACCESS_OUTCOME, _R.STRUCTURE_CAUSE, _R.STRUCTURE_PART_OF,
    _R.STRUCTURE_ENDOSCOPIC, _R.STRUCTURE_VISIT, _R.STRUCTURE_OTHER_CLASS, _R.STRUCTURE_STATUS_TIME,
    _R.STRUCTURE_EXCEPTIVE, _R.STRUCTURE_LISTED_TARGETS, _R.STRUCTURE_SINGLE_TARGET, _R.STRUCTURE_SEGMENT,
    _R.STRUCTURE_UMBRELLA, _R.SESSION_INCONSISTENT, _R.SESSION_CONFLICT, _R.SESSION_UNREACHABLE, _R.ANATOMY_CONFLICT,
    _R.PERSON_CONFLICT, _R.INSTRUMENT_CONFLICT, _R.FRAME_ROLE})
QUALIFIED_REASONS: frozenset[Reason] = frozenset({
    _R.QUALIFIED_HEDGED, _R.QUALIFIED_CONDITIONAL, _R.QUALIFIED_REPORTED, _R.QUALIFIED_PARTIAL,
    _R.QUALIFIED_NAMED_ONLY, _R.QUALIFIED_RESTATEMENT_ONLY, _R.QUALIFIED_REFERENCE_ONLY})
# What fails a contradicted claim's side (3.3 row 1): its shape (S2) and its sources' units (I1, I3's bound), as the reader
# gives them; geometry's location of each source (I2, I3) is read from Checked.citations.
SIDE_REASONS: frozenset[Reason] = frozenset({_R.SHAPE_INCONSISTENT, _R.UNIT_UNKNOWN, _R.SOURCE_TOO_LONG})
# Row 2's reason for each doubt basis.
DOUBT_REASONS: Mapping[DoubtBasis, Reason] = MappingProxyType({DoubtBasis.STATED: _R.DOUBT_STATED,
                                                                DoubtBasis.UNCLEAR: _R.DOUBT_UNCLEAR})
# Row 9's appraisal_qualified:<q> for each qualifier pass 2 names (DECISIONS D186): the member of its value, looked up
# once, so a qualifier the closed list does not hold fails the import rather than a settle.
APPRAISAL_QUALIFIED: Mapping[Qualifier2, Reason] = MappingProxyType({
    qualifier: Reason(f'{Reason.APPRAISAL_QUALIFIED.value}:{qualifier.value}') for qualifier in Qualifier2})
# The qualifiers a supports verdict may name and stay a support (DECISIONS D224: pass 2's approximate never lowers a
# supported claim; 1.3: approximate is recorded and never lowers): D186's demotion reads every other qualifier.
NEVER_LOWERS: frozenset[Qualifier2] = frozenset({Qualifier2.APPROXIMATE})
# Each Kind by its value, as absorbing() reads an event's kind: a supported kind whose value is no Kind (S2's empty
# value on a supported fact, an item-level finding: 1.8 keeps the answer) has none, and so absorbs nothing (DECISIONS
# D229).
KINDS: Mapping[str, Kind] = MappingProxyType({member.value: member for member in Kind})
# The section attribute an act inherits each of its effective facts from (1.5): its date relation from the occasion.
INHERITED_FROM: Mapping[Attribute, Attribute] = MappingProxyType({
    A.DATE_RELATION: A.OCCASION, A.PERFORMER: A.PERFORMER, A.PERFORMER_PERSON: A.PERFORMER_PERSON, A.ENTRY: A.OWNER})
# Which effective facts inherit when the act's own slot is empty (1.5; 3.2.1: a statement's performer is its own).
ACT_INHERITED: tuple[Attribute, ...] = (A.DATE_RELATION, A.PERFORMER, A.PERFORMER_PERSON)
STATEMENT_INHERITED: tuple[Attribute, ...] = (A.DATE_RELATION,)
# The attribute 3.2.3 writes a fact's control in, where it is not the fact's own (claims.CONTROLS' as_attribute; equal
# to store.CONTROL_ATTRIBUTES, which a test pins).
CONTROL_ATTRIBUTES: Mapping[Attribute, Attribute] = MappingProxyType({
    rule.attribute: rule.as_attribute for rule in claims.CONTROLS
    if rule.as_attribute is not None and rule.as_attribute is not rule.attribute})
# The two facts of a session one contrary control appraises together (DECISIONS D244's R-ANAT; the module's docstring):
# reached_anatomy, and the attribute 3.2.3 writes its control in (CONTROL_ATTRIBUTES: the reach). Read from the
# CONTROLS table, so a reached_anatomy control written in another attribute moves it, and an attribute this ruling does
# not name never shares (a KeyError fails the import, never a settle).
SHARED_CONTROL: tuple[Family, frozenset[Attribute]] = (
    Family.SESSION, frozenset({A.REACHED_ANATOMY, CONTROL_ATTRIBUTES[A.REACHED_ANATOMY]}))
# The one form the shared control may take (DECISIONS D292's U3, the share re-pinned): the reach's own control sentence,
# the form the reach's control rule renders ("In session {X} the endoscope did not reach the {point}." - CONTROLS'
# reached row: its own value, in the negated state). A reached_anatomy control in any other form is never shared,
# whatever its content, so a rewording of that control can only stop the share (fail-closed).
SHARED_FORM: str = claims.FORMS[(claims.ObjectClass.SESSION, A.REACHED, FactState.NEGATED)].value
# The attribute a claim's template is the form of, for a control no stored fact names (claims.FORMS, the first row of
# each template; and 3.2.3's own forms).
TEMPLATE_ATTRIBUTES: Mapping[str, Attribute] = MappingProxyType({
    **{template.value: attribute for (_class, attribute, _state), template in reversed(list(claims.FORMS.items()))},
    claims.TemplateId.STMT_DONE.value: A.STATUS, claims.TemplateId.ACT_RESTATES_SUMMARY.value: A.RESTATEMENTS_ROLE,
    claims.TemplateId.SESSION_ALL_STATIONS.value: A.STATIONS, claims.TemplateId.SESSION_SOME_STATIONS.value: A.STATIONS,
    claims.TemplateId.STMT_BREADTH_ALL.value: A.SCOPE_BREADTH,
    claims.TemplateId.STMT_BREADTH_EXCEPTIVE.value: A.SCOPE_BREADTH})
# Every value pass 1's facts may hold that is an enumeration value (1.4): a doubt's reading is stored only if it is one,
# an id or an ISO date (P9: no model string is stored).
_ENUMERATION_VALUES: frozenset[str] = frozenset(
    member.value for family in Family for field in xs.ATTRIBUTES[family] if field.values is not None
    for member in field.values)
_ESTABLISHED = frozenset({FactState.SUPPORTED, FactState.NEGATED})


# --- how settle reads a run's usage (its records are contract/types', DECISIONS D229) ----------------------------------


def usage_of(metadata: Mapping[str, object]) -> Usage:
    """A run's usage (ProviderRun.usage: usageMetadata as reported) as its integer counts; a count that is not a whole
    number of at least 0 reads as 0 (nothing but integers is stored, P9)."""
    def count(which: UsageCount) -> int:
        value = metadata.get(which.value)
        return value if type(value) is int and value >= 0 else 0

    return Usage(prompt=count(UsageCount.PROMPT), candidates=count(UsageCount.CANDIDATES),
                 thoughts=count(UsageCount.THOUGHTS), total=count(UsageCount.TOTAL), cached=count(UsageCount.CACHED),
                 tool_use_prompt=count(UsageCount.TOOL_USE_PROMPT))


@dataclass(frozen=True)
class Settled:
    """A settled inventory: events, the content of EventInventory.events (1.7: units, encounter, people, sections,
    sessions, anatomy, lesions, events, doubts, claims, unlisted, and DECISIONS D296's lesion_pairs - which store.row_v2
    keeps at the @3 pair only; contract/types records, Enum members and these records inside, which store.row_v2
    converts), and verification, settle's report."""
    events: Mapping[str, object]
    verification: Report


@dataclass(frozen=True)
class Unhealthy:
    """An appraisal 3.2.6's health refused whole: no row is written (7.5); the stage records health on the appraisal
    run."""
    health: Health


# --- the truth table (3.3) and the coherence table (3.2.3) --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Case:
    """One fact's inputs to the truth table (``decide``): state, pass 1's claim (None: a silent slot); sides, for a
    contradicted claim, whether every side's sources pass S2 and I1-I3; doubts, the bases of the doubts naming it;
    joined, whether K8 joins it; findings, every check finding on it (Q1's included); claimed, whether a claim appraises
    it - and every fact its result also rests on (a restates role: the owner of R's section, which no claim appraises
    today); indistinct, whether row 7 applies; pair and pair_reasons, its appraisal pair's outcome and reasons
    (``appraise``), None when it is not claimed."""
    state: FactState | None
    sides: bool
    doubts: frozenset[DoubtBasis]
    joined: bool
    findings: tuple[Reason, ...]
    claimed: bool
    indistinct: bool
    pair: PairOutcome | None
    pair_reasons: tuple[Reason, ...]


def ordered(reasons: Iterable[Reason]) -> tuple[Reason, ...]:
    """``reasons`` once each, in the closed list's order (hand-off 1c:R6)."""
    found = set(reasons)
    return tuple(reason for reason in Reason if reason in found)


def row(case: Case) -> int:
    """The row of 3.3's table that settles one fact (1-9): the first that holds (the module's docstring). Rows 1-5 are
    decided before the appraisal, which only rows 6-9 read: no verdict changes a fact settled there."""
    found = set(case.findings)
    if (case.state is FactState.CONTRADICTED and case.sides) or DoubtBasis.CONFLICT in case.doubts or case.joined:
        return 1
    if any(basis in DOUBT_REASONS for basis in case.doubts):
        return 2
    if case.state is None:
        return 3
    if found - QUALIFIED_REASONS or case.state is FactState.CONTRADICTED:
        return 4  # a contradicted claim that is not row 1 failed a side's integrity: it is never appraised
    if found:
        return 5
    if not case.claimed or case.pair is None:
        return 6
    if case.indistinct:
        return 7
    return 8 if case.pair is PairOutcome.ESTABLISHED else 9


def decide(case: Case) -> tuple[Result, tuple[Reason, ...]]:
    """The result and reasons of one fact (3.3's table, the module's docstring): those of its ``row``."""
    found = set(case.findings)
    which = row(case)
    if which == 1:
        return Result.CONTRADICTED, ordered({Reason.CONTRADICTED_BY_PASS1} | found)
    if which == 2:
        return Result.UNKNOWN, ordered({DOUBT_REASONS[basis] for basis in case.doubts if basis in DOUBT_REASONS}
                                       | found)
    if which == 3:
        return Result.UNKNOWN, ordered({Reason.SILENT} | found)
    if which in (4, 5):
        return Result.UNRESOLVED, ordered(found or {Reason.SHAPE_INCONSISTENT})
    if which == 6:
        return Result.UNRESOLVED, (Reason.UNAPPRAISED,)
    if which == 7:
        return Result.UNRESOLVED, (Reason.CARDS_INDISTINCT,)
    if which == 8:
        return (Result.SUPPORTED if case.state is FactState.SUPPORTED else Result.NEGATED), ()
    return Result.UNRESOLVED, case.pair_reasons or (Reason.APPRAISAL_MISSING,)


def appraise(verdict: Verdict | None, attached_evidence: bool, controlled: bool,
             control: VerdictValue | None) -> tuple[PairOutcome, tuple[Reason, ...]]:
    """3.2.3's coherence table for one claim and its control: ``verdict``, pass 2's on the claim (None: none read);
    ``attached_evidence``, 3.2.5's check (appraise_read.ReadVerdict.attached_evidence); ``controlled``, whether the
    claim has a control; ``control``, pass 2's verdict on the control (None: none read).

    A supports verdict naming a qualifier that lowers - any but those of NEVER_LOWERS - is read as qualified (DECISIONS
    D186), its reasons appraisal_qualified:<q> for each qualifier that lowers. Approximate never lowers a supports
    verdict (1.3; DECISIONS D224): it is not read here, so the pair goes on through the table and the qualifier stays
    recorded in the verdict the row stores. A qualified verdict is pass 2's own and D224 leaves it as 3.2.3 writes it:
    appraisal_qualified:<q> for every qualifier it names, approximate included, appraisal_qualified when it names
    none."""
    if verdict is None:
        return PairOutcome.MISSING, (Reason.APPRAISAL_MISSING,)
    value = verdict.verdict
    lowering = tuple(qualifier for qualifier in verdict.qualifiers if qualifier not in NEVER_LOWERS)
    if value is VerdictValue.SUPPORTS and lowering:
        return PairOutcome.QUALIFIED, ordered(APPRAISAL_QUALIFIED[qualifier] for qualifier in lowering)
    if value is VerdictValue.QUALIFIED:
        named = ordered(APPRAISAL_QUALIFIED[qualifier] for qualifier in verdict.qualifiers)
        return PairOutcome.QUALIFIED, named or (Reason.APPRAISAL_QUALIFIED,)
    if value is VerdictValue.UNCLEAR:
        return PairOutcome.UNCLEAR, (Reason.APPRAISAL_UNCLEAR,)
    if value is VerdictValue.CONTRADICTS:
        both = controlled and control is VerdictValue.CONTRADICTS
        return (PairOutcome.UNINFORMATIVE if both else PairOutcome.CONTRADICTED), (Reason.APPRAISAL_CONTRADICTS,)
    if verdict.attached is not Attached.YES or not attached_evidence:
        return PairOutcome.DETACHED, (Reason.APPRAISAL_DETACHED,)
    if not controlled or control is VerdictValue.CONTRADICTS:
        return PairOutcome.ESTABLISHED, ()
    if control is None:
        return PairOutcome.CONTROL_MISSING, (Reason.APPRAISAL_MISSING,)
    return PairOutcome.INCOHERENT, (Reason.CONTROL_INCOHERENT,)


# --- the appraisal: verdicts bound to their claims, pairs, health -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Pair:
    """One claim with its control (None: uncontrolled), and the pair's outcome and reasons."""
    claim: str
    control: str | None
    outcome: PairOutcome
    reasons: tuple[Reason, ...]


def verdicts_of(claim_set: claims.ClaimSet, appraisal: ReadAppraisal) -> dict[str, ReadVerdict | None]:
    """Each claim's read verdict, by claim id, bound by content key [R:MO-5]: None for a claim whose read verdict names
    another content key (a verdict is never read against a different claim). ValueError when the appraisal was read
    against another request (its verdicts are not the claim set's claims, in order)."""
    if tuple(item.claim for item in appraisal.verdicts) != tuple(claim.id for claim in claim_set.claims):
        raise ValueError('The appraisal was read against another request than this claim set.')
    found: dict[str, ReadVerdict | None] = {}
    for claim, read in zip(claim_set.claims, appraisal.verdicts):
        found[claim.id] = read if read.content == claim.content else None
    return found


def _verdict(verdicts: Mapping[str, ReadVerdict | None], claim_id: str) -> Verdict | None:
    read = verdicts.get(claim_id)
    return None if read is None else read.verdict


def pairs_of(claim_set: claims.ClaimSet, verdicts: Mapping[str, ReadVerdict | None]) -> tuple[Pair, ...]:
    """Every distinct claim/control pair of the request - each appraised fact's claim with its control or none, and
    each completeness claim with its control - with its outcome, in the claim set's order."""
    wanted: list[tuple[str, str | None]] = []
    for item in claim_set.appraised:
        if (item.claim, item.control) not in wanted:
            wanted.append((item.claim, item.control))
    for complete in claim_set.completeness:
        if (complete.claim, complete.control) not in wanted:
            wanted.append((complete.claim, complete.control))
    found = []
    for claim_id, control_id in wanted:
        read = verdicts.get(claim_id)
        control = _verdict(verdicts, control_id) if control_id is not None else None
        outcome, reasons = appraise(_verdict(verdicts, claim_id), read is not None and read.attached_evidence,
                                    control_id is not None, None if control is None else control.verdict)
        found.append(Pair(claim_id, control_id, outcome, reasons))
    return tuple(found)


def measure_health(claim_set: claims.ClaimSet, verdicts: Mapping[str, ReadVerdict | None],
                   pairs: Sequence[Pair]) -> Health:
    """3.2.6's three measures over the request and pass 2's answer (the module's docstring), and the refusals they
    give."""
    controlled = [pair for pair in pairs if pair.control is not None]
    not_rejected = 0
    for pair in controlled:
        control = _verdict(verdicts, pair.control) if pair.control is not None else None
        if control is None or control.verdict is not VerdictValue.CONTRADICTS:
            not_rejected += 1
    real: dict[str, bool] = {}
    for pair in pairs:
        real[pair.claim] = real.get(pair.claim, True) and pair.outcome is PairOutcome.ESTABLISHED
    established = sum(1 for value in real.values() if value)
    missing = sum(1 for claim in claim_set.claims if _verdict(verdicts, claim.id) is None)
    total = len(claim_set.claims)
    refused: list[HealthRefusal] = []
    above, below = CONTROL_ACCEPTANCE_REFUSED_ABOVE, ESTABLISHMENT_REFUSED_BELOW
    if len(controlled) >= CONTROL_ACCEPTANCE_AT_LEAST and not_rejected * above[1] > above[0] * len(controlled):
        refused.append(HealthRefusal.CONTROL_ACCEPTANCE)
    if len(real) >= ESTABLISHMENT_AT_LEAST and established * below[1] < below[0] * len(real):
        refused.append(HealthRefusal.ESTABLISHMENT)
    if total and missing * COMPLETENESS_REFUSED_ABOVE[1] > COMPLETENESS_REFUSED_ABOVE[0] * total:
        refused.append(HealthRefusal.COMPLETENESS)
    return Health(pairs=len(controlled), not_rejected=not_rejected, claims=len(real), established=established,
                  verdicts=total, missing=missing, refused=tuple(refused))


# --- settling -------------------------------------------------------------------------------------------------------------


def settle(read: ReadAnswer, checked: Checked[FactKey], claim_set: claims.ClaimSet,
           indistinct: Sequence[Sequence[str]], appraisal: ReadAppraisal, usage: Usages, *,
           appraisal_version: str = interpretation.APPRAISAL_VERSION) -> Settled | Unhealthy:
    """The settled inventory of one revision (the module's docstring): ``read``, pass 1's answer as extract_read read
    it; ``checked``, contract/checks.check of the same revision and answer; ``claim_set`` and ``indistinct``, the
    request's (appraise_prompt.Request.claim_set and .indistinct); ``appraisal``, pass 2's answer to that request as
    appraise_read read it; ``usage``, both runs' token counts; ``appraisal_version``, the label the appraisal was asked
    under (gemini-appraisal@1 by default; the Fable path names gemini-appraisal@2, AMENDMENT-2 8.1), whose health
    thresholds' pin is checked. Unhealthy when 3.2.6's health refuses the appraisal. Pure: equal arguments give an
    equal result in every process. RuntimeError when the health thresholds are not pinned under the label
    (check_pin); ValueError when the inputs are not of one revision and one request."""
    check_pin(appraisal_version)
    if read.unit_count != len(checked.units):
        raise ValueError('The checks were run on another segmentation than the answer was read against.')
    verdicts = verdicts_of(claim_set, appraisal)
    pairs = pairs_of(claim_set, verdicts)
    health = measure_health(claim_set, verdicts, pairs)
    if health.refused:
        return Unhealthy(health)
    return _Settler(read, checked, claim_set, indistinct, appraisal, verdicts, pairs).run(health, usage)


def _put(record: dict[str, object], path: Sequence[str], value: object) -> None:
    """``value`` at ``path`` (an attribute's path in its object, 1.4) of ``record``, its groups made as needed."""
    node = record
    for part in path[:-1]:
        inner = node.setdefault(part, {})
        assert isinstance(inner, dict)
        node = inner
    node[path[-1]] = value


def _is_value(value: str) -> bool:
    """Whether ``value`` is a value a fact may hold - an enumeration value, an object's id or an ISO date - and so may
    be stored (P9: never a model string)."""
    return value in _ENUMERATION_VALUES or is_id(value, OBJECT_LETTERS) or iso_date(value) or partial_date(value)


_SILENT = SettledClaim(state=None, value='', qualifiers=(), options=(), inherited_from=None)


class _Settler:
    """One settle: the answer, the checks, the claims and the verdicts, indexed; the facts as they are settled."""

    def __init__(self, read: ReadAnswer, checked: Checked[FactKey], claim_set: claims.ClaimSet,
                 indistinct: Sequence[Sequence[str]], appraisal: ReadAppraisal,
                 verdicts: Mapping[str, ReadVerdict | None], pairs: Sequence[Pair]) -> None:
        self.read, self.checked, self.claim_set, self.appraisal = read, checked, claim_set, appraisal
        self.raw: Mapping[str, Any] = read.answer
        self.verdicts = verdicts
        self.pairs = {(pair.claim, pair.control): pair for pair in pairs}
        self.pair_list = tuple(pairs)
        self.facts: dict[tuple[xs.Family, str, Attribute], list[ReadFact]] = {}
        for item in read.facts:
            self.facts.setdefault((item.key.family, item.key.object, item.key.attribute), []).append(item)
        self.members: dict[tuple[str, Attribute], list[ReadMember]] = {}
        for member in read.members:
            self.members.setdefault((member.key.object, member.key.attribute), []).append(member)
        self.citations: dict[tuple[xs.Family, str, Cited, int], ReadCitation] = {
            (citation.family, citation.object, citation.cited, citation.index): citation for citation in read.citations}
        self.claims = {claim.id: claim for claim in claim_set.claims}
        self.joined = {key for supported, negated in checked.joined for key in (*supported, *negated)}
        self.sections = {place.id: place for place in checked.sections}
        self.doubting: dict[tuple[xs.Family, str, Attribute], list[int]] = {}
        for doubt in read.doubts:
            for family, name in doubt.objects:
                for attribute in doubt.named(family):
                    self.doubting.setdefault((family, name, attribute), []).append(doubt.index)
        for index, events in checked.objectless_doubts.items():
            for name in events:
                for attribute in xs.attributes(Family.EVENT):
                    self.doubting.setdefault((Family.EVENT, name, attribute), []).append(index)
        self.bound, self.partners = self.binding()
        self.borrowers = self.borrowing()
        self.indistinct = self.indistinct_keys(indistinct)
        self.counted: list[tuple[Attribute, SettledFact]] = []
        self.applied: dict[int, int] = {}

    # -- which fact reads which claim --

    def binding(self) -> tuple[dict[FactKey, claims.Appraised], set[FactKey]]:
        """Each appraised fact bound to its claim, and the facts that share a claim another fact reads (the module's
        docstring): one fact per claim, the first whose value is the claim's, and no control read twice but the one
        SHARED_CONTROL names (``shares``). A claim whose value is no entry's own (a partner rendered as a fact that is
        not itself claimed) is read by none of them: the store reads a verdict only for the fact whose value its claim
        states (store._v2_verdicts_bound), so binding it to another would make the row unstorable."""
        groups: dict[str, list[claims.Appraised]] = {}
        for item in self.claim_set.appraised:
            groups.setdefault(item.claim, []).append(item)
        bound: dict[FactKey, claims.Appraised] = {}
        partners: set[FactKey] = set()
        read: set[str] = set()
        readers: dict[str, list[FactKey]] = {}  # each control read, with the facts that read it as their control
        for claim_id, items in groups.items():
            stored = self.claims.get(claim_id)
            chosen = next((item for item in items if stored is not None and item.value == stored.value), None)
            if (stored is None or chosen is None or claim_id in read
                    or (chosen.control is not None and chosen.control in read
                        and not self.shares(chosen.control, readers.get(chosen.control, []), chosen.key))):
                partners.update(item.key for item in items)
                continue
            bound[chosen.key] = chosen
            read.add(claim_id)
            if chosen.control is not None:
                read.add(chosen.control)
                readers.setdefault(chosen.control, []).append(chosen.key)
            partners.update(item.key for item in items if item is not chosen)
        return bound, partners

    def shares(self, control: str, readers: Sequence[FactKey], key: FactKey) -> bool:
        """Whether the fact at ``key`` may read ``control`` as its contrary control though ``readers`` already read it
        (DECISIONS D244's R-ANAT; the module's docstring): only when exactly one fact read it before, as its control,
        and the two are one session's SHARED_CONTROL facts - its reach and its reached_anatomy - and the control is
        the reach's own sentence (SHARED_FORM, D292's U3) and only ever a contrary control of the request (no fact's
        claim, no pair control, no completeness claim or control: those keep one reader each)."""
        family, attributes = SHARED_CONTROL
        shared = self.claims.get(control)
        if len(readers) != 1 or shared is None or shared.template != SHARED_FORM:
            return False
        first = readers[0]
        if not (first.family is family and key.family is family and first.object == key.object
                and {first.attribute, key.attribute} == attributes):
            return False
        return not (any(item.claim == control for item in self.claim_set.appraised)
                    or any(pair.claim == control for pair in self.claim_set.pair_controls)
                    or any(control in (complete.claim, complete.control) for complete in self.claim_set.completeness))

    def borrowing(self) -> dict[FactKey, FactKey]:
        """Each bound fact that reads the control another bound fact reads (``shares`` lets in only a session's reach
        and its reached_anatomy), with that other fact: the BORROWER is the one whose control 3.2.3 writes in the
        other's attribute (CONTROL_ATTRIBUTES: reached_anatomy -> reached), so the control is stored with the fact whose
        own form it is, and the borrower's appraisal names no control (the module's docstring: the store reads a claim
        for one fact only). Computed from the binding alone, so the claim set's order changes nothing."""
        readers: dict[str, list[FactKey]] = {}
        for key, item in self.bound.items():
            if item.control is not None:
                readers.setdefault(item.control, []).append(key)
        found: dict[FactKey, FactKey] = {}
        for keys in readers.values():
            if len(keys) != 2:
                continue
            for key, other in ((keys[0], keys[1]), (keys[1], keys[0])):
                if CONTROL_ATTRIBUTES.get(key.attribute) is other.attribute:
                    found[key] = other
        return found

    def pair_read(self, item: claims.Appraised, pair: Pair) -> tuple[PairOutcome, tuple[Reason, ...]]:
        """The outcome and reasons a bound fact reads from its pair (rows 8 and 9): the pair's own; but a borrower's
        established pair counts only beside its lender's established pair - one verdict on the shared control is read
        once, and 3.2.3's first row is the only one that reads its rejection as one - and otherwise the borrower reads
        control_incoherent (the module's docstring; the fail-closed reading, a question in the step's notes)."""
        lender = self.borrowers.get(item.key)
        if lender is None or pair.outcome is not PairOutcome.ESTABLISHED:
            return pair.outcome, pair.reasons
        lent = self.bound.get(lender)
        their = None if lent is None else self.pairs.get((lent.claim, lent.control))
        if their is not None and their.outcome is PairOutcome.ESTABLISHED:
            return pair.outcome, pair.reasons
        return PairOutcome.INCOHERENT, (Reason.CONTROL_INCOHERENT,)

    def indistinct_keys(self, groups: Sequence[Sequence[str]]) -> set[FactKey]:
        """Row 7 (3.2.3 [R:CO-7]): in each group of events whose cards read alike, the claimed facts of every attribute
        whose claimed values differ between the group's events."""
        found: set[FactKey] = set()
        for group in groups:
            names = tuple(group)
            entries = [item for item in self.claim_set.appraised
                       if item.key.family is Family.EVENT and item.key.object in names]
            for attribute in {item.key.attribute for item in entries}:
                mine = [item for item in entries if item.key.attribute is attribute]
                values = {name: frozenset((item.state, item.value) for item in mine if item.key.object == name)
                          for name in names}
                if len(set(values.values())) > 1:
                    found.update(item.key for item in mine)
        return found

    # -- reading the answer --

    def slot(self, family: xs.Family, name: str, attribute: Attribute) -> list[ReadFact]:
        return self.facts.get((family, name, attribute), [])

    def one(self, family: xs.Family, name: str, attribute: Attribute) -> ReadFact | None:
        """The fact of a FACT or a slot as a single-valued attribute is read (extract_read.merged, AMENDMENT-2 4.3.3):
        the merged view of an overfilled slot, never its first written fact."""
        return merged(self.slot(family, name, attribute))

    def supported(self, family: xs.Family, name: str, attribute: Attribute) -> str | None:
        found = self.one(family, name, attribute)
        if found is None or not isinstance(found.fact, Fact) or found.fact.state is not FactState.SUPPORTED:
            return None
        return found.fact.value

    def state_of(self, family: xs.Family, name: str, attribute: Attribute) -> FactState | None:
        found = self.one(family, name, attribute)
        return found.fact.state if found is not None and isinstance(found.fact, Fact) else None

    # -- one fact --

    def source(self, source: Source, failed: Sequence[Source]) -> SettledSource:
        citation = self.checked.citations.get(source)
        return SettledSource(units=source.units, link=source.link, words=None if citation is None else citation.words,
                             geometry=CheckStatus.FAILED if source in failed else CheckStatus.OK)

    def claim_of(self, found: ReadFact, failed: Sequence[Source],
                 inherited_from: str | None) -> tuple[SettledClaim, tuple[SettledSource, ...]]:
        """Pass 1's claim as stored (1.7 claim): a fact as written; the date of service by DECISIONS D187's map."""
        fact = found.fact
        sources = tuple(self.source(source, failed) for source in fact.sources)
        options = tuple(SettledOption(option.value, tuple(self.source(source, failed) for source in option.sources))
                        for option in fact.options)
        if isinstance(fact, DateOfService):
            if fact.state is DateState.STATED:
                return SettledClaim(FactState.SUPPORTED, fact.value, (), options, inherited_from), sources
            if fact.state is DateState.SEVERAL:
                return SettledClaim(FactState.CONTRADICTED, fact.value, (), options, inherited_from), sources
            return SettledClaim(None, '', (), (), inherited_from), ()
        return SettledClaim(fact.state, fact.value, fact.qualifiers, options, inherited_from), sources

    def sides(self, found: ReadFact | None) -> bool:
        """3.3 row 1's condition on a contradicted claim: its shape holds (S2) and every source of every side passes
        I1-I3 - the reader's unit and length findings, and geometry's location of each source."""
        if found is None or set(found.reasons) & SIDE_REASONS:
            return False
        fact = found.fact
        sources = (*fact.sources, *(source for option in fact.options for source in option.sources))
        return all(self.checked.citations.get(source) is not None and not self.checked.citations[source].reasons
                   for source in sources)

    def appraisal_of(self, item: claims.Appraised) -> Appraisal:
        """The stored appraisal of a bound fact (1.7): its claim and pass 2's verdict on it, and its control with pass
        2's verdict - none for a borrower, whose control is stored with its lender's (``borrowing``)."""
        claim = self.claims[item.claim]
        verdict = _verdict(self.verdicts, item.claim)
        control = None
        if item.control is not None and item.key not in self.borrowers:
            other = _verdict(self.verdicts, item.control)
            control = ControlVerdict(item.control, None if other is None else other.verdict)
        return Appraisal(claim=item.claim, content=claim.content, verdict=None if verdict is None else verdict.verdict,
                         attached=None if verdict is None else verdict.attached,
                         qualifiers=() if verdict is None else verdict.qualifiers,
                         evidence=() if verdict is None else verdict.evidence, control=control)

    def settled(self, attribute: Attribute, key: FactKey, keys: Sequence[FactKey], claim: SettledClaim,
                sources: tuple[SettledSource, ...], sides: bool, literals: tuple[StoredLiteral, ...],
                claimable: bool = True, doubted: Sequence[FactKey] = (), governed: bool = True) -> SettledFact:
        """One fact through the truth table: ``key`` is where its claim is appraised (the act's key for an inherited
        fact), ``keys`` where its findings and doubts are read (the section's fact's key first, for an inherited one);
        ``doubted``, further keys whose doubts (never their findings) name this fact too; ``governed``, whether every
        fact its result also rests on has a per-act claim - when not, its own claim's pair is kept with it and it settles
        unappraised (row 6: what it needs is not in CLAIMED), never established (a restates role: ``role``)."""
        findings = ordered(reason for name in keys for reason in self.checked.findings.get(name, ()))
        indexes = sorted({index for name in (*keys, *doubted)
                          for index in self.doubting.get((name.family, name.object, name.attribute), ())})
        bases = frozenset(self.read.doubts[index].doubt.basis for index in indexes)
        item = self.bound.get(key) if claimable and key not in self.partners else None
        if item is not None and (item.state is not claim.state or item.value != claim.value
                                 or item.inherited_from != claim.inherited_from):
            item = None  # a claim made about another value or another section is not this fact's (fail-closed)
        pair = self.pairs.get((item.claim, item.control)) if item is not None else None
        outcome: PairOutcome | None = None
        pair_reasons: tuple[Reason, ...] = ()
        if item is not None and pair is not None:
            outcome, pair_reasons = self.pair_read(item, pair)
        case = Case(state=claim.state, sides=sides, doubts=bases, joined=any(name in self.joined for name in keys),
                    findings=findings, claimed=item is not None and governed, indistinct=key in self.indistinct,
                    pair=outcome, pair_reasons=pair_reasons)
        result, reasons = decide(case)
        # pass 2's verdict stays with the fact it was given for, whatever row settled it: a fact claims.py claimed and
        # rows 1-5 settle (K8's joined members, a fact D200's object-less doubt names: claims.py reads neither yet)
        # keeps it, so pass 2's doubt about a filing is never discarded (3.2.3 [R:HO-3]); it never lifts anything
        appraisal = self.appraisal_of(item) if item is not None and claim.state in _ESTABLISHED else None
        fact = SettledFact(claim=claim, sources=sources, checks=self.checks_of(findings, claim, sources, literals),
                           appraisal=appraisal, result=result, reasons=reasons)
        self.counted.append((attribute, fact))
        for index in indexes:
            self.applied[index] = self.applied.get(index, 0) + 1
        return fact

    def checks_of(self, findings: Sequence[Reason], claim: SettledClaim, sources: Sequence[SettledSource],
                  literals: tuple[StoredLiteral, ...]) -> Checks:
        """1.7's checks record: each check failed exactly when one of its findings is on the fact (geometry also when a
        source's G1 failed); literals as L1 read them; qualified as Q1 reads the claim's qualifiers."""
        found = set(findings)
        every = (*sources, *(source for option in claim.options for source in option.sources))

        def status(failed: bool) -> CheckStatus:
            return CheckStatus.FAILED if failed else CheckStatus.OK

        return Checks(
            integrity=status(bool(found - GEOMETRY_REASONS - LITERAL_REASONS - CONSISTENCY_REASONS - QUALIFIED_REASONS)),
            geometry=status(bool(found & GEOMETRY_REASONS) or any(source.geometry is CheckStatus.FAILED
                                                                  for source in every)),
            literal=status(bool(found & LITERAL_REASONS)), literals=literals,
            consistency=status(bool(found & CONSISTENCY_REASONS)),
            qualified=any(qualifier is not Qualifier.APPROXIMATE for qualifier in claim.qualifiers))

    def own(self, key: FactKey, found: ReadFact | None) -> SettledFact:
        """An object's own fact (or a silent slot, ``found`` None)."""
        claim: SettledClaim = _SILENT
        sources: tuple[SettledSource, ...] = ()
        if found is not None:
            claim, sources = self.claim_of(found, self.checked.failed_links.get(key, ()), None)
        sides = claim.state is FactState.CONTRADICTED and self.sides(found)
        return self.settled(key.attribute, key, (key,), claim, sources, sides, self.checked.literals.get(key, ()))

    def inherited(self, key: FactKey) -> SettledFact | list[SettledFact]:
        """An act's effective fact taken from its containing section (1.5; the module's docstring). From an overfilled
        section slot (AMENDMENT-2 4.3.5), one per-act fact per written section fact (``inherited_one``)."""
        section = self.checked.containing.get(key.object)
        if section is None:
            return self.settled(key.attribute, key, (key,), _SILENT, (), False, self.checked.literals.get(key, ()))
        base = FactKey(Family.SECTION, section, INHERITED_FROM[key.attribute], 0)
        written = self.slot(Family.SECTION, section, base.attribute)
        if len(written) > 1:
            return [self.inherited_one(key, item, section) for item in written]
        found = written[0] if written else None
        if found is None:
            claim: SettledClaim = SettledClaim(None, '', (), (), section)
            sources: tuple[SettledSource, ...] = ()
        else:
            claim, sources = self.claim_of(found, self.checked.failed_links.get(base, ()), section)
        sides = claim.state is FactState.CONTRADICTED and self.sides(found)
        literals = self.checked.literals.get(key) or self.checked.literals.get(base, ())
        return self.settled(key.attribute, key, (base, key), claim, sources, sides, literals)

    def inherited_one(self, key: FactKey, item: ReadFact, section: str) -> SettledFact:
        """The act's per-act fact for one written fact of an overfilled section slot (4.3.5): the section's fact as
        written, inherited_from the section; rows 1-5 read that written fact's findings (its slot_overfull among them)
        and doubts with the act's own, so it is never established; L1's per-act literals when the act has them."""
        claim, sources = self.claim_of(item, self.checked.failed_links.get(item.key, ()), section)
        sides = claim.state is FactState.CONTRADICTED and self.sides(item)
        literals = self.checked.literals.get(key) or self.checked.literals.get(item.key, ())
        return self.settled(key.attribute, key, (item.key, key), claim, sources, sides, literals)

    def single(self, family: xs.Family, name: str, attribute: Attribute) -> SettledFact | list[SettledFact]:
        """A FACT or a slot of an object's own: its one fact settled (or silent); an overfilled slot's written facts,
        each settled (4.3.5: the list the store accepts under gemini-inventory@3, 4.3.6)."""
        written = self.slot(family, name, attribute)
        if len(written) > 1:
            return [self.own(item.key, item) for item in written]
        return self.own(FactKey(family, name, attribute, 0), written[0] if written else None)

    def member(self, member: ReadMember) -> SettledFact:
        """A member of a statement's scope list (targets, segment, covers, excepts): a value its statement states, its
        source the statement's anchor (the step's notes, reading R2)."""
        key = member.key
        anchor = self.checked.anchors.get(key.object)
        source = SettledSource(units=() if anchor is None else anchor.units, link=Link.STATEMENT, words=None,
                               geometry=CheckStatus.OK if anchor is not None and not anchor.reasons
                               else CheckStatus.FAILED)
        claim = SettledClaim(FactState.SUPPORTED, member.value, (), (), None)
        return self.settled(key.attribute, key, (key,), claim, (source,), False, ())

    def role(self, name: str, index: int, node: Mapping[str, Any]) -> SettledFact:
        """A restatement's role (1.5 [R:SC-D]): a value pass 1 gives, its source the restatement's own units (link
        other_statement); claimable only when G6 counts the restatement (Checked.restatements).

        A ``restates`` role is what moves its act's entry to the documenting clinician, and 1.5 moves it only when the
        role AND the owner of R's section are established (3.3: the entry so moved is an inherited fact - steps 1-5 on
        R's section's owner, G4 on R's edge, steps 6-9 on a per-act claim). So the role carries that move's conditions,
        as the engine reads the move from the role alone (requirements' SUP.5 reads entry and the role; the row does not
        say which section R lies in):
        - rows 1-5 read R's section's owner (its findings and its doubts) beside the role's own, and every doubt that
          names the act's entry (3.1: a doubt about an act's inherited attribute applies to its effective fact);
        - G4's edge: R attached to a section (Checked.restatements' value); a restatement attached to none lies in no
          part the documenting clinician owns, and is never claimable;
        - the role is claimable only when pass 1 gives R's section's owner as the documenting clinician (supported);
        - steps 6-9: no claim of the request appraises R's section's owner for this act (3.2.1 claims no section fact,
          and act.entry cites the anchor's section only), so the role is never established: its own pair is stored with
          it and it settles unappraised (3.2.1: an omission only holds). The fail-closed reading of the step's notes'
          question; until a ruling adds that claim, the entry is never moved (1.5: event_entry is then a question)."""
        key = FactKey(Family.EVENT, name, A.RESTATEMENTS_ROLE, index)
        valid = (name, index) in self.checked.restatements
        source = SettledSource(units=tuple(node['units']), link=Link.OTHER_STATEMENT, words=None,
                               geometry=CheckStatus.OK if valid else CheckStatus.FAILED)
        claim = SettledClaim(FactState.SUPPORTED, node['role'], (), (), None)
        if RestatementRole(node['role']) is not RestatementRole.RESTATES:
            return self.settled(A.RESTATEMENTS_ROLE, key, (key,), claim, (source,), False, (), claimable=valid)
        entry = FactKey(Family.EVENT, name, A.ENTRY, 0)
        section = self.checked.restatements.get((name, index))
        if section is None:
            return self.settled(A.RESTATEMENTS_ROLE, key, (key,), claim, (source,), False, (), claimable=False,
                                doubted=(entry,), governed=False)
        owner = FactKey(Family.SECTION, section, A.OWNER, 0)
        clinician = self.supported(Family.SECTION, section, A.OWNER) == Owner.DOCUMENTING_CLINICIAN.value
        return self.settled(A.RESTATEMENTS_ROLE, key, (owner, key), claim, (source,), False, (),
                            claimable=valid and clinician, doubted=(entry,), governed=False)

    def cited(self, family: xs.Family, name: str, cited: Cited, index: int = 0) -> SettledSource:
        """A citation that is no fact's source (a name, a start, a closing source, a description), as stored: its words
        located; its geometry ok when it locates - for a section's start, when G2 located the start, and for a closing
        source, when G2 located it (the w3int build's Q3, options a and b)."""
        found = self.citations[(family, name, cited, index)]
        source = found.source if found.source is not None else Source(found.units, '', Link.SECTION)
        citation = self.checked.citations.get(source)
        place = self.sections.get(name) if family is Family.SECTION else None
        if cited is Cited.START:
            ok = place is not None and place.start is not None
        elif cited is Cited.END:
            ok = place is not None and index < len(place.closers) and place.closers[index] is not None
        else:
            ok = citation is not None and not citation.reasons
        return SettledSource(units=source.units, link=source.link,
                             words=None if citation is None else citation.words,
                             geometry=CheckStatus.OK if ok else CheckStatus.FAILED)

    # -- the objects --

    def facts_of(self, family: xs.Family, name: str, record: dict[str, object]) -> None:
        """Every FACT, SLOT and FACTS attribute of one object, stored at its path."""
        for field in xs.ATTRIBUTES[family]:
            if field.arity in (xs.Arity.OTHER, xs.Arity.LIST):
                continue
            if field.arity is xs.Arity.FACTS:
                value: object = [self.own(item.key, item) for item in self.slot(family, name, field.attribute)]
            else:
                value = self.single(family, name, field.attribute)
            _put(record, field.path, value)

    def encounter(self) -> dict[str, object]:
        when = FactKey(Family.ENCOUNTER, '', A.DATE_OF_SERVICE, 0)
        clinician = FactKey(Family.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN, 0)
        others: list[dict[str, object]] = []
        for index, other in enumerate(self.raw['encounter']['other_dates']):
            found = next((item for item in self.slot(Family.ENCOUNTER, '', A.OTHER_DATES_ROLE)
                          if item.key.index == index), None)
            if other['value'] == '' or found is None:
                continue  # a date with no value has none to store (the step's notes, deviation D2)
            others.append({'value': other['value'], 'role': self.own(found.key, found)})
        return {'date_of_service': self.own(when, self.one(Family.ENCOUNTER, '', A.DATE_OF_SERVICE)),
                'other_dates': others,
                'documenting_clinician': self.single(Family.ENCOUNTER, '', clinician.attribute)}

    def person(self, item: Mapping[str, Any]) -> dict[str, object]:
        name = item['id']
        record: dict[str, object] = {'id': name, 'name': self.cited(Family.PERSON, name, Cited.NAME)}
        self.facts_of(Family.PERSON, name, record)
        return record

    def section(self, item: Mapping[str, Any]) -> dict[str, object]:
        name = item['id']
        record: dict[str, object] = {
            'id': name, 'start': self.cited(Family.SECTION, name, Cited.START),
            'end': [self.cited(Family.SECTION, name, Cited.END, index) for index in range(len(item['end']))]}
        self.facts_of(Family.SECTION, name, record)
        return record

    def session(self, item: Mapping[str, Any]) -> dict[str, object]:
        name = item['id']
        record: dict[str, object] = {'id': name}
        self.facts_of(Family.SESSION, name, record)
        record['completeness'] = self.completeness(name)
        return record

    def anatomy(self, item: Mapping[str, Any]) -> dict[str, object]:
        name = item['id']
        record: dict[str, object] = {'id': name}
        self.facts_of(Family.ANATOMY, name, record)
        return record

    def lesion(self, item: Mapping[str, Any]) -> dict[str, object]:
        name = item['id']
        record: dict[str, object] = {'id': name, 'description': self.cited(Family.LESION, name, Cited.DESCRIPTION)}
        self.facts_of(Family.LESION, name, record)
        return record

    def event(self, item: Mapping[str, Any]) -> dict[str, object]:
        name = item['id']
        anchor = self.checked.anchors.get(name)
        record: dict[str, object] = {
            'id': name,
            'anchor': {'units': tuple(item['anchor']['units']),
                       'kind_words': None if anchor is None else anchor.kind_words,
                       'status_words': None if anchor is None else anchor.status_words},
            'restatements': [{'units': tuple(node['units']), 'role': self.role(name, index, node)}
                             for index, node in enumerate(item['restatements'])]}
        statement = self.state_of(Family.EVENT, name, A.STATUS) is FactState.NEGATED
        inherits = STATEMENT_INHERITED if statement else ACT_INHERITED
        for field in xs.ATTRIBUTES[Family.EVENT]:
            attribute = field.attribute
            if field.arity is xs.Arity.OTHER:
                continue
            if field.arity is xs.Arity.LIST:
                value: object = [self.member(member) for member in self.members.get((name, attribute), [])]
            elif field.arity is xs.Arity.FACTS:
                value = [self.own(found.key, found) for found in self.slot(Family.EVENT, name, attribute)]
            elif attribute in inherits and not self.slot(Family.EVENT, name, attribute):
                value = self.inherited(FactKey(Family.EVENT, name, attribute, 0))
            else:
                value = self.single(Family.EVENT, name, attribute)
            _put(record, field.path, value)
        _put(record, xs.field(Family.EVENT, A.ENTRY).path, self.inherited(FactKey(Family.EVENT, name, A.ENTRY, 0)))
        return record

    def completeness(self, session: str) -> StoredCompleteness | None:
        found = next((item for item in self.claim_set.completeness if item.session == session), None)
        if found is None:
            return None
        pair = self.pairs[(found.claim, found.control)]
        claim = self.claims[found.claim]
        verdict = _verdict(self.verdicts, found.claim)
        control = _verdict(self.verdicts, found.control)
        appraisal = Appraisal(claim=found.claim, content=claim.content,
                              verdict=None if verdict is None else verdict.verdict,
                              attached=None if verdict is None else verdict.attached,
                              qualifiers=() if verdict is None else verdict.qualifiers,
                              evidence=() if verdict is None else verdict.evidence,
                              control=ControlVerdict(found.control, None if control is None else control.verdict))
        if pair.outcome is PairOutcome.ESTABLISHED:
            return StoredCompleteness(appraisal, Result.SUPPORTED, ())
        return StoredCompleteness(appraisal, Result.UNRESOLVED, pair.reasons)

    # -- the claims, the doubts, the unlisted statements --

    def stored_claims(self) -> list[StoredClaim]:
        """Every claim of the request, in order, with its role and attribute (the module's docstring). A fact's claim
        is about the attribute of the fact that reads it; a claim no fact reads, about the attribute of an entry whose
        value it states, else the attribute its template is the form of (a partner rendered as a fact that is not
        claimed: the excepted acts' claim is the breadth's exceptive sentence, so its value is a breadth) - never an
        attribute whose values its value is not, which the store refuses."""
        roles: dict[str, ClaimRole] = {}
        attributes: dict[str, Attribute] = {}
        for key, item in self.bound.items():
            roles[item.claim], attributes[item.claim] = ClaimRole.CLAIM, key.attribute
        for item in self.claim_set.appraised:
            roles.setdefault(item.claim, ClaimRole.CLAIM)
            made = self.claims.get(item.claim)
            if item.claim not in attributes and made is not None and item.value == made.value:
                attributes[item.claim] = item.key.attribute
        for item in self.claim_set.appraised:
            made = self.claims.get(item.claim)
            template = None if made is None else TEMPLATE_ATTRIBUTES.get(made.template)
            attributes.setdefault(item.claim, template if template is not None else item.key.attribute)
        for complete in self.claim_set.completeness:
            roles.setdefault(complete.claim, ClaimRole.COMPLETENESS)
            attributes.setdefault(complete.claim, A.STATIONS)
        for item in self.claim_set.appraised:
            if item.control is not None:
                roles.setdefault(item.control, ClaimRole.CONTROL)
                attributes.setdefault(item.control, CONTROL_ATTRIBUTES.get(item.key.attribute, item.key.attribute))
        for complete in self.claim_set.completeness:
            roles.setdefault(complete.control, ClaimRole.COMPLETENESS_CONTROL)
            attributes.setdefault(complete.control, A.STATIONS)
        for pair in self.claim_set.pair_controls:
            roles.setdefault(pair.claim, ClaimRole.PAIR_CONTROL)
            attributes.setdefault(pair.claim, pair.attribute)
        for lesion_pair in self.claim_set.lesion_pairs:  # DECISIONS D296: a claim and its sameness control
            roles.setdefault(lesion_pair.claim, ClaimRole.CLAIM)
            attributes.setdefault(lesion_pair.claim, A.DISTINCT_FROM)
            roles.setdefault(lesion_pair.control, ClaimRole.CONTROL)
            attributes.setdefault(lesion_pair.control, A.SAME_AS)
        out = []
        for claim in self.claim_set.claims:
            verdict = _verdict(self.verdicts, claim.id)
            stored = None if verdict is None else StoredVerdict(verdict.verdict, verdict.attached, verdict.qualifiers,
                                                                 verdict.evidence)
            out.append(StoredClaim(
                id=claim.id, role=roles.get(claim.id, ClaimRole.CONTROL), template=claim.template,
                subject=claim.subject, attribute=attributes.get(claim.id, TEMPLATE_ATTRIBUTES.get(claim.template,
                                                                                                  A.STATUS)),
                value=claim.value, units=claim.units, content=claim.content, verdict=stored))
        return out

    def lesion_pairs(self) -> list[dict[str, object]]:
        """DECISIONS D296: each lesion pair claim of the request (claims.LesionPair) with its outcome - ``supported``
        only when 3.2.3's coherence table establishes the pair (``appraise``: the claim supported with no lowering
        qualifier, attached with an attached evidence unit, and its sameness control contradicted), else
        ``unresolved`` with the table's reasons. No other verdict pattern establishes it, so it is never a release: a
        claim rejected, an incoherent pair (both supported), an uninformative one (both rejected), a missing or unclear
        verdict all leave the two lesions not established apart. Health and the coherence counts read the fact pairs
        only, as before. Whatever the form (claims.LESION_PAIR_FORMS: D300 RF-L3's membership forms included), the table
        reads the claim and its control alike; the engine reads each form against the multiplicity it presumes.

        DECISIONS D300 RF-L5: each pair the claim set dropped to stay within its bound (ClaimSet.dropped_lesion_pairs)
        is recorded too - no claim, no control, ``unresolved`` with the reason ``unappraised`` (3.3 row 6: nothing was
        asked) - so the drop is in the stored row and a dropped pair releases nothing."""
        out: list[dict[str, object]] = []
        for pair in self.claim_set.lesion_pairs:
            read = self.verdicts.get(pair.claim)
            control = _verdict(self.verdicts, pair.control)
            outcome, reasons = appraise(_verdict(self.verdicts, pair.claim), read is not None and read.attached_evidence,
                                        True, None if control is None else control.verdict)
            result = Result.SUPPORTED if outcome is PairOutcome.ESTABLISHED else Result.UNRESOLVED
            out.append({'lesion': pair.lesion, 'other': pair.other, 'claim': pair.claim, 'control': pair.control,
                        'result': result.value, 'reasons': [reason.value for reason in reasons]})
        for lesion, other in self.claim_set.dropped_lesion_pairs:
            out.append({'lesion': lesion, 'other': other, 'claim': None, 'control': None,
                        'result': Result.UNRESOLVED.value, 'reasons': [Reason.UNAPPRAISED.value]})
        return out

    def doubts(self) -> list[Doubt]:
        """The doubts as pass 1 gave them, each reading stored only when it is a value (P9)."""
        return [Doubt(about=doubt.doubt.about, objects=doubt.doubt.objects, units=doubt.doubt.units,
                      basis=doubt.doubt.basis, readings=tuple(value for value in doubt.doubt.readings
                                                              if _is_value(value)))
                for doubt in self.read.doubts]

    def natures(self, name: str) -> set[UnlistedWhat]:
        """What an event is for 3.2.6's drop rule: an act when its status is supported performed (done), a denial when
        it is negated performed (1.4: "not done" is negated performed), and a doubt when a doubt of pass 1 names it. A
        planned or attempted event is neither an act nor a denial, so it absorbs no unlisted act or denial: 3.2.6 drops
        an entry only for an event of the same nature, and no line of the design maps a plan or an attempt onto a done
        act (the fail-closed reading: keeping an entry only holds; the step's notes' question)."""
        found: set[UnlistedWhat] = set()
        status = self.one(Family.EVENT, name, A.STATUS)
        fact = None if status is None else status.fact
        if isinstance(fact, Fact) and fact.value == Status.PERFORMED.value:
            if fact.state is FactState.SUPPORTED:
                found.add(UnlistedWhat.ACT)
            elif fact.state is FactState.NEGATED:
                found.add(UnlistedWhat.DENIAL)
        if any(family is Family.EVENT and object_ == name and indexes
               for (family, object_, _attribute), indexes in self.doubting.items()):
            found.add(UnlistedWhat.DOUBT)
        return found

    def absorbing(self, entry: ReadUnlisted) -> str | None:
        """The event that absorbs an unlisted entry (3.2.6 [R:SC-A][R:HO-6]), None when it is kept (the module's
        docstring). An event's kind is read through KINDS, never constructed from pass 1's value: a supported kind
        whose value is no Kind (S2's empty value, shape_inconsistent, with which 1.8 keeps the answer) is no compatible
        kind, so the event absorbs nothing and the entry is kept (DECISIONS D229: fail-closed instead of a raise that
        would leave no settled inventory)."""
        units = set(entry.unlisted.units)
        kind = entry.unlisted.kind
        if not units or kind is None or UnlistedFinding.SESSION_UNKNOWN in entry.findings:
            return None
        for item in self.raw['events']:
            name: str = item['id']
            anchor = self.checked.anchors.get(name)
            if anchor is None or anchor.reasons:
                continue
            told = set(anchor.units)
            told.update(unit for index, node in enumerate(item['restatements'])
                        if (name, index) in self.checked.restatements for unit in node['units'])
            if not told & units or entry.unlisted.what not in self.natures(name):
                continue
            value = self.supported(Family.EVENT, name, A.KIND)
            own = KINDS.get(value) if value is not None else None
            if own is None or not (own is kind or kind in catalogue.UMBRELLAS.get(own, ())
                                   or own in catalogue.UMBRELLAS.get(kind, ())):
                continue
            if entry.session is not None and self.supported(Family.EVENT, name, A.SESSION) != entry.session:
                continue
            return name
        return None

    def unlisted(self) -> tuple[list[Unlisted], list[Dropped], set[int]]:
        kept: list[Unlisted] = []
        dropped: list[Dropped] = []
        for entry in self.appraisal.unlisted:
            absorbed = self.absorbing(entry)
            listed = entry.unlisted
            if absorbed is None:
                kept.append(Unlisted(listed.units, listed.what, listed.kind, entry.session))
            else:
                dropped.append(Dropped(listed.units, listed.what, listed.kind, entry.session, absorbed))
        known = {unit.id for unit in self.checked.units}
        doubted: set[int] = set()
        for index, events in self.checked.objectless_doubts.items():
            if not events:
                units = tuple(unit for unit in self.read.doubts[index].doubt.units if unit in known)
                kept.append(Unlisted(units, UnlistedWhat.DOUBT, None, None))
                doubted.add(index)
        return kept, dropped, doubted

    # -- the whole --

    def run(self, health: Health, usage: Usages) -> Settled:
        raw = self.raw
        events: dict[str, object] = {
            'units': self.checked.units,
            'encounter': self.encounter(),
            'people': [self.person(item) for item in raw['people']],
            'sections': [self.section(item) for item in raw['sections']],
            'sessions': [self.session(item) for item in raw['sessions']],
            'anatomy': [self.anatomy(item) for item in raw['anatomy']],
            'lesions': [self.lesion(item) for item in raw['lesions']],
            'events': [self.event(item) for item in raw['events']],
        }
        kept, dropped, doubted = self.unlisted()
        events['doubts'] = self.doubts()
        events['claims'] = self.stored_claims()
        events['unlisted'] = kept
        events['lesion_pairs'] = self.lesion_pairs()  # DECISIONS D296 (store.row_v2 keeps it at the @3 pair only)
        return Settled(events=MappingProxyType(events), verification=self.report(health, usage, kept, dropped,
                                                                                 doubted))

    def report(self, health: Health, usage: Usages, kept: Sequence[Unlisted], dropped: Sequence[Dropped],
               doubted: set[int]) -> Report:
        counts: dict[Attribute, dict[Result, int]] = {}
        reasons: dict[Reason, int] = {}
        for attribute, fact in self.counted:
            per = counts.setdefault(attribute, {})
            per[fact.result] = per.get(fact.result, 0) + 1
            for reason in fact.reasons:
                reasons[reason] = reasons.get(reason, 0) + 1
        ordered_counts = MappingProxyType({
            attribute: MappingProxyType({result: counts[attribute][result] for result in Result
                                         if result in counts[attribute]})
            for attribute in Attribute if attribute in counts})
        outcomes = {outcome: 0 for outcome in PairOutcome}
        for pair in self.pair_list:
            outcomes[pair.outcome] += 1
        coherence = Coherence(
            established=outcomes[PairOutcome.ESTABLISHED], incoherent=outcomes[PairOutcome.INCOHERENT],
            uninformative=outcomes[PairOutcome.UNINFORMATIVE], contradicted=outcomes[PairOutcome.CONTRADICTED],
            qualified=outcomes[PairOutcome.QUALIFIED], unclear=outcomes[PairOutcome.UNCLEAR],
            detached=outcomes[PairOutcome.DETACHED], missing=outcomes[PairOutcome.MISSING],
            control_missing=outcomes[PairOutcome.CONTROL_MISSING])
        doubts = tuple(DoubtApplied(index=doubt.index, about=doubt.doubt.about, basis=doubt.doubt.basis,
                                    objects=doubt.doubt.objects, malformed=doubt.malformed,
                                    applied=self.applied.get(doubt.index, 0), unlisted=doubt.index in doubted)
                       for doubt in self.read.doubts)
        return Report(counts=ordered_counts,
                      reasons=MappingProxyType({reason: reasons[reason] for reason in Reason if reason in reasons}),
                      doubts=doubts, health=health, coherence=coherence,
                      unlisted=UnlistedReport(kept=len(kept), dropped=tuple(dropped)), usage=usage)
