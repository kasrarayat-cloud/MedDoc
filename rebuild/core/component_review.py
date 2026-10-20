"""Explicit, revision-bound editing of one prospective form requirement draft."""
from copy import deepcopy
from types import SimpleNamespace

from django.core import signing
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from documents.component_contracts import ENCOUNTER_CONTRACT, RENDERINGS, UNIT_REQUIREMENTS
from documents.semantic_preparation_roles import (
    ANSWER_MODES, ANSWER_TYPES, CONSTRAINT_KEYS, POLARITIES, SUBJECTS, TEMPORALITIES,
    DefinitionError, digest, protected_field,
)
from . import semantic_preparation as workflow, template_review
from .save_recovery import recoverable_save, binding as save_binding

SALT = 'field-components-review-v1'
OUTER_CONTROLS = ('meaning', 'value_type', 'answer_mode', 'patient_name_requirement', 'unit',
                  'choices', 'subject', 'temporality', 'polarity', *CONSTRAINT_KEYS)
PART_CONTROLS = ('question_quote', 'label', 'meaning', 'value_type', 'subject', 'temporality',
                 'polarity', 'unit', 'unit_requirement')
ENCOUNTER_SCOPE_LABELS = [('current', 'This encounter'), ('past', 'Past encounters'),
                        ('all_documented', 'This encounter and documented past encounters')]


def part_controls(definition):
    return PART_CONTROLS + (('encounter_scope',) if definition['component_contract']['contract'] == ENCOUNTER_CONTRACT else ())


def binding(prep, actor, field_key):
    return {'actor': str(actor.pk), 'preparation': str(prep.pk), 'field': field_key,
            'revision': prep.revision, 'preparation_sha256': workflow.approval_binding(prep)}


def token_for(prep, actor, field_key):
    return signing.dumps(binding(prep, actor, field_key), salt=SALT, compress=True)


def verify_token(prep, actor, field_key, token):
    try:
        value = signing.loads(token, salt=SALT, max_age=12*60*60)
    except signing.BadSignature as exc:
        raise ValidationError('This component review expired. Reopen the current definition before saving.') from exc
    if value != binding(prep, actor, field_key):
        raise ValidationError('The form changed after this component review opened. Reopen it; nothing was saved.')


def one(post, key):
    values = post.getlist(key)
    if len(values) != 1:
        raise ValidationError('A required-part control is missing or repeated. Reopen the current review.')
    return values[0].replace('\r\n', '\n').replace('\r', '\n')


def checked(post, key):
    values = post.getlist(key)
    if not values:
        return False
    if values != ['on']:
        raise ValidationError('A required-part decision is repeated or invalid.')
    return True


def parts_for(field, definition):
    parts = [deepcopy(c) for c in definition['component_contract']['components']]
    used = {c['id'] for c in parts}
    if not protected_field(field) and len(parts) < 30:
        index = 1
        while 'part_'+str(index) in used:
            index += 1
        parts.append({'id': 'part_'+str(index), 'question_quote': field['label'], 'label': None,
            'meaning': '', 'value_type': 'text', 'scope': {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'},
            'unit': None, 'unit_requirement': 'none', 'required': True, 'new': True})
        if definition['component_contract']['contract'] == ENCOUNTER_CONTRACT:
            parts[-1]['encounter_scope'] = ''  # An added part requires an explicit choice.
    return [{**p, 'index': i} for i, p in enumerate(parts)]


def posted_definition(prep, field, current, post):
    from .semantic_preparation_views import posted_definitions
    prefix = 'field_'+field['key']+'_'
    normalized = post.copy()
    for name in OUTER_CONTROLS:
        normalized[prefix+name] = one(post, prefix+name)
    proxy = SimpleNamespace(source_version=SimpleNamespace(fields=[field]),
        config={'semantic_definition_version': 4}, component_baseline={field['key']: current})
    value = posted_definitions(proxy, normalized)[field['key']]
    for name in ('meaning', 'unit'):
        old = current[name]
        if old is not None and one(post, prefix+name) == old.replace('\r\n', '\n').replace('\r', '\n'):
            value[name] = old
    choices = one(post, prefix+'choices')
    if choices == '\n'.join(current['choices']).replace('\r\n', '\n').replace('\r', '\n'):
        value['choices'] = deepcopy(current['choices'])
    elif any('\n' in c or '\r' in c for c in current['choices']):
        raise ValidationError('Keep the original multiline choice boundaries unchanged.')
    rendering = one(post, 'rendering')
    controls = part_controls(current)
    components = []
    allowed = {'csrfmiddlewaretoken', 'component_token', 'rendering', 'reason', 'component_reviewed'} | {
        prefix+name for name in OUTER_CONTROLS}
    for part in parts_for(field, current):
        base = 'part_'+str(part['index'])+'_'
        allowed.update(base+name for name in (*controls, 'remove', 'add'))
        remove, add = checked(post, base+'remove'), checked(post, base+'add')
        if (part.get('new') and remove) or (not part.get('new') and add):
            raise ValidationError('A required-part action does not match this retained review.')
        if remove or part.get('new') and not add:
            continue
        raw = {name: one(post, base+name) for name in controls}
        for name in ('question_quote', 'label', 'meaning', 'unit'):
            old = part.get(name)
            if old is not None and raw[name] == old.replace('\r\n', '\n').replace('\r', '\n'):
                raw[name] = old
        components.append({'id': part['id'], 'question_quote': raw['question_quote'],
            'label': raw['label'] or None, 'meaning': raw['meaning'], 'value_type': raw['value_type'],
            'scope': {name: raw[name] for name in ('subject', 'temporality', 'polarity')},
            'unit': raw['unit'] or None, 'unit_requirement': raw['unit_requirement'], 'required': True})
        if 'encounter_scope' in controls:
            components[-1]['encounter_scope'] = raw['encounter_scope']
    if set(post) - allowed:
        raise ValidationError('This component form has unsupported controls. Reopen it; nothing was saved.')
    if not checked(post, 'component_reviewed'):
        raise ValidationError('Compare every required part with the original question and confirm this component review.')
    value['component_contract'] = {'contract': current['component_contract']['contract'], 'rendering': rendering, 'components': components}
    return value


@recoverable_save('definitions')
@require_http_methods(['GET', 'POST'])
def edit(request, pk, field_key):
    from .semantic_preparation_views import selected
    prep, member = selected(request, pk)
    if member.role not in ('owner', 'clinician') or workflow.definition_version(prep.config) != 4:
        raise Http404()
    fields = {f['key']: f for f in prep.source_version.fields}
    if field_key not in fields:
        raise Http404()
    field = fields[field_key]
    values = workflow.corrected_definitions(prep)
    current = values[field_key]
    error, token_valid = '', False
    display_definition = current
    display_parts = parts_for(field, current)
    if request.method == 'POST':
        try:
            verify_token(prep, request.user, field_key, one(request.POST, 'component_token'))
            token_valid = True
            definition = posted_definition(prep, field, current, request.POST)
            workflow.correct_components(prep.pk, request.user, field_key,
                one(request.POST, 'component_token'), definition, one(request.POST, 'reason'))
            return redirect('template_definitions', pk=prep.pk)
        except (ValidationError, DefinitionError) as exc:
            error = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
            if token_valid:
                # Preserve entered controls for correction without treating them
                # as validated definitions or changing the retained draft.
                display_definition = deepcopy(current)
                prefix = 'field_'+field_key+'_'
                for name in ('meaning', 'value_type', 'answer_mode', 'patient_name_requirement', 'unit'):
                    if len(request.POST.getlist(prefix+name)) == 1:
                        display_definition[name] = request.POST[prefix+name]
                for name in ('subject', 'temporality', 'polarity'):
                    if len(request.POST.getlist(prefix+name)) == 1:
                        display_definition['scope'][name] = request.POST[prefix+name]
                for name in CONSTRAINT_KEYS:
                    if len(request.POST.getlist(prefix+name)) == 1:
                        display_definition['constraints'][name] = request.POST[prefix+name] or None
                if len(request.POST.getlist(prefix+'choices')) == 1:
                    display_definition['choices'] = request.POST[prefix+'choices'].splitlines()
                if len(request.POST.getlist('rendering')) == 1:
                    display_definition['component_contract']['rendering'] = request.POST['rendering']
                for part in display_parts:
                    base = 'part_'+str(part['index'])+'_'
                    for name in part_controls(current):
                        if len(request.POST.getlist(base+name)) == 1:
                            if name in ('subject', 'temporality', 'polarity'):
                                part['scope'][name] = request.POST[base+name]
                            else:
                                part[name] = request.POST[base+name]
                    part['remove'] = request.POST.getlist(base+'remove') == ['on']
                    part['add'] = request.POST.getlist(base+'add') == ['on']
    row = template_review.rows([{'field': field, 'definition': display_definition, 'state': ''}])[0]
    return render(request, 'template_component_review.html', {
        'preparation': prep, 'template': prep.source_version.template, 'row': row,
        'parts': display_parts, 'definition_version': 4,
        'component_editing': True,
        'component_token': token_for(prep, request.user, field_key),
        'save_binding': save_binding(prep, 'definitions'),
        'renderings': RENDERINGS,
        'component_encounter_scopes': ENCOUNTER_SCOPE_LABELS if current['component_contract']['contract'] == ENCOUNTER_CONTRACT else [],
        'unit_requirements': [('none', 'No unit required'), ('documented', 'Keep the documented unit and scale'),
                              ('printed', 'Use the exact unit printed on the form')],
        'component_types': list(template_review.TYPE_LABELS.items()),
        'subjects': list(template_review.SUBJECT_LABELS.items()),
        'temporalities': list(template_review.TIMING_LABELS.items()),
        'polarities': list(template_review.POLARITY_LABELS.items()),
        'editable': prep.state in workflow.EDITABLE,
        'reason': request.POST.get('reason', '') if token_valid else '',
        'error': error}, status=409 if error else 200)
