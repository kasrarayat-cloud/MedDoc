# Administration console — assessment and acceptance, 2026-09-21

**Branch** `feat/admin-console-operability` · **base** `main` at `e66d84ab` (the merge of PR #1250)
**Status** UNMERGED and UNDEPLOYED, deliberately. See *Integration order* at the foot.

> **The outcome this was measured against:** an administration console the owner can use to
> manage accounts, investigate failures and explain charges **without terminal commands**.

---

## 1 · How the assessment was done, and why it is not just my opinion

Ten auditors, one per stated requirement, read the existing console against the code and against
the isolated synthetic database. Each was required to cite FILE:LINE and a concrete reproduction,
and each returned what **already works** as well as what is missing — the reuse list mattered as
much as the gap list, because most of this console did not need rebuilding.

Every claimed gap was then handed to an independent **refuter** whose default position was that
the claim is wrong: the capability already exists somewhere, the evidence does not say what the
claimant thinks, or a recorded decision excludes it.

| | count |
|---|---|
| requirements audited | 10 |
| gaps claimed | 99 |
| **gaps refuted** — already reachable, inaccurate, or deliberately excluded | **25** |
| **gaps confirmed** | **74** |

**The refutation changed what got built, in both directions**, and three cases are worth naming:

- **A console "issue refund" button was refused, and refusing it was correct.** The application's
  Stripe credential is deliberately Checkout-write-only
  (`docs/rebuild/production-payments-checklist-20260921.md`), so such a button could only move
  QuillMD's ledger while no money moved — manufacturing exactly the Stripe/ledger divergence the
  webhook design prevents. Refunds are issued in Stripe and arrive here as signed events.
- **A "force-resolve a stuck job" button was refused.** The worker unit carries
  `Restart=on-failure`, so the honest console-side answer is a *warning*, not a mutation. That is
  what was built.
- **It caught a defect in my own work.** I replaced `floatformat:6` on the admin credits table
  with exact rendering. The refuter pointed out that `billing.html` — *the doctor's own page* —
  applies the identical filter, so fixing one surface and not the other would leave the owner
  explaining a charge from a different number than the person they are explaining it to. Both
  surfaces now use one filter.

Full per-gap verdicts: the workflow journal, and §6 below for what was deliberately left.

---

## 2 · Defects where the console was telling the owner something untrue

These were the priority: a missing feature is visible, a wrong number is not.

### 2.1 An evidence type the form accepted and the screen could not offer

`templates/admin_dashboard.html` hand-wrote the reconciliation evidence picker and closed one
option with an attribute — `</option value="provider_report">`. A parser sees a *closing* tag, so
the rendered control offered exactly two values: the empty prompt and **Provider invoice**.

Measured in a real Chromium against that exact markup:

```
[ {"value": "",        "text": "Select authenticated evidence type"},
  {"value": "invoice", "text": "Provider invoice"} ]
```

`ReconciliationForm` has always accepted `provider_report`. So an administrator recording a
provider **cost report** — which the surrounding prose is at pains to distinguish ("an
open-period report is not an invoice") — had one selectable option, and it was the wrong one.
That flag is what `CostReconciliation.invoice_reconciled` is computed from, so the typo
converted every cost report into an invoice-reconciled actual.

**Fixed** by rendering the form's own choices, so the control cannot drift from the form again.

### 2.2 Money that was rounded, and rounded in the wrong direction

Balances are `DecimalField(max_digits=24, decimal_places=12)`. Measured through this project's own
Django:

| stored | `floatformat:6` (before) | exact (now) |
|---|---|---|
| `0.000000499999` | `0.000000` — a real balance shown as nothing | `$0.000000499999` |
| `0.000000999999` | `0.000001` — **more money than the account holds** | `$0.000000999999` |
| `10.000000000000` | `10.000000` | `$10.00` |
| `0E-12` | `0.000000` | `$0.00` |

Elsewhere the raw `{{ value }}` printed all twelve stored places, and inconsistently
(`1234.5` renders as `1234.5`, not `1234.500000`). One filter now serves the admin console, the
charge-evidence page **and** the doctor's billing page: it never rounds, never uses scientific
notation, pads to cents, and round-trips back to the identical `Decimal` (asserted for nine
values). Stripe amounts print as dollars instead of `2500 ¢`.

### 2.3 Three states the console reported as their opposite

- **An unverified account rendered a green "Active" badge.** It cannot sign in at all.
- **A membership read "Active" for an account the console had just suspended.** The server rule
  (`core.security.membership`) requires an active membership *and* an enabled *and* verified
  account; the column showed only the first. It now shows effective access, with the raw
  membership flag beside it.
- **A fully refunded payment kept a green `paid` badge for its full amount.** Gross, refunded and
  net are now separate columns, and a refund that never reached the ledger says so in words.

### 2.4 A status panel with no signal in it

`integrations.html` wrote the whole status **sentence** into the CSS class
(`class="badge {{ integration.status }}"`). No sentence matches a badge variant, so "Not
connected" and "Unavailable" rendered in the same neutral grey as "Licensed feed configured" —
a panel whose only job is to be scanned returned nothing. Each row now carries a `severity`; the
two strings pinned by existing tests are unchanged.

---

## 3 · What the owner can now do without a terminal

### Business overview
Money at the top, each tile carrying **the expression that produced it**: charged to paid
balances, charged to promotional credit, provider cost (configured estimate *and*
evidence-reconciled, separately), costs carried by QuillMD, paid in, refunded out, promotional
credit granted. Below that, position as of now (unspent promotional, unspent paid, reserved) and
a "needs someone" row (usage awaiting evidence, charges waiting for funds, jobs with no
established outcome).

⚠️ **One number is deliberately NOT computed: revenue, or margin.** Work funded by a promotional
credit debits a wallet while no cash ever arrives, so collapsing the two into one figure encodes
an accounting policy this product has not chosen. The components are exact and the single
subtraction shown states both of its terms. **This is an owner decision and it is flagged in §7.**

### A date window
`from`/`to`, inclusive UTC calendar days, applied to every paginated list and to the flow
figures. An unreadable or inverted range **narrows nothing and says so** — silently ignoring it
would put an all-time total under a date heading. Balances deliberately ignore the window,
because a balance has no date range, and the page says that where the balances are.

### One page per account
`/console/accounts/<id>/detail/`: enabled/suspended, verified/not, **MFA enrolment** (visible
nowhere before), last sign-in, promotional vs paid vs reserved vs charged, the organization
wallet that pays when the department bills the organization, memberships with effective access,
payments with refunded and net, and an audit trail of actions **by** the account *and on it* —
the latter unreachable before, because `target` stores a UUID the console never printed.

### Sign out everywhere, without suspending
The only way to invalidate a session was to disable the account, which conflates "laptop left on
a train" with "no longer works here". Both are audited; the audit row records which was done.

### Organizations, roles and who pays
`/console/organizations/`: the tree, every membership with effective access, outstanding
invitations with a revoke control, and **`Department.organization_pays`** — the flag that decides
which balance is billed, previously visible nowhere and changeable nowhere in the product.
Two refusals are enforced and tested: an administrator's membership is not edited here, and a
department is never left without an active owner. Changing the payer is **not** retrospective and
the screen says so, because an administrator who believes otherwise will explain a charge wrongly.

### Failed jobs, and whether anything is running at all
A Processing panel: queued, running, **past the staleness bound**, awaiting a decision, and funds
held on open jobs. Jobs now show started/finished, not only created.

⚠️ **The worker-liveness reading is an inference with a proof, stated as such.** The web process
cannot see the worker. `core.jobs.mark_stale` moves any job running beyond five minutes to
`reconciliation` and runs on every pass of the worker loop — so a job that has outlived that
bound **establishes that the reaper has not run**. The panel says that, rather than "the worker is
down". And an empty queue is reported as proving nothing either way, rather than as green.

### Services, and backups
`/console/services/` separates **Configured** (is a key present, what shape) from **Observed**
(ffprobe/ffmpeg presence, email delivery counted from the audit rows every send already writes,
queue state). Everything `manage.py configuration_status` printed is now in the browser, from the
same function, so the two cannot disagree.

### Usage export
`/console/usage.csv` streams exactly the rows on screen under the same search and date window —
identifiers and money only. The export is itself audited, with the row count.

### Audit investigation
Date range; an **exact** action picker beside the free-text box (`action__icontains` silently
widens across a family: `payment.refund` also matches `payment.refund_failed`); organization and
department columns; pivots from an event to the actor, the action and the target; `details`
rendered as a readable list instead of a Python dict repr. Reading the audit trail is now itself
recorded — it was the one administrative read the product did not log. The dashboard's "recent
activity" panel no longer fills with its own page loads.

---

## 4 · Backup status: why it is published, not read

⚠️ **The obvious implementation is a false red that becomes a false green.**

`deploy/quillmd-fresh-admin.service` runs the admin surface as `quillmd-app` and carries
`InaccessiblePaths=… /opt/meddoc-pro/rebuild/.runtime`, so the entire runtime tree is masked out
of its mount namespace. Independently, the state directories are mode `0700` owned by the
operations identity (`claude`), which shares no group with `quillmd-app`; and `/var/lib/quillmd`
is `root:quillmd-app` mode `710`, which the operations identity cannot traverse either. The two
identities are disjoint **by design**.

A view that reads `.runtime/backup-alerts/status.json` therefore returns "unavailable" on a host
whose backups are perfectly healthy. It would also pass every test, because tests run as the
identity that *can* read it. A panel that is wrong when things are fine is one somebody stops
reading — which is how the false red becomes a false green on the night it matters.

**So the privileged side publishes and the console reads.** `manage.py
publish_operations_status` runs as the identity that owns the state, calls the existing
`ops.backup_alerts.status()` aggregator, and writes its already-redacted report into a
`ServiceHealth` row. The payload is an **allowlist** — an unrecognised key is dropped, not copied
blind — and the command refuses any report that does not assert `clinical_content_included=False`.

The reader distinguishes three states and never collapses them:

| state | shown as |
|---|---|
| never published | **"Never published"**, warning, with the command to install — explicitly *not* a report of health |
| published, fresh | the aggregator's own condition and severity |
| published, older than twice its cadence | **STALE**, downgraded to warning **even when the stored severity says healthy** |

All four (including a `computed_at` in the future) are covered by tests.

⚠️ **NOT VERIFIED, and it is an operator step:** installing the publisher on the production host —
a systemd unit running as the operations identity on the existing alerts cadence. Until that
happens the panel will honestly read "Never published" in production. The publisher's own path is
proven in tests with a stubbed aggregator; **the real aggregator was deliberately not run**,
because `ops/backup_alerts.py` reads `.runtime/backup-secrets/` and references `rebuild/.env`.

---

## 5 · Verification

### Environment — fully isolated, nothing of production touched
- Worktree `/opt/meddoc-pro/.worktrees/admin-console`, branch `feat/admin-console-operability`.
  The shared tree stayed on `main` and clean; no peer worktree was written to.
- Dedicated PostgreSQL 16 container `quillmd-admin-console-db` on `127.0.0.1:55441`, database
  `quillmd_admin_ci`, synthetic credentials, `--log-driver=none`. The live database
  (`quillmd_fresh`, :55438) and the shared CI database (:55439) were never written.
- Isolated gunicorn on **:9160** (doctor) and **:9161** (admin), plus a worker. Production's
  :9130/:9131 stayed up and untouched throughout — confirmed by their `/health/` payloads
  reporting release `e66d84ab…` while the isolated pair report `development-unrecorded`.
- **Administrator MFA preserved.** Every screenshot and browser check signed in with a real TOTP
  code against `seed_private`'s confirmed authenticator; no MFA requirement was relaxed anywhere.
- `rebuild/.env` was never read, by any route.

### Synthetic data — built through the real billing code, and it passes the product's own audit
`manage.py seed_admin_demo` creates ten operational states — a settled charge, a charge capped at
the approved limit with the difference absorbed, an absorbed platform failure, a job held for
reconciliation with funds reserved, a job running past the staleness bound, a released failure, an
invoice reconciliation, a $25.00 top-up and a $5.00 refund through the signed-event path, a refund
the ledger could not take, plus an unverified account, a suspended account, an organization-paying
department and an open invitation.

⚠️ **Nothing is hand-written.** Every row goes through `reserve` / `settle` / `release` /
`absorb_failed_job` / `reconcile_usage` / `record_stripe_event` / `process_stripe_event`, and the
provider cost is computed by **the auditor's own function** rather than typed. Typing plausible
figures by hand was tried first and produced three rows of
`recomputed_defined_cost_matches: false` — a fixture that cannot pass the product's own audit is
not demonstrating the product. On the final data:

```
manage.py audit_billing   ->  "all_checks_pass": true,  "durable_receipt_gaps": 0
wallet reconciliation     ->  11 wallets, 0 MISMATCH
```

### Arithmetic checked by hand on the charge-evidence page
`(4210 × $3 + 866 × $15) ÷ 1e6 = $0.02562` → `× 1.5 = $0.03843` charged (under the $0.60 hold) →
invoice evidence `$0.18` → new uncapped `$0.27`, under the limit, so delta `+$0.23157` applied →
ledger: promotional `−$0.03843`, paid `−$0.23157` → **net charge $0.27**. Both wallets read
"Ledger agrees".

### Two write workflows walked against the live isolated stack

Not through the test database — through the running server on `:9161`, against the seeded
synthetic data, so the effect is observed rather than asserted.

**A role change is honoured by the server, not merely displayed.** The check is
`core.security.membership`, the function the product itself uses to decide access:

```
before: xray_employee@… is employee in X-ray
server: may act as owner/clinician -> NO
POST /console/memberships/<pk>/  302  -> role now clinician
server: may act as owner/clinician -> YES      (the change is real, not cosmetic)
audit : admin@… {'account': 'xray_employee@…', 'role_from': 'employee', 'role_to': 'clinician',
                 'active_from': True, 'active_to': True}
```

**A payer change is not retrospective, which is what the screen promises.**

```
before: organization_pays=False, 4 jobs carry a recorded payer
POST /console/departments/<pk>/payer/  302  -> organization_pays=True
org paid wallet created                    : True
recorded payers unchanged on existing jobs : True
audit : admin@… {'organization_pays_from': False, 'organization_pays_to': True}
```

The second line is the one that matters: `Job.payer` is stamped when funds are first held and is
never re-read from the department, so an administrator explaining an old charge is not looking at
a number this setting could have moved underneath them.

### Tests
Both runs are `bash scripts/ci/verify-fresh.sh python`, the same gate CI runs, each against its
own isolated database.

| suite | pristine `main` (`e66d84ab`) | this branch |
|---|---|---|
| `core.tests` | 577, OK (8 skipped) | **646, OK (8 skipped)** |
| `documents.*` | 56, OK | **56, OK** |
| `ops` | 732, OK | **732, OK** |
| **total** | **1365, EXIT=0** | **1434, EXIT=0** |

**+69 tests, zero regressions.** Sixty-nine is the count in
`core/tests/test_admin_console.py` plus the strengthened assertion in `test_admin_evidence.py`.

The pristine baseline was taken in a **separate worktree at `main`** against its own database,
after an earlier baseline was found contaminated by concurrent edits.

⚠️ **One "failure" in the first baseline was my harness, not the repo**, and it is worth
recording: I had set `QUILLMD_ENV_MANAGED=1` to guarantee no `.env` could ever be read.
`documents/sdk_service.py` treats that variable as "managed deployment" and then requires
`QUILLMD_STATE_DIR == /var/lib/quillmd`, so one test failed for a reason that had nothing to do
with the code. The harness now matches CI exactly, and the worktree has no `.env` for
`load_dotenv` to find (verified by resolving the path settings.py would use).

### Browser
Nine pages driven in a real Chromium with TOTP sign-in, full page at 1440px, all **200** —
including the two that used to be wrong. Captured and indexed at
[`admin-console-screenshots-20260921/`](admin-console-screenshots-20260921/), with a caption per
image saying what it demonstrates.

The date window was then exercised through the rendered page rather than through the function:

| request | scope the page states | charged — paid | banner |
|---|---|---|---|
| no window | every record (no date window) | `$0.23157` | — |
| `from=2026-09-21&to=2026-09-21` | 2026-09-21 to 2026-09-21 (UTC, both days included) | `$0.23157` | — |
| `from=2020-01-01&to=2020-01-02` | 2020-01-01 to 2020-01-02 | **`$0.00`** | — |
| `from=banana&to=2026-09-21` | every record (no date window) | `$0.23157` | shown |
| `from=2026-09-2199` | every record (no date window) | `$0.23157` | shown |

Rows 3 and 4 are the pair that matters: a valid window really does narrow, and an unreadable one
really does not — so neither reading is vacuous.

The walk itself is committed as `rebuild/admin-console-browser.mjs` so the evidence is
reproducible rather than described: **14 of 14** checks, including a cross-page assertion that no
console screen renders `History:`, `Findings:` or a patient display name. It is deliberately NOT
wired into CI — it needs a running server, a seeded database and Playwright, and the CI job that
has all three runs the clinician walk; the running instructions are in its header.

⚠️ **It caught one of my own wrong expectations on the first run**: I asserted the admin surface
lands on `/`, and it lands on `/console/`, because `redirect('admin_dashboard')` resolves by NAME
and that name is registered on `console/` first.

⚠️ **One route shipped as a 500 during authoring and only a request caught it**: `audit()` takes
`action` positionally, and passing a detail named `action` raised `TypeError` on the audit page.
The suite now requests every console route as an MFA administrator for exactly this class.

---

## 5a · The adversarial pass over the finished diff — 18 defects in my own work

`AGENTS.md` makes a refutation pass mandatory on the clinical generation path. This change does
not touch that path, but it is **money code**, so the same discipline was applied: five distinct
lenses (money correctness; access and exposure; false-green/false-red; migration, concurrency and
load; silent regression), each told to break the diff rather than review it, each finding then
handed to an **independent verifier** required to reproduce it before confirming.

| | count |
|---|---|
| defects claimed | 18 |
| **independently confirmed** | **18** |
| thrown out | 0 |

**All eighteen are fixed in this branch, each with a regression test** (except `L4`, a lock-mode
change with no meaningful assertion). Two were caught by me first, by checking an assumption
rather than by any test. The verifiers also corrected two diagnoses and downgraded three
severities — the pass improved the findings as well as the code.

### The ones worth reading

| id | what it was |
|---|---|
| **`FieldError` 500** | `/console/?from=…` raised on every dated request: `User` extends `AbstractUser`, so its date column is `date_joined`, not `created_at` — **and the code carried a comment asserting all these models inherit `Entity`.** Found by checking the claim, not by a test. Now one date column per source, with a regression test. |
| **`FG-1`** | A window in which **every** recorded send failed rendered as amber *"No delivery recorded in this window"* — directly above a detail line reading *"failed 5"*. An absent measurement and a uniformly failing one are opposite findings; they were sharing a sentence. |
| **`M2`/`F1`** | One unreadable date bound narrowed every figure on the page **and** displayed *"these figures cover every record"* beneath the heading naming the window it had just applied. Now an unreadable bound drops the whole window, as the inverted-range arm already did. |
| **`REG-1`** | My own scraper fix broke the operator's sandbox verification. I had made `micro()` refuse anything finer than a micro-dollar — and an ordinary generation produces `$9.9615655`, so the whole money verification aborted at baseline for any account that had ever generated a document. The script now parses the full 12-decimal stored precision. |
| **`M1`** | The platform-cost totals are deliberately unwindowed, but the table beneath them is windowed — so filtering to a quiet day put **$156.498 of total immediately above "No platform costs match these filters"**, with no scope statement on that section. Introduced by this branch. The disclosure now sits where the numbers are, and two tests pin the scope in both directions. |
| **`M3`** | A usage row whose whole charge had been reversed exported as `charged_cost 0.1845` with every reconciliation column blank — indistinguishable from a charge that stands. **An accountant reading the file alone would have billed it.** An `absorbed_reversal` column now makes the file reconcile to the screen. |
| **`FR-2`** | The Processing panel asserted *"nothing is running. Nothing is picking work up."* while the strip beside it read **Running = 1** — a healthy worker part-way through a long transcription. |
| **`F2`** | The last-active-owner guard counted an **unverified** account as an owner. `core.security.membership` requires a verified account, so the guard could leave a department whose only owner cannot exercise the role. |
| **`L1`** | `/console/organizations/` issued `3 + 2·organizations + 2·departments` queries — measured at **1213 queries, 2.5 s and 876 KB of HTML** for 102 organizations. Four grouped queries and a page of twenty now; a test pins the query count against a growing tree. |
| **`TEST-3`, `TEST-4`** | **Two of my own new tests were vacuous.** The dated-request test asserted status 200, that the window was active, and that each context key existed — a mutation making the narrowing a no-op for ten of the eleven lists left all three passing. And `funds_held_on_open_jobs` could not observe the `state='held'` predicate it was named after. Both now count rows against positive and negative controls. Fixing the first exposed that five of the eleven lists had **no rows at all** in the fixture, so those assertions had been passing on empty lists. |

### One claim this branch made that was false, and is now stated correctly

The console **cannot** guarantee a department always has an owner. The membership screen refuses
the edit, but **suspending the owner's account from the account page reaches the same state** —
and that is deliberately still permitted, because a security suspension must never be blocked by
organization structure. What was wrong was the claim. The suspension now says plainly what it
did (*"X now has no active, verified owner…"*), the organizations page already flags the state,
and the invariant is described as being about that screen rather than about the product.

---

## 6 · Confirmed gaps deliberately NOT closed here

Named so the next reader does not have to rediscover them. Each is confirmed-real; none is
blocking the stated outcome.

| gap | why not now |
|---|---|
| grant or adjust a credit from the console | **Money → owner.** `LedgerEntry` is immutable by design, so this can only mean appending a compensating entry, and who may mint credit is a policy decision. |
| issue a refund from the console | **Refuted and correctly so** — the application credential cannot create a Stripe refund. See §1. |
| retry or requeue a failed job | A mutation on the clinical generation path; it needs the adversarial pass that path requires and a decision about re-charging. |
| resend a verification link; clear a sign-in lockout | Real and useful; `LoginAttempt` keys are hashed, so lockouts need a lookup path designing rather than a template change. |
| suspend another administrator | Deliberately still refused, now with the reason on screen. Locking out the only other administrator has no route back through the product. |
| rename, move or retire an organization or department | Only creation exists today; retirement needs a decision about what happens to its patients and templates. |
| per-dimension filters (user / department / provider / simulated / missing-receipt) | One `q` box still ORs across twelve lists. The date window was the axis that mattered most; the rest is friction. |
| the unpaginated wallet loop on the dashboard | A 3N+1 over every wallet on every load. Correct, and it will not scale; it is a performance item, not an accuracy one. |
| `/health/` returns `ok` unconditionally | It is a liveness probe that reads as a system verdict. Changing its contract touches anything that monitors it. |
| `auth.login_failed` records no subject | Deliberate today. Recording attempted identifiers is a privacy decision, not an oversight to fix silently. |
| exact money on `encounter_input.html` / `voice_limit.html` | Those two clinician surfaces still print a raw `Decimal`. They are on the clinical recording path, a parallel workstream is editing them, and one string is asserted by a CI browser test — so converting them here would widen this diff into somebody else's file for a cosmetic gain. Named rather than done. |
| `L4` lock-mode change has no test | `select_for_update(of=('self',))` narrows an exclusive lock from the joined rows to the row being written. Correct, and I could not write an assertion that would fail meaningfully without a contrived deadlock harness. |
| the spent-funds refund case | Now visible in words ("No money has moved") but still has no console control; only the checkout-replay loop can discharge it. |

---

## 7 · For the owner

1. **What counts as revenue when promotional credit funds the work?** The console shows the two
   charged figures separately and computes no aggregate over them. Deciding this is what turns
   the overview into a margin figure.
2. **Should an administrator be able to change `organization_pays`?** It is implemented, audited,
   non-retrospective and reversible — but it decides who is billed, and restricting it is a
   reasonable call.
3. **Installing the status publisher** is an operator step on the production host (§4). Until it
   runs, the backup panel will read "Never published", which is true.

---

## 8 · Integration order

**This PR is a draft and must not merge or deploy until the typed/voice milestone associated with
PR #1250 is complete**, then be integrated sequentially.

### Overlapping changes, identified before integration

`main` moved under a parallel workstream while this was built. Files touched by both in the last
24 hours:

| file | this PR | the parallel work | conflict risk |
|---|---|---|---|
| `rebuild/core/views.py` | 3 localised edits — `admin_dashboard` context, `audit_view`, nothing else | 5 commits in 24h | **real**; kept deliberately small, with all new logic in new modules |
| `rebuild/templates/admin_dashboard.html` | extensive | 3 commits in 24h | **real** |
| `rebuild/templates/financial_detail.html`, `billing.html` | money filter only | 2 commits each | low |
| `rebuild/core/context.py`, `models.py`, `static/app.css`, `templates/base.html`, `audit.html`, `integrations.html`, `quillmd/urls.py` | additive | — | low |
| everything else here | **new files** | — | none |

`rebuild/core/generation.py`, `core/jobs.py`, `core/billing.py` and the typed/voice tests are
**untouched by this PR** — the clinical generation path is not modified at all, which is why the
mandatory adversarial pass over that path is not triggered by this change.

**Before merging:** rebase onto the then-current `main`, re-run the full gate, and re-take the
browser walk. `rebuild/core/migrations/0018_servicehealth.py` is additive and creates one new
table; if another migration lands first, renumber it.
