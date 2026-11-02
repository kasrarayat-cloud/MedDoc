"""Prove one participant's live access with exactly one minimal synthetic request (HARNESS.md 8; checklist item 1.3).

Run it where the participant's credentials are mounted (the worker):

    python manage.py participant_access_check --participant astra

It refuses, sending nothing, unless that participant is live on this installation (CPT_STUDIO_PROVIDER_MODE for Corti,
CPT_STUDIO_ASTRA_MODE or CPT_STUDIO_FABLE_MODE), the installation is synthetic-only and an owner authorization is
configured; and while another provider request holds the installation-wide single-flight lock (I8). It then sends one
request through the real adapter, with no retry: Astra and Fable read the short synthetic GI note below as pasted text,
and Corti codes the same note. The answer is read as the pipeline reads it, and one JSON receipt is printed with no
secret in it: what was called, which model was asked for and which answered, the vendor's request and response ids,
the latency, the usage as reported with its estimated cost, and a summary of the reading. Nothing is written to the
database. The exit status is 1 when the request did not succeed or its answer was not used.

Astra's and Fable's request is the harness@2 one, so it offers the reference tools and runs as the pipeline's does,
through the tool loop (send_loop, HARNESS.md 11.2). The tools are answered here by a trivial local executor that
returns a fixed synthetic note and no reference data: the check proves access and the loop's mechanics, not the CMS
sources. The receipt gives the number of exchanges and, for each, its outcome, its request and response sha256 and the
vendor's request and response ids (Astra's client request id too), and each tool call's id and tool. The loop is given
PARTICIPANT_SEND_DEADLINE_SECONDS, inside the installer's limit for the whole check.
"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from studio.participants import LABELS, openai_astra, participant_mode, pricing, registry
from studio.providers import get_provider
from studio.providers.base import ProviderUnavailable

PARTICIPANTS = ('corti', 'astra', 'fable')
TOOL_NOTE = ('This is CPT Studio\'s access check: its tools return no reference data here. Answer from the document '
             'alone.')
NOTE = ('SYNTHETIC TEST DOCUMENT - not a real patient. Written for a CPT Studio access check.\n'
        'Procedure: Colonoscopy. Date of service: 2026-11-01.\n'
        'Findings: The colonoscope was advanced to the cecum; the appendiceal orifice was identified. A 5 mm '
        'sessile polyp in the sigmoid colon was removed with a cold snare and retrieved for pathology. The rest of '
        'the examined colon was normal.\n'
        'Impression: One sigmoid colon polyp, removed by cold snare.\n')


class Command(BaseCommand):
    help = ('Send one minimal synthetic request to one participant and print a JSON receipt (no secret, no database '
            'write).')

    def add_arguments(self, parser):
        parser.add_argument('--participant', required=True, choices=PARTICIPANTS)

    def handle(self, *args, **options):
        name = options['participant']
        label = 'Corti' if name == 'corti' else LABELS[name]
        mode = settings.PROVIDER_MODE if name == 'corti' else participant_mode(name)
        if mode != 'live':
            raise CommandError(f'{label} is not live on this installation (its mode is {mode}); nothing was sent.')
        if not settings.SYNTHETIC_ONLY:
            raise CommandError('This installation is not synthetic-only; nothing was sent.')
        if not settings.AUTHORIZATION_REF:
            raise CommandError('No owner authorization is configured (CPT_STUDIO_AUTHORIZATION_REF); nothing was sent.')
        try:
            with _single_flight():
                receipt = _corti() if name == 'corti' else _participant(name)
        except ProviderUnavailable as exc:  # misconfigured, or no request could be built: nothing was sent
            raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps(receipt, sort_keys=True))
        reading = receipt['reading']
        if receipt['outcome'] != 'succeeded' or reading is None or reading['refused']:
            raise CommandError(f'The {label} access check did not pass: see the receipt.')


@contextmanager
def _single_flight():
    """The installation-wide provider lock the pipeline's sends take (jobs._send): one clinical provider call at a
    time, the access check included. Taking a session advisory lock writes nothing."""
    from studio.jobs import PROVIDER_LOCK_KEY

    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [PROVIDER_LOCK_KEY])
        if not cursor.fetchone()[0]:
            raise CommandError('Another provider request is in flight; nothing was sent. Try again once it has '
                               'finished.')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK_KEY])


def _local_tool(name: str, arguments: dict) -> tuple[dict, list]:
    """The access check's tool executor: a fixed synthetic note and no reference data, so no ref is ever retrieved."""
    return {'tool': name, 'note': TOOL_NOTE}, []


def _participant(name: str) -> dict:
    adapter = registry.build(name, 'live')
    request = adapter.build_request(NOTE, (), 'paste', None)
    client_request_id = f'cptstudio-access-check-{uuid.uuid4()}'
    outcome = adapter.send_loop(request, deadline_s=settings.PARTICIPANT_SEND_DEADLINE_SECONDS,
                                client_request_id=client_request_id, original_bytes=None, execute_tool=_local_tool)
    exchange = outcome.final
    summary = None
    if exchange.outcome == 'succeeded':
        reading = adapter.read(request, exchange.response_bytes, outcome.refs_retrieved)
        summary = {'refused': reading.refused, 'problems': list(reading.problems),
                   'codes': [code.code for code in reading.codes], 'unverified_quotes': reading.unverified_quotes}
    receipt = _receipt(name, adapter.adapter_version, request, exchange, summary)
    receipt['client_request_id'] = client_request_id if name == 'astra' else ''
    receipt['estimated_cost'] = pricing.estimate_loop(adapter.requested_model,
                                                      [record.usage for record in outcome.exchanges])
    receipt['exchange_count'] = len(outcome.exchanges)
    receipt['exchanges'] = [{
        'turn': record.turn, 'outcome': record.outcome, 'http_status': record.http_status,
        'request_sha256': record.request_sha256, 'response_sha256': record.response_sha256,
        'request_id': record.provider_request_id, 'response_id': record.response_id, 'latency_ms': record.latency_ms,
        'client_request_id': openai_astra.turn_client_request_id(client_request_id, record.turn)
        if name == 'astra' else '',
        'tool_calls': [{'call_id': call.call_id, 'tool': call.tool} for call in record.tool_calls],
    } for record in outcome.exchanges]
    return receipt


def _corti() -> dict:
    provider = get_provider('live')
    request = provider.build_request(NOTE, None)
    exchange = provider.send(request, deadline_s=settings.PROVIDER_READ_TIMEOUT_SECONDS + 30)  # jobs._send's deadline
    summary = None
    if exchange.outcome == 'succeeded':
        normalized = provider.normalize(request, exchange.response_bytes)
        summary = {'refused': normalized.refused, 'problems': list(normalized.problems),
                   'codes': [code.code for code in normalized.codes if code.role == 'selected'],
                   'candidates': [code.code for code in normalized.codes if code.role != 'selected'],
                   'unverified_quotes': sum(1 for code in normalized.codes + normalized.internal_context
                                            for span in code.evidence if not span.exact)}
    receipt = _receipt('corti', provider.adapter_version, request, exchange, summary)
    receipt['client_request_id'] = ''
    receipt['estimated_cost'] = None  # Corti reports credits, not tokens (usage_basis says so)
    return receipt


def _receipt(name: str, adapter_version: str, request, exchange, reading) -> dict:
    return {'participant': name, 'adapter_version': adapter_version, 'endpoint': exchange.endpoint,
            'requested_model': exchange.requested_model, 'returned_model': exchange.returned_model,
            'outcome': exchange.outcome, 'sent': exchange.sent, 'http_status': exchange.http_status,
            'request_id': exchange.provider_request_id, 'response_id': exchange.response_id,
            'latency_ms': exchange.latency_ms, 'usage': exchange.usage, 'usage_basis': exchange.usage_basis,
            'request_sha256': request.canonical_sha256, 'response_sha256': exchange.response_sha256,
            'error': exchange.error, 'reading': reading, 'authorization_ref': settings.AUTHORIZATION_REF,
            'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
