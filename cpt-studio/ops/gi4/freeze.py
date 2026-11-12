"""H2: the request-side freeze and differential between two trees. A request is the document's text plus, when one is
known, one "Date of service" line, so the date the request carries is the only interpretation it sends; this tool shows
that a change moves nothing on that side (or only what its package declared).

(a) the sha256 of every cue pattern context.py or sections.py reads (their module-level patterns and constants, and every
    cues.* and symbols.* name they reference), and sections.layout identity (sections, sentences, clauses) per text;
(b) the date channel per text and member state, classified NEW-SEND (a date the base did not send), NEW-TAKE (a member
    answer the base did not take), NEW-HELD (an answer the base did not hold) and SEND->ASK (the base sent the document's
    date, the head asks); the gate is NEW-SEND = NEW-TAKE = 0, always - but for the one owner-ruled movement below;
(c) the request sha256 for the primary (no member answer) and every dated request;
(d) the analyze stage's mention counts (detect.service_mention_count, services.mention_count).
Every other movement must be declared (``--declare FILE``: {"cues_added": [...], "movements": {"CLASS": max}}); with no
declaration the expected delta is NONE, and any movement fails.

The owner's decision of 2026-11-07 (the date forms; docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, "Owner
decision, 2026-11-07", interpretation (a)-(d) and (b') after the first refutation) is the one movement of the request
side a declaration may name (``"owner_ruling": {"id": "2026-11-07 date forms", "changed_cues": {name: head sha256},
...}``, _ruled_acceptor). Under it (i) exactly the named context.py and sections.py constants may change, each to the
sha256 the declaration pins; (ii) a NEW-SEND is accepted only text by text and state by state, where the base sent no
date for the text and the head's documented service date is quoted by its evidence in one of the decided forms -
checked here by this module's own patterns (ruled_forms), written from the ruling, never by the reader that changed;
(iii) NEW-HELD only where the held member answer contradicts that newly sent date, NEW-TAKE only where the taken answer
equals it, each only where the declaration names it (``new_held_forms``, ``new_take_forms``); SEND->ASK never; every
other class as before. No class of (b) is ever accepted by a count.

  python -m ops.gi4.freeze --base REF|DIR --head REF|DIR [--corpus FILE.jsonl ...] [--quick] [--declare FILE]
  python -m ops.gi4.freeze --tree DIR --cues --json-out FILE        (one tree's cue inventory; used by the above)
Each ref is exported with git archive into the scratch directory and read in a process of its own.
"""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import inspect
import json
import re
import sys
import types
from pathlib import Path

from ops.gi4 import boot, corpus as corpus_mod

DATE_CLASSES = ('NEW-SEND', 'NEW-TAKE', 'NEW-HELD', 'SEND->ASK')
OTHER_CLASSES = ('LAYOUT-CHANGED', 'FACT-CHANGED', 'REQUEST-CHANGED', 'MENTIONS-CHANGED', 'STATE-CHANGED',
                 'TEXT-MISSING', 'READER-ERROR')
GATE = ('NEW-SEND', 'NEW-TAKE')
RULED = ' (ruled)'  # the suffix of a movement class the owner's ruling accepted, text by text (_ruled_acceptor)


# --- (a) the cue inventory -------------------------------------------------------------------------------------------

def _canon(value, depth=0):
    """A JSON form of a constant (patterns with their flags), or None for what is no constant (functions, classes,
    modules, objects)."""
    if depth > 6:
        return ['deep']
    if isinstance(value, re.Pattern):
        return ['re', value.pattern if isinstance(value.pattern, str) else value.pattern.decode('latin-1'), value.flags]
    if isinstance(value, (bool, int, float, str)) or value is None:
        return ['v', value]
    if isinstance(value, bytes):
        return ['b', value.hex()]
    if isinstance(value, (tuple, list)):
        items = [_canon(v, depth + 1) for v in value]
        return None if any(i is None for i in items) else ['t', items]
    if isinstance(value, (set, frozenset)):
        items = [_canon(v, depth + 1) for v in value]
        return None if any(i is None for i in items) else ['s', sorted(json.dumps(i) for i in items)]
    if isinstance(value, dict):
        items = [[_canon(k, depth + 1), _canon(v, depth + 1)] for k, v in value.items()]
        return None if any(k is None or v is None for k, v in items) else ['d', sorted(json.dumps(i) for i in items)]
    if callable(value) and depth > 0:
        return ['fn', getattr(value, '__module__', ''), getattr(value, '__qualname__', repr(value))]
    return None


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def cue_inventory(modules=None) -> dict:
    """{name: sha256} of every constant context.py and sections.py read: their own module-level constants
    ('context.X', 'sections.X') and every cues.* / symbols.* attribute their source references ('cues.X', 'symbols.X')."""
    if modules is None:
        from studio.gi import context, cues, sections
        from studio.ingest import symbols
        modules = {'context': context, 'sections': sections, 'cues': cues, 'symbols': symbols}
    out = {}
    for prefix in ('context', 'sections'):
        mod = modules[prefix]
        for name, value in vars(mod).items():
            if name.startswith('__') or isinstance(value, (types.ModuleType, type)) or inspect.isroutine(value):
                continue
            c = _canon(value)
            if c is not None:
                out[f'{prefix}.{name}'] = _sha(c)
        aliases = {'cues': 'cues', '_BOX_SYMBOLS': 'symbols', 'symbols': 'symbols'}
        for node in ast.walk(ast.parse(inspect.getsource(mod))):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
                target = aliases[node.value.id]
                value = getattr(modules[target], node.attr, None)
                c = None if value is None else _canon(value)
                if c is None and value is not None and not inspect.isroutine(value):
                    c = ['repr', repr(value)]
                if c is not None:
                    out[f'{target}.{node.attr}'] = _sha(c)
    return dict(sorted(out.items()))


def compare_cues(base: dict, head: dict) -> dict:
    changed = sorted(k for k in base if k in head and base[k] != head[k])
    return {'changed': changed,
            'removed': sorted(k for k in base if k not in head),
            'added': sorted(k for k in head if k not in base), 'count': [len(base), len(head)],
            'head': {k: head[k] for k in changed}}  # what a changed constant is now (an owner ruling pins it)


# --- the owner's ruling of 2026-11-07: the date forms ----------------------------------------------------------------
# The decided forms, read by this module's own patterns, written from the ruling's words - never context.py's, so a
# reader that changed never certifies its own movement: under a date-of-service label (the closed list, "Date of
# service", "DOS", "Date of procedure", "Procedure date", "Service date", "Visit date", ...), (1) a weekday before a full
# date, naming the date's own weekday; (2) a day-first date with a month name and a four-digit year ("16-Nov-2026", "9
# November 2026"); and (3) one of the labels the ruling added - "Date of Operation", "Exam date", "Examination date" -
# only where the ruling reads them (the session's interpretation (b') after the first refutation): in the document's
# head, as the installed reader bounds it (_ruled_place: recomputed here from the installed, frozen sections module -
# never context.py, the reader that changed), never under a title of a note written around a procedure, and only where
# the label stands as a label (it opens its line or a field of its own: _R_LEAD, _R_BREAK, _r_opens_field). A two-digit
# year, an all-numeric date with hyphens or dots, a day-first numeric date, "Date:" alone, "Operation date",
# "Date/Time of Operation" and any other label are none of them, and neither is a label the ruling added anywhere else.
DATE_FORMS_RULING = '2026-11-07 date forms'
_R_TIME = r'(?:[ \t]*(?:/|&|and)[ \t]*time)?'
_R_MONTH = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?'
            r'|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)')
_R_NEW_LABEL = r'(?:date[ \t]+of[ \t]+operation|exam(?:ination)?[ \t]+date)'
_R_LABEL = (r'(?:date' + _R_TIME + r'[ \t]+of[ \t]+(?:service|procedure|visit|encounter)|DOS' + _R_TIME
            + r'|(?:service|procedure|visit|encounter)[ \t]+date' + _R_TIME + ')')
_R_WEEKDAY = (r'(?P<wd>monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|wed|thu(?:rs?)?|fri|sat'
              r'|sun)\.?,?[ \t]+')
_R_DATE = (r'(?P<iy>\d{4})-(?P<im>\d{2})-(?P<id>\d{2})|(?P<um>\d{1,2})/(?P<ud>\d{1,2})/(?P<uy>\d{4})'
           r'|(?P<lm>' + _R_MONTH + r')\.?[ \t]+(?P<ld>\d{1,2})(?:st|nd|rd|th)?,?[ \t]+(?P<ly>\d{4})'
           r'|(?P<dd>\d{1,2})(?:st|nd|rd|th)?(?:[ \t]+|-)(?P<dm>' + _R_MONTH + r')\.?(?:,?[ \t]+|-)(?P<dy>\d{4})')
_RULED_FORM = re.compile(r'(?<![\w/-])(?:(?P<new>' + _R_NEW_LABEL + r')|' + _R_LABEL + r')\b[ \t]*'
                         r'(?:\([ \t]*DOS[ \t]*\)[ \t]*)?[:#=\u2013|-]?[ \t]*(?:' + _R_WEEKDAY + r')?'
                         r'(?:(?P<date>' + _R_DATE + r')(?![\w/-]))?', re.I | re.A)
_R_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
_R_WEEKDAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
_R_HEAD_LINES = 12  # the head: at most a document's first 12 non-empty lines, as the installed reader bounds it
_R_LEAD = re.compile(r'[ \t]*[#*_>]*[ \t]*(?:(?:[-*\u2022]|\d{1,2}[.)])[ \t]+)?[*_]*\Z')  # a line's lead before a label
_R_BREAK = re.compile(r'(?:\t| {2}|\|)[ \t*_]*\Z')  # a field break before a label
_R_PREVIOUS_WORD = re.compile(r"(?<![A-Za-z'\u2019-])([A-Za-z][A-Za-z'\u2019-]*) \Z")
_R_NEW_LABEL_RX = re.compile(r'(?<![\w/-])' + _R_NEW_LABEL + r'\b', re.I | re.A)
STRICT_UNDER_RULING = ('NEW-SEND', 'NEW-TAKE', 'NEW-HELD', 'SEND->ASK')  # never declared by a count under the ruling


def _ruled_day(m: re.Match, weekday: bool = True):
    """The ISO date a _RULED_FORM match states, or None (no full date, no calendar date, or - unless ``weekday`` is
    False, the date as written with its weekday aside - a weekday naming another day than the date's own)."""
    import datetime as dt
    if not m.group('date'):
        return None
    if m.group('iy'):
        parts = (m.group('iy'), m.group('im'), m.group('id'))
    elif m.group('uy'):
        parts = (m.group('uy'), m.group('um'), m.group('ud'))
    elif m.group('ly'):
        parts = (m.group('ly'), _R_MONTHS.index(m.group('lm')[:3].lower()) + 1, m.group('ld'))
    else:
        parts = (m.group('dy'), _R_MONTHS.index(m.group('dm')[:3].lower()) + 1, m.group('dd'))
    try:
        day = dt.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
    if weekday and m.group('wd') and _R_WEEKDAYS.index(m.group('wd')[:3].lower()) != day.weekday():
        return None
    return day.isoformat()


def ruled_forms(span: str, head=True) -> list:
    """The decided forms a quoted span states, as (form, ISO date or None, the quote, the date as written or None):
    'label' (a label the ruling added, whatever its value: its date when it is a full date - only where ``head`` (True,
    False, or a predicate over the label's offset in ``span`` and its text) says the ruling reads it there; elsewhere
    such a match is no decided form at all), 'weekday' (a weekday before a full date, naming its weekday), 'dayfirst' (a day-first date
    with a month name and a four-digit year); a weekday or a day-first date only with its date. The date as written sets
    a weekday aside: a label the ruling added before "Tuesday, November 9, 2026" (a Monday) reads no date, but writes
    2026-11-09."""
    out = []
    for m in _RULED_FORM.finditer(span):
        if m.group('new') and not (head(m.start('new'), m.group('new')) if callable(head) else head):
            continue  # a label the ruling added where the ruling does not read it
        day = _ruled_day(m)
        forms = [name for name, present in (('label', m.group('new')), ('weekday', m.group('wd') and day),
                                            ('dayfirst', m.group('dd') and day)) if present]
        if forms:
            out.append(('+'.join(forms), day, ' '.join(m.group(0).split()), _ruled_day(m, weekday=False)))
    return out


def _head_bound(text: str) -> int:
    """Where ``text``'s first _R_HEAD_LINES non-empty lines end (its length when it has fewer)."""
    lines, at = 0, 0
    while at <= len(text):
        nl = text.find('\n', at)
        end = len(text) if nl < 0 else nl
        lines += bool(text[at:end].strip())
        if lines >= _R_HEAD_LINES or nl < 0:
            return end
        at = nl + 1
    return len(text)


def _ruled_place(text: str) -> tuple:
    """(where the document's head ends, whether its title is that of a note written around a procedure), as the
    installed reader computes them (context._head_end, sections.around_procedure_title) - recomputed here from the
    installed sections module, which the ruling does not change and whose layout H2 holds identical text by text: the
    first _R_HEAD_LINES non-empty lines, or the first section heading after the first two, whichever comes first."""
    from studio.gi import sections
    title_end = sections.head_lines_end(text, 2)
    first = next((s.start for s in sections.layout(text).sections if s.heading is not None and s.start >= title_end),
                 len(text))
    return min(_head_bound(text), first), sections.around_procedure_title(text)


def _r_opens_field(text: str, at: int, label: str) -> bool:
    """A flattened header row's field: a label written with a capital and lower case one space after a word written in
    lower case (as the installed reader reads one; its own copy here)."""
    if not label[:1].isupper() or label.upper() == label:
        return False
    word = _R_PREVIOUS_WORD.search(text[max(0, at - 40):at])
    return word is not None and word.group(1)[:1].islower()


def _label_read_at(text: str, at: int, place: tuple, label: str) -> bool:
    """Whether the ruling reads a label it added at offset ``at`` of ``text``: in the head (``place``: _ruled_place), no
    note written around a procedure, and the label standing as a label - it opens its line (a lead of blanks, markdown or
    a list mark before it) or a field of its own (a field break before it, or a flattened header row's field)."""
    head_end, around = place
    if around or at >= head_end:
        return False
    line_start = text.rfind('\n', 0, at) + 1
    before = text[max(line_start, at - 200):at]
    return bool((at - line_start <= 200 and _R_LEAD.match(before)) or _R_BREAK.search(before[-40:])
                or _r_opens_field(text, at, label))


def _evidence_forms(rec: dict, text: str, place=None) -> list:
    """Every decided form the service-date fact's evidence quotes (rec['fact'][2]: [start, end] offsets into text); a
    label the ruling added only where the ruling reads it (_label_read_at; ``place`` is _ruled_place(text), read when
    a span holds such a label and none is given)."""
    if not rec or 'fact' not in rec or text is None:
        return []
    out = []
    for start, end in rec['fact'][2]:
        def head(offset, label, start=start):
            nonlocal place
            if place is None:
                place = _ruled_place(text)
            return _label_read_at(text, start + offset, place, label)
        out += ruled_forms(text[start:end], head)
    return out


def _reworded(base_fact, head_fact, rewordings) -> bool:
    """Whether two service-date facts differ by their note alone, as the declaration's rewordings ([old, new] note texts,
    each the whole text of a note constant) change it: the base note with every old text replaced by its new one is the
    head's note, and the origin, value and evidence are equal."""
    if not rewordings or base_fact[:3] != head_fact[:3] or base_fact[3] == head_fact[3]:
        return False
    note = base_fact[3] or ''
    for old, new in rewordings:
        note = note.replace(old, new)
    return note == head_fact[3]


def _ruled_acceptor(base: dict, head: dict, texts: dict, declaration: dict):
    """classify's ``accept`` under the declaration's owner ruling: for one movement (class, text, member state) the
    decided form that explains it, quoted - or None, refused. Text by text, never by a count. The NEWLY SENT date of a
    text: the head's fact is the document's one date (origin 'document'), its primary state ('none') sends it, the
    base's primary state sent no date (DATELESS), and the fact's evidence quotes that date in a decided form.
    NEW-SEND      only with ``new_send_forms``: the state sends the newly sent date, and the base sent no date for the
                  state (DATELESS or HELD);
    NEW-HELD      only with ``new_held_forms``: the member's answer CONTRADICTS the newly sent date (another day);
    NEW-TAKE      only with ``new_take_forms``: the member's answer EQUALS the newly sent date;
    FACT-CHANGED  a decided form in the head's or the base's evidence, or a note the declaration rewords and nothing
                  else (``note_rewordings``, _reworded);
    STATE-CHANGED a decided form in the head's or the base's evidence, for a state both trees observed;
    SEND->ASK and every other class: never (other classes stay declared by count, as before)."""
    ruling = declaration.get('owner_ruling') or {}
    send, take, hold = (bool(ruling.get(k)) for k in ('new_send_forms', 'new_take_forms', 'new_held_forms'))
    rewordings = [tuple(pair) for pair in ruling.get('note_rewordings') or ()]

    places = {}

    def forms(rec, doc_id, text):
        if text is not None and doc_id not in places and _R_NEW_LABEL_RX.search(text) is not None:
            places[doc_id] = _ruled_place(text)  # read once per text, and only for a text writing such a label
        return _evidence_forms(rec, text, places.get(doc_id))

    def newly_sent(b, h, doc_id, text):
        fact = h.get('fact') or [None, None]
        bn, hn = (b.get('states') or {}).get('none') or {}, (h.get('states') or {}).get('none') or {}
        if fact[0] != 'document' or not fact[1] or bn.get('sends') != 'DATELESS' or hn.get('sends') != fact[1]:
            return None
        hit = next((f for f in forms(h, doc_id, text) if f[1] == fact[1]), None)
        return None if hit is None else (fact[1], f'{hit[0]} \u201c{hit[2]}\u201d')

    def decide(cls, doc_id, label):
        b, h, text = base.get(doc_id) or {}, head.get(doc_id) or {}, texts.get(doc_id)
        bs, hs = (b.get('states') or {}).get(label) or {}, (h.get('states') or {}).get(label) or {}
        if cls in ('NEW-SEND', 'NEW-TAKE', 'NEW-HELD'):
            sent = newly_sent(b, h, doc_id, text)
            if sent is None:
                return None
            if cls == 'NEW-SEND':
                ok = send and hs.get('sends') == sent[0] and bs.get('sends') in ('DATELESS', 'HELD')
                return sent[1] if ok else None
            answer = hs.get('answer')
            if cls == 'NEW-TAKE':
                ok = take and answer == sent[0] and hs.get('taken') and not bs.get('taken')
                return f'{sent[1]}, the answer {answer} equal to it' if ok else None
            ok = hold and answer is not None and answer != sent[0] and hs.get('held') and not bs.get('held')
            return f'{sent[1]}, the answer {answer} contradicting it' if ok else None
        if cls == 'STATE-CHANGED' and (label is None or not bs or not hs):
            return None  # a member state one tree did not observe is no movement of the ruling
        if cls == 'FACT-CHANGED' and _reworded(b.get('fact') or [None] * 4, h.get('fact') or [None] * 4, rewordings):
            return 'reworded note'
        if cls in ('FACT-CHANGED', 'STATE-CHANGED'):
            either = forms(h, doc_id, text) or forms(b, doc_id, text)
            return f'{either[0][0]} \u201c{either[0][2]}\u201d' if either else None
        return None

    def accept(cls, doc_id, label=None):
        why = decide(cls, doc_id, label)
        if why is not None:
            accept.rows.append([cls, doc_id, label, why])  # every accepted movement, for the report
        return why

    accept.rows = []
    return accept


# --- (b)-(d) the differential ----------------------------------------------------------------------------------------

def classify(base: dict, head: dict, accept=None) -> tuple[collections.Counter, dict]:
    """Movement counts and up to five examples per class, base -> head, over the texts both observed. With ``accept``
    (an owner ruling's _ruled_acceptor), a movement it explains is counted as CLASS + RULED, its example quoting the
    decided form, and never as CLASS."""
    counts, examples = collections.Counter(), collections.defaultdict(list)

    def note(cls, doc_id, detail, label=None):
        why = accept(cls, doc_id, label) if accept is not None else None
        if why is not None:
            cls, detail = cls + RULED, f'{detail} - quotes {why}'
        counts[cls] += 1
        if len(examples[cls]) < 5:
            examples[cls].append(f'{doc_id}: {detail}')

    for doc_id, b in base.items():
        h = head.get(doc_id)
        if h is None:
            note('TEXT-MISSING', doc_id, 'not observed on the head')
            continue
        if 'error' in b or 'error' in h:
            if b.get('error') != h.get('error'):
                note('READER-ERROR', doc_id, f"{b.get('error')} -> {h.get('error')}")
            continue
        if b['layout'] != h['layout']:
            note('LAYOUT-CHANGED', doc_id, 'sections.layout differs')
        if b['fact'] != h['fact']:
            note('FACT-CHANGED', doc_id, f"{b['fact'][:2]} -> {h['fact'][:2]}")
        if b['mentions'] != h['mentions']:
            note('MENTIONS-CHANGED', doc_id, f"{b['mentions']} -> {h['mentions']}")
        for label, bs in b['states'].items():
            hs = h['states'].get(label)
            if hs is None:
                note('STATE-CHANGED', doc_id, f'{label} not observed on the head')
                continue
            moved = False
            if hs['sends'] not in ('DATELESS', 'HELD') and hs['sends'] != bs['sends']:
                note('NEW-SEND', doc_id, f"{label}: {bs['sends']} -> {hs['sends']}", label)
                moved = True
            if hs['taken'] and not bs['taken']:
                note('NEW-TAKE', doc_id, f"{label}: {bs['answer']} taken", label)
                moved = True
            if hs['held'] and not bs['held']:
                note('NEW-HELD', doc_id, f"{label}: {bs['answer']} held ({bs['sends']} -> HELD)", label)
                moved = True
            if label == 'none' and bs['sends'] not in ('DATELESS', 'HELD') and hs['sends'] in ('DATELESS', 'HELD'):
                note('SEND->ASK', doc_id, f"{bs['sends']} -> {hs['sends']}", label)
                moved = True
            if hs['sends'] == bs['sends'] and hs['request'] != bs['request']:
                note('REQUEST-CHANGED', doc_id, f"{label}: {str(bs['request'])[:8]} -> {str(hs['request'])[:8]}")
                moved = True
            if not moved and (hs['sends'], hs['taken'], hs['held']) != (bs['sends'], bs['taken'], bs['held']):
                note('STATE-CHANGED', doc_id, f"{label}: {bs['sends']} -> {hs['sends']}", label)
    return counts, dict(examples)


def gate(cues: dict, counts: collections.Counter, declaration: dict) -> list:
    """The reasons the freeze fails (empty when it holds). With an owner ruling declared (the date forms: the only one
    this gate knows), a changed constant passes only when the ruling names it - and, where it pins a sha256, only as that
    sha256 - and NEW-SEND, NEW-TAKE, NEW-HELD and SEND->ASK pass only as the ruling's text-by-text acceptance counted
    them (CLASS + RULED): any of them left unaccepted fails, whatever count ``movements`` declares."""
    reasons = []
    ruling = declaration.get('owner_ruling')
    if ruling is not None and ruling.get('id') != DATE_FORMS_RULING:
        reasons.append(f"owner ruling {ruling.get('id')!r} is not one this gate knows ({DATE_FORMS_RULING!r})")
        ruling = None
    strict = STRICT_UNDER_RULING if ruling is not None else GATE
    for cls in strict:
        if counts.get(cls):
            reasons.append(f'{cls} = {counts[cls]} (the gate is {cls} = 0'
                           + (', but for the owner ruling\'s accepted movements)' if ruling is not None else ')'))
    named = (ruling or {}).get('changed_cues') or {}
    named = dict.fromkeys(named) if isinstance(named, list) else named
    head = cues.get('head', {})
    changed = [k for k in cues['changed'] if k not in named or (named[k] is not None and head.get(k) != named[k])]
    if changed or cues['removed']:
        reasons.append(f"cue patterns changed {changed} / removed {cues['removed']}"
                       + (' (an owner ruling names only its own, each as the sha256 it pins)' if ruling else ''))
    undeclared = sorted(set(cues['added']) - set(declaration.get('cues_added', ())))
    if undeclared:
        reasons.append(f'cue patterns added and not declared: {undeclared}')
    allowed = declaration.get('movements', {})
    for cls, n in sorted(counts.items()):
        if cls not in strict and not cls.endswith(RULED) and n > allowed.get(cls, 0):
            reasons.append(f'{cls} = {n}, declared {allowed.get(cls, 0)}')
    return reasons


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.freeze')
    parser.add_argument('--base')
    parser.add_argument('--head')
    parser.add_argument('--tree')
    parser.add_argument('--cues', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--corpus', nargs='*', default=(), help='extra JSONL corpora ({"text": ...} per line)')
    parser.add_argument('--quick', action='store_true', help='a twentieth of the generated corpus')
    parser.add_argument('--declare', help='the package declaration (JSON); default: the expected delta is NONE')
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--scratch')
    parser.add_argument('--out', help='write the report (JSON) here')
    parser.add_argument('--json-out', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.cues:
        boot.offline(args.tree)
        boot.write_json(args.json_out, cue_inventory())
        return 0
    if not (args.base and args.head):
        parser.error('--base and --head are required')
    scratch = boot.scratch_dir(args.scratch)
    trees = {'base': boot.tree_arg(args.base, scratch), 'head': boot.tree_arg(args.head, scratch)}
    declaration = json.loads(Path(args.declare).read_text(encoding='utf-8')) if args.declare else {}
    cues = compare_cues(*(boot.run_tool('freeze', trees[k], ['--cues'], scratch=scratch, label=f'cues-{k}')
                          for k in ('base', 'head')))
    docs = corpus_mod.full_corpus(quick=args.quick, extra=args.corpus)
    corpus_path = scratch / f'h2-corpus{"-quick" if args.quick else ""}.jsonl'
    corpus_mod.write(docs, corpus_path)
    obs = {k: corpus_mod.observe_tree(t, corpus_path, scratch, f'h2-{k}', readers=False, workers=args.workers)
           for k, t in trees.items()}
    ruling = declaration.get('owner_ruling')
    accept = (_ruled_acceptor(obs['base'], obs['head'], {d['id']: d['text'] for d in docs}, declaration)
              if ruling is not None and ruling.get('id') == DATE_FORMS_RULING else None)
    counts, examples = classify(obs['base'], obs['head'], accept)
    states = sum(len(o.get('states', {})) for o in obs['base'].values())
    requests = sum(1 for o in obs['base'].values() for s in o.get('states', {}).values() if s['request'])
    reasons = gate(cues, counts, declaration)
    print(f"== H2 freeze: base {trees['base']}\n               head {trees['head']}")
    print(f"(a) cue patterns read by context.py and sections.py: base {cues['count'][0]}, head {cues['count'][1]}; "
          f"changed {len(cues['changed'])}, removed {len(cues['removed'])}, added {len(cues['added'])}"
          + (f" {cues['added']}" if cues['added'] else '') + (f" changed {cues['changed']}" if cues['changed'] else ''))
    layout_n = counts.get('LAYOUT-CHANGED', 0)
    print(f'    sections.layout over {len(docs)} texts: {"identical" if not layout_n else f"{layout_n} differ"}')
    print(f'(b) date channel over {states} text x member states:', ', '.join(
        f'{c} {counts.get(c, 0)}' + (f' (+{counts[c + RULED]} accepted by the owner ruling)' if counts.get(c + RULED)
                                     else '') for c in DATE_CLASSES))
    print(f"(c) requests over {requests} primary and dated requests: changed {counts.get('REQUEST-CHANGED', 0)}")
    print(f"(d) mention counts over {len(docs)} texts: changed {counts.get('MENTIONS-CHANGED', 0)}")
    others = {c: counts.get(c, 0) for c in OTHER_CLASSES if counts.get(c)}
    if others:
        print('    other movements:', others)
    if accept is not None:
        forms = collections.Counter((cls, why.split(' ', 1)[0]) for cls, _, _, why in accept.rows)
        print(f"    the owner ruling ({ruling['id']}) accepted, text by text:",
              ', '.join(f'{cls} {n} quoting {form}' for (cls, form), n in sorted(forms.items())) or 'nothing')
    for cls, rows in examples.items():
        for row in rows[:3 if cls.endswith(RULED) else 5]:
            print(f'      {cls}: {row}')
    print('== GATE', 'HOLDS' if not reasons else 'FAILS: ' + '; '.join(reasons))
    if args.out:
        boot.write_json(args.out, {'cues': cues, 'texts': len(docs), 'states': states, 'requests': requests,
                                   'counts': dict(counts), 'examples': examples, 'gate': reasons,
                                   'accepted': accept.rows if accept is not None else [],
                                   'trees': {k: str(v) for k, v in trees.items()}})
    return 1 if reasons else 0


if __name__ == '__main__':
    sys.exit(main())
