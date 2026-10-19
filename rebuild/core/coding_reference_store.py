"""Bounded PostgreSQL projections of an immutable coding reference.

Open-ended generation searches the complete Index. Approval has candidate entry
identities, so it needs only those authoritative entries and their ancestors,
plus the selected reportable codes and complete governing Tabular chains. No
path, description or instruction supplied by the model is used as reference.
Direct predictions have finite code identities instead: their complete Index
route and lexical subtype forests are rediscovered from the stored release.
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
MAX_ROOTS = 32768
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
        # Source negation may refer to a rejected specific subtype of an
        # affirmed parent. Read its dated Index entries again at approval;
        # persisted strings and the selected entry alone are insufficient.
        checks = run.result.get('source_checks', {})
        if type(checks) is not dict or type(checks.get(key, {})) is not dict:
            raise ValidationError('Invalid saved source checks.')
        scope_entries = checks.get(key, {}).get('index_scope_entry_ids', [])
        if type(scope_entries) is not list or len(scope_entries) > MAX_IDENTITIES:
            raise ValidationError('Invalid saved Index assertion scopes.')
        wanted = [candidate.get('entry_id'), *aliases, *scope_entries]
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
        query = f'''WITH picked AS MATERIALIZED (
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
        # JSONpath comparisons against $ids[*] can allocate a large cross
        # product before the outer byte limit is applied. SQL membership over
        # one ordered scan bounds executor working storage independently.
        value = self.read('''(SELECT COALESCE(jsonb_agg(entry ORDER BY ordinal), '[]'::jsonb)
            FROM jsonb_array_elements("index") WITH ORDINALITY AS index_entries(entry, ordinal)
            WHERE entry->>'id' = ANY(%s::text[]))''', [sorted(identities)])
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
        # Expand the stored object once. Re-extracting the large outer JSON for
        # every requested key can repeatedly detoast the complete Tabular file.
        value = self.read('''(SELECT COALESCE(jsonb_object_agg(key, value), '{}'::jsonb)
            FROM jsonb_each(tabular->'nodes') AS node_entries(key, value)
            WHERE key = ANY(%s::text[]))''', [sorted(identities)])
        if type(value) is not dict or not set(value) <= identities:
            raise ValidationError('Invalid stored Tabular projection.')
        for key, node in value.items():
            if (type(node) is not dict or node.get('id') != key or 'parent' not in node
                    or type(node.get('instructions')) is not list):
                raise ValidationError('Invalid stored Tabular node.')
        return value

    def children(self, parents):
        value = self.read('''(SELECT COALESCE(jsonb_agg(entry ORDER BY ordinal), '[]'::jsonb)
            FROM jsonb_array_elements("index") WITH ORDINALITY AS index_entries(entry, ordinal)
            WHERE entry->>'parent_id' = ANY(%s::text[]))''', [sorted(parents)])
        if (type(value) is not list or len(value) > MAX_IDENTITIES
                or any(type(row) is not dict or type(row.get('id')) is not str
                       or not INDEX_ID.fullmatch(row['id']) or row.get('parent_id') not in parents for row in value)
                or len({row['id'] for row in value}) != len(value)):
            raise ValidationError('Invalid prediction Index child projection.')
        return {row['id']:row for row in value}


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
        'introduction', tabular->'introduction',
        'guidelines_sha256', provenance #>> '{manifest,files,guidelines,sha256}')''')
    if type(tabular) is not dict or tabular.get('format') != FORMAT or not re.fullmatch(r'20\d\d', str(tabular.get('version'))):
        raise ValidationError('Unsupported bound coding reference format.')
    guidelines_sha256 = tabular.pop('guidelines_sha256', None)
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
        tabular=tabular, _index_lookup=index, projection_bytes=query.total_bytes,
        guidelines_sha256=guidelines_sha256)


def _prediction_codes(codes):
    if (type(codes) is not list or len(codes) > MAX_SELECTIONS
            or any(type(code) is not str for code in codes)
            or len(codes) != len(set(codes))):
        raise ValidationError('Invalid or oversized prediction code set.')
    try:
        if any(normalize_code(code) != code for code in codes):
            raise ValueError()
    except ValueError as exc:
        raise ValidationError('Invalid prediction ICD-10-CM code.') from exc
    return set(codes)


def _forest(roots, initial, fetch, fetch_children):
    """Complete child closure, with no truncation or silently missing branch."""
    nodes, pending, visited = dict(initial), set(roots), set()
    for _ in range(MAX_DEPTH):
        if len(nodes.keys() | pending) > MAX_IDENTITIES:
            raise ValidationError('Prediction Index scope exceeds the bounded identity limit.')
        missing = pending - nodes.keys()
        if missing:
            loaded = fetch(missing)
            if set(loaded) != missing:
                raise ValidationError('A prediction Index child is missing.')
            nodes.update(loaded)
        children = set()
        for key in pending:
            row = nodes[key]
            if row.get('id') != key or (key in roots and row.get('parent_id') is not None):
                raise ValidationError('Invalid prediction Index root.')
            values = row.get('children')
            if (type(values) is not list or len(values) > MAX_IDENTITIES
                    or any(type(value) is not str or not INDEX_ID.fullmatch(value) for value in values)
                    or len(values) != len(set(values))):
                raise ValidationError('Invalid prediction Index children.')
            for child in values:
                if child in visited or child in pending or child in children:
                    raise ValidationError('Repeated or cyclic prediction Index child.')
                children.add(child)
        visited.update(pending)
        loaded = fetch_children(pending)
        if set(loaded) != children:
            raise ValidationError('Prediction Index parent and child links disagree.')
        if not children:
            break
        if len(nodes.keys() | children) > MAX_IDENTITIES:
            raise ValidationError('Prediction Index scope exceeds the bounded identity limit.')
        nodes.update(loaded)
        for key in pending:
            if any(nodes[child].get('parent_id') != key for child in nodes[key]['children']):
                raise ValidationError('A prediction Index child has a different parent.')
        pending = children
    else:
        raise ValidationError('Prediction Index ancestry exceeds the bounded depth.')
    if len(visited) > MAX_IDENTITIES:
        raise ValidationError('Prediction Index scope exceeds the bounded identity limit.')
    return {key: nodes[key] for key in visited}


def prediction_reference(metadata, codes, *, source_contract=None, source_inventory=None):
    """Recompute finite predictions without materializing a full release.

    Every selected-code route is loaded, including alternative main terms.
    Complete lexical subtype forests retain negation and specificity checks;
    complete Tabular ancestry retains inherited exclusions and instructions.
    This does not consume stored eligibility, model paths or saved scope IDs.
    Oversized or malformed closure refuses without a full-reference fallback.
    """
    from . import coding_engine as engine
    from .source_assertion_coding import CONTRACT as GRAPH_SOURCE_CONTRACT, HISTORY_ROLES
    source_terms = set()
    taxonomy_roles=[]
    if source_inventory is not None:
        # Source terms are a retrieval scope, never evidence for selecting a code.
        # Their complete authoritative families are revalidated by the caller.
        if (type(source_inventory) is not dict
                or type(source_inventory.get('reference_terms')) is not list
                or len(source_inventory['reference_terms']) > MAX_SELECTIONS
                or any(type(t) is not str or not 1 <= len(t) <= 180
                       for t in source_inventory['reference_terms'])
                or any(type(source_inventory.get(k)) is not str
                       or not re.fullmatch(r'[0-9a-f]{64}', source_inventory.get(k, ''))
                       for k in ('source_sha256', 'inventory_sha256'))):
            raise ValidationError('Invalid source condition reference scope.')
        inventory_contract = source_inventory.get('source_contract')
        if (any(c in (engine.QUALIFIED_SOURCE_CONTRACT, GRAPH_SOURCE_CONTRACT) for c in (source_contract, inventory_contract))
                and source_contract != inventory_contract):
            raise ValidationError('The prospective source inventory and reference contract differ.')
        source_terms = {engine.norm(t) for t in source_inventory['reference_terms']}
        if source_contract==GRAPH_SOURCE_CONTRACT:
            taxonomy_roles=source_inventory.get('reference_taxonomy_roles')
            if (type(taxonomy_roles)is not list or any(type(role)is not str or role not in HISTORY_ROLES for role in taxonomy_roles)
                    or taxonomy_roles!=sorted(set(taxonomy_roles))
                    or type(source_inventory.get('items'))is not list
                    or any(type(row)is not dict for row in source_inventory['items'])
                    or taxonomy_roles!=sorted({row.get('consumer_role') for row in source_inventory['items']
                        if row.get('consumer_role') in HISTORY_ROLES})):
                raise ValidationError('Invalid checked history reference scope.')
    wanted = _prediction_codes(codes)
    query = _Projection(metadata)
    tabular = query.read('''jsonb_build_object(
        'format', tabular->'format', 'version', tabular->'version',
        'dictionary_sha256', tabular->'dictionary_sha256',
        'index_xml_sha256', tabular->'index_xml_sha256',
        'tabular_xml_sha256', tabular->'tabular_xml_sha256',
        'introduction', tabular->'introduction',
        'guidelines_sha256', provenance #>> '{manifest,files,guidelines,sha256}')''')
    if type(tabular) is not dict or tabular.get('format') != FORMAT or not re.fullmatch(r'20\d\d', str(tabular.get('version'))):
        raise ValidationError('Unsupported bound coding reference format.')
    guidelines_sha256 = tabular.pop('guidelines_sha256', None)
    routes = query.read('''(SELECT COALESCE(jsonb_agg(entry ORDER BY ordinal), '[]'::jsonb)
        FROM jsonb_array_elements("index") WITH ORDINALITY AS index_entries(entry, ordinal)
        WHERE entry->>'code' = ANY(%s::text[]))''', [sorted(wanted)]) if wanted else []
    if (type(routes) is not list or len(routes) > MAX_IDENTITIES
            or any(type(row) is not dict or type(row.get('id')) is not str
                   or not INDEX_ID.fullmatch(row['id']) or row.get('code') not in wanted
                   or 'parent_id' not in row for row in routes)
            or len({row['id'] for row in routes}) != len(routes)):
        raise ValidationError('Invalid selected-code Index routes.')
    ancestors = _ancestors({row['id'] for row in routes}, {row['id']:row for row in routes},
        query.index, 'parent_id') if routes else {}
    roots = {key for key, row in ancestors.items() if row['parent_id'] is None}
    # All roots are only a compact authority-owned vocabulary inventory. Their
    # potentially large children, aliases and instructions are not transferred.
    inventory = query.read('''(WITH descriptions AS MATERIALIZED (
        SELECT key, value FROM jsonb_each(tabular->'codes'))
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'id', entry->'id', 'term', entry->'term', 'code', entry->'code',
        'description', COALESCE(descriptions.value, '""'::jsonb)) ORDER BY ordinal), '[]'::jsonb)
        FROM jsonb_array_elements("index") WITH ORDINALITY AS root_entries(entry, ordinal)
        LEFT JOIN descriptions ON descriptions.key = entry->>'code'
        WHERE entry->'parent_id' = 'null'::jsonb)''') if routes or source_inventory is not None else []
    if (type(inventory) is not list or len(inventory) > MAX_ROOTS
            or any(type(row) is not dict or type(row.get('id')) is not str
                   or not INDEX_ID.fullmatch(row['id']) or type(row.get('term')) is not str
                   or type(row.get('description')) is not str for row in inventory)
            or len({row['id'] for row in inventory}) != len(inventory)):
        raise ValidationError('Invalid bounded Index root inventory.')
    descriptions = query.read('''(SELECT COALESCE(jsonb_object_agg(wanted, tabular->'codes'->wanted), '{}'::jsonb)
        FROM unnest(%s::text[]) AS names(wanted) WHERE tabular->'codes' ? wanted)''', [sorted(wanted)])
    if (type(descriptions) is not dict or not set(descriptions) <= wanted
            or any(type(value) is not str or not value for value in descriptions.values())):
        raise ValidationError('Invalid prediction code descriptions.')
    lexical = set()
    modern = source_contract in engine.SOURCE_CONTRACTS or source_contract == GRAPH_SOURCE_CONTRACT
    for route in routes:
        head = route
        while head['parent_id'] is not None:
            head = ancestors[head['parent_id']]
        terms = (engine.index_head_terms(head, descriptions.get(route['code'], '')) if modern else
                 [re.sub(r'\(s\)$', '', head.get('term', ''), flags=re.I)])
        for term in [descriptions.get(route['code'], ''), *terms]:
            lexical.update(engine.anchors({'term':term, 'index_terms':[term]}))
    for row in inventory:
        terms = engine.index_head_terms(row, row['description']) if modern else [row['term']]
        if any(engine.norm(term) in lexical | source_terms and engine.norm(term) not in engine.TAXONOMY_HEADS for term in terms):
            roots.add(row['id'])
        if taxonomy_roles and engine.norm(row['term'])=='history':
            roots.add(row['id'])
    forest = _forest(roots, ancestors, query.index, query.children) if roots else {}
    # One final source-order query preserves route choice and scope-ID order.
    index = query.index(set(forest)) if forest else {}
    bases = {row['code'].rstrip('-') for row in index.values() if isinstance(row.get('code'), str) and row['code']}
    descriptions = query.read('''(SELECT COALESCE(jsonb_object_agg(key, value), '{}'::jsonb)
        FROM jsonb_each(tabular->'codes') AS code_entries(key, value)
        WHERE key = ANY(%s::text[]) OR EXISTS (SELECT 1 FROM unnest(%s::text[]) AS bases(base)
            WHERE key = base OR (length(replace(key, '.', '')) = 7
                AND left(key, length(base)) = base)))''', [sorted(wanted), sorted(bases)])
    if (type(descriptions) is not dict
            or any(type(value) is not str or not value for value in descriptions.values())):
        raise ValidationError('Invalid prediction subtype descriptions.')
    prefixes = set()
    for code in descriptions:
        if normalize_code(code) != code:
            raise ValidationError('Invalid stored prediction subtype code.')
        raw = code.replace('.', '')
        prefixes.update(raw[:3] + ('.' + raw[3:n] if n > 3 else '') for n in range(3, len(raw) + 1))
    initial = query.nodes(prefixes) if prefixes else {}
    governing = {_governing_node(initial, code) for code in descriptions}
    if None in governing:
        raise ValidationError('A prediction code lacks its governing Tabular node.')
    nodes = _ancestors(governing, initial, query.nodes, 'parent') if governing else {}
    tabular.update(codes=descriptions, nodes=nodes)
    reference = SimpleNamespace(pk=metadata.pk, id=metadata.pk, release_id=metadata.release_id,
        release=metadata.release, digest=metadata.digest, index=list(index.values()),
        tabular=tabular, _index_lookup=index, projection_bytes=query.total_bytes,
        guidelines_sha256=guidelines_sha256)
    if source_inventory is not None:
        reference.completeness_scope = {
            'contract': 'source-reference-closure-v1',
            'source_sha256': source_inventory['source_sha256'],
            'inventory_sha256': source_inventory['inventory_sha256'],
            'terms': sorted(set(source_inventory['reference_terms'])), 'complete': True}
        if source_contract==GRAPH_SOURCE_CONTRACT:
            reference.completeness_scope['taxonomy_roles']=taxonomy_roles
    return reference
