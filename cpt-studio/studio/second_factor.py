"""The operator's second factor (release 1, B2; RELEASE-1-SPEC 3.3 and 4, B2): the console's gate, finished in Lane 1 so
the console's gate (Lane 3) can rely on it, and the WebAuthn ceremony around it (Lane 2), which
studio.second_factor_views serves. Only those views write the session's SESSION_SECOND_FACTOR_AT, after a verified key or
recovery code (complete_sign_in, refresh).

The gate
    satisfied(request)
        True only when the request is signed in, its session was opened at the admin door (SESSION_DOOR is 'admin') and
        it carries a valid second-factor time (SESSION_SECOND_FACTOR_AT: whole seconds since the epoch, not in the
        future). A password alone, a session opened at cpt.quillmd.com, a session from before release 1 or a malformed
        marker is never satisfied.
    requires_recent_second_factor(max_age=SECOND_FACTOR_STEP_UP_SECONDS)
        a decorator for the acts that change who can see what (B2, item 5): a satisfied session whose second factor is
        older than ``max_age`` seconds is sent to /login/second-factor?next=<the console page the act's form is on>
        and the act is not done - the form is never replayed; the operator submits it again. A session that is not
        satisfied at all is answered Django's 404, as the console's gate answers it. ``max_age`` left out is
        settings.SECOND_FACTOR_STEP_UP_SECONDS, read at each request.
    Neither is applied to any console act here: Lane 3's operator_view and acts apply them.

The ceremony (py_webauthn 3.0.1; the relying party is settings.WEBAUTHN_RP_ID - the admin host exactly, never quillmd.com,
which sibling sites share - and the origin settings.WEBAUTHN_ORIGIN; user verification 'preferred', attestation 'none';
every credential row records its relying-party id)
    begin(request, user, sign_in_ref, next_url)  a checked password waits for its key: the ANONYMOUS session holds
        PENDING = {the account, when, the sign-in's reference, where to go} for SECOND_FACTOR_PENDING_SECONDS. login()
        is not called: a password alone opens nothing.
    authentication_options / verify_key  a signed challenge for the account's own keys: the challenge lives in the
        session (CHALLENGE) and is used once - taken out before anything is checked, so a replayed response meets no
        challenge; verify_authentication_response checks the challenge, the relying-party id, the origin, the stored
        public key and the signature counter, and a response made inside another origin's frame (crossOrigin) is
        refused.
    complete_sign_in(request, user, state)  only then login() runs (a new session key; studio.sessions writes the admin
        door, the times and the reference) and the session gets SESSION_SECOND_FACTOR_AT; the attempt becomes signed_in.
    note_failure  a wrong key or recovery code counts per account in RateWindow (SECOND_FACTOR_ATTEMPTS per
        SECOND_FACTOR_PENDING_SECONDS); at the limit a pending sign-in is dropped, recorded as second_factor_failed, with a
        SecurityEvent.
    use_recovery_code  a recovery code stands in for a key once: stored as Django's make_password hash.
    issue_setup_code / setup_token  setup needs a single-use code issued on the server (OneTimeToken OPERATOR_SETUP, valid
        ENROLMENT_CODE_SECONDS, stored as its sha256 only; issuing one revokes the account's earlier unused ones).
    registration_options / verify_registration  a new key, from a setup code (enrolment) or from the keys page.
    new_recovery_codes  RECOVERY_CODE_COUNT codes, shown once; the earlier unused ones are voided.
    reset(user, ...)  the server's reset of lost keys (B2, item 7): keys removed, recovery codes voided, sessions ended, a
        new setup code issued. No console path resets an operator's own factor.
Codes are typed as groups of five letters and digits (CODE_ALPHABET; no 0, 1, i, l or o), case and hyphens ignored.
Nothing here writes a code, a key or a challenge into a log, an audit row or a security event: ids and counts only.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.utils import timezone
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, parse_client_data_json
from webauthn.helpers.structs import (AttestationConveyancePreference, AuthenticatorSelectionCriteria,
                                      AuthenticatorTransport, PublicKeyCredentialDescriptor, ResidentKeyRequirement,
                                      UserVerificationRequirement)

from . import hosts, rate, request_meta, security_events, sessions, throttle
from .models import OneTimeToken, SecondFactorCredential, SecondFactorRecoveryCode, User

STEP_UP_PATH = '/login/second-factor'  # Lane 2's second-factor page on the admin host (RELEASE-1-SPEC 3.4)
CONSOLE_FRONT = '/ops/'
ACCOUNT_PAGE = '/account/'  # an operator's password change asks for the step-up too (B4, item 1)


def _age(request):
    """Seconds since the session's second factor, or None: no session, no marker, a marker that is not a positive
    finite number, or one in the future."""
    session = getattr(request, 'session', None)
    if session is None:
        return None
    at = session.get(request_meta.SESSION_SECOND_FACTOR_AT)
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at <= 0:
        return None
    age = request_meta.epoch_seconds() - at
    return age if age >= 0 else None


def satisfied(request) -> bool:
    """Whether the request's session passed the second factor at the admin door (see the module)."""
    if getattr(request, 'session', None) is None:
        return False
    if not getattr(getattr(request, 'user', None), 'is_authenticated', False):
        return False
    if request.session.get(request_meta.SESSION_DOOR) != request_meta.ADMIN:
        return False
    return _age(request) is not None


def _form_page(request) -> str:
    """Where the operator comes back to after the step-up: a GET's own page; for any other method the page its form was
    on (the Referer, when it is this host's and names a console page); else the console's front page."""
    if request.method in ('GET', 'HEAD'):
        candidate = request.get_full_path()
    else:
        try:
            parts = urlsplit(request.META.get('HTTP_REFERER', ''))
        except ValueError:
            return CONSOLE_FRONT
        if not parts.netloc or parts.netloc != request.get_host():
            return CONSOLE_FRONT
        candidate = parts.path + (f'?{parts.query}' if parts.query else '')
    return candidate if hosts.is_console_page(candidate) else CONSOLE_FRONT


def requires_recent_second_factor(view=None, *, max_age=None):
    """The step-up decorator (see the module): ``@requires_recent_second_factor()``,
    ``@requires_recent_second_factor(max_age=...)`` or bare."""
    if view is None:
        return functools.partial(requires_recent_second_factor, max_age=max_age)
    if max_age is not None and (isinstance(max_age, bool) or not isinstance(max_age, int) or max_age < 0):
        raise ValueError('max_age is a whole number of seconds.')

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not satisfied(request):
            raise Http404()
        limit = settings.SECOND_FACTOR_STEP_UP_SECONDS if max_age is None else max_age
        if _age(request) > limit:
            response = HttpResponseRedirect(f'{STEP_UP_PATH}?{urlencode({"next": _form_page(request)})}')
            if request.method not in ('GET', 'HEAD'):
                response.status_code = 303  # the browser fetches the step-up page; the act's form is not sent again
            return response
        return view(request, *args, **kwargs)
    return wrapper


def recent(request) -> bool:
    """Whether the satisfied session's second factor is within SECOND_FACTOR_STEP_UP_SECONDS (the step-up's test)."""
    age = _age(request)
    return satisfied(request) and age is not None and age <= settings.SECOND_FACTOR_STEP_UP_SECONDS


def step_up_location(next_url) -> str:
    """The step-up page, coming back to ``next_url``."""
    return f'{STEP_UP_PATH}?{urlencode({"next": next_url})}'


def safe_next(target) -> str:
    """Where a finished second factor goes: ``target`` when it is a console page of the admin host or the account page,
    else the console's front page."""
    target = str(target or '')
    if target == ACCOUNT_PAGE or hosts.is_console_page(target):
        return target
    return CONSOLE_FRONT


# --- the ceremony ---------------------------------------------------------------------------------------------------------

PENDING = 'cpt_2fa_pending'  # the anonymous session's checked password, waiting for its key
CHALLENGE = 'cpt_2fa_challenge'  # the one challenge the session's next key response must sign
ENROLMENT = 'cpt_enrol'  # the setup code a session presented, until its first key is registered
SIGN_IN, STEP_UP, ENROL, ADD = 'sign_in', 'step_up', 'enrol', 'add'  # what a challenge is for
CODE_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'
CODE_GROUP = 5
SETUP_CODE_GROUPS, RECOVERY_CODE_GROUPS = 5, 3  # about 124 and 74 bits
FAILED_SCOPE = 'second_factor.failed'  # wrong keys and recovery codes, per account
SETUP_CODE_SCOPE = 'second_factor.setup_code'  # wrong setup codes, per address
LABEL_CHARS = 60  # SecondFactorCredential.label
TRANSPORTS = frozenset(item.value for item in AuthenticatorTransport)
REMOVED_BY_RESET = 'reset on the server'
REMOVED_BY_OPERATOR = 'removed by the operator'
MAX_RESPONSE_CHARS = 64 * 1024  # a key's response, as JSON: far more than any authenticator sends


class Refused(Exception):
    """A second-factor step refused, with the sentence the operator reads."""


NOT_VERIFIED = 'The security key could not be verified. Try again.'
NO_CHALLENGE = 'This page has expired. Start again.'
TOO_MANY = 'Too many attempts. Wait {wait} and try again.'


def is_human_operator(user) -> bool:
    """A human account holding a platform-operator grant (studio.operator.is_operator; C3 makes that need a human too)."""
    from .operator import is_operator  # here: operator's gate may import this module
    return user is not None and getattr(user, 'actor_kind', None) == User.HUMAN and is_operator(user)


def _now():
    return timezone.now()


def active_keys(user):
    """The account's keys for this relying party that were not removed, oldest first."""
    return SecondFactorCredential.objects.filter(user=user, rp_id=settings.WEBAUTHN_RP_ID,
                                                 removed_at__isnull=True).order_by('created_at', 'pk')


def _descriptor(key):
    transports = [AuthenticatorTransport(item) for item in key.transports or [] if item in TRANSPORTS]
    return PublicKeyCredentialDescriptor(id=base64url_to_bytes(key.credential_id), transports=transports or None)


def _store_challenge(request, user, purpose, challenge):
    request.session[CHALLENGE] = {'c': bytes_to_base64url(challenge), 'at': request_meta.epoch_seconds(),
                                  'for': purpose, 'u': str(user.pk)}


def _take_challenge(request, user, purpose) -> bytes:
    """The session's challenge for ``user`` and ``purpose``, taken out of the session (used once), or Refused."""
    stored = request.session.pop(CHALLENGE, None)
    if not isinstance(stored, dict) or stored.get('for') != purpose or stored.get('u') != str(user.pk):
        raise Refused(NO_CHALLENGE)
    at = stored.get('at')
    age = request_meta.epoch_seconds() - at if isinstance(at, int) and not isinstance(at, bool) else -1
    if not 0 <= age <= settings.SECOND_FACTOR_PENDING_SECONDS or not isinstance(stored.get('c'), str):
        raise Refused(NO_CHALLENGE)
    return base64url_to_bytes(stored['c'])


def parse_response(raw) -> dict:
    """A key's response as the page sends it (JSON text), as a dict, or Refused."""
    if isinstance(raw, dict):
        data = raw
    else:
        if not isinstance(raw, str) or not raw or len(raw) > MAX_RESPONSE_CHARS:
            raise Refused(NOT_VERIFIED)
        try:
            data = json.loads(raw)
        except ValueError:
            raise Refused(NOT_VERIFIED) from None
    if not isinstance(data, dict) or not isinstance(data.get('id'), str) or not isinstance(data.get('response'), dict):
        raise Refused(NOT_VERIFIED)
    return data


def _refuse_cross_origin(data):
    """A response made inside a frame of another origin (clientDataJSON crossOrigin) is refused: the console is never
    framed (frame-ancestors 'none')."""
    try:
        client = parse_client_data_json(base64url_to_bytes(data['response']['clientDataJSON']))
    except Exception:  # noqa: BLE001 - unreadable client data verifies nothing
        raise Refused(NOT_VERIFIED) from None
    if client.cross_origin:
        raise Refused(NOT_VERIFIED)


def authentication_options(request, user, purpose) -> dict:
    """The options of a signed challenge for ``user``'s own keys (navigator.credentials.get), as JSON data."""
    challenge = secrets.token_bytes(32)
    options = generate_authentication_options(rp_id=settings.WEBAUTHN_RP_ID, challenge=challenge,
                                              allow_credentials=[_descriptor(key) for key in active_keys(user)],
                                              user_verification=UserVerificationRequirement.PREFERRED)
    _store_challenge(request, user, purpose, challenge)
    return json.loads(options_to_json(options))


def verify_key(request, user, raw, purpose):
    """``user``'s key that signed the session's challenge, its counter and last use updated, or Refused. The challenge
    is taken out first, so it serves one response whatever that response is."""
    challenge = _take_challenge(request, user, purpose)
    data = parse_response(raw)
    _refuse_cross_origin(data)
    with transaction.atomic():
        key = active_keys(user).select_for_update().filter(credential_id=data['id']).first()
        if key is None:  # another account's key, a removed one, or one made for another relying party
            raise Refused(NOT_VERIFIED)
        try:
            verified = verify_authentication_response(
                credential=data, expected_challenge=challenge, expected_rp_id=settings.WEBAUTHN_RP_ID,
                expected_origin=settings.WEBAUTHN_ORIGIN, credential_public_key=bytes(key.public_key),
                credential_current_sign_count=key.sign_count, require_user_verification=False)
        except Exception:  # noqa: BLE001 - whatever does not verify is refused, never a 500
            raise Refused(NOT_VERIFIED) from None
        if verified.credential_id != base64url_to_bytes(key.credential_id):
            raise Refused(NOT_VERIFIED)
        key.sign_count = verified.new_sign_count
        key.last_used_at = _now()
        key.save(update_fields=['sign_count', 'last_used_at'])
    return key


def clean_label(text) -> str:
    """A key's label as stored: stripped, at most LABEL_CHARS, no control characters; 'Security key' when empty."""
    label = ' '.join(str(text or '').split())[:LABEL_CHARS]
    if request_meta.UNSTORABLE.search(label) or any(ord(char) < 32 for char in label):
        raise Refused('The name of the key holds a character that cannot be stored.')
    return label or 'Security key'


def registration_options(request, user, purpose) -> dict:
    """The options of a new key for ``user`` (navigator.credentials.create), as JSON data; the account's keys are
    excluded, so one authenticator is never registered twice."""
    challenge = secrets.token_bytes(32)
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID, rp_name=settings.WEBAUTHN_RP_NAME, user_name=user.get_username(),
        user_id=user.pk.bytes, user_display_name=user.display_name or user.get_username(), challenge=challenge,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.DISCOURAGED,
                                                               user_verification=UserVerificationRequirement.PREFERRED),
        exclude_credentials=[_descriptor(key) for key in active_keys(user)])
    _store_challenge(request, user, purpose, challenge)
    return json.loads(options_to_json(options))


def verify_registration(request, user, raw, label, purpose):
    """The new key that answered the session's challenge, stored for ``user``, or Refused."""
    challenge = _take_challenge(request, user, purpose)
    data = parse_response(raw)
    _refuse_cross_origin(data)
    label = clean_label(label)
    try:
        verified = verify_registration_response(credential=data, expected_challenge=challenge,
                                                expected_rp_id=settings.WEBAUTHN_RP_ID,
                                                expected_origin=settings.WEBAUTHN_ORIGIN,
                                                require_user_verification=False)
    except Exception:  # noqa: BLE001
        raise Refused(NOT_VERIFIED) from None
    credential_id = bytes_to_base64url(verified.credential_id)
    if len(credential_id) > SecondFactorCredential._meta.get_field('credential_id').max_length:
        raise Refused(NOT_VERIFIED)
    if SecondFactorCredential.objects.filter(credential_id=credential_id).exists():
        raise Refused('This security key is already set up.')
    transports = data['response'].get('transports')
    transports = [item for item in transports if item in TRANSPORTS][:8] if isinstance(transports, list) else []
    return SecondFactorCredential.objects.create(
        user=user, rp_id=settings.WEBAUTHN_RP_ID, label=label, credential_id=credential_id,
        public_key=verified.credential_public_key, sign_count=verified.sign_count, transports=transports,
        aaguid=str(verified.aaguid or '')[:36])


def remove_key(user, key_id):
    """Remove one of ``user``'s keys (the row stays, marked removed); the last key cannot be removed. The key."""
    with transaction.atomic():
        keys = list(active_keys(user).select_for_update())
        key = next((item for item in keys if str(item.pk) == str(key_id)), None)
        if key is None:
            raise Refused('That key is not one of yours, or it was already removed.')
        if len(keys) == 1:
            raise Refused('The last key cannot be removed. Add another key first.')
        key.removed_at = _now()
        key.removed_reason = REMOVED_BY_OPERATOR
        key.save(update_fields=['removed_at', 'removed_reason'])
    return key


# --- codes ------------------------------------------------------------------------------------------------------------------

def plain_code(typed, groups):
    """A typed code in its one stored form - lowercase, no spaces or hyphens - or None when it is not a code of
    ``groups`` groups of CODE_GROUP characters of CODE_ALPHABET."""
    if not isinstance(typed, str) or len(typed) > 200:
        return None
    plain = ''.join(char for char in typed.strip().lower() if char not in ' -\t')
    if len(plain) != groups * CODE_GROUP or any(char not in CODE_ALPHABET for char in plain):
        return None
    return plain


def shown_code(plain) -> str:
    return '-'.join(plain[at:at + CODE_GROUP] for at in range(0, len(plain), CODE_GROUP))


def new_code(groups) -> str:
    """A new code of ``groups`` groups, as shown (with hyphens)."""
    return shown_code(''.join(secrets.choice(CODE_ALPHABET) for _ in range(groups * CODE_GROUP)))


def code_digest(plain) -> str:
    return hashlib.sha256(plain.encode('ascii')).hexdigest()


def issue_setup_code(user, by, code=None):
    """(the OneTimeToken, the code as shown) of a new setup code for ``user``, issued by the person ``by``: ``code`` when
    the caller made one (the installer's), else a new one. The account's earlier unused codes are revoked. ValueError
    when ``code`` is not a setup code."""
    if code is None:
        plain = plain_code(new_code(SETUP_CODE_GROUPS), SETUP_CODE_GROUPS)
    else:
        plain = plain_code(code, SETUP_CODE_GROUPS)
        if plain is None:
            raise ValueError(f'A setup code is {SETUP_CODE_GROUPS} groups of {CODE_GROUP} letters and digits.')
    now = _now()
    with transaction.atomic():
        OneTimeToken.objects.filter(user=user, purpose=OneTimeToken.OPERATOR_SETUP, used_at__isnull=True,
                                    revoked_at__isnull=True).update(revoked_at=now)
        token = OneTimeToken.objects.create(
            user=user, purpose=OneTimeToken.OPERATOR_SETUP, token_sha256=code_digest(plain), created_by=str(by)[:120],
            expires_at=now + timedelta(seconds=settings.ENROLMENT_CODE_SECONDS))
    return token, shown_code(plain)


def setup_token(typed):
    """The live setup code ``typed`` names - unused, not revoked, not expired, for an active human operator - or None."""
    plain = plain_code(typed, SETUP_CODE_GROUPS)
    if plain is None:
        return None
    token = (OneTimeToken.objects.select_related('user')
             .filter(token_sha256=code_digest(plain), purpose=OneTimeToken.OPERATOR_SETUP, used_at__isnull=True,
                     revoked_at__isnull=True, expires_at__gt=_now()).first())
    if token is None or not token.user.is_active or not is_human_operator(token.user):
        return None
    return token


def live_setup_token(token_id, user):
    """The setup code a session presented, if it is still live and still ``user``'s, else None."""
    try:
        token = OneTimeToken.objects.select_related('user').get(pk=token_id, user=user)
    except (OneTimeToken.DoesNotExist, ValueError, TypeError):
        return None
    if token.used_at or token.revoked_at or token.expires_at <= _now() or token.purpose != OneTimeToken.OPERATOR_SETUP:
        return None
    return token


def new_recovery_codes(user):
    """RECOVERY_CODE_COUNT new recovery codes for ``user``, as shown (hyphens), each stored as Django's make_password
    hash; the account's earlier unused codes are voided."""
    codes = [new_code(RECOVERY_CODE_GROUPS) for _ in range(settings.RECOVERY_CODE_COUNT)]
    with transaction.atomic():
        SecondFactorRecoveryCode.objects.filter(user=user, used_at__isnull=True).update(used_at=_now())
        SecondFactorRecoveryCode.objects.bulk_create(
            [SecondFactorRecoveryCode(user=user, code_hash=make_password(plain_code(code, RECOVERY_CODE_GROUPS)))
             for code in codes])
    return codes


def recovery_codes_left(user) -> int:
    return SecondFactorRecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


def use_recovery_code(user, typed) -> bool:
    """Whether ``typed`` is one of ``user``'s unused recovery codes; a match is used up at once."""
    plain = plain_code(typed, RECOVERY_CODE_GROUPS)
    if plain is None:
        return False
    with transaction.atomic():
        for code in (SecondFactorRecoveryCode.objects.select_for_update()
                     .filter(user=user, used_at__isnull=True).order_by('created_at', 'pk')):
            if check_password(plain, code.code_hash):
                code.used_at = _now()
                code.save(update_fields=['used_at'])
                return True
    return False


# --- the second step of the admin door ---------------------------------------------------------------------------------

def begin(request, user, sign_in_ref, next_url):
    """A checked password at the admin door: the anonymous session waits for ``user``'s key (see the module)."""
    request.session.pop(CHALLENGE, None)
    request.session[PENDING] = {'user': str(user.pk), 'at': request_meta.epoch_seconds(), 'ref': str(sign_in_ref),
                                'next': safe_next(next_url), 'failures': 0}
    request.session[request_meta.SESSION_SIGN_IN_REF] = str(sign_in_ref)  # the second step's records carry it


def pending(request):
    """(the account, the state) of the session's checked password waiting for its key, or (None, None): none, one older
    than SECOND_FACTOR_PENDING_SECONDS, or one whose account is no longer an active human operator."""
    state = request.session.get(PENDING)
    if not isinstance(state, dict):
        return None, None
    at = state.get('at')
    age = request_meta.epoch_seconds() - at if isinstance(at, int) and not isinstance(at, bool) else -1
    if not 0 <= age <= settings.SECOND_FACTOR_PENDING_SECONDS:
        drop_pending(request)
        return None, None
    try:
        user = User.objects.get(pk=state.get('user'), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError):
        drop_pending(request)
        return None, None
    if not is_human_operator(user):
        drop_pending(request)
        return None, None
    return user, state


def drop_pending(request):
    request.session.pop(PENDING, None)
    request.session.pop(CHALLENGE, None)


def attempts_left(user) -> int:
    used = rate.count(FAILED_SCOPE, user.pk, since=rate.window_start(settings.SECOND_FACTOR_PENDING_SECONDS))
    return max(0, settings.SECOND_FACTOR_ATTEMPTS - used)


def too_many(user) -> str:
    """The refusal sentence when ``user`` has no second-factor attempt left in this window, else ''."""
    if attempts_left(user) > 0:
        return ''
    window = settings.SECOND_FACTOR_PENDING_SECONDS
    ends = rate.window_start(window) + timedelta(seconds=window)
    return TOO_MANY.format(wait=throttle.wait_words((ends - _now()).total_seconds()))


def note_failure(request, user, state=None, *, kind='key') -> bool:
    """A wrong key or recovery code of ``user`` (``state``: a pending sign-in's, else a step-up's): counted; at the limit a
    pending sign-in is dropped and recorded as second_factor_failed, with one SecurityEvent. Whether it was dropped."""
    count = rate.hit(FAILED_SCOPE, user.pk, window_seconds=settings.SECOND_FACTOR_PENDING_SECONDS)
    if state is not None:
        state['failures'] = int(state.get('failures', 0)) + 1
        request.session[PENDING] = state
        if state['failures'] >= settings.SECOND_FACTOR_ATTEMPTS or count >= settings.SECOND_FACTOR_ATTEMPTS:
            drop_pending(request)
            throttle.settle_second_factor(request, state.get('ref'), signed_in=False)
            security_events.record('second_factor.failed', subject=user, request=request, stage=SIGN_IN, kind=kind,
                                   failures=state['failures'], attempt_ref=state.get('ref'))
            return True
        return False
    if count == settings.SECOND_FACTOR_ATTEMPTS:
        security_events.record('second_factor.failed', subject=user, request=request, stage=STEP_UP, kind=kind,
                               failures=count)
    return False


def complete_sign_in(request, user, state):
    """The admin door's sign-in, after a verified key or recovery code: login() (a new session key; studio.sessions
    writes the admin door, the times and the reference), then the second factor's time; the attempt becomes
    signed_in."""
    sessions.prepare_sign_in(request, door=request_meta.ADMIN, sign_in_ref=state['ref'])
    drop_pending(request)
    login(request, user)
    request.session[request_meta.SESSION_SECOND_FACTOR_AT] = request_meta.epoch_seconds()
    throttle.settle_second_factor(request, state['ref'], signed_in=True)


def refresh(request):
    """The step-up: a verified key or recovery code in a signed-in session at the admin door renews its second factor."""
    request.session[request_meta.SESSION_SECOND_FACTOR_AT] = request_meta.epoch_seconds()


def reset(user, by, code=None):
    """The server's reset of an operator's lost factor (B2, item 7): every key removed, every unused recovery code voided,
    every session ended, a new setup code issued. (counts, the OneTimeToken, the code as shown)."""
    now = _now()
    with transaction.atomic():
        removed = active_keys(user).update(removed_at=now, removed_reason=REMOVED_BY_RESET)
        voided = SecondFactorRecoveryCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
        ended = sessions.end_sessions(user)
        token, shown = issue_setup_code(user, by, code)
    return {'keys_removed': removed, 'recovery_codes_voided': voided, 'sessions_ended': ended}, token, shown

