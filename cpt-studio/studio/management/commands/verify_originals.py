"""Read stored originals and converted PDFs again and check their sha256 (release 1, D3; 164.312(c)(1) integrity;
studio.maintenance.verify_originals).

A random sample (--sample, default maintenance.VERIFY_SAMPLE of each kind), or every stored file with --all. Each file
that no longer matches its recorded sha256, is missing or cannot be read writes one SecurityEvent
storage.original_mismatch (ids only), and the run one maintenance.originals_verified with its counts. The worker runs the
same check once a week. The command answers an error (non-zero exit) when any problem was found, so whoever runs it sees
it; alerting from outside the host is new-server work.
"""
from django.core.management.base import BaseCommand, CommandError

from studio import maintenance


class Command(BaseCommand):
    help = 'Check a sample (or --all) of the stored originals and converted PDFs against their recorded sha256.'

    def add_arguments(self, parser):
        parser.add_argument('--sample', type=int, default=maintenance.VERIFY_SAMPLE,
                            help='How many of each kind to read (default %(default)s).')
        parser.add_argument('--all', action='store_true', help='Read every stored file.')

    def handle(self, *args, **options):
        if options['sample'] < 1:
            raise CommandError('--sample is a whole number, at least 1.')
        counts = maintenance.verify_originals(sample=options['sample'], every_file=options['all'])
        line = 'Stored files checked: ' + ', '.join(f'{name} {value}' for name, value in counts.items())
        problems = sum(counts[name] for name in (maintenance.MISMATCH, maintenance.MISSING, maintenance.UNREADABLE))
        if problems:
            raise CommandError(f'{line}. {problems} stored file(s) failed the check; each has a SecurityEvent '
                               f'{maintenance.MISMATCH_EVENT}.')
        self.stdout.write(line)
