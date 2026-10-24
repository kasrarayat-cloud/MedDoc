"""Pipeline jobs: extract -> analyze -> predict -> assess (ARCHITECTURE section 5).

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
import time
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from . import audit, models, review
from .gi import context as gi_context
from .gi import detect as gi_detect
from .ingest import Limits, extract_document, extract_paste
from .providers import get_provider, normalizer_for
from .providers.base import ProviderUnavailable
from .reference.store import DbReferenceLookup
from .storage import read_original
from .types import Fact, PageSpan, ProviderRequest, RoutingResult, from_jsonable, sha256_json, to_jsonable
from .validation.engine import assess as run_assessment

log = logging.getLogger(__name__)

CONTEXT_VERSION = 'gi-context@1'
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


# --- helpers -----------------------------------------------------------------

def _limits():
    return Limits(timeout_s=settings.EXTRACTION_TIMEOUT_SECONDS, max_pages=settings.MAX_PDF_PAGES,
                  max_chars=settings.MAX_PASTE_CHARS, max_bytes=settings.MAX_UPLOAD_BYTES)


def context_facts(context) -> dict[str, Fact]:
    return {name: from_jsonable(Fact, value) for name, value in (context.facts or {}).items()}


def context_service_date(context):
    fact = (context.facts or {}).get('service_date') or {}
    if fact.get('origin') not in {'document', 'user'} or not fact.get('value'):
        return None
    try:
        return date.fromisoformat(fact['value'])
    except ValueError:
        return None


def make_context(encounter, revision, *, created_by=None):
    """Snapshot document facts merged with the encounter's member-supplied values."""
    document_facts = gi_context.extract_context(revision.text)
    merged = gi_context.merge_user_values(document_facts, dict(encounter.user_values or {}))
    facts = {name: to_jsonable(fact) for name, fact in merged.items()}
    user_values = dict(encounter.user_values or {})
    return models.EncounterContext.objects.create(
        encounter=encounter, revision=revision, facts=facts, user_values=user_values, version=CONTEXT_VERSION,
        sha256=sha256_json({'facts': facts, 'user_values': user_values, 'revision': str(revision.pk)}),
        created_by=created_by)


def routing_for(revision, service_date=None):
    """The deterministic routing of a revision for an effective service date, stored once per distinct result."""
    result = gi_detect.route(revision.text, service_date)
    data = to_jsonable(result)
    digest = sha256_json(data)
    existing = models.RoutingRun.objects.filter(revision=revision, version=result.version, sha256=digest).first()
    if existing:
        return existing
    return models.RoutingRun.objects.create(revision=revision, version=result.version, result=data, sha256=digest)


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
    context = make_context(encounter, revision)
    routing = routing_for(revision, context_service_date(context))
    with transaction.atomic():
        locked = models.Encounter.objects.select_for_update().get(pk=encounter.pk)
        if locked.current_revision_id == revision.pk:
            locked.current_context = context
            locked.save(update_fields=['current_context', 'updated_at'])
    enqueue(Job.PREDICT, encounter=encounter, revision=revision, context=context, key=f'predict:{context.pk}',
            requested_by=job.requested_by)
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


def stage_predict(job):
    revision, encounter, context = job.revision, job.encounter, job.context
    encounter.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists; nothing was sent'}
    if context is None or context.revision_id != revision.pk or encounter.current_context_id != context.pk:
        # Provider input is only ever the current revision's text with that revision's current context.
        return {'skipped': 'the context is not the current one for this revision; nothing was sent'}
    provider = get_provider()
    service_date = context_service_date(context)
    assess_key = f'assess:{context.pk}'

    def next_assess(run):
        enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=run,
                key=f'{assess_key}:{run.pk if run else "no-provider"}', requested_by=job.requested_by)

    if provider is None:
        next_assess(None)
        return {'provider': 'disabled'}
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

    # Reuse a retained result for the identical request instead of paying twice.
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

    if provider.mode == 'live':
        if not settings.SYNTHETIC_ONLY or revision.synthetic_attested_at is None:
            raise StageFailure('Live provider calls require a synthetic-attested document.')
        if not settings.AUTHORIZATION_REF:
            raise StageFailure('Live provider calls are not authorized on this installation.')
        membership = models.Membership.objects.filter(user=job.requested_by, workspace=encounter.workspace,
                                                      active=True).first()
        if membership is None or not membership.can_review:
            raise StageFailure('Only an owner or reviewer of this workspace can start a live provider request.')

    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [PROVIDER_LOCK_KEY])
        if not cursor.fetchone()[0]:
            raise Requeue('another provider request is in flight')
    try:
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=provider.name, adapter_version=provider.adapter_version,
            request_sha256=request.canonical_sha256, request_body=request.body, contexts=list(request.contexts),
            state=models.ProviderRun.RESERVED, authorization_ref=settings.AUTHORIZATION_REF,
            requested_by=job.requested_by, service_date=service_date)
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
                     run_identity=str(run.run_identity))
        exchange = provider.send(request, deadline_s=settings.PROVIDER_READ_TIMEOUT_SECONDS + 30)
        _finish_run(run, exchange)
        audit.record(encounter.workspace, 'provider.finished', encounter=encounter, run=str(run.pk),
                     state=run.state, http_status=run.http_status, usage=run.usage, latency_ms=run.latency_ms)
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK_KEY])
    next_assess(run)
    return {'provider': run.state, 'run': str(run.pk)}


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
    revision.refresh_from_db()
    if run is not None and run_service_date(run) != context_service_date(context):
        raise StageFailure('The provider result was requested for a different service date than this context; '
                           'it was not used. Change the context again to request proposals for this date.')
    routing_run = routing_for(revision, context_service_date(context))
    provider_status, normalized = _provider_inputs(run)
    result = run_assessment(
        text=revision.text, pages=tuple(PageSpan(**p) for p in revision.pages), context=context_facts(context),
        routing=from_jsonable(RoutingResult, routing_run.result), normalized=normalized,
        reference=DbReferenceLookup(), service_date=context_service_date(context), provider_status=provider_status,
        extraction_status=revision.extraction_status, extraction_messages=tuple(revision.messages))
    try:
        assessment = review.persist_assessment(encounter=encounter, revision=revision, context=context,
                                               routing_run=routing_run, provider_run=run, result=result)
    except ValueError as exc:
        raise StageFailure(f'The assessment was not recorded: {exc}') from exc
    return {'assessment': str(assessment.pk), 'provider_status': provider_status}


STAGES = {Job.EXTRACT: stage_extract, Job.ANALYZE: stage_analyze, Job.PREDICT: stage_predict, Job.ASSESS: stage_assess}


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
            if job.kind == Job.PREDICT and job.context_id:
                finished = (models.ProviderRun.objects
                            .filter(revision=job.revision, created_at__gte=job.started_at,
                                    state__in=(models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED,
                                               models.ProviderRun.UNKNOWN, models.ProviderRun.NOT_SENT))
                            .order_by('-created_at').first())
            sending = models.ProviderRun.objects.filter(revision=job.revision, state=models.ProviderRun.SENDING)
            reserved = models.ProviderRun.objects.filter(revision=job.revision, state=models.ProviderRun.RESERVED)
            unknown = job.kind == Job.PREDICT and sending.exists()
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
                enqueue(Job.ASSESS, encounter=job.encounter, revision=job.revision, context=job.context,
                        provider_run=finished, key=f'assess:{job.context_id}:{finished.pk}',
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
        job = enqueue(kind, encounter=encounter, revision=last.revision, context=context,
                      provider_run=provider_run, key=f'{last.idempotency_key}:resume:{uuid.uuid4()}',
                      requested_by=user)
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
            enqueue(Job.PREDICT, encounter=encounter, revision=revision, context=context,
                    key=f'predict:{context.pk}:after-reconcile:{run.pk}', requested_by=user)
        audit.record(encounter.workspace, 'provider.reconciled', encounter=encounter, actor=user, run=str(run.pk))
        review.refresh_state(encounter)
    return True


def _run_answers(run, revision, context):
    """Whether ``run`` already answers the request the provider would build for ``context`` now.

    Compared on the request itself (provider, adapter and canonical request hash), never
    on the previous context: the run in use may have been requested for another date.
    Whatever that run's outcome: a setting or billing change that leaves the request
    unchanged re-checks and never sends (ARCHITECTURE 5.4), so a failed or not-sent
    request is never re-sent behind a metadata save.
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


def change_context(encounter, user, values):
    """Apply member-supplied metadata, snapshot a new context and re-assess.

    Re-assesses with the run already in use only when that run answers exactly the
    request the new context would send; otherwise re-predicts (an identical retained
    result is still reused for free by the predict stage).
    """
    with transaction.atomic():
        encounter = _locked(encounter)
        revision = encounter.current_revision
        if revision is None or revision.extraction_status not in {models.SourceRevision.OK,
                                                                  models.SourceRevision.PARTIAL}:
            raise Refused('Context can be set once the document text has been extracted.')
        if busy(encounter):
            raise Refused('Wait for processing to finish (or stop it) before changing context.')
        merged = dict(encounter.user_values or {})
        for key, value in values.items():
            if value:
                merged[key] = value
            else:
                merged.pop(key, None)
        encounter.user_values = merged
        encounter.save(update_fields=['user_values', 'updated_at'])
        context = make_context(encounter, revision, created_by=user)
        encounter.current_context = context
        encounter.save(update_fields=['current_context', 'updated_at'])
        audit.record(encounter.workspace, 'context.changed', encounter=encounter, actor=user,
                     fields=sorted(values), context=str(context.pk))
        assessment = encounter.current_assessment
        last_run = assessment.provider_run if assessment and assessment.revision_id == revision.pk else None
        clear_stop(encounter)
        if _run_answers(last_run, revision, context):
            enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=last_run,
                    key=f'assess:{context.pk}:{last_run.pk}', requested_by=user)
        else:
            enqueue(Job.PREDICT, encounter=encounter, revision=revision, context=context,
                    key=f'predict:{context.pk}', requested_by=user)
        review.refresh_state(encounter)
    return context
