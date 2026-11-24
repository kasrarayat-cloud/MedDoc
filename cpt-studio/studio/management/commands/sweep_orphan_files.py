"""Count, or remove, the stored files no row names (release 1, D3; studio.maintenance.sweep_orphan_files).

A file under ORIGINALS_DIR is an orphan when neither SourceFile.storage_name nor CodingRound.view_pdf_storage_name names
it and it was last changed more than an hour ago (a younger one may belong to an upload still in progress). A dry run
unless --delete is given. The output is counts only - never a file's name. A run that deletes records first: one
SecurityEvent maintenance.orphans_swept with what the sweep found (the orphans it goes on to remove), then it removes
them and prints what it removed - so a record the database refuses removes nothing (refutation round 2, records-2). The
daily maintenance runs the same sweep, deleting.
"""
from django.core.management.base import BaseCommand

from studio import maintenance, security_events


class Command(BaseCommand):
    help = 'Count (a dry run) or, with --delete, remove the stored files that no row names and that are over an hour old.'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true', help='Remove the orphans (default: only count them).')

    def handle(self, *args, **options):
        counts, orphans = maintenance.scan_orphan_files()
        if options['delete']:
            security_events.record(maintenance.SWEPT_EVENT, **{name: value for name, value in counts.items()
                                                               if name not in ('deleted', 'failed')})
            counts.update(maintenance.remove_orphan_files(orphans))
        mode = 'removed' if options['delete'] else 'dry run, nothing removed'
        self.stdout.write(f'Orphan sweep ({mode}): ' + ', '.join(f'{name} {value}' for name, value in counts.items()))
