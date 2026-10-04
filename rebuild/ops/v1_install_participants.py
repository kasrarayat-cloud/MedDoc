"""Bounded recovery of ONLY the existing private operational timers.

No installation, unit rewrite, message, provider, database or source operation.
The normal adapter stores the prior active set durably before pausing timers.
The independent watchdog restores that exact set if the owning process dies.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from . import managed_helper
from .v1_private_install_adapter import require

TIMERS = ('quillmd-fresh-backup.timer', 'quillmd-fresh-offsite.timer', 'quillmd-fresh-backup-alerts.timer')
PRIVATE_UNITS = tuple('quillmd-fresh-' + name + '.service' for name in ('doctor', 'admin', 'worker'))
STATE_ROOT = Path('/opt/meddoc-pro/rebuild/.runtime/v1-private-install')


def action(operation, units, *, directory):
    require(operation in ('start', 'stop') and isinstance(units, tuple)
            and units and set(units) <= set(TIMERS + PRIVATE_UNITS), 'Fixed private participant action required.')
    require(directory.resolve() == directory and directory.parent == STATE_ROOT, 'Fixed activation evidence required.')
    code = ('import os,subprocess\nos.chroot("/host");os.chdir("/")\nsubprocess.run('
            + repr(['systemctl', operation, *units]) + ',check=True)\n')
    return managed_helper.run_helper(['/usr/bin/docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none',
        '--network=none', '--pid=host', '--mount', 'type=bind,src=/,dst=/host,readonly', managed_helper.IMAGE,
        'python', '-B', '-'], input=code.encode(), timeout=200, failure_directory=directory)


def start_identity(pid):
    try:
        return Path('/proc/' + str(pid) + '/stat').read_text().rsplit(') ', 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def validate(record):
    require(set(record) == {'target', 'pid', 'start', 'prior_active'}
            and re.fullmatch('[a-f0-9]{40}', record['target']) and type(record['pid']) is int and record['pid'] > 0
            and isinstance(record['start'], str) and record['start'].isdigit()
            and isinstance(record['prior_active'], list) and len(set(record['prior_active'])) == len(record['prior_active'])
            and set(record['prior_active']) <= set(TIMERS), 'Invalid private participant recovery record.')
    return record


def spawn(directory, record, *, source):
    validate(record)
    require(directory == STATE_ROOT / record['target'], 'Recovery target/path differs.')
    code = ('import sys\nsys.path.insert(0,' + repr(str(source / 'rebuild')) + ')\n'
            'from ops.v1_install_participants import watch\nwatch(' + repr(str(directory)) + ')\n')
    return subprocess.Popen([sys.executable, '-B', '-c', code], start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def watch(directory):
    from .backup_restore import read_private, write_private
    directory = Path(directory)
    require(directory.parent == STATE_ROOT and directory.resolve() == directory, 'Invalid recovery evidence directory.')
    marker = directory / 'timer-pause.json'
    record = validate(json.loads(read_private(marker, 16384)))
    require(directory.name == record['target'], 'Recovery directory targets another release.')
    # Main execution has a 1,500-second absolute deadline. This independent
    # watchdog lives for 1,800 seconds; it never silently extends the transaction.
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline and not (directory / 'timers-restored.json').exists():
        if start_identity(record['pid']) != record['start']:
            action('stop', PRIVATE_UNITS, directory=directory)
            if record['prior_active']:
                action('start', tuple(record['prior_active']), directory=directory)
            write_private(directory / 'timers-recovered-after-owner-exit.json',
                          json.dumps({'restored': record['prior_active'], 'private_surfaces_stopped': True}).encode())
            return
        time.sleep(5)
