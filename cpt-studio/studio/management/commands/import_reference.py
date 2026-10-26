"""Load one public CMS reference file in a single transaction.

    manage.py import_reference --kind cms-pfs --zip rvu26d.zip --expected-sha256 <hex> --release RVU26D \\
        --url https://www.cms.gov/files/zip/... --effective-start 2026-10-01 --effective-end 2026-12-31 \\
        --retrieved-at 2026-10-23T20:59:00Z

Only code-keyed facts are stored; descriptors are never imported. Re-running
with the same file is a no-op; a different file under the same release is
refused.
"""
import argparse
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from studio.models import ReferenceSource
from studio.reference.importers import IMPORTERS, ReferenceImportError, source_key


def _date(value):
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'{value!r} is not a YYYY-MM-DD date') from exc


def _aware_datetime(value):
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f'{value!r} is not an ISO-8601 date and time') from exc
    if not timezone.is_aware(moment):
        raise argparse.ArgumentTypeError(f'{value!r} has no UTC offset')
    return moment


class Command(BaseCommand):
    help = 'Import a public CMS reference file (code-keyed facts only; descriptors are never imported).'

    def add_arguments(self, parser):
        parser.add_argument('--kind', required=True, choices=sorted(IMPORTERS))
        parser.add_argument('--zip', required=True, dest='zip_path')
        parser.add_argument('--expected-sha256', required=True)
        parser.add_argument('--release', required=True)
        parser.add_argument('--url', required=True)
        parser.add_argument('--effective-start', required=True, type=_date)
        parser.add_argument('--effective-end', required=True, type=_date)
        parser.add_argument('--retrieved-at', required=True, type=_aware_datetime)

    def handle(self, *args, **options):
        kind = options['kind']
        try:
            key = source_key(kind, options['release'])
            with transaction.atomic():
                existed = ReferenceSource.objects.filter(key=key).exists()
                source = IMPORTERS[kind](
                    options['zip_path'], expected_sha256=options['expected_sha256'], release=options['release'],
                    url=options['url'], effective_start=options['effective_start'],
                    effective_end=options['effective_end'], retrieved_at=options['retrieved_at'])
        except ReferenceImportError as exc:
            raise CommandError(str(exc)) from exc
        if existed:
            self.stdout.write(f'{source.key} is already loaded from this file (sha256 {source.sha256}); '
                              'nothing changed.')
            return
        self.stdout.write(f'Loaded {source.key}: {source.row_count} rows from {source.title}, effective '
                          f'{source.effective_start.isoformat()} to {source.effective_end.isoformat()}, '
                          f'sha256 {source.sha256}.')
