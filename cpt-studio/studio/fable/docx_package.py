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
  MAX_PACKAGE_BYTES in all once inflated; each part is then read through a bounded reader that inflates at most its
  declared size plus one byte, so a size header that lies is refused, never believed. No part is held to a ratio of
  its inflated to its stored size, an XML part no more than a picture: report generators write uniform table XML that
  deflates 127 to 158 times (a vital-signs flowsheet, a medication grid) and a clinical image can deflate 133 times (an
  ECG strip kept as a metafile), and the code before release 1 converts both. What a part may cost is bounded by these
  absolute limits, not by how well it compressed - a crafted part with varied bytes reaches them at a ratio of 2 - and
  by the bounded child's limits (CONVERT_MEMORY_BYTES of address space, CONVERT_SECONDS) and its container's.
  Running out of PACKAGE_SECONDS is not a refusal of the file: the conversion is busy, and a member may retry
  (ConversionBusy).
- Every relationship with TargetMode External is dropped - a linked picture, template, frame or object LibreOffice would
  fetch from a URL or a local path while it converts, into the PDF that is sent and shown - with any part only they
  referenced. The content types keep their bytes then, as before release 1: an Override left for a part that is not
  there is one a reader passes over (repair round 1, C4).
- Field instructions and embedded content LibreOffice could act on are removed (E2), in every part that holds them: the
  instruction of each field of a type in FIELD_INSTRUCTIONS_REMOVED (and of any field whose type its own text does not
  spell), keeping the result the reader sees - a field's type read from its live instruction text, text a tracked
  change deleted counting only when nothing live names a type (_Field); w:object (its preview picture kept), w:control
  and a w:altChunk that holds nothing, with the parts only they named, and their Overrides in the content types. Each
  part is edited by byte ranges of its own bytes, never written out again, and a part with nothing to remove passes
  through byte for byte: a Word file with none of these features gives exactly the package it gave before release 1. A
  formula ('=' first) is never removed. What was removed is reported as counts only.
- Release 2 (Group F's rule: E2 never takes content out of a Word file while leaving nothing of it in the PDF). Where it
  would, the file is refused, ContentNotShown, with counts and a code for the member's sentence, and nothing of it is
  rebuilt or converted: a w:altChunk whose r:id names a relationship to a part present and not empty, in any format,
  story or namespace form, and - on purpose, although the file holds nothing of it - one whose relationship is External,
  and every w:subDoc, which the doctor's own Word can pull in (R2-28); an object, control or pointer that would leave no
  picture - a v:imagedata or a:blip naming a part that is sent - in its place (R2-29); a field kept, not HYPERLINK or
  TOC, whose stored result holds something a reader sees outside the fields in it while a removed field stood in its
  instruction, which LibreOffice 7.4 drops (R2-30's fallback). An altChunk that holds nothing (no r:id, or one naming
  no relationship, a missing part or an empty part) is removed as release 1 removes it, counted in 'chunks'. A
  removed field in another field's result, and in no field's instruction, stays a field whose instruction is QUOTE -
  a type LibreOffice shows by its stored result - unless it is INCLUDEPICTURE (R2-30). Everything else is edited as
  release 1 edits it, so a Word file that needs no refusal and no QUOTE gives exactly release 1's package.
  check_in_child runs the same check on a Word file whose conversion a round stored, before that conversion is read
  again (R2-28 step 7, C8).
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
MAX_PART_BYTES = 32 * 1024 * 1024  # and one part (no ratio of inflated to stored size: the module's docstring)
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
DRAWINGML_NAMESPACES = ('http://schemas.openxmlformats.org/drawingml/2006/main',  # transitional
                        'http://purl.oclc.org/ooxml/drawingml/main')  # strict
SVG_TYPE = 'image/svg+xml'  # an SVG picture may declare a DOCTYPE; no other part of a Word package may (OPC)


class PackageRefused(Exception):
    """The Word file is not a package LibreOffice may be given (safe_package); the reason, in fixed words, is for the
    operator."""


class _OutOfTime(PackageRefused):
    """safe_package passed PACKAGE_SECONDS."""


# --- release 2 (R2-28 to R2-30): what E2 would take out of a Word file and leave nothing of in the PDF ----------------
INSERTED_DOCUMENT, INSERTED_OBJECT = 'inserted_document', 'inserted_object'  # ContentNotShown's codes (R2-28)
REFUSAL_CODES = (INSERTED_DOCUMENT, INSERTED_OBJECT)
# What ContentNotShown counts: inserted documents (a w:altChunk that holds content or reaches outside, a w:subDoc:
# R2-28), objects and controls that would leave no picture (R2-29), and fields whose stored result LibreOffice 7.4
# loses once a field in their instruction is removed (R2-30's fallback, its own count; told as an inserted document,
# the lead's decision in refutation round 1: every removed field type pulls content from outside the file).
LOST_KINDS = ('documents', 'objects', 'controls', 'fields')
CONTENT_NOT_SHOWN = 'it holds inserted content that could not be shown in the PDF'  # names no part and no text


class ContentNotShown(PackageRefused):
    """E2 would take content out of the Word file and leave nothing of it in the PDF (release 2, Group F's rule): the
    file is refused, and nothing of it is converted. ``counts``: how many of each of LOST_KINDS; ``code``:
    INSERTED_DOCUMENT when it holds an inserted document or a field R2-30's fallback counts, else INSERTED_OBJECT -
    which of the two sentences a member reads (studio.fable.document.REFUSED_PACKAGE_TEXT)."""

    def __init__(self, counts):
        self.counts = {kind: counts.get(kind, 0) for kind in LOST_KINDS}
        self.code = INSERTED_DOCUMENT if self.counts['documents'] or self.counts['fields'] else INSERTED_OBJECT
        super().__init__(CONTENT_NOT_SHOWN)


class ConversionRefused(Exception):
    """convert_in_child (and check_in_child): safe_package refused the Word file; the reason is in fixed words.
    ``code`` and ``counts``: a ContentNotShown's (R2-31), else '' and {}."""

    def __init__(self, reason, code='', counts=None):
        super().__init__(reason)
        self.code, self.counts = code, dict(counts or {})


class ConversionBusy(Exception):
    """convert_in_child: the package checks ran out of PACKAGE_SECONDS - the conversion is busy, not the file refused;
    a member may retry."""


class ConversionFailed(Exception):
    """convert_in_child: no PDF came of the Word file (the child failed, passed a limit or made no PDF); the detail is
    in fixed words."""


class ConversionAbandoned(Exception):
    """convert_in_child: whoever asked for the conversion left before it finished (``watch``), so it was stopped - the
    child and LibreOffice killed as at a timeout (repair round 1, C2)."""


def convert_in_child(data: bytes, *, runner=None, seconds=CONVERT_SECONDS, memory_bytes=CONVERT_MEMORY_BYTES,
                     watch=None) -> bytes:
    """``data`` (a Word file) as PDF bytes, converted in a bounded child: ``runner(package, work)`` runs there on the
    package safe_package made of ``data`` and the work folder made here (default soffice_convert). The folder is removed
    after every run - a success, a failure or a timeout - once the child and every process group it reported are gone.
    ConversionRefused when safe_package refused the file, ConversionBusy when its checks ran out of time,
    ConversionFailed when no PDF came of it, ConversionAbandoned when ``watch`` (the client's connection, for the
    converter service) became readable first: its client left."""
    try:
        work = Path(tempfile.mkdtemp(prefix=WORK_PREFIX))
    except OSError as exc:
        raise ConversionFailed(f'no work folder could be made ({type(exc).__name__})') from None
    try:
        try:
            answer = bounded.run_bounded(_convert_package, runner or soffice_convert, data, str(work), seconds=seconds,
                                         memory_bytes=memory_bytes, watch=watch)
        except bounded.Abandoned:
            raise ConversionAbandoned('its client left before it finished') from None
        except bounded.Overrun as exc:
            raise ConversionFailed(f'the conversion passed its {exc.reason} limit') from None
        except Exception as exc:  # noqa: BLE001 - the child's failure is logged by run_bounded
            raise ConversionFailed(type(exc).__name__) from None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if isinstance(answer, tuple) and len(answer) == 2 and answer[0] == 'busy':
        raise ConversionBusy(answer[1])
    if isinstance(answer, tuple) and len(answer) == 4 and answer[0] == 'refused':
        raise ConversionRefused(*answer[1:])
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
    makes of safe_package(data) in the work folder ``work``, the removal counts), ('refused', reason, code, counts) - a
    ContentNotShown's code and counts, else '' and {} (R2-31) -, or ('busy', reason) when the checks ran out of
    PACKAGE_SECONDS."""
    try:
        package, removed = _safe_package(data)
    except _OutOfTime as exc:
        return ('busy', str(exc))
    except ContentNotShown as exc:
        return ('refused', str(exc), exc.code, dict(exc.counts))
    except PackageRefused as exc:
        return ('refused', str(exc), '', {})
    return ('pdf', runner(package, Path(work)), removed)


def check_in_child(data: bytes, *, seconds=CONVERT_SECONDS, memory_bytes=CONVERT_MEMORY_BYTES) -> bool:
    """Release 2, R2-28 step 7 (C8): release 2's package check of ``data`` - a Word file a round of whose revision
    stored its conversion - before that conversion is read again, run as a conversion's check runs (in a bounded child
    of ``seconds`` and ``memory_bytes``, safe_package's own PACKAGE_SECONDS inside it) and converting nothing.

    False: the stored conversion may be read again - the check refused nothing and made none of R2-30's edits, so the
    package is the one release 1 gave; or the file is no Word package at all (refused before any part of it was read,
    by the checks release 1 runs too), which no stored conversion came of. True: the round converts afresh - R2-30's
    edit applies to the file, or the check refused it once its parts were read for a reason that is not
    ContentNotShown, which a fresh conversion then gives. ConversionRefused (with ContentNotShown's code and counts),
    ConversionBusy or ConversionFailed otherwise, as convert_in_child raises them."""
    try:
        answer = bounded.run_bounded(_check_package, data, seconds=seconds, memory_bytes=memory_bytes)
    except bounded.Overrun as exc:
        raise ConversionFailed(f'the check passed its {exc.reason} limit') from None
    except Exception as exc:  # noqa: BLE001 - the child's failure is logged by run_bounded
        raise ConversionFailed(type(exc).__name__) from None
    if isinstance(answer, tuple) and len(answer) == 2 and answer[0] == 'busy':
        raise ConversionBusy(answer[1])
    if isinstance(answer, tuple) and len(answer) == 4 and answer[0] == 'refused':
        raise ConversionRefused(*answer[1:])
    if isinstance(answer, tuple) and len(answer) == 2 and answer[0] == 'checked' and answer[1] in (True, False):
        return answer[1]
    raise ConversionFailed('the check gave no answer')


def _check_package(data: bytes):
    """In check_in_child's bounded child: ('checked', whether the round converts afresh), ('refused', reason, code,
    counts) for ContentNotShown, or ('busy', reason)."""
    report = {}
    try:
        _package(data, report)
    except _OutOfTime as exc:
        return ('busy', str(exc))
    except ContentNotShown as exc:
        return ('refused', str(exc), exc.code, dict(exc.counts))
    except PackageRefused:
        return ('checked', bool(report.get('read')))
    return ('checked', report.get('shells', 0) > 0)


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
    - E2's removals (fields, objects, controls, imported documents that hold nothing), by byte ranges.
    - Release 2 (Group F's rule): a file E2 would take content out of while leaving nothing of it in the PDF is refused,
      ContentNotShown, and nothing of it is rebuilt or converted - an imported document that holds content or reaches
      outside and every subdocument (R2-28), an object or a control that would leave no picture (R2-29), a field whose
      stored result LibreOffice 7.4 loses once a field in its instruction goes (R2-30's fallback). A removed field in
      another field's result stays a field whose instruction is QUOTE (R2-30). Everything else is edited as release 1
      edits it: a Word file that needs no refusal and no QUOTE gives exactly release 1's package.
    - The zip is rebuilt from the parts as read, in their order.
    """
    return _safe_package(data)[0]


def _safe_package(data: bytes):
    """(safe_package's bytes, the counts of what E2 removed: {'fields', 'objects', 'controls', 'chunks'})."""
    return _package(data, {})


def _package(data: bytes, report: dict):
    """_safe_package's work. ``report`` is told how far it got, whether it returns or raises: 'read', once every part
    was read and the package found a Word one (E2 then begins); 'shells', how many of R2-30's QUOTE shells it made in
    the parts still sent (check_in_child reads both)."""
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
    rewritten, dropped_targets, kept_targets, kept_rows, dropped_rows = {}, set(), set(), {}, {}
    for name in parts:
        if not name.casefold().endswith('.rels'):
            continue
        kept, dropped = _relationships(name, parts[name])
        kept_rows[name], dropped_rows[name] = kept, dropped
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
    external_orphans = frozenset(orphans)  # what the rule before release 1 drops: the content types keep their bytes
    report['read'] = True
    removed, held, unshown, shells = _remove_active_content(infos, parts, by_folded, kept_rows, dropped_rows, rewritten,
                                                            special, orphans, deadline)
    report['shells'] = sum(made for name, made in shells.items() if name not in orphans)
    released = orphans - external_orphans  # what E2 dropped, with the content it removed
    if released:  # a part E2 dropped takes its Override with it
        types = _without_overrides(parts[CONTENT_TYPES_PART], {name.casefold() for name in released})
        if types is not parts[CONTENT_TYPES_PART]:
            rewritten[CONTENT_TYPES_PART] = types
    for name, refusal in held.items():  # a part that could not be checked is refused only if it is still sent
        if name not in orphans:
            raise refusal
    # release 2: what E2 would leave nothing of, in the parts still sent - the file is refused, and never rebuilt
    lost = {kind: sum(counts[kind] for name, counts in unshown.items() if name not in orphans) for kind in LOST_KINDS}
    if any(lost.values()):
        raise ContentNotShown(lost)
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
    """E1, from the zip directory alone, before any part is read: no part over MAX_PART_BYTES once inflated, and no
    more than MAX_PACKAGE_BYTES in all. A part's ratio of inflated to stored size is not held against it (the module's
    docstring says why)."""
    for info in infos:
        if info.file_size > MAX_PART_BYTES:
            raise PackageRefused('a part is too large once inflated')
    if sum(info.file_size for info in infos) > MAX_PACKAGE_BYTES:
        raise PackageRefused('its parts are too large once inflated')


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
# with one dictionary lookup. A w:subDoc shares the w:altChunk's role (R2-28 step 5); a w:pict is read for R2-29 only.
_FLDCHAR, _FLDSIMPLE, _OBJECT, _CONTROL, _ALTCHUNK, _POINTER, _TEXT, _SYMBOL, _SPACE, _DELETION, _PICT = range(11)
_ROLES = {name: role for role, local_names in (
    (_FLDCHAR, ('fldChar',)), (_FLDSIMPLE, ('fldSimple',)), (_OBJECT, ('object',)), (_CONTROL, ('control',)),
    (_ALTCHUNK, ('altChunk', 'subDoc')), (_POINTER, ('objectEmbed', 'objectLink')),
    (_TEXT, ('instrText', 'delInstrText', 't', 'delText')), (_SYMBOL, ('sym',)), (_SPACE, ('tab', 'ptab', 'br', 'cr')),
    (_DELETION, ('del', 'moveFrom')), (_PICT, ('pict',)))
    for name in _names(*local_names)}
# Text a tracked change deleted: these elements inside a w:del or w:moveFrom (repair round 1, C5: see _Field).
_DELETED_TEXT = _names('delInstrText', 'delText')
# What points at an embedded or linked object: inside a w:object it goes with the object; anywhere else on its own.
OLE_OBJECT = 'urn:schemas-microsoft-com:office:office OLEObject'
_ROLES[OLE_OBJECT] = _POINTER
_CONTAINERS = (_OBJECT, _CONTROL, _ALTCHUNK, _POINTER)  # removed whole (an object but for its preview)
_OBJECTS, _DRAWINGS, _FLDDATAS = _names('object'), _names('drawing'), _names('fldData')
# Release 2, R2-28: a w:subDoc is always an inserted document (a master document's subdocuments are other files); a
# w:altChunk is one when its r:id names a relationship that reaches outside, or a part present and not empty.
_SUBDOCS = _names('subDoc')
_ALTCHUNK_IDS = tuple(f'{namespace} id' for namespace in RELATIONSHIP_ID_NAMESPACES)
# R2-29: what a w:object may hold beside VML and a w:drawing - the pointers, which show nothing themselves, and a
# movie - and what a picture is: a v:imagedata (r:id or o:relid) or an a:blip (r:embed) whose part is sent.
_OBJECT_POINTERS = _names('objectEmbed', 'objectLink', 'control', 'movie') | {OLE_OBJECT}
_SHAPETYPE = f'{VML_NAMESPACE} shapetype'
_PICTURE_KEYS = {f'{VML_NAMESPACE} imagedata': tuple(f'{namespace} id' for namespace in RELATIONSHIP_ID_NAMESPACES)
                 + ('urn:schemas-microsoft-com:office:office relid',)}
_PICTURE_KEYS.update({f'{namespace} blip': tuple(f'{relationships} embed'
                                                 for relationships in RELATIONSHIP_ID_NAMESPACES)
                      for namespace in DRAWINGML_NAMESPACES})
# R2-30's fallback: what a reader sees in a field's stored result besides text - a picture, a drawing, an object.
_SHOWN = _names('drawing', 'pict', 'object')
# outer types whose stored result 7.4 keeps with release 1's edit (R2-30): HYPERLINK and TOC, and QUOTE and STYLEREF
# (the lead's 7.4 run on lane D's corpus inputs H7f and H7g, refutation round 1); any other type, an unknown name
# included, stays refused - LibreOffice evaluates many real types
_EXEMPT_OUTER_TYPES = ('HYPERLINK', 'TOC', 'QUOTE', 'STYLEREF')
_PICTURE_TYPE = 'INCLUDEPICTURE'  # a removed type whose result is a picture LibreOffice draws wherever it stands
# How a reader might assemble a field's instruction - from all its text, from the instruction elements only, from the
# text not deleted, or from w:instrText alone - and whether a symbol's character, a tab or a break counts in it. The
# type is read in each, and a field any reading finds removed is removed, so no reader's view of an instruction is
# wider than this one's. A field Word wrote reads the same in all four. In each, text a tracked change deleted counts
# only when the live text names no type (_Field).
_READINGS =((_names('instrText', 'delInstrText', 't', 'delText'), True), (_names('instrText', 'delInstrText'), False),
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
                      rb'|OLEObject|objectEmbed|objectLink|subDoc)[\s/>]')
_DOCTYPE = re.compile(rb'<!DOCTYPE')
_TAG = re.compile(rb'<(?:[^"\'>]|"[^"]*"|\'[^\']*\')*>')  # one tag, from its '<' to its '>' (quotes may hold '>')
_TAG_NAME = re.compile(rb'<([^\s/>]+)')
_ATTRIBUTE = re.compile(rb'([^\s=/>"\']+)\s*=\s*("[^"]*"|\'[^\']*\')')  # one attribute of a tag, and its quoted value
_DECLARED_ENCODING = re.compile(rb'^(?:\xef\xbb\xbf)?<\?xml[^>]*?encoding\s*=\s*["\']([A-Za-z0-9._-]+)["\']')
_SKIP_PREFIX = re.compile('[\\s\\\\"\'\\u201c\\u201d\\u2018\\u2019]*')  # white space, backslashes and quotes
_LETTER_RUN = re.compile(r'[A-Za-z]*')
# Letters enough to decide a type, and one more, so that INCLUDEPICTURE is told from a longer word (R2-30): a type is
# removed when its letters begin with a removed one, which the extra letter never changes.
_TYPE_LETTERS = max(len(name) for name in FIELD_INSTRUCTIONS_REMOVED) + 1
_TIME_CHECK_ELEMENTS = 0xFFF  # the deadline is checked every 4,096 elements too
_REMOVED_KINDS = ('fields', 'objects', 'controls', 'chunks')
_REREADS = 4  # how often a part may be read again after a removal inside another field's instruction (see below)
# An element as the reader keeps it: a list [name, offset of its start tag, the namespaces its start tag declares, its
# property children (only while a field's instruction is open), its children (a w:fldSimple's or w:object's only),
# expat's index at its end (an end tag's '<', or the end of an empty element), a w:fldSimple's instruction - or, for a
# w:altChunk or w:subDoc, whether it is refused as an inserted document (R2-28)].
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


def _names_a_picture(text) -> bool:
    """Whether ``text`` (a w:fldSimple's instruction) names INCLUDEPICTURE and nothing longer, read as _Reading reads
    one (R2-30: its result, a picture, is unwrapped as release 1 unwraps it)."""
    reading = _Reading()
    reading.feed(text or '')
    return reading.letters.upper() == _PICTURE_TYPE


def _symbol_character(attrs) -> str:
    """The character a w:sym stands for (its w:char, hexadecimal), as a reader would put it in an instruction."""
    try:
        code = int(next((attrs[key] for key in _SYMBOL_CHAR if key in attrs), ''), 16)
    except ValueError:
        return '\ufffd'
    return chr(code) if 0 < code < 0x110000 else '\ufffd'


class _Field:
    """A complex field (w:fldChar begin ... separate ... end) while it is read: its marks with the open elements around
    each, and its type in each of the _READINGS as far as its own instruction has named it.

    A field's type is read from its live instruction text (repair round 1, C5: the L-CODING lens's coding-4, a PAGE
    field whose instruction holds a tracked deletion of 'LINK' was neutralised). Text a tracked change deleted - a
    w:delInstrText or w:delText inside a w:del or w:moveFrom - is read apart, and counts only when the live text names
    no type: a field deleted whole, or whose whole instruction is a deletion. That is how LibreOffice reads it, measured
    on a real LibreOffice (24.2): it renders the base's 'deleted LINK, inserted PAGE' as a live page number, a deleted
    'PA' before a live 'GE' as GE, and a w:moveFrom like a w:del; it reads a deleted instruction when nothing else is
    left of it, a w:delInstrText outside any deletion, and a w:instrText inside one - so those count as here."""
    __slots__ = ('begin', 'begin_chain', 'separates', 'end', 'readings', 'decided', 'in_instruction', 'holds_removed',
                 'watched', 'result_shown')

    def __init__(self, begin, chain):
        self.begin, self.begin_chain, self.separates, self.end = begin, chain, [], None
        self.readings = [[_Reading(), None] for _ in _READINGS]  # [live, deleted (made when deleted text comes)]
        self.decided, self.in_instruction = False, True
        # R2-30's fallback: a removed field stood in this field's instruction; its result is read (from its first
        # separate); it holds something a reader sees outside the fields in it
        self.holds_removed = self.watched = self.result_shown = False

    def feed(self, text, name=None, deleted=False):
        """Text of the instruction: in a text element ``name`` (``deleted``: a tracked change deleted it), or (None) a
        symbol's character, a tab or a break."""
        for (kinds, run_content), pair in zip(_READINGS, self.readings):
            live = pair[0]
            if name is None:
                if run_content and not live.done:
                    live.feed(text)
            elif name in kinds:
                if not deleted:
                    if not live.done:
                        live.feed(text)
                elif live.state == _Reading.BEFORE:  # deleted text counts only while nothing live names a type
                    if pair[1] is None:
                        pair[1] = _Reading()
                    if not pair[1].done:
                        pair[1].feed(text)
        self.decided = all(pair[0].done for pair in self.readings)

    def nested(self):
        for live, deleted in self.readings:
            live.nested()
            if deleted is not None:
                deleted.nested()
        self.decided = all(pair[0].done for pair in self.readings)

    def removed(self) -> bool:
        return any((live if live.state != _Reading.BEFORE or deleted is None else deleted).removed()
                   for live, deleted in self.readings)

    def _types(self) -> set:
        """The type every reading names (its letters, as removed() reads them), in capitals."""
        return {(live if live.state != _Reading.BEFORE or deleted is None else deleted).letters.upper()
                for live, deleted in self.readings}

    def names_a_picture(self) -> bool:
        """INCLUDEPICTURE in every reading (R2-30): its result, a picture, is unwrapped as release 1 unwraps it."""
        return self._types() == {_PICTURE_TYPE}

    def loses_its_result(self) -> bool:
        """R2-30's fallback, read at a kept field's end once a removed field stood in its instruction: a type every
        reading names other than HYPERLINK, TOC, QUOTE or STYLEREF, and a stored result that holds, outside the fields
        in it, something a reader sees - 7.4's 'H01' shape, whose plain result LibreOffice 7.4 drops, with or without
        R2-30's QUOTE. A result that is fields alone keeps every word on 7.4 (H02-H04, I01, I02: the QUOTE keeps a
        removed one)."""
        types = self._types()
        exempt = len(types) == 1 and next(iter(types)) in _EXEMPT_OUTER_TYPES
        return bool(self.separates) and self.result_shown and not exempt


class _PartReader:
    """One part read once with expat (namespaces resolved): the byte ranges E2 removes from it, the tags it renames,
    the counts, and the relationship ids found where a removal can reach. ``editable``: whether edits can be made in its
    bytes (UTF-8 only); when not, a part that needs one is refused. ``nested_removal``: a field was removed inside
    another field's instruction, whose type its result may now complete (_edited_part reads the part again).

    Release 2: ``lost`` counts what E2 would leave nothing of in the PDF (LOST_KINDS: ContentNotShown), and ``shells``
    the removed fields kept as QUOTE fields (R2-30). ``pictures``: the part's relationship ids that name a part present
    and not empty, ``external``: those that reach outside (_relationship_ids). ``carried``: the offsets of the fields
    an earlier reading of the part found a removed field in the instruction of (R2-30's fallback, decided once no field
    of the part is removed inside an instruction any more: _edited_part)."""

    def __init__(self, raw, deadline, *, editable=True, pictures=frozenset(), external=frozenset(),
                 carried=frozenset()):
        self.raw, self.deadline, self.editable = raw, deadline, editable
        self.pictures, self.external, self.carried = pictures, external, carried
        self.stack, self.fields, self.edits, self.declared, self.references = [], [], [], [], []
        self.removed = dict.fromkeys(_REMOVED_KINDS, 0)
        self.lost = dict.fromkeys(LOST_KINDS, 0)
        # R2-29: the open w:object and w:pict, each [element, 'controls' once it holds a control, its pointers], and the
        # offsets of the pictures that stand in them (in document order)
        self.holders, self.pictured = [], []
        # R2-30: QUOTE shells made; the fields found holding a removed field in their instruction (their offsets) and
        # how many of them lose their result (counted in lost['fields'] by the reading that removes nothing more inside
        # an instruction)
        self.shells, self.candidates, self.unshown = 0, [], 0
        self.elements = self.instructions = self.containers = self.deletions = 0  # deletions: open w:del, w:moveFrom
        self.watched = 0  # open fields whose result is read for R2-30's fallback
        self.text_field = self.text_name = self.parser = self.shown_field = None
        self.nested_removal = self.text_deleted = False

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
        if not self.nested_removal:  # R2-30's fallback: no field's type can change by another reading of the part
            self.lost['fields'] += self.unshown
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
        if self.holders and name in _PICTURE_KEYS and any(attrs.get(key) in self.pictures
                                                          for key in _PICTURE_KEYS[name]):
            self.pictured.append(element[_AT])  # R2-29: a picture whose part is sent, in an open object or w:pict
        if self.watched and name in _SHOWN and self.fields and self.fields[-1].watched:
            self.fields[-1].result_shown = True  # R2-30's fallback: a picture in the result a field holds
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
                    if field.holds_removed or field.begin[_AT] in self.carried:  # R2-30's fallback: read its result
                        field.watched = True
                        self.watched += 1
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
                self.holders.append([element, '', 0])
            elif role == _ALTCHUNK:  # R2-28 step 4: refused when it holds content or reaches outside; every w:subDoc
                element[_INSTRUCTION] = element[_NAME] in _SUBDOCS or any(
                    attrs[key] in self.pictures or attrs[key] in self.external for key in _ALTCHUNK_IDS if key in attrs)
            elif self.holders:  # R2-29 step 4: a pointer or a control counts in the w:object or w:pict it stands in
                holder = self.holders[-1]
                holder[2] += 1
                if role == _CONTROL:
                    holder[1] = 'controls'
            else:  # and in neither, it is lost
                self.lost['controls' if role == _CONTROL else 'objects'] += 1
        elif role == _PICT:
            self.holders.append([element, '', 0])
        elif role == _TEXT:
            if open_type:
                self.text_field, self.text_name = field, element[_NAME]
                self.text_deleted = bool(self.deletions) and element[_NAME] in _DELETED_TEXT
                self.parser.CharacterDataHandler = self._text
            elif field is not None and field.watched and not field.result_shown:
                self.shown_field = field  # R2-30's fallback: text in the result being read
                self.parser.CharacterDataHandler = self._shown_text
        elif role == _DELETION:
            self.deletions += 1
        elif open_type:  # a symbol stands for its character, a tab or a break for white space
            field.feed(_symbol_character(attrs) if role == _SYMBOL else ' ')
        elif role == _SYMBOL and field is not None and field.watched:
            field.result_shown = True

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
            if self.text_field is not None or self.shown_field is not None:
                self.text_field = self.shown_field = None
                self.parser.CharacterDataHandler = None
        elif role == _DELETION:
            self.deletions -= 1
        elif role == _FLDCHAR:
            field = self.fields[-1] if self.fields else None
            if field is not None and field.end is not None and field.end[0] is element:
                self.fields.pop()
                if field.in_instruction:
                    self.instructions -= 1
                if field.watched:
                    self.watched -= 1
                if field.removed():
                    if not self.instructions and field.separates and self._in_a_result() \
                            and not field.names_a_picture():
                        self._shell_field(field)
                    else:
                        self._remove_field(field)
                        self._removed_in_an_instruction(field.names_a_picture())
                elif field.holds_removed or field.begin[_AT] in self.carried:
                    self.candidates.append(field.begin[_AT])  # R2-30's fallback (read)
                    self.unshown += field.loses_its_result()
        elif role == _FLDSIMPLE:
            if _removed_type(element[_INSTRUCTION]):
                picture = _names_a_picture(element[_INSTRUCTION])
                if not self.instructions and self._in_a_result() and not picture \
                        and self.raw[self._tag_end(element[_AT]) - 2] != 0x2F:
                    self._shell_simple_field(element)
                else:
                    self._remove_simple_field(element)
                    self._removed_in_an_instruction(picture)
        elif role in _CONTAINERS:
            self.containers -= 1
            if role == _OBJECT:
                self._end_object(element, self.holders.pop())
            elif role == _ALTCHUNK:
                if element[_INSTRUCTION]:  # R2-28: refused as an inserted document; no edit is made
                    self.lost['documents'] += 1
                else:  # it holds nothing: removed as release 1 removes it
                    self._remove(element)
                    self.removed['chunks'] += 1
            else:
                self._remove(element)
                if role == _CONTROL:
                    self.removed['controls'] += 1
                elif not any(ancestor[_NAME] in _OBJECTS for ancestor in self.stack):
                    self.removed['objects'] += 1  # a pointer outside an object; inside one the object counts
        elif role == _PICT:  # R2-29 step 4: lost when its pictures are fewer than the pointers or controls it holds
            _, kind, pointers = self.holders.pop()
            if self._pictures_in(element) < pointers:
                self.lost[kind or 'objects'] += 1

    def _text(self, data):
        field = self.text_field
        if field is not None and not field.decided:
            field.feed(data, self.text_name, self.text_deleted)

    def _shown_text(self, data):
        if data.strip():
            self.shown_field.result_shown = True

    # release 2
    def _in_a_result(self) -> bool:
        """Whether what just ended lies in another field's result (asked while no field's instruction is open): an open
        complex field, or a w:fldSimple around it (R2-30)."""
        return bool(self.fields) or any(_ROLES.get(element[_NAME]) == _FLDSIMPLE for element in self.stack)

    def _removed_in_an_instruction(self, picture):
        """A removed field just went as release 1 removes it. Inside another field's instruction (release 1's re-read),
        every field whose instruction is open holds it - unless it was INCLUDEPICTURE (R2-30's fallback)."""
        if self.instructions:
            self.nested_removal = True
            if not picture:
                for field in self.fields:
                    if field.in_instruction:
                        field.holds_removed = True

    def _pictures_in(self, element) -> int:
        """How many pictures whose part is sent stand in ``element`` (R2-29)."""
        return (bisect.bisect_left(self.pictured, element[_END])
                - bisect.bisect_left(self.pictured, element[_AT]))

    def _end_object(self, element, holder):
        """R2-29 step 3: a w:object is lost - under 'controls' when it held a control, else 'objects' - when its
        pictures are fewer than its pointers, when it holds anything but VML, w:drawing and pointers, when it has both a
        drawing and a VML shape, or when it points at something with no drawing and other than exactly one VML shape:
        the file is refused and the object left as it is. Otherwise it is removed as release 1 removes it."""
        _, kind, pointers = holder
        children = element[_CHILDREN] or []
        drawings = [child for child in children if child[_NAME] in _DRAWINGS]
        shapes = [child for child in children if child[_NAME].startswith(_VML_PREFIX) and child[_NAME] != _SHAPETYPE]
        beside = [child for child in children if child[_NAME] not in _DRAWINGS and child[_NAME] not in _OBJECT_POINTERS
                  and not child[_NAME].startswith(_VML_PREFIX)]
        if self._pictures_in(element) < pointers or beside or (drawings and shapes) \
                or (pointers and not drawings and len(shapes) != 1):
            self.lost[kind or 'objects'] += 1
            return
        self._remove_object(element)

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

    def _remove_between(self, first, first_chain, last, last_chain, marks=True):
        """Removes everything from the start of ``first`` to the end of ``last`` (a field's begin mark and its separate
        or end mark), keeping only what the elements around them need to stay whole: below the element both are in, the
        end tags of ``first``'s ancestors and the start tags and property children (pPr, rPr, ...) of ``last``'s. With
        ``marks`` False, ``first`` and ``last`` themselves stay: what stands between them goes (R2-30)."""
        common = 0
        for mine, theirs in zip(first_chain, last_chain):
            if mine is not theirs:
                break
            common += 1
        low, high = (first[_AT], self._span(last)[1]) if marks else (self._span(first)[1], last[_AT])
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

    def _shell_field(self, field):
        """R2-30: a removed complex field in another field's result stays a field, of a type LibreOffice shows by its
        stored result: its begin mark is followed by the instruction ' QUOTE ' (an instrText of the begin mark's own
        prefix, with any namespaces the mark declares), what stood between the begin and separate marks goes, and the
        separate mark, the result and the end mark stay. The count stays under fields."""
        separate, separate_chain = field.separates[0]
        start, end = self._span(field.begin)
        prefix = _TAG_NAME.match(self.raw, start).group(1).rpartition(b':')[0]
        tag = prefix + b':instrText' if prefix else b'instrText'
        declarations = ''.join(f' xmlns={quoteattr(uri)}' if declared is None else f' xmlns:{declared}={quoteattr(uri)}'
                               for declared, uri in field.begin[_DECLARED]).encode('utf-8')
        self._edit(start, end, self.raw[start:end] + b'<' + tag + declarations + b' xml:space="preserve"> QUOTE </'
                   + tag + b'>')
        self._remove_between(field.begin, field.begin_chain, separate, separate_chain, marks=False)
        self.removed['fields'] += 1
        self.shells += 1

    def _shell_simple_field(self, element):
        """R2-30: a removed w:fldSimple in another field's result stays a field: every instr attribute of its start tag
        reads ' QUOTE ', its w:fldData goes (as release 1's unwrapping takes it), its runs stay."""
        start_end = self._tag_end(element[_AT])
        values = [(match.start(2), match.end(2)) for match in _ATTRIBUTE.finditer(
            self.raw, _TAG_NAME.match(self.raw, element[_AT]).end(), start_end)
            if match.group(1).rpartition(b':')[2] == b'instr']
        if not values:
            raise PackageRefused('a document part cannot be edited safely')
        for value_start, value_end in values:
            self._edit(value_start, value_end, b'" QUOTE "')
        for child in element[_CHILDREN]:
            if child[_NAME] in _FLDDATAS:
                self._remove(child)
        self.removed['fields'] += 1
        self.shells += 1

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


def _edited_part(raw, deadline, pictures=frozenset(), external=frozenset()):
    """(``raw`` with E2's removals made, their counts, the relationship ids only removed content named, the counts of
    what E2 would leave nothing of - LOST_KINDS -, the QUOTE shells made), or None when nothing is to be removed - the
    part then passes through byte for byte. When anything is lost, the file is refused (ContentNotShown), so the part is
    returned unedited. ``pictures`` and ``external``: _relationship_ids of the part.

    The part is read once. What the edit must not break is confirmed without reading it again in Python: the edits only
    take whole elements, or whole tags of one element, so expat - in C, with no handler - confirms it still parses
    (well-formed, every prefix bound); and an id some kept attribute still holds keeps its relationship, found by its
    bytes. The one way an edit can make a new instruction is a field removed inside another field's instruction: its
    result, kept, now stands in that instruction, and may complete the outer field's type ('LI' and a removed field's
    result 'NK'). Only then is the part read again, and edited again, until nothing more is removed. Each reading is
    given the offsets, moved by the edits, of the fields an earlier one found holding a removed field in their
    instruction, and the reading that removes nothing more inside an instruction - when every field's type is final -
    counts those whose result 7.4 would lose (R2-30's fallback)."""
    reader = _PartReader(raw, deadline, editable=_editable(raw), pictures=pictures, external=external).read()
    if any(reader.lost.values()):
        return raw, dict.fromkeys(_REMOVED_KINDS, 0), set(), dict(reader.lost), 0
    if not reader.edits:
        return None
    data, removed, gone, shells, lost = raw, dict.fromkeys(_REMOVED_KINDS, 0), set(), 0, dict.fromkeys(LOST_KINDS, 0)
    for _ in range(_REREADS):
        edits = _merged(reader.edits)
        gone |= _named_by(reader.references, edits)
        for kind in _REMOVED_KINDS:
            removed[kind] += reader.removed[kind]
        for kind in LOST_KINDS:
            lost[kind] += reader.lost[kind]
        shells += reader.shells
        data = _applied(data, edits)
        if not reader.nested_removal:
            break
        reader = _PartReader(data, deadline, pictures=pictures, external=external,
                             carried=_moved(reader.candidates, edits)).read()
        if not reader.edits:
            for kind in LOST_KINDS:
                lost[kind] += reader.lost[kind]
            break
    else:
        raise PackageRefused('a document part could not be edited safely')
    _well_formed(data)
    return data, removed, gone - _still_named(data, gone), lost, shells


def _moved(offsets, edits) -> frozenset:
    """``offsets`` of a part where they stand once ``edits`` (merged: in order, apart) are made; one an edit takes is
    gone."""
    moved = set()
    for offset in offsets:
        shift = 0
        for start, end, replacement in edits:
            if end <= offset:
                shift += len(replacement) - (end - start)
            elif start <= offset:
                break
            else:
                moved.add(offset + shift)
                break
        else:
            moved.add(offset + shift)
    return frozenset(moved)


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


def _remove_active_content(infos, parts, by_folded, kept_rows, dropped_rows, rewritten, special, orphans, deadline):
    """E2 over every part still sent (not a relationships part or the content types): a part whose bytes hold field or
    object markup is read and edited (``rewritten``), and every part that would bring a DTD to a parser is refused - an
    SVG picture's excepted. A part read as XML here is held to E1's size limits only, as every part is. The
    relationships only removed content named are dropped (``kept_rows`` and ``rewritten`` updated) and the parts only
    they named added to ``orphans``. Returns (the counts, {part: the refusal held until it is known whether the part is
    still sent}, {part: what E2 would leave nothing of in it}, {part: the QUOTE shells made in it})."""
    removed, held, dropped_ids, unshown, shells = dict.fromkeys(_REMOVED_KINDS, 0), {}, {}, {}, {}
    types = _content_types(parts[CONTENT_TYPES_PART])
    for info in infos:
        name = info.filename
        if name in orphans or name.casefold() in special:
            continue
        raw = parts[name]
        view = raw.replace(b'\x00', b'') if _wide(raw) else raw
        try:
            triggered = _TRIGGER.search(view) is not None
            if triggered:
                pictures, external = _relationship_ids(name, parts, by_folded, kept_rows, dropped_rows)
                outcome = _edited_part(raw, deadline, pictures, external)
                if outcome is not None:
                    edited, counts, ids, lost, made = outcome
                    if any(lost.values()):  # the file is refused: nothing of the part is edited
                        unshown[name] = lost
                    else:
                        rewritten[name] = edited
                        for kind in _REMOVED_KINDS:
                            removed[kind] += counts[kind]
                        if ids:
                            dropped_ids[name] = ids
                        if made:
                            shells[name] = made
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
    return removed, held, unshown, shells


def _relationship_ids(name, parts, by_folded, kept_rows, dropped_rows):
    """(the ids of the part ``name``'s kept relationships whose target is a part of the package that is not empty, by
    its name as written or percent-decoded; the ids of its relationships that reach outside - TargetMode other than
    Internal, dropped): what a preview picture must name (R2-29 step 1), and what makes a w:altChunk an inserted
    document (R2-28 step 2)."""
    folder, _, leaf = name.rpartition('/')
    rels = by_folded.get((f'{folder}/_rels/{leaf}.rels' if folder else f'_rels/{leaf}.rels').casefold())
    present = set()
    for row in kept_rows.get(rels, ()):
        target = _part_name(_source_folder(rels), row.get('Target', ''))
        for form in {target, unquote(target)} if target is not None else ():
            part = by_folded.get(form.casefold())
            if part is not None and parts[part]:
                present.add(row.get('Id'))
    return frozenset(present), frozenset(row.get('Id') for row in dropped_rows.get(rels, ()))


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
