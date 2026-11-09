"""The operator's interpretation evidence (design/FINAL.md 3.1, 4.2, 10.3, 13 and 14.7; DECISIONS D22): the record every
new-path assessment carries, the operator's interpretation section of one assessment, and the D22 window report with its
self-test (``manage.py interpretation_report``). Operator surfaces only: nothing here is a customer screen or download, and
none of it names a provider or model to a customer (D22).

THE RECORD (FINAL 4.2; ``interpretation_record``) is Assessment.interpretation, outside the result's sha256: the engine and
both interpretation versions, the inventory id and its sha256, the Gemini run, the context, member_date_state and the
sentinel's record ({legacy_calls, scope, tool, deny_size, positive_control}, sentinel.record). One builder, so the writer
(persist_assessment) and the readers here agree on one shape.

THE WINDOW REPORT (D22; ``window``) states, for [since, until): the model constant and this process's interpreter mode;
the Gemini runs by state, by the model asked for and the model that answered, the paused ones, their usage as reported
and their estimated cost (participants.pricing's dated rates; an estimate, never an invoice); the event inventories by
state; the assessments by engine version, the legacy-engine ones among them, the new-path ones that lack an inventory or
a sentinel record, and every problem record_problems finds in a new-path record; the legacy calls the new-path records
count; the sentinel's recorded trips (AuditEvent 'sentinel.tripped'), among them the processes that recorded they could
not count; this process's sentinel (install state, deny-set size against its pin, the positive control, its counters,
among them the residual legacy execution on legacy rows); and the interpreter hold (standing, set and released in the
window). Every field is in D22_FIELDS, and ``render`` prints each one.

THE SELF-TEST (FINAL 13; ``self_test``) is the installer's verify one-shot: the sentinel installed in this process with the
deny set as pinned, the positive control ok and tripping, the model constant equal to D13's literal, zero new_path
executions recorded, every new-path record without a problem, zero sentinel trips, and zero legacy-engine assessments in
the window (the installer gives --since the new worker's start, ADJUDICATION P-7). The hold state is reported beside it.

WHAT A ONE-SHOT CAN SEE. Counts, trips and holds are stored rows, the same from every process. The interpreter mode and a
sentinel's counters belong to each process: the report prints its own, labelled 'this process', and checks neither as the
installation's. A one-shot runs with the interpreter disabled unless it is given a mode (FINAL 13), so the installer reads
the worker's configured mode from the worker itself; a web or worker process that could not count records that on its
first read or write (sentinel.observe, sentinel.gate), and the trips show it here.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.utils import timezone

from studio import interpretation
from studio.interpretation import holds, sentinel
from studio.models import (Assessment, AuditEvent, EncounterContext, EventInventory, InterpreterHold,
                           InterpreterHoldRelease, ProviderRun)

SENTINEL_KEYS = ('legacy_calls', 'scope', 'tool', 'deny_size', 'positive_control')
RECORD_KEYS = ('engine_version', 'interpretation_version', 'inventory_version', 'inventory', 'gemini_run', 'context',
               'member_date_state', 'sentinel')
USAGE_KEYS = ('promptTokenCount', 'candidatesTokenCount', 'thoughtsTokenCount', 'totalTokenCount',
              'cachedContentTokenCount', 'toolUsePromptTokenCount')
# Every field of the window report, in the order ``render`` prints them (each is printed once, with its value).
D22_FIELDS = (
    'window',
    'interpreter mode (this process)',
    'model',
    'gemini runs',
    'gemini runs by state',
    'gemini runs by requested model',
    'gemini runs by returned model',
    'gemini runs paused',
    'gemini usage',
    'gemini estimated cost',
    'event inventories by state',
    'assessments by engine version',
    'new-path assessments',
    'legacy-engine assessments',
    'new-path assessments without an inventory',
    'new-path assessments without a sentinel record',
    'new-path records off their pins',
    'new-path records with problems',
    'sentinel legacy calls recorded',
    'sentinel trips',
    'sentinel unavailable in a process',
    'sentinel install',
    'sentinel deny-set size',
    'sentinel positive control',
    'sentinel totals',
    'sentinel residual legacy execution',
    'interpreter hold',
    'holds set',
    'hold releases',
)
SELF_TEST = ('sentinel installed', 'deny set as pinned', 'positive control', 'positive control trips', 'model constant',
             'no new-path legacy execution recorded', 'every new-path assessment carries its record',
             'no sentinel trip', 'no legacy-engine assessment')
# The model constant as D13 and FINAL 5.4 state it, written out: the self-test compares the code's constants with these,
# never with each other (interpretation.MODEL, adapter.MODEL and adapter.ENDPOINT are one value).
D13_MODEL = 'gemini-4-argon'
FINAL_ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent'
MAX_PROBLEMS = 10  # distinct record problems the report names (the count is complete)


# --- the record (FINAL 4.2) -------------------------------------------------------------------------------------------------

def interpretation_record(*, inventory, context, member_date_state, sentinel_record) -> dict:
    """Assessment.interpretation for a new-path assessment made from ``inventory`` (a 'read' EventInventory) through
    ``context`` (the gemini context derived from it): the D22 operator record (FINAL 4.2). ``member_date_state``: the
    contract 8.2 row the context's date came from (CPT Studio's own value, never model text); ``sentinel_record``:
    sentinel.record() of the scope the assessment was made in. Raises ValueError on anything else, so a record that
    would not say what made the assessment is never written."""
    if not isinstance(inventory, EventInventory) or inventory.pk is None or inventory.state != EventInventory.READ:
        raise ValueError('A new-path assessment is made from a stored event inventory that was read.')
    if not isinstance(context, EncounterContext) or not interpretation.is_new_context(context):
        raise ValueError('A new-path assessment is made through a context derived from an event inventory.')
    if context.event_inventory_id != inventory.pk or context.revision_id != inventory.revision_id:
        raise ValueError('The context was not derived from this inventory.')
    try:
        json.dumps(member_date_state, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError('member_date_state is recorded as JSON.') from None
    if not isinstance(sentinel_record, dict) or tuple(sorted(sentinel_record)) != tuple(sorted(SENTINEL_KEYS)):
        raise ValueError(f'The sentinel record has exactly {", ".join(SENTINEL_KEYS)}.')
    return {'engine_version': interpretation.ENGINE_VERSION,
            'interpretation_version': inventory.interpretation_version,
            'inventory_version': inventory.inventory_version,
            'inventory': {'id': str(inventory.pk), 'sha256': inventory.sha256},
            'gemini_run': str(inventory.provider_run_id),
            'context': str(context.pk),
            'member_date_state': member_date_state,
            'sentinel': {key: sentinel_record[key] for key in SENTINEL_KEYS}}


_STORED = ('sha256', 'provider_run_id', 'interpretation_version', 'inventory_version')


def record_problems(assessment, *, calls: bool = True) -> list:
    """What is wrong with a new-path assessment's stored record, in CPT Studio's words ([] when nothing is): a missing or
    misshapen record, one that disagrees with the assessment's own inventory, run or context, or a sentinel record that
    counts legacy executions (unless ``calls`` is False: the D22 self-test checks those apart), names another tool or
    deny set, or a positive control that did not pass."""
    stored = None
    if assessment.event_inventory_id is not None:
        stored = EventInventory.objects.filter(pk=assessment.event_inventory_id).values(*_STORED).first()
    return _record_problems(assessment.interpretation, assessment.event_inventory_id, assessment.context_id, stored,
                            calls=calls)


def _record_problems(record, event_inventory_id, context_id, stored: Optional[dict], *, calls: bool) -> list:
    """record_problems over stored values: the record, the assessment's inventory and context ids, and that inventory's
    stored _STORED values (None when it is not stored)."""
    if not isinstance(record, dict):
        return ['The assessment carries no interpretation record.']
    problems = []
    missing = [key for key in RECORD_KEYS if key not in record]
    if missing:
        problems.append(f'The interpretation record lacks {", ".join(missing)}.')
    inventory = record.get('inventory') if isinstance(record.get('inventory'), dict) else {}
    if event_inventory_id is None:
        problems.append('The assessment names no event inventory.')
    elif inventory.get('id') != str(event_inventory_id):
        problems.append('The record names another inventory than the assessment does.')
    elif stored is None or stored['sha256'] != inventory.get('sha256'):
        problems.append('The record\'s inventory sha256 is not the stored inventory\'s.')
    elif record.get('gemini_run') != str(stored['provider_run_id']):
        problems.append('The record names another run than the inventory was read from.')
    elif (record.get('interpretation_version'), record.get('inventory_version')) != (
            stored['interpretation_version'], stored['inventory_version']):
        problems.append('The record\'s versions are not the inventory\'s.')
    if record.get('context') != str(context_id):
        problems.append('The record names another context than the assessment does.')
    problems += sentinel_problems(record.get('sentinel'), calls=calls)
    return problems


def sentinel_problems(found, *, calls: bool = True) -> list:
    """What a recorded sentinel record says is wrong ([] when nothing is). ``calls``: whether a counted legacy execution
    is one (a count that is not a count always is)."""
    if not isinstance(found, dict) or tuple(sorted(found)) != tuple(sorted(SENTINEL_KEYS)):
        return ['The assessment carries no sentinel record.']
    problems = []
    counted = found['legacy_calls']
    if type(counted) is not int or counted < 0:
        problems.append(f'The sentinel record counts legacy executions as {counted!r}, which is not a count.')
    elif calls and counted != 0:
        problems.append(f'The sentinel counted {counted} legacy executions while the assessment was made.')
    if found['tool'] != sentinel.TOOL:
        problems.append('The sentinel record names another tool.')
    if found['deny_size'] != sentinel.DENY_SIZE:
        problems.append(f'The sentinel record names a deny set of {found["deny_size"]}, not {sentinel.DENY_SIZE}.')
    if found['positive_control'] != 'ok':
        problems.append('The sentinel\'s positive control had not passed.')
    return problems


# --- the operator's section of one assessment (detail, trace, report) --------------------------------------------------------

def interpretation_section(assessment) -> dict:
    """The operator's interpretation section of ``assessment`` (FINAL 3.1, 8.3): for a new-path assessment its record and
    what is wrong with it, the event inventory it was made from (versions, hashes, state, the stored events and the
    verification report), the Gemini run that inventory was read from (state, models, usage and estimated cost) and the
    hold that run set, if any; for a legacy assessment only that it is one. Stored rows only: nothing is re-read."""
    if not interpretation.is_new_assessment(assessment):
        return {'engine': 'legacy', 'engine_version': assessment.engine_version, 'record': None}
    inventory = (EventInventory.objects.select_related('provider_run').filter(pk=assessment.event_inventory_id).first()
                 if assessment.event_inventory_id else None)
    run = inventory.provider_run if inventory is not None else None
    hold = InterpreterHold.objects.filter(run=run).order_by('created_at', 'pk').first() if run is not None else None
    return {'engine': 'events', 'engine_version': assessment.engine_version,
            'record': assessment.interpretation, 'problems': record_problems(assessment),
            'inventory': _inventory_json(inventory) if inventory is not None else None,
            'run': run_json(run) if run is not None else None,
            'hold': holds.as_json(hold) if hold is not None else None}


def _inventory_json(inventory) -> dict:
    events = inventory.events if isinstance(inventory.events, dict) else {}
    return {'id': str(inventory.pk), 'state': inventory.state,
            'interpretation_version': inventory.interpretation_version,
            'inventory_version': inventory.inventory_version, 'sha256': inventory.sha256,
            'text_sha256': inventory.text_sha256, 'request_sha256': inventory.request_sha256,
            'response_sha256': inventory.response_sha256, 'created_at': inventory.created_at.isoformat(),
            'counts': {part: len(events.get(part) or ()) for part in ('passages', 'lesions', 'events', 'relations')},
            'events': inventory.events, 'encounter_facts': inventory.encounter_facts,
            'open_questions': inventory.open_questions, 'verification': inventory.verification}


def run_json(run) -> dict:
    """One Gemini run as the operator reads it: what was asked and what answered, the outcome, the usage as reported and
    its estimated cost. Never the request body, the response bytes or a key (none is ever stored)."""
    return {'id': str(run.pk), 'provider': run.provider, 'purpose': run.purpose, 'state': run.state, 'sent': run.sent,
            'http_status': run.http_status, 'requested_model': run.requested_model,
            'returned_model': run.returned_model, 'adapter_version': run.adapter_version,
            'request_sha256': run.request_sha256, 'response_sha256': run.response_sha256,
            'usage': dict(run.usage or {}), 'estimated_cost': estimated_cost(run.requested_model, run.usage,
                                                                             run.started_at, sent=run.sent,
                                                                             reused=run.reused_from_id is not None),
            'reused_from': str(run.reused_from_id) if run.reused_from_id else None,
            'started_at': run.started_at.isoformat() if run.started_at else None,
            'finished_at': run.finished_at.isoformat() if run.finished_at else None, 'latency_ms': run.latency_ms}


def estimated_cost(requested_model, usage, started_at, *, sent=True, reused=False) -> Optional[str]:
    """participants.pricing's estimate in USD as text, at the rate of the day the request was sent; None for a run that
    was not sent, a reuse (no new usage), a run that reported no usage, or a usage pricing cannot price."""
    if not sent or reused or not isinstance(usage, dict) or not usage:
        return None
    from studio.participants import pricing

    found = pricing.estimate(requested_model or interpretation.MODEL, dict(usage), on=started_at)
    return found['estimated_usd'] if found else None


# --- the D22 window report ----------------------------------------------------------------------------------------------

def window(since: datetime, until: Optional[datetime] = None) -> dict:
    """The D22 window report for [since, until) (until: now). Both are timezone-aware."""
    until = until or timezone.now()
    _check_window(since, until)
    span = {'created_at__gte': since, 'created_at__lt': until}
    return {'window': {'since': since.isoformat(), 'until': until.isoformat()},
            'interpreter': {'process_mode': holds.mode(), 'model': interpretation.MODEL,
                            'provider': interpretation.PROVIDER,
                            'adapter_version': interpretation.ADAPTER_VERSION,
                            'interpretation_version': interpretation.INTERPRETATION_VERSION,
                            'inventory_version': interpretation.INVENTORY_VERSION,
                            'engine_version': interpretation.ENGINE_VERSION},
            'gemini_runs': _runs(span),
            'inventories': dict(sorted(Counter(EventInventory.objects.filter(**span)
                                               .values_list('state', flat=True)).items())),
            'assessments': _assessments(span),
            'trips': _trips(span),
            'sentinel': {**sentinel.status(), 'totals': sentinel.totals(),
                         'residual': sentinel.top(sentinel.LEGACY_RECORD)},
            'hold': {**holds.state(),
                     'set': dict(sorted(Counter(InterpreterHold.objects.filter(**span)
                                                .values_list('reason', flat=True)).items())),
                     'released': [{'id': str(item['id']), 'hold': str(item['hold_id']),
                                   'by': item['released_by__username'], 'at': item['created_at'].isoformat()}
                                  for item in InterpreterHoldRelease.objects.filter(**span).order_by('created_at', 'pk')
                                  .values('id', 'hold_id', 'released_by__username', 'created_at')]}}


def _check_window(since, until):
    for name, value in (('since', since), ('until', until)):
        if not isinstance(value, datetime) or timezone.is_naive(value):
            raise ValueError(f'The window\'s {name} is a timezone-aware date and time.')
    if until <= since:
        raise ValueError('The window ends after it starts.')


def _runs(span: dict) -> dict:
    rows = list(ProviderRun.objects.filter(provider=interpretation.PROVIDER, **span).values(
        'state', 'requested_model', 'returned_model', 'usage', 'sent', 'reused_from_id', 'scope', 'started_at'))
    usage, cost, priced, unpriced = Counter(), Decimal('0'), 0, 0
    for row in rows:
        reported = row['usage'] if isinstance(row['usage'], dict) else {}
        for key in USAGE_KEYS:
            value = reported.get(key)
            if type(value) is int and value >= 0:
                usage[key] += value
        if not row['sent'] or row['reused_from_id'] is not None:
            continue
        found = estimated_cost(row['requested_model'], reported, row['started_at'])
        try:
            cost += Decimal(found) if found is not None else Decimal('0')
        except InvalidOperation:
            found = None
        priced, unpriced = (priced + 1, unpriced) if found is not None else (priced, unpriced + 1)
    paused = Counter((row['scope'] if isinstance(row['scope'], dict) else {}).get('held') or 'other'
                     for row in rows if row['state'] == ProviderRun.NOT_SENT)
    return {'total': len(rows),
            'by_state': dict(sorted(Counter(row['state'] for row in rows).items())),
            'requested_models': dict(sorted(Counter(row['requested_model'] or '(none)' for row in rows).items())),
            'returned_models': dict(sorted(Counter(row['returned_model'] or '(none)' for row in rows).items())),
            'paused': dict(sorted(paused.items())),
            'sent': sum(1 for row in rows if row['sent']),
            'reused': sum(1 for row in rows if row['reused_from_id'] is not None),
            'usage': {key: usage[key] for key in USAGE_KEYS},
            'cost': {'estimated_usd': f'{cost:f}', 'priced_runs': priced, 'unpriced_runs': unpriced,
                     'basis': _pricing_basis()}}


def _pricing_basis() -> str:
    from studio.participants import pricing

    return pricing.GEMINI_BASIS


def _assessments(span: dict) -> dict:
    rows = list(Assessment.objects.filter(**span).values('engine_version', 'event_inventory_id', 'context_id',
                                                         'interpretation'))
    new = [row for row in rows if _is_new(row['engine_version'])]
    records = [row['interpretation'].get('sentinel') if isinstance(row['interpretation'], dict) else None
               for row in new]
    complete = [found for found in records if not sentinel_problems_shape(found)]
    calls = sum(found['legacy_calls'] for found in complete)
    off_pins = sum(1 for found in complete if (found['tool'], found['deny_size'], found['positive_control'])
                   != (sentinel.TOOL, sentinel.DENY_SIZE, 'ok'))
    # every new-path record read as record_problems reads one, without its legacy-call count (checked apart)
    ids = {row['event_inventory_id'] for row in new if row['event_inventory_id'] is not None}
    stored = {row['id']: row for row in EventInventory.objects.filter(pk__in=ids).values('id', *_STORED)}
    problems, with_problems = Counter(), 0
    for row in new:
        found = _record_problems(row['interpretation'], row['event_inventory_id'], row['context_id'],
                                 stored.get(row['event_inventory_id']), calls=False)
        with_problems += bool(found)
        problems.update(found)
    return {'total': len(rows),
            'by_engine_version': dict(sorted(Counter(row['engine_version'] for row in rows).items())),
            'new_path': len(new), 'legacy_engine': len(rows) - len(new),
            'without_inventory': sum(1 for row in new if row['event_inventory_id'] is None),
            'without_sentinel_record': len(new) - len(complete),
            'off_pins': off_pins,
            'with_record_problems': with_problems,
            'record_problems': dict(problems.most_common(MAX_PROBLEMS)),
            'legacy_calls': calls,
            'with_legacy_calls': sum(1 for found in complete if found['legacy_calls'] != 0),
            'deny_sizes': dict(sorted(Counter(str(found['deny_size']) for found in complete).items())),
            'positive_controls': dict(sorted(Counter(str(found['positive_control']) for found in complete).items())),
            'tools': dict(sorted(Counter(str(found['tool']) for found in complete).items()))}


def sentinel_problems_shape(found) -> bool:
    """Whether a recorded sentinel record is missing or misshapen: not exactly SENTINEL_KEYS, or a legacy_calls that is
    not a count (its values are judged by sentinel_problems)."""
    if not isinstance(found, dict) or tuple(sorted(found)) != tuple(sorted(SENTINEL_KEYS)):
        return True
    calls = found['legacy_calls']
    return type(calls) is not int or calls < 0


def _is_new(engine_version) -> bool:
    return interpretation.is_new_assessment(_Engine(engine_version))


class _Engine:
    __slots__ = ('engine_version',)

    def __init__(self, engine_version):
        self.engine_version = engine_version


def _trips(span: dict) -> dict:
    rows = [data if isinstance(data, dict) else {} for data in
            AuditEvent.objects.filter(event=sentinel.TRIPPED, **span).values_list('data', flat=True)]
    # FINAL 10.2: a process that could not count records it (a refused write, or once per process on a read)
    unavailable = [data for data in rows if data.get('reason') == 'unavailable']
    return {'total': len(rows), 'refused': sum(1 for data in rows if data.get('refused') is True),
            'recorded': sum(1 for data in rows if data.get('refused') is not True),
            'by_reason': dict(sorted(Counter(str(data.get('reason', '')) for data in rows).items())),
            'by_entry': dict(sorted(Counter(str(data.get('entry', '')) for data in rows).items())),
            'unavailable': {'total': len(unavailable),
                            'refused': sum(1 for data in unavailable if data.get('refused') is True),
                            'recorded': sum(1 for data in unavailable if data.get('refused') is not True),
                            'install': dict(sorted(Counter(str(data.get('install', '')) for data in unavailable)
                                                   .items()))}}


# --- the self-test (FINAL 13) --------------------------------------------------------------------------------------------

def self_test(report: dict) -> dict:
    """The installer's verify checks over a window report from this process (``window``): {'passed', 'checks': [{name,
    ok, detail}]}, one per SELF_TEST name. Nothing here checks the interpreter mode: a one-shot's is its own, never the
    worker's, so the installer reads the worker's configured mode from the worker."""
    found = report['sentinel']
    assessments, trips = report['assessments'], report['trips']
    trip = sentinel.trip_test()
    from studio.interpretation import adapter

    constants = {'interpretation.MODEL': interpretation.MODEL, 'adapter.MODEL': adapter.MODEL,
                 'adapter.ENDPOINT': adapter.ENDPOINT}
    expected = {'interpretation.MODEL': D13_MODEL, 'adapter.MODEL': D13_MODEL, 'adapter.ENDPOINT': FINAL_ENDPOINT}
    wrong = [name for name, value in constants.items() if value != expected[name]]
    checks = [
        ('sentinel installed', found['state'] == 'ok', found['reason'] or found['state']),
        ('deny set as pinned', found['deny_size'] == sentinel.DENY_SIZE and found['sizes'] == sentinel.PINNED_SIZES,
         f'{found["deny_size"]} code objects, pinned {sentinel.DENY_SIZE}'),
        ('positive control', found['positive_control'] == 'ok', found['positive_control']),
        ('positive control trips', trip['ok'],
         f'a probe execution in a new_path scope was counted {trip["counted"]} time(s) and '
         f'{"refused" if trip["tripped"] else "NOT refused"}; a clean scope was '
         f'{"not refused" if trip["clean"] else "REFUSED"}'),
        ('model constant', not wrong,
         f'{interpretation.MODEL}, D13 says {D13_MODEL}' + (f'; {", ".join(wrong)} differ' if wrong else '')),
        ('no new-path legacy execution recorded', assessments['legacy_calls'] == 0,
         f'{assessments["legacy_calls"]} legacy executions over {assessments["new_path"]} new-path assessments'),
        ('every new-path assessment carries its record', assessments['with_record_problems'] == 0,
         f'{assessments["with_record_problems"]} of {assessments["new_path"]} with a problem in their record '
         f'({assessments["without_inventory"]} without an inventory, {assessments["without_sentinel_record"]} without '
         f'a sentinel record, {assessments["off_pins"]} off their pins)'),
        ('no sentinel trip', trips['total'] == 0,
         f'{trips["total"]} recorded, {trips["unavailable"]["total"]} of them a process that could not count'),
        ('no legacy-engine assessment', assessments['legacy_engine'] == 0,
         f'{assessments["legacy_engine"]} in the window'),
    ]
    return {'passed': all(ok for _, ok, _ in checks),
            'checks': [{'name': name, 'ok': bool(ok), 'detail': detail} for name, ok, detail in checks]}


# --- the text -------------------------------------------------------------------------------------------------------------

def render(report: dict, test: Optional[dict] = None) -> list:
    """The report (and the self-test) as text lines, one 'field: value' line per D22 field, in D22_FIELDS' order."""
    runs, assessments, found, hold = report['gemini_runs'], report['assessments'], report['sentinel'], report['hold']
    standing, unavailable = hold['standing'], report['trips']['unavailable']
    values = {
        'window': f'{report["window"]["since"]} to {report["window"]["until"]}',
        'interpreter mode (this process)': (f'{report["interpreter"]["process_mode"]}; this process\'s own setting - a '
                                            'one-shot runs with the interpreter disabled unless it is given a mode, '
                                            'and the worker\'s own setting decides for the worker'),
        'model': f'{report["interpreter"]["model"]} (asked by URL; an answer naming another is held)',
        'gemini runs': f'{runs["total"]} ({runs["sent"]} sent, {runs["reused"]} reused)',
        'gemini runs by state': _pairs(runs['by_state']),
        'gemini runs by requested model': _pairs(runs['requested_models']),
        'gemini runs by returned model': _pairs(runs['returned_models']),
        'gemini runs paused': _pairs(runs['paused']),
        'gemini usage': _pairs(runs['usage']),
        'gemini estimated cost': (f'USD {runs["cost"]["estimated_usd"]} over {_count(runs["cost"]["priced_runs"], "priced run")}'
                                  f' ({_count(runs["cost"]["unpriced_runs"], "sent run")} not priced); '
                                  f'{runs["cost"]["basis"]}'),
        'event inventories by state': _pairs(report['inventories']),
        'assessments by engine version': _pairs(assessments['by_engine_version']),
        'new-path assessments': str(assessments['new_path']),
        'legacy-engine assessments': str(assessments['legacy_engine']),
        'new-path assessments without an inventory': str(assessments['without_inventory']),
        'new-path assessments without a sentinel record': str(assessments['without_sentinel_record']),
        'new-path records off their pins': (f'{assessments["off_pins"]} (another tool, deny set or a positive control '
                                            'that had not passed)'),
        'new-path records with problems': (f'{assessments["with_record_problems"]}' + (
            ' (' + '; '.join(f'{sentence} x{n}' for sentence, n in assessments['record_problems'].items()) + ')'
            if assessments['record_problems'] else '')),
        'sentinel legacy calls recorded': (f'{assessments["legacy_calls"]} over {assessments["new_path"]} new-path '
                                           f'assessments ({assessments["with_legacy_calls"]} with any); deny sizes '
                                           f'{_pairs(assessments["deny_sizes"])}; positive controls '
                                           f'{_pairs(assessments["positive_controls"])}; tools '
                                           f'{_pairs(assessments["tools"])}'),
        'sentinel trips': (f'{report["trips"]["total"]} ({report["trips"]["refused"]} refused writes, '
                           f'{report["trips"]["recorded"]} recorded reads); by reason {_pairs(report["trips"]["by_reason"])}'
                           f'; by entry {_pairs(report["trips"]["by_entry"])}'),
        'sentinel unavailable in a process': (
            f'{unavailable["total"]} recorded by a process whose sentinel could not count ({unavailable["refused"]} '
            f'refused writes, {unavailable["recorded"]} reads); '
            + ('; '.join(f'{reason} x{n}' for reason, n in unavailable['install'].items()) or 'none')),
        'sentinel install': (f'{found["state"]}' + (f' ({found["reason"]})' if found['reason'] else '')
                             + f'; {found["tool"]} tool {found["tool_id"]} ({found["tool_name"]}); Python '
                               f'{found["python"]}; this process'),
        'sentinel deny-set size': (f'{found["deny_size"]} code objects (pinned {found["pinned_deny_size"]}; '
                                   f'{found["checks_denied"]} checks functions; {found["caches"]} caches)'),
        'sentinel positive control': found['positive_control'],
        'sentinel totals': _pairs(found['totals']) + '; this process',
        'sentinel residual legacy execution': ('; '.join(found['residual']) or 'none') + '; this process',
        'interpreter hold': (('; '.join(f'{item["reason"]} set {item["set_at"]} by run {item["run"]} (HTTP '
                                        f'{item["http_status"]}, {item["vendor_status"] or "no vendor status"})'
                                        for item in standing) or 'none standing') + '; installation-wide'),
        'holds set': _pairs(hold['set']),
        'hold releases': ('; '.join(f'hold {item["hold"]} by {item["by"]} at {item["at"]}' for item in hold['released'])
                          or 'none'),
    }
    lines = [f'{field}: {value}' for field, value in values.items()]
    if test is not None:
        lines += [f'self-test {item["name"]}: {"PASS" if item["ok"] else "FAIL"} ({item["detail"]})'
                  for item in test['checks']]
        lines.append(f'self-test: {"PASSED" if test["passed"] else "FAILED"}')
    return lines


def _count(n: int, noun: str) -> str:
    return f'{n} {noun}{"" if n == 1 else "s"}'


def _pairs(mapping: dict) -> str:
    return ', '.join(f'{key} {value}' for key, value in mapping.items()) or 'none'
