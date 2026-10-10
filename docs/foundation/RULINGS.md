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
| 2026-09-07 | #230 | OWNER-RULING | **STANDING** — **NO NEW ENUM VALUE FOR SIX TEST ROWS**; the act follows the **gate0 precedent exactly** | One raw-SQL one-shot; **committed declaration first**, in `docs/deploy-declarations/` and **NOT** `docs/foundation/deploys/`; **pre-guards bound to the declared population**; **post-verify that ROLLS BACK**. **USERS:** `deactivatedAt` reconciled to the **audit-trail timestamp RE-DERIVED AT RUN TIME** — refuse if the witnesses disagree; **`updatedAt` untouched AND asserted untouched**; `deactivatedBy` = **the ruling identifier**, the established practice in that column (`gate0-ruling-2026-08-05` on the other two users of this same population). **PRACTICES:** `practices.isActive = false` **as a MARKER, stated as a marker in the declaration** — nothing reads it today. **The declaration commit plus the users' EXISTING `USER_DEACTIVATED` rows are the record.** ⚠️ **A real `PRACTICE_ARCHIVED` action arrives with practice-lifecycle work in the ADMIN arc, with its own migration; these six get their rows THEN** — an irreversible enum value is not spent on a six-row cleanup, and the archive is not blocked waiting for one. | [`2026-09-07-230-232.md`](rulings/2026-09-07-230-232.md) |
| 2026-09-07 | #231 | OWNER-RULING | **RATIFIED AS BUILT** — #227's allowlist arm, and the two rejections that prove it | **The arm rejecting its own author's drafts is THE POINT**: a **false claim on the allowlist** (`rendererBinding` declared constant when it is varied through a nested loop variable) and a **stale entry** (`unmentionedPolicy`, which the mirror does not read). ⚠️ **AND THE CAST-FORM READ DETECTION** — the probe written `(field as { … }).prop` left the arm **37/37 GREEN** because `field.` never appears literally; that is **the `as any` admin-door shape**, where six doors were invisible to the obvious grep. `READS_RE` now matches both spellings, and a cast is exactly how the first form is written when the property is not on the declared type — which is precisely when a new, unwatched input arrives. **Lands with #1018 after #1040 merges.** | [`2026-09-07-230-232.md`](rulings/2026-09-07-230-232.md) |
| 2026-09-07 | #232 | OWNER-RULING | **STANDING — THE ORDER IS THE RULING** | **#1040 on citation → the #226 one-shot on production under its declaration → JUDGE (five timestamps equal the witness; six practices flagged; nothing else moved) → round five on #1018.** ⚠️ **Each arrow is a gate, not a step.** The declaration cannot be committed before #1040 lands (the pre-commit hook refuses source citing an unrecorded ruling — correctly); the one-shot cannot run before its declaration is committed (the runner refuses an untracked or uncommitted declaration — the B7 backfill lost that distinction by 1m57s); and the judgement is not the act's own exit code but a separate re-derivation against the declared rows. **A step skipped here is not a shortcut, it is the removal of the thing that makes the act auditable.** | [`2026-09-07-230-232.md`](rulings/2026-09-07-230-232.md) |
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
| 2026-09-07 | #251 | OWNER-RULING | **STANDING** — **TEXT SCANNERS ARE RETIRED AS PROOFS OF BEHAVIOUR**; text reads remain only for prose and docs | [`2026-09-07-251-255.md`](rulings/2026-09-07-251-255.md) |
| 2026-09-07 | #252 | OWNER-RULING | **STANDING** — **THE WITNESS IS AUTONOMOUS**; the `pg_stat_activity` sampler is RETIRED | [`2026-09-07-251-255.md`](rulings/2026-09-07-251-255.md) |
| 2026-09-07 | #253 | OWNER-RULING | **STANDING** — the seven code fixes land as **ONE repair**, so the next round judges one finished diff | [`2026-09-07-251-255.md`](rulings/2026-09-07-251-255.md) |
| 2026-09-07 | #254 | OWNER-RULING | **STANDING — AMENDS #223** — one round each, and **if a round finds only INSTRUMENT defects and no CODE defects, the PR LEAVES DRAFT with those instruments repaired** | [`2026-09-07-251-255.md`](rulings/2026-09-07-251-255.md) |
| 2026-09-07 | #255 | OWNER-RULING | **STANDING** — **ONE SANDBOX PER AGENT, VERIFIERS INCLUDED** | [`2026-09-07-251-255.md`](rulings/2026-09-07-251-255.md) |
| 2026-09-07 | #256 | OWNER-RULING | **RATIFIED** — #1036's trigger fixes, widened lock, reaped fixture, the **"one" not "six"** and all four §2.5 obligations; #1018's **Proxy tracer**, seeded matrix and full-predicate lock; the renumber; the duplicate-root-ruling gate | [`2026-09-07-256-257.md`](rulings/2026-09-07-256-257.md) |
| 2026-09-07 | #257 | OWNER-RULING | **STANDING** — one round each, and **#254's rule releases the draft**: a round finding only INSTRUMENT defects, with those instruments repaired, ends the hold | [`2026-09-07-256-257.md`](rulings/2026-09-07-256-257.md) |
| 2026-09-07 | #258 | OWNER-RULING | **STANDING** — **NO MIRROR**: `scaffoldDefaultOfferable` CALLS the resolver's exported `missingResolution` predicate, so the eighth unmirrored call site — and any ninth — cannot exist | [`2026-09-07-258-260.md`](rulings/2026-09-07-258-260.md) |
| 2026-09-07 | #259 | OWNER-RULING | **STANDING** — the matrix is **REDESIGNED, not re-seeded**: the exact product over the TRACED read set, compatible pairs from the compiler's own table, **BRANCH coverage**, zero-witnessed strata REFUSED, sampling only over a stated budget with a per-stratum floor | [`2026-09-07-258-260.md`](rulings/2026-09-07-258-260.md) |
| 2026-09-07 | #260 | OWNER-RULING | **RATIFIED** — #1036's four gap closures with their controls, the insert-door practice fix with its split fixture, and **one branch per push**; then round eight on #1018 and round five on #1036, each under #254 | [`2026-09-07-258-260.md`](rulings/2026-09-07-258-260.md) |
| 2026-09-07 | #261 | OWNER-RULING | **STANDING** — a row that prints a patient's name is **never certified below the fold**: `bulkConfirmable` excludes `visit_metadata`, as a RULING | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #262 | OWNER-RULING | **STANDING** — **two of the three claimed blockers were the session's own**; the door exists, and the wrapper becomes the door | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #263 | OWNER-RULING | **STANDING** — the 53-control re-issue is **ONE declared, machine-driven act**, then the owner's eyeball | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #264 | OWNER-RULING | **STANDING** — **AGE NEVER GUESSES**: the injector refuses, blank and with a named reason, whenever the UTC-12..UTC+14 window admits two answers | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #265 | OWNER-RULING | **STANDING** — mechanise the deploy RANGE, and three sweep arms | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-07 | #266 | OWNER-RULING | **STANDING — PROJECTOR-1** — bare-keyword temporality, and the arm is over the WHOLE registry | [`2026-09-07-261-266.md`](rulings/2026-09-07-261-266.md) |
| 2026-09-08 | #267 | OWNER-RULING | **STANDING** — **THE CHART OWNS THE NOTE**: every row attached to a visit carries `visit.practiceId`, read FROM THE VISIT ROW | [`2026-09-08-267-271.md`](rulings/2026-09-08-267-271.md) |
| 2026-09-08 | #268 | OWNER-RULING | **STANDING** — the deadlock is a **WRITER-ORDER** defect: `withPracticeLock` before any user-row write; the trigger keeps its lock as re-entrant defence | [`2026-09-08-267-271.md`](rulings/2026-09-08-267-271.md) |
| 2026-09-08 | #269 | OWNER-RULING | **STANDING** — the guard **REFUSES above READ COMMITTED**, naming the level; the proof runs at **all three** | [`2026-09-08-267-271.md`](rulings/2026-09-08-267-271.md) |
| 2026-09-08 | #270 | OWNER-RULING | **STANDING — AMENDS #258** — *one implementation, **EITHER DIRECTION***: the resolver walking the offer's table satisfies the invariant | [`2026-09-08-267-271.md`](rulings/2026-09-08-267-271.md) |
| 2026-09-08 | #271 | OWNER-RULING | **STANDING** — the order: merge **#1054**; `main` → **#1036** re-verified **ON THE MERGE RESULT**; the 19 instrument survivors close **WITH** the code fixes; then one round each under #254 | [`2026-09-08-267-271.md`](rulings/2026-09-08-267-271.md) |
| 2026-09-08 | #272 | OWNER-RULING | **STANDING** — **a record-derived refusal NEVER withholds a document**; on a REQUIRED control it degrades to blank-with-a-named-reason and routes to the doctor's own fill | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #273 | OWNER-RULING | **STANDING — ONE GUARD** (closes #265(b)): keep `gate-ruling-row-identity`, fold the unique arms across, delete the weaker copy | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #274 | OWNER-RULING | **STANDING** — BUILD the ingest entry point: a server-side FUNCTION (not a route), two pre-guards, abort otherwise; its own PR and its own pass | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #275 | OWNER-RULING | **STANDING — THE SEQUENCE**: #1057's re-pass → merge #1055/#1056/#1057/#1058 on clean citations → the ingest PR → composed deploy → the re-issue act → the owner's confirm, certify, activate, fresh visit → the eleven-row diff → 🟢 | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
| 2026-09-08 | #276 | OWNER-RULING | **STANDING** — the twenty `.lens-1018-*` sandboxes are **Design/Admin's**, and **#213's marker is what makes them reapable**; build it in this batch | [`2026-09-08-272-276.md`](rulings/2026-09-08-272-276.md) |
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
| 2026-09-08 | #297 | OWNER-RULING | **STANDING — CLASS (d)** — reclaim IN ORDER through the wrappers: **(a)** `docker builder prune -af` with no `--until` (today's cache is regenerable; **declare the slowdown in the log** so no lane reads it as a fault); **(b)** the **ROLLBACK KEEP POLICY IS AMENDED** — keep every tag **younger than 72 h** PLUS the tags of the **last FIVE JUDGED deploys**, because everything older is a redeploy of an older commit and not a rollback; `prune-rollback-tags.sh` implements it, its dry run lists **what goes and why**, the act carries a **§2.5-style declaration**, and ⚠️ **#137 stays unchanged for everything inside the keep-set**; **(c)** re-run preflight and proceed **only under 90%** | [`2026-09-08-297-300.md`](rulings/2026-09-08-297-300.md) |
| 2026-09-08 | #298 | OWNER-RULING | **STANDING** — **#255 stands**: one sandbox per agent, verifiers included. If RAM says so (**swap is exhausted**) the round runs **SEQUENTIALLY BY LANE**, never by sharing sandboxes — sequencing costs wall-clock, sharing costs the independence #255 exists to buy | [`2026-09-08-297-300.md`](rulings/2026-09-08-297-300.md) |
| 2026-09-08 | #299 | OWNER-RULING | **STANDING** — the preflight skill's own preamble is corrected to the box it runs on (**32 GB / 14 cores**, not 13 GB / 8): **a threshold calibrated against a machine that no longer exists is the WATCHED-SET failure in prose** — the numbers still function, the stated baseline a future reader would calibrate from does not | [`2026-09-08-297-300.md`](rulings/2026-09-08-297-300.md) |
| 2026-09-08 | #300 | OWNER-RULING | **RATIFIED** — #294 (uniform audit, one derivation, the harness `worker.ts` has wanted since the stuck-chart incident), #295 (**15/0** with all three causes named), and the colour fix that asks for `Tests` and `<n> passed` **independently** | [`2026-09-08-297-300.md`](rulings/2026-09-08-297-300.md) |
| 2026-09-08 | #301 | OWNER-RULING | **STANDING — SEQUENCING** — the ledger is oversize because **#278's pointer reshape has not landed**, not because it grew (`main` 146,340 chars vs **51,812** on PR #1061): land #1061 first, union by ruling number with the POINTER form winning, then every ledger branch rebases onto it — **no rotation** | [`2026-09-08-297-300.md`](rulings/2026-09-08-297-300.md) |
| 2026-09-08 | #302 | OWNER-RULING | **STANDING** — the SELECTION half is #287's: the worker selects the **TENANT** practice's active template, never the author's; `doctorId` is attribution only. Arm: a locum visit at A renders **A's** template, and a tenant with none yields the named `no_tenant_template` miss — **never a pin, never a mismatch** | [`2026-09-08-302-305.md`](rulings/2026-09-08-302-305.md) |
| 2026-09-08 | #303 | OWNER-RULING | **STANDING** — the omit matrix's **status dimension is DERIVED from the enum** (#259), and the **1,344 disagreements + 16,800 token mismatches are ADJUDICATED**: each is a defect, a legitimate divergence with a stated reason, or an instrument artifact. ⚠️ **No silent allowlist.** The dangerous direction is already closed — **0** `offered && !honoured` over 3,483,648 rows | [`2026-09-08-302-305.md`](rulings/2026-09-08-302-305.md) |
| 2026-09-08 | #304 | OWNER-RULING | **STANDING — THE EXIT RULE** — lane 1's next round is its **LAST**: instrument-only, or SUBJECT defects whose fix **DELETES or NARROWS** a path → fix and ready. **Only a fix that ADDS a path earns another round.** Lane 2 runs under the identical rule | [`2026-09-08-302-305.md`](rulings/2026-09-08-302-305.md) |
| 2026-09-08 | #305 | OWNER-RULING | **RATIFIED** — the SWC gate with its planted control (and ⚠️ *four identical answers is an instrument measuring nothing*), the read-only ownership pre-check, the `isScoped` repair, the resolver dedupe gap recorded on #1071, the canon renumber and row form, the `-F` amend | [`2026-09-08-302-305.md`](rulings/2026-09-08-302-305.md) |
| 2026-09-09 | #306 | OWNER-RULING | **STANDING** — **THE NARROWING STANDS**: an unrecoverable practice is never a legitimate outcome of two ordinary clicks; winding down gets its own door, **PRACTICE-ARCHIVE** (ADMIN lifecycle) — ONE declared act archiving the practice AND its members together, restorable, audited, on the deferred `PRACTICE_ARCHIVED` row | Exemption 2 counts RESTORABLE members, not LIVE ones, refusing only the corner where a trapped non-owner remains and no restorable owner can rescue; suspending a solo OWNER stays legal because that owner is their own rescuer. ⚠️ **The capability is RE-HOMED, not dismissed** — today's path reaches the end state by ACCRETION, one legal click at a time, with no actor ever deciding the practice is closing. | [`2026-09-09-306-309.md`](rulings/2026-09-09-306-309.md) |
| 2026-09-09 | #307 | OWNER-RULING | **STANDING** — `meddoc-pro` is RETIRED: **remove the compose service definition and the image reference** so no `compose up` can revive an unlocked `users` writer; declared, git-reversible, carrying the co-tenant baseline row | The four unlocked doors' missing lock was MEASURED to deadlock the locked ones, the locked side losing and its write silently gone. ⚠️ **The doors stay PINNED until DELETE-MEDDOC-PRO** (filed now as the arc item) removes the CODE — closing the service closes the door, it does not delete the writer. ⚠️ `pro.quillmd.com` must still answer **410**; a change AWAY from 410 is the finding. **Custom-file owns compose and deploy — board filing.** | [`2026-09-09-306-309.md`](rulings/2026-09-09-306-309.md) |
| 2026-09-09 | #308 | OWNER-RULING | **STANDING** — **THE SHARED TREE MUST TYPECHECK**: no dev server on the deploy surface — identify the resident `next-server`'s owner session and stop it THERE, clear the stale gitignored `.next`, and make the pre-push typecheck **EXCLUDE `.next/types`** | A stale generated artifact made the hook refuse EVERY push from `/opt/meddoc-pro`, a branch deletion included, naming a file the pusher never touched. ⚠️ **The exclusion is the part that ends the class** — the first two steps fix today's instance only. ⚠️ A process on a shared box belongs to whoever started it, so it is stopped THERE, not killed from outside. **Custom-file's — the hook is theirs.** | [`2026-09-09-306-309.md`](rulings/2026-09-09-306-309.md) |
| 2026-09-09 | #309 | OWNER-RULING | **RATIFIED** — merge **#1018** and **#1036** through the wrapper on their clean citations; they ride the NEXT composed deploy with their rows, and the re-issue deploy already in flight does not wait | ⚠️ **The `next@16.2.11` + #302 e2e interaction stays recorded as UNEXPLAINED on #1018**: four failures with #302 on the old Next, a pass on 16.3.4 with #302 unchanged, two #302-free controls passing on the old version, and ONE file between failing and passing commits — `package-lock.json`. **A green that arrives without a mechanism is a green, not an explanation.** | [`2026-09-09-306-309.md`](rulings/2026-09-09-306-309.md) |
| 2026-09-09 | #310 | OWNER-RULING | **STANDING** — **FULL AUTONOMY THROUGH THE ADMIN ARC**: the lane runs the arc end to end with **no reporting in between** and ONE consolidated report at the end (what shipped, what was decided on the owner's behalf and why, what remains, the preview URL). Scope in order, each with its pass and §2.5 rows: #1078 + #1083 → ADMIN-3a (the `Practice` write path) + #226's archive + ADMIN-6 → #307 + DMP-a + the console PORT (DELETE-MEDDOC-PRO only after) → the three design directions (control room / ledger / instrument panel) as HTML mockups in separate sub-sessions with BAN lists, published to `_preview`, plumbing continuing while the shell waits for ONE pick → composed deploys, never two in flight | **PRE-DECIDED, never pause:** (a) product questions → the standing principles (chart owns the note; tenant is billed; one predicate per rule; PORT not BUILD); (b) capability trades → **fail closed, never strand, never withhold**; (c) instruments → fix the CAUSE. **STOP only for: sudo, a secret in no container, an irreversible production deletion no declaration covers.** ⚠️ **A red gate, a failed round, a conflicting PR or a defect in this lane's own work is NOT a stop — it is the work.** ⚠️ **The proof burden is UNCHANGED**: what moves is the routing of NARRATION, not of EVIDENCE. | [`2026-09-09-310.md`](rulings/2026-09-09-310.md) |
| 2026-09-10 | #311 | OWNER-RULING | **STANDING — FULL AUTONOMY TO THE 🟢 (CUSTOM-FILE)**: deploy → judge → re-issue → **confirm on the owner's behalf (d)** → certify → activate → the eleven-row diff on the **round-trip export** → 🟢, ONE report; pre-decided (a) principles (b) never withhold (c) fix the cause; STOP only for sudo / a secret in no container / an uncovered irreversible deletion. ⚠️ Recorded a day late, before any act under it. ⚠️ **The owner's fresh visit is NOT waived**: it stays his, reported as what remains | [`2026-09-10-311-312.md`](rulings/2026-09-10-311-312.md) |
| 2026-09-10 | #312 | RECORDED | **STANDING** — decided under #311(a), #311(b) and #311(d): the ten re-proposed rows on `d2120cdd`: **seven confirmed as proposed** (Referring MD, Patient, Age, PSH ×3, Marital, each by name and never in bulk per #261), because acceptance rows 2/3/7/9 and #246/#247 require those fills; **Telehealth consent and Total minutes ×2 → `manual`, no concept, NULL policy**: telehealth because no concept exists and `manual`+`omit` is unwritable, total time by **amendment 3** because three refutation rounds broke #314's grounding guard at the class level, so the machine never prints the figure and the doctor fills it by hand, as on the active form today; acceptance row 8 moves to what remains and #314 is deferred, no longer a precondition. ⚠️ **Amended before landing:** the telehealth line is never printed and CANNOT be inserted at review, exactly as on the active form today (gap FILED); #313's one-item-per-bullet distribution precedes activation. ⚠️ The judgement's "keep eight manual" recommendation is DECLINED | [`2026-09-10-311-312.md`](rulings/2026-09-10-311-312.md) |
| 2026-09-10 | #313 | RECORDED | **STANDING** — **ONE ITEM PER BULLET**: a form's repeated list-valued bullets each get one dictated item, nothing dropped, nothing printed twice; one pass in `prepareTemplateTwinFill` AFTER the bridge and BEFORE overrides; groups are narrow (same part/alias/tag, sole control in its paragraph via a new stripped IR property, one unbroken run, same scaffold, identical mappings), and a doubt refuses the WHOLE group; K>N joins the remainder into the last bullet; unused bullets are cleared as `list_item_slot_unused`; the pass self-validates and collapses rather than ever withholding. ⚠️ Measured live: PMH ×3, Impression ×4 and Plan ×5 each print the whole list today. O1–O5 decided under #311, class (a); the render is still owed to the owner's eye. The draft's IR gains the property by a declared act; the active version is untouched | [`2026-09-10-313.md`](rulings/2026-09-10-313.md) |
| 2026-09-11 | #315 | OWNER-RULING | **STANDING — TOKEN-1**: scaffold text carrying a CLOSED, REGISTERED token set (`{patient}`, `{age}` today) is substituted DETERMINISTICALLY from the visit record at FILL time, NEVER by the model; an unresolvable token renders the field BLANK with a NAMED reason (the whole scaffold-default insert declines — no half-substituted sentence); the manifest records each substitution; the certification self-test covers it; a GATE arms on the EXPORT BYTES that no brace placeholder reaches a rendered document. ⚠️ From the owner's first real visit. Seam: the `scaffold_default` arm of `applyClinicianOverrides`, a pure string op keeping `clinician_correction` sourceType (so #247 holds); substitution reads name + `ageAtDateResolved` from the record — no `visit_record` fact. ⚠️ Reading of "renders blank" is FIELD-level (decline the insert), NOT token-level (empty substring), because a malformed clinical sentence is worse than a blank; owner may reverse. WHY the braces printed at all is filed separately (WHY-1): the panel INSERTED the scaffold verbatim, it was not an unfilled render | [`2026-09-11-315-316.md`](rulings/2026-09-11-315-316.md) |
| 2026-09-11 | #316 | OWNER-RULING | **STANDING — PANEL-1 (REVIEW-DEFAULTS)**: the "Your blanks" panel (a) never offers a control whose scaffold is FURNITURE (underscores/dashes/whitespace only); (b) MERGES identical scaffold texts into one row with a count; (c) renders COLLAPSED by default as a single line "N blanks — review" (counting blank CONTROLS, not wordings) with "Insert all my defaults" as the primary action; (d) does not offer controls TOKEN-1 auto-fills — those are record-derived (visit_metadata) concepts, already excluded because they are never blank; ⚠️ a token-BEARING dictation scaffold is KEPT (it inserts safely via TOKEN-1 substitution — dropping it by scaffold-shape would blank a fillable control, per the adversarial pass). The per-visit, per-field click STAYS — an undictated exam is never printed automatically, one audit row per field. ⚠️ From the owner's first real visit. (a)/(d) live in `scaffoldDefaultOfferable` (offer=write door); (b)/(c) in the builder + client; furniture/token-only share the pure leaf `scaffold-text.ts` with TOKEN-1 | [`2026-09-11-315-316.md`](rulings/2026-09-11-315-316.md) |
| 2026-09-12 | #317 | OWNER-RULING | **STANDING — SLICE-0 COLON OPERATIVE-NOTE TWIN**: the owner's colon operative-note form is made to work end-to-end as a native DOCX Template Twin, certified through the real path (compile → confirm mappings → synthetic round-trip test → `certifyAndActivateTemplateTwin`), as the GI (WM IOV) form was. Controls: one per LABEL (Patient Name, DOB, ID, Date of Surgery, Surgeon), per SECTION BODY (Procedure, Preoperative Diagnosis, Consent, Description of Procedure, DD, DT), per NUMBERED SLOT (Findings 1–3, Recommendations 1–3 — identical aliases compile to distinct fields because `fieldId` is position-salted). ⚠️ SOURCE SUBSTITUTION: the owner named `colon_questions_only.pdf`, which was NOT retained by the upload path (measurement `board/PDF-UPLOAD-NOT-RETAINED-20260912.md`); owner confirmed building from the committed blank `colon_blank_answers.pdf`, whose structure is identical. Produced ONCE, pinned by sha; FIVE additive proofs (build-time, deterministic, occurrence-asserted; pattern from `regenerate-consult-form.ts`, NOT owner-quoted) | [`2026-09-12-317-318.md`](rulings/2026-09-12-317-318.md) |
| 2026-09-12 | #318 | OWNER-RULING | **STANDING — TEMPLATE-CHOICE-1, AND IT RE-OPENS A RULING**: a practice may hold several CERTIFIED templates; the visit shows a PICKER (default = the practice's default template); the chosen template is recorded on the visit; the fill uses the chosen twin. ⚠️ RE-OPENS the 2026-09-04 RULED doctor-scoped `note_templates` decision (`gate-practice-scope` GATE 0.3) FOR CERTIFIED-TEMPLATE CHOICE ONLY: the worker-honor + fill are already practice-scoped (#302), so this widens the request-context PICKER list and the PERSIST guard (`resolveRequestedTemplate`) from `doctorId` to `practiceId` + a certification filter; authorship and the per-doctor `resolveActiveTemplate` fallback stay doctor-scoped. Practice default = net-new nullable `Practice.defaultNoteTemplateId`, set by a practice OWNER (sign-route pattern: DB read → fail-closed → refuse by name → audit), falling back to today's resolution when unset. Deeper admin-console integration is the ADMIN lane's, filed not built | [`2026-09-12-317-318.md`](rulings/2026-09-12-317-318.md) |
| 2026-09-16 | #326 | OWNER-RULING | **STANDING — ONE PIPELINE FOR EVERY UPLOADED FORM (render → detect → map → fill → certify)**: retire the structural-twin derivation for prose Word + PDF and the pdf-native anchor/styled re-render. New pipeline: (1) normalize every upload to rendered PDF pages (Word via the existing Gotenberg converter — the pages ARE the layout); (2) detect fields on the pages with CommonForms/FFDNet self-hosted (label from nearest text); (3) map fields to the note model with AI once per template, doctor approves a sample-value preview; (4) fill values into the detected boxes with pdf-lib every visit, continuation page on overflow; (5) certify = every box fills on the synthetic visit AND the page is pixel-identical outside the boxes. Word-with-controls forms (the GI consult, the colon operative twin) KEEP WORKING until migrated. PROOF FIRST, no deploy; then migration in slices, each with its adversarial pass. ⚠️ Migrating an upload path is a clinical-surface change — adversarial pass per slice; owner acceptance test (class c) before any real doctor form cuts over. | [`2026-09-16-326.md`](rulings/2026-09-16-326.md) |
| 2026-09-15 | #325 | OWNER-RULING | **STANDING — S2 PDF NUMBERED-SLOT SECTION BINDING (+ DD/DT + PREOP)**: owner-directed slice (the "build the S2 slice" answer, 2026-09-15) closing the three S2-derivation gaps the RULING C inspect rehearsal surfaced — the colon PDF certified the colon SECTIONS (REGISTRY-3/#324) but could not AUTO-CERTIFY because (1) the POSTOPERATIVE FINDINGS / RECOMMENDATIONS numbered slots derived as bare `Fill-in` controls with no concept, (2) `DD (dictated)`/`DT (transcribed)` missed the visit-metadata regex, (3) PREOPERATIVE DIAGNOSIS was left prose by #324's writing-gap bar. Fix: a recognised colon-less operative heading (`SECTION_HEADING_CONCEPTS`) stamps a `pdfsec:<concept>` **`w:tag`** on its marker slots (alias stays `Fill-in` — pdf-native anchoring zips by ORDER over the original markers, untouched); `compilerDecidedConcept` reads the tag; the derivation emits each slot as a SOLE control so the slots bullet-group (G3/G4) and DISTRIBUTE one item per slot; `bullet-groups`' union-find skips the generic `Fill-in` alias. DD/DT regex admits the literal parenthetical clarifier (constrained). A single-valued operative section past the title zone is fielded BY NAME (closed set + depth) as one block control, concept on the tag — no geometry change, no new title over-derive. ⚠️ Own adversarial pass (clinical-generation path) | [`2026-09-15-325.md`](rulings/2026-09-15-325.md) |
| 2026-09-15 | #324 | OWNER-RULING | **STANDING — S2 AFFORDANCE AMENDMENT: A BOLD HEADING + EMPTY MULTI-LINE GAP IS ONE MULTI-LINE CONTROL**: amends #320 — a bold heading followed by an empty MULTI-LINE GAP (CONSENT, DESCRIPTION OF PROCEDURE — free-prose sections with a heading + blank space beneath) derives ONE multi-line control; a heading with NO gap stays prose. Closes the twin-completeness gap S2-4 (#322) surfaced: these sections were left as prose (no affordance) and absent from the twin export; now the twin fields them and the doctor's page fills them. The empty vertical gap beneath the heading IS the affordance (down to the next line box / bottom); it materialises so the hardened S1 `deriveProseTwin` yields ONE control whose value flows BELOW (a block control, matching S2-4 block placement). ⚠️ Own adversarial pass | [`2026-09-15-323-324.md`](rulings/2026-09-15-323-324.md) |
| 2026-09-15 | #323 | OWNER-RULING | **STANDING — REGISTRY-3: THE COLONOSCOPY-SPECIFIC CONCEPTS ARE REGISTERED, EACH FULLY WIRED**: register `procedure.bowel_prep` (with a BBPS score), `procedure.extent_of_exam`, `procedure.specimens` (a LIST), `procedure.estimated_blood_loss`, `procedure.complications` (`procedure.anesthesia` already exists — the template). Each new concept is wired across ALL FIVE dimensions: (1) L3 field (`encounter-facts` + L3 schema/prompt), (2) proposer guidance (`semantic-mapping`, accurate enough auto-certify does not decline on a wrong mapping), (3) projector (`field-value-derivation`; `specimens`→LIST, `bowel_prep`→BBPS), (4) self-test sentence (`verification-encounter`, the synthetic round-trip), (5) partition (`concept-registry` membership). `"Electronically signed by"` is RECORD-DERIVED — the signing doctor (visit-record filled, never dictated, exempt from the synthetic round-trip like `procedure.surgeon`). ⚠️ Own adversarial pass (clinical-generation path) | [`2026-09-15-323-324.md`](rulings/2026-09-15-323-324.md) |
| 2026-09-14 | #322 | OWNER-RULING | **STANDING — S2-4: THE PDF-ORIGIN VISIT EXPORT IS THE DOCTOR'S OWN PAGE, DRIVEN BY THE CERTIFIED TWIN'S VALUES**: for a PDF-origin template the visit export renders on the ORIGINAL PDF page (the pdf-native coordinate fill) using the CERTIFIED TWIN's field values — the twin decides WHAT fills, the doctor's page decides HOW it looks. Today the two are disjoint: `nativePdfExport` fills the original page but from a NOTE-HEADING split (`buildPdfFillTexts`), never the twin; twin values are keyed by `fieldId` and render only as a structural DOCX→Gotenberg. The only shared signal is the LABEL, so a LABEL bridge maps the twin's `FieldResolution[]` (joined to field-definition labels) onto the pdf-native anchors. The STRUCTURAL styled render becomes the FALLBACK only, with a NAMED REASON, when a value cannot be placed (overflow beyond the continuation rule, or a control with no anchor) — no clinical value dropped. PREVIEW and EXPORT share one renderer: the settings sample preview and the visit export are the same original-page fill. Flag-gated + fail-safe; twin-driven values fire ONLY for a CERTIFIED twin (uncertified → current behaviour). ⚠️ The owner's own colon twin is compiled (21 fields) but 0 certifications — S2-4 cannot fire live until panel-confirm; proven here on the colon form as a FIXTURE. ⚠️ Own adversarial pass | [`2026-09-14-322.md`](rulings/2026-09-14-322.md) |
| 2026-09-14 | #321 | OWNER-RULING | **STANDING — MATERIALISED FILL-LINE IS THE BLANK STATE**: #320 shipped with the materialised underscores ON the label (a filled twin showed "PATIENT NAME: ______John"). Owner REVERSES that acceptance: a materialised line is shown when the field is BLANK and REPLACED by the value when filled — never both; the 19-control count stands. The line moves OFF the label INTO the control content — the renderer replaces the whole `w:sdtContent` on fill (#164), so filled = value alone, blank = line; the SAME shape #317 + the integration fixtures already use; underscores are furniture (#316), so a blank field showing the line is a blank not an undictated default. S2 ONLY (the synthesised twin); an S1 doctor-uploaded DOCX keeps byte-preservation (invariant #1). BUILD: `pdf-form/fill-line-blank-state.ts` relocateFillLinesToBlankState (strip label underscores + set control content to the line), self-verifying via the keystone + fail-safe to the untransformed twin; wired into create-draft on the wasPdf path. ⚠️ Own adversarial pass | [`2026-09-14-321.md`](rulings/2026-09-14-321.md) |
| 2026-09-14 | #320 | OWNER-RULING | **STANDING — S2 PDF BLANK-AFFORDANCE AMENDED + PREVIEW NEVER EMPTY**: the owner's uploaded `Colonoscopy_Operative_Template.pdf` derived 0 controls (bare `LABEL:` lines, no underscore run) → quarantined → blank flat-PDF preview. MEASURED: the form draws NO visible rule lines (46 of 48 horizontal segments are WHITE field-box backgrounds; 2 are the page frame) and is single-column — so a "detect drawn rule lines" rule would still derive 0. RULE (owner-confirmed post-measurement): a blank affordance is EITHER (a) a colon/numbered label with an EMPTY WRITABLE SPAN (rest of row to the right margin, or blank line(s) below before the next label) OR (b) a drawn rule line (vector OR text underscores) following a label; "never invent a blank" → "never invent one without an affordance"; two-column rows → two controls in reading order. The PREVIEW never renders empty — 0 controls or a render failure shows the reason + derived count. BUILD: PDF→prose becomes geometry-aware and MATERIALISES the affordance as an underscore run, so the hardened S1 `deriveProseTwin` derives it unchanged (keystone-verified); S1's label-shape guards + the confirm step backstop precision. Re-derive the owner's upload and report the count vs ~22. Target = #317's 17-control hand-built equivalent, now automatic. ⚠️ Own adversarial pass | [`2026-09-14-320.md`](rulings/2026-09-14-320.md) |
| 2026-09-12 | #319 | OWNER-RULING | **STANDING — REGISTRY-2 (operative-note family)**: the closed registry gains `procedure.*` — `procedure.performed`, `preop_diagnosis`, `findings` (ACCUMULATES), `consent`, `description`, `recommendations` (ACCUMULATES), `anesthesia` (if dictated) — each with an L3 extraction field, prompt guidance, projector, self-test sentences, and its SINGLE/ACCUMULATES partition; polarity STATED not inferred for lists. Record-derived (`visit_record`): `procedure.surgeon` = signing doctor's name (a clinician name IS permitted — record-derived, not model-asserted, so #127 holds), `visit_metadata.date_of_service` = visit date, `patient_id` = record MRN else blank-with-reason, `DD`/`DT` = system timestamps. Then re-propose 5091c82c's 17 mappings under the new registry, auto-confirm per the confidence rule, certify (real path), supersede PDF-native `cmtxznk2u001v…`, keep GI `3877d5cf` as the practice default, judge. Own adversarial pass | [`2026-09-12-319.md`](rulings/2026-09-12-319.md) |
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

| 2026-10-09 | QuillMD testing authority | OWNER-RULING | **STANDING** — necessary purposeful paid QuillMD testing has no monetary or cumulative call ceiling; explicit standing-authority mode, immutable purpose/accounting, existing synthetic/provider/access safeguards; historical finite approvals and unknown $0.10 hold preserved. | [`2026-10-09-quillmd-standing-testing-authority.md`](rulings/2026-10-09-quillmd-standing-testing-authority.md) |
| 2026-10-10 | QuillMD account recovery | OWNER-RULING | Recover the actual existing account or provision a separate synthetic doctor if recovery cannot promptly complete; secure usable credential delivery, canonical fresh-browser proof and demonstrated recovery-flow repair; preserve records, permissions and MFA. | [`2026-10-10-quillmd-account-recovery.md`](rulings/2026-10-10-quillmd-account-recovery.md) |
