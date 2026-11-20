"""CMS reference passages: the data files, their import and their loading (HARNESS.md 5).

A passage is verbatim CMS text: read from the publisher's PDF with pypdf, runs of whitespace collapsed to one space and
nothing else changed. ops/verify_passages.py (removed 2026-11-20 with the earlier PDF reader) proves it again from the PDFs (the file's sha256 first, then every passage
on its own page). One JSON data file per source, in studio/reference/data/:

    {"source": {key, kind, publisher, title, release, url, sha256, retrieved_at, effective_start, effective_end,
                license_note, scope_note},
     "passages": [{passage_key, section, page, topic, topic_value, text}],
     "excluded": [{topic, topic_value, section, page, anchor, reason}]}

``sha256`` is the file the passages were read from. ``page`` is that PDF's own page number, or "N-M" for a passage that
runs across a page break. Where the extracted text puts a page header or a field label inside a passage, the passage is
cut there, one passage per page; the parts share the topic value and their keys sort in reading order. "excluded" says
what the curation left out and why, each item located by an anchor (its first words, never a descriptor) that no
passage may contain.

No descriptor. A passage that quotes a CPT code description is never imported. The import refuses a data file in which
any text has a code followed by an opening parenthesis or by '--' (the two forms in which these CMS files print a
description after a code), so that a curation mistake cannot store one; a description in any other form is left out by
the curation and listed under "excluded".

Import (``import_data_file``; manage.py import_passages --data <file>): one transaction writes a PassageSource and its
ReferencePassage rows, each passage's sha256 that of its UTF-8 text. The same file again is a no-op that says so (its
retrieval time may differ, as for import_reference); anything else under a loaded key is refused, as is the same file
under another key, and a window that overlaps a loaded source of the same kind.

No retrieval (FIX-SPEC-2 section 8, 2026-11-20). The retrieval that read these passages for a code, with the dormant
endoscopy rule set that grouped codes into endoscopic families and picked NCCI rules by code ranges and code lists,
was deleted: the coding review reads the document itself, and no code-family or code-specific rule logic is kept.
The data files, their import and load_passages stay.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from studio.models import PassageSource, ReferencePassage

PFS_DOCUMENTATION = 'cms-pfs-documentation'
NCCI_MANUAL = 'cms-ncci-policy-manual'
CLAIMS_MANUAL = 'cms-claims-manual'
KIND_LABELS = {PFS_DOCUMENTATION: 'CMS PFS file documentation', NCCI_MANUAL: 'CMS NCCI Policy Manual',
               CLAIMS_MANUAL: 'CMS Claims Processing Manual'}
# Every topic a data file's passage may carry, with the kind of source that states it (the import checks it).
TOPICS = {'pfs.status': PFS_DOCUMENTATION, 'pfs.global_days': PFS_DOCUMENTATION, 'pfs.mult_proc': PFS_DOCUMENTATION,
          'pfs.endo_base': PFS_DOCUMENTATION, 'pfs.pctc': PFS_DOCUMENTATION, 'ncci.endoscopy': NCCI_MANUAL,
          'claims.multiple_endoscopy': CLAIMS_MANUAL}
FIELD_TOPICS = ('pfs.endo_base',)  # a field's own definition, not a value's: topic_value is ''

# --- data files ----------------------------------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent / 'data'
MAX_DATA_BYTES = 1024 * 1024
MAX_TEXT = 4000
SOURCE_FIELDS = ('key', 'kind', 'publisher', 'title', 'release', 'url', 'sha256', 'retrieved_at', 'effective_start',
                 'effective_end', 'license_note', 'scope_note')
PASSAGE_FIELDS = ('passage_key', 'section', 'page', 'topic', 'topic_value', 'text')
EXCLUDED_FIELDS = ('topic', 'topic_value', 'section', 'page', 'anchor', 'reason')
# The model's column widths.
LIMITS = {'publisher': 120, 'title': 200, 'release': 60, 'url': 400, 'section': 200}

SOURCE_KEY = re.compile(r'[a-z0-9][a-z0-9.-]{0,59}')
PASSAGE_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
PAGE = re.compile(r'([1-9][0-9]{0,3})(?:-([1-9][0-9]{0,3}))?')
TOPIC_VALUE = re.compile(r'[0-9A-Z]{1,20}')
SHA256 = re.compile(r'[0-9a-f]{64}')
# A code followed by an opening parenthesis or by '--': how these CMS files print a description after a code.
CODE_THEN_DESCRIPTION = re.compile(r'(?<![0-9A-Za-z])(?:[0-9]{4}[0-9A-Z]|[A-Z][0-9]{4})\s*(?:\(|--)')


class PassageImportError(Exception):
    """The data file or its metadata cannot be imported; nothing was written."""


@dataclass(frozen=True)
class DataFile:
    source: dict  # SOURCE_FIELDS; the window as dates, retrieved_at an aware datetime
    passages: tuple[dict, ...]  # PASSAGE_FIELDS plus 'sha256', of the text
    excluded: tuple[dict, ...]


def collapse(text: str) -> str:
    """Runs of whitespace as one space, the ends trimmed: the one change a passage's text carries."""
    return ' '.join(text.split())


def passage_sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def bundled_files() -> tuple[Path, ...]:
    """The data files this release ships, by name."""
    return tuple(sorted(DATA_DIR.glob('*.json')))


def _unique_keys(pairs):
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise PassageImportError(f'An object repeats a key ({sorted(k for k in set(keys) if keys.count(k) > 1)}).')
    return dict(pairs)


def _no_constant(name):
    raise PassageImportError(f'{name} is not JSON data.')


def read_data_file(path) -> DataFile:
    path = Path(path)
    if not path.is_file():
        raise PassageImportError(f'{path} is not a readable file.')
    with path.open('rb') as handle:
        raw = handle.read(MAX_DATA_BYTES + 1)
    if len(raw) > MAX_DATA_BYTES:
        raise PassageImportError(f'{path.name} is larger than {MAX_DATA_BYTES} bytes.')
    try:
        document = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_keys, parse_constant=_no_constant)
    except UnicodeDecodeError as exc:
        raise PassageImportError(f'{path.name} is not UTF-8: {exc}') from exc
    except ValueError as exc:
        raise PassageImportError(f'{path.name} is not valid JSON: {exc}') from exc
    return parse_data(document, path.name)


def _fields(value, names, where):
    if not isinstance(value, dict) or set(value) != set(names):
        found = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise PassageImportError(f'{where} must have exactly the fields {", ".join(names)}; found {found}.')
    for name in names:
        text = value[name]
        if not isinstance(text, str):
            raise PassageImportError(f'{where}: {name} must be a string.')
        if any(unicodedata.category(ch) in ('Cc', 'Cs') for ch in text):
            raise PassageImportError(f'{where}: {name} has a control character or a lone surrogate.')
        if CODE_THEN_DESCRIPTION.search(text):
            raise PassageImportError(f'{where}: {name} has a code followed by a parenthesis or "--", the form of a '
                                     'quoted code description; nothing is imported.')
        if name in LIMITS and len(text) > LIMITS[name]:
            raise PassageImportError(f'{where}: {name} is longer than {LIMITS[name]} characters.')


def _iso_date(value, where):
    try:
        day = date.fromisoformat(value)
    except ValueError as exc:
        raise PassageImportError(f'{where} {value!r} is not a YYYY-MM-DD date.') from exc
    if day.isoformat() != value:
        raise PassageImportError(f'{where} {value!r} is not a YYYY-MM-DD date.')
    return day


def _page(value, where):
    match = PAGE.fullmatch(value)
    if match is None or (match[2] is not None and int(match[2]) <= int(match[1])):
        raise PassageImportError(f'{where}: page {value!r} must be a page number or a range "N-M" with N < M.')


def _source(source, name) -> dict:
    where = f'{name} source'
    _fields(source, SOURCE_FIELDS, where)
    if not SOURCE_KEY.fullmatch(source['key']):
        raise PassageImportError(f'{where}: key {source["key"]!r} must be 1-60 lower-case letters, digits, dots or '
                                 'dashes.')
    if source['kind'] not in KIND_LABELS:
        raise PassageImportError(f'{where}: kind {source["kind"]!r} is not one of {", ".join(KIND_LABELS)}.')
    for field in ('publisher', 'title', 'release', 'license_note', 'scope_note'):
        if not source[field].strip():
            raise PassageImportError(f'{where}: {field} is empty.')
    url = source['url']
    if not url.startswith('https://') or any(ch.isspace() for ch in url):
        raise PassageImportError(f'{where}: the url must be an https:// URL without spaces.')
    if not SHA256.fullmatch(source['sha256']):
        raise PassageImportError(f'{where}: sha256 must be 64 lower-case hexadecimal characters.')
    try:
        retrieved_at = datetime.fromisoformat(source['retrieved_at'])
    except ValueError as exc:
        raise PassageImportError(f'{where}: retrieved_at is not an ISO-8601 date and time.') from exc
    if not timezone.is_aware(retrieved_at):
        raise PassageImportError(f'{where}: retrieved_at has no UTC offset.')
    start = _iso_date(source['effective_start'], f'{where}: effective_start')
    end = _iso_date(source['effective_end'], f'{where}: effective_end')
    if start > end:
        raise PassageImportError(f'{where}: the effective start is after the effective end.')
    return dict(source, retrieved_at=retrieved_at, effective_start=start, effective_end=end)


def _passage(passage, kind, where) -> dict:
    _fields(passage, PASSAGE_FIELDS, where)
    if not PASSAGE_KEY.fullmatch(passage['passage_key']):
        raise PassageImportError(f'{where}: passage_key must be 1-80 letters, digits, dots, dashes or underscores.')
    if not passage['section'].strip():
        raise PassageImportError(f'{where}: section is empty.')
    _page(passage['page'], where)
    topic, value = passage['topic'], passage['topic_value']
    if TOPICS.get(topic) != kind:
        raise PassageImportError(f'{where}: topic {topic!r} is not one a {kind} source states.')
    if (value != '') if topic in FIELD_TOPICS else not TOPIC_VALUE.fullmatch(value):
        raise PassageImportError(f'{where}: topic_value {value!r} does not fit topic {topic}.')
    text = passage['text']
    if not text or len(text) > MAX_TEXT:
        raise PassageImportError(f'{where}: the text must have 1 to {MAX_TEXT} characters.')
    if collapse(text) != text:
        raise PassageImportError(f'{where}: the text must have its runs of whitespace collapsed to one space.')
    return dict(passage, sha256=passage_sha256(text))


def parse_data(document, name='data') -> DataFile:
    """A data file's content checked against the schema above: anything else refuses the whole file."""
    if not isinstance(document, dict) or set(document) != {'source', 'passages', 'excluded'}:
        raise PassageImportError(f'{name} must have exactly the members source, passages and excluded.')
    source = _source(document['source'], name)
    if not isinstance(document['passages'], list) or not document['passages']:
        raise PassageImportError(f'{name}: passages must be a non-empty list.')
    passages, keys, texts = [], set(), set()
    for number, item in enumerate(document['passages'], start=1):
        passage = _passage(item, source['kind'], f'{name} passage {number}')
        if passage['passage_key'] in keys:
            raise PassageImportError(f'{name}: passage_key {passage["passage_key"]!r} appears twice.')
        if passage['text'] in texts:
            raise PassageImportError(f'{name}: passage {passage["passage_key"]!r} repeats another passage\'s text.')
        keys.add(passage['passage_key'])
        texts.add(passage['text'])
        passages.append(passage)
    if not isinstance(document['excluded'], list):
        raise PassageImportError(f'{name}: excluded must be a list.')
    for number, item in enumerate(document['excluded'], start=1):
        where = f'{name} excluded item {number}'
        _fields(item, EXCLUDED_FIELDS, where)
        _page(item['page'], where)
        if TOPICS.get(item['topic']) != source['kind'] or not all(item[f].strip() for f in ('anchor', 'reason')):
            raise PassageImportError(f'{where}: it needs a topic of this source, an anchor and a reason.')
        holding = [p['passage_key'] for p in passages if item['anchor'] in p['text']]
        if holding:
            raise PassageImportError(f'{where}: passage {holding[0]!r} holds the text it says is left out.')
    return DataFile(source=source, passages=tuple(passages), excluded=tuple(document['excluded']))


# --- import --------------------------------------------------------------------------------------------------------

COMPARED = ('kind', 'publisher', 'title', 'release', 'url', 'sha256', 'effective_start', 'effective_end',
            'license_note', 'scope_note')


def _stored_passages(source: PassageSource) -> list[tuple]:
    rows = source.passages.values_list(*PASSAGE_FIELDS, 'sha256')
    return sorted(tuple(row) for row in rows)  # sorted here, never by the database's collation


def _confirm_existing(existing: PassageSource, data: DataFile):
    declared = data.source
    if existing.sha256 != declared['sha256']:
        raise PassageImportError(f'{existing.key} is already loaded from a different file (sha256 {existing.sha256}); '
                                 f'refusing to replace it with {declared["sha256"]}.')
    differences = [name for name in COMPARED if getattr(existing, name) != declared[name]]
    given = sorted(tuple(p[f] for f in (*PASSAGE_FIELDS, 'sha256')) for p in data.passages)
    if _stored_passages(existing) != given or existing.passage_count != len(given):
        differences.append('passages')
    if differences:
        raise PassageImportError(f'{existing.key} is already loaded from this file with different '
                                 f'{", ".join(differences)}; a loaded source is never changed.')


def _refuse_conflicts(declared: dict):
    same_file = PassageSource.objects.filter(sha256=declared['sha256']).first()
    if same_file is not None:
        raise PassageImportError(f'This file (sha256 {declared["sha256"]}) is already loaded as {same_file.key}.')
    overlap = PassageSource.objects.filter(kind=declared['kind'], effective_start__lte=declared['effective_end'],
                                           effective_end__gte=declared['effective_start']).first()
    if overlap is not None:
        raise PassageImportError(
            f'{overlap.key} ({overlap.effective_start.isoformat()} to {overlap.effective_end.isoformat()}) already '
            f'covers part of {declared["effective_start"].isoformat()} to {declared["effective_end"].isoformat()}; '
            'two passage sources of one kind may not cover the same date.')


def import_data_file(path) -> tuple[PassageSource, bool]:
    """Load one data file in a single transaction: (its PassageSource, whether this call created it)."""
    data = read_data_file(path)
    declared = data.source
    with transaction.atomic():
        existing = PassageSource.objects.filter(key=declared['key']).first()
        if existing is not None:
            _confirm_existing(existing, data)
            return existing, False
        _refuse_conflicts(declared)
        source = PassageSource.objects.create(**{name: declared[name] for name in SOURCE_FIELDS},
                                              passage_count=len(data.passages))
        ReferencePassage.objects.bulk_create(
            [ReferencePassage(source=source, sha256=p['sha256'], **{f: p[f] for f in PASSAGE_FIELDS})
             for p in data.passages])
    return source, True


# --- loading ---------------------------------------------------------------------------------------------------------

def load_passages() -> list[dict]:
    """Every imported passage with its source's key, kind, title, release, window, file sha256 and url, sorted by
    (source key, passage key). A row whose text no longer matches its sha256 raises: it was changed after import."""
    loaded = []
    for row in ReferencePassage.objects.select_related('source'):
        source = row.source
        if passage_sha256(row.text) != row.sha256:
            raise ValueError(f'Passage {source.key}/{row.passage_key} does not match its sha256; it was changed '
                             'after import.')
        loaded.append({'source_key': source.key, 'kind': source.kind, 'source_title': source.title,
                       'release': source.release, 'effective_start': source.effective_start.isoformat(),
                       'effective_end': source.effective_end.isoformat(), 'source_sha256': source.sha256,
                       'url': source.url, 'passage_key': row.passage_key, 'section': row.section, 'page': row.page,
                       'topic': row.topic, 'topic_value': row.topic_value, 'text': row.text, 'sha256': row.sha256})
    return sorted(loaded, key=lambda p: (p['source_key'], p['passage_key']))

