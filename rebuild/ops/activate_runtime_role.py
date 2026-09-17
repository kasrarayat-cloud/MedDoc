#!/usr/bin/env python3
"""Switch only the private fresh application's DB login after coordinated role setup."""
import argparse
import json
import os
from pathlib import Path
import re

from dotenv import dotenv_values
import psycopg
from backup_restore import private_dir, read_private, require, run, write_private, inspect_container

APP = Path('/opt/meddoc-pro/rebuild')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    path = Path(args.credentials).absolute()
    require(path.parent == APP / '.runtime/db-role-secrets', 'Use the inaccessible role-secret directory.')
    data = json.loads(read_private(path, 16384))
    container = inspect_container('quillmd-fresh-postgres')
    require(data['database'] == 'quillmd_fresh' and data['container_id'] == container['Id'], 'Fresh target mismatch.')
    runtime = data['roles']['runtime']
    require(runtime['name'] == 'quillmd_runtime' and len(runtime['password']) >= 40, 'Invalid runtime credentials.')
    env = APP / '.env'
    original = read_private(env, 128 * 1024)
    bootstrap = read_private(APP / '.runtime/postgres.env', 128 * 1024)
    old = dotenv_values(env)
    with psycopg.connect(dbname='quillmd_fresh', user=runtime['name'], password=runtime['password'],
                          host='127.0.0.1', port=55438, connect_timeout=5) as connection:
        row = connection.execute('SELECT current_user,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        require(row == ('quillmd_runtime', False, False, False, False), 'Runtime privilege proof failed.')
        connection.execute('SELECT count(*) FROM core_user').fetchone()
    if not args.execute:
        print('Verified constrained runtime login and preserved bootstrap file; environment unchanged.')
        return
    require(Path(os.environ.get('RULED_MUTATION_DECLARATION', '')).name ==
            '20260917-quillmd-private-beta-update.md'
            and re.fullmatch('[a-f0-9]{40}', os.environ.get('RULED_MUTATION_DECL_COMMIT', '')),
            'Committed coordinated role activation declaration required.')
    for kind in ('doctor', 'admin', 'worker'):
        require(run(['systemctl', 'show', 'quillmd-fresh-' + kind + '.service',
                     '--property=ActiveState', '--value']).strip() == b'inactive', 'Stop private services first.')
        policy = run(['systemctl', 'show', 'quillmd-fresh-' + kind + '.service', '--property=InaccessiblePaths', '--value'])
        require(b'/run/docker.sock' in policy and b'/db-role-secrets' in policy and b'/backup-secrets' in policy,
                'Install and reload the secret-isolation unit policy before runtime activation.')
    replacements = {'QUILLMD_DB_USER': runtime['name'], 'QUILLMD_DB_PASSWORD': runtime['password']}
    lines = original.decode().splitlines()
    for key in replacements:
        require(sum(line.startswith(key + '=') for line in lines) <= 1, 'Duplicate DB environment key.')
    lines = [line for line in lines if not any(line.startswith(key + '=') for key in replacements)]
    lines += [key + '=' + value for key, value in replacements.items()]
    pending = APP / '.runtime/db-role-secrets/runtime-env.pending'
    write_private(pending, ('\n'.join(lines) + '\n').encode())
    require(env.read_bytes() == original, 'Environment changed concurrently.')
    pending.replace(env)
    require((APP / '.runtime/postgres.env').read_bytes() == bootstrap, 'Bootstrap credentials changed.')
    updated = dotenv_values(env)
    require(all(updated.get(k) == v for k, v in old.items() if k not in replacements), 'Unrelated configuration changed.')
    print('Activated constrained runtime DB credentials; unrelated environment and bootstrap retained. Services remain stopped.')


if __name__ == '__main__':
    main()
