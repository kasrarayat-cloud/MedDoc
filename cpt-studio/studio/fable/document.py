"""The document block of a coding request (BUILD-SPEC 4.3): the original file as the Anthropic API reads it.

- PDF: a base64 document block with citations, titled with the original file name. No local PDF parsing at all.
- DOCX: converted to PDF by LibreOffice (``soffice --headless --convert-to pdf``) in a bounded child
  (bounded.run_bounded: 60 s, a memory cap, a throwaway HOME and profile directory, no inherited environment); the PDF
  is sent as above. A failed conversion is DocumentError CONVERT.
- TXT (UTF-8; a leading byte-order mark is dropped) and pasted text: a text document block with citations.

The stored form of the block (``stored_block``, what ProviderRun.request_body keeps) replaces the base64 data with
{"$original_sha256", "$original_bytes"} of the bytes it carried; a converted Word file also names its source file.
"""
from __future__ import annotations

import base64
import hashlib
import os
import shutil
import signal
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .. import bounded
from ..storage import ALLOWED_SUFFIXES, OriginalCorrupted, read_original
from . import CONVERT, DOCUMENT, STORAGE

PDF, DOCX, TEXT = ALLOWED_SUFFIXES['.pdf'], ALLOWED_SUFFIXES['.docx'], ALLOWED_SUFFIXES['.txt']
PASTE_TITLE = 'Pasted text'
CONVERT_SECONDS = 60  # the bounded child's wall clock
SOFFICE_SECONDS = 55  # soffice's own, inside it, so the child kills soffice's process group before it is killed
CONVERT_MEMORY_BYTES = 2 * 1024 ** 3  # address-space growth allowed to the child, and so to soffice
# The API takes 32 MB per request; base64 adds a third, so a PDF over 23 MiB (about 30.7 MB encoded) cannot fit with
# the instructions. Uploads stop at 15 MB; only a converted Word file can be larger.
MAX_PDF_BYTES = 23 * 1024 * 1024
SOFFICE = 'soffice'
WORK_PREFIX = 'cpt-convert-'  # the worker removes a child's leftover work directories at start (jobs.work)
CONVERT_TEXT = 'The Word file could not be opened.'
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
    """The document cannot be sent: ``failure_kind`` (CONVERT, DOCUMENT or STORAGE) and ``text``, a plain sentence
    for the customer; ``detail`` says more, for the operator."""

    def __init__(self, failure_kind: str, text: str, detail: str = ''):
        super().__init__(text)
        self.failure_kind, self.text, self.detail = failure_kind, text, detail


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
    title = source.original_name or 'document'
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
    """``data`` (a Word file) as PDF bytes, converted in a bounded child (``runner``: the function run there, default
    LibreOffice's); DocumentError CONVERT when it cannot be."""
    try:
        pdf = bounded.run_bounded(runner or soffice_convert, data, seconds=seconds, memory_bytes=memory_bytes)
    except bounded.Overrun as exc:
        raise DocumentError(CONVERT, CONVERT_TEXT, f'the conversion passed its {exc.reason} limit') from None
    except Exception as exc:  # noqa: BLE001 - the child's failure is logged by run_bounded
        raise DocumentError(CONVERT, CONVERT_TEXT, type(exc).__name__) from None
    if not isinstance(pdf, bytes) or not pdf.startswith(b'%PDF-'):
        raise DocumentError(CONVERT, CONVERT_TEXT, 'the conversion produced no PDF')
    return pdf


def soffice_convert(data: bytes) -> bytes:
    """LibreOffice's conversion, run inside the bounded child (Django-free). A throwaway work directory holds the
    input, the output, HOME, TMPDIR and the LibreOffice profile; the environment is built from nothing; soffice runs in a
    session of its own, which is killed whatever happens; the directory is removed."""
    work = Path(tempfile.mkdtemp(prefix=WORK_PREFIX))
    try:
        home, profile, out, tmp = (work / name for name in ('home', 'profile', 'out', 'tmp'))
        for folder in (home, profile, out, tmp):
            folder.mkdir(mode=0o700)
        source = work / 'document.docx'
        fd = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
        command = [SOFFICE, f'-env:UserInstallation={profile.as_uri()}', '--headless', '--invisible', '--norestore',
                   '--nologo', '--nodefault', '--nolockcheck', '--convert-to', 'pdf', '--outdir', str(out),
                   str(source)]
        env = {'HOME': str(home), 'TMPDIR': str(tmp), 'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8'}
        process = subprocess.Popen(command, env=env, cwd=str(work), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                                   close_fds=True)
        try:
            process.wait(timeout=SOFFICE_SECONDS)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)  # whatever it left running in its session
            except (ProcessLookupError, PermissionError):
                pass
            process.wait()
        if process.returncode != 0:
            raise RuntimeError(f'soffice exited with {process.returncode}')
        result = out / 'document.pdf'
        with open(result, 'rb') as handle:
            pdf = handle.read(MAX_PDF_BYTES + 1)
        if len(pdf) > MAX_PDF_BYTES:
            raise RuntimeError('the converted PDF is too large')
        return pdf
    finally:
        shutil.rmtree(work, ignore_errors=True)
