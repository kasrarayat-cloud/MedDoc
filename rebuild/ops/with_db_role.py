#!/usr/bin/env python3
"""Run Django management with separately stored migrator/backup credentials.

`--profile private` (the default) is the fresh synthetic database, exactly as before. `--profile
production` takes every connection value from the reviewed production record (deployment_profile.py):
the pinned RDS endpoint, port, database name, role names and verify-full TLS with the pinned CA bundle.
Nothing about the target comes from the command line or the operator's environment.
"""
import argparse
import json
import os
from pathlib import Path
import sys

try:
    from .backup_restore import read_private, require
except ImportError:
    from backup_restore import read_private, require


def _production_target(data, role_kind):
    try:
        from . import deployment_profile
    except ImportError:
        import deployment_profile
    try:
        profile = deployment_profile.load_production()
    except deployment_profile.ProfileError as exc:
        raise RuntimeError('Production profile refused: ' + str(exc)) from None
    require(data.get('profile') == 'production' and data.get('database') == profile.database_name,
            'Wrapper credentials belong to another target.')
    require(set(data.get('roles', {})) == {'migrator', 'backup'}
            and all(data['roles'][kind].get('name') == profile.roles[kind] for kind in ('migrator', 'backup')),
            'Wrapper credentials do not name the reviewed production roles.')
    values = {'QUILLMD_DB_NAME': profile.database_name, 'QUILLMD_DB_HOST': profile.database_host,
              'QUILLMD_DB_PORT': str(profile.database_port), 'PGSSLMODE': profile.sslmode,
              'PGSSLROOTCERT': str(profile.ca_bundle), 'QUILLMD_DEPLOYMENT_PROFILE': 'production'}
    values['PGOPTIONS'] = '-c role=' + profile.roles['owner'] if role_kind == 'migrator' else ''
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--role', choices=['migrator', 'backup'], default='migrator')
    parser.add_argument('--profile', choices=['private', 'production'], default='private')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    data = json.loads(read_private(args.credentials, 16384))
    if args.profile == 'private':
        require(data['database'] == 'quillmd_fresh', 'Wrapper is restricted to the fresh database.')
    source = Path(args.source).absolute()
    require(source.resolve() == source and (source / 'manage.py').is_file(), 'Verified source root required.')
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    # import_terminology writes tens of thousands of rows and makes no provider call: it reads a
    # local file whose hash it verifies. Without it here, the largest write in the programme would
    # be the only one running as the database superuser.
    require(command and command[0] in ('migrate', 'showmigrations', 'check', 'import_terminology'),
            'Only migration, check and verified terminology import commands are allowed; no worker or provider action.')
    if args.profile == 'production':
        target = _production_target(data, args.role)
    role = data['roles'][args.role]
    if args.profile == 'private':
        env = dict(os.environ, QUILLMD_DB_NAME='quillmd_fresh', QUILLMD_DB_USER=role['name'],
                   QUILLMD_DB_PASSWORD=role['password'], QUILLMD_DB_HOST='127.0.0.1', QUILLMD_DB_PORT='55438')
        env['PGOPTIONS'] = '-c role=quillmd_owner' if args.role == 'migrator' else ''
    else:
        # No inherited libpq setting (PGHOST, PGSERVICE, PGSSLMODE=disable, ...) may redirect or weaken the target.
        env = {name: value for name, value in os.environ.items() if not name.startswith('PG')}
        env.update(target, QUILLMD_DB_USER=role['name'], QUILLMD_DB_PASSWORD=role['password'])
    os.execve(sys.executable, [sys.executable, str(source / 'manage.py'), *command], env)


if __name__ == '__main__':
    main()
