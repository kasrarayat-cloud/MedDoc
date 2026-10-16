"""One durable direct prediction attempt. No agent API, retries or fallback.

The live path has its own prospective coding purpose under standing synthetic
testing authority. Replay is restricted to an explicitly isolated test database.
Provider credits are not dollars; unknown invoice cost stays unknown.
"""
from copy import deepcopy
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from dotenv import dotenv_values
import requests
from requests.adapters import HTTPAdapter

from . import coding_provider as receipts, testing_authority
from .coding_provider import CodingFailure, CodingNotSent, CodingUnknown

PROTOCOL = 'quillmd-corti-direct-prediction-v1'
PURPOSE = 'corti-direct-coding-workflow-synthetic-20261016'
MAX_REQUEST_BYTES = 512000
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
TIMEOUT_SECONDS = 120
STAGE = 'prediction'


def _credentials():
    # Treat exported dotenv assignments as data; never source shell code or
    # interpolate other environment variables. No secret enters run.config.
    from .coding_licensing import _read
    try:
        path = Path(settings.CORTI_CREDENTIALS_FILE)
        values = dotenv_values(stream=io.StringIO(_read(path, 32000).decode()), interpolate=False)
        region = values.get('CORTI_ENVIRONMENT')
        tenant = values.get('CORTI_TENANT_NAME')
        client, secret = values.get('CORTI_CLIENT_ID'), values.get('CORTI_CLIENT_SECRET')
        if (region not in ('us', 'eu') or not isinstance(tenant, str)
                or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', tenant)
                or not all(isinstance(x, str) and x.strip() for x in (client, secret))):
            raise ValueError()
        return region, tenant, client, secret
    except Exception:
        raise CodingNotSent('Protected Corti dotenv configuration is unavailable or invalid.') from None


def configuration(actor, encounter):
    if not settings.SYNTHETIC_ONLY:
        raise CodingNotSent('Corti coding remains restricted to synthetic testing.')
    testing_authority.admit_actor(actor, encounter.department_id)
    from .security import membership
    membership(actor, encounter.department_id, roles=['owner', 'clinician'])
    mode = getattr(settings, 'CORTI_CODING_MODE', 'disabled')
    result = dict(provider='corti', mode=mode, coding_protocol=PROTOCOL,
        coding_purpose=PURPOSE, actor_id=str(actor.pk), department_id=str(encounter.department_id),
        encounter_id=str(encounter.pk), actor_enrollment=testing_authority.ACTOR_ENROLLMENTS.get(str(actor.pk), ''),
        max_calls=1, automatic_retries=0, timeout_seconds=TIMEOUT_SECONDS,
        request_byte_limit=MAX_REQUEST_BYTES, account_charged_usd='0', invoice_reconciled=False)
    if mode == 'replay':
        if not receipts._fixture_allowed():
            raise CodingNotSent('Corti replay requires an explicitly isolated test database.')
        fixture = getattr(settings, 'CORTI_REPLAY_FIXTURE', None)
        if type(fixture) is not dict or set(fixture) != {'request', 'response_raw', 'response_sha256', 'original_verdict'}:
            raise CodingNotSent('An exact retained request, raw response, hash and original verdict are required.')
        if (type(fixture['response_raw']) is not str
                or hashlib.sha256(fixture['response_raw'].encode()).hexdigest() != fixture['response_sha256']):
            raise CodingNotSent('Retained replay response hash does not match.')
        result['replay_fixture_sha256'] = receipts.digest(fixture)
    elif mode == 'live':
        if not testing_authority.enabled():
            raise CodingNotSent('Prospective standing synthetic testing authority is not active.')
        region, tenant, _client, _secret = _credentials()
        result.update(environment=region, tenant=tenant,
            testing_authority_id=testing_authority.AUTHORITY_ID,
            testing_authority_sha256=testing_authority.AUTHORITY_SHA256,
            testing_authority_mode=testing_authority.MODE)
    else:
        raise CodingNotSent('Corti direct coding has not been enabled for this candidate.')
    return result


def payload(run):
    from .coding_engine import clinical_answers
    contexts = [{'type': 'text', 'text': run.inputs['notes']}]
    # Preserve exact saved text. Never send internal generation proofs or held
    # candidate answers. A separate context keeps provider offsets unambiguous.
    for key, answer in clinical_answers(run.inputs.get('answers', {})).items():
        if answer.get('text', '').strip():
            contexts.append({'type': 'text', 'text': answer['text']})
    if run.config.get('mode') == 'replay':
        original = settings.CORTI_REPLAY_FIXTURE['request']
        # Replay may only reuse the exact original synthetic note. Saved answers
        # remain in the bound snapshot, but are not invented original API input.
        if original.get('context') != contexts[:1]:
            raise CodingNotSent('Retained response cannot be replayed against a different source note.')
        return deepcopy(original)
    contexts.append({'type': 'text', 'text': 'Date of service: ' + run.inputs['service_date']})
    return {'system': ['icd10cm-outpatient', 'cpt'], 'context': contexts}


def _admit(run, identity):
    if run.state != 'running' or run.config != configuration(run.user, run.encounter):
        raise CodingNotSent('Corti configuration or authority changed before sending.')
    if receipts._identity(run) != identity:
        raise CodingNotSent('Corti input identity changed before sending.')


def _session():
    session = requests.Session()
    session.trust_env = False
    session.mount('https://', HTTPAdapter(max_retries=0))
    return session


def _redact(raw, secrets):
    for value in secrets:
        if value:
            raw = raw.replace(value.encode(), b'[REDACTED]')
    return re.sub(rb'(?i)("(?:access_token|refresh_token|id_token|client_secret)"\s*:\s*")[^"]*',
                  rb'\1[REDACTED]', raw)


def execute(run, request):
    identity = receipts._identity(run)
    body = receipts.encode(request)
    if len(body) > MAX_REQUEST_BYTES:
        raise CodingNotSent('Coding request exceeds its byte limit; nothing was truncated or sent.')
    envelope = {'protocol': PROTOCOL, 'identity': identity, 'payload': deepcopy(request),
                'config': deepcopy(run.config)}
    with transaction.atomic():
        current = receipts._locked(run)
        _admit(current, identity)
        if current.requests:
            raise CodingNotSent('The direct prediction was already attempted; it cannot be resubmitted.')
        current.requests = [dict(stage=STAGE, attempt=1, provider='corti', simulated=run.config['mode'] == 'replay',
            envelope=envelope, request_sha256=hashlib.sha256(body).hexdigest(), state='reserved', sent=False,
            raw_response=None, response_sha256='', actual_cost=None, usage={},
            started_at=timezone.now().isoformat(), finished_at=None)]
        current.save(update_fields=['requests'])
        run.requests = deepcopy(current.requests)
    sent = received = False
    start = time.monotonic()
    try:
        if run.config['mode'] == 'replay':
            if not receipts._fixture_allowed():
                raise CodingNotSent('Replay is unavailable outside isolated tests.')
            fixture = settings.CORTI_REPLAY_FIXTURE
            raw = fixture['response_raw'].encode()
            http_status, latency, secrets = 200, None, []
        else:
            # Share the existing single-flight provider lock, without changing
            # the configured clinical-generation provider or its accounting.
            with receipts._provider_slot({'mode': 'live'}), _session() as session:
                with transaction.atomic():
                    _admit(receipts._locked(run), identity)
                region, tenant, client, secret = _credentials()
                auth_url = f'https://auth.{region}.corti.app/realms/{tenant}/protocol/openid-connect/token'
                auth = session.post(auth_url, data={'client_id': client, 'client_secret': secret,
                    'grant_type': 'client_credentials', 'scope': 'openid'}, timeout=(10, 30), allow_redirects=False)
                if auth.status_code != 200:
                    raise CodingNotSent('Corti authentication failed; no coding request was sent.')
                token = auth.json().get('access_token')
                if type(token) is not str or not token:
                    raise CodingNotSent('Corti authentication did not return an access token.')
                secrets = [client, secret, token]
                receipts._store(run, STAGE, {'state': 'sending', 'sent': True})
                sent = True
                started = time.monotonic()
                with session.post(f'https://api.{region}.corti.app/v2/tools/coding/',
                        data=body, headers={'Authorization': 'Bearer ' + token, 'Tenant-Name': tenant,
                        'Content-Type': 'application/json'}, timeout=(10, TIMEOUT_SECONDS),
                        allow_redirects=False, stream=True) as response:
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES or time.monotonic() - started > TIMEOUT_SECONDS:
                            raise CodingUnknown('Corti response exceeded the technical response bound.')
                        chunks.append(chunk)
                    raw = b''.join(chunks)
                    http_status = response.status_code
                latency = round((time.monotonic() - started) * 1000, 3)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise CodingUnknown('Corti response exceeds the durable receipt bound.')
        safe = _redact(raw, secrets)
        receipts._store(run, STAGE, {'state': 'received', 'raw_response': {
            'body': safe.decode('utf-8', errors='replace'), 'redacted': safe != raw},
            'response_sha256': hashlib.sha256(raw).hexdigest(), 'http_status': http_status,
            'latency_ms': latency, 'actual_cost': '0' if not sent else None})
        received = True
        if http_status != 200:
            raise CodingFailure('Corti returned an unsuccessful status; raw failure retained.')
        parsed = receipts._json(safe)
        if type(parsed) is not dict or type(parsed.get('codes')) is not list or len(parsed['codes']) > 64:
            raise CodingFailure('Corti returned an invalid selected-code collection.')
        usage = deepcopy(parsed.get('usageInfo', {}))
        credit = usage.get('creditsConsumed') if type(usage) is dict else None
        try:
            if credit is not None and (isinstance(credit, bool) or not Decimal(str(credit)).is_finite() or Decimal(str(credit)) < 0):
                raise ValueError()
        except (InvalidOperation, ValueError):
            raise CodingUnknown('Corti credits could not be reconciled.') from None
        receipts._store(run, STAGE, {'state': 'succeeded', 'usage': usage,
            'usage_basis': 'historical_replay_not_new_usage' if not sent else 'provider_reported_credits_not_usd',
            'finished_at': timezone.now().isoformat(), 'total_latency_ms': round((time.monotonic()-start)*1000, 3)})
        return parsed
    except Exception as exc:
        row = run.requests[0]
        if row['state'] not in receipts.TERMINAL:
            unknown = sent and not received
            receipts._store(run, STAGE, {'state': 'unknown' if unknown else 'failed' if received else 'not_sent',
                'actual_cost': None if sent else '0', 'error_code': 'outcome_unknown' if unknown else 'response_invalid' if received else 'not_sent',
                'finished_at': timezone.now().isoformat()})
        error = CodingUnknown if sent and not received else CodingFailure if received else CodingNotSent
        raise error('Corti stopped; the retained attempt will not be resent.') from None
