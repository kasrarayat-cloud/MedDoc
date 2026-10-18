"""Declared coding-completeness installation; inert without an exact new plan.

Admits one empty append-only review table and exact candidate static assets.
All existing clinical rows, files, approvals, guards and configuration remain
fixed except the migration ledger/sequence and release stamp. No provider work
or clinical/coding decision is submitted by this controller.
"""
import argparse
import ast
import gzip
import hashlib
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

from dotenv import dotenv_values
from dotenv.parser import parse_stream
from . import activate_rowan_corti as prior
from .activate_coordinated_workflow import table_fingerprint, TABLE_FINGERPRINT_CONTRACT

BASE = '96f750f9d9c984db0839352777e099d740d87b72'
SOURCE = Path(__file__).resolve().parents[2]
FORMAT = 'quillmd-coding-completeness-native-install-v1'
MIGRATION = '0032_coding_source_decision'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
NEW_TABLE = 'core_codingsourcedecision'
NEW_TRIGGER = 'coding_source_decision_append_only'
MIGRATION_AST_SHA256 = '32e6b76e6634d5ed7897574c8f56eaa9901a832b13b94f43569133bdaa0d7936'
SCHEMA_FORMAT = 'quillmd-coding-completeness-schema-v1'
STATIC = frozenset({'coding.js'})
RUNTIME = frozenset({'rebuild/core/models.py', MIGRATION_PATH,
    'rebuild/core/coding_completeness.py', 'rebuild/core/coding_reference_store.py',
    'rebuild/core/coding_source_review.py', 'rebuild/core/coding_service.py',
    'rebuild/core/coding_views.py', 'rebuild/core/coding_export.py',
    'rebuild/quillmd/urls.py', 'rebuild/templates/coding_source_review.html',
    'rebuild/templates/coding_panel.html', 'rebuild/static/coding.js'})
SUPPORT = frozenset({'rebuild/ops/activate_coding_completeness.py',
    'rebuild/ops/test_activate_coding_completeness.py',
    'docs/runbooks/coding-completeness-install-20261018.md',
    'docs/audit-reports/source-coding-completeness-20261018.md',
    'rebuild/core/tests/test_coding_completeness.py',
    'rebuild/core/tests/test_coding_source_review.py',
    'rebuild/core/tests/test_coding_source_reference.py'})
FIXTURES = frozenset()
require, Refusal = prior.require, prior.Refusal


@contextmanager
def bound_primitives(static=()):
    """Reuse low-level publication primitives, never a consumed activation."""
    saved = {key: getattr(prior, key) for key in ('BASE', 'SOURCE', 'STATIC')}
    prior.BASE, prior.SOURCE, prior.STATIC = BASE, SOURCE, frozenset(static)
    try:
        yield
    finally:
        for key, value in saved.items():
            setattr(prior, key, value)


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == {'format', 'base', 'candidate', 'source_sha256',
        'source_worktree', 'evidence_directory', 'environment_before_sha256', 'environment', 'static',
        'baseline_path', 'baseline_sha256', 'schema_contract_path', 'schema_contract_sha256'},
        'closed_coding_completeness_plan')
    require(plan['format'] == FORMAT and plan['base'] == BASE
            and re.fullmatch('[a-f0-9]{40}', plan['candidate']) and plan['candidate'] != BASE,
            'exact_coding_completeness_revision')
    require(re.fullmatch('[a-f0-9]{64}', plan['environment_before_sha256']), 'environment_pin')
    require(re.fullmatch('[a-f0-9]{64}', plan['baseline_sha256']), 'declared_baseline_pin')
    baseline_path = Path(plan['baseline_path'])
    require(baseline_path.is_absolute() and baseline_path.parent.resolve() == baseline_path.parent,
            'canonical_declared_baseline_path')
    paths = plan['source_sha256']
    require(type(paths) is dict and 0 < len(paths) <= len(RUNTIME | SUPPORT | FIXTURES) and RUNTIME.intersection(paths),
            'finite_coding_completeness_source_manifest')
    for name, digest in paths.items():
        path = PurePosixPath(name)
        require(name == str(path) and not path.is_absolute()
                and not any(part.startswith('.') for part in path.parts)
                and name in RUNTIME | SUPPORT | FIXTURES
                and re.fullmatch('[a-f0-9]{64}', digest), 'only_coding_completeness_source')
    require(type(plan['environment']) is dict and plan['environment'] == {}, 'release_stamp_only')
    require(type(plan['static']) is list and plan['static'] == sorted(set(plan['static']))
            and set(plan['static']) <= STATIC, 'bounded_public_static')
    require(sorted('rebuild/static/' + name for name in plan['static'])
            == sorted(name for name in paths if name.startswith('rebuild/static/')), 'exact_changed_static')
    require(MIGRATION_PATH in paths and 'rebuild/core/models.py' in paths, 'migration_model_bound')
    require(re.fullmatch('[a-f0-9]{64}', plan['schema_contract_sha256']), 'schema_contract_pin')
    schema_path = Path(plan['schema_contract_path'])
    require(schema_path.is_absolute() and schema_path.parent.resolve() == schema_path.parent, 'canonical_schema_contract_path')
    out = Path(plan['evidence_directory']); source = Path(plan['source_worktree'])
    require(out.is_absolute() and out.parent.resolve() == out.parent and not out.exists()
            and not out.is_symlink() and out.parent.stat().st_uid == os.getuid()
            and stat.S_IMODE(out.parent.stat().st_mode) == 0o700, 'exclusive_private_output')
    require(source.is_absolute() and source.resolve() == source and source == SOURCE, 'exact_operator_worktree')


def render_environment(original, revision, environment):
    require(type(environment) is dict and environment == {}, 'release_stamp_only')
    require(re.fullmatch('[a-f0-9]{40}', revision) and revision != BASE, 'exact_coding_completeness_revision')
    values = dotenv_values(stream=io.StringIO(original.decode()), interpolate=False)
    require(values.get('QUILLMD_RELEASE_SHA') == BASE, 'exact_installed_release')
    require(sum(binding.key == 'QUILLMD_RELEASE_SHA' for binding in parse_stream(io.StringIO(original.decode()))) == 1,
            'duplicate_release_assignment')
    lines, found = [], False
    for line in original.splitlines(keepends=True):
        match = re.match(rb'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=', line)
        if match and match[1] == b'QUILLMD_RELEASE_SHA':
            require(not found, 'duplicate_release_assignment'); found = True
            ending = b'\r\n' if line.endswith(b'\r\n') else b'\n' if line.endswith(b'\n') else b''
            lines.append(b'QUILLMD_RELEASE_SHA="' + revision.encode() + b'"' + ending)
        else:
            lines.append(line)
    require(found, 'release_assignment_found')
    result = b''.join(lines)
    after = dotenv_values(stream=io.StringIO(result.decode()), interpolate=False)
    require(after == {**values, 'QUILLMD_RELEASE_SHA': revision}, 'only_release_stamp_changed')
    return result


def unchanged(before, after):
    require(before == after, 'all_current_database_state_unchanged')
    require(not any(after['pending'].values()), 'no_provider_work_during_install')


CATALOG_KEYS = frozenset({'tables', 'columns', 'constraints', 'indexes', 'triggers',
    'functions', 'sequence_metadata', 'policies', 'default_acl', 'views', 'rules'})


def catalog(connection):
    """Read the declared public catalog in the caller's existing RO/RR transaction.

    Internal FK trigger names contain installation-specific OIDs. Their declared
    constraints are measured instead; only the admitted CreateModel may create
    them. Explicit triggers retain their complete definitions and attributes.
    """
    require(connection.execute("SELECT current_setting('transaction_read_only'),current_setting('transaction_isolation')").fetchone()
            == ('on', 'repeatable read'), 'catalog_readonly_repeatable_read')
    def rows(sql, names):
        result = {}
        for key, *values in connection.execute(sql):
            require(key not in result and len(values) == len(names), 'unambiguous_catalog_rows')
            result[key] = dict(zip(names, values))
        return result
    result = {}
    result['tables'] = rows("""SELECT c.relname,pg_get_userbyid(c.relowner),c.relrowsecurity,c.relforcerowsecurity,
        c.relpersistence::text,c.relkind::text,c.relreplident::text,c.reloptions,c.relispartition,
        COALESCE(s.spcname,''),am.amname,
        (SELECT jsonb_agg(jsonb_build_object('grantor',pg_get_userbyid(x.grantor),'grantee',
            CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END,
            'privilege',x.privilege_type,'grantable',x.is_grantable)
            ORDER BY x.grantor,x.grantee,x.privilege_type,x.is_grantable)
         FROM aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) x)
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_tablespace s ON s.oid=c.reltablespace LEFT JOIN pg_am am ON am.oid=c.relam
        WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname""",
        ('owner','rls','force_rls','persistence','kind','replica_identity','options','partition','tablespace','access_method','privileges'))
    # Sort ACLs by role names rather than installation-specific role OIDs.
    for table in result['tables'].values():
        table['privileges'].sort(key=lambda row: (row['grantor'],row['grantee'],row['privilege'],row['grantable']))
    result['columns'] = rows("""SELECT c.relname||':'||a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),
        a.attnotnull,pg_get_expr(d.adbin,d.adrelid),a.attidentity::text,a.attgenerated::text,
        CASE WHEN a.attcollation=0 THEN NULL ELSE cn.nspname||'.'||co.collname END,
        a.attacl::text,a.attstorage::text,a.attcompression::text,a.atthasmissing,a.attmissingval::text
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        LEFT JOIN pg_collation co ON co.oid=a.attcollation LEFT JOIN pg_namespace cn ON cn.oid=co.collnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY c.relname,a.attnum""", ('name','type','not_null','default','identity','generated','collation',
            'acl','storage','compression','has_missing','missing_value'))
    result['constraints'] = rows("""SELECT r.relname||':'||c.conname,pg_get_constraintdef(c.oid),c.convalidated,
        c.contype::text,c.condeferrable,c.condeferred,c.connoinherit,c.conislocal,c.coninhcount
        FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname='public' ORDER BY r.relname,c.conname""",
        ('definition','validated','type','deferrable','initially_deferred','no_inherit','local','inherit_count'))
    result['indexes'] = rows("""SELECT c.relname||':'||i.relname,pg_get_indexdef(x.indexrelid),x.indisunique,
        x.indisprimary,x.indisvalid,x.indisready,x.indislive,x.indisreplident,x.indisclustered,
        pg_get_userbyid(i.relowner),i.reloptions,COALESCE(s.spcname,'')
        FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_tablespace s ON s.oid=i.reltablespace
        WHERE n.nspname='public' ORDER BY c.relname,i.relname""",
        ('definition','unique','primary','valid','ready','live','replica_identity','clustered','owner','options','tablespace'))
    result['triggers'] = rows("""SELECT c.relname||':'||t.tgname,pg_get_triggerdef(t.oid),t.tgenabled::text,t.tgtype,
        pn.nspname,p.proname,encode(t.tgargs,'hex'),t.tgqual::text,t.tgattr::text,
        t.tgconstraint,t.tgdeferrable,t.tginitdeferred
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace
        WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""",
        ('definition','enabled','type','function_schema','function','arguments_hex','when','columns','constraint','deferrable','initially_deferred'))
    result['functions'] = rows("""SELECT p.proname||'('||pg_get_function_identity_arguments(p.oid)||')',
        encode(sha256(convert_to(pg_get_functiondef(p.oid),'UTF8')),'hex'),pg_get_userbyid(p.proowner),
        p.proacl::text,p.prosecdef,p.proconfig,l.lanname,pg_get_function_identity_arguments(p.oid),pg_get_function_result(p.oid)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang
        WHERE n.nspname='public' AND p.prokind IN ('f','p') ORDER BY 1""",
        ('definition_sha256','owner','acl','security_definer','configuration','language','arguments','returns'))
    result['sequence_metadata'] = rows("""SELECT s.sequencename,s.sequenceowner,s.data_type,s.start_value,s.min_value,
        s.max_value,s.increment_by,s.cycle,s.cache_size,c.relacl::text
        FROM pg_sequences s JOIN pg_class c ON c.relname=s.sequencename JOIN pg_namespace n ON n.oid=c.relnamespace
        AND n.nspname=s.schemaname WHERE s.schemaname='public' ORDER BY s.sequencename""",
        ('owner','type','start','minimum','maximum','increment','cycle','cache','acl'))
    result['policies'] = rows("""SELECT tablename||':'||policyname,permissive,roles,cmd,qual,with_check
        FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname""",
        ('permissive','roles','command','qualification','with_check'))
    result['default_acl'] = rows("""SELECT pg_get_userbyid(d.defaclrole)||':'||COALESCE(n.nspname,'')||':'||d.defaclobjtype::text,
        d.defaclacl::text FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
        WHERE d.defaclnamespace=0 OR n.nspname='public' ORDER BY 1""", ('acl',))
    result['views'] = rows("""SELECT c.relname,pg_get_userbyid(c.relowner),c.relacl::text,c.relkind::text,
        pg_get_viewdef(c.oid,true),c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('v','m') ORDER BY c.relname""",
        ('owner','acl','kind','definition','options'))
    result['rules'] = rows("""SELECT c.relname||':'||r.rulename,pg_get_ruledef(r.oid),r.ev_enabled::text
        FROM pg_rewrite r JOIN pg_class c ON c.oid=r.ev_class JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' ORDER BY c.relname,r.rulename""", ('definition','enabled'))
    return result


def catalog_additions(before, after):
    require(set(before) == set(after) == CATALOG_KEYS, 'complete_catalog_categories')
    added = {}
    for category in sorted(CATALOG_KEYS):
        old, new = before[category], after[category]
        require(type(old) is dict and type(new) is dict and set(old) <= set(new)
                and all(new[key] == value for key, value in old.items()), 'old_catalog_unchanged_' + category)
        added[category] = {key: new[key] for key in sorted(set(new) - set(old))}
        permitted = {NEW_TABLE} if category == 'tables' else set()
        if category in {'columns','constraints','indexes','triggers'}:
            permitted = {key for key in added[category] if key.split(':')[0] == NEW_TABLE}
        require(set(added[category]) <= permitted, 'only_new_review_catalog_' + category)
    require(NEW_TABLE not in before['tables'] and set(added['tables']) == {NEW_TABLE}, 'one_new_review_table')
    return added


def normalize_added_roles(added, role_mapping):
    """Map only typed role fields; SQL, definitions and old catalogs are untouched."""
    require(type(role_mapping) is dict and set(role_mapping.values()) == {'quillmd_owner','quillmd_runtime'}
            and len(role_mapping) == 2 and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,62}', key) for key in role_mapping),
            'explicit_two_role_mapping')
    result = json.loads(json.dumps(added))
    for category in ('tables','indexes'):
        for row in result[category].values():
            require(row['owner'] in role_mapping, 'rehearsed_owner_mapped')
            row['owner'] = role_mapping[row['owner']]
    for row in result['tables'].values():
        for acl in row['privileges']:
            require(acl['grantor'] in role_mapping and acl['grantee'] in role_mapping, 'rehearsed_acl_roles_mapped')
            acl['grantor'], acl['grantee'] = role_mapping[acl['grantor']], role_mapping[acl['grantee']]
        row['privileges'].sort(key=lambda acl: (acl['grantor'],acl['grantee'],acl['privilege'],acl['grantable']))
    return result


def rehearsal_contract(plan, before_catalog, after_catalog, *, server_version_num, role_mapping):
    """Pure contract builder. The caller separately proves the isolated rehearsal."""
    result = dict(format=SCHEMA_FORMAT, base=BASE, candidate=plan['candidate'],
        source_sha256=plan['source_sha256'], migration=MIGRATION,
        migration_sha256=plan['source_sha256'][MIGRATION_PATH],
        postgresql_server_version_num=str(server_version_num), role_mapping=role_mapping,
        catalog_additions=normalize_added_roles(catalog_additions(before_catalog, after_catalog), role_mapping))
    validate_schema_contract(result, plan)
    return result


def validate_schema_contract(contract, plan):
    require(type(contract) is dict and set(contract) == {'format','base','candidate','source_sha256','migration',
        'migration_sha256','postgresql_server_version_num','role_mapping','catalog_additions'}, 'closed_schema_contract')
    require(contract['format'] == SCHEMA_FORMAT and contract['base'] == BASE
            and contract['candidate'] == plan['candidate'] and contract['source_sha256'] == plan['source_sha256']
            and contract['migration'] == MIGRATION and contract['migration_sha256'] == plan['source_sha256'][MIGRATION_PATH],
            'candidate_migration_schema_binding')
    require(re.fullmatch(r'17[0-9]{4}', contract['postgresql_server_version_num']), 'rehearsed_postgresql17')
    roles = contract['role_mapping']
    require(type(roles) is dict and len(roles) == 2 and set(roles.values()) == {'quillmd_owner','quillmd_runtime'}
            and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,62}', key) for key in roles), 'explicit_two_role_mapping')
    added = contract['catalog_additions']
    empty = {key: {} for key in CATALOG_KEYS}
    require(catalog_additions(empty, added) == added, 'finite_measured_schema_delta')
    table = added['tables'][NEW_TABLE]
    require(table['owner'] == 'quillmd_owner' and table['rls'] is False and table['force_rls'] is False
            and table['persistence'] == 'p' and table['kind'] == 'r' and table['partition'] is False
            and table['options'] is None and table['tablespace'] == '' and table['access_method'] == 'heap', 'new_review_table_owner_shape')
    privileges = table['privileges']
    owner = {'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'}
    expected = [{'grantor':'quillmd_owner','grantee':grantee,'privilege':p,'grantable':False}
        for grantee, allowed in [('quillmd_owner',owner),('quillmd_runtime',{'SELECT','INSERT','UPDATE','DELETE'})] for p in allowed]
    key = lambda row: (row['grantor'],row['grantee'],row['privilege'],row['grantable'])
    require(sorted(privileges,key=key) == sorted(expected,key=key), 'exact_new_review_privileges')
    wanted = {'id':('uuid',True),'created_at':('timestamp with time zone',True),'review_digest':('character varying(64)',True),
        'review':('jsonb',True),'choices':('jsonb',True),'approved_at':('timestamp with time zone',True),
        'base_decision_id':('uuid',False),'previous_id':('uuid',False),'run_id':('uuid',True),'user_id':('uuid',True)}
    columns = list(added['columns'].values())
    require(len(columns) == len(wanted) and {row['name']:(row['type'],row['not_null']) for row in columns} == wanted
            and all(row['default'] is None and row['identity'] == row['generated'] == '' and row['acl'] is None
                    and row['has_missing'] is False and row['missing_value'] is None for row in columns), 'exact_new_review_columns')
    require(set(added['triggers']) == {NEW_TABLE + ':' + NEW_TRIGGER}, 'one_append_only_trigger')
    trigger = added['triggers'][NEW_TABLE + ':' + NEW_TRIGGER]
    require(trigger['enabled'] == 'O' and trigger['type'] == 27 and trigger['function_schema'] == 'public'
            and trigger['function'] == 'quillmd_append_only' and trigger['arguments_hex'] == '' and trigger['when'] is None
            and trigger['columns'] == '' and trigger['constraint'] == 0 and trigger['deferrable'] is False
            and trigger['initially_deferred'] is False, 'complete_append_only_trigger')
    require(added['constraints'] and added['indexes']
            and all(row['validated'] is True for row in added['constraints'].values())
            and all(row['valid'] is True and row['ready'] is True and row['live'] is True
                    and row['owner'] == 'quillmd_owner' for row in added['indexes'].values()), 'valid_new_review_keys')
    constraints = list(added['constraints'].values())
    foreign = {row['definition'] for row in constraints if row['type'] == 'f'}
    wanted_foreign = {
        'FOREIGN KEY (base_decision_id) REFERENCES core_codingdecision(id) DEFERRABLE INITIALLY DEFERRED',
        'FOREIGN KEY (previous_id) REFERENCES core_codingsourcedecision(id) DEFERRABLE INITIALLY DEFERRED',
        'FOREIGN KEY (run_id) REFERENCES core_codingrun(id) DEFERRABLE INITIALLY DEFERRED',
        'FOREIGN KEY (user_id) REFERENCES core_user(id) DEFERRABLE INITIALLY DEFERRED'}
    require(len(constraints) == 6 and foreign == wanted_foreign
            and [row['definition'] for row in constraints if row['type'] == 'p'] == ['PRIMARY KEY (id)']
            and [row['definition'] for row in constraints if row['type'] == 'u'] == ['UNIQUE (previous_id)'],
            'exact_source_review_foreign_and_unique_keys')
    index = added['indexes'].get(NEW_TABLE + ':coding_source_first_once')
    require(len(added['indexes']) == 6 and index is not None and index['unique'] is True and index['primary'] is False
            and index['definition'] == 'CREATE UNIQUE INDEX coding_source_first_once ON public.' + NEW_TABLE
                + ' USING btree (run_id) WHERE (previous_id IS NULL)', 'first_source_review_unique_partial_index')


def load_schema_contract(plan):
    raw = prior.backup_restore.read_private(Path(plan['schema_contract_path']), 4 * 1024**2)
    require(prior.sha(raw) == plan['schema_contract_sha256'], 'schema_contract_bytes')
    contract = json.loads(raw); validate_schema_contract(contract, plan)
    return contract, raw


def validate_migration_source(plan, root):
    raw = (root / MIGRATION_PATH).read_bytes()
    require(prior.sha(raw) == plan['source_sha256'][MIGRATION_PATH], 'migration_source_pin')
    # Full syntax admission, not an import or a migration operation name check.
    # Covers imports, exact fields/options/dependency and sole literal guard SQL.
    syntax = ast.dump(ast.parse(raw), include_attributes=False).encode()
    require(prior.sha(syntax) == MIGRATION_AST_SHA256, 'exact_create_model_and_append_only_sql')
    return dict(migration=MIGRATION, source_sha256=prior.sha(raw), ast_sha256=prior.sha(syntax))


def migration_source():
    return '''import os,django
os.environ['DJANGO_SETTINGS_MODULE']='quillmd.settings'
django.setup()
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
with connection.cursor() as c:
 c.execute('SELECT current_database(),current_user')
 assert c.fetchone()==('quillmd_fresh','quillmd_owner')
e=MigrationExecutor(connection);target=[('core','0032_coding_source_decision')]
assert [(m.app_label,m.name,b)for m,b in e.migration_plan(target)]==[('core','0032_coding_source_decision',False)]
with transaction.atomic():e.migrate(target)
print('coding_completeness_additive_migration_committed')
'''


def migrate(original):
    opts = prior.database_options(original, owner=True)
    env = {k:v for k,v in os.environ.items() if k in {'PATH','LANG','HOME','USER'}}
    env.update({k:v for k,v in dotenv_values(stream=io.StringIO(original.decode()), interpolate=False).items() if isinstance(v,str)})
    env.update(QUILLMD_ENV_MANAGED='1', QUILLMD_DB_USER=opts['user'], QUILLMD_DB_PASSWORD=opts['password'],
        PGOPTIONS=opts['options'], PYTHONDONTWRITEBYTECODE='1')
    result = prior.command([str(prior.APP / '.venv/bin/python'),'-B','-c',migration_source()], cwd=prior.APP, env=env, timeout=90)
    require(result.strip() == b'coding_completeness_additive_migration_committed', 'migration_receipt')


def validate_static_stage(plan, staged):
    """Admit only candidate aliases, immutable hashed twins and one manifest."""
    wanted = {'.','staticfiles.json'}
    for name in plan['static']:
        raw = (SOURCE / 'rebuild/static' / name).read_bytes()
        require(prior.sha(raw) == plan['source_sha256']['rebuild/static/' + name], 'staged_static_source_pin')
        suffix = Path(name).suffix
        hashed = name[:-len(suffix)] + '.' + hashlib.md5(raw).hexdigest()[:12] + suffix
        for target, data in ((name,raw),(hashed,raw),(name+'.gz',gzip.compress(raw,mtime=0)),
                (hashed+'.gz',gzip.compress(raw,mtime=0))):
            wanted.add(target)
            require(staged.get(target,{}).get('sha256') == prior.sha(data)
                    and staged[target]['size'] == len(data) and staged[target]['kind'] == 'file'
                    and staged[target]['mode'] == 0o644, 'exact_candidate_static_bytes')
    require(set(staged) == wanted and staged['.']['kind'] == 'directory'
            and staged['staticfiles.json']['kind'] == 'file' and staged['staticfiles.json']['mode'] == 0o644,
            'exact_static_stage_population')


def migration_preserved(before, after, contract):
    require(set(before) == set(after), 'complete_snapshot_population')
    require(set(after['tables']) == set(before['tables']) | {NEW_TABLE} and NEW_TABLE not in before['tables'], 'one_new_empty_table')
    require(after['tables'][NEW_TABLE] == [0, hashlib.sha256(TABLE_FINGERPRINT_CONTRACT.encode()+b'\0'+(0).to_bytes(8,'big')).hexdigest()],
            'no_source_review_created')
    for name, value in before['tables'].items():
        if name != 'django_migrations': require(after['tables'][name] == value, 'all_existing_rows_preserved')
    old_ledger, new_ledger = before['migration_ledger'], after['migration_ledger']
    require(new_ledger[:-1] == old_ledger and len(new_ledger) == len(old_ledger)+1
            and new_ledger[-1][1:3] == ['core',MIGRATION] and new_ledger[-1][3], 'exact_migration_ledger_append')
    require(before['tables']['django_migrations'][0] == len(old_ledger)
            and after['tables']['django_migrations'][0] == len(new_ledger)
            and sorted(after['migrations']) == sorted(before['migrations']+[['core',MIGRATION]]), 'only_one_migration_record')
    require(before['postgresql_server_version_num'] == after['postgresql_server_version_num']
            == contract['postgresql_server_version_num'], 'same_rehearsed_postgresql_version')
    require(catalog_additions(before['catalog'],after['catalog']) == contract['catalog_additions'], 'exact_rehearsed_schema_additions')
    for category in ('schema','constraints','indexes','triggers'):
        require([row for row in after[category] if row[0] != NEW_TABLE] == before[category], 'old_' + category + '_preserved')
    require(set(before['sequences']) == set(after['sequences']), 'no_added_sequence')
    for name, row in before['sequences'].items():
        expected = [row[0]+int(row[1]),True] if name == 'django_migrations_id_seq' else row
        require(after['sequences'][name] == expected, 'only_migration_sequence_advance')
    require(str(after['sequences']['django_migrations_id_seq'][0]) == new_ledger[-1][0], 'migration_ledger_sequence_binding')
    changed = {'tables','migrations','migration_ledger','schema','constraints','indexes','triggers','sequences','catalog'}
    require(all(before[key] == after[key] for key in before.keys()-changed), 'other_snapshot_metadata_preserved')
    require(not any(after['pending'].values()), 'no_provider_work_during_install')
    return dict(all_existing_rows_preserved=True, all_existing_catalog_preserved=True, new_tables=[NEW_TABLE],
        new_decisions=0, migrations_executed=1, provider_calls=0)


def snapshot(original):
    """Capture the complete existing watched set in one read-only transaction.

    This new contract is deliberately distinct from historical aggregate MD5
    receipts. Old receipts/controllers remain unchanged and are not rehashed.
    """
    import psycopg
    from psycopg import sql
    with psycopg.connect(**prior.database_options(original)) as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        require(connection.execute("SELECT current_database(),current_user,current_setting('transaction_read_only')").fetchone()
                == ('quillmd_fresh', 'quillmd_runtime', 'on'), 'readonly_snapshot')
        connection.execute("SET LOCAL statement_timeout='90s'")
        connection.execute("SET LOCAL work_mem='4MB'")
        tables = [x[0] for x in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        rows = {name: table_fingerprint(connection, name) for name in tables}
        migration_rows = [list(x) for x in connection.execute('SELECT app,name FROM public.django_migrations ORDER BY app,name')]
        migration_ledger = [[str(v) for v in row] for row in connection.execute(
            'SELECT id,app,name,applied FROM public.django_migrations ORDER BY id')]
        pending = {}
        for table, states in [('core_job', ('queued', 'running')), ('core_codingrun', ('queued', 'running')),
                ('core_aistagereceipt', ('reserved', 'sending', 'received')),
                ('core_templatepreparation', ('queued', 'inventory', 'proposer', 'checker')),
                ('core_templatedefinitionpreparation', ('queued', 'inventory', 'proposer', 'checker'))]:
            pending[table] = connection.execute(sql.SQL('SELECT count(*) FROM {} WHERE state=ANY(%s)').format(
                sql.Identifier('public', table)), (list(states),)).fetchone()[0]
        schema = [list(x) for x in connection.execute("""SELECT c.relname,pg_get_userbyid(c.relowner),c.relacl::text,
            a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid
            WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum""")]
        triggers = [list(x) for x in connection.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""")]
        constraints = [list(x) for x in connection.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid)
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' ORDER BY c.relname,k.conname""")]
        indexes = [list(x) for x in connection.execute("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname")]
        functions = [list(x) for x in connection.execute("""SELECT p.proname,pg_get_function_identity_arguments(p.oid),
            md5(pg_get_functiondef(p.oid)),pg_get_userbyid(p.proowner),p.proacl::text
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind='f'
            ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)""")]
        sequences = {}
        for (name,) in connection.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename"):
            sequences[name] = list(connection.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(
                sql.Identifier('public', name))).fetchone())
        return dict(table_fingerprint_contract=TABLE_FINGERPRINT_CONTRACT, tables=rows,
            catalog=catalog(connection), postgresql_server_version_num=connection.execute("SHOW server_version_num").fetchone()[0],
            migrations=migration_rows, migration_ledger=migration_ledger, schema=schema, triggers=triggers,
            constraints=constraints, indexes=indexes, functions=functions, sequences=sequences, pending=pending,
            latest_enrolled_encounter=str(connection.execute("SELECT max(created_at) FROM public.core_encounter WHERE created_by_id='5f4d1a3d-eeb6-4207-b1df-4597dc696e82'").fetchone()[0]))


def declared_baseline(plan):
    """Load a fresh, purpose-bound observation; no native state is changed."""
    raw = prior.backup_restore.read_private(Path(plan['baseline_path']), 32 * 1024**2)
    require(prior.sha(raw) == plan['baseline_sha256'], 'declared_baseline_bytes')
    baseline = json.loads(raw)
    require(baseline['read_only'] is True and baseline['native_mutations'] == 0
            and baseline['provider_calls'] == 0 and baseline['coordination_exclusion_acquired'] is False,
            'declared_readonly_observation')
    require(baseline['installed_base'] == BASE and baseline['candidate'] == plan['candidate']
            and baseline['source_worktree'] == plan['source_worktree']
            and baseline['source_sha256'] == plan['source_sha256'], 'declared_baseline_source_binding')
    require(baseline['environment_sha256'] == plan['environment_before_sha256'], 'declared_baseline_environment')
    started = datetime.fromisoformat(baseline['capture_started_at'])
    captured = datetime.fromisoformat(baseline['captured_at'])
    now = datetime.now(timezone.utc)
    require(started.tzinfo is not None and captured.tzinfo is not None
            and 0 <= (captured - started).total_seconds()
            and 0 <= (now - captured).total_seconds() <= (now - started).total_seconds() <= 3600,
            'fresh_declared_baseline')
    require(baseline['database']['table_fingerprint_contract'] == TABLE_FINGERPRINT_CONTRACT,
            'declared_snapshot_contract')
    require(not any(baseline['database']['pending'].values()), 'declared_baseline_pending_work')
    return baseline, raw


def compare_declared_baseline(declared, locked, prepared):
    """Only a service-health refresh may precede the strict locked baseline."""
    require(declared['installed_changed_source_sha256'] ==
            {name: entry['sha256'] for name, entry in prepared['before'].items()},
            'declared_original_source_bytes')
    for key in ('configuration', 'files', 'static'):
        require(declared[key] == locked[key], 'declared_' + key + '_preserved')
    require(declared['foreign_services'] == locked['services'], 'declared_foreign_services_preserved')
    before, after = declared['database'], locked['database']
    require(set(before) == set(after) and all(before[k] == after[k] for k in before if k != 'tables'),
            'declared_database_metadata_preserved')
    old, new = before['tables'], after['tables']
    require(set(old) == set(new) and 'core_servicehealth' in old, 'declared_table_population_preserved')
    changes = [name for name in old if old[name] != new[name]]
    require(set(changes) <= {'core_servicehealth'} and old['core_servicehealth'][0] == new['core_servicehealth'][0],
            'only_predeclared_servicehealth_refresh')
    return dict(declared_baseline_compared_before_stop=True,
        permitted_database_table_changes=changes, foreign_services_preserved=True,
        configuration_preserved=True, files_preserved=True, static_preserved=True,
        installed_source_preserved=True, other_database_state_preserved=True)


def failure_diagnostics(error):
    """Retain safe classifications and code locations, never exception text/SQL.

    A previous operational failure retained only its class. SQLSTATE and the
    precise operator stage distinguish a database rejection from a transport
    failure; fixed connection categories preserve useful libpq evidence without
    copying credentials, SQL parameters or source content into a receipt.
    """
    import psycopg
    name = type(error).__name__
    result = {'failure_type': name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', name) else 'Exception',
              'reason': 'protected_operational_failure', 'sqlstate': None, 'connection_failure': None}
    if isinstance(error, Refusal):
        result['reason'] = 'installation_invariant_refused'
    if isinstance(error, psycopg.Error):
        state = error.sqlstate
        if isinstance(state, str) and re.fullmatch('[0-9A-Z]{5}', state):
            result['sqlstate'] = state
        if isinstance(error, psycopg.OperationalError):
            message = str(error).casefold()
            categories = (('connection refused', 'connection_refused'),
                ('timeout expired', 'connection_timeout'), ('connection timeout', 'connection_timeout'),
                ('password authentication failed', 'authentication_failed'),
                ('could not translate host name', 'name_resolution_failed'),
                ('server closed the connection unexpectedly', 'server_closed_connection'),
                ('connection is closed', 'connection_closed'), ('ssl syscall error', 'ssl_transport_error'))
            result['connection_failure'] = next((code for marker, code in categories if marker in message),
                                                'unclassified_operational_error')
    if isinstance(error, OSError) and type(error.errno) is int:
        result['errno'] = error.errno
    locations = []
    frame = error.__traceback__
    allowed = {'activate_coding_completeness.py', 'activate_coordinated_workflow.py', 'activate_rowan_corti.py'}
    while frame:
        filename = Path(frame.tb_frame.f_code.co_filename).name
        if filename in allowed:
            locations.append({'module': filename, 'line': frame.tb_lineno})
        frame = frame.tb_next
    result['operator_locations'] = locations
    return result


def verify_original_before_resume(original, guard, prepared):
    """HEAD alone does not prove the installed index or working files are old."""
    require(prior.git('rev-parse', 'HEAD').decode().strip() == BASE
            and not prior.git('status', '--porcelain', '--untracked-files=no').strip(),
            'clean_original_checkout_before_recovery')
    require((prior.APP / '.env').read_bytes() == original, 'original_environment_before_recovery')
    for name, entry in prepared['before'].items():
        guard.file_proof(prior.ROOT, name, entry, prepared['binding'], revision=BASE)
    for name in prepared['after'].keys() - prepared['before'].keys():
        path = prior.ROOT / name
        require(not path.exists() and not path.is_symlink(), 'new_source_absent_before_recovery')


def stop_failed_resume(host):
    """Attempt every stop and verify every unit, even if an earlier stop failed."""
    result = {'stop_errors': {}, 'state_errors': {}, 'units_inactive': {}}
    for unit in prior.UNITS:
        try:
            host.service('stop', unit)
        except BaseException as error:
            result['stop_errors'][unit] = failure_diagnostics(error)
    for unit in prior.UNITS:
        try:
            state = host.state(unit)
            result['units_inactive'][unit] = state.get('ActiveState') == 'inactive' and state.get('MainPID') == '0'
        except BaseException as error:
            result['units_inactive'][unit] = False
            result['state_errors'][unit] = failure_diagnostics(error)
    result['all_units_inactive'] = all(result['units_inactive'].values())
    return result


def execute(plan, digest):
    validate_plan(plan)
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.is_file() and re.fullmatch('[a-f0-9]{40}', commit),
            'ruled_declaration_required')
    text = declaration.read_bytes()
    require(all(value.encode() in text for value in (digest, plan['candidate'], FORMAT)), 'declaration_exact_plan')
    repo = Path(prior.command(['git', '-C', str(declaration.parent), 'rev-parse', '--show-toplevel']).decode().strip())
    require(prior.command(['git', '-C', str(repo), 'show', commit + ':' + declaration.relative_to(repo).as_posix()])
            == text, 'committed_declaration_bytes')
    original = prior.backup_restore.read_private(prior.APP / '.env', 65536)
    require(prior.sha(original) == plan['environment_before_sha256'], 'environment_before_pin')
    active = render_environment(original, plan['candidate'], plan['environment'])
    declared, declared_raw = declared_baseline(plan)
    schema, schema_raw = load_schema_contract(plan)
    migration_admission = validate_migration_source(plan, SOURCE)
    guard = prior.source_guard(); prepared = prior.source_plan(plan, guard)
    prior.command(['bash', str(SOURCE / 'scripts/check-citation.sh'), plan['candidate']], cwd=SOURCE, timeout=120)
    out = Path(plan['evidence_directory']); out.mkdir(mode=0o700)
    prior.write_new(out / 'plan.json', plan)
    prior.write_new(out / 'declared-baseline.json', declared_raw)
    prior.write_new(out / 'schema-contract.json', schema_raw)
    prior.write_new(out / 'migration-source-admission.json', migration_admission)
    cipher = prior.backup_restore.key_at(prior.legacy.KEY)
    prior.write_new(out / 'environment-before.fernet', cipher.encrypt(original))
    prior.write_new(out / 'environment-after.fernet', cipher.encrypt(active))
    stopped = resumed = resume_started = publication_attempted = migration_attempted = False
    stage = 'coordination_locks'
    host = prior.legacy.Host(prior.managed_helper)
    with ExitStack() as coordination:
        try:
            primitives = prior.legacy.static_primitives()
            prior.activation_exclusion.bind_runtime(prior.APP / '.runtime')
            stage = 'coordination_locks'
            coordination.enter_context(prior.legacy.operation_locks())
            coordination.enter_context(prior.activation_exclusion.hold(
                'coding-completeness:' + plan['candidate'][:12], timeout=30))
            stage = 'baseline_static'
            static_before = primitives.static_inventory(prior.APP / 'staticfiles')
            baseline = {'static': static_before}
            stage = 'baseline_configuration'; baseline['configuration'] = host.configuration()
            stage = 'baseline_foreign_services'; baseline['services'] = prior.foreign_services()
            stage = 'baseline_database'; baseline['database'] = snapshot(original)
            stage = 'baseline_clinical_files'; baseline['files'] = prior.private_storage.inventory(Path('/var/lib/quillmd/files'))
            stage = 'baseline_pending_check'; unchanged(baseline['database'], baseline['database'])
            stage = 'retain_baseline'; prior.write_new(out / 'baseline.json', baseline)
            stage = 'declared_baseline_comparison'
            refreshed, refreshed_raw = declared_baseline(plan)
            require(refreshed_raw == declared_raw and refreshed == declared, 'declared_baseline_recheck')
            comparison = compare_declared_baseline(declared, baseline, prepared)
            stage = 'original_source_before_stop'
            verify_original_before_resume(original, guard, prepared)
            stage = 'migration_pre_stop_admission'
            require(NEW_TABLE not in baseline['database']['tables']
                    and ['core', MIGRATION] not in baseline['database']['migrations'], 'new_migration_not_consumed')
            require(baseline['database']['postgresql_server_version_num'] == schema['postgresql_server_version_num'], 'same_rehearsed_postgresql_version')
            current_schema, current_schema_raw = load_schema_contract(plan)
            require(current_schema == schema and current_schema_raw == schema_raw, 'schema_contract_recheck')
            validate_migration_source(plan, SOURCE)
            stage = 'static_staging'
            if plan['static']:
                primitives.static_delta = prior.static_delta
                static_stage, static_staged_before, staged = prior.stage_static(plan, out, primitives)
                require(static_staged_before == static_before, 'static_staging_baseline')
                validate_static_stage(plan, staged)
            stage = 'retain_pre_stop_comparison'
            prior.write_new(out / 'pre-stop-comparison.json', comparison)
            stage = 'stop_owned_services'; stopped = True
            for unit in prior.UNITS:
                host.service('stop', unit)
            stage = 'verify_owned_services_stopped'
            require(all(host.state(unit)['ActiveState'] == 'inactive' and host.state(unit)['MainPID'] == '0'
                        for unit in prior.UNITS), 'owned_units_drained')
            stage = 'database_after_stop'; after_stop = snapshot(original)
            stage = 'retain_database_after_stop'
            prior.write_new(out / 'database-after-stop.json', after_stop)
            stage = 'database_after_stop'; unchanged(baseline['database'], after_stop)
            stage = 'source_publication'; publication_attempted = True
            prior.publish_source(plan, guard, prepared)
            stage = 'migration_source_after_publication'
            validate_migration_source(plan, prior.ROOT)
            stage = 'additive_migration'; migration_attempted = True
            migrate(original)
            stage = 'database_after_migration'; after_migration = snapshot(original)
            stage = 'retain_database_after_migration'
            prior.write_new(out / 'database-after-migration.json', after_migration)
            stage = 'migration_preservation'
            migration_proof = migration_preserved(after_stop, after_migration, schema)
            stage = 'static_publication'
            if plan['static']:
                static_after = primitives.install_static(prior.APP / 'staticfiles', static_stage, static_before, staged)
            else:
                static_after = primitives.static_inventory(prior.APP / 'staticfiles')
                require(static_after == static_before, 'static_bytes_unchanged')
            stage = 'environment_publication'
            require((prior.APP / '.env').read_bytes() == original, 'environment_concurrency')
            temporary = prior.APP / '.coding-completeness-env-pending'
            prior.write_new(temporary, active); temporary.replace(prior.APP / '.env')
            stage = 'database_before_resume'; before_resume = snapshot(active)
            stage = 'retain_database_before_resume'
            prior.write_new(out / 'database-before-resume.json', before_resume)
            stage = 'database_before_resume'; unchanged(after_migration, before_resume)
            stage = 'clinical_files_before_resume'
            require(prior.private_storage.inventory(Path('/var/lib/quillmd/files')) == baseline['files'],
                    'all_clinical_files_preserved')
            stage = 'configuration_before_resume'
            require(host.configuration() == baseline['configuration'], 'configuration_preserved')
            stage = 'foreign_services_before_resume'
            require(prior.foreign_services() == baseline['services'], 'foreign_services_preserved')
            stage = 'retain_preservation'
            evidence_sha256 = {name: prior.sha((out / name).read_bytes()) for name in
                ('baseline.json', 'database-after-stop.json', 'database-after-migration.json', 'database-before-resume.json')}
            prior.write_new(out / 'pre-resume-preservation.json', dict(**migration_proof,
                files_preserved=True, static_inventory=static_after, evidence_sha256=evidence_sha256,
                declared_baseline_sha256=plan['baseline_sha256'],
                pre_stop_comparison_sha256=prior.sha((out / 'pre-stop-comparison.json').read_bytes()),
                schema_contract_sha256=plan['schema_contract_sha256'],
                environment_delta=['QUILLMD_RELEASE_SHA']))
            stage = 'resume_owned_services'; resume_started = True
            for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                host.service('start', unit)
            stage = 'normal_https_health'; health = prior.await_health(plan['candidate'])
            stage = 'verify_owned_services_resumed'
            require(all(host.state(unit)['ActiveState'] == 'active' for unit in prior.UNITS), 'owned_units_active')
            resumed = True
            stage = 'configuration_after_resume'
            require(host.configuration() == baseline['configuration'], 'configuration_preserved_after_resume')
            stage = 'foreign_services_after_resume'
            require(prior.foreign_services() == baseline['services'], 'foreign_services_preserved_after_resume')
            result = dict(format=FORMAT, installed_revision=plan['candidate'], complete=True, health=health,
                migrations_executed=1, provider_calls=0, clinician_decisions_created=0,
                migration=MIGRATION, schema_contract_sha256=plan['schema_contract_sha256'],
                evidence_sha256=evidence_sha256, plan_sha256=digest,
                declared_baseline_sha256=plan['baseline_sha256'],
                pre_stop_comparison_sha256=prior.sha((out / 'pre-stop-comparison.json').read_bytes()),
                declaration_commit=commit, declaration_sha256=prior.sha(text),
                environment_delta=['QUILLMD_RELEASE_SHA'], strict_preservation_ends_before_resume=True)
            stage = 'retain_completion'; prior.write_new(out / 'installation-complete.json', result)
            return result
        except BaseException as error:
            # Drain before retaining evidence: a disk/write error must not leave
            # newly started units running after an unsuccessful installation.
            drain = stop_failed_resume(host) if resume_started else None
            prior.write_new(out / 'failure.json', dict(format=FORMAT, complete=False, stage=stage,
                **failure_diagnostics(error), stopped=stopped, resumed=resumed, resume_started=resume_started,
                publication_attempted=publication_attempted, migration_attempted=migration_attempted,
                failed_resume_drain=drain, provider_calls=0, automatic_retry=False))
            if drain is not None:
                prior.write_new(out / 'failed-resume-drain.json', drain)
                require(drain['all_units_inactive'], 'failed_resume_drain_incomplete')
            if stopped and not publication_attempted and not resume_started:
                try:
                    verify_original_before_resume(original, guard, prepared)
                except BaseException as recovery_error:
                    prior.write_new(out / 'original-recovery-refused.json', failure_diagnostics(recovery_error))
                    raise Refusal('original_recovery_refused_inspect_retained_evidence') from None
                for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                    host.service('start', unit)
                prior.write_new(out / 'original-release-resumed.json', {'release': BASE})
            raise Refusal('installation_failed_inspect_retained_evidence') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--plan'); parser.add_argument('--plan-sha256')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(dict(inert=True, database_queries=0, provider_calls=0, service_actions=0))); return
    os.umask(0o077); sys.dont_write_bytecode = True
    plan, digest = prior.private_json(Path(args.plan))
    require(digest == args.plan_sha256, 'private_plan_hash')
    validate_plan(plan)
    with bound_primitives(plan['static']):
        print(json.dumps(execute(plan, digest), sort_keys=True))


if __name__ == '__main__':
    main()
