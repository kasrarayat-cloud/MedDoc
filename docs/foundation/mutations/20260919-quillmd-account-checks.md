# Declaration — private invitation and password-recovery verification

**Date:** 2026-09-19
**Act:** one run of `rebuild/verify-private-accounts.mjs` against the permanent private services
(`127.0.0.1:9130` doctor, `127.0.0.1:9131` admin), serving release
`6d73c5e9026d974053365468101c2f7921544c6c`.
**Why it is declared:** the run CREATES rows in the live private-staging database — a user, a wallet, a
welcome grant, a membership — and rows cannot be un-created. §2.5's product is that the comparison has one
correct answer, fixed before the evidence exists.

## What this act is NOT

- **No recording, no generation, no provider contact of any kind.** `providerJobs` must be `0` in the
  report and no `Usage`, `ProviderReceipt` or `Reservation` row may appear. The recording milestone is
  accepted as complete on its retained evidence and is not re-run.
- **No permission is widened.** No directory mode, group, ACL or unit file changes; no sudo; no
  token-retrieval endpoint; MFA stays enforced. The outbox is read through the existing confined
  service-identity reader (`ops/private_storage`), narrowed by `ops/private_mail` to the single message
  RECORD addressed to this run's own synthetic address.
- **⚠️ NOT A DEMONSTRATION OF EMAIL DELIVERY.** `QUILLMD_EMAIL_MODE` is `file`. Reading the private outbox
  shows that the APPLICATION composed and handed off the message. It shows nothing whatever about whether
  a message would arrive in a real mailbox, and nothing here may be reported as if it did.
- **No token is recorded.** The invitation and recovery links ARE their tokens
  (`core/email_delivery.py` builds `{origin}/{route}/{raw_token}/`). They are navigated to and never
  logged, never written to the report, never passed as a process argument and never an operand of an
  assertion. The report records `describe()`: that a route was found, of what kind, of what length.

## Baseline, measured 2026-09-19 before the act

| quantity | value |
|---|---|
| users | 8 |
| promotional wallets | 8 |
| welcome ledger entries | 8 |
| active memberships | 7 |
| invitations / accepted | 4 / 3 |
| departments | 3 |
| patients | 3 |
| encounters | 12 |
| jobs | 14 |
| usage rows | 14 |
| provider receipts | 11 |
| reservations / held | 12 / 0 |
| total charged | 0.217724101050 |
| total configured-rate cost | 0.145149400700 |
| promotional balance, all wallets | 79.782275898950 |
| paid balance, all wallets | 0 |
| audit events | 399 |
| confirmed TOTP devices | 1 (`last_t` 59657718) |
| private outbox files | 7 |

## What MUST change

| quantity | from | to |
|---|---|---|
| users | 8 | **9** — one invited synthetic employee |
| promotional wallets | 8 | **9** |
| welcome ledger entries | 8 | **9** — exactly one, and exactly `$10.000000000000` |
| active memberships | 7 | **8** — in the inviting doctor's own department, not another, and still 8 after the second acceptance |
| invitations / accepted | 4 / 3 | **6 / 5** — TWO invitations to the one address |
| promotional balance, all wallets | 79.782275898950 | **89.782275898950** — exactly +10 |
| audit events | 399 | **grows** |
| TOTP `last_t` | 59657718 | **advances** — verifying the administrator's code consumes that step, which is what makes the replay refusal real |
| private outbox files | 7 | **grows** — two invitation messages, one recovery message (they may share a file: the filenames carry one second of entropy and the application appends) |
| the invited account's password | set at acceptance | **replaced by recovery** |
| Django sessions | 54 | **grows**, and the invited user's pre-recovery session stops working |

⚠️ **WHY TWO INVITATIONS, WHEN THE CHECK IS ABOUT ONE GRANT.** The welcome grant's idempotency key is
`welcome:{user.pk}`, and a GET on a spent invitation link cannot reach it: `invite_accept` opens with
`get_object_or_404(..., accepted_at__isnull=True)`, so a consumed link answers 404 before a line of the
acceptance path runs. A refutation pass demonstrated that a build which re-keyed the grant per invitation
would fund the wallet twice and still pass that check. The only way to call `welcome_credit()` a second
time is a SECOND invitation accepted by the now-existing, signed-in user — so the run issues two, accepts
both, and the declared delta says so in advance.

⚠️ **EVERY new audit row must be an account, authentication or email action attributable to this run's
synthetic identities.** A billing, job, usage or reconciliation action appearing in that set is the
finding, whatever explanation is available afterwards.

## What MUST NOT change

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

A difference outside this table is the finding. The clinical-count rows (patients, encounters) are never
omitted: a run that moves them has done something nobody asked for.

## Preserving the earlier failed run

The earlier attempt was the twelfth check of the whole-release harness, recorded at
`rebuild/.runtime/beta-deployed-browser-verification.json` — release `6d73c5e9026d974053365468101c2f7921544c6c`,
`complete: false`, eleven checks passed and *"Private invitation, single welcome grant, and password
recovery work after deployment"* `false`. It failed at its mail step because its helper ran as the
OPERATOR account and could not read the application's private outbox, which was the OS isolation working
exactly as designed.

**That file is retained byte-for-byte and is not rewritten.** This run writes to a SEPARATE file,
`rebuild/.runtime/private-accounts-verification.json` (mode 0600), so the failed result and the repaired
result both stand and the record shows which was which.
