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

AMENDMENT-2 (docs/gemini-migration/AMENDMENT-2.md 1.5, as its refutation revised it; DECISIONS D275, D279; step F1): the
interpreter is Claude Fable 5.2, and a stored run is classified by the adapter that recorded it - ``classify`` takes the
run's ``adapter_version`` and dispatches to fable_adapter.classify for ADAPTER_VERSION_V3 and to adapter.classify for the
Gemini versions (one classifier per adapter, each reading the response alone), and ``classify_run`` passes the run's
own. A caller that names no version is read as the dormant Gemini adapter's, the unchanged callers' reading (studio/
jobs.py until step F6 passes run.adapter_version). The table gains two reasons: REFUSED (a 400 or another 4xx on a body
the adapter pins: a refusal of every request of the version or of the account) and DECLINED (the model declined to
answer: never read, never re-asked of another model, D275). Three rules are added:
- ``record`` sets a hold only for a run of the CURRENT adapter version - the one the reading stages send now,
  jobs._reading_adapter_version (AMENDMENT-2 section 9: the _V3 names, and v1's under the test-only v1 chain) - so a
  stored run of another version returns the hold its answer set, if any, and never sets one: a Gemini quota answer
  never pauses Fable (DECISIONS D289, G2-02: no stored Gemini or v1 run is a source of a new hold).
- A hold is REQUEST-BOUND (``request_bound``) when the answer that set it began as a 200 stream and says something
  about that request rather than about the account, the version or the model: a decline, or a hold an error event set
  after message_start [R:connector-CONN-1]. Its release ends the installation's pause, never the block on its request:
  jobs' failed-before door returns such a run for its own identical request, and only an operator's recorded override
  sends it once (step F6). Every other hold releases as before.
- ``release`` ends every standing hold as before, and ``release_report`` names each with its reason, run, encounter and
  the first 16 hex of the run's request sha256, saying for a request-bound one that its request stays blocked for
  members; ``interpreter_hold --release`` prints it.
A Fable hold's vendor status is the Anthropic error type or the refusal category (lowercase, at most 40 characters);
its violations stay [].
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Any, Optional, cast

from django.db import IntegrityError, transaction  # type: ignore[import-untyped]
from django.db.models import Q  # type: ignore[import-untyped]

from studio import interpretation
from studio.interpretation import adapter, fable_adapter
from studio.models import EventInventory, InterpreterHold, InterpreterHoldRelease, ProviderExchange, ProviderRun

AUTH, PERMISSION, QUOTA, MODEL = InterpreterHold.AUTH, InterpreterHold.PERMISSION, InterpreterHold.QUOTA, InterpreterHold.MODEL
REFUSED, DECLINED = InterpreterHold.REFUSED, InterpreterHold.DECLINED  # AMENDMENT-2 1.5
# the union of adapter.HOLD_REASONS (Gemini's: P-5 adds 'model') and fable_adapter.HOLD_REASONS (Fable's: 'refused' and
# 'declined' added), which a test pins
REASONS = (AUTH, PERMISSION, QUOTA, MODEL, REFUSED, DECLINED)
# What each reason means, in the operator's words (the hold names its run, HTTP status and vendor status beside it).
REASON_TEXT = {
    AUTH: 'the key was refused',
    PERMISSION: 'the key may not use the model or the service',
    QUOTA: ('a quota or spending limit is exhausted (daily, zero, unbilled or not named), billing is not enabled, or a '
            'payment is required'),
    MODEL: 'an answer named a model other than the one asked for, and was not read',
    REFUSED: 'requests of this version were refused as invalid',
    DECLINED: 'the model declined to answer a request; it was not read and nothing was re-asked of another model',
}
# The runs this table classifies (ProviderRun.purpose): pass 1, and design v2's pass 2 (FINAL-V2 7.4: one classifier).
PURPOSES = (interpretation.PURPOSE, interpretation.APPRAISAL_PURPOSE)
# The adapter that recorded a run classifies it (AMENDMENT-2 1.5; refute-cb-r1 CB1-1): by its adapter version, each
# version with its provider (interpretation.READ_PROVIDERS: Fable's runs and the stored runs of Gemini). The module's
# classify is read at call time, so the one classifier of each adapter is the one in force.
CLASSIFIERS: Mapping[str, ModuleType] = MappingProxyType({
    interpretation.ADAPTER_VERSION: adapter, interpretation.ADAPTER_VERSION_V2: adapter,
    interpretation.ADAPTER_VERSION_V3: fable_adapter})
VERSION_PROVIDERS: Mapping[str, str] = MappingProxyType({
    interpretation.ADAPTER_VERSION: interpretation.PROVIDER, interpretation.ADAPTER_VERSION_V2: interpretation.PROVIDER,
    interpretation.ADAPTER_VERSION_V3: interpretation.PROVIDER_V3})
GEMINI = interpretation.ADAPTER_VERSION_V2  # the version a caller that names none is read as (jobs, until step F6)

ANSWERED, FAILED, TOO_LONG, HOLD, UNKNOWN, NONE = 'answered', 'failed', 'too_long', 'hold', 'unknown', 'none'
EFFECTS = (ANSWERED, FAILED, TOO_LONG, HOLD, UNKNOWN, NONE)
# the adapters' classify kinds, each the effect of the same name (an adapter's verdict is never changed, only composed
# with what an adapter cannot know: whether the run's outcome is known at all, and whether its reading was refused)
_EFFECT_OF = {adapter.ANSWERED: ANSWERED, adapter.FAILED: FAILED, adapter.TOO_LONG: TOO_LONG, adapter.HOLD: HOLD}

# ProviderRun.scope['held'] of an interpret stage that sent nothing because the interpreter is paused (FINAL 6.3 step 3)
HELD_DISABLED, HELD_HOLD = 'interpreter_disabled', 'interpreter_hold'
PAUSED_MESSAGE = ('Reading documented procedures is paused on this installation. Nothing was sent. Resume once it is '
                  'available again.')
DISABLED = 'disabled'  # the settings.GEMINI_MODE that sends nothing
UNKNOWN_WHY = 'Whether the request reached the interpreter is not known; it is reconciled, never sent again unasked.'
REFUSED_WHY = 'The interpretation was not used: its answer could not be read.'
APPRAISAL_REFUSED_WHY = 'The appraisal was not used: its answer could not be read.'  # design v2's pass 2
# AMENDMENT-2 1.5 [R:connector-CONN-1]: what the release report says of a request-bound hold's request, and of another's
BLOCKED = ("its request stays blocked for members: a Resume or a Retry does not send it again, and only an operator's "
           'recorded override sends it once')
UNBLOCKED = "a member's next Resume may send its request again"

MAX_NOTE_CHARS = 2000
_UNSTORABLE = re.compile('[\x00\ud800-\udfff]')  # PostgreSQL text holds no NUL; a lone surrogate cannot be encoded
_REQUEST_HEX = 16  # the first hex of a run's request sha256 the release report names


@dataclass(frozen=True)
class Outcome:
    """What one interpretation run's outcome means (the table above). ``verdict`` is the recording adapter's
    Classification, unchanged (None when the outcome is UNKNOWN or NONE: an adapter classifies only a definite outcome).
    ``why`` is CPT Studio's sentence; it repeats nothing a model wrote and names no provider or model."""
    effect: str
    verdict: Optional[adapter.Classification] = None
    why: str = ''

    def __post_init__(self) -> None:
        if self.effect not in EFFECTS:
            raise ValueError(f'An outcome is one of {", ".join(EFFECTS)}.')
        if (self.verdict is None) != (self.effect in (UNKNOWN, NONE)):
            raise ValueError('Only an outcome that is not known, or a run with no outcome, has no classification.')
        if self.effect == HOLD and (self.verdict is None or self.verdict.kind != adapter.HOLD
                                    or self.verdict.hold not in REASONS):
            raise ValueError(f'A hold is the classification of a hold, with one reason of {", ".join(REASONS)}.')

    @property
    def reason(self) -> str:
        """The hold's reason (one of REASONS) when the effect is HOLD, else ''."""
        return self.verdict.hold if self.effect == HOLD and self.verdict is not None else ''

    @property
    def retry(self) -> bool:
        """Whether the recorded retry door (FINAL 11.3) is offered: for a definite failure of the attempt only. A hold is
        released by an operator, a cut-off answer is never retried for a member (C5), and an unknown outcome is
        reconciled."""
        return self.effect == FAILED


def classifier(adapter_version: object) -> Callable[[str, object, object], Optional[adapter.Classification]]:
    """The classify of the adapter that records runs of ``adapter_version`` (AMENDMENT-2 1.5): fable_adapter's for
    ADAPTER_VERSION_V3, adapter's for the Gemini versions. ValueError for any other: a run is never classified by an
    adapter that did not record it."""
    found = CLASSIFIERS.get(adapter_version) if isinstance(adapter_version, str) else None
    if found is None:
        raise ValueError('Only a run of an interpreter adapter version is classified here.')
    return cast(Callable[[str, object, object], Optional[adapter.Classification]], found.classify)


def classify(state: str, http_status: object = None, response_bytes: object = b'', *, refused: object = None,
             purpose: str = interpretation.PURPOSE, adapter_version: str = GEMINI) -> Outcome:
    """The effect of an interpretation run that ended in ``state`` (ProviderRun.state), with its HTTP status and its
    response bytes as stored. A definite outcome is the classification of the adapter that recorded the run
    (``adapter_version``: classifier), exactly - the same for both passes, since each classifier reads the response
    alone; a caller that names no version is read as the dormant Gemini adapter's (GEMINI). ``refused``: the answer's
    reading was refused - a read.Refusal, contract/extract_read's or contract/appraise_read's Refusal, an appraisal
    settle refused as unhealthy, or the run's EventInventory in state 'refused' - which makes a usable envelope a
    definite failure of the attempt; it never changes a hold, a failure or a cut-off answer. ``purpose``: the run's
    (PURPOSES), which names the pass in the failure's sentence when the refusal gives none of its own."""
    if purpose not in PURPOSES:
        raise ValueError(f'Only a run of {", ".join(PURPOSES)} is classified here.')
    classify_by = classifier(adapter_version)
    if state == ProviderRun.UNKNOWN:
        return Outcome(UNKNOWN, why=UNKNOWN_WHY)
    verdict = classify_by(state, http_status, response_bytes)
    if verdict is None:
        return Outcome(NONE)
    effect = _EFFECT_OF.get(verdict.kind)
    if effect is None:
        raise ValueError(f'The adapter classified an outcome as {verdict.kind!r}, which this table does not know.')
    if effect == ANSWERED and refused is not None:
        return Outcome(FAILED, verdict, _refusal_why(refused, purpose))
    return Outcome(effect, verdict, verdict.why)


def classify_run(run: Any, *, inventory: Any = None, refused: object = None) -> Outcome:
    """classify() of a stored run of either pass (PURPOSES), by the adapter that recorded it (its adapter_version).
    ``inventory``: the EventInventory its answer was read into, if any - for a pass-1 run, the row whose provider run it
    is; for design v2's appraisal, the row whose appraisal run it is (a refused row binds none, FINAL-V2 6.3) - and a
    'refused' row makes the answer a definite failure. ``refused``: a refused reading recorded elsewhere - the
    appraisal's, which has no inventory row (FINAL-V2 7.5): contract/appraise_read's Refusal, or settle's refusal of an
    unhealthy appraisal (3.2.6) - anything whose ``reason`` is CPT Studio's sentence; given, it is the refusal read."""
    _check_run(run)
    if inventory is not None:
        bound = (inventory.appraisal_run_id if run.purpose == interpretation.APPRAISAL_PURPOSE
                 else inventory.provider_run_id)
        if str(bound) != str(run.pk):  # an id given as text is the same id
            raise ValueError('The inventory given was not read from this run.')
    if refused is None and inventory is not None and inventory.state == EventInventory.REFUSED:
        refused = inventory
    return classify(run.state, run.http_status, bytes(run.response_bytes or b''), refused=refused,
                    purpose=run.purpose, adapter_version=run.adapter_version)


def _check_run(run: Any) -> None:
    """ValueError unless ``run`` is a run of either pass (PURPOSES) of an interpreter provider (interpretation.
    READ_PROVIDERS: Fable's runs, and the stored runs of Gemini) at an adapter version of that provider."""
    if (run.provider not in interpretation.READ_PROVIDERS or run.purpose not in PURPOSES
            or VERSION_PROVIDERS.get(run.adapter_version, run.provider) != run.provider):
        raise ValueError('Only an interpretation or an appraisal run is classified here.')


def _refusal_why(refused: object, purpose: str = interpretation.PURPOSE) -> str:
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

def current_adapter_version() -> str:
    """The adapter version of the runs the reading stages send now - studio/jobs.py's own reading of it,
    jobs._reading_adapter_version (AMENDMENT-2 section 9: ADAPTER_VERSION_V3, and v1's under the test-only v1 chain),
    read at call time so the two never disagree. Only a run of it sets a hold (``record``)."""
    from studio import jobs

    reading: Callable[[], object] = jobs._reading_adapter_version
    return str(reading())


def record(run: Any, outcome: Outcome) -> Optional[InterpreterHold]:
    """The hold ``outcome`` (a HOLD) sets for the ANSWER ``run`` carries, with what the recording adapter's
    classification read from it: the reason, the HTTP status, the vendor status and the violations (P-3, P-4),
    unchanged, recorded against the run that was sent. One answer sets at most one hold, whichever run carries it:
    - settling a run again (a stale sweep, a second worker) returns the hold its answer already set, released or not;
    - a reuse (jobs' reuse doors: nothing sent, the earlier run's bytes copied, reused_from that run) carries its
      origin's answer, so it returns the hold that answer set, released or not, and never sets another: an operator's
      release of a hold is not undone by re-reading the answer that set it;
    - a run that was not sent sets no hold of its own (it paid nothing; the answer's hold, if any, was its origin's), and
      returns None when its origin set none;
    - AMENDMENT-2 1.5: a stored run of another adapter version than the current one (current_adapter_version) returns
      the hold its answer set, if any, and never sets one - a Gemini quota answer never pauses Fable (D289, G2-02).
    Concurrent settlements of one answer are serialized on the origin run's row. A run of either pass sets the same
    installation-wide hold, which stops every request of both passes (``paused_reason``)."""
    if outcome.effect != HOLD or outcome.verdict is None:
        raise ValueError('Only a hold outcome records a hold.')
    _check_run(run)
    origin = run.reused_from_id or run.pk
    verdict = outcome.verdict
    with transaction.atomic():
        ProviderRun.objects.select_for_update().filter(pk=origin).exists()
        existing = _answer_hold(origin)
        if existing is not None or not run.sent or run.adapter_version != current_adapter_version():
            return existing
        return cast(InterpreterHold, InterpreterHold.objects.create(
            reason=verdict.hold, http_status=verdict.http_status, vendor_status=verdict.vendor_status,
            violations=[dict(item) for item in verdict.violations], run=run))


def _answer_hold(origin: object) -> Optional[InterpreterHold]:
    """The hold the answer of run ``origin`` set - on that run or on any reuse of it - released or not, else None."""
    return cast(Optional[InterpreterHold],
                InterpreterHold.objects.filter(Q(run_id=origin) | Q(run__reused_from_id=origin))
                .order_by('created_at', 'pk').first())


def hold_of(run: Any) -> Optional[InterpreterHold]:
    """The hold the answer ``run`` carries set, released or not (one answer sets at most one: ``record``), else None."""
    return _answer_hold(run.reused_from_id or run.pk)


def request_bound(hold: InterpreterHold) -> bool:
    """Whether ``hold`` is request-bound (AMENDMENT-2 1.5 [R:connector-CONN-1]): the answer that set it began as a 200
    stream of ADAPTER_VERSION_V3 and says something about that request rather than about the account, the version or the
    model - reason DECLINED (stop_reason refusal), or any hold an error event set after message_start
    (fable_adapter.request_bound over the run's kept answer). A 200 hold that is not the model's and not a decline came
    from an error event; when its bytes cannot be read the hold is read as request-bound (fail-closed: its request stays
    blocked). Every other hold - a 401, 402, 403, 404 or 400 body, an unnamed 429, a substituted model, any Gemini hold -
    is about the account, the version or the model: its release lets the next Resume send, as before."""
    run = hold.run
    if run.adapter_version != interpretation.ADAPTER_VERSION_V3:
        return False
    if hold.reason == DECLINED:
        return True
    if hold.reason == MODEL or hold.http_status != 200:
        return False
    raw = _answer_bytes(run)
    return not raw or fable_adapter.request_bound(200, raw)


def request_bound_run(run: Any) -> bool:
    """Whether ``run``'s own answer sets a request-bound hold - read from the run as stored, whether or not a hold row
    exists (a reuse's, or one record kept from setting): a run of ADAPTER_VERSION_V3 whose outcome is a HOLD that
    fable_adapter.request_bound reads as a decline or an error event after message_start, or the hold its answer set when
    that is request-bound. What jobs' failed-before door, retry_target and retry_reading read (step F6)."""
    hold = hold_of(run)
    if hold is not None and request_bound(hold):
        return True
    if run.adapter_version != interpretation.ADAPTER_VERSION_V3 or run.state != ProviderRun.SUCCEEDED:
        return False
    raw = _answer_bytes(run)
    return classify_run(run).effect == HOLD and bool(raw) and fable_adapter.request_bound(run.http_status, raw)


def _answer_bytes(run: Any) -> bytes:
    """The answer ``run`` keeps: its own response bytes, else its one turn-1 exchange's whose sha256 checks and which
    answers the run's own request (an answer kept only in its exchange: jobs._turn_one_exchange's rule), else b''."""
    own = bytes(run.response_bytes or b'')
    if own:
        return own
    exchanges = list(ProviderExchange.objects.filter(run_id=run.pk).order_by('turn')[:2])
    if len(exchanges) != 1:
        return b''
    exchange = exchanges[0]
    data = bytes(exchange.response_bytes or b'')
    if (exchange.turn != 1 or not data or hashlib.sha256(data).hexdigest() != exchange.response_sha256
            or exchange.request_sha256 != run.request_sha256):
        return b''
    return data


def settle(run: Any, *, inventory: Any = None, refused: object = None) -> tuple[Outcome, Optional[InterpreterHold]]:
    """(outcome, hold): classify_run(run) - with ``inventory`` and ``refused`` as it takes them - and the STANDING hold
    its answer set - None when the outcome is not a hold, when that hold was released, for an unsent copy of an answer
    whose origin set none, or for a stored run of another adapter version whose answer set none. A HOLD outcome with no
    standing hold is still an answer that is never read (P-5: a substituted model; a decline), so the caller must not
    read it; only the installation is not paused by it any more."""
    outcome = classify_run(run, inventory=inventory, refused=refused)
    if outcome.effect != HOLD:
        return outcome, None
    hold = record(run, outcome)
    return outcome, (hold if hold is not None and not _has_release(hold) else None)


def active() -> Any:
    """Every standing hold, oldest first: a hold no release names."""
    return InterpreterHold.objects.filter(release__isnull=True).order_by('created_at', 'pk')


def current() -> Optional[InterpreterHold]:
    """The newest standing hold, or None."""
    return cast(Optional[InterpreterHold],
                InterpreterHold.objects.filter(release__isnull=True).order_by('-created_at', '-pk').first())


def is_held() -> bool:
    return bool(active().exists())


def mode() -> str:
    """THIS PROCESS's configured interpreter mode (settings.GEMINI_MODE, validated when the settings load); 'disabled'
    when none is configured. Never the installation's: each process has its own, and a one-shot's is 'disabled' unless
    it is given one."""
    from django.conf import settings  # type: ignore[import-untyped]

    return cast(str, getattr(settings, 'GEMINI_MODE', DISABLED) or DISABLED)


def paused_reason() -> Optional[str]:
    """Why an interpret stage run in THIS process may build no request now (FINAL 6.3 step 3; 11.2): HELD_DISABLED when
    this process's mode is 'disabled', HELD_HOLD while a hold stands (installation-wide), else None. The worker asks it
    for its own stages."""
    if mode() == DISABLED:
        return HELD_DISABLED
    if is_held():
        return HELD_HOLD
    return None


def clean_note(text: object) -> str:
    """A release's note as recorded: stripped; refused when empty, too long or not storable."""
    note = str(text or '').strip()
    if not note:
        raise ValueError('A release needs a note saying why the hold may end.')
    if len(note) > MAX_NOTE_CHARS:
        raise ValueError(f'The note can be at most {MAX_NOTE_CHARS} characters.')
    if _UNSTORABLE.search(note):
        raise ValueError('The note contains a NUL character or an invalid Unicode code point.')
    return note


def release(*, user: Any, note: object) -> list[InterpreterHoldRelease]:
    """End every standing hold, each with its own InterpreterHoldRelease naming ``user`` and ``note`` (the hold rows
    stay). ``user`` must be an operator now: an active account holding an operator grant no revocation ended. Returns
    the releases recorded, oldest hold first - each names its hold, whose reason, run, encounter and request
    ``release_report`` reads; [] when no hold stood. A hold a concurrent release ended meanwhile is skipped, never
    released twice (the release is one-to-one with its hold). A request-bound hold's release ends the installation's
    pause, never the block on its request (AMENDMENT-2 1.5 [R:connector-CONN-1])."""
    from studio import operator

    clean = clean_note(note)
    if not operator.is_operator(user):
        raise PermissionError('Only an operator may release the interpreter hold.')
    out: list[InterpreterHoldRelease] = []
    with transaction.atomic():
        for hold in list(active()):
            try:
                with transaction.atomic():
                    out.append(InterpreterHoldRelease.objects.create(hold=hold, released_by=user, note=clean))
            except IntegrityError:  # released by a concurrent command since it was read
                continue
    return out


def release_report(item: Any) -> dict[str, Any]:
    """What a release ended (AMENDMENT-2 1.5 [R:connector-CONN-1]), for the operator: the hold, its reason in words, the
    run that set it, that run's encounter, the first 16 hex of the run's request sha256, and whether the hold is
    request-bound - whether its request stays blocked for members after the release (BLOCKED) or a member's next
    Resume may send it again (UNBLOCKED). ``item`` is an InterpreterHoldRelease (``release`` returns them) or the hold."""
    hold = getattr(item, 'hold', item)
    run = hold.run
    bound = request_bound(hold)
    return {'hold': str(hold.pk), 'reason': hold.reason, 'means': REASON_TEXT.get(hold.reason, 'an unrecorded reason'),
            'run': str(run.pk), 'encounter': str(run.encounter_id),
            'request': str(run.request_sha256 or '')[:_REQUEST_HEX], 'request_bound': bound,
            'members': BLOCKED if bound else UNBLOCKED}


def released_line(item: Any) -> str:
    """One line of release_report for the operator: the hold, its reason, its run, encounter and request, and what
    members may now send."""
    found = release_report(item)
    return (f'hold {found["hold"]} ({found["reason"]}): run {found["run"]} of encounter {found["encounter"]}, request '
            f'{found["request"] or "(none recorded)"}; {found["members"]}')


def as_json(hold: InterpreterHold) -> dict[str, Any]:
    """One hold as the operator's report reads it: ids, reason, statuses and counts; never the release note."""
    released = getattr(hold, 'release', None) if _has_release(hold) else None
    return {'id': str(hold.pk), 'reason': hold.reason, 'means': REASON_TEXT.get(hold.reason, 'an unrecorded reason'),
            'http_status': hold.http_status, 'vendor_status': hold.vendor_status,
            'violations': len(hold.violations or []), 'run': str(hold.run_id), 'set_at': hold.created_at.isoformat(),
            'released_at': released.created_at.isoformat() if released is not None else None,
            'released_by': released.released_by.username if released is not None else None}


def _has_release(hold: Any) -> bool:
    try:
        return hold.release is not None
    except InterpreterHoldRelease.DoesNotExist:
        return False


def state() -> dict[str, Any]:
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
