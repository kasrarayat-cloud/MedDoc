"""Display-only field summaries and explicit, snapshot-bound review consent.

The workflow still owns validation, locking and immutable approval. This adapter
translates one informed review into its existing exhaustive review lists. A GET,
AI result, checked-by-default control or an unsaved edit cannot do that.
"""
import hashlib
import json
import re
from types import SimpleNamespace
from django.core import signing
from django.core.exceptions import ValidationError
from documents.semantic_preparation_roles import CONSTRAINT_KEYS, protected_field
from .field_location import describe

TYPE_LABELS = {'person_name': 'Name', 'identifier': 'Reference / identifier', 'date': 'Date',
               'integer': 'Whole number', 'number': 'Number', 'choice': 'Choice', 'text': 'Text'}
SUBJECT_LABELS = {'patient': 'Patient', 'clinician': 'Clinician', 'encounter': 'Visit',
                  'other': 'Other person', 'unspecified': 'Not yet specified'}
TIMING_LABELS = {'current': 'Current', 'past': 'Past', 'future': 'Future', 'any': 'Any documented time'}
POLARITY_LABELS = {'any': 'Include positive and negative statements',
                   'positive': 'Positive statements only', 'negative': 'Negative statements only'}
MODE_LABELS = {'atomic': 'One concise value', 'narrative': 'Relevant narrative facts'}


def review_items(prep, items):
    """Ask once when a printed name label leaves the person's role unstated.

    Model context can suggest Patient, but a generic printed name still needs a
    clinician's explicit choice in setup. Qualified labels and previously
    reviewed/approved definitions keep their existing behavior.
    """
    corrected = prep.corrections.get('answer_definitions') if hasattr(prep, 'candidate_sha256') else prep.corrections
    result = []
    for item in items:
        row = {**item}
        definition = row.get('definition') or {}
        # A role can be attached to another word by the legacy Word inspector
        # (PatientFullname). Use spacing only for classification, not display.
        # A role in an instruction ("clinician to complete") does not identify
        # whose name belongs here; only a complete role/name phrase qualifies.
        role_label = re.sub(r'([a-z])([A-Z])', r'\1 \2', row['field']['label'])
        role_label = re.sub(r'\([^)]*\)', '', role_label).strip(' :*')
        role = (r'(?:patient|clinician|doctor|physician|provider|nurse|surgeon|therapist|witness|'
                r'guardian|parent|carer|caregiver|mother|father|contact|referrer|consultant|assessor|author|staff|practitioner)')
        name = r'(?:(?:full|legal|first|last|given|family|middle|complete)\s+)*names?'
        qualified = re.fullmatch(r'(?:the\s+)?'+role+r'(?:[’\']s)?\s+'+name+r'|'+name+r'\s+of\s+(?:the\s+)?'+role,
                                 role_label, re.IGNORECASE)
        if (prep.state != 'approved' and not corrected and not qualified
                and definition.get('value_type') == 'person_name'):
            row.update(state='unresolved', reason='The name label does not specify whose name belongs here.')
        result.append(row)
    return result


def label_text(label):
    return ' '.join(label.split())


def label_displays(template):
    """Restore actual Word paragraph/break spacing, never guess from capital letters.

    Label text can span formatted runs (HbA1c, McDonald), so run boundaries are
    not spaces. Ambiguous duplicate representations keep their stored spelling.
    """
    if template.format != 'docx': return {}
    from documents import inspect_template, DocumentError
    from documents.preparation_service import read_original
    from .security import private_path
    path = private_path(template.original_path)
    if hashlib.sha256(read_original(path)).hexdigest() != template.sha256:
        raise ValidationError('The original form failed its integrity check.')
    from django.core.cache import cache
    cache_key = 'template-review-labels-v1:'+template.sha256
    cached = cache.get(cache_key)
    if cached is not None: return cached
    try:
        result = inspect_template(path)
    except DocumentError:
        # Historical mappings can remain exportable when a newer inspector would
        # refuse a fresh upload. Optional display metadata must not strand them.
        return {}
    if result['sha256'] != template.sha256:
        raise ValidationError('The original form failed its integrity check.')
    labels = result.get('display_labels', {})
    cache.set(cache_key, labels, 86400)
    return labels


def rows(items, labels=None):
    result = []
    for original in items:
        row = {**original}
        field, definition = row['field'], row.get('definition') or {}
        label = (labels or {}).get(field['label'], label_text(field['label']))
        kind = definition.get('value_type')
        constraints = definition.get('constraints', {})
        summary = TYPE_LABELS.get(kind, 'Answer field')
        low, high = constraints.get('scale_minimum'), constraints.get('scale_maximum')
        if low is None: low = constraints.get('minimum')
        if high is None: high = constraints.get('maximum')
        if kind in {'integer', 'number'}:
            if low is not None and high is not None:
                summary = f'{"Whole number" if kind == "integer" else "Number"} from {low} to {high}'
            elif low is not None: summary += f' · minimum {low}'
            elif high is not None: summary += f' · maximum {high}'
        unit = definition.get('unit')
        if unit:
            if unit.casefold() in {'celsius', '°c', 'degrees celsius', 'degree celsius'}:
                summary = 'Temperature in Celsius'
                if kind == 'integer': summary += ' · whole degrees'
            else: summary += f' · {unit}'
        if kind == 'text' and definition.get('answer_mode') == 'narrative': summary = 'Narrative'
        limits = []
        for key, title in [('minimum', 'Minimum'), ('maximum', 'Maximum')]:
            if constraints.get(key) is not None: limits.append(f'{title} {constraints[key]}')
        if constraints.get('scale_minimum') is not None:
            limits.append(f'Scale {constraints["scale_minimum"]} to {constraints["scale_maximum"]}')
        scope = definition.get('scope', {})
        subject = SUBJECT_LABELS.get(scope.get('subject'), '')
        scope_notes = []
        if scope.get('temporality') in {'current', 'past', 'future'}:
            scope_notes.append(TIMING_LABELS[scope['temporality']]+' information')
        if scope.get('polarity') in {'positive', 'negative'}:
            scope_notes.append(POLARITY_LABELS[scope['polarity']])
        location = describe(field)
        if 'cell' in (field.get('locator') or {}): location = f'Response beside “{label}”'
        row.update(display_label=label, type_summary=summary, subject_label=subject,
                   scope_summary=' · '.join(scope_notes), protected=protected_field(field),
                   reason=row.get('reason', '').replace('Save doctor corrections', 'Save decisions'),
                   location=location, name_question=row.get('name_question_type', kind) == 'person_name' and row.get('state') == 'unresolved',
                   numeric=kind in {'integer', 'number'}, choice=kind == 'choice', constraints_summary=' · '.join(limits),
                   type_options=[(k,v) for k,v in TYPE_LABELS.items() if definition.get('version') == 2 or k not in {'person_name', 'identifier'}], subject_options=list(SUBJECT_LABELS.items()),
                   timing_options=list(TIMING_LABELS.items()), polarity_options=list(POLARITY_LABELS.items()),
                   mode_options=list(MODE_LABELS.items()))
        result.append(row)
    return result


def snapshot(prep, items, user_id, operation):
    source = getattr(prep, 'source_version', None)
    template = source.template if source else prep.template
    payload = {'operation': operation, 'user': str(user_id), 'preparation': str(prep.pk),
        'revision': prep.revision, 'state': prep.state, 'source': str(source.pk) if source else str(template.pk),
        'source_sha256': template.sha256, 'inventory': prep.inventory, 'config': prep.config,
        'candidate': getattr(prep, 'candidate_sha256', ''), 'changes': getattr(prep, 'changes', []),
        'fields': [{'field': r['field'], 'definition': r['definition'], 'state': r.get('state'),
                    'reason': r.get('reason', '')} for r in items]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def tokens(prep, items, user_id):
    return {f'review_token_{op}': signing.dumps(snapshot(prep, items, user_id, op), salt='template-review-v1')
            for op in ('save', 'approve')}


def submitted(prep, items, user, post, operation):
    """All controls must round-trip, including hidden inapplicable blank values."""
    try:
        sealed = signing.loads(post.get(f'review_token_{operation}', ''), salt='template-review-v1', max_age=28800)
    except signing.BadSignature:
        raise ValidationError('This review has expired or changed. Reload the form and review it again.')
    if sealed != snapshot(prep, items, user.pk, operation):
        raise ValidationError('The form changed since this review opened. Reload and compare the current definitions.')
    if post.get('review_summary') != 'on':
        raise ValidationError('Compare all fields with the original and confirm the review summary before continuing.')
    baseline = {r['field']['key']: r['definition'] for r in items}
    if not baseline:
        raise ValidationError('Answer definitions are not available for this review.')
    for key, definition in baseline.items():
        names = ['meaning', 'value_type', 'unit', 'choices', 'subject', 'temporality', 'polarity', *CONSTRAINT_KEYS]
        if definition['version'] == 2: names.append('answer_mode')
        if any(len(post.getlist('field_'+key+'_'+name)) != 1 for name in names):
            raise ValidationError('A definition control is missing or repeated. Reload before reviewing this form.')
    from .semantic_preparation_views import posted_definitions
    proxy = SimpleNamespace(source_version=SimpleNamespace(fields=[r['field'] for r in items]),
                            config={'semantic_definition_version': next(iter(baseline.values()))['version']})
    normalized = post.copy()
    newline = lambda value: value.replace('\r\n', '\n').replace('\r', '\n')
    for key in baseline:
        for name in ('meaning', 'choices'):
            control = 'field_'+key+'_'+name
            normalized[control] = newline(post[control])
    values = posted_definitions(proxy, normalized)
    for key, current in baseline.items():
        prefix = 'field_'+key+'_'
        # Browser form encoding normalizes textarea newlines. An unchanged
        # control means the EXACT retained value, not a rewrite of its bytes.
        if normalized[prefix+'meaning'] == newline(current['meaning']):
            values[key]['meaning'] = current['meaning']
        if normalized[prefix+'choices'] == newline('\n'.join(current['choices'])):
            values[key]['choices'] = list(current['choices'])
        elif any('\n' in choice or '\r' in choice for choice in current['choices']):
            raise ValidationError('This form has multiline choices. Keep the allowed choices unchanged so their original option boundaries are preserved.')
        unit = current['unit'] or ''
        if post[prefix+'unit'] == unit.replace('\r', '').replace('\n', ''):
            values[key]['unit'] = current['unit']
    decisions = []
    for row in items:
        key = row['field']['key']
        current, value = baseline[key], values[key]
        if row.get('state') == 'unresolved':
            if operation == 'approve':
                raise ValidationError('Resolve and save the open questions before approving this template.')
            if current['value_type'] == 'person_name':
                subject = post.get('name_subject_'+key, '')
                if subject not in {'patient', 'clinician', 'other'}:
                    raise ValidationError(f'Whose name belongs in {label_text(row["field"]["label"])}? Choose a person.')
                other = post.get('name_other_'+key, '').strip()
                if subject == 'other' and not 3 <= len(other) <= 120:
                    raise ValidationError('Describe whose name belongs here when choosing Other person.')
                role = {'patient': 'patient', 'clinician': 'clinician', 'other': other}[subject]
                value['scope']['subject'] = subject
                # This replacement is disclosed beside the explicit question and
                # previewed on selection. The original model response stays intact.
                if value['meaning'] == current['meaning']:
                    value['meaning'] = f'{label_text(row["field"]["label"])}: the {role}’s name, as requested by this form.'
                decisions.append(f'{label_text(row["field"]["label"])}: {role}')
            else:
                decision = post.get('decision_'+key, '')
                if (decision not in {'accept', 'edit'} or (decision == 'edit' and value == current)
                        or (decision == 'accept' and value != current)):
                    raise ValidationError(f'Resolve the question for {label_text(row["field"]["label"])} before saving.')
                decisions.append(f'{label_text(row["field"]["label"])}: {"confirmed proposed meaning" if decision == "accept" else "edited definition"}')
        if value['scope']['subject'] != current['scope']['subject'] and value['meaning'] == current['meaning']:
            raise ValidationError('When changing whom a field describes, update its meaning to describe that person too.')
    if operation == 'approve' and values != baseline:
        raise ValidationError('Save your edited definitions before approving this template. No version was created.')
    changed = [label_text(r['field']['label']) for r in items if values[r['field']['key']] != baseline[r['field']['key']]]
    reason = 'Reviewed the complete original, field meanings, constraints and destinations. '
    reason += '; '.join(decisions) if decisions else 'Explicit definition edits: '+', '.join(changed)
    return values, list(baseline), reason[:1000]
