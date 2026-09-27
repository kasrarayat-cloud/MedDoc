#!/usr/bin/env python3
"""Read-only check of a RESTORED production database against a RESTORED state volume (restore drill).

A restore is not trusted because AWS reported it complete. This connects to a DRILL RDS instance
restored from production (point in time or snapshot), never to the live one, as the read-only backup
role over verify-full TLS with the profile's pinned CA bundle, and checks what the private
restore-check (backup_restore.py) already requires of a synthetic restore:

- every release-bound integrity trigger has its expected table, event, function body and enabled
  state, with no additional custom core trigger, and the count agrees with the selected release;
- backup_restore.INVARIANTS are all zero (wallet bounds, the 1.5x charge rule, encounter scope,
  held reservations);
- every file the database references (backup_restore.FILE_QUERIES) exists under the restored
  volume's files/ as a regular file inside it and, where the database records a sha256, has exactly
  those bytes. State files are write-once, so a volume snapshot taken AT OR AFTER the database's
  restore point must contain every referenced file; a missing one means the pairing is wrong.

It prints counts only: no row content, no file path, no identifier. The drill instance and volume
names are fixed patterns (quillmd-production-drill-<YYYYMMDD>t<HHMM>, /mnt/quillmd-drill-<same>),
and the live endpoint and live state root are refused, so the tool cannot be pointed at production.

    python3 ops/production_restore_check.py --database-host <drill endpoint> \
        --state-root /mnt/quillmd-drill-20261101t0300 --credentials <role credential file> \
        --expected-triggers 39
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

try:
    from . import backup_restore as backup
    from . import deployment_profile
    from . import integrity_contract
except ImportError:
    import backup_restore as backup
    import deployment_profile
    import integrity_contract

DRILL_STAMP = r'[0-9]{8}t[0-9]{4}'
TRIGGERS = integrity_contract.CATALOG
TABLES = '''SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname'''


class CheckError(RuntimeError):
    """Contains only a fixed label."""


def require(condition, label):
    if not condition:
        raise CheckError(label)


def drill_target(profile, host, state_root):
    """The drill endpoint and mount, refusing anything that is, or could be, the live system."""
    require(host != profile.database_host, 'live_database')
    pattern = (r'quillmd-production-drill-(' + DRILL_STAMP + r')\.[a-z0-9]{6,63}\.'
               + re.escape(profile.region) + r'\.rds\.amazonaws\.com')
    match = re.fullmatch(pattern, host or '')
    require(match is not None, 'drill_database_host')
    state = Path(state_root)
    require(str(state) == '/mnt/quillmd-drill-' + match.group(1) and state != profile.state_root, 'drill_state_root')
    require(state.is_dir() and not state.is_symlink() and state.resolve() == state, 'drill_state_root')
    return host, state


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def check(query, state_root, expected_triggers):
    """Run every check through `query(sql) -> rows`; return a counts-only report."""
    triggers = query(TRIGGERS)
    trigger_report = integrity_contract.assess(triggers, query(integrity_contract.CONTEXT), expected_triggers)
    invariants = {name: query(statement)[0][0] for name, statement in backup.INVARIANTS.items()}
    references = {}
    for _, statement in backup.FILE_QUERIES + [('preserved','SELECT storage_key,sha256 FROM core_preservedfile')]:
        for relative, expected in query(statement):
            backup.safe_relative(relative)
            previous = references.get(relative, '')
            require(not (previous and expected and previous != expected), 'conflicting_file_hashes')
            references[relative] = expected or previous
    files_root = Path(state_root) / 'files'
    missing = mismatched = 0
    for relative, expected in sorted(references.items()):
        path = files_root / relative
        try:
            info = path.lstat()
        except OSError:
            missing += 1
            continue
        if not stat.S_ISREG(info.st_mode) or path.resolve() != path or not path.is_relative_to(files_root):
            missing += 1
        elif expected and _file_sha256(path) != expected:
            mismatched += 1
    tables = [row[0] for row in query(TABLES)]
    rows = sum(query('SELECT count(*) FROM public."%s"' % name.replace('"', '""'))[0][0] for name in tables)
    report = {
        'triggers': trigger_report,
        'invariants': {'violations': sum(invariants.values()), 'checked': len(invariants),
                       'passed': not any(invariants.values())},
        'files': {'referenced': len(references), 'missing': missing, 'hash_mismatched': mismatched,
                  'passed': missing == 0 and mismatched == 0},
        'tables': len(tables), 'rows': rows,
    }
    report['passed'] = all(report[name]['passed'] for name in ('triggers', 'invariants', 'files'))
    return report


def connect(profile, host, credentials):
    import psycopg
    data = json.loads(backup.read_private(credentials, 16384))
    require(data.get('profile') == 'production' and data.get('database') == profile.database_name
            and data.get('roles', {}).get('backup', {}).get('name') == profile.roles['backup'], 'credentials')
    role = data['roles']['backup']
    return psycopg.connect(host=host, port=profile.database_port, dbname=profile.database_name, user=role['name'],
                           password=role['password'], sslmode='verify-full', sslrootcert=str(profile.ca_bundle),
                           options='-c default_transaction_read_only=on', connect_timeout=10)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--database-host', required=True)
    parser.add_argument('--state-root', required=True)
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--expected-triggers', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        profile = deployment_profile.load_production()
        host, state = drill_target(profile, args.database_host, args.state_root)
        with connect(profile, host, args.credentials) as connection:
            report = check(lambda text: connection.execute(text).fetchall(), state, args.expected_triggers)
    except Exception as exc:  # noqa: BLE001 - only a fixed label or a class name is ever printed
        label = str(exc) if isinstance(exc, (CheckError, deployment_profile.ProfileError)) else type(exc).__name__
        print(json.dumps({'passed': False, 'refused': label}), file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
