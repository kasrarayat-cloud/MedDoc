#!/usr/bin/env python3
"""Preserving private activation of the combined administration console and doctor/form release.

One act installs both reviewed candidates, because the source advance moves both public
assets and a single source-bound static transition must carry them together. Default is
read-only. --execute runs only from the clean reviewed worktree, through the committed
declaration. No provider, payment, email, backup, restore or renewal call is made.

The inherited entry point is the qualified typed/voice adapter, which already owns the
public-asset transition. Only two things are added here: the exact additive service-health
migration, and a preservation comparison that tolerates that migration and nothing else.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[1]
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
SELF = 'scripts/activate-admin-console.py'
DRIVER = 'scripts/activate-typed-voice.py'
DRIVER_SHA256 = 'ef4c050862b52d29b2dc62a0d60bc183354f50d8e41c261f9137f1f79bded4bd'
DECL = 'docs/foundation/mutations/20260921-quillmd-admin-console-integration.md'
EVIDENCE = PRIVATE / 'admin-console-20260921'
# The baseline is the SERVED release, not shared main: main already carries the merged
# doctor/form work (PR #1252) that this act installs for the first time.
BASELINE = 'e66d84abbb4cda663dc4489d175c71d477572fca'
RUNNING_RELEASE = BASELINE
MIGRATION = '0018_servicehealth'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
MIGRATION_SHA256 = 'f1382977ec80fda51f39bdc6ae329efcce0c7398ee0d864ceefbd74507267f9c'
PREVIOUS_MIGRATION = '0017_reconciliation_evidence_kind'
NEW_TABLE = 'core_servicehealth'
NEW_COLUMNS = ('id', 'created_at', 'key', 'condition', 'severity', 'healthy', 'action',
               'payload', 'computed_at', 'published_at', 'expected_interval_seconds')
CAPTURE_RUN = '20260921T043001Z-0a6f66da'
CAPTURE_SOURCE = '08e40870f18ca4e79b0cc2b27d6b09ba48f911a7'
CAPTURE_MANIFEST_SHA256 = 'ac714b19363a66294d35cfde0d4b1de62de2ab9db1916b67f466f9e41bd19c82'
OPS_TEST = 'rebuild/ops/test_admin_console_activation.py'
# The last transition that installed public assets, and its receipt, pinned by content.
PRIOR_TRANSITION = 'typed-voice-20260921/typed-voice-resume-b6b40b02.json'
PRIOR_TRANSITION_SHA256 = '757d43c7da60db56ea8f5030757e7bf95db4f37e5677cae7648a114c4b04d13e'
SCREENSHOTS = 'docs/rebuild/admin-console-screenshots-20260921/'
RESULT_PATTERN = r'typed-voice-activation-[a-zA-Z0-9_-]+\.json'
RENAMED_PATTERN = r'admin-console-activation-[a-zA-Z0-9_-]+\.json'
RUNTIME_ALLOWED = {
    SELF, OPS_TEST, MIGRATION_PATH,
    'rebuild/admin-console-browser.mjs',
    'rebuild/core/admin_console.py',
    'rebuild/core/admin_views.py',
    'rebuild/core/context.py',
    'rebuild/core/field_location.py',
    'rebuild/core/forms.py',
    'rebuild/core/jobs.py',
    'rebuild/core/management/commands/publish_operations_status.py',
    'rebuild/core/management/commands/seed_admin_demo.py',
    'rebuild/core/models.py',
    'rebuild/core/templatetags/__init__.py',
    'rebuild/core/templatetags/console.py',
    'rebuild/core/tests/test_admin_console.py',
    'rebuild/core/tests/test_admin_evidence.py',
    'rebuild/core/tests/test_mapping_review_clarity.py',
    'rebuild/core/tests/test_repeat_request_disclosure.py',
    'rebuild/core/views.py',
    'rebuild/documents/engine.py',
    'rebuild/documents/test_unmapped_areas.py',
    'rebuild/quillmd/settings.py',
    'rebuild/quillmd/urls.py',
    'rebuild/static/app.css',
    'rebuild/static/app.js',
    'rebuild/stripe-sandbox-verify.mjs',
    'rebuild/templates/admin_account.html',
    'rebuild/templates/admin_dashboard.html',
    'rebuild/templates/admin_organizations.html',
    'rebuild/templates/admin_services.html',
    'rebuild/templates/audit.html',
    'rebuild/templates/base.html',
    'rebuild/templates/billing.html',
    'rebuild/templates/financial_detail.html',
    'rebuild/templates/integrations.html',
    'rebuild/templates/template_detail.html',
    'scripts/ci/verify-fresh.sh',
}
REQUIRED = {SELF, DECL, OPS_TEST, MIGRATION_PATH, 'rebuild/core/admin_console.py',
            'rebuild/core/admin_views.py', 'rebuild/core/models.py',
            'rebuild/static/app.css', 'rebuild/static/app.js'}
STATE = {'migration_checks': 0, 'migration_performed': False}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class _RenamedReceiptRe:
    """Rename only the inherited receipt-name pattern; every other regex stays the module's own.

    The inherited main hard-codes the typed/voice receipt name. Renaming the one pattern is
    preferred over copying a 160-line main that would then drift from the qualified original.
    """

    def __getattr__(self, name):
        return getattr(re, name)

    def fullmatch(self, pattern, string, *args, **kwargs):
        if pattern == RESULT_PATTERN:
            pattern = RENAMED_PATTERN
        return re.fullmatch(pattern, string, *args, **kwargs)


_driver_bytes = (SOURCE / DRIVER).read_bytes()
require(sha(_driver_bytes) == DRIVER_SHA256, 'Qualified typed/voice activation driver changed.')
require(RESULT_PATTERN in _driver_bytes.decode(),
        'Inherited receipt-name pattern is absent; the receipt rename would be inert.')
t = types.ModuleType('_admin_console_activation_driver')
t.__file__ = __file__
sys.modules[t.__name__] = t
exec(compile(_driver_bytes, str(SOURCE / DRIVER), 'exec'), t.__dict__)
a, b = t.a, t.b
_inherited_verify_source = t.verify_source
_inherited_snapshot = t.snapshot
_inherited_receipt = a.receipt


def migration_names(plan):
    """Parse the plan with the qualified grammar, for the pre-advance state it cannot describe."""
    rows = [re.fullmatch(r'\[([X ])\][ \t]+([a-z_][a-z_0-9]*\.[a-z_0-9]+)', line.strip())
            for line in plan.splitlines() if line.strip()]
    require(rows and all(rows), 'Migration plan cannot be parsed completely.')
    names = [row[2] for row in rows]
    require(len(names) == len(set(names)), 'Repeated migration in the plan.')
    require([row[2] for row in rows if row[1] != 'X'] == [], 'Pending migration before the source advance.')
    return names


def verify_migrations(old, plan):
    """First call is the pre-advance state; the second applies the one declared migration."""
    STATE['migration_checks'] += 1
    present = (ROOT / MIGRATION_PATH).exists()
    frontier = ["SELECT name FROM django_migrations WHERE app='core' ORDER BY id DESC LIMIT 1"]
    if STATE['migration_checks'] == 1:
        require(not present, 'Shared source already carries the new migration before the advance.')
        require('core.' + MIGRATION not in migration_names(plan), 'Unexpected new migration in the pre-activation plan.')
        require(b.output(old.PSQL + frontier) == PREVIOUS_MIGRATION, 'Unexpected migration frontier before activation.')
        require(b.output(old.PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='"
                                     + PREVIOUS_MIGRATION + "'"]) == '1', 'Exactly one existing 0017 history row required.')
        require(b.output(old.PSQL + ["SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename='"
                                     + NEW_TABLE + "'"]) == '0', 'The declared new table already exists.')
        return
    require(STATE['migration_checks'] == 2 and present and not STATE['migration_performed'],
            'Unexpected additional migration verification.')
    b.verify_migration_plan(plan, applied=False)
    b.validate_migration((ROOT / MIGRATION_PATH).read_bytes())
    require(b.output(old.PSQL + frontier) == PREVIOUS_MIGRATION, 'Migration frontier moved before the declared apply.')
    b.run(b.management('migrate', 'core', MIGRATION, '--noinput'), cwd=APP,
          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    STATE['migration_performed'] = True
    b.verify_migration_plan(b.output(b.management('showmigrations', '--plan'), cwd=APP), applied=True)
    for name, count in ((MIGRATION, '1'), (PREVIOUS_MIGRATION, '1')):
        require(b.output(old.PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='"
                                     + name + "'"]) == count, 'Unexpected migration history for ' + name + '.')
    require(b.output(old.PSQL + ['SELECT count(*) FROM "' + NEW_TABLE + '"']) == '0',
            'The declared new table must be created empty.')


def rows(old):
    """Full per-table fingerprints, excluding ONLY the two declared additions.

    The new table is skipped and its history row filtered out, so the before and after
    snapshots describe the identical universe and compare with exact equality. Nothing else
    is projected away: no other difference has an excuse available to it.
    """
    result = {}
    for name in old.tables():
        if name == NEW_TABLE:
            continue
        where = " WHERE NOT (app='core' AND name='" + MIGRATION + "')" if name == 'django_migrations' else ''
        data = subprocess.check_output(
            old.PSQL + ['COPY (SELECT (to_jsonb(t))::text AS value FROM "' + name + '" t' + where
                        + ' ORDER BY value) TO STDOUT'], timeout=600)
        result[name] = {'sha256': sha(data), 'rows': len(data.splitlines())}
    return result


def snapshot(modules, helper):
    result = _inherited_snapshot(modules, helper)
    present = NEW_TABLE in result['tables']
    result['new_table_rows'] = int(b.output(modules['old'].PSQL
                                            + ['SELECT count(*) FROM "' + NEW_TABLE + '"'])) if present else None
    return result


IDENTICAL = ('rows', 'clinical', 'catalog', 'storage', 'static', 'unit_files',
             'shared_configs', 'preserved_operations')
TABLE_OF = {'schema': lambda row: row['table_name'], 'constraints': lambda row: row[0],
            'indexes': lambda row: row[0]}


def check_new_table(before, after):
    require(not any(row['table_name'] == NEW_TABLE for row in before['schema']),
            'The declared new table was already present before activation.')
    added = [row for row in after['schema'] if row['table_name'] == NEW_TABLE]
    require(tuple(row['column_name'] for row in added) == NEW_COLUMNS,
            'New table columns differ from the eleven declared ones.')
    require([row['ordinal_position'] for row in added] == list(range(1, len(NEW_COLUMNS) + 1)),
            'New table column order differs from the declared one.')
    require(after['tables'].count(NEW_TABLE) == 1, 'The declared new table is not present exactly once.')
    require(all(table_of(row) == NEW_TABLE for name, table_of in TABLE_OF.items()
                for row in after[name] if row not in before[name]),
            'A constraint, index or column was added outside the declared new table.')


def unchanged(before, after):
    require(before.keys() == after.keys(), 'Preservation inventory shape changed.')
    require(set(before) == set(IDENTICAL) | set(TABLE_OF) | {'tables', 'new_table_rows'},
            'Preservation inventory gained or lost a component; every one must be judged.')
    for name in IDENTICAL:
        require(after[name] == before[name], 'Undeclared activation delta: ' + name)
    require([n for n in after['tables'] if n != NEW_TABLE] == [n for n in before['tables'] if n != NEW_TABLE],
            'Undeclared activation delta: tables')
    for name, table_of in TABLE_OF.items():
        require([r for r in after[name] if table_of(r) != NEW_TABLE]
                == [r for r in before[name] if table_of(r) != NEW_TABLE],
                'Undeclared activation delta: ' + name)
    require(before['new_table_rows'] is None and after['new_table_rows'] in (None, 0),
            'The declared new table must be absent beforehand and stay empty throughout.')
    if NEW_TABLE in after['tables']:
        check_new_table(before, after)


def validate_changed(changed):
    require(REQUIRED <= changed, 'Required reviewed combined change is absent.')
    require(all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                and str(PurePosixPath(name)) == name for name in changed), 'Noncanonical changed path.')
    require(all(name in RUNTIME_ALLOWED or name == DECL
                or re.fullmatch(re.escape(SCREENSHOTS) + r'[A-Za-z0-9._-]+\.(?:jpg|md)', name)
                or (name.startswith('docs/rebuild/') and name.endswith('.md')) for name in changed),
            'Undeclared source change; expand only after review.')
    require({p for p in changed if p.startswith('rebuild/core/migrations/')} == {MIGRATION_PATH},
            'Only the exact additive service-health migration may change.')
    require({p for p in changed if p.startswith('rebuild/static/')}
            == {'rebuild/static/app.css', 'rebuild/static/app.js'},
            'Only the two reviewed public assets may change.')
    require(not any(p.startswith('rebuild/ops/') and p != OPS_TEST for p in changed),
            'No qualified operations helper may change inside this activation.')
    require(not any(p.startswith('deploy/') or p.startswith('rebuild/deploy/')
                    or p.startswith('.github/') for p in changed),
            'No service policy or workflow change is declared by this activation.')


LOADED = {}


def recorded_static():
    """The retained public assets, from the last transition's OWN receipt, pinned by sha256."""
    data = (PRIVATE / PRIOR_TRANSITION).read_bytes()
    require(sha(data) == PRIOR_TRANSITION_SHA256, 'Prior static-transition receipt changed.')
    receipt = json.loads(data)
    require(receipt.get('complete') is True and receipt.get('migration_performed') is False
            and receipt.get('existing_hashed_assets_retained') is True,
            'Prior receipt is not a completed retaining code-only transition.')
    after = receipt.get('static_transition', {}).get('after')
    require(isinstance(after, dict) and after, 'Prior transition recorded no installed public assets.')
    return after


def authenticated_static_inventory(identity, word):
    """The inherited reader's guards, with its FIXED retained set replaced by a RECORDED one.

    ⚠️ THE INHERITED ALLOWLIST IS SINGLE-USE, AND THIS IS ITS SECOND RECURRENCE. It admits the
    CURRENT compiled asset plus two hard-coded historical ones, so EVERY retaining transition
    leaves behind an asset the next activation cannot name. Its own docstring records the first
    recurrence — it exists because the activator before it "only recognizes the current manifest".
    Measured here: `staticfiles/` holds three CSS and two JS generations, and the constant names
    one CSS pair, so the reader refuses a directory nothing is wrong with. Hard-coding today's
    four extra assets would only move the wall to the next activation.

    ⚠️ NOTHING IS LOOSENED. Every structural guard is kept: canonical root, operator ownership,
    no symlink, regular files, one link, bounded size and count, exact 0644/0755 modes, the
    manifest equal to the reviewed input set, each compiled name matching the hashed pattern, and
    each collected source byte-equal to the current application source. The inherited constant
    keeps full authority over the two assets it does name. What changes is only the PROVENANCE of
    the rest: an extra object must appear in the last transition's own pinned receipt with
    identical kind/mode/size/sha256, AND be a previously compiled form of a declared input.

    ⚠️ THIS BUILDS ITS ROWS INDEPENDENTLY, ON PURPOSE. The caller cross-checks this against the
    entry point's own descriptor reader. Delegating to that reader would make the comparison
    compare a value with itself, so a future simplification that calls it here would silently
    turn a real cross-check into a tautology. The ops test pins that this does not delegate.
    """
    root = APP / 'staticfiles'
    require(root.is_absolute() and root.resolve(strict=True) == root, 'Canonical static root required.')
    rows = {}
    for path in [root, *sorted(root.rglob('*'))]:
        require(len(rows) < 10000, 'Static output inventory exceeds the bounded scope.')
        info = path.lstat()
        directory = stat.S_ISDIR(info.st_mode)
        require(info.st_uid == os.getuid() and not stat.S_ISLNK(info.st_mode)
                and (directory or stat.S_ISREG(info.st_mode))
                and stat.S_IMODE(info.st_mode) == (0o755 if directory else 0o644)
                and (directory or (info.st_nlink == 1 and info.st_size <= 16 * 1024 * 1024)),
                'Static output must be operator-owned, regular, unlinked and correctly moded.')
        relative = '.' if path == root else path.relative_to(root).as_posix()
        row = {'mode': stat.S_IMODE(info.st_mode), 'device': info.st_dev, 'inode': info.st_ino,
               'kind': 'directory' if directory else 'file'}
        if not directory:
            data = path.read_bytes()
            require(len(data) == info.st_size, 'Static output changed during read.')
            row.update(size=len(data), sha256=sha(data))
        rows[relative] = row
    manifest = json.loads((root / 'staticfiles.json').read_bytes())
    inputs = identity.static_sources()
    require(isinstance(manifest.get('paths'), dict) and set(manifest['paths']) == set(inputs) == t.STATIC_INPUTS,
            'Static manifest differs from the reviewed application and installed OTP assets.')
    allowed, allowed_dirs, patterns = {'staticfiles.json'}, {'.'}, []
    for source, compiled in manifest['paths'].items():
        original = PurePosixPath(source)
        pattern = re.escape(str(original.with_suffix(''))) + r'\.[a-f0-9]{12}' + re.escape(original.suffix)
        require(isinstance(compiled, str) and re.fullmatch(pattern, compiled),
                'Static manifest includes an unexpected path.')
        require((root / source).read_bytes() == inputs[source].read_bytes(),
                'Collected static input differs from current application source.')
        require(compiled in rows and rows[compiled]['kind'] == 'file', 'Compiled static asset is missing.')
        patterns.append(pattern)
        for name in (source, compiled):
            allowed.update((name, name + '.gz', name + '.br'))
            allowed_dirs.update(str(parent) for parent in PurePosixPath(name).parents)
    inherited = LOADED['old'].RETAINED_STATIC
    for name, expected in inherited.items():
        found = rows.get(name, {})
        require(found.get('kind') == 'file'
                and all(found.get(key) == expected[key] for key in ('mode', 'size', 'sha256')),
                'A historically retained public asset differs from its exact recorded bytes or mode.')
    retained = recorded_static()
    for name, row in rows.items():
        if name in allowed or name in inherited or (row['kind'] == 'directory' and name in allowed_dirs):
            continue
        expected = retained.get(name)
        require(expected is not None
                and all(expected.get(key) == row.get(key) for key in ('kind', 'mode', 'size', 'sha256')),
                'Static output contains an object no recorded transition installed: ' + name)
        require(row['kind'] == 'file'
                and any(re.fullmatch(pattern + r'(?:\.gz|\.br)?', name) for pattern in patterns),
                'A retained public asset is not a previously compiled form of a declared input: ' + name)
    return rows


_inherited_load = a.load


def load(name, relative, target):
    module = _inherited_load(name, relative, target)
    if name == 'old':
        LOADED['old'] = module
        # Replace only this one reader on the byte-identical qualified helper, the same way the
        # inherited adapters replace `systemd` and `private_write` on theirs.
        module.static_inventory = authenticated_static_inventory
    return module


def verify_source(target):
    changed = _inherited_verify_source(target)
    require((SOURCE / DRIVER).read_bytes() == b.blob(BASELINE, DRIVER) == b.blob(target, DRIVER),
            'Pinned activation driver identity mismatch.')
    return changed


def receipt(document):
    result = _inherited_receipt(document)
    if 'baseline' in result:
        result['activation_adapter'] = SELF
        result['pinned_driver'] = DRIVER
        result['declared_migration'] = MIGRATION
        result['declared_migration_sha256'] = MIGRATION_SHA256
        result['migration_performed'] = STATE['migration_performed']
        result['declared_schema_delta'] = (
            'One new empty table ' + NEW_TABLE + ' with its eleven declared columns and its own '
            'constraints and indexes, plus one django_migrations row. Every other table, row, '
            'column, constraint, index, trigger and function is compared for exact equality.')
        if 'existing_schema_indexes_constraints_catalog_unchanged' in result:
            del result['existing_schema_indexes_constraints_catalog_unchanged']
            result['existing_schema_indexes_constraints_catalog_unchanged_apart_from_declared_new_table'] = True
    return result


def configure():
    for name in ('ROOT', 'SOURCE', 'APP', 'PRIVATE', 'EVIDENCE', 'SELF', 'DECL', 'BASELINE',
                 'RUNNING_RELEASE', 'MIGRATION', 'MIGRATION_PATH', 'MIGRATION_SHA256',
                 'PREVIOUS_MIGRATION', 'CAPTURE_RUN', 'CAPTURE_SOURCE', 'CAPTURE_MANIFEST_SHA256'):
        setattr(a, name, globals()[name])
    a.receipt = receipt
    a.load = load
    a.configured_driver()
    for name in ('EVIDENCE', 'SELF', 'DECL', 'BASELINE', 'RUNNING_RELEASE', 'MIGRATION',
                 'RUNTIME_ALLOWED', 'REQUIRED', 'validate_changed', 'verify_migrations',
                 'verify_source', 'snapshot', 'unchanged'):
        setattr(t, name, globals()[name])
    t.re = _RenamedReceiptRe()
    b.rows = rows
    b.check_schema = check_new_table
    return t


configure()


if __name__ == '__main__':
    if '--execute' in sys.argv:
        EVIDENCE.mkdir(mode=0o700, exist_ok=True)
    t.main()
