"""CMS reference passages: the data files, their import and their retrieval (HARNESS.md 5).

A passage is verbatim CMS text: read from the publisher's PDF with pypdf, runs of whitespace collapsed to one space and
nothing else changed. ops/verify_passages.py proves it again from the PDFs (the file's sha256 first, then every passage
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

Retrieval (``retrieve``) is pure and deterministic. For each code (sorted, unique) it records every lookup it makes, the
PFS and MUE facts ``lookup`` returns (each with its source's key, release, window and sha256), and the passages these
rules select, only from a passage source whose window covers the service date (one source per kind, as for the facts;
with no service date no dated passage applies, and a note says so):

- the definition of each of the code's own PFS values (pfs.status, pfs.global_days, pfs.mult_proc, pfs.pctc), from the
  PFS documentation of the release its facts came from, and the endoscopic base code field's definition (pfs.endo_base)
  when the code names a base;
- the endoscopy rules below. An endoscopy is a code with multiple procedure indicator 3; its family is the endoscopic
  base it names, and a base that is itself proposed belongs to its family:

  | passage                          | selected when                                                       | for       |
  |----------------------------------|---------------------------------------------------------------------|-----------|
  | ncci.endoscopy 1                 | a proposed code is the endoscopic base another proposed code names  | both      |
  |   (surgical includes diagnostic) |                                                                     |           |
  | ncci.endoscopy 2                 | two or more proposed codes name one endoscopic base                 | each      |
  |   (the most comprehensive code)  |                                                                     |           |
  | claims.multiple_endoscopy 13     | one family has two or more proposed codes                           | each      |
  | claims.multiple_endoscopy 14     | a family and a proposed code outside it whose multiple procedure    | all of    |
  |   (unrelated endoscopies or      |   indicator is 1, 2 or 3                                            |   them    |
  |   other surgery)                 |                                                                     |           |
  | ncci.endoscopy 4                 | a code in rule 4's ranges (43753-43757, 91010-91299) and an         | that code |
  |                                  |   endoscopy                                                         |           |
  | ncci.endoscopy 7                 | one of rule 7's codes (43450, 43453) and an endoscopy               | that code |
  | ncci.endoscopy 16                | rule 16's code (76000) and an endoscopy                             | that code |

  The other stored rules are not selected in harness@1: they turn on what codes and indicators cannot show (rule 3 on
  units, rule 12 on which family's anatomy contains another's, the rest on the procedure's circumstances).

``notes`` say what was not retrieved and why. Passages, rules and notes only inform the reviewer: nothing here decides a
status (I2).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Mapping, Optional

from django.db import transaction
from django.utils import timezone

from studio.models import PassageSource, ReferencePassage
from studio.reference.store import MUE, PFS, applied_sources, source_applies
from studio.types import CodeReference, ReferenceLookup, ReferenceSourceInfo

PFS_DOCUMENTATION = 'cms-pfs-documentation'
NCCI_MANUAL = 'cms-ncci-policy-manual'
CLAIMS_MANUAL = 'cms-claims-manual'
KIND_LABELS = {PFS_DOCUMENTATION: 'CMS PFS file documentation', NCCI_MANUAL: 'CMS NCCI Policy Manual',
               CLAIMS_MANUAL: 'CMS Claims Processing Manual'}
# Every topic a passage is retrieved by, in the order a retrieval lists them, with the kind of source that states it.
TOPICS = {'pfs.status': PFS_DOCUMENTATION, 'pfs.global_days': PFS_DOCUMENTATION, 'pfs.mult_proc': PFS_DOCUMENTATION,
          'pfs.endo_base': PFS_DOCUMENTATION, 'pfs.pctc': PFS_DOCUMENTATION, 'ncci.endoscopy': NCCI_MANUAL,
          'claims.multiple_endoscopy': CLAIMS_MANUAL}
TOPIC_ORDER = {topic: index for index, topic in enumerate(TOPICS)}
FIELD_TOPICS = ('pfs.endo_base',)  # a field's own definition, not a value's: topic_value is ''

PFS_FIELDS = ('status', 'global_days', 'mult_proc', 'endo_base', 'pctc')
MUE_FIELDS = ('value', 'mai', 'rationale')
FACT_LABELS = {'pfs.status': 'PFS status code', 'pfs.global_days': 'PFS global surgery days',
               'pfs.mult_proc': 'PFS multiple procedure indicator', 'pfs.endo_base': 'PFS endoscopic base code',
               'pfs.pctc': 'PFS PC/TC indicator', 'mue.value': 'MUE value', 'mue.mai': 'MUE adjudication indicator',
               'mue.rationale': 'MUE rationale'}

ENDOSCOPY = '3'  # multiple procedure indicator 3: the special rules for multiple endoscopic procedures
MULTIPLE_SURGERY = ('1', '2', '3')  # the indicators under which a code is ranked with other procedures
RULE_4_RANGES = ((43753, 43757), (91010, 91299))  # NCCI Ch. VI C.4's own ranges
RULE_7_CODES = ('43450', '43453')  # NCCI Ch. VI C.7's own codes
RULE_16_CODES = ('76000',)  # NCCI Ch. VI C.16's own code

NO_DATE_NOTE = 'Service date unknown; no dated passage applies.'
# What HARNESS.md 5 names as not connected, worded as the encounter API reports it.
NOT_CONNECTED = ('NCCI procedure-to-procedure edits (AMA licence agreement not accepted)',
                 'AMA CPT descriptors and guidelines (no licence)', 'Payer policies')

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


# --- loading and retrieval -----------------------------------------------------------------------------------------

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


def _codes(codes) -> list[str]:
    if isinstance(codes, str):
        raise TypeError('codes must be an iterable of codes, not one string.')
    found = set()
    for code in codes:
        if not isinstance(code, str) or not code:
            raise ValueError(f'{code!r} is not a code.')
        found.add(code)
    return sorted(found)


def _index(passages) -> tuple[dict, tuple[ReferenceSourceInfo, ...]]:
    """(source key, topic, topic value) -> its passages by key; and each passage source, as the window rule reads it."""
    index, sources = defaultdict(list), {}
    for passage in passages:
        key = passage['source_key']
        info = ReferenceSourceInfo(
            key=key, kind=passage['kind'], publisher='', title=passage.get('source_title', ''),
            release=passage['release'], url=passage.get('url', ''), sha256=passage.get('source_sha256', ''),
            effective_start=passage['effective_start'], effective_end=passage['effective_end'], license_note='',
            scope_note='')
        if sources.setdefault(key, info) != info:
            raise ValueError(f'The passages of {key} disagree about their source.')
        if passage_sha256(passage['text']) != passage['sha256']:
            raise ValueError(f'Passage {key}/{passage["passage_key"]} does not match its sha256.')
        index[(key, passage['topic'], passage['topic_value'])].append(passage)
    for found in index.values():
        found.sort(key=lambda p: p['passage_key'])
    return index, tuple(sources[key] for key in sorted(sources))


def _unapplied(kind, sources, service_date) -> str:
    covering = [s.key for s in sources if s.kind == kind and source_applies(s, service_date)]
    if covering:
        return (f'{len(covering)} {KIND_LABELS[kind]} passage sources cover {service_date.isoformat()} '
                f'({", ".join(covering)}); none was used because the applicable one is ambiguous.')
    return f'No {KIND_LABELS[kind]} passage source covers {service_date.isoformat()}.'


def _facts(reference: CodeReference, fact_sources: Mapping[str, ReferenceSourceInfo]) -> list[dict]:
    facts = []
    for kind, prefix, fields, found in ((PFS, 'pfs', PFS_FIELDS, reference.pfs),
                                        (MUE, 'mue', MUE_FIELDS, reference.mue)):
        if not found:
            continue
        source = fact_sources.get(found.get('source_key'))
        if source is None:
            raise ValueError(f'{reference.code}: the lookup names source {found.get("source_key")!r}, which it '
                             'does not list.')
        for field in fields:
            if field in found:
                facts.append({'source_key': source.key, 'release': source.release,
                              'effective': [source.effective_start, source.effective_end], 'sha256': source.sha256,
                              'field': f'{prefix}.{field}', 'value': found[field], 'kind': kind,
                              'label': FACT_LABELS[f'{prefix}.{field}']})
    return facts


def _endoscopy_rules(references: Mapping[str, CodeReference]) -> dict[str, dict[tuple[str, str], list[str]]]:
    """code -> {(topic, topic value): why} for the endoscopy rules in the module docstring's table."""
    codes = set(references)
    pfs = {code: ref.pfs for code, ref in references.items() if ref.pfs}
    indicator = {code: facts.get('mult_proc') for code, facts in pfs.items()}
    base = {code: facts.get('endo_base') or '' for code, facts in pfs.items()}
    endoscopies = sorted(code for code in pfs if indicator[code] == ENDOSCOPY)
    rules = defaultdict(lambda: defaultdict(set))

    def add(code, topic, value, reason):
        rules[code][(topic, value)].add(reason)

    named = defaultdict(list)  # endoscopic base -> the proposed codes that name it (rules 1 and 2)
    for code in sorted(pfs):
        if base[code] and base[code] != code:
            named[base[code]].append(code)
    for root, members in sorted(named.items()):
        if root in codes:
            for member in members:
                for code in (member, root):
                    add(code, 'ncci.endoscopy', '1', f'{root} is the endoscopic base of {member}')
        if len(members) >= 2:
            for member in members:
                add(member, 'ncci.endoscopy', '2', f'{", ".join(members)} name the endoscopic base {root}')

    families = defaultdict(set)  # base -> its proposed codes: the endoscopies naming it, and itself when proposed
    for code in endoscopies:
        families[base[code] or code].add(code)
    for root, members in families.items():
        if root in codes:
            members.add(root)
    partners = defaultdict(set)  # code -> the proposed codes it is ranked with outside its family (item 14)
    for root, members in sorted(families.items()):
        if len(members) >= 2:
            family = ', '.join(sorted(members))
            for member in members:
                add(member, 'claims.multiple_endoscopy', '13', f'{family} are one endoscopic family (base {root})')
        for other in sorted(pfs):
            if other not in members and indicator[other] in MULTIPLE_SURGERY:
                for member in members:
                    partners[member].add(other)
                    partners[other].add(member)
    for code, others in partners.items():
        add(code, 'claims.multiple_endoscopy', '14', f'{code} is not of one endoscopic family with '
                                                     f'{", ".join(sorted(others))}')

    for code in sorted(codes):
        others = ', '.join(e for e in endoscopies if e != code)
        if not others:
            continue
        with_endoscopy = f'with {others}, of multiple procedure indicator 3'
        if code.isdigit() and any(low <= int(code) <= high for low, high in RULE_4_RANGES):
            add(code, 'ncci.endoscopy', '4', f'{code} is in rule 4\'s ranges, {with_endoscopy}')
        if code in RULE_7_CODES:
            add(code, 'ncci.endoscopy', '7', f'{code} is one of rule 7\'s codes, {with_endoscopy}')
        if code in RULE_16_CODES:
            add(code, 'ncci.endoscopy', '16', f'{code} is rule 16\'s code, {with_endoscopy}')
    return {code: {key: sorted(reasons) for key, reasons in found.items()} for code, found in rules.items()}


def _pfs_queries(code, reference: CodeReference, when: str, notes: list) -> list[tuple[str, str, str]]:
    if not reference.pfs:
        notes.append(f'{code} has no PFS facts for {when}; no PFS definition was retrieved for it.')
        return []
    queries = []
    for field in PFS_FIELDS:
        value = reference.pfs.get(field)
        if not value:
            continue
        if f'pfs.{field}' in FIELD_TOPICS:
            queries.append((f'pfs.{field}', '', f'{code} names the endoscopic base {value}'))
        else:
            queries.append((f'pfs.{field}', value, ''))
    return queries


def _shown(passage) -> dict:
    return {name: passage[name] for name in ('source_key', 'release', 'passage_key', 'section', 'page', 'topic',
                                             'topic_value', 'sha256', 'text')}


def retrieve(codes: Iterable[str], service_date: Optional[date], lookup: ReferenceLookup,
             passages: Iterable[Mapping]) -> list[dict]:
    """One retrieval trace per code (sorted, unique): {code, service_date, facts, passages, lookups, notes}. Pure: the
    lookup and the passages (load_passages' dicts) are its only inputs, and the same inputs give the same list."""
    wanted = _codes(codes)
    if service_date is not None and (not isinstance(service_date, date) or isinstance(service_date, datetime)):
        raise TypeError('service_date must be a date or None.')
    index, passage_sources = _index(passages)
    applied = applied_sources(passage_sources, service_date)  # kind -> the one passage source covering the date
    fact_sources = {source.key: source for source in lookup.sources()}
    references = {code: lookup.lookup(code, service_date) for code in wanted}
    rules = _endoscopy_rules(references)
    when = service_date.isoformat() if service_date else 'an unknown date'
    entries = []
    for code in wanted:
        reference = references[code]
        facts = _facts(reference, fact_sources)
        lookups = [f'reference lookup {code} on {when}: ' + (', '.join(reference.applicable_sources)
                                                             or 'no source applied')]
        notes = list(reference.notes)
        selected = {}
        if service_date is None:
            notes.append(NO_DATE_NOTE)
        else:
            queries = _pfs_queries(code, reference, when, notes)
            triggered = rules.get(code, {})
            queries += [(topic, value, '; '.join(triggered[(topic, value)]))
                        for topic, value in sorted(triggered, key=lambda k: (TOPIC_ORDER[k[0]], len(k[1]), k[1]))]
            fact_release = fact_sources[reference.pfs['source_key']].release if reference.pfs else None
            noted = set()
            for topic, value, reason in queries:
                kind = TOPICS[topic]
                source, why = applied.get(kind), None
                if source is None:
                    why = _unapplied(kind, passage_sources, service_date)
                elif kind == PFS_DOCUMENTATION and source.release != fact_release:
                    why = (f'The {KIND_LABELS[kind]} covering {when} ({source.key}) is release {source.release}, not '
                           f'{fact_release} of the facts; its definitions were not used.')
                if why is not None:
                    if kind not in noted:
                        notes.append(why)
                        noted.add(kind)
                    continue
                found = index.get((source.key, topic, value), [])
                shown = f'{topic}={value}' if value else topic
                lookups.append(f'passages {shown} in {source.key}' + (f' ({reason})' if reason else '')
                               + f': {len(found)}')
                if not found:
                    notes.append(f'{source.key} has no passage for {shown}.')
                for passage in found:
                    selected.setdefault((TOPIC_ORDER[topic], source.key, passage['passage_key']), passage)
        entries.append({'code': code, 'service_date': service_date.isoformat() if service_date else None,
                        'facts': facts, 'passages': [_shown(selected[key]) for key in sorted(selected)],
                        'lookups': lookups, 'notes': notes})
    return entries
