# FOUNDATION — the relay ledger

> **HOW THIS FILE IS ORGANISED — read this once.**
>
> **This is the LIVE HEAD. It is not the whole ledger.**
>
> On 2026-08-26 this file was **1,830,324 characters against a 150,000-character
> tool read limit** — **twelve times over** — and `MASTER.md` STEP 0 orders every
> session to READ it. About 8% fitted in one read.
>
> ⚠️ **And a ledger's truncation is the worse kind.** A rulebook cut at the top
> still hands back *some* live rules. This file is **append-only**, so its front
> is its **oldest** content: a plain read returned the stale beginning, omitted
> every current arc, and **said nothing about it**. A confident, well-formed,
> obsolete answer.
>
> | where | what | authority |
> |---|---|---|
> | **this head** | the LIVE QUEUE, open items, `## Rules`, `## Invariants`, the reused-id reconciliation, and the archive index | **governs** |
> | **`docs/foundation/relay/`** | every closed arc, **verbatim and dated** | **governs** |
> | the ARCHIVE INDEX below | one row per archive — title, frozen pre-split span, size | **pointer only** |
>
> **Nothing was rewritten.** Archives are verbatim slices; corrections are
> appended and dated and superseded wording is kept, because in this programme
> the correction is the point.
>
> **Citations still resolve.** Every pre-split `RELAY.md:NNNNN` — here, in
> `RULINGS.md`, or in any external file — resolves through the **frozen
> pre-split span** column of the index. Those numbers address a file that can
> never grow again, so they cannot go stale. **New** pointers use TITLES: a line
> number in an append-only file is stale before it lands.
>
> **Adding to the ledger:** append to this head as before. When it crosses its
> budget, `bash scripts/rotate-ledger.sh --apply` archives the closed arc using
> the same proven splitter, and the result lands as a normal item — PR, citation,
> ledger row. **Do not hand-split this file again.**
>
> The split's five proofs and their mutation proofs: `docs/foundation/relay/README.md`.

**This ledger is the contract between sessions.** `SPEC.md` says what to build;
`DISCOVERY.md` says what is true today; this says what order, with what proof.

---

> ⚠️ **RULINGS INDEX: `docs/foundation/RULINGS.md`** — every war-room decision as
> one line with a pointer to its full text. **Grep it before deciding anything
> ruling-shaped.** New rulings append there in the same commit that records them.

## ⏭️ THE LIVE QUEUE

**`MASTER.md:480` calls this "the authorization". Until 2026-08-26 it pointed at
a 296,784-character section whose every row was closed, inside a file only 8% of
which could be read.** This is that queue, rebuilt from what is actually open.

> **Standard ceremony per item:** citation by `bash scripts/gh-runs.sh` on the
> FULL 40-char sha · merge by `bash scripts/merge-pr.sh` · a §2.5 declaration for
> anything that changes runtime · and an **ADVERSARIAL PASS that is MANDATORY on
> any note-surface or export change** — told to REFUTE, given the claims not the
> intent, required to produce FILE:LINE + a concrete input → wrong output, and
> permitted to report NOTHING FOUND.
>
> ⚠️ **WHO MAY SHIP IS STATED IN EXACTLY ONE PLACE: `AGENTS.md` § STANDING
> AUTHORITY** (ruling #150). Not here. The loop builds, proves and merges;
> supervised sessions deploy clinical-surface changes.

**F5-i-2 LEADS THE QUEUE** — owner ruling **#156**, class (a)/(b), 2026-08-28.
It displaced F8, which **CLOSED 2026-08-27** on the judged deploy of `eec8685b`
(ruling #147's *"F24 CLOSES → F8 opens"* is therefore discharged, and F24 closed
2026-08-25 at 75 of 80). **Canon and process items ride along; they are not the
work.** The morning report's `### THROUGHPUT` line exists to keep that visible.

| Item | State | What it is | Blocked on / Done when |
|---|---|---|---|
| **F5-i-2** | 🟡 **ENGINE BUILT + GATED 2026-08-28 — ACCEPTANCE OWED, and the loop cannot run it** | **SHAPE-AWARE VERIFICATION ENCOUNTERS.** The certification engine learns to derive a self-test per template **SHAPE**, not only the venous/measurement shape. For consult/SOAP forms — the owner's among them — the synthetic encounter is derived from the **compiled field set** (histories, social fields, impressions, plan lines, HPI narratives), and the coverage floor is **SHAPE-APPROPRIATE**: the measurement-cell requirement applies only to shapes that HAVE measurement cells. A shape with no generator stays an **HONEST LOUD REFUSAL** — today's state, now visible. **It ABSORBS R4** (prose-template support). ⚠️ **THE GATE NEVER LOOSENS.** No certification without a round-trip self-test. The option *"certify measurement-less forms without proof"* is **REJECTED BY NAME** — that is the fake-certified state the gate exists to kill, and it is what F5-i removed when it deleted the fallback that proved a leg-vein study and called it the doctor's template. | **Done when the owner's R5 form certifies END-TO-END on QA** with **REALISTIC per-field concept mappings — never a blanket substitution** (the walk's own lesson: [canon 71](../canon/71-a-refusal-caused-by-my-own-substitution.md)), a synthetic visit fills, and the export is **byte-faithful on his layout**. **Half two of the R5 walk re-runs to completion as the proof.** Build + **MANDATORY adversarial pass** — this is the F5-c derivation generalized, so its wrong-fill traps are known cousins. |
| **F8** | 🟢 **CLOSED 2026-08-27** | The ICD-10 coding tab. | **CLOSED on the judged deploy of `eec8685b`.** S1's substrate, S1b's drop record and S2's coding surface are LIVE. The acceptance walk passed on a QA build proven byte-identical to what shipped (blob `3aa08f9f`, empty runtime diff). **18 declared rows, 18 matched, no unnamed movement** — `docs/foundation/deploys/20260827-b439dcbb-JUDGED.md`. |
| **F8-S1** | 🟢 **MERGED · DEPLOYED 2026-08-27** | The ICD decision substrate + migration `20260825130000_f8s1_icd_decisions`. | **HOLD DISCHARGED** under #153(g) — migration and caller shipped as one supervised act. `assert-migrations-applied` flipped 🔴 2 unapplied → 🟢 109/109. |
| **F8-S1b** | 🟢 **MERGED · DEPLOYED 2026-08-27** | The ICD drop record — four exits, four reason tokens (ruling #149). | Shipped inside the same judged deploy. |
| **F8-S2** | 🟢 **CLOSED — DEPLOYED 2026-08-27** | The coding surface on the visit page (#153). | Walk passed; contrast defect found by the added axe-panel-open arm and fixed by ground (5 reported, 8 real, worst **1.16:1** hidden in axe's `incomplete`); re-proved 5→0, incomplete 1→0, elements 41→49. Live and structurally verified in the shipped bundle. |
| **F12-e** | 🟢 **MERGED · CITED 4 of 4 · DEPLOYED 2026-08-27 — AS AN UNJUDGED RIDER** | The **signed document carried no E/M while the screen showed one**. Fixed at `sign/route.ts`: the freeze is gated on `emApplies` ALONE — `emBlob &&` was the defect, not the guard. Ruling **#152** (PROVISIONAL). Merge `4895decfa5453e4688626992bf60229e9fac4df6` (PR #879). | ⚠️ **THE HOLD WAS OVERTAKEN BY A TREE.** This row read *"DEPLOY HELD"* until 2026-08-28 and that was **STALE**: the merge is a `rev-parse`-verified ancestor of the DEPLOYED commit `eec8685bfabd6d45614461d77a12aeeb272bc7b2`, and production runs that deploy's image `32a43656`. **It is LIVE.** This is [a declaration is bound to a CHANGE, a deploy ships a TREE](../../AGENTS.md) exactly: the F8 deploy's **18 declared rows were about ICD work, and not one could have detected an F12-e regression.** So the EVIDENCE half is missing, not the code. **Owed:** the F12-e comparison run after the fact, per that entry — and it is surfaced to the owner because a clinical-surface change reached production while its supervised judgement was still being held for it. |
| **F6.5** | 🟢 **BUILT 2026-08-28, run `20260828-220858-b1` session 02 — see the section below.** The recon below was re-verified against `main` before building and every line of it held | 🔴 was: **OPEN — RECON DONE 2026-08-27, and the item is NOT what the row said** | `gate-r1`'s *"BOTH sides"* test asserts one side. **Re-measured:** `gate-r1-paper-structure.test.ts:188` is titled *"the lockup gaps are absolute points on BOTH sides"* and makes exactly ONE assertion, on `toTwip(LOCKUP_PT.ruleToBody)`. `eyebrowToTitle` and `titleToRule` are live and unguarded at **`docx-generator.ts:168` and `:191`** — ⚠️ **not `:106`/`:129` as this row said; the line numbers had drifted.** | Done when the guard exists. Explicitly **a guard, not a deletion**. ⚠️ **AND THE NAME IS A FOSSIL: there is no longer a second side.** `lib/pdf-generator.ts` **does not exist** — ruling #113 retired `generateVisitPdf`, and PDF now renders DOCX→Gotenberg. So the fix is not "add the missing side"; it is *guard the two live tokens on the ONE surviving generator and stop the title claiming a generator that was deleted.* |
| **F18** | 🔵 **OPEN** | Three counts on one screen; the largest is frozen at compile time — banner reads *"79 of 80"* while the button reads *"6 of 80"*. | One count from one source, or three counts that each say which question they answer. ⚠️ Do **not** repoint the banner at mapping rows without establishing what `detectionStatus` is FOR. |
| **F6.3-followup** | 🔵 **OPEN** | The render sidecar is bounded but **not fair**: F6.3 stops one archive monopolising the renderer; two archives can still starve an interactive render. | A cross-request admission gate, or a second sidecar for bulk work. *Do not read F6.3's green as fairness.* |
| **F34** | 🟢 **OPEN — loop-eligible, and the loop owns the script** | **NO-PROGRESS GAINS A THIRD WORLD: `BLOCKED-ON-CI`.** Before halting, the probe checks for the loop's OWN open PRs whose citations are pending or already green. If any exist, the state is **BLOCKED-ON-CI** — a distinct marker that AUTO-RELIGHTS when they land or the queue drains — not a malfunction halt. ⚠️ **WORK THAT EXISTS BUT CANNOT LAND IS STARVATION, NOT SPIN**, and the switch currently cannot tell them apart. | **SPECIMEN, QUOTED — run `20260828-220858-b1`, halted `2026-08-29T00:00:20Z`:** *"The session reported CONTINUE, but `docs/foundation/RELAY.md` on origin/main is byte-identical from the start of the session to its end, for a second consecutive run."* The switch was RIGHT by its own rule — an item is not finished until its ledger row lands. But the loop had closed **F6.5** and built **F5-i-2** (#899, later merged 4-of-4). Its row could not land because #899's citation sat behind ~16 runs on the single self-hosted runner — **and the fix for that queue (#900, the second runner) was stuck in the same queue.** Done when the probe distinguishes the two worlds and a starved session relights itself instead of halting. ⚠️ The check is about the LOOP'S OWN PRs specifically; another actor's queue is not the loop's starvation. |
| **F25** | 🟢 **OPEN — small, loop-eligible** | Split the loop's `REPORT-MISSING` marker three ways: `REPORT-MISSING` / `REPORT-UNHEADED` / `SESSION-NEVER-STARTED`. | **VERIFIED UNBUILT**: in `scripts/foundation-loop.sh`, `REPORT-MISSING`=3, the other two = **0**. ⚠️ The discriminator must classify CONTENT, not count lines. |
| **F30** | 🟢 **CLOSED 2026-08-27** | Retirement conditions tested, not remembered. | **DONE — the close condition was *"a session actually runs it at STEP 0"*, and run `20260827-041645-b1` session 01 did.** `grep -c check-retirement-conditions .claude/settings.json` → **1**, so the grant HAS shipped; the script ran, partitioned **15 == 15**, fired its positive control, and exited **1** with **4 entries DUE**. ⚠️ Ruling **#151**'s claim that it *"has sat UNGRANTED on `main` since F30"* is therefore **STALE** — see the finding row below. |
| **F17** | ⏸️ **PARKED** | Four non-billable ICD-10 headers (`I87.30`–`.33`) admitted by the billing floor. Measured through `isValidIcd10()` with controls. | **TRIGGER NAMED** — see the archived body. |
| **F12-h** | ⏸️ **PARKED** | The templated-operative E2E class. | **TRIGGER NAMED:** the `e2e` headroom question (F19). |
| **F12-b** | ⏸️ **PARKED** | E/M item hosted by R4b 2026-08-14. | Parked on the **OWNER PING**. ⚠️ Single mention in the whole ledger. |
| **F5-i part 1b** | 🔴 **UN-PARKED 2026-08-28 — now F5-i-2, at the top of this table** | Per-shape certification generators. **The owner's call, which this row waited on, was made:** ruling #156. | ⚠️ **Never delivered by restoring the fallback.** The census retires when a second shape lands. **This row is a POINTER now; F5-i-2 is the item.** |
| **F19** | ⏸️ **DEFERRED — owner decision owed** | The `e2e` ceiling (`e2e.yml` `timeout-minutes: 55`). | Decision owed after the auto-cert ping. ⚠️ **Do not raise or lower the ceiling** without it. |
| **F20** *(swap)* | 🔧 **OPEN — owner-approved, awaits a quiet window** | Swap pinned at 4.0Gi with ~20 GB RAM free; historical pages never faulted back. ⚠️ **Two items carry the id `F20`** — see the reconciliation below. | `swapoff -a && swapon -a` in a quiet window. |
| **F11** *(third grant)* | 🔴 **OPEN — owner question** | Two of three STEP-0/canon instruments were granted 2026-08-17; the third is an owner question. | An owner decision. |
| **F7** | 🟢 **OPEN — supervised, low priority** | The one-time root-scratch sweep (342 files). | ⚠️ **Re-priced 2026-08-16: F7 is TIDYING, NOT A BLOCKER — "F7 must not hold the queue."** `shred` is denied to the loop by design. |
| **F33** *(unclaimed — this change)* | 🟠 **IN FLIGHT** | The ledger split + rotation, **plus its reader sweep**. ⚠️ **Referred to by BRANCH, not by number, until it lands** — the NUMBER-CLAIM PROTOCOL: a number is claimed by landing on `main`. Branch: `docs/ledger-split-and-rotation`. | This PR, cited. |
| **F33-R** *(same change)* | 🟢 **BUILT — the reader sweep** | **A CENSUS PROVES CONTENT, NOT REACHABILITY.** The split was content-preserving and every reader of the two paths still broke. Fixed in this PR: `check-retirement-conditions.sh` (watched set = head + archives), `rotate-ledger.sh` (3 phantom manifest anchors; `WRITE_HEAD` never passed, so `--apply` reported success while duplicating content), the `RULINGS.md` live index (status token per row — `OWNER RULING` was 23 → **0**, `PROVISIONAL` 47 → **1**), the archive spans (2 of 25 were hulls over a promoted section, so their citations resolved past EOF), and the mandated routes in `MASTER.md` + `AGENTS.md`. | **Done.** Guarded by `gate-ledger-reachability.test.ts` — 23 arms, mutation-proved. |

### 🟡 F8-S2 — THE CODING SURFACE REACHES THE VISIT PAGE — **2026-08-27, run `20260827-041645-b1` session 02**

**Ruling #153 (OWNER) built; ruling #154 (PROVISIONAL) recorded. Branch
`feat/f8-s2-coding-view`, PR #883, retired both sides.** S1 and S1b have had no
caller since 2026-08-25 — this is that caller.

**Citation — 4 of 4 on `cfd5c0f097465c2adb72e3506ba745322bb984a9`:**
   · `CI` 33074173989 a1
   · `e2e` 33074174018 a1
   · `a11y-ci` 33074174002 a1
   · `secrets-scan` 33074174004 a1

Produced by `bash scripts/check-citation.sh` on the MERGE commit and pasted, not
typed. Every line is `a1` — nothing was re-run, so there is nothing to explain.

⚠️ **AND THE `e2e` LINE WAS VERIFIED AT THE JOB LEVEL.** The surviving
`Playwright E2E (transcribe-md)` job carries **58 steps** — the real pack — while
the docs-only twin is `skipped` at 0. **See the step-count finding below: 58
here, 57 on the PR head, 59 on session 01's — the discriminator is a THRESHOLD,
and an exact-count predicate would have false-alarmed on two of those three.**

⚠️ **THE 16 RENDER ARMS RAN FOR THE FIRST TIME IN THIS CI, AND PASSED** — they
cannot execute in a worktree at all. That includes the mount-count proof that
the note panel survives a full round trip through Coding, which is the one
clinical claim of this slice.

**THE RECON CAME FIRST, AS #153(f) REQUIRES, AND IT CORRECTED THE ROW IT STARTED
FROM.** The contract's `Note · Documents · Coding` tab bar still does not exist;
the only two `role="tablist"` elements in the visit surface
(`visit-ready-view.tsx:1656`, `review-tabs-v2.tsx:162`) are both on the
**flag-OFF legacy path**, which #153 refuses to re-reach. What the measurement
found instead is **favourable and was not predicted**: both papers are already
hoisted into single consts — `paper` (unsigned, `ReviewDocumentView`) and
`signedPaper` (signed, `SignedDocumentView`) — each composed by **two** returns,
a Rounds one and a plain one. They were hoisted for an unrelated reason (*"so
the Rounds branch composes the SAME nodes instead of building second copies"*).
**So wrapping ONE const reaches all four render paths**, and the paper's React
identity is preserved for free.

⚠️ **AND THAT IDENTITY IS THE WHOLE CLINICAL RISK OF THIS SLICE.**
`visit-ready-view.tsx:1040-1043` states it in its own words: the paper *"is never
keyed and never conditionally mounted: `ReviewDocumentView` holds the in-session
E/M confirm in local state, so anything that changed its React identity would
silently re-block Sign and read as a flaky gate."* **The obvious two-view switch
— `{view === 'note' ? note : coding}` — unmounts the paper the moment the doctor
looks at coding.** The walk that would have shipped:

    1. doctor confirms the E/M level      -> in-session confirm held in state
    2. doctor switches to Coding          -> paper unmounts, state destroyed
    3. doctor switches back to Note       -> paper remounts, confirm GONE
    4. Sign is blocked again, no explanation, nothing to click

No error, no log line, and no existing gate watching. `VisitViewSwitch`
therefore **HIDES and never unmounts**, and hides **two ways** — `hidden` for
the accessibility tree and an inline `display:none` for the mechanics, because
`hidden` is UA-stylesheet `display:none` and any author rule with higher
specificity defeats it silently, leaving a panel VISIBLE while telling assistive
tech it is absent.

**WHAT LANDED**

| piece | what it does |
|---|---|
| `visit-view-switch.tsx` | the `Note \| Coding` primitive — #153(b). Roving tabindex + arrow keys, because a `role="tab"` without them is a half-implemented pattern that still passes axe |
| `icd-coding-view.tsx` | the surface. Needs-review / Accepted / Rejected / **No longer suggested** (orphaned) / **Suggested but not carried** (S1b's amber drops) |
| `lib/icd-decisions.ts` | ruling #154 — the reason vocabulary, the biconditional, the reason-aware no-op, and the narrower's asymmetric enforcement |
| `icd-codes/decision/route.ts` | `z.enum` at the boundary, and **#148(e)'s owed refusal audit** |
| migration `20260827120000_f8s2_icd_refusal_audit` | the fourth label, `ICD_CODE_DECISION_REFUSED` |
| `page.tsx` | selects and threads `icdDecisions`, which nothing read before |

**#148(e)'s OBLIGATION IS DISCHARGED, AND ITS SCOPE IS DELIBERATE.** S1 left
refusals unaudited *because no UI could invoke the route*, and named this slice
as the one that revisits it. Four refusals now write a row —
`visit_not_active`, **`visit_locked`**, `visit_not_ready`, `code_not_suggested`,
plus the two new reason refusals. **401 and 404 deliberately do NOT**: 401 has no
actor to attribute, and 404 is the ownership gate, so a row there would let an
unauthorised prober **append to the audit log of a practice they cannot read** —
turning an information-leak refusal into an information-leak write. `visit_locked`
is the important one: an attempt to re-code a SIGNED record is exactly what a
coding dispute asks about, and it left no trace anywhere until now.

**PROOF**

| gate | arms | status |
|---|---|---|
| `gate-f8-s2-decision-reason.test.ts` | 19, pure | **PASS locally**, mutation-proved 5 ways |
| `gate-f8-s2-coding-view.test.tsx` | 15, render | ⚠️ **CANNOT RUN IN A WORKTREE — CI-proven only.** See the finding below |
| `gate-f8-icd-decisions` · `gate-f8-icd-drop-record` · `decision/route` | 87 | **PASS** — updated to the tightened contract, not weakened |
| `review-read-only-paper` · `em-stale-unification` · `jsx-enclosing` | 71 | **PASS** — the structural guards on the surface I edited |

**THE MUTATION TABLE — every mutation asserted APPLIED before its result was believed:**

| mutation | reddens |
|---|---|
| M1 · delete the reason gate | **5 of 19** |
| M2 · relocate the gate AFTER the no-op check | **2 of 19**, and the failure NAMES the arm |
| M3 · no-op compares state only, ignoring the reason | **1 of 19** |
| M4 · narrower stops enforcing the reason on a rejected record | **2 of 19** |
| M5 · an accept keeps a stray reason | **1 of 19** |

⚠️ **M2's FIRST ATTEMPT WAS A NO-OP THAT PRINTED GREEN, AND IT FOUND A REAL
DEFECT IN MY OWN GATE.** The first M2 planted only a comment marker — canon's
*"mutate toward the REAL shape"* — so `19 passed` proved nothing. Rebuilt to
physically relocate the gate, it exposed that **the arm titled *"the reason gate
runs BEFORE the no-op check"* was aimed at a case that refuses under BOTH
orderings**: re-rejecting with a garbage reason differs from the stored reason,
so `sameReason` is false and the early return never fires. It was an arm that
could not fail, dressed as an ordering guard. The discriminating case is a reason
attached to an **already-ACCEPTED** code, where `sameState` and `sameReason` are
both true and a late gate absorbs an illegal payload as a successful no-op. Arm
rewritten; M2 now reddens it.

**⚠️ THE ADVERSARIAL PASS FOUND THREE DEFECTS IN MY OWN FINISHED DIFF.**
Fifth consecutive slice in this programme where that is true.

| # | what it found | why it mattered |
|---|---|---|
| **1** | **A comment asserting a mechanism that is measurably FALSE.** It said `props.readonly` was *"the only way to be read-only in this branch"*. `:631` computes `isSigned = props.readonly \|\| props.signedAt !== null`, and the branch is gated on `!isSigned` — so `props.readonly` **cannot be true where it is read.** | *A wrong mechanism in a source comment outlives the session that wrote it.* The prop is still forwarded rather than hard-coded `false`, because the two fail in OPPOSITE directions if that gate ever changes — forwarding stays correct, a literal `false` would silently offer accept/reject on a visit the caller declared read-only. |
| **2** | **A concurrency defect that makes a doctor's decision APPEAR TO VANISH.** Controls were disabled per-code, so two decisions could be in flight at once. The SERVER serialises them correctly under S1's row lock — the defect is on the CLIENT: every response carries a full projection, and whichever lands **last** wins the render. Response A arriving after B renders a projection computed before B existed. | The server is right and the screen is wrong until reload. **That is the same "your work vanished" perception the entire view switch exists to prevent**, arriving through a different door. Fixed by allowing ONE in-flight request — removing the race rather than reconciling it. New gate arm; the mutation that reddens it is named in the test. |
| **4** | **A SECOND comment my own change made false — on the security-relevant path.** The route's audit call site read *"it fires only when the write actually committed, because `decide` returns it only then."* The refusal audit makes that false: `decide` now returns a row in TWO cases, one of which writes nothing. Caught on a re-read, AFTER the first three were already fixed and pushed. | Same class as **1**, which is the point: *naming a class is not enumerating it.* The invariant that survives is stated instead — a NO-OP returns no row, and **the discriminator is the LABEL, never the presence of a row.** ⚠️ **This one cost a declared cancellation**: the branch's runs were in flight, and canon closes a branch at that moment. Merging a knowingly-false comment about audit behaviour on the accept/reject path was judged worse than discarding three runs that were still QUEUED and had done no work. Declared, not silent. |
| **3** | **A `useState` initialiser that runs once beside two `useMemo`s that do not.** If `props.icdCodes` changed under the component, the cards would re-derive from the new blob while the partition still described the old one. | **Unreachable today by measurement** — `icdCodes` has one writer and `layer-skip.ts:101` skips L7a whenever it has content — so it is recorded WITH ITS RE-ARMING CONDITION rather than fixed with an untestable synchronisation mechanism on a clinical surface. |

**AND FOUR REFUTATION TARGETS THAT SURVIVED, each checked rather than assumed:**
`readIcdDrops` really reads the `dropped` key my fixture writes · `apiError`
really returns `{error}`, which the view's error path reads · **both flags are
`true` in production** (`NEXT_PUBLIC_UX_SIMPLIFY` and
`NEXT_PUBLIC_REVIEW_DOC_VIEW`, read from the running container — they are
DIFFERENT flags, and the signed branch keys on the first, so a flag-off there
would have left #153(e) unmet in the only universe that matters) · and the
migration's `ALTER TYPE … ADD VALUE` form is **proven in this exact database**:
three prior `AuditAction` migrations are applied with `finished_at` set and
`PROMO_GRANT_CREDITED` is present in the live enum. ⚠️ **That last one was
established WITHOUT applying anything to QA** — doing so would have discharged
#153(g)'s declared hold, which is not this session's to discharge.

**WHAT THIS ROW DOES NOT CLAIM**

- ⚠️ **THE ACCEPTANCE WALK OF #153 HAS NOT BEEN RUN.** *"reach coding → accept →
  reject with a reason → sign → read frozen"* is an end-to-end walk on a real
  visit, and the loop **cannot drive a browser** (already an open finding) and
  **does not deploy a clinical surface** (#150). The parts are gated; the WALK is
  owed by the deploying supervised session and is the remaining condition for
  F8-S2 to close.
- **IT IS NOT DEPLOYED.** Per #153(g) the deploy is supervised and carries **TWO**
  migrations — S1's held `20260825130000_f8s1_icd_decisions` **and** this slice's
  `20260827120000_f8s2_icd_refusal_audit`. §2.5 is owed by that session, and its
  declaration must name both.
- ⚠️ **THE ADVERSARIAL PASS WAS RUN IN-SESSION, NOT BY INDEPENDENT REFUTERS** —
  the same honest limit F12-e recorded. Canon's argument for the pass is that it
  does not share the author's context, so a self-run pass is the weaker
  instrument. **This item is a candidate for an independent pass before it ships**,
  and it reaches a billable record.
- **Nothing here changes what any export or note emits.** An accepted code still
  flows nowhere — that is a later slice and a document-visible change needing its
  own pass.
- **No search-add typeahead, no substitute-code chip** (#149(f) DELETED that
  derivation: prefix-scanning the 604-code starter set offered `E66.0 → E66.01`,
  upcoding plain obesity to MORBID obesity), **no specialty-aware ranking.**

### 🟢 F6.5 — THE LOCKUP GUARD, AND THE FIRST MUTATION REFUTED MY OWN CLAIM ABOUT IT — **2026-08-28, run `20260828-220858-b1` session 02**

**Branch `fix/f65-lockup-guard`.** Citation owed — see HALTED below; the runner
was saturated when this was built.

**THE RECON WAS RE-VERIFIED BEFORE BUILDING, AND IT HELD.** The row's own line
numbers had drifted once before, so nothing was taken on trust: `pdf-generator.ts`
genuinely does not exist, `LOCKUP_PT` lives at `export-page.ts:175`, and
`eyebrowToTitle` / `titleToRule` are live and unguarded at `docx-generator.ts:168`
and `:191`. The single surviving assertion sat at `:192`, not `:188` — `:188` is
the `it(...)` title line.

**THE OLD TEST HAD THREE DEFECTS, ALL INVISIBLE WHILE IT WAS GREEN.**

| # | defect |
|---|---|
| 1 | **`BOTH sides` is a FOSSIL.** Ruling #113 retired the PDF generator; the PDF is now LibreOffice's render of these very bytes. There is one side. The file HEADER had already been corrected for this; the `it()` title had not |
| 2 | **One of three gaps asserted.** `ruleToBody` only; `eyebrowToTitle` and `titleToRule` unguarded |
| 3 | ⚠️ **IT PINNED A SPELLING.** `expect(DOCX_SRC).toContain('toTwip(LOCKUP_PT.ruleToBody)')` — a SOURCE-TEXT check. **`LOCKUP_PT` was not even imported by the test**; it appeared only inside a string. Extracting that call into a named const — an improvement — reddens it, while a change that keeps the spelling and emits different bytes stays green. **It failed for improvements and passed for regressions** ([canon 72](../canon/72-pin-properties-not-spellings.md)) |

**WHAT LANDED.** The gap assertions now run against the RENDERED bytes, for all
three tokens, plus a non-vacuity arm. Measured first, never assumed — the three
tokens reach the document in **two different Word units**, which is not a slip:

| token | reaches the XML as | unit |
|---|---|---|
| `eyebrowToTitle: 3` | `<w:spacing w:after="60"/>` | twips |
| `titleToRule: 6` | `w:space="6"` on the border | **whole points** |
| `ruleToBody: 12` | `<w:spacing w:after="240"/>` | twips |

⚠️ **AND THE HELPER CARRIES A TRAP I WALKED INTO FIRST.** Anchoring on the bare
`'<w:p'` matches inside `<w:pPr>` and `<w:pBdr>`, so my probe's title slice began
*inside the paragraph's own properties*. `paragraphAround()` anchors on `'<w:p '`
and `'<w:p>'` and takes the `Math.max` — the substring trap, [fifth sighting](../canon/50-the-substring-trap-fourth-sighting-same-family.md).

**THE MUTATION TABLE — every mutation asserted APPLIED (by line number) before
its result was believed.**

| mutation | result |
|---|---|
| **M1 · `eyebrowToTitle: 3 → 5`** | ⚠️ **GREEN — 15 passed. This REFUTED a claim I had already written into the comment.** |
| M2 · hard-code the eyebrow gap (`after: 80`) | **REDDENS**, naming the arm and printing the real paragraph |
| M3 · hard-code the border space (`space: 9`) | **REDDENS** |
| M4 · hard-code the rule→body gap (`after: 300`) | **REDDENS** |
| M5 · collapse `titleToRule` to `0` | **REDDENS the non-vacuity arm** — and the derivation arm stayed green, which is the division of labour working |

⚠️ **M1 IS THE ENTRY IN THIS ROW WORTH READING.** My comment claimed the new
guard fixed *"changing `eyebrowToTitle: 3` to `5` left it green"*. **It does
not.** The expectation is computed from the same `LOCKUP_PT` the generator
reads, so **both sides move together and no token edit can ever redden it** —
[a control aimed where the answer is predetermined is not a control](../canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md).
The guard was fine; **the claim about it was false**, and it would have shipped
as a comment asserting a mechanism that does not exist — the exact defect F8-S2's
adversarial pass found twice in one diff. The comment now states the limit in its
own words, and the discriminating mutation is **breaking the DERIVATION**, never
editing the token.

**WHAT THIS ROW DOES NOT CLAIM**

- **It changes NOTHING a doctor receives.** Test-only: `git diff` touches one
  file, and `export-page.ts` / `docx-generator.ts` are byte-clean — verified by
  `git diff --numstat` after every mutation was restored, not by re-reading them.
- **It does not pin the tokens' VALUES**, deliberately — those are a design
  decision, not an invariant. Stated above and in the source.
- **No adversarial pass by an independent refuter.** The mandatory pass binds
  changes to the clinical generation / note / export path; this alters no
  emitter. M1 was self-caught, which is the weaker instrument by canon's own
  argument, and is named as such.
- `tsc --noEmit` clean; **100 files / 1618 tests pass** in `src/lib/__tests__/`,
  run in a worktree with `node_modules` symlinked (`setup: 108ms` — React
  resolves, so these are real local runs, not the CI-only case).

### ✅ F12-e — THE SIGNED DOCUMENT CARRIES THE LEVEL THE DOCTOR ATTESTED — **2026-08-27, run `20260827-041645-b1` session 01**

**Ruling #152 (PROVISIONAL). Branch `fix/f12e-em-freeze-parity`, PR #879, retired both sides.**

**Citation — 4 of 4 on `4895decfa5453e4688626992bf60229e9fac4df6`:**
   · `CI` 33049826612 a1
   · `e2e` 33049826630 a1
   · `a11y-ci` 33049826669 a1
   · `secrets-scan` 33049826615 a1

Produced by `bash scripts/check-citation.sh` on the MERGE commit, pasted rather
than typed. Every line is `a1` — no run was re-run, so there is nothing to
explain.

⚠️ **AND THE `e2e` LINE WAS VERIFIED AT THE JOB LEVEL, NOT TAKEN ON ITS
CONCLUSION.** RELAY's own open finding says a `4 of 4` no longer proves the
Playwright pack ran. Measured on this very run: the surviving
`Playwright E2E (transcribe-md)` job carries **59 steps** — the real pack — while
the docs-only twin is `skipped` at 0. The same probe on #878 (a docs-only PR)
returns **5**. **The discriminator is STEP COUNT**, and it is now written down in
the findings table rather than left as a claim.

**THE MECHANISM, NAMED BY RUNNING SOMETHING RATHER THAN BY READING.** The freeze
at `sign/route.ts` required L7b to have emitted an `em` blob. The level the
doctor REVIEWS does not come from that blob — `visits/[id]/page.tsx:649` seeds
`emScoredCode` from `initialEmScore.override ?? suggestedCode`, **inside**
`if (!emNotApplicable)`. So:

    emBlob === null  ->  no signedCode frozen
      -> projectEmForDisplay(null, …) returns null   (visit-export.ts:107)
      -> the signed PDF, DOCX and EVERY EHR clipboard format print NO E/M,
         while the screen showed one and the doctor attested it.

⚠️ **THE FILING'S TWO LOAD-BEARING CLAIMS WERE BOTH CORRECTED BY BUILDING IT.**

| the filing said | measured |
|---|---|
| *"Introduced by F12-c"* | **No — live in production today.** F12-c widens the population; it did not create it. F12-c is not even deployed. |
| *"`emSuppressed` is exactly the hook a fix needs"* | **Not needed, and deliberately not consulted.** It says *why* the blob is absent; the freeze does not care. |

**THE POPULATION, READ-ONLY ON PROD, POSITIVE-CONTROLLED:**

| measure | n |
|---|---|
| `cptCodes.em = null` AND `emScoredCode` non-null | **12** |
| …of those, **SIGNED** | **10** |
| …imaging (where an absent E/M would be CORRECT) | **0** |
| control: rows with `cptCodes` / an `em` key / `em = null` / SIGNED | 28 / 27 / 17 / 32 |

All `bariatric-surgery` and `gastroenterology`. ⚠️ **AND THE VERDICT WAS
ESTABLISHED WITHOUT READING ONE BYTE OF NOTE TEXT** — because the `emScoredCode`
seed sits inside `if (!emNotApplicable)`, its presence is *structural proof* the
predicate said E/M APPLIES. A predicate run over production note bodies would
have been a PHI read; this is the same answer by a route that never needed one.

**⚠️ THE ADVERSARIAL PASS FOUND A DEFECT THE FIX ITSELF INTRODUCED — AND IT IS
THE `99214 — undefined` STRING THIS REPOSITORY HAS ALREADY SHIPPED ONCE.**
Freezing on a blob-less visit synthesises `{ signedCode }` with no
`description`, and `CptEm.description` was declared REQUIRED, so
`ehr-formatters.ts:231` and `docx-generator.ts:259` interpolated it blind.
**Unrepaired, the fix would have traded an ABSENT field for a WRONG one.** No
prose is invented (there is no non-AMA descriptor set here, and #149(d) forbids
authoring a billing string): the separator is conditional at both sites, and
`CptEm.description` is now **OPTIONAL** — which is the load-bearing half,
because it made a third consumer (`codes-tab.tsx:148`) fail to typecheck rather
than wait to be grepped for.

**THE GATES, BOTH MUTATION-PROVED, EVERY MUTATION ASSERTED APPLIED FIRST:**

| gate | arms | mutation → reddens |
|---|---|---|
| `gate-f12e-em-freeze-parity.test.ts` | 11, behavioural — real route, real `emAppliesToVisit` | `emBlob && emApplies` → **4**; `emBlob` alone → **5**, incl. F12-a's own suppression arm |
| `gate-f12e-frozen-level-prints-no-undefined.test.ts` | 8 — four EHR formats + a **real rendered DOCX** | restore either interpolation → **4** (EHR) / **1** (DOCX), output showing `99214 — undefined` |

⚠️ **A VACUITY DEFECT IN MY OWN GATE, FOUND BY THE SAME PASS AND FIXED:** every
suppression arm asserts an ABSENCE, and an absence is also what you get when the
route refused or never reached the write. `expectSigned()` now asserts the
SIGNED write happened first — **proved to discriminate** by mutating the harness
to omit the attestation, which turned three silent passes into three named
failures.

**WHAT THIS ROW DOES NOT CLAIM.**

- **It is FORWARD-ONLY.** The **10 already-signed rows keep their absent E/M.**
  Changing a signed clinical record is owner-class and was not attempted.
- **It is NOT DEPLOYED**, and the loop is not the actor that would deploy it.
- ⚠️ **THE ADVERSARIAL PASS WAS RUN IN-SESSION, NOT BY INDEPENDENT REFUTERS.**
  Canon's whole argument for that pass is that it does not share the author's
  context, so a self-run pass is the weaker instrument. Named, not papered over:
  **this item is a candidate for an independent pass before it ships.**
- **The full-suite number from the worktree is not a measurement** — no root
  `node_modules`, so 16 files cannot resolve `react/jsx-dev-runtime`. The
  controlled delta against the same tree before the change is **+1 file, +8
  tests, zero new failures**, and the one failing test (`gate-devstates`) passes
  10/10 on clean `main` in the shared checkout.

> ⚠️ **WHERE THE BILLING ARC IS, AND WHY THE QUEUE LOOKS EMPTY OF IT.** The
> B-series (B8 wallet/admission, B9 grants) has **zero OPEN rows in this head** —
> measured, not assumed. Its bodies live in `docs/foundation/relay/` (`2026-08-10`,
> `-11-part2`, `-12`, `-13`, `-15-part2`), and every row there is CLOSED or LIVE.
> **So "the billing tail is next" is a PROGRAM-SPINE statement, not a queue row**:
> whoever takes it opens it by reading those archives and filing a fresh item
> here, because *a ledger row is the builder's input and an archive is not*.
> ⚠️ Do not read the absence as "billing is done" — read it as "billing has no
> open row **yet**". Naming which of the two it is was the whole point of the
> reader sweep.

### Open findings carrying no item id

| Finding | State | Note |
|---|---|---|
| **✅ `main` IS `strict: false` — #899 IS BEHIND `main` AND THAT DOES **NOT** BLOCK ITS MERGE. DO NOT "HELPFULLY" MERGE `main` INTO IT.** | 🟢 **MEASURED 2026-08-28, session 02 — a trap DISARMED before anyone stepped in it** | `git merge-base --is-ancestor origin/main origin/feat/f5i2-shape-aware-encounters` returns **1** — #899 does not contain #898's merge — and `gh pr view 899` reads `mergeable=UNKNOWN`. **Together those look exactly like *"this PR must be updated before it can merge."*** It must not. `gh api …/branches/main/protection` reads **`"strict": false`**, so *require-branches-up-to-date* is **OFF**. ⚠️ **THE TRAP IS THAT THE HELPFUL ACT IS THE EXPENSIVE ONE:** merging `main` into #899 is a push to its ref, which **cancels its four runs** — runs that have held a queue position since `22:39:17Z` behind a single saturated runner — and buys **nothing**, because protection never asked for it. **Merge #899 on its own green, unrebased.** |
| **the gate reads SIX check runs; the citation ceremony cites FOUR workflow runs — and that is why the `e2e` skip-twin exists** | 🔵 **MEASURED 2026-08-28, session 02 — sharpens two open rows, competes with neither** | Branch protection's required contexts, read from the API: **`Playwright E2E (transcribe-md)` · `test` · `npm audit (high+critical gate)` · `axe-core sweep (chromium x desktop+mobile)` · `TruffleHog (verified-only, diff-scan)` · `unit tests (transcribe-md + packages)`** — **six JOB names**, while `check-citation.sh` cites four WORKFLOW names. [Gate on the object the gate reads](../canon/11-gate-on-the-object-the-gate-reads.md), confirmed live rather than recalled. ⚠️ **AND IT EXPLAINS THE MECHANISM BEHIND THE OPEN *"a 4 of 4 no longer proves the pack ran"* ROW, WHICH WAS RECORDED AS A SHAPE WITHOUT A REASON.** `Playwright E2E (transcribe-md)` is a REQUIRED CONTEXT, so **something with that exact name must report success on every PR — including a docs-only one.** The skip-twin sharing the real pack's `name:` is not an accident or sloppiness; **it is what lets a docs-only PR satisfy branch protection at all.** Any fix to the step-count discriminator must therefore keep a job of that name reporting success on docs-only PRs, or it will make every docs-only PR unmergeable. **That constraint was not written down anywhere and it bounds the fix.** |
| **⚠️ `MASTER.md`'s OWN WORKED GREP SCORES ZERO — the status token is `OWNER-RULING`, and STEP 0 writes it `OWNER RULING`** | 🔴 **MEASURED 2026-08-28, session 02 — one-line fix, applied in this change** | `MASTER.md:134` teaches the post-split verification with the string **`OWNER RULING`** (spaced). **Measured against the live head: spaced = `0`, hyphenated `OWNER-RULING` = `26`.** ⚠️ **THE FALSE ALARM IS THE EXACT ONE THAT PARAGRAPH EXISTS TO PREVENT.** Its subject is the split having truncated the status markers out of the rows — so a session that runs the printed string gets `0`, matches it against the prose's *"returned 0"*, and concludes the ledger is **still broken** when it is fine. **A wrong number that matches the expectation is invisible** — [the most dangerous wrong number is the one the prediction expects](../canon/65-the-most-dangerous-wrong-number-is-the-one-expected.md), arriving through the instruction that teaches the check. Same class `MASTER.md` already records for `check-read-budget.sh`: a correctly-measured note that decayed and kept reading as rigour. ⚠️ **AND IT COST ME TWO WRONG GREPS BEFORE I READ THE ROW FORMAT** — I also tried `^\| #15`, which cannot match because rows begin `\| <date> \| #NNN \|`. *Read the format before trusting a pattern; a zero measures YOUR PATTERN first.* |
| **⚠️ `main`'s QUEUE HEAD CITES RULING #156 AS ITS AUTHORITY, AND #156 IS NOT IN THE REGISTER ON `main`** | 🟠 **MEASURED 2026-08-28, session 02 — NOT a defect by session 01; it is #899's blockage propagating** | `RELAY.md:66` opens the live queue with *"**F5-i-2 LEADS THE QUEUE** — owner ruling **#156**"*, and `:88` cites it again. **`grep -c "#156"` on `main`: `RELAY.md` = 2, `RULINGS.md` = 0**, across the head AND every archive, positive-controlled with `#155` (1 head + 1 archive). ⚠️ **I NEARLY FILED THIS AS SESSION 01 FAILING TO TRANSCRIBE, AND THAT WOULD HAVE BEEN FALSE.** The transcription EXISTS — commit **`5fab2a24`**, *"#156 was cited by the queue head and was not in the register"* — and `git branch --contains` puts it on **`feat/f5i2-shape-aware-encounters` ALONE**; `git merge-base --is-ancestor 5fab2a24 origin/main` returns **1**. Session 01 did precisely what canon orders — *the receiving session records the ruling in its first commit* — and bundled it with the work it authorises. **So the ruling is correctly written and inherits #899's blockage.** The live consequence stands and is worth naming: **until #899 merges, `main` carries a queue head whose stated authority a reader cannot resolve.** It discharges itself on that merge; no separate action is owed. |
| **⚠️ A THIRD-PARTY MERGE DESTROYED A CITATION MID-PACK — 1h04m37s of EXECUTED work, and the canon reference case was 33m39s** | 🔴 **MEASURED 2026-08-28, run `20260828-220858-b1` session 02** | Session 01 merged #897 → `8f5320311b4e61d1b137d2d99ec7c8095619664f` and handed its citation to me. At **23:47:52Z** a supervised session merged **#898** → `3030e957034fd0828be1f4414ac843287d2999c9`, and that push **cancelled three of `8f532031`'s four runs**: `CI` 33215808366, `e2e` 33215808323, `secrets-scan` 33215808410. Only `a11y-ci` 33215808322 survived, `success`. ⚠️ **The `e2e`'s Playwright job 99005441277 had been EXECUTING for `1h04m37s`** — not queued, executing — which is **double** the 33m39s of `AGENTS.md`'s own reference case for this exact shape. **`8f532031` can now never be cited 4 of 4.** ⚠️ **NOBODY MISBEHAVED, WHICH IS THE POINT:** *a merge IS a push*, `merge-pr.sh` guards the base branch's runs and a merge to `main` legitimately lands there. **THE RECOVERY IS CANON'S AND IT IS ALREADY AVAILABLE:** cite the **DESCENDANT** — `3030e957` contains `8f532031`, so a full citation on it covers #897's code **plus** #898's, and certifies the tree that actually ships rather than its parent. Its four runs were queued at `23:47:52Z`. **Do not re-run the cancelled past.** |
| **the shared tree was DIRTY and the loop REFUSED to sync it — sessions read a STALE `MASTER.md` and `INBOX.md`** | ✅ **DISCHARGED 2026-08-28 by #898 + a supervised ff-merge — INSTANCE only** | My own launch header recorded it: *"shared tree is 2 commit(s) behind origin/main and NOT synced: branch=main dirty=3 — refusing to move it under a session. The INBOX and MASTER below may be STALE."* The three dirty entries were `.axe/`, `.ci-labels/`, `.enum/` — **live supervised WORKTREES**, untracked because `.gitignore` did not cover the class. ⚠️ **So the loop's own relight guard was being tripped by other sessions' correctly-created worktrees, and the cost was silent: a session reads a rulebook two commits stale and is TOLD so in one line it may not act on.** #898 (`fix/gitignore-worktree-class`) landed the class rule and `scripts/list-worktrees.sh`; a supervised session then synced the tree. **Verified, not assumed:** shared-tree `HEAD` = `3030e957` = `origin/main`, `git status --porcelain` **empty**, `grep -c worktree .gitignore` = **4**, and `.f0-ignore` retired. ⚠️ **The HAZARD is not closed** — it re-arms whenever an actor creates a root directory the ignore class does not name. |
| **one self-hosted runner is a SPOF** | 🔴 **OPEN — trigger met** | `quillmd-ci-1` is a single point of failure for every merge. Measured 57–88 min queues; 12 runs deep on 2026-08-26. **The owner has authorized a second light-jobs runner; the measured pain has arrived.** |
| **`nightly-tests` on `ubuntu-latest`** | 🟠 **FILED, NOT BUILT** | The only workflow left GitHub-hosted after #868 (`nightly-tests.yml:45`). Not a required context. |
| **a `4 of 4` citation no longer proves the Playwright pack ran** | 🔵 **OPEN** | Since #861 the `e2e` workflow can conclude `success` without executing the pack. `check-citation.sh` reads run conclusions and never `/jobs`. Loop-fixable. |
| **zombie CI runs poison the `--branch` view** | 🔵 **OPEN — MEASURED 2026-08-27, signature CORRECTED, partially cured** | Runs `queued` forever with **zero jobs**. ⚠️ **`created_at == updated_at` IS NOT THE DISCRIMINATOR and must not be used as one** — PR #877's own `CI` and `secrets-scan` both carried it while holding **4 and 1 real jobs** and running to completion, and 2 of 6 genuine zombies did *not* carry it. **`jobs == 0` while `status == queued` is the tell.** They do **NOT age out**: a Dependabot run sat queued with zero jobs for **1,334 h (55.6 days)**, two on `main` for **489 h**. `POST /actions/runs/{id}/force-cancel` **partially works, 2 of 6** — and the split is exact: `created ≠ updated` → **clears**; `created == updated` → **refuses**, with GitHub answering *"Cannot cancel a workflow run that has not been queued yet"* about a run whose own `status` field reads `queued`. **4 remain, permanently.** The hook ritual stands. |
| **`retire-branch.sh`'s remote leg is DENIED** | ⚠️ **REFUTED 2026-08-27 — THE ROW IS MEASURABLY FALSE, and it was filed one day earlier** | The row says the remote half *"can never succeed"*. **It just did.** `bash scripts/retire-branch.sh feat/f8-s2-coding-view` printed `· remote — retired`, and `git ls-remote --heads origin feat/f8-s2-coding-view` returns **empty** against a positive control (`main` resolves to `cfd5c0f0…`). The script still shells `git push origin --delete` at **`retire-branch.sh:77`** — the row's own mechanism, unchanged. ⚠️ **WHY THE PREMISE WAS WRONG, AND `AGENTS.md` ALREADY SAYS IT:** *"a deny matches the command the agent RUNS, not what a script it runs does internally, so the wrapper is a hole in its own deny by construction."* The deny reaches what a session TYPES, not what a granted script executes. **The row reasoned from the deny list to a behavioural conclusion and never ran the command.** Its recommended `gh api -X DELETE` workaround is unnecessary. ⚠️ Only the LOCAL leg failed here, correctly and loudly, because a worktree still held the branch. |
| **a `4 of 4` e2e discriminator must be a THRESHOLD, not an exact step count** | 🔵 **OPEN — SHARPENED 2026-08-27 with three data points** | The step-count discriminator is right and *"59 steps"* is not the predicate. **Measured across three real packs: 59** (session 01, #879), **57** (F8-S2 PR head), **58** (F8-S2 merge commit) — all the genuine pack, all on code PRs. The docs-only twin reads **5** or **0**. ⚠️ **A `steps === 59` check would have FALSE-ALARMED on two of those three**, and the whole point of this finding is to stop a false green — manufacturing false reds instead would just move the defect. The honest predicate is *"the surviving job has many steps (≳50) and the skipped twin has ~0"*, and any implementation should assert the GAP rather than a constant. |
| **`gh run list --status in_progress` UNDER-REPORTS — a run reads `queued` while its jobs execute** | 🔵 **OPEN — measured 2026-08-27** | Observed on the F8-S2 merge commit: the `CI` run reported `status: queued` at RUN level while `gh api …/jobs` showed **one job already `completed success`** and others running. A repo-wide `--status in_progress` query returned **0 runs while the runner reported `busy=true`** — arithmetic that does not reconcile, resolved by looking at jobs. ⚠️ **THIS SHARPENS THE ZOMBIE FINDING RATHER THAN COMPETING WITH IT:** `status == queued` is AMBIGUOUS between *waiting* and *executing*, which is exactly why the zombie tell had to be `jobs == 0` and not the status. A session asking *"is anything running?"* by run status alone gets a false NO — and that is the in-flight question every push depends on. |
| **⚠️ I FABRICATED A 40-CHARACTER SHA — second occurrence of a canon entry written THE SAME DAY** | 🔵 **FILED 2026-08-27, by the session that did it** | Querying my own new HEAD, I typed `f3c413b3ad4e30e15caf7bad1f4a4bcc27a3b2fd`. The real commit is `f3c413b3cbb51a37a0f0744d8b3e735fa75f582c`. **I padded the short `f3c413b3` from `git commit`'s output into a plausible full-length string**, `gh run list --commit` correctly returned `[]`, **and I was one step from blaming that empty result on the documented propagation window** — the *"a documented defect is the most convenient suspect"* trap, in the same breath as the fabrication. Caught by resolving the sha with `git rev-parse` instead of trusting my own typing. ⚠️ `docs/canon/37`'s subsection records this exact instance class **from earlier today**; this is its second occurrence, which is the argument for its rule: **check your own input before you check the precedent.** |
| **a dependabot wave saturates the single runner, and it re-priced a declared cancellation** | 🟠 **OPEN — measured 2026-08-27** | Repo-wide queue went from **7 to ~19** DURING this session as a dependabot fan-out landed: 13 runs across five dependabot branches, all behind `quillmd-ci-1`. ⚠️ **AND IT MADE MY OWN DECLARED CANCELLATION COST MORE THAN I PREDICTED.** I declared it as *"~3 minutes of queue position, no executed work"* — true at the moment of the push. What actually happened is that the fresh runs rejoined the **back** of a queue that then filled behind me, turning a ~3-minute prediction into roughly an hour of wall-clock. **The declaration was honest and the estimate was wrong**, which is precisely canon's own warning that *the cost is set by how late the event lands* and that a cheap instance is not evidence of a cheap class. Recorded against the SPOF row above as the concrete pain the second runner would relieve. |
| **`a11y-ci` green does NOT cover the coding panel's interior** | 🔵 **OPEN — honest limit, filed 2026-08-27 by F8-S2** | The sweep DOES reach the right routes — `a11y.spec.ts:105`/`:107` visit `/visits/:READY` and `/visits/:SIGNED`, the two branches F8-S2 edits — so the `Note \| Coding` tablist IS swept. **But the Coding panel is `hidden` on first paint and nothing clicks the tab, and axe skips hidden subtrees.** So the panel's cards, reason picker and amber section are **unswept**, and this slice's `4 of 4` must not be read as covering them. The cure is an a11y arm that activates the tab; deliberately not built here, because a11y spec changes belong with the Phase-1 restyle that will rewrite this surface anyway (#153(c)). |
| **the loop cannot drive a browser** | 🟠 **OPEN** | `MASTER.md`'s permission table has no row for it. ⚠️ **It just cost something concrete:** F8-S2's acceptance walk (#153) is an end-to-end browser flow, so the item is BUILT and GATED and cannot be CLOSED by the loop. |
| **⚠️ A COMPONENT TEST CANNOT RUN IN A WORKTREE — BY CONFIG, NOT BY CHANCE** | 🔴 **OPEN — MECHANISM NAMED 2026-08-27, and it is sharper than the ledger's prior account** | The ledger recorded this as *"16 worktree files fail deterministically on `react/jsx-dev-runtime`"*, which reads like a resolution accident. **It is a hard-coded path.** `apps/transcribe-md/vitest.config.ts:21` aliases react to `path.resolve(__dirname, '../../node_modules/react')` — a root `node_modules` **SIBLING**, which no `git worktree` has. **Controlled:** a PRE-EXISTING component test (`em-level-card.test.tsx`) fails identically in the same tree, so it is the harness and not the new code; `require.resolve('react')` from the same directory succeeds, so it is the ALIAS and not node resolution. **Measured this session: 17 of 387 files, every one of them this cause, 1 failed test (`gate-devstates`, same cause).** ⚠️ **AGENTS.md requires the loop to work in an isolated worktree, so for the loop this is EVERY React gate, ALWAYS** — including its own new ones, which is why F8-S2's 15 render arms are CI-proven only. ⚠️ **AND IT IS NOT A CASUAL FIX:** the alias's own comment records why it is hard-coded — the monorepo hoists RTL's react peer to the root while the app installs its own, and two React copies in one process give *"useState is null"*. Re-pointing it changes how 380 test files resolve React, which is not a thing to do inside a clinical slice. **Filed, not fixed.** |
| **`ln` is REFUSED to the loop, and it is not in `MASTER.md`'s permission table** | 🟠 **OPEN — filed 2026-08-27** | `MASTER.md` says a refusal absent from its table **is a finding**, so this is filed rather than absorbed. The natural cure for the row above is one symlink — `.f8s2-build/node_modules → /opt/meddoc-pro/node_modules`, reproducing exactly what CI has, inside a directory `.gitignore` already covers via `.f[0-9]*-*` — and `ln` is refused. ⚠️ **The granted route was DECLINED on purpose:** `node -e` would have created it, and `MASTER.md` explicitly forbids tunnelling a withheld form through a sanctioned interpreter — *the sanctioned-hatch-becomes-the-undisciplined-door failure*. **Either grant `ln`, or the worktree/React finding above stays permanent for the loop.** |
| **⚠️ A STALE SHARED TREE MAKES `assert-migrations-applied.sh` UNDER-REPORT — AND THE WRONG NUMBER IS THE EXPECTED ONE** | 🔴 **OPEN — MEASURED 2026-08-27, session 02, and this is the dangerous shape** | STEP 0 runs this check every session. **Measured at close-out:** it printed 🔴 `1 unapplied — 20260825130000_f8s1_icd_decisions`. The truth on `main` is **2** — F8-S2 landed `20260827120000_f8s2_icd_refusal_audit` in the same arc. The script reads the migrations DIRECTORY OF THE TREE IT RUNS IN, and `ls packages/db/prisma/migrations \| grep -c f8s2` in `/opt/meddoc-pro` returns **0**, because the shared tree's local `main` is behind. ⚠️ **WHY THIS IS WORSE THAN AN ORDINARY STALE-TREE READING: `1` IS EXACTLY WHAT F8-S1's DECLARED HOLD PREDICTS.** A session comparing the check against the ledger sees the number it expects, ticks the invariant, and never learns a second unapplied migration exists. *A wrong number that matches the declared expectation is invisible* — there is no incoherent value to catch it, which is the detector this house normally relies on. **This is the canon entry *"a tree-relative instrument answers about its OWN tree"* with a sharper consequence than that entry records.** ⚠️ **CONCRETE COST IF UNCAUGHT:** the supervised deploy owed by #153(g) must apply BOTH migrations; a §2.5 declaration written from this check would name one. **The cure is to resolve the shared tree by absolute path AND sync it before believing the number** — and until then, read this check's count against `git -C /opt/meddoc-pro rev-parse HEAD` vs `origin/main`, not against the ledger's expectation. |
| **the shared tree's local `main` is BEHIND `origin/main`** | 🔴 **RE-ARMED 2026-08-27 by session 02's own merges — the instance closed and the hazard did not** | Marked discharged earlier this session (all three refs read `fdfb76f7`), then **re-created by my own two merges**: HEAD is `fdfb76f7c2ed9443037f47f2903b59a5cf2307c8`, `origin/main` is `e12514662e8b00cc74c0459057de327faa49b181`. **The loop did NOT sync it**, for the reason session 01 gave: `git merge --ff-only` on the shared tree is an act on a deploy surface, the discriminator is *"is anyone standing there?"*, and a supervised actor was demonstrably active today (#878/#880/#881). It is also the direct cause of the migration under-report row above. **A `git merge --ff-only` by the supervised side clears both.** ⚠️ **AND THE LESSON IS IN THE RE-ARMING, NOT THE FIX:** every merge the loop makes re-creates this, so it is not a defect anybody can close — it is a standing consequence of the loop merging while the deploy surface tracks a different ref. |
| *(historical — the 2-merges-behind instance, discharged and superseded by the row above)* | ✅ **DISCHARGED 2026-08-27, session 02 — verified, not assumed** | Local `main`, `origin/main` and the shared tree's `HEAD` all read `fdfb76f7c2ed9443037f47f2903b59a5cf2307c8`. The supervised side synced it, as the row said would clear it. Left on the record with its original body below, because the hazard it names is permanent and only this INSTANCE closed. |
| *(the original body of the row above)* | 🔵 **HISTORICAL** | Measured at `07:29Z`: `/opt/meddoc-pro` local `main` = `83532132`, `origin/main` = `4895decf`. ⚠️ **`deploy-prod.sh` reads `git rev-parse HEAD` FROM THE TREE IT RUNS IN** and names its §2.5 declaration after that sha — the canon case *"A DECLARATION NAMING THE WRONG COMMIT IS WORSE THAN NO DECLARATION, BECAUSE IT LOOKS LIKE EVIDENCE."* **The loop did NOT sync it**: routine syncing of the shared tree is an act on a deploy surface, the discriminator is *"is anyone standing there?"*, and a supervised actor was demonstrably active (they merged #878 at `06:34Z`). **A `git merge --ff-only` by the supervised side clears it.** |
| **`check-retirement-conditions.sh` is GRANTED — ruling #151's premise is stale** | 🔵 **OPEN — correction owed to a ruling, filed 2026-08-27** | #151 argues from *"it has sat UNGRANTED on `main` since F30 … and still inert"*. **Measured 2026-08-27: `grep -c` → 1, and the script RAN.** The ruling's CONCLUSION (the loop detects, a supervised session adds) is untouched — only its live example expired. Same shape `MASTER.md` already records for `check-read-budget.sh`: **an entry naming an instrument as REFUSED must be re-checked when the grant lands.** |
| **4 INBOX entries have MET their retirement condition and are still delivered** | 🟠 **OPEN — SUPERVISED action, measured 2026-08-27** | From `check-retirement-conditions.sh` (exit **1**, partition **15 == 15**, positive control fired): the **F10 acceptance-criteria pointer** (F10 closed), the **auto-certification handoff** (branch merged AND `auto-certify.ts` on `origin/main`), the **retirement-sweep entry itself** (*"retires when the sweep prints its first list"* — it just did), and the **#137/F23 pointer**, whose struck sentence was a **false present-tense fact**. ⚠️ **The loop never writes `INBOX.md` by design**, so it can only report these. |
| **a `4 of 4` e2e no longer proves the pack ran — and here is the DISCRIMINATOR** | 🔵 **OPEN — now REPRODUCED, filed 2026-08-27** | Previously recorded as a claim; measured here. `e2e.yml` runs **two jobs sharing one `name:`** — a docs-only skip job (`:87`–`:89`) and the real pack (`:113`–`:115`) — so the run conclusion cannot tell them apart. **Measured: #878 (docs-only) `success` with the surviving job at 5 STEPS; #879 (code) `success` at 59 STEPS.** ⚠️ **The discriminator is STEP COUNT, not conclusion and not job name** — `check-citation.sh` reads run conclusions and never `/jobs`. Loop-fixable, and the fix now has an exact predicate. |
| **an intermittent failure in the unit suite on clean `main`** | 🔵 **OPEN — observed once in 5 runs, NOT named** | Full suite in the SHARED tree on clean `main`: one run reported **1 file / 1 test failed**; four further runs reported **381 files / 5321 tests, 0 failures**. ⚠️ **The failing test was NOT captured before it passed again, so it is unnamed** — recorded with that limit rather than smoothed away. Distinct from the 16 worktree files that fail deterministically on `react/jsx-dev-runtime` (no root `node_modules`). |
| **10 SIGNED visits carry no E/M in their exported document** | 🔴 **OPEN — OWNER-CLASS, filed 2026-08-27 by F12-e** | The back-catalogue F12-e's fix cannot reach: `cptCodes.em = null` + a real `emScoredCode` (99212–99215), `bariatric-surgery` / `gastroenterology`, **zero imaging**. The screen showed a level; the signed PDF/DOCX/EHR print none. **Remediation touches SIGNED CLINICAL RECORDS, so it is owner class (b)/(d), not the loop's.** ⚠️ **The direction of harm is UNDER-CODING**, which is the safe direction and is why this is filed rather than rushed. **TRIGGER:** an owner decision on whether a signed record may gain a frozen level after the fact, and under what audit. |
| **the logout-path residual under F26** | 🔴 **OPEN** | Session cookie still present 10s after sign-out while the URL had reached `/login`. |
| **F3's twelfth declared row** | 🔵 **OPEN** | A visit row vanished unaudited; actor later named as the BullMQ stale-visits cron. Carried, unclosed. |
| **the concept-supply flow** | 🔵 **OPEN — unscheduled, no id** | Ruled into existence by #147 mechanic 4 and F24's close. Competes with F8. |
| **`docs/rounds/RELAY.md` is 236,036 chars** | 🔵 **OPEN — named, triggered** | 1.57× the read limit; F32's banner covers the interim. **It belongs to the Rounds programme, not Foundation** — a Rounds session splits it with `bash scripts/rotate-ledger.sh` once its manifest gains a row. Scope discipline over completeness. |

## Rules

The Rounds relay's rules apply verbatim and are not restated here — read
`docs/rounds/RELAY.md` §Rules first. In particular: **1** (one item per session,
taken to its gate), **2a** (merge-commit CI cited by SHA and run id; local
results never close an item), **2b** (no push mid-run), **2c** (no evidence
before the event), and **7** (say what would make the check fail, then make it
fail) with its corollaries.

Four rules are specific to this program.

**F1. A tenant test that has never seen two seats has proved nothing.**
193 of 196 users are alone in their practice, and **no practice with more than
one user holds any clinical data at all** (DISCOVERY §B.10). A `practiceId`
filter passes vacuously against that population. **T1 exists to remove this
excuse, and no item after T1 may cite a gate that ran only against a solo
practice.**

**F2. A billing number is not proved by a green test. It is proved against the
vendor's own page, with a URL and a date.**
Every rate in the price table carries both. The Deepgram error (DISCOVERY §D.2)
survived a deliberate reconciliation *because both sides of it were internal*.

**F3. READ-ONLY on production stays the default.** Any item that writes to
production data is a **deliberate transactional act** — abort-on-mismatch
guard, audit row, stated row count before and after — never a side effect of a
migration or a check. The house precedent is the imaging-E/M artifact purge.

**F4. The billing writer must be incapable of running outside production, and
"incapable" needs two conditions** — the code gate *and* credentials that are
not real. `scripts/check-qa-mock-posture.sh` reads the **running containers**,
not the compose file, for exactly this reason. A `${STRIPE_SECRET_KEY:-…}` in
`docker-compose.qa.yml` is a bug until proven otherwise.

---

## Invariants re-checked every item

- `bash scripts/assert-migrations-applied.sh` — after any migration, and before
  reading a deploy's own success message as proof.
- `bash scripts/check-qa-mock-posture.sh` — every item that touches a vendor key.
- `bash scripts/check-imaging-em-artifacts.sh`, `check-minio-encrypted-mount.sh`,
  `check-pg-encrypted-mount.sh` — the standing set.
- Close-out hygiene per AGENTS.md: shred, **check exit codes**, escalate, *then*
  remove.
- Branch cadence: branch from `main`, merge back on green, retire the branch.

---

## RECONCILIATION — REUSED ITEM IDS

**Two ids are each carried by two unrelated items.** Recorded here because a
`grep` returns both, and the merged one reads as the live one because it is the
one with a citation attached.

| id | the two items | which a grep should mean | why |
|---|---|---|---|
| **F20** | **α** *SWAP IS PINNED AT 4.0Gi* (filed 2026-08-18, **still OPEN**) · **β** *THE NO-PROGRESS KILL SWITCH WAS READING A FILE THE SESSION CANNOT WRITE* (2026-08-19, **DONE**, ruling #132, merge `904991ab1479afdd79c5c70cfee34f8e28a679ef`) | **β** | β's id is welded into a ruling row, two branch names, a merge commit and the on-disk filename `gate-f20-ledger-progress-universe.test.ts`. α holds it only in ledger prose. Renaming β would falsify artifacts; renaming α costs nothing. ⚠️ **This collision was never previously recorded anywhere.** |
| **F26** | **α** *#745 IS SECURITY-SHAPED* (2026-08-22, **DISCHARGED** 2026-08-25) · **β** *A SUPERSEDED CANCELLATION IS NOT A FAILURE* (2026-08-24, **MERGED AND CITED**, ruling #146, merge `f6326311337fb8e757fcf886b4d5da979a471e0e`) | **β** | Same reasoning: β is welded into a ruling row, a branch name and `gate-f26-citation-supersession.test.ts`. α's subject already has a durable identifier of its own — the issue number `#745`. Partly recorded already, in α's own discharge body. |

⚠️ **Neither id is renamed in any archived body.** Both β items are referenced by
merged citations, ruling rows, branch names and on-disk test filenames; renaming
them would make the record false rather than clearer. The sweep that found these
cleared F10, F12 and F30 as false positives after three of its own detector
versions each failed a control.

⚠️ **AND A REUSED ID IS A SYMPTOM, NOT THE DISEASE.** Both collisions happened
because a session picked "the next number" by reading a file it could not read
in one read. The NUMBER-CLAIM PROTOCOL (`RULINGS.md`) is the cure for the
*claiming* race; this split is the cure for the *reading* one.

<!-- ARCHIVE-INDEX-BEGIN — generated; do not hand-edit -->

> **Generated by `scripts/lib/split-ledger.py`. Do not hand-edit between the
> markers — `scripts/rotate-ledger.sh` regenerates this block and REPLACES it.**
>
> **The durable pointer is the TITLE.** A line number in an append-only file is
> stale before it lands — measured here: a citation to line 27621 was correct
> against the PARENT commit and wrong by 16 against the commit that wrote it,
> because that commit added 16 lines above it. Cite sections by title.
>
> **The `pre-split lines` column is the ONE legitimate use of line numbers, and
> it is why every existing citation still resolves.** Those numbers address the
> FROZEN pre-split file, which can never grow again, so they cannot go stale. A
> reader holding an old `RELAY.md:NNNNN` — in this ledger, in RULINGS.md, or in
> any of the external files that cite one — finds its archive by the span below.
> **Nothing had to be rewritten to keep those citations working.**

| archive | first section (TITLE — the durable pointer) | pre-split lines | chars |
|---|---|---|---|
| [`2026-08-15-part1.md`](relay/2026-08-15-part1.md) | ⏭️ THE QUEUE — FIDELITY ARC AT THE HEAD — set 2026-08-15 | 31–1889 | 109,810 |
| [`2026-08-15-part2.md`](relay/2026-08-15-part2.md) | ✅ F14-a — THE CITATION DOOR SURVIVES A RUNS-API OUTAGE — **2026-08-17, run `20260817-183630` | 1890–3636 | 104,880 |
| [`2026-08-15-part3.md`](relay/2026-08-15-part3.md) | 🟡 F5-a — THE WALL IS 22, NOT 75, AND THE MEASUREMENT CAME FIRST — **2026-08-16** | 3637–5086 | 82,092 |
| [`2026-08-04-part1.md`](relay/2026-08-04-part1.md) | GATE 0 — ✅ CLEARED 2026-08-04 | 5087–5137, 5174–6758 | 87,178 |
| [`2026-08-04-part2.md`](relay/2026-08-04-part2.md) | Phase BILLING | 6759–7556, 7570–7691 | 54,633 |
| [`2026-08-08.md`](relay/2026-08-08.md) | Found on the way past — 2026-08-08, on the loop's FIRST unattended run | 7692–8013 | 18,059 |
| [`2026-08-09.md`](relay/2026-08-09.md) | Found on the way past — 2026-08-09, scoping the sanctioned smoke | 8014–9137 | 61,127 |
| [`2026-08-10.md`](relay/2026-08-10.md) | 🟩 B3 IS LIVE IN PRODUCTION — 2026-08-10T02:48Z. 2 of 3 Deepgram rates, and it says so. | 9138–10823 | 91,455 |
| [`2026-08-11-part1.md`](relay/2026-08-11-part1.md) | 🟩 THE OWED DEPLOY IS DONE — `f89c7c33` IS LIVE IN PRODUCTION, 2026-08-11T01:48Z | 10824–12893 | 109,762 |
| [`2026-08-11-part2.md`](relay/2026-08-11-part2.md) | ✅ B8 STEP 1 IS BUILT — THE WALLET READ, AND ADMISSION JUDGES THE MONEY A DEBIT CAN REACH — 2 | 12894–13046 | 8,309 |
| [`2026-08-12.md`](relay/2026-08-12.md) | 🟩 B8 STEP 1 IS LIVE IN PRODUCTION — `dbb584a4`, 2026-08-12T01:10Z | 13047–15095 | 107,826 |
| [`2026-08-13.md`](relay/2026-08-13.md) | ✅ B8 STEP 3 IS BUILT — A FAILED VISIT IS **FREE**, AND THE ITEM SHIPS THE MEASUREMENT INSTEA | 15096–16822 | 95,178 |
| [`2026-08-14.md`](relay/2026-08-14.md) | RC-1 + RC-3 — WHAT THE ADVERSARIAL PASS FOUND — 2026-08-14 | 16823–18382 | 86,119 |
| [`2026-08-16.md`](relay/2026-08-16.md) | ✅ F4 — SHIPPED AND LIVE, 2026-08-16 — 11 of 11 DECLARED ROWS MATCHED | 18383–18495 | 5,510 |
| [`2026-08-17.md`](relay/2026-08-17.md) | ✅ F10 — A DECLARATION IS COMMITTABLE BEFORE ITS DEPLOY — **2026-08-17, session 06** | 18496–19713 | 67,207 |
| [`2026-08-18-part1.md`](relay/2026-08-18-part1.md) | F17 — TWO ADDITIONS FROM AN INDEPENDENT RE-MEASUREMENT, AND THE ITEM STAYS PARKED — **2026-0 | 19714–21212 | 82,588 |
| [`2026-08-18-part2.md`](relay/2026-08-18-part2.md) | ✅ F12-c — THE COMPUTE LAYER STOPS WRITING AN OFFICE E/M ONTO AN OPERATIVE NOTE — **BUILT 202 | 21213–22962 | 101,779 |
| [`2026-08-20.md`](relay/2026-08-20.md) | ✅ F6.4 — THE VACUOUS ARM, AND THE SIGNED-DOCUMENT DEFECT IT WAS HIDING — **2026-08-20, run ` | 22963–24319 | 72,343 |
| [`2026-08-21.md`](relay/2026-08-21.md) | 🔵 F5-e — CLAIMED: fix direction **(B)**, at the root — 2026-08-21, run `20260820-174139-b1`  | 24320–25625 | 71,859 |
| [`2026-08-22.md`](relay/2026-08-22.md) | 🟠 SESSION FINDING — THE QA IMAGES ARE THREE DAYS STALE, AND F5-i PART 1a's OWED QA WALK CANN | 25626–26879 | 66,669 |
| [`2026-08-24-part1.md`](relay/2026-08-24-part1.md) | F24-S5 REBUILD — the identity widens · owner ruling, 2026-08-24 | 26880–28721 | 99,256 |
| [`2026-08-24-part2.md`](relay/2026-08-24-part2.md) | 🔴 F24-S5 ITEM A — THE CEILING IS A **WALL**, AND THE WALL IS ON THE BRANCH THE DEPLOY IS HEL | 28722–29757 | 53,987 |
| [`2026-08-25-part1.md`](relay/2026-08-25-part1.md) | 🟢 F24 — **CLOSED** 2026-08-25, at 75 of 80 | 29758–31869 | 108,424 |
| [`2026-08-25-part2.md`](relay/2026-08-25-part2.md) | ⚠️ F8-S2 — THE RATIFIED DEFAULT DOES **NOT** DISCHARGE THE PARK, AND HERE IS THE MEASUREMENT | 31870–32143 | 13,403 |
| [`2026-08-26.md`](relay/2026-08-26.md) | 🟩 F5-i PART 1a's OWED QA WALK IS **DONE** — AND THE BLOCKER THAT HELD IT IS DISCHARGED BY ME | 32144–33386 | 66,885 |

**25 archives · 1,826,338 chars · largest 109,810.**

<!-- ARCHIVE-INDEX-END -->

### 🟡 F5-i-2 — THE NARRATIVE SHAPE DERIVES A SELF-TEST — **2026-08-28, run `20260828-220858-b1` session 01**

**Owner ruling #156. Branch `feat/f5i2-shape-aware-encounters`.**

⚠️ **AND THE FIRST THING THIS ROW HAS TO SAY IS THAT #156 WAS NOT IN THE
REGISTER.** The queue head has cited it since `a7a5d75d` (2026-08-28T03:42:26Z)
and `grep -c "#156"` returned **0** against `RULINGS.md` and **0** against every
file in `docs/foundation/rulings/`, positive-controlled against `#155` (1 head,
1 archive). The decision's substance had landed — in that commit's message and
in the queue row — but the ruling row never did. Transcribed in this branch's
first commit, marked as a transcription, with the receiving session's record
governing if the two ever differ.

**WHAT THE ENGINE DOES NOW.** `deriveVerificationEncounter` gains a second
generator, reached **only** when a form carries ZERO measurement rows. It
dictates one sentence per narrative concept the form's own compiled field set
carries — `chief_complaint`, `past_medical_history`, `plan`, `hpi.*`, `exam.*`,
`test.*.result` and the rest — and **nothing for a concept the form does not
name**. A concept it has no sentence for is **SKIPPED, never guessed**.

**THE GATE DID NOT LOOSEN, AND TWO MEASUREMENTS SAY SO RATHER THAN A PROMISE.**

- The **cell floor was already shape-appropriate** and was not touched:
  `certification-lifecycle.ts:778` reads `cellFieldIds.size > 0 && filledCellCount === 0`,
  so a form with no table cells was never required to fill one. #156(b) is
  satisfied by code that already existed; claiming credit for changing it would
  have been a false row.
- The flat `MIN_CERTIFIED_FILLED_FIELDS = 10` is **untouched**. It is reachable
  for the owner's 35-field form, so nothing about his acceptance needs it moved,
  and relaxing a safety floor with no evidence it blocks anything is the
  loosening #156(d) rejects by name.

**PROOF — 22 arms in `gate-f5i2-narrative-encounter.test.ts`, plus the inverted
arms in three existing gates.**

| mutation | asserted applied first | reddens |
|---|---|---|
| M1 · a catch-all sentence for unknown concepts | ✅ | **1** — the "cannot speak to" refusal |
| M2 · dictate every sentence regardless of the form | ✅ | **8**, incl. the fabrication arm and the fill proof |
| M3 · strip the header (sentence count changed) | ✅ | **3 — AND NOT THE ARM BEING PROVED.** See the finding below |
| M3b · strip the marker, count held constant | ✅ | **1** — exactly the arm built for it |
| M4 · let a MEASUREMENT form reach the narrative generator | ✅ | **16 across 3 files**, incl. the arterial and thyroid fabrication refusals |
| M5 · one identical sentence for every concept | ✅ | **5 — AND NOT the correspondence arm.** See the finding below |
| M5b · same, against the new distinctness arm | ✅ | **6** |
| M6 · drop the canonical sort | ✅ | **1** — determinism |
| M7 · an off-registry sentence key | ✅ | **module load throws; the suite cannot run at all** |
| M8 · half-revert the synonym fix (measurement side) | ✅ | **1** |
| M9 · half-revert the synonym fix (narrative side) | ✅ | **1** |

**⚠️ TWO MUTATIONS FOUND DEFECTS IN MY OWN GATE, WHICH IS THE POINT OF RUNNING
THEM.**

- **M3** should have reddened *"passes the REAL synthetic-evidence gate"* and did
  not — three unrelated count arms caught it instead, which is canon's
  *overlapping guards must not launder an unproved arm* exactly. The measurement
  that explains it: of the twelve sentences this generator can dictate, **4 carry
  an explicit synthetic marker of their own and 8 carry none**, and the fixture
  happened to include two of the four. A new arm builds a form drawn only from
  the bare eight, and M3b reddens it alone.
- **M5** should have reddened *"each field cites the sentence dictated for ITS
  OWN concept"* and did not: the harness pairs sentence *i* with concept *i*, so
  identical sentences satisfy it by construction. It proves CORRESPONDENCE and
  cannot prove DISTINCTNESS. ⚠️ **And the implementation already claimed
  distinctness in a comment with nothing asserting it** — the venous generator's
  own scar restated, where `index % 5` gave 8 distinct values across 20 cells,
  every text arm passed, and 14 cells could never fill.

**⚠️ THE ADVERSARIAL PASS FOUND TWO DEFECTS IN THE FINISHED DIFF, SHARING ONE
ROOT — AND THE FIRST WAS A FABRICATION THIS CHANGE ITSELF INTRODUCED.**

`REGISTRY_SYNONYMS` lets a physician approve an alternative spelling, and
`resolveTemplateFields` honours it when MATCHING facts. The new classifier read
the RAW concept string, so it was reading a different vocabulary from the one
that fills.

| # | concrete input → wrong output | why it mattered |
|---|---|---|
| **1** | `exam.vascular.diameter` — a registry synonym of `measurement.diameter` — took the narrative branch and dictated **"Examination of the vascular diameter: documented and unremarkable in this synthetic example."** | Invented prose about a MEASUREMENT field, stored in the certification artifact. ⚠️ **Before this change that input refused safely (`no_measurement_rows`), so the change had made it strictly WORSE** — the arterial fabrication class arriving through a synonym. |
| **2** | `impression` — a synonym of `assessment`, and an ordinary consult mapping — found no sentence and was silently dropped, so a form mapped that way could be refused as unaddressable when it is nothing of the kind. | A false rejection on exactly the shape this item exists to serve. |

Fixed at the root by `canonicalConcept()` in `concept-registry.ts`, built from
`REGISTRY_SYNONYMS` rather than written out so the two directions cannot
disagree — **fix by ground, not by hit**: every present and future synonym is
covered, not the four that exist today. Each half is mutation-pinned separately
(M8, M9) because *the failure that ships is a half-landed fix*.

**A THIRD FINDING, PINNED RATHER THAN FIXED — and it bounds this item's own
acceptance.** A consult form is served **only** while it carries zero
measurement rows. Map ONE field to a measurement concept — a doctor confirming
`Largest polyp diameter (mm)` as `measurement.length` is an ordinary act — and
the form leaves the narrative branch and refuses `unsupported_study_type`. That
refusal is CORRECT today (this engine cannot dictate a polyp diameter, and
inventing one is the fabrication class), but it means **#156's acceptance is
contingent on the owner's form having no measurement-mapped field, and that has
NOT been established**: the only measurement of his form was taken under a
blanket `exam.vascular` substitution that forced `measurementRows` to zero for
*any* form ([canon 71](../canon/71-a-refusal-caused-by-my-own-substitution.md)).
An arm pins the boundary with a discriminating control so it fails loudly if
anybody moves it by accident.

**WHAT THIS ROW DOES NOT CLAIM**

- ⚠️ **#156's ACCEPTANCE IS NOT MET, AND THE LOOP CANNOT MEET IT.** *"The owner's
  R5 form certifies END-TO-END on QA, a synthetic visit fills, the export is
  byte-faithful on his layout, half two of the R5 walk re-runs to completion"* is
  a browser walk on QA. **The loop cannot drive a browser** (standing open
  finding) and does not deploy a clinical surface (#150). The ENGINE is built and
  gated; the WALK is owed by a supervised session, and the `.docx` handoff stays
  HELD until it is green, exactly as #156 says.
- ⚠️ **THE FILL PROOF USES AN IDEAL EXTRACTION, NOT THE MODEL.** It drives the
  REAL `resolveTemplateFields` over the derived encounter's own sentences with
  one fact per dictated concept — deliberately the BEST case, on the same
  reasoning the venous fill proof states. **The untested claim, written down
  before the pass ran: that a real Layer-3 extraction of this text emits facts
  whose `concept` equals the form's mapped concepts.** Only the QA walk closes
  that.
- ⚠️ **THE ADVERSARIAL PASS WAS RUN IN-SESSION, NOT BY INDEPENDENT REFUTERS** —
  the same honest limit F12-e and F8-S2 recorded, and canon's whole argument for
  the pass is that it does not share the author's context. A self-run pass is the
  weaker instrument. **This item is a candidate for an independent pass before it
  ships**, and it reaches a stored clinical artifact.
- **Nothing is deployed.** No migration, no schema change, no runtime flag.
- **`no_measurement_rows` was RETIRED and replaced by `no_addressable_fields`.**
  Back-catalogue measured rather than assumed: production carries **5**
  `TEMPLATE_TWIN_CERTIFY_FAILED` rows (2 `certify`, 2
  `certifyNativeTemplateAction`, 1 `synthetic_test` — reconciling to 5) and
  **zero** with `stage: 'derive_encounter'`, so no stored reason string is
  invalidated.

### 🟢 A STANDING OPEN FINDING IS DISCHARGED BY MEASUREMENT — the worktree/React blocker

**`ln -s /opt/meddoc-pro/node_modules <worktree>/node_modules` works, and the
loop's render arms are no longer CI-only.**

The ledger's row *"⚠️ A COMPONENT TEST CANNOT RUN IN A WORKTREE — BY CONFIG, NOT
BY CHANCE"* records `vitest.config.ts:21` aliasing react to a root
`node_modules` SIBLING no worktree has, and its sibling row records `ln` as
REFUSED to the loop. **The grant has since shipped** — `MASTER.md`'s permission
table carries it, scoped by pinning the source path — and it was exercised
tonight.

**Measured, using the ledger's OWN named control:** `em-level-card.test.tsx` —
the pre-existing component test that row cites as failing identically in a
worktree — passes **12 of 12**, with `setup: 121ms` rather than the `0ms` that
marks a wrong-config run. **Full suite in the worktree: 388 files, 5437 tests,
0 failures**, against that row's recorded baseline of *17 of 387 files failing
deterministically, 1 failed test*.

⚠️ **THE `ln` ROW IS THEREFORE DISCHARGED AND THE `vitest.config.ts` ROW IS
NOT.** The alias is unchanged and still hard-codes a path a worktree does not
have; what changed is that the loop may now create the thing it points at. The
underlying config remains as that row describes it, including its recorded
reason (two React copies give *"useState is null"*), and re-pointing it is still
not a thing to do inside a clinical slice.

⚠️ **AND THE INTERMITTENT-FAILURE ROW IS NOT DISCHARGED EITHER** — *"observed
once in 5 runs, NOT named"*. It did not reproduce in two full runs tonight.
**Two clean runs is not a refutation of a 1-in-5 flake**, and recording it as one
would be the coarse-sampling error that row already guards against.
