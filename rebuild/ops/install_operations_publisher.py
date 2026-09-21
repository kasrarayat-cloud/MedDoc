#!/usr/bin/env python3
"""Scoped installation of the operations-status publisher units; nothing else is touched.

⚠️ THE WEB PROCESS STRUCTURALLY CANNOT READ THE BACKUP STATE, AND THAT IS NOT RELAXED HERE.
`deploy/quillmd-fresh-admin.service` carries `InaccessiblePaths=… /opt/meddoc-pro/rebuild/.runtime`,
so the whole runtime tree is outside the admin surface's mount namespace, and the state
directories are mode 0700 owned by a different identity with no shared group. A console view that
read `.runtime/backup-alerts/status.json` would report 'unavailable' on a host whose backups are
perfectly healthy — and a panel that is wrong when things are fine is one somebody stops reading.

So the publisher runs AS THE OPERATIONS IDENTITY, the same `claude` that
`quillmd-fresh-backup-alerts.service` already uses, calls the existing aggregator, and writes the
already-redacted report into a table the web process can read. No privilege is granted to the web
identity, no path is opened to it, and no mode is widened.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import pwd
import secrets

try:
    from . import install_backup_schedule as base
except ImportError:
    import install_backup_schedule as base

INSTALLER = 'rebuild/ops/install_operations_publisher.py'
DECLARATION = 'docs/foundation/mutations/20260921-quillmd-operations-publisher.md'
SERVICE = 'quillmd-fresh-operations-publisher.service'
TIMER = 'quillmd-fresh-operations-publisher.timer'
COMMAND = 'rebuild/core/management/commands/publish_operations_status.py'
PUBLISHED_KEY = 'backup'


def scope():
    """Reuse the reviewed filesystem/systemd guards with explicit, narrower unit names."""
    base.INSTALLER = INSTALLER
    base.DECLARATION = DECLARATION
    base.SERVICE, base.TIMER, base.UNITS = SERVICE, TIMER, (SERVICE, TIMER)
    base.LINK = 'timers.target.wants/' + TIMER
    base.MONITOR = base.APP / '.runtime/operations-publisher-20260921'
    base.EVIDENCE = base.APP / '.runtime/operations-publisher-20260921'
    base.SOURCES = (INSTALLER, 'rebuild/ops/install_backup_schedule.py', 'rebuild/ops/managed_helper.py',
                    'rebuild/ops/backup_alerts.py', COMMAND, 'rebuild/core/models.py',
                    DECLARATION, *('rebuild/deploy/' + name for name in base.UNITS))


def root_action(payload):
    """Called only inside the fixed, reviewed root helper; no caller-supplied paths."""
    base.require(os.getuid() == 0 and set(payload) == {'action', 'hashes', 'baseline', 'commit'},
                 'Invalid helper input.')
    base.require(payload['action'] in ('install', 'activate', 'disable')
                 and set(payload['hashes']) == set(base.SOURCES), 'Invalid helper scope.')
    for relative, expected in payload['hashes'].items():
        path = base.ROOT / relative
        base.require(path.resolve() == path and base.digest(path) == expected, 'Reviewed source drift.')
    base.require(base.baseline() == payload['baseline'], 'Host changed after baseline.')
    result = {'action': payload['action'], 'success': False, 'commit': payload['commit'],
              'started_at': datetime.now(timezone.utc).isoformat(), 'new_publisher_units_only': True}
    try:
        if payload['action'] == 'install':
            base.require_absent(payload['baseline'])
            for name in base.UNITS:
                fd = os.open(base.SYSTEMD / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
                with os.fdopen(fd, 'wb') as stream:
                    os.fchmod(stream.fileno(), 0o644)
                    os.fchown(stream.fileno(), 0, 0)
                    stream.write((base.APP / 'deploy' / name).read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
            base.command(['systemctl', 'daemon-reload'])
            base.require_installed(payload['hashes'])
        elif payload['action'] == 'activate':
            base.require_installed(payload['hashes'])
            base.require(base.LINK not in payload['baseline']['units'], 'Timer already enabled.')
            # One publication, proved before the timer is allowed to repeat it.
            base.command(['systemctl', 'start', SERVICE], timeout=120)
            state = base.command(['systemctl', 'show', SERVICE, '--property=Result,ExecMainStatus']).decode()
            base.require(dict(x.split('=', 1) for x in state.splitlines()) ==
                         {'Result': 'success', 'ExecMainStatus': '0'},
                         'The first operations-status publication did not complete successfully.')
            base.command(['systemctl', 'enable', TIMER])
            base.command(['systemctl', 'start', TIMER])
            base.require(base.command(['systemctl', 'is-active', TIMER]).strip() == b'active'
                         and base.command(['systemctl', 'is-enabled', TIMER]).strip() == b'enabled',
                         'Publisher timer activation failed.')
        else:
            base.require_installed(payload['hashes'])
            base.command(['systemctl', 'disable', '--now', TIMER])
            base.require(base.command(['systemctl', 'show', TIMER, '--property=ActiveState', '--value']).strip()
                         == b'inactive', 'Publisher timer rollback failed.')
        after = base.baseline()
        if payload['action'] == 'disable':
            prior = dict(payload['baseline'], units=dict(payload['baseline']['units']))
            prior['units'].pop(base.LINK, None)
            base.compare_baseline(prior, after, payload['hashes'], False)
            base.require(base.LINK not in after['units'], 'Timer enablement survived rollback.')
        else:
            base.compare_baseline(payload['baseline'], after, payload['hashes'],
                                  payload['action'] == 'activate')
        result.update(success=True, baseline_preserved=True, after=after)
    except Exception:
        result['error'] = 'Scoped publisher installation or verification failed; inspect retained evidence.'
        if payload['action'] == 'activate':
            try:
                base.command(['systemctl', 'disable', '--now', TIMER])
                result['timer_stopped_disabled'] = True
            except Exception:
                result['timer_stopped_disabled'] = False
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    return result


def published_row():
    """Read the published row back through the application's own model, as the operator."""
    import subprocess
    code = ("import django,os,json;os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings');"
            "django.setup();from core.models import ServiceHealth;"
            "r=ServiceHealth.objects.filter(key=" + repr(PUBLISHED_KEY) + ").first();"
            "print(json.dumps(None if r is None else {'key':r.key,'condition':r.condition,"
            "'severity':r.severity,'healthy':r.healthy,'computed_at':r.computed_at.isoformat(),"
            "'published_at':r.published_at.isoformat(),'interval':r.expected_interval_seconds,"
            "'payload_keys':sorted(r.payload)}))")
    done = subprocess.run([str(base.APP / '.venv/bin/python'), '-B', '-c', code], cwd=base.APP,
                          capture_output=True, timeout=120)
    base.require(done.returncode == 0, 'Could not read the published operations status back.')
    return json.loads(done.stdout.decode())


def verify_publication(before):
    """A real row, written by this act, recently, and carrying no clinical content."""
    row = published_row()
    base.require(row is not None, 'No operations status was published.')
    base.require(before is None or row['published_at'] != before['published_at'],
                 'The published row was not refreshed by this act.')
    published = datetime.fromisoformat(row['published_at'])
    age = (datetime.now(timezone.utc) - published).total_seconds()
    base.require(0 <= age <= 900, 'The published operations status is not recent.')
    base.require(row['interval'] >= 60, 'Published expected interval is below the schema floor.')
    base.require(not any(key in row['payload_keys'] for key in
                         ('patient', 'encounter', 'note', 'transcript', 'clinical')),
                 'Published payload names a clinical field; publication refused.')
    return row


def main():
    scope()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--action', choices=('install', 'activate', 'disable'), default='install')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    base.require(os.getuid() == pwd.getpwnam('claude').pw_uid, 'Use the authorized project operator.')
    os.umask(0o077)
    hashes = base.reviewed_source(args.expected_commit, mutation=args.execute)
    before = base.baseline()
    if args.action == 'install':
        base.require_absent(before)
    else:
        base.require_installed(hashes)
    published_before = published_row()
    if not args.execute:
        print(json.dumps({'plan_verified': True, 'action': args.action, 'commit': args.expected_commit,
                          'host_mutation': False, 'application_restart': False,
                          'already_published': published_before is not None}))
        return 0
    base.private_directory(base.EVIDENCE, create=True)
    name = ('publisher-units-' + args.action + '-'
            + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + secrets.token_hex(4))
    payload = {'action': args.action, 'hashes': hashes, 'baseline': before, 'commit': args.expected_commit}
    base.write_private(base.EVIDENCE / (name + '-before.json'), payload)
    body = ('import argparse,datetime,hashlib,json,os,pathlib,pwd,re,secrets,stat,subprocess,sys\n'
            'os.chroot("/host");os.chdir("/")\n'
            'sys.path.insert(0,' + repr(str(base.APP / 'ops')) + ')\n'
            'files=' + repr(hashes) + '\n'
            'assert all(hashlib.sha256((pathlib.Path(' + repr(str(base.ROOT))
            + ')/p).read_bytes()).hexdigest()==h for p,h in files.items())\n'
            'sys.dont_write_bytecode=True\n'
            'import install_operations_publisher as operation\n'
            'operation.scope()\n'
            'print(json.dumps(operation.root_action(' + repr(payload) + '),sort_keys=True))\n')
    try:
        child = base.managed_helper_run(base.helper_command(), input=body.encode(), timeout=200)
        result = json.loads(child.stdout) if child.returncode == 0 else {'success': False, 'error': 'helper_failed'}
        result.update(helper_container=getattr(child, 'helper_container', None),
                      helper_cleanup_complete=getattr(child, 'helper_cleanup_complete', False))
    except Exception as error:
        result = {'success': False, 'error': 'helper_outcome_unconfirmed',
                  'helper_reason': getattr(error, 'reason', 'transport_failed'),
                  'helper_container': getattr(error, 'container_name', None),
                  'helper_initial_reason': getattr(error, 'operation_reason', None),
                  'helper_cleanup_complete': getattr(error, 'cleanup_complete', False)}
    result['hashes'] = hashes
    if result.get('success') is True and args.action == 'activate':
        # Proved from the operator side, through the application's own model, not from the helper.
        result['publication'] = verify_publication(published_before)
    base.write_private(base.EVIDENCE / (name + '-result.json'), result)
    print(json.dumps({'success': result.get('success') is True, 'action': args.action,
                      'evidence': str(base.EVIDENCE / (name + '-result.json')),
                      'publication': result.get('publication')}))
    return 0 if result.get('success') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
