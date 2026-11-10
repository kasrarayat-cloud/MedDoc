"""Normalization of one accepted answer into the persisted event inventory (design/contract.md 4 and 5; design/FINAL.md
C1-C2; design/ADJUDICATION.md EB1-EB4): ``normalize(parsed, revision_text)`` gives an Inventory whose parts are the
EventInventory row's content (store.row). Pure and DB-free; the interpret stage runs it under bounded.run_bounded.

The steps, in the order their inputs require (contract 4.1 lists them by subject):
1. Passages. Each passage is located by participants.reading.Locator - whitespace runs collapsed, nothing else
   normalized, at least 8 non-space characters, at most 8 places - and is ``located`` (one place), ``ambiguous`` (2 to
   8) or ``unlocated`` (stored by its length only, never its text). The closing-bracket rule (contract 5.1) then extends
   a located span whose brackets of one kind - ( [ { and the curly double quote - open more than they close, when the
   revision text's next characters, after at most one run of spaces, are exactly the missing closers. It only ever adds
   the document's own closers to a span that already located.
2. The open questions are read first (step 7 of the contract), so every attribute an open question names is built
   ``open`` and every later rule sees it (an open attribute is treated as an unverified one, contract 5.5).
3. The documenting endoscopist and the team: their words bound like an attribute's, their names read (literals.names);
   each entry is one member of the team the performer check reads (verify.performer_words) - except, for a
   documenting_team performer, a team entry whose own words ARE that performer's words: the act's own performer
   statement listed again as the team confirms nothing about it (Draft._team_for).
4. The date of service and every other date, each verified by its own date literal (contract 8.1).
5. Lesions: the description, the site (landmark words) and the size (size literal), each in the lesion's own passages.
6. Events: every attribute bound to its OWN passages by its OWN words (5.2, below), its literal check run on those
   words alone (EB1); then the structural rules (5.4); then the model's contradicts[] claims (an unknown or own event is
   a dismissed claim; the rest are handed to the relations step).
7. Reach (attached to its examination only when permitted, 5.4; DECISIONS D36: unverified, reach_inferred, when its
   words stand only in passages of the session's other events), visit facts (to an em_visit event), anatomy.
8. The steps of slice S03, LINKED_STEPS: lesion distinctness and act-to-lesion identity (6.2-6.3), pairing, model
   claims, steps and bundling identity (6.4-6.6), and the mapping fields (9.1). Each is resolved by name when normalize
   runs and is called with the Draft; a missing one RAISES - normalization never proceeds without it.
9. Derived encounter facts: current examination families, procedure_day (D21; 8.3), absent structures.
10. The verification report (4.3): counts per attribute, reasons, relations, discarded entries, problems.

Binding (contract 5.2, FINAL C2). An attribute's passage ids must name passages of this answer that located (unknown:
``passage_unknown``; unlocated: ``passage_unlocated``). Its words are searched inside the whitespace-collapsed text of
those passages' spans - for an ambiguous passage, its first place - with no minimum length: first exactly, then after
the narrow typographic normalization (NFKC, case folding, hyphens and dashes as spaces, curly quotes straight; ``match:
normalized``). An occurrence counts only where it does not split a word at either end, so the words "not" are never
found inside "another" (a refinement of C2's substring search, recorded as a deviation of slice S02). The first
occurrence is kept with ``occurrences: n``; the words record is always the revision text's own slice. Words found only
in a passage the attribute does not cite never count. The basis is ``stated`` (words located), ``default`` (no words,
and a frame default: time current_encounter, performer documenting_team - EB2, accepted with no guard - or a procedure
the single-family guard settles) or ``absent`` (the not-stated value). A default value whose words fail to locate falls
back to the default, the problem recorded - unless those words hold a date that is not the service date or (DECISIONS
D35) a marker of another occasion (time), or a name that is not a team member's (performer): EB2 reads given words
whether or not they locate, for that literal only (the procedure default falls back whatever its unlocated words lack),
and nothing of them is stored. Any other value with no words, or words that do not locate, is unverified.

Normalization never merges, splits, renumbers or drops an event or a lesion; an event every check fails stays, with its
states and reasons. No model-written string is stored: every value is an enumeration value, a defined id, an ISO date or
a slice of the revision text; an id the answer cites but does not define is counted, never stored (P9).
"""
from __future__ import annotations

import copy
import hashlib
import importlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from studio.interpretation import LABEL, lexicon, literals, schema, verify
from studio.interpretation.read import Refusal
from studio.participants.reading import TOO_SHORT, Locator
from studio.types import sha256_json

# The steps of contract 4.1 that the modules of slice S03 own, in the order normalize runs them on the Draft: each is
# (module, function), resolved when normalize runs and called as function(draft); it changes the draft in place.
# - identity.distinguish: every lesion's distinct_from and possibly_same_as (6.3);
# - identity.link: every event target's identity and identity_by for a DEFINED lesion (6.2) - normalize has already set
#   identity 'unresolved' for those, and 'none' (with lesion_unknown in identity_by) for an undefined one;
# - relations.relate: the relations (6.4-6.6) through Draft.relation, from Draft.claims and the events;
# - mapping.map_events: every event's catalogue_kind, code_technique and key (9.1); normalize sets ``family``.
LINKED_STEPS = (
    ('studio.interpretation.identity', 'distinguish'),
    ('studio.interpretation.identity', 'link'),
    ('studio.interpretation.relations', 'relate'),
    ('studio.interpretation.mapping', 'map_events'),
)

LOCATED, AMBIGUOUS, UNLOCATED = 'located', 'ambiguous', 'unlocated'
OTHER_ROLES = ('birth', 'other_occurrence', 'other_document', 'report_time', 'unclear')
OPENERS = {'(': ')', '[': ']', '{': '}', '\u201c': '\u201d'}
_CLOSERS = frozenset(OPENERS.values())
# The open questions' ``about`` values that open an attribute of the same name on each listed event.
EVENT_ABOUT = frozenset({'procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope', 'extent',
                         'completion', 'visit_basis'})
# The attributes whose meaning does not depend on where their words stand (S16 repair round 2): the technique (a
# device's surface form) names the same device wherever its words are, and no consumer reads its place - coverage reads
# the kind, status, time and target words (C-10), identity the kind, status and target, the relations values and
# states. Its words may bind where a passage too short for the Locator to place stands (Draft._place_free).
# The procedure is NOT place-free: DECISIONS D37 withdrew it. Bound at the places of a heading too short to place ("EGD",
# found in a title and a heading alike), it verified the procedure of acts Gemini read in a reproduced outside report as
# today's, and turned W1S-075, -076, -171 (and, on FRESH-1, -193) 43239 from held to READY against the registry's
# expected NOT_READY - a regression by the owner's rule of 2026-11-09. A procedure cited only from such a heading stays
# unverified.
# Time, status, scope, performer, kind, target and purpose are bound to places too: where their words stand decides
# which statement, act and code they cover, so an unplaced passage never binds them.
PLACE_FREE = ('technique',)
# What the verification report counts, by attribute (contract 4.3).
COUNTED = ('procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope', 'purpose', 'part_of',
           'reach', 'completion', 'visit_basis', 'separately_identifiable', 'lesion', 'lesion_site', 'lesion_size',
           'date_of_service', 'other_dates', 'documenting_endoscopist', 'team', 'anatomy')


@dataclass(frozen=True)
class Inventory:
    """One normalized answer: the content of its EventInventory row (contract 4.3) - ``events`` ({passages, lesions,
    events, relations}), ``encounter_facts``, ``open_questions`` and the ``verification`` report - and the sha256 of
    the revision text it was made from. store.row adds the run's request and response sha256 to the report and the
    bindings, and hashes the row; ``sha256`` here is the content's own hash, stable for the same answer and text."""
    text_sha256: str
    events: dict
    encounter_facts: dict
    open_questions: list
    verification: dict

    @property
    def sha256(self) -> str:
        return sha256_json({'label': LABEL, 'text_sha256': self.text_sha256, 'events': self.events,
                            'encounter_facts': self.encounter_facts, 'open_questions': self.open_questions,
                            'verification': self.verification})

    def content(self) -> dict:
        """The keyword arguments store.row takes for the content (a deep copy)."""
        return copy.deepcopy({'events': self.events, 'encounter_facts': self.encounter_facts,
                              'open_questions': self.open_questions, 'verification': self.verification})


@dataclass(frozen=True)
class _Default:
    """Whether a value with no words (or unlocated words) may be accepted as a frame default, with the guard's checks
    and, when it may not, why. ``deny`` reads the words Gemini gave for a default value that do not locate, for the one
    literal EB2 lets deny the default: a date in a time's words that is not the service date - or (DECISIONS D35) a
    marker of another occasion in them - and a name in a performer's words that is not a team member's. None where no
    given word denies the default (the procedure default, contract 5.2)."""
    allowed: bool
    checks: tuple = ()
    reasons: tuple = ()
    deny: Optional[Callable[[str], verify.Verdict]] = None


def normalize(parsed: Mapping, revision_text: str, pages: Sequence = ()) -> Inventory:
    """The inventory of ``parsed`` - an answer read.read accepted (never a Refusal) - against ``revision_text``, the text
    the request was built from. ``pages`` is accepted as the contract's signature names it and is not read: passages are
    located in the revision text, which the pages tile, and no page number is stored. Pure; raises only on a programming
    error, an input that is not an accepted answer, or a linked step that cannot be resolved."""
    if isinstance(parsed, Refusal) or not isinstance(parsed, Mapping):
        raise TypeError('normalize reads an answer read.read accepted, never a refusal.')
    if not isinstance(revision_text, str):
        raise TypeError('The revision text must be a string.')
    draft = Draft(parsed, revision_text)
    draft.build()
    for module, name in LINKED_STEPS:
        getattr(importlib.import_module(module), name)(draft)
    return draft.finish()


class Draft:
    """The inventory under construction. What a linked step (LINKED_STEPS) may read and change:
    - ``passages``, ``lesions``, ``events``: {id: record} in the answer's order, each record in its stored shape (4.3);
    - ``claims``: the model's contradicts[] entries naming another existing event, [{'statement', 'event',
      'passages'}] - unknown and own-event claims are already dismissed relations;
    - ``identity_open``: the events whose target identity an open question leaves open;
    - ``relations`` (add through ``relation``), ``encounter`` (the encounter facts), ``problems`` (CPT Studio's
      sentences) and ``discarded`` ({'where', 'reason'});
    - ``service_date``: the verified, unopened date of service, or None; ``revision_text`` and ``answer`` (the parsed
      answer) for reference only - a step reads no text for meaning (EB1) and stores no model string (P9);
    - ``passages_of(span)``: the located or ambiguous passages whose place holds a span.
    A target's identity_by may carry {'reasons': [...]} from verify.IDENTITY_REASONS; the report counts them."""

    def __init__(self, parsed: Mapping, revision_text: str):
        self.answer = parsed
        self.revision_text = revision_text
        self.passages: dict = {}
        self.lesions: dict = {}
        self.events: dict = {}
        self.relations: list = []
        self.claims: list = []
        self.identity_open: frozenset = frozenset()
        self.encounter: dict = {}
        self.open_questions: list = []
        self.problems: list = []
        self.discarded: list = []
        self.service_date: Optional[date] = None
        self._opened: set = set()
        self._date_open = False
        self._team: tuple = ()
        self._members: tuple = ()  # (names, own words span, is a team entry) per member, in self._team's order
        self._tallied: list = []
        self._hay: dict = {}

    # --- the steps -------------------------------------------------------------------------------------------------

    def build(self) -> None:
        self._locate_passages()
        self._read_openings()
        self._bind_names()
        self._bind_date()
        self._bind_lesions()
        self._bind_events()
        self._attach_reach()
        self._attach_visits()
        self._bind_anatomy()

    def finish(self) -> Inventory:
        self._derive()
        self._finish_questions()
        events = {'passages': list(self.passages.values()), 'lesions': list(self.lesions.values()),
                  'events': list(self.events.values()), 'relations': list(self.relations)}
        return Inventory(text_sha256=hashlib.sha256(self.revision_text.encode('utf-8')).hexdigest(),
                         events=events, encounter_facts=self.encounter, open_questions=self.open_questions,
                         verification=self._report())

    def relation(self, type: str, *, statement: str, event: str, attribute: str = '', reason: str = '',
                 claimed_by_model: bool = False, passages: Sequence = ()) -> dict:
        """Add a relation (4.3) with the next id (R1, R2, ...), its passages limited to this answer's passage ids."""
        record = {'id': f'R{len(self.relations) + 1}', 'type': type, 'statement': statement, 'event': event,
                  'attribute': attribute, 'reason': reason, 'claimed_by_model': claimed_by_model,
                  'passages': [pid for pid in passages if pid in self.passages]}
        self.relations.append(record)
        return record

    def passages_of(self, span: Mapping) -> list:
        """The ids of the located or ambiguous passages one of whose places holds ``span`` (a {start, end} record)."""
        return [pid for pid, record in self.passages.items() if record['state'] != UNLOCATED and any(
            place['start'] <= span['start'] and span['end'] <= place['end'] for place in record['spans'])]

    # --- 1. passages ---------------------------------------------------------------------------------------------------

    def _locate_passages(self) -> None:
        locator = Locator(self.revision_text)
        for index, raw in enumerate(self.answer['passages']):
            located = locator.locate(raw['text'])
            spans, extended = [], ''
            for found in located.spans:
                end = closing_bracket_end(self.revision_text, found.start, found.end)
                if end != found.end:
                    extended = 'closing_bracket'
                spans.append({'start': found.start, 'end': end, 'text': self.revision_text[found.start:end]})
            state = UNLOCATED if not spans else LOCATED if len(spans) == 1 else AMBIGUOUS
            self.passages[raw['id']] = {'id': raw['id'], 'state': state, 'spans': spans,
                                        'reason': located.reason if not spans else '', 'chars': len(raw['text']),
                                        'extended': extended}
            if not spans:
                why = 'is too short to locate' if located.reason == 'too short' else 'was not found'
                self.problems.append(f'passages[{index}] {why} in the revision text.')

    # --- 2. the open questions' openings (contract 4.1 step 7) ----------------------------------------------------------

    def _read_openings(self) -> None:
        events = {item['id'] for item in self.answer['events']}
        identity = set()
        for question in self.answer['open_questions']:
            about = question['about']
            listed = [eid for eid in question['events'] if eid in events]
            if about in EVENT_ABOUT:
                self._opened.update((eid, about) for eid in listed)
            elif about == 'contradiction':
                self._opened.update((eid, 'status') for eid in listed)
            elif about == 'identity':
                identity.update(listed)
            elif about == 'date_of_service':
                self._date_open = True
        self.identity_open = frozenset(identity)

    # --- binding (contract 5.2, FINAL C2) ------------------------------------------------------------------------------

    def _known(self, ids: Sequence, where: str) -> list:
        known = [pid for pid in ids if pid in self.passages]
        unknown = len(ids) - len(known)
        if unknown:
            self.problems.append(f'{where} cites {unknown} passage id{"s" if unknown != 1 else ""} the answer does not '
                                 'define.')
        return known

    def _bind(self, where: str, raw: Mapping, value, *, absent: bool = False, default: Optional[_Default] = None,
              check: Optional[Callable[[str], verify.Verdict]] = None, opened: bool = False,
              span_check: Optional[Callable[[Mapping], verify.Verdict]] = None, place_free: bool = False) -> dict:
        """The attribute record (contract 4.2) of ``raw`` ({words, passages}) for ``value``. ``span_check``, when given,
        is the check of located words that also needs where they are (the performer's: _team_for); ``check`` reads
        their text alone."""
        ids = list(raw.get('passages', ()))
        known = self._known(ids, where)
        record = {'value': value, 'basis': 'absent', 'state': 'absent', 'open': bool(opened), 'words': None,
                  'passages': known, 'checks': [], 'literals': {}, 'reasons': []}
        if absent:
            return record
        words = raw.get('words', '')
        if not has_words(words):
            if default is not None and default.allowed:
                return self._defaulted(record, default)
            failure = list(default.reasons) if default is not None and default.reasons else ['words_missing']
            return self._failed(record, failure, default.checks if default is not None else ())
        usable = [self.passages[pid] for pid in known if self.passages[pid]['state'] != UNLOCATED]
        span = self._locate_words(words, usable) if usable else None
        located = 'passages_located'
        if span is None and place_free:
            span, located = self._place_free(words, known), 'passage_places'
        if span is None:
            if usable:
                return self._fall_back(record, where, ['words_unlocated'], default, words)
            failure = (['passage_unknown'] if len(known) < len(ids) else []) + (
                ['passage_unlocated'] if len(usable) < len(known) else [])
            failure = failure or ['words_unlocated']
            return self._fall_back(record, where, failure, default, words)
        record.update(basis='stated', words=span)
        record['checks'] = [located, 'words_in_own_passage']
        if check is not None or span_check is not None:
            verdict = span_check(span) if span_check is not None else check(span['text'])
            record['checks'] += list(verdict.checks)
            record['literals'] = dict(verdict.literals)
            record['reasons'] = verify.ordered(verdict.reasons)
        record['state'] = 'unverified' if record['reasons'] else 'verified'
        return record

    @staticmethod
    def _defaulted(record: dict, default: _Default, extra: tuple = ()) -> dict:
        record.update(basis='default', state='verified', checks=['default', *extra, *default.checks], reasons=[])
        return record

    @staticmethod
    def _failed(record: dict, reasons, checks=()) -> dict:
        record.update(state='unverified', checks=list(checks), reasons=verify.ordered(reasons))
        return record

    def _fall_back(self, record: dict, where: str, failure: list, default: Optional[_Default], words: str) -> dict:
        """Words that do not bind: a default value falls back to its default, the problem recorded (5.2), because it
        would have been accepted with no words at all - unless the words Gemini gave state, by their own literal, what
        the default denies (EB2, which governs: "where Gemini DID give time words, a date literal in those words that
        differs from the service date leaves the time unverified", and so for a name in performer words that is not a
        team member's, and - DECISIONS D35 - for a marker of another occasion in time words: "At the original
        procedure" given for a current time denies it whether or not it locates). Only that literal is read
        (``default.deny``), never the attribute's other checks: the procedure default an E/M visit's kind settles falls
        back whatever its unlocated words lack. Nothing of the words is stored. Anything else is unverified with the
        failure."""
        if default is not None and default.allowed:
            verdict = default.deny(words) if default.deny is not None else verify.Verdict()
            if verdict.reasons:
                return self._failed(record, failure + list(verdict.reasons), verdict.checks)
            self.problems.append(f'{where}: its words were not found in its own passages, so the frame default was '
                                 'accepted.')
            return self._defaulted(record, default, ('default_after_unlocated_words',))
        reasons = failure + (list(default.reasons) if default is not None else [])
        return self._failed(record, reasons, default.checks if default is not None else ())

    def _locate_words(self, words: str, passages: list) -> Optional[dict]:
        """The first occurrence of ``words`` in the first of ``passages`` holding it - exact tier first, then normalized
        (FINAL C2) - as the revision text's own slice, or None."""
        for tier, needle in (('exact', ' '.join(words.split())), ('normalized', lexicon.fold(words))):
            if not needle:
                continue
            for passage in passages:
                hay, starts, ends = self._haystack(passage, tier)
                positions = _bounded_positions(hay, needle)
                if positions:
                    first = positions[0]
                    base = passage['spans'][0]['start']
                    start, end = base + starts[first], base + ends[first + len(needle) - 1]
                    return {'start': start, 'end': end, 'text': self.revision_text[start:end], 'match': tier,
                            'occurrences': len(positions)}
        return None

    def _place_free(self, words: str, pids: Sequence) -> Optional[dict]:
        """The words of a PLACE_FREE attribute cited from a passage too short for the Locator to place (fewer than its 8
        characters: a heading such as "Snare"): the passage's own text at EVERY place it stands in the revision text -
        whitespace collapsed, word-bounded, the exact tier then the normalized - and the words inside it there. The first
        occurrence is kept with ``occurrences``, how many there are over every place: more than one keeps the location
        ambiguous, as FINAL C2 records it. The passage itself stays unlocated (its text is never stored), so no rule that
        reads places sees it. None when the passage's text, or the words inside it, are not there."""
        given = {item['id']: item['text'] for item in self.answer['passages']}
        for pid in pids:
            record = self.passages.get(pid)
            if record is None or record['state'] != UNLOCATED or record['reason'] != TOO_SHORT:
                continue
            for tier, fold in (('exact', None), ('normalized', lexicon.fold_char)):
                needle = ' '.join(given[pid].split()) if fold is None else lexicon.fold(given[pid])
                inner = ' '.join(words.split()) if fold is None else lexicon.fold(words)
                if not needle or not inner:
                    continue
                hay, starts, ends = self._document(tier, fold)
                found = [at + offset for at in _bounded_positions(hay, needle)
                         for offset in _bounded_positions(needle, inner)]
                if found:
                    first = found[0]
                    start, end = starts[first], ends[first + len(inner) - 1]
                    return {'start': start, 'end': end, 'text': self.revision_text[start:end], 'match': tier,
                            'occurrences': len(found)}
        return None

    def _document(self, tier: str, fold) -> tuple:
        """The whole revision text, collapsed (and folded on the normalized tier), with each character's offsets."""
        key = ('', tier)
        if key not in self._hay:
            self._hay[key] = _mapped(self.revision_text, fold)
        return self._hay[key]

    def _haystack(self, passage: dict, tier: str) -> tuple:
        key = (passage['id'], tier)
        if key not in self._hay:
            self._hay[key] = _mapped(passage['spans'][0]['text'], lexicon.fold_char if tier == 'normalized' else None)
        return self._hay[key]

    # --- 3. the documenting endoscopist and the team (contract 8.3) ----------------------------------------------------

    def _bind_names(self) -> None:
        encounter = self.answer['encounter']
        entries = [('encounter.documenting_endoscopist', encounter['documenting_endoscopist'])]
        entries += [(f'encounter.team[{index}]', raw) for index, raw in enumerate(encounter['team'])]
        records, team, members = [], [], []
        for index, (where, raw) in enumerate(entries):
            bound = self._bind(where, raw, None, absent=not has_words(raw['words']))
            names = literals.names(bound['words']['text']) if bound['state'] == 'verified' else ()
            if names:  # one member per entry, whatever number of names the parser reads in it (verify.performer_words)
                team.append(names)
                members.append((names, bound['words'], index > 0))
            records.append({'state': bound['state'], 'words': bound['words'], 'passages': bound['passages'],
                            'checks': bound['checks'], 'reasons': bound['reasons'],
                            'names': [name.as_record() for name in names]})
        self._team = tuple(team)
        self._members = tuple(members)
        self.encounter['documenting_endoscopist'] = records[0]
        self.encounter['team'] = records[1:]
        self._tally('documenting_endoscopist', records[0])
        for record in records[1:]:
            self._tally('team', record)

    def _team_for(self, value: str, span: Mapping) -> tuple:
        """The members a performer's located words ``span`` are checked against (verify.performer_words; EB2). For
        documenting_team, a TEAM entry whose own words are those very words is left out: such an entry is the act's own
        performer statement listed again as the team ("Both done by Dr. Hale." read as Dr. Hale's membership), so it
        confirms nothing about it - EB2's "listed team member" is one the document lists, and an entry that IS the
        statement being checked would make any name its own confirmation. The documenting endoscopist is never left
        out, and the other values keep every member: their check (name_not_other) must not be weakened (EB3)."""
        if value != 'documenting_team':
            return self._team
        return tuple(names for names, words, team in self._members
                     if not (team and words and words['start'] < span['end'] and span['start'] < words['end']))

    # --- 4. the date of service and the other dates (contract 8.1) -----------------------------------------------------

    def _bind_date(self) -> None:
        raw = self.answer['encounter']['date_of_service']
        where = 'encounter.date_of_service'
        others = {role: [] for role in OTHER_ROLES}
        candidates = []
        for index, item in enumerate(raw['other_dates']):
            bound = self._bind(f'{where}.other_dates[{index}]', item, item['value'], absent=not item['value'],
                               check=lambda text, value=item['value']: verify.date_words(value, text))
            entry = {'value': item['value'], 'verified': bound['state'] == 'verified', 'words': bound['words'],
                     'passages': bound['passages'], 'reasons': bound['reasons']}
            self._tally('other_dates', bound)
            if item['role'] == 'this_encounter':
                if entry['verified']:
                    candidates.append(item['value'])
            else:
                others[item['role']].append(entry)
        record = {'state': raw['state'], 'value': None, 'verified': False, 'words': None, 'passages': [], 'reasons': [],
                  'candidates': [], 'readings': [], 'others': others}
        tally = {'state': 'absent', 'open': self._date_open, 'reasons': []}
        if raw['state'] == 'stated':
            value = raw['value']
            bound = self._bind(where, raw, value, check=lambda text: verify.date_words(value, text))
            if not value:
                bound = self._failed(bound, bound['reasons'] + ['date_mismatch'], bound['checks'])
            reasons = list(bound['reasons'])
            if any(candidate != value for candidate in candidates):  # Gemini gave this encounter another date as well
                reasons.append('date_mismatch')
                self.problems.append(f'{where}: the answer gives this encounter another date beside the one stated.')
            verified = not reasons and bound['state'] == 'verified'
            record.update(words=bound['words'], passages=bound['passages'], reasons=verify.ordered(reasons),
                          verified=verified and not self._date_open, value=value if verified and not
                          self._date_open else None)
            tally = {'state': 'verified' if verified else 'unverified', 'open': self._date_open,
                     'reasons': record['reasons']}
        elif raw['state'] == 'several':
            record['passages'] = self._known(list(raw['passages']), where)
            record['candidates'] = sorted(set(candidates))
            tally = {'state': 'verified' if record['candidates'] else 'unverified', 'open': self._date_open,
                     'reasons': []}
        record['readings'] = self._readings(record, others)
        self.encounter['date_of_service'] = record
        self._tally('date_of_service', tally)
        if record['verified']:
            self.service_date = literals.iso_date(record['value'])

    def _readings(self, record: dict, others: dict) -> list:
        """The full dates in the date's own words and own passages (8.1, for a member's date to settle an unverified
        one), never a date that is another role's: one inside another role's words, or of another role's value."""
        taken = [entry['words'] for entries in others.values() for entry in entries if entry['words']]
        values = {entry['value'] for entries in others.values() for entry in entries}
        places = [record['words']] if record['words'] else []
        places += [self.passages[pid]['spans'][0] for pid in record['passages']
                   if pid in self.passages and self.passages[pid]['state'] != UNLOCATED]
        readings = set()
        for place in places:
            for literal in literals.full_dates(place['text']):
                start, end = place['start'] + literal.start, place['start'] + literal.end
                if any(span['start'] < end and start < span['end'] for span in taken):
                    continue
                if literal.value.isoformat() not in values:
                    readings.add(literal.value.isoformat())
        return sorted(readings)

    # --- 5. lesions (contract 6.1) -------------------------------------------------------------------------------------

    def _bind_lesions(self) -> None:
        for index, raw in enumerate(self.answer['lesions']):
            where = f'lesions[{index}]'
            words = self._bind(f'{where}.words', raw, '')
            site_raw = {'words': raw['site_words'], 'passages': raw['passages']}
            site = self._bind(f'{where}.site', site_raw, raw['landmark'], absent=raw['landmark'] == 'not_stated',
                              check=lambda text, value=raw['landmark']: verify.landmark_words(value, text))
            if site['words']:
                site['literals'].update(verify.identity_literals(site['words']['text']))
            size = {'mm': [], 'span': None}
            size_tally = {'state': 'absent', 'open': False}
            reasons = list(words['reasons'])
            if has_words(raw['site_words']):
                reasons += site['reasons']
            if has_words(raw['size_words']):
                bound = self._bind(f'{where}.size', {'words': raw['size_words'], 'passages': raw['passages']}, '',
                                   check=verify.size_words)
                size = {'mm': list(bound['literals'].get('sizes_mm', [])), 'span': bound['words']}
                reasons += bound['reasons']
                size_tally = {'state': bound['state'], 'open': False}
            record = {'id': raw['id'], 'words': words['words'], 'landmark': raw['landmark'], 'site': site, 'size': size,
                      'multiplicity': raw['multiplicity'], 'passages': words['passages'],
                      'state': 'unverified' if reasons else 'verified', 'reasons': verify.ordered(reasons),
                      'distinct_from': [], 'possibly_same_as': []}
            self.lesions[raw['id']] = record
            self._tally('lesion', record)
            self._tally('lesion_site', site, reasons=False)
            self._tally('lesion_size', size_tally, reasons=False)

    # --- 6. events (contract 5.2-5.4) ----------------------------------------------------------------------------------

    def _bind_events(self) -> None:
        raws = self.answer['events']
        families = frozenset(
            lexicon.family_of(raw['procedure']['value']) for raw in raws
            if raw['status']['value'] in verify.POSITIVE and raw['time']['value'] == 'current_encounter'
            and lexicon.family_of(raw['procedure']['value']) in lexicon.PROCEDURAL_FAMILIES)
        for index, raw in enumerate(raws):
            self.events[raw['id']] = self._event(index, raw, families)
        self._part_of(raws)
        for index, raw in enumerate(raws):
            self._claims(index, raw)
        for record in self.events.values():
            record['positive'] = record['status']['value'] in verify.POSITIVE
            record['current'] = _current(record['time'])
            for name in ('procedure', 'kind', 'technique', 'target', 'time', 'performer', 'status', 'scope', 'purpose',
                         'part_of'):
                self._tally(name, record[name])

    def _event(self, index: int, raw: Mapping, families: frozenset) -> dict:
        eid, where = raw['id'], f'events[{index}]'

        def opened(name: str) -> bool:
            return (eid, name) in self._opened

        def bind(name: str, value, **options) -> dict:
            return self._bind(f'{where}.{name}', raw[name], value, opened=opened(name), **options)

        procedure, kind = raw['procedure']['value'], raw['kind']['value']
        technique, time = raw['technique']['value'], raw['time']['value']
        performer, status = raw['performer']['value'], raw['status']['value']
        scope, purpose = raw['scope']['value'], raw['purpose']['value']
        settled = verify.single_family(kind, procedure, families)

        def time_check(text: str) -> verify.Verdict:
            return verify.time_words(time, text, self.service_date)

        def performer_check(text: str) -> verify.Verdict:
            return verify.performer_words(performer, text, self._team)

        def performer_span_check(span: Mapping) -> verify.Verdict:
            return verify.performer_words(performer, span['text'], self._team_for(performer, span))

        record = {
            'id': eid,
            'family': lexicon.family_of(procedure),
            'procedure': bind('procedure', procedure, absent=procedure == 'unknown',
                              default=_Default(settled, ('single_family',), () if settled else ('procedure_unsettled',)),
                              check=lambda text: verify.procedure_words(procedure, text, len(families) >= 2)),
            'kind': bind('kind', kind),
            'technique': bind('technique', technique, absent=technique == 'not_stated',
                              check=lambda text: verify.device_words(technique, text),
                              place_free='technique' in PLACE_FREE),
            'target': self._target(where, raw['target'], opened('target')),
            'time': bind('time', time, absent=time == 'unknown',
                         default=_Default(True, deny=time_check) if time == 'current_encounter' else None,
                         check=time_check),
            'performer': bind('performer', performer, absent=performer == 'unknown',
                              default=_Default(True, deny=performer_check) if performer == 'documenting_team' else None,
                              check=performer_check, span_check=performer_span_check),
            'status': bind('status', status, check=lambda text: verify.status_words(status, text)),
            'scope': bind('scope', scope, absent=scope in ('not_applicable', 'unknown'),
                          check=lambda text: verify.scope_words(scope, text)),
            'purpose': bind('purpose', purpose, absent=purpose == 'not_stated'),
            'part_of': None,
            'sequence': raw['sequence'],
            'extent': None, 'completion': None, 'visit': None,
            'catalogue_kind': '', 'code_technique': '', 'positive': False, 'current': 'unresolved', 'key': {},
        }
        defined = {item['id'] for item in self.answer['lesions']}
        listed = list(dict.fromkeys(lid for lid in raw['scope']['targets'] if lid in defined))  # each lesion once
        if any(lid not in defined for lid in raw['scope']['targets']):
            self.problems.append(f'{where}.scope names a lesion the answer does not define.')
        record['scope']['targets'] = listed
        self._structure(where, record, raw)
        return record

    def _target(self, where: str, raw: Mapping, opened: bool) -> dict:
        """The target (contract 5.3-5.4): its landmark bound to its words, the lesion kept only when the answer defines
        it (identity 'unresolved' until identity.link decides; 'none' with lesion_unknown for an undefined id)."""
        lesion, landmark = raw['lesion'], raw['landmark']
        defined = lesion in {item['id'] for item in self.answer['lesions']}
        absent = landmark == 'not_stated' and (not lesion or not has_words(raw['words']))
        record = self._bind(f'{where}.target', raw, landmark, absent=absent, opened=opened,
                            check=None if landmark == 'not_stated' else (
                                lambda text: verify.landmark_words(landmark, text)))
        if record['words']:
            record['literals'].update(verify.identity_literals(record['words']['text']))
        record['lesion'] = lesion if defined else ''
        record['identity'] = 'unresolved' if defined else 'none'
        record['identity_by'] = None
        if lesion:
            record['checks'].append('lesion_reference')
        if lesion and not defined:
            record['identity_by'] = {'reasons': ['lesion_unknown']}
            self.problems.append(f'{where}.target names a lesion the answer does not define.')
        return record

    def _structure(self, where: str, record: dict, raw: Mapping) -> None:
        """The structural rules on one event (contract 5.4)."""
        status, time, kind = record['status'], record['time'], record['kind']
        scope = record['scope']
        scope['checks'].append('scope_permitted')
        if not verify.scope_permitted(status['value']):
            if scope['value'] != 'not_applicable':
                scope.update(state='discarded', reasons=verify.ordered(scope['reasons'] + ['scope_not_permitted']))
                self.discarded.append({'where': f'{where}.scope', 'reason': 'scope_not_permitted'})
        elif scope['value'] == 'not_applicable':
            scope.update(value='unknown', basis='absent', state='absent', words=None, literals={}, reasons=[])
            self.problems.append(f'{where}: a statement that an act was not done or is in doubt gave no scope, so its '
                                 'scope is unknown.')
        elif scope['state'] != 'absent' and scope['value'] in ('single_target', 'listed_targets', 'all_of_kind'):
            scope['checks'].append('scope_target')
            if not verify.scope_fits(scope['value'], raw['target']['lesion'], bool(record['target']['lesion']),
                                     raw['target']['landmark'], len(scope['targets'])):
                _fail(scope, 'scope_target_mismatch')
        if kind['value'] == 'intervention':
            kind['checks'].append('umbrella')
            if not verify.umbrella_fits(kind['value'], status['value']):
                _fail(kind, 'umbrella_on_positive')
        if time['value'] != 'unknown':
            status['checks'].append('status_time')
            time['checks'].append('status_time')
            if not verify.status_time_consistent(status['value'], time['value']):
                _fail(status, 'inconsistent_status_time')
                _fail(time, 'inconsistent_status_time')

    def _part_of(self, raws: Sequence) -> None:
        """part_of names another existing event, never itself, with no cycle (5.4); otherwise part_of_invalid. An id the
        answer does not define is never stored."""
        edges = {raw['id']: raw['part_of'] for raw in raws if raw['part_of'] in self.events and raw['part_of'] != raw['id']}
        in_cycle = set()
        for start in edges:
            seen, node = [], start
            while node in edges and node not in seen:
                seen.append(node)
                node = edges[node]
            if node in seen:
                in_cycle.update(seen[seen.index(node):])
        for index, raw in enumerate(raws):
            target = raw['part_of']
            record = {'value': '', 'basis': 'absent', 'state': 'absent', 'open': False, 'words': None, 'passages': [],
                      'checks': [], 'literals': {}, 'reasons': []}
            if target:
                record.update(basis='stated', checks=['part_of_reference'])
                if target in self.events:
                    record['value'] = target
                if target not in self.events or target == raw['id'] or raw['id'] in in_cycle:
                    record.update(state='unverified', reasons=['part_of_invalid'])
                    if target not in self.events:
                        self.problems.append(f'events[{index}].part_of names an event the answer does not define.')
                else:
                    record['state'] = 'verified'
            self.events[raw['id']]['part_of'] = record

    def _claims(self, index: int, raw: Mapping) -> None:
        """The model's contradicts[] (5.4): a claim naming no other existing event is a dismissed claim
        (claim_unknown_event); every other claim goes to the relations step."""
        for claim in raw['contradicts']:
            passages = [pid for pid in claim['passages'] if pid in self.passages]
            if claim['event'] in self.events and claim['event'] != raw['id']:
                self.claims.append({'statement': raw['id'], 'event': claim['event'], 'passages': passages})
            else:
                self.relation('dismissed_claim', statement=raw['id'], event='', reason='claim_unknown_event',
                              claimed_by_model=True, passages=passages)

    # --- 7. reach, visit facts, anatomy (contract 5.3-5.4, 8.3) --------------------------------------------------------

    def _attach_reach(self) -> None:
        self.encounter['reach'] = []
        for index, raw in enumerate(self.answer['encounter']['reach']):
            where = f'encounter.reach[{index}]'
            event = self.events.get(raw['event'])
            eid = raw['event'] if event is not None else ''
            landmark, completion_value = raw['landmark'], raw['completion']['value']
            extent = self._bind(where, raw, landmark, absent=landmark == 'not_stated', opened=(eid, 'extent') in
                                self._opened, check=lambda text: verify.reach_words(landmark, text))
            if event is not None and extent['words'] is not None:
                self._reach_source(extent, raw['words'], event)
            completion = self._bind(f'{where}.completion', raw['completion'], completion_value,
                                    absent=completion_value == 'not_stated', opened=(eid, 'completion') in self._opened)
            reach_text = extent['words']['text'] if extent['words'] else ''
            entry = {'event': eid, 'family': event['family'] if event is not None else '', 'landmark': landmark,
                     'state': extent['state'], 'reasons': extent['reasons'], 'attached': False}
            if event is None:
                self.problems.append(f'{where} names an event the answer does not define.')
            if extent['state'] != 'absent':
                extent['checks'].append('reach_permitted')
                if event is None or not verify.reach_permitted(event, reach_text):
                    for record in (extent, completion):
                        if record['state'] != 'absent':
                            record.update(state='discarded',
                                          reasons=verify.ordered(record['reasons'] + ['reach_not_permitted']))
                    entry.update(state='discarded', reasons=extent['reasons'])
                    self.discarded.append({'where': where, 'reason': 'reach_not_permitted'})
                elif event['extent'] is None:
                    event['extent'], event['completion'] = extent, completion
                    entry['attached'] = True
                else:
                    self.problems.append(f'{where} gives a second reach for one examination; the first is kept.')
            self.encounter['reach'].append(entry)
            self._tally('reach', extent)
            self._tally('completion', completion)

    def _reach_source(self, extent: dict, words: str, examination: Mapping) -> None:
        """DECISIONS D36 (verify.reach_stated): a reach whose words stand only in passages of the session's other events -
        its cited passages that hold the words, each cited by another event of the examination's family and not by the
        examination - is inferred from where those acts were done: unverified (reach_inferred), so R6 asks the extent.
        A cited passage that does not hold the words is not where the reach was read, and counts for nothing."""
        extent['checks'].append('reach_source')
        holding = [pid for pid in extent['passages'] if self.passages[pid]['state'] != UNLOCATED
                   and self._locate_words(words, [self.passages[pid]]) is not None]
        session = [event for event in self.events.values()
                   if event['id'] != examination['id'] and event['family'] == examination['family']]
        if not verify.reach_stated(holding, examination, session):
            _fail(extent, 'reach_inferred')

    def _attach_visits(self) -> None:
        self.encounter['visits'] = []
        for index, raw in enumerate(self.answer['encounter']['visit_facts']):
            where = f'encounter.visit_facts[{index}]'
            event = self.events.get(raw['event'])
            eid = raw['event'] if event is not None else ''
            basis_value = raw['basis']['value']
            separate_value = raw['separately_identifiable']['value']
            basis = self._bind(f'{where}.basis', raw['basis'], basis_value, absent=basis_value == 'not_stated',
                               opened=(eid, 'visit_basis') in self._opened,
                               check=lambda text: verify.basis_words(basis_value, text))
            separate = self._bind(f'{where}.separately_identifiable', raw['separately_identifiable'], separate_value,
                                  absent=separate_value == 'not_stated',
                                  check=lambda text: verify.separate_words(separate_value, text))
            attached = False
            if event is None:
                self.problems.append(f'{where} names an event the answer does not define.')
            for record in (basis, separate):
                record['checks'].append('visit_permitted')
            if event is None or event['kind']['value'] != 'em_visit':
                for record in (basis, separate):
                    if record['state'] != 'absent':
                        record.update(state='discarded',
                                      reasons=verify.ordered(record['reasons'] + ['visit_not_permitted']))
                self.discarded.append({'where': where, 'reason': 'visit_not_permitted'})
            elif event['visit'] is None:
                event['visit'] = {'basis': basis, 'separately_identifiable': separate}
                attached = True
            else:
                self.problems.append(f'{where} gives a second set of visit facts for one visit; the first is kept.')
            self.encounter['visits'].append({'event': eid, 'basis': basis_value, 'basis_state': basis['state'],
                                             'separately_identifiable': separate_value,
                                             'separately_identifiable_state': separate['state'],
                                             'attached': attached})
            self._tally('visit_basis', basis)
            self._tally('separately_identifiable', separate)

    def _bind_anatomy(self) -> None:
        self.encounter['anatomy'] = []
        for index, raw in enumerate(self.answer['encounter']['anatomy']):
            landmark = raw['landmark']
            record = self._bind(f'encounter.anatomy[{index}]', raw, landmark, absent=landmark == 'not_stated',
                                check=lambda text, value=landmark: verify.landmark_words(value, text))
            record['anatomy'] = raw['state']
            self.encounter['anatomy'].append(record)
            self._tally('anatomy', record)

    # --- 9. derived encounter facts (contract 8.3; D21) ----------------------------------------------------------------

    def _derive(self) -> None:
        current, performed, possible = set(), set(), set()
        for record in self.events.values():
            family = record['family']
            if record['kind']['value'] == 'examination' and record['positive'] and record['current'] == 'yes' and family:
                current.add(family)
            if (family in lexicon.PROCEDURAL_FAMILIES and record['time']['value'] == 'current_encounter'
                    and record['status']['value'] in verify.POSITIVE + ('uncertain',)):
                if record['status']['value'] in verify.POSITIVE and all(
                        verify.usable(record[name]) for name in ('status', 'time', 'performer', 'procedure')):
                    performed.add(family)
                else:
                    possible.add(family)
        absent = [record['value'] for record in self.encounter['anatomy']
                  if record['anatomy'] == 'absent' and verify.usable(record)]
        self.encounter['derived'] = {
            'current_families': _in_order(current),
            'procedure_day': {'performed': _in_order(performed), 'possible': _in_order(possible - performed)},
            'absent': sorted(set(absent), key=_landmark_order),
        }

    # --- open questions (contract 4.1 step 7) ----------------------------------------------------------------------------

    def _finish_questions(self) -> None:
        for index, raw in enumerate(self.answer['open_questions']):
            events = [eid for eid in raw['events'] if eid in self.events]
            lesions = [lid for lid in raw['lesions'] if lid in self.lesions]
            passages = [pid for pid in raw['passages'] if pid in self.passages]
            unknown = (len(raw['events']) - len(events)) + (len(raw['lesions']) - len(lesions)) + (
                len(raw['passages']) - len(passages))
            if unknown:
                self.problems.append(f'open_questions[{index}] names {unknown} id{"s" if unknown != 1 else ""} the '
                                     'answer does not define.')
            about, attached = raw['about'], []
            for eid in events:
                record = self.events[eid]
                if about in ('extent', 'completion'):
                    if record[about] is not None:
                        attached.append({'event': eid, 'attribute': about})
                elif about == 'visit_basis':
                    if record['visit'] is not None:
                        attached.append({'event': eid, 'attribute': 'visit_basis'})
                elif about in EVENT_ABOUT:
                    attached.append({'event': eid, 'attribute': about})
                elif about == 'contradiction':
                    attached.append({'event': eid, 'attribute': 'status'})
                elif about == 'identity':
                    attached.append({'event': eid, 'attribute': 'identity'})
            if about == 'date_of_service':
                attached.append({'encounter': 'date_of_service'})
            self.open_questions.append({'about': about, 'events': events, 'lesions': lesions, 'passages': passages,
                                        'attached_to': attached})

    # --- 10. the verification report (contract 4.3) --------------------------------------------------------------------

    def _tally(self, name: str, record: Mapping, reasons: bool = True) -> None:
        self._tallied.append((name, record, reasons))

    def _report(self) -> dict:
        counts = {name: dict.fromkeys(('claimed', 'verified', 'unverified', 'absent', 'discarded', 'open'), 0)
                  for name in COUNTED}
        reasons = Counter()
        for name, record, with_reasons in self._tallied:
            state = record['state']
            row = counts[name]
            row[state] += 1
            row['claimed'] += state != 'absent'
            row['open'] += bool(record.get('open'))
            if with_reasons:
                reasons.update(record.get('reasons', ()))
        for record in self.events.values():
            identity_by = record['target'].get('identity_by')
            if isinstance(identity_by, Mapping):
                reasons.update(identity_by.get('reasons', ()))
        reasons.update(relation['reason'] for relation in self.relations if relation['reason'] in verify.REASONS)
        relations = Counter(relation['type'] for relation in self.relations)
        return {'label': LABEL, 'counts': {name: row for name, row in counts.items() if row['claimed'] or row['absent']},
                'reasons': {reason: reasons[reason] for reason in verify.ordered(reasons)},
                'relations': dict(sorted(relations.items())), 'discarded': list(self.discarded),
                'problems': list(self.problems), 'refused': False}


# --- helpers -----------------------------------------------------------------------------------------------------------

def closing_bracket_end(text: str, start: int, end: int) -> int:
    """The end of the span [start, end) of ``text`` after the closing-bracket rule (contract 5.1): when the span opens
    more brackets of one kind than it closes, and the text's next characters - after at most one run of spaces - are
    exactly the missing closers (innermost first), the span ends after them; otherwise ``end``."""
    segment = text[start:end]
    deficit = {opener: segment.count(opener) - segment.count(closer) for opener, closer in OPENERS.items()}
    if not any(value > 0 for value in deficit.values()):
        return end
    stack = []
    for char in segment:
        if char in OPENERS:
            stack.append(char)
        elif char in _CLOSERS and stack and OPENERS[stack[-1]] == char:
            stack.pop()
    expected = ''.join(OPENERS[opener] for opener in reversed(stack))
    if Counter(expected) != Counter({OPENERS[opener]: value for opener, value in deficit.items() if value > 0}):
        return end
    after = end
    while after < len(text) and text[after] in ' \t':
        after += 1
    return after + len(expected) if text.startswith(expected, after) else end


def _mapped(text: str, fold: Optional[Callable[[str], str]]) -> tuple:
    """``text`` with whitespace runs collapsed to one space (and each character folded, when ``fold`` is given), with
    the start and end offset in ``text`` of each character kept."""
    chars, starts, ends = [], [], []
    for index, char in enumerate(text):
        for piece in (fold(char) if fold else char):
            if piece.isspace():
                if chars and chars[-1] == ' ':
                    ends[-1] = index + 1
                    continue
                piece = ' '
            chars.append(piece)
            starts.append(index)
            ends.append(index + 1)
    return ''.join(chars), starts, ends


def has_words(words: str) -> bool:
    """Whether ``words`` hold a letter or a digit: words of punctuation alone state nothing, and are read as no words
    (a refinement of contract 5.2 recorded by slice S02: "." would otherwise bind any value its passage holds)."""
    return any(char.isalnum() for char in words)


def _word_char(char: str) -> bool:
    return char.isalnum() or char == '_'


def _bounded_positions(hay: str, needle: str) -> list:
    """Every place ``needle`` occurs in ``hay`` without splitting a word at either end."""
    found, at = [], hay.find(needle)
    while at != -1:
        end = at + len(needle)
        before = at == 0 or not (_word_char(needle[0]) and _word_char(hay[at - 1]))
        after = end == len(hay) or not (_word_char(needle[-1]) and _word_char(hay[end]))
        if before and after:
            found.append(at)
        at = hay.find(needle, at + 1)
    return found


def _fail(record: dict, reason: str) -> None:
    """A structural rule's failure: the attribute is unverified with the reason (a discarded one stays discarded)."""
    record['reasons'] = verify.ordered(record['reasons'] + [reason])
    if record['state'] != 'discarded':
        record['state'] = 'unverified'


def _current(time: Mapping) -> str:
    """Whether an event is of this encounter: 'yes' for a usable current_encounter time, 'no' for a usable earlier or
    future one, 'unresolved' otherwise."""
    if not verify.usable(time):
        return 'unresolved'
    return 'yes' if time['value'] == 'current_encounter' else 'no'


def _in_order(families) -> list:
    return [family for family in lexicon.FAMILY_ORDER if family in families]


def _landmark_order(landmark: str) -> int:
    return schema.LANDMARKS.index(landmark)
