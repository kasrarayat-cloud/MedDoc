"""Pipeline jobs: extract -> interpret -> analyze -> predict [-> astra -> fable -> assess #1 -> astra_peer -> fable_peer]
-> assess [-> review2 -> assess] (ARCHITECTURE section 5; the harness participants' stages, HARNESS.md 2, 11 and 12, run
only when configured; the Gemini migration's interpret stage and derive-only analyze, design/FINAL.md 6.1-6.5, 6.9, and
its events assess, peers, second review, context save and recompute, 6.6-6.10).

One worker claims queued jobs with SELECT ... FOR UPDATE SKIP LOCKED. Every
stage is idempotent (unique idempotency key), must start before its deadline,
and records failure explicitly. Provider sends are single-flight under a
PostgreSQL advisory lock, reserved in the database before any network I/O,
never retried automatically, and an unknown outcome blocks every further send
for the encounter until a member reconciles it.
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import logging
import sys
import time
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import JSONField, Q, Value
from django.utils import timezone

from . import audit, bounded, interpretation, models, participants, review
from .interpretation import adapter as interpretation_adapter
from .interpretation import assess as events_engine
from .interpretation import facts as interpretation_facts
from .interpretation import holds as interpretation_holds
from .interpretation import report as interpretation_report
from .interpretation import sentinel
from .interpretation import store as inventory_store
from .gi import context as gi_context
from .gi import detect as gi_detect
from .ingest import Limits, extract_document, extract_paste
from .providers import get_provider, normalizer_for
from .providers.corti import CortiProvider, build_coding_request
from .providers.replay import ReplayProvider
from .providers.base import ProviderUnavailable
from .participants import http as participant_http
from .participants import loop as participant_loop
from .participants import peer as participant_peer
from .participants import prompt as participant_prompt
from .reference import passages as reference_passages
from .reference import tools as reference_tools
from .reference.store import prefetched_lookup, selected_codes
from .storage import ALLOWED_SUFFIXES, OriginalCorrupted, read_original
from .types import (ConfirmedFinding, EvidenceSpan, Fact, NormalizedResponse, PageSpan, ParticipantInput, ProviderCode,
                    ProviderRequest, RawExchange, RoutingResult, from_jsonable, sha256_json, to_jsonable)
from .validation import checks as validation_checks
from .validation.engine import assess as run_assessment
from .validation.questions import MemberAnswerInput

log = logging.getLogger(__name__)

CONTEXT_VERSION = 'gi-context@5'  # @5: the recall round (2026-11-08): the owner's date forms of 2026-11-07 (a day-first date
# with a month name, a weekday before the date, a head 'Exam date' / 'Date of Operation').
# A context gi-context@4 recorded (installed 41e03656df61 to 73dcf8b4b40a) stays CURRENT, unlike @1-@3 below. Not because
# @4 never says what @5 would not: a @4 context that asked, then took a member's date answer, sends that answer where @5
# HOLDS it as contradicting a newly read head date (the recall round's final refutation; through the findings-stated
# reach 45385 read READY on it). It stays current because retiring it was refuted in its turn (2026-11-08): the
# participant and peer stages send on an earlier context queued, resumed or swept across an install without remaking
# it (a gap @1-@3 share), and on the encounters @4 read the retirement itself regressed - a member's answer applied to
# the stored assessment with no recompute (a false 'reviewed' with an approved export), a withdrawal never applied, a
# reconciliation's attempt lost, second reviews withdrawn - while no live context @4 recorded reads differently under
# @5 (facts and document date, measured on the live copy before the install, a stop condition of its declaration),
# and no context can be recorded under @4 once this revision is installed.
# Context versions recorded under other rules: a stage remakes such a context before it sends or assesses anything
# (_remade_context), and no second review is offered or sent on one (_second_review_bounds, stage_review2).
# - gi-context@1 (the installed revision 057a7d39) kept a member's value as plain metadata;
# - gi-context@2 (2b82889f and 90377ec6f413) read a date label a plan or history section held as dropped, so h2-08's
#   recorded context says 2026-10-05 where the third round's binding reads a conflict with its charge block's
#   2026-10-06. Kept current, it was re-sent by a predict queued or stopped at the install, a reconciliation or a second
#   review, and assessed as documented (refutation of the integrated third round, STATE-1 and STATE-2).
# - gi-context@3 (80df1831d168, the third round's narrow release) read the dates as GI round 4 no longer does: round 4
#   asks a date @3 sent where the note's own head states another day (PD's rule (a)), takes only the day a procedure
#   note's own sign-off states (rule (c)) and places headings by PS's section reach, so a context @3 recorded can say a
#   date the current rules ask or hold, and a stage would send and assess it as documented (interpretation 49;
#   pd.json integration_20261101_cycle2).
EARLIER_CONTEXT_VERSIONS = ('gi-context@1', 'gi-context@2', 'gi-context@3')
MEMBER_DATE_CONFLICT_MESSAGE = ('Nothing was sent: the service date entered as encounter metadata differs from the '
                                'documented one. Correct or clear the metadata (or add an addendum), and the request is '
                                'made for the agreed date.')
PROVIDER_LOCK_KEY = 0x435054535455  # 'CPTSTU': CPT Studio's own single-flight key
QUEUE_DEADLINE = timedelta(minutes=30)  # a job that cannot start within this window expires
Job = models.Job
# The Gemini migration's stage and its runs (design/FINAL.md 6.1): Job.kind 'interpret', ProviderRun.purpose
# 'interpretation' and provider 'gemini', the labels studio.interpretation owns.
INTERPRET = interpretation.JOB_KIND
INTERPRETATION = interpretation.PURPOSE
READABLE = (models.SourceRevision.OK, models.SourceRevision.PARTIAL)
_CURRENT_VERSIONS = (interpretation.INTERPRETATION_VERSION, interpretation.INVENTORY_VERSION)


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
    # Nothing is built, reused or sent while the hold stands - a harness participant's request included: the assess
    # reads the participants' answers as they are, and settling the date makes the request, and the participants' turn.
    return enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=run,
                   key=_assess_key(f'assess:{context.pk}:{run.pk}' if run else f'{key}:no-provider', revision),
                   requested_by=requested_by)


# --- the harness participants' chain (HARNESS.md 2) ------------------------------------------------------------------
#
# predict -> astra -> fable -> assess, each participant's stage only when it is configured. Every stage of a chain
# carries the Corti run as Job.provider_run. A participant stage's key is '<name>:<chain>', where <chain> is a digest of
# what started the chain (the assess key that predict would have queued, and the predict job - or the member's context
# save, change_context), so two chains for one context never share a stage's key, and the stale sweep, settling a stage
# whose worker died, queues the next stage under the key the stage itself would have used. The assess the chain ends
# with is keyed by _assess_key.

UPGRADE_MARK = ':after-upgrade'  # a chain the upgrade's predict started: its stages stop where they would send


def _participant_key(name, chain, upgrade=False):
    return f'{name}:{chain}' + (UPGRADE_MARK if upgrade else '')


def _chain_of(job):
    """The chain digest a participant stage's key carries ('<name>:<chain>', then a Resume's suffix or the mark)."""
    return job.idempotency_key.split(':')[1]


def _assess_key(base, revision):
    """The key of an assess: ``base`` - exactly today's key - when no participant is configured (I1); otherwise ``base``
    plus ':p:' and 12 hex of the sha256 of the participant runs it reads (_participant_run, '-' for none), so an assess
    reading other participant runs is never taken for one already queued. 200 characters hold the longest base (a second
    review's, 125) with this suffix and a Resume's."""
    names = participants.configured()
    if not names:
        return base
    runs = [_participant_run(revision, name) for name in names]
    ids = ','.join(str(run.pk) if run is not None else '-' for run in runs)
    return f'{base}:p:{hashlib.sha256(ids.encode()).hexdigest()[:12]}'


def _after_predict(encounter, revision, context, run, *, key, origin, requested_by, upgrade=False):
    """What follows the predict outcome ``run`` (None: the provider is disabled): the assess under ``key``, exactly as
    before, when no harness participant is configured (I1); otherwise the first configured participant's stage, carrying
    ``run`` (HARNESS.md 2). ``origin`` names what started the chain - the predict job that recorded ``run``, or a
    member's context save that re-checks with it (change_context) - so no two chains share a stage's key, and
    ``upgrade`` marks a chain the upgrade's predict started (_upgrade_predict_key). A member date conflict's hold never
    starts a chain: nothing is sent while it stands (_queue_predict, stage_predict)."""
    names = participants.configured()
    if not names:
        return enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=run, key=key,
                       requested_by=requested_by)
    chain = hashlib.sha256(f'{key}|{origin}'.encode()).hexdigest()[:32]
    return enqueue(names[0], encounter=encounter, revision=revision, context=context, provider_run=run,
                   key=_participant_key(names[0], chain, upgrade), requested_by=requested_by)


def _queue_after_participant(job):
    """The stage after participant ``job.kind``'s: the next configured participant's, in HARNESS.md 2's order, or the
    assess, keyed by the predict's assess key and the participant runs it reads. A chain the upgrade's predict started
    keeps its mark, so each of its participants stops where it would send until a member's Resume
    (stage_participant)."""
    names = participants.configured()
    order = participants.PARTICIPANTS
    later = [name for name in order[order.index(job.kind) + 1:] if name in names]
    if later:
        return enqueue(later[0], encounter=job.encounter, revision=job.revision, context=job.context,
                       provider_run=job.provider_run, requested_by=job.requested_by,
                       key=_participant_key(later[0], _chain_of(job), job.idempotency_key.endswith(UPGRADE_MARK)))
    base = f'assess:{job.context_id}:{job.provider_run_id or "no-provider"}'
    return enqueue(Job.ASSESS, encounter=job.encounter, revision=job.revision, context=job.context,
                   provider_run=job.provider_run, key=_assess_key(base, job.revision), requested_by=job.requested_by)


def _participant_run(revision, name):
    """The run of participant ``name`` the assess reads for ``revision`` (HARNESS.md 2): its newest finished
    'independent' run - succeeded, failed, unknown or not sent - leaving out, as _run_in_use does, an unknown outcome a
    member reconciled (released for one new attempt) and a reservation the stale sweep settled unsent (it never reached
    the send). None when there is none."""
    return _newest_finished(revision.provider_runs.filter(provider=name, purpose=models.ProviderRun.INDEPENDENT))


def _newest_finished(runs):
    """The newest finished run of ``runs`` (succeeded, failed, unknown or not sent), leaving out an unknown outcome a
    member reconciled and a reservation the stale sweep settled unsent: the one rule _participant_run and _peer_run
    read a participant's runs by."""
    from django.db.models import Q

    finished = (models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED, models.ProviderRun.NOT_SENT,
                models.ProviderRun.UNKNOWN)
    reserved_then_swept = (Q(state=models.ProviderRun.NOT_SENT) & Q(started_at__isnull=True)
                           & ~Q(request_sha256=''))
    reconciled = Q(state=models.ProviderRun.UNKNOWN) & Q(reconciled_at__isnull=False)
    return (runs.filter(state__in=finished).exclude(reserved_then_swept).exclude(reconciled)
            .order_by('-created_at', '-pk').first())


def _participants_owed(revision, context):
    """The configured participants with no recorded outcome for ``revision`` (_participant_run finds none): their stage
    was stopped, expired or swept before it recorded one, or the participant was configured since. () while ``context``
    holds a member date conflict, while which nothing is sent - and so () when none is configured (I1)."""
    if gi_context.is_member_conflict((context.facts or {}).get('service_date')):
        return ()
    return tuple(name for name in participants.configured()
                 if _participant_run(revision, name) is None or _stopped_and_resumable(revision, name))


def _stopped_and_resumable(revision, name) -> bool:
    """Whether participant ``name``'s newest finished, sent first reading for ``revision`` is a loop a member's Stop
    ended between exchanges (refutation round 1 of harness repair 3, L6-2): it is owed its turn, which continues it."""
    return _resumable_stop(_newest_finished(revision.provider_runs.filter(
        provider=name, purpose=models.ProviderRun.INDEPENDENT, sent=True)))


# --- harness@2's peer review (HARNESS.md 11.1, 12.1) ------------------------------------------------------------------
#
# assess #1 -> astra_peer -> fable_peer -> assess #2. assess #1 is the assess the last phase-1 stage queues, exactly as
# before (_queue_after_participant). When a configured participant's first reading was read, it queues the first owed
# peer stage, keyed '<kind>:<12 hex of sha256(assess #1 id)>' (_peer_key), so one assess #1 makes one peer chain and a
# peer stage finds the assessment it reads from its own key. Each peer stage queues the next owed one; the last queues
# assess #2, keyed '<assess #1 base>:q:<12 hex of the phase-1 and peer run ids>' (_final_key). A reviewer's confirmation
# queues one re-assessment, keyed '<the final assessment's key>:c:<12 hex of the confirmation ids>'
# (reassess_after_confirmation). With no model participant configured none of this runs (I1).

PEER_OF = {Job.ASTRA_PEER: 'astra', Job.FABLE_PEER: 'fable'}
PEER_KIND = {name: kind for kind, name in PEER_OF.items()}
FINAL_MARK, AGAIN_MARK = ':q:', ':c:'  # the key parts of assess #2 and of a re-assessment after a confirmation
FIRST, FINAL, AGAIN = 'first', 'final', 'again'  # what an assess reads: _assess_mode


def _digest(value) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


def _peer_key(kind, first, upgrade=False):
    """A peer stage's key (HARNESS.md 12.1): its kind and 12 hex of sha256(assess #1's id), plus the mark of a chain the
    upgrade's predict started, whose stages stop where they would send until a member's Resume (stage_peer)."""
    return f'{kind}:{_digest(first.pk)}' + (UPGRADE_MARK if upgrade else '')


def _assess_mode(job):
    """What an assess reads, from the key it was queued under (a Resume keeps the stage's own key as its prefix):
    FIRST - assess #1, every assess before harness@2 among them -, FINAL - assess #2 - or AGAIN - a re-assessment after
    a confirmation."""
    key = job.idempotency_key
    if AGAIN_MARK in key:
        return AGAIN
    return FINAL if FINAL_MARK in key else FIRST


def _records(assessment):
    """An assessment's Assessment.participants entries, by participant name."""
    return {record['name']: record for record in assessment.participants or []
            if isinstance(record, dict) and isinstance(record.get('name'), str)}


def _newest_assessment(revision):
    return models.Assessment.objects.filter(revision=revision).order_by('-created_at', '-pk').first()


def _first_assessment(job):
    """The assess #1 a peer stage reads: the revision's newest assessment, when its id is the one the stage's key names;
    None when a newer assessment exists, whose own chain owns the revision."""
    newest = _newest_assessment(job.revision)
    return newest if newest is not None and _digest(newest.pk) == job.idempotency_key.split(':')[1] else None


def _peer_run(revision, name, first):
    """The peer-review run of participant ``name`` made for assess #1 ``first`` (its scope names that assessment), read
    as _participant_run reads a phase-1 run. None when there is none."""
    return _newest_finished(revision.provider_runs.filter(provider=name, purpose=models.ProviderRun.PEER_REVIEW,
                                                           scope__assessment=str(first.pk)))


def _owed_peers(first, after=None):
    """The peer stages owed for assess #1 ``first``, in HARNESS.md 12.1's order (only those after the peer stage of
    participant ``after`` when given): one for each configured participant whose first reading ``first`` read ('read').
    A participant whose first assessment failed never gets a first look that has already seen its peers."""
    records, names, order = _records(first), participants.configured(), participants.PARTICIPANTS
    later = order[order.index(after) + 1:] if after else order
    return [PEER_KIND[name] for name in later if name in names and (records.get(name) or {}).get('state') == 'read']


def peer_review_held(first):
    """Whether a member date conflict holds assess #1 ``first`` - the Corti run it read is the hold, or its context's
    service date is a member conflict - while which nothing is sent, a peer review included (owed_peer_stages)."""
    run, context = first.provider_run, first.context
    if (run is not None and run.state == models.ProviderRun.NOT_SENT
            and (run.scope or {}).get('held') == models.ProviderRun.HELD_MEMBER_DATE_CONFLICT):
        return True
    return context is not None and gi_context.is_member_conflict((context.facts or {}).get('service_date'))


def owed_peer_stages(first):
    """The peer stages assess #1 ``first`` owes (HARNESS.md 12.1), in order (_owed_peers) - and none while a member date
    conflict holds it (peer_review_held). stage_assess queues the first of them; an assessment that owes none is its
    chain's final assessment (review.is_final), and the reports say whether peer reviews follow by the same rule, so the
    pipeline, the API and the reports never disagree about which assessment is final."""
    return [] if peer_review_held(first) else _owed_peers(first)


def _assessment_base(assessment):
    """The base of the key of the assess that made ``assessment``, from its own row: 'assess:<context>:<Corti run or
    no-provider>', and ':review2:<that run>' when it read a second review. (An assess queued after a second review that
    did not succeed read none, so the base it was queued under also named that run; this one does not.)"""
    base = f'assess:{assessment.context_id}:{assessment.provider_run_id or "no-provider"}'
    return base + (f':review2:{assessment.second_run_id}' if assessment.second_run_id else '')


def _final_key(first):
    """assess #2's key (HARNESS.md 12.1): assess #1's base, ':q:' and 12 hex of the sha256 of the phase-1 runs ``first``
    read and of the peer runs made for it, each over the configured participants in stage order ('-' for none)."""
    records, names = _records(first), participants.configured()
    peers = [_peer_run(first.revision, name, first) for name in names]
    ids = [(records.get(name) or {}).get('run') or '-' for name in names]
    ids += [str(run.pk) if run is not None else '-' for run in peers]
    return f'{_assessment_base(first)}{FINAL_MARK}{hashlib.sha256(",".join(ids).encode()).hexdigest()[:12]}'


def _queue_peers(job, first, after=None, upgrade=False):
    """What follows assess #1 ``first`` (``after`` None) or the peer stage of participant ``after``: the next owed peer
    stage, carrying the context and the Corti run as the chain does; once none is owed after a peer stage, assess #2.
    None when assess #1 owes none: it is then the final assessment."""
    owed = _owed_peers(first, after)
    if owed:
        return enqueue(owed[0], encounter=job.encounter, revision=job.revision, context=job.context,
                       provider_run=job.provider_run, key=_peer_key(owed[0], first, upgrade),
                       requested_by=job.requested_by)
    if after is None:
        return None
    return enqueue(Job.ASSESS, encounter=job.encounter, revision=job.revision, context=job.context,
                   provider_run=job.provider_run, key=_final_key(first), requested_by=job.requested_by)


def _chain_upgrade(job):
    """Whether the assess #1 ``job`` ends a chain the upgrade's predict started: the newest phase-1 stage of its
    revision and context carries the mark (an assess a member's save queued directly has none), or the assess does
    itself. Its peer stages then carry the mark too, so they stop where they would send, as its participants did
    (refutation r1, migrate-5: an upgrade never sends a request nobody asked for). A member's Resume of the assess is a
    member's request."""
    if ':resume:' in job.idempotency_key:
        return False
    if job.idempotency_key.endswith(UPGRADE_MARK):  # an assess a remake no member asked for queued (_remade_context)
        return True
    last = (Job.objects.filter(revision=job.revision, context=job.context, kind__in=Job.PARTICIPANT_KINDS)
            .order_by('-created_at', '-pk').first())
    return last is not None and last.idempotency_key.endswith(UPGRADE_MARK)


def loop_run(run):
    """The run whose tool loop answered for ``run`` (HARNESS.md 12.1): itself, or for a reuse - which reuses the whole
    run and records no exchange - the retained run it reuses. Its exchanges and tool calls are the ones that stand for
    ``run``, and its reading's references are checked against their refs (run_refs)."""
    return run.reused_from if run.reused_from_id else run


def loop_runs(run) -> list:
    """The runs whose exchanges make up ``run``'s whole tool loop: loop_run(run) and, for a continuation (F-STOP), the
    stopped runs it continues, first run first (continued_runs)."""
    return continued_runs(loop_run(run))


def run_refs(run) -> frozenset:
    """Every ref the tool calls of ``run``'s own loop (loop_runs: a continuation's carried exchanges included, F-STOP)
    returned to the participant: what its reading's references_used is checked against (HARNESS.md 11.2)."""
    found = models.ToolCall.objects.filter(exchange__run__in=loop_runs(run)).values_list('refs', flat=True)
    return frozenset(ref for refs in found if isinstance(refs, list) for ref in refs if isinstance(ref, str))


def assessment_phase(assessment) -> int:
    """HARNESS.md 12.3: 0 when the assessment had no model participant configured (its record is harness@1's 'not
    configured') - and for no assessment -, else 2 when any entry has a peer state and 1 when none has. The one reading
    of an assessment's phase: the API's harness.phase, the trace and the reports read it here (review.assessment_phase).
    """
    if assessment is None:
        return 0
    records = [record for name, record in _records(assessment).items() if name in participants.PARTICIPANTS]
    if not any(record.get('state') != 'not_configured' for record in records):
        return 0
    return 2 if any('peer_state' in record for record in records) else 1


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
        created_by=created_by,
        # P5 FLOW: the document's own date before the member's value is merged, read from the facts the bounded child
        # returned (never the text again here), recorded beside the context and outside its sha256
        document_date=gi_context.document_service_date_fact(revision.text, facts=document_facts))


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
                  extraction_messages, second=None, second_scope=None, participant_inputs=(), confirmed=(),
                  member_answers=()):
    """The routing for ``service_date`` and the validation assessment that reads it, in one child: validation's span
    readings reuse the routing analysis the child already made. The documented-service inventory is read here too
    (engine @4), under the same deadline and memory limit. ``participant_inputs``: the configured harness participants'
    readings (HARNESS.md 5); ``confirmed``: the revision's reviewer-confirmed findings (HARNESS.md 12.5);
    ``member_answers``: the revision's standing member answers (member_answers_of; completion repair 2026-11-06). Each
    is passed to the engine only when there is one, so with none it is called exactly as before (I1)."""
    data = to_jsonable(gi_detect.route(text, service_date))
    harness = {'participants': participant_inputs} if participant_inputs else {}
    if confirmed:
        harness['confirmed'] = confirmed
    if member_answers:
        harness['member_answers'] = member_answers
    result = run_assessment(
        text=text, pages=pages, context=context, routing=from_jsonable(RoutingResult, data), normalized=normalized,
        reference=reference, service_date=service_date, provider_status=provider_status,
        extraction_status=extraction_status, extraction_messages=extraction_messages, second=second,
        second_scope=second_scope, **harness)
    return data, result


ROUTING_CACHE_MODULES = ('studio.gi.detect', 'studio.gi.sections', 'studio.gi.context', 'studio.validation.checks',
                         'studio.validation.engine',
                         # completion repair (builder A): the documented-service reader's text-keyed caches too
                         # (services._occasion_indications, with _report_physician_words and _act_frame), so nothing a
                         # stage read stays resident
                         'studio.gi.services',
                         # completion repair (builder R1): the structure overlay's caches
                         'studio.gi.structure')


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
    # one rule with the derived state's: an unknown outcome not reconciled, or a run left 'sending' by a stage that no
    # longer runs (decision (k), 2026-11-03: it blocks every send door like an unknown outcome)
    return review._unreconciled_unknown(encounter)


FAILED_BEFORE_MESSAGE = ('Nothing was sent: this request was sent before for this document and failed, and an '
                         'identical request is never sent again.')
FAILED_BEFORE_ERROR = ' Its error then: {error}'


def _failed_before(encounter, provider, request):
    """This encounter's newest run - any revision, whatever it was made for - that SENT ``request`` (provider, adapter
    version and body hash, as _run_answers compares them) and FAILED; None when there is none.

    Such a request is never sent again (refutation p1, sends-0..2: a date round trip, a cleared date after one whose
    request could not be built, a reconciliation's released attempt and an addendum that left a second review's excerpt
    as it was each re-sent one byte-identical). Each send door asks it after reusing a retained answer to the same
    request and after the unknown-outcome block, and before anything that sends: the predict records a not-sent run
    carrying the request (_not_resent_run) and re-assesses with it, the second review sends nothing and is refused when
    asked for. Another encounter's runs are not read: an upload is a member's new request."""
    return (models.ProviderRun.objects.filter(
        encounter=encounter, provider=provider.name, adapter_version=provider.adapter_version,
        request_sha256=request.canonical_sha256, state=models.ProviderRun.FAILED, sent=True)
        .order_by('-created_at').first())


MAX_CONTINUED_RUNS = 8  # runs one continuation chain may hold (each adds an exchange; max_exchanges bounds it too)


def _stopped_attempt(encounter, provider, request, purpose):
    """The stopped run a member's Resume continues (HARNESS.md, "Harness repair 3", F-STOP), or None: this encounter's
    newest finished run of ``request`` (the provider, the adapter version and the body's sha256, as _failed_before
    compares them) for ``purpose``, when it is a loop a member's Stop ended between exchanges - failed, sent, and marked
    'stopped_after_turn' by _finish_loop. Any other newest run (a success the stage reuses, a failure never sent again,
    an unknown outcome, a later continuation of it) is no stopped attempt. Read after the unknown-outcome block and
    before _failed_before, which a stopped run would otherwise answer: its request did not fail, it was paused."""
    # refutation round 1 of harness repair 3 (L6-1): the newest finished run that was SENT - a hold or another
    # not-sent run recorded after the Stop (an unknown outcome elsewhere, a refusal) never hides the stopped one
    run = _newest_finished(models.ProviderRun.objects.filter(
        encounter=encounter, provider=provider.name, adapter_version=provider.adapter_version,
        request_sha256=request.canonical_sha256, purpose=purpose, sent=True))
    # refutation cycle 2 (C2-5, an edge): a replay adapter shares the live adapter's version, so the mode is compared
    # too - a chain never mixes a live run and a replay one; a stopped run of the other mode is no attempt to continue
    if run is not None and (run.scope or {}).get('mode', 'live') != getattr(provider, 'mode', 'live'):
        return None
    return run if _resumable_stop(run) else None


def _resumable_stop(run) -> bool:
    """Whether ``run`` is a loop a member's Stop ended between exchanges (failed, sent, and marked 'stopped_after_turn'
    by _finish_loop): one a Resume continues from its record (F-STOP)."""
    return (run is not None and run.state == models.ProviderRun.FAILED and run.sent
            and isinstance((run.scope or {}).get('stopped_after_turn'), int))


def continued_runs(run) -> list:
    """``run`` and the stopped runs it continues (scope 'continues', F-STOP), first run first; [run] for a run that
    continues none. A chain that loops, or is longer than MAX_CONTINUED_RUNS, is cut where it does."""
    chain, seen = [run], {run.pk}
    while len(chain) < MAX_CONTINUED_RUNS:
        earlier = (chain[-1].scope or {}).get('continues')
        if not isinstance(earlier, str):
            break
        previous = models.ProviderRun.objects.filter(pk=earlier, encounter_id=run.encounter_id,
                                                     provider=run.provider).first()
        if previous is None or previous.pk in seen:
            break
        chain.append(previous)
        seen.add(previous.pk)
    return list(reversed(chain))


def _carried_exchanges(run) -> tuple:
    """The exchanges a continuation of stopped run ``run`` carries (F-STOP): every recorded exchange of ``run`` and of
    the runs it continues, in turn order, each with the tool calls it answered in the order they were recorded, exactly
    as recorded. The loop proves each one before it sends anything (loop._resumed)."""
    records = []
    for each in continued_runs(run):
        for exchange in each.exchanges.order_by('turn'):
            calls = tuple(participant_loop.ToolCallRecord(
                call_id=call.call_id, tool=call.tool, arguments=call.arguments, result=call.result,
                result_sha256=call.result_sha256, refs=tuple(call.refs or ()), executed_at=call.executed_at)
                for call in exchange.tool_calls.order_by('pk'))
            records.append(participant_loop.ExchangeRecord(
                turn=exchange.turn, request_body=exchange.request_body, request_sha256=exchange.request_sha256,
                outcome=exchange.state, http_status=exchange.http_status, response_bytes=bytes(exchange.response_bytes),
                response_sha256=exchange.response_sha256, latency_ms=exchange.latency_ms, usage=dict(exchange.usage),
                provider_request_id=exchange.provider_request_id, response_id=exchange.response_id,
                error=exchange.error, tool_calls=calls, started_at=exchange.started_at,
                finished_at=exchange.finished_at))
    return tuple(records)


def _not_resent_run(job, encounter, revision, provider, request, service_date, failed, **recorded):
    """The run a predict records where the send door met ``request`` already sent for this encounter that FAILED
    (``failed``): nothing is sent, and the run says so and gives that failure's error. It carries the request, so it
    answers it as the run in use - this revision's, and the installed revision's after a rollback: both read the
    revision's newest finished run, so neither sends that request behind a later save. Its start is recorded, as a
    reused run's is: it went through the send door, so no revision reads it as a reservation the stale sweep settled
    unsent, which still owes its attempt (round 7c8 skeptic, sk:2 and sk:3). ``recorded``: a harness participant's
    purpose, scope and identity columns (stage_participant); none for Corti's, whose row is as before."""
    now = timezone.now()
    error = FAILED_BEFORE_MESSAGE + (FAILED_BEFORE_ERROR.format(error=failed.error) if failed.error else '')
    return models.ProviderRun.objects.create(
        encounter=encounter, revision=revision, provider=provider.name, adapter_version=provider.adapter_version,
        request_sha256=request.canonical_sha256, request_body=request.body, contexts=list(request.contexts),
        state=models.ProviderRun.NOT_SENT, sent=False, error=error, authorization_ref=settings.AUTHORIZATION_REF,
        requested_by=job.requested_by, service_date=service_date, started_at=now, finished_at=now, **recorded)


def _retained_second_review(encounter, provider, request):
    """The workspace's retained answer to the second-review ``request`` (the original SUCCEEDED run, not a reuse of
    one), which stage_review2 reuses with nothing sent; None when there is none. The blocker asks the same lookup, so
    the offer and the stage never disagree about a reuse (round 7c8 skeptic: the offer refused, as a request that had
    failed here, one another encounter's identical request had since had answered)."""
    return models.ProviderRun.objects.filter(
        encounter__workspace=encounter.workspace, provider=provider.name, adapter_version=provider.adapter_version,
        request_sha256=request.canonical_sha256, state=models.ProviderRun.SUCCEEDED, reused_from__isnull=True,
        purpose=models.ProviderRun.SECOND_REVIEW).order_by('created_at').first()


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
    _after_extract(job, revision)
    return {'status': status}


def _after_extract(job, revision):
    """What a revision whose text was recorded runs next: its interpretation (design/FINAL.md 6.2; extract used to queue
    the legacy analyze). tests/legacy_chain.py replaces this, with the other seams named there, so the legacy
    regression suites still run the legacy chain; no production switch exists (FINAL 16.14)."""
    return enqueue(INTERPRET, encounter=job.encounter, revision=revision, key=_interpret_key(revision),
                   requested_by=job.requested_by)


# --- analyze: derive only (design/FINAL.md 6.4) ------------------------------------------------------------------------
#
# The analyze stage of the Gemini migration reads no text: it loads the EventInventory its key names
# ('analyze:<revision>:<inventory>'), derives the gemini-context@1 facts from it with the encounter's member values
# (interpretation.facts.derive: pure, no fork, no network, no legacy call) and records that context with its RoutingRun
# stand-in, makes it current under the row lock, and queues the predict exactly as before (_queue_predict, whose hold test
# reads the re-homed is_member_conflict over the derived facts). The legacy stage it replaces - _analyze_child's
# mention gate, gi.context.extract_context and gi.detect.route - lives on only in tests/legacy_chain.py; the archived
# children it called stay below for the rollback image's records and that test-only chain.

EARLIER_READING_MESSAGE = 'This document was read by an earlier version. Resume to have it read again.'
INVENTORY_NOT_READ_MESSAGE = ('The interpretation this stage reads was not read whole (it is missing, was refused or '
                              'is not this revision\'s); nothing was derived from it.')
CONTEXT_DATE_MESSAGE = 'The derived context names another service date than its derivation; nothing was used.'


def _analyze_inventory_id(job):
    """The EventInventory id an analyze stage's key names ('analyze:<revision>:<inventory>', a Resume's suffix aside), or
    None for a key of the legacy shape ('analyze:<revision>', or a Resume of an extract): a stage queued before the
    install, which this image never runs as it was (FINAL 9)."""
    parts = job.idempotency_key.split(':resume:', 1)[0].split(':')
    if len(parts) != 3 or parts[0] != Job.ANALYZE or parts[1] != str(job.revision_id):
        return None
    try:
        return uuid.UUID(parts[2])
    except ValueError:
        return None


def _gate(entry, encounter):
    """A new-path write gate (FINAL 10.3): None when the write may proceed; otherwise the refusal (CPT Studio's
    sentence, an AuditEvent 'sentinel.tripped' already recorded) as the stage's failure. Asked before the write."""
    try:
        sentinel.gate(entry, encounter=encounter)
    except sentinel.Tripped as exc:
        raise StageFailure(str(exc)) from None


def _stored_inventory(inventory, revision):
    """The EventInventory row ``inventory`` as interpretation.store.load reads and checks it, against ``revision``'s text
    sha256 and the sha256 of its run's stored response bytes as computed now (P6: every new-path consumer reads the
    stored row, never the text). A row the store cannot read fails the stage with the store's own sentence."""
    data = bytes(inventory.provider_run.response_bytes or b'')
    try:
        return inventory_store.load(inventory_store.fields_of(inventory), text_sha256=revision.text_sha256,
                                    response_sha256=hashlib.sha256(data).hexdigest())
    except inventory_store.StoreError as exc:
        raise StageFailure(f'The stored interpretation could not be read: {exc}') from None


def derived_facts(encounter, inventory, stored):
    """interpretation.facts.derive over the FROZEN inventory ``stored`` (its row ``inventory``) with ``encounter``'s
    member values: what a gemini-context@1 row records. Pure. A member value the derivation refuses (an unknown name, a
    value not valid for its fact) fails the stage, as the legacy merge refused it."""
    try:
        return interpretation_facts.derive(stored, dict(encounter.user_values or {}))
    except (TypeError, ValueError) as exc:
        raise StageFailure(f'The encounter context could not be derived from the interpretation: {exc}') from None


def record_derived_context(encounter, revision, inventory, derived, *, created_by=None):
    """The EncounterContext row of ``derived`` (derived_facts) for ``revision``: version gemini-context@1, bound to its
    EventInventory (FINAL 4.2-4.3, D6), the facts in the legacy Fact shape with service_date's ``state``, the member
    values, and document_date in the shape answers.py reads. Its sha256 also names the inventory it was derived from.
    The caller asks the write gate first (analyze; a context save)."""
    user_values = dict(encounter.user_values or {})
    facts = derived.facts
    return models.EncounterContext.objects.create(
        encounter=encounter, revision=revision, facts=facts, user_values=user_values,
        version=interpretation.CONTEXT_VERSION, created_by=created_by, document_date=derived.document_date,
        event_inventory=inventory,
        sha256=sha256_json({'facts': facts, 'user_values': user_values, 'revision': str(revision.pk),
                            'event_inventory': str(inventory.pk)}))


def _stand_in(revision, inventory, stored, service_date):
    """The gemini-routing@1 stand-in record for ``service_date`` (FINAL 4.3, 6.5): pure, no mention and no cue."""
    return interpretation_facts.routing_stand_in(stored, service_date, inventory_id=str(inventory.pk),
                                                 inventory_sha256=inventory.sha256)


def stage_analyze(job):
    """Derive only (FINAL 6.4): the inventory the key names (same revision, the current versions, state read), its
    derived context and stand-in recorded under the new_path gate, the context made current under the row lock, and the
    predict queued as before. A key of the legacy shape - a stage queued before the install - or an inventory of other
    versions ends resumable: a Resume has the revision read again (FINAL 9)."""
    revision, encounter = job.revision, job.encounter
    pk = _analyze_inventory_id(job)
    if pk is None:
        raise StageCancelled(EARLIER_READING_MESSAGE)
    revision.refresh_from_db()
    inventory = (models.EventInventory.objects.filter(pk=pk, encounter_id=encounter.pk, revision_id=revision.pk)
                 .select_related('provider_run').first())
    if inventory is not None and (inventory.interpretation_version, inventory.inventory_version) != _CURRENT_VERSIONS:
        raise StageCancelled(EARLIER_READING_MESSAGE)
    if inventory is None or inventory.state != models.EventInventory.READ:
        raise StageFailure(INVENTORY_NOT_READ_MESSAGE)
    stored = _stored_inventory(inventory, revision)
    encounter.refresh_from_db()
    derived = derived_facts(encounter, inventory, stored)
    service_date = date.fromisoformat(derived.effective) if derived.effective else None
    data = _stand_in(revision, inventory, stored, service_date)
    _gate('analyze', encounter)
    context = record_derived_context(encounter, revision, inventory, derived)
    if context_service_date(context) != service_date:  # one date: the context's, its stand-in's and the request's
        raise StageFailure(CONTEXT_DATE_MESSAGE)
    routing = _record_routing(revision, data, service_date)
    with transaction.atomic():
        locked = models.Encounter.objects.select_for_update().get(pk=encounter.pk)
        if locked.current_revision_id == revision.pk:
            locked.current_context = context
            locked.save(update_fields=['current_context', 'updated_at'])
    # FINAL 6.4 step 4: _queue_predict unchanged - a held member date records the not-sent hold run and queues the
    # assess, exactly as for a legacy context, since the held rows carry the legacy note (dates.member_date_state)
    _queue_predict(encounter, revision, context, key=f'predict:{context.pk}', requested_by=job.requested_by)
    return {'context': str(context.pk), 'routing': str(routing.pk), 'inventory': str(inventory.pk),
            'member_date_state': derived.member_date.state}


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
    # What was called and what answered (HARNESS.md 6): the adapter's record, or what the reservation named when the
    # exchange names none (a request that never left); the models are '' for Corti, whose API names none.
    run.endpoint = (exchange.endpoint or run.endpoint)[:200]
    run.requested_model = (exchange.requested_model or run.requested_model)[:100]
    run.returned_model = exchange.returned_model[:100]
    run.response_id = exchange.response_id[:140]
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
    remade = f'the context was recorded by {context.version}; it was remade under {CONTEXT_VERSION}'
    if _run_answers(last_run, revision, fresh):
        # harness@2 (HARNESS.md 12.1): an assess #1 queues the peer reviews, which send. An assess a remake no member
        # asked for queues - the stages the branch below names - carries the upgrade's mark, so its peer stages stop
        # where they would send until a member's Resume (_chain_upgrade); with no participant configured, none (I1).
        member = job.kind == Job.PREDICT and job.idempotency_key != _upgrade_predict_key(context)
        mark = UPGRADE_MARK if participants.configured() and not member else ''
        enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=fresh, provider_run=last_run,
                key=_assess_key(f'assess:{fresh.pk}:{last_run.pk}', revision) + mark, requested_by=job.requested_by)
    elif (job.kind == Job.PREDICT and job.idempotency_key != _upgrade_predict_key(context)
          or gi_context.is_member_conflict((fresh.facts or {}).get('service_date'))):
        # the request a member's action queued (an upload, a date change, a Resume, a reconciliation), or the hold. An
        # upgrade's own predict, queued under an earlier revision at a stage that never sends, is no member's request:
        # remade again, it queues the upgrade's predict for the fresh context below, which never sends either (the
        # narrow release's second refutation, STATE2N-1: 90377ec6f413's after-upgrade predict, still queued at the
        # swap, was remade into this ordinary predict and sent)
        _queue_predict(encounter, revision, fresh, key=f'predict:{fresh.pk}', requested_by=job.requested_by)
    else:
        # Refutation r1, migrate-5 (ec5): this stage never sends - an assess the earlier revision queued or a member
        # resumed, or the stale-stage sweep's settlement of its predict - so neither does the predict it queues for the
        # remade context. That predict runs as any other (a request that cannot be built, a retained answer, an
        # unknown outcome to reconcile: each recorded and shown as itself) and stops only where it would send - or, with
        # sending disabled, where an assessment with no answer would replace a recorded request (STATE2-1) - for a
        # member's Resume (stage_predict; ec5 skeptic: a stop recorded here for every request the run in use does not
        # answer said "differs from the one sent before. Resume to send it." where nothing had been sent, where nothing
        # could be built, and while an unknown outcome blocked every send).
        _queue_predict(encounter, revision, fresh, key=_upgrade_predict_key(fresh), requested_by=job.requested_by)
    return {'skipped': remade}


REMADE_REQUEST_MESSAGE = ('Nothing was sent: after an upgrade this document was read again under the current rules, '
                          'and the request they make for it differs from the one sent before. Resume to send it.')
REMADE_UNANSWERED_MESSAGE = ('Nothing was sent: after an upgrade this document was read again under the current '
                             'rules, and no provider answer is recorded for the request they make for it. Resume to '
                             'send it.')
REMADE_DISABLED_MESSAGE = ('Nothing was sent: after an upgrade this document was read again under the current rules, '
                           'and sending is disabled. What is recorded for it stays as it is; once sending is enabled, '
                           'Resume to send the request the current rules make.')


def _upgrade_predict_key(context):
    """The key of the predict an upgrade's remake queues at a stage that never sends: that predict never sends."""
    return f'predict:{context.pk}:after-upgrade'


def _remade_request_message(revision, request):
    """Why the upgrade's predict stopped where it would send ``request``, worded from what is recorded: "differs from
    the one sent before" only when the run in use carries another request (provider, adapter and body, as _run_answers
    compares them) that was sent."""
    run = _run_in_use(revision)
    sent = run is not None and run.sent and bool(run.request_sha256)
    if sent and (run.provider, run.adapter_version, run.request_sha256) != (
            request.provider, request.adapter_version, request.canonical_sha256):
        return REMADE_REQUEST_MESSAGE
    return REMADE_UNANSWERED_MESSAGE


def _earlier_reading(job):
    """FINAL 6.5 and 9: this image never remakes a context that is not a gemini context, nor sends or assesses on one -
    a stage queued before the install, a Resume of one, or a stale sweep's successor on a legacy context ends
    StageCancelled (resumable: a member's Resume has the revision read again, resume). None for a gemini context, or a
    stage given none. Replaced by the test-only legacy chain (tests/legacy_chain.py: the legacy _remade_context), which
    is the only way the legacy branches after it still run; no production switch exists (FINAL 16.14)."""
    if job.context is not None and not interpretation.is_new_context(job.context):
        raise StageCancelled(EARLIER_READING_MESSAGE)
    return None


def _legacy_reading_allowed() -> bool:
    """Whether the LEGACY chain may run on a context that is not a gemini context: never on this image (design/FINAL.md
    6.7, 6.10 and 9). So an assess, a participant's first reading or peer review, or a second review given such a
    context ends StageCancelled (_refuse_legacy_context; resumable: a member's Resume has the revision read again); a
    context save on a revision with no gemini context stores the member's values and has the revision read
    (change_context); an answer's recompute leaves the answer on the legacy overlay (recompute_after_answers); a
    re-assessment from retained answers refuses a legacy final (reassess_retained); and no second review is offered on
    one (_second_review_bounds). Replaced by the test-only legacy chain (tests/legacy_chain.py, slice S15: True), which
    is the only way the legacy branches after each of those tests still run; no production switch exists (FINAL
    16.14)."""
    return False


def _refuse_legacy_context(job):
    """FINAL 6.7 and 9: a stage given no context, or one that is not a gemini context - queued before the install, a
    Resume of one, a stale sweep's successor - ends StageCancelled (resumable) on this image: the legacy child never
    runs and nothing is sent on it (_legacy_reading_allowed)."""
    if (job.context is None or not interpretation.is_new_context(job.context)) and not _legacy_reading_allowed():
        raise StageCancelled(EARLIER_READING_MESSAGE)


def _route_by_stand_in(job, context, service_date):
    """The RoutingRun a predict on a gemini context needs for ``service_date`` (FINAL 6.5): the stand-in derived from the
    context's own inventory (Job.context names it: never the newest inventory), recorded once per inventory and date
    under the new_path write gate (_record_routing keeps one row per distinct record). Nothing reads text, and the
    legacy router (_route_child) is never called."""
    inventory = context.event_inventory
    if inventory is None:
        raise StageFailure('The context names no event inventory, so nothing can be routed or sent for it.')
    if models.RoutingRun.objects.filter(revision_id=context.revision_id, service_date=service_date,
                                        version=interpretation.ROUTING_VERSION,
                                        result__inventory=str(inventory.pk)).exists():
        return
    stored = _stored_inventory(inventory, job.revision)
    data = _stand_in(job.revision, inventory, stored, service_date)
    _gate('predict', job.encounter)
    _record_routing(job.revision, data, service_date)


def stage_predict(job):
    revision, encounter, context = job.revision, job.encounter, job.context
    encounter.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists; nothing was sent'}
    if context is None or context.revision_id != revision.pk or encounter.current_context_id != context.pk:
        # Provider input is only ever the current revision's text with that revision's current context.
        return {'skipped': 'the context is not the current one for this revision; nothing was sent'}
    remade = _earlier_reading(job)  # FINAL 6.5: a context that is not a gemini context is never remade on this image
    if remade is not None:
        return remade
    provider = get_provider()
    service_date = context_service_date(context)
    if interpretation.is_new_context(context):
        # FINAL 6.5: the RoutingRun gate on a gemini context is its derived stand-in for the date (pure; _route_child is
        # never called), recorded before anything is built, sent or held, so every later stage finds it for the date
        _route_by_stand_in(job, context, service_date)
    assess_key = f'assess:{context.pk}'

    def next_assess(run):
        # the assess, or with a harness participant configured its chain (HARNESS.md 2), which goes on to the assess
        _after_predict(encounter, revision, context, run, key=f'{assess_key}:{run.pk if run else "no-provider"}',
                       origin=str(job.pk), requested_by=job.requested_by,
                       upgrade=job.idempotency_key == _upgrade_predict_key(context))

    if provider is None and job.idempotency_key == _upgrade_predict_key(context) and _recorded_in_use(revision):
        # gi3 (STATE2-1; the narrow release's refutation, STATE-N1 and STATE-N2): with sending disabled, the predict an
        # upgrade's remake queued never replaces what is recorded for this revision with 'provider not run'. An outcome
        # still unknown blocks it, as it blocks every send, and the encounter reads 'provider_unknown'; any other
        # recorded request (succeeded or failed) stops it, and that record stays as it is until a member's Resume once
        # sending is enabled. With no request recorded it runs as before (ec5 skeptic:1).
        if _unreconciled_unknown(encounter):
            return {'blocked': 'a previous request has an unknown outcome; reconcile it before sending again'}
        raise StageCancelled(REMADE_DISABLED_MESSAGE)
    if provider is None:
        next_assess(None)
        return {'provider': 'disabled'}
    if gi_context.is_member_conflict((context.facts or {}).get('service_date')):
        # Session interpretation 19: a member-entered service date that differs from the document's is a conflict with
        # both sides kept (interpretation 11), so the request has no date it can carry. Nothing is built, reused or
        # sent while it stands - a dateless request would be paid for and discarded once the date is settled - and the
        # encounter asks the date question. Correcting or clearing the metadata starts the request for its date. Every
        # path that queues a predict records this hold itself (_queue_predict); this holds one queued any other way. No
        # harness participant is sent to while it stands either: the assess follows the hold directly.
        run = _member_date_hold(encounter, revision, provider, job.requested_by)
        enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=run,
                key=_assess_key(f'{assess_key}:{run.pk}', revision), requested_by=job.requested_by)
        return {'provider': 'not_sent', 'reason': 'member-entered service date conflicts with the document'}
    if (not interpretation.is_new_context(context)
            and not models.RoutingRun.objects.filter(revision=revision, service_date=service_date).exists()):
        # Nothing is sent for a date this revision was never routed for (round 6 pipeline:0): after a date change the
        # new date is routed first, in one bounded child under the analyze deadline, so a document that cannot be read
        # for that date fails here with the plain message and no request is built, reused or sent. A context that is not
        # a gemini context reaches here only through the test-only legacy chain (tests/legacy_chain.py): on this image
        # _earlier_reading ends such a stage before anything else (FINAL 6.5).
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

    failed = _failed_before(encounter, provider, request)
    if failed is not None:
        # Refutation p1, sends-0 and sends-2: this request was sent before and FAILED, so it is never sent again - not
        # after a date round trip or a cleared date, and not as a reconciliation's released attempt. The stage ends as
        # that request did (provider_failed), with a run of its own, as a predict that reuses, sends or cannot build
        # its request ends: re-assessing with the OLDER failed run left a newer one as the revision's newest finished
        # run, which is the run in use for every later save here (a member date never sent was then never attempted
        # again) and for the installed revision after a rollback (its setting save re-sent the failed request; round
        # 7c8 skeptic, sk:2 and sk:3).
        run = _not_resent_run(job, encounter, revision, provider, request, service_date, failed)
        next_assess(run)
        return {'provider': 'not_resent', 'run': str(run.pk)}

    _live_gate(job, provider, revision, encounter)
    if job.idempotency_key == _upgrade_predict_key(context):
        # Refutation r1, migrate-5 (ec5): the predict an upgrade's remake queued at a stage that never sends stops here,
        # where it would send - the system's stop, with the reason - and only a member's Resume sends the request.
        raise StageCancelled(_remade_request_message(revision, request))

    run = _send(job, provider, request, service_date=service_date)
    next_assess(run)
    return {'provider': run.state, 'run': str(run.pk)}


def _send(job, provider, request, *, service_date, purpose=models.ProviderRun.PRIMARY, scope=None, original_bytes=None,
          execute_tool=None, continues=None):
    """One provider attempt under the send discipline (ARCHITECTURE 5.4): single-flight by advisory lock, the run
    written 'reserved' before any network I/O, a Stop observed before sending, no automatic retry, and the outcome -
    including an unknown one - recorded with the raw bytes and usage.

    A harness participant's attempt (purpose 'independent' or 'peer_review', HARNESS.md 2-3, 11, 12.1) is the same send
    through the participant's own contract: its reservation names the endpoint and model it calls, and the run is ONE
    tool loop (send_loop) under the provider lock, given the loop deadline, the run's identity as the client request id,
    CPT Studio's CMS tool executor (``execute_tool``; studio.reference.tools for the encounter's workspace when none is
    given) and ``original_bytes`` - a PDF upload's original, read back through studio.storage against its sha256 - to be
    re-verified against the request and expanded at send time. Every exchange and tool call of the loop is recorded with
    the run's outcome (_finish_loop). A member's Stop is observed before every exchange of the loop, not only the first
    (refutation round 1, sends-3): one recorded while the loop runs ends it before its next exchange, the run records
    the exchanges sent (failed, sent: it has no final answer) and the stage ends stopped. Since harness repair 3
    (HARNESS.md, "Harness repair 3", F-STOP) such a run is marked resumable (scope 'stopped_after_turn'), and
    ``continues`` - the stopped run a member's Resume continues (_stopped_attempt) - makes this attempt its
    continuation: a run of its own, with its own identity and the same request, whose loop carries the stopped run's
    exchanges (_carried_exchanges, never sent again) and sends from the next exchange on; its scope names the run it
    continues. Corti's path is unchanged.

    The interpreter's attempt (purpose 'interpretation', design/FINAL.md 6.3) takes the looped branch too
    (LOOPED_PURPOSES): its reservation names the endpoint and the model, its one exchange is recorded as turn 1
    (_finish_loop, _record_exchange), a Stop is observed before the send, an orphan is settled by
    may_have_reached_vendor, and its loop deadline is INTERPRETER_SEND_DEADLINE_SECONDS (_check_loop_time). It is
    offered no tool: the executor it is given refuses any call (Gemini is offered none, so none is ever asked for)."""
    encounter, revision = job.encounter, job.revision
    independent = purpose in LOOPED_PURPOSES
    carried = ()
    if continues is not None:
        carried = _carried_exchanges(continues)
        scope = {**(scope or {}), 'continues': str(continues.pk), 'continues_after_turn': len(carried)}
    if independent:
        # before anything is reserved: a loop that could outrun the stage's deadline never starts
        _check_loop_time(job, purpose)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [PROVIDER_LOCK_KEY])
        if not cursor.fetchone()[0]:
            raise Requeue('another provider request is in flight')
    try:
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=revision, provider=provider.name, adapter_version=provider.adapter_version,
            request_sha256=request.canonical_sha256, request_body=request.body, contexts=list(request.contexts),
            state=models.ProviderRun.RESERVED, authorization_ref=settings.AUTHORIZATION_REF,
            requested_by=job.requested_by, service_date=service_date, purpose=purpose, scope=scope or {},
            **(_participant_identity(provider) if independent else {}))
        try:
            if _stop_requested(job, encounter):
                run.state = models.ProviderRun.CANCELLED
                run.error = 'Stopped before sending; nothing was sent.'
                run.finished_at = timezone.now()
                run.save()
                raise StageCancelled('Stopped before the provider request was sent.')
            run.state = models.ProviderRun.SENDING
            run.started_at = timezone.now()
            run.save(update_fields=['state', 'started_at'])
        except StageCancelled:
            raise
        except Exception:
            # Refutation r2, L5-3: the stage fails between the reservation and the send (a read of the Stop or the
            # write that marks the run sending raised), so nothing reached the provider. The run is never left
            # 'reserved', which nothing settles once its stage has ended: it is recorded not sent, and the stage fails
            # as before.
            _settle_reservation(run)
            raise
        audit.record(encounter.workspace, 'provider.sending', encounter=encounter, run=str(run.pk),
                     provider=provider.name, mode=provider.mode, request_sha256=request.canonical_sha256,
                     run_identity=str(run.run_identity), purpose=purpose,
                     **({'continues': str(continues.pk), 'continues_after_turn': len(carried)}
                        if continues is not None else {}))
        outcome = None
        if independent:
            if purpose == INTERPRETATION:
                tools, deadline = _no_interpretation_tool, settings.INTERPRETER_SEND_DEADLINE_SECONDS
            else:
                tools = execute_tool or reference_tools.executor(encounter.workspace)
                deadline = settings.PARTICIPANT_LOOP_DEADLINE_SECONDS
            outcome = _send_loop(provider, request, run, original_bytes, tools, lambda: _stop_requested(job, encounter),
                                 carried=carried, deadline_s=deadline)
            _finish_loop(run, outcome)
        else:
            exchange = provider.send(request, deadline_s=settings.PROVIDER_READ_TIMEOUT_SECONDS + 30)
            try:
                _finish_run(run, exchange)
            except Exception:  # noqa: BLE001 - logged; the run records why, never the internals
                # Decision (k) (2026-11-03; R6 4.6): the answer arrived and its outcome could not be recorded. The run
                # is never left 'sending' - a failed job is not swept, so nothing would block an identical send - but
                # recorded unknown, as _finish_loop records a participant's: it may have reached the vendor and been
                # billed, so every send door waits on its reconciliation. The stage fails as before.
                log.exception('the outcome of provider run %s could not be recorded', run.pk)
                _settle_unrecorded(run, exchange)
                raise
        # a participant's row names its provider, so the Activity tab words it ("Astra response recorded")
        audit.record(encounter.workspace, 'provider.finished', encounter=encounter, run=str(run.pk),
                     state=run.state, http_status=run.http_status, usage=run.usage, latency_ms=run.latency_ms,
                     purpose=purpose, **({'provider': provider.name} if independent else {}))
        if outcome is not None and outcome.stopped:
            raise StageCancelled(STOPPED_BEFORE_SEND_MESSAGE if purpose == INTERPRETATION else STOPPED_IN_LOOP_MESSAGE)
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK_KEY])
    return run


def _no_interpretation_tool(name, arguments):
    """The tool executor an interpretation's loop is given (FINAL 6.3: Gemini sends no tools; the executor refuses any):
    CPT Studio offers the interpreter no tool, so a call is answered with a refusal and nothing is looked up."""
    return {'error': 'CPT Studio offers no tool to this request.'}, ()


UNRECORDED_OUTCOME_MESSAGE = ('The answer arrived but its outcome could not be recorded (logged). The request may have '
                              'reached the vendor and been billed: it is recorded with an unknown outcome, and nothing '
                              'is sent again until it is reconciled.')
ORPHANED_SENDING_MESSAGE = ('The stage that sent this request ended without recording its outcome. The request may have '
                            'reached the vendor and been billed: it is recorded with an unknown outcome, and nothing is '
                            'sent again until it is reconciled.')
UNSENT_RESERVATION_MESSAGE = ('Nothing was sent: the stage stopped with an unexpected error (logged) after reserving '
                              'this request and before sending it.')
ORPHANED_RESERVATION_MESSAGE = ('Nothing was sent: the stage that reserved this request ended before sending it.')


def _settle_reservation(run):
    """Refutation r2, L5-3: ``run``, reserved and never marked sending - nothing reached the provider - recorded not
    sent once its stage failed, with no start recorded: a reservation settled unsent still owes the attempt it reserved
    (_run_in_use, _newest_finished and _unsent_attempt read one so, as they read a dead worker's). Only while it is
    still 'reserved'. A failure here is logged; the stale sweep settles it (mark_stale)."""
    try:
        models.ProviderRun.objects.filter(pk=run.pk, state=models.ProviderRun.RESERVED).update(
            state=models.ProviderRun.NOT_SENT, sent=False, error=UNSENT_RESERVATION_MESSAGE, finished_at=timezone.now())
    except Exception:  # noqa: BLE001 - logged; the sweep settles a reservation whose stage no longer runs
        log.exception('provider run %s could not be settled as not sent after its stage failed', run.pk)


def _settle_unrecorded(run, exchange):
    """Decision (k): ``run`` (still 'sending') recorded unknown - or not sent, where its exchange provably sent nothing -
    with only small fields written, since writing the whole outcome just failed. A failure here is logged and leaves
    the run 'sending', which every send door still reads as an unknown outcome (review._orphaned_sending) and the stale
    sweep settles (mark_stale)."""
    unsent = exchange.outcome == 'not_sent' and not exchange.sent
    try:
        models.ProviderRun.objects.filter(pk=run.pk, state=models.ProviderRun.SENDING).update(
            state=models.ProviderRun.NOT_SENT if unsent else models.ProviderRun.UNKNOWN, sent=bool(exchange.sent),
            error='Nothing was sent; its record could not be written (logged).' if unsent else UNRECORDED_OUTCOME_MESSAGE,
            finished_at=timezone.now())
    except Exception:  # noqa: BLE001 - logged; the run stays 'sending', which blocks every send door
        log.exception('provider run %s could not be settled after its outcome failed to record', run.pk)


def _stop_requested(job, encounter):
    """Whether a member's Stop was recorded for ``job`` or its encounter, read again from the database: before the
    send, and before every later exchange of a participant's tool loop."""
    job.refresh_from_db(fields=['stop_requested_at'])
    return bool(job.stop_requested_at) or is_stopped(encounter.pk)


PARTICIPANT_PURPOSES = (models.ProviderRun.INDEPENDENT, models.ProviderRun.PEER_REVIEW)
# The purposes _send runs as one loop (FINAL 6.3): the participants' and the interpreter's (whose loop is one exchange).
LOOPED_PURPOSES = PARTICIPANT_PURPOSES + (INTERPRETATION,)
STOPPED_IN_LOOP_MESSAGE = ('Stopped by a workspace member while the tool loop ran: what was sent is recorded, and '
                           'nothing more was sent.')
STOPPED_BEFORE_SEND_MESSAGE = 'Stopped by a workspace member before the request was sent; nothing was sent.'
LOOP_RECORDING_SECONDS = 15  # kept, after a whole tool loop, for recording its outcome within the stage's deadline
LOOP_LATE_MESSAGE = ('the stage has run too long to finish a whole tool loop before its deadline; nothing was reserved '
                     'or sent, and it starts again')
UNRECORDED_MESSAGE = ('The {label} outcome could not be recorded whole (logged), so what reached the vendor is not '
                      'known. The outcome is unknown; reconcile it before any new attempt.')
UNRECORDED_REPLAY_MESSAGE = ('The {label} outcome could not be recorded whole (logged). It was replayed from a '
                             'recorded response and called no vendor, so nothing was sent. The outcome is unknown; '
                             'reconcile it before any new attempt.')
LOOP_OUTCOMES = ('succeeded', 'failed', 'unknown', 'not_sent')


def _check_loop_time(job, purpose=None):
    """HARNESS.md 12.1: a phase-1 or peer job's deadline - JOB_DEADLINE_SECONDS for its kind, never past
    STALE_RUNNING_SECONDS, where the stale-stage sweep takes a stage for dead - covers the tool loop's own deadline
    (PARTICIPANT_LOOP_DEADLINE_SECONDS) plus the stage's bookkeeping. A stage that has already used so much of it that a
    whole loop and its recording would no longer fit reserves and sends nothing: it is queued again (Requeue) and starts
    afresh. The deadline is the purpose's (FINAL 6.3): INTERPRETER_SEND_DEADLINE_SECONDS (510 s, D49) for an
    interpretation, whose stage has JOB_DEADLINE_SECONDS['interpret'] (560 s), and the participants' 540 s otherwise."""
    if job.started_at is None:
        return
    budget = min(settings.JOB_DEADLINE_SECONDS.get(job.kind, settings.STALE_RUNNING_SECONDS),
                 settings.STALE_RUNNING_SECONDS)
    loop = (settings.INTERPRETER_SEND_DEADLINE_SECONDS if purpose == INTERPRETATION
            else settings.PARTICIPANT_LOOP_DEADLINE_SECONDS)
    used = (timezone.now() - job.started_at).total_seconds()
    if used + loop + LOOP_RECORDING_SECONDS > budget:
        raise Requeue(LOOP_LATE_MESSAGE)


LOOP_LOCK_LOST_MESSAGE = ('The database session that held the provider lock, which keeps every other provider request '
                          'waiting, ended while the tool loop ran, after {number} exchange{plural}; nothing more was '
                          'sent, and the run has no final answer.')


class _ProviderLockLost(Exception):
    """This database session does not hold the installation-wide provider lock that _send took on its session."""


def _holds_provider_lock():
    """Whether this database session holds the installation-wide provider lock (PROVIDER_LOCK_KEY), as PostgreSQL's
    lock table says (a bigint advisory key is its classid and objid halves, objsubid 1). A session advisory lock is held
    only by the session that took it until that session ends, so a session Django opened after that one ended - a
    transaction.atomic whose rollback fails closes the connection and opens another - never holds it (refutation
    round 3, sends-1). A query that fails raises, and the loop never goes on without knowing (loop._halt)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND granted "
                       'AND pid = pg_backend_pid() AND objsubid = 1 AND (classid::bigint << 32) + objid::bigint = %s)',
                       [PROVIDER_LOCK_KEY])
        return bool(cursor.fetchone()[0])


def _loop_label(name):
    """The word a loop's run errors name its sender by: a participant's label (Astra, Fable); 'interpretation' for the
    interpreter, whose errors name no provider (D22)."""
    return 'interpretation' if name == interpretation.PROVIDER else participants.LABELS.get(name, name)


def _send_loop(provider, request, run, original_bytes, execute_tool, should_stop, carried=(), deadline_s=None):
    """The participant's one tool loop (HARNESS.md 11.2): a loop.LoopOutcome. An adapter answers every run with one; one
    that raised instead, or answered with anything else, may have sent the request, so the outcome is unknown, with no
    exchange recorded but those recorded as they ended, and blocks every further send until a member reconciles it -
    never a run left 'sending' that nothing blocks on and no member can reconcile (I8). ``should_stop``: the member's
    Stop, observed before every later exchange (sends-3). Each exchange is recorded as it ends (_record_exchange,
    refutation round 2, sends-r2-4: they were written only once the whole loop had ended, so a worker that died
    mid-loop - SIGKILL, an OOM kill, a host reset - left nothing of exchanges that had been answered and paid for).

    The check the loop asks before it goes on after an exchange (before it answers the tool calls, and again right
    before the next exchange is sent) also asks, after the member's Stop, whether this database session still holds
    the provider lock _send took (_holds_provider_lock; refutation round 3, sends-1, I8): the last thing read from
    the database before each later exchange is sent. An exchange's record that met an ended session let Django open
    another one, which never took the lock, and the loop sent its next exchange while any other session could take
    the lock and send. Once the session that holds the lock is gone, the loop ends there and nothing more is sent:
    the run has no final answer and is failed and sent with the exchanges sent so far, in CPT Studio's own sentence
    (LOOP_LOCK_LOST_MESSAGE) - never as a member's Stop, so the stage ends as a failed participant's does (I10). A
    check that fails on the ended session itself stops the loop as before (loop._halt), and the stale sweep settles
    the run."""
    lost = []

    def checked():
        if should_stop():
            return True
        if not _holds_provider_lock():
            lost.append(True)
            raise _ProviderLockLost()
        return False
    try:
        with participant_loop.recording(lambda record: _record_exchange(run, record)):
            outcome = provider.send_loop(request, deadline_s=deadline_s or settings.PARTICIPANT_LOOP_DEADLINE_SECONDS,
                                         client_request_id=str(run.run_identity), original_bytes=original_bytes,
                                         execute_tool=execute_tool, should_stop=checked,
                                         **({'carried': carried} if carried else {}))
        if (not isinstance(outcome, participant_loop.LoopOutcome) or not isinstance(outcome.final, RawExchange)
                or outcome.final.outcome not in LOOP_OUTCOMES or not isinstance(outcome.exchanges, tuple)
                or not all(isinstance(item, participant_loop.ExchangeRecord) for item in outcome.exchanges)):
            raise TypeError(f'send_loop answered with {type(outcome).__name__}, not a loop.LoopOutcome')
    except Exception as exc:  # noqa: BLE001 - logged; the run records why, never the internals
        log.exception('participant %s raised while sending run %s', provider.name, run.pk)
        return participant_loop.LoopOutcome(final=RawExchange(
            outcome='unknown', sent=True, error=PARTICIPANT_RAISED_MESSAGE.format(
                label=_loop_label(provider.name), error=type(exc).__name__)))
    if lost and outcome.stopped:  # the loop ended at the check that found the lock gone (it never goes on after one)
        number = len(outcome.exchanges)
        error = LOOP_LOCK_LOST_MESSAGE.format(number=number, plural='' if number == 1 else 's')
        return participant_loop.LoopOutcome(final=dataclasses.replace(outcome.final, error=error),
                                            exchanges=outcome.exchanges)
    return outcome


def _finish_loop(run, outcome):
    """The run's outcome and every exchange and tool call of its loop not yet recorded as it ended (_record_exchange),
    exactly as the LoopOutcome carries them, in one transaction (HARNESS.md 12.1): the run's own fields from the loop's
    final RawExchange (its first request is already the run's request; its final response is the last exchange's). When
    they cannot all be recorded, the run is recorded as unknown - an exchange may have reached the vendor - unless the
    loop provably sent nothing. Its sent flag follows the rule the stale sweep and the installer's undo settle a run by
    (may_have_reached_vendor): a run whose reservation names no endpoint, a replay, called no vendor and is never sent,
    whatever its loop's final says (refutation round 4, sends-3: this fallback recorded a replayed run sent, with
    "what reached the vendor is not known")."""
    called = bool(run.endpoint)  # the reservation's: the endpoint its adapter calls, '' for a replay
    if outcome.stopped and outcome.exchanges:
        # F-STOP: a loop a member's Stop ended between exchanges - every exchange complete, nothing in flight - can be
        # continued from its last turn by a later run (_stopped_attempt); a lost provider lock is never one (stopped is
        # False there: _send_loop)
        run.scope = {**(run.scope or {}), 'stopped_after_turn': outcome.exchanges[-1].turn}
    try:
        with transaction.atomic():
            _finish_run(run, outcome.final)
            recorded = set(run.exchanges.values_list('turn', flat=True))
            _record_exchanges(run, [record for record in outcome.exchanges if record.turn not in recorded])
    except Exception as exc:  # noqa: BLE001 - logged; the run records why, never the internals
        log.exception('the loop outcome of participant run %s could not be recorded', run.pk)
        label = _loop_label(run.provider)
        unsent = outcome.final.outcome == 'not_sent' and not outcome.final.sent
        if unsent:
            error = f'Nothing was sent; its record could not be written ({type(exc).__name__}, logged).'
        else:
            error = (UNRECORDED_MESSAGE if called else UNRECORDED_REPLAY_MESSAGE).format(label=label)
        _finish_run(run, RawExchange(
            outcome='not_sent' if unsent else 'unknown', sent=called and not unsent, endpoint=outcome.final.endpoint,
            requested_model=outcome.final.requested_model, error=error))


def _record_exchange(run, record):
    """One exchange of ``run``'s tool loop and its tool calls, recorded as the exchange ends - its answer read and its
    tool calls answered, before the next exchange is sent - in a transaction of its own, committed at once (refutation
    round 2, sends-r2-4). One that cannot be recorded is logged and recorded with the run's outcome (_finish_loop). A
    write that meets an ended database session leaves Django on another session, which does not hold the provider lock:
    the loop's next check finds that, and nothing more is sent (_send_loop; refutation round 3, sends-1)."""
    try:
        with transaction.atomic():
            _record_exchanges(run, (record,))
    except Exception:  # noqa: BLE001 - logged; the loop goes on, and _finish_loop records what is still missing
        log.exception('exchange %s of participant run %s could not be recorded as it ended', record.turn, run.pk)


def _record_exchanges(run, exchanges):
    """One ProviderExchange per loop exchange (turn 1..n) and one ToolCall per tool call it answered. A tool call whose
    arguments were missing or null (None: the loop answered it with CPT Studio's own sentence) is recorded with JSON
    null arguments - never SQL NULL, which the column refuses, so the record failed and the whole run, its answer
    included, was recorded unknown with nothing of it kept (refutation round 2, sends-r2-1)."""
    for record in exchanges:
        data = record.response_bytes or b''
        exchange = models.ProviderExchange.objects.create(
            run=run, turn=record.turn, request_body=record.request_body, request_sha256=record.request_sha256,
            state=record.outcome, http_status=record.http_status, response_bytes=data,
            response_sha256=record.response_sha256 or (hashlib.sha256(data).hexdigest() if data else ''),
            latency_ms=record.latency_ms, usage=dict(record.usage or {}),
            provider_request_id=(record.provider_request_id or '')[:120], response_id=(record.response_id or '')[:140],
            error=record.error or '', started_at=record.started_at, finished_at=record.finished_at)
        models.ToolCall.objects.bulk_create([models.ToolCall(
            exchange=exchange, call_id=call.call_id, tool=call.tool,
            arguments=Value(None, JSONField()) if call.arguments is None else call.arguments, result=call.result,
            result_sha256=call.result_sha256, refs=list(call.refs), executed_at=call.executed_at or timezone.now())
            for call in record.tool_calls])


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


# --- the harness participants' stages (HARNESS.md 2-3) ----------------------------------------------------------------

PARTICIPANT_BLOCKED_MESSAGE = ('Nothing was sent: a previous request has an unknown outcome; reconcile it before '
                               'sending again.')
PARTICIPANT_ORIGINAL_MESSAGE = ('Nothing was sent: the original file could not be read back unchanged from the store, '
                                'so the request that names it was not made.')
PARTICIPANT_UPGRADE_MESSAGE = ('Nothing was sent: after an upgrade this document was read again under the current '
                               'rules, and no {label} answer is recorded for the request it makes. Resume to send it.')
PARTICIPANT_NOT_RUN = 'No request was made for this revision.'
PARTICIPANT_HELD_MESSAGE = ('Nothing was sent: the service date entered as encounter metadata conflicts with the '
                            'document, and nothing is sent while that question is open. Settling it gives {label} its '
                            'turn.')
PARTICIPANT_NOT_CONFIGURED = '{label} is not configured on this installation.'
PARTICIPANT_RAISED_MESSAGE = ('The {label} request may have been sent: its adapter stopped with an unexpected error '
                              '({error}, logged) before it recorded an outcome. The outcome is unknown; reconcile it '
                              'before any new attempt.')
PARTICIPANT_UNREADABLE_MESSAGE = ('The stored answer could not be read: the reader stopped with an unexpected error '
                                  '({error}, logged), so nothing from it was used.')
# scope['held'] of a participant's run that the unknown-outcome block stopped: nothing was sent, on purpose
UNKNOWN_OUTCOME_HELD = 'unknown_outcome'
PDF_MEDIA_TYPE, DOCX_MEDIA_TYPE = ALLOWED_SUFFIXES['.pdf'], ALLOWED_SUFFIXES['.docx']


def _participant_document(revision):
    """(kind, original, source file) of what a participant is given (HARNESS.md 3): 'pdf' - with the original, named by
    sha256 and size in the request, its bytes read back only at send time - only for an upload whose media type is PDF;
    'addendum' for an addendum revision, whose text no original matches; 'docx', 'txt' or 'paste' otherwise."""
    if revision.kind == models.SourceRevision.ADDENDUM:
        return 'addendum', None, None
    if revision.kind == models.SourceRevision.PASTE:
        return 'paste', None, None
    source = revision.source_file
    if source is not None and source.media_type == PDF_MEDIA_TYPE:
        return 'pdf', {'sha256': source.sha256, 'bytes': source.size}, source
    return ('docx' if source is not None and source.media_type == DOCX_MEDIA_TYPE else 'txt'), None, None


def _participant_pages(revision):
    """The revision's pages as a participant's framing needs them (prompt.framed_document: the spans tile the whole
    text): each page runs on to the next page's start - the separator extraction puts between two pages is read with the
    page before it - and the last page to the end of the text, so the addendum an addendum revision appends after its
    parent's pages is read with the last page. Each [Page N] line still stands where that page begins; every quote is
    located in the text itself, so no offset moves."""
    spans = sorted((PageSpan(**p) for p in revision.pages), key=lambda span: span.start)
    tiled = []
    for index, span in enumerate(spans):
        end = spans[index + 1].start if index + 1 < len(spans) else len(revision.text)
        tiled.append(PageSpan(page=span.page, start=tiled[-1].end if tiled else 0, end=end))
    return tuple(tiled)


def _participant_identity(adapter):
    """What a participant's run records of what it calls (HARNESS.md 6): the adapter's constant endpoint and model."""
    return {'endpoint': adapter.endpoint[:200], 'requested_model': adapter.requested_model[:100]}


def _participant_not_sent(job, name, adapter, request, error, *, mode, held='', started=True,
                          purpose=models.ProviderRun.INDEPENDENT, scope=None):
    """A participant's run that sent nothing, with why: the participant is shown as not run, and the chain goes on
    (I10). It carries ``request`` when one was built. ``started``: it went through the stage's send doors, as a reused
    or not resent run does, so no reader takes it for a reservation the stale sweep settled unsent; one whose request
    could not be built carries none and records no start, as Corti's does. ``purpose`` and ``scope``: a peer review's
    (stage_peer), whose scope names the assessment it was made for."""
    now = timezone.now()
    return models.ProviderRun.objects.create(
        encounter=job.encounter, revision=job.revision, provider=name,
        adapter_version=adapter.adapter_version if adapter is not None else '',
        request_sha256=request.canonical_sha256 if request is not None else '',
        request_body=request.body if request is not None else {},
        contexts=list(request.contexts) if request is not None else [], state=models.ProviderRun.NOT_SENT,
        sent=False, error=error, authorization_ref=settings.AUTHORIZATION_REF, requested_by=job.requested_by,
        service_date=None, purpose=purpose, scope={'mode': mode, **(scope or {}), **({'held': held} if held else {})},
        started_at=now if started else None, finished_at=now,
        **(_participant_identity(adapter) if adapter is not None else {}))


def _participant_done(job, run, outcome=None):
    """The participant stage's result once ``run`` records its outcome; the chain goes on (_queue_after_participant)."""
    _queue_after_participant(job)
    return {'participant': job.kind, 'state': outcome or run.state, 'run': str(run.pk)}


def _retained_answer(encounter, participant, request, purpose):
    """The workspace's retained answer to the identical participant request (provider, adapter version, request sha256,
    purpose) recorded in the same mode - the original SUCCEEDED run, not a reuse of one, whose tool loop recorded its
    exchanges; None when there is none. A run with no exchange is no loop's answer (refutation round 1, sends-2): before
    part B, this adapter version sent its body through the single-exchange send(), whose stored answer can still ask for
    tool calls, so reused it would stand in for the loop the identical request is owed."""
    from django.db.models import Exists, OuterRef

    return models.ProviderRun.objects.filter(
        Exists(models.ProviderExchange.objects.filter(run=OuterRef('pk'))),
        encounter__workspace=encounter.workspace, provider=participant.name,
        adapter_version=participant.adapter_version, request_sha256=request.canonical_sha256,
        state=models.ProviderRun.SUCCEEDED, reused_from__isnull=True, purpose=purpose,
        scope__mode=participant.mode).order_by('created_at').first()


NOT_ATTEMPTED_AGAIN_MESSAGE = ('Nothing was sent: this identical request was attempted before for this document and '
                               'recorded not sent, and it is not attempted again behind a reconciliation or a context '
                               'change; an addendum or a new upload makes a new request.')
NOT_ATTEMPTED_AGAIN_ERROR = ' Its reason then: {error}'


def _unsent_attempt(encounter, revision, participant, request, purpose):
    """This revision's attempt of the identical participant request (provider, adapter version, request sha256, purpose,
    mode) that stands as recorded not sent, or None (refutation round 1, sends-1). It is the newest finished run of that
    request (_newest_finished) when that run went through the send doors - its start recorded: a reservation the stale
    sweep settled never reached the send and still owes its attempt - sent nothing, and carries no hold: a run the
    unknown-outcome block stopped owes its attempt, and a member date conflict's hold is never one. A request sent and
    FAILED is the failed-request door's (_failed_before), never this one's.

    Such an attempt stands as Corti's not-sent attempt does behind a metadata save (ARCHITECTURE 5.4): a chain re-run by
    another run's reconciliation or by a context change never attempts that request again; an addendum or a new upload
    makes a new one."""
    run = _newest_finished(revision.provider_runs.filter(
        provider=participant.name, purpose=purpose, adapter_version=participant.adapter_version,
        request_sha256=request.canonical_sha256, scope__mode=participant.mode))
    if (run is None or run.state != models.ProviderRun.NOT_SENT or run.sent or run.started_at is None
            or 'held' in (run.scope or {}) or _failed_before(encounter, participant, request) is not None):
        return None
    return run


def _reused_participant_run(job, prior, purpose, scope=None):
    """The run a participant stage records where it reuses ``prior``: the whole run, nothing sent and no new usage, and
    no exchange of its own (its loop is prior's: loop_run). ``scope``: what it adds to prior's mode (a peer review names
    the assessment it was made for)."""
    now = timezone.now()
    run = models.ProviderRun.objects.create(
        encounter=job.encounter, revision=job.revision, provider=prior.provider, adapter_version=prior.adapter_version,
        request_sha256=prior.request_sha256, request_body=prior.request_body, contexts=prior.contexts,
        state=models.ProviderRun.SUCCEEDED, sent=False, http_status=prior.http_status,
        provider_request_id=prior.provider_request_id, response_sha256=prior.response_sha256,
        response_bytes=bytes(prior.response_bytes), usage={}, usage_basis='reused_retained_result_no_new_usage',
        authorization_ref=settings.AUTHORIZATION_REF, requested_by=job.requested_by, reused_from=prior,
        service_date=None, purpose=purpose, scope={'mode': (prior.scope or {}).get('mode', ''), **(scope or {})},
        endpoint=prior.endpoint, requested_model=prior.requested_model, returned_model=prior.returned_model,
        response_id=prior.response_id, started_at=now, finished_at=now)
    audit.record(job.encounter.workspace, 'provider.reused', encounter=job.encounter, run=str(run.pk),
                 reused_from=str(prior.pk), provider=prior.provider, purpose=purpose)
    return run


def stage_participant(job):
    """One harness participant's own review of the current revision (HARNESS.md 2-3; job kinds 'astra' and 'fable', in
    that order after predict, each carrying the Corti run as Job.provider_run).

    The participant is given the revision alone - its text with [Page N] lines, and a PDF upload's original - so its
    request depends on no context: a context change reuses its answer. Its send doors are predict's, in predict's order:
    a request that cannot be built is recorded not sent; a retained answer to the identical request is reused - the
    whole run, recording no new exchange; an unknown outcome blocks every send; a request that failed is never sent
    again; the live gate; then one tool loop under _send's discipline, with CPT Studio's CMS tool executor (HARNESS.md
    12.1). Every outcome is a run of its own, and the chain goes on to the next configured participant or the assess: a
    participant that is unavailable, refused by the live gate or failing blocks only itself (I10)."""
    name, revision, encounter, context = job.kind, job.revision, job.encounter, job.context
    encounter.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists; nothing was sent'}
    if context is None or context.revision_id != revision.pk or encounter.current_context_id != context.pk:
        return {'skipped': 'the context is not the current one for this revision; nothing was sent'}
    _refuse_legacy_context(job)  # FINAL 6.6 and 9: nothing is sent on a context that is not a gemini context
    try:
        participant = participants.get_participant(name)
    except ProviderUnavailable as exc:
        return _participant_done(job, _participant_not_sent(job, name, None, None, str(exc), started=False,
                                                            mode=participants.participant_mode(name)))
    if participant is None:  # disabled since the chain was queued: it records nothing, as one never configured
        _queue_after_participant(job)
        return {'participant': name, 'state': 'disabled'}
    kind, original, source = _participant_document(revision)
    try:
        request = participant.build_request(revision.text, _participant_pages(revision), kind, original)
    except ProviderUnavailable as exc:
        return _participant_done(job, _participant_not_sent(job, name, participant, None, str(exc), started=False,
                                                            mode=participant.mode))

    # Reuse a retained answer to the identical request instead of paying twice - one recorded in the same mode only, so
    # a replayed answer never stands in for a live one (a replayed run never presents as live output).
    prior = _retained_answer(encounter, participant, request, models.ProviderRun.INDEPENDENT)
    if prior is not None:
        return _participant_done(job, _reused_participant_run(job, prior, models.ProviderRun.INDEPENDENT), 'reused')
    # An attempt of this identical request that was recorded not sent stands: nothing is sent and no run is added, so
    # the assess reads that run as before (refutation round 1, sends-1). Asked before the unknown-outcome block, whose
    # held run would owe that request an attempt.
    unsent = _unsent_attempt(encounter, revision, participant, request, models.ProviderRun.INDEPENDENT)
    if unsent is not None:
        return _participant_done(job, unsent, 'not_attempted_again')

    if _unreconciled_unknown(encounter):
        held = _participant_not_sent(job, name, participant, request, PARTICIPANT_BLOCKED_MESSAGE,
                                     mode=participant.mode, held=UNKNOWN_OUTCOME_HELD)
        return _participant_done(job, held, 'blocked')
    # F-STOP: a member's Stop paused this request's loop between exchanges; its Resume continues it from the next
    # exchange (a run of its own, linked to the stopped one), never sending an exchange again
    stopped = _stopped_attempt(encounter, participant, request, models.ProviderRun.INDEPENDENT)
    failed = None if stopped is not None else _failed_before(encounter, participant, request)
    if failed is not None:
        run = _not_resent_run(job, encounter, revision, participant, request, None, failed,
                              purpose=models.ProviderRun.INDEPENDENT, scope={'mode': participant.mode},
                              **_participant_identity(participant))
        return _participant_done(job, run, 'not_resent')
    try:
        _live_gate(job, participant, revision, encounter)
    except StageFailure as exc:
        return _participant_done(job, _participant_not_sent(job, name, participant, request, f'Nothing was sent: {exc}',
                                                            mode=participant.mode))
    if job.idempotency_key.endswith(UPGRADE_MARK):
        # a chain the upgrade's predict started stops where it would send, as that predict does, until a member's
        # Resume (refutation r1, migrate-5): an upgrade never sends a request nobody asked for
        raise StageCancelled(PARTICIPANT_UPGRADE_MESSAGE.format(label=participants.LABELS.get(name, name)))
    original_bytes = None
    if source is not None:
        try:
            original_bytes = read_original(source)  # re-verified against the recorded sha256
        except (OriginalCorrupted, OSError):
            return _participant_done(job, _participant_not_sent(job, name, participant, request,
                                                                PARTICIPANT_ORIGINAL_MESSAGE, mode=participant.mode))
    run = _send(job, participant, request, service_date=None, purpose=models.ProviderRun.INDEPENDENT,
                scope={'mode': participant.mode}, original_bytes=original_bytes,
                execute_tool=reference_tools.executor(encounter.workspace), continues=stopped)
    return _participant_done(job, run)


# --- the interpret stage (design/FINAL.md 6.1-6.3, 6.9 and 11, as design/ADJUDICATION.md P-2 and P-6 amend them) -------
#
# extract -> interpret -> analyze. One stage per revision and INTERPRETATION_VERSION, keyed
# 'interpret:<revision>:<version>' - a recorded retry adds ':retry:<run>', a reconciliation ':after-reconcile:<run>', the
# stale sweep ':settled:<run>' - whose every outcome is a ProviderRun(provider 'gemini', purpose 'interpretation',
# adapter_version ADAPTER_VERSION), and whose every answer read is an EventInventory row: 'read' queues
# 'analyze:<revision>:<inventory>', 'refused' ends the stage failed with the retry door (FINAL 11.3). Gemini is the only
# interpreter: nothing here calls the legacy reader, the stage runs under a new_path sentinel scope (run_job), its reading
# runs in a forked child counted against that scope, and the inventory insert is gated.
#
# Each run's meaning (interpretation.holds' effect: answered, failed, too_long, hold, unknown, none) is recorded on its
# scope ('effect') as the stage settles it; a run the stage itself kept from sending says why ('refused': 'size' for the
# size bound, 'unbuilt' for a text that cannot be framed, 'failed_before' for the failed-request door, 'settled' for the
# stale sweep's settled path, which never sends, 'live_gate' and 'sentinel' where no request could be made; 'held' for a
# pause, FINAL 11.2). Every outcome is a run (FINAL 6.3), and the progress panel and the retry door read them. A stage
# keyed ':settled:<run>' or ':after-reconcile:<run>' settles that run itself when it holds the answer to the request
# (_settled_answer), recording no run of its own: that run is its outcome (keyed_interpretation_run).

INTERPRET_TOO_LONG_MESSAGE = 'This document is too long to read in one piece; nothing was sent.'
INTERPRET_UNBUILT_MESSAGE = 'The document could not be prepared for reading; nothing was sent.'
INTERPRET_NOT_SENT_MESSAGE = 'The interpretation request was not sent; nothing reached the interpreter.'
INTERPRET_FAILED_MESSAGE = 'The interpretation did not succeed and was not used.'
INTERPRET_CUT_OFF_MESSAGE = ('The interpretation was cut off at its output limit: the document is too long to be read '
                             'in one piece, and the identical request is not sent again.')
INTERPRET_NOT_RESENT_MESSAGE = ('Nothing was sent: this document\'s reading was sent before and did not succeed, and '
                                'the identical request is sent again only for a recorded retry.')
INTERPRET_BLOCKED = 'a previous request has an unknown outcome; reconcile it before sending again'
INTERPRET_SETTLED_MESSAGE = ('Nothing was sent: the stage that sent this document\'s request stopped before its answer '
                             'was used, and no stored answer answers the request made now. Resume to have the document '
                             'read.')
STORED_ANSWER_CHANGED = 'The stored answer no longer matches its recorded hash; nothing from it was used.'
READ_OVERRUN_MESSAGE = 'The stored answer could not be read within the {reason} limit; nothing from it was used.'
READ_FAILED_MESSAGE = ('The stored answer could not be read: the reader stopped with an unexpected error (logged), so '
                       'nothing from it was used.')
RETRY_RELEASE_NOTE = 'released for one retry'  # FINAL 11.3: the note a retry writes on the run it releases
# scope['refused'] of a run the stage kept unsent: the size bound, a text that cannot be framed, the failed-before door,
# the live gate, a sentinel that cannot vouch for the write the answer would need (NOT_RUN: no request could be made)
SIZE, UNBUILT, FAILED_BEFORE, LIVE_GATE, SENTINEL = 'size', 'unbuilt', 'failed_before', 'live_gate', 'sentinel'
SETTLED = 'settled'  # ... and the stale sweep's settled path, which never sends (FINAL 6.9; D11: no automatic retry)
NOT_RUN = (LIVE_GATE, SENTINEL)
SETTLED_FROM_EXCHANGE = 'settled_from_exchange'  # scope key of a run P-6 settled from its recorded exchange


def _interpret_key(revision, suffix=''):
    """The interpret stage's key (FINAL 6.1): 'interpret:<revision>:<INTERPRETATION_VERSION>', plus ':<suffix>' -
    'retry:<run>', 'after-reconcile:<run>' or 'settled:<run>' - always on the base, so suffixes never chain (a Resume
    adds its own, which resume keeps to one). At most 115 characters before a Resume's 44, inside the 200 the column
    holds."""
    base = f'{INTERPRET}:{revision.pk}:{interpretation.INTERPRETATION_VERSION}'
    return f'{base}:{suffix}' if suffix else base


def _keyed_run(job, mark):
    """The run of this encounter that ``job``'s key names after ':<mark>:' ('after-reconcile', 'retry', 'settled'), or
    None."""
    _, found, tail = job.idempotency_key.split(':resume:', 1)[0].partition(f':{mark}:')
    if not found:
        return None
    try:
        pk = uuid.UUID(tail)
    except ValueError:
        return None
    return models.ProviderRun.objects.filter(pk=pk, encounter_id=job.encounter_id).first()


def keyed_interpretation_run(job):
    """The interpretation run of ``job``'s revision that its key names - ':settled:<run>' (the stale sweep, FINAL 6.9) or
    ':after-reconcile:<run>' (a reconciliation) - or None. Such a stage settles that run itself when it holds the answer
    to the request (_settled_answer) and records no run of its own, so that run's outcome is the stage's own (the reading
    review._failed_stage_state makes of a failed one)."""
    for mark in ('settled', 'after-reconcile'):
        run = _keyed_run(job, mark)
        if run is not None:
            return run if run.purpose == INTERPRETATION and run.revision_id == job.revision_id else None
    return None


def _settled_path(job) -> bool:
    """Whether ``job`` is the stale sweep's settled path itself ('interpret:...:settled:<run>'), never a member's Resume
    of it: the one interpret stage that sends nothing, whatever it finds (FINAL 6.9; D11: no automatic retry)."""
    base, resumed, _ = job.idempotency_key.partition(':resume:')
    return not resumed and ':settled:' in base


def _size_bound(revision):
    """'chars' or 'pages' when ``revision`` is over the interpreter's size bound (D4, FINAL C9: INTERPRET_MAX_CHARS,
    INTERPRET_MAX_PAGES), else ''. It replaces the legacy mention gate, which read legacy vocabularies."""
    if len(revision.text or '') > settings.INTERPRET_MAX_CHARS:
        return 'chars'
    if len(revision.pages or ()) > settings.INTERPRET_MAX_PAGES:
        return 'pages'
    return ''


def _interpretation_not_sent(job, error, *, mode, interpreter=None, request=None, started=False, **scope):
    """An interpretation run that sent nothing, with why (FINAL 6.3 steps 2-4, the failed-request door): it carries
    ``request`` when one was built; ``started`` when it went through the send doors (as a reuse or a not-resent run does),
    so no reader takes it for a reservation the stale sweep settled unsent. ``scope``: what it adds to its mode - 'held'
    for a pause (FINAL 11.2), 'refused' and 'effect' for a run the stage kept from sending."""
    now = timezone.now()
    identity = (_participant_identity(interpreter) if interpreter is not None
                else {'endpoint': '', 'requested_model': interpretation.MODEL})
    return models.ProviderRun.objects.create(
        encounter=job.encounter, revision=job.revision, provider=interpretation.PROVIDER,
        adapter_version=interpretation.ADAPTER_VERSION,
        request_sha256=request.canonical_sha256 if request is not None else '',
        request_body=request.body if request is not None else {},
        contexts=list(request.contexts) if request is not None else [], state=models.ProviderRun.NOT_SENT, sent=False,
        error=error, authorization_ref=settings.AUTHORIZATION_REF, requested_by=job.requested_by, service_date=None,
        purpose=INTERPRETATION, scope={'mode': mode, **{key: value for key, value in scope.items() if value}},
        started_at=now if started else None, finished_at=now, **identity)


def _mark_effect(run, effect):
    """Record on ``run``'s scope what its outcome means (interpretation.holds' effects), as the stage settled it."""
    scope = {**(run.scope or {}), 'effect': effect}
    models.ProviderRun.objects.filter(pk=run.pk).update(scope=scope)
    run.scope = scope


def _answer_runs(run):
    """The runs carrying ``run``'s stored answer: its origin (the run that was sent) and every reuse of it. One answer's
    reading is a pure function of its bytes and the interpretation version, so a refusal or a retry release on any of
    them is the answer's."""
    origin = run.reused_from_id or run.pk
    return Q(pk=origin) | Q(reused_from_id=origin)


def _answer_refusal(run):
    """The EventInventory, at the current versions, in which a reading of ``run``'s answer was refused (on the run or on
    any run carrying the same answer), or None."""
    origin = run.reused_from_id or run.pk
    return (models.EventInventory.objects.filter(
        Q(provider_run_id=origin) | Q(provider_run__reused_from_id=origin), state=models.EventInventory.REFUSED,
        interpretation_version=interpretation.INTERPRETATION_VERSION,
        inventory_version=interpretation.INVENTORY_VERSION).order_by('created_at', 'pk').first())


def _recorded_effect(run):
    """The effect a stage recorded on ``run`` (scope 'effect') while it still describes the run, else None: 'unknown' or
    'none' recorded on a run whose outcome is now a definite one (SUCCEEDED or FAILED) - an unknown outcome P-6 settled
    from its recorded exchange - describes the run as it was, never its answer, which is classified from the run as
    stored (refutation of S09, finding 1: a stale 'unknown' kept the settled answer from every door, and it was paid
    for again)."""
    stored = (run.scope or {}).get('effect')
    if stored not in interpretation_holds.EFFECTS:
        return None
    if (stored in (interpretation_holds.UNKNOWN, interpretation_holds.NONE)
            and run.state in (models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED)):
        return None
    return stored


def interpretation_effect(run) -> str:
    """What interpretation run ``run``'s outcome means (interpretation.holds' table, FINAL 11.1): as the stage recorded it
    (scope 'effect', while it still describes the run: _recorded_effect), else classified now from the run as stored -
    for a stored answer, with the refusal of any reading of that answer (_answer_refusal). 'none' for a run that sent
    nothing or has no outcome yet."""
    stored = _recorded_effect(run)
    if stored is not None:
        return stored
    if run.state in (models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED):
        return interpretation_holds.classify(run.state, run.http_status, bytes(run.response_bytes or b''),
                                             refused=_answer_refusal(run)).effect
    return interpretation_holds.classify(run.state).effect


def released_for_retry(run) -> bool:
    """Whether ``run``'s answer was released for one retry (FINAL 11.3: a member's or an operator's recorded act writes
    RETRY_RELEASE_NOTE on the released run's reconciled_by, reconciled_at and reconciliation_note): on the run or on any
    run carrying the same answer."""
    return models.ProviderRun.objects.filter(
        _answer_runs(run), reconciled_at__isnull=False, reconciliation_note=RETRY_RELEASE_NOTE,
        state__in=(models.ProviderRun.FAILED, models.ProviderRun.SUCCEEDED)).exists()


def _read_inventory(revision, mode=None):
    """The newest EventInventory read for ``revision`` at the current versions (in ``mode`` when given: a replayed answer
    never stands in for a live one), or None."""
    rows = models.EventInventory.objects.filter(
        revision=revision, state=models.EventInventory.READ,
        interpretation_version=interpretation.INTERPRETATION_VERSION,
        inventory_version=interpretation.INVENTORY_VERSION)
    if mode is not None:
        rows = rows.filter(provider_run__scope__mode=mode)
    return rows.select_related('provider_run').order_by('-created_at', '-pk').first()


def _new_path_owed(revision, context=None) -> bool:
    """Whether a member's explicit act on ``revision`` (a Resume, a reconciliation) must have it interpreted first (FINAL
    6.9 and 9; 16.2): it has no EventInventory read at the current versions, or ``context`` - the context the act would
    use - is not a gemini context. Replaced by the test-only legacy chain (tests/legacy_chain.py)."""
    if context is not None and not interpretation.is_new_context(context):
        return True
    return _read_inventory(revision) is None


def _retained_interpretation(encounter, interpreter, request):
    """FINAL 6.3's second door, as ADJUDICATION P-2 amends it: the workspace's oldest stored SUCCEEDED answer to the
    identical request - provider, adapter version, request sha256 and mode, the original run (never a reuse of one),
    which recorded its exchange as _retained_answer requires - whose answer is a usable one (interpretation_effect:
    answered, so never one whose reading at the current versions was refused, nor a hold, nor a cut-off answer) and was
    not released for retry. None when there is none: nothing is reused."""
    from django.db.models import Exists, OuterRef

    priors = models.ProviderRun.objects.filter(
        Exists(models.ProviderExchange.objects.filter(run=OuterRef('pk'))),
        encounter__workspace=encounter.workspace, provider=interpreter.name,
        adapter_version=interpreter.adapter_version, request_sha256=request.canonical_sha256,
        state=models.ProviderRun.SUCCEEDED, reused_from__isnull=True, purpose=INTERPRETATION,
        scope__mode=interpreter.mode).order_by('created_at', 'pk')
    for prior in priors:
        if interpretation_effect(prior) == interpretation_holds.ANSWERED and not released_for_retry(prior):
            return prior
    return None


def _interpretation_failed_before(encounter, interpreter, request):
    """FINAL 6.3's failed-before door (as _failed_before, for the interpreter): this encounter's newest attempt of the
    identical request that was SENT and did not succeed - failed, a reading refused, or cut off (effects failed and
    too_long); never a hold, which an operator's release ends, and never an unknown outcome, which is reconciled - or
    None. A run released for one retry (FINAL 11.3) does not block: its retry is the one attempt it was released for."""
    attempts = models.ProviderRun.objects.filter(
        encounter=encounter, provider=interpreter.name, adapter_version=interpreter.adapter_version,
        request_sha256=request.canonical_sha256, purpose=INTERPRETATION, sent=True,
        state__in=(models.ProviderRun.FAILED, models.ProviderRun.SUCCEEDED)).order_by('-created_at', '-pk')
    for run in attempts:
        if interpretation_effect(run) not in (interpretation_holds.FAILED, interpretation_holds.TOO_LONG):
            continue
        return None if released_for_retry(run) else run
    return None


def _settle_from_exchange(run) -> bool:
    """ADJUDICATION P-6: an interpretation run left 'sending' by a dead worker or by a stage that no longer runs, or
    recorded unknown and reconciled, whose one exchange (turn 1) was recorded succeeded with HTTP 200 and response bytes
    whose sha256 checks, is settled SUCCEEDED from that exchange - the answer it holds - and its settled path reads it,
    or records its hold, or fails its refused reading (_settled_answer, _settle_interpretation): nothing is sent. The
    effect a stage recorded on it ('unknown') is dropped, since it described the run as it was and never its answer
    (refutation of S09, finding 1). Every other run is left as it is (False)."""
    if (run.provider != interpretation.PROVIDER or run.purpose != INTERPRETATION
            or run.state not in (models.ProviderRun.SENDING, models.ProviderRun.UNKNOWN)):
        return False
    exchanges = list(run.exchanges.order_by('turn')[:2])
    if len(exchanges) != 1:
        return False
    exchange = exchanges[0]
    data = bytes(exchange.response_bytes or b'')
    if (exchange.turn != 1 or exchange.state != models.ProviderRun.SUCCEEDED or exchange.http_status != 200 or not data
            or hashlib.sha256(data).hexdigest() != exchange.response_sha256
            or exchange.request_sha256 != run.request_sha256):
        return False
    _, model, response_id = interpretation_adapter.describe(data)
    usage = dict(exchange.usage or {})
    scope = {key: value for key, value in (run.scope or {}).items() if key != 'effect'}
    settled = models.ProviderRun.objects.filter(pk=run.pk, state=run.state).update(
        state=models.ProviderRun.SUCCEEDED, sent=run.sent or bool(run.endpoint), http_status=200, response_bytes=data,
        response_sha256=exchange.response_sha256, latency_ms=exchange.latency_ms, usage=usage,
        usage_basis=participant_http.USAGE_BASIS if usage else '', error='',
        provider_request_id=exchange.provider_request_id, response_id=exchange.response_id or response_id,
        returned_model=model, finished_at=exchange.finished_at or timezone.now(),
        scope={**scope, SETTLED_FROM_EXCHANGE: True})
    if settled:
        run.refresh_from_db()
    return bool(settled)


def _settled_answer(job, interpreter, request):
    """The run a settled or after-reconcile stage settles itself, before any door (FINAL 6.9; ADJUDICATION P-6;
    refutation of S09, findings 1 and 2): its keyed run (keyed_interpretation_run) when that run SUCCEEDED - the stale
    sweep's, or one P-6 settled from its recorded exchange - holds the answer to the identical request (provider,
    adapter version, request sha256 and mode, as the stored-answer door matches them) and no stage has settled its
    outcome yet (no effect recorded that still describes it). _settle_interpretation then reads it, records its hold
    (P-5: an answer naming another model is never read and never paid for again) or fails its refused or cut-off reading,
    exactly as the stage that sent it would have: nothing is sent (D11). None otherwise - a run already settled, or one
    that answers another request - and the doors decide."""
    run = keyed_interpretation_run(job)
    if (run is None or run.state != models.ProviderRun.SUCCEEDED or run.provider != interpreter.name
            or run.adapter_version != interpreter.adapter_version or run.request_sha256 != request.canonical_sha256
            or (run.scope or {}).get('mode') != interpreter.mode or _recorded_effect(run) is not None):
        return None
    return run


def _queue_analyze(job, inventory):
    """FINAL 6.1: 'analyze:<revision>:<inventory>' for an inventory read (one analyze per inventory)."""
    return enqueue(Job.ANALYZE, encounter=job.encounter, revision=job.revision,
                   key=f'{Job.ANALYZE}:{job.revision_id}:{inventory.pk}', requested_by=job.requested_by)


def _interpretation_child(request, response_bytes, text):
    """The reading of one stored answer (FINAL 6.3, Read), DB-free in a forked child under a wall clock (bounded): the
    envelope (adapter.answer_text, FINAL 5.4), the strict read (interpretation.read) and normalization
    (interpretation.normalize). ('read', the inventory's content for store.row) or ('refused', stage, reason)."""
    from .interpretation import normalize
    from .interpretation import read as interpretation_read

    answer = interpretation_adapter.answer_text(request, response_bytes)
    if isinstance(answer, interpretation_read.Refusal):
        return 'refused', answer.stage, answer.reason
    parsed = interpretation_read.read(answer)
    if isinstance(parsed, interpretation_read.Refusal):
        return 'refused', parsed.stage, parsed.reason
    return 'read', normalize.normalize(parsed, text).content()


def _read_answer(job, run):
    """The EventInventory of succeeded run ``run``'s stored answer at the current versions: the one recorded for it, or
    one recorded now (FINAL 6.3, Read) - the stored bytes' sha256 re-checked, the reading run in a forked child counted
    against the stage's scope (sentinel.run_counted), the row written through interpretation.store's one write path
    (store.row with the revision text, store.refused_row for a refusal) and gated. A read that cannot be completed fails
    the stage and writes no row: stored bytes that no longer match their sha256 are a definite failure of the answer
    (its effect 'failed': the retry door); a child that overran or failed, a row the store refused or a write gate that
    refused is this server's failure, never the answer's, so the answer stays reusable - read again, with nothing sent,
    by the stored-answer door of a later stage (a new upload of the same text included)."""
    existing = models.EventInventory.objects.filter(
        provider_run=run, interpretation_version=interpretation.INTERPRETATION_VERSION,
        inventory_version=interpretation.INVENTORY_VERSION).first()
    if existing is not None:
        return existing
    revision = job.revision
    data = bytes(run.response_bytes or b'')
    if hashlib.sha256(data).hexdigest() != run.response_sha256:
        _mark_effect(run, interpretation_holds.FAILED)
        raise StageFailure(STORED_ANSWER_CHANGED)
    request = ProviderRequest(provider=run.provider, adapter_version=run.adapter_version, body=run.request_body,
                              canonical_sha256=run.request_sha256, contexts=tuple(run.contexts or ()))
    try:
        result = sentinel.run_counted(_interpretation_child, request, data, revision.text,
                                      seconds=settings.JOB_DEADLINE_SECONDS['analyze'],
                                      memory_bytes=settings.BOUNDED_MEMORY_BYTES)
    except bounded.Overrun as exc:
        raise StageFailure(READ_OVERRUN_MESSAGE.format(reason=exc.reason)) from None
    except RuntimeError:
        raise StageFailure(READ_FAILED_MESSAGE) from None
    bindings = {'encounter_id': job.encounter_id, 'revision_id': revision.pk, 'provider_run_id': run.pk,
                'text_sha256': revision.text_sha256, 'request_sha256': run.request_sha256,
                'response_sha256': run.response_sha256}
    try:
        if result[0] == 'read':
            fields = inventory_store.row(revision_text=revision.text, **bindings, **result[1])
        else:
            from .interpretation.read import Refusal

            fields = inventory_store.refused_row(Refusal(stage=result[1], reason=result[2]), **bindings)
    except (inventory_store.StoreError, TypeError, ValueError):
        log.exception('the reading of interpretation run %s could not be stored', run.pk)
        raise StageFailure(READ_FAILED_MESSAGE) from None
    _gate('interpret', job.encounter)
    return models.EventInventory.objects.create(**{name: fields[name] for name in inventory_store.FIELDS})


def _settle_interpretation(job, run, *, reused=False):
    """What the stage does with ``run``'s outcome (FINAL 6.3 and 11.1; interpretation.holds' table), recording its effect
    on the run: an answer read - its inventory recorded 'read' - queues the analyze; an outcome still unknown is left to
    the reconcile flow, the encounter blocked on it; a hold (holds.settle records it, one per answer) ends the stage
    paused; anything else - a refused reading (recorded 'refused'), a cut-off answer, a definite failure, a request not
    sent - ends it failed, with the recorded retry door (FINAL 11.3) where it applies. Never a retry, never a fallback,
    never the legacy reader."""
    if run.state == models.ProviderRun.UNKNOWN:
        _mark_effect(run, interpretation_holds.UNKNOWN)
        return {'provider': models.ProviderRun.UNKNOWN, 'run': str(run.pk)}
    if run.state not in (models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED):
        _mark_effect(run, interpretation_holds.NONE)
        raise StageFailure(INTERPRET_NOT_SENT_MESSAGE)
    inventory = _read_answer(job, run) if run.state == models.ProviderRun.SUCCEEDED else None
    outcome, hold = interpretation_holds.settle(run, inventory=inventory)
    _mark_effect(run, outcome.effect)
    if outcome.effect == interpretation_holds.ANSWERED:
        _queue_analyze(job, inventory)
        return {'provider': 'reused' if reused else run.state, 'run': str(run.pk), 'inventory': str(inventory.pk)}
    if outcome.effect == interpretation_holds.HOLD and hold is not None:
        raise StageCancelled(interpretation_holds.PAUSED_MESSAGE)
    if outcome.effect == interpretation_holds.TOO_LONG:
        raise StageFailure(INTERPRET_CUT_OFF_MESSAGE)
    if outcome.effect == interpretation_holds.HOLD:  # an answer that is never read, whose hold was released (or unsent)
        raise StageFailure(INTERPRET_FAILED_MESSAGE)
    raise StageFailure(f'{INTERPRET_FAILED_MESSAGE} {outcome.why}'.strip())


def stage_interpret(job):
    """The revision's interpretation (FINAL 6.3): Gemini reads the documented clinical events once, and the answer read
    is the EventInventory every later stage reads.

    Before anything is built: the current revision only, with its text extracted; the size bound (over it, a not-sent
    run and a failed stage that says so plainly); the interpreter's mode and the installation-wide hold (disabled or
    held - or an interpreter that cannot be configured - a not-sent run with scope.held, and the stage ends CANCELLED:
    paused, resumable; FINAL 11.2); then the request, built purely from the text, its page framing and the
    instructions (one that cannot be framed: a not-sent run, failed). Before the doors, a reconciliation's stage settles
    the run it was released for from its recorded exchange when it can (ADJUDICATION P-6). The doors, in predict's
    order: an inventory already read for this revision and versions (no send: analyze); the run a settled or
    after-reconcile key names, settled itself when it holds the answer to the identical request and no stage settled it
    yet (_settled_answer: read, its hold recorded, or its refused or cut-off reading failed - nothing sent); a stored
    answer to the identical request (reused, nothing sent; P-2); the encounter-wide unknown-outcome block; the
    failed-before door (skipping a run released for one retry); the stale sweep's settled path stops here, recording
    that nothing was sent, resumable (FINAL 6.9: it never sends - only a member's Resume of it may); the live gate and
    the write gate asked before the send (each refusal a not-sent run: every outcome is a run); then one send (_send,
    purpose 'interpretation'), and its outcome settled (_settle_interpretation)."""
    revision, encounter = job.revision, job.encounter
    encounter.refresh_from_db()
    revision.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists; nothing was sent'}
    if revision.extraction_status not in READABLE:
        return {'skipped': 'the revision has no extracted text; nothing was sent'}
    bound = _size_bound(revision)
    if bound:
        _interpretation_not_sent(job, INTERPRET_TOO_LONG_MESSAGE, mode=interpretation_holds.mode(), refused=SIZE,
                                 bound=bound, effect=interpretation_holds.TOO_LONG)
        raise StageFailure(INTERPRET_TOO_LONG_MESSAGE)
    paused, interpreter, why = interpretation_holds.paused_reason(), None, interpretation_holds.PAUSED_MESSAGE
    if paused is None:
        try:
            interpreter = interpretation_adapter.get_interpreter()
        except ProviderUnavailable as exc:  # misconfigured: as disabled until an operator configures it
            paused, why = interpretation_holds.HELD_DISABLED, str(exc)
        else:
            paused = interpretation_holds.HELD_DISABLED if interpreter is None else None
    if paused is not None:
        _interpretation_not_sent(job, why, mode=interpretation_holds.mode(), held=paused)
        raise StageCancelled(interpretation_holds.PAUSED_MESSAGE)
    kind, _, _ = _participant_document(revision)
    try:
        request = interpreter.build_request(revision.text, _participant_pages(revision), kind)
    except ProviderUnavailable as exc:
        _interpretation_not_sent(job, str(exc), mode=interpreter.mode, interpreter=interpreter, refused=UNBUILT,
                                 effect=interpretation_holds.NONE)
        raise StageFailure(INTERPRET_UNBUILT_MESSAGE) from None

    reconciled = _keyed_run(job, 'after-reconcile')
    if reconciled is not None:
        _settle_from_exchange(reconciled)  # P-6: an answer the unknown run already holds is read, never paid for again
    existing = _read_inventory(revision, interpreter.mode)
    if existing is not None:
        _queue_analyze(job, existing)
        return {'provider': 'read_before', 'run': str(existing.provider_run_id), 'inventory': str(existing.pk)}
    settled = _settled_answer(job, interpreter, request)
    if settled is not None:
        # FINAL 6.9 and P-6: the answer the keyed run holds is settled as the stage that sent it would have settled it -
        # read, its hold recorded against it, or its refused or cut-off reading failed - and never paid for again
        return _settle_interpretation(job, settled, reused=settled.reused_from_id is not None)
    prior = _retained_interpretation(encounter, interpreter, request)
    if prior is not None:
        return _settle_interpretation(job, _reused_participant_run(job, prior, INTERPRETATION), reused=True)
    if _unreconciled_unknown(encounter):
        return {'blocked': INTERPRET_BLOCKED}
    failed = _interpretation_failed_before(encounter, interpreter, request)
    if failed is not None:
        _interpretation_not_sent(job, INTERPRET_NOT_RESENT_MESSAGE, mode=interpreter.mode, interpreter=interpreter,
                                 request=request, started=True, refused=FAILED_BEFORE, failed=str(failed.pk),
                                 effect=interpretation_holds.NONE)
        raise StageFailure(INTERPRET_NOT_RESENT_MESSAGE)
    if _settled_path(job):
        # FINAL 6.9: the stale sweep's settled path sends nothing (D11: no automatic retry). Its run was read or settled
        # above, or a door answered; what is left - a request the stored answer does not answer, an answer settled
        # before - is sent only on a member's explicit act: a Resume of this stage
        _interpretation_not_sent(job, INTERPRET_SETTLED_MESSAGE, mode=interpreter.mode, interpreter=interpreter,
                                 request=request, started=True, refused=SETTLED, effect=interpretation_holds.NONE)
        raise StageCancelled(INTERPRET_SETTLED_MESSAGE)
    for refused, check in ((LIVE_GATE, lambda: _live_gate(job, interpreter, revision, encounter)),
                           # the inventory write is gated after the read (_read_answer); asked here first too, so an
                           # answer this process could not record - its sentinel not installed and proven, or a denied
                           # execution already counted - is never paid for
                           (SENTINEL, lambda: _gate('interpret.send', encounter))):
        try:
            check()
        except StageFailure as exc:
            _interpretation_not_sent(job, f'Nothing was sent: {exc}', mode=interpreter.mode, interpreter=interpreter,
                                     request=request, started=True, refused=refused, effect=interpretation_holds.NONE)
            raise
    run = _send(job, interpreter, request, service_date=None, purpose=INTERPRETATION, scope={'mode': interpreter.mode})
    return _settle_interpretation(job, run)


# --- the peer-review stages (HARNESS.md 11.1, 12.1, 12.4) -------------------------------------------------------------

PEER_UPGRADE_MESSAGE = ('Nothing was sent: after an upgrade this document was read again under the current rules, and '
                        'no {label} peer review is recorded for the request it makes. Resume to send it.')
PEER_WAITS = "a participant's first assessment of this revision has not finished; the peer review waits for it"
PEER_NEWER = ('No peer review was asked for: a newer assessment of this revision exists, and its own chain owns the '
              'revision.')
PEER_MOVED = ("No peer review was asked for: the first assessment was not made from the participants' current first "
              'assessments, so a newer chain owns the revision.')
PEER_HELD = ('Nothing was sent: the service date entered as encounter metadata conflicts with the document, and '
             'nothing is sent while that question is open.')
PEER_FROZEN_CHANGED = ('Nothing was sent: a frozen first reading no longer reads back as the first assessment recorded '
                       'it, so the peer-review request, which must show exactly what was frozen, was not built.')
PEER_UNBUILT = 'Nothing was sent: CPT Studio could not build the peer-review request ({error}, logged).'


class _PeerUnbuilt(Exception):
    """A peer request cannot be built from the frozen inputs; the message says why (a not-sent peer run: I10)."""


def stage_peer(job):
    """One participant's peer review of the current revision (HARNESS.md 11.1, 12.1, 12.4; job kinds 'astra_peer' and
    'fable_peer', in that order after assess #1, each carrying the context and the Corti run as the chain does).

    It runs only when every configured participant's phase-1 run for the revision is terminal - until then it waits
    (Requeue) - and when the assessment it reads, the assess #1 its key names, is the revision's newest and was made
    from the participants' current phase-1 runs; otherwise it records not_run with why and queues nothing more: the
    newer chain owns the revision. A participant whose first reading assess #1 did not read takes no part (it was owed
    no stage; one met anyway is skipped and the chain goes on). Its request is built from the frozen inputs alone
    (_peer_material), and it passes every send door phase 1 passes, in the same order: a request that cannot be built is
    recorded not sent; a retained answer to the identical request is reused; an unknown outcome blocks every send; a
    request that failed is never sent again; the live gate; an upgrade's chain stops where it would send; then one tool
    loop under _send's discipline (Stop observed, single flight). Every outcome is a run of its own (purpose
    'peer_review', its scope naming assess #1), and the chain goes on to the next owed peer stage or assess #2: a
    participant that is unavailable, refused by the live gate or failing blocks only itself (I10)."""
    name, revision, encounter, context = PEER_OF[job.kind], job.revision, job.encounter, job.context
    encounter.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists; nothing was sent'}
    if context is None or context.revision_id != revision.pk or encounter.current_context_id != context.pk:
        return {'skipped': 'the context is not the current one for this revision; nothing was sent'}
    _refuse_legacy_context(job)  # FINAL 6.6 and 9: nothing is sent on a context that is not a gemini context
    first = _first_assessment(job)
    if first is None or first.context_id != context.pk:
        return {'peer': job.kind, 'state': 'not_run', 'reason': PEER_NEWER}
    configured = participants.configured()
    if not all(_phase1_settled(revision, other) for other in configured):
        raise Requeue(PEER_WAITS)
    records = _records(first)
    if any((records.get(other) or {}).get('run') != _pk(_participant_run(revision, other)) for other in configured):
        return {'peer': job.kind, 'state': 'not_run', 'reason': PEER_MOVED}
    if gi_context.is_member_conflict((context.facts or {}).get('service_date')):
        return {'peer': job.kind, 'state': 'not_run', 'reason': PEER_HELD}
    if (records.get(name) or {}).get('state') != 'read':
        return _peer_done(job, first, None, 'not_run')
    try:
        participant = participants.get_participant(name)
    except ProviderUnavailable as exc:
        return _peer_done(job, first, _peer_not_sent(job, first, name, None, None, str(exc), started=False,
                                                     mode=participants.participant_mode(name)))
    if participant is None:  # disabled since the chain was queued: it records nothing, as one never configured
        return _peer_done(job, first, None, 'disabled')
    try:
        own, peers, cpt_studio, frozen = _peer_material(revision, first, name, records)
    except _PeerUnbuilt as exc:
        return _peer_done(job, first, _peer_not_sent(job, first, name, participant, None, str(exc), started=False,
                                                     mode=participant.mode))
    kind, _, _ = _participant_document(revision)
    try:
        # FINAL 6.6 (D9): CPT Studio's reading after a new-path assess #1 is headed as what it is - its reading after
        # its first assessment; a legacy assess #1's keeps the legacy heading, so its request is byte-identical
        with participant_prompt.using_reading_heading(_peer_reading_heading(first)):
            request = participant.build_peer_request(revision.text, _participant_pages(revision), kind, own, peers,
                                                     cpt_studio, frozen)
    except ProviderUnavailable as exc:
        return _peer_done(job, first, _peer_not_sent(job, first, name, participant, None, str(exc), started=False,
                                                     mode=participant.mode))
    except Exception as exc:  # noqa: BLE001 - logged; one participant's unbuildable request blocks only itself (I10)
        log.exception('the peer-review request of %s for assessment %s could not be built', name, first.pk)
        return _peer_done(job, first, _peer_not_sent(job, first, name, participant, None,
                                                     PEER_UNBUILT.format(error=type(exc).__name__), started=False,
                                                     mode=participant.mode))
    scope = {'assessment': str(first.pk)}
    prior = _retained_answer(encounter, participant, request, models.ProviderRun.PEER_REVIEW)
    if prior is not None:
        return _peer_done(job, first, _reused_participant_run(job, prior, models.ProviderRun.PEER_REVIEW, scope),
                          'reused')
    unsent = _unsent_attempt(encounter, revision, participant, request, models.ProviderRun.PEER_REVIEW)
    if unsent is not None:
        # as phase 1 (sends-1), with a run of its own naming this assess #1, which is the run assess #2 reads; it
        # carries the request and says why nothing was sent
        error = NOT_ATTEMPTED_AGAIN_MESSAGE + (NOT_ATTEMPTED_AGAIN_ERROR.format(error=unsent.error) if unsent.error
                                               else '')
        return _peer_done(job, first, _peer_not_sent(job, first, name, participant, request, error,
                                                     mode=participant.mode), 'not_attempted_again')
    if _unreconciled_unknown(encounter):
        held = _peer_not_sent(job, first, name, participant, request, PARTICIPANT_BLOCKED_MESSAGE,
                              mode=participant.mode, held=UNKNOWN_OUTCOME_HELD)
        return _peer_done(job, first, held, 'blocked')
    stopped = _stopped_attempt(encounter, participant, request, models.ProviderRun.PEER_REVIEW)  # F-STOP, as above
    failed = None if stopped is not None else _failed_before(encounter, participant, request)
    if failed is not None:
        run = _not_resent_run(job, encounter, revision, participant, request, None, failed,
                              purpose=models.ProviderRun.PEER_REVIEW, scope={'mode': participant.mode, **scope},
                              **_participant_identity(participant))
        return _peer_done(job, first, run, 'not_resent')
    try:
        _live_gate(job, participant, revision, encounter)
    except StageFailure as exc:
        return _peer_done(job, first, _peer_not_sent(job, first, name, participant, request, f'Nothing was sent: {exc}',
                                                     mode=participant.mode))
    if job.idempotency_key.endswith(UPGRADE_MARK):
        raise StageCancelled(PEER_UPGRADE_MESSAGE.format(label=participants.LABELS.get(name, name)))
    run = _send(job, participant, request, service_date=None, purpose=models.ProviderRun.PEER_REVIEW,
                scope={'mode': participant.mode, **scope}, execute_tool=reference_tools.executor(encounter.workspace),
                continues=stopped)
    return _peer_done(job, first, run)


def _peer_reading_heading(first) -> str:
    """The heading of CPT Studio's reading in a peer request made for assess #1 ``first`` (FINAL 6.6, D9): the events
    engine's assessment is CPT Studio's reading after its first assessment; any other keeps the legacy heading
    (participants.prompt.READING_HEADINGS). The participants' adapter versions are not bumped: their stored answers are
    read as before (prompt.py's recorded exception)."""
    return (participant_prompt.EVENTS_READING_HEADING if interpretation.is_new_assessment(first)
            else participant_prompt.READING_HEADING)


def _pk(run):
    return str(run.pk) if run is not None else None


def _phase1_settled(revision, name):
    """Whether participant ``name``'s newest phase-1 run for ``revision`` is terminal - or there is none, as for a
    participant configured since assess #1 (HARNESS.md 12.1)."""
    run = (revision.provider_runs.filter(provider=name, purpose=models.ProviderRun.INDEPENDENT)
           .order_by('-created_at', '-pk').first())
    return run is None or run.state in models.ProviderRun.TERMINAL


def _peer_done(job, first, run, outcome=None):
    """The peer stage's result once ``run`` (None: it recorded none) states its outcome; the chain goes on to the next
    owed peer stage or assess #2 (_queue_peers), carrying an upgrade's mark as phase 1 does."""
    _queue_peers(job, first, after=PEER_OF[job.kind], upgrade=job.idempotency_key.endswith(UPGRADE_MARK))
    return {'peer': job.kind, 'state': outcome or run.state, 'run': _pk(run)}


def _peer_not_sent(job, first, name, adapter, request, error, **kwargs):
    """A peer-review run that sent nothing, with why (_participant_not_sent), its scope naming assess #1 ``first``."""
    return _participant_not_sent(job, name, adapter, request, error, purpose=models.ProviderRun.PEER_REVIEW,
                                 scope={'assessment': str(first.pk)}, **kwargs)


def _peer_material(revision, first, name, records):
    """(own, peers, cpt_studio, frozen) of participant ``name``'s peer request (HARNESS.md 12.4), from assess #1
    ``first`` and the runs it read: its own frozen reading, re-read from its phase-1 run with that run's reader and
    refs; Corti's selected codes with the exact passages of the document their evidence quotes (_corti_conclusions);
    the other model's frozen reading, when it has one, in the reading schema's shape with none of that model's own
    wording (peer.shown_reading: refutation round 2, IR2-3); CPT Studio's rule-based reading after assess #1, which
    names no person and no value a member entered (_cpt_studio_reading: IR2-1, IR2-2), with each held or excluded
    proposal's code only in a code's shape (_peer_codes: refutation round 3, peer-1); and assess #1's frozen list with
    that reading's sha256 added. A frozen reading that no longer reads back as assess #1 recorded it refuses the request
    (_PeerUnbuilt): the record shows exactly what was shown. Of assess #1's frozen list, only what this request shows
    is listed (refutation round 1, IND-5): a Corti answer or another model's reading that is not shown - not read, or
    refused - is not listed under "shown above"; the peer builder refuses any other list (peer.check_frozen). The
    other model's entry still names its frozen reading (its reading_sha256), from which what is shown is made."""
    peers = {}
    corti = _corti_conclusions(first.provider_run)
    if corti is not None:
        peers['corti'] = corti
    for other in participants.PARTICIPANTS:
        if other != name and (records.get(other) or {}).get('state') == 'read':
            peers[other] = participant_peer.shown_reading(_frozen_reading(revision, other, records))
    cpt_studio = _peer_codes(_cpt_studio_reading(first))
    shown = {name, *peers, 'revision'}
    frozen = [list(pair) for pair in (records.get(name) or {}).get('frozen') or []
              if isinstance(pair, (list, tuple)) and len(pair) == 2 and pair[0] in shown]
    return (_frozen_reading(revision, name, records), peers, cpt_studio,
            frozen + [['cpt_studio', sha256_json(cpt_studio)]])


def _frozen_reading(revision, name, records):
    """Participant ``name``'s frozen first reading as assess #1 read it: re-read from the phase-1 run its entry names,
    and the same reading only when its sha256 is the one the entry recorded (recorded_reading)."""
    _, reading = recorded_reading(revision, records.get(name) or {})
    if reading is None:
        raise _PeerUnbuilt(PEER_FROZEN_CHANGED)
    return reading


def answer_sha256(answer) -> str:
    """The sha256 of a normalized reading or peer review in canonical JSON (HARNESS.md 12.3: an entry's reading_sha256
    and peer_sha256): the one hash an assessment records for a frozen output and every reader compares it with."""
    return sha256_json(to_jsonable(answer))


def recorded_reading(revision, record):
    """(run, reading) of the frozen first reading an Assessment.participants entry ``record`` names (HARNESS.md 12.3):
    its phase-1 run of ``revision`` (entry_run), re-read as participant_reading reads it, and the reading only when it
    was read, is not refused and its sha256 is the entry's reading_sha256 - anything else is not what was frozen (None).
    The peer stage builds its request from it, and the API's candidates read it (review.frozen_inputs)."""
    run = entry_run(revision, record, models.ProviderRun.INDEPENDENT)
    reading = participant_reading(run)[0] if run is not None and run.state == models.ProviderRun.SUCCEEDED else None
    if (reading is None or reading.refused or not record.get('reading_sha256')
            or answer_sha256(reading) != record['reading_sha256']):
        return run, None
    return run, reading


def recorded_peer_review(revision, record):
    """(run, peer review) of the peer review an assess #2 entry ``record`` names (HARNESS.md 12.3), read as
    recorded_reading reads a first reading: re-read with peer_reading, and the review only when its state was 'read',
    it is not refused and its sha256 is the entry's peer_sha256 (None otherwise)."""
    run = entry_run(revision, record, models.ProviderRun.PEER_REVIEW)
    review_ = peer_reading(run)[0] if run is not None and run.state == models.ProviderRun.SUCCEEDED else None
    if (review_ is None or review_.refused or record.get('peer_state') != 'read' or not record.get('peer_sha256')
            or answer_sha256(review_) != record['peer_sha256']):
        return run, None
    return run, review_


def entry_run(revision, record, purpose):
    """The run an Assessment.participants entry names for its participant - its phase-1 'run' (purpose independent) or
    its 'peer_run' (purpose peer_review) - when that is the participant's run of ``revision`` with that purpose; None
    otherwise (no entry, no run named, or one that is not a run id)."""
    if not isinstance(record, dict):
        return None
    field = 'peer_run' if purpose == models.ProviderRun.PEER_REVIEW else 'run'
    return _own_run(revision, record.get('name'), record.get(field), purpose)


def _corti_conclusions(run):
    """Corti's frozen conclusions as a peer is shown them (HARNESS.md 12.4): its selected codes in its own order, each
    once, with the units it selected it in (as the engine counts them), no modifiers (its API states none) and the
    passages of the document its evidence quotes exactly - never its display text, and never a passage of the date line
    CPT Studio adds to its request, which is no document text. A code is shown as given only in a CPT or HCPCS code's
    shape, and any other only by its length (peer.shown_code; refutation round 3, peer-1: Corti's adapter keeps any
    string as a code, and 'SYNTH;WITH-LESION(S)' - 20 characters, which the engine never lists - passed the 20-character
    token rule of round 2's IR2-3 repair to both vendors). None when its answer was not read: no run, a run that did not
    succeed, or a response refused whole."""
    if run is None or run.state != models.ProviderRun.SUCCEEDED:
        return None
    _, normalized = _provider_inputs(run)
    if normalized is None or normalized.refused:
        return None
    selected = {}
    for code in normalized.codes:
        if code.role == 'selected' and isinstance(code.code, str):
            selected.setdefault(code.code, []).append(code)
    return {'codes': [{'code': participant_peer.shown_code(code), 'modifiers': [], 'units': len(items),
                       'evidence': list(dict.fromkeys(span.text for item in items for span in item.evidence
                                                      if span.context_index == 0 and span.exact))}
                      for code, items in selected.items()]}


def _peer_codes(cpt_studio):
    """CPT Studio's rule-based reading (_cpt_studio_reading) as a peer request shows it: each held or excluded
    proposal's code only in a CPT or HCPCS code's shape, any other only by its length (peer.shown_code), as Corti's own
    section shows it. The engine lists any code of up to 10 characters Corti selected as a proposal, and one in no
    code's shape is excluded for scope with the scope check's sentence alone, which never names it - so its code was the
    one place such a value reached a peer request through CPT Studio's reading (refutation round 3, peer-1: a Corti
    code withheld in Corti's section was shown as given here). Everything else is as _cpt_studio_reading made it; a new
    dict."""
    return {**cpt_studio, **{key: [dict(item, code=participant_peer.shown_code(item['code']))
                                   for item in cpt_studio[key]] for key in ('held', 'excluded')}}


# What a peer request shows of CPT Studio's reading carries no person and no value a member entered (refutation round 2,
# IR2-1, IR2-2; the session lead's D4). The page and the reports keep their own wording: this is what a model is shown.
PEER_CONFIRMED_REASON = ("This code's reading rests in part on a reviewer's confirmation of a participant's located "
                         "passage, not on CPT Studio's own readers, so its reasons are not shown here.")
PEER_MEMBER_CONFLICT = ('Encounter metadata a workspace member entered differs from what the document gives; both are '
                        'kept and neither is used until they agree. The value entered is not shown here.')
PEER_MEMBER_DATE = 'the date of service a workspace member entered'
_MEMBER_CONFLICT_PREFIX = gi_context.USER_CONFLICT_NOTE.split('{', 1)[0]  # how every member conflict's note opens


def _cpt_studio_reading(first):
    """CPT Studio's rule-based reading after assess #1 (HARNESS.md 12.4): its open clarifications, as the questions a
    peer answers by id, and its held and excluded proposals, each with the details of its checks that did not pass. The
    peer instructions label it as a reading that may be wrong. Each question is described by review.question_identity,
    the one function the API's candidates match a peer answer back to the final assessment's question by (12.5), and
    named by its stable id (_question_ids).

    It names no person and no value a member entered (refutation round 2, IR2-1, IR2-2; HARNESS.md 12.4 as amended): a
    proposal whose reading rests on a reviewer's confirmation is shown with one fixed sentence in place of its reasons
    (_peer_reasons), and every reason and question is shown without a member's value (_peer_text)."""
    member_date = _member_date(first)
    items = list(first.clarifications.filter(state=models.Clarification.OPEN).select_related('proposal')
                 .order_by('created_at', 'pk'))
    named = _question_ids(first, items)
    questions = []
    for item in items:
        scope, family, fact, proposal_key, _ = review.question_identity(item)
        questions.append({'question_id': named[item.pk], 'scope': scope, 'fact': fact, 'family': family,
                          'proposal_key': proposal_key, 'question': _peer_text(item.question, member_date),
                          'reason': _peer_text(item.reason, member_date)})

    def proposals(status):
        return [{'key': p.key, 'code': p.code, 'status': p.status, 'reasons': _peer_reasons(p, member_date)}
                for p in first.proposals.filter(status=status).order_by('position')]
    return {'open_questions': questions, 'held': proposals(models.Proposal.NEEDS_CLARIFICATION),
            'excluded': proposals(models.Proposal.STATUS_EXCLUDED)}


def _peer_reasons(proposal, member_date):
    """A held or excluded proposal's reasons as a peer request shows them: the details of its checks that did not pass,
    without a member's value (_peer_text) - or, when its reading rests on a reviewer's confirmation, the one fixed
    sentence PEER_CONFIRMED_REASON in their place. Such a proposal's checks word the confirmation "confirmed from
    <participant>'s located passage by <reviewer>", whichever of them carries it, so none of them is shown: a member's
    identity, and a reviewer's attested conclusion filed as CPT Studio's own reading, reached both vendors (IR2-1). It
    rests on one when support['confirmed'] lists a confirmation it read, or - fail closed - when any of its checks,
    passed or not, is a confirmation's (checks.CONFIRMATION_SOURCE) or words one (checks.CONFIRMED_HEADING)."""
    found = [check for check in proposal.checks or [] if isinstance(check, dict)]
    support = proposal.support if isinstance(proposal.support, dict) else {}
    if support.get('confirmed') or any(check.get('source') == validation_checks.CONFIRMATION_SOURCE
                                       or validation_checks.CONFIRMED_HEADING in str(check.get('detail') or '')
                                       for check in found):
        return [PEER_CONFIRMED_REASON]
    return [_peer_text(str(check.get('detail') or ''), member_date) for check in found if check.get('status') != 'pass']


def _peer_text(text, member_date):
    """``text`` (a check's detail, a question or its reason) as a peer request shows it: no value a workspace member
    entered (refutation round 2, IR2-2; HARNESS.md 3: no member-entered date, setting or billing context is sent). The
    facts.required clause listing what a member entered (checks.MEMBER_ENTERED) is left out - it closes the detail,
    which then holds only CPT Studio's own reading; a member conflict's note (context.USER_CONFLICT_NOTE and the notes
    sharing its opening words) is replaced, from those words on, by PEER_MEMBER_CONFLICT, which leaves the value out;
    and a service date a member entered (``member_date``) is named PEER_MEMBER_DATE. So a save that changes only a
    member's value, and nothing CPT Studio reads, makes the identical peer request, which is reused."""
    clause = text.find(validation_checks.MEMBER_ENTERED)
    if clause != -1:
        text = text[:clause].rstrip()
    conflict = text.find(_MEMBER_CONFLICT_PREFIX)
    if conflict != -1:
        text = text[:conflict] + PEER_MEMBER_CONFLICT
    return text.replace(member_date, PEER_MEMBER_DATE) if member_date else text


def _member_date(first):
    """The service date a workspace member entered as encounter metadata that assess #1 ``first`` read (its context's
    service_date fact of origin 'user'), or '' when the date it read is the document's, or there is none."""
    fact = ((first.context.facts or {}) if first.context_id else {}).get('service_date')
    value = fact.get('value') if isinstance(fact, dict) and fact.get('origin') == 'user' else None
    return value if isinstance(value, str) else ''


def _question_ids(first, items):
    """{clarification pk: the id a peer request names it by} for ``items``, open questions of assess #1 ``first``
    (pipeline Q2: assess #1's own row ids changed with every new assess #1, so an identical question made a new, paid
    peer request each time). A question is named by the first clarification of the revision that asks the same thing -
    the same review.question_identity - so the same question has the same id however many assessments ask it, and the
    identical peer request is reused, never resent. That id is a clarification of this encounter and revision, which is
    how the review package resolves an answer's id (review.peer_answers, the reports) before it matches the question
    through that same identity. Fail closed: a question whose identity two open questions here share keeps its own
    id."""
    identities = {item.pk: review.question_identity(item) for item in items}
    seen = list(identities.values())
    unique = {identity for identity in seen if seen.count(identity) == 1}
    earliest = {}
    for row in (models.Clarification.objects.filter(encounter_id=first.encounter_id,
                                                    assessment__revision_id=first.revision_id)
                .select_related('proposal').order_by('created_at', 'pk')):
        identity = review.question_identity(row)
        if identity in unique:
            earliest.setdefault(identity, row.pk)
    return {pk: str(earliest.get(identity, pk) if identity in unique else pk) for pk, identity in identities.items()}


def _first_located(quotes):
    """The first located occurrence among ``quotes`` (LocatedQuote): an exact slice of the revision text (I7); '' when
    none was located - an unlocated quote is never shown as evidence."""
    for quote in quotes:
        for span in quote.spans:
            return span.text
    return ''


def _participant_record(name, state, run, reading, reason):
    """One Assessment.participants entry (HARNESS.md 6, 12.3): the state, the run and adapter version it was read from,
    the models requested and returned, the unverified-quote count and why it was not read or not used; and, from a
    reading that was used, the codes it proposed and those it advised not to code, each with its first located quote, so
    the screen and the reports state its positions without re-reading the run. harness@2 adds the sha256 of the
    normalized reading in canonical JSON ('' when there is none) and the exchanges and tool calls of the run's loop
    (loop_run: a reuse's are those of the run it reuses)."""
    used = reading if state == 'read' else None
    proposed, advised = {}, {}
    for item in used.codes if used is not None else ():
        proposed[item.code] = proposed.get(item.code) or _first_located(item.evidence)
    for item in used.not_coded if used is not None else ():
        if item.code and item.code not in advised:
            advised[item.code] = {'code': item.code, 'reason': item.reason, 'quote': _first_located(item.evidence)}
    source = loop_runs(run) if run is not None else None  # a continuation's whole loop (F-STOP)
    return {'name': name, 'state': state, 'run': str(run.pk) if run is not None else None,
            'adapter_version': run.adapter_version if run is not None else '',
            'requested_model': run.requested_model if run is not None else '',
            'returned_model': run.returned_model if run is not None else '',
            'unverified_quotes': reading.unverified_quotes if reading is not None else 0, 'reason': reason,
            'codes': [{'code': code, 'quote': quote} for code, quote in proposed.items()],
            'not_coded': list(advised.values()),
            'reading_sha256': answer_sha256(reading) if reading is not None else '',
            'exchanges': (models.ProviderExchange.objects.filter(run__in=source).count()
                          if source is not None else 0),
            'tool_calls': models.ToolCall.objects.filter(exchange__run__in=source).count() if source is not None else 0}


def not_configured_record(name):
    """The Assessment.participants entry of a participant not configured on this installation (I1: 'not configured')."""
    return {'name': name, 'state': 'not_configured', 'run': None, 'adapter_version': '', 'requested_model': '',
            'returned_model': '', 'unverified_quotes': 0,
            'reason': PARTICIPANT_NOT_CONFIGURED.format(label=participants.LABELS.get(name, name)), 'codes': [],
            'not_coded': []}


def participant_reading(run):
    """(reading, problem): participant run ``run``'s stored answer read as the adapter version that recorded it, after
    its bytes are checked against their recorded sha256, with the refs its own loop's tool calls returned (run_refs:
    references_used is checked against them); (None, why) when it cannot be read. Needs no credentials."""
    return _stored_answer(run, participants.reader_for)


def peer_reading(run):
    """(peer review, problem): peer-review run ``run``'s stored answer (HARNESS.md 11.1), read as participant_reading
    reads a first reading, by the peer reader of the adapter version that recorded it."""
    return _stored_answer(run, participants.peer_reader_for)


def _stored_answer(run, reader_for):
    data = bytes(run.response_bytes)
    if hashlib.sha256(data).hexdigest() != run.response_sha256:
        return None, 'The stored response no longer matches its recorded hash; it was not read.'
    request = ProviderRequest(provider=run.provider, adapter_version=run.adapter_version, body=run.request_body,
                              canonical_sha256=run.request_sha256, contexts=tuple(run.contexts))
    try:
        reader = reader_for(run.provider, run.adapter_version)
    except ProviderUnavailable as exc:
        return None, str(exc)
    refs = run_refs(run)
    try:  # a run whose loop called no tool is read exactly as before
        return (reader(request, data, refs) if refs else reader(request, data)), ''
    except Exception as exc:  # noqa: BLE001 - logged; one participant's unreadable answer blocks only itself (I10)
        log.exception('the stored answer of participant run %s could not be read', run.pk)
        return None, PARTICIPANT_UNREADABLE_MESSAGE.format(error=type(exc).__name__)


def _participant_input(encounter, revision, name, *, held=False):
    """(ParticipantInput, its Assessment.participants record) of configured participant ``name`` (HARNESS.md 5), read
    from its newest finished run for ``revision`` (_participant_run): 'read' with the reading; 'refused' when the
    reading - or the stored answer itself - was not used; 'blocked' for a run the unknown-outcome block stopped;
    otherwise the run's own state; 'not_run' when there is none ('blocked' while an unknown outcome stands; ``held``:
    the assess reads Corti's member date hold, while which nothing is sent, and the reason says so). A participant's own
    failure is its state, never the stage's (I10)."""
    return _first_input(encounter, name, _participant_run(revision, name), held=held)


def _first_input(encounter, name, run, *, held=False, kept=None):
    """_participant_input's reading of a given phase-1 run (None: none). ``kept``: the (state, reason) an earlier
    assessment recorded for a participant it read with no run, re-read exactly as it was (_reread)."""
    reading = None
    if run is None and kept is not None:
        state, reason = kept
    elif run is None and _unreconciled_unknown(encounter):
        state, reason = 'blocked', PARTICIPANT_BLOCKED_MESSAGE
    elif run is None:
        state, reason = 'not_run', (PARTICIPANT_HELD_MESSAGE.format(label=participants.LABELS.get(name, name)) if held
                                    else PARTICIPANT_NOT_RUN)
    elif run.state == models.ProviderRun.SUCCEEDED:
        reading, problem = participant_reading(run)
        if reading is None:
            state, reason = 'refused', problem
        elif reading.refused:
            state, reason = 'refused', '; '.join(reading.problems) or 'The reading was not used.'
        else:
            state, reason = 'read', ''
    elif run.state == models.ProviderRun.NOT_SENT and (run.scope or {}).get('held') == UNKNOWN_OUTCOME_HELD:
        state, reason = 'blocked', run.error
    else:
        state, reason = run.state, run.error
    return (ParticipantInput(provider=name, state=state, reading=reading if state == 'read' else None, reason=reason),
            _participant_record(name, state, run, reading, reason))


PEER_FIRST_NOT_READ = 'Its first reading was not read, so it takes no part in peer review.'
PEER_NOT_RUN = 'No peer-review request was made.'
ASSESS_MOVED = ('the assessment this stage reads is no longer the newest of its revision, so a newer chain owns the '
                'revision; nothing was assessed')


def _with_peer(encounter, item, record, run, kept=None):
    """``item`` and ``record`` (a participant's phase-1 input and entry) with its peer review (HARNESS.md 12.1, 12.3),
    read from peer-review run ``run`` as a first reading is read from its run: 'not_run' for a participant whose first
    reading was not read, which takes no part. ``kept``: the (peer state, reason) an earlier assessment recorded for a
    peer review it read with no run. The input's reason speaks for the peer review beside a first reading that was read
    (the engine's convention); the entry keeps both reasons apart."""
    peer = None
    if item.state != 'read':
        state, reason = 'not_run', PEER_FIRST_NOT_READ
    elif run is None and kept is not None:
        state, reason = kept
    elif run is None and _unreconciled_unknown(encounter):
        state, reason = 'blocked', PARTICIPANT_BLOCKED_MESSAGE
    elif run is None:
        state, reason = 'not_run', PEER_NOT_RUN
    elif run.state == models.ProviderRun.SUCCEEDED:
        peer, problem = peer_reading(run)
        if peer is None:
            state, reason = 'refused', problem
        elif peer.refused:
            state, reason = 'refused', '; '.join(peer.problems) or 'The peer review was not used.'
        else:
            state, reason = 'read', ''
    elif run.state == models.ProviderRun.NOT_SENT and (run.scope or {}).get('held') == UNKNOWN_OUTCOME_HELD:
        state, reason = 'blocked', run.error
    else:
        state, reason = run.state, run.error
    first_reason = item.reason if item.state != 'read' else ('' if state == 'read' else reason)
    item = dataclasses.replace(item, peer_state=state, peer=peer if state == 'read' else None, reason=first_reason)
    return item, {**record, 'peer_state': state, 'peer_run': str(run.pk) if run is not None else None,
                  'peer_reason': reason, 'peer_sha256': answer_sha256(peer) if peer is not None else '',
                  'peer_unverified_quotes': peer.unverified_quotes if peer is not None else 0}


def _reread(encounter, revision, basis, names, mode):
    """[(ParticipantInput, record)] of what assess #2 (FINAL) or a re-assessment (AGAIN) reads (HARNESS.md 12.1): the
    phase-1 runs ``basis`` read - for assess #2, assess #1 - and the peer runs: for assess #2 those made for assess #1,
    for a re-assessment those ``basis`` read, when it had a peer phase. A participant ``basis`` read with no run is read
    as ``basis`` recorded it; one it recorded as not configured, configured since, as one with no run."""
    records = _records(basis)
    out = []
    for name in names:
        record = records.get(name) or {}
        run = _own_run(revision, name, record.get('run'), models.ProviderRun.INDEPENDENT)
        recorded = record.get('state') not in (None, 'not_configured')
        item, entry = _first_input(encounter, name, run,
                                   kept=(record['state'], record.get('reason') or '') if run is None and recorded
                                   else None)
        if mode == FINAL:
            out.append(_with_peer(encounter, item, entry, _peer_run(revision, name, basis)))
        elif 'peer_state' in record:
            peer_run = _own_run(revision, name, record.get('peer_run'), models.ProviderRun.PEER_REVIEW)
            out.append(_with_peer(encounter, item, entry, peer_run,
                                  kept=(record['peer_state'], record.get('peer_reason') or '') if peer_run is None
                                  else None))
        else:
            out.append((item, entry))
    return out


def _own_run(revision, name, pk, purpose):
    """The run an assessment's entry names for participant ``name``, of this revision and purpose; None for none, and
    for a value that is not a run id (an entry is read back from JSON, never assumed well formed)."""
    if not pk or not isinstance(pk, str) or not isinstance(name, str):
        return None
    try:
        pk = uuid.UUID(pk)
    except ValueError:
        return None
    return revision.provider_runs.filter(pk=pk, provider=name, purpose=purpose).first()


def _frozen(revision, corti, records):
    """assess #1's and #2's frozen list (HARNESS.md 11.1, 12.3): every frozen phase-1 output by name and sha256 -
    'corti', the Corti run's response bytes; each model participant with a reading, its normalized reading in canonical
    JSON; and 'revision', the text they were all built from - in harness order."""
    frozen = [['corti', corti.response_sha256]] if corti is not None and corti.response_sha256 else []
    frozen += [[name, records[name]['reading_sha256']] for name in participants.PARTICIPANTS
               if (records.get(name) or {}).get('reading_sha256')]
    return frozen + [['revision', revision.text_sha256]]


def confirmed_findings(revision):
    """The reviewer-confirmed findings an assessment of ``revision`` reads (HARNESS.md 11.3, 12.5): every
    FindingConfirmation of this revision only - a new revision's assessment reads none - except the service date's,
    which entered through the context as the member's date and is never the engine's. Each passage's exactness is
    checked against the revision text, never assumed; the engine checks it again and lists a confirmation it does not
    read, with why. A proposal's question is bound to the proposal it was made for: the code and support['identity'] of
    its clarification's own proposal row, which is the question the reviewer answered - never the key alone, which
    a later assessment can give to another code (EV-1); a row whose proposal records no identity binds to nothing, and
    the engine says so. Refutation round 3 (HARNESS.md 12.10, D7): while confirmations are not offered - the release
    default - it hands the engine none, without reading a row: one that exists anyway (a test's, an earlier
    installation's) is never applied."""
    if not review.confirmations_offered():
        return ()
    text = revision.text
    found = []
    for row in (models.FindingConfirmation.objects.filter(revision=revision)
                .select_related('confirmed_by', 'clarification__proposal').order_by('created_at', 'pk')):
        if row.scope == 'encounter' or row.fact == 'service_date':
            continue
        proposal = row.clarification.proposal if row.scope == 'proposal' else None
        identity = (proposal.support or {}).get('identity') if proposal is not None else ''
        found.append(ConfirmedFinding(
            scope=row.scope, fact=row.fact, family=row.family, proposal_key=row.proposal_key, value=row.value,
            evidence=tuple(_confirmed_span(span, text) for span in row.spans if isinstance(span, dict))
            if isinstance(row.spans, list) else (),
            located_by=tuple(row.located_by) if isinstance(row.located_by, list) else (),
            confirmed_by=row.confirmed_by.label(), confirmation_id=str(row.pk),
            proposal_code=proposal.code if proposal is not None else '',
            proposal_identity=identity if isinstance(identity, str) else ''))
    return tuple(found)


def _confirmed_span(span, text):
    start, end, quoted = span.get('start'), span.get('end'), span.get('text')
    exact = (type(start) is int and type(end) is int and isinstance(quoted, str) and 0 <= start < end <= len(text)
             and text[start:end] == quoted)
    page = span.get('page')
    return EvidenceSpan(0, start if type(start) is int else -1, end if type(end) is int else -1,
                        quoted if isinstance(quoted, str) else '', exact, page if type(page) is int else None)


# A retrieval's note says the step that failed (refutation round 4, truth-5), one sentence each: loading the stored CMS
# passages, before the retrieval read anything (RETRIEVAL_STEP_LOAD: a passage changed after import fails its sha256
# check), or the retrieval of the facts and passages for the codes itself (RETRIEVAL_STEP_RETRIEVE). The note had said
# "CPT Studio could not record which CMS reference facts and passages it retrieved" of a failed load, when the retrieval
# never ran and nothing was retrieved, and every code card points to that note for what failed.
RETRIEVAL_STEP_LOAD = 'load'
RETRIEVAL_STEP_RETRIEVE = 'retrieve'
# Where an installed CMS reference file applied to the assessment's service date, each code's checks read the CMS facts
# before the retrieval (stage_assess looks them up first), and stand.
RETRIEVAL_FAILED = ("Reference validation failed: CPT Studio's retrieval for this assessment's codes failed ({error}, "
                    "logged), so no CMS reference fact or passage is listed here. Each code's checks read the CMS facts "
                    "before that and stand as shown; retrieval only informs the reviewer and decides no status, so the "
                    "assessment stands as made.")
RETRIEVAL_LOAD_FAILED = ("Reference validation failed: CPT Studio could not load the stored CMS reference passages "
                         "({error}, logged), so the retrieval for this assessment's codes did not run and no CMS "
                         "reference fact or passage is listed here. Each code's checks read the CMS facts before that "
                         "and stand as shown; retrieval only informs the reviewer and decides no status, so the "
                         "assessment stands as made.")
# The notes where no installed CMS reference file applied to the assessment's service date: no code's checks read a CMS
# fact (each is not verified), so the note says that no code was checked against a CMS reference file and why -
# {why}, serializers.no_source_sentence, the words reference validation says when the retrieval itself succeeds -
# never that the checks read the CMS facts (refutation round 3, truth-1: it said so beside checks that were all "not
# verified", and that CPT Studio could not record the facts it retrieved, when no file applied and none was).
RETRIEVAL_FAILED_UNCHECKED = ("Reference validation failed: CPT Studio's retrieval for this assessment's codes failed "
                              "({error}, logged), so no CMS reference fact or passage is listed here. {why} Retrieval "
                              "only informs the reviewer and decides no status, so the assessment stands as made.")
RETRIEVAL_LOAD_FAILED_UNCHECKED = ("Reference validation failed: CPT Studio could not load the stored CMS reference "
                                   "passages ({error}, logged), so the retrieval for this assessment's codes did not "
                                   "run and no CMS reference fact or passage is listed here. {why} Retrieval only "
                                   "informs the reviewer and decides no status, so the assessment stands as made.")


def _retrieval(result, service_date, reference, provider_codes):
    """The retrieval traces (HARNESS.md 5, Assessment.retrieval) for the codes of the assessment's proposals a reviewer
    can decide (review.decidable: selected, or excluded and reinstatable) among the codes the proposal provider selected
    (``provider_codes``: its first and its bounded second review's selections), from the checks' own lookup,
    with the CMS passages that govern its facts, read here in the parent, which has the database. [] only when no such
    proposal has such a code. An alternative's code is never traced, whoever gave it: a participant's (refutation round
    7, d14-1: in this release it is never a proposal, D14), the provider's candidate, or a code its bounded second
    review selected that CPT Studio did not add (alt2; refutation round 8, retrieval-1 and retrieval-2). Tracing one
    beside the proposals' codes gave a proposal's code CMS endoscopy-family rules and passages that pair it with a code
    no proposal carries, and counted that code as checked against the CMS reference files, even where no proposal could
    be decided on. Nor is a code excluded with no reinstatement - outside CPT-only results, or with no exact source
    evidence - whose CMS checks never ran and which no reviewer can decide (refutation round 9, retrieval-1,
    retrieval-2, page-1: it was traced, paired a READY 45378 with it in a CMS endoscopy-family rule, and was counted
    "Done 1 code checked"). The lookup is still prefetched for every selection, which the checks read (_second_review
    evaluates the second review's). The traces are a record kept beside the engine's result, never part of what I1 pins
    (HARNESS.md 9), so tracing only the decidable codes changes no result, with no participant configured or with one.

    A retrieval that fails never stops the assessment (I1, I10; refutation round 1, parity-1: a Corti code ending in a
    superscript digit raised here and the encounter was left with no assessment at all). Retrieval only informs the
    reviewer, so the assessment is recorded as made and its retrieval is one entry marked 'failed' whose note says that
    reference validation failed (retrieval_failure): never a trace that reads as a code checked. Whether an installed
    CMS reference file applied to the service date - so that the codes' checks read the CMS facts - is the engine's own
    record of the lookup (``result.reference_sources``), read here in memory, never asked of the database again. The
    entry names the step that failed: loading the stored passages, or the retrieval (refutation round 4, truth-5)."""
    # Completion repair (integration, 2026-11-06; builder Q1's measured patch): every decidable proposal's code, whoever
    # proposed it - an admitted participant code is a proposal a member decides (directive item 3), and its checks read
    # the lookup prefetched for every proposed code (stage_assess). ``provider_codes`` is kept for the record's callers;
    # review.decidable still keeps every alternative out, so the refutation rounds' cases above are unchanged.
    codes = sorted({proposal.code for proposal in result.proposals if review.decidable(proposal)})
    if not codes:
        return []
    step = RETRIEVAL_STEP_LOAD
    try:
        passages = reference_passages.load_passages()
        step = RETRIEVAL_STEP_RETRIEVE
        return to_jsonable(list(reference_passages.retrieve(codes, service_date, reference, passages)))
    except Exception as exc:  # noqa: BLE001 - logged; the record says reference validation failed, never the internals
        log.exception('reference retrieval failed for %d code(s) of an assessment', len(codes))
        from .serializers import source_applied  # local import: serializers imports this module's peers

        return [retrieval_failure(service_date, type(exc).__name__,
                                  applied=source_applied(getattr(result, 'reference_sources', ())), step=step)]


def retrieval_failure(service_date, error, *, applied=False, step=RETRIEVAL_STEP_RETRIEVE):
    """The one Assessment.retrieval entry of a retrieval that failed: no code, no fact, no passage, and CPT Studio's own
    sentence saying reference validation failed, which step failed, and what that leaves of the codes' checks.
    ``step``: RETRIEVAL_STEP_LOAD where the stored CMS passages could not be loaded, so the retrieval never ran
    (RETRIEVAL_LOAD_FAILED*); otherwise the retrieval's own sentence, which claims nothing was loaded or read
    (RETRIEVAL_FAILED*; refutation round 4, truth-5: a failed load had read "could not record which CMS reference facts
    and passages it retrieved"), so a caller that names no step, or one this does not know, never has the note claim
    one. ``applied``: an installed CMS reference file applied to the service date (the engine's reference_sources), so
    each code's checks read the CMS facts before the retrieval and stand; otherwise none read one, and the note says
    that no code was checked against a CMS reference file, and why (*_UNCHECKED; refutation round 3, truth-1). False
    unless the caller read that one applied, so the note never claims a check read a CMS fact it did not read. Marked
    'failed', so no reader counts it as a code checked."""
    from .serializers import no_source_sentence  # local import: serializers imports this module's peers

    day = service_date.isoformat() if service_date else None
    load = step == RETRIEVAL_STEP_LOAD
    if applied:
        note = (RETRIEVAL_LOAD_FAILED if load else RETRIEVAL_FAILED).format(error=error)
    else:
        note = (RETRIEVAL_LOAD_FAILED_UNCHECKED if load else RETRIEVAL_FAILED_UNCHECKED).format(
            error=error, why=no_source_sentence(day))
    return {'code': '', 'service_date': day, 'facts': [], 'passages': [], 'lookups': [], 'notes': [note],
            'failed': True}


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


# --- assess on the new path (design/FINAL.md 6.7, as design/ADJUDICATION.md amends it) -------------------------------
#
# stage_assess dispatches on the context it was given: a gemini context's assess is _assess_events - the events engine
# (studio.interpretation.assess) over the context's EventInventory, in one bounded child counted against the stage's
# new_path scope (sentinel.run_counted), its RoutingRun the context's derived stand-in for the date (looked up, never
# recomputed), and the assessment recorded with its inventory and its D22 record through persist_assessment's sentinel
# write gate. Any other context ends StageCancelled (resumable): this image never runs the legacy child
# (_refuse_legacy_context). What an events assess reads, by its key's marks (_events_mode):
# - FIRST: the inventory the context names, the Corti run (Job.provider_run), each configured participant's newest
#   phase-1 run, the standing member answers; it queues the first owed peer stage, as before;
# - FINAL (':q:'): what assess #1 read, by the ids it recorded, plus the peer runs made for it; assess #1 must have been
#   made from the context's inventory, or a newer chain owns the revision (ASSESS_MOVED); it queues nothing;
# - AGAIN (':c:': an answer's recompute, a retained re-assessment): the final's inventory and runs by id; nothing is
#   sent and nothing queued (D8);
# - REVIEW2 (':review2:', the follow-up of the bounded second review): as FINAL reads - the inputs the assessment it
#   follows recorded, by id, its peer runs included - plus the second review, merged by the events engine (FINAL 7.10);
#   it queues nothing.

REVIEW2 = 'review2'  # what an assess reads (_events_mode): the follow-up of a bounded second review
REVIEW2_MARK = ':review2:'
ASSESS_SCOPE = 'assess'  # the D22 record's sentinel scope name (FINAL 10.3)
CONTEXT_INVENTORY_MESSAGE = ('The context names no event inventory of this revision, so nothing was assessed from '
                             'it.')
CONTEXT_DERIVATION_MESSAGE = ('The context is not what its event inventory and its member values derive, so nothing '
                              'was assessed from it.')
STAND_IN_MISSING_MESSAGE = ('No derived routing record is stored for the context\'s date of service, so nothing was '
                            'assessed. Resume to process the document again.')
PROVIDER_DATE_MESSAGE = ('The provider result was requested for a different service date than this context; it was not '
                         'used. Change the context again to request proposals for this date.')


def _events_mode(job):
    """What an events assess reads, from the key it was queued under (a Resume keeps the stage's own key as its prefix):
    AGAIN (':c:'), FINAL (':q:'), REVIEW2 (':review2:') or FIRST - in that order, since a re-assessment's key keeps the
    marks of the assessment it re-makes."""
    key = job.idempotency_key
    if AGAIN_MARK in key:
        return AGAIN
    if FINAL_MARK in key:
        return FINAL
    return REVIEW2 if REVIEW2_MARK in key else FIRST


def _assess_child_events(stored, context, normalized, reference, provider_status, text, pages, extraction_status,
                         extraction_messages, second=None, second_scope=None, participant_inputs=(), member_answers=()):
    """The events engine's assessment of ``stored`` - the context's EventInventory as interpretation.store.load read it
    - in one bounded child (DB-free; its denied executions counted by sentinel.run_counted): the engine reads the
    inventory and the gemini context's facts for meaning, and the revision ``text`` only for the exactness of the
    proposers' spans and the member answers' passages (studio/interpretation/assess.py)."""
    return events_engine.assess(
        inventory=stored, context=context, normalized=normalized, provider_status=provider_status, reference=reference,
        text=text, pages=pages, extraction_status=extraction_status, extraction_messages=extraction_messages,
        second=second, second_scope=second_scope, participants=participant_inputs, member_answers=member_answers)


def _events_inventory(job):
    """(the EventInventory row, its store.StoredInventory) that the events assess ``job`` reads: the one its gemini
    context names (Job.context: never the newest inventory). One of other versions ends the stage resumable (the
    revision is read again on Resume); one that is missing, not read or not this revision's fails it."""
    context, revision = job.context, job.revision
    inventory = (models.EventInventory.objects.select_related('provider_run')
                 .filter(pk=context.event_inventory_id, encounter_id=job.encounter_id).first()
                 if context.event_inventory_id else None)
    if inventory is None or inventory.revision_id != revision.pk or context.revision_id != revision.pk:
        raise StageFailure(CONTEXT_INVENTORY_MESSAGE)
    if (inventory.interpretation_version, inventory.inventory_version) != _CURRENT_VERSIONS:
        raise StageCancelled(EARLIER_READING_MESSAGE)
    if inventory.state != models.EventInventory.READ:
        raise StageFailure(INVENTORY_NOT_READ_MESSAGE)
    return inventory, _stored_inventory(inventory, revision)


def _member_date_state(context, stored):
    """The contract 8.2 member_date_state row the gemini ``context``'s date came from (Assessment.interpretation's
    member_date_state): derived again, purely, from the inventory and the member values the context recorded - and only
    when that derivation gives the context's own date state, so the record never describes another derivation."""
    try:
        derived = interpretation_facts.derive(stored, dict(context.user_values or {}))
    except (TypeError, ValueError):
        raise StageFailure(CONTEXT_DERIVATION_MESSAGE) from None
    if derived.member_date.state != ((context.facts or {}).get('service_date') or {}).get('state'):
        raise StageFailure(CONTEXT_DERIVATION_MESSAGE)
    return derived.member_date.as_record()


def _events_stand_in(revision, inventory, service_date):
    """The RoutingRun an events assessment records (FINAL 6.7 step 5): the gemini-routing@1 stand-in derived from
    ``inventory`` for ``service_date``, as analyze, predict or a context save recorded it - looked up, never
    recomputed here. None when there is none."""
    return (models.RoutingRun.objects.filter(revision=revision, version=interpretation.ROUTING_VERSION,
                                             service_date=service_date, result__inventory=str(inventory.pk))
            .order_by('-created_at', '-pk').first())


def _assess_events(job):
    """The assess stage on a gemini context (FINAL 6.7; the section comment above): read what its mode reads, assess in
    the bounded child, record the retrieval traces, take the context's stand-in for the date, and record the
    assessment with its event inventory and its D22 interpretation record - the sentinel's record of the stage scope
    taken just before persist_assessment, whose write gate refuses the insert when the scope counted a new_path
    execution (a StageFailure, nothing recorded, the trip audited). Nothing is sent, and no legacy reader runs."""
    revision, encounter, context, run = job.revision, job.encounter, job.context, job.provider_run
    revision.refresh_from_db()
    inventory, stored = _events_inventory(job)
    if run is not None and run_service_date(run) != context_service_date(context):
        raise StageFailure(PROVIDER_DATE_MESSAGE)
    held = (run is not None and run.state == models.ProviderRun.NOT_SENT
            and (run.scope or {}).get('held') == models.ProviderRun.HELD_MEMBER_DATE_CONFLICT)
    names = participants.configured()
    mode = _events_mode(job)
    if mode == FIRST:  # assess #1: the participants' newest phase-1 runs (HARNESS.md 2, 12.1)
        read = [_participant_input(encounter, revision, name, held=held) for name in names]
    else:
        # assess #2, a re-assessment and a second review's follow-up read the revision's newest assessment, which must
        # be the one they were queued for - made on this context, Corti run and event inventory; a newer chain owns the
        # revision otherwise, and nothing is assessed
        basis = _newest_assessment(revision)
        if (basis is None or basis.context_id != job.context_id or basis.provider_run_id != job.provider_run_id
                or basis.event_inventory_id != inventory.pk
                or (mode == FINAL and job.idempotency_key.split(':resume:', 1)[0] != _final_key(basis))):
            return {'skipped': ASSESS_MOVED}
        read = _reread(encounter, revision, basis, names, FINAL if mode == FINAL else AGAIN)
    provider_status, normalized = _provider_inputs(run)
    second = _second_run_for(revision, run)
    second_normalized = _second_inputs(second) if second is not None else None
    inputs = tuple(item for item, _ in read)
    proposed = {code.code for item in inputs if item.reading is not None for code in item.reading.codes}
    proposed |= {code.code for item in inputs if item.peer is not None for code in item.peer.additional_codes}
    provider_codes = tuple(sorted(set(selected_codes(normalized)) | set(selected_codes(second_normalized))))
    # every code the engine may look up, prefetched for the child, which has no database: a superset, never one missed
    looked_up = set(events_engine.codes_to_look_up(normalized, second_normalized, inputs)) | set(provider_codes)
    reference = prefetched_lookup(tuple(sorted(looked_up | proposed)))
    service_date = context_service_date(context)
    routing_run = _events_stand_in(revision, inventory, service_date)
    if routing_run is None:
        raise StageFailure(STAND_IN_MISSING_MESSAGE)
    member_date_state = _member_date_state(context, stored)
    release_routing_caches()  # FINAL 6.7 step 2: no cached legacy result answers for code (the scope clears too)
    seconds = settings.JOB_DEADLINE_SECONDS['assess']
    try:
        result = sentinel.run_counted(
            _assess_child_events, stored, dict(context.facts or {}), normalized, reference, provider_status,
            revision.text, tuple(PageSpan(**p) for p in revision.pages), revision.extraction_status,
            tuple(revision.messages), second_normalized, dict(second.scope) if second is not None else None, inputs,
            member_answers_of(revision), seconds=seconds, memory_bytes=settings.ASSESS_MEMORY_BYTES)
    except bounded.Overrun as exc:
        raise StageFailure(OVERRUN_MESSAGES[exc.reason].format(seconds=seconds)) from None
    retrieval = _retrieval(result, service_date, reference, provider_codes)  # a decidable code's only (r7, r8, r9)
    records = {record['name']: record for _, record in read}
    if names and mode != AGAIN:  # HARNESS.md 12.3: the frozen phase-1 outputs read, as assess #1 and #2 record them
        frozen = _frozen(revision, run, records)
        for record in records.values():
            record['frozen'] = frozen
    try:
        record = interpretation_report.interpretation_record(
            inventory=inventory, context=context, member_date_state=member_date_state,
            sentinel_record=sentinel.record(name=ASSESS_SCOPE))
        assessment = review.persist_assessment(
            encounter=encounter, revision=revision, context=context, routing_run=routing_run, provider_run=run,
            result=result, second_run=second, retrieval=retrieval,
            participants=[records.get(name) or not_configured_record(name) for name in participants.PARTICIPANTS],
            event_inventory=inventory, interpretation=record)
    except sentinel.Tripped as exc:  # the write gate refused: nothing recorded, the trip audited (FINAL 10.3)
        raise StageFailure(str(exc)) from None
    except ValueError as exc:
        raise StageFailure(f'The assessment was not recorded: {exc}') from exc
    out = {'assessment': str(assessment.pk), 'provider_status': provider_status, 'inventory': str(inventory.pk),
           'mode': mode}
    if second is not None:
        out['second_review'] = str(second.pk)
    if names and mode == FIRST and owed_peer_stages(assessment):
        # HARNESS.md 12.1, unchanged: assess #1 queues the first owed peer stage when a configured participant's first
        # reading was read; otherwise it is the final assessment. Nothing is sent while a member date conflict holds it.
        queued = _queue_peers(job, assessment, upgrade=_chain_upgrade(job))
        out['peer_review'] = queued.kind
    return out


def stage_assess(job):
    revision, encounter, context, run = job.revision, job.encounter, job.context, job.provider_run
    encounter.refresh_from_db()
    if encounter.current_revision_id != revision.pk:
        return {'skipped': 'a newer revision exists'}
    if context is not None and interpretation.is_new_context(context):
        return _assess_events(job)  # FINAL 6.7: the events engine, over the context's event inventory
    _refuse_legacy_context(job)  # FINAL 6.7 and 9: never the legacy child on this image (StageCancelled, resumable)
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
    # Each configured harness participant's reading of this revision (HARNESS.md 5), and the reviewer-confirmed findings
    # of the revision (12.5). None of either is passed when none is configured, so the engine's input, its result and
    # the lookups are exactly as before (I1).
    held = (run is not None and run.state == models.ProviderRun.NOT_SENT
            and (run.scope or {}).get('held') == models.ProviderRun.HELD_MEMBER_DATE_CONFLICT)
    names = participants.configured()
    mode = _assess_mode(job) if names else FIRST
    if mode == FIRST:  # assess #1: the participants' newest phase-1 runs (HARNESS.md 2, 12.1)
        read = [_participant_input(encounter, revision, name, held=held) for name in names]
    else:
        # assess #2 reads what assess #1 read and the peer runs made for it; a re-assessment after a confirmation reads
        # exactly what the final assessment read. Either reads the revision's newest assessment, which must be the one
        # it was queued for: a newer chain owns the revision otherwise, and nothing is assessed.
        basis = _newest_assessment(revision)
        if (basis is None or basis.context_id != job.context_id or basis.provider_run_id != job.provider_run_id
                or (mode == FINAL and job.idempotency_key.split(':resume:', 1)[0] != _final_key(basis))):
            return {'skipped': ASSESS_MOVED}
        read = _reread(encounter, revision, basis, names, mode)
    inputs = tuple(item for item, _ in read)
    proposed = {code.code for item in inputs if item.reading is not None for code in item.reading.codes}
    proposed |= {code.code for item in inputs if item.peer is not None for code in item.peer.additional_codes}
    provider_codes = tuple(sorted(set(selected_codes(normalized)) | set(selected_codes(second_normalized))))
    reference = prefetched_lookup(tuple(sorted(set(provider_codes) | proposed)))
    service_date = context_service_date(context)
    confirmed = confirmed_findings(revision) if names else ()
    # Completion repair (2026-11-06, U11): every assessment of the revision reads the members' standing answers, each
    # bound to the question it answered (engine._MemberAnswers) - whatever made this stage: the answer's own recompute
    # (recompute_after_answers), a context save, a peer phase, a Resume or a release's refresh.
    member = member_answers_of(revision)
    data, result = _bounded(
        _assess_child, revision.text, service_date, tuple(PageSpan(**p) for p in revision.pages),
        context_facts(context), normalized, reference, provider_status, revision.extraction_status,
        tuple(revision.messages), second_normalized, dict(second.scope) if second is not None else None, inputs,
        confirmed, member, seconds=settings.JOB_DEADLINE_SECONDS['assess'], memory_bytes=settings.ASSESS_MEMORY_BYTES)
    routing_run = _record_routing(revision, data, service_date)
    retrieval = _retrieval(result, service_date, reference, provider_codes)  # a decidable code's only (r7, r8, r9)
    records = {record['name']: record for _, record in read}
    if names and mode != AGAIN:  # HARNESS.md 12.3: assess #1 and #2 record every frozen phase-1 output they read
        frozen = _frozen(revision, run, records)
        for record in records.values():
            record['frozen'] = frozen
    try:
        assessment = review.persist_assessment(
            encounter=encounter, revision=revision, context=context, routing_run=routing_run, provider_run=run,
            result=result, second_run=second, retrieval=retrieval,
            participants=[records.get(name) or not_configured_record(name) for name in participants.PARTICIPANTS])
    except ValueError as exc:
        raise StageFailure(f'The assessment was not recorded: {exc}') from exc
    # The bounded second review is never queued here: a workspace owner or reviewer asks for it
    # (request_second_review; owner decision 2026-10-27, narrow install-first).
    out = {'assessment': str(assessment.pk), 'provider_status': provider_status}
    if second is not None:
        out['second_review'] = str(second.pk)
    if names and mode == FIRST and owed_peer_stages(assessment):
        # HARNESS.md 12.1: assess #1 queues the first owed peer stage when a configured participant's first reading was
        # read; otherwise it is the final assessment. Nothing is sent while a member date conflict holds the encounter.
        queued = _queue_peers(job, assessment, upgrade=_chain_upgrade(job))
        out['peer_review'] = queued.kind
    return out


# --- the bounded second review (ARCHITECTURE 5.11) ------------------------------------------------------------------

SECOND_REVIEW_REASONS = ('no_proposal', 'not_covered')
SECOND_REVIEW_MAX_CHARS = 20_000  # a longer excerpt is not sent (a second review is about one report, not a chart)
# The states of a second review that conclusively never reached the provider, when its run says sent=False: recorded not
# sent by the adapter (only while the request provably has not left), where its request could not be built, or where the
# stale sweep (or an undo's close) settled a reservation that never reached the send; cancelled by a Stop before sending.
# One whose outcome is unknown stays 'unknown', sent or not.
NEVER_SENT_STATES = (models.ProviderRun.NOT_SENT, models.ProviderRun.CANCELLED)
SECOND_REVIEW_EARLIER_CONTEXT = ('This document was read under earlier context rules: save a change to the encounter '
                                 'context (or add an addendum) so it is read under the current ones, then ask.')
# FINAL 6.7-6.8: on a gemini context the follow-up re-reads what the assessment it follows read and queues nothing, so
# the ask is taken only on its chain's final assessment (review.is_final). An assess #1 whose peer stages were stopped,
# expired or swept is resumed first: its follow-up owed the same peer stages and nothing queued them, so Resume was no
# longer offered, no answer was recomputed and no decision could be recorded (S10 review round 2, finding 1).
SECOND_REVIEW_NOT_FINAL = ('The peer reviews of this document have not finished: resume processing to finish them, '
                           'then ask for a second review.')


def _second_review_items(assessment):
    """(the unresolved documented services a second review may ask about, (start, end) of the text that documents
    them or None)."""
    # as the review leaves them: an item a code the reviewer reinstated accounts for is not asked about again
    # (refutation P2FR, EUS-SECOND: the second review was offered for an EUS its reinstated, approved code accounts for)
    completeness = review.reviewed_completeness(assessment) or {}
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


def _answer_of(run):
    """What a primary run's outcome is: the provider's answer (the same response) to the same request."""
    return (run.provider, run.adapter_version, run.request_sha256, run.response_sha256)


def _second_run_for(revision, run, *, any_outcome=False):
    """The second review that succeeded on this revision and date for the primary answer ``run`` carries: made for
    ``run`` itself or for any run carrying the same answer to the same request - the retained run it reuses, or another
    run reusing that same retained run (refutation r1, sends-2 / context-2: after a member date conflict was cleared, or
    a date changed and changed back, the reused primary never found the paid second review, so its code disappeared from
    the decision set and another could not be asked for; ec5: also when that second review had been made for a primary
    that was itself a reuse, as when the same report is uploaded twice in a workspace). ``any_outcome``: the newest
    one made for that answer, whatever its outcome (second_review_status names it for the page)."""
    found = _second_runs_for(revision, run, any_outcome=any_outcome)
    return found[0] if found else None


def _second_runs_for(revision, run, *, any_outcome=False):
    """Every second review _second_run_for matches for the answer ``run`` carries (on this revision and date), newest
    first: a reconciled unknown one releases another ask, so an older one can stand behind a newer one (refutation P2FR,
    ROLLBACK 0: a retry that failed hid an older second review whose outcome is unknown)."""
    if run is None or run.state != models.ProviderRun.SUCCEEDED or run.purpose != models.ProviderRun.PRIMARY:
        return []
    seconds = models.ProviderRun.objects.filter(revision=revision, purpose=models.ProviderRun.SECOND_REVIEW,
                                                service_date=run.service_date)
    if not any_outcome:
        seconds = seconds.filter(state=models.ProviderRun.SUCCEEDED)
    seconds = list(seconds.order_by('-created_at'))
    made_for = set()
    for second in seconds:
        try:
            made_for.add(uuid.UUID(str((second.scope or {}).get('primary_run'))))
        except ValueError:
            continue
    answers = {str(primary.pk): _answer_of(primary) for primary in models.ProviderRun.objects.filter(
        pk__in=made_for, revision=revision, purpose=models.ProviderRun.PRIMARY, state=models.ProviderRun.SUCCEEDED)}
    return [second for second in seconds
            if answers.get(str((second.scope or {}).get('primary_run'))) == _answer_of(run)]


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


# request_second_review's refusal of an ask whose key is used (_second_review_key): its stage waits or runs, or was
# stopped, expired or swept before it ran (Resume runs it once), or failed before it recorded a run.
SECOND_REVIEW_ASKED = 'A second review was already requested for this assessment.'


def _second_review_key(revision, assessment):
    """The idempotency key of the ask request_second_review queues for ``assessment``: keyed by the assessment and by
    how many second reviews of this revision and date conclusively never reached the provider - each releases another
    ask (_second_review_bounds), which the key of the ask it answered must not refuse. The count only grows (runs are
    never removed, and those states are final), and it keeps the key as short as a Resume's suffixes need
    (Job.idempotency_key holds 200 characters)."""
    released = models.ProviderRun.objects.filter(
        revision=revision, purpose=models.ProviderRun.SECOND_REVIEW,
        service_date=assessment.provider_run.service_date, state__in=NEVER_SENT_STATES, sent=False).count()
    return f'review2:{revision.pk}:{assessment.pk}' + (f':after-unsent:{released}' if released else '')


def _second_review_blocker(encounter, revision, context, assessment):
    """Why the one bounded second review cannot be asked for now, or '' when it can (5.11): the one predicate the API
    accepts an ask by, so the encounter view's offer, the review queue's 'second_review' reason and POST second-review
    never disagree. The bounds first (_second_review_bounds, whose reasons stand as they were), then the ask itself:
    request_second_review queues one stage per key, so once this assessment's key is used every ask is refused (fix
    round gi2, truth-1: the queue said "Second review available" for an encounter whose ask the server refused - its
    stage stopped, expired or swept before it ran, or failed before it recorded a run - because this said '' there)."""
    reason = _second_review_bounds(encounter, revision, context, assessment)
    if reason or not models.Job.objects.filter(idempotency_key=_second_review_key(revision, assessment)).exists():
        return reason
    return SECOND_REVIEW_ASKED


def _second_review_bounds(encounter, revision, context, assessment):
    """Why a bound stands against the one bounded second review, or '' when none does (5.11). The bounds are the ones the
    automatic second review kept (interpretations 10, 19, 22): once per revision and service date whatever its outcome
    - only a reconciled unknown one, or one that conclusively never reached the provider (NEVER_SENT_STATES, not sent),
    releases another ask - only for the current assessment of a usable primary response read under the current context
    rules - on a gemini context, only its chain's final assessment (SECOND_REVIEW_NOT_FINAL: the follow-up queues
    nothing) -, only with a known, unconflicted service date, never while a request has an unknown outcome.
    stage_review2 checks them again when it runs. Cheap checks first: the encounter view reads this on every refresh."""
    if busy(encounter):
        return 'Wait for processing to finish (or stop it) before asking for a second review.'
    if (assessment is None or revision is None or context is None or assessment.revision_id != revision.pk
            or assessment.context_id != context.pk):
        return 'There is no current assessment to review again.'
    if not interpretation.is_new_context(context) and not _legacy_reading_allowed():
        # FINAL 6.8 and 9: stage_review2 sends nothing on a context that is not a gemini context (it ends cancelled), so
        # the offer never accepts an ask the stage then refuses; a save or an addendum has the document read again
        return SECOND_REVIEW_EARLIER_CONTEXT
    if context.version in EARLIER_CONTEXT_VERSIONS:
        # Repair gi2 (eus2 F3): stage_review2 sends nothing for a context an earlier version recorded, so the offer
        # never accepts an ask the stage then skips (after an install that bumped the context version, the ask was
        # accepted, nothing was sent, the button came back and a second press was refused).
        return SECOND_REVIEW_EARLIER_CONTEXT
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
    # Repair gi2 (eus2 L1): one that conclusively never reached the provider - not sent, or cancelled before sending -
    # used up the bound, so it could never be asked for again but by a new, paid primary request (an addendum).
    if (earlier.exclude(state=models.ProviderRun.UNKNOWN, reconciled_at__isnull=False)
            .exclude(state__in=NEVER_SENT_STATES, sent=False).exists()):
        return 'A second review was already requested for this document and date.'
    if _unreconciled_unknown(encounter):
        return 'A previous request has an unknown outcome; reconcile it before asking again.'
    if interpretation.is_new_context(context) and not review.is_final(assessment):
        # FINAL 6.7-6.8: Resume finishes the peer chain, and the ask is taken on its final. Asked after the bounds a
        # finished chain still meets (the items, the date, one per revision and date, an unknown outcome to
        # reconcile first) and before the request is built, since one that cannot be built accepts the ask
        return SECOND_REVIEW_NOT_FINAL
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
    if (_failed_before(encounter, provider, request) is not None
            and _retained_second_review(encounter, provider, request) is None):
        # refutation p1, sends-1: the once-per-revision bound alone let an addendum re-offer the identical request.
        # Only where no answer to it is retained: one is reused and nothing is sent, as stage_review2 does - reuse,
        # then the unknown-outcome block, then this (round 7c8 skeptic: a reuse is not a send, 5.4).
        return ('The text that documents the unresolved services is a request already sent for this document that '
                'failed, and an identical request is never sent again.')
    return ''


def second_review_status(encounter):
    """What the encounter view shows about the bounded second review: whether one can be asked for now, why not, the
    unresolved items it would ask about, and ``run``: the second review made for the answer the current assessment
    (the one the view shows, on its own revision) reads, whatever its outcome (None when none was), so the page states
    the outcome of one whose response was not read
    or not used, never that no code was proposed (skeptic of refutation 7c8 reports-5: an unknown, failed or refused
    second review left the panel saying "No CPT codes were proposed for this document")."""
    revision, context, assessment = (encounter.current_revision, encounter.current_context,
                                     encounter.current_assessment)
    items = _second_review_items(assessment)[0] if assessment is not None else []
    reason = _second_review_blocker(encounter, revision, context, assessment) if items else ''
    # Made for the answer the SHOWN assessment reads, on that assessment's own revision: while a newer revision is not
    # assessed yet (an addendum, then Stop, or a predict an unknown outcome blocks) the page still shows this one, so it
    # still states its second review's outcome (refutation p2, reports2:1: naming a run only for an assessment of the
    # current revision left the panel saying "No CPT codes were proposed" beside the unknown-outcome reconcile card).
    made = (_second_run_for(assessment.revision, assessment.provider_run, any_outcome=True)
            if assessment is not None else None)
    return {'available': bool(items) and not reason, 'reason': reason,
            'items': [item.get('label', '') for item in items][:8], 'run': str(made.pk) if made is not None else None}


def request_second_review(encounter, user):
    """Queue the ONE bounded second review for the current assessment, asked for by a workspace owner or reviewer
    (owner decision 2026-10-27: never queued by an assessment). Refused with the reason when a bound stands.

    The stage is keyed by _second_review_key, and _second_review_blocker refuses an ask whose key is used, so the offer
    and the ask read one predicate. Two asks at once still queue one stage (the row lock and the busy check), and a
    stage stopped before it ran recorded no run, so its key stands and Resume runs it."""
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
                      provider_run=assessment.provider_run, key=_second_review_key(revision, assessment),
                      requested_by=user)
        if job.state != Job.QUEUED:
            raise Refused(SECOND_REVIEW_ASKED)
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
    _refuse_legacy_context(job)  # FINAL 6.8 and 9: nothing is sent on a context that is not a gemini context
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
                key=_assess_key(f'assess:{context.pk}:{primary.pk}:review2:{run.pk}', revision),
                requested_by=job.requested_by)

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
    prior = _retained_second_review(encounter, provider, request)
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
    if _failed_before(encounter, provider, request) is not None:
        # Refutation p1, sends-1: an addendum that left the excerpt as it was made a new revision, whose own bound let
        # the identical FAILED request be sent again. Nothing changed, so the assessment stands as it is.
        return {'skipped': 'the second review would repeat a request sent before for this document that failed; '
                           'nothing was sent'}
    _live_gate(job, provider, revision, encounter)
    run = _send(job, provider, request, service_date=service_date, purpose=models.ProviderRun.SECOND_REVIEW,
                scope=scope)
    next_assess(run)
    return {'second_review': run.state, 'run': str(run.pk)}


STAGES = {Job.EXTRACT: stage_extract, Job.ANALYZE: stage_analyze, Job.PREDICT: stage_predict, Job.ASSESS: stage_assess,
          Job.REVIEW2: stage_review2, Job.ASTRA: stage_participant, Job.FABLE: stage_participant,
          Job.ASTRA_PEER: stage_peer, Job.FABLE_PEER: stage_peer, INTERPRET: stage_interpret}
# The stages that send, and the purpose of the runs they record (the stale sweep settles them by those runs).
SENDING_PURPOSES = {Job.PREDICT: models.ProviderRun.PRIMARY, Job.REVIEW2: models.ProviderRun.SECOND_REVIEW,
                    **{kind: models.ProviderRun.INDEPENDENT for kind in Job.PARTICIPANT_KINDS},
                    **{kind: models.ProviderRun.PEER_REVIEW for kind in Job.PEER_KINDS},
                    INTERPRET: INTERPRETATION}


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


def _new_path_stage(job) -> bool:
    """FINAL 10.3: whether ``job`` is new-path work - an interpret stage, an analyze stage of the derive-only shape, or a
    stage whose context is a gemini context - which runs wholly under a new_path sentinel scope (run_job)."""
    if job.kind == INTERPRET:
        return True
    if job.kind == Job.ANALYZE:
        return _analyze_inventory_id(job) is not None
    return job.context_id is not None and interpretation.is_new_context(job.context)


def _stage_scope(job):
    """The sentinel scope a stage runs in (FINAL 10.2-10.3): new_path for new-path work - the sentinel installed and the
    denied caches cleared as it opens, every denied execution counted against it, its forked children's included, and
    every new-path write gated on it - and none for the legacy stages, which keep running as before."""
    if _new_path_stage(job):
        return sentinel.scope(sentinel.NEW_PATH, entry=f'stage:{job.kind}')
    return contextlib.nullcontext()


def run_job(job):
    if job.state != Job.RUNNING:
        review.refresh_state(job.encounter)
        return job
    handler = STAGES[job.kind]
    try:
        with _stage_scope(job):
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


def may_have_reached_vendor(runs):
    """The runs of ``runs`` (a ProviderRun queryset) whose record shows they may have reached the vendor: a recorded
    exchange in any state but not_sent - a participant's loop records each exchange as it ends - of a run that called a
    vendor at all, its reservation naming the endpoint its adapter calls. A replay calls none (its endpoint is ''): its
    exchanges are recorded 'succeeded' and reached nothing (refutation round 3, sends-4). Corti's runs record no
    exchange. The one rule by which a run left sending is settled as sent, by the stale sweep (mark_stale) and by the
    installer's undo (ops/install.py CLOSE_STAGES, run in the undone revision's image; refutation round 3, sends-3)."""
    from django.db.models import Exists, OuterRef

    return runs.exclude(endpoint='').filter(Exists(models.ProviderExchange.objects.filter(run=OuterRef('pk')).exclude(
        state=models.ProviderRun.NOT_SENT)))


STALE_INTERPRETATION = 'the worker stopped after the interpretation outcome was recorded'


def _stale_interpretation(job, run):
    """(job state, error, result) of an interpret stage its worker left running after ``run`` (its newest finished
    interpretation run) recorded an outcome - settled as the stage would have settled it, sending nothing (FINAL 6.9):
    a SUCCEEDED run (P-6's included) queues 'interpret:...:settled:<run>', the settled path, which finds the inventory
    already read or settles that run itself from its stored bytes (_settled_answer: read, its hold recorded, or its
    refused or cut-off reading failed) and never sends (_settled_path); an unknown outcome stays for the reconcile flow;
    a FAILED run goes through interpretation.holds (a hold pauses, anything else fails the stage); a run kept unsent
    ends as its stage did - paused when it was a pause, failed otherwise."""
    result = {'provider': run.state, 'run': str(run.pk), 'settled': STALE_INTERPRETATION}
    if run.state == models.ProviderRun.SUCCEEDED:
        enqueue(INTERPRET, encounter=job.encounter, revision=job.revision,
                key=_interpret_key(job.revision, f'settled:{run.pk}'), requested_by=job.requested_by)
        return Job.SUCCEEDED, '', result
    if run.state == models.ProviderRun.UNKNOWN:
        _mark_effect(run, interpretation_holds.UNKNOWN)
        return Job.SUCCEEDED, '', result
    if run.state == models.ProviderRun.FAILED:
        outcome, hold = interpretation_holds.settle(run)
        _mark_effect(run, outcome.effect)
        if outcome.effect == interpretation_holds.HOLD and hold is not None:
            return Job.CANCELLED, interpretation_holds.PAUSED_MESSAGE, result
        return Job.FAILED, f'{INTERPRET_FAILED_MESSAGE} {outcome.why}'.strip(), result
    if (run.scope or {}).get('held'):
        return Job.CANCELLED, interpretation_holds.PAUSED_MESSAGE, result
    return Job.FAILED, run.error or INTERPRET_NOT_SENT_MESSAGE, result


def mark_stale():
    """Settle jobs a dead worker left 'running'. A send in flight becomes UNKNOWN, never resent."""
    cutoff = timezone.now() - timedelta(seconds=settings.STALE_RUNNING_SECONDS)
    for job in Job.objects.filter(state=Job.RUNNING, started_at__lt=cutoff):
        with transaction.atomic():
            # A predict whose run had already FINISHED when the worker died (its outcome recorded, the assess not
            # yet queued) is settled by that run, exactly as the stage would have settled it, so a Resume can
            # never re-send an identical request that already failed. Read before reserved runs are settled below.
            finished = None
            sends = job.kind in SENDING_PURPOSES  # a harness participant's stage sends too (HARNESS.md 2)
            if job.kind == INTERPRET:
                # ADJUDICATION P-6: an interpretation its dead worker left sending, whose one exchange was recorded
                # answered (HTTP 200, a sha256 that checks), is settled SUCCEEDED from that exchange - nothing is sent
                for run in models.ProviderRun.objects.filter(
                        revision=job.revision, created_at__gte=job.started_at, state=models.ProviderRun.SENDING,
                        provider=interpretation.PROVIDER, purpose=INTERPRETATION):
                    _settle_from_exchange(run)
            # FINAL 6.9: an interpret stage carries no context, and its finished run is the interpreter's
            if sends and (job.context_id or job.kind == INTERPRET):
                runs = models.ProviderRun.objects.filter(
                    revision=job.revision, created_at__gte=job.started_at, purpose=SENDING_PURPOSES[job.kind],
                    state__in=(models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED, models.ProviderRun.UNKNOWN,
                               models.ProviderRun.NOT_SENT))
                # a reservation settled unsent (_settle_reservation; refutation r2, L5-3) never reached the send: no
                # outcome of the stage, which still owes the attempt it reserved, as a reservation settled below does
                # (the shape _run_in_use and _newest_finished leave out)
                from django.db.models import Q

                runs = runs.exclude(Q(state=models.ProviderRun.NOT_SENT) & Q(started_at__isnull=True)
                                    & ~Q(request_sha256=''))
                if job.kind in Job.PARTICIPANT_KINDS:
                    runs = runs.filter(provider=job.kind)  # its own run: both participants' runs are 'independent'
                elif job.kind in Job.PEER_KINDS:
                    runs = runs.filter(provider=PEER_OF[job.kind])  # and both peer reviews are 'peer_review'
                elif job.kind == INTERPRET:
                    runs = runs.filter(provider=interpretation.PROVIDER)
                finished = runs.order_by('-created_at').first()
            sending = models.ProviderRun.objects.filter(revision=job.revision, state=models.ProviderRun.SENDING)
            reserved = models.ProviderRun.objects.filter(revision=job.revision, state=models.ProviderRun.RESERVED)
            unknown = sends and sending.exists()
            reached = set(may_have_reached_vendor(sending).values_list('pk', flat=True))
            for run in sending:
                run.state, run.error, run.finished_at = (models.ProviderRun.UNKNOWN,
                                                         'The worker stopped while the request was in flight.',
                                                         timezone.now())
                # a participant's loop records each exchange as it ends: one of them that may have reached the vendor
                # means the run was sent (refutation round 2, sends-r2-4; Corti's runs record no exchange) - by the rule
                # the installer's undo settles a run with too, and never for a replay (refutation round 3, sends-3/-4)
                run.sent = run.sent or run.pk in reached
                run.save(update_fields=['state', 'error', 'finished_at', 'sent'])
            for run in reserved:
                run.state, run.error, run.finished_at = (models.ProviderRun.NOT_SENT,
                                                         'The worker stopped before sending.', timezone.now())
                run.save(update_fields=['state', 'error', 'finished_at'])
            if finished is not None and not unknown and job.kind == INTERPRET:
                # FINAL 6.9: settled as the stage would have settled it, sending nothing (_stale_interpretation)
                job.state, job.error, job.result = _stale_interpretation(job, finished)
            elif finished is not None and not unknown:
                # the stage the settled one would have queued, under the key it would have used
                if job.kind == Job.PREDICT and (finished.scope or {}).get('held'):
                    # a member date conflict's hold: no participant chain, as stage_predict queues none
                    key = _assess_key(f'assess:{job.context_id}:{finished.pk}', job.revision)
                    enqueue(Job.ASSESS, encounter=job.encounter, revision=job.revision, context=job.context,
                            provider_run=finished, key=key, requested_by=job.requested_by)
                elif job.kind == Job.PREDICT:
                    _after_predict(job.encounter, job.revision, job.context, finished,
                                   key=f'assess:{job.context_id}:{finished.pk}', origin=str(job.pk),
                                   requested_by=job.requested_by,
                                   upgrade=job.idempotency_key == _upgrade_predict_key(job.context))
                elif job.kind == Job.REVIEW2:
                    primary = job.provider_run
                    key = f'assess:{job.context_id}:{primary.pk}:review2:{finished.pk}'
                    enqueue(Job.ASSESS, encounter=job.encounter, revision=job.revision, context=job.context,
                            provider_run=primary, key=_assess_key(key, job.revision), requested_by=job.requested_by)
                elif job.kind in Job.PEER_KINDS:
                    # the next owed peer stage or assess #2, for the assess #1 its key names while it is the newest
                    first = _first_assessment(job)
                    if first is not None:
                        _queue_peers(job, first, after=PEER_OF[job.kind],
                                     upgrade=job.idempotency_key.endswith(UPGRADE_MARK))
                else:
                    _queue_after_participant(job)
                job.state, job.error = Job.SUCCEEDED, ''
                settled = 'the worker stopped after the provider outcome was recorded'
                job.result = ({'participant': job.kind, 'state': finished.state, 'run': str(finished.pk),
                               'settled': settled} if job.kind in Job.PARTICIPANT_KINDS else
                              {'peer': job.kind, 'state': finished.state, 'run': str(finished.pk),
                               'settled': settled} if job.kind in Job.PEER_KINDS else
                              {'provider': finished.state, 'run': str(finished.pk), 'settled': settled})
            else:
                # A send in flight is unknown (reconcile it); any other stage recorded nothing it would not redo,
                # so it is cancelled and can be resumed rather than stranding the encounter.
                job.state = Job.UNKNOWN if unknown else Job.CANCELLED
                job.error = ('The worker stopped while this stage was running.' if unknown else
                             'The worker stopped while this stage was running; resume to run it again.')
            job.finished_at = timezone.now()
            job.save(update_fields=['state', 'error', 'result', 'finished_at'])
        review.refresh_state(job.encounter)
    # Decision (k): a run left 'sending' by a stage that no longer runs - its outcome never recorded, the job failed or
    # ended - is settled unknown like a dead worker's, so its reconciliation can release one new attempt. Until then
    # every send door blocks on it (review._orphaned_sending). Its own stage, were it running, started before it.
    # ADJUDICATION P-6 comes first (refutation of S09, finding 3): an interpretation run whose one exchange was recorded
    # answered (HTTP 200, a sha256 that checks) is settled SUCCEEDED from that exchange instead - the answer it holds,
    # never an outcome left for a member to reconcile - and, on the encounter's current revision, its settled path is
    # queued ('interpret:...:settled:<run>'), which reads it, records its hold or fails its reading, and sends nothing.
    for run in models.ProviderRun.objects.filter(state=models.ProviderRun.SENDING, created_at__lt=cutoff):
        if Job.objects.filter(encounter_id=run.encounter_id, state=Job.RUNNING, started_at__lte=run.created_at).exists():
            continue
        with transaction.atomic():
            if _settle_from_exchange(run):
                settled, encounter = True, run.encounter
                if encounter.current_revision_id == run.revision_id:
                    enqueue(INTERPRET, encounter=encounter, revision=run.revision,
                            key=_interpret_key(run.revision, f'settled:{run.pk}'), requested_by=run.requested_by)
            else:
                reached = may_have_reached_vendor(models.ProviderRun.objects.filter(pk=run.pk)).exists()
                settled = models.ProviderRun.objects.filter(pk=run.pk, state=models.ProviderRun.SENDING).update(
                    state=models.ProviderRun.UNKNOWN, error=ORPHANED_SENDING_MESSAGE, finished_at=timezone.now(),
                    sent=run.sent or reached)
        if settled:
            review.refresh_state(run.encounter)
    # Refutation r2, L5-3: a reservation left by a stage that no longer runs - the stage failed before sending it, and
    # its own settling (_settle_reservation) failed too - never reached the provider. It is settled not sent, as a dead
    # worker's reservation is above (no start recorded: the attempt it reserved is still owed), so nothing reads it as
    # an outcome to confirm that nothing could ever settle. Its own stage, were it running, started before it.
    for run in models.ProviderRun.objects.filter(state=models.ProviderRun.RESERVED, created_at__lt=cutoff):
        if Job.objects.filter(encounter_id=run.encounter_id, state=Job.RUNNING,
                              started_at__lte=run.created_at).exists():
            continue
        settled = models.ProviderRun.objects.filter(pk=run.pk, state=models.ProviderRun.RESERVED).update(
            state=models.ProviderRun.NOT_SENT, sent=False, error=ORPHANED_RESERVATION_MESSAGE,
            finished_at=timezone.now())
        if settled:
            review.refresh_state(run.encounter)


def remove_stale_ingest_dirs():
    """A worker killed mid-extraction can leave its child's work directory (it may hold a PDF copy)."""
    import shutil
    import tempfile
    from pathlib import Path

    for path in Path(tempfile.gettempdir()).glob('cpt-ingest-*'):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)


# Decision (j) (2026-11-03): a dead worker never animates. The worker process beats every HEARTBEAT_SECONDS from a thread
# of its own (so a long stage never reads as a dead worker); the progress panel reads a beat older than
# WORKER_SILENT_SECONDS, while a document waits on processing, as processing paused.
HEARTBEAT_SECONDS = 30
WORKER_SILENT_SECONDS = 120
WORKER_NAME = 'worker'


def beat(*, name=WORKER_NAME, now=None):
    """Record one heartbeat of this worker process (models.WorkerBeat). Never raises: a failed beat is logged, and a
    worker whose beats keep failing reads as not responding, which is what it is to a member."""
    import os

    try:
        models.WorkerBeat.objects.update_or_create(name=name, defaults={
            'beat_at': now or timezone.now(), 'revision': str(settings.RELEASE_SHA)[:64], 'pid': os.getpid()})
    except Exception:  # noqa: BLE001 - logged; the next beat tries again
        log.exception('the worker heartbeat could not be recorded')


def start_heartbeat(should_stop, *, interval=HEARTBEAT_SECONDS):
    """A daemon thread that beats every ``interval`` seconds until ``should_stop()``; its database connection is
    closed when it ends. Returns the thread."""
    import threading

    from django.db import connection as thread_connection

    def loop():
        try:
            while not should_stop():
                beat()
                for _ in range(int(interval * 10)):
                    if should_stop():
                        break
                    time.sleep(0.1)
        finally:
            thread_connection.close()
    thread = threading.Thread(target=loop, name='cpt-studio-heartbeat', daemon=True)
    thread.start()
    return thread


def worker_responding(*, now=None, name=WORKER_NAME):
    """True when the worker beat within WORKER_SILENT_SECONDS, False when its newest beat is older, None when no beat
    was ever recorded (nothing is known, and nothing is claimed)."""
    row = models.WorkerBeat.objects.filter(name=name).first()
    if row is None:
        return None
    return (now or timezone.now()) - row.beat_at <= timedelta(seconds=WORKER_SILENT_SECONDS)


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
        base = last.idempotency_key.split(':resume:', 1)[0]
        readable = last.revision.extraction_status in READABLE
        if readable and (last.kind == INTERPRET or _new_path_owed(
                last.revision, context if last.kind in {Job.PREDICT, Job.ASSESS} else None)):
            # FINAL 6.9 and 9: a revision with no inventory read at the current versions - or a stage on a context that
            # is not a gemini context - is interpreted first, by this explicit act; a stopped or paused interpret runs
            # again under its own key (a retry's or a reconciliation's suffix kept)
            kind, provider_run, context = INTERPRET, None, None
            base = base if last.kind == INTERPRET else _interpret_key(last.revision)
        elif last.kind == Job.ASSESS and context is not None and last.context_id != context.pk:
            kind, provider_run = Job.PREDICT, None  # the context changed while stopped: re-run from predict
        elif last.kind == Job.EXTRACT and last.revision.extraction_status in {models.SourceRevision.OK,
                                                                               models.SourceRevision.PARTIAL}:
            kind, provider_run = Job.ANALYZE, None  # the text was recorded before the stage was cut short
        else:
            kind, provider_run = last.kind, last.provider_run
        clear_stop(encounter)
        # One fresh suffix on the stage's own key, never a chain: each Resume used to append ':resume:<uuid>' (44
        # characters) to the previous Resume's key, so the third or fourth Resume in a row overflowed the 200-character
        # key column (an HTTP 500, nothing recorded; refutation gi2, sends known limit 'third Resume'). Nothing parses
        # the suffix; the stage's own key stays the prefix (_upgrade_predict_key compares the whole key, so a resumed
        # upgrade predict still sends, as before).
        key = f'{base}:resume:{uuid.uuid4()}'
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

    A harness participant's run (refutation round 1, sends-1): when nothing else blocks a send and Corti's run in use
    answers the request the context makes, the participants' chain starts from that run, as a context change that
    keeps the request does - so Corti's request, sent or recorded not sent, is never attempted again behind another
    run's reconciliation, and only the participant released here is sent again. Otherwise a predict, as before: also
    for a context an earlier version recorded, which the predict remakes under the current rules before anything is
    sent (_remade_context), since those rules may hold the encounter where the earlier ones did not.

    The Gemini migration (design/FINAL.md 6.9 and 9): a reconciled interpretation run, or any reconciliation on a
    revision with no inventory read at the current versions, queues the interpret stage
    ('interpret:...:after-reconcile:<run>') and never a predict; that stage settles the run from its recorded exchange
    before it would send (ADJUDICATION P-6).
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
        if (revision is not None and revision.extraction_status in READABLE
                and (run.purpose == INTERPRETATION or _new_path_owed(
                    revision, context if context is not None and context.revision_id == revision.pk else None))):
            # FINAL 6.9 and 9: a reconciled interpretation run queues the interpret stage, never a predict - which,
            # before it would send, settles the run from its recorded exchange when it holds an answer (P-6) - and so
            # does any reconciliation on a revision with no inventory read at the current versions: its first
            # interpretation is this explicit act's
            enqueue(INTERPRET, encounter=encounter, revision=revision,
                    key=_interpret_key(revision, f'after-reconcile:{run.pk}'), requested_by=user)
        elif context is not None and revision is not None and context.revision_id == revision.pk:
            corti = _run_in_use(revision)
            if (run.purpose in PARTICIPANT_PURPOSES and participants.configured()
                    and context.version not in EARLIER_CONTEXT_VERSIONS and not _unreconciled_unknown(encounter)
                    and not gi_context.is_member_conflict((context.facts or {}).get('service_date'))
                    and _run_answers(corti, revision, context)):
                _after_predict(encounter, revision, context, corti, key=f'assess:{context.pk}:{corti.pk}',
                               origin=f'reconcile:{run.pk}', requested_by=user)
            else:
                _queue_predict(encounter, revision, context, key=f'predict:{context.pk}:after-reconcile:{run.pk}',
                               requested_by=user)
        # a participant's row names its provider, so the Activity tab words it ("Unknown Astra outcome reconciled")
        audit.record(encounter.workspace, 'provider.reconciled', encounter=encounter, actor=user, run=str(run.pk),
                     **({'provider': run.provider} if run.purpose in PARTICIPANT_PURPOSES else {}))
        review.refresh_state(encounter)
    return True


RETRY_BUSY = 'Wait for processing to finish (or stop it) before asking for the document to be read again.'
RETRY_NOTHING = 'This document has no reading to try again.'
RETRY_READ = 'This document was read; there is no failed reading to try again.'
RETRY_UNKNOWN = 'An earlier request has an unknown outcome; it is reconciled before anything is tried again.'
RETRY_PAUSED = ('Reading documented procedures is paused on this installation; resume processing once it is available '
                'again.')
RETRY_TOO_LONG = ('This document is too long to be read in one piece, so the same request would be cut off again; it is '
                  'not sent again. Shorten it or split it, then upload it again.')
RETRY_UNBUILT = 'This document could not be prepared for reading; upload it again.'


def retry_target(revision):
    """(the attempt a retry of ``revision``'s reading answers, the run it would release or None) - FINAL 11.3 - or
    (None, None) when there is no attempt. The attempt is the revision's newest interpretation run that is not a pause
    (scope.held). The run released is the newest attempt that was SENT and did not succeed - failed, or an answer whose
    reading was refused or cut off (interpretation_effect failed or too_long) - which the failed-before door would
    otherwise hold against the request: the attempt itself, or, for a run that door kept unsent, the attempt it names.
    A request that never left, or an answer still unread, needs no release: the retry tries it again, or reads it again
    with nothing sent."""
    newest = (models.ProviderRun.objects.filter(revision=revision, provider=interpretation.PROVIDER,
                                                purpose=INTERPRETATION).exclude(scope__has_key='held')
              .order_by('-created_at', '-pk').first())
    if newest is None:
        return None, None
    blocking = newest
    if (newest.scope or {}).get('refused') == FAILED_BEFORE:
        blocking = models.ProviderRun.objects.filter(pk=(newest.scope or {}).get('failed'),
                                                     encounter_id=newest.encounter_id).first() or newest
    released = (blocking if blocking.sent and blocking.state in (models.ProviderRun.FAILED, models.ProviderRun.SUCCEEDED)
                and interpretation_effect(blocking) in (interpretation_holds.FAILED, interpretation_holds.TOO_LONG)
                else None)
    return newest, released


def retry_reading(encounter, user, *, override=False):
    """The recorded retry (FINAL 11.3; D11): one more attempt at the current revision's reading. The run the
    failed-before door would hold against it (retry_target) is released for that one attempt - written on its
    reconciled_by, reconciled_at and reconciliation_note (RETRY_RELEASE_NOTE), which the failed-before door and the
    stored-answer door read (released_for_retry) - and 'interpret:...:retry:<run>' is queued, audited
    'interpretation.retry'. Refused (Refused) while a stage runs or an outcome is unknown, when the revision was read or
    was never attempted, while a hold stands (an operator's release and a Resume end that), for a document
    over the size bound or that cannot be prepared, and for an answer cut off at its output limit (C5: the member is
    told the document is too long to be read in one piece) unless ``override`` - an operator's recorded override, which
    the caller (the API's retry-reading door, slice S11) grants only to an operator. Returns the queued job."""
    with transaction.atomic():
        encounter = _locked(encounter)
        if busy(encounter):
            raise Refused(RETRY_BUSY)
        revision = encounter.current_revision
        if revision is None or revision.extraction_status not in READABLE:
            raise Refused(RETRY_NOTHING)
        if _read_inventory(revision) is not None:
            raise Refused(RETRY_READ)
        if _unreconciled_unknown(encounter):
            raise Refused(RETRY_UNKNOWN)
        newest, released = retry_target(revision)
        if newest is None:
            raise Refused(RETRY_NOTHING)
        refused = (newest.scope or {}).get('refused')
        if refused == SIZE:
            raise Refused(RETRY_TOO_LONG)
        if refused == UNBUILT:
            raise Refused(RETRY_UNBUILT)
        if interpretation_holds.is_held():  # every attempt would pause while a hold stands
            raise Refused(RETRY_PAUSED)
        effect = interpretation_effect(released or newest)
        if effect == interpretation_holds.TOO_LONG and not override:
            raise Refused(RETRY_TOO_LONG)
        if released is not None and not released_for_retry(released):
            locked = models.ProviderRun.objects.select_for_update().get(pk=released.pk)
            locked.reconciled_by, locked.reconciled_at = user, timezone.now()
            locked.reconciliation_note = RETRY_RELEASE_NOTE
            locked.save(update_fields=['reconciled_by', 'reconciled_at', 'reconciliation_note'])
        clear_stop(encounter)
        key = _interpret_key(revision, f'retry:{(released or newest).pk}')
        if Job.objects.filter(idempotency_key=key).exists():  # asked again for the same attempt: a stage of its own
            key = f'{key}:resume:{uuid.uuid4()}'
        job = enqueue(INTERPRET, encounter=encounter, revision=revision, key=key, requested_by=user)
        audit.record(encounter.workspace, 'interpretation.retry', encounter=encounter, actor=user,
                     run=str((released or newest).pk), released=released is not None, effect=effect,
                     override=bool(override))
        review.refresh_state(encounter)
    return job


def _run_answers(run, revision, context):
    """Whether ``run`` already answers the request the provider would build for ``context`` now.

    Compared on the request itself (provider, adapter and canonical request hash), never
    on the previous context: the run in use may have been requested for another date.
    Whatever that run's outcome: a setting or billing change that leaves the request
    unchanged re-checks and never re-sends the primary request (ARCHITECTURE 5.4), so a
    failed or not-sent request is never re-sent behind a metadata save - except that a
    save settling a held member date conflict makes a request whose one attempt
    conclusively never reached the provider (change_context, _attempt_owed). The re-check
    may still make the one bounded second review its revision and date have not had (5.11).
    """
    if run is None or not run.request_sha256:
        return False
    try:
        request = _request_for(run, revision, context)
    except ProviderUnavailable:
        return False
    return request is not None and request.canonical_sha256 == run.request_sha256


# gi3 fix round 2 (STATE2-1): an adapter's request is a pure function of the text and the date
# (providers.corti.build_coding_request), so with sending disabled - an install's or an incident's provider-mode switch -
# the request a recorded run answers is still known. A context remade or saved with its request unchanged is then
# re-assessed with the recorded answer, never with none: with none, every proposal of a reviewed encounter was dropped
# and the reviewer's decisions on it invalidated ("99214 is no longer proposed").
_BUILT_ADAPTERS = frozenset(((CortiProvider.name, CortiProvider.adapter_version),
                             (ReplayProvider.name, ReplayProvider.adapter_version)))


def _request_for(run, revision, context):
    """The request ``run``'s provider and adapter would build for ``context`` now: the configured provider's, or, with
    sending disabled, the adapter's own builder for a provider and adapter this revision builds (_BUILT_ADAPTERS). None
    when neither can build it. Nothing is sent either way."""
    provider = get_provider()
    if provider is not None:
        if (provider.name, provider.adapter_version) != (run.provider, run.adapter_version):
            return None
        return provider.build_request(revision.text, context_service_date(context))
    if (run.provider, run.adapter_version) not in _BUILT_ADAPTERS:
        return None
    return build_coding_request(run.provider, run.adapter_version, revision.text, context_service_date(context),
                                settings.PROVIDER_MAX_REQUEST_BYTES)


def _recorded_in_use(revision):
    """gi3 (STATE2-1, as the narrow release's refutation refined it: STATE-N1, STATE-N2): whether the run in use
    (_run_in_use) records a request made for this revision - succeeded, failed or with an outcome still unknown - which
    an assessment with no answer would replace with 'provider not run'. A run that carries no request (none could be
    built) is no such record (ec5 skeptic:1)."""
    run = _run_in_use(revision)
    return run is not None and bool(run.request_sha256)


def _run_in_use(revision):
    """The provider run whose outcome stands for ``revision``: its newest request that finished.

    That is so whether or not an assessment was made with it. A member's Stop during the send, a swept assess or an
    expired one cancels the assess that would have used it, and a Resume would re-assess with it, so a context change
    does the same (round 3, orchestrator:0). A reconciled unknown outcome no longer stands: the member released it for
    one new attempt, which a context change must not consume by re-assessing with it.

    A run the stale-stage sweep settled as not sent because its worker stopped after reserving it is no outcome at
    all: it carries its request but never reached the send (no started_at), so the attempt it reserved still has to
    be made, as a Resume of that predict makes it (round 4, pipeline:2). Neither is a hold (below). Every other
    not-sent run stands: one the provider exchange answered went through the send, one recorded when no request could
    be built carries no request to compare (a save after it re-predicts, and the predict's send door, not this reading,
    keeps a request that failed unsent), and one a predict recorded where that door met a request that FAILED carries
    that request (_not_resent_run).
    """
    from django.db.models import Q

    finished = (models.ProviderRun.SUCCEEDED, models.ProviderRun.FAILED, models.ProviderRun.NOT_SENT,
                models.ProviderRun.UNKNOWN)
    reserved_then_swept = (Q(state=models.ProviderRun.NOT_SENT) & Q(started_at__isnull=True)
                           & ~Q(request_sha256=''))
    # A held run (a member date conflict: scope.held) is a hold, not the outcome of any request: it carries none to
    # compare, so standing as the run in use it let a cleared conflict re-send the byte-identical request that had
    # FAILED before it (ec5 integration, from the REPORTRUNS skeptic; 5.4: never re-sent behind a metadata save). The
    # installed revision (057a7d39) reads a hold, like a second review, as its run in use (it skips neither); what a
    # rollback does about rows only this revision writes is the installer's (refutation p1, migrate-1). Refutation
    # p1's first repair skipped every run without a request the same way; that let a cleared date re-assess past the
    # revision's newest run, rows the installed revision misread after a rollback (round 7c8 skeptic, sk:2), so only
    # the hold is skipped.
    held = Q(state=models.ProviderRun.NOT_SENT) & Q(scope__has_key='held')
    run = (revision.provider_runs.filter(state__in=finished, purpose=models.ProviderRun.PRIMARY)
           .exclude(reserved_then_swept).exclude(held).order_by('-created_at').first())
    if run is None or (run.state == models.ProviderRun.UNKNOWN and run.reconciled_at is not None):
        return None
    return run


def _attempt_owed(encounter, run):
    """Whether ``run`` - the run in use - is a primary attempt that conclusively never reached the provider, so the
    request it carries still has no outcome: the adapter recorded it not sent (it does so only while the coding request
    provably has not left; ARCHITECTURE 5.4), it carries its request, it went through the send door (started_at: a
    reservation the stale sweep settled is never the run in use) and it is no hold, and no attempt of that request in
    this encounter was sent and FAILED (the run a predict records where its send door met such a request carries it and
    stands: _not_resent_run). A run whose outcome is unknown, failed or succeeded is never one."""
    if (run is None or run.purpose != models.ProviderRun.PRIMARY or run.state != models.ProviderRun.NOT_SENT
            or run.sent or not run.request_sha256 or run.started_at is None or 'held' in (run.scope or {})):
        return False
    return not models.ProviderRun.objects.filter(
        encounter=encounter, provider=run.provider, adapter_version=run.adapter_version,
        request_sha256=run.request_sha256, state=models.ProviderRun.FAILED, sent=True).exists()


def _settles_member_conflict(previous, context):
    """Whether a member's save settles the member date conflict the encounter was held on (session interpretation 19):
    the context it replaces, of the same revision, held the service date as a member conflict - so nothing was sent for
    it, and the hold said that correcting or clearing the metadata makes the request for the agreed date - and the new
    one does not."""
    return (previous is not None and previous.revision_id == context.revision_id
            and gi_context.is_member_conflict((previous.facts or {}).get('service_date'))
            and not gi_context.is_member_conflict((context.facts or {}).get('service_date')))


CONTEXT_SAVE = 'context.save'  # a save on an event inventory: its sentinel scope's entry and write gate (FINAL 10.3)
AFTER_SAVE = 'after-save'  # an interpret stage's key mark: a member's context save had the revision read (FINAL 9)
CONTEXT_UNREAD_MESSAGE = ("This document's reading ended without a result and nothing is left to resume, so its "
                          'context cannot be changed and nothing is sent for it. Ask for it to be read again, or '
                          'upload it again.')
CONTEXT_NONE_MESSAGE = ('This document has not been read yet, so it has no context to change. Resume processing to '
                        'have it read.')


class _SaveGateClosed(Exception):
    """A context save the sentinel's write gate refuses (FINAL 10.3), raised inside the save's transaction so nothing of
    it is written; change_context then asks the gate outside that transaction, so the refusal's audit row is written
    after the save's own rollback. The row is kept only when no transaction of the CALLER's is open around
    change_context (api.context): a caller that holds one and lets the refusal propagate (answers.save_details,
    review.confirm_finding) rolls the row back with its own work. The Refused therefore carries the row's data as
    ``trip``, for such a caller to record once it has left its transaction (slice S11; S10 review round 2,
    finding 3)."""

    def __init__(self, scope):
        super().__init__('the sentinel refuses this save')
        self.scope = scope


def change_context(encounter, user, values, *, confirmation=None):
    """Apply member-supplied metadata, snapshot a new context and re-assess.

    Re-assesses with the run already in use only when that run answers exactly the
    request the new context would send - and, for a save that settles a held member
    date conflict, is not a primary attempt that conclusively never reached the
    provider (_attempt_owed: the request the hold deferred is made); otherwise
    re-predicts (an identical retained result is still reused for free by the predict
    stage, and a date the revision was never routed for is routed first).

    ``confirmation``: the FindingConfirmation of a service date a reviewer confirmed (HARNESS.md 11.3, 12.5;
    review.confirm_finding), which enters here as the member's date, exactly as a member's save: its context.changed
    audit row names the confirmation. None for a member's own save, whose row is as before.

    The Gemini migration (design/FINAL.md 6.10, 9 and 16.3-16.4; D8):
    - a revision with an event inventory read at the current versions - the current gemini context's own, else the
      revision's - is saved ON THAT FROZEN INVENTORY (_save_on_inventory): interpretation.facts.derive with the new
      values is recorded as a new gemini-context@1 row bound to it, here under the row lock (pure: no text read for
      meaning, no network, nothing sent to the interpreter), its routing stand-in recorded for a changed effective date,
      under a new_path sentinel scope whose write gate refuses the save (Refused; its trip audited once the save rolled
      back - kept only when no transaction of the caller's is open, and carried on the Refused as ``trip`` for a
      caller that holds one: _SaveGateClosed) when it counted a legacy execution or cannot vouch for itself; then the
      decision is exactly as before (_decide_after_save);
    - any other revision (the legacy reader's, or one never read at the current versions) stores the values and has
      the revision read, its first interpretation, in the worker (_save_before_reading): no context is made here, and
      the current one is returned. Refused when its reading ended failed with nothing to resume
      (CONTEXT_UNREAD_MESSAGE): the recorded retry or a new upload is the way, never a save.
    The legacy flow below them runs only under the test-only legacy chain (_legacy_reading_allowed)."""
    try:
        return _change_context(encounter, user, values, confirmation)
    except _SaveGateClosed as closed:
        # the save's transaction rolled back whole; asked again outside it, the gate records why and refuses (a
        # caller's own transaction, when one is open, still holds that row: the Refused carries it as ``trip``)
        try:
            sentinel.gate(CONTEXT_SAVE, encounter=encounter, actor=user, scope_=closed.scope)
        except sentinel.Tripped as exc:
            refused = Refused(str(exc))
            refused.trip = exc.data  # the audit row's data (sentinel.TRIPPED), as the gate recorded it
            raise refused from None
        raise Refused(sentinel.MESSAGES['unavailable']) from None  # never reached: a refusal never lifts


def _merge_values(encounter, values):
    """The member's values merged into the encounter's (an empty value clears one), and saved."""
    merged = dict(encounter.user_values or {})
    for key, value in values.items():
        if value:
            merged[key] = value
        else:
            merged.pop(key, None)
    encounter.user_values = merged
    encounter.save(update_fields=['user_values', 'updated_at'])


def _saved_inventory(revision, previous):
    """The EventInventory a context save re-derives from (FINAL 6.10, D8): the one the current gemini context of this
    revision names, when it was read at the current versions; else the revision's newest inventory read at them (its
    analyze did not finish, or a legacy context is current); None when there is none - the revision is read first."""
    if (previous is not None and previous.revision_id == revision.pk and interpretation.is_new_context(previous)
            and previous.event_inventory_id):
        own = (models.EventInventory.objects.select_related('provider_run')
               .filter(pk=previous.event_inventory_id, revision=revision, state=models.EventInventory.READ,
                       interpretation_version=interpretation.INTERPRETATION_VERSION,
                       inventory_version=interpretation.INVENTORY_VERSION).first())
        if own is not None:
            return own
    return _read_inventory(revision)


def _save_on_inventory(encounter, user, revision, previous, inventory, values, confirmation):
    """A context save on ``inventory``, frozen (change_context; FINAL 6.10): the values stored, the gemini-context@1 row
    derived from the inventory with them (the same derivation analyze records), its stand-in for its effective date when
    none is stored yet, the context made current, the audit row, and the decision exactly as before. All of it in one
    new_path sentinel scope; the gate is asked after the derivation and before the first row is written (_SaveGateClosed
    rolls the whole save back). Nothing is read, built or sent for the interpreter. Returns the new context."""
    with sentinel.scope(sentinel.NEW_PATH, entry=CONTEXT_SAVE) as scope:
        _merge_values(encounter, values)
        try:
            stored = _stored_inventory(inventory, revision)
            derived = derived_facts(encounter, inventory, stored)
        except StageFailure as exc:
            raise Refused(str(exc)) from None
        service_date = date.fromisoformat(derived.effective) if derived.effective else None
        data = _stand_in(revision, inventory, stored, service_date)
        if sentinel.refusal(scope) is not None:
            raise _SaveGateClosed(scope)
        context = record_derived_context(encounter, revision, inventory, derived, created_by=user)
        if context_service_date(context) != service_date:  # one date: the context's and its stand-in's
            raise Refused(CONTEXT_DATE_MESSAGE)
        if _events_stand_in(revision, inventory, service_date) is None:
            _record_routing(revision, data, service_date)
        encounter.current_context = context
        encounter.save(update_fields=['current_context', 'updated_at'])
        audit.record(encounter.workspace, 'context.changed', encounter=encounter, actor=user,
                     fields=sorted(values), context=str(context.pk),
                     **({'confirmation': str(confirmation.pk)} if confirmation is not None else {}))
        _decide_after_save(encounter, user, revision, previous, context)
    return context


def _save_before_reading(encounter, user, revision, values, confirmation):
    """A context save on a revision with no event inventory read at the current versions (change_context; FINAL 6.10 and
    9): the values are stored and the revision's interpretation is queued - its first, for a revision the legacy reader
    read - keyed '<interpret key>:after-save:<uuid>', so a stage of its own runs whatever ran before; analyze then
    derives the context with these values. No context is made here: the current one is returned - the legacy reader's,
    or an earlier revision's - never taken for one this save made. Refused when the revision's reading ended FAILED with
    nothing to resume (CONTEXT_UNREAD_MESSAGE: the recorded retry or a new upload is the way), and when the encounter has
    no context at all (CONTEXT_NONE_MESSAGE: a Resume has it read; as before the migration, a document never read to the
    end took no context save)."""
    latest = review.latest_job(encounter)
    if latest is not None and latest.kind == INTERPRET and latest.state == Job.FAILED:
        raise Refused(CONTEXT_UNREAD_MESSAGE)
    if encounter.current_context_id is None:
        raise Refused(CONTEXT_NONE_MESSAGE)
    _merge_values(encounter, values)
    clear_stop(encounter)
    job = enqueue(INTERPRET, encounter=encounter, revision=revision,
                  key=_interpret_key(revision, f'{AFTER_SAVE}:{uuid.uuid4()}'), requested_by=user)
    audit.record(encounter.workspace, 'context.changed', encounter=encounter, actor=user, fields=sorted(values),
                 reading=str(job.pk), **({'confirmation': str(confirmation.pk)} if confirmation is not None else {}))
    return encounter.current_context


def _decide_after_save(encounter, user, revision, previous, context):
    """What a context save queues once its new ``context`` is current (``previous``: the one it replaced), the same for
    every context (FINAL 6.10: "decide exactly as today"):

    Refutation p2 sends2-0 (repair gi2): a save that settles a held member date conflict makes the request the hold
    deferred when the run in use is a primary attempt that conclusively never reached the provider. The settled context
    asks for that attempt's own request, so re-checking with it left the hold's promise ("the request is made for the
    agreed date") unkept and the encounter failed on a request never made. Only that save, once per such save: every
    other save that leaves the request unchanged still re-checks (5.4; round 3 pipeline3:0), and the predict applies
    every send rule (a retained answer reused, the unknown-outcome block, the failed-request door, single flight)."""
    last_run = _run_in_use(revision)
    clear_stop(encounter)
    owed = _settles_member_conflict(previous, context) and _attempt_owed(encounter, last_run)
    if _run_answers(last_run, revision, context) and not owed:
        if _participants_owed(revision, context):
            # A configured participant has no outcome for this revision - its stage was stopped, expired or swept
            # before it recorded one, or it was configured since: the chain runs before the assess, under every
            # send door, so it gets its turn and each participant that answered reuses its answer (HARNESS.md 2).
            _after_predict(encounter, revision, context, last_run, key=f'assess:{context.pk}:{last_run.pk}',
                           origin=f'context:{context.pk}', requested_by=user)
        else:
            # the participants' requests carry no context (HARNESS.md 2): the assess reads their answers as they are
            enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=last_run,
                    key=_assess_key(f'assess:{context.pk}:{last_run.pk}', revision), requested_by=user)
    else:
        _queue_predict(encounter, revision, context, key=f'predict:{context.pk}', requested_by=user)


def _change_context(encounter, user, values, confirmation):
    with transaction.atomic():
        encounter = _locked(encounter)
        revision = encounter.current_revision
        if revision is None or revision.extraction_status not in {models.SourceRevision.OK,
                                                                  models.SourceRevision.PARTIAL}:
            raise Refused('Context can be set once the document text has been extracted.')
        if busy(encounter):
            raise Refused('Wait for processing to finish (or stop it) before changing context.')
        previous = encounter.current_context  # read before this save replaces it (_settles_member_conflict)
        inventory = _saved_inventory(revision, previous)
        if inventory is not None:
            context = _save_on_inventory(encounter, user, revision, previous, inventory, values, confirmation)
            review.refresh_state(encounter)
            return context
        if not _legacy_reading_allowed():
            context = _save_before_reading(encounter, user, revision, values, confirmation)
            review.refresh_state(encounter)
            return context
        # The legacy flow: only the test-only legacy chain reaches it (_legacy_reading_allowed).
        if not models.RoutingRun.objects.filter(revision=revision).exists() and not review.can_resume(encounter):
            # Its analysis overran or failed, so nothing may be sent for it, whatever the context says: the request
            # would answer a document the service could not read (round 5, pipeline:0). A stage that was only stopped
            # - a Stop, the stale-stage sweep or a queue expiry, the rule resume uses - is not refused (round 6
            # pipeline:1): its document is readable, and the predict below routes the new date before anything is
            # sent (round 6 pipeline:0), so the one request is for the member's date and never first for the
            # document's own.
            raise Refused('This document could not be read to the end, so its context cannot be changed and nothing '
                          'is sent for it. Upload it again, shorter or split.')
        _merge_values(encounter, values)
        context = make_context(encounter, revision, created_by=user, seconds=settings.CONTEXT_REQUEST_SECONDS,
                               refusal=Refused)
        encounter.current_context = context
        encounter.save(update_fields=['current_context', 'updated_at'])
        audit.record(encounter.workspace, 'context.changed', encounter=encounter, actor=user,
                     fields=sorted(values), context=str(context.pk),
                     **({'confirmation': str(confirmation.pk)} if confirmation is not None else {}))
        _decide_after_save(encounter, user, revision, previous, context)
        review.refresh_state(encounter)
    return context


REASSESS_BUSY = 'Wait for processing to finish (or stop it) before the encounter is assessed again.'
# Refutation round 2, truth-10: each refusal says what is so - no final assessment of the current revision at all, or
# one made on an earlier context, which no re-assessment of the current context reads (review.CONTEXT_CHANGED).
REASSESS_NONE = 'The current revision has no final assessment to make again.'
REASSESS_CONTEXT = review.CONTEXT_CHANGED
REASSESS_UNFINISHED = ('The current assessment has no finished assessment stage to make it again from; resume '
                       'processing first.')


def reassess_after_confirmation(encounter, user):
    """One assess after a reviewer's confirmation (HARNESS.md 12.1, 12.5): it reads exactly what the final assessment
    read, plus every confirmation of the revision (stage_assess, AGAIN), sends nothing and queues no peer review.
    Refused (Refused: the API's 409) while the encounter is busy, when the current revision has no final assessment
    (REASSESS_NONE), when the final assessment was made on an earlier context (REASSESS_CONTEXT), and when no finished
    assess stage made it.

    Its key is the key of the stage that made the final assessment, ':c:' and 12 hex of the sha256 of the sorted ids of
    every confirmation of the revision, so the same confirmations queue one assess. An earlier re-assessment's ':c:'
    part is left off the final's key first: appended to each other, a run of confirmations would outgrow the
    200-character key column, as chained Resume suffixes once did (refutation gi2), and the new digest already covers
    every confirmation the earlier one did.

    Refutation round 3 (HARNESS.md 12.10, D7): while confirmations are not offered - the release default - it refuses
    first, as review.confirm_finding does, with review.CONFIRMATIONS_NOT_OFFERED; nothing is queued."""
    if not review.confirmations_offered():
        raise Refused(review.CONFIRMATIONS_NOT_OFFERED)
    with transaction.atomic():
        encounter = _locked(encounter)
        if busy(encounter):
            raise Refused(REASSESS_BUSY)
        revision, context, final = encounter.current_revision, encounter.current_context, encounter.current_assessment
        if revision is None or context is None or final is None or final.revision_id != revision.pk:
            raise Refused(REASSESS_NONE)
        if final.context_id != context.pk:
            raise Refused(REASSESS_CONTEXT)
        made = (Job.objects.filter(encounter=encounter, revision=revision, kind=Job.ASSESS, state=Job.SUCCEEDED,
                                   result__assessment=str(final.pk)).order_by('-created_at', '-pk').first())
        if made is None:
            raise Refused(REASSESS_UNFINISHED)
        ids = sorted(str(pk) for pk in models.FindingConfirmation.objects.filter(revision=revision)
                     .values_list('pk', flat=True))
        key = (f'{made.idempotency_key.split(AGAIN_MARK, 1)[0]}{AGAIN_MARK}'
               f'{hashlib.sha256(",".join(ids).encode()).hexdigest()[:12]}')
        clear_stop(encounter)
        job = enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context,
                      provider_run=final.provider_run, key=key, requested_by=user)
        review.refresh_state(encounter)
    return job


# --- completion repair (2026-11-06, U11): a member's answer recomputes the assessment, nothing sent ------------------

ANSWERS_MARK = 'a'  # an answer recompute's AGAIN part: ':c:a' and 11 hex of the revision's answer history


def member_answers_of(revision) -> tuple[MemberAnswerInput, ...]:
    """The standing member answers of ``revision`` as the engine reads them (engine._MemberAnswers): every MemberAnswer
    no MemberAnswerRevocation withdrew, oldest first, each with the question it answered - its fingerprint, '' for an
    answer recorded before answers carried one, which binds by its code, family and fact as the installed release bound
    it (questions.bind; refutation cycle 2, answers W2). () for none, and the engine is then called exactly as
    before."""
    return tuple(MemberAnswerInput(code=answer.code, family=answer.family, fact=answer.fact, value=answer.value,
                                   question=answer.question or '', answer_id=str(answer.pk))
                 for answer in models.MemberAnswer.objects.filter(revision=revision, revocation__isnull=True)
                 .order_by('answered_at', 'pk'))


def answers_digest(revision) -> str:
    """11 hex of the sha256 of ``revision``'s whole answer history - every answer ever recorded and every revocation -
    so each save or withdrawal that changes what stands names a recompute of its own, and no history ever recurs (a
    revocation is permanent): the answers' part of the recompute's key (recompute_after_answers)."""
    answered = sorted(str(pk) for pk in models.MemberAnswer.objects.filter(revision=revision)
                      .values_list('pk', flat=True))
    revoked = sorted(f'r{pk}' for pk in models.MemberAnswerRevocation.objects.filter(answer__revision=revision)
                     .values_list('pk', flat=True))
    return hashlib.sha256(','.join(answered + revoked).encode()).hexdigest()[:11]


def recompute_after_answers(encounter, user):
    """ONE assess after a member's answers changed (a save of "Not documented" or "Cannot confirm", or a withdrawal):
    the AGAIN path - it reads exactly what the final assessment read (the Corti run, every participant run and peer run
    its entries name: _reread), plus the revision's standing answers (stage_assess, member_answers_of) - in the bounded
    assess child; it builds no request, sends nothing and queues no peer review. Called under the encounter's row lock,
    by the save or the withdrawal that changed the answers (answers.save_details, answers.revoke_answer).

    Its key is the key of the stage that made the final assessment with any earlier ':c:' part left off, ':c:a' and the
    revision's answer history (answers_digest), so the assess job's key includes the answers: the same history queues
    one assess, and a changed one is never taken for an assessment already made.

    None, queuing nothing, when there is no final assessment of the current revision and context to make again, when a
    newer assessment of the revision exists (the stage would assess nothing), when its peer phase has not finished
    (is_final), when the context was recorded under earlier context rules (the stage would remake it and could send), or
    when no finished assess stage made it: the answers stand, the review overlay reads them, and the next assessment
    made reads them too."""
    revision, context, final = encounter.current_revision, encounter.current_context, encounter.current_assessment
    if (revision is None or context is None or final is None or final.revision_id != revision.pk
            or final.context_id != context.pk or not review.is_final(final)):
        return None
    if not interpretation.is_new_context(context) and not _legacy_reading_allowed():
        # FINAL 6.10, 9 and 16.2: an answer on a revision the legacy reader read stands on its overlay and is not
        # recomputed - re-assessing would have the document read again, which an answer never does (D7, D8)
        return None
    if context.version in EARLIER_CONTEXT_VERSIONS:
        return None  # the stage would remake the context first and could send (reassess_retained's RETAINED_EARLIER)
    newest = _newest_assessment(revision)
    if newest is None or newest.pk != final.pk:
        return None
    made = (Job.objects.filter(encounter=encounter, revision=revision, kind=Job.ASSESS, state=Job.SUCCEEDED,
                               result__assessment=str(final.pk)).order_by('-created_at', '-pk').first())
    if made is None:
        return None
    key = f'{made.idempotency_key.split(AGAIN_MARK, 1)[0]}{AGAIN_MARK}{ANSWERS_MARK}{answers_digest(revision)}'
    if len(key) > Job._meta.get_field('idempotency_key').max_length:
        return None
    clear_stop(encounter)  # a member's answer asks for processing, as a context save does
    return enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context,
                   provider_run=final.provider_run, key=key, requested_by=user)


# --- P5 FLOW: re-assessment from retained answers, nothing sent (owner directive 2026-11-03, section 6; R6 6.4) ----------

RETAINED_STOPPED = 'A member stopped processing of this document; nothing is queued while the Stop stands.'
RETAINED_NOT_FINAL = ('The current assessment is not its chain\'s final assessment (its peer stages have not finished), '
                      'so there is no final reading to re-read.')
RETAINED_NOT_NEWEST = 'A newer assessment of the current revision exists, so the stage would assess nothing.'
RETAINED_EARLIER = ('The current context was recorded under earlier context rules; re-assessing it would remake the '
                    'context first and could send. Nothing was queued.')
RETAINED_HELD = 'A member date conflict holds this document: there is no retained answer to re-read until it is settled.'
RETAINED_DATE = ('The retained answer was requested for another service date than the current context; it cannot be '
                 're-read for this one.')
RETAINED_PARTICIPANTS = ('The participants configured here are not the ones the final assessment read ({recorded} read, '
                         '{configured} configured): the re-assessment would read other answers than the retained ones.')
RETAINED_BYTES = 'A retained answer no longer matches its recorded sha256 (run {run}); it would not be read.'
RETAINED_KEY = 'The re-assessment key would be longer than the job key column holds.'
RETAINED_TAG = 'Give the release tag as 1 to 80 printable characters with no spaces.'
# FINAL 6.10 (D16): a re-assessment from retained answers re-reads a final made from an event inventory only. A legacy
# final is refused, so no installer phase can ever have a document read again, or cause a paid send.
RETAINED_LEGACY = ('The current assessment was not made from an event inventory: re-assessing it would have the '
                   'document read again, which only a member\'s explicit act does. Nothing was queued.')


def _retained_runs(revision, final):
    """(name, phase-1 run, peer run) of each model participant ``final`` read, by the ids its entries name - exactly what
    an AGAIN-mode assess re-reads (_reread)."""
    out = []
    for name, record in sorted(review.model_records(final).items()):
        if record.get('state') in (None, 'not_configured'):
            continue
        run = _own_run(revision, name, record.get('run'), models.ProviderRun.INDEPENDENT)
        peer = (_own_run(revision, name, record.get('peer_run'), models.ProviderRun.PEER_REVIEW)
                if 'peer_state' in record else None)
        out.append((name, run, peer))
    return out


def reassess_retained(encounter, tag, *, user=None, dry_run=False, expected_participants=None) -> dict:
    """Queue ONE re-assessment of the current revision that re-reads the final assessment's retained answers by id -
    Corti's run and every participant run and peer run its entries name - and sends nothing (R6 6.4): an assess keyed
    '<the final's key>:c:<12 hex of sha256(tag)>', read in AGAIN mode (_assess_mode), which queues no peer stage and
    builds no request. ``tag`` names the release it is made for: one job per tag, so running it again for the same
    release queues nothing (``action`` 'already_queued').

    Refused (Refused, with why) under the row lock, before anything is written: while busy; while a member's Stop
    stands (claim_next would cancel it); with no final assessment of the current revision, one made on another context,
    one that is not its chain's final, or a newer assessment of the revision (the stage would skip); on a context of an
    earlier version (the stage would remake it and could send); while a member date conflict holds it; when the
    retained Corti answer was made for another date; when the participants configured here are not the ones the final
    read (the stage would read others); when a retained answer no longer matches its recorded sha256; and with no
    finished assess stage that made the final. Writes the 'assessment.refreshed' audit row; ``dry_run`` checks the same
    and writes nothing. Returns what was (or would be) queued and what it re-reads.

    ``expected_participants``: the participants the WORKER that makes the re-assessment runs (the installer passes them
    from its app receipt: its one-shot runs with every participant disabled, so this process's own configuration is not
    the worker's); None reads this process's configuration, as a command run in the worker's environment does."""
    if not isinstance(tag, str) or not 0 < len(tag) <= 80 or not tag.isprintable() or any(c.isspace() for c in tag):
        raise Refused(RETAINED_TAG)
    with transaction.atomic():
        encounter = _locked(encounter)
        if busy(encounter):
            raise Refused(REASSESS_BUSY)
        if encounter.stopped_at is not None:
            raise Refused(RETAINED_STOPPED)
        revision, context, final = encounter.current_revision, encounter.current_context, encounter.current_assessment
        if revision is None or context is None or final is None or final.revision_id != revision.pk:
            raise Refused(REASSESS_NONE)
        if final.context_id != context.pk:
            raise Refused(REASSESS_CONTEXT)
        if (not (interpretation.is_new_context(context) and interpretation.is_new_assessment(final))
                and not _legacy_reading_allowed()):
            raise Refused(RETAINED_LEGACY)  # FINAL 6.10: new-path finals only (D16)
        if not review.is_final(final):
            raise Refused(RETAINED_NOT_FINAL)
        if _newest_assessment(revision).pk != final.pk:
            raise Refused(RETAINED_NOT_NEWEST)
        if context.version in EARLIER_CONTEXT_VERSIONS:
            raise Refused(RETAINED_EARLIER)
        corti = final.provider_run
        if peer_review_held(final):
            raise Refused(RETAINED_HELD)
        if corti is not None and run_service_date(corti) != context_service_date(context):
            raise Refused(RETAINED_DATE)
        retained = _retained_runs(revision, final)
        recorded = sorted(name for name, _, _ in retained)
        configured = sorted(participants.configured() if expected_participants is None else expected_participants)
        if recorded != configured:
            raise Refused(RETAINED_PARTICIPANTS.format(recorded=', '.join(recorded) or 'none',
                                                       configured=', '.join(configured) or 'none'))
        for run in [corti] + [item for _, run, peer in retained for item in (run, peer)]:
            if (run is not None and run.state == models.ProviderRun.SUCCEEDED
                    and hashlib.sha256(bytes(run.response_bytes)).hexdigest() != run.response_sha256):
                raise Refused(RETAINED_BYTES.format(run=run.pk))
        made = (Job.objects.filter(encounter=encounter, revision=revision, kind=Job.ASSESS, state=Job.SUCCEEDED,
                                   result__assessment=str(final.pk)).order_by('-created_at', '-pk').first())
        if made is None:
            raise Refused(REASSESS_UNFINISHED)
        key = f'{made.idempotency_key.split(AGAIN_MARK, 1)[0]}{AGAIN_MARK}{_digest(tag)}'
        if len(key) > Job._meta.get_field('idempotency_key').max_length:
            raise Refused(RETAINED_KEY)
        existing = Job.objects.filter(idempotency_key=key).first()
        out = {'encounter': str(encounter.pk), 'tag': tag, 'key': key, 'final_assessment': str(final.pk),
               'context': str(context.pk), 'document_review_run': str(corti.pk) if corti is not None else None,
               'participants': [{'name': name, 'run': str(run.pk) if run is not None else None,
                                 'peer_run': str(peer.pk) if peer is not None else None}
                                for name, run, peer in retained]}
        if existing is not None:
            return {**out, 'action': 'already_queued', 'job': str(existing.pk), 'job_state': existing.state}
        if dry_run:
            return {**out, 'action': 'dry_run', 'job': None, 'job_state': None}
        job = enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context, provider_run=corti, key=key,
                      requested_by=user)
        audit.record(encounter.workspace, 'assessment.refreshed', encounter=encounter, actor=user, job=str(job.pk),
                     tag=tag, assessment=str(final.pk))
        review.refresh_state(encounter)
    return {**out, 'action': 'queued', 'job': str(job.pk), 'job_state': job.state}
