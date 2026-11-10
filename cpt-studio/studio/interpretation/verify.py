"""Evidence binding's checks (design/contract.md 5.2-5.5, design/FINAL.md C1, as design/ADJUDICATION.md EB1-EB4 amend
them): the closed lists of checks and failure reasons, one check per attribute, the structural rules, and time_state.

The principle (EB). Evidence binding checks that Gemini's own evidence states Gemini's own value. It is not a second
reading of the document:
- EB1. A check reads only the cited WORDS of the attribute it verifies - the document's own slice that normalization
  located inside that attribute's own passages - and the literal values inside them: a date, a size, a person's name, a
  landmark, a device, or a C1 marker where the value can decide an exclusion. No check scans the rest of a passage, a
  neighbouring sentence, a heading or the document. The contract's foreign-date and foreign-name passage guards, FINAL
  C10, and every "marker in passage" scan are REMOVED: their reasons (REMOVED_REASONS) are never produced.
- EB2. The frame defaults are Gemini's reading: a current_encounter time or a documenting_team performer given with no
  words is accepted (basis ``default``). Where Gemini did give time words, a date literal in them that differs from the
  service date leaves the time unverified; where it gave performer words, a name in them that is not the documenting
  endoscopist or a listed team member leaves the performer unverified.
- EB3. C1's markers read only the words of a value that could EXCLUDE: status planned or attempted_not_completed, time
  earlier_encounter or future with no date literal, performer other_facility with no person name. A missing marker
  never touches the READY path (performed, current_encounter, documenting_team).
- DECISIONS D35 narrows EB3 for the time alone: a current_encounter time whose OWN words carry a marker of another
  occasion - a C1 earlier or future marker, or "original" (lexicon.other_occasion) - is unverified (other_occasion),
  because Gemini's own words contradict Gemini's own value. A time question, never an exclusion: no exclusion reads a
  current time, and the earlier and future values' markers are read exactly as EB3 reads them.
- DECISIONS D42 completed D35 fail-closed, and D54 reads the words WHOLE: a current_encounter time whose OWN words
  carry no date literal at day precision and no D35 marker is verified only when those words are made of whole
  present-encounter frames (lexicon.current_frame); otherwise it is unverified (current_unanchored) - the words name an
  occasion, a period or a sequence without saying it is this one. An anchor word inside other words ("these were the
  findings at her index colonoscopy") and a year or a month ("in November 2026") anchor nothing.

What a failure does (contract 5.5): the attribute is unverified with its reasons, closed lists here. It never sets,
changes or removes a value, never excludes a code, never creates a status, a contradiction or a hold. Consumers read an
attribute through ``usable`` (verified and not opened by an open question) and an exclusion's evidence through
``exclusion_basis`` (FINAL C1: there is no wording-only exclusion).

Pure and Django-free; reads nothing from studio.gi (FINAL 3.1).
"""
from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from studio.interpretation import lexicon, literals

# --- the closed lists --------------------------------------------------------------------------------------------------

# Every reason normalization and these checks give (contract 5.5 with FINAL C1 and the structural rules of 5.4), in the
# order a record lists them.
REASONS = (
    # binding (contract 5.2)
    'passage_unknown', 'passage_unlocated', 'words_missing', 'words_unlocated',
    # literal checks (contract 5.3)
    'date_mismatch', 'date_unchecked', 'name_mismatch', 'name_not_other', 'size_missing', 'landmark_missing',
    'landmark_conflict', 'device_reach', 'device_missing', 'procedure_name_missing', 'procedure_unsettled',
    'negation_missing', 'quantifier_missing', 'duration_missing', 'label_missing',
    # the C1 markers (FINAL 5.2, 5.5; EB3), and a current time's words naming another occasion (DECISIONS D35)
    'planning_missing', 'failure_missing', 'time_marker_missing', 'facility_marker_missing', 'other_occasion',
    'current_unanchored',
    # structural (contract 5.4)
    'scope_target_mismatch', 'umbrella_on_positive', 'inconsistent_status_time', 'part_of_invalid',
    'claim_unknown_event', 'lesion_unknown', 'reach_not_permitted', 'reach_inferred', 'visit_not_permitted',
    'scope_not_permitted',
)
# The identity rules' reasons (contract 6.2): identity.py gives them, in a target's identity_by.
IDENTITY_REASONS = ('identity_not_in_statement', 'identity_no_tie', 'identity_literal_conflict', 'identity_ambiguous',
                    'lesion_unverified')
# EB1 removed the passage guards; these are never given, by any module.
REMOVED_REASONS = ('foreign_date_in_passage', 'foreign_name_in_passage')
# The checks a record lists as having run on it.
CHECKS = (
    'passages_located', 'passage_places', 'words_in_own_passage', 'default', 'default_after_unlocated_words',
    'single_family', 'date_literal', 'name_tokens', 'size_literal', 'landmark_words', 'reach_device', 'device_words',
    'procedure_name', 'negation_marker', 'quantifier', 'duration_literal', 'label_words', 'planning_marker',
    'failure_marker', 'time_marker', 'occasion_marker', 'current_anchor', 'facility_marker', 'scope_permitted',
    'scope_target',
    'umbrella', 'status_time', 'part_of_reference', 'lesion_reference', 'reach_permitted', 'reach_source',
    'visit_permitted', 'lesion_site',
)
_ORDER = {reason: index for index, reason in enumerate(REASONS + IDENTITY_REASONS)}

POSITIVE = ('performed', 'attempted_not_completed')
NEGATIVE = ('not_performed', 'uncertain')
_TIME_WANTS = {'current_encounter': 0, 'earlier_encounter': -1, 'future': 1}
# The reasons time_state recomputes: the only ones that depend on the service date.
REEVALUATED = ('date_mismatch', 'date_unchecked')


def ordered(reasons) -> list:
    """``reasons`` once each, in the closed lists' order (an unknown reason is a programming error)."""
    unique = set(reasons)
    unknown = unique - set(_ORDER)
    if unknown:
        raise ValueError(f'Not a closed-list reason: {sorted(unknown)}.')
    return sorted(unique, key=_ORDER.__getitem__)


@dataclass(frozen=True)
class Verdict:
    """What one check found in an attribute's words: the checks that ran, the literals read, the reasons it fails."""
    checks: tuple = ()
    literals: dict = field(default_factory=dict)
    reasons: tuple = ()


def _verdict(checks, found: dict, reasons=()) -> Verdict:
    return Verdict(tuple(checks), {key: value for key, value in found.items() if value}, tuple(reasons))


# --- the checks, one per attribute (contract 5.3, C1; EB1-EB3): each reads the attribute's own words, ``text`` --------

def date_words(value: str, text: str) -> Verdict:
    """date_of_service and other_dates: the words hold exactly one date, and it is ``value`` (date_mismatch). A full value
    (YYYY-MM-DD, and "", which none equals) is read against the full dates in the words, exactly one; a month or a year
    (YYYY-MM, YYYY: an other date read.date_error admits at its own precision) against every date literal in the words,
    exactly one, of that precision and equal to it - so a month value whose words state a day is a mismatch."""
    if len(value) in (4, 7):
        found = literals.dates(text)
        precision = literals.MONTH if len(value) == 7 else literals.YEAR
        ok = len(found) == 1 and found[0].precision == precision and found[0].iso == value
    else:
        found = literals.full_dates(text)
        ok = len(found) == 1 and found[0].value.isoformat() == value
    return _verdict(('date_literal',), {'dates': [_date_record(item) for item in found]},
                    () if ok else ('date_mismatch',))


def _date_record(literal: literals.DateLiteral) -> dict:
    return {'value': literal.iso, 'precision': literal.precision}


def time_words(value: str, text: str, service_date: Optional[date]) -> Verdict:
    """time, stated (EB2): every date literal in the words compares, at its own precision, as ``value`` requires - the
    same for current_encounter, before for earlier_encounter, after for future (date_mismatch); a literal with no
    service date established leaves an earlier or future time unverified (date_unchecked). With no date literal, an
    earlier or future time needs a time marker in the words (time_marker_missing; C1, EB3).
    DECISIONS D35: a current_encounter time whose words carry a marker of another occasion (lexicon.other_occasion: a
    C1 earlier or future marker, or "original") is unverified (other_occasion), date literal or not - "At the original
    procedure" given as the words of a time Gemini calls current. The words are read for that marker only where they
    contradict the value; an earlier or future time is read exactly as before, so no exclusion changes (EB3).
    DECISIONS D54 (amends D42): a current_encounter time given words is verified only when those words carry a date
    literal at day precision (read by the date check above: equal to the service date, or date_mismatch) or are made
    only of whole present-encounter frames (lexicon.current_frame: "today", "this examination", "during the present
    encounter", "Today, on withdrawal"); otherwise it is unverified (current_unanchored) - "These were the findings at
    her index colonoscopy", "At the index procedure, on withdrawal", "At her index colonoscopy in November 2026". A year
    or a month no longer anchors: one that differs from the service date still gives date_mismatch, beside it. D35's
    marker stands alone where found. A current time given NO words stays Gemini's reading (EB2)."""
    found = literals.dates(text)
    records = [_date_record(item) for item in found]
    if found:
        verdict = _verdict(('date_literal',), {'dates': records}, _date_reasons(value, records, service_date))
    elif value in ('earlier_encounter', 'future'):
        kind = 'earlier' if value == 'earlier_encounter' else 'future'
        marks = lexicon.markers(kind, text)
        return _verdict(('date_literal', 'time_marker'), {'markers': list(marks)},
                        () if marks else ('time_marker_missing',))
    else:
        verdict = _verdict(('date_literal',), {})
    if value != 'current_encounter':
        return verdict
    marks = lexicon.other_occasion(text)
    # D54: worded, with no date literal at day precision and no marker of another occasion (D35's reason then stands
    # alone), a current time's words must be made only of whole present-encounter frames
    day = sorted((item for item in found if item.precision == literals.DAY), key=lambda item: item.start, reverse=True)
    rest = text
    for item in day:  # D64: a same-day date anchors only words that name nothing else
        rest = rest[:item.start] + ' ' + rest[item.end:]
    dated = bool(day) and lexicon.dated_frame(rest)
    unanchored = (bool(lexicon.fold(text).strip()) and not dated and not marks
                  and not lexicon.current_frame(text))
    return _verdict(verdict.checks + ('occasion_marker', 'current_anchor'), {**verdict.literals, 'markers': list(marks)},
                    verdict.reasons + (('other_occasion',) if marks else ()) + (('current_unanchored',) if unanchored
                                                                                else ()))


def _date_reasons(value: str, records: Sequence[Mapping], service_date: Optional[date]) -> tuple:
    if not records or value not in _TIME_WANTS:
        return ()
    if service_date is None:
        return ('date_unchecked',) if value != 'current_encounter' else ()
    want = _TIME_WANTS[value]
    for record in records:
        when = literals.stored_date(record.get('value'), record.get('precision'))
        if when is None or literals.compare(when, record['precision'], service_date) != want:
            return ('date_mismatch',)
    return ()


def performer_words(value: str, text: str, team: Sequence[Sequence[literals.Name]]) -> Verdict:
    """performer, stated (contract 5.3; EB2). ``team`` holds one entry per member - the documenting endoscopist, then
    each team member - and each entry is the names read in that member's own verified words. A member is its entry,
    not one parsed name: "Okafor, Grace, MD" reads as two names (literals.names splits at commas) and is one person.
    - documenting_team: every name in the words is a member's name - ALL of its tokens are tokens of ONE member - else
      name_mismatch (also when the team has no verified name: a name cannot be confirmed). Words naming no one pass.
      A token shared with the team is not enough (EB2: a name "that is not the documenting endoscopist or a listed
      team member leaves the performer unverified"): "Dr. Michael Grace" is not Grace Okafor, and "Dr. Grace Lee" is
      neither Grace Okafor nor Robin Lee.
    - other_clinician, other_facility: no name in the words shares a token with any member, else name_not_other (also
      when the team has no verified name: "another" cannot be established, contract 8.3). other_facility with no
      person name (titled or credentialed) needs a facility marker (facility_marker_missing; C1, EB3)."""
    names = literals.names(text)
    members = [tokens for tokens in (literals.name_tokens(tuple(member)) for member in team) if tokens]
    tokens = frozenset().union(*members)
    found = {'names': [name.as_record() for name in names]}
    reasons, checks = [], ['name_tokens']
    if value == 'documenting_team':
        if names and not all(any(set(name.tokens) <= member for member in members) for name in names):
            reasons.append('name_mismatch')
    elif value in ('other_clinician', 'other_facility'):
        if names and (not tokens or any(set(name.tokens) & tokens for name in names)):
            reasons.append('name_not_other')
        if value == 'other_facility' and not any(name.titled or name.credentialed for name in names):
            checks.append('facility_marker')
            marks = lexicon.markers('facility', text)
            found['markers'] = list(marks)
            if not marks:
                reasons.append('facility_marker_missing')
    return _verdict(checks, found, reasons)


def size_words(text: str) -> Verdict:
    """A lesion's size words hold a number with mm or cm (ranges allowed), read in millimetres (size_missing)."""
    sizes = literals.sizes_mm(text)
    return _verdict(('size_literal',), {'sizes_mm': list(sizes)}, () if sizes else ('size_missing',))


def landmark_words(value: str, text: str) -> Verdict:
    """A target's, a lesion's or an anatomy entry's landmark (contract 5.3): the words name it or a landmark it contains
    (landmark_missing), and every landmark they name is it, contains it or is contained by it - one at least must be
    (landmark_conflict when none is). ``other`` has no surface form: only the conflict is checked."""
    named = lexicon.landmarks_named(text)
    found = {'landmarks': list(named)}
    if value == 'other':
        return _verdict(('landmark_words',), found, ('landmark_conflict',) if named else ())
    if not named:
        return _verdict(('landmark_words',), found, ('landmark_missing',))
    if not any(lexicon.compatible(value, name) for name in named):
        return _verdict(('landmark_words',), found, ('landmark_conflict',))
    if not any(value == name or lexicon.contains(value, name) for name in named):
        return _verdict(('landmark_words',), found, ('landmark_missing',))
    return _verdict(('landmark_words',), found)


def reach_words(value: str, text: str) -> Verdict:
    """A reach's landmark (contract 5.3, reach row): landmark_words, and the guard - applied to the reach's own words
    (EB1), never its passage - that a non-scope device named there with no scope means a device's reach (device_reach)."""
    verdict = landmark_words(value, text)
    if lexicon.device_reach(text):
        return Verdict(verdict.checks + ('reach_device',), verdict.literals, verdict.reasons + ('device_reach',))
    return Verdict(verdict.checks + ('reach_device',), verdict.literals, verdict.reasons)


def device_words(value: str, text: str) -> Verdict:
    """technique: the words hold a surface form of the device class (device_missing; lexicon.device_named). ``other``
    has no surface form and is bound by its words alone."""
    if value in lexicon.UNCHECKED_DEVICES:
        return Verdict()
    named = lexicon.device_named(value, text)
    return _verdict(('device_words',), {'devices': [value] if named else []}, () if named else ('device_missing',))


def procedure_words(value: str, text: str, several: bool) -> Verdict:
    """procedure, stated: with several current procedural families the words must name the claimed one
    (procedure_name_missing); with one or none, the words locating is the binding (contract 5.3)."""
    if not several:
        return Verdict()
    ok = lexicon.procedure_named(value, text)
    return _verdict(('procedure_name',), {}, () if ok else ('procedure_name_missing',))


def status_words(value: str, text: str) -> Verdict:
    """status: not_performed needs a negator or a non-performance word (negation_missing); planned a planning marker
    (planning_missing) and attempted_not_completed a failure marker (failure_missing; C1, EB3); performed and uncertain
    are bound by their words alone."""
    if value == 'not_performed':
        negators = lexicon.negation(text)
        return _verdict(('negation_marker',), {'negators': list(negators)}, () if negators else ('negation_missing',))
    if value in ('planned', 'attempted_not_completed'):
        kind = 'planning' if value == 'planned' else 'failure'
        marks = lexicon.markers(kind, text)
        return _verdict((f'{kind}_marker',), {'markers': list(marks)}, () if marks else (f'{kind}_missing',))
    return Verdict()


def scope_words(value: str, text: str) -> Verdict:
    """scope all_of_kind needs a quantifier in its words (quantifier_missing). Every other scope, ``exceptive``
    included (ADJUDICATION C-7: verified as words, never through a list), is bound by its words alone."""
    if value != 'all_of_kind':
        return Verdict()
    found = lexicon.found(text, lexicon.QUANTIFIERS)
    return _verdict(('quantifier',), {'quantifiers': list(found)}, () if found else ('quantifier_missing',))


def basis_words(value: str, text: str) -> Verdict:
    """A visit's basis: total_time needs a duration (duration_missing), medical_decision_making the label "decision
    making" or "MDM" (label_missing)."""
    if value == 'total_time':
        minutes = literals.durations_min(text)
        return _verdict(('duration_literal',), {'minutes': list(minutes)}, () if minutes else ('duration_missing',))
    if value == 'medical_decision_making':
        labels = lexicon.found(text, lexicon.DECISION_LABELS)
        return _verdict(('label_words',), {'labels': list(labels)}, () if labels else ('label_missing',))
    return Verdict()


def separate_words(value: str, text: str) -> Verdict:
    """A visit's separate identifiability denied needs a negator or a non-performance word (negation_missing)."""
    if value != 'denied':
        return Verdict()
    negators = lexicon.negation(text)
    return _verdict(('negation_marker',), {'negators': list(negators)}, () if negators else ('negation_missing',))


def identity_literals(text: str) -> dict:
    """The size and distance literals in a target's or a lesion site's words, recorded for the identity and
    distinctness rules (contract 6.2-6.3); never a failure here."""
    return {key: value for key, value in (('sizes_mm', list(literals.sizes_mm(text))),
                                          ('distances_cm', list(literals.distances_cm(text)))) if value}


# --- the structural rules (contract 5.4) -------------------------------------------------------------------------------

def scope_permitted(status: str) -> bool:
    """A scope is stated only on a not_performed or uncertain statement."""
    return status in NEGATIVE


def scope_fits(scope: str, lesion: str, defined: bool, landmark: str, listed: int) -> bool:
    """A scope's target rule (contract 5.4). ``lesion`` is the target's lesion id as the answer gives it, ``defined``
    whether the answer defines that id, ``landmark`` the target's landmark and ``listed`` how many defined lesion ids
    the scope lists. Each arm reads the target the way that leaves a doubtful scope unverified:
    - single_target needs a defined target lesion or a landmark;
    - listed_targets needs two or more defined lesion ids;
    - all_of_kind needs an empty target: no lesion id at all - an id the answer does not define still ties the statement
      to a lesion, so it is not about every act of its kind - and landmark not_stated.
    Other scopes have no target rule."""
    if scope == 'single_target':
        return defined or landmark != 'not_stated'
    if scope == 'listed_targets':
        return listed >= 2
    if scope == 'all_of_kind':
        return not lesion and landmark == 'not_stated'
    return True


def umbrella_fits(kind: str, status: str) -> bool:
    """``intervention`` is a statement about every intervention, never a positive act (umbrella_on_positive)."""
    return not (kind == 'intervention' and status in POSITIVE)


def status_time_consistent(status: str, time: str) -> bool:
    """Not performed or attempted in the future, and not planned in an earlier encounter."""
    return not ((status in POSITIVE and time == 'future') or (status == 'planned' and time == 'earlier_encounter'))


def single_family(kind: str, procedure: str, families: frozenset) -> bool:
    """The procedure default's guard (contract 5.3): an E/M visit event takes its family from its kind (any E/M
    family); any other event's family must be the one procedural family the current positive procedural events claim."""
    if kind in lexicon.EM_KINDS:
        return procedure in lexicon.EM_PROCEDURES
    return len(families) == 1 and lexicon.family_of(procedure) in families


def reach_permitted(event: Mapping, reach_text: str) -> bool:
    """A reach is the extent of an endoscope's examination of this encounter (contract 5.4, as EB1 reads it): its event
    is an examination whose time is a usable current_encounter, whose status is a usable performed or
    attempted_not_completed, and whose technique is a usable endoscope - or not_stated with a scope named in the
    reach's own words (``reach_text``, the document's slice; '' when they did not locate)."""
    time, status, technique = event['time'], event['status'], event['technique']
    if event['kind']['value'] != 'examination':
        return False
    if not (usable(time) and time['value'] == 'current_encounter'):
        return False
    if not (usable(status) and status['value'] in POSITIVE):
        return False
    if technique['value'] == 'endoscope':
        return usable(technique)
    return technique['value'] == 'not_stated' and lexicon.scope_named(reach_text)


# DECISIONS D36: the attributes whose passages are an event's own - the passages it cites for its statement.
CITING = ('procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope', 'purpose')


def cites(event: Mapping, pid: str) -> bool:
    """D36: whether one of ``event``'s statement attributes (CITING) cites passage ``pid``."""
    return any(isinstance(event.get(name), Mapping) and pid in (event[name].get('passages') or ()) for name in CITING)


def reach_stated(passages: Sequence[str], examination: Mapping, session: Sequence[Mapping]) -> bool:
    """DECISIONS D36: whether a reach is its examination's own statement and not inferred from where the session's acts
    were done. ``passages`` are the reach's cited passages that hold its words, ``examination`` its event and
    ``session`` the other events of that event's family. True when one of those passages belongs to the examination
    (it cites it) or to no other event of the session ("Cecum reached." on its own line); False when each belongs only
    to other events of the session - a biopsy's sentence, "Biopsies of the ascending colon were taken", or an act's
    finding (reach_inferred). Structural, over Gemini's own citations: no word is read."""
    return any(cites(examination, pid) or not any(cites(event, pid) for event in session) for pid in passages)


# --- reading an attribute ----------------------------------------------------------------------------------------------

def usable(attribute) -> bool:
    """Whether a consumer may rely on an attribute: verified (stated or a default), and not opened by an open question
    (contract 5.5: an open attribute is treated as an unverified one)."""
    return isinstance(attribute, Mapping) and attribute.get('state') == 'verified' and not attribute.get('open')


def exclusion_basis(name: str, attribute) -> str:
    """The evidence a usable attribute gives for an exclusion (FINAL C1: every exclusion records ``literal`` or
    ``marker``; there is no wording-only exclusion): 'literal' for a negator (status not_performed), a compared date
    literal (time earlier_encounter or future) or a person name with a title or credential (performer other_clinician
    or other_facility); 'marker' for a C1 marker (status planned or attempted_not_completed, time without a date,
    other_facility without a person name); '' otherwise, including for any attribute that is not usable."""
    if not usable(attribute):
        return ''
    value, found = attribute.get('value'), attribute.get('literals') or {}
    if name == 'status':
        if value == 'not_performed' and found.get('negators'):
            return 'literal'
        if value in ('planned', 'attempted_not_completed') and found.get('markers'):
            return 'marker'
    elif name == 'time' and value in ('earlier_encounter', 'future'):
        if found.get('dates'):
            return 'literal'
        if found.get('markers'):
            return 'marker'
    elif name == 'performer' and value in ('other_clinician', 'other_facility'):
        if any(item.get('titled') or item.get('credentialed') for item in found.get('names', ())):
            return 'literal'
        if value == 'other_facility' and found.get('markers'):
            return 'marker'
    return ''


def time_state(attribute: Mapping, effective_date) -> dict:
    """A stored time attribute judged again against ``effective_date`` (a date, a YYYY-MM-DD string, or None), with no
    text read and nothing sent (contract 5.3, "re-evaluated, not re-read"; 8.2, D8): a copy of the record whose
    date-dependent reasons (REEVALUATED) are recomputed from its stored date literals, and whose state follows. A
    default, absent or discarded time, and every other reason, is kept as stored. ValueError for an effective date that
    is no date."""
    record = copy.deepcopy(dict(attribute))
    if (record.get('basis') != 'stated' or record.get('state') == 'discarded'
            or record.get('value') not in _TIME_WANTS):
        return record
    service = _as_date(effective_date)
    stored = (record.get('literals') or {}).get('dates') or []
    reasons = [reason for reason in record.get('reasons', ()) if reason not in REEVALUATED]
    reasons += _date_reasons(record['value'], stored, service)
    record['reasons'] = ordered(reasons)
    record['state'] = 'unverified' if record['reasons'] else 'verified'
    return record


def _as_date(value) -> Optional[date]:
    if value is None or (isinstance(value, date) and not hasattr(value, 'hour')):
        return value
    if isinstance(value, str):
        parsed = literals.iso_date(value)
        if parsed is not None:
            return parsed
    raise ValueError('An effective date is a date, a YYYY-MM-DD string or None.')
