"""What a doctor reads about a request: ONE mapping from job and complete-form batch states to plain words.

Every doctor-facing page reads a request's status through doctor_status(): the document page's request list, the billing
page's list of requests holding funds, the billing charge page, and the answer to a re-posted request. Internal state
words ('reconciliation', 'staged', 'validating', 'not_adopted') and administrator notes (job.error written for an
administrator, such as 'Resolved by administrator: ...') never reach the doctor; the billing classifications they are
owed (core.jobs.public_error's doctor-facing reasons) do.

Wording only. Whether a request is charged is read from billing's own predicate (core.jobs.billable_outcome) and the
batch's recorded state, never inferred from text; no amount, settlement or ledger rule is decided here.
"""
from collections import namedtuple

Status = namedtuple('Status', 'key label tone explanation pending charged')

LABELS = {
    'waiting': ('Waiting to start', 'neutral'),
    'in_progress': ('In progress', 'neutral'),
    'held': ('On hold for review', 'warning'),
    'completed': ('Completed', 'success'),
    'completed_not_applied': ('Completed, not applied', 'warning'),
    'not_completed': ('Not completed', 'warning'),
    'cancelled': ('Cancelled', 'neutral'),
    'unknown': ('Status unavailable', 'warning'),
}
EXPLANATIONS = {
    'waiting': 'Queued. No request has been sent yet; the maximum charge you approved is held, not charged.',
    'in_progress': 'Processing has started. The held maximum is settled when the result arrives, and the charge never '
                   'exceeds it.',
    'held': 'On hold until an administrator reviews it. The held amount is not charged until then, and any charge stays '
            'within the maximum you approved.',
    'completed': 'Completed. Its charge is shown under Billing.',
    'not_completed': 'This request did not complete. It is not charged to you.',
    'cancelled': 'Cancelled before any provider request; nothing was charged.',
    'unknown': 'This request\'s status could not be read. Contact your administrator before resubmitting.',
}
BATCH_PREPARING = 'The complete form is being prepared. Answers appear together after validation.'
PENDING = ('waiting', 'in_progress', 'held')


def _status(key, explanation=None, charged=False):
    label, tone = LABELS[key]
    return Status(key, label, tone, explanation or EXPLANATIONS[key], key in PENDING, charged)


def _batch(job):
    if job.kind != 'generation_part':
        return None
    try:
        return job.generation_part.batch
    except Exception:  # noqa: BLE001 - a part row that cannot be read is reported as unreadable, never guessed
        return False


def doctor_status(job):
    """The doctor's words for one request. A complete-form part speaks for its whole batch."""
    from .jobs import CANCELLED_ERROR, NOT_ADOPTED, PLATFORM_FAILURE, billable_outcome
    batch = _batch(job)
    if batch is False:
        return _status('unknown')
    if batch is not None:
        state = batch.state
        if state == 'queued':return _status('waiting', BATCH_PREPARING)
        if state in ('running', 'validating'):return _status('in_progress', BATCH_PREPARING)
        if state == 'reconciliation':return _status('held')
        if state == 'succeeded':return _status('completed', charged=True)
        if state == 'not_adopted':
            return _status('completed_not_applied', 'The complete form was processed but not applied to this document. '
                                                    'The provider completed it, so it remains charged.', charged=True)
        if state == 'failed':return _status('not_completed')
        if state == 'cancelled':return _status('cancelled')
        return _status('unknown')
    state, error = job.state, job.error or ''
    if state == 'queued':return _status('waiting')
    if state in ('running', 'staged', 'validating'):return _status('in_progress')
    if state == 'reconciliation':return _status('held')
    if state == 'succeeded':return _status('completed', charged=billable_outcome(job))
    if state == 'cancelled' or error == CANCELLED_ERROR:return _status('cancelled')
    if state == 'failed':
        if error.startswith(NOT_ADOPTED):
            return _status('completed_not_applied', error[len(NOT_ADOPTED):] + ' The provider completed this request, so '
                                                    'it remains charged.', charged=billable_outcome(job))
        if error.startswith(PLATFORM_FAILURE):
            return _status('not_completed', error[len(PLATFORM_FAILURE):] + ' This was a platform failure; it is not '
                                            'charged to you.')
        return _status('not_completed')
    return _status('unknown')


ENCOUNTER_LABELS = {'draft': 'Draft', 'review': 'Answers ready for review', 'finalized': 'Finalized', 'redacted': 'Redacted'}


def encounter_label(encounter):
    """A document's status in the doctor's words; an unrecognised value says so rather than printing it."""
    return ENCOUNTER_LABELS.get(encounter.status, 'Status unavailable')


def reuse_message(job, *, recording=False):
    """The answer to a re-posted request that found an earlier one under the same request key: nothing new was sent or
    charged, and what the earlier request is doing NOW (refuted wording: 'answer draft' while it was still queued)."""
    status = doctor_status(job)
    subject = 'A request to transcribe this recording' if recording else 'A request for these source notes'
    if status.pending:
        return (f'{subject} was already made and is {status.label.lower()}. No new request was made and nothing more was '
                'charged. Refresh this page to see its result.')
    if status.key == 'completed':
        if recording:
            return ('This recording was already transcribed for this document. No new request was made and nothing was '
                    'charged. Its transcript is below in Document record.')
        return ('These source notes already have an answer draft from an earlier request. No new request was made and '
                'nothing was charged. Edit and save the notes to generate again.')
    return (f'{subject} was already made ({status.label.lower()}). No new request was made and nothing more was charged.')
