"""Write the offline backup exposure ledger (core.exposure): which recovery points may still contain a disposed or
redacted document, and what a restore of each re-applies.

    manage.py backup_exposure_ledger --checkpoint <signed checkpoint JSON file> --output <new file outside the state root> \
        [--recovery-points <inventory JSON exported from the backup system>] [--backup-root <local backup directory>]

The journal is verified complete against the independently signed checkpoint first. The ledger file is created once,
mode 0600, and must lie outside the clinical state root (it describes the restores that state root is subject to).
Standard output carries counts and the ledger's sha256 only: no identifiers, paths or clinical text.
"""
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core import disposition_journal as journal, disposition_policy as p, exposure


class Command(BaseCommand):
    help = 'Write the offline backup exposure ledger from the verified journal and the recovery point inventory.'

    def add_arguments(self, parser):
        parser.add_argument('--checkpoint', required=True, help='File holding the independently signed journal checkpoint.')
        parser.add_argument('--output', required=True, help='New file for the ledger, outside the clinical state root.')
        parser.add_argument('--recovery-points', help='JSON inventory exported from the backup system.')
        parser.add_argument('--backup-root', help='Local encrypted backup directory (ops/backup_restore.py runs).')

    def handle(self, *args, **options):
        if not options['recovery_points'] and not options['backup_root']:
            raise CommandError('Name the recovery points: --recovery-points and/or --backup-root.')
        try:
            with Path(options['checkpoint']).open('rb') as stream: checkpoint = p.decode(stream.read(p.MAX_BYTES + 1))
            entries = journal.verified(checkpoint)
            points = []
            if options['recovery_points']:
                with Path(options['recovery_points']).open('rb') as stream:
                    raw = stream.read(64 * 1024 * 1024 + 1)
                if len(raw) > 64 * 1024 * 1024: raise ValidationError('The recovery point inventory is too large.')
                try: data = json.loads(raw)
                except ValueError: raise ValidationError('The recovery point inventory is not JSON.') from None
                points += exposure.inventory(data)
            if options['backup_root']:
                points += exposure.local_backups(options['backup_root'])
            if len({point['id'] for point in points}) != len(points):
                raise ValidationError('A recovery point is listed twice.')
            # Commit evidence is this database's tombstones: run it against the live database, never a restored one.
            value = exposure.ledger(entries, points, timezone.now(), exposure.commit_evidence())
            digest = exposure.write_private(options['output'], value)
        except OSError:
            raise CommandError('An input file could not be read.') from None
        except ValidationError as error:
            raise CommandError(' '.join(error.messages)) from None
        self.stdout.write(json.dumps({'ledger_sha256': digest, **value['counts'],
                                      'journal_sequence': value['journal']['sequence']}, sort_keys=True))
