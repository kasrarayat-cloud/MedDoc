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

**F8 LEADS THE QUEUE** — ruling #147 (*"F24 CLOSES → F8 opens"*), and F24 closed
2026-08-25 at 75 of 80. **Canon and process items ride along; they are not the
work.** The morning report's `### THROUGHPUT` line exists to keep that visible.

| Item | State | What it is | Blocked on / Done when |
|---|---|---|---|
| **F8** | 🔴 **OPEN — QUEUE HEAD** | The ICD-10 coding tab. Recon re-validated: code-side claims hold by byte-identity, population claims have drifted. Design contract `docs/foundation/f8-icd-tab-design.md` is landed and live. | **UNBLOCKED IN FULL 2026-08-27.** The last open question — *where the coding surface lives* — was answered by **ruling #153**: the visit page, smallest primitive. S1 and S1b are merged; **F8-S2 is the only remaining work and it is now startable.** Done when S2's acceptance walk passes end to end. |
| **F8-S1** | 🟡 **MERGED · DEPLOY HELD — now SCOPED to S2** | The ICD decision substrate + migration `20260825130000_f8s1_icd_decisions`. Cited 4 of 4. | ⚠️ **RULING #153(g), 2026-08-27: the migration deploys *WITH* S2's landing, as ONE supervised deploy — migration and caller together.** That is this hold's own stated retirement condition, not a new decision: S1 shipped with no caller deliberately, and S2 is the caller. **VERIFIED HELD**: `assert-migrations-applied.sh` reads 🔴 `1 unapplied` on prod AND QA — **declared, not a finding**, and it stands until S2 lands. ⚠️ **Its printed remediation advice must NOT be followed** — applying a migration outside the §2.5 gate is exactly what this hold prevents. Deploy is a supervised act. |
| **F8-S1b** | 🟡 **MERGED · NOT DEPLOYED** | The ICD drop record — four exits, four reason tokens (ruling #149). | Does **not** extend S1's hold. Deploy is supervised. |
| **F8-S2** | 🔴 **OPEN — UNPARKED 2026-08-27 by ruling #153 (OWNER)** | Wire S1/S1b's substrate to a surface **on the visit page**: a segmented `Note \| Coding` control, or an equivalent two-view switch, on the visit's paper. The doctor reaches coding **without leaving the visit**. | ⚠️ **RECON FIRST** — measure the REAL component tree and propose the insertion point; do NOT start from the contract's tab-bar premise, which is already measured not to exist. **The return path is narrow and named:** if the paper *structurally cannot* host a second view, THAT finding returns — **never a re-litigation of the choice.** ⛔ **Never a separate route; never re-reaching the V2 strip** (both refused explicitly, so silence cannot be read as permission). **Constraints:** decisions flow ONLY through `icdDecisions` + the three audit labels + provenance separation (#149(a)); a **SIGNED** visit shows coding **READ-ONLY**; the primitive stays **minimal** — structure now, style at Phase-1. ⚠️ **#148(e)'s obligation falls due here by its own re-arming condition: the refusal audit is owed IN THE SAME CHANGE.** **DONE WHEN, end to end on a real visit:** reach coding → accept one code → reject one **with a reason** → both land in `icdDecisions` with correct audit labels → **sign** → the coding view reads **frozen**. |
| **F12-e** | 🟡 **BUILT · MERGED-PENDING · DEPLOY HELD** | The **signed document carried no E/M while the screen showed one**. Fixed at `sign/route.ts`: the freeze is gated on `emApplies` ALONE — `emBlob &&` was the defect, not the guard. Ruling **#152** (PROVISIONAL). | **Built, gated and held.** Deploy is a SUPERVISED act (`AGENTS.md` § STANDING AUTHORITY, ruling #150) — the loop does not ship a clinical-surface change, so it built and HELD, and this row says so. §2.5 is owed by the deploying session, which takes its own baseline. |
| **F6.5** | 🔴 **OPEN** | `gate-r1`'s *"BOTH sides"* test asserts one side. `LOCKUP_PT.eyebrowToTitle`/`titleToRule` are **live and UNGUARDED** (`docx-generator.ts:106`, `:129`) — not dead code. | Done when the guard exists. Explicitly **a guard, not a deletion**. |
| **F18** | 🔵 **OPEN** | Three counts on one screen; the largest is frozen at compile time — banner reads *"79 of 80"* while the button reads *"6 of 80"*. | One count from one source, or three counts that each say which question they answer. ⚠️ Do **not** repoint the banner at mapping rows without establishing what `detectionStatus` is FOR. |
| **F6.3-followup** | 🔵 **OPEN** | The render sidecar is bounded but **not fair**: F6.3 stops one archive monopolising the renderer; two archives can still starve an interactive render. | A cross-request admission gate, or a second sidecar for bulk work. *Do not read F6.3's green as fairness.* |
| **F25** | 🟢 **OPEN — small, loop-eligible** | Split the loop's `REPORT-MISSING` marker three ways: `REPORT-MISSING` / `REPORT-UNHEADED` / `SESSION-NEVER-STARTED`. | **VERIFIED UNBUILT**: in `scripts/foundation-loop.sh`, `REPORT-MISSING`=3, the other two = **0**. ⚠️ The discriminator must classify CONTENT, not count lines. |
| **F30** | 🟡 **RESIDUAL CLOSING HERE** | Retirement conditions tested, not remembered. Script merged; **the grant did not ship with it** and it stayed inert for days. | **The grant ships in this change.** Closes when a session actually runs it at STEP 0. |
| **F17** | ⏸️ **PARKED** | Four non-billable ICD-10 headers (`I87.30`–`.33`) admitted by the billing floor. Measured through `isValidIcd10()` with controls. | **TRIGGER NAMED** — see the archived body. |
| **F12-h** | ⏸️ **PARKED** | The templated-operative E2E class. | **TRIGGER NAMED:** the `e2e` headroom question (F19). |
| **F12-b** | ⏸️ **PARKED** | E/M item hosted by R4b 2026-08-14. | Parked on the **OWNER PING**. ⚠️ Single mention in the whole ledger. |
| **F5-i part 1b** | ⏸️ **PARKED — owner's call** | Per-shape certification generators. | ⚠️ **Never delivered by restoring the fallback.** The census retires when a second shape lands. |
| **F19** | ⏸️ **DEFERRED — owner decision owed** | The `e2e` ceiling (`e2e.yml` `timeout-minutes: 55`). | Decision owed after the auto-cert ping. ⚠️ **Do not raise or lower the ceiling** without it. |
| **F20** *(swap)* | 🔧 **OPEN — owner-approved, awaits a quiet window** | Swap pinned at 4.0Gi with ~20 GB RAM free; historical pages never faulted back. ⚠️ **Two items carry the id `F20`** — see the reconciliation below. | `swapoff -a && swapon -a` in a quiet window. |
| **F11** *(third grant)* | 🔴 **OPEN — owner question** | Two of three STEP-0/canon instruments were granted 2026-08-17; the third is an owner question. | An owner decision. |
| **F7** | 🟢 **OPEN — supervised, low priority** | The one-time root-scratch sweep (342 files). | ⚠️ **Re-priced 2026-08-16: F7 is TIDYING, NOT A BLOCKER — "F7 must not hold the queue."** `shred` is denied to the loop by design. |
| **F33** *(unclaimed — this change)* | 🟠 **IN FLIGHT** | The ledger split + rotation, **plus its reader sweep**. ⚠️ **Referred to by BRANCH, not by number, until it lands** — the NUMBER-CLAIM PROTOCOL: a number is claimed by landing on `main`. Branch: `docs/ledger-split-and-rotation`. | This PR, cited. |
| **F33-R** *(same change)* | 🟢 **BUILT — the reader sweep** | **A CENSUS PROVES CONTENT, NOT REACHABILITY.** The split was content-preserving and every reader of the two paths still broke. Fixed in this PR: `check-retirement-conditions.sh` (watched set = head + archives), `rotate-ledger.sh` (3 phantom manifest anchors; `WRITE_HEAD` never passed, so `--apply` reported success while duplicating content), the `RULINGS.md` live index (status token per row — `OWNER RULING` was 23 → **0**, `PROVISIONAL` 47 → **1**), the archive spans (2 of 25 were hulls over a promoted section, so their citations resolved past EOF), and the mandated routes in `MASTER.md` + `AGENTS.md`. | **Done.** Guarded by `gate-ledger-reachability.test.ts` — 23 arms, mutation-proved. |

### ✅ F12-e — THE SIGNED DOCUMENT CARRIES THE LEVEL THE DOCTOR ATTESTED — **2026-08-27, run `20260827-041645-b1` session 01**

**Ruling #152 (PROVISIONAL). Branch `fix/f12e-em-freeze-parity`.**

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

### Open findings carrying no item id

| Finding | State | Note |
|---|---|---|
| **one self-hosted runner is a SPOF** | 🔴 **OPEN — trigger met** | `quillmd-ci-1` is a single point of failure for every merge. Measured 57–88 min queues; 12 runs deep on 2026-08-26. **The owner has authorized a second light-jobs runner; the measured pain has arrived.** |
| **`nightly-tests` on `ubuntu-latest`** | 🟠 **FILED, NOT BUILT** | The only workflow left GitHub-hosted after #868 (`nightly-tests.yml:45`). Not a required context. |
| **a `4 of 4` citation no longer proves the Playwright pack ran** | 🔵 **OPEN** | Since #861 the `e2e` workflow can conclude `success` without executing the pack. `check-citation.sh` reads run conclusions and never `/jobs`. Loop-fixable. |
| **zombie CI runs poison the `--branch` view** | 🔵 **OPEN — MEASURED 2026-08-27, signature CORRECTED, partially cured** | Runs `queued` forever with **zero jobs**. ⚠️ **`created_at == updated_at` IS NOT THE DISCRIMINATOR and must not be used as one** — PR #877's own `CI` and `secrets-scan` both carried it while holding **4 and 1 real jobs** and running to completion, and 2 of 6 genuine zombies did *not* carry it. **`jobs == 0` while `status == queued` is the tell.** They do **NOT age out**: a Dependabot run sat queued with zero jobs for **1,334 h (55.6 days)**, two on `main` for **489 h**. `POST /actions/runs/{id}/force-cancel` **partially works, 2 of 6** — and the split is exact: `created ≠ updated` → **clears**; `created == updated` → **refuses**, with GitHub answering *"Cannot cancel a workflow run that has not been queued yet"* about a run whose own `status` field reads `queued`. **4 remain, permanently.** The hook ritual stands. |
| **`retire-branch.sh`'s remote leg is DENIED** | 🔵 **OPEN — filed 2026-08-26** | It shells `git push origin --delete`, which is in the deny list, so the remote half can never succeed. It correctly refuses to claim otherwise. The working route is `gh api -X DELETE repos/{owner}/{repo}/git/refs/heads/<branch>`. |
| **the loop cannot drive a browser** | 🟠 **OPEN** | `MASTER.md`'s permission table has no row for it. |
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
