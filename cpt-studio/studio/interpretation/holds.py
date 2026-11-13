"""The installation-wide interpreter hold (design/FINAL.md 4.1, 6.3, 11.1 and 11.2; DECISIONS D11; design/ADJUDICATION.md
P-3, P-4 and P-5): what one interpretation run's outcome means for the installation (``classify``), the hold it sets
(``record``, ``settle``), whether one stands (``active``, ``current``, ``paused_reason``) and its recorded release
(``release``).

ONE CLASSIFIER. A Gemini response is read by ``interpretation.adapter.classify`` and by nothing else: the HTTP status,
error.status, the google.rpc.ErrorInfo reasons, the QuotaFailure violations and the envelope (P-3, P-4, P-5, C5). This
module never reads a response body. It adds only the rows of FINAL 11.1 that are not about a response - an outcome
that is not known, nothing sent, an answer whose READING was refused - and a hold records exactly what the adapter's
classification says: its reason, HTTP status, vendor status and violations.

THE TABLE (FINAL 11.1, as P-3, P-4, P-5 and C5 amend it, and FINAL-V2 amendment 1's A11). An interpretation run's
outcome has exactly one effect:

| the outcome                                                                     | effect     | what follows          |
|---------------------------------------------------------------------------------|------------|-----------------------|
| adapter.classify says HOLD - auth (401; API_KEY_INVALID, API_KEY_EXPIRED,        | HOLD       | an operator's release |
| UNAUTHENTICATED), permission (403; API_KEY_SERVICE_BLOCKED, SERVICE_DISABLED,   |            | (interpreter_hold     |
| PERMISSION_DENIED, FAILED_PRECONDITION), quota (BILLING_DISABLED; 402, a        |            | --release), then      |
| payment failure, A11; a 429 whose QuotaFailure names a daily, zero, free-tier   |            | members Resume        |
| or unnamed window, or a 429 with no QuotaFailure at all - D39: a spending cap   |            |                       |
| answers so) or model (a 200 naming another model, or none: P-5)                 |            |                       |
| adapter.classify says FAILED - a 429 whose every violation is a per-minute     | FAILED     | the recorded retry    |
| paid-tier limit above 0, a 5xx, a 400 without the names above, any other       |            | (FINAL 11.3)          |
| refusal of the request, or an                                                   |            |                       |
| envelope the reader refuses (finish reason, candidates, parts, not JSON)        |            |                       |
| adapter.classify says ANSWERED, but the reading was refused (read.Refusal: the  | FAILED     | the recorded retry    |
| schema, bounds or ids of the answer; an EventInventory in state 'refused')      |            |                       |
| adapter.classify says TOO_LONG (MAX_TOKENS; C5)                                 | TOO_LONG   | no paid retry for a   |
|                                                                                 |            | member                |
| the run is UNKNOWN (a send cut by its deadline, a connection lost after the     | UNKNOWN    | reconcile (FINAL 6.9) |
| request left, an unrecorded outcome)                                            |            |                       |
| adapter.classify says ANSWERED and the reading was not refused                  | ANSWERED   | analyze               |
| nothing was sent (not_sent, cancelled) or there is no outcome yet (reserved,    | NONE       | -                     |
| sending)                                                                        |            |                       |

There is no automatic retry and no fallback, and never the legacy reader (D11).

THE HOLD (FINAL 11.2). While one stands, or the interpreter mode is 'disabled' (D11 refined: treated like a hold), no
Gemini request is built for sending: each interpret stage records a not-sent run with scope.held = HELD_HOLD or
HELD_DISABLED (``paused_reason``) and ends CANCELLED, and the encounter reads stopped with the paused phase and
PAUSED_MESSAGE. The hold is installation-wide (it names no workspace) and append-only: an InterpreterHold row stands until
an InterpreterHoldRelease names it. One ANSWER sets at most one hold, whichever run carries it: settling a run twice, or a
reuse of it (jobs' reuse doors copy the answer and send nothing), never sets a second one, and a run that was not sent
sets none. An operator - an active account holding an operator grant no revocation ended - releases every standing hold
with ``manage.py interpreter_hold --release`` and a recorded note; members then Resume.

TWO SCOPES. A hold is stored, so every process sees the same holds. The mode is a setting of each PROCESS
(settings.GEMINI_MODE): the worker's decides for the worker, and a one-shot runs with the interpreter disabled unless it is
given a mode (FINAL 13), so what a one-shot reads of its own mode says nothing of the worker's. ``state`` names the two
apart, and the installer reads the worker's configured mode from the worker itself.

DESIGN V2 (docs/gemini-migration/FINAL-V2.md 7.4 and 7.5, AMENDMENT-1.md 7.3; step 3b of its 8.1): the purpose
``appraisal``. Design v2's second Gemini call, the appraisal (pass 2, ProviderRun.purpose interpretation.
APPRAISAL_PURPOSE), is a run of this table too, by the same one classifier (adapter.classify), so a HOLD set by either
pass's answer - auth, permission, quota (a bare 429 and a 402 included) or a substituted model - stops every request of
BOTH passes, installation-wide (``paused_reason`` names no purpose), and one release ends it. What differs is only
where a refused reading is recorded (FINAL-V2 7.5): pass 1's in its EventInventory row, 'refused'; pass 2's on its own
run, with no inventory row - its answer refused by contract/appraise_read, or an appraisal settle refuses as unhealthy
(3.2.6) - so ``classify_run`` and ``settle`` take it as ``refused``. Either is a definite failure with the recorded
retry door; neither changes a hold, a failure or a cut-off answer (MAX_TOKENS: TOO_LONG, never re-sent for a member).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from django.db import IntegrityError, transaction
from django.db.models import Q

from studio import interpretation
from studio.interpretation import adapter
from studio.models import EventInventory, InterpreterHold, InterpreterHoldRelease, ProviderRun

AUTH, PERMISSION, QUOTA, MODEL = InterpreterHold.AUTH, InterpreterHold.PERMISSION, InterpreterHold.QUOTA, InterpreterHold.MODEL
REASONS = (AUTH, PERMISSION, QUOTA, MODEL)  # P-5 adds 'model'; adapter.HOLD_REASONS, which a test pins equal
# What each reason means, in the operator's words (the hold names its run, HTTP status and vendor status beside it).
REASON_TEXT = {
    AUTH: 'the key was refused',
    PERMISSION: 'the key may not use the model or the service',
    QUOTA: ('a quota or spending limit is exhausted (daily, zero, unbilled or not named), billing is not enabled, or a '
            'payment is required'),
    MODEL: 'an answer named a model other than the one asked for, and was not read',
}
# The runs this table classifies (ProviderRun.purpose): pass 1, and design v2's pass 2 (FINAL-V2 7.4: one classifier).
PURPOSES = (interpretation.PURPOSE, interpretation.APPRAISAL_PURPOSE)

ANSWERED, FAILED, TOO_LONG, HOLD, UNKNOWN, NONE = 'answered', 'failed', 'too_long', 'hold', 'unknown', 'none'
EFFECTS = (ANSWERED, FAILED, TOO_LONG, HOLD, UNKNOWN, NONE)
# adapter.classify's kinds, each the effect of the same name (the adapter's verdict is never changed, only composed with
# what the adapter cannot know: whether the run's outcome is known at all, and whether its reading was refused)
_EFFECT_OF = {adapter.ANSWERED: ANSWERED, adapter.FAILED: FAILED, adapter.TOO_LONG: TOO_LONG, adapter.HOLD: HOLD}

# ProviderRun.scope['held'] of an interpret stage that sent nothing because the interpreter is paused (FINAL 6.3 step 3)
HELD_DISABLED, HELD_HOLD = 'interpreter_disabled', 'interpreter_hold'
PAUSED_MESSAGE = ('Reading documented procedures is paused on this installation. Nothing was sent. Resume once it is '
                  'available again.')
DISABLED = 'disabled'  # the settings.GEMINI_MODE that sends nothing
UNKNOWN_WHY = 'Whether the request reached the interpreter is not known; it is reconciled, never sent again unasked.'
REFUSED_WHY = 'The interpretation was not used: its answer could not be read.'
APPRAISAL_REFUSED_WHY = 'The appraisal was not used: its answer could not be read.'  # design v2's pass 2

MAX_NOTE_CHARS = 2000
_UNSTORABLE = re.compile('[\x00\ud800-\udfff]')  # PostgreSQL text holds no NUL; a lone surrogate cannot be encoded


@dataclass(frozen=True)
class Outcome:
    """What one interpretation run's outcome means (the table above). ``verdict`` is adapter.classify's Classification,
    unchanged (None when the outcome is UNKNOWN or NONE: the adapter classifies only a definite outcome). ``why`` is CPT
    Studio's sentence; it repeats nothing a model wrote and names no provider or model."""
    effect: str
    verdict: Optional[adapter.Classification] = None
    why: str = ''

    def __post_init__(self):
        if self.effect not in EFFECTS:
            raise ValueError(f'An outcome is one of {", ".join(EFFECTS)}.')
        if (self.verdict is None) != (self.effect in (UNKNOWN, NONE)):
            raise ValueError('Only an outcome that is not known, or a run with no outcome, has no classification.')
        if self.effect == HOLD and (self.verdict.kind != adapter.HOLD or self.verdict.hold not in REASONS):
            raise ValueError(f'A hold is the classification of a hold, with one reason of {", ".join(REASONS)}.')

    @property
    def reason(self) -> str:
        """The hold's reason (one of REASONS) when the effect is HOLD, else ''."""
        return self.verdict.hold if self.effect == HOLD else ''

    @property
    def retry(self) -> bool:
        """Whether the recorded retry door (FINAL 11.3) is offered: for a definite failure of the attempt only. A hold is
        released by an operator, a cut-off answer is never retried for a member (C5), and an unknown outcome is
        reconciled."""
        return self.effect == FAILED


def classify(state: str, http_status=None, response_bytes=b'', *, refused=None,
             purpose: str = interpretation.PURPOSE) -> Outcome:
    """The effect of an interpretation run that ended in ``state`` (ProviderRun.state), with its HTTP status and its
    response bytes as stored. A definite outcome is adapter.classify's, exactly - the same for both passes, since the
    classifier reads the response alone. ``refused``: the answer's reading was refused - a read.Refusal, contract/
    extract_read's or contract/appraise_read's Refusal, an appraisal settle refused as unhealthy, or the run's
    EventInventory in state 'refused' - which makes a usable envelope a definite failure of the attempt; it never
    changes a hold, a failure or a cut-off answer. ``purpose``: the run's (PURPOSES), which names the pass in the
    failure's sentence when the refusal gives none of its own."""
    if purpose not in PURPOSES:
        raise ValueError(f'Only a run of {", ".join(PURPOSES)} is classified here.')
    if state == ProviderRun.UNKNOWN:
        return Outcome(UNKNOWN, why=UNKNOWN_WHY)
    verdict = adapter.classify(state, http_status, response_bytes)
    if verdict is None:
        return Outcome(NONE)
    effect = _EFFECT_OF.get(verdict.kind)
    if effect is None:
        raise ValueError(f'The adapter classified an outcome as {verdict.kind!r}, which this table does not know.')
    if effect == ANSWERED and refused is not None:
        return Outcome(FAILED, verdict, _refusal_why(refused, purpose))
    return Outcome(effect, verdict, verdict.why)


def classify_run(run, *, inventory=None, refused=None) -> Outcome:
    """classify() of a stored run of either pass (PURPOSES). ``inventory``: the EventInventory its answer was read into,
    if any - for a pass-1 run, the row whose provider run it is; for design v2's appraisal, the row whose appraisal run
    it is (a refused row binds none, FINAL-V2 6.3) - and a 'refused' row makes the answer a definite failure.
    ``refused``: a refused reading recorded elsewhere - the appraisal's, which has no inventory row (FINAL-V2 7.5):
    contract/appraise_read's Refusal, or settle's refusal of an unhealthy appraisal (3.2.6) - anything whose ``reason``
    is CPT Studio's sentence; given, it is the refusal read."""
    _check_run(run)
    if inventory is not None:
        bound = (inventory.appraisal_run_id if run.purpose == interpretation.APPRAISAL_PURPOSE
                 else inventory.provider_run_id)
        if str(bound) != str(run.pk):  # an id given as text is the same id
            raise ValueError('The inventory given was not read from this run.')
    if refused is None and inventory is not None and inventory.state == EventInventory.REFUSED:
        refused = inventory
    return classify(run.state, run.http_status, bytes(run.response_bytes or b''), refused=refused,
                    purpose=run.purpose)


def _check_run(run):
    if run.provider != interpretation.PROVIDER or run.purpose not in PURPOSES:
        raise ValueError('Only an interpretation or an appraisal run is classified here.')


def _refusal_why(refused, purpose: str = interpretation.PURPOSE) -> str:
    """The refusal's own sentence (a Refusal's reason, or the refused inventory's first recorded problem: both CPT
    Studio's words), else REFUSED_WHY - APPRAISAL_REFUSED_WHY for design v2's appraisal."""
    reason = getattr(refused, 'reason', None)
    if isinstance(reason, str) and reason.strip():
        return reason
    verification = getattr(refused, 'verification', None)
    problems = verification.get('problems') if isinstance(verification, dict) else None
    if isinstance(problems, list) and problems and isinstance(problems[0], str) and problems[0].strip():
        return problems[0]
    return APPRAISAL_REFUSED_WHY if purpose == interpretation.APPRAISAL_PURPOSE else REFUSED_WHY


# --- the hold --------------------------------------------------------------------------------------------------------------

def record(run, outcome: Outcome) -> Optional[InterpreterHold]:
    """The hold ``outcome`` (a HOLD) sets for the ANSWER ``run`` carries, with what adapter.classify read from it: the
    reason, the HTTP status, the vendor status and the violations (P-3, P-4), unchanged, recorded against the run that
    was sent. One answer sets at most one hold, whichever run carries it:
    - settling a run again (a stale sweep, a second worker) returns the hold its answer already set, released or not;
    - a reuse (jobs' reuse doors: nothing sent, the earlier run's bytes copied, reused_from that run) carries its
      origin's answer, so it returns the hold that answer set, released or not, and never sets another: an operator's
      release of a hold is not undone by re-reading the answer that set it;
    - a run that was not sent sets no hold of its own (it paid nothing; the answer's hold, if any, was its origin's), and
      returns None when its origin set none.
    Concurrent settlements of one answer are serialized on the origin run's row. A run of either pass sets the same
    installation-wide hold, which stops every request of both passes (``paused_reason``)."""
    if outcome.effect != HOLD:
        raise ValueError('Only a hold outcome records a hold.')
    _check_run(run)
    origin = run.reused_from_id or run.pk
    verdict = outcome.verdict
    with transaction.atomic():
        ProviderRun.objects.select_for_update().filter(pk=origin).exists()
        existing = (InterpreterHold.objects.filter(Q(run_id=origin) | Q(run__reused_from_id=origin))
                    .order_by('created_at', 'pk').first())
        if existing is not None or not run.sent:
            return existing
        return InterpreterHold.objects.create(
            reason=verdict.hold, http_status=verdict.http_status, vendor_status=verdict.vendor_status,
            violations=[dict(item) for item in verdict.violations], run=run)


def settle(run, *, inventory=None, refused=None) -> tuple:
    """(outcome, hold): classify_run(run) - with ``inventory`` and ``refused`` as it takes them - and the STANDING hold
    its answer set - None when the outcome is not a hold, when that hold was released, or for an unsent copy of an
    answer whose origin set none. A HOLD outcome with no standing hold is still an answer that is never read (P-5: a
    substituted model), so the caller must not read it; only the installation is not paused by it any more."""
    outcome = classify_run(run, inventory=inventory, refused=refused)
    if outcome.effect != HOLD:
        return outcome, None
    hold = record(run, outcome)
    return outcome, (hold if hold is not None and not _has_release(hold) else None)


def active():
    """Every standing hold, oldest first: a hold no release names."""
    return InterpreterHold.objects.filter(release__isnull=True).order_by('created_at', 'pk')


def current() -> Optional[InterpreterHold]:
    """The newest standing hold, or None."""
    return InterpreterHold.objects.filter(release__isnull=True).order_by('-created_at', '-pk').first()


def is_held() -> bool:
    return active().exists()


def mode() -> str:
    """THIS PROCESS's configured interpreter mode (settings.GEMINI_MODE, validated when the settings load); 'disabled'
    when none is configured. Never the installation's: each process has its own, and a one-shot's is 'disabled' unless
    it is given one."""
    from django.conf import settings

    return getattr(settings, 'GEMINI_MODE', DISABLED) or DISABLED


def paused_reason() -> Optional[str]:
    """Why an interpret stage run in THIS process may build no request now (FINAL 6.3 step 3; 11.2): HELD_DISABLED when
    this process's mode is 'disabled', HELD_HOLD while a hold stands (installation-wide), else None. The worker asks it
    for its own stages."""
    if mode() == DISABLED:
        return HELD_DISABLED
    if is_held():
        return HELD_HOLD
    return None


def clean_note(text) -> str:
    """A release's note as recorded: stripped; refused when empty, too long or not storable."""
    note = str(text or '').strip()
    if not note:
        raise ValueError('A release needs a note saying why the hold may end.')
    if len(note) > MAX_NOTE_CHARS:
        raise ValueError(f'The note can be at most {MAX_NOTE_CHARS} characters.')
    if _UNSTORABLE.search(note):
        raise ValueError('The note contains a NUL character or an invalid Unicode code point.')
    return note


def release(*, user, note) -> list:
    """End every standing hold, each with its own InterpreterHoldRelease naming ``user`` and ``note`` (the hold rows
    stay). ``user`` must be an operator now: an active account holding an operator grant no revocation ended. Returns
    the releases recorded, oldest hold first; [] when no hold stood. A hold a concurrent release ended meanwhile is
    skipped, never released twice (the release is one-to-one with its hold)."""
    from studio import operator

    note = clean_note(note)
    if not operator.is_operator(user):
        raise PermissionError('Only an operator may release the interpreter hold.')
    out = []
    with transaction.atomic():
        for hold in list(active()):
            try:
                with transaction.atomic():
                    out.append(InterpreterHoldRelease.objects.create(hold=hold, released_by=user, note=note))
            except IntegrityError:  # released by a concurrent command since it was read
                continue
    return out


def as_json(hold: InterpreterHold) -> dict:
    """One hold as the operator's report reads it: ids, reason, statuses and counts; never the release note."""
    released = getattr(hold, 'release', None) if _has_release(hold) else None
    return {'id': str(hold.pk), 'reason': hold.reason, 'means': REASON_TEXT.get(hold.reason, 'an unrecorded reason'),
            'http_status': hold.http_status, 'vendor_status': hold.vendor_status,
            'violations': len(hold.violations or []), 'run': str(hold.run_id), 'set_at': hold.created_at.isoformat(),
            'released_at': released.created_at.isoformat() if released is not None else None,
            'released_by': released.released_by.username if released is not None else None}


def _has_release(hold) -> bool:
    try:
        return hold.release is not None
    except InterpreterHoldRelease.DoesNotExist:
        return False


def state() -> dict:
    """The interpreter state for the operator, in its two scopes, named apart:
    - INSTALLATION-WIDE (stored rows, the same in every process): 'held', whether a hold stands, and 'standing', every
      standing hold;
    - THIS PROCESS only: 'process_mode', its own settings.GEMINI_MODE, and 'process_paused', why an interpret stage run
      here would build no request (paused_reason), with the paused message. A one-shot's mode is not the worker's."""
    standing = [as_json(hold) for hold in active().select_related('run')]
    process_mode = mode()
    paused = HELD_DISABLED if process_mode == DISABLED else HELD_HOLD if standing else None
    return {'held': bool(standing), 'standing': standing, 'process_mode': process_mode, 'process_paused': paused,
            'message': PAUSED_MESSAGE if paused else ''}


def describe(hold: InterpreterHold) -> str:
    """One line for an operator: the hold, its reason in words, what the response said and the run that set it."""
    status = f'HTTP {hold.http_status}' if hold.http_status is not None else 'no HTTP status'
    vendor = f', {hold.vendor_status}' if hold.vendor_status else ''
    violations = len(hold.violations or [])
    quota = f', {violations} quota violation{"s" if violations != 1 else ""}' if violations else ''
    return (f'hold {hold.pk}: {hold.reason} ({REASON_TEXT.get(hold.reason, "an unrecorded reason")}); '
            f'{status}{vendor}{quota}; run {hold.run_id}; set {hold.created_at.isoformat()}')
