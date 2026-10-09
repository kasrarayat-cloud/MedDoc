"""Finite, source-grounded metadata for the two new preparation API roles.

These helpers are opt-in for blank-word-preparation-v2. They cannot reinterpret
historical v1 inventories or grant document-writing authority to a model.
"""
from copy import deepcopy

if __package__:
    from .engine import DocumentFailure, PRINTED_UNITS, PRINTED_DATE_FORMATS
else:
    from engine import DocumentFailure, PRINTED_UNITS, PRINTED_DATE_FORMATS


PROTOCOL = 'blank-word-preparation-v2'
TYPES = ('text', 'number', 'integer', 'date', 'choice')
UNCERTAINTIES = ('none', 'constraints_unstated', 'placement_requires_review',
                 'signing_protected', 'unsupported_structure')
METADATA_KEYS = frozenset(('label', 'data_type', 'unit', 'choices', 'destination', 'uncertainty'))


def _fail(message):
    raise DocumentFailure(message, 'invalid_proposal')


def role_schema(role):
    if role not in {'proposer', 'checker'}:
        _fail('Unsupported preparation role.')
    decision = 'decision' if role == 'proposer' else 'verdict'
    states = ['map', 'needs_review'] if role == 'proposer' else ['pass', 'unresolved']
    metadata = {'type': 'object', 'additionalProperties': False,
                'required': sorted(METADATA_KEYS), 'properties': {
                    'label': {'type': 'string', 'minLength': 1, 'maxLength': 2000},
                    'data_type': {'type': 'string', 'enum': list(TYPES)},
                    # The pinned SDK accepts nullable scalars through anyOf;
                    # its schema transformer rejects a list-valued type.
                    'unit': {'anyOf': [{'type': 'string', 'maxLength': 80}, {'type': 'null'}]},
                    'choices': {'type': 'array', 'maxItems': 200,
                                'items': {'type': 'string', 'minLength': 1, 'maxLength': 2000}},
                    'destination': {'type': 'string', 'minLength': 1, 'maxLength': 128},
                    'uncertainty': {'type': 'string', 'enum': list(UNCERTAINTIES)}}}
    return {'type': 'object', 'additionalProperties': False,
            'required': ['inventory_sha256', 'anchors', 'stories'], 'properties': {
                'inventory_sha256': {'type': 'string'},
                'anchors': {'type': 'array', 'maxItems': 100, 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'required': ['anchor_id', 'question_id', decision, 'metadata'], 'properties': {
                        'anchor_id': {'type': 'string'}, 'question_id': {'type': 'string'},
                        decision: {'type': 'string', 'enum': states}, 'metadata': metadata}}},
                'stories': {'type': 'array', 'maxItems': 1000, 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'required': ['story_id', 'content_sha256', 'verdict'], 'properties': {
                        'story_id': {'type': 'string'}, 'content_sha256': {'type': 'string'},
                        'verdict': {'type': 'string', 'enum': ['retain', 'unresolved']}}}}}}


def _source_metadata(inventory, anchor):
    if (not isinstance(inventory, dict) or inventory.get('protocol') != PROTOCOL
            or not isinstance(inventory.get('anchors'), list)
            or not isinstance(inventory.get('questions'), list)
            or not isinstance(inventory.get('issues'), list) or not isinstance(anchor, dict)):
        _fail('Typed preparation metadata requires a complete new-protocol inventory.')
    matches = [item for item in inventory['anchors']
               if isinstance(item, dict) and item.get('id') == anchor.get('id')]
    if (len(matches) != 1 or matches[0] != anchor or not isinstance(anchor.get('id'), str)
            or not isinstance(anchor.get('question_id'), str)
            or anchor.get('kind') not in {'existing', 'literal_blank', 'protected_blank', 'choose_cell'}
            or type(anchor.get('protected_signing')) is not bool):
        _fail('The metadata answer area is not bound to one original anchor.')
    questions = [question for question in inventory['questions']
                 if isinstance(question, dict) and question.get('id') == anchor['question_id']]
    if (len(questions) != 1 or not isinstance(questions[0].get('text'), str)
            or not 0 < len(questions[0]['text']) <= 2000
            or type(questions[0].get('protected_signing')) is not bool
            or questions[0]['protected_signing'] != anchor['protected_signing']):
        _fail('The metadata question is not bound to the original signing policy.')
    question = questions[0]
    protected = anchor['protected_signing'] or anchor['kind'] == 'protected_blank'
    constraint = question.get('answer_constraints')
    kind, unit, choices = 'text', None, []
    if constraint is not None and not protected:
        if (not isinstance(constraint, dict) or type(constraint.get('version')) is not int
                or constraint['version'] != 1 or constraint.get('data_type') not in TYPES):
            _fail('The original question has an invalid source constraint.')
        kind = constraint['data_type']
        permitted = {'text': {'version', 'data_type'}, 'number': {'version', 'data_type', 'unit'},
                     'integer': {'version', 'data_type'}, 'date': {'version', 'data_type', 'format'},
                     'choice': {'version', 'data_type', 'options'}}[kind]
        if set(constraint) - permitted:
            _fail('The original question constraint includes unsupported metadata.')
        unit = constraint.get('unit')
        if unit is not None and (not isinstance(unit, str) or unit not in PRINTED_UNITS):
            _fail('The original question has an invalid printed unit.')
        if kind == 'choice':
            choices = constraint.get('options')
            if (not isinstance(choices, list) or not 1 <= len(choices) <= 200
                    or any(not isinstance(choice, str) or not 0 < len(choice) <= 2000 for choice in choices)
                    or len(set(choices)) != len(choices)):
                _fail('The original question has invalid printed choices.')
        if kind == 'date' and (not isinstance(constraint.get('format'), str)
                               or constraint['format'] not in PRINTED_DATE_FORMATS):
            _fail('The original question has no declared date format.')
    destinations = [anchor['id']]
    if anchor['kind'] == 'choose_cell':
        offered = anchor.get('choices')
        if (not isinstance(offered, list) or not offered
                or any(not isinstance(choice, dict) or not isinstance(choice.get('id'), str)
                       or not 0 < len(choice['id']) <= 128 for choice in offered)):
            _fail('An uncertain placement has no finite original destinations.')
        destinations = [choice['id'] for choice in offered]
        if len(set(destinations)) != len(destinations) or protected:
            _fail('The placement choices are duplicated or belong to a protected signing area.')
    if protected:
        uncertainty = 'signing_protected'
    elif anchor['kind'] == 'choose_cell':
        uncertainty = 'placement_requires_review'
    elif inventory['issues']:
        uncertainty = 'unsupported_structure'
    elif kind == 'text':
        uncertainty = 'constraints_unstated'
    else:
        uncertainty = 'none'
    return {'label': question['text'], 'data_type': kind, 'unit': unit,
            'choices': deepcopy(choices), 'destination': destinations[0],
            'uncertainty': uncertainty}, destinations


def role_rows(inventory, role):
    """Deterministic fixture rows, explicitly separate from actual API results."""
    if role not in {'proposer', 'checker'}:
        _fail('Unsupported preparation role.')
    key = 'decision' if role == 'proposer' else 'verdict'
    rows = []
    for anchor in inventory.get('anchors', []) if isinstance(inventory, dict) else []:
        metadata, _ = _source_metadata(inventory, anchor)
        needs_review = metadata['uncertainty'] in {'placement_requires_review', 'unsupported_structure'}
        state = ('needs_review' if needs_review else 'map') if role == 'proposer' else ('unresolved' if needs_review else 'pass')
        rows.append({'anchor_id': anchor['id'], 'question_id': anchor['question_id'],
                     key: state, 'metadata': metadata})
    if not rows:
        _fail('The new-protocol inventory has no original answer areas.')
    return rows


def validate_metadata_row(inventory, anchor, row):
    """Role agreement cannot authorize fabricated metadata or destinations."""
    expected, destinations = _source_metadata(inventory, anchor)
    if (not isinstance(row, dict)
            or set(row) not in ({'anchor_id', 'question_id', 'decision', 'metadata'},
                                {'anchor_id', 'question_id', 'verdict', 'metadata'})
            or row['anchor_id'] != anchor['id'] or row['question_id'] != anchor['question_id']):
        _fail('The proposed metadata changed its original question association.')
    if (('decision' in row and (not isinstance(row['decision'], str) or row['decision'] not in {'map', 'needs_review'}))
            or ('verdict' in row and (not isinstance(row['verdict'], str) or row['verdict'] not in {'pass', 'unresolved'}))):
        _fail('The proposed metadata has an unsupported role decision.')
    metadata = row['metadata']
    if (not isinstance(metadata, dict) or set(metadata) != METADATA_KEYS
            or any(not isinstance(metadata[key], str) for key in ('label', 'data_type', 'destination', 'uncertainty'))
            or metadata['unit'] is not None and not isinstance(metadata['unit'], str)
            or not isinstance(metadata['choices'], list)
            or any(not isinstance(choice, str) for choice in metadata['choices'])):
        _fail('The proposed field metadata is not the closed structured schema.')
    if metadata['destination'] not in destinations:
        _fail('The proposed destination is not one of the original finite answer areas.')
    expected['destination'] = metadata['destination']
    if metadata != expected:
        _fail('The proposed field metadata differs from the original question, constraints or protection.')
    return row
