"""One compact, truthful progress panel for a document (owner directive 2026-11-03, section 5; P5 FLOW).

``encounter_progress(encounter, now)`` folds the current revision's jobs into four plain steps - Reading your document,
Identifying procedures, Checking suggested codes, Preparing your results - and one phase: queued, processing,
action_needed, awaiting_detail, completed, partial, failed, stopped or being_confirmed (the page adds 'uploading' while
its own POST is in flight). ``checks_summary(encounter)`` states the three functions - Document review, Independent
checks, Coding validation - as done, running, waiting, unavailable or not run.

Read-only over the rows: the jobs, the runs, the context and the live assessment. Nothing here writes, queues or sends,
so a page that polls it can never cause a paid request (R6 4.5). Every sentence is from the fixed tables below: never a
job's or a run's error text (they name providers and carry technical payloads), never a percentage, a remaining time or
an estimate - the only times it gives are the ones recorded (when each step started and finished) and the server's
clock, from which the page shows the time elapsed. "Taking longer than usual" is a display threshold drawn from the
bound each stage really has where it runs (stage_bound; jobs.QUEUE_DEADLINE for a stage not yet started): a step past
SLOW_SHARE of its bound says what it is waiting for. The wording never implies a limit it enforces: the threshold is
the page's, not a stop.
"""
import uuid

from django.conf import settings
from django.utils import timezone

from . import jobs, models, participants, review
from .gi.context import is_member_conflict

Job = models.Job
ACTIVE = (Job.QUEUED, Job.RUNNING)
READING, IDENTIFYING, CHECKING, PREPARING = 'reading', 'identifying', 'checking', 'preparing'
STEPS = ((READING, 'Reading your document'), (IDENTIFYING, 'Identifying procedures'),
         (CHECKING, 'Checking suggested codes'), (PREPARING, 'Preparing your results'))
STEP_ORDER = tuple(key for key, _ in STEPS)
STEP_STATES = ('done', 'active', 'waiting', 'not_started', 'failed', 'stopped', 'skipped')
PHASES = ('queued', 'processing', 'action_needed', 'awaiting_detail', 'completed', 'partial', 'failed', 'stopped',
          'being_confirmed', 'paused')
DOCUMENT_REVIEW, INDEPENDENT_CHECKS, CODING_VALIDATION = 'Document review', 'Independent checks', 'Coding validation'
SENDING_KINDS = (Job.PREDICT, Job.REVIEW2)
CHECK_KINDS = Job.PARTICIPANT_KINDS + Job.PEER_KINDS
# What a running step is doing, by the kind of its job: the functions, never who performs them.
DETAILS = {Job.PREDICT: DOCUMENT_REVIEW, Job.REVIEW2: DOCUMENT_REVIEW, Job.ASSESS: CODING_VALIDATION,
           **{kind: INDEPENDENT_CHECKS for kind in CHECK_KINDS}}
STEP_OF = {Job.EXTRACT: READING, Job.ANALYZE: IDENTIFYING, **{kind: CHECKING for kind in SENDING_KINDS + CHECK_KINDS}}
JOB_STEP_STATES = {Job.SUCCEEDED: 'done', Job.FAILED: 'failed', Job.CANCELLED: 'stopped',
                   # an outcome still being confirmed did not finish; it is never called a failure of a send that may
                   # have been answered (the being_confirmed phase says what happens next)
                   Job.UNKNOWN: 'stopped'}
SLOW_SHARE = 0.6
FAILED_STATES = ('extraction_failed', 'processing_failed', 'provider_failed', 'provider_not_run')
# A first reading's or a peer review's outcome that leaves the independent checks incomplete (Assessment.participants
# states; 'not_run' there is a configured participant that gave nothing).
INCOMPLETE_OUTCOMES = ('failed', 'refused', 'unknown', 'not_sent', 'blocked', 'not_run')
# What a finished sending stage recorded (Job.result 'provider' for the document review, 'second_review' for its
# re-check, 'state' for a check).
USED_OUTCOMES = ('succeeded', 'reused')
# What a stage that did not do its work recorded (Job.result 'blocked': an unknown outcome stopped it where it would
# send; 'skipped': it had nothing to do for the current document, its context or its assessment) - never done.
BLOCKED, SKIPPED = 'blocked', 'skipped'

MESSAGES = {
    'queued': 'Waiting to start. Documents are processed one at a time, in the order they arrive.',
    'processing': 'Working on your document. This page updates by itself.',
    'action_needed': ('Action needed: the date of service entered for this document differs from the date in the '
                      'document, so nothing has been sent for checking. Choose which date is right to continue.'),
    # refutation round 2 (L7-03's class): the document states no date of service of its own to differ from
    'action_needed_undated': ('Action needed: the date of service for this document is not settled, so nothing has been '
                              'sent for checking. Enter or choose the date under "A few details needed" to continue.'),
    'awaiting_detail': 'A few details are needed. Codes that do not depend on them can be reviewed now.',
    'completed': 'Your results are ready.',
    'partial': 'Your results are ready, but some checks could not be completed. Each code shows what was checked.',
    'being_confirmed': ('We are confirming whether an earlier check completed. Nothing will be sent again until that '
                        'is settled.'),
    # decision (j): the worker stopped beating (jobs.worker_responding is False) while the document waits on it
    'paused': ('Processing is paused: the processing service is not responding right now. Your document is saved, and '
               'this page shows the next step once the service is back.'),
}
TAKING_TURN = 'Waiting its turn: the coding service checks one document at a time.'
# Refutation r2, L5-7: the run has begun - a step of it finished - and its next step waits in the queue (one worker
# takes the oldest queued step of any document), so never "Waiting to start" as if nothing had been done.
NEXT_STEP_QUEUED = ('Waiting for the next step to start. Steps are processed one at a time, in the order they are '
                    'queued.')
# Refutation r2, L5-5: the re-check of what is still open (session decision (n)) was asked for this result and did not
# complete - it failed, was not sent, or its outcome stayed unknown - so the results are the earlier check's.
RECHECK_INCOMPLETE = ('Your results are ready, but checking what is still open again could not be completed. The '
                      'results shown are from the earlier check.')
SLOW_MESSAGES = {
    Job.EXTRACT: ('Reading is taking longer than usual. Long or scanned documents take more time while their text is '
                  'recognised.'),
    Job.ANALYZE: 'Identifying the procedures is taking longer than usual for this document.',
    Job.PREDICT: ('The document review is taking longer than usual: it is still waiting for the coding service to '
                  'answer.'),
    Job.REVIEW2: ('The document review is taking longer than usual: it is still waiting for the coding service to '
                  'answer.'),
    Job.ASSESS: 'Coding validation is taking longer than usual for this document.',
    **{kind: 'The independent checks are taking longer than usual. They are still running.' for kind in CHECK_KINDS},
}
OVERDUE = ('This step is taking much longer than usual. You can leave this page and come back; your document is '
           'saved.')
QUEUE_SLOW = 'Waiting longer than usual to start: other documents are being processed first.'
ERRORS = {
    'extraction_failed': ('We could not read the text of this document. Upload a clearer copy, or paste the text '
                          'instead.', 'new_document'),
    'processing_failed': ('Processing could not be completed for this document. Upload it again; if it is very long, '
                          'shorten or split it first.', 'new_document'),
    'provider_failed': ('The coding service could not complete its review of this document, so no codes were '
                        'suggested. You can upload the document again.', 'new_document'),
    'provider_not_run': ('The coding service is not available right now, so no codes were suggested.', 'none'),
    'unfinished': ('Processing did not finish for this document. Upload it again.', 'new_document'),
}
STOPPED_BY_MEMBER = 'Processing was stopped before it finished.'
STOPPED_BY_SYSTEM = 'Processing paused before it finished.'


def _iso(value):
    return value.isoformat() if value else None


def _end(job):
    """When a finished job finished (a row recorded before every path set finished_at: when it started, else queued)."""
    return job.finished_at or job.started_at or job.created_at


def _recorded(job):
    """What a finished job's own result says its stage did: BLOCKED or SKIPPED when it did not do its work (refutation
    r2, L5-4), else the outcome it recorded - a re-check's under 'second_review' (jobs.stage_review2; refutation r2,
    L5-5), the document review's under 'provider', a check's under 'state' - or None when it records none (an
    extract, an analyze, an assess)."""
    result = job.result if isinstance(job.result, dict) else {}
    if BLOCKED in result:
        return BLOCKED
    if SKIPPED in result:
        return SKIPPED
    if job.kind == Job.REVIEW2:
        # the stale sweep records a re-check it settles under 'provider', as it does a document review's
        return result.get('second_review', result.get('provider'))
    return result.get('provider', result.get('state'))


def _runs(rows):
    """The revision's jobs (oldest first) cut into runs: a job queued while every earlier job of the revision had
    finished starts a run - an upload, an addendum, or a member's save, Resume or reconciliation, each refused while a
    stage is queued or running (R6 4.5) - and every stage a stage queues joins its run (a successor is queued before its
    predecessor's finish is recorded)."""
    runs, pending, latest = [], False, None
    for job in rows:
        if runs and not pending and job.created_at >= latest:
            runs.append([job])
        elif runs:
            runs[-1].append(job)
        else:
            runs.append([job])
        if job.state in ACTIVE:
            pending = True
        else:
            latest = _end(job) if latest is None else max(latest, _end(job))
    return runs


def _held(run, context):
    return ((run is not None and run.state == models.ProviderRun.NOT_SENT
             and (run.scope or {}).get('held') == models.ProviderRun.HELD_MEMBER_DATE_CONFLICT)
            or (context is not None and is_member_conflict((context.facts or {}).get('service_date'))))


def _peers_follow(job, revision):
    """Whether an assess #1 still queued or running is followed by peer reviews: a model participant is configured, no
    member date conflict holds it, and a configured participant's newest first reading succeeded (a reading refused once
    read is known only when the assess runs; the step is then folded again from what it did)."""
    names = participants.configured()
    if not names or _held(job.provider_run, job.context):
        return False
    return any((run := jobs._participant_run(revision, name)) is not None and run.state == models.ProviderRun.SUCCEEDED
               for name in names)


def _assess_step(job, later, revision):
    """An assess is Preparing your results when it makes its chain's final assessment (assess #2, a re-assessment of it,
    or an assess #1 that owes no peer review), else part of Checking suggested codes."""
    if jobs._assess_mode(job) != jobs.FIRST:
        return PREPARING
    if any(item.kind in Job.PEER_KINDS for item in later):
        return CHECKING
    if job.state == Job.SUCCEEDED:
        return PREPARING  # it ran and queued no peer review: it made the final assessment
    return CHECKING if _peers_follow(job, revision) else PREPARING


def _by_step(run, revision):
    out = {}
    for index, job in enumerate(run):
        step = _assess_step(job, run[index + 1:], revision) if job.kind == Job.ASSESS else STEP_OF.get(job.kind)
        if step is not None:
            out.setdefault(step, []).append(job)
    return out


def _skip(job):
    """Whether ``job`` finished without doing its stage's work: it recorded that it had nothing to do for the current
    document, context or assessment (Job.result 'skipped'). A skip is never done by itself (refutation r2, L5-4); what
    its step or function did before stands. An extract whose text was already recorded did read it."""
    return job.state == Job.SUCCEEDED and job.kind != Job.EXTRACT and _recorded(job) == SKIPPED


def _step_outcome(job):
    """The state one finished job gives its step, or None when it did nothing for the step (refutation r3, C-R3-5).

    A job's own state first: failed, or stopped (cancelled, or an outcome still being confirmed: JOB_STEP_STATES). A
    stage that succeeded is read by what it recorded (_recorded): a skip, or a send a member date conflict held, did
    nothing (None). A send an unknown outcome blocked (refutation r2, L5-4), or one whose own outcome is unknown, did
    not finish: it reads as an outcome still being confirmed reads - never done, never a failure. A document review or
    its re-check (SENDING_KINDS) whose request gave the document no answer - it failed, it was not sent, it is a request
    that failed before and is never sent again, or sending is disabled - did not finish its step: the document then
    reads provider_failed or provider_not_run ("Processing could not finish"). A check's own failure blocks only itself
    (HARNESS.md I10): the document's processing goes on and the checks say what was unavailable, so it leaves the step
    done. Anything else is done."""
    if job.state != Job.SUCCEEDED:
        return JOB_STEP_STATES.get(job.state, 'failed')
    if _skip(job):
        return None
    sends = job.kind in SENDING_KINDS + CHECK_KINDS
    if sends and _held(None, job.context):
        return None  # nothing was asked while a member date conflict held the document (the step reads skipped)
    value = _recorded(job)
    if value == BLOCKED or (sends and value == models.ProviderRun.UNKNOWN):
        return 'stopped'
    if job.kind in SENDING_KINDS and value is not None and value not in USED_OUTCOMES:
        return 'failed'
    return 'done'


# How one step reads the outcomes of its stages, the first that any stage gives: an outcome still being confirmed, or a
# stop, outranks a failure (as the being_confirmed and stopped phases outrank failed), and a failure outranks done.
FOLD_ORDER = ('stopped', 'failed', 'done')


def _fold(rows):
    states = [job.state for job in rows]
    if Job.RUNNING in states:
        return 'active'
    if Job.QUEUED in states:
        return 'active' if any(state != Job.QUEUED for state in states) else 'waiting'
    # Refutation r3, C-R3-5: every finished stage of the step is read, never only its last - a document review that did
    # not finish is not made done by the checks that ran after it - and a stage that did nothing leaves the others to
    # say what the step did (every one of them skipped: skipped, refutation r2, L5-4)
    found = {outcome for outcome in map(_step_outcome, rows) if outcome is not None}
    return next((state for state in FOLD_ORDER if state in found), 'skipped')


def _step(key, label, rows, state):
    started = [job.started_at for job in rows if job.started_at]
    finished = _end(rows[-1]) if rows and state in ('done', 'failed', 'stopped') else None
    return {'key': key, 'label': label, 'state': state, 'started_at': _iso(min(started)) if started else None,
            'finished_at': _iso(finished)}


def _steps(runs, revision):
    """The four steps: each step of the current run as its jobs stand; a step before the run's first is the latest
    earlier run's (a re-assessment re-reads what was read and checked before), and so is one every job of which skipped
    its work in this run (a skip did nothing: what the step did before stands, or it reads skipped); one between its
    first and its last was skipped (nothing was sent while a member date conflict held the document); one after its last
    has not started."""
    current = _by_step(runs[-1], revision) if runs else {}
    present = [STEP_ORDER.index(key) for key in current]
    first, last = (min(present), max(present)) if present else (None, None)
    out = []
    for index, (key, label) in enumerate(STEPS):
        mine = current.get(key)
        if mine and not all(_skip(job) for job in mine):
            out.append(_step(key, label, mine, _fold(mine)))
        elif mine or (first is not None and index < first):
            earlier = next((rows for rows in (_by_step(run, revision).get(key) for run in reversed(runs[:-1])) if rows),
                           None)
            out.append(_step(key, label, earlier, _fold(earlier)) if earlier
                       else _step(key, label, [], 'skipped' if mine else 'not_started'))
        elif first is not None and first < index < last:
            out.append(_step(key, label, [], 'skipped'))
        else:
            out.append(_step(key, label, [], 'not_started'))
    if revision is not None and revision.extraction_status == models.SourceRevision.FAILED and out[0]['state'] == 'done':
        out[0]['state'] = 'failed'  # the extract stage finished by recording that no text could be read
    return out


def next_step_queued(steps):
    """Whether the queued phase is a step waiting its turn after a finished one (refutation r2, L5-7): a step the panel
    shows reads done - one of this run, or one it keeps from an earlier run, as a member's save, Resume, detail,
    reconciliation or re-check re-reads what was read and checked before - so it is never "Waiting to start" as if
    nothing had been done. Refutation r3, C-R3-4: the message read only the current run's jobs while the page's title
    read every step, so the two disagreed after a member's re-run. One rule over the steps the server serves: the server
    says NEXT_STEP_QUEUED by it (queued_message), and the page titles the queued phase "Waiting for the next step" by
    the same rule over the same served steps (app.js progressPanel)."""
    return any(step['state'] == 'done' for step in steps)


def queued_message(steps, queued):
    """The message of a queued phase that is not slow: TAKING_TURN for a step its stage put back to wait its turn (a
    retry: Job.result 'requeued'), else NEXT_STEP_QUEUED after a finished step (next_step_queued), else
    MESSAGES['queued']."""
    if queued is not None and (queued.result or {}).get('requeued'):
        return TAKING_TURN
    return NEXT_STEP_QUEUED if next_step_queued(steps) else MESSAGES['queued']


def date_held(encounter):
    """The member date hold (directive 5: "Action needed" at once): the current context of the current revision holds
    the service date as a member's value that conflicts with the document, so nothing is sent until it is settled. Known
    as soon as the analyze stage records that context - a few seconds after an upload, never at the upload itself."""
    context, revision = encounter.current_context, encounter.current_revision
    return (context is not None and revision is not None and context.revision_id == revision.pk
            and is_member_conflict((context.facts or {}).get('service_date')))


def stage_bound(kind):
    """The seconds a running stage of ``kind`` really has - the bound enforced where it runs, never a figure nothing
    reads - from which "taking longer than usual" is drawn (critic C4): the extraction child's timeout
    (EXTRACTION_TIMEOUT_SECONDS, 240 s: jobs._limits), the routing child's (JOB_DEADLINE_SECONDS['analyze'], 60 s), the
    coding service's send deadline (PROVIDER_READ_TIMEOUT_SECONDS + 30, 150 s: jobs._send, for the document review and
    its second review alike), the assess child's (JOB_DEADLINE_SECONDS['assess'], 120 s) and an independent check's
    stage budget (JOB_DEADLINE_SECONDS for its kind, 580 s: jobs._check_loop_time). JOB_DEADLINE_SECONDS' extract,
    predict and review2 entries are read nowhere, so they are never used. None for a kind with no bound."""
    if kind == Job.EXTRACT:
        return settings.EXTRACTION_TIMEOUT_SECONDS
    if kind in SENDING_KINDS:
        return settings.PROVIDER_READ_TIMEOUT_SECONDS + 30
    if kind in (Job.ANALYZE, Job.ASSESS) + CHECK_KINDS:
        return settings.JOB_DEADLINE_SECONDS.get(kind)
    return None


def _slow(active, now):
    """(slow, message): a running step past SLOW_SHARE of its stage's real bound (stage_bound; past the bound itself:
    OVERDUE), or a step queued past SLOW_SHARE of the start-by window; (False, '') otherwise and for a step with no
    bound. A display threshold only: nothing here stops, expires or requeues a stage."""
    if active is None:
        return False, ''
    if active.state == Job.RUNNING and active.started_at is not None:
        bound = stage_bound(active.kind)
        if not bound:
            return False, ''
        elapsed = (now - active.started_at).total_seconds()
        if elapsed > bound:
            return True, OVERDUE
        return (True, SLOW_MESSAGES.get(active.kind, OVERDUE)) if elapsed > SLOW_SHARE * bound else (False, '')
    waited = (now - active.created_at).total_seconds()
    return (True, QUEUE_SLOW) if waited > SLOW_SHARE * jobs.QUEUE_DEADLINE.total_seconds() else (False, '')


def final_assessment(encounter):
    """The live assessment when it was made on the current context and is its chain's final one, else None."""
    assessment = review.live_assessment(encounter)
    if assessment is None or assessment.context_id != encounter.current_context_id or not review.is_final(assessment):
        return None
    return assessment


def recheck_incomplete(assessment):
    """Refutation r2, L5-5: the newest re-check of what is still open (the bounded second review the page offers as
    "Check what is still open again", session decision (n)) made for the answer ``assessment`` reads, when it did not
    complete - failed, not sent, or with an outcome unknown (reconciled or not) - else None (none was asked, or it was
    answered).
    Its own run's outcome (jobs._second_run_for with any outcome, as jobs.second_review_status names it), since an
    assessment reads only a second review that was answered."""
    run = assessment.provider_run
    if run is None or run.state != models.ProviderRun.SUCCEEDED or run.purpose != models.ProviderRun.PRIMARY:
        return None
    second = jobs._second_run_for(assessment.revision, run, any_outcome=True)
    return second if second is not None and second.state != models.ProviderRun.SUCCEEDED else None


def _document_outcome(assessment):
    """'not_run' when no request was made (none, or the member date hold); 'done' when the answer the assessment reads
    was used and a re-check asked for it completed; else 'unavailable' - the request did not succeed, a response was
    refused whole, or the re-check did not complete (refutation r2, L5-5: a failed paid re-check read 'done')."""
    run = assessment.provider_run
    if run is None or _held(run, None):
        return 'not_run'
    if (run.state == models.ProviderRun.SUCCEEDED and review._refused_run(assessment) is None
            and recheck_incomplete(assessment) is None):
        return 'done'
    return 'unavailable'


def _checks_outcome(assessment):
    """'not_run' with no model participant configured for ``assessment`` or while a member date conflict held it (none
    was asked); 'unavailable' when one gave nothing usable (INCOMPLETE_OUTCOMES: its first reading, or the peer review of
    a reading that was read); else 'done'."""
    records = [record for record in review.model_records(assessment).values()
               if record.get('state') not in (None, 'not_configured')]
    if not records or review.peer_review_held(assessment):
        return 'not_run'
    for record in records:
        if record.get('state') in INCOMPLETE_OUTCOMES or (
                record.get('state') == 'read' and record.get('peer_state') in INCOMPLETE_OUTCOMES):
            return 'unavailable'
    return 'done'


def _validation_outcome(assessment):
    from .serializers import _reference_validation  # local import: the one reading of reference validation

    return {'done': 'done', 'failed': 'unavailable', 'not_verified': 'unavailable'}.get(
        _reference_validation(assessment, False)['state'], 'not_run')


def _assessed_outcome(job):
    """Coding validation as the assessment a finished assess made records it (_validation_outcome; Job.result
    'assessment') - never 'done' from the job alone (refutation r2, L5-4: once a later request was blocked, the same
    assess read 'done' through its job and 'not_run' through its assessment). 'unavailable' when that assessment
    cannot be read."""
    pk = (job.result or {}).get('assessment')
    try:
        assessment = models.Assessment.objects.filter(pk=uuid.UUID(str(pk))).first() if pk else None
    except ValueError:
        assessment = None
    return _validation_outcome(assessment) if assessment is not None else 'unavailable'


def _jobs_outcome(rows):
    """A function's finished jobs of one run, as what they recorded (_recorded): 'unavailable' when one gave nothing
    usable - a request blocked by an unknown outcome, or a re-check that did not complete, included (refutation r2,
    L5-4, L5-5) - 'not_run' when every one was disabled or skipped its work, else 'done'; an assess as the assessment it
    made records coding validation."""
    outcomes = []
    for job in rows:
        if _held(job.provider_run if job.kind == Job.ASSESS else None, job.context):
            outcomes.append('not_run')  # nothing was asked while a member date conflict held the document
            continue
        value = _recorded(job)
        if _skip(job):
            outcomes.append('not_run')  # it asked nothing (the callers leave skips out: what came before stands)
        elif job.state != Job.SUCCEEDED or (value is not None and value not in USED_OUTCOMES + ('disabled',)):
            outcomes.append('unavailable')
        elif job.kind == Job.ASSESS:
            outcomes.append(_assessed_outcome(job))
        else:
            outcomes.append('not_run' if value == 'disabled' else 'done')
    if 'unavailable' in outcomes:
        return 'unavailable'
    return 'not_run' if outcomes and all(item == 'not_run' for item in outcomes) else 'done'


def checks_summary(encounter):
    """The three functions as the customer reads them (DESIGN section 7 ``checks``): 'running' or 'waiting' while a job
    of the function is running or queued, or while processing has not reached it yet; once processing is over, what
    the final assessment of the current context records - 'done', 'unavailable' (it ran and gave nothing usable, or a
    reference check could not be completed) or 'not_run' (none was asked, or none could be: no participant configured,
    sending disabled, a member date conflict) - and with no final assessment what the latest run's jobs recorded."""
    revision = encounter.current_revision
    rows = list(encounter.jobs.filter(revision=revision).select_related('provider_run', 'context')
                .order_by('created_at', 'pk')) if revision is not None else []
    runs = _runs(rows)
    current = runs[-1] if runs else []
    busy = any(job.state in ACTIVE for job in rows)
    assessment = final_assessment(encounter) if not busy else None
    configured = bool(participants.configured())
    out = []
    for key, label, kinds, outcome in (('document_review', DOCUMENT_REVIEW, SENDING_KINDS, _document_outcome),
                                       ('independent_checks', INDEPENDENT_CHECKS, CHECK_KINDS, _checks_outcome),
                                       ('coding_validation', CODING_VALIDATION, (Job.ASSESS,), _validation_outcome)):
        mine = [job for job in current if job.kind in kinds]
        if any(job.state == Job.RUNNING for job in mine):
            state = 'running'
        elif any(job.state == Job.QUEUED for job in mine):
            state = 'waiting'
        elif busy:
            state = _busy_state(key, mine, current, revision, configured)
        elif assessment is not None:
            state = outcome(assessment)
        else:
            # a skip did nothing for its function, so the run before it stands (refutation r2, L5-4)
            latest = next((found for found in ([job for job in run if job.kind in kinds and not _skip(job)]
                                               for run in reversed(runs)) if found), [])
            state = _jobs_outcome(latest) if latest else 'not_run'
        out.append({'key': key, 'label': label, 'state': state})
    return out


def _busy_state(key, mine, current, revision, configured):
    """A function with no job running or queued while its document is processing: the final assessment comes last, so
    coding validation waits for it; a function that finished its part of this run says what it recorded, or waits for
    its peer reviews; one this run has not reached waits, and one this run did not ask for keeps what was recorded
    before (a re-assessment re-reads the answers it already has) - as does one whose jobs of this run skipped their work
    (refutation r2, L5-4: a skip asked nothing)."""
    mine = [job for job in mine if not _skip(job)]
    active = next((job for job in current if job.state in ACTIVE), None)
    if key == 'coding_validation' or active is None:
        return 'waiting'
    if _held(active.provider_run if active.kind == Job.ASSESS else None, active.context):
        return 'not_run'  # a member date conflict holds the document: nothing is asked of either until it is settled
    if key == 'independent_checks':
        if not configured and not mine:
            return 'not_run'
        if active.kind == Job.ASSESS and _assess_step(active, [], revision) == CHECKING:
            return 'waiting'  # an assess #1: its peer reviews follow it
    if mine:
        return _jobs_outcome(mine)
    if active.kind in (Job.EXTRACT, Job.ANALYZE) or (key == 'independent_checks' and active.kind in SENDING_KINDS):
        return 'waiting'
    previous = models.Assessment.objects.filter(revision=revision).order_by('-created_at', '-pk').first()
    if previous is None:
        return 'waiting'
    return _document_outcome(previous) if key == 'document_review' else _checks_outcome(previous)


def encounter_progress(encounter, now=None) -> dict:
    """The progress block of a document (DESIGN section 7 ``progress``, every key and nothing else). ``can_stop`` and
    ``can_resume`` say whether the action applies to the document; the caller also requires a role that may take it.
    ``started_at`` is when the current run was asked for (its first job queued), ``finished_at`` when its last job
    finished (None while busy)."""
    now = now or timezone.now()
    revision = encounter.current_revision
    rows = list(encounter.jobs.filter(revision=revision).select_related('provider_run', 'context')
                .order_by('created_at', 'pk')) if revision is not None else []
    runs = _runs(rows)
    busy = jobs.busy(encounter)
    current = runs[-1] if runs else []
    running = next((job for job in current if job.state == Job.RUNNING), None)
    queued = next((job for job in current if job.state == Job.QUEUED), None)
    active = running or queued
    slow, slow_message, error, limited = False, '', None, None
    if date_held(encounter):
        phase = 'action_needed'
    elif busy and jobs.worker_responding(now=now) is False:
        # decision (j): a worker whose newest beat is older than WORKER_SILENT_SECONDS is never drawn as working - no
        # step animates and nothing is called slow; a worker that never beat (None) claims nothing either way
        phase = 'paused'
    elif busy:
        phase = 'processing' if running is not None else 'queued'
        slow, slow_message = _slow(active, now)
    else:
        state = review._derive_state(encounter)
        if state == 'stopped':
            phase = 'stopped'
            error = {'text': STOPPED_BY_MEMBER if encounter.stopped_at is not None else STOPPED_BY_SYSTEM,
                     'action': 'resume' if review.can_resume(encounter) else 'none'}
        elif state in FAILED_STATES or state == 'processing':
            phase = 'failed'
            text, action = ERRORS[state if state in FAILED_STATES else 'unfinished']
            error = {'text': text, 'action': action}
        elif state == 'provider_unknown':
            phase = 'being_confirmed'
        elif _open_details(encounter):
            phase = 'awaiting_detail'
        else:
            limited = _partial(encounter, revision)
            phase = 'partial' if limited else 'completed'
    steps = _steps(runs, revision)
    if slow:
        message = slow_message
    elif phase == 'queued':
        # a retry waits its turn; a step after one the panel shows done waits for the next step (refutation r2, L5-7),
        # by the rule the page titles it with (refutation r3, C-R3-4: next_step_queued)
        message = queued_message(steps, queued)
    elif error is not None:
        message = error['text']
    elif limited:
        message = limited
    elif phase == 'action_needed' and not _document_states_a_date(encounter):
        message = MESSAGES['action_needed_undated']
    else:
        message = MESSAGES[phase]
    finished = [_end(job) for job in current if job.state not in ACTIVE]
    return {
        'phase': phase, 'busy': busy, 'steps': steps,
        'active_detail': DETAILS.get(active.kind, '') if busy and active is not None else '',
        'started_at': _iso(current[0].created_at) if current else None,
        'finished_at': _iso(max(finished)) if finished and not busy else None,
        'server_time': _iso(now), 'slow': slow, 'message': message,
        'can_stop': busy, 'can_resume': (not busy) and review.can_resume(encounter), 'can_leave': True,
        'error': error,
    }


def _document_states_a_date(encounter):
    """Whether the document states a date of service of its own (answers.service_date_block's document value)."""
    from . import answers  # local import: the details flow reads the jobs this module reads
    return bool(answers.service_date_block(encounter).get('document_value'))


def _open_details(encounter):
    """Whether a detail row the customer is shown has no saved answer: the rows answers.details_needed builds, with the
    review overlay's questions when the review layer has one (answers.effective_view)."""
    from . import answers  # local import: answers reads review and jobs too

    live = review.live_assessment(encounter)
    return any(row['saved'] is None for row in answers.details_needed(encounter, live, answers.effective_view(live)))


def _partial(encounter, revision):
    """The message of a result completed with limits (directive 5, "partially completed"), or None when it has none:
    the final assessment is present, and a re-check of what is still open asked for it did not complete
    (RECHECK_INCOMPLETE: it says so; refutation r2, L5-5), or the document review, an independent check or a reference
    check could not be completed, or the document's text was read only in part (MESSAGES['partial']) - the same readings
    the checks state, so a check read 'unavailable' is never beside a result called complete."""
    assessment = final_assessment(encounter)
    if assessment is None:
        return None
    if recheck_incomplete(assessment) is not None:
        return RECHECK_INCOMPLETE
    if ((revision is not None and revision.extraction_status == models.SourceRevision.PARTIAL)
            or _document_outcome(assessment) == 'unavailable' or _checks_outcome(assessment) == 'unavailable'
            or _validation_outcome(assessment) == 'unavailable'):
        return MESSAGES['partial']
    return None
