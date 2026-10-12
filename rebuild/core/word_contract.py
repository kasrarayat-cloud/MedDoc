"""Answer capability approved with a new blank Word preparation.

Physical field types describe the document. Semantic types describe its answers.
Neither a mapping number nor agent agreement grants this capability.
"""
from copy import deepcopy
from django.core.exceptions import ValidationError
from documents.preparation import digest, model_inventory, validate_role
from documents import semantic_preparation_roles as roles

LEGACY_PROFILE = 'reviewed-word-answer-contract-v1'
PROFILE = 'reviewed-word-answer-contract-v2'
CONFIG_KEY = 'word_answer_contract'
INFO_KEY = 'answer_contract'
MISSING = ('This Word form needs approved answer definitions before generation. '
           'Open the form’s mapping and prepare/review its reusable answer definitions. '
           'Your notes and earlier documents are preserved; no AI request was sent.')


def requested(config):
    if CONFIG_KEY not in config:
        return False
    if config[CONFIG_KEY] not in (LEGACY_PROFILE, PROFILE):
        raise ValidationError('Unsupported explicit Word answer contract. Nothing was downgraded.')
    return True


def timing_reference(config):
    requested(config)
    return roles.TEMPORAL_REFERENCE_CONTRACT if config.get(CONFIG_KEY) == PROFILE else None


def eligible(inventory):
    fields = inventory['fields']
    anchors = inventory['anchors']
    return (not inventory['document_backend'] and fields and len(fields) == len(anchors)
            and all(a['kind'] == 'existing' for a in anchors)
            and {a.get('field_key') for a in anchors} == {f['key'] for f in fields})


def inventory_for(inventory):
    if not eligible(inventory):
        raise ValidationError('Review answer meanings after approving the new answer locations.')
    return roles.build_inventory(inventory['fields'],
        source_version_id='blank-preparation:'+inventory['inventory_sha256'],
        source_sha256=inventory['source_sha256'], original=model_inventory(inventory))


def active(inventory, config):
    return requested(config) and eligible(inventory)


def validate_result(inventory, response, role, config):
    if active(inventory, config):
        if not isinstance(response, dict) or set(response) != {'inventory_sha256', 'anchors', 'stories', 'answer_definitions'}:
            raise ValidationError('Preparation omitted its required answer definitions. No legacy fallback is permitted.')
        validate_role(inventory, {k: v for k, v in response.items() if k != 'answer_definitions'}, role)
        roles.validate_role_result(inventory['fields'], inventory_for(inventory), response['answer_definitions'], role)
        if any(row['definition']['version'] != 2 for row in response['answer_definitions']['fields']):
            raise ValidationError('Fresh Word preparation requires the complete answer contract.')
    else:
        validate_role(inventory, response, role)
    return response


def proposed(prep):
    if not active(prep.inventory, prep.config):
        return {}
    validate_result(prep.inventory, prep.proposal, 'proposer', prep.config)
    validate_result(prep.inventory, prep.checker, 'checker', prep.config)
    values = deepcopy(roles.definitions_from_role(prep.checker['answer_definitions']))
    corrections = prep.corrections.get('answer_definitions', {})
    if corrections:
        roles.validate_definitions(prep.inventory['fields'], corrections)
        if any(d['version'] != 2 for d in corrections.values()):
            raise ValidationError('A reviewed correction cannot discard the complete answer contract.')
        values = deepcopy(corrections)
    return values


def review_rows(prep):
    # Queued and failed-before-inspection records have no inventory yet.
    # Completed responses still pass the full contract validator below.
    if not prep.proposal or not prep.checker:
        return []
    values = proposed(prep)
    if not values:
        return []
    proposals = roles.definitions_from_role(prep.proposal['answer_definitions']) if values else {}
    checks = {r['field_key']: r for r in prep.checker['answer_definitions']['fields']} if values else {}
    issues = approval_issues(prep)
    return [{'key': f['key'], 'label': f['label'], 'field': f, 'definition': values[f['key']],
             'disagreement': values[f['key']] != proposals[f['key']],
             'state': 'unresolved' if f['key'] in issues else 'pass',
             'reason': ' '.join(filter(None, (checks[f['key']]['reason'], issues.get(f['key']))))}
            for f in prep.inventory['fields'] if f['key'] in values]


def identity_scope_issues(prep):
    values = proposed(prep)
    return roles.identity_scope_issues(prep.inventory['fields'], values) if values else {}


def approval_issues(prep):
    """Pending semantic decisions, separate from immutable source/layout issues.

    The supported clinician correction saves complete reviewed definitions and
    its reason separately. A layout correction or approval checkbox alone does
    not adjudicate an unresolved semantic result. Historical readers do not use
    this new-use gate.
    """
    values = proposed(prep)
    if not values:
        return {}
    issues = roles.identity_scope_issues(prep.inventory['fields'], values)
    if not prep.corrections.get('answer_definitions'):
        labels = {f['key']: f['label'] for f in prep.inventory['fields']}
        for role, response in (('Proposer', prep.proposal), ('Checker', prep.checker)):
            for row in response['answer_definitions']['fields']:
                if row['state'] == 'unresolved':
                    key = row['field_key']
                    detail = (f"Resolve the answer definition for {labels[key]} using Save doctor corrections "
                              f"before approval. {role}: {row['reason']}").strip()
                    issues[key] = ' '.join(filter(None, (issues.get(key), detail)))
    return issues


def require_resolved(prep, *, generation=False):
    issues = approval_issues(prep)
    if issues:
        if generation:
            raise ValidationError('This approved form still has unresolved answer definitions. '
                'Open its mapping and prepare/review a new answer-definition version before generation. '
                'Earlier documents remain available; no AI request was sent.')
        raise ValidationError(list(issues.values()))


def require_identity_scopes(fields, values):
    try:
        return roles.require_identity_scopes(fields, values)
    except roles.DefinitionError as exc:
        raise ValidationError(str(exc)) from exc


def seal(prep, reviewed, actor):
    values = proposed(prep)
    if not values:
        return
    if len(reviewed) != len(values) or set(reviewed) != set(values):
        raise ValidationError('Review and confirm the meaning, type, unit, choices, scope and destination of every answer.')
    require_resolved(prep)
    # New destinations must use the existing separate definition review, never
    # an anchor/field zip or label-based reassignment.
    fields = prep.candidate_info['fields']
    source = {f['key']: f for f in prep.inventory['fields']}
    if {f['key'] for f in fields} != set(source) or any(
            f['label'] != source[f['key']]['label'] or f['locator'] != source[f['key']]['locator'] for f in fields):
        raise ValidationError('Answer definitions changed their original questions or destinations.')
    require_identity_scopes(fields, values)
    prep.candidate_info[INFO_KEY] = {'profile': prep.config[CONFIG_KEY], 'fields_sha256': digest(fields),
        'source_inventory_sha256': prep.inventory['inventory_sha256'], 'definitions': values,
        'reviewed_fields': sorted(reviewed), 'reviewed_by': str(actor.pk)}


def has_inline(version):
    prep = getattr(version, 'preparation', None) if getattr(version, 'preparation_id', None) else None
    return bool(prep and (CONFIG_KEY in getattr(prep, 'config', {}) or INFO_KEY in prep.candidate_info))


def definitions(version):
    if not has_inline(version):
        return {}
    prep = version.preparation
    if not requested(prep.config):
        raise ValidationError('Answer definitions have no matching preparation profile.')
    if not eligible(prep.inventory):
        if INFO_KEY in prep.candidate_info:
            raise ValidationError('Answer definitions have no exact original anchor binding.')
        return {}  # Explicit separate definition approval is required.
    from .template_source import physical_source_for_version
    physical_source_for_version(version)
    value = prep.candidate_info.get(INFO_KEY)
    expected = proposed(prep)
    if (not isinstance(value, dict) or set(value) != {'profile','fields_sha256','source_inventory_sha256',
            'definitions','reviewed_fields','reviewed_by'} or value['profile'] != prep.config[CONFIG_KEY]
            or value['fields_sha256'] != digest(version.fields)
            or digest(version.fields) != digest(prep.candidate_info['fields'])
            or value['source_inventory_sha256'] != prep.inventory['inventory_sha256']
            or value['definitions'] != expected or value['reviewed_fields'] != sorted(expected)
            or value['reviewed_by'] != str(prep.approved_by_id)):
        raise ValidationError('The approved Word answer definitions are incomplete or changed. Review a new version.')
    try:
        return roles.validate_definitions(version.fields, value['definitions'])
    except roles.DefinitionError as exc:
        raise ValidationError(str(exc)) from exc


def require_generation(version):
    from .semantic_preparation import validated_semantic_definitions
    try:
        values = validated_semantic_definitions(version)
    except OSError as exc:
        raise ValidationError('This form’s approved source is unavailable. Ask support to restore it before generation; no AI request was sent.') from exc
    if (not values and version.template.format == 'docx'
            and (version.document_backend or {}).get('backend') != 'wm-iov-foss-v2'):
        raise ValidationError(MISSING)
    if values:
        require_identity_scopes(version.fields, values)
        if (not getattr(version, 'semantic_definitions', {})
                and not getattr(version, 'semantic_preparation_id', None) and has_inline(version)):
            require_resolved(version.preparation, generation=True)
    return values
