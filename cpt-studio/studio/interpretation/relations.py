"""Relations between what the document states (design/contract.md 6.4-6.6; design/FINAL.md 7.3-7.7; design/ADJUDICATION.md
C-7, C-8, C-11 and C-16): normalize's third linked step, ``relate``, taking the Draft after identity.distinguish and
identity.link. It reads the events' stored attributes - values, states and the literals their own words hold - and
never the text (EB1); it produces no value. Every relation is recorded, with its reason, for the operator: nothing is a
silent veto (contract 5.5).

PAIRING (6.4): one statement N against one act A. N is an event whose status is ``not_performed`` (or ``uncertain``, which
gives DOUBT instead of CONTRADICTION); A is a positive event (``performed`` or ``attempted_not_completed``) that N
concerns: A's catalogue kind is N's, a tattoo and an injection are one act, an umbrella covers its members (``removal``:
snare, emr, hot_biopsy, esd; ``intervention``: every act kind but the examination, the visit, prolonged visit time and
moderate sedation), or the two events have the same kind (so "no clip was placed" still meets a clip placed for
hemostasis, which the catalogue reads as bleeding control). The rows, in order, each SAME, DIFFERENT (both sides verified
and unequal) or UNKNOWN (a side unverified, open or absent):

| row | SAME | DIFFERENT | UNKNOWN |
|---|---|---|---|
| procedure (C-8) | both families verified and equal; or a single-family encounter and no second family claimed | both verified and unequal: another session | a family unverified where the encounter's current procedures claim two or more families |
| time | equal verified values (a default current_encounter counts) | another time | either unverified, open or unknown (C6) |
| performer | equal category, and for other_clinician a shared name token | another performer (other_clinician: names sharing no token) | either unverified, open or unknown; other_clinician without a name on both sides |
| technique | N names no device; N's device equals or contains A's (snare: cold_snare, hot_snare; forceps: cold_forceps, hot_forceps) | the two verified devices are apart: a technique-specific statement | N's device unverified; A's device absent, unverified or open (C-16), or wider than N's (a snare where N denies the cold snare) |
| target, by N's scope | all_of_kind: every act of its kind in its own session (C-8); single_target: the same verified lesion, or N has no lesion and N's place contains or is every place of A's; listed_targets: A's verified lesion listed | distinct lesions (identity 6.3); disjoint places; a verified lesion distinct from every listed one; an EXCEPTIVE scope ("no further / other / additional", C-7) never pairs | scope unknown, unverified or open; a family whose session holds two examinations (all_of_kind); a target unresolved; lesions possibly the same; a lesion on one side and only a compatible place on the other |

Any DIFFERENT gives INDEPENDENT, recorded with its reason (an established difference settles it, whatever else is
unknown). Otherwise the first UNKNOWN in row order gives UNRESOLVED(that attribute). Otherwise both kinds and both statuses
must be verified (an unverified kind gives UNRESOLVED(scope): whether the statement concerns the act; an unverified status
UNRESOLVED(status)); then N not_performed gives CONTRADICTION and N uncertain gives DOUBT.

PLACES (Context.places, read by the target row, the claims and the bundling identities): an event's verified, placed
target landmark and its verified lesion's verified site. A surgically made place has no position in the tract, so it is
never disjoint from anything (lexicon.ALTERED_LANDMARKS) - except that a target verified at an anastomosis takes the
place of the encounter's ONE anastomosis when its anatomy entry's own words name its type (DECISIONS D34,
mapping.anastomosis_place: an ileocolonic one the right colon, a colorectal, coloanal or ileorectal one the rectum, a
gastrojejunal one the stomach, an esophagojejunal or esophagogastric one the esophagus). Several anastomoses, no type
word, an unknown type, a target whose own words name another type, or an event whose family does not reach that place
(mapping.ANASTOMOSIS_FAMILIES) keep the ambiguity. A lesion's site is read as stated. A difference that rests on a D34 place sets a pair apart, but it is never HARD: that place is in the anatomy
entry's words, not the event's, so it never dismisses Gemini's own claim (C-11; Context.stated_places).

MODEL CLAIMS (6.4; C-11). Each contradicts[] entry normalize handed over is judged by the same table (a planned statement
judged as a statement, giving DOUBT). A claim the table finds INDEPENDENT is a ``dismissed_claim`` only when a HARD literal
establishes the difference - disjoint places, distances or specimen labels (identity.HARD), a time with a date literal,
a performer named with a title or credential (or two other clinicians whose names share no token), two devices with
surface forms, two families each named by the procedure-name check; otherwise it is UNRESOLVED on the attribute of the
difference (C-11: a size-only distinctness never dismisses Gemini's own claim; nor does a time read by its marker alone,
another clinician named by no name, an "other" device, or a family verified by its binding alone). A claim whose
statement does not concern the act - two kinds - is dismissed only by a hard row of the same table: a kind is verified
by its binding alone (contract 5.6), never a literal, so otherwise it is UNRESOLVED(kind) (review finding 2: an EMR
denial of the very lesion a snare removed had been dismissed as "another act"). UNRESOLVED, DOUBT and CONTRADICTION stand
as computed, marked as claimed. A claim between two positive events matters only where a code depends on what they
disagree on: a hard difference of place, time, performer or family dismisses it (two acts); different kinds give
UNRESOLVED(kind), different statuses UNRESOLVED(status), two devices UNRESOLVED(technique) where a code depends on the
technique (and dismiss it otherwise), any other difference or unknown UNRESOLVED on its attribute - recorded once for each
side, so each is the positive side of one.

STEPS (6.6): every verified ``part_of`` is a ``step`` relation (statement: the whole act; event: the step), named by the
catalogue rule it carries: ``lift_injection`` (an injection or tattoo in an EMR or ESD), ``resection_technique`` (a snare
or hot biopsy in an EMR or ESD), ``endoscopic_portion`` (an examination within another, C3), else ``step``.

BUNDLING IDENTITY (6.6; FINAL 7.7; ADJUDICATION C-2 and C-5): two current positive acts of one session whose bundling
depends on whether they are on one lesion - a biopsy beside a removal (``biopsy_of_removed_lesion``), a snare or hot
biopsy beside an EMR or ESD (``resection_technique``), an injection (never a tattoo, never one whose hemostasis purpose is
verified) beside an EMR or ESD (``lift_injection``) - get a ``bundling_identity`` relation (statement: the removal or
resection; event: the act whose code it makes depend on identity) when that identity is in doubt and their places do not
set them apart. Places are each act's OWN verified places (Context.places: its verified target landmark, its verified
lesion's site), compared only when both acts have one: verified places that are not compatible - disjoint, or not
comparable, such as an anastomosis beside a segment - ask nothing (6.6: "at compatible landmarks"; FINAL 5.6: the E15
biopsy is unaffected). The site of a lesion an act names but is not verified to be is no place of that act's: an
unverified identifier never sets two acts apart (P3; review finding 6), whether through that site or through that
lesion's distinctness. In doubt, at compatible or unknown places: both verified to lesions possibly the same; a biopsy
and a removal of one verified group lesion that cite no common passage (C-2); either names a lesion it is not verified to
be; an injection whose lesion is not verified or whose place, or the resection's, is not known (C-5); and neither names a
lesion while both are stated in one passage (an own kind, status or target passage in common) - legacy's one-clause rule
(reconcile._one_resection, reconcile.py:714-724), asked instead of decided, because a missing identifier never makes a
non-match (P3; review finding 4). On one verified single lesion the engine bundles and nothing is asked. Each act is its
own where neither names a lesion and they are stated apart (random biopsies told in their own sentence), and where one is
verified to a lesion and the other names none (Gemini's own reading ties only that act to it).

Pure and Django-free; imports nothing from studio.gi but through mapping's reference tables (FINAL 3.1).
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from studio.interpretation import identity, lexicon, mapping, verify

# --- the closed lists --------------------------------------------------------------------------------------------------

CONTRADICTION, DOUBT, UNRESOLVED, INDEPENDENT = 'contradiction', 'doubt', 'unresolved', 'independent'
DISMISSED, STEP, BUNDLING = 'dismissed_claim', 'step', 'bundling_identity'
TYPES = (CONTRADICTION, DOUBT, UNRESOLVED, INDEPENDENT, DISMISSED, STEP, BUNDLING)  # store.RELATION_TYPES
SAME, DIFFERENT, UNKNOWN = 'same', 'different', 'unknown'
ROWS = ('procedure', 'time', 'performer', 'technique', 'target')
# The attributes a relation names: the rows, the scope (whether a statement concerns the act), the status, the kind (a
# model's claim that two positive events are one act of two kinds; contract 6.5's UNRESOLVED(kind)) and part_of.
ATTRIBUTES = ('procedure', 'time', 'performer', 'technique', 'target', 'scope', 'status', 'kind', 'part_of')
REASONS = (
    # INDEPENDENT, and a dismissed claim's reason
    'another_procedure', 'another_time', 'another_performer', 'another_technique', 'another_lesion', 'another_site',
    'exceptive', 'no_act',
    # UNRESOLVED
    'procedure_unresolved', 'session_unresolved', 'time_unresolved', 'performer_unresolved', 'technique_unresolved',
    'scope_unresolved', 'identity_unresolved', 'possibly_same_lesion', 'site_unresolved', 'site_overlap',
    'kind_unresolved', 'status_unresolved', 'claim_soft_difference', 'claim_kind', 'claim_status', 'claim_technique',
    'claim_no_difference',
    # CONTRADICTION, DOUBT
    'same_act', 'in_doubt',
    # STEP and BUNDLING
    'lift_injection', 'resection_technique', 'endoscopic_portion', 'step', 'biopsy_of_removed_lesion',
)
# A statement for pairing; a statement for a model's claim (a planned act judged as a statement, giving DOUBT).
STATEMENTS = ('not_performed', 'uncertain')
CLAIM_STATEMENTS = ('not_performed', 'uncertain', 'planned')
DEVICE_CONTAINS = {'snare': frozenset({'cold_snare', 'hot_snare'}), 'forceps': frozenset({'cold_forceps', 'hot_forceps'})}
RESECTIONS = frozenset({'emr', 'esd'})
RESECTION_TECHNIQUES = frozenset({'snare', 'hot_biopsy'})
# DECISIONS D30 and D41: the kinds a removal's procedural adjunct can be (coverage.ADJUNCT_KINDS is this set)
PROCEDURAL_ADJUNCTS = frozenset({'ablation', mapping.BLEEDING_CONTROL})


@dataclass(frozen=True)
class Row:
    """One row of the pairing table: SAME, DIFFERENT or UNKNOWN, the attribute it names, why, and whether a DIFFERENT
    rests on a hard literal (C-11)."""
    attribute: str
    result: str
    reason: str = ''
    hard: bool = False


@dataclass(frozen=True)
class Verdict:
    """What the table gives one pair: the relation type, the attribute and the reason, whether an INDEPENDENT rests on a
    hard literal, and the rows."""
    type: str
    attribute: str = ''
    reason: str = ''
    hard: bool = False
    rows: tuple = field(default=(), compare=False)


# --- the encounter the rows read ---------------------------------------------------------------------------------------

class Context:
    """What the rows read beyond the two events: the current procedural families (normalize's own rule for the
    procedure default: positive, current_encounter, procedural), the families whose session holds two current
    examinations (FINAL 7.8: that session is unresolved), the lesions' facts and the events' catalogue kinds."""

    def __init__(self, draft):
        self.draft = draft
        events = draft.events.values()
        self.families = frozenset(
            event['family'] for event in events if event['status']['value'] in verify.POSITIVE
            and event['time']['value'] == 'current_encounter' and event['family'] in lexicon.PROCEDURAL_FAMILIES)
        exams = Counter(event['family'] for event in events if event['kind']['value'] == 'examination'
                        and event['status']['value'] in verify.POSITIVE and event['current'] == 'yes'
                        and event['family'])
        self.unresolved_sessions = frozenset(family for family, count in exams.items() if count >= 2)
        self.facts = identity.lesion_facts(draft)
        self.kinds = {eid: mapping.catalogue_kind(event) for eid, event in draft.events.items()}
        # DECISIONS D34: the place the encounter's one anastomosis takes, from its anatomy entry's own words ('' when
        # none is established: several anastomoses, no type word, an unknown type).
        self.anastomosis = mapping.anastomosis_place(draft.encounter)

    @property
    def multi_family(self) -> bool:
        return len(self.families) >= 2

    def distinct(self, first: str, second: str) -> str:
        """Why two lesions are distinct ('' when they are not; identity.DISTINCT_BY)."""
        if second not in self.draft.lesions.get(first, {}).get('distinct_from', ()):
            return ''
        return identity.distinct_reason(self.facts[first], self.facts[second]) or 'passage'

    def target_place(self, event: Mapping) -> str:
        """The event's verified, placed target landmark as the comparisons and D29 read it: an anastomosis at the place
        the encounter's one anastomosis takes (DECISIONS D34; mapping.compared_landmark), else as stated."""
        return mapping.compared_landmark(event, self.anastomosis)

    def places(self, event: Mapping) -> frozenset:
        """The places an event's target is verified to be at: its verified, placed target landmark (target_place: an
        anastomosis at its D34 place) and its verified lesion's verified site."""
        found = set()
        own = self.target_place(event)
        if own:
            found.add(own)
        lesion = identity.verified_lesion(event)
        if lesion and self.facts[lesion].landmark:
            found.add(self.facts[lesion].landmark)
        return frozenset(found)

    def stated_places(self, *events) -> bool:
        """Whether every place of ``events`` is stated by that event's own words or its lesion's: none is an anastomosis
        D34 placed. A D34 place comes from the anatomy entry's words, not the event's, so a difference it makes sets the
        two apart for the pairing and D29 but is never HARD (C-11: Gemini's own claim is dismissed only by a literal)."""
        return not any(self.target_place(event) != mapping.target_landmark(event) for event in events)


def concerns(context: Context, statement: Mapping, act: Mapping) -> bool:
    """Whether ``statement`` concerns ``act``'s kind (module docstring)."""
    if mapping.covers(context.kinds[statement['id']], context.kinds[act['id']]):
        return True
    kind = statement['kind']['value']
    return kind == act['kind']['value'] and kind != 'other'


def _all_disjoint(first, second) -> bool:
    return bool(first) and bool(second) and all(lexicon.disjoint(one, two) for one in first for two in second)


def _name_tokens(attribute: Mapping) -> frozenset:
    return frozenset(token for name in (attribute.get('literals') or {}).get('names', ()) for token in name['tokens'])


# --- the rows ----------------------------------------------------------------------------------------------------------

def named_family(procedure: Mapping) -> bool:
    """Whether a procedure attribute's family rests on a literal: usable, with its words through the procedure-name
    check (several current families; contract 5.3). A family verified by its located words alone (one family) or by
    the single-family default is Gemini's reading, never a literal (C-11)."""
    return verify.usable(procedure) and 'procedure_name' in (procedure.get('checks') or ())


def procedure_row(context: Context, statement: Mapping, act: Mapping) -> Row:
    first, second = statement['family'], act['family']
    if verify.usable(statement['procedure']) and verify.usable(act['procedure']) and first and second:
        if first == second:
            return Row('procedure', SAME)
        hard = named_family(statement['procedure']) and named_family(act['procedure'])
        return Row('procedure', DIFFERENT, 'another_procedure', hard)
    if not context.multi_family and len({family for family in (first, second) if family}) <= 1:
        return Row('procedure', SAME)
    return Row('procedure', UNKNOWN, 'procedure_unresolved')


def time_row(statement: Mapping, act: Mapping) -> Row:
    first, second = statement['time'], act['time']
    if not (verify.usable(first) and verify.usable(second)):
        return Row('time', UNKNOWN, 'time_unresolved')
    if first['value'] == second['value']:
        return Row('time', SAME)
    hard = any(verify.exclusion_basis('time', side) == 'literal' for side in (first, second))
    return Row('time', DIFFERENT, 'another_time', hard)


def performer_row(statement: Mapping, act: Mapping) -> Row:
    first, second = statement['performer'], act['performer']
    if not (verify.usable(first) and verify.usable(second)):
        return Row('performer', UNKNOWN, 'performer_unresolved')
    if first['value'] != second['value']:
        hard = any(verify.exclusion_basis('performer', side) == 'literal' for side in (first, second))
        return Row('performer', DIFFERENT, 'another_performer', hard)
    if first['value'] == 'other_clinician':
        one, two = _name_tokens(first), _name_tokens(second)
        if one and two:
            return Row('performer', SAME) if one & two else Row('performer', DIFFERENT, 'another_performer', True)
        return Row('performer', UNKNOWN, 'performer_unresolved')
    return Row('performer', SAME)


def _wider(outer: str, inner: str) -> bool:
    return inner in DEVICE_CONTAINS.get(outer, ())


def technique_row(statement: Mapping, act: Mapping) -> Row:
    first, second = statement['technique'], act['technique']
    if first['value'] == 'not_stated':
        return Row('technique', SAME)  # the statement names no device
    if not (verify.usable(first) and verify.usable(second)):
        return Row('technique', UNKNOWN, 'technique_unresolved')  # C-16: the act's device absent or unverified
    one, two = first['value'], second['value']
    if one == two and one != 'other' or _wider(one, two):
        return Row('technique', SAME)
    if _wider(two, one) or one == two == 'other':
        return Row('technique', UNKNOWN, 'technique_unresolved')
    hard = one not in lexicon.UNCHECKED_DEVICES and two not in lexicon.UNCHECKED_DEVICES
    return Row('technique', DIFFERENT, 'another_technique', hard)


def _single_target(context: Context, statement: Mapping, act: Mapping) -> Row:
    named = statement['target']['lesion']
    lesion, other = identity.verified_lesion(statement), identity.verified_lesion(act)
    places, act_places = context.places(statement), context.places(act)
    if named:
        if lesion and other:
            if lesion == other:
                return Row('target', SAME)
            why = context.distinct(lesion, other)
            if why:
                return Row('target', DIFFERENT, 'another_lesion', why in identity.HARD)
            return Row('target', UNKNOWN, 'possibly_same_lesion')
        if _all_disjoint(places, act_places):
            return Row('target', DIFFERENT, 'another_site', context.stated_places(statement, act))
        return Row('target', UNKNOWN, 'identity_unresolved')
    if not places or not act_places:
        return Row('target', UNKNOWN, 'site_unresolved')
    if all(any(own == place or lexicon.contains(own, place) for own in places) for place in act_places):
        return Row('target', SAME)
    if _all_disjoint(places, act_places):
        return Row('target', DIFFERENT, 'another_site', context.stated_places(statement, act))
    return Row('target', UNKNOWN, 'site_overlap')


def _listed_targets(context: Context, statement: Mapping, act: Mapping) -> Row:
    listed = list(statement['scope'].get('targets') or ())
    lesion = identity.verified_lesion(act)
    if lesion:
        if lesion in listed:
            return Row('target', SAME)
        reasons = [context.distinct(lesion, other) for other in listed]
        if listed and all(reasons):
            return Row('target', DIFFERENT, 'another_lesion', all(why in identity.HARD for why in reasons))
        return Row('target', UNKNOWN, 'possibly_same_lesion')
    places = context.places(act)
    sites = [context.facts[other].landmark for other in listed if other in context.facts]
    if listed and places and len(sites) == len(listed) and all(sites) and _all_disjoint(places, sites):
        return Row('target', DIFFERENT, 'another_site', context.stated_places(act))
    return Row('target', UNKNOWN, 'identity_unresolved')


def target_row(context: Context, statement: Mapping, act: Mapping) -> Row:
    if statement['status']['value'] not in STATEMENTS:  # a planned act a claim names: it has a target, not a scope
        return _act_target_row(context, statement, act)
    scope = statement['scope']
    value = scope['value']
    if not verify.usable(scope):
        return Row('scope', UNKNOWN, 'scope_unresolved')
    if value == 'exceptive':  # C-7: covers only acts beyond those reported; never pairs with a positive act
        return Row('scope', DIFFERENT, 'exceptive')
    if value == 'all_of_kind':  # C-8: every act of its kind in its own examination or session
        if {statement['family'], act['family']} & context.unresolved_sessions:
            return Row('procedure', UNKNOWN, 'session_unresolved')
        return Row('target', SAME)
    if value == 'single_target':
        return _single_target(context, statement, act)
    if value == 'listed_targets':
        return _listed_targets(context, statement, act)
    return Row('scope', UNKNOWN, 'scope_unresolved')


# --- one pair ----------------------------------------------------------------------------------------------------------

def rows_of(context: Context, statement: Mapping, act: Mapping) -> tuple:
    """The pairing table's rows for ``statement`` against ``act``, in order (module docstring)."""
    return (procedure_row(context, statement, act), time_row(statement, act), performer_row(statement, act),
            technique_row(statement, act), target_row(context, statement, act))


def pair(context: Context, statement: Mapping, act: Mapping) -> Verdict:
    """The pairing table's verdict for ``statement`` (not_performed, uncertain or - for a claim - planned) against the
    positive ``act`` (module docstring)."""
    rows = rows_of(context, statement, act)
    different = [row for row in rows if row.result == DIFFERENT]
    if different:
        return Verdict(INDEPENDENT, different[0].attribute, different[0].reason, any(row.hard for row in different), rows)
    unknown = next((row for row in rows if row.result == UNKNOWN), None)
    if unknown is not None:
        return Verdict(UNRESOLVED, unknown.attribute, unknown.reason, rows=rows)
    if not (verify.usable(statement['kind']) and verify.usable(act['kind'])):
        return Verdict(UNRESOLVED, 'scope', 'kind_unresolved', rows=rows)
    if not (verify.usable(statement['status']) and verify.usable(act['status'])):
        return Verdict(UNRESOLVED, 'status', 'status_unresolved', rows=rows)
    if statement['status']['value'] == 'not_performed':
        return Verdict(CONTRADICTION, 'status', 'same_act', rows=rows)
    return Verdict(DOUBT, 'status', 'in_doubt', rows=rows)


def judge_claim(context: Context, statement: Mapping, act: Mapping) -> Verdict:
    """A model's claim that ``statement`` contradicts the positive ``act`` (C-11): the table's verdict, an INDEPENDENT
    that rests on no hard literal becoming UNRESOLVED on the attribute of the difference. A statement of another kind
    is set apart only by a hard row of the table; otherwise the claim asks whether it concerns the act."""
    if not concerns(context, statement, act):
        rows = rows_of(context, statement, act)
        hard = [row for row in rows if row.result == DIFFERENT and row.hard]
        if hard:
            return Verdict(INDEPENDENT, hard[0].attribute, hard[0].reason, True, rows)
        if verify.usable(statement['kind']) and verify.usable(act['kind']):
            return Verdict(UNRESOLVED, 'kind', 'claim_kind', rows=rows)
        return Verdict(UNRESOLVED, 'scope', 'kind_unresolved', rows=rows)
    verdict = pair(context, statement, act)
    if verdict.type == INDEPENDENT and not verdict.hard:
        return Verdict(UNRESOLVED, verdict.attribute, 'claim_soft_difference', rows=verdict.rows)
    return verdict


def _act_target_row(context: Context, first: Mapping, second: Mapping) -> Row:
    """The target of two positive events compared (a model's claim that they are one act)."""
    lesion, other = identity.verified_lesion(first), identity.verified_lesion(second)
    if lesion and other:
        if lesion == other:
            return Row('target', SAME)
        why = context.distinct(lesion, other)
        if why:
            return Row('target', DIFFERENT, 'another_lesion', why in identity.HARD)
        return Row('target', UNKNOWN, 'possibly_same_lesion')
    if _all_disjoint(context.places(first), context.places(second)):
        return Row('target', DIFFERENT, 'another_site', context.stated_places(first, second))
    return Row('target', UNKNOWN, 'identity_unresolved')


def judge_positive_claim(context: Context, first: Mapping, second: Mapping) -> Verdict:
    """A model's claim that two positive events cannot both be true (module docstring)."""
    rows = (procedure_row(context, first, second), time_row(first, second), performer_row(first, second),
            technique_row(first, second), _act_target_row(context, first, second))
    hard = [row for row in rows if row.result == DIFFERENT and row.hard and row.attribute != 'technique']
    if hard:
        return Verdict(INDEPENDENT, hard[0].attribute, hard[0].reason, True, rows)
    if not (concerns(context, first, second) or concerns(context, second, first)):
        return Verdict(UNRESOLVED, 'kind', 'claim_kind', rows=rows)
    if first['status']['value'] != second['status']['value']:
        return Verdict(UNRESOLVED, 'status', 'claim_status', rows=rows)
    soft = [row for row in rows if row.result == DIFFERENT and row.attribute != 'technique']
    if soft:
        return Verdict(UNRESOLVED, soft[0].attribute, 'claim_soft_difference', rows=rows)
    technique = rows[3]
    if technique.result == DIFFERENT:
        kind = context.kinds[first['id']]
        if any(mapping.technique_dependent(event['family'], kind) for event in (first, second)):
            return Verdict(UNRESOLVED, 'technique', 'claim_technique', rows=rows)
        return Verdict(INDEPENDENT, 'technique', 'another_technique', True, rows)
    unknown = next((row for row in rows if row.result == UNKNOWN), None)
    if unknown is not None:
        return Verdict(UNRESOLVED, unknown.attribute, unknown.reason, rows=rows)
    return Verdict(UNRESOLVED, 'status', 'claim_no_difference', rows=rows)


# --- the relations' passages -------------------------------------------------------------------------------------------

_STATEMENT_SIDE = ('status', 'kind', 'scope', 'target')
_ACT_SIDE = ('kind', 'status')
_OWN = frozenset({'procedure', 'time', 'performer', 'technique', 'target', 'scope', 'status', 'kind'})


def _passages(statement: Mapping, act: Mapping, attribute: str = '', extra=()) -> list:
    """Both sides' own passages (FINAL 7.4 h1: a question quotes both sides): the statement's status, kind, scope and
    target passages, then the act's kind and status passages and the passages of the attribute the relation names."""
    ids = []
    names = _ACT_SIDE + ((attribute,) if attribute in _OWN else ())
    for event, fields in ((statement, _STATEMENT_SIDE), (act, names)):
        for name in fields:
            record = event.get(name)
            if isinstance(record, Mapping):
                ids += list(record.get('passages') or ())
    ids += list(extra)
    return list(dict.fromkeys(ids))


# --- the step ----------------------------------------------------------------------------------------------------------

def relate(draft) -> None:
    """normalize's third linked step (module docstring): the pairings, the model's claims, the steps and the bundling
    identities, added through Draft.relation in that order. Reads the events' stored attributes only."""
    context = Context(draft)
    events = draft.events
    computed = {}
    statements = [event for event in events.values() if event['status']['value'] in STATEMENTS]
    acts = [event for event in events.values() if event['status']['value'] in verify.POSITIVE]
    for statement in statements:
        for act in acts:
            if not concerns(context, statement, act):
                continue
            verdict = pair(context, statement, act)
            computed[(statement['id'], act['id'])] = draft.relation(
                verdict.type, statement=statement['id'], event=act['id'], attribute=verdict.attribute,
                reason=verdict.reason, passages=_passages(statement, act, verdict.attribute))
    _claims(draft, context, computed)
    _steps(draft)
    _bundling(draft, context)


def _claims(draft, context: Context, computed: dict) -> None:
    seen = set()
    for claim in draft.claims:
        first, second = draft.events[claim['statement']], draft.events[claim['event']]
        pair_key = frozenset((first['id'], second['id']))
        if pair_key in seen:
            continue
        seen.add(pair_key)
        positive = [event['status']['value'] in verify.POSITIVE for event in (first, second)]
        if all(positive):
            _positive_claim(draft, context, first, second, claim['passages'])
            continue
        if not any(positive):  # two statements: neither is an act any code reads
            draft.relation(DISMISSED, statement=first['id'], event=second['id'], reason='no_act', claimed_by_model=True,
                           passages=_passages(first, second) + list(claim['passages']))
            continue
        statement, act = (second, first) if positive[0] else (first, second)
        verdict = judge_claim(context, statement, act)
        kind = DISMISSED if verdict.type == INDEPENDENT else verdict.type
        passages = _passages(statement, act, verdict.attribute, claim['passages'])
        existing = computed.get((statement['id'], act['id']))
        if existing is None:
            draft.relation(kind, statement=statement['id'], event=act['id'], attribute=verdict.attribute,
                           reason=verdict.reason, claimed_by_model=True, passages=passages)
        else:  # the same pair, now claimed: one relation per pair, judged as a claim
            existing.update(type=kind, attribute=verdict.attribute, reason=verdict.reason, claimed_by_model=True,
                            passages=[pid for pid in dict.fromkeys(existing['passages'] + passages)
                                      if pid in draft.passages])


def _positive_claim(draft, context: Context, first: Mapping, second: Mapping, passages) -> None:
    verdict = judge_positive_claim(context, first, second)
    if verdict.type == INDEPENDENT:
        draft.relation(DISMISSED, statement=first['id'], event=second['id'], attribute=verdict.attribute,
                       reason=verdict.reason, claimed_by_model=True,
                       passages=_passages(first, second, verdict.attribute, passages))
        return
    for one, two in ((first, second), (second, first)):  # each positive side is the event of one relation
        draft.relation(verdict.type, statement=one['id'], event=two['id'], attribute=verdict.attribute,
                       reason=verdict.reason, claimed_by_model=True,
                       passages=_passages(one, two, verdict.attribute, passages))


def step_reason(step: Mapping, whole: Mapping) -> str:
    """The catalogue rule a verified part_of carries (6.6; COMMON_BUNDLED; C3)."""
    kind, of = step['kind']['value'], whole['kind']['value']
    if of in RESECTIONS and kind in mapping.ONE_ACT:
        return 'lift_injection'
    if of in RESECTIONS and kind in RESECTION_TECHNIQUES:
        return 'resection_technique'
    if kind == 'examination' and of == 'examination':
        return 'endoscopic_portion'
    return 'step'


def _steps(draft) -> None:
    for event in draft.events.values():
        part = event['part_of']
        if isinstance(part, Mapping) and part.get('state') == 'verified' and part.get('value') in draft.events:
            whole = draft.events[part['value']]
            draft.relation(STEP, statement=whole['id'], event=event['id'], attribute='part_of',
                           reason=step_reason(event, whole), passages=_passages(whole, event))


def bundling_rule(context: Context, whole: Mapping, part: Mapping) -> str:
    """The bundling rule whose identity ``part`` beside ``whole`` depends on (module docstring), '' for none."""
    of, kind = context.kinds[whole['id']], context.kinds[part['id']]
    if of in mapping.REMOVAL_MEMBERS and kind == 'biopsy':
        return 'biopsy_of_removed_lesion'
    if of in RESECTIONS and kind in RESECTION_TECHNIQUES:
        return 'resection_technique'
    if of in RESECTIONS and kind == 'injection' and part['kind']['value'] == 'injection':
        return 'lift_injection'
    if of in mapping.REMOVAL_MEMBERS and kind in PROCEDURAL_ADJUNCTS:  # D41
        return 'procedural_adjunct'
    return ''


def _own_passages(event: Mapping) -> set:
    return {pid for name in ('kind', 'status', 'target') for pid in event[name].get('passages') or ()}


def _compatible(first, second) -> bool:
    return bool(first) and bool(second) and all(lexicon.compatible(one, two) for one in first for two in second)


def identity_in_doubt(context: Context, rule: str, whole: Mapping, part: Mapping) -> bool:
    """Whether the bundling of ``part`` beside ``whole`` under ``rule`` depends on an identity not established (module
    docstring). Each act's OWN verified places (Context.places) that are not compatible - disjoint, or not comparable
    (an anastomosis beside a segment) - ask nothing (contract 6.6: "at compatible landmarks"; FINAL 5.6: the E15 biopsy
    is unaffected); an unverified link sets nothing apart (P3)."""
    places, part_places = context.places(whole), context.places(part)
    known = bool(places) and bool(part_places)
    if known and not _compatible(places, part_places):
        return False
    lesion, other = identity.verified_lesion(whole), identity.verified_lesion(part)
    if lesion and other:
        if lesion == other:  # one verified lesion: bundled - unless a biopsy and a removal of a group cite no passage
            return (rule == 'biopsy_of_removed_lesion' and not context.facts[lesion].single  # in common (C-2)
                    and not _own_passages(whole) & _own_passages(part))
        return not context.distinct(lesion, other)
    if rule == 'procedural_adjunct':
        # D41 (the S17 refutation of D30): a removal's adjunct is bundled only through a verified link (its part_of, or
        # the removal's verified lesion: coverage.bundled_reason). Beside a removal of its session, an ablation or a
        # bleeding control that names no lesion, names one not established, or stands at compatible or unknown places is
        # set apart by nothing verified - so it is asked, never READY alone; only a verified part_of naming another act
        # (above: incompatible places; two distinct verified lesions) sets it apart. FINAL 5.7: a false READY is repaired.
        step = part.get('part_of')
        return not (isinstance(step, Mapping) and step.get('state') == 'verified' and step.get('value')
                    and step.get('value') != whole['id'])
    identities = (whole['target']['identity'], part['target']['identity'])
    if rule == 'lift_injection':  # C-5: its lesion or its site unresolved
        return identity.UNRESOLVED in identities or not known
    if identity.UNRESOLVED in identities:
        return True  # a lesion named but not established, at compatible or unknown places
    if lesion or other:
        return False  # one verified to a lesion, the other naming none: Gemini's reading ties only that act to it
    return bool(_own_passages(whole) & _own_passages(part))  # neither names a lesion: one statement asks (P3)


def _bundling(draft, context: Context) -> None:
    current = [event for event in draft.events.values()
               if event['status']['value'] in verify.POSITIVE and event['current'] == 'yes']
    for whole in current:
        for part in current:
            if part is whole:
                continue
            rule = bundling_rule(context, whole, part)
            if not rule or procedure_row(context, whole, part).result == DIFFERENT:
                continue
            step = part['part_of']
            if isinstance(step, Mapping) and step.get('state') == 'verified' and step.get('value') == whole['id']:
                continue  # a verified step of it: bundled by its part_of
            if identity_in_doubt(context, rule, whole, part):
                draft.relation(BUNDLING, statement=whole['id'], event=part['id'], attribute='target', reason=rule,
                               passages=_passages(whole, part, 'target'))
