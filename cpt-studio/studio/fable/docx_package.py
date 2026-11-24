"""The Word package LibreOffice is given, and LibreOffice's conversion of it (SEC-S6; release 1 E1-E3). No Django here:
the converter service (studio.converter_server) runs exactly the code the worker ran in-process, and
studio.fable.document re-exports every name, so its callers and tests keep theirs.

``convert_in_child`` is the one way a Word file becomes a PDF, for the worker's in-process path and for the converter
service alike (E1). Its caller - the parent - makes a throwaway work folder, runs ``_convert_package`` in a bounded
child (studio.bounded.run_bounded: CONVERT_SECONDS of wall clock, CONVERT_MEMORY_BYTES of address-space growth) and
removes the folder whatever happened. In the child, ``safe_package`` makes the upload a package that cannot reach
outside itself (within PACKAGE_SECONDS, checked between parts); then the runner - ``soffice_convert`` unless a test
gives another - converts it in that folder within SOFFICE_SECONDS, and tells the parent LibreOffice's process group
before it waits on it, so the parent's finally kills that group as well as the child, timeout or not.

``safe_package``:
- Only a Word package is converted (an OpenDocument file or any other zip named .docx is refused, since LibreOffice
  opens what it finds, whatever the name).
- Its size is checked from the zip directory before any part is read (E1): at most MAX_PART_BYTES a part and
  MAX_PACKAGE_BYTES in all once inflated, and no XML part (.xml or .rels, or any part read as XML later) over
  INFLATION_CHECKED_FROM that inflates more than MAX_INFLATION times its stored size - a picture is held to the size
  limits only, since a clinical image (an ECG strip kept as a metafile) can deflate 133-fold; each part is then read
  through a bounded reader that inflates at most its declared size plus one byte, so a size header that lies is
  refused, never believed. Running out of PACKAGE_SECONDS is not a refusal of the file: the conversion is busy, and a
  member may retry (ConversionBusy).
- Every relationship with TargetMode External is dropped - a linked picture, template, frame or object LibreOffice would
  fetch from a URL or a local path while it converts, into the PDF that is sent and shown - with any part only they
  referenced.
- Field instructions and embedded content LibreOffice could act on are removed (E2), in every part that holds them: the
  instruction of each field of a type in FIELD_INSTRUCTIONS_REMOVED (and of any field whose type its own text does not
  spell), keeping the result the reader sees; w:object (its preview picture kept), w:control and w:altChunk, with the
  parts only they named, and their Overrides in the content types. Each part is edited by byte ranges of its own
  bytes, never written out again, and a part with nothing to remove passes through byte for byte: a Word file with none
  of these features gives exactly the package it gave before release 1. A formula ('=' first) is never removed. What
  was removed is reported as counts only.
- The zip is rebuilt from the parts as read, in their order, so LibreOffice reads exactly what was checked. Nothing else
  of any part is changed: the document's text, pictures and layout are LibreOffice's to read as written.
"""
from __future__ import annotations

import bisect
import copy
import io
import logging
import os
import posixpath
import re
import shutil
import signal
import struct
import subprocess
import tempfile
import time
import zipfile
import zlib
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree
from xml.parsers import expat
from xml.sax.saxutils import escape, quoteattr

from .. import bounded

log = logging.getLogger(__name__)

# --- the conversion and its limits (E1) -----------------------------------------------------------------------------
# The bounded child's wall clock, which its parent keeps, is the sum of what the child does: the package checks, then
# LibreOffice, then a margin for the rest (starting, writing the package, reading the PDF back). LibreOffice keeps the
# 55 s it had before release 1, so no Word file that converts today times out (a deviation from spec E1, which took the
# checks' 10 s out of LibreOffice's time).
PACKAGE_SECONDS = 10  # safe_package's own, checked between parts (and every few thousand elements of a part)
SOFFICE_SECONDS = 55  # soffice's own, inside the child
CHILD_MARGIN_SECONDS = 5
CONVERT_SECONDS = PACKAGE_SECONDS + SOFFICE_SECONDS + CHILD_MARGIN_SECONDS  # 70
CONVERT_MEMORY_BYTES = 2 * 1024 ** 3  # address-space growth allowed to the child, a second guard behind its container
# The API takes 32 MB per request; base64 adds a third, so a PDF over 23 MiB (about 30.7 MB encoded) cannot fit with
# the instructions. Uploads stop at 15 MB; only a converted Word file can be larger.
MAX_PDF_BYTES = 23 * 1024 * 1024
SOFFICE = 'soffice'
WORK_PREFIX = 'cpt-convert-'  # the worker also removes leftover work folders at start (studio.jobs)
# The throwaway profile's one setting, a second guard behind safe_package: LibreOffice's "block any links from
# documents not among the trusted locations" (none is trusted), so a link it would still find is not fetched either.
PROFILE_SETTINGS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
                    'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                    '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
                    '<prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>'
                    '</oor:items>\n')

# --- the Word package (ECMA-376 Part 2, Open Packaging Conventions) --------------------------------------------------
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
MAX_PACKAGE_BYTES = 64 * 1024 * 1024  # what the parts may hold once inflated, in all (E1; it was 512 MiB)
MAX_PART_BYTES = 32 * 1024 * 1024  # and one part
MAX_INFLATION = 100  # a part may inflate to at most this many times its stored size...
INFLATION_CHECKED_FROM = 1024 * 1024  # ...once it inflates past this: a smaller part costs nothing whatever its ratio
URI_SCHEME = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*:')

# --- what E2 removes --------------------------------------------------------------------------------------------------
# A field whose type (the first word of its instruction) starts with one of these is neutralised: LibreOffice could
# act on its instruction while it converts - include a file of the server, fetch a picture, link or query a source.
FIELD_INSTRUCTIONS_REMOVED = ('INCLUDETEXT', 'INCLUDEPICTURE', 'INCLUDE', 'LINK', 'DDE', 'DDEAUTO', 'IMPORT',
                              'DATABASE')
WORD_NAMESPACES = ('http://schemas.openxmlformats.org/wordprocessingml/2006/main',  # transitional
                   'http://purl.oclc.org/ooxml/wordprocessingml/main')  # strict
RELATIONSHIP_ID_NAMESPACES = ('http://schemas.openxmlformats.org/officeDocument/2006/relationships',
                              'http://purl.oclc.org/ooxml/officeDocument/relationships')
VML_NAMESPACE = 'urn:schemas-microsoft-com:vml'
SVG_TYPE = 'image/svg+xml'  # an SVG picture may declare a DOCTYPE; no other part of a Word package may (OPC)


class PackageRefused(Exception):
    """The Word file is not a package LibreOffice may be given (safe_package); the reason, in fixed words, is for the
    operator."""


class _OutOfTime(PackageRefused):
    """safe_package passed PACKAGE_SECONDS."""


class ConversionRefused(Exception):
    """convert_in_child: safe_package refused the Word file; the reason is in fixed words."""


class ConversionBusy(Exception):
    """convert_in_child: the package checks ran out of PACKAGE_SECONDS - the conversion is busy, not the file refused;
    a member may retry."""


class ConversionFailed(Exception):
    """convert_in_child: no PDF came of the Word file (the child failed, passed a limit or made no PDF); the detail is
    in fixed words."""


def convert_in_child(data: bytes, *, runner=None, seconds=CONVERT_SECONDS, memory_bytes=CONVERT_MEMORY_BYTES) -> bytes:
    """``data`` (a Word file) as PDF bytes, converted in a bounded child: ``runner(package, work)`` runs there on the
    package safe_package made of ``data`` and the work folder made here (default soffice_convert). The folder is removed
    after every run - a success, a failure or a timeout - once the child and every process group it reported are gone.
    ConversionRefused when safe_package refused the file, ConversionBusy when its checks ran out of time,
    ConversionFailed when no PDF came of it."""
    try:
        work = Path(tempfile.mkdtemp(prefix=WORK_PREFIX))
    except OSError as exc:
        raise ConversionFailed(f'no work folder could be made ({type(exc).__name__})') from None
    try:
        try:
            answer = bounded.run_bounded(_convert_package, runner or soffice_convert, data, str(work), seconds=seconds,
                                         memory_bytes=memory_bytes)
        except bounded.Overrun as exc:
            raise ConversionFailed(f'the conversion passed its {exc.reason} limit') from None
        except Exception as exc:  # noqa: BLE001 - the child's failure is logged by run_bounded
            raise ConversionFailed(type(exc).__name__) from None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if isinstance(answer, tuple) and len(answer) == 2 and answer[0] == 'busy':
        raise ConversionBusy(answer[1])
    if isinstance(answer, tuple) and len(answer) == 2 and answer[0] == 'refused':
        raise ConversionRefused(answer[1])
    if not (isinstance(answer, tuple) and len(answer) == 3 and answer[0] == 'pdf'):
        raise ConversionFailed('the conversion produced no PDF')
    _, pdf, removed = answer
    if isinstance(removed, dict) and any(removed.values()):
        log.info('word package: %d field instructions, %d embedded objects, %d controls and %d imported documents '
                 'removed before conversion', removed.get('fields', 0), removed.get('objects', 0),
                 removed.get('controls', 0), removed.get('chunks', 0))
    if not isinstance(pdf, bytes) or not pdf.startswith(b'%PDF-'):
        raise ConversionFailed('the conversion produced no PDF')
    return pdf


def _convert_package(runner, data: bytes, work: str):
    """In the bounded child (its memory cap and wall clock bound the zip and XML reading too): ('pdf', what ``runner``
    makes of safe_package(data) in the work folder ``work``, the removal counts), ('refused', reason), or ('busy',
    reason) when the checks ran out of PACKAGE_SECONDS."""
    try:
        package, removed = _safe_package(data)
    except _OutOfTime as exc:
        return ('busy', str(exc))
    except PackageRefused as exc:
        return ('refused', str(exc))
    return ('pdf', runner(package, Path(work)), removed)


def safe_package(data: bytes) -> bytes:
    """``data`` (an uploaded .docx) as a Word package that cannot reach outside itself when LibreOffice converts it, or
    PackageRefused (the module's docstring says what is checked, dropped and removed). Django-free; it runs in the
    bounded child.

    - It must be a Word package: a zip, every part named once (part names compare without case), none encrypted, at
      most MAX_PACKAGE_PARTS parts, each part's size within E1's limits; '[Content_Types].xml' and the package
      relationships ('_rels/.rels') present; the package's officeDocument relationship internal, naming a part present
      whose content type is a Word document's or template's main part; no part that marks an OpenDocument package.
    - Every relationship with a TargetMode other than Internal is dropped from every relationships part, and any part
      only such relationships named is dropped with its own relationships. A relationships part that declares a DTD, or
      is not a Relationships element, is refused.
    - E2's removals (fields, objects, controls, imported documents), by byte ranges.
    - The zip is rebuilt from the parts as read, in their order.
    """
    return _safe_package(data)[0]


def _safe_package(data: bytes):
    """(safe_package's bytes, the counts of what E2 removed: {'fields', 'objects', 'controls', 'chunks'})."""
    deadline = time.monotonic() + PACKAGE_SECONDS
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
        _check_sizes(infos)
        names = {info.filename for info in infos}
        if any(name.casefold() in OPENDOCUMENT_PARTS for name in names):
            raise PackageRefused('it is an OpenDocument package, not a Word file')
        if CONTENT_TYPES_PART not in names or ROOT_RELATIONSHIPS_PART not in names:
            raise PackageRefused('it is not a Word package (no content types or package relationships)')
        parts = {}
        for info in infos:
            parts[info.filename] = _read_part(archive, info)
            _check_time(deadline)
    by_folded = {name.casefold(): name for name in parts}
    _require_word_main_part(parts, by_folded)
    rewritten, dropped_targets, kept_targets, kept_rows = {}, set(), set(), {}
    for name in parts:
        if not name.casefold().endswith('.rels'):
            continue
        kept, dropped = _relationships(name, parts[name])
        kept_rows[name] = kept
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
    removed, held = _remove_active_content(infos, parts, by_folded, kept_rows, rewritten, special, orphans, deadline)
    if orphans:  # a dropped part's Override goes with it
        types = _without_overrides(parts[CONTENT_TYPES_PART], {name.casefold() for name in orphans})
        if types is not parts[CONTENT_TYPES_PART]:
            rewritten[CONTENT_TYPES_PART] = types
    for name, refusal in held.items():  # a part that could not be checked is refused only if it is still sent
        if name not in orphans:
            raise refusal
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
    return out.getvalue(), removed


def _check_time(deadline):
    if time.monotonic() > deadline:
        raise _OutOfTime(f'checking it took longer than {PACKAGE_SECONDS} s')


def _check_sizes(infos):
    """E1, from the zip directory alone, before any part is read: no part over MAX_PART_BYTES once inflated, no more
    than MAX_PACKAGE_BYTES in all, and no XML part past INFLATION_CHECKED_FROM that inflates more than MAX_INFLATION
    times its stored size."""
    for info in infos:
        if info.file_size > MAX_PART_BYTES:
            raise PackageRefused('a part is too large once inflated')
        if _xml_named(info.filename) and _inflates_too_much(info):
            raise PackageRefused(f'a part inflates more than {MAX_INFLATION} times its stored size')
    if sum(info.file_size for info in infos) > MAX_PACKAGE_BYTES:
        raise PackageRefused('its parts are too large once inflated')


def _xml_named(name) -> bool:
    """Whether the part ``name`` is read as XML by its name (an .xml or .rels part)."""
    return name.casefold().endswith(('.xml', '.rels'))


def _inflates_too_much(info) -> bool:
    """Whether a part past INFLATION_CHECKED_FROM inflates more than MAX_INFLATION times its stored size."""
    return info.file_size > INFLATION_CHECKED_FROM and info.file_size > MAX_INFLATION * info.compress_size


def _read_part(archive, info) -> bytes:
    """A part's bytes through a bounded reader: it inflates at most the part's declared size plus one byte (zipfile
    alone stops at the declared size and trusts it), and a part whose bytes are not its declared size - a size header
    that lies, either way - is refused."""
    declared = info.file_size
    probe = copy.copy(info)
    probe.file_size = declared + 1
    try:
        with archive.open(probe) as handle:
            data = handle.read(declared + 1)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, ValueError, OSError, EOFError, zlib.error) as exc:
        raise PackageRefused(f'a part cannot be read ({type(exc).__name__})') from None
    if len(data) != declared:
        raise PackageRefused('a part is not the size its header says')
    return data


def _xml(name, raw):
    """The root element of an XML part, refused when it declares a DTD (OPC allows none) or cannot be read."""
    probe = expat.ParserCreate()

    def no_dtd(*args):
        raise PackageRefused('a package part declares a DTD')
    probe.StartDoctypeDeclHandler = no_dtd
    probe.EntityDeclHandler = no_dtd
    try:
        probe.Parse(raw, True)
        return ElementTree.fromstring(raw)
    except (expat.ExpatError, ElementTree.ParseError, ValueError):
        raise PackageRefused('a package part is not well-formed XML') from None


def _local(tag) -> str:
    return tag.rpartition('}')[2] if isinstance(tag, str) else ''


def _relationships(name, raw):
    """(kept, dropped) Relationship elements of a relationships part: dropped, every one whose TargetMode (in any
    namespace) is not Internal; kept, the package relationships of the OPC namespace that are left."""
    root = _xml(name, raw)
    if root.tag != f'{{{RELATIONSHIPS_NS}}}Relationships':
        raise PackageRefused('a relationships part is not a package relationships part')
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


# --- E2: field instructions and embedded content, removed by byte ranges -------------------------------------------

def _names(*local_names):
    return frozenset(f'{namespace} {local}' for namespace in WORD_NAMESPACES for local in local_names)


# The roles of the few elements E2 reads (an element's name is 'namespace local'); every other element is read past
# with one dictionary lookup.
_FLDCHAR, _FLDSIMPLE, _OBJECT, _CONTROL, _ALTCHUNK, _POINTER, _TEXT, _SYMBOL, _SPACE = range(9)
_ROLES = {name: role for role, local_names in (
    (_FLDCHAR, ('fldChar',)), (_FLDSIMPLE, ('fldSimple',)), (_OBJECT, ('object',)), (_CONTROL, ('control',)),
    (_ALTCHUNK, ('altChunk',)), (_POINTER, ('objectEmbed', 'objectLink')),
    (_TEXT, ('instrText', 'delInstrText', 't', 'delText')), (_SYMBOL, ('sym',)), (_SPACE, ('tab', 'ptab', 'br', 'cr')))
    for name in _names(*local_names)}
# What points at an embedded or linked object: inside a w:object it goes with the object; anywhere else on its own.
_ROLES['urn:schemas-microsoft-com:office:office OLEObject'] = _POINTER
_CONTAINERS = (_OBJECT, _CONTROL, _ALTCHUNK, _POINTER)  # removed whole (an object but for its preview)
_OBJECTS, _DRAWINGS, _FLDDATAS = _names('object'), _names('drawing'), _names('fldData')
# How a reader might assemble a field's instruction - from all its text, from the instruction elements only, from the
# text not deleted, or from w:instrText alone - and whether a symbol's character, a tab or a break counts in it. The
# type is read in each, and a field any reading finds removed is removed, so no reader's view of an instruction is
# wider than this one's. A field Word wrote reads the same in all four.
_READINGS = ((_names('instrText', 'delInstrText', 't', 'delText'), True), (_names('instrText', 'delInstrText'), False),
             (_names('instrText', 't'), True), (_names('instrText'), False))
# the attributes as WordprocessingML qualifies them, and unqualified: a reader lenient about the prefix must not see a
# field here missed
_FLDCHARTYPE = tuple(f'{namespace} fldCharType' for namespace in WORD_NAMESPACES) + ('fldCharType',)
_INSTR = tuple(f'{namespace} instr' for namespace in WORD_NAMESPACES) + ('instr',)
_SYMBOL_CHAR = tuple(f'{namespace} char' for namespace in WORD_NAMESPACES) + ('char',)
_RELATIONSHIP_ID_PREFIXES = tuple(f'{namespace} ' for namespace in RELATIONSHIP_ID_NAMESPACES)
_WORD_PREFIXES = tuple(f'{namespace} ' for namespace in WORD_NAMESPACES)
_VML_PREFIX = f'{VML_NAMESPACE} '
# A part is read for E2 only when its bytes hold one of these elements' tags (any prefix): element names are literal in
# a part's bytes, so a part without one has nothing E2 removes.
_TRIGGER = re.compile(rb'<(?:[^\s<>/:!?"\'=]+:)?(?:fldChar|fldSimple|instrText|delInstrText|object|control|altChunk'
                      rb'|OLEObject|objectEmbed|objectLink)[\s/>]')
_DOCTYPE = re.compile(rb'<!DOCTYPE')
_TAG = re.compile(rb'<(?:[^"\'>]|"[^"]*"|\'[^\']*\')*>')  # one tag, from its '<' to its '>' (quotes may hold '>')
_TAG_NAME = re.compile(rb'<([^\s/>]+)')
_DECLARED_ENCODING = re.compile(rb'^(?:\xef\xbb\xbf)?<\?xml[^>]*?encoding\s*=\s*["\']([A-Za-z0-9._-]+)["\']')
_SKIP_PREFIX = re.compile('[\\s\\\\"\'\\u201c\\u201d\\u2018\\u2019]*')  # white space, backslashes and quotes
_LETTER_RUN = re.compile(r'[A-Za-z]*')
_TYPE_LETTERS = max(len(name) for name in FIELD_INSTRUCTIONS_REMOVED)  # letters enough to decide a type
_TIME_CHECK_ELEMENTS = 0xFFF  # the deadline is checked every 4,096 elements too
_REMOVED_KINDS = ('fields', 'objects', 'controls', 'chunks')
_REREADS = 4  # how often a part may be read again after a removal inside another field's instruction (see below)
# An element as the reader keeps it: a list [name, offset of its start tag, the namespaces its start tag declares, its
# property children (only while a field's instruction is open), its children (a w:fldSimple's or w:object's only),
# expat's index at its end (an end tag's '<', or the end of an empty element), a w:fldSimple's instruction].
_NAME, _AT, _DECLARED, _PROPS, _CHILDREN, _END, _INSTRUCTION = range(7)


class _Reading:
    """One reading of a field's instruction, as far as it names the field's type: white space, backslashes and quotes
    are read past, and the type is the run of letters that follows, ended by anything else (a space, a quote, a digit,
    a nested field) - so IF{PAGE} is IF. Anything else first names no type that is removed: an '=' first is a formula,
    which is kept, whatever bookmark names follow it ('= Included + 1'). A nested field before anything is read leaves
    the type unreadable, and the field is removed."""
    __slots__ = ('state', 'letters')
    BEFORE, LETTERS, DONE, UNREADABLE = range(4)

    def __init__(self):
        self.state, self.letters = self.BEFORE, ''

    @property
    def done(self) -> bool:
        return self.state >= self.DONE

    def feed(self, text):
        at, end = 0, len(text)
        if self.state == self.BEFORE:
            at = _SKIP_PREFIX.match(text).end()
            if at == end:
                return
            if not ('A' <= text[at] <= 'Z' or 'a' <= text[at] <= 'z'):  # an '=', a digit: no type removed
                self.state = self.DONE
                return
            self.state = self.LETTERS
        if self.state == self.LETTERS:
            run = _LETTER_RUN.match(text, at)
            self.letters = (self.letters + run.group())[:_TYPE_LETTERS]
            if run.end() < end or len(self.letters) >= _TYPE_LETTERS:
                self.state = self.DONE

    def nested(self):
        if self.state == self.BEFORE:
            self.state = self.UNREADABLE
        elif self.state == self.LETTERS:
            self.state = self.DONE

    def removed(self) -> bool:
        return self.state == self.UNREADABLE or self.letters.upper().startswith(FIELD_INSTRUCTIONS_REMOVED)


def _removed_type(text) -> bool:
    """Whether ``text`` (a w:fldSimple's instruction) names a field E2 removes, read as _Reading reads one."""
    reading = _Reading()
    reading.feed(text or '')
    return reading.removed()


def _symbol_character(attrs) -> str:
    """The character a w:sym stands for (its w:char, hexadecimal), as a reader would put it in an instruction."""
    try:
        code = int(next((attrs[key] for key in _SYMBOL_CHAR if key in attrs), ''), 16)
    except ValueError:
        return '\ufffd'
    return chr(code) if 0 < code < 0x110000 else '\ufffd'


class _Field:
    """A complex field (w:fldChar begin ... separate ... end) while it is read: its marks with the open elements around
    each, and its type in each of the _READINGS as far as its own instruction has named it."""
    __slots__ = ('begin', 'begin_chain', 'separates', 'end', 'readings', 'decided', 'in_instruction')

    def __init__(self, begin, chain):
        self.begin, self.begin_chain, self.separates, self.end = begin, chain, [], None
        self.readings = [_Reading() for _ in _READINGS]
        self.decided, self.in_instruction = False, True

    def feed(self, text, name=None):
        """Text of the instruction: in a text element ``name``, or (None) a symbol's character, a tab or a break."""
        for (kinds, run_content), reading in zip(_READINGS, self.readings):
            if not reading.done and (name in kinds if name is not None else run_content):
                reading.feed(text)
        self.decided = all(reading.done for reading in self.readings)

    def nested(self):
        for reading in self.readings:
            reading.nested()
        self.decided = all(reading.done for reading in self.readings)

    def removed(self) -> bool:
        return any(reading.removed() for reading in self.readings)


class _PartReader:
    """One part read once with expat (namespaces resolved): the byte ranges E2 removes from it, the tags it renames,
    the counts, and the relationship ids found where a removal can reach. ``editable``: whether edits can be made in its
    bytes (UTF-8 only); when not, a part that needs one is refused. ``nested_removal``: a field was removed inside
    another field's instruction, whose type its result may now complete (_edited_part reads the part again)."""

    def __init__(self, raw, deadline, *, editable=True):
        self.raw, self.deadline, self.editable = raw, deadline, editable
        self.stack, self.fields, self.edits, self.declared, self.references = [], [], [], [], []
        self.removed = dict.fromkeys(_REMOVED_KINDS, 0)
        self.elements = self.instructions = self.containers = 0
        self.text_field = self.text_name = self.parser = None
        self.nested_removal = False

    def read(self):
        parser = self.parser = expat.ParserCreate(namespace_separator=' ')
        parser.buffer_text = True
        parser.StartElementHandler, parser.EndElementHandler = self._start, self._end
        parser.StartNamespaceDeclHandler = self._namespace
        parser.XmlDeclHandler = self._declaration
        parser.StartDoctypeDeclHandler = parser.EntityDeclHandler = _refuse_dtd
        try:
            parser.Parse(self.raw, True)
        except expat.ExpatError:
            if _begins_as_xml(self.raw):
                raise PackageRefused('a document part is not well-formed XML') from None
            self.edits = []  # not XML at all (a picture whose bytes happened to match): nothing a reader acts on
            return self
        for field in self.fields:
            if field.removed():
                raise PackageRefused('a field to be removed is not closed')
        return self

    # expat's handlers
    def _namespace(self, prefix, uri):
        self.declared.append((prefix, uri))

    def _declaration(self, version, encoding, standalone):
        if encoding and encoding.casefold() not in ('utf-8', 'us-ascii', 'ascii'):
            self.editable = False

    def _start(self, name, attrs):
        self.elements += 1
        if not self.elements & _TIME_CHECK_ELEMENTS:
            _check_time(self.deadline)
        stack, declared = self.stack, self.declared
        if declared:  # the declarations go with this element; the next one starts a list of its own
            self.declared = []
        element = [name, self.parser.CurrentByteIndex, declared or (), None, None, None, None]
        if stack and stack[-1][_CHILDREN] is not None:
            stack[-1][_CHILDREN].append(element)
        role = _ROLES.get(name)
        if role is not None:
            self._role_starts(role, element, attrs)
        if attrs and (self.instructions or self.containers):  # inside what a removal can take: its relationship ids
            for key, value in attrs.items():
                if key.startswith(_RELATIONSHIP_ID_PREFIXES):
                    self.references.append((element[_AT], value))
        stack.append(element)

    def _role_starts(self, role, element, attrs):
        field = self.fields[-1] if self.fields else None
        open_type = field is not None and not field.decided  # a field whose type is still being read
        if role == _FLDCHAR:
            kind = next((attrs[key] for key in _FLDCHARTYPE if key in attrs), None)
            if kind == 'begin':
                if open_type:
                    field.nested()
                self.fields.append(_Field(element, list(self.stack)))
                self.instructions += 1
            elif kind == 'separate' and field is not None:
                field.separates.append((element, list(self.stack)))
                if field.in_instruction:
                    field.in_instruction = False
                    self.instructions -= 1
                field.decided = True
            elif kind == 'end' and field is not None:
                field.end = (element, list(self.stack))
                field.decided = True
        elif role == _FLDSIMPLE:
            if open_type:
                field.nested()
            element[_CHILDREN] = []
            element[_INSTRUCTION] = next((attrs[key] for key in _INSTR if key in attrs), '')
        elif role in _CONTAINERS:
            self.containers += 1
            if role == _OBJECT:
                element[_CHILDREN] = []
        elif role == _TEXT:
            if open_type:
                self.text_field, self.text_name = field, element[_NAME]
                self.parser.CharacterDataHandler = self._text
        elif open_type:  # a symbol stands for its character, a tab or a break for white space
            field.feed(_symbol_character(attrs) if role == _SYMBOL else ' ')

    def _end(self, name):
        element = self.stack.pop()
        element[_END] = self.parser.CurrentByteIndex
        role = _ROLES.get(name)
        if role is None:
            if self.instructions and name.endswith('Pr') and self.stack and name.startswith(_WORD_PREFIXES):
                parent = self.stack[-1]
                if parent[_PROPS] is None:
                    parent[_PROPS] = []
                parent[_PROPS].append(element)
            return
        if role == _TEXT:
            if self.text_field is not None:
                self.text_field = None
                self.parser.CharacterDataHandler = None
        elif role == _FLDCHAR:
            field = self.fields[-1] if self.fields else None
            if field is not None and field.end is not None and field.end[0] is element:
                self.fields.pop()
                if field.in_instruction:
                    self.instructions -= 1
                if field.removed():
                    self._remove_field(field)
                    self.nested_removal = self.nested_removal or bool(self.instructions)
        elif role == _FLDSIMPLE:
            if _removed_type(element[_INSTRUCTION]):
                self._remove_simple_field(element)
                self.nested_removal = self.nested_removal or bool(self.instructions)
        elif role in _CONTAINERS:
            self.containers -= 1
            if role == _OBJECT:
                self._remove_object(element)
            else:
                self._remove(element)
                if role == _CONTROL:
                    self.removed['controls'] += 1
                elif role == _ALTCHUNK:
                    self.removed['chunks'] += 1
                elif not any(ancestor[_NAME] in _OBJECTS for ancestor in self.stack):
                    self.removed['objects'] += 1  # a pointer outside an object; inside one the object counts

    def _text(self, data):
        field = self.text_field
        if field is not None and not field.decided:
            field.feed(data, self.text_name)

    # the removals
    def _edit(self, start, end, replacement=b''):
        if not self.editable:
            raise PackageRefused('a document part that needs a change is not UTF-8')
        self.edits.append((start, end, replacement))

    def _tag_end(self, at):
        match = _TAG.match(self.raw, at)
        if match is None:
            raise PackageRefused('a document part cannot be edited safely')
        return match.end()

    def _span(self, element):
        """(start, end) of ``element``'s bytes, from its start tag's '<' to its end tag's '>'."""
        start_end = self._tag_end(element[_AT])
        if self.raw[start_end - 2] == 0x2F:  # '/>': an empty element is its start tag
            return element[_AT], start_end
        return element[_AT], self._tag_end(element[_END])

    def _remove(self, element):
        self._edit(*self._span(element))

    def _remove_between(self, first, first_chain, last, last_chain):
        """Removes everything from the start of ``first`` to the end of ``last`` (a field's begin mark and its separate
        or end mark), keeping only what the elements around them need to stay whole: below the element both are in, the
        end tags of ``first``'s ancestors and the start tags and property children (pPr, rPr, ...) of ``last``'s."""
        common = 0
        for mine, theirs in zip(first_chain, last_chain):
            if mine is not theirs:
                break
            common += 1
        low, high = first[_AT], self._span(last)[1]
        kept = [(element[_END], self._tag_end(element[_END])) for element in first_chain[common:]]
        for element in last_chain[common:]:
            kept.append((element[_AT], self._tag_end(element[_AT])))
            for prop in element[_PROPS] or ():
                span = self._span(prop)
                if span[0] >= low and span[1] <= last[_AT]:
                    kept.append(span)
        at = low
        for start, end in sorted(kept):
            if start > at:
                self._edit(at, start)
            at = max(at, end)
        if high > at:
            self._edit(at, high)

    def _remove_field(self, field):
        """A complex field's instruction goes - begin to separate, and the end mark - and its result stays; with no
        separate there is no result, and begin to end goes."""
        if field.separates:
            separate, separate_chain = field.separates[0]
            self._remove_between(field.begin, field.begin_chain, separate, separate_chain)
            for extra, _ in field.separates[1:]:
                self._remove(extra)
            self._remove(field.end[0])
        else:
            self._remove_between(field.begin, field.begin_chain, *field.end)
        self.removed['fields'] += 1

    def _unwrap(self, element, keep):
        """Removes ``element``'s start and end tags and every child but those ``keep`` accepts."""
        if element[_DECLARED]:
            raise PackageRefused('a field or object to be removed declares namespaces of its own')
        start_end = self._tag_end(element[_AT])
        self._edit(element[_AT], start_end)
        for child in element[_CHILDREN]:
            if not keep(child):
                self._remove(child)
        self._edit(element[_END], self._tag_end(element[_END]))

    def _remove_simple_field(self, element):
        """A w:fldSimple's instruction is its attribute: its start and end tags go (and its w:fldData), its runs - the
        result the reader sees - stay."""
        start_end = self._tag_end(element[_AT])
        if self.raw[start_end - 2] == 0x2F:
            self._edit(element[_AT], start_end)
        else:
            self._unwrap(element, lambda child: child[_NAME] not in _FLDDATAS)
        self.removed['fields'] += 1

    def _remove_object(self, element):
        """A w:object goes, and its preview picture stays where there is one: a DrawingML one (w:drawing) in its place,
        a VML one (v:shape) as the w:pict it would be without the object."""
        start_end = self._tag_end(element[_AT])
        children = element[_CHILDREN] or []
        drawings = [child for child in children if child[_NAME] in _DRAWINGS]
        pictures = [child for child in children if child[_NAME].startswith(_VML_PREFIX)]
        if self.raw[start_end - 2] == 0x2F or not (drawings or pictures):
            self._remove(element)
        elif drawings:
            self._unwrap(element, lambda child: child[_NAME] in _DRAWINGS)
        else:
            qualified = _TAG_NAME.match(self.raw, element[_AT]).group(1)
            prefix = qualified.rpartition(b':')[0]
            pict = prefix + b':pict' if prefix else b'pict'
            declarations = ''.join(f' xmlns={quoteattr(uri)}' if declared is None
                                   else f' xmlns:{declared}={quoteattr(uri)}' for declared, uri in element[_DECLARED])
            self._edit(element[_AT], start_end, b'<' + pict + declarations.encode('utf-8') + b'>')
            for child in children:
                if not child[_NAME].startswith(_VML_PREFIX):
                    self._remove(child)
            self._edit(element[_END], self._tag_end(element[_END]), b'</' + pict + b'>')
        self.removed['objects'] += 1


def _refuse_dtd(*args):
    raise PackageRefused('a document part declares a DTD')


def _merged(edits):
    """``edits`` (start, end, replacement) in order, each inside a removal dropped (the removal takes it with it); two
    that overlap otherwise cannot both be made, and the part is refused."""
    merged = []
    for start, end, replacement in sorted(edits, key=lambda edit: (edit[0], -edit[1], edit[2] != b'')):
        if merged:
            last_start, last_end, last_replacement = merged[-1]
            if start >= last_start and end <= last_end and last_replacement == b'':
                continue
            if start < last_end:
                raise PackageRefused('a document part cannot be edited safely')
        merged.append((start, end, replacement))
    return merged


def _applied(raw, edits) -> bytes:
    out, at = [], 0
    for start, end, replacement in edits:
        out += [raw[at:start], replacement]
        at = end
    out.append(raw[at:])
    return b''.join(out)


def _wide(raw) -> bool:
    """Whether ``raw`` may be XML in a two- or four-byte encoding (a UTF-16 or UTF-32 byte order mark, or a NUL among
    its first bytes), whose tags its bytes do not spell."""
    return raw[:2] in (b'\xff\xfe', b'\xfe\xff') or b'\x00' in raw[:4]


def _begins_as_xml(raw) -> bool:
    """Whether ``raw`` starts as XML would ('<' after a byte order mark and white space, whatever its encoding): one
    that then fails to parse is refused, never passed on half-read."""
    head = raw[:256]
    for mark in (b'\xef\xbb\xbf', b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff', b'\xff\xfe', b'\xfe\xff'):
        if head.startswith(mark):
            head = head[len(mark):]
            break
    return head.replace(b'\x00', b'').lstrip(b' \t\r\n').startswith(b'<')


def _editable(raw) -> bool:
    if _wide(raw):
        return False
    declared = _DECLARED_ENCODING.match(raw[:256])
    return declared is None or declared.group(1).decode('ascii').casefold() in ('utf-8', 'us-ascii', 'ascii')


def _named_by(references, edits) -> set:
    """The relationship ids among ``references`` ((offset, id) pairs) that lie in what ``edits`` take."""
    starts, found = [start for start, _, _ in edits], set()
    for offset, value in references:
        at = bisect.bisect_right(starts, offset) - 1
        if at >= 0 and edits[at][0] <= offset < edits[at][1]:
            found.add(value)
    return found


def _still_named(data, values) -> set:
    """Which of ``values`` (relationship ids) some attribute of ``data`` still holds, found by their bytes (as written,
    or with XML's escapes): a relationship whose id any kept attribute holds is kept."""
    found = set()
    for value in values:
        for form in {value, escape(value, {'"': '&quot;', "'": '&apos;'})}:
            if re.search(rb'=\s*(["\'])' + re.escape(form.encode('utf-8')) + rb'\1', data):
                found.add(value)
    return found


def _well_formed(data):
    """Refuses an edited part that expat no longer parses (namespaces resolved): read in C, with no handler."""
    try:
        expat.ParserCreate(namespace_separator=' ').Parse(data, True)
    except expat.ExpatError:
        raise PackageRefused('a document part could not be edited safely') from None


def _edited_part(raw, deadline):
    """(``raw`` with E2's removals made, their counts, the relationship ids only removed content named), or None when
    nothing is to be removed - the part then passes through byte for byte.

    The part is read once. What the edit must not break is confirmed without reading it again in Python: the edits only
    take whole elements, or whole tags of one element, so expat - in C, with no handler - confirms it still parses
    (well-formed, every prefix bound); and an id some kept attribute still holds keeps its relationship, found by its
    bytes. The one way an edit can make a new instruction is a field removed inside another field's instruction: its
    result, kept, now stands in that instruction, and may complete the outer field's type ('LI' and a removed field's
    result 'NK'). Only then is the part read again, and edited again, until nothing more is removed."""
    reader = _PartReader(raw, deadline, editable=_editable(raw)).read()
    if not reader.edits:
        return None
    data, removed, gone = raw, dict.fromkeys(_REMOVED_KINDS, 0), set()
    for _ in range(_REREADS):
        edits = _merged(reader.edits)
        gone |= _named_by(reader.references, edits)
        for kind in _REMOVED_KINDS:
            removed[kind] += reader.removed[kind]
        data = _applied(data, edits)
        if not reader.nested_removal:
            break
        reader = _PartReader(data, deadline).read()
        if not reader.edits:
            break
    else:
        raise PackageRefused('a document part could not be edited safely')
    _well_formed(data)
    return data, removed, gone - _still_named(data, gone)


def _content_types(raw):
    """({extension: content type}, {part name: content type}) of the content types part, all folded."""
    defaults, overrides = {}, {}
    for child in _xml(CONTENT_TYPES_PART, raw):
        if child.tag == f'{{{CONTENT_TYPES_NS}}}Default':
            defaults[(child.get('Extension') or '').casefold()] = (child.get('ContentType') or '').casefold()
        elif child.tag == f'{{{CONTENT_TYPES_NS}}}Override':
            part = (child.get('PartName') or '').lstrip('/').casefold()
            overrides[part] = (child.get('ContentType') or '').casefold()
    return defaults, overrides


def _content_type(name, types) -> str:
    defaults, overrides = types
    folded = name.casefold()
    if folded in overrides:
        return overrides[folded]
    leaf = folded.rpartition('/')[2]
    return defaults.get(leaf.rpartition('.')[2], '') if '.' in leaf else ''


def _without_overrides(raw, dropped) -> bytes:
    """The content types part ``raw`` without the Override of any part in ``dropped`` (folded part names), removed by
    byte range; ``raw`` itself when it overrides none of them - or when it is not UTF-8, whose bytes are not edited (a
    stale Override names a part that is not there, which a reader passes over)."""
    if not _editable(raw):
        return raw
    spans, opened = [], []
    parser = expat.ParserCreate(namespace_separator=' ')

    def start(name, attrs):
        part = (attrs.get('PartName') or '').lstrip('/')
        hit = name == f'{CONTENT_TYPES_NS} Override' and bool({part.casefold(), unquote(part).casefold()} & dropped)
        opened.append(parser.CurrentByteIndex if hit else None)

    def end(name):
        at = opened.pop()
        if at is not None:
            start_end = _TAG.match(raw, at).end()
            stop = start_end if raw[start_end - 2] == 0x2F else _TAG.match(raw, parser.CurrentByteIndex).end()
            spans.append((at, stop))
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.Parse(raw, True)  # read already (_xml): well-formed, with no DTD
    return _applied(raw, [(at, stop, b'') for at, stop in spans]) if spans else raw


def _refuse_any_dtd(raw):
    """Refuses ``raw`` when an XML parser reading it would meet a DTD; anything else wrong with it is not this
    check's."""
    probe = expat.ParserCreate()
    probe.StartDoctypeDeclHandler = probe.EntityDeclHandler = _refuse_dtd
    try:
        probe.Parse(raw, True)
    except expat.ExpatError:
        pass


def _remove_active_content(infos, parts, by_folded, kept_rows, rewritten, special, orphans, deadline):
    """E2 over every part still sent (not a relationships part or the content types): a part whose bytes hold field or
    object markup is read and edited (``rewritten``), and every part that would bring a DTD to a parser is refused - an
    SVG picture's excepted. A part read as XML here is held to E1's inflation ratio like an .xml part. The relationships
    only removed content named are dropped (``kept_rows`` and ``rewritten`` updated) and the parts only they named added
    to ``orphans``. Returns (the counts, {part: the refusal held until it is known whether the part is still sent})."""
    removed, held, dropped_ids = dict.fromkeys(_REMOVED_KINDS, 0), {}, {}
    types = _content_types(parts[CONTENT_TYPES_PART])
    for info in infos:
        name = info.filename
        if name in orphans or name.casefold() in special:
            continue
        raw = parts[name]
        view = raw.replace(b'\x00', b'') if _wide(raw) else raw
        try:
            triggered = _TRIGGER.search(view) is not None
            if triggered or (_DOCTYPE.search(view) and _content_type(name, types) != SVG_TYPE):
                if not _xml_named(name) and _inflates_too_much(info) and _begins_as_xml(raw):
                    raise PackageRefused(f'a part inflates more than {MAX_INFLATION} times its stored size')
            if triggered:
                outcome = _edited_part(raw, deadline)
                if outcome is not None:
                    rewritten[name], counts, ids = outcome
                    for kind in _REMOVED_KINDS:
                        removed[kind] += counts[kind]
                    if ids:
                        dropped_ids[name] = ids
            elif _DOCTYPE.search(view) and _content_type(name, types) != SVG_TYPE:
                _refuse_any_dtd(raw)
        except _OutOfTime:
            raise
        except PackageRefused as exc:
            held[name] = exc
        _check_time(deadline)
    candidates = set()
    for name, ids in dropped_ids.items():
        folder, _, leaf = name.rpartition('/')
        own = (f'{folder}/_rels/{leaf}.rels' if folder else f'_rels/{leaf}.rels').casefold()
        if own not in by_folded or by_folded[own] in orphans:
            continue
        rels = by_folded[own]
        gone = [row for row in kept_rows[rels] if row.get('Id') in ids]
        if not gone:
            continue
        kept_rows[rels] = [row for row in kept_rows[rels] if row.get('Id') not in ids]
        rewritten[rels] = _relationships_xml(kept_rows[rels])
        for row in gone:
            target = _part_name(_source_folder(rels), row.get('Target', ''))
            if target is not None:
                candidates.add(target.casefold())
    orphans |= _released(candidates, kept_rows, by_folded, special, orphans)
    return removed, held


def _released(candidates, kept_rows, by_folded, special, dropped):
    """The parts (``candidates``, folded names) that nothing still sent names once E2 dropped the relationships of what
    it removed, each with its own relationships part, and in turn what only those named."""
    released = set()
    while candidates:
        gone = dropped | released
        named = set()
        for rels, rows in kept_rows.items():
            if rels in gone:
                continue
            folder = _source_folder(rels)
            for row in rows:
                target = _part_name(folder, row.get('Target', ''))
                if target is not None:
                    named.add(target.casefold())
        fresh = {by_folded[target] for target in candidates
                 if target in by_folded and target not in named and target not in special} - gone
        candidates = set()
        for part in sorted(fresh):
            released.add(part)
            folder, _, leaf = part.rpartition('/')
            own = (f'{folder}/_rels/{leaf}.rels' if folder else f'_rels/{leaf}.rels').casefold()
            if own in by_folded:
                rels = by_folded[own]
                released.add(rels)
                for row in kept_rows.get(rels, ()):
                    target = _part_name(_source_folder(rels), row.get('Target', ''))
                    if target is not None:
                        candidates.add(target.casefold())
    return released


# --- LibreOffice ----------------------------------------------------------------------------------------------------

def soffice_convert(data: bytes, work=None) -> bytes:
    """LibreOffice's conversion, run inside the bounded child (Django-free) on the package safe_package made, in the
    work folder ``work`` its parent made (none given: a folder of its own, removed after). The folder holds the input,
    the output, HOME, TMPDIR and the LibreOffice profile (seeded with PROFILE_SETTINGS: no untrusted link is followed);
    the environment is built from nothing; soffice runs in a session of its own, whose process group is told to the
    parent before it is waited on (studio.bounded.report_group: the parent kills it whatever happens here) and is
    killed here too, whatever happens."""
    own = work is None
    work = Path(tempfile.mkdtemp(prefix=WORK_PREFIX)) if own else Path(work)
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
        bounded.report_group(process.pid)  # its own session: the group id is its pid
        try:
            process.wait(timeout=SOFFICE_SECONDS)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)  # whatever it left running in its session
            except (ProcessLookupError, PermissionError):
                pass
            bounded.group_ended(process.pid)  # before the wait: until it is reaped, its group id cannot be reused
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
        if own:
            shutil.rmtree(work, ignore_errors=True)
