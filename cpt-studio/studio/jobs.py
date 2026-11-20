"""The coding pipeline's jobs (BUILD-SPEC sections 1 and 3) and the worker machinery they run on.

upload, answers or retry -> start_round -> Job kind 'code' -> stage_code: prepare the document -> the READER send ->
the CHECKER send -> combine (studio.fable.result) -> the round done -> the encounter state (studio.state).

The worker is one process running CPT_STUDIO_CONCURRENT_DOCUMENTS threads, each claiming queued jobs with
SELECT ... FOR UPDATE SKIP LOCKED on its own database connection. One chain per encounter: every member action that
queues a job holds the encounter row lock and refuses while one is queued or running. Every send is checked against
the document's spending ceiling - its worst case counts every attempt it may make, its server-side fallback's included,
from the API's free token count, and with no count nothing is sent -, takes one of N provider slots without waiting
(none free: the job is queued again) and is reserved in the database before any network I/O; a member's Stop is
observed before each send. Nothing is ever sent again automatically: a round reuses a read it already paid for; an
outcome that may have reached the vendor is recorded unknown, and Resume and Retry of its round wait for an operator's
reconcile; a stage that died is settled as it would have settled itself, never cancelled past a send it made.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.conf import settings
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.models import Q
from django.utils import timezone

from . import audit, models, state
from .storage import OriginalCorrupted, read_original, store_original
from .fable import (BUSY, CEILING, CONVERT, DECLINED, DOCUMENT, FAILED, HOLD, STORAGE, TOO_LONG, UNAVAILABLE,
                    UNKNOWN, UNREADABLE)
from .fable import client as fable_client
from .fable import document as fable_document
from .fable import pricing, prompts
from .fable import result as fable_result

log = logging.getLogger(__name__)

Job, Round, Run = models.Job, models.CodingRound, models.ProviderRun
CODE = 'code'  # Job.kind of the coding stage
READER, CHECKER = 'coding_reader', 'coding_checker'  # ProviderRun.purpose of its two sends
PURPOSES = (READER, CHECKER)
PROVIDER = 'anthropic'
ADAPTER_VERSION = 'cptstudio-fable-coder@1'
PROVIDER_LOCK_KEY = 0x435054535455  # 'CPTSTU': slot n is the advisory lock PROVIDER_LOCK_KEY + n
INSURANCE = ('medicare', 'medicaid', 'commercial', 'unknown')
# A job that cannot start within this window expires (cancelled, resumable).
QUEUE_DEADLINE = timedelta(minutes=120)
REQUEUE_SECONDS = 2  # a job queued again (no free slot) waits this long in its thread
STALE_SWEEP_SECONDS = 60  # how often the running worker settles stages a dead thread or process left 'running'
# A running code job no thread of this process runs is taken for dead after this long: two sends of up to 96,000
# output tokens at max effort (about 1,000 s each at the slowest rate measured, 100 tokens a second) and the document's
# preparation, with margin. The worker's own threads are never swept (_live).
CODE_STALE_SECONDS = 3600
RECONCILE_NOTE_CHARS = 12
STOPPED_MESSAGE = 'Stopped by a workspace member; nothing more was sent.'
BUSY_MESSAGE = 'Wait for processing to finish (or stop it) first.'
RETRY_NOTHING = 'There is no failed coding to try again.'
# Resume or Retry of a round with a send whose outcome is not known and no operator's reconcile yet (FIX-SPEC 4).
RECONCILE_FIRST = 'Whether the last coding finished is not known yet. It can run again once it has been checked.'
FAILURE_TEXT = {
    UNREADABLE: 'The coding result could not be read. Try again.',
    CEILING: 'This document reached its spending limit.',
    HOLD: 'Coding is paused on this installation. Try again later.',
    BUSY: 'The coding service is busy. Try again in a few minutes.',
    CONVERT: fable_document.CONVERT_TEXT,
    DOCUMENT: 'This document could not be read.',
    DECLINED: 'This document could not be coded.',
    TOO_LONG: 'The coding result was too long to finish. Try again, or split the document.',
    UNKNOWN: 'Coding was interrupted, and whether it finished is not known. It can be tried again once it has been '
             'checked.',
    FAILED: 'Coding did not finish. Try again.',
    UNAVAILABLE: 'Coding is not available right now.',
    STORAGE: fable_document.STORAGE_TEXT,
}


class StageFailure(Exception):
    """A stage failed for a reason the member should read."""


class StageCancelled(Exception):
    """The stage observed a Stop and ended without sending anything more."""


class Requeue(Exception):
    """The stage could not start its send now (every provider slot is in use); it is queued again."""


class Refused(Exception):
    """A member action was refused; the message says why (the API answers 409)."""


def failure_text(kind: str, document=None) -> str:
    """The customer's sentence for a round that failed with ``kind`` (the document's own wording for DOCUMENT)."""
    if kind == DOCUMENT and document is not None:
        return fable_document.REFUSED_TEXT.get(document.kind, FAILURE_TEXT[DOCUMENT])
    return FAILURE_TEXT.get(kind, FAILURE_TEXT[FAILED])


# --- enqueueing and member actions -------------------------------------------------------------------------------------

def enqueue(kind, *, encounter, revision, key, requested_by=None):
    """Create the job for ``key`` once. A repeated key returns the existing job."""
    job, _ = Job.objects.get_or_create(
        idempotency_key=key,
        defaults={'encounter': encounter, 'revision': revision, 'kind': kind, 'requested_by': requested_by,
                  'deadline_at': timezone.now() + QUEUE_DEADLINE})
    return job


def clear_stop(encounter):
    """A member asked for processing again: lift the encounter's Stop."""
    models.Encounter.objects.filter(pk=encounter.pk).update(stopped_at=None, stopped_by=None)


def is_stopped(encounter_id):
    return models.Encounter.objects.filter(pk=encounter_id, stopped_at__isnull=False).exists()


def busy(encounter):
    return encounter.jobs.filter(state__in=[Job.QUEUED, Job.RUNNING]).exists()


def _locked(encounter):
    return models.Encounter.objects.select_for_update().get(pk=encounter.pk)


def latest_round(encounter):
    return Round.objects.filter(encounter_id=encounter.pk).order_by('-number').first()


def context_snapshot(encounter) -> dict:
    """A round's context (BUILD-SPEC 2): the service date and insurance a member entered (Encounter.user_values),
    and every answer so far, oldest first."""
    values = encounter.user_values if isinstance(encounter.user_values, dict) else {}
    service_date = values.get('service_date')
    insurance = values.get('insurance')
    answers = models.CodingAnswer.objects.filter(encounter_id=encounter.pk).order_by('answered_at', 'pk')
    return {'service_date': service_date if isinstance(service_date, str) and service_date.strip() else None,
            'insurance': insurance if insurance in INSURANCE else 'unknown',
            'answers': [{'question': answer.question, 'answer': answer.answer} for answer in answers]}


def start_round(encounter, revision, trigger, by):
    """A new coding round of ``revision`` (number = last + 1, queued, with the context as it is now) and its job
    ('code:<round>'). Upload, answers and retry call it; refused while a job of the encounter is queued or running.
    Lifts the encounter's Stop."""
    if trigger not in (Round.UPLOAD, Round.ANSWERS, Round.RETRY):
        raise ValueError(f'{trigger!r} is not a coding round trigger.')
    with transaction.atomic():
        locked = _locked(encounter)
        if revision.encounter_id != locked.pk:
            raise ValueError('The revision belongs to another encounter.')
        if busy(locked):
            raise Refused(BUSY_MESSAGE)
        last = latest_round(locked)
        round_ = Round.objects.create(encounter=locked, revision=revision, number=last.number + 1 if last else 1,
                                      trigger=trigger, context=context_snapshot(locked))
        clear_stop(locked)
        enqueue(CODE, encounter=locked, revision=revision, key=f'{CODE}:{round_.pk}', requested_by=by)
        audit.record(locked.workspace, 'coding.round_queued', encounter=locked, actor=by, round=str(round_.pk),
                     number=round_.number, trigger=trigger)
        state.refresh(locked)
    return round_


def stop_encounter(encounter, user):
    """A member's Stop: queued jobs are cancelled (their rounds with them); a running one stops before its next send."""
    now = timezone.now()
    with transaction.atomic():
        models.Encounter.objects.filter(pk=encounter.pk).update(stopped_at=now, stopped_by=user)
        stopped = 0
        for job in encounter.jobs.select_for_update().filter(state__in=[Job.QUEUED, Job.RUNNING]):
            job.stop_requested_at, job.stop_requested_by = now, user
            if job.state == Job.QUEUED:
                job.state, job.error, job.finished_at = Job.CANCELLED, 'Stopped by a workspace member.', now
                _cancel_queued_round(job)
            job.save(update_fields=['stop_requested_at', 'stop_requested_by', 'state', 'error', 'finished_at'])
            stopped += 1
    audit.record(encounter.workspace, 'pipeline.stopped', encounter=encounter, actor=user, jobs=stopped)
    state.refresh(encounter)
    return stopped


def awaiting_reconcile(round_) -> bool:
    """Whether a send of ``round_`` may have reached the vendor with no outcome known and no operator's reconcile yet: an
    UNKNOWN run not reconciled, or a run still marked sending whose stage no longer records it. Resume and Retry of the
    round wait for the reconcile (FIX-SPEC 4), so that read is not sent again, by anyone, before someone has looked."""
    return Run.objects.filter(purpose__in=PURPOSES, scope__round=str(round_.pk)).filter(
        Q(state=Run.SENDING) | Q(state=Run.UNKNOWN, reconciled_at__isnull=True)).exists()


def resume(encounter, user):
    """Queue the latest round again when it was cancelled (a Stop, an expired queue, a worker that stopped): a fresh
    job for the same round, which reuses any read the round already has. None when there is nothing to resume - and
    when a send of the round failed though the round was closed as stopped (by an earlier close, say): the round then
    ends failed with that send's kind, and its read is not sent again. Refused while a send of the round awaits an
    operator's reconcile (awaiting_reconcile)."""
    with transaction.atomic():
        locked = _locked(encounter)
        if busy(locked):
            raise Refused(BUSY_MESSAGE)
        round_ = latest_round(locked)
        if round_ is None or round_.state not in (Round.CANCELLED, Round.QUEUED):
            return None
        if awaiting_reconcile(round_):
            raise Refused(RECONCILE_FIRST)
        failed = abandoned_outcome(round_)
        if failed:
            _update_round(round_, **_abandoned_fields(round_, failed))
            state.refresh(locked)
            return None
        clear_stop(locked)
        Round.objects.filter(pk=round_.pk).update(state=Round.QUEUED, error='', failure_kind='', finished_at=None)
        job = enqueue(CODE, encounter=locked, revision=round_.revision,
                      key=f'{CODE}:{round_.pk}:resume:{uuid.uuid4()}', requested_by=user)
        audit.record(locked.workspace, 'pipeline.resumed', encounter=locked, actor=user, round=str(round_.pk))
        state.refresh(locked)
    return job


def retry(encounter, user):
    """A human retry of a failed round: a new round of the current revision (trigger retry), read afresh. Refused while
    a send of the failed round awaits an operator's reconcile (awaiting_reconcile)."""
    with transaction.atomic():
        locked = _locked(encounter)
        if busy(locked):
            raise Refused(BUSY_MESSAGE)
        round_ = latest_round(locked)
        if round_ is None or round_.state != Round.FAILED:
            raise Refused(RETRY_NOTHING)
        if awaiting_reconcile(round_):
            raise Refused(RECONCILE_FIRST)
        return start_round(locked, locked.current_revision or round_.revision, Round.RETRY, user)


def reconcile(encounter, run, user, note):
    """An operator's reconciliation of an UNKNOWN run: who looked, when and what they found. It queues nothing; once it
    is recorded, a Resume or a human retry of the run's round may send again. True when recorded, None when ``run`` is
    not an unreconciled unknown outcome."""
    note = (note or '').strip()
    if len(note) < RECONCILE_NOTE_CHARS:
        raise Refused(f'Write a note of at least {RECONCILE_NOTE_CHARS} characters saying what was found.')
    with transaction.atomic():
        run = Run.objects.select_for_update().get(pk=run.pk, encounter_id=encounter.pk)
        if run.state != Run.UNKNOWN or run.reconciled_at is not None:
            return None
        run.reconciled_by, run.reconciled_at, run.reconciliation_note = user, timezone.now(), note
        run.save(update_fields=['reconciled_by', 'reconciled_at', 'reconciliation_note'])
        audit.record(encounter.workspace, 'provider.reconciled', encounter=encounter, actor=user, run=str(run.pk))
    return True


# --- holds (BUILD-SPEC 3.3) ----------------------------------------------------------------------------------------------

def standing_holds():
    """Every InterpreterHold no release names, oldest first: while one stands, nothing is sent."""
    return models.InterpreterHold.objects.filter(release__isnull=True).order_by('created_at', 'pk')


def release_holds(*, user, note):
    """End every standing hold with an InterpreterHoldRelease naming ``user`` and ``note`` (the operator console gates
    who may). Returns the releases recorded; a hold released concurrently is skipped."""
    note = (note or '').strip()
    if not note:
        raise Refused('A release needs a note saying why the hold may end.')
    released = []
    for hold in list(standing_holds()):
        try:
            with transaction.atomic():
                released.append(models.InterpreterHoldRelease.objects.create(hold=hold, released_by=user, note=note))
        except IntegrityError:
            continue
    return released


def _record_hold(run, outcome):
    """The hold an account refusal sets (one per run), recorded with the run's outcome."""
    if not outcome.hold or not run.sent:
        return None
    existing = models.InterpreterHold.objects.filter(run=run).first()
    return existing or models.InterpreterHold.objects.create(
        reason=outcome.hold, http_status=outcome.http_status, vendor_status=outcome.error_type[:40], violations=[],
        run=run)


# --- spend (BUILD-SPEC 3.2) ----------------------------------------------------------------------------------------------

def ceiling_usd() -> Decimal:
    return Decimal(str(settings.DOCUMENT_CEILING_USD))


def run_cost(run):
    """The priced cost of a coding run from its stored usage, or None when it cannot be priced (the operator's)."""
    return pricing.cost_usd(run.usage) if run.usage else None


def _held_cost(run) -> Decimal:
    """What ``run`` counts against its revision's ceiling: nothing for a run that sent nothing, a replay, or one the API
    refused before answering (an error status, no usage); its priced usage when it answered; otherwise - unknown, still
    in flight, unpriceable - the worst case it was reserved at."""
    if run.state in (Run.NOT_SENT, Run.CANCELLED) or (run.state in (Run.SUCCEEDED, Run.FAILED) and not run.sent):
        return Decimal(0)
    if run.state in (Run.SUCCEEDED, Run.FAILED):
        priced = run_cost(run)
        if priced is not None:
            return priced
        if run.state == Run.FAILED and (run.http_status or 0) >= 400 and not run.usage:
            return Decimal(0)
    try:
        return Decimal(str((run.scope or {})['worst_usd']))
    except (KeyError, InvalidOperation):
        return ceiling_usd()  # nothing says what it could cost: it counts as the whole ceiling


def spent_usd(revision) -> Decimal:
    """Every coding run already on ``revision``, as it counts against the ceiling."""
    return sum((_held_cost(run) for run in Run.objects.filter(revision_id=revision.pk, purpose__in=PURPOSES)),
               Decimal(0))


# --- the coding stage (BUILD-SPEC 3) -------------------------------------------------------------------------------------

def _job_round(job):
    """The round a code job names ('code:<round>' and an optional ':resume:<uuid>')."""
    parts = job.idempotency_key.split(':')
    if len(parts) < 2 or parts[0] != CODE:
        return None
    try:
        return Round.objects.filter(pk=uuid.UUID(parts[1]), encounter_id=job.encounter_id).first()
    except ValueError:
        return None


def _update_round(round_, **fields):
    Round.objects.filter(pk=round_.pk).update(**fields)
    for name, value in fields.items():
        setattr(round_, name, value)


def _fail(round_, kind, *, text=None, document=None):
    """End ``round_`` failed with ``kind`` and the customer's sentence, and fail the stage."""
    text = text or failure_text(kind, document)
    _update_round(round_, state=Round.FAILED, failure_kind=kind, error=text, finished_at=timezone.now())
    audit.record(round_.encounter.workspace, 'coding.round_failed', encounter=round_.encounter,
                 round=str(round_.pk), failure_kind=kind)
    raise StageFailure(text)


def _stop_requested(job, encounter):
    """Whether a member's Stop was recorded for ``job`` or its encounter, read again from the database."""
    job.refresh_from_db(fields=['stop_requested_at'])
    return bool(job.stop_requested_at) or is_stopped(encounter.pk)


def _live_gate(job, coder, revision, round_):
    """A live send needs a synthetic-attested document, the recorded authority and an owner or reviewer's request
    (unchanged from the earlier pipeline)."""
    if coder.mode != fable_client.LIVE:
        return
    if not settings.SYNTHETIC_ONLY or revision.synthetic_attested_at is None:
        _fail(round_, UNAVAILABLE, text='Coding needs a document attested as synthetic.')
    if not settings.AUTHORIZATION_REF:
        _fail(round_, UNAVAILABLE, text='Coding is not authorized on this installation.')
    membership = models.Membership.objects.filter(user=job.requested_by, workspace_id=job.encounter.workspace_id,
                                                  active=True).first()
    if membership is None or not membership.can_review:
        _fail(round_, UNAVAILABLE, text='Only an owner or reviewer of this workspace can start coding.')


def stage_code(job):
    """Code one round (BUILD-SPEC 3): (1) refuse when stopped; the round runs. (2) Prepare the document. (3) Before each
    send, the spend check and a provider slot. (4) The READER, unless this round already has a succeeded reader run.
    (5) Parse; an unreadable answer fails the round. (6) The CHECKER, by the same rules. (7) Combine and write the
    round. (8) run_job refreshes the encounter state."""
    round_ = _job_round(job)
    if round_ is None:
        raise StageFailure('This job names no coding round.')
    if round_.state in (Round.DONE, Round.FAILED):
        return {'skipped': f'the round is already {round_.state}', 'round': str(round_.pk)}
    try:
        return _code(job, round_)
    except Requeue:
        _update_round(round_, state=Round.QUEUED)
        raise
    except StageCancelled:
        _update_round(round_, state=Round.CANCELLED, finished_at=timezone.now())
        raise
    except StageFailure:
        raise
    except Exception:
        log.exception('the coding stage failed unexpectedly for round %s', round_.pk)
        # a send of the round may have ended before the error: the round fails as that send would have failed it
        _fail(round_, abandoned_outcome(round_) or FAILED)


def _code(job, round_):
    encounter = job.encounter
    if _stop_requested(job, encounter):
        raise StageCancelled(STOPPED_MESSAGE)
    _update_round(round_, state=Round.RUNNING, started_at=round_.started_at or timezone.now(), error='',
                  failure_kind='', finished_at=None)
    if standing_holds().exists():
        _fail(round_, HOLD)
    coder = fable_client.coder()
    if coder is None:
        _fail(round_, UNAVAILABLE)
    _live_gate(job, coder, round_.revision, round_)
    try:
        document = fable_document.prepare(round_.revision, converter=_stored_conversion(round_))
    except fable_document.DocumentError as exc:
        log.info('round %s: the document was not sent (%s)', round_.pk, exc.detail or exc.failure_kind)
        _fail(round_, exc.failure_kind, text=exc.text)
    _keep_view(round_, document, encounter)
    context = round_.context or {}
    reader_request = fable_client.build_request(system=prompts.READER_SYSTEM, document=document,
                                                instruction=prompts.reader_instruction(context),
                                                effort=settings.CODING_EFFORT)
    reader_run = _reused(round_, READER) or _send(job, round_, READER, reader_request, coder)
    _update_round(round_, reader_run=reader_run)
    reader_message = _settled(round_, reader_run, document)
    try:
        reader = fable_result.read_reader(reader_message)
    except fable_result.Unreadable as exc:
        log.info('round %s: the reader answer was not readable (%s)', round_.pk, exc)
        _fail(round_, UNREADABLE)
    _update_round(round_, reader_result=reader)
    checker_request = fable_client.build_request(
        system=prompts.CHECKER_SYSTEM, document=document,
        instruction=prompts.checker_instruction(context, fable_result.listing(reader)), effort=settings.CODING_EFFORT)
    checker_run = _reused(round_, CHECKER) or _send(job, round_, CHECKER, checker_request, coder)
    _update_round(round_, checker_run=checker_run)
    checker_message = _settled(round_, checker_run, document)
    try:
        checker = fable_result.read_checker(checker_message)
    except fable_result.Unreadable as exc:
        log.info('round %s: the checker answer was not readable (%s)', round_.pk, exc)
        _fail(round_, UNREADABLE)
    combined = fable_result.combine(reader, checker)
    _update_round(round_, checker_result=checker, codes=combined['codes'], questions=combined['questions'],
                  problems=combined['problems'], citations=fable_result.citations(reader_message, checker_message),
                  state=Round.DONE, error='', failure_kind='', finished_at=timezone.now())
    audit.record(encounter.workspace, 'coding.round_done', encounter=encounter, round=str(round_.pk),
                 codes=len(combined['codes']), questions=len(combined['questions']))
    return {'round': str(round_.pk), 'reader_run': str(reader_run.pk), 'checker_run': str(checker_run.pk),
            'codes': len(combined['codes'])}


def _stored_conversion(round_):
    """For a Word document: a converter answering with the PDF a round of this revision already read and stored (the
    newest), so a resumed round, and every later round of the revision, reads - and the customer's viewer shows - the
    same pages; it converts afresh when that file can no longer be read back unchanged. None (convert) when no round
    of the revision stored one."""
    stored = (Round.objects.filter(revision_id=round_.revision_id, view_pdf_storage_name__isnull=False)
              .exclude(view_pdf_storage_name='').order_by('-number').first())
    if stored is None:
        return None

    def reuse(data):
        try:
            return read_original(SimpleNamespace(storage_name=stored.view_pdf_storage_name,
                                                 sha256=stored.view_pdf_sha256))
        except (OriginalCorrupted, OSError):
            log.warning('round %s: the stored conversion of round %s could not be read back; converting again',
                        round_.pk, stored.pk)
            return fable_document.convert_docx(data)
    return reuse


def _keep_view(round_, document, encounter):
    """Record on ``round_`` the PDF a Word document was converted to, as it is sent (CodingRound.view_pdf_*): the file
    an earlier round of the revision stored when the bytes are the same, else stored now (storage.store_original). A
    failure to store is logged and coding goes on: the viewer then shows no page of a Word document."""
    if document.kind != 'docx' or round_.view_pdf_sha256 == document.sha256:
        return
    same = (Round.objects.filter(revision_id=round_.revision_id, view_pdf_sha256=document.sha256,
                                 view_pdf_storage_name__isnull=False).exclude(view_pdf_storage_name='')
            .order_by('-number').first())
    if same is not None:
        name = same.view_pdf_storage_name
    else:
        try:
            name, _digest, _size = store_original(encounter.workspace_id, document.data, 'converted.pdf')
        except Exception:  # noqa: BLE001 - logged; the coding does not depend on the viewer's copy
            log.exception('round %s: the converted PDF could not be stored for the viewer', round_.pk)
            return
    _update_round(round_, view_pdf_storage_name=name, view_pdf_sha256=document.sha256)


def _reused(round_, purpose):
    """This round's succeeded run of ``purpose``, if it has one (a read already paid for is never sent again)."""
    return (Run.objects.filter(purpose=purpose, scope__round=str(round_.pk), state=Run.SUCCEEDED)
            .order_by('created_at').first())


def _settled(round_, run, document) -> dict:
    """The final message of a succeeded ``run``; any other outcome fails the round with its own kind."""
    if run.state != Run.SUCCEEDED:
        kind = (run.scope or {}).get('failure_kind') or {Run.UNKNOWN: UNKNOWN, Run.NOT_SENT: UNAVAILABLE}.get(
            run.state, FAILED)
        _fail(round_, kind, document=document)
    try:
        return stored_message(run)
    except ValueError:
        _fail(round_, UNREADABLE)


def stored_message(run) -> dict:
    """The final message a coding run stored (its response bytes are the message's JSON); ValueError otherwise."""
    message = json.loads(bytes(run.response_bytes or b''))
    if not isinstance(message, dict):
        raise ValueError('the stored answer is not a message')
    return message


def _service_date(round_):
    try:
        return date.fromisoformat((round_.context or {}).get('service_date') or '')
    except (TypeError, ValueError):
        return None


def _send(job, round_, purpose, request, coder):
    """One send under the discipline: the Stop, a standing hold and the spend ceiling checked - the send's worst case,
    every attempt it may make, from the API's count of the request (_worst_case) -, a provider slot taken without
    waiting, the run reserved before any network I/O, then sent once and its outcome recorded - an unknown one included
    - with any hold it sets, and the slot's lock if the send outlived the database session that held it."""
    encounter = job.encounter
    if _stop_requested(job, encounter):
        raise StageCancelled(STOPPED_MESSAGE)
    slot = _take_slot()
    held = False
    try:
        if standing_holds().exists():
            _fail(round_, HOLD)
        counted, worst = _worst_case(round_, purpose, request, coder)
        spent = spent_usd(round_.revision)
        if spent + worst > ceiling_usd():
            log.info('round %s: %s refused at the ceiling (spent %s, worst case %s)', round_.pk, purpose, spent, worst)
            _fail(round_, CEILING)
        run = Run.objects.create(
            encounter=encounter, revision=round_.revision, provider=PROVIDER, adapter_version=ADAPTER_VERSION,
            request_sha256=request.sha256, request_body=request.stored, contexts=[], state=Run.RESERVED,
            authorization_ref=settings.AUTHORIZATION_REF, requested_by=job.requested_by,
            service_date=_service_date(round_), purpose=purpose, endpoint=coder.endpoint,
            requested_model=fable_client.MODEL,
            scope={'round': str(round_.pk), 'mode': coder.mode, 'effort': request.params['output_config']['effort'],
                   'worst_usd': pricing.usd(worst), 'worst_basis': 'count' if counted else 'replay',
                   'input_tokens_counted': counted, 'attempts': request.attempts, 'slot': slot})
        try:
            if _stop_requested(job, encounter):
                run.state, run.error, run.finished_at = (Run.CANCELLED, 'Stopped before sending; nothing was sent.',
                                                         timezone.now())
                run.save(update_fields=['state', 'error', 'finished_at'])
                raise StageCancelled(STOPPED_MESSAGE)
            run.state, run.started_at = Run.SENDING, timezone.now()
            run.save(update_fields=['state', 'started_at'])
        except StageCancelled:
            raise
        except Exception:
            _settle_reservation(run)
            raise
        audit.record(encounter.workspace, 'provider.sending', encounter=encounter, run=str(run.pk), purpose=purpose,
                     mode=coder.mode, request_sha256=request.sha256, run_identity=str(run.run_identity))
        try:
            outcome = coder.send(request)
        except Exception as exc:  # noqa: BLE001 - a coder that raised may have sent: its outcome is unknown
            log.exception('the coder raised while sending coding run %s', run.pk)
            outcome = fable_client.unknown_outcome(exc, sent=bool(coder.endpoint))
    finally:
        held = _release_slot(slot)
    _fresh_connection()
    try:
        with transaction.atomic():
            _finish_run(run, outcome, slot_held=held)
            _record_hold(run, outcome)
    except Exception:
        log.exception('the outcome of coding run %s could not be recorded', run.pk)
        _settle_unrecorded(run, outcome)
        _fail(round_, UNKNOWN)
    audit.record(encounter.workspace, 'provider.finished', encounter=encounter, run=str(run.pk), state=run.state,
                 http_status=run.http_status, usage=run.usage, latency_ms=run.latency_ms, purpose=purpose,
                 fallback=outcome.fallback)
    return run


def _worst_case(round_, purpose, request, coder):
    """The spend check's figures for one send (BUILD-SPEC 3.2, FIX-SPEC 4): (the request's input tokens as the coder's
    free token count counted them, the send's worst case - every attempt the request may make, its server-side
    fallback's included). A coder that calls the API must count the request: when the count cannot be had, nothing is
    sent and the round fails busy, for a human retry; no estimate stands in (a PDF is billed by its pages, which its
    bytes do not bound). A coder that calls nothing (a replay, endpoint '') bills nothing: (None, 0)."""
    if not coder.endpoint:
        return None, Decimal(0)
    counted = _counted_input(coder, request)
    if counted is None:
        log.warning('round %s: the %s request could not be counted; nothing was sent', round_.pk, purpose)
        audit.record(round_.encounter.workspace, 'provider.count_failed', encounter=round_.encounter,
                     round=str(round_.pk), purpose=purpose)
        _fail(round_, BUSY)
    return counted, pricing.worst_case_usd(counted, request.params['max_tokens'], attempts=request.attempts)


def _counted_input(coder, request):
    """The request's input tokens by the coder's free token count (the live coder's, BUILD-SPEC 3.2), or None when it
    cannot be had: the coder has no count, the count raised, or it answered no whole positive number."""
    count = getattr(coder, 'count_input_tokens', None)
    if not callable(count):
        return None
    try:
        tokens = count(request)
    except Exception:  # noqa: BLE001 - logged; nothing is sent
        log.exception('the token count of a coding request raised; nothing is sent')
        return None
    return tokens if type(tokens) is int and tokens > 0 else None


def _finish_run(run, outcome, *, slot_held=True):
    run.state = {'succeeded': Run.SUCCEEDED, 'failed': Run.FAILED, 'unknown': Run.UNKNOWN,
                 'not_sent': Run.NOT_SENT}[outcome.state]
    run.sent = bool(outcome.sent)
    run.http_status = outcome.http_status
    run.response_bytes = outcome.response_bytes or b''
    run.response_sha256 = hashlib.sha256(outcome.response_bytes).hexdigest() if outcome.response_bytes else ''
    run.latency_ms = outcome.latency_ms
    run.usage = dict(outcome.usage or {})
    run.usage_basis = pricing.USAGE_BASIS if outcome.usage else ''
    run.provider_request_id = outcome.request_id[:120]
    run.returned_model = outcome.returned_model[:100]
    run.response_id = outcome.response_id[:140]
    run.error = outcome.error
    run.scope = {**(run.scope or {}), 'fallback': outcome.fallback, 'stop_reason': outcome.stop_reason,
                 **({'failure_kind': outcome.failure_kind} if outcome.failure_kind else {}),
                 **({'error_type': outcome.error_type} if outcome.error_type else {}),
                 **({} if slot_held else {'slot_lost': True})}
    run.finished_at = timezone.now()
    run.save()


UNRECORDED_MESSAGE = ('The answer arrived but its outcome could not be recorded (logged). The request may have reached '
                      'the vendor and been billed: it is recorded with an unknown outcome.')
ORPHANED_SENDING_MESSAGE = ('The stage that sent this request ended without recording its outcome. The request may have '
                            'reached the vendor and been billed: it is recorded with an unknown outcome.')
UNSENT_RESERVATION_MESSAGE = ('Nothing was sent: the stage stopped with an unexpected error (logged) after reserving this '
                              'request and before sending it.')
ORPHANED_RESERVATION_MESSAGE = 'Nothing was sent: the stage that reserved this request ended before sending it.'


def _settle_reservation(run):
    """A reservation never marked sending, once its stage failed: recorded not sent. The stale sweep settles it if
    this write fails too."""
    try:
        Run.objects.filter(pk=run.pk, state=Run.RESERVED).update(
            state=Run.NOT_SENT, sent=False, error=UNSENT_RESERVATION_MESSAGE, finished_at=timezone.now())
    except Exception:  # noqa: BLE001 - logged; the sweep settles a reservation whose stage no longer runs
        log.exception('coding run %s could not be settled as not sent after its stage failed', run.pk)


def _settle_unrecorded(run, outcome):
    """A run still 'sending' whose outcome could not be written: unknown (or not sent, when nothing was sent), with
    only small fields; left 'sending' for the stale sweep when even that fails."""
    unsent = outcome.state == 'not_sent' and not outcome.sent
    try:
        Run.objects.filter(pk=run.pk, state=Run.SENDING).update(
            state=Run.NOT_SENT if unsent else Run.UNKNOWN, sent=bool(outcome.sent),
            http_status=outcome.http_status, finished_at=timezone.now(),
            error='Nothing was sent; its record could not be written (logged).' if unsent else UNRECORDED_MESSAGE)
    except Exception:  # noqa: BLE001 - logged
        log.exception('coding run %s could not be settled after its outcome failed to record', run.pk)


# This process's sends holding a provider slot (MONEY-4): never more than CONCURRENT_DOCUMENTS, whatever happens to the
# database sessions that hold the slots' locks.
_SENDS_LOCK = threading.Lock()
_sends_in_flight = 0


def _take_slot() -> int:
    """One of the N provider slots, taken without waiting; Requeue when none is free. A slot is held twice: in this
    process's count of its sends in flight, and as a session lock of this thread's database connection
    (PROVIDER_LOCK_KEY + 0 .. N-1), which keeps another worker process out while the session lives.

    MONEY-4 (fixed within the process, bounded across processes): when a session ends mid-send - a database restart, a
    terminated backend - its lock goes with it while the send goes on. The count still holds the slot, so no other send
    of this process takes it until the send ends, and the run records the lost lock (scope.slot_lost). Another process
    could take the lock meanwhile; one worker process runs (the installer's invariant), and every process's own count
    keeps its sends at N whatever the locks do."""
    global _sends_in_flight
    limit = int(settings.CONCURRENT_DOCUMENTS)
    with _SENDS_LOCK:
        if _sends_in_flight >= limit:
            raise Requeue('every provider slot is in use')
        _sends_in_flight += 1
    try:
        with connection.cursor() as cursor:
            for index in range(limit):
                cursor.execute('SELECT pg_try_advisory_lock(%s)', [PROVIDER_LOCK_KEY + index])
                if cursor.fetchone()[0]:
                    return index
    except BaseException:
        _uncount_send()
        raise
    _uncount_send()
    raise Requeue('every provider slot is in use')


def _uncount_send():
    global _sends_in_flight
    with _SENDS_LOCK:
        _sends_in_flight = max(_sends_in_flight - 1, 0)


def _release_slot(index: int) -> bool:
    """Give slot ``index`` back - its session lock, then this process's count - and say whether the lock was still
    held: False when the database session that held it ended during the send (logged; the run records it)."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK_KEY + index])
            held = bool(cursor.fetchone()[0])
    except Exception:  # noqa: BLE001 - the session that held the lock ended, and the lock with it
        log.exception('provider slot %s could not be released: the database session that held it ended during the '
                      'send', index)
        held = False
    else:
        if not held:
            log.error('provider slot %s was no longer held when its send ended: the database session that held it '
                      'ended during the send', index)
    finally:
        _uncount_send()
    return held


def _fresh_connection():
    """After a send of up to many minutes, a connection that broke or outlived its age is replaced before the outcome
    is written (never inside a transaction, where Django keeps the connection)."""
    if not connection.in_atomic_block:
        connection.close_if_unusable_or_obsolete()


STAGES = {CODE: stage_code}


# --- the worker --------------------------------------------------------------------------------------------------------

_LIVE: set = set()  # the jobs this process's threads are running now: never swept
_LIVE_LOCK = threading.Lock()


@contextlib.contextmanager
def _live(job_id):
    with _LIVE_LOCK:
        _LIVE.add(job_id)
    try:
        yield
    finally:
        with _LIVE_LOCK:
            _LIVE.discard(job_id)


def _live_ids() -> set:
    with _LIVE_LOCK:
        return set(_LIVE)


def _cancel_queued_round(job):
    """A code job cancelled before it ran leaves its round cancelled (resumable), never queued with nothing to run."""
    if job.kind != CODE:
        return
    round_ = _job_round(job)
    if round_ is not None and round_.state in (Round.QUEUED, Round.RUNNING):
        _update_round(round_, state=Round.CANCELLED, finished_at=timezone.now())


def claim_next():
    """Claim the oldest runnable job of a kind this worker runs, expiring or cancelling as needed."""
    with transaction.atomic():
        job = (Job.objects.select_for_update(skip_locked=True).filter(state=Job.QUEUED, kind__in=list(STAGES))
               .order_by('created_at').first())
        if job is None:
            return None
        now = timezone.now()
        if job.stop_requested_at or is_stopped(job.encounter_id):
            job.state, job.error, job.finished_at = Job.CANCELLED, 'Stopped before it started.', now
            _cancel_queued_round(job)
        elif job.deadline_at < now:
            job.state, job.error, job.finished_at = (Job.CANCELLED, 'The stage expired before it could start; resume '
                                                     'to run it.', now)
            _cancel_queued_round(job)
        else:
            job.state, job.started_at = Job.RUNNING, now
            job.attempts += 1
        job.save(update_fields=['state', 'error', 'started_at', 'finished_at', 'attempts'])
        return job


def run_job(job):
    if job.state != Job.RUNNING:
        state.refresh(job.encounter)
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
    except Exception:  # noqa: BLE001 - recorded, never shown with internals
        log.exception('stage %s failed for job %s', job.kind, job.pk)
        job.state, job.error = Job.FAILED, f'The {job.kind} stage failed unexpectedly; the error was logged.'
    if job.state != Job.QUEUED:
        job.finished_at = timezone.now()
    # Only the columns the worker owns: a Stop recorded on this row meanwhile must survive.
    job.save(update_fields=['state', 'started_at', 'attempts', 'result', 'error', 'finished_at'])
    if job.state == Job.QUEUED:
        time.sleep(REQUEUE_SECONDS)
    state.refresh(job.encounter)
    return job


def may_have_reached_vendor(runs):
    """The runs of ``runs`` (a ProviderRun queryset) that may have reached the vendor if left sending: those that call
    one (a replay's endpoint is '')."""
    return runs.exclude(endpoint='')


def stale_threshold(kind) -> int:
    if kind == CODE:
        return CODE_STALE_SECONDS
    return int(getattr(settings, 'STALE_RUNNING_SECONDS_BY_KIND', {}).get(kind, settings.STALE_RUNNING_SECONDS))


def _settle_in_flight(runs) -> int:
    """Settle the sends of ``runs`` whose stage no longer runs: one still sending becomes UNKNOWN (it may have reached
    the vendor: sent when it called one); a reservation never marked sending - nothing of it was sent, the mark is
    written before any network I/O - becomes NOT_SENT. Returns how many were sending."""
    sending = list(runs.filter(state=Run.SENDING))
    for run in sending:
        run.state, run.error, run.finished_at = (Run.UNKNOWN, 'The worker stopped while the request was in flight.',
                                                 timezone.now())
        run.sent = run.sent or bool(run.endpoint)
        run.save(update_fields=['state', 'error', 'finished_at', 'sent'])
    runs.filter(state=Run.RESERVED).update(state=Run.NOT_SENT, error='The worker stopped before sending.',
                                           finished_at=timezone.now())
    return len(sending)


def abandoned_outcome(round_) -> str:
    """How ``round_`` ends when its stage ended without settling it (a dead worker, a lost database session, a close):
    the failure kind the stage itself would have ended it with, or '' when nothing it sent is unsettled (MONEY-2). For
    each send in turn - the reader, then the checker - one that succeeded is reused by a Resume; otherwise the send's
    newest run decides: still sending, or unknown with no operator's reconcile, is UNKNOWN (it may have reached the
    vendor and is never sent again by itself); failed - answered and billed, or refused - is that run's own kind;
    not sent, cancelled, or an unknown an operator reconciled leaves nothing unsettled. Settle the sends in flight first
    (_settle_in_flight)."""
    runs = list(Run.objects.filter(purpose__in=PURPOSES, scope__round=str(round_.pk)).order_by('created_at', 'pk'))
    for purpose in PURPOSES:
        sent = [run for run in runs if run.purpose == purpose]
        if any(run.state == Run.SUCCEEDED for run in sent):
            continue
        if not sent:
            return ''
        newest = sent[-1]
        if newest.state == Run.SENDING or (newest.state == Run.UNKNOWN and newest.reconciled_at is None):
            return UNKNOWN
        if newest.state == Run.FAILED:
            return (newest.scope or {}).get('failure_kind') or FAILED
        return ''
    return ''


def _document_of(revision):
    """What the API refusal's sentence needs of ``revision``'s document (failure_text): its kind."""
    if revision.kind == models.SourceRevision.PASTE:
        return SimpleNamespace(kind='paste')
    media_type = getattr(revision.source_file, 'media_type', None)
    return SimpleNamespace(kind={fable_document.PDF: 'pdf', fable_document.DOCX: 'docx',
                                 fable_document.TEXT: 'txt'}.get(media_type, ''))


def _abandoned_fields(round_, kind) -> dict:
    """``round_``'s columns once its stage ended without settling it: failed with ``kind`` and the sentence the stage
    would have written, or - no kind - cancelled, for a Resume that reuses its paid reads."""
    if kind:
        return {'state': Round.FAILED, 'failure_kind': kind, 'error': failure_text(kind, _document_of(round_.revision)),
                'finished_at': timezone.now()}
    return {'state': Round.CANCELLED, 'finished_at': timezone.now()}


def mark_stale(*, startup=False):
    """Settle jobs a dead thread or process left 'running'; a send in flight becomes UNKNOWN, never resent.

    A job one of this process's threads runs is never swept. ``startup``: the worker's own first sweep, which settles
    every other RUNNING job whatever its age (one worker process runs: the installer stops the old one first);
    otherwise a job is swept once older than its kind's threshold. A code job's round is settled as its stage would
    have settled it (abandoned_outcome): failed as unknown while a send of it may have reached the vendor with no
    outcome known, failed with a send's own kind when a send of it failed, and only when nothing it sent is unsettled
    cancelled, for a Resume, which reuses the round's paid reads."""
    now = timezone.now()
    live = _live_ids()
    for job in Job.objects.filter(state=Job.RUNNING).order_by('started_at', 'pk'):
        if job.pk in live:
            continue
        if not startup and (job.started_at is None
                            or job.started_at >= now - timedelta(seconds=stale_threshold(job.kind))):
            continue
        with transaction.atomic():
            round_ = _job_round(job) if job.kind == CODE else None
            if round_ is not None:
                runs = Run.objects.filter(purpose__in=PURPOSES, scope__round=str(round_.pk))
            else:
                runs = Run.objects.filter(revision_id=job.revision_id, created_at__gte=job.started_at or now)
            sending = _settle_in_flight(runs)
            kind = abandoned_outcome(round_) if round_ is not None else (UNKNOWN if sending else '')
            if kind == UNKNOWN:
                job.state, job.error = Job.UNKNOWN, (
                    'The worker stopped while this stage was sending.' if sending else
                    'The worker stopped after a send of this stage ended with an unknown outcome, before its round was '
                    'written.')
            elif kind:
                job.state, job.error = Job.FAILED, (f'The worker stopped after a send of this stage failed ({kind}), '
                                                    'before its round was written.')
            else:
                job.state, job.error = (Job.CANCELLED, 'The worker stopped while this stage was running; resume to run '
                                        'it again.')
            if round_ is not None and round_.state in (Round.QUEUED, Round.RUNNING):
                _update_round(round_, **_abandoned_fields(round_, kind))
            job.finished_at = timezone.now()
            job.save(update_fields=['state', 'error', 'finished_at'])
        state.refresh(job.encounter)
    # A run left 'sending' or 'reserved' by a stage that no longer runs - its outcome never recorded - is settled like a
    # dead worker's. Its own stage, were it running, started before it.
    cutoff = now - timedelta(seconds=settings.STALE_RUNNING_SECONDS)
    for found, settled_state, message in ((Run.SENDING, Run.UNKNOWN, ORPHANED_SENDING_MESSAGE),
                                          (Run.RESERVED, Run.NOT_SENT, ORPHANED_RESERVATION_MESSAGE)):
        for run in Run.objects.filter(state=found, created_at__lt=cutoff):
            if Job.objects.filter(encounter_id=run.encounter_id, state=Job.RUNNING,
                                  started_at__lte=run.created_at).exists():
                continue
            changed = Run.objects.filter(pk=run.pk, state=found).update(
                state=settled_state, error=message, finished_at=timezone.now(),
                sent=run.sent or (found == Run.SENDING and bool(run.endpoint)))
            if changed:
                state.refresh(run.encounter)
    # A round left queued or running with no job of its encounter queued or running - its stage ended without settling
    # it, on a database error say - is settled as that stage would have settled it (abandoned_outcome), under the
    # encounter's lock: failed when a send of it is unsettled, else cancelled so a Resume can continue it (never left
    # processing for good).
    for round_ in Round.objects.filter(state__in=(Round.QUEUED, Round.RUNNING), created_at__lt=cutoff):
        with transaction.atomic():
            if busy(_locked(round_.encounter)):
                continue
            _settle_in_flight(Run.objects.filter(purpose__in=PURPOSES, scope__round=str(round_.pk)))
            changed = Round.objects.filter(pk=round_.pk, state__in=(Round.QUEUED, Round.RUNNING)).update(
                **_abandoned_fields(round_, abandoned_outcome(round_)))
        if changed:
            state.refresh(round_.encounter)


def remove_stale_work_dirs():
    """A worker killed mid-conversion (or mid-extraction, before this pipeline) can leave its child's work directory."""
    import shutil
    import tempfile
    from pathlib import Path

    for prefix in (fable_document.WORK_PREFIX, 'cpt-ingest-'):
        for path in Path(tempfile.gettempdir()).glob(f'{prefix}*'):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, ignore_errors=True)


# The worker process beats every HEARTBEAT_SECONDS from a thread of its own; a beat older than WORKER_SILENT_SECONDS,
# while a document waits on processing, reads as processing paused.
HEARTBEAT_SECONDS = 30
WORKER_SILENT_SECONDS = 120
WORKER_NAME = 'worker'


def beat(*, name=WORKER_NAME, now=None):
    """Record one heartbeat of this worker process (models.WorkerBeat). Never raises."""
    import os

    try:
        models.WorkerBeat.objects.update_or_create(name=name, defaults={
            'beat_at': now or timezone.now(), 'revision': str(settings.RELEASE_SHA)[:64], 'pid': os.getpid()})
    except Exception:  # noqa: BLE001 - logged; the next beat tries again
        log.exception('the worker heartbeat could not be recorded')


def start_heartbeat(should_stop, *, interval=HEARTBEAT_SECONDS):
    """A daemon thread that beats every ``interval`` seconds until ``should_stop()``; its database connection is
    closed when it ends. Returns the thread."""
    def loop():
        try:
            while not should_stop():
                beat()
                for _ in range(int(interval * 10)):
                    if should_stop():
                        break
                    time.sleep(0.1)
        finally:
            connection.close()
    thread = threading.Thread(target=loop, name='cpt-studio-heartbeat', daemon=True)
    thread.start()
    return thread


def worker_responding(*, now=None, name=WORKER_NAME):
    """True when the worker beat within WORKER_SILENT_SECONDS, False when its newest beat is older, None when no beat
    was ever recorded."""
    row = models.WorkerBeat.objects.filter(name=name).first()
    if row is None:
        return None
    return (now or timezone.now()) - row.beat_at <= timedelta(seconds=WORKER_SILENT_SECONDS)


def _thread_count(threads=None) -> int:
    return max(1, int(threads or settings.CONCURRENT_DOCUMENTS))


def _worker_thread(should_stop, poll_seconds, *, drain=False):
    """One worker thread: claim and run jobs on its own database connection until ``should_stop()`` (or, draining,
    until nothing is queued)."""
    try:
        while not should_stop():
            try:
                close_old_connections()
                job = claim_next()
                if job is None:
                    if drain:
                        return
                    time.sleep(poll_seconds)
                    continue
                with _live(job.pk):
                    run_job(job)
            except Exception:  # noqa: BLE001 - logged; the thread goes on with a new connection
                log.exception('a worker thread met an unexpected error')
                connection.close()
                time.sleep(poll_seconds)
    finally:
        connection.close()


def _run_threads(target, count, *, while_waiting=None, should_stop=None):
    pool = [threading.Thread(target=target, name=f'cpt-studio-coder-{index}') for index in range(count)]
    for thread in pool:
        thread.start()
    try:
        for thread in pool:
            while thread.is_alive():
                thread.join(timeout=1.0)
                if while_waiting is not None and not should_stop():
                    while_waiting()
    finally:
        for thread in pool:
            thread.join()


def work(should_stop, *, poll_seconds=1.0, threads=None, clock=time.monotonic):
    """The worker: the startup sweep, then CPT_STUDIO_CONCURRENT_DOCUMENTS threads claiming and running jobs until
    ``should_stop()`` (each finishes its current job first); the main thread sweeps every STALE_SWEEP_SECONDS."""
    remove_stale_work_dirs()
    mark_stale(startup=True)
    swept = {'at': clock()}

    def sweep():
        if clock() - swept['at'] >= STALE_SWEEP_SECONDS:
            try:
                mark_stale()
            except Exception:  # noqa: BLE001 - logged; the next sweep tries again
                log.exception('the stale sweep failed')
                connection.close()
            swept['at'] = clock()
    try:
        _run_threads(lambda: _worker_thread(should_stop, poll_seconds), _thread_count(threads), while_waiting=sweep,
                     should_stop=should_stop)
    finally:
        connection.close()


def drain(should_stop, *, threads=None, poll_seconds=1.0):
    """Process queued jobs with the worker's threads until none is left (``run_worker --once``)."""
    _run_threads(lambda: _worker_thread(should_stop, poll_seconds, drain=True), _thread_count(threads))
