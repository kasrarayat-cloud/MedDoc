"""GI service routing: which services a document describes, their status, and
the family facts that support them. See ARCHITECTURE.md section 5.3.

Status is fail-closed. A mention is "performed" only with positive evidence:
an explicit past-tense performance cue in its clause, or a procedure /
findings / technique section with no contrary cue. Every other reading -
planned, historical, cancelled, negated, incomplete or uncertain - keeps the
service from silently becoming a performed one.

A family is performed when a mention carries explicit evidence, or section
evidence that no cancellation or negation of today's service contradicts (in
an office visit note, section evidence also needs documented extent or
interventions). A performed service whose incompleteness is documented - an
incomplete mention, extent short of the cecum, failed cannulation, "the
procedure was terminated" - is incomplete. Otherwise the family takes the
most informative remaining status. Sentences that refer to a service without
naming it ("the procedure was cancelled") become mentions only when they say
it was not done or not completed, never to make it performed.

Pure functions over the canonical text; results are cached per text.
"""
from __future__ import annotations

import bisect
import functools
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from studio.gi import context as ctx
from studio.gi import cues
from studio.gi.profiles import DETECTED_FAMILIES, FAMILY_ORDER, PROFILES
from studio.gi.sections import Layout, layout
from studio.types import Fact, FamilyFinding, RoutingResult, ServiceMention, Span

ROUTING_VERSION = 'gi-routing@1'
PROCEDURE_FAMILIES = tuple(f for f in DETECTED_FAMILIES if PROFILES[f].procedure)
# Within one mention the strongest reading wins; "performed" never beats a doubt.
STATUS_PRECEDENCE = ('negated', 'historical', 'cancelled', 'incomplete', 'planned', 'uncertain', 'performed')
# Across a family's mentions, after performed and incomplete (ARCHITECTURE 5.3).
AGGREGATE_ORDER = ('cancelled', 'negated', 'historical', 'planned', 'uncertain')
POSITIVE_SECTIONS = ('procedure', 'findings', 'technique')
EM_SECTIONS = ('mdm', 'time')
DATE_REACH = 40  # a date speaks for a mention only within this many characters
CLAUSE_REACH = 300  # cues further than this from a span never govern it (bounds the work per span)
# Facts read only from performed or incomplete text: they show a procedure was actually done.
EVIDENCE_FACTS = ('extent', 'interventions', 'cannulation', 'tissue_sampling')
EM_WITHOUT_BASIS = ('uncertain: procedure documentation with no MDM or E/M time does not establish a separate '
                    'office E/M service')
HEADING_ONLY = ('uncertain: an office visit note names this service under a procedure heading without documented '
                'extent or interventions')
EM_HEADINGS = {'chief complaint': 'chief complaint', 'cc': 'chief complaint', 'reason for visit': 'reason for visit',
               'medical decision making': 'medical decision making', 'medical decision-making': 'medical decision making',
               'mdm': 'medical decision making', 'decision making': 'medical decision making'}
# What may stand between two coordinated service names ("the EGD and the colonoscopy").
_CONNECTOR = re.compile(r'[\s,/&+]*(?:(?:and/or|and|or|nor|plus|then|followed\s+by|as\s+well\s+as)'
                        r'(?:\s+(?:the|a|an|her|his|their))?[\s,/&+]*)*', re.A | re.I)


@dataclass(frozen=True)
class Mention:
    family: str
    start: int
    end: int
    kind: str  # service | em-heading | em-visit | em-time | em-mdm
    label: str = ''
    value: str = ''  # minutes (em-time) or level (em-mdm)


@dataclass(frozen=True)
class Reading:
    status: str
    cues: tuple[str, ...]
    basis: str  # cue | section | default
    past_negation: bool = False  # negated only about earlier encounters ("no prior", "never had")


@dataclass(frozen=True)
class Cue:
    start: int
    end: int
    status: str
    name: str
    text: str


def _service_mentions(text: str) -> tuple[Mention, ...]:
    """Procedure-family names; where two overlap the longer one wins."""
    found = [Mention(family, m.start(), m.end(), 'service', m.group(0))
             for family, pattern in cues.SERVICE_PATTERNS for m in pattern.finditer(text)]
    found += [Mention('gi.flex_sig', m.start(), m.end(), 'service', m.group(0))
              for m in cues.FS_ABBREVIATION.finditer(text)]
    return _without_overlaps(found)


def _without_overlaps(found: list[Mention]) -> tuple[Mention, ...]:
    """Left to right; where two mentions overlap the longer one wins."""
    found.sort(key=lambda m: (m.start, -(m.end - m.start)))
    kept: list[Mention] = []
    for m in found:
        if not kept or m.start >= kept[-1].end:
            kept.append(m)
    return tuple(kept)


def _em_mentions(text: str, lay: Layout) -> tuple[Mention, ...]:
    found = []
    for section in lay.sections:
        label = EM_HEADINGS.get(section.label)
        if label and section.heading:
            h = section.heading
            found.append(Mention('gi.office_em', h.start, h.start + len(h.text.rstrip(':').rstrip()), 'em-heading',
                                 label))
        if section.kind == 'mdm' and section.heading:
            body = cues.MDM_BODY_LEVEL.match(text, section.heading.end, section.end)
            if body:
                found.append(Mention('gi.office_em', body.start('level'), body.end('level'), 'em-mdm', 'MDM level',
                                     body.group('level').lower()))
        if section.kind == 'time':
            for line in re.finditer(r'[^\n]+', text[section.start:section.end]):
                m = cues.EM_TIME_LINE.match(line.group(0))
                if m:
                    start = section.start + line.start()
                    found.append(Mention('gi.office_em', start + m.start(), start + m.end(), 'em-time', 'E/M time',
                                         str(int(m.group('minutes')))))
    for m in cues.EM_VISIT.finditer(text):
        found.append(Mention('gi.office_em', m.start(), m.end(), 'em-visit', m.group(0)))
    for m in cues.EM_TIME.finditer(text):
        s_start, s_end = lay.sentence_for(m.start(), m.end())
        if not cues.NOT_EM_TIME.search(text, s_start, s_end):
            found.append(Mention('gi.office_em', m.start(), m.end(), 'em-time', 'E/M time',
                                 str(int(m.group('minutes')))))
    for m in cues.MDM_LEVEL.finditer(text):
        level = (m.group('level') or m.group('level2')).lower()
        found.append(Mention('gi.office_em', m.start(), m.end(), 'em-mdm', 'MDM level', level))
    return _without_overlaps(found)


def _clause_cues(text: str) -> tuple[Cue, ...]:
    """Every clause-scope cue in the text, matched once over the whole text."""
    found = []
    for status, entries in (('cancelled', cues.CANCELLED_CLAUSE), ('incomplete', cues.INCOMPLETE_CLAUSE),
                            ('historical', cues.HISTORICAL_CLAUSE), ('planned', cues.PLANNED_CLAUSE),
                            ('uncertain', cues.UNCERTAIN_CLAUSE), ('performed', cues.PERFORMED_CLAUSE)):
        for name, pattern in entries:
            found.extend(Cue(m.start(), m.end(), status, name, m.group(0)) for m in pattern.finditer(text))
    return tuple(sorted(found, key=lambda c: (c.start, c.end)))


@dataclass(frozen=True)
class Intervention:
    label: str
    families: tuple[str, ...]
    start: int
    end: int


def _inside(items, starts: list[int], start: int, end: int) -> list:
    """Items (sorted by start) lying wholly inside [start, end)."""
    found = []
    for item in items[bisect.bisect_left(starts, start):]:
        if item.start >= end:
            break
        if item.end <= end:
            found.append(item)
    return found


@dataclass
class Analysis:
    text: str
    lay: Layout
    services: tuple[Mention, ...]
    em: tuple[Mention, ...]
    clause_cues: tuple[Cue, ...]
    dates: tuple[ctx.DateMention, ...]
    service_date: Optional[date]
    interventions: tuple[Intervention, ...]
    em_readings: dict = field(default_factory=dict)
    references: dict = field(default_factory=dict)  # Mention -> Reading for "the procedure was cancelled"
    attributed: list = field(default_factory=list)  # family per sentence
    # family -> (status, cue) that a "performed" reading of that family's service takes in this document
    adjustments: dict = field(default_factory=dict)

    def __post_init__(self):
        self._service_starts = [m.start for m in self.services]
        self._cue_starts = [c.start for c in self.clause_cues]
        self._date_starts = [d.start for d in self.dates]
        self._touchable = sorted([(m.start, m.end) for m in self.services]
                                 + [(i.start, i.end) for i in self.interventions])
        self._touchable_starts = [t[0] for t in self._touchable]
        self._longest = max((e - s for s, e in self._touchable), default=0)

    def services_in(self, start: int, end: int) -> list[Mention]:
        return _inside(self.services, self._service_starts, start, end)

    def cues_in(self, start: int, end: int) -> list[Cue]:
        return _inside(self.clause_cues, self._cue_starts, start, end)

    def dates_in(self, start: int, end: int) -> list[ctx.DateMention]:
        return _inside(self.dates, self._date_starts, start, end)

    def touches_service(self, start: int, end: int) -> bool:
        """Whether [start, end) overlaps a service name or an intervention word."""
        end = max(end, start + 1)
        low = bisect.bisect_left(self._touchable_starts, start - self._longest)
        for s, e in self._touchable[low:]:
            if s >= end:
                return False
            if e > start:
                return True
        return False


def _overlaps(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def _gap(a0: int, a1: int, b0: int, b1: int) -> int:
    if _overlaps(a0, a1, b0, b1):
        return 0
    return b0 - a1 if a1 <= b0 else a0 - b1


def _masked(an: Analysis, start: int, end: int) -> str:
    """text[start:end] with every service name replaced by SERVICE_TOKEN."""
    out, pos = [], start
    for m in an.services_in(start, end):
        out.append(an.text[pos:m.start])
        out.append(f' {cues.SERVICE_TOKEN} ')
        pos = m.end
    out.append(an.text[pos:end])
    return ''.join(out)


def _merge_groups(text: str, items: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    groups: list[list[tuple[int, int]]] = []
    for item in sorted(items):
        if groups and _CONNECTOR.fullmatch(text[groups[-1][-1][1]:item[0]]):
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def _groups(an: Analysis, cs: int, ce: int, ts: int, te: int) -> tuple[list[tuple[int, int]], int, list[tuple[int, int]]]:
    """Coordinated mention groups of a clause ("EGD and colonoscopy" is one group),
    the index of the target's group and that group's members, including every
    service named inside the target (each is read with its own anchored cues)."""
    target = (max(ts, cs), min(max(te, ts + 1), ce))
    items, inner = [], []
    for m in an.services_in(cs, ce):
        if _overlaps(m.start, m.end, *target):
            inner.append((m.start, m.end))
            target = (min(target[0], m.start), max(target[1], m.end))
        else:
            items.append((m.start, m.end))
    items.append(target)
    groups = _merge_groups(an.text, items)
    index = next(i for i, g in enumerate(groups) if target in g)
    return [(g[0][0], g[-1][1]) for g in groups], index, groups[index] + inner


def _attached(spans: list[tuple[int, int]], index: int, start: int, end: int, reach: Optional[int] = None) -> bool:
    gaps = [_gap(start, end, gs, ge) for gs, ge in spans]
    return gaps[index] == min(gaps) and (reach is None or gaps[index] <= reach)


def _clause_reading_cues(an: Analysis, clause: tuple[int, int], ts: int, te: int) -> list[tuple[str, str, bool]]:
    """(status, label, about_past) for every cue that governs the target in one clause."""
    text = an.text
    cs, ce = an.lay.window(clause, ts, te, CLAUSE_REACH)
    spans, index, members = _groups(an, cs, ce, ts, te)
    clause = text[cs:ce]
    found = []
    for cue in an.cues_in(cs, ce):
        status = cue.status
        if cue.name == 'aborted':
            s_start, s_end = an.lay.window(an.lay.sentence_for(cue.start, cue.end), cue.start, cue.end, CLAUSE_REACH)
            if cues.STARTED.search(text, s_start, s_end) and not cues.BEFORE_START.search(text, s_start, s_end):
                status = 'incomplete'
        if cue.name in ('terminated', 'stopped') and cues.MEDICATION.search(clause):
            continue
        if _attached(spans, index, cue.start, cue.end):
            found.append((status, f'{status}: {cue.text}', False))
    for d in an.dates_in(cs, ce):
        if not _attached(spans, index, d.start, d.end, DATE_REACH):
            continue
        label = text[d.start:d.end]
        if an.service_date is None:
            found.append(('uncertain', f'uncertain: dated {label}; service date not established', False))
        else:
            order = ctx.compare_to_service(d, an.service_date)
            if order < 0:
                found.append(('historical', f'historical: {label} is before the service date', False))
            elif order > 0 and not d.bare:  # a lone future "year" is more often a room or a count
                found.append(('planned', f'planned: {label} is after the service date', False))
    today = bool(cues.TODAY.search(clause))
    for ms, me in members:
        pre, post = _masked(an, cs, ms), _masked(an, me, ce)
        for name, pattern in cues.NEGATED_PRE:
            m = pattern.search(pre)
            if m:
                found.append(('negated', f'negated: {m.group(0).strip()}', bool(cues.NEGATION_ABOUT_PAST.search(m.group(0)))))
        for name, pattern in cues.NEGATED_POST:
            m = pattern.search(post)
            if m:
                found.append(('negated', f'negated: {m.group(0).strip()}', False))
        for m in cues.NEGATED_SPAN.finditer(text, cs, ce):
            if m.start('body') <= ms and me <= m.end('body'):
                found.append(('negated', f'negated: {m.group(0).strip()}', bool(cues.NEGATION_ABOUT_PAST.search(m.group(0)))))
        for status, entries in (('historical', cues.HISTORICAL_PRE), ('planned', cues.PLANNED_PRE),
                                ('incomplete', cues.INCOMPLETE_PRE), ('uncertain', cues.UNCERTAIN_PRE)):
            for name, pattern in entries:
                m = pattern.search(pre)
                if m:
                    found.append((status, f'{status}: {m.group(0).strip()}', False))
        m = cues.HAD_PRE.search(pre)
        if m and not today:
            found.append(('historical', f'historical: {m.group(0).strip()}', False))
        for status, entries in (('incomplete', cues.INCOMPLETE_POST), ('uncertain', cues.UNCERTAIN_POST)):
            for name, pattern in entries:
                m = pattern.search(post)
                if m:
                    found.append((status, f'{status}: {m.group(0).strip()}', False))
    return found


def _section_label(section) -> str:
    heading = f' ({section.heading.text.rstrip(":").strip()})' if section.heading else ''
    return f'section: {section.kind}{heading}'


def _cue_reading(an: Analysis, start: int, end: int) -> Optional[Reading]:
    found = []
    for clause in an.lay.clauses_for(start, end):
        found.extend(_clause_reading_cues(an, clause, start, end))
    if not found:
        return None
    status = next(s for s in STATUS_PRECEDENCE if any(f[0] == s for f in found))
    deciding = tuple(dict.fromkeys(label for s, label, _ in found if s == status))
    past = status == 'negated' and all(p for s, _, p in found if s == 'negated')
    section = an.lay.section_at(start)
    if status == 'performed' and section.kind == 'history':
        today = any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(start, end))
        return Reading('uncertain' if today else 'historical', deciding + (_section_label(section),), 'cue')
    if status == 'performed' and section.kind == 'plan':
        return Reading('uncertain', deciding + (_section_label(section),), 'cue')
    return Reading(status, deciding, 'cue', past)


def _default_reading(an: Analysis, start: int, end: int) -> Reading:
    section = an.lay.section_at(start)
    label = _section_label(section)
    if section.kind in POSITIVE_SECTIONS:
        return Reading('performed', (label,), 'section')
    if section.kind == 'plan':
        return Reading('planned', (label,), 'section')
    if section.kind == 'history':
        return Reading('historical', (label,), 'section')
    if section.kind in EM_SECTIONS and not an.touches_service(start, end):
        return Reading('performed', (label + ': E/M documentation of this encounter',), 'section')
    return Reading('uncertain', ('uncertain: no performance evidence in its sentence or section',), 'default')


def _generic_reading(an: Analysis, start: int, end: int) -> Reading:
    return _cue_reading(an, start, end) or _default_reading(an, start, end)


def _read_span(an: Analysis, start: int, end: int) -> Reading:
    """The reading of [start, end). A span with no service name in it that covers
    an E/M documentation mention or a procedure reference reads as that mention."""
    if not an.touches_service(start, end):
        for mentions, readings in ((an.references, an.references), (an.em, an.em_readings)):
            for m in mentions:
                if _overlaps(m.start, m.end, start, max(end, start + 1)):
                    return readings[m]
    reading = _generic_reading(an, start, end)
    if reading.status == 'performed' and (an.touches_service(start, end)
                                          or an.lay.section_at(start).kind in POSITIVE_SECTIONS):
        return _adjusted(reading, an.adjustments.get(_family_of_span(an, start, end)))
    return reading


def _adjusted(reading: Reading, adjustment: Optional[tuple[str, str]]) -> Reading:
    """A performed reading takes the document-level judgement of its family's service
    (cancelled, not evidenced in an office note, or not completed)."""
    if adjustment is None or reading.status != 'performed':
        return reading
    status, cue = adjustment
    return Reading(status, reading.cues + (cue,), reading.basis)


def _family_of_span(an: Analysis, start: int, end: int) -> Optional[str]:
    named = {m.family for m in an.services if _overlaps(m.start, m.end, start, max(end, start + 1))}
    if named:
        return named.pop() if len(named) == 1 else None
    index = _sentence_index(an, start)
    return an.attributed[index] if index >= 0 and an.attributed else None


# --- which family a sentence describes --------------------------------------------

_UPPER_TRACT = ('gi.egd', 'gi.eus', 'gi.ercp')
_LOWER_TRACT = ('gi.colonoscopy', 'gi.flex_sig')


def _only(candidates) -> Optional[str]:
    candidates = list(dict.fromkeys(candidates))
    return candidates[0] if len(candidates) == 1 else None


def _hinted_family(an: Analysis, s: int, e: int, families: list[str]) -> Optional[str]:
    by_instrument = _only(f for f, p in cues.INSTRUMENTS if f in families and p.search(an.text, s, e))
    if by_instrument:
        return by_instrument
    upper = any(p.search(an.text, s, e) for _, _, p in cues.UPPER_LANDMARKS)
    lower = any(p.search(an.text, s, e) for _, _, p in cues.LOWER_LANDMARKS)
    if upper and not lower:
        return 'gi.egd' if 'gi.egd' in families else _only(f for f in _UPPER_TRACT if f in families)
    if lower and not upper:
        return _only(f for f in _LOWER_TRACT if f in families)
    return None


def _attribute_sentences(an: Analysis, families: list[str]) -> list[Optional[str]]:
    """The procedure family each sentence describes, or None when it cannot be told."""
    result: list[Optional[str]] = []
    current, current_section = None, None
    for s, e in an.lay.sentences:
        section = an.lay.section_at(s)
        if section is not current_section:
            current_section = section
            heading = section.heading
            current = _only(m.family for m in an.services_in(heading.start, heading.end)
                            if m.family in families) if heading else None
        named = list(dict.fromkeys(m.family for m in an.services_in(s, e) if m.family in families))
        if len(named) > 1:
            result.append(None)
            continue
        family = named[0] if named else _hinted_family(an, s, e, families)
        if family:
            current = family
        elif current:
            family = current
        elif len(families) == 1:
            family = families[0]
        result.append(family)
    return result


def _sentence_index(an: Analysis, pos: int) -> int:
    index = bisect.bisect_right(an.lay.sentences, (pos, 1 << 62)) - 1
    return index if index >= 0 and pos < an.lay.sentences[index][1] else -1


def _clauses_in(an: Analysis, s: int, e: int) -> list[tuple[int, int]]:
    clauses = an.lay.clauses
    found = []
    for c in clauses[bisect.bisect_left(clauses, (s, -1)):]:
        if c[0] >= e:
            break
        if c[1] <= e:
            found.append(c)
    return found


def _span(text: str, start: int, end: int) -> Span:
    return Span(start, end, text[start:end])


def _fact(name: str, found: list[tuple[str, Span]]) -> Optional[Fact]:
    """Absent when nothing is documented; a conflict when values differ."""
    if not found:
        return None
    values = list(dict.fromkeys(v for v, _ in found))
    evidence = tuple(sorted(dict.fromkeys(s for _, s in found), key=lambda s: (s.start, s.end)))
    if len(values) == 1:
        return Fact(name, values[0], 'document', evidence)
    return Fact(name, None, 'conflict', evidence, 'Conflicting documented values: ' + ', '.join(values) + '.')


def _joined(name: str, found: list[tuple[str, Span]]) -> Optional[Fact]:
    """Several documented values that are all true at once ("biopsy; cold snare")."""
    if not found:
        return None
    values = list(dict.fromkeys(v for v, _ in found))
    evidence = tuple(sorted(dict.fromkeys(s for _, s in found), key=lambda s: (s.start, s.end)))
    return Fact(name, '; '.join(values), 'document', evidence)


def _family_sentences(an: Analysis, attributed: list[Optional[str]], family: str) -> list[tuple[int, int]]:
    return [span for span, f in zip(an.lay.sentences, attributed) if f == family]


def _landmarks(an: Analysis, sentences, table) -> tuple[list, list]:
    """(reached, blocked) as (depth, label, clause span) for landmarks read as
    part of a performed or incomplete service."""
    text = an.text
    reached, blocked = [], []
    for s, e in sentences:
        for cs, ce in _clauses_in(an, s, e):
            for label, depth, pattern in table:
                for m in pattern.finditer(text, cs, ce):
                    status = _generic_reading(an, m.start(), m.end()).status
                    ws, we = an.lay.window((cs, ce), m.start(), m.end(), CLAUSE_REACH)
                    pre, post = text[ws:m.start()], text[m.end():we]
                    hit = (depth, label, _span(text, cs, ce))
                    if status in ('performed', 'incomplete') and cues.REACHED_BEYOND.search(pre):
                        reached.append(hit)
                    elif status in ('performed', 'incomplete', 'negated') and (
                            cues.NOT_REACHED_BEFORE.search(pre) or cues.NOT_REACHED_AFTER.search(post)):
                        blocked.append(hit)
                    elif status in ('performed', 'incomplete') and (
                            cues.REACHED_BEFORE.search(pre) or cues.REACHED_AFTER.search(post)):
                        reached.append(hit)
    return reached, blocked


_REFERENCE_PATTERNS = ((('cancelled', cues.PROCEDURE_CANCELLED), ('negated', cues.PROCEDURE_NOT_PERFORMED),
                        ('incomplete', cues.PROCEDURE_INCOMPLETE), (None, cues.ABORTED))
                       + tuple(('incomplete', pattern) for _, pattern in cues.INCOMPLETE_CLAUSE))


def _references(an: Analysis, attributed: list[Optional[str]]) -> dict[Mention, Reading]:
    """Clauses that refer to a family's service without naming it ("the procedure
    was cancelled", "unable to advance beyond the splenic flexure"). Only these
    not-done and not-completed readings are taken from a reference, never a
    performed one."""
    text = an.text
    found: dict[Mention, Reading] = {}
    for (s, e), family in zip(an.lay.sentences, attributed):
        if family is None or an.lay.section_at(s).kind in ('plan', 'history', 'indication'):
            continue
        for cs, ce in _clauses_in(an, s, e):
            if an.services_in(cs, ce) or cues.MEDICATION.search(text, cs, ce):
                continue
            for status, pattern in _REFERENCE_PATTERNS:
                for m in pattern.finditer(text, cs, ce):
                    context = _generic_reading(an, m.start(), m.end()).status
                    if context in ('historical', 'planned'):
                        continue
                    status_here = status or context  # "aborted": cancelled before insertion, incomplete after
                    mention = Mention(family, m.start(), m.end(), 'reference', m.group(0))
                    found[mention] = Reading(status_here, (f'{status_here}: {m.group(0)}',), 'cue')
    return {m: found[m] for m in _without_overlaps(list(found))}


# --- family facts -------------------------------------------------------------------

def _interventions(an: Analysis, attributed: list[Optional[str]], family: str) -> Optional[Fact]:
    found = []
    for iv in an.interventions:
        index = _sentence_index(an, iv.start)
        if family not in iv.families or index < 0 or attributed[index] != family:
            continue
        if _generic_reading(an, iv.start, iv.end).status == 'performed':
            found.append((iv.label, _span(an.text, iv.start, iv.end)))
    labels = {label for label, _ in found}
    found = [(label, span) for label, span in found
             if not any(other in labels for other in cues.SUPERSEDED_BY.get(label, ()))]
    order = [label for label, _, _ in cues.INTERVENTIONS]
    found.sort(key=lambda item: (order.index(item[0]), item[1].start))
    return _joined('interventions', found)


def _colon_extent(an: Analysis, sentences) -> Optional[Fact]:
    reached, blocked = _landmarks(an, sentences, cues.LOWER_LANDMARKS)
    if not reached:
        return None
    depth, label, span = max(reached, key=lambda hit: hit[0])
    if depth < cues.CECUM_DEPTH:
        evidence = [span] + [b[2] for b in blocked if b[0] > depth]
        return Fact('extent', f'incomplete: {label}', 'document', tuple(dict.fromkeys(evidence)))
    return Fact('extent', label, 'document', (span,))


def _upper_extent(an: Analysis, sentences, incomplete: bool) -> Optional[Fact]:
    reached, _ = _landmarks(an, sentences, cues.UPPER_LANDMARKS)
    if not reached:
        return None
    _, label, span = max(reached, key=lambda hit: hit[0])
    return Fact('extent', f'incomplete: {label}' if incomplete else label, 'document', (span,))


def _flex_sig_extent(an: Analysis, sentences) -> Optional[Fact]:
    text = an.text
    found = []
    for s, e in sentences:
        for cs, ce in _clauses_in(an, s, e):
            if not cues.ADVANCED.search(text, cs, ce):
                continue
            for m in cues.CENTIMETERS.finditer(text, cs, ce):
                if _generic_reading(an, m.start(), m.end()).status in ('performed', 'incomplete'):
                    found.append((f"{int(m.group('cm'))} cm", _span(text, cs, ce)))
    if found:
        return _fact('extent', found)
    reached, _ = _landmarks(an, sentences, cues.LOWER_LANDMARKS)
    if not reached:
        return None
    _, label, span = max(reached, key=lambda hit: hit[0])
    return Fact('extent', label, 'document', (span,))


def _polyp_count(an: Analysis, attributed: list[Optional[str]]) -> Optional[Fact]:
    text = an.text
    for kinds in (('findings',), ('procedure', 'technique')):
        total, evidence, uncounted = 0, [], False
        for (s, e), family in zip(an.lay.sentences, attributed):
            if family != 'gi.colonoscopy' or an.lay.section_at(s).kind not in kinds:
                continue
            uncounted = uncounted or bool(cues.POLYP_UNCOUNTED.search(text, s, e))
            for m in cues.POLYP_COUNT.finditer(text, s, e):
                if _generic_reading(an, m.start(), m.end()).status != 'performed':
                    continue
                number = m.group('n').lower()
                total += int(number) if number.isdigit() else cues.NUMBER_WORDS[number]
                evidence.append(_span(text, m.start(), m.end()))
        if uncounted:
            return None
        if evidence:
            return Fact('polyp_count', str(total), 'document', tuple(evidence))
    return None


def _intent(an: Analysis, attributed: list[Optional[str]], only_family: bool) -> Optional[Fact]:
    text = an.text
    found = []
    for (s, e), family in zip(an.lay.sentences, attributed):
        indication = an.lay.section_at(s).kind == 'indication'
        for cs, ce in _clauses_in(an, s, e):
            for m in cues.INTENT.finditer(text, cs, ce):
                services = an.services_in(cs, ce)
                if services:
                    groups = _merge_groups(text, [(svc.start, svc.end) for svc in services])
                    nearest = min(groups, key=lambda g: _gap(m.start(), m.end(), g[0][0], g[-1][1]))
                    ok = any(svc.family == 'gi.colonoscopy' for svc in services if (svc.start, svc.end) in nearest)
                else:
                    ok = indication and family == 'gi.colonoscopy' and (
                        only_family or bool(cues.COLON_WORDS.search(text, cs, ce)))
                if ok:
                    found.append((m.group('intent').lower(), _span(text, m.start(), m.end())))
    return _fact('intent', found)


def _prep_quality(an: Analysis, sentences) -> Optional[Fact]:
    text = an.text
    words, scores = [], []
    for s, e in sentences:
        if an.lay.section_at(s).kind in ('plan', 'history'):
            continue
        for m in cues.PREP_QUALITY.finditer(text, s, e):
            words.append(((m.group('q') or m.group('q2')).lower(), _span(text, m.start(), m.end())))
        for m in cues.BBPS.finditer(text, s, e):
            if int(m.group('score')) <= 9:
                scores.append((f"BBPS {int(m.group('score'))}", _span(text, m.start(), m.end())))
    word, score = _fact('prep_quality', words), _fact('prep_quality', scores)
    if word and score and word.value and score.value:
        return Fact('prep_quality', f'{word.value} ({score.value})', 'document',
                    tuple(sorted(word.evidence + score.evidence, key=lambda sp: sp.start)))
    return word or score


def _incomplete_reason(an: Analysis, incomplete: list[Mention]) -> Optional[Fact]:
    """Documented reasons in the sentences that say the service was not completed."""
    text = an.text
    found = []
    for mention in incomplete:
        s, e = an.lay.window(an.lay.sentence_for(mention.start, mention.end), mention.start, mention.end, CLAUSE_REACH)
        for label, pattern in cues.INCOMPLETE_REASONS:
            found.extend((label, _span(text, m.start(), m.end())) for m in pattern.finditer(text, s, e))
    return _joined('incomplete_reason', sorted(dict.fromkeys(found), key=lambda item: item[1].start))


def _eus_facts(an: Analysis, sentences) -> list[Fact]:
    text = an.text
    sampling, sampled_sentences = [], []
    for s, e in sentences:
        for label, pattern in (('FNA', cues.EUS_FNA), ('FNB', cues.EUS_FNB)):
            for m in pattern.finditer(text, s, e):
                if _generic_reading(an, m.start(), m.end()).status == 'performed':
                    sampling.append((label, _span(text, m.start(), m.end())))
                    sampled_sentences.append((s, e))
    tiers = [sampled_sentences,
             [(m.end(), an.lay.sentence_for(m.start(), m.end())[1]) for m in cues.EUS_TARGET_PHRASE.finditer(text)],
             [(s, e) for s, e in sentences if an.lay.section_at(s).kind == 'indication']]
    target = None
    for tier in tiers:
        found = []
        for s, e in tier:
            for template, pattern in cues.EUS_TARGETS:
                for m in pattern.finditer(text, s, e):
                    if not any(_overlaps(m.start(), m.end(), sp.start, sp.end) for _, sp in found):
                        groups = [g.lower() for g in m.groups() if g]
                        found.append((template.format(*groups), _span(text, m.start(), m.end())))
        if found:
            found.sort(key=lambda item: item[1].start)
            target = _joined('target', found)
            break
    if sampling:
        sampled = _joined('tissue_sampling', sorted(sampling, key=lambda item: (item[0], item[1].start)))
    else:
        stated = [_span(text, m.start(), m.end()) for s, e in sentences for m in cues.SAMPLING_NONE.finditer(text, s, e)]
        sampled = Fact('tissue_sampling', 'none documented', 'document' if stated else 'missing', tuple(stated),
                       '' if stated else 'No FNA or FNB is documented as performed.')
    return [f for f in (target, sampled) if f]


def _cannulation(an: Analysis, sentences) -> Optional[Fact]:
    """Successful or failed; both documented is a conflict for a reviewer, never a pick."""
    text = an.text
    found = []
    for s, e in sentences:
        for value, pattern, readable in (('successful', cues.CANNULATION_SUCCESS, ('performed', 'incomplete')),
                                         ('failed', cues.CANNULATION_FAILED, ('performed', 'incomplete', 'negated'))):
            for m in pattern.finditer(text, s, e):
                if _generic_reading(an, m.start(), m.end()).status in readable:
                    found.append((value, _span(text, m.start(), m.end())))
    failed_spans = {sp for v, sp in found if v == 'failed'}
    found = [(v, sp) for v, sp in found
             if v == 'failed' or not any(_overlaps(sp.start, sp.end, f.start, f.end) for f in failed_spans)]
    return _fact('cannulation', found)


def _egd_location(an: Analysis, interventions: Optional[Fact]) -> Optional[Fact]:
    if not interventions:
        return None
    found = []
    for span in interventions.evidence:
        for cs, ce in an.lay.clauses_for(span.start, span.end):
            hits = sorted(((m.start(), -(m.end() - m.start()), m.end(), label) for label, p in cues.UPPER_LOCATIONS
                           for m in p.finditer(an.text, cs, ce)))
            last_end = -1
            for start, _, end, label in hits:
                if start >= last_end:
                    found.append((label, _span(an.text, start, end)))
                    last_end = end
    found.sort(key=lambda item: item[1].start)
    return _joined('location', found)


def _aggregate(readings: list[Reading], section_suffices: bool = True) -> str:
    """Performed on explicit evidence, or on section evidence nothing contradicts;
    else incomplete; else the most informative remaining status."""
    explicit = any(r.status == 'performed' and r.basis == 'cue' for r in readings)
    by_section = section_suffices and any(r.status == 'performed' and r.basis == 'section' for r in readings)
    contradicted = any(r.status == 'cancelled' or (r.status == 'negated' and not r.past_negation) for r in readings)
    if explicit or (by_section and not contradicted):
        return 'performed'
    statuses = {r.status for r in readings}
    return next((s for s in ('incomplete',) + AGGREGATE_ORDER if s in statuses), 'uncertain')


def _procedure_facts(an: Analysis, family: str, attributed, only_family: bool,
                     incomplete: list[Mention]) -> tuple[list[Fact], bool]:
    """(facts, incompleteness documented for the service) for one procedure family."""
    sentences = _family_sentences(an, attributed, family)
    interventions = _interventions(an, attributed, family)
    short = False
    if family == 'gi.colonoscopy':
        extent = _colon_extent(an, sentences)
        short = bool(extent and extent.value.startswith('incomplete'))
        facts = [extent, interventions, _polyp_count(an, attributed), _intent(an, attributed, only_family),
                 _prep_quality(an, sentences), _incomplete_reason(an, incomplete) if incomplete or short else None]
    elif family == 'gi.egd':
        facts = [_upper_extent(an, sentences, bool(incomplete)), interventions, _egd_location(an, interventions)]
    elif family == 'gi.flex_sig':
        facts = [_flex_sig_extent(an, sentences), interventions]
    elif family == 'gi.eus':
        facts = _eus_facts(an, sentences)
    else:
        cannulation = _cannulation(an, sentences)
        short = bool(cannulation and cannulation.value == 'failed')
        facts = [cannulation, interventions]
    return [f for f in facts if f], bool(incomplete) or short


def _em_base_reading(an: Analysis, m: Mention) -> Reading:
    cue = _cue_reading(an, m.start, m.end)
    if cue and cue.status != 'performed':
        return cue
    if m.kind == 'em-visit' and cue is None and an.lay.section_at(m.start).kind in ('plan', 'history'):
        return _default_reading(an, m.start, m.end)
    label = 'visit statement' if m.kind == 'em-visit' else m.label
    return Reading('performed', (cue.cues if cue else ()) + (f'performed: office E/M documentation ({label})',), 'cue')


# The clinician's own statement that a same-day E/M was significant and separately
# identifiable (e.g. an addendum answering that clarification). Only an explicit,
# non-negated statement outside plan/history counts; nothing is inferred.
_SEPARATE_EM = re.compile(r'\b(?:significant\s*,?\s*(?:and\s+)?)?separately[\s-]+identifiable\b', re.A | re.I)
_SEPARATE_EM_NEGATION = re.compile(r"\b(?:not|no|without|never|cannot|isn't|wasn't)\b[^.;:\n]{0,60}$", re.A | re.I)
SEPARATE_EM_NOTE = 'The documentation states a significant, separately identifiable E/M service.'


def _separate_em_fact(an: Analysis) -> Optional[Fact]:
    text, spans = an.text, []
    for match in _SEPARATE_EM.finditer(text):
        start, _ = an.lay.sentence_for(match.start(), match.end())
        if _SEPARATE_EM_NEGATION.search(text[start:match.start()]):
            continue
        if an.lay.section_at(match.start()).kind in ('plan', 'history'):
            continue
        spans.append(_span(text, match.start(), match.end()))
    return Fact('separate_em', 'documented', 'document', tuple(spans), SEPARATE_EM_NOTE) if spans else None


def _em_facts(an: Analysis, readings: dict) -> list[Fact]:
    text = an.text
    context_facts = ctx.extract_context(text)
    facts = [context_facts[name] for name in ('setting', 'patient_status')
             if context_facts[name].origin in ('document', 'conflict')]
    done = [m for m in an.em if readings[m].status == 'performed']
    times = [(m.value, _span(text, m.start, m.end)) for m in done if m.kind == 'em-time']
    levels = [(m.value, _span(text, m.start, m.end)) for m in done if m.kind == 'em-mdm']
    mdm = levels + [('mdm', _span(text, m.start, m.end)) for m in done
                    if m.kind == 'em-heading' and m.label == 'medical decision making']
    basis = '+'.join(name for name, found in (('time', times), ('mdm', mdm)) if found)
    if basis:
        evidence = tuple(sorted(dict.fromkeys(s for _, s in times + mdm), key=lambda s: s.start))
        facts.append(Fact('em_basis', basis, 'document', evidence))
    facts += [f for f in (_fact('time_minutes', times), _fact('mdm_level', levels), _separate_em_fact(an)) if f]
    return facts


def _missing(family: str, facts: list[Fact]) -> tuple[str, ...]:
    known = {f.name for f in facts if f.value is not None}
    return tuple(name for name in PROFILES[family].required_facts if name not in known)


def _mention(an: Analysis, m: Mention, reading: Reading) -> ServiceMention:
    s, e = an.lay.sentence_for(m.start, m.end)
    return ServiceMention(family=m.family, status=reading.status, span=_span(an.text, m.start, m.end),
                          sentence=_span(an.text, s, e), section=an.lay.section_at(m.start).kind, cues=reading.cues)


def _adjustment(status: str, readings: list[Reading], facts: list[Fact], plain: str) -> Optional[tuple[str, str]]:
    """(status, cue) a performed mention of a family takes when the family as a whole is
    not performed; None when the family is performed."""
    if status == 'performed':
        return None
    if status == 'incomplete':
        cues_found = [r.cues[0] for r in readings if r.status == 'incomplete']
        cues_found += [f'incomplete: {f.name} {f.value}' for f in facts
                       if (f.name, f.value) == ('cannulation', 'failed')
                       or (f.name == 'extent' and (f.value or '').startswith('incomplete'))]
        return 'incomplete', cues_found[0]
    contrary = [r for r in readings if r.status == 'cancelled' or (r.status == 'negated' and not r.past_negation)]
    if plain == 'performed' and not contrary:
        return 'uncertain', HEADING_ONLY
    return status, next(r for r in contrary + readings if r.status == status).cues[0]


def _route(an: Analysis) -> RoutingResult:
    readings = {m: _generic_reading(an, m.start, m.end) for m in an.services}
    detected = [f for f in PROCEDURE_FAMILIES if any(m.family == f for m in an.services)]
    attributed = an.attributed = _attribute_sentences(an, detected)
    an.references = _references(an, attributed)
    readings.update(an.references)
    base = {m: _em_base_reading(an, m) for m in an.em}
    em_facts = _em_facts(an, base)
    has_basis = any(f.name == 'em_basis' for f in em_facts)
    findings: dict[str, FamilyFinding] = {}
    for family in detected:
        mentions = sorted([m for m in an.services if m.family == family]
                          + [m for m in an.references if m.family == family], key=lambda m: m.start)
        incomplete = [m for m in mentions if readings[m].status == 'incomplete']
        facts, short = _procedure_facts(an, family, attributed, len(detected) == 1, incomplete)
        # In an office visit note a "Procedures" heading alone is not evidence the
        # service was done today; documented extent or interventions are.
        evidenced = any(f.name in EVIDENCE_FACTS and f.origin == 'document' and f.value not in (None, 'none documented')
                        for f in facts)
        family_readings = [readings[m] for m in mentions]
        status = _aggregate(family_readings, section_suffices=evidenced or not has_basis)
        if status not in ('performed', 'incomplete'):
            facts = [f for f in facts if f.origin != 'missing']  # "no sampling documented" speaks only of a done EUS
        if status == 'performed' and short:
            status = 'incomplete'
        an.adjustments[family] = _adjustment(status, family_readings, facts, _aggregate(family_readings))
        findings[family] = FamilyFinding(
            family, status, tuple(_mention(an, m, _adjusted(readings[m], an.adjustments[family])) for m in mentions),
            tuple(facts), _missing(family, facts))
    procedure_done = any(f.status in ('performed', 'incomplete') for f in findings.values())
    an.em_readings = {m: (Reading('uncertain', r.cues + (EM_WITHOUT_BASIS,), 'cue')
                          if r.status == 'performed' and procedure_done and not has_basis else r)
                      for m, r in base.items()}
    if an.em:
        status = _aggregate(list(an.em_readings.values()))
        findings['gi.office_em'] = FamilyFinding(
            'gi.office_em', status, tuple(_mention(an, m, an.em_readings[m]) for m in an.em), tuple(em_facts),
            _missing('gi.office_em', em_facts))
    office = 'gi.office_em' in findings and findings['gi.office_em'].status == 'performed'
    kind = {(True, False): 'procedure_report', (False, True): 'office_note', (True, True): 'mixed'}.get(
        (procedure_done, office), 'unknown')
    ordered = tuple(findings[f] for f in FAMILY_ORDER if f in findings)
    return RoutingResult(version=ROUTING_VERSION, document_kind=kind, findings=ordered)


@functools.lru_cache(maxsize=16)
def _analysis(text: str) -> tuple[Analysis, RoutingResult]:
    lay = layout(text)
    interventions = tuple(Intervention(label, families, m.start(), m.end())
                          for label, pattern, families in cues.INTERVENTIONS for m in pattern.finditer(text))
    an = Analysis(text, lay, _service_mentions(text), _em_mentions(text, lay), _clause_cues(text),
                  ctx.find_dates(text), ctx.service_date_of(text), interventions)
    return an, _route(an)


def route(text: str) -> RoutingResult:
    """The GI services the document describes, with status, facts and missing facts."""
    if not isinstance(text, str):
        raise TypeError('route() needs the canonical text as str.')
    return _analysis(text)[1]


def status_for_span(text: str, start: int, end: int) -> tuple[str, tuple[str, ...]]:
    """Status of the service mentioned at [start, end), judged from its clause,
    sentence and section, with the cues that decided it. Fail-closed."""
    if not isinstance(text, str):
        raise TypeError('status_for_span() needs the canonical text as str.')
    if not (0 <= start < end <= len(text)):
        raise ValueError(f'span [{start}, {end}) is not a non-empty range inside the text (length {len(text)}).')
    reading = _read_span(_analysis(text)[0], start, end)
    return reading.status, reading.cues
