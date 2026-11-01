"""PDF extraction (ARCHITECTURE 5.1): the pypdf text layer page by page, OCR for
pages without a usable text layer, page spans over the final canonical text.

What a page shows is read, or the result says what was not read:

- **Text layer.** pypdf's text layer, with text in optional content that is
  hidden by default, and text drawn wholly outside the visible page area,
  removed (each named in the messages). Symbol fonts are read
  as the characters their glyphs show, check boxes as ☐ / ☒; glyphs that
  name no character (unmapped symbol glyphs, private-use or control codes)
  are counted and dropped, never shown as the letters that encode them
  (studio.ingest.pdffonts). Text pypdf cannot read as the PDF encodes it (a
  glyph-index font without a ToUnicode map among it) is never dropped: each
  character of it is U+FFFD in its place (the unread mark '[?]' alone in a
  box, or alone at the start of a checklist row), counted and named. A page
  whose readable text has fewer than ``min_text_chars_per_page`` non-whitespace
  characters has no usable text layer: it is OCRed when OCR is available; otherwise — or
  when OCR fails or time runs out — it is named and the result is 'partial'
  (other pages have text) or 'failed' (none does).
- **Scans with a short text layer.** A page mostly covered by images (by area,
  however the images are split, inline or nested) whose text is short — a
  stamp or a fax header over a scan — is treated like a page without a text
  layer: OCRed, or named and unread; an unread page keeps the text its layer
  holds, so the result is then 'partial', never 'failed' with that text
  thrown away. A page-sized image under a substantial text layer, any image
  of a million pixels or more, or dense images covering a fifth of the page
  or more beside one, is named. Images an annotation's appearance paints
  count like images in the page's content.
- **Forms and annotations.** Displayed form-field values and annotation text
  are read and added after the page's text under a labelled heading. A
  displayed check box or radio button over a printed box (☐ / ☒, '[ ]', '[x]':
  a checklist made fillable) replaces that box with its own state, unless the
  printed box shows a mark the widget's state denies; a FreeText or stamp that
  shows only a mark (X, ✓, ✔) over a printed box checks it. Where a printed
  box's state is not plainly what the page shows (a widget its printed mark
  contradicts, any other mark over it, a position that cannot be read under a
  widget or mark, two candidates for one printed box) it is written as the
  unread mark '[?]', which routing holds, and the result is 'partial'. A widget
  or mark is also over a printed box where it overlaps the box as drawn: its
  glyph across the box's width, past any whitespace its string opens with and
  the TJ numbers and strings of spaces before it, on its own piece's baseline (a
  box inside a piece of text, or starting one no operator placed, after a font
  change with no move, lies somewhere right of where that piece's operators
  draw); a check box or a mark that checks inside a box whose printed state it
  agrees with keeps the box as printed.
  Otherwise a displayed check box is written as ☐ / ☒ before the piece of page
  text it sits beside, when it can be tied to exactly one: its baseline lies
  within the box's height and it starts just right of the box, and every other
  button on that row is tied too (the shared box contract). An unchecked one
  writes '[?]' instead where it may be the label's to its left (page text there
  that is not a list marker; measured by where the text on each side ends, a
  row of options read before their words, "Biopsy taken: ☐ Yes ☒ No", is
  written as it shows, and boxes after their words, "Moderate [x] MAC [ ]", are
  not written as the next word's), and where the text line it is tied to runs
  on into another column: past a gap between the glyphs drawn (padding spaces
  draw nothing, inside a string as between strings, one whitespace glyph being a
  word space; a TJ number moves what follows it), or with text pypdf joined into
  the line from another baseline or from left of it, or that the layer cannot
  place or the page does not measure (a font that gives no widths). A
  radio button is written the same way before its own option word ("Biopsy
  taken: ☐ Yes ☒ No") when every button of its group can be. Notes,
  drawings and hidden annotations are counted; a field whose appearance
  disagrees with its value, or an annotation that cannot be read, makes the
  result 'partial'. XFA form content is not read: 'partial'.
- **Integrity.** A page count that disagrees with the page tree, a file that
  ends inside an unfinished incremental update, or no end-of-file marker
  fails the document. Bytes after the last end-of-file marker that carry no
  PDF data (whitespace, NUL, a DOS end-of-file byte, comment lines, repeated
  end-of-file markers) are padding, not an unfinished update. A page whose compressed content does not decode
  completely is named and the result is 'partial', as is a page read with
  OCR whose image's encoding cannot be checked to its end
  (studio.ingest.pdfcontent).

A document is never truncated: too many pages or too much text fails the
whole document.
"""
from __future__ import annotations

import contextlib
import heapq
import io
import itertools
import logging
import math
import os
import re
import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import pypdf
from pypdf import PasswordType
from pypdf.errors import DependencyError, LimitReachedError
from pypdf.generic import DictionaryObject, NullObject, StreamObject
from pypdf.generic._font import Font

from studio.types import ExtractionResult

from .ocr import OcrTools, ocr_page
from .pdfannots import PageAnnotations, read_annotations
from .pdffonts import (PAD_CHARS, SPACE, UNREAD, BoxGuard, composite_glyph, composite_map, kind, not_valid_text,
                       symbol_glyphs, undecodable)
from .symbols import BOX_PRINTED_PATTERN, CHECKED_BOX, UNCHECKED_BOX
from . import pdfcontent
from .pdfcontent import (IDENTITY, OptionalContent, PageContent, analyse_page, as_list, extraction_page, image_state,
                         multiply, number, object_key, raw_entry, readings_for, resolved, stream_damaged)
from .text import (INGEST_VERSION, REPLACEMENT, agree, caused_by, canonicalize, failed, format_seconds, from_memory,
                   join_pages, non_space_count, page_phrase, pdf_method, replace_surrogates)

if TYPE_CHECKING:
    from .extract import Limits

# OCR is not started for a page with less time than this left in the budget.
MIN_OCR_SECONDS = 1.0
# A page whose bitmap would be larger than this is not rendered for OCR: a
# 300 dpi letter page is 8.4 million pixels, a 20 x 20 inch page 36 million.
MAX_RENDER_PIXELS = 40_000_000
# An image this large beside a text layer may be scanned content that the text
# layer does not cover; logos and thumbnails are smaller.
LARGE_IMAGE_PIXELS = 1_000_000
# ... and so may dense images covering this share of the page, whatever their pixel count.
LARGE_IMAGE_COVERAGE = 0.2
# A page whose images cover at least this share of its area may be a scan.
SCAN_COVERAGE = 0.5
# ... and when its readable text is shorter than this, the text is a stamp or
# a header over the scan, not the scan's content: the page is read with OCR.
SCAN_TEXT_CHARS = 200
MAX_PAGE_TREE_NODES = 100_000
# A form check box is tied to a page-text line whose baseline lies within the box's height (give or take this
# many points) and whose text starts no further right of the box than BOX_GAP box sizes (within the bounds).
BOX_SLACK = 1.0
BOX_GAP, BOX_GAP_MIN, BOX_GAP_MAX = 3.0, 18.0, 48.0
# A box printed in the page text (a checklist made fillable): every unchecked spelling of the shared box vocabulary
# (a box glyph after symbol mapping, typed brackets with any padding), and the checked U+2612 and "[x]"
# (symbols.BOX_PRINTED_PATTERN; its groups 'off' and 'on' tell the printed state).
PRINTED_BOX = re.compile(BOX_PRINTED_PATTERN)
OVERLAP = ('{pages} {has} a form check box over a printed box whose position could not be read, so the box may show '
           'a different state than the text; check the original.')
# Where a printed box's state is not plainly what the page shows (a widget or a mark on it that disagrees with it or
# cannot be read as a check, a position that cannot be read, two candidates for it), the box is written as the unread
# mark of the box contract, which routing holds (studio.gi.detect._BOX_UNREAD): a state is never guessed.
_ING_UNREAD_BOX = '[?]'
_ING_UNREAD_NOTE = ('{pages} {has} a printed box whose state a form check box or a mark placed on or beside it '
                    'contradicts, or that could not be read as checked or not; it was written as unread ([?]), so '
                    'check the original.')
# A widget over a printed box may start right of the box glyph's origin by up to a quarter of its own size (and at
# most this many points): a box glyph's left side bearing puts its visible square there.
_ING_MAX_REACH = 4.0
# Cost bounds: distinct baselines one box's height may hold, and pieces or printed boxes examined for one box. Past
# them a box is not tied to text, and a widget or mark over printed boxes leaves every printed box on the page unread.
_ING_MAX_ROWS = 32
_ING_MAX_SCAN = 64
# A gap in a line of page text wider than this many font sizes (about two word spaces) after the piece a box is tied
# to, with no box before it, is a gap between columns: the box does not govern the text after it (_ING_Ink.runs_on).
_ING_COLUMN_GAP = 0.6
# The operators that show text (PDF 32000-1 9.4.3): where each draws is kept with the piece pypdf joins it into.
_I2_SHOWS = frozenset({b'Tj', b'TJ', b"'", b'"'})
# ... of which these show one string: a piece drawn by one of them alone is one string of ink.
_I2_ONE_STRING = frozenset({b'Tj', b"'", b'"'})
# The operators that set where the next text is drawn (PDF 32000-1 9.4.2, and BT): pypdf reports a piece at the place
# the last of them gave, so a piece that starts after text drawn since then (a font change, no move) is reported where
# that earlier text began, not where it is drawn.
_I2_MOVES = frozenset({b'BT', b'Td', b'TD', b'Tm', b'T*', b"'", b'"'})
# Page text left of a box that is only a list marker ('1.', '2)', '(a)', a bullet) is not a label for the box.
_ING_LIST_MARKER = re.compile(r'(?:[-*\u2022\u00b7\u25aa\u25e6\u25cf\u2023\u2043\u2013\u2014]|\(?[0-9]{1,3}[.)]|'
                              r'\(?[A-Za-z][.)])')

# PDF Reference, implementation notes: readers require the header within the
# first 1024 bytes and %%EOF within the last 1024. A file without them is
# truncated or not a PDF; parsers would "repair" it into fewer pages.
MARKER_WINDOW = 1024
PDF_WHITESPACE = b'\x00\t\n\x0c\r '

DAMAGED = 'The PDF could not be read; the file is damaged or is not a valid PDF.'
INCOMPLETE = 'The PDF is incomplete: it has no end-of-file marker. Upload the complete file.'
UNFINISHED = ('The PDF is incomplete: it ends with data after its last end-of-file marker, such as an unfinished '
              'update. Upload the complete file.')
UNANCHORED = ('The PDF is incomplete: its last revision has no cross-reference pointer (startxref), so only an '
              'earlier revision could be read. Upload the complete file.')
PASSWORD = 'The PDF is password-protected.'
AES_UNSUPPORTED = 'The PDF is encrypted with AES, which this server cannot decrypt.'
NO_TEXT = 'No text could be read from the PDF.'
INVALID_TAIL = '; they are shown as \ufffd.'  # how the invalid-text notice ends
UNREADABLE_TAIL = 'or as the unread mark [?] in a box, so check the original.'  # how the unreadable-text notice ends
OBJECTS_DAMAGED = ('The PDF is damaged: a compressed block of its objects could not be decoded completely, so '
                   'text may be missing or wrong.')
XFA = ('The PDF contains an XFA form; XFA content is not read, so form content that an XFA-capable viewer shows '
       'may be missing from the text.')
SECTIONS_LOST = ('The PDF is damaged: part of its cross-reference data could not be read, so objects it lists, and '
                 'any text they hold, may be missing.')
LIMIT_REACHED = ('The PDF could not be read: its structure goes past a limit this server applies to uploaded files '
                 '(such as the number of its cross-reference or page entries).')
# pypdf reports these through logging, not exceptions, and then reads less than the page holds.
DECODING_LOGGERS = ('pypdf.filters',)
DECODING_WARNINGS = ('Impossible to decode XFormObject', 'Detected cyclic form XObject', 'Expected StreamObject')
LIMIT_WARNINGS = ('Exceeded ',)  # pypdf stops drawing form XObjects after its invocation limit
# pypdf leaves out a cross-reference section it cannot read and goes on: objects it lists may be missing.
SECTION_WARNINGS = ('XRef object at ', 'Previous trailer cannot be read')
# pypdf 6.21.4 ignores a /DecodeParms that is not a dictionary and decodes with the filter's defaults: on an ASCII85,
# ASCIIHex, RunLength or LZW stream that is the whole stream (pdfcontent.stream_state checks it decodes to its end);
# on Flate it may drop a predictor, which stream_state names as damage, as pypdf 6.21.2's own warning did.
IGNORED_WARNINGS = ('Ignoring invalid DecodeParms',)


def extract_pdf(data: bytes, limits: Limits, tools: OcrTools | None, deadline: float,
                workdir: str) -> ExtractionResult:
    """``deadline`` (time.monotonic) bounds OCR work; ``workdir`` is a private directory."""
    engine = {'ingest': INGEST_VERSION, 'pypdf': pypdf.__version__}
    try:
        return _extract(data, limits, tools, deadline, workdir, engine)
    except DependencyError:
        # AES needs a crypto library pypdf could not import; it can surface on open or per object.
        return failed('pdf-text', engine, AES_UNSUPPORTED)


@dataclass
class _Page:
    layer: str  # canonical text-layer text, hidden optional content removed
    replaced: bool  # invalid characters were replaced with U+FFFD
    content: PageContent
    annotations: PageAnnotations
    block: str  # labelled form-field and annotation text ('' for none)
    damaged: bool
    limited: bool = False  # pypdf stopped reading form XObjects at its invocation limit
    undecodable: int = 0  # glyphs of the text layer that name no character, dropped
    placed: int = 0  # check-box glyphs written into the layer (not read from it)
    overlap: bool = False  # a check box may lie over a printed box whose position could not be read (or had too
    # much under it to read); two check boxes over one known box, or one over several, are named as unread_box
    unverified: bool = False  # read with OCR, and an image's encoding could not be checked to its end
    unread_box: bool = False  # a printed box was written unread: a widget or mark disagrees with it or is not a check
    # characters of its text (layer and labelled block) that could not be read as the PDF encodes them, each written
    # in its place as U+FFFD (or as the '?' of an unread mark); the page is named (partial)
    unread: int = 0
    held: int = 0  # of them, those written as U+FFFD: no readable text
    block_held: int = 0  # of those, the ones in the labelled block
    block_replaced: bool = False  # the labelled block holds text that is not valid (shown as U+FFFD)

    @property
    def text(self) -> str:
        """The page's readable text: its layer, then the labelled block."""
        if not self.block:
            return self.layer
        if not self.layer:
            return self.block
        return (self.layer if not self.layer or self.layer.endswith('\n') else self.layer + '\n') + '\n' + self.block

    @property
    def readable_chars(self) -> int:
        """Non-whitespace characters of what was read, without the labels and glyphs this module adds, nor U+FFFD where
        text could not be read (a page of nothing else has no usable text layer)."""
        return non_space_count(self.layer) - self.placed - self.held + sum(
            non_space_count(line) for line in self.annotations.fields + self.annotations.texts)

    @property
    def block_chars(self) -> int:
        """Non-whitespace characters of the labelled block that were read (its labels and U+FFFD where its text could
        not be read aside): form-field values and annotation text, read without the page's fonts, which no OCR of the
        page and no unusable layer takes away."""
        return sum(non_space_count(line) for line in self.annotations.fields + self.annotations.texts) - self.block_held


@dataclass
class _Ocr:
    texts: dict = field(default_factory=dict)  # page -> OCR text
    problems: dict = field(default_factory=dict)  # page -> problem fragment, None when time ran out


def _extract(data, limits, tools, deadline, workdir, engine) -> ExtractionResult:
    reader, problem, sections_lost = _open(data, limits)
    if problem:
        return failed('pdf-text', engine, problem)
    pages, problem = _page_list(reader, limits)
    if problem:
        return failed('pdf-text', engine, problem)
    count = len(pages)
    objects_damaged = _object_streams_damaged(reader)

    root = resolved(reader.trailer.get('/Root'))
    optional = OptionalContent(root)
    acroform = resolved(root.get('/AcroForm')) if isinstance(root, dict) else None
    xfa = resolved(acroform.get('/XFA')) if isinstance(acroform, dict) else None
    has_xfa = not isinstance(xfa, (type(None), NullObject))
    read = [_read_page(page, reader, optional, acroform, number) for number, page in enumerate(pages, 1)]

    no_layer = [n for n, page in enumerate(read, 1) if page.readable_chars < limits.min_text_chars_per_page]
    scanned = [n for n, page in enumerate(read, 1) if n not in no_layer
               and page.content.image_coverage >= SCAN_COVERAGE and page.readable_chars < SCAN_TEXT_CHARS]
    candidates = sorted(no_layer + scanned)
    layer_chars = sum(len(page.text) for n, page in enumerate(read, 1) if n not in candidates)
    if layer_chars > limits.max_chars:
        return failed('pdf-text', engine, _too_long(layer_chars, limits))

    ocr = _Ocr()
    if candidates and tools:
        ocr.texts, ocr.problems = _ocr_pages(data, {n: pages[n - 1] for n in candidates}, limits, tools, deadline,
                                             workdir)
        engine = engine | {'tesseract': tools.tesseract_version, 'pdftoppm': tools.pdftoppm_version}
    elif candidates:
        engine = engine | {'ocr': 'not available'}
    # A page read with OCR keeps its labelled block (form-field values and annotation text, read without its fonts):
    # the OCR text stands for its layer only.
    texts = [_with_block(ocr.texts[n], page.block) if n in ocr.texts else page.text for n, page in enumerate(read, 1)]
    for n in ocr.texts:  # the page's text came from its images: they must be whole
        page = read[n - 1]
        states = {image_state(image) for image in page.content.images}
        page.damaged = page.damaged or pdfcontent.DAMAGED in states
        page.unverified = pdfcontent.UNVERIFIED in states

    unavailable = [] if tools else candidates
    unread = sorted(set(unavailable) | set(ocr.problems))
    messages, partial = _messages(read, texts, no_layer, scanned, unavailable, ocr, limits)
    if objects_damaged:
        messages.append(OBJECTS_DAMAGED)
    if sections_lost:
        messages.append(SECTIONS_LOST)
    if has_xfa:
        messages.append(XFA)
    method = pdf_method(len(ocr.texts), count)

    # An unread page that may be a scan still had its text layer read: that text is kept, and it counts; so does an
    # unread page's labelled block (its form fields' values are read without its fonts).
    if not any(texts[n - 1].strip() for n in range(1, count + 1)
               if n not in unread or n in scanned or read[n - 1].block_chars > 0):
        # no text is returned, so nothing is shown as \ufffd: that notice would describe text the result does not hold
        return failed(method, engine, *(message for message in messages if not message.endswith(INVALID_TAIL)
                                        and not message.endswith(UNREADABLE_TAIL)), NO_TEXT)
    text, spans = join_pages(texts)
    if len(text) > limits.max_chars:
        return failed(method, engine, _too_long(len(text), limits))
    status = 'partial' if unread or partial or objects_damaged or sections_lost or has_xfa else 'ok'
    return ExtractionResult(status=status, method=method, text=text, pages=spans, messages=tuple(messages),
                            ocr_pages=tuple(sorted(ocr.texts)), engine=engine)


def _open(data: bytes, limits: Limits) -> tuple[pypdf.PdfReader | None, str, bool]:
    """(the reader, why the document cannot be read ('' when it can), whether pypdf left out a cross-reference
    section it could not read, so that objects it lists may be missing)."""
    if b'%PDF-' not in data[:MARKER_WINDOW]:
        return None, DAMAGED, False
    tail = data[-MARKER_WINDOW:]
    if b'%%EOF' not in tail:
        return None, INCOMPLETE, False
    last = len(data) - len(tail) + tail.rindex(b'%%EOF')
    if not _padding(data[last + len(b'%%EOF'):]):
        # An incremental update cut short leaves an earlier revision's %%EOF last in
        # the file, followed by the start of the update: a parser reads the old revision.
        return None, UNFINISHED, False
    end = last  # a run of end markers with only padding between them closes one revision (pypdf #4008)
    while (previous := data.rfind(b'%%EOF', 0, end)) >= 0 and _padding(data[previous + len(b'%%EOF'):end]):
        end = previous
    if b'startxref' in data[:end] and b'startxref' not in data[data.rfind(b'%%EOF', 0, end) + 1:end]:
        # The last revision has no startxref of its own: a parser would fall back to an earlier one.
        return None, UNANCHORED, False
    reader = None
    try:
        with _watching() as warnings:
            # pypdf reads the file as it ends at that revision's marker: the padding carries no PDF data.
            reader = pypdf.PdfReader(io.BytesIO(data[:end + len(b'%%EOF')]))
            if reader.is_encrypted and reader.decrypt('') == PasswordType.NOT_DECRYPTED:
                # pypdf 6.21.2 refused an encryption key length outside the standard before any password; 6.21.4
                # tries it, so a file no empty password opens is named as 6.21.2 named it, not 'password-protected'
                return None, PASSWORD if _key_length_valid(reader) else DAMAGED, False
            with contextlib.suppress(IndexError):  # no pages at all: reported by _page_list
                reader.get_page(0)  # flattens the page tree: a broken one fails here, not mid-document
    except (DependencyError, MemoryError):
        raise
    except LimitReachedError:  # pypdf stops at its structure limits: named as a limit, never as damage
        return None, _limit_problem(reader, limits), False
    except Exception as exc:  # any parser error on untrusted bytes means the file is unreadable
        if from_memory(exc):
            raise MemoryError from exc
        if caused_by(exc, LimitReachedError):  # pypdf wraps a limit hit while reading a trailer
            return None, _limit_problem(reader, limits), False
        return None, DAMAGED, False
    if _xref_limit_reached(reader):
        return None, _limit_problem(reader, limits), False
    return reader, '', warnings.sections


def _xref_limit_reached(reader) -> bool:
    """Whether pypdf 6.21.4 stopped reading a cross-reference stream at its entry limit and went on without it
    (it logs only that the section 'can not be read')."""
    counted = getattr(reader, '_xref_stream_entry_count', 0)
    limit = getattr(reader, '_xref_stream_maximum_entries', None)
    return isinstance(counted, int) and isinstance(limit, int) and counted > limit


def _limit_problem(reader, limits: Limits) -> str:
    """Why a document past one of pypdf's structure limits is not read: its page count when that is past the page
    limit (counted here, from the page tree), else the limit."""
    with contextlib.suppress(Exception):
        root = resolved(reader.trailer.get('/Root'))
        leaves = _leaf_count(root.raw_get('/Pages')) if isinstance(root, dict) and '/Pages' in root else None
        if leaves is not None and leaves > limits.max_pages:
            return f'The PDF has {leaves} pages; the limit is {limits.max_pages}.'
    return LIMIT_REACHED


def _key_length_valid(reader) -> bool:
    """Whether the encryption key length the file declares is one the standard allows (ISO 32000-1 7.6.2: 40 to 128
    bits in steps of 8; ISO 32000-2 7.6.6: 256), read as pypdf 6.21.2 read it: /Length (40 when absent), or the stream
    crypt filter's /Length in bytes (16 when absent) for AES-128."""
    try:
        encryption = resolved(reader.trailer.get('/Encrypt'))
        bits = int(number(encryption.get('/Length'), 40))
        if int(number(encryption.get('/V'))) == 4:
            filters, name = resolved(encryption.get('/CF')), resolved(encryption.get('/StmF'))
            crypt = resolved(filters.get(name)) if isinstance(filters, dict) and isinstance(name, str) else None
            if isinstance(crypt, dict) and resolved(crypt.get('/CFM')) == '/AESV2':
                bits = int(number(crypt.get('/Length'), 16)) * 8
    except Exception:
        return True
    return bits % 8 == 0 and (40 <= bits <= 128 or bits == 256)


def _padding(data: bytes) -> bool:
    """Whether ``data`` (bytes after an end-of-file marker) carries no PDF data: whitespace, NUL, DOS
    end-of-file bytes (0x1A) and whole comment lines, as producers append. An unfinished update starts with
    an object, an xref table or a trailer, never with these."""
    for line in data.replace(b'\r', b'\n').split(b'\n'):
        line = line.strip(PDF_WHITESPACE + b'\x1a')
        if line and not line.startswith(b'%'):
            return False
    return True


def _page_list(reader, limits) -> tuple[list, str]:
    """The pages of the page tree, walked — never the declared /Count, which pypdf trusts for
    encrypted files — or why the document cannot be read."""
    root = resolved(reader.trailer.get('/Root'))
    tree = root.raw_get('/Pages') if isinstance(root, dict) and '/Pages' in root else None
    leaves = _leaf_count(tree)
    pages = list(reader.flattened_pages or [])
    if leaves is None or leaves != len(pages):
        return [], DAMAGED
    declared = resolved(resolved(tree).get('/Count')) if isinstance(resolved(tree), dict) else None
    if isinstance(declared, int) and declared != leaves:
        return [], (f'The PDF is damaged: its page count says {_pages(declared)} but its page tree holds '
                    f'{_pages(leaves)}.')
    if not pages:
        return [], 'The PDF has no pages.'
    if len(pages) > limits.max_pages:
        return [], f'The PDF has {len(pages)} pages; the limit is {limits.max_pages}.'
    return pages, ''


def _object_streams_damaged(reader) -> bool:
    """Whether an object stream (compressed objects: pages, fonts, annotations) fails a strict decode;
    pypdf would read the objects it holds silently short."""
    numbers = {entry[0] for entry in (getattr(reader, 'xref_objStm', None) or {}).values()
               if isinstance(entry, (tuple, list)) and entry}
    for number in sorted(numbers):
        try:
            stream = reader.get_object(number)
        except (DependencyError, MemoryError):
            raise
        except Exception:
            return True
        if stream_damaged(stream) if hasattr(stream, 'get') else True:
            return True
    return False


def _pages(count: int) -> str:
    return f'{count} page' if count == 1 else f'{count} pages'


def _leaf_count(tree) -> int | None:
    """Leaf pages under ``tree``, counted by walking /Kids; None for a cycle or an oversized tree."""
    stack, seen, leaves = [tree], set(), 0
    while stack:
        reference = stack.pop()
        node = resolved(reference)
        if not isinstance(node, dict):
            continue
        key = object_key(reference)
        if key in seen or len(seen) >= MAX_PAGE_TREE_NODES:
            return None
        seen.add(key)
        kind = resolved(node.get('/Type'))
        if kind == '/Pages' or (kind is None and '/Kids' in node):
            stack.extend(reversed(as_list(node.get('/Kids'))))
        elif kind in (None, '/Page'):
            leaves += 1
    return leaves


class _DecodingWarnings(logging.Handler):
    """Notices pypdf decoding a stream with its recovery path, or skipping a form it cannot decode."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.seen = False  # a stream decoded only with repairs, or a form that could not be decoded
        self.limited = False  # forms past pypdf's invocation limit were not read
        self.sections = False  # a cross-reference section was left out (read while the file is opened)

    def emit(self, record) -> None:
        with contextlib.suppress(Exception):
            message = record.getMessage()
            if record.name.startswith(DECODING_LOGGERS):
                self.seen = self.seen or not message.startswith(IGNORED_WARNINGS)
                return
            self.seen = self.seen or message.startswith(DECODING_WARNINGS)
            self.limited = self.limited or message.startswith(LIMIT_WARNINGS)
            self.sections = self.sections or message.startswith(SECTION_WARNINGS)
            return
        self.seen = self.seen or record.name.startswith(DECODING_LOGGERS)  # a record whose message cannot be read


@contextlib.contextmanager
def _watching():
    handler = _DecodingWarnings()
    logger = logging.getLogger('pypdf')
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


def _read_page(page, reader, optional, acroform, number: int) -> _Page:
    with _watching() as warnings:
        content = analyse_page(page, reader, optional)
        # Text pypdf cannot read as the PDF encodes it (a string its CMap does not decode, a CMap pypdf does not
        # implement, a font it cannot build or the resources do not name) would reach the layer as U+FFFD and mojibake:
        # the walk read the operator showing it itself, each character it could not read pdffonts.UNREAD in its place
        # (pdfcontent._TextPlacement.transcribed), which is written as U+FFFD and named; the rest of the layer, in
        # fonts pypdf reads as the PDF encodes them, is read as pypdf reads it.
        layer = _layer_text(page, content, readings_for(reader))
        annotations = read_annotations(page, optional, acroform)
    if annotations.placements:  # images displayed annotations paint are on the page too
        content.placements.extend(annotations.placements)
        content.images.extend(image for image in annotations.images
                              if all(image is not known for known in content.images))
        content.__dict__.pop('image_coverage', None)
    text, placed, overlap, unread_box = _placed_boxes(layer, annotations, content.unread_boxes,
                                                      content.unread_box_glyphs)
    text, _ = replace_surrogates(text)
    block, _ = replace_surrogates(annotations.block(number))
    # Text that is not valid is shown as U+FFFD however it got there: a lone surrogate replaced here, or U+FFFD a
    # font's ToUnicode, a stored value or the reader's own decoding of one wrote. Text that could not be read as the PDF
    # encodes it (pdffonts.UNREAD) is U+FFFD too, in its place, counted and named on its own (UNREADABLE_TEXT).
    replaced = REPLACEMENT in text or REPLACEMENT in block
    block_replaced, block_held = REPLACEMENT in block, block.count(UNREAD)
    held = text.count(UNREAD) + block_held
    text, block = text.replace(UNREAD, REPLACEMENT), block.replace(UNREAD, REPLACEMENT)
    return _Page(layer=canonicalize(text), replaced=replaced, content=content,
                 annotations=annotations, block=block, damaged=content.damaged or warnings.seen,
                 limited=warnings.limited, undecodable=layer.undecodable, placed=placed + layer.marks,
                 overlap=overlap, unread_box=unread_box or bool(layer.marks or annotations.boxed),
                 unread=layer.unread + annotations.unread, held=held, block_held=block_held,
                 block_replaced=block_replaced)


def _placed_boxes(layer: _Layer, annotations: PageAnnotations, unread_text=(),
                  box_glyphs=()) -> tuple[str, int, bool, bool]:
    """The layer text with the page's displayed check boxes written in; how many characters that added (glyphs
    inserted, and what an unread mark adds over the box it replaces); whether a check box may lie over a printed box
    whose position could not be read, or had too much under it to read (OVERLAP; the page is then partial); and
    whether a printed box was written unread for any other reason, two check boxes over one printed box and one
    over several among them (named, partial):
    - a check box or radio button over a printed box (its baseline within the box's height, the glyph's origin
      within the widget's width, or up to a quarter of the widget's size left of it, give or take BOX_SLACK)
      replaces it with its own state, unless the printed box shows a mark the widget's state denies; a FreeText or
      stamp that shows only a mark (X, x, ✓, ✔) over one printed box checks it. Any other displayed annotation over
      a printed box (a field showing something included), a printed box whose position cannot be read under a widget
      or mark, two candidates for one printed box and a widget or mark over several leave those printed boxes unread
      ('[?]'). For the marks that are not checks, a printed box drawn inside a form XObject lies where the form places
      it on the page (the form's /Matrix and the CTM at its Do, through nesting); only one whose place cannot be read
      lies under any of them;
    - any other check box writes its glyph and a space before the piece of page text that starts nearest to its
      right on its baseline (within BOX_GAP; pieces on two lines compete, and then nothing is written), replacing a
      printed box that starts that piece (unread when the printed box shows a mark the box denies); a radio button
      before the piece that starts with its own option word, when every button of its group can be. A box that may
      be the label's to its left (_ING_labelled) writes '[?]' instead of '☐', as does an unchecked box before a text
      line that runs on into another column (_ING_Ink.runs_on). Nothing is written on a row holding a button that is
      not tied, and a piece two buttons claim gets neither: ambiguity is never resolved by guessing.
    Pieces and printed boxes are indexed by row and by x within each row, so a button reads only what lies beside or
    under it. An unchecked box on a row that holds text the reader could not read beside it (``unread_text``: where
    each such operator draws, pdfcontent.PageContent.unread_boxes; text lying under the box is its own printed box)
    writes '[?]' where that text may be its label (left of it, no piece of text that can be read starting between
    them) or lies right of it (between it and the piece it is tied to, or running on from that piece) (_I4_may_hold);
    text left of it beyond a piece that can be read holds neither (a bullet before an item whose options the boxes
    are, '� Diabetes: ☐ Yes ☒ No'). Last, every printed box is
    placed where it is drawn (_I2_Places: its glyph and width, or the piece that draws it), and a widget or mark over
    one that the readings above left decided leaves it unread (_I2_under_marks): holds only; and a glyph that could not
    be read at the start of a checklist row is the unread mark (_I4_lone_marks; ``box_glyphs``: where each operator
    whose glyphs are a box shape starts)."""
    text, widgets = layer.text, annotations.widgets
    starts = {offset: origin for offset, origin in layer.pieces if origin is not None and origin[2]}
    pieces = _ING_Rows((origin[1], origin[0], offset, None) for offset, origin in starts.items())
    piece_offsets = [offset for offset, _ in layer.pieces]
    line_offsets = [offset for offset, _ in layer.lines]
    known, inside, lost = [], [], []  # printed boxes: starting a piece; inside a piece on a placed line; elsewhere
    # Printed boxes drawn inside a form XObject are 'lost' to widgets and marks that check; marks that are not checks
    # read where the form places them, as for known and inside boxes, and only the rest (unplaced) anywhere.
    placed_starts = {offset: origin for offset, origin in layer.placed_pieces if origin[2]}
    placed_line = dict(layer.placed_lines)
    placed_known, placed_inside, unplaced = [], [], []
    for match in PRINTED_BOX.finditer(text):
        origin = starts.get(match.start())
        if origin is not None:
            known.append((origin[1], origin[0], match.start(), match))
            continue
        index = bisect_right(line_offsets, match.start()) - 1
        line = layer.lines[index][1] if index >= 0 else None
        if line is not None and line[2]:
            inside.append((line[1], line[0], match.start(), match))
            continue
        lost.append(match)
        at = placed_starts.get(match.start())
        if at is not None:
            placed_known.append((at[1], at[0], match.start(), match))
            continue
        at = placed_line.get(layer.lines[index][0]) if index >= 0 and line is None else None
        if at is not None and at[2]:
            placed_inside.append((at[1], at[0], match.start(), match))
        else:
            unplaced.append(match)
    known, inside = _ING_Rows(known), _ING_Rows(inside)
    placed_known, placed_inside = _ING_Rows(placed_known), _ING_Rows(placed_inside)
    placed_hide: dict[int, int] = {}  # as hide, for placed_inside
    edits: dict[int, tuple[int, str]] = {}  # start -> (end, replacement)
    hide: dict[int, int] = {}  # row of ``inside`` -> how many of its boxes, from the left of their lines, are unread
    overlap = named = lose_all = everything = False

    def unread(match) -> None:
        edits[match.start()] = (match.end(), _ING_UNREAD_BOX)

    def write(match, glyph: str) -> None:
        """A printed box replaced; two readings of it that disagree leave it unread."""
        nonlocal named
        held = edits.get(match.start())
        if held is not None and held[1] != glyph:
            named = named or held[1] != _ING_UNREAD_BOX
            glyph = _ING_UNREAD_BOX
        edits[match.start()] = (match.end(), glyph)

    def lying_under(rect, known=known, inside=inside, lost=lost):
        """(the known printed boxes ``rect`` lies over, the unknown-position ones that may lie under it: (row of
        ``inside``, how many from the left), whether a box whose line's place is unknown may), or None when there is
        too much to read."""
        x0, y0, x1, y1 = rect
        rows, maybe = known.around(y0, y1), inside.around(y0, y1)
        if rows is None or maybe is None:
            return None
        reach = min(_ING_MAX_REACH, max(BOX_SLACK, min(x1 - x0, y1 - y0) / 4))
        boxes = []
        for row in rows:
            if y0 - BOX_SLACK <= known.baselines[row] <= y1 + BOX_SLACK:
                span = known.span(row, x0 - reach, x1)
                if len(boxes) + len(span) > _ING_MAX_SCAN:  # counted before collecting: a wide window costs nothing
                    return None
                boxes.extend(known.rows[row][position][2] for position in span)
        hides = [(row, count) for row in maybe if (count := bisect_right(inside.xs[row], x1))]
        return boxes, hides, bool(lost)

    def unsettled_boxes(boxes, hides, anywhere) -> None:
        nonlocal lose_all
        for match in boxes:
            unread(match)
        for row, count in hides:
            hide[row] = max(hide.get(row, 0), count)
        lose_all = lose_all or anywhere

    over_a_box, claims = set(), {}
    by_widget = False  # a check box, not a mark, had too much under it to read (the page is then named as overlap)
    for i, w in enumerate(widgets):
        found = lying_under(w.rect)
        if found is None:
            everything = by_widget = True
            over_a_box.add(i)
            continue
        boxes, hides, anywhere = found
        if boxes or hides or anywhere:
            over_a_box.add(i)
            if len(boxes) == 1 and not hides and not anywhere:
                claims.setdefault(boxes[0].start(), []).append((i, boxes[0]))
            else:
                # Named by what is true: a box whose position could not be read may lie under it (OVERLAP); a check box
                # over several boxes at known places leaves them unread (the unread note).
                overlap = overlap or bool(hides or anywhere)
                named = named or len(boxes) > 1
                unsettled_boxes(boxes, hides, anywhere)
    replaced = set()
    for owners in claims.values():
        if len(owners) == 1:
            i, match = owners[0]
            if _ING_printed_on(match) and not widgets[i].on:  # the page shows a mark the widget's state denies
                unread(match)
                named = True
            else:
                write(match, CHECKED_BOX if widgets[i].on else UNCHECKED_BOX)
            replaced.add(i)
        else:
            named = True  # two check boxes over one printed box at a known place: unread, its position was read
            unread(owners[0][1])
    checked_by: dict[int, int] = {}  # mark index -> the printed box it checks
    for k, rect in enumerate(annotations.marks):
        found = lying_under(rect)
        if found is None:
            everything = True
            continue
        boxes, hides, anywhere = found
        if len(boxes) == 1 and not hides and not anywhere:
            write(boxes[0], CHECKED_BOX)
            checked_by[k] = boxes[0].start()
        elif boxes or hides or anywhere:
            named = True  # a mark over several boxes, or where a box's place cannot be read: no form check box
            unsettled_boxes(boxes, hides, anywhere)
    for rect in annotations.unread_marks:  # a pen tick, a drawn stamp, other typed text: not read as a check
        found = lying_under(rect)
        placed = lying_under(rect, placed_known, placed_inside, unplaced) if found and found[2] else None
        if found is None or (found[2] and placed is None):
            everything = True
            continue
        if placed is not None:  # boxes a form draws: those the mark may lie over, and every one whose place is unknown
            found = (found[0] + placed[0], found[1], placed[2])
            for row, count in placed[1]:
                placed_hide[row] = max(placed_hide.get(row, 0), count)
        if any(found) or (placed and placed[1]):
            named = True
            unsettled_boxes(*found)
    near: dict[int, int] = {}  # widget index -> offset of the piece nearest to its right, on one line
    beside_unread: set[int] = set()  # widgets beside text the reader could not read that may hold what they stand for
    unread_rows = _I3_Bands(unread_text)
    readable = _I4_Readable(text, pieces) if unread_rows.boxes else None
    groups: dict[int, list] = {}
    for i, w in enumerate(widgets):
        if i in over_a_box:
            continue
        x0, y0, x1, y1 = w.rect
        gap = min(BOX_GAP_MAX, max(BOX_GAP_MIN, BOX_GAP * max(x1 - x0, y1 - y0)))
        tie = _ING_beside(text, pieces, w, x1 - (x1 - x0) / 2, x1 + gap)
        if tie is not None:
            near[i] = tie
        # Text on the box's row that could not be read may be its label (left of it, no text that can be read
        # starting between them), or lie between it and the piece it is tied to, or run on from that piece: unchecked,
        # it is unsure there (it may hold that text, not the piece's). Text lying under the box is the printed box it
        # is drawn over, not text beside it; text left of it beyond a piece that can be read (a bullet before the item
        # whose options the boxes are) is neither (_I4_may_hold).
        if readable is not None:
            left = readable.left_of(w.rect)
            if unread_rows.beside(w.rect, lambda box, rect=w.rect, left=left: _I4_may_hold(box, rect, left)):
                beside_unread.add(i)
        if w.radio:
            groups.setdefault(w.group, []).append(i)
    ink = _ING_Ink(layer.ink, starts, near, widgets, layer) if near else None
    labelled = _ING_labelled(text, pieces, piece_offsets, widgets, near, starts, ink)
    ties = dict(near)
    for members in groups.values():  # a radio group is placed whole or not at all
        if not all(i in ties for i in members):
            for i in members:
                ties.pop(i, None)
    owners: dict[int, list] = {}
    for i, offset in ties.items():
        owners.setdefault(offset, []).append(i)
    ties = {i: offset for i, offset in ties.items() if len(owners[offset]) == 1}
    settled = set(ties) | replaced
    unsettled = _Rows(w.rect for j, w in enumerate(widgets) if j not in settled)
    if ink is not None:  # the pieces a box is written before: a line that reaches one goes on with the next option
        ink.stops = {offset for offset in ties.values() if not unsettled.holds(starts[offset][1])}
    for i, offset in ties.items():
        if unsettled.holds(starts[offset][1]):
            continue  # a row holding a button that is not tied gets no glyph
        on = widgets[i].on
        glyph = CHECKED_BOX if on else UNCHECKED_BOX
        box = PRINTED_BOX.match(text, offset)
        if box is None:
            # A box with a label to its left may be the label's: unchecked, it holds what it sits beside. An unchecked
            # box before a text line that runs on into another column holds that column's text too.
            unsure = not on and (i in beside_unread or i in labelled or ink.runs_on(offset, starts[offset]))
            edits[offset] = (offset, (_ING_UNREAD_BOX if unsure else glyph) + ' ')
        elif offset not in edits:  # a printed box starts the piece: never write two glyphs
            printed = _ING_printed_on(box)
            if printed != on and (printed or i in labelled):
                unread(box)
                named = True
            else:
                edits[offset] = (box.end(), glyph)
    if everything:  # too much to read: no printed box on the page is read as decided, named by what had too much
        overlap = overlap or by_widget
        named = named or not by_widget
        for match in [item[2] for row in known.rows for item in row] + [item[2] for row in inside.rows for item in row]:
            unread(match)
        lose_all = True
    for row, count in hide.items():
        for position in range(count):
            unread(inside.rows[row][position][2])
    for row, count in placed_hide.items():
        for position in range(count):
            unread(placed_inside.rows[row][position][2])
    if lose_all:
        for match in lost:
            unread(match)
    printed = [item[2] for row in known.rows for item in row] + [item[2] for row in inside.rows for item in row] + lost
    if printed and not everything and (widgets or annotations.marks or annotations.unread_marks):
        # Where each printed box is drawn (its glyph, across its width; or somewhere right of where its piece's
        # operators draw): a widget or mark over one that the readings above left decided leaves it unread, and so
        # does the box a widget or mark had written its own state into (two candidates). Holds only.
        held = {start for start, (_, replacement) in edits.items() if replacement == _ING_UNREAD_BOX}
        own = {i: owners[0][1].start() for owners in claims.values() if len(owners) == 1 for i, _ in owners}
        extra, more_named, more_overlap = _I2_under_marks(layer, printed, widgets, annotations, held, own, checked_by)
        for match in extra:
            unread(match)
        named, overlap = named or more_named, overlap or more_overlap
    # the unread mark where no other reading writes
    lone = _I3_unclaimed(_I4_lone_marks(text, starts, layer.drawn, edits, widgets, box_glyphs), edits)
    edits.update(lone)
    out, at, placed = [], 0, 0
    for start in sorted(edits):
        end, replacement = edits[start]
        if start < at:
            continue  # inside a printed box already replaced
        out.append(text[at:start])
        out.append(replacement)
        if start in lone:
            placed += non_space_count(replacement)  # the mark stands for a glyph that could not be read: none is text
        elif replacement.startswith(_ING_UNREAD_BOX):
            placed += non_space_count(replacement) - non_space_count(text[start:end])
        elif start == end:
            placed += 1
        at = end
    out.append(text[at:])
    return ''.join(out), placed, overlap, named


class _I3_Bands:
    """The vertical extents of some boxes (the glyphs of the text a page reader could not read), to ask whether any
    meets a button's row (give or take BOX_SLACK): sorted by their bottoms, with the highest top among each prefix, so
    each question costs one bisection, whatever the number of boxes and buttons."""

    def __init__(self, boxes):
        self.boxes = sorted((tuple(box) for box in boxes), key=lambda box: box[1])
        self.bottoms = [box[1] for box in self.boxes]
        self.tops = list(itertools.accumulate((box[3] for box in self.boxes), max))

    def meets(self, y0: float, y1: float) -> bool:
        """Whether a box's [bottom - BOX_SLACK, top + BOX_SLACK] meets [y0, y1]."""
        index = bisect_right(self.bottoms, y1 + BOX_SLACK)
        return index > 0 and self.tops[index - 1] >= y0 - BOX_SLACK

    def beside(self, rect, counts=None) -> bool:
        """Whether a box meets the band of ``rect`` (a button), as ``meets``, and reaches left or right of it by more
        than BOX_SLACK: text on the button's row, not the button's own printed box lying under it; with ``counts``,
        only a box for which counts(box) holds. Read from the box with the highest bottom down, while the highest top
        below still meets the band; past _ING_MAX_SCAN boxes, True (as if one were beside it), so each question costs a
        bisection and a bounded scan."""
        x0, y0, x1, y1 = rect
        index, read = bisect_right(self.bottoms, y1 + BOX_SLACK) - 1, 0
        while index >= 0 and self.tops[index] >= y0 - BOX_SLACK:
            box = self.boxes[index]
            if box[3] >= y0 - BOX_SLACK and (box[0] < x0 - BOX_SLACK or box[2] > x1 + BOX_SLACK) \
                    and (counts is None or counts(box)):
                return True
            read += 1
            if read > _ING_MAX_SCAN:
                return True
            index -= 1
        return False


def _I3_unclaimed(marks: dict, edits: dict) -> dict:
    """The ``marks`` ({start: (end, replacement)}) no edit of ``edits`` starts within: each asks the edits' sorted
    starts by bisection, so many marks beside many edits cost a logarithm each."""
    taken = sorted(edits)
    out = {}
    for start, (end, replacement) in marks.items():
        index = bisect_left(taken, start)
        if index == len(taken) or taken[index] > end:
            out[start] = (end, replacement)
    return out


class _I4_Readable:
    """Where each piece of page text that can be read starts (its first character not UNREAD), by row as ``pieces``
    (_ING_Rows) holds them: the nearest one left of a button on its rows costs a bisection a row."""

    def __init__(self, text: str, pieces: '_ING_Rows'):
        self.pieces = pieces
        self.xs = [[x for x, offset, _ in row if offset < len(text) and text[offset] not in (UNREAD, '\n')]
                   for row in pieces.rows]

    def left_of(self, rect) -> float | None:
        """Where the nearest piece that can be read starts left of ``rect`` (by more than BOX_SLACK) on its rows; None
        when none does, or past _ING_MAX_ROWS rows (as if none did: text that cannot be read there may be a label)."""
        x0, y0, x1, y1 = rect
        rows = self.pieces.around(y0, y1)
        best = None
        for row in rows or ():
            xs = self.xs[row]
            index = bisect_right(xs, x0 - BOX_SLACK) - 1
            if index >= 0 and (best is None or xs[index] > best):
                best = xs[index]
        return best


def _I4_may_hold(box, rect, left: float | None) -> bool:
    """Whether text that could not be read (``box``: where it is drawn, on the row of ``rect``, a button, and not
    under it) may hold what the button stands for: right of the button (between it and the piece it is tied to, or
    running on from that piece); or left of it with no piece of text that can be read starting between them (``left``:
    where the nearest such piece left of the button starts, _I4_Readable.left_of), so that it may be the button's
    label. Text further left, beyond a piece that can be read (a bullet before an item whose options the buttons are:
    '� Diabetes: ☐ Yes ☒ No'), is neither."""
    bx0, by0, bx1, by1 = box
    x0, y0, x1, y1 = rect
    if bx1 > x1 + BOX_SLACK:
        return True
    return bx0 < x0 - BOX_SLACK and (left is None or left < bx1 - BOX_SLACK)


_I4_RUN = 2  # the characters a box glyph that could not be read stands as: one, or two (a box and its padding in one
# string, a glyph-index box and its font's space, a box drawn twice for bold)


class _I4_Points:
    """Where some operators start on the page, to ask whether one starts within BOX_SLACK of a point: bucketed in cells
    BOX_SLACK wide, so each question reads the nine cells round it (and at most _ING_MAX_SCAN points)."""

    def __init__(self, points):
        self.cells: dict = {}
        for x, y in points:
            self.cells.setdefault((math.floor(x / BOX_SLACK), math.floor(y / BOX_SLACK)), []).append((x, y))

    def near(self, x: float, y: float) -> bool:
        if not self.cells:
            return False
        column, row, read = math.floor(x / BOX_SLACK), math.floor(y / BOX_SLACK), 0
        for cell in itertools.product((column - 1, column, column + 1), (row - 1, row, row + 1)):
            for px, py in self.cells.get(cell, ()):
                if abs(px - x) <= BOX_SLACK and abs(py - y) <= BOX_SLACK:
                    return True
                read += 1
                if read > _ING_MAX_SCAN:
                    return False
        return False


def _I4_row(text: str, first: int, end: int, starts: dict) -> tuple[int, str, int] | None:
    """(the end of what the unread mark replaces, the mark, where the row's label starts) for the run of at most
    _I4_RUN unread characters at ``first`` (the first thing on its line, which ends at ``end``) when it stands where a
    row's box stands: then padding and the row's text (not a box of its own) on the same line; or alone on its line,
    with the line after it starting where the page draws it, just right of the glyph on its baseline (``starts``: where
    each piece starts on the page), as pypdf writes a row whose glyph and label are drawn by separate operators that
    end their lines. None for anything else."""
    size, run = len(text), first
    while run < end and text[run] == UNREAD:
        run += 1
    if run - first > _I4_RUN:
        return None
    after = run
    while after < end and text[after] in PAD_CHARS:
        after += 1
    if run < after < end:
        return (run, _ING_UNREAD_BOX, after) if text[after] != UNREAD and not PRINTED_BOX.match(text, after) else None
    if after == end < size:
        label = end + 1
        while label < size and text[label] in PAD_CHARS:
            label += 1
        glyph, row = starts.get(first), starts.get(label)
        if glyph is not None and row is not None and label < size and text[label] not in (UNREAD, '\n') \
                and not PRINTED_BOX.match(text, label) and abs(row[1] - glyph[1]) <= BOX_SLACK \
                and 0 < row[0] - glyph[0] <= BOX_GAP_MAX:
            return label, _ING_UNREAD_BOX + ' ', label
    return None


def _I4_lone_marks(text: str, starts: dict, drawn: dict, edits: dict, widgets: list,
                   box_glyphs=()) -> dict[int, tuple[int, str]]:
    """{offset: (end, replacement)} writing the unread mark '[?]' for a glyph that could not be read (UNREAD, one or
    _I4_RUN of them: a box glyph's string may hold its padding, or the box be drawn twice) standing where a checklist
    row's box stands (_I4_row), only where the row is a checklist row:
    - its glyph is a box shape (``box_glyphs``: where each operator whose glyphs pdffonts.box_glyphs reads as a box
      starts on the page, matched to where the row's piece and the operators pypdf joined into it start: ``starts``,
      ``drawn``);
    - or a row of its list shows a box: a printed or typed box (PRINTED_BOX), a check box's glyph written there
      (``edits``, _placed_boxes' readings), or a glyph that is a box shape (a list: consecutive lines that are rows, a
      row whose glyph pypdf wrote on a line of its own taking its label's line, blank lines between them aside; any
      other line, a heading among them, ends it);
    - or an unchecked check box (``widgets``) lies on its row, tied to nothing there: read as listed, its item would be
      affirmed against the box; a checked one agrees with its item read as listed, and its glyph stays U+FFFD (NR-5);
    and never where a check box's state already governs it, as boxes the row shows of its own do: a printed box on its
    line or its label's, or a check box's glyph written there (a check box tied to the row's label, an edit at the
    label; or the item's options, '� Diabetes: ☐ Yes ☒ No', which routing reads, as it read them beside the installed
    reader's mojibake). Anything else (a bullet or list marker in a font that cannot be read, under a procedure list)
    is left as U+FFFD, its item as listed, as the installed reader's mojibake left it. The glyph is otherwise a box
    whose state cannot be read: written as U+FFFD it would leave its item to read as listed (affirmed); as the unread
    mark, on the item's line, the item is held. One pass over the lines, then one over the rows."""
    size, line, number = len(text), 0, 0
    taken = sorted(edits)
    shapes, rows = _I4_Points(box_glyphs), _I3_Bands(w.rect for w in widgets if not w.on)
    kinds: dict[int, bool | None] = {}  # line number -> a row (whether it shows a box), or None: a blank line
    candidates: list = []  # (line number, offset, end, mark, glyph a box shape, an unchecked box on its row, own boxes)

    def shows_box(start: int, stop: int) -> bool:
        """Whether text[start:stop] (one line) shows a printed box or holds an edit (a check box's glyph written)."""
        index = bisect_left(taken, start)
        return PRINTED_BOX.search(text, start, stop) is not None or (index < len(taken) and taken[index] <= stop)

    while line <= size:
        end = text.find('\n', line)
        end = size if end < 0 else end
        first = line
        while first < end and text[first] in PAD_CHARS:
            first += 1
        at = bisect_left(taken, line)
        boxed = first < end and (PRINTED_BOX.search(text, first, end) is not None
                                 or (at < len(taken) and taken[at] <= end))
        found = _I4_row(text, first, end, starts) if first < end and text[first] == UNREAD else None
        if found is not None:
            origin = starts.get(first)
            points = [origin, *(drawn.get(first) or ((),))[0]]
            shape = any(point is not None and shapes.near(point[0], point[1]) for point in points)
            own = boxed  # the row's own boxes: on its line, or on its label's line when that is the next
            if found[2] > end:
                stop = text.find('\n', found[2])
                own = own or shows_box(found[2], size if stop < 0 else stop)
            boxed = boxed or shape
            # a check box tied to the row's label writes its glyph there (an edit on the row): one of its own boxes
            candidates.append((number, first, found[0], found[1], shape,
                               origin is not None and rows.meets(origin[1], origin[1]), own))
            if found[2] > end:  # its label is the next line's: that line is the row's
                kinds[number + 1] = kinds.get(number + 1, False)
        if first >= end:
            kinds.setdefault(number, None)
        elif boxed or found is not None:
            kinds[number] = kinds.get(number, False) or boxed
        number += 1
        line = end + 1
    listed: dict[int, bool] = {}  # line number -> whether a row of its list shows a box
    block: list = []
    for index in range(number + 1):
        kind = kinds.get(index, 'text')
        if kind is None and block:
            continue  # a blank line inside a list
        if kind is None or kind == 'text':
            shows = any(kinds[member] for member in block)
            listed.update((member, shows) for member in block)
            block = []
            continue
        block.append(index)
    return {first: (end, mark) for number, first, end, mark, shape, checkbox, own in candidates
            if not own and (shape or checkbox or listed.get(number))}


def _I2_under_marks(layer: '_Layer', printed: list, widgets: list, annotations: PageAnnotations, held: set,
                    own: dict, checked: dict) -> tuple[list, bool, bool]:
    """The printed boxes (``printed``: every PRINTED_BOX match on the page) that a widget or mark lies over by where the
    box is drawn (_I2_Places), that _placed_boxes' own reading left decided (not in ``held``) and that are not the box
    the widget or check mark itself decided (``own`` / ``checked``: widget / mark index -> that box's start): a mark
    that is not a check over any of them, a check box or a mark that checks over one at a known place whose printed
    state it denies (one that agrees with the box shows what the box shows), or over one whose place is not read
    exactly; and the box the widget or mark decided, when such a box (held already or not) lies under it too: two
    candidates. Also whether the page is named as unread (a box at a known place under a check box, any box under a
    mark, a decided box withdrawn) or as OVERLAP (a box whose place is not read exactly under a check box). Where there
    is too much to read, every printed box on the page."""
    if not own and not checked:  # no box decided by a widget or mark: only boxes not held yet can change
        printed = [match for match in printed if match.start() not in held]
        if not printed:
            return [], False, False
    places = _I2_Places(layer, printed)
    by_start = {match.start(): match for match in printed}
    out: dict[int, object] = {}
    named = overlap = everything = False
    rects = ([(w.rect, own.get(i), True, w.on) for i, w in enumerate(widgets)]
             + [(rect, checked.get(k), False, True) for k, rect in enumerate(annotations.marks)]
             + [(rect, None, False, None) for rect in annotations.unread_marks])
    for rect, mine, widget, on in rects:
        found = places.under(rect)
        if found is None:  # too much to read: no printed box on the page is read as decided (once, at the end)
            everything = True
            overlap, named = overlap or widget, named or not widget
            continue
        exact, inside = ([match for match in group if match.start() != mine] for group in found)
        exact = [match for match in exact if on is None or _ING_printed_on(match) != on]
        if mine is not None and (exact or inside):  # the box it decided has a second candidate under it
            out[mine] = by_start[mine]
            named = True
        exact, inside = ([match for match in group if match.start() not in held] for group in (exact, inside))
        if not exact and not inside:
            continue
        for match in exact + inside:
            out[match.start()] = match
        named = named or bool(exact) or not widget
        overlap = overlap or (widget and bool(inside))
    return list(by_start.values() if everything else out.values()), named, overlap


class _I2_Places:
    """Where each printed box is drawn, read from the pieces that draw it (_Layer.drawn) and the page's ink: a box that
    starts a piece lies at the piece's first glyph drawn (after any whitespace its string opens with: the ink's first
    glyph that draws), across the box's own width (measured by the piece's font where it gives every character's
    width, else one em for a box glyph and 0.6 em for each character of a typed box); one whose glyph cannot be found
    there (the piece opens with whitespace and no measured ink starts it), one that starts a piece no operator placed
    (pypdf reports such a piece, after a font change with no move, where earlier text of its text object began), and
    one inside a piece, lie somewhere right of where each of the piece's operators draws, on that operator's baseline.
    A box that no piece places is left to _placed_boxes' own reading. Each piece is indexed once per baseline it draws
    on, and its boxes are looked up by the piece (_I2_boxes), so a piece drawn on many baselines costs its baselines
    plus its boxes, never their product."""

    def __init__(self, layer: '_Layer', printed: list):
        text, firsts = layer.text, sorted(layer.drawn)
        breaks = [k for k, char in enumerate(text) if char == '\n']  # a box and its piece share a line
        origins, placed = dict(layer.pieces), dict(layer.placed_pieces)
        ink = _ING_Rows((y, x, end, rest) for y, x, end, *rest in layer.ink)
        fonts: dict = {}
        exact, inside = [], []
        self._I2_boxes: dict = {}  # piece -> the boxes inside it (or not found where it starts), in text order
        for match in printed:
            start = match.start()
            index = bisect_right(firsts, start) - 1
            if index < 0 or bisect_right(breaks, firsts[index]) != bisect_right(breaks, start):
                continue
            first = firsts[index]
            shows, lead, font, em, _, positioned = layer.drawn[first]
            origin = origins.get(first) or placed.get(first)
            if origin is None or not origin[2]:
                continue
            record = self._ink_at(ink, origin) if first == start and positioned else None
            if first == start and positioned and (record is not None or not lead):
                x = max(origin[0], record[2][1]) if record is not None else origin[0]
                exact.append((origin[1], x, start, (x + self._width(match.group(0), font, em, record, fonts), match)))
                continue
            if first not in self._I2_boxes:
                self._I2_boxes[first] = []
                lowest: dict = {}  # baseline -> where the piece's operators on it start, leftmost
                for position in (origin, *shows):
                    if position is not None and position[2]:
                        key = round(position[1], 2)
                        lowest[key] = min(lowest.get(key, position[0]), position[0])
                inside.extend((y, x, first, None) for y, x in lowest.items())
            self._I2_boxes[first].append(match)
        self.exact, self.inside = _ING_Rows(exact), _ING_Rows(inside)
        self.widest = max((right - x for _, x, _, (right, _) in exact), default=0.0)

    @staticmethod
    def _ink_at(ink: '_ING_Rows', origin: tuple):
        """The measured string that starts where a piece starts (within BOX_SLACK), or None."""
        x, y, _ = origin
        for row in ink.around(y, y) or ():
            span = ink.span(row, x - BOX_SLACK, x + BOX_SLACK)
            if len(span):
                return ink.rows[row][span[0]]
        return None

    @staticmethod
    def _width(box: str, font, em: float | None, record, fonts: dict) -> float:
        """The width of a printed box drawn at ``em`` (one em, page space) in ``font``: its characters' widths where the
        font gives each of them, else one em for a glyph and 0.6 em for each character of a typed box."""
        size = em if em else (record[2][0] if record is not None else 12.0)
        if font is not None and id(font) not in fonts:
            try:
                fonts[id(font)] = Font.from_font_resource(font)
            except Exception:
                fonts[id(font)] = None
        widths = getattr(fonts.get(id(font)), 'character_widths', None) or {}
        if box and all(char in widths and char != 'default' for char in box):
            return sum(widths[char] for char in box) / 1000 * size
        return size * (1.0 if len(box) == 1 else 0.6 * len(box))

    def under(self, rect) -> tuple[list, list] | None:
        """(the boxes whose drawn width ``rect`` overlaps on their baseline, the boxes that may lie under it somewhere
        right of where their piece draws on a baseline its height holds), or None when there is too much to read."""
        x0, y0, x1, y1 = rect
        rows, maybe = self.exact.around(y0, y1), self.inside.around(y0, y1)
        if rows is None or maybe is None:
            return None
        exact, inside = [], []
        for row in rows:
            span = self.exact.span(row, x0 - self.widest - BOX_SLACK, x1)
            if len(span) > _ING_MAX_SCAN:
                return None
            for position in span:
                _, _, (right, match) = self.exact.rows[row][position]
                if right + BOX_SLACK > x0:
                    exact.append(match)
        for row in maybe:
            for position in range(bisect_right(self.inside.xs[row], x1)):  # the pieces drawing on it from x1 or left
                boxes = self._I2_boxes[self.inside.rows[row][position][1]]
                if len(exact) + len(inside) + len(boxes) > _ING_MAX_SCAN:  # each piece adds a box at least: bounded
                    return None
                inside.extend(boxes)
        return exact, inside


def _ING_printed_on(box) -> bool:
    """Whether a printed box (a PRINTED_BOX match) shows a mark: by the box vocabulary's own 'on' or 'off' group where
    it names one, else any box but the unchecked glyph and a pair of brackets with nothing in them."""
    groups = box.re.groupindex
    if 'on' in groups:
        return box.group('on') is not None
    if 'off' in groups:
        return box.group('off') is None
    found = box.group(0)
    return found != UNCHECKED_BOX and bool(found.strip('[]() \t\u00a0_'))


def _ING_beside(text: str, pieces: '_ING_Rows', w, low: float, high: float) -> int | None:
    """The offset of the piece of page text that starts nearest to the box's right (low <= x <= high) on its rows, a
    radio button's only when it starts with its own option word; None when there is none, when candidates lie on two
    lines, or when there is too much to read."""
    x0, y0, x1, y1 = w.rect
    rows = pieces.around(y0, y1)
    if rows is None:
        return None
    best, lowest, highest, scanned = None, None, None, 0
    for row in rows:
        y = pieces.baselines[row]
        for position in pieces.span(row, low, high):
            x, offset, _ = pieces.rows[row][position]
            if w.radio and not _starts_with_word(text, offset, w.option):
                scanned += 1
                if scanned > _ING_MAX_SCAN:
                    return None
                continue
            candidate = (x, y, offset)
            best = candidate if best is None else min(best, candidate)
            lowest, highest = (y, y) if lowest is None else (min(lowest, y), max(highest, y))
            break  # the row's nearest candidate
    if best is None or highest - lowest > 2 * BOX_SLACK:
        return None  # nothing beside it, or pieces on two lines compete
    return best[2]


def _ING_left_label(text: str, pieces: '_ING_Rows', piece_offsets: list, w) -> int | None:
    """The offset of the piece of page text nearest to the box's left on its rows when it may be the box's own label:
    neither a list marker nor a printed box; else None."""
    x0, y0, x1, y1 = w.rect
    rows = pieces.around(y0, y1)
    left = None
    for row in rows or ():
        position = bisect_left(pieces.xs[row], x1 - (x1 - x0) / 2) - 1
        if position >= 0:
            x, offset, _ = pieces.rows[row][position]
            left = max(left, (x, offset)) if left is not None else (x, offset)
    if left is None:
        return None
    word = _ING_piece_text(text, piece_offsets, left[1])
    if _ING_LIST_MARKER.fullmatch(word) or PRINTED_BOX.fullmatch(word):
        return None
    # a glyph that could not be read lying under the box (as _I4_row reads a row's box) is the printed box it is drawn
    # over, as a printed box that can be read is, not a label
    core = ''.join(char for char in word if char not in PAD_CHARS)
    return None if left[0] >= x0 - BOX_SLACK and 0 < len(core) <= _I4_RUN and set(core) == {UNREAD} else left[1]


def _ING_piece_text(text: str, piece_offsets: list, offset: int) -> str:
    """The text of the piece starting at ``offset``, up to the next piece or line break, stripped."""
    after = bisect_right(piece_offsets, offset)
    end = piece_offsets[after] if after < len(piece_offsets) else len(text)
    newline = text.find('\n', offset, end)
    return text[offset:end if newline < 0 else newline].strip()


def _ING_labelled(text: str, pieces: '_ING_Rows', piece_offsets: list, widgets: list, near: dict, starts: dict,
                  ink: '_ING_Ink | None') -> set:
    """The tied boxes that may be the label's to their left rather than the piece's they are tied to (unchecked, they
    write the unread mark). Each has a piece on its left that may be a label (_ING_left_label), and the piece it is
    tied to does not start with its own option word; then:
    - a box whose left piece no other box is tied to may be that label's (a box after its label), unless it is the
      first of a row of options read before their words: another box's left piece is the piece it is tied to, that
      piece does not end with a colon (which labels the next box), and the box sits closer to that piece than to the
      text on its left, by at least BOX_SLACK;
    - a box whose left piece another box is tied to (the next box of a row of options) may be that label's when it
      sits no closer to the piece on its right than to the text on its left (boxes after their option words, 'Moderate
      [x] MAC [ ]'); where the text on its left cannot be measured, when a box tied to its left piece may be its own
      label's."""
    left = {i: _ING_left_label(text, pieces, piece_offsets, widgets[i]) for i, offset in near.items()
            if not (widgets[i].option and _starts_with_word(text, offset, widgets[i].option))}
    claimers: dict[int, list] = {}  # piece offset -> boxes tied to it
    for i, offset in near.items():
        claimers.setdefault(offset, []).append(i)
    labels: dict[int, list] = {}  # piece offset -> boxes whose left label it is
    for i, offset in left.items():
        if offset is not None:
            labels.setdefault(offset, []).append(i)
    labelled: set = set()
    for i in sorted(left, key=lambda j: (widgets[j].rect[0], j)):  # a box's left neighbours first
        offset = left[i]
        if offset is None:
            continue
        tied = near[i]
        gap = ink.left_gap(widgets[i], starts[tied][1]) if ink is not None else None
        leading = gap is not None and gap - (starts[tied][0] - widgets[i].rect[2]) >= BOX_SLACK
        if offset not in claimers:
            first_of_options = any(j != i for j in labels.get(tied, ()))
            if not (first_of_options and leading and not _ING_piece_text(text, piece_offsets, tied).endswith(':')):
                labelled.add(i)
        elif gap is not None:
            if not leading:
                labelled.add(i)
        elif any(j in labelled for j in claimers[offset]):
            labelled.add(i)
    return labelled


class _ING_Ink:
    """The page's upright text as drawn (_Layer.ink) by row and x, to measure the gaps around tied boxes."""

    def __init__(self, ink, starts: dict, near: dict, widgets: list, layer: '_Layer | None' = None):
        # each string: (baseline, start, end, (font size, where its first and last glyphs that draw start and end, one
        # whitespace glyph's advance among those it opens or closes with, whether whitespace opens it)), as
        # PageContent.ink records it
        self.rows = _ING_Rows((y, x, end, rest) for y, x, end, *rest in ink)
        tied: dict[float, list] = {}  # baseline of a tied piece -> where the boxes tied on it start
        for i, offset in near.items():
            tied.setdefault(starts[offset][1], []).append(widgets[i].rect[0])
        self.tied = sorted((y, sorted(xs)) for y, xs in tied.items())
        self.tied_baselines = [y for y, _ in self.tied]
        self.layer = layer
        self.offsets = [offset for offset, _ in layer.pieces] if layer is not None else []
        self.origins = [origin for _, origin in layer.pieces] if layer is not None else []
        self.stops: set = set()  # offsets of the pieces a box is written before (set by _placed_boxes)
        self._I2_fonts: dict = {}  # id(font dict) -> whether the page measures text set in it (_I2_measured)

    def left_gap(self, w, baseline: float) -> float | None:
        """How far right of the end of the text nearest to its left, on the row at ``baseline``, the box starts; None
        when there is none there, when that text runs into the box, or when there is too much to read."""
        x0, y0, x1, y1 = w.rect
        rows = self.rows.around(baseline, baseline)
        nearest = None
        for row in rows if rows is not None else ():
            position = bisect_left(self.rows.xs[row], x1 - (x1 - x0) / 2) - 1
            if position >= 0:
                start, end, _ = self.rows.rows[row][position]
                nearest = max(nearest, (start, end)) if nearest is not None else (start, end)
        if nearest is None or nearest[1] > x0 + BOX_SLACK:
            return None
        return x0 - nearest[1]

    def runs_on(self, offset: int, origin: tuple) -> bool:
        """Whether the text line a box is tied to (the piece at ``offset``, drawn at ``origin``) runs on into text the
        box does not govern, before the next box of the line: text pypdf joined into the line from another baseline
        or from left of the piece, or that the layer cannot place or the page does not measure (_I2_joins); or a gap
        wider than _ING_COLUMN_GAP font sizes on its row, between the glyphs drawn (padding spaces draw nothing, inside
        a string, the box's own included, as between strings; a TJ number moves the glyphs after it; one whitespace
        glyph between two words is a word space). True when that cannot be read (the piece's text is not where the
        layer puts it, or more than _ING_MAX_SCAN strings or operators before an answer)."""
        x, y, _ = origin
        if self.layer is not None and self._I2_joins(offset, x, y):
            return True
        rows = self.rows.around(y, y)
        if rows is None:
            return True
        found = [self._from(row, bisect_left(self.rows.xs[row], x - BOX_SLACK)) for row in rows]
        found = found[0] if len(found) == 1 else heapq.merge(*found)
        first = next(found, None)
        if first is None or first[0] > x + BOX_SLACK:
            return True  # the piece's text is not where the layer puts it
        end, (size, _, drawn_end, space, _, inner) = first[1], first[2]
        if inner > _ING_COLUMN_GAP * size:
            return True  # padding inside the string the box is tied to: a gap between the glyphs drawn
        if self.layer is not None and self._I2_alone(offset):
            return False  # the line is one string alone: ink beyond it on the row is another line's
        low = bisect_left(self.tied_baselines, y - 2 * BOX_SLACK)
        high = bisect_right(self.tied_baselines, y + 2 * BOX_SLACK)
        rows_of_boxes = [boxes for _, boxes in self.tied[low:high]]
        trailing = space if drawn_end < end - 1e-9 else 0.0  # whitespace follows the last glyph drawn so far
        for count, (start, stop, (next_size, next_low, next_high, next_space, opens, inner)) in enumerate(found):
            if count >= _ING_MAX_SCAN:
                return True
            for boxes in rows_of_boxes:  # the next box of the row starts first: the line goes on with the next option
                before = bisect_right(boxes, start + BOX_SLACK)
                if before and x < boxes[before - 1] and boxes[before - 1] >= end - BOX_SLACK:
                    return False
            if start - end > _ING_COLUMN_GAP * size:
                return True
            word_space = max(trailing, next_space if opens else 0.0)
            if next_low - drawn_end - word_space > _ING_COLUMN_GAP * size:
                return True  # the gap the glyphs show (padded with spaces, or moved by a TJ's numbers)
            if inner > _ING_COLUMN_GAP * next_size:
                return True  # padding inside a later string of the line
            if stop > end:
                end, size = stop, next_size
            if next_high > drawn_end:
                drawn_end, trailing = next_high, (next_space if next_high < stop - 1e-9 else 0.0)
        return False

    def _I2_alone(self, offset: int) -> bool:
        """Whether nothing follows the box's piece (at ``offset``) on its text line and the piece is drawn by one
        operator that shows one string (Tj, ', "): whatever else is drawn on the row pypdf put on another line, or
        before the box on this one, neither of which the box governs. A gap inside that string is read before this
        (runs_on: padding inside the string the box is tied to)."""
        text = self.layer.text
        newline = text.find('\n', offset)
        end = len(text) if newline < 0 else newline
        later = bisect_right(self.offsets, offset)
        return ((later == len(self.offsets) or self.offsets[later] >= end)
                and self.layer.drawn.get(offset, ((), False, None, None, False, True))[4])

    def _I2_joins(self, offset: int, x: float, y: float) -> bool:
        """Whether pypdf joined into the text line of the box's piece (at ``offset``, drawn at (x, y)), after it and
        before the next piece a box is written before or that a printed box starts, text that is not that piece's
        continuation: drawn on another baseline (another column's line, or a wrapped cell's), left of the piece,
        where the layer cannot place it, not upright, or (a piece) where the page text is not measured, or set in a
        font that gives no widths (_I2_measured: pypdf reports a piece that follows a font change with no move where
        earlier text began, which other text's ink may share). Each operator pypdf joined in is read where it draws
        (_Layer.drawn)."""
        layer, text = self.layer, self.layer.text
        newline = text.find('\n', offset)
        end = len(text) if newline < 0 else newline
        scanned = 0

        def strays(positions) -> bool:
            nonlocal scanned
            for position in positions:
                scanned += 1
                if scanned > _ING_MAX_SCAN or position is None or not position[2]:
                    return True
                if abs(position[1] - y) > BOX_SLACK or position[0] < x - BOX_SLACK:
                    return True
            return False

        if strays(layer.drawn.get(offset, ((),))[0][1:]):
            return True
        for index in range(bisect_right(self.offsets, offset), len(self.offsets)):
            start = self.offsets[index]
            if start >= end or start in self.stops or PRINTED_BOX.match(text, start):
                return False
            origin = self.origins[index]
            if origin is None or strays([origin, *layer.drawn.get(start, ((),))[0]]):
                return True
            if not self._I2_measured(layer.drawn.get(start)):
                return True  # a font that gives no widths: where the piece is drawn, past a gap or not, is unknown
            rows = self.rows.around(origin[1], origin[1])
            if rows is None or not any(len(self.rows.span(row, origin[0] - BOX_SLACK, origin[0] + BOX_SLACK))
                                       for row in rows):
                return True  # no measured text where the piece starts
        return False

    def _I2_measured(self, drawn) -> bool:
        """Whether a piece (its _Layer.drawn entry) is set in a font the page measures, as PageContent.ink is: one that
        gives its glyphs' widths. pypdf reports a piece that follows another in its text object (after a font change,
        no move) at the place the text object was last moved to, which another piece's ink may start at; a piece whose
        own ink is never recorded is not read there. Read once per font."""
        font = drawn[2] if drawn else None
        if font is None:
            return False
        if id(font) not in self._I2_fonts:
            try:
                self._I2_fonts[id(font)] = pdfcontent._ING_widths_known(Font.from_font_resource(font))
            except Exception:
                self._I2_fonts[id(font)] = False
        return self._I2_fonts[id(font)]

    def _from(self, row: int, position: int):
        """The ink of ``row`` from ``position`` on, in x order."""
        items = self.rows.rows[row]
        return (items[k] for k in range(position, len(items)))


class _ING_Rows:
    """Items (baseline, x, key, value) in rows of one exact baseline, each row sorted by x (then key). A box's rows are
    found by bisecting the baselines, and what lies beside or under it by bisecting x within each row, so a crowded
    row costs a logarithm per box, not the whole row."""

    def __init__(self, items):
        rows: dict = {}
        for y, x, key, value in items:
            rows.setdefault(y, []).append((x, key, value))
        self.baselines = sorted(rows)
        self.rows = [sorted(rows[y], key=lambda item: (item[0], item[1])) for y in self.baselines]
        self.xs = [[item[0] for item in row] for row in self.rows]

    def around(self, y0: float, y1: float) -> range | None:
        """The rows whose baseline a box's height holds (give or take BOX_SLACK); None past _ING_MAX_ROWS of them."""
        low = bisect_right(self.baselines, y0 - BOX_SLACK - 1e-9)
        high = bisect_right(self.baselines, y1 + BOX_SLACK)
        return range(low, high) if high - low <= _ING_MAX_ROWS else None

    def span(self, row: int, x0: float, x1: float) -> range:
        """Positions in ``row`` of the items with x0 <= x <= x1."""
        xs = self.xs[row]
        return range(bisect_left(xs, x0), bisect_right(xs, x1))


class _Rows:
    """The union of the rows (heights, give or take BOX_SLACK) of some buttons."""

    def __init__(self, rects):
        merged: list = []
        for y0, y1 in sorted((r[1] - BOX_SLACK, r[3] + BOX_SLACK) for r in rects):
            if merged and y0 <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], y1)
            else:
                merged.append([y0, y1])
        self.starts = [m[0] for m in merged]
        self.ranges = merged

    def holds(self, baseline: float) -> bool:
        index = bisect_right(self.starts, baseline) - 1
        return index >= 0 and baseline <= self.ranges[index][1]


def _starts_with_word(text: str, offset: int, word: str) -> bool:
    """Whether the text at ``offset`` starts with ``word`` (any case), followed by no further letter."""
    return bool(word) and text[offset:offset + len(word)].lower() == word.lower() and not \
        text[offset + len(word):offset + len(word) + 1].isalnum()


@dataclass(frozen=True)
class _Layer:
    text: str = ''  # decoded text-layer text, before canonicalisation
    undecodable: int = 0  # glyphs that name no character, dropped
    marks: int = 0  # unread glyphs alone in a typed box, written as '?' (pdffonts.BoxGuard)
    unread: int = 0  # characters that could not be read (pdffonts.UNREAD): kept in place in ``text``, or in a mark
    lines: tuple = ()  # (offset in text, origin) of each line; origin (x, y, upright) when drawn by the page itself
    pieces: tuple = ()  # (offset, origin) of the first character (not a space) of each piece of text, as for lines
    ink: tuple = ()  # each string the page's upright text draws, as PageContent.ink records it
    # (offset, where it starts on the page) of each line and piece drawn inside a form XObject whose placement could
    # be read; ``lines`` and ``pieces`` give those None, and only marks that are not checks read these
    placed_lines: tuple = ()
    placed_pieces: tuple = ()
    # offset of each piece's first character (not a space) -> (where on the page each text-showing operator pypdf joined
    # into the piece draws, None where that is unknown; whether whitespace opens the piece; its font; one em along
    # its baseline, page space, or None; whether one operator showing one string draws it; whether an operator placed
    # it, so that its origin is where it is drawn): what a piece is drawn from, read by _ING_Ink and _placed_boxes
    drawn: dict = field(default_factory=dict)


def _layer_text(page, content: PageContent, readings=None) -> _Layer:
    """The page's text layer, decoded font by font (studio.ingest.pdffonts).

    pypdf reports each piece of text it writes with the font and the position
    it was drawn at; the pieces make up its output exactly, so the text is
    rebuilt from them, dropping glyphs that name no character. If the pieces
    ever disagree with the output, the output is read as text in an ordinary
    font. A page whose text layer cannot be parsed is treated as having none,
    so it goes to OCR (or is reported) instead of failing the whole document.
    """
    if content.operations is None:
        return _Layer()
    pieces: list = []
    page_resources = [None]
    # Form XObjects being read: their pieces are positioned in the form's own space, so each is kept with where the
    # form's content lands on the page ([matrix, resources, whether its own content is being read]; None: unknown).
    forms: list = []
    # Where each text-showing operator not yet flushed into a piece draws, on the page (None: unknown). pypdf moves
    # its text matrix only with the positioning operators, so this is where the operator's line or move put it.
    shows: list = []
    strings: list = []  # for each of ``shows``: whether its operator shows one string
    # Whether text has advanced the text position since the last positioning operator (_I2_MOVES), and, for the
    # piece being gathered, whether none had when its first text was shown: pypdf reports a piece where the last
    # positioning operator put the text, so a piece that starts after text drawn since then is not drawn there.
    advanced, placed_first = [False], []

    def placement():
        """The matrix that places what is drawn now on the page (IDENTITY on the page itself), or None."""
        if not forms:
            return IDENTITY
        return forms[-1][0] if forms[-1][2] else None

    def before(operator, operands, cm, tm):
        if forms and not forms[-1][2]:
            forms[-1][2] = True  # an operator of the form's own content: text visited from now on is the form's
        if operator == b'Do':
            outer = forms[-1] if forms else [IDENTITY, page_resources[0], True]
            forms.append([*_ING_form_space(operands, cm, outer[0], outer[1]), False])

    def after(operator, operands, cm, tm):
        if operator == b'Do' and forms:
            forms.pop()
        elif operator in _I2_SHOWS:
            if not shows:
                placed_first[:] = [operator in _I2_MOVES or not advanced[0]]  # ' and " move before they show
            matrix = placement()
            shows.append(_ING_placed(cm, tm, matrix) if matrix is not None else None)
            strings.append(operator in _I2_ONE_STRING)
        if operator in _I2_SHOWS or operator in _I2_MOVES:
            advanced[0] = operator in _I2_SHOWS  # a show (also ' and ", after their move) advances; a move resets

    def visit(text, cm, tm, font, size):
        if text:
            drawn = (tuple(shows), _I2_em(cm, tm, size, placement()), len(strings) == 1 and strings[0],
                     placed_first[0] if placed_first else True)
            if not forms:
                pieces.append((text, _origin(cm, tm), font, None, drawn))
            else:
                matrix = forms[-1][0] if forms[-1][2] else None
                pieces.append((text, None, font, _ING_placed(cm, tm, matrix) if matrix is not None else None, drawn))
        shows.clear()
        strings.clear()
        placed_first.clear()

    try:
        copy = extraction_page(page, content)
        with contextlib.suppress(Exception):
            page_resources[0] = copy.get_inherited('/Resources', None)  # as pypdf reads the page's resources
        raw = copy.extract_text(visitor_operand_before=before, visitor_operand_after=after, visitor_text=visit)
        if ''.join(piece[0] for piece in pieces) != raw:
            pieces = [(raw, None, None, None, ((), None, False, True))]
        decoded = _decoded(pieces, readings)  # inside the guard: a font it cannot classify leaves the page unread
    except (DependencyError, MemoryError):
        raise
    except Exception:
        return _Layer()
    ink, content.ink = tuple(content.ink), []  # read once, here: the page's other readers do not keep it
    return replace(decoded, ink=ink)


def _ING_form_space(operands, cm, outer, resources) -> tuple:
    """(the matrix that places on the page what the form a 'Do' draws draws, the form's resources), or (None, None)
    when that cannot be read: the form's /Matrix, times the CTM at the Do (in the space of the stream that draws it),
    times that stream's own placement ``outer``. The form is found as pypdf finds it, in ``resources``."""
    try:
        if outer is None or not operands or not isinstance(resources, DictionaryObject):
            return None, None
        xobjects = resolved(resources.get('/XObject'))
        xobject = resolved(raw_entry(xobjects, operands[0])) if isinstance(xobjects, DictionaryObject) else None
        if not isinstance(xobject, StreamObject) or resolved(xobject.get('/Subtype')) != '/Form':
            return None, None
        values = [float(number(value)) for value in as_list(xobject.get('/Matrix'))]
        own = tuple(values) if len(values) == 6 else IDENTITY
        inner = resolved(xobject.get('/Resources'))
        return (multiply(own, multiply(tuple(float(value) for value in cm), outer)),
                inner if isinstance(inner, DictionaryObject) else None)
    except (DependencyError, MemoryError):
        raise
    except Exception:
        return None, None


def _I2_em(cm, tm, size, matrix) -> float | None:
    """One em along the baseline, on the page, of text drawn at font size ``size`` with (cm, tm) (``matrix``: what
    places it on the page, as for _ING_placed); None when that cannot be read or the text is not upright."""
    if matrix is None:
        return None
    try:
        place = multiply(tuple(float(value) for value in cm), matrix)
        a, b, c, d = (float(value) for value in tm[:4])
        horizontal, vertical = a * place[0] + b * place[2], c * place[1] + d * place[3]
        em = float(size) * horizontal
    except (TypeError, ValueError, IndexError):
        return None
    return em if horizontal > 0 and vertical > 0 and em > 0 else None


def _ING_placed(cm, tm, matrix) -> tuple[float, float, bool] | None:
    """Where a piece of text drawn inside a form starts on the page (``matrix``: _ING_form_space's), as _origin."""
    try:
        return _origin(multiply(tuple(float(value) for value in cm), matrix), tm)
    except (TypeError, ValueError):
        return None


def _origin(cm, tm) -> tuple[float, float, bool] | None:
    """Where a piece of text starts, in default user space, and whether it is upright."""
    try:
        a, b, c, d, e, f = (float(v) for v in tm)
        a2, b2, c2, d2, e2, f2 = (float(v) for v in cm)
    except (TypeError, ValueError):
        return None
    m = (a * a2 + b * c2, a * b2 + b * d2, c * a2 + d * c2, c * b2 + d * d2, e * a2 + f * c2 + e2,
         e * b2 + f * d2 + f2)
    upright = m[0] > 0 and m[3] > 0 and abs(m[1]) <= 0.01 * m[0] and abs(m[2]) <= 0.01 * m[3]
    return m[4], m[5], upright


def _decoded(pieces, readings=None) -> _Layer:
    """The layer read from pypdf's pieces in one pass, keeping only what is written: a glyph that names no character
    is counted and dropped; pdffonts.UNREAD (a character of text pypdf cannot read as the PDF encodes it, which the
    page walk transcribed: pdfcontent) is counted and kept in its place, never dropped (the page reader writes it as
    U+FFFD), and pdffonts.SPACE is a space; and a typed box whose only content is unread glyphs (pdffonts.BoxGuard:
    ones that name no character, UNREAD, or text that is not valid) and padding is written as the contract's unread
    mark, its brackets round exactly '?' ('[?]', held): never '[]' (unchecked), '[\ufffd]' (a mark that checks it) or
    '[? ]' (which routing does not hold). What the box held is replaced once it closes; ``readings``: the document's
    pdffonts.FontReadings (each font's kind)."""
    out: list[str] = []
    size, dropped, unread, lines, starting, firsts = 0, 0, 0, [], True, []
    placed_lines, placed_firsts = [], []  # the same, for text drawn inside a form XObject placed on the page
    drawn: dict = {}  # as _Layer.drawn
    decoders: dict[int, object] = {}
    guard, marks = BoxGuard(), 0
    opener = (0, 0)  # (index in out, offset after it) of the item that opened the box being read
    for number, (text, origin, font, placed, (shows, em, single, positioned)) in enumerate(pieces):
        if id(font) not in decoders:
            decoders[id(font)] = _decoder(font, readings)
        decode = decoders[id(font)]
        first = True  # the piece's first character drawn (not a space) is drawn at its origin
        lead = False  # whitespace opens the piece (drawn, or pypdf's own between pieces)
        last = len(text) - 1
        for index, char in enumerate(text):
            mapped = char if char == UNREAD else ' ' if char == SPACE else decode(char, index == last)
            if mapped == UNREAD:
                unread += 1
            if mapped is None and char == ' ':
                continue  # a space may be pypdf's own, between pieces of text: padding
            opens = False  # whether this item opens a box
            if mapped is None or (len(mapped) == 1 and (mapped == UNREAD or not_valid_text(mapped))):
                # an unread glyph: one alone in a box (with padding, or more unread glyphs) is its unread mark
                if guard.opener and guard.pending is None:  # (its token is made only where it may be needed)
                    guard.unread((number, first, lead, origin, placed, (shows, font, em, single, positioned)))
                if mapped is None:
                    dropped += 1
                    continue
            else:
                closed = guard.text(mapped)
                if closed is not None:  # the box closes: what it held since its opener is the unread mark
                    piece, was_first, was_lead, at_origin, at_placed, (at_shows, *rest) = closed
                    marks += 1
                    del out[opener[0] + 1:]
                    size = opener[1]
                    while firsts and firsts[-1][0] >= size:  # a piece the box held starts no more
                        firsts.pop()
                    while placed_firsts and placed_firsts[-1][0] >= size:
                        placed_firsts.pop()
                    while drawn and next(reversed(drawn)) >= size:
                        drawn.popitem()
                    if was_first:  # the mark is the first character its piece draws
                        firsts.append((size, at_origin))
                        if at_origin is None and at_placed is not None:
                            placed_firsts.append((size, at_placed))
                        drawn[size] = (at_shows, was_lead, *rest)
                        if piece == number:
                            first = False
                    lead = False if first else lead  # what this piece wrote before was the box's, now gone
                    out.append('?')
                    size += 1
                opens = guard.opener and any(part not in PAD_CHARS for part in mapped)
            if mapped == '\n':
                out.append(mapped)
                size += 1
                starting, first = True, False
                continue
            if starting:
                lines.append((size, origin))
                if origin is None and placed is not None:
                    placed_lines.append((size, placed))
                starting = False
            if first and not mapped.isspace():
                firsts.append((size, origin))
                if origin is None and placed is not None:
                    placed_firsts.append((size, placed))
                drawn[size] = (shows, lead, font, em, single, positioned)
                first = False
            elif first:
                lead = True
            out.append(mapped)
            size += len(mapped)
            if opens:
                opener = (len(out) - 1, size)
    return _Layer(''.join(out), dropped, marks, unread, tuple(lines), tuple(firsts), placed_lines=tuple(placed_lines),
                  placed_pieces=tuple(placed_firsts), drawn=drawn)


def _decoder(font, readings=None):
    """(char, last in its piece) -> the character it stands for, or None for a glyph that names none."""
    style = (readings.kind(font) if readings is not None else kind(font)) if font is not None else 'text'
    if style == 'glyph-index':  # nothing it writes is a character: each glyph is text that cannot be read, in its
        # place (the page walk transcribes such text, pdffonts.decode_plan, so this is a guard); pypdf's own line
        # break ends a piece, and a space may be pypdf's own
        return lambda char, last: '\n' if char == '\n' and last else None if char == ' ' else UNREAD
    if style == 'symbol-composite':
        trusted, table = composite_map(font), symbol_glyphs(font) or {}
        return lambda char, last: composite_glyph(char, trusted, table)
    return lambda char, last: None if undecodable(char) else char


def _ocr_pages(data, pages, limits, tools, deadline, workdir) -> tuple[dict[int, str], dict[int, str | None]]:
    """OCR texts by page number, and problems by page number (None: the time budget ran out first)."""
    pdf_path = os.path.join(workdir, 'document.pdf')
    descriptor = os.open(pdf_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(data)
    texts, problems = {}, {}
    for number, page in pages.items():
        budget = deadline - time.monotonic()
        if budget < MIN_OCR_SECONDS:
            problems[number] = None
            continue
        too_large = _render_problem(page, limits.ocr_dpi)
        if too_large:
            problems[number] = too_large
            continue
        outcome = ocr_page(tools, pdf_path, number, dpi=limits.ocr_dpi,
                           timeout_s=min(limits.ocr_page_timeout_s, budget), workdir=workdir)
        if outcome.text is None:
            problems[number] = outcome.problem
        else:
            texts[number] = outcome.text
    return texts, problems


def _render_problem(page, dpi: int) -> str:
    """Why ``page`` must not be rendered at ``dpi``, or '' when it may be."""
    try:
        unit = float(page.user_unit)
        width_in, height_in = (abs(float(side)) * unit / 72 for side in (page.mediabox.width, page.mediabox.height))
    except Exception:  # an unreadable media box: the renderer decides, under the child's limits
        return ''
    if width_in * height_in * dpi * dpi <= MAX_RENDER_PIXELS:
        return ''
    return f'the page is too large to render: {width_in:.0f} × {height_in:.0f} inches'


# --- messages -----------------------------------------------------------------------

SCANNED = 'mostly covered by an image and {has} only a short text layer'
UNREADABLE_TEXT = ('{pages} {has} text in a font or encoding this server cannot read as the PDF encodes it; {count} '
                   '{stand} in its place as \ufffd, or as the unread mark [?] in a box, so check the original.')


def unreadable_note(pages, total: int) -> str:
    """The notice for text on ``pages`` that could not be read as the PDF encodes it, ``total`` characters standing in
    its place (U+FFFD, or the '?' of an unread mark). That is as many as pypdf would have written there, not a count of
    the glyphs the page draws (to pypdf, two bytes of a CMap it does not implement are one character), so the notice
    counts what stands in the text's place, never the text."""
    return UNREADABLE_TEXT.format(pages=page_phrase(pages), has=agree(pages, 'has', 'have'),
                                  count=f'{total:,} character{"" if total == 1 else "s"}',
                                  stand='stands' if total == 1 else 'stand')


def _messages(read, texts, no_layer, scanned, unavailable, ocr: _Ocr, limits) -> tuple[list[str], bool]:
    """User-facing messages, and whether anything beyond unread pages makes the result partial."""
    messages = []
    seconds = format_seconds(limits.timeout_s)
    ocr_pages = sorted(ocr.texts)
    if ocr_pages:
        messages.append(f'{page_phrase(ocr_pages)} {agree(ocr_pages, "was", "were")} read with OCR; '
                        'OCR can misread characters — check evidence against the original.')
    rescanned = [n for n in ocr_pages if n in scanned]
    if rescanned:
        messages.append(f'{_scanned_phrase(rescanned)}, so {agree(rescanned, "it was", "they were")} read with OCR '
                        'instead.')
    blank = [n for n in ocr_pages if not ocr.texts[n].strip()]
    if blank:
        messages.append(f'{page_phrase(blank)} {agree(blank, "has", "have")} no readable text (OCR found none).')
    plain = [n for n in unavailable if n in no_layer]
    if plain:
        messages.append(f'{page_phrase(plain)} {agree(plain, "has", "have")} no usable text layer '
                        'and OCR is not available on this server.')
    covered = [n for n in unavailable if n in scanned]
    if covered:
        messages.append(f'{_scanned_phrase(covered)} (for example a stamp or a fax header), so '
                        f'{agree(covered, "it may be a scan", "they may be scans")}; OCR is not available on this '
                        f'server, so the {agree(covered, "image was", "images were")} not read.')
    timed_out = [n for n, problem in sorted(ocr.problems.items()) if problem is None]
    plain = [n for n in timed_out if n in no_layer]
    if plain:
        messages.append(f'{page_phrase(plain)} {agree(plain, "has", "have")} no usable text layer and '
                        f'{agree(plain, "was", "were")} not read: the {seconds}-second extraction time limit was '
                        'reached.')
    covered = [n for n in timed_out if n in scanned]
    if covered:
        messages.append(f'{_scanned_phrase(covered)}, and {agree(covered, "was", "were")} not read: the '
                        f'{seconds}-second extraction time limit was reached.')
    for n, problem in sorted(ocr.problems.items()):
        if problem is not None:
            reason = 'has no usable text layer' if n in no_layer else 'is ' + SCANNED.format(has='has') + ','
            messages.append(f'Page {n} {reason} and OCR could not read it ({problem}).')
    imaged = [n for n, page in enumerate(read, 1) if n not in no_layer and n not in scanned
              and (page.content.largest_image_pixels >= LARGE_IMAGE_PIXELS
                   or page.content.image_coverage >= LARGE_IMAGE_COVERAGE)]
    if imaged:
        messages.append(f'{page_phrase(imaged)} {agree(imaged, "combines", "combine")} a text layer with a large '
                        'image; only the text layer was read, so check the text against the original if the image '
                        'holds text.')
    # Notices about the page's own text are for pages whose layer is returned; a page read with OCR keeps only its
    # labelled block (_with_block), so those about the block are for it too.
    invalid = [n for n, page in enumerate(read, 1)
               if (page.replaced if n not in ocr.texts else page.block_replaced)]
    if invalid:
        messages.append(f'{page_phrase(invalid)} {agree(invalid, "contains", "contain")} characters the PDF does '
                        f'not encode as valid text{INVALID_TAIL}')
    unmapped = [(n, count) for n, page in enumerate(read, 1)
                if (count := page.undecodable + page.annotations.undecodable if n not in ocr.texts
                    else page.annotations.undecodable if page.block else 0)]
    if unmapped:
        pages, total = [n for n, _ in unmapped], sum(count for _, count in unmapped)
        one = total == 1
        messages.append(f'{page_phrase(pages)} {agree(pages, "has", "have")} {total:,} character{"" if one else "s"} '
                        f'that {"does" if one else "do"} not map to text (symbol-font glyphs, private-use or control '
                        f'codes); {"it was" if one else "they were"} not extracted.')
    # Text in a font or encoding pypdf cannot read as the PDF encodes it, kept in its place as U+FFFD wherever the page's
    # own text is returned (on a page read with OCR, only its labelled block's).
    unreadable = [(n, count) for n, page in enumerate(read, 1)
                  if (count := page.unread if n not in ocr.texts else page.annotations.unread if page.block else 0)]
    if unreadable:
        messages.append(unreadable_note([n for n, _ in unreadable], sum(count for _, count in unreadable)))
    damaged = [n for n, page in enumerate(read, 1) if page.damaged]
    if damaged:
        its = agree(damaged, 'its', 'their')
        messages.append(f'{page_phrase(damaged)} {agree(damaged, "is", "are")} damaged: part of {its} content could '
                        f'not be decoded, so {its} text may be incomplete or wrong.')
    unchecked = [n for n, page in enumerate(read, 1) if page.unverified and not page.damaged]
    if unchecked:
        messages.append(f'{page_phrase(unchecked)} {agree(unchecked, "was", "were")} read with OCR, but '
                        f'{agree(unchecked, "its image", "their images")} could not be checked for completeness, so '
                        f'{agree(unchecked, "its", "their")} text may be incomplete.')
    overlapped = [n for n, page in enumerate(read, 1) if page.overlap and n not in ocr.texts]
    if overlapped:
        messages.append(OVERLAP.format(pages=page_phrase(overlapped), has=agree(overlapped, 'has', 'have')))
    unread_boxes = [n for n, page in enumerate(read, 1) if page.unread_box and n not in ocr.texts]
    if unread_boxes:
        messages.append(_ING_UNREAD_NOTE.format(pages=page_phrase(unread_boxes),
                                                has=agree(unread_boxes, 'has', 'have')))
    limited = [n for n, page in enumerate(read, 1) if page.limited]
    if limited:
        messages.append(f'{page_phrase(limited)} {agree(limited, "draws", "draw")} more form objects than the '
                        f'extractor reads; the rest of {agree(limited, "its", "their")} text was not read.')
    layered = [n for n, page in enumerate(read, 1) if page.content.hidden_text or page.annotations.hidden_text]
    if layered:
        messages.append(f'{page_phrase(layered)} {agree(layered, "has", "have")} text in a layer that is hidden by '
                        'default (optional content); that text was not extracted.')
    outside = [n for n, page in enumerate(read, 1) if page.content.offpage_text]
    if outside:
        messages.append(f'{page_phrase(outside)} {agree(outside, "has", "have")} text placed outside the visible page '
                        'area; that text was not extracted.')
    clipped = [n for n, page in enumerate(read, 1) if page.content.clipped_text]
    if clipped:
        messages.append(f'{page_phrase(clipped)} {agree(clipped, "has", "have")} text outside the area its clipping '
                        'path or form box shows; that text was not extracted.')
    # Marks that change what the page says (studio.ingest.pdfannots), also over a page read with OCR, which reads
    # struck-through text as written. Checked before 'obscured': an undecidable check names the page there.
    marked = [n for n, page in enumerate(read, 1) if page.annotations.marked
              or (n not in ocr.texts and page.content.covered_by(page.annotations.covers))]
    if marked:
        messages.append(f'{page_phrase(marked)} {agree(marked, "has", "have")} strike-out, redaction or cover-up marks '
                        'added as PDF annotations; the text under them was read as written, so check it against the '
                        'original.')
    obscured = [n for n, page in enumerate(read, 1) if page.content.obscured_text and n not in ocr.texts]
    if obscured:
        messages.append(f'{page_phrase(obscured)} {agree(obscured, "has", "have")} text that a viewer may not show '
                        '(white on the page, painted over, or clipped in a way that could not be checked); it was '
                        'read, so check it against the original.')
    struck = [n for n, page in enumerate(read, 1) if page.content.struck_text and n not in ocr.texts]
    if struck:
        messages.append(f'{page_phrase(struck)} {agree(struck, "has", "have")} text struck through by a line drawn '
                        'across it; it was read as written, so check it against the original.')
    annotation_partial = _annotation_messages(read, {n for n in ocr.texts if not read[n - 1].block}, messages)
    return messages, bool(unreadable or damaged or unchecked or limited or overlapped or unread_boxes or marked
                          or obscured or struck) or annotation_partial


def _with_block(text: str, block: str) -> str:
    """A page's text from OCR, then its labelled block, joined as _Page.text joins the layer and the block."""
    if not block:
        return text
    if not text:
        return block
    return (text if text.endswith('\n') else text + '\n') + '\n' + block


def _scanned_phrase(pages) -> str:
    return f'{page_phrase(pages)} {agree(pages, "is", "are")} ' + SCANNED.format(has=agree(pages, 'has', 'have'))


def _annotation_messages(read, ocred: set, messages: list) -> bool:
    """Messages about forms and annotations; True when one of them makes the result partial."""
    shown = [(n, page.annotations) for n, page in enumerate(read, 1) if n not in ocred]
    after = lambda pages: 'the page text' if len(pages) == 1 else "each page's text"  # noqa: E731
    fielded = [n for n, found in shown if found.fields]
    if fielded:
        messages.append(f'{page_phrase(fielded)} {agree(fielded, "has", "have")} PDF form fields; their values were '
                        f'read and added after {after(fielded)}, labelled as form fields.')
    annotated = [n for n, found in shown if found.texts]
    if annotated:
        messages.append(f'{page_phrase(annotated)} {agree(annotated, "has", "have")} text added as PDF annotations; '
                        f'it was read and added after {after(annotated)}, labelled as annotation text.')
    mismatched = [(n, label) for n, found in shown for label in found.mismatched]
    for n, label in mismatched:
        if label == 'text annotation':
            messages.append(f'Page {n}: a text annotation shows text that differs from its stored text; the stored '
                            'text was read, so check it against the original.')
        else:
            messages.append(f'Page {n}: form field "{label}" shows text that differs from its stored value; the '
                            'stored value was read, so check it against the original.')
    unreadable = [n for n, found in shown if found.unreadable]
    if unreadable:
        messages.append(f'{page_phrase(unreadable)} {agree(unreadable, "has", "have")} a form field or annotation '
                        'whose text could not be read.')
    hidden = [n for n, page in enumerate(read, 1) if page.annotations.hidden]
    if hidden:
        messages.append(f'{page_phrase(hidden)} {agree(hidden, "has", "have")} hidden form fields or annotations; '
                        'their text was not extracted.')
    drawn = [n for n, found in shown if found.drawn]
    if drawn:
        messages.append(f'{page_phrase(drawn)} {agree(drawn, "has", "have")} handwriting, drawings or stamps added as '
                        'PDF annotations; they are not text, so check the original.')
    notes = sum(page.annotations.note_chars for page in read)
    if notes:
        messages.append(f'Comment text in PDF annotations is not extracted ({notes:,} character'
                        f'{"" if notes == 1 else "s"}).')
    return bool(mismatched or unreadable)


def _too_long(chars: int, limits: Limits) -> str:
    return f'The extracted text has {chars:,} characters; the limit is {limits.max_chars:,}.'
