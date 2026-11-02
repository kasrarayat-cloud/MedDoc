"""Load the verbatim CMS passages of one data file in a single transaction.

    manage.py import_passages --data studio/reference/data/cms-ncci-policy-manual-2026-ch6.json

The data files are studio/reference/data/*.json (studio/reference/passages.py describes them); ops/verify_passages.py
proves their passages against the publishers' PDFs. A passage that quotes a CPT code description is never imported.
Re-running with the same file is a no-op that says so; anything else under a loaded source's key, the same file under
another key, and a window that overlaps a loaded source of the same kind are refused.
"""
from django.core.management.base import BaseCommand, CommandError

from studio.reference.passages import PassageImportError, import_data_file


class Command(BaseCommand):
    help = 'Import the verbatim CMS passages of one data file (passages quoting a CPT code description never are).'

    def add_arguments(self, parser):
        parser.add_argument('--data', required=True, dest='data_path')

    def handle(self, *args, **options):
        try:
            source, created = import_data_file(options['data_path'])
        except PassageImportError as exc:
            raise CommandError(str(exc)) from exc
        if not created:
            self.stdout.write(f'{source.key} is already loaded with these {source.passage_count} passages (sha256 '
                              f'{source.sha256}); nothing changed.')
            return
        self.stdout.write(f'Loaded {source.key}: {source.passage_count} passages from {source.title}, effective '
                          f'{source.effective_start.isoformat()} to {source.effective_end.isoformat()}, sha256 '
                          f'{source.sha256}.')
