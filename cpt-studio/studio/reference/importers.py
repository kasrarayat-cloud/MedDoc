"""Importers for public CMS reference files (ARCHITECTURE 5.5).

Only code-keyed facts are stored; descriptor text is never read into a row.
The archive is read once and its sha256 must equal the expected value before
it is opened, so the bytes that were verified are the bytes that are parsed.
Any row that does not match the expected layout refuses the whole import.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from django.db import transaction
from django.utils import timezone

from studio.models import ReferenceCodeFact, ReferenceSource
from studio.reference.store import MUE, PFS

PUBLISHER = 'Centers for Medicare & Medicaid Services (CMS)'
# A statement of fact, never a claim of permission (owner, 2026-11-01; HARNESS.md 11.6): no AMA licence is held, and
# whether CPT Studio's use of CPT content needs one is the owner's open decision (D4), not something this note settles.
LICENSE_NOTE = ('CPT codes are copyright the American Medical Association; descriptors are not imported or displayed. '
                'CPT Studio holds no AMA licence; whether its use of CPT content needs one is an open owner decision.')
SCOPE_NOTES = {
    PFS: 'Medicare Physician Fee Schedule indicators (not a CPT edition; not payer-specific)',
    MUE: 'Medicare NCCI practitioner MUE values (units per day; not every payer)',
}
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
HEADER_SEARCH_ROWS = 40
MONTHS = ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC')

CODE = re.compile(r'[0-9A-Z]{5}')
MODIFIER = re.compile(r'(?:[0-9A-Z]{2})?')
SHA256 = re.compile(r'[0-9a-f]{64}')
RELEASE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,38}')

PFS_MEMBER = re.compile(r'PPRRVU(?P<year>[0-9]{4})_(?P<month>[A-Za-z]{3})_nonQPP\.csv', re.IGNORECASE)
# fact name -> (column header: the last two header rows joined, pattern for the cell)
PFS_COLUMNS = {
    'status': ('STATUS CODE', re.compile(r'[A-Z]')),
    'global_days': ('GLOB DAYS', re.compile(r'[0-9]{3}|[A-Z]{3}')),
    'mult_proc': ('MULT PROC', re.compile(r'[0-9]')),
    'endo_base': ('ENDO BASE', re.compile(r'(?:[0-9A-Z]{5})?')),
    'pctc': ('PCTC IND', re.compile(r'[0-9]')),
}

MUE_MEMBER = re.compile(
    r'MCR_MUE_PractitionerServices_Eff_(?P<month>[0-9]{2})-(?P<day>[0-9]{2})-(?P<year>[0-9]{4})\.csv', re.IGNORECASE)
# column -> header with all whitespace removed, upper-cased ('HCPCS/\nCPT Code' -> 'HCPCS/CPTCODE')
MUE_COLUMNS = {'code': 'HCPCS/CPTCODE', 'value': 'PRACTITIONERSERVICESMUEVALUES',
               'mai': 'MUEADJUDICATIONINDICATOR', 'rationale': 'MUERATIONALE'}
MAI = re.compile(r'([1-3])\s+(\S.*)', re.DOTALL)
UNITS = re.compile(r'[0-9]{1,6}')


class ReferenceImportError(Exception):
    """The file or its declared metadata cannot be imported; nothing was written."""


@dataclass(frozen=True)
class ParsedTable:
    member: str
    rows: tuple[tuple[str, str, dict], ...]  # (code, modifier, facts)


@dataclass(frozen=True)
class Declared:
    kind: str
    key: str
    sha256: str
    release: str
    url: str
    effective_start: date
    effective_end: date
    retrieved_at: datetime


def source_key(kind: str, release: str) -> str:
    """'cms-pfs' + 'RVU26D' -> 'cms-pfs-rvu26d'; '2026-Q4' -> '...-2026q4'."""
    if not isinstance(release, str) or not RELEASE.fullmatch(release):
        raise ReferenceImportError(f'Release {release!r} must be 1-39 letters, digits, dots, dashes or underscores.')
    return f'{kind}-{re.sub(r"[^a-z0-9]", "", release.lower())}'


# --- shared reading ---------------------------------------------------------------

def _read_verified(zip_path, expected_sha256: str) -> bytes:
    path = Path(zip_path)
    if not path.is_file():
        raise ReferenceImportError(f'{path} is not a readable file.')
    with path.open('rb') as handle:
        data = handle.read(MAX_ARCHIVE_BYTES + 1)
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ReferenceImportError(f'{path.name} is larger than {MAX_ARCHIVE_BYTES} bytes.')
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise ReferenceImportError(f'{path.name} has sha256 {actual}, not the expected {expected_sha256}; refused.')
    return data


def _member_text(data: bytes, pattern: re.Pattern, description: str) -> tuple[str, str]:
    """(member name, decoded text) of the one member matching ``pattern``."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ReferenceImportError(f'Not a valid zip archive: {exc}') from exc
    with archive:
        names = [info for info in archive.infolist() if pattern.fullmatch(info.filename)]
        if len(names) != 1:
            found = ', '.join(info.filename for info in names) or 'none'
            raise ReferenceImportError(f'Expected exactly one {description} in the archive; found {found}.')
        info = names[0]
        if info.file_size > MAX_MEMBER_BYTES:
            raise ReferenceImportError(f'{info.filename} is larger than {MAX_MEMBER_BYTES} bytes.')
        try:
            with archive.open(info) as handle:
                raw = handle.read(MAX_MEMBER_BYTES + 1)
        except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
            raise ReferenceImportError(f'{info.filename} could not be read: {exc}') from exc
    if len(raw) > MAX_MEMBER_BYTES:
        raise ReferenceImportError(f'{info.filename} is larger than {MAX_MEMBER_BYTES} bytes.')
    # CMS publishes these tables as ISO-8859-1.
    return info.filename, raw.removeprefix(b'\xef\xbb\xbf').decode('iso-8859-1')


def _rows(text: str, member: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(text, newline=''), strict=True))
    except csv.Error as exc:
        raise ReferenceImportError(f'{member} is not valid CSV: {exc}') from exc


def _squeeze(cell: str) -> str:
    return ' '.join(cell.split()).upper()


def _column_index(names: list[str], wanted: str, member: str) -> int:
    hits = [index for index, name in enumerate(names) if name == wanted]
    if len(hits) != 1:
        raise ReferenceImportError(f'{member}: expected one column {wanted!r}, found {len(hits)}.')
    return hits[0]


def _cell(row: list[str], index: int) -> str:
    return row[index].strip()


def _refuse_row(member: str, number: int, problem: str):
    raise ReferenceImportError(f'{member} row {number}: {problem}; nothing was imported.')


# --- CMS PFS relative value file (PPRRVU, non-QPP) ------------------------------------

def parse_pfs(data: bytes, effective_start: date) -> ParsedTable:
    member, text = _member_text(data, PFS_MEMBER, 'PPRRVU<year>_<Mon>_nonQPP.csv table')
    match = PFS_MEMBER.fullmatch(member)
    month = match['month'].upper()
    if (int(match['year']), MONTHS.index(month) + 1 if month in MONTHS else 0) != (effective_start.year,
                                                                                    effective_start.month):
        raise ReferenceImportError(f'{member} is the {match["month"]} {match["year"]} release; the declared effective '
                                   f'start {effective_start.isoformat()} is not in that month.')
    rows = _rows(text, member)
    header = next((i for i, row in enumerate(rows[:HEADER_SEARCH_ROWS])
                   if len(row) > 1 and _squeeze(row[0]) == 'HCPCS' and _squeeze(row[1]) == 'MOD'), None)
    if not header:
        raise ReferenceImportError(f'{member}: no two-row header block ending in HCPCS / MOD was found in the first '
                                   f'{HEADER_SEARCH_ROWS} rows.')
    above = rows[header - 1] + [''] * (len(rows[header]) - len(rows[header - 1]))
    names = [_squeeze(f'{upper} {lower}') for upper, lower in zip(above, rows[header])]
    columns = {fact: _column_index(names, name, member) for fact, (name, _) in PFS_COLUMNS.items()}
    width = len(rows[header])
    parsed, seen = [], set()
    for number, row in enumerate(rows[header + 1:], start=header + 2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != width:
            _refuse_row(member, number, f'{len(row)} cells where the header has {width}')
        code, modifier = _cell(row, 0), _cell(row, 1)
        if not CODE.fullmatch(code):
            _refuse_row(member, number, f'code {code!r} is not five letters or digits')
        if not MODIFIER.fullmatch(modifier):
            _refuse_row(member, number, f'modifier {modifier!r} is not two letters or digits')
        if (code, modifier) in seen:
            _refuse_row(member, number, f'{code} {modifier or "(no modifier)"} appears twice')
        seen.add((code, modifier))
        facts = {}
        for fact, (name, pattern) in PFS_COLUMNS.items():
            value = _cell(row, columns[fact])
            if not pattern.fullmatch(value):
                _refuse_row(member, number, f'{name} value {value!r} is not in the expected format')
            facts[fact] = value or None
        parsed.append((code, modifier, facts))
    if not parsed:
        raise ReferenceImportError(f'{member} has no data rows.')
    return ParsedTable(member=member, rows=tuple(parsed))


# --- CMS NCCI practitioner services MUE table -----------------------------------------

def parse_mue(data: bytes, effective_start: date) -> ParsedTable:
    member, text = _member_text(data, MUE_MEMBER, 'MCR_MUE_PractitionerServices_Eff_<MM-DD-YYYY>.csv table')
    match = MUE_MEMBER.fullmatch(member)
    try:
        stated = date(int(match['year']), int(match['month']), int(match['day']))
    except ValueError as exc:
        raise ReferenceImportError(f'{member} does not name a valid effective date.') from exc
    if stated != effective_start:
        raise ReferenceImportError(f'{member} is effective {stated.isoformat()}; the declared effective start is '
                                   f'{effective_start.isoformat()}.')
    rows = _rows(text, member)
    wanted = set(MUE_COLUMNS.values())
    header = next((i for i, row in enumerate(rows[:HEADER_SEARCH_ROWS])
                   if wanted <= {''.join(cell.split()).upper() for cell in row}), None)
    if header is None:
        raise ReferenceImportError(f'{member}: the MUE header row was not found in the first '
                                   f'{HEADER_SEARCH_ROWS} rows.')
    names = [''.join(cell.split()).upper() for cell in rows[header]]
    columns = {field: _column_index(names, name, member) for field, name in MUE_COLUMNS.items()}
    width = len(rows[header])
    parsed, seen, labels = [], set(), {}
    for number, row in enumerate(rows[header + 1:], start=header + 2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != width:
            _refuse_row(member, number, f'{len(row)} cells where the header has {width}')
        code = _cell(row, columns['code'])
        if not CODE.fullmatch(code):
            _refuse_row(member, number, f'code {code!r} is not five letters or digits')
        if code in seen:
            _refuse_row(member, number, f'{code} appears twice')
        seen.add(code)
        value = _cell(row, columns['value'])
        if not UNITS.fullmatch(value):
            _refuse_row(member, number, f'MUE value {value!r} is not a whole number of units')
        indicator = MAI.fullmatch(_cell(row, columns['mai']))
        if indicator is None:
            _refuse_row(member, number,
                        f'adjudication indicator {_cell(row, columns["mai"])!r} is not "<1|2|3> <label>"')
        digit, label = int(indicator[1]), ' '.join(indicator[2].split())
        if labels.setdefault(digit, label) != label:
            _refuse_row(member, number, f'indicator {digit} is labelled {label!r} here and {labels[digit]!r} earlier')
        facts = {'value': int(value), 'mai': {'indicator': digit, 'label': label},
                 'rationale': ' '.join(_cell(row, columns['rationale']).split())}
        parsed.append((code, '', facts))
    if not parsed:
        raise ReferenceImportError(f'{member} has no data rows.')
    return ParsedTable(member=member, rows=tuple(parsed))


# --- import -----------------------------------------------------------------------

def _declare(kind, expected_sha256, release, url, effective_start, effective_end, retrieved_at) -> Declared:
    sha = expected_sha256.strip().lower() if isinstance(expected_sha256, str) else ''
    if not SHA256.fullmatch(sha):
        raise ReferenceImportError('The expected sha256 must be 64 hexadecimal characters.')
    if not (isinstance(url, str) and url.startswith('https://') and len(url) <= 400
            and not any(c.isspace() for c in url)):
        raise ReferenceImportError('The source URL must be an https:// URL of at most 400 characters.')
    for name, value in (('effective start', effective_start), ('effective end', effective_end)):
        if not isinstance(value, date) or isinstance(value, datetime):
            raise ReferenceImportError(f'The {name} must be a date.')
    if effective_start > effective_end:
        raise ReferenceImportError('The effective start is after the effective end.')
    if not isinstance(retrieved_at, datetime) or not timezone.is_aware(retrieved_at):
        raise ReferenceImportError('The retrieval time must be a timezone-aware datetime.')
    return Declared(kind=kind, key=source_key(kind, release), sha256=sha, release=release, url=url,
                    effective_start=effective_start, effective_end=effective_end, retrieved_at=retrieved_at)


def _confirm_existing(existing: ReferenceSource, declared: Declared) -> ReferenceSource:
    if existing.sha256 != declared.sha256:
        raise ReferenceImportError(f'{existing.key} is already loaded from a different file '
                                   f'(sha256 {existing.sha256}); refusing to replace it with {declared.sha256}.')
    differences = [f'{name} {getattr(existing, name)} (installed) vs {getattr(declared, name)} (declared)'
                   for name in ('kind', 'release', 'url', 'effective_start', 'effective_end')
                   if getattr(existing, name) != getattr(declared, name)]
    if differences:
        raise ReferenceImportError(f'{existing.key} is already loaded from this file with different metadata: '
                                   + '; '.join(differences) + '.')
    return existing


def _refuse_conflicts(declared: Declared):
    same_file = ReferenceSource.objects.filter(sha256=declared.sha256).first()
    if same_file is not None:
        raise ReferenceImportError(f'This file (sha256 {declared.sha256}) is already loaded as {same_file.key}.')
    overlap = ReferenceSource.objects.filter(kind=declared.kind, effective_start__lte=declared.effective_end,
                                             effective_end__gte=declared.effective_start).first()
    if overlap is not None:
        raise ReferenceImportError(
            f'{overlap.key} ({overlap.effective_start.isoformat()} to {overlap.effective_end.isoformat()}) already '
            f'covers part of {declared.effective_start.isoformat()} to {declared.effective_end.isoformat()}; two '
            'sources of one kind may not cover the same date.')


def _import(declared: Declared, zip_path, parse: Callable[[bytes, date], ParsedTable], title: str) -> ReferenceSource:
    data = _read_verified(zip_path, declared.sha256)
    with transaction.atomic():
        existing = ReferenceSource.objects.filter(key=declared.key).first()
        if existing is not None:
            return _confirm_existing(existing, declared)
        _refuse_conflicts(declared)
        table = parse(data, declared.effective_start)
        source = ReferenceSource.objects.create(
            key=declared.key, kind=declared.kind, publisher=PUBLISHER, title=f'{title} ({table.member})',
            release=declared.release, url=declared.url, sha256=declared.sha256, retrieved_at=declared.retrieved_at,
            effective_start=declared.effective_start, effective_end=declared.effective_end,
            license_note=LICENSE_NOTE, scope_note=SCOPE_NOTES[declared.kind], row_count=len(table.rows))
        ReferenceCodeFact.objects.bulk_create(
            [ReferenceCodeFact(source=source, code=code, modifier=modifier, facts=facts)
             for code, modifier, facts in table.rows], batch_size=5000)
    return source


def import_cms_pfs(zip_path, *, expected_sha256, release, url, effective_start, effective_end,
                   retrieved_at) -> ReferenceSource:
    """Load a CMS PFS relative value file (RVUyyX zip, PPRRVU non-QPP table): status, global days,
    multiple procedure, endoscopic base and PC/TC indicators per (code, modifier)."""
    declared = _declare(PFS, expected_sha256, release, url, effective_start, effective_end, retrieved_at)
    return _import(declared, zip_path, parse_pfs, 'Medicare Physician Fee Schedule relative value file')


def import_cms_mue_practitioner(zip_path, *, expected_sha256, release, url, effective_start, effective_end,
                                retrieved_at) -> ReferenceSource:
    """Load a CMS NCCI practitioner services MUE table: MUE value, adjudication indicator and rationale per code."""
    declared = _declare(MUE, expected_sha256, release, url, effective_start, effective_end, retrieved_at)
    return _import(declared, zip_path, parse_mue, 'Medicare NCCI practitioner services MUE table')


IMPORTERS = {PFS: import_cms_pfs, MUE: import_cms_mue_practitioner}
