# RULINGS INDEX — every war-room decision, one line each



> **THIS FILE IS THE INDEX. READ IT WHOLE — IT FITS.**
>
> It was ~372,000 characters against a 150,000-character read limit until the
> 2026-08-26 split; the warning that used to stand here said *"you cannot read
> this file in one read — GREP IT."* **Both halves of that are now false, and
> false in the direction that costs:** the index is well under the limit, and
> grep is no longer complete access, because the REASONING moved.
>
> | you want | where it is | how to get it |
> |---|---|---|
> | which ruling, what STATUS, what it decided | **this file** | read it, or grep it |
> | **why** — the argument, the measurements, the reversal path | `docs/foundation/rulings/` | grep **head AND archives** |
>
> ⚠️ **SO THE MANDATED ROUTE IS BOTH, AND IT IS ONE COMMAND:**
>
>     grep -n '<what you want>' docs/foundation/RULINGS.md docs/foundation/rulings/*.md
>
> A grep of this file alone answers *which ruling and what status*. It will not
> find a ruling's reasoning, and — this is the part that bites — **it returns
> zero rather than saying so.** `AGENTS.md` cites `#96(b)`; that string lives in
> an archive, and a head-only grep for it reports nothing at all.
>
> **A ruling you cannot reach is not a weaker ruling, it is an absent one** —
> which is the whole reason this file exists, pointed at its own new shape.

## ⚠️ THE NUMBER-CLAIM PROTOCOL — a number is CLAIMED by LANDING, and only then

**Standing 2026-08-18, after the SECOND collision in one day.**

A row's number is chosen by *reading this file and taking the next one* — which
is a **read-then-write race by construction**. Two actors drafting from the same
snapshot pick the same number and neither can see the other until a merge forces
it. The loop and a supervised session collided on **#124**, then on **#125**,
hours apart.

**THE PROTOCOL, so the third collision follows a rule instead of re-deriving one:**

1. **A NUMBER IS CLAIMED BY LANDING ON `main`, AND ONLY THEN.** An unmerged row
   holds no number; it holds a *proposal*.
2. **ANYTHING UNLANDED REFERS TO ITSELF BY DECISION AND BRANCH, NEVER BY A BARE
   NUMBER** — in INBOX entries, code comments, commit messages, RELAY rows. ⚠️ A
   number is not a stable address until its row lands; **a branch name is.**
3. **ON COLLISION, THE MERGED ROW KEEPS THE NUMBER AND THE UNLANDED ONE
   RENUMBERS.** Renumbering something already on `main` strands every reference
   pointing at it from code, tests and other rows.
4. **THE RENUMBER IS SWEPT BY PREDICATE, NEVER BY MEMORY** —
   `git diff --name-only origin/main...HEAD`, then grep each file for the token.
   The second collision touched **21 references across 15 files**, including one
   living only in a test comment explaining why an upstream gate was removed.

⚠️ **THE COST OF GETTING THIS WRONG IS NOT COSMETIC.** The first collision was
tidy bookkeeping. The second put a pointer to the WRONG DECISION into `INBOX.md`
— the file whose entire purpose is mechanical delivery — and every session
launched in that window was handed it. **A wrong pointer in the delivery
mechanism outranks anything it delivers.**

---

**Read this BEFORE deciding anything ruling-shaped.** One `grep` here is cheaper
than a rediscovery, and rediscovery is the failure this file exists to stop.

> ⚠️ **REDISCOVERY IS A PROCESS SMELL, NOT A VIRTUE.**
>
> On 2026-08-06, T5's tranche 2 concluded that `note_templates` stay
> doctor-scoped and wrote a careful argument for it. **GATE 0.3 had ruled exactly
> that on 2026-08-04**, recorded verbatim at SPEC §4.3. Same answer, same
> reasoning, reached independently — which is reassuring about the reasoning and
> says nothing good about the process.
>
> It cost nothing that time. The next one will not be so lucky, because **the
> failure mode is not duplicated effort — it is CONTRADICTION.** A session that
> cannot see a ruling can reach the opposite conclusion just as confidently, ship
> it, and leave two parts of the system built to incompatible decisions with no
> record that a choice was ever made.

## How to use it

1. **Before deciding**: `grep -i '<topic>' docs/foundation/RULINGS.md`. If a row
   matches, the decision is made — cite it and execute it. Disagreeing with a
   standing ruling is a war-room question, not a session one.
2. **On arrival**: a new ruling APPENDS a row here **in the same commit** that
   records it in full. An index updated later is an index that is already wrong.
3. **The row is a pointer, never the content.** The full text and its reasoning
   live where they live; a summary that drifts from its source is worse than no
   summary. If a row and its target disagree, **the target is right and this file
   is stale** — fix it.
4. ⚠️ **A RULING'S NUMBER IS MINTED BY THE SESSION THAT WRITES IT AND STATED
   INSIDE ITS OWN ROW — it is NOT this file's line number, and it never was.**
   New rows carry a leading `**#N**`. Take `N` as one past the highest `#N` in
   the file, and if the highest row has no `#N`, state the number you chose and
   why in your session report.

   **Why this had to be written down: the two conventions have already
   diverged, in both directions.** Sessions have been deriving a number by
   reading the line their row landed on, and blank separator lines between rows
   made that drift silently:

   | the row | sits at line | is cited as |
   |---|---|---|
   | B4 closing step | 86 | **85 in `RELAY.md` (×2) and 86 in this file** — the same ruling under two numbers |
   | B7 step 1 | 92 | **91**, everywhere |
   | B7 step 2 | 94 | **93**, everywhere |

   ⚠️ **THE B4 ROW IS THE ONE THAT MATTERS: a single decision is reachable under
   two different names, so a `grep` for one of them finds nothing and reads as
   "no ruling exists".** That is precisely the CONTRADICTION failure this file
   exists to prevent, arriving through its own index.

   **History is deliberately NOT renumbered.** Existing citations are correct
   relative to whatever each session minted, and rewriting them would break the
   references that already work while fixing nothing that is ambiguous today.
   The cure is forward-only: **state the number in the row**, so a `grep` for
   `#N` lands on exactly one place and the next session cannot collide by
   counting lines.

## The index

<!-- RULINGS-INDEX-BEGIN — generated by scripts/lib/rulings-index.py; do not hand-edit -->

> **Generated by `scripts/lib/rulings-index.py`. Do not hand-edit between the
> markers — the generator REPLACES this block, so a hand edit does not survive.**
>
> ⚠️ **A ROW IS A POINTER, NEVER THE RULING.** If a row and its archived body
> disagree, **the body is right and the row is the defect** — and the fix is to
> correct the body and re-run this, never to edit the row.
>
> **THE STATUS COLUMN EXISTS SO A GREP RETURNS A TRUE COUNT.** Grep the PIPED
> form of the token — a bare word is also counted where it appears inside
> somebody's prose, and the piped form is only ever a row:
>
>     grep -c '[|] PROVISIONAL [|]' docs/foundation/RULINGS.md
>
> ⚠️ **The example above writes the pipes as `[|]` DELIBERATELY.** Written
> literally it would be a row-shaped string inside the index, and this
> generator's own post-write census would count it — a probe that matches
> itself. It caught exactly that on its first run.
>
> ⚠️ **AND THE HEAD IS NOT THE WHOLE FILE.** A grep for a ruling's REASONING
> must read the archives too:
>
>     grep -n '<what you want>' docs/foundation/RULINGS.md docs/foundation/rulings/*.md
>
> The head answers *which ruling and what status*. The archive answers *why*.

**130 rulings.** **31 OWNER-RULING** · **5 RATIFIED** · **43 PROVISIONAL** · **1 SUPERSEDED** · **50 RECORDED**

| date | # | status | ruling — the POINTER, never the prose | full body |
|---|---|---|---|---|
| 2026-08-04 | — | RECORDED | GATE 0.1 — the 12 MEDDOC_PRO-only accounts | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-05 | — | RECORDED | GATE 0.1 veto — the same 12 accounts | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-04 | — | RECORDED | GATE 0.2 — cross-app redirect users | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-04 | — | RECORDED | GATE 0.3 — note templates | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-04 | — | RECORDED | GATE 0.4 — money | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-04 | — | RECORDED | GATE 0.5 — Resend | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-05 | — | RECORDED | Exit gate 1 — worker.ts:983 read-after-write | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-05 | — | RECORDED | Exit gate 3 — audit_logs as an S4c exclusion | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-05 | — | RECORDED | T3 derivation | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | T4-b schema drift — the prescribed fix | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | T4 blocker | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | §4.1a — WHO MAY SIGN | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | §4.1b — WHO MAY READ | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | §4.1c — the interim posture | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | T6 role vocabulary | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | T6 backfill derivation | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | SUPER_ADMIN's tenant bypass | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | A migration must not DOWNGRADE anybody | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | Which actions are role-gated | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | No-downgrade applies to REACTIVATION | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | Structural-only prod verification | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | Platform-global note_templates | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | The fail-closed rule's exclusions | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | The shape for owner-ruled PROD mutations | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | — | RECORDED | T5 tranche 2 | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | T7 index-name drift | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | F-TYPE's $transaction class | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | confidenceScores Json null | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | — | RECORDED | T2's repair is DONE, not pending | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | — | RECORDED | validateSession FAILS CLOSED | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | — | RECORDED | B0 Q1 — mocked ai_calls rows | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | — | RECORDED | A provenance column's DEFAULT must never be the TRUSTED value | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | — | RECORDED | B0 Q2 — usage rows MIRROR VENDOR CALLS | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | — | RECORDED | B0 Q3 — the mock stays CONTENT-SENSITIVE | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | — | RECORDED | THE REAPING MODEL — the loop LISTS, a supervised session DESTROYS | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | — | RECORDED | The five @quillmd-test.local prod accounts — CONTAIN, don't delete | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | — | RECORDED | B1-b — api_usage_events.requestId goes NULLABLE with a provenance-tied CHECK, in TWO STEPS | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | — | RECORDED | The sizing data is GENERATED, not awaited | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | — | RECORDED | A push to a branch with required runs MUST check in-flight BY COMMIT first | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | — | RECORDED | FIX-THEN-SMOKE — the capture gap closes BEFORE any measurement | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | — | RECORDED | The Anthropic balance probe is APPROVED — one call, before the smoke | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | — | RECORDED | runStaleVisitCleanup — examine it BEFORE it stops being a no-op | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | — | RATIFIED | B2 — WHICH FAILURE BRANCHES METER, AND WHICH TABLE IS THE BILLING SOURCE | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | — | RECORDED | The durable meter's PROVENANCE REGIME begins at B0-a — no pre-regime call is ever INSERTED into… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | — | PROVISIONAL | B3 — HOW A RATE IS SHAPED, WHEN IT STARTS, AND WHAT AN UNPRICED CALL COSTS | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | — | PROVISIONAL | B4 step 1 — THE DEEPGRAM METER LABELS BECOME OBSERVATIONS, ON NEW ROWS ONLY | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | — | PROVISIONAL | B4 step 2 — A STAGE-LEVEL MOCK SHORT-CIRCUIT SITS BELOW THE METER, AND THE ENTAILMENT FIXTURE B… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | — | RECORDED | A DEACTIVATED CREDENTIAL IS REPLACED ONLY WHEN THE CAPABILITY IT EXERCISES STILL EXISTS — refin… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | — | PROVISIONAL | B4 step 3 — THE judge STAGE METERS UNDER MOCK, AND THE JUDGEMENT IS STILL NOT FABRICATED | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | — | PROVISIONAL | B4 closing step — A PERMITTED ZERO IS NOT A PASS, AND TWO MORE HARDCODED OPERATION LABELS BECOM… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | — | PROVISIONAL | B4's closure — THE ANCHORED DRAFT IS A DIFFERENT NOTE, AND ITS SPANS ARE DERIVED FROM THE TRANS… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | — | PROVISIONAL | B5 — THE LEDGER'S APPEND-ONLY GUARANTEE HAS EXACTLY ONE HOLE, AND THE HOLE WAS ALREADY RULED EL… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | — | PROVISIONAL | B6 — WHAT AN UNPRICEABLE VISIT COSTS, AND WHY THE WRITER SHIPS UNWIRED | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | — | PROVISIONAL | B7 — AN INBOUND EVENT CARRIES ITS OWN MODE, SO assertProdDatabase() IS THE WEAKER GUARD | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | #93 | PROVISIONAL | B7 step 2 — THE PAYING PARTY IS THE SESSION'S, THE MODE RULE MIRRORS OUTWARD, AND THE DOOR OPEN… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | #94 | PROVISIONAL | B8 step 1 — ADMISSION JUDGES THE MONEY A DEBIT CAN REACH, AND A BALANCE THAT DISAGREES WITH ITS… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | #95 | PROVISIONAL | B8 step 2 — THE DEBIT AND THE BLOCK LAND TOGETHER AND SHIP INERT, AND THE METER BECOMES OBSERVA… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | #96 | RATIFIED | B7 step 3a — THE PROMO GRANT NEEDED A DRAW ORDER FIRST, AND THE REVERSIBLE HALF GOES FIRST | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | #97 | PROVISIONAL | B7 step 3b — A GRANT IS A PROPERTY OF BECOMING A PRACTICE, NOT AN EVENT THAT HAPPENED ONCE | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | #99 | OWNER-RULING | B7 STEP 3c IS AUTHORIZED IN FULL BY THE OWNER, AND THE POPULATION QUESTION IS ANSWERED BY REMOV… · amends #99(e) | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | #100 | OWNER-RULING | THREE RATIFICATIONS, AND THE PUSH RULE STOPS BEING A RULE · amends #100(b) | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-12 | #101 | OWNER-RULING | THE MERGE SIDE GETS THE SAME MECHANISM, AND SCRATCH GETS A NAME | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-12 | #102 | OWNER-RULING | A RULED MUTATION GETS THE DEPLOY'S DECLARATION GATE, AND "EXISTS" BECOMES "WAS COMMITTED" | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | #103 | OWNER-RULING | THE INBOX: AN INTER-SESSION CHANNEL THAT DID NOT EXIST, AND THE ONE THING IT MUST NEVER CARRY | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-12 | #98 | PROVISIONAL | B8's QA BEHAVIOURAL PROOF — THE DEBT THAT WAS CARRIED FOUR TIMES, AND THE TWO SHIPPED DEFECTS I… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | #104 | PROVISIONAL | B8 step 3 — A FAILED VISIT IS FREE, AND THE ITEM SHIPS THE MEASUREMENT INSTEAD OF THE CHARGE | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | #105 | PROVISIONAL | B8 step 3c — A PERMANENT FAILURE IS DISCARDED, SO "fail-fast" STOPS BEING A WISH | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | #106 | OWNER-RULING | CUSTOM-TEMPLATE FIDELITY: THE STATICS ARE ASSEMBLED, THE FILE IS KEPT, AND THE FALLBACK GOES LO… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | #106 | OWNER-RULING | (g) — STATICS ARE GUARDED AT THE OUTPUT, NOT AT THE LAYER THAT WROTE THEM | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | #107 | RECORDED | #106's DIAGNOSIS IS CORRECTED: THE PARAPHRASE WAS OURS, NOT THE MODEL'S | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | #108 | RECORDED | CI'S PIPELINE SUITES RUN IN THE PRODUCTION FLAG UNIVERSE — 🔵 ORDERED, BUILT AFTER RC-2 | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | #109 | OWNER-RULING | THE PRESCRIPTION SAFETY SURFACE IS DELETED, AND THE GATE COMES OUT WITH IT | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | #110 | RECORDED | THE SPECIALTY VOCABULARY BUNDLE MISSES THE SPECIALTIES THAT NEED IT — 🔵 OPEN ITEM, MEASURED, NO… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | #112 | OWNER-RULING | A NOTE'S OWN LIST NUMBERS ARE CONTENT, NOT STYLING | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | #113 | OWNER-RULING | ONE BUILDER, ONE TRUTH: THE PDF EXPORT CONVERGES AND generateVisitPdf RETIRES | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | #114 | RECORDED | THE SIGNED-VIEW DIVERGENCE IS UNEXPLAINED; BOTH PROPOSED MECHANISMS WERE WRONG — 🔵 OPEN, MEASUR… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | #117 | OWNER-RULING | THE ATTESTATION FOOTER SHIPS WITH F3, AND DRAFT MARKING IS RESTORED | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | #116 | RECORDED | (c)-CORRECTED — THE GOTENBERG COST IS EVERY NON-SIDECAR ENVIRONMENT, NOT JUST A DOWN SIDECAR · amends #116(c) | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | #109 | OWNER-RULING | (a) — #109's SCOPE IS AMENDED: THE MEDICATION LIST IS RESTORED, READ-ONLY | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-14 | #111 | RECORDED | AUTHORIZATION TRAVELS OWNER → SESSION DIRECTLY, NEVER THROUGH A PEER RELAY | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | #115 | PROVISIONAL | THE VISIT DATE IS THE ENCOUNTER'S DATE; signedAt BELONGS ONLY IN THE SIGNATURE CHROME | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | #115 | PROVISIONAL | b — DD: AND DT: ARE DICTATION AND TRANSCRIPTION DATES, AND #115 MADE THEM CONTRADICT THE FORM | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | #116 | PROVISIONAL | F3's CENSUS FOUND FIVE CALLERS WHERE #113 NAMED ONE, AND TWO OF THEM RENDER A SIGNED NOTE TO FE…| [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | #118 | PROVISIONAL | RULING #117 CONTRADICTS ITSELF TWICE; CLAUSE (a) GOVERNS, THE SHIPPED STRING GOVERNS, AND #117'… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | #116 | PROVISIONAL | b — SITE 3 HAD A SECOND sizeBytes CONSUMER, IN AN AUDIT ROW, MEASURING A DOCUMENT THAT IS NEVER…| [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-16 | #119 | PROVISIONAL | THE QUILLMD WATERMARK IS NOT RESTORED ON THE CONVERGED PDF, AND ITS LOSS IS DECLARED RATHER THA… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-16 | #120 | PROVISIONAL | THE VANISHED VISIT'S ACTOR IS THE BullMQ CLEANUP CRON, AND THE DEFECT IS THAT RETENTION DELETES… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-16 | #121 | OWNER-RULING | F10's ACCEPTANCE CRITERIA, SET BEFORE THE FIX IS DESIGNED SO IT IS NOT GUESSED AT | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-17 | #122 | PROVISIONAL | WHEN THE ARCHIVE RENDER BOUND ENGAGES, THE DOCTOR GETS A NAMED NOTE, NOT A SHORTER ARCHIVE | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-17 | #123 | OWNER-RULING | E/M DOES NOT BELONG ON A PROCEDURE OR OPERATIVE NOTE, AND THE EXPORT'S E/M BLOCK NEVER GOT R4b'… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-17 | #124 | PROVISIONAL | A REPO-WIDE RUNS-API OUTAGE MUST NOT SHUT THE MERGE AND PUSH DOORS, AND THE FALLBACK'S FLOOR IS… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-18 | #125 | PROVISIONAL | F12 SPLITS: THE POLICY HALF SHIPS ALONE, AND THE SKIN HALF IS PARKED ON ONE FACT FROM THE OWNER | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-18 | #126 | PROVISIONAL | THE NOTE-SHAPE SUPPRESSION MUST NOT HANG ON A LIVE RELATION, AND THE CLASSIFIER NEEDS THE OFFIC… · amends #126(b) | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-17 | #127 | OWNER-RULING | AUTO-CERTIFICATION BY AI IS THE DEFAULT PATH, AND THE MODEL NEVER ASSERTS LATERALITY | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-18 | #128 | PROVISIONAL | THE COMPUTE LAYER STOPS WRITING AN OFFICE E/M ONTO AN OPERATIVE NOTE, AND THE INCOMPLETENESS DE… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | #129 | PROVISIONAL | A RETIRED TEMPLATE DOES NOT OVERRULE THE DOCUMENT BEING SIGNED | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | #130 | PROVISIONAL | THE OFFICE COUNTERWEIGHT ACCEPTS SPELLINGS OF THE FOUR SOAP CONCEPTS AND REFUSES SYNONYMS FOR T… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | #131 | PROVISIONAL | playwright install --with-deps IS SPLIT INTO ITS TWO HALVES AT ALL FOUR SITES, BECAUSE ONE STEP… · amends #131(b) | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | #131 | PROVISIONAL | (b) — THE INSTRUMENT ANSWERED ITS OWN QUESTION ON ITS FIRST RUN, SO THE RULING ABOVE IS CORRECT…| [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | #132 | PROVISIONAL | THE NO-PROGRESS KILL SWITCH MEASURES THE LEDGER ON origin/main, NOT IN THE SHARED WORKING TREE | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | #131 | PROVISIONAL | (c) — THE BOUNDED WAIT FIRED ITS OWN PREDICTION: THE APT TIMEOUT IS INEFFECTIVE FOR #739, THE M…| [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-20 | #133 | PROVISIONAL | THE DOCX RENDERS EVERY MARKDOWN HEADING DEPTH, AND THE GATE THAT SHOULD HAVE CAUGHT THIS WAS VA… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-20 | #134 | OWNER-RULING | A DEPLOY REFUSES A COMMIT ITS OWN GATE HAS NOT SEEN, AND FAILS CLOSED WHEN IT CANNOT TELL | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-20 | #135 | PROVISIONAL | F5-d: THE GSV at the SFJ REFUSAL IS A NUMERIC-TEXT MISMATCH, NOT TOKEN OVERLAP — THE FILED SUSP… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-20 | #136 | PROVISIONAL | F5-d(b): THE SHARED DERIVATION SHIPS AS A TIGHTENING, AND THE BRIDGE REFUSES WHAT IT CANNOT WRI… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-21 | #137 | OWNER-RULING | ROLLBACK TAGS ARE PRUNED BY NAME, NEVER BY -a, AND PREFLIGHT'S PRESCRIBED SWEEP IS PERMANENTLY… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-21 | #138 | OWNER-RULING | f5c-refute IS PLAIN-rm SCRATCH, AND THE PERMISSION DENIAL WAS NOT A JUDGEMENT | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-21 | #139 | PROVISIONAL | F5-i PART 1 SPLITS INTO 1a / 1b, AND 1a IS TAKEN NOW | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-22 | #140 | OWNER-RULING | THE LABEL COLUMN IS RESOLVED FROM EVIDENCE, NOT GUESSED FROM TEXT | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-23 | #141 | PROVISIONAL | A CAPTION IS VALIDATED BY SHAPE ACROSS A PARAGRAPH BREAK, AND BY SECTION UNIFORMITY; THE ADJACE… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-23 | #142 | OWNER-RULING | F24 DOES NOT CLOSE ON THE TABLE-BOUND HALF; THE ACCEPTANCE SENTENCE MEANS WHAT IT SAYS | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | #144 | OWNER-RULING | THE BOUND IDENTITY WIDENS TO NOTE + OVERRIDES; THE FRESHNESS GATES ARE NEVER LOOSENED · amends #144(d) | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | #143 | PROVISIONAL | A FORM CONTROL IS ADDRESSED BY A SERVER-ISSUED ORDINAL; AND A FILL INPUT THAT IS NOT THE NOTE M… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | #145 | PROVISIONAL | THE PLACEHOLDER IS EXCLUDED WITHOUT RENUMBERING, AND THE EXCLUSION IS THREE LAYERS - 🟡 PROVISIO… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | #146 | SUPERSEDED | A CANCELLED RUN THAT A RE-RUN ALREADY REPLACED IS NOT A FAILURE, AND THE UNIT OF A CITATION IS… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | #147 | OWNER-RULING | F24 CLOSES AT 75/80. THE ACCEPTANCE IS RESTATED AS *EVERY FIELD THE VALIDATOR CAN DEFEND*; THE… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-25 | #148 | RATIFIED | F8 SLICES. S1 IS THE DECISION SUBSTRATE, IT IS DELIBERATELY UNREACHABLE, AND THE CONTRACT'S TAB… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-25 | #149 | RATIFIED | THE AMBER RULE GETS ITS SUBSTRATE; THE FOUR DROP EXITS STAY FOUR; AND THE ALLOWLIST IS NOT ALLO… · amends #149(b), #149(e) | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-25 | #150 | OWNER-RULING | AUTHORITY LIVES IN EXACTLY ONE FILE. AGENTS.md § STANDING AUTHORITY IS THE SINGLE SOURCE FOR WH… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-26 | #151 | PROVISIONAL | (PROPOSED — unlanded, refer to it as feat/f29-orphan-branch-sweep until it lands) — A GRANT RUL… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-27 | #152 | PROVISIONAL | THE SIGNED DOCUMENT CARRIES THE LEVEL THE DOCTOR ATTESTED, AND THE FREEZE IS GATED ON emApplies… | [`2026-08-27.md`](rulings/2026-08-27.md) |
| 2026-08-27 | #154 | RATIFIED | THE ICD REJECTION REASON IS A CLOSED VOCABULARY OF TOKENS, NEVER FREE TEXT | [`2026-08-27.md`](rulings/2026-08-27.md) |
| 2026-08-27 | #153 | OWNER-RULING | THE CODING SURFACE LIVES ON THE VISIT PAGE, VIA THE SMALLEST NAVIGATION PRIMITIVE THAT WORKS | [`2026-08-27.md`](rulings/2026-08-27.md) |
| 2026-08-27 | #155 | OWNER-RULING | THE TEN ALREADY-SIGNED RECORDS STAY AS SIGNED; THE GAP IS MADE VISIBLE WITHOUT TOUCHING A BYTE | [`2026-08-27.md`](rulings/2026-08-27.md) |
| 2026-08-28 | #156 | OWNER-RULING | SHAPE-AWARE VERIFICATION ENCOUNTERS: THE CERTIFICATION ENGINE LEARNS A SELF-TEST PER TEMPLATE S… | [`2026-08-28.md`](rulings/2026-08-28.md) |
| 2026-09-02 | #162(c) | OWNER-RULING | SUPERSEDED by #164 then #165 — the renderer fix rides the PR; emptiness is byte-equality, never parsing | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-02 | #163 | OWNER-RULING | SUPERSEDED by #164 — nulls left unpatched; hygiene moves to compile-time refuse-and-flag | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-02 | #164 | OWNER-RULING | SUPERSEDED by #165 — the blank proof is a counting rule, not a parser | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-02 | #165 | OWNER-RULING | **STANDING** — bound the edit with the document's own element; prove it with bytes you wrote | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-02 | #168 | OWNER-RULING | **STANDING** — the run shell is skeleton; content generators fail closed on the COUNT — #168(a) numbering, #168(b) selections | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-02 | #167 | OWNER-RULING | **STANDING** — rule 1 v3: STRUCTURE-KEEP, fail-closed; delete every node that is not skeleton | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-03 | #175 | OWNER-RULING | **STANDING — CLOSING SET** — one list, the loud half built, the arms swept as sets | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-04 | #176 | OWNER-RULING | **STANDING — THE ADMIN ARC IS PINNED TO THE BOARD, AND BILLING IS DEFERRED TO A SESSION THAT DOES NOT EXIST YET** | [`2026-09-04.md`](rulings/2026-09-04.md) |
| 2026-09-04 | #177 | OWNER-RULING | **STANDING** — the pricing unit is the provider SEAT, and the welcome credit follows it | [`2026-09-04.md`](rulings/2026-09-04.md) |
| 2026-09-04 | #178 | OWNER-RULING | **STANDING — ADDENDUM to #177** — the margin multiplier is a CONFIGURABLE SETTING, never a constant | [`2026-09-04.md`](rulings/2026-09-04.md) |
| 2026-09-03 | #174 | OWNER-RULING | **STANDING — TERMINAL** — the compiler admits only controls it fully understands | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-03 | #173 | OWNER-RULING | **STANDING — ARC-ENDING** — the numbering-eligibility guard is DELETED; a proof is scoped to what the prover does | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-03 | #172 | OWNER-RULING | **STANDING** — R1 conforms to its noun; the table-style layer resolves ONE HOP; the arms get a mechanism | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-02 | #171 | OWNER-RULING | **STANDING** — the escalation widens by one class; two bindings leave the slice | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-02 | #170 | OWNER-RULING | **STANDING** — the `pPr` inert-allowlist, and the deletion it buys | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-02 | #169 | OWNER-RULING | **STANDING** — blank credit ONLY by positive proof of no numbering | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-09-04 | #179 | OWNER-RULING | **STANDING** — ROS at SYMPTOM granularity: a closed lexicon, enforced by the schema, and no text matching anywhere | [`2026-09-04.md`](rulings/2026-09-04.md) |
| 2026-09-05 | #191 | OWNER-RULING | **STANDING** — the SCAFFOLDED-FIELD policy: `unmentionedPolicy` on a control that ships with default content | [`2026-09-05-191.md`](rulings/2026-09-05-191.md) |
| 2026-09-05 | #192 | OWNER-RULING | **STANDING — amends #191's keep half** — KEEP is an EXPLICIT per-field declaration, never inferred from content | [`2026-09-05-192.md`](rulings/2026-09-05-192.md) |
| 2026-09-05 | #193 | OWNER-RULING | **STANDING — amends #192** — KEEP is never MODEL-AUTHORED and never AUTO-CONFIRMED | [`2026-09-05-193.md`](rulings/2026-09-05-193.md) |
| 2026-09-05 | #194 | OWNER-RULING | **STANDING — supersedes the KEEP half of #191/#192/#193** — the machine never prints an undictated default · amends #194(a) | [`2026-09-05-194.md`](rulings/2026-09-05-194.md) |
| 2026-09-06 | #198 | OWNER-RULING | **STANDING — amends §2.5; RENUMBERED from #188** — a MIGRATION-carrying deploy requires the STRICT declaration | [`2026-09-06-198.md`](rulings/2026-09-06-198.md) |
| 2026-09-05 | #189 | OWNER-RULING | **STANDING** — the configured model id is validated AT STARTUP | [`2026-09-05-189-190.md`](rulings/2026-09-05-189-190.md) |
| 2026-09-05 | #190 | OWNER-RULING | **STANDING — BLOCKING** — the FAN-OUT adversarial pass over #179 is OWED | [`2026-09-05-189-190.md`](rulings/2026-09-05-189-190.md) |
| 2026-09-06 | #195 | OWNER-RULING | **STANDING** — OWNER IS NOT EXCLUSIVE: a practice may have more than one owner, and an owner may create another | [`2026-09-06-195.md`](rulings/2026-09-06-195.md) |
| 2026-09-06 | #196 | OWNER-RULING | **STANDING (ADMIN-2)** — the SUBDOMAIN MODEL: `<practice>.quillmd.com`, per-subdomain HTTP-01, apex filed as ADMIN-2b | [`2026-09-06-196-197.md`](rulings/2026-09-06-196-197.md) |
| 2026-09-06 | #197 | OWNER-RULING | **STANDING (ADMIN-3)** — specialty is a MODEL, not a filter: a `Practice` property selecting prompts, vocabulary and template defaults | [`2026-09-06-196-197.md`](rulings/2026-09-06-196-197.md) |
| 2026-09-04 | #183 | OWNER-RULING | **STANDING — BLOCKING-CLASS** — the CANON INDEX moves out of `AGENTS.md` into `docs/canon/INDEX.md` | [`2026-09-04-183.md`](rulings/2026-09-04-183.md) |
| 2026-09-05 | #184 | OWNER-RULING | **STANDING** — the COMPOSED deploy judgement: judge the union, every row names its author | [`2026-09-05-184-186.md`](rulings/2026-09-05-184-186.md) |
| 2026-09-05 | #186 | OWNER-RULING | **STANDING** — two passenger fixes + three CI mechanisms | [`2026-09-05-184-186.md`](rulings/2026-09-05-184-186.md) |
| 2026-09-05 | #185 | OWNER-RULING | **STANDING (T2)** — the diagnosis categoriser: threshold 0.90 SPECIFICATION-DERIVED, the Z-code rule, five states on two axes, auto-accept at sign time | [`2026-09-05-185.md`](rulings/2026-09-05-185.md) |
| 2026-09-05 | #187 | OWNER-RULING | **STANDING (T2 close-out)** — the provenance word, the section order, #972's hold, and two fixes | [`2026-09-05-187.md`](rulings/2026-09-05-187.md) |
| 2026-09-05 | #188 | OWNER-RULING | **STANDING (T4)** — the five clipboard formats survive, the safety caption stays, and the referring physician becomes its own item | [`2026-09-05-188.md`](rulings/2026-09-05-188.md) |
| 2026-09-04 | #181 | OWNER-RULING | **STANDING** — sign-out fails closed; the client never sends an empty CSRF token; sign-in refuses rather than minting an unrevocable session | [`2026-09-04-181-182.md`](rulings/2026-09-04-181-182.md) |
| 2026-09-04 | #182 | OWNER-RULING | **STANDING — amends #181(d)** — cannot-tell is neither invalid nor fine; doors enumerated from the tree | [`2026-09-04-181-182.md`](rulings/2026-09-04-181-182.md) |
| 2026-09-02 | #166 | OWNER-RULING | **STANDING** — `shred` is granted to a SUPERVISED session, scoped BY TARGET | [`2026-09-02.md`](rulings/2026-09-02.md) |
| 2026-08-30 | #157 | OWNER-RULING | ⚠️ FINAL FORM #157(d), 2026-08-31 — A DENIED NARRATIVE ALWAYS RENDERS BLANK; no text heuristic… | [`2026-08-30.md`](rulings/2026-08-30.md) |
| 2026-08-30 | #158 | OWNER-RULING | THE RE-ATTESTATION RETARGETS TO THE LIVE TEMPLATE; THE DEAD TEMPLATE'S ROWS ARE RECORDED, NEVER… | [`2026-08-30.md`](rulings/2026-08-30.md) |
| 2026-08-30 | #159 | OWNER-RULING | THE CERTIFICATION SEQUENCE IS ORDERED, AND THE FILL FLOOR NEVER LOWERS WITHOUT ITS OWN RULING | [`2026-08-30.md`](rulings/2026-08-30.md) |
| 2026-08-30 | #160 | OWNER-RULING | THE LOOP'S DECOMMISSION IS A TRACKED AMENDMENT; AN UNTRACKED FILE AND A PASTE CACHE ARE NOT A R… | [`2026-08-30.md`](rulings/2026-08-30.md) |
| 2026-08-30 | #161 | OWNER-RULING | PR #915 MERGES ON main's e2e COMPLETING — ⚠️ OPERATIONAL, one merge, NOT standing | [`2026-08-30.md`](rulings/2026-08-30.md) |
| 2026-09-04 | #180 | OWNER-RULING | **THE ALLOWLIST EXIT'S REASON SPLITS IN TWO** — a header refusal and a fabrication refusal are different things to tell a doctor | [`2026-09-04.md`](rulings/2026-09-04.md) |
| 2026-09-06 | #199 | OWNER-RULING | **STANDING — amends the §2.5 ROWS gate (PR #1022)** — the rows gate gets its OWN purpose-named scope predicate, and a PR that did nothing wrong cannot go red | [`2026-09-06-199-200.md`](rulings/2026-09-06-199-200.md) |
| 2026-09-06 | #200 | OWNER-RULING | **STANDING (ADMIN-5)** — #195 binds the INVARIANT and its PROOF, never the MECHANISM | [`2026-09-06-199-200.md`](rulings/2026-09-06-199-200.md) |
| 2026-09-06 | #201 | OWNER-RULING | **STANDING** — `compilerVersion` BUMPS and the active compiled versions get a RULED RECOMPILE, so REVIEW-DEFAULTS can fire at all | [`2026-09-06-201-203.md`](rulings/2026-09-06-201-203.md) |
| 2026-09-06 | #202 | OWNER-RULING | **STANDING** — a per-field policy toggle MUST NOT de-certify a template; the current behaviour is the DEFECT | [`2026-09-06-201-203.md`](rulings/2026-09-06-201-203.md) |
| 2026-09-06 | #203 | OWNER-RULING | **STANDING** — `KEY_VERSION` v6 → v7 lands in the SAME COMMIT as the #1018 fix | [`2026-09-06-201-203.md`](rulings/2026-09-06-201-203.md) |
| 2026-09-06 | #204 | OWNER-RULING | **STANDING — supersedes `432bd450`'s MECHANISM, not its diagnosis** — the insert DOOR consults the PER-VISIT RESOLUTION | [`2026-09-06-204-206.md`](rulings/2026-09-06-204-206.md) |
| 2026-09-06 | #205 | OWNER-RULING | **STANDING (ADMIN-5)** — the harness must GENUINELY RACE, and the negative control must FAIL under sequential execution | [`2026-09-06-204-206.md`](rulings/2026-09-06-204-206.md) |
| 2026-09-06 | #206 | OWNER-RULING | **STANDING** — the reap wrapper REFUSES to remove another session's LIVE lens sandbox | [`2026-09-06-204-206.md`](rulings/2026-09-06-204-206.md) |
| 2026-09-07 | #207 | OWNER-RULING | **STANDING** — `#179(6)` HAS CONTENT, and the PROJECTOR is wrong first | [`2026-09-07-207-209.md`](rulings/2026-09-07-207-209.md) |
| 2026-09-07 | #208 | OWNER-RULING | **STANDING — BLOCKING #985** — `conceptScope` is a MAPPING, not a RENDER POLICY, so #192/#193 and #179(3) do not collide | [`2026-09-07-207-209.md`](rulings/2026-09-07-207-209.md) |
| 2026-09-07 | #209 | OWNER-RULING | **STANDING** — the reconstruction IS the regeneration; **no re-upload** | [`2026-09-07-207-209.md`](rulings/2026-09-07-207-209.md) |
| 2026-09-07 | #210 | OWNER-RULING | **STANDING** — the LAST-OWNER INVARIANT is a property of the DATA, not of one door | [`2026-09-07-210-214.md`](rulings/2026-09-07-210-214.md) |
| 2026-09-07 | #211 | OWNER-RULING | **STANDING** — PR **#1018** gets a **FOURTH** round, on the round-three fixes | [`2026-09-07-210-214.md`](rulings/2026-09-07-210-214.md) |
| 2026-09-07 | #212 | OWNER-RULING | **STANDING** — PR **#1026** gets one more pass **AFTER the trigger lands**, because the trigger changes what the harness must prove | [`2026-09-07-210-214.md`](rulings/2026-09-07-210-214.md) |
| 2026-09-07 | #213 | OWNER-RULING | **STANDING — amends #206** — the sandbox marker is **session id + start-time, NEVER `$$`** | [`2026-09-07-210-214.md`](rulings/2026-09-07-210-214.md) |
| 2026-09-07 | #214 | OWNER-RULING | **STANDING** — `shred` is DELIBERATELY denied; the granted door is `scripts/reap-session-scratch.sh` | [`2026-09-07-210-214.md`](rulings/2026-09-07-210-214.md) |

| 2026-09-07 | #215 | OWNER-RULING | **STANDING — FILED, NOT BUILT** — field identity salts with a CANONICAL **CONTENT** sha (the OPC parts' bytes), never the zip container | [`2026-09-07-215-218.md`](rulings/2026-09-07-215-218.md) |
| 2026-09-07 | #216 | OWNER-RULING | **STANDING** — a SCAFFOLDED control is always `narrative_text` | [`2026-09-07-215-218.md`](rulings/2026-09-07-215-218.md) |
| 2026-09-07 | #217 | OWNER-RULING | **STANDING** — `conceptScope` gets its COLUMN, WRITER and READ-BACK, as its own ordered change **before the form certifies** | [`2026-09-07-215-218.md`](rulings/2026-09-07-215-218.md) |
| 2026-09-07 | #218 | OWNER-RULING | **STANDING** — the de-slug happens at EMISSION, and the verbatim NEVER receives an identifier | [`2026-09-07-215-218.md`](rulings/2026-09-07-215-218.md) |
| 2026-09-07 | #219 | OWNER-RULING | **STANDING — PROTOCOL AMENDMENT** — a number is claimed by the LEDGER ROW THAT LANDS FIRST; **a branch is a claim, a merged row is a fact** | [`2026-09-07-219-224.md`](rulings/2026-09-07-219-224.md) |
| 2026-09-07 | #220 | OWNER-RULING | **STANDING** — the CONSTRAINT-TRIGGER departure is **RATIFIED**, and so are the three closures the pass forced | [`2026-09-07-219-224.md`](rulings/2026-09-07-219-224.md) |
| 2026-09-07 | #221 | OWNER-RULING | **STANDING** — **ONE PREDICATE FOR "ABLE OWNER"**, derived by all three readers from a SINGLE CONSTANT | [`2026-09-07-219-224.md`](rulings/2026-09-07-219-224.md) |
| 2026-09-07 | #222 | OWNER-RULING | **STANDING** — the SIX ZERO-OWNER PRACTICES are an ADMIN data-hygiene item, and the trigger must never refuse a write that does not REDUCE `≥1 → 0` | [`2026-09-07-219-224.md`](rulings/2026-09-07-219-224.md) |
| 2026-09-07 | #223 | OWNER-RULING | **STANDING** — **#1018 gets a FIFTH round**, on the round-four fixes; **#1036 stays DRAFT** until its remaining 13 findings close and a clean round follows | [`2026-09-07-219-224.md`](rulings/2026-09-07-219-224.md) |
| 2026-09-07 | #224 | OWNER-RULING | **STANDING** — #214 is **NOT DISCHARGEABLE** by the granted door, and declining to route around it was CORRECT | [`2026-09-07-219-224.md`](rulings/2026-09-07-219-224.md) |
| 2026-09-07 | #225 | OWNER-RULING | **STANDING** — C SHIPS; the window is closed by **SEQUENCING**, not accepted open | [`2026-09-07-225.md`](rulings/2026-09-07-225.md) |
| 2026-09-07 | #226 | OWNER-RULING | **STANDING — CLASS (d), DECIDED** — the six test practices and their seven inactive users are **ARCHIVED**, as a RULED MUTATION | [`2026-09-07-226-229.md`](rulings/2026-09-07-226-229.md) |
| 2026-09-07 | #227 | OWNER-RULING | **STANDING** — the *"mentioned, not varied"* residual closes by **DECLARATION, not judgement** | [`2026-09-07-226-229.md`](rulings/2026-09-07-226-229.md) |
| 2026-09-07 | #228 | OWNER-RULING | **RATIFIED** — the batch's landed work stands | [`2026-09-07-226-229.md`](rulings/2026-09-07-226-229.md) |
| 2026-09-07 | #229 | OWNER-RULING | **STANDING** — both PRs stay DRAFT; **round five**, then they ride the next composed deploy **with their rows** | [`2026-09-07-226-229.md`](rulings/2026-09-07-226-229.md) |
| 2026-09-07 | #233 | OWNER-RULING | **RATIFIED** — the retraction (**rewritten, not deleted**), the SSI measurement with its positive control, #1042's harness isolation, and the attribution correction | [`2026-09-07-233-236.md`](rulings/2026-09-07-233-236.md) |
| 2026-09-07 | #234 | OWNER-RULING | **STANDING** — #227's false declaration is fixed by **VARYING**, never by re-declaring | [`2026-09-07-233-236.md`](rulings/2026-09-07-233-236.md) |
| 2026-09-07 | #235 | OWNER-RULING | **STANDING** — the pre-existing sign/override race is its own clinical-path item, **SIGN-PTR-1**, NOT folded into #1018 | [`2026-09-07-233-236.md`](rulings/2026-09-07-233-236.md) |
| 2026-09-07 | #236 | OWNER-RULING | **STANDING** — the order: #1036's round → fix #1018's survivors → **push ONCE** → draft on clean rounds → the composed deploy | [`2026-09-07-233-236.md`](rulings/2026-09-07-233-236.md) |
| 2026-09-07 | #237 | OWNER-RULING | **RATIFIED** — the batch's landed work: #233–#236 recorded first, `gate-ruling-row-identity` and the #194 drift it found, #234 as built, the five #1018 closures, the one push | [`2026-09-07-237-242.md`](rulings/2026-09-07-237-242.md) |
| 2026-09-07 | #238 | OWNER-RULING | **STANDING** — the `practiceId` comparison lands on the UPDATE arm, **closed in the DATABASE**, and it is FIRST because it is the only remaining door | [`2026-09-07-237-242.md`](rulings/2026-09-07-237-242.md) |
| 2026-09-07 | #239 | OWNER-RULING | **STANDING** — **ONE predicate for "live member"**, as #221 gave one for "able owner"; the app layer DERIVES from the trigger's definition and never keeps a second count | [`2026-09-07-237-242.md`](rulings/2026-09-07-237-242.md) |
| 2026-09-07 | #240 | OWNER-RULING | **STANDING** — the proofs are REPAIRED before they are trusted again: five instruments that cannot currently fail | [`2026-09-07-237-242.md`](rulings/2026-09-07-237-242.md) |
| 2026-09-07 | #241 | OWNER-RULING | **STANDING** — the two records are corrected to say what is TRUE: the stale comment, and the §2.5 rows' forbidden-state count | [`2026-09-07-237-242.md`](rulings/2026-09-07-237-242.md) |
| 2026-09-07 | #242 | OWNER-RULING | **STANDING** — the order: #1036's five repairs → a fresh round on #1036 → round six on #1018 → both leave draft on CLEAN rounds only | [`2026-09-07-237-242.md`](rulings/2026-09-07-237-242.md) |
| 2026-09-07 | #243 | OWNER-RULING | **RATIFIED** — the #1036 repairs: #238 closed in the database with a VALID control, #239's one predicate with behavioural coverage, #240's four repairs, #241's two records, and the two self-introduced defects caught | [`2026-09-07-243-245.md`](rulings/2026-09-07-243-245.md) |
| 2026-09-07 | #244 | OWNER-RULING | **STANDING** — three canon entries: **128** assert a SQL mutation in the DATABASE, **129** a witness that rolls back with the refused transaction cannot witness the refusal, **130** Postgres has no nested transactions | [`2026-09-07-243-245.md`](rulings/2026-09-07-243-245.md) |
| 2026-09-07 | #245 | OWNER-RULING | **STANDING** — a fresh round on #1036 → round six on #1018 → **EACH** leaves draft on a clean round → the next composed deploy with their rows | [`2026-09-07-243-245.md`](rulings/2026-09-07-243-245.md) |
| 2026-09-07 | #246 | OWNER-RULING | **STANDING — REGISTRY-1**, the last change before 🟢: the four concepts the acceptance needs, as their own change | [`2026-09-07-246.md`](rulings/2026-09-07-246.md) |
| 2026-09-07 | #247 | OWNER-RULING | **STANDING** — **family 3 is a NEW FACT CLASS, not a reuse**: `sourceType` gains **`visit_record`** | [`2026-09-07-247.md`](rulings/2026-09-07-247.md) |
| 2026-09-07 | #258 | OWNER-RULING | **STANDING** — **NO MIRROR**: `scaffoldDefaultOfferable` CALLS the resolver's exported `missingResolution` predicate, so the eighth unmirrored call site — and any ninth — cannot exist | Round seven found an EIGHTH unmirrored site (a checkbox with a multi-concept `conceptScope`, OFFERED an omit the resolver will not honour). ⚠️ **SEVEN ROUNDS OF ARMS DID NOT CLOSE THIS AND COULD NOT** — every previous repair widened a matrix so the mirror's CURRENT divergences were visible, and **a second implementation of a rule is a defect testing can only FIND, never prevent. The tests were being asked to do the job the code should do.** The arm changes shape with it: an **identity check that the offer DELEGATES** rather than decides, plus **one behavioural control per known guard**, so delegation to the wrong function or to a stub still reds. | [`2026-09-07-258-260.md`](rulings/2026-09-07-258-260.md) |
| 2026-09-07 | #259 | OWNER-RULING | **STANDING** — the matrix is **REDESIGNED, not re-seeded**: the exact product over the TRACED read set, compatible pairs from the compiler's own table, **BRANCH coverage**, zero-witnessed strata REFUSED, sampling only over a stated budget with a per-stratum floor | The seeded sample failed four ways at once and re-seeding fixes none: its first guard killed **73.4%** of rows so the two inputs it was widened to watch were **constant everywhere the other seven guards live**; the generator saturates at **6.42% of the cross-product forever**; the coverage arm is a tautology that **passes at `SAMPLES = 3`**; and its green is a property of the seed literal — **correct code REDS on some seeds**. ⚠️ **The hand-written type list is what killed 73.4% of the rows — `'date'` had no compatible partner in it at all** — which is why the pairs come from the compiler's table and never from a guess. ⚠️ **AND THE ACCEPTANCE TEST FOR THE ARM ITSELF: it must RED at `SAMPLES = 3`.** | [`2026-09-07-258-260.md`](rulings/2026-09-07-258-260.md) |
| 2026-09-07 | #260 | OWNER-RULING | **RATIFIED** — #1036's four gap closures with their controls, the insert-door practice fix with its split fixture, and **one branch per push**; then round eight on #1018 and round five on #1036, each under #254 | The savepoint fact is **re-measured on every run**, and ⚠️ *"the conclusion survived and the reason didn't"* is the part worth keeping — **a comment that reaches the right answer by a false route will be trusted by the next reader for the route.** ⚠️ **A fixture that gives two distinct things the same value cannot witness them being confused**: the *"not the requester"* arm carried its title for months without being able to distinguish what it named, until the fixture split the session's practice from the visit author's. ⚠️ **One branch per push** — the two-view check is correct per branch and **cannot see contention the pusher is about to create with their own next push**. | [`2026-09-07-258-260.md`](rulings/2026-09-07-258-260.md) |
| 2026-09-07 | #261 | OWNER-RULING | **STANDING** — a row that prints a patient's name is **never certified below the fold**: `bulkConfirmable` excludes `visit_metadata`, as a RULING | Bulk confirmation certifies dispositions the doctor has not individually read, on the argument that the machine's proposal is obviously right. ⚠️ **That argument does not survive a field whose rendered output is the patient's own NAME** — the failure mode is not a mis-mapped concept, it is a document that confidently prints the wrong person. Recorded as a ruling because **the exclusion LOOKS LIKE A GAP**: a future session tidying `bulkConfirmable` will find `visit_metadata` conspicuously missing from a list its siblings are on, read that as an oversight, and close it. | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #262 | OWNER-RULING | **STANDING** — **two of the three claimed blockers were the session's own**; the door exists, and the wrapper becomes the door | This lane certified/activated `939aa9ea` and ran its ten-row correction under a mutation declaration; Design/Admin ran #226 the same morning — **both records name how the act reached the database.** The mechanism ordered: **`run-ruled-mutation.sh` executes the declared act INSIDE the container**, as `deploy-prod.sh` already does for migrations, so **no session needs `.env` or a raw `exec`** — the shape of `dc.sh` and the reaper, whose grant is `Bash(bash scripts/<named>.sh:*)` because nothing after that prefix can change which file runs. ⚠️ **THE GENERALISABLE HALF:** a session that cannot perform an act has two indistinguishable explanations — *the system forbids it* and *I have not found the door* — and escalating the first when the second is true spends an owner decision that should never have been raised. **A peer's record of the same act is the check, and it is one grep.** Only if ONE named permission rule then remains is it his. | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #263 | OWNER-RULING | **STANDING** — the 53-control re-issue is **ONE declared, machine-driven act**, then the owner's eyeball | Re-ingest from the stored artifact (**pre-guard: bytes sha = the pinned record**) → new compiled version (**pre-guard: its 53 fieldIds set-equal to the certified version's**) → **`transfer-certification-to-active` PARAMETERISED** — source, target and expected count as **REQUIRED arguments**, **every guard kept**, **its own PR first** — moving **the 43**, with **the ten** re-proposed under the new registry → **abort on any mismatch, counts printed.** THEN the human step, which is owner-class (c) and not meant to be automated: he confirms the `visit_metadata` rows in the app (see **#261**), this lane certifies and activates, he records a **fresh GI visit** and exports → **eleven-row diff on HIS export** → 🟢. | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #264 | OWNER-RULING | **STANDING** — **AGE NEVER GUESSES**: the injector refuses, blank and with a named reason, whenever the UTC-12..UTC+14 window admits two answers | Until `Practice.timezone` exists, the age injector **REFUSES** whenever the computed age would differ **anywhere in the UTC-12..UTC+14 window** of the visit instant. ⚠️ **A one-year-high age on a consult letter is a CLINICAL ERROR, not a formatting blemish** — the window is ±26 hours wide, so for any patient whose birthday falls near the visit date there exists a real timezone giving a different answer, and the server's own zone is not evidence about the doctor's. **The blank is the point:** a named refusal is a question the doctor answers in one second; a confident wrong number is one he will not notice. **Board filing PRACTICE-TZ** to Design/Admin — `Practice.timezone` (IANA), captured at signup, editable, used by **every** visit-local-date derivation. The refusal retires when it lands. | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #265 | OWNER-RULING | **STANDING** — mechanise the deploy RANGE, and three sweep arms | **(a)** The declaration **derives `production..HEAD` from the last judged deploy's rollback tag**, **never from `origin/main`**; **a TYPED range is REFUSED.** ⚠️ `origin/main` answers *what has been merged*, which is not *what is running* — they agree most days, and the day they do not the range silently omits or invents commits, giving a §2.5 declaration that **looks exactly like evidence**. **(b)** Two duplicate root-ruling guards exist for one property: **the first on `main` STAYS, the other lane deletes its copy on rebase** (canon 115). **(c)** **Every shell-out timeout in the test tree is bounded by its own `it` budget** — reference `c4e778a2`, an arm that **declared 120s and ran under 5s**, so its shell-out could never fail as a timeout. **(d)** **`pro.quillmd.com` 410 is the intended steady state, NEVER a preflight fix.** | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #266 | OWNER-RULING | **STANDING — PROJECTOR-1** — bare-keyword temporality, and the arm is over the WHOLE registry | Bare-keyword temporality has **mis-stamped two clinical fields**: the **HPI header → `historical`**, and **"referred" → `planned`**. The arm ordered: **every registered concept's self-test sentence must project to its declared temporality, armed over the WHOLE registry** — not a sample, and not the two known instances. ⚠️ **The two named fields are the symptom; the arm is the point** — fixing two keywords closes two instances of a class that produces a new one every time a concept is added, whereas a registry-wide arm turns *somebody noticed* into *the next one cannot merge*. | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-08 | #272 | OWNER-RULING | **STANDING** — **a record-derived refusal NEVER withholds a document**; on a REQUIRED control it degrades to blank-with-a-named-reason and routes to the doctor's own fill | On a required control *"the record cannot answer"* becomes a **blank with a named reason**, routed to the *"Your blanks"* surface **exactly as a manual field** — never `blocking` → `render: null`. ⚠️ **A withheld consult over one ambiguous age is the wrong trade; a doctor typing "61" is the right one.** This decides the owner-class (b) question PR #1057 surfaced: #264's refusal WIDENED a pre-existing trigger (`main` already routed a required age control with a missing DOB into `missingResolution → needs_clinician_input → blocking`), and **the pre-existing behaviour is ALSO wrong for this class.** Consistent with **#157(b)** — *no denial may refuse an export* — which already makes `FIELD_DENIAL_WITHHELD` an unconditional warning; a record that cannot answer is not a reason to withhold the other 149 fields. **THE ARM:** an ambiguous age on a required control yields a **RENDERED** document with that field blank and its reason in the manifest. PRACTICE-TZ retires the refusal later. | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #273 | OWNER-RULING | **STANDING — ONE GUARD** (closes #265(b)): keep `gate-ruling-row-identity`, fold the unique arms across, delete the weaker copy | *Two guards for one property drift the day either is fixed.* ⚠️ **This OVERRIDES the ordering rule #265(b) originally gave** — *"the first on `main` stays"* selects the **ledger** arm (landed 2026-08-27 vs row-identity's 2026-09-07), and the session reported that **both had already merged**, so there was no "other lane" and no race left to resolve. **The question becomes MERIT, not ORDER**, and the exported, separately-controlled implementation is the one worth keeping. The session's refusal to delete on the ordering rule alone was the right escalation. ⚠️ **"Fold any UNIQUE arm" is the half that can go wrong silently** — deleting a describe that carried one assertion nothing else makes is a coverage loss no test reports, so **the unique set is enumerated BEFORE anything is deleted** and the enumeration is the evidence. | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #274 | OWNER-RULING | **STANDING** — BUILD the ingest entry point: a server-side FUNCTION (not a route), two pre-guards, abort otherwise; its own PR and its own pass | `ingest from stored artifact BYTES → new DRAFT compiled version`, callable from the in-container door (#262's `--in transcribe-md-worker`). **PRE-GUARDS:** (1) the artifact's **sha256 equals the pinned record**; (2) the new version's **53 fieldIds are set-equal to the CERTIFIED version's**. ⚠️ **A FUNCTION, NOT A ROUTE** — a route needs a session and an HTTP surface and would make an irreversible act reachable by anything that can reach the app; the ruled door already carries the declaration gate, the single-container resolution and the image-revision check. ⚠️ **THE SECOND GUARD DEPENDS ON A PROPERTY THAT MUST BE VERIFIED, NOT ASSUMED:** `fieldId` is recorded as salted with the **whole-package sha256**, so the same bytes should reproduce the same fieldIds — **if that is false the guard can never pass and the act is impossible**, so the derivation is read from the code before the guard is written. | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #275 | OWNER-RULING | **STANDING — THE SEQUENCE**: #1057's re-pass → merge #1055/#1056/#1057/#1058 on clean citations → the ingest PR → composed deploy → the re-issue act → the owner's confirm, certify, activate, fresh visit → the eleven-row diff → 🟢 | ⚠️ **STEP 1 PRECEDES THE MERGES BECAUSE THE DIFF CHANGED AFTER THE PASS RAN.** #1057's pass found five defects and the fixes are themselves a finished diff; a pass over the pre-fix tree does not discharge the post-fix one — *a clean round is the condition, not a count of rounds served* (#223). The re-issue act runs through `--in transcribe-md-worker` under its declaration: **transfer the 43, re-propose the ten.** ⚠️ **AND THE `five narrative shapes` CI-ONLY RED STAYS RECORDED UNTIL REPRODUCED, NEVER DISMISSED** — it failed in CI on a branch touching nothing near it and passes locally; *"probably a flake"* is the sentence that retires a finding without evidence. | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #276 | OWNER-RULING | **STANDING** — the twenty `.lens-1018-*` sandboxes are **Design/Admin's**, and **#213's marker is what makes them reapable**; build it in this batch | The session was right not to reap another lane's scratch — the close-out rule assigns that to the session that made it. ⚠️ **But "not mine" is not a disposal policy:** left alone they are 12.8 GB of a shared deploy surface nobody feels entitled to touch, **and the reason nobody can touch them is that a sandbox carries no record of whose it is or when it was made.** #213's marker is that record, and building it converts *"not mine"* into *"abandoned, and safe to reap"*. ⚠️ **A LIVENESS SIGNAL IS PART OF THE MARKER, NOT AN EXTRA** — a sandbox in USE must never be reaped, and canon records how that measurement goes wrong: **`pgrep -f` returned a false LIVE reading for three hours because the probe matched itself.** The marker must be readable by a session that did not create it, and liveness answerable without a probe that can match the asker. | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #277 | OWNER-RULING | **RATIFIED** — #267–#271, the deadlock proof, the isolation refusal, the single-source tenant, the six instrument closures, canon 143, and the `$executeRaw` fix **with its double** | [`2026-09-08-277-283.md`](rulings/2026-09-08-277-283.md) |
| 2026-09-08 | #278 | OWNER-RULING | **STANDING** — every index row is a **POINTER** (number, date, title, body path); STANDING rows stay in the head as pointers, never as prose; `rotate-ledger.sh` becomes **ATOMIC** | [`2026-09-08-277-283.md`](rulings/2026-09-08-277-283.md) |
| 2026-09-08 | #279 | OWNER-RULING | **STANDING** — `V3`'s failing input is the **INSERT** race: run the moved-lock mutation against `raceB`, and if it reds, that race with that mutation IS the order arm | [`2026-09-08-277-283.md`](rulings/2026-09-08-277-283.md) |
| 2026-09-08 | #280 | OWNER-RULING | **STANDING** — `F1`/`TRACER-1`: the same Proxy tracer, second application, on the resolver's ladder; **the regex half is DELETED, not upgraded** | [`2026-09-08-277-283.md`](rulings/2026-09-08-277-283.md) |
| 2026-09-08 | #281 | OWNER-RULING | **STANDING** — **production Postgres stops being published to the host**: remove the compose mapping, §2.5 row, next deploy; MinIO and Redis audited after | [`2026-09-08-277-283.md`](rulings/2026-09-08-277-283.md) |
| 2026-09-08 | #282 | OWNER-RULING | **STANDING** — `setup-worktree.sh`'s mirror **REFUSES a real-directory destination, naming it**, with a control that plants one | [`2026-09-08-277-283.md`](rulings/2026-09-08-277-283.md) |
| 2026-09-08 | #283 | OWNER-RULING | **STANDING** — the order: #278 (own PR) → #279 → #280 → #281/#282 → the two canon entries → **then one round each under #254** | [`2026-09-08-277-283.md`](rulings/2026-09-08-277-283.md) |
| 2026-09-08 | #287 | OWNER-RULING | **STANDING — CLASS (a) DECIDED** — the CHART's practice owns the template too; the fill parameter splits into `tenantPracticeId` (scopes the visit AND selects/validates the template) and `authorUserId` (audit only, never a scope); no active template ⇒ styled export with a NAMED REASON, never a mismatch error | [`2026-09-08-287-293.md`](rulings/2026-09-08-287-293.md) |
| 2026-09-08 | #288 | OWNER-RULING | **STANDING** — `NM-1` fixed NOW under NO MIRROR: `validation/index.ts` calls the shared `requiresClinicianInput` and the partial copy is deleted; **class closure — every blocking-code emission has exactly ONE caller, gated** | [`2026-09-08-287-293.md`](rulings/2026-09-08-287-293.md) |
| 2026-09-08 | #289 | OWNER-RULING | **STANDING** — the door list is **DERIVED from the filesystem**, every route CLASSIFIED, an unclassified route REDS, every writer DRIVEN and asserted to take `withPracticeLock`; fix `unsuspend`, `grant-admin`, `revoke-admin`, `force-logout` now | [`2026-09-08-287-293.md`](rulings/2026-09-08-287-293.md) |
| 2026-09-08 | #290 | OWNER-RULING | **STANDING** — #278's staging runs the **REAL ledger gates (vitest)** on the staging copy, as ruled; control plants a wiped archive index and asserts the swap is REFUSED | [`2026-09-08-287-293.md`](rulings/2026-09-08-287-293.md) |
| 2026-09-08 | #291 | OWNER-RULING | **STANDING** — #279's **10/12 is WITHDRAWN** until re-measured; `mk_moved` must relocate the lock after the counts on EVERY path, not behind an early return | [`2026-09-08-287-293.md`](rulings/2026-09-08-287-293.md) |
| 2026-09-08 | #292 | OWNER-RULING | **STANDING** — `rounds-c1` is this lane's and in scope: the test **asserts its precondition** (after `clearCookies()` the session endpoint answers unauthenticated BEFORE navigating) instead of naming its own flake | [`2026-09-08-287-293.md`](rulings/2026-09-08-287-293.md) |
| 2026-09-08 | #293 | OWNER-RULING | **STANDING** — the order: #287 → #288 → #289 → #290 → #291 → #292, **then one round each under #254** | [`2026-09-08-287-293.md`](rulings/2026-09-08-287-293.md) |
| 2026-09-08 | #294 | OWNER-RULING | **STANDING — THE TENANT IS BILLED**: a locum visit at A is A's chart, A's document and A's usage — `worker.ts` re-derives `practiceId` from the **VISIT row**, one derivation for its ~25 sites, never from `visit.user`; the 25 are AUDITED FIRST and any site that genuinely means the author keeps `authorUserId` **by name**, while scope, template, admission and charging take the tenant. §2.5: production is **58/58 author-practice == tenant**, so the change moves nothing today. Arm: admission and charge hit **A** on the three-identity fixture | [`2026-09-08-294-296.md`](rulings/2026-09-08-294-296.md) |
| 2026-09-08 | #295 | OWNER-RULING | **STANDING** — **rebuild the QA image** through the sanctioned QA compose build, so `rounds-c1`'s four Gate-C failures either clear or become real: **a stale fixture is not a baseline**, and until the rebuild those four are neither a pass nor a defect | [`2026-09-08-294-296.md`](rulings/2026-09-08-294-296.md) |
| 2026-09-08 | #296 | OWNER-RULING | **STANDING** — the order: #294 → #295 → **one round each under #254**; instrument-only survivors, with those instruments repaired, release **both** drafts | [`2026-09-08-294-296.md`](rulings/2026-09-08-294-296.md) |
<!-- RULINGS-INDEX-END -->

## What is NOT in here, deliberately

**Engineering lessons are not rulings.** The canon in `AGENTS.md` — the
write-path sweep, title-narrower-than-measurement, the watched-set diff, scripted
edits proving their application — is how to do the work correctly, not a decision
about what the product is. Mixing them would make this file long enough that
nobody greps it, which is the only way it can fail.

The test is: **could a reasonable person have decided otherwise?** If yes, it is
a ruling and belongs here. If it is simply true, it is a lesson and belongs in
`AGENTS.md`.

⚠️ **THIS SECTION USED TO HAVE 41 RULING ROWS UNDERNEATH IT** — `#109(a)`, `#111`,
`#115` and everything through `#149` — because appends land at the end of a file
and this section had stopped being the end. **Nobody misfiled anything; the file
outgrew its own shape.** A session reading by heading would have concluded those
rulings were excluded. The split fixes it by construction: every row is in the
index above, every body in `docs/foundation/rulings/`.

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
| [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) | The index | 107–180 | 105,194 |
| [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) | (untitled) | 181–215 | 78,364 |
| [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) | What is NOT in here, deliberately | 216–250 | 106,835 |
| [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) | (untitled) | 251–269 | 78,823 |

**4 archives · 369,216 chars · largest 106,835.**

<!-- ARCHIVE-INDEX-END -->
