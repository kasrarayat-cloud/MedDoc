# INBOX — operational notices to the next session

**Printed into every session's log by `scripts/foundation-loop.sh` at launch,
before the session starts.** Delivery is mechanical: receipt cannot be skipped
and requires no read-discipline from anybody.

---

## ⛔ THE HARD CONSTRAINT — OPERATIONAL NOTICES ONLY

**This file carries operational notices and NOTHING else:**

- a union the next session will meet, declared in advance
- a hold, a hazard, a thing in flight
- coordination between a supervised session and the loop

⚠️ **A RULING NEVER GOES HERE. Rulings live in `RULINGS.md` and nowhere else.**

An inbox that can carry a ruling is a **second source of truth**, and the entire
ledger design exists to prevent exactly that. The failure is not that somebody
reads the wrong file — it is that two files can disagree, and a session that
finds a decision here has no way to know whether `RULINGS.md` contradicts it.
**If what you are about to write decides something, it is a ruling: put it in
`RULINGS.md`, and put its pointer here only if a session needs to act on it
tonight.**

## HOW IT WORKS

- **Append-only, from the supervised side.** The loop never writes here.
- **Every entry is timestamped** and starts with `### <UTC ISO8601> — <title>`.
  The printer counts those headings; **no headings means nothing is printed.**
- **Fail-open by design.** A missing inbox, an unreadable one, or one with no
  entries prints nothing and never blocks a launch. An inbox that could stop the
  programme would be a worse bug than the problem it solves.
- **Retired, never deleted.** Once a session's log shows an entry was delivered,
  move it to `docs/foundation/inbox-archive/`. Confirm delivery first:

      grep -l "<the entry's timestamp>" docs/foundation/logs/*.log

  ⚠️ **A session already running cannot be reached** — it is a fresh process and
  has already been launched. An entry added now reaches the NEXT launch.

---

<!-- entries below; newest last -->

### 2026-08-13T20:38:44Z — the ledger moved 175 → 176 / $1,750 → $1,760, and it is EXPLAINED

**Reconciliation should expect 176 rows and $1,760.00, not 175 / $1,750.00.**

A real signup took the wired signup door on production at `20:38:44Z` and was
granted its $10 promo automatically — practice `cmsrzdmp6000001leg3eb8rgi`, key
`grant:promo:practice:cmsrzdmp6000001leg3eb8rgi`.

⚠️ **IT IS A REAL PRACTICE CARRYING A REAL $10 PROMO LIABILITY — not synthetic,
not a fixture.** The account is the owner's own. B9 must reconcile it as real.

**Full record: `RELAY.md` § "THE 176th GRANT — A REAL SIGNUP THROUGH THE WIRED
DOOR".** The 175 / $1,750.00 figures elsewhere in `RELAY.md` and `RULINGS.md` are
NOT wrong — they were true when written, and every one of them predates this.
