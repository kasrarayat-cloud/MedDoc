"""Bounded PostgreSQL projections of an immutable reference for approval.

Generation searches the complete Index. Approval already has candidate entry
identities, so it needs only those authoritative entries and their ancestors,
plus the selected reportable codes and complete governing Tabular chains. No
path, description or instruction supplied by the model is used as reference.
"""
import json
import re
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import connections

from .coding_terminology import FORMAT, _governing_node, normalize_code
from .models import CodingRelease


MAX_SELECTIONS = 64
MAX_IDENTITIES = 2048
MAX_DEPTH = 33
MAX_QUERY_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
INDEX_ID = re.compile(r'idx:[0-9a-f]{64}\Z')


def _requested(run, selections):
    if (type(selections) is not dict or set(selections) != {'selected_ids', 'overrides'}
            or type(selections['selected_ids']) is not list or type(selections['overrides']) is not dict):
        raise ValidationError('Invalid sparse coding selection.')
    ids, overrides = selections['selected_ids'], selections['overrides']
    if (len(ids) > MAX_SELECTIONS or any(type(value) is not str for value in ids)
            or len(ids) != len(set(ids)) or any(key not in ids for key in overrides)):
        raise ValidationError('Invalid or oversized sparse coding selection.')
    rows = run.result.get('suggestions', [])
    if type(rows) is not list or len(rows) > MAX_SELECTIONS:
        raise ValidationError('Invalid saved coding suggestions.')
    by_id = {}
    for row in rows:
        if type(row) is not dict or type(row.get('id')) is not str or row['id'] in by_id:
            raise ValidationError('Invalid or repeated saved coding suggestion.')
        by_id[row['id']] = row
    candidates = run.result.get('candidates', {})
    if type(candidates) is not dict:
        raise ValidationError('Invalid saved coding candidates.')
    codes, entries = set(), set()
    for key in ids:
        if key not in by_id:
            raise ValidationError('Sparse selection must identify a saved suggestion.')
        row = by_id[key]
        override = overrides.get(key)
        if override is not None and (type(override) is not dict or set(override) != {'code', 'reason'}):
            raise ValidationError('A coding replacement needs its code and reason.')
        code = override['code'] if override is not None else row.get('code')
        if row.get('system') == 'CPT':
            continue
        if row.get('system') != 'ICD-10-CM':
            raise ValidationError('Unrecognized selected coding system.')
        try:
            if normalize_code(code) != code:
                raise ValueError()
        except ValueError as exc:
            raise ValidationError('Invalid selected ICD-10-CM code.') from exc
        available = candidates.get(key, [])
        if type(available) is not list or len(available) > 48 or any(type(c) is not dict for c in available):
            raise ValidationError('Invalid saved coding candidates.')
        candidate = next((c for c in available if c.get('code') == code and c.get('system') == 'ICD-10-CM'), None)
        if candidate is None:
            raise ValidationError('The selected code has no saved authoritative candidate.')
        aliases = candidate.get('source_aliases', [])
        if type(aliases) is not list or len(aliases) > MAX_SELECTIONS:
            raise ValidationError('Invalid saved Index aliases.')
        wanted = [candidate.get('entry_id'), *aliases]
        if any(type(value) is not str or not INDEX_ID.fullmatch(value) for value in wanted):
            raise ValidationError('Invalid authoritative Index identity.')
        entries.update(wanted)
        codes.add(code)
    if len(entries) > MAX_IDENTITIES:
        raise ValidationError('Too many Index identities for one approval.')
    return codes, entries


class _Projection:
    def __init__(self, metadata):
        self.connection = connections[metadata._state.db or 'default']
        if self.connection.vendor != 'postgresql':
            raise ValidationError('Sparse coding reference reads require PostgreSQL.')
        self.table = self.connection.ops.quote_name(CodingRelease._meta.db_table)
        self.binding = [metadata.pk, metadata.release_id, metadata.digest]
        self.total_bytes = 0

    def read(self, expression, params=()):
        # Expressions are private constants; all identities, paths and values
        # are parameters. Size is checked on the server before JSON is returned.
        query = f'''WITH picked AS (
            SELECT {expression} AS payload FROM {self.table}
            WHERE id = %s AND release_id = %s AND digest = %s
        ) SELECT CASE WHEN octet_length(payload::text) <= %s THEN payload ELSE NULL END,
                 octet_length(payload::text) FROM picked'''
        with self.connection.cursor() as cursor:
            cursor.execute(query, [*params, *self.binding, MAX_QUERY_BYTES])
            row = cursor.fetchone()
        if row is None or type(row[1]) is not int or row[1] > MAX_QUERY_BYTES or row[0] is None:
            raise ValidationError('The bound coding reference is missing, changed or exceeds the projection limit.')
        self.total_bytes += row[1]
        if self.total_bytes > MAX_TOTAL_BYTES:
            raise ValidationError('The selected reference exceeds the bounded approval size.')
        try:
            return json.loads(row[0]) if isinstance(row[0], (str, bytes, bytearray)) else row[0]
        except (ValueError, UnicodeError) as exc:
            raise ValidationError('Invalid stored coding reference projection.') from exc

    def index(self, identities):
        value = self.read('jsonb_path_query_array("index", %s::jsonpath, %s::jsonb)',
            ['$[*] ? (@.id == $ids[*])', json.dumps({'ids': sorted(identities)})])
        if type(value) is not list or len(value) > MAX_IDENTITIES:
            raise ValidationError('Invalid stored Index projection.')
        result = {}
        for entry in value:
            if (type(entry) is not dict or entry.get('id') not in identities
                    or entry['id'] in result or 'parent_id' not in entry):
                raise ValidationError('Missing or duplicate stored Index identity.')
            result[entry['id']] = entry
        if set(result) != identities:
            raise ValidationError('A selected Index entry or ancestor is absent from its bound release.')
        return result

    def nodes(self, identities):
        value = self.read('''(SELECT COALESCE(jsonb_object_agg(wanted, tabular->'nodes'->wanted), '{}'::jsonb)
            FROM unnest(%s::text[]) AS names(wanted) WHERE tabular->'nodes' ? wanted)''', [sorted(identities)])
        if type(value) is not dict or not set(value) <= identities:
            raise ValidationError('Invalid stored Tabular projection.')
        for key, node in value.items():
            if (type(node) is not dict or node.get('id') != key or 'parent' not in node
                    or type(node.get('instructions')) is not list):
                raise ValidationError('Invalid stored Tabular node.')
        return value


def _ancestors(seeds, initial, fetch, parent_key):
    nodes, pending = dict(initial), set(seeds)
    for _ in range(MAX_DEPTH):
        missing = pending - nodes.keys()
        if missing:
            loaded = fetch(missing)
            if set(loaded) != missing:
                raise ValidationError('A coding reference ancestor is missing.')
            nodes.update(loaded)
        next_ids = set()
        for key in pending:
            parent = nodes[key][parent_key]
            if parent is not None:
                if type(parent) is not str or not parent:
                    raise ValidationError('Invalid coding reference ancestor.')
                next_ids.add(parent)
        if not next_ids:
            break
        pending = next_ids
    else:
        raise ValidationError('Cyclic or oversized coding reference ancestry.')
    retained = {}
    for seed in seeds:
        current, seen = seed, set()
        while current is not None:
            if current in seen or current not in nodes or len(seen) >= MAX_DEPTH:
                raise ValidationError('Invalid coding reference ancestry.')
            seen.add(current)
            retained[current] = nodes[current]
            current = nodes[current][parent_key]
    return retained


def selection_reference(metadata, run, selections):
    """Return source-owned sparse reference material for exactly this selection.

    The caller checks the saved release/date snapshot. Every projection also
    binds the immutable CodingRelease primary key, CodeSet and reference digest.
    Accessing deferred index/tabular/provenance ORM fields is unnecessary.
    """
    codes, entries = _requested(run, selections)
    query = _Projection(metadata)
    tabular = query.read('''jsonb_build_object(
        'format', tabular->'format', 'version', tabular->'version',
        'dictionary_sha256', tabular->'dictionary_sha256',
        'index_xml_sha256', tabular->'index_xml_sha256',
        'tabular_xml_sha256', tabular->'tabular_xml_sha256',
        'introduction', tabular->'introduction')''')
    if type(tabular) is not dict or tabular.get('format') != FORMAT or not re.fullmatch(r'20\d\d', str(tabular.get('version'))):
        raise ValidationError('Unsupported bound coding reference format.')
    index = _ancestors(entries, {}, query.index, 'parent_id') if entries else {}
    descriptions = query.read('''(SELECT COALESCE(jsonb_object_agg(wanted, tabular->'codes'->wanted), '{}'::jsonb)
        FROM unnest(%s::text[]) AS names(wanted) WHERE tabular->'codes' ? wanted)''', [sorted(codes)])
    if (type(descriptions) is not dict or set(descriptions) != codes
            or any(type(value) is not str or not value for value in descriptions.values())):
        raise ValidationError('A selected code is not reportable in the bound release.')
    prefixes = set()
    for code in codes:
        raw = code.replace('.', '')
        prefixes.update(raw[:3] + ('.' + raw[3:n] if n > 3 else '') for n in range(3, len(raw) + 1))
    initial = query.nodes(prefixes) if prefixes else {}
    governing = {_governing_node(initial, code) for code in codes}
    if None in governing:
        raise ValidationError('A selected code lacks its governing Tabular node.')
    nodes = _ancestors(governing, initial, query.nodes, 'parent') if governing else {}
    tabular.update(codes=descriptions, nodes=nodes)
    return SimpleNamespace(pk=metadata.pk, id=metadata.pk, release_id=metadata.release_id,
        release=metadata.release, digest=metadata.digest, index=list(index.values()),
        tabular=tabular, _index_lookup=index, projection_bytes=query.total_bytes)
