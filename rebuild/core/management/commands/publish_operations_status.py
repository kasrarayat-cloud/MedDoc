"""Publish backup/offsite status INTO the database, for the administration console to read.

⚠️ THE WEB PROCESS CANNOT READ THE BACKUP STATE, AND THE OBVIOUS VIEW IS A FALSE RED.

`deploy/quillmd-fresh-admin.service` runs the admin surface as `quillmd-app` and carries
`InaccessiblePaths=… /opt/meddoc-pro/rebuild/.runtime`, so the whole runtime tree is masked out
of its mount namespace; the state directories are additionally mode 0700 owned by the operations
identity, which is a different user with no shared group. A view that reads
`.runtime/backup-alerts/status.json` therefore returns 'unavailable' on a host whose backups are
perfectly healthy — and a panel that is wrong when things are fine is one somebody stops reading,
which is how the false red becomes a false green on the night it matters.

The identities are disjoint by design and this command does not change that. It runs AS the
operations identity (the same user as `quillmd-fresh-backup-alerts.service`), calls the existing
aggregator, and writes the already-redacted report into a table the web process can read. The
console renders that row and distinguishes three states it must never collapse: never published,
published-but-stale, published-and-fresh.

Nothing new is computed here and nothing is interpreted. `ops.backup_alerts.report()` already
emits a fixed non-clinical shape — condition, severity, healthy, an action sentence, timestamps,
run identifiers and boolean verdicts. This copies it.

    python manage.py publish_operations_status            # publish
    python manage.py publish_operations_status --dry-run  # print, write nothing

Exit status mirrors the aggregator: 0 when healthy or merely warning, 1 otherwise, so a timer
that runs it surfaces a failure the same way the alert check does.
"""
import json
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import ServiceHealth

from ops import activation_exclusion as exclusion

#: Keys of the aggregator's report that are safe and useful to retain. Anything the aggregator
#: might add later is dropped rather than published blind: a redaction allowlist only works if
#: it is an allowlist.
#:
#: ⚠️ AND WHAT SAYS THE REPORT IS STALE IS PART OF THE REPORT (R3-2, round 3). `check_running`
#: marks a report made while a monitor check was running (it shows the last completed check), and
#: `state_unreadable` one made from a monitor state that could not be read, with the backup
#: condition computed anyway and when the next restart notice may be sent. Dropping them published
#: a stale or unreadable state as though it were current. Fixed labels, booleans and timestamps only.
PAYLOAD_KEYS = ('local_capture', 'offsite', 'external_monitor', 'alert',
                'offsite_recovery_verified', 'outside_host_failure_detection',
                'clinical_content_included', 'monitor_age_seconds', 'stale_after_seconds',
                'check_running', 'state_unreadable', 'backup_condition', 'backup_severity',
                'next_state_notice_at', 'last_state_notice_condition')


def collect():
    """Call the operations aggregator. Import is local so the web process never loads it."""
    from pathlib import Path
    root = str(Path(__file__).resolve().parents[3])
    if root not in sys.path:
        sys.path.insert(0, root)
    from ops import backup_alerts
    return backup_alerts.status()


class Command(BaseCommand):
    help = 'Publish the backup/offsite status report into ServiceHealth for the admin console.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Print the document that would be published and write nothing.')
        parser.add_argument('--interval-seconds', type=int, default=300,
                            help='Cadence this publisher runs at. The console calls the row STALE past twice this.')

    def handle(self, *args, **options):
        interval = options['interval_seconds']
        if interval < 60:
            raise CommandError('An interval under 60 seconds cannot be distinguished from a stuck publisher.')
        if options['dry_run']:
            return self.publish(interval, dry_run=True)
        # ⚠️ EXCLUSION, AND THE COLLECTION HAPPENS INSIDE IT. This command and the activation both
        # write state the activation's preservation checks guard. On 2026-09-22 a tick landed
        # inside an act's window and the invariant refused, correctly. Collecting outside the lock
        # and writing inside it would be worse than the race it replaces: it would publish a
        # picture of the host from BEFORE the activation under a current timestamp.
        with exclusion.attempt('publish_operations_status') as acquired:
            if not acquired:
                holder = exclusion.holder() or {}
                exclusion.record('publication_deferred', reason='activation_holds_exclusion',
                                 holder=holder.get('owner'), holder_pid=holder.get('pid'))
                # No write, and NO health claimed. The existing row is left strictly alone so its
                # own staleness check keeps working — a deferred tick must age visibly, not be
                # papered over with a manufactured green.
                self.stdout.write('Publication deferred: an activation holds exclusion. '
                                  'Nothing written; the existing row keeps its own freshness.')
                return
            return self.publish(interval, dry_run=False)

    def publish(self, interval, *, dry_run):
        report, code = collect()
        if not isinstance(report, dict) or 'condition' not in report or 'severity' not in report:
            raise CommandError('The operations aggregator returned a shape this publisher does not recognise.')
        if report.get('clinical_content_included') is not False:
            # The aggregator asserts this itself. If it ever stops asserting it, refuse rather
            # than copy an unknown document into a table the console renders.
            raise CommandError('Refusing to publish a report that does not assert clinical_content_included=False.')
        payload = {key: report[key] for key in PAYLOAD_KEYS if key in report}
        document = {
            'condition': str(report['condition'])[:60],
            'severity': report['severity'] if report['severity'] in dict(ServiceHealth.SEVERITIES) else 'failure',
            'healthy': bool(report.get('healthy')),
            'action': str(report.get('action') or '')[:400],
            'payload': json.loads(json.dumps(payload, default=str)),
            'computed_at': timezone.now(),
            'expected_interval_seconds': interval,
        }
        if dry_run:
            self.stdout.write(json.dumps({**document, 'computed_at': document['computed_at'].isoformat()},
                                         sort_keys=True, indent=2))
            return
        ServiceHealth.objects.update_or_create(key='backup', defaults=document)
        self.stdout.write(f"Published backup status: {document['condition']} ({document['severity']}).")
        if code:
            # Publishing succeeded; the STATE is unhealthy. Say so in the exit code, as the
            # alert check does, so a timer does not read a successful write as a healthy host.
            raise SystemExit(code)
