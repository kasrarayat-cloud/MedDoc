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

### 2026-08-14T20:09:13Z — ✅ RETIRED: "RC-2 IS ON `main` AND NOT DEPLOYED"

**Retired 2026-08-20 by owner order. A FALSE PRESENT-TENSE FACT delivered to
every session for five days.**

It told the next session to read it before running `deploy-prod.sh`. Its
migration finished **2026-08-15T01:36:44Z** and its own predicted consequence has
happened — `template_twin_compiled_versions` holds the row F5-d has been working
on all week.

⚠️ **THE WORSE SHAPE OF THE STALE-ENTRY CLASS.** An expired *condition* wastes a
session's time; a false *present-tense fact* is read as a description of the
running system. The `DEPLOYMENT_RUNBOOK §5.6` shape, which this repository has
already paid six hours for.

Second live instance behind the retirement-sweep item — and the reason a false
fact outranks the sweep's schedule.


### 2026-08-15T04:18:34Z — HANDOFF: the fidelity arc is at RELAY's head, and the loop is the ONLY deploy actor

> ⚠️ **SUPERSEDED ON ITS DEPLOY CLAUSE, 2026-08-25 (ruling #150).** The owner's
> 2026-08-22 STANDING AUTHORITY gives clinical-surface deploys to SUPERVISED
> sessions. **Who may ship is stated in `AGENTS.md` § STANDING AUTHORITY and
> nowhere else.** The entry below is left intact as the record of what was true
> on 2026-08-15 — it is not an instruction to follow today.

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

### 2026-08-18T07:00:00Z — AUTO-CERTIFICATION IS IN FLIGHT; the West Medical walk is SUPERSEDED

**The decision is the owner's AUTO-CERTIFICATION ruling — `#127`, recorded in
`RULINGS.md` as "AUTO-CERTIFICATION BY AI IS THE DEFAULT PATH, AND THE MODEL
NEVER ASSERTS LATERALITY" — built by a SUPERVISED session on branch
`feat/twin-auto-certification`.**

⚠️ **CITE BY NAME AND BRANCH, AND ONLY THEN BY NUMBER.** An earlier version of
this entry said "#125" and was WRONG within hours: the loop independently
numbered its own F12-splits ruling **#125** and merged first, so the pointer sent
readers to a different decision entirely. It had already happened once before
that with **#124**.

**Two actors drafting from the same snapshot pick the same next number, and
neither can see the other's choice until a merge.** A number is not a stable
address until the row lands; the branch name is. The number above is safe to
quote *because* the row has landed and was re-read from `RULINGS.md` on
2026-08-19 — not because it was remembered.

⚠️ **AND THE LEDGERS STILL DISAGREE ABOUT THIS EXACT NUMBER.** `RULINGS.md` has
**#125 = F12 SPLITS** and **#127 = auto-certification**; `RELAY.md`'s F12 section
says *"ruling #127 (PROVISIONAL) split them"*. One of those is stale. Treat
`RULINGS.md` as the index — it is the one-line-per-decision register the
programme keeps for exactly this purpose — and do not propagate a number read
out of a prose section.

⚠️ **DO NOT CITE "certify the West Medical template" AS A BLOCKER, and do not
build toward it.** The owner will certify nothing — the machine will. On upload,
when a twin compiles with zero blocking elements, the model's own proposals are
confirmed, a round-trip proof runs in the worker, and the template certifies
itself. The twice-owed OWNER PING is retired by that work, not by the doctor.

**Coordinate any twin-adjacent work against that branch.** It already touches
`auto-certify-eligibility.ts`, `auto-certify.ts`, `worker.ts`, `queue.ts`,
`note-template-lifecycle.ts`, `settings/page.tsx` and
`native-template-manager.tsx`, and it consumes F16's `mappings-readiness.ts`
rather than restating its predicate.

✅ **THE THIRD ACTOR SESSION 03 DETECTED IS THIS BUILD — correctly spotted, and
the observation was right to make.** `feat/twin-auto-certification` in a `/tmp`
scratchpad worktree, semantically adjacent to F16, with real file-level overlap.
It syncs from `main` before each stage precisely so the overlap resolves in the
branch rather than at merge.

**This entry retires when that branch merges.**

### 2026-08-20T01:45:00Z — ✅ RETIRED: the `ledger-progress.sh` hardening — LANDED, AND NOT AS FILED

**The residual was real. My proposed fix was the WRONG ONE, and the loop said so
in its own gate.**

I filed: compare the hash against the empty-stdin digest `e3b0c442…855` and
return CANNOT-TELL. The loop **declined it, with a reason that is better than
mine**, recorded at
`gate-f20-ledger-progress-universe.test.ts:522` — *"it cannot tell 'we hashed
nothing' from 'the file is genuinely zero bytes', and the existence check exists
precisely so those stay distinguishable. `pipefail` is also strictly stronger:
it catches a truncated read that emitted bytes before failing, which yields a
WRONG hash that no constant comparison could ever see."*

It shipped `$(set -o pipefail; git show … | sha256sum …)` — inside the
substitution, so a sourced library neither mutates its caller's shell options
nor depends on them.

⚠️ **AND I RE-BROKE IT BY "LANDING" MY VERSION ON TOP.** I grepped for
`PIPESTATUS|hash-of-empty|e3b0c442`, saw nothing, and concluded the fix was
outstanding. The shipped fix uses `set -o pipefail` — **a form my token list did
not contain**. CI caught it immediately: `a LEGITIMATELY EMPTY ledger still
MEASURES` went red, which is exactly the arm written to catch my proposal.

> **A sweep is defeated by an incomplete TOKEN LIST at least as often as by a
> missing form** — AGENTS.md's own rule, and I searched for the shape of the fix
> I had imagined rather than the shape of a fix.

**Reverted; `ledger-progress.sh` is byte-identical to `main`.**


### 2026-08-20T15:30:00Z — F5-d: TWO `GSV at the SFJ` CELLS BLOCK CERTIFICATION, AND THE CACHE IS NOW HONEST

**The owner's template is one gate from certifying. This is the gate.**

Third live observation, and each refusal has been more specific than the last:

| run | refusal |
|---|---|
| 2026-08-18 | `fillCoverage=false (7 filled, need >= 10)` |
| 2026-08-20 07:00 | `fillCoverage=false (5 filled)` — **a STALE PINNED NOTE**; fixed by `8f46098a` + a declared pin-clear |
| **2026-08-20 15:25** | **passes fill coverage**; blocked by **2 field checks** |

    [template-twin:synthetic] BLOCKED compiled=617d6de9…:
      ttf_e119ecd84bdd6b6c0b802967:ASSERTION_NOT_SUPPORTED,
      ttf_12e093b32f6ad5da739ada7d:ASSERTION_NOT_SUPPORTED

    TEMPLATE_TWIN_CERTIFY_FAILED {"auto": true, "stage": "synthetic_test",
      "reason": "The synthetic encounter left 2 blocking field checks. Add direct
                 synthetic evidence or correct the mapping, then test again."}

**Both blockers are the SAME LABEL, once per leg** — measured, not inferred:

| fieldId | label | criticality | concept | sourceType |
|---|---|---|---|---|
| `ttf_e119ecd84bdd…` | `GSV at the SFJ` | routine | `measurement.diameter` | extraction |
| `ttf_12e093b32f6a…` | `GSV at the SFJ` | routine | `measurement.diameter` | extraction |

Blank-cell tally for the run: **44 blank — 32 `no_supporting_fact`, 12
`laterality_mismatch`.**

⚠️ **THE ENCOUNTER DOES DICTATE THIS SEGMENT.** `deriveVerificationEncounter`
emits `Right GSV at the SFJ: diameter … millimeters, reflux time … seconds` and
the Left equivalent. So the assertion is unsupported for a reason **downstream
of the text**, not because the segment was never said.

**PRIME SUSPECT, STATED AS A SUSPECT AND NOT A DIAGNOSIS:**
`segmentCongruent` (`bridge-evidence.ts:131-142`) is token-overlap —
`want.some(t => hay.includes(t))` — and `'aagsv'` CONTAINS `'gsv'`. The
refutation pass already demonstrated this filling an **AAGSV** cell from a
plain-GSV fact. The same looseness plausibly makes a `GSV at the SFJ` cell's
candidate set ambiguous in the other direction. **This has NOT been reproduced.
Reproduce it before believing it** — this programme has twice had a confidently
stated mechanism refuted, and the reproduction that settles it is one script.

**DO NOT** loosen the validator or the fill threshold to get past this. A
certificate over a cell nobody proved is what these gates exist to refuse.

**The state is intact and the doctor owes nothing:** `NEEDS_CONFIRMATION`,
**80 mappings CERTIFIED / 0 pending**, 0 fill manifests.

**This entry retires when the owner's template certifies, or when the two
assertions are shown to be correctly refused — in which case the encounter or
the mapping is what changes, never the gate.**

### ⚠️ F5-d IS THE HEAD ITEM, AND ITS ACCEPTANCE SHAPE IS RULED — NOT NEGOTIABLE

**(a) REPRODUCE BEFORE YOU FIX.** One script, running the REAL matcher on the
REAL derived encounter against THE TWO BLOCKED FIELDS. Name the mechanism at
FILE:LINE **before a line of fix is written**. The token-overlap suspect
(`segmentCongruent`, `bridge-evidence.ts:131-142`) is CONFIRMED OR REFUTED with
the same rigor that killed the last two confident mechanisms in this programme —
both of which were plausible, both read out of the code, and both wrong.

> *Read to form a hypothesis; RUN something to name a mechanism.*

**(b) FIX AT THE ROOT, RED-PROVEN AGAINST TONIGHT'S EXACT REFUSAL** — both
fields, both legs, `ASSERTION_NOT_SUPPORTED`. Then **re-measure the blank
census**. Tonight's is **44 blank: 32 `no_supporting_fact`, 12
`laterality_mismatch`**. If the fix moves those numbers, **say WHICH and WHY**.
A number that moves without an explanation is the finding, and a number that
moves in the right direction for the wrong reason is worse.

**(c) THEN the backfill re-run → OBSERVE → CERTIFIED → verify the DB → the ping;
or the FOURTH verbatim refusal with the mappings intact.** The no-ping-until-
observed rule stands. Three honest refusals in, the fourth candidate inherits
everything the first three proved: the arms have teeth, the cache is honest, and
the encounter reaches the model.

⚠️ **DO NOT loosen the validator, the fill threshold, or the congruence test to
get past this.** A certificate over a cell nobody proved is precisely what these
gates exist to refuse.

---

### 2026-08-20T16:40:00Z — RETIREMENT CONDITIONS BECOME MECHANICAL (queued BEHIND F5-d)

**Small. Behind F5-d, not in front of it.**

A sweep — nightly, or at PICKUP — greps `INBOX.md` and `RELAY.md` for
**"retires when"** clauses and TESTS each one where it names a checkable fact:
a PR merged, a file present, a symbol in a script, a flag flipped. Expired
entries surface as a **named list** instead of sitting at the top of the queue
for the next session to read past.

⚠️ **TONIGHT IS THE REFERENCE CASE, AND THE COST IS MEASURED.** The citation-gate
entry ended *"This entry retires when the gate lands."* The gate landed in #756;
the entry stayed. **Session 04 was handed it as its 🔴 TOP PRIORITY**, spent its
run establishing that the work was already done, landed nothing, and honestly
marked `STOP-CONDITION`. The loop then sat dark. The clause was written
correctly, came due, and **nobody executed it** — by the author, who was awake
and working on adjacent things.

> **A retirement condition nobody executes is the EXEMPTION-DECAY class one file
> over.** `AGENTS.md` already records that an exemption's reason is prose and
> prose decays silently, and that the cure is to write the retiring condition as
> a testable event. This is the other half: **a testable event that nothing
> tests is still just prose.**

**Shape:** report-only first — print the list, change nothing. A sweep that
auto-deletes entries on a heuristic would eventually delete a live one, and the
failure mode of a wrong deletion is worse than a stale entry. Positive-control
it: an entry whose condition is demonstrably NOT met must not appear in the
expired list.

**This entry retires when the sweep prints its first list.**

### 2026-08-20T23:10:00Z — 🔴 F5-e: THE REFLUX COLUMN IS STRUCTURALLY UNADDRESSABLE

**CONFIRMED end to end, with a positive control. Not a suspicion.**

`bridge-fill`'s `place()` addresses the reflux cell with `irRow.vein` — the
row's vessel label — for BOTH columns. `segmentCongruent` then needs an anatomy
token in the fact's concept, value or evidence quote. **A reflux fact has none.**

| fact concept | n | quotes carrying an anatomy token |
|---|---|---|
| `measurement.diameter` | 20 | **20** |
| `measurement.reflux_time` | 20 | **0** |

Real quotes: `Right GSV at the SFJ: diameter 3.10 millimeters` versus
`reflux time 0.110 seconds`.

Through the real `matchMeasurementFact`:

    diameter  3.1   -> FILLED   cites "Right GSV at the SFJ: diameter 3.10 millimeters"
    reflux    0.11  -> REFUSED  no_supporting_fact
    CONTROL   the same reflux fact WITH anatomy in its quote -> FILLED

⚠️ **A REQUIRED GATE ARM ASSERTED THE OPPOSITE AND PASSED** — it fed both facts
the whole dictated sentence, a quote production never produces. Corrected in the
same change that files this, and mutation-proved: restoring the old quote
reddens it.

**TWO FIX DIRECTIONS. Loop's choice; the adversarial pass is MANDATORY either
way (clinical generation path).**

**(A) GENERATOR PHRASING** — emit a self-contained reflux sentence carrying the
vessel. Cheap. **Fixes only the synthetic proof**; a real dictation has no such
guarantee.

**(B) ADDRESSING / L3 CONTEXT AT THE ROOT** — `place()` supplies the row's
anatomy as addressing context, or L3 attaches the segment to every measurement
fact it splits. Invasive. **The one that helps a real visit.**

⚠️ **(A) WITHOUT (B) MAKES THE PROOF PASS AND LEAVES THE PRODUCT BROKEN** — a
certificate attesting a fill path a real encounter cannot exercise. If (A) is
taken alone, say so in the ledger and keep F5-e OPEN for (B).

**Retires when a reflux cell fills from a fact whose quote does not name the
vessel — or when (B) lands and the arm above is deliberately inverted.**

### 2026-08-20T23:00:00Z — 📌 CLAIM A RULED FIX DIRECTION BEFORE BUILDING IT

**Cheap rule. Tonight is the reference case.**

Ruling **#135** named a fix direction (shared canonical derivation, one rule
both callers). **Two actors independently built it** — the loop as F5-d(b)
(#763) and a supervised session (#764) — in the same window, neither knowing
the other had started.

**Measured cost: one full adversarial pass and one closed PR.** Nothing was
lost and nothing shipped twice; the loop's version was better and won on the
merits. But the second pass bought a verdict on code that never merged.

> **When a PROVISIONAL ruling names a fix direction, the actor picking it up
> posts the claim to `INBOX.md` (or the RELAY row) BEFORE building — one line,
> the ruling number and who is on it. The second actor then EXTENDS instead of
> duplicating.**

⚠️ **AND THE COLLISION WAS NOT WASTED, WHICH IS THE PART TO READ CORRECTLY.**
Two independent implementations reached the SAME core predicate —
`derived === null`, never a type test, never `String()` — which is real evidence
the predicate is right, of a kind one implementation cannot produce. The
diff also surfaced what each had missed: the loop's version carried the
`rowPrototype` axis the supervised one did not, and the supervised one carried a
FALSE GREEN correction, F5-e, and a stale-entry retirement the loop's did not.

**So the rule is CLAIM FIRST, not "never converge".** A convergent fix is a
chance to diff two solutions — the existing canon already says so. What this
entry adds is that the diff is worth more when it is *chosen* than when it is
*discovered at merge time*, and the choosing costs one line.

**This entry retires when a claim line appears on a ruled fix direction and the
second actor extends it.**

### 2026-08-21T09:00:00Z — 🔴 F5-i: MULTI-SHAPE CERTIFICATION PROOF (behind F5-f's ship)

**OWNER QUESTION: "is the fix for ALL categories/templates, not just mine?"**

**The structural answer is YES** — one engine, no per-template code paths: every
template goes through the same compiler → mappings → auto-certify → fill →
export. Nothing branches on a template id or a specialty.

⚠️ **BUT ONE OBSERVATION IS NOT A CATEGORY PROOF.** Everything demonstrated
end-to-end so far ran on ONE shape: a tabular measurement form (the 80-field
venous duplex). The paths a table exercises — `bridgeNumericTableCells`, row
addressing, `segmentCongruent`, measurement-cell fill coverage — are precisely
the paths a table-less form never touches. The engine is least proven exactly
where it has never been run.

**1. THE QA WALK GAINS A SECOND SHAPE.** A committed BLANK operative-note
fixture — numbered lists, free-text sections, header fields, **zero measurement
tables** — through the same arms where applicable: upload → compile →
auto-certify → visit → fill → export.

⚠️ Note the fixture question is itself open: the repo carries
`colon_blank_answers.pdf` (a blank PDF form) and `WM IOV Template.docx` (the
tabular one). A blank operative-note **.docx** may need to be added under the
sanctioned fixture path — and it must be BLANK, per the tracked-fixture rule. A
filled document is never a fixture.

**2. THE HONEST LIMIT GETS ITS FIX DIRECTION: SHAPE-DERIVED OR REFUSE.**
`deriveVerificationEncounter` currently FALLS BACK to a venous dictation for a
form whose labels it cannot speak to. Ruled: a template the generator cannot
address lands in **needs-review** naming that — *"we could not generate a
matching self-test"* — and never certifies against an unrelated specialty's
dictation.

> **A certificate must mean THE form was exercised, not that A form was.**

The current fallback is the weaker claim wearing the stronger one's clothes: it
produces a green certificate whose proof never touched the template it certifies.

**3. THE CENSUS — measured 2026-08-21, so the next specialty arrives onto a map.**

| shape | status |
|---|---|
| **tabular measurement** (venous duplex, 80 fields) | ✅ PROVEN end-to-end in production — certified, filled, exported, owner-verified |
| **operative note** (Colonoscopy Operative Note, Operative Note ×3) | ⚠️ **UNPROVEN** — 4 templates exist in production, **0 compiled twins** |
| **SOAP office** (System Default — SOAP, Primary Care Chronic Disease Follow-up) | ⚠️ **UNPROVEN** — 0 compiled twins |
| **imaging report** (Ultrasound Imaging Report) | ⚠️ **UNPROVEN** — 0 compiled twins |

**Production holds 10 note templates and exactly ONE compiled twin.** The
generality claim currently rests on that one. That is the honest state, and it
is why this item exists rather than a reassurance.

**This entry retires when a second SHAPE certifies end-to-end and the census
above is re-measured.**

### 2026-08-21T12:20:00Z — POINTER: ruling #137 landed, F23 is loop-eligible

**This is a POINTER, not a ruling.** The decision lives in `RULINGS.md` #137
and the work item in `RELAY.md` **F23**. Nothing here decides anything.

Two things a session starting tonight needs to know:

1. **`docker image prune -af` is FORBIDDEN.** Preflight's Check 2 no longer
   prescribes it. `prune -a` deletes unused **TAGGED** images and this host
   holds **146 rollback tags** — the documented rollback path for every past
   deploy. If any instruction you meet still says to run it, that instruction
   is stale; #137 supersedes it.
2. **`scripts/ops/prune-rollback-tags.sh` is already GRANTED** in
   `.claude/settings.json`, shipped with the ruling. ~~The script does not exist
   yet — F23 builds it.~~ Do not re-add the grant.

   > ⚠️ **CORRECTED 2026-08-26 BY THE SUPERVISED LEAD — the struck sentence had
   > been FALSE for five days and was printed into the head of EVERY session log
   > in that window.** F23 landed **2026-08-21**; the script exists
   > (`scripts/ops/prune-rollback-tags.sh`). The grant half was always true —
   > `grep -c prune-rollback-tags .claude/settings.json` → 1 — so only the
   > existence claim was wrong, which is what made it survive: the row read
   > mostly-correct.
   >
   > **The original wording is kept, struck, not deleted** — this file is a
   > record as well as an instruction, and the correction is the point.
   >
   > **Why the loop could not fix this itself, and it is not laziness:** the loop
   > never writes `INBOX.md` by design (append-only from the supervised side), so
   > a false premise here is structurally beyond it. It is the same shape as the
   > grant rule the loop cannot obey — *an actor cannot be ordered to do what it
   > is structurally denied* — ratified this day. **The loop DETECTS
   > (`scripts/check-retirement-conditions.sh`, whose grant ships in this same
   > change); a supervised session CORRECTS.**

**Supervised-side state, so the loop does not collide with it:** F5-f + F5-h +
the residual are LIVE (`1e7245b0`, 15 of 15 judged, PR #777 merged). The
supervised lead is holding for the owner's live acceptance test on the Word/PDF
re-download; **its findings become F5-f's behavioural evidence and will be
routed to the ledger either way.** No shared-tree work is in flight from this
side.

### 2026-08-24T15:25:10Z — A UNION TO EXPECT ON `RELAY.md`, AND WHO OWNS IT

**Operational notice. Nothing here decides anything.** Filed by **session 05 of
run `20260824-073818-b1`**.

**PR #833 (`docs/f24-s5-walk-refused`) WILL CONFLICT ON `docs/foundation/RELAY.md`,
and the resolution is a UNION.**

Measured rather than predicted:

    git merge-base origin/main origin/docs/f24-s5-walk-refused
    -> be9bce63…            <- my FIRST merge (#831, F27)

So #833 forked **after** F27 landed and **before** `03eb0d92` (#832, F27's
citation + the QA-recreate row). Both branches **append to the end of
`RELAY.md`**, which is the shape that conflicts.

⚠️ **BOTH SIDES DESCRIBE THINGS THAT ACTUALLY HAPPENED** — #833 records an
acceptance walk that ran and refused; `03eb0d92` records a citation and a
measured QA recreate. **That is the tell for a UNION, never a choice.** Taking
either side alone silently deletes a landed item's ledger row, and nothing
fails when it does.

**Verify the union by `git diff --numstat` showing 0 REMOVED**, not by reading
the merged file — a section that survived and a section that was re-added look
identical, and only the removal count tells them apart.

#### ⚠️ NOTHING OF #833's WAS CANCELLED BY MY MERGES — CHECKED, NOT ASSUMED

`merge-pr.sh` takes both views on the PR's own base branch before merging, and
`main` read **4 completed / 0 in-flight** at both merges (`be9bce63`, then
`03eb0d92`). A merge to `main` does not touch a PR branch's own runs. **#833's
gates are its own and were not disturbed.**

#### WHY THIS IS FILED AT ALL

This is the *"landing into a live loop"* shape with the actors swapped, and the
cost lands on somebody else's branch. Canon's own words: **a cost that falls on
another actor and comes out fine is the kind nobody corrects.** #833's author
branched off the merged first PR, which was correct at the time; `03eb0d92`
simply landed afterwards.

⚠️ **THIS FILE CANNOT CONFLICT WITH #833** — that PR touches
`docs/foundation/RELAY.md` and nothing else, and this notice touches only
`INBOX.md`. Chosen deliberately so the coordination message does not become a
second instance of the problem it describes.
