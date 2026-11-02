"""Candidate answers to an open question, from the participants' located passages (HARNESS.md 11.3, 12.5).

Pure: no Django, no I/O. The encounter view lists these for each OPEN clarification of the final assessment, and the
confirmation endpoint recomputes them server-side before it accepts one. A candidate never answers anything by itself: a
reviewer confirms it, with an attestation, and agreement between participants never verifies one.

Sources, from the frozen phase-1 readings and the phase-2 answers of the runs the final assessment read:

    | clarification fact             | phase-1 source                                          | phase-2 source        |
    |--------------------------------|---------------------------------------------------------|-----------------------|
    | service_date (encounter scope) | date_of_service and its date evidence                   | the answer to its id  |
    | extent                         | each service of the family: extent and its evidence     | the same              |
    | target                         | each service of the family: anatomy and its evidence    | the same              |
    | cannulation                    | none                                                    | the same              |
    | performed_status (proposal)    | each service of the family: status and its evidence     | the same              |
    | em_basis                       | office_em services: each quote stating time or a level  | the same              |
    | any other fact                 | none: never a candidate                                 | none                  |

A service is "of the family" when engine.PARTICIPANT_FAMILY_MAP maps its family to the question's. A reading that was
refused, and an answer that says the document does not settle its question, are no source.

One candidate is one value with the passage one quote was located at (every occurrence of it, at most 8). Identical
(value, spans) from several participants or phases merge into one candidate naming all of them: ``located_by`` and
``runs`` list each, ``phases`` says in which phase each located it, and ``phase`` is 'independent' when any of them did
so in its frozen first reading ('peer_review' only when every one did so after peer review). ``id`` is 16 hex of the
sha256 of (clarification id, fact, value, sorted spans, sorted located_by).

Values are CPT Studio's own words, never the participant's: a date in YYYY-MM-DD form; a status (performed, not
performed, cancelled, planned, historical); the one landmark (routing's labels, by the family's tract) or the one EUS
structure (routing's own reading) the value names; a cannulation outcome (successful, failed); an E/M basis as routing
states one (time, mdm, time+mdm). A value CPT Studio cannot state so - it names two landmarks, it qualifies itself
with a negation, an attempt, a doubt or an alternative, or it is no date or status - is '' and its candidate is
unverified, with why. (So a value never inverts in the restating: "cecum not reached" is never offered as "cecum".)

A candidate is verified only when every one of these holds, checked in this order; ``why`` names the first that fails:
- its value is stated in CPT Studio's words (above);
- it cites a passage whose quote was located verbatim in the revision text (I7), at most 8 spans;
- each span is an exact slice of the revision text that does not run across a page break (a [Page N] line);
- the deterministic consistency check for its fact passes on each span:
  - date: the span states that calendar date, as gi.context.find_dates reads one, at day precision;
  - extent: the span names the landmark the value names (its routing pattern);
  - target: the span names the structure the value names (a design choice of HARNESS.md 12.5);
  - cannulation: the span states that cannulation outcome, by routing's cannulation cues, and not the other (12.5 asks
    for an outcome; the outcome stated must be the value's);
  - status: the span lies in no history, plan or indication section (gi.sections);
  - E/M basis: the span states a total time in minutes (routing's E/M time cues, never a procedure time) for 'time', an
    MDM level for 'mdm'.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Optional, Sequence

from studio.gi import cues, sections
from studio.gi.context import find_dates
from studio.gi.profiles import PROFILES
from studio.participants import PARTICIPANTS
from studio.types import LocatedQuote, ParticipantReading, QuestionAnswer, canonical_json
from studio.validation import engine

DATE_FACT = 'service_date'
STATUS_FACT = engine.STATUS_FACT
# The facts a candidate answers: the service date (through the context), a proposal's status and the required facts the
# readers take from the document (engine.CONFIRMABLE_FACTS: cannulation, em_basis, extent, target).
FACTS = (DATE_FACT, STATUS_FACT) + tuple(engine.CONFIRMABLE_FACTS)
INDEPENDENT, PEER_REVIEW = engine.INDEPENDENT, engine.PEER_REVIEW
MAX_SPANS = 8
MAX_VALUE_CHARS = 200  # models.FindingConfirmation.value
# The attestation a confirmation records, with the candidate's value (HARNESS.md 11.3, 12.5).
ATTESTATION = 'I read this passage in the source document; it documents {value} for this encounter.'
HELD_SECTIONS = ('history', 'plan', 'indication')  # never documents a service at this encounter (11.3)

# A confirmed status as CPT Studio words it, from what a peer answer states (engine._status_value's normal form) and
# from a reading's status; every one is a value engine._Confirmations reads ('performed', engine.NOT_PERFORMED_VALUES).
STATUS_WORDS = {'performed': 'performed', 'not_performed': 'not performed', 'negated': 'not performed',
                'cancelled': 'cancelled', 'canceled': 'cancelled', 'planned': 'planned', 'historical': 'historical'}
READING_STATUSES = {'performed': 'performed', 'not_performed': 'not performed', 'planned': 'planned',
                    'historical': 'historical'}
ATTEMPTED = ('the value is an attempted, incomplete service, which is neither performed nor not performed at this '
             'encounter, so a confirmation cannot carry it')
# The landmarks of an extent, by the family's tract (routing's own tables and labels).
TRACTS = {'gi.egd': cues.UPPER_LANDMARKS, 'gi.enteroscopy': cues.UPPER_LANDMARKS,
          'gi.colonoscopy': cues.LOWER_LANDMARKS, 'gi.flex_sig': cues.LOWER_LANDMARKS}

_ISO_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
# Words with which a value says more than the fact it states: a negation, an attempt or an incomplete examination, a
# doubt or an alternative. Such a value is never restated in CPT Studio's words.
_QUALIFIED = re.compile(r"\b(?:no|not|never|none|nor|without|unable|cannot|failed|failure|unsuccessful|incomplete|"
                        r"aborted|abandoned|attempt|attempts|attempted|partial|partially|short|unclear|uncertain|"
                        r"unknown|possible|possibly|probable|probably|likely|presumed|suspected|approximately|about|"
                        r"around|or)\b|n't\b|\?", re.A | re.I)
_UNCERTAIN = re.compile(r'\b(?:unclear|uncertain|unknown|possible|possibly|probable|probably|likely|presumed|suspected|'
                        r'or)\b|\?', re.A | re.I)
_TERSE_OUTCOMES = {'successful': 'successful', 'success': 'successful', 'succeeded': 'successful',
                   'achieved': 'successful', 'cannulated': 'successful', 'failed': 'failed', 'failure': 'failed',
                   'unsuccessful': 'failed', 'not achieved': 'failed', 'not cannulated': 'failed'}
_TIME_WORDS = re.compile(r'\b(?:time|minutes?|mins?)\b', re.A | re.I)
_MDM_WORDS = re.compile(r'\b(?:mdm|decision[- ]making|complexity|straightforward|low|moderate|high)\b', re.A | re.I)
_NO_PASSAGE = 'No passage is cited for this value.'
_UNLOCATED = {'too short': 'Its quote is too short to be located (fewer than 8 characters), so it is never evidence.',
              'not found': 'Its quote was not found verbatim in the document text, and a quote that is not found is '
                           'never evidence.'}


@dataclass(frozen=True)
class Question:
    """An open clarification, as the candidates read it: its id, scope, fact, family and (proposal scope) the key of its
    proposal."""
    id: str
    scope: str  # encounter | service | proposal
    fact: str
    family: str = ''
    proposal_key: str = ''


@dataclass(frozen=True)
class FrozenReading:
    """A model participant's frozen phase-1 reading that the final assessment read, with its run's id."""
    name: str  # astra | fable
    run: str
    reading: ParticipantReading


@dataclass(frozen=True)
class PeerAnswer:
    """A model participant's phase-2 answer to this question, with its peer-review run's id."""
    name: str
    run: str
    answer: QuestionAnswer


@dataclass(frozen=True)
class _Source:
    name: str
    run: str
    phase: str
    value: str
    problem: str  # why the value cannot be stated in CPT Studio's words ('' when it can)
    quote: Optional[LocatedQuote]  # None: no passage cited


def attestation(value: str) -> str:
    """The exact attestation a confirmation of ``value`` records."""
    return ATTESTATION.format(value=value)


def askable(question: Question) -> bool:
    """Whether a candidate can answer ``question``: one of FACTS, in the scope a confirmation answers it in (the service
    date at the encounter, a status at a proposal, a required fact at a service or a proposal of a family that requires
    it)."""
    if not isinstance(question, Question) or question.fact not in FACTS:
        return False
    if question.fact == DATE_FACT:
        return question.scope == 'encounter'
    if question.family not in PROFILES:
        return False
    if question.fact == STATUS_FACT:
        return question.scope == 'proposal' and bool(question.proposal_key)
    return question.scope in ('service', 'proposal') and question.fact in PROFILES[question.family].required_facts


def candidates(question: Question, text: str, pages: Sequence = (), readings: Sequence[FrozenReading] = (),
               answers: Sequence[PeerAnswer] = ()) -> list[dict]:
    """The candidates of ``question`` (see the module docstring), verified against ``text`` (the revision text) and its
    ``pages`` (PageSpan or {page, start, end}); [] for a question no candidate answers or with no source - a Corti-only
    encounter has neither. Deterministic: the same inputs, in any order, give the same list."""
    if not askable(question) or not isinstance(text, str):
        return []
    index = _page_index(pages)
    sources: list[_Source] = []
    for item in sorted(readings, key=_order):
        sources += _reading_sources(question, item)
    for item in sorted(answers, key=_order):
        sources += _answer_sources(question, item)
    merged: dict[tuple, dict] = {}
    for source in sources:
        spans = tuple(sorted(source.quote.spans, key=lambda s: (s.start, s.end))) if source.quote is not None else ()
        key = (source.value, tuple((span.start, span.end) for span in spans))
        entry = merged.get(key)
        if entry is None:
            entry = merged[key] = {'value': source.value, 'spans': spans, 'by': {}, 'runs': [],
                                   'why': _why(question, source, spans, text, index)}
        entry['by'].setdefault(source.name, set()).add(source.phase)
        if source.run not in entry['runs']:
            entry['runs'].append(source.run)
    out = [_candidate(question, entry, index) for entry in merged.values()]
    out.sort(key=lambda c: (not c['verified'], c['spans'][0]['start'] if c['spans'] else len(text) + 1, c['value'],
                            c['id']))
    return out


def canonical_value(fact: str, family: str, raw) -> tuple[str, str]:
    """(the value of ``fact`` in CPT Studio's own words, '') for a participant's ``raw`` value, or ('', why there is
    none: a clause beginning "the value")."""
    if not isinstance(raw, str) or not raw.strip():
        return '', 'the value is empty'
    text = ' '.join(raw.split())
    if fact == DATE_FACT:
        value, problem = _date_value(text)
    elif fact == STATUS_FACT:
        value, problem = _status_value(text)
    elif fact == 'extent':
        value, problem = _landmark_value(text, family)
    elif fact == 'target':
        value, problem = _target_value(text)
    elif fact == 'cannulation':
        value, problem = _cannulation_value(text)
    elif fact == 'em_basis':
        value, problem = _basis_value(text)
    else:
        return '', 'the value answers a question no candidate answers'
    if value and len(value) > MAX_VALUE_CHARS:
        return '', f'the value is longer than the {MAX_VALUE_CHARS} characters a confirmation records'
    return value, problem


# --- the sources ------------------------------------------------------------------------------------------------------

def _order(item) -> tuple:
    name = getattr(item, 'name', '')
    return (PARTICIPANTS.index(name) if name in PARTICIPANTS else len(PARTICIPANTS), str(name),
            str(getattr(item, 'run', '')))


def _quoted(item, phase: str, value: str, problem: str, quotes) -> list[_Source]:
    """One source per quote, or one with no passage when the value cites none."""
    located = [quote for quote in quotes if isinstance(quote, LocatedQuote)]
    if not located:
        return [_Source(item.name, str(item.run), phase, value, problem, None)]
    return [_Source(item.name, str(item.run), phase, value, problem, quote) for quote in located]


def _family_of(question: Question, service) -> bool:
    return question.family in engine.PARTICIPANT_FAMILY_MAP.get(getattr(service, 'family', ''), ())


def _reading_sources(question: Question, item: FrozenReading) -> list[_Source]:
    reading = item.reading
    if not isinstance(reading, ParticipantReading) or reading.refused or reading.provider != item.name:
        return []
    fact = question.fact
    if fact == DATE_FACT:
        if not reading.date_of_service:
            return []
        value, problem = canonical_value(fact, question.family, reading.date_of_service)
        return _quoted(item, INDEPENDENT, value, problem, reading.date_evidence)
    if fact == 'cannulation':
        return []  # 12.5: a reading states no cannulation outcome of its own
    out = []
    for service in reading.services:
        if not _family_of(question, service):
            continue
        if fact == 'em_basis':  # each quote that states a total time or a level is a candidate of its own
            for quote in service.evidence:
                passage = quote.spans[0].text if quote.spans else quote.quote
                basis = _basis_stated(passage)
                if basis:
                    out += _quoted(item, INDEPENDENT, basis, '', (quote,))
            continue
        if fact == STATUS_FACT:
            if service.status == 'unclear':
                continue  # the participant does not settle it
            value = READING_STATUSES.get(service.status, '')
            problem = ATTEMPTED if service.status == 'attempted_incomplete' else (
                '' if value else 'the value is not a status a confirmation carries')
        else:
            raw = service.extent if fact == 'extent' else service.anatomy
            if not raw.strip():
                continue
            value, problem = canonical_value(fact, question.family, raw)
        out += _quoted(item, INDEPENDENT, value, problem, service.evidence)
    return out


def _answer_sources(question: Question, item: PeerAnswer) -> list[_Source]:
    answer = item.answer
    if not isinstance(answer, QuestionAnswer) or not answer.settled:
        return []
    value, problem = canonical_value(question.fact, question.family, answer.value)
    return _quoted(item, PEER_REVIEW, value, problem, answer.evidence)


# --- values in CPT Studio's words -------------------------------------------------------------------------------------

def _date_value(text: str) -> tuple[str, str]:
    if _QUALIFIED.search(text):
        return '', 'the value qualifies its date (a negation, a doubt or an alternative)'
    if _ISO_DATE.fullmatch(text):
        try:
            return date.fromisoformat(text).isoformat(), ''
        except ValueError:
            return '', 'the value is no calendar date'
    days = {mention.value for mention in find_dates(text) if mention.precision == 'day'}
    if len(days) == 1:
        return days.pop().isoformat(), ''
    return '', 'the value names no single calendar date'


def _status_value(text: str) -> tuple[str, str]:
    word = STATUS_WORDS.get(re.sub(r'[\s-]+', '_', text.strip().rstrip('.!').strip().lower()))
    if word:
        return word, ''
    return '', ('the value is neither performed nor a status of a service not performed at this encounter (not '
                'performed, cancelled, planned, historical)')


def landmarks_named(text: str, table) -> list[str]:
    """The landmark labels ``text`` names, in text order, the most specific where one match holds another ("second part
    of the duodenum" names that landmark, never also the duodenum)."""
    found = [(m.start(), m.end(), label) for label, _, pattern in table for m in pattern.finditer(text)]
    kept = [hit for hit in found
            if not any(o[0] <= hit[0] and hit[1] <= o[1] and o[1] - o[0] > hit[1] - hit[0] for o in found)]
    return list(dict.fromkeys(label for _, _, label in sorted(kept)))


def _landmark_value(text: str, family: str) -> tuple[str, str]:
    table = TRACTS.get(family)
    if table is None:
        return '', 'the value is an extent of a service whose landmarks CPT Studio does not read'
    if _QUALIFIED.search(text):
        return '', 'the value says more than a landmark reached (a negation, an attempt, a doubt or an alternative)'
    named = landmarks_named(text, table)
    if not named:
        return '', 'the value names no landmark CPT Studio reads'
    if len(named) > 1:
        return '', f'the value names more than one landmark ({", ".join(named)})'
    return named[0], ''


def _target_label(template: str, match) -> str:
    return ' '.join(template.format(*[group.lower() for group in match.groups() if group]).split())


def targets_named(text: str) -> list[str]:
    """The EUS structures ``text`` names as routing reads them: the first template that matches each place."""
    found = []
    for template, pattern in cues.EUS_TARGETS:
        for m in pattern.finditer(text):
            if not any(start < m.end() and m.start() < end for start, end, _ in found):
                found.append((m.start(), m.end(), _target_label(template, m)))
    return list(dict.fromkeys(label for _, _, label in sorted(found)))


def _targets_stated(text: str) -> set[str]:
    """Every EUS structure any of routing's templates reads in ``text``."""
    return {_target_label(template, m) for template, pattern in cues.EUS_TARGETS for m in pattern.finditer(text)}


def _target_value(text: str) -> tuple[str, str]:
    if _QUALIFIED.search(text):
        return '', 'the value says more than the structure examined (a negation, a doubt or an alternative)'
    named = targets_named(text)
    if not named:
        return '', 'the value names no structure CPT Studio reads'
    if len(named) > 1:
        return '', f'the value names more than one structure ({", ".join(named)})'
    return named[0], ''


def _cannulation_value(text: str) -> tuple[str, str]:
    terse = _TERSE_OUTCOMES.get(text.rstrip('.!').strip().lower())
    if terse:
        return terse, ''
    if _UNCERTAIN.search(text):
        return '', 'the value doubts its cannulation outcome or offers an alternative'
    failed, succeeded = cues.CANNULATION_FAILED.search(text), cues.CANNULATION_SUCCESS.search(text)
    if bool(failed) != bool(succeeded):
        return ('failed' if failed else 'successful'), ''
    return '', 'the value names no single cannulation outcome'


def _basis_value(text: str) -> tuple[str, str]:
    if _QUALIFIED.search(text):
        return '', 'the value qualifies its basis (a negation, a doubt or an alternative)'
    value = '+'.join(name for name, words in (('time', _TIME_WORDS), ('mdm', _MDM_WORDS)) if words.search(text))
    return (value, '') if value else ('', 'the value names neither total time nor medical decision making')


def _basis_stated(text: str) -> str:
    """'time', 'mdm' or 'time+mdm': what ``text`` states by routing's E/M cues (a total time in minutes that is no
    procedure time; an MDM level); '' for neither."""
    time = (any(not cues.NOT_EM_TIME.search(m.group(0)) for m in cues.EM_TIME.finditer(text))
            or bool(cues.EM_TIME_LINE.match(text)))
    level = bool(cues.MDM_LEVEL.search(text))
    return '+'.join(name for name, stated in (('time', time), ('mdm', level)) if stated)


# --- verification -----------------------------------------------------------------------------------------------------

def _sentence(clause: str) -> str:
    return clause[:1].upper() + clause[1:] + ('' if clause.endswith('.') else '.')


def _why(question: Question, source: _Source, spans: tuple, text: str, index) -> str:
    """'' for a verified candidate; otherwise the first check that fails, in CPT Studio's words."""
    if source.problem or not source.value:
        return _sentence(source.problem or 'the value cannot be stated in CPT Studio\'s words')
    if source.quote is None:
        return _NO_PASSAGE
    if not spans:
        return _UNLOCATED.get(source.quote.reason, _UNLOCATED['not found'])
    if len(spans) > MAX_SPANS:
        return f'It cites more than {MAX_SPANS} passages.'
    for span in spans:
        if not _exact(text, span):
            return 'A passage is not an exact slice of the document text.'
        if _crosses(index, span):
            return 'A passage runs across a page break (a [Page N] line).'
    for span in spans:
        failed = _inconsistent(question, source.value, text, span)
        if failed:
            return _sentence(failed)
    return ''


def _inconsistent(question: Question, value: str, text: str, span) -> str:
    """Why ``span`` does not pass the consistency check for ``question``'s fact; '' when it does."""
    passage = text[span.start:span.end]
    fact = question.fact
    if fact == DATE_FACT:
        day = date.fromisoformat(value)
        if any(m.precision == 'day' and m.value == day and span.start <= m.start and m.end <= span.end
               for m in _dates(text)):
            return ''
        return f'the passage does not state {value} as a calendar date'
    if fact == 'extent':
        patterns = [pattern for label, _, pattern in TRACTS.get(question.family, ()) if label == value]
        return '' if any(pattern.search(passage) for pattern in patterns) else f'the passage does not name the {value}'
    if fact == 'target':
        return '' if value in _targets_stated(passage) else f'the passage does not name the {value}'
    if fact == 'cannulation':
        succeeded, failed = cues.CANNULATION_SUCCESS.search(passage), cues.CANNULATION_FAILED.search(passage)
        if not (succeeded or failed):
            return 'the passage states no cannulation outcome'
        if succeeded and failed:
            return 'the passage states both a successful and a failed cannulation'
        stated = 'successful' if succeeded else 'failed'
        return '' if stated == value else f'the passage states a {stated} cannulation, not a {value} one'
    if fact == 'em_basis':
        stated = _basis_stated(passage).split('+')
        if 'time' in value.split('+') and 'time' not in stated:
            return 'the passage states no total time in minutes'
        if 'mdm' in value.split('+') and 'mdm' not in stated:
            return 'the passage states no level of medical decision making'
        return ''
    if fact == STATUS_FACT:
        held = [kind for kind in _section_kinds(text, span) if kind in HELD_SECTIONS]
        return (f'the passage is in a {held[0]} section, which never documents a service at this encounter'
                if held else '')
    return 'the value answers a question no candidate answers'


@lru_cache(maxsize=8)
def _dates(text: str):
    return find_dates(text)


def _section_kinds(text: str, span) -> list[str]:
    lay = sections.layout(text)
    kinds = [section.kind for section in lay.sections if section.start < span.end and span.start < section.end]
    return kinds or [lay.section_at(span.start).kind]


def _exact(text: str, span) -> bool:
    start, end = getattr(span, 'start', None), getattr(span, 'end', None)
    return (type(start) is int and type(end) is int and 0 <= start < end <= len(text)
            and text[start:end] == getattr(span, 'text', None))


def _page_index(pages) -> tuple[tuple[int, int, int], ...]:
    """(start, end, page) of each well-formed page span, by start."""
    out = []
    for page in pages or ():
        if isinstance(page, dict):
            start, end, number = page.get('start'), page.get('end'), page.get('page')
        else:
            start, end, number = getattr(page, 'start', None), getattr(page, 'end', None), getattr(page, 'page', None)
        if type(start) is int and type(end) is int and type(number) is int and 0 <= start <= end:
            out.append((start, end, number))
    return tuple(sorted(out))


def _crosses(index, span) -> bool:
    """Whether a page begins or ends strictly inside ``span``: the passage runs across a [Page N] line."""
    return any(span.start < edge < span.end for start, end, _ in index for edge in (start, end))


def _page_of(index, position: int) -> Optional[int]:
    return next((number for start, end, number in index if start <= position < end), None)


def _candidate(question: Question, entry: dict, index) -> dict:
    by = entry['by']
    located = sorted(by, key=lambda name: (PARTICIPANTS.index(name) if name in PARTICIPANTS else len(PARTICIPANTS),
                                           name))
    phases = {name: INDEPENDENT if INDEPENDENT in by[name] else PEER_REVIEW for name in located}
    spans = entry['spans']
    identity = canonical_json([question.id, question.fact, entry['value'], [[s.start, s.end] for s in spans],
                               sorted(located)])
    return {'id': hashlib.sha256(identity).hexdigest()[:16], 'clarification_id': question.id, 'fact': question.fact,
            'value': entry['value'], 'located_by': located,
            'phase': INDEPENDENT if INDEPENDENT in phases.values() else PEER_REVIEW, 'phases': phases,
            'runs': list(entry['runs']),
            'spans': [{'start': s.start, 'end': s.end, 'text': s.text, 'page': _page_of(index, s.start)}
                      for s in spans],
            'verified': entry['why'] == '', 'why': entry['why']}
