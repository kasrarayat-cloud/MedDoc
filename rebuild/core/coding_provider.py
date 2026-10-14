"""Two owner-sponsored synthetic coding calls, separate from clinical jobs.

No SDK retries, wallet writes, clinical adoption, or implicit fixture fallback.
The request and raw response commit before metering or clinical interpretation.
"""
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone
from pydantic import BaseModel

from . import ai_stages, generation, testing_authority

AUTHORITY_ID = 'quillmd-outpatient-coding-synthetic-20261014-v1'
PROTOCOL = 'outpatient-coding-provider-v1'
STAGES = ('concepts', 'resolution')
MAX_REQUEST_BYTES = 512000
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_TOKENS = 8000
TIMEOUT_SECONDS = 120
TERMINAL = frozenset(('succeeded', 'failed', 'unknown', 'not_sent'))


class CodingNotSent(ValidationError):
    """A refusal before transport; no provider charge is inferred."""


class CodingUnknown(ValidationError):
    """A possibly chargeable send requires reconciliation, never automatic retry."""


class CodingFailure(ValidationError):
    """The retained response failed validation; known costs remain recorded."""


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def _fixture_allowed():
    name = str(connection.settings_dict.get('NAME', ''))
    return (getattr(settings, 'CODING_ALLOW_TEST_FIXTURES', False) is True
            and (name.startswith('test_') or (connection.vendor == 'sqlite'
                 and (name == ':memory:' or name.startswith('file:memorydb_')))))


def configuration(actor, encounter):
    """Snapshot this new purpose, existing actor enrollment and configured price."""
    testing_authority.admit_actor(actor, encounter.department_id)
    # This coding-only grant includes existing synthetic department records.
    # The clinical-generation ownership gate remains unchanged in its module.
    from .security import membership
    membership(actor, encounter.department_id, roles=['owner', 'clinician'])
    base = generation.configuration()
    if (base.get('mode') not in ('live', 'fixture')
            or base.get('provider') not in ('anthropic', 'openai')
            or base['provider'] != settings.AI_PROVIDER
            or base.get('model') != settings.AI_MODEL
            or not isinstance(base['model'], str) or not 0 < len(base['model']) <= 100):
        raise CodingNotSent('Coding requires the configured authorized provider and model.')
    if base['mode'] == 'fixture' and not _fixture_allowed():
        raise CodingNotSent('Coding fixtures are restricted to explicitly configured isolated tests.')
    if any(type(base.get(k)) is not str for k in ('input_rate', 'cached_rate', 'output_rate')):
        raise CodingNotSent('Coding requires explicit decimal rate strings.')
    generation.rates(base)
    generation.normalized_discount(base.get('discount_rate'))
    result = {key: base[key] for key in ('mode', 'provider', 'model', 'input_rate',
              'cached_rate', 'output_rate', 'discount_rate', 'pricing_version')}
    result.update(coding_authority_id=AUTHORITY_ID, coding_protocol=PROTOCOL,
                  coding_purpose='outpatient-coding-assistance', actor_id=str(actor.pk),
                  coding_encounter_scope='authorized_department_existing_synthetic',
                  department_id=str(encounter.department_id), encounter_id=str(encounter.pk),
                  actor_enrollment=testing_authority.ACTOR_ENROLLMENTS.get(str(actor.pk), ''),
                  max_calls=2, request_byte_limit=MAX_REQUEST_BYTES,
                  output_token_limit=MAX_OUTPUT_TOKENS, timeout_seconds=TIMEOUT_SECONDS,
                  account_charged_usd='0', cost_basis='provider_usage_times_configured_rates',
                  invoice_reconciled=False)
    if base['mode'] == 'fixture':
        fixtures = getattr(settings, 'CODING_FIXTURE_RESPONSES', None)
        if type(fixtures) is not dict or set(fixtures) != set(STAGES):
            raise CodingNotSent('Both explicit coding fixture responses are required.')
        result['fixture_responses'] = deepcopy(fixtures)
    try:
        estimate = ai_stages.quote(result, MAX_REQUEST_BYTES, MAX_OUTPUT_TOKENS) * 2
        if not estimate.is_finite() or not 0 <= estimate < Decimal('1000000000000'):
            raise ValueError('estimate out of retained range')
    except (InvalidOperation, ValueError) as exc:
        raise CodingNotSent('Coding prices do not produce a finite retainable estimate.') from exc
    result['maximum_estimated_cost'] = str(estimate)
    return json.loads(encode(result))


def _identity(run):
    inputs = {'inputs': run.inputs, 'context': run.context, 'releases': run.releases}
    if not re.fullmatch('[0-9a-f]{64}', run.input_digest or '') or digest(inputs) != run.input_digest:
        raise CodingNotSent('Coding input snapshot does not match its immutable digest.')
    return {'input_digest': run.input_digest, 'config_sha256': digest(run.config),
            'actor_id': str(run.user_id), 'encounter_id': str(run.encounter_id)}


def _admit(run, identity=None):
    if run.state != 'running' or encode(run.config) != encode(configuration(run.user, run.encounter)):
        raise CodingNotSent('Coding is not running under its unchanged authorized configuration.')
    actual = _identity(run)
    if identity is not None and actual != identity:
        raise CodingNotSent('Coding input or configuration changed before the provider send.')
    return actual


def _locked(run):
    return type(run).objects.select_for_update().select_related('user', 'encounter').get(pk=run.pk)


def _aggregate(rows):
    if any(row['sent'] and row['actual_cost'] is None for row in rows):
        return None
    return sum((Decimal(row['actual_cost']) for row in rows if row['actual_cost'] is not None), Decimal('0'))


def _store(run, stage, change):
    with transaction.atomic():
        current = _locked(run)
        rows = deepcopy(current.requests)
        found = [row for row in rows if row['stage'] == stage]
        if len(found) != 1 or found[0]['state'] in TERMINAL:
            raise CodingUnknown('Coding receipt is absent or already complete; it cannot be rewritten.')
        found[0].update(change)
        current.requests = rows
        current.actual_cost = _aggregate(rows)
        fields = ['requests', 'actual_cost']
        current.save(update_fields=fields)
        for field in fields:
            setattr(run, field, deepcopy(getattr(current, field)))


@contextmanager
def _provider_slot(config):
    if config['mode'] == 'fixture':
        if not _fixture_allowed():
            raise CodingNotSent('Coding fixtures are unavailable outside isolated tests.')
        yield
        return
    if connection.vendor != 'postgresql':
        raise CodingNotSent('Live coding requires the shared PostgreSQL provider lock.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [testing_authority.PROVIDER_LOCK])
        acquired = cursor.fetchone()[0]
    if acquired is not True:
        raise CodingNotSent('Another provider request is active; nothing was sent.')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [testing_authority.PROVIDER_LOCK])
            if cursor.fetchone()[0] is not True:
                raise CodingFailure('Coding provider lock release could not be confirmed.')


def _counter(value):
    if type(value) is not int or not 0 <= value <= 1000000000:
        raise CodingUnknown('Raw provider token usage is not a bounded nonnegative integer.')
    return value


def _token_tree(value):
    if type(value) is dict:
        for key, item in value.items():
            if key.endswith('tokens'):
                _counter(item)
            elif isinstance(item, (dict, list)):
                _token_tree(item)
    elif type(value) is list:
        for item in value:
            _token_tree(item)


def raw_accounting(raw, config):
    """Meter the untouched raw counters, before SDK falsey-value normalization."""
    usage = raw.get('usage')
    if type(usage) is not dict:
        raise CodingUnknown('Raw provider usage is missing.')
    _token_tree(usage)
    input_tokens = _counter(usage.get('input_tokens'))
    output_tokens = _counter(usage.get('output_tokens'))
    rates = generation.rates(config)
    units = {'input_tokens': input_tokens, 'output_tokens': output_tokens}
    if config['provider'] == 'anthropic':
        cached = _counter(usage.get('cache_read_input_tokens', 0))
        written = _counter(usage.get('cache_creation_input_tokens', 0))
        breakdown = usage.get('cache_creation')
        write_cost = Decimal(written) * rates['input_per_million'] * Decimal('1.25')
        if breakdown is not None:
            if type(breakdown) is not dict:
                raise CodingUnknown('Invalid provider cache creation breakdown.')
            short = _counter(breakdown.get('ephemeral_5m_input_tokens', 0))
            long = _counter(breakdown.get('ephemeral_1h_input_tokens', 0))
            if short + long != written:
                raise CodingUnknown('Provider cache creation totals do not reconcile.')
            if long:
                raise CodingUnknown('Long-duration cache creation has no configured coding rate; reconciliation is required.')
            write_cost = rates['input_per_million'] * Decimal(short) * Decimal('1.25')
            units['cache_creation_5m_tokens'] = short
            units['cache_creation_1h_tokens'] = long
        units.update(cached_input_tokens=cached, cache_creation_tokens=written)
        amount = input_tokens * rates['input_per_million'] + cached * rates['cached_per_million'] + write_cost + output_tokens * rates['output_per_million']
    elif config['provider'] == 'openai':
        details = usage.get('input_tokens_details')
        if type(details) is not dict:
            raise CodingUnknown('Raw provider input-token details are missing.')
        cached = _counter(details.get('cached_tokens'))
        if cached > input_tokens:
            raise CodingUnknown('Provider cached input exceeds total input.')
        units['cached_input_tokens'] = cached
        amount = (input_tokens - cached) * rates['input_per_million'] + cached * rates['cached_per_million'] + output_tokens * rates['output_per_million']
    else:
        raise CodingUnknown('Unknown provider accounting format.')
    list_cost = amount / 1000000
    discount = generation.discount_rate(config)
    cost = generation.discounted_cost(list_cost, discount)
    if not cost.is_finite() or not 0 <= cost < Decimal('1000000000000'):
        raise CodingUnknown('Provider cost is outside the finite retained range.')
    return cost, units, generation.cost_rates(rates, list_cost, discount)


def _json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON constant')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def execute(run, stage, payload, schema, instructions):
    """Send at most once for each of two stages; return strictly validated JSON."""
    if stage not in STAGES or not isinstance(schema, type) or not issubclass(schema, BaseModel):
        raise CodingNotSent('Coding requires a named stage and a Pydantic response model.')
    if schema.model_config.get('extra') != 'forbid' or not isinstance(instructions, str) or not instructions:
        raise CodingNotSent('Coding requires a closed response model and explicit instructions.')
    config = deepcopy(run.config)
    identity = _identity(run)
    envelope = {'protocol': PROTOCOL, 'stage': stage, 'identity': identity, 'payload': payload,
                'schema': schema.model_json_schema(), 'instructions': instructions,
                'config': config, 'max_output_tokens': MAX_OUTPUT_TOKENS, 'timeout_seconds': TIMEOUT_SECONDS}
    try:
        raw_request = encode(envelope)
    except (TypeError, ValueError) as exc:
        raise CodingNotSent('Coding request must contain finite JSON values.') from exc
    if len(raw_request) > MAX_REQUEST_BYTES:
        raise CodingNotSent('Coding request exceeds its byte limit; nothing was truncated or sent.')
    # Transport consumes the exact retained JSON snapshot, not caller-owned dicts.
    envelope = json.loads(raw_request)
    with transaction.atomic():
        current = _locked(run)
        _admit(current, identity)
        rows = deepcopy(current.requests)
        if (type(rows) is not list or len(rows) >= 2 or any(row['stage'] == stage for row in rows)
                or (stage == 'concepts' and rows)
                or (stage == 'resolution' and (len(rows) != 1 or rows[0]['stage'] != 'concepts' or rows[0]['state'] != 'succeeded'))
                or any(row['envelope']['identity'] != identity for row in rows)):
            raise CodingNotSent('Coding stage is already attempted or its predecessor is not complete.')
        row = {'stage': stage, 'attempt': 1, 'provider': config['provider'], 'simulated': config['mode'] == 'fixture',
               'envelope': envelope, 'request_sha256': hashlib.sha256(raw_request).hexdigest(),
               'state': 'reserved', 'sent': False, 'raw_response': None, 'response_sha256': '',
               'provider_request_id': '', 'provider_resource_id': '', 'returned_model': '',
               'usage': {}, 'rates': {}, 'actual_cost': None, 'error_code': '',
               'started_at': timezone.now().isoformat(), 'finished_at': None}
        current.requests = rows + [row]
        current.actual_cost = _aggregate(current.requests)
        current.save(update_fields=['requests', 'actual_cost'])
        run.requests = deepcopy(current.requests)
    sent = False
    metered = False
    received = False

    def on_response(response):
        nonlocal metered, received
        raw = response.model_dump(mode='json')
        raw_bytes = encode(raw)
        if len(raw_bytes) > MAX_RESPONSE_BYTES:
            raise CodingUnknown('Raw response exceeds the durable coding receipt bound.')
        ids = {'provider_request_id': getattr(response, '_request_id', '') or '',
               'provider_resource_id': getattr(response, 'id', '') or '',
               'returned_model': getattr(response, 'model', '') or ''}
        _store(run, stage, {'raw_response': raw, 'response_sha256': hashlib.sha256(raw_bytes).hexdigest(),
                           'state': 'received', **ids})
        received = True
        if (any(type(value) is not str or not value or len(value) > (100 if key == 'returned_model' else 140)
                for key, value in ids.items())
                or any(old['stage'] != stage and (old['provider_request_id'] == ids['provider_request_id']
                           or old['provider_resource_id'] == ids['provider_resource_id']) for old in run.requests)):
            raise CodingUnknown('Provider response identity is missing, invalid or repeated.')
        for name in ('provider_request_id', 'provider_resource_id'):
            if type(run).objects.exclude(pk=run.pk).filter(requests__contains=[{
                    'provider': config['provider'], name: ids[name]}]).exists():
                raise CodingUnknown('Provider response identity already belongs to another coding run.')
        cost, units, rates = raw_accounting(raw, config)
        _store(run, stage, {'actual_cost': str(cost), 'usage': units, 'rates': rates})
        metered = True

    try:
        with _provider_slot(config):
            with transaction.atomic():
                _admit(_locked(run), identity)
            if config['mode'] == 'live':
                key = 'ANTHROPIC_API_KEY' if config['provider'] == 'anthropic' else 'OPENAI_API_KEY'
                if not os.getenv(key):
                    raise CodingNotSent('The configured provider credential is unavailable; nothing was sent.')
                _store(run, stage, {'state': 'sending', 'sent': True})
                sent = True
                _response_object, _cost, _units, _rates, text, complete = ai_stages._response(
                    envelope['payload'], envelope['schema'], envelope['instructions'], config,
                    MAX_OUTPUT_TOKENS, TIMEOUT_SECONDS, on_response)
                if not received or not metered:
                    raise CodingUnknown('Provider response or usage was not durably retained.')
            else:
                parsed_fixture = deepcopy(config['fixture_responses'][stage])
                raw = {'simulated': True, 'output': parsed_fixture}
                _store(run, stage, {'state': 'received', 'raw_response': raw, 'response_sha256': digest(raw),
                                   'actual_cost': '0', 'usage': {}, 'rates': {}})
                metered = received = True
                text, complete = encode(parsed_fixture), True
            try:
                if not complete:
                    raise ValueError('incomplete response')
                parsed = schema.model_validate(_json(text), strict=True).model_dump(mode='json')
                encode(parsed)
            except Exception as exc:
                raise CodingFailure('Coding response failed its closed local schema.') from exc
            _store(run, stage, {'state': 'succeeded', 'finished_at': timezone.now().isoformat()})
            return parsed
    except Exception as exc:
        # A lock-release error after success does not rewrite a completed receipt.
        active = next(row for row in run.requests if row['stage'] == stage)
        if active['state'] in TERMINAL:
            raise
        unknown = sent and not metered
        state = 'unknown' if unknown else ('failed' if received else 'not_sent')
        cost = None if unknown else active['actual_cost'] if metered else '0'
        _store(run, stage, {'state': state, 'actual_cost': cost, 'error_code': 'outcome_unknown' if unknown else 'response_invalid' if received else 'not_sent',
                           'finished_at': timezone.now().isoformat()})
        error_type = CodingUnknown if unknown else CodingFailure if received else CodingNotSent
        raise error_type('Coding stopped; the retained attempt will not be resent.') from exc
