"""Sign-in slows down instead of locking anyone out (release 1, B1; RELEASE-1-SPEC 4, B1). Both doors - cpt.quillmd.com's
studio.views.login_view and admin.quillmd.com's admin_login_view - open a Door for each attempt, ask it for a refusal
BEFORE any password is checked, and hand it the result of the password check, which writes the attempt's LoginAttempt.

The checks, in order, all before Argon2 runs (Door.refusal):
  (a) address flood: failed attempts from the client's key - an IPv4 address, or an IPv6 address's /64
      (studio.request_meta.client_key) - in the window reach SIGNIN_CLIENT_LIMIT: refused from that address only. Only
      attempts that reached the password check and failed count; a refusal never does, so the refusal ends once the
      failures leave the window, however often the network keeps trying meanwhile (refutation r2, finding 9);
  (b) pair: failures for (the username, the client's key) reach SIGNIN_PAIR_LIMIT: refused from that pair only;
  (c) username delay: failures for the username from any address reach SIGNIN_USER_DELAY_AFTER: the next try waits
      min(SIGNIN_DELAY_BASE_SECONDS * 2 ** (n - SIGNIN_USER_DELAY_AFTER), SIGNIN_DELAY_MAX_SECONDS) after the last
      failure. It never locks: the wait never grows past the ceiling, and refusals do not lengthen it;
  (d) known device: a valid device cookie for this username (device_cookie_name(): signed with django.core.signing,
      salt 'cpt-device', holding the account's id, a random id and the issue date - never a session; HttpOnly, Secure
      under HTTPS, SameSite=Strict, Path=/; KNOWN_DEVICE_DAYS long; set on every successful sign-in by
      studio.sessions.SessionPolicyMiddleware) skips (c), never (a) or (b);
  (e) known address: an attempt from a client key - an IPv4 address, or an IPv6 /64 - from which this username signed
      in within KNOWN_DEVICE_DAYS (a LoginAttempt that succeeded, older rows included) skips (c) too, never (a) or (b):
      someone else's failures, sent from anywhere for as long as they like, cannot keep a doctor out of the office
      they sign in from (refutation r2, finding 8). A doctor on a new network without the device cookie still waits
      while someone keeps the delay armed: the delay never exceeds SIGNIN_DELAY_MAX_SECONDS, and clear_signin_failures
      is the way back.
The window is SIGNIN_WINDOW_SECONDS. The refusal sentence is the same whether or not the account exists (USER_REFUSAL;
CLIENT_REFUSAL for (a)), and every refusal is answered before the password hasher runs (AUTH-3, L-AVAIL).

The counts live in RateWindow rows (studio.rate), one per minute: failures per username, per pair and per address, and
refusals per username and per address. The pair's and the address's places are taken before the password is checked,
one atomic hit each (reserve), and given back unless the attempt fails, so attempts sent at the same moment never pass a
limit together (refutation r2, finding 10); the username's failure is counted after the check. A username is only ever counted as its keyed hash (user_key), never as typed
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
from - and is what the console's unlock (Lane 3) and the ruled act clear_signin_failures --username call;
clear_address(key) deletes an address's - its failures, its refusals and the pairs tried from it - for
clear_signin_failures --address (address_key reads the address given). Each act writes its own SecurityEvent.
LoginAttempt rows are never deleted here.

The earlier LOGIN_THROTTLE_* lockout settings are gone (release 1); nothing reads them.
"""
from __future__ import annotations

import ipaddress
import math
import secrets
import uuid
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import F, Max, Sum
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


def address_key(text) -> str:
    """The client key of an address given to clear_signin_failures --address: an IPv4 address as it is, an IPv6
    address or /64 prefix as its /64 (an IPv4-mapped one as its IPv4 address) - request_meta.client_key's own reading.
    ValueError for anything else (a name, a wider or narrower network, a range)."""
    text = str(text or '').strip()
    if '/' in text:
        network = ipaddress.ip_network(text)  # strict: host bits set is no prefix
        if network.version != 6 or network.prefixlen != 64:
            raise ValueError('an address is an IPv4 address, or an IPv6 address or /64 prefix')
        text = str(network.network_address)
    ipaddress.ip_address(text)  # ValueError when it is no address
    return key_of_address(text)


def clear_address(key) -> int:
    """Delete the RateWindow rows of the client key ``key``: its failures and refusals, and those of every pair a name
    was tried in from it in the last day (RateWindow rows older than a day are pruned by the daily maintenance). The
    rows deleted."""
    since = timezone.now() - timedelta(days=1)
    tried = set(LoginAttempt.objects.filter(created_at__gte=since).values_list('username', 'client').distinct())
    pairs = {pair_key(name, key) for name, address in tried if key_of_address(address) == key}
    deleted = RateWindow.objects.filter(scope__in=(FAIL_CLIENT, REFUSED_CLIENT), key=key).delete()[0]
    if pairs:
        deleted += RateWindow.objects.filter(scope=FAIL_PAIR, key__in=pairs).delete()[0]
    return deleted


def reserve(scope, key, limit, now=None) -> bool:
    """Take one place of (scope, key)'s ``limit`` in the sign-in window BEFORE a password is checked, and answer whether
    it is within the limit. The place is one atomic hit (rate.hit), whose own count says where this attempt stands, so
    two attempts sent at the same moment can never both take the last place (refutation r2, finding 10). A place over
    the limit is given back at once, so a refusal never counts; the caller gives back one that turns out not to be a
    failure (give_back)."""
    now = now or timezone.now()
    start = rate.window_start(MINUTE, now)
    earlier = sum(count for window, count in _rows(scope, key, _since(now)) if window < start)
    if earlier + rate.hit(scope, key, window_seconds=MINUTE) > limit:
        give_back(scope, key)
        return False
    return True


def give_back(scope, key):
    """Give back one place of (scope, key) taken by reserve: its newest window's count goes down by one, never below
    zero."""
    newest = (RateWindow.objects.filter(scope=scope, key=key, count__gt=0).order_by('-window_start')
              .values_list('pk', flat=True).first())
    if newest is not None:
        RateWindow.objects.filter(pk=newest, count__gt=0).update(count=F('count') - 1)


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
        self.reserved = []  # the (scope, key) places refusal() took for this attempt, before its password is checked

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

    def known_address(self) -> bool:
        """Whether this username signed in from this client key - this IPv4 address, or this IPv6 address's /64 - within
        KNOWN_DEVICE_DAYS (check e): any LoginAttempt of the name that succeeded, an older release's rows included (they
        carry succeeded alone), its client read as a client key (key_of_address)."""
        since = timezone.now() - timedelta(days=settings.KNOWN_DEVICE_DAYS)
        addresses = (LoginAttempt.objects.filter(username=self.username, succeeded=True, created_at__gte=since)
                     .values_list('client', flat=True).distinct())
        return any(key_of_address(address) == self.client_key for address in addresses)

    def refusal(self) -> str:
        """The sentence that refuses this attempt before any password is checked, or '' when it may go on. The address's
        and the pair's places are taken first (reserve: one atomic hit each, so attempts sent at the same moment can
        never all pass a limit one place short - refutation r2, finding 10); record() keeps them as this attempt's
        failure, or gives them back. A refused attempt gives back what it took, and is counted per minute, per
        username key and per address key."""
        now = timezone.now()
        since = _since(now)
        if not reserve(FAIL_CLIENT, self.client_key, settings.SIGNIN_CLIENT_LIMIT, now):
            client_rows = _rows(FAIL_CLIENT, self.client_key, since)  # checked failures only: a refusal never counts
            return self._refuse(ADDRESS, _wait_below(client_rows, settings.SIGNIN_CLIENT_LIMIT, now))
        self.reserved.append((FAIL_CLIENT, self.client_key))
        if not reserve(FAIL_PAIR, self.pair_key, settings.SIGNIN_PAIR_LIMIT, now):
            self.give_back()
            return self._refuse(PAIR, _wait_below(_rows(FAIL_PAIR, self.pair_key, since), settings.SIGNIN_PAIR_LIMIT,
                                                  now))
        self.reserved.append((FAIL_PAIR, self.pair_key))
        failures, last = failures_of(self.username, now)
        wait = delay_seconds(failures)
        if wait and last is not None and now < last + timedelta(seconds=wait) and not self.known_device() \
                and not self.known_address():
            self.give_back()
            return self._refuse(USERNAME, (last + timedelta(seconds=wait) - now).total_seconds(), failures=failures)
        return ''

    def give_back(self):
        """Give back every place refusal() took for this attempt."""
        for scope, key in self.reserved:
            give_back(scope, key)
        self.reserved = []

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
        """Write this attempt's LoginAttempt with ``outcome``; a failure is counted toward (a) to (c): the places
        refusal() took are its address's and its pair's failure (an attempt that took none - setup's sign-in - is
        counted there now), and its username's is counted here. Any other outcome gives the places back."""
        LoginAttempt.objects.create(username=self.username, client=self.client,
                                    succeeded=outcome == LoginAttempt.SIGNED_IN, door=self.door, outcome=outcome,
                                    sign_in_ref=self.sign_in_ref)
        if outcome in FAILURES:
            rate.hit(FAIL_USER, self.user_key, window_seconds=MINUTE)
            for scope, key in ((FAIL_PAIR, self.pair_key), (FAIL_CLIENT, self.client_key)):
                if (scope, key) not in self.reserved:
                    rate.hit(scope, key, window_seconds=MINUTE)
            self.reserved = []
        else:
            self.give_back()


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
