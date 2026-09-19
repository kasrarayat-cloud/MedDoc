# Declaration — private account checks, second run

**Date:** 2026-09-19
**Act:** one further run of `rebuild/verify-private-accounts.mjs` against the permanent private services,
release `6d73c5e9026d974053365468101c2f7921544c6c`.

⚠️ **THE FIRST RUN STOPPED PART WAY. THIS DOCUMENT JUDGES IT BEFORE IT DECLARES ANYTHING NEW**, because a
second declaration written over an unjudged act is how a partial mutation becomes invisible.

## Part 1 — the first run, judged against `20260919-quillmd-account-checks.md`

It ran `05:01:54Z → 05:02:06Z` and stopped at the fifth check with an `AssertionError`. **The application
did nothing wrong. The assertion was wrong**, and the fault is mine:

> `str()` on a `Decimal` uses SCIENTIFIC notation once the exponent is negative and the value is zero. A
> promotional wallet with nothing reserved stringifies as **`0E-12`**, not `0.000000000000`. Measured on
> this host: `str(Decimal('0.000000000000')) == '0E-12'`, while `format(…, 'f') == '0.000000000000'`.

⚠️ **AND IT FAILS ONLY AT ZERO, WHICH IS THE VALUE A MONEY ASSERTION MOST NEEDS TO CHECK** — nothing
reserved, nothing charged, nothing outstanding. Every non-zero amount compares correctly, which is exactly
why it read fine in review and in three refutation passes. The fix is one function on the Python side of
every money field, not a looser comparison on the JavaScript side.

**Every declared quantity, compared. Four checks had passed, so the first invitation and acceptance are
real and are kept.**

| declared | expected | observed | verdict |
|---|---|---|---|
| users | 8 → 9 | **9** | ✅ |
| promotional wallets | 8 → 9 | **9** | ✅ |
| welcome ledger entries | 8 → 9 | **9** | ✅ |
| active memberships | 7 → 8 | **8**, in department `46a5abdd` — the inviting doctor's own | ✅ |
| promotional balance, all wallets | 79.782275898950 → 89.782275898950 | **89.782275898950**, exactly +10 | ✅ |
| audit events | grows, account/auth/email only | 399 → **404**: `auth.login`, `email.outbox`, `department.invite`, `credit.welcome`, `department.invitation_accepted` — no billing action | ✅ |
| private outbox files | grows | 7 → **8** | ✅ |
| invitations / accepted | 4 / 3 → **6 / 5** | **5 / 4** | ⚠️ **SHORT BY ONE — the run stopped before the second invitation was created. Named, not smoothed: the declaration described a complete run and this one is not.** |
| TOTP `last_t` | advances | **59657718, unchanged** | ⚠️ the MFA check never ran |
| Django sessions | grows | 54 → **55** | ✅ |
| the invited account's password | replaced by recovery | **not replaced** | ⚠️ the recovery check never ran |
| jobs | 14 | **14** | ✅ |
| usage rows | 14 | **14** | ✅ |
| provider receipts | 11 | **11** | ✅ |
| reservations / held | 12 / 0 | **12 / 0** | ✅ |
| total charged | 0.217724101050 | **0.217724101050** | ✅ |
| total configured-rate cost | 0.145149400700 | **0.145149400700** | ✅ |
| paid balance | 0 | **0** | ✅ |
| departments | 3 | **3** | ✅ |
| patients | 3 | **3** | ✅ |
| encounters | 12 | **12** | ✅ |
| provider calls | 0 | **0** — `providerJobs: 0`, no `Usage`, `ProviderReceipt` or `Reservation` row moved | ✅ |

**Every MUST-NOT-CHANGE row held. Every MUST-CHANGE row that the completed checks were responsible for
matched exactly.** The three differences are all the same fact stated three times — the run stopped — and
each is recorded against the check that never executed rather than explained away.

**What the repaired mail access proved on the way through**, from the run's own sanitized report: the
confined reader answered before anything was sent (7 files), the invitation was located from **1 changed
path, 1 record for this run, 0 for anybody else, 0 outside the synthetic domain**, and the extracted token
was **43 characters** — exactly `secrets.token_urlsafe(32)`. The check that failed on 2026-09-19 with
`PermissionError` now passes.

## Part 2 — the second run

The first run's rows are **kept, not cleaned up**, and its evidence file
(`rebuild/.runtime/private-accounts-verification.json`) is **retained unmodified**; this run writes to
`rebuild/.runtime/private-accounts-verification-run2.json` (mode 0600). A fresh synthetic identity is used,
so the first account stays exactly as it is.

### Baseline, measured 2026-09-19 after the first run and before this one

| quantity | value |
|---|---|
| users | 9 |
| promotional wallets | 9 |
| welcome ledger entries | 9 |
| active memberships | 8 |
| invitations / accepted | 5 / 4 |
| departments | 3 |
| patients | 3 |
| encounters | 12 |
| jobs | 14 |
| usage rows | 14 |
| provider receipts | 11 |
| reservations / held | 12 / 0 |
| total charged | 0.217724101050 |
| total configured-rate cost | 0.145149400700 |
| promotional balance, all wallets | 89.782275898950 |
| paid balance, all wallets | 0 |
| audit events | 404 |
| confirmed TOTP devices | 1 (`last_t` 59657718) |
| Django sessions | 55 |
| private outbox files | 8 |

### What MUST change

| quantity | from | to |
|---|---|---|
| users | 9 | **10** — one further invited synthetic employee |
| promotional wallets | 9 | **10** |
| welcome ledger entries | 9 | **10** — exactly one for the new account, of exactly `$10.000000000000` |
| active memberships | 8 | **9** — in the inviting doctor's own department, and still 9 after the retried acceptance |
| invitations / accepted | 5 / 4 | **7 / 6** — two invitations to the new address, both accepted |
| promotional balance, all wallets | 89.782275898950 | **99.782275898950** — exactly +10 |
| audit events | 404 | **grows**, and every new row is an account, authentication or email action for this run's synthetic identities |
| TOTP `last_t` | 59657718 | **advances** — verifying the administrator's code consumes that step, which is what makes the replay refusal real |
| private outbox files | 8 | **grows** — two invitation messages and one recovery message, which may share a file |
| the new account's password | set at acceptance | **replaced by recovery** |
| Django sessions | 55 | **grows**, and the new user's pre-recovery session stops working |

### What MUST NOT change

| quantity | value |
|---|---|
| jobs | 14 |
| usage rows | 14 |
| provider receipts | 11 |
| reservations / held | 12 / 0 |
| total charged | 0.217724101050 |
| total configured-rate cost | 0.145149400700 |
| paid balance, all wallets | 0 |
| departments | 3 |
| patients | 3 |
| encounters | 12 |
| provider calls | **0** |
| **the first run's account** | its wallet, welcome entry, membership and invitation are untouched |

A difference outside these tables is the finding. No recording, no generation, no provider contact. No
permission is widened; no token is printed. A private-outbox read demonstrates the APPLICATION's
behaviour, not email delivery.
