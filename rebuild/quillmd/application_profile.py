"""V1 application profile: the settings that decide synthetic versus real operation.

Pure functions over an environment mapping, with no Django import, so the settings module can
call them at import time and tests can call them with a plain dict.

Every setting here has a default that keeps the private synthetic system exactly as it was
before the profile existed. Values that are not recognised REFUSE rather than fall back: a
typo in a data-mode or payment-mode switch must stop the process, never quietly select a mode.

Messages name settings, never values. Several of the values are credentials.
"""
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit

DATA_MODES = ('synthetic', 'real')
REGISTRATION_MODES = ('open', 'invite')
STRIPE_MODES = ('test', 'live')
BOOLEAN_WORDS = ('false', 'true')

#: Stripe server keys by mode. A publishable key, a webhook secret or the other mode's key never
#: matches; the patterns are anchored and allow no whitespace.
STRIPE_KEY_PATTERNS = {
    'test': re.compile(r'(?:sk|rk)_test_[A-Za-z0-9_]+'),
    'live': re.compile(r'(?:sk|rk)_live_[A-Za-z0-9_]+'),
}

#: Stripe's webhook endpoint signing secret. The webhook verifies every event with the configured value exactly as
#: settings holds it (unstripped), so the startup check tests that same value.
WEBHOOK_SECRET_PATTERN = re.compile(r'whsec_[A-Za-z0-9]+')

#: The doctor surface's host: the only host an emailed link or a Checkout return may name. The administrator host is
#: in ALLOWED_HOSTS too, but a clinician or payer sent there lands on a surface that answers 404 to doctor pages.
DOCTOR_HOST = 'app.quillmd.com'
#: The only spelling accepted for the application origin: lower-case https, the host, an optional port without
#: leading zeros, an optional trailing '/'. urlsplit forgives what a link built from the raw value does not: leading
#: control characters, an empty user ('@'), an empty port (':'), upper case, repeated slashes.
ORIGIN_FORM = re.compile(r'https://[a-z0-9.-]+(?::[1-9][0-9]{0,4})?/?')

#: Hosts a recipient's browser cannot reach, or that exist only inside the test client.
NON_PUBLIC_HOSTS = frozenset({'localhost', '127.0.0.1', '::1', 'testserver', '0.0.0.0'})

#: The largest promotional grant the setting accepts. A bound, not a policy: it stops a typo
#: (an extra zero) from minting credit that is spent on real provider calls.
WELCOME_CREDIT_MAX = Decimal('500')
WELCOME_CREDIT_DEFAULT = '10'


class ProfileError(ValueError):
    """An unsafe or unrecognised profile setting. The message names settings only."""


def raw(env, name, default=''):
    """The configured text, with an empty assignment (``NAME=``) read as unset."""
    value = env.get(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def choice(env, name, allowed, default):
    value = raw(env, name, default)
    if value not in allowed:
        raise ProfileError(f'{name} must be one of: {", ".join(allowed)}.')
    return value


def flag(env, name, default='0'):
    """A '0'/'1' switch. Anything else refuses instead of meaning 'off'."""
    return choice(env, name, ('0', '1'), default) == '1'


def welcome_credit(env):
    """QUILLMD_WELCOME_CREDIT as an exact Decimal in whole cents, 0 to WELCOME_CREDIT_MAX."""
    text = raw(env, 'QUILLMD_WELCOME_CREDIT', WELCOME_CREDIT_DEFAULT)
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        raise ProfileError('QUILLMD_WELCOME_CREDIT must be a US dollar amount such as 10 or 12.50.') from None
    if (not amount.is_finite() or amount < 0 or amount > WELCOME_CREDIT_MAX
            or amount != amount.quantize(Decimal('0.01'))):
        raise ProfileError(f'QUILLMD_WELCOME_CREDIT must be between 0 and {WELCOME_CREDIT_MAX} US dollars, in whole cents.')
    return amount


def deepgram_mip_opt_out(env, data_mode):
    """QUILLMD_DEEPGRAM_MIP_OPT_OUT: 'true' or 'false' when set. Unset follows the data mode: real mode sends
    'true' (and `real_mode_problems` refuses 'false'); synthetic mode returns None, meaning the parameter is
    not sent at all, exactly the request as it was before V1."""
    if not raw(env, 'QUILLMD_DEEPGRAM_MIP_OPT_OUT'):
        return 'true' if data_mode == 'real' else None
    return choice(env, 'QUILLMD_DEEPGRAM_MIP_OPT_OUT', BOOLEAN_WORDS, 'true')


def dollars(amount):
    """'$10' for a whole amount, '$12.50' otherwise — the wording the product has always used."""
    amount = Decimal(amount)
    return f'${amount:,.0f}' if amount == amount.to_integral_value() else f'${amount:,.2f}'


def public_https_origin_problem(value, allowed_hosts):
    """Why `value` is not an explicit public HTTPS origin, or None when it is."""
    if not value:
        return 'must be set explicitly'
    origin = value.rstrip('/')
    try:
        parsed = urlsplit(origin)
        parsed.port  # A malformed or out-of-range port raises here.
    except ValueError:
        return 'must be a valid https origin'
    if parsed.scheme != 'https':
        return 'must be an https origin'
    # '?' and '#' are refused as characters, not by what urlsplit parses: an EMPTY query or fragment
    # parses as '' and passes a truthiness test, yet every link built on it lands after the '?' or '#'.
    if (parsed.username or parsed.password or parsed.query or parsed.fragment or '?' in value or '#' in value
            or parsed.path not in ('', '/') or any(character.isspace() for character in origin)):
        return 'must be an origin only (scheme and host, no path, query, fragment or credentials)'
    if parsed.port == 0:
        return 'must not name port 0'
    host = (parsed.hostname or '').lower()
    if not host or host in NON_PUBLIC_HOSTS or host.endswith('.localhost'):
        return 'must name a public host, not a loopback or test host'
    if host not in allowed_hosts:
        return 'must name one of the allowed application hosts'
    if host != DOCTOR_HOST:
        return f'must name the doctor host {DOCTOR_HOST}, not the administrator surface or another allowed host'
    if not ORIGIN_FORM.fullmatch(value):
        return (f'must be written exactly as https://{DOCTOR_HOST}, optionally with :port '
                '(lower case; no empty user or port, leading zeros, control characters or extra slashes)')
    return None


def stripe_key_matches(key, mode):
    return isinstance(key, str) and STRIPE_KEY_PATTERNS[mode].fullmatch(key) is not None


def explicit_origin_problem(env, app_base_url, allowed_hosts):
    """QUILLMD_APP_BASE_URL must be SET (the default is a loopback development origin), and the value
    settings actually holds must be a public https origin."""
    if not raw(env, 'QUILLMD_APP_BASE_URL'):
        return 'must be set explicitly'
    return public_https_origin_problem(app_base_url, allowed_hosts)


def real_mode_problems(env, *, allowed_hosts, session_cookie_secure, csrf_cookie_secure, email_mode, app_base_url,
                       stripe_mode, stripe_secret_key):
    """Every reason QUILLMD_DATA_MODE=real may not start, as '<SETTING> <requirement>' lines.

    An empty list means the production-required settings are present and safe. The keyword
    arguments are the values settings.py actually computed, so what is checked is what the process
    will use — a stray space that settings would not strip cannot pass here and fail later.
    """
    problems = []
    if raw(env, 'QUILLMD_HTTPS', '0') != '1':
        problems.append('QUILLMD_HTTPS must be 1')
    if not session_cookie_secure:
        problems.append('SESSION_COOKIE_SECURE must be on (set QUILLMD_HTTPS=1)')
    if not csrf_cookie_secure:
        problems.append('CSRF_COOKIE_SECURE must be on (set QUILLMD_HTTPS=1)')
    if raw(env, 'QUILLMD_REGISTRATION', 'open') != 'invite':
        problems.append("QUILLMD_REGISTRATION must be 'invite'")
    # Only 'resend' selects a transport. Every other value, not just 'file', writes account
    # email to the private outbox on this host, so nobody would receive a verification link.
    if email_mode != 'resend':
        problems.append("QUILLMD_EMAIL_MODE must be 'resend' (anything else writes to the private file outbox)")
    if raw(env, 'QUILLMD_PREVIEW_AUTH_ENABLED', '0') == '1':
        problems.append('QUILLMD_PREVIEW_AUTH_ENABLED must be off')
    # The preview gate's shared login is appended to invitation and recovery email, with
    # copy that tells the recipient to use synthetic information only. Any value refuses, whitespace
    # included: settings keeps it unstripped, and a blank-looking one makes every account email fail.
    for name in ('QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME', 'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD'):
        if env.get(name):
            problems.append(f'{name} must be unset')
    if raw(env, 'QUILLMD_MFA_REQUIRED_ALL', '0') != '1':
        problems.append('QUILLMD_MFA_REQUIRED_ALL must be 1')
    if raw(env, 'QUILLMD_DEEPGRAM_MIP_OPT_OUT', 'true') != 'true':
        problems.append("QUILLMD_DEEPGRAM_MIP_OPT_OUT must be 'true'")
    # Real data mode takes payments only in live mode, or none at all. With a sandbox mode and any
    # server key present, a payment made with Stripe's public test card would become paid balance
    # that funds real provider calls. Any value counts as present, computed or configured.
    if stripe_mode != 'live' and (stripe_secret_key or raw(env, 'STRIPE_SECRET_KEY')):
        problems.append("QUILLMD_STRIPE_MODE must be 'live' while STRIPE_SECRET_KEY is set "
                        '(a sandbox payment would become spendable credit); unset STRIPE_SECRET_KEY to run without payments')
    origin = explicit_origin_problem(env, app_base_url, allowed_hosts)
    if origin:
        problems.append(f'QUILLMD_APP_BASE_URL {origin}')
    return problems


def stripe_live_problems(env, *, allowed_hosts, secret_key, webhook_secret, app_base_url):
    """Every reason QUILLMD_STRIPE_MODE=live may not start. Test mode has none: it is today's.

    Like `real_mode_problems`, the keyword arguments are the values settings.py computed.
    """
    problems = []
    if not stripe_key_matches(secret_key, 'live'):
        problems.append('STRIPE_SECRET_KEY must be a live secret or restricted key (sk_live_ or rk_live_)')
    # A padded value or another kind of key can never verify a signature: every paid event would be refused, charged
    # and never credited. The value checked is the one the webhook uses, and the environment must hold exactly it.
    # A well-formed secret of a DIFFERENT endpoint cannot be detected here; the bounded live payment test finds it.
    if not (isinstance(webhook_secret, str) and WEBHOOK_SECRET_PATTERN.fullmatch(webhook_secret)
            and env.get('STRIPE_WEBHOOK_SECRET') == webhook_secret):
        problems.append('STRIPE_WEBHOOK_SECRET must be the endpoint signing secret exactly (whsec_ followed by letters '
                        'and digits, no spaces), or paid checkouts are never credited')
    # The preview gate answers 403 to Stripe's webhook, which carries no preview grant: a paid live
    # checkout would be charged and never credited. Read raw, like real mode: the stricter reading.
    if raw(env, 'QUILLMD_PREVIEW_AUTH_ENABLED', '0') == '1':
        problems.append('QUILLMD_PREVIEW_AUTH_ENABLED must be off (the preview gate refuses the Stripe webhook, '
                        'so paid checkouts are never credited)')
    origin = explicit_origin_problem(env, app_base_url, allowed_hosts)
    if origin:
        problems.append(f'QUILLMD_APP_BASE_URL {origin} (Checkout returns the payer there)')
    return problems
