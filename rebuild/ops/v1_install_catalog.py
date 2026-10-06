"""Read-only PostgreSQL inventory for the source-bound private upgrade contract.

Callers own the repeatable-read transaction and authenticated connection. SQL is
fixed here; identifiers come only from validated catalog names. No row content
is returned except migration/permission metadata, identifiers for those three
metadata tables, and SHA-256/count fingerprints.
"""
import hashlib
import json
import re

from .v1_private_install_adapter import require

METADATA = frozenset({'django_migrations', 'django_content_type', 'auth_permission'})
SCHEMA_FIELDS = ('table_name', 'column_name', 'ordinal_position', 'data_type', 'udt_name',
                 'is_nullable', 'column_default', 'numeric_precision', 'numeric_scale')
FUNCTION_FIELDS = ('name', 'owner', 'language', 'security_definer', 'config', 'acl', 'body', 'definition')
TRIGGER_FIELDS = ('table', 'name', 'function', 'type', 'enabled', 'args', 'when', 'definition')


def identifier(name):
    require(isinstance(name, str) and re.fullmatch('[a-z_][a-z_0-9]*', name), 'Unexpected catalog identifier.')
    return '"' + name + '"'


def read(query, copy_hash, *, before=None):
    tables = [row[0] for row in query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
    for name in tables:
        identifier(name)
    schema = [dict(zip(SCHEMA_FIELDS, row)) for row in query('''SELECT table_name,column_name,
        ordinal_position,data_type,udt_name,is_nullable,column_default,numeric_precision,numeric_scale
        FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position''')]
    constraints = [list(row) for row in query('''SELECT c.conrelid::regclass::text,c.conname,c.contype::text,
        c.confrelid::regclass::text,pg_get_constraintdef(c.oid) FROM pg_constraint c
        JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public'
        ORDER BY c.conrelid::regclass::text,c.conname''')]
    indexes = [list(row) for row in query("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname")]
    functions = [dict(zip(FUNCTION_FIELDS, row)) for row in query('''SELECT p.oid::regprocedure::text,
        pg_get_userbyid(p.proowner),l.lanname,p.prosecdef,p.proconfig,p.proacl::text,p.prosrc,pg_get_functiondef(p.oid)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang
        WHERE n.nspname='public' AND p.prokind='f' ORDER BY p.oid::regprocedure::text''')]
    triggers = [dict(zip(TRIGGER_FIELDS, row)) for row in query('''SELECT c.relname,t.tgname,p.proname,
        t.tgtype,t.tgenabled,encode(t.tgargs,'hex'),pg_get_expr(t.tgqual,t.tgrelid),pg_get_triggerdef(t.oid)
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='public' AND NOT t.tgisinternal
        ORDER BY c.relname,t.tgname''')]
    columns = {name: sorted(row['column_name'] for row in schema if row['table_name'] == name) for name in tables}
    ids = {name: [row[0] for row in query('SELECT id FROM ' + identifier(name) + ' ORDER BY id')] for name in METADATA}
    require(all(len(values) <= 10000 and all(type(value) is int and value > 0 for value in values)
                for values in ids.values()), 'Metadata ID population exceeds the reviewed bound.')
    def where(name, *, old):
        values = before['metadata_ids'][name] if old else ids[name]
        return ' WHERE t.id IN (' + ','.join(str(value) for value in values) + ')' if values else ' WHERE false'
    def fingerprint(name, *, old=False):
        removed = sorted(set(columns[name]) - set(before['columns'][name])) if old else []
        for field in removed:
            identifier(field)
        expression = 'to_jsonb(t)' + ''.join("-'" + field + "'" for field in removed)
        predicate = where(name, old=True) if old and name in METADATA else ''
        return copy_hash('COPY (SELECT (' + expression + ')::text AS value FROM ' + identifier(name)
                         + ' t' + predicate + ' ORDER BY value) TO STDOUT')
    result = {'tables': tables, 'schema': schema, 'constraints': constraints, 'indexes': indexes,
              'catalog': {'functions': functions, 'triggers': triggers}, 'columns': columns,
              'metadata_ids': ids, 'rows': {name: fingerprint(name) for name in tables},
              'unresolved_jobs': int(query("SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')")[0][0]),
              'held_reservations': int(query("SELECT count(*) FROM core_reservation WHERE state='held'")[0][0])}
    if before is not None:
        require(set(before['columns']) <= set(columns), 'Historical table was removed.')
        require(all(set(fields) <= set(columns[name]) for name, fields in before['columns'].items()),
                'Historical column was removed.')
        result.update(old_columns=before['columns'], old_rows={name: fingerprint(name, old=True) for name in before['tables']},
                      new_core_rows={name: result['rows'][name] for name in set(tables) - set(before['tables'])})
        def added_predicate(name):
            values = before['metadata_ids'][name]
            return ' WHERE t.id NOT IN (' + ','.join(str(value) for value in values) + ')' if values else ''
        result['new_noncore_rows'] = {
            'django_migrations': [list(row) for row in query('SELECT t.app,t.name FROM django_migrations t'
                                                            + added_predicate('django_migrations') + ' ORDER BY t.app,t.name')],
            'django_content_type': [list(row) for row in query('SELECT t.app_label,t.model FROM django_content_type t'
                                                             + added_predicate('django_content_type') + ' ORDER BY t.app_label,t.model')],
            'auth_permission': [list(row) for row in query('SELECT c.app_label,c.model,t.codename,t.name FROM auth_permission t'
                  + ' JOIN django_content_type c ON c.id=t.content_type_id' + added_predicate('auth_permission')
                  + ' ORDER BY c.app_label,c.model,t.codename,t.name')]}
    return result


def stream_hash(stream):
    digest, count = hashlib.sha256(), 0
    for value in stream:
        value = bytes(value)
        digest.update(value); count += value.count(b'\n')
    return {'rows': count, 'sha256': digest.hexdigest()}
