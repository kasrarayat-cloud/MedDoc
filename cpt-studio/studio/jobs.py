"""Pipeline jobs: extract -> analyze -> predict -> assess [-> review2 -> assess] (ARCHITECTURE section 5).

One worker claims queued jobs with SELECT ... FOR UPDATE SKIP LOCKED. Every
stage is idempotent (unique idempotency key), must start before its deadline,
and records failure explicitly. Provider sends are single-flight under a
PostgreSQL advisory lock, reserved in the database before any network I/O,
never retried automatically, and an unknown outcome blocks every further send
for the encounter until a member reconciles it.
"""
from __future__ import annotations

import hashlib
import logging
import sys
import time
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from . import audit, bounded, models, review
from .gi import context as gi_context
from .gi import detect as gi_detect
from .ingest import Limits, extract_document, extract_paste
from .providers import get_provider, normalizer_for
from .providers.base import ProviderUnavailable
from .reference.store import prefetched_lookup, selected_codes
from .storage import read_original
from .types import (EvidenceSpan, Fact, NormalizedResponse, PageSpan, ProviderCode, ProviderRequest, RoutingResult,
                    from_jsonable, sha256_json, to_jsonable)
from .validation.engine import assess as run_assessment

log = logging.getLogger(__name__)

CONTEXT_VERSION = 'gi-context@2'
# Context versions recorded under other merge rules (gi-context@1, the installed revision 057a7d39, kept a member's value
# as plain metadata): a stage remakes such a context before it sends or assesses anything (_remade_context).
EARLIER_CONTEXT_VERSIONS = ('gi-context@1',)
MEMBER_DATE_CONFLICT_MESSAGE = ('Nothing was sent: the service date entered as encounter metadata differs from the '
                                'documented one. Correct or clear the metadata (or add an addendum), and the request is '
                                'made for the agreed date.')
PROVIDER_LOCK_KEY = 0x435054535455  # 'CPTSTU': CPT Studio's own single-flight key
QUEUE_DEADLINE = timedelta(minutes=30)  # a job that cannot start within this window expires
Job = models.Job


class StageFailure(Exception):
    """A stage failed for a reason the member should read."""


class Requeue(Exception):
    """The stage could not start now (e.g. provider lock busy); try again later."""


class Refused(Exception):
    """A member action was refused; the message says why (the API answers 409)."""


STALE_SWEEP_SECONDS = 60  # how often a running worker settles stages a dead worker left 'running'


# --- enqueueing --------------------------------------------------------------

def enqueue(kind, *, encounter, revision, key, context=None, provider_run=None, requested_by=None):
    """Create the job for ``key`` once. A repeated key returns the existing job."""
    job, _ = Job.objects.get_or_create(
        idempotency_key=key,
        defaults={'encounter': encounter, 'revision': revision, 'kind': kind, 'context': context,
                  'provider_run': provider_run, 'requested_by': requested_by,
                  'deadline_at': timezone.now() + QUEUE_DEADLINE})
    return job


def clear_stop(encounter):
    """A member asked for processing again: lift the encounter's Stop."""
    models.Encounter.objects.filter(pk=encounter.pk).update(stopped_at=None, stopped_by=None)


def is_stopped(encounter_id):
    return models.Encounter.objects.filter(pk=encounter_id, stopped_at__isnull=False).exists()


def start_pipeline(revision, requested_by):
    clear_stop(revision.encounter)
    return enqueue(Job.EXTRACT, encounter=revision.encounter, revision=revision,
                   key=f'extract:{revision.pk}', requested_by=requested_by)


def _member_date_hold(encounter, revision, provider, requested_by):
    """The not-sent run session interpretation 19 records for a context whose service date is a member conflict: the
    request has no date it could carry, so nothing is built, reused or sent, and the run says why."""
    return models.ProviderRun.objects.create(
        encounter=encounter, revision=revision, provider=provider.name, adapter_version=provider.adapter_version,
        request_sha256='', request_body={}, contexts=[], state=models.ProviderRun.NOT_SENT,
        error=MEMBER_DATE_CONFLICT_MESSAGE, authorization_ref=settings.AUTHORIZATION_REF, requested_by=requested_by,
        service_date=None, finished_at=timezone.now(), scope={'held': models.ProviderRun.HELD_MEMBER_DATE_CONFLICT})


def _queue_predict(encounter, revision, context, *, key, requested_by):
    """Queue the predict for ``context`` - unless it is the current revision's current context and its service date is
    a member conflict. Then the hold is recorded here, where it is decided, and only the assess that reads it is queued:
    never a job that can send and whose hold only this revision's predict stage knows (refutation r1, migrate lens: the
    installed revision's worker, restored after a failed replacement or reinstalled, read the conflict as 'no date' and
    sent the request without one). Every other predict is queued as before; one for a context that is no longer current
    is skipped by every revision's predict stage."""
    fact = (context.facts or {}).get('service_date') if context is not None else None
    if not gi_context.is_member_conflict(fact) or not models.Encounter.objects.filter(
            pk=encounter.pk, current_revision_id=revision.pk, current_context_id=context.pk).exists():
        return enqueue(Job.PREDICT, encounter=encounter, revision=revision, context=context, key=key,
                       requested_by=requested_by)
    provider = get_provider()
    run = _member_date_hold(encounter, revision, provider, requested_by) if provider is not None else None
    return enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=run,
                   key=f'assess:{context.pk}:{run.pk}' if run else f'{key}:no-provider', requested_by=requested_by)


# --- helpers -----------------------------------------------------------------

def _limits():
    return Limits(timeout_s=settings.EXTRACTION_TIMEOUT_SECONDS, max_pages=settings.MAX_PDF_PAGES,
                  max_chars=settings.MAX_PASTE_CHARS, max_bytes=settings.MAX_UPLOAD_BYTES)


def context_facts(context) -> dict[str, Fact]:
    return {name: from_jsonable(Fact, value) for name, value in (context.facts or {}).items()}


def context_service_date(context):
    return _service_date_of(context.facts)


def _service_date_of(facts):
    """The effective service date of a context's facts (as stored): a documented or member-supplied date, else None."""
    fact = (facts or {}).get('service_date') or {}
    if fact.get('origin') not in {'document', 'user'} or not fact.get('value'):
        return None
    try:
        return date.fromisoformat(fact['value'])
    except ValueError:
        return None


OVERRUN_MESSAGES = {
    'time': 'Reading this document took longer than {seconds} seconds and was stopped. The document may be too long '
            'or unusual to read within the limit; shorten it or split it, then upload it again.',
    'memory': 'Reading this document needed more memory than the limit allows and was stopped. Shorten it or split '
              'it, then upload it again.',
}
MENTIONS_MESSAGE = ('This document names a procedure {count:,} times, more than the {limit:,} this service reads in one '
                    'document, so it was not read and nothing was sent. Shorten it or split it, then upload it again.')


def _bounded(fn, *args, seconds, refusal=None, memory_bytes=None):
    """``fn(*args)`` under the wall-clock and memory limits (studio/bounded.py; ``memory_bytes`` defaults to
    BOUNDED_MEMORY_BYTES); an overrun fails the stage, or is refused to the member when ``refusal`` is given (a web
    request)."""
    try:
        return bounded.run_bounded(fn, *args, seconds=seconds,
                                   memory_bytes=memory_bytes or settings.BOUNDED_MEMORY_BYTES)
    except bounded.Overrun as exc:
        message = OVERRUN_MESSAGES[exc.reason].format(seconds=seconds)
        raise (refusal or StageFailure)(message) from None


def make_context(encounter, revision, *, created_by=None, seconds=None, refusal=None):
    """Snapshot document facts merged with the encounter's member-supplied values (a member's change: the stages
    extract the facts inside their own single bounded child, _analyze_child)."""
    document_facts = _bounded(gi_context.extract_context, revision.text,
                              seconds=seconds or settings.JOB_DEADLINE_SECONDS['analyze'], refusal=refusal)
    return _record_context(encounter, revision, document_facts, created_by=created_by)


def _merged_facts(document_facts, user_values):
    merged = gi_context.merge_user_values(document_facts, dict(user_values or {}))
    return {name: to_jsonable(fact) for name, fact in merged.items()}


def _record_context(encounter, revision, document_facts, *, created_by=None):
    user_values = dict(encounter.user_values or {})
    facts = _merged_facts(document_facts, user_values)
    return models.EncounterContext.objects.create(
        encounter=encounter, revision=revision, facts=facts, user_values=user_values, version=CONTEXT_VERSION,
        sha256=sha256_json({'facts': facts, 'user_values': user_values, 'revision': str(revision.pk)}),
        created_by=created_by)


def _record_routing(revision, data, service_date):
    """Store a routing result (its JSON form) once per distinct result and the service date it was routed for."""
    digest = sha256_json(data)
    version = data.get('version', '')
    existing = models.RoutingRun.objects.filter(revision=revision, version=version, sha256=digest,
                                                service_date=service_date).first()
    if existing:
        return existing
    return models.RoutingRun.objects.create(revision=revision, version=version, result=data, sha256=digest,
                                            service_date=service_date)


# --- the bounded children (round 5: bounded:0-2, pipeline:1-2, validation:0) ---------------------------------
#
# Each CPU-bound stage runs ALL of its document reading in ONE forked child under the stage's own deadline and the
# memory allowance (studio/bounded.py), so no part of a stage reads the document unbounded in the worker, the stage
# deadline is the stage's and not each call's, and no routing analysis is ever retained in the long-lived worker.
# The children are Django-free and never touch the database: the parent records what they return.

def _analyze_child(text, user_values, mention_limit):
    """The document's facts and its routing for the effective service date those facts (with the member's values)
    give. Routing then reuses the context work the child already did, instead of redoing it cold. A document naming
    procedures more than ``mention_limit`` times is not read: only that count (an int) is returned (round 7: a
    mention is read in its list window, and a long list of one service's name overran the stage). Every later stage
    reads only a revision this stage read."""
    named = gi_detect.service_mention_count(text)
    if named <= mention_limit:  # and the documented-service reader's own vocabulary, which is wider (refutation r1)
        from .gi import services as gi_services
        named = max(named, gi_services.mention_count(text, mention_limit))
    if named > mention_limit:
        return named
    document_facts = gi_context.extract_context(text)
    service_date = _service_date_of(_merged_facts(document_facts, user_values))
    return document_facts, service_date, to_jsonable(gi_detect.route(text, service_date))


def _route_child(text, service_date):
    """The routing for ``service_date`` alone: a date change routes the new date before anything is sent for it."""
    return to_jsonable(gi_detect.route(text, service_date))


def _assess_child(text, service_date, pages, context, normalized, reference, provider_status, extraction_status,
                  extraction_messages, second=None, second_scope=None):
    """The routing for ``service_date`` and the validation assessment that reads it, in one child: validation's span
    readings reuse the routing analysis the child already made. The documented-service inventory is read here too
    (engine @4), under the same deadline and memory limit."""
    data = to_jsonable(gi_detect.route(text, service_date))
    result = run_assessment(
        text=text, pages=pages, context=context, routing=from_jsonable(RoutingResult, data), normalized=normalized,
        reference=reference, service_date=service_date, provider_status=provider_status,
        extraction_status=extraction_status, extraction_messages=extraction_messages, second=second,
        second_scope=second_scope)
    return data, result


ROUTING_CACHE_MODULES = ('studio.gi.detect', 'studio.gi.sections', 'studio.gi.context', 'studio.validation.checks',
                         'studio.validation.engine')


def release_routing_caches():
    """Clear every functools cache of the routing and validation modules in this process. The stages read documents
    only in bounded children, so in the worker this is a backstop: nothing a stage read stays resident (bounded:2)."""
    for name in ROUTING_CACHE_MODULES:
        module = sys.modules.get(name)
        for value in vars(module).values() if module else ():
            clear = getattr(value, 'cache_clear', None)
            if callable(clear) and hasattr(value, 'cache_info'):
                clear()


DATE_CONTEXT_PREFIX = 'Date of service: '


def run_service_date(run):
    """The service date a run's request was built with: the recorded column, or for a run recorded before the
    column existed, the one 'Date of service: ' context its request carried (None when it carried none)."""
    if run.service_date is not None or not run.request_sha256:
        return run.service_date
    dates = [c[len(DATE_CONTEXT_PREFIX):] for c in (run.contexts or [])[1:]
             if isinstance(c, str) and c.startswith(DATE_CONTEXT_PREFIX)]
    try:
        return date.fromisoformat(dates[0]) if len(dates) == 1 else None
    except ValueError:
        return None


def addendum_block_text(number, created_at, text):
    stamp = created_at.strftime('%Y-%m-%d %H:%M UTC')
    return f'\n\nADDENDUM (revision {number}, added {stamp})\n{text.strip()}\n'


def addendum_block(revision):
    return addendum_block_text(revision.number, revision.created_at, revision.addendum_text)


def _unreconciled_unknown(encounter):
    return encounter.provider_runs.filter(state=models.ProviderRun.UNKNOWN, reconciled_at__isnull=True).exists()


# --- stages ------------------------------------------------------------------

def stage_extract(job):
    revision = job.revision
    if revision.extraction_status != models.SourceRevision.PENDING:
        return {'skipped': 'already extracted'}
    pages_override = None
    if revision.kind == models.SourceRevision.UPLOAD:
        source = revision.source_file
        result = extract_document(read_original(source), source.original_name, source.media_type, limits=_limits())
    elif revision.kind == models.SourceRevision.PASTE:
        result = extract_paste(revision.pasted_text, limits=_limits())
    else:
        parent = revision.parent
        if parent is None or parent.extraction_status not in {models.SourceRevision.OK, models.SourceRevision.PARTIAL}:
            raise StageFailure('The previous revision has no extracted text to add the addendum to.')
        result = extract_paste(parent.text + addendum_block(revision), method='addendum', limits=_limits())
        if result.status != models.SourceRevision.FAILED and not result.text.startswith(parent.text):
            raise StageFailure('The addendum changed the existing document text; it was not recorded.')
    status, messages = result.status, list(result.messages)
    ocr_pages, engine = list(result.ocr_pages), dict(result.engine)
    if revision.kind == models.SourceRevision.ADDENDUM and status != models.SourceRevision.FAILED:
        # The addendum revision's text contains the parent's text unchanged, so the
        # parent's extraction limitations still describe it: they are carried, never dropped.
        pages_override = list(parent.pages)
        if parent.extraction_status == models.SourceRevision.PARTIAL:
            status = models.SourceRevision.PARTIAL
        messages = list(parent.messages) + messages
        ocr_pages = list(parent.ocr_pages)
        engine = {**dict(parent.engine or {}), 'addendum': engine}
    pages = pages_override if pages_override is not None else [
        {'page': p.page, 'start': p.start, 'end': p.end} for p in result.pages]
    models.SourceRevision.record_extraction(
        revision.pk, extraction_status=status, extraction_method=result.method, text=result.text,
        text_sha256=hashlib.sha256(result.text.encode('utf-8')).hexdigest(), pages=pages,
        messages=messages, ocr_pages=ocr_pages, engine=engine, extracted_at=timezone.now())
    audit.record(job.encounter.workspace, 'revision.extracted', encounter=job.encounter, revision=str(revision.pk),
                 status=status, method=result.method, pages=len(pages), ocr_pages=ocr_pages,
                 characters=len(result.text))
    if status == models.SourceRevision.FAILED:
        return {'status': 'failed'}
    enqueue(Job.ANALYZE, encounter=job.encounter, revision=revision, key=f'analyze:{revision.pk}',
            requested_by=job.requested_by)
    return {'status': status}


def stage_analyze(job):
    revision, encounter = job.revision, job.encounter
    revision.refresh_from_db()
    read = _bounded(_analyze_child, revision.text, dict(encounter.user_values or {}), settings.MAX_SERVICE_MENTIONS,
                    seconds=settings.JOB_DEADLINE_SECONDS['analyze'])
    if isinstance(read, int):  # it names procedures more often than the service reads: not read, nothing recorded
        raise StageFailure(MENTIONS_MESSAGE.format(count=read, limit=settings.MAX_SERVICE_MENTIONS))
    document_facts, service_date, data = read
    context = _record_context(encounter, revision, document_facts)
    if context_service_date(context) != service_date:  # the child read the same facts; never route another date
        raise StageFailure('The document was routed for another service date than its context; nothing was used.')
    routing = _record_routing(revision, data, service_date)
    with transaction.atomic():
        locked = models.Encounter.objects.select_for_update().get(pk=encounter.pk)
        if locked.current_revision_id == revision.pk:
            locked.current_context = context
            locked.save(update_fields=['current_context', 'updated_at'])
    _queue_predict(encounter, revision, context, key=f'predict:{context.pk}', requested_by=job.requested_by)
    return {'context': str(context.pk), 'routing': str(routing.pk)}


def _finish_run(run, exchange):
    state = {'succeeded': models.ProviderRun.SUCCEEDED, 'failed': models.ProviderRun.FAILED,
             'unknown': models.ProviderRun.UNKNOWN, 'not_sent': models.ProviderRun.NOT_SENT}[exchange.outcome]
    run.state = state
    run.sent = bool(exchange.sent)
    run.http_status = exchange.http_status
    run.response_bytes = exchange.response_bytes or b''
    run.response_sha256 = exchange.response_sha256 or (
        hashlib.sha256(exchange.response_bytes).hexdigest() if exchange.response_bytes else '')
    run.latency_ms = exchange.latency_ms
    run.usage = dict(exchange.usage or {})
    run.usage_basis = exchange.usage_basis
    run.provider_request_id = exchange.provider_request_id[:120]
    run.error = exchange.error
    run.finished_at = timezone.now()
    run.save()


def _remade_context(job):
    """A stage given a context an earlier version recorded (gi-context@1 kept a member's value as plain metadata, where
    the current rules keep a differing value as a conflict) remakes it under the current rules - bounded, as a member's
    change does - makes it current and starts again from it; nothing is sent or assessed on the old one (refutation r1:
    after the upgrade a queued, resumed or swept encounter sent a member date the current rules hold as a conflict).
    Returns the job's result, or None when the context is current."""
    context, encounter, revision = job.context, job.encounter, job.revision
    if context is None or context.version not in EARLIER_CONTEXT_VERSIONS or context.revision_id != revision.pk:
        return None
    fresh = make_context(encounter, revision)
    with transaction.atomic():
        locked = models.Encounter.objects.select_for_update().get(pk=encounter.pk)
        if locked.current_revision_id != revision.pk or locked.current_context_id != context.pk:
            return {'skipped': 'the context is not the current one for this revision; nothing was sent'}
        locked.current_context = fresh
        locked.save(update_fields=['current_context', 'updated_at'])
    audit.record(encounter.workspace, 'context.remade', encounter=encounter, context=str(fresh.pk),
                 previous=str(context.pk), previous_version=context.version)
    last_run = _run_in_use(revision)
    if _run_answers(last_run, revision, fresh):
        enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=fresh, provider_run=last_run,
                key=f'assess:{fresh.pk}:{last_run.pk}', requested_by=job.requested_by)
    else:
        _queue_predict(encounter, revision, fresh, key=f'predict:{fresh.pk}', requested_by=job.requested_by)
    return {'skipped': f'the context was recorded by {context.version}; it was remade under {CONTEXT_VERSION}'}


def stage_predict(job):
    revision, encounter, context = job.revision, job.encounter, job.context
    encounter.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists; nothing was sent'}
    if context is None or context.revision_id != revision.pk or encounter.current_context_id != context.pk:
        # Provider input is only ever the current revision's text with that revision's current context.
        return {'skipped': 'the context is not the current one for this revision; nothing was sent'}
    remade = _remade_context(job)
    if remade is not None:
        return remade
    provider = get_provider()
    service_date = context_service_date(context)
    assess_key = f'assess:{context.pk}'

    def next_assess(run):
        enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=run,
                key=f'{assess_key}:{run.pk if run else "no-provider"}', requested_by=job.requested_by)

    if provider is None:
        next_assess(None)
        return {'provider': 'disabled'}
    if gi_context.is_member_conflict((context.facts or {}).get('service_date')):
        # Session interpretation 19: a member-entered service date that differs from the document's is a conflict with
        # both sides kept (interpretation 11), so the request has no date it can carry. Nothing is built, reused or
        # sent while it stands - a dateless request would be paid for and discarded once the date is settled - and the
        # encounter asks the date question. Correcting or clearing the metadata starts the request for its date. Every
        # path that queues a predict records this hold itself (_queue_predict); this holds one queued any other way.
        run = _member_date_hold(encounter, revision, provider, job.requested_by)
        next_assess(run)
        return {'provider': 'not_sent', 'reason': 'member-entered service date conflicts with the document'}
    if not models.RoutingRun.objects.filter(revision=revision, service_date=service_date).exists():
        # Nothing is sent for a date this revision was never routed for (round 6 pipeline:0): after a date change the
        # new date is routed first, in one bounded child under the analyze deadline, so a document that cannot be read
        # for that date fails here with the plain message and no request is built, reused or sent.
        data = _bounded(_route_child, revision.text, service_date, seconds=settings.JOB_DEADLINE_SECONDS['analyze'])
        _record_routing(revision, data, service_date)
    try:
        request = provider.build_request(revision.text, service_date)
    except ProviderUnavailable as exc:
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=provider.name, adapter_version=provider.adapter_version,
            request_sha256='', request_body={}, contexts=[], state=models.ProviderRun.NOT_SENT, error=str(exc),
            authorization_ref=settings.AUTHORIZATION_REF, requested_by=job.requested_by, service_date=service_date,
            finished_at=timezone.now())
        next_assess(run)
        return {'provider': 'not_sent'}

    # Reuse a retained result for the identical request instead of paying twice - whatever the run was made for: a
    # second review's excerpt pasted as a note of its own is the same question (refutation r1: it was resent).
    prior = models.ProviderRun.objects.filter(
        encounter__workspace=encounter.workspace, provider=provider.name, adapter_version=provider.adapter_version,
        request_sha256=request.canonical_sha256, state=models.ProviderRun.SUCCEEDED, reused_from__isnull=True,
    ).order_by('created_at').first()
    if prior is not None:
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=prior.provider, adapter_version=prior.adapter_version,
            request_sha256=prior.request_sha256, request_body=prior.request_body, contexts=prior.contexts,
            state=models.ProviderRun.SUCCEEDED, sent=False, http_status=prior.http_status,
            provider_request_id=prior.provider_request_id, response_sha256=prior.response_sha256,
            response_bytes=bytes(prior.response_bytes), usage={}, usage_basis='reused_retained_result_no_new_usage',
            authorization_ref=settings.AUTHORIZATION_REF, requested_by=job.requested_by, reused_from=prior,
            service_date=service_date, started_at=timezone.now(), finished_at=timezone.now())
        audit.record(encounter.workspace, 'provider.reused', encounter=encounter, run=str(run.pk), reused_from=str(prior.pk))
        next_assess(run)
        return {'provider': 'reused', 'run': str(run.pk)}

    if _unreconciled_unknown(encounter):
        return {'blocked': 'a previous request has an unknown outcome; reconcile it before sending again'}

    _live_gate(job, provider, revision, encounter)

    run = _send(job, provider, request, service_date=service_date)
    next_assess(run)
    return {'provider': run.state, 'run': str(run.pk)}


def _send(job, provider, request, *, service_date, purpose=models.ProviderRun.PRIMARY, scope=None):
    """One provider attempt under the send discipline (ARCHITECTURE 5.4): single-flight by advisory lock, the run
    written 'reserved' before any network I/O, a Stop observed before sending, no automatic retry, and the outcome -
    including an unknown one - recorded with the raw bytes and usage."""
    encounter, revision = job.encounter, job.revision
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [PROVIDER_LOCK_KEY])
        if not cursor.fetchone()[0]:
            raise Requeue('another provider request is in flight')
    try:
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=provider.name, adapter_version=provider.adapter_version,
            request_sha256=request.canonical_sha256, request_body=request.body, contexts=list(request.contexts),
            state=models.ProviderRun.RESERVED, authorization_ref=settings.AUTHORIZATION_REF,
            requested_by=job.requested_by, service_date=service_date, purpose=purpose, scope=scope or {})
        job.refresh_from_db(fields=['stop_requested_at'])
        if job.stop_requested_at or is_stopped(encounter.pk):
            run.state = models.ProviderRun.CANCELLED
            run.error = 'Stopped before sending; nothing was sent.'
            run.finished_at = timezone.now()
            run.save()
            raise StageCancelled('Stopped before the provider request was sent.')
        run.state = models.ProviderRun.SENDING
        run.started_at = timezone.now()
        run.save(update_fields=['state', 'started_at'])
        audit.record(encounter.workspace, 'provider.sending', encounter=encounter, run=str(run.pk),
                     provider=provider.name, mode=provider.mode, request_sha256=request.canonical_sha256,
                     run_identity=str(run.run_identity), purpose=purpose)
        exchange = provider.send(request, deadline_s=settings.PROVIDER_READ_TIMEOUT_SECONDS + 30)
        _finish_run(run, exchange)
        audit.record(encounter.workspace, 'provider.finished', encounter=encounter, run=str(run.pk),
                     state=run.state, http_status=run.http_status, usage=run.usage, latency_ms=run.latency_ms,
                     purpose=purpose)
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK_KEY])
    return run


def _live_gate(job, provider, revision, encounter):
    if provider.mode == 'live':
        if not settings.SYNTHETIC_ONLY or revision.synthetic_attested_at is None:
            raise StageFailure('Live provider calls require a synthetic-attested document.')
        if not settings.AUTHORIZATION_REF:
            raise StageFailure('Live provider calls are not authorized on this installation.')
        membership = models.Membership.objects.filter(user=job.requested_by, workspace=encounter.workspace,
                                                      active=True).first()
        if membership is None or not membership.can_review:
            raise StageFailure('Only an owner or reviewer of this workspace can start a live provider request.')


class StageCancelled(Exception):
    """The stage observed a Stop request and ended without side effects."""


def _provider_inputs(run):
    """(provider_status, normalized response or None, problems)."""
    if run is None:
        return 'not_run', None
    if run.state != models.ProviderRun.SUCCEEDED:
        return ('unknown' if run.state == models.ProviderRun.UNKNOWN else 'failed'), None
    data = bytes(run.response_bytes)
    if hashlib.sha256(data).hexdigest() != run.response_sha256:
        raise StageFailure('The stored provider response no longer matches its recorded hash.')
    request = ProviderRequest(provider=run.provider, adapter_version=run.adapter_version, body=run.request_body,
                              canonical_sha256=run.request_sha256, contexts=tuple(run.contexts))
    return 'succeeded', normalizer_for(run.provider)(request, data)


def stage_assess(job):
    revision, encounter, context, run = job.revision, job.encounter, job.context, job.provider_run
    encounter.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists'}
    if context is not None and encounter.current_context_id == context.pk:
        remade = _remade_context(job)
        if remade is not None:
            return remade
    revision.refresh_from_db()
    if run is not None and run_service_date(run) != context_service_date(context):
        raise StageFailure('The provider result was requested for a different service date than this context; '
                           'it was not used. Change the context again to request proposals for this date.')
    provider_status, normalized = _provider_inputs(run)
    second = _second_run_for(revision, run)
    second_normalized = _second_inputs(second) if second is not None else None
    reference = prefetched_lookup(tuple(sorted(set(selected_codes(normalized)) | set(selected_codes(second_normalized)))))
    service_date = context_service_date(context)
    data, result = _bounded(
        _assess_child, revision.text, service_date, tuple(PageSpan(**p) for p in revision.pages),
        context_facts(context), normalized, reference, provider_status, revision.extraction_status,
        tuple(revision.messages), second_normalized, dict(second.scope) if second is not None else None,
        seconds=settings.JOB_DEADLINE_SECONDS['assess'], memory_bytes=settings.ASSESS_MEMORY_BYTES)
    routing_run = _record_routing(revision, data, service_date)
    try:
        assessment = review.persist_assessment(encounter=encounter, revision=revision, context=context,
                                               routing_run=routing_run, provider_run=run, result=result,
                                               second_run=second)
    except ValueError as exc:
        raise StageFailure(f'The assessment was not recorded: {exc}') from exc
    # The bounded second review is never queued here: a workspace owner or reviewer asks for it
    # (request_second_review; owner decision 2026-10-27, narrow install-first).
    out = {'assessment': str(assessment.pk), 'provider_status': provider_status}
    if second is not None:
        out['second_review'] = str(second.pk)
    return out


# --- the bounded second review (ARCHITECTURE 5.11) ------------------------------------------------------------------

SECOND_REVIEW_REASONS = ('no_proposal', 'not_covered')
SECOND_REVIEW_MAX_CHARS = 20_000  # a longer excerpt is not sent (a second review is about one report, not a chart)


def _second_review_items(assessment):
    """(the unresolved documented services a second review may ask about, (start, end) of the text that documents
    them or None)."""
    completeness = assessment.completeness or {}
    # only items both readers read as done today (engine._routing_agrees); an assessment without the mark asks nothing
    items = [u for u in completeness.get('unresolved_items', []) if u.get('reason') in SECOND_REVIEW_REASONS
             and u.get('second_review') is True]
    if not items:
        return [], None
    services = {s.get('id'): s for s in (assessment.services or {}).get('services', [])}
    spans = []
    for item in items:
        service = services.get(item.get('service')) or {}
        if service.get('scope_end', 0) > service.get('scope_start', 0):
            spans.append((service['scope_start'], service['scope_end']))
        spans += [(ev['start'], ev['end']) for ev in item.get('evidence', [])]
    if not spans:
        return items, None
    return items, (min(a for a, _ in spans), max(b for _, b in spans))


def _second_run_for(revision, run):
    """The second review made for ``run`` (the primary run in use), if one succeeded - or made for the retained run
    ``run`` reuses for the identical request on this revision (refutation r1: after a member date conflict was cleared,
    the reused primary never found the paid second review, so its code disappeared from the decision set)."""
    if run is None or run.state != models.ProviderRun.SUCCEEDED or run.purpose != models.ProviderRun.PRIMARY:
        return None
    primaries = {str(run.pk)} | ({str(run.reused_from_id)} if run.reused_from_id else set())
    for second in (models.ProviderRun.objects.filter(revision=revision, purpose=models.ProviderRun.SECOND_REVIEW,
                                                     state=models.ProviderRun.SUCCEEDED, service_date=run.service_date)
                   .order_by('-created_at')):
        if (second.scope or {}).get('primary_run') in primaries:
            return second
    return None


def _second_inputs(second):
    """The second review's normalized response with its passages moved from the excerpt to the revision text (the
    engine re-checks each against the revision, never assumes it)."""
    provider_status, normalized = _provider_inputs(second)
    if provider_status != 'succeeded' or normalized is None:
        return None
    offset = int((second.scope or {}).get('start', 0))

    def moved(code):
        spans = tuple(EvidenceSpan(0, e.start + offset, e.end + offset, e.text, e.exact, e.page)
                      for e in code.evidence if e.context_index == 0)
        return ProviderCode(code.role, code.system, code.code, code.display, spans, code.parent_code, code.index)
    return NormalizedResponse(normalized.provider, normalized.adapter_version,
                              tuple(moved(c) for c in normalized.codes), normalized.internal_context,
                              normalized.problems, normalized.refused)


def _second_review_blocker(encounter, revision, context, assessment):
    """Why the one bounded second review cannot be asked for now, or '' when it can (5.11). The bounds are the ones the
    automatic second review kept (interpretations 10, 19, 22): once per revision and service date whatever its outcome
    (only a reconciled unknown one releases another), only for the current assessment of a usable primary response,
    only with a known, unconflicted service date, never while a request has an unknown outcome. stage_review2 checks
    them again when it runs. Cheap checks first: the encounter view reads this on every refresh."""
    if busy(encounter):
        return 'Wait for processing to finish (or stop it) before asking for a second review.'
    if (assessment is None or revision is None or context is None or assessment.revision_id != revision.pk
            or assessment.context_id != context.pk):
        return 'There is no current assessment to review again.'
    items, span = _second_review_items(assessment)
    if not items:
        return 'No documented service is left without a supported proposal.'
    if span is None or span[1] - span[0] > SECOND_REVIEW_MAX_CHARS:
        return (f'The text that documents the unresolved services is longer than a second review sends '
                f'({SECOND_REVIEW_MAX_CHARS:,} characters).')
    run = assessment.provider_run
    if run is None or run.state != models.ProviderRun.SUCCEEDED or run.purpose != models.ProviderRun.PRIMARY:
        return 'Only a successful provider response can be reviewed again.'
    if run.service_date is None or context_service_date(context) != run.service_date:
        return 'A second review needs a known, agreed date of service: answer the date question first.'
    if _second_run_for(revision, run) is not None:
        return 'A second review was already made for this document and date.'
    earlier = models.ProviderRun.objects.filter(revision=revision, purpose=models.ProviderRun.SECOND_REVIEW,
                                                service_date=run.service_date)
    if earlier.exclude(state=models.ProviderRun.UNKNOWN, reconciled_at__isnull=False).exists():
        return 'A second review was already requested for this document and date.'
    if _unreconciled_unknown(encounter):
        return 'A previous request has an unknown outcome; reconcile it before asking again.'
    provider = get_provider()
    if provider is None:
        return 'The provider is not configured on this installation.'
    try:
        _, normalized = _provider_inputs(run)
    except StageFailure as exc:
        return str(exc)
    if normalized is None or normalized.refused:
        return 'The provider refused the request whole, so a second review has nothing to fill.'
    try:
        request = provider.build_request(revision.text[span[0]:span[1]], run.service_date)
    except ProviderUnavailable:
        return ''  # stage_review2 records the not-sent run and its reason
    if request.canonical_sha256 == run.request_sha256 or models.ProviderRun.objects.filter(
            encounter__workspace=encounter.workspace, provider=provider.name, adapter_version=provider.adapter_version,
            request_sha256=request.canonical_sha256, state=models.ProviderRun.SUCCEEDED,
            purpose=models.ProviderRun.PRIMARY).exists():
        return ('The text that documents the unresolved services is a request the provider already answered, so a '
                'second review would ask nothing new.')
    return ''


def second_review_status(encounter):
    """What the encounter view shows about the bounded second review: whether one can be asked for now, why not, and
    the unresolved items it would ask about."""
    revision, context, assessment = (encounter.current_revision, encounter.current_context,
                                     encounter.current_assessment)
    items = _second_review_items(assessment)[0] if assessment is not None else []
    reason = _second_review_blocker(encounter, revision, context, assessment) if items else ''
    return {'available': bool(items) and not reason, 'reason': reason,
            'items': [item.get('label', '') for item in items][:8]}


def request_second_review(encounter, user):
    """Queue the ONE bounded second review for the current assessment, asked for by a workspace owner or reviewer
    (owner decision 2026-10-27: never queued by an assessment). Refused with the reason when a bound stands."""
    with transaction.atomic():
        encounter = _locked(encounter)
        revision, context, assessment = (encounter.current_revision, encounter.current_context,
                                         encounter.current_assessment)
        reason = _second_review_blocker(encounter, revision, context, assessment)
        if reason:
            raise Refused(reason)
        items, _ = _second_review_items(assessment)
        clear_stop(encounter)
        job = enqueue(Job.REVIEW2, encounter=encounter, revision=revision, context=context,
                      provider_run=assessment.provider_run, key=f'review2:{revision.pk}:{assessment.pk}',
                      requested_by=user)
        if job.state != Job.QUEUED:
            raise Refused('A second review was already requested for this assessment.')
        audit.record(encounter.workspace, 'provider.second_review_requested', encounter=encounter, actor=user,
                     items=[item.get('label', '') for item in items][:8])
        review.refresh_state(encounter)
    return job


def stage_review2(job):
    revision, encounter, context, primary = job.revision, job.encounter, job.context, job.provider_run
    encounter.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists; nothing was sent'}
    if context is None or encounter.current_context_id != context.pk or context.version in EARLIER_CONTEXT_VERSIONS:
        return {'skipped': 'the context changed; nothing was sent'}
    assessment = encounter.current_assessment
    if (assessment is None or assessment.revision_id != revision.pk or assessment.context_id != context.pk
            or primary is None or assessment.provider_run_id != primary.pk):
        return {'skipped': 'the assessment changed; nothing was sent'}
    provider = get_provider()
    if provider is None:
        return {'skipped': 'the provider is disabled; nothing was sent'}
    service_date = context_service_date(context)
    if service_date != primary.service_date:
        return {'skipped': 'the service date changed; nothing was sent'}
    items, span = _second_review_items(assessment)
    if not items or span is None or span[1] - span[0] > SECOND_REVIEW_MAX_CHARS:
        return {'skipped': 'nothing to ask about; nothing was sent'}
    start, end = span
    scope = {'start': start, 'end': end, 'primary_run': str(primary.pk), 'assessment': str(assessment.pk),
             'items': [item.get('label', '') for item in items][:8]}

    def next_assess(run):
        enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=primary,
                key=f'assess:{context.pk}:{primary.pk}:review2:{run.pk}', requested_by=job.requested_by)

    try:
        request = provider.build_request(revision.text[start:end], service_date)
    except ProviderUnavailable as exc:
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=provider.name, adapter_version=provider.adapter_version,
            request_sha256='', request_body={}, contexts=[], state=models.ProviderRun.NOT_SENT, error=str(exc),
            authorization_ref=settings.AUTHORIZATION_REF, requested_by=job.requested_by, service_date=service_date,
            purpose=models.ProviderRun.SECOND_REVIEW, scope=scope, finished_at=timezone.now())
        next_assess(run)
        return {'second_review': 'not_sent'}
    if request.canonical_sha256 == primary.request_sha256 or models.ProviderRun.objects.filter(
            encounter__workspace=encounter.workspace, provider=provider.name, adapter_version=provider.adapter_version,
            request_sha256=request.canonical_sha256, state=models.ProviderRun.SUCCEEDED,
            purpose=models.ProviderRun.PRIMARY).exists():
        # The excerpt is the whole text (a report that opens with its title): the request repeats a primary request
        # already answered, so it asks nothing new and is never sent (refutation r1: a byte-identical paid resend).
        return {'skipped': 'the second review would repeat a primary request already answered; nothing was sent'}
    prior = models.ProviderRun.objects.filter(
        encounter__workspace=encounter.workspace, provider=provider.name, adapter_version=provider.adapter_version,
        request_sha256=request.canonical_sha256, state=models.ProviderRun.SUCCEEDED, reused_from__isnull=True,
        purpose=models.ProviderRun.SECOND_REVIEW).order_by('created_at').first()
    if prior is not None:
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=prior.provider, adapter_version=prior.adapter_version,
            request_sha256=prior.request_sha256, request_body=prior.request_body, contexts=prior.contexts,
            state=models.ProviderRun.SUCCEEDED, sent=False, http_status=prior.http_status,
            provider_request_id=prior.provider_request_id, response_sha256=prior.response_sha256,
            response_bytes=bytes(prior.response_bytes), usage={}, usage_basis='reused_retained_result_no_new_usage',
            authorization_ref=settings.AUTHORIZATION_REF, requested_by=job.requested_by, reused_from=prior,
            service_date=service_date, purpose=models.ProviderRun.SECOND_REVIEW, scope=scope,
            started_at=timezone.now(), finished_at=timezone.now())
        audit.record(encounter.workspace, 'provider.reused', encounter=encounter, run=str(run.pk), reused_from=str(prior.pk),
                     purpose=models.ProviderRun.SECOND_REVIEW)
        next_assess(run)
        return {'second_review': 'reused', 'run': str(run.pk)}
    if _unreconciled_unknown(encounter):
        return {'blocked': 'a previous request has an unknown outcome; reconcile it before sending again'}
    _live_gate(job, provider, revision, encounter)
    run = _send(job, provider, request, service_date=service_date, purpose=models.ProviderRun.SECOND_REVIEW,
                scope=scope)
    next_assess(run)
    return {'second_review': run.state, 'run': str(run.pk)}


STAGES = {Job.EXTRACT: stage_extract, Job.ANALYZE: stage_analyze, Job.PREDICT: stage_predict, Job.ASSESS: stage_assess,
          Job.REVIEW2: stage_review2}


# --- worker ------------------------------------------------------------------

def claim_next():
    """Claim the oldest runnable job, expiring or cancelling as needed."""
    with transaction.atomic():
        job = (Job.objects.select_for_update(skip_locked=True).filter(state=Job.QUEUED)
               .order_by('created_at').first())
        if job is None:
            return None
        now = timezone.now()
        if job.stop_requested_at or is_stopped(job.encounter_id):
            job.state, job.error, job.finished_at = Job.CANCELLED, 'Stopped before it started.', now
        elif job.deadline_at < now:
            # Nothing ran, so nothing was recorded: the stage stays resumable rather than failing the encounter.
            job.state, job.error, job.finished_at = (Job.CANCELLED, 'The stage expired before it could start; '
                                                     'resume to run it.', now)
        else:
            job.state, job.started_at = Job.RUNNING, now
            job.attempts += 1
        job.save(update_fields=['state', 'error', 'started_at', 'finished_at', 'attempts'])
        return job


def run_job(job):
    if job.state != Job.RUNNING:
        review.refresh_state(job.encounter)
        return job
    handler = STAGES[job.kind]
    try:
        job.result = handler(job) or {}
        job.state = Job.SUCCEEDED
    except Requeue as exc:
        job.state, job.started_at = Job.QUEUED, None
        job.attempts = max(job.attempts - 1, 0)
        job.result = {'requeued': str(exc)}
    except StageCancelled as exc:
        job.state, job.error = Job.CANCELLED, str(exc)
    except StageFailure as exc:
        job.state, job.error = Job.FAILED, str(exc)
    except Exception:  # noqa: BLE001 — recorded, never shown with internals
        log.exception('stage %s failed for job %s', job.kind, job.pk)
        job.state, job.error = Job.FAILED, f'The {job.kind} stage failed unexpectedly; the error was logged.'
    finally:
        release_routing_caches()
    if job.state != Job.QUEUED:
        job.finished_at = timezone.now()
    # Only the columns the worker owns: a Stop recorded on this row meanwhile must survive.
    job.save(update_fields=['state', 'started_at', 'attempts', 'result', 'error', 'finished_at'])
    if job.state == Job.QUEUED:
        time.sleep(1)
    review.refresh_state(job.encounter)
    return job


def mark_stale():
    """Settle jobs a dead worker left 'running'. A send in flight becomes UNKNOWN, never resent."""
    cutoff = timezone.now() - timedelta(seconds=settings.STALE_RUNNING_SECONDS)
    for job in Job.objects.filter(state=Job.RUNNING, started_at__lt=cutoff):
        with transaction.atomic():
            # A predict whose run had already FINISHED when the worker died (its outcome recorded, the assess not
            # yet queued) is settled by that run, exactly as the stage would have settled it, so a Resume can
            # never re-send an identical request that already failed. Read before reserved runs are settled below.
            finished = None
            sends = job.kind in (Job.PREDICT, Job.REVIEW2)
            if sends and job.context_id:
                purpose = models.ProviderRun.PRIMARY if job.kind == Job.PREDICT else models.ProviderRun.SECOND_REVIEW
                finished = (models.ProviderRun.objects
                            .filter(revision=job.revision, created_at__gte=job.started_at, purpose=purpose,
                                    state__in=(models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED,
                                               models.ProviderRun.UNKNOWN, models.ProviderRun.NOT_SENT))
                            .order_by('-created_at').first())
            sending = models.ProviderRun.objects.filter(revision=job.revision, state=models.ProviderRun.SENDING)
            reserved = models.ProviderRun.objects.filter(revision=job.revision, state=models.ProviderRun.RESERVED)
            unknown = sends and sending.exists()
            for run in sending:
                run.state, run.error, run.finished_at = (models.ProviderRun.UNKNOWN,
                                                         'The worker stopped while the request was in flight.',
                                                         timezone.now())
                run.save(update_fields=['state', 'error', 'finished_at'])
            for run in reserved:
                run.state, run.error, run.finished_at = (models.ProviderRun.NOT_SENT,
                                                         'The worker stopped before sending.', timezone.now())
                run.save(update_fields=['state', 'error', 'finished_at'])
            if finished is not None and not unknown:
                primary = finished if job.kind == Job.PREDICT else job.provider_run
                enqueue(Job.ASSESS, encounter=job.encounter, revision=job.revision, context=job.context,
                        provider_run=primary, key=f'assess:{job.context_id}:{primary.pk}'
                        + ('' if job.kind == Job.PREDICT else f':review2:{finished.pk}'),
                        requested_by=job.requested_by)
                job.state, job.error = Job.SUCCEEDED, ''
                job.result = {'provider': finished.state, 'run': str(finished.pk),
                              'settled': 'the worker stopped after the provider outcome was recorded'}
            else:
                # A send in flight is unknown (reconcile it); any other stage recorded nothing it would not redo,
                # so it is cancelled and can be resumed rather than stranding the encounter.
                job.state = Job.UNKNOWN if unknown else Job.CANCELLED
                job.error = ('The worker stopped while this stage was running.' if unknown else
                             'The worker stopped while this stage was running; resume to run it again.')
            job.finished_at = timezone.now()
            job.save(update_fields=['state', 'error', 'result', 'finished_at'])
        review.refresh_state(job.encounter)


def remove_stale_ingest_dirs():
    """A worker killed mid-extraction can leave its child's work directory (it may hold a PDF copy)."""
    import shutil
    import tempfile
    from pathlib import Path

    for path in Path(tempfile.gettempdir()).glob('cpt-ingest-*'):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)


def work(should_stop, *, poll_seconds=1.0, clock=time.monotonic):
    remove_stale_ingest_dirs()
    mark_stale()
    swept = clock()
    while not should_stop():
        # A worker that died mid-stage and came straight back must still settle that stage
        # once it is old enough, so the sweep repeats rather than running only at start.
        if clock() - swept >= STALE_SWEEP_SECONDS:
            mark_stale()
            swept = clock()
        job = claim_next()
        if job is None:
            time.sleep(poll_seconds)
            continue
        run_job(job)


# --- member actions ----------------------------------------------------------
#
# Every action that can queue a stage runs inside one transaction holding the
# encounter row lock, and refuses while any stage is queued or running. So at
# most one stage chain is ever queued per encounter, each provider attempt
# answers exactly one member action, and two concurrent actions cannot
# interleave their reads and writes.

def busy(encounter):
    return encounter.jobs.filter(state__in=[Job.QUEUED, Job.RUNNING]).exists()


def _locked(encounter):
    return models.Encounter.objects.select_for_update().get(pk=encounter.pk)


def stop_encounter(encounter, user):
    now = timezone.now()
    with transaction.atomic():
        models.Encounter.objects.filter(pk=encounter.pk).update(stopped_at=now, stopped_by=user)
        stopped = 0
        for job in encounter.jobs.select_for_update().filter(state__in=[Job.QUEUED, Job.RUNNING]):
            job.stop_requested_at, job.stop_requested_by = now, user
            if job.state == Job.QUEUED:
                job.state, job.error, job.finished_at = Job.CANCELLED, 'Stopped by a workspace member.', now
            job.save(update_fields=['stop_requested_at', 'stop_requested_by', 'state', 'error', 'finished_at'])
            stopped += 1
    audit.record(encounter.workspace, 'pipeline.stopped', encounter=encounter, actor=user, jobs=stopped)
    review.refresh_state(encounter)
    return stopped


def resume(encounter, user):
    """Re-enqueue the stage a Stop cancelled, under a fresh key."""
    with transaction.atomic():
        encounter = _locked(encounter)
        if busy(encounter):
            raise Refused('Wait for processing to finish (or stop it) before resuming.')
        # The same rule as the API's can_resume: only the current revision's LATEST stage, when it was
        # cancelled (a Stop, the stale-stage sweep or a queue expiry), runs again - never an older one.
        if not review.can_resume(encounter):
            return None
        last = review.latest_job(encounter)
        context = encounter.current_context if last.kind in {Job.PREDICT, Job.ASSESS} else last.context
        if last.kind == Job.ASSESS and context is not None and last.context_id != context.pk:
            kind, provider_run = Job.PREDICT, None  # the context changed while stopped: re-run from predict
        elif last.kind == Job.EXTRACT and last.revision.extraction_status in {models.SourceRevision.OK,
                                                                               models.SourceRevision.PARTIAL}:
            kind, provider_run = Job.ANALYZE, None  # the text was recorded before the stage was cut short
        else:
            kind, provider_run = last.kind, last.provider_run
        clear_stop(encounter)
        key = f'{last.idempotency_key}:resume:{uuid.uuid4()}'
        if kind == Job.PREDICT:
            job = _queue_predict(encounter, last.revision, context, key=key, requested_by=user)
        else:
            job = enqueue(kind, encounter=encounter, revision=last.revision, context=context,
                          provider_run=provider_run, key=key, requested_by=user)
        audit.record(encounter.workspace, 'pipeline.resumed', encounter=encounter, actor=user, stage=last.kind)
        review.refresh_state(encounter)
    return job


def reconcile(encounter, run, user, note):
    """Record a member's reconciliation of an UNKNOWN outcome and allow one new attempt.

    True when recorded, None when ``run`` is not an unreconciled unknown outcome.
    The one attempt is a predict for the current revision's current context; when
    the current revision has no context (its extraction failed) nothing is queued.
    """
    with transaction.atomic():
        encounter = _locked(encounter)
        if busy(encounter):
            raise Refused('Wait for processing to finish (or stop it) before reconciling.')
        run = models.ProviderRun.objects.select_for_update().get(pk=run.pk, encounter=encounter)
        if run.state != models.ProviderRun.UNKNOWN or run.reconciled_at is not None:
            return None
        run.reconciled_by, run.reconciled_at, run.reconciliation_note = user, timezone.now(), note
        run.save(update_fields=['reconciled_by', 'reconciled_at', 'reconciliation_note'])
        revision, context = encounter.current_revision, encounter.current_context
        clear_stop(encounter)
        if context is not None and revision is not None and context.revision_id == revision.pk:
            _queue_predict(encounter, revision, context, key=f'predict:{context.pk}:after-reconcile:{run.pk}',
                           requested_by=user)
        audit.record(encounter.workspace, 'provider.reconciled', encounter=encounter, actor=user, run=str(run.pk))
        review.refresh_state(encounter)
    return True


def _run_answers(run, revision, context):
    """Whether ``run`` already answers the request the provider would build for ``context`` now.

    Compared on the request itself (provider, adapter and canonical request hash), never
    on the previous context: the run in use may have been requested for another date.
    Whatever that run's outcome: a setting or billing change that leaves the request
    unchanged re-checks and never re-sends the primary request (ARCHITECTURE 5.4), so a
    failed or not-sent request is never re-sent behind a metadata save. The re-check may
    still make the one bounded second review its revision and date have not had (5.11).
    """
    if run is None or not run.request_sha256:
        return False
    try:
        provider = get_provider()
        if provider is None or (provider.name, provider.adapter_version) != (run.provider, run.adapter_version):
            return False
        request = provider.build_request(revision.text, context_service_date(context))
    except ProviderUnavailable:
        return False
    return request.canonical_sha256 == run.request_sha256


def _run_in_use(revision):
    """The provider run whose outcome stands for ``revision``: its newest request that finished.

    That is so whether or not an assessment was made with it. A member's Stop during the send, a swept assess or an
    expired one cancels the assess that would have used it, and a Resume would re-assess with it, so a context change
    does the same (round 3, orchestrator:0). A reconciled unknown outcome no longer stands: the member released it for
    one new attempt, which a context change must not consume by re-assessing with it.

    A run the stale-stage sweep settled as not sent because its worker stopped after reserving it is no outcome at
    all: it carries its request but never reached the send (no started_at), so the attempt it reserved still has to
    be made, as a Resume of that predict makes it (round 4, pipeline:2). Every other not-sent run stands: one the
    provider exchange answered went through the send, and one recorded when no request could be built carries no
    request to compare.
    """
    from django.db.models import Q

    finished = (models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED, models.ProviderRun.NOT_SENT,
                models.ProviderRun.UNKNOWN)
    reserved_then_swept = (Q(state=models.ProviderRun.NOT_SENT) & Q(started_at__isnull=True)
                           & ~Q(request_sha256=''))
    run = (revision.provider_runs.filter(state__in=finished, purpose=models.ProviderRun.PRIMARY)
           .exclude(reserved_then_swept).order_by('-created_at').first())
    if run is None or (run.state == models.ProviderRun.UNKNOWN and run.reconciled_at is not None):
        return None
    return run


def change_context(encounter, user, values):
    """Apply member-supplied metadata, snapshot a new context and re-assess.

    Re-assesses with the run already in use only when that run answers exactly the
    request the new context would send; otherwise re-predicts (an identical retained
    result is still reused for free by the predict stage, and a date the revision was
    never routed for is routed first).
    """
    with transaction.atomic():
        encounter = _locked(encounter)
        revision = encounter.current_revision
        if revision is None or revision.extraction_status not in {models.SourceRevision.OK,
                                                                  models.SourceRevision.PARTIAL}:
            raise Refused('Context can be set once the document text has been extracted.')
        if busy(encounter):
            raise Refused('Wait for processing to finish (or stop it) before changing context.')
        if not models.RoutingRun.objects.filter(revision=revision).exists() and not review.can_resume(encounter):
            # Its analysis overran or failed, so nothing may be sent for it, whatever the context says: the request
            # would answer a document the service could not read (round 5, pipeline:0). A stage that was only stopped
            # - a Stop, the stale-stage sweep or a queue expiry, the rule resume uses - is not refused (round 6
            # pipeline:1): its document is readable, and the predict below routes the new date before anything is
            # sent (round 6 pipeline:0), so the one request is for the member's date and never first for the
            # document's own.
            raise Refused('This document could not be read to the end, so its context cannot be changed and nothing '
                          'is sent for it. Upload it again, shorter or split.')
        merged = dict(encounter.user_values or {})
        for key, value in values.items():
            if value:
                merged[key] = value
            else:
                merged.pop(key, None)
        encounter.user_values = merged
        encounter.save(update_fields=['user_values', 'updated_at'])
        context = make_context(encounter, revision, created_by=user, seconds=settings.CONTEXT_REQUEST_SECONDS,
                               refusal=Refused)
        encounter.current_context = context
        encounter.save(update_fields=['current_context', 'updated_at'])
        audit.record(encounter.workspace, 'context.changed', encounter=encounter, actor=user,
                     fields=sorted(values), context=str(context.pk))
        last_run = _run_in_use(revision)
        clear_stop(encounter)
        if _run_answers(last_run, revision, context):
            enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=last_run,
                    key=f'assess:{context.pk}:{last_run.pk}', requested_by=user)
        else:
            _queue_predict(encounter, revision, context, key=f'predict:{context.pk}', requested_by=user)
        review.refresh_state(encounter)
    return context
