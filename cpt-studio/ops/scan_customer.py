#!/usr/bin/env python3
"""Scan every customer surface of a running CPT Studio for what a customer must never be shown - and nothing else.

    python3 ops/scan_customer.py --base-url https://cpt.quillmd.com --credentials customer.json --out EVIDENCE_DIR
        [--encounter ID ...] [--all [--limit N]] [--operator-json DIR]

The owner directive of 2026-11-03 (section 2) keeps provider and model identities, usage, request ids, hashes, trace
links, retrieval logs and rule ids out of every customer screen, API response and download, enforced on the server
(cpt-studio/CORE-UX-DESIGN.md sections 5 and 7). This tool signs a CUSTOMER account in and makes only GET requests:

  GET /                         the customer page, and each same-origin script and stylesheet its HTML names (script src,
                                link rel stylesheet, modulepreload or preload): scanned whole. Not the PDF library the
                                page imports on demand to draw a PDF (studio/static/studio/lib/pdfjs-<version>/, named on
                                <body> as data-pdf-module and data-pdf-worker): third-party files byte-identical to their
                                npm package, sealed by sha256 - in its MANIFEST.json, and by the Django suite's own digest
                                of every file and the manifest (tests/test_frontend.py PDF_LIB_DIGEST), so a changed file
                                fails the suite until that line changes too - and never scanned as CPT Studio's own
                                wording (DECISIONS D368; the shared denylist's 'bundle' surface states the exception)
  GET /api/session              against the customer contract's session keys, scanned
  GET /api/encounters           the list, against the contract's list keys, scanned
  for each encounter named (--encounter, repeatable) or listed (--all, at most --limit, newest first):
    GET /api/encounters/<id>             against the contract (every key listed, nothing else), scanned
    GET <document.original_url>          its status and headers only: the document is the customer's own
    GET <document.view_url>              likewise (the original, or the PDF a Word file was converted to)
    GET <reports[].download_url>         every customer export, scanned whole, with no X-Content-SHA256 header: a TXT
                                         or CSV as its text; a PDF (served as application/pdf, opening with %PDF- or
                                         listed as pdf) as the text pypdf extracts from each page, as a reader sees it
                                         (invisible format characters deleted, control characters read as spaces):
                                         its running header and footer line by line, its body as one stream over
                                         every page with only the text inside a printed quotation of the document set
                                         aside, neighbouring lines also read joined (over a line break, a page break
                                         or a quotation) - and its document information values; never its raw bytes
                                         (its trailer /ID is 32 hex characters; its streams are compressed). A PDF that
                                         cannot be read, or that holds what the scan does not read (bookmarks, a form,
                                         page labels, annotations, an image ...), fails the scan; it never passes
    GET every /ops/ URL of it            each must answer 404 to this session (the operator console's pages)
    GET every removed URL of it          each must answer 404 (the earlier trace and operator API, for everyone)
  POST /logout/ and GET /api/session     the session must then be refused (verify_login.py's sign-out proof)

Every body and header is scanned with ops/verification/customer-denylist.json (the browser walk ops/walk.cjs reads the
same list, and this module's tests run its vectors) and every payload is held to ops/verification/customer-contract.json
- the Fable coding build's customer contract (client contract customer-2026-11-26); the Django suite holds the server to
the same file through this module's readers (tests/test_api_customer.py). A string that is one of the encounter's own
quotations - the passages of its document its codes cite - is not scanned. --operator-json DIR adds an operator view's
own identifiers, read by the paths the denylist names (deny_value_paths; files <encounter id>.json and, optionally,
<encounter id>.trace.json): the Fable coding build's operator console is server-rendered and its denylist names none, so
the option only matters for a denylist that names some.

Sign-in and transport are ops/verify_login.py's: --credentials a private JSON file with top-level "username" and
"password" (or --username with --password-file), refused if a group or other user may read it; TLS verified; a plain
http base URL only on the loopback; no redirect followed; the password never printed or written. Stdlib only, but for
pypdf, imported only to read a PDF export (requirements-dev.txt): where it is missing, a PDF export fails the scan.

The evidence, OUT/scan-evidence.json (which must not exist yet), holds every request made (method, path, status), the
encounters scanned, every check and the hits (where and what matched, never a password). Exit 0 when every hard check
passed, 1 when any failed or the run stopped, 2 on a usage error before any request.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import platform
import re
import secrets
import sys
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_scan_customer_login', HERE / 'verify_login.py')
login = importlib.util.module_from_spec(_spec)
sys.modules.setdefault('cpt_scan_customer_login', login)
_spec.loader.exec_module(login)

EVIDENCE_SCHEMA = 'cpt-studio-customer-scan@1'
EVIDENCE_NAME = 'scan-evidence.json'
DENYLIST = json.loads((HERE / 'verification' / 'customer-denylist.json').read_text(encoding='utf-8'))
CONTRACT = json.loads((HERE / 'verification' / 'customer-contract.json').read_text(encoding='utf-8'))
# ASCII-only and case-insensitive, as the walk's JavaScript reads the same patterns ('gi' without 'u'): Python's re.I
# alone would fold the long s and the Kelvin sign onto ASCII letters, which JavaScript does not. A pattern marked
# "case_sensitive": true (design v2, FINAL-V2 4.12 [R:MO-2]: a provider name joined to a word by its case alone) is
# matched with its case as written, ASCII-only, as the walk reads it ('g').
FLAGS = re.ASCII | re.IGNORECASE
PATTERNS = [(p['id'], p['severity'], frozenset(p['surfaces']),
             re.compile(p['source'], re.ASCII if p.get('case_sensitive') is True else FLAGS))
            for p in DENYLIST['patterns']]
FORBIDDEN_KEYS = frozenset(DENYLIST['forbidden_keys'])
DENY_SHAPE = re.compile(DENYLIST['deny_value_shape'])
ISO_TIMESTAMP = re.compile(CONTRACT['iso_pattern'])
DATE_ONLY = re.compile(CONTRACT['date_pattern'])
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
# Response headers that carry no customer-facing wording (as the walk's own list, ops/walk.cjs).
UNSCANNED_HEADERS = frozenset({'set-cookie', 'date', 'etag', 'last-modified', 'content-length', 'content-security-policy',
                               'content-security-policy-report-only', 'strict-transport-security', 'permissions-policy',
                               'report-to', 'nel', 'expires', 'cache-control', 'vary', 'connection', 'keep-alive',
                               'transfer-encoding', 'content-encoding', 'accept-ranges', 'age'})
# The operator console's GET pages (studio/operator.py, cptstudio/urls.py), each 404 to a customer; and what was removed
# for everyone - the earlier trace, the earlier operator API and its script - each 404 whoever asks.
OPS_GET_PATHS = ('/ops/', '/ops/encounters/{id}', '/ops/encounters/{id}/original')
REMOVED_PATHS = ('/api/encounters/{id}/trace', '/ops/api/encounters/{id}', '/ops/assets/ops.js')
MAX_HITS = 60


# --- the shared denylist (ops/verification/customer-denylist.json); ops/walk.cjs is the same reader ----------------

@dataclass
class ScanContext:
    document_text: str = ''
    deny_values: list = field(default_factory=list)
    allowed: list = field(default_factory=list)


def scan_context(document_text: str = '', deny_values=(), allowed=()) -> ScanContext:
    text = document_text or ''
    values = sorted({value for value in deny_values if value and value not in text})
    allowed = sorted({item for item in [*DENYLIST['allowed'], *allowed] if item}, key=len, reverse=True)
    return ScanContext(text, values, allowed)


def _excerpt(text: str, at: int, length: int) -> str:
    start = max(0, at - 24)
    end = at + length + 24
    return ('…' if start else '') + re.sub(r'\s+', ' ', text[start:end]) + ('…' if end < len(text) else '')


# A JSON value that is never a passage of the document: a code line's modifier is part of the code line the coding
# review returned, so it is scanned whole even when a quotation holds the same words (SEC-S4: a modifier 'Claude' beside
# a cited 'Dr. Claude Example ...' was set aside as a part of the quotation). The walk's scanJson reads the same paths.
NEVER_QUOTED = re.compile(r'\.modifiers\[\d+\]$')


def scan_text(text, ctx: ScanContext, surface: str, where: str = '', hits: list | None = None,
              quotable: bool = True) -> list:
    """The hits of one string on one surface ({id, severity, surface, where, match}). A string that is a substring of
    the document text is a quotation of it and is not scanned (bundle text always is), unless it is not ``quotable``
    (NEVER_QUOTED)."""
    hits = [] if hits is None else hits
    raw = text if isinstance(text, str) else ('' if text is None else str(text))
    if not raw.strip():
        return hits
    if quotable and surface != 'bundle' and ctx.document_text and raw in ctx.document_text:
        return hits
    cleaned = raw
    for allowed in ctx.allowed:
        cleaned = cleaned.replace(allowed, ' ')
    for pattern_id, severity, surfaces, regex in PATTERNS:
        if surface not in surfaces:
            continue
        for match in regex.finditer(cleaned):
            hits.append({'id': pattern_id, 'severity': severity, 'surface': surface, 'where': where,
                         'match': _excerpt(cleaned, match.start(), len(match.group()))})
    if surface != 'bundle':
        for value in ctx.deny_values:
            if value in cleaned:
                hits.append({'id': 'deny_value', 'severity': 'hard', 'surface': surface, 'where': where,
                             'match': f'{value[:14]}…'})
    return hits


def scan_json(value, ctx: ScanContext, where: str = '$', hits: list | None = None, surface: str = 'json') -> list:
    """Every string value and every key of a JSON value; a forbidden key is a hit by itself; a value at a NEVER_QUOTED
    path is scanned whole."""
    hits = [] if hits is None else hits
    if isinstance(value, str):
        return scan_text(value, ctx, surface, where, hits, quotable=not NEVER_QUOTED.search(where))
    if isinstance(value, list):
        for index, item in enumerate(value):
            scan_json(item, ctx, f'{where}[{index}]', hits, surface)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                hits.append({'id': 'forbidden_key', 'severity': 'hard', 'surface': surface, 'where': f'{where}.{key}',
                             'match': key})
            scan_text(key, ctx, surface, f'{where}.{key} (key)', hits)
            scan_json(item, ctx, f'{where}.{key}', hits, surface)
    return hits


def csv_rows(text: str) -> list:
    """RFC 4180 rows (quoted cells, doubled quotes, CR LF or LF)."""
    rows, row, cell, quoted, i = [], [], '', False, 0
    while i < len(text):
        ch = text[i]
        if quoted:
            if ch == '"' and text[i + 1:i + 2] == '"':
                cell += '"'
                i += 1
            elif ch == '"':
                quoted = False
            else:
                cell += ch
        elif ch == '"':
            quoted = True
        elif ch == ',':
            row.append(cell)
            cell = ''
        elif ch in '\r\n':
            if ch == '\r' and text[i + 1:i + 2] == '\n':
                i += 1
            row.append(cell)
            rows.append(row)
            row, cell = [], ''
        else:
            cell += ch
        i += 1
    if cell or row:
        row.append(cell)
        rows.append(row)
    return rows


def scan_file(text: str, ctx: ScanContext, name: str, fmt: str, hits: list | None = None) -> list:
    """A downloaded file, whole: a CSV cell by cell, a TXT line by line, any quoted passage that is the document's own
    text set aside (an export quotes the document)."""
    hits = [] if hits is None else hits
    if fmt == 'csv':
        for r, row in enumerate(csv_rows(text), start=1):
            for c, cell in enumerate(row, start=1):
                scan_text(cell, ctx, 'file', f'{name} row {r} cell {c}', hits)
        return hits
    for index, line in enumerate(re.split(r'\r?\n', text), start=1):
        rest = line
        for quoted in re.findall(r'"[^"]*"', line):
            if quoted[1:-1] in ctx.document_text:
                rest = rest.replace(quoted, '""', 1)
        if rest.strip() and rest.strip() in ctx.document_text:
            continue
        scan_text(rest, ctx, 'file', f'{name} line {index}', hits)
    return hits


# --- a PDF export: the text it shows, never its bytes ------------------------------------------------------------------

PDF_TYPE = 'application/pdf'
# The curly quotation marks the PDF export prints every quotation between (studio/physician_pdf.py): a quotation may
# wrap over several lines and continue over a page break. Only what lies between them can be the document's own words.
OPEN_QUOTE, CLOSE_QUOTE = '“', '”'
# What a PDF can show beside its pages' text and its document information, which this scan does not read: a PDF that
# holds any of them is a scan problem, never a pass (a CPT Studio export holds none). Page labels are the names a viewer
# shows for the pages in its page box ("Claude Fable 1"), not text on any page.
UNREAD_IN_CATALOG = {'/Outlines': 'bookmarks', '/AcroForm': 'a form', '/Names': 'a names tree (attachments, scripts or '
                     'destinations)', '/OpenAction': 'an open action', '/AA': 'document actions',
                     '/Metadata': 'an XMP metadata stream', '/PageLabels': 'page labels'}
UNREAD_ON_PAGE = {'/Annots': 'annotations', '/AA': 'page actions'}
# The entries this scan knows a CPT Studio export holds - what ReportLab writes for it - and reads past: any other entry
# of the trailer, the catalog, a page or a page's resources (optional content, a page's own XMP stream, article threads,
# encryption ...) is something the scan does not read, so the PDF fails it (a list of what is unread can never be whole).
READ_IN_TRAILER = frozenset({'/Size', '/Root', '/Info', '/ID'})
READ_IN_CATALOG = frozenset({'/Type', '/Pages', '/PageMode'})
READ_ON_PAGE = frozenset({'/Type', '/Parent', '/Resources', '/MediaBox', '/Contents', '/Rotate', '/Trans'})
READ_IN_RESOURCES = frozenset({'/Font', '/ProcSet'})
# What a reader never sees as itself, so the PDF's text is read without it (a name with an invisible character inside
# it, "Cl<U+200E>aude", reads "Claude"): Unicode's default-ignorable code points - zero-width spaces and joiners, the
# bidirectional marks, embeddings and isolates, the invisible operators, variation selectors, the soft hyphen, the
# Hangul fillers, tags, the object replacement character (which the report's fonts draw as nothing, so the report
# deletes it) - and every other format character (category Cf) are deleted; a C0 or C1 control character is
# read as a space, as the report prints one (studio/physician_pdf.py clean_text). pypdf gives U+0000 for a character the
# PDF's font has no glyph for (a .notdef box), so that reads as a space too.
_INVISIBLE = re.compile('[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e'
                        '\u2060-\u206f\u3164\ufe00-\ufe0f\ufeff\uffa0\ufff0-\ufffc\U0001bca0-\U0001bca3'
                        '\U0001d173-\U0001d17a\U000e0000-\U000e0fff]')
_CONTROL = re.compile('[\x00-\x1f\x7f-\x9f]')


class Unreadable(Exception):
    """A download that claims to be a PDF and cannot be read as one, or a Python without pypdf: a scan problem, never a
    pass. The message says why, never with the file's words."""


@dataclass
class PdfReading:
    pages: list     # the text pypdf extracts from each page, in order
    metadata: dict  # each entry of the document information dictionary: its name (without '/') -> its value as text


def visible(text: str) -> str:
    """One line of a PDF's text as a reader sees it: every default-ignorable or other format character deleted, every
    C0 or C1 control character a space (_INVISIBLE, _CONTROL). A line break is a control character too, so this reads
    a line, never a page."""
    text = _CONTROL.sub(' ', text)
    if text.isascii():
        return text
    return ''.join(ch for ch in _INVISIBLE.sub('', text) if unicodedata.category(ch) != 'Cf')


def is_pdf(body: bytes, content_type: str = '') -> bool:
    """A download is read as a PDF when it is served as one (Content-Type application/pdf) or opens as one (%PDF-)."""
    return (content_type or '').split(';', 1)[0].strip().lower() == PDF_TYPE or body.startswith(b'%PDF-')


def _resolved(value):
    return value.get_object() if hasattr(value, 'get_object') else value


def read_pdf(body: bytes) -> PdfReading:
    """The text of each page of a PDF and its document information values, read by pypdf in its strict mode (a file it
    would have to repair is not read). Unreadable when pypdf is missing, when it cannot read the body, when the PDF has
    no page or a page gives no visible text (visible), or when it holds what this scan does not read
    (UNREAD_IN_CATALOG - page labels among them -, UNREAD_ON_PAGE, an image or form object). The pages are returned as
    pypdf extracted them; scan_pdf reads them as a reader sees them."""
    try:
        from pypdf import PdfReader  # imported only here: the rest of this tool is stdlib only
    except ImportError:
        raise Unreadable('pypdf is not installed for this Python, so the PDF could not be read') from None
    try:
        reader = PdfReader(io.BytesIO(body), strict=True)
        catalog = _resolved(reader.trailer['/Root'])
        unread = [what for key, what in UNREAD_IN_CATALOG.items() if key in catalog]
        unread += [f'the entry {key} of the trailer' for key in sorted(set(reader.trailer) - READ_IN_TRAILER)]
        unread += [f'the entry {key} of the catalog'
                   for key in sorted(set(catalog) - READ_IN_CATALOG - set(UNREAD_IN_CATALOG))]
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            unread += [f'{what} on page {number}' for key, what in UNREAD_ON_PAGE.items() if key in page]
            unread += [f'the entry {key} of page {number}'
                       for key in sorted(set(page) - READ_ON_PAGE - set(UNREAD_ON_PAGE))]
            resources = _resolved(page.get('/Resources')) or {}
            if _resolved(resources.get('/XObject')):
                unread.append(f'an image or form object on page {number}')
            unread += [f'the resource {key} of page {number}'
                       for key in sorted(set(resources) - READ_IN_RESOURCES - {'/XObject'})]
            pages.append(page.extract_text() or '')
        info = reader.metadata or {}
        metadata = {str(key).lstrip('/'): str(info[key]) for key in info}
    except Exception as exc:  # noqa: BLE001 - whatever pypdf raises, the file was not read
        raise Unreadable(f'pypdf could not read it as a PDF ({type(exc).__name__})') from None
    if unread:
        raise Unreadable(f'it holds {", ".join(unread)}, which this scan does not read')
    if not pages:
        raise Unreadable('it has no page')
    empty = [str(number) for number, text in enumerate(pages, start=1)
             if not any(visible(line).strip() for line in re.split(r'\r?\n', text))]
    if empty:
        raise Unreadable(f'no text could be read from page {", ".join(empty)}')
    return PdfReading(pages, metadata)


def _squeezed(text: str) -> str:
    return ' '.join(text.split())


def _bare(text: str) -> str:
    return ''.join(text.split())


REPLACEMENT = chr(0xFFFD)  # what the report prints for a character none of its fonts draws (studio/physician_pdf.py)


def _of_document(printed: str, document: str) -> bool:
    """``printed`` (a quotation's text as the PDF gives it, white space removed) is a part of ``document`` (likewise):
    compared with no white space at all, because the layout breaks a line inside a long token (a URL, a run of
    underscores) without a hyphen or a space, and with each U+FFFD standing for one character or none, because the report
    prints U+FFFD for a character its fonts cannot draw - which can be one this reading deletes from the document (a
    format character) or removes with the white space."""
    if not printed:
        return False
    if REPLACEMENT not in printed:
        return printed in document
    # The literal pieces between runs of U+FFFD, a run of k standing for 0 to k characters. A run at either end can stand
    # for nothing, so only the pieces from the first literal to the last are placed: by the set of document positions
    # each placement can end at, in time linear in the document for each piece (a pattern of k optional wildcards
    # backtracks exponentially on a run of undrawable characters, refutation round 4).
    parts = re.split('(' + re.escape(REPLACEMENT) + '+)', printed)
    literals, gaps = parts[0::2], [len(run) for run in parts[1::2]]
    if literals[0] == '':
        literals, gaps = literals[1:], gaps[1:]
    if literals and literals[-1] == '':
        literals, gaps = literals[:-1], gaps[:-1]
    if not literals:
        return True  # nothing but undrawn characters: no word of it can be read, so none can be scanned
    # The usual case first: each U+FFFD one character of the document, a fixed-width pattern that opens with a literal (the
    # runs at either end, which can stand for nothing, are left off) and has no optional part, so it stops at its first
    # placement; only a quotation that fails it (an undrawn white space or format character the reading removed) is
    # placed piece by piece below (refutation rounds 5 and 6). It answers nothing the placement below would not.
    fixed = re.escape(literals[0]) + ''.join(f'.{{{gap}}}' + re.escape(literal) for gap, literal in zip(gaps, literals[1:]))
    if re.search(fixed, document, re.DOTALL):
        return True
    ends, at = set(), document.find(literals[0])
    while at >= 0:
        ends.add(at + len(literals[0]))
        at = document.find(literals[0], at + 1)
    for gap, literal in zip(gaps, literals[1:]):
        ends = {end + skip + len(literal) for end in ends for skip in range(gap + 1)
                if document.startswith(literal, end + skip)}
        if not ends:
            return False
    return bool(ends)


def _running_count(pages: list) -> int:
    """How many lines lead every page alike: the report's running header and footer (the brand, the status line, the
    identity line, the footer note and the "CPT-<ref> · r<n> / <page> of <pages>" line), which studio/physician_pdf.py
    draws first on each page, so pypdf reads them first. A line is the same on every page once its white space is
    squeezed and its own "<page> of <pages>" is set aside. A one-page PDF has none: nothing repeats."""
    if len(pages) < 2:
        return 0
    total = len(pages)
    keyed = [[re.sub(rf'(?<!\d)0*{number} of 0*{total}$', '# of #', _squeezed(line)) for line in lines]
             for number, lines in enumerate(pages, start=1)]
    count = 0
    for column in zip(*keyed):
        if len(set(column)) != 1:
            break
        count += 1
    return count


def _quotations_aside(stream: str, document: str) -> list:
    """The spans of ``stream`` (a run of PDF lines joined by line breaks) that are printed quotations of the document,
    marks included: each opens with a curly opening mark and closes with a curly closing mark, and its text is a part of
    ``document``, which is given with no white space (_of_document). A quotation whose own text holds a closing mark is
    followed to the last closing mark up to which its text is still the document's. A mark that opens no quotation of
    the document is the product's own wording, as is everything outside the spans."""
    spans, at = [], 0
    while True:
        start = stream.find(OPEN_QUOTE, at)
        if start < 0:
            return spans
        end, close = None, stream.find(CLOSE_QUOTE, start + 1)
        while close >= 0:
            if not _of_document(_bare(stream[start + 1:close]), document):
                break
            end, close = close, stream.find(CLOSE_QUOTE, close + 1)
        if end is None:
            at = start + 1
        else:
            spans.append((start, end + 1))
            at = end + 1


def _where(name: str, place: tuple) -> str:
    return f'{name} page {place[0]} line {place[1]}'


def _where_joined(name: str, first: tuple, second: tuple) -> str:
    if first[0] == second[0]:
        return f'{name} page {first[0]} lines {first[1]}-{second[1]}'
    return f'{name} page {first[0]} line {first[1]} to page {second[0]} line {second[1]}'


def _scan_stream(lines: list, document: str, ctx: ScanContext, name: str, hits: list) -> None:
    """``lines`` ((page, line) place, text), in reading order, as one stream: every printed quotation of the document
    set aside (_quotations_aside, however many lines and pages it runs over), then each line's remaining text - the
    product's own wording, white space squeezed - scanned whole (never as a quotation, whatever words the document
    shares with it), and each joined to the line of product wording before it, wherever that is: over a page break and
    over a quotation set aside, so a phrase cut in two by either is read as one."""
    stream = '\n'.join(text for _, text in lines)
    blanked = list(stream)
    for start, end in _quotations_aside(stream, document):
        for index in range(start, end):
            if blanked[index] != '\n':
                blanked[index] = ' '
    previous = None
    for (place, _), text in zip(lines, ''.join(blanked).split('\n')):
        own = _squeezed(text)
        if not own:
            continue
        scan_text(own, ctx, 'file', _where(name, place), hits, quotable=False)
        if previous is not None:
            _scan_joint(previous[1], own, ctx, _where_joined(name, previous[0], place), hits)
        previous = (place, own)


def _scan_joint(first: str, second: str, ctx: ScanContext, where: str, hits: list) -> None:
    """What spans the break between two neighbouring lines of product wording in a PDF (each line was scanned alone):
    the two read joined by a space, each with the allowed strings removed first as scan_text removes them, and only a
    match that starts in the first line and ends in the second reported. Never joined with nothing between them: most
    line ends fall between words, and two words read as one fail clean reports (refutation round 3), so a token the
    layout cuts mid-word is read as two (a known limit; the page JSON holds it whole while its round is current)."""
    cleaned = []
    for line in (first, second):
        for allowed in ctx.allowed:
            line = line.replace(allowed, ' ')
        cleaned.append(line)
    joined, joint = f'{cleaned[0]} {cleaned[1]}', len(cleaned[0])
    for pattern_id, severity, surfaces, regex in PATTERNS:
        if 'file' not in surfaces:
            continue
        for match in regex.finditer(joined):
            if match.start() < joint and match.end() > joint + 1:
                hits.append({'id': pattern_id, 'severity': severity, 'surface': 'file', 'where': where,
                             'match': _excerpt(joined, match.start(), len(match.group()))})


def scan_pdf(reading: PdfReading, ctx: ScanContext, name: str, hits: list | None = None) -> list:
    """A PDF export as read_pdf read it, every line read as a reader sees it (visible). The running header and footer
    that lead every page alike (_running_count) are scanned on each page as lines of their own, joined only to each
    other. The rest - the body of every page - is one stream (_scan_stream): only the text inside a printed quotation
    (between the curly marks the report prints a quotation between, over however many lines and pages it runs) is set
    aside, and only while it is the document's own words (_of_document); every other line is the
    product's wording and is scanned whole, even a line whose words a quotation also holds (a code line's modifier
    "Claude" wrapped onto a line of its own beside a cited "Dr. Claude Example ..."). Neighbouring lines of product
    wording are also read joined, for a phrase the layout cut in two ("tool" / "calls"), over a line break, a page break
    or a quotation set aside. Then every document information value, read as a reader sees it and scanned whole: never
    a quotation."""
    hits = [] if hits is None else hits
    document = _bare(visible(ctx.document_text))
    pages = [[visible(line) for line in re.split(r'\r?\n', text)] for text in reading.pages]
    running = _running_count(pages)
    body = []
    for page_number, lines in enumerate(pages, start=1):
        places = [((page_number, index), line) for index, line in enumerate(lines, start=1)]
        _scan_stream(places[:running], document, ctx, name, hits)
        body += places[running:]
    _scan_stream(body, document, ctx, name, hits)
    for key, value in reading.metadata.items():
        scan_text(_squeezed(visible(value)), ctx, 'file', f'{name} metadata {key}', hits, quotable=False)
    return hits


def scan_headers(headers, ctx: ScanContext, where: str, hits: list | None = None) -> list:
    hits = [] if hits is None else hits
    items = headers.items() if isinstance(headers, dict) else headers
    for name, value in items:
        if name.lower() in UNSCANNED_HEADERS:
            continue
        scan_text(name, ctx, 'header', f'{where} header {name} (name)', hits)
        scan_text(str(value), ctx, 'header', f'{where} header {name}', hits)
    return hits


def harvest(value, dotted: str) -> list:
    """The strings at a dotted path ('a.b[]' takes each element of a.b, a numeric part indexes a list)."""
    nodes = [value]
    for part in dotted.split('.'):
        each = part.endswith('[]')
        key = part[:-2] if each else part
        found = []
        for node in nodes:
            if isinstance(node, list) and key.isdigit():
                nxt = node[int(key)] if int(key) < len(node) else None
            elif isinstance(node, dict):
                nxt = node.get(key)
            else:
                nxt = None
            if each:
                found.extend(nxt if isinstance(nxt, list) else [])
            elif nxt is not None:
                found.append(nxt)
        nodes = found
    return [node for node in nodes if isinstance(node, str)]


def quotations(encounter) -> str:
    """The encounter's own quotations - every passage of its document a code cites (codes[].quotes[].text) - one per
    line: what scan_text sets aside as the document's own text."""
    quotes = [quote.get('text') for code in ((encounter or {}).get('codes') or []) if isinstance(code, dict)
              for quote in (code.get('quotes') or []) if isinstance(quote, dict)]
    return '\n'.join(quote for quote in quotes if isinstance(quote, str) and quote.strip())


def deny_values_from(encounter: dict, trace: dict | None = None) -> list:
    """Every identifier the operator view (and its trace) holds that a customer surface must never carry:
    identifier-shaped (a digit or . : @ / - in it) and at least deny_value_min_length long."""
    paths = DENYLIST['deny_value_paths']
    values = [v for p in paths['encounter'] for v in harvest(encounter, p)]
    if trace:
        values += [v for p in paths['trace'] for v in harvest(trace, p)]
    return sorted({v for v in values if len(v) >= DENYLIST['deny_value_min_length'] and DENY_SHAPE.search(v)})


# --- the shared contract (ops/verification/customer-contract.json) --------------------------------------------------

def _kind(value) -> str:
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, list):
        return 'a list'
    if isinstance(value, dict):
        return 'an object'
    return {int: 'number', float: 'number', str: 'string'}.get(type(value), type(value).__name__)


_SCALARS = {
    'string': lambda v: isinstance(v, str),
    'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    'boolean': lambda v: isinstance(v, bool),
    'any': lambda v: True,
    'date': lambda v: isinstance(v, str) and bool(DATE_ONLY.match(v)),
    'iso': lambda v: isinstance(v, str) and bool(ISO_TIMESTAMP.match(v)),
}
_MISSING = object()


def shape_problems(value, node, where: str = '$', out: list | None = None, types: dict | None = None) -> list:
    """The differences between a value and a contract node, each '<where>: <what>'; at most 60."""
    out = [] if out is None else out
    types = CONTRACT['types'] if types is None else types
    if len(out) >= 60:
        return out
    if isinstance(node, str):
        nullable = node.endswith('?')
        base = node[:-1] if nullable else node
        test = _SCALARS.get(base)
        if test is None:
            out.append(f'{where}: the contract names an unknown type {base}')
        elif value is None and (nullable or base == 'any'):
            pass
        elif value is _MISSING or not test(value):
            out.append(f'{where}: {"nothing" if value is _MISSING else _kind(value)} where the contract has {node}')
        return out
    if not isinstance(node, dict):
        out.append(f'{where}: the contract node is not understood')
        return out
    if 'ref' in node:
        if value is None and node.get('nullable'):
            return out
        if node['ref'] not in types:
            out.append(f'{where}: the contract names an unknown type {node["ref"]}')
            return out
        return shape_problems(value, types[node['ref']], where, out, types)
    if value is None and node.get('nullable'):
        return out
    if 'enum' in node:
        if isinstance(value, bool) or value not in node['enum']:  # the contract's enums are words, never booleans
            out.append(f'{where}: {json.dumps(value)} is not one of {"|".join(str(item) for item in node["enum"])}')
        return out
    if 'items' in node:
        if not isinstance(value, list):
            out.append(f'{where}: {_kind(value)} where the contract has a list')
        else:
            for index, item in enumerate(value):
                shape_problems(item, node['items'], f'{where}[{index}]', out, types)
        return out
    if 'map' in node:
        if not isinstance(value, dict):
            out.append(f'{where}: {_kind(value)} where the contract has an object')
        else:
            for key, item in value.items():
                shape_problems(item, node['map'], f'{where}.{key}', out, types)
        return out
    if isinstance(node.get('keys'), dict):
        if not isinstance(value, dict):
            out.append(f'{where}: {_kind(value)} where the contract has an object')
            return out
        for key, child in node['keys'].items():
            if key not in value:
                out.append(f'{where}.{key}: missing (the contract lists it)')
            else:
                shape_problems(value[key], child, f'{where}.{key}', out, types)
        for key in value:
            if key not in node['keys']:
                out.append(f'{where}.{key}: not in the customer contract')
        return out
    out.append(f'{where}: the contract node is not understood')
    return out


# --- checks ------------------------------------------------------------------------------------------------------

def check_scan(check_id: str, hits: list, what: str) -> list:
    hard = [h for h in hits if h['severity'] == 'hard']
    soft = [h for h in hits if h['severity'] != 'hard']

    def words(items):
        shown = [f'{h["id"]} at {h["where"]}: {json.dumps(h["match"], ensure_ascii=False)}' for h in items[:6]]
        return '; '.join(shown) + (f'; and {len(items) - 6} more' if len(items) > 6 else '')

    out = [login.check(check_id, 'hard', not hard, f'{len(hard)} hit(s) in {what}: {words(hard)}' if hard
                       else f'{what}: no provider, model, usage, id, hash, trace, rule-id or orchestration text')]
    if soft:
        out.append(login.check(f'{check_id}.wording', 'soft', False, f'{len(soft)} soft hit(s) in {what}: {words(soft)}'))
    return out


def check_contract(value, schema: str, check_id: str) -> dict:
    problems = shape_problems(value, CONTRACT[schema])
    return login.check(check_id, 'hard', not problems,
                       f'{len(problems)} difference(s) from the customer contract: {"; ".join(problems[:10])}' if problems
                       else f'the {schema} payload carries every key the contract lists and nothing else')


class _Assets(HTMLParser):
    """The scripts and stylesheets a page loads, and how many inline scripts it holds."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.assets, self.scripts, self.inline, self._in_script, self._script_text = [], 0, 0, False, ''

    def handle_starttag(self, tag, attrs):
        attrs = {name: value or '' for name, value in attrs}
        if tag == 'script':
            if attrs.get('src'):
                self.scripts += 1
                self.assets.append(attrs['src'])
            else:
                self._in_script, self._script_text = True, ''
        elif tag == 'link' and attrs.get('href') and set(attrs.get('rel', '').lower().split()) & {'stylesheet', 'modulepreload', 'preload'}:
            self.assets.append(attrs['href'])

    def handle_data(self, data):
        if self._in_script:
            self._script_text += data

    def handle_endtag(self, tag):
        if tag == 'script' and self._in_script:
            self._in_script = False
            if self._script_text.strip():
                self.inline += 1


def page_assets(body: bytes) -> _Assets:
    parser = _Assets()
    parser.feed(body.decode('utf-8', 'replace'))
    parser.close()
    return parser


class Scanner:
    """The signed-in customer session and what it reads; every request is listed by the transport before it is made."""

    def __init__(self, transport, origin: str, jar: dict):
        self.transport, self.origin, self.jar = transport, origin, jar
        self.checks, self.hits = [], {'json': [], 'header': [], 'file': [], 'bundle': []}

    def get(self, where: str, accept: str = 'application/json', read_body: bool = True):
        return self.transport.send('GET', where, headers=login._headers(self.origin, accept, login.cookie_header(self.jar)),
                                   read_body=read_body)

    def bundle(self, ctx: ScanContext) -> None:
        page = self.get('/', 'text/html')
        self.checks.append(login.check('bundle.read', 'hard', page.status == 200, f'GET / answered HTTP {page.status}'))
        if page.status != 200:
            return
        scan_text(page.body.decode('utf-8', 'replace'), ctx, 'bundle', 'GET /', self.hits['bundle'])
        assets = page_assets(page.body)
        foreign = []
        for address in dict.fromkeys(assets.assets):
            parts = urlsplit(address)
            if parts.scheme or parts.netloc:
                if f'{parts.scheme}://{parts.netloc}' != self.origin:
                    foreign.append(address)
                    continue
            where = parts.path + (f'?{parts.query}' if parts.query else '')
            asset = self.get(where, '*/*')
            if asset.status != 200:
                self.checks.append(login.check('bundle.read', 'hard', False, f'GET {where} answered HTTP {asset.status}'))
                continue
            scan_text(asset.body.decode('utf-8', 'replace'), ctx, 'bundle', f'GET {where}', self.hits['bundle'])
        self.checks.append(login.check('bundle.one_script', 'hard', assets.scripts == 1 and assets.inline == 0 and not foreign,
                                       f'{assets.scripts} script(s) loaded by the customer page, {assets.inline} inline'
                                       + (f'; from another origin: {", ".join(foreign)}' if foreign else '')))

    def json_get(self, where: str, ctx: ScanContext):
        answer = self.get(where)
        scan_headers(answer.headers, ctx, f'GET {where}', self.hits['header'])
        data = answer.json()
        if data is None:
            scan_text(answer.body.decode('utf-8', 'replace'), ctx, 'json', f'GET {where} (not JSON)', self.hits['json'])
        else:
            scan_json(data, ctx, f'GET {where}', self.hits['json'])
        return answer, data

    def pdf(self, body: bytes, ctx: ScanContext, name: str, check_id: str, url: str) -> dict:
        """A PDF export read and scanned (read_pdf, scan_pdf): the check that says it was read, or why it was not."""
        try:
            reading = read_pdf(body)
        except Unreadable as exc:
            return login.check(check_id, 'hard', False, f'GET {url}: {exc}; it was not scanned')
        scan_pdf(reading, ctx, name, self.hits['file'])
        return login.check(check_id, 'hard', True, f'GET {url}: read as a PDF, {len(reading.pages)} page(s) of text and '
                                                   f'{len(reading.metadata)} document information value(s) scanned')

    def encounter(self, encounter_id: str, operator_dir: Path | None) -> dict:
        short = encounter_id[:8]
        operator, trace = None, None
        if operator_dir is not None:
            path = operator_dir / f'{encounter_id}.json'
            if path.is_file():
                operator = json.loads(path.read_text(encoding='utf-8'))
            traced = operator_dir / f'{encounter_id}.trace.json'
            if traced.is_file():
                trace = json.loads(traced.read_text(encoding='utf-8'))
        probe = scan_context()
        answer = self.get(f'/api/encounters/{encounter_id}')
        data = answer.json()
        text = ((operator or {}).get('revision') or {}).get('text') or quotations(data)
        ctx = scan_context(text, deny_values_from(operator, trace) if operator else (), [urlsplit(self.origin).hostname or ''])
        scan_headers(answer.headers, ctx, f'GET /api/encounters/{encounter_id}', self.hits['header'])
        record = {'id': encounter_id, 'status': answer.status, 'operator_view': operator is not None, 'reports': 0}
        if answer.status != 200 or not isinstance(data, dict):
            self.checks.append(login.check(f'encounter.{short}.read', 'hard', False, f'GET /api/encounters/{encounter_id} answered HTTP {answer.status}'))
            return record
        scan_json(data, ctx, f'GET /api/encounters/{encounter_id}', self.hits['json'])
        self.checks.append(check_contract(data, 'encounter', f'customer.contract.{short}'))
        for name, field in (('original', 'original_url'), ('view', 'view_url')):
            address = (data.get('document') or {}).get(field)
            if isinstance(address, str) and address.startswith('/'):
                got = self.get(address, '*/*', read_body=False)  # its headers: the document itself is the customer's own
                scan_headers(got.headers, ctx, f'GET {address}', self.hits['header'])
                self.checks.append(login.check(f'{name}.{short}', 'hard', got.status == 200, f'GET {address} answered HTTP {got.status}'))
        for report in data.get('reports') or []:
            url = report.get('download_url') if isinstance(report, dict) else None
            if not (isinstance(url, str) and url.startswith('/api/reports/')):
                self.checks.append(login.check(f'report.{short}.url', 'hard', False, f'a report with no customer download URL: {json.dumps(url)}'))
                continue
            got = self.get(url, '*/*')
            record['reports'] += 1
            scan_headers(got.headers, ctx, f'GET {url}', self.hits['header'])
            hashed = any(name.lower() == 'x-content-sha256' for name, _ in got.headers)
            self.checks.append(login.check(f'report.{short}.{report.get("kind")}.{report.get("fmt")}', 'hard', got.status == 200 and not hashed,
                                           f'GET {url} answered HTTP {got.status}' + ('; it carries X-Content-SHA256' if hashed else '')))
            if got.status == 200:
                name = f'{report.get("kind")}.{report.get("fmt")}'
                if report.get('fmt') == 'pdf' or is_pdf(got.body, got.content_type):
                    self.checks.append(self.pdf(got.body, ctx, name, f'report.{short}.{name}.text', url))
                else:
                    scan_file(got.body.decode('utf-8', 'replace'), ctx, name, report.get('fmt', 'txt'), self.hits['file'])
        wrong = []
        for template in OPS_GET_PATHS + REMOVED_PATHS:
            where = template.format(id=encounter_id)
            got = self.get(where)
            scan_text(got.body.decode('utf-8', 'replace'), probe if got.status == 404 else ctx, 'json', f'GET {where} ({got.status})', self.hits['json'])
            if got.status != 404:
                wrong.append(f'GET {where} -> {got.status}')
        self.checks.append(login.check(f'authorization.{short}', 'hard', not wrong, '; '.join(wrong)
                                       or f'{len(OPS_GET_PATHS) + len(REMOVED_PATHS)} operator and removed URL(s), each 404 to the customer'))
        return record


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--base-url', required=True, help='the CPT Studio origin, e.g. https://cpt.quillmd.com')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--credentials', type=Path, help='a private JSON file with top-level "username" and "password"')
    source.add_argument('--password-file', type=Path, help='a private file holding only the password (with --username)')
    parser.add_argument('--username', help='the account signed in with --password-file')
    parser.add_argument('--encounter', action='append', default=[], help='an encounter id to scan (repeatable)')
    parser.add_argument('--all', action='store_true', help='scan every encounter the list serves (at most --limit)')
    parser.add_argument('--limit', type=int, default=50, help='the most encounters --all scans (default 50)')
    parser.add_argument('--operator-json', type=Path, help='a directory of operator encounter JSON (<id>.json, <id>.trace.json)')
    parser.add_argument('--out', required=True, type=Path, help=f'the evidence directory (gets {EVIDENCE_NAME})')
    return parser.parse_args(argv)


def run(transport, origin: str, username: str, password: str, encounters: list, every: bool, limit: int,
        operator_dir: Path | None) -> dict:
    """The sign-in, the scans and the sign-out: {'checks', 'hits', 'encounters', 'signed_in', 'error'}."""
    jar, out = {}, {'checks': [], 'hits': {}, 'encounters': [], 'signed_in': False, 'error': None}
    try:
        page = transport.send('GET', login.LOGIN_PATH, headers=login._headers(origin, 'text/html'))
        login.apply_cookies(jar, page.set_cookies)
        hidden, problems = login.login_form(login.read_page(page.body), origin) if page.status == 200 else (None, [f'GET {login.LOGIN_PATH} answered HTTP {page.status}'])
        if problems:
            out['checks'].append(login.check('login.form', 'hard', False, '; '.join(problems)))
            return out
        fields = hidden + [('username', username), ('password', password)]
        answer = transport.send('POST', login.LOGIN_PATH, body=urlencode(fields).encode('utf-8'), headers=login._headers(
            origin, 'text/html', login.cookie_header(jar), form=True, referer=f'{origin}{login.LOGIN_PATH}'))
        login.apply_cookies(jar, answer.set_cookies)
        # the session cookie's name as the server serving now set it: release 1's __Host- one over https (B6), or an
        # earlier revision's plain one after a switch-back (refutation, rollback lens B-9)
        session = jar.get(login.served_cookie_names(jar, origin)[0])
        out['checks'].append(login.check('login.signed_in', 'hard', answer.status in (302, 303) and bool(session),
                                         f'POST {login.LOGIN_PATH} answered HTTP {answer.status}' + ('' if session else '; no session cookie was set')))
        if not session:
            return out
        out['signed_in'] = True
        scanner = Scanner(transport, origin, jar)
        try:
            base = scan_context(allowed=[urlsplit(origin).hostname or ''])
            scanner.bundle(base)
            reply, data = scanner.json_get(login.SESSION_PATH, base)
            scanner.checks.append(check_contract(data, 'session', 'session.contract') if reply.status == 200
                                  else login.check('session.contract', 'hard', False, f'GET {login.SESSION_PATH} answered HTTP {reply.status}'))
            listed, rows = scanner.json_get('/api/encounters', base)
            scanner.checks.append(check_contract(rows, 'list', 'customer.list_contract') if listed.status == 200
                                  else login.check('customer.list_contract', 'hard', False, f'GET /api/encounters answered HTTP {listed.status}'))
            named = list(dict.fromkeys(encounters))
            if every and isinstance(rows, dict):
                named += [row.get('id') for row in rows.get('encounters') or [] if isinstance(row, dict) and row.get('id') not in named][:max(0, limit)]
            for encounter_id in named:
                if not (isinstance(encounter_id, str) and UUID.match(encounter_id)):
                    scanner.checks.append(login.check('encounter.id', 'hard', False, f'not an encounter id: {json.dumps(encounter_id)}'))
                    continue
                out['encounters'].append(scanner.encounter(encounter_id, operator_dir))
            if not named:
                scanner.checks.append(login.check('encounters.scanned', 'soft', False, 'no encounter was named or listed, so none was scanned'))
        except Exception as exc:  # noqa: BLE001 - recorded; the sign-out below still runs
            out['error'] = str(exc) if isinstance(exc, login.RequestFailed) else f'{type(exc).__name__}: {exc}'
        out['checks'].extend(scanner.checks)
        for surface, what in (('json', 'the customer API bodies'), ('header', 'the customer response headers'),
                              ('file', 'the customer report downloads'), ('bundle', 'the served page and bundle')):
            out['checks'].extend(check_scan(f'scan.{surface}', scanner.hits[surface], what))
            out['hits'][surface] = scanner.hits[surface][:MAX_HITS]
        out['error'] = login.sign_out(transport, origin, jar, session, out['checks']) or out['error']
    except login.RequestFailed as exc:
        out['error'] = str(exc)
    return out


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        origin = login.origin_of(args.base_url)
        if args.password_file is not None:
            if not (args.username or '').strip():
                raise login.UsageError('--password-file needs --username, the account it signs in')
            username, password, mode = login.load_password_file(args.password_file, args.username)
        else:
            if args.username is not None:
                raise login.UsageError('--username goes with --password-file; a --credentials file names its own account')
            username, password, mode = login.load_credentials(args.credentials)
        bad = [item for item in args.encounter if not UUID.match(item)]
        if bad:
            raise login.UsageError(f'not an encounter id (a lowercase UUID): {", ".join(bad)}')
        if args.limit < 0:
            raise login.UsageError('--limit must not be negative')
        if args.operator_json is not None and not args.operator_json.is_dir():
            raise login.UsageError(f'--operator-json {args.operator_json} is not a directory')
        evidence_path = args.out / EVIDENCE_NAME
        if evidence_path.exists():
            raise login.UsageError(f'{args.out} already holds {EVIDENCE_NAME}; use a fresh --out directory')
    except login.UsageError as exc:
        print(f'scan_customer: {exc}', file=sys.stderr)
        return 2
    secret = login.Secret(password)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    started = login.utc_now()
    transport = login.Transport(origin)
    try:
        outcome = run(transport, origin, username, password, args.encounter, args.all, args.limit, args.operator_json)
    except Exception as exc:  # noqa: BLE001 - a defect of this tool: recorded (scrubbed), and the run fails
        outcome = {'checks': [], 'hits': {}, 'encounters': [], 'signed_in': None, 'error': f'{type(exc).__name__}: {exc}'}
    failed = [item['id'] for item in outcome['checks'] if item['status'] == 'fail']
    result = 'pass' if not outcome['error'] and not failed and outcome['checks'] else 'fail'
    posts = [item for item in transport.requests if item['method'] != 'GET']
    unexpected = [item for item in posts if item['path'] not in (login.LOGIN_PATH, login.LOGOUT_PATH)]
    evidence = {
        'schema': EVIDENCE_SCHEMA,
        'run_id': f'scan-{started.replace("-", "").replace(":", "").replace(".", "")}-{secrets.token_hex(4)}',
        'started_at': started, 'finished_at': login.utc_now(), 'base_url': origin, 'synthetic_only': True,
        'tool': {'python': platform.python_version()}, 'credentials': {'username': username, 'file_mode': f'{mode:04o}'},
        'requests': transport.requests, 'only_get_beyond_sign_in_and_out': not unexpected,
        'encounters': outcome['encounters'], 'checks': outcome['checks'], 'hits': outcome['hits'],
        'run_error': outcome['error'], 'result': result if not unexpected else 'fail',
    }
    login.write_evidence(evidence_path, evidence, secret)
    print(secret.scrub(f'customer scan of {origin} as {username}: {evidence["result"]}'
                       + (f' [{", ".join(failed)}]' if failed else '')
                       + (f' (run stopped: {outcome["error"]})' if outcome['error'] else '')))
    print(f'evidence: {evidence_path}')
    return 0 if evidence['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
