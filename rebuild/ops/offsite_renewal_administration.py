#!/usr/bin/env python3
"""Reserve the owner's renewal key-administration work AFTER the offsite policy has expired.

The renewal runbook requires a separate shared reservation BEFORE the desktop creates, and later
revokes, the temporary account-wide read-only key. The only door for that,
`offsite_operator.py reserve-external`, validates the policy at the CURRENT time, so from the moment
the policy lapses it refuses with `policy_expired` — while the audit that would renew the policy
still needs exactly that work. `offsite_renewal.py` already survives expiry for the ticket itself
by validating the policy at its ORIGINAL observation time; this door does the same for the
administration reservation, and for nothing else.

⚠️ WHY A NEW MODULE AND NOT AN EDIT. The installed allocation contract pins the sha256 of seven
control sources (`offsite_allocation.SOURCES`), `automatic_offsite.py` and `offsite_operator.py`
among them. Editing either would make every policy validation refuse with `policy_invalid` —
including the historical validation that `issue-ticket` and `import-result` depend on — so the
renewal path would lock itself out. This file is not a control source and changes none of them.

What it keeps, deliberately:
- ADVANCE accounting: the reservation is written to the canonical shared ledger before any
  external activity, and never refunded, re-dated or reset.
- The policy's own daily request and download limits. The desktop session is NOT bounded by the
  worker's run ceiling — key creation precedes the audit and revocation follows the import, hours
  or a day later — so the operator declares when the session ends (at most two days ahead, the
  ticket window's own bound) and the FULL reservation is charged to every UTC date from now to
  that end. Conservative on purpose: unused headroom is lost, spent headroom is never missed.
  Prior consumption is read, never rewritten.
- The canonical exclusion lock (`lock_busy` while any backup, readback, restore or operator
  holds it) and reference uniqueness, plus a small per-expired-policy cap.

What it refuses:
- A policy that is still valid (use `offsite_operator.py reserve-external`), missing or invalid.
- A policy whose historical validation fails, or a renewal import in progress.
- Any request beyond the administration envelope, the daily limits or the per-policy cap.

It admits no backup upload, readback or restore: those reserve through `Budget._reservation`,
which still refuses `policy_expired`. It makes no provider call and reads no credential.
"""
import argparse
from datetime import timedelta
import json
import os
import re

try:
    from . import automatic_offsite as engine, offsite_renewal as renewal, install_offsite_policy as installer
except ImportError:
    import automatic_offsite as engine
    import offsite_renewal as renewal
    import install_offsite_policy as installer

#: One desktop administration session: the 2026-09-21 precedent was 34 requests / 4,456,448
#: bytes (6 calls + 4 retries + 24 navigation at the 131,072-byte per-call floor). The envelope
#: bounds a single reservation; it is not an allowance and is charged in full when reserved.
MAX_REQUESTS = 40
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
#: A failed session may need one more; a third means something is wrong and a person must look.
PER_EXPIRED_POLICY = 2
LABEL = re.compile(r'[a-z0-9][a-z0-9-]{2,62}')
PREFIX = 'renewal-administration:'


def _assert_canonical_lock():
    """Budget.assert_live without its current-policy equality — the policy is expired by design."""
    path = engine.STATE / 'budget.json'
    engine.check(path.parent.resolve() == engine.STATE.resolve() and path.exists(), 'state_invalid')
    held = engine._HELD_LOCKS.get(str(engine.STATE))
    engine.check(held is not None and held[0] == os.getpid(), 'lock_busy')
    info = os.fstat(held[1])
    actual = os.stat(engine.STATE / 'execution.lock', follow_symlinks=False)
    engine.check((info.st_dev, info.st_ino) == (actual.st_dev, actual.st_ino), 'state_invalid')
    return path


def reserve(requests, download_bytes, label, session_end, *, at=None):
    """Charge one bounded renewal-administration session to the shared ledger, before it happens."""
    engine.check(type(requests) is int and 1 <= requests <= MAX_REQUESTS
                 and type(download_bytes) is int and 0 <= download_bytes <= MAX_DOWNLOAD_BYTES, 'state_invalid')
    engine.check(isinstance(label, str) and LABEL.fullmatch(label) is not None, 'state_invalid')
    try:
        end = engine.timestamp(session_end)
    except engine.Refusal:
        raise engine.Refusal('state_invalid') from None      # an operator typo, not a policy fault
    with engine.exclusion(engine.STATE):
        at = at or engine.now()
        engine.check(at < end <= at + timedelta(days=2), 'state_invalid')
        try:
            engine.policy(engine.POLICY, at)
        except engine.Refusal as refusal:
            if refusal.code != 'policy_expired':
                raise
        else:
            raise engine.Refusal('state_invalid')      # still valid: the ordinary door applies
        limits, raw = renewal.historical_limits()      # every original control, at its original time
        engine.check(at >= engine.timestamp(limits['valid_until']), 'state_invalid')
        engine.check(renewal.read_state()['state'] != 'importing', 'state_invalid')
        path = _assert_canonical_lock()
        policy_sha256 = installer.digest(raw)
        scope = PREFIX + policy_sha256[:16] + ':'
        reference = scope + label
        value = engine.budget_ledger(path, at)
        # Only this door can write after expiry (the ordinary door refuses then), so entries in the
        # namespace dated before expiry were written by somebody else and do not use up this cap.
        expired_at = engine.timestamp(limits['valid_until'])

        def after_expiry(item):
            try:
                return engine.timestamp(str(item.get('at', ''))) >= expired_at
            except engine.Refusal:
                return True       # an undatable entry in this namespace counts: fail toward the cap
        prior = [item for item in value['external_reservations']
                 if isinstance(item, dict) and str(item.get('reference', '')).startswith(scope) and after_expiry(item)]
        engine.check(not any(item.get('reference') == reference for item in value['external_reservations']
                             if isinstance(item, dict)), 'state_invalid')
        engine.check(len(prior) < PER_EXPIRED_POLICY, 'budget_exhausted')
        dates, day = [], at.date()
        while day <= end.date():
            dates.append(day.isoformat())
            day += timedelta(days=1)
        for day in dates:
            counters = value['days'].get(day, {'requests': 0, 'download_bytes': 0})
            engine.check(counters['requests'] + requests <= limits['daily_request_budget']
                         and counters['download_bytes'] + download_bytes <= limits['daily_download_budget_bytes'],
                         'budget_exhausted')
        for day in dates:
            counters = value['days'].setdefault(day, {'requests': 0, 'download_bytes': 0})
            counters['requests'] += requests
            counters['download_bytes'] += download_bytes
        entry = {'reference': reference, 'at': at.isoformat(), 'requests': requests,
                 'download_bytes': download_bytes, 'charged_days': dates}
        value['external_reservations'].append(entry)
        value.update(**value['days'][value['day']])
        engine.atomic(path, value)
        return {'complete': True, 'provider_calls': 0, 'reservation': entry,
                'expired_policy_sha256': policy_sha256, 'expired_policy_valid_until': limits['valid_until'],
                'shared_budget': engine.budget_summary(engine.STATE, at)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--requests', required=True, type=int)
    parser.add_argument('--download-bytes', required=True, type=int)
    parser.add_argument('--label', required=True,
                        help='Unique nonsecret name for this session, e.g. desktop-key-administration-20260923.')
    parser.add_argument('--session-end', required=True,
                        help='UTC ISO time by which key creation AND revocation will be finished (at most 2 days ahead).')
    args = parser.parse_args(argv)
    os.umask(0o077)
    print(json.dumps(reserve(args.requests, args.download_bytes, args.label, args.session_end), sort_keys=True))
    return 0


def cli(argv=None):
    """Every refusal is reported as data with exit 1; nothing is written on any refusal."""
    try:
        return main(argv)
    except (engine.Refusal, renewal.Refusal) as error:
        print(json.dumps({'complete': False, 'reason_code': error.code}))
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Unreadable or malformed state: fail closed, nothing was written, and say so as data.
        print(json.dumps({'complete': False, 'reason_code': 'state_invalid'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
