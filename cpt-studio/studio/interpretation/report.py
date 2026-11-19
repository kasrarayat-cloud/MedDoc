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

DESIGN V2 (docs/gemini-migration/FINAL-V2.md 5.7 measure 9, 6.2, 7.4; AMENDMENT-1 9.2; step 5c of its 8.1). A
cpt-studio-events@2 assessment is made from an inventory settled from TWO Gemini runs - pass 1 (purpose interpretation)
and the appraisal (pass 2, purpose appraisal) - so its record (``interpretation_record`` dispatches by the inventory's
versions, store.READ_VERSIONS) names both (``appraisal_run`` beside ``gemini_run``) and its sentinel record carries
``retired_calls`` (the RETIRED kind of 5.7 measure 1, which step 6a arms: None in a process whose sentinel does not
count it, and record_problems names that as a problem, so the self-test fails until it does). The operator's section of
a v2 assessment shows both runs with their usage and estimated cost, their sums, every Gemini run of the encounter by
purpose and its sums (AMENDMENT-1 9.2: "the operator report sums them per encounter"), and the inventory's appraisal
health and coherence (verification.health, verification.coherence). The window report adds the runs and usage by
purpose, the v2 inventories' health and coherence sums, the appraisals refused as unhealthy (an appraisal run whose
scope records a refused health), and the retired calls the v2 records count; a cpt-studio-events@1 assessment is a v1
row (FINAL-V2 6.2: a test instance's), counted apart and, like a legacy-engine one, failing the self-test's
'no legacy-engine assessment'; an assessment of a later events version (a later release's row after a switch-back) is
read by no rule of this release: counted apart again, its record a problem ('every new-path assessment carries its
record' fails), never judged as v1's. The self-test's names are unchanged (ops/install.py reads them): its 'no new-path
legacy execution recorded' counts retired executions too.

WHAT A ONE-SHOT CAN SEE. Counts, trips and holds are stored rows, the same from every process. The interpreter mode and a
sentinel's counters belong to each process: the report prints its own, labelled 'this process', and checks neither as the
installation's. A one-shot runs with the interpreter disabled unless it is given a mode (FINAL 13), so the installer reads
the worker's configured mode from the worker itself; a web or worker process that could not count records that on its
first read or write (sentinel.observe, sentinel.gate), and the trips show it here.

AMENDMENT-2 (docs/gemini-migration/AMENDMENT-2.md section 9 and 8.1, adopted by DECISIONS D279: the interpreter is
Claude Fable 5.2, D275; step F5). Both passes are read by claude-fable-5-2 on the Anthropic Messages API, and an
installation may still hold Gemini's stored runs:
- the runs are the interpreter's of every provider of interpretation.READ_PROVIDERS ('anthropic', then 'gemini'),
  counted in the window, the encounter's sums and the appraisals, and shown by provider; the human labels read
  "interpreter runs", "interpreter usage" and "interpreter estimated cost". The stored record's key ``gemini_run``
  (RECORD_KEYS_V2) and the report's JSON key ``gemini_runs`` keep their names: the first is a stored record shape
  (renaming it needs a new record version), the second the installer's stored evidence, and each means "the
  interpreter's runs";
- each run is priced by the model its request named, ``pricing.estimate(run.requested_model, ...)``: a Fable run at
  claude-fable-5-2's undated rates (AMENDMENT-2 1.7), a Gemini run at its dated rates; with no fallback (DECISIONS D289,
  G2-05) a run that recorded no model is unpriced, never priced at another model's rates. A run with no usage (a Fable
  stream that never reached message_delta records none) is a sent run not priced, as is one whose usage has tokens no
  recorded rate covers (a 1-hour cache write, usage.iterations);
- the usage sums add Anthropic's counts beside Gemini's (ANTHROPIC_USAGE_KEYS: input, the cache write and its 5-minute
  and 1-hour parts, the cache read, output, and the thinking count, which the output includes and pricing never prices
  apart), so the cache read and write tokens and the thinking tokens are summed and shown;
- the self-test's 'model constant' compares interpretation.MODEL_V3, fable_adapter.MODEL and fable_adapter.ENDPOINT with
  the written-out D275_MODEL and D275_ENDPOINT, and the dormant Gemini adapter's interpretation.MODEL, adapter.MODEL and
  adapter.ENDPOINT with D13_MODEL and FINAL_ENDPOINT (kept for that adapter) - each with its literal, never with each
  other;
- 8.1's labels: every reader here accepts both families of design v2's engine (V2_ENGINES: cpt-studio-events@3 and @2;
  @2 rows are read as stored), and the record builder, a writer, names the engine that made the assessment: the label
  engine/assess stamps (assess.ENGINE_VERSION, read at call time), or the one its caller names. A record naming another
  engine than its assessment's own is a problem.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.utils import timezone  # type: ignore[import-untyped]  # Django ships no type stubs

from studio import interpretation
from studio.interpretation import holds, sentinel
from studio.models import (Assessment, AuditEvent, EncounterContext, EventInventory, InterpreterHold,
                           InterpreterHoldRelease, ProviderRun)

# design v2: the version pairs, engine and context this release reads (store.READ_VERSIONS; readers.READ_ENGINES and
# READ_CONTEXTS), named here as the record builder checks them; the purposes of the two Gemini runs.
V2_PURPOSES = (interpretation.PURPOSE, interpretation.APPRAISAL_PURPOSE)
# AMENDMENT-2 8.1: the engine versions of design v2 this release reads - AMENDMENT-2's, and the @2 rows, read as stored
V2_ENGINES = (interpretation.ENGINE_VERSION_V3, interpretation.ENGINE_VERSION_V2)

SENTINEL_KEYS = ('legacy_calls', 'scope', 'tool', 'deny_size', 'positive_control')
RECORD_KEYS = ('engine_version', 'interpretation_version', 'inventory_version', 'inventory', 'gemini_run', 'context',
               'member_date_state', 'sentinel')
# design v2 (FINAL-V2 5.7 measure 9): the record names both runs, and its sentinel record the retired calls too (None
# when this process's sentinel counts none: a problem, until step 6a arms the RETIRED kind); any further key a later
# sentinel records (its retired size, its second positive control) is kept as given.
RECORD_KEYS_V2 = ('engine_version', 'interpretation_version', 'inventory_version', 'inventory', 'gemini_run',
                  'appraisal_run', 'context', 'member_date_state', 'sentinel')
RETIRED_CALLS = 'retired_calls'
SENTINEL_KEYS_V2 = SENTINEL_KEYS + (RETIRED_CALLS,)
# The health measures and coherence outcomes a v2 inventory's verification report records (contract/settle.Health and
# Coherence, 1.7), summed by the window report.
HEALTH_MEASURES = ('pairs', 'not_rejected', 'claims', 'established', 'verdicts', 'missing')
COHERENCE_OUTCOMES = ('established', 'incoherent', 'uninformative', 'contradicted', 'qualified', 'unclear', 'detached',
                      'missing', 'control_missing')
# Gemini's usageMetadata counts, as its stored runs report them
USAGE_KEYS = ('promptTokenCount', 'candidatesTokenCount', 'thoughtsTokenCount', 'totalTokenCount',
              'cachedContentTokenCount', 'toolUsePromptTokenCount')
# AMENDMENT-2 E.1 and section 9: Anthropic's usage counts, as a Fable run reports them (a dotted key is a count inside a
# nested object): input (no cache tokens), the cache write with its 5-minute and 1-hour parts, the cache read, the
# output, and the thinking count inside it
ANTHROPIC_USAGE_KEYS = ('input_tokens', 'cache_creation_input_tokens', 'cache_creation.ephemeral_5m_input_tokens',
                        'cache_creation.ephemeral_1h_input_tokens', 'cache_read_input_tokens', 'output_tokens',
                        'output_tokens_details.thinking_tokens')
# every count the usage sums add up, Fable's first: a run's counts are those its provider reports, the others zero
SUMMED_KEYS = ANTHROPIC_USAGE_KEYS + USAGE_KEYS
# Every field of the window report, in the order ``render`` prints them (each is printed once, with its value).
D22_FIELDS = (
    'window',
    'interpreter mode (this process)',
    'model',
    'interpreter runs',
    'interpreter runs by state',
    'interpreter runs by requested model',
    'interpreter runs by returned model',
    'interpreter runs paused',
    'interpreter usage',
    'interpreter estimated cost',
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
    # design v2 (step 5c): both runs, their usage, the appraisal's health and coherence, the retired calls
    'interpreter runs by purpose',
    'interpreter usage by purpose',
    'interpreter estimated cost by purpose',
    'event inventories by version',
    'appraisal health',
    'appraisal coherence',
    'appraisals refused as unhealthy',
    'v1 assessments',
    'sentinel retired calls recorded',
)
SELF_TEST = ('sentinel installed', 'deny set as pinned', 'positive control', 'positive control trips', 'model constant',
             'no new-path legacy execution recorded', 'every new-path assessment carries its record',
             'no sentinel trip', 'no legacy-engine assessment')
# The model constant as D13 and FINAL 5.4 state it, as DECISIONS D230 sets it (gemini-4-carbon from 2026-11-13), written
# out: the self-test compares the code's constants with these, never with each other (interpretation.MODEL,
# adapter.MODEL and adapter.ENDPOINT are one value). Kept for the dormant Gemini adapter (AMENDMENT-2 section 9).
D13_MODEL = 'gemini-4-carbon'
FINAL_ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-4-carbon:generateContent'
# The interpreter's model and endpoint as DECISIONS D275 sets them (AMENDMENT-2 section 9), written out:
# interpretation.MODEL_V3, fable_adapter.MODEL and fable_adapter.ENDPOINT are compared with these, never with each
# other.
D275_MODEL = 'claude-fable-5-2'
D275_ENDPOINT = 'https://api.anthropic.com/v1/messages'
MAX_PROBLEMS = 10  # distinct record problems the report names (the count is complete)


# --- the record (FINAL 4.2) -------------------------------------------------------------------------------------------------

def interpretation_record(*, inventory: Any, context: Any, member_date_state: Any, sentinel_record: Any,
                          engine_version: Optional[str] = None) -> dict[str, Any]:
    """Assessment.interpretation for a new-path assessment made from ``inventory`` (a 'read' EventInventory) through
    ``context`` (the gemini context derived from it): the D22 operator record (FINAL 4.2). ``member_date_state``: the
    contract 8.2 row the context's date came from (CPT Studio's own value, never model text); ``sentinel_record``:
    sentinel.record() of the scope the assessment was made in. Raises ValueError on anything else, so a record that
    would not say what made the assessment is never written. A design v2 inventory (a version pair store.READ_VERSIONS
    lists) gets the v2 record (``interpretation_record_v2``, which takes ``engine_version``); a v1 record is v1's
    engine's, so any other ``engine_version`` is refused."""
    if is_v2_inventory(inventory):
        return interpretation_record_v2(inventory=inventory, context=context, member_date_state=member_date_state,
                                        sentinel_record=sentinel_record, engine_version=engine_version)
    if engine_version not in (None, interpretation.ENGINE_VERSION):
        raise ValueError('A v1 inventory\'s assessment is made by the v1 events engine.')
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
_STORED_V2 = _STORED + ('appraisal_run_id',)


# --- design v2's record (FINAL-V2 5.7 measure 9; step 5c) -------------------------------------------------------------

def is_v2_inventory(inventory: object) -> bool:
    """Whether ``inventory`` is a design v2 EventInventory: its version pair is one store.READ_VERSIONS lists."""
    from studio.interpretation import store

    return isinstance(inventory, EventInventory) and (
        inventory.interpretation_version, inventory.inventory_version) in store.READ_VERSIONS


def is_v2_assessment(engine_version: object) -> bool:
    """Whether an assessment's engine version is one design v2's reader reads: AMENDMENT-2's or design v2's own
    (V2_ENGINES; AMENDMENT-2 8.1: every reader of a stored row accepts both families)."""
    return isinstance(engine_version, str) and engine_version in V2_ENGINES


def _unread_events(engine_version: object) -> bool:
    """A new-path assessment of an events version this release neither reads (v2) nor reads as stored (v1): a later
    release's row (after a switch-back, FINAL-V2 6.4), which no rule of this release judges."""
    return (_is_new(engine_version) and not is_v2_assessment(engine_version)
            and engine_version != interpretation.ENGINE_VERSION)


def _unread_problem(engine_version: object) -> str:
    return f'The assessment was made at {engine_version}, an events version this release does not read.'


def _current_engine() -> str:
    """The engine label design v2's engine stamps on every assessment it makes (engine/assess.ENGINE_VERSION, the
    result's engine_version that persist_assessment stores), read at call time: AMENDMENT-2 8.1's writers write the
    current label, so a record names the engine that made its assessment whatever version the engine is at."""
    from studio.interpretation.engine import assess

    return str(assess.ENGINE_VERSION)


def interpretation_record_v2(*, inventory: Any, context: Any, member_date_state: Any, sentinel_record: Any,
                             engine_version: Optional[str] = None) -> dict[str, Any]:
    """Assessment.interpretation for a design v2 assessment (FINAL-V2 5.7 measure 9): made from ``inventory`` (a 'read'
    v2 EventInventory, settled from pass 1's run and the appraisal run) through ``context`` (the gemini-context@2
    derived from it) by the engine ``engine_version`` names (by default the engine's own label, _current_engine; one of
    V2_ENGINES). Both runs are named, and the sentinel record carries the retired calls (None when the sentinel that
    made it counts none; any further key it records is kept). ValueError on anything else."""
    engine = _current_engine() if engine_version is None else engine_version
    if not is_v2_assessment(engine):
        raise ValueError(f'A design v2 assessment is made by an engine this release reads ({", ".join(V2_ENGINES)}).')
    if not is_v2_inventory(inventory) or inventory.pk is None or inventory.state != EventInventory.READ:
        raise ValueError('A design v2 assessment is made from a stored v2 event inventory that was read.')
    if inventory.appraisal_run_id is None:
        raise ValueError('A design v2 inventory that was read names its appraisal run.')
    if not isinstance(context, EncounterContext) or context.version != interpretation.CONTEXT_VERSION_V2:
        raise ValueError('A design v2 assessment is made through a context derived from its inventory.')
    if context.event_inventory_id != inventory.pk or context.revision_id != inventory.revision_id:
        raise ValueError('The context was not derived from this inventory.')
    try:
        json.dumps(member_date_state, allow_nan=False)
        json.dumps(sentinel_record, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError('member_date_state and the sentinel record are recorded as JSON.') from None
    if not isinstance(sentinel_record, dict) or not set(SENTINEL_KEYS) <= set(sentinel_record):
        raise ValueError(f'The sentinel record has at least {", ".join(SENTINEL_KEYS)}.')
    found = {key: sentinel_record[key] for key in SENTINEL_KEYS}
    found[RETIRED_CALLS] = sentinel_record.get(RETIRED_CALLS)
    found.update({key: value for key, value in sentinel_record.items() if key not in found})
    return {'engine_version': engine,
            'interpretation_version': inventory.interpretation_version,
            'inventory_version': inventory.inventory_version,
            'inventory': {'id': str(inventory.pk), 'sha256': inventory.sha256},
            'gemini_run': str(inventory.provider_run_id),
            'appraisal_run': str(inventory.appraisal_run_id),
            'context': str(context.pk),
            'member_date_state': member_date_state,
            'sentinel': found}


def record_problems(assessment: Any, *, calls: bool = True) -> list[str]:
    """What is wrong with a new-path assessment's stored record, in CPT Studio's words ([] when nothing is): a missing or
    misshapen record, one that disagrees with the assessment's own inventory, run or context, or a sentinel record that
    counts legacy executions (unless ``calls`` is False: the D22 self-test checks those apart), names another tool or
    deny set, or a positive control that did not pass. A design v2 assessment's record names both runs, the
    assessment's own engine and counts the retired calls (``_record_problems_v2``); one of an events version this
    release does not read has that one problem, never v1's rules (``_unread_events``)."""
    if _unread_events(assessment.engine_version):
        return [_unread_problem(assessment.engine_version)]
    v2 = is_v2_assessment(assessment.engine_version)
    stored = None
    if assessment.event_inventory_id is not None:
        stored = EventInventory.objects.filter(pk=assessment.event_inventory_id).values(
            *(_STORED_V2 if v2 else _STORED)).first()
    if v2:
        return _record_problems_v2(assessment.interpretation, assessment.engine_version, assessment.event_inventory_id,
                                   assessment.context_id, stored, calls=calls)
    return _record_problems(assessment.interpretation, assessment.event_inventory_id, assessment.context_id, stored,
                            calls=calls)


def _record_problems_v2(record: object, engine_version: object, event_inventory_id: object, context_id: object,
                        stored: Optional[dict[str, Any]], *, calls: bool) -> list[str]:
    """record_problems over a design v2 assessment's stored values: v1's, with both runs named, the engine the
    assessment records (``engine_version``, its own column) and the retired calls counted (sentinel_problems_v2)."""
    if not isinstance(record, dict):
        return ['The assessment carries no interpretation record.']
    problems = []
    missing = [key for key in RECORD_KEYS_V2 if key not in record]
    if missing:
        problems.append(f'The interpretation record lacks {", ".join(missing)}.')
    if not is_v2_assessment(engine_version) or record.get('engine_version') != engine_version:
        problems.append('The interpretation record names another engine than the assessment was made by.')
    inventory = record.get('inventory') if isinstance(record.get('inventory'), dict) else {}
    assert isinstance(inventory, dict)
    if event_inventory_id is None:
        problems.append('The assessment names no event inventory.')
    elif inventory.get('id') != str(event_inventory_id):
        problems.append('The record names another inventory than the assessment does.')
    elif stored is None or stored['sha256'] != inventory.get('sha256'):
        problems.append('The record\'s inventory sha256 is not the stored inventory\'s.')
    else:
        if record.get('gemini_run') != str(stored['provider_run_id']):
            problems.append('The record names another run than the inventory was read from.')
        if stored['appraisal_run_id'] is None or record.get('appraisal_run') != str(stored['appraisal_run_id']):
            problems.append('The record names another appraisal run than the inventory was settled from.')
        if (record.get('interpretation_version'), record.get('inventory_version')) != (
                stored['interpretation_version'], stored['inventory_version']):
            problems.append('The record\'s versions are not the inventory\'s.')
    if record.get('context') != str(context_id):
        problems.append('The record names another context than the assessment does.')
    problems += sentinel_problems_v2(record.get('sentinel'), calls=calls)
    return problems


def sentinel_problems_v2(found: object, *, calls: bool = True) -> list[str]:
    """What a design v2 sentinel record says is wrong ([] when nothing is): v1's (sentinel_problems, over its five
    keys), and its retired calls - not counted at all (None: this process's sentinel does not count the retired
    modules), not a count, or (with ``calls``) any."""
    if not isinstance(found, dict) or not set(SENTINEL_KEYS_V2) <= set(found):
        return ['The assessment carries no sentinel record.']
    problems = sentinel_problems({key: found[key] for key in SENTINEL_KEYS}, calls=calls)
    retired = found[RETIRED_CALLS]
    if retired is None:
        problems.append('The sentinel record counts no retired executions: the sentinel that made it does not count '
                        'the retired modules.')
    elif type(retired) is not int or retired < 0:
        problems.append(f'The sentinel record counts retired executions as {retired!r}, which is not a count.')
    elif calls and retired != 0:
        problems.append(f'The sentinel counted {retired} retired executions while the assessment was made.')
    return problems


def _record_problems(record: object, event_inventory_id: object, context_id: object,
                     stored: Optional[dict[str, Any]], *, calls: bool) -> list[str]:
    """record_problems over stored values: the record, the assessment's inventory and context ids, and that inventory's
    stored _STORED values (None when it is not stored)."""
    if not isinstance(record, dict):
        return ['The assessment carries no interpretation record.']
    problems = []
    missing = [key for key in RECORD_KEYS if key not in record]
    if missing:
        problems.append(f'The interpretation record lacks {", ".join(missing)}.')
    inventory = record.get('inventory') if isinstance(record.get('inventory'), dict) else {}
    assert isinstance(inventory, dict)
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


def sentinel_problems(found: object, *, calls: bool = True) -> list[str]:
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

def interpretation_section(assessment: Any) -> dict[str, Any]:
    """The operator's interpretation section of ``assessment`` (FINAL 3.1, 8.3): for a new-path assessment its record and
    what is wrong with it, the event inventory it was made from (versions, hashes, state, the stored events and the
    verification report), the interpreter run that inventory was read from (state, models, usage and estimated cost)
    and the hold that run set, if any; for a legacy assessment only that it is one. Stored rows only: nothing is
    re-read. A design v2 assessment's section is ``interpretation_section_v2``'s; one of an events version this release
    does not read says so, its record shown as stored and nothing of it judged or loaded."""
    if not interpretation.is_new_assessment(assessment):
        return {'engine': 'legacy', 'engine_version': assessment.engine_version, 'record': None}
    if is_v2_assessment(assessment.engine_version):
        return interpretation_section_v2(assessment)
    if _unread_events(assessment.engine_version):
        return {'engine': 'events', 'engine_version': assessment.engine_version, 'record': assessment.interpretation,
                'problems': [_unread_problem(assessment.engine_version)], 'inventory': None, 'run': None,
                'hold': None}
    inventory = (EventInventory.objects.select_related('provider_run').filter(pk=assessment.event_inventory_id).first()
                 if assessment.event_inventory_id else None)
    run = inventory.provider_run if inventory is not None else None
    hold = InterpreterHold.objects.filter(run=run).order_by('created_at', 'pk').first() if run is not None else None
    return {'engine': 'events', 'engine_version': assessment.engine_version,
            'record': assessment.interpretation, 'problems': record_problems(assessment),
            'inventory': _inventory_json(inventory) if inventory is not None else None,
            'run': run_json(run) if run is not None else None,
            'hold': holds.as_json(hold) if hold is not None else None}


def _inventory_json(inventory: Any) -> dict[str, Any]:
    events = inventory.events if isinstance(inventory.events, dict) else {}
    return {'id': str(inventory.pk), 'state': inventory.state,
            'interpretation_version': inventory.interpretation_version,
            'inventory_version': inventory.inventory_version, 'sha256': inventory.sha256,
            'text_sha256': inventory.text_sha256, 'request_sha256': inventory.request_sha256,
            'response_sha256': inventory.response_sha256, 'created_at': inventory.created_at.isoformat(),
            'counts': {part: len(events.get(part) or ()) for part in ('passages', 'lesions', 'events', 'relations')},
            'events': inventory.events, 'encounter_facts': inventory.encounter_facts,
            'open_questions': inventory.open_questions, 'verification': inventory.verification}


def interpretation_section_v2(assessment: Any) -> dict[str, Any]:
    """The operator's interpretation section of a design v2 assessment (FINAL-V2 5.7 measure 9; AMENDMENT-1 9.2): its
    record and what is wrong with it; the inventory (versions, hashes, state, the stored events and the verification
    report, with its appraisal health and coherence); BOTH runs - ``run`` (pass 1, purpose interpretation) and
    ``appraisal_run`` (pass 2, purpose appraisal), each with its usage as reported and its estimated cost - and
    ``usage``, their sums; ``encounter_usage``, every interpreter run of the encounter by purpose with the sums (the
    actual cost of every update); and the holds the two runs set. Stored rows only: nothing is re-read."""
    inventory = (EventInventory.objects.select_related('provider_run', 'appraisal_run')
                 .filter(pk=assessment.event_inventory_id).first() if assessment.event_inventory_id else None)
    first = inventory.provider_run if inventory is not None else None
    second = inventory.appraisal_run if inventory is not None else None
    runs = [run for run in (first, second) if run is not None]
    hold = InterpreterHold.objects.filter(run__in=runs).order_by('created_at', 'pk').first() if runs else None
    holds_set = (list(InterpreterHold.objects.filter(run__in=runs).order_by('created_at', 'pk')) if runs else [])
    found = [run_json(run) for run in runs]
    return {'engine': 'events', 'engine_version': assessment.engine_version,
            'record': assessment.interpretation, 'problems': record_problems(assessment),
            'inventory': _inventory_json_v2(inventory) if inventory is not None else None,
            'run': run_json(first) if first is not None else None,
            'appraisal_run': run_json(second) if second is not None else None,
            'usage': usage_sums(found),
            'encounter_usage': encounter_usage(assessment.encounter_id),
            'hold': holds.as_json(hold) if hold is not None else None,
            'holds': [holds.as_json(item) for item in holds_set],
            'questions': question_section(inventory) if inventory is not None else None}


QUESTION_UNSET = 'none'  # what an operator's line says for an absent figure


def question_section(inventory: Any) -> Optional[dict[str, Any]]:
    """Round r3's part of the operator report (build-v2/a2b/r3 DESIGN-v2 (i); DECISIONS D320, D322) for a design v2
    inventory whose row records the question stage (events.questions, verification.question_runs; None for a row
    without one, as every row written before round r3 or whose round 1 asked nothing):
    - ``codes``: per code a question served - the witnesses the ESTABLISHED questions released, each with its question
      (family, form, subjects, attribute, value), the witness (fact, attribute, subject, cause, reason) and its
      located spans (the revision's offsets, and the revision's own words at them); and each unestablished question
      with its reasons;
    - ``requests``: each question request - its round, batch and run, its outcome, its claims, the request it halves,
      its health (the measures and what refused it), its output rate (a measure: below
      settings.QUESTION_RATE_FLOOR_TOKENS_PER_SECOND or not, never a hold), the worst case it was reserved at, and its
      usage and estimated cost (run_json);
    - ``calibration``: each calibration item with its verdicts and whether it breached;
    - ``usage``: the question runs' sums (usage_sums).
    Operator surface only (studio/serializers.py, the interpretation_report command): nothing here reaches a customer
    or a reviewer. Stored rows only; nothing is re-read but the revision text the spans name."""
    events = inventory.events if isinstance(inventory.events, dict) else {}
    verification = inventory.verification if isinstance(inventory.verification, dict) else {}
    records = [item for item in events.get('questions') or () if isinstance(item, dict)]
    named = [item for item in verification.get('question_runs') or () if isinstance(item, dict)]
    if not records and not named:
        return None
    text = getattr(getattr(inventory, 'revision', None), 'text', '') or ''
    health = {(item.get('round'), item.get('batch')): item for item in verification.get('question_health') or ()
              if isinstance(item, dict)}
    runs = {str(run.pk): run for run in ProviderRun.objects.filter(
        pk__in=[item.get('provider_run_id') for item in named if isinstance(item.get('provider_run_id'), str)])}
    codes: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        question = {key: record.get(key) for key in ('id', 'round', 'batch', 'family', 'form', 'subjects', 'attribute',
                                                      'value', 'negated', 'census')}
        established = record.get('result') == 'supported'
        spans = [{'start': span['start'], 'end': span['end'], 'words': text[span['start']:span['end']]}
                 for span in record.get('proof') or () if isinstance(span, dict)
                 and type(span.get('start')) is int and type(span.get('end')) is int]
        for witness in record.get('witnesses') or ():
            if not isinstance(witness, dict) or not isinstance(witness.get('code'), str):
                continue
            entry = codes.setdefault(witness['code'], {'released': [], 'unestablished': []})
            if established:
                entry['released'].append({'question': question, 'witness': {key: witness.get(key) for key in (
                    'fact', 'attribute', 'subject', 'cause', 'reason')}, 'spans': spans})
            else:
                entry['unestablished'].append({'question': question, 'reasons': list(record.get('reasons') or ())})
    requests = []
    for item in named:
        named_run = item.get('provider_run_id')
        run = runs.get(named_run) if isinstance(named_run, str) else None
        scope = ((run.scope or {}).get('question') or {}) if run is not None else {}
        measured = health.get((item.get('round'), item.get('batch')))
        requests.append({'round': item.get('round'), 'batch': item.get('batch'), 'run': item.get('provider_run_id'),
                         'outcome': item.get('outcome'), 'claims': item.get('claims'), 'split_of': item.get('split_of'),
                         'request_sha256': item.get('request_sha256'), 'response_sha256': item.get('response_sha256'),
                         'health': ({'measures': measured.get('measures'), 'refused': measured.get('refused')}
                                    if measured is not None else None),
                         'rate': scope.get('rate'), 'worst_case_usd': scope.get('worst_case_usd'),
                         'detail': run_json(run) if run is not None else None})
    calibration = [{key: item.get(key) for key in ('round', 'batch', 'kind', 'form', 'subjects', 'verdicts', 'breach')}
                   for item in events.get('calibration') or () if isinstance(item, dict)]
    return {'codes': dict(sorted(codes.items())), 'requests': requests, 'calibration': calibration,
            'established': sum(1 for record in records if record.get('result') == 'supported'),
            'asked': len(records),
            'usage': usage_sums([request['detail'] for request in requests if request['detail'] is not None])}


def render_questions(found: Optional[dict[str, Any]]) -> list[str]:
    """question_section as text lines for the operator (the interpretation_report command's encounter view)."""
    if not found:
        return []
    lines = [f'questions: {found["asked"]} asked, {found["established"]} established, '
             f'{_count(len(found["requests"]), "request")}']
    for request in found['requests']:
        refused = (request['health'] or {}).get('refused') or []
        rate = request['rate'] or {}
        lines.append(f'question request round {request["round"]} batch {request["batch"]}: run {request["run"]} '
                     f'outcome {request["outcome"]}, {request["claims"]} claims'
                     + (f', half of {request["split_of"][:16]}' if request['split_of'] else '')
                     + f'; refused {", ".join(refused) or QUESTION_UNSET}'
                     + (f'; {rate.get("tokens_per_second")} tokens a second'
                        + (' (below the floor: a measure)' if rate.get('below_floor') else '') if rate else ''))
    for code, entry in found['codes'].items():
        for item in entry['released']:
            words = '; '.join(f'[{span["start"]}, {span["end"]}] "{span["words"]}"' for span in item['spans'])
            lines.append(f'question code {code}: released {item["witness"]["fact"]} by {item["question"]["id"]} '
                         f'({item["question"]["family"]} {item["question"]["form"]}) at {words or QUESTION_UNSET}')
        for item in entry['unestablished']:
            lines.append(f'question code {code}: not established {item["question"]["id"]} '
                         f'({item["question"]["family"]} {item["question"]["form"]}): '
                         f'{", ".join(item["reasons"]) or QUESTION_UNSET}')
    for item in found['calibration']:
        lines.append(f'question calibration round {item["round"]} batch {item["batch"]} {item["kind"]} '
                     f'{item["form"]}: ' + ('BREACH' if item['breach'] else 'held'))
    return lines


def _inventory_json_v2(inventory: Any) -> dict[str, Any]:
    """A design v2 inventory as the operator reads it: its versions, hashes and state, the count of each object family
    it settled, the stored events and verification report, and the appraisal's health and coherence (1.7)."""
    events = inventory.events if isinstance(inventory.events, dict) else {}
    verification = inventory.verification if isinstance(inventory.verification, dict) else {}
    return {'id': str(inventory.pk), 'state': inventory.state,
            'interpretation_version': inventory.interpretation_version,
            'inventory_version': inventory.inventory_version, 'sha256': inventory.sha256,
            'text_sha256': inventory.text_sha256, 'request_sha256': inventory.request_sha256,
            'response_sha256': inventory.response_sha256,
            'appraisal_request_sha256': verification.get('appraisal_request_sha256'),
            'appraisal_response_sha256': verification.get('appraisal_response_sha256'),
            'claims_sha256': verification.get('claims_sha256'),
            'created_at': inventory.created_at.isoformat(),
            'counts': {part: len(events.get(part) or ()) for part in ('units', 'sections', 'sessions', 'anatomy',
                                                                      'lesions', 'events', 'doubts', 'claims',
                                                                      'unlisted')},
            'health': verification.get('health'), 'coherence': verification.get('coherence'),
            'events': inventory.events, 'verification': inventory.verification}


def usage_count(usage: object, key: str) -> Optional[int]:
    """The count ``key`` names in ``usage`` as reported - a dotted key names a count inside a nested object
    ('output_tokens_details.thinking_tokens') - when it is a whole number, zero or more; None otherwise (absent, null,
    or not a count)."""
    value: object = usage
    for part in key.split('.'):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value if type(value) is int and value >= 0 else None


def _add_usage(totals: Counter[str], usage: object) -> None:
    for key in SUMMED_KEYS:
        value = usage_count(usage, key)
        if value is not None:
            totals[key] += value


def usage_sums(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """The sums of ``runs`` (run_json's): each usage count of SUMMED_KEYS over the runs that were sent and are no reuse
    (a reuse reports no new usage), the estimated cost over the priced ones, and how many were priced and not."""
    usage: Counter[str] = Counter()
    cost, priced, unpriced = Decimal('0'), 0, 0
    for run in runs:
        if not run['sent'] or run['reused_from'] is not None:
            continue
        _add_usage(usage, run['usage'] or {})
        found = run['estimated_cost']
        try:
            cost += Decimal(found) if found is not None else Decimal('0')
        except InvalidOperation:
            found = None
        priced, unpriced = (priced + 1, unpriced) if found is not None else (priced, unpriced + 1)
    return {'runs': len(runs), 'usage': {key: usage[key] for key in SUMMED_KEYS},
            'estimated_usd': f'{cost:f}', 'priced_runs': priced, 'unpriced_runs': unpriced}


def encounter_usage(encounter_id: object) -> dict[str, Any]:
    """Every interpreter run of the encounter (interpretation.READ_PROVIDERS: Fable's, and Gemini's stored ones) by
    purpose (pass 1's interpretation, pass 2's appraisal, and any other), each purpose's usage_sums, and the sums over
    all of them (AMENDMENT-1 9.2: the actual cost of every update)."""
    runs = [run_json(run) for run in ProviderRun.objects.filter(encounter_id=encounter_id,
                                                                provider__in=interpretation.READ_PROVIDERS)
            .order_by('created_at', 'pk')]
    purposes = list(dict.fromkeys([*V2_PURPOSES, *(run['purpose'] for run in runs)]))
    return {'by_purpose': {purpose: usage_sums([run for run in runs if run['purpose'] == purpose])
                           for purpose in purposes},
            'total': usage_sums(runs)}


def run_json(run: Any) -> dict[str, Any]:
    """One interpreter run as the operator reads it: what was asked and what answered, the outcome, the usage as
    reported and its estimated cost. Never the request body, the response bytes or a key (none is ever stored)."""
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


def estimated_cost(requested_model: object, usage: object, started_at: object, *, sent: bool = True,
                   reused: bool = False) -> Optional[str]:
    """participants.pricing's estimate in USD as text, by the model the run's request named (``requested_model``:
    claude-fable-5-2's undated rates, a Gemini model's at the rate of the day the request was sent); None for a run
    that was not sent, a reuse (no new usage), a run that reported no usage, a usage pricing cannot price, and a run
    that recorded no model - never priced at another model's rates (DECISIONS D289, G2-05: no fallback)."""
    if not sent or reused or not isinstance(usage, dict) or not usage:
        return None
    if not isinstance(requested_model, str) or not requested_model:
        return None
    from studio.participants import pricing

    found = pricing.estimate(requested_model, dict(usage), on=started_at)
    return str(found['estimated_usd']) if found else None


# --- the D22 window report ----------------------------------------------------------------------------------------------

def window(since: datetime, until: Optional[datetime] = None) -> dict[str, Any]:
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
                            'engine_version': interpretation.ENGINE_VERSION,
                            # design v2: the labels this release writes (FINAL-V2 1.1)
                            'adapter_version_v2': interpretation.ADAPTER_VERSION_V2,
                            'interpretation_pair': interpretation.INTERPRETATION_PAIR,
                            'inventory_version_v2': interpretation.INVENTORY_VERSION_V2,
                            'engine_version_v2': interpretation.ENGINE_VERSION_V2,
                            # AMENDMENT-2 8.1: the labels the current path writes, beside the kept names
                            'model_v3': interpretation.MODEL_V3, 'provider_v3': interpretation.PROVIDER_V3,
                            'adapter_version_v3': interpretation.ADAPTER_VERSION_V3,
                            'interpretation_pair_v3': interpretation.INTERPRETATION_PAIR_V3,
                            'inventory_version_v3': interpretation.INVENTORY_VERSION_V3,
                            'engine_version_v3': interpretation.ENGINE_VERSION_V3,
                            'read_providers': list(interpretation.READ_PROVIDERS)},
            'gemini_runs': _runs(span),
            'inventories': dict(sorted(Counter(EventInventory.objects.filter(**span)
                                               .values_list('state', flat=True)).items())),
            'inventories_by_version': _inventory_versions(span),
            'appraisal': _appraisal(span),
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


def _check_window(since: object, until: object) -> None:
    for name, value in (('since', since), ('until', until)):
        if not isinstance(value, datetime) or timezone.is_naive(value):
            raise ValueError(f'The window\'s {name} is a timezone-aware date and time.')
    assert isinstance(since, datetime) and isinstance(until, datetime)
    if until <= since:
        raise ValueError('The window ends after it starts.')


def _runs(span: dict[str, Any]) -> dict[str, Any]:
    """The window's interpreter runs - every provider of interpretation.READ_PROVIDERS - by state, provider, requested
    and returned model, the paused ones, their usage summed (SUMMED_KEYS) and their estimated cost, each priced by the
    model its request named (estimated_cost; no fallback)."""
    rows = list(ProviderRun.objects.filter(provider__in=interpretation.READ_PROVIDERS, **span).values(
        'state', 'requested_model', 'returned_model', 'usage', 'sent', 'reused_from_id', 'scope', 'started_at',
        'purpose', 'provider'))
    usage: Counter[str] = Counter()
    cost, priced, unpriced = Decimal('0'), 0, 0
    for row in rows:
        reported = row['usage'] if isinstance(row['usage'], dict) else {}
        _add_usage(usage, reported)
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
            'by_provider': dict(sorted(Counter(row['provider'] for row in rows).items())),
            'by_state': dict(sorted(Counter(row['state'] for row in rows).items())),
            'requested_models': dict(sorted(Counter(row['requested_model'] or '(none)' for row in rows).items())),
            'returned_models': dict(sorted(Counter(row['returned_model'] or '(none)' for row in rows).items())),
            'paused': dict(sorted(paused.items())),
            'sent': sum(1 for row in rows if row['sent']),
            'reused': sum(1 for row in rows if row['reused_from_id'] is not None),
            'usage': {key: usage[key] for key in SUMMED_KEYS},
            'cost': {'estimated_usd': f'{cost:f}', 'priced_runs': priced, 'unpriced_runs': unpriced,
                     'basis': _pricing_basis()},
            'by_purpose': _by_purpose(rows)}


def _by_purpose(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """design v2: the window's interpreter runs by purpose (pass 1's interpretation, pass 2's appraisal, and any other):
    each purpose's count, sent and reused runs, usage as reported and estimated cost (usage_sums over the same rows)."""
    purposes = list(dict.fromkeys([*V2_PURPOSES, *(row['purpose'] for row in rows)]))
    out = {}
    for purpose in purposes:
        mine = [row for row in rows if row['purpose'] == purpose]
        sums = usage_sums([{'sent': row['sent'], 'reused_from': row['reused_from_id'],
                            'usage': row['usage'] if isinstance(row['usage'], dict) else {},
                            'estimated_cost': (estimated_cost(row['requested_model'], row['usage'], row['started_at'])
                                               if row['sent'] and row['reused_from_id'] is None else None)}
                           for row in mine])
        out[purpose] = {'total': len(mine), 'sent': sum(1 for row in mine if row['sent']),
                        'reused': sum(1 for row in mine if row['reused_from_id'] is not None),
                        'usage': sums['usage'], 'estimated_usd': sums['estimated_usd'],
                        'priced_runs': sums['priced_runs'], 'unpriced_runs': sums['unpriced_runs']}
    return out


def _inventory_versions(span: dict[str, Any]) -> dict[str, int]:
    """design v2: the window's event inventories by version pair ('<interpretation_version> / <inventory_version>')."""
    pairs = EventInventory.objects.filter(**span).values_list('interpretation_version', 'inventory_version')
    return dict(sorted(Counter(f'{first} / {second}' for first, second in pairs).items()))


def _appraisal(span: dict[str, Any]) -> dict[str, Any]:
    """design v2 (FINAL-V2 3.2.6, 1.7): the appraisals of the window - the v2 inventories read (each settled from a
    healthy appraisal) with their health measures and coherence outcomes summed (verification.health and .coherence),
    and the appraisal runs of every interpreter provider (interpretation.READ_PROVIDERS) whose scope records a refused
    health (an appraisal 3.2.6 refused whole, which writes no inventory: 7.5), by refusal."""
    from studio.interpretation import store

    rows = [row for row in EventInventory.objects.filter(state=EventInventory.READ, **span).values(
        'interpretation_version', 'inventory_version', 'verification')
        if (row['interpretation_version'], row['inventory_version']) in store.READ_VERSIONS]
    health: Counter[str] = Counter()
    coherence: Counter[str] = Counter()
    unread = 0
    for row in rows:
        report_ = row['verification'] if isinstance(row['verification'], dict) else {}
        found_health = report_.get('health') if isinstance(report_.get('health'), dict) else None
        found_coherence = report_.get('coherence') if isinstance(report_.get('coherence'), dict) else None
        if found_health is None or found_coherence is None:
            unread += 1
            continue
        for key in HEALTH_MEASURES:
            value = found_health.get(key)
            if type(value) is int and value >= 0:
                health[key] += value
        for key in COHERENCE_OUTCOMES:
            value = found_coherence.get(key)
            if type(value) is int and value >= 0:
                coherence[key] += value
    refused: Counter[str] = Counter()
    unhealthy = 0
    for scope in ProviderRun.objects.filter(provider__in=interpretation.READ_PROVIDERS,
                                            purpose=interpretation.APPRAISAL_PURPOSE, **span).values_list('scope',
                                                                                                          flat=True):
        found = scope.get('health') if isinstance(scope, dict) else None
        reasons = found.get('refused') if isinstance(found, dict) else None
        if isinstance(reasons, list) and reasons:
            unhealthy += 1
            refused.update(str(reason) for reason in reasons)
    return {'inventories': len(rows), 'without_health': unread,
            'health': {key: health[key] for key in HEALTH_MEASURES},
            'coherence': {key: coherence[key] for key in COHERENCE_OUTCOMES},
            'unhealthy': unhealthy, 'refused': dict(sorted(refused.items()))}


def _pricing_basis() -> str:
    """What the window's estimate rests on: each run priced by the model its request named, and each priced model's
    basis (participants.pricing's), the interpreter's first."""
    from studio.participants import pricing

    bases = '; '.join(f'{model}: {basis}' for model, basis in (
        (pricing.FABLE_52, pricing.FABLE_52_BASIS), (pricing.GEMINI, pricing.GEMINI_BASIS),
        (pricing.GEMINI_ARGON, pricing.GEMINI_ARGON_BASIS)))
    return f'each run priced by the model its request named, a run that named none not priced; {bases}'


def _assessments(span: dict[str, Any]) -> dict[str, Any]:
    rows = list(Assessment.objects.filter(**span).values('engine_version', 'event_inventory_id', 'context_id',
                                                         'interpretation'))
    new = [row for row in rows if _is_new(row['engine_version'])]
    v2 = [row for row in new if is_v2_assessment(row['engine_version'])]
    v1 = [row for row in new if row['engine_version'] == interpretation.ENGINE_VERSION]
    # a later events version's records are judged by no rule of this release: each is a record with a problem, and
    # its sentinel record is not read (it counts among those without one)
    records = [(row['interpretation'].get('sentinel') if isinstance(row['interpretation'], dict) else None,
                is_v2_assessment(row['engine_version'])) for row in new if not _unread_events(row['engine_version'])]
    complete: list[dict[str, Any]] = [found for found, is_v2 in records
                                      if isinstance(found, dict) and not sentinel_problems_shape(found, v2=is_v2)]
    calls = sum(found['legacy_calls'] for found in complete)
    off_pins = sum(1 for found in complete if (found['tool'], found['deny_size'], found['positive_control'])
                   != (sentinel.TOOL, sentinel.DENY_SIZE, 'ok'))
    # design v2: the retired calls each v2 record counts (None: its sentinel counted none - a record problem)
    retired = [found.get(RETIRED_CALLS) for found, is_v2 in records
               if is_v2 and isinstance(found, dict) and not sentinel_problems_shape(found, v2=True)]
    counted = [value for value in retired if type(value) is int and value >= 0]
    # every new-path record read as record_problems reads one, without its legacy-call count (checked apart)
    ids = {row['event_inventory_id'] for row in new if row['event_inventory_id'] is not None}
    stored = {row['id']: row for row in EventInventory.objects.filter(pk__in=ids).values('id', *_STORED_V2)}
    problems: Counter[str] = Counter()
    with_problems = 0
    for row in new:
        if _unread_events(row['engine_version']):
            found = [_unread_problem(row['engine_version'])]
        elif is_v2_assessment(row['engine_version']):
            found = _record_problems_v2(row['interpretation'], row['engine_version'], row['event_inventory_id'],
                                        row['context_id'], stored.get(row['event_inventory_id']), calls=False)
        else:
            found = _record_problems(row['interpretation'], row['event_inventory_id'], row['context_id'],
                                     stored.get(row['event_inventory_id']), calls=False)
        with_problems += bool(found)
        problems.update(found)
    return {'total': len(rows),
            'by_engine_version': dict(sorted(Counter(row['engine_version'] for row in rows).items())),
            'new_path': len(new), 'legacy_engine': len(rows) - len(new),
            'v2': len(v2), 'v1_events': len(v1), 'unread_events': len(new) - len(v2) - len(v1),
            'without_inventory': sum(1 for row in new if row['event_inventory_id'] is None),
            'without_sentinel_record': len(new) - len(complete),
            'off_pins': off_pins,
            'with_record_problems': with_problems,
            'record_problems': dict(problems.most_common(MAX_PROBLEMS)),
            'legacy_calls': calls,
            'with_legacy_calls': sum(1 for found in complete if found['legacy_calls'] != 0),
            'retired_calls': sum(counted),
            'with_retired_calls': sum(1 for value in counted if value != 0),
            'without_retired_count': len(retired) - len(counted),
            'deny_sizes': dict(sorted(Counter(str(found['deny_size']) for found in complete).items())),
            'positive_controls': dict(sorted(Counter(str(found['positive_control']) for found in complete).items())),
            'tools': dict(sorted(Counter(str(found['tool']) for found in complete).items()))}


def sentinel_problems_shape(found: object, *, v2: bool = False) -> bool:
    """Whether a recorded sentinel record is missing or misshapen: not exactly SENTINEL_KEYS (for a design v2 record,
    not at least SENTINEL_KEYS_V2), or a legacy_calls that is not a count (its values are judged by sentinel_problems
    and sentinel_problems_v2)."""
    if not isinstance(found, dict):
        return True
    if v2 and not set(SENTINEL_KEYS_V2) <= set(found):
        return True
    if not v2 and tuple(sorted(found)) != tuple(sorted(SENTINEL_KEYS)):
        return True
    calls = found['legacy_calls']
    return type(calls) is not int or calls < 0


def _is_new(engine_version: object) -> bool:
    return interpretation.is_new_assessment(_Engine(engine_version))


class _Engine:
    __slots__ = ('engine_version',)

    def __init__(self, engine_version: object) -> None:
        self.engine_version = engine_version


def _trips(span: dict[str, Any]) -> dict[str, Any]:
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

def model_constants() -> tuple[dict[str, str], dict[str, str]]:
    """(the code's model constants, the written-out literal each must equal): AMENDMENT-2 section 9's three for the
    interpreter (interpretation.MODEL_V3, fable_adapter.MODEL and fable_adapter.ENDPOINT against D275_MODEL and
    D275_ENDPOINT), and the dormant Gemini adapter's three against D13_MODEL and FINAL_ENDPOINT - each compared with its
    literal, never with another constant (each three are one value)."""
    from studio.interpretation import adapter, fable_adapter

    constants = {'interpretation.MODEL_V3': interpretation.MODEL_V3, 'fable_adapter.MODEL': fable_adapter.MODEL,
                 'fable_adapter.ENDPOINT': fable_adapter.ENDPOINT, 'interpretation.MODEL': interpretation.MODEL,
                 'adapter.MODEL': adapter.MODEL, 'adapter.ENDPOINT': adapter.ENDPOINT}
    expected = {'interpretation.MODEL_V3': D275_MODEL, 'fable_adapter.MODEL': D275_MODEL,
                'fable_adapter.ENDPOINT': D275_ENDPOINT, 'interpretation.MODEL': D13_MODEL,
                'adapter.MODEL': D13_MODEL, 'adapter.ENDPOINT': FINAL_ENDPOINT}
    return constants, expected


def self_test(report: dict[str, Any]) -> dict[str, Any]:
    """The installer's verify checks over a window report from this process (``window``): {'passed', 'checks': [{name,
    ok, detail}]}, one per SELF_TEST name. Nothing here checks the interpreter mode: a one-shot's is its own, never the
    worker's, so the installer reads the worker's configured mode from the worker."""
    found = report['sentinel']
    assessments, trips = report['assessments'], report['trips']
    trip = sentinel.trip_test()
    constants, expected = model_constants()
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
         f'{constants["interpretation.MODEL_V3"]}, D275 says {D275_MODEL}; the dormant Gemini adapter\'s '
         f'{constants["interpretation.MODEL"]}, D13 says {D13_MODEL}'
         + (f'; {", ".join(wrong)} differ' if wrong else '')),
        ('no new-path legacy execution recorded',
         assessments['legacy_calls'] == 0 and assessments['retired_calls'] == 0,
         f'{assessments["legacy_calls"]} legacy executions and {assessments["retired_calls"]} retired executions over '
         f'{assessments["new_path"]} new-path assessments'),
        ('every new-path assessment carries its record', assessments['with_record_problems'] == 0,
         f'{assessments["with_record_problems"]} of {assessments["new_path"]} with a problem in their record '
         f'({assessments["without_inventory"]} without an inventory, {assessments["without_sentinel_record"]} without '
         f'a sentinel record, {assessments["off_pins"]} off their pins)'),
        ('no sentinel trip', trips['total'] == 0,
         f'{trips["total"]} recorded, {trips["unavailable"]["total"]} of them a process that could not count'),
        ('no legacy-engine assessment', assessments['legacy_engine'] == 0 and assessments['v1_events'] == 0,
         f'{assessments["legacy_engine"]} legacy-engine and {assessments["v1_events"]} v1 assessments in the window'),
    ]
    return {'passed': all(ok for _, ok, _ in checks),
            'checks': [{'name': name, 'ok': bool(ok), 'detail': detail} for name, ok, detail in checks]}


# --- the text -------------------------------------------------------------------------------------------------------------

def render(report: dict[str, Any], test: Optional[dict[str, Any]] = None) -> list[str]:
    """The report (and the self-test) as text lines, one 'field: value' line per D22 field, in D22_FIELDS' order."""
    runs, assessments, found, hold = report['gemini_runs'], report['assessments'], report['sentinel'], report['hold']
    appraisal, interpreter = report['appraisal'], report['interpreter']
    standing, unavailable = hold['standing'], report['trips']['unavailable']
    values = {
        'window': f'{report["window"]["since"]} to {report["window"]["until"]}',
        'interpreter mode (this process)': (f'{interpreter["process_mode"]}; this process\'s own setting - a '
                                            'one-shot runs with the interpreter disabled unless it is given a mode, '
                                            'and the worker\'s own setting decides for the worker'),
        'model': (f'{interpreter["model_v3"]} (named in each request; an answer that reports another model is held); '
                  f'the dormant Gemini adapter\'s {interpreter["model"]} (asked by URL)'),
        'interpreter runs': (f'{runs["total"]} ({runs["sent"]} sent, {runs["reused"]} reused; by provider '
                             f'{_pairs(runs["by_provider"])})'),
        'interpreter runs by state': _pairs(runs['by_state']),
        'interpreter runs by requested model': _pairs(runs['requested_models']),
        'interpreter runs by returned model': _pairs(runs['returned_models']),
        'interpreter runs paused': _pairs(runs['paused']),
        'interpreter usage': _pairs(runs['usage']),
        'interpreter estimated cost': (f'USD {runs["cost"]["estimated_usd"]} over '
                                       f'{_count(runs["cost"]["priced_runs"], "priced run")} '
                                       f'({_count(runs["cost"]["unpriced_runs"], "sent run")} not priced); '
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
        # design v2 (step 5c)
        'interpreter runs by purpose': ('; '.join(f'{purpose} {found["total"]} ({found["sent"]} sent, '
                                                  f'{found["reused"]} reused)'
                                                  for purpose, found in runs['by_purpose'].items()) or 'none'),
        'interpreter usage by purpose': ('; '.join(f'{purpose}: {_pairs(found["usage"])}'
                                                   for purpose, found in runs['by_purpose'].items()) or 'none'),
        'interpreter estimated cost by purpose': ('; '.join(
            f'{purpose} USD {found["estimated_usd"]} over {_count(found["priced_runs"], "priced run")} '
            f'({_count(found["unpriced_runs"], "sent run")} not priced)'
            for purpose, found in runs['by_purpose'].items()) or 'none'),
        'event inventories by version': _pairs(report['inventories_by_version']),
        'appraisal health': (f'{appraisal["inventories"]} v2 inventories read ({appraisal["without_health"]} with no '
                             f'health recorded); {_pairs(appraisal["health"])}'),
        'appraisal coherence': _pairs(appraisal['coherence']),
        'appraisals refused as unhealthy': (f'{appraisal["unhealthy"]}' + (
            f' ({_pairs(appraisal["refused"])})' if appraisal['refused'] else '')),
        'v1 assessments': (f'{assessments["v1_events"]} (cpt-studio-events@1: read as stored and blocked; '
                           f'{assessments["v2"]} design v2 assessments'
                           + (f'; {assessments["unread_events"]} of an events version this release does not read'
                              if assessments.get('unread_events') else '') + ')'),
        'sentinel retired calls recorded': (f'{assessments["retired_calls"]} over {assessments["v2"]} design v2 '
                                            f'assessments ({assessments["with_retired_calls"]} with any; '
                                            f'{assessments["without_retired_count"]} whose sentinel counted none)'),
    }
    lines = [f'{field}: {value}' for field, value in values.items()]
    if test is not None:
        lines += [f'self-test {item["name"]}: {"PASS" if item["ok"] else "FAIL"} ({item["detail"]})'
                  for item in test['checks']]
        lines.append(f'self-test: {"PASSED" if test["passed"] else "FAILED"}')
    return lines


# --- one encounter (design v2: both runs and the usage sums; AMENDMENT-1 9.2) -----------------------------------------

def encounter_section(encounter_id: object) -> Optional[dict[str, Any]]:
    """The interpretation section of one encounter (``manage.py interpretation_report --encounter``): its id, its
    current assessment's section (interpretation_section: for a design v2 assessment both runs with their usage,
    estimated cost and sums) and every interpreter run of the encounter by purpose with the sums (encounter_usage),
    also for an encounter with no assessment yet. None when no encounter has that id. Stored rows only."""
    from studio.models import Encounter

    encounter = Encounter.objects.select_related('current_assessment').filter(pk=encounter_id).first()
    if encounter is None:
        return None
    assessment = encounter.current_assessment if encounter.current_assessment_id else None
    return {'encounter': str(encounter.pk),
            'assessment': str(assessment.pk) if assessment is not None else None,
            'section': interpretation_section(assessment) if assessment is not None else None,
            'usage': encounter_usage(encounter.pk)}


def _flat(usage: object) -> dict[str, object]:
    """A usage as reported, for a text line: each nested object's members spelt with dotted keys
    ('cache_creation.ephemeral_5m_input_tokens'), as ANTHROPIC_USAGE_KEYS spells them."""
    out: dict[str, object] = {}
    for key, value in (usage.items() if isinstance(usage, dict) else ()):
        if isinstance(value, dict):
            out.update({f'{key}.{inner}': item for inner, item in value.items()})
        else:
            out[str(key)] = value
    return out


def _run_line(name: str, run: Optional[dict[str, Any]]) -> str:
    if not run:
        return f'{name}: none'
    cost = run.get('estimated_cost')
    return (f'{name}: {run["id"]} provider {run["provider"]} purpose {run["purpose"]} state {run["state"]} requested '
            f'{run["requested_model"] or "-"} returned {run["returned_model"] or "-"}; usage '
            f'{_pairs(_flat(run["usage"]))}; '
            + (f'estimated cost USD {cost}' if cost else 'no estimated cost'))


def render_encounter(section: dict[str, Any]) -> list[str]:
    """An encounter_section as text lines: the assessment, its runs (pass 1 and the appraisal, for a design v2 one),
    their sums, and the encounter's runs by purpose with the sums."""
    found = section.get('section') or {}
    lines = [f'encounter: {section["encounter"]}',
             f'encounter assessment: {section["assessment"] or "none"}'
             + (f' ({found.get("engine_version")})' if found else '')]
    if found:
        lines.append(_run_line('encounter pass 1 run', found.get('run')))
        if 'appraisal_run' in found:
            lines.append(_run_line('encounter appraisal run', found.get('appraisal_run')))
        if found.get('usage'):
            sums = found['usage']
            lines.append(f'encounter assessment usage: {_pairs(sums["usage"])}; estimated cost USD '
                         f'{sums["estimated_usd"]} over {_count(sums["priced_runs"], "priced run")}')
        lines += [f'encounter record problem: {problem}' for problem in found.get('problems') or ()]
        lines += render_questions(found.get('questions'))  # round r3: the question stage, its codes and requests
    usage = section['usage']
    for purpose, sums in usage['by_purpose'].items():
        lines.append(f'encounter {purpose} runs: {sums["runs"]}; usage {_pairs(sums["usage"])}; estimated cost USD '
                     f'{sums["estimated_usd"]} over {_count(sums["priced_runs"], "priced run")} '
                     f'({_count(sums["unpriced_runs"], "sent run")} not priced)')
    total = usage['total']
    lines.append(f'encounter interpreter runs: {total["runs"]}; usage {_pairs(total["usage"])}; estimated cost USD '
                 f'{total["estimated_usd"]} over {_count(total["priced_runs"], "priced run")} '
                 f'({_count(total["unpriced_runs"], "sent run")} not priced)')
    return lines


def _count(n: int, noun: str) -> str:
    return f'{n} {noun}{"" if n == 1 else "s"}'


def _pairs(mapping: dict[str, Any]) -> str:
    return ', '.join(f'{key} {value}' for key, value in mapping.items()) or 'none'
