"""Test driver (not a test module): the stage `plan` report and pricing for a SYNTHETIC campaign — a declaration and an
optional amendment committed in a temporary checkout, and a temporary ledger — in a fresh process with Django configured
the way `sonnet5_stages.plan` configures it: no credential, no network, no database, no environment file.

    python -B ops/tests/amendment_plan_driver.py <spec.json>

spec: {"declaration", "repository", "amendment" (path or null), "root", "state", "stage", "settings" (extra
environment, e.g. a changed rate)}. Prints {"report": …} or {"refused": "<reason>"}; exit 0 either way.
"""
import json
import os
import socket
import sys
from pathlib import Path

REBUILD = Path(__file__).resolve().parents[2]


def _deny(*_args, **_kwargs):
    raise AssertionError('the plan driver never opens a socket')


def main(spec_path):
    socket.socket.connect = _deny
    socket.socket.connect_ex = _deny
    socket.create_connection = _deny
    spec = json.loads(Path(spec_path).read_text())
    sys.path.insert(0, str(REBUILD))
    sys.path.insert(0, str(REBUILD / 'ops'))
    from ops import provider_campaign as pc
    from ops import sonnet5_qa as sq
    from ops import sonnet5_stages as st
    if sq.env_file_present():
        raise SystemExit('refusing: the checkout carries rebuild/.env')
    try:
        declaration = pc.declared(spec['declaration'], repository=spec['repository'], out=sys.stderr)
        amendment = (pc.declared_amendment(spec['amendment'], declaration, out=sys.stderr)
                     if spec.get('amendment') else None)
    except pc.Refused as refused:
        print(json.dumps({'refused': str(refused), 'at': 'declaration'}))
        return 0
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False           # (and the checkout has no rebuild/.env: checked above)
    os.environ.pop('QUILLMD_ENV_MANAGED', None)
    os.environ.update({'QUILLMD_SECRET_KEY': 'amendment-plan-driver-placeholder', 'QUILLMD_DB_PASSWORD': 'unused',
                       'QUILLMD_DB_NAME': sq.DATABASE['name'], 'QUILLMD_DB_USER': sq.DATABASE['user'],
                       'QUILLMD_DB_HOST': '/nonexistent-plan-socket-dir', 'QUILLMD_DB_PORT': '1',
                       'QUILLMD_STATE_DIR': spec['state'], 'QUILLMD_ADMIN_SITE': '0',
                       'DJANGO_SETTINGS_MODULE': 'quillmd.settings', **pc.declared_settings(declaration),
                       **sq.PRICE_SETTINGS, **st.STAGE_FLAGS[spec['stage']], **(spec.get('settings') or {})})
    import django
    django.setup()
    from django.db.backends.base import base as dbbase

    def no_database(self, *args, **kwargs):
        raise AssertionError('the plan driver never touches a database')
    dbbase.BaseDatabaseWrapper.ensure_connection = no_database
    if spec.get('drift_default'):
        # (test only: the compiler's DEFAULT-path maximum moves by $0.000001 while every pricing version stays the same
        # — the frozen maxima must still refuse it, amendment or not)
        from decimal import Decimal
        from core import generation
        real = generation.maximum_cost

        def drifted(notes, fields, config=None, **kwargs):
            value = real(notes, fields, config, **kwargs)
            return value if (config or {}).get('ordinary_field_contract') else value + Decimal('0.000001')
        generation.maximum_cost = drifted
    try:
        report = st.plan_report(spec['stage'], declaration, Path(spec['root']), spec['state'], amendment)
    except pc.Refused as refused:
        print(json.dumps({'refused': str(refused), 'at': 'plan'}))
        return 0
    print(json.dumps({'report': report}, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
