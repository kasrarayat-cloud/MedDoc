"""PDF extraction (ARCHITECTURE 5.1): the pypdf text layer page by page, OCR for
pages without a usable text layer, page spans over the final canonical text.

What a page shows is read, or the result says what was not read:

- **Text layer.** pypdf's text layer, with text in optional content that is
  hidden by default, and text drawn wholly outside the visible page area,
  removed (each named in the messages). Symbol fonts are read
  as the characters their glyphs show, check boxes as ☐ / ☒; glyphs that
  name no character (unmapped symbol glyphs, private-use or control codes,
  glyph-index fonts without a ToUnicode map) are counted and dropped, never
  shown as the letters that encode them (studio.ingest.pdffonts). A page whose readable
  text has fewer than ``min_text_chars_per_page`` non-whitespace characters
  has no usable text layer: it is OCRed when OCR is available; otherwise — or
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
  displayed check box over a printed box (☐ / ☒, '[ ]', '[x]': a checklist
  made fillable) replaces that box with its own state; a FreeText or stamp
  that shows only a mark (X, ✓, ✔) over a printed box checks it; a check box
  over a printed box whose position cannot be read makes the result
  'partial'. Otherwise a displayed check box is written as ☐ / ☒ before the
  piece of page text it sits beside, when it can be tied to exactly one: its
  baseline lies within the box's height and it starts just right of the box,
  and every other button on that row is tied too (the shared box contract). A
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
import io
import logging
import os
import re
import time
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pypdf
from pypdf import PasswordType
from pypdf.errors import DependencyError
from pypdf.generic import NullObject

from studio.types import ExtractionResult

from .ocr import OcrTools, ocr_page
from .pdfannots import PageAnnotations, read_annotations
from .pdffonts import composite_glyph, composite_map, kind, symbol_glyphs, undecodable
from .symbols import CHECKED_BOX, UNCHECKED_BOX
from . import pdfcontent
from .pdfcontent import (OptionalContent, PageContent, analyse_page, as_list, extraction_page, image_state,
                         object_key, resolved, stream_damaged)
from .text import (INGEST_VERSION, agree, canonicalize, failed, format_seconds, join_pages, non_space_count,
                   page_phrase, pdf_method, replace_surrogates)

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
# A box printed in the page text (a checklist made fillable): a box glyph after symbol mapping, or typed brackets.
PRINTED_BOX = re.compile(r'[' + UNCHECKED_BOX + CHECKED_BOX + r']|\[ ?\]|\[[xX]\]')
OVERLAP = ('{pages} {has} a form check box over a printed box whose position could not be read, so the box may show '
           'a different state than the text; check the original.')

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
OBJECTS_DAMAGED = ('The PDF is damaged: a compressed block of its objects could not be decoded completely, so '
                   'text may be missing or wrong.')
XFA = ('The PDF contains an XFA form; XFA content is not read, so form content that an XFA-capable viewer shows '
       'may be missing from the text.')
# pypdf reports these through logging, not exceptions, and then reads less than the page holds.
DECODING_LOGGERS = ('pypdf.filters',)
DECODING_WARNINGS = ('Impossible to decode XFormObject', 'Detected cyclic form XObject', 'Expected StreamObject')
LIMIT_WARNINGS = ('Exceeded ',)  # pypdf stops drawing form XObjects after its invocation limit


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
    overlap: bool = False  # a check box lies over a printed box whose position could not be read
    unverified: bool = False  # read with OCR, and an image's encoding could not be checked to its end

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
        """Non-whitespace characters of what was read, without the labels and glyphs this module adds."""
        return non_space_count(self.layer) - self.placed + sum(non_space_count(line) for line in
                                                               self.annotations.fields + self.annotations.texts)


@dataclass
class _Ocr:
    texts: dict = field(default_factory=dict)  # page -> OCR text
    problems: dict = field(default_factory=dict)  # page -> problem fragment, None when time ran out


def _extract(data, limits, tools, deadline, workdir, engine) -> ExtractionResult:
    reader, problem = _open(data)
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
    texts = [ocr.texts.get(n, page.text) for n, page in enumerate(read, 1)]
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
    if has_xfa:
        messages.append(XFA)
    method = pdf_method(len(ocr.texts), count)

    # An unread page that may be a scan still had its text layer read: that text is kept, and it counts.
    if not any(texts[n - 1].strip() for n in range(1, count + 1) if n not in unread or n in scanned):
        return failed(method, engine, *messages, NO_TEXT)
    text, spans = join_pages(texts)
    if len(text) > limits.max_chars:
        return failed(method, engine, _too_long(len(text), limits))
    status = 'partial' if unread or partial or objects_damaged or has_xfa else 'ok'
    return ExtractionResult(status=status, method=method, text=text, pages=spans, messages=tuple(messages),
                            ocr_pages=tuple(sorted(ocr.texts)), engine=engine)


def _open(data: bytes) -> tuple[pypdf.PdfReader | None, str]:
    if b'%PDF-' not in data[:MARKER_WINDOW]:
        return None, DAMAGED
    tail = data[-MARKER_WINDOW:]
    if b'%%EOF' not in tail:
        return None, INCOMPLETE
    last = len(data) - len(tail) + tail.rindex(b'%%EOF')
    if not _padding(data[last + len(b'%%EOF'):]):
        # An incremental update cut short leaves an earlier revision's %%EOF last in
        # the file, followed by the start of the update: a parser reads the old revision.
        return None, UNFINISHED
    end = last  # a run of end markers with only padding between them closes one revision (pypdf #4008)
    while (previous := data.rfind(b'%%EOF', 0, end)) >= 0 and _padding(data[previous + len(b'%%EOF'):end]):
        end = previous
    if b'startxref' in data[:end] and b'startxref' not in data[data.rfind(b'%%EOF', 0, end) + 1:end]:
        # The last revision has no startxref of its own: a parser would fall back to an earlier one.
        return None, UNANCHORED
    try:
        # pypdf reads the file as it ends at that revision's marker: the padding carries no PDF data.
        reader = pypdf.PdfReader(io.BytesIO(data[:end + len(b'%%EOF')]))
        if reader.is_encrypted and reader.decrypt('') == PasswordType.NOT_DECRYPTED:
            return None, PASSWORD
        with contextlib.suppress(IndexError):  # no pages at all: reported by _page_list
            reader.get_page(0)  # flattens the page tree: a broken one fails here, not mid-document
    except (DependencyError, MemoryError):
        raise
    except Exception:  # any parser error on untrusted bytes means the file is unreadable
        return None, DAMAGED
    return reader, ''


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

    def emit(self, record) -> None:
        if record.name.startswith(DECODING_LOGGERS):
            self.seen = True
            return
        with contextlib.suppress(Exception):
            message = record.getMessage()
            self.seen = self.seen or message.startswith(DECODING_WARNINGS)
            self.limited = self.limited or message.startswith(LIMIT_WARNINGS)


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
        layer = _layer_text(page, content)
        annotations = read_annotations(page, optional, acroform)
    if annotations.placements:  # images displayed annotations paint are on the page too
        content.placements.extend(annotations.placements)
        content.images.extend(image for image in annotations.images
                              if all(image is not known for known in content.images))
        content.__dict__.pop('image_coverage', None)
    text, placed, overlap = _placed_boxes(layer, annotations)
    text, replaced = replace_surrogates(text)
    block, block_replaced = replace_surrogates(annotations.block(number))
    return _Page(layer=canonicalize(text), replaced=replaced or block_replaced, content=content,
                 annotations=annotations, block=block, damaged=content.damaged or warnings.seen,
                 limited=warnings.limited, undecodable=layer.undecodable, placed=placed, overlap=overlap)


def _placed_boxes(layer: _Layer, annotations: PageAnnotations) -> tuple[str, int, bool]:
    """The layer text with the page's displayed check boxes written in, how many glyphs were inserted, and
    whether a check box lies over a printed box whose position could not be read (the page is then partial):
    - a check box over a printed box (its baseline within the box's height, its start within the box's width,
      give or take BOX_SLACK) replaces it with its own state; a FreeText or stamp mark over one checks it;
    - any other check box writes its glyph and a space before the piece of page text that starts nearest to its
      right on its baseline (within BOX_GAP; pieces on two lines compete, and then nothing is written), replacing a
      printed box that starts that piece; a radio button before the piece that starts with its own option word,
      when every button of its group can be. Nothing is written on a row holding a button that is not tied, and a
      piece two buttons claim gets neither: ambiguity is never resolved by guessing.
    Pieces, printed boxes and rows are looked up by baseline, so each button reads only its own row."""
    text, widgets = layer.text, annotations.widgets
    pieces = _ByBaseline((origin[1], offset, origin) for offset, origin in layer.pieces
                         if origin is not None and origin[2])
    starts = {offset: origin for _, offset, origin in pieces.items}
    line_offsets = [offset for offset, _ in layer.lines]
    printed, unplaced, unplaced_anywhere = [], [], False
    for match in PRINTED_BOX.finditer(text):
        origin = starts.get(match.start())
        if origin is not None:
            printed.append((origin[1], match.start(), (match.end(), origin)))
            continue
        index = bisect_right(line_offsets, match.start()) - 1
        line = layer.lines[index][1] if index >= 0 else None
        if line is not None and line[2]:
            unplaced.append((line[1], match.start(), line))
        else:
            unplaced_anywhere = True  # its line's place is not known either
    printed, unplaced = _ByBaseline(printed), _ByBaseline(unplaced)

    def boxes_under(rect, exclude=()):
        return [(start, end) for start, (end, origin) in printed.on(rect[1], rect[3])
                if _covers(rect, origin) and start not in exclude]

    def may_hide(rect):
        return unplaced_anywhere or any(line[0] <= rect[2] for _, line in unplaced.on(rect[1], rect[3]))

    edits: dict[int, tuple[int, str]] = {}  # start -> (end, replacement)
    overlap, over_a_box, claims = False, set(), {}
    for i, w in enumerate(widgets):
        if w.radio:
            continue
        under, hidden = boxes_under(w.rect), may_hide(w.rect)
        if under or hidden:
            over_a_box.add(i)
            if len(under) == 1 and not hidden:
                claims.setdefault(under[0][0], []).append((i, under[0][1]))
            else:
                overlap = True
    replaced = set()
    for start, owners in claims.items():
        if len(owners) == 1:
            i, end = owners[0]
            edits[start] = (end, CHECKED_BOX if widgets[i].on else UNCHECKED_BOX)
            replaced.add(i)
        else:
            overlap = True  # two check boxes over one printed box
    for rect in annotations.marks:
        under = boxes_under(rect, claims)
        if len(under) == 1:
            edits[under[0][0]] = (under[0][1], CHECKED_BOX)
        elif under or may_hide(rect):
            overlap = True
    ties: dict[int, int] = {}  # widget index -> offset of the piece its glyph goes before
    groups: dict[int, list] = {}
    for i, w in enumerate(widgets):
        if i in over_a_box:
            continue
        x0, y0, x1, y1 = w.rect
        gap = min(BOX_GAP_MAX, max(BOX_GAP_MIN, BOX_GAP * max(x1 - x0, y1 - y0)))
        beside = [(x, y, offset) for offset, (x, y, _) in pieces.on(y0, y1)
                  if x1 - (x1 - x0) / 2 <= x <= x1 + gap and (not w.radio or _starts_with_word(text, offset, w.option))]
        if beside and max(y for _, y, _ in beside) - min(y for _, y, _ in beside) <= 2 * BOX_SLACK:
            ties[i] = min(beside)[2]  # one line: the piece nearest to the box's right; two lines compete: none
        if w.radio:
            groups.setdefault(w.group, []).append(i)
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
    inserted = 0
    for i, offset in ties.items():
        if unsettled.holds(starts[offset][1]):
            continue  # a row holding a button that is not tied gets no glyph
        glyph = CHECKED_BOX if widgets[i].on else UNCHECKED_BOX
        box = PRINTED_BOX.match(text, offset)
        if box is None:
            edits[offset] = (offset, glyph + ' ')
            inserted += 1
        elif offset not in edits:  # a printed box starts the piece: never write two glyphs
            edits[offset] = (box.end(), glyph)
    for offset, (end, replacement) in sorted(edits.items(), reverse=True):
        text = text[:offset] + replacement + text[end:]
    return text, inserted, overlap


class _ByBaseline:
    """(baseline, key, value) items, looked up by the baselines a box's height (give or take BOX_SLACK) holds."""

    def __init__(self, items):
        self.items = sorted(items, key=lambda item: item[0])
        self.baselines = [item[0] for item in self.items]

    def on(self, y0: float, y1: float) -> list:
        low = bisect_right(self.baselines, y0 - BOX_SLACK - 1e-9)
        high = bisect_right(self.baselines, y1 + BOX_SLACK)
        return [(key, value) for _, key, value in self.items[low:high]]


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


def _covers(rect, origin) -> bool:
    """Whether a box printed at ``origin`` lies under ``rect``."""
    x0, y0, x1, y1 = rect
    return y0 - BOX_SLACK <= origin[1] <= y1 + BOX_SLACK and x0 - BOX_SLACK <= origin[0] <= x1


def _starts_with_word(text: str, offset: int, word: str) -> bool:
    """Whether the text at ``offset`` starts with ``word`` (any case), followed by no further letter."""
    return bool(word) and text[offset:offset + len(word)].lower() == word.lower() and not \
        text[offset + len(word):offset + len(word) + 1].isalnum()


@dataclass(frozen=True)
class _Layer:
    text: str = ''  # decoded text-layer text, before canonicalisation
    undecodable: int = 0  # glyphs that name no character, dropped
    lines: tuple = ()  # (offset in text, origin) of each line; origin (x, y, upright) when drawn by the page itself
    pieces: tuple = ()  # (offset, origin) of the first character (not a space) of each piece of text, as for lines


def _layer_text(page, content: PageContent) -> _Layer:
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
    depth = [0]  # form XObjects being read: their pieces are positioned in the form's own space

    def before(operator, operands, cm, tm):
        if operator == b'Do':
            depth[0] += 1

    def after(operator, operands, cm, tm):
        if operator == b'Do':
            depth[0] -= 1

    def visit(text, cm, tm, font, size):
        if text:
            pieces.append((text, _origin(cm, tm) if depth[0] == 0 else None, font))

    try:
        raw = extraction_page(page, content).extract_text(visitor_operand_before=before, visitor_operand_after=after,
                                                          visitor_text=visit)
    except (DependencyError, MemoryError):
        raise
    except Exception:
        return _Layer()
    if ''.join(piece[0] for piece in pieces) != raw:
        pieces = [(raw, None, None)]
    return _decoded(pieces)


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


def _decoded(pieces) -> _Layer:
    out: list[str] = []
    size, dropped, lines, starting, firsts = 0, 0, [], True, []
    decoders: dict[int, object] = {}
    for text, origin, font in pieces:
        if id(font) not in decoders:
            decoders[id(font)] = _decoder(font)
        decode = decoders[id(font)]
        first = True  # the piece's first character drawn (not a space) is drawn at its origin
        for index, char in enumerate(text):
            mapped = decode(char, index == len(text) - 1)
            if mapped is None:
                dropped += char != ' '  # a space may be pypdf's own, between pieces of text
                continue
            if mapped == '\n':
                out.append(mapped)
                size += 1
                starting, first = True, False
                continue
            if starting:
                lines.append((size, origin))
                starting = False
            if first and not mapped.isspace():
                firsts.append((size, origin))
                first = False
            out.append(mapped)
            size += len(mapped)
    return _Layer(''.join(out), dropped, tuple(lines), tuple(firsts))


def _decoder(font):
    """(char, last in its piece) -> the character it stands for, or None for a glyph that names none."""
    style = kind(font) if font is not None else 'text'
    if style == 'glyph-index':  # nothing it writes is a character; pypdf's own line break ends a piece
        return lambda char, last: '\n' if char == '\n' and last else None
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
    blank = [n for n in ocr_pages if not texts[n - 1].strip()]
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
    invalid = [n for n, page in enumerate(read, 1) if page.replaced and n not in ocr.texts]
    if invalid:
        messages.append(f'{page_phrase(invalid)} {agree(invalid, "contains", "contain")} characters the PDF does '
                        'not encode as valid text; they are shown as �.')
    unmapped = [(n, page.undecodable + page.annotations.undecodable) for n, page in enumerate(read, 1)
                if n not in ocr.texts and page.undecodable + page.annotations.undecodable]
    if unmapped:
        pages, total = [n for n, _ in unmapped], sum(count for _, count in unmapped)
        one = total == 1
        messages.append(f'{page_phrase(pages)} {agree(pages, "has", "have")} {total:,} character{"" if one else "s"} '
                        f'that {"does" if one else "do"} not map to text (symbol-font glyphs, private-use or control '
                        f'codes); {"it was" if one else "they were"} not extracted.')
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
    annotation_partial = _annotation_messages(read, set(ocr.texts), messages)
    return messages, bool(damaged or unchecked or limited or overlapped) or annotation_partial


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
