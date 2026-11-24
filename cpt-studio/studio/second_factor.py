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
    begin(request, user, sign_in_ref, next_url)  a checked password waits for its key: the session it was posted in
        ends (signed out, or flushed) and a fresh ANONYMOUS session holds PENDING = {the account, when, the sign-in's
        reference, where to go} for SECOND_FACTOR_PENDING_SECONDS. login() is not called: a password alone opens nothing.
    authentication_options / verify_key  a signed challenge for the account's own keys: the challenge lives in the
        session (CHALLENGE) and is used once - taken out of the session and used up in the database (a OneTimeToken of
        CHALLENGE_PURPOSE, bound to the account, the purpose and the flow, used with one conditional UPDATE) before
        anything is checked, so a replayed response, or the same response sent from two copies of the session at once,
        meets no challenge; verify_authentication_response checks the challenge, the relying-party id, the origin, the
        stored public key and the signature counter, and a response made inside another origin's frame (crossOrigin) is
        refused.
    complete_sign_in(request, user, state)  only then, and only when its attempt is still second_factor_pending and
        becomes signed_in in one UPDATE, login() runs (a new session key; studio.sessions writes the admin door, the
        times and the reference) and the session gets SESSION_SECOND_FACTOR_AT.
    note_failure  a wrong key or recovery code counts per account in RateWindow (SECOND_FACTOR_ATTEMPTS per
        SECOND_FACTOR_PENDING_SECONDS) and per pending sign-in (its reference, from its start); at either limit a pending
        sign-in is dropped - in every copy of the session, since pending() reads its count - and recorded as
        second_factor_failed, with one SecurityEvent. The per-account count is two counts (failure_scope; release 1
        repair round 1, auth-0): a request carrying this account's own valid known-device cookie spends and reads
        FAILED_KNOWN_DEVICE_SCOPE, every other request FAILED_SCOPE. So someone holding the password alone, who can
        fill the shared count every window from anywhere, never uses up the attempts of the operator's own browser,
        whose key, recovery codes and step-up keep working. A request without that cookie - a new browser, another
        account's cookie, a forged or expired one - shares FAILED_SCOPE, as every request did before; someone who also
        holds the device cookie can spend the device's count too (the cookie is HttpOnly, Secure and SameSite=Strict,
        and it opens nothing: the password and a key or code are still needed). Each pending sign-in keeps its own
        limit, whichever count its requests spend.
    use_recovery_code  a recovery code stands in for a key once: stored as Django's make_password hash.
    issue_setup_code / setup_token  setup needs a single-use code issued on the server (OneTimeToken OPERATOR_SETUP, valid
        ENROLMENT_CODE_SECONDS, stored as its sha256 only; issuing one revokes the account's earlier unused ones).
    claim_setup_code / live_claim  the setup's first step uses the code up at once and gives its session a claim
        (SETUP_CLAIM_PURPOSE, ENROLMENT_CODE_SECONDS) that the second step uses up with the first key.
    registration_options / checked_registration / store_key  a new key, from a setup code (enrolment) or from the keys
        page: checked first, its challenge used up outside any transaction, then stored by store_key inside the
        caller's transaction, beside the act's SecurityEvent (release 1 repair round 1, failclosed-2 and -5). Every act
        here that changes a key or a code - store_key, remove_key, use_recovery_code, new_recovery_codes,
        claim_setup_code - is written in the transaction of its caller, which writes the act's record in it too.
    new_recovery_codes  RECOVERY_CODE_COUNT codes, shown once; the earlier unused ones are voided.
    reset(user, ...)  the server's reset of lost keys (B2, item 7): keys removed, recovery codes voided, sessions ended, a
        new setup code issued. No console path resets an operator's own factor.
Codes are typed as groups of five letters and digits (CODE_ALPHABET; no 0, 1, i, l or o), case and hyphens ignored.
Nothing here writes a code, a key or a challenge into a log, an audit row or a security event: ids and counts only.
"""
from __future__ import annotations

import functools
import hashlib
from contextlib import contextmanager
import json
import math
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, parse_client_data_json
from webauthn.helpers.structs import (AttestationConveyancePreference, AuthenticatorSelectionCriteria,
                                      AuthenticatorTransport, PublicKeyCredentialDescriptor, ResidentKeyRequirement,
                                      UserVerificationRequirement)

from . import hosts, rate, request_meta, security_events, session_store, sessions, throttle
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


def safe_next(target, host=None) -> str:
    """Where a finished second factor goes: ``target`` when it is a path of this site alone (local_path) that names a
    console page of the admin host or the account page, else the console's front page."""
    target = str(target or '')
    if not local_path(target, host):
        return CONSOLE_FRONT
    if target == ACCOUNT_PAGE or hosts.is_console_page(target):
        return target
    return CONSOLE_FRONT


def local_path(target, host=None) -> bool:
    """Whether ``target`` is a path of this site and nothing else: exactly one leading '/', not followed by '/' or a
    backslash; no backslash, control, format or other invisible character anywhere (Unicode category C); and accepted
    by Django's url_has_allowed_host_and_scheme with no host but ``host``. A browser reads '///ops/people' as the host
    'ops' (refutation r2, finding 5), and '/\\ops' or a tab inside the slashes the same way."""
    if not isinstance(target, str) or not target.startswith('/') or target[1:2] in ('/', '\\'):
        return False
    if any(char == '\\' or unicodedata.category(char)[0] == 'C' for char in target):
        return False
    return url_has_allowed_host_and_scheme(target, allowed_hosts={host} if host else set(), require_https=False)


# --- the ceremony ---------------------------------------------------------------------------------------------------------

PENDING = sessions.PENDING_SIGN_IN_KEY  # the anonymous session's checked password, waiting for its key
CHALLENGE = 'cpt_2fa_challenge'  # the one challenge the session's next key response must sign
ENROLMENT = sessions.SETUP_KEY  # the setup a session claimed with its code, until its first key is registered
SIGN_IN, STEP_UP, ENROL, ADD = 'sign_in', 'step_up', 'enrol', 'add'  # what a challenge is for
CODE_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'
CODE_GROUP = 5
SETUP_CODE_GROUPS, RECOVERY_CODE_GROUPS = 5, 3  # about 124 and 74 bits
FAILED_SCOPE = 'second_factor.failed'  # wrong keys and recovery codes, per account, but for its own known devices
FAILED_KNOWN_DEVICE_SCOPE = 'second_factor.failed_known_device'  # the same, from requests with its known-device cookie
PENDING_FAILED_SCOPE = 'second_factor.failed_sign_in'  # the same, per pending sign-in (its reference)
SETUP_CODE_SCOPE = 'second_factor.setup_code'  # wrong setup codes, per address
LABEL_CHARS = 60  # SecondFactorCredential.label
TRANSPORTS = frozenset(item.value for item in AuthenticatorTransport)
REMOVED_BY_RESET = 'reset on the server'
REMOVED_BY_OPERATOR = 'removed by the operator'
MAX_RESPONSE_CHARS = 64 * 1024  # a key's response, as JSON: far more than any authenticator sends
CHALLENGE_PURPOSE = 'webauthn_challenge'  # OneTimeToken.purpose of a challenge's single use (a plain column)
SETUP_CLAIM_PURPOSE = 'operator_setup_claim'  # OneTimeToken.purpose of a setup a session claimed with its code
# a credential id as a response names it: base64url, at most SecondFactorCredential.credential_id's 1400 characters
CREDENTIAL_ID = re.compile(r'[A-Za-z0-9_-]{1,1400}')


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


def _flow(request, purpose) -> str:
    """What a challenge is bound to besides its account and its purpose: the pending sign-in's reference (SIGN_IN), the
    enrolment's claim (ENROL), else the signed-in session's sign-in reference (STEP_UP, ADD); '' when there is none."""
    session = request.session
    if purpose in (SIGN_IN, ENROL):
        state = session.get(PENDING if purpose == SIGN_IN else ENROLMENT)
        return str(state.get('ref' if purpose == SIGN_IN else 'claim') or '') if isinstance(state, dict) else ''
    return str(session.get(request_meta.SESSION_SIGN_IN_REF) or '')


def _challenge_digest(user, purpose, flow, challenge) -> str:
    """The sha256 a challenge's single use is kept under (CHALLENGE_PURPOSE): of the account, the purpose, the flow and
    the challenge, so a challenge is used up only in the flow it was made for."""
    return hashlib.sha256(b'\n'.join([b'cpt-studio-webauthn-challenge', str(user.pk).encode('ascii'),
                                      purpose.encode('ascii'), flow.encode('utf-8'), challenge])).hexdigest()


def _store_challenge(request, user, purpose, challenge):
    """The session keeps the challenge (CHALLENGE); the database keeps its single use, as a OneTimeToken of
    CHALLENGE_PURPOSE that _take_challenge uses up. The account's used or expired challenges are deleted: they open
    nothing, and they are not records."""
    now = _now()
    OneTimeToken.objects.filter(user=user, purpose=CHALLENGE_PURPOSE).filter(
        Q(used_at__isnull=False) | Q(revoked_at__isnull=False) | Q(expires_at__lte=now)).delete()
    OneTimeToken.objects.create(user=user, purpose=CHALLENGE_PURPOSE, created_by=purpose,
                                token_sha256=_challenge_digest(user, purpose, _flow(request, purpose), challenge),
                                expires_at=now + timedelta(seconds=settings.SECOND_FACTOR_PENDING_SECONDS))
    request.session[CHALLENGE] = {'c': bytes_to_base64url(challenge), 'at': request_meta.epoch_seconds(),
                                  'for': purpose, 'u': str(user.pk)}


def _take_challenge(request, user, purpose) -> bytes:
    """The session's challenge for ``user`` and ``purpose``, used up, or Refused. It is taken out of the session, and its
    single use is taken in the database with one UPDATE ... WHERE used_at IS NULL, before the response is even read: of
    two requests that loaded the same session at the same moment, one gets the challenge and the other is refused, and a
    response that is refused, or that fails in any other way, has used it up all the same (refutation r2, finding 1).
    It is called outside any transaction a refusal rolls back."""
    stored = request.session.pop(CHALLENGE, None)
    if not isinstance(stored, dict) or stored.get('for') != purpose or stored.get('u') != str(user.pk):
        raise Refused(NO_CHALLENGE)
    at = stored.get('at')
    age = request_meta.epoch_seconds() - at if isinstance(at, int) and not isinstance(at, bool) else -1
    if not 0 <= age <= settings.SECOND_FACTOR_PENDING_SECONDS or not isinstance(stored.get('c'), str):
        raise Refused(NO_CHALLENGE)
    challenge = base64url_to_bytes(stored['c'])
    now = _now()
    used = OneTimeToken.objects.filter(
        token_sha256=_challenge_digest(user, purpose, _flow(request, purpose), challenge), user=user,
        purpose=CHALLENGE_PURPOSE, used_at__isnull=True, revoked_at__isnull=True, expires_at__gt=now).update(used_at=now)
    if used != 1:
        raise Refused(NO_CHALLENGE)
    return challenge


def parse_response(raw) -> dict:
    """A key's response as the page sends it (JSON text), as a dict, or Refused. Its credential id (and rawId, when
    given) must be base64url of the length a credential id can have (CREDENTIAL_ID) before anything looks it up: a NUL
    or any other character the database cannot hold is the ordinary refusal, never a server error (refutation r2,
    finding 3)."""
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
    if not CREDENTIAL_ID.fullmatch(data['id']) or ('rawId' in data and not (
            isinstance(data['rawId'], str) and CREDENTIAL_ID.fullmatch(data['rawId']))):
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


def checked_registration(request, user, raw, label, purpose) -> dict:
    """The new key that answered the session's challenge, checked but not stored yet (store_key stores it), or Refused.
    The challenge is used up first (_take_challenge), so this runs outside the transaction that stores the key."""
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
    transports = data['response'].get('transports')
    transports = [item for item in transports if item in TRANSPORTS][:8] if isinstance(transports, list) else []
    return {'label': label, 'credential_id': credential_id, 'public_key': verified.credential_public_key,
            'sign_count': verified.sign_count, 'transports': transports, 'aaguid': str(verified.aaguid or '')[:36]}


def store_key(user, checked):
    """Store for ``user`` the key checked_registration answered, or Refused when that authenticator is already set up."""
    if SecondFactorCredential.objects.filter(credential_id=checked['credential_id']).exists():
        raise Refused('This security key is already set up.')
    return SecondFactorCredential.objects.create(user=user, rp_id=settings.WEBAUTHN_RP_ID, **checked)


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
    the caller made one (the installer's), else a new one. The account's earlier unused codes are revoked, and so is
    any setup a session claimed with one and has not finished (claim_setup_code). ValueError when ``code`` is not a
    setup code."""
    if code is None:
        plain = plain_code(new_code(SETUP_CODE_GROUPS), SETUP_CODE_GROUPS)
    else:
        plain = plain_code(code, SETUP_CODE_GROUPS)
        if plain is None:
            raise ValueError(f'A setup code is {SETUP_CODE_GROUPS} groups of {CODE_GROUP} letters and digits.')
    now = _now()
    with transaction.atomic():
        OneTimeToken.objects.filter(user=user, purpose__in=(OneTimeToken.OPERATOR_SETUP, SETUP_CLAIM_PURPOSE),
                                    used_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
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


def claim_setup_code(token):
    """The setup's first step uses ``token`` - a live setup code - up, in one UPDATE ... WHERE used_at IS NULL, and
    answers the claim that lets this one session finish the setup: a OneTimeToken of SETUP_CLAIM_PURPOSE, live for
    ENROLMENT_CODE_SECONDS, which the second step uses up when the first key is stored. None when another request used
    the code first: two browsers holding one code cannot both choose the password (refutation r2, finding 6). Runs in
    the caller's transaction, which sets the password with it."""
    now = _now()
    used = OneTimeToken.objects.filter(pk=token.pk, purpose=OneTimeToken.OPERATOR_SETUP, used_at__isnull=True,
                                       revoked_at__isnull=True, expires_at__gt=now).update(used_at=now)
    if used != 1:
        return None
    return OneTimeToken.objects.create(user=token.user, purpose=SETUP_CLAIM_PURPOSE, created_by=token.created_by,
                                       token_sha256=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
                                       expires_at=now + timedelta(seconds=settings.ENROLMENT_CODE_SECONDS))


def live_claim(claim_id, user):
    """The setup claim a session holds (claim_setup_code), if it is still live and still ``user``'s, else None."""
    try:
        claim = OneTimeToken.objects.get(pk=claim_id, user=user, purpose=SETUP_CLAIM_PURPOSE)
    except (OneTimeToken.DoesNotExist, ValueError, TypeError, ValidationError):
        return None
    if claim.used_at or claim.revoked_at or claim.expires_at <= _now():
        return None
    return claim


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
    """A checked password at the admin door: the session it was posted in ends - a signed-in one is signed out
    (logout()), an anonymous one is flushed - and a fresh anonymous session, under a new key, waits for ``user``'s key
    (see the module). Nothing of an earlier session - its sign-in, its reference, its second factor - carries into the
    pending sign-in, and the pending sign-in's reference is never written into a signed-in session (refutation r2,
    finding 4)."""
    if getattr(getattr(request, 'user', None), 'is_authenticated', False):
        logout(request)
    else:
        request.session.flush()
    request.session[PENDING] = {'user': str(user.pk), 'at': request_meta.epoch_seconds(), 'ref': str(sign_in_ref),
                                'next': safe_next(next_url, request.get_host()), 'pw': user.get_session_auth_hash()}
    request.session[request_meta.SESSION_SIGN_IN_REF] = str(sign_in_ref)  # the second step's records carry it


def pending(request):
    """(the account, the state) of the session's checked password waiting for its key, or (None, None): none, one older
    than SECOND_FACTOR_PENDING_SECONDS, one whose own failures reached SECOND_FACTOR_ATTEMPTS (counted in the database,
    so every copy of the session sees them: refutation r2, finding 2), one whose account is no longer an active human
    operator, or one whose password changed after it was checked: the pending sign-in carries the account's session
    auth hash (Django's keyed hash of the stored password hash, as a signed-in session does), so neither a key nor a
    recovery code completes a sign-in made with a password that is no longer the account's."""
    state = request.session.get(PENDING)
    if not isinstance(state, dict) or not isinstance(state.get('ref'), str):
        return None, None
    at = state.get('at')
    age = request_meta.epoch_seconds() - at if isinstance(at, int) and not isinstance(at, bool) else -1
    if not 0 <= age <= settings.SECOND_FACTOR_PENDING_SECONDS:
        drop_pending(request)
        return None, None
    try:
        dead = pending_failures(state) >= settings.SECOND_FACTOR_ATTEMPTS
    except ValueError:  # a reference that is no id: not a pending sign-in of this release
        dead = True
    if dead:
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
    if not constant_time_compare(str(state.get('pw') or ''), user.get_session_auth_hash()):
        drop_pending(request)  # the password it checked has changed since (refutation r2, finding 11)
        return None, None
    return user, state


def drop_pending(request):
    request.session.pop(PENDING, None)
    request.session.pop(CHALLENGE, None)


def pending_failures(state) -> int:
    """The failures of one pending sign-in, from its start: per its reference, in RateWindow (PENDING_FAILED_SCOPE), so
    two requests at the same moment are both counted and every copy of the session reads the same number."""
    window = settings.SECOND_FACTOR_PENDING_SECONDS
    started = datetime.fromtimestamp(state['at'], tz=dt_timezone.utc)
    return rate.count(PENDING_FAILED_SCOPE, state['ref'], since=rate.window_start(window, started))


def failure_scope(request, user) -> str:
    """The per-account count of second-factor failures ``request`` spends and reads (see the module; auth-0):
    FAILED_KNOWN_DEVICE_SCOPE when it carries ``user``'s own valid known-device cookie (throttle.device_user_id: signed,
    at most KNOWN_DEVICE_DAYS old, naming this account), else FAILED_SCOPE - no request, no cookie, another account's,
    a forged or an expired one."""
    cookies = getattr(request, 'COOKIES', None) or {}
    owner = throttle.device_user_id(cookies.get(throttle.device_cookie_name()))
    return FAILED_KNOWN_DEVICE_SCOPE if owner is not None and owner == user.pk else FAILED_SCOPE


def attempts_left(user, state=None, request=None) -> int:
    """The second-factor attempts ``user`` has left: per account in this window - the count ``request`` spends
    (failure_scope; FAILED_SCOPE when no request is given) - and for a pending sign-in (``state``) its own too,
    whichever is fewer."""
    used = rate.count(failure_scope(request, user), user.pk,
                      since=rate.window_start(settings.SECOND_FACTOR_PENDING_SECONDS))
    if state is not None:
        used = max(used, pending_failures(state))
    return max(0, settings.SECOND_FACTOR_ATTEMPTS - used)


def too_many(user, request=None) -> str:
    """The refusal sentence when ``user`` has no second-factor attempt left in this window - in the count ``request``
    spends (failure_scope) - else ''."""
    if attempts_left(user, request=request) > 0:
        return ''
    window = settings.SECOND_FACTOR_PENDING_SECONDS
    ends = rate.window_start(window) + timedelta(seconds=window)
    return TOO_MANY.format(wait=throttle.wait_words((ends - _now()).total_seconds()))


def note_failure(request, user, state=None, *, kind='key') -> bool:
    """A wrong key or recovery code of ``user`` (``state``: a pending sign-in's, else a step-up's): counted per account,
    and for a pending sign-in per its reference too - each an atomic hit, the limit read after it. At the limit a pending
    sign-in is dropped and its attempt becomes second_factor_failed, with one SecurityEvent (written by the one request
    whose update settled it). Whether it was dropped. The per-account count is the one ``request`` spends
    (failure_scope: the account's own known devices apart from every other request)."""
    scope = failure_scope(request, user)
    known_device = scope == FAILED_KNOWN_DEVICE_SCOPE
    count = rate.hit(scope, user.pk, window_seconds=settings.SECOND_FACTOR_PENDING_SECONDS)
    if state is not None:
        rate.hit(PENDING_FAILED_SCOPE, state['ref'], window_seconds=settings.SECOND_FACTOR_PENDING_SECONDS)
        failures = pending_failures(state)
        if failures >= settings.SECOND_FACTOR_ATTEMPTS or count >= settings.SECOND_FACTOR_ATTEMPTS:
            drop_pending(request)
            if throttle.settle_second_factor(request, state['ref'], signed_in=False):
                security_events.record('second_factor.failed', subject=user, request=request, stage=SIGN_IN, kind=kind,
                                       failures=failures, attempt_ref=state['ref'], known_device=known_device)
            return True
        return False
    if count == settings.SECOND_FACTOR_ATTEMPTS:
        security_events.record('second_factor.failed', subject=user, request=request, stage=STEP_UP, kind=kind,
                               failures=count, known_device=known_device)
    return False


def complete_sign_in(request, user, state) -> bool:
    """The admin door's sign-in, after a verified key or recovery code. Its attempt becomes signed_in first, in one
    UPDATE that needs it still second_factor_pending: an attempt another request already settled - its failures
    reached the limit in another copy of the session - never signs in, and the sign-in is dropped (refutation r2,
    finding 2). Then login() (a new session key; studio.sessions writes the admin door, the times and the reference)
    and the second factor's time. Whether it signed in."""
    if not throttle.settle_second_factor(request, state['ref'], signed_in=True):
        drop_pending(request)
        return False
    sessions.prepare_sign_in(request, door=request_meta.ADMIN, sign_in_ref=state['ref'])
    drop_pending(request)
    login(request, user)
    request.session[request_meta.SESSION_SECOND_FACTOR_AT] = request_meta.epoch_seconds()
    return True


@contextmanager
def new_sign_in_only_if_kept(request):
    """Around a transaction that may sign the request in (a recovery code's, setup's key step): when it raises - a
    record refused at its statement or at the COMMIT, after login() ran - the sign-in it made is rolled back, and the
    mark login() left for studio.sessions (request.cpt_new_sign_in: set the known-device cookie and the actor header on
    the answer) goes with it, so the failed answer gives the browser no known-device cookie (release 1 repair round 1,
    failclosed-5 and -7). Put it outside transaction.atomic(), so a failed commit passes through it."""
    try:
        yield
    except BaseException:
        request.__dict__.pop('cpt_new_sign_in', None)
        raise


def refresh(request):
    """The step-up: a verified key or recovery code in a signed-in session at the admin door renews its second factor."""
    request.session[request_meta.SESSION_SECOND_FACTOR_AT] = request_meta.epoch_seconds()


def reset(user, by, code=None):
    """The server's reset of an operator's lost factor (B2, item 7): every key removed, every unused recovery code voided,
    every session ended, a new setup code issued. (counts, the OneTimeToken, the code as shown)."""
    now = _now()
    with transaction.atomic():
        session_store.lock_accounts([user.pk])  # the account first: the lock order (studio.session_store)
        removed = active_keys(user).update(removed_at=now, removed_reason=REMOVED_BY_RESET)
        voided = SecondFactorRecoveryCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
        ended = sessions.end_sessions(user)
        token, shown = issue_setup_code(user, by, code)
    return {'keys_removed': removed, 'recovery_codes_voided': voided, 'sessions_ended': ended}, token, shown

