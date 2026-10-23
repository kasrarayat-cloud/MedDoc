"""Section, sentence and clause structure of a canonical clinical text.

A section starts at a heading line ("Findings", "Procedure: Colonoscopy",
"ASSESSMENT AND PLAN:") and runs to the next heading line; text before the
first heading is an ``other`` section with no heading. Every span is a
half-open range over the canonical text, so ``text[start:end]`` is exact.

Only labels in ``HEADINGS`` open a section. A key-value line such as
"Date of service: 2026-10-21" or "Extent: cecum" is content, not a heading.
"""
from __future__ import annotations

import bisect
import functools
import re
from dataclasses import dataclass
from typing import Optional

from studio.gi import cues
from studio.types import Span

SECTION_KINDS = ('procedure', 'findings', 'technique', 'impression', 'indication', 'history', 'plan', 'assessment',
                 'exam', 'mdm', 'time', 'other')


def _kind(kind: str, *labels: str) -> dict[str, str]:
    return {label: kind for label in labels}


HEADINGS: dict[str, str] = {
    **_kind('procedure', 'procedure', 'procedures', 'procedure performed', 'procedures performed',
            'procedure done', 'procedures done', 'name of procedure', 'procedure name', 'operation',
            'operation performed', 'operations performed', 'procedure note', 'procedure report', 'endoscopy report',
            'operative note', 'operative report', 'service performed', 'services performed'),
    **_kind('technique', 'technique', 'procedure technique', 'description of procedure', 'description of the procedure',
            'procedure description', 'procedure details', 'details of procedure', 'details of the procedure',
            'procedure in detail', 'procedure narrative', 'operative technique', 'description'),
    **_kind('findings', 'findings', 'endoscopic findings', 'procedure findings', 'egd findings', 'colonoscopy findings',
            'eus findings', 'ercp findings', 'sigmoidoscopy findings', 'upper endoscopy findings',
            'findings and interventions', 'specimens', 'specimen', 'specimens obtained', 'specimens collected'),
    **_kind('impression', 'impression', 'impressions', 'post-procedure impression', 'postprocedure impression',
            'post-procedure diagnosis', 'postprocedure diagnosis', 'post-procedure diagnoses', 'postoperative diagnosis',
            'post-operative diagnosis', 'final impression', 'endoscopic impression', 'summary', 'conclusion',
            'conclusions'),
    **_kind('indication', 'indication', 'indications', 'indication for procedure', 'indications for procedure',
            'indication for the procedure', 'reason for procedure', 'reason for exam', 'reason for examination',
            'reason for visit', 'reason for referral', 'referral reason', 'chief complaint', 'cc',
            'pre-procedure diagnosis', 'preprocedure diagnosis', 'preoperative diagnosis', 'pre-operative diagnosis'),
    **_kind('history', 'history', 'history of present illness', 'hpi', 'interval history', 'past medical history',
            'past surgical history', 'past medical/surgical history', 'past medical and surgical history', 'pmh',
            'psh', 'medical history', 'surgical history', 'family history', 'social history', 'past history',
            'prior procedures', 'prior endoscopy', 'previous endoscopy', 'endoscopic history', 'procedure history',
            'gi history', 'history and physical', 'pre-procedure history and physical'),
    **_kind('exam', 'examination', 'physical examination', 'physical exam', 'exam', 'pe', 'vital signs', 'vitals',
            'pre-procedure examination', 'pre-procedure physical examination'),
    **_kind('assessment', 'assessment', 'diagnosis', 'diagnoses', 'clinical impression', 'pre-procedure assessment'),
    **_kind('plan', 'plan', 'plans', 'recommendations', 'recommendation', 'plan of care', 'treatment plan',
            'follow-up', 'follow up', 'followup', 'assessment and plan', 'assessment/plan', 'a/p', 'a and p',
            'impression and plan', 'impression/plan', 'recommendations and plan', 'next steps', 'instructions',
            'discharge instructions', 'post-procedure instructions'),
    **_kind('mdm', 'medical decision making', 'medical decision-making', 'mdm', 'decision making'),
    **_kind('time', 'time', 'total time', 'time statement', 'time spent', 'visit time', 'time documentation'),
    **_kind('other', 'medications', 'current medications', 'medication', 'allergies', 'review of systems', 'ros',
            'sedation', 'anesthesia', 'consent', 'informed consent', 'complications', 'estimated blood loss', 'ebl',
            'disposition', 'signature', 'attestation', 'instrument', 'instruments', 'equipment', 'providers', 'staff',
            'bowel preparation', 'bowel prep', 'preparation', 'prep', 'quality of preparation'),
}

_PREFIX = re.compile(r'[ \t]*(?:#{1,4}[ \t]*|\*{1,2}[ \t]*|(?:\d{1,2}|[A-Za-z])[.)][ \t]+)?', re.A)
_CLOCK = re.compile(r'[ \t]*\d{1,2}:\d{2}', re.A)
_TITLE_QUALIFIER = re.compile(r'\b(?:prior|previous|last|planned|scheduled|next|outside|old)\b', re.A | re.I)
_ABBREVIATIONS = frozenset({'dr', 'mr', 'mrs', 'ms', 'st', 'vs', 'approx', 'e.g', 'i.e', 'eg', 'ie', 'fig', 'etc',
                            'pt', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec',
                            'a.m', 'p.m'})
_BIG = 1 << 62
# Clause boundaries inside a sentence; ", and the patient ..." starts a new subject.
_CLAUSE_WORD = re.compile(r'(?<=[\s,])(?:but|however|whereas|although|though|except)\b'
                          r'|(?<=,\s)and\s+(?=(?:the|she|he|they|we|i|it|this|there|patient)\b)', re.A | re.I)


@dataclass(frozen=True)
class Section:
    kind: str  # one of SECTION_KINDS
    label: str  # normalised heading label; '' for text before the first heading
    heading: Optional[Span]  # the heading text as written (label and colon)
    start: int  # heading line start (or 0)
    end: int  # next heading line start (or len(text))


def normalize_label(raw: str) -> str:
    label = raw.strip().strip('*').strip().lower().replace('&', ' and ')
    label = re.sub(r'\(s\)', 's', label)
    label = re.sub(r'\s+', ' ', label)
    return label.strip(' .:-')


def _service_named(line: str) -> bool:
    return bool(cues.FS_ABBREVIATION.search(line)) or any(p.search(line) for _, p in cues.SERVICE_PATTERNS)


def _heading(text: str, ls: int, le: int) -> Optional[tuple[str, str, Span]]:
    """(kind, label, heading span) when the line [ls, le) is a heading line."""
    body_start = _PREFIX.match(text, ls, le).end()
    line = text[body_start:le]
    colon = line.find(':')
    raw = line if colon < 0 else line[:colon]
    if not raw.strip() or len(raw) > 60:
        return None
    label = normalize_label(raw)
    kind = HEADINGS.get(label)
    content = '' if colon < 0 else line[colon + 1:]
    if kind is None and colon < 0 and cues.PROCEDURE_TITLE.match(line.strip()) and _service_named(line) \
            and not _TITLE_QUALIFIER.search(line):
        kind = 'procedure'
    if kind is None or (kind == 'time' and _CLOCK.match(content)):
        return None
    lead = len(raw) - len(raw.lstrip())
    h_start = body_start + lead
    h_end = body_start + (colon + 1 if colon >= 0 else len(raw.rstrip()))
    return kind, label, Span(h_start, h_end, text[h_start:h_end])


def _lines(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    while True:
        nl = text.find('\n', start)
        if nl < 0:
            spans.append((start, len(text)))
            return spans
        spans.append((start, nl))
        start = nl + 1


def _soft_wrap(text: str, prev: tuple[int, int], nxt: tuple[int, int]) -> bool:
    """A line break inside a sentence: the line has no closing punctuation and
    the next line continues in lower case."""
    before = text[prev[0]:prev[1]].rstrip()
    after = text[nxt[0]:nxt[1]].lstrip()
    return bool(before) and before[-1] not in '.!?:;' and bool(after) and after[0].islower()


_STOP = re.compile(r'[.!?](?=\s)')
_WORD_BEFORE = re.compile(r'([A-Za-z][A-Za-z.]{0,10})$')
_NEXT_CHAR = re.compile(r'\s*(\S)')


def _sentence_breaks(text: str, start: int, end: int) -> list[int]:
    """Positions inside one line where a sentence ends."""
    breaks = []
    for m in _STOP.finditer(text, start, end):
        q = m.start()
        if text[q] == '.':
            word = _WORD_BEFORE.search(text, max(start, q - 12), q)
            follow = _NEXT_CHAR.match(text, q + 1, end)
            if word and (word.group(1).lower() in _ABBREVIATIONS or len(word.group(1)) == 1):
                continue
            if follow and follow.group(1).islower():
                continue
        breaks.append(q + 1)
    return breaks


def _trimmed(text: str, start: int, end: int) -> Optional[tuple[int, int]]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


@dataclass(frozen=True)
class Layout:
    """Sections, sentences and clauses of one text, indexed once."""
    text: str
    sections: tuple[Section, ...]
    sentences: tuple[tuple[int, int], ...]
    clauses: tuple[tuple[int, int], ...]
    section_starts: tuple[int, ...]

    def section_at(self, pos: int) -> Section:
        index = bisect.bisect_right(self.section_starts, pos) - 1
        return self.sections[max(index, 0)]

    def sentence_for(self, start: int, end: int) -> tuple[int, int]:
        return _first_overlap(self.sentences, start, end)

    def window(self, clause: tuple[int, int], start: int, end: int, reach: int) -> tuple[int, int]:
        """The part of a clause within ``reach`` characters of [start, end), cut at
        whitespace so no word is split (a regex reads a cut as the end of the text)."""
        cs, ce = clause
        inner_lo, inner_hi = max(cs, start), min(ce, end)
        lo, hi = max(cs, start - reach), min(ce, end + reach)
        if lo > cs:
            space = re.search(r'\s', self.text[lo:inner_lo])
            lo = lo + space.end() if space else inner_lo
        if hi < ce:
            spaces = [m.start() for m in re.finditer(r'\s', self.text[inner_hi:hi])]
            hi = inner_hi + spaces[-1] if spaces else inner_hi
        return lo, hi

    def clauses_for(self, start: int, end: int) -> list[tuple[int, int]]:
        """Every clause that overlaps [start, end); the span itself when it overlaps none."""
        found = [c for c in _window(self.clauses, start, end) if c[0] < max(end, start + 1) and c[1] > start]
        return found or [_first_overlap(self.clauses, start, end)]


def _window(spans: tuple[tuple[int, int], ...], start: int, end: int) -> tuple[tuple[int, int], ...]:
    low = max(bisect.bisect_right(spans, (start, _BIG)) - 1, 0)
    high = bisect.bisect_left(spans, (end + 1, -1))
    return spans[low:high + 1]


def _first_overlap(spans: tuple[tuple[int, int], ...], start: int, end: int) -> tuple[int, int]:
    for span in _window(spans, start, end):
        if span[0] < max(end, start + 1) and span[1] > start:
            return span
    return (start, end)


def split_sections(text: str) -> tuple[Section, ...]:
    return layout(text).sections


@functools.lru_cache(maxsize=16)
def layout(text: str) -> Layout:
    lines = _lines(text)
    headings = {i: _heading(text, ls, le) for i, (ls, le) in enumerate(lines)}
    sections: list[Section] = []
    opened = [(i, h) for i, h in headings.items() if h]
    first = lines[opened[0][0]][0] if opened else len(text)
    if first > 0 or not opened:
        sections.append(Section('other', '', None, 0, first))
    for n, (i, (kind, label, span)) in enumerate(opened):
        end = lines[opened[n + 1][0]][0] if n + 1 < len(opened) else len(text)
        sections.append(Section(kind, label, span, lines[i][0], end))

    breaks: set[int] = set()
    for i, (ls, le) in enumerate(lines):
        breaks.update(_sentence_breaks(text, ls, le))
        if headings[i]:
            breaks.update((ls, headings[i][2].end, le))
        joined = i + 1 < len(lines) and not headings[i] and not headings[i + 1] \
            and _soft_wrap(text, (ls, le), lines[i + 1])
        if not joined:
            breaks.add(le)
    sentences = _segments(text, sorted(breaks | {0, len(text)}))
    clauses = []
    for s, e in sentences:
        cuts = {s, e}
        cuts.update(s + m.end() for m in re.finditer(';', text[s:e]))
        cuts.update(s + m.start() for m in _CLAUSE_WORD.finditer(text[s:e]))
        clauses.extend(_segments(text, sorted(cuts)))
    return Layout(text, tuple(sections), tuple(sentences), tuple(clauses), tuple(s.start for s in sections))


def _segments(text: str, cuts: list[int]) -> list[tuple[int, int]]:
    out = []
    for a, b in zip(cuts, cuts[1:]):
        span = _trimmed(text, a, b)
        if span:
            out.append(span)
    return out
