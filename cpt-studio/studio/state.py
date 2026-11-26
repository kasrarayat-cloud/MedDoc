"""The encounter's derived state (BUILD-SPEC section 5), written to Encounter.state after every job, decision and answer.

Read from the latest coding round only:
- processing: it is queued or running;
- stopped: it was cancelled (a member's Stop, an expired queue, a worker that stopped mid-stage) - Resume continues it;
- failed: it failed;
- once it is done, from its final statuses and the current decisions (latest CodeDecision per line, revoke clearing
  it; FIX-SPEC 1 - two lines with one code are two lines): awaiting_answer when a line needs an answer; else
  needs_review when a needs_review line has no current approve or reject; else ready when a ready line has none; else
  reviewed when the reviewer decided every ready and needs_review line; else no_codes.
An encounter with no coding round (one recorded before this path) keeps the state it has.
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction
from django.utils import timezone

from . import models

PROCESSING, STOPPED, FAILED = 'processing', 'stopped', 'failed'
AWAITING_ANSWER, NEEDS_REVIEW, READY, REVIEWED, NO_CODES = (
    'awaiting_answer', 'needs_review', 'ready', 'reviewed', 'no_codes')
LABELS = {PROCESSING: 'Processing', STOPPED: 'Stopped', FAILED: 'Could not finish', AWAITING_ANSWER: 'Questions for you',
          NEEDS_REVIEW: 'Needs your review', READY: 'Ready for approval', REVIEWED: 'Reviewed',
          NO_CODES: 'No codes found'}
Round, Decision = models.CodingRound, models.CodeDecision
DECIDED = (Decision.APPROVE, Decision.REJECT)


def label(state: str) -> str:
    return LABELS.get(state, state)


def latest_round(encounter) -> Optional[models.CodingRound]:
    return Round.objects.filter(encounter_id=encounter.pk).order_by('-number').first()


def decisions_of(round_) -> list[models.CodeDecision]:
    """Every decision on ``round_``, with its reviewer, in sequence order: the one query current_decisions runs (release
    2, R2-25: a document's read runs it once and derives both its state and its codes' decisions from it)."""
    return list(Decision.objects.filter(round_id=round_.pk).select_related('reviewer').order_by('sequence'))


def current_of(decisions) -> dict[str, models.CodeDecision]:
    """{line: its current decision} of ``decisions`` (decisions_of's, in sequence order): the latest row per line; a
    revoke leaves none."""
    current: dict[str, models.CodeDecision] = {}
    for decision in decisions:
        if decision.action == Decision.REVOKE:
            current.pop(decision.line, None)
        else:
            current[decision.line] = decision
    return current


def current_decisions(round_) -> dict[str, models.CodeDecision]:
    """{line: its current decision} for ``round_``: the latest row per line by sequence; a revoke leaves none."""
    return current_of(decisions_of(round_))


def compute(encounter) -> Optional[str]:
    """The state ``encounter`` reads now, or None when it has no coding round."""
    return derive(latest_round(encounter))


def derive(round_, current=None) -> Optional[str]:
    """The state of an encounter whose latest coding round is ``round_`` (None when it has none): compute's rules, in
    this one place. ``current`` is that round's current decisions (current_of) when the caller has read them already;
    otherwise they are read here (release 2, R2-25)."""
    if round_ is None:
        return None
    if round_.state in (Round.QUEUED, Round.RUNNING):
        return PROCESSING
    if round_.state == Round.CANCELLED:
        return STOPPED
    if round_.state != Round.DONE:
        return FAILED
    codes = [code for code in round_.codes or () if isinstance(code, dict)]
    if any(code.get('status') == 'needs_answer' for code in codes):
        return AWAITING_ANSWER
    decided = {line for line, decision in (current if current is not None else current_decisions(round_)).items()
               if decision.action in DECIDED}
    for status, state in (('needs_review', NEEDS_REVIEW), ('ready', READY)):
        if any(code.get('status') == status and code.get('line') not in decided for code in codes):
            return state
    if any(code.get('status') in ('needs_review', 'ready') for code in codes):
        return REVIEWED
    return NO_CODES


def refresh(encounter) -> str:
    """Recompute and store Encounter.state (written only when it changed); returns the state."""
    with transaction.atomic():
        locked = models.Encounter.objects.select_for_update().get(pk=encounter.pk)
        state = compute(locked)
        if state is None:
            state = locked.state
        elif locked.state != state:
            models.Encounter.objects.filter(pk=locked.pk).update(state=state, updated_at=timezone.now())
    encounter.state = state
    return state
