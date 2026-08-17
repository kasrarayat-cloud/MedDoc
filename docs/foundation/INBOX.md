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

### 2026-08-15T04:18:34Z — HANDOFF: the fidelity arc is at RELAY's head, and the loop is the ONLY deploy actor

**Supervised sessions are CLOSED.** The owner has stopped relaying; this loop
carries the queue from here.

**READ `RELAY.md`'s head before anything else.** Five items (F1–F5) sit ahead of
the billing tail, each with its ruling and its done-when. They are fidelity
defects the owner found on a signed test visit — **on the path the pilot doctor
actually walks** — which is why they jump B8/B9.

**Three rulings were recorded tonight: #112, #113, #114.** Grep them before
deciding anything in this area. Two of them record things that are NOT true, so
nobody re-derives them:

- ⚠️ **The twin is NOT half-filling the PDF.** Production holds 0 compiled twin
  versions, 0 mappings, 0 fill manifests. RC-3's loud-fallback rule stands as a
  RULE and is worth extending to every export leg — it is simply not that bug's
  mechanism.
- ⚠️ **The signed view does NOT fall back to a different renderer.** It already
  renders the document surface. Both proposed mechanisms for the signed/pre-sign
  divergence were wrong; **F2 is a MEASUREMENT, not a theory.**

**IN FLIGHT WHEN THIS WAS WRITTEN:**

- `fix/docx-numbering-fidelity` — **PR open, F1's payload.** Cite, merge, deploy
  under a §2.5 declaration naming the document-visible change.
- **#663** (RC-2 deploy report) and **#664** (co-tenant status check) — open,
  waiting on a quiet `main`. F4.
- `feat/certification-door` — a worktree branch holding **two finished item-3
  commits**. Do not lose them; F4 rebases and lands them.

**PRODUCTION IS CURRENT.** RC-2 is live (migrations 104) and the `.dockerignore`
build fix is deployed. Twin tables are 0 by design — **the first non-zero will be
a doctor's upload, not a defect**, and it supersedes every earlier "zero compiled
versions" report by ACTION.

⚠️ **ONE HOUSEKEEPING ITEM THE LOOP CANNOT DO:** ~147 MB of scratch at
`…/scratchpad/rc2-build` + `rc2-src.tar` needs shredding and `shred` is denied to
the unattended layer. The paths are in the owner's hands. **Do not `rm` them** —
unlinking before shredding converts a recoverable failure into a permanent one.

### 2026-08-16T08:10:00Z — the 147 MB housekeeping clause is DISCHARGED, and F7 is re-priced

**The clause at the end of the 2026-08-15 handoff entry above is STALE. Do not
act on it.**

**Measured 2026-08-16: `scratchpad/rc2-build` and `rc2-src.tar` DO NOT EXIST.**
The owner cleared them. F7 was scoped partly around that figure and should not
be.

Remaining scratch, same pass: **35 files, 456 KB** of
`.b6-*/.b7-*/.f2-*/.f3-*` at the repo root, **all gitignored** — so
`git status --porcelain` reads **0** and they **do NOT block a relight**, which
is the launch guard's actual predicate. Clinical artifacts: **0**, against a
traversal control of **133** `.md` files in the same trees. **F7 is tidying, not
a blocker, and must not hold the queue.**

⚠️ **A notice that says work is pending when it is not makes the next session
re-derive it** — which is the exact failure an inbox exists to prevent. Retiring
a discharged clause is as much a part of the mechanism as adding a live one.

### 2026-08-16T19:30:00Z — POINTER: F10 now has OWNER ACCEPTANCE CRITERIA (ruling #121). Read them before designing the fix.

**This is a pointer, not the decision.** The decision is **ruling #121** in
`RULINGS.md`. Read it there.

**Why it is in front of you tonight:** F10 was filed hours ago and the criteria
were set afterwards. **A fix designed before them would be guessed at**, and
F10 is the kind of item where a plausible wrong shape passes its own test.

**The three, in one line each — the mechanism is YOURS to design:**

1. **The gate does not weaken** — no deploy without a declaration judged against
   the **exact tree shipped**. ⚠️ **This does NOT mean flipping
   `declaration_gate`'s `present` to `strict`** — `present` is deliberate under
   ruling #96(b), and flipping it would refuse every deploy whose declaration
   lands in the same PR. Read it as *"the judgement covers what actually
   shipped"*.
2. **The circularity breaks** — a declaration must be committable **before or
   with** its deploy without invalidating its own name. Candidates (none
   mandated): name by the CHANGE's sha with ancestry-verification at the gate;
   an explicit carry-forward marker the gate resolves; or another shape.
   ⚠️ **Prove it BOTH directions, including the wrong-tree-REFUSED arm** —
   `retire-branch.sh` passed 9 of 9 refusal tests and still printed a false
   green on the happy path.
3. **Falsifiability does not narrow** — a declaration that can name *"whatever
   ships"* is no declaration. A scheme that resolves to the deployed tree by
   construction cannot come out false.

**INTERIM, until F10 lands:** a §2.5 **carry-forward** may be written to the
shared tree — it can only be named after a post-merge sha — and **MUST be
committed by the same session before close-out.** The exception **retires with
F10**; do not let it outlive its reason.

✅ **F9 IS DONE AND THIS NOTICE DOES NOT REOPEN IT.** Merged and cited
(`5f2334b1`, #695). The manual tag-first habit is now the **fallback**, not the
mechanism.

### 2026-08-17T12:00:00Z — POINTER: F12 is at F6's HEAD — owner finding on E/M (ruling #123)

**Pointer, not the decision.** The decision is **ruling #123** in `RULINGS.md`;
the item is **F12** in `RELAY.md`, queued **ahead of F6**.

Two parts, both from the owner's own exported PDF, and they ship together:

1. **SKIN** — the E/M block renders in **legacy cream** in exported PDFs. Fix at
   the **component/builder root**, semantics byte-identical.
   ⚠️ **The mechanism is NOT named. Reproduce before editing.** Measured:
   `docx-generator.ts:188-197` has **no shading at all**, so the cream is *not*
   from the converged DOCX→Gotenberg path. Discriminate first.
2. **POLICY** — E/M **does not belong on procedure/operative notes.** Suppress
   **by note SHAPE**, in-app and in exports. Office visits unchanged.
   ⚠️ **`emAppliesToSpecialty` takes only a specialty id and CANNOT express
   this** — a GI doctor does both under one specialty. It is a **second axis**.

**Done when:** both directions attempt-proved (office visit SHOWS E/M;
colonoscopy op-note shows NONE, nowhere), §2.5 with **absence rows**, mandatory
adversarial pass.
