"""Admit a quarantined restored target after journal replay; write one append-only RestoreAdmission record.

    manage.py restore_admission --instance-id <QUILLMD_RESTORE_INSTANCE_ID> --custodian <administrator email> \
        --checkpoint <signed checkpoint JSON file> --expected-triggers <release contract count> [--check-only]

--check-only runs every admission condition and prints the counts-only report without writing anything. Output never
contains clinical text, file paths or row content. Quarantine lifts only after this command has written the record and
the operator has set QUILLMD_RESTORE_QUARANTINE=0 while keeping QUILLMD_RESTORE_INSTANCE_ID (cutover plan).
"""
import json
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from core import disposition_policy as p, restore_admission, retention
from core.models import User


class Command(BaseCommand):
    help = 'Admit a quarantined restored target after replay (writes one append-only RestoreAdmission record).'

    def add_arguments(self, parser):
        parser.add_argument('--instance-id', required=True)
        parser.add_argument('--custodian', required=True, help='Email of the verified administrator recording admission.')
        parser.add_argument('--checkpoint', required=True, help='File holding the independently signed journal checkpoint.')
        parser.add_argument('--expected-triggers', type=int, required=True)
        parser.add_argument('--check-only', action='store_true')

    def handle(self, *args, **options):
        try:
            path = Path(options['checkpoint'])
            with path.open('rb') as stream: raw = stream.read(p.MAX_BYTES + 1)
            checkpoint = p.decode(raw)
            actor = User.objects.filter(email__iexact=options['custodian']).first()
            retention.custodian(actor)
            if options['check_only']:
                report = restore_admission.assess(options['instance_id'], checkpoint, options['expected_triggers'])
                self.stdout.write(json.dumps(report, sort_keys=True))
                if not report['admissible']: raise CommandError('Restore admission is not available: ' + ', '.join(report['blockers']) + '.')
                return
            row = restore_admission.admit(actor, options['instance_id'], checkpoint, options['expected_triggers'])
        except OSError:
            raise CommandError('The checkpoint file could not be read.') from None
        except (ValidationError, PermissionDenied) as error:
            raise CommandError(' '.join(getattr(error, 'messages', None) or [str(error)])) from None
        except RuntimeError as error:
            # The restore check raises only fixed labels (production_restore_check.CheckError, backup_restore.require).
            raise CommandError('The restore check refused: ' + str(error)) from None
        self.stdout.write(json.dumps({'admitted': True, 'instance_id': str(row.instance_id), 'record': str(row.pk),
                                      'journal_sequence': row.journal_sequence, 'report_sha256': row.report_sha256},
                                     sort_keys=True))
