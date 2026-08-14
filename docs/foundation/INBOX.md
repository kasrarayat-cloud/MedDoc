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

### 2026-08-14T20:09:13Z — RC-2 IS ON `main` AND NOT DEPLOYED. A `main` DEPLOY SHIPS COMPILE-ON-UPLOAD.

**Read this before running `scripts/deploy-prod.sh`.**

`main` (`e022ec0c`) now carries RC-2, which **changes production behaviour on a
path every doctor uses**: `saveNoteTemplateAction` compiles a Template Twin on
**every `.docx` upload** through Settings → My Note Format, and stores the
uploaded bytes before extraction.

**Production has NOT been deployed with it.** The last deploy was `133f55c1`
(item 3 + F3 + R4b), whose declaration
(`docs/foundation/deploys/20260814-133f55c1.md`) says nothing about any of this
— it could not, because RC-2 merged afterwards.

⚠️ **SO A DEPLOY OF `main` RIGHT NOW WOULD SHIP AN UNDECLARED RUNTIME CHANGE**,
which is the exact seam the R5 row in `RELAY.md` records: *"I deployed `main`"
is not the same claim as "I judged what I deployed"*. Write a NEW §2.5
declaration naming RC-2 before deploying, and note that it is
**migration-carrying**:

    20260814024500_rc2_note_template_source_artifact   (migrations 103 → 104)

**What the declaration must name, at minimum:**

- migrations **103 → 104**
- `note_templates` gains `sourceObjectKey` / `sourceSha256`, **NULL for every
  existing row** — absence means "we do not have the file", never "it is
  elsewhere". No backfill; do not invent one.
- **twin rows begin to appear in production for the first time.**
  `template_twin_source_artifacts` and `template_twin_compiled_versions` are
  currently EMPTY in prod and will stop being empty on the first `.docx` upload
  after the deploy. That is intended, and it will make prod's twin tables stop
  matching every prior report that says "zero compiled versions".
- **`MAPPINGS_NOT_READY` still refuses** — compiled ≠ certified. Nothing becomes
  certified by this, no fill runs, no export changes.
- object storage takes new writes under the template-artifact prefix.

**Not a bug, and deliberately not deployed by the session that built it:** the
queue said *"RC-2 to completion"*, and completion is merged-and-cited. Shipping a
parked capability's first live behaviour change is an owner call, not a tidy-up.

**Proof it works, if you need it before deciding:**
`scripts/qa/rc2-twin-door-on-qa.ts` — 17 of 17 on the QA stack, 80 fields, bound
to the doctor's own template, correctly uncertified.

⚠️ **AND THE QA STACK WAS REBUILT FROM THAT BRANCH TO RUN IT** — QA images are
now newer than production's and contain RC-2. `check-qa-mock-posture.sh` was
re-run afterwards and still reports vendor-severed.
