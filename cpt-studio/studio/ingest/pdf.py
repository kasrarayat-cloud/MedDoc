"""PDF extraction (ARCHITECTURE 5.1): the pypdf text layer page by page, OCR for
pages without a usable text layer, page spans over the final canonical text.

A page whose text layer has fewer than ``min_text_chars_per_page``
non-whitespace characters is treated as having no usable text layer. It is
OCRed when OCR is available; otherwise — or when OCR fails or time runs out —
it is named in the messages and the result is 'partial' (other pages have
text) or 'failed' (none does). A page that has a text layer and also a large
image is read from its text layer and named in the messages. A document is
never truncated: too many pages or too much text fails the whole document.
"""
from __future__ import annotations

import io
import os
import time
from typing import TYPE_CHECKING

import pypdf
from pypdf import PasswordType
from pypdf.errors import DependencyError

from studio.types import ExtractionResult

from .ocr import OcrTools, ocr_page
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
MAX_FORM_DEPTH = 3

# PDF Reference, implementation notes: readers require the header within the
# first 1024 bytes and %%EOF within the last 1024. A file without them is
# truncated or not a PDF; parsers would "repair" it into fewer pages.
MARKER_WINDOW = 1024

DAMAGED = 'The PDF could not be read; the file is damaged or is not a valid PDF.'
INCOMPLETE = 'The PDF is incomplete: it has no end-of-file marker. Upload the complete file.'
PASSWORD = 'The PDF is password-protected.'
AES_UNSUPPORTED = 'The PDF is encrypted with AES, which this server cannot decrypt.'
NO_TEXT = 'No text could be read from the PDF.'


def extract_pdf(data: bytes, limits: Limits, tools: OcrTools | None, deadline: float,
                workdir: str) -> ExtractionResult:
    """``deadline`` (time.monotonic) bounds OCR work; ``workdir`` is a private directory."""
    engine = {'ingest': INGEST_VERSION, 'pypdf': pypdf.__version__}
    try:
        return _extract(data, limits, tools, deadline, workdir, engine)
    except DependencyError:
        # AES needs a crypto library pypdf could not import; it can surface on open or per object.
        return failed('pdf-text', engine, AES_UNSUPPORTED)


def _extract(data, limits, tools, deadline, workdir, engine) -> ExtractionResult:
    reader, problem = _open(data)
    if problem:
        return failed('pdf-text', engine, problem)
    pages = list(reader.pages)
    count = len(pages)
    if count == 0:
        return failed('pdf-text', engine, 'The PDF has no pages.')
    if count > limits.max_pages:
        return failed('pdf-text', engine, f'The PDF has {count} pages; the limit is {limits.max_pages}.')

    layers = [_layer_text(page) for page in pages]
    texts = [text for text, _ in layers]
    needs_ocr = [n for n, text in enumerate(texts, 1) if non_space_count(text) < limits.min_text_chars_per_page]
    layer_chars = sum(len(text) for n, text in enumerate(texts, 1) if n not in needs_ocr)
    if layer_chars > limits.max_chars:
        return failed('pdf-text', engine, _too_long(layer_chars, limits))

    ocr_texts, problems = {}, {}
    if needs_ocr and tools:
        ocr_texts, problems = _ocr_pages(data, {n: pages[n - 1] for n in needs_ocr}, limits, tools, deadline, workdir)
        engine = engine | {'tesseract': tools.tesseract_version, 'pdftoppm': tools.pdftoppm_version}
    elif needs_ocr:
        engine = engine | {'ocr': 'not available'}
    for page, text in ocr_texts.items():
        texts[page - 1] = text

    ocr_pages = sorted(ocr_texts)
    unavailable = [] if tools else needs_ocr
    unread = sorted(set(unavailable) | set(problems))
    invalid = [n for n, (_, replaced) in enumerate(layers, 1) if replaced and n not in ocr_texts]
    imaged = [n for n, page in enumerate(pages, 1) if n not in needs_ocr and _has_large_image(page)]
    messages = _messages(texts, ocr_pages, unavailable, problems, invalid, imaged, limits)
    method = pdf_method(len(ocr_pages), count)

    if not any(texts[n - 1].strip() for n in range(1, count + 1) if n not in unread):
        return failed(method, engine, *messages, NO_TEXT)
    text, spans = join_pages(texts)
    if len(text) > limits.max_chars:
        return failed(method, engine, _too_long(len(text), limits))
    return ExtractionResult(status='partial' if unread else 'ok', method=method, text=text, pages=spans,
                            messages=tuple(messages), ocr_pages=tuple(ocr_pages), engine=engine)


def _open(data: bytes) -> tuple[pypdf.PdfReader | None, str]:
    if b'%PDF-' not in data[:MARKER_WINDOW]:
        return None, DAMAGED
    if b'%%EOF' not in data[-MARKER_WINDOW:]:
        return None, INCOMPLETE
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted and reader.decrypt('') == PasswordType.NOT_DECRYPTED:
            return None, PASSWORD
        len(reader.pages)  # walks the page tree: a broken one fails here, not mid-document
    except (DependencyError, MemoryError):
        raise
    except Exception:  # any parser error on untrusted bytes means the file is unreadable
        return None, DAMAGED
    return reader, ''


def _layer_text(page) -> tuple[str, bool]:
    """Canonical text-layer text, and whether invalid characters were replaced.

    A page whose text layer cannot be parsed is treated as having none, so it
    goes to OCR (or is reported) instead of failing the whole document.
    """
    try:
        raw = page.extract_text()
    except (DependencyError, MemoryError):
        raise
    except Exception:
        return '', False
    text, replaced = replace_surrogates(raw)
    return canonicalize(text), replaced


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


def _has_large_image(page) -> bool:
    try:
        return _large_image_in(page.get('/Resources'), 0)
    except Exception:  # unreadable resources: no claim either way
        return False


def _large_image_in(resources, depth: int) -> bool:
    resources = _resolved(resources)
    xobjects = _resolved(resources.get('/XObject')) if isinstance(resources, dict) else None
    if depth > MAX_FORM_DEPTH or not isinstance(xobjects, dict):
        return False
    for reference in xobjects.values():
        xobject = _resolved(reference)
        subtype = xobject.get('/Subtype')
        if subtype == '/Image':
            pixels = int(_resolved(xobject.get('/Width', 0))) * int(_resolved(xobject.get('/Height', 0)))
            if pixels >= LARGE_IMAGE_PIXELS:
                return True
        elif subtype == '/Form' and _large_image_in(xobject.get('/Resources'), depth + 1):
            return True
    return False


def _resolved(value):
    return value.get_object() if hasattr(value, 'get_object') else value


def _messages(texts, ocr_pages, unavailable, problems, invalid, imaged, limits) -> list[str]:
    messages = []
    if ocr_pages:
        messages.append(f'{page_phrase(ocr_pages)} {agree(ocr_pages, "was", "were")} read with OCR; '
                        'OCR can misread characters — check evidence against the original.')
    blank = [n for n in ocr_pages if not texts[n - 1].strip()]
    if blank:
        messages.append(f'{page_phrase(blank)} {agree(blank, "has", "have")} no readable text (OCR found none).')
    if unavailable:
        messages.append(f'{page_phrase(unavailable)} {agree(unavailable, "has", "have")} no usable text layer '
                        'and OCR is not available on this server.')
    out_of_time = [n for n, problem in sorted(problems.items()) if problem is None]
    if out_of_time:
        messages.append(f'{page_phrase(out_of_time)} {agree(out_of_time, "has", "have")} no usable text layer and '
                        f'{agree(out_of_time, "was", "were")} not read: the '
                        f'{format_seconds(limits.timeout_s)}-second extraction time limit was reached.')
    messages.extend(f'Page {n} has no usable text layer and OCR could not read it ({problem}).'
                    for n, problem in sorted(problems.items()) if problem is not None)
    if imaged:
        messages.append(f'{page_phrase(imaged)} {agree(imaged, "combines", "combine")} a text layer with a large '
                        'image; only the text layer was read, so check the text against the original if the image '
                        'holds text.')
    if invalid:
        messages.append(f'{page_phrase(invalid)} {agree(invalid, "contains", "contain")} characters the PDF does '
                        'not encode as valid text; they are shown as �.')
    return messages


def _too_long(chars: int, limits: Limits) -> str:
    return f'The extracted text has {chars:,} characters; the limit is {limits.max_chars:,}.'
