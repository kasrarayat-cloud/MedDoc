"""Prospective, reviewed component and presentation requirements for one field.

This validates a literal contract. It does not infer components from clinical
language or treat a valid structure as evidence that a proposal is complete.
"""
import re
from copy import deepcopy

CONTRACT = 'field-components-v1'
ENCOUNTER_CONTRACT = 'field-components-v2'
CONFIG_KEY = 'semantic_component_contract'
ENCOUNTER_SCOPES = ('current', 'past', 'all_documented')
RENDERINGS = ('plain', 'labelled', 'protected')
UNIT_REQUIREMENTS = ('none', 'documented', 'printed')
COMPONENT_KEYS = {'id', 'question_quote', 'label', 'meaning', 'value_type',
                  'scope', 'unit', 'unit_requirement', 'required'}


def literal_part(text, value):
    """A complete literal word/phrase, with punctuation preserved."""
    if not isinstance(value, str) or not value.strip():
        return False
    return any((match.start() == 0 or not (text[match.start()-1].isalnum() and value[0].isalnum()))
               and (match.end() == len(text) or not (text[match.end()].isalnum() and value[-1].isalnum()))
               for match in re.finditer(re.escape(value), text))


def validate_v1(field, definition):
    from .semantic_preparation_roles import (
        require, _string, protected_field, ANSWER_TYPES, SUBJECTS, TEMPORALITIES, POLARITIES,
    )
    contract = definition.get('component_contract')
    require(isinstance(contract, dict) and set(contract) == {'contract', 'rendering', 'components'}
            and contract['contract'] == CONTRACT and contract['rendering'] in RENDERINGS
            and isinstance(contract['components'], list) and len(contract['components']) <= 30,
            'A prospective definition requires its complete reviewed component contract.')
    components = contract['components']
    protected = protected_field(field)
    require((protected and contract['rendering'] == 'protected' and not components)
            or (not protected and contract['rendering'] != 'protected' and bool(components)),
            'Signing areas remain protected; every other field requires explicit components.')
    require(len(components) <= 1 or (definition['value_type'] == 'text'
            and definition['answer_mode'] == 'narrative'),
            'One answer area requesting several values requires narrative text.')
    require(contract['rendering'] != 'labelled' or definition['value_type'] == 'text',
            'Labelled values require an existing text answer area.')
    ids, labels = set(), set()
    for component in components:
        require(isinstance(component, dict) and set(component) == COMPONENT_KEYS,
                'A component has unsupported or missing requirements.')
        identifier = component['id']
        require(isinstance(identifier, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', identifier)
                and identifier not in ids, 'Component IDs must be distinct within their field.')
        ids.add(identifier)
        _string(component['meaning'], 'component meaning', 2000)
        _string(component['question_quote'], 'component question quote', 2000)
        require(literal_part(field['label'], component['question_quote']),
                'Every component must remain bound to the original question text.')
        require(component['value_type'] in ANSWER_TYPES,
                'A component requires a supported value type.')
        scope = component['scope']
        require(isinstance(scope, dict) and set(scope) == {'subject', 'temporality', 'polarity'}
                and scope['subject'] in SUBJECTS and scope['temporality'] in TEMPORALITIES
                and scope['polarity'] in POLARITIES, 'Invalid component scope.')
        require(component['value_type'] != 'person_name' or scope['subject'] in ('patient', 'clinician', 'other', 'unspecified'),
                'A component name needs a supported person role or explicit unresolved attribution.')
        require(component['unit_requirement'] in UNIT_REQUIREMENTS
                and (component['unit'] is None or isinstance(component['unit'], str)),
                'Invalid component unit requirement.')
        if component['unit'] is not None:
            _string(component['unit'], 'component unit', 80)
        require((component['unit_requirement'] == 'printed') == (component['unit'] is not None),
                'Only a printed component unit can prescribe a unit; documented units come from source.')
        require(component['unit'] is None or literal_part(field['label'], component['unit'])
                or component['unit'] == (field.get('answer_constraints') or {}).get('unit'),
                'A prescribed component unit must be literal in the original question.')
        require(component['required'] is True,
                'Requested components cannot be made optional to hide incomplete answers.')
        label = component['label']
        if contract['rendering'] == 'labelled':
            _string(label, 'component label', 2000)
            require(label not in labels and (literal_part(field['label'], label)
                    or literal_part(definition['meaning'], label)),
                    'Component labels must be distinct literal parts of the reviewed question or meaning.')
            labels.add(label)
        else:
            require(label is None, 'Plain and protected answers cannot introduce hidden labels.')
    if len(components) == 1 and definition['answer_mode'] == 'atomic':
        component = components[0]
        require(component['value_type'] == definition['value_type'] and component['scope'] == definition['scope']
                and component['unit'] == definition['unit'],
                'An atomic component must preserve the approved field type, scope and unit.')
    return contract


def validate(field, definition):
    """Dispatch only the retained tag; approved definitions are never upgraded."""
    from .semantic_preparation_roles import require
    contract = definition.get('component_contract')
    if isinstance(contract, dict) and contract.get('contract') == ENCOUNTER_CONTRACT:
        require(set(contract) == {'contract', 'rendering', 'components'}
                and isinstance(contract['components'], list), 'Invalid encounter component contract.')
        for component in contract['components']:
            require(isinstance(component, dict) and set(component) == COMPONENT_KEYS | {'encounter_scope'}
                    and component['encounter_scope'] in ENCOUNTER_SCOPES,
                    'Every component requires an explicit encounter scope.')
        # Apply every unchanged v1 structural requirement to the common fields.
        # This local validation projection never replaces the retained definition.
        common = deepcopy(definition)
        common['component_contract']['contract'] = CONTRACT
        for component in common['component_contract']['components']:
            del component['encounter_scope']
        validate_v1(field, common)
        return contract
    return validate_v1(field, definition)


def configured(config):
    from .semantic_preparation_roles import require
    value = config.get(CONFIG_KEY, CONTRACT)
    require(value in (CONTRACT, ENCOUNTER_CONTRACT)
            and (CONFIG_KEY not in config or config.get('semantic_definition_version') == 4),
            'Unsupported explicit component contract.')
    return value


def identity_issue(definition):
    names = [component['label'] or component['question_quote']
             for component in definition['component_contract']['components']
             if component['value_type'] == 'person_name' and component['scope']['subject'] == 'unspecified']
    return ('Choose whose name belongs in each unresolved required part: '+', '.join(names)+
            '. Review the complete original form before approval or generation.') if names else ''


def schema():
    from .semantic_preparation_roles import ANSWER_TYPES, SUBJECTS, TEMPORALITIES, POLARITIES
    def obj(properties):
        return {'type': 'object', 'additionalProperties': False, 'required': list(properties), 'properties': properties}
    def enum(values):
        return {'type': 'string', 'enum': list(values)}
    string = {'type': 'string', 'minLength': 1, 'maxLength': 2000}
    nullable = lambda value: {'anyOf': [value, {'type': 'null'}]}
    component = obj({'id': {'type': 'string', 'minLength': 1, 'maxLength': 80},
        'question_quote': string, 'label': nullable(string), 'meaning': string,
        'value_type': enum(ANSWER_TYPES),
        'scope': obj({'subject': enum(SUBJECTS), 'temporality': enum(TEMPORALITIES), 'polarity': enum(POLARITIES)}),
        'unit': nullable({'type': 'string', 'minLength': 1, 'maxLength': 80}),
        'unit_requirement': enum(UNIT_REQUIREMENTS), 'required': {'type': 'boolean', 'enum': [True]}})
    return obj({'contract': enum((CONTRACT,)), 'rendering': enum(RENDERINGS),
                'components': {'type': 'array', 'maxItems': 30, 'items': component}})


INSTRUCTIONS = (
    'Version 4 additionally supplies component_contract field-components-v1 for EVERY field. '
    'Independently enumerate every distinct value requested by the complete original question and reviewed meaning. '
    'Each component has a stable local id, exact question_quote from the original label, precise meaning, '
    'value_type, subject/temporality/polarity scope, unit, unit_requirement and required:true. '
    'Do not enumerate a fixed list of possible patient findings for an open narrative question: its component '
    'is that complete clinical topic and its future source-grounded answer must remain complete. '
    'Atomic fields have one matching component. Combined identity or measurement fields have all requested '
    'components and narrative text; use labelled rendering to preserve each role/value association. '
    'Plain rendering has null component labels. Labelled rendering requires distinct labels, exact literal '
    'phrases in the original question OR your outer definition.meaning, never arbitrary generated aliases. '
    'For a generic original heading, question_quote may be that whole heading; put the explicit requested '
    'components and labels into the reviewed meaning. Labels are reviewed requirements, not patient facts. '
    'unit_requirement is none, documented, or printed. printed requires a non-null exact original-question '
    'unit; otherwise unit is null. documented requires retaining that component\'s own source unit and scale, '
    'never another measurement\'s or a guessed normal unit. Missing requested components are explicit missing '
    'information; they cannot become optional, be silently dropped or permit partial coding completion. '
    'Protected signing areas have rendering protected and no components. Check all roles, label associations, '
    'units, question bindings, completeness and unchanged physical destinations against the COMPLETE blank form. '
    'A structurally valid contract is not evidence that its meaning is correct. Mark unresolved on uncertainty. '
)


def fixture(field, definition):
    """Explicit mock fixture only; makes no clinical/component inference."""
    from .semantic_preparation_roles import protected_field
    protected = protected_field(field)
    return {'contract': CONTRACT, 'rendering': 'protected' if protected else 'plain',
        'components': [] if protected else [{'id': 'answer', 'question_quote': field['label'], 'label': None,
            'meaning': definition['meaning'], 'value_type': definition['value_type'], 'scope': dict(definition['scope']),
            'unit': definition['unit'], 'unit_requirement': 'printed' if definition['unit'] is not None else 'none',
            'required': True}]}


ENCOUNTER_INSTRUCTIONS = INSTRUCTIONS.replace(CONTRACT, ENCOUNTER_CONTRACT, 1) + (
    'Every component additionally requires encounter_scope: current, past, or all_documented. '
    'This names the encounter the source assertion belongs to, independently of scope.temporality '
    '(the clinical event time), subject and polarity. current permits only the target encounter; '
    'past permits only explicitly past encounters with past events; all_documented permits the '
    'target encounter and explicitly past encounters with past events, preserving each qualifier. '
    'Unknown or future encounter ownership never counts as current or past. A future plan belonging '
    'to the current encounter can still have future event temporality; it is not a performed service. '
    'For an open topic requesting all documented information across encounters, use one complete '
    'topic component with all_documented. Do not invent required current/past sibling components '
    'or lists of possible findings: an absent time category is not an absent requested value. '
    'Choose encounter_scope from the complete original question and meaning, not from patient notes. '
    'The independent checker must verify this encounter permission separately from event time. '
)


def schema_for(contract=CONTRACT):
    from .semantic_preparation_roles import require
    require(contract in (CONTRACT, ENCOUNTER_CONTRACT), 'Unsupported component schema.')
    result = schema()
    if contract == ENCOUNTER_CONTRACT:
        result['properties']['contract']['enum'] = [contract]
        component = result['properties']['components']['items']
        component['required'].append('encounter_scope')
        component['properties']['encounter_scope'] = {'type': 'string', 'enum': list(ENCOUNTER_SCOPES)}
    return result


def instructions_for(contract=CONTRACT):
    from .semantic_preparation_roles import require
    require(contract in (CONTRACT, ENCOUNTER_CONTRACT), 'Unsupported component instructions.')
    return ENCOUNTER_INSTRUCTIONS if contract == ENCOUNTER_CONTRACT else INSTRUCTIONS


def fixture_for(field, definition, contract=CONTRACT):
    """Explicit fixture default only; live scopes come from reviewed proposals."""
    from .semantic_preparation_roles import require
    require(contract in (CONTRACT, ENCOUNTER_CONTRACT), 'Unsupported component fixture.')
    result = fixture(field, definition)
    if contract == ENCOUNTER_CONTRACT:
        result['contract'] = contract
        for component in result['components']:
            component['encounter_scope'] = 'current'
    return result
