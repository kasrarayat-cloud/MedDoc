"""Separate reusable answer definitions; physical layout approvals stay immutable."""
from copy import deepcopy
from uuid import UUID
import hashlib
import json
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from documents import DocumentError, inspect_template
from documents.preparation import TYPED_PROTOCOL, model_inventory
from documents.preparation_service import inspect_preparation
from documents.semantic_preparation_roles import (
    PROTOCOL, DefinitionError, build_inventory, definitions_from_role, digest, fixture_role,
    role_instructions, role_schema, validate_definitions, validate_inventory, validate_role_result,
)
from . import ai_stages, testing_authority
from .generation import configuration
from .models import Template, TemplateVersion, TemplateDefinitionPreparation
from .security import audit, membership, private_path


RUNNING = ('inventory', 'proposer', 'checker')
EDITABLE = ('review', 'guided')
PHYSICAL_ATTRIBUTES = ('fields', 'review_requirements', 'document_backend', 'prepared_path',
                       'prepared_sha256', 'preparation_id')


def source_identity(version):
    return {'version_id': str(version.pk), 'template_id': str(version.template_id),
            'original_sha256': version.template.sha256, 'number': version.number,
            **{name: str(getattr(version, name)) if name == 'preparation_id' and getattr(version, name)
               else getattr(version, name) for name in PHYSICAL_ATTRIBUTES}}


def approval_binding(prep):
    return digest({'protocol': PROTOCOL, 'source': source_identity(prep.source_version),
        'config': prep.config, 'inventory': prep.inventory, 'proposal': prep.proposal,
        'checker': prep.checker, 'corrections': prep.corrections,
        'correction_history': prep.correction_history, 'revision': prep.revision,
        'approved_definitions': prep.approved_definitions,
        'approved_by': str(prep.approved_by_id) if prep.approved_by_id else None,
        'approved_at': prep.approved_at.isoformat() if prep.approved_at else None})


def unavailable_reason(version):
    if (version.document_backend or {}).get('backend') == 'wm-iov-foss-v2':
        return ('Reusable semantic definitions are not yet supported for this advanced Word mapping. '
                'Its qualified Word adapter requires the existing labelled-evidence review. '
                'Continue using that approved mapping; the original form and earlier documents are preserved.')
    return ''


def _validate_source(prep, *, current=False):
    source = prep.source_version
    if source.template.format != 'docx':
        raise ValidationError('Reusable semantic definitions currently require a blank Word form.')
    reason = unavailable_reason(source)
    if reason:
        raise ValidationError(reason)
    if current and source.template.versions.order_by('-number').values_list('pk', flat=True).first() != source.pk:
        raise ValidationError('The mapping has a newer version. Review definitions for that current version.')
    from .template_source import source_for_version
    # This is the PRIOR immutable source, never the semantic version being validated.
    source_for_version(source)
    if prep.inventory:
        validate_inventory(source.fields, prep.inventory)
        if (prep.inventory['source_version_id'] != str(source.pk)
                or prep.inventory['source_sha256'] != source.template.sha256):
            raise ValidationError('The definitions no longer match their retained original mapping.')


def _validate_roles(prep):
    fields = prep.source_version.fields
    for role, response in (('proposer', prep.proposal), ('checker', prep.checker)):
        validate_role_result(fields, prep.inventory, response, role)
        _require_definition_version(response, definition_version(prep.config))


def corrected_definitions(prep):
    values = deepcopy(definitions_from_role(prep.proposal)) if prep.proposal else {}
    values.update(deepcopy(prep.corrections))
    return values


def roles_agree(prep):
    return (all(row['state'] == 'proposed' for row in prep.proposal['fields'])
            and all(row['state'] == 'pass' for row in prep.checker['fields'])
            and definitions_from_role(prep.proposal) == definitions_from_role(prep.checker))


def validated_semantic_definitions(version):
    """Shared enqueue/review/export gate for a separately approved semantic version."""
    try:
        return _validated_semantic_definitions(version)
    except OSError as exc:
        raise ValidationError('The retained approved Word source is unavailable. Contact support to restore that source; no generation was started.') from exc
    except DefinitionError as exc:
        raise ValidationError(str(exc)) from exc


def _validated_semantic_definitions(version):
    if not getattr(version, 'semantic_definitions', {}) and not getattr(version, 'semantic_preparation_id', None):
        from .word_contract import definitions
        return definitions(version)
    if not version.semantic_definitions or not version.semantic_preparation_id:
        raise ValidationError('Semantic answer definitions require their separate clinician approval.')
    prep = version.semantic_preparation
    source = prep.source_version
    if (prep.state != 'approved' or not prep.approved_by_id or not prep.approved_at
            or source.pk == version.pk or source.number >= version.number
            or source.template_id != version.template_id
            or prep.approval_sha256 != approval_binding(prep)
            or prep.approved_definitions != version.semantic_definitions
            or any(getattr(version, name) != getattr(source, name) for name in PHYSICAL_ATTRIBUTES)):
        raise ValidationError('This semantic definition version is unapproved, stale or has altered destinations.')
    try:
        _validate_source(prep)
        _validate_roles(prep)
        values = validate_definitions(source.fields, corrected_definitions(prep))
        _require_definition_version({'fields':[{'definition':d} for d in values.values()]}, definition_version(prep.config))
        if values != version.semantic_definitions:
            raise ValidationError('The semantic version differs from the reviewed field definitions.')
    except DefinitionError as exc:
        raise ValidationError(str(exc)) from exc
    return version.semantic_definitions


@transaction.atomic
def create_preparation(source_version, actor, *, retry_of=None):
    if not settings.WORD_PREPARATION_ENABLED:
        raise ValidationError('AI form preparation is not enabled in this environment.')
    template = Template.objects.select_for_update().get(pk=source_version.template_id)
    source = TemplateVersion.objects.select_related('template').get(pk=source_version.pk, template=template)
    membership(actor, template.department, roles=['owner', 'clinician'])
    reason = unavailable_reason(source)
    if reason:
        raise ValidationError(reason)
    # Every browser replay retains the original request, including blocked attempts.
    attempts = TemplateDefinitionPreparation.objects.filter(source_version=source, requested_by=actor)
    previous = attempts.order_by('-created_at','-pk').first()
    if retry_of is None:
        if previous:return previous
    else:
        try:retry_of=str(UUID(str(retry_of)))
        except (ValueError,TypeError,AttributeError):raise ValidationError('Select the retained blocked attempt before requesting a new preparation.')
        reused=attempts.filter(config__definition_retry_of=retry_of).order_by('created_at','pk').first()
        if reused:return reused
        if previous is None or str(previous.pk)!=retry_of or previous.state!='blocked':
            raise ValidationError('Only the latest retained blocked preparation can receive an explicit new attempt.')
        if (previous.error_code=='provider_unknown' or previous.ai_stage_receipts.exclude(state__in=['succeeded','failed']).exists()
                or previous.ai_stage_receipts.filter(actual_cost__isnull=True).exists()):
            raise ValidationError('Reconcile the retained uncertain provider outcome before requesting another preparation. Nothing was resent.')
    transient = TemplateDefinitionPreparation(source_version=source)
    _validate_source(transient, current=True)
    if not 0 < len(source.fields) <= 100:
        raise ValidationError('This bounded definition review supports one to 100 approved fields.')
    config = testing_authority.active_config(configuration(), 'preparation')
    if testing_authority.identity(config):
        config = testing_authority.bind_actor_config(config, actor, template.department_id)
    elif config.get('mode') == 'live':
        raise ValidationError('Live definition preparation needs an active authorized preparation procedure.')
    config = {**config, 'semantic_definition_protocol': PROTOCOL, 'semantic_definition_version': 2}
    if retry_of is not None:config['definition_retry_of']=retry_of
    config = ai_stages.definition_pipeline_config(config)
    prep = TemplateDefinitionPreparation.objects.create(source_version=source, requested_by=actor, config=config)
    audit(actor, 'template.definitions_requested', prep.pk, department=template.department,
          source_version=str(source.pk), source_sha256=template.sha256, retry_of=retry_of)
    return prep


def _inventory(prep):
    source = prep.source_version
    from documents.sdk_service import WM_IOV_SHA256
    original = private_path(source.template.original_path)
    known = inspect_template(original) if source.template.sha256 == WM_IOV_SHA256 else None
    inventory = inspect_preparation(original, known, protocol=TYPED_PROTOCOL)
    if inventory['source_sha256'] != source.template.sha256:
        raise ValidationError('Original integrity check failed.')
    return build_inventory(source.fields, source_version_id=str(source.pk),
        source_sha256=source.template.sha256, original=model_inventory(inventory))


def definition_version(config):
    value = config.get('semantic_definition_version', 1)
    if type(value) is not int or value not in (1, 2):
        raise ValidationError('Unsupported explicit answer-definition version.')
    return value


def _require_definition_version(response, expected):
    if any(row['definition']['version'] != expected for row in response['fields']):
        raise DefinitionError('The returned answer definitions do not match the requested schema version. Review a new preparation; no older contract was adopted.')
    return response


def _call_role(prep, role):
    version = definition_version(prep.config)
    payload = {'protocol': PROTOCOL, 'original': prep.inventory, 'role': role}
    if role == 'checker':
        payload['proposal'] = prep.proposal
    options = {}
    if prep.config.get('mode') != 'live':
        options['fixture_output'] = fixture_role(prep.source_version.fields, prep.inventory, role, prep.proposal, version)
    response = ai_stages.execute_stage(definition_preparation=prep, stage='definition_'+role,
        payload=payload, schema=role_schema(role, version), instructions=role_instructions(role, version),
        config=prep.config, **options)
    return _require_definition_version(
        validate_role_result(prep.source_version.fields, prep.inventory, response, role), version)


def run_one():
    if not settings.WORD_PREPARATION_ENABLED:
        return False
    with transaction.atomic():
        prep = TemplateDefinitionPreparation.objects.select_for_update(skip_locked=True).filter(state='queued').order_by('created_at').first()
        if not prep or TemplateDefinitionPreparation.objects.filter(state__in=RUNNING).exists():
            return False
        prep.state = 'inventory'; prep.started_at = timezone.now()
        prep.save(update_fields=['state', 'started_at'])
    try:
        membership(prep.requested_by, prep.source_version.template.department, roles=['owner', 'clinician'])
        _validate_source(prep)
        prep.inventory = _inventory(prep)
        prep.state = 'proposer'; prep.save(update_fields=['inventory', 'state'])
        prep.proposal = _call_role(prep, 'proposer')
        prep.state = 'checker'; prep.save(update_fields=['proposal', 'state'])
        prep.checker = _call_role(prep, 'checker')
        prep.state = 'review' if roles_agree(prep) else 'guided'
    except Exception as exc:
        prep.state = 'blocked'
        prep.error_code = ('membership_lost' if isinstance(exc, PermissionDenied) else
            'provider_unknown' if isinstance(exc, ai_stages.StageUnknown) else
            'not_sent' if isinstance(exc, ai_stages.StageNotSent) else
            'invalid_definition' if isinstance(exc, (DefinitionError, ai_stages.StageFailure)) else
            'source_unavailable' if isinstance(exc, (DocumentError, ValidationError)) else 'processing_failure')
    prep.finished_at = timezone.now(); prep.save()
    audit(prep.requested_by, 'template.definitions_finished', prep.pk,
          department=prep.source_version.template.department, state=prep.state, error_code=prep.error_code)
    return True


def _reviewed(prep, reviewed_fields):
    keys = [field['key'] for field in prep.source_version.fields]
    if len(reviewed_fields) != len(keys) or set(reviewed_fields) != set(keys):
        raise ValidationError('Explicitly review every field meaning, scope, type, constraints and fixed destination.')


@transaction.atomic
def correct(prep_id, actor, revision, definitions, reviewed_fields, reason):
    prep = TemplateDefinitionPreparation.objects.select_for_update().select_related('source_version__template').get(pk=prep_id)
    membership(actor, prep.source_version.template.department, roles=['owner', 'clinician'])
    if prep.state not in EDITABLE or prep.revision != revision:
        raise ValidationError('Review the current definition revision before saving corrections.')
    _validate_source(prep, current=True); _validate_roles(prep); _reviewed(prep, reviewed_fields)
    if not isinstance(reason, str) or not 12 <= len(reason.strip()) <= 1000:
        raise ValidationError('Give a specific review reason between 12 and 1000 characters.')
    try:
        validate_definitions(prep.source_version.fields, definitions)
        _require_definition_version({'fields':[{'definition':d} for d in definitions.values()]}, definition_version(prep.config))
    except DefinitionError as exc:
        raise ValidationError(str(exc)) from exc
    prep.corrections = deepcopy(definitions)
    prep.correction_history.append({'revision': revision, 'actor': str(actor.pk),
        'at': timezone.now().isoformat(), 'reason': reason.strip(), 'definitions': deepcopy(definitions),
        'reviewed_fields': list(reviewed_fields)})
    prep.revision += 1; prep.state = 'review'
    prep.save(update_fields=['corrections', 'correction_history', 'revision', 'state'])
    audit(actor, 'template.definitions_corrected', prep.pk, department=prep.source_version.template.department,
          revision=prep.revision, definition_sha256=digest(definitions))
    return prep


def _receipt_integrity(prep):
    rows = list(prep.ai_stage_receipts.order_by('stage'))
    if (len(rows) != 2 or {row.stage for row in rows} != {'definition_proposer', 'definition_checker'}
            or any(row.state != 'succeeded' or row.attempt != 1 or row.config != prep.config
                   or row.actual_cost is None for row in rows)):
        raise ValidationError('Both independent definition stages must have retained, reconciled results.')
    for row in rows:
        for relative, expected in [(row.request_path, row.request_sha256), (row.result_path, row.result_sha256)]:
            if hashlib.sha256(private_path(relative).read_bytes()).hexdigest() != expected:
                raise ValidationError('The retained definition-stage evidence failed its integrity check.')


@transaction.atomic
def approve(prep_id, actor, revision, inventory_sha256, reviewed_fields, original_reviewed):
    prep = TemplateDefinitionPreparation.objects.select_for_update().select_related('source_version__template').get(pk=prep_id)
    source = prep.source_version
    membership(actor, source.template.department, roles=['owner', 'clinician'])
    # Share the lock order used by mapping creation: no stale definitions may win a new version.
    Template.objects.select_for_update().get(pk=source.template_id)
    if (prep.state != 'review' or prep.revision != revision or not original_reviewed
            or inventory_sha256 != prep.inventory.get('inventory_sha256')):
        raise ValidationError('Compare the complete original and approve the current reviewed definitions.')
    _validate_source(prep, current=True); _validate_roles(prep); _reviewed(prep, reviewed_fields)
    if not prep.corrections and not roles_agree(prep):
        raise ValidationError('Resolve every proposer/checker disagreement with explicit clinician corrections.')
    _receipt_integrity(prep)
    try:
        values = validate_definitions(source.fields, corrected_definitions(prep))
        _require_definition_version({'fields':[{'definition':d} for d in values.values()]}, definition_version(prep.config))
    except DefinitionError as exc:
        raise ValidationError(str(exc)) from exc
    prep.approved_definitions = deepcopy(values)
    prep.state = 'approved'; prep.approved_by = actor; prep.approved_at = timezone.now()
    prep.approval_sha256 = approval_binding(prep); prep.save()
    latest = source.template.versions.order_by('-number').first()
    version = TemplateVersion.objects.create(template=source.template, number=latest.number+1,
        **{name: deepcopy(getattr(source, name)) for name in PHYSICAL_ATTRIBUTES},
        semantic_definitions=deepcopy(values), semantic_preparation=prep, created_by=actor)
    audit(actor, 'template.definitions_approved', version.pk, department=source.template.department,
          source_version=str(source.pk), approval_sha256=prep.approval_sha256,
          definition_sha256=digest(values), revision=prep.revision)
    return version
