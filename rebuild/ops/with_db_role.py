#!/usr/bin/env python3
"""Run Django management with separately stored migrator/backup credentials."""
import argparse
import json
import os
from pathlib import Path
import sys

try:
    from .backup_restore import read_private, require
except ImportError:
    from backup_restore import read_private, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--role', choices=['migrator', 'backup'], default='migrator')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    data = json.loads(read_private(args.credentials, 16384))
    require(data['database'] == 'quillmd_fresh', 'Wrapper is restricted to the fresh database.')
    source = Path(args.source).absolute()
    require(source.resolve() == source and (source / 'manage.py').is_file(), 'Verified source root required.')
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    require(command and command[0] in ('migrate', 'showmigrations', 'check'),
            'Only migration/check management commands are allowed; no worker or provider action.')
    role = data['roles'][args.role]
    env = dict(os.environ, QUILLMD_DB_NAME='quillmd_fresh', QUILLMD_DB_USER=role['name'],
               QUILLMD_DB_PASSWORD=role['password'], QUILLMD_DB_HOST='127.0.0.1', QUILLMD_DB_PORT='55438')
    env['PGOPTIONS'] = '-c role=quillmd_owner' if args.role == 'migrator' else ''
    os.execve(sys.executable, [sys.executable, str(source / 'manage.py'), *command], env)


if __name__ == '__main__':
    main()
