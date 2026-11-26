"""The document block of a coding request (BUILD-SPEC 4.3): the original file as the Anthropic API reads it.

- PDF: a base64 document block with citations, titled with the original file name. No local PDF parsing at all.
- DOCX: converted to PDF by LibreOffice, by the one code that converts a Word file (studio.fable.docx_package,
  Django-free: safe_package makes it a package that cannot reach outside itself - SEC-S6, release 1 E1 and E2 - and
  soffice_convert converts that in a bounded child of 70 s, with a memory cap, a throwaway HOME and profile and no
  inherited environment). Where it runs (release 1 E3): with settings.CONVERTER_SOCKET, in the converter service on that
  socket (studio.converter_server: a sealed container, one conversion at a time); a converter that cannot be reached, or
  does not answer in time, fails the document BUSY - a member may retry - and nothing is converted inside the worker.
  With no socket, in-process (tests and local runs), unless settings.CONVERTER_REQUIRED, which makes a missing socket
  BUSY too: production never converts in the worker. A failed conversion is DocumentError CONVERT. The PDF is sent as
  above. Release 2: a Word file refused because E2 would leave content out of its PDF (docx_package.ContentNotShown)
  is CONVERT with the sentence of its code (REFUSED_PACKAGE_TEXT) and its code and counts for the record (R2-31); and
  a round that would read a conversion an earlier round stored first runs the same check on the stored original
  (needs_fresh_conversion, studio.jobs: R2-28 step 7, C8).
- TXT (UTF-8; a leading byte-order mark is dropped) and pasted text: a text document block with citations.

The stored form of the block (``stored_block``, what ProviderRun.request_body keeps) replaces the base64 data with
{"$original_sha256", "$original_bytes"} of the bytes it carried; a converted Word file also names its source file.

The Word package's names (safe_package, soffice_convert, their limits and helpers) live in studio.fable.docx_package and
are re-exported here, so callers and tests keep theirs.
"""
from __future__ import annotations

import base64
import hashlib
import unicodedata
from dataclasses import dataclass

from django.conf import settings

from .. import converter_server
from ..storage import ALLOWED_SUFFIXES, OriginalCorrupted, read_original
from . import BUSY, CONVERT, DOCUMENT, STORAGE, docx_package
from .docx_package import (  # noqa: F401 - re-exported (E3): callers and tests keep these names
    CONTENT_TYPES_NS, CONTENT_TYPES_PART, CONVERT_MEMORY_BYTES, CONVERT_SECONDS, MAX_PACKAGE_BYTES, MAX_PACKAGE_PARTS,
    MAX_PART_BYTES, MAX_PDF_BYTES, OFFICE_DOCUMENT_TYPES, OPENDOCUMENT_PARTS, PACKAGE_SECONDS, PROFILE_SETTINGS,
    RELATIONSHIPS_NS, ROOT_RELATIONSHIPS_PART, SOFFICE, SOFFICE_SECONDS, URI_SCHEME, WORD_MAIN_TYPES, WORK_PREFIX,
    PackageRefused, _convert_package, _local, _part_name, _relationships, _relationships_xml, _require_word_main_part,
    _source_folder, _xml, safe_package, soffice_convert)

PDF, DOCX, TEXT = ALLOWED_SUFFIXES['.pdf'], ALLOWED_SUFFIXES['.docx'], ALLOWED_SUFFIXES['.txt']
PASTE_TITLE = 'Pasted text'
# E3: the worker's side of the converter service. It allows CONVERTER_CONNECT_SECONDS to connect and, in all,
# converter_wait_seconds(): CONVERT_SECONDS for each of the worker's CONCURRENT_DOCUMENTS threads - the service converts
# one file at a time, so every thread may wait its turn behind the others - the connect, and CONVERTER_MARGIN_SECONDS
# (300 s for 4).
CONVERTER_CONNECT_SECONDS = 2
CONVERTER_MARGIN_SECONDS = 18
CONVERT_TEXT = 'The Word file could not be opened.'
# Release 2, R2-31: a Word file refused because E2 would leave something out of the PDF (docx_package.ContentNotShown),
# by its code - what the member has, and what to do; every other refusal keeps CONVERT_TEXT.
REFUSED_PACKAGE_TEXT = {
    docx_package.INSERTED_DOCUMENT: ('This Word file has another document inserted in it, which cannot be read here. '
                                     'Open it in Word, save it as a PDF and upload the PDF.'),
    docx_package.INSERTED_OBJECT: ('This Word file has an embedded object that cannot be shown here. Open it in Word, '
                                   'save it as a PDF and upload the PDF.'),
}
BUSY_TEXT = 'The coding service is busy. Try again in a few minutes.'  # studio.jobs.FAILURE_TEXT[BUSY], word for word
STORAGE_TEXT = 'The stored document could not be read back unchanged.'
EMPTY_TEXT = 'The document is empty.'
NOT_UTF8_TEXT = 'The text file could not be read. Save it as UTF-8 text and upload it again.'
UNSUPPORTED_TEXT = 'This kind of document cannot be coded.'
# The API's refusal of the document (failure kind DOCUMENT), worded for what was uploaded.
REFUSED_TEXT = {'pdf': 'This PDF could not be read. It may be password-protected or damaged.',
                'docx': 'The Word file could not be read.',
                'txt': 'The text file could not be read.',
                'paste': 'The pasted text could not be read.'}


class DocumentError(Exception):
    """The document cannot be sent: ``failure_kind`` (CONVERT, BUSY, DOCUMENT or STORAGE) and ``text``, a plain
    sentence for the customer; ``detail`` says more, for the operator, in fixed words. ``code`` and ``counts``: why a
    Word file was refused and how much of what it holds, when E2 would leave content out of its PDF (R2-31): one of
    docx_package.REFUSAL_CODES and {kind: n} over docx_package.LOST_KINDS, else '' and {}."""

    def __init__(self, failure_kind: str, text: str, detail: str = '', *, code: str = '', counts=None):
        super().__init__(text)
        self.failure_kind, self.text, self.detail = failure_kind, text, detail
        self.code = code if code in docx_package.REFUSAL_CODES else ''
        self.counts = {kind: (counts or {}).get(kind, 0) for kind in docx_package.LOST_KINDS} if self.code else {}

    def recorded(self) -> dict:
        """What the round's coding.round_failed event adds (R2-31): {'refused': the code, 'inserted': the counts}, or {}
        - codes and counts only, never a word of the file."""
        return {'refused': self.code, 'inserted': dict(self.counts)} if self.code else {}


@dataclass(frozen=True)
class Document:
    kind: str  # pdf | docx | txt | paste
    title: str
    data: bytes  # the bytes the block carries: the PDF, or the text as UTF-8
    block: dict  # the content block as sent
    stored_block: dict  # the content block as recorded
    sha256: str  # of ``data``
    source_sha256: str  # of the uploaded original (or of the pasted text)

    @property
    def size(self) -> int:
        return len(self.data)


def prepare(revision, *, converter=None, reader=read_original) -> Document:
    """The Document of ``revision`` (an upload or a paste), or DocumentError. ``converter``: DOCX bytes -> PDF bytes
    (default convert_docx); ``reader``: the stored original's bytes, sha256-checked (storage.read_original)."""
    from ..models import SourceRevision

    if revision.kind == SourceRevision.PASTE:
        text = canonical_text(revision.pasted_text or '')
        return _text_document('paste', PASTE_TITLE, text, hashlib.sha256(text.encode('utf-8')).hexdigest())
    source = revision.source_file
    if revision.kind != SourceRevision.UPLOAD or source is None:
        raise DocumentError(DOCUMENT, UNSUPPORTED_TEXT, f'a {revision.kind} revision is not coded')
    try:
        data = reader(source)
    except (OriginalCorrupted, OSError) as exc:
        raise DocumentError(STORAGE, STORAGE_TEXT, type(exc).__name__) from None
    title = source.original_name or 'document'  # E4, a neutral title (OWNER DECISION D17), is release 1b: kept as is
    if source.media_type == PDF:
        return _pdf_document('pdf', title, data, source.sha256)
    if source.media_type == DOCX:
        try:
            pdf = (converter or convert_docx)(data)
        except DocumentError:
            raise
        except Exception as exc:  # noqa: BLE001 - a converter's failure is a failed conversion, never a crash
            raise DocumentError(CONVERT, CONVERT_TEXT, type(exc).__name__) from None
        if not isinstance(pdf, bytes) or not pdf.startswith(b'%PDF-'):
            raise DocumentError(CONVERT, CONVERT_TEXT, 'the conversion produced no PDF')
        return _pdf_document('docx', title, pdf, source.sha256, converted_from=data)
    if source.media_type == TEXT:
        raw = data[3:] if data.startswith(b'\xef\xbb\xbf') else data
        try:
            text = canonical_text(raw.decode('utf-8'))
        except UnicodeDecodeError:
            raise DocumentError(DOCUMENT, NOT_UTF8_TEXT, 'the text file is not UTF-8') from None
        return _text_document('txt', title, text, source.sha256)
    raise DocumentError(DOCUMENT, UNSUPPORTED_TEXT, f'media type {source.media_type!r} is not coded')


def canonical_text(text: str) -> str:
    """CRLF and CR become LF, NUL is removed (a JSON column cannot store it), Unicode NFC: nothing else."""
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\x00', '')
    return unicodedata.normalize('NFC', text)


def _pdf_document(kind, title, pdf, source_sha256, converted_from=None) -> Document:
    if len(pdf) > MAX_PDF_BYTES:
        raise DocumentError(DOCUMENT, REFUSED_TEXT[kind], f'the PDF is {len(pdf):,} bytes')
    digest = hashlib.sha256(pdf).hexdigest()
    block = {'type': 'document', 'title': title, 'citations': {'enabled': True},
             'source': {'type': 'base64', 'media_type': PDF, 'data': base64.standard_b64encode(pdf).decode('ascii')}}
    pointer = {'$original_sha256': digest, '$original_bytes': len(pdf)}
    if converted_from is not None:
        pointer['$converted_from'] = {'media_type': DOCX, 'sha256': source_sha256, 'bytes': len(converted_from)}
    stored = {**block, 'source': {**block['source'], 'data': pointer}}
    return Document(kind=kind, title=title, data=pdf, block=block, stored_block=stored, sha256=digest,
                    source_sha256=source_sha256)


def _text_document(kind, title, text, source_sha256) -> Document:
    if not text.strip():
        raise DocumentError(DOCUMENT, EMPTY_TEXT, 'no text')
    data = text.encode('utf-8')
    block = {'type': 'document', 'title': title, 'citations': {'enabled': True},
             'source': {'type': 'text', 'media_type': TEXT, 'data': text}}
    return Document(kind=kind, title=title, data=data, block=block, stored_block=block,
                    sha256=hashlib.sha256(data).hexdigest(), source_sha256=source_sha256)




def convert_docx(data: bytes, *, runner=None, seconds=CONVERT_SECONDS, memory_bytes=CONVERT_MEMORY_BYTES) -> bytes:
    """``data`` (a Word file) as PDF bytes; DocumentError CONVERT when it cannot be converted, BUSY when the converter
    cannot convert it now or the package checks ran out of time (a member may retry). With settings.CONVERTER_SOCKET the
    converter service converts it (E3); with none, settings.CONVERTER_REQUIRED makes it BUSY, and otherwise it is
    converted here, in a bounded child, by the same code the service runs (``runner``: the function run there on the
    package safe_package made of ``data`` and the work folder made for it, default LibreOffice's; ``seconds`` and
    ``memory_bytes``: the child's limits)."""
    path = settings.CONVERTER_SOCKET
    if path:
        return _converted_by_service(path, data)
    if settings.CONVERTER_REQUIRED:
        raise DocumentError(BUSY, BUSY_TEXT, 'a converter is required and no converter socket is set')
    try:
        return docx_package.convert_in_child(data, runner=runner, seconds=seconds, memory_bytes=memory_bytes)
    except docx_package.ConversionBusy as exc:  # its checks ran out of time: not the file's fault
        raise DocumentError(BUSY, BUSY_TEXT, str(exc)) from None
    except docx_package.ConversionRefused as exc:
        raise _refused(exc, f'the Word package was refused: {exc}') from None
    except docx_package.ConversionFailed as exc:
        raise DocumentError(CONVERT, CONVERT_TEXT, str(exc)) from None


def needs_fresh_conversion(data: bytes) -> bool:
    """Release 2, R2-28 step 7 (C8), the worker's side: release 2's package check of ``data`` - a Word file a round of
    whose revision stored its conversion - before that conversion is read again (docx_package.check_in_child: in the
    worker, in the bounded child and under the limits a conversion's check runs under, converting nothing, with no
    converter call). DocumentError CONVERT when the check refuses the file (ContentNotShown): the sentence and the
    record of its code, as a fresh conversion of it would end. True when the round must convert afresh: R2-30's QUOTE
    applies to the file, or the check could not decide (it ran out of time, failed, or refused the file once its parts
    were read) - the converter then decides, as for any fresh conversion. False when the stored conversion may be read
    again: a clean revision's view stays byte-identical, with no converter call."""
    try:
        return docx_package.check_in_child(data)
    except docx_package.ConversionRefused as exc:
        raise _refused(exc, f'the Word package was refused: {exc}') from None
    except (docx_package.ConversionBusy, docx_package.ConversionFailed):
        return True


def _refused(exc, detail) -> DocumentError:
    """CONVERT for a refused Word file (``exc``: docx_package.ConversionRefused or converter_server.ConverterFailed):
    with the sentence, code and counts of a file refused for what E2 would leave out of its PDF, else the general
    sentence and no code (R2-31)."""
    code = getattr(exc, 'code', '')
    if isinstance(code, str) and code in REFUSED_PACKAGE_TEXT:
        return DocumentError(CONVERT, REFUSED_PACKAGE_TEXT[code], detail, code=code, counts=getattr(exc, 'counts', {}))
    return DocumentError(CONVERT, CONVERT_TEXT, detail)


def converter_wait_seconds() -> int:
    """How long the worker waits for the converter, in all, for one Word file (see CONVERTER_CONNECT_SECONDS)."""
    return CONVERT_SECONDS * settings.CONCURRENT_DOCUMENTS + CONVERTER_CONNECT_SECONDS + CONVERTER_MARGIN_SECONDS


def _converted_by_service(path, data: bytes) -> bytes:
    """The PDF the converter service on the socket ``path`` made of ``data`` (studio.converter_server.request): BUSY
    when it cannot be reached, does not answer in time or says it is busy; CONVERT when it refused the file - with the
    sentence and record of a ContentNotShown's code when the converter gave one this worker believes (R2-31) -, failed,
    or answered in a form it does not use."""
    try:
        return converter_server.request(path, data, connect_seconds=CONVERTER_CONNECT_SECONDS,
                                        total_seconds=converter_wait_seconds())
    except converter_server.ConverterBusy as exc:
        raise DocumentError(BUSY, BUSY_TEXT, str(exc)) from None
    except converter_server.ConverterFailed as exc:
        raise _refused(exc, str(exc)) from None
