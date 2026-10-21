"""Reversible preparation-only wire encoding; canonical validation stays mandatory.

Versioned JSON text preserves canonical components without changing validation.
Earlier choices-only and choices/quote transports remain explicit for replay.
"""
from copy import deepcopy
import json

from documents import DocumentError

ARRAY_TRANSPORT = 'anthropic-shared-component-choices-json-v2'
QUOTE_TRANSPORT = 'anthropic-shared-component-choices-quote-json-v3'
TRANSPORT = 'anthropic-shared-components-json-v4'
COMPACT_TRANSPORT = 'anthropic-shared-component-rows-json-v5'
UNIT_POLICY_TRANSPORT = 'anthropic-shared-component-rows-unit-policy-json-v6'
LABEL_REFERENCE_TRANSPORT = 'anthropic-shared-component-rows-label-reference-json-v7'
TRANSPORTS = (ARRAY_TRANSPORT, QUOTE_TRANSPORT, TRANSPORT, COMPACT_TRANSPORT, UNIT_POLICY_TRANSPORT,
              LABEL_REFERENCE_TRANSPORT)
COMPONENT_COLUMNS = ('id', 'question_quote', 'label', 'meaning', 'value_type', 'scope',
                     'unit', 'unit_requirement', 'required', 'encounter_scope', 'choices', 'option_quote')
UNIT_POLICY_COLUMNS = ('id', 'question_quote', 'label', 'meaning', 'value_type', 'scope',
                       'unit_policy', 'required', 'encounter_scope', 'choices', 'option_quote')
LABEL_REFERENCE_COLUMNS = tuple('label_ref' if key == 'label' else key for key in UNIT_POLICY_COLUMNS)
SCOPE_COLUMNS = ('subject', 'temporality', 'polarity')
MAX_ENCODED_BYTES = 2 * 1024 * 1024  # The existing retained-response byte bound.
INSTRUCTIONS = (
    ' Response transport anthropic-shared-component-choices-json-v2: ONLY '
    'answer_definitions.fields[].definition.component_contract.components[].choices '
    'is a string containing a JSON array of the complete original ordered string options. '
    'For a non-choice component return the string "[]". Escape quotes, backslashes and '
    'control characters as JSON requires; do not shorten, normalize, omit or reorder options. '
    'All other choices properties remain arrays. option_quote remains a string or null, '
    'with the same original source evidence requirements. This encoding grants no semantic '
    'approval and changes no canonical constraint. '
)
QUOTE_INSTRUCTIONS = (
    ' Response transport anthropic-shared-component-choices-quote-json-v3: ONLY '
    'answer_definitions.fields[].definition.component_contract.components[].choices '
    'and option_quote use JSON text strings on wire. choices contains a JSON array '
    'of the complete original ordered string options; use the string "[]" for a '
    'non-choice component. option_quote contains exactly one JSON scalar: the string '
    '"null" encodes canonical null, while a JSON-quoted string encodes the exact '
    'canonical source quote. A source quote whose literal text is null must therefore '
    'be JSON-quoted, never confused with canonical null. Empty string is not a null '
    'sentinel. Escape quotes, backslashes and control characters as JSON requires; '
    'do not shorten, normalize, omit or reorder any source evidence. All other choices '
    'properties remain arrays. Canonical nullable option_quote requirements and every '
    'source/type/bound check remain mandatory after decoding. This encoding grants '
    'no semantic approval and changes no canonical constraint. '
)
COMPONENTS_INSTRUCTIONS = (
    ' Response transport anthropic-shared-components-json-v4: ONLY '
    'answer_definitions.fields[].definition.component_contract.components is a string '
    'containing one JSON array of the complete original ordered component objects. '
    'Preserve every component property, ID, question_quote, label, meaning, value_type, '
    'scope, unit, unit_requirement, required, encounter_scope, choices and option_quote '
    'with its canonical JSON type and exact source text. Inside this encoded array, '
    'choices remains an ordered array of strings and option_quote remains a string or '
    'null; do not encode either property again. Null, the literal string null, empty '
    'strings and empty arrays are distinct. Encode an empty component array as the '
    'string "[]" only where the canonical signing/protection contract permits it. '
    'component_contract.contract and rendering, all other outer properties and all '
    'other choices remain unchanged explicit JSON values. Escape quotes, backslashes '
    'and control characters as JSON requires. Do not shorten, normalize, omit, reorder '
    'or infer any component or source evidence. All canonical source, type, ownership, '
    'required, protection and bound checks remain mandatory after decoding. This '
    'encoding grants no semantic approval and changes no canonical constraint. '
)
COMPACT_INSTRUCTIONS = (
    ' Response transport anthropic-shared-component-rows-json-v5: ONLY '
    'answer_definitions.fields[].definition.component_contract.components is a string '
    'containing one JSON array of complete ordered component ROWS. Each component row '
    'has EXACTLY twelve values in this order: [id, question_quote, label, meaning, '
    'value_type, scope, unit, unit_requirement, required, encounter_scope, choices, '
    'option_quote]. scope is EXACTLY [subject, temporality, polarity], three explicit '
    'strings in that order. Every position is mandatory; do not omit trailing nulls, '
    'empty arrays, or other values. id, question_quote, meaning, value_type, '
    'unit_requirement and encounter_scope are strings. label and unit are strings '
    'or null; required is a JSON boolean; choices is the complete ordered array of '
    'strings; option_quote is the exact original source string or null. '
    'Do not encode any individual position again. Canonical null, the literal string '
    'null, empty strings and empty arrays are distinct. Preserve all original text, '
    'Unicode, quotes and backslashes exactly with ordinary JSON escaping. Do not '
    'shorten, normalize, reorder, omit or infer any component, property or source '
    'evidence. An empty component array is the string "[]" only where the canonical '
    'signing/protection contract permits it. All twelve canonical property names '
    'and three scope names are restored by position before the unchanged complete '
    'canonical/source/type/ownership/required/protection/bound validation. '
    'component_contract.contract and rendering and ALL other outer properties '
    'remain unchanged explicit JSON values. This transport grants no approval '
    'and changes no canonical constraint. '
)
UNIT_POLICY_INSTRUCTIONS = (
    ' Response transport anthropic-shared-component-rows-unit-policy-json-v6: ONLY '
    'answer_definitions.fields[].definition.component_contract.components is a string '
    'containing one JSON array of complete ordered component ROWS. Each row has EXACTLY '
    'eleven values in this order: [id, question_quote, label, meaning, value_type, scope, '
    'unit_policy, required, encounter_scope, choices, option_quote]. scope is EXACTLY '
    '[subject, temporality, polarity], three explicit strings in that order. '
    'unit_policy is EXACTLY one of ["none"], ["documented"], or ["printed", literal_unit]. '
    'The first two restore canonical unit:null and unit_requirement:none or documented; '
    'printed restores the exact supplied string as unit and unit_requirement:printed. '
    'There is no other unit position and no default. documented retains each future '
    'source value\'s own documented unit and scale without prescribing a fixed unit, '
    'borrowing another measurement\'s unit, converting units, or guessing a normal unit. '
    'printed requires a nonblank exact original-question or original printed-metadata '
    'unit, at most eighty characters. A unit mentioned only in an example or exclusion '
    'does not establish a prescribed unit; mark unresolved on ambiguity. '
    'Every position is mandatory; id, question_quote, meaning, value_type and '
    'encounter_scope are strings. label is a string or null; required is a JSON '
    'boolean; choices is the complete ordered array of strings; option_quote is '
    'the exact original source string or null. Preserve all original Unicode, quotes, '
    'backslashes, nulls, empty arrays, choices and source evidence exactly. Do not '
    'encode any individual position again or omit, shorten, reorder or infer a value. '
    'An empty component array is "[]" only where canonical signing protection permits. '
    'All twelve canonical component properties and three scope properties are restored '
    'before unchanged complete canonical/source/type/ownership/required/protection/bound '
    'validation. component_contract.contract and rendering and every other outer '
    'property remain unchanged explicit JSON values. '
    'Field scope and component scope are eligibility filters on EVERY requested clause, '
    'not summaries of a dominant topic. A question requesting historical information '
    'and current status, or other mixed historical/current/future information, requires '
    'an outer temporality:any and either one complete component with temporality:any '
    'or genuinely separate required components for the explicitly requested clauses '
    'with scopes that admit each clause. Do not invent time categories or required '
    'siblings for an open topic. Independently verify encounter_scope as well as event '
    'temporality. Never silently alter another role\'s scopes or treat agreement as '
    'approval; unresolved source or scope uncertainty remains for explicit review. '
    'This representation grants no semantic approval and changes no canonical constraint. '
)
LABEL_REFERENCE_INSTRUCTIONS = UNIT_POLICY_INSTRUCTIONS.replace(
    UNIT_POLICY_TRANSPORT, LABEL_REFERENCE_TRANSPORT, 1).replace(
    '[id, question_quote, label, meaning, value_type, scope,',
    '[id, question_quote, label_ref, meaning, value_type, scope,', 1).replace(
    'label is a string or null;',
    'label_ref is null for plain rendering; for labelled rendering it is EXACTLY '
    '["question_quote"], ["question", start, end], or ["meaning", start, end]. '
    'Prefer ["question_quote"] when that complete component question_quote is a clear distinct label. '
    'The first reference restores that same question_quote verbatim. The other references restore '
    'the exact substring of this field\'s ORIGINAL question label or this outer definition.meaning. '
    'start/end are zero-based Unicode code-point offsets with an exclusive end, not UTF-8 bytes '
    'or UTF-16 units; both must be JSON integers with 0 <= start < end <= source length. '
    'References must select complete literal words/phrases at the unchanged source boundaries. '
    'Use an exact meaning span only when a generic question needs distinct reviewed component labels. '
    'No free label text, casing change, inferred label, default or reference to another field is allowed. '
    'Protected rendering still has no components. Labels are display requirements only, never '
    'evidence of clinical facts, complete meaning, eligibility, identity or approval;', 1)


def invalid():
    return DocumentError('The preparation choice transport is invalid; its original response is retained.',
                         'invalid_response')


def instructions(transport):
    if transport not in TRANSPORTS:
        raise invalid()
    if transport == LABEL_REFERENCE_TRANSPORT:
        return LABEL_REFERENCE_INSTRUCTIONS
    if transport == UNIT_POLICY_TRANSPORT:
        return UNIT_POLICY_INSTRUCTIONS
    if transport == COMPACT_TRANSPORT:
        return COMPACT_INSTRUCTIONS
    if transport == TRANSPORT:
        return COMPONENTS_INSTRUCTIONS
    return INSTRUCTIONS if transport == ARRAY_TRANSPORT else QUOTE_INSTRUCTIONS


def wire_schema(canonical, transport=TRANSPORT):
    """Copy and replace only the versioned wire properties, before SDK lowering."""
    instructions(transport)
    value = deepcopy(canonical)
    try:
        contract = (value['properties']['answer_definitions']['properties']['fields']['items']
                    ['properties']['definition']['properties']['component_contract']['properties'])
        if transport == LABEL_REFERENCE_TRANSPORT:
            original = contract['components']
            if (original['type'] != 'array' or original['items']['type'] != 'object'
                    or set(original['items']['properties']) != set(COMPONENT_COLUMNS)
                    or set(original['items']['required']) != set(COMPONENT_COLUMNS)):
                raise invalid()
            contract['components'] = {'type': 'string', 'description': (
                'JSON text containing ordered rows of EXACTLY eleven explicit values: '
                + json.dumps(LABEL_REFERENCE_COLUMNS) + '. scope is exactly '
                + json.dumps(SCOPE_COLUMNS) + ' as three strings in order. '
                'label_ref is null only for plain rendering; labelled rendering requires exactly '
                '["question_quote"], ["question", start, end], or ["meaning", start, end]. '
                'Restore the same component question_quote or the exact source substring. question '
                'means this field\'s immutable original question, meaning means its outer definition.meaning. '
                'Offsets are native integers, zero-based Unicode code points, exclusive end, '
                '0 <= start < end <= len(source), selecting literal word/phrase boundaries. '
                'No label string position, normalization, inference, omission or default. '
                'unit_policy is exactly ["none"], ["documented"], or ["printed", literal_unit]. '
                'Reference-only RESTORED canonical object schema after decode, NOT a wire row; '
                'NEVER emit separate label, unit or unit_requirement positions. Every unchanged '
                'canonical source/label/type/scope/unit/choice/protection check remains mandatory: '
                + json.dumps(original, ensure_ascii=False, sort_keys=True))}
            return value
        if transport == UNIT_POLICY_TRANSPORT:
            original = contract['components']
            if (original['type'] != 'array' or original['items']['type'] != 'object'
                    or set(original['items']['properties']) != set(COMPONENT_COLUMNS)
                    or set(original['items']['required']) != set(COMPONENT_COLUMNS)):
                raise invalid()
            contract['components'] = {'type': 'string', 'description': (
                'JSON text containing ordered rows of EXACTLY eleven explicit values: '
                + json.dumps(UNIT_POLICY_COLUMNS) + '. scope is exactly '
                + json.dumps(SCOPE_COLUMNS) + ' as three strings in order. '
                'unit_policy is exactly ["none"], ["documented"], or ["printed", literal_unit]; '
                'restore (unit:null,unit_requirement:none/documented) or '
                '(unit:literal_unit,unit_requirement:printed) respectively. '
                'No omission, extra values, coercion or default. All unchanged canonical '
                'constraints are checked after strict local decoding: '
                'Reference-only RESTORED canonical object schema after decode, NOT a wire row; '
                'NEVER emit separate unit or unit_requirement positions. '
                + json.dumps(original, ensure_ascii=False, sort_keys=True))}
            return value
        if transport == COMPACT_TRANSPORT:
            original = contract['components']
            if (original['type'] != 'array' or original['items']['type'] != 'object'
                    or set(original['items']['properties']) != set(COMPONENT_COLUMNS)
                    or set(original['items']['required']) != set(COMPONENT_COLUMNS)):
                raise invalid()
            contract['components'] = {'type': 'string', 'description': (
                'JSON text containing complete ordered rows of EXACTLY twelve values: '
                + json.dumps(COMPONENT_COLUMNS) + '. The scope position is EXACTLY '
                + json.dumps(SCOPE_COLUMNS) + ' as three explicit string values in order. '
                'All positions are mandatory; no defaults, omission, extra positions or nested transport. '
                'Every canonical value and constraint below is preserved by position and '
                'checked after strict decoding: '
                + json.dumps(original, ensure_ascii=False, sort_keys=True))}
            return value
        if transport == TRANSPORT:
            original = contract['components']
            if original['type'] != 'array' or original['items']['type'] != 'object':
                raise invalid()
            contract['components'] = {'type': 'string', 'description': (
                'JSON text encoding the complete ordered array of canonical component objects. '
                'Inner choices are arrays and option_quote is null or a string; no nested transport. '
                'All canonical constraints are checked after strict decoding: '
                + json.dumps(original, ensure_ascii=False, sort_keys=True))}
            return value
        properties = contract['components']['items']['properties']
        choices = properties['choices']
        if choices['type'] != 'array' or choices['items']['type'] != 'string':
            raise invalid()
        properties['choices'] = {'type': 'string', 'description': (
            'A JSON-encoded ordered array of this component\'s complete original string choices; '
            'the string [] for a non-choice component. Canonical constraints, checked after decoding: '
            + json.dumps(choices, ensure_ascii=False, sort_keys=True))}
        if transport == QUOTE_TRANSPORT:
            quote = properties['option_quote']
            if (type(quote.get('anyOf')) is not list or len(quote['anyOf']) != 2
                    or [branch.get('type') for branch in quote['anyOf']] != ['string', 'null']):
                raise invalid()
            properties['option_quote'] = {'type': 'string', 'description': (
                'JSON text encoding exactly canonical null or the exact original source string. '
                'Use null (four characters) for canonical null, or a JSON-quoted string for a source quote. '
                'No empty-string sentinel. Canonical constraints, checked after decoding: '
                + json.dumps(quote, ensure_ascii=False, sort_keys=True))}
    except (KeyError, TypeError):
        raise invalid() from None
    return value


def contracts(value):
    """Admit no missing path or fallback; preserve every property for validation."""
    if type(value) is not dict:
        raise invalid()
    try:
        semantic = value['answer_definitions']
        if type(semantic) is not dict or type(semantic['fields']) is not list:
            raise invalid()
        for row in semantic['fields']:
            if type(row) is not dict or type(row['definition']) is not dict:
                raise invalid()
            contract = row['definition']['component_contract']
            if type(contract) is not dict or contract['contract'] != 'field-components-v3':
                raise invalid()
            yield contract
    except (KeyError, TypeError):
        raise invalid() from None


def components(value):
    """Walk canonical arrays without accepting encoded or incomplete objects."""
    for contract in contracts(value):
        if type(contract.get('components')) is not list:
            raise invalid()
        for component in contract['components']:
            if type(component) is not dict:
                raise invalid()
            yield component


def decode_components(response):
    """Decode exactly one array string, keeping every inner canonical value."""
    value = deepcopy(response)

    def constant(_):
        raise ValueError('Non-JSON constant')

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON property')
            result[key] = item
        return result

    for contract in contracts(value):
        try:
            encoded = contract['components']
            if type(encoded) is not str or len(encoded.encode('utf-8')) > MAX_ENCODED_BYTES:
                raise invalid()
            decoded = json.loads(encoded, parse_constant=constant, object_pairs_hook=unique_object)
            if type(decoded) is not list or any(type(component) is not dict for component in decoded):
                raise invalid()
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise invalid() from None
        contract['components'] = decoded
    return value


def decode_component_rows(response):
    """Restore all explicit values, without inferring or defaulting semantic data."""
    value = deepcopy(response)

    def constant(_):
        raise ValueError('Non-JSON constant')

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON property')
            result[key] = item
        return result

    for contract in contracts(value):
        try:
            encoded = contract['components']
            if type(encoded) is not str or len(encoded.encode('utf-8')) > MAX_ENCODED_BYTES:
                raise invalid()
            rows = json.loads(encoded, parse_constant=constant, object_pairs_hook=unique_object)
            if type(rows) is not list:
                raise invalid()
            decoded = []
            for row in rows:
                if type(row) is not list or len(row) != len(COMPONENT_COLUMNS):
                    raise invalid()
                component = dict(zip(COMPONENT_COLUMNS, row))
                scope = component['scope']
                if (any(type(component[key]) is not str for key in
                        ('id', 'question_quote', 'meaning', 'value_type', 'unit_requirement', 'encounter_scope'))
                        or any(component[key] is not None and type(component[key]) is not str
                               for key in ('label', 'unit', 'option_quote'))
                        or type(component['required']) is not bool
                        or type(scope) is not list or len(scope) != len(SCOPE_COLUMNS)
                        or any(type(item) is not str for item in scope)
                        or type(component['choices']) is not list
                        or any(type(item) is not str for item in component['choices'])):
                    raise invalid()
                component['scope'] = dict(zip(SCOPE_COLUMNS, scope))
                decoded.append(component)
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise invalid() from None
        contract['components'] = decoded
    return value


def encode_unit_policy_rows(response):
    """Strict inverse for offline replay, never a repair of an invalid old result."""
    value = deepcopy(response)
    for contract in contracts(value):
        if type(contract.get('components')) is not list:
            raise invalid()
        rows = []
        for component in contract['components']:
            if type(component) is not dict or set(component) != set(COMPONENT_COLUMNS):
                raise invalid()
            unit, requirement = component['unit'], component['unit_requirement']
            if type(requirement) is not str:
                raise invalid()
            if requirement in ('none', 'documented') and unit is None:
                policy = [requirement]
            elif (requirement == 'printed' and type(unit) is str
                    and 0 < len(unit) <= 80 and unit.strip()):
                policy = ['printed', unit]
            else:
                raise invalid()
            scope = component['scope']
            if type(scope) is not dict or set(scope) != set(SCOPE_COLUMNS):
                raise invalid()
            rows.append([policy if key == 'unit_policy' else
                         [scope[name] for name in SCOPE_COLUMNS] if key == 'scope' else component[key]
                         for key in UNIT_POLICY_COLUMNS])
        contract['components'] = json.dumps(rows, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    # Apply the same exact row/type bounds to the inverse; no semantic inference.
    if decode_unit_policy_rows(value) != response:
        raise invalid()
    return value


def decode_unit_policy_rows(response):
    """Restore a disjoint explicit policy to the unchanged canonical unit pair."""
    value = deepcopy(response)

    def constant(_):
        raise ValueError('Non-JSON constant')

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON property')
            result[key] = item
        return result

    for contract in contracts(value):
        try:
            encoded = contract['components']
            if type(encoded) is not str or len(encoded.encode('utf-8')) > MAX_ENCODED_BYTES:
                raise invalid()
            rows = json.loads(encoded, parse_constant=constant, object_pairs_hook=unique_object)
            if type(rows) is not list:
                raise invalid()
            decoded = []
            for row in rows:
                if type(row) is not list or len(row) != len(UNIT_POLICY_COLUMNS):
                    raise invalid()
                component = dict(zip(UNIT_POLICY_COLUMNS, row))
                policy = component.pop('unit_policy')
                if type(policy) is not list or not policy or type(policy[0]) is not str:
                    raise invalid()
                if len(policy) == 1 and policy[0] in ('none', 'documented'):
                    component.update(unit=None, unit_requirement=policy[0])
                elif (len(policy) == 2 and policy[0] == 'printed' and type(policy[1]) is str
                        and 0 < len(policy[1]) <= 80 and policy[1].strip()):
                    component.update(unit=policy[1], unit_requirement='printed')
                else:
                    raise invalid()
                scope = component['scope']
                if (any(type(component[key]) is not str for key in
                        ('id', 'question_quote', 'meaning', 'value_type', 'encounter_scope'))
                        or any(component[key] is not None and type(component[key]) is not str
                               for key in ('label', 'option_quote'))
                        or type(component['required']) is not bool
                        or type(scope) is not list or len(scope) != len(SCOPE_COLUMNS)
                        or any(type(item) is not str for item in scope)
                        or type(component['choices']) is not list
                        or any(type(item) is not str for item in component['choices'])):
                    raise invalid()
                component['scope'] = dict(zip(SCOPE_COLUMNS, scope))
                decoded.append(component)
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise invalid() from None
        contract['components'] = decoded
    return value


def _label_bound_rows(value, fields):
    """Use only the caller's immutable field inventory, never response field text."""
    if type(fields) is not list:
        raise invalid()
    originals = {}
    for field in fields:
        if (type(field) is not dict or type(field.get('key')) is not str
                or field['key'] in originals or type(field.get('label')) is not str):
            raise invalid()
        originals[field['key']] = field
    try:
        rows = value['answer_definitions']['fields']
        if type(rows) is not list:
            raise invalid()
        seen, bound = set(), []
        for row in rows:
            if (type(row) is not dict or type(row.get('field_key')) is not str
                    or row['field_key'] in seen or row['field_key'] not in originals
                    or type(row.get('definition')) is not dict):
                raise invalid()
            seen.add(row['field_key'])
            contract = row['definition']['component_contract']
            if type(contract) is not dict or contract['contract'] != 'field-components-v3':
                raise invalid()
            bound.append((row['definition'], contract, originals[row['field_key']]))
        if seen != set(originals):
            raise invalid()
        return bound
    except (KeyError, TypeError):
        raise invalid() from None


def _label_span(source, start, end):
    """Exact code-point slice with the same literal boundaries as canonical labels."""
    if (type(source) is not str or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(source)):
        raise invalid()
    source.encode('utf-8')  # Refuse unpaired surrogates; never normalize Unicode.
    label = source[start:end]
    if (not label.strip() or len(label) > 2000
            or start and source[start-1].isalnum() and label[0].isalnum()
            or end < len(source) and source[end].isalnum() and label[-1].isalnum()):
        raise invalid()
    return label


def _label_reference(component, definition, field):
    label = component['label']
    if definition['component_contract']['rendering'] == 'plain' and label is None:
        return None
    if (definition['component_contract']['rendering'] != 'labelled'
            or type(label) is not str or not label.strip()):
        raise invalid()
    if label == component['question_quote']:
        return ['question_quote']
    # The canonical validator admits only literal question/outer-meaning labels.
    # Preserve every such label exactly, including the generic-heading case.
    for tag, source in (('question', field['label']), ('meaning', definition['meaning'])):
        start = source.find(label)
        while start != -1:
            try:
                if _label_span(source, start, start + len(label)) == label:
                    return [tag, start, start + len(label)]
            except DocumentError:
                pass
            start = source.find(label, start + 1)
    raise invalid()


def encode_label_reference_rows(response, fields):
    """Strict inverse for valid canonical definitions, never historical repair."""
    from documents.semantic_preparation_roles import validate_definitions
    try:
        bound = _label_bound_rows(response, fields)
        validate_definitions(fields, {row['field_key']: row['definition']
                                    for row in response['answer_definitions']['fields']})
        value = encode_unit_policy_rows(response)
        for (definition, contract, field), (_, encoded, _) in zip(bound, _label_bound_rows(value, fields)):
            rows = json.loads(encoded['components'])
            for component, row in zip(contract['components'], rows):
                row[2] = _label_reference(component, definition, field)
            encoded['components'] = json.dumps(rows, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        if decode_label_reference_rows(value, fields) != response:
            raise invalid()
        return value
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        raise invalid() from None


def decode_label_reference_rows(response, fields):
    """Resolve display references only; all unchanged canonical checks still follow."""
    value = deepcopy(response)

    def constant(_):
        raise ValueError('Non-JSON constant')

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON property')
            result[key] = item
        return result

    try:
        for definition, contract, field in _label_bound_rows(value, fields):
            encoded = contract['components']
            if type(encoded) is not str or len(encoded.encode('utf-8')) > MAX_ENCODED_BYTES:
                raise invalid()
            rows = json.loads(encoded, parse_constant=constant, object_pairs_hook=unique_object)
            if type(rows) is not list or contract['rendering'] not in ('plain', 'labelled', 'protected'):
                raise invalid()
            if contract['rendering'] == 'protected' and rows:
                raise invalid()
            for row in rows:
                if type(row) is not list or len(row) != len(LABEL_REFERENCE_COLUMNS):
                    raise invalid()
                reference = row[2]
                if contract['rendering'] == 'plain' and reference is None:
                    label = None
                elif contract['rendering'] == 'labelled' and type(reference) is list:
                    if reference == ['question_quote'] and type(row[1]) is str:
                        label = row[1]
                    elif (len(reference) == 3 and type(reference[0]) is str
                          and reference[0] in ('question', 'meaning')):
                        source = field['label'] if reference[0] == 'question' else definition['meaning']
                        label = _label_span(source, reference[1], reference[2])
                    else:
                        raise invalid()
                else:
                    raise invalid()
                row[2] = label
            contract['components'] = json.dumps(rows, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        return decode_unit_policy_rows(value)
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        raise invalid() from None


def decode(response, transport=TRANSPORT, *, fields=None):
    """Decode losslessly, then let the unchanged full canonical validator judge it."""
    instructions(transport)
    if transport == LABEL_REFERENCE_TRANSPORT:
        return decode_label_reference_rows(response, fields)
    if transport == UNIT_POLICY_TRANSPORT:
        return decode_unit_policy_rows(response)
    if transport == COMPACT_TRANSPORT:
        return decode_component_rows(response)
    if transport == TRANSPORT:
        return decode_components(response)
    value = deepcopy(response)
    def constant(_):
        raise ValueError('Non-JSON constant')
    for component in components(value):
        try:
            encoded = component['choices']
            if type(encoded) is not str or len(encoded.encode('utf-8')) > MAX_ENCODED_BYTES:
                raise invalid()
            choices = json.loads(encoded, parse_constant=constant)
            if type(choices) is not list or any(type(choice) is not str for choice in choices):
                raise invalid()
            if transport == QUOTE_TRANSPORT:
                encoded_quote = component['option_quote']
                if (type(encoded_quote) is not str
                        or len(encoded_quote.encode('utf-8')) > MAX_ENCODED_BYTES):
                    raise invalid()
                quote = json.loads(encoded_quote, parse_constant=constant)
                if quote is not None and type(quote) is not str:
                    raise invalid()
                component['option_quote'] = quote
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise invalid() from None
        component['choices'] = choices
    return value
