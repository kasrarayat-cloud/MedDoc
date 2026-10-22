"""Closed owner grants for one already evidenced clinical attempt.

A grant changes neither the general recovery protocol nor a retained request.
Its data identifies immutable evidence, never clinical wording or patient names.
Normal encounter locking, signed offers and unique request keys consume it once.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from uuid import UUID

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError

from .models import Job, AuditEvent, TemplatePreparation, TemplateDefinitionPreparation, CodingRun

CONTRACT = 'scoped-clinical-call-grant-successor-v1'
STAGES = (('extractor', 1), ('assigner', 1), ('checker', 1))
FAMILY_CALLS = 9
PRIOR_CALLS = 6
CEILING = Decimal('8.15')
# Reconciled grant data is canonical JSON so every use receives a fresh value.
# The grant is a separate owner authority; historical five/eight-call edges stay
# byte-for-byte under their original validators.
GRANTS_JSON = '{"quillmd-existing-case-one-attempt-20261022-v1":{"actor":"5f4d1a3d-eeb6-4207-b1df-4597dc696e82","authorization_sha256":"aa57fa7df8b1560d2dee6a260c94a9d7b7e30790aa9522f980c9b8485399b686","clinical_exposure":"3.269055000000","definitions_sha256":"69715fcd3583c0870409c245812e712392edab010972242c19d0c7803bb593bc","department":"46a5abdd-36f1-41f0-968f-8c09c39d9daa","encounter":"ddd212c3-60c5-4fd1-b329-8994fc50ff2c","encounter_binding_sha256":"b09c8ac411b5d74d32fcc32bdd777002316a3cf2a0d8de8201b13a4053be0aaa","id":"quillmd-existing-case-one-attempt-20261022-v1","jobs":["00112b06-78b6-4c74-8a42-08b5c2ff34f2","53764047-b19f-40be-b447-e639242cf3cb","cffab250-d883-4d17-adc3-24141fd8d5a8","67c496c9-db58-4cd3-b314-7ea90f710eaa","5e9dfd29-7bd4-4fa8-acde-57766adb8724","76ce2a52-ad47-4b8f-b29d-37d96e0650ed"],"preparation_exposure":"1.207400000000","preparation_sha256":"4baa97619e2027c042ab601e6cc25c4b743d4f9f94e8c40f098ad1a0fddac34a","proofs_sha256":"ddb100b8d6fe941bf89b638cc5e853f0a6b773ed60dc97171098c1962002a9dd","revision":0,"source_sha256":"22aec43a9af4828484f95115665c4747d664033cf89c1131d90863a015cc2fd7","template":"460d81a5-1d93-4206-b5ba-fb6c134f40e9","version":"676e4d55-3f08-4c4a-ab2f-5ec2261eb8ff"}}'


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def selected(config):
    value = config.get('semantic_recovery')
    return type(value) is dict and value.get('contract') == CONTRACT


def record(identifier):
    value = json.loads(GRANTS_JSON).get(identifier)
    keys = {'id', 'authorization_sha256', 'encounter', 'actor', 'department', 'template',
        'version', 'revision', 'source_sha256', 'definitions_sha256', 'encounter_binding_sha256',
        'jobs', 'proofs_sha256', 'preparation_sha256', 'clinical_exposure', 'preparation_exposure'}
    if (type(value) is not dict or set(value) != keys or value['id'] != identifier
        or type(value['revision']) is not int or value['revision'] < 0
        or type(value['jobs']) is not list or len(value['jobs']) != PRIOR_CALLS
        or len(set(value['jobs'])) != PRIOR_CALLS
        or any(type(value[k]) is not str or not re.fullmatch('[a-f0-9]{64}', value[k])
            for k in ('authorization_sha256', 'source_sha256', 'definitions_sha256',
                'encounter_binding_sha256', 'proofs_sha256', 'preparation_sha256'))):
        raise ValueError('Unknown or incomplete clinical-call authority')
    for key in ('clinical_exposure', 'preparation_exposure'):
        if type(value[key]) is not str: raise ValueError('Noncanonical campaign exposure')
        _money(Decimal(value[key]))
    for identifier in [value[key] for key in ('encounter', 'actor', 'department', 'template', 'version')] + value['jobs']:
        if type(identifier) is not str or str(UUID(identifier)) != identifier:
            raise ValueError('Noncanonical grant identity')
    return value


def _money(value):
    if type(value) is not Decimal or not value.is_finite() or value < 0:
        raise ValueError('Unproved campaign exposure')
    return value


def _descriptor(obj, fields):
    result = {}
    for key in fields:
        value = getattr(obj, key)
        if key == 'config': value = _digest(value)
        elif key.endswith('_id') or key == 'pk': value = str(value) if value is not None else None
        elif key in ('quote_maximum', 'computed_cost'): value = str(_money(value)) if value is not None else None
        result[key] = value
    return result


def preparation_snapshot(preparation):
    """Stable identities, original approval, rates and exact receipt costs."""
    rows = list(preparation.receipts.order_by('role', 'pk')[:3])
    if (preparation.state != 'approved' or len(rows) != 2
        or {row.role for row in rows} != {'proposer', 'checker'}
        or any(row.state != 'succeeded' or row.simulated is not False
            or row.computed_cost is None for row in rows)):
        raise ValueError('Associated preparation is not completely reconciled')
    fields = ('pk', 'preparation_id', 'role', 'state', 'provider', 'requested_model',
        'returned_model', 'request_sha256', 'response_path', 'response_sha256',
        'provider_request_id', 'provider_resource_id', 'simulated', 'quote_maximum',
        'computed_cost', 'usage', 'rates', 'error_code', 'failure', 'failure_path', 'failure_sha256')
    body = {'preparation': _descriptor(preparation, ('pk', 'template_id', 'requested_by_id',
        'state', 'revision', 'config', 'approved_by_id', 'approval_sha256', 'candidate_path', 'candidate_sha256')),
        'receipts': [_descriptor(row, fields) for row in rows]}
    exposure = sum((max(_money(row.quote_maximum), _money(row.computed_cost)) for row in rows), Decimal('0'))
    return body, exposure


def _baseline(job, grant):
    from . import generation_recovery as recovery
    nodes, _, _ = recovery._lineage(job)
    if ([str(row.pk) for row in nodes] != grant['jobs'] or job.kind != 'generation'
        or str(job.encounter_id) != grant['encounter'] or str(job.user_id) != grant['actor']
        or type(job.revision) is not int or job.revision != grant['revision']
        or job.config.get('semantic_source_sha256') != grant['source_sha256']
        or job.config.get('semantic_definitions_sha256') != grant['definitions_sha256']
        or job.config.get('semantic_template_version') != grant['version']
        or _digest(job.config.get('semantic_encounter_binding')) != grant['encounter_binding_sha256']):
        raise ValueError('Grant family or original source changed')
    proofs = [recovery._local_failure(row) for row in nodes]
    if any(value is None for value in proofs) or _digest(proofs) != grant['proofs_sha256']:
        raise ValueError('Grant requires all six original authenticated failures')
    exposure = sum((_money(Decimal(value['prior_quote'])) for value in proofs), Decimal('0'))
    if exposure != Decimal(grant['clinical_exposure']): raise ValueError('Clinical exposure changed')
    preparations = list(TemplatePreparation.objects.filter(template_id=grant['template'])[:2])
    if len(preparations) != 1: raise ValueError('Associated preparation changed')
    snapshot, prep_exposure = preparation_snapshot(preparations[0])
    if (_digest(snapshot) != grant['preparation_sha256']
        or prep_exposure != Decimal(grant['preparation_exposure'])):
        raise ValueError('Associated preparation evidence changed')
    proof = {**proofs[-1], 'prior_calls': len(nodes), 'prior_quote': str(exposure)}
    if proof.get('truncated_transport') != recovery.clinical_transport.JSON_TRANSPORT:
        raise ValueError('Grant requires the evidenced truncated extractor')
    return proof, exposure + prep_exposure


def _current(grant, encounter, user):
    from . import generation_recovery as recovery
    if (str(encounter.pk) != grant['encounter'] or str(user.pk) != grant['actor']
        or str(encounter.department_id) != grant['department']
        or str(encounter.template_version_id) != grant['version']
        or str(encounter.template_version.template_id) != grant['template']
        or type(encounter.revision) is not int or encounter.revision != grant['revision']
        or encounter.status != 'draft' or type(encounter.answers) is not dict or encounter.answers):
        raise ValueError('Grant case changed')
    if (TemplateDefinitionPreparation.objects.filter(source_version_id=grant['version']).exists()
        or CodingRun.objects.filter(encounter_id=grant['encounter']).exists()):
        # The recorded campaign has neither additional definition preparation
        # nor coding. Unknown/new work cannot be priced as zero or ignored.
        raise ValueError('Campaign contains unreviewed associated exposure')


def _universe(grant, child=None):
    rows = list(Job.objects.filter(encounter_id=grant['encounter'])[:FAMILY_CALLS + 1])
    expected = set(grant['jobs']) | ({str(child.pk)} if child is not None else set())
    if len(rows) != len(expected) or {str(row.pk) for row in rows} != expected:
        raise ValueError('Grant case has unknown or additional jobs')


def _value(grant, proof, config, exposure, release):
    from . import generation_recovery as recovery
    return {'contract': CONTRACT, **proof, 'grant_id': grant['id'],
        'authorization_sha256': grant['authorization_sha256'], 'grant_sha256': _digest(grant),
        'ordered_proofs_sha256': grant['proofs_sha256'], 'campaign_prior_exposure': str(exposure),
        'family_max_calls': FAMILY_CALLS, 'per_batch_max_calls': recovery.PER_BATCH_MAX_CALLS,
        'family_cost_ceiling': str(CEILING), 'stage_sequence': [list(row) for row in STAGES],
        'encounter': grant['encounter'], 'actor': grant['actor'], 'revision': grant['revision'],
        'new_transport': recovery.clinical_transport.DIRECT_TRANSPORT,
        'accepted_release': release, 'new_configuration_sha256': recovery._digest({
            key: config[key] for key in recovery.CONFIG_KEYS if key in config})}


def proposal(job, encounter, user, config):
    from . import generation_recovery as recovery, testing_authority, anthropic_request_policy as policy
    try:
        candidates = [value for value in json.loads(GRANTS_JSON).values()
            if value['jobs'][-1] == str(job.pk)]
        if len(candidates) != 1: return None
        grant = record(candidates[0]['id'])
        proof, exposure = _baseline(job, grant)
        _current(grant, encounter, user)
        if not recovery._source_matches(job, encounter): return None
        children = recovery._children(job)
        if children and (len(children) != 1 or not recovery.linked(job, children[0])): return None
        _universe(grant, children[0] if children else None)
        authorized = testing_authority.active_config(config, 'generation')
        authorized = testing_authority.bind_actor_config(authorized, user, encounter.department_id)
        testing_authority.validate_config(authorized, 'generation')
        testing_authority.admit_encounter(user, encounter)
        if (not recovery._same(recovery._v2_bounds(authorized), recovery._v2_bounds(job.config))
            or not recovery._same(authorized.get(testing_authority.ACTOR_ENROLLMENT_KEY),
                job.config.get(testing_authority.ACTOR_ENROLLMENT_KEY))
            or exposure >= CEILING or proof['prior_calls'] + len(STAGES) != FAMILY_CALLS
            or job.config.get(policy.CONFIG_KEY) != policy.PROFILE
            or config.get(policy.CONFIG_KEY) != policy.PROFILE
            or config.get(recovery.TRANSPORT_KEY) != recovery.clinical_transport.DIRECT_TRANSPORT
            or any(key not in job.config or not recovery._same(value, job.config[key])
                for key, value in config.items() if key not in recovery.CHANGED_KEYS)):
            return None
        prospective = {key: config[key] for key in recovery.CONFIG_KEYS if key in config and key != recovery.TRANSPORT_KEY}
        original = {key: job.config[key] for key in recovery.CONFIG_KEYS if key in job.config and key != recovery.TRANSPORT_KEY}
        release = settings.RELEASE_SHA
        if (not recovery._same(prospective, original) or type(release) is not str
            or not re.fullmatch('[a-f0-9]{40}', release) or release == job.config['queued_release_sha']): return None
        return _value(grant, proof, config, exposure, release)
    except (Job.DoesNotExist, AttributeError, KeyError, TypeError, ValueError, OSError,
            InvalidOperation, PermissionDenied, ValidationError):
        return None


def edge(parent, child, proof):
    """Historical authentication uses captured authority, never current activation."""
    from . import generation_recovery as recovery
    try:
        value = child.config[recovery.RECOVERY_KEY]
        grant = record(value['grant_id'])
        original, exposure = _baseline(parent, grant)
        release = child.config.get('queued_release_sha')
        if (not recovery._same(proof, original)
            or not recovery._same(value, _value(grant, original, child.config, exposure, release))
            or child.kind != 'generation' or child.pk == parent.pk
            or child.user_id != parent.user_id or child.encounter_id != parent.encounter_id
            or child.revision != parent.revision or type(child.revision) is not int
            or child.config.get(recovery.TRANSPORT_KEY) != recovery.clinical_transport.DIRECT_TRANSPORT
            or type(release) is not str or not re.fullmatch('[a-f0-9]{40}', release)
            or release == parent.config['queued_release_sha']
            or child.request_key not in {recovery.request_key(parent),
                recovery.request_key(parent) + ':failed:' + child.pk.hex,
                recovery.request_key(parent) + ':cancelled:' + child.pk.hex}
            or not recovery._same({key: item for key, item in child.config.items() if key not in recovery.CHANGED_KEYS},
                {key: item for key, item in parent.config.items() if key not in recovery.CHANGED_KEYS})
            or parent.finished_at is None or parent.finished_at > child.created_at): return False
        children = recovery._children(parent)
        if len(children) != 1 or children[0].pk != child.pk: return False
        events = list(AuditEvent.objects.filter(action='generation.recovery_queued', target=str(child.pk),
            actor_id=child.user_id, department_id=child.encounter.department_id)[:2])
        return (len(events) == 1 and events[0].created_at >= child.created_at
            and recovery._same(events[0].details, {'recovery': value}))
    except (Job.DoesNotExist, AttributeError, KeyError, TypeError, ValueError, OSError,
            InvalidOperation, ValidationError):
        return False


def stage_exposure(config, previous, cap, stage, attempt):
    """Validate the complete prefix, rather than just a count of receipts."""
    from . import generation_recovery as recovery
    rows = sorted(previous, key=lambda row: (row.created_at, row.pk))
    if (len(rows) >= len(STAGES) or type(attempt) is not int
        or (stage, attempt) != STAGES[len(rows)]
        or [(row.stage, row.attempt) for row in rows] != list(STAGES[:len(rows)])
        or any(type(row.attempt) is not int or row.state != 'succeeded'
            or row.actual_cost is None or row.simulated is not False
            or not recovery._same(row.config, config) for row in rows)):
        raise ValueError('Only the single ordered first attempt is authorized')
    return sum((max(_money(row.quote_maximum), _money(row.actual_cost)) for row in rows), Decimal('0')) + _money(cap)


def enforce(job, previous, cap, stage, attempt):
    """Parent lock + shared provider lock protect the one ordered attempt."""
    from . import generation_recovery as recovery
    value = job.config[recovery.RECOVERY_KEY]
    grant = record(value['grant_id'])
    nodes, _, _ = recovery._lineage(job, lock=True)
    if len(nodes) != PRIOR_CALLS + 1:
        raise ValueError('Unauthenticated scoped attempt')
    _current(grant, job.encounter, job.user)
    _universe(grant, job)
    if not recovery._source_matches(job, job.encounter): raise ValueError('Current grant source changed')
    _, exposure = _baseline(nodes[-2], grant)
    if exposure + stage_exposure(job.config, previous, cap, stage, attempt) > CEILING:
        raise ValueError('The total original case campaign ceiling is exhausted')
