"""The installation-wide provider holds of Corti, Astra and Fable (FINAL-V2 amendment 1, A16 and A20; its 7.3, adopted as
DECISIONS D208): what a run of one of those providers means for its provider (``classify``, ``classify_run``,
``classify_exchange``), the hold it sets (``record``), whether one stands (``active``, ``held``), the test of a run that
set one (``sets_hold``) and the recorded release (``release``).

ONE CLASSIFICATION (A20). It is read from the RECORDED fields of a run or of a participant's exchange - its HTTP status
and whether it was sent - and never from an error text or a response body:

| a run of                      | sets that provider's hold when                                   | reason                     |
|-------------------------------|------------------------------------------------------------------|----------------------------|
| Corti (``corti``, ``replay``) | it was sent and the coding service answered 401, 402, 403 or 429 | 402, 429: quota; 403:      |
|                               | (Corti's 429s are not classified finer: fail-closed)             | permission; 401: auth      |
| Corti                         | it was NOT sent and carries an HTTP status: its token endpoint   | 402, 429: quota; 403:      |
|                               | answered that status, which ``providers.corti`` records on the   | permission; every other    |
|                               | not-sent exchange; any 4xx (the token request carries only the   | 4xx: auth                  |
|                               | installation's credentials, so no 4xx of it is request-specific) |                            |
| Astra, Fable                  | a sent exchange of the run answered any 4xx but 413 (fail-closed:| 401: auth; 403: permission;|
|                               | a vendor's payment refusal may arrive under another status)      | 402, 429: quota; other:    |
|                               |                                                                  | refused                    |

Everything else sets no hold: a token endpoint's 5xx or redirect, an answer that could not be read or carried no
usable token, a transport failure (the local not-sent class, AMENDMENT-1 7.1); a coding 5xx or another 4xx (a definite
failure, retried once per member act, 7.2); a participant's 413 (the request's own size, which fails that request only,
HARNESS I10) or a 5xx.

THE HOLD (A16). A hold names its provider - ``corti`` for Corti and its replay alike, or a participant's name - its
reason, the status and the run whose recorded refusal set it (for Corti's token endpoint, the run recorded not sent).
It is installation-wide, append-only, and stands until a ProviderHoldRelease names it. ONE RUN SETS AT MOST ONE HOLD, and
a reuse of a run (reused_from) sets none: settling a run again returns the hold it already set. While a provider's hold
stands, no request of that provider is sent by any encounter (every send door reads ``held``); a stored answer is still
reused. A run a hold kept unsent records ``scope.held = HELD`` and is never the outcome of a request.

A HOLD-SETTING RUN is a run a ProviderHold row names (``sets_hold``), never one read by its status alone (A20,
[R2:truth-RT2]): a refusal recorded before the install, which no row names, is still held against its identical request
by the failed-before door, and no member retries it (A10, by status: ``retry_refused``).

Imports: the models and the operator check only; no provider adapter, no document text.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from django.db import IntegrityError, transaction  # type: ignore[import-untyped]  # Django ships no type stubs

from studio.models import ProviderHold, ProviderHoldRelease, ProviderRun

CORTI, ASTRA, FABLE = 'corti', 'astra', 'fable'
# The ProviderRun.provider names each hold covers: Corti's coding service and its replay adapter are one provider (the
# replay records the same service's answers); a participant's replay keeps the participant's name.
COVERS = {'corti': CORTI, 'replay': CORTI, 'astra': ASTRA, 'fable': FABLE}
PROVIDERS = (CORTI, ASTRA, FABLE)
AUTH, PERMISSION, QUOTA, REFUSED = ProviderHold.AUTH, ProviderHold.PERMISSION, ProviderHold.QUOTA, ProviderHold.REFUSED
REASONS = (AUTH, PERMISSION, QUOTA, REFUSED)
HELD = 'provider_hold'  # scope.held of a run the hold kept unsent (AMENDMENT-1 7.3)
CODING_HOLD_STATUSES = {401: AUTH, 402: QUOTA, 403: PERMISSION, 429: QUOTA}  # Corti's coding service (A20)
TOKEN_STATUS_REASONS = {402: QUOTA, 403: PERMISSION, 429: QUOTA}  # Corti's token endpoint; any other 4xx is AUTH
PARTICIPANT_STATUS_REASONS = {401: AUTH, 402: QUOTA, 403: PERMISSION, 429: QUOTA}  # any other 4xx but 413: REFUSED
NOT_A_HOLD = 413  # a participant's request too large: that request's own failure (HARNESS I10), never a hold
REFUSED_BEFORE_STATUSES = frozenset({401, 402, 403, 429})  # A10: never retried by a member, read by status alone
MAX_NOTE_CHARS = 2000
REASON_TEXT = {AUTH: 'the provider refused the installation\'s credentials',
               PERMISSION: 'the provider refused the installation permission for the request',
               QUOTA: 'the provider refused for payment or quota',
               REFUSED: 'the provider refused the request in a way that may hold for every request'}


@dataclass(frozen=True)
class Refusal:
    """What a run means for its provider (A20): the provider whose hold it sets, the reason and the HTTP status."""
    provider: str
    reason: str
    http_status: int


def provider_of(name: object) -> Optional[str]:
    """The provider a hold of a run of ProviderRun.provider ``name`` covers (COVERS), or None for any other provider
    (Gemini's runs: interpretation.holds)."""
    return COVERS.get(name) if isinstance(name, str) else None


def _status(value: object) -> Optional[int]:
    return value if type(value) is int else None


def classify(name: object, http_status: object, sent: object) -> Optional[Refusal]:
    """The refusal a run of provider ``name`` with the recorded ``http_status`` and ``sent`` means for its provider (the
    module's table), or None when it sets no hold. For a participant this is one exchange's status (classify_run reads
    every exchange of a participant's run)."""
    provider = provider_of(name)
    status = _status(http_status)
    if provider is None or status is None:
        return None
    if provider == CORTI:
        if sent is True:
            reason = CODING_HOLD_STATUSES.get(status)
            return Refusal(CORTI, reason, status) if reason is not None else None
        if sent is False and 400 <= status <= 499:  # a not-sent run with a status: the token endpoint answered it
            return Refusal(CORTI, TOKEN_STATUS_REASONS.get(status, AUTH), status)
        return None
    if sent is True and 400 <= status <= 499 and status != NOT_A_HOLD:
        return Refusal(provider, PARTICIPANT_STATUS_REASONS.get(status, REFUSED), status)
    return None


def classify_exchange(name: object, exchange: Any) -> Optional[Refusal]:
    """The refusal one recorded exchange of a participant's run means (its ``http_status``; sent unless its state or
    outcome is not_sent), or None."""
    state = getattr(exchange, 'outcome', None) or getattr(exchange, 'state', None)
    sent = state != ProviderRun.NOT_SENT and getattr(exchange, 'http_status', None) is not None
    return classify(name, getattr(exchange, 'http_status', None), sent)


def classify_run(run: Any, exchanges: Optional[Iterable[Any]] = None) -> Optional[Refusal]:
    """The refusal ``run`` means for its provider, or None: Corti's from the run's own recorded status and ``sent``; a
    participant's from its recorded exchanges (``exchanges`` when given, else the run's stored ones) - the first that
    refuses - and from the run's own status when it recorded none. A reuse (reused_from) sets nothing: its origin's
    outcome is its origin's."""
    provider = provider_of(getattr(run, 'provider', None))
    if provider is None or getattr(run, 'reused_from_id', None):
        return None
    if provider == CORTI:
        return classify(run.provider, run.http_status, bool(run.sent))
    found = list(exchanges) if exchanges is not None else list(run.exchanges.order_by('turn'))
    for exchange in found:
        refusal = classify_exchange(run.provider, exchange)
        if refusal is not None:
            return refusal
    if not found:
        return classify(run.provider, run.http_status, bool(run.sent))
    return None


def record(run: Any, refusal: Optional[Refusal] = None) -> Optional[ProviderHold]:
    """The hold ``run``'s recorded refusal sets (``refusal``, or classify_run(run)), or None when it sets none. One run sets
    at most one hold: recording it again returns the one it set, released or not (an operator's release is never undone
    by settling the run again); a reuse sets none. Concurrent recordings of one run are serialized on its row. Called by
    jobs._send in the transaction that records the outcome (A20 [R2:binding-R2B-1]), and by the fallback that records an
    outcome from its few fields, in a transaction of its own [R3:binding-R3B-1]."""
    if getattr(run, 'reused_from_id', None):
        return None
    found = refusal if refusal is not None else classify_run(run)
    if found is None:
        return None
    with transaction.atomic():
        ProviderRun.objects.select_for_update().filter(pk=run.pk).exists()
        existing: Optional[ProviderHold] = ProviderHold.objects.filter(run_id=run.pk).order_by('created_at', 'pk').first()
        if existing is not None:
            return existing
        made: ProviderHold = ProviderHold.objects.create(provider=found.provider, reason=found.reason,
                                                         http_status=found.http_status, run_id=run.pk)
        return made


def active(provider: Optional[str] = None) -> Any:
    """Every standing hold - one no release names - oldest first; of ``provider`` only when given (a run's provider name
    is mapped: ``replay`` is Corti's)."""
    holds = ProviderHold.objects.filter(release__isnull=True)
    if provider is not None:
        holds = holds.filter(provider=provider_of(provider) or provider)
    return holds.order_by('created_at', 'pk')


def held(provider: str) -> bool:
    """Whether a hold of ``provider`` (or of the provider a run's name maps to) stands."""
    return bool(active(provider).exists())


def current(provider: str) -> Optional[ProviderHold]:
    """The newest standing hold of ``provider``, or None."""
    found: Optional[ProviderHold] = active(provider).order_by('-created_at', '-pk').first()
    return found


def sets_hold(run: Any) -> bool:
    """Whether ``run`` is a hold-setting run: a ProviderHold row names it (A20 [R2:truth-RT2]) - never read from its
    status alone, released or not."""
    pk = getattr(run, 'pk', None)
    return pk is not None and ProviderHold.objects.filter(run_id=pk).exists()


def retry_refused(run: Any) -> bool:
    """A10's reading by STATUS (whether or not a hold row names the run): a Corti run that was sent and refused with 401,
    402, 403 or 429, or whose token endpoint answered a 4xx (recorded not sent with its status). No member retries it."""
    if provider_of(getattr(run, 'provider', None)) != CORTI:
        return False
    status = _status(getattr(run, 'http_status', None))
    if status is None:
        return False
    if getattr(run, 'sent', False):
        return status in REFUSED_BEFORE_STATUSES
    return 400 <= status <= 499


def clean_note(text: object) -> str:
    """A release's note as recorded: stripped; refused when empty, too long or not storable."""
    note = str(text or '').strip()
    if not note:
        raise ValueError('A release needs a note saying why the hold may end.')
    if len(note) > MAX_NOTE_CHARS:
        raise ValueError(f'A release note holds at most {MAX_NOTE_CHARS} characters.')
    if '\x00' in note or any(0xD800 <= ord(character) <= 0xDFFF for character in note):
        raise ValueError('A release note cannot hold NUL or a lone surrogate.')
    return note


def release(provider: str, *, user: Any, note: object) -> list[ProviderHoldRelease]:
    """End every standing hold of ``provider``, each with its own ProviderHoldRelease naming ``user`` and ``note`` (the hold
    rows stay). ``user`` must be an operator now (an active account holding an operator grant no revocation ended).
    Returns the releases recorded, oldest hold first; [] when none stood. A hold a concurrent release ended is skipped,
    never released twice. ValueError for an unknown provider or a note that cannot be recorded."""
    from studio import operator

    name = provider_of(provider) or provider
    if name not in PROVIDERS:
        raise ValueError(f'Unknown provider {provider!r}: a provider hold is Corti\'s, Astra\'s or Fable\'s.')
    text = clean_note(note)
    if not operator.is_operator(user):
        raise PermissionError('Only an operator may release a provider hold.')
    out = []
    with transaction.atomic():
        for hold in list(active(name)):
            try:
                with transaction.atomic():
                    out.append(ProviderHoldRelease.objects.create(hold=hold, released_by=user, note=text))
            except IntegrityError:  # released by a concurrent command since it was read
                continue
    return out


def as_json(hold: ProviderHold) -> dict[str, object]:
    """One hold as an operator's report reads it: ids, provider, reason, status and times; never the release note."""
    try:
        released = hold.release
    except ProviderHoldRelease.DoesNotExist:
        released = None
    return {'id': str(hold.pk), 'provider': hold.provider, 'reason': hold.reason,
            'means': REASON_TEXT.get(hold.reason, 'an unrecorded reason'), 'http_status': hold.http_status,
            'run': str(hold.run_id), 'set_at': hold.created_at.isoformat(),
            'released_at': released.created_at.isoformat() if released is not None else None}


def state() -> dict[str, object]:
    """Every standing provider hold, per provider (installation-wide stored rows)."""
    return {name: [as_json(hold) for hold in active(name)] for name in PROVIDERS}
