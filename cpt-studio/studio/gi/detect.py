"""GI service routing: which services a document describes, their status, and
the family facts that support them. See ARCHITECTURE.md section 5.3.

Status is fail-closed. A mention is "performed" only with positive evidence:
an explicit past-tense performance cue in its clause, or a procedure /
findings / technique section with no contrary cue. Every other reading -
planned, historical, cancelled, negated, incomplete or uncertain - keeps the
service from silently becoming a performed one. A negation word in the clause
that no anchored negation pattern, clause cue or narrow exception accounts for
turns "performed" into "uncertain" (a doubt), and a doubt contradicts section
evidence just as a negation does.

A family is performed when a mention carries explicit evidence, or section
evidence that no cancellation, negation or doubt about today's service
contradicts (in an office visit note, section evidence also needs documented
extent or interventions). A performed service whose incompleteness is
documented - an incomplete mention, extent short of the cecum or of the
duodenum, failed cannulation, "the procedure was terminated" - is incomplete.
Otherwise the family is cancelled or negated when a mention says so of today's
service, and uncertain when a doubt about today's service leaves it open; only
then does it take what its mentions say of other encounters (historical,
planned, or a negation of earlier encounters such as "no prior colonoscopy").
A plan or history section speaks of other encounters, so nothing there
contradicts today's service. Doubt never cascades: a family's judgement reaches
its other passages only as cancelled, incomplete or uncertain, never as
planned, historical or negated. Sentences
that refer to a service without naming it ("the procedure was cancelled")
become mentions only when they say it was not done or not completed, never to
make it performed. Facts are read only from text read as performed (or
incomplete) for this encounter, never from a clause that names a procedure not
done at this encounter ("On her colonoscopy in 2023 the cecum was reached").

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
from studio.gi import sections as gi_sections
from studio.gi.sections import Layout, layout
from studio.types import Fact, FamilyFinding, RoutingResult, ServiceMention, Span

ROUTING_VERSION = 'gi-routing@3'
PROCEDURE_FAMILIES = tuple(f for f in DETECTED_FAMILIES if PROFILES[f].procedure)
# Within one mention the strongest reading wins; "performed" never beats a doubt.
STATUS_PRECEDENCE = ('negated', 'historical', 'cancelled', 'incomplete', 'planned', 'uncertain', 'performed')
# Across a family's mentions (ARCHITECTURE 5.3), after performed and incomplete: first what the
# mentions say of today's service (cancelled, negated, a doubt), then this order, for what they say
# only of other encounters. A doubt about today ranks above every reading about another encounter,
# so a plan, a history or a negation of earlier encounters never decides a family whose service
# today is in doubt (see _aggregate).
ELSEWHERE_ORDER = ('negated', 'historical', 'planned')
POSITIVE_SECTIONS = ('procedure', 'findings', 'technique')
# Sections whose text speaks of other encounters: a mention there (unless its clause says today)
# never contradicts today's service, whatever its cues.
ELSEWHERE_SECTIONS = ('plan', 'history')
EM_SECTIONS = ('mdm', 'time')
DATE_REACH = 40  # a date speaks for a mention only within this many characters
CLAUSE_REACH = 300  # cues further than this from a span never govern it (bounds the work per span)
# Facts read only from performed or incomplete text: they show a procedure was actually done.
EVIDENCE_FACTS = ('extent', 'interventions', 'cannulation', 'tissue_sampling')
EM_WITHOUT_BASIS = ('uncertain: procedure documentation with no MDM or E/M time does not establish a separate '
                    'office E/M service')
HEADING_ONLY = ('uncertain: an office visit note names this service under a procedure heading without documented '
                'extent or interventions')
# What a performed passage of a family takes when no mention of the family documents it as performed
# at this encounter: held for clarification, never excluded as that other status.
UNESTABLISHED = 'uncertain: no mention of this service documents it as performed at this encounter'
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
    # uncertain because of an unresolved negation, an abort that does not say whether the
    # procedure started, or "pending": it contradicts section evidence like a negation does
    doubt: bool = False


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
    """Items (sorted by start) lying wholly inside [start, end). Indexed, never sliced: a slice would
    copy every later item on each call."""
    found = []
    for index in range(bisect.bisect_left(starts, start), len(items)):
        item = items[index]
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
    # (start, end) of each OTHER_FAMILY procedure name, sorted: items of a check-box line (_unchecked_box)
    other_names: tuple = ()

    def __post_init__(self):
        self._service_starts = [m.start for m in self.services]
        self._cue_starts = [c.start for c in self.clause_cues]
        self._date_starts = [d.start for d in self.dates]
        self._touchable = sorted([(m.start, m.end) for m in self.services]
                                 + [(i.start, i.end) for i in self.interventions])
        self._touchable_starts = [t[0] for t in self._touchable]
        self._longest = max((e - s for s, e in self._touchable), default=0)
        self._ordered_interventions = tuple(sorted(self.interventions, key=lambda i: (i.start, i.end)))
        self._intervention_starts = [i.start for i in self._ordered_interventions]
        self.memo: dict = {}  # pure per-text results: (kind, start, end) -> value

    def services_in(self, start: int, end: int) -> list[Mention]:
        return _inside(self.services, self._service_starts, start, end)

    def interventions_in(self, start: int, end: int) -> list[Intervention]:
        return _inside(self._ordered_interventions, self._intervention_starts, start, end)

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


def _masked_map(an: Analysis, start: int, end: int) -> tuple[str, list[int]]:
    """``_masked`` and, for each of its characters and one past its end, the text offset it
    stands for. A match ending inside a service token maps to that mention's end."""
    key = ('masked', start, end)
    if key not in an.memo:
        token = f' {cues.SERVICE_TOKEN} '
        out, where, pos = [], [], start
        for m in an.services_in(start, end):
            out.append(an.text[pos:m.start])
            where.extend(range(pos, m.start))
            out.append(token)
            where.extend([m.start] * (len(token) - 1) + [m.end])
            pos = m.end
        out.append(an.text[pos:end])
        where.extend(range(pos, end))
        where.append(end)
        an.memo[key] = (''.join(out), where)
    return an.memo[key]


# A cues._pre pattern ends where its mention starts and spans a trigger of at most six words and at most five filler
# words; PRE_WORDS is twice that. Only that many masked words before a mention can hold its match, so searching from
# there finds exactly the matches a search from the window's start finds, and every target whose window reaches back
# that far shares one reading of the member. A coordinated list made each of its N targets re-read all N members over
# its whole window ('EUS, ' x 400 took 21 s).
PRE_WORDS = 24
_PRE_TOKEN = re.compile(r'[^\s,]+', re.A)  # a word as cues._pre separates them


def _pre_start(an: Analysis, cs: int, ms: int) -> int:
    """Where a cues._pre search before the member at ``ms`` begins: its PRE_WORDS-th word back (a service name is
    one word, as _masked writes it), or ``cs`` when the window starts after that."""
    key = ('pre-start', ms)
    if key not in an.memo:
        starts = an.memo.get(('word-starts',))
        if starts is None:
            starts = an.memo[('word-starts',)] = [m.start() for m in _PRE_TOKEN.finditer(an.text)]
        pos = ms
        for _ in range(PRE_WORDS):
            index = bisect.bisect_left(starts, pos) - 1
            if index < 0:
                pos = 0
                break
            pos = _outside_a_service(an, starts[index])
        an.memo[key] = pos
    return max(cs, an.memo[key])


def _outside_a_service(an: Analysis, pos: int) -> int:
    """``pos``, or the start of the service name it lies inside: a cut there would split a name _masked replaces."""
    while True:
        index = bisect.bisect_right(an._service_starts, pos) - 1
        while index >= 0 and an.services[index].start >= pos - an._longest:
            mention = an.services[index]
            if mention.start < pos < mention.end:
                pos = mention.start
                break
            index -= 1
        else:
            return pos


def _masked_post(an: Analysis, me: int, ce: int) -> str:
    """``_masked(an, me, ce)``: the text after a member is read whole, since a post pattern may end at the window's end
    ('was not' followed by nothing). Not memoised: round 4 (pipeline:0) measured a memo of these tails at 1.5 GiB on a
    20 KB paste, for no time saved."""
    return _masked(an, me, ce)


def _pre_negations(an: Analysis, start: int, ms: int) -> list[tuple[str, str, int]]:
    """(label, matched words, text offset) of each NEGATED_PRE trigger before the member at ``ms``, read from
    ``start`` (_pre_start)."""
    key = ('pre-negations', start, ms)
    if key not in an.memo:
        pre, found = _masked(an, start, ms), []
        for name, pattern in cues.NEGATED_PRE:
            m = pattern.search(pre)
            if m:
                found.append((name, m.group(0), _masked_map(an, start, ms)[1][m.start()]))
        an.memo[key] = found
    return an.memo[key]


def _pre_cues(an: Analysis, start: int, ms: int) -> tuple[list, Optional[tuple]]:
    """The historical, planned, incomplete and uncertain pre-triggers of the member at ``ms``, read from ``start``
    (_pre_start), and its 'had' history trigger (which a clause saying today overrides)."""
    key = ('pre-cues', start, ms)
    if key not in an.memo:
        pre, found = _masked(an, start, ms), []
        for status, entries in (('historical', cues.HISTORICAL_PRE), ('planned', cues.PLANNED_PRE),
                                ('incomplete', cues.INCOMPLETE_PRE), ('uncertain', cues.UNCERTAIN_PRE)):
            for name, pattern in entries:
                m = pattern.search(pre)
                if m:
                    found.append((status, f'{status}: {m.group(0).strip()}', False,
                                  'pending' in m.group(0).lower()))
        m = cues.HAD_PRE.search(pre)
        an.memo[key] = (found, ('historical', f'historical: {m.group(0).strip()}', False, False) if m else None)
    return an.memo[key]


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
    service and every intervention named inside the target (each is read with its
    own anchored cues, so "No biopsies were taken." reads the "No" before "biopsies")."""
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
    inner += sorted({(iv.start, iv.end) for iv in an.interventions_in(*target)} - set(inner))
    return [(g[0][0], g[-1][1]) for g in groups], index, groups[index] + inner


def _attached(spans: list[tuple[int, int]], index: int, start: int, end: int, reach: Optional[int] = None) -> bool:
    gaps = [_gap(start, end, gs, ge) for gs, ge in spans]
    return gaps[index] == min(gaps) and (reach is None or gaps[index] <= reach)


def _span_negations(an: Analysis, cs: int, ce: int) -> list[re.Match]:
    """NEGATED_SPAN matches ("no ... was <done>") in the window [cs, ce)."""
    key = ('span-negations', cs, ce)
    if key not in an.memo:
        an.memo[key] = list(cues.NEGATED_SPAN.finditer(an.text, cs, ce)) if _has_negation(an, cs, ce) else []
    return an.memo[key]


def _has_negation(an: Analysis, cs: int, ce: int) -> bool:
    key = ('has-negation', cs, ce)
    if key not in an.memo:
        an.memo[key] = bool(cues.DOUBT_TOKEN.search(an.text, cs, ce))
    return an.memo[key]


def _said(m: re.Match) -> str:
    """A post-pattern match as a cue's words, without the separator it starts with."""
    return m.group(0).strip().lstrip(',:;=-\u2013\u2014( ').strip()


def _member_negations(an: Analysis, cs: int, ce: int, ms: int, me: int, post: Optional[str] = None):
    """Anchored negations of the mention at [ms, me) in the window [cs, ce): a list of
    (label, about_past, text span), and the spans of pre-triggers that govern the word
    after the mention instead ("No flexible sigmoidoscopy complications"). The pre-triggers are
    read from _pre_start, which finds exactly what the whole window would."""
    key = ('negations', cs, ce, ms, me)
    if key not in an.memo:
        post = _masked(an, me, ce) if post is None else post
        found, governs_next = [], []
        for name, said, at in _pre_negations(an, _pre_start(an, cs, ms), ms):
            where = (at, ms)
            if cues.NEGATION_HEAD_AFTER.match(post):
                governs_next.append(where)
            else:
                past = name != cues.REFUSAL and bool(cues.NEGATION_ABOUT_PAST.search(said))
                found.append((f'negated: {said.strip()}', past, where))
        for _, pattern in cues.NEGATED_POST:
            m = pattern.search(post)
            if m:
                found.append((f'negated: {_said(m)}', False, (me, _masked_map(an, me, ce)[1][m.end()])))
        for m in _span_negations(an, cs, ce):
            # the mention starts inside "no ... was <done>" and ends by its verb ("No plastic stent was placed")
            if m.start('body') <= ms < m.end('body') and me <= m.end():
                found.append((f'negated: {m.group(0).strip()}', bool(cues.NEGATION_ABOUT_PAST.search(m.group(0))),
                              (m.start(), m.end())))
        an.memo[key] = (found, governs_next)
    return an.memo[key]


def _named_before(an: Analysis, pos: int, cs: int) -> bool:
    """A service or intervention name ends right before ``pos`` (only spaces and commas between):
    a "was not <done>" there is that mention's NEGATED_POST, not a memberless negation."""
    ends = [m.end for m in an.services_in(cs, pos)] + [iv.end for iv in an.interventions_in(cs, pos)]
    return any(not an.text[end:pos].strip(' \t,') for end in ends)


def _memberless_negations(an: Analysis, cs: int, ce: int) -> list[tuple[str, tuple[int, int]]]:
    """Explicit negations in the window [cs, ce) that name no service or intervention ("No
    polypectomy was performed", "The stricture was not dilated"): (label, span). They deny the
    act their own words describe."""
    key = ('memberless', cs, ce)
    if key not in an.memo:
        found = []
        if _has_negation(an, cs, ce):
            for m in _span_negations(an, cs, ce):
                if not an.services_in(m.start('body'), m.end('body')) and not an.interventions_in(m.start('body'), m.end()):
                    found.append((f'negated: {m.group(0).strip()}', (m.start(), m.end())))
            for m in cues.NOT_DONE_CLAUSE.finditer(an.text, cs, ce):
                if not _named_before(an, m.start(), cs):
                    found.append((f'negated: {m.group(0).strip()}', (m.start(), m.end())))
        an.memo[key] = found
    return an.memo[key]


def _anchored_explains(an: Analysis, cs: int, ce: int, token: tuple[int, int], served: Optional[int] = None) -> bool:
    """Whether an anchored negation of a service or intervention named next to ``token`` (the
    two names after it, the one before it) covers it - "no colonoscopy", "EUS was not",
    "Neither EUS nor ERCP" - or is a pre-trigger that governs the word after its mention.
    ``served``: the end of the service read (named before ``token``). For it, an intervention of
    its own description ("EGD to D2 with biopsy") does not explain a denial set off after it by a
    separator (", declined by the patient", ", not performed", " (declined)"): that denial has no
    subject of its own and may deny the whole service, so it stays unresolved (_described_with)."""
    after = sorted({(m.start, m.end) for m in an.services_in(token[1], ce)}
                   | {(iv.start, iv.end) for iv in an.interventions_in(token[1], ce)})[:2]
    before = sorted({(m.start, m.end) for m in an.services_in(cs, token[0])}
                    | {(iv.start, iv.end) for iv in an.interventions_in(cs, token[0])})[-1:]
    for ms, me in after + before:
        found, governs_next = _member_negations(an, cs, ce, ms, me)
        spans = [where for _, _, where in found] + governs_next
        if served is not None and (ms, me) in before and _described_with(an, served, ms, me):
            spans = [w for w in spans if not (w[0] == me and _SEPARATOR_LED.match(an.text, me, ce))]
        if any(s <= token[0] and token[1] <= e for s, e in spans):
            return True
    return False


# A denial set off from the name before it ("biopsy, declined by the patient", "biopsy (declined)", "biopsy -
# not performed"), not one that has the name as its subject ("biopsies not taken", "biopsy declined").
_SEPARATOR_LED = re.compile(r'\s*[,:;=|(\u2013\u2014-]', re.A)
_DESCRIPTION_BREAK = re.compile(r'[,;:(|\u2013\u2014]|\s-\s', re.A)


def _described_with(an: Analysis, served: int, ms: int, me: int) -> bool:
    """Whether [ms, me) is an intervention named in the description of the service that ends at ``served``: after
    it, with no separator between them ("Flexible sigmoidoscopy to 30 cm with biopsy", "Colonoscopy with cold snare
    polypectomy"). After a separator it starts an item of its own ("Colonoscopy with polypectomy, biopsies ...")."""
    if served > ms or not any(iv.start == ms and iv.end == me for iv in an.interventions_in(ms, me)):
        return False
    return not _DESCRIPTION_BREAK.search(an.text, served, ms)


def _landmark_negations_near(an: Analysis, clause: tuple[int, int], token: tuple[int, int]) -> list[tuple[int, int]]:
    """Spans of "could not be advanced to the", "was not reached" and the like next to ``token``,
    each tied to the landmark it denies: the extent logic reads them, so they explain their
    negation words."""
    cs, ce = clause
    found = []
    for _, _, pattern in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS:
        for m in pattern.finditer(an.text, token[1], min(ce, token[1] + 150)):
            before = cues.NOT_REACHED_BEFORE.search(an.text, max(cs, m.start() - 150), m.start())
            if before:
                found.append((before.start(), m.start()))
        for m in pattern.finditer(an.text, max(cs, token[0] - 150), token[0]):
            after = cues.NOT_REACHED_AFTER.match(an.text, m.end(), ce)
            if after:
                found.append((m.end(), after.end()))
    return found


def _token_explanations(an: Analysis, clause: tuple[int, int], token: tuple[int, int]):
    """What accounts for the negation word at ``token`` in its clause: spans that explain it for
    any target (a clause cue, a denied landmark, a complication or qualifier exception), and
    spans that explain it only for a target they lie outside (a denied finding, "no polyps were
    seen", or a different act denied, "no sedation was given")."""
    key = ('token-explanations', token[0])
    if key not in an.memo:
        cs, ce = clause
        explains = [(c.start, c.end) for c in an.cues_in(max(cs, token[0] - 200), min(ce, token[1] + 200))]
        explains += _landmark_negations_near(an, clause, token)
        masked, where = _masked_map(an, max(cs, token[0] - 40), min(ce, token[1] + 400))
        for pattern in (cues.COMPLICATION_NEGATION, cues.QUALIFIER_NEGATION, _OPTION_LABEL):
            explains += [(where[m.start()], where[m.end()]) for m in pattern.finditer(masked)]
        # A denied finding or a denied other act explains the word only outside the passage being
        # read: "No polyps were seen" quoted as the evidence for a polypectomy is not "performed".
        outside_only = [(where[m.start()], where[m.end()]) for pattern in (*cues.FINDING_NEGATION, cues.OTHER_ACT_NEGATION)
                        for m in pattern.finditer(masked)]
        an.memo[key] = (explains, outside_only)
    return an.memo[key]


def _covered(token: tuple[int, int], spans) -> bool:
    return any(s <= token[0] and token[1] <= e for s, e in spans)


def _unexplained(an: Analysis, clause: tuple[int, int], cs: int, ce: int, token: tuple[int, int],
                 ts: int, te: int) -> bool:
    """Whether nothing accounts for the negation word at ``token`` when [ts, te) is read: no
    clause cue, exception or denied landmark; no denied act or memberless negation outside the
    target; no anchored negation of a service or intervention named next to it."""
    explains, outside_only = _token_explanations(an, clause, token)
    if _covered(token, explains):
        return False
    target = (ts, max(te, ts + 1))
    # Inside a passage that names a service or an intervention, or states an act ("The colonoscope was
    # advanced to the cecum and no polyps were seen"), a denied finding or other act is incidental to it
    # ("Biopsies were taken where no ulcers were seen"); inside a passage that does neither, it is what
    # the passage says ("No polyps were seen."). The act's cue must lie outside the denial itself. A passage
    # that only states an act keeps a denial that an act it would have needed follows ("... and no polyps were
    # found to remove"): it says that act was not needed, so the negation stays unresolved (_NEEDED_ACT_AFTER).
    named = bool(an.services_in(*target) or an.interventions_in(*target))
    stated = not named and any(c.status == 'performed' and not any(_overlaps(c.start, c.end, *w) for w in outside_only)
                               for c in an.cues_in(*target))
    outside = [w for w in outside_only
               if named or (stated and not _NEEDED_ACT_AFTER.match(an.text, w[1], ce)) or not _overlaps(*w, *target)]
    outside += [w for _, w in _memberless_negations(an, cs, ce) if not _overlaps(*w, *target)]
    # the service the target reads, when one is named in it before the negation word (see _anchored_explains)
    served = [m.end for m in an.services_in(max(cs, ts), min(token[0], target[1]))]
    return not _covered(token, outside) and not _anchored_explains(an, cs, ce, token, served[-1] if served else None)


# An act a denied finding would have needed, within five words after the denial: "no polyps were found to remove",
# "there were no polyps to remove", "no polyps were identified for removal", "no polyps were seen that required
# removal", "no lesions were seen for endoscopic resection". Only acts a code is billed for (removal, sampling,
# treatment ...), never the procedure's own steps ("on retroflexion", "despite an adequate preparation").
_NEEDED_ACT_AFTER = re.compile(r"\s+(?:[\w/'-]+\s+){0,4}?(?:polypectom\w*|biops\w*|snar\w*|forceps|remov\w*|resect\w*|"
                               r'excis\w*|sampl\w*|dilat\w*|inject\w*|clip\w*|tattoo\w*|cauter\w*|coagulat\w*|ablat\w*|'
                               r'ligat\w*|band(?:s|ed|ing)?|treat\w*|therap\w*|retriev\w*|extract\w*|aspirat\w*|stent\w*|'
                               r'brush\w*|EMR|APC|FNA|FNB|hemostasis|interventions?|sphincterotom\w*|papillotom\w*)\b',
                               re.A | re.I)


DOUBT_PREFIX = 'uncertain: unresolved negation'
SILENT_SECTION_PREFIX = 'uncertain: section silent:'


def _doubt(an: Analysis, ts: int, te: int) -> Optional[str]:
    """A cue when a negation word that attaches to the target (like a clause cue: to the
    nearest mention group of its clause) is accounted for by nothing - no anchored negation of
    a named mention, no clause cue, no memberless negation of another act, no complication,
    finding or qualifier exception. Fail-closed: such a word withholds "performed"."""
    key = ('doubt', ts, te)
    if key not in an.memo:
        an.memo[key] = None
        for clause in an.lay.clauses_for(ts, te):
            cs, ce = an.lay.window(clause, ts, te, CLAUSE_REACH)
            if not _has_negation(an, cs, ce):
                continue
            spans, index, _ = _groups(an, cs, ce, ts, te)
            token = next((t for t in cues.DOUBT_TOKEN.finditer(an.text, cs, ce)
                          if _attached(spans, index, t.start(), t.end())
                          and _unexplained(an, clause, cs, ce, (t.start(), t.end()), ts, te)), None)
            if token:
                an.memo[key] = f"{DOUBT_PREFIX} '{token.group(0)}' in its clause"
                break
    return an.memo[key]


# What may follow a service name for its section alone to read it as performed. The words of
# the name's clause after it are read in order, within CONTINUATION_REACH characters, and none of
# them may move the service to another time, place or state:
# - the first word may begin a description of the procedure or of what it found ("with cold
#   snare polypectomy", "to the cecum", "on 2026-10-21", "at Harborview", ", average-risk
#   screening", "(EGD)"), but must not predicate something of the service: an auxiliary, a
#   linking or status word (_PREDICATES), an unlisted participle ("requested", "omitted"), a
#   copula that does not describe ("was felt to be"), or a "to" that opens neither an extent nor,
#   under a procedure heading, the procedure's purpose ("to evaluate anemia", _TO_PURPOSE);
# - every later word is read for a qualifier (_QUALIFIERS: "at a later date", "once", "pending
#   clearance", "TBD", "last year", "at an outside hospital", "elsewhere", "previously", "to be
#   determined", "(to confirm with the patient)", ": unknown") and for a status participle that
#   closes the clause ("... requested by the referring physician").
# Service names, interventions, landmarks, numbers, brackets ("(EGD)") and the joiners ' | '
# (a table row's cells), '/', '+' and '&' are passed over, and so is any other word: the
# vocabulary of a description is open, its qualifiers are not. A qualifier leaves the section
# silent and the reading a doubt: the service is held for clarification, never excluded.
CONTINUATION_REACH = 240  # how far after a name its clause is read (bounds the work per span)
_NEXT_WORD = re.compile(r'[A-Za-z][\w/\'-]*|\d', re.A)
_CONTINUES = frozenset((
    'with', 'w/', 'and', 'or', 'plus', 'including', 'includes', 'to', 'into', 'through', 'thru', 'of', 'for', 'via',
    'using', 'under', 'in', 'from', 'by', 'then', 'followed', 'per', 'after', 'today', 'this',
    'procedure', 'procedures', 'report', 'note', 'finding', 'findings', 'technique', 'description', 'details',
    'summary', 'impression', 'images', 'photos', 'photographs', 'specimen', 'specimens', 'pathology', 'prep',
    'preparation', 'quality', 'withdrawal', 'insertion', 'time', 'extent', 'indication', 'indications', 'scope',
    'instrument', 'equipment', 'result', 'results', 'showed', 'shows', 'revealed', 'reveals', 'demonstrated',
    'demonstrates', 'disclosed', 'confirmed', 'found', 'identified', 'documented', 'noted', 'performed', 'completed',
    'complete', 'done', 'undertaken', 'accomplished', 'achieved', 'successful', 'successfully', 'uneventful',
    'normal', 'abnormal', 'unremarkable', 'negative', 'positive', 'notable', 'significant', 'remarkable',
    'diagnostic', 'screening', 'surveillance', 'therapeutic', 'routine', 'repeat', 'full', 'total', 'bidirectional',
    'upper', 'lower', 'flexible', 'standard', 'elective', 'urgent', 'emergent', 'index', 'guided', 'assisted',
    'related', 'associated', 'difficult', 'challenging', 'prolonged', 'technically', 'otherwise', 'entirely',
    'essentially', 'grossly', 'also', 'additionally', 'again', 'within',
    # determiners and counts that open a description of what was found
    'a', 'an', 'the', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'single',
    'multiple', 'several', 'few', 'numerous', 'many', 'small', 'large', 'diminutive', 'tiny', 'medium', 'mild',
    'moderate', 'severe', 'patchy', 'diffuse', 'focal', 'minimal'))
# Straight after the name: words that predicate something of the service.
_PREDICATES = frozenset((
    'has', 'have', 'had', 'will', 'would', 'should', 'could', 'can', 'may', 'might', 'must', 'did', 'does', 'do',
    'shall', 'which', 'that', 'who', 'however', 'though', 'although', 'but', 'yet', 'instead', 'unfortunately',
    'ultimately', 'eventually', 'initially', 'originally', 'previously', 'tbd', 'tba', 'pending', 'unnecessary',
    'unavailable', 'impossible', 'inadvisable', 'inappropriate', 'later', 'next', 'tomorrow', 'soon', 'hold',
    'unable', 'unsafe', 'unwise', 'optional', 'possible', 'needed', 'required', 'indicated', 'due'))
# Anywhere after the name in its clause: words that move the service to another time, place or state.
_QUALIFIERS = frozenset((
    'later', 'tomorrow', 'soon', 'someday', 'sometime', 'tbd', 'tba', 'pending', 'awaiting', 'once', 'when',
    'whenever', 'until', 'unless', 'if', 'elsewhere', 'previously', 'earlier', 'formerly', 'maybe',
    'perhaps', 'tentative', 'tentatively', 'hypothetical', 'hypothetically', 'unfortunately', 'unable', 'unsafe',
    'unwise', 'unnecessary', 'unavailable', 'impossible', 'inadvisable', 'inappropriate', 'optional'))
# A condition or a time these open is a description when it is told in the past ("biopsies taken when abnormal
# mucosa was seen"), a qualifier otherwise ("once the INR is corrected").
_WHEN_WORDS = frozenset(('once', 'when', 'whenever', 'until'))
_TOLD_IN_THE_PAST = re.compile(r'(?:\s+[\w/-]+){0,6}?\s+(?:was|were|had|did)\b', re.A | re.I)
# These end what the line says of the service: after a reporting verb the words report what it found
# ("Colonoscopy showed a polyp, for EMR at a later date"), and after a relative pronoun (not as the first
# word, where it predicates: "Colonoscopy, which ...") they speak of another thing or act.
_REPORTING = frozenset(('showed', 'shows', 'revealed', 'reveals', 'demonstrated', 'demonstrates', 'disclosed',
                        'found', 'noted', 'identified', 'documented'))
_RELATIVES = frozenset(('that', 'which', 'who', 'whom', 'whose', 'where'))
# A state word that qualifies the service only where it closes its clause ("Colonoscopy: unknown."), not
# where it qualifies a noun ("a lesion of uncertain significance").
_PREDICATIVE_STATES = frozenset(('unknown', 'unclear', 'uncertain', 'undecided', 'undetermined', 'unconfirmed'))
# Participles that describe a performed service or what it found, never its status.
_DESCRIPTIVE_ED = frozenset((
    'performed', 'completed', 'guided', 'assisted', 'related', 'associated', 'pedunculated', 'serrated', 'ulcerated',
    'elevated', 'depressed', 'scattered', 'inflamed', 'dilated', 'nodulated', 'raised', 'excavated', 'flattened',
    'lobulated', 'fixed', 'mixed', 'localized', 'retained', 'visualized', 'examined', 'intubated', 'reached',
    'identified', 'noted', 'documented', 'biopsied', 'removed', 'resected', 'retrieved', 'clipped', 'tattooed',
    'treated', 'banded', 'injected', 'sampled', 'obtained', 'advanced', 'inserted', 'introduced', 'passed',
    'photographed', 'photodocumented', 'achieved', 'confirmed', 'demonstrated', 'revealed', 'cauterized',
    'coagulated', 'ligated', 'placed', 'deployed', 'extracted', 'cleared', 'swept', 'cannulated', 'stented',
    'aspirated', 'lifted', 'closed', 'marked', 'washed', 'irrigated', 'suctioned', 'imaged', 'measured', 'sized',
    'sent', 'submitted', 'labeled', 'labelled', 'tolerated', 'uncomplicated', 'complicated', 'limited', 'extended'))
_ON_HOLD = re.compile(r'on\s+hold\b|to\s+follow\b|at\s+a\s+later\b', re.A | re.I)
# After "to", an extent goes on describing the service ("to the cecum", "to 40 cm") ...
_TO_EXTENT = frozenset(('the', 'a', 'an', 'its', 'approximately', 'approx', 'about', 'around', 'roughly', 'nearly',
                        'near', 'level', 'mid', 'distal', 'proximal', 'terminal', 'second', 'third', 'fourth', 'beyond',
                        'within'))
# ... and, under a procedure heading or later in the line, so does the purpose of the procedure or of
# an act it describes ("EGD to evaluate dysphagia", "ERCP to remove common bile duct stones", "with
# biopsies to evaluate for celiac disease"). Only these verbs (fail-closed): an unlisted one ("to
# come", "to be scheduled", "to confirm with the patient", "to check") stays a future or a status.
_TO_PURPOSE = frozenset((
    'evaluate', 'reevaluate', 're-evaluate', 'assess', 'reassess', 'investigate', 'exclude', 'rule', 'screen',
    'survey', 'stage', 'restage', 'characterize', 'characterise', 'examine', 'inspect', 'visualize', 'visualise',
    'localize', 'localise', 'identify', 'define', 'delineate', 'diagnose', 'determine', 'sample', 'biopsy', 'remove',
    'resect', 'excise', 'treat', 'dilate', 'retrieve', 'extract', 'drain', 'decompress', 'mark', 'tattoo', 'ablate',
    'control', 'obtain', 'clear', 'relieve', 'palliate', 'place', 'insert', 'deploy', 'replace', 'exchange',
    'measure', 'map', 'monitor', 'document',
    # the standard abbreviations of "evaluate" and "rule out"
    'eval', 'r/o'))
# Manner adverbs that may stand between "to" and a listed purpose verb ("to further evaluate", "to better
# evaluate", "to more fully assess"): verified forms only, at most two of them. Any other word there ("to possibly
# evaluate", "to further discuss") keeps the "to" a stop.
_TO_MANNER = frozenset(('further', 'better', 'fully', 'again', 'more', 'thoroughly', 'completely'))
# A "to" that ends one of these relations is part of it, not a purpose or a future ("due to anemia",
# "secondary to bleeding", "prior to surgery", "distal to the lesion").
_TO_RELATIONS = frozenset(('due', 'owing', 'secondary', 'related', 'according', 'addition', 'prior', 'subsequent',
                           'next', 'close', 'adjacent', 'similar', 'compared', 'proximal', 'distal'))
_COPULA = frozenset(('was', 'were', 'is', 'are'))
_AFTER_COPULA = frozenset(('normal', 'unremarkable', 'negative', 'positive', 'complete', 'completed', 'performed',
                           'done', 'uneventful', 'successful', 'successfully', 'notable', 'significant', 'remarkable',
                           'otherwise', 'technically', 'difficult', 'challenging', 'prolonged', 'then', 'also',
                           'carried', 'undertaken', 'accomplished', 'without', 'essentially', 'grossly', 'entirely',
                           'within', 'subsequently', 'uneventfully', 'easily', 'routinely'))
_DETERMINERS = frozenset(('the', 'a', 'an', 'this', 'that', 'these', 'those', 'its', 'her', 'his', 'their', 'our'))
# Words that report a result, so a "pending" after them is the result's ("pathology pending").
_RESULT_WORDS = frozenset(('pathology', 'path', 'histology', 'cytology', 'result', 'results', 'report', 'reports',
                           'labs', 'culture', 'cultures'))
_TIME_UNIT = re.compile(r'\s+(?:\d+\s+)?(?:weeks?|months?|years?|visits?|time|spring|summer|fall|autumn|winter)\b',
                        re.A | re.I)
_OUTSIDE_PLACE = re.compile(r'\s+(?:hospitals?|facilit(?:y|ies)|institutions?|cent(?:er|re)s?|clinics?|practices?|'
                            r'providers?|offices?|gastroenterologists?|physicians?|endoscopists?|doctors?)\b',
                            re.A | re.I)
# A participle or a state word is predicative when its clause ends after it, or when it opens an agent,
# a condition or a reason ("... requested by the referring physician"); before a noun it describes one.
_PREDICATIVE_AFTER = re.compile(r'[\s,]*(?:$|[.;:!?)\]]|(?:by|until|pending|due|because|per)\b)', re.A | re.I)
_VERB_BEFORE = re.compile(r'\b(?:was|were|is|are|has|have|had|did|does|will)\b', re.A | re.I)
_SEPARATOR = re.compile(r'[\s,:\u2013\u2014-]*', re.A)
_LANDMARK_AT = re.compile('|'.join(f'(?:{p.pattern})' for _, _, p in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS),
                          re.A | re.I)


def _group_end(an: Analysis, m: Mention, limit: int) -> int:
    """The end of the coordinated mention group that starts with ``m`` ("EGD and colonoscopy")."""
    end = m.end
    index = bisect.bisect_left(an._service_starts, m.end)
    for other in an.services[index:]:
        if other.end > limit or not _CONNECTOR.fullmatch(an.text[end:other.start]):
            break
        end = other.end
    return end


def _named_at(an: Analysis, pos: int, limit: int) -> Optional[int]:
    """The end of a service name, an intervention or a landmark that starts at ``pos``."""
    near = min(limit, pos + 120)  # a name that starts here is short; never list the whole sentence
    for m in an.services_in(pos, near):
        if m.start == pos:
            return m.end
    for iv in an.interventions_in(pos, near):
        if iv.start == pos:
            return iv.end
    landmark = _LANDMARK_AT.match(an.text, pos, limit)
    return landmark.end() if landmark else None


def _to_stops(an: Analysis, word: re.Match, limit: int, purpose: bool) -> Optional[str]:
    """None when this "to" opens an extent (or, with ``purpose``, a listed purpose); else what it opens."""
    text = an.text
    at = _SEPARATOR.match(text, word.end(), limit).end()
    follow = _NEXT_WORD.match(text, at, limit)
    if follow is None:
        return 'to'
    following = follow.group(0).lower()
    if (following[0].isdigit() or following in _TO_EXTENT or _LANDMARK_AT.match(text, at, limit)
            or any(m.start == at for m in an.services_in(at, min(limit, at + 120)))):
        return None
    if purpose:
        verb = follow
        for _ in range(2):  # at most two manner adverbs before the purpose verb
            if verb is None or verb.group(0).lower() not in _TO_MANNER:
                break
            verb = _NEXT_WORD.match(text, _SEPARATOR.match(text, verb.end(), limit).end(), limit)
        if verb is not None and verb.group(0).lower() in _TO_PURPOSE:
            return None
    return f'to {follow.group(0)}'


def _stop_word(an: Analysis, word: re.Match, limit: int, first: bool, procedure: bool,
               previous: str) -> Optional[str]:
    """The words that keep the section from speaking for the service, when ``word`` opens them."""
    text, said = an.text, word.group(0)
    lowered = said.lower()
    hold = _ON_HOLD.match(text, word.start(), limit)
    if hold:
        return hold.group(0)
    if lowered == 'to':
        return None if previous in _TO_RELATIONS else _to_stops(an, word, limit, purpose=procedure or not first)
    if lowered[0].isdigit():
        return None
    if lowered == 'due' and re.match(r'\s+to\b', text[word.end():limit]):
        return None  # "due to iron deficiency anemia": a reason
    if first and lowered in _COPULA:
        at = _SEPARATOR.match(text, word.end(), limit).end()
        after = _NEXT_WORD.match(text, at, limit)
        following = after.group(0).lower() if after else ''
        if cues.DOUBT_TOKEN.match(text, at, limit) or following in _AFTER_COPULA or following in _DESCRIPTIVE_ED:
            return None
        return said
    if lowered == 'last':
        unit = _TIME_UNIT.match(text, word.end(), limit)
        if unit is None or previous in _DETERMINERS \
                or cues.SYMPTOM_TIME_BEFORE.search(text, max(0, word.start() - 40), word.start()) \
                or _trails_another_thing(an, word.start(), 0):
            return None  # "the last 5 cm", "bleeding since last month", "a positive FIT last month": not the service's
        return said + unit.group(0)
    if lowered == 'outside':
        place = _OUTSIDE_PLACE.match(text, word.end(), limit)
        return said + place.group(0) if place and not _trails_another_thing(an, word.start(), 0) else None
    if lowered == 'elsewhere' and _trails_another_thing(an, word.start(), 0):
        return None  # "a CT colonography performed elsewhere": the test's place (routing:0)
    if previous == 'as' or (previous in ('previously', 'originally', 'initially', 'already')
                            and cues.AS_BOOKED_BEFORE.search(text, max(0, word.start() - 30), word.start())):
        return None  # "as scheduled", "as previously planned": the booking it kept
    if lowered in ('previously', 'earlier') and previous in _DETERMINERS:
        return None  # "the previously tattooed site": it describes a place
    if lowered in ('pending', 'awaiting') and previous in _RESULT_WORDS:
        return None  # "pathology pending": the result's, not the service's
    if lowered in _WHEN_WORDS and _TOLD_IN_THE_PAST.match(text, word.end(), limit):
        return None
    if lowered in _QUALIFIERS:
        return said
    if lowered in _PREDICATIVE_STATES and _PREDICATIVE_AFTER.match(text, word.end(), limit):
        return said
    if lowered in _CONTINUES:
        return None
    participle = lowered.endswith('ed') and lowered not in _DESCRIPTIVE_ED
    if first:
        return said if lowered in _PREDICATES or participle else None
    if participle and _PREDICATIVE_AFTER.match(text, word.end(), limit):
        return said
    return None


def _continuation(an: Analysis, pos: int, limit: int, clause_end: int, procedure: bool) -> Optional[str]:
    """The words after ``pos`` (up to ``limit``, the end of the name's sentence) that keep a section
    from speaking for the service named before ``pos``, or None when they describe the procedure or
    what it found (see above). The first word is read even where a clause word opens it
    ("Colonoscopy, however, was not."); later words only up to ``clause_end``, the end of the name's
    own clause. ``procedure``: under a procedure heading, where a "to" may open the procedure's
    purpose."""
    text = an.text
    limit = min(limit, pos + CONTINUATION_REACH)
    first, previous = True, ''
    while True:
        pos = _SEPARATOR.match(text, pos, limit).end()
        if pos >= limit or text[pos] in '.;!?\n' or (not first and pos >= clause_end):
            return None
        named = _named_at(an, pos, limit)
        if named is not None:
            pos, first, previous = named, False, ''
            continue
        token = cues.DOUBT_TOKEN.match(text, pos, limit)
        if token:  # a negation word: the unresolved-negation check reads it, with its exceptions
            pos, first, previous = token.end(), False, ''
            continue
        word = _NEXT_WORD.match(text, pos, limit)
        if word is None:
            pos += 1  # other punctuation (' | ', '/', '+', '&', a bracket, a bullet, a box) carries no status
            continue
        lowered = word.group(0).lower()
        if lowered in _REPORTING or (not first and lowered in _RELATIVES):
            return None
        stop = _stop_word(an, word, limit, first, procedure, previous)
        if stop is not None:
            return stop
        pos, first, previous = word.end(), False, word.group(0).lower()


# The subject of a sentence that speaks of the service named just before it.
_REFERRING_SUBJECT = re.compile(r'(?:it|this|that|the\s+(?:procedure|exam|examination|study|endoscopy|test|case))\b',
                                re.A | re.I)


def _denying_word(an: Analysis, start: int, end: int, only: Optional[re.Pattern] = None) -> Optional[re.Match]:
    """A negation word in [start, end) that nothing but a memberless negation accounts for:
    no clause cue, no complication, finding, qualifier or other-act exception, no anchored
    negation of a service or intervention named there. Read for the service named before
    this text, a memberless "was not performed" denies it. ``only``: consider only the
    negation words it matches whole."""
    for token in cues.DOUBT_TOKEN.finditer(an.text, start, end):
        if only is not None and not only.fullmatch(token.group(0)):
            continue
        span = (token.start(), token.end())
        clause = an.lay.clauses_for(*span)[0]
        explains, outside_only = _token_explanations(an, clause, span)
        if not _covered(span, explains + outside_only) and not _anchored_explains(an, *clause, span):
            return token
    return None


# A sentence adverb or a conjunction that may open the text speaking of the service named before it:
# "However, it was not performed.", "Unfortunately, the patient declined after consent."
_OPENER = re.compile(r'(?:(?:however|unfortunately|ultimately|eventually|subsequently|regrettably|finally|but|instead)'
                     r'\b[\s,]*)+', re.A | re.I)
# A status line: "Status: Cancelled.", "Procedure status: Not performed - the patient had eaten breakfast."
_STATUS_KEY = re.compile(r'(?:(?:procedure|case|exam|examination|study|service|endoscopy)[ \t]+)?status[ \t]*'
                         r'[:=\u2013\u2014-][ \t]*', re.A | re.I)
_STATUS_DONE = re.compile(r'(?:performed|completed?|done|successful(?:ly)?|finished|accomplished)\b', re.A | re.I)
# A status value that holds the service ("Status: Pending.", "Status: TBD"); a negation or a cancelling,
# deferring or doubting cue is read as on a bare line.
_STATUS_HOLD = re.compile(r'(?:pending|scheduled|tbd|tba|requested|ordered|unknown|unclear|incomplete|planned|'
                          r'awaiting|deferred|postponed|on\s+hold)\b', re.A | re.I)
# The negation words that, unexplained, deny an act in a short line after any service line ("Patient
# declined.", "Not performed."); "no" and "none" there deny a thing ("No complications.") and never do.
_ACT_DENIAL = re.compile(r"\b(?:not|never|cannot|unable|declined|declines|refused|refuses)\b|n't\b", re.A | re.I)
DENIAL_CLAUSES = 3  # later clauses of the service's own sentence read for a denial (bounds the work per span)


def _bare_denial(an: Analysis, start: int, end: int) -> bool:
    """[start, end), after a bare service line, denies it: it opens with a negation nothing explains,
    or is a short line with such a negation or refusal ("Patient declined.", "Pt refused."; "declined
    sedation" is explained), or a short cancelling, deferring, doubting or historical status line."""
    first = cues.DOUBT_TOKEN.match(an.text, start, end)
    if first and _denying_word(an, first.start(), first.end()):
        return True
    words = len(an.text[start:end].split())
    if words <= 6 and _denying_word(an, start, end):
        return True
    return words <= 5 and any(c.status in ('cancelled', 'planned', 'uncertain', 'historical')
                              for c in an.cues_in(start, end))


def _unchecked_option(an: Analysis, start: int, end: int) -> bool:
    """Whether the line [start, end) is an option its own unchecked box leaves unselected ("Procedure cancelled | ☐",
    "☐ Procedure aborted", "Procedure cancelled: not checked", "Procedure cancelled: [ ] Yes [x] No"). It states
    nothing, so it never denies or holds the service above it: routing:7's later denials must not read what
    contract:3 reads as no statement. Boxes that disagree or cannot be read still hold, through those denials.
    Only a line every denying option of which has its own unchecked box is one (routing:0): a checked, disagreeing or
    unread box on any denying option ("☐ Completed ☒ Cancelled") makes it a statement, whatever box comes first. A
    form-field line answered with a denial is one only when its label carries the denial ("Procedure cancelled: No",
    not "Procedure status: Not performed")."""
    if _box_state(an, start, end) == 'off':
        options = _box_denying_options(an, start, end)
        words = options + [m.span() for m in _BOX_DONE_OPTION.finditer(an.text, start, end)]
        return all(_box_option_state(an, start, end, option, words) == 'off' for option in options)
    if not _unchecked_state(an, start, end):
        return False
    fields = _form_fields(an)
    line = _within(fields.denying, fields.denying_starts, start, end)
    if line is None or not _BOX_DENIAL_ANSWER.search(line.line):
        return True  # a box state ("<label>: not checked"), or a printed line such a field names
    colon = an.text.find(':', line.start, line.end)
    return bool(_box_denying_options(an, line.start, colon if colon >= 0 else line.end))


# A form-field line's value that denies (not a box state): "<label>: No", "None", "Not done", "Not performed".
_BOX_DENIAL_ANSWER = re.compile(r':[ \t]*(?:no|none|not[ \t]+done|not[ \t]+performed)[ \t.]*$', re.A | re.I)


def _box_denying_options(an: Analysis, start: int, end: int) -> list[tuple[int, int]]:
    """The spans of [start, end) that would deny or hold the service if their option were selected: a cancelling,
    deferring, doubting, historical or incomplete cue, an act denial ("Not performed", "Declined") or a rescheduling."""
    found = [(c.start, c.end) for c in an.cues_in(start, end)
             if c.status in ('cancelled', 'planned', 'uncertain', 'historical', 'incomplete')]
    found += [m.span() for m in _ACT_DENIAL.finditer(an.text, start, end)]
    return found + [m.span() for m in _RESCHEDULED.finditer(an.text, start, end)]


# The words of a status option that says the service was done ("☐ Completed ☒ Cancelled", "Completed ☐ | Cancelled
# ☒"): with the denying options they are a status line's option words, which its boxes lead or trail.
_BOX_DONE_OPTION = re.compile(r'\b(?:complete[ds]?|performed|done|finished|accomplished|successful(?:ly)?)\b',
                              re.A | re.I)


def _box_option_state(an: Analysis, lo: int, hi: int, option: tuple[int, int], words: list) -> Optional[str]:
    """The state of the box(es) governing the status option at ``option``, one of the option words ``words`` of the
    status line [lo, hi) (its denying and its completion options): the boxes lead when the line's first box comes before
    its first option word ("☐ Completed ☒ Cancelled"), and trail when its last box comes after its last option word
    ("Completed ☐ | Cancelled ☒"; "Procedure cancelled: [ ] Yes [x] No" is a yes/no pair after its one option word).
    A line that can be read both ways is 'unknown'; None when the line has no box. The option words are what the
    boxes mark, so a status line is never read by where an item would be."""
    text = an.text
    _, boxes = _box_tokens(an, lo, hi)
    if not boxes:
        return None
    words = _merged(list(words) + [option])
    if boxes[0][0] < words[0][0]:
        before = [b for b in boxes if b[0] < option[1]]
        if not before:
            return None
        run = [before[-1]]
        for b in reversed(before[:-1]):
            if not _BOX_RUN_GAP.fullmatch(text, b[1], run[0][0]):
                break
            run.insert(0, b)
        return _run_state(run)
    if boxes[-1][0] > words[-1][0]:
        index = next(i for i, (s, e) in enumerate(words) if s <= option[0] < e)
        after = words[index + 1][0] if index + 1 < len(words) else hi
        group = [b for b in boxes if option[0] <= b[0] < after]
        return _group_state(text, group) if group else None
    return 'unknown'


def _cancels(an: Analysis, start: int, end: int) -> bool:
    """A cancellation cue in [start, end); an abort after the scope went in is not one."""
    return any(c.status == 'cancelled' and (c.name != 'aborted' or _abort_status(an, c)[0] != 'incomplete')
               for c in an.cues_in(start, end))


def _denies(an: Analysis, ns: int, ne: int, bare: bool) -> bool:
    """Whether [ns, ne) - the next sentence of the section, or a later clause of the service's own
    sentence, naming no service - denies or doubts the service named just before it. A sentence
    adverb ("However,", "Unfortunately,") may open it, and then:
    - a status line denies unless its value is one of completion ("Status: Cancelled.", "Procedure
      status: Not performed - ...", "Status: Pending."; not "Status: Completed.");
    - after a bare service line, the bare-line tests (_bare_denial);
    - after any service line, a short line with an unexplained act denial ("Patient declined.",
      "Not performed.") or a cancellation ("Cancelled."; not "Aborted at 30 cm."), never a denied
      thing ("No complications.") or a plan ("Repeat in 5 years.");
    - a sentence whose subject refers back to the service and cancels or denies it ("It was not
      performed.", "However, this was cancelled.")."""
    text = an.text
    if _unchecked_option(an, ns, ne):
        return False  # "Procedure cancelled | ☐": an option nobody selected states nothing (contract:3)
    at = _SEPARATOR.match(text, ns, ne).end()
    opener = _OPENER.match(text, at, ne)
    body = opener.end() if opener else at
    key = _STATUS_KEY.match(text, body, ne)
    if key:
        value = key.end()
        if _STATUS_DONE.match(text, value, ne):
            return False
        return (bool(_STATUS_HOLD.match(text, value, ne)) or _bare_denial(an, value, ne)
                or _value_calls_off(an, value, ne))
    if bare and _bare_denial(an, body, ne):
        return True
    if len(text[body:ne].split()) <= 6 and (_denies_an_act(an, body, ne) or _cancels(an, body, ne)
                                            or _reschedules(an, body, ne)):
        return True
    if not _REFERRING_SUBJECT.match(text, body, ne):
        return False
    return _cancels(an, ns, ne) or bool(_denying_word(an, ns, ne)) or _reschedules(an, ns, ne)


# A rescheduling of today's service: "Rescheduled.", "Rebooked for next week", "Moved to next week", "The procedure
# was rescheduled because ...". Not one that brought it to today ("rescheduled from last week"; _reschedules also
# skips any text that says today). Read only where a line or a status value is asked whether it denies a service.
_RESCHEDULED = re.compile(r'\bre-?(?:schedul|book)\w*\b(?!\s+(?:from|after)\b)'
                          r'|\b(?:moved|pushed|bumped)\s+(?:back\s+)?to\s+(?:next|tomorrow|later|a\s+later|another|'
                          r'a\s+(?:different|future|new))\b', re.A | re.I)
DENIAL_SENTENCES = 6  # later sentences read for a status line or a cancellation (bounds the work per span)


def _reschedules(an: Analysis, start: int, end: int) -> bool:
    """Whether [start, end) reschedules the service (_RESCHEDULED) and does not say today."""
    key = ('reschedules', start, end)
    if key not in an.memo:
        an.memo[key] = bool(_RESCHEDULED.search(an.text, start, end)) and not cues.TODAY.search(an.text, start, end)
    return an.memo[key]


def _value_calls_off(an: Analysis, value: int, end: int) -> bool:
    """Whether a status value opens with a cancellation (not an abort after the start), a rescheduling, or another
    status that is not completion, whatever reason follows it ("Status: Cancelled - the patient had eaten
    breakfast.", "Status: Rescheduled to next week because ..."): the bare-line tests read only short values."""
    at = _SEPARATOR.match(an.text, value, end).end()
    if _RESCHEDULED.match(an.text, at, end):
        return True
    return any(c.start == at and c.status in ('cancelled', 'planned', 'uncertain', 'historical')
               and (c.name != 'aborted' or _abort_status(an, c)[0] != 'incomplete')
               for c in an.cues_in(at, min(end, at + 60)))


def _status_line(an: Analysis, start: int, end: int) -> bool:
    at = _SEPARATOR.match(an.text, start, end).end()
    opener = _OPENER.match(an.text, at, end)
    return bool(_STATUS_KEY.match(an.text, opener.end() if opener else at, end))


def _procedure_called_off(an: Analysis, start: int, end: int) -> bool:
    """Whether [start, end) says the procedure was cancelled, postponed, rescheduled or not performed ("The procedure
    was cancelled because the patient had eaten breakfast."), and not of an earlier encounter."""
    key = ('called-off', start, end)
    if key not in an.memo:
        an.memo[key] = any(_generic_reading(an, m.start(), m.end()).status != 'historical'
                           for pattern in (cues.PROCEDURE_CANCELLED, cues.PROCEDURE_NOT_PERFORMED)
                           for m in pattern.finditer(an.text, start, end))
    return an.memo[key]


# A typed answer that the procedure was not performed: "Procedure performed: No (patient refused).", "Exam
# completed? no" (round 4 release:8). Only these label words, then a separator, then a denial that opens the value.
_PERFORMED_ANSWERED_NO = re.compile(r'[ \t]*(?:procedure|exam|examination|study|endoscopy|case)[ \t]+'
                                    r'(?:performed|done|completed)[ \t]*[:?=|\u2013\u2014-][ \t]*'
                                    r'(?:no|n|not\s+(?:done|performed|completed))\b', re.A | re.I)


def _calls_off(an: Analysis, ks: int, ke: int) -> bool:
    """Whether the sentence [ks, ke) is a status line or a typed answer that denies the service, or says the procedure
    was called off."""
    line = an.text.rfind('\n', 0, ks) + 1  # the answer's label may be a heading, read as a sentence of its own
    return ((_status_line(an, ks, ke) and _denies(an, ks, ke, bare=False))
            or bool(_PERFORMED_ANSWERED_NO.match(an.text, line, ke)) or _procedure_called_off(an, ks, ke))


def _called_off_further(an: Analysis, index: int) -> Optional[str]:
    """A status line that denies the service ("Status: Cancelled - ...", "Procedure status: Not performed."), a typed
    "Procedure performed: No", or a sentence that says the procedure was called off, within DENIAL_SENTENCES sentences
    after - or before - the service line at ``index``, in any section but a plan or a history. Reading stops at a
    sentence that names a service of another family (that one speaks of its own service); a sentence naming only the
    line's own family ("The risks and benefits of EUS were discussed.") is read on (round 4 routing:6). It holds the
    line above it, never excludes."""
    key = ('called-off-further', index)
    if key not in an.memo:
        an.memo[key] = None
        own = {m.family for m in an.services_in(*an.lay.sentences[index])}
        sentences = an.lay.sentences
        for step in (1, -1):
            read = 0
            position = index + step
            while 0 <= position < len(sentences) and abs(position - index) <= 2 * DENIAL_SENTENCES:
                ks, ke = sentences[position]
                position += step
                heading = an.lay.section_at(ks).heading
                if heading is not None and heading.start == ks and ke <= heading.end:
                    continue  # a heading line ("Indication:") is structure, not a sentence about the service
                read += 1
                if read > DENIAL_SENTENCES or {m.family for m in an.services_in(ks, ke)} - own:
                    break
                if an.lay.section_at(ks).kind in ELSEWHERE_SECTIONS or _unchecked_option(an, ks, ke):
                    continue
                if _calls_off(an, ks, ke):
                    an.memo[key] = an.text[ks:ke]
                    break
            if an.memo[key] is not None:
                break
    return an.memo[key]


# A label line whose own words deny performance: "Procedures not performed:", "Not done:", "Procedures not performed
# today:". With its verb it is no heading (sections keep it content), so the lines under it take the section before
# it. ("Cancelled procedures:", with no verb, is a heading of its own: the lines under it read its silent default.)
_DENYING_LABEL = re.compile(r'[ \t]*(?:[-*][ \t]*)?(?:[A-Za-z][\w/-]*[ \t]+){0,3}?(?:not[ \t]+(?:performed|done)|cancell?ed|'
                            r'deferred|declined)(?:[ \t]+[\w/-]+){0,5}[ \t]*:[ \t]*', re.A | re.I)
LABEL_ITEMS = 12  # item lines read back to their label (bounds the work per span)


def _denying_label_above(an: Analysis, s: int) -> Optional[str]:
    """The label line over the list that the line of the sentence at ``s`` belongs to, when that label denies
    performance (_DENYING_LABEL): read back over at most LABEL_ITEMS lines of the same section, stopping at a blank
    line or at any other label line (a line that ends with a colon), which then governs instead."""
    key = ('denying-label', s)
    if key not in an.memo:
        an.memo[key] = None
        text = an.text
        starts = an.memo.get(('line-starts',))
        if starts is None:
            starts = an.memo[('line-starts',)] = [0] + [m.end() for m in re.finditer('\n', text)]
        index = bisect.bisect_right(starts, s) - 1
        section = an.lay.section_at(s)
        for line in range(index - 1, max(-1, index - 1 - LABEL_ITEMS), -1):
            ls, le = starts[line], starts[line + 1] - 1
            words = text[ls:le].strip()
            if not words or an.lay.section_at(ls) is not section:
                break
            if words.endswith(':'):
                if len(words) <= 80 and _DENYING_LABEL.fullmatch(text, ls, le):
                    an.memo[key] = words
                break
    return an.memo[key]


def _denies_an_act(an: Analysis, start: int, end: int) -> bool:
    """Whether the short line [start, end) carries an act denial that nothing explains ("Not performed.", "Patient
    declined.") and that is not the denial of another act or care step written right after its name
    (cues.OTHER_ACT_DENIED: "Sedation was not needed.", "Retroflexion: not performed", "The patient did not
    require sedation."). Every other unexplained act denial still denies the service named before the line."""
    other = [(m.start(), m.end()) for m in cues.OTHER_ACT_DENIED.finditer(an.text, start, end)]
    for token in cues.DOUBT_TOKEN.finditer(an.text, start, end):
        if not _ACT_DENIAL.fullmatch(token.group(0)) or _covered((token.start(), token.end()), other):
            continue
        if _denying_word(an, token.start(), token.end(), only=_ACT_DENIAL):
            return True
    return False


def _later_denial(an: Analysis, after: int, s: int, e: int, bare: bool) -> Optional[str]:
    """The later clause of the sentence [s, e) (after ``after``, the end of the service's own clause),
    or else the next sentence of the same section, that denies the service named before it (see
    _denies); None when none does. A clause or a sentence that names a service speaks of that one,
    unless it names only this service and reschedules it ("The EUS will be rescheduled because ...").
    Then a denying status line or a cancellation further down (_called_off_further). Also the label line
    above the service's line when its own words deny performance (_denying_label_above): read here, as
    the one denial a section-read service is asked about, although it stands before the line."""
    label = _denying_label_above(an, s)
    if label is not None:
        return label
    for cs, ce in _first_clauses_in(an, after, e, DENIAL_CLAUSES):
        if an.services_in(cs, ce):
            return None
        if _denies(an, cs, ce, bare=False):
            return an.text[cs:ce]
    index = _sentence_index(an, s)
    if index < 0:
        return None
    if index + 1 < len(an.lay.sentences):
        ns, ne = an.lay.sentences[index + 1]
        if an.lay.section_at(ns) is an.lay.section_at(s):
            named = an.services_in(ns, ne)
            if not named and _denies(an, ns, ne, bare):
                return an.text[ns:ne]
            if named and _reschedules(an, ns, ne):
                own = {m.family for m in an.services_in(s, after)}
                if own and all(m.family in own for m in named):
                    return an.text[ns:ne]
    # also for the last sentence: a status line may stand above it (round 4 routing:6)
    return _called_off_further(an, index)


def _clause_end(an: Analysis, pos: int, e: int) -> int:
    """The end of the clause that holds ``pos`` (at most ``e``)."""
    for cs, ce in an.lay.clauses_for(pos, pos + 1):
        if cs <= pos < ce:
            return min(ce, e)
    return e


def _silent_section(an: Analysis, ts: int, te: int) -> Optional[str]:
    """A cue when a section default would make a named service performed although the words
    after the name in its clause are not those of a procedure description (_continuation), or a
    later clause or the next line speaks of it and denies it (_later_denial): the section stays
    silent."""
    key = ('silent-section', ts, te)
    if key not in an.memo:
        an.memo[key] = None
        s, e = an.lay.sentence_for(ts, te)
        named = [m for m in an.services_in(max(s, ts - 120), min(e, max(te, ts + 1) + 120))
                 if _overlaps(m.start, m.end, ts, max(te, ts + 1))]
        for m in named:
            end = _group_end(an, m, e)
            word = _continuation(an, end, e, _clause_end(an, m.start, e),
                                 procedure=an.lay.section_at(m.start).kind == 'procedure')
            if word is not None:
                an.memo[key] = f"{SILENT_SECTION_PREFIX} '{word}' follows the service name, so its section does not make it performed"
                break
            before, after = an.text[s:m.start], an.text[end:e]
            bare = not after.strip(' \t.;:!?)') and len(before) <= 40 and not _VERB_BEFORE.search(before)
            line = _later_denial(an, _clause_end(an, m.start, e), s, e, bare)
            if line is not None:
                an.memo[key] = f"{SILENT_SECTION_PREFIX} the text after it ('{line.strip()}') qualifies it"
                break
    return an.memo[key]


def _landmark_in(an: Analysis, start: int, end: int) -> bool:
    return any(p.search(an.text, start, end) for _, _, p in cues.UPPER_LANDMARKS + cues.LOWER_LANDMARKS)


def _started_before(an: Analysis, pos: int) -> bool:
    """The sentence before, in the same section, documents the scope going in (and names no
    other procedure than the sentence at ``pos``)."""
    index = _sentence_index(an, pos)
    if index <= 0:
        return False
    (ps, pe), (s, e) = an.lay.sentences[index - 1], an.lay.sentences[index]
    if an.lay.section_at(ps) is not an.lay.section_at(s) or not cues.STARTED.search(an.text, ps, pe):
        return False
    before, here = {m.family for m in an.services_in(ps, pe)}, {m.family for m in an.services_in(s, e)}
    return not (before and here and before.isdisjoint(here))


def _abort_status(an: Analysis, cue: Cue) -> tuple[str, bool]:
    """(status, doubt) of an "aborted": cancelled when its sentence says it was before the
    start, incomplete once the scope went in (advanced, reached, a landmark or a depth in cm,
    here or in the sentence before), and otherwise uncertain - held, never excluded."""
    key = ('abort', cue.start)
    if key not in an.memo:
        text = an.text
        s, e = an.lay.window(an.lay.sentence_for(cue.start, cue.end), cue.start, cue.end, CLAUSE_REACH)
        if cues.BEFORE_START.search(text, s, e):
            an.memo[key] = ('cancelled', False)
        elif cues.STARTED.search(text, s, e) or _landmark_in(an, s, e) or _started_before(an, cue.start):
            an.memo[key] = ('incomplete', False)
        else:
            an.memo[key] = ('uncertain', True)
    return an.memo[key]


# --- whose time a relative-time or outside-place cue tells (routing:0) --------------------------------------------
# The history cues read for their owner: 'ago' (read at 57b4b3747), and 'last month' and 'elsewhere' (round 2b). A cue
# is the service's only when nothing but the service's own act stands between them ("EGD was performed last month",
# "She underwent EGD last year", "Last month she underwent EGD"). One that trails a test, a result or a diagnosis is
# that thing's ("a positive FIT last month", "a CT scan done last week", "anemia diagnosed last month", "a mass seen
# on CT last week"). Anything else, or the service's own history in a clause that says today, is held: never
# historical, and a pre-57b4b3747 cue ('ago') never releases. The round-2b cues never demote an E/M visit statement.
_OWNED_TIME_CUES = ('ago', 'last month', 'elsewhere')
_ROUND_2B_TIME_CUES = ('last month', 'elsewhere')
_TIME_TOKEN = re.compile(r"[A-Za-z][\w/'&-]*|\d+(?:\.\d+)?", re.A)
# Words that tell nobody's time: auxiliaries, the subject and the act of a performance, determiners and links.
_TIME_PASS = frozenset((
    'was', 'were', 'is', 'are', 'be', 'been', 'being', 'has', 'have', 'had', 'did', 'does', 'do', 'also', 'then',
    'subsequently', 'successfully', 'uneventfully', 'a', 'an', 'the', 'her', 'his', 'their', 'its', 'this', 'that',
    'of', 'on', 'at', 'by', 'in', 'from', 'with', 'for', 'to', 'into', 'and', 'or', 'she', 'he', 'they', 'we', 'i',
    'patient', 'pt', 'performed', 'done', 'completed', 'carried', 'out', 'undertaken', 'underwent', 'undergone',
    'received', 'obtained', 'taken', 'collected', 'drawn', 'reviewed', 'mm', 'cm', 'x', cues.SERVICE_TOKEN))
# A finite verb passed on the walk back makes the time its subject's ("Colonoscopy for a positive FIT was performed last
# month"), unless a relative pronoun makes it a clause of the thing ("a CT that was done last week").
_FINITE = frozenset(('was', 'were', 'is', 'are', 'has', 'have', 'had', 'been', 'being'))
_RELATIVE_PRONOUN = frozenset(('that', 'which', 'who'))
# Words that describe the service itself (beside its names, interventions and landmarks, which are read as spans).
_TIME_OWN = frozenset((
    'screening', 'surveillance', 'diagnostic', 'therapeutic', 'routine', 'complete', 'full', 'upper', 'lower',
    'flexible', 'cold', 'hot', 'snare', 'forceps', 'scope', 'colonoscope', 'endoscope', 'gastroscope', 'sigmoidoscope',
    'duodenoscope', 'echoendoscope', 'enteroscope', 'procedure', 'exam', 'examination'))
# What another thing's time trails: a test, a result or a diagnosis, by its noun or its participle.
_ANOTHER_THING = re.compile(r'(?:FIT|i?FOBT|gFOBT|FIT-DNA|Cologuard|mt-?sDNA|stool|fecal|CT|CTA|CTE|CTC|MRI|MRCP|MRE|PET|'
                            r'PET-CT|ultrasound|sonograms?|sonography|x-?rays?|radiographs?|imaging|scans?|colonography|'
                            r'enterography|esophagram|barium|labs?|laboratory|bloodwork|CBC|hemoglobin|Hgb|ferritin|'
                            r'LFTs?|lipase|bilirubin|CEA|calprotectin|serolog\w*|tests?|testing|results?|reports?|'
                            r'patholog\w*|histolog\w*|cytolog\w*|cultures?|diagnos\w*|seen|found|noted|detected|'
                            r'identified|discovered|shown|showed|demonstrated|revealed|suspected|confirmed|positive|'
                            r'abnormal|elevated)', re.A | re.I)
TIME_REACH = 120  # how far back a time's owner is looked for (bounds the work per cue)


def _trails_another_thing(an: Analysis, pos: int, lo: int) -> bool:
    """Whether the time told at ``pos`` trails a test, a result or a diagnosis: walking back from ``pos`` (not before
    ``lo``, nor past a sentence stop or a comma) over words that tell nobody's time, the first other word names one,
    and no finite verb outside a relative clause stands between them (_FINITE)."""
    text = an.text
    lo = max(lo, pos - TIME_REACH)
    lo = max(lo, text.rfind('\n', lo, pos) + 1)  # never past a line start, and never scanned beyond the reach
    tokens = list(_TIME_TOKEN.finditer(text, lo, pos))
    end, finite = pos, False
    for token in reversed(tokens):
        if any(ch in '.;!?,' for ch in text[token.end():end]):
            return False
        end = token.start()
        word = token.group(0).lower()
        if word in _FINITE:
            finite = True
            continue
        if word in _RELATIVE_PRONOUN:
            finite = False
            continue
        if word in _TIME_PASS:
            continue
        return not finite and bool(_ANOTHER_THING.fullmatch(token.group(0)))
    return False


def _only_its_own_act(an: Analysis, lo: int, hi: int, history: list[tuple[int, int]]) -> bool:
    """Whether [lo, hi) holds nothing but words of the service's own act: words that tell nobody's time, words that
    describe the service, and service names, interventions, landmarks and other history cues (``history``)."""
    text = an.text
    if hi - lo > TIME_REACH:
        return False
    covered = ([(m.start, m.end) for m in an.services_in(lo, hi)] + [(iv.start, iv.end) for iv in an.interventions_in(lo, hi)]
               + [m.span() for m in _LANDMARK_AT.finditer(text, lo, hi)] + history)
    for token in _TIME_TOKEN.finditer(text, lo, hi):
        word = token.group(0).lower()
        if word in _TIME_PASS or word in _TIME_OWN:
            continue
        if not any(s <= token.start() and token.end() <= e for s, e in covered):
            return False
    return True


def _time_owner(an: Analysis, start: int, end: int, members: list[tuple[int, int]], window: tuple[int, int],
                history: list[tuple[int, int]]) -> str:
    """Whose time the expression at [start, end) tells, for the target whose service names and interventions are
    ``members`` (see _groups), in the clause window ``window``: 'other' (a symptom's, or a test's, result's or
    diagnosis's named before it), 'service' (only the service's own act stands between it and the nearest member) or
    'unclear'. A member written after the time is reached only when none is written before it ("Last month she
    underwent EGD")."""
    cs, _ = window
    if cues.SYMPTOM_TIME_BEFORE.search(an.text, max(cs, start - 40), start):
        return 'other'
    if any(_overlaps(s, e, start, end) for s, e in members):
        return 'service'
    before = [e for s, e in members if e <= start]
    if before:
        anchor = max(before)
        if _trails_another_thing(an, start, anchor):
            return 'other'
        if _another_familys_anchor(an, members, anchor):
            return 'unclear'  # "Colonoscopy ... after a normal EGD performed last week": maybe not the colonoscopy's
        return 'service' if _only_its_own_act(an, anchor, start, history) else 'unclear'
    if _trails_another_thing(an, start, cs):
        return 'other'
    after = [s for s, e in members if s >= end]
    return 'service' if after and _only_its_own_act(an, end, min(after), history) else 'unclear'


def _another_familys_anchor(an: Analysis, members: list[tuple[int, int]], anchor: int) -> bool:
    """Whether the member ending at ``anchor`` is a service of another family than the first service of ``members``
    (round 4 routing:5). Then a time after it may be that service's, so it holds the target rather than dating it."""
    services = [m for s, e in sorted(members) for m in an.services_in(s, e) if m.kind == 'service']
    at_anchor = [m for m in services if m.end == anchor]
    return bool(services and at_anchor) and at_anchor[-1].family != services[0].family


def _owned_time_cue(an: Analysis, cue: Cue, members: list[tuple[int, int]], window: tuple[int, int], em: bool,
                    today: bool, history: list[tuple[int, int]]) -> Optional[tuple[str, str]]:
    """(status, label) an attached 'ago', 'last month' or 'elsewhere' cue gives the target, or None when it is not the
    target's time at all (see _OWNED_TIME_CUES). ``today``: a today marker of the clause attaches to the target."""
    if em and cue.name in _ROUND_2B_TIME_CUES:
        return None
    owner = _time_owner(an, cue.start, cue.end, members, window, history)
    if owner == 'other':
        if cue.name in _ROUND_2B_TIME_CUES:
            return None
        return 'uncertain', f"uncertain: '{cue.text}' dates another thing named before it"
    if owner == 'service' and not today:
        return 'historical', f'historical: {cue.text}'
    if owner == 'service':
        return 'uncertain', f"{ANOTHER_TIME_PREFIX}: '{cue.text}' beside today in one clause"
    return 'uncertain', f"{ANOTHER_TIME_PREFIX}: '{cue.text}' may date it or another thing in its clause"


# --- another time (routing:8, routing:10): a time no listed cue reads holds a reading that would be performed --------
# The prefix of every time hold (here and in _owned_time_cue): no fact is read from a clause about a service so held
# (_about_another_procedure).
ANOTHER_TIME_PREFIX = 'uncertain: another time'
# A time told against an event written after it is that event's relation, not another date of the service: "the day
# before the colonoscopy", "two weeks after a positive FIT", "3 days prior to surgery". Only "... before.", "...
# prior." or "... after." with no event after them tell another date.
_RELATIONAL_END = re.compile(r'(?:before|after)$', re.A | re.I)
_PRIOR_END = re.compile(r'prior$', re.A | re.I)
_AN_EVENT_AFTER = re.compile(r'[ \t]+[A-Za-z0-9]', re.A)
_TO_AN_EVENT_AFTER = re.compile(r'[ \t]+to[ \t]+[A-Za-z0-9]', re.A | re.I)
# The times that tell history (_tells_history): a past-tense performed clause told so is no same-day procedure.
_HISTORY_TIMES = ('another encounter', 'childhood', 'recently', 'yesterday')
_PAST_INTERVAL = re.compile(r'(?:prior|earlier|before|previously|back)$', re.A | re.I)
# A time a comparison names is no time of the service: "The cecum was reached, as on her prior exam".
_COMPARE_LEAD = re.compile(r'\b(?:as|than|unlike|compared\s+(?:with|to)|in\s+comparison\s+(?:with|to)|similar\s+to)[\s,]*$',
                           re.A | re.I)
_WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
_MONTH_INDEX = {name: n for n, names in enumerate((('jan', 'january'), ('feb', 'february'), ('mar', 'march'),
                                                   ('apr', 'april'), ('may',), ('jun', 'june'), ('jul', 'july'),
                                                   ('aug', 'august'), ('sep', 'sept', 'september'), ('oct', 'october'),
                                                   ('nov', 'november'), ('dec', 'december')), 1) for name in names}


def _other_times(an: Analysis) -> tuple[list, list[int]]:
    """Every cues.OTHER_TIME match in the text, matched once over the whole text: (start, end, name, match), sorted."""
    key = ('other-times',)
    if key not in an.memo:
        found = sorted(((m.start(), m.end(), name, m) for name, pattern in cues.OTHER_TIME
                        for m in pattern.finditer(an.text)), key=lambda item: (item[0], item[1]))
        an.memo[key] = (found, [item[0] for item in found])
    return an.memo[key]


_PART_OF_MONTH = re.compile(r'\b(?:early|mid|late|end\s+of|beginning\s+of)\b', re.A | re.I)


def _today_compatible(an: Analysis, name: str, m: re.Match) -> bool:
    """Whether a weekday, a month or a month/day may be the date of service itself (never when that is unknown)."""
    day = an.service_date
    if day is None or name not in ('weekday', 'month', 'month/day'):
        return False
    said = m.group(0).lower()
    if name == 'weekday':
        return (m.group('rel') or 'this').lower() == 'this' and _WEEKDAYS[day.weekday()] in said
    if name == 'month/day':
        return (int(m.group('m')), int(m.group('d'))) == (day.month, day.day)
    if said.startswith(('last', 'next', 'past')):
        return False
    month = _MONTH_INDEX[(m.group('month') or m.group('may') or m.group('month2')).lower()]
    mday = m.group('mday') or m.group('mday2')
    if mday is None and _PART_OF_MONTH.search(said):
        return False  # "at the end of October", "in early October": maybe not the day of service (round 4 routing:7)
    return month == day.month and (mday is None or int(mday) == day.day)


def _tells_history(an: Analysis, name: str, m: re.Match) -> bool:
    """Whether an OTHER_TIME match tells a time before the date of service ("at her last visit", "as a child",
    "recently underwent", "two weeks prior", "last Tuesday", "in June" before an October date of service), never a
    later or an unknown one ("in 6 wks", "next Tuesday", "in December")."""
    if name in _HISTORY_TIMES:
        return True
    if name == 'interval':
        return bool(_PAST_INTERVAL.search(m.group(0)))
    if name == 'weekday':
        return (m.group('rel') or '').lower() in ('last', 'past', 'previous')
    day = an.service_date
    if day is None or name not in ('month', 'month/day'):
        return False
    if name == 'month/day':
        return (int(m.group('m')), int(m.group('d'))) < (day.month, day.day)
    said = m.group(0).lower()
    if said.startswith(('last', 'past', 'next', 'this')):
        return said.startswith(('last', 'past'))
    month = _MONTH_INDEX[(m.group('month') or m.group('may') or m.group('month2')).lower()]
    mday = m.group('mday') or m.group('mday2')
    return (month, int(mday)) < (day.month, day.day) if mday else month < day.month


def _attached_times(an: Analysis, start: int, end: int):
    """(name, match, owner) of each OTHER_TIME match that attaches to the passage [start, end) in one of its clauses,
    other than a symptom's, a test's or a result's (owner 'other'), one told against an event after it
    (_RELATIONAL_END), one a comparison names, a weekday, month or month/day that may be the date of service, and any
    in a clause whose today marker attaches to the passage. Owner: 'service' or 'unclear' (_time_owner)."""
    found, starts = _other_times(an)
    text = an.text
    for clause in an.lay.clauses_for(start, end):
        cs, ce = an.lay.window(clause, start, end, CLAUSE_REACH)
        times = [item for item in found[bisect.bisect_left(starts, cs):bisect.bisect_left(starts, ce)] if item[1] <= ce]
        if not times:
            continue
        spans, index, members = _groups(an, cs, ce, start, end)
        if any(_attached(spans, index, m.start(), m.end()) for m in cues.TODAY.finditer(text, cs, ce)):
            continue
        history = [(c.start, c.end) for c in an.cues_in(cs, ce) if c.status == 'historical']
        names = {(m.start, m.end) for m in an.services_in(cs, ce)} | {(iv.start, iv.end)
                                                                       for iv in an.interventions_in(cs, ce)}
        named = [m for m in members if m in names] or [(max(start, cs), min(max(end, start + 1), ce))]
        for ts_, te_, name, m in times:
            if not _attached(spans, index, ts_, te_):
                continue
            if _today_compatible(an, name, m) or _COMPARE_LEAD.search(text, max(cs, ts_ - 30), ts_):
                continue
            said = m.group(0)
            if (_RELATIONAL_END.search(said) and _AN_EVENT_AFTER.match(text, te_, ce)) \
                    or (_PRIOR_END.search(said) and _TO_AN_EVENT_AFTER.match(text, te_, ce)):
                continue  # "two weeks after a positive FIT", "the day before the colonoscopy": told against an event
            owner = _time_owner(an, ts_, te_, named, (cs, ce), history)
            if owner != 'other':
                yield name, m, owner


def _another_time(an: Analysis, start: int, end: int) -> Optional[str]:
    """A cue holding the passage [start, end), which would read performed, when a time no listed cue reads attaches
    to it (_attached_times). (A listed history or planned cue or a date that attaches already outranks a hold.) It
    never excludes: the hold-only rule."""
    key = ('another-time', start, end)
    if key not in an.memo:
        an.memo[key] = next((f"{ANOTHER_TIME_PREFIX}: '{m.group(0)}' may place it on another date"
                             for _, m, _ in _attached_times(an, start, end)), None)
    return an.memo[key]


def _told_at_another_time(an: Analysis, start: int, end: int) -> bool:
    """Whether the passage [start, end) is told at a time before the date of service that is its own (owner
    'service', _tells_history): "Hemorrhoid banding was performed at her last visit", "Appendectomy was done as a
    child". A later or unknown time ("with a repeat banding in 6 wks") is never this: it holds, it never releases."""
    return any(owner == 'service' and _tells_history(an, name, m) for name, m, owner in _attached_times(an, start, end))


def _clause_reading_cues(an: Analysis, clause: tuple[int, int], ts: int, te: int,
                         em: bool = False) -> list[tuple[str, str, bool, bool]]:
    """(status, label, about_past, doubt) for every cue that governs the target in one clause. ``em``: the target is
    an E/M documentation mention (see _owned_time_cue)."""
    text = an.text
    cs, ce = an.lay.window(clause, ts, te, CLAUSE_REACH)
    spans, index, members = _groups(an, cs, ce, ts, te)
    words = text[cs:ce]
    found = []
    clause_cues = an.cues_in(cs, ce)
    today = any(_attached(spans, index, m.start(), m.end()) for m in cues.TODAY.finditer(text, cs, ce))
    history = [(c.start, c.end) for c in clause_cues if c.status == 'historical']
    # the service names and interventions of the target's group: a cited passage is no name of its own
    names = {(m.start, m.end) for m in an.services_in(cs, ce)} | {(iv.start, iv.end) for iv in an.interventions_in(cs, ce)}
    named = [m for m in members if m in names] or [(max(ts, cs), min(max(te, ts + 1), ce))]
    for cue in clause_cues:
        status, doubt = cue.status, False
        if cue.name == 'aborted':
            status, doubt = _abort_status(an, cue)
        if cue.name in ('terminated', 'stopped') and cues.MEDICATION.search(words):
            continue
        if cue.name in ('ago', 'last month') and cues.SYMPTOM_TIME_BEFORE.search(text, max(cs, cue.start - 40), cue.start):
            continue  # "bleeding since last month": the symptom's time, not the service's
        if cue.name == 'elsewhere' and cues.REQUEST_BEFORE.search(text, max(cs, cue.start - 30), cue.start):
            continue  # "EUS requested by her previous gastroenterologist": a request, not a history
        if cue.name in ('scheduled', 'plan', 'booked', 'ordered', 'recommend') \
                and cues.AS_BOOKED_BEFORE.search(text, max(cs, cue.start - 30), cue.start):
            continue  # "was performed today as scheduled": the booking it kept, not a future
        if _attached(spans, index, cue.start, cue.end):
            if cue.name in _OWNED_TIME_CUES:
                owned = _owned_time_cue(an, cue, named, (cs, ce), em, today, history)
                if owned is not None:
                    found.append((owned[0], owned[1], False, False))
                continue
            label = (f'uncertain: {cue.text}, with no statement whether the procedure had started' if doubt
                     else f'{status}: {cue.text}')
            found.append((status, label, False, doubt))
    for d in an.dates_in(cs, ce):
        if not _attached(spans, index, d.start, d.end, DATE_REACH):
            continue
        label = text[d.start:d.end]
        if an.service_date is None:
            found.append(('uncertain', f'uncertain: dated {label}; service date not established', False, False))
        else:
            order = ctx.compare_to_service(d, an.service_date)
            if order < 0:
                found.append(('historical', f'historical: {label} is before the service date', False, False))
            elif order > 0 and not d.bare:  # a lone future "year" is more often a room or a count
                found.append(('planned', f'planned: {label} is after the service date', False, False))
    # A negation that names no service or intervention denies the act it describes. Over a
    # target inside its clause it is a negation; over a longer passage that mixes it with
    # other text it is a doubt.
    for label, (s, e) in _memberless_negations(an, cs, ce):
        if _overlaps(s, e, ts, max(te, ts + 1)):
            if clause[0] <= ts and te <= clause[1]:
                found.append(('negated', label, False, False))
            else:
                denied = label.split(': ', 1)[1]
                found.append(('uncertain', f"uncertain: part of the passage is denied ('{denied}')", False, True))
    today = bool(cues.TODAY.search(words))
    for ms, me in members:
        post = _masked_post(an, me, ce)
        negations, _ = _member_negations(an, cs, ce, ms, me, post)
        found += [('negated', label, past, False) for label, past, _ in negations]
        pre_cues, had = _pre_cues(an, _pre_start(an, cs, ms), ms)
        found += pre_cues
        if had is not None and not today:
            found.append(had)
        for status, entries in (('incomplete', cues.INCOMPLETE_POST), ('uncertain', cues.UNCERTAIN_POST)):
            for name, pattern in entries:
                m = pattern.search(post)
                if m:
                    found.append((status, f'{status}: {_said(m)}', False, name == 'pending'))
    return found


def _section_label(section) -> str:
    heading = f' ({section.heading.text.rstrip(":").strip()})' if section.heading else ''
    return f'section: {section.kind}{heading}'


# A plan-section passage whose clause says today is held, never planned and never performed (validation:1; round 4,
# routing:1 and routing:3). Round 3b also released an explicit past-tense performance that said today as performed;
# round 4 found it firing on another thing's past tense ("the MRI that was done this morning"), so it was withdrawn.
PLAN_TODAY = 'uncertain: its clause says today, so its plan section does not make it planned'


def _cue_reading(an: Analysis, start: int, end: int, em: bool = False) -> Optional[Reading]:
    """The reading of [start, end) from the cues of its clauses. An explicit performance cue is history in
    a history section (uncertain if its clause says today), uncertain in a plan section (carrying PLAN_TODAY when a
    clause says today, so the E/M beside it is held; round 3b's release of such a clause as performed was withdrawn
    in round 4, routing:1, because it fired on another thing's past tense), and uncertain in an indication section
    unless its clause says today: an indication tells why
    today's service is done, or its prior work-up ("An EGD was performed in August"), so a past-tense
    performance there is held, never performed. ``em``: an E/M documentation mention, which the indication rule
    does not concern."""
    found = []
    for clause in an.lay.clauses_for(start, end):
        found.extend(_clause_reading_cues(an, clause, start, end, em))
    if not found:
        return None
    status = next(s for s in STATUS_PRECEDENCE if any(f[0] == s for f in found))
    deciding = tuple(dict.fromkeys(f[1] for f in sorted((f for f in found if f[0] == status), key=lambda f: not f[3])))
    past = status == 'negated' and all(f[2] for f in found if f[0] == 'negated')
    doubt = status == 'uncertain' and any(f[3] for f in found if f[0] == 'uncertain')
    section = an.lay.section_at(start)
    if status == 'performed' and section.kind == 'history':
        today = any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(start, end))
        return Reading('uncertain' if today else 'historical', deciding + (_section_label(section),), 'cue')
    if status == 'performed' and section.kind == 'plan':
        today = any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(start, end))
        return Reading('uncertain', deciding + ((PLAN_TODAY,) if today else ()) + (_section_label(section),), 'cue')
    if status == 'performed' and section.kind == 'indication' and not em \
            and not any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(start, end)):
        return Reading('uncertain', deciding + (_section_label(section),), 'cue')
    if status == 'performed' and not em:
        held = _another_time(an, start, end)  # a time no listed cue reads holds it (routing:10)
        if held:
            return Reading('uncertain', (held,) + deciding, 'cue', doubt=True)  # contradicts (round 4 routing:7)
    return Reading(status, deciding, 'cue', past, doubt)


HELD_AFTER_A_CUT = 'uncertain: the line before it is cut after a plan, cancellation or denial verb'
EM_DOCUMENTATION = ': E/M documentation of this encounter'
SILENT = 'uncertain: no performance evidence in its sentence or section'  # validation reads this prefix as silence


def _default_reading(an: Analysis, start: int, end: int) -> Reading:
    section = an.lay.section_at(start)
    label = _section_label(section)
    if section.kind in POSITIVE_SECTIONS:
        held = _another_time(an, start, end)  # a time no listed cue reads keeps the section silent (routing:8)
        if held:
            # a doubt, so it contradicts the family's other section evidence (round 4 routing:7)
            return Reading('uncertain', (held, label), 'cue', doubt=True)
        return Reading('performed', (label,), 'section')
    if section.kind == 'plan':
        # a plan's default at most holds a clause that says today (validation:1): it may document today's service.
        # Round 4 (routing:3): also when a hedge, condition or future word is in the clause. The word may be about
        # the finding ("EGD this morning revealed a Schatzki ring, likely the cause"), and no word list tells which,
        # so the clause holds rather than plans; a hold costs a clarification, a plan excluded today's procedure.
        windows = [an.lay.window(clause, start, end, CLAUSE_REACH) for clause in an.lay.clauses_for(start, end)]
        if any(cues.TODAY.search(an.text, *w) for w in windows):
            return Reading('uncertain', (PLAN_TODAY, label), 'section')
        return Reading('planned', (label,), 'section')
    if section.kind == 'history':
        return Reading('historical', (label,), 'section')
    if section.kind in EM_SECTIONS and not an.touches_service(start, end):
        return Reading('performed', (label + EM_DOCUMENTATION,), 'section')
    heading = section.heading
    if section.kind == 'other' and section.label == gi_sections._SEC_HELD_LABEL:
        # a service line after a line cut on a plan, cancellation or denial verb (sections, round 4 structure:11)
        return Reading('uncertain', (HELD_AFTER_A_CUT,), 'cue', doubt=True)
    if (section.kind == 'other' and heading is not None
            and gi_sections._sec_phrase_heading(an.text, (section.kind, section.label, heading))):
        # under a colon-less phrase line inside findings (sections, round 4 structure:4): it may tell another time or
        # a plan ("Surgical opinion for further management"), so what is listed under it is held, never silent
        return Reading('uncertain', (f"uncertain: listed under '{heading.text.strip()[:80]}', a line that may tell "
                                     'another time or a plan',), 'cue')
    if (section.kind == 'other' and heading is not None and heading.end - heading.start <= 80
            and _DENYING_LABEL.fullmatch(an.text, heading.start, heading.end)):
        # "Cancelled procedures:" opens a section of its own: what is listed under it is not silent (round 4 release:9)
        return Reading('uncertain', (f"uncertain: listed under '{an.text[heading.start:heading.end].strip()}', a "
                                     'label that denies performance',), 'cue', doubt=True)
    return Reading('uncertain', (SILENT,), 'default')


# Check boxes, as extraction writes them (U+2610 unchecked, U+2612 checked) and as pasted text carries them: the one
# box vocabulary of the shared contract, defined in studio.ingest.symbols and read the same way by extraction, the
# section reader and routing (unchecked: every box shape symbols lists, "[ ]" and "( )" with any inner whitespace,
# "[_]"; checked: every checked box shape, U+2713, U+2714, U+25A0, "[x]" and "(x)" with optional inner whitespace,
# "[*]", "[v]"). PDF form fields are also written as "<label>: not checked" (see _unchecked_state).
from studio.ingest import symbols as _BOX_SYMBOLS  # noqa: E402 (Django-free: the extraction child imports it too)
_BOX_PAD = _BOX_SYMBOLS.BOX_PAD  # a box's padding: any whitespace but a line break
_BOX = re.compile('(?P<off>' + _BOX_SYMBOLS.BOX_OFF_PATTERN + ')|(?P<on>' + _BOX_SYMBOLS.BOX_ON_PATTERN + ')')
# A mark in brackets that looks like a box but is none of the contract's ("(•)", "[?]", "[N]", "[-]", "{ }",
# "<x>"; the unread mark extraction writes is "[?]"): the item it marks is held, and it is never passed over to hand
# the item a neighbour's box. Bare radio glyphs and answers in parentheses count only where their line marks options
# (_box_tokens).
_BOX_UNREAD = re.compile(_BOX_SYMBOLS.BOX_UNREAD_PATTERN)
_BOX_RADIO = re.compile(_BOX_SYMBOLS.BOX_RADIO_PATTERN)
_BOX_PAREN_ANSWER = re.compile(_BOX_SYMBOLS.BOX_PAREN_ANSWER_PATTERN)
UNCHECKED = 'negated: an unchecked box'
BOXES_DISAGREE = 'uncertain: the check boxes for this item disagree'
BOX_UNREAD = 'uncertain: this item is marked with a box this reader cannot read'
# A status reference that a box or an answer keeps from being read as its status (_references): the checked or unread
# box of another denying option on its line ("[ ] Completed [x] Cancelled [ ] Aborted"), and a status question answered
# with a denial ("Procedure cancelled: No"). Each is held, never read as cancelled or incomplete.
BOX_STATUS_OPTION = "uncertain: a status option on the line '{}' is checked or cannot be read"
BOX_STATUS_ANSWER = "uncertain: the status question '{}' is answered no, which is held and never read as that status"
BOX_REACH = 200  # a box governs only an item within this many characters of it, on its line (bounds the work per span)
# The option a box marks in a yes/no pair ("Biopsy taken: [x] Yes [ ] No", "Biopsy taken: Yes [ ] No [x]").
_OPTION_WORDS = r'(?:(?P<yes>yes|done|performed)|(?P<no>no|not[ \t]+done|not[ \t]+performed|none))'
_OPTION_AFTER = re.compile(r'[ \t]*' + _OPTION_WORDS + r'\b', re.A | re.I)
_OPTION_BEFORE = re.compile(r'\b' + _OPTION_WORDS + r'[ \t]*$', re.A | re.I)
# A "No" that labels a box is an option, not a negation of the item ("[x] Yes [ ] No"): it explains itself.
_BOX_TEXT = _BOX.pattern.replace('?P<off>', '?:').replace('?P<on>', '?:')
_NO_OPTION = r'(?:no|none|not[ \t]+done|not[ \t]+performed)'
_OPTION_LABEL = re.compile(r'(?:' + _BOX_TEXT + r')[ \t]*' + _NO_OPTION + r'\b|\b' + _NO_OPTION + r'[ \t]*(?:' + _BOX_TEXT
                           + r')', re.A | re.I)
# What joins the items of one label ("Biopsy/polypectomy", "biopsy or polypectomy", "Biopsy, polypectomy"): a box
# after the label governs every item it names.
_LABEL_JOINER = re.compile(r'(?:[ \t\-/,&+()]|\b(?:and|or)\b)*', re.A | re.I)
# Boxes written next to each other with only spaces between them ("☒ ☐ Biopsy") are one item's; boxes in cells of
# their own ("Anoscopy | ☒ | ☐", a flattened "Done | Not done" table) are its options, and the first governs.
_BOX_RUN_GAP = re.compile(r'[ \t\u00a0]*')
_CELL_GAP = re.compile(r'[ \t\u00a0|:]*')  # what may open a sentence before its first box ("| ☐")
_LABEL_COLON = re.compile(r'[ \t\u00a0]*:[ \t\u00a0]*')  # between a label and the box after it ("Biopsy: ☐")


def _box_tokens(an: Analysis, lo: int, hi: int) -> tuple[list, list]:
    """The items and the boxes wholly inside [lo, hi). Items: (start, end) of service names, interventions and
    other procedures' names, overlapping ones merged. Boxes: (start, end, state), state 'off', 'on' or 'unread'. A bare
    radio glyph or an answer in parentheses is an unread mark only where [lo, hi) marks options (_box_option_marks)."""
    items = _merged(list({(m.start, m.end) for m in an.services_in(lo, hi)}
                         | {(iv.start, iv.end) for iv in an.interventions_in(lo, hi)} | set(_other_names_in(an, lo, hi))))
    unread = [(u.start(), u.end(), 'unread') for u in _BOX_UNREAD.finditer(an.text, lo, hi)
              if not _BOX.fullmatch(an.text, u.start(), u.end())]
    boxes = [(b.start(), b.end(), 'off' if b.group('off') is not None else 'on') for b in _BOX.finditer(an.text, lo, hi)]
    if unread:  # "(\u2713)" is one unread mark, not a box inside brackets
        starts = [u[0] for u in unread]
        boxes = [b for b in boxes if not (bisect.bisect_right(starts, b[0]) and
                                          b[1] <= unread[bisect.bisect_right(starts, b[0]) - 1][1])]
    marks = sorted(boxes + unread)
    return items, sorted(marks + _box_option_marks(an, lo, hi, marks))


def _box_option_marks(an: Analysis, lo: int, hi: int, marks: list) -> list:
    """The bare radio glyphs and answers in parentheses of [lo, hi) that mark options, as unread marks: a radio glyph
    when another one is in [lo, hi), or when a box or bracketed mark is and the glyph does not open its line (a bullet
    does); an answer in parentheses when any of those is ("\u25cb Biopsy \u25cf Cold snare polypectomy", "( ) Biopsy (Y)
    Cold snare polypectomy"; never "\u25cf Biopsy", "\u25cf Biopsy \u2610" or "H. pylori (-)"). Marks inside brackets
    are the bracketed mark's."""
    text = an.text

    def bracketed(pos):
        return any(s <= pos < e for s, e, _ in marks)

    def opens_its_line(pos):  # read back at most BOX_REACH characters: a line start further back is no opening
        newline = text.rfind('\n', max(0, pos - BOX_REACH), pos)
        return (newline >= 0 or pos <= BOX_REACH) and not text[newline + 1:pos].strip()

    radios = [m for m in _BOX_RADIO.finditer(text, lo, hi) if not bracketed(m.start())]
    if len(radios) < 2:
        radios = [m for m in radios if marks and not opens_its_line(m.start())]
    found = [(m.start(), m.end(), 'unread') for m in radios]
    if marks or found:
        found += [(m.start(), m.end(), 'unread') for m in _BOX_PAREN_ANSWER.finditer(text, lo, hi)
                  if not bracketed(m.start())]
    return found


def _box_segment(an: Analysis, start: int, end: int) -> tuple[int, int, int, int]:
    """(lo, hi) of the text whose boxes may govern [start, end), and the part of it on the item's line within
    BOX_REACH. The text is the item's sentence, joined to the sentences next to it on the same line that open with a
    box when that run of sentences ends with a box: a cell or a label ending in a period keeps the box after it
    ("Biopsy. | ☐", "Biopsy. ☐ Cold snare polypectomy. ☒")."""
    text, span_end = an.text, max(end, start + 1)
    sentence_start, sentence_end = an.lay.sentence_for(start, end)
    reach_lo, reach_hi = max(0, start - BOX_REACH), min(len(text), span_end + BOX_REACH)
    newline = text.rfind('\n', reach_lo, start)
    line_lo = newline + 1 if newline >= 0 else reach_lo
    newline = text.find('\n', end, reach_hi)
    line_hi = reach_hi if newline < 0 else newline
    lo, hi = min(sentence_start, start), max(sentence_end, span_end)
    index = _sentence_index(an, start)
    if index >= 0:
        sentences = an.lay.sentences
        first = last = index
        while first > 0 and sentences[first - 1][0] >= reach_lo and _opens_with_a_box(an, sentences[first]) \
                and '\n' not in text[sentences[first - 1][1]:sentences[first][0]]:
            first -= 1
        while last + 1 < len(sentences) and sentences[last + 1][1] <= reach_hi \
                and _opens_with_a_box(an, sentences[last + 1]) and '\n' not in text[sentences[last][1]:sentences[last + 1][0]]:
            last += 1
        if first != last:
            merged_lo, merged_hi = sentences[first][0], sentences[last][1]
            items, boxes = _box_tokens(an, max(merged_lo, line_lo), min(merged_hi, line_hi))
            if boxes and (not items or boxes[-1][0] > items[-1][0]):  # the run ends with a box: its boxes trail
                lo, hi = min(lo, merged_lo), max(hi, merged_hi)
    return lo, hi, max(lo, line_lo), min(hi, line_hi)


def _opens_with_a_box(an: Analysis, sentence: tuple[int, int]) -> bool:
    at = _CELL_GAP.match(an.text, sentence[0], sentence[1]).end()
    return bool(_BOX.match(an.text, at, sentence[1]) or _BOX_UNREAD.match(an.text, at, sentence[1]))


def _box_orientation(an: Analysis, lo: int, hi: int, extra: Optional[tuple[int, int]] = None) -> str:
    """'lead' or 'trail': whether the boxes of [lo, hi) mark the items after them or before them (``extra``: the
    passage being read when it is not an item itself, read as one). Boxes lead when the text opens with a box
    ("☐ Biopsy ☒ Cold snare polypectomy"), or when a service name or a label with a colon opens it, every box is
    followed straight by an item, and no item after a box is the next box's label ("Colonoscopy: [ ] biopsy [x] cold
    snare", "Polypectomy: [ ] cold snare [x] hot snare").
    Otherwise they trail ("Biopsy | ☐ | Cold snare polypectomy | ☒"), and items written after the last box are
    remarks that no box governs ("... | ☒ | clip placed after polypectomy")."""
    key = ('box-orientation', lo, hi, extra)
    if key not in an.memo:
        text = an.text
        items, boxes = _box_tokens(an, lo, hi)
        if extra is not None:
            items = _merged(items + [extra])
        if not boxes or not items or boxes[0][0] < items[0][0]:
            an.memo[key] = 'lead'
        elif boxes[-1][0] > items[-1][0]:
            an.memo[key] = 'trail'
        else:
            first = items[0]
            label_end = _label_end(text, items, 0)
            by_service = any(m.start == first[0] for m in an.services_in(first[0], first[1]))
            by_label = text.startswith(':', _BOX_RUN_GAP.match(text, label_end, hi).end(), hi)
            starts = {s for s, _ in items}
            followed = True
            for i, (s, e, _) in enumerate(boxes):
                if i + 1 < len(boxes) and _BOX_RUN_GAP.fullmatch(text, e, boxes[i + 1][0]):
                    continue  # boxes of one item: the run is followed by what follows its last box
                if _BOX_RUN_GAP.match(text, e, hi).end() not in starts:
                    followed = False
                    break
            # A label written straight after a box and followed by a colon and the next box is that box's label, so
            # the boxes trail ("Biopsy: [ ] Cold snare polypectomy: [x] clip placed", "Colonoscopy: [ ] EGD: [x]
            # dilation"); under a heading an item after a box is followed by the next box with no colon.
            labelled = False
            for (_, previous_end, _), (s, _, _) in zip(boxes, boxes[1:]):
                at = _BOX_RUN_GAP.match(text, previous_end, hi).end()
                index = bisect.bisect_left(items, (at, -1))
                if index < len(items) and items[index][0] == at and _LABEL_COLON.fullmatch(
                        text, _label_end(text, items, index), s):
                    labelled = True
                    break
            an.memo[key] = 'lead' if followed and (by_service or by_label) and not labelled else 'trail'
    return an.memo[key]


def _merged(spans: list) -> list:
    """(start, end) spans sorted, overlapping ones merged."""
    merged: list = []
    for s, e in sorted(spans):
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _label_end(text: str, items: list, index: int) -> int:
    """The end of the label that starts with items[index]: the items written on to it, joined by spaces, hyphens,
    '/', ',', '&', '+', brackets, 'and' or 'or'."""
    end = items[index][1]
    for s, e in items[index + 1:]:
        if s < end or not _LABEL_JOINER.fullmatch(text, end, s):
            break
        end = e
    return end


def _run_state(run: list) -> str:
    """The state of boxes written next to each other for one item: 'unknown' when one cannot be read, 'mixed'
    when they disagree."""
    states = {state for _, _, state in run}
    if 'unread' in states:
        return 'unknown'
    return states.pop() if len(states) == 1 else 'mixed'


def _box_state(an: Analysis, start: int, end: int) -> Optional[str]:
    """The state of the box(es) that govern the item at [start, end): 'off', 'on', 'mixed' (boxes for the item that
    disagree), 'unknown' (a box this reader cannot read), or None when no box governs it. A box governs items on its
    own line or cell (_box_segment), within BOX_REACH of it, before or after them (_box_orientation):
    - boxes lead ("[ ] Biopsy [x] Cold snare polypectomy", "( ) Biopsy", "Checklist: [ ] Biopsy.",
      "Colonoscopy: [ ] biopsy [x] cold snare"): the boxes nearest before the item (or inside the passage) govern it;
    - boxes trail ("Biopsy | [ ]", "Biopsy: [ ]", "Biopsy [ ]", "Biopsy/polypectomy | [ ]", "Biopsy taken: [ ] Yes
      [x] No"): the boxes after the item's label, before the next item, govern every item the label names; a
      yes/no pair there is read by the option it marks.
    Boxes written next to each other with nothing but spaces between them are one item's: when they disagree, the
    item is 'mixed'."""
    key = ('box', start, end)
    if key not in an.memo:
        text, span_end = an.text, max(end, start + 1)
        reach_lo, reach_hi = max(0, start - BOX_REACH), min(len(text), span_end + BOX_REACH)
        line_lo, line_hi = text.rfind('\n', reach_lo, start) + 1 or reach_lo, text.find('\n', end, reach_hi)
        line_hi = reach_hi if line_hi < 0 else line_hi
        result = None
        if (_BOX.search(text, line_lo, line_hi) or _BOX_UNREAD.search(text, line_lo, line_hi)
                or _BOX_RADIO.search(text, line_lo, line_hi)):  # else no box is near
            seg_lo, seg_hi, lo, hi = _box_segment(an, start, end)
            items, boxes = _box_tokens(an, lo, hi)
            # an item's orientation is its whole segment's; any other passage's is read where it stands
            is_item = any(s <= start and span_end <= e for s, e in items)
            orientation = (_box_orientation(an, seg_lo, seg_hi) if is_item
                           else _box_orientation(an, lo, hi, (start, span_end)))
            if orientation == 'lead':
                before = [b for b in boxes if b[0] < span_end]
                if before:
                    run = [before[-1]]
                    for b in reversed(before[:-1]):
                        if not _BOX_RUN_GAP.fullmatch(text, b[1], run[0][0]):
                            break
                        run.insert(0, b)
                    result = _run_state(run)
            else:
                items = sorted(set(items) | {(start, end)})
                index = items.index((start, end))
                label_end = max(span_end, _label_end(text, items, index))
                after = next((s for s, _ in items if s >= label_end), hi)
                group = [b for b in boxes if start <= b[0] < after]
                if group:
                    result = _group_state(text, group)
        an.memo[key] = result
    return an.memo[key]


def _unchecked_box(an: Analysis, start: int, end: int) -> bool:
    """Whether the item at [start, end) is governed by an unchecked box in its own line or cell (_box_state)."""
    return _box_state(an, start, end) == 'off'


def _other_names_in(an: Analysis, start: int, end: int) -> tuple:
    names = an.other_names
    low, high = bisect.bisect_left(names, (start, -1)), bisect.bisect_left(names, (end, -1))
    return tuple(name for name in names[low:high] if name[1] <= end)


def _group_state(text: str, group: list) -> Optional[str]:
    """The boxes after an item, up to the next item: the first one (with the boxes written next to it) governs,
    unless they mark yes/no options. Then the item is denied when "No" is checked or "Yes" is not, and held ('mixed')
    when both are checked."""
    first = group[0]
    if _OPTION_BEFORE.search(text, max(0, first[0] - 20), first[0]):
        marks = [(b, _OPTION_BEFORE.search(text, max(0, b[0] - 20), b[0])) for b in group]
    elif _OPTION_AFTER.match(text, first[1]):
        marks = [(b, _OPTION_AFTER.match(text, b[1])) for b in group]
    else:
        run = [first]
        for b in group[1:]:
            if not _BOX_RUN_GAP.fullmatch(text, run[-1][1], b[0]):
                break
            run.append(b)
        return _run_state(run)
    if any(b[2] == 'unread' for b, _ in marks):
        return 'unknown'
    yes = next((b for b, word in marks if word and word.group('yes')), None)
    no = next((b for b, word in marks if word and word.group('no')), None)
    if no is not None and no[2] == 'on' and yes is not None and yes[2] == 'on':
        return 'mixed'  # both options marked: the boxes for the item disagree (structure:15)
    if no is not None and no[2] == 'on':
        return 'off'
    if yes is not None:
        return yes[2]
    return None


# A form line whose whole value says its box is off ("Biopsy: not checked", "Extent reached: no option
# selected"; extraction writes PDF form fields so): it denies the item its label names.
_STATE_OFF = re.compile(r'[^:\n]{1,120}:[ \t]*(?:not[ \t]+checked|unchecked|no[ \t]+option[ \t]+selected)[ \t.]*', re.A | re.I)


def _unchecked_state(an: Analysis, start: int, end: int) -> bool:
    """Whether [start, end) lies on one line that is a form line whose value is off (looked for within BOX_REACH
    of the span; a longer line never matches: its label is at most 120 characters), on a line of a '[PDF form fields
    on page N]' block that denies its item, or in the printed line or cell such a line names on its page
    (_form_fields)."""
    text = an.text
    if text.find('\n', start, end) >= 0:
        return False
    before = text.rfind('\n', max(0, start - BOX_REACH), start)
    after = text.find('\n', end, end + BOX_REACH)
    if _STATE_OFF.fullmatch(text, before + 1, len(text) if after < 0 else after):
        return True
    fields = _form_fields(an)
    if _within(fields.denying, fields.denying_starts, start, end):
        return True
    named = _within(fields.named, fields.named_starts, start, end)
    return named is not None and named.state == 'off' and named.exact


# --- form-field blocks: a field line reaches the printed label it names ----------------------------------------
# Extraction writes a PDF page's form fields after its text (studio/ingest/pdfannots.py). A line of that block whose
# value denies its item - an unchecked box, no option selected, a selected "No", "None", "Not done" or "Not
# performed" - negates the printed line or table cell on the same page whose words equal its label (ignoring case,
# whitespace, a colon and list markers or boxes around it); when it names none, the page's items are held.
FORM_HEADER = re.compile(r'^[ \t]*\[PDF (form fields|annotation text) on page (\d+)\][ \t]*$', re.A | re.M)
_FIELD_DENIED = re.compile(r'(?P<label>[^\n]{1,120}?):[ \t]*(?:not[ \t]+checked|unchecked|no[ \t]+option[ \t]+selected'
                           r'|no|none|not[ \t]+done|not[ \t]+performed)[ \t.]*', re.A | re.I)
_FIELD_CHECKED = re.compile(r'(?P<label>[^\n]{1,120}?):[ \t]*(?:checked|yes)[ \t.]*', re.A | re.I)
_BLANK_LINE = re.compile(r'\n[ \t]*\n')
_LEADING_MARK = re.compile(r'(?:[-*\u2022\u00b7\u25aa\u25e6\u25cf\u2023\u2043\u2013\u2014]|\(?\d{1,3}[.)]|\(?[a-z][.)]'
                           r'(?=\s)|' + _BOX_TEXT + '|' + _BOX_UNREAD.pattern + r')\s*', re.I)
_TRAILING_BOX = re.compile(r'(?:' + _BOX_TEXT + '|' + _BOX_UNREAD.pattern + r')$')
FIELD_LABEL_CHARS = 200  # a printed line or cell longer than this never equals a field's label (bounds the work)
FIELD_UNTIED = "uncertain: the form field '{}' says its item was not done, and no printed line on its page names it"
FIELD_PAGE = ("uncertain: the form field '{}' says this item was not done, but the page it is on cannot be told from "
              "the pages before it")


@dataclass(frozen=True)
class _Named:
    start: int
    end: int
    state: str  # 'off' (a denying field line names it) | 'on' (a checked one) | 'mixed'
    exact: bool  # its page's printed text is known exactly
    line: str  # the field line, as written


@dataclass(frozen=True)
class _FieldPage:
    start: int  # the page's printed text, as far as it can be told: from the end of the previous block
    end: int  # the end of the page's form-field block
    unmatched: str  # the first denying field line whose label names nothing printed on the page ('' for none)


@dataclass(frozen=True)
class _Fields:
    denying: tuple  # _Named spans of the denying field lines themselves, sorted
    named: tuple  # _Named printed lines and cells, sorted
    pages: tuple  # _FieldPage of each form-field block with an unmatched denying line, sorted
    denying_starts: tuple = ()
    named_starts: tuple = ()
    page_starts: tuple = ()


def _label_key(raw: str) -> str:
    """A label or a printed line as compared: lower case, single spaces, without a colon or the list markers and
    boxes around it."""
    text = raw.strip().lower()
    while True:
        mark = _LEADING_MARK.match(text)
        if not mark or not mark.end():
            break
        text = text[mark.end():]
    while True:
        text = text.rstrip()
        if text.endswith(':'):
            text = text[:-1]
            continue
        tail = _TRAILING_BOX.search(text, max(0, len(text) - 12))
        if not tail or tail.start() == 0:
            break
        text = text[:tail.start()]
    return ' '.join(text.split())


def _form_fields(an: Analysis) -> _Fields:
    """The '[PDF form fields on page N]' blocks of the text, read once: their denying lines, the printed lines and
    cells their labels name on their page, and the pages with a denying line that names none. A page's printed text
    runs from the end of the previous page's block to its own block; it is known exactly when that previous block is
    the previous page's (or there is none before page 1), else it may hold earlier pages too, and a line it names is
    held instead of negated."""
    key = ('form-fields',)
    if key not in an.memo:
        text = an.text
        headers = list(FORM_HEADER.finditer(text))
        denying, named, pages = [], [], []
        previous_end, previous_page = 0, 0
        for i, header in enumerate(headers):
            limit = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            blank = _BLANK_LINE.search(text, header.end(), limit)
            block_end = blank.start() if blank else limit
            page = int(header.group(2))
            if header.group(1) == 'form fields':
                exact = page == previous_page + 1
                labels: dict = {}
                for line in re.finditer(r'[^\n]+', text[header.end():block_end]):
                    words = line.group(0)
                    at = header.end() + line.start()
                    denied = _FIELD_DENIED.fullmatch(words)
                    checked = None if denied else _FIELD_CHECKED.fullmatch(words)
                    if denied:
                        denying.append(_Named(at, at + len(words), 'off', exact, words.strip()))
                    if denied or checked:
                        label = _label_key((denied or checked).group('label'))
                        state = 'off' if denied else 'on'
                        previous = labels.get(label)
                        labels[label] = (state if previous is None or previous[0] == state else 'mixed',
                                         previous[1] if previous else words.strip())
                found = set()
                if labels:
                    for line in re.finditer(r'[^\n]+', text[previous_end:header.start()]):
                        at = previous_end + line.start()
                        cells = line.group(0).split(' | ')
                        offset = 0
                        for cell in cells:
                            stripped = cell.strip()
                            if stripped and len(stripped) <= FIELD_LABEL_CHARS:
                                label = _label_key(stripped)
                                if label in labels:
                                    begin = at + offset + (len(cell) - len(cell.lstrip()))
                                    named.append(_Named(begin, begin + len(stripped), labels[label][0], exact,
                                                        labels[label][1]))
                                    found.add(label)
                            offset += len(cell) + 3
                unmatched = next((line for label, (state, line) in labels.items() if state != 'on' and label not in found),
                                 '')
                if unmatched:
                    pages.append(_FieldPage(previous_end, block_end, unmatched))
            previous_end, previous_page = block_end, page
        denying.sort(key=lambda n: n.start)
        named.sort(key=lambda n: n.start)
        an.memo[key] = _Fields(tuple(denying), tuple(named), tuple(pages), tuple(n.start for n in denying),
                               tuple(n.start for n in named), tuple(p.start for p in pages))
    return an.memo[key]


def _within(spans: tuple, starts: tuple, start: int, end: int):
    """The span of ``spans`` (sorted by ``starts``, not overlapping) that holds [start, end), or None."""
    index = bisect.bisect_right(starts, start) - 1
    if index >= 0 and max(end, start + 1) <= spans[index].end:
        return spans[index]
    return None


def _box_reading(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """What the check boxes and form-field lines say of [start, end), or None when they say nothing: negated by an
    unchecked box or a denying field line (UNCHECKED); held when its boxes disagree, when a box cannot be read, when
    a field line names it on a page that cannot be bounded, or when its page has a denying field line that names no
    printed item (and its own reading has no explicit performance cue and no checked box of its own)."""
    state = _box_state(an, start, end)
    fields = _form_fields(an)
    named = _within(fields.named, fields.named_starts, start, end) if an.text.find('\n', start, end) < 0 else None
    if state == 'unknown':
        return Reading('uncertain', (BOX_UNREAD,), 'cue', doubt=True)
    if state == 'mixed' or (named is not None and (named.state == 'mixed' or state not in (None, named.state))):
        return Reading('uncertain', (BOXES_DISAGREE,), 'cue', doubt=True)
    if state == 'off' or _unchecked_state(an, start, end):
        return Reading('negated', (UNCHECKED,), 'cue')
    if named is not None and named.state == 'off':
        return Reading('uncertain', (FIELD_PAGE.format(named.line),), 'cue', doubt=True)
    if state == 'on':
        return None
    pages = fields.pages
    index = bisect.bisect_right(fields.page_starts, start) - 1
    if index < 0 or start >= pages[index].end or not _names_an_item(an, start, end):
        return None
    cue = _cue_reading(an, start, end)
    if cue is not None or _default_reading(an, start, end).status not in ('performed', 'uncertain'):
        return None
    return Reading('uncertain', (FIELD_UNTIED.format(pages[index].unmatched),), 'cue', doubt=True)


def _names_an_item(an: Analysis, start: int, end: int) -> bool:
    end = max(end, start + 1)
    return an.touches_service(start, end) or any(_overlaps(s, e, start, end)
                                                  for s, e in _other_names_in(an, start - OTHER_NAME_REACH,
                                                                              end + OTHER_NAME_REACH))


BOX_HOLDS = (BOXES_DISAGREE, BOX_UNREAD, FIELD_UNTIED.split("'")[0])  # the cues of the holds above


# The line above ends in a complete answer or refusal of its own: a field answered by a bare denial ("Schatzki ring
# present: no", "Tattoo placed today: no") or a refusal verb with nothing after it ("the patient declined").
_ANSWER_AT_LINE_END = re.compile(r'(?:[:?=|][ \t]*(?:no|none|n|not[ \t]+(?:done|performed))'
                                 r'|\b(?:declined|declines|refused|refuses))[ \t.]*$', re.A | re.I)


def _denied_from_the_line_above(an: Analysis, start: int, end: int) -> Optional[str]:
    """A cue when a negation reaches [start, end) only because its sentence was joined across a line break after a
    complete answer or refusal (_ANSWER_AT_LINE_END) on the line above, and the span's own line has no denial
    ("Schatzki ring present: no" then "biopsies were taken ...", "the patient declined" then "Colonoscopy with cold
    snare polypectomy ..."; round 4 structure:2 and structure:3). Whose answer it is cannot be read, so it holds rather
    than negates. Cut prose ("Comment: because of time constraints, no" then "EUS ... was performed today.") is a
    wrapped sentence and stays negated. Bounded by CLAUSE_REACH."""
    text = an.text
    ss, _ = an.lay.sentence_for(start, end)
    ls = text.rfind('\n', 0, start) + 1
    if ls <= ss:
        return None
    le = text.find('\n', end)
    le = len(text) if le < 0 else le
    if cues.DOUBT_TOKEN.search(text, max(ls, start - CLAUSE_REACH), min(le, end + CLAUSE_REACH)):
        return None
    above = text[max(ss, ls - 1 - CLAUSE_REACH):ls - 1]
    answer = _ANSWER_AT_LINE_END.search(above)
    if answer is None:
        return None
    return f"uncertain: the line above it ends in an answer of its own ('{answer.group(0).strip(' :?=|.')}')"


_DEFERRAL_CUE = re.compile(r"'(?:defer|defers|deferring|deferral|postpone|postpones|postponing)' in its clause$",
                           re.A | re.I)


def _box_checked_option(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """A hold for the status option at [start, end) that its own box reading left unchecked ("[ ] Aborted") when its
    line selects a denying option, itself or another ("[ ] Completed [x] Cancelled [ ] Aborted", "Completed ☐ |
    Aborted ☒"): a checked, disagreeing or unread box on a denying option makes the line a statement (routing:0), held
    and never read as that status (_box_option_state). None when every denying option of the line is unchecked. The
    line is read within BOX_REACH of the option."""
    text = an.text
    lo = max(text.rfind('\n', max(0, start - BOX_REACH), start) + 1, start - BOX_REACH)
    newline = text.find('\n', end, end + BOX_REACH)
    hi = min(len(text), end + BOX_REACH) if newline < 0 else newline
    options = _box_denying_options(an, lo, hi)
    words = options + [m.span() for m in _BOX_DONE_OPTION.finditer(text, lo, hi)]
    for option in options:
        if _box_option_state(an, lo, hi, option, words) not in (None, 'off'):
            return Reading('uncertain', (BOX_STATUS_OPTION.format(' '.join(text[lo:hi].split())),), 'cue', doubt=True)
    return None


# A status question answered with a denial, on its own line: the reference, after an optional list marker, "was the"
# and the word for the procedure; then ':', '?', '=', '|', a dash, a tab or two spaces; then "No", "None", "N", "Not
# done" or "Not performed" and nothing else ("Procedure cancelled: No", "Was the procedure cancelled? No", "Procedure
# aborted  No", a table row "Procedure cancelled | No"; never "Procedure cancelled, no sedation given.").
_BOX_ANSWER_LEAD = re.compile(r'[ \t]*(?:[-*•][ \t]*|\d{1,2}[.)][ \t]*)?(?:(?:was|is|has|had)[ \t]+)?(?:(?:the|this)[ \t]+)?'
                              r'(?:(?:procedure|exam|examination|study|endoscopy|case)[ \t]+)?', re.I)
_BOX_ANSWER_TAIL = re.compile(r'[ \t]*(?:[:?=|–—-]|\t| {2,})[ \t]*(?:no|none|n|not[ \t]+done|not[ \t]+performed)[ \t.]*',
                              re.I)
BOX_ANSWER_REACH = 80  # how far a status question's lead or answer is read from its reference (bounds the work)


def _box_status_answer(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """A hold for the status reference at [start, end) when its own line is a status question answered with a denial
    (structure:13): "Procedure cancelled: No" says the procedure was not cancelled, so it is never read as a
    cancellation; whatever else it means is left for review."""
    text = an.text
    newline = text.rfind('\n', max(0, start - BOX_ANSWER_REACH), start)
    if newline < 0 and start > BOX_ANSWER_REACH:
        return None
    line_end = text.find('\n', end, end + BOX_ANSWER_REACH + 1)
    if line_end < 0:
        if end + BOX_ANSWER_REACH < len(text):
            return None
        line_end = len(text)
    if not (_BOX_ANSWER_LEAD.fullmatch(text, newline + 1, start) and _BOX_ANSWER_TAIL.fullmatch(text, end, line_end)):
        return None
    return Reading('uncertain', (BOX_STATUS_ANSWER.format(text[newline + 1:line_end].strip()),), 'cue', doubt=True)


def _generic_reading(an: Analysis, start: int, end: int) -> Reading:
    """The reading of [start, end) from its clause cues or its section. A performed reading
    of a procedure (not of E/M documentation) becomes an uncertain doubt when an unresolved
    negation sits in its clause, or when only its section speaks for a named service whose
    words are not those of a procedure description ("Colonoscopy declined by patient")."""
    key = ('reading', start, end)
    if key not in an.memo:
        boxed = _box_reading(an, start, end)  # check boxes and form-field lines (see _box_reading)
        if boxed is not None:
            an.memo[key] = boxed
    if key not in an.memo:
        reading = _cue_reading(an, start, end) or _default_reading(an, start, end)
        if reading.status == 'negated':
            joined = _denied_from_the_line_above(an, start, end)
            if joined:
                # a doubt, so the family's section evidence elsewhere cannot turn the lost negation into performed
                reading = Reading('uncertain', (joined,) + reading.cues, 'cue', doubt=True)
        if reading.cues == (SILENT,):
            # A silent mention whose clause puts the service off ("we decided to defer EUS"): a doubt, not silence,
            # so it contradicts the section evidence of the procedure line (round 4 release:10).
            doubt = _doubt(an, start, end)
            if doubt and _DEFERRAL_CUE.search(doubt):
                reading = Reading('uncertain', (doubt,), 'cue', doubt=True)
        if reading.status == 'performed' and not reading.cues[0].endswith(EM_DOCUMENTATION):
            doubt = (reading.basis == 'section' and _silent_section(an, start, end)) or _doubt(an, start, end)
            if doubt:
                reading = Reading('uncertain', (doubt,) + reading.cues, reading.basis, doubt=True)
        an.memo[key] = reading
    return an.memo[key]


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
    if reading.status in NOT_TODAY and an.touches_service(start, end) and any(
            m.kind == 'em-visit' and _overlaps(m.start, m.end, start, max(end, start + 1)) for m in an.em):
        # A visit statement that names another service ("Follow-up office visit to discuss the EGD performed last
        # week") takes that service's status from its time; the visit itself is today's, so it holds, never
        # excludes (round 4 routing:4).
        return Reading('uncertain', (f'uncertain: the visit statement names another service, read {reading.status}',)
                       + reading.cues, reading.basis)
    return reading


def _adjusted(reading: Reading, adjustment: Optional[tuple[str, str]]) -> Reading:
    """A performed reading takes the document-level judgement of its family's service when
    that judgement is cancelled, not completed, or uncertain (see _adjustment): never planned,
    historical or negated, which other mentions say of other encounters or of other passages."""
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


def _first_clauses_in(an: Analysis, s: int, e: int, limit: int) -> list[tuple[int, int]]:
    """Exactly ``_clauses_in(an, s, e)[:limit]``, without listing the clauses past the first ``limit`` (round 4
    routing:14: a 200 KB semicolon list made _later_denial list every later clause for every mention)."""
    clauses = an.lay.clauses
    found = []
    for i in range(bisect.bisect_left(clauses, (s, -1)), len(clauses)):
        c = clauses[i]
        if c[0] >= e or len(found) >= limit:
            break
        if c[1] <= e:
            found.append(c)
    return found


def _last_clauses_in(an: Analysis, s: int, e: int, limit: int) -> list[tuple[int, int]]:
    """Exactly ``_clauses_in(an, s, e)[-limit:]``, walking back from ``e`` (round 4 routing:10: a 280 KB clause chain
    made _continues_another_procedure list every earlier clause for every fact)."""
    clauses = an.lay.clauses
    low = bisect.bisect_left(clauses, (s, -1))
    found = []
    for i in range(bisect.bisect_left(clauses, (e, -1)) - 1, low - 1, -1):
        if len(found) >= limit:
            break
        if clauses[i][1] <= e:
            found.append(clauses[i])
    found.reverse()
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
    part of a performed or incomplete service. A landmark is reached only from a
    reading with no unresolved negation; a denied advancement ("it was not advanced
    to the cecum") is blocked, never reached."""
    text = an.text
    reached, blocked = [], []
    for s, e in sentences:
        for cs, ce in _clauses_in(an, s, e):
            for label, depth, pattern in table:
                for m in pattern.finditer(text, cs, ce):
                    if _about_another_procedure(an, m.start(), m.end()):
                        continue
                    reading = _generic_reading(an, m.start(), m.end())
                    status = reading.status
                    # the reading before an unresolved negation was found: blocked is read from it
                    base = 'performed' if reading.cues[0].startswith((DOUBT_PREFIX, SILENT_SECTION_PREFIX)) else status
                    ws, we = an.lay.window((cs, ce), m.start(), m.end(), CLAUSE_REACH)
                    pre, post = text[ws:m.start()], text[m.end():we]
                    hit = (depth, label, _span(text, cs, ce))
                    if status in ('performed', 'incomplete') and cues.REACHED_BEYOND.search(pre):
                        reached.append(hit)
                    elif base in ('performed', 'incomplete', 'negated') and (
                            cues.NOT_REACHED_BEFORE.search(pre) or cues.NOT_REACHED_AFTER.search(post)):
                        blocked.append(hit)
                    elif status in ('performed', 'incomplete') and (
                            cues.REACHED_BEFORE.search(pre) or cues.REACHED_AFTER.search(post)
                            or (_reached_label(an, ws, m.start()) and _plain_tail(an, m.end(), we))
                            or _straight_after_service(an, ws, m.start())):
                        reached.append(hit)
                    elif (_answers_silently(an, reading, m.start(), m.end()) and _reached_label(an, ws, m.start())
                          and _plain_tail(an, m.end(), we)):
                        reached.append(hit)  # "Furthest extent reached: cecum." answered in an addendum
    return reached, blocked


def _answers_silently(an: Analysis, reading: Reading, start: int, end: int) -> bool:
    """Whether the value of an extent label at [start, end) states the extent reached although its section does not
    speak for it: its section is an 'other' one (the product's addendum block, an unrecognised label, a form block,
    the preparation or complications), its reading is the silent default (no cue at all: nothing hedged, planned,
    historical or denied), and no unresolved negation is in its clause (the doubt a positive section would find:
    "Extent: cecum not reached."). An addendum answering "confirm the furthest extent reached" is read so; the label
    itself still has to pass _reached_label (an aim never does). An indication, an assessment or an impression can
    tell prior work-up, so a label there is still read only when its own wording states performance."""
    section = an.lay.section_at(start)
    return (reading.basis == 'default' and reading.cues == (SILENT,) and section.kind == 'other'
            and section.label in _ANSWERING_SECTIONS and not _doubt(an, start, end))


# The 'other' sections that speak for this report's own procedure (round 4 routing:2): the product's addendum block,
# the PDF form-field and annotation blocks, and the report's own preparation and complications. Any other unrecognised
# label ("Outside records:", "Referral information:") may tell another facility's procedure, so a label answered there
# is never read as today's extent.
_ANSWERING_SECTIONS = frozenset(('addendum', 'pdf form fields', 'pdf annotation text', 'bowel preparation',
                                 'bowel prep', 'preparation', 'prep', 'quality of preparation', 'complications'))
_EXTENT_TAIL_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+", re.A)
_VALUE_END = re.compile(r'[.;\n]')


def _plain_tail(an: Analysis, end: int, we: int) -> bool:
    """Whether the value after an extent label's landmark adds nothing but punctuation and cues.EXTENT_TAIL words,
    read to the value's sentence or line end (round 4 routing:9, release:3: "Extent: cecum (intended)." and "cecum
    (intended; not reached)" name no extent reached). A closed list: any other word leaves the extent unread."""
    stop = _VALUE_END.search(an.text, end, we)
    tail = an.text[end:stop.start() if stop else we]
    return all(word.lower() in cues.EXTENT_TAIL for word in _EXTENT_TAIL_WORD.findall(tail))


# Where the words that lead an extent label start: after the last separator before it in its clause.
_LEAD_BREAK = re.compile(r'[,;:|(\[\u2013\u2014]|\s-\s', re.A)
# A list marker or a bullet, which leads no label ("1) Extent: cecum", "- Extent: cecum").
_LIST_MARK = re.compile(r'(?:\d{1,2}[.)]?|[A-Za-z][.)]|[^\w]+)', re.A)


def _reached_label(an: Analysis, lo: int, pos: int) -> bool:
    """Whether an extent label ends right before the landmark at ``pos`` ("Extent reached: ", "The furthest extent
    reached was the ") and names the extent reached (_label_lead_plain), never an aim ("Intended extent: ")."""
    label = cues.EXTENT_LABEL_BEFORE.search(an.text, lo, pos)
    return bool(label) and _label_lead_plain(an, lo, label.start())


def _label_lead_plain(an: Analysis, lo: int, start: int) -> bool:
    """Whether only words that leave an extent label the extent reached (cues.EXTENT_LEAD), a service name, a list
    marker or a bullet stand between the label at ``start`` and the last separator before it (or ``lo``, the start
    of its clause). A word of aim ("Intended", "Expected", "Target", "Goal", "Planned") or any other word does not:
    the label then names no extent reached. Only that stretch is read (bounded by the clause window)."""
    breaks = [m.end() for m in _LEAD_BREAK.finditer(an.text, lo, start)]
    for word in _masked(an, breaks[-1] if breaks else lo, start).split():
        lowered = word.lower()
        if lowered not in cues.EXTENT_LEAD and lowered != cues.SERVICE_TOKEN and not _LIST_MARK.fullmatch(word):
            return False
    return True


def _straight_after_service(an: Analysis, lo: int, pos: int) -> bool:
    """Whether ``pos`` follows a service name read as performed with only "to (the)" between them, the
    shorthand of an extent ("Colonoscopy to cecum", "Colonoscopy to TI", "EGD to D2")."""
    named = an.services_in(lo, pos)
    if not named:
        return False
    service = named[-1]
    return bool(cues.SERVICE_TO_GAP.fullmatch(an.text, service.end, pos)) \
        and _generic_reading(an, service.start, service.end).status == 'performed'


# Between a flexible sigmoidoscopy and its "to 30 cm": nothing, an abbreviation, or "was performed".
_CM_GAP = re.compile(r'\s*(?:\(\s*[A-Z]{2,6}\s*\)\s*)?(?:(?:was|were)\s+(?:performed|done|completed)\s*)?', re.A | re.I)


def _cm_after_flex_sig(an: Analysis, lo: int, pos: int) -> bool:
    """Whether the depth at ``pos`` ("to 30 cm") is the shorthand extent of a flexible sigmoidoscopy read as
    performed and named just before it ("Flexible sigmoidoscopy to 30 cm", "FS was performed to 35 cm")."""
    named = [m for m in an.services_in(lo, pos) if m.family == 'gi.flex_sig']
    if not named:
        return False
    service = named[-1]
    return bool(_CM_GAP.fullmatch(an.text, service.end, pos)) \
        and _generic_reading(an, service.start, service.end).status == 'performed'


_REFERENCE_PATTERNS = ((('cancelled', cues.PROCEDURE_CANCELLED), ('negated', cues.PROCEDURE_NOT_PERFORMED),
                        ('incomplete', cues.PROCEDURE_INCOMPLETE), (None, cues.ABORTED))
                       + tuple(('incomplete', pattern) for _, pattern in cues.INCOMPLETE_CLAUSE))


# What a colonoscopy or an EGD may leave undone and still be complete: intubating the terminal ileum (or
# traversing the ileocecal valve to it) and retroflexion (cues.OTHER_ACT_NEGATION treats them as other acts).
_SUB_ACT = re.compile(r'\b(?:retroflex\w*|terminal\s+ile(?:um|al)|ile(?:um|al)\s+intubation|ileum|ileal|TI|'
                      r'ileo-?cecal\s+valve)\b', re.A | re.I)
_SUB_ACT_PLACE = re.compile(r'\bterminal\s+ileum\b|\bneo-?terminal\s+ileum\b|\bTI\b|\bileo-?cecal\s+valve\b', re.A | re.I)


def _reached_expected_depth(an: Analysis, attributed: list[Optional[str]], family: str) -> bool:
    """Whether the family's own text documents its expected extent reached: the cecum for a colonoscopy,
    the depth the named upper endoscopy calls for for an EGD."""
    key = ('reached-depth', family)
    if key not in an.memo:
        table, expected = ((cues.LOWER_LANDMARKS, cues.CECUM_DEPTH) if family == 'gi.colonoscopy'
                           else (cues.UPPER_LANDMARKS, _expected_upper_depth(an)))
        reached, _ = _landmarks(an, _family_sentences(an, attributed, family), table)
        an.memo[key] = max((depth for depth, _, _ in reached), default=0) >= expected
    return an.memo[key]


def _only_a_sub_act(an: Analysis, attributed: list[Optional[str]], family: str, s: int, e: int) -> bool:
    """Whether the sentence [s, e), which says something was not completed or was aborted, speaks only of
    a sub-act (the terminal ileum, the ileocecal valve, retroflexion) of a procedure that reached its
    expected extent: then it is no incompleteness of the procedure. A landmark short of that extent in the
    same sentence ("could not be advanced beyond the splenic flexure") keeps it the procedure's."""
    if family not in ('gi.colonoscopy', 'gi.egd') or not _SUB_ACT.search(an.text, s, e):
        return False
    table = cues.LOWER_LANDMARKS if family == 'gi.colonoscopy' else cues.UPPER_LANDMARKS
    for _, _, pattern in table:
        for m in pattern.finditer(an.text, s, e):
            if not _SUB_ACT_PLACE.fullmatch(m.group(0)):
                return False
    return _reached_expected_depth(an, attributed, family)


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
                    context = _generic_reading(an, m.start(), m.end())
                    if context.status in ('historical', 'planned'):
                        continue
                    if context.cues == (UNCHECKED,):  # an unchecked status option ("Procedure cancelled | [ ]") ...
                        selected = _box_checked_option(an, m.start(), m.end())
                        if selected is not None:  # ... on a line that selects another denying option: held (routing:0)
                            found[Mention(family, m.start(), m.end(), 'reference', m.group(0))] = selected
                        continue  # ... is otherwise not a statement
                    if context.cues and context.cues[0].startswith(BOX_HOLDS):
                        found[Mention(family, m.start(), m.end(), 'reference', m.group(0))] = context
                        continue  # its box or form field cannot be read: held, never cancelled
                    answered = _box_status_answer(an, m.start(), m.end())
                    if answered is not None:  # "Procedure cancelled: No": held, never cancelled (structure:13)
                        found[Mention(family, m.start(), m.end(), 'reference', m.group(0))] = answered
                        continue
                    if family == 'gi.ercp' and 'cannulat' in m.group(0).lower() and _pancreatic_avoidance(an, m.start()):
                        continue
                    if status in ('incomplete', None) and _only_a_sub_act(an, attributed, family, s, e):
                        continue  # "The terminal ileum was not intubated" after the cecum was reached
                    mention = Mention(family, m.start(), m.end(), 'reference', m.group(0))
                    if status:
                        found[mention] = Reading(status, (f'{status}: {m.group(0)}',), 'cue')
                    else:  # "aborted": cancelled before insertion, incomplete after, otherwise held as a doubt
                        found[mention] = Reading(context.status, context.cues, 'cue', doubt=context.doubt)
    return {m: found[m] for m in _without_overlaps(list(found))}


# --- family facts -------------------------------------------------------------------

def _interventions(an: Analysis, attributed: list[Optional[str]], family: str) -> Optional[Fact]:
    found = []
    for iv in an.interventions:
        index = _sentence_index(an, iv.start)
        if family not in iv.families or index < 0 or attributed[index] != family:
            continue
        if _generic_reading(an, iv.start, iv.end).status == 'performed' \
                and not _about_another_procedure(an, iv.start, iv.end):
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


# How deep an upper endoscopy is expected to reach (UPPER_LANDMARKS depth): an EGD the
# duodenum (bulb or beyond), an enteroscopy beyond the second part, an esophagoscopy the
# esophagus. The colon's counterpart is CECUM_DEPTH.
_ESOPHAGOSCOPY = re.compile(r'\besophagoscop', re.A | re.I)
_ENTEROSCOPY = re.compile(r'\benteroscop', re.A | re.I)
EGD_DEPTH, ENTEROSCOPY_DEPTH, ESOPHAGOSCOPY_DEPTH = 3, 6, 1


def _expected_upper_depth(an: Analysis) -> int:
    """The depth the named upper endoscopies call for: the deepest any of them needs among
    those read as performed or incomplete (all of them when none is)."""
    named = [m for m in an.services if m.family == 'gi.egd']
    done = [m for m in named if _generic_reading(an, m.start, m.end).status in ('performed', 'incomplete')]
    depths = [ESOPHAGOSCOPY_DEPTH if _ESOPHAGOSCOPY.match(m.label) else
              ENTEROSCOPY_DEPTH if _ENTEROSCOPY.search(m.label) else EGD_DEPTH for m in (done or named)]
    return max(depths, default=EGD_DEPTH)


def _upper_extent(an: Analysis, sentences, incomplete: bool) -> Optional[Fact]:
    """The deepest landmark reached; incomplete when the service is documented as incomplete
    or that landmark lies short of the depth the named procedure calls for."""
    reached, blocked = _landmarks(an, sentences, cues.UPPER_LANDMARKS)
    if not reached:
        return None
    depth, label, span = max(reached, key=lambda hit: hit[0])
    if incomplete or depth < _expected_upper_depth(an):
        evidence = [span] + [b[2] for b in blocked if b[0] > depth]
        return Fact('extent', f'incomplete: {label}', 'document', tuple(dict.fromkeys(evidence)))
    return Fact('extent', label, 'document', (span,))


def _flex_sig_extent(an: Analysis, sentences) -> Optional[Fact]:
    text = an.text
    found = []
    for s, e in sentences:
        for cs, ce in _clauses_in(an, s, e):
            advanced = bool(cues.ADVANCED.search(text, cs, ce))
            hits = [m for m in cues.CENTIMETERS.finditer(text, cs, ce)
                    if advanced or _cm_after_flex_sig(an, cs, m.start())]
            # "Depth of insertion: 30 cm", never an aim ("Intended depth of insertion: 60 cm"); a label is also read
            # where it answers silently (_answers_silently: "Depth of insertion: 40 cm." in an addendum)
            labels = [m for m in cues.EXTENT_CM.finditer(text, cs, ce)
                      if _label_lead_plain(an, an.lay.window((cs, ce), m.start(), m.end(), CLAUSE_REACH)[0], m.start())]
            for m in hits + labels:
                reading = _generic_reading(an, m.start(), m.end())
                if (reading.status in ('performed', 'incomplete')
                        or (m in labels and _answers_silently(an, reading, m.start(), m.end()))) \
                        and not _about_another_procedure(an, m.start(), m.end()):
                    found.append((f"{int(m.group('cm'))} cm", _span(text, cs, ce)))
    if found:
        return _fact('extent', found)
    reached, _ = _landmarks(an, sentences, cues.LOWER_LANDMARKS)
    if not reached:
        return None
    _, label, span = max(reached, key=lambda hit: hit[0])
    return Fact('extent', label, 'document', (span,))


NOT_TODAY = ('planned', 'historical', 'cancelled', 'negated')
# A counted polyp phrase never comes from a denial ("not a single polyp", "No polyps ...") or a
# history ("a history of polyps") in its own clause.
_POLYP_DENIED = re.compile(r"\b(?:no|not|none|never|neither|nor|without|history|hx|h/o|prior|previous|previously|"
                           r"s/p|family)\b|n't\b", re.A | re.I)
# A direct denial of an intent word: "not a screening colonoscopy", "non-screening".
_INTENT_DENIED = re.compile(r'\b(?:not|no|non|never)[\s-]+(?:(?:a|an|the)\s+)?$', re.A | re.I)


def _not_today(reading: Reading) -> bool:
    """A reading that says the text is not about a service done at this encounter."""
    return reading.status in NOT_TODAY or reading.doubt


# A service named only to compare with ("Compared with her 2023 colonoscopy, the cecum was reached")
# does not make the rest of its clause about that other procedure.
_COMPARED_WITH = re.compile(r'\b(?:compared\s+(?:with|to)|in\s+comparison\s+(?:with|to)|unlike|than|similar\s+to'
                            r'|as\s+(?:on|in|at|with|during))\s+(?:(?:the|her|his|their|a|an|that|this)\s+)?'
                            r'(?:[\w-]+\s+){0,3}$', re.A | re.I)


def _about_another_procedure(an: Analysis, start: int, end: int) -> bool:
    """Whether the clause holding [start, end) speaks of a procedure not done at this encounter: it
    names a service read as planned, historical, cancelled, denied today or in doubt, and does not
    say today. A fact read there ("On her colonoscopy in 2023 the cecum was reached", "Her prior
    colonoscopy reached the cecum", "EUS with fine-needle biopsy at a later date") is that other
    procedure's, never today's. A negation of earlier encounters ("no prior colonoscopy") and a
    service named only to compare with do not count. Only the clause within CLAUSE_REACH of the
    fact is read, so a long clause naming many services costs no more per fact."""
    key = ('another-procedure', start, end)
    if key not in an.memo:
        an.memo[key] = False
        for clause in an.lay.clauses_for(start, end):
            cs, ce = an.lay.window(clause, start, end, CLAUSE_REACH)  # bounded, like every clause reading
            if cues.TODAY.search(an.text, cs, ce):
                continue
            if _names_another_procedure(an, cs, ce) or _another_exam(an, clause, cs, ce) \
                    or (not an.services_in(cs, ce) and _continues_another_procedure(an, clause)):
                an.memo[key] = True
                break
    return an.memo[key]


# Another examination named without a service name (routing:13): "On a prior exam the cecum was reached", "At her last
# procedure", "Her most recent examination", "Per the outside report", and a clause led by "Previously" (not
# "Previously placed", which tells the time of another act).
_ANOTHER_EXAM = re.compile(r'\b(?:prior|previous|last|index|outside|earlier|preceding|old|most\s+recent)\s+'
                           r'(?:(?:diagnostic|screening|surveillance|endoscopic|colonoscopic|gi|incomplete|complete)\s+)?'
                           r'(?:exam(?:ination)?s?|procedures?|stud(?:y|ies)|scopes?|endoscop(?:y|ies))\b'
                           r'|\bper\s+(?:the\s+)?(?:outside|prior|previous|old|last)\s+(?:reports?|records?)\b', re.A | re.I)
_PREVIOUSLY_LEAD = re.compile(r'[\s,]*previously\b(?![\s,]+\w+(?:ed|en)\b)', re.A | re.I)
_DENIED_BEFORE = re.compile(r'\b(?:no|not|never|without)\s+(?:(?:a|an|the|any)\s+)?$', re.A | re.I)
# The other examination tells the time of the clause only as an adverbial ("On a prior exam ...", "... at her last
# procedure") or as the subject of a verb ("Her most recent examination reached the cecum"), never as an object or a
# modifier ("Prior exam notes were reviewed and the cecum was reached").
_EXAM_LEAD = re.compile(r'\b(?:on|at|during|in|from|by|after|following|according\s+to)\s+(?:(?:a|an|the|her|his|'
                        r'their|this|that|its)\s+)?$', re.A | re.I)
_EXAM_SUBJECT_BEFORE = re.compile(r'[\s,]*(?:(?:a|an|the|her|his|their|this|that|its)\s+)?', re.A | re.I)
_EXAM_VERB_AFTER = re.compile(r'\s+(?:also\s+|then\s+)?(?:was|were|had|has|is|showed|shows|revealed|demonstrated|'
                              r'reached|found|noted|documented|confirmed|identified|visualized|removed|took)\b',
                              re.A | re.I)


def _another_exam(an: Analysis, clause: tuple[int, int], cs: int, ce: int) -> bool:
    """Whether the clause (window [cs, ce)) speaks of another examination without naming its service (see
    _ANOTHER_EXAM), other than one it denies ("no prior exam") or names only to compare with ("as on her prior exam",
    "Compared with her prior exam")."""
    text = an.text
    if clause[0] == cs and _PREVIOUSLY_LEAD.match(text, cs, ce):
        return True
    for m in _ANOTHER_EXAM.finditer(text, cs, ce):
        if _DENIED_BEFORE.search(text, max(cs, m.start() - 20), m.start()) \
                or _COMPARED_WITH.search(text, max(cs, m.start() - 60), m.start()):
            continue
        if m.group(0).lower().startswith('per') or _EXAM_LEAD.search(text, max(cs, m.start() - 30), m.start()) \
                or (_EXAM_SUBJECT_BEFORE.fullmatch(text, clause[0], m.start())
                    and _EXAM_VERB_AFTER.match(text, m.end(), ce)):
            return True
    return False


def _held_for_another_time(reading: Reading) -> bool:
    """A reading held because a time places it on another date (ANOTHER_TIME_PREFIX)."""
    return reading.status == 'uncertain' and any(c.startswith(ANOTHER_TIME_PREFIX) for c in reading.cues)


def _names_another_procedure(an: Analysis, cs: int, ce: int) -> bool:
    """Whether the clause window [cs, ce) names a service read as not done at this encounter - planned, historical,
    cancelled, denied today, in doubt, or held for another time - other than one named only to compare with."""
    for svc in an.services_in(cs, ce):
        reading = _generic_reading(an, svc.start, svc.end)
        if not ((_not_today(reading) or _held_for_another_time(reading)) and not reading.past_negation):
            continue
        if _COMPARED_WITH.search(an.text, max(cs, svc.start - 60), svc.start):
            continue
        return True
    return False


def _continues_another_procedure(an: Analysis, clause: tuple[int, int]) -> bool:
    """Whether a clause that names no service goes on about the procedure of an earlier clause of its sentence: the
    nearest earlier clause (of at most DENIAL_CLAUSES) that names a service names one not done at this encounter, and
    none between says today ("She recently underwent EGD; the endoscope was advanced to the second part of the
    duodenum"). A later clause never speaks for an earlier one ("The cecum was reached; her prior colonoscopy ...")."""
    s, _ = an.lay.sentence_for(*clause)
    for pc in reversed(_last_clauses_in(an, s, clause[0], DENIAL_CLAUSES)):
        ps, pe = an.lay.window(pc, max(pc[0], pc[1] - 1), pc[1], CLAUSE_REACH)
        if cues.TODAY.search(an.text, ps, pe):
            return False
        if an.services_in(ps, pe):
            return _names_another_procedure(an, ps, pe)
    return False


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
                if _POLYP_DENIED.search(text, _clause_at(an, m.start())[0], m.end()) \
                        or _about_another_procedure(an, m.start(), m.end()):
                    continue
                number = m.group('n').lower()
                total += int(number) if number.isdigit() else cues.NUMBER_WORDS[number]
                evidence.append(_span(text, m.start(), m.end()))
        if uncounted:
            return None
        if evidence:
            return Fact('polyp_count', str(total), 'document', tuple(evidence))
    return None


def _intent(an: Analysis, attributed: list[Optional[str]], only_family: bool, today: bool = True) -> Optional[Fact]:
    """Screening, surveillance or diagnostic. For a colonoscopy done at this encounter
    (``today``) it is read only from today's indication and procedure text: never from a plan
    or history, a planned, historical, cancelled or negated clause, a doubt, or a direct
    denial ("This is not a screening colonoscopy"). For a colonoscopy that is only planned,
    the plan may state it."""
    text = an.text
    found = []
    skipped_sections = ('plan', 'history') if today else ('history',)
    skipped = NOT_TODAY if today else ('historical', 'cancelled', 'negated')
    for (s, e), family in zip(an.lay.sentences, attributed):
        kind = an.lay.section_at(s).kind
        if kind in skipped_sections:
            continue
        indication = kind == 'indication'
        clauses = _clauses_in(an, s, e)
        for at, (cs, ce) in enumerate(clauses):
            for m in cues.INTENT.finditer(text, cs, ce):
                reading = _generic_reading(an, m.start(), m.end())
                # a question or a hedge ("Is this a screening colonoscopy?", "unclear whether", "Presumed
                # screening", "Screening, to be confirmed") states no intent; the silent default of an indication does
                hedged = reading.status == 'uncertain' and reading.basis == 'cue'
                if reading.status in skipped or reading.doubt or hedged \
                        or _INTENT_DENIED.search(text, max(cs, m.start() - 40), m.start()) \
                        or _intent_hedged(an, m, (cs, ce), clauses[at + 1] if at + 1 < len(clauses) else None):
                    continue
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


# Hedges that keep an intent word from stating an intent (intent only: the shared uncertain vocabularies decide
# service status and are not widened for it). A presumption right before the intent word ("Presumed screening",
# "Suspected screening colonoscopy"); a confirmation still pending, anywhere in its clause ("Screening (to be
# confirmed with the referring office)", "not yet confirmed", "TBD"); or a state of doubt that closes a clause
# ("Screening colonoscopy, unclear.", "Screening per patient, but unclear."), never one that qualifies another word
# ("likely hemorrhoidal", "family history uncertain because ..."). "per patient", "per referral" and "confirmed
# with ..." are no hedges.
_INTENT_PRESUMED = re.compile(r'\b(?:presum(?:ed|ably|ptive)|suspected|likely|probabl[ey]|possibl[ey]|perhaps|maybe|'
                              r'questionabl[ey]|apparent(?:ly)?|tentative(?:ly)?)[\s,]+(?:(?:a|an|the)\s+)?$',
                              re.A | re.I)
_INTENT_PENDING = re.compile(r'\bto\s+be\s+(?:confirmed|determined|clarified|verified|decided|established)\b'
                             r'|\bnot\s+(?:yet\s+)?(?:confirmed|established|clear|certain|sure)\b'
                             r'|\bpending\s+(?:confirmation|clarification|verification)\b|\b(?:tbc|tbd|unconfirmed)\b',
                             re.A | re.I)
_INTENT_DOUBTED = re.compile(r'\b(?:unclear|uncertain|unsure|undetermined|undecided|questionable)\b'
                             r'(?=\s*(?:[.;,!?)\]]|$|whether\b|if\b))', re.A | re.I)
_CLAUSE_OPENS = re.compile(r'(?:but|however|though|although|whereas|yet)\b', re.A | re.I)


def _intent_hedged(an: Analysis, m: re.Match, clause: tuple[int, int], following: Optional[tuple[int, int]]) -> bool:
    """Whether the intent word at ``m`` is hedged (see _INTENT_PRESUMED): read in its clause (within CLAUSE_REACH)
    and in the next clause of its sentence when that one only qualifies it ("..., but unclear.")."""
    text = an.text
    if _INTENT_PRESUMED.search(text, max(clause[0], m.start() - 40), m.start()):
        return True
    windows = [an.lay.window(clause, m.start(), m.end(), CLAUSE_REACH)]
    if following is not None and _CLAUSE_OPENS.match(text, following[0], following[1]):
        windows.append((following[0], min(following[1], following[0] + 120)))
    return any(_INTENT_PENDING.search(text, lo, hi) or _INTENT_DOUBTED.search(text, lo, hi) for lo, hi in windows)


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
                if _generic_reading(an, m.start(), m.end()).status == 'performed' \
                        and not _about_another_procedure(an, m.start(), m.end()):
                    sampling.append((label, _span(text, m.start(), m.end())))
                    sampled_sentences.append((s, e))

    def eus_not_today(start: int, end: int) -> bool:
        return any(_not_today(_generic_reading(an, svc.start, svc.end))
                   for svc in an.services_in(start, end) if svc.family == 'gi.eus')

    # The target is read only for today's EUS: never from a prior, planned or negated one.
    tiers = [sampled_sentences,
             [(m.end(), an.lay.sentence_for(m.start(), m.end())[1]) for m in cues.EUS_TARGET_PHRASE.finditer(text)
              if not eus_not_today(m.start(), m.end())],
             [(s, e) for s, e in sentences if an.lay.section_at(s).kind == 'indication' and not eus_not_today(s, e)]]
    target = None
    for tier in tiers:
        found = []
        for s, e in tier:
            for template, pattern in cues.EUS_TARGETS:
                for m in pattern.finditer(text, s, e):
                    if _not_today(_generic_reading(an, m.start(), m.end())):
                        continue
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


def _clause_at(an: Analysis, pos: int) -> tuple[int, int]:
    for cs, ce in an.lay.clauses_for(pos, pos + 1):
        if cs <= pos < ce:
            return cs, ce
    return an.lay.sentence_for(pos, pos + 1)


def _biliary_cannulation_succeeded(an: Analysis) -> bool:
    text = an.text
    for m in cues.CANNULATION_SUCCESS.finditer(text):
        cs, ce = _clause_at(an, m.start())
        if cues.BILIARY_SUBJECT.search(text, cs, ce) and _generic_reading(an, m.start(), m.end()).status in (
                'performed', 'incomplete'):
            return True
    return False


def _pancreatic_avoidance(an: Analysis, start: int) -> bool:
    """A "not cannulated" phrase whose subject is the pancreatic duct, in a document that
    documents a successful biliary cannulation: a deliberate choice, not a failed ERCP.
    Without documented biliary success the phrase keeps its fail-closed reading."""
    cs, _ = _clause_at(an, start)
    subject = an.text[cs:start]
    return (bool(cues.PANCREATIC_SUBJECT.search(subject)) and not cues.BILIARY_SUBJECT.search(subject)
            and _biliary_cannulation_succeeded(an))


def _cannulation(an: Analysis, sentences) -> Optional[Fact]:
    """Successful or failed; both documented is a conflict for a reviewer, never a pick."""
    text = an.text
    found = []
    for s, e in sentences:
        for value, pattern, readable in (('successful', cues.CANNULATION_SUCCESS, ('performed', 'incomplete')),
                                         ('failed', cues.CANNULATION_FAILED, ('performed', 'incomplete', 'negated'))):
            for m in pattern.finditer(text, s, e):
                if value == 'failed' and _pancreatic_avoidance(an, m.start()):
                    continue
                if _generic_reading(an, m.start(), m.end()).status in readable \
                        and not _about_another_procedure(an, m.start(), m.end()):
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


def _contradicts(reading: Reading) -> bool:
    """A reading that denies or doubts today's service: cancelled, negated (not only about
    earlier encounters), or an uncertain doubt. Only readings about this encounter are asked
    (see _elsewhere): a plan's "no further colonoscopy is needed" denies no service of today."""
    return (reading.status == 'cancelled' or (reading.status == 'negated' and not reading.past_negation)
            or (reading.status == 'uncertain' and reading.doubt))


def _elsewhere(an: Analysis, m: Mention) -> bool:
    """A mention in a plan or history section whose clause does not say today: whatever it reads,
    it speaks of another encounter, not of this one."""
    if an.lay.section_at(m.start).kind not in ELSEWHERE_SECTIONS:
        return False
    return not any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(m.start, m.end))


def _today_doubt(reading: Reading, kind: str) -> bool:
    """An uncertain reading about this encounter that leaves today's service open: a doubt (an
    unresolved negation, an unread section, "pending", an abort that does not say whether the
    procedure started) anywhere, or a hedge ("?", "possible") in a procedure, findings or
    technique section, or a plan passage held because its clause says today (PLAN_TODAY: round 4 release:4, so a
    second plan, history or negated mention of the family cannot outrank it). Silence (no evidence at all) is never
    one: it is no doubt, and a positive section never reads silent."""
    return reading.status == 'uncertain' and (reading.doubt or kind in POSITIVE_SECTIONS or PLAN_TODAY in reading.cues)


def _aggregate(readings: list[Reading], section_suffices: bool = True, kinds: tuple = (),
               away: tuple = ()) -> str:
    """Performed on explicit evidence, or on section evidence that no reading about this encounter
    contradicts; else incomplete; else what the readings say of today's service: cancelled, negated,
    or uncertain when a doubt or a hedge about it (or section evidence that is contradicted or does
    not suffice) leaves it open. Only then what they say of other encounters (ELSEWHERE_ORDER):
    doubt never cascades into a plan, a history or a negation of earlier encounters ("no prior
    colonoscopy"). ``kinds``: each reading's section kind; ``away``: whether it speaks of another
    encounter (_elsewhere). Both default to "about this encounter, section unknown"."""
    kinds = tuple(kinds) or ('',) * len(readings)
    away = tuple(away) or (False,) * len(readings)
    here = [(r, k) for r, k, elsewhere in zip(readings, kinds, away) if not elsewhere]
    explicit = any(r.status == 'performed' and r.basis == 'cue' for r in readings)
    section = any(r.status == 'performed' and r.basis == 'section' for r, _ in here)
    if explicit or (section and section_suffices and not any(_contradicts(r) for r, _ in here)):
        return 'performed'
    statuses = {r.status for r in readings}
    if 'incomplete' in statuses:
        return 'incomplete'
    if 'cancelled' in statuses:
        return 'cancelled'
    if any(r.status == 'negated' and not r.past_negation for r, _ in here):
        return 'negated'
    if section or any(_today_doubt(r, k) for r, k in here):
        return 'uncertain'
    return next((s for s in ELSEWHERE_ORDER if s in statuses), 'uncertain')


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
        extent = _upper_extent(an, sentences, bool(incomplete))
        short = bool(extent and extent.value.startswith('incomplete'))
        facts = [extent, interventions, _egd_location(an, interventions)]
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
    cue = _cue_reading(an, m.start, m.end, em=True)
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
# Anything in the statement's sentence (or the rest of its line) that denies, questions or
# hedges it: then it is not a statement that the service was provided.
_SEPARATE_EM_CONTRARY = re.compile(
    r"\b(?:no|not|none|never|neither|nor|without|cannot|nil|denied|declined|absent|lacking|unclear|uncertain|unknown|"
    r"whether|if|unless|may|might|could|would|should|possibl[ey]|questionabl[ey]|consider\w*|recommend\w*|pending|"
    r"question|answer|"
    # a condition or a rule, not a statement of what was done: "requires that ... is documented", "applies only
    # when ...", "must be documented", "criteria"
    r"when|whenever|once|where|only|requires?|required|requirements?|must|needs?|needed|applies|apply|criteria|"
    r"criterion|to\s+bill)\b|n't\b|\?|(?<![\w/])n/?a(?![\w/])|(?:^|[\s(])[QA]\s*[:.)]", re.A | re.I)
# A statement about another encounter is not one about this one: "at the previous visit", "at that visit".
_OTHER_ENCOUNTER = re.compile(r'\b(?:previous|prior|last|earlier|preceding|initial|first|next|upcoming|future|subsequent|'
                              r'follow-?up)\s+(?:office\s+|clinic\s+)?(?:visit|encounter|consult(?:ation)?|appointment|'
                              r'evaluation)s?\b|\b(?:at|during|on)\s+that\s+(?:visit|encounter|time|date|day)\b', re.A | re.I)
SEPARATE_EM_REACH = 300  # how much of the rest of the statement's line is quoted with it (all of it is read)
# An affirmative predicate in the same sentence: "... was provided", "I performed ...", ": yes".
_SEPARATE_EM_AFFIRMED = re.compile(
    r'\b(?:was|were|is|are|has\s+been|have\s+been|had\s+been)\s+(?:also\s+|separately\s+)?(?:performed|provided|'
    r'documented|rendered|furnished|completed|delivered|conducted|carried\s+out)\b'
    r'|\b(?:I|we)\s+(?:also\s+|separately\s+)?(?:performed|provided|rendered|furnished|conducted)\b'
    r'|[:=-]\s*yes\b', re.A | re.I)
SEPARATE_EM_NOTE = 'The documentation states a significant, separately identifiable E/M service.'
# The history cues that tell a time or another provider (routing:17); 'records reviewed' and 'in the past' are not
# read here ("including review of outside records" describes this visit).
_SEPARATE_EM_HISTORY = ('ago', 'last month', 'elsewhere')
# A month and a day with no year, anywhere in the statement ("at the 10/14 consultation").
_BARE_MONTH_DAY = re.compile(r'(?<![\w/.-])(?P<m>\d{1,2})/(?P<d>\d{1,2})(?![\w/-])', re.A)


def _another_encounters_time(an: Analysis, start: int, end: int) -> bool:
    """Whether [start, end) tells a time that is not the date of service (routing:17): a history cue of time or of
    another provider (_SEPARATE_EM_HISTORY: "two days ago", "last week", "by the referring physician"), an unlisted
    time (cues.OTHER_TIME: "yesterday", "on October 14", "on Tuesday", "next ...") that may not be the date of service,
    or a month and a day with no year that are not the date of service's (or any when that is unknown)."""
    if any(c.name in _SEPARATE_EM_HISTORY
           and not cues.SYMPTOM_TIME_BEFORE.search(an.text, max(start, c.start - 40), c.start)
           for c in an.cues_in(start, end)):
        return True  # a symptom's time ("pain that began last week") is not the encounter's
    found, starts = _other_times(an)
    for ts_, te_, name, m in found[bisect.bisect_left(starts, start):bisect.bisect_left(starts, end)]:
        if te_ <= end and not _today_compatible(an, name, m):
            return True
    day = an.service_date
    return any(day is None or (int(m.group('m')), int(m.group('d'))) != (day.month, day.day)
               for m in _BARE_MONTH_DAY.finditer(an.text, start, end) if 1 <= int(m.group('m')) <= 12)


def _separate_em_fact(an: Analysis) -> Optional[Fact]:
    """The clinician's explicit statement that a same-day E/M was significant and separately
    identifiable. Fail-closed over the whole sentence and the rest of its line: a denial, a
    question, a hedge, a condition or a rule ("requires that ... is documented"), another
    encounter ("at the previous visit"), a date that is not the date of service (or any date when
    that is unknown), or the lack of an affirmative predicate means it is not documented. So does an
    unchecked box that governs it (FORMS' _unchecked_box / _unchecked_state, or the first box after it
    on its line: contract:5), and a time that is not the date of service within SEPARATE_EM_REACH of it
    (_another_encounters_time: routing:17). The evidence is the sentence and the rest of its line
    (within SEPARATE_EM_REACH), so a check quoting it cannot hide what follows."""
    text, spans = an.text, []
    for match in _SEPARATE_EM.finditer(text):
        if an.lay.section_at(match.start()).kind in ('plan', 'history'):
            continue
        start, end = an.lay.sentence_for(match.start(), match.end())
        line_end = text.find('\n', end)
        rest_end = len(text) if line_end < 0 else line_end
        # An unchecked attestation is no statement (contract:5): a box that governs the sentence, or the first box
        # written after it on its line. Fail-closed on the box STATE: boxes that disagree, or a mark this reader
        # cannot read before or after the sentence, attest nothing either (_unchecked_box answers False for both).
        after = _BOX.search(text, end, min(rest_end, end + BOX_REACH))
        if _box_state(an, start, end) in ('off', 'mixed', 'unknown') or _unchecked_state(an, start, end) \
                or (after is not None and after.group('off') is not None):
            continue
        if _SEPARATE_EM_CONTRARY.search(text, start, end) or _SEPARATE_EM_CONTRARY.search(text, end, rest_end):
            continue
        if not _SEPARATE_EM_AFFIRMED.search(text, start, end):
            continue
        # About this encounter only: no other visit, and no date that is not the date of service.
        if _OTHER_ENCOUNTER.search(text, start, rest_end) or any(
                an.service_date is None or ctx.compare_to_service(d, an.service_date) != 0
                for d in an.dates_in(start, rest_end)):
            continue
        if _another_encounters_time(an, start, min(rest_end, end + SEPARATE_EM_REACH)):
            continue
        quoted = min(rest_end, end + SEPARATE_EM_REACH)
        spans.append(_span(text, start, quoted if text[end:quoted].strip() else end))
    return Fact('separate_em', 'documented', 'document', tuple(dict.fromkeys(spans)), SEPARATE_EM_NOTE) if spans else None


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


# A mention stores its sentence whole up to this length; a longer one by its clause, and a longer clause by the part
# within CLAUSE_REACH of the mention, which is all routing reads of it. Without the bound every mention of a long
# sentence carried a copy of it, and the stored routing grew as mentions x sentence length (routing:19).
MENTION_SENTENCE_LIMIT = 1000


def _stored_sentence(an: Analysis, start: int, end: int) -> tuple[int, int]:
    """The span a mention at [start, end) stores as its sentence (see MENTION_SENTENCE_LIMIT); it holds the mention."""
    s, e = an.lay.sentence_for(start, end)
    if e - s <= MENTION_SENTENCE_LIMIT:
        return s, e
    clauses = an.lay.clauses_for(start, end)
    cs, ce = max(s, clauses[0][0]), min(e, clauses[-1][1])
    if ce - cs <= MENTION_SENTENCE_LIMIT and cs <= start and end <= ce:
        return cs, ce
    lo, hi = an.lay.window((s, e), start, end, CLAUSE_REACH)
    return min(lo, start), max(hi, end)


def _mention(an: Analysis, m: Mention, reading: Reading) -> ServiceMention:
    s, e = _stored_sentence(an, m.start, m.end)
    return ServiceMention(family=m.family, status=reading.status, span=_span(an.text, m.start, m.end),
                          sentence=_span(an.text, s, e), section=an.lay.section_at(m.start).kind, cues=reading.cues)


def _adjustment(status: str, readings: list[Reading], facts: list[Fact], plain: str, kinds: tuple = (),
                away: tuple = ()) -> Optional[tuple[str, str]]:
    """(status, cue) a performed passage of a family takes when the family as a whole is not
    performed; None when the family is performed. Only a judgement about today's service is passed
    on, and only as cancelled, incomplete or uncertain: a family denied today, held in doubt, or
    named only as planned, historical or never done before holds its performed passages for
    clarification. A plan, a history or a negation never rewrites a passage as that status.
    ``kinds`` and ``away`` as for _aggregate."""
    if status == 'performed':
        return None
    if status == 'incomplete':
        cues_found = [r.cues[0] for r in readings if r.status == 'incomplete']
        cues_found += [f'incomplete: {f.name} {f.value}' for f in facts
                       if (f.name, f.value) == ('cannulation', 'failed')
                       or (f.name == 'extent' and (f.value or '').startswith('incomplete'))]
        return 'incomplete', cues_found[0]
    if status == 'cancelled':
        return 'cancelled', next(r for r in readings if r.status == 'cancelled').cues[0]
    kinds = tuple(kinds) or ('',) * len(readings)
    away = tuple(away) or (False,) * len(readings)
    here = [(r, k) for r, k, elsewhere in zip(readings, kinds, away) if not elsewhere]
    contrary = [r for r, _ in here if _contradicts(r)]
    denial = next((r for r in contrary if r.status == 'negated'), None)
    if status == 'negated' and denial is not None:
        return 'uncertain', f'uncertain: the document denies this service ({denial.cues[0]})'
    if status == 'uncertain':
        if plain == 'performed' and not contrary:
            return 'uncertain', HEADING_ONLY
        doubt = next((r for r, k in here if _today_doubt(r, k)), None)
        if doubt is not None:
            return 'uncertain', doubt.cues[0]
    return 'uncertain', UNESTABLISHED


def _with_fact(facts: list[Fact], name: str, fact: Optional[Fact], after: tuple[str, ...]) -> list[Fact]:
    """``facts`` with the fact called ``name`` replaced by ``fact`` (dropped when None), kept in
    its place: after the facts named in ``after``."""
    kept = [f for f in facts if f.name != name]
    if fact is None:
        return kept
    at = max((i + 1 for i, f in enumerate(kept) if f.name in after), default=0)
    return kept[:at] + [fact] + kept[at:]


# --- gi.other: a procedure of this encounter outside the detected families ---------------------------------
OTHER_FAMILY = 'gi.other'  # outside DETECTED_FAMILIES: a gi.other code's status still comes from its own passage
# What makes a phrase a procedure, by its form rather than a list of names: "Anoscopy", "Hemorrhoidectomy",
# "Rubber band ligation", "Paracentesis" are; "Labs", "CT", "A rectal examination" are not.
_PROCEDURE_WORD = re.compile(r'\b(?:\w+(?:scop(?:y|ies)|ectom(?:y|ies)|otom(?:y|ies)|ostom(?:y|ies)|plast(?:y|ies)|'
                             r'centesis|pex(?:y|ies)|rrhaph(?:y|ies))|ligations?|banding|biops(?:y|ies)|injections?|'
                             r'dilat(?:ion|ation)s?|drainage|excisions?|incisions?|resections?|ablations?|sclerotherapy|'
                             r'cauterization|cautery|manometry|debridement'
                             # the act nouns' standard abbreviations (routing:22): incision and drainage, rubber band
                             # ligation
                             r'|I[ \t]*&[ \t]*D|RBL)\b', re.A | re.I)
# Never such a procedure: an E/M service, an examination, sedation, consent, a test, or a person ("I", never the "I" of
# "I&D").
_NOT_A_PROCEDURE = re.compile(r'\b(?:visits?|evaluations?|management|E/M|consult\w*|counsel\w*|exam(?:ination)?s?|'
                              r'histor(?:y|ies)|reviews?|assessments?|discussions?|education|sedation|anesthesia|'
                              r'anaesthesia|consent|labs?|laboratory|imaging|tests?|testing|time|MDM|separately|'
                              r'patient|pt|she|he|they|we|i(?![ \t]*&))\b', re.A | re.I)
# A name led by a negation, a condition or a plan documents no procedure done ("No endoscopy or other
# procedure was performed", "None performed today", "If banding were done", "Discussed hemorrhoid banding").
_NOT_DONE_LED = re.compile(r'(?:no|none|not|neither|nor|without|w/o|if|unless|whether|should|would|could|may|might|'
                           r'can|will|discuss\w*|consider\w*|offer\w*|recommend\w*|plan\w*|schedul\w*|request\w*|'
                           r'possible|possibly|potential|probable|pending|candidate)\b', re.A | re.I)
# An explicit statement that a procedure was done. The procedure is the subject written before the
# participle with only auxiliaries between them (_DONE_GAP: "Anoscopy was performed", "Rubber band ligation
# x3 completed today", never "Anoscopy was not performed"), or the object of "underwent" / "we performed".
_DONE = re.compile(r'\b(?:performed|done|completed|carried\s+out|undertaken)\b', re.A | re.I)
_DONE_GAP = re.compile(r'(?:[ \t]+(?:was|were|has|have|had|been|then|also|subsequently|successfully|uneventfully|'
                       r'safely|today))*[ \t]*', re.A | re.I)
_OTHER_OBJECT_CUE = re.compile(r'(?<!\bnever\s)\b(?:underwent|(?:we|I)\s+(?:performed|completed|did))\s+', re.A | re.I)
# A subject starts after the last break before its participle ("After verbal consent, anoscopy was performed").
_SUBJECT_BREAK = re.compile(r'[,;:(]|\s[-\u2013\u2014]\s|\.(?=\s)', re.A)
# Where the name of a procedure ends: a verb, a status word, a clause break or punctuation.
_NP_END = re.compile(r'\s+(?:was|were|is|are|has|have|had|will|would|could|should|may|might|can|to\s+be|because|'
                     r'due|without|today|performed|done|completed|'
                     r'scheduled|planned|declined|deferred|cancell?ed|postponed|recommended|requested|ordered|'
                     r'attempted|aborted|refused|revealed|showed|demonstrated|not|if|when|once|'
                     r'and\s+(?:the|a|an)\s+patient)\b|[,;:.(]|\s[-\u2013\u2014]\s', re.A | re.I)
_WORD = re.compile(r'(?<!\S)\S+')  # a whole word: never the cut-off tail of one
# Words before a name that are not part of it: "After banding was performed", "We performed an anoscopy".
_NAME_LEAD = re.compile(r'(?:(?:after|before|once|when|while|following|then|also|subsequently)\s+)?(?:(?:an?|the)\s+)?',
                        re.A | re.I)
OTHER_BOX_ITEMS = 12  # the items of one check-box line that are read as names (bounds the work per line)
OTHER_NAME_REACH = 120  # a procedure's name is short (bounds the work per candidate)
# A history word that leads a name stays outside it, so the history pre-cue (cues.HISTORICAL_PRE) reads the name as
# history (routing:21): "Prior hemorrhoid banding was performed", "Status post hemorrhoidectomy".
_HISTORY_LEAD = re.compile(r'(?:(?:prior|previous|previously|recent|recently|remote|past|earlier|last|most\s+recent|index|'
                           r'outside|s/p|status\s+post|(?:personal\s+)?history\s+of|hx\s+of|h/o)\s+)+', re.A | re.I)
# A band ligation written in a colonoscopy's or a flexible sigmoidoscopy's own findings is that procedure's
# (45398 / 45350), not another one (routing:21).
_BANDING = re.compile(r'\bband(?:s|ed|ing)?\b|\bligat\w*|\bRBL\b', re.A | re.I)
_LOWER_FAMILIES = ('gi.colonoscopy', 'gi.flex_sig')
_RETROFLEXION = re.compile(r'\bretroflex\w*', re.A | re.I)
OTHER_CONTEXT_SENTENCES = 6  # how many earlier sentences of its section speak for a banding (bounds the work)
# Further forms of a procedure done (routing:22), each told by its form and each only ever adding a hold:
# - the act of an act noun, as a participle after an auxiliary ("Two internal hemorrhoids were banded today") or after
#   "we" / "I" ("Today we banded two internal hemorrhoids"); never "dilated" or "injected", which name findings;
# - a -scopy name labelling its findings in an office note ("Anoscopy: grade 2 internal hemorrhoids, no fissure.");
# - the subject of "was performed" written with an appositive or a list between commas ("Rubber band ligation of
#   internal hemorrhoids, columns 1 and 2, was performed today").
_ACT_PARTICIPLE = r'(?:banded|ligated|excised|resected|ablated|cauteri[sz]ed|incised|drained|debrided|sclerosed|biopsied)'
_ACT_DONE = re.compile(r'\b(?:was|were|has[ \t]+been|have[ \t]+been|had[ \t]+been)[ \t]+(?:(?:then|also|successfully|'
                       r'uneventfully|safely|subsequently)[ \t]+)?' + _ACT_PARTICIPLE + r'\b', re.A | re.I)
_WE_ACT = re.compile(r'\b(?:we|I)[ \t]+(?:(?:then|also|successfully|subsequently)[ \t]+)?(?P<act>' + _ACT_PARTICIPLE
                     + r')\b', re.A | re.I)
_SCOPY_LABEL = re.compile(r'[ \t]*(?:[-*•][ \t]+)?(?P<name>(?:[A-Za-z][\w/-]*[ \t]+){0,3}[A-Za-z]+scop(?:y|ies))'
                          r'[ \t]*:[ \t]*(?=\S)', re.A | re.I)
_APPOSITIVE_GAP = re.compile(r'(?:[ \t]*,[ \t]*(?:(?!\b(?:was|were|is|are|has|have|had|not|no|never|which|that|who|if|'
                             r'when|unless|whether)\b)[^,;:.()\n]){1,60}?)+[ \t]*,?' + _DONE_GAP.pattern, re.A | re.I)
# A stated act or a findings label whose ordinary reading is silent still speaks of a procedure: held, never
# performed (validation then holds a same-day E/M as possibly beside it).
OTHER_STATED = 'uncertain: a procedure is stated by its act or its findings, with no performance cue'


def _about_a_detected_family(an: Analysis, start: int, end: int, detected: list[str]) -> bool:
    """Whether [start, end) speaks of a detected family's procedure: it names one of those services, an
    instrument of one ("the colonoscope", "fine-needle"), or one of their interventions ("polypectomy")."""
    if an.services_in(start, end):
        return True
    if any(p.search(an.text, start, end) for family, p in cues.INSTRUMENTS if family in detected):
        return True
    return any(set(iv.families) & set(detected) for iv in an.interventions_in(start, end))


def _procedure_name(an: Analysis, start: int, limit: int) -> Optional[tuple[int, int]]:
    """The name of a procedure written from ``start`` (after a check box and _NAME_LEAD): up to the first
    verb, status word, clause break, punctuation or check box, within OTHER_NAME_REACH. None when empty."""
    text = an.text
    limit = min(limit, start + OTHER_NAME_REACH)
    start = _SEPARATOR.match(text, start, limit).end()
    lead = _BOX.match(text, start, limit)
    if lead:
        start = _SEPARATOR.match(text, lead.end(), limit).end()
    start = _NAME_LEAD.match(text, start, limit).end()
    start = _HISTORY_LEAD.match(text, start, limit).end() if _HISTORY_LEAD.match(text, start, limit) else start
    stop = _NP_END.search(text, start, limit)
    end = stop.start() if stop else limit
    box = _BOX.search(text, start, end)
    return _trimmed_span(text, start, box.start() if box else end)


def _trimmed_span(text: str, start: int, end: int) -> Optional[tuple[int, int]]:
    while start < end and not text[start].isalnum():
        start += 1
    while end > start and not text[end - 1].isalnum():
        end -= 1
    return (start, end) if start < end else None


def _other_mentions(an: Analysis, detected: list[str]) -> list[Mention]:
    """Procedures documented in the text that name none of the detected families (OTHER_FAMILY): a
    procedure's name (_PROCEDURE_WORD: "Anoscopy", "Rubber band ligation", "Hemorrhoidectomy") written
    - as the first sentence of a procedure section ("Procedure: Anoscopy with banding of two internal
      hemorrhoids.");
    - as the subject of an explicit performed clause ("Rubber band ligation of an internal hemorrhoid was
      performed today", "After verbal consent, anoscopy was performed");
    - as the object of "underwent" / "we performed".
    Never a phrase that speaks of a detected family within CLAUSE_REACH (_about_a_detected_family), an
    E/M service, an examination, sedation, consent, a test or a person (_NOT_A_PROCEDURE), nor a name led
    by a negation, a condition or a plan (_NOT_DONE_LED). Each one's status comes from the ordinary
    readings, so a planned or denied procedure reads planned or negated."""
    text, found = an.text, {}

    def consider(span, clause, form=''):
        """``form``: 'act' (a stated act: its participle is the procedure's word) or 'label' (a findings label), the
        routing:22 forms, whose mentions carry it as their value (see _other_finding)."""
        if span is None:
            return
        s, e = span
        name = text[s:e]
        if (form != 'act' and not _PROCEDURE_WORD.search(name)) or _NOT_A_PROCEDURE.search(name) \
                or _NOT_DONE_LED.match(name):
            return
        scope = (max(clause[0], s - CLAUSE_REACH), min(clause[1], e + CLAUSE_REACH))
        if _about_a_detected_family(an, *scope, detected) or _lower_tract_banding(an, s, e, detected):
            return
        if form and _in_a_detected_procedures_text(an, s, e, detected):
            return
        found[(s, e)] = Mention(OTHER_FAMILY, s, e, 'service', name, form)

    def told_done(span, clause, form=''):
        """An explicit performed clause names no same-day procedure when it is told at an earlier time of its own
        ("was performed at her last visit", "was done as a child", "in June"): history, as it read at 57b4b3747,
        before gi.other existed (routing:21). A later or unknown time names it, and its reading holds it."""
        if span is not None and not _told_at_another_time(an, *span):
            consider(span, clause, form)

    def subject(m, cs):
        """The subject written before the verb at ``m``: from the last break before it (_SUBJECT_BREAK), else, past
        comma breaks only, from an earlier one when the rest up to the verb is an appositive or a list (routing:22)."""
        breaks = [(b.end(), b.group(0)) for b in _SUBJECT_BREAK.finditer(text, cs, m.start())]
        starts = [breaks[-1][0] if breaks else cs]
        for index in range(len(breaks) - 1, -1, -1):
            if breaks[index][1] != ',':
                break
            starts.append(breaks[index - 1][0] if index else cs)
        for n, at in enumerate(starts):
            word = _WORD.search(text, at, m.start())
            name = word and _procedure_name(an, word.start(), m.start())
            if not name:
                continue
            named = bool(_PROCEDURE_WORD.search(text, *name))
            if n == 0:
                if not named:
                    continue  # nothing is named after the last break: an earlier comma may open the subject
                return name if _DONE_GAP.fullmatch(text, name[1], m.start()) else None
            if named and _APPOSITIVE_GAP.fullmatch(text, name[1], m.start()):
                return name
        return None

    def names(pos, sentence):  # the name written at pos and, along a check-box line, each item's name
        for _ in range(OTHER_BOX_ITEMS):
            span = _procedure_name(an, pos, sentence[1])
            consider(span, sentence)
            after = span[1] if span else pos + 1
            box = _BOX.search(text, after, min(sentence[1], after + OTHER_NAME_REACH))
            if box is None:
                return
            pos = box.start()

    for section in an.lay.sections:
        if section.kind != 'procedure':
            continue
        first = _SEPARATOR.match(text, section.heading.end if section.heading else section.start, section.end).end()
        index = _sentence_index(an, first)
        if index < 0 or an.lay.section_at(first) is not section:
            continue
        names(max(an.lay.sentences[index][0], first), an.lay.sentences[index])
        for sentence in an.lay.sentences[index + 1:bisect.bisect_left(an.lay.sentences, (section.end, -1))]:
            if _BOX.search(text, *sentence):
                names(sentence[0], sentence)  # a later check-box line names its own procedures
    def subject_start(m):
        clause = _clause_at(an, m.start())
        heading = an.lay.section_at(m.start()).heading
        cs = heading.end if heading is not None and clause[0] < heading.end <= m.start() else clause[0]
        return clause, max(cs, m.start() - OTHER_NAME_REACH)

    for m in _DONE.finditer(text):
        clause, cs = subject_start(m)
        told_done(subject(m, cs), clause)
    for m in _OTHER_OBJECT_CUE.finditer(text):
        clause = _clause_at(an, m.start())
        told_done(_procedure_name(an, m.end(), clause[1]), clause)
    # routing:22: a stated act ("<subject> were banded", "we banded <object>") and an office note's findings label
    for m in _ACT_DONE.finditer(text):
        clause, cs = subject_start(m)
        breaks = [b.end() for b in _SUBJECT_BREAK.finditer(text, cs, m.start())]
        word = _WORD.search(text, breaks[-1] if breaks else cs, m.start())
        if word is not None:
            told_done(_trimmed_span(text, _NAME_LEAD.match(text, word.start(), m.start()).end(), m.end()), clause, 'act')
    for m in _WE_ACT.finditer(text):
        clause = _clause_at(an, m.start())
        obj = _procedure_name(an, m.end(), clause[1])
        if obj is not None:
            told_done((m.start('act'), obj[1]), clause, 'act')
    if any(m.kind in ('em-visit', 'em-time', 'em-mdm') for m in an.em):
        for s, e in an.lay.sentences:
            label = _SCOPY_LABEL.match(text, s, e)
            if label:
                told_done(label.span('name'), (s, e), 'label')
    return sorted(found.values(), key=lambda mention: mention.start)


def _in_a_detected_procedures_text(an: Analysis, s: int, e: int, detected: list[str]) -> bool:
    """Whether [s, e) lies in a detected procedure's own text: a procedure, findings or technique section whose
    heading, or one of the OTHER_CONTEXT_SENTENCES sentences before it, names a detected family or its instrument
    ("Findings: The gastroscope was advanced ... Three columns were banded.")."""
    if not detected:
        return False
    section = an.lay.section_at(s)
    index = _sentence_index(an, s)
    if section.kind not in POSITIVE_SECTIONS or index < 0:
        return False
    lo = max(section.start, an.lay.sentences[max(0, index - OTHER_CONTEXT_SENTENCES)][0])
    if any(m.family in detected for m in an.services_in(lo, e)):
        return True
    return any(p.search(an.text, lo, e) for family, p in cues.INSTRUMENTS if family in detected)


def _lower_tract_banding(an: Analysis, s: int, e: int, detected: list[str]) -> bool:
    """Whether the procedure named at [s, e) is a band ligation written in a detected colonoscopy's or flexible
    sigmoidoscopy's own text: a procedure, findings or technique section whose heading, or one of the
    OTHER_CONTEXT_SENTENCES sentences before it, names that service, its instrument or a retroflexion. An office
    note's banding beside a colonoscopy named only in its history is not."""
    if not set(_LOWER_FAMILIES) & set(detected) or not _BANDING.search(an.text, s, e):
        return False
    section = an.lay.section_at(s)
    index = _sentence_index(an, s)
    if section.kind not in POSITIVE_SECTIONS or index < 0:
        return False
    lo = max(section.start, an.lay.sentences[max(0, index - OTHER_CONTEXT_SENTENCES)][0])
    if any(m.family in _LOWER_FAMILIES for m in an.services_in(lo, e)):
        return True
    return any(p.search(an.text, lo, e) for family, p in cues.INSTRUMENTS if family in _LOWER_FAMILIES) \
        or bool(_RETROFLEXION.search(an.text, lo, e))


def _other_finding(an: Analysis, others: list[Mention], has_basis: bool) -> FamilyFinding:
    """The OTHER_FAMILY finding. Its mentions are different procedures ("Anoscopy", "Rubber band
    ligation"), so each is judged alone, by the rules every family follows (with E/M documentation, an
    office note's procedure heading alone does not establish it: HEADING_ONLY), and one procedure's denial
    never adjusts another's passage. The family is performed, incomplete or uncertain when any of its
    procedures is (in that order: one procedure's denial does not make the family read "negated" while
    another may have been done); else the usual aggregate of all of them."""
    raw = [_stated(_generic_reading(an, m.start, m.end), m) for m in others]
    kinds = tuple(an.lay.section_at(m.start).kind for m in others)
    away = tuple(_elsewhere(an, m) for m in others)
    statuses, readings = [], []
    for reading, kind, elsewhere in zip(raw, kinds, away):
        one = _aggregate([reading], section_suffices=not has_basis, kinds=(kind,), away=(elsewhere,))
        plain = _aggregate([reading], kinds=(kind,), away=(elsewhere,))
        statuses.append(one)
        readings.append(_adjusted(reading, _adjustment(one, [reading], [], plain, (kind,), (elsewhere,))))
    status = next((s for s in ('performed', 'incomplete', 'uncertain') if s in statuses), None) or _aggregate(
        raw, section_suffices=not has_basis, kinds=kinds, away=away)
    return FamilyFinding(OTHER_FAMILY, status, tuple(_mention(an, m, r) for m, r in zip(others, readings)), (),
                         _missing(OTHER_FAMILY, []))


def _stated(reading: Reading, m: Mention) -> Reading:
    """A routing:22 mention (a stated act or a findings label, its value) whose ordinary reading is silent: held with
    OTHER_STATED, never performed; every other reading as it is."""
    if m.value in ('act', 'label') and reading.status == 'uncertain' and reading.cues == (SILENT,):
        return Reading('uncertain', (OTHER_STATED,), 'cue')
    return reading


def _route(an: Analysis) -> RoutingResult:
    detected = [f for f in PROCEDURE_FAMILIES if any(m.family == f for m in an.services)]
    others = _other_mentions(an, detected)
    an.other_names = tuple((m.start, m.end) for m in others)
    readings = {m: _generic_reading(an, m.start, m.end) for m in an.services}
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
        kinds = tuple(an.lay.section_at(m.start).kind for m in mentions)
        away = tuple(_elsewhere(an, m) for m in mentions)
        status = _aggregate(family_readings, section_suffices=evidenced or not has_basis, kinds=kinds, away=away)
        if status not in ('performed', 'incomplete'):
            facts = [f for f in facts if f.origin != 'missing']  # "no sampling documented" speaks only of a done EUS
            if family == 'gi.colonoscopy':  # the intent of a colonoscopy that is only planned may be in the plan
                facts = _with_fact(facts, 'intent', _intent(an, attributed, len(detected) == 1, today=False),
                                   after=('extent', 'interventions', 'polyp_count'))
        if status == 'performed' and short:
            status = 'incomplete'
        an.adjustments[family] = _adjustment(status, family_readings, facts,
                                             _aggregate(family_readings, kinds=kinds, away=away), kinds, away)
        findings[family] = FamilyFinding(
            family, status, tuple(_mention(an, m, _adjusted(readings[m], an.adjustments[family])) for m in mentions),
            tuple(facts), _missing(family, facts))
    if others:
        findings[OTHER_FAMILY] = _other_finding(an, others, has_basis)
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
def _analysis(text: str, service_date: Optional[date] = None) -> tuple[Analysis, RoutingResult]:
    lay = layout(text)
    interventions = tuple(Intervention(label, families, m.start(), m.end())
                          for label, pattern, families in cues.INTERVENTIONS for m in pattern.finditer(text))
    effective = service_date if service_date is not None else ctx.service_date_of(text)
    an = Analysis(text, lay, _service_mentions(text), _em_mentions(text, lay), _clause_cues(text),
                  ctx.find_dates(text), effective, interventions)
    return an, _route(an)


def _checked_date(service_date, caller):
    if service_date is not None and not isinstance(service_date, date):
        raise TypeError(f'{caller} needs service_date as a date or None.')
    return service_date


def route(text: str, service_date: Optional[date] = None) -> RoutingResult:
    """The GI services the document describes, with status, facts and missing facts.

    ``service_date`` is the encounter's effective date of service (a member-supplied
    value overrides the document's). None uses the date the document itself states.
    """
    if not isinstance(text, str):
        raise TypeError('route() needs the canonical text as str.')
    return _analysis(text, _checked_date(service_date, 'route()'))[1]


def status_for_span(text: str, start: int, end: int,
                    service_date: Optional[date] = None) -> tuple[str, tuple[str, ...]]:
    """Status of the service mentioned at [start, end), judged from its clause,
    sentence and section, with the cues that decided it. Fail-closed.
    ``service_date`` as for route()."""
    if not isinstance(text, str):
        raise TypeError('status_for_span() needs the canonical text as str.')
    if not (0 <= start < end <= len(text)):
        raise ValueError(f'span [{start}, {end}) is not a non-empty range inside the text (length {len(text)}).')
    reading = _read_span(_analysis(text, _checked_date(service_date, 'status_for_span()'))[0], start, end)
    return reading.status, reading.cues
