"""What a doctor reads about a request: ONE mapping from job and complete-form batch states to plain words.

Every doctor-facing page reads a request's status through doctor_status(): the document page's request list, the billing
page's list of requests holding funds, the billing charge page, and the answer to a re-posted request. Internal state
words ('reconciliation', 'staged', 'validating', 'not_adopted') and administrator notes (job.error written for an
administrator, such as 'Resolved by administrator: ...') never reach the doctor; the billing classifications they are
owed (core.jobs.public_error's doctor-facing reasons) do.

Wording only, and true of the ledger (refutation F5 of dc33e094). Whether a request is charged is read from the ledger
itself (net_charge: its entries for the request's jobs), never inferred from its state or text: a job the worker settled
and the sweep then held for review IS charged. A sentence that says "not charged" is said only while the ledger shows no
net charge; with one, the sentence says it was charged and that Billing shows it. No amount, settlement or ledger rule is
decided here.
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


#: The sentence for each status when the ledger shows a net charge for the request. Never "not charged".
CHARGED_EXPLANATIONS = {
    'waiting': 'Queued. A charge is already recorded for this request; Billing shows it.',
    'in_progress': 'Processing. A charge is already recorded for this request; Billing shows it, and the charge never exceeds '
                   'the maximum you approved.',
    'held': 'This request was charged, and an administrator is reviewing it. Billing shows the charge; any correction is made '
            'there and never exceeds the maximum you approved.',
    'not_completed': 'This request did not complete, but a charge is recorded for it; Billing shows it.',
    'cancelled': 'Cancelled, but a charge is recorded for this request; Billing shows it.',
    'unknown': 'This request\'s status could not be read. A charge is recorded for it; Billing shows it. Contact your '
               'administrator before resubmitting.',
}


def net_charge(jobs):
    """What the ledger has charged for these jobs, net of any reversal (absorbed failures, reconciliations): the negated sum
    of their ledger entries. Zero for a job that was never settled or whose charge was reversed."""
    from django.db.models import Sum
    from .models import LedgerEntry
    total = LedgerEntry.objects.filter(job_id__in=[job.pk for job in jobs]).aggregate(total=Sum('amount'))['total']
    return -(total or 0)


def _status(key, explanation=None, charge=0):
    label, tone = LABELS[key]
    if charge > 0 and key in CHARGED_EXPLANATIONS:
        explanation = CHARGED_EXPLANATIONS[key]
    return Status(key, label, tone, explanation or EXPLANATIONS[key], key in PENDING, charge > 0)


def _batch(job):
    if job.kind != 'generation_part':
        return None
    try:
        return job.generation_part.batch
    except Exception:  # noqa: BLE001 - a part row that cannot be read is reported as unreadable, never guessed
        return False


def doctor_status(job):
    """The doctor's words for one request. A complete-form part speaks for its whole batch."""
    from .jobs import CANCELLED_ERROR, NOT_ADOPTED, PLATFORM_FAILURE
    batch = _batch(job)
    if batch is False:
        return _status('unknown', charge=net_charge([job]))
    if batch is not None:
        charge = net_charge([part.job for part in batch.parts.select_related('job')])
        state = batch.state
        if state == 'queued':return _status('waiting', BATCH_PREPARING, charge)
        if state in ('running', 'validating'):return _status('in_progress', BATCH_PREPARING, charge)
        if state == 'reconciliation':return _status('held', charge=charge)
        if state == 'succeeded':return _status('completed', charge=charge)
        if state == 'not_adopted':
            return _status('completed_not_applied', 'The complete form was processed but not applied to this document. '
                           + ('The provider completed it, so it remains charged; Billing shows it.' if charge > 0
                              else 'No charge is recorded for it.'), charge)
        if state == 'failed':return _status('not_completed', charge=charge)
        if state == 'cancelled':return _status('cancelled', charge=charge)
        return _status('unknown', charge=charge)
    charge = net_charge([job])
    state, error = job.state, job.error or ''
    if state == 'queued':return _status('waiting', charge=charge)
    if state in ('running', 'staged', 'validating'):return _status('in_progress', charge=charge)
    if state == 'reconciliation':return _status('held', charge=charge)
    if state == 'succeeded':return _status('completed', charge=charge)
    if state == 'cancelled' or error == CANCELLED_ERROR:return _status('cancelled', charge=charge)
    if state == 'failed':
        if error.startswith(NOT_ADOPTED):
            return _status('completed_not_applied', error[len(NOT_ADOPTED):] + (
                ' The provider completed this request, so it remains charged; Billing shows it.' if charge > 0
                else ' No charge is recorded for it.'), charge)
        if error.startswith(PLATFORM_FAILURE):
            return _status('not_completed', error[len(PLATFORM_FAILURE):] + ' This was a platform failure; it is not '
                                            'charged to you.', charge)
        return _status('not_completed', charge=charge)
    return _status('unknown', charge=charge)


#: ⚠️ ANOTHER PERSON'S REQUEST IS TOLD IN THE THIRD PERSON (refutation R3B-2 of 75d11c09): the held list shows an owner of
#: the paying organization the requests colleagues made, and each carried its requester's sentence ("the maximum charge you
#: approved is held"), telling the owner they approved a hold they never saw. The same facts, without "you".
THIRD_PERSON = (('the maximum charge you approved', 'the approved maximum charge'),
                ('the maximum you approved', 'the approved maximum'),
                ('It is not charged to you.', 'It is not charged.'),
                ('it is not charged to you.', 'it is not charged.'),
                ('Contact your administrator before resubmitting.', 'Its requester should contact an administrator before '
                                                                   'resubmitting.'),
                # 'Billing shows it' is true of the REQUESTER's Billing: a colleague's or an owner's Billing shows a charge on
                # the requester's own wallet nowhere (refutation R4B-2 of b3d8111d).
                ('Billing shows it', "its requester's Billing shows it"),
                ('Billing shows the charge', "its requester's Billing shows the charge"),
                ('Its charge is shown under Billing.', "Its charge is shown under its requester's Billing."))


def for_others(status):
    """`status` as read by someone other than its requester. Any sentence still addressed to the reader falls back to the
    label alone: a closed list of rewrites is checked, never trusted."""
    import re
    text = status.explanation
    for mine, theirs in THIRD_PERSON:
        text = text.replace(mine, theirs)
    if re.search(r'(?i)\byou(r)?\b', text) or re.search(r"(?<!requester's )\bBilling\b", text):
        text = status.label + '.'
    return status._replace(explanation=text)


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
