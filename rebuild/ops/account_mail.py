"""Locate THIS run's account message AND bind it to the application record that caused it.

⚠️ WHY THIS IS A MODULE AND NOT A STRING IN FOUR HARNESSES. The defect this whole repair exists for was
one reader, copied. `verify-private-release.mjs`, `identity-browser.mjs`, `private-beta-browser.mjs` and
`verify-private-accounts.mjs` each carried their own outbox reader, each matched an address against a
whole FILE, and each took the first link in it — and a refutation pass demonstrated that shape returning
ANOTHER ACCOUNT'S raw invitation token, which those harnesses then navigate to. Putting the selection in
`ops/private_mail` fixed the selection and would have left the same trap open one layer up if the
application-side BINDING were pasted into four inline Python snippets instead. There is one binding, it
lives here, and changing it changes every harness at once.

`ops/private_mail` stays free of application models — it knows outbox files, records and addressees.
This module is the layer that knows what an invitation IS.

**SELECTION AND BINDING ANSWER DIFFERENT QUESTIONS, AND ONLY BOTH ARE SUFFICIENT.**

  · Selection — `private_mail` — asks *was this message written TO me, in a file this run changed*.
  · Binding — here — asks *is this the message THIS RUN CAUSED*.

A stale invitation to the same address, a superseded record, a token lifted from another account's
message and delivered to ours: every one of those answers the first question correctly. Only the second
refuses them, and a failed binding is a REFUSAL — never a fallback to the next candidate, which is the
first-match behaviour this repair removed.

**THE BINDINGS ARE EXACT AND LEAK NOTHING:**

  · an invitation token is bound by `sha256(token) == Invitation.token_hash`. `core/views.py` stores
    `digest(raw)` on the row, so the comparison is an identity check against the record, and a hash is
    not a credential;
  · a recovery token is bound by its `uidb64` segment decoding to the user's own primary key AND
    `default_token_generator.check_token(user, …)` — the application's own verifier, so a token for a
    different user, a superseded password, or an expired window all fail it.

Django imports are DEFERRED into the functions on purpose: `unittest discover -s ops` runs with no
`DJANGO_SETTINGS_MODULE`, and a model import at module scope would take the whole operations suite down
with it.
"""
try:                                    # the house idiom: `discover -s ops` makes this a top-level module
    from . import private_mail
except ImportError:                     # pragma: no cover - import shape, not behaviour
    import private_mail

PURPOSES = ('invite', 'recovery/confirm')


class NoBinding(Exception):
    """No record could be identified to bind the message to. Never carries a token."""


def binding(purpose, address):
    """What the confined helper must be told so it can bind a token to the record this run created.

    Returns `(expectations, final)`. `expectations` are the checks the HELPER applies inside the container,
    before anything is returned; `final` is an optional host-side predicate for a check the container
    cannot compute.

    ⚠️ THE SPLIT IS NOT ARBITRARY, AND IT IS THE WHOLE DESIGN. Everything decidable from bytes plus a
    constant is decided on the SERVICE side of the boundary, so an unrelated record is discarded where it
    lives rather than exported to the operator and rejected afterwards. `check_token` is the one check that
    cannot go in: it needs the secret key and the user's password hash, and the helper has no database and
    no network. It therefore runs last, on a token that has ALREADY satisfied the in-container binding.
    """
    if purpose not in PURPOSES:
        raise NoBinding('no binding is defined for this message purpose')
    address = address.lower()
    if purpose == 'invite':
        from core.models import Invitation
        open_rows = list(Invitation.objects.filter(email=address, accepted_at__isnull=True))
        # Exactly one, or the run cannot say which record it is expecting — and guessing here would put
        # the first-match behaviour back, one layer up from where it was removed.
        if len(open_rows) != 1:
            raise NoBinding('expected exactly one open invitation for this address, found %d' % len(open_rows))
        # `token_hash` IS sha256 of the raw token, so the helper compares without ever holding a
        # credential: a digest is not one, and it identifies the record exactly.
        return {'expect_sha256': open_rows[0].token_hash}, None
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    from core.models import User
    user = User.objects.get(email=address)
    identifier = urlsafe_base64_encode(force_bytes(user.pk))

    def final(token):
        prefix, separator, secret = token.partition('/')
        if not separator or prefix != identifier:
            return False
        return default_token_generator.check_token(user, secret)
    # The helper rejects any token whose first segment is not this user's own identifier; `check_token`
    # then confirms it against the live user, on the host.
    return {'expect_prefix': identifier}, final


def locate(purpose, address, before, notes=None):
    """The `/<purpose>/<token>/` path for this run, bound to its record, or raise.

    ⚠️ THE RETURNED STRING IS THE SECRET ITSELF — the route and the token are one string. Navigate to it.
    Do not log it, store it, assert on it, put it in a report, or pass it to a subprocess.
    """
    expectations, final = binding(purpose, address)
    return private_mail.route(purpose, address, before, notes=notes, verify=final, **expectations)
