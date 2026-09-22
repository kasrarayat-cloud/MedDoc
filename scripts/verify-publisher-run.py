#!/usr/bin/env python3
"""READ-ONLY: judge the next SCHEDULED operations-publisher run and append the verdict as evidence.

It never starts, stops or edits a unit and never writes the database. It reads `systemctl show`
and the unit's journal through the repository's managed root helper (read-only bind of `/`), and
the committed `core_servicehealth` row through the database container, then applies
`rebuild/ops/publisher_verification.judge`. The evidence file is created with O_EXCL: an earlier
receipt — including a failed self-check — is never rewritten.

Usage: verify-publisher-run.py --output <new evidence json> [--refers-to <receipt path>] [--bound-seconds 480]
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / 'rebuild'))
sys.path.insert(0, str(SOURCE / 'rebuild' / 'ops'))
import publisher_verification as verification  # noqa: E402

SERVICE = 'quillmd-fresh-operations-publisher.service'
TIMER = 'quillmd-fresh-operations-publisher.timer'
PROPERTIES = ('InvocationID', 'Result', 'ExecMainStatus', 'ExecMainStartTimestamp', 'ExecMainExitTimestamp')


def helper(code):
    from ops import install_backup_schedule as base, managed_helper
    argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', 'none', '--pid=host',
            '--mount', 'type=bind,src=/,dst=/host,readonly', base.IMAGE, 'python', '-B', '-']
    return managed_helper.run_helper(argv, input=code.encode(), timeout=120).stdout.decode()


def show(unit, properties):
    code = ("import os,subprocess,sys\nos.chroot('/host');os.chdir('/')\n"
            "sys.stdout.write(subprocess.run(" + repr(['systemctl', 'show', unit, '--property=' + ','.join(properties)])
            + ",capture_output=True,text=True,check=True).stdout)\n")
    return dict(line.split('=', 1) for line in helper(code).splitlines() if '=' in line)


def journal(since):
    code = ("import os,subprocess,sys\nos.chroot('/host');os.chdir('/')\n"
            "sys.stdout.write(subprocess.run(" + repr(['journalctl', '-u', SERVICE, '--since', since, '-o', 'json', '--no-pager'])
            + ",capture_output=True,text=True,check=True).stdout)\n")
    entries = []
    for line in helper(code).splitlines():
        if line.strip():
            item = json.loads(line)
            entries.append((item.get('_SYSTEMD_INVOCATION_ID') or item.get('INVOCATION_ID') or '', str(item.get('MESSAGE', ''))))
    return entries


def published_row():
    query = ("select json_build_object('computed_at', computed_at, 'condition', condition, 'severity', severity, "
             "'healthy', healthy) from core_servicehealth where key='backup'")
    out = subprocess.run(['docker', 'exec', 'quillmd-fresh-postgres', 'psql', '-U', 'quillmd_fresh', '-d', 'quillmd_fresh',
                          '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c', "SET timezone='UTC'; " + query],
                         capture_output=True, text=True, check=True).stdout.strip().splitlines()
    rows = [line for line in out if line.startswith('{')]
    return json.loads(rows[0]) if rows else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--output', required=True)
    parser.add_argument('--refers-to', default='')
    parser.add_argument('--bound-seconds', type=int, default=480)
    args = parser.parse_args()
    started = datetime.now(timezone.utc)
    before_row, before_unit = published_row(), show(SERVICE, PROPERTIES)
    before_trigger = show(TIMER, ('LastTriggerUSec',)).get('LastTriggerUSec')
    evidence = {'kind': 'publisher_run_reverification', 'read_only': True, 'started_at': started.isoformat(),
                'before': {'row': before_row, 'invocation': before_unit.get('InvocationID'), 'timer_trigger': before_trigger}}
    if args.refers_to:
        data = Path(args.refers_to).read_bytes()
        evidence['refers_to'] = {'path': args.refers_to, 'sha256': hashlib.sha256(data).hexdigest(),
                                 'note': 'The original receipt is preserved unchanged; this file appends a verdict.'}
    deadline = time.monotonic() + args.bound_seconds
    unit = before_unit
    while time.monotonic() < deadline and unit.get('InvocationID') == before_unit.get('InvocationID'):
        time.sleep(15)
        unit = show(SERVICE, PROPERTIES)
    if unit.get('InvocationID') == before_unit.get('InvocationID'):
        evidence['verdict'] = {'publication_verified': False, 'reason': 'no_scheduled_run_within_bound'}
    else:
        # a run that is still executing has no exit timestamp yet; wait for it to finish
        while time.monotonic() < deadline + 60 and not unit.get('ExecMainExitTimestamp'):
            time.sleep(3)
            unit = show(SERVICE, PROPERTIES)
        evidence['timer_trigger_after'] = show(TIMER, ('LastTriggerUSec',)).get('LastTriggerUSec')
        evidence['timer_triggered'] = evidence['timer_trigger_after'] != before_trigger
        entries = journal(started.strftime('%Y-%m-%d %H:%M:%S UTC'))
        row = published_row()
        evidence['after'] = {'unit': unit, 'row': row,
                             'journal': [message for owner, message in entries if owner == unit.get('InvocationID')]}
        try:
            evidence['verdict'] = verification.judge(before_row, before_unit.get('InvocationID'), unit, row, entries)
        except verification.VerificationFailure as failure:
            evidence['verdict'] = {'publication_verified': False, 'reason': failure.reason, 'detail': str(failure)}
    evidence['finished_at'] = datetime.now(timezone.utc).isoformat()
    fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(evidence, stream, indent=1, sort_keys=True, default=str)
    print(json.dumps({'output': args.output, 'verdict': evidence['verdict'],
                      'timer_triggered': evidence.get('timer_triggered')}, sort_keys=True, default=str))
    return 0 if evidence['verdict'].get('publication_verified') else 1


if __name__ == '__main__':
    raise SystemExit(main())
