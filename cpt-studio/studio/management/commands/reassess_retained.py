"""Re-assess one document from its retained answers, with nothing sent (owner directive 2026-11-03, section 6: "Mara is
reassessed using retained responses where possible"; R6 6.4; P5 FLOW).

    python manage.py reassess_retained --encounter <uuid> --tag <release> [--username <account>] [--dry-run]

Queues ONE assess of the current revision in the re-assessment mode that re-reads exactly what the final assessment
read - the retained Corti answer and every participant run and peer run its entries name, by id - and builds or sends
no request and queues no peer stage (jobs.reassess_retained, which states every refusal). The running worker makes it;
an identical result keeps the assessment that stands. The job is keyed by the tag, so a second run for the same release
queues nothing. Prints one JSON object: what was queued (or would be, with --dry-run) and what it re-reads. Exits 1 with
the reason when refused. Records the 'assessment.refreshed' audit row ("Results were refreshed with updated software"),
attributed to --username when given, else to the system.
"""
import json
import uuid

from django.core.management.base import BaseCommand, CommandError

from studio import jobs, models


class Command(BaseCommand):
    help = 'Re-assess one document from its retained answers, sending nothing (one job per release tag).'

    def add_arguments(self, parser):
        parser.add_argument('--encounter', required=True, help='the document (encounter) id')
        parser.add_argument('--tag', required=True, help='the release the re-assessment is made for')
        parser.add_argument('--username', default='', help='the account the request is recorded for (default: system)')
        parser.add_argument('--dry-run', action='store_true', help='check every guard and print the plan; queue nothing')
        parser.add_argument('--participants', default=None,
                            help='the participants the worker runs, comma-separated, or none (default: this '
                                 "process's own configuration); the installer passes its app receipt's")

    def handle(self, *args, **options):
        try:
            encounter = models.Encounter.objects.get(pk=uuid.UUID(options['encounter']))
        except (ValueError, models.Encounter.DoesNotExist):
            raise CommandError('No document has that id.')
        user = None
        if options['username']:
            user = models.User.objects.filter(username=options['username'], is_active=True).first()
            if user is None:
                raise CommandError('No active account has that username.')
        expected = None
        if options['participants'] is not None:
            from studio import participants
            value = options['participants'].strip()
            expected = [] if value == 'none' else [name.strip() for name in value.split(',')]
            if not all(name in participants.PARTICIPANTS for name in expected) or len(set(expected)) != len(expected):
                raise CommandError('--participants names each participant once (' + ', '.join(participants.PARTICIPANTS)
                                   + '), or is none.')
        try:
            out = jobs.reassess_retained(encounter, options['tag'], user=user, dry_run=options['dry_run'],
                                         expected_participants=expected)
        except jobs.Refused as exc:
            raise CommandError(str(exc))
        self.stdout.write(json.dumps(out, sort_keys=True))
