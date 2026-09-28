"""Prepared, default-off context relations for two ordinary history roles.

The model's context classification is clinical evidence requiring qualification,
not proof supplied by this module. This validates references and provenance only.
Existing source guards retain their veto; no clinician or historical draft is
assigned a new model decision. No source text is sent in another request.
"""
import hashlib
import json
from typing import Literal

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from pydantic import BaseModel, ConfigDict, StrictInt

from .generation import UnitSelection

CONTRACT = 'ordinary-history-context-v1'
MAX_UNITS = 64
SALT = 'quillmd.ordinary-history-context.v1'
ROLES = {'chief complaint': 'chief', 'history of present illness': 'hpi', 'hpi': 'hpi'}
INSTRUCTIONS = (' For the listed history_context_targets only, return a complete context relation: '
    'classify EVERY offered source unit exactly once as answer, context_only, required_qualifier, contrary, or unresolved. '
    'Answer units are the exact selected output sentences. Required qualifiers must also be selected in full; '
    'never drop a qualifier of subject, negation, time, uncertainty or scope. Contrary or unresolved context holds the answer. '
    'Context_only means the complete source statement neither changes nor is needed to interpret this particular answer; '
    'it is not permission to ignore a clinically related Assessment. Patient attribution alone does not establish independence. '
    'Keep a known same-patient statement reusable in distinct Chief complaint and HPI fields, but never in repeated or scoped questions. '
    'No newly composed wording or inferred clinical meaning. Empty output remains missing. Return all context references, including negatives.')


class UnitRelation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    unit_id: StrictInt
    relation: Literal['answer', 'context_only', 'required_qualifier', 'contrary', 'unresolved']


class HistoryRelation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str
    units: list[UnitRelation]


class HistorySelections(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fields: list[UnitSelection]
    history_context: list[HistoryRelation]


def enabled(config=None):
    return bool(getattr(settings, 'V3_HISTORY_CONTEXT', False)) and (
        config is None or config.get('history_context_contract') == CONTRACT)


def refuse_request(config):
    """This prepared contract cannot silently ride a legacy model rollback."""
    if not enabled(config):
        raise ValidationError('History context was switched off; generate again.')
    if config.get('provider') != 'anthropic' or config.get('model') != 'claude-sonnet-5':
        raise ValidationError('History context requires the exact native claude-sonnet-5 model.')


def targets(fields, units):
    from .generation import question_key
    if not 0 < len(units) <= MAX_UNITS:
        return {}
    by_role = {}
    for field in fields:
        role = ROLES.get(question_key(field.get('label')))
        if role:
            by_role.setdefault(role, []).append(field)
    return {group[0]['key']: group[0] for group in by_role.values() if len(group) == 1
            and group[0].get('kind') in ('text', 'long_text')
            # The importer repeats a table's own label as context. It adds no
            # external section/role; any actual additional context stays held.
            and question_key(group[0].get('context') or '') in ('', question_key(group[0]['label']))
            and not group[0].get('write_protected')
            and group[0].get('locator', {}).get('contract') == 'v3'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def binding(notes, fields, context_labels):
    return digest({'notes': notes, 'fields': fields, 'context_labels': list(context_labels), 'contract': CONTRACT})


def records(notes, fields, context_labels, units, selections):
    """Validate the closed full-source partition; mint server-only provenance."""
    if not enabled():
        raise ValidationError('History context is disabled; no answers adopted.')
    eligible = targets(fields, units)
    relations = selections.history_context
    if len(relations) != len(eligible) or {r.key for r in relations} != set(eligible):
        raise ValidationError('History context contains missing, duplicated or unknown fields.')
    selected = {f.key: f for f in selections.fields}
    known = {u['id'] for u in units}
    out = {}
    for relation in relations:
        refs = [entry.unit_id for entry in relation.units]
        if len(refs) != len(known) or set(refs) != known:
            raise ValidationError('History context must cover every source unit exactly once.')
        pick = selected.get(relation.key)
        if pick is None:
            raise ValidationError('History context has no matching answer selection.')
        partition = {entry.unit_id: entry.relation for entry in relation.units}
        chosen = set(pick.unit_ids)
        if any(partition[unit] == 'context_only' for unit in chosen) or any(
                kind == 'answer' and unit not in chosen for unit, kind in partition.items()):
            raise ValidationError('History context disagrees with its exact output selection.')
        payload = {'contract': CONTRACT, 'binding': binding(notes, fields, context_labels),
                   'key': relation.key, 'output': sorted(chosen),
                   'partition': [entry.model_dump() for entry in relation.units],
                   'conflict': pick.conflict}
        out[relation.key] = signing.dumps(payload, salt=SALT, compress=True)
    return out


def read(reading, label, evidence, record, *, text=None):
    """Return exact permitted IDs or visible warnings, never a new interpretation."""
    from . import generation as g, v3_syntax
    empty = {'ids': set(), 'warnings': []}
    if record is None:
        return empty
    units = reading['units']
    refused = {'ids': set(), 'warnings': units or [reading['source']]}
    if not enabled() or not isinstance(record, str) or len(record) > 50000:
        return refused
    try:
        value = signing.loads(record, salt=SALT)
        if (not isinstance(value, dict) or set(value) != {'contract', 'binding', 'key', 'output', 'partition', 'conflict'}
                or type(value['conflict']) is not bool or not isinstance(value['output'], list)
                or any(type(i) is not int for i in value['output'])):
            return refused
        eligible = targets(reading['fields'], units)
        field = eligible.get(value['key'])
        if (value['contract'] != CONTRACT or value['binding'] != binding(
                reading['source']['quote'], reading['fields'], reading['context_labels'])
                or not field or g.question_key(field['label']) != g.question_key(label)):
            return refused
        chosen = value['output']
        indexed = {u['id']: u for u in units}
        expected = [{k: indexed[i][k] for k in ('quote', 'start', 'end')} for i in chosen]
        values = [reading['parsed'][i][1] if reading['parsed'][i] else indexed[i]['quote'] for i in chosen]
        if evidence != expected or (text is not None and text != '\n'.join(values)):
            return refused
        # Re-validate even server-created records when reading a later draft.
        relation = HistoryRelation(key=value['key'], units=value['partition'])
        refs = [entry.unit_id for entry in relation.units]
        if len(refs) != len(units) or set(refs) != set(indexed) or len(chosen) != len(set(chosen)):
            return refused
        partition = {entry.unit_id: entry.relation for entry in relation.units}
        if (value['conflict'] or any(kind in ('contrary', 'unresolved') or
                (kind == 'required_qualifier' and unit not in chosen)
                or (kind == 'answer' and unit not in chosen)
                for unit, kind in partition.items()) or any(partition[i] == 'context_only' for i in chosen)):
            return refused
        # An unlabelled history may reuse a proven actor; a pronoun alone cannot
        # inherit from the grammatical subject of a sentence mentioning a father.
        actors = reading['actor_relations']['units']
        explicit, subject_spans = [], {}
        for i in chosen:
            unit = indexed[i]
            own = reading['parsed'][i]
            if ((own and own[0] != g.question_key(label)) or
                    (reading['subjects'][i] and reading['subjects'][i] != g.question_key(label))
                    or i in reading['unresolved_subjects']):
                return refused
            if not own and i not in actors and not reading['patients'].get(i):
                return refused
            if match := g.EXPLICIT_PATIENT_SUBJECT.match(unit['quote']):
                end = len(match.group().rstrip())
                explicit.append(unit); subject_spans[i] = (end - len('patient'), end)
            if g.v3_shape_holds(unit['quote'], unit['quote']):
                return refused
        if set(subject_spans) != v3_syntax.complete_ids(explicit, subject_spans=subject_spans):
            return refused
        return {'ids': set(chosen), 'warnings': []}
    except (signing.BadSignature, KeyError, TypeError, ValueError, ValidationError):
        return refused
