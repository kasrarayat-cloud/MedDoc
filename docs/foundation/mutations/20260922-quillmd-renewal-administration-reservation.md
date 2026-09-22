# Declaration — reserve the B2 renewal key-administration session after policy expiry

A ledger-only act. **No provider call, no credential read or created, no ticket issued or
consumed, no backup, readback, restore or alert.** It is run only when the owner has confirmed
that the designated desktop is ready for the renewal session (see the nonsecret handoff), never
to beat a clock.

## Why this exists

The renewal runbook (`docs/rebuild/offsite-renewal-operations-20260920.md`, step 1) requires a
separate shared reservation **before** the desktop creates, and later revokes, the temporary
account-wide read-only B2 key. The only shipped door, `offsite_operator.py reserve-external`,
validates the policy at the current time and refuses `policy_expired` once the policy lapses
(`automatic_offsite.py:85`, `:304`). The policy lapsed at `2026-09-22T19:32:21.377935Z`.
`rebuild/ops/offsite_renewal_administration.py` (owner decision B, 2026-09-22) reserves this one
kind of work against the expired policy's own limits, validated at its original observation time.

## The act

From `/opt/meddoc-pro` (the shared tree, clean on `main`):

```
bash scripts/run-ruled-mutation.sh \
  --declaration /opt/meddoc-pro/docs/foundation/mutations/20260922-quillmd-renewal-administration-reservation.md \
  -- /opt/meddoc-pro/rebuild/.venv/bin/python -B rebuild/ops/offsite_renewal_administration.py \
  --requests 34 --download-bytes 4456448 --label desktop-key-administration-<UTC date of the session> \
  --session-end <UTC time by which the key is created AND revoked; at most 2 days ahead>
```

34 requests / 4,456,448 bytes repeats the 2026-09-21 decomposition (6 API calls, 4 retries,
24 navigation estimate, at the repository's 131,072-byte per-call floor). Charged in full when
reserved, never refunded. Key creation precedes the audit and revocation follows the import, so
the session can span days: the FULL reservation is charged to every UTC date from the act to the
declared session end (at most 2 days, the ticket window's own bound).

## MUST change

| quantity | declared value |
|---|---|
| `automatic-offsite/budget.json`, every UTC date from the act to `--session-end` | requests **+34**, download bytes **+4,456,448** on EACH of those dates |
| `external_reservations` | exactly one new entry, reference `renewal-administration:<expired-policy sha256[:16]>:desktop-key-administration-<date>` |

## MUST NOT change

| quantity | declared value |
|---|---|
| every other day's counters and every prior reservation | byte-identical |
| `automatic-offsite/renewal/*` (status, tickets, intents, returned audit) | unchanged — no ticket is issued here |
| offsite policy, allocation contract, units, timers | unchanged |
| application database, documents, billing records | untouched |

## Refusals that are correct, not failures

`state_invalid` if the policy is valid again (use `offsite_operator.py reserve-external`) or a
renewal import is running; `budget_exhausted` if the day's limits or the two-per-expired-policy cap
would be exceeded (only this door's own post-expiry entries count toward the cap); `state_invalid`
also for a session end that is malformed, has no time zone, is in the past or is more than 2 days
ahead; `lock_busy` while a backup, readback or other operator holds the lock (retry
after it finishes); `policy_invalid` if the expired policy no longer validates at its original time.
