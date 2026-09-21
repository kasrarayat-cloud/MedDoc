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
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
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
# ⚠️ A CreateModel migration is NOT only a table. Django's post_migrate writes the model's
# ContentType and its four default permissions, so the declared delta is five rows wider than a
# reading of the migration file suggests. Measured, not assumed: this is what the act's own
# comparison caught when the first attempt declared only the table and its history row.
NEW_MODEL = 'servicehealth'
NEW_PERMISSIONS = ('add_servicehealth', 'change_servicehealth', 'delete_servicehealth',
                   'view_servicehealth')
BOOKKEEPING = {
    'django_migrations': "WHERE NOT (app='core' AND name='" + MIGRATION + "')",
    'django_content_type': "WHERE NOT (app_label='core' AND model='" + NEW_MODEL + "')",
    'auth_permission': ("WHERE content_type_id NOT IN (SELECT id FROM django_content_type"
                        " WHERE app_label='core' AND model='" + NEW_MODEL + "')"),
}
CAPTURE_RUN = '20260921T043001Z-0a6f66da'
CAPTURE_SOURCE = '08e40870f18ca4e79b0cc2b27d6b09ba48f911a7'
CAPTURE_MANIFEST_SHA256 = 'ac714b19363a66294d35cfde0d4b1de62de2ab9db1916b67f466f9e41bd19c82'
OPS_TEST = 'rebuild/ops/test_admin_console_activation.py'
# The last transition that installed public assets, and its receipt, pinned by content.
PRIOR_TRANSITION = 'typed-voice-20260921/typed-voice-resume-b6b40b02.json'
PRIOR_TRANSITION_SHA256 = '757d43c7da60db56ea8f5030757e7bf95db4f37e5677cae7648a114c4b04d13e'
SCREENSHOTS = 'docs/rebuild/admin-console-screenshots-20260921/'
RESULT_PATTERN = r'typed-voice-activation-[a-zA-Z0-9_-]+\.json'
# The first attempt of this act, stopped by its own comparison, and the forward repair of it.
FAILED_TARGET = '1f8d7d9d124243f78bd17449e60339f313a2e1c5'
FAILED_RECEIPT_NAME = 'admin-console-activation-1f8d7d9d1242.json'
FAILED_RECEIPT_SHA256 = 'aff789294cce292313543171e3ef9d36c4f6e2b80642d00b3c3b25b8fdbef446'
RESUME_DECL = 'docs/foundation/mutations/20260921-quillmd-admin-console-resume.md'
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
FAILED_RECEIPT = EVIDENCE / FAILED_RECEIPT_NAME
RESUME_PATHS = {SELF, OPS_TEST, RESUME_DECL}
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
    check_new_bookkeeping(old)


def rows(old):
    """Full per-table fingerprints, excluding ONLY the declared additions.

    The new table is skipped and the new model's own bookkeeping rows are filtered out, so the
    before and after snapshots describe the IDENTICAL universe and compare with exact equality.

    ⚠️ Each filter is written so it matches NOTHING before the migration — the history row, the
    ContentType and the permissions do not exist yet, and the permission filter's subquery is
    empty — so one implementation serves both universes and there is no before/after asymmetry
    to get wrong. Nothing else is projected away: no other difference has an excuse available.
    """
    result = {}
    for name in old.tables():
        if name == NEW_TABLE:
            continue
        where = BOOKKEEPING.get(name, '')
        data = subprocess.check_output(
            old.PSQL + ['COPY (SELECT (to_jsonb(t))::text AS value FROM "' + name + '" t '
                        + where + ' ORDER BY value) TO STDOUT'], timeout=600)
        result[name] = {'sha256': sha(data), 'rows': len(data.splitlines())}
    return result


def check_new_bookkeeping(old):
    """What post_migrate added must be EXACTLY the new model's own rows, and nothing else."""
    require(b.output(old.PSQL + ["SELECT count(*) FROM django_content_type WHERE app_label='core'"
                                 " AND model='" + NEW_MODEL + "'"]) == '1',
            'The new model has no ContentType, or more than one.')
    codenames = b.output(old.PSQL + ["SELECT string_agg(p.codename, ',' ORDER BY p.codename)"
                                     " FROM auth_permission p JOIN django_content_type c"
                                     " ON c.id = p.content_type_id WHERE c.app_label='core'"
                                     " AND c.model='" + NEW_MODEL + "'"])
    require(codenames == ','.join(sorted(NEW_PERMISSIONS)),
            'The new model\'s permissions are not exactly the four declared defaults.')


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
                for row in after[name] if wire(row) not in [wire(x) for x in before[name]]),
            'A constraint, index or column was added outside the declared new table.')


def wire(value):
    """Normalize ONLY tuple-vs-list, so a JSON-reloaded snapshot compares with a live one.

    The qualified SQL readers return constraint and index rows as tuples; a receipt reloads
    those same arrays as lists. Nothing is sorted, omitted or coerced — a difference in any
    value still shows.
    """
    if isinstance(value, dict):
        require(all(type(key) is str for key in value), 'Snapshot object keys must remain JSON strings.')
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(item) for item in value]
    return value


def compare(before, after, label):
    """The ONE tolerance implementation, shared by the live and the saved comparators.

    A second copy of this would drift from the first the day either is fixed, and the rule it
    encodes — tolerate the declared delta and nothing else — is the whole product of §2.5 here.
    """
    require(before.keys() == after.keys(), 'Preservation inventory shape changed.')
    require(set(before) == set(IDENTICAL) | set(TABLE_OF) | {'tables', 'new_table_rows'},
            'Preservation inventory gained or lost a component; every one must be judged.')
    for name in IDENTICAL:
        require(wire(after[name]) == wire(before[name]), label + ': ' + name)
    require([n for n in after['tables'] if n != NEW_TABLE] == [n for n in before['tables'] if n != NEW_TABLE],
            label + ': tables')
    for name, table_of in TABLE_OF.items():
        require([wire(r) for r in after[name] if table_of(r) != NEW_TABLE]
                == [wire(r) for r in before[name] if table_of(r) != NEW_TABLE],
                label + ': ' + name)
    require(before['new_table_rows'] in (None, 0) and after['new_table_rows'] in (None, 0)
            and not (before['new_table_rows'] == 0 and after['new_table_rows'] is None),
            'The declared new table must stay empty, and must never disappear once created.')
    if NEW_TABLE in after['tables'] and NEW_TABLE not in before['tables']:
        check_new_table(before, after)


def unchanged(before, after):
    compare(before, after, 'Undeclared activation delta')


def unchanged_saved_snapshot(before, after):
    compare(before, after, 'Undeclared saved-state activation delta')


def validate_changed(changed):
    require(REQUIRED <= changed, 'Required reviewed combined change is absent.')
    require(all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                and str(PurePosixPath(name)) == name for name in changed), 'Noncanonical changed path.')
    require(all(name in RUNTIME_ALLOWED or name in (DECL, RESUME_DECL)
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


def verify_resume_migrations(old, plan):
    """On resume the declared migration is ALREADY applied; assert that, and its bookkeeping."""
    b.verify_migration_plan(plan, applied=True)
    require(b.output(old.PSQL + ["SELECT name FROM django_migrations WHERE app='core'"
                                 " ORDER BY id DESC LIMIT 1"]) == MIGRATION,
            'The declared migration is not the applied frontier.')
    for name, count in ((MIGRATION, '1'), (PREVIOUS_MIGRATION, '1')):
        require(b.output(old.PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core'"
                                     " AND name='" + name + "'"]) == count,
                'Unexpected migration history for ' + name + '.')
    require(b.output(old.PSQL + ['SELECT count(*) FROM "' + NEW_TABLE + '"']) == '0',
            'The declared new table must still be empty at resume.')
    check_new_bookkeeping(old)


def validate_failed_receipt(data):
    require(sha(data) == FAILED_RECEIPT_SHA256, 'Original failed activation receipt changed.')
    failed = json.loads(data)
    require(failed.get('complete') is False and failed.get('target') == FAILED_TARGET
            and failed.get('baseline') == BASELINE and failed.get('served_before') == RUNNING_RELEASE
            and failed.get('stage') == 'advance_stopped_source_ff_only'
            and failed.get('failure_kind') == 'RuntimeError'
            and failed.get('failure_services_stopped') is True
            and failed.get('provider_calls') == 0
            and failed.get('migration_performed') is True
            and failed.get('declared_migration') == MIGRATION,
            'Only the exact stopped post-migration refusal is resumable.')
    require('static_transition' not in failed,
            'The failed act reached the public-asset transition; do not resume it generically.')
    require(failed['state_directory'] == str(EVIDENCE / ('activation-state-' + FAILED_TARGET[:12])),
            'Original rollback state path changed.')
    return failed


def verify_resume_source(target):
    require(re.fullmatch('[a-f0-9]{40}', target), 'Full merged repair target required.')
    require(SOURCE.is_relative_to(ROOT / '.worktrees') and SOURCE.resolve() == SOURCE,
            'Use the retained reviewed repair worktree.')
    require(not b.output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=SOURCE)
            and not b.output(['git', 'diff', '--name-only', target], cwd=SOURCE),
            'Repair worktree must be clean and byte-equivalent to the merged target.')
    require(b.git('rev-parse', 'HEAD') == FAILED_TARGET and b.git('branch', '--show-current') == 'main'
            and b.git('rev-parse', 'origin/main') == target
            and not b.git('status', '--porcelain', '--untracked-files=no'),
            'Shared main must remain at the exact failed target before resume.')
    b.run(['git', 'merge-base', '--is-ancestor', FAILED_TARGET, target], cwd=ROOT)
    changed = set(b.git('diff', '--name-only', FAILED_TARGET, target).splitlines())
    require(changed == RESUME_PATHS,
            'The repair may change only this activator, its guards and the repair declaration.')
    require(Path(__file__).read_bytes() == b.blob(target, SELF)
            and (SOURCE / DRIVER).read_bytes() == b.blob(FAILED_TARGET, DRIVER) == b.blob(target, DRIVER),
            'Repair adapter or pinned driver identity mismatch.')
    return changed


def resume_failed(args):
    """One exact forward repair of the stopped act. The migration is NOT replayed.

    The first attempt advanced the source and applied the declared migration, then stopped at
    its own preservation comparison because the declaration had not named the ContentType and
    four permissions that Django's post_migrate writes for a new model. Nothing beyond that had
    happened: no public asset moved, no release stamp changed, no service started. This finishes
    exactly the remaining work against the state that act left behind.
    """
    require(Path(args.resume_failed) == FAILED_RECEIPT, 'Only the pinned failed result may be resumed.')
    changed = verify_resume_source(args.target)
    pulls = json.loads(b.output(['gh', 'api', 'repos/kasrarayat-cloud/MedDoc/commits/'
                                 + args.target + '/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'Exact merged repair PR required.')
    b.run(['bash', str(ROOT / 'scripts/check-citation.sh'), args.target], cwd=ROOT)
    modules = {name: a.load(name, relative, args.target) for name, relative in b.HELPERS.items()}
    old, word, identity, storage, previous = (modules[k] for k in ('old', 'word', 'identity', 'storage', 'previous'))
    failed = validate_failed_receipt(word.checked_file(FAILED_RECEIPT, private=True))
    state_before = Path(failed['state_directory'])
    require(state_before.resolve(strict=True) == state_before and state_before.is_dir(),
            'Canonical prior rollback state required.')
    require(not (state_before / 'static-stage').exists(),
            'The failed act began collecting public assets; inspect instead of resuming.')
    b.stopped()
    require(len(old.tables()) == 36
            and b.output(old.PSQL + ["SELECT count(*) FROM core_job WHERE state IN"
                                     " ('queued','running','reconciliation')"]) == '0',
            'Unexpected tables or unresolved jobs during repair.')
    verify_resume_migrations(old, b.output(b.management('showmigrations', '--plan'), cwd=APP))
    b.run(b.management('check'), cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    original = word.checked_file(APP / '.env', private=True)
    require(original == word.checked_file(state_before / 'prior-environment.env', private=True)
            and sha(original) == failed['environment_before_sha256'],
            'Environment changed after the failed activation.')
    updated = b.updated_environment(original, args.target)
    require(args.backup_report == failed['backup_report'], 'Historical recovery reference changed.')
    restore, manifest = a.backup_evidence(args.backup_report, modules)
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json',
                                          private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper)
            and b.output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper,
            'Pinned service helper unavailable.')
    # The authenticated reader describes the pre-advance population; past the advance the
    # collected copy legitimately differs from its source until the transition runs.
    old.static_inventory = lambda _identity, _word: t.static_inventory(APP / 'staticfiles')
    baseline = snapshot(modules, helper)
    unchanged_saved_snapshot(failed['stopped_before'], baseline)
    t.assert_retained_capture(manifest, modules, baseline['storage']['files'])
    protected = previous.protected()
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE), 'Installed Word SDK inputs changed.')
    installed = APP / '.word-sdk' / modules['billing'].SDK_RELEASE
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                    installed / 'build-proof.json', modules['billing'].PIN, inputs)
    identity.source_readability(helper)
    lock = PRIVATE / '.private-readiness-activation.lock'
    lock_bytes = word.checked_file(lock, private=True)
    lock_value = json.loads(lock_bytes)
    require(lock_value.get('target') == FAILED_TARGET and lock_value.get('automatic_rollback') is False
            and type(lock_value.get('pid')) is int and lock_value['pid'] > 1,
            'Original activation lock differs.')
    try:
        os.kill(lock_value['pid'], 0)
    except ProcessLookupError:
        pass
    else:
        raise RuntimeError('Original activation process is still present; do not resume concurrently.')
    result_path = Path(args.result)
    state = EVIDENCE / ('resume-state-' + args.target[:12])
    require(result_path.is_absolute() and result_path.resolve() == result_path
            and result_path.parent == EVIDENCE
            and re.fullmatch(r'admin-console-resume-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not any(p.exists() or p.is_symlink() for p in (result_path, state)),
            'Unused protected repair result and state required.')
    b.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
    print('Read-only exact failed-state repair checks passed; writers remain stopped.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration
            and declaration == SOURCE / RESUME_DECL and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == b.blob(args.target, RESUME_DECL) == b.blob(commit, RESUME_DECL),
            'Committed exact repair declaration required.')
    b.run(['git', 'merge-base', '--is-ancestor', commit, args.target], cwd=ROOT)
    state.mkdir(mode=0o700)
    identity.private_write(state / 'original-lock.json', lock_value)
    result = {'complete': False, 'started_at': datetime.now(timezone.utc).isoformat(),
        'baseline': FAILED_TARGET, 'served_before': RUNNING_RELEASE, 'target': args.target,
        'changed_paths': sorted(changed), 'resumed_failure': str(FAILED_RECEIPT),
        'resumed_failure_sha256': FAILED_RECEIPT_SHA256, 'prior_rollback_state': str(state_before),
        'migration_applied_by_the_resumed_act': True, 'state_directory': str(state),
        'provider_calls': 0, 'stopped_before': baseline, 'backup_report': args.backup_report,
        'backup_run_id': manifest['run_id'], 'restored_backup_run_id': restore['backup_run_id'],
        'current_capture_restored': False, 'original_failed_result_preserved': True,
        'environment_before_sha256': sha(original), 'environment_after_sha256': sha(updated),
        'rollback_policy': 'Stop on failure; retain current data, schema, configuration and prior '
                           'source. A reviewed forward repair is preferred to any replay.'}
    phase = 0

    def checkpoint(stage):
        nonlocal phase
        result['stage'] = stage
        identity.private_write(state / ('phase-%02d.json' % phase), result)
        phase += 1

    try:
        checkpoint('advance_only_the_reviewed_repair')
        b.stopped()
        verify_resume_source(args.target)
        unchanged(baseline, snapshot(modules, helper))
        require(word.checked_file(lock, private=True) == lock_bytes
                and word.checked_file(APP / '.env', private=True) == original,
                'Repair preconditions changed.')
        b.run(['git', 'merge', '--ff-only', args.target], cwd=ROOT, stdout=subprocess.DEVNULL)
        require(b.git('rev-parse', 'HEAD') == args.target
                and not b.git('status', '--porcelain', '--untracked-files=no'),
                'Shared source differs from the exact repair target.')
        verify_resume_migrations(old, b.output(b.management('showmigrations', '--plan'), cwd=APP))
        b.run(b.management('check'), cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        unchanged(baseline, snapshot(modules, helper))
        checkpoint('collect_and_install_source_bound_public_assets')
        stage = state / 'static-stage'
        t.create_static_stage(stage)
        t.collect_static(stage)
        staged = t.validate_staged_static(stage, identity.static_sources())
        installed_static = t.install_static(APP / 'staticfiles', stage, baseline['static'], staged)
        result['static_transition'] = {'before': baseline['static'], 'staged': staged,
            'after': installed_static, 'old_immutable_assets_retained': True,
            'prior_archive': str(state_before / 'prior-static.tar')}
        baseline = dict(baseline, static=installed_static)
        unchanged(baseline, snapshot(modules, helper))
        result['source_readability'] = identity.source_readability(helper)
        checkpoint('replace_release_setting_only')
        modules['env'].replace_environment(APP / '.env', original, updated)
        checkpoint('start_and_verify_exact_private_release')
        word.systemd('start', helper)
        for attempt in range(45):
            try:
                live_health = b.health(args.target)
                break
            except (subprocess.CalledProcessError, json.JSONDecodeError, RuntimeError):
                time.sleep(1)
        else:
            raise RuntimeError('Repaired private release did not become healthy.')
        result['proofs_after'] = identity.verify_live(args.target, storage)
        result['interfaces_after'] = identity.verify_interfaces()
        worker_after = old.worker_process()
        require(worker_after['systemd_start'] != failed['worker_before']['systemd_start']
                and worker_after['kernel_start_utc'] > failed['worker_before']['kernel_start_utc'],
                'Worker restart not evidenced.')
        result['worker_after'] = worker_after
        unchanged(baseline, snapshot(modules, helper))
        require(word.checked_file(APP / '.env', private=True) == updated
                and previous.protected() == protected, 'Configuration or protected services changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                     installed / 'build-proof.json', modules['billing'].PIN,
                                     inputs) == artifact, 'Installed Word SDK changed.')
        b.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
        result.update(complete=True, health=live_health, existing_rows_unchanged=True,
            private_files_and_mail_unchanged=True, existing_hashed_assets_retained=True,
            static_delta_source_bound=True, backup_units_installed=False,
            finished_at=datetime.now(timezone.utc).isoformat())
        require(word.checked_file(lock, private=True) == lock_bytes,
                'Original lock changed before completion.')
        checkpoint('complete')
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(t.failure_details(error, result.get('stage')), complete=False,
                      finished_at=datetime.now(timezone.utc).isoformat())
        try:
            word.systemd('stop', helper); b.stopped(); result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False
            result['stop_failure_kind'] = type(stop_error).__name__
        identity.private_write(result_path, result)
        raise RuntimeError('Private repair stopped; inspect retained failure and rollback evidence.') from None
    print('Private repair and exact installed release verified; evidence: ' + str(result_path), flush=True)


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
                 'verify_source', 'snapshot', 'unchanged', 'unchanged_saved_snapshot',
                 'resume_failed', 'validate_failed_receipt', 'verify_resume_source',
                 'FAILED_TARGET', 'FAILED_RECEIPT', 'FAILED_RECEIPT_SHA256', 'RESUME_DECL',
                 'RESUME_PATHS'):
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
