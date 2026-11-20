"""A member's acts on the encounter's latest coding round (BUILD-SPEC 6): review decisions and answers.

Decisions (approve, reject, revoke). An owner or reviewer decides one code line of the latest round, once that round is
done (line identity, FIX-SPEC section 1). The request names the round the page showed, the line and its code: a round
that is not the latest, or a latest round not done, is refused as changed (the page reloads); a line that round does not
hold, or one holding another code, is refused too - so a decision is never recorded on a line its reviewer did not see.
- a ready or needs_review line may be approved or rejected; a needs_answer line is answered first (that starts a new
  round) and a not_supported line is never decided;
- a line with a current decision may only have it revoked, and is then decided again;
- an approval carries the review attestation for the reviewer's kind, exactly (ACKNOWLEDGEMENTS, unchanged from the
  earlier review module).
Every decision is a new CodeDecision row - append-only, ordered by studio_decision_sequence; the latest row per line is
current and a revoke clears it (state.current_decisions) - audited as decision.recorded, and the encounter state is
refreshed.

Answers. An owner or reviewer answers questions the latest round asked, once it is done: each answer names a question by
the id the customer page was given (question_id: the round's own, so a page left open on an earlier round is refused)
and has 1 to 2,000 characters. The answers are stored as CodingAnswer rows and a new round starts (trigger answers),
whose context carries every answer so far (jobs.start_round reads them all).

Retry. A failed latest round (not one stopped at the spending ceiling, which the same document would meet again) is
coded again as a new round of the current revision (jobs.retry); so is an encounter with no round at all - a record of
the earlier system - once its queued jobs of the earlier system's kinds, which today's worker never runs, are retired.

Nothing here reads the document or changes a code: the codes are Fable's (BUILD-SPEC section 0).
"""
from __future__ import annotations

import re
import uuid

from django.db import transaction
from django.utils import timezone

from . import audit, jobs, models, state

Round, Decision, Answer = models.CodingRound, models.CodeDecision, models.CodingAnswer
APPROVE, REJECT, REVOKE = Decision.APPROVE, Decision.REJECT, Decision.REVOKE
ACTIONS = (APPROVE, REJECT, REVOKE)
DECIDABLE = ('ready', 'needs_review')
MAX_NOTE_CHARS = 2000
MAX_ANSWERS = 50
CODE_CHARS = 8  # CodeDecision.code holds at most this many characters
LINE_CHARS = 4  # and CodeDecision.line this many (L1..L999, M1..M999)
# PostgreSQL text cannot hold NUL, and a lone surrogate cannot be encoded at all.
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')

# The review attestation an approval carries, for the reviewer's kind - the exact text. It keeps the earlier
# attestation's meaning (studio/review.py ACKNOWLEDGEMENTS until 2026-11-20); its middle sentence named documentation
# checks that no longer exist and now says what is true of the coding review (DECISIONS D355). The session serves it;
# an approval must send it back.
ACKNOWLEDGEMENTS = {
    'human': ('I read the whole source document, not only the quoted passages, and it supports this code as a '
              'service performed at this encounter. The coding review can be wrong. This synthetic review is not '
              'clinical approval or billing advice.'),
    'agent': ('I am an automated agent. I read the whole source document, not only the quoted passages, and it '
              'supports this code as a service performed at this encounter. The coding review can be wrong. This '
              'agent-executed synthetic review is not clinical approval or billing advice.'),
}

ROUND_CHANGED = 'This coding review has changed. Reload to see the latest.'
NOT_IN_ROUND = 'That code is not part of this coding review. Reload to see the latest.'
ROUND_REQUIRED = 'Name the coding review the decision was made on.'
LINE_REQUIRED = 'Name the code line to decide on.'
DECIDED_ALREADY = 'This code already has a decision. Undo it first.'
NOTHING_TO_UNDO = 'This code has no decision to undo.'
NOT_DECIDABLE = {'needs_answer': 'Answer the question about this code first; the coding review then reads it again.',
                 'not_supported': 'A code the coding review found not supported cannot be approved or rejected.'}
ATTESTATION_REFUSED = 'The acknowledgement is not the current review attestation. Reload the page and approve again.'
NO_QUESTIONS = 'There are no questions to answer now.'
STALE_QUESTIONS = 'These questions are no longer asked. Reload the page to see the current questions.'


class Refused(Exception):
    """A decision or an answer refused: ``status`` (400 invalid input, 404 not found, 409 not now) and the member's
    sentence."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def acknowledgement_for(user) -> str:
    """The exact attestation an approval by ``user`` carries ('' for an unknown kind, which can then approve nothing)."""
    return ACKNOWLEDGEMENTS.get(getattr(user, 'actor_kind', ''), '')


def decidable_code(row) -> str:
    """The code a decision on ``row`` (a round's code row) is recorded under, or '' when none can be: its code and its
    line must both fit a CodeDecision."""
    code = row.get('code') if isinstance(row, dict) else None
    line = row.get('line') if isinstance(row, dict) else None
    if not (isinstance(line, str) and line.strip() and len(line) <= LINE_CHARS):
        return ''
    return code if isinstance(code, str) and code.strip() and len(code) <= CODE_CHARS else ''


def allowed_actions(row, decision, can_review: bool) -> list:
    """The decisions a member may record on ``row`` now (BUILD-SPEC 6): none without the reviewer role; revoke while a
    decision stands; approve and reject for a ready or needs_review line; nothing else."""
    if not can_review or not decidable_code(row):
        return []
    if decision is not None:
        return [REVOKE]
    if row.get('status') in DECIDABLE:
        return [APPROVE, REJECT]
    return []


def _text(value, label, *, limit=MAX_NOTE_CHARS) -> str:
    """Member-supplied text: a string, or absent/null as ''; never altered - refused when it cannot be stored."""
    if value is None:
        return ''
    if not isinstance(value, str):
        raise Refused(400, f'{label} must be text.')
    if UNSTORABLE.search(value):
        raise Refused(400, f'{label} contains a NUL character or an invalid Unicode code point; remove it and try again.')
    if len(value) > limit:
        raise Refused(400, f'{label} can be at most {limit:,} characters.')
    return value


def _locked(encounter):
    return models.Encounter.objects.select_for_update().select_related('workspace').get(pk=encounter.pk)


def record(encounter, user, membership, *, round_number, line, code, action, acknowledgement='',
           note='') -> models.CodeDecision:
    """Record ``action`` on line ``line`` (holding ``code``) of round ``round_number`` - the round the page showed,
    which must be the encounter's latest and done - by ``user`` (BUILD-SPEC 6; FIX-SPEC 1), or Refused."""
    if not isinstance(action, str) or action not in ACTIONS:
        raise Refused(400, 'Choose approve, reject or undo.')
    if not isinstance(code, str) or not code:
        raise Refused(400, 'Name the code to decide on.')
    if not isinstance(line, str) or not line:
        raise Refused(400, LINE_REQUIRED)
    if type(round_number) is not int or round_number < 1:
        raise Refused(400, ROUND_REQUIRED)
    note = _text(note, 'The note')
    acknowledgement = _text(acknowledgement, 'The acknowledgement')
    with transaction.atomic():
        locked = _locked(encounter)
        round_ = state.latest_round(locked)
        if round_ is None or round_.state != Round.DONE or round_.number != round_number:
            raise Refused(409, ROUND_CHANGED)
        rows = [item for item in round_.codes or () if isinstance(item, dict) and item.get('line') == line]
        if len(rows) != 1 or rows[0].get('code') != code:
            raise Refused(409, NOT_IN_ROUND)
        row = rows[0]
        current = state.current_decisions(round_).get(line)
        allowed = allowed_actions(row, current, bool(membership.can_review))
        if action not in allowed:
            if current is not None:
                raise Refused(409, DECIDED_ALREADY)
            if action == REVOKE:
                raise Refused(409, NOTHING_TO_UNDO)
            raise Refused(409, NOT_DECIDABLE.get(row.get('status'), 'This code cannot be decided here.'))
        if action == APPROVE and (not acknowledgement or acknowledgement != acknowledgement_for(user)):
            raise Refused(400, ATTESTATION_REFUSED)
        decision = Decision.objects.create(
            encounter=locked, round=round_, line=line, code=code, action=action, reviewer=user,
            reviewer_kind=user.actor_kind, acknowledgement=acknowledgement if action == APPROVE else '', note=note)
        audit.record(locked.workspace, 'decision.recorded', encounter=locked, actor=user, decision=str(decision.pk),
                     round=str(round_.pk), number=round_.number, action=action, line=line, code=code)
        state.refresh(locked)
    decision.refresh_from_db(fields=['sequence', 'created_at'])
    return decision


# --- answers -------------------------------------------------------------------------------------------------------------

def question_id(round_, question) -> str:
    """The id a question of ``round_`` is given on the customer page: the round's own (uuid5 of the round and the
    question's place in it), so an answer from a page left open on an earlier round names no question of a later one."""
    return str(uuid.uuid5(round_.pk, str(question.get('id') if isinstance(question, dict) else '')))


def round_questions(round_) -> list:
    """[(question id, question)] of ``round_`` (its combined questions with a text), in the order asked."""
    out = []
    for item in round_.questions or ():
        if isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip():
            out.append((question_id(round_, item), item))
    return out


def answer_items(value) -> list:
    """[(question id, answer text)] of a request's ``answers`` ([{question_id, text}]), validated, or Refused 400."""
    if not isinstance(value, list) or not value:
        raise Refused(400, 'Write an answer to at least one question, then send.')
    if len(value) > MAX_ANSWERS:
        raise Refused(400, f'Send at most {MAX_ANSWERS} answers at once.')
    items, seen = [], set()
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get('question_id'), str):
            raise Refused(400, 'Each answer names the question it answers.')
        text = _text(item.get('text'), 'An answer', limit=10 * Answer.MAX_CHARS).strip()
        if not text:
            raise Refused(400, 'An answer cannot be empty. Write it, or leave that question out.')
        if len(text) > Answer.MAX_CHARS:
            raise Refused(400, f'An answer can be at most {Answer.MAX_CHARS:,} characters. Shorten it, then send.')
        if item['question_id'] in seen:
            raise Refused(400, 'Answer each question once.')
        seen.add(item['question_id'])
        items.append((item['question_id'], text))
    return items


def _blocking_jobs(encounter) -> bool:
    """Whether a job keeps an encounter with no round from being coded now: one running, or one queued of a kind this
    worker runs. A job of the earlier system's kinds left queued is never run by today's worker (retry retires it)."""
    return encounter.jobs.filter(state=models.Job.RUNNING).exists() or encounter.jobs.filter(
        state=models.Job.QUEUED, kind__in=list(jobs.STAGES)).exists()


def retry_offered(encounter, round_) -> bool:
    """Whether a member may ask for the document to be coded again now: its latest round failed (not at the spending
    ceiling, which a new round of the same document would meet again), nothing runs and no send of the round awaits an
    operator's reconcile (jobs.awaiting_reconcile: jobs.retry refuses it until then, FIX-SPEC 4); or it has no round at
    all (an earlier review) and a revision to code."""
    if round_ is None:
        return encounter.current_revision_id is not None and not _blocking_jobs(encounter)
    return (round_.state == Round.FAILED and round_.failure_kind != jobs.CEILING
            and not jobs.busy(encounter) and not jobs.awaiting_reconcile(round_))


SUPERSEDED_JOB = 'Not run: the document is coded again with the current version of CPT Studio.'


def retry(encounter, user) -> models.CodingRound:
    """A member's retry (POST retry): a new round of the current revision, trigger retry - for a failed latest round
    (jobs.retry), or for an encounter with no round, whose queued jobs of the earlier system's kinds are retired first
    (today's worker never runs them). Refused or jobs.Refused (the member's sentence) otherwise."""
    with transaction.atomic():
        locked = _locked(encounter)
        round_ = state.latest_round(locked)
        if round_ is None:
            if locked.current_revision_id is None:
                raise Refused(409, 'This document has nothing to code.')
            models.Job.objects.filter(encounter=locked, state=models.Job.QUEUED).exclude(
                kind__in=list(jobs.STAGES)).update(state=models.Job.CANCELLED, error=SUPERSEDED_JOB,
                                                   finished_at=timezone.now())
            return jobs.start_round(locked, locked.current_revision, Round.RETRY, user)
        if round_.state == Round.FAILED and round_.failure_kind == jobs.CEILING:
            raise Refused(409, jobs.FAILURE_TEXT[jobs.CEILING])
        return jobs.retry(locked, user)


def record_answers(encounter, user, items) -> models.CodingRound:
    """Store ``items`` (answer_items) as answers to the latest round's questions and start the next round (trigger
    answers) with every answer so far in its context, all in one transaction; Refused when the latest round is not done
    or a question is not one it asked; jobs.Refused while a job of the encounter runs."""
    with transaction.atomic():
        locked = _locked(encounter)
        round_ = state.latest_round(locked)
        if round_ is None or round_.state != Round.DONE:
            raise Refused(409, NO_QUESTIONS)
        asked = dict(round_questions(round_))
        if not asked:
            raise Refused(409, NO_QUESTIONS)
        if any(question not in asked for question, _ in items):
            raise Refused(409, STALE_QUESTIONS)
        if jobs.busy(locked):
            raise jobs.Refused(jobs.BUSY_MESSAGE)
        for question, text in items:
            Answer.objects.create(encounter=locked, round=round_, question=asked[question]['text'], answer=text,
                                  answered_by=user)
        audit.record(locked.workspace, 'answers.recorded', encounter=locked, actor=user, round=str(round_.pk),
                     number=round_.number, count=len(items))
        return jobs.start_round(locked, round_.revision, Round.ANSWERS, user)
