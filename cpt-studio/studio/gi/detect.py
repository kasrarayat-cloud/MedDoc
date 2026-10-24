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


def _member_negations(an: Analysis, cs: int, ce: int, ms: int, me: int,
                      pre: Optional[str] = None, post: Optional[str] = None):
    """Anchored negations of the mention at [ms, me) in the window [cs, ce): a list of
    (label, about_past, text span), and the spans of pre-triggers that govern the word
    after the mention instead ("No flexible sigmoidoscopy complications")."""
    key = ('negations', cs, ce, ms, me)
    if key not in an.memo:
        pre = _masked(an, cs, ms) if pre is None else pre
        post = _masked(an, me, ce) if post is None else post
        found, governs_next = [], []
        for name, pattern in cues.NEGATED_PRE:
            m = pattern.search(pre)
            if not m:
                continue
            where = (_masked_map(an, cs, ms)[1][m.start()], ms)
            if cues.NEGATION_HEAD_AFTER.match(post):
                governs_next.append(where)
            else:
                past = name != cues.REFUSAL and bool(cues.NEGATION_ABOUT_PAST.search(m.group(0)))
                found.append((f'negated: {m.group(0).strip()}', past, where))
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


def _anchored_explains(an: Analysis, cs: int, ce: int, token: tuple[int, int]) -> bool:
    """Whether an anchored negation of a service or intervention named next to ``token`` (the
    two names after it, the one before it) covers it - "no colonoscopy", "EUS was not",
    "Neither EUS nor ERCP" - or is a pre-trigger that governs the word after its mention."""
    after = sorted({(m.start, m.end) for m in an.services_in(token[1], ce)}
                   | {(iv.start, iv.end) for iv in an.interventions_in(token[1], ce)})[:2]
    before = sorted({(m.start, m.end) for m in an.services_in(cs, token[0])}
                    | {(iv.start, iv.end) for iv in an.interventions_in(cs, token[0])})[-1:]
    for ms, me in after + before:
        found, governs_next = _member_negations(an, cs, ce, ms, me)
        if any(s <= token[0] and token[1] <= e for s, e in [where for _, _, where in found] + governs_next):
            return True
    return False


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
        for pattern in (cues.COMPLICATION_NEGATION, cues.QUALIFIER_NEGATION):
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
    # Inside a passage that names a service or an intervention, a denied finding or other act
    # is incidental to it ("Biopsies were taken where no ulcers were seen"); inside a passage
    # that names neither, it is what the passage says ("No polyps were seen.").
    named = bool(an.services_in(*target) or an.interventions_in(*target))
    outside = [w for w in outside_only if named or not _overlaps(*w, *target)]
    outside += [w for _, w in _memberless_negations(an, cs, ce) if not _overlaps(*w, *target)]
    return not _covered(token, outside) and not _anchored_explains(an, cs, ce, token)


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
    'measure', 'map', 'monitor', 'document'))
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
    if purpose and following in _TO_PURPOSE:
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
        return said + unit.group(0) if unit and previous not in _DETERMINERS else None
    if lowered == 'outside':
        place = _OUTSIDE_PLACE.match(text, word.end(), limit)
        return said + place.group(0) if place else None
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
                         r'[:=–—-][ \t]*', re.A | re.I)
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
    at = _SEPARATOR.match(text, ns, ne).end()
    opener = _OPENER.match(text, at, ne)
    body = opener.end() if opener else at
    key = _STATUS_KEY.match(text, body, ne)
    if key:
        value = key.end()
        if _STATUS_DONE.match(text, value, ne):
            return False
        return bool(_STATUS_HOLD.match(text, value, ne)) or _bare_denial(an, value, ne)
    if bare and _bare_denial(an, body, ne):
        return True
    if len(text[body:ne].split()) <= 6 and (_denying_word(an, body, ne, only=_ACT_DENIAL) or _cancels(an, body, ne)):
        return True
    if not _REFERRING_SUBJECT.match(text, body, ne):
        return False
    return _cancels(an, ns, ne) or bool(_denying_word(an, ns, ne))


def _later_denial(an: Analysis, after: int, s: int, e: int, bare: bool) -> Optional[str]:
    """The later clause of the sentence [s, e) (after ``after``, the end of the service's own clause),
    or else the next sentence of the same section, that denies the service named before it (see
    _denies); None when none does. A clause or a sentence that names a service speaks of that one."""
    for cs, ce in _clauses_in(an, after, e)[:DENIAL_CLAUSES]:
        if an.services_in(cs, ce):
            return None
        if _denies(an, cs, ce, bare=False):
            return an.text[cs:ce]
    index = _sentence_index(an, s)
    if index < 0 or index + 1 >= len(an.lay.sentences):
        return None
    ns, ne = an.lay.sentences[index + 1]
    if an.lay.section_at(ns) is not an.lay.section_at(s) or an.services_in(ns, ne):
        return None
    return an.text[ns:ne] if _denies(an, ns, ne, bare) else None


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


def _clause_reading_cues(an: Analysis, clause: tuple[int, int], ts: int, te: int) -> list[tuple[str, str, bool, bool]]:
    """(status, label, about_past, doubt) for every cue that governs the target in one clause."""
    text = an.text
    cs, ce = an.lay.window(clause, ts, te, CLAUSE_REACH)
    spans, index, members = _groups(an, cs, ce, ts, te)
    words = text[cs:ce]
    found = []
    for cue in an.cues_in(cs, ce):
        status, doubt = cue.status, False
        if cue.name == 'aborted':
            status, doubt = _abort_status(an, cue)
        if cue.name in ('terminated', 'stopped') and cues.MEDICATION.search(words):
            continue
        if _attached(spans, index, cue.start, cue.end):
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
        pre, post = _masked(an, cs, ms), _masked(an, me, ce)
        negations, _ = _member_negations(an, cs, ce, ms, me, pre, post)
        found += [('negated', label, past, False) for label, past, _ in negations]
        for status, entries in (('historical', cues.HISTORICAL_PRE), ('planned', cues.PLANNED_PRE),
                                ('incomplete', cues.INCOMPLETE_PRE), ('uncertain', cues.UNCERTAIN_PRE)):
            for name, pattern in entries:
                m = pattern.search(pre)
                if m:
                    found.append((status, f'{status}: {m.group(0).strip()}', False,
                                  'pending' in m.group(0).lower()))
        m = cues.HAD_PRE.search(pre)
        if m and not today:
            found.append(('historical', f'historical: {m.group(0).strip()}', False, False))
        for status, entries in (('incomplete', cues.INCOMPLETE_POST), ('uncertain', cues.UNCERTAIN_POST)):
            for name, pattern in entries:
                m = pattern.search(post)
                if m:
                    found.append((status, f'{status}: {_said(m)}', False, name == 'pending'))
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
    deciding = tuple(dict.fromkeys(f[1] for f in sorted((f for f in found if f[0] == status), key=lambda f: not f[3])))
    past = status == 'negated' and all(f[2] for f in found if f[0] == 'negated')
    doubt = status == 'uncertain' and any(f[3] for f in found if f[0] == 'uncertain')
    section = an.lay.section_at(start)
    if status == 'performed' and section.kind == 'history':
        today = any(cues.TODAY.search(an.text, cs, ce) for cs, ce in an.lay.clauses_for(start, end))
        return Reading('uncertain' if today else 'historical', deciding + (_section_label(section),), 'cue')
    if status == 'performed' and section.kind == 'plan':
        return Reading('uncertain', deciding + (_section_label(section),), 'cue')
    return Reading(status, deciding, 'cue', past, doubt)


EM_DOCUMENTATION = ': E/M documentation of this encounter'
SILENT = 'uncertain: no performance evidence in its sentence or section'  # validation reads this prefix as silence


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
        return Reading('performed', (label + EM_DOCUMENTATION,), 'section')
    return Reading('uncertain', (SILENT,), 'default')


# Checkbox glyphs as extraction writes them (Wingdings and form fields map to these) and their ASCII forms.
# The box nearest before an item on its line governs it: "☐ Biopsy ☒ Cold snare polypectomy".
_BOX = re.compile(r'(?P<off>\u2610|\u25a1|\[[ _]?\])|(?P<on>\u2611|\u2612|\u2713|\u2714|\u25a0|\[[xX\u2713\u2714]\])')
UNCHECKED = 'negated: an unchecked box'


BOX_REACH = 200  # a box governs only an item within this many characters after it (bounds the work per span)


def _unchecked_box(an: Analysis, start: int, end: int) -> bool:
    """Whether the item at [start, end) is governed by an unchecked box on its own line, within BOX_REACH."""
    reach = max(0, start - BOX_REACH)
    newline = an.text.rfind('\n', reach, start)
    line_start = newline + 1 if newline >= 0 else reach
    last = None
    for m in _BOX.finditer(an.text, line_start, max(end, start + 1)):
        last = m
    return last is not None and last.group('off') is not None


def _generic_reading(an: Analysis, start: int, end: int) -> Reading:
    """The reading of [start, end) from its clause cues or its section. A performed reading
    of a procedure (not of E/M documentation) becomes an uncertain doubt when an unresolved
    negation sits in its clause, or when only its section speaks for a named service whose
    words are not those of a procedure description ("Colonoscopy declined by patient")."""
    key = ('reading', start, end)
    if key not in an.memo and _unchecked_box(an, start, end):
        an.memo[key] = Reading('negated', (UNCHECKED,), 'cue')
    if key not in an.memo:
        reading = _cue_reading(an, start, end) or _default_reading(an, start, end)
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
                    context = _generic_reading(an, m.start(), m.end())
                    if context.status in ('historical', 'planned'):
                        continue
                    if family == 'gi.ercp' and 'cannulat' in m.group(0).lower() and _pancreatic_avoidance(an, m.start()):
                        continue
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
            if not cues.ADVANCED.search(text, cs, ce):
                continue
            for m in cues.CENTIMETERS.finditer(text, cs, ce):
                if _generic_reading(an, m.start(), m.end()).status in ('performed', 'incomplete') \
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
    service named only to compare with do not count."""
    key = ('another-procedure', start, end)
    if key not in an.memo:
        an.memo[key] = False
        for cs, ce in an.lay.clauses_for(start, end):
            if cues.TODAY.search(an.text, cs, ce):
                continue
            for svc in an.services_in(cs, ce):
                reading = _generic_reading(an, svc.start, svc.end)
                if not (_not_today(reading) and not reading.past_negation):
                    continue
                if _COMPARED_WITH.search(an.text, max(cs, svc.start - 60), svc.start):
                    continue
                an.memo[key] = True
                break
            if an.memo[key]:
                break
    return an.memo[key]


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
        for cs, ce in _clauses_in(an, s, e):
            for m in cues.INTENT.finditer(text, cs, ce):
                reading = _generic_reading(an, m.start(), m.end())
                if reading.status in skipped or reading.doubt \
                        or _INTENT_DENIED.search(text, max(cs, m.start() - 40), m.start()):
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
    technique section. Silence (no evidence at all) is never one: it is no doubt, and a positive
    section never reads silent."""
    return reading.status == 'uncertain' and (reading.doubt or kind in POSITIVE_SECTIONS)


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
# Anything in the statement's sentence (or the rest of its line) that denies, questions or
# hedges it: then it is not a statement that the service was provided.
_SEPARATE_EM_CONTRARY = re.compile(
    r"\b(?:no|not|none|never|neither|nor|without|cannot|nil|denied|declined|absent|lacking|unclear|uncertain|unknown|"
    r"whether|if|unless|may|might|could|would|should|possibl[ey]|questionabl[ey]|consider\w*|recommend\w*|pending|"
    r"question|answer)\b|n't\b|\?|(?<![\w/])n/?a(?![\w/])|(?:^|[\s(])[QA]\s*[:.)]", re.A | re.I)
# An affirmative predicate in the same sentence: "... was provided", "I performed ...", ": yes".
_SEPARATE_EM_AFFIRMED = re.compile(
    r'\b(?:was|were|is|are|has\s+been|have\s+been|had\s+been)\s+(?:also\s+|separately\s+)?(?:performed|provided|'
    r'documented|rendered|furnished|completed|delivered|conducted|carried\s+out)\b'
    r'|\b(?:I|we)\s+(?:also\s+|separately\s+)?(?:performed|provided|rendered|furnished|conducted)\b'
    r'|[:=-]\s*yes\b', re.A | re.I)
SEPARATE_EM_NOTE = 'The documentation states a significant, separately identifiable E/M service.'


def _separate_em_fact(an: Analysis) -> Optional[Fact]:
    """The clinician's explicit statement that a same-day E/M was significant and separately
    identifiable. Fail-closed over the whole sentence and the rest of its line: a denial, a
    question, a hedge, or the lack of an affirmative predicate means it is not documented.
    The evidence is the whole sentence, so a check quoting it cannot hide a trailing "not"."""
    text, spans = an.text, []
    for match in _SEPARATE_EM.finditer(text):
        if an.lay.section_at(match.start()).kind in ('plan', 'history'):
            continue
        start, end = an.lay.sentence_for(match.start(), match.end())
        line_end = text.find('\n', end)
        rest = text[end:len(text) if line_end < 0 else line_end]
        if _SEPARATE_EM_CONTRARY.search(text, start, end) or _SEPARATE_EM_CONTRARY.search(rest):
            continue
        if not _SEPARATE_EM_AFFIRMED.search(text, start, end):
            continue
        spans.append(_span(text, start, end))
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


def _mention(an: Analysis, m: Mention, reading: Reading) -> ServiceMention:
    s, e = an.lay.sentence_for(m.start, m.end)
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
