"""Exact labelled synthetic v4 responses; never clinical or provider evidence."""
import json
from types import SimpleNamespace

from . import generation as g, v3_field_relations as r


def body(notes, catalogue, asked, context_labels, *, requested_ids=None, units=None):
    units = list(units if units is not None else g.source_units(notes, asked, context_labels=context_labels)[0])
    requested = [f for f in asked if requested_ids is None or f['key'] in requested_ids]
    labels = g.recognized_labels(asked, context_labels)
    parsed = {u['id']: g.labelled_value(u['quote'], labels) for u in units}
    owners = {}
    for field in catalogue:
        owners.setdefault(g.question_key(field['label']), []).append(field['key'])
    selected = {pick.key: pick.quotes for pick in g.fixture(notes, asked, context_labels=context_labels).fields}
    with_options = any(r.options(f) for f in requested)
    rows = []
    reading = None
    for field in requested:
        key = field['key']; label = g.question_key(field['label'])
        chosen = [u['id'] for u in units if u['quote'] in selected[key]]
        partition = {name: [] for name in r.PARTITION}
        for unit in units:
            own = parsed[unit['id']]
            relation = ('answer' if unit['id'] in chosen else 'independent'
                        if own and own[1] and own[0] != label and len(owners.get(own[0], ())) == 1
                        else 'unresolved')
            if relation == 'unresolved' and chosen and unit['quote'].count(':') == 1:
                # A reviewed-out human destination is absent from the mapping.
                # Its complete document-status metadata can still be unrelated
                # to an exact own-labelled ordinary answer. Use the same closed
                # source proof as governance; never infer a signer or patient.
                from .source_scope import completed_document_status_boundary
                if reading is None:
                    reading = g.governance_for(notes, catalogue, context_labels, v3_units=units)[11]['preceding']
                selected_units = [u for u in units if u['id'] in chosen]
                if completed_document_status_boundary(reading, unit, selected_units, field):
                    relation = 'independent'
            partition[relation].append(unit['id'])
        row = {'key': key, 'unit_ids': chosen, 'conflict': False, 'context': partition}
        if with_options:
            # Only an exact printed option supplied under this field's own
            # complete label can choose an option. No polarity inference.
            values = [g.v3_option_value(field, parsed[uid][1]) for uid in chosen]
            matched = {g.question_key(v) for v in values if v}
            row['option_ids'] = ([o['id'] for o in r.options(field) if g.question_key(o['text']) in matched]
                                 if values and all(values) else [])
        rows.append(row)
    return {'fields': rows}


def result(notes, catalogue, compiled, config):
    wire = body(notes, catalogue, compiled['asked'], compiled['context'], units=compiled['units'])
    # The existing validator reads the same bound response shape; the caller
    # separately settles this as simulated, with no provider id or cost.
    response = SimpleNamespace(model=config['model'], stop_reason='end_turn',
        content=[SimpleNamespace(type='text', text=json.dumps(wire))])
    raw = {'anthropic_response': response, 'ordinary_field_contract': r.CONTRACT,
        'notes': notes, 'fields': compiled['asked'], 'full_catalogue': catalogue,
        'context_labels': compiled['context'], 'requested_model': config['model']}
    if config.get('patient_default_context'):
        raw['patient_default_context'] = config['patient_default_context']
    return r.validated(raw)
