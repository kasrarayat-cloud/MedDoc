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

The report format is studio/reports.py ('cpt-studio-report@4'); the item-list
rules below mirror its _list_for. When the format changes, change these
constants and expected_list with it; never loosen a check to fit.

Format @4 adds, and these are checked only in a file that names that format:
  TXT      CODING COMPLETENESS states the encounter's coding state the API
           reports; UNRESOLVED DOCUMENTED SERVICES lists exactly the persisted
           unresolved items; CONFLICTS IN THE RECORD lists every persisted
           conflict; every source passage CPT Studio selected quotes the
           revision text exactly at its offsets
  CSV      one coding_completeness row with the API's state; one
           unresolved_service row per persisted unresolved item and one
           conflict row per persisted conflict; every source passage of a
           proposal row is the API's and quotes the revision text exactly

The Gemini migration's new path (cpt-studio/design: FINAL.md 4.3, 8.3), read
where the encounter JSON's assessment is the events engine's: its services
record is a stub with no service, conflict or act (so no conflict entry is
listed and no act's evidence is quoted: the anchors are support.source), and a
contradiction is one line, the detail of its 'services.conflicts' check.

And only where the encounter JSON records it: a bounded second review (its
Origin lines, alternatives and usage entry), and a member date conflict's hold
(PROVIDER USAGE lists it as recorded with nothing sent, no usage and no hashes,
beside every other persisted run with its state, usage and hashes).

harness@2 (cpt-studio/HARNESS.md 12.6), only where a file or the encounter
JSON carries it, so every other report is read exactly as before:
  TXT      every passage printed in CONFIRMED FINDINGS and PEER REVIEW quotes
           the revision text exactly at its offsets; CONFIRMED FINDINGS lists
           exactly the persisted confirmations of the revision (by id)
  CSV      the rows that are not proposals (confirmed_finding, peer_answer,
           peer_position, peer_additional_code, participant_reference) are
           never read as items; every passage in their evidence quotes the
           revision text exactly; the confirmed_finding rows name exactly the
           persisted confirmations
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
# The breaks str.splitlines splits a value at, as reports._join splits it: \r\n is ONE break (txt_printed).
TXT_VALUE_BREAK = re.compile('\r\n|[\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]')
CONTROL = re.compile('[\x00-\x08\x0e-\x1f\x7f-\x9f]')
HEX64 = re.compile(r'\b[0-9a-f]{64}\b', re.I)
UUID = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.I)
RULE_LINE = re.compile(r'^[\s=\-_*~─━—]+$')
OPTIONAL_HASHES = ('refetch_sha256', 'header_sha256')  # recorded when the browser verifier could take them
FORMULA_START = ('=', '+', '-', '@', '\t', '\r')
FORMULA_START_EXTRA = ('\n', '＝', '＋', '－', '＠')  # LF and fullwidth forms: warned, not required
ITEM_LISTS = ('approved', 'rejected', 'undecided', 'excluded', 'alternative')
ENCOUNTER_LISTS = ('coding_completeness', 'unresolved_service', 'conflict')  # rows that are not proposals (@4)
# harness@2's rows that are not proposals (reports.HARNESS2_LISTS): never items, read only by _csv_harness2
HARNESS2_LISTS = ('confirmed_finding', 'peer_answer', 'peer_position', 'peer_additional_code', 'participant_reference')
FORMAT_4 = 'cpt-studio-report@4'
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
    'status': ('status',),
    'family': ('family',),
    'documented_service': ('documented_service',),
    'exclusion_reason': ('exclusion_reason',),
    'source_passages': ('source_passages',),
    'proposal_origin': ('proposal_origin',),
    'checks': ('checks',),  # harness@2: a confirmed_finding row's ids
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


def txt_printed(text: str) -> str:
    """``text`` exactly as a customer TXT prints it inside a quotation - reports._join's one rule for a line break in a
    value: split where str.splitlines splits it, each part's controls escaped (reports._visible), and every part after
    the first on a line of its own, CONTINUATION deep unless it already starts that deep, when it is printed as it is.

    So a printed line seven to thirteen spaces deep reads two ways (a part that had seven fewer spaces, or one that had
    exactly as many), and a quotation is never read back by stripping a fixed indent: the passage it is compared with is
    printed as the writer prints it, and the two must be equal (refutation round 3, B-04: stripping seven spaces read a
    passage line the document indents eight spaces back with one, and failed the genuine export)."""
    first, *rest = (escaped(part) for part in TXT_VALUE_BREAK.split(text))
    return '\n'.join([first] + [part if part.startswith(CONTINUATION) else CONTINUATION + part for part in rest])


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
    if FORMAT_4 in head:
        out.extend(_txt_documented(doc, name, text, sections, api, revision_text))
        out.extend(_txt_second_review(doc, name, sections, api))
        out.extend(_txt_member_date_hold(doc, name, sections, api))
    out.extend(_txt_harness2(doc, name, sections, api, revision_text))
    return out


# --- the bounded second review (ARCHITECTURE 5.11) ------------------------------------------------------------------
#
# Checked only where the encounter JSON records one (a second-review run or a proposal from it), so every other report
# is read exactly as before. What the renderer says of it must match what is persisted: reports._item_block's Origin
# line on each numbered item from the second review and on no other, reports._alternatives_section's wording of each
# alternative by its origin, and reports._provider_section's one entry per provider run (a second review labelled as
# one) with the usage recorded for that run.

SECOND_REVIEW_ORIGIN_LINE = 'Origin: selected by the provider in the bounded second review of an unresolved service'
ALTERNATIVE_LINE = re.compile(r'^  - (?P<code>\S+) · .*? — (?P<origin>second-review alternative|provider alternative), '
                              r'never selectable(?::|$)')
USAGE_LINE = re.compile(r'^    Usage: (?P<usage>none reported|\{.*\})(?: \((?P<basis>[^()]*)\))?$')
SHA_LINE = re.compile(r'^    Request sha256: (?P<request>\S+) · Response sha256: (?P<response>\S+)$')


def proposal_origin(proposal: dict) -> str:
    return (proposal.get('support') or {}).get('origin') or 'primary'


def has_second_review(api: dict) -> bool:
    proposals = ((api.get('assessment') or {}).get('proposals')) or []
    return (any(proposal_origin(p) == 'second_review' for p in proposals)
            or any(run.get('purpose') == 'second_review' for run in api.get('provider_runs') or []))


def _run_key(second: bool, usage: str, request: str, response: str) -> tuple:
    return ('second_review' if second else 'primary', usage, request, response)


def _txt_second_review(doc, name, sections, api) -> list[Result]:
    if not has_second_review(api):
        return []
    proposals = ((api.get('assessment') or {}).get('proposals')) or []
    body = {heading: lines for heading, lines in sections}
    out = []
    # 1. the Origin line: on every numbered item the second review added, and on no other
    second = {str(p.get('code')) for p in proposals if proposal_origin(p) == 'second_review' and p.get('bucket') != 'alternative'}
    marked, numbered = set(), set()
    for heading, lines in sections:
        if heading.startswith((APPROVED_HEADING, 'UNDECIDED')):
            for code, block in item_blocks(lines):
                numbered.add(code)
                if any(line.strip() == SECOND_REVIEW_ORIGIN_LINE for line in block):
                    marked.add(code)
    want = second & numbered
    out.append(Result(doc, name, 'txt.second_review.origin', 'pass' if marked == want else 'fail',
                      f'{len(marked)} numbered item(s) say they came from the second review, as persisted'
                      if marked == want else f'Origin line on {sorted(marked)}; the second review added {sorted(want)}'))
    # 2. every alternative of the provider's worded by its origin. A harness participant's alternative (origin
    # 'participant') is worded as its participant's ('proposed by ...' or 'listed by ...'), never as the provider's or
    # the second review's, so it is not counted here - and a participant alternative worded as either would add a line
    # nothing expects, which fails (walk-tool repair W1: it was expected as a 'provider alternative' and failed a
    # right report)
    heading = next((h for h in body if h.startswith('ALTERNATIVES')), None)
    seen = Counter()
    for line in body.get(heading, []) if heading else []:
        match = ALTERNATIVE_LINE.match(line)
        if match:
            seen[(match.group('code'), match.group('origin'))] += 1
    expected = Counter((str(p.get('code')), 'second-review alternative' if proposal_origin(p) == 'second_review'
                        else 'provider alternative') for p in proposals
                       if p.get('bucket') == 'alternative' and proposal_origin(p) != 'participant')
    out.append(Result(doc, name, 'txt.second_review.alternatives', 'pass' if seen == expected else 'fail',
                      f'{sum(seen.values())} alternative(s), each worded by its origin' if seen == expected else
                      f'listed {sorted(seen.items())}; persisted {sorted(expected.items())}'))
    # 3. PROVIDER USAGE: one entry per run, the second review labelled as one, with the usage recorded for it
    entries, current = [], None
    for line in body.get('PROVIDER USAGE', []):
        if line.startswith('  - '):
            current = {'second': ' · bounded second review' in line, 'usage': None, 'request': None, 'response': None}
            entries.append(current)
        elif current is not None:
            usage, shas = USAGE_LINE.match(line), SHA_LINE.match(line)
            if usage:
                current['usage'] = usage.group('usage')
            elif shas:
                current['request'], current['response'] = shas.group('request'), shas.group('response')
    listed = Counter(_run_key(e['second'], e['usage'], e['request'], e['response']) for e in entries)
    persisted = Counter(_run_key(run.get('purpose') == 'second_review',
                                 json.dumps(run['usage'], sort_keys=True, ensure_ascii=False) if run.get('usage')
                                 else 'none reported', run.get('request_sha256') or 'none',
                                 run.get('response_sha256') or 'none') for run in api.get('provider_runs') or [])
    out.append(Result(doc, name, 'txt.second_review.provider_usage', 'pass' if listed == persisted else 'fail',
                      f'{sum(listed.values())} provider run(s) listed with their recorded usage '
                      f'({sum(n for key, n in persisted.items() if key[0] == "second_review")} second review)'
                      if listed == persisted else
                      f'listed {sorted(listed.items())}; persisted {sorted(persisted.items())}'))
    return out


# --- a member date conflict's hold (session interpretation 19) --------------------------------------------------------
#
# Checked only where the encounter JSON records one, so every other report is read exactly as before. The API serves no
# run scope; the run's error names the hold, because only jobs._member_date_hold writes studio/jobs.py's
# MEMBER_DATE_CONFLICT_MESSAGE (and always with scope {'held': 'member_date_conflict'}). reports._provider_section must
# list it as recorded, not requested, with nothing sent, no usage and no hashes, beside every other persisted run.

MEMBER_DATE_HOLD_MESSAGE = ('Nothing was sent: the service date entered as encounter metadata differs from the '
                            'documented one. Correct or clear the metadata (or add an addendum), and the request is '
                            'made for the agreed date.')
HOLD_WORDING = ' · nothing was sent: the service date entered as encounter metadata conflicts with the document'


def is_member_date_hold(run: dict) -> bool:
    return ((run.get('purpose') or 'primary') == 'primary' and run.get('state') == 'not_sent'
            and not run.get('request_sha256') and run.get('error') == MEMBER_DATE_HOLD_MESSAGE)


def _provider_entries(lines) -> list[dict]:
    """PROVIDER USAGE as reports._provider_section writes it: '  - provider · mode · state · ...' per run, then its
    Usage and sha256 lines."""
    entries, current = [], None
    for line in lines:
        if line.startswith('  - '):
            fields = line[4:].split(' · ')
            current = {'head': line, 'fields': fields, 'state': fields[2] if len(fields) > 2 else '',
                       'usage': None, 'request': None, 'response': None}
            entries.append(current)
        elif current is not None:
            usage, shas = USAGE_LINE.match(line), SHA_LINE.match(line)
            if usage:
                current['usage'] = usage.group('usage')
            elif shas:
                current['request'], current['response'] = shas.group('request'), shas.group('response')
    return entries


def _txt_member_date_hold(doc, name, sections, api) -> list[Result]:
    runs = api.get('provider_runs') or []
    holds = [run for run in runs if is_member_date_hold(run)]
    if not holds:
        return []
    entries = _provider_entries(dict(sections).get('PROVIDER USAGE', []))
    worded = [e for e in entries if e['head'].endswith(HOLD_WORDING)]
    right = [e for e in worded if e['state'] == 'not_sent' and e['usage'] == 'none reported' and e['request'] == 'none'
             and e['response'] == 'none' and any(f.startswith('recorded ') for f in e['fields'])
             and not any(f.startswith(('requested ', 'HTTP ')) for f in e['fields'])]
    listed = Counter((e['state'], e['usage'], e['request'], e['response']) for e in entries)
    persisted = Counter((run.get('state'), json.dumps(run['usage'], sort_keys=True, ensure_ascii=False)
                         if run.get('usage') else 'none reported', run.get('request_sha256') or 'none',
                         run.get('response_sha256') or 'none') for run in runs)
    ok = len(right) == len(worded) == len(holds)
    return [
        Result(doc, name, 'txt.member_date_hold.listed', 'pass' if ok else 'fail',
               f'{len(holds)} hold(s) listed as recorded with nothing sent, no usage and no hashes' if ok else
               f'{len(holds)} hold(s) persisted; {len(worded)} entry(ies) say nothing was sent for the member date, '
               f'{len(right)} of them as recorded with no usage and no hashes'),
        Result(doc, name, 'txt.member_date_hold.provider_usage', 'pass' if listed == persisted else 'fail',
               f'{sum(listed.values())} provider run(s) listed with their recorded state, usage and hashes'
               if listed == persisted else f'listed {sorted(listed.items())}; persisted {sorted(persisted.items())}'),
    ]


SOURCE_OPENER = '       + source passage selected by CPT Studio: '  # reports._item_block, at CONTINUATION depth


def _txt_documented(doc, name, text, sections, api, revision_text) -> list[Result]:
    state, unresolved, conflicts, _ = _documented_expected(api)
    body = {heading: lines for heading, lines in sections}
    coding = body.get('CODING COMPLETENESS', [])
    out = [Result(doc, name, 'txt.coding_completeness',
                  'pass' if any(line.strip() == f'State: {state}' for line in coding) else 'fail',
                  f'states the API coding state {state!r}' if any(line.strip() == f'State: {state}' for line in coding)
                  else f'CODING COMPLETENESS does not state {state!r}')]
    heading = next((h for h in body if h.startswith('UNRESOLVED DOCUMENTED SERVICES')), None)
    lines = body.get(heading, []) if heading else []
    listed = {line[4:].rsplit(' [', 1)[0] for line in lines if line.startswith('  - ') and ' [' in line}
    expected = {label for _, label in unresolved}
    ok = heading is not None and listed == expected
    out.append(Result(doc, name, 'txt.unresolved', 'pass' if ok else 'fail',
                      f'{len(listed)} unresolved item(s) listed, as persisted' if ok else
                      f'section {"missing" if heading is None else "differs"}: listed {sorted(listed)}, persisted '
                      f'{sorted(expected)}'))
    conflict_lines = body.get('CONFLICTS IN THE RECORD', [])
    if events_engine(api):
        out.append(_txt_event_conflicts(doc, name, conflict_lines, api))
    else:
        named = {(line.split('(', 1)[1].split(')', 1)[0], line[4:].split(' (', 1)[0].replace(' ', '_'))
                 for line in conflict_lines if line.startswith('  - ') and '(' in line}
        out.append(Result(doc, name, 'txt.conflicts', 'pass' if named == conflicts else 'fail',
                          f'{len(named)} conflict(s) listed, as persisted' if named == conflicts else
                          f'listed {sorted(named)}, persisted {sorted(conflicts)}'))
    # A passage over several lines is one entry (the renderer continues it at nine spaces and closes it on its last
    # line), read like an evidence entry; an opener with no closing citation cannot be checked and fails.
    entries, unclosed = scan_entries(text.splitlines(), SOURCE_OPENER, SOURCE_OPENER)
    wrong = [f'{start}-{end}' for entry, start, end in entries if not quotes_exactly(entry, start, end, revision_text)]
    wrong += ['a source passage line with no closing citation'] * unclosed
    out.append(Result(doc, name, 'txt.source_passages', 'fail' if wrong else 'pass',
                      f'source passages that do not quote the revision text at their offsets: {wrong}' if wrong
                      else f'{len(entries)} source passage(s) quote the revision text exactly at their offsets'))
    return out


LEGACY_CONFLICT_END = '; both sides kept, neither chosen:'  # reports._conflicts_section's line of a stored conflict
EVENT_CONFLICTS_HEAD = 'Conflicting statements'  # every services.conflicts warning's detail starts so (assess.py)


def _txt_event_conflicts(doc, name, lines, api) -> Result:
    """CONFLICTS IN THE RECORD of a new-path assessment: the services.conflicts check's detail as its one line where the
    check warns, and no conflict entry of a stored services record - the stub stores none - nor a warning the check does
    not make (reports._conflicts_section over reports._event_services)."""
    note = conflict_note(api)
    entries = [line for line in lines if line.startswith('  - ')]
    stored = [line for line in entries if line.endswith(LEGACY_CONFLICT_END)]
    worded = [line for line in entries if line[4:].startswith(EVENT_CONFLICTS_HEAD)]
    want = [f'  - {note}'] if note else []
    ok = not stored and worded == want
    return Result(doc, name, 'txt.conflicts', 'pass' if ok else 'fail',
                  ('the services.conflicts warning is listed, as recorded' if note else 'no conflict listed, none recorded')
                  if ok else f'listed {worded + stored}; recorded {want or "no conflict"}')


# --- harness@2 (cpt-studio/HARNESS.md 12.6) -------------------------------------------------------------------------
#
# Checked only where the file carries the sections or rows, or the encounter JSON a confirmation, so every other report
# is read exactly as before. The renderer prints a confirmed finding's passage as '    Passage: "..." [chars a–b, page
# n]' and a peer answer's, position's or additional code's as '      "..." [chars a–b, page n]', each continuing at
# CONTINUATION depth; and a confirmation's id on its '    Confirmation: <id> · question <id>' line (the CSV: its checks
# cell 'confirmation=<id>;...').

CONFIRMED_HEADING, PEER_HEADING = 'CONFIRMED FINDINGS', 'PEER REVIEW'
HARNESS2_OPENERS = {CONFIRMED_HEADING: ('    Passage: "', '    Passage: '), PEER_HEADING: ('      "', '      ')}
CONFIRMATION_LINE = re.compile(r'^    Confirmation: (?P<id>[0-9a-f-]{36}) · question ')
CONFIRMATION_CELL = re.compile(r'(?:^|;)confirmation=(?P<id>[0-9a-f-]{36})(?:;|$)')


def _api_confirmations(api) -> set:
    return {str(item.get('id')) for item in (api or {}).get('confirmations') or [] if isinstance(item, dict)}


def _txt_harness2(doc, name, sections, api, revision_text) -> list[Result]:
    body = {heading: lines for heading, lines in sections}
    persisted = _api_confirmations(api)
    out = []
    if CONFIRMED_HEADING in body or PEER_HEADING in body:
        entries, unclosed = [], 0
        for heading, (opener, prefix) in HARNESS2_OPENERS.items():
            found, missing_close = scan_entries(body.get(heading, []), opener, prefix)
            entries += found
            unclosed += missing_close
        wrong = [f'{start}-{end}' for entry, start, end in entries if not quotes_exactly(entry, start, end,
                                                                                         revision_text)]
        wrong += ['a passage line with no closing citation'] * unclosed
        out.append(Result(doc, name, 'txt.harness2_passages', 'fail' if wrong else 'pass',
                          f'passages that do not quote the revision text at their offsets: {wrong}' if wrong
                          else f'{len(entries)} passage(s) quote the revision text exactly at their offsets'))
    if CONFIRMED_HEADING in body or persisted:
        listed = {m.group('id') for line in body.get(CONFIRMED_HEADING, []) for m in [CONFIRMATION_LINE.match(line)]
                  if m}
        ok = CONFIRMED_HEADING in body and listed == persisted
        out.append(Result(doc, name, 'txt.confirmed_findings', 'pass' if ok else 'fail',
                          f'{len(listed)} confirmation(s) listed, as persisted' if ok else
                          f'section {"missing" if CONFIRMED_HEADING not in body else "differs"}: listed '
                          f'{sorted(listed)}, persisted {sorted(persisted)}'))
    return out


def _csv_harness2(doc, name, rows, columns, api, revision_text) -> list[Result]:
    persisted = _api_confirmations(api)
    if not rows and not persisted:
        return []
    wrong = []
    for row in rows:
        cell = _cell(row, columns, 'evidence')
        for match in CSV_EVIDENCE_OFFSETS.finditer(cell):
            start, end = int(match.group(1)), int(match.group(2))
            passage = cp_slice(revision_text, start, end)
            if passage is None or not cell[:match.start()].endswith(f'"{escaped(passage)}" '):
                wrong.append(f'{start}-{end}')
    named = {m.group('id') for row in rows if norm_list(row[columns['item_list']]) == 'confirmed_finding'
             for m in [CONFIRMATION_CELL.search(_cell(row, columns, 'checks'))] if m}
    return [Result(doc, name, 'csv.harness2_passages', 'fail' if wrong else 'pass',
                   f'offsets not quoting the revision text: {wrong}' if wrong
                   else f'{len(rows)} harness@2 row(s); every passage quotes the revision text exactly'),
            Result(doc, name, 'csv.confirmed_findings', 'pass' if named == persisted else 'fail',
                   f'{len(named)} confirmed_finding row(s), as persisted' if named == persisted else
                   f'rows name {sorted(named)}, persisted {sorted(persisted)}')]


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


def scan_entries(lines, opener, prefix) -> tuple[list[tuple[str, int, int]], int]:
    """(entries, unclosed): each entry is (text, start, end) for an opener line and every continuation line up to the
    next opener. Its offsets are its LAST line that ends like a citation: a passage line that happens to end in
    '" [chars 1-2]' is text, and the renderer's closing bracket comes after it (round 3, orchestrator:1). ``unclosed``
    counts openers with no closing citation at all, which the renderer never writes."""
    entries: list[tuple[str, int, int]] = []
    runs, current = [], None
    for line in lines:
        if line.startswith(opener):
            current = [line]
            runs.append(current)
        elif current is not None and line.startswith(CONTINUATION):
            current.append(line)
        else:
            current = None
    unclosed = 0
    for run in runs:
        ends = [i for i, line in enumerate(run) if TXT_EVIDENCE_END.search(line)]
        if not ends:
            unclosed += 1
            continue
        match = TXT_EVIDENCE_END.search(run[ends[-1]])
        text = [run[0][len(prefix):]] + [line.strip() for line in run[1:ends[-1] + 1]]
        entries.append(('\n'.join(text), int(match.group(1)), int(match.group(2))))
    return entries, unclosed


def quotes_exactly(entry: str, start: int, end: int, revision_text: str) -> bool:
    """The WHOLE quoted text before the entry's structural bracket is the revision text at its offsets: a prefix test
    let anything, an inner bracket with a wrong end offset included, stand between the passage and the bracket read
    (round 4, pipeline:4). The closing quote stays in the comparison, so a space before it is not collapsed away."""
    passage = cp_slice(revision_text, start, end)
    flat = collapse(entry)
    tail = TXT_EVIDENCE_END.search(flat)
    quoted = collapse(flat[:tail.start()] + '"') if tail else None
    return passage is not None and quoted == collapse(f'"{txt_shown(passage)}"')


def _evidence_entries(sections, kind) -> list[tuple[str, int, int]]:
    """(entry text, start, end) for each evidence entry printed where the renderer prints one: after an item
    block's '     Evidence:' line (up to the block's next field), and '    Evidence: "' lines in ENCOUNTER CONTEXT.
    A passage that continues over several lines is one entry; its offsets are its closing bracket."""
    entries: list[tuple[str, int, int]] = []

    def scan(lines, opener, prefix):
        entries.extend(scan_entries(lines, opener, prefix)[0])

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
    wrong = [f'{start}-{end}' for entry, start, end in _evidence_entries(sections, kind)
             if not quotes_exactly(entry, start, end, revision_text)]
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
    encounter_rows = [row for row in rows if 'item_list' in columns
                      and norm_list(row[columns['item_list']]) in ENCOUNTER_LISTS]
    harness2_rows = [row for row in rows if 'item_list' in columns
                     and norm_list(row[columns['item_list']]) in HARNESS2_LISTS]
    items_rows = [row for row in rows if not ('item_list' in columns and norm_list(row[columns['item_list']])
                                              in ('none',) + ENCOUNTER_LISTS + HARNESS2_LISTS)]
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
    if 'source_passages' in columns:
        out.extend(_csv_documented(doc, name, encounter_rows, items_rows, columns, api, revision_text))
    if has_second_review(api):
        out.append(_csv_second_review(doc, name, items_rows, columns, api))
    out.extend(_csv_harness2(doc, name, harness2_rows, columns, api, revision_text))
    return out


def _csv_second_review(doc, name, items_rows, columns, api) -> Result:
    """Each proposal row's proposal_origin is the persisted origin (reports: 'second_review', 'primary' for a primary
    proposal with support, '' for one without), so a code from the second review never reads as the provider's own."""
    if 'proposal_origin' not in columns or 'proposal_id' not in columns:
        return Result(doc, name, 'csv.second_review.origin', 'fail', 'no proposal_origin or proposal_id column')
    proposals = {str(p['id']): p for p in ((api.get('assessment') or {}).get('proposals')) or []}
    wrong = []
    for row in items_rows:
        proposal = proposals.get(undo_neutralisation(row[columns['proposal_id']]).strip())
        if proposal is None:
            continue  # _csv_items reports rows that are not persisted proposals
        support = proposal.get('support') or {}
        want = support.get('origin', '') or ('primary' if support else '')
        got = undo_neutralisation(row[columns['proposal_origin']]).strip()
        if got != want:
            wrong.append(f'{proposal.get("code")}: {got!r} != {want!r}')
    return Result(doc, name, 'csv.second_review.origin', 'fail' if wrong else 'pass',
                  str(wrong) if wrong else f'{len(items_rows)} row(s) carry their persisted origin')


# The Gemini migration's new path (design/FINAL.md 4.3, 8.3): an assessment the events engine made
# (interpretation.is_new_assessment: its engine label) carries the stub services record - no service, conflict or act -
# and words a contradiction in its encounter check 'services.conflicts', which reports._event_services prints as the one
# line of CONFLICTS IN THE RECORD (conflict_note).
EVENTS_ENGINE = 'cpt-studio-events@'
CONFLICTS_CHECK = 'services.conflicts'


def events_engine(api: dict) -> bool:
    """Whether the encounter JSON's assessment was made by the events engine (the new path)."""
    return str(((api or {}).get('assessment') or {}).get('engine_version') or '').startswith(EVENTS_ENGINE)


def conflict_note(api: dict) -> str:
    """The new path's line of CONFLICTS IN THE RECORD (reports._event_services' conflict_note): the detail of the
    assessment's 'services.conflicts' check where it warns; '' where it does not, or for a legacy assessment."""
    if not events_engine(api):
        return ''
    for check in (api.get('assessment') or {}).get('encounter_checks') or []:
        if isinstance(check, dict) and check.get('id') == CONFLICTS_CHECK and check.get('status') == 'warn':
            return str(check.get('detail') or '')
    return ''


def _documented_expected(api: dict):
    """(coding state, {(service, label)} unresolved, {(service, subject)} conflicts, {proposal id: [source spans]})
    as the encounter JSON persists them. A new-path assessment persists no conflict entry (its stub's list is empty and
    nothing else is read as one): its contradictions are conflict_note's one line."""
    assessment = api.get('assessment') or {}
    completeness = assessment.get('completeness') or {}
    inventory = assessment.get('services') or {}
    unresolved = {(u.get('service', ''), u.get('label', '')) for u in completeness.get('unresolved_items') or []}
    conflicts = set() if events_engine(api) else {(c.get('service', ''), c.get('subject', ''))
                                                  for c in inventory.get('conflicts') or []}
    sources = {p.get('id'): list((p.get('support') or {}).get('source') or []) for p in assessment.get('proposals') or []}
    return ((api.get('coding') or {}).get('state'), unresolved, conflicts, sources)


def _csv_documented(doc, name, encounter_rows, items_rows, columns, api, revision_text) -> list[Result]:
    state, unresolved, conflicts, sources = _documented_expected(api)
    coding = [row for row in encounter_rows if norm_list(row[columns['item_list']]) == 'coding_completeness']
    written_state = [_cell(row, columns, 'status').strip() for row in coding]
    out = [Result(doc, name, 'csv.coding_completeness', 'pass' if written_state == [state] else 'fail',
                  f'coding_completeness rows {written_state}; API state {state!r}')]
    written_unresolved = {(_cell(row, columns, 'documented_service').strip(), _cell(row, columns, 'exclusion_reason'))
                          for row in encounter_rows if norm_list(row[columns['item_list']]) == 'unresolved_service'}
    out.append(Result(doc, name, 'csv.unresolved', 'pass' if written_unresolved == unresolved else 'fail',
                      f'{len(written_unresolved)} unresolved row(s) equal the persisted unresolved items'
                      if written_unresolved == unresolved else
                      f'persisted not written: {sorted(unresolved - written_unresolved)}; written not persisted: '
                      f'{sorted(written_unresolved - unresolved)}'))
    written_conflicts = {(_cell(row, columns, 'documented_service').strip(), _cell(row, columns, 'status').strip())
                         for row in encounter_rows if norm_list(row[columns['item_list']]) == 'conflict'}
    out.append(Result(doc, name, 'csv.conflicts', 'pass' if written_conflicts == conflicts else 'fail',
                      f'{len(written_conflicts)} conflict row(s) equal the persisted conflicts'
                      if written_conflicts == conflicts else
                      f'persisted {sorted(conflicts)}; written {sorted(written_conflicts)}'))
    wrong, missing = [], []
    for row in items_rows + [r for r in encounter_rows if norm_list(r[columns['item_list']]) == 'unresolved_service']:
        cells = [(_cell(row, columns, 'source_passages'))] + (
            [_cell(row, columns, 'evidence')] if norm_list(row[columns['item_list']]) == 'unresolved_service' else [])
        for cell in cells:
            for match in CSV_EVIDENCE_OFFSETS.finditer(cell):
                start, end = int(match.group(1)), int(match.group(2))
                passage = cp_slice(revision_text, start, end)
                if passage is None or not cell[:match.start()].endswith(f'"{escaped(passage)}" '):
                    wrong.append(f'{start}-{end}')
    for row in items_rows:
        pid = _cell(row, columns, 'proposal_id').strip() if 'proposal_id' in columns else ''
        cell = _cell(row, columns, 'source_passages')
        for span in sources.get(pid, []):
            if f'"{escaped(span.get("text", ""))}" [{span.get("start")}-{span.get("end")}]' not in cell:
                missing.append(f'{pid}[{span.get("start")}:{span.get("end")}]')
    out.append(Result(doc, name, 'csv.source_passages', 'fail' if (wrong or missing) else 'pass',
                      f'offsets not quoting the revision text: {wrong}; API source passages missing: {missing}'
                      if (wrong or missing) else 'every source passage is the API\'s and quotes the revision text'))
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


# --- customer reports (cpt-studio-customer-report@1; cpt-studio/CORE-UX-DESIGN.md section 5) ------------------------
#
# A customer report is checked against the OPERATOR view of the encounter (today's full encounter view, as
# GET /ops/api/encounters/<id> serves it): --api-dir/<encounter id>.json when given, otherwise the operator snapshot the
# evidence names (operator_snapshots) - never the customer API the browser session read, which is what is being
# verified. A draft's statuses are the view's statement of the customer page (each listed code's 'customer':
# serializers.customer_codes; refutation round 3, B-02), never re-derived from the overlay's facts; where the view
# states none, the status check cannot run (incomplete). The grammar read here is the one studio/reports.py writes
# (render_customer_txt, render_customer_csv), and the committed samples under ops/verification/samples are that
# renderer's own bytes (tests/test_cux_r2_reports.py pins them; refutation round 2, L3-1: the checks once read a grammar
# the server never wrote, so every genuine export failed): when the format changes, change it there and here together;
# never loosen a check to fit.
#
# TXT, as reports.render_customer_txt writes it:
#     SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS
#     CPT STUDIO — APPROVED CODES | CPT STUDIO — SUGGESTED CODES — NOT APPROVED
#     [Agent-executed synthetic review — not clinical approval]       when agent review took part in a listed approval
#     Report format: cpt-studio-customer-report@1
#     Encounter: <title>
#     Date of service: <YYYY-MM-DD> | not established
#     Generated: <ISO time> by <label>
#
#     Approved codes | Suggested codes — not approved
#     N. CODE — units U — modifiers: M[, M] | none                     approved; a draft: N. CODE — <status> — units ...
#        Approved by <label> (<agent|human>) at <ISO time>             approved only
#        Agent-executed synthetic review — not clinical approval       an approval agent review took part in
#        <the draft's other review label, when it has one>
#        <one sentence>
#        Quote: "<passage>" (page P, characters S–E)                   a draft: (page P), or (page not known)
#
#     Limitations
#     - <limitation>
#
#     SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS
# Item lines at column 0, detail lines at three spaces; a line break inside any value continues on a line indented seven
# spaces (reports.CONTINUATION), so stored text never starts an item, a detail or a heading - and a part of the value
# that already starts seven spaces deep is printed as it is, so a quotation's passage is compared as txt_printed prints
# it, never read back by stripping seven spaces (refutation round 3, B-04).
#
# CSV, as reports.render_customer_csv writes it: the header row (CUSTOMER_CSV_COLUMNS), a banner row (report_format =
# the SYNTHETIC line, every other cell empty), one row per quotation of each code (a code with none has one row with
# empty evidence cells), and the banner row again last.

CUSTOMER_FORMAT = 'cpt-studio-customer-report@1'
CUSTOMER_KINDS = ('draft', 'approved')
CUSTOMER_DRAFT_HEADLINE = re.compile(r'\bSUGGESTED\s+CODES\s*[-–—:]+\s*NOT\s+APPROVED\b', re.I)
CUSTOMER_APPROVED_HEADLINE = re.compile(r'\bAPPROVED\s+CODES\b', re.I)
CUSTOMER_STATUS_LABELS = {'ready': 'Ready for review', 'needs_detail': 'Needs a detail', 'approved': 'Approved',
                          'excluded': 'Excluded'}
AGENT_SUB_LABEL = 'Agent-executed synthetic review — not clinical approval'
# The reading is strict about what a report says and tolerant only of how a line is laid out: an item line "N. CODE ..."
# at 0-6 spaces carries its units ("units 1", "Units: 1", "1 unit"), modifiers ("modifiers: XS", "Modifier: 59") and,
# in a draft, its status label - read from the item line only, never from a detail line; detail lines at one to six
# spaces; a line at seven or more continues the value above it and is never read as anything of its own; a quotation
# opened by "Quote:" (or "Evidence:", "Source:", a bullet), its passage between the first and the last quote mark, its
# place in a trailing (...) or [...] ("page P", "characters S–E", "chars S-E"); headings at column 0 after a blank line.
CUSTOMER_ITEM_LINE = re.compile(rf'^ {{0,6}}(?P<number>\d+)[.)]\s+(?P<code>{CODE})\b(?P<rest>.*)$')
CUSTOMER_FIELD = re.compile(r'^(?P<name>Report format|Encounter|Date of service|Generated at|Generated by|Generated):\s*'
                            r'(?P<value>.*)$', re.I)
CUSTOMER_GENERATED = re.compile(r'^(?P<at>\S+)\s+by\s+(?P<by>\S.*)$')
CUSTOMER_APPROVER = re.compile(r'^Approved by:?\s*(?P<by>.+?)(?:\s*\((?P<kind>agent|human)\))?\s*(?:\bat\b|\bon\b|·|,)\s*'
                               r'(?P<at>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(?:Z|[+-]\d{2}:?\d{2}|UTC)?)\s*$',
                               re.I)
CUSTOMER_QUOTE_OPEN = re.compile(r'^(?:(?:Quote|Quoted|Evidence|Source|Passage)s?:\s*|[-•*]\s*)"', re.I)
CUSTOMER_QUOTE = re.compile(r'^"(?P<text>.*)"(?:\s*[\[(](?P<where>[^\])]*)[\])])?\s*$', re.S)
CUSTOMER_PAGE = re.compile(r'\b(?:page|p\.)\s*(\d+)\b', re.I)
CUSTOMER_OFFSETS = re.compile(r'\b(?:chars?|characters|offsets?)\s*:?\s*(\d+)\s*(?:[–-]|to)\s*(\d+)\b', re.I)
CUSTOMER_UNITS = re.compile(r'\bunits?\s*:?\s*(\d+)\b|\b(\d+)\s+units?\b', re.I)
CUSTOMER_MODIFIERS = re.compile(r'\bmodifiers?\s*:?\s*(none|[0-9A-Z]{2}(?:\s*[,;/]\s*[0-9A-Z]{2})*)(?![0-9A-Za-z])', re.I)
CUSTOMER_KNOWN_HEADING = re.compile(r'^(?:SUGGESTED\s+CODES\s*[-–—:]+\s*NOT\s+APPROVED|APPROVED\s+CODES|LIMITATIONS)\s*:?$', re.I)
# reports.CUSTOMER_CSV_COLUMNS: CORE-UX-DESIGN.md 5's columns, then review_label (the agent label of a row's approval)
CUSTOMER_CSV_COLUMNS = ('report_format', 'encounter_title', 'date_of_service', 'number', 'code', 'units', 'modifiers', 'status',
                        'approved_by', 'approver_kind', 'approved_at', 'summary', 'evidence_text', 'evidence_page',
                        'evidence_start', 'evidence_end', 'review_label')
CUSTOMER_APPROVAL_CELLS = ('approved_by', 'approver_kind', 'approved_at')
CUSTOMER_QUOTE_CONTINUATION = '       '
ISO_TIMESTAMP_LOOSE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$')
# What a modifier comparison reads where the operator view's decision does not say which modifier was chosen (no
# 'modifiers' on it): the export can be judged neither right nor wrong, so the check could not run (refutation round 2,
# L3-3: read as "none", a dropped modifier passed and the reviewer's chosen one failed).
UNKNOWN = None
_scanner = None


def scanner():
    """ops/scan_customer.py, the stdlib reader of the shared denylist (loaded by path: ops is no package)."""
    global _scanner
    if _scanner is None:
        spec = importlib.util.spec_from_file_location('cpt_verify_downloads_scan', Path(__file__).resolve().parent / 'scan_customer.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault('cpt_verify_downloads_scan', module)
        spec.loader.exec_module(module)
        _scanner = module
    return _scanner


def _proposals(api: dict) -> list:
    return list(((api.get('assessment') or {}).get('proposals')) or [])


def customer_code_rows(api: dict) -> list:
    """The codes a customer report lists, in the contract's order (ops/verify_browser.cjs expectedCodeRows): selected and
    reinstated codes by stored position, then the excluded codes still decidable; never an alternative."""
    proposals = _proposals(api)
    first = [p for p in proposals if p.get('bucket') == 'selected'
             or (p.get('bucket') == 'excluded' and p.get('decision') and p['decision'].get('action') != 'confirm')]
    then = [p for p in proposals if p.get('bucket') == 'excluded' and p not in first
            and (p.get('reinstatable') is True or (p.get('decision') or {}).get('action') == 'confirm')]
    return first + then


def customer_status(p: dict):
    """The customer status the server gives the code - on the page and in a draft - as the operator view states it:
    the proposal's 'customer' (serializers.customer_codes: customer_api.code_rows over the review overlay, the rows the
    page is served; ops/verify_browser.cjs expectedCustomerStatus reads the same). UNKNOWN where the view carries none,
    which nothing is judged against (cannot verify). Never re-derived from the overlay's facts (refutation round 3, B-02:
    the re-derivation read a reinstated code whose needed detail a member answered unavailable - Excluded, revoke only -
    as ready, failing the genuine draft and passing one forged to say "Ready for review")."""
    row = p.get('customer')
    status = row.get('status') if isinstance(row, dict) else None
    return status if isinstance(status, str) and status in CUSTOMER_STATUS_LABELS else UNKNOWN


def agent_reviewed(p: dict) -> bool:
    """Whether the code's current decision is an agent's approval, by the one rule every customer surface labels it by
    (customer_api.agent_approval, refutation round 2 L3-6): exactly when its approver is an agent. A person's approval
    of a code an agent reinstated is the person's (who reinstated it stays in the record, never in the label)."""
    decision = p.get('decision') or {}
    return decision.get('action') == 'approve' and decision.get('reviewer_kind') == 'agent'


def act_index(api: dict) -> dict:
    """CPT Studio's located acts by id, from the operator view's recorded reading (assessment.services), whatever the
    engine - as review.act_index reads it for customer_api._act_index and review.approved_items. A new-path assessment's
    services record is the stub (design/FINAL.md 4.3, 8.3), which carries no act, so its anchors are its support.source
    alone."""
    out = {}
    services = ((api.get('assessment') or {}).get('services') or {}).get('services')
    for service in services if isinstance(services, list) else []:
        for act in (service.get('acts') or []) if isinstance(service, dict) else []:
            if isinstance(act, dict) and isinstance(act.get('id'), str):
                out[act['id']] = act
    return out


def _sliced(span, revision_text: str) -> bool:
    return isinstance(span, dict) and cp_slice(revision_text, span.get('start'), span.get('end')) == span.get('text')


SHOWN_SUPPORT = ('pass', 'warn')  # studio/review.py SHOWN_SUPPORT: the readings a code's passages are quoted under


def allowed_passages(p: dict, revision_text: str, acts: dict | None = None, status: str | None = None) -> tuple[list, list]:
    """(the passages a quotation of the code may be, the passages CPT Studio found unrelated) by the one rule the server
    quotes a code by - the page's "Why this code?" (customer_api._quotes) and the approved export's evidence alike
    (CORE-UX-DESIGN.md 7: CPT Studio's own located passages for the matched act first, then the provider's exact passages
    only when they support; never a passage that does not support, and none for an excluded code):
    - nothing at all unless the support reading records the act as shown ('pass' or 'warn', review.SHOWN_SUPPORT): a
      'not_applicable' reading's source passages are the service's own, which show no act (refutation round 2, L3-7),
      and a 'fail' shows none; then support.source;
    - the evidence CPT Studio's reading recorded for each act the support record names, while that act is stored
      'performed' or 'incomplete';
    - the provider's exact passages (context 0, exact) the support reading found supporting, never one it found unrelated.
    Nothing where no support reading was recorded (L3-10: every exact provider passage was accepted, so a page quoting a
    passage nothing had shown to support the code passed). ``status``: the code's customer status (customer_status);
    an excluded code quotes nothing."""
    exact = {i: s for i, s in enumerate(p.get('evidence') or []) if isinstance(s, dict) and s.get('context_index') == 0
             and s.get('exact') is True and _sliced(s, revision_text)}
    support = p.get('support') if isinstance(p.get('support'), dict) else {}
    unrelated_ids = {i for i in support.get('unrelated') or [] if type(i) is int} if isinstance(support.get('unrelated'), list) else set()
    unrelated = [exact[i] for i in sorted(unrelated_ids) if i in exact]
    reading = support.get('status') if isinstance(support.get('status'), str) else None
    # review.evidence_spans: nothing unless the support reading records the act as shown (SHOWN_SUPPORT)
    if reading not in SHOWN_SUPPORT or status == 'excluded':
        return [], unrelated
    source = [s for s in support.get('source') or [] if _sliced(s, revision_text)]
    own = []
    for act in support.get('acts') or []:
        stored = (acts or {}).get(act.get('id')) if isinstance(act, dict) else None
        if isinstance(stored, dict) and stored.get('status') in ('performed', 'incomplete'):
            own += [s for s in stored.get('evidence') or [] if _sliced(s, revision_text)]
    supporting = support.get('supporting') if isinstance(support.get('supporting'), list) else []
    cited = [exact[i] for i in supporting if type(i) is int and i in exact and i not in unrelated_ids]
    return source + own + cited, unrelated


def page_of(pages, start: int, end: int):
    for item in pages or []:
        if isinstance(item, dict) and isinstance(item.get('start'), int) and item['start'] <= start and end <= item['end']:
            return item.get('page')
    return None


def established_date(api: dict) -> str | None:
    fact = ((api.get('context') or {}).get('facts') or {}).get('service_date') or {}
    value = str(fact.get('value') or '')
    return value if fact.get('origin') in ('document', 'user') and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) else None


def same_instant(a: str, b: str) -> bool:
    """Two timestamps are the same second ('Z', '+00:00', '+0000' and a trailing ' UTC' read alike; no zone is UTC)."""
    def parse(value):
        text = re.sub(r'\s*UTC$', '+00:00', str(value).strip()).replace('Z', '+00:00')
        text = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', text)
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    x, y = parse(a), parse(b)
    return x is not None and y is not None and int(x.timestamp()) == int(y.timestamp())


@dataclass
class CustomerItem:
    number: int
    code: str
    units: str = ''
    modifiers: tuple = ()
    status: str = ''
    approved_by: str = ''
    approver_kind: str = ''
    approved_at: str = ''
    summary: str = ''
    quotes: list = None
    tokens: tuple = ()
    modifiers_seen: bool = False
    agent_label: bool = False  # the item carries the agent-executed synthetic review label
    other_label: str = ''      # a CSV review_label that is not that label


def _decided_modifiers(decision: dict):
    """The modifiers the operator view's decision records - () where none was chosen - or UNKNOWN where it does not say
    (a decision with no 'modifiers' list): fail closed, never read as none."""
    if not decision:
        return ()
    value = decision.get('modifiers', UNKNOWN)
    return tuple(str(m) for m in value) if isinstance(value, list) else UNKNOWN


def customer_truth(api: dict, kind: str) -> list[dict]:
    """What a customer report of ``kind`` must list, from the operator view: each code with its number, units, decided
    modifiers (UNKNOWN where the view does not say), status (customer_status: the server's, UNKNOWN where the view does
    not state it), approver (label, own kind, time), whether agent review took part in its approval, and the passages it
    may quote."""
    revision_text = (api.get('revision') or {}).get('text') or ''
    rows = customer_code_rows(api)
    acts = act_index(api)
    if kind == 'approved':
        rows = [p for p in rows if (p.get('decision') or {}).get('action') == 'approve']
    out = []
    for number, p in enumerate(rows, start=1):
        decision = p.get('decision') or {}
        approve = decision.get('action') == 'approve'
        status = customer_status(p)
        allowed, unrelated = allowed_passages(p, revision_text, acts, status)
        out.append({'number': number, 'id': p.get('id'), 'code': str(p.get('code', '')), 'units': str(p.get('units', '')),
                    'modifiers': _decided_modifiers(decision), 'status': status,
                    'approved_by': decision.get('reviewer', '') if approve else '',
                    'approver_kind': decision.get('reviewer_kind', '') if approve else '',
                    'approved_at': (decision.get('decided_at') or decision.get('created_at') or '') if approve else '',
                    'agent': agent_reviewed(p), 'allowed': allowed, 'unrelated': unrelated})
    return out


def _item_facts(item: 'CustomerItem', line: str) -> None:
    """Units, modifiers and the status label as an item line states them (the first statement of each)."""
    units = CUSTOMER_UNITS.search(line)
    if units and not item.units:
        item.units = units.group(1) or units.group(2)
    modifiers = CUSTOMER_MODIFIERS.search(line)
    if modifiers and not item.modifiers_seen:
        item.modifiers_seen = True
        words = [w for w in re.split(r'[\s,;/]+', modifiers.group(1)) if w]
        item.modifiers = () if [w.lower() for w in words] == ['none'] else tuple(w.upper() for w in words)
    for label in CUSTOMER_STATUS_LABELS.values():
        if not item.status and re.search(rf'(?<![\w-]){re.escape(label)}(?![\w-])', line):
            item.status = label


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(' '))


def parse_customer_txt(text: str) -> dict:
    """The customer TXT, in reports.render_customer_txt's grammar (the comment above CUSTOMER_FORMAT), laid out as the
    comment above CUSTOMER_ITEM_LINE allows: the banner lines, the headline, the header fields and the header's agent
    label, the sections and, in the codes section, the numbered items with their detail lines and quotations. A numbered
    code line anywhere else - before the codes section, in the limitations or in any other section - is a stray item."""
    lines = text.splitlines()
    filled = [line for line in lines if line.strip()]
    out = {'first': filled[0] if filled else '', 'last': filled[-1] if filled else '', 'headline': filled[1] if len(filled) > 1 else '',
           'fields': {}, 'formats': [], 'sections': [], 'items': [], 'limitations': [], 'stray_items': [], 'header_agent': False}
    section = ''
    codes_section = False
    item = None
    entry = None
    names = {name.lower(): name for name in ('Report format', 'Encounter', 'Date of service', 'Generated at', 'Generated by', 'Generated')}

    def close_entry():
        nonlocal entry
        if entry is not None and item is not None:
            # the entry is the quotation as printed - its first line from the opening quote mark, every continued line
            # whole - so 'printed' is the passage exactly as the file prints it, which is what a passage is compared
            # with (txt_printed); 'text' reads it with each continued line's seven-space indent removed, for messages
            match = CUSTOMER_QUOTE.match(entry)
            where = match.group('where') if match else None
            offsets = CUSTOMER_OFFSETS.search(where or '')
            page = CUSTOMER_PAGE.search(where or '')
            printed = match.group('text') if match else None
            item.quotes.append({'raw': entry, 'parsed': bool(match), 'printed': printed,
                                'text': printed.replace('\n' + CUSTOMER_QUOTE_CONTINUATION, '\n') if match else None,
                                'start': int(offsets.group(1)) if offsets else None, 'end': int(offsets.group(2)) if offsets else None,
                                'page': int(page.group(1)) if page else None})
        entry = None

    for index, line in enumerate(lines):
        if entry is not None:
            if line.startswith(CUSTOMER_QUOTE_CONTINUATION):  # a line break inside the passage continues it
                entry += '\n' + line  # whole: how deep it is printed is part of what it says (txt_printed)
                continue
            close_entry()
        if line.startswith(CUSTOMER_QUOTE_CONTINUATION):
            continue  # the continuation of a value above: never an item, a detail, a field or a heading of its own
        field_match = CUSTOMER_FIELD.match(line)
        if field_match and not section:
            name, value = names[field_match.group('name').lower()], field_match.group('value').strip()
            if name == 'Report format':
                out['formats'].append(value)
            elif name == 'Generated':
                generated = CUSTOMER_GENERATED.match(value)
                for field, part in (('Generated at', 'at'), ('Generated by', 'by')):
                    if generated:
                        out['fields'].setdefault(field, generated.group(part).strip())
            else:
                out['fields'].setdefault(name, value)
            continue
        stripped = line.strip()
        if not section and line == stripped and stripped == AGENT_SUB_LABEL:
            out['header_agent'] = True
            continue
        capitals = not re.search(r'[a-z]', line) and len(re.findall(r'[A-Z]', line)) >= 4 and not CODE_TOKEN.search(line)
        heading = (bool(stripped) and line == line.lstrip() and index > 1 and not lines[index - 1].strip()
                   and (capitals or bool(CUSTOMER_KNOWN_HEADING.match(stripped))))
        if heading:
            section = stripped
            out['sections'].append(section)
            codes_section = bool(CUSTOMER_DRAFT_HEADLINE.search(section) or CUSTOMER_APPROVED_HEADLINE.search(section))
            item = None
            continue
        match = CUSTOMER_ITEM_LINE.match(line)
        if match:
            tokens = tuple(token.strip() for token in re.split(r'\s[—·]\s', match.group('rest')) if token.strip())
            found = CustomerItem(number=int(match.group('number')), code=match.group('code'), quotes=[], tokens=tokens)
            _item_facts(found, match.group('rest'))
            if codes_section:
                out['items'].append(found)
                item = found
            else:
                out['stray_items'].append(found)
                item = None
            continue
        if re.match(r'limitations\b', section, re.I):
            bullet = re.match(r'^\s*[-•*]\s+(.*)$', line)
            if bullet:
                out['limitations'].append(bullet.group(1).strip())
            continue
        if item is not None and 1 <= _indent(line) < len(CUSTOMER_QUOTE_CONTINUATION):
            detail = stripped
            approver = CUSTOMER_APPROVER.match(detail)
            if approver:
                item.approved_by, item.approved_at = approver.group('by').strip(), approver.group('at').strip()
                item.approver_kind = (approver.group('kind') or '').lower()
            elif detail == AGENT_SUB_LABEL:
                item.agent_label = True
            elif CUSTOMER_QUOTE_OPEN.match(detail):
                entry = line[line.index('"'):]  # from the line as printed, its trailing spaces kept
            elif not item.summary:
                item.summary = detail
    close_entry()
    return out


def _quote_text_ok(printed: str, slice_text: str | None) -> bool:
    """A printed quotation is the passage exactly - as written, with its controls escaped, or with its line breaks as the
    TXT shows them (txt_shown); never equal only once whitespace is collapsed, which would pass an offset one character
    off at a line end."""
    return slice_text is not None and printed in (slice_text, escaped(slice_text), txt_shown(slice_text))


def _quote_matches(quote: dict, passage: str | None) -> bool:
    """Whether a quotation is ``passage`` exactly. A TXT quotation (parse_customer_txt: it carries 'printed') is the
    passage as reports._join prints it (txt_printed) - its line breaks continued as the writer continues them, its
    controls escaped - never the passage read back by stripping a fixed indent, nor equal only once whitespace is
    collapsed (refutation round 3, B-04). A CSV cell is the passage as written or with its controls escaped
    (_quote_text_ok)."""
    if passage is None:
        return False
    if 'printed' in quote:
        return quote['printed'] is not None and quote['printed'] == txt_printed(passage)
    return _quote_text_ok(quote['text'], passage)


def _check_customer_items(doc, name, kind, items, truth, revision_text, pages, prefix) -> list[Result]:
    """The numbered items against the truth: the same codes in order and numbered 1..n, each with its units, modifiers,
    status, approver, agent label and quotations (each exact where it gives offsets, each a passage the server's one
    quotation rule holds for the code)."""
    out = []
    shown = Counter(i.code for i in items)
    wanted = Counter(t['code'] for t in truth)
    numbered = [i.number for i in items] == list(range(1, len(items) + 1))
    out.append(Result(doc, name, f'{prefix}.items', 'pass' if shown == wanted and numbered else 'fail',
                      f'{len(items)} item(s): {", ".join(f"{i.number}. {i.code}" for i in items) or "none"}'
                      + ('' if shown == wanted else f'; the operator view implies {", ".join(t["code"] for t in truth) or "none"}')
                      + ('' if numbered else '; not numbered 1..n')))
    order = [i.code for i in items] == [t['code'] for t in truth]
    out.append(Result(doc, name, f'{prefix}.order', 'pass' if order else 'warn',
                      'in the order the customer list shows them' if order else 'not in the order the customer list shows them'))
    # each item against the persisted proposal of its code (the n-th of a code against the n-th)
    pending = {}
    for want in truth:
        pending.setdefault(want['code'], []).append(want)
    pairs = [(item, pending[item.code].pop(0)) for item in items if pending.get(item.code)]
    wrong_units, wrong_modifiers, unknown_modifiers, wrong_status, unknown_status, wrong_approver = [], [], [], [], [], []
    wrong_label, inexact, unsupported, unquoted = [], [], [], []
    for item, want in pairs:
        if (item.units or '') != want['units']:
            wrong_units.append(f'{item.code} units {item.units or "not printed"} (persisted {want["units"]})')
        if want['modifiers'] is UNKNOWN:
            unknown_modifiers.append(f'{item.code} (the report shows {list(item.modifiers) or "none"})')
        elif tuple(item.modifiers) != tuple(want['modifiers']):
            wrong_modifiers.append(f'{item.code} modifiers {list(item.modifiers)} (persisted {list(want["modifiers"])})')
        if kind == 'draft' and want['status'] is UNKNOWN:
            unknown_status.append(f'{item.code} (the report shows {item.status or "no status"})')
        elif kind == 'draft' and item.status != CUSTOMER_STATUS_LABELS.get(want['status']):
            wrong_status.append(f'{item.code} {item.status or "no status"} (expected {CUSTOMER_STATUS_LABELS.get(want["status"])})')
        if item.agent_label != want['agent'] or item.other_label:
            wrong_label.append(f'{item.code} {"carries" if item.agent_label else "lacks"} the agent-executed synthetic review label'
                               + (f' and is labelled {item.other_label!r}' if item.other_label else '')
                               + f' ({"an approval agent review took part in" if want["agent"] else "no approval agent review took part in"})')
        if kind == 'approved':
            if item.approved_by != want['approved_by'] or not same_instant(item.approved_at, want['approved_at']) \
                    or item.approver_kind != want['approver_kind'] or item.status not in ('', 'Approved'):
                wrong_approver.append(f'{item.code} approved by {item.approved_by or "nobody"} ({item.approver_kind or "no kind"}) at '
                                      f'{item.approved_at or "no time"}; persisted {want["approved_by"]} ({want["approver_kind"]}) at '
                                      f'{want["approved_at"]}')
            if not item.quotes and want['allowed']:
                unquoted.append(item.code)
        for q in item.quotes or []:
            if not q['parsed']:
                inexact.append(f'{item.code} {q["raw"][:40]!r} is not a quotation the grammar reads')
                continue
            if q['start'] is not None:
                slice_text = cp_slice(revision_text, q['start'], q['end'])
                if not _quote_matches(q, slice_text):
                    inexact.append(f'{item.code}[{q["start"]}:{q["end"]}]')
                elif q['page'] is not None and page_of(pages, q['start'], q['end']) not in (None, q['page']):
                    inexact.append(f'{item.code}[{q["start"]}:{q["end"]}] page {q["page"]}')
                same = [s for s in want['allowed'] if s.get('start') == q['start'] and s.get('end') == q['end']]
                if any(s.get('start') == q['start'] and s.get('end') == q['end'] for s in want['unrelated']):
                    unsupported.append(f'{item.code}[{q["start"]}:{q["end"]}] is a passage CPT Studio found unrelated')
                elif not same:
                    unsupported.append(f'{item.code}[{q["start"]}:{q["end"]}] is none of the passages CPT Studio holds as support')
            else:
                texts = [s.get('text', '') for s in want['allowed']]
                if not any(_quote_matches(q, t) for t in texts):
                    unsupported.append(f'{item.code} {collapse(q["text"])[:50]!r} is none of the passages CPT Studio holds as support')
                if kind == 'approved':
                    inexact.append(f'{item.code} {collapse(q["text"])[:40]!r} is printed without its character offsets')
    out.append(Result(doc, name, f'{prefix}.units', 'fail' if wrong_units else 'pass', '; '.join(wrong_units) or 'units as persisted'))
    if wrong_modifiers:
        out.append(Result(doc, name, f'{prefix}.modifiers', 'fail', '; '.join(wrong_modifiers)))
    elif unknown_modifiers:
        out.append(Result(doc, name, f'{prefix}.modifiers', 'incomplete', 'cannot verify: the operator view\'s decision carries '
                          f'no "modifiers" list for {"; ".join(unknown_modifiers)}'))
    else:
        out.append(Result(doc, name, f'{prefix}.modifiers', 'pass', 'modifiers as decided (none where none was chosen)'))
    if kind == 'draft' and wrong_status:
        out.append(Result(doc, name, f'{prefix}.status', 'fail', '; '.join(wrong_status)))
    elif kind == 'draft' and unknown_status:
        out.append(Result(doc, name, f'{prefix}.status', 'incomplete', 'cannot verify: the operator view does not say what '
                          f'the customer page shows (no "customer" status) for {"; ".join(unknown_status)}'))
    elif kind == 'draft':
        out.append(Result(doc, name, f'{prefix}.status', 'pass', 'each status as the server gives it on the customer page'))
    else:
        out.append(Result(doc, name, f'{prefix}.approver', 'fail' if wrong_approver else 'pass', '; '.join(wrong_approver)
                          or 'each approval by its persisted reviewer, of the reviewer\'s own kind, at its time'))
        out.append(Result(doc, name, f'{prefix}.quoted', 'fail' if unquoted else 'pass',
                          f'approved without a quotation although CPT Studio holds a supporting passage: {unquoted}' if unquoted
                          else 'every approved code quotes its evidence where CPT Studio holds a supporting passage'))
    out.append(Result(doc, name, f'{prefix}.agent_label', 'fail' if wrong_label else 'pass', '; '.join(wrong_label)
                      or 'each approval agent review took part in is labelled agent-executed synthetic review, and only those'))
    out.append(Result(doc, name, f'{prefix}.evidence.exact', 'fail' if inexact else 'pass', '; '.join(inexact)
                      or 'every quotation with offsets is an exact slice of the revision text on its page'))
    out.append(Result(doc, name, f'{prefix}.evidence.support', 'fail' if unsupported else 'pass', '; '.join(unsupported)
                      or 'every quotation is a passage CPT Studio holds as support for its code'))
    return out


def _customer_scan(doc, name, text, fmt, api, trace) -> list[Result]:
    module = scanner()
    revision_text = (api.get('revision') or {}).get('text') or '' if api else ''
    ctx = module.scan_context(revision_text, module.deny_values_from(api, trace) if api else ())
    hits = module.scan_file(text, ctx, name, fmt)
    hard = [h for h in hits if h['severity'] == 'hard']
    soft = [h for h in hits if h['severity'] != 'hard']
    words = lambda items: '; '.join(f'{h["id"]} at {h["where"]}: {h["match"]!r}' for h in items[:6])  # noqa: E731
    out = [Result(doc, name, 'scan.file', 'fail' if hard else 'pass', f'{len(hard)} hit(s): {words(hard)}' if hard
                  else 'no provider, model, usage, id, hash, trace, rule-id or orchestration text')]
    if soft:
        out.append(Result(doc, name, 'scan.file.wording', 'warn', f'{len(soft)} soft hit(s): {words(soft)}'))
    return out


def check_customer_txt(doc: str, name: str, text: str, kind: str, api: dict | None, trace: dict | None = None,
                       generated_by: str | None = None) -> list[Result]:
    parsed = parse_customer_txt(text)
    out = [Result(doc, name, 'marker.synthetic', 'pass' if SYNTHETIC_MARK.search(parsed['first']) and SYNTHETIC_MARK.search(parsed['last']) else 'fail',
                  'the SYNTHETIC line opens and closes the report' if SYNTHETIC_MARK.search(parsed['first']) and SYNTHETIC_MARK.search(parsed['last'])
                  else f'first line {parsed["first"][:60]!r}; last line {parsed["last"][:60]!r}'),
           Result(doc, name, 'format', 'pass' if parsed['formats'] == [CUSTOMER_FORMAT] else 'fail', f'report format {parsed["formats"]}')]
    draft_head = bool(CUSTOMER_DRAFT_HEADLINE.search(parsed['headline']))
    approved_head = bool(CUSTOMER_APPROVED_HEADLINE.search(parsed['headline'])) and not draft_head
    ok = draft_head if kind == 'draft' else approved_head
    out.append(Result(doc, name, 'headline', 'pass' if ok else 'fail', parsed['headline'][:80] or 'no headline'))
    codes_section = [s for s in parsed['sections'] if CUSTOMER_DRAFT_HEADLINE.search(s) or CUSTOMER_APPROVED_HEADLINE.search(s)]
    wrong_section = (kind == 'draft' and any(CUSTOMER_APPROVED_HEADLINE.search(s) and not CUSTOMER_DRAFT_HEADLINE.search(s) for s in codes_section)) \
        or (kind == 'approved' and any(CUSTOMER_DRAFT_HEADLINE.search(s) for s in codes_section))
    out.append(Result(doc, name, 'codes.section', 'pass' if len(codes_section) == 1 and not wrong_section else 'fail',
                      f'sections {parsed["sections"]}'))
    out.append(Result(doc, name, 'items.outside_section', 'fail' if parsed['stray_items'] else 'pass',
                      f'numbered codes outside the codes section: {[i.code for i in parsed["stray_items"]]}' if parsed['stray_items'] else 'none'))
    out.append(Result(doc, name, 'limitations', 'pass' if parsed['limitations'] else 'warn',
                      f'{len(parsed["limitations"])} limitation(s)' if parsed['limitations'] else 'no limitations listed'))
    if api is None:
        out.append(Result(doc, name, 'content.vs.operator', 'incomplete', 'no operator view of the encounter; content checks skipped'))
        return out
    fields = parsed['fields']
    date = established_date(api)
    printed = fields.get('Date of service')
    # an established date is printed as it is; none established, the report names no date of its own
    date_ok = printed == date if date else (printed is not None and not re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}', printed))
    out.append(Result(doc, name, 'header.encounter', 'pass' if fields.get('Encounter') == api.get('title') else 'fail',
                      f'{fields.get("Encounter")!r} (operator {api.get("title")!r})'))
    out.append(Result(doc, name, 'header.date_of_service', 'pass' if date_ok else 'fail',
                      f'{printed!r} (operator {date or "no date established"!r})'))
    out.append(Result(doc, name, 'header.generated', 'pass' if fields.get('Generated at') and fields.get('Generated by') else 'fail',
                      f'generated at {fields.get("Generated at")!r} by {fields.get("Generated by")!r}'))
    out.append(Result(doc, name, 'header.generated_iso', 'pass' if ISO_TIMESTAMP_LOOSE.match(fields.get('Generated at') or '') else 'warn',
                      f'generated at {fields.get("Generated at")!r}'))
    if generated_by:
        out.append(Result(doc, name, 'header.generated_by', 'pass' if fields.get('Generated by') == generated_by else 'warn',
                          f'{fields.get("Generated by")!r} (the walk signed in as {generated_by!r})'))
    revision = api.get('revision') or {}
    truth = customer_truth(api, kind)
    agent = any(t['agent'] for t in truth)
    out.append(Result(doc, name, 'header.agent_label', 'pass' if parsed['header_agent'] == agent else 'fail',
                      ('the header says agent-executed synthetic review' if parsed['header_agent'] else 'the header does not say agent-executed synthetic review')
                      + (' (agent review took part in a listed approval)' if agent else ' (agent review took part in no listed approval)')))
    out.extend(_check_customer_items(doc, name, kind, parsed['items'], truth, revision.get('text') or '', revision.get('pages'), 'items'))
    if kind == 'approved':
        approved = {t['code'] for t in truth}
        others = {t['code'] for t in customer_truth(api, 'draft')} - approved
        quoted = [q['text'] or '' for i in parsed['items'] for q in i.quotes or []]
        mentioned = sorted(code_tokens(text, quoted) & others)
        out.append(Result(doc, name, 'approved.only', 'warn' if mentioned else 'pass',
                          f'codes not approved are named outside the items: {mentioned}' if mentioned else 'no code that was not approved is named'))
    out.extend(_customer_scan(doc, name, text, 'txt', api, trace))
    return out


def _banner_row(row) -> bool:
    """reports.render_customer_csv's banner row: report_format the SYNTHETIC line, every other cell empty."""
    return bool(row) and bool(SYNTHETIC_MARK.search(row[0])) and not any(cell.strip() for cell in row[1:])


def check_customer_csv(doc: str, name: str, text: str, kind: str, api: dict | None, trace: dict | None = None) -> list[Result]:
    rows = scanner().csv_rows(text)
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return [Result(doc, name, 'csv.parse', 'fail', 'no header row')]
    header = [undo_neutralisation(cell) for cell in rows[0]]
    out = [Result(doc, name, 'csv.columns', 'pass' if tuple(header) == CUSTOMER_CSV_COLUMNS else 'fail',
                  f'columns {header}' + ('' if tuple(header) == CUSTOMER_CSV_COLUMNS else f' (expected {list(CUSTOMER_CSV_COLUMNS)})'))]
    if tuple(header) != CUSTOMER_CSV_COLUMNS:
        return out
    banner_first = len(rows) > 1 and _banner_row(rows[1])
    banner_last = len(rows) > 2 and _banner_row(rows[-1])
    out.append(Result(doc, name, 'csv.synthetic_marker', 'pass' if banner_first and banner_last else 'fail',
                      'the SYNTHETIC banner row follows the header and closes the file' if banner_first and banner_last else
                      f'SYNTHETIC banner row {"after the header" if banner_first else "not after the header"} and {"last" if banner_last else "not last"}'))
    data = rows[2 if banner_first else 1:len(rows) - 1 if banner_last else len(rows)]
    out.extend(_neutralised(doc, name, data))
    col = {column: index for index, column in enumerate(CUSTOMER_CSV_COLUMNS)}
    cell = lambda row, column: undo_neutralisation(row[col[column]]) if col[column] < len(row) else ''  # noqa: E731
    ragged = [n for n, row in enumerate(data, start=3 if banner_first else 2) if len(row) != len(CUSTOMER_CSV_COLUMNS)]
    out.append(Result(doc, name, 'csv.parse', 'fail' if ragged else 'pass', f'rows of another width: {ragged[:5]}' if ragged else f'{len(data)} row(s)'))
    formats = sorted({cell(row, 'report_format') for row in data})
    out.append(Result(doc, name, 'format', 'pass' if formats in ([CUSTOMER_FORMAT], []) else 'fail', f'report_format {formats}'))
    if api is None:
        out.append(Result(doc, name, 'content.vs.operator', 'incomplete', 'no operator view of the encounter; content checks skipped'))
        return out
    titles = sorted({cell(row, 'encounter_title') for row in data})
    dates = sorted({cell(row, 'date_of_service') for row in data})
    date = established_date(api) or ''
    out.append(Result(doc, name, 'csv.constants', 'pass' if titles in ([api.get('title')], []) and dates in ([date], []) else 'fail',
                      f'encounter_title {titles}, date_of_service {dates} (operator {api.get("title")!r}, {date!r})'))
    groups: dict[str, list] = {}
    for row in data:
        groups.setdefault(cell(row, 'number'), []).append(row)
    facts = ('code', 'units', 'modifiers', 'status', 'approved_by', 'approver_kind', 'approved_at', 'summary', 'review_label')
    inconsistent = [number for number, group in groups.items() if len({tuple(cell(r, c) for c in facts) for r in group}) > 1]
    out.append(Result(doc, name, 'csv.groups', 'fail' if inconsistent else 'pass',
                      f'items whose rows disagree: {inconsistent}' if inconsistent else f'{len(groups)} item(s), each one set of values across its rows'))
    items = []
    status_of = {label.lower(): key for key, label in CUSTOMER_STATUS_LABELS.items()}
    for number, group in groups.items():
        first = group[0]
        status = cell(first, 'status').strip()
        label = cell(first, 'review_label').strip()
        item = CustomerItem(number=int(number) if number.isdigit() else -1, code=cell(first, 'code').strip(), units=cell(first, 'units').strip(),
                            modifiers=tuple(w for w in re.split(r'[\s,;/]+', cell(first, 'modifiers')) if w),
                            status=CUSTOMER_STATUS_LABELS.get(status, CUSTOMER_STATUS_LABELS.get(status_of.get(status.lower(), ''), status)),
                            approved_by=cell(first, 'approved_by'), approver_kind=cell(first, 'approver_kind'),
                            approved_at=cell(first, 'approved_at'), summary=cell(first, 'summary'), quotes=[],
                            agent_label=label == AGENT_SUB_LABEL, other_label=label if label and label != AGENT_SUB_LABEL else '')
        for row in group:
            if not any(cell(row, c) for c in ('evidence_text', 'evidence_page', 'evidence_start', 'evidence_end')):
                continue
            start, end, page = cell(row, 'evidence_start'), cell(row, 'evidence_end'), cell(row, 'evidence_page')
            item.quotes.append({'raw': cell(row, 'evidence_text'), 'parsed': start.isdigit() and end.isdigit(), 'text': cell(row, 'evidence_text'),
                                'start': int(start) if start.isdigit() else None, 'end': int(end) if end.isdigit() else None,
                                'page': int(page) if page.isdigit() else None})
        items.append(item)
    if kind == 'draft':
        filled = [i.code for i in items if i.approved_by or i.approver_kind or i.approved_at]
        out.append(Result(doc, name, 'csv.approval_cells', 'fail' if filled else 'pass',
                          f'a draft carries approval cells for {filled}' if filled else 'no approval cell is filled in a draft'))
    revision = api.get('revision') or {}
    truth = customer_truth(api, kind)
    out.extend(_check_customer_items(doc, name, kind, items, truth, revision.get('text') or '', revision.get('pages'), 'csv.items'))
    out.extend(_customer_scan(doc, name, text, 'csv', api, trace))
    return out


def check_customer_hashes(doc: str, name: str, data: bytes, download: dict) -> list[Result]:
    """A customer download: the bytes on disk, re-fetched with the customer session, as the operator listing and the
    operator's stored bytes hold them; never an X-Content-SHA256 on the customer download."""
    actual = sha256_bytes(data)
    out = []
    for field, label in (('sha256', 'browser-computed'), ('refetch_sha256', 're-fetched customer download'),
                         ('operator_sha256', 'operator listing'), ('operator_download_sha256', 'operator stored bytes'),
                         ('operator_header_sha256', "operator download's X-Content-SHA256")):
        recorded = download.get(field)
        if not recorded:
            out.append(Result(doc, name, f'sha256.{field}', 'fail', f'no {label} sha256 recorded'))
        else:
            out.append(Result(doc, name, f'sha256.{field}', 'pass' if recorded == actual else 'fail',
                              actual if recorded == actual else f'file {actual} != {label} {recorded}'))
    out.append(Result(doc, name, 'header.no_hash', 'fail' if download.get('header_sha256') else 'pass',
                      'the customer download carries X-Content-SHA256' if download.get('header_sha256') else 'no X-Content-SHA256 on the customer download'))
    out.append(Result(doc, name, 'audience', 'pass' if download.get('operator_audience') == 'customer' else 'fail',
                      f'the operator listing calls it {download.get("operator_audience")!r}'))
    if download.get('size') != len(data):
        out.append(Result(doc, name, 'size', 'fail', f'file {len(data)} bytes != recorded {download.get("size")}'))
    return out


def load_trace(evidence_dir: Path, doc: dict, api_dir: Path | None) -> dict | None:
    candidates = []
    if api_dir and doc.get('encounter_id'):
        candidates.append(api_dir / f'{doc["encounter_id"]}.trace.json')
    trace = (doc.get('operator_snapshots') or {}).get('trace')
    if trace:
        candidates.append(evidence_dir / trace)
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding='utf-8'))
    return None


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
    """The encounter JSON the checks hold the files to: --api-dir/<id>.json, else the OPERATOR snapshot the evidence
    names (operator_snapshots, schema cpt-studio-browser-evidence@2), else - for evidence of a walk before the customer
    interface - its api_snapshots (then the full view). A @2 walk's customer_snapshots are never a source of truth."""
    candidates = []
    if api_dir and doc.get('encounter_id'):
        candidates.append(api_dir / f'{doc["encounter_id"]}.json')
    for snapshots in (doc.get('operator_snapshots') or {}, doc.get('api_snapshots') or {}):
        candidates += [evidence_dir / snapshots[key] for key in ('final', 'after_reload') if snapshots.get(key)]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding='utf-8')), str(path)
    return None, ''


def verify_document(evidence_dir: Path, doc: dict, api_dir: Path | None, session_label: str | None = None) -> list[Result]:
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
        try:
            text, problem = data.decode('utf-8'), None
        except UnicodeDecodeError as exc:
            text, problem = None, str(exc)
        # a customer report (the walk records its audience; the file names its format) or an operator report as before
        customer = download.get('audience') == 'customer' or (text is not None and CUSTOMER_FORMAT in text)
        if customer:
            out.extend(check_customer_hashes(doc_id, name, data, download))
            if download.get('audience') != 'customer':
                out.append(Result(doc_id, name, 'audience.recorded', 'fail', 'a customer report recorded as another audience\'s download'))
        else:
            out.extend(check_hashes(doc_id, name, data, download, listed))
        if kind not in (CUSTOMER_KINDS if customer else ('draft', 'reviewed')) or fmt not in ('txt', 'csv'):
            out.append(Result(doc_id, name, 'format', 'fail', f'unknown {"customer " if customer else ""}report {kind!r}/{fmt!r}'))
            continue
        if text is None:
            out.append(Result(doc_id, name, 'utf8', 'fail', problem))
            continue
        if customer:
            trace = load_trace(evidence_dir, doc, api_dir)
            out.extend(check_customer_txt(doc_id, name, text, kind, api, trace, session_label) if fmt == 'txt' else
                       check_customer_csv(doc_id, name, text, kind, api, trace))
        else:
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
    parser.add_argument('--api-dir', type=Path, help='directory of <encounter id>.json OPERATOR encounter views (GET /ops/api/'
                                                     'encounters/<id>), optionally beside <encounter id>.trace.json')
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
    session_label = ((evidence.get('session') or {}).get('user') or {}).get('label')
    for doc in documents:
        results.extend(verify_document(args.evidence.parent, doc, args.api_dir, session_label))
    print_table(results)
    if args.json_out:
        args.json_out.write_text(json.dumps([asdict(r) for r in results], indent=2) + '\n', encoding='utf-8')
    return exit_status(results)


if __name__ == '__main__':
    sys.exit(main())
