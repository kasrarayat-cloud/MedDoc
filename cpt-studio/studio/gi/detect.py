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

ROUTING_VERSION = 'gi-routing@4'
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


def service_mention_count(text: str) -> int:
    """How many times the text names a procedure family (the service mentions route() reads one by one): what the
    analyze stage bounds before reading a document (settings.MAX_SERVICE_MENTIONS)."""
    return len(_service_mentions(text))


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
    """Every clause-scope cue in the text, matched once over the whole text. The "?" of the unread mark extraction
    writes ("[?]", symbols.BOX_UNREAD_MARK) is no question-mark hedge: the item it marks is held as unread (BOX_UNREAD),
    and its neighbours on the line are not doubted by it (round 5 extraction:8)."""
    found = []
    for status, entries in (('cancelled', cues.CANCELLED_CLAUSE), ('incomplete', cues.INCOMPLETE_CLAUSE),
                            ('historical', cues.HISTORICAL_CLAUSE), ('planned', cues.PLANNED_CLAUSE),
                            ('uncertain', cues.UNCERTAIN_CLAUSE), ('performed', cues.PERFORMED_CLAUSE)):
        for name, pattern in entries:
            found.extend(Cue(m.start(), m.end(), status, name, m.group(0)) for m in pattern.finditer(text)
                         if not (name == 'question mark'
                                 and text.startswith(_BOX_SYMBOLS.BOX_UNREAD_MARK, max(0, m.start() - 1))))
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
        self._longest_service = max((m.end - m.start for m in self.services), default=0)
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
    20 KB paste, for no time saved.

    Except where the member is followed, after nothing but spaces and commas, by the next service name inside the
    window (a list: "EUS, EUS, EUS ..."): every reader of a member's tail - NEGATED_POST, INCOMPLETE_POST,
    UNCERTAIN_POST and NEGATION_HEAD_AFTER - is anchored at its start and fails on a tail that opens with spaces or
    commas and then a service token, whatever follows (none takes the token there: each needs a word of its own first,
    and the one that may take any word, HEDGED_AFTER's place phrase, takes it only after a preposition). Such a tail
    is read as LIST_TAIL, which every one of them reads the same way, instead of being masked to the window's end once
    per member per mention: on a long list that cost 18 ms a mention, 85 s on a 50,000-character paste (round 4d
    integration; pinned with the readers' own outcomes in tests/test_repairs_r4d_integration.py)."""
    following = bisect.bisect_left(an._service_starts, me)
    if following < len(an.services):
        nxt = an.services[following]
        if nxt.end <= ce and _LIST_GAP.fullmatch(an.text, me, nxt.start) is not None:
            return LIST_TAIL
    return _masked(an, me, ce)


# A member's tail that opens with the next service name (_masked_post): spaces and commas, then the token.
LIST_TAIL = f' {cues.SERVICE_TOKEN} '
_LIST_GAP = re.compile(r'[\s,]*')


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
        post = _masked_post(an, me, ce) if post is None else post
        found, governs_next = [], []
        listed = post is LIST_TAIL  # every post reader fails on it (_masked_post): nothing to search
        for name, said, at in _pre_negations(an, _pre_start(an, cs, ms), ms):
            where = (at, ms)
            if not listed and cues.NEGATION_HEAD_AFTER.match(post):
                governs_next.append(where)
            else:
                past = name != cues.REFUSAL and bool(cues.NEGATION_ABOUT_PAST.search(said))
                found.append((f'negated: {said.strip()}', past, where))
        for _, pattern in () if listed else cues.NEGATED_POST:
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


def _continuation(an: Analysis, pos: int, limit: int, clause_end: int, procedure: bool,
                  target: Optional[tuple[int, int]] = None) -> Optional[str]:
    """The words after ``pos`` (up to ``limit``, the end of the name's sentence) that keep a section
    from speaking for the service named before ``pos``, or None when they describe the procedure or
    what it found (see above). The first word is read even where a clause word opens it
    ("Colonoscopy, however, was not."); later words only up to ``clause_end``, the end of the name's
    own clause. ``procedure``: under a procedure heading, where a "to" may open the procedure's
    purpose. ``target``: what is read (the service's name, or a passage naming it); a word of an option whose own box is
    unchecked states nothing about a target beside it (round 4c-2 box2:I: "Colonoscopy: ☒ Completed ☐ Cancelled"), and
    a passage across the option keeps it (_B2_unselected_option)."""
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
        if stop is not None and not (target is not None
                                     and _B2_unselected_option(an, word.start(), word.end(), *target) == 'off'):
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
    words = _B3_words(an.text, start, end, 6)  # a box of any spelling is one word (round 6 declared:5)
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
    not "Procedure status: Not performed"). Round 4d BOXES3: never a line the strict check-box rows hold (_B3_hold)."""
    if _B3_hold(an, start, end) is not None:
        return False
    if _box_state(an, start, end) == 'off':
        options = _box_denying_options(an, start, end)
        if not options:  # nothing on the line would deny if selected ("Procedure completed: ☐ Yes ☒ No"): no option
            return False
        words = options + [m.span() for m in _BOX_DONE_OPTION.finditer(an.text, start, end)]
        return all(state == 'off' for state in _box_option_states(an, start, end, options, words))
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
    deferring, doubting, historical or incomplete cue, an act denial ("Not performed", "Declined"), a rescheduling, or
    a status value's own hold word (_STATUS_HOLD: "Pending", "TBD", "On hold"; round 5 regression:0)."""
    found = [(c.start, c.end) for c in an.cues_in(start, end)
             if c.status in ('cancelled', 'planned', 'uncertain', 'historical', 'incomplete')]
    found += [m.span() for m in _ACT_DENIAL.finditer(an.text, start, end)]
    found += [m.span() for m in _BOX_NOT_DONE_OPTION.finditer(an.text, start, end)]
    found += [m.span() for m in _BOX_STATUS_HOLD_WORD.finditer(an.text, start, end)
              if _box_beside_a_mark(an.text, m.start(), m.end(), start, end)]
    return found + [m.span() for m in _RESCHEDULED.finditer(an.text, start, end)]


# The status hold words (_STATUS_HOLD) of a boxed status value, wherever they stand, not only where a value opens with
# one ("Status: Completed ☐ Pending ☒"): written beside a mark, each is an option, so a checked one holds (round 5
# regression:0); one in a remark ("Completed ☒ (pathology pending)") is no option.
_BOX_STATUS_HOLD_WORD = re.compile(r'\b' + _STATUS_HOLD.pattern, _STATUS_HOLD.flags)
# A denial option written as two words ("Not performed", "Not done"): one option word, so the box after its participle
# is its own ("Performed ☐ Not performed ☒"), never a box no option word reaches (round 5 declared:2).
_BOX_NOT_DONE_OPTION = re.compile(r'\bnot[ \t]+(?:done|performed)\b', re.A | re.I)


# The words of a status option that says the service was done ("☐ Completed ☒ Cancelled", "Completed ☐ | Cancelled
# ☒"): with the denying options they are a status line's option words, which its boxes lead or trail.
_BOX_DONE_OPTION = re.compile(r'\b(?:complete[ds]?|performed|done|finished|accomplished|successful(?:ly)?)\b',
                              re.A | re.I)


def _box_option_states(an: Analysis, lo: int, hi: int, options: list, words: list) -> list:
    """The state of the box(es) governing each status option of ``options``, among the option words ``words`` of the
    status line [lo, hi) (its denying and its completion options): the boxes lead when the line's first box comes
    before its first option word ("☐ Completed ☒ Cancelled"), and trail when its last box comes after its last option
    word ("Completed ☐ | Cancelled ☒"; "Procedure cancelled: [ ] Yes [x] No" is a yes/no pair after its one option
    word). A line that can be read both ways gives 'unknown'; a line with no box gives None. The option words are what
    the boxes mark, so a status line is never read by where an item would be. One pass over the line's boxes."""
    text = an.text
    _, boxes = _box_tokens(an, lo, hi)
    if not options:
        return []
    if not boxes:
        return [None] * len(options)
    words = _merged(list(words) + list(options))
    word_starts = [w[0] for w in words]
    box_starts = [b[0] for b in boxes]
    if boxes[0][0] < words[0][0]:
        found = []
        for _, option_end in options:
            index = bisect.bisect_left(box_starts, option_end)
            found.append(_box_lead_state(text, boxes[max(0, index - BOX_RUN_LIMIT):index], option_end))
        return found
    if boxes[-1][0] <= words[-1][0]:
        return ['unknown'] * len(options)
    found = []
    for option_start, _ in options:
        index = bisect.bisect_right(word_starts, option_start) - 1
        after = words[index + 1][0] if index + 1 < len(words) else hi
        group = boxes[bisect.bisect_left(box_starts, option_start):bisect.bisect_left(box_starts, after)]
        found.append(_box_option_group_state(text, words[index], group) if group else None)
    return found


def _box_option_group_state(text: str, word: tuple[int, int], group: list) -> Optional[str]:
    """The state of the boxes ``group`` that trail the status option word ``word``: as _group_state reads an item's
    (a yes/no pair after the option is read by the option it marks: "Procedure cancelled: [ ] Yes [x] No"), except that
    when the yes/no word right before the first box is the option's own word ("Not done ☒", "Not performed ☐"), the
    option's own box run decides: _group_state would read its "Not done" as the "No" of a pair, so a checked option as
    unchecked and an unchecked one as unread (round 5 declared:2)."""
    first = group[0]
    before = _OPTION_BEFORE.search(text, max(0, first[0] - 20), first[0])
    if before is None or before.start() >= word[1]:
        return _group_state(text, group)
    run = [first]
    for b in group[1:]:
        if not _BOX_RUN_GAP.fullmatch(text, run[-1][1], b[0]):
            break
        run.append(b)
    return _run_state(run)


def _cancels(an: Analysis, start: int, end: int) -> bool:
    """A cancellation cue in [start, end); an abort after the scope went in is not one."""
    return any(c.status == 'cancelled' and (c.name != 'aborted' or _abort_status(an, c)[0] != 'incomplete')
               for c in an.cues_in(start, end))


def _boxed_status_denies(an: Analysis, lo: int, hi: int) -> Optional[bool]:
    """For a status value with boxes ("[ ] Completed [x] Cancelled - patient ate breakfast", "Completed ☐ Cancelled ☒
    Postponed"; round 4, BOXES' residual): True when any denying option is not plainly unchecked (checked,
    disagreeing, unread, or governed by no box), False when every one is unchecked, None when the value has no box or
    no denying option (it is read as text, as before round 4b: round 5 regression:0). The caller holds the service
    line; it never excludes. Round 4d BOXES3: True on a row the strict check-box rows hold (_B3_hold)."""
    _, boxes = _box_tokens(an, lo, hi)
    if not boxes:
        return None
    options = _box_denying_options(an, lo, hi)
    if not options:
        return None
    if _B3_hold(an, lo, hi) is not None:
        return True
    words = options + [m.span() for m in _BOX_DONE_OPTION.finditer(an.text, lo, hi)]
    return any(state != 'off' for state in _box_option_states(an, lo, hi, options, words))


def _B3_status_value_denies(an: Analysis, value: int, ne: int) -> bool:
    """Whether a status line's value [value, ne) denies or holds the service, as round 5 read the value after its key: a
    value with boxes option by option (_boxed_status_denies), a completion never ("Completed.", "Done"), else a hold
    word, a short denying or cancelling value, or a value that opens with a calling off ("Cancelled - the patient had
    eaten breakfast."). _denies reads round 5's key on its value and the shared grammar's on its own, and holds when
    either denies (round 4d BOXES3)."""
    boxed = _boxed_status_denies(an, value, ne)
    if boxed is not None:
        return boxed  # a value with boxes is read option by option, never by its first word
    if _STATUS_DONE.match(an.text, value, ne):
        return False
    return (bool(_STATUS_HOLD.match(an.text, value, ne)) or _bare_denial(an, value, ne)
            or _value_calls_off(an, value, ne))


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
    old_key = _STATUS_KEY.match(text, body, ne)
    new_key = _B3_STATUS_KEY.match(text, body, ne)
    if old_key:
        # round 5's status line is read on its own value exactly as before; the shared grammar's value, after a label
        # cell's own colon and a second separator ("Status: | Cancelled - ...": round 6 declared:4), may only add a
        # hold: read after both separators, "Status: | Completed? No" opened with a completion and was released
        # (round 4d's verification), where its own value, "| Completed? No", holds
        if _B3_status_value_denies(an, old_key.end(), ne):
            return True
        return bool(new_key) and new_key.end() != old_key.end() and _B3_status_value_denies(an, new_key.end(), ne)
    if new_key and _B3_status_value_denies(an, new_key.end(), ne):
        return True
    # round 4d BOXES3: a status line only the shared grammar's lead or separator reads (round 6 declared:4: "• Status:
    # Cancelled - ...", "Status | Cancelled ...") holds as one; where it would not (a completion, unchecked boxed
    # options), the tests below decide as before, so it never releases a line they hold
    if _box_selected_denial(an, body, ne):
        return True  # "☒ Not performed": a selected denial option on a line naming no item holds (round 5 declared:8)
    if bare and _bare_denial(an, body, ne):
        return True
    # a box of any spelling is one word ("[ x ] Cancelled - patient ate breakfast.": round 6 declared:5)
    if _B3_words(text, body, ne, 6) <= 6 and (_denies_an_act(an, body, ne) or _cancels(an, body, ne)
                                              or _reschedules(an, body, ne)):
        return True
    if not _REFERRING_SUBJECT.match(text, body, ne):
        return False
    return _cancels(an, ns, ne) or bool(_denying_word(an, ns, ne)) or _reschedules(an, ns, ne)


def _box_selected_denial(an: Analysis, lo: int, hi: int) -> bool:
    """Whether the line [lo, hi), naming no item, selects a "Not performed" or "Not done" option: one written beside a
    box, with only spaces, a colon or a cell bar between (where _OPTION_LABEL explains its own "not" as an option's
    label, whatever the box's state), whose own box (_box_option_states) is checked, unread or disagrees (round 5
    declared:8: "☒ Not performed", "Performed ☐ Not performed ☒", "Completed | ☐ | Not done | ☒"). An item's own
    denial ("Biopsy: [x] Not performed") and another act's ("☒ Retroflexion not performed": no option beside its box)
    are read as before."""
    text = an.text
    if _box_tokens(an, lo, hi)[0]:
        return False
    spans = [m.span() for m in _BOX_NOT_DONE_OPTION.finditer(text, lo, hi) if _box_beside_a_mark(text, *m.span(), lo, hi)]
    if not spans:
        return False
    if _B3_hold(an, lo, hi) is not None:
        return True  # round 4d BOXES3: on a row the strict check-box rows hold, such an option is no unselected one
    words = _box_denying_options(an, lo, hi) + [m.span() for m in _BOX_DONE_OPTION.finditer(text, lo, hi)]
    return any(state not in ('off', None) for state in _box_option_states(an, lo, hi, spans, words))



def _box_beside_a_mark(text: str, start: int, end: int, lo: int, hi: int) -> bool:
    """Whether the option word [start, end) is written beside a box or mark, in [lo, hi): right after or right before
    it, with only spaces, a colon or a cell bar between (_BOX_BESIDE_AFTER, _BOX_BESIDE_BEFORE)."""
    return bool(_BOX_BESIDE_AFTER.match(text, end, hi) or _BOX_BESIDE_BEFORE.search(text, max(lo, start - 20), start))


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
    """Whether [start, end) is a status line: its key after the separator and a sentence adverb, as round 5 read it
    (_STATUS_KEY) or in the shared grammar, after any list marker or with a bar, tab or two spaces as its separator
    (_B3_STATUS_KEY, round 6 declared:4). Its callers then ask _denies, which only holds such a line."""
    at = _SEPARATOR.match(an.text, start, end).end()
    opener = _OPENER.match(an.text, at, end)
    body = opener.end() if opener else at
    return bool(_STATUS_KEY.match(an.text, body, end) or _B3_STATUS_KEY.match(an.text, body, end))


def _procedure_called_off(an: Analysis, start: int, end: int) -> bool:
    """Whether [start, end) says the procedure was cancelled, postponed, rescheduled or not performed ("The procedure
    was cancelled because the patient had eaten breakfast."), and not of an earlier encounter. A status option whose
    own box is unchecked says nothing ("Procedure completed ☒ | Procedure cancelled ☐": _box_own_option_off, round 5
    regression:4)."""
    key = ('called-off', start, end)
    if key not in an.memo:
        an.memo[key] = any(_generic_reading(an, m.start(), m.end()).status != 'historical'
                           and not _box_own_option_off(an, m.start(), m.end())
                           for pattern in (cues.PROCEDURE_CANCELLED, cues.PROCEDURE_NOT_PERFORMED)
                           for m in pattern.finditer(an.text, start, end))
    return an.memo[key]


# --- One grammar for the lines that ask whether the procedure was done or called off (round 5 declared:0, 1, 9, 10) ---
# The typed done-question (_PERFORMED_ANSWERED_NO), its boxed form (_PERFORMED_QUESTION), the form field's
# (_BOX_DONE_QUESTION) and the status question answered with a denial (_BOX_ANSWER_LEAD, _BOX_ANSWER_TAIL) are built
# from these pieces, so a spelling one of them accepts every one accepts. Each only holds.
# The lead: an indent, a list marker ("- ", "* ", "• ", "1. ", "2) ", "(1) ", "a. "), "was", "is", "has" or "had", and
# "the" or "this" ("Was the procedure performed?").
_BOX_Q_LEAD = (r'[ \t]*(?:(?:[-*\u2022\u00b7\u25aa\u25e6\u25cf\u2023\u2043\u2013\u2014]|\(?\d{1,3}[.)]|\(?[a-z][.)](?=[ \t]))'
               r'[ \t]*)?(?:(?:was|is|has|had)[ \t]+)?(?:(?:the|this)[ \t]+)?')
# The procedure's own word, the done-question's verb, and an optional "today" after either question.
_BOX_Q_NOUN = r'(?:procedure|exam|examination|study|endoscopy|case)'
_BOX_Q_DONE = r'(?:performed|completed|done|attempted|started)'
_BOX_Q_TODAY = r'(?:[ \t]+today)?'
# The separator: ':', '?', '=', '|', a dash, a tab or two spaces, after the label's own '?' or ':' (a form block's
# "<label>: <value>" for a label that asks: "Procedure performed?: No").
_BOX_Q_SEP = r'[ \t]*(?:[?:][ \t]*)?(?:[:?=|\u2013\u2014-]|\t| {2,})[ \t]*'
# The answers that say no, or that this reader cannot read as done: "No", "None", "N", "Not done", "Not performed",
# "Not completed", "N/A", "NA", "Not applicable".
_BOX_Q_DENIAL = r'(?:no|none|n|not\s+(?:done|performed|completed)|n/a|na|not\s+applicable)'
# Round 4d BOXES3 (round 6 declared:4): the status line's key in the same grammar, so a status line after any list
# marker ("• Status: Cancelled - ...", "2) Status: ...", "(1) Status: ...") or with a cell bar, a tab or two spaces as
# its separator ("Status | Cancelled", "Procedure status<TAB>Cancelled") is read as one. _STATUS_KEY stays the key of
# round 5: a line only this key reads may hold the service, never release a line the other readers held (_denies).
_B3_STATUS_KEY = re.compile(_BOX_Q_LEAD + r'(?:(?:procedure|case|exam|examination|study|service|endoscopy)[ \t]+)?status'
                            + _BOX_Q_SEP, re.A | re.I)


# A typed answer that the procedure was not performed: "Procedure performed: No (patient refused).", "Exam
# completed? no" (round 4 release:8), "- Procedure performed: No", "Was the procedure performed? No", "Procedure
# performed<tab>No". The grammar's lead and the procedure's word, a done verb, a separator, then a denial that opens the
# value, whatever follows it.
_PERFORMED_ANSWERED_NO = re.compile(_BOX_Q_LEAD + _BOX_Q_NOUN + r'[ \t]+' + _BOX_Q_DONE + _BOX_Q_TODAY + _BOX_Q_SEP
                                    + _BOX_Q_DENIAL + r'(?![0-9A-Za-z_])', re.I)


# The question whether the procedure was done, answered with boxes: "Procedure completed: ☐ Yes ☒ No".
_PERFORMED_QUESTION = re.compile(_BOX_Q_LEAD + _BOX_Q_NOUN + r'[ \t]+' + _BOX_Q_DONE + _BOX_Q_TODAY
                                 + r'(?:' + _BOX_Q_SEP + r')?', re.I)


def _performed_answer_denies(an: Analysis, ls: int, le: int) -> bool:
    """Whether the line [ls, le) asks whether the procedure was done and its boxes answer anything but a plain Yes
    (No checked, Yes unchecked, both, or an unread mark: _group_state). Round 4, BOXES' residual. Read once per line
    (round 5 bounded:3: every sentence of a long line asked it again, and each read the whole line's boxes)."""
    key = ('performed-answer', ls, le)
    if key not in an.memo:
        question = _PERFORMED_QUESTION.match(an.text, ls, le)
        if question is None:
            an.memo[key] = False
        else:
            _, boxes = _box_tokens(an, question.end(), le)
            an.memo[key] = bool(boxes) and _group_state(an.text, boxes) != 'on'
    return an.memo[key]


# Round 4d BOXES3 (round 6 declared:9): the typed done-question with a service's own name as its noun ("Was the EUS
# performed today? No", "EUS performed? No", "Colonoscopy completed: No", "Was the EUS with FNA performed today? No"),
# in the grammar's lead, verb, separator and denial. _BOX_Q_NOUN names only the procedure's own words, so such a line
# read 'uncertain: ?' (a hedge, no doubt) and the procedure line's section evidence released the family. The noun is
# at most 60 characters and holds no separator, and the denial is the whole answer: the line ends after it, or a
# punctuation mark, a dash or a parenthesis follows ("No.", "No - the patient had eaten", "No (patient declined)").
# A word straight after it is a description, not an answer ("Colonoscopy performed: no polyps were seen", "EGD
# performed - no complications": _B3_ASKED_END).
_B3_ASKED_END = r'(?=[ \t]*(?:[.,;:!(\u2013\u2014-]|\Z))'
_B3_SERVICE_ANSWERED_NO = re.compile(_BOX_Q_LEAD + r'(?P<noun>[A-Za-z](?:[^\n?:=|\t.;]|\.(?=\S)){0,59}?)[ \t]+' + _BOX_Q_DONE + _BOX_Q_TODAY
                                     + _BOX_Q_SEP + _BOX_Q_DENIAL + r'(?![0-9A-Za-z_])' + _B3_ASKED_END, re.I)
_B3_ASKED_NO = 'uncertain: the line \'{}\' asks whether the service it names was done and answers no'
# A noun qualified as earlier asks about another time, not today's service (round 4d integration, BOXES3 verifier's new
# problem 3: "Prior colonoscopy performed? No" under Indication held today's colonoscopy). The noun also ends at a
# sentence end or a semicolon (new problem 4: "Colonoscopy to the cecum. Biopsy done? No"); a period inside an
# abbreviation ("E.U.S.") does not end it.
_B3_EARLIER_NOUN = re.compile(r'(?:(?:any|the|a|your|her|his|their)\s+)?(?:prior|previous|last|earlier|past|preceding|'
                              r'former|old)\b', re.I)


def _B3_asked_no(an: Analysis, start: int, end: int) -> Optional[str]:
    """The hold of a passage within the question of a typed done-question that names a service and answers it with a
    denial (_B3_SERVICE_ANSWERED_NO: the passage lies inside the line's noun and that noun names a service), or None.
    A hold with doubt (_box_reading), so the service named is held wherever its family's section evidence stands; the
    question's own "?" was read as a hedge, which is no doubt. Matched once per line, from its start."""
    line_start, line_end = _B3_line(an, start)
    if end > line_end:
        return None
    key = ('b3-asked', line_start)
    if key not in an.memo:
        an.memo[key] = None
        found = _B3_SERVICE_ANSWERED_NO.match(an.text, line_start, line_end)
        if (found is not None and an.services_in(*found.span('noun'))
                and not _B3_EARLIER_NOUN.match(an.text, *found.span('noun'))):
            an.memo[key] = found.span('noun')
    noun = an.memo[key]
    if noun is None or not (noun[0] <= start and max(end, start + 1) <= noun[1]):
        return None
    return _B3_ASKED_NO.format(_B3_shown_line(an, start, end))


def _B3_label_hold_unread(an: Analysis, start: int, end: int) -> Optional[str]:
    """box2:L's hold (_B2_label_hold: a status line whose hold word has its own box checked, "Colonoscopy: ☒ Incomplete
    ☐ Completed") of a passage its own words and section leave uncertain with no doubt: a status row outside a positive
    section ("Procedure: Colonoscopy" / "Indication: Screening." / "Colonoscopy: ☒ Pending ☐ Completed"). box2:L is read
    only where the passage would otherwise read performed, so such a row read 'no performance evidence' and the
    procedure line's section evidence released the family, where the same row straight under the procedure line holds
    it (round 6 declared:9's mechanism: the hold read only after a performed reading). A hold with doubt, nothing else."""
    if not _BOX.search(an.text, max(0, start - BOX_REACH), min(len(an.text), max(end, start + 1) + BOX_REACH)):
        return None
    hold = _B2_label_hold(an, start, end)
    if hold is None:
        return None
    own = _cue_reading(an, start, end) or _default_reading(an, start, end)
    return hold if own.status == 'uncertain' and not own.doubt else None


def _calls_off(an: Analysis, ks: int, ke: int) -> bool:
    """Whether the sentence [ks, ke) is a status line or a typed or boxed answer that denies the service, or says the
    procedure was called off."""
    text = an.text
    line = text.rfind('\n', 0, ks) + 1  # the answer's label may be a heading, read as a sentence of its own
    line_end = text.find('\n', ks)
    line_end = len(text) if line_end < 0 else line_end
    return ((_status_line(an, ks, ke) and _denies(an, ks, ke, bare=False))
            or bool(_PERFORMED_ANSWERED_NO.match(text, line, ke)) or _performed_answer_denies(an, line, line_end)
            or _procedure_called_off(an, ks, ke))


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
# Round 4c declared:6: after any list marker the other readers strip (_LEADING_MARK's bullets, "1.", "2)", "(1)",
# "b."), and with parentheses in its words ("Procedure(s) not performed:", "Cancelled procedures (patient request):").
# Round 4d declared:7: any number of words before and after the denial ("The following procedures were not performed:",
# "Procedures not performed today due to patient refusal of sedation:"); the label is bounded by its length, 80
# characters, at every reader, never by an undeclared word count.
_SEC_LABEL_MARK = (r'(?:[-*\u2022\u00b7\u25aa\u25e6\u25cf\u2023\u2043\u2013\u2014][ \t]*|\(?\d{1,3}[.)][ \t]*'
                   r'|\(?[A-Za-z][.)][ \t]+)')
_DENYING_LABEL = re.compile(r'[ \t]*' + _SEC_LABEL_MARK + r'?(?:[A-Za-z][\w/()-]*[ \t]+)*?(?:not[ \t]+(?:performed|done)|'
                            r'cancell?ed|deferred|declined)(?:[ \t]+[\w/()-]+)*[ \t]*:[ \t]*', re.A | re.I)
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
                if len(words) <= 80 and (_DENYING_LABEL.fullmatch(text, ls, le) or _P2_boxed_denying_label(text, ls, le)):
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
                                 procedure=an.lay.section_at(m.start).kind == 'procedure', target=(ts, te))
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
    (round 4 routing:5), named apart from it: then a time after it may be that service's, so it holds the target rather
    than dating it ("Colonoscopy ... after a normal EGD performed last week"). Outside a procedure, findings or technique
    section a service coordinated with the first one by _CONNECTOR alone ("History of present illness: EGD and
    colonoscopy last month were unremarkable.") shares its time, as at R4B-BASE (round 5 regression:6); in today's
    procedure text it still holds ("Procedure: Colonoscopy, EGD last week was normal.")."""
    services = [m for s, e in sorted(members) for m in an.services_in(s, e) if m.kind == 'service']
    at_anchor = [m for m in services if m.end == anchor]
    if not (services and at_anchor) or at_anchor[-1].family == services[0].family:
        return False
    if an.lay.section_at(at_anchor[-1].start).kind in POSITIVE_SECTIONS:
        return True
    first, last = (services[0].start, services[0].end), (at_anchor[-1].start, at_anchor[-1].end)
    return not any(first in group and last in group
                   for group in _merge_groups(an.text, sorted({(m.start, m.end) for m in services})))


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
    mday = m.group('mday') or m.group('mday2') or m.group('mayday')  # "on May 3" (round 5 declared:7)
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
            if status in _B2_DENYING_STATUSES:  # round 4c-2 box2:I: an option's own words, read by its own box
                read = _B2_option_words(an, cue.start, cue.end, ts, te, cue.text, status)
                if read is not None:
                    found += read
                    continue
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
        for label, past, (ns, ne) in negations:  # round 4c-2 box2:I: "Colonoscopy: Not performed ☐ | Performed ☒"
            read = _B2_option_words(an, ns, ne, ts, te, label.split(': ', 1)[-1], 'negated')
            found += [('negated', label, past, False)] if read is None else read
        pre_cues, had = _pre_cues(an, _pre_start(an, cs, ms), ms)
        found += pre_cues
        if had is not None and not today:
            found.append(had)
        for status, entries in () if post is LIST_TAIL else (('incomplete', cues.INCOMPLETE_POST),
                                                              ('uncertain', cues.UNCERTAIN_POST)):
            for name, pattern in entries:
                m = pattern.search(post)
                if m:
                    where = _masked_map(an, me, ce)[1]  # round 4c-2 box2:I: "Colonoscopy: Incomplete ☐ | Completed ☒"
                    read = _B2_option_words(an, where[m.start()], where[m.end()], ts, te, _said(m), status)
                    found += [(status, f'{status}: {_said(m)}', False, name == 'pending')] if read is None else read
    return found


def _section_label(section) -> str:
    heading = f' ({section.heading.text.rstrip(":").strip()})' if section.heading else ''
    return f'section: {section.kind}{heading}'


# A plan-section passage whose clause says today is held, never planned and never performed (validation:1; round 4,
# routing:1 and routing:3). Round 3b also released an explicit past-tense performance that said today as performed;
# round 4 found it firing on another thing's past tense ("the MRI that was done this morning"), so it was withdrawn.
PLAN_TODAY = 'uncertain: its clause says today, so its plan section does not make it planned'


def _SEC_phrase_section(an: Analysis, section) -> bool:
    """Whether ``section`` is the 'other' section a colon-less phrase line opened inside a procedure, findings or
    technique section (sections, round 4 structure:4; round 4c sections:2, sections:4)."""
    return (section.kind == 'other' and section.heading is not None
            and gi_sections._sec_phrase_heading(an.text, (section.kind, section.label, section.heading)))


def _SEC_listed_under(section) -> str:
    return (f"uncertain: listed under '{section.heading.text.strip()[:80]}', a line that may tell another time or a "
            'plan')


_SEC_AFTER_A_PLAN_LABEL = ("uncertain: it follows a plan label with an answer of its own ('Referral:', 'Orders:', "
                           "'To do:'), so it may name what is still to be done")


def _SEC_hold_cue(an: Analysis, section) -> Optional[str]:
    """The cue of the hold every line takes in an 'other' section that holds what it lists: under a colon-less phrase
    line inside a procedure, findings or technique section (sections, round 4 structure:4; round 4c sections:2, :4),
    or after one of round 3b's plan labels with an answer of its own (round 4c regression:2, sections:5)."""
    if section.kind == 'other' and section.label == gi_sections._SEC_PLAN_HELD_LABEL:
        return _SEC_AFTER_A_PLAN_LABEL
    return _SEC_listed_under(section) if _SEC_phrase_section(an, section) else None


_SEC_NEXT_LINE = re.compile(r'\n[ \t]*(?:\n[ \t]*)?[^\n]*')  # the first line under a label that is not blank, or the next
_SEC_ANSWER_REACH = 200  # how much of that line is read for a negation word (bounds the work per span)


def _box_checked_in_every_reading(an: Analysis, start: int, end: int) -> bool:
    """Whether a checked box governs [start, end) in every reading of its row: _box_state is 'on' and, on a row that
    pairs both ways, both readings give the item that checked box. One reading alone ("Biopsy: ☒ Cold snare
    polypectomy": the box trails Biopsy or leads the snare) keeps _box_state's 'on' - the row reads as every tree read
    it outside a performed-today label - but is no proof enough to lift a hold that only an item's own box lifts
    (round 4d integration: the BOXES3 verifier's new problem 6, where it released round 4c's performed-today hold)."""
    return _box_state(an, start, end) == 'on' and not an.memo.get(('box-one-reading', start, end), False)


def _SEC_today_label_hold(an: Analysis, section, start: int, end: int) -> Optional[str]:
    """A cue holding [start, end) when only its procedure section would read it performed, and that section was opened
    by one of round 3b's performed-today labels ("Procedures performed today:") over any section but a procedure,
    findings or technique one (a plan, a history, an examination, an impression, an indication, an 'other' heading, the
    text before the first heading), below the label's own line (round 4c sections:1). The label may answer none in any
    words ("None today", "No procedures performed", "None. EGD to be scheduled"), and then the item after it is planned
    or silent (R3B-BASE: excluded under a plan, held elsewhere), never performed; no word list tells, so the line is
    held, with or without a performance cue of its own (_cue_reading). The label's own line and its sentence keep their
    reading, and so does an item its checked box governs (round 3 contract:8: "Procedures performed today:" then "[x]
    Flexible sigmoidoscopy to 30 cm"), read through the box vocabulary's own reader (_box_state)."""
    if section.kind != 'procedure' or section.label not in gi_sections._SEC_TODAY_LABELS or section.heading is None:
        return None
    text = an.text
    line_end = text.find('\n', section.heading.end)
    line_end = len(text) if line_end < 0 else line_end
    index = bisect.bisect_right(an.lay.section_starts, section.start) - 1
    if index > 0 and an.lay.sections[index - 1].kind in POSITIVE_SECTIONS:
        # after a procedure, findings or technique section, only a label whose answer (its value, or the first line
        # under a bare label) carries an unresolved negation word ("None today", "No procedures performed"): there it
        # doubted the next line at R3B-BASE, inside the section in force
        answer_end = line_end
        if not text[section.heading.end:line_end].strip():
            nxt = _SEC_NEXT_LINE.search(text, line_end, min(len(text), line_end + _SEC_ANSWER_REACH))
            answer_end = nxt.end() if nxt else line_end
        if not cues.DOUBT_TOKEN.search(text, section.heading.end, answer_end):
            return None
    if an.lay.sentence_for(start, end)[0] < line_end or _box_checked_in_every_reading(an, start, end):
        return None
    label = ' '.join(text[section.heading.start:line_end].split())[:80]
    return f"uncertain: listed after '{label}', a performed-today label that may answer none"


def _SEC_held_within(an: Analysis, start: int, end: int) -> Optional[str]:
    """The hold cue (_SEC_hold_cue) of the first section that [start, end) reaches into: a passage cited across a line
    break, from a findings line into a line held after a plan label ("The ascending colon polyp needs" then "EMR at a
    tertiary center."), reads as the held line does, never as the section it starts in."""
    lay = an.lay
    lo = max(bisect.bisect_right(lay.section_starts, start) - 1, 0)
    hi = bisect.bisect_left(lay.section_starts, max(end, start + 1))
    return next((cue for cue in map(lambda section: _SEC_hold_cue(an, section), lay.sections[lo:hi]) if cue), None)


# Round 4c-2 plan:A: a plan clause that says today and states the procedure's own RESULT ("EGD today showed esophagitis
# versus reflux.") carries PLAN_TODAY whatever hedge outranks it, as round 4c's validation:3 arm does for a performance
# statement: the hedge then speaks of the finding, not of whether the procedure was done. The result is stated by a
# reporting verb (_REPORTING, the verbs the continuation reader reads as reporting what the procedure found) straight
# after the service name; only further names (coordinated services, the interventions and landmarks it names), these
# joiners and a today phrase may stand between them. A hedged, conditioned or discussed plan names no result ("Possible
# EGD today if symptoms persist.", "Discussed colonoscopy today"), so it reads as before (round 3 validation:1).
_P2_RESULT_REACH = 120  # how far after a service's name its reporting verb is looked for (bounds the work per span)
_P2_RESULT_GAP = re.compile(r'[ \t,()/&+]*', re.A)
_P2_RESULT_JOINER = re.compile(r'(?:with|and|plus)\b|w/', re.A | re.I)


def _P2_says_today(an: Analysis, start: int, end: int) -> bool:
    """Whether a clause that [start, end) overlaps says today (cues.TODAY), as the plan arms of _cue_reading read it;
    memoised per clause, so a long clause naming many services is searched once, never once per mention."""
    for cs, ce in an.lay.clauses_for(start, end):
        key = ('p2-says-today', cs, ce)
        if key not in an.memo:
            an.memo[key] = bool(cues.TODAY.search(an.text, cs, ce))
        if an.memo[key]:
            return True
    return False


def _P2_states_its_result(an: Analysis, start: int, end: int) -> bool:
    """Whether a service named in [start, end) is followed in its own clause by a reporting verb (_REPORTING:
    "showed", "revealed", "demonstrated", "found", "noted", ...) with nothing between them but further names
    (_named_at), "with", "w/", "and", "plus" and a today phrase (cues.TODAY): "EGD today showed ...", "EGD with biopsies
    this morning revealed ...", "Today's EGD showed ...". Read within _P2_RESULT_REACH of each name."""
    text = an.text
    for m in an.services_in(start, max(end, start + 1)):
        limit = min(_clause_end(an, m.start, len(text)), m.end + _P2_RESULT_REACH)
        pos = m.end
        while pos < limit:
            pos = _P2_RESULT_GAP.match(text, pos, limit).end()
            step = _named_at(an, pos, limit) if pos < limit else None
            if step is None:
                joined = cues.TODAY.match(text, pos, limit) or _P2_RESULT_JOINER.match(text, pos, limit)
                step = joined.end() if joined else None
            if step is None:
                word = _NEXT_WORD.match(text, pos, limit)
                if word is not None and word.group(0).lower() in _REPORTING:
                    return True
                break
            pos = step
    return False


# Round 4c-2 plan:A2: an explicit performance statement that a hedge or a doubt in its clause outranks ("Anoscopy was
# performed and showed grade 2 internal hemorrhoids versus prolapse." under Assessment and plan) keeps only the hedge's
# labels, so validation saw no 'performed:' cue there and released the E/M beside it, which the unhedged statement holds
# (ARCHITECTURE 5.6). Where the unhedged statement would count for that hold (a plan section, an indication or chief
# complaint, a history section whose clause says today), the reading now carries this hold cue as well: its prefix is
# the stated-act prefix validation already counts in those sections (checks._VAL_OTHER_STATED_CUE, as OTHER_STATED is),
# and the labels _cue_reading keeps, the hedge first, are unchanged.
_P2_HEDGED_STATEMENT = ('uncertain: a procedure is stated by its act or its findings, and a hedge or doubt in its clause '
                        'outranks the performance statement')


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
    held = [STATUS_PRECEDENCE.index(f[4]) for f in found if len(f) > 4 and f[4] in STATUS_PRECEDENCE]
    if held and STATUS_PRECEDENCE.index(status) > min(held):
        status = 'uncertain'  # round 4c-2 box2:I: a hold keeps the rank of the option's words it stands for
    deciding = tuple(dict.fromkeys(f[1] for f in sorted((f for f in found if f[0] == status), key=lambda f: not f[3])))
    past = status == 'negated' and all(f[2] for f in found if f[0] == 'negated')
    doubt = status == 'uncertain' and any(f[3] for f in found if f[0] == 'uncertain')
    section = an.lay.section_at(start)
    hold = (_SEC_held_within(an, start, end) or _SEC_today_label_hold(an, section, start, end)
            if status == 'performed' and not em else None)
    if hold:
        # round 4c sections:0: under a phrase line ("Review of prior procedures"), or after a plan label with an answer
        # of its own (regression:2), or below a performed-today label opened over a section that is not a procedure,
        # findings or technique one (sections:1: "Past history:" then "Procedures performed today: None today" then
        # "EGD ... was performed." read historical at R3B-BASE), a line with its own performance cue is held like the
        # lines without one, never performed
        return Reading('uncertain', (hold,) + deciding, 'cue')
    if status == 'performed' and section.kind == 'history':
        today = any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(start, end))
        return Reading('uncertain' if today else 'historical', deciding + (_section_label(section),), 'cue')
    if status == 'performed' and section.kind == 'plan':
        today = any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(start, end))
        return Reading('uncertain', deciding + ((PLAN_TODAY,) if today else ()) + (_section_label(section),), 'cue')
    if status == 'uncertain' and section.kind == 'plan' and not em and any(f[0] == 'performed' for f in found) \
            and any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(start, end)):
        # round 4c validation:3: a hedge outranked the performance statement ("Anoscopy was performed today and showed
        # grade 2 internal hemorrhoids versus prolapse."), so the clause that says today carries PLAN_TODAY as the
        # performed arm above does, and validation holds the E/M beside it. A plan clause with no performance statement
        # ("Possible EGD today if symptoms persist.", "Discussed colonoscopy today") reads as before (round 3 validation:1,
        # round 2 review:1: its visit stays approvable).
        return Reading('uncertain', deciding + (PLAN_TODAY, _section_label(section)), 'cue', past, doubt)
    if status == 'uncertain' and section.kind == 'plan' and not em and _P2_says_today(an, start, end) \
            and _P2_states_its_result(an, start, end):
        # round 4c-2 plan:A: a plan clause that says today and states the procedure's result ("EGD today showed
        # esophagitis versus reflux.") holds as the unhedged clause does (PLAN_TODAY); the hedge is the finding's
        return Reading('uncertain', deciding + (PLAN_TODAY, _section_label(section)), 'cue', past, doubt)
    if status == 'uncertain' and not em and any(f[0] == 'performed' for f in found) and (
            section.kind in ('plan', 'indication') or (section.kind == 'history' and _P2_says_today(an, start, end))):
        # round 4c-2 plan:A2: a performance statement a hedge outranks still counts for the E/M hold where the unhedged
        # statement does (a plan section with no today word, an indication, a history clause that says today)
        return Reading('uncertain', deciding + (_P2_HEDGED_STATEMENT, _section_label(section)), 'cue', past, doubt)
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
        hold = _SEC_held_within(an, start, end) or _SEC_today_label_hold(an, section, start, end)  # round 4c
        if hold:
            return Reading('uncertain', (hold, label), 'cue')
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
    hold = _SEC_hold_cue(an, section)
    if hold:
        # under a colon-less phrase line inside findings (sections, round 4 structure:4): it may tell another time or
        # a plan ("Surgical opinion for further management"), so what is listed under it is held, never silent; and the
        # same after a plan label with an answer of its own (round 4c regression:2, sections:5)
        return Reading('uncertain', (hold,), 'cue')
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
# An intervention with no box of its own, joined by "with", "w/", "plus" or ";" to a later item whose box is not checked
# ("Polypectomy with cold snare | ☐"): that box may govern the whole label, so the item is held (structure:16).
BOX_LATER = 'uncertain: a box later on its line may govern this item'
# A status reference that a box or an answer keeps from being read as its status (_references): the checked or unread
# box of another denying option on its line ("[ ] Completed [x] Cancelled [ ] Aborted"), and a status question answered
# with a denial ("Procedure cancelled: No"). Each is held, never read as cancelled or incomplete.
BOX_STATUS_OPTION = "uncertain: a status option on the line '{}' is checked or cannot be read"
BOX_STATUS_ANSWER = "uncertain: the status question '{}' is answered no, which is held and never read as that status"
# A passage naming no item on a status row every denying option of which has its own unchecked box ("Status: Completed ☒
# Aborted ☐ Cancelled ☐" cited whole): the row says nothing against the service, so its unchecked options' words are
# never read as a cancellation; held (round 5 regression:4).
BOX_STATUS_UNSELECTED = ("uncertain: the line '{}' is a status row whose denying options are all unchecked; it is not "
                         "read as that status")
BOX_REACH = 200  # a box governs only an item within this many characters of it, on its line (bounds the work per span)
# The option a box marks in a yes/no pair ("Biopsy taken: [x] Yes [ ] No", "Biopsy taken: Yes [ ] No [x]").
_OPTION_WORDS = r'(?:(?P<yes>yes|done|performed)|(?P<no>no|not[ \t]+done|not[ \t]+performed|none))'
_OPTION_AFTER = re.compile(r'[ \t]*' + _OPTION_WORDS + r'\b', re.A | re.I)
# Read back from a box, never across a line break (\Z, not $: "$" also matches before the newline that ends the
# search window, so the last word of the line above became the option label of a box opening the next line; round
# 4c-2 box2:H, as at d05326ef).
_OPTION_BEFORE = re.compile(r'\b' + _OPTION_WORDS + r'[ \t]*\Z', re.A | re.I)
# A "No" that labels a box is an option, not a negation of the item ("[x] Yes [ ] No"): it explains itself.
_BOX_TEXT = _BOX.pattern.replace('?P<off>', '?:').replace('?P<on>', '?:')
_NO_OPTION = r'(?:no|none|not[ \t]+done|not[ \t]+performed)'
_OPTION_LABEL = re.compile(r'(?:' + _BOX_TEXT + r')[ \t]*' + _NO_OPTION + r'\b|\b' + _NO_OPTION + r'[ \t]*(?:' + _BOX_TEXT
                           + r')', re.A | re.I)
# A box, an unread mark or a radio glyph right after or right before an option word, with only spaces, a colon or a
# cell bar between (_box_beside_a_mark: round 5 declared:8, regression:0).
_BOX_BESIDE_AFTER = re.compile(r'[ \t|:]*(?:(?:' + _BOX_TEXT + ')|' + _BOX_UNREAD.pattern + '|' + _BOX_RADIO.pattern + ')')
_BOX_BESIDE_BEFORE = re.compile(r'(?:(?:' + _BOX_TEXT + ')|' + _BOX_UNREAD.pattern + '|' + _BOX_RADIO.pattern
                                + r')[ \t|:]*\Z')  # never across a line break, as _OPTION_BEFORE (box2:H)
# What joins the items of one label ("Biopsy/polypectomy", "biopsy or polypectomy", "Biopsy, polypectomy"): a box
# after the label governs every item it names.
_LABEL_JOINER = re.compile(r'(?:[ \t\-/,&+()]|\b(?:and|or)\b)*', re.A | re.I)
# Boxes written next to each other with only spaces between them ("☒ ☐ Biopsy") are one item's; boxes in cells of
# their own ("Anoscopy | ☒ | ☐", a flattened "Done | Not done" table) are its options, and the first governs.
_BOX_RUN_GAP = re.compile(r'[ \t\u00a0]*')
BOX_RUN_LIMIT = 8  # boxes written next to each other for one item, read back at most (bounds the work per option)
_CELL_GAP = re.compile(r'[ \t\u00a0|:]*')  # what may open a sentence before its first box ("| ☐")
_LABEL_COLON = re.compile(r'[ \t\u00a0]*:[ \t\u00a0]*')  # between a label and the box after it ("Biopsy: ☐")


def _box_tokens(an: Analysis, lo: int, hi: int) -> tuple[list, list]:
    """The items and the boxes wholly inside [lo, hi). Items: (start, end) of service names, interventions and
    other procedures' names, overlapping ones merged. Boxes: (start, end, state), state 'off', 'on' or 'unread'. A bare
    radio glyph or an answer in parentheses is an unread mark only where [lo, hi) marks options (_box_option_marks).
    Memoised per window (round 4c-2 box2:I: the status-line readers read each window twice), and apart before and after
    routing names the other procedures (an.other_names); callers never change the lists."""
    key = ('box-tokens', lo, hi, bool(an.other_names))
    if key not in an.memo:
        an.memo[key] = _box_tokens_read(an, lo, hi)
    return an.memo[key]


def _box_tokens_read(an: Analysis, lo: int, hi: int) -> tuple[list, list]:
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
    positional = _box_option_marks(an, lo, hi, marks)
    return items, sorted(marks + positional) if positional else marks


def _box_option_marks(an: Analysis, lo: int, hi: int, marks: list) -> list:
    """The bare radio glyphs and answers in parentheses of [lo, hi) that mark options, as unread marks: a radio glyph
    when another one is in [lo, hi), or when a box or bracketed mark is and the glyph does not open its line (a bullet
    does); an answer in parentheses when any of those is ("\u25cb Biopsy \u25cf Cold snare polypectomy", "( ) Biopsy (Y)
    Cold snare polypectomy"; never "\u25cf Biopsy", "\u25cf Biopsy \u2610" or "H. pylori (-)"). Marks inside brackets
    are the bracketed mark's."""
    text = an.text
    radios = list(_BOX_RADIO.finditer(text, lo, hi))
    answers = list(_BOX_PAREN_ANSWER.finditer(text, lo, hi)) if marks or radios else []
    if not radios and not answers:
        return []
    starts = [s for s, _, _ in marks]

    def bracketed(pos):  # inside a box or bracketed mark (marks are sorted and do not overlap)
        index = bisect.bisect_right(starts, pos) - 1
        return index >= 0 and pos < marks[index][1]

    def opens_its_line(pos):  # read back at most BOX_REACH characters: a line start further back is no opening
        newline = text.rfind('\n', max(0, pos - BOX_REACH), pos)
        return (newline >= 0 or pos <= BOX_REACH) and not text[newline + 1:pos].strip()

    radios = [m for m in radios if not bracketed(m.start())]
    if len(radios) < 2:
        radios = [m for m in radios if marks and not opens_its_line(m.start())]
    found = [(m.start(), m.end(), 'unread') for m in radios]
    if marks or found:
        found += [(m.start(), m.end(), 'unread') for m in answers if not bracketed(m.start())]
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
    remarks that no box governs ("... | ☒ | clip placed after polypectomy"). 'both' when the boxes would lead by that
    rule but the first box does not come straight after the opening label's colon or a linking word, or the opening
    label is an item's name and not a service's ("Biopsy: ☐ Cold snare polypectomy", round 6 declared:8), and every box
    also comes straight after an item ("Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒ clip placed"): either reading
    fits, so _box_state holds the items they disagree about (structure:0)."""
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
            lead = followed and (by_service or by_label) and not labelled
            plain = _BOX_LEAD_GAP.fullmatch(text, label_end, boxes[0][0])
            # round 4d BOXES3 (round 6 declared:8): a colon after an item's own name opening the row is no plain lead
            # ("Biopsy: ☐ Cold snare polypectomy"): "Biopsy: ☐" is the declared trailing layout, so where the boxes
            # also trail their items both readings fit; a service's name ("Colonoscopy: [ ] biopsy") still leads
            if lead and (not plain or not by_service) and _box_trails_fit(text, items, boxes):
                an.memo[key] = 'both'  # an item the two readings disagree about is held (structure:0, _box_state)
            else:
                an.memo[key] = 'lead' if lead else 'trail'
    return an.memo[key]


# Where boxes plainly lead the items after them: the first box comes straight after the opening label's colon or a
# linking word ("Colonoscopy: [ ] biopsy [x] cold snare", "Colonoscopy with ☐ biopsy ☒ cold snare").
_BOX_LEAD_GAP = re.compile(_BOX_RUN_GAP.pattern + r'(?::|with\b|w/|including\b)' + _BOX_RUN_GAP.pattern, re.I)
# What may stand between an item and a box that trails it: spaces, a colon or a cell boundary ("Biopsy ☐", "Biopsy: ☐",
# "Biopsy | ☐").
_BOX_TRAIL_GAP = re.compile(_BOX_RUN_GAP.pattern + r'(?:[:|]' + _BOX_RUN_GAP.pattern + ')?')


def _box_trails_fit(text: str, items: list, boxes: list) -> bool:
    """Whether every box of a segment (the first of each run) comes straight after an item, so that the boxes may trail
    their items as well as lead the next ones ("Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒ clip placed",
    "Colonoscopy - Biopsy ☐ ...", "Colonoscopy ☒ Biopsy ☐ ..."). Items are sorted and do not overlap."""
    ends = [e for _, e in items]
    for i, (s, _, _) in enumerate(boxes):
        if i and _BOX_RUN_GAP.fullmatch(text, boxes[i - 1][1], s):
            continue
        index = bisect.bisect_right(ends, s) - 1
        if index < 0 or not _BOX_TRAIL_GAP.fullmatch(text, ends[index], s):
            return False
    return True


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
    disagree), 'unknown' (a box this reader cannot read), 'unclear' (a box later on its line may govern it:
    _box_trail_state), or None when no box governs it. A box governs items on its
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
                result = _box_lead_state(text, boxes, span_end)
            elif orientation == 'trail':
                result = _box_trail_state(an, items, boxes, start, end, hi)
            else:  # 'both' (structure:0): the readings agree, or the item is held as boxes that disagree
                led = _box_lead_state(text, boxes, span_end)
                trailed = _box_trail_state(an, items, boxes, start, end, hi)
                if led == trailed or (led in (None, 'on') and trailed in (None, 'on')):
                    result = led or trailed
                    # round 4d integration (BOXES3 verifier, new problem 6): a checked box only one reading gives the
                    # item ("Biopsy: ☒ Cold snare polypectomy": the box trails Biopsy or leads the snare) is no proof
                    # the item itself was checked (_box_checked_in_every_reading)
                    if led != trailed:
                        an.memo[('box-one-reading', start, end)] = True
                elif 'unknown' in (led, trailed):
                    result = 'unknown'  # round 4d BOXES3: a reading gives it the unread mark: held as unread
                else:
                    result = 'mixed'
        an.memo[key] = result
    return an.memo[key]


def _box_lead_state(text: str, boxes: list, span_end: int) -> Optional[str]:
    """Leading boxes: the state of the boxes nearest before the item (or inside the passage) ending at ``span_end``,
    with the boxes written next to them."""
    before = [b for b in boxes if b[0] < span_end]
    if not before:
        return None
    run = [before[-1]]
    for b in reversed(before[:-1]):
        if not _BOX_RUN_GAP.fullmatch(text, b[1], run[0][0]):
            break
        run.insert(0, b)
    return _run_state(run)


# What joins an intervention to a later item of the same label without making them one label ("Polypectomy with cold
# snare", "Biopsy; polypectomy", "Biopsy plus polypectomy"): a box after the later item may govern both (structure:16).
_BOX_LINK = re.compile(r'[ \t]*(?:with\b|w/|plus\b|;)[ \t]*', re.I)


def _box_trail_state(an: Analysis, items: list, boxes: list, start: int, end: int, hi: int) -> Optional[str]:
    """Trailing boxes: the state of the boxes after the label of the item at [start, end), before the next item (a
    yes/no pair read by the option it marks). An intervention with no box of its own, joined by _BOX_LINK words to a
    later item whose own box is not checked, is 'unclear' (BOX_LATER): that box may govern the whole label. A service
    name is described by its interventions ("Colonoscopy with biopsy ☐"), as round 3b pinned, so it is not held."""
    text, span_end = an.text, max(end, start + 1)
    items = sorted(set(items) | {(start, end)})
    index = items.index((start, end))
    label_end = max(span_end, _label_end(text, items, index))
    after = next((s for s, _ in items if s >= label_end), hi)
    group = [b for b in boxes if start <= b[0] < after]
    if group:
        return _group_state(text, group)
    if an.services_in(start, span_end):
        return None
    item_starts = [s for s, _ in items]
    first = bisect.bisect_left(item_starts, label_end)
    for later in range(first, min(len(items), first + OTHER_BOX_ITEMS)):  # a label joins few items (bounds the work)
        later_start = items[later][0]
        if not _BOX_LINK.fullmatch(text, label_end, later_start):
            return None
        label_end = max(items[later][1], _label_end(text, items, later))
        after_index = bisect.bisect_left(item_starts, label_end)
        later_after = items[after_index][0] if after_index < len(items) else hi
        later_group = [b for b in boxes if later_start <= b[0] < later_after]
        if later_group:
            return None if _group_state(text, later_group) in (None, 'on') else 'unclear'
    return None


def _unchecked_box(an: Analysis, start: int, end: int) -> bool:
    """Whether the item at [start, end) is governed by an unchecked box in its own line or cell (_box_state)."""
    return _box_state(an, start, end) == 'off'


def _other_names_in(an: Analysis, start: int, end: int) -> tuple:
    names = an.other_names
    low, high = bisect.bisect_left(names, (start, -1)), bisect.bisect_left(names, (end, -1))
    return tuple(name for name in names[low:high] if name[1] <= end)


# What may stand between one item's options ("☐ Not done ☒ Not performed", "☐ Not done | ☒ Not performed", "Not done ☐
# / Not performed ☒"), and the label of an option that is no yes/no word ("☐ Not done ☐ Completed ☒ Not performed"):
# anything else (another item's label, "Biopsy: ☒ Yes ☐ No  Cold snare polypectomy: ☐ Yes ☒ No") ends the item's own
# options (_B3_later_denial_checked).
_B3_OPTION_GAP = re.compile(r'[ \t\u00a0|,;/]*')
_B3_OPTION_LABEL = re.compile(r'[^:\n]{0,40}')


def _B3_later_denial_checked(text: str, marks: list) -> bool:
    """Whether, among an item's own options (the option boxes ``marks``, (box, its yes/no word or None) as _group_state
    reads them, written one after another with only _B3_OPTION_GAP after an option's word, or a short label with no
    colon in place of a word), a denial option after the first one is checked while the first is not: "Cold snare
    polypectomy: ☐ Not done ☒ Not performed", "☒ Yes ☐ Not done ☒ Not performed", "☐ Not done ☐ Completed ☒ Not
    performed". _group_state read only the first denial option, so the checked one was never read and the item read
    performed where every base excluded it (round 6 declared:11): the boxes for the item disagree."""
    after = marks[0][1].start() >= marks[0][0][1]
    first_no = None
    for at, (box, word) in enumerate(marks):
        if at:
            previous_box, previous_word = marks[at - 1]
            if after:
                gap, pattern = ((previous_word.end(), box[0]), _B3_OPTION_GAP) if previous_word is not None else (
                    (previous_box[1], box[0]), _B3_OPTION_LABEL)
            else:
                gap, pattern = ((previous_box[1], word.start()), _B3_OPTION_GAP) if word is not None else (
                    (previous_box[1], box[0]), _B3_OPTION_LABEL)
            if gap[0] > gap[1] or not pattern.fullmatch(text, *gap):
                return False
        if word is not None and word.group('no'):
            if first_no is None:
                first_no = box
            elif box[2] == 'on':
                return first_no[2] != 'on'
    return False


def _group_state(text: str, group: list) -> Optional[str]:
    """The boxes after an item, up to the next item: the first one (with the boxes written next to it) governs,
    unless they mark yes/no options. Then the item is denied when "No" is checked or "Yes" is not, and held ('mixed')
    when both are checked, or when a later denial option of the item's own is checked while the first is not and no
    unchecked "Yes" denies it ("☐ Not done ☒ Not performed", "☒ Yes ☐ Not done ☒ Not performed": round 4d BOXES3,
    _B3_later_denial_checked)."""
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
    if no is not None and no[2] != 'on' and (yes is None or yes[2] == 'on') and _B3_later_denial_checked(text, marks):
        return 'mixed'  # round 4d BOXES3 (round 6 declared:11): "☐ Not done ☒ Not performed": a later denial checked
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
# A denying value is a box state, a selected denial ("No", "None", "Not done", "Not performed"), or a short answer this
# reader cannot read as done or not done ("N", "0", "N/A"); _box_field_answer decides what each says of the label.
_FIELD_DENIED = re.compile(r'(?P<label>[^\n]{1,120}?):[ \t]*(?:'
                           r'(?P<box>not[ \t]+checked|unchecked|no[ \t]+option[ \t]+selected)'
                           r'|(?P<answer>no|none|not[ \t]+done|not[ \t]+performed)|(?P<unclear>n/a|na|n|0))[ \t.]*',
                           re.A | re.I)
_FIELD_CHECKED = re.compile(r'(?P<label>[^\n]{1,120}?):[ \t]*(?:checked|yes)[ \t.]*', re.A | re.I)
_BLANK_LINE = re.compile(r'\n[ \t]*\n')
_LEADING_MARK = re.compile(r'(?:[-*\u2022\u00b7\u25aa\u25e6\u25cf\u2023\u2043\u2013\u2014]|\(?\d{1,3}[.)]|\(?[a-z][.)]'
                           r'(?=\s)|' + _BOX_TEXT + '|' + _BOX_UNREAD.pattern + r')\s*', re.I)
_TRAILING_BOX = re.compile(r'(?:' + _BOX_TEXT + '|' + _BOX_UNREAD.pattern + r')$')
FIELD_LABEL_CHARS = 200  # a printed line or cell longer than this never equals a field's label (bounds the work)
FIELD_UNTIED = "uncertain: the form field '{}' says its item was not done, and no printed line on its page names it"
FIELD_PAGE = ("uncertain: the form field '{}' says this item was not done, but the page it is on cannot be told from "
              "the pages before it")
# Round 4 (structure:6, structure:7, contract:2, evidence:4, contract:4, release:12): a "No" or "None" denies or holds
# only an item its label names or a field with a widget's default name; one whose label names the item among other
# words ("Flexible sigmoidoscopy in the last 10 years: No"), and a short answer ("Biopsy (Y/N): N"), hold it; a status
# field that gives no completion holds its page.
BOX_FIELD_HELD = ("uncertain: the form field '{}' answers for this item in a way this reader cannot read as done or "
                  "not done")
BOX_FIELD_HELD_UNTIED = ("uncertain: the form field '{}' answers for an item on its page in a way this reader "
                         "cannot read as done or not done, and no printed line on its page names it")
BOX_FIELD_ANSWER_UNTIED = ("uncertain: the form field '{}' may answer for an item on its page, and no printed line "
                           "on its page names it")
BOX_FIELD_STATUS = "uncertain: the form field '{}' gives the procedure on its page a status other than completed"


@dataclass(frozen=True)
class _Named:
    start: int
    end: int
    state: str  # 'off' (a denying field line names it) | 'on' (a checked one) | 'held' (_box_field_answer) | 'mixed'
    exact: bool  # its page's printed text is known exactly
    line: str  # the field line, as written


@dataclass(frozen=True)
class _FieldPage:
    start: int  # the page's printed text, as far as it can be told: from the end of the previous block
    end: int  # the end of the page's form-field block
    unmatched: str  # the first denying field line whose label names nothing printed on the page ('' for none)
    cue: str = FIELD_UNTIED  # the hold the page gives its items, with that line in it


@dataclass(frozen=True)
class _Fields:
    denying: tuple  # _Named spans of the denying field lines themselves, sorted
    named: tuple  # _Named printed lines and cells, sorted
    pages: tuple  # _FieldPage of each form-field block with an unmatched denying line, sorted
    denying_starts: tuple = ()
    named_starts: tuple = ()
    page_starts: tuple = ()
    held: tuple = ()  # _Named spans of the field lines that hold their item ('held'), sorted
    held_starts: tuple = ()
    checked: tuple = ()  # _Named spans of the checked or Yes field lines: silent, never held by their page
    checked_starts: tuple = ()
    untied: tuple = ()  # _FieldPage of each block with any denying or answering line that names nothing printed
    untied_starts: tuple = ()
    answers: tuple = ()  # _Named printed questions a status-question field answers with a denial (declared:1), sorted
    answer_starts: tuple = ()


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
    held instead of negated. What a denying line says of its label is _box_field_answer's; a label names a printed line
    or cell that equals it, an option row it opens, or an item a printed row's boxes delimit (_box_label_candidates).
    A status field that gives the procedure no completion holds its page (contract:4); every denying or answering
    line that names nothing printed is recorded for the separately identifiable E/M statement
    (_box_attestation_refused)."""
    key = ('form-fields',)
    if key not in an.memo:
        text = an.text
        headers = list(FORM_HEADER.finditer(text))
        denying, held, checked, named, pages, untied, answers = [], [], [], [], [], [], []
        previous_end, previous_page = 0, 0
        for i, header in enumerate(headers):
            limit = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            blank = _BLANK_LINE.search(text, header.end(), limit)
            block_end = blank.start() if blank else limit
            page = int(header.group(2))
            if header.group(1) == 'form fields':
                exact = page == previous_page + 1
                labels: dict = {}  # label key -> (state, its first line, the hold its page takes when it names nothing)
                answered: dict = {}  # label key -> its first denying or answering line, whatever its label names
                questions: dict = {}  # label key -> its first line, for a status question answered with a denial
                status = ''  # the first status field that gives the procedure no completion
                for line in re.finditer(r'[^\n]+', text[header.end():block_end]):
                    words = line.group(0)
                    at = header.end() + line.start()
                    if not status and _box_status_field(an, at, at + len(words)):
                        status = words.strip()
                    denied = _FIELD_DENIED.fullmatch(words)
                    is_checked = None if denied else _FIELD_CHECKED.fullmatch(words)
                    if is_checked:
                        checked.append(_Named(at, at + len(words), 'on', exact, words.strip()))
                        _box_label_state(labels, _label_key(is_checked.group('label')), 'on', words.strip(),
                                         FIELD_UNTIED)
                    if not denied:
                        continue
                    label = _label_key(denied.group('label'))
                    answered.setdefault(label, words.strip())
                    state, template = _box_field_answer(an, at, at + len(denied.group('label')), denied)
                    if not denied.group('box') and _box_status_question(an, at, at + len(denied.group('label'))):
                        questions.setdefault(label, words.strip())
                    if state is not None:
                        (denying if state == 'off' else held).append(_Named(at, at + len(words), state, exact,
                                                                             words.strip()))
                        _box_label_state(labels, label, state, words.strip(), template)
                found = set()
                if answered or labels:
                    wanted = set(answered) | set(labels)
                    for line in re.finditer(r'[^\n]+', text[previous_end:header.start()]):
                        at = previous_end + line.start()
                        offset = 0
                        for cell in line.group(0).split(' | '):
                            for candidates in _box_label_candidates(cell, at + offset):
                                matches = [(begin, part, _label_key(part)) for begin, part in candidates]
                                matches = [m for m in matches if m[2] in wanted]
                                for begin, part, label in matches:
                                    if label in labels:
                                        named.append(_Named(begin, begin + len(part), labels[label][0], exact,
                                                            labels[label][1]))
                                    if label in questions:
                                        answers.append(_Named(begin, begin + len(part), 'answer', exact,
                                                              questions[label]))
                                    found.add(label)
                                if matches:
                                    break
                            offset += len(cell) + 3
                unmatched = next(((line, template) for label, (state, line, template) in labels.items()
                                  if state != 'on' and label not in found), None)
                if status:
                    pages.append(_FieldPage(previous_end, block_end, status, BOX_FIELD_STATUS))
                elif unmatched is not None:
                    pages.append(_FieldPage(previous_end, block_end, *unmatched))
                untied_line = next((line for label, line in answered.items() if label not in found), '')
                if untied_line:
                    untied.append(_FieldPage(previous_end, block_end, untied_line))
            previous_end, previous_page = block_end, page
        for spans in (denying, held, checked, named, answers):
            spans.sort(key=lambda n: n.start)
        an.memo[key] = _Fields(tuple(denying), tuple(named), tuple(pages), tuple(n.start for n in denying),
                               tuple(n.start for n in named), tuple(p.start for p in pages), tuple(held),
                               tuple(n.start for n in held), tuple(checked), tuple(n.start for n in checked),
                               tuple(untied), tuple(p.start for p in untied), tuple(answers),
                               tuple(n.start for n in answers))
    return an.memo[key]


def _box_label_state(labels: dict, label: str, state: str, line: str, template: str) -> None:
    """Record a field line's state for its label: lines for one label that disagree make it 'mixed'."""
    previous = labels.get(label)
    if previous is None:
        labels[label] = (state, line, template)
    elif previous[0] != state:
        labels[label] = ('mixed', previous[1], previous[2])


def _box_field_answer(an: Analysis, start: int, end: int, denied: re.Match) -> tuple[Optional[str], Optional[str]]:
    """(state, the hold of its page when its label names nothing printed) of a denying field line whose label is
    [start, end): a box state ('<label>: not checked') is 'off', whatever the label, as before; a selected "No", "None",
    "Not done" or "Not performed" is 'off' when the label names an item alone ("Biopsy", "Biopsy taken") or is a
    widget's default name ("Check Box1", "Text7"), 'held' when it names an item among other words ("Flexible
    sigmoidoscopy in the last 10 years", "Colonoscopy complications", "Biopsy (Y/N)"), and nothing when it names
    none ("Complications: None", "EBL: None", "Procedure cancelled: No"); a short answer this reader cannot read ("N",
    "0", "N/A") is 'held' when the label names an item, and nothing otherwise. (None, None): the line holds nothing.
    A selected denial whose label names nothing this reader knows holds nothing only when the label is known to name
    no item (_box_names_no_item); any other fails closed, 'held' (round 5 regression:1: "Polyps removed: No", "Cecum
    reached: No" and "FNA performed: No" name their item in other words, and untied they hold the page again)."""
    if denied.group('box'):
        return 'off', FIELD_UNTIED
    kind = _box_label_kind(an, start, end)
    if denied.group('answer'):
        if kind == 'other' and not _box_names_no_item(an, start, end):
            return 'held', BOX_FIELD_ANSWER_UNTIED
        return {'item': ('off', FIELD_UNTIED), 'generic': ('off', BOX_FIELD_ANSWER_UNTIED),
                'qualified': ('held', BOX_FIELD_HELD_UNTIED)}.get(kind, (None, None))
    return ('held', BOX_FIELD_HELD_UNTIED) if kind in ('item', 'qualified') else (None, None)


# Field labels known to name no item, so their "No" or "None" says nothing of a service (round 5 regression:1). A closed
# list, read whole: a label not on it fails closed. An optional "Any", "if any", a parenthesis ("(if any)", "(mL)") and
# the label's own "?" may stand with it.
_BOX_NO_ITEM_WORDS = (r'complications?|adverse[ \t]+events?|ebl|estimated[ \t]+blood[ \t]+loss|blood[ \t]+loss|sedation|'
                      r'anesthesia|anaesthesia|allerg(?:y|ies)|comments?|notes?|remarks?')
_BOX_LABEL_AFFIX = r'(?:[ \t]*(?:\([^()\n]{0,40}\)|if[ \t]+any))?[ \t]*\??'
_BOX_NO_ITEM_LABEL = re.compile(r'(?:any[ \t]+)?(?:' + _BOX_NO_ITEM_WORDS + ')' + _BOX_LABEL_AFFIX, re.A | re.I)
# The fields a line under the separately identifiable E/M statement may answer instead of it (round 5 declared:12): those,
# and the ordinary fields of a procedure report, with a participle ("Sedation given", "Teaching physician present").
# Read whole; any other label is the statement's answer.
_BOX_OWN_FIELD_LABEL = re.compile(r'(?:any[ \t]+)?(?:' + _BOX_NO_ITEM_WORDS + r'|bleeding|interpreter|teaching[ \t]+physician|'
                                  r'resident|disposition)(?:[ \t]+(?:given|used|present|involvement|involved|needed|'
                                  r'required|noted))?' + _BOX_LABEL_AFFIX, re.A | re.I)
# The words that make a line under the statement its answer, whatever else it names ("☐ I attest the colonoscopy
# note"): an attestation, agreement or confirmation, or the statement's own words.
_BOX_ATTEST_WORD = re.compile(r'\b(?:attest\w*|agree\w*|confirm\w*|acknowledg\w*|separate\w*|e/?m|e&m|modifier|'
                              r'significant\w*|identifiable)\b', re.A | re.I)


def _box_names_no_item(an: Analysis, start: int, end: int) -> bool:
    """Whether the field label [start, end), which names no service, intervention or procedure word, is known to name
    no item: a label on the closed list _BOX_NO_ITEM_LABEL ("Complications", "EBL", "Sedation"), or a status question
    the reference readers answer ("Procedure cancelled: No" holds there as a status answer, never by its field)."""
    if _BOX_NO_ITEM_LABEL.fullmatch(_label_key(an.text[start:end])):
        return True
    return _box_status_question(an, start, end)


def _box_status_question(an: Analysis, start: int, end: int) -> bool:
    """Whether the field label [start, end) asks after the procedure's status: it carries a status reference
    (_REFERENCE_PATTERNS: "Procedure cancelled", "Was the procedure aborted?"), which the reference readers read."""
    return any(pattern.search(an.text, start, end) for _, pattern in _REFERENCE_PATTERNS)


# A field label that is a widget's default name, not a question: "Check Box1", "Text 7", "Field3", "Group1".
_BOX_GENERIC_FIELD = re.compile(r'(?:check[ \t]*box|checkbox|text(?:[ \t]*field)?|field|group|radio(?:[ \t]*button)?|'
                                r'button|option|choice|drop[ \t]*down|combo[ \t]*box|list[ \t]*box|untitled|'
                                r'form[ \t]*field)[ \t]*\d*', re.A | re.I)
# The words an item's own question adds to its name ("Biopsy taken", "Was a polypectomy performed").
_BOX_ITEM_WORDS = frozenset(('taken', 'performed', 'done', 'completed', 'obtained', 'attempted', 'given', 'placed',
                             'today', 'was', 'were', 'a', 'an', 'the', 'any'))
_BOX_LABEL_WORD = re.compile(r"[A-Za-z0-9][\w/'-]*", re.A)


def _box_label_kind(an: Analysis, start: int, end: int) -> str:
    """What the field label [start, end) names: 'generic' (a widget's default name), 'item' (a service, an
    intervention or another procedure's word alone, with the words of its own question), 'qualified' (one among other
    words: a time, an attribute, a count), or 'other' (none)."""
    text = an.text
    if _BOX_GENERIC_FIELD.fullmatch(_label_key(text[start:end])):
        return 'generic'
    names = ({(m.start, m.end) for m in an.services_in(start, end)} | {(iv.start, iv.end) for iv in
                                                                       an.interventions_in(start, end)}
             | {m.span() for m in _PROCEDURE_WORD.finditer(text, start, end)})
    if not names:
        return 'other'
    rest = [w.group(0).lower() for w in _BOX_LABEL_WORD.finditer(text, start, end)
            if not any(s <= w.start() < e for s, e in names)]
    return 'item' if all(word in _BOX_ITEM_WORDS for word in rest) else 'qualified'


# A form field that asks whether the procedure was done, answered with a denial ("Procedure performed: No",
# "Procedure performed?: No", "Was the procedure performed?: No"): the typed done-question's own grammar (round 5
# declared:0), read from the field line's start.
_BOX_DONE_QUESTION = _PERFORMED_ANSWERED_NO


def _box_status_field(an: Analysis, start: int, end: int) -> bool:
    """Whether the form-field line [start, end) gives the procedure a status that is no completion: a status field
    whose value is not one of completion and holds or denies as a status line's would ("Procedure status: Cancelled -
    the patient had eaten breakfast", "Status: Not performed", "Status: Rescheduled"), or a question whether the
    procedure was done answered with a denial (contract:4). Its page's services are then held, wherever the field
    stands: extraction writes every field after its page's text, beyond the status readers' reach."""
    text = an.text
    if _BOX_DONE_QUESTION.match(text, start, end):
        return True
    # round 5's key on its own value, as before, and the shared grammar's (round 6 declared:4: a list marker, "?:", a
    # cell bar) on its own: either value holds the page. Read only after both separators, "Status: | Completed? No"
    # opened with a completion and held nothing (round 4d's verification), where round 5's value holds.
    for key in (_STATUS_KEY.match(text, start, end), _B3_STATUS_KEY.match(text, start, end)):
        if key is None:
            continue
        value = _SEPARATOR.match(text, key.end(), end).end()
        if value >= end or _STATUS_DONE.match(text, value, end):
            continue
        if (_STATUS_HOLD.match(text, value, end) or _bare_denial(an, value, end)
                or _value_calls_off(an, value, end)):
            return True
    return False


# The option row a field's label opens on its printed page ("Complications: ☐ Yes ☒ No", "Biopsy taken: [ ] Yes [x]
# No"): after the label's colon, only boxes, unread marks and option words.
_BOX_OPTION_VALUE = re.compile(r'(?:[ \t]*(?:(?:' + _BOX_TEXT + ')|' + _BOX_UNREAD.pattern + '|' + _BOX_RADIO.pattern
                               + r'|yes|no|none|done|not[ \t]+done|n/a))+[ \t.]*', re.I)
_BOX_MARK = re.compile('(?:' + _BOX_TEXT + ')|' + _BOX_UNREAD.pattern + '|' + _BOX_RADIO.pattern)


def _box_label_candidates(cell: str, base: int) -> list:
    """The ways a printed cell (at text offset ``base``) may give a form field its label, in order, each a list of
    (start, text): the whole cell ("Biopsy", "☐ Biopsy"); the label of an option row it opens ("Complications" of
    "Complications: ☐ Yes ☒ No"); the items its boxes delimit ("EGD", "Colonoscopy" of "☐ EGD ☒ Colonoscopy"). The first
    way that names a field is the cell's."""
    stripped = cell.strip()
    if not stripped or len(stripped) > 4 * FIELD_LABEL_CHARS:
        return []
    lead = len(cell) - len(cell.lstrip())
    found = [[(base + lead, stripped)]] if len(stripped) <= FIELD_LABEL_CHARS else []
    colon = stripped.find(':')
    if 0 < colon <= FIELD_LABEL_CHARS and _BOX_OPTION_VALUE.fullmatch(stripped, colon + 1):
        found.append([(base + lead, stripped[:colon])])
    marks = list(_BOX_MARK.finditer(stripped))
    if len(marks) >= 2:
        parts, previous = [], 0
        for mark in marks + [None]:
            stop = mark.start() if mark else len(stripped)
            part = stripped[previous:stop]
            if part.strip() and len(part.strip()) <= FIELD_LABEL_CHARS:
                parts.append((base + lead + previous + len(part) - len(part.lstrip()), part.strip()))
            previous = mark.end() if mark else stop
        found.append(parts)
    return found


def _within(spans: tuple, starts: tuple, start: int, end: int):
    """The span of ``spans`` (sorted by ``starts``, not overlapping) that holds [start, end), or None."""
    index = bisect.bisect_right(starts, start) - 1
    if index >= 0 and max(end, start + 1) <= spans[index].end:
        return spans[index]
    return None


def _box_reading(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """What the check boxes and form-field lines say of [start, end), or None when they say nothing: negated by an
    unchecked box or a denying field line (UNCHECKED); held when its boxes disagree, when a box cannot be read, when a
    box later on its line may govern it, when a field line answers for it in a way this reader cannot read, when a
    field line names it on a page that cannot be bounded, or when its page has a denying field line that names no
    printed item or a status field that gives no completion (and its own reading has no explicit performance cue and no
    checked box of its own). A checked field line itself stays silent. A field that answers for an item in a way this
    reader cannot read holds that passage only, with no doubt about its family's service: such an answer is about
    another time or attribute ("Flexible sigmoidoscopy in the last 10 years: No"), or one this reader cannot read.
    Round 4d BOXES3: the strict check-box rows are consulted first (_B3_hold): a passage of a row whose marks cannot be
    paired with its entries in exactly one way is held (uncertain, a doubt), never read by a box; where the row's own
    reading below already holds it, that hold and its cue stand. A row too long to pair is held without being read.
    Where the boxes say nothing, a passage inside the noun of a typed done-question that names a service and answers no
    ("Was the EUS performed today? No") is held with doubt (_B3_asked_no; round 6 declared:9)."""
    unpaired = _B3_hold(an, start, end)
    if unpaired is not None and _B3_long_row(an, start, end):
        return Reading('uncertain', (unpaired,), 'cue', doubt=True)
    reading = _B3_declared_box_reading(an, start, end)
    if unpaired is None and reading is None:
        asked = _B3_asked_no(an, start, end) or _B3_label_hold_unread(an, start, end)  # round 6 declared:9
        return None if asked is None else Reading('uncertain', (asked,), 'cue', doubt=True)
    if unpaired is None or (reading is not None and reading.status == 'uncertain'):
        return reading
    return Reading('uncertain', (unpaired,), 'cue', doubt=True)


def _B3_declared_box_reading(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """The declared box contract's reading of [start, end) (_box_reading, before round 4d's strict rows)."""
    state = _box_state(an, start, end)
    fields = _form_fields(an)
    one_line = an.text.find('\n', start, end) < 0
    named = _within(fields.named, fields.named_starts, start, end) if one_line else None
    if state == 'unknown' or _box_names_an_unread_item(an, start, end):
        return Reading('uncertain', (BOX_UNREAD,), 'cue', doubt=True)
    if state == 'unclear':
        return Reading('uncertain', (BOX_LATER,), 'cue', doubt=True)
    if named is not None and named.state == 'held':  # a hold of this passage, no doubt about its family's service
        return Reading('uncertain', (BOX_FIELD_HELD.format(named.line),), 'cue')
    if state == 'mixed' or (named is not None and (named.state == 'mixed' or state not in (None, named.state))):
        return Reading('uncertain', (BOXES_DISAGREE,), 'cue', doubt=True)
    if _B2_items_differ(an, start, end, state):  # round 4c-2 box2:G: a row of items in different box states, read whole
        return Reading('uncertain', (_B2_ITEMS_DIFFER,), 'cue', doubt=True)
    if state == 'off':  # round 4c-2 box2:I: the unchecked box it is read by may be an option's, not its own
        label = _B2_label_state(an, start, end)
        if label == 'on':
            state = 'on'  # "Colonoscopy" of "Colonoscopy: ☐ Cancelled ☒ Completed": read as its line's options say
        elif label == 'unpaired':  # round 4d BOXES3: its row's marks cannot be paired with certainty
            return Reading('uncertain', (_B3_hold(an, start, end),), 'cue', doubt=True)
        elif label == 'unknown':
            return Reading('uncertain', (BOX_UNREAD,), 'cue', doubt=True)
        elif label == 'across':
            return Reading('uncertain', (_B2_ROW_ACROSS,), 'cue', doubt=True)
        elif _B2_item_box_differs(an, start, end):
            return Reading('uncertain', (_B2_OPTION_BOX,), 'cue', doubt=True)
    elif state == 'on' and _B2_item_box_differs(an, start, end, 'off'):
        # "Not performed ☐ Biopsy ☒ Cold snare polypectomy ☐": read by the biopsy's ☒, its own box unchecked
        return Reading('uncertain', (_B2_OTHER_BOX,), 'cue', doubt=True)
    if _B2_runs_disagree(an, start, end, state):  # round 4c-2 box2:K: "Photos ☐ | Biopsy ☒ | Cold snare polypectomy ☐"
        return Reading('uncertain', (_B2_ROW_READINGS,), 'cue', doubt=True)
    if state == 'off' and _box_selected_denial(an, start, end):
        # round 4c-2 box2:H: a passage naming no item that selects a "Not performed" or "Not done" option ("☒ Not
        # performed") is held, as round 5 declared:8 holds the service it follows: it names nothing it could deny
        return Reading('uncertain', (BOX_STATUS_OPTION.format(_B3_shown_line(an, start, end)),), 'cue', doubt=True)
    if state == 'off' or _unchecked_state(an, start, end):
        return Reading('negated', (UNCHECKED,), 'cue')
    held = _within(fields.held, fields.held_starts, start, end) if one_line else None
    if held is not None:
        return Reading('uncertain', (BOX_FIELD_HELD.format(held.line),), 'cue')
    if named is not None and named.state == 'off':
        return Reading('uncertain', (FIELD_PAGE.format(named.line),), 'cue', doubt=True)
    if one_line and not _box_tokens(an, start, max(end, start + 1))[0] and _box_own_option_off(an, start, end):
        return Reading('uncertain', (BOX_STATUS_UNSELECTED.format(_B3_shown_line(an, start, end)),), 'cue', doubt=True)
    if state == 'on' or (one_line and _within(fields.checked, fields.checked_starts, start, end) is not None):
        return None
    pages = fields.pages
    index = bisect.bisect_right(fields.page_starts, start) - 1
    if index < 0 or start >= pages[index].end or not _names_an_item(an, start, end):
        return None
    cue = _cue_reading(an, start, end)
    if cue is not None or _default_reading(an, start, end).status not in ('performed', 'uncertain'):
        return None
    return Reading('uncertain', (pages[index].cue.format(pages[index].unmatched),), 'cue', doubt=True)


def _box_names_an_unread_item(an: Analysis, start: int, end: int) -> bool:
    """Whether the passage [start, end) names, besides itself, an item whose own box cannot be read ("☑ Cold snare
    polypectomy [?] Biopsy" cited whole): such a passage is held as unread. The unread mark's question mark is no
    hedge (_clause_cues), so a passage read by its first box would otherwise vouch for the item the mark governs
    (round 5 extraction:8). Read only where an unread mark is near."""
    text = an.text
    if not _BOX_UNREAD.search(text, max(0, start - BOX_REACH), min(len(text), end + BOX_REACH)):
        return False
    items = _box_tokens(an, start, max(end, start + 1))[0]
    return any(_box_state(an, s, e) == 'unknown' for s, e in items if (s, e) != (start, end))


# --- round 4c-2 box2:G: a passage across items whose boxes differ ---------------------------------------------------
_B2_ITEMS_DIFFER = ('uncertain: the passage names items whose check boxes differ, so the item it speaks for cannot be '
                    'told from it')


def _B2_items_differ(an: Analysis, start: int, end: int, state: Optional[str]) -> bool:
    """Whether the box states in the passage [start, end) differ: those of the items it names (_box_state: checked,
    unchecked, disagreeing or one a later box may govern) and ``state``, the box the passage itself is read by.
    "Interventions: ☑ Cold snare polypectomy ☐ Biopsy" cited whole, "Cold snare polypectomy ☐ Biopsy", or "☐ Photos ☑
    Cold snare polypectomy" (read by the box of an entry that is no item): read by one box, such a passage vouches for,
    or denies, an item another box governs, and which item is the code's own cannot be told from it (box2:G). It is
    held, never ready and never negated. An item no box governs counts for nothing; an unread one is
    _box_names_an_unread_item's. Read only where a box is near; each item's state is _box_state's, memoised."""
    text, span_end = an.text, max(end, start + 1)
    if not _BOX.search(text, max(0, start - BOX_REACH), min(len(text), span_end + BOX_REACH)):
        return False
    items = _box_tokens(an, start, span_end)[0]
    if not items:
        return False
    states = {_box_state(an, s, e) for s, e in items} | {state}
    states.discard(None)
    return len(states) > 1


def _names_an_item(an: Analysis, start: int, end: int) -> bool:
    end = max(end, start + 1)
    return an.touches_service(start, end) or any(_overlaps(s, e, start, end)
                                                  for s, e in _other_names_in(an, start - OTHER_NAME_REACH,
                                                                              end + OTHER_NAME_REACH))


BOX_HOLDS = (BOXES_DISAGREE, BOX_UNREAD, FIELD_UNTIED.split("'")[0], BOX_LATER)  # the cues of the holds above


# The line above ends in a complete answer or refusal of its own: a field answered by a bare denial ("Schatzki ring
# present: no", "Tattoo placed today: no") or a refusal verb with nothing after it ("the patient declined").
_ANSWER_AT_LINE_END = re.compile(r'(?:[:?=|][ \t]*(?:no|none|n|not[ \t]+(?:done|performed))'
                                 r'|\b(?:declined|declines|refused|refuses))[ \t.]*$', re.A | re.I)
# Or a field answered after a spaced dash, of any length, whose label is no clause ("History of an adverse reaction to
# sedation or to anesthesia in the past - no"; round 4c sections:7: sections' _FIELD_ANSWER reads labels of up to 60
# characters, so a longer one still joins the next line); the label is read from the last separator before the dash.
_SEC_DASH_ANSWER = re.compile(r'[ \t][-\u2013\u2014][ \t]*(?:no|none|n|not[ \t]+(?:done|performed))[ \t.]*$', re.A | re.I)
_SEC_LABEL_START = re.compile(r'.*(?:[.;,:?=|]|\t|[ ]{2})', re.A | re.S)


def _SEC_answer_above(an: Analysis, ls: int, le: int) -> Optional[str]:
    """The answer the line before line [ls, le) ends in, read the way sections reads it when it decides whether that
    line runs on (round 4c declared:5): from its content (after any heading label on it), right-stripped, its last
    WRAP_TAIL characters; a field, column or last-field answer (sections._answered), an option row
    (sections._OPTION_ROW), a dash answer of any length (_SEC_DASH_ANSWER), or a spoken answer after a comma or a
    colon ("the patient said, no": sections._SEC_SPOKEN_ANSWER_PUNCT, round 4c sections:8) when line [ls, le) opens a
    clause of its own. None otherwise. Reads at most 4 * WRAP_TAIL characters of the line above."""
    text, tail_size = an.text, gi_sections.WRAP_TAIL
    above_start, above_end = text.rfind('\n', 0, ls - 1) + 1, ls - 1
    section = an.lay.section_at(above_start)
    content = (section.heading.end if section.heading is not None and section.start == above_start
               and section.heading.end <= above_end else above_start)
    lo = max(content, above_end - 4 * tail_size)
    before = text[lo:above_end].rstrip()
    if not before:
        return None
    tail = before[-tail_size:]
    probe = before if lo == content and len(before) <= tail_size else tail
    said = tail.split()[-1].strip(' :?=|.,')
    if gi_sections._answered(probe) or gi_sections._OPTION_ROW.search(tail):
        return said
    dash = _SEC_DASH_ANSWER.search(tail)
    if dash:
        label = before[:len(before) - len(tail) + dash.start()]
        lead = _SEC_LABEL_START.match(label)
        if not gi_sections._LABEL_CLAUSE.search(label[lead.end():] if lead else label):
            return said
    if gi_sections._SEC_SPOKEN_ANSWER_PUNCT.search(tail) \
            and gi_sections._own_clause(text[ls:min(le, ls + 2 * gi_sections.OWN_CLAUSE_REACH)].lstrip()):
        return said
    return None


# The negation words a service's own line is read for (_S2_own_line_denies): each is read in a clause window of its own,
# so a line of more is not read for its own denial and the line above decides, which can only hold (round 7 bounded:5:
# "Biopsies were taken, no, no, ..." under an answered question routed 10-12x slower than aaf517e, and without the
# question the analyze stage overran from about 200,000 characters).
_S2_OWN_LINE_TOKENS = 8


def _S2_own_line_denies(an: Analysis, lo: int, hi: int) -> bool:
    """Whether [lo, hi), the service's own line within CLAUSE_REACH of the span, holds a negation word that negates on
    its own, as the cue reader negates (_clause_reading_cues): an anchored negation of a service or intervention named
    next to it (_anchored_explains: "No biopsy was performed", "Biopsy not done", "Biopsies were not needed"), or a
    negation that names no service and denies the act its words describe (_memberless_negations: "No tissue was
    obtained", "The stricture was not dilated"); clause cues never negate. Only then does the line's own reading stand
    (round 4d sections:3: the hold was skipped on any negation word, so the question's "No" above still excluded the
    biopsy). A word a complication, qualifier or finding explains ("without difficulty", "with no bleeding", "no polyps
    were seen") or that only doubts (", which was not ulcerated", "could not be completed") does not: the cross-line
    negation is then what decides, and it holds. Bounded: a line with more than _S2_OWN_LINE_TOKENS negation words is
    not read for them (False: the cross-line answer decides, and it can only hold), counted by a search that stops past
    the cap; the negation readers are memoised."""
    text = an.text
    tokens = []
    for token in cues.DOUBT_TOKEN.finditer(text, lo, hi):
        tokens.append((token.start(), token.end()))
        if len(tokens) > _S2_OWN_LINE_TOKENS:
            return False
    for span in tokens:
        cs, ce = an.lay.window(an.lay.clauses_for(*span)[0], span[0], span[1], CLAUSE_REACH)
        if _anchored_explains(an, cs, ce, span) or _covered(span, [where for _, where in _memberless_negations(an, cs, ce)]):
            return True
    return False


def _denied_from_the_line_above(an: Analysis, start: int, end: int) -> Optional[str]:
    """A cue when a negation reaches [start, end) only because its sentence was joined across a line break after a
    complete answer or refusal (_ANSWER_AT_LINE_END) on the line above, and the span's own line has no denial
    ("Schatzki ring present: no" then "biopsies were taken ...", "the patient declined" then "Colonoscopy with cold
    snare polypectomy ..."; round 4 structure:2 and structure:3). Whose answer it is cannot be read, so it holds rather
    than negates. Cut prose ("Comment: because of time constraints, no" then "EUS ... was performed today.") is a
    wrapped sentence and stays negated. Round 4c (sections:7, sections:8, declared:5): the line above is read whole,
    from its own start (a field question's "?" ends the question's sentence before its "No"), and its answer is read
    by sections' own readers too (_SEC_answer_above), so a line sections reads as answered never negates across the
    break. Round 4d sections:3: "no denial" is a negation word nothing explains (_S2_own_line_denies), never any
    negation word ("Biopsies were taken ... without difficulty." holds). Bounded by CLAUSE_REACH and WRAP_TAIL."""
    text = an.text
    ss, _ = an.lay.sentence_for(start, end)
    ls = text.rfind('\n', 0, start) + 1
    if ls <= ss:
        return None
    le = text.find('\n', end)
    le = len(text) if le < 0 else le
    if _S2_own_line_denies(an, max(ls, start - CLAUSE_REACH), min(le, end + CLAUSE_REACH)):
        return None
    above = text[max(text.rfind('\n', 0, ls - 1) + 1, ls - 1 - CLAUSE_REACH):ls - 1]
    answer = _ANSWER_AT_LINE_END.search(above)
    said = answer.group(0).strip(' :?=|.') if answer else _SEC_answer_above(an, ls, le)
    if said is None:
        return None
    return f"uncertain: the line above it ends in an answer of its own ('{said}')"


_DEFERRAL_CUE = re.compile(r"'(?:defer|defers|deferring|deferral|postpone|postpones|postponing)' in its clause$",
                           re.A | re.I)


def _box_checked_option(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """A hold for the status option at [start, end) that its own box reading left unchecked ("[ ] Aborted") when its
    line selects a denying option, itself or another ("[ ] Completed [x] Cancelled [ ] Aborted", "Completed ☐ |
    Aborted ☒"): a checked, disagreeing or unread box on a denying option makes the line a statement (routing:0), held
    and never read as that status (_box_option_states). None when every denying option of the line is unchecked. The
    line is read within BOX_REACH of the option. Round 4d BOXES3: held with the strict rows' cue on a row they hold."""
    unpaired = _B3_hold(an, start, end)
    if unpaired is not None:
        return Reading('uncertain', (unpaired,), 'cue', doubt=True)
    text = an.text
    lo = max(text.rfind('\n', max(0, start - BOX_REACH), start) + 1, start - BOX_REACH)
    newline = text.find('\n', end, end + BOX_REACH)
    hi = min(len(text), end + BOX_REACH) if newline < 0 else newline
    options = _box_denying_options(an, lo, hi)
    words = options + [m.span() for m in _BOX_DONE_OPTION.finditer(text, lo, hi)]
    if any(state not in (None, 'off') for state in _box_option_states(an, lo, hi, options, words)):
        return Reading('uncertain', (BOX_STATUS_OPTION.format(' '.join(text[lo:hi].split())),), 'cue', doubt=True)
    return None


# A status question answered with a denial, on its own line, in the shared grammar (_BOX_Q_LEAD ..): the reference,
# after the grammar's lead and the word for the procedure; an optional "today"; the separator, after the label's own
# '?' or ':'; then a denial; then nothing, or a punctuated remark ("Procedure cancelled: No", "Was the procedure
# cancelled? No, it was completed.", "Procedure cancelled?: No" in a form block, "Procedure cancelled: N/A", a table row
# "Procedure cancelled | No"; never "Procedure cancelled, no sedation given.", "Procedure cancelled: no driver
# available." or "Procedure cancelled: No-show", where "no" opens the reason).
_BOX_ANSWER_LEAD = re.compile(_BOX_Q_LEAD + r'(?:' + _BOX_Q_NOUN + r'[ \t]+)?', re.I)
_BOX_ANSWER_TAIL = re.compile(_BOX_Q_TODAY + _BOX_Q_SEP + _BOX_Q_DENIAL
                              + r'(?:[ \t]*[,;(]|[ \t]+[–—-]|\.[ \t]+|[ \t.]*$)', re.I)
BOX_ANSWER_REACH = 80  # how far a status question's lead or answer is read from its reference (bounds the work)


def _box_status_answer(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """A hold for the status reference at [start, end) when its own line is a status question answered with a denial
    (structure:13): "Procedure cancelled: No" says the procedure was not cancelled, so it is never read as a
    cancellation; whatever else it means is left for review. The answer is read within BOX_ANSWER_REACH of the
    reference; a remark after it may run on. So is a printed question standing alone whose answer is the form field
    tied to it ("Procedure cancelled?" over "[PDF form fields on page 1] / Procedure cancelled?: No", round 5
    declared:1)."""
    text = an.text
    fields = _form_fields(an)
    tied = _within(fields.answers, fields.answer_starts, start, end)
    if tied is not None:
        return Reading('uncertain', (BOX_STATUS_ANSWER.format(tied.line),), 'cue', doubt=True)
    newline = text.rfind('\n', max(0, start - BOX_ANSWER_REACH), start)
    if newline < 0 and start > BOX_ANSWER_REACH:
        return None
    if not _BOX_ANSWER_LEAD.fullmatch(text, newline + 1, start):
        return None
    line_end = text.find('\n', end, end + BOX_ANSWER_REACH + 1)
    stop = line_end if line_end >= 0 else min(len(text), end + BOX_ANSWER_REACH + 1)
    if not _BOX_ANSWER_TAIL.match(text, end, stop):
        return None
    return Reading('uncertain', (BOX_STATUS_ANSWER.format(text[newline + 1:stop].strip()),), 'cue', doubt=True)


# Round 4c-2 plan:C: a performed reading of a line listed under a label that denies performance ("Procedures not
# performed:", "Not done:"; "Cancelled procedures:" over a line with a performance cue of its own) is held, whatever the
# line names. The label was read (_denying_label_above) only for a service mention, through _later_denial, so a line
# naming an intervention ("Cold snare polypectomy of the 6 mm sigmoid polyp.") read performed by its section. The label
# is read exactly as that reader reads it (LABEL_ITEMS lines back, in the same section, stopping at a blank line or at
# another label line), and the hold is a doubt, as the verbless denying heading's own default is (round 4 release:9).
# Round 4d declared:6: the box may follow a list marker the other readers strip ("- [ ] Procedures not performed:", "1. [x]
# Not done:", "• ☐ Cancelled procedures:"), as it may precede one ("☐ 1. Procedures not performed:").
_P2_LEADING_BOX = re.compile(r'[ \t]*(?:' + _SEC_LABEL_MARK + r')?(?:' + _BOX_MARK.pattern + r')[ \t]*')


def _P2_boxed_denying_label(text: str, ls: int, le: int) -> bool:
    """Whether the label line [ls, le) is a denying label led by one box of any state ("[ ] Procedures not performed:",
    "[x] Not done:", "[?] Cancelled procedures:"), after any list marker ("- [ ] ...", round 4d declared:6): one box,
    then the label as _DENYING_LABEL reads it. An unchecked box may be an unselected option, so what is listed under it
    is held, never read performed (round 4c-2 plan:C)."""
    lead = _P2_LEADING_BOX.match(text, ls, le)
    return bool(lead) and bool(_DENYING_LABEL.fullmatch(text, lead.end(), le))


def _P2_listed_under_a_denial(an: Analysis, start: int, reading: Reading) -> Reading:
    """``reading`` of the passage at ``start``, held when it reads performed (not as E/M documentation) and its line is
    listed under a denying label (_denying_label_above): uncertain, a doubt, never negated (round 4c-2 plan:C)."""
    if reading.status != 'performed' or (reading.cues and reading.cues[0].endswith(EM_DOCUMENTATION)):
        return reading
    label = _denying_label_above(an, start)
    if label is None:
        return reading
    return Reading('uncertain', (f"uncertain: listed under '{label}', a label that denies performance",) + reading.cues,
                   reading.basis, doubt=True)


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
        if reading.status == 'performed':
            hold = _B2_label_hold(an, start, end)  # round 4c-2 box2:L: "Colonoscopy: ☒ Incomplete ☐ Completed"
            if hold:
                reading = Reading('uncertain', (hold,) + reading.cues, 'cue', doubt=True)
        an.memo[key] = _P2_listed_under_a_denial(an, start, reading)  # round 4c-2 plan:C
    return an.memo[key]


def _read_span(an: Analysis, start: int, end: int, adjust: bool = True) -> Reading:
    """The reading of [start, end). A span with no service name in it that covers
    an E/M documentation mention or a procedure reference reads as that mention.
    ``adjust=False``: before its family's document-level judgement (own_status_for_span)."""
    if not an.touches_service(start, end):
        for mentions, readings in ((an.references, an.references), (an.em, an.em_readings)):
            for m in mentions:
                if _overlaps(m.start, m.end, start, max(end, start + 1)):
                    return readings[m]
    reading = _generic_reading(an, start, end)
    if adjust and reading.status == 'performed' and (an.touches_service(start, end)
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
    # Positional (round 6 bounded:1): services are sorted by start and never overlap, so only those starting within the
    # longest service name before the span can reach it - the same overlap test as a scan of every service, which made
    # each cited span cost O(services) and a long cited report quadratic.
    stop = max(end, start + 1)
    low = bisect.bisect_left(an._service_starts, start - an._longest_service)
    high = bisect.bisect_left(an._service_starts, stop)
    named = {m.family for m in an.services[low:high] if _overlaps(m.start, m.end, start, stop)}
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
    """The clauses inside [s, e), read from the first one at s by index (refutation r1 cost lens, ec5 cost: a slice
    from there copied every later clause of the document at each call - a list of 133,000 "A," lines, each its own
    clause, took the analyze stage past its limit)."""
    clauses = an.lay.clauses
    found = []
    for i in range(bisect.bisect_left(clauses, (s, -1)), len(clauses)):
        c = clauses[i]
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


def _landmarks(an: Analysis, sentences, table, unread: Optional[list] = None,
               denied: Optional[list] = None, doubted: Optional[list] = None, *,
               cut: Optional[list] = None, cut_denials: Optional[list] = None,
               labelled: Optional[list] = None) -> tuple[list, list]:
    """(reached, blocked) as (depth, label, clause span) for landmarks read as
    part of a performed or incomplete service. A landmark is reached only from a
    reading with no unresolved negation; a denied advancement ("it was not advanced
    to the cecum") is blocked, never reached. ``unread``, when given, collects the landmark of every extent label that
    would be reached but for its tail (_plain_tail: "Extent: Cecum | Scope: Olympus"): its extent is not read, and it
    keeps a shallower landmark from reading the procedure incomplete (_P2_unread_reaches, round 4c-2 plan:B).
    ``denied``, when given, collects every other landmark its reading denies or doubts (negated, cancelled, incomplete,
    or an unresolved negation: "Cecum not reached."); with the blocked ones, they keep that rule from firing (plan:B2).
    ``doubted``, when given, collects every extent label plan:D refuses to read as reached (_P2_refused_label) whose own
    sentence states no reach denial (_P2_reach_denied: "Extent: cecum; no biopsies taken"), with that sentence's span
    after its landmark; such a label withholds the extent beside a shallower landmark (_P2_doubted_withholds, round 4c-2
    plan:D2). A label refused for a reach denial ("Extent: cecum; not reached") is a denied one. ``cut``, when given,
    collects every reached extent label that is read only because a next report-field cell ends its value (round 4c
    declared:11: "Extent: cecum | Prep quality: Good"; _S2_read_by_the_cut), and ``cut_denials`` every blocked or denied
    hit with its match, its clause window and whether its own reading denies it outright (hit, start, end, window start,
    window end, explicit: negated, cancelled or incomplete), so that a denial in the family's text can still keep such a
    label from reading as reached (_S2_cut_denied, round 4d regression:3). ``labelled``, when given, collects every
    landmark an extent label names (cues.EXTENT_LABEL_BEFORE right before it: "Extent: Cecum | Scope: Olympus",
    "Intended extent: cecum"), whatever its reading: the document's own statement of the extent (_insertion_only)."""
    text = an.text
    reached, blocked = [], []
    for s, e in sentences:
        for cs, ce in _clauses_in(an, s, e):
            clause = None  # round 4d bounded:3: one Span of the clause, shared by every hit of it (memory linear in the text)
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
                    if clause is None:
                        clause = _span(text, cs, ce)
                    hit = (depth, label, clause)
                    if labelled is not None and cues.EXTENT_LABEL_BEFORE.search(text, ws, m.start()):
                        labelled.append(hit)
                    if status in ('performed', 'incomplete') and cues.REACHED_BEYOND.search(pre):
                        reached.append(hit)
                    elif base in ('performed', 'incomplete', 'negated') and (
                            cues.NOT_REACHED_BEFORE.search(pre) or cues.NOT_REACHED_AFTER.search(post)):
                        blocked.append(_P2_beyond_the_valve(an, m, hit))  # round 4c-2 plan:D2
                        if cut_denials is not None:  # round 4d regression:3
                            cut_denials.append((blocked[-1], m.start(), m.end(), ws, we,
                                                status in ('negated', 'cancelled', 'incomplete')))
                    elif status in ('performed', 'incomplete') and (
                            cues.REACHED_BEFORE.search(pre) or cues.REACHED_AFTER.search(post)
                            or (_reached_label(an, ws, m.start()) and _plain_tail(an, m.end(), we)
                                and not _P2_label_denied(an, m.end(), depth, table))  # round 4c-2 plan:D
                            or _straight_after_service(an, ws, m.start())):
                        reached.append(hit)
                        if cut is not None and _S2_read_by_the_cut(an, m.end(), we) \
                                and not (cues.REACHED_BEFORE.search(pre) or cues.REACHED_AFTER.search(post)
                                         or _straight_after_service(an, ws, m.start())):
                            cut.append(hit)  # read only by declared:11's cell cut (round 4d regression:3)
                    elif (_answers_silently(an, reading, m.start(), m.end()) and _reached_label(an, ws, m.start())
                          and _plain_tail(an, m.end(), we) and not _P2_label_denied(an, m.end(), depth, table)):
                        reached.append(hit)  # "Furthest extent reached: cecum." answered in an addendum
                        if cut is not None and _S2_read_by_the_cut(an, m.end(), we):
                            cut.append(hit)  # round 4d regression:3
                    elif unread is not None and _reached_label(an, ws, m.start()) \
                            and not _P2_tail_contrary(an, m.end()) and (
                                ((status in ('performed', 'incomplete') or _answers_silently(an, reading, m.start(), m.end()))
                                 and _P2_neutral_tail(an, m.end()))
                                or _P2_doubted_by_a_next_field(an, reading, m.end(), ws, we)):
                        unread.append(hit)  # a label reached but for its neutral tail (round 4c-2 plan:B, plan:B2)
                    elif doubted is not None and _P2_refused_label(an, reading, m.start(), m.end(), ws, we, depth, table) \
                            and not _P2_reach_denied(an, m.end(), depth, table):
                        doubted.append(hit + ((m.end(), _P2_label_rest(an, m.end(), depth, table)),))  # plan:D2
                    elif denied is not None and (status in ('negated', 'cancelled', 'incomplete')
                                                 or (reading.cues and reading.cues[0].startswith(DOUBT_PREFIX)
                                                     and not _P2_doubt_is_a_finding(an, ws, we))
                                                 or (_reached_label(an, ws, m.start())
                                                     and _P2_label_denied(an, m.end(), depth, table))):
                        denied.append(_P2_beyond_the_valve(an, m, hit))  # a landmark its reading denies or doubts (plan:B2)
                        if cut_denials is not None:  # round 4d regression:3
                            cut_denials.append((denied[-1], m.start(), m.end(), ws, we,
                                                status in ('negated', 'cancelled', 'incomplete')))
    return reached, blocked


def _P2_doubted_by_a_next_field(an: Analysis, reading: Reading, end: int, ws: int, we: int) -> bool:
    """Whether the only doubt of an extent label's landmark (which ends at ``end``; its clause window [ws, we)) is a
    negation word inside a next cell that opens a listed report field on the label's line ("Extent: Cecum |
    Complications: None"): round 4c declared:11 ends the label's value at that cell, so the answer is the field's own.
    The label is still never read; it only counts as unread (round 4c-2 plan:B)."""
    if reading.status != 'uncertain' or not reading.cues or not reading.cues[0].startswith(DOUBT_PREFIX):
        return False
    text = an.text
    line_end = text.find('\n', end, we)
    cell = _SEC_NEXT_CELL.search(text, end, we if line_end < 0 else line_end)
    return (cell is not None and _P2_neutral_region(text, end, cell.start(), need_cell=False)
            and not any(t.start() < cell.start() for t in cues.DOUBT_TOKEN.finditer(text, ws, we)))


# Words after an extent label's landmark that make it an aim or an attempt, not an unread statement of the extent reached
# ("Extent: cecum (intended).", "cecum was the goal", "Extent: Cecum (attempted)"): round 4 routing:9 and release:3 read
# such a label as no extent, and its shallower prose landmark still decides (round 4c-2 plan:B keeps that reading).
_P2_AIM_WORD = re.compile(r'\b(?:intend\w*|intent\w*|goals?|targets?|targeted|aim\w*|expect\w*|attempt\w*|objectives?|'
                          r'desir\w*|anticipat\w*|tried|try|trying|incomplet\w*|partial\w*|abandon\w*|unsuccessful|'
                          r'fail\w*|hop(?:e|ed|es|ing)|sought|propos\w*|want\w*|wish\w*)\b', re.A | re.I)


def _P2_tail_contrary(an: Analysis, end: int) -> bool:
    """Whether the rest of an extent label's line after its landmark (which ends at ``end``) denies, doubts, plans or
    calls off the landmark, or names it an aim: a negation word (cues.DOUBT_TOKEN), a clause cue that is no performance
    cue (cancelled, incomplete, historical, planned, uncertain, "?"), or an aim word (_P2_AIM_WORD). Read to the line's
    end, to a next cell that opens a listed report field (_SEC_NEXT_CELL), or CLAUSE_REACH characters, whichever comes
    first, across a ";" or a "." ("Extent: cecum (intended; not reached)", "Extent: cecum | Reached: No"). Such a label
    is no unread statement of the extent reached, so it never withholds an extent (round 4c-2 plan:B)."""
    text = an.text
    line_end = text.find('\n', end, end + CLAUSE_REACH)
    stop = min(len(text), end + CLAUSE_REACH) if line_end < 0 else line_end
    cell = _SEC_NEXT_CELL.search(text, end, stop)
    stop = cell.start() if cell else stop
    return bool(cues.DOUBT_TOKEN.search(text, end, stop) or _P2_AIM_WORD.search(text, end, stop)
                or any(c.status != 'performed' for c in an.cues_in(end, stop)))


def _P2_unread_reaches(unread: list, expected: int) -> bool:
    """Whether an extent label left unread for its tail names a landmark at or beyond ``expected``, the depth the
    procedure calls for, beside a deepest landmark read as reached that lies short of it (round 4c-2 plan:B): that
    shallower landmark then reads no incomplete extent ("The colonoscope was inserted into the rectum" beside "Extent:
    Cecum | Scope: Olympus" is no "incomplete: rectum"); no extent is read and the family's extent clarification asks
    for it. A label short of that depth agrees the procedure was incomplete, so the reading stays as it was. The label
    itself is still never read."""
    return any(hit[0] >= expected for hit in unread)


# Round 4c-2 plan:B2: the only tails plan:B reads as neutral. The label's own value is plain (_P2_plain_value: nothing
# but cues.EXTENT_TAIL words and punctuation), and what leaves it unread is a next cell that opens one of these fields,
# none of which can speak of the extent reached: the instrument, the staff, the room. Any other word in the tail, an aim
# no list names ("(ambition)") included, keeps the base reading: the shallower landmark still decides.
_P2_CELL_BREAK = re.compile(r'[ \t]*\|[ \t]*|\t[ \t]*|[ ]{2,}')  # a table row's next cell, a tab or a column (as _SEC_NEXT_CELL)
_P2_NEUTRAL_CELL = re.compile(r'(?:[ \t]*\|[ \t]*|\t[ \t]*|[ ]{2,})(?:scope|instrument|(?:colono|gastro|sigmoido|entero|'
                              r'duodeno|echoendo|endo)scope|model|serial(?:[ \t]+(?:number|no\.?|#))?|endoscopist|'
                              r'operator|proceduralist|attending|fellow|assistant|nurse|technician|room)[ \t]*:',
                              re.A | re.I)


def _P2_plain_value(text: str, start: int, end: int) -> bool:
    """Whether [start, end), an extent label's value after its landmark, holds only cues.EXTENT_TAIL words."""
    return all(word.lower() in cues.EXTENT_TAIL for word in _EXTENT_TAIL_WORD.findall(text, start, end))


def _P2_neutral_region(text: str, start: int, stop: int, need_cell: bool) -> bool:
    """Whether [start, stop), after an extent label's landmark, is a plain value followed only by cells that open a
    field of _P2_NEUTRAL_CELL (at least one when ``need_cell``)."""
    first = _P2_CELL_BREAK.search(text, start, stop)
    if first is None:
        return not need_cell and _P2_plain_value(text, start, stop)
    if not _P2_NEUTRAL_CELL.match(text, first.start(), stop) or not _P2_plain_value(text, start, first.start()):
        return False
    return all(_P2_NEUTRAL_CELL.match(text, cell.start(), stop) for cell in _P2_CELL_BREAK.finditer(text, first.end(), stop))


def _P2_neutral_tail(an: Analysis, end: int) -> bool:
    """Whether the tail after an extent label's landmark (which ends at ``end``) is neutral (round 4c-2 plan:B2): a plain
    value, then only cells that open a field of _P2_NEUTRAL_CELL (one at least), read to the line's end, to a next cell
    that opens a listed report field (_SEC_NEXT_CELL), or CLAUSE_REACH characters."""
    text = an.text
    line_end = text.find('\n', end, end + CLAUSE_REACH)
    stop = min(len(text), end + CLAUSE_REACH) if line_end < 0 else line_end
    listed = _SEC_NEXT_CELL.search(text, end, stop)
    return _P2_neutral_region(text, end, listed.start() if listed else stop, need_cell=True)


def _P2_doubt_is_a_finding(an: Analysis, ws: int, we: int) -> bool:
    """Whether every negation word in a landmark's clause window [ws, we) belongs to a denied finding, another act or a
    complication (cues.FINDING_NEGATION, OTHER_ACT_NEGATION, COMPLICATION_NEGATION: "No polyps in the cecum."): such a
    doubt says what was or was not found there, never that the landmark was not reached (round 4c-2 plan:B2)."""
    masked, where = _masked_map(an, ws, we)
    spans = [(where[m.start()], where[m.end()])
             for pattern in (*cues.FINDING_NEGATION, cues.OTHER_ACT_NEGATION, cues.COMPLICATION_NEGATION)
             for m in pattern.finditer(masked)]
    return all(_covered((t.start(), t.end()), spans) for t in cues.DOUBT_TOKEN.finditer(an.text, ws, we))


# Round 4c-2 plan:D: "Extent: cecum; not reached" was read as the cecum reached - the ";" ends both the label's value
# (_plain_tail) and the landmark's clause, so the denial after it was never seen. The rest of the label's own sentence is
# now read too, past ";" and ",": a denial there keeps the label from being read as reached. A negation that a denied
# finding, complication, other act or qualifier explains denies nothing ("; no polyps"), unless the denied words name a
# landmark ("; no appendiceal orifice seen"); a denied "was not seen" is never such a finding here (it is how a landmark
# is said not to be reached). The sentence ends at a full stop, at a next report or equipment field, and at a deeper
# landmark or retroflexion, whose own denial is theirs ("Extent: cecum; TI not intubated").
_P2_SENTENCE_STOP = re.compile(r'\.(?=\s|$)')
_P2_FIELD_SEPARATOR = re.compile(r'[ \t]*[;,][ \t]*')
_P2_FINDING_DENIALS = tuple(p for p in cues.FINDING_NEGATION if not p.search('was not seen'))


def _P2_field_opens(text: str, pos: int) -> bool:
    """Whether a listed report field (_SEC_NEXT_CELL) or an equipment, staff or room field (_P2_NEUTRAL_CELL) opens at
    ``pos``, read as the cell after a separator would be."""
    probe = ' | ' + text[pos:pos + 80]
    return bool(_SEC_NEXT_CELL.match(probe) or _P2_NEUTRAL_CELL.match(probe))


def _P2_label_denied(an: Analysis, end: int, depth: int, table) -> bool:
    """Whether the rest of an extent label's own sentence after its landmark (of ``depth`` in ``table``, ending at
    ``end``; _P2_label_rest) denies or doubts that landmark (round 4c-2 plan:D): a negation no finding, complication,
    other-act or qualifier exception explains, a clause cue that is no performance cue, an aim word (_P2_AIM_WORD), or
    a reach denial of the closed list (plan:D2: "; short of the cecum" carries no negation word). Read once per label
    (round 4d bounded:6: _landmarks asked it twice per label, and plan:D2 a third time)."""
    key = ('p2-label-denied', end, depth, id(table))
    if key not in an.memo:
        an.memo[key] = _S2_label_denied_read(an, end, depth, table)
    return an.memo[key]


def _S2_label_denied_read(an: Analysis, end: int, depth: int, table) -> bool:
    """_P2_label_denied's reading itself (see there), unmemoised."""
    text = an.text
    stop = _P2_label_rest(an, end, depth, table)
    if stop <= end:
        return False
    masked, where = _masked_map(an, end, stop)
    explained = [(where[m.start()], where[m.end()])
                 for pattern in (cues.COMPLICATION_NEGATION, cues.QUALIFIER_NEGATION, cues.OTHER_ACT_NEGATION,
                                 cues.OTHER_ACT_DENIED, *_P2_FINDING_DENIALS)
                 for m in pattern.finditer(masked)]
    explained = [(s, e) for s, e in explained if not _LANDMARK_AT.search(text, s, e)]
    if any(not _covered((t.start(), t.end()), explained) for t in cues.DOUBT_TOKEN.finditer(text, end, stop)):
        return True
    return bool(_P2_AIM_WORD.search(text, end, stop) or any(c.status != 'performed' for c in an.cues_in(end, stop))
                or _P2_reach_denied_in(an, end, stop, table, depth))


def _P2_label_rest(an: Analysis, end: int, depth: int, table) -> int:
    """Where the rest of an extent label's own sentence after its landmark (of ``depth`` in ``table``, ending at
    ``end``) stops (round 4c-2 plan:D): the line's end or CLAUSE_REACH characters, past ";" and ",", up to a full stop,
    a next field (_P2_field_opens, after a cell break or a ";" or ","), or the segment (_P2_segment_start) that names a
    landmark of ``table`` deeper than ``depth``, retroflexion, or a passage of the ileocecal valve beside a lower-tract
    label short of the terminal ileum (plan:D2: "; unable to intubate the TI", "; unable to retroflex" are theirs). Read
    once per label (round 4d bounded:6: _landmarks, plan:D and plan:D2 asked it four times per label)."""
    key = ('p2-label-rest', end, depth, id(table))
    if key in an.memo:
        return an.memo[key]
    text = an.text
    stop = min(len(text), end + CLAUSE_REACH)
    line_end = text.find('\n', end, stop)
    stop = line_end if line_end >= 0 else stop
    for found in (_P2_SENTENCE_STOP.search(text, end, stop), _SEC_NEXT_CELL.search(text, end, stop),
                  _P2_NEUTRAL_CELL.search(text, end, stop)):
        if found:
            stop = min(stop, found.start())
    field = next((sep for sep in _P2_FIELD_SEPARATOR.finditer(text, end, stop) if _P2_field_opens(text, sep.end())), None)
    if field:
        stop = field.start()
    theirs = [pattern.search(text, end, stop) for _, deeper, pattern in table if deeper > depth]
    theirs.append(_RETROFLEXION.search(text, end, stop))
    if table is cues.LOWER_LANDMARKS and depth < _P2_TI_DEPTH:
        theirs.append(_P2_TI_PASSAGE.search(text, end, stop))
    for found in theirs:
        if found:
            stop = min(stop, _P2_segment_start(text, end, found.start()))
    an.memo[key] = stop
    return stop


# Round 4c-2 plan:D2: passing the ileocecal valve is reaching the terminal ileum ("unable to intubate the ileocecal
# valve", "IC valve not intubated", "could not pass the IC valve"), whatever the cecum pattern says of the valve.
_P2_TI_DEPTH = next(depth for label, depth, _ in cues.LOWER_LANDMARKS if label == 'terminal ileum')
_P2_TI_PASSAGE = re.compile(
    r"\b(?:intubat|pass|travers|cross|negotiat|enter|cannulat)\w*\s+(?:(?:of|into|through)\s+)?(?:the\s+)?"
    r"(?:ileo-?cecal|IC)\s+valve\b"
    r"|\b(?:ileo-?cecal|IC)\s+valve\s+(?:(?:was|were|is|could|can|did|not|be|been|unable|to|cannot|"
    r"(?:could|can|did|was|were)n['\u2019]t)\s+)*(?:intubat|travers|cannulat|pass|enter|negotiat|cross)\w*", re.A | re.I)


def _P2_beyond_the_valve(an: Analysis, m, hit: tuple) -> tuple:
    """``hit`` (depth, label, clause span) of a blocked or denied landmark match ``m``, at the terminal ileum's depth
    when a passage of the ileocecal valve covers ``m`` ("Unable to intubate the ileocecal valve.", "The ileocecal valve
    could not be traversed.", _P2_TI_PASSAGE: only the valve lies inside one): the scope stood at the valve, and what
    it denies is the terminal ileum (round 4c-2 plan:D2). Only plan:D2's guard reads the difference
    (_P2_doubted_withholds reads denials up to the doubted label's depth); every other reader of these hits compares
    them with a depth short of the cecum."""
    for passage in _P2_TI_PASSAGE.finditer(an.text, max(0, m.start() - 60), m.end() + 80):
        if passage.start() <= m.start() and m.end() <= passage.end():
            return (_P2_TI_DEPTH,) + hit[1:]
    return hit


def _P2_segment_start(text: str, lo: int, pos: int) -> int:
    """Where the segment that holds ``pos`` starts in [lo, pos): after the last _P2_REACH_BREAK there, else ``lo``."""
    breaks = [b.end() for b in _P2_REACH_BREAK.finditer(text, lo, pos)]
    return breaks[-1] if breaks else lo


# Round 4c-2 plan:D2: plan:D's refusal lets a shallower landmark read the procedure incomplete only when the label's own
# sentence states that its landmark was not reached - a closed list of reach denials, whose subject and object are that
# landmark (_P2_reach_names_the_landmark): "; not reached", "; could not be advanced", "; unable to intubate", "; failed
# to reach", "; short of the cecum", "; reached: no", also with the reason first ("; due to poor prep not reached",
# "; prep poor therefore not visualized"). Any other denial, doubt or aim ("; no biopsies taken", "; prep fair?",
# "; consent not signed") withholds the extent instead, and the family's extent clarification asks for it.
_P2_REACH_DENIAL = re.compile(
    r"\b(?:(?:not|never)\s+(?:(?:yet|been|be)\s+)*(?:reached|visuali[sz]ed|intubated|achieved|advanced)"
    r"|(?:could(?:\s+not|n['\u2019]t)|can(?:\s*not|['\u2019]t)|did(?:\s+not|n['\u2019]t)|would(?:\s+not|n['\u2019]t))\s+"
    r"(?:be\s+)?(?:reach(?:ed)?|advanced?|intubated?|visuali[sz]ed?)"
    r"|(?:unable|not\s+able|failed|failure)\s+to\s+(?:be\s+)?(?:reach(?:ed)?|advanced?|intubated?|visuali[sz]ed?|achieved?)"
    r"|(?:(?:stopped|fell|came(?:\s+up)?|ended(?:\s+up)?)\s+)?(?:just\s+)?short\s+of"
    r"|(?:reached|intubated|visuali[sz]ed|achieved)\s*[:=]\s*no)\b", re.A | re.I)
# A reach denial's segment: between the separators of the label's sentence (never a field's colon: "; polyp: not
# reached" speaks of the polyp).
_P2_REACH_BREAK = re.compile(r'[;,|()\[\]]|\s[-\u2013\u2014]+\s', re.A)
# A reason before the denial ("due to poor prep not reached"), or a word that draws the consequence ("prep poor
# therefore not visualized"): the denial's own subject is then the landmark.
_P2_REASON_LEAD = re.compile(r'[ \t]*(?:due\s+to|because(?:\s+of)?|secondary\s+to|owing\s+to|on\s+account\s+of|'
                             r'as\s+a\s+result\s+of|in\s+view\s+of|given)\b', re.A | re.I)
_P2_THEN = re.compile(r'\b(?:so|therefore|thus|hence|consequently)[ \t]+(?:(?:it|was|were|is|has|had|have|been)[ \t]+)*\Z',
                      re.A | re.I)
# A relative clause ("due to a lesion that could not be reached") or a hedge names no denial of the landmark.
_P2_RELATIVE = re.compile(r'\b(?:that|which|who|whom|whose|where)[ \t]+'
                          r'(?:(?:was|were|is|are|has|had|have|been|could|can|did|would)[ \t]+)*\Z', re.A | re.I)
_P2_REACH_HEDGE = re.compile(r'\?|\b(?:possibl\w*|probabl\w*|likely|maybe|perhaps|presumabl\w*|apparently|may|might|'
                             r'questionabl\w*|uncertain|unclear|unsure|suspected)\b', re.A | re.I)
# The only words that may stand before a reach denial in its segment, besides the landmark itself: function words, a
# word of intubation or visualization, and the instrument (whose advancement is the reach).
_P2_INSTRUMENT = frozenset(('scope', 'instrument', 'colonoscope', 'endoscope', 'gastroscope', 'duodenoscope',
                            'enteroscope', 'sigmoidoscope'))
_P2_REACH_SUBJECT = frozenset(('the', 'a', 'and', 'but', 'however', 'it', 'was', 'were', 'is', 'are', 'has', 'have',
                               'had', 'been', 'be', 'could', 'can', 'did', 'would', 'also', 'still', 'yet', 'intubation',
                               'visualization', 'visualisation')) | _P2_INSTRUMENT
# What may follow a reach denial in its segment: nothing, a reason, the landmark or the instrument, one of these words,
# or a word of direction (_P2_REACH_TOWARD) that is followed by a landmark. Any other word is the denial's own object
# ("unable to reach the lesion", "failed to advance the guidewire"): no denial of the landmark.
_P2_REACH_ONWARD = frozenset(('further', 'farther', 'any', 'at', 'all', 'despite', 'after', 'again', 'yet', 'either',
                              'even', 'completely', 'fully', 'today', 'during'))
_P2_REACH_TOWARD = frozenset(('to', 'into', 'beyond', 'past', 'up', 'as', 'far'))
# Round 4d sections:1: "not advanced further", "could not be advanced any further", "not advanced farther due to looping"
# say the scope went no further than the label's landmark, never that it did not reach it (all three bases read the
# label so); "further" or "farther" then "than" reads as "beyond". And "beyond" or "past" denies reaching the label's
# landmark only before a landmark shallower than it ("not advanced beyond the transverse colon" after "Extent: cecum"),
# never before the label's own or one as deep ("not advanced beyond the cecum", "past the ileocecal valve").
_S2_ONWARD_ONLY = frozenset(('further', 'farther', 'any'))
_S2_BEYOND = frozenset(('beyond', 'past'))


def _P2_landmark_at(text: str, pos: int, table) -> bool:
    return any(pattern.match(text, pos) for _, _, pattern in table)


def _S2_landmark_depth_at(text: str, pos: int, table) -> Optional[int]:
    """The depth of the first landmark of ``table`` that starts at ``pos``, or None."""
    return next((depth for _, depth, pattern in table if pattern.match(text, pos)), None)


def _P2_reach_names_the_landmark(text: str, lo: int, hit, hi: int, table, depth: int,
                                 expected: Optional[int] = None) -> bool:
    """Whether the reach denial ``hit`` (a _P2_REACH_DENIAL match) in the segment [lo, hi) of an extent label's own
    sentence denies reaching the label's landmark, of ``depth`` in ``table`` (round 4c-2 plan:D2): no hedge or "?" in the
    segment; before it, a reason ("due to poor prep"), a word of consequence ("so", "therefore"), or only landmarks and
    _P2_REACH_SUBJECT words ("cecum was", "scope could"), never a relative clause; after it, nothing or what
    _P2_REACH_ONWARD, _P2_REACH_TOWARD and a reason allow, and for "short of" a landmark. Round 4d sections:1: never an
    onward word ("further", "any further"), and "beyond" or "past" only before a landmark shallower than ``depth``
    ("further than" reads as "beyond") - and, second round, shallower than ``expected`` too, the depth the procedure
    calls for, when given: "Extent: terminal ileum; not advanced beyond the cecum" says the cecum was reached, so it
    denies the label without saying the procedure fell short (the label is doubted, and its extent withheld)."""
    if _P2_REACH_HEDGE.search(text, lo, hi):
        return False
    before = text[lo:hit.start()]
    if _P2_RELATIVE.search(before):
        return False
    if not (_P2_REASON_LEAD.match(before) or _P2_THEN.search(before)):
        masked = before
        for _, _, pattern in table:
            masked = pattern.sub(' ', masked)
        if any(word.lower() not in _P2_REACH_SUBJECT for word in _EXTENT_TAIL_WORD.findall(masked)):
            return False
    words = [(w.start(), w.group(0).lower()) for w in _EXTENT_TAIL_WORD.finditer(text, hit.end(), hi)]
    while words and words[0][1] in ('the', 'a'):
        words.pop(0)
    if 'short' in hit.group(0).lower():
        return bool(words) and _P2_landmark_at(text, words[0][0], table)
    if not words:
        return True
    pos, first = words[0]
    if first in _S2_ONWARD_ONLY:  # round 4d sections:1
        rest = [w for w in words[1:] if w[1] not in ('the', 'a')]
        if first == 'any':
            if not rest or rest[0][1] not in ('further', 'farther'):
                return False
            rest = rest[1:]
        if not rest or rest[0][1] != 'than':
            return False
        first, words = 'beyond', rest  # "further than the sigmoid colon" reads as "beyond the sigmoid colon"
    elif first in _P2_REACH_ONWARD or first in _P2_INSTRUMENT or _P2_REASON_LEAD.match(text, pos) \
            or _P2_landmark_at(text, pos, table):
        return True
    if first in _P2_REACH_TOWARD:
        rest = [w for w in words[1:] if w[1] not in ('the', 'a', 'to', 'far', 'as')]
        landmark = _S2_landmark_depth_at(text, rest[0][0], table) if rest else None
        return landmark is not None and (first not in _S2_BEYOND or (  # round 4d sections:1
            landmark < depth and (expected is None or landmark < expected)))
    return False


def _P2_reach_denied_in(an: Analysis, end: int, stop: int, table, depth: int) -> bool:
    """Whether [end, stop), the rest of an extent label's own sentence, states that its landmark (of ``depth``) was not
    reached: a reach denial of the closed list (_P2_REACH_DENIAL) whose segment speaks of that landmark (round 4c-2
    plan:D2), read against the depth the procedure calls for (_S2_expected_depth; round 4d sections:1)."""
    text = an.text
    for hit in _P2_REACH_DENIAL.finditer(text, end, stop):
        breaks = [b.end() for b in _P2_REACH_BREAK.finditer(text, end, hit.start())]
        after = _P2_REACH_BREAK.search(text, hit.end(), stop)
        if _P2_reach_names_the_landmark(text, breaks[-1] if breaks else end, hit, after.start() if after else stop, table,
                                        depth, _S2_expected_depth(an, table)):
            return True
    return False


def _S2_expected_depth(an: Analysis, table) -> int:
    """The depth the procedure of ``table`` calls for: the cecum for the lower tract, _expected_upper_depth for the
    upper (round 4d sections:1). Memoised per analysis."""
    if table is not cues.UPPER_LANDMARKS:
        return cues.CECUM_DEPTH
    if 's2-expected-upper' not in an.memo:
        an.memo['s2-expected-upper'] = _expected_upper_depth(an)
    return an.memo['s2-expected-upper']


def _P2_reach_denied(an: Analysis, end: int, depth: int, table) -> bool:
    """_P2_reach_denied_in over the rest of the extent label's own sentence (_P2_label_rest), read once per label (round
    4d bounded:6)."""
    key = ('p2-reach-denied', end, depth, id(table))
    if key not in an.memo:
        stop = _P2_label_rest(an, end, depth, table)
        an.memo[key] = stop > end and _P2_reach_denied_in(an, end, stop, table, depth)
    return an.memo[key]


def _P2_refused_label(an: Analysis, reading: Reading, start: int, end: int, ws: int, we: int, depth: int,
                      table) -> bool:
    """Whether the extent label whose landmark is at [start, end) (clause window [ws, we)) would be read as reached in
    _landmarks - a performed or incomplete reading or a silent answer, a reached label and a plain tail - but for
    plan:D's refusal (_P2_label_denied; round 4c-2 plan:D2)."""
    return ((reading.status in ('performed', 'incomplete') or _answers_silently(an, reading, start, end))
            and _reached_label(an, ws, start) and _plain_tail(an, end, we) and _P2_label_denied(an, end, depth, table))


def _P2_doubted_withholds(doubted: list, hits: list, depth: int) -> bool:
    """Whether a label plan:D refuses for no reach denial names a landmark deeper than ``depth``, the deepest one read
    as reached, while the family's text outside that label's own sentence (_P2_outside) denies no landmark between
    the two (round 4c-2 plan:D2): then that shallower landmark decides no extent, and none is read. "The cecum was not
    reached." still lets it decide; a denial of a landmark beyond the label's own ("TI not intubated.") does not."""
    outside = _P2_outside(hits, doubted)
    return any(hit[0] > depth and not any(depth < other[0] <= hit[0] for other in outside) for hit in doubted)


def _S2_doubted_short(doubted: list, hits: list, depth: int, expected: int) -> tuple[bool, Optional[tuple]]:
    """(withhold, label) for the extent labels plan:D refuses for no reach denial (``doubted``) beside ``depth``, the
    deepest landmark read as reached, short of ``expected``, the depth the procedure calls for. A label counts when it
    lies deeper than ``depth`` and the family's text outside its own sentence denies no landmark between the two
    (_P2_doubted_withholds' guard). One at or beyond ``expected`` withholds the extent (plan:D2: it may be the extent
    reached); otherwise the deepest one short of ``expected`` is returned: both of its readings - reached and no
    further, or not reached at all - leave the procedure incomplete, so it reads the procedure incomplete at its own
    landmark, as every base reads it (round 4d sections:1, second round: withholding it erased the incompleteness its
    depth establishes - "Extent: transverse colon; not advanced further due to looping" beside "The colonoscope was
    inserted into the rectum" read performed). Neither when none counts. The guard is read in one sorted sweep, as
    _P2_outside reads it (a hit is outside when its clause starts in no doubted label's own sentence), so the work is
    linear in the labels and the hits, never their product (one line of many labels held thousands of each)."""
    if not any(hit[0] > depth for hit in doubted):
        return False, None
    regions, i, reach, floor = sorted(hit[3] for hit in doubted), 0, -1, None
    for other in sorted(hits, key=lambda hit: hit[2].start):
        start = other[2].start
        while i < len(regions) and regions[i][0] <= start:
            reach = max(reach, regions[i][1])
            i += 1
        if reach <= start and other[0] > depth:  # outside every doubted label's own sentence (_P2_outside)
            floor = other[0] if floor is None else min(floor, other[0])
    clear = [hit for hit in doubted if hit[0] > depth and (floor is None or floor > hit[0])]
    if any(hit[0] >= expected for hit in clear):
        return True, None
    return False, max(clear, key=lambda hit: hit[0], default=None)


def _P2_outside(hits: list, doubted: list) -> list:
    """The landmark hits whose clause does not start inside a doubted label's own sentence after its landmark (round
    4c-2 plan:D2): that sentence is read by the closed list of reach denials alone ("Extent: cecum; no view of the cecum
    due to poor prep" withholds), while a denial elsewhere in the family's text still decides (plan:B2's guard)."""
    regions = [hit[3] for hit in doubted]
    return [hit for hit in hits if not any(lo <= hit[2].start < hi for lo, hi in regions)]


def _P2_denied_beyond(hits: list, depth: int) -> bool:
    """Whether the family's own text denies or doubts reaching a landmark deeper than ``depth``, the deepest one read as
    reached (round 4c-2 plan:B2): "Cecum not reached.", "The cecum could not be reached.", "The transverse colon was not
    reached." Then the document says the procedure fell short, and the shallower landmark's reading stands."""
    return any(hit[0] > depth for hit in hits)


def _answers_silently(an: Analysis, reading: Reading, start: int, end: int) -> bool:
    """Whether the value of an extent label at [start, end) states the extent reached although its section does not
    speak for it: its section is the product's addendum block or a PDF form-field or annotation block
    (_ANSWERING_SECTIONS), its reading is the silent default (no cue at all: nothing hedged, planned,
    historical or denied), and no unresolved negation is in its clause (the doubt a positive section would find:
    "Extent: cecum not reached."). An addendum answering "confirm the furthest extent reached" is read so; the label
    itself still has to pass _reached_label (an aim never does). An indication, an assessment or an impression can
    tell prior work-up, so a label there is still read only when its own wording states performance."""
    section = an.lay.section_at(start)
    return (reading.basis == 'default' and reading.cues == (SILENT,) and section.kind == 'other'
            and section.label in _ANSWERING_SECTIONS and not _doubt(an, start, end))


# The 'other' sections that speak for this report's own procedure (round 4 routing:2): the product's addendum block
# and the PDF form-field and annotation blocks. Any other 'other' section may tell another facility's procedure
# ("Outside records:", "Referral information:", and round 4c declared:3: a "Prep:", "Bowel preparation:" or
# "Complications:" line inside such a block made an outside report's "Extent: cecum" today's extent), so a label
# answered there is never read as today's extent (reverted to the R3B-BASE reading, as the verifier asked).
_ANSWERING_SECTIONS = frozenset(('addendum', 'pdf form fields', 'pdf annotation text'))
_EXTENT_TAIL_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+", re.A)
_VALUE_END = re.compile(r'[.;\n]')
# Round 4c declared:11: a Word table row's next cell (" | ", extraction joins cells so), or a column after a tab or two
# or more spaces, ends the value when it opens one of these report fields ("Extent: Cecum | Prep quality: Good |
# Withdrawal time: 9 min"). A closed list: any other next cell ("| intended", "| Reached: No") stays in the tail, so an
# aim or an answer there still leaves the extent unread.
_SEC_NEXT_CELL = re.compile(r'(?:[ \t]*\|[ \t]*|\t[ \t]*|[ ]{2,})(?:(?:bowel[ \t]+)?prep(?:aration)?(?:[ \t]+quality)?'
                            r'|quality[ \t]+of[ \t]+(?:the[ \t]+)?(?:bowel[ \t]+)?prep(?:aration)?|bbps'
                            r'|boston[ \t]+bowel[ \t]+prep(?:aration)?[ \t]+scale(?:[ \t]+\(bbps\))?|withdrawal[ \t]+time'
                            r'|insertion[ \t]+time|sedation|complications|findings|retroflexion)[ \t]*:', re.A | re.I)


def _plain_tail(an: Analysis, end: int, we: int) -> bool:
    """Whether the value after an extent label's landmark adds nothing but punctuation and cues.EXTENT_TAIL words,
    read to the value's sentence or line end, or to a next cell that opens another report field (_SEC_NEXT_CELL)
    (round 4 routing:9, release:3: "Extent: cecum (intended)." and "cecum (intended; not reached)" name no extent
    reached). A closed list: any other word leaves the extent unread."""
    stop = _VALUE_END.search(an.text, end, we)
    stop_at = stop.start() if stop else we
    cell = _SEC_NEXT_CELL.search(an.text, end, stop_at)
    tail = an.text[end:cell.start() if cell else stop_at]
    return all(word.lower() in cues.EXTENT_TAIL for word in _EXTENT_TAIL_WORD.findall(tail))


def _S2_read_by_the_cut(an: Analysis, end: int, we: int) -> bool:
    """Whether the value after an extent label's landmark (which ends at ``end``; ``we``, its clause window's end), read
    to the value's sentence or line end without declared:11's next-cell cut, holds a word outside cues.EXTENT_TAIL: then
    _plain_tail reads the label only because that cut ends it ("Extent: cecum | Prep quality: Good"; round 4d
    regression:3). Reads at most the clause window, stopping at the first such word."""
    stop = _VALUE_END.search(an.text, end, we)
    return not all(word.group(0).lower() in cues.EXTENT_TAIL
                   for word in _EXTENT_TAIL_WORD.finditer(an.text, end, stop.start() if stop else we))


# Round 4d regression:3, second round: a landmark written as a field's label ("Cecum - not reached", "The cecum | not
# seen", "Cecum (not reached)") is answered across the separator after it, which is the field's own, never a segment
# break of plan:D2's; only "the" or "a" may lead the label in its segment.
_S2_FIELD_SEP = re.compile(r'[ \t]*(?:[;,|(\[]|[-\u2013\u2014]+)[ \t]*', re.A)


def _S2_label_lead(text: str, lo: int, ms: int) -> bool:
    """Whether the landmark at ``ms`` opens its segment (which starts at ``lo``) as a field's label would: no word but
    "the" or "a" before it."""
    return all(word.group(0).lower() in ('the', 'a') for word in _EXTENT_TAIL_WORD.finditer(text, lo, ms))


def _S2_segment(text: str, ws: int, ms: int, me: int, we: int) -> tuple[int, int]:
    """The landmark match [ms, me)'s own segment inside its clause window [ws, we): between plan:D2's separators
    (_P2_REACH_BREAK), past the field's own separator right after a landmark written as a field's label (_S2_FIELD_SEP,
    _S2_label_lead)."""
    lo = _P2_segment_start(text, ws, ms)
    after = _P2_REACH_BREAK.search(text, me, we)
    if after and not text[me:after.start()].strip() and _S2_label_lead(text, lo, ms):
        after = _P2_REACH_BREAK.search(text, after.end(), we)
    return lo, (after.start() if after else we)


def _S2_reach_denial_of(an: Analysis, ms: int, me: int, ws: int, we: int, depth: int, table) -> bool:
    """Whether the landmark match [ms, me) (its clause window [ws, we)) is the subject or the object of a reach denial
    of plan:D2's closed list in its own segment (_P2_REACH_DENIAL, read by _P2_reach_names_the_landmark): "Cecum not
    reached.", "The colonoscope failed to reach the cecum.", "The appendiceal orifice was not visualized.", and across a
    field's own separator after a landmark written as its label ("Cecum - not reached", _S2_segment). Reads the window
    only (round 4d regression:3)."""
    text = an.text
    label = _S2_label_lead(text, _P2_segment_start(text, ws, ms), ms)
    for denial in _P2_REACH_DENIAL.finditer(text, ws, we):
        lo = _P2_segment_start(text, ws, denial.start())
        after = _P2_REACH_BREAK.search(text, denial.end(), we)
        hi = after.start() if after else we
        own = (lo <= ms and me <= hi) or (label and me <= lo and bool(_S2_FIELD_SEP.fullmatch(text, me, lo)))
        if own and _P2_reach_names_the_landmark(text, lo, denial, hi, table, depth):
            return True
    return False


# Round 4d regression:3, second round: what a denial or doubt of a landmark's own reading may be about instead of its
# reach - an act done (or not) at that landmark, or a lesion there ("The cecum was not biopsied.", "No photos of the
# cecum were taken.", "Tattooing of the cecum was deferred.", "Retroflexion in the cecum could not be completed.", "The
# lesion near the cecum could not be reached."); a surgical procedure counts by its form ("due to a prior
# appendectomy"). A closed list: a word it does not name is no act.
_S2_ACT_AT = re.compile(
    r'\b(?:biops\w*|tattoo\w*|photo\w*|pictures?|images?|imaged|video\w*|clip\w*|polyp\w*|lesions?|mass(?:es)?|'
    r'tumou?rs?|lipoma\w*|resect\w*|remov\w*|excis\w*|retroflex\w*|snar\w*|inject\w*|dilat\w*|band(?:s|ed|ing)?|'
    r'ligat\w*|ablat\w*|APC|argon|cauter\w*|coagulat\w*|EMR|ESD|sampl\w*|brush\w*|marked|marking|retriev\w*|'
    r'aspirat\w*|irrigat\w*|lavage|wash\w*|suction\w*|stent\w*|specimens?|cultures?|spray\w*|chromoendoscop\w*|'
    r'hemosta\w*|\w+(?:ectom(?:y|ies)|otom(?:y|ies)|ostom(?:y|ies)|plast(?:y|ies)|pex(?:y|ies)|rrhaph(?:y|ies)|centesis))\b',
    re.A | re.I)
# The words that say a landmark was or was not reached (a reach predicate), and those that say how it was seen (a view
# predicate): only a denial or doubt of these speaks of the extent at all. Closed lists.
_S2_REACH_WORD = re.compile(r'\b(?:reach\w*|intubat\w*|advanc\w*|achiev\w*|enter(?:ed|ing|s)?|pass(?:ed|es|ing)?|'
                            r'travers\w*|attain\w*|access\w*|arriv\w*|made[ \t]+it)\b', re.A | re.I)
# A landmark answered by a bare denial ("Cecum: no.", "Cecum - none"): whether it denies the reach or answers another
# question cannot be read, so it doubts.
_S2_BARE_DENIAL = re.compile(r'[ \t]*(?:[:=\u2013\u2014-][ \t]*)?(?:no|not|none|never|n/?a)[ \t]*(?:\.(?=\s)|\.?[ \t]*\Z)',
                             re.A | re.I)
# ... of which "none" and "N/A" answer a findings-by-segment line as often as a reach ("Cecum: none." - no lesions): even
# when its reading is negated, it only doubts.
_S2_BARE_NONE = re.compile(r'[ \t]*(?:[:=\u2013\u2014-][ \t]*)?(?:none|n/?a)[ \t]*(?:\.(?=\s)|\.?[ \t]*\Z)', re.A | re.I)
_S2_VIEW_WORD = re.compile(r'\b(?:seen|see|visuali[sz]\w*|visible|identif\w*|evaluat\w*|examin\w*|inspect\w*|view\w*|'
                           r'assess\w*)\b', re.A | re.I)


def _S2_contradiction(an: Analysis, ms: int, me: int, ws: int, we: int, explicit: bool, level: int,
                      table) -> Optional[str]:
    """How the blocked or denied landmark match [ms, me) (clause window [ws, we), at ``level``; ``explicit``: its own
    reading is negated, cancelled or incomplete) speaks of reaching it (round 4d regression:3): 'denied' - a reach
    denial of plan:D2's closed list naming it (_S2_reach_denial_of: "Cecum not reached."), or its explicit reading with no
    act in its own segment: with no act there, what is denied is the landmark itself ("No cecal intubation.", "Cecal
    intubation: not done.", "Despite multiple attempts the cecum was not reached.", "Cecum: no.", "Cecum: declined.") -
    but a bare "none" or "N/A" (_S2_BARE_NONE: "Cecum: none.", a findings-by-segment answer) only doubts, unless the
    landmark's own name is the reach ("Cecal intubation: none.");
    'doubted' - a reach word in its segment beside an act ("The cecum was not reached or biopsied.", "The lesion near the
    cecum could not be reached.") or in a reading that only doubts ("The cecum may not have been reached."), or, with no
    act there, a view word, a hedge or a bare denial ("Cecum: not seen.", "The cecum could not be evaluated."); None - its
    segment holds no negation, cue or hedge of its own (its reading comes from another segment: "The colonoscope was
    advanced to the cecum, which was not biopsied."), or what it denies is an act or a finding at the landmark ("The cecum
    was not biopsied.", "Biopsy of the cecum was cancelled.", "The cecum was not inflamed.", "Cecal intubation was not
    photodocumented."): HEAD's reading of the label stands. The segment is the landmark's own (_S2_segment: between
    plan:D2's separators inside the window, a field's own separator after a landmark label included); a reach word of
    the match itself ("cecal intubation") is no reach word for the doubt. Reads the segment only."""
    if _S2_reach_denial_of(an, ms, me, ws, we, level, table):
        return 'denied'
    text = an.text
    lo, hi = _S2_segment(text, ws, ms, me, we)
    hedged = bool(_P2_REACH_HEDGE.search(text, lo, hi))
    if not (hedged or cues.DOUBT_TOKEN.search(text, lo, hi) or any(c.status != 'performed' for c in an.cues_in(lo, hi))):
        return None
    acts = bool(_S2_ACT_AT.search(text, lo, hi))
    if explicit and not acts and (not _S2_BARE_NONE.match(text[me:hi]) or _S2_REACH_WORD.search(text, ms, me)):
        return 'denied'
    if (_S2_REACH_WORD.search(text, lo, ms) or _S2_REACH_WORD.search(text, me, hi)
            or (not acts and (hedged or _S2_VIEW_WORD.search(text, lo, hi) or _S2_BARE_DENIAL.match(text[me:hi])))):
        return 'doubted'
    return None


def _S2_cut_denied(an: Analysis, reached: list, cut: list, cut_denials: list, table, expected: int,
                   sub_acts: bool = False) -> tuple[list, bool]:
    """(``reached``, withhold) after judging each extent label read only because of declared:11's cell cut (``cut``,
    from _landmarks) against the family's own text (round 4d regression:3: "Extent: cecum | Prep quality: Good" then
    "Cecum not reached."). A blocked or denied hit (``cut_denials``) of a landmark deeper than the deepest one reached by
    anything else and no deeper than the label's own may contradict the label (plan:D2's guard, _P2_doubted_withholds),
    as _S2_contradiction reads it:
    - denied ("Cecum not reached.", "No cecal intubation.") - the label is dropped, and 9a9f40301's reading returns: the
      extent withheld, or the procedure incomplete at the shallower landmark it reached;
    - doubted at the label's own depth ("Cecum: not seen.", "The cecum was not well seen due to stool."): whether it
      denies the reach or tells how the landmark was seen cannot be read, so the extent is withheld (``withhold``) and
      asked - never the label's landmark, never a shallower one - when the label lies at or beyond ``expected``, the depth
      the procedure calls for; a label short of it reads the procedure incomplete at its own landmark, as HEAD reads it
      (round 4d, second round: withholding it erased that incompleteness, "Extent: transverse colon | Prep quality: Poor"
      beside "The transverse colon was not well seen due to stool." read performed);
    - doubted, shallower ("The sigmoid colon could not be examined."): the scope passed it; the reading stands;
    - neither - an act or a finding at the landmark denied ("The cecum was not biopsied.", "The cecum was not
      inflamed."): the reading stands (round 4d, second round: such a denial dropped the label and a complete
      colonoscopy read 'incomplete: rectum').
    With ``sub_acts`` (a colonoscopy), a denial of a landmark beyond ``expected`` - the terminal ileum, a sub-act
    (_only_a_sub_act) - only doubts the label: "Extent: terminal ileum | Prep quality: Good" beside "The terminal ileum
    was not intubated." says nothing of the cecum, and dropping the label read a complete colonoscopy 'incomplete:
    rectum' (9a9f40301's reading, which never read the label). A denial beyond the label's landmark ("TI not intubated."
    beside a cecum label) and a label read whole (the listed residual 'round 4c-2 plan:D (rest)') change nothing. Each
    denial is judged once (bounded by the hits)."""
    if not cut:
        return reached, False
    cut_ids = {id(hit) for hit in cut}
    depth = max((hit[0] for hit in reached if id(hit) not in cut_ids), default=0)
    top = max(hit[0] for hit in cut)
    denied, doubted = set(), set()
    for other, ms, me, ws, we, explicit in cut_denials:
        level = other[0]
        if depth < level <= top and level not in denied:
            verdict = _S2_contradiction(an, ms, me, ws, we, explicit, level, table)
            if verdict == 'denied' and sub_acts and level > expected:
                verdict = 'doubted'  # a sub-act's landmark: the label is doubted, never dropped
            if verdict == 'denied':
                denied.add(level)
            elif verdict == 'doubted':
                doubted.add(level)
    dropped = {id(hit) for hit in cut if any(depth < level <= hit[0] for level in denied)}
    withhold = any(hit[0] in doubted and hit[0] >= expected for hit in cut if id(hit) not in dropped)
    return ([hit for hit in reached if id(hit) not in dropped] if dropped else reached), withhold


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
    the depth the named upper endoscopy calls for for an EGD. An extent label plan:D refuses for no reach denial
    counts too (round 4c-2 plan:D2: "Extent: cecum; prep fair?" beside "The terminal ileum was not intubated."): its
    extent is withheld and asked, and a sentence about a sub-act (_only_a_sub_act) reads no incomplete procedure."""
    key = ('reached-depth', family)
    if key not in an.memo:
        table, expected = ((cues.LOWER_LANDMARKS, cues.CECUM_DEPTH) if family == 'gi.colonoscopy'
                           else (cues.UPPER_LANDMARKS, _expected_upper_depth(an)))
        doubted = []
        reached, _ = _landmarks(an, _family_sentences(an, attributed, family), table, None, None, doubted)
        an.memo[key] = max((hit[0] for hit in reached + doubted), default=0) >= expected
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


def _box_own_option_off(an: Analysis, start: int, end: int) -> bool:
    """Whether the status reference [start, end) is a denying option of a line with boxes whose own box, read by the
    line's option words (_box_option_states, as _unchecked_option and _box_checked_option read them), is unchecked:
    "Aborted" of "Status: Completed ☒ Aborted ☐ Cancelled ☐". Such an option states nothing (round 5 regression:4:
    read where an item would be, the box before it, Completed's ☒, was taken for its own). The line is read within
    BOX_REACH of the reference. Round 4d BOXES3: never on a row the strict check-box rows hold (_B3_hold): its marks
    cannot be paired with its entries with certainty, so no box there is the option's own (round 6 regression:0, 5)."""
    if _B3_hold(an, start, end) is not None:
        return False
    text = an.text
    lo = max(text.rfind('\n', max(0, start - BOX_REACH), start) + 1, start - BOX_REACH)
    newline = text.find('\n', end, end + BOX_REACH)
    hi = min(len(text), end + BOX_REACH) if newline < 0 else newline
    if not _box_tokens(an, lo, hi)[1]:
        return False
    options = _box_denying_options(an, lo, hi)
    own = [i for i, (s, e) in enumerate(options) if _overlaps(s, e, start, end)]
    if not own:
        return False
    words = options + [m.span() for m in _BOX_DONE_OPTION.finditer(text, lo, hi)]
    states = _box_option_states(an, lo, hi, options, words)
    return all(states[i] == 'off' for i in own)


# --- round 4c-2 box2:I: an unchecked option's own words state nothing about the service or the item beside it ---------
# The statuses a denying or plan option's own words carry (_box_denying_options: a cancelling, planning, doubting,
# historical or incomplete cue, an act denial): an unselected option neither denies nor holds (_unchecked_option).
_B2_DENYING_STATUSES = ('cancelled', 'planned', 'uncertain', 'historical', 'incomplete', 'negated')
_B2_OPTION_UNREAD = "uncertain: '{}' is an option on its line whose own box cannot be read"
_B2_OPTION_ACROSS = "uncertain: the passage runs across the option '{}', whose own box is unchecked, and other words"
_B2_OPTION_BLANK = "uncertain: '{}' is an unchecked option on a line that selects nothing"
_B2_OPTION_REMARK = ("uncertain: '{}' stands in the text of an unchecked option with other option words, so whether it "
                     'is the option or a remark about the service cannot be told')
_B2_OPTION_BOX = ('uncertain: the unchecked box it is read by may be the box of an option beside it: read by its '
                  "line's option words, its own box is checked, or the line can be read both ways")
_B2_OTHER_BOX = ('uncertain: the checked box it is read by may be the box of another entry on its line: read by its '
                 "line's option words, its own box is unchecked")
_B2_ROW_ACROSS = ("uncertain: the passage runs from its status line's label across the line's options, whose denying "
                  'options are unchecked')


def _B2_option_words(an: Analysis, start: int, end: int, ts: int, te: int, shown: str,
                     status: str) -> Optional[list]:
    """How a clause reader reads the words [start, end) for the target [ts, te) when they may be a status option's own
    words (_B2_unselected_option): None to read them as before, [] when the option's own box is unchecked and the
    target lies outside its words (they state nothing about it), or the hold to read instead when its box cannot be
    read, when its line selects nothing, when its text may hold a remark, or when the target runs across the option
    and other words. A hold carries ``status``, what the words would have said, so it keeps their rank among the
    clause's cues (_cue_reading): "☒ Rescheduled ☐ Completed - aborted at the splenic flexure" is held, never read by
    the rescheduling alone (planned, while the family read performed)."""
    unselected = _B2_unselected_option(an, start, end, ts, te)
    if unselected == 'off':
        return []
    if unselected == 'unpaired':  # round 4d BOXES3: held with the strict rows' cue, keeping the words' rank
        return [('uncertain', _B3_hold(an, start, end), False, True, status)]
    if unselected in ('unknown', 'across', 'blank', 'remark'):
        label = {'unknown': _B2_OPTION_UNREAD, 'across': _B2_OPTION_ACROSS, 'blank': _B2_OPTION_BLANK,
                 'remark': _B2_OPTION_REMARK}[unselected]
        return [('uncertain', label.format(' '.join(shown.split())[:80]), False, True, status)]
    return None


def _B2_unselected_option(an: Analysis, start: int, end: int, ts: int, te: int) -> Optional[str]:
    """Whether the words [start, end) are those of a denying or plan option of a line with boxes (_B2_status_line:
    "Cancelled" of "Colonoscopy: ☒ Completed ☐ Cancelled", "in 3 years" of "☑ Cold snare polypectomy ☐ Repeat in 3
    years") that says nothing of the target [ts, te): 'off' when that option's own box is unchecked and the target lies
    outside the option's own words (from its box to the next box, or from the box before it, or the line's label, to
    its own box, as the line's boxes lead or trail), 'blank' when it is unchecked on a line that selects nothing,
    'remark' when it is unchecked but its text may hold a remark,
    'unknown' when its box cannot be read or disagrees, 'across' when the target runs across the unchecked option and
    other words, else None. A target inside the option's words ("☐
    Repeat colonoscopy in 3 years") and prose after a single box ("☐ Biopsy. Repeat colonoscopy in 3 years.") read as
    before. Round 5 regression:4 (ARCHITECTURE 5.3), carried from the status references to the clause readers a
    service or an item is read by. The option is read once per span (memoised). 'unpaired' (round 4d BOXES3) when the
    strict check-box rows hold the option's words (_B3_hold): its row's marks cannot be paired with its entries with
    certainty, so they are never dropped (round 6 regression:1, regression:2)."""
    if _B3_hold(an, start, end) is not None:
        return 'unpaired'
    key = ('b2-unselected', start, end)
    if key not in an.memo:
        an.memo[key] = _B2_option_reading(an, start, end)
    found = an.memo[key]
    if found is None:
        return None
    state, text_lo, text_hi = found
    end_ = max(te, ts + 1)
    if text_lo <= ts and end_ <= text_hi:
        return None  # the target is the option's own words: its own box reads it
    if end_ <= text_lo or ts >= text_hi:  # a target beside the option
        if state == 'off' and not _B2_target_selected(an, start, end, ts, te):
            return 'unknown'  # an item it names is not itself checked: what reads it then cannot be told
        return state
    # a passage across the option and other words ("☑ Cold snare polypectomy ☐ Repeat in 3 years" cited whole): held
    return 'across' if state == 'off' else state


def _B2_target_selected(an: Analysis, start: int, end: int, ts: int, te: int) -> bool:
    """Whether every item the target [ts, te) names on the status line of the option words [start, end), after its
    label, has its own box checked, read by the line's entries (_B2_status_line); True when it names none there (the
    label, or a target off the line). The option's words then state nothing about it, and it is read by its own box.
    An item that is not itself checked keeps the hold: the box reader, which sees no option word, may give it another
    item's box ("Planned ☐ | Biopsy ☒ | Cold snare polypectomy ☐" reads as if its boxes lead, so the unchecked
    polypectomy takes the biopsy's ☒), and dropping the option's words would read it performed."""
    line = _B2_status_line(an, *_B2_line_window(an, start, end))
    return line is None or all(state == 'on' for state in _B2_listed_states(line, ts, te))


def _B2_listed_states(line: tuple, start: int, end: int) -> list:
    """The states of the status line's items (after its label, _B2_item_runs) that the passage [start, end) names."""
    return [state for (s, e), state in line[8] if _overlaps(s, e, start, max(end, start + 1))]


def _B2_item_runs(text: str, items: list) -> list:
    """The items, those written next to each other with nothing but spaces between them joined into one entry ("Cold
    snare" and "polypectomy" of "Cold snare polypectomy ☒"): one name, which the box after it governs whole."""
    runs = []
    for start, end in items:
        if runs and not text[runs[-1][1]:start].strip(' \t'):
            runs[-1] = (runs[-1][0], end)
        else:
            runs.append((start, end))
    return runs


def _B2_line_window(an: Analysis, start: int, end: int) -> tuple[int, int]:
    """The line of [start, end) within BOX_REACH of it, as _box_own_option_off reads a status line."""
    text = an.text
    lo = max(text.rfind('\n', max(0, start - BOX_REACH), start) + 1, start - BOX_REACH)
    newline = text.find('\n', end, end + BOX_REACH)
    return lo, min(len(text), end + BOX_REACH) if newline < 0 else newline


def _B2_status_line(an: Analysis, lo: int, hi: int) -> Optional[tuple]:
    """The status line [lo, hi) read option by option: (label end, its denying options (_box_denying_options) and their
    states, its completion options (_BOX_DONE_OPTION; one inside a denying option, "Not performed", is merged into it
    and has its state) and their states, its boxes, its entries, whether any entry's own box is checked, and its items
    with their states), or None when it has no box or no denying option. The states are read by the line's entries as _box_own_option_off reads them
    (_box_option_states: the boxes lead when the first box comes before the first entry, trail when the last box comes
    after the last; 'unknown' when the line can be read both ways). The entries are the option words and the line's
    box-marked items (_B2_item_runs), but not its label: what opens the line before its first box and its first option
    word and ends in ":" or "|" ("Colonoscopy:" of "Colonoscopy: ☒ Completed ☐ Cancelled" or of "Colonoscopy:
    Cancelled ☐ | Completed ☒", "Colonoscopy status:"), which is what its options are about. So "Cold snare
    polypectomy ☒ | Repeat in 3 years ☐", which the option words alone would read as leading, trails. Memoised per
    line."""
    key = ('b2-status-line', lo, hi)
    if key not in an.memo:
        text = an.text
        items, boxes = _box_tokens(an, lo, hi)
        options = _box_denying_options(an, lo, hi) if boxes else []
        result = None
        if options:
            done = [m.span() for m in _BOX_DONE_OPTION.finditer(text, lo, hi)]
            cut = min([boxes[0][0]] + [s for s, _ in options + done])
            head = text[lo:cut].rstrip(' \t')
            label_end = lo + len(head) if head.endswith((':', '|')) else lo
            listed = _B2_item_runs(text, [item for item in items if item[0] >= label_end])
            entries = options + done + listed
            states = _box_option_states(an, lo, hi, entries, entries)
            result = (label_end, options, states[:len(options)], done, states[len(options):len(options) + len(done)],
                      boxes, entries, 'on' in states, tuple(zip(listed, states[len(options) + len(done):])))
        an.memo[key] = result
    return an.memo[key]


def _B2_option_reading(an: Analysis, start: int, end: int) -> Optional[tuple]:
    """(state, text start, text end) of the denying option the words [start, end) belong to on a status line
    (_B2_status_line), or None when they are none or its own box is checked: 'off' (unchecked), 'blank' (unchecked, on
    a line that selects nothing: "Colonoscopy: ☐ Not done ☐ Completed" says nothing either way, so it is held),
    'remark' (unchecked, but its text holds more than one run of option words, denying or completing: "☐ Cancelled -
    aborted at the splenic flexure", "☐ Completed - aborted at the splenic flexure", where the later words may be a
    remark about the service and not the option's own, so it is held) or
    'unknown' (unread, disagreeing, or a line its boxes can be read both ways). Its words run between the boxes around
    it, and never into the line's label."""
    lo, hi = _B2_line_window(an, start, end)
    line = _B2_status_line(an, lo, hi)
    if line is None:
        return None
    label_end, options, states, done, _, boxes, _, selected, _ = line
    own = [i for i, (s, e) in enumerate(options) if _overlaps(s, e, start, end)]
    if not own:
        return None
    found = {states[i] for i in own}
    index = _B3_line_index(an, line, lo, hi)
    text_lo, text_hi = _B2_option_text(line, min(options[i][0] for i in own), max(options[i][1] for i in own), hi,
                                       index)
    if found & {'unknown', 'mixed', 'unclear'}:
        return 'unknown', text_lo, text_hi
    if found == {'off'}:
        if _B2_has_remark(an.text, line, text_lo, text_hi, index):
            return 'remark', text_lo, text_hi
        return ('off' if selected else 'blank'), text_lo, text_hi
    return None


def _B2_option_text(line: tuple, option_start: int, option_end: int, hi: int,
                    index: Optional[tuple] = None) -> tuple[int, int]:
    """[start, end) of the text of the option at [option_start, option_end) on the status line ``line``: from the box
    before it (or the line's label) to the box after it (or the end of the window ``hi``). ``index``: the line's sorted
    box ends and starts (_B3_line_index), read by bisection instead of a scan of every box (round 6 bounded:0)."""
    label_end, boxes = line[0], line[5]
    if index is not None:
        ends, starts = index[0], index[1]
        before = bisect.bisect_right(ends, option_start)
        after = bisect.bisect_left(starts, option_end)
        return (max(ends[before - 1], label_end) if before else label_end,
                starts[after] if after < len(starts) else hi)
    return (max([b[1] for b in boxes if b[1] <= option_start] + [label_end]),
            min((b[0] for b in boxes if b[0] >= option_end), default=hi))


def _B2_has_remark(text: str, line: tuple, text_lo: int, text_hi: int, index: Optional[tuple] = None) -> bool:
    """Whether the option text [text_lo, text_hi) of the status line ``line`` holds more than one run of option
    words, denying or completing (_B2_option_clusters): the later run may be a remark about the service. ``index``:
    the line's option words sorted (_B3_line_index), the ones in the text found by bisection (round 6 bounded:0)."""
    if index is not None:
        words, word_starts = index[2], index[3]
        spans = []
        for at in range(bisect.bisect_left(word_starts, text_lo), len(words)):
            if words[at][0] > text_hi:
                break
            if words[at][1] <= text_hi:
                spans.append(words[at])
        return _B2_option_clusters(text, spans) > 1
    return _B2_option_clusters(text, [o for o in line[1] + line[3] if text_lo <= o[0] and o[1] <= text_hi]) > 1


def _B3_line_remark(an: Analysis, line: tuple, lo: int, hi: int) -> bool:
    """Whether any unchecked denying option of the status line read in [lo, hi) holds a remark in its text
    (_B2_has_remark), as _B2_label_state asks: read once per line window, each option by bisection (round 6 bounded:0:
    asked again for every passage, each scanning every box and every option per unchecked option)."""
    key = ('b3-line-remark', lo, hi)
    if key not in an.memo:
        index = _B3_line_index(an, line, lo, hi)
        an.memo[key] = any(_B2_has_remark(an.text, line, *_B2_option_text(line, s, e, hi, index), index)
                           for (s, e), state in zip(line[1], line[2]) if state == 'off')
    return an.memo[key]


def _B3_line_index(an: Analysis, line: tuple, lo: int, hi: int) -> tuple:
    """(box ends, box starts, option words, their starts) of the status line read in the window [lo, hi), each
    sorted, built once per window: the option readers find an option's text and the words in it by bisection, so a
    long status line is never rescanned per option (round 6 bounded:0: 2,699 options x every box and option)."""
    key = ('b3-line-index', lo, hi)
    if key not in an.memo:
        words = sorted(set(line[1] + line[3]))
        an.memo[key] = (sorted(b[1] for b in line[5]), sorted(b[0] for b in line[5]), words, [w[0] for w in words])
    return an.memo[key]


def _B2_option_clusters(text: str, spans: list) -> int:
    """How many runs the option words ``spans`` of one option's text form: words next to each other, or overlapping,
    with nothing but spaces between them are one ("Not done", "Repeat colonoscopy in 5 years"); anything else between
    them starts another ("Cancelled - aborted at the splenic flexure", "Planned for next visit")."""
    runs, last = 0, None
    for start, end in sorted(set(spans)):
        if last is None or (start > last and text[last:start].strip()):
            runs += 1
            last = end
        else:
            last = max(last, end)
    return runs


def _B2_label_state(an: Analysis, start: int, end: int) -> Optional[str]:
    """What its status line says of a passage that opens in the line's label (_B2_status_line: "Colonoscopy" of
    "Colonoscopy: ☐ Cancelled ☒ Completed" or of "Colonoscopy: Cancelled ☐ | Completed ☒"), which the box reader reads by
    the first box after the label, an option's. When every denying option's own box is unchecked and a completion
    option's is checked, the line says it was done: 'on' for a passage within the label (read as a checked box's
    passage; the option's words state nothing about it), 'across' for one that runs on into the options (held, as a
    passage across an unchecked option and other words is). 'unknown' when an option's box cannot be read, the line
    can be read both ways, or an unchecked option's text may hold a remark (_B2_has_remark: "Colonoscopy: ☐ Incomplete
    - patient declined further sedation ☒ Completed"); else None (read as before: "Colonoscopy: ☐ Completed ☒
    Cancelled" stays denied). 'unpaired' (round 4d BOXES3) when the strict check-box rows hold the passage (_B3_hold):
    its row's marks cannot be paired with its entries in exactly one way, so its options are not read at all."""
    if an.text.find('\n', start, end) >= 0:
        return None
    if _B3_hold(an, start, end) is not None:
        return 'unpaired'
    lo, hi = _B2_line_window(an, start, end)
    line = _B2_status_line(an, lo, hi)
    if line is None or start >= line[0]:
        return None
    label_end, options, states, _, done_states, _, _, _, _ = line
    if any(state in ('unknown', 'mixed', 'unclear') for state in states + done_states) or _B3_line_remark(an, line, lo, hi):
        return 'unknown'
    if all(state == 'off' for state in states) and 'on' in done_states:
        return 'on' if max(end, start + 1) <= label_end else 'across'
    return None


def _B2_item_box_differs(an: Analysis, start: int, end: int, against: str = 'on') -> bool:
    """Whether the items the passage [start, end) names after its status line's label (_B2_status_line), read by the
    line's entries, are not all unchecked, where the box reader, which sees no option word, reads the passage by an
    unchecked box: an item's own box is checked ("Repeat in 3 years ☐ | Cold snare polypectomy ☒": the option is no
    item, so the boxes look as if they lead and the reader takes ☐ for the polypectomy's; the item alone and the row
    cited whole), or the line can be read both ways ("Colonoscopy ☐ Cancelled ☒ Completed"). The passage is then held.
    ``against`` 'off': for a passage the box reader reads by a checked box, whether an item it names has its own box
    unchecked ("Not performed ☐ Biopsy ☒ Cold snare polypectomy ☐": the polypectomy took the biopsy's ☒).
    An item the entries give no box of its own is not read so: a question's "?" ("Endoscopy attempted?: ☐ Yes ☒ No")
    and a plan option's words ("Follow-up colonoscopy in 3 years ( )") are option words to them."""
    if an.text.find('\n', start, end) >= 0:
        return False
    line = _B2_status_line(an, *_B2_line_window(an, start, end))
    if line is None:
        return False
    states = _B2_listed_states(line, start, end)
    if against == 'off':
        return 'off' in states
    return 'on' in states or any(state in ('unknown', 'mixed', 'unclear') for state in states)


# --- round 4c-2 box2:K: a row whose first word is neither an item nor an option --------------------------------------
_B2_ROW_READINGS = ('uncertain: its line can be read with the boxes leading or trailing, and the two readings give it '
                    'different boxes')


def _B2_entry_runs(text: str, lo: int, hi: int, boxes: list) -> list:
    """The word runs of the line part [lo, hi) between its boxes, each trimmed of spaces and cell bars: every entry the
    boxes may mark, item or not ("Photos", "Biopsy", "Cold snare polypectomy" of "Photos ☐ | Biopsy ☒ | Cold snare
    polypectomy ☐"). The first run's text up to its last ":" is the line's label, which its boxes do not mark
    ("Colonoscopy:" of "Colonoscopy: ☐ biopsy ☒ cold snare" or of "Colonoscopy: Pending ☐ | Completed ☒")."""
    edges = [lo] + [edge for box in boxes for edge in (box[0], box[1])] + [hi]
    runs = []
    for index in range(0, len(edges) - 1, 2):
        run_lo, run_hi = edges[index], edges[index + 1]
        if index == 0:
            colon = text.rfind(':', run_lo, run_hi)
            run_lo = colon + 1 if colon >= 0 else run_lo
        part = text[run_lo:run_hi]
        left, right = len(part) - len(part.lstrip(' \t|')), len(part.rstrip(' \t|'))
        if right > left and _B2_WORD.search(part, left, right):
            runs.append((run_lo + left, run_lo + right))
    return runs


_B2_WORD = re.compile(r'\w')


def _B2_runs_disagree(an: Analysis, start: int, end: int, state: Optional[str], item: bool = True) -> bool:
    """Whether the passage [start, end), which the box reader reads by a checked or an unchecked box, takes the other
    state when its line is read with every word run between the boxes as an entry (_B2_entry_runs, read as
    _box_option_states reads a status line's entries: the boxes lead when the first box comes before the first run,
    trail when the last box comes after the last). The box reader orients a row by its items only, so a first word
    that is neither an item nor an option ("Photos ☐ | Biopsy ☒ | Cold snare polypectomy ☐") makes it lead, and each
    item takes the box of the entry before it: the unchecked polypectomy read performed, the checked biopsy negated
    (d05326ef read each by its own box). ARCHITECTURE 5.3: a row whose boxes can be read as leading or trailing holds
    the items the readings disagree on. Only a passage inside one run, and only a definite disagreement, checked or
    unchecked: a line the runs leave unread either way, one whose boxes answer yes or no, or one whose entries are
    labelled with a colon before their box (_box_orientation reads those), reads as before. ``item``: only a passage
    that names an item (a service, an intervention, a gi.other name; the visit statement's reader passes False for
    itself), so a status reference ("Procedure cancelled" of "Procedure completed ☐ | Procedure cancelled ☒") is read
    as before."""
    if state not in ('on', 'off') or an.text.find('\n', start, end) >= 0:
        return False
    if item and not _box_tokens(an, start, max(end, start + 1))[0]:
        return False
    _, _, lo, hi = _box_segment(an, start, end)
    boxes = _box_tokens(an, lo, hi)[1]
    text = an.text
    if not boxes or any(_OPTION_BEFORE.search(text, max(lo, b[0] - 20), b[0]) or _OPTION_AFTER.match(text, b[1], hi)
                        for b in boxes):
        return False  # yes / no answers are read by the option they mark (_group_state), not as entries
    runs = _B2_entry_runs(text, lo, hi, boxes)
    if any(text[run[1] - 1] == ':' for run in runs):
        return False  # entries labelled "X:" before their box are round 4c's ("Colonoscopy: ☐ EGD: ☒ dilation")
    own = [run for run in runs if run[0] <= start and max(end, start + 1) <= run[1]]
    if len(own) != 1:
        return False
    other = _box_option_states(an, lo, hi, own, runs)[0]
    return other in ('on', 'off') and other != state


# --- round 4c-2 box2:L: a service-labelled status row with a hold word checked -------------------------------------
_B2_LABEL_HOLD = "uncertain: its status line checks '{}', which holds it"


def _B2_label_hold(an: Analysis, start: int, end: int) -> Optional[str]:
    """The hold of a passage that opens in a status line's label (_B2_status_line: "Colonoscopy" of "Colonoscopy: ☒
    Incomplete ☐ Completed", the row cited whole, "Colonoscopy status: ...") when a hold word of the line (an option
    beside its own mark, _BOX_STATUS_HOLD_WORD: pending, incomplete, on hold, TBD, TBA, unknown, unclear, requested,
    ...; round 4c regression:0) has its own box checked: the cue naming it, else None. As under "Status:", where the
    line's hold words hold the service; a service's name as the label read it performed (45378 ready). The callers
    read it only where the passage would otherwise read performed. Round 4d BOXES3: a passage the strict check-box rows
    hold (_B3_hold) takes their cue; the label ends at any of the shared separators (_B3_LABEL_SEP: "Colonoscopy -
    ☒ Incomplete ☐ Completed", "Colonoscopy completed: ☒ Incomplete", a tab, "=": round 6 declared:2); and a hold word
    whose own box cannot be read or disagrees holds it too, as its option ("'Pending' is an option on its line whose
    own box cannot be read": round 6 declared:3). Only holds."""
    if an.text.find('\n', start, end) >= 0:
        return None
    unpaired = _B3_hold(an, start, end)
    if unpaired is not None:
        return unpaired
    lo, hi = _B2_line_window(an, start, end)
    if not (_BOX.search(an.text, lo, hi) or _BOX_UNREAD.search(an.text, lo, hi) or _BOX_RADIO.search(an.text, lo, hi)):
        # no mark in the window: its status line has no box (_box_tokens_read finds none, and no positional mark
        # without one), so it is None - answered without reading and memoising the window's items for every performed
        # mention of a box-free text (round 7 bounded:3: 34 MB of them at 30,000 characters of "EUS; EUS; ...")
        return None
    line = _B2_status_line(an, lo, hi)
    if line is None:
        return None
    label_end = max(line[0], _B3_label_end(an.text, lo, line[5][0][0]))
    if start >= label_end:
        return None
    # A passage in the label only by the shared separators, on a line of one mark ("Colonoscopy - ☒ Incomplete"): the
    # status line's entries take the label for one, so a hold word beside the mark reads that mark's state.
    single = line[5][0] if start >= line[0] and len(line[5]) == 1 else None
    for (option_start, option_end), state in zip(line[1], line[2]):
        if not _BOX_STATUS_HOLD_WORD.fullmatch(an.text, option_start, option_end):
            continue
        if single is not None and _box_beside_a_mark(an.text, option_start, option_end, lo, hi):
            state = 'unknown' if single[2] == 'unread' else single[2]
        if state == 'on':
            return _B2_LABEL_HOLD.format(an.text[option_start:option_end])
        if state in ('unknown', 'mixed', 'unclear'):
            return _B2_OPTION_UNREAD.format(an.text[option_start:option_end])
    return None


def _B3_label_end(text: str, lo: int, first_mark: int) -> int:
    """The end of a status line's label in [lo, first_mark), the text before its first mark: after its last label
    separator (_B3_LABEL_SEP) and the spaces after it, or ``lo`` when it has none (round 6 declared:2)."""
    last = None
    for last in _B3_LABEL_SEP.finditer(text, lo, first_mark):
        pass
    return lo if last is None else _BOX_RUN_GAP.match(text, last.end(), first_mark).end()


# --- round 4d BOXES3: strict check-box rows (contract-r4d section 4) -------------------------------------------------
# ONE predicate (_B3_row) decides whether the check boxes of a passage's row can be read. The row is the passage's box
# segment on its line (_box_segment: its sentence, joined to the sentences beside it on the line that open with a box
# when that run ends with one). A row of one mark that is not the unread mark keeps its reading. Any other row is read
# only when its marks and its entries pair in exactly one way (_B3_pairing: the word runs between the marks are its
# entries, after the row's label; every entry has exactly one mark, all leading or all trailing their entries) and
# every reader of the row pairs them so (_B3_agrees): the box reader for each item (_box_state), the option readers for
# each status option (_box_option_states over the row and over the option's own line window, as _box_own_option_off and
# _box_checked_option read it, and _B2_status_line). Every box reader consults it first (_B3_hold): on any other row of
# two or more marks, or one with an unread mark, a passage the row's marks may govern is held (uncertain, a doubt, the
# cue below), never ready and never newly negated or excluded. On a row that pairs, the declared box contract applies
# as before, and an unread mark holds what it may govern: the entry it marks (as before), a passage across it, and the
# label of a row of options (read by every option: round 6 declared:0, declared:3).
B3_ROW_CHARS = 1000  # a box row longer than this is never paired: it is held (bounds the work per row)
B3_LINE_MARKS = 64  # a line with more marks than this is never paired, row by row: held (bounds the work per line)
# A row with a mark past the document's first B3_DOCUMENT_MARKS is never paired: held (bounds the work per document).
# Pairing reads each option in its own line window, and a line's cap leaves the document's unbounded: 64-mark rows one
# per line kept a window read per option, 98 MB at 50,000 characters, and a 300,000-character paste of them overran the
# analyze stage's memory where aaf517e read it in 3 s (round 7 bounded:0, regression:0).
B3_DOCUMENT_MARKS = 1000
_B3_ROW_HOLD = ("uncertain: the check boxes on the line '{}' cannot be paired with its entries in exactly one way, so "
                'what they say of it is held')
_B3_HOLD_PREFIX = _B3_ROW_HOLD.split("'")[0]
# The cap's hold (B3_ROW_CHARS, B3_LINE_MARKS): the row is never paired, so the cue says so (round 4d integration, BOXES3
# verifier's new problem 7: "cannot be paired in exactly one way" was untrue of a row nobody tried to pair). Same prefix,
# so every reader that recognises the strict rows' hold recognises it.
_B3_ROW_UNPAIRED = ("uncertain: the check boxes on the line '{}' are not paired with its entries (the row is too long, or "
                    'its line carries too many check boxes), so what they say of it is held')
assert _B3_ROW_UNPAIRED.split("'")[0] == _B3_HOLD_PREFIX
_B3_DOCUMENT_UNPAIRED = ("uncertain: the check boxes on the line '{}' are not paired with its entries (the document has "
                         'more than ' + f'{B3_DOCUMENT_MARKS:,}' + ' check boxes up to it), so what they say of it is held')
assert _B3_DOCUMENT_UNPAIRED.split("'")[0] == _B3_HOLD_PREFIX
_B3_DOCUMENT_CAP_KEY = ('b3-document-cap',)  # where the document's mark past B3_DOCUMENT_MARKS starts
_B3_LINES_KEY = ('b3-line-breaks',)  # the text's line breaks, sorted (each line's bounds are read by bisection)
# What ends a row's label in the text before its first mark: a colon (after the label's own "?"), a cell bar, "=", a
# tab, a dash with a space on either side (the shared grammar's separators, _BOX_Q_SEP: round 6 declared:2), a linking
# word ("with", "w/", "including": _BOX_LEAD_GAP), or a comma right before the mark ("Colonoscopy, ☐ biopsy ☒ cold
# snare", structure:0). A hyphen inside a word ("Fine-needle") is none.
_B3_LABEL_SEP = re.compile(r'[:|=\t]|(?<=[ \t])[-–—](?=[ \t])|\b(?:with|including)\b|\bw/'
                           r'|,(?=[ \t ]*\Z)', re.A | re.I)
# An entry that is one yes/no answer ("Yes", "No", "None", "Not done", "N/A"): a row of them answers its label.
_B3_YES_NO = re.compile(r'(?:' + _OPTION_WORDS + r'|n/a)[ \t.]*', re.A | re.I)
_B3_CELL_BEFORE = re.compile(r'[|\t][ \t ]*\Z')  # a cell bar or tab right before a mark ("Biopsy | ☐")
_B3_CELL_AFTER = re.compile(r'[ \t ]*(?:[|\t]|\Z)')  # a cell bar or tab, or the row's end, after it ("☐ | Cold")


# A word, where a box or mark of any spelling, with what is written straight after it, is one ("[ x ]", "( x )",
# "[  x  ]" as "☒": round 6 declared:5); every other word is split at whitespace as str.split() splits it.
_B3_WORD_OR_MARK = re.compile('(?:' + _BOX_MARK.pattern + r')\S*|\S+')


def _B3_words(text: str, lo: int, hi: int, limit: int) -> int:
    """The number of words of [lo, hi) (_B3_WORD_OR_MARK), counted up to ``limit`` + 1: a bounded read, so a long line
    is never split whole (the short-line bounds of _denies and _bare_denial ask only whether it is within a few)."""
    count = 0
    for _ in _B3_WORD_OR_MARK.finditer(text, lo, hi):
        count += 1
        if count > limit:
            break
    return count


def _B3_shown_line(an: Analysis, start: int, end: int) -> str:
    """The line from the start of the line of ``start`` to the end of the line of ``end``, its whitespace collapsed, at
    most 160 characters: what the status-row holds quote. Memoised per line, its bounds found by bisection (round 6
    bounded:2: every reference of a long one-line row split and joined the whole line again to keep 160 characters)."""
    line_start, line_end = _B3_line(an, start)[0], _B3_line(an, end)[1]
    key = ('b3-shown', line_start, line_end)
    if key not in an.memo:
        an.memo[key] = ' '.join(an.text[line_start:line_end].split())[:160]
    return an.memo[key]


def _B3_line(an: Analysis, pos: int) -> tuple[int, int]:
    """[start, end) of the physical line holding ``pos``: found by bisection over the text's line breaks, indexed once
    per text, so a long line is never scanned again per passage."""
    if _B3_LINES_KEY not in an.memo:
        an.memo[_B3_LINES_KEY] = [m.start() for m in re.finditer('\n', an.text)]
    breaks = an.memo[_B3_LINES_KEY]
    index = bisect.bisect_left(breaks, pos)
    return (breaks[index - 1] + 1 if index else 0), (breaks[index] if index < len(breaks) else len(an.text))


def _B3_word_run(text: str, lo: int, hi: int) -> Optional[tuple[int, int]]:
    """[lo, hi) trimmed of spaces and cell bars, or None when no word is left (as _B2_entry_runs trims a run)."""
    part = text[lo:hi]
    left, right = len(part) - len(part.lstrip(' \t| ')), len(part.rstrip(' \t| '))
    if right > left and _B2_WORD.search(part, left, right):
        return lo + left, lo + right
    return None


def _B3_pairing(an: Analysis, lo: int, hi: int, marks: list, label_end: int, options: list) -> Optional[tuple]:
    """('lead' | 'trail', [((run start, run end), mark index or None)]) of the row [lo, hi) read with its label ending
    at ``label_end``, or None when its marks and its entries (the word runs between the marks, after the label) do not
    alternate one to one: two marks with no entry between them (one entry's boxes), a last mark with no entry after it
    in a leading row, or an entry before the first mark and one after the last that names an option. In a leading row
    every mark comes before its entry, and an entry ending in ":" before the next mark is that mark's label, so the row
    cannot lead ("Colonoscopy: ☐ EGD: ☒ dilation"); in a trailing row every mark comes after its entry, and a last run
    naming no option is a remark no mark governs ("... | ☒ | clip placed after polypectomy", ARCHITECTURE 5.3), unless
    the last mark is the unread mark, which may be the box of the run after it as well: 'ambiguous'."""
    text = an.text
    sequence, cursor = [], label_end
    for index, (start, end, _) in enumerate(marks):
        run = _B3_word_run(text, cursor, start)
        if run:
            sequence.append(('run', run))
        sequence.append(('mark', index))
        cursor = end
    run = _B3_word_run(text, cursor, hi)
    if run:
        sequence.append(('run', run))
    if any(a[0] == b[0] for a, b in zip(sequence, sequence[1:])):
        return None
    if sequence[0][0] == 'mark':
        if sequence[-1][0] != 'run':
            return None
        pairs = [(sequence[i + 1][1], sequence[i][1]) for i in range(0, len(sequence), 2)]
        if any(text[run[1] - 1] == ':' for run, _ in pairs[:-1]):
            return None
        return 'lead', pairs
    pairs = [(sequence[i][1], sequence[i + 1][1]) for i in range(0, len(sequence) - 1, 2)]
    if len(sequence) % 2:
        remark = sequence[-1][1]
        if marks[-1][2] == 'unread':
            return 'ambiguous'  # the unread mark may be the box of the text after it as well (ARCHITECTURE 5.1)
        if any(remark[0] < e and s < remark[1] for s, e in options) or _B3_YES_NO.fullmatch(text, *remark):
            return None
        pairs.append((remark, None))
    return 'trail', pairs


def _B3_label_reading(an: Analysis, lo: int, hi: int, marks: list, options: list) -> Optional[tuple]:
    """(label end, orientation, pairs) of the row [lo, hi): the one way its marks and its entries pair, or None when
    they pair in none or in more than one. The text before the first mark is the row's label up to its last label
    separator (_B3_LABEL_SEP: "Colonoscopy:", "Colonoscopy -", "Biopsy taken:", "Colonoscopy with"), what follows it an
    entry ("Interventions: Photos ☒ | Biopsy ☐"). A label that ends right before the first mark may also be the row's
    first entry, whose box trails it ("Biopsy: ☐", "Biopsy | ☐ | Cold snare polypectomy | ☒"): when both readings pair,
    marks alone in their cells trail their entries; a label naming a service, or naming no item, is the row's label
    ("Colonoscopy: ☐ biopsy ☒ cold snare", "Interventions: ☐ Biopsy ☒ Cold snare polypectomy"); a label naming an item
    pairs both ways and cannot be told ("Biopsy: ☐ Cold snare polypectomy ☒ hot snare", round 6 declared:8). With no
    separator, a row of yes/no answers answers the text before them ("Biopsy taken ☐ Yes ☒ No"). A reading that leaves
    the unread mark the last mark before an entry pairs it both ways ('ambiguous': "Biopsy: [?] Cold snare
    polypectomy", round 6 declared:1), and so does the row."""
    text = an.text
    first = marks[0][0]

    def read(label_end: int) -> Optional[tuple]:
        found = _B3_pairing(an, lo, hi, marks, label_end, options)
        return (label_end,) + found if isinstance(found, tuple) else found

    if _B3_word_run(text, lo, first) is None:
        found = read(lo)
        return found if isinstance(found, tuple) else None
    separators = list(_B3_LABEL_SEP.finditer(text, lo, first))
    if not separators:
        answered = read(first)
        if isinstance(answered, tuple) and answered[1] == 'lead' and all(
                _B3_YES_NO.fullmatch(text, *run) for run, _ in answered[2]):
            return answered
        found = read(lo)
        return found if isinstance(found, tuple) else None
    cut = _BOX_RUN_GAP.match(text, separators[-1].end(), first).end()
    if _B3_word_run(text, cut, first):  # the label, then the row's first entry
        found = read(cut)
        return found if isinstance(found, tuple) else None
    as_label, as_entry = read(cut), read(lo)
    if 'ambiguous' in (as_label, as_entry):
        return None
    if as_label is None or as_entry is None:
        return as_label or as_entry
    if all(_B3_CELL_BEFORE.search(text, max(lo, s - 20), s) and _B3_CELL_AFTER.match(text, e, hi) for s, e, _ in marks):
        return as_entry
    if an.services_in(lo, cut) or not _box_tokens(an, lo, cut)[0]:
        return as_label
    return None


def _B3_agrees(an: Analysis, lo: int, hi: int, label_end: int, pairs: list, marks: list) -> bool:
    """Whether every reader of the row [lo, hi) reads each item and each status option after its label by the mark it
    pairs with (``pairs``; an entry no mark governs, a remark, gives None; the unread mark reads 'unknown'), wherever
    a reader's reading could release or exclude: the box reader (_box_state) for every item ('unclear', BOX_LATER's
    hold, agrees with an unchecked or unread mark; a checked box and none agree, as both leave the item to its own
    words; no box agrees for an item among an option's own words, which the option readers read: "☐ Repeat colonoscopy
    in 5 years"); the status-line reader of each option's line window (_B2_status_line: its denying options
    exactly, its completion options and listed items where it reads one checked that is not); and the option readers
    over the row and over that window (_box_option_states, as _box_own_option_off, _box_checked_option, _unchecked_option
    and _boxed_status_denies read a status line): exactly for a status reference or a "Not done" option, or on a row
    naming no item, else where they read a denying option unchecked or a completion checked that is not. A reading
    that can only hold is no disagreement ("Procedure status: Completed ☒ Not done ☐" reads Completed unchecked)."""
    text = an.text
    starts = [run[0] for run, _ in pairs]

    def paired(start: int, end: int) -> Optional[str]:
        index = bisect.bisect_right(starts, start) - 1
        if index < 0 or max(end, start + 1) > pairs[index][0][1]:
            return 'outside'
        mark = pairs[index][1]
        if mark is None:
            return None
        state = marks[mark][2]
        return 'unknown' if state == 'unread' else state

    denying = _merged([o for o in _box_denying_options(an, lo, hi) if o[0] >= label_end])
    worded = [m.span() for m in _BOX_DONE_OPTION.finditer(text, label_end, hi)
              if not any(_overlaps(*m.span(), s, e) for s, e in denying)]
    in_options = [(run, any(_overlaps(*run, s, e) for s, e in denying + worded)) for run, _ in pairs]
    # a completion word is an option only beside a mark: a remark's prose ("... polyp was performed.") is none
    done = [o for o in worded if _box_beside_a_mark(text, *o, lo, hi)]
    items = [item for item in _box_tokens(an, lo, hi)[0] if item[0] >= label_end]
    if _B2_VISITS_KEY not in an.memo:
        an.memo[_B2_VISITS_KEY] = sorted((v.start, v.end) for v in an.em if v.kind == 'em-visit')
    all_visits = an.memo[_B2_VISITS_KEY]
    visits = [v for v in all_visits[bisect.bisect_left(all_visits, (label_end, -1)):bisect.bisect_left(all_visits, (hi, -1))]
              if v[1] <= hi]
    for start, end in visits:  # the visit statement's own reader (_B2_visit_box): option by option among statements
        _, _, vlo, vhi = _box_segment(an, start, end)
        others = [v for v in all_visits[bisect.bisect_left(all_visits, (vlo, -1)):bisect.bisect_left(all_visits, (vhi + 1, -1))]
                  if v[1] <= vhi and v != (start, end)]
        read = (_box_option_states(an, vlo, vhi, [(start, end)], _merged(others + [(start, end)] + list(
            _box_tokens(an, vlo, vhi)[0])))[0] if others else _box_state(an, start, end))
        wanted = paired(start, end)
        if read != wanted and not (read in (None, 'on') and wanted in (None, 'on')):
            return False
    for start, end in items:
        wanted, read = paired(start, end), _box_state(an, start, end)
        if read == wanted or (read == 'unclear' and wanted in ('off', 'unknown')):
            continue
        if read in (None, 'on') and wanted in (None, 'on'):
            continue  # a checked box and none both leave the item to its own words (_box_reading reads neither)
        if read is None and any(run[0] <= start and end <= run[1] and option for run, option in in_options):
            continue  # an option's own words ("☐ Repeat colonoscopy in 5 years"): the option readers read them
        return False
    if not denying and not done:
        return True
    exact = [(m.start(), m.end()) for _, pattern in _REFERENCE_PATTERNS for m in pattern.finditer(text, label_end, hi)]
    exact += [m.span() for m in _BOX_NOT_DONE_OPTION.finditer(text, label_end, hi)]

    def conflicts(completion: bool, read: Optional[str], wanted: Optional[str], strict: bool) -> bool:
        if read == wanted:
            return False
        if completion:
            return read == 'on'  # a completion read checked where its own mark is not: a release
        return strict or read == 'off'  # a denying option read unchecked where its own mark is not: a release

    options = _merged(denying + done)
    for (start, end), read in zip(options, _box_option_states(an, lo, hi, options, options)):
        strict = not items or any(_overlaps(start, end, s, e) for s, e in exact)
        if conflicts((start, end) in done, read, paired(start, end), strict):
            return False
    for start, end in options:
        wanted, completion = paired(start, end), (start, end) in done
        strict = not items or any(_overlaps(start, end, s, e) for s, e in exact)
        wlo, whi = _B2_line_window(an, start, end)
        words = _box_denying_options(an, wlo, whi) + [m.span() for m in _BOX_DONE_OPTION.finditer(text, wlo, whi)]
        if conflicts(completion, _box_option_states(an, wlo, whi, [(start, end)], words)[0], wanted, strict):
            return False
        line = _B2_status_line(an, wlo, whi)
        if line is None:
            continue
        entries = list(zip(line[1], line[2])) + list(zip(line[3], line[4]))
        if any(_overlaps(s, e, start, end) and conflicts(completion, state, wanted, True) for (s, e), state in entries):
            return False
        if any(label_end <= s and e <= hi and state == 'on' and paired(s, e) != 'on' for (s, e), state in line[8]):
            return False
    return True


def _B3_row(an: Analysis, start: int, end: int) -> Optional[tuple]:
    """The strict reading of the box row of the passage [start, end) (see above): None when the row holds no mark, or
    one mark that is not the unread mark; else (row start, row end, label end, readable, pairs, marks, whether a mark
    is unread, whether its entries are options, the hold's cue, whether the row is too long to pair, the end of a label
    no reading pairs with a mark). Memoised per row."""
    text = an.text
    line_lo, line_hi = _B3_line(an, start)
    seg_lo, seg_hi, _, _ = _box_segment(an, start, end)
    lo, hi = max(seg_lo, line_lo), min(seg_hi, line_hi)
    key = ('b3-row', lo, hi, bool(an.other_names))
    if key not in an.memo:
        result = None
        if hi > lo and (_BOX.search(text, lo, hi) or _BOX_UNREAD.search(text, lo, hi)
                        or _BOX_RADIO.search(text, lo, hi)):
            unpaired = (_B3_ROW_UNPAIRED if _B3_crowded(an, line_lo, line_hi)
                        else _B3_DOCUMENT_UNPAIRED if hi > _B3_document_cap(an) else None)
            result = _B3_row_read(an, lo, hi, unpaired)
        an.memo[key] = result
    return an.memo[key]


def _B3_document_cap(an: Analysis) -> int:
    """Where the document's mark past its first B3_DOCUMENT_MARKS starts (past the text when it has no more): a row
    ending after it has a mark there or later and is never paired. Found once per text by a search that stops at that
    mark, so the cap depends on the text alone, never on which rows were read first."""
    if _B3_DOCUMENT_CAP_KEY not in an.memo:
        cap = len(an.text) + 1
        for count, glyph in enumerate(_B3_MARK_GLYPH.finditer(an.text), 1):
            if count > B3_DOCUMENT_MARKS:
                cap = glyph.start()
                break
        an.memo[_B3_DOCUMENT_CAP_KEY] = cap
    return an.memo[_B3_DOCUMENT_CAP_KEY]


_B3_MARK_GLYPH = re.compile('(?:' + _BOX_TEXT + ')|' + _BOX_UNREAD.pattern + '|' + _BOX_RADIO.pattern)


def _B3_crowded(an: Analysis, line_lo: int, line_hi: int) -> bool:
    """Whether the line [line_lo, line_hi) carries more than B3_LINE_MARKS marks: counted once per line, up to the cap
    (a long one-line paste of rows is never paired row by row: each row's readers read windows across its
    neighbours, and pairing every one would cost a window read per option)."""
    key = ('b3-crowded', line_lo)
    if key not in an.memo:
        count = 0
        for _ in _B3_MARK_GLYPH.finditer(an.text, line_lo, line_hi):
            count += 1
            if count > B3_LINE_MARKS:
                break
        an.memo[key] = count > B3_LINE_MARKS
    return an.memo[key]


def _B3_row_read(an: Analysis, lo: int, hi: int, unpaired: Optional[str]) -> Optional[tuple]:
    text = an.text
    shown = ' '.join(text[lo:min(hi, lo + 640)].split())[:160]
    cue = _B3_ROW_HOLD.format(shown)
    if hi - lo > B3_ROW_CHARS:
        # Round 4d integration (BOXES3 verifier, new problem 7): one plain box is never paired, so a long row with one
        # keeps its reading as a short one does - counted with a search that stops at the second mark (linear); any
        # other mark, or more than one, is held with the cap's own cue, since the row was never paired at all.
        glyphs = []
        for glyph in _B3_MARK_GLYPH.finditer(text, lo, hi):
            glyphs.append(glyph)
            if len(glyphs) > 1:
                break
        if not glyphs or (len(glyphs) == 1 and _BOX.fullmatch(text, *glyphs[0].span())):
            return None
        return lo, hi, lo, False, (), (), True, False, _B3_ROW_UNPAIRED.format(shown), True, lo
    _, marks = _box_tokens(an, lo, hi)
    unread = any(state == 'unread' for _, _, state in marks)
    if not marks or (len(marks) == 1 and not unread):
        return None
    if unpaired is not None:  # its line carries more than B3_LINE_MARKS marks, or it has a mark past the document's
        # first B3_DOCUMENT_MARKS: never paired (bounded), held with the cue that says which
        return lo, hi, lo, False, (), tuple(marks), unread, False, unpaired.format(shown), True, lo
    # The row's option words: denying and completion words written beside a mark (as a hold word is an option only
    # there: _box_beside_a_mark), so a remark's prose ("... polyp was performed.") names none.
    options = [o for o in _box_denying_options(an, lo, hi) + [m.span() for m in _BOX_DONE_OPTION.finditer(text, lo, hi)]
               if _box_beside_a_mark(text, *o, lo, hi)]
    # A label no reading pairs with a mark: a service's name and a label separator followed by the row's first entry, on
    # a row of items ("Colonoscopy: Biopsy ☐ Cold snare polypectomy ☒ clip placed"; a service is described by its
    # interventions, never governed by their boxes: _box_trail_state); passages within it are not the row's to hold. An
    # item's label is read by its options ("Polypectomy: cold snare [?] hot snare", round 6 declared:1), so it is none.
    cut = _B3_label_end(text, lo, marks[0][0])
    free = (cut if cut > lo and _B3_word_run(text, cut, marks[0][0]) and not any(o[0] >= cut for o in options)
            and an.services_in(lo, cut) and not an.interventions_in(lo, cut) and not _other_names_in(an, lo, cut)
            else lo)
    reading = _B3_label_reading(an, lo, hi, marks, options)
    if reading is None:
        return lo, hi, lo, False, (), tuple(marks), unread, False, cue, False, free
    label_end, _, pairs = reading
    readable = _B3_agrees(an, lo, hi, label_end, pairs, marks)
    with_options = any(o[0] >= label_end for o in options) or any(_B3_YES_NO.fullmatch(text, *run) for run, _ in pairs)
    return lo, hi, label_end, readable, tuple(pairs), tuple(marks), unread, with_options, cue, False, free


def _B3_hold(an: Analysis, start: int, end: int) -> Optional[str]:
    """The hold's cue (_B3_ROW_HOLD) when the strict check-box rows hold the passage [start, end), else None: its row's
    marks cannot be paired with its entries in exactly one way, or are paired so but an unread mark may govern it (the
    passage opens in the label of a row of options, or runs across entries one of whose marks is unread). A passage
    that starts outside the row (prose after it on its line) is not the row's, nor one no mark is near: a box governs
    only what is within BOX_REACH of it on its line. Memoised per passage (apart before and after routing names the
    other procedures, as _box_tokens)."""
    key = ('b3-hold', start, end, bool(an.other_names))
    if key not in an.memo:
        an.memo[key] = _B3_hold_read(an, start, end)
    return an.memo[key]


def _B3_hold_read(an: Analysis, start: int, end: int) -> Optional[str]:
    text = an.text
    line_lo, line_hi = _B3_line(an, start)
    near_lo, near_hi = max(line_lo, start - BOX_REACH), min(line_hi, max(end, start + 1) + BOX_REACH)
    if not (_BOX.search(text, near_lo, near_hi) or _BOX_UNREAD.search(text, near_lo, near_hi)
            or _BOX_RADIO.search(text, near_lo, near_hi)):
        return None
    row = _B3_row(an, start, end)
    if row is None:
        return None
    lo, hi, label_end, readable, pairs, marks, unread, with_options, cue, _, free = row
    if not lo <= start < hi or max(end, start + 1) <= free:
        return None
    if not readable:
        return cue
    if unread:
        if start < label_end and with_options:
            return cue
        spanned = [mark for run, mark in pairs if run[0] < max(end, start + 1) and start < run[1]]
        if (len(spanned) > 1 or (spanned and start < label_end)) and any(
                mark is not None and marks[mark][2] == 'unread' for mark in spanned):
            return cue
    return None


def _B3_long_row(an: Analysis, start: int, end: int) -> bool:
    """Whether the passage's row is too long to pair (B3_ROW_CHARS): held without being read further."""
    row = _B3_row(an, start, end)
    return row is not None and row[9]


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
                    unpaired = _B3_hold(an, m.start(), m.end())
                    if unpaired is not None:  # round 4d BOXES3: its row's marks cannot be paired: held, never read
                        found[Mention(family, m.start(), m.end(), 'reference', m.group(0))] = Reading(
                            'uncertain', (unpaired,), 'cue', doubt=True)
                        continue
                    if context.cues == (UNCHECKED,):  # an unchecked status option ("Procedure cancelled | [ ]") ...
                        selected = _box_checked_option(an, m.start(), m.end())
                        if selected is not None:  # ... on a line that selects another denying option: held (routing:0)
                            found[Mention(family, m.start(), m.end(), 'reference', m.group(0))] = selected
                        continue  # ... is otherwise not a statement
                    if context.cues and context.cues[0].startswith(BOX_HOLDS):
                        found[Mention(family, m.start(), m.end(), 'reference', m.group(0))] = context
                        continue  # its box or form field cannot be read: held, never cancelled
                    if _box_own_option_off(an, m.start(), m.end()):  # "Completed ☒ Aborted ☐": its own box is off
                        selected = _box_checked_option(an, m.start(), m.end())
                        if selected is not None:  # ... on a line that selects another denying option: held
                            found[Mention(family, m.start(), m.end(), 'reference', m.group(0))] = selected
                        continue  # ... is otherwise not a statement (round 5 regression:4)
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


_INSERTED_AT = re.compile(r'\b(?:inserted|introduced|placed|passed)\b[^.;]{0,40}?\b(?:into|in|through|via)\s+(?:the\s+)?'
                          r'(?:rectum|anus|anal\s+canal|esophagus|oesophagus|mouth|oropharynx)\b'
                          r'|\bper\s+(?:rectum|anum|os)\b|\b(?:inserted|introduced)\s+(?:transorally|transanally|orally)\b',
                          re.A | re.I)


def _insertion_only(depth: int, span: Span, denials, labelled=()) -> bool:
    """The deepest landmark reached is the first one, read only from the instrument's insertion ("The colonoscope was
    inserted into the rectum and advanced under direct vision"), nothing denies or doubts a deeper reach, and no extent
    label names a landmark (``labelled``, read or not): the text states where the examination started, not how far it
    went. An extent label is the document's own statement of the extent, so beside one the label readings decide as
    before (round 4c-2 plan:B, B2, D, D2: an unread, shorter, denied or aimed label keeps the procedure incomplete)."""
    return depth == 1 and not denials and not labelled and bool(_INSERTED_AT.search(span.text))


def _colon_extent(an: Analysis, sentences) -> Optional[Fact]:
    unread, denied, doubted, cut, cut_denials, labelled = [], [], [], [], [], []
    reached, blocked = _landmarks(an, sentences, cues.LOWER_LANDMARKS, unread, denied, doubted, cut=cut,
                                  cut_denials=cut_denials, labelled=labelled)
    reached, withhold = _S2_cut_denied(an, reached, cut, cut_denials, cues.LOWER_LANDMARKS,  # round 4d regression:3
                                       cues.CECUM_DEPTH, sub_acts=True)
    if not reached or withhold:
        return None
    depth, label, span = max(reached, key=lambda hit: hit[0])
    if depth < cues.CECUM_DEPTH and _insertion_only(depth, span, blocked + denied + doubted, labelled):
        return None  # "inserted into the rectum and advanced": where the examination starts, never how far it went
    if depth < cues.CECUM_DEPTH:
        if _P2_unread_reaches(unread, cues.CECUM_DEPTH) and not _P2_denied_beyond(blocked + denied, depth):
            return None  # round 4c-2 plan:B: an unread label names the cecum or beyond
        withhold, short = _S2_doubted_short(doubted, blocked + denied, depth, cues.CECUM_DEPTH)
        if withhold:
            return None  # round 4c-2 plan:D2: a label refused for no reach denial lies at or beyond the cecum
        if short:
            depth, label, span = short[:3]  # round 4d sections:1: one short of the cecum keeps the procedure incomplete
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
    unread, denied, doubted, cut, cut_denials, labelled = [], [], [], [], [], []
    reached, blocked = _landmarks(an, sentences, cues.UPPER_LANDMARKS, unread, denied, doubted, cut=cut,
                                  cut_denials=cut_denials, labelled=labelled)
    reached, withhold = _S2_cut_denied(an, reached, cut, cut_denials, cues.UPPER_LANDMARKS,  # round 4d regression:3
                                       _expected_upper_depth(an))
    if not reached or withhold:
        return None
    depth, label, span = max(reached, key=lambda hit: hit[0])
    if depth < _expected_upper_depth(an) and not incomplete and _insertion_only(depth, span, blocked + denied + doubted,
                                                                                 labelled):
        return None  # "introduced into the esophagus": where the examination starts, never how far it went
    if depth < _expected_upper_depth(an) and _P2_unread_reaches(unread, _expected_upper_depth(an)) \
            and not _P2_denied_beyond(blocked + denied, depth):
        return None  # round 4c-2 plan:B: an unread label names the depth the procedure calls for
    if depth < _expected_upper_depth(an):
        withhold, short = _S2_doubted_short(doubted, blocked + denied, depth, _expected_upper_depth(an))
        if withhold:
            return None  # round 4c-2 plan:D2: a label refused for no reach denial lies at or beyond the depth called for
        if short:
            depth, label, span = short[:3]  # round 4d sections:1: one short of it keeps the procedure incomplete
    if incomplete or depth < _expected_upper_depth(an):
        evidence = [span] + [b[2] for b in blocked if b[0] > depth]
        return Fact('extent', f'incomplete: {label}', 'document', tuple(dict.fromkeys(evidence)))
    return Fact('extent', label, 'document', (span,))


def _flex_sig_extent(an: Analysis, sentences) -> Optional[Fact]:
    text = an.text
    found, refused = [], []
    for s, e in sentences:
        for cs, ce in _clauses_in(an, s, e):
            advanced = bool(cues.ADVANCED.search(text, cs, ce))
            hits = [m for m in cues.CENTIMETERS.finditer(text, cs, ce)
                    if advanced or _cm_after_flex_sig(an, cs, m.start())]
            # "Depth of insertion: 30 cm", never an aim ("Intended depth of insertion: 60 cm"); a label is also read
            # where it answers silently (_answers_silently: "Depth of insertion: 40 cm." in an addendum)
            leads = [m for m in cues.EXTENT_CM.finditer(text, cs, ce)
                     if _label_lead_plain(an, an.lay.window((cs, ce), m.start(), m.end(), CLAUSE_REACH)[0], m.start())]
            labels = [m for m in leads if not _P2_label_denied(an, m.end(), 0, cues.LOWER_LANDMARKS)]  # round 4c-2 plan:D
            for m in hits + leads:
                reading = _generic_reading(an, m.start(), m.end())
                if (reading.status in ('performed', 'incomplete')
                        or (m in leads and _answers_silently(an, reading, m.start(), m.end()))) \
                        and not _about_another_procedure(an, m.start(), m.end()):
                    if m in leads and m not in labels:  # refused by plan:D (round 4c-2 plan:D2)
                        refused.append((f"{int(m.group('cm'))} cm", _P2_reach_denied(an, m.end(), 0, cues.LOWER_LANDMARKS)))
                    else:
                        found.append((f"{int(m.group('cm'))} cm", _span(text, cs, ce)))
    # round 4c-2 plan:D2: beside a depth label plan:D refuses, no other value decides (the base held their conflict),
    # and with none, a landmark decides only after a reach denial
    if refused and (any(value != label for value, _ in found for label, _ in refused)
                    or (not found and not all(reach for _, reach in refused))):
        return None
    if found:
        return _fact('extent', found)
    denied, doubted, cut, cut_denials = [], [], [], []
    reached, blocked = _landmarks(an, sentences, cues.LOWER_LANDMARKS, None, denied, doubted, cut=cut,
                                  cut_denials=cut_denials)
    # round 4d regression:3: a flexible sigmoidoscopy calls for no depth, so a doubted label always withholds
    reached, withhold = _S2_cut_denied(an, reached, cut, cut_denials, cues.LOWER_LANDMARKS, 0)
    if not reached or withhold:
        return None
    depth, label, span = max(reached, key=lambda hit: hit[0])
    if _S2_doubted_short(doubted, blocked + denied, depth, 0)[0]:  # _P2_doubted_withholds, read in one sweep (round 4d)
        return None  # round 4c-2 plan:D2: a landmark label refused for no reach denial lies deeper
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
    found, seen = [], set()
    for span in interventions.evidence:
        for cs, ce in an.lay.clauses_for(span.start, span.end):
            if (cs, ce) in seen:  # a clause's locations are read once, however many of its interventions are listed
                continue  # (round 7 bounded:4: once per intervention, a listed clause cost interventions x locations)
            seen.add((cs, ce))
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
               away: tuple = (), held_statements: bool = False) -> str:
    """Performed on explicit evidence, or on section evidence that no reading about this encounter
    contradicts; else incomplete; else what the readings say of today's service: cancelled, negated,
    or uncertain when a doubt or a hedge about it (or section evidence that is contradicted or does
    not suffice) leaves it open. Only then what they say of other encounters (ELSEWHERE_ORDER):
    doubt never cascades into a plan, a history or a negation of earlier encounters ("no prior
    colonoscopy"). ``kinds``: each reading's section kind; ``away``: whether it speaks of another
    encounter (_elsewhere). Both default to "about this encounter, section unknown". ``held_statements``: a procedure
    family's aggregate, where an explicit performance statement its section held (_P2_held_statement) is today's
    possible service and so ranks before what the readings say of other encounters (round 4c-2 plan:E)."""
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
    if held_statements and any(_P2_held_statement(r) for r in readings):
        return 'uncertain'  # round 4c-2 plan:E: a held performance statement outranks another encounter's mention
    return next((s for s in ELSEWHERE_ORDER if s in statuses), 'uncertain')


def _P2_held_statement(reading: Reading) -> bool:
    """Whether ``reading`` is an explicit performance statement its section or another hold kept from reading performed
    (round 4c-2 plan:E): uncertain, with a 'performed:' cue ("EGD was performed with biopsies." under Assessment and
    plan), or with plan:A2's hedged-statement hold. 5.6 counts such a statement as a possible same-day procedure, so in a
    procedure family's aggregate it is what the mentions say of today."""
    return reading.status == 'uncertain' and any(cue.startswith('performed:') or cue == _P2_HEDGED_STATEMENT
                                                 for cue in reading.cues)


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
        reading = _default_reading(an, m.start, m.end)
    else:
        label = 'visit statement' if m.kind == 'em-visit' else m.label
        reading = Reading('performed', (cue.cues if cue else ()) + (f'performed: office E/M documentation ({label})',),
                          'cue')
    if m.kind == 'em-visit' and reading.status == 'performed':
        held = _B2_visit_box(an, m.start, m.end)  # round 4c-2 box2:J
        if held is not None:
            return held
    return reading


# --- round 4c-2 box2:J: an E/M visit statement governed by an unread mark or an unchecked box ----------------------
_B2_VISIT_UNREAD = 'uncertain: the visit statement is marked with a box this reader cannot read'
_B2_VISIT_UNCHECKED = 'uncertain: the visit statement is marked with an unchecked box, so it is not read as documented'
_B2_VISIT_DISAGREE = ('uncertain: the boxes that mark the visit statement disagree, or a later box on its line may '
                      'govern it')
_B2_VISITS_KEY = ('b2-visit-statements',)  # the visit statements, sorted (read per segment by bisection)


def _B2_visit_box(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """The hold of an E/M visit statement at [start, end) that a box governs (_box_state, as any passage is read:
    its own line or cell, before or after it, within BOX_REACH) when that box is unread, unchecked or disagreeing,
    or that a form line marks off (_unchecked_state); None when a checked box governs it, or none. The box reader's
    items are services, interventions and gi.other names, and a visit statement is none of them, so nothing read
    its box: "[?] Established patient office visit." read performed once the unread mark's "?" was no hedge (round
    4c extraction:8), and "☐ Established patient office visit." at every tree. Each statement is read by its own box,
    so in an option row ("Visit type: ☐ New patient visit ☒ Established patient visit") the unchecked option of
    another visit type never holds the checked one; as a status line's label it is read by the line's options
    (_B2_label_state). Held, never negated: an unchecked visit statement is no statement that the visit did not
    happen. A checked hold word of its status line holds it (box2:L), and so does a row its boxes can be read for both
    ways (box2:K). Round 4d BOXES3: so does a row the strict check-box rows hold (_B3_hold), where the reading below
    does not already hold it."""
    unpaired = _B3_hold(an, start, end)
    held = _B3_visit_box_as_declared(an, start, end)
    if unpaired is None or held is not None:
        return held
    return Reading('uncertain', (unpaired,), 'cue', doubt=True)


def _B3_visit_box_as_declared(an: Analysis, start: int, end: int) -> Optional[Reading]:
    """The declared box contract's hold of an E/M visit statement (_B2_visit_box, before round 4d's strict rows)."""
    hold = _B2_label_hold(an, start, end)
    if hold:
        return Reading('uncertain', (hold,), 'cue', doubt=True)
    _, _, lo, hi = _box_segment(an, start, end)
    if _B2_VISITS_KEY not in an.memo:
        an.memo[_B2_VISITS_KEY] = sorted((v.start, v.end) for v in an.em if v.kind == 'em-visit')
    visits = an.memo[_B2_VISITS_KEY]
    others = [v for v in visits[bisect.bisect_left(visits, (lo, -1)):bisect.bisect_left(visits, (hi + 1, -1))]
              if v[1] <= hi and v != (start, end)]
    if others:  # an option row of visit statements: every statement an entry, each read by its own box
        entries = _merged(others + [(start, end)] + list(_box_tokens(an, lo, hi)[0]))
        state = _box_option_states(an, lo, hi, [(start, end)], entries)[0]
    else:
        state = _box_state(an, start, end)
        if _B2_runs_disagree(an, start, end, state, item=False):
            return Reading('uncertain', (_B2_ROW_READINGS,), 'cue', doubt=True)
    if state == 'off':
        label = _B2_label_state(an, start, end)
        if label == 'on':
            return None  # "Established patient office visit: ☐ Cancelled ☒ Completed"
        return Reading('uncertain', (_B2_VISIT_UNREAD if label in ('unknown', 'across') else _B2_VISIT_UNCHECKED,),
                       'cue', doubt=True)
    if state == 'unknown':
        return Reading('uncertain', (_B2_VISIT_UNREAD,), 'cue', doubt=True)
    if state in ('mixed', 'unclear'):
        return Reading('uncertain', (_B2_VISIT_DISAGREE,), 'cue', doubt=True)
    if state is None and _unchecked_state(an, start, end):
        return Reading('uncertain', (_B2_VISIT_UNCHECKED,), 'cue', doubt=True)
    return None


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


# The marks that keep a separately identifiable E/M statement from attesting unless each is a checked box: any box, an
# unread mark, a bare radio glyph or cross, an answer in parentheses (the shared vocabulary).
_BOX_CROSS = re.compile(_BOX_SYMBOLS.BOX_CROSS_PATTERN)
_BOX_ANY_MARK = ('(?:' + _BOX_TEXT + ')|' + _BOX_UNREAD.pattern + '|' + _BOX_RADIO.pattern + '|'
                 + _BOX_PAREN_ANSWER.pattern + '|' + _BOX_CROSS.pattern)
# A line that answers a statement: an optional short label, then only marks and answer words ("☐ Yes ☒ No", "No",
# "Answer: No", "☒", "Attested: ☐"; never "☐ Follow-up colonoscopy in 3 years" or "Plan: Follow up in 2 weeks.").
_BOX_ANSWER_LINE = re.compile(r"[ \t]*(?:(?P<label>[A-Za-z][\w /'-]{0,30}):[ \t]*)?(?:(?:" + _BOX_ANY_MARK
                              + r"|(?:yes|no|y|n|none|n/a|done|not[ \t]+done)\b)[ \t]*)+\.?[ \t]*", re.I)
_BOX_BARE_YES = re.compile(r"[ \t]*(?:[A-Za-z][\w /'-]{0,30}:[ \t]*)?(?:yes|y)\.?[ \t]*", re.I)
_BOX_OPTION_WORD = re.compile(r'\b' + _OPTION_WORDS + r'\b', re.A | re.I)
# A line under the statement made of one mark and a short label of its own, before or after it ("☐ Attested",
# "Attested ☐", "Attested | ☐", "☐ Yes, I attest"; round 5 declared:4): the statement's own box, unless its label
# answers for something else (_box_answers_its_own_label).
_BOX_LABELLED_MARK = re.compile(r"[ \t]*(?:(?:" + _BOX_ANY_MARK + r")[ \t]*(?:[|:][ \t]*)?(?P<after>[A-Za-z][\w /',.&-]{0,40}?)"
                                r"|(?P<before>[A-Za-z][\w /',.&-]{0,40}?)[ \t]*(?:[|:][ \t]*)?(?:" + _BOX_ANY_MARK + r"))[ \t.]*",
                                re.I)
_BOX_LONE_MARKS = re.compile(r'[ \t]*(?:(?:' + _BOX_ANY_MARK + r')[ \t]*)+')
BOX_ANSWER_LINE_CHARS = 120  # a line longer than this answers no statement (bounds the work)


def _box_attestation_refused(an: Analysis, start: int, end: int, rest_end: int) -> bool:
    """Whether a box, a mark, an answer or a form field keeps the separately identifiable E/M statement at [start, end)
    (the rest of its line runs to ``rest_end``) from attesting. Fail-closed, so only ever a refusal (a hold):
    - a box that governs it is not checked (off, disagreeing, unread, or one a later box may govern), or its line is a
      form line whose value is off (contract:5);
    - any mark on its line, before or after it, is not a checked box: an unchecked box, an unread mark, a bare radio
      glyph or cross, an answer in parentheses ("☐ ...", "... [ ]", "[N] ...", "○ ...", "(N) ...": structure:10);
    - the line under it answers it with anything but yes (a checked "Yes", a lone checked box, a bare "Yes"), or it
      asks (it ends with a colon) and no such answer follows; a lone box line right above it is not checked
      (routing:11, contract:0's next-line layout); the line above it (one blank line may stand between) is about the
      attestation and refuses it as the line under would (_B3_attestation_above_refuses: round 4d BOXES3, round 6
      declared:10);
    - its page's form block has a field line naming it that is not checked, or a denying or answering line that names
      nothing printed: an attestation box whose glyph extraction could not place ("Separate E/M attestation: not
      checked", "Check Box 7: not checked": contract:0, release:5, routing:11)."""
    text = an.text
    if _box_state(an, start, end) not in (None, 'on') or _unchecked_state(an, start, end):
        return True
    newline = text.rfind('\n', max(0, start - BOX_REACH), start)
    line_start = newline + 1 if newline >= 0 or start <= BOX_REACH else None
    if _box_marks_refuse(an, max(line_start or 0, start - BOX_REACH), min(rest_end, end + BOX_REACH)):
        return True
    answer = _box_line_after(text, rest_end)
    reply = _BOX_ANSWER_LINE.fullmatch(text, *answer) if answer is not None else None
    if reply is not None and reply.group('label') and _box_answers_its_own_label(an, *reply.span('label')):
        reply = None  # "Complications: None": a field answering its own label, not the statement (declared:12)
    if reply is not None:
        if not _box_answer_affirms(an, *answer):
            return True
    elif answer is not None and _box_own_box_refuses(an, *answer):
        return True  # "☐ Attested": the statement's own box, on the line under it, is not checked (declared:4)
    elif answer is not None and _B2_attestation_line_refuses(an, *answer):
        return True  # "Notes: Not attested", "Notes: Attested": an answer about the attestation that refuses (box2:F)
    elif not text[end:rest_end].strip() and text[start:end].rstrip().endswith(':'):
        return True  # it asks, and nothing under it answers yes
    above = _box_line_before(text, line_start) if line_start else None
    if above is not None and _BOX_LONE_MARKS.fullmatch(text, *above) and not _box_answer_affirms(an, *above):
        return True
    if line_start and _B3_attestation_above_refuses(an, line_start):
        return True  # round 6 declared:10: "☐ Separate E/M attestation:" on the line above it
    fields = _form_fields(an)
    named = _within(fields.named, fields.named_starts, start, end) if text.find('\n', start, end) < 0 else None
    if named is not None and named.state != 'on':
        return True
    if answer is not None:  # a field tied to the printed line under it that is not checked: the statement's box
        index = bisect.bisect_left(fields.named_starts, answer[0])
        under = fields.named[index] if index < len(fields.named) else None
        if (under is not None and under.start < answer[1] and under.state != 'on'
                and not _box_answers_its_own_label(an, under.start, under.end)):
            return True  # (declared:4: a PDF's unchecked box beside its printed label "Attested")
    index = bisect.bisect_right(fields.untied_starts, start) - 1
    return index >= 0 and start < fields.untied[index].end


# The attestation's own words, as a line above the statement may carry them (_B3_attestation_above_refuses): narrower
# than _BOX_ATTEST_WORD, whose "significant", "identifiable" and "E/M" are the statement's own words and open many
# lines about something else ("Significant findings: none", "E/M: established patient, no new problems").
_B3_ATTEST_ABOVE = re.compile(r'\b(?:(?:un|non-?|dis)?(?:attest|agree|confirm|acknowledg)\w*|separate\w*|modifier)\b',
                              re.A | re.I)
B3_ABOVE_ANSWER_WORDS = 4  # a field's value read as an answer above the statement: at most this many words
# A line above with no mark is asked only when it names the attestation itself (round 4d integration, BOXES3 verifier's
# new problem 2): an attestation word, modifier 25, or "separate(ly)" about the E/M - never a bare agree, confirm or
# acknowledge, which ordinary lines carry ("Allergies confirmed: none.", "Consent: patient agrees.", "Diagnosis not
# confirmed."). A line with a mark is still asked by any of _B3_ATTEST_ABOVE's words.
_B3_ATTEST_NAME = re.compile(r'\b(?:un|non-?|dis)?attest\w*|\bmodifier\W{0,3}25\b'
                             r'|\bseparate\w*[ \t,]+(?:\w+[ \t,]+){0,3}?(?:E\s*/\s*M\b|E&M\b|evaluation\b|identifiable\b'
                             r'|service\b|visit\b|encounter\b)',
                             re.A | re.I)
# The attestation itself denied, at any length: "I do not attest ...", "cannot confirm", "declined to attest" (and the
# words negated in themselves, as _B2_DENIED, defined further down, reads them).
_B3_ATTEST_DENIED = re.compile(r"(?:\b(?:not|never|cannot)\b|n't\b|\b(?:decline[sd]?|refuse[sd]?|unable)\s+to\b)"
                               r"[ \t\w]{0,20}?\b(?:attest|agree|confirm|acknowledg)\w*"
                               r"|\b(?:un|non-?|dis)(?:attest|agree|confirm|acknowledg)\w*", re.A | re.I)


def _B3_attestation_above_refuses(an: Analysis, line_start: int) -> bool:
    """Whether the line above the separately identifiable E/M statement's line (starting at ``line_start``; one blank
    line may stand between, as under it) is about the attestation and refuses it (round 6 declared:10: only a lone box
    line above was read, so "☐ Separate E/M attestation:", "☐ Attested", "Attested: ☐", "[ ] Attested" or "Attested |
    [ ]" right above the statement left it attesting, 99214 ready). Only a line with one of the attestation's own words
    (_B3_ATTEST_ABOVE) is asked, and only in the shapes of an answer, since a line above the statement is as often the
    end of what comes before it ("☐ Labs reviewed", "Attestation: I saw the patient and agree with the resident's
    note."):
    - a line with a mark: refused unless its marks affirm (_box_answer_affirms: checked boxes alone, a checked Yes) and
      box2:F does not refuse it ("☐ Attested", "Attested | [ ]", "Notes: ☐ Attested", "☒ Not attested");
    - a field line whose value is at most B3_ABOVE_ANSWER_WORDS words: read by box2:F (_B2_attestation_line_refuses),
      as under the statement ("Separate E/M attested: No", "Attestation: pending", "E/M attestation: Not attested",
      "Notes: Not attested", "Attestation: Agree" refuse; "Attested - Yes", "Attested by: Dr. Smith", "Modifier: 25" do
      not; the first two were held at d05326ef and ready since 4347acd); a longer value is prose ("Attestation: I saw
      the patient and agree with the resident's note.");
    - a line that denies the attestation itself, at any length (_B3_ATTEST_DENIED: "Attestation: I do not attest to a
      separate service today.", "cannot confirm", "Unattested");
    - a line of at most B3_ABOVE_ANSWER_WORDS words with no field that holds a word the statement's own line would
      refuse (_B2_contrary: "Not attested", "Modifier 25 not appended");
    - a form field tied to that printed line, not checked ("Attested" printed above, its PDF box unchecked).
    Only refuses (a hold)."""
    text = an.text
    above = _box_line_before(text, line_start)
    if above is None and line_start >= 2 and text[line_start - 2] == '\n':
        above = _box_line_before(text, line_start - 1)  # one blank line between
    if above is None:
        return False
    start, end = above
    if not _B3_ATTEST_ABOVE.search(text, start, end):
        return False
    if _B2_MARK.search(text, start, end):
        return _B2_attestation_line_refuses(an, start, end) or not _box_answer_affirms(an, start, end)
    if not _B3_ATTEST_NAME.search(text, start, end):
        return False  # round 4d integration (BOXES3 verifier, new problem 2): "Allergies confirmed: none." is not it
    if _B3_ATTEST_DENIED.search(text, start, end):
        return True  # "Attestation: I do not attest to a separate service today."
    field = _B2_FIELD.match(text, start, end)
    if (field is not None and _B3_words(text, field.end(), end, B3_ABOVE_ANSWER_WORDS) <= B3_ABOVE_ANSWER_WORDS
            and _B2_attestation_line_refuses(an, start, end)):
        return True
    if field is None and _B3_words(text, start, end, B3_ABOVE_ANSWER_WORDS) <= B3_ABOVE_ANSWER_WORDS and _B2_contrary(
            text, start, end):
        return True  # a short line that refuses it: "Not attested", "Unattested", "Modifier 25 not appended"
    fields = _form_fields(an)
    index = bisect.bisect_left(fields.named_starts, start)
    tied = fields.named[index] if index < len(fields.named) else None
    return tied is not None and tied.start < end and tied.state != 'on'


def _box_answers_its_own_label(an: Analysis, start: int, end: int) -> bool:
    """Whether the label [start, end) of a line under the statement answers for something other than the statement:
    it names an item (a service, an intervention or a procedure's word: "Biopsy: No", "☐ Follow-up colonoscopy in 3
    years") or is a field known to answer its own question (_BOX_OWN_FIELD_LABEL: "Complications: None", "Sedation
    given: No"), and carries no attestation word (_BOX_ATTEST_WORD). Any other label is read as the statement's
    answer: fail-closed (round 5 declared:12, declared:4)."""
    if _BOX_ATTEST_WORD.search(an.text, start, end):
        return False
    if an.services_in(start, end) or an.interventions_in(start, end) or _PROCEDURE_WORD.search(an.text, start, end):
        return True
    return bool(_BOX_OWN_FIELD_LABEL.fullmatch(_label_key(an.text[start:end])))


def _box_own_box_refuses(an: Analysis, start: int, end: int) -> bool:
    """Whether the line [start, end) under the statement is its own box, with a short label, and that box is not
    checked (_BOX_LABELLED_MARK, _box_marks_refuse; round 5 declared:4)."""
    mark = _BOX_LABELLED_MARK.fullmatch(an.text, start, end)
    if mark is None:
        return False
    label = 'after' if mark.group('after') is not None else 'before'
    return not _box_answers_its_own_label(an, *mark.span(label)) and _box_marks_refuse(an, start, end)


def _box_marks_refuse(an: Analysis, lo: int, hi: int) -> bool:
    """Whether [lo, hi) holds a mark that is not a checked box (see _box_attestation_refused)."""
    text = an.text
    if any(b.group('off') is not None for b in _BOX.finditer(text, lo, hi)):
        return True
    if any(not _BOX.fullmatch(text, *u.span()) for u in _BOX_UNREAD.finditer(text, lo, hi)):
        return True
    return bool(_BOX_RADIO.search(text, lo, hi) or _BOX_PAREN_ANSWER.search(text, lo, hi)
                or _BOX_CROSS.search(text, lo, hi))


def _box_answer_affirms(an: Analysis, start: int, end: int) -> bool:
    """Whether the answer line [start, end) says yes: a bare "Yes" ("Answer: Yes", "Y"), checked boxes alone, or a
    yes/no pair whose "Yes" is checked and whose "No" is not. An unread mark, a radio glyph, a cross or an answer in
    parentheses says nothing this reader can read: no."""
    text = an.text
    if (any(not _BOX.fullmatch(text, *u.span()) for u in _BOX_UNREAD.finditer(text, start, end))
            or _BOX_RADIO.search(text, start, end) or _BOX_PAREN_ANSWER.search(text, start, end)
            or _BOX_CROSS.search(text, start, end)):
        return False
    boxes = [(b.start(), b.end(), 'off' if b.group('off') is not None else 'on')
             for b in _BOX.finditer(text, start, end)]
    if not boxes:
        return bool(_BOX_BARE_YES.fullmatch(text, start, end))
    if not _BOX_OPTION_WORD.search(text, start, end):
        return all(state == 'on' for _, _, state in boxes)
    return _group_state(text, boxes) == 'on'


# --- round 4c-2 box2:F: a refusal in the line under the separately identifiable E/M statement ---------------------------
# A field line under the statement: a list marker, a short label and the shared separator (_BOX_Q_LEAD, _BOX_Q_SEP: one
# grammar with the status lines), except that a word's own hyphen ("Same-day", "Follow-up") separates nothing.
_B2_FIELD = re.compile(_BOX_Q_LEAD + r"(?P<label>[A-Za-z][\w /'-]{0,30}?)(?!(?<=[A-Za-z0-9])[-\u2013\u2014][A-Za-z0-9])"
                       + _BOX_Q_SEP + r"(?=\S)", re.I)  # a value follows: "Attested?" alone is no field
_B2_MARK = re.compile(_BOX_ANY_MARK)
# An attestation word negated in itself ("Unattested", "Disagree", "Unconfirmed"): an attestation word and a word the
# statement's own line would refuse at once.
_B2_DENIED = re.compile(r'\b(?:un|non-?|dis)(?:attest|agree|confirm|acknowledg)\w*', re.A | re.I)


def _B2_attestation_line_refuses(an: Analysis, start: int, end: int) -> bool:
    """Whether the line [start, end) under the separately identifiable E/M statement refuses it as an answer about the
    attestation (box2:F). Only lines that carry an attestation word (_BOX_ATTEST_WORD) are asked, and only to refuse:
    - one that carries a word the statement's own line would refuse (_SEPARATE_EM_CONTRARY: "Not attested", "Notes: E/M
      not separately identifiable", "☒ Not attested", "Attestation: pending") refuses, read the way the rest of the
      statement's own line is; the separator of a field line is no part of it (a label's own "?" is no hedge);
    - a field line or a marked line whose value carries the attestation word ("Notes: Attested", "Notes: Agree", "Notes: ☐
      Attested") is the statement's answer whatever its label, and refuses unless it affirms as an answer may: checked
      boxes alone or a checked Yes (_box_answer_affirms).
    Prose with no contrary word ("Modifier 25 appended.", "Patient agrees with the plan.") and a field whose label alone
    names the attestation ("Attested - Yes", "E/M level: 99214") are left as they were."""
    text = an.text
    if not (_BOX_ATTEST_WORD.search(text, start, end) or _B2_DENIED.search(text, start, end)):
        return False
    field = _B2_FIELD.match(text, start, end)
    if field is None:
        if _B2_contrary(text, start, end):
            return True
        if not _B2_MARK.search(text, start, end):
            return False
        value = start
    else:
        value = field.end()
        if _B2_contrary(text, *field.span('label')) or _B2_contrary(text, value, end):
            return True
    return bool(_BOX_ATTEST_WORD.search(text, value, end)) and not _box_answer_affirms(an, start, end)


def _B2_contrary(text: str, start: int, end: int) -> bool:
    """Whether [start, end) holds a word the statement's own line would refuse (_SEPARATE_EM_CONTRARY), not counting a
    denial option that labels a box ("☒ Yes ☐ No": _OPTION_LABEL, an option that explains itself), or an attestation
    word negated in itself (_B2_DENIED)."""
    if _B2_DENIED.search(text, start, end):
        return True
    options = [m.span() for m in _OPTION_LABEL.finditer(text, start, end)]
    return any(not any(s <= c.start() and c.end() <= e for s, e in options)
               for c in _SEPARATE_EM_CONTRARY.finditer(text, start, end))


def _box_line_after(text: str, pos: int) -> Optional[tuple[int, int]]:
    """The next non-blank line after the line break at ``pos`` (one blank line may stand between), if it is short."""
    for _ in range(2):
        if pos >= len(text):
            return None
        start = pos + 1
        stop = text.find('\n', start, start + BOX_ANSWER_LINE_CHARS + 1)
        if stop < 0:
            stop = len(text) if len(text) - start <= BOX_ANSWER_LINE_CHARS else -1
        if stop < 0:
            return None
        if text[start:stop].strip():
            return start, stop
        pos = stop
    return None


def _box_line_before(text: str, line_start: int) -> Optional[tuple[int, int]]:
    """The line right above the one starting at ``line_start``, if it is short."""
    if line_start <= 0:
        return None
    start = text.rfind('\n', max(0, line_start - 1 - BOX_ANSWER_LINE_CHARS), line_start - 1) + 1
    if start == 0 and line_start - 1 > BOX_ANSWER_LINE_CHARS:
        return None
    return (start, line_start - 1) if text[start:line_start - 1].strip() else None


# Encounters and settings a statement may name after its "separately identifiable" words (routing:11). Fail-closed:
# one that its own words do not make this encounter is another one.
_BOX_ENCOUNTER = re.compile(r"\b(?:visits?|encounters?|consult(?:ation)?s?|appointments?|admissions?|"
                            r"hospitali[sz]ations?|stays?|emergency\s+(?:department|room)|(?-i:ED|ER)|urgent\s+care|"
                            r"inpatient|hospital|pre-?op(?:erative)?|pre-?procedur(?:e|al)|referrals?|tele-?health|"
                            r"televisits?)\b", re.I)
_BOX_THIS_ENCOUNTER = re.compile(r"\b(?:this|today'?s?|current|same|present)\b", re.I)
_BOX_EM_NOUN = re.compile(r'\b(?:E/?M|E&M|evaluation\s+and\s+management)\s+$', re.I)
_BOX_TODAY_AFTER = re.compile(r'\s+today\b', re.I)


def _box_names_another_encounter(an: Analysis, pos: int, rest_end: int) -> bool:
    """Whether the statement, after its "separately identifiable" words ending at ``pos`` (to the end of its line,
    within SEPARATE_EM_REACH), names an encounter or a setting that is not this encounter: "at the preoperative
    visit", "during the hospital admission", "in the emergency department", "at the referral consultation", "at the
    visit" (routing:11). One is this encounter only when "this", "today's", "current", "same" or "present" stands
    within the three words before it, or "today" right after it ("at today's visit", "during this encounter", "during
    the same visit as the procedure", "the visit today"); the E/M service itself ("E/M visit") is no encounter."""
    text = an.text
    hi = min(rest_end, pos + SEPARATE_EM_REACH)
    for m in _BOX_ENCOUNTER.finditer(text, pos, hi):
        if _BOX_EM_NOUN.search(text, max(pos, m.start() - 40), m.start()):
            continue
        words = text[max(pos, m.start() - 60):m.start()].split()[-3:]
        if _BOX_THIS_ENCOUNTER.search(' '.join(words)) or _BOX_TODAY_AFTER.match(text, m.end(), hi):
            continue
        return True
    return False


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
        # An unchecked attestation is no statement: fail-closed on any box, mark, answer or form field that does not
        # check it (contract:5, contract:0, release:5, routing:11: _box_attestation_refused), and on another encounter
        # it names (routing:11: _box_names_another_encounter). Both only refuse: the E/M stays held.
        if _box_attestation_refused(an, start, end, rest_end) \
                or _box_names_another_encounter(an, match.end(), rest_end):
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
    instrument of one ("the colonoscope", "fine-needle"), or one of their interventions ("polypectomy"). An intervention
    written in a procedure, findings or technique section is a detected family's only when that family is named
    somewhere other than a history or plan section (_VAL_named_beyond_history: "Procedure: EGD ... Band ligation of
    three columns was performed."): a family named only in the history or the plan ("History of present illness: EGD
    in 2020 was normal.", "Plan: EGD next month.") does not take an office note's "Procedure: Anoscopy with rubber band
    ligation ... was performed today." (round 5 regression:5). An intervention stated as performed today
    (_V2_stated_today), in any section, is a detected family's only when that family is named for today
    (_V2_named_for_today): outside the history and the plan, by a mention not read as another encounter's (round 4d
    validation:7: "Assessment: Anoscopy with rubber band ligation ... was performed today." beside an EGD named only in
    the HPI; validation:11: "Chief complaint: rectal bleeding; EGD 2020 normal."). Any other intervention outside a
    procedure, findings or technique section is read as before ("rubber band ligation was done in 2021" stays the
    historical EGD's)."""
    if an.services_in(start, end):
        return True
    if any(p.search(an.text, start, end) for family, p in cues.INSTRUMENTS if family in detected):
        return True
    named = _VAL_named_beyond_history(an)
    for iv in an.interventions_in(start, end):
        families = [family for family in iv.families if family in detected]
        if not families:
            continue
        if _V2_stated_today(an, iv.start, iv.end):
            if any(family in _V2_named_for_today(an) for family in families):
                return True
            # round 4d repair 2: in its own report, the procedure line naming the family as booked is that report's
            # procedure ("Procedure: EGD (rescheduled from last week)" over "Findings: ... Band ligation of three
            # columns was performed today."), unless the statement names another procedure of its own ("Anoscopy with
            # rubber band ligation ...")
            if (an.lay.section_at(iv.start).kind in POSITIVE_SECTIONS
                    and not _V2_names_another_procedure(an, start, end)
                    and _V2_booked_report_line(an, iv.start, families)):
                return True
        elif an.lay.section_at(iv.start).kind not in POSITIVE_SECTIONS or any(family in named for family in families):
            return True
    return False


_V2_STATED_REACH = 60  # how far an intervention's own performance cue may stand from it (bounds the work per cue)


def _V2_stated_today(an: Analysis, start: int, end: int) -> bool:
    """Whether the intervention at [start, end) is stated as performed today (round 4d validation:7): its clause says
    today (cues.TODAY) and holds an explicit performance cue (PERFORMED_CLAUSE) within _V2_STATED_REACH of it with no
    other procedure word or service between them ("... rubber band ligation of two internal hemorrhoids was performed
    today.", never another procedure's "was performed" earlier in a list). Both are read within twice that reach of
    the intervention, inside its clause (bounds the work per intervention: a clause may be a whole pasted line)."""
    cs, ce = _clause_at(an, start)
    lo, hi = max(cs, start - 2 * _V2_STATED_REACH), min(ce, end + 2 * _V2_STATED_REACH)
    if not cues.TODAY.search(an.text, lo, hi):
        return False
    for cue in an.cues_in(lo, hi):
        if cue.status != 'performed':
            continue
        lo, hi = (end, cue.start) if cue.start >= end else (cue.end, start)
        if hi - lo <= _V2_STATED_REACH and not _PROCEDURE_WORD.search(an.text, lo, max(lo, hi)) \
                and not an.services_in(lo, max(lo, hi)):
            return True
    return False


_VAL_ELSEWHERE_KINDS = ('history', 'plan')  # sections that tell a service of another encounter (round 5 regression:5)


def _VAL_named_beyond_history(an: Analysis) -> frozenset:
    """The families named, by a service name or an instrument, in a section that is not a history or a plan section
    (_VAL_ELSEWHERE_KINDS): those whose interventions an unnamed procedure may be. Read once per text: one pass over
    the service mentions and one search per instrument pattern."""
    key = ('val-named-beyond-history',)
    if key not in an.memo:
        found = {m.family for m in an.services if an.lay.section_at(m.start).kind not in _VAL_ELSEWHERE_KINDS}
        for family, pattern in cues.INSTRUMENTS:
            if family not in found and any(an.lay.section_at(m.start()).kind not in _VAL_ELSEWHERE_KINDS
                                           for m in pattern.finditer(an.text)):
                found.add(family)
        an.memo[key] = frozenset(found)
    return an.memo[key]


def _V2_named_for_today(an: Analysis) -> frozenset:
    """The families named for today: as _VAL_named_beyond_history, by a mention not itself read as another
    encounter's - planned, historical, cancelled or negated (round 4d validation:11: "Chief complaint: rectal bleeding;
    EGD 2020 normal." names no EGD of today). Read once per text: a reading per mention until its family is found.
    Those readings are taken before the other procedures' names are known (an.other_names, which box readings
    consult), so they are read in a copy of the memo and never kept. Bounded: at most _V2_NAMED_READS readings per
    family and per instrument pattern; a family whose first ones all read another encounter's counts as named, as in
    _VAL_named_beyond_history (no new procedure is read from a text that long)."""
    key = ('v2-named-for-today',)
    if key not in an.memo:
        named = _VAL_named_beyond_history(an)
        found: set = set()
        reads: dict = {}
        kept = an.memo
        an.memo = dict(kept)
        try:
            candidates = [(m.family, m.start, m.end) for m in an.services]
            candidates += [(family, m.start(), m.end()) for family, pattern in cues.INSTRUMENTS
                           for m in pattern.finditer(an.text)]
            for family, start, end in candidates:
                if family in found or family not in named or an.lay.section_at(start).kind in _VAL_ELSEWHERE_KINDS:
                    continue
                reads[family] = reads.get(family, 0) + 1
                if reads[family] > _V2_NAMED_READS or _generic_reading(an, start, end).status not in NOT_TODAY:
                    found.add(family)
        finally:
            an.memo = kept
        an.memo[key] = frozenset(found)
    return an.memo[key]


_V2_NAMED_READS = 50  # mentions of one family read for today's naming (bounds the work per text)


# The readings of a report's own procedure line that still make it that report's procedure: as booked, called off or
# denied, never another encounter's (historical)
_V2_BOOKED = tuple(status for status in NOT_TODAY if status != 'historical')
# A procedure line whose label the layout reads as no heading: a procedure heading's label (sections.HEADINGS) after an
# optional bar or list marker, then a dash, an equals sign, a bar, "?:", a tab or two spaces ("Procedure - EGD
# (rescheduled from last week)", "| Procedure | EGD |", "Procedure?: EGD"). Every run is bounded (no backtracking over
# a long blank run).
_V2_LABEL_LINE = re.compile(r'^[ \t]{0,8}(?:\|[ \t]{0,4})?'
                            r'(?:(?:[-*\u2022]|\d{1,2}[.)]|\(\d{1,2}\)|[A-Za-z][.)])[ \t]{1,4})?'
                            r'(?P<label>[A-Za-z][A-Za-z /]{0,58}?)[ \t]{0,4}'
                            r'(?:\?:|[-\u2013\u2014=|]|\t|[ ]{2,8})[ \t]{0,8}(?=\S)', re.A | re.M)


def _V2_booked_report_line(an: Analysis, at: int, families: list[str]) -> bool:
    """Whether the procedure line of the report that the intervention at ``at`` lies in - the first sentence of the
    last procedure section with a line of its own, or the last line labelled as a procedure outside a history or plan
    section (_V2_LABEL_LINE), opening before it - names one of ``families`` read as the report's own procedure though
    not as performed (_V2_BOOKED): as booked ("Procedure: EGD (rescheduled from last week)", "Procedure - Planned EGD
    with banding", "Procedure: EGD, previously scheduled"), called off or denied ("Procedure: EGD (postponed from last
    week)", "Procedure: EGD was cancelled."). That report's own findings' band ligation is that procedure's, as the
    base read it, never a new gi.other procedure (round 4d repair 2, the verifier's new problem 6: the validation:7
    rule made it one); a line naming the family as another encounter's ("Procedure: EGD in 2020 was normal.") books
    nothing (validation:11). A procedure line opening between the line and the intervention is another report. Read
    once per text, in a copy of the memo as _V2_named_for_today reads; bounded: one pass of _V2_LABEL_LINE and at most
    _V2_NAMED_READS readings, beyond which every line counts as booked (as the base read them)."""
    key = ('v2-booked-lines',)
    if key not in an.memo:
        starts: list = []
        booked: list = []
        kept = an.memo
        an.memo = dict(kept)
        reads = 0
        lines: list = []  # (where the report opens, its line's start, its line's end)
        for section in an.lay.sections:
            if section.kind != 'procedure':
                continue
            first = _SEPARATOR.match(an.text, section.heading.end if section.heading else section.start,
                                     section.end).end()
            index = _sentence_index(an, first)
            if index >= 0 and an.lay.section_at(first) is section:  # a heading with no line of its own opens none
                lines.append((section.start, *an.lay.sentences[index]))
        for m in _V2_LABEL_LINE.finditer(an.text):
            if (gi_sections.HEADINGS.get(gi_sections.normalize_label(m.group('label'))) == 'procedure'
                    and an.lay.section_at(m.start()).kind not in _VAL_ELSEWHERE_KINDS):
                end = an.text.find('\n', m.end())
                lines.append((m.start(), m.end(), len(an.text) if end < 0 else end))
        try:
            for opens, s, e in sorted(lines):
                found = set()
                for m in an.services_in(s, e):
                    reads += 1
                    if reads > _V2_NAMED_READS or _generic_reading(an, m.start, m.end).status in _V2_BOOKED:
                        found.add(m.family)
                starts.append(opens)
                booked.append(frozenset(found))
        finally:
            an.memo = kept
        an.memo[key] = (starts, booked)
    starts, booked = an.memo[key]
    index = bisect.bisect_right(starts, at) - 1
    return index >= 0 and any(family in booked[index] for family in families)


# A procedure word that names a procedure ("Anoscopy", "Hemorrhoidectomy", "Paracentesis", "Manometry"), never an act
# done within one ("Sclerotherapy and band ligation of three columns were performed today."), nor the bare word for an
# endoscopy, which names no procedure but the report's own ("Under endoscopy, band ligation ... was performed today.")
_V2_PROCEDURE_NAME = re.compile(r'\w+(?:scop(?:y|ies)|ectom(?:y|ies)|otom(?:y|ies)|ostom(?:y|ies)|plast(?:y|ies)|'
                                r'centesis|pex(?:y|ies)|rrhaph(?:y|ies))|manometry', re.A | re.I)
_V2_OWN_ENDOSCOPY = re.compile(r'endoscop(?:y|ies)', re.A | re.I)


def _V2_names_another_procedure(an: Analysis, start: int, end: int) -> bool:
    """Whether [start, end) names a procedure of its own beside its interventions ("Anoscopy with rubber band ligation
    of two internal hemorrhoids was performed today."): a procedure word naming a procedure (_V2_PROCEDURE_NAME) outside
    every intervention there."""
    interventions = an.interventions_in(start, end)
    return any(_V2_PROCEDURE_NAME.fullmatch(m.group()) and not _V2_OWN_ENDOSCOPY.fullmatch(m.group())
               and not any(_overlaps(m.start(), m.end(), iv.start, iv.end) for iv in interventions)
               for m in _PROCEDURE_WORD.finditer(an.text, start, end))


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
    readings, so a planned or denied procedure reads planned or negated. A procedure coordinated with such a word in
    one name ("Office visit and anoscopy were performed today") is read alone and held (round 4c-2 box2:E:
    _B2_coordinated_parts, _B2_held)."""
    text, found = an.text, {}
    plain, coordinated = set(), set()  # round 4c-2 box2:E: the names read whole, and the parts read from a name

    def consider(span, clause, form='', whole=None):
        """``form``: 'act' (a stated act: its participle is the procedure's word) or 'label' (a findings label), the
        routing:22 forms, whose mentions carry it as their value (see _other_finding). ``whole``: the name a part was
        read from (box2:E), None for a name read whole."""
        if span is None:
            return
        s, e = span
        name = text[s:e]
        act = form == 'act' and (whole is None or _B2_ACT.search(name) is not None)  # the part that holds the act
        if (not act and not _PROCEDURE_WORD.search(name)) or _NOT_DONE_LED.match(name):
            return
        if _NOT_A_PROCEDURE.search(name):
            if whole is None:  # box2:E: each procedure coordinated with the visit or another non-procedure is held
                for ps, pe in _B2_coordinated_parts(name):
                    consider((s + ps, s + pe), clause, form, span)
            return
        scope = (max(clause[0], s - CLAUSE_REACH), min(clause[1], e + CLAUSE_REACH))
        if _about_a_detected_family(an, *scope, detected) or _lower_tract_banding(an, s, e, detected):
            return
        if form and _in_a_detected_procedures_text(an, s, e, detected):
            return
        found[(s, e)] = Mention(OTHER_FAMILY, s, e, 'service', name, form)
        (plain if whole is None else coordinated).add((s, e))

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
    an.memo[_B2_COORDINATED_KEY] = frozenset(coordinated - plain)
    return sorted(found.values(), key=lambda mention: mention.start)


# --- round 4c-2 box2:E: a procedure coordinated with the visit or another non-procedure in one name --------------------
# What coordinates two parts of one name, in _CONNECTOR's own words (each match is a _CONNECTOR match): a connector word
# between spaces, an article after it ("Office visit and anoscopy", "Physical exam and the banding"), or "&", "+" or "/"
# between spaces. A bare "&", "+" or "/" coordinates only where it touches a non-procedure word ("Office visit/anoscopy";
# never "E/M" or "I&D"). A name never holds a comma: _SUBJECT_BREAK and _NP_END end it there.
_B2_PART_BREAK = re.compile(r'\s+(?:(?:and/or|and|or|nor|plus|then|followed\s+by|as\s+well\s+as)'
                            r'(?:\s+(?:the|a|an|her|his|their))?|[&+/])\s+', re.A | re.I)
_B2_BARE_BREAK = re.compile(r'[&+/]', re.A)
# The participle of a stated act (routing:22), which opens a "we banded ..." name and closes a "... were banded" one: of a
# coordinated act's parts, only the one that holds it is the act.
_B2_ACT = re.compile(r'\b' + _ACT_PARTICIPLE + r'\b', re.A | re.I)
_B2_COORDINATED = ('uncertain: the procedure is named together with a visit, an examination or another service that is '
                   'not a procedure, so it is not read as performed')
_B2_COORDINATED_KEY = ('b2-coordinated',)  # an.memo: the (start, end) of each part read only from a coordinated name


def _B2_coordinated_parts(name: str) -> list[tuple[int, int]]:
    """The parts of a name _NOT_A_PROCEDURE refuses ("Office visit and anoscopy", "Physical exam and banding"), as
    offsets into ``name``: split where _B2_PART_BREAK, or a bare "&", "+" or "/" touching a non-procedure word,
    coordinates them, never inside a procedure's word ("Office visit and I & D"), each part trimmed of _NAME_LEAD and
    _HISTORY_LEAD as _procedure_name trims a whole name ("and prior anoscopy" reads "anoscopy", after its history word).
    [] when nothing coordinates two parts. Read on the name alone, as the whole-name tests read it."""
    words = [m.span() for m in _PROCEDURE_WORD.finditer(name)]
    refused = [m.span() for m in _NOT_A_PROCEDURE.finditer(name)]
    breaks = [b.span() for b in _B2_PART_BREAK.finditer(name)]
    breaks += [b.span() for b in _B2_BARE_BREAK.finditer(name) if any(e == b.start() or s == b.end() for s, e in refused)]
    parts, at = [], 0
    for start, end in sorted(breaks):
        if start >= at and not any(s < end and start < e for s, e in words):
            parts.append((at, start))
            at = end
    parts.append((at, len(name)))
    trimmed = []
    for start, end in parts:
        start = _NAME_LEAD.match(name, start, end).end()
        lead = _HISTORY_LEAD.match(name, start, end)
        span = _trimmed_span(name, lead.end() if lead else start, end)
        if span:
            trimmed.append(span)
    return trimmed if len(trimmed) > 1 else []


def _B2_held(an: Analysis, reading: Reading, m: Mention) -> Reading:
    """A part read only from a coordinated name (box2:E): uncertain with _B2_COORDINATED first, its own cues after it
    (without silence), never performed; every other mention's reading as it is."""
    if (m.start, m.end) not in an.memo.get(_B2_COORDINATED_KEY, ()):
        return reading
    return Reading('uncertain', (_B2_COORDINATED,) + tuple(c for c in reading.cues if c != SILENT), 'cue',
                   doubt=reading.doubt)


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
    raw = [_B2_held(an, _stated(_generic_reading(an, m.start, m.end), m), m) for m in others]
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
    # round 4c-2 box2:E: a part read from a coordinated name is no item of a box line, and one that reads planned,
    # historical, cancelled or negated documents nothing, as before (the plain name reads that way alone)
    parts = an.memo[_B2_COORDINATED_KEY]
    an.other_names = tuple((m.start, m.end) for m in others if (m.start, m.end) not in parts)
    if parts:
        others = [m for m in others if (m.start, m.end) not in parts
                  or _generic_reading(an, m.start, m.end).status not in NOT_TODAY]
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
        status = _aggregate(family_readings, section_suffices=evidenced or not has_basis, kinds=kinds, away=away,
                            held_statements=True)  # round 4c-2 plan:E
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


def denying_label_over(text: str, pos: int, service_date: Optional[date] = None) -> Optional[str]:
    """The label that denies performance over the list the line at ``pos`` belongs to ("Procedures not performed:",
    "Cancelled procedures:", "[ ] Not done:"), read exactly as routing reads it (_denying_label_above: LABEL_ITEMS lines
    back in the same section, stopping at a blank line or at another label line); None when there is none. For the
    documented-service reader (gi/services), so that both readers hold the same listed lines (round 4c-2 plan:C)."""
    if not isinstance(text, str):
        raise TypeError('denying_label_over() needs the canonical text as str.')
    if not 0 <= pos < len(text):
        return None
    return _denying_label_above(_analysis(text, _checked_date(service_date, 'denying_label_over()'))[0], pos)


def own_box_checked(text: str, start: int, end: int, service_date: Optional[date] = None) -> bool:
    """Whether the item at [start, end) is governed by a checked box of its own in every reading of its row
    (_box_checked_in_every_reading: "(x) Cold snare polypectomy", "Biopsy: [x]"; never "Biopsy: \u2612 Cold snare
    polypectomy", whose box one reading gives the other item). For the documented-service reader (gi/services), which
    reads such an item, where routing finds its line silent, as the one marked option of its row (ARCHITECTURE 5.9)."""
    if not isinstance(text, str):
        raise TypeError('own_box_checked() needs the canonical text as str.')
    if not (0 <= start < end <= len(text)):
        return False
    return _box_checked_in_every_reading(_analysis(text, _checked_date(service_date, 'own_box_checked()'))[0], start,
                                         end)

def checked_field_ties(text: str, start: int, end: int, service_date: Optional[date] = None) -> tuple:
    """The printed lines or cells on its own page that the checked or "Yes" form-field line holding [start, end) names
    (routing's tie, _form_fields), as (start, end) pairs: () when that is no checked field line, when the lines of its
    label disagree, or when it names nothing printed on its page. For the documented-service reader (gi/services), which
    trusts such a field only through the printed list its item is in (the owner's strict-box decision, 2026-10-25)."""
    if not isinstance(text, str):
        raise TypeError('checked_field_ties() needs the canonical text as str.')
    if not (0 <= start < end <= len(text)):
        return ()
    fields = _form_fields(_analysis(text, _checked_date(service_date, 'checked_field_ties()'))[0])
    line = _within(fields.checked, fields.checked_starts, start, end)
    field = _FIELD_CHECKED.fullmatch(line.line) if line is not None else None
    if field is None:
        return ()
    headers = [h for h in FORM_HEADER.finditer(text) if h.start() < line.start]
    if not headers:
        return ()
    page_end = headers[-1].start()
    page_start = 0
    if len(headers) > 1:  # the page's printed text starts where the previous block ends (_form_fields)
        blank = _BLANK_LINE.search(text, headers[-2].end(), page_end)
        page_start = blank.start() if blank else page_end
    key = _label_key(field.group('label'))
    ties = []
    for named in fields.named:
        if named.state != 'on' or not page_start <= named.start < page_end:
            continue
        tied = _FIELD_CHECKED.fullmatch(named.line)
        if tied is not None and _label_key(tied.group('label')) == key:
            ties.append((named.start, named.end))
    return tuple(ties)


def own_status_for_span(text: str, start: int, end: int,
                        service_date: Optional[date] = None) -> tuple[str, tuple[str, ...]]:
    """status_for_span before the family's document-level judgement (_adjusted): what the passage's own clause,
    sentence and section say. For a code routing does not read the passage's family for (validation's gi.other
    hold, round 4c lead): "Procedure: Colonoscopy" reads incomplete when the colonoscopy stopped short, which says
    nothing of a hemorrhoid banding."""
    if not isinstance(text, str):
        raise TypeError('own_status_for_span() needs the canonical text as str.')
    if not (0 <= start < end <= len(text)):
        raise ValueError(f'span [{start}, {end}) is not a non-empty range inside the text (length {len(text)}).')
    reading = _read_span(_analysis(text, _checked_date(service_date, 'own_status_for_span()'))[0], start, end,
                         adjust=False)
    return reading.status, reading.cues
