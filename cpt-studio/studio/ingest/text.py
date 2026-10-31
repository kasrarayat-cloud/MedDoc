"""Canonical text, result builders and the TXT reader (ARCHITECTURE 5.1).

Canonical text is the coordinate system for every evidence offset: CRLF and
CR become LF, NUL is removed and the result is Unicode NFC — nothing else.
Pure functions only; importable by the extraction child (no Django).
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import TYPE_CHECKING

from studio.types import ExtractionResult, PageSpan

if TYPE_CHECKING:
    from .extract import Limits

INGEST_VERSION = 'cpt-studio-ingest@4'
PAGE_SEPARATOR = '\n\n'
# The method a failure is reported under before any page was read.
METHOD_FOR_KIND = {'pdf': 'pdf-text', 'docx': 'docx', 'txt': 'txt'}

_UTF8_BOM = b'\xef\xbb\xbf'
_SURROGATES = re.compile('[\ud800-\udfff]')
REPLACEMENT = '\ufffd'  # what text that is not valid is shown as


def canonicalize(text: str) -> str:
    """CRLF and CR -> LF, NUL removed, Unicode NFC. Nothing else."""
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\x00', '')
    return unicodedata.normalize('NFC', text)


def has_surrogates(text: str) -> bool:
    """Lone surrogates are not Unicode text: they cannot be stored or exported."""
    return _SURROGATES.search(text) is not None


def replace_surrogates(text: str) -> tuple[str, bool]:
    replaced, count = _SURROGATES.subn(REPLACEMENT, text)
    return replaced, count > 0


def caused_by(exc: BaseException | None, kind: type) -> bool:
    """Whether ``exc`` or one of its causes (the first 16) is a ``kind``."""
    for _ in range(16):
        if exc is None:
            return False
        if isinstance(exc, kind):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def from_memory(exc: BaseException | None) -> bool:
    """Whether ``exc`` was raised because memory ran out: a MemoryError among its causes (pypdf 6.21.4 reports
    running out of memory inside a dictionary as a read error)."""
    return caused_by(exc, MemoryError)


def non_space_count(text: str) -> int:
    return len(''.join(text.split()))


def format_seconds(seconds: float) -> str:
    return f'{seconds:.0f}' if seconds >= 100 else f'{seconds:.3g}'


def page_phrase(pages: Sequence[int]) -> str:
    """'Page 3' or 'Pages 1-2, 5' for ascending page numbers."""
    runs: list[list[int]] = []
    for page in pages:
        if runs and page == runs[-1][1] + 1:
            runs[-1][1] = page
        else:
            runs.append([page, page])
    listed = ', '.join(str(first) if first == last else f'{first}-{last}' for first, last in runs)
    return f'Page {listed}' if len(pages) == 1 else f'Pages {listed}'


def agree(pages: Sequence[int], singular: str, plural: str) -> str:
    return singular if len(pages) == 1 else plural


def pdf_method(ocr_count: int, page_count: int) -> str:
    if ocr_count == 0:
        return 'pdf-text'
    return 'pdf-ocr' if ocr_count == page_count else 'pdf-mixed'


def join_pages(texts: Sequence[str]) -> tuple[str, tuple[PageSpan, ...]]:
    """Join canonical page texts with PAGE_SEPARATOR; spans index the joined text.

    Raises ValueError if the joined text is not canonical or a span does not
    slice back to its page's text — the offsets would then be wrong.
    """
    text = PAGE_SEPARATOR.join(texts)
    spans, start = [], 0
    for number, page in enumerate(texts, 1):
        spans.append(PageSpan(page=number, start=start, end=start + len(page)))
        start += len(page) + len(PAGE_SEPARATOR)
    if canonicalize(text) != text or any(text[span.start:span.end] != texts[span.page - 1] for span in spans):
        raise ValueError('Page texts do not assemble into canonical text with exact page spans.')
    return text, tuple(spans)


def failed(method: str, engine: dict, *messages: str) -> ExtractionResult:
    """A failed extraction carries no text: nothing downstream may code from it."""
    return ExtractionResult(status='failed', method=method, text='', messages=tuple(messages), engine=engine)


def single_page(text: str, method: str, limits: Limits, noun: str, engine: dict,
                notes: Sequence[str] = ()) -> ExtractionResult:
    """``text`` (already canonical) as one page; failed when invalid, empty or too long."""
    if has_surrogates(text):
        return failed(method, engine, f'The {noun} contains characters that are not valid Unicode text.', *notes)
    if not text.strip():
        return failed(method, engine, f'The {noun} is empty.', *notes)
    if len(text) > limits.max_chars:
        return failed(method, engine, f'The {noun} has {len(text):,} characters; the limit is {limits.max_chars:,}.',
                      *notes)
    return ExtractionResult(status='ok', method=method, text=text, pages=(PageSpan(page=1, start=0, end=len(text)),),
                            messages=tuple(notes), engine=engine)


def extract_txt(data: bytes, limits: Limits) -> ExtractionResult:
    """UTF-8 text (a leading BOM is dropped); anything else fails explicitly."""
    engine = {'ingest': INGEST_VERSION}
    raw = data[len(_UTF8_BOM):] if data.startswith(_UTF8_BOM) else data
    try:
        decoded = raw.decode('utf-8')
    except UnicodeDecodeError:
        return failed('txt', engine, 'The text file is not valid UTF-8.')
    return single_page(canonicalize(decoded), 'txt', limits, 'text file', engine)
