# Declaration — desktop credential-administration reservation, September 21, 2026

One additive entry in the shared offsite ledger. **No provider request, no credential read, no
credential creation, no B2 call, no application change, no deploy, no restart.**

## Why a separate reservation exists at all

The shipped runbook is explicit, and it is the reason this declaration exists rather than the work
being folded into the collector's ticket:

> *"Any UI/key-administration work outside the collector needs a separate shared reservation
> **before** the activity; the collector ticket does not grant unlimited browser requests or
> credential administration."*
> — `docs/rebuild/offsite-renewal-operations-20260920.md:61-63`

The live collector ticket `98b609fe6b166bef1b256644373ae3df` reserves **20 requests / 8,388,608
bytes** for the audit run itself. That reservation is **not** touched, borrowed, refunded or
re-dated by this act, and the ticket stays unconsumed.

## The act

    rebuild/.venv/bin/python -B rebuild/ops/offsite_operator.py reserve-external \
      --requests 34 --download-bytes 4456448 \
      --reference desktop-key-administration-20260921-6calls-plus4retry-plus24navigation-cushion

`offsite_operator.py reserve-external` is the shipped, documented entry point for this consumer
class — *"Durable additive reservation, unique evidence reference, no provider request and no
credential read"* (`docs/rebuild/offsite-consumers-20260920.md:30`).

⚠️ **THE RESERVING INSTRUMENT ITSELF EXPIRES BEFORE THE WORK DOES.**
`automatic_offsite.py:304` refuses with `policy_expired` once the installed policy's `valid_until`
passes. That is **2026-09-21T20:16:35.867379Z** — and the policy can only be renewed by the very
audit this reservation enables. After that instant there is no shipped door to create it. This
declaration is therefore written and landed against a hard clock, and that is stated so the
timing is not mistaken for haste.

### Expected delta — exactly one ledger row

| must change | exactly |
|---|---|
| `budget.json` day `2026-09-21` requests | **154 → 188** |
| `budget.json` day `2026-09-21` download_bytes | **44,814,360 → 49,270,808** |
| `external_reservations` | **+1 row**, reference `desktop-key-administration-20260921-6calls-plus4retry-plus24navigation-cushion`, 34 requests, 4,456,448 bytes, `charged_days ["2026-09-21"]` |

| must NOT change | |
|---|---|
| the two collector reservations (`673a83fb…`, `98b609fe…`) | identical, not refunded, not re-dated |
| ticket `98b609fe6b166bef1b256644373ae3df` and its intent | unconsumed, byte-identical |
| `renewal/status.json` | untouched — `reserve_external` writes only `budget.json` |
| the installed policy file and its digest `fc6673a7…` | identical |
| day `2026-09-20` counters and the `legacy_import` block | identical |
| the restricted runtime backup key's scope | unchanged |
| application, services, timers, Tab 1 work | untouched |

### How 34 / 4,456,448 was derived, and what is honestly unknown

The consumers doc warns: *"do not copy example numbers as measurements"*
(`offsite-consumers-20260920.md:66-69`). The 2026-09-20 figure of 31 / 2,000,000 is a declared
cushion, not a measurement, and its **byte** side is a round number derived nowhere. So the
request side reuses that precedent's honest logic and the byte side is re-anchored to this
repository's own per-call response floor, `131072*calls` (`offsite_account_audit.py:348`):

| component | requests | justification |
|---|---|---|
| provisioning `b2_authorize_account` | 1 | existing provisioner; no new credential is created by this act |
| `b2_create_key` (account-wide, `listBuckets`+`listFiles`, no bucketIds, no namePrefix) | 1 | no reviewed cost exists — charged at the floor |
| scope pre-check `b2_authorize_account` with the new key | 1 | proves the key is exactly the required scope before it reaches the collector |
| cleanup-session `b2_authorize_account` | 1 | create and revoke are hours apart; a fresh authorization is the honest assumption |
| `b2_delete_key` | 1 | revocation |
| revocation proof `b2_authorize_account` with the revoked key (expect 401) | 1 | mirrors the 09-20 `fresh_authorization_http_status: 401` evidence |
| failure/retry allowance | 4 | charges are taken **before** I/O and are never refunded |
| **browser/console navigation cushion — UNMEASURED** | **24** | the 09-20 precedent's 20, plus 4, because the route is not fixed and a wholly-console route has no measurement anywhere |
| **total** | **34** | **× 131,072 = 4,456,448 bytes** |

⚠️ **Sizing every request at the floor is deliberate: the reservation then does not depend on
which route the owner chooses.** Console or Native API, the same 34 requests are covered at the
same per-request allowance. **The navigation component is an estimate, is labelled as one, and
cannot be refunded or re-dated afterwards.**

### A scope tension, named rather than silently resolved

`docs/rebuild/offsite-allocation-20260920.md:51-52` says to suspend recurrence and obtain new
account evidence **before** credential changes. `docs/rebuild/offsite-renewal-operations-20260920.md:57-63`
authorizes obtaining the audit credential under only a separate shared reservation. Nothing in the
corpus reconciles them. **This act follows the runbook**, because it is the narrower and later
instruction and it governs this exact handoff step; recurrence is **not** suspended and no timer
is touched. The tension is recorded here so the next reader meets it as a decision, not a gap.

### The instrument's grant lands with it

Per AGENTS.md, an entry that names an instrument verifies that instrument's grant in the same
commit. `grep -c offsite_operator .claude/settings.json` was **0**, as was the venv interpreter
this and every recorded renewal command uses. Both rows are added by this commit.

## What this declaration does not authorize

It does not create, read, transfer or revoke any credential; those are owner-side desktop actions.
No B2 API call, no account-wide inventory, no upload, restore, readback or renewal, no alert
email, no new collector ticket, no deployment or restart, no change to the master key or to the
restricted runtime backup key, and no public launch. **It does not renew the policy** — only a
returned, validated and imported audit result does that.
