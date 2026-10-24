"""Verify downloaded CPT Studio reports file by file, independently of the browser.

    .venv/bin/python ops/verify_downloads.py --evidence OUT/evidence.json [--api-dir DIR] [--only ID,ID]
                                             [--json-out PATH]

The input is the evidence JSON written by ops/verify_browser.cjs: every
downloaded file (path, size, the sha256 the browser computed, the sha256 the
API returned), the decisions it made, and the API snapshots it saved. The
encounter JSON (GET /api/encounters/<id>) comes from --api-dir/<encounter
id>.json when given, otherwise from the snapshot the evidence names; it is the
source of truth for proposals, current decisions and the revision text.

Per report file:
  sha256   the bytes on disk match every sha256 recorded for them
  marker   SYNTHETIC ... NOT FOR BILLING is present
  TXT      the header block says DRAFT — NOT REVIEWED or REVIEWED (and no
           DRAFT); a draft has no APPROVED SELECTIONS; a reviewed report's
           APPROVED SELECTIONS numbers exactly the approved proposals (code and
           units), rejected codes are listed outside it, the reviewer is named
           and agent review is labelled; the revision and its text sha256 are
           cited; every listed passage is present and every printed offset
           pair quotes exactly the revision text at those offsets
  CSV      parses; every cell is formula-neutralised; the (code, item list)
           rows equal what the persisted decisions imply, with matching
           decision, reviewer and units; constant columns name this encounter,
           revision and assessment; every passage is present and every printed
           offset pair quotes exactly the revision text

Exit status: 0 all checks passed; 1 at least one check failed; 2 nothing failed
but at least one check could not be performed (fail closed).

The report format is studio/reports.py ('cpt-studio-report@3'); the item-list
rules below mirror its _list_for. When the format changes, change these
constants and expected_list with it; never loosen a check to fit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

DRAFT_HEADLINE = re.compile(r'\bDRAFT\b\s*[-–—:]*\s*NOT\s+REVIEWED\b')
NOT_REVIEWED = re.compile(r'\bNOT\s+REVIEWED\b|\bUNREVIEWED\b', re.I)
REVIEWED_WORD = re.compile(r'\bREVIEWED\b')
SYNTHETIC_MARK = re.compile(r'SYNTHETIC[^\n]{0,24}?NOT\s+FOR\s+BILLING', re.I)
APPROVED_HEADING = 'APPROVED SELECTIONS'
# item list -> the heading prefix of the TXT section that lists it (reports.render_txt)
TXT_LIST_SECTIONS = {'approved': APPROVED_HEADING, 'rejected': 'REJECTED', 'undecided': 'UNDECIDED',
                     'excluded': 'EXCLUDED CANDIDATES', 'alternative': 'ALTERNATIVES'}
AGENT_LABEL = re.compile(r'agent-executed synthetic review', re.I)
CODE = r'(?:\d{5}|\d{4}[FTU]|[A-V]\d{4})'
# A code may carry a trailing '-modifier'; a leading '-' (an identifier or a range end) is not a code.
CODE_TOKEN = re.compile(rf'(?<![\w.@/-]){CODE}(?![\w/])')
# Item lines: the renderer prints them at two spaces and stored text always continues at seven or more
# (reports.CONTINUATION), so a note quoting "2. 45385 ..." is never an item, while any shallower code line still
# counts, whatever its marker ('2.', '2)', '(2)', '#2', '+', '‣', '–' or none): a forged item at column 0-6 must
# not pass as "not itemised" (round 3, orchestrator:3).
ITEM_LINE = re.compile(rf'^ {{0,6}}(?:(?:\(?\w{{1,4}}[.)]+|#\d+|[^\w\s])\s*)?(?P<code>{CODE})\b(?P<rest>.*)$')
CONTINUATION = '       '  # reports.CONTINUATION
# ITEM_LINE reads ASCII indentation only. A line is also read the way a viewer draws it (round 4, pipeline:5): every
# whitespace character takes one column, a tab included (a viewer draws one as anything from one to eight columns, the
# renderer never indents with one, and the narrowest reading is the one that counts the line); a zero-width character
# takes none and is dropped wherever it stands: a format character (Cf: ZWSP, joiners, BOM, bidi marks, soft hyphen),
# a combining mark (Mn, Me), or one of the default-ignorable letters below (the Hangul fillers).
_PIPE_IGNORABLE = frozenset('\u115f\u1160\u3164\uffa0')
# ITEM_LINE without its column limit: a code-first line at any depth. Before a list's first item there is nothing for a
# continuation to continue, so such a line there is no continuation (round 4, evidence:7).
_PIPE_ANY_DEPTH = re.compile(rf'^ *(?:(?:\(?\w{{1,4}}[.)]+|#\d+|[^\w\s])\s*)?(?P<code>{CODE})\b(?P<rest>.*)$')
# What _listed records for a line drawn as an item where the renderer writes none: never a persisted value, so the
# list check fails whatever code the line carries, the persisted approval itself included.
_PIPE_UNREAD = 'drawn as an item where the renderer writes none'
UNITS = re.compile(r'\bunits?\s+(\d+)\b', re.I)
TXT_OFFSETS = re.compile(r'\[chars (\d+)[–-](\d+)\b')
CSV_OFFSETS = re.compile(r'\[(\d+)-(\d+)(?:, p\d+)?\]')
# Offsets are read only where the renderer prints them: the closing bracket of a quoted passage at the end of a
# TXT evidence entry, and each ' | '-separated CSV evidence item's trailing bracket. Stored text (a note, an
# acknowledgement, a passage that itself contains '[2-3]') is never read as an offset pair.
TXT_EVIDENCE_END = re.compile(r'" \[chars (\d+)[–-](\d+)(?:, page \d+)?\]$')
CSV_EVIDENCE_OFFSETS = re.compile(r'(?<=" )\[(\d+)-(\d+)(?:, p\d+)?\](?= \| "|$)')
# Mirrors reports._join/_visible: in the TXT a line break of any form (str.splitlines) continues a value on an
# indented line, and every other C0 control but tab, DEL and C1 prints as \xNN; the CSV keeps line breaks inside
# its quoted cells and escapes the same controls. Passages are compared as the renderer shows them.
TXT_LINE_BREAKS = re.compile('[\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]')
CONTROL = re.compile('[\x00-\x08\x0e-\x1f\x7f-\x9f]')
HEX64 = re.compile(r'\b[0-9a-f]{64}\b', re.I)
UUID = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.I)
RULE_LINE = re.compile(r'^[\s=\-_*~─━—]+$')
OPTIONAL_HASHES = ('refetch_sha256', 'header_sha256')  # recorded when the browser verifier could take them
FORMULA_START = ('=', '+', '-', '@', '\t', '\r')
FORMULA_START_EXTRA = ('\n', '＝', '＋', '－', '＠')  # LF and fullwidth forms: warned, not required
ITEM_LISTS = ('approved', 'rejected', 'undecided', 'excluded', 'alternative')
SELECTED_LISTS = ('approved', 'rejected', 'undecided')
COLUMN_CANDIDATES = {
    'item_list': ('item_list', 'list', 'disposition'),
    'code': ('code', 'cpt', 'cpt_code'),
    'report_kind': ('report_kind',),
    'evidence': ('evidence',),
    'decision': ('decision',),
    'reviewer': ('reviewer',),
    'reviewer_kind': ('reviewer_kind',),
    'units': ('units',),
    'encounter_id': ('encounter_id',),
    'revision_number': ('revision_number',),
    'text_sha256': ('text_sha256',),
    'assessment_id': ('assessment_id',),
    'proposal_id': ('proposal_id',),
}


@dataclass
class Result:
    doc: str
    report: str
    check: str
    status: str  # pass | fail | warn | incomplete
    detail: str = ''


@dataclass
class Item:
    proposal_id: str
    code: str
    item_list: str
    bucket: str
    status: str
    units: str
    action: str
    reviewer: str
    reviewer_kind: str
    evidence: list
    labels: tuple
    reinstated_by: str = ''        # what the encounter JSON says (proposal.reinstated_by)
    reinstated_by_kind: str = ''
    decision_id: str = ''
    derived_by: str = ''           # re-derived here from decisions.history, following carries
    derived_kind: str = ''


# --- helpers ------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collapse(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def cp_slice(text: str, start, end):
    """API offsets are Python code points, as Python str indexing is; bad offsets give None."""
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        return None
    return text[start:end]


def escaped(text: str) -> str:
    return CONTROL.sub(lambda m: f'\\x{ord(m.group()):02x}', text)


def txt_shown(text: str) -> str:
    """A passage as the TXT prints it (line breaks become continuation lines; collapse() then reads them as spaces)."""
    return escaped(TXT_LINE_BREAKS.sub('\n', text))


def who(reviewer: str, kind: str) -> str:
    """reports._who: an agent always reads as an automated agent, once."""
    if kind == 'agent':
        return reviewer if 'automated agent' in reviewer else f'{reviewer} (automated agent)'
    return f'{reviewer} ({kind})'


def reinstatement_from_history(api: dict, decision_id: str):
    """The reinstate decision a current decision rests on, re-derived from decisions.history as
    review.reinstatement_for derives it: the decision itself; else the latest earlier, not invalidated reinstate on
    the same proposal; else the same question for the decision it was carried from. History is in sequence order."""
    history = list(((api.get('decisions') or {}).get('history')) or [])
    index = {str(entry.get('id')): n for n, entry in enumerate(history)}
    node, seen = index.get(str(decision_id)) if decision_id else None, set()
    while node is not None and node not in seen:
        seen.add(node)
        entry = history[node]
        if entry.get('action') == 'reinstate':
            return entry
        prior = [e for e in history[:node] if e.get('proposal_id') == entry.get('proposal_id')
                 and e.get('action') == 'reinstate' and not e.get('invalidated')]
        if prior:
            return prior[-1]
        node = index.get(str(entry['carried_from'])) if entry.get('carried_from') else None
    return None


def undo_neutralisation(cell: str) -> str:
    if cell[:1] == "'" and cell[1:2] in FORMULA_START + FORMULA_START_EXTRA:
        return cell[1:]
    return cell


def norm_header(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', undo_neutralisation(name.strip()).lower()).strip('_')


def norm_list(value: str) -> str:
    value = undo_neutralisation(value.strip()).strip().lower().replace(' ', '_')
    return value[:-1] if value.endswith('s') and value[:-1] in ITEM_LISTS else value


def expected_list(proposal: dict, kind: str) -> str:
    """The item list a report of ``kind`` must show for a proposal (mirrors reports._list_for)."""
    action = (proposal.get('decision') or {}).get('action')
    if proposal.get('bucket') == 'alternative':
        return 'alternative'
    if action == 'reject':
        return 'rejected'
    if action == 'approve' and kind == 'reviewed':
        return 'approved'
    if proposal.get('bucket') == 'excluded' and action in (None, 'confirm'):
        return 'excluded'
    return 'undecided'


def items_from_api(api: dict, kind: str) -> dict[str, Item]:
    items = {}
    for p in ((api.get('assessment') or {}).get('proposals')) or []:
        decision = p.get('decision') or {}
        labels = tuple(x for x in (p.get('family_label'), p.get('eyebrow'), p.get('family')) if x)
        # Mirrors serializers._reinstated_by: only an excluded proposal is ever reinstated, and a confirmed
        # exclusion never was.
        reinstated = p.get('bucket') == 'excluded' and decision.get('action') != 'confirm'
        derived = (reinstatement_from_history(api, decision.get('id', '')) or {}) if reinstated else {}
        items[str(p['id'])] = Item(
            proposal_id=str(p['id']), code=str(p.get('code', '')), item_list=expected_list(p, kind),
            bucket=p.get('bucket', ''), status=p.get('status', ''), units=str(p.get('units', '')),
            action=decision.get('action', ''), reviewer=decision.get('reviewer', ''),
            reviewer_kind=decision.get('reviewer_kind', ''), evidence=list(p.get('evidence') or []), labels=labels,
            reinstated_by=(p.get('reinstated_by') or {}).get('reviewer', ''),
            reinstated_by_kind=(p.get('reinstated_by') or {}).get('reviewer_kind', ''),
            decision_id=str(decision.get('id', '')), derived_by=derived.get('reviewer', ''),
            derived_kind=derived.get('reviewer_kind', ''))
    return items


def exact_spans(item: Item, revision_text: str) -> list[dict]:
    """The item's evidence spans that really equal the revision text at their offsets."""
    return [s for s in item.evidence if s.get('context_index', 0) in (0, None)
            and cp_slice(revision_text, s.get('start'), s.get('end')) == s.get('text')]


def code_tokens(text: str, strip: list[str]) -> set[str]:
    """Code-shaped tokens in text once quoted passages, offsets, hashes and ids are removed."""
    text = collapse(text)
    for passage in sorted({collapse(s) for s in strip if s.strip()}, key=len, reverse=True):
        text = text.replace(passage, ' ')
    text = TXT_OFFSETS.sub(' ', CSV_OFFSETS.sub(' ', UUID.sub(' ', HEX64.sub(' ', text))))
    return set(CODE_TOKEN.findall(text))


# --- sha256 -------------------------------------------------------------------

def check_hashes(doc: str, name: str, data: bytes, download: dict, listed: dict) -> list[Result]:
    actual = sha256_bytes(data)
    out = []
    for field, label in (('sha256', 'browser-computed'), ('api_sha256', 'API response'),
                         ('refetch_sha256', 're-fetched download'), ('header_sha256', 'X-Content-SHA256 header')):
        recorded = download.get(field)
        if recorded is None and field in OPTIONAL_HASHES:
            continue
        if not recorded:
            out.append(Result(doc, name, f'sha256.{field}', 'fail', f'no {label} sha256 recorded'))
        else:
            out.append(Result(doc, name, f'sha256.{field}', 'pass' if recorded == actual else 'fail',
                              actual if recorded == actual else f'file {actual} != {label} {recorded}'))
    report_id = download.get('report_id')
    if report_id in listed:
        ok = listed[report_id] == actual
        out.append(Result(doc, name, 'sha256.listing', 'pass' if ok else 'fail',
                          f'encounter report listing {listed[report_id]}'))
    else:
        out.append(Result(doc, name, 'sha256.listing', 'incomplete', f'report {report_id} not in the API listing'))
    if download.get('size') != len(data):
        out.append(Result(doc, name, 'size', 'fail', f'file {len(data)} bytes != recorded {download.get("size")}'))
    return out


# --- TXT ----------------------------------------------------------------------

def txt_sections(text: str, sub_headings: set[str]) -> list[tuple[str, list[str]]]:
    """[(heading, body lines)]; the header block before the first heading has heading ''.

    A heading is an unindented line with no lowercase letter, at least four
    capitals and no code, after a blank line or rule; a family label or eyebrow
    is a sub-heading and stays inside its section.
    """
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = [('', [])]
    for index, line in enumerate(lines):
        previous = lines[index - 1] if index else ''
        is_heading = (bool(line.strip()) and line == line.lstrip() and not RULE_LINE.match(line)
                      and not re.search(r'[a-z]', line) and len(re.findall(r'[A-Z]', line)) >= 4
                      and not CODE_TOKEN.search(line) and (not previous.strip() or bool(RULE_LINE.match(previous)))
                      and line.strip().upper() not in sub_headings)
        if is_heading:
            sections.append((line.strip(), []))
        else:
            sections[-1][1].append(line)
    return sections


def header_block(text: str) -> str:
    block = []
    for line in text.splitlines():
        if not line.strip():
            if block:
                break
            continue
        block.append(line)
    return '\n'.join(block)


def check_txt(doc: str, name: str, text: str, kind: str, api: dict | None) -> list[Result]:
    out = [_marker(doc, name, text)]
    head = header_block(text)
    if kind == 'draft':
        ok = bool(DRAFT_HEADLINE.search(head))
        out.append(Result(doc, name, 'headline', 'pass' if ok else 'fail',
                          'DRAFT — NOT REVIEWED' if ok else 'no DRAFT — NOT REVIEWED headline in the header block'))
    else:
        reviewed = [ln for ln in head.splitlines() if REVIEWED_WORD.search(ln) and not NOT_REVIEWED.search(ln)]
        ok = bool(reviewed) and not re.search(r'\bDRAFT\b', head)
        out.append(Result(doc, name, 'headline', 'pass' if ok else 'fail',
                          reviewed[0].strip() if ok else 'REVIEWED headline missing, or DRAFT in the header block'))
    items = items_from_api(api, kind) if api else {}
    sections = txt_sections(text, {label.upper() for item in items.values() for label in item.labels})
    approved = [body for heading, body in sections if heading == APPROVED_HEADING]
    if kind == 'draft':
        out.append(Result(doc, name, 'approved.section', 'fail' if approved else 'pass',
                          'a draft must not contain APPROVED SELECTIONS' if approved else 'absent'))
    if api is None:
        out.append(Result(doc, name, 'content.vs.api', 'incomplete', 'no encounter JSON; content checks skipped'))
        return out
    revision = api.get('revision') or {}
    revision_text = revision.get('text') or ''
    out.extend(_txt_citations(doc, name, text, revision))
    out.extend(_txt_lists(doc, name, sections, items, kind))
    if kind == 'reviewed' and len(approved) == 1:
        out.extend(_approved_mentions(doc, name, approved[0], items))
    out.extend(_reviewer_labels(doc, name, text, items, sections, kind))
    listed = [i for i in items.values() if i.item_list == ('approved' if kind == 'reviewed' else 'undecided')]
    out.extend(_txt_passages(doc, name, text, listed, revision_text, sections, kind))
    return out


def _marker(doc, name, text) -> Result:
    marker = SYNTHETIC_MARK.search(text)
    return Result(doc, name, 'marker.synthetic', 'pass' if marker else 'fail',
                  marker.group(0) if marker else 'SYNTHETIC ... NOT FOR BILLING not found')


def _txt_citations(doc, name, text, revision) -> list[Result]:
    out = []
    number = revision.get('number')
    ok = number is not None and re.search(rf'^\s*Revision:\s*{number}\b', text, re.M)
    out.append(Result(doc, name, 'cites.revision.number', 'pass' if ok else 'fail',
                      f'revision {number}' if ok else f'revision {number} not cited'))
    cited = [('revision.text_sha256', revision.get('text_sha256'))]
    if revision.get('source_file'):
        cited.append(('source_file.sha256', revision['source_file'].get('sha256')))
    for check, value in cited:
        if not value:
            out.append(Result(doc, name, f'cites.{check}', 'incomplete', 'not in the encounter JSON'))
        else:
            out.append(Result(doc, name, f'cites.{check}', 'pass' if value in text else 'fail',
                              value if value in text else f'{value} not cited'))
    return out


def _PIPE_zero_width(ch) -> bool:
    return unicodedata.category(ch) in ('Cf', 'Mn', 'Me') or ch in _PIPE_IGNORABLE


def _PIPE_shown(line) -> str:
    """The line as a viewer draws it: its leading whitespace and zero-width characters redrawn as the ASCII spaces
    they occupy, and every other zero-width character dropped."""
    width = index = 0
    while index < len(line) and (line[index].isspace() or _PIPE_zero_width(line[index])):
        width += line[index].isspace()
        index += 1
    return ' ' * width + ''.join(ch for ch in line[index:] if not _PIPE_zero_width(ch))


def _PIPE_unread_item(line, before_first_item):
    """The code of a line a viewer reads as an item and ITEM_LINE does not: one that reads as an item once drawn as a
    viewer draws it, or, before the list's first item, a code-first line at continuation depth. None otherwise."""
    shown = _PIPE_shown(line)
    match = ITEM_LINE.match(shown) or (_PIPE_ANY_DEPTH.match(shown) if before_first_item else None)
    return match.group('code') if match else None


def _listed(body, with_units) -> Counter:
    listed = Counter()
    before_first_item = True
    for line in body:
        match = ITEM_LINE.match(line)
        if match:
            before_first_item = False
            units = UNITS.search(match.group('rest'))
            listed[(match.group('code'), (units.group(1) if units else '?') if with_units else '')] += 1
            continue
        unread = _PIPE_unread_item(line, before_first_item)
        if unread:
            listed[(unread, _PIPE_UNREAD)] += 1
    return listed


def _txt_lists(doc, name, sections, items, kind) -> list[Result]:
    """Each list section itemises exactly the proposals the persisted state puts in that list."""
    out = []
    for item_list, prefix in TXT_LIST_SECTIONS.items():
        if (item_list == 'approved' and kind != 'reviewed') or (item_list == 'undecided' and kind == 'reviewed'):
            continue
        bodies = [body for heading, body in sections if heading.startswith(prefix)]
        check = 'approved.codes' if item_list == 'approved' else f'list.{item_list}'
        if len(bodies) != 1:
            out.append(Result(doc, name, check, 'fail', f'{len(bodies)} "{prefix}" sections (expected 1)'))
            continue
        with_units = item_list == 'approved'
        expected = Counter((i.code, i.units if with_units else '') for i in items.values()
                           if i.item_list == item_list)
        listed = _listed(bodies[0], with_units)
        shown = sorted(code if not units else f'{code} x{units}' for code, units in expected.elements())
        out.append(Result(doc, name, check, 'pass' if listed == expected else 'fail',
                          f'exactly {shown or "none"}' if listed == expected else
                          f'listed {sorted(listed.elements())}, persisted {sorted(expected.elements())}'))
    return out


def _approved_mentions(doc, name, body, items) -> list[Result]:
    approved = {i.code for i in items.values() if i.item_list == 'approved'}
    others = {i.code for i in items.values() if i.item_list != 'approved'} - approved
    passages = [s.get('text', '') for i in items.values() for s in i.evidence]
    mentioned = code_tokens('\n'.join(body), passages) & others
    if not mentioned:
        return []
    return [Result(doc, name, 'approved.mentions_others', 'warn',
                   f'non-approved codes mentioned (not itemised) in APPROVED SELECTIONS: {sorted(mentioned)}')]


def item_blocks(body) -> list[tuple[str, list[str]]]:
    """A numbered list section split into item blocks, each from one item line to the next."""
    blocks: list[tuple[str, list[str]]] = []
    for line in body:
        match = ITEM_LINE.match(line)
        if match:
            blocks.append((match.group('code'), [line]))
        elif blocks:
            blocks[-1][1].append(line)
    return blocks


def _numbered_prefix(kind) -> str:
    """The list whose items the renderer prints as numbered blocks: approved (reviewed) or undecided (draft)."""
    return TXT_LIST_SECTIONS['approved' if kind == 'reviewed' else 'undecided']


def _reviewer_labels(doc, name, text, items, sections, kind) -> list[Result]:
    decided = [i for i in items.values() if i.action]
    reviewers = sorted({i.reviewer for i in decided if i.reviewer})
    missing = [r for r in reviewers if r not in text]
    out = [Result(doc, name, 'reviewer.identity', 'fail' if missing else 'pass',
                  f'reviewer not named: {missing}' if missing else ', '.join(reviewers) or 'no decisions')]
    # Who reinstated a code is re-derived from decisions.history (following carries); the encounter JSON's own
    # proposal.reinstated_by must agree with it, so neither can silently lose the agent.
    disagree = [f'{i.code}: history says {i.derived_by or "none"} ({i.derived_kind or "-"}), proposal.reinstated_by '
                f'says {i.reinstated_by or "none"} ({i.reinstated_by_kind or "-"})'
                for i in items.values() if (i.derived_by, i.derived_kind) != (i.reinstated_by, i.reinstated_by_kind)]
    if disagree:
        out.append(Result(doc, name, 'reviewer.reinstated_by.consistent', 'fail', '; '.join(disagree)))
    if any(i.reviewer_kind == 'agent' for i in decided) or any(i.derived_kind == 'agent' for i in items.values()):
        ok = bool(AGENT_LABEL.search(text))
        out.append(Result(doc, name, 'reviewer.agent_label', 'pass' if ok else 'fail',
                          'agent-executed synthetic review labelled' if ok else 'agent review not labelled'))
    # The renderer names the reinstater inside the item's OWN block, for the numbered list only (a rejected code's
    # short line names no reinstater): one named block per agent-reinstated item, never a match elsewhere.
    numbered = 'approved' if kind == 'reviewed' else 'undecided'
    due = [i for i in items.values() if i.derived_kind == 'agent' and i.item_list == numbered]
    if due:
        bodies = [body for heading, body in sections if heading.startswith(_numbered_prefix(kind))]
        blocks = item_blocks(bodies[0]) if len(bodies) == 1 else []
        used: set[int] = set()
        for item in due:
            label = who(item.derived_by, item.derived_kind)
            phrase = collapse(f'Reinstated from exclusion by {label}')
            found = next((n for n, (code, block) in enumerate(blocks)
                          if n not in used and code == item.code and phrase in collapse('\n'.join(block))), None)
            if found is not None:
                used.add(found)
            out.append(Result(doc, name, f'reviewer.reinstated_by.{item.code}', 'pass' if found is not None else 'fail',
                              f'{item.code}: reinstated by {label}' + ('' if found is not None
                                                                     else ' is not named in its own item block')))
    return out


def _evidence_entries(sections, kind) -> list[tuple[str, int, int]]:
    """(entry text, start, end) for each evidence entry printed where the renderer prints one: after an item
    block's '     Evidence:' line (up to the block's next field), and '    Evidence: "' lines in ENCOUNTER CONTEXT.
    A passage that continues over several lines is one entry; its offsets are its closing bracket."""
    entries: list[tuple[str, int, int]] = []

    def scan(lines, opener, prefix):
        # An entry is its opener and every continuation line up to the next opener. Its offsets are its LAST
        # line that ends like a citation: a passage line that happens to end in '" [chars 1-2]' is text, and the
        # renderer's closing bracket comes after it (round 3, orchestrator:1).
        runs, current = [], None
        for line in lines:
            if line.startswith(opener):
                current = [line]
                runs.append(current)
            elif current is not None and line.startswith(CONTINUATION):
                current.append(line)
            else:
                current = None
        for run in runs:
            ends = [i for i, line in enumerate(run) if TXT_EVIDENCE_END.search(line)]
            if ends:
                match = TXT_EVIDENCE_END.search(run[ends[-1]])
                text = [run[0][len(prefix):]] + [line.strip() for line in run[1:ends[-1] + 1]]
                entries.append(('\n'.join(text), int(match.group(1)), int(match.group(2))))

    for heading, body in sections:
        if heading.startswith(_numbered_prefix(kind)):
            for _, block in item_blocks(body):
                if '     Evidence:' not in block:
                    continue
                region = []
                for line in block[block.index('     Evidence:') + 1:]:
                    if not line.startswith(CONTINUATION):
                        break  # the block's next field (Rationale:, Modifier considerations ...)
                    region.append(line)
                scan(region, '       - "', '       - ')
        elif heading == 'ENCOUNTER CONTEXT':
            scan(body, '    Evidence: "', '    Evidence: ')
    return entries


def _txt_passages(doc, name, text, listed, revision_text, sections, kind) -> list[Result]:
    flat = collapse(text)
    missing = []
    for item in listed:
        spans = exact_spans(item, revision_text)
        if not spans:
            missing.append(f'{item.code}: no exact evidence span in the encounter JSON')
        for span in spans:
            quoted = collapse(f'"{txt_shown(span["text"])}" [chars {span["start"]}')
            if quoted not in flat:
                missing.append(f'{item.code}[{span["start"]}:{span["end"]}]')
    wrong = []
    for entry, start, end in _evidence_entries(sections, kind):
        passage = cp_slice(revision_text, start, end)
        flat = collapse(entry)
        tail = TXT_EVIDENCE_END.search(flat)
        # The WHOLE quoted text before the entry's structural bracket must be the revision text at its offsets: a
        # prefix test let anything, an inner bracket with a wrong end offset included, stand between the passage and
        # the bracket read (round 4, pipeline:4). The closing quote stays in the comparison, so a space before it is
        # not collapsed away.
        quoted = collapse(flat[:tail.start()] + '"') if tail else None
        if passage is None or quoted != collapse(f'"{txt_shown(passage)}"'):
            wrong.append(f'{start}-{end}')
    return [Result(doc, name, 'evidence.present', 'fail' if missing else 'pass',
                   f'missing: {missing}' if missing else f'{sum(len(exact_spans(i, revision_text)) for i in listed)}'
                                                         ' passage(s) present with their offsets'),
            Result(doc, name, 'evidence.offsets', 'fail' if wrong else 'pass',
                   f'printed offsets that do not quote the revision text: {wrong}' if wrong
                   else 'every printed offset pair quotes the revision text exactly')]


# --- CSV ----------------------------------------------------------------------

def parse_csv(text: str):
    """-> (header, data rows); raises ValueError (or csv.Error) when there is no usable header."""
    rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    if not rows:
        raise ValueError('empty CSV')
    names = {norm_header(cell) for cell in rows[0]}
    if not (names & set(COLUMN_CANDIDATES['code']) and names & set(COLUMN_CANDIDATES['item_list'])):
        raise ValueError(f'the header has no code column and item-list column ({rows[0]})')
    return rows[0], rows[1:]


def resolve_columns(header: list[str]) -> dict[str, int]:
    names = [norm_header(cell) for cell in header]
    columns = {}
    for logical, candidates in COLUMN_CANDIDATES.items():
        found = next((candidate for candidate in candidates if candidate in names), None)
        if found:
            columns[logical] = names.index(found)
    return columns


def check_csv(doc: str, name: str, text: str, kind: str, api: dict | None) -> list[Result]:
    out = [_marker(doc, name, text)]
    try:
        header, data = parse_csv(text)
    except (csv.Error, ValueError) as exc:
        out.append(Result(doc, name, 'csv.parse', 'fail', str(exc)))
        return out
    ragged = [n for n, row in enumerate(data, start=2) if len(row) != len(header)]
    out.append(Result(doc, name, 'csv.parse', 'fail' if ragged else 'pass',
                      f'rows {ragged[:5]} do not have {len(header)} fields' if ragged
                      else f'{len(data)} data row(s), {len(header)} columns'))
    out.extend(_neutralised(doc, name, [header] + data))
    columns = resolve_columns(header)
    rows = [row for row in data if len(row) == len(header)]
    out.append(_csv_kind(doc, name, text, kind, rows, columns))
    # A report with no proposals carries exactly one placeholder row (item list 'none') so that the file itself
    # still names its kind and SYNTHETIC; it is never an item.
    placeholder = [row for row in rows if 'item_list' in columns and norm_list(row[columns['item_list']]) == 'none']
    items_rows = [row for row in rows if not ('item_list' in columns and norm_list(row[columns['item_list']]) == 'none')]
    if placeholder:
        identity = {'report_kind', 'encounter_id', 'revision_number', 'source_sha256', 'text_sha256', 'assessment_id',
                    'item_list', 'not_verified', 'synthetic'}
        filled = sorted(norm_header(h) for i, h in enumerate(header) for row in placeholder
                        if norm_header(h) not in identity and undo_neutralisation(row[i]).strip())
        proposals = ((api or {}).get('assessment') or {}).get('proposals')
        ok = len(placeholder) == 1 and not items_rows and not filled and not proposals
        out.append(Result(doc, name, 'csv.placeholder', 'pass' if ok else 'fail',
                          'no proposals: one placeholder row names the report kind' if ok else
                          f'{len(placeholder)} placeholder row(s) beside {len(items_rows)} item row(s); '
                          f'item cells filled: {sorted(set(filled))}; persisted proposals: {len(proposals or [])}'))
    if api is None:
        out.append(Result(doc, name, 'content.vs.api', 'incomplete', 'no encounter JSON; content checks skipped'))
        return out
    items = items_from_api(api, kind)
    revision_text = (api.get('revision') or {}).get('text') or ''
    out.extend(_csv_items(doc, name, items_rows, columns, items, kind))
    out.extend(_csv_constants(doc, name, rows, columns, api))
    out.extend(_csv_evidence(doc, name, items_rows, columns, items, revision_text))
    return out


def _cell(row, columns, logical) -> str:
    return undo_neutralisation(row[columns[logical]]) if logical in columns else ''


def _neutralised(doc, name, rows) -> list[Result]:
    bad, extra = [], []
    for r, row in enumerate(rows, start=1):
        for c, cell in enumerate(row, start=1):
            if cell[:1] in FORMULA_START:
                bad.append(f'row {r} col {c}: {cell[:20]!r}')
            elif cell[:1] in FORMULA_START_EXTRA:
                extra.append(f'row {r} col {c}: {cell[:20]!r}')
    out = [Result(doc, name, 'csv.neutralised', 'fail' if bad else 'pass',
                  f'formula-like cells: {bad[:5]}' if bad else 'no cell starts with = + - @ tab CR')]
    if extra:
        out.append(Result(doc, name, 'csv.neutralised_extra', 'warn', f'LF/fullwidth-leading cells: {extra[:5]}'))
    return out


def _csv_kind(doc, name, text, kind, rows, columns) -> Result:
    if 'report_kind' in columns:
        values = sorted({_cell(row, columns, 'report_kind').strip().lower() for row in rows})
        ok = values == [kind] or (not rows and not values)
        return Result(doc, name, 'csv.kind', 'pass' if ok else 'fail', f'report_kind values {values}')
    has_draft = bool(re.search(r'\bDRAFT\b', text, re.I))
    ok = has_draft if kind == 'draft' else not has_draft
    return Result(doc, name, 'csv.kind', 'pass' if ok else 'fail',
                  f'no report_kind column; "draft" {"present" if has_draft else "absent"} in the file')


def _csv_items(doc, name, rows, columns, items, kind) -> list[Result]:
    def key(code, item_list, action, reviewer, reviewer_kind, units, proposal_id=None):
        return (code, item_list, action, reviewer, reviewer_kind, units, proposal_id)

    by_id = 'proposal_id' in columns  # one row per proposal: compare exactly, not as a multiset
    written = Counter(key(_cell(r, columns, 'code').strip(), norm_list(r[columns['item_list']]),
                          _cell(r, columns, 'decision').strip() if 'decision' in columns else None,
                          _cell(r, columns, 'reviewer').strip() if 'reviewer' in columns else None,
                          _cell(r, columns, 'reviewer_kind').strip() if 'reviewer_kind' in columns else None,
                          _cell(r, columns, 'units').strip() if 'units' in columns else None,
                          _cell(r, columns, 'proposal_id').strip() if by_id else None) for r in rows)
    persisted = Counter(key(i.code, i.item_list,
                            i.action if 'decision' in columns else None,
                            i.reviewer if 'reviewer' in columns else None,
                            i.reviewer_kind if 'reviewer_kind' in columns else None,
                            i.units if 'units' in columns else None,
                            i.proposal_id if by_id else None) for i in items.values())
    missing, extra = persisted - written, written - persisted
    fields = ['code', 'item_list'] + [c for c in ('decision', 'reviewer', 'reviewer_kind', 'units') if c in columns]
    out = [Result(doc, name, 'csv.items', 'pass' if not (missing or extra) else 'fail',
                  f'{len(rows)} row(s) match the persisted proposals and decisions ({", ".join(fields)})'
                  if not (missing or extra) else
                  f'persisted but not in the CSV: {sorted(_short(k) for k in missing.elements())}; '
                  f'in the CSV but not persisted: {sorted(_short(k) for k in extra.elements())}')]
    if kind == 'reviewed':
        approved_rows = sorted(_cell(r, columns, 'code') for r in rows if norm_list(r[columns['item_list']]) == 'approved')
        approved = sorted(i.code for i in items.values() if i.item_list == 'approved')
        out.append(Result(doc, name, 'csv.approved_codes', 'pass' if approved_rows == approved else 'fail',
                          f'approved rows {approved_rows}; persisted approvals {approved}'))
    return out


def _short(key) -> str:
    code, item_list, action, _, reviewer_kind, units, _proposal = key
    return f'{code}/{item_list}' + (f'/{action or "-"}' if action is not None else '') + (
        f'/{reviewer_kind or "-"}' if reviewer_kind is not None else '') + (f'/u{units}' if units is not None else '')


def _csv_constants(doc, name, rows, columns, api) -> list[Result]:
    revision = api.get('revision') or {}
    expected = {'encounter_id': api.get('id'), 'revision_number': revision.get('number'),
                'text_sha256': revision.get('text_sha256'), 'assessment_id': (api.get('assessment') or {}).get('id')}
    out = []
    for column, value in expected.items():
        if column not in columns:
            continue
        values = sorted({_cell(row, columns, column) for row in rows})
        ok = value is not None and values in ([str(value)], [])
        out.append(Result(doc, name, f'csv.{column}', 'pass' if ok else 'fail', f'{values} (expected {value})'))
    return out


def csv_evidence_cell(item: Item, revision_text: str) -> str:
    """The evidence cell reports._csv_row writes for ``item``: its exact passages only, as the CSV shows them."""
    return escaped(' | '.join(f'"{s["text"]}" [{s["start"]}-{s["end"]}' + (f', p{s["page"]}]' if s.get('page') else ']')
                              for s in exact_spans(item, revision_text)))


def _csv_evidence(doc, name, rows, columns, items, revision_text) -> list[Result]:
    if 'evidence' not in columns:
        return [Result(doc, name, 'csv.evidence', 'fail', 'no evidence column')]
    groups: dict[tuple, list[str]] = {}
    for row in rows:
        group = (_cell(row, columns, 'code').strip(), norm_list(row[columns['item_list']]))
        groups.setdefault(group, []).append(_cell(row, columns, 'evidence'))
    missing, missing_other = [], []
    for item in items.values():
        cells = '\n'.join(groups.get((item.code, item.item_list), []))
        for span in exact_spans(item, revision_text):
            if f'"{escaped(span["text"])}" [{span["start"]}-{span["end"]}' not in cells:
                (missing if item.item_list in SELECTED_LISTS else missing_other).append(
                    f'{item.code}[{span["start"]}:{span["end"]}]')
    wrong = []
    for row in rows:
        cell = _cell(row, columns, 'evidence')
        item = items.get(_cell(row, columns, 'proposal_id').strip()) if 'proposal_id' in columns else None
        if item is not None and cell == csv_evidence_cell(item, revision_text):
            # Exactly the renderer's layout of this proposal's exact passages: every bracket in it is structural
            # and quotes the revision text, whatever the passages themselves contain (round 3, orchestrator:1).
            continue
        for match in CSV_EVIDENCE_OFFSETS.finditer(cell):
            start, end = int(match.group(1)), int(match.group(2))
            passage = cp_slice(revision_text, start, end)
            # The item's quoted passage ends right before its bracket and is exactly the (escaped) revision text.
            if passage is None or not cell[:match.start()].endswith(f'"{escaped(passage)}" '):
                wrong.append(f'{start}-{end}')
    out = [Result(doc, name, 'csv.evidence.present', 'fail' if missing else 'pass',
                  f'missing passages of selected proposals: {missing}' if missing
                  else 'every exact passage of a selected proposal present with its offsets'),
           Result(doc, name, 'csv.evidence.offsets', 'fail' if wrong else 'pass',
                  f'printed offsets that do not quote the revision text: {wrong}' if wrong
                  else 'every printed offset pair quotes the revision text exactly')]
    if missing_other:
        out.append(Result(doc, name, 'csv.evidence.present_other', 'warn',
                          f'excluded/alternative passages not in the CSV: {missing_other}'))
    return out


# --- API-level ------------------------------------------------------------------

def check_api_evidence(doc: str, api: dict) -> list[Result]:
    revision_text = (api.get('revision') or {}).get('text')
    if revision_text is None:
        return [Result(doc, '-', 'api.evidence.exact', 'incomplete', 'no revision text in the encounter JSON')]
    wrong, ready_without = [], []
    for item in items_from_api(api, 'draft').values():
        for span in item.evidence:
            if span.get('exact', True) and span.get('context_index', 0) in (0, None) and \
                    cp_slice(revision_text, span.get('start'), span.get('end')) != span.get('text'):
                wrong.append(f'{item.code}[{span.get("start")}:{span.get("end")}]')
        if item.bucket == 'selected' and item.status == 'ready' and not exact_spans(item, revision_text):
            ready_without.append(item.code)
    return [Result(doc, '-', 'api.evidence.exact', 'fail' if wrong else 'pass',
                   f'spans claimed exact but not equal to the revision text: {wrong}' if wrong
                   else 'every span claimed exact equals the revision text'),
            Result(doc, '-', 'api.ready_has_exact_evidence', 'fail' if ready_without else 'pass',
                   f'ready proposals without exact evidence: {ready_without}' if ready_without else 'yes')]


def _decisions_match(doc_id, doc, api) -> Result:
    proposals = {str(p['id']): p for p in (api.get('assessment') or {}).get('proposals', [])}
    recorded = [d for d in doc.get('decisions') or [] if d.get('http_status') == 201]
    wrong = []
    for decision in recorded:
        state = (proposals.get(str(decision.get('proposal_id'))) or {}).get('decision_state')
        expected = {'approve': 'approved', 'reject': 'rejected', 'confirm': 'exclusion_confirmed'}.get(decision.get('action'))
        if state != expected:
            wrong.append(f'{decision.get("code")}: recorded {decision.get("action")}, persisted {state}')
    return Result(doc_id, '-', 'decisions.persisted', 'fail' if wrong else 'pass',
                  str(wrong) if wrong else f'{len(recorded)} recorded decision(s) match the snapshot')


# --- driver ---------------------------------------------------------------------

def load_api(evidence_dir: Path, doc: dict, api_dir: Path | None) -> tuple[dict | None, str]:
    candidates = []
    if api_dir and doc.get('encounter_id'):
        candidates.append(api_dir / f'{doc["encounter_id"]}.json')
    snapshots = doc.get('api_snapshots') or {}
    candidates += [evidence_dir / snapshots[key] for key in ('final', 'after_reload') if snapshots.get(key)]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding='utf-8')), str(path)
    return None, ''


def verify_document(evidence_dir: Path, doc: dict, api_dir: Path | None) -> list[Result]:
    doc_id = doc.get('id', '?')
    downloads = doc.get('downloads') or []
    if not downloads:
        return [Result(doc_id, '-', 'downloads', 'incomplete', 'the evidence records no downloads')]
    api, source = load_api(evidence_dir, doc, api_dir)
    out = []
    if api is None:
        out.append(Result(doc_id, '-', 'api.snapshot', 'incomplete', 'no encounter JSON found'))
    else:
        out.append(Result(doc_id, '-', 'api.snapshot', 'pass', source))
        if doc.get('encounter_id') and api.get('id') != doc['encounter_id']:
            out.append(Result(doc_id, '-', 'api.snapshot.encounter', 'fail',
                              f'snapshot is for {api.get("id")}, evidence names {doc["encounter_id"]}'))
        out.extend(check_api_evidence(doc_id, api))
        out.append(_decisions_match(doc_id, doc, api))
    listed = {r.get('id'): r.get('sha256') for r in (api or {}).get('reports', [])}
    for download in downloads:
        kind, fmt = download.get('kind'), download.get('fmt')
        name = f'{kind}.{fmt}'
        path = evidence_dir / download.get('path', '')
        if not download.get('path') or not path.is_file():
            out.append(Result(doc_id, name, 'file', 'fail', f'downloaded file missing: {path}'))
            continue
        data = path.read_bytes()
        out.extend(check_hashes(doc_id, name, data, download, listed))
        if kind not in ('draft', 'reviewed') or fmt not in ('txt', 'csv'):
            out.append(Result(doc_id, name, 'format', 'fail', f'unknown report {kind!r}/{fmt!r}'))
            continue
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError as exc:
            out.append(Result(doc_id, name, 'utf8', 'fail', str(exc)))
            continue
        out.extend(check_txt(doc_id, name, text, kind, api) if fmt == 'txt' else
                   check_csv(doc_id, name, text, kind, api))
    return out


def exit_status(results: list[Result]) -> int:
    if any(r.status == 'fail' for r in results):
        return 1
    return 2 if any(r.status == 'incomplete' for r in results) else 0


def print_table(results: list[Result], stream=None) -> None:
    stream = stream or sys.stdout
    fields = (('DOC', 'doc'), ('REPORT', 'report'), ('CHECK', 'check'), ('STATUS', 'status'))
    widths = [max([len(h)] + [len(getattr(r, f)) for r in results]) for h, f in fields]
    print('  '.join(h.ljust(w) for (h, _), w in zip(fields, widths)) + '  DETAIL', file=stream)
    for r in results:
        cells = (r.doc, r.report, r.check, r.status.upper())
        print('  '.join(c.ljust(w) for c, w in zip(cells, widths)) + '  ' + r.detail, file=stream)
    counts = {s: sum(1 for r in results if r.status == s) for s in ('pass', 'warn', 'fail', 'incomplete')}
    print(f'\n{len(results)} checks: ' + ', '.join(f'{v} {k}' for k, v in counts.items()), file=stream)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--api-dir', type=Path, help='directory of <encounter id>.json API snapshots')
    parser.add_argument('--only', help='comma-separated document ids')
    parser.add_argument('--json-out', type=Path, help='also write the results as JSON')
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'verify_downloads: cannot read the evidence: {exc}', file=sys.stderr)
        return 2
    only = {s.strip() for s in args.only.split(',')} if args.only else None
    documents = [d for d in evidence.get('documents', []) if only is None or d.get('id') in only]
    results = [] if documents else [Result('-', '-', 'documents', 'incomplete', 'no documents selected')]
    for doc in documents:
        results.extend(verify_document(args.evidence.parent, doc, args.api_dir))
    print_table(results)
    if args.json_out:
        args.json_out.write_text(json.dumps([asdict(r) for r in results], indent=2) + '\n', encoding='utf-8')
    return exit_status(results)


if __name__ == '__main__':
    sys.exit(main())
