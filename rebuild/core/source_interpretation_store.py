"""Explicit, append-only generation lineage for the prospective source graph.

Reading this store never sends a request or upgrades a historical generation.
Review metadata and encounter revision counters are not source identity.
"""
from copy import deepcopy
import hashlib
import json
import os
import re
import stat
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection

from . import ai_stages, source_assertion_graph as graph
from .models import Encounter, Job, SourceInterpretation
from .provider_schema import retained_request_matches
from .security import private_path

IDENTITY_KEYS = ('patient_id', 'encounter_id', 'department_id', 'service_date',
    'template_version_id', 'generation_job_id', 'patient_display_name', 'patient_reference')
SEQUENCE = (('extractor', 1), ('assigner', 1), ('checker', 1), ('assigner', 2), ('checker', 2))
MAX_RECEIPT_BYTES = 8 * 1024 * 1024


def require(condition, code):
    if not condition:
        raise ValidationError('Source interpretation: ' + code, code=code)


def same(left, right):
    """JSON equality preserves boolean/number and string/number distinctions."""
    return graph.canonical(left) == graph.canonical(right)


def _definitions(encounter):
    from .semantic_review import definitions_for
    return definitions_for(encounter.template_version)


def identity_for(encounter, definitions, *, generation_job_id):
    require(same(definitions, _definitions(encounter)), 'current_definitions')
    require(encounter.patient.department_id == encounter.department_id
        and encounter.template_version.template.department_id == encounter.department_id,
        'department_binding')
    result = {'patient_id': str(encounter.patient_id), 'encounter_id': str(encounter.pk),
        'department_id': str(encounter.department_id), 'service_date': encounter.service_date.isoformat(),
        'template_version_id': str(encounter.template_version_id), 'generation_job_id': str(generation_job_id),
        'patient_display_name': encounter.patient.display_name, 'patient_reference': encounter.patient.reference}
    for key in IDENTITY_KEYS:
        require(type(result[key]) is str and (bool(result[key]) or key == 'patient_reference'), 'identity_text')
    try:
        for key in IDENTITY_KEYS[:3] + IDENTITY_KEYS[4:6]:
            require(str(UUID(result[key])) == result[key], 'identity_uuid')
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError('Source interpretation: identity_uuid') from exc
    return result


def _bindings(encounter, job, definitions):
    identity = identity_for(encounter, definitions, generation_job_id=str(job.pk))
    source_sha = hashlib.sha256(encounter.notes.encode()).hexdigest()
    require(job.encounter_id == encounter.pk and job.kind == 'generation', 'job_encounter')
    require(job.config.get('semantic_fact_scope_contract') == graph.CONTRACT
        and job.config.get('semantic_template_version') == identity['template_version_id']
        and job.config.get('semantic_source_sha256') == source_sha
        and job.config.get('semantic_definitions_sha256') == graph.digest(definitions)
        and same(job.config.get('semantic_encounter_binding'),
                 {k: v for k, v in identity.items() if k != 'generation_job_id'}), 'queued_bindings')
    version = encounter.template_version
    return {'identity': identity, 'source_sha256': source_sha,
        'fields_sha256': graph.digest(version.fields), 'definitions_sha256': graph.digest(definitions),
        'original_sha256': version.template.sha256, 'prepared_sha256': version.prepared_sha256,
        'generation_revision': job.revision, 'config_sha256': graph.digest(job.config),
        'result_path': job.result_path, 'result_sha256': job.result_sha256}


def _read(path, expected):
    require(type(path) is str and re.fullmatch(r'receipts/[0-9a-f]{48}\.json', path)
        and type(expected) is str and re.fullmatch(r'[0-9a-f]{64}', expected), 'receipt_pointer')
    resolved = private_path(path)
    target = settings.MEDIA_ROOT.resolve() / path
    require(not target.parent.is_symlink() and not target.is_symlink() and target == resolved, 'receipt_link')
    try:
        # A retained receipt must remain a regular file, not an alternate file selected by a link.
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_RECEIPT_BYTES, 'receipt_size')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(MAX_RECEIPT_BYTES + 1)
            after = os.fstat(fd)
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'receipt_changed')
        finally:
            os.close(fd)
        require(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == expected, 'receipt_digest')
        result = json.loads(raw)
        require(type(result) is dict, 'receipt_object')
        return result
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValidationError('Source interpretation: unreadable_receipt') from exc


def _output(wrapper, row):
    if row.simulated:
        require(wrapper.get('simulated') is True and 'output' in wrapper, 'simulated_receipt')
        return deepcopy(wrapper['output'])
    require('simulated' not in wrapper and type(wrapper.get('provider_output')) is dict, 'live_receipt')
    require(wrapper.get('provider_request_id') == row.provider_request_id
        and wrapper.get('provider_resource_id') == row.provider_resource_id
        and wrapper.get('returned_model') == row.returned_model, 'provider_receipt_identity')
    response = wrapper['provider_output']
    if row.provider == 'anthropic':
        text = ''.join(b.get('text', '') for b in response.get('content', []) if b.get('type') == 'text')
    elif row.provider == 'openai':
        text = ''.join(c.get('text', '') for item in response.get('output', [])
            for c in item.get('content', []) if c.get('type') == 'output_text')
    else:
        raise ValidationError('Source interpretation: unknown_provider')
    try:
        result = json.loads(text)
        require(type(result) is dict, 'provider_output_object')
        return result
    except (ValueError, TypeError) as exc:
        raise ValidationError('Source interpretation: unreadable_provider_output') from exc


def _retained(job, interpretation, answers):
    """Reconstruct the exact already-sent stage payloads, without a transport."""
    from . import source_assertion_generation as generation
    expected = generation.raw_outputs(interpretation)
    rows = list(job.ai_stage_receipts.order_by('created_at', 'pk'))
    require(len(rows) in (3, 5) and tuple((r.stage, r.attempt) for r in rows) == SEQUENCE[:len(rows)]
        and tuple((role, attempt) for role, attempt, _ in expected) == SEQUENCE[:len(rows)]
        and len(expected) == len(rows), 'stage_population')
    requests, outputs, manifest = [], [], []
    for row, (_, _, expected_output) in zip(rows, expected):
        require(row.job_id == job.pk and row.definition_preparation_id is None
            and row.state == 'succeeded' and row.actual_cost is not None
            and row.started_at is not None and row.finished_at is not None
            and row.started_at <= row.finished_at and same(row.config, job.config), 'stage_state')
        request = _read(row.request_path, row.request_sha256)
        output = _output(_read(row.result_path, row.result_sha256), row)
        require(same(output, expected_output), 'stage_output_binding')
        requests.append(request); outputs.append(output)
        manifest.append({'id': str(row.pk), 'stage': row.stage, 'attempt': row.attempt,
            'request_path': row.request_path, 'request_sha256': row.request_sha256,
            'result_path': row.result_path, 'result_sha256': row.result_sha256,
            'config_sha256': graph.digest(row.config), 'actual_cost': str(row.actual_cost),
            'provider': row.provider, 'requested_model': row.requested_model,
            'returned_model': row.returned_model, 'provider_request_id': row.provider_request_id,
            'provider_resource_id': row.provider_resource_id, 'simulated': row.simulated,
            'started_at': row.started_at.isoformat(), 'finished_at': row.finished_at.isoformat()})
    cursor = 0
    def retained_send(role, attempt, payload, schema, instructions):
        nonlocal cursor
        require(cursor < len(rows), 'stage_replay_overrun')
        limit, timeout = ai_stages.generation_limits(job.config)
        envelope = {'protocol': ai_stages.PROTOCOL, 'stage': role, 'attempt': attempt,
            'payload': payload, 'schema': schema, 'instructions': instructions, 'max_output_tokens': limit}
        if 'semantic_capacity_profile' in job.config:
            envelope['timeout_seconds'] = timeout
        row = rows[cursor]
        require(retained_request_matches(requests[cursor], envelope, config=job.config,
            provider=row.provider, simulated=row.simulated), 'stage_request_binding')
        value = deepcopy(outputs[cursor]); cursor += 1
        return value
    restored = generation.run(interpretation['notes'], interpretation['fields'],
        interpretation['definitions'], retained_send, identity=interpretation['identity'])
    require(cursor == len(rows) and same(restored['interpretation'], interpretation)
        and same(restored['answers'], answers), 'retained_derivation')
    result = _read(job.result_path, job.result_sha256)
    from .semantic_generation import CONTRACT
    require(set(result) == {'contract', 'answers', 'interpretation', 'stages'}
        and result['contract'] == CONTRACT and same(result['answers'], answers)
        and same(result['interpretation'], interpretation)
        and result['stages'] == [str(row.pk) for row in rows], 'job_result_binding')
    return manifest


def _validate(encounter, job, interpretation):
    from . import source_assertion_generation as generation
    require(type(interpretation) is dict, 'interpretation_object')
    definitions = _definitions(encounter)
    bindings = _bindings(encounter, job, definitions)
    require(same(interpretation.get('identity'), bindings['identity'])
        and same(interpretation.get('fields'), encounter.template_version.fields)
        and same(interpretation.get('definitions'), definitions), 'interpretation_bindings')
    answers = generation.restore(encounter.notes, interpretation)
    return bindings, answers


def adopt(encounter, job, interpretation, answers):
    """Must share the caller's source lock, adoption and job-success transaction."""
    require(connection.in_atomic_block, 'adoption_transaction')
    current = Encounter.objects.select_for_update().select_related('patient', 'template_version__template').get(pk=encounter.pk)
    parent = Job.objects.select_for_update().get(pk=job.pk)
    require(current.status != 'finalized' and parent.state == 'running'
        and parent.revision == current.revision, 'adoption_freshness')
    bindings, generated = _validate(current, parent, interpretation)
    require(same(generated, answers), 'adoption_answers')
    manifest = _retained(parent, interpretation, generated)
    require(not SourceInterpretation.objects.filter(job=parent).exists(), 'already_adopted')
    return SourceInterpretation.objects.create(job=parent, encounter=current, contract=graph.CONTRACT,
        interpretation_sha256=interpretation['sha256'], source_sha256=bindings['source_sha256'],
        bindings=bindings, interpretation=deepcopy(interpretation), stage_receipts=manifest)


def _current_for_read(encounter):
    """Read registry/source joins anew; retain their locks in a caller's write transaction."""
    require(isinstance(encounter, Encounter) and not encounter._state.adding
        and encounter._state.db == connection.alias, 'persisted_encounter')
    query = Encounter.objects.select_related('patient', 'template_version__template')
    if connection.in_atomic_block:
        lock = True
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_read_only')
                state = cursor.fetchone()
            require(state in (('on',), ('off',)), 'transaction_read_mode')
            lock = state == ('off',)
        if lock:
            query = query.select_for_update(of=('self', 'patient', 'template_version', 'template_version__template'))
    try:
        return query.get(pk=encounter.pk)
    except Encounter.DoesNotExist as exc:
        raise ValidationError('Source interpretation: missing_current_encounter') from exc


def load_for_answer(encounter, field, definition, answer):
    """Select by the explicit job; copied proofs never find a row by digest alone."""
    lineage = answer.get('source_interpretation')
    require(type(lineage) is dict and set(lineage) == {'generation_job_id', 'interpretation_sha256'}, 'answer_lineage')
    try:
        identifier = UUID(lineage['generation_job_id'])
        require(str(identifier) == lineage['generation_job_id'], 'answer_job_uuid')
        row = SourceInterpretation.objects.select_related('job').get(job_id=identifier, encounter_id=encounter.pk)
    except (TypeError, ValueError, SourceInterpretation.DoesNotExist) as exc:
        raise ValidationError('Source interpretation: missing_explicit_generation') from exc
    require(row.contract == graph.CONTRACT and row.job.state == 'succeeded'
        and lineage['interpretation_sha256'] == row.interpretation_sha256
        and row.interpretation.get('sha256') == row.interpretation_sha256, 'stored_identity')
    current = _current_for_read(encounter)
    bindings, generated = _validate(current, row.job, row.interpretation)
    require(same(bindings, _bindings(encounter, row.job, _definitions(encounter))), 'caller_current_bindings')
    require(same(bindings, row.bindings) and row.source_sha256 == bindings['source_sha256'], 'stored_bindings')
    key = field.get('key')
    require(key in generated and same(definition, row.interpretation['definitions'].get(key))
        and same(field, next((f for f in row.interpretation['fields'] if f.get('key') == key), None)), 'answer_destination')
    require(same(_retained(row.job, row.interpretation, generated), row.stage_receipts), 'stored_stage_receipts')
    return deepcopy(row.interpretation)
