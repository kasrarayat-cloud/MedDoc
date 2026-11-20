"""The document block of a coding request (BUILD-SPEC 4.3): the original file as the Anthropic API reads it.

- PDF: a base64 document block with citations, titled with the original file name. No local PDF parsing at all.
- DOCX: converted to PDF by LibreOffice (``soffice --headless --convert-to pdf``) in a bounded child
  (bounded.run_bounded: 60 s, a memory cap, a throwaway HOME and profile directory, no inherited environment); the PDF
  is sent as above. A failed conversion is DocumentError CONVERT. Before LibreOffice reads it, the Word file is made a
  package that cannot reach outside itself (``safe_package``, SEC-S6): only a Word package is converted (an
  OpenDocument file or any other zip named .docx is refused, since LibreOffice opens what it finds, whatever the name),
  every relationship with TargetMode External is dropped - a linked picture, template, frame or object LibreOffice
  would fetch from a URL or a local path while it converts, into the PDF that is sent and shown - with any part only
  they referenced, and the zip is rebuilt from what was read, so LibreOffice reads exactly what was checked.
- TXT (UTF-8; a leading byte-order mark is dropped) and pasted text: a text document block with citations.

The stored form of the block (``stored_block``, what ProviderRun.request_body keeps) replaces the base64 data with
{"$original_sha256", "$original_bytes"} of the bytes it carried; a converted Word file also names its source file.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import posixpath
import re
import shutil
import signal
import struct
import subprocess
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from xml.parsers import expat
from xml.sax.saxutils import quoteattr

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
# The Word package LibreOffice is given (safe_package; ECMA-376 Part 2, Open Packaging Conventions).
CONTENT_TYPES_PART = '[Content_Types].xml'
ROOT_RELATIONSHIPS_PART = '_rels/.rels'
RELATIONSHIPS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CONTENT_TYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
OFFICE_DOCUMENT_TYPES = ('http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
                         'http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument')
# The main part of a Word document or template (a macro-enabled one is not a .docx)
WORD_MAIN_TYPES = ('application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
                   'application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml')
# The parts that mark an OpenDocument package, which no Word file holds
OPENDOCUMENT_PARTS = ('mimetype', 'meta-inf/manifest.xml')
MAX_PACKAGE_PARTS = 10_000
MAX_PACKAGE_BYTES = 512 * 1024 * 1024  # what the parts may hold once inflated (the bounded child's memory is the cap)
URI_SCHEME = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*:')
# The throwaway profile's one setting, a second guard behind safe_package: LibreOffice's "block any links from
# documents not among the trusted locations" (none is trusted), so a link it would still find is not fetched either.
PROFILE_SETTINGS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
                    'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                    '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
                    '<prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>'
                    '</oor:items>\n')
# The API's refusal of the document (failure kind DOCUMENT), worded for what was uploaded.
REFUSED_TEXT = {'pdf': 'This PDF could not be read. It may be password-protected or damaged.',
                'docx': 'The Word file could not be read.',
                'txt': 'The text file could not be read.',
                'paste': 'The pasted text could not be read.'}


class PackageRefused(Exception):
    """The Word file is not a package LibreOffice may be given (safe_package); the reason is for the operator."""


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
    """``data`` (a Word file) as PDF bytes, converted in a bounded child (``runner``: the function run there on the
    package safe_package made of ``data``, default LibreOffice's); DocumentError CONVERT when it cannot be."""
    try:
        pdf = bounded.run_bounded(_convert_package, runner or soffice_convert, data, seconds=seconds,
                                  memory_bytes=memory_bytes)
    except bounded.Overrun as exc:
        raise DocumentError(CONVERT, CONVERT_TEXT, f'the conversion passed its {exc.reason} limit') from None
    except Exception as exc:  # noqa: BLE001 - the child's failure is logged by run_bounded
        raise DocumentError(CONVERT, CONVERT_TEXT, type(exc).__name__) from None
    if isinstance(pdf, tuple) and len(pdf) == 2 and pdf[0] == 'refused':
        raise DocumentError(CONVERT, CONVERT_TEXT, f'the Word package was refused: {pdf[1]}')
    if not isinstance(pdf, bytes) or not pdf.startswith(b'%PDF-'):
        raise DocumentError(CONVERT, CONVERT_TEXT, 'the conversion produced no PDF')
    return pdf


def _convert_package(runner, data: bytes):
    """In the bounded child (its memory cap and wall clock bound the zip and XML reading too): the PDF ``runner`` makes
    of safe_package(data), or ('refused', reason)."""
    try:
        package = safe_package(data)
    except PackageRefused as exc:
        return ('refused', str(exc))
    return runner(package)


def safe_package(data: bytes) -> bytes:
    """``data`` (an uploaded .docx) as a Word package that cannot reach outside itself when LibreOffice converts it
    (SEC-S6), or PackageRefused. Django-free; it runs in the bounded child.

    - It must be a Word package: a zip, every part named once (part names compare without case), none encrypted, at
      most MAX_PACKAGE_PARTS parts and MAX_PACKAGE_BYTES inflated; '[Content_Types].xml' and the package relationships
      ('_rels/.rels') present; the package's officeDocument relationship internal, naming a part present whose content
      type is a Word document's or template's main part; no part that marks an OpenDocument package. LibreOffice opens
      what it finds whatever the name says, so an OpenDocument file named .docx would otherwise be read as one.
    - Every relationship with a TargetMode other than Internal - an External relationship names a URL or a local path,
      which LibreOffice fetches while it converts (a linked picture, an attached template, a frame, an object) - is
      dropped from every relationships part, and any part only such relationships named is dropped with its own
      relationships. A relationships part that declares a DTD, or is not a Relationships element, is refused.
    - The zip is rebuilt from the parts as read, in their order, so LibreOffice reads exactly what was checked. Nothing
      else of any part is changed: the document's text, pictures and layout are LibreOffice's to read as written.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError):
        raise PackageRefused('it is not a zip archive') from None
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_PACKAGE_PARTS:
            raise PackageRefused(f'it has more than {MAX_PACKAGE_PARTS:,} parts')
        if any(info.flag_bits & 0x1 for info in infos):
            raise PackageRefused('a part is encrypted')
        if len({info.filename.casefold() for info in infos}) != len(infos):
            raise PackageRefused('a part is named twice')
        if sum(info.file_size for info in infos) > MAX_PACKAGE_BYTES:
            raise PackageRefused('its parts are too large once inflated')
        names = {info.filename for info in infos}
        if any(name.casefold() in OPENDOCUMENT_PARTS for name in names):
            raise PackageRefused('it is an OpenDocument package, not a Word file')
        if CONTENT_TYPES_PART not in names or ROOT_RELATIONSHIPS_PART not in names:
            raise PackageRefused('it is not a Word package (no content types or package relationships)')
        try:
            parts = {info.filename: archive.read(info) for info in infos}
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, ValueError, OSError, EOFError) as exc:
            raise PackageRefused(f'a part cannot be read ({type(exc).__name__})') from None
    by_folded = {name.casefold(): name for name in parts}
    _require_word_main_part(parts, by_folded)
    rewritten, dropped_targets, kept_targets = {}, set(), set()
    for name in parts:
        if not name.casefold().endswith('.rels'):
            continue
        kept, dropped = _relationships(name, parts[name])
        folder = _source_folder(name)
        for relationship in kept:
            target = _part_name(folder, relationship.get('Target', ''))
            if target is not None:
                kept_targets.add(target.casefold())
        for relationship in dropped:
            target = _part_name(folder, relationship.get('Target', ''))
            if target is not None:
                dropped_targets.add(target.casefold())
        if dropped:
            rewritten[name] = _relationships_xml(kept)
    special = {CONTENT_TYPES_PART.casefold()} | {name.casefold() for name in parts if name.casefold().endswith('.rels')}
    orphans = {by_folded[target] for target in dropped_targets - kept_targets - special if target in by_folded}
    for orphan in sorted(orphans):
        folder, _, leaf = orphan.rpartition('/')
        own = f'{folder}/_rels/{leaf}.rels' if folder else f'_rels/{leaf}.rels'
        orphans = orphans | ({by_folded[own.casefold()]} if own.casefold() in by_folded else set())
    out = io.BytesIO()
    try:
        with zipfile.ZipFile(out, 'w') as rebuilt:
            for info in infos:
                if info.filename in orphans:
                    continue
                fresh = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                stored = info.compress_type == zipfile.ZIP_STORED
                fresh.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
                rebuilt.writestr(fresh, rewritten.get(info.filename, parts[info.filename]))
    except (ValueError, OverflowError, struct.error, zipfile.LargeZipFile) as exc:
        raise PackageRefused(f'it cannot be rebuilt ({type(exc).__name__})') from None
    return out.getvalue()


def _xml(name, raw):
    """The root element of an XML part, refused when it declares a DTD (OPC allows none) or cannot be read."""
    probe = expat.ParserCreate()

    def no_dtd(*args):
        raise PackageRefused(f'{name} declares a DTD')
    probe.StartDoctypeDeclHandler = no_dtd
    probe.EntityDeclHandler = no_dtd
    try:
        probe.Parse(raw, True)
        return ElementTree.fromstring(raw)
    except (expat.ExpatError, ElementTree.ParseError, ValueError):
        raise PackageRefused(f'{name} is not well-formed XML') from None


def _local(tag) -> str:
    return tag.rpartition('}')[2] if isinstance(tag, str) else ''


def _relationships(name, raw):
    """(kept, dropped) Relationship elements of a relationships part: dropped, every one whose TargetMode (in any
    namespace) is not Internal; kept, the package relationships of the OPC namespace that are left."""
    root = _xml(name, raw)
    if root.tag != f'{{{RELATIONSHIPS_NS}}}Relationships':
        raise PackageRefused(f'{name} is not a package relationships part')
    kept, dropped = [], []
    for child in root:
        modes = [value for key, value in child.attrib.items() if _local(key) == 'TargetMode']
        if _local(child.tag) == 'Relationship' and any(mode != 'Internal' for mode in modes):
            dropped.append(child)
        elif child.tag == f'{{{RELATIONSHIPS_NS}}}Relationship':
            kept.append(child)
    return kept, dropped


def _relationships_xml(kept) -> bytes:
    """A relationships part holding exactly ``kept``, each with the attributes OPC defines."""
    rows = []
    for relationship in kept:
        attributes = ''.join(f' {key}={quoteattr(relationship.get(key))}'
                             for key in ('Id', 'Type', 'Target', 'TargetMode') if relationship.get(key) is not None)
        rows.append(f'<Relationship{attributes}/>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{RELATIONSHIPS_NS}">'
            f'{"".join(rows)}</Relationships>').encode('utf-8')


def _source_folder(relationships_name) -> str:
    """The folder a relationships part's targets are resolved in: that of the part it describes ('word/_rels/
    document.xml.rels' -> 'word'; '_rels/.rels', the package's own -> '')."""
    folder = relationships_name.rpartition('/')[0]
    return folder.rpartition('/')[0] if '/' in folder else ''


def _part_name(folder, target):
    """The package part a relationship's target names (a zip entry name), or None for a URI with a scheme, a network
    path or a path leaving the package."""
    target = (target or '').split('#', 1)[0]
    if not target or URI_SCHEME.match(target) or target.startswith('//'):
        return None
    path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(folder, target))
    return None if path in ('', '.', '..') or path.startswith('../') else path


def _require_word_main_part(parts, by_folded):
    """Refuses a package whose officeDocument relationship is missing, not internal, or names a part that is absent or
    whose content type is not a Word document's or template's main part."""
    root = _xml(ROOT_RELATIONSHIPS_PART, parts[ROOT_RELATIONSHIPS_PART])
    if root.tag != f'{{{RELATIONSHIPS_NS}}}Relationships':
        raise PackageRefused(f'{ROOT_RELATIONSHIPS_PART} is not a package relationships part')
    main = [child for child in root if child.tag == f'{{{RELATIONSHIPS_NS}}}Relationship'
            and child.get('Type') in OFFICE_DOCUMENT_TYPES]
    if len(main) != 1 or main[0].get('TargetMode', 'Internal') != 'Internal':
        raise PackageRefused('it names no single main document part inside the package')
    target = _part_name('', main[0].get('Target', ''))
    if target is None or target.casefold() not in by_folded:
        raise PackageRefused('its main document part is missing')
    types = _xml(CONTENT_TYPES_PART, parts[CONTENT_TYPES_PART])
    if types.tag != f'{{{CONTENT_TYPES_NS}}}Types':
        raise PackageRefused(f'{CONTENT_TYPES_PART} is not a content types part')
    found = None
    for child in types:
        if child.tag == f'{{{CONTENT_TYPES_NS}}}Override' and \
                (child.get('PartName') or '').lstrip('/').casefold() == target.casefold():
            found = child.get('ContentType')
    if found is None:
        extension = target.rpartition('.')[2].casefold() if '.' in target.rpartition('/')[2] else ''
        for child in types:
            if child.tag == f'{{{CONTENT_TYPES_NS}}}Default' and (child.get('Extension') or '').casefold() == extension:
                found = child.get('ContentType')
    if found not in WORD_MAIN_TYPES:  # compared exactly, as LibreOffice's own detection compares it
        raise PackageRefused('its main document part is not a Word document')


def soffice_convert(data: bytes) -> bytes:
    """LibreOffice's conversion, run inside the bounded child (Django-free) on the package safe_package made. A
    throwaway work directory holds the input, the output, HOME, TMPDIR and the LibreOffice profile (seeded with
    PROFILE_SETTINGS: no untrusted link is followed); the environment is built from nothing; soffice runs in a session
    of its own, which is killed whatever happens; the directory is removed."""
    work = Path(tempfile.mkdtemp(prefix=WORK_PREFIX))
    try:
        home, profile, out, tmp = (work / name for name in ('home', 'profile', 'out', 'tmp'))
        for folder in (home, profile, out, tmp, profile / 'user'):
            folder.mkdir(mode=0o700)
        (profile / 'user' / 'registrymodifications.xcu').write_text(PROFILE_SETTINGS, encoding='utf-8')
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
