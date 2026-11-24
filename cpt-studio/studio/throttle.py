"""Sign-in slows down instead of locking anyone out (release 1, B1; RELEASE-1-SPEC 4, B1). Both doors - cpt.quillmd.com's
studio.views.login_view and admin.quillmd.com's admin_login_view - open a Door for each attempt, ask it for a refusal
BEFORE any password is checked, and hand it the result of the password check, which writes the attempt's LoginAttempt.

The checks, in order, all before Argon2 runs (Door.refusal):
  (a) address flood: refused or failed attempts from the client's key - an IPv4 address, or an IPv6 address's /64
      (studio.request_meta.client_key) - in the window reach SIGNIN_CLIENT_LIMIT: refused from that address only;
  (b) pair: failures for (the username, the client's key) reach SIGNIN_PAIR_LIMIT: refused from that pair only;
  (c) username delay: failures for the username from any address reach SIGNIN_USER_DELAY_AFTER: the next try waits
      min(SIGNIN_DELAY_BASE_SECONDS * 2 ** (n - SIGNIN_USER_DELAY_AFTER), SIGNIN_DELAY_MAX_SECONDS) after the last
      failure. It never locks: the wait never grows past the ceiling, and refusals do not lengthen it;
  (d) known device: a valid device cookie for this username (device_cookie_name(): signed with django.core.signing,
      salt 'cpt-device', holding the account's id, a random id and the issue date - never a session; HttpOnly, Secure
      under HTTPS, SameSite=Strict, Path=/; KNOWN_DEVICE_DAYS long; set on every successful sign-in by
      studio.sessions.SessionPolicyMiddleware) skips (c), never (a) or (b).
The window is SIGNIN_WINDOW_SECONDS. The refusal sentence is the same whether or not the account exists (USER_REFUSAL;
CLIENT_REFUSAL for (a)), and every refusal is answered before the password hasher runs (AUTH-3, L-AVAIL).

The counts live in RateWindow rows (studio.rate), one per minute: failures per username, per pair and per address, and
refusals per username and per address. A username is only ever counted as its keyed hash (user_key), never as typed
text, and a pair as the keyed hash of both (pair_key). A refusal is counted, never hidden (AUTH-9): the first refusal of
a minute writes one SecurityEvent signin.throttled holding ids and counts - per username for (b) and (c), per address
for (a) - and refused_in() answers the console's "N refused in the last hour".

Every attempt that reaches the password check writes one LoginAttempt (Door.check): its door ('cpt' or 'admin'), its
outcome (LoginAttempt.OUTCOMES) and its sign-in reference. ``succeeded`` stays, because the older release reads it: true
for signed_in only. The failures - wrong_password, unknown_account, password_expired (a staff-set password not replaced
within STAFF_PASSWORD_UNUSED_SECONDS, B4: refused exactly like a wrong password, with one SecurityEvent
password.expired_unused) and second_factor_failed (B2) - count toward (a) to (c). no_access - the right password at a
door that does not admit the account (no active membership at cpt, not a human operator at admin) - never counts toward
a delay, so a doctor's right password at the admin door changes nothing on the doctors' sign-in.

clear_failures(username) deletes that name's RateWindow rows - its failures, its refusals and the pairs it was tried
from - and is what the console's unlock (Lane 3) and the ruled act clear_signin_failures call; each writes its own
SecurityEvent. LoginAttempt rows are never deleted here.

The settings LOGIN_THROTTLE_* (today's lockout) are read by nothing here.
"""
from __future__ import annotations

import math
import secrets
import uuid
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Max, Sum
from django.utils import timezone

from . import rate, request_meta, security_events
from .models import LoginAttempt, RateWindow, User

FAIL_USER, FAIL_PAIR, FAIL_CLIENT = 'signin.fail.user', 'signin.fail.pair', 'signin.fail.client'
REFUSED_USER, REFUSED_CLIENT = 'signin.refused.user', 'signin.refused.client'
MINUTE = 60  # every sign-in counter is kept per minute
FAILURES = frozenset({LoginAttempt.WRONG_PASSWORD, LoginAttempt.UNKNOWN_ACCOUNT, LoginAttempt.PASSWORD_EXPIRED,
                      LoginAttempt.SECOND_FACTOR_FAILED})
DEVICE_SALT = 'cpt-device'
USER_REFUSAL = 'Too many attempts. Wait {wait} and try again, or sign in from a device you have used before.'
CLIENT_REFUSAL = 'Too many attempts from this network. Wait {wait} and try again.'
ADDRESS, PAIR, USERNAME = 'address', 'pair', 'username'  # which check refused (the SecurityEvent's own words)


def user_key(username) -> str:
    """The key a typed username is counted by: its keyed hash, casefolded, so 'Owner' and 'owner' share one delay."""
    return rate.key_hash('signin-user:' + str(username).casefold())


def pair_key(username, client_key) -> str:
    """The key of (a typed username, a client's key): one keyed hash of both."""
    return rate.key_hash('signin-pair:' + str(username).casefold() + '\n' + str(client_key))


def key_of_address(address) -> str:
    """request_meta.client_key's reading of a stored address (a LoginAttempt's client)."""
    return request_meta.client_key(SimpleNamespace(META={'REMOTE_ADDR': str(address or '')}))


def device_cookie_name() -> str:
    """The known-device cookie's name: with the __Host- prefix under HTTPS (B6), plain without it (the prefix needs
    Secure)."""
    return '__Host-cptstudio_device' if settings.HTTPS else 'cptstudio_device'


def device_cookie_value(user_id) -> str:
    """A new known-device cookie for the account ``user_id``: its id, a random id and the issue date, signed."""
    return signing.dumps({'u': str(user_id), 'r': secrets.token_hex(8), 'd': timezone.now().date().isoformat()},
                         salt=DEVICE_SALT)


def device_user_id(value):
    """The account id a known-device cookie names, or None: absent, forged, malformed or older than
    KNOWN_DEVICE_DAYS."""
    if not value or not isinstance(value, str) or len(value) > 400:
        return None
    try:
        data = signing.loads(value, salt=DEVICE_SALT, max_age=timedelta(days=settings.KNOWN_DEVICE_DAYS))
    except (signing.BadSignature, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('u'), str):
        return None
    try:
        return uuid.UUID(data['u'])
    except ValueError:
        return None


def delay_seconds(failures) -> int:
    """How long after the last failure the next try waits, for ``failures`` in the window (0 below the threshold)."""
    if failures < settings.SIGNIN_USER_DELAY_AFTER:
        return 0
    extra = failures - settings.SIGNIN_USER_DELAY_AFTER
    if extra >= 32:  # 2 ** 32 * 30 s is far past any ceiling; no huge numbers
        return settings.SIGNIN_DELAY_MAX_SECONDS
    return min(settings.SIGNIN_DELAY_BASE_SECONDS * 2 ** extra, settings.SIGNIN_DELAY_MAX_SECONDS)


def staff_password_expired(user, moment=None) -> bool:
    """Whether ``user``'s password was set by staff (password_change_required_at) longer than
    STAFF_PASSWORD_UNUSED_SECONDS ago (B4, item 4): such a password no longer signs in, at either door."""
    flagged = getattr(user, 'password_change_required_at', None)
    if flagged is None:
        return False
    return (moment or timezone.now()) - flagged > timedelta(seconds=settings.STAFF_PASSWORD_UNUSED_SECONDS)


def _since(now):
    """The start of the first per-minute window the sign-in window reaches back to (it covers the whole window)."""
    return rate.window_start(MINUTE, now - timedelta(seconds=settings.SIGNIN_WINDOW_SECONDS))


def _rows(scope, key, since):
    return list(RateWindow.objects.filter(scope=scope, key=key, window_start__gte=since)
                .order_by('window_start').values_list('window_start', 'count'))


def _wait_below(rows, limit, now):
    """Seconds until the windows in ``rows`` (ascending) sum below ``limit`` as the oldest leave the sign-in window, if
    nothing more is counted; at least a minute."""
    total = sum(count for _, count in rows)
    window = timedelta(seconds=settings.SIGNIN_WINDOW_SECONDS + MINUTE)
    for start, count in rows:
        total -= count
        if total < limit:
            return max((start + window - now).total_seconds(), MINUTE)
    return settings.SIGNIN_WINDOW_SECONDS


def wait_words(seconds) -> str:
    minutes = max(1, math.ceil(seconds / 60))
    return f'{minutes} minute' if minutes == 1 else f'{minutes} minutes'


def failures_of(username, now=None):
    """(the failures counted for ``username`` in the sign-in window, the time of the last one or None)."""
    now = now or timezone.now()
    found = RateWindow.objects.filter(scope=FAIL_USER, key=user_key(username), window_start__gte=_since(now)).aggregate(
        total=Sum('count'), last=Max('last_at'))
    return found['total'] or 0, found['last']


def refused_in(username, *, seconds=3600) -> int:
    """The attempts refused for ``username`` in the last ``seconds`` (the console's Sign-ins page, AUTH-9)."""
    since = rate.window_start(MINUTE, timezone.now() - timedelta(seconds=seconds))
    return rate.count(REFUSED_USER, user_key(username), since=since)


def count_failure(username, client_key):
    """One more failure of ``username`` from ``client_key``: per username, per pair and per address."""
    rate.hit(FAIL_USER, user_key(username), window_seconds=MINUTE)
    rate.hit(FAIL_PAIR, pair_key(username, client_key), window_seconds=MINUTE)
    rate.hit(FAIL_CLIENT, client_key, window_seconds=MINUTE)


def clear_failures(username) -> int:
    """Delete ``username``'s RateWindow rows: its failures, its refusals and those of every pair it was tried from in
    the last day - under any case of the name, which the keys fold (RateWindow rows older than a day are pruned by the
    daily maintenance). The rows deleted."""
    since = timezone.now() - timedelta(days=1)
    folded = str(username).casefold()
    tried = set(LoginAttempt.objects.filter(username__iexact=username, created_at__gte=since)
                .values_list('username', 'client'))
    pairs = {pair_key(name, key_of_address(address)) for name, address in tried if name.casefold() == folded}
    named = user_key(username)
    deleted = RateWindow.objects.filter(scope__in=(FAIL_USER, REFUSED_USER), key=named).delete()[0]
    if pairs:
        deleted += RateWindow.objects.filter(scope=FAIL_PAIR, key__in=pairs).delete()[0]
    return deleted


class Door:
    """One sign-in attempt at one door (``door``: request_meta.CPT or ADMIN) for one typed ``username`` (as the
    LoginAttempt stores it: at most 150 characters, unstorable ones replaced)."""

    def __init__(self, request, door, username):
        self.request, self.door, self.username = request, door, username
        self.client = request_meta.UNSTORABLE.sub('�', request_meta.client_address(request))
        self.client_key = request_meta.client_key(request)
        self.user_key = user_key(username)
        self.pair_key = pair_key(username, self.client_key)
        self.sign_in_ref = uuid.uuid4()  # this attempt's reference: its LoginAttempt's, and its session's if it signs in

    def account(self):
        """The account the typed name names exactly, or None."""
        return User.objects.filter(username=self.username).first()

    def known_device(self) -> bool:
        """Whether the browser holds a valid known-device cookie for this username (check d)."""
        user_id = device_user_id(self.request.COOKIES.get(device_cookie_name()))
        if user_id is None:
            return False
        try:
            return User.objects.filter(username=self.username, pk=user_id).exists()
        except (ValidationError, ValueError):
            return False

    def refusal(self) -> str:
        """The sentence that refuses this attempt before any password is checked, or '' when it may go on. A refusal is
        counted per minute, per username key and per address key."""
        now = timezone.now()
        since = _since(now)
        client_rows = _rows(FAIL_CLIENT, self.client_key, since) + _rows(REFUSED_CLIENT, self.client_key, since)
        client_rows.sort()
        if sum(count for _, count in client_rows) >= settings.SIGNIN_CLIENT_LIMIT:
            return self._refuse(ADDRESS, _wait_below(client_rows, settings.SIGNIN_CLIENT_LIMIT, now))
        pair_rows = _rows(FAIL_PAIR, self.pair_key, since)
        if sum(count for _, count in pair_rows) >= settings.SIGNIN_PAIR_LIMIT:
            return self._refuse(PAIR, _wait_below(pair_rows, settings.SIGNIN_PAIR_LIMIT, now))
        failures, last = failures_of(self.username, now)
        wait = delay_seconds(failures)
        if wait and last is not None and now < last + timedelta(seconds=wait) and not self.known_device():
            return self._refuse(USERNAME, (last + timedelta(seconds=wait) - now).total_seconds(), failures=failures)
        return ''

    def _refuse(self, check, wait, *, failures=None):
        refused_name = rate.hit(REFUSED_USER, self.user_key, window_seconds=MINUTE)
        refused_address = rate.hit(REFUSED_CLIENT, self.client_key, window_seconds=MINUTE)
        if (refused_address if check == ADDRESS else refused_name) == 1:  # the first refusal of this minute
            account = self.account()
            security_events.record('signin.throttled', subject=account, request=self.request, door=self.door,
                                   check=check, name_key=self.user_key, account_known=account is not None,
                                   failures=failures, refused_this_minute=refused_name,
                                   refused_from_address_this_minute=refused_address)
        sentence = CLIENT_REFUSAL if check == ADDRESS else USER_REFUSAL
        return sentence.format(wait=wait_words(wait))

    def check(self, user, *, allowed, success=LoginAttempt.SIGNED_IN):
        """Record this attempt's password check and answer the account that may go on, or None. ``user`` is what
        authenticate() answered (None: a wrong password or no such account); ``allowed(user)`` says whether this door
        admits the account; ``success`` is the outcome of an admitted one (signed_in, or second_factor_pending at the
        admin door). A staff-set password past STAFF_PASSWORD_UNUSED_SECONDS is refused here, right after the password
        and before anything else (B4, item 4)."""
        if user is None:
            outcome = (LoginAttempt.WRONG_PASSWORD if User.objects.filter(username=self.username).exists()
                       else LoginAttempt.UNKNOWN_ACCOUNT)
        elif staff_password_expired(user):
            outcome = LoginAttempt.PASSWORD_EXPIRED
        elif not allowed(user):
            outcome = LoginAttempt.NO_ACCESS
        else:
            outcome = success
        self.record(outcome)
        if outcome == LoginAttempt.PASSWORD_EXPIRED:
            security_events.record('password.expired_unused', subject=user, request=self.request, door=self.door,
                                   attempt_ref=self.sign_in_ref)
        return user if outcome == success else None

    def record(self, outcome):
        """Write this attempt's LoginAttempt with ``outcome``; a failure is counted toward (a) to (c)."""
        LoginAttempt.objects.create(username=self.username, client=self.client,
                                    succeeded=outcome == LoginAttempt.SIGNED_IN, door=self.door, outcome=outcome,
                                    sign_in_ref=self.sign_in_ref)
        if outcome in FAILURES:
            count_failure(self.username, self.client_key)


def settle_second_factor(request, sign_in_ref, *, signed_in) -> int:
    """The admin door's second step settled (B2): the attempt recorded as second_factor_pending under ``sign_in_ref``
    becomes signed_in (succeeded) or second_factor_failed - a failure counted toward (a) to (c), from the address that
    failed it. The rows changed (0 when none was pending)."""
    pending = LoginAttempt.objects.filter(sign_in_ref=sign_in_ref, outcome=LoginAttempt.SECOND_FACTOR_PENDING)
    if signed_in:
        return pending.update(outcome=LoginAttempt.SIGNED_IN, succeeded=True)
    attempt = pending.first()
    changed = pending.update(outcome=LoginAttempt.SECOND_FACTOR_FAILED, succeeded=False)
    if attempt is not None and changed:
        count_failure(attempt.username, request_meta.client_key(request))
    return changed
