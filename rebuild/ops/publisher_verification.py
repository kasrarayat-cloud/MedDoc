#!/usr/bin/env python3
"""Judge ONE operations-publisher run from systemd's record, the journal and the committed row.

⚠️ WHY THIS EXISTS. `publish_operations_status` publishes, then exits 1 whenever the backup state
is unhealthy ("Publishing succeeded; the STATE is unhealthy. Say so in the exit code"), and the
unit carries no SuccessExitStatus. So after the offsite policy expired, every tick ended
`Result=exit-code, ExecMainStatus=1` while publishing correctly — and the 2026-09-22 install
adapter, which required `Result=success`, reported a failed self-check on a release that had
installed cleanly. But an uncaught exception ALSO exits 1, so the exit code alone cannot tell
"published; backups unhealthy" from "broke". The verdict is therefore bound to the run itself:

1. systemd shows a NEW invocation (a oneshot's Result/ExecMainStatus replay the last run);
2. the committed row is newer than before AND its computed_at lies inside that invocation's
   start..exit window, so it was written by this run and not by another writer or an earlier one;
3. that invocation's journal carries exactly one "Published backup status: C (S)." matching the
   row, and no traceback or error lines;
4. the exit agrees with the published state: status 0 only for a healthy/warning/in-progress row,
   status 1 only for an UNHEALTHY row. Any other status or Result is a failure.

Publication and backup health are reported as SEPARATE fields. A verified publication of an
unhealthy state is `publication_verified: True, backup_healthy: False` — never a healthy claim.
"""
from datetime import datetime, timedelta, timezone
import re

PUBLISHED = re.compile(r'^Published backup status: (?P<condition>[A-Za-z0-9_]+) \((?P<severity>[a-z_]+)\)\.$')
ERROR_LINE = re.compile(r'Traceback \(most recent call last\)|\bError\b|\bException\b|CommandError')
#: systemd prints wall-clock start/exit to the second; the row's computed_at has microseconds.
CLOCK_SLACK = timedelta(seconds=1)


class VerificationFailure(RuntimeError):
    def __init__(self, reason, detail=''):
        self.reason = reason
        super().__init__(reason + (': ' + detail if detail else ''))


def systemd_time(value):
    """'Tue 2026-09-22 20:58:15 UTC' → aware datetime. Anything else is unverifiable."""
    try:
        return datetime.strptime(value.strip(), '%a %Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)
    except (AttributeError, ValueError):
        raise VerificationFailure('unverifiable_timestamps', repr(value)) from None


def row_time(value):
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value))
        except ValueError:
            raise VerificationFailure('unverifiable_row', repr(value)) from None
    if result.tzinfo is None:
        raise VerificationFailure('unverifiable_row', 'naive computed_at')
    return result.astimezone(timezone.utc)


def judge(before_row, before_invocation, unit, row, journal):
    """Return the verdict for the run `unit` describes, or raise VerificationFailure.

    before_row / row: {'computed_at', 'condition', 'severity', 'healthy'} (row may be None)
    before_invocation: the InvocationID seen before; unit: `systemctl show` properties of the run
    journal: [(invocation_id, message), ...] for the service unit around the run
    """
    invocation = (unit or {}).get('InvocationID') or ''
    if not re.fullmatch(r'[0-9a-f]{32}', invocation):
        raise VerificationFailure('no_invocation')
    if invocation == (before_invocation or ''):
        raise VerificationFailure('replayed_invocation', 'the properties describe the previous run')
    if not row:
        raise VerificationFailure('no_write', 'no published row')
    written = row_time(row['computed_at'])
    if before_row and written <= row_time(before_row['computed_at']):
        raise VerificationFailure('no_write', 'the row did not advance')
    start = systemd_time(unit.get('ExecMainStartTimestamp', ''))
    end = systemd_time(unit.get('ExecMainExitTimestamp', ''))
    if not (start - CLOCK_SLACK <= written <= end + CLOCK_SLACK):
        raise VerificationFailure('stale_or_foreign_write', f'row {written.isoformat()} outside run {start}..{end}')
    lines = [message for owner, message in journal if owner == invocation]
    if any(ERROR_LINE.search(str(message)) for message in lines):
        raise VerificationFailure('execution_error', 'error output in this invocation')
    published = [PUBLISHED.match(str(message).strip()) for message in lines]
    published = [match for match in published if match]
    if len(published) != 1:
        raise VerificationFailure('publication_not_logged', f'{len(published)} publication lines')
    if (published[0]['condition'], published[0]['severity']) != (row['condition'], row['severity']):
        raise VerificationFailure('publication_mismatch', 'journal and committed row disagree')
    result, status = unit.get('Result'), unit.get('ExecMainStatus')
    healthy = row.get('healthy') is True
    if result == 'success' and status == '0':
        if not (healthy or row['severity'] in ('warning', 'in_progress')):
            raise VerificationFailure('inconsistent_exit', 'exit 0 with an unhealthy failure row')
    elif result == 'exit-code' and status == '1':
        if healthy or row['severity'] == 'healthy':
            raise VerificationFailure('inconsistent_exit', 'exit 1 with a healthy row is an execution fault')
    else:
        raise VerificationFailure('execution_failure', f'Result={result} ExecMainStatus={status}')
    return {'publication_verified': True, 'invocation': invocation,
            'exit': {'result': result, 'status': status},
            'row': {'computed_at': written.isoformat(), 'condition': row['condition'],
                    'severity': row['severity'], 'healthy': healthy},
            'backup_healthy': healthy,
            'meaning': ('Publication verified; the published backup state is healthy.' if healthy else
                        'Publication verified; the published backup state is UNHEALTHY ('
                        + row['condition'] + '). The non-zero exit reports that state, not a failure to publish.')}
