"""Import a verified public ICD-10-CM release or an explicitly licensed CPT CSV.

This loads terminology into the fresh application. It never reads old users,
clinical documents, application history, or an old application database.
"""
import csv
from datetime import date
import hashlib
import io
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from core.models import AuditEvent, Code, CodeSet

MAX_BYTES = 20 * 1024 * 1024
MIN_ICD_CODES = 70000
OFFICIAL_HOSTS = {'ftp.cdc.gov', 'www.cdc.gov', 'cdc.gov', 'www.cms.gov', 'cms.gov'}
# FY2026 includes QA0.* categories: the second character is not always numeric.
ICD_PATTERN = re.compile(r'[A-Z][A-Z0-9]{2,6}\Z')
CPT_PATTERN = re.compile(r'(?:[0-9]{5}|[0-9]{4}[A-Z])\Z')


def text_payload(payload):
    try:
        return payload.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError as exc:
        raise CommandError('Terminology must be strict UTF-8; no replacement decoding is allowed.') from exc


def description(value, line):
    value = value.strip()
    if not value or len(value) > 500 or any(unicodedata.category(c).startswith('C') for c in value):
        raise CommandError(f'Invalid or oversized description on row {line}; nothing was imported.')
    return value


def parse_icd(payload):
    """Read the official *codes* file, not an addendum, order file or XML leaf list."""
    rows = {}
    for number, line in enumerate(text_payload(payload).splitlines(), 1):
        if not line.strip():
            continue
        raw = line[:7].rstrip()
        if len(line) < 9 or line[7] != ' ' or not ICD_PATTERN.fullmatch(raw):
            raise CommandError(f'Invalid ICD-10-CM codes-file format on row {number}.')
        code = raw[:3] + ('.' + raw[3:] if len(raw) > 3 else '')
        if code in rows:
            raise CommandError(f'Duplicate terminology code on row {number}.')
        rows[code] = description(line[8:], number)
    if not rows:
        raise CommandError('Empty terminology file.')
    return rows


def parse_cpt(payload):
    """Only caller-provided licensed CSV. No CPT download or inferred descriptors."""
    reader = csv.DictReader(io.StringIO(text_payload(payload), newline=''), strict=True)
    if reader.fieldnames != ['code', 'description']:
        raise CommandError('Licensed CPT CSV must have exactly code,description columns.')
    rows = {}
    try:
        for number, row in enumerate(reader, 2):
            code = row.get('code', '')
            if None in row or not code or not CPT_PATTERN.fullmatch(code) or row.get('description') is None:
                raise CommandError(f'Invalid CPT CSV row {number}.')
            if code in rows:
                raise CommandError(f'Duplicate terminology code on row {number}.')
            rows[code] = description(row['description'], number)
    except csv.Error as exc:
        raise CommandError('Malformed CPT CSV.') from exc
    if not rows:
        raise CommandError('Empty terminology file.')
    return rows


@transaction.atomic
def save_release(rows, metadata, license_expiry=''):
    # Serialize all release writers so concurrent repeat imports cannot create
    # overlapping current releases or duplicate audit events.
    if connection.vendor != 'postgresql':
        raise CommandError('Terminology imports require the fresh PostgreSQL database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [913020260917])
    existing = CodeSet.objects.filter(system=metadata['system'], version=metadata['version']).first()
    if existing:
        if any(getattr(existing, key) != value for key, value in metadata.items()):
            raise CommandError('This version already exists with different metadata. Releases are immutable.')
        actual = dict(Code.objects.filter(release=existing).values_list('code', 'description'))
        if actual != rows:
            raise CommandError('Existing terminology differs from the verified file; refusing to overwrite it.')
        return existing, False
    if CodeSet.objects.filter(system=metadata['system'],
                              effective_from__lte=metadata['effective_until'],
                              effective_until__gte=metadata['effective_from']).exists():
        raise CommandError('This release overlaps an existing version; effective periods must be explicit.')
    release = CodeSet.objects.create(**metadata)
    Code.objects.bulk_create([Code(release=release, code=code, description=title)
                              for code, title in rows.items()], batch_size=1000)
    AuditEvent.objects.create(action='terminology.import', target=str(release.pk), details={
        'system': release.system, 'version': release.version, 'count': len(rows),
        'sha256': release.sha256, 'source_url': release.source_url,
        'effective_from': release.effective_from.isoformat(),
        'effective_until': release.effective_until.isoformat(),
        'license_expiry': license_expiry,
    })
    return release, True


class Command(BaseCommand):
    help = 'Import verified full ICD-10-CM codes or supplied licensed CPT CSV into the fresh database.'

    def add_arguments(self, parser):
        parser.add_argument('--system', choices=['ICD-10-CM', 'CPT'], required=True)
        parser.add_argument('--path', required=True)
        parser.add_argument('--sha256', required=True)
        parser.add_argument('--release-version', required=True)
        parser.add_argument('--effective-from', required=True)
        parser.add_argument('--effective-until', required=True)
        parser.add_argument('--source-url', required=True)
        parser.add_argument('--expected-count', type=int, required=True)

    def handle(self, *args, **options):
        database = str(connection.settings_dict['NAME'])
        if not (database.startswith('quillmd_') or database.startswith('test_quillmd_')):
            raise CommandError('Refusing to import outside a fresh quillmd_ database.')
        try:
            start = date.fromisoformat(options['effective_from'])
            end = date.fromisoformat(options['effective_until'])
        except ValueError as exc:
            raise CommandError('Effective dates must use YYYY-MM-DD.') from exc
        if start > end:
            raise CommandError('Effective start must precede or equal the end date.')
        version = options['release_version'].strip()
        if not version or len(version) > 60 or any(unicodedata.category(c).startswith('C') for c in version):
            raise CommandError('Version must contain 1–60 characters.')
        source = options['source_url']
        try:
            url = urlsplit(source)
            valid_source = (url.scheme == 'https' and url.hostname and not url.username
                            and not url.password and not url.query and not url.fragment
                            and url.port in (None, 443) and len(source) <= 200
                            and not any(ord(c) < 33 for c in source))
        except ValueError:
            valid_source = False
        if not valid_source:
            raise CommandError('Use a stable HTTPS provenance URL without credentials, query or fragment.')
        system = options['system']
        license_reference = ''
        license_expiry = ''
        if system == 'ICD-10-CM':
            if url.hostname not in OFFICIAL_HOSTS:
                raise CommandError('ICD-10-CM provenance must be an official CDC or CMS source.')
            if options['expected_count'] < MIN_ICD_CODES:
                raise CommandError('A full ICD-10-CM codes file is required; an addendum or subset is refused.')
        else:
            from core.coding_licensing import entitlement_for_release, EntitlementUnavailable
            try:
                entitlement = entitlement_for_release(version=version, effective_from=start, effective_until=end,
                    source_url=source, sha256=options['sha256'].lower(), code_count=options['expected_count'])
            except EntitlementUnavailable as exc:
                raise CommandError(exc.messages[0]) from exc
            license_reference = entitlement['manifest']['license_id']
            license_expiry = entitlement['manifest']['validity']['until']
        expected_hash = options['sha256'].lower()
        if not re.fullmatch('[0-9a-f]{64}', expected_hash):
            raise CommandError('Expected SHA-256 must contain 64 hexadecimal characters.')
        path = Path(options['path'])
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise CommandError('Terminology path must be a nonempty regular file of at most 20 MiB.')
        with path.open('rb') as stream:
            payload = stream.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES or hashlib.sha256(payload).hexdigest() != expected_hash:
            raise CommandError('Terminology checksum mismatch; nothing was imported.')
        rows = parse_icd(payload) if system == 'ICD-10-CM' else parse_cpt(payload)
        if len(rows) != options['expected_count']:
            raise CommandError('Terminology row count differs from the declared full release count.')
        metadata = dict(system=system, version=version, effective_from=start, effective_until=end,
                        source_url=source, sha256=expected_hash, license_reference=license_reference)
        if system == 'CPT':
            from core.coding_licensing import save_licensed_release, EntitlementUnavailable
            try:
                release, created = save_licensed_release(rows, metadata, entitlement)
            except EntitlementUnavailable as exc:
                raise CommandError(exc.messages[0]) from exc
        else:
            release, created = save_release(rows, metadata, license_expiry)
        self.stdout.write(self.style.SUCCESS(
            f'{"Imported" if created else "Already verified"}: {release.system} {release.version}; '
            f'{len(rows)} codes; SHA-256 {release.sha256}.'))
