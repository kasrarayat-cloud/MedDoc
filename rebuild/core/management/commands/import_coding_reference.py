"""Attach reviewed official Index/Tabular evidence to an existing CodeSet.

No downloads, code-set changes, clinical changes, or overwrite path. The caller
must independently acquire/review the official artifacts and pin the manifest.
"""
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit
from uuid import UUID
import zipfile

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.coding_terminology import MAX_XML_BYTES, parse_reference, reference_digest
from core.management.commands.import_terminology import OFFICIAL_HOSTS, parse_icd


MANIFEST_FORMAT = 'icd10cm-official-reference-manifest-v1'
FILE_KEYS = {'codes', 'index', 'tabular', 'guidelines'}


def read_pinned_file(path, expected_hash, maximum):
    """Bounded stable fd read, refusing symlinks and non-regular files."""
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise CommandError('Reference paths must be absolute.')
    if not isinstance(expected_hash, str) or not re.fullmatch('[a-f0-9]{64}', expected_hash):
        raise CommandError('Reference SHA-256 must be 64 lowercase hexadecimal characters.')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum:
                raise CommandError('Reference must be a nonempty bounded regular file.')
            chunks = []
            count = 0
            while True:
                chunk = os.read(fd, min(1024 * 1024, maximum + 1 - count))
                if not chunk:
                    break
                chunks.append(chunk); count += len(chunk)
                if count > maximum:
                    raise CommandError('Reference exceeds its size limit.')
            after = os.fstat(fd)
            current = os.stat(path, follow_symlinks=False)
        finally:
            os.close(fd)
    except OSError as exc:
        raise CommandError('Cannot read pinned regular reference file.') from exc
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if identity(before) != identity(after) or identity(after) != identity(current):
        raise CommandError('Reference changed while being read.')
    raw = b''.join(chunks)
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise CommandError('Reference checksum mismatch; nothing was imported.')
    return raw


def official_url(value):
    if not isinstance(value, str) or len(value) > 1000 or any(ord(c) < 33 for c in value):
        raise CommandError('Invalid official reference URL.')
    try:
        u = urlsplit(value)
        valid = (u.scheme == 'https' and u.hostname in OFFICIAL_HOSTS and not u.username
                 and not u.password and not u.query and not u.fragment
                 and u.port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        raise CommandError('Reference provenance must be a stable official CMS/NCHS HTTPS URL.')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key.')
        result[key] = value
    return result


def prepare_reference(manifest_path, manifest_sha256):
    """Pure file preparation; no DB access. It does not authorize an import."""
    raw = read_pinned_file(manifest_path, manifest_sha256, 1024 * 1024)
    try:
        m = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON.')))
    except (ValueError, UnicodeError) as exc:
        raise CommandError('Malformed reference manifest.') from exc
    required = {'format', 'release', 'files', 'expected_code_count',
                'expected_index_entry_count', 'expected_tabular_diagnosis_count'}
    if not isinstance(m, dict) or set(m) != required or m['format'] != MANIFEST_FORMAT:
        raise CommandError('Use the closed official-reference manifest format.')
    metadata = m['release']
    if (not isinstance(metadata, dict) or set(metadata) != {
            'id', 'system', 'version', 'effective_from', 'effective_until', 'sha256', 'source_url'}
            or metadata['system'] != 'ICD-10-CM'):
        raise CommandError('Reference must bind one existing ICD-10-CM CodeSet exactly.')
    try:
        if str(UUID(metadata['id'])) != metadata['id']:
            raise ValueError('Noncanonical release UUID.')
        start = date.fromisoformat(metadata['effective_from'])
        end = date.fromisoformat(metadata['effective_until'])
        if (start.isoformat() != metadata['effective_from'] or end.isoformat() != metadata['effective_until']
                or start > end or end > date(end.year, 9, 30)
                or start < date(end.year - 1, 10, 1)):
            raise ValueError('Invalid fiscal-year interval.')
    except (ValueError, TypeError) as exc:
        raise CommandError('Invalid release identity/effective dates.') from exc
    if not isinstance(metadata['version'], str) or not 1 <= len(metadata['version']) <= 60:
        raise CommandError('Invalid release version.')
    official_url(metadata['source_url'])
    minimums = {'expected_code_count': 70000, 'expected_index_entry_count': 70000,
                'expected_tabular_diagnosis_count': 40000}
    for key, minimum in minimums.items():
        if type(m[key]) is not int or not minimum <= m[key] <= 500000:
            raise CommandError('A declared complete official reference is required, not a subset/addendum.')
    if not isinstance(m['files'], dict) or set(m['files']) != FILE_KEYS:
        raise CommandError('Codes, Index, Tabular and guidelines pins are all required.')
    payloads = {}
    for kind, ref in m['files'].items():
        if not isinstance(ref, dict) or set(ref) != {'path', 'sha256', 'source_url', 'archive'}:
            raise CommandError('Each reference needs exact path/SHA-256/official URL/archive provenance.')
        official_url(ref['source_url'])
        payloads[kind] = read_pinned_file(ref['path'], ref['sha256'], MAX_XML_BYTES)
        archive = ref['archive']
        if archive is not None:
            if (not isinstance(archive, dict) or set(archive) != {'path', 'sha256', 'member'}
                    or not isinstance(archive['member'], str) or not archive['member']):
                raise CommandError('Malformed source archive provenance.')
            raw_archive = read_pinned_file(archive['path'], archive['sha256'], 64 * 1024 * 1024)
            try:
                with zipfile.ZipFile(io.BytesIO(raw_archive)) as zipped:
                    matches = [i for i in zipped.infolist() if i.filename == archive['member']]
                    if len(matches) != 1 or not 0 < matches[0].file_size <= MAX_XML_BYTES:
                        raise CommandError('Source archive member is ambiguous, empty or oversized.')
                    if zipped.read(matches[0]) != payloads[kind]:
                        raise CommandError('Source archive member differs from the pinned extracted file.')
            except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
                raise CommandError('Cannot verify official source archive member.') from exc
        elif kind != 'guidelines':
            raise CommandError('Code/Index/Tabular files require the exact official archive/member pins.')
    if (m['files']['codes']['sha256'] != metadata['sha256']
            or m['files']['codes']['source_url'] != metadata['source_url']):
        raise CommandError('The codes file provenance must equal the existing CodeSet provenance.')
    if not payloads['guidelines'].startswith(b'%PDF-'):
        raise CommandError('Pinned official guidelines must be a PDF.')
    dictionary = parse_icd(payloads['codes'])
    if len(dictionary) != m['expected_code_count']:
        raise CommandError('Full codes count differs from the manifest.')
    try:
        reference = parse_reference(payloads['index'], payloads['tabular'], dictionary)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    if reference['tabular']['version'] != str(end.year):
        raise CommandError('XML fiscal year differs from the bound CodeSet dates.')
    if len(reference['index']) != m['expected_index_entry_count']:
        raise CommandError('Full Index entry count differs from the manifest.')
    if sum(n['kind'] == 'diag' for n in reference['tabular']['nodes'].values()) != m['expected_tabular_diagnosis_count']:
        raise CommandError('Full Tabular diagnosis count differs from the manifest.')
    provenance = {'format': MANIFEST_FORMAT, 'manifest_sha256': manifest_sha256,
                  'manifest': m, 'dictionary_sha256': reference['tabular']['dictionary_sha256'],
                  'network_fetch_performed': False}
    return {'reference': reference, 'provenance': provenance,
            'digest': reference_digest({**reference, 'provenance': provenance})}


@transaction.atomic
def save_reference(prepared):
    from core.models import AuditEvent, Code, CodeSet, CodingRelease
    if connection.vendor != 'postgresql':
        raise CommandError('Coding-reference imports require PostgreSQL.')
    database = str(connection.settings_dict['NAME'])
    if not (database.startswith('quillmd_') or database.startswith('test_quillmd_')):
        raise CommandError('Refusing to import outside a fresh quillmd_ database.')
    with connection.cursor() as cursor:
        # Same writer lock as CodeSet imports, so the dictionary cannot be
        # changed by a concurrent supported terminology import during binding.
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [913020260917])
    metadata = prepared['provenance']['manifest']['release']
    try:
        release = CodeSet.objects.select_for_update().get(pk=metadata['id'])
    except CodeSet.DoesNotExist as exc:
        raise CommandError('The declared existing CodeSet was not found.') from exc
    actual_metadata = {'id': str(release.pk), 'system': release.system, 'version': release.version,
                       'effective_from': release.effective_from.isoformat(),
                       'effective_until': release.effective_until.isoformat(),
                       'sha256': release.sha256, 'source_url': release.source_url}
    if actual_metadata != metadata:
        raise CommandError('Existing CodeSet metadata differs from the manifest.')
    actual = dict(Code.objects.filter(release=release).values_list('code', 'description'))
    reference = prepared['reference']
    if actual != reference['tabular']['codes']:
        raise CommandError('Existing code dictionary differs from the exact pinned complete codes file.')
    values = {**reference, 'provenance': prepared['provenance'], 'digest': prepared['digest']}
    if reference_digest({**reference, 'provenance': prepared['provenance']}) != prepared['digest']:
        raise CommandError('Prepared reference digest mismatch.')
    existing = CodingRelease.objects.select_for_update().filter(release=release).first()
    if existing:
        if any(getattr(existing, key) != value for key, value in values.items()):
            raise CommandError('Existing coding reference differs; references are immutable.')
        return existing, False
    created = CodingRelease.objects.create(release=release, **values)
    AuditEvent.objects.create(action='coding.reference_import', target=str(created.pk), details={
        'release': str(release.pk), 'version': release.version, 'system': release.system,
        'digest': prepared['digest'], 'manifest_sha256': prepared['provenance']['manifest_sha256'],
        'codes': len(actual), 'index_entries': len(reference['index']),
        'tabular_diagnoses': sum(n['kind'] == 'diag' for n in reference['tabular']['nodes'].values()),
    })
    return created, True


class Command(BaseCommand):
    help = 'Immutably attach pinned official Index/Tabular evidence to an exact existing ICD-10-CM CodeSet.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument('--manifest-sha256', required=True)

    def handle(self, *args, **options):
        prepared = prepare_reference(options['manifest'], options['manifest_sha256'])
        reference, created = save_reference(prepared)
        self.stdout.write(self.style.SUCCESS(
            f'{"Imported" if created else "Already verified"}: coding reference '
            f'{reference.release.version}; SHA-256 {reference.digest}.'))
