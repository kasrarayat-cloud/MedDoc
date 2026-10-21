"""Display-only field summaries and explicit, snapshot-bound review consent.

The workflow still owns validation, locking and immutable approval. This adapter
translates one informed review into its existing exhaustive review lists. A GET,
AI result, checked-by-default control or an unsaved edit cannot do that.
"""
import hashlib
import json
import re
import unicodedata
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
PATIENT_NAME_LABELS = {'none': 'No additional requirement', 'documented': 'Include documented patient name'}


def _printed_name_subject(label):
    """Resolve the requested person from complete, bounded printed clauses.

    A completion actor is not an answer subject. Unknown instructions, competing
    requested roles and exclusions of the requested person remain reviewable;
    neither a model's subject nor its proposed meaning supplies missing context.
    """
    text = unicodedata.normalize('NFKC', label)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text).casefold()
    text = re.sub(r'(?m)^\s*\d+(?:[.)]\s*|\s+)', '', text)
    clinical = r'(?:clinician|doctor|physician|provider|nurse|surgeon|therapist|practitioner)'
    role = (r'(?:(?:referring|treating|attending|consulting|supervising)\s+)?'+clinical+
            r'|patient|witness|guardian|parent|carer|caregiver|mother|father|contact|referrer|consultant|assessor|author|staff')
    name = r'(?:(?:full|legal|first|last|given|family|middle|complete)\s+)*names?'
    # Occupation and functional role are separate dimensions. A referring
    # physician remains a physician; sibling occupations/roles are not aliases.
    parents = {'physician': ('clinician',), 'surgeon': ('physician',),
               'nurse': ('clinician',), 'therapist': ('clinician',),
               'provider': ('clinician',), 'practitioner': ('clinician',),
               'mother': ('parent',), 'father': ('parent',)}
    unspecified_subject_roles = {'staff', 'author', 'assessor'}

    def role_parts(value):
        parts = value.split()
        return parts[-1], tuple(parts[:-1])

    def ancestry(occupation):
        result, pending = set(), [occupation]
        while pending:
            current = pending.pop()
            if current not in result:
                result.add(current)
                pending.extend(parents.get(current, ()))
        return result

    def is_clinical(value):
        return 'clinician' in ancestry(role_parts(value)[0])
    verbs = r'(?:record|document|enter|provide|give|identify|specify|state|write(?:\s+down)?|name(?!\s+of\b))'
    actor = r'(?:the\s+)?(?:'+role+r')\s+(?:to\s+complete|to\s+fill\s+in|use\s+only)'
    # These annotations affect presentation/completion, never whose name it is.
    annotation = r'(?:please\s+print|in\s+block\s+letters|if\s+documented|'+actor+r'|for\s+(?:the\s+)?(?:'+role+r')\s+use)'
    text = re.sub(r'\(\s*'+annotation+r'\s*\)', '', text)
    text = text.replace('(', ',').replace(')', ',')
    requested, explicit, excluded = set(), set(), set()

    def person(value):
        value = value.strip()
        value = re.sub(r'^(?:the\s+)', '', value)
        match = re.fullmatch(r'('+role+r')(?:[’\']s)?\s+'+name+
                             r'|'+name+r'\s+of\s+(?:the\s+)?('+role+r')', value)
        if match:
            value = next(part for part in match.groups() if part is not None)
        elif not re.fullmatch(role, value):
            # The object of an explicit identity request can itself be qualified
            # by a relative clause ("the clinician who referred the patient").
            match = re.fullmatch(r'('+role+r')\s+who\s+(.+)', value)
            if not match:
                return None
            value = match[1]
            # Do not discard an arbitrary relative clause: it may identify a
            # different person or exclude the heading's person. Admit a bounded
            # affirmative identity or care relation; unknown relations stay open.
            identity = re.fullmatch(r'is\s+(?:the\s+)?('+role+r')', match[2])
            if identity:
                return person(identity[1])
            relation = re.fullmatch(
                r'(referred|refers|treated|treats|supervised|supervises|'
                r'assessed|examined|evaluated|saw|cared\s+for)\s+(?:the\s+)?patient', match[2])
            if not relation:
                return None
            modifier = {'referred': 'referring', 'refers': 'referring',
                        'treated': 'treating', 'treats': 'treating',
                        'supervised': 'supervising', 'supervises': 'supervising'}.get(relation[1])
            if modifier and re.fullmatch(clinical, value.split()[-1]):
                parts = value.split()
                if len(parts) > 1 and parts[0] != modifier:
                    return None
                value = modifier+' '+parts[-1]
        if value in {'referrer', 'consultant'}:
            return {'referrer': 'referring clinician', 'consultant': 'consulting clinician'}[value]
        parts = value.split()
        if re.fullmatch(clinical, parts[-1]):
            return ' '.join([*parts[:-1], {'doctor': 'physician'}.get(parts[-1], parts[-1])])
        return {'caregiver': 'carer'}.get(value, value)

    for clause in re.split(r'[\n;.!?,]+', text):
        clause = clause.strip(' :*')
        if not clause:
            continue
        clause = re.sub(r'^(?:if|when)\s+documented\s*:\s*|\s+(?:if|when)\s+documented$', '', clause)
        if re.fullmatch(annotation, clause):
            continue
        # A documentation condition controls availability, not the named role.
        if re.fullmatch(r'(?:if|when)\s+documented', clause):
            continue
        negative = re.match(r'^(?:do\s+not\s+'+verbs+r'|exclude|excluding|omit|not|no)\s+', clause)
        if negative:
            target = person(clause[negative.end():])
            if target is None:
                return None
            excluded.add(target)
            continue
        clause = re.sub(r'^(?:please\s+)?'+verbs+r'\s+(?:only\s+)?|^what\s+is\s+|^who\s+is\s+', '', clause)
        clause = re.sub(r'\s+only$', '', clause)
        target = person(clause)
        if target is None:
            # A generic continuation cannot qualify a bare name on its own.
            if re.fullmatch(r'(?:the\s+)?'+name, clause):
                continue
            return None
        requested.add(target)
        if not (target.endswith('clinician') and re.search(r'\bclinician\s+who\b', clause)):
            explicit.add(target)
    # Only a positively established matching care role may refine a generic
    # clinician to the heading's clinical occupation. Separate requests, unknown
    # relations and different functional roles cannot refine each other.
    if len(requested) == 2:
        generic = [x for x in requested if x not in explicit and x.endswith(' clinician')]
        specific = [x for x in requested if is_clinical(x) and x.split()[-1] != 'clinician']
        if (len(generic) == len(specific) == 1
                and ' '.join(specific[0].split()[:-1]) in ('', ' '.join(generic[0].split()[:-1]))):
            requested.remove(generic[0])
    if len(requested) != 1:
        return None
    target = next(iter(requested))
    def excludes_target(value):
        occupation, relation = role_parts(target)
        other, other_relation = role_parts(value)
        if occupation in unspecified_subject_roles or other in unspecified_subject_roles:
            return True  # Their relationship to the requested person is unknown.
        if relation and other_relation and relation != other_relation:
            return False
        # Exclusions apply to both a complete superclass and an overlapping
        # unqualified/subclass request; neither can establish a safe sole target.
        return occupation in ancestry(other) or other in ancestry(occupation)
    if any(excludes_target(value) for value in excluded):
        return None
    if target == 'patient':
        return 'patient'
    if role_parts(target)[0] in unspecified_subject_roles:
        return None
    if is_clinical(target):
        return 'clinician'
    return 'other'


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
        # Keep the contract's specific remediation until that finding is resolved.
        # The printed-label adapter can then report any remaining name ambiguity.
        if row.get('state') == 'unresolved' and row.get('reason'):
            result.append(row)
            continue
        printed_subject = _printed_name_subject(row['field']['label'])
        field_corrected = bool(corrected)
        if definition.get('version') == 4:
            if hasattr(prep, 'candidate_sha256'):
                from .word_contract import fully_reviewed_keys
            else:
                from .semantic_preparation import fully_reviewed_keys
            field_corrected = row['field']['key'] in fully_reviewed_keys(prep)
        if (prep.state != 'approved' and not field_corrected
                and definition.get('value_type') == 'person_name'):
            if printed_subject is None:
                row.update(state='unresolved', reason='The name label does not specify whose name belongs here.')
            elif definition.get('scope', {}).get('subject') not in (None, printed_subject):
                row.update(state='unresolved', reason='The proposed name subject does not match the person requested by the printed question.')
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
                   type_options=[(k,v) for k,v in TYPE_LABELS.items() if definition.get('version') in (2, 3, 4) or k not in {'person_name', 'identifier'}], subject_options=list(SUBJECT_LABELS.items()),
                   timing_options=list(TIMING_LABELS.items()), polarity_options=list(POLARITY_LABELS.items()),
                   mode_options=list(MODE_LABELS.items()), patient_name_options=list(PATIENT_NAME_LABELS.items()),
                   patient_name_summary=PATIENT_NAME_LABELS.get(definition.get('patient_name_requirement'), ''))
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
        if definition['version'] in (2, 3, 4): names.append('answer_mode')
        if definition['version'] in (3, 4): names.append('patient_name_requirement')
        if any(len(post.getlist('field_'+key+'_'+name)) != 1 for name in names):
            raise ValidationError('A definition control is missing or repeated. Reload before reviewing this form.')
    from .semantic_preparation_views import posted_definitions
    proxy = SimpleNamespace(source_version=SimpleNamespace(fields=[r['field'] for r in items]),
                            config={'semantic_definition_version': next(iter(baseline.values()))['version']},
                            component_baseline=baseline)
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
                if value.get('version') == 4:
                    parts = value['component_contract']['components']
                    if (len(parts) != 1 or parts[0]['value_type'] != 'person_name'
                            or value['component_contract']['rendering'] != 'plain'):
                        raise ValidationError('Use Edit required parts to review this name and its component roles.')
                    parts[0]['scope'] = dict(value['scope'])
                    parts[0]['meaning'] = value['meaning']
                decisions.append(f'{label_text(row["field"]["label"])}: {role}')
            else:
                decision = post.get('decision_'+key, '')
                if (decision not in {'accept', 'edit'} or (decision == 'edit' and value == current)
                        or (decision == 'accept' and value != current)):
                    raise ValidationError(f'Resolve the question for {label_text(row["field"]["label"])} before saving.')
                decisions.append(f'{label_text(row["field"]["label"])}: {"confirmed proposed meaning" if decision == "accept" else "edited definition"}')
        if value['scope']['subject'] != current['scope']['subject'] and value['meaning'] == current['meaning']:
            raise ValidationError('When changing whom a field describes, update its meaning to describe that person too.')
        if (value.get('version') == 4 and value != current
                and value['component_contract'] == current['component_contract']):
            raise ValidationError('Use Edit required parts to check the components against this corrected definition before saving.')
    if operation == 'approve' and values != baseline:
        raise ValidationError('Save your edited definitions before approving this template. No version was created.')
    changed = [label_text(r['field']['label']) for r in items if values[r['field']['key']] != baseline[r['field']['key']]]
    reason = 'Reviewed the complete original, field meanings, constraints and destinations. '
    reason += '; '.join(decisions) if decisions else 'Explicit definition edits: '+', '.join(changed)
    return values, list(baseline), reason[:1000]
