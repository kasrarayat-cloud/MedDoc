# RULINGS INDEX — every war-room decision, one line each



> ⚠️ **YOU CANNOT READ THIS FILE IN ONE READ.** ~372,000 characters against a
> 150,000-character read limit — about **40%** fits, and a ruling that does not
> fit is not a weaker ruling, it is an **absent** one.
>
> **GREP IT.** That is what STEP 0 and `AGENTS.md` both say, and it is the only
> access that sees every row. A read of the top is not a survey of the file.

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

**120 rulings.** `#93`–`#151` carry explicit ids — **59 distinct, no gaps and no duplicates** — and **54** legacy rows predate the numbering scheme and are addressed by subject. **48 are PROVISIONAL** — `MASTER.md` carries every one of those in the morning report).

> **ONE ROW PER RULING, IN THE RULING'S OWN WORDS.** What this file's title always
> claimed and, by 2026-08-26, no longer was: the *"Verdict, in one line"* column had
> become the full body — largest single row **10,330 characters**, file **375,008**
> against a 150,000-character read limit.
>
> ⚠️ **A ROW IS A POINTER, NEVER THE RULING.** If a row and its archived body
> disagree, **the body is right and the row is the defect** — fix the row.
>
> **Citations resolve unchanged.** 607 references across 234 files cite rulings **by
> number only**; none by path or line. The number is greppable here and in the body.

| date | ruling | verdict, genuinely in one line | full body |
|---|---|---|---|
| 2026-08-04 | **GATE 0.1** — the 12 `MEDDOC_PRO`-only accounts | Excluded from backfill, **deactivated**, rows retained, **no deletion**; owner veto window until the TE… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-05 | **GATE 0.1 veto** — the same 12 accounts | **Lapsed; owner confirmed in writing.** Deactivate all 12. ⚠️ SPEC §4.1 says four are `@meddoc.com` wit… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-04 | **GATE 0.2** — cross-app redirect users | Classify **by where clinical data lives**, not by entitlement; the query runs at migration time, never … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-04 | **GATE 0.3** — note templates | **PER-DOCTOR in TEAMS v1**; the unique index stays; practice-shared library is **post-TEAMS, flag-gated… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-04 | **GATE 0.4** — money | Integer **micro-dollars** ledger-wide; `cost_micro × 3 / 2` in integer math, half-up at the micro-dolla… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-04 | **GATE 0.5** — Resend | **Not metered.** Only per-run vendors produce `UsageEvent`s; the price table gains **PROVENANCE** per r… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-05 | **Exit gate 1** — `worker.ts:983` read-after-write | **Accepted for now, ASSIGNED to BILLING B1/B4.** Observability today; becomes an undercharge the moment… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-05 | **Exit gate 3** — `audit_logs` as an S4c exclusion | **Carried as a REQUIREMENT on T5/T7**, named by name with the S4c reasoning, so a later tidy-up cannot … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-05 | **T3 derivation** | `transcribe_visits.practiceId` derives from the **PATIENT**, not the author — the chart owns the note, … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **T4-b schema drift** — the prescribed fix | **Correction ratified.** Declaring `@@unique([doctorId, encounterType])` would create a FULL unique whe… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **T4 blocker** | **Ratified as a DEPENDENCY, not a missing test.** T4 stays PARTIAL until T5+T6 make the positive gate r… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **§4.1a — WHO MAY SIGN** | **The signer signs as themselves, always; no on-behalf-of.** OWNER and CLINICIAN may sign any UNSIGNED … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **§4.1b — WHO MAY READ** | **Read is PRACTICE-UNIFORM in v1.** OWNER, CLINICIAN and TECH all read the practice's clinical data; ro… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **§4.1c — the interim posture** | **SEE widened, DO did not.** T5 widened reads; every ACTION kept its author conjunct as a placeholder s… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **T6 role vocabulary** | **TWO AXES, NEW FIELD.** Practice role is a new enum `PracticeRole {OWNER, CLINICIAN, TECH}` on the Use… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **T6 backfill derivation** | Derives from **STRUCTURE, not the legacy label**: an active user with a practice → **OWNER**. Deactivat… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **`SUPER_ADMIN`'s tenant bypass** | **DIES, fail-closed.** No role bypasses the practice wall for clinical reads through the app | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **A migration must not DOWNGRADE anybody** | **STANDING MIGRATION PRINCIPLE**, generalised from T6's backfill. A backfill mints the capability peopl… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **Which actions are role-gated** | **SIGNING IS THE SOLE ROLE-GATED ACTION.** Delete / archive / edit are gated by PRACTICE MEMBERSHIP, co… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **No-downgrade applies to REACTIVATION** | Restoring an account sets `OWNER` **only where the row has a practice and no role** — never uncondition… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **Structural-only prod verification** | Where production's POPULATION cannot exercise a behaviour, prod gets **structural verification only** —… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **Platform-global `note_templates`** | **NULLABLE + a BICONDITIONAL CHECK**: `(doctorId IS NULL AND practiceId IS NULL) OR (both NOT NULL)`. A… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **The fail-closed rule's exclusions** | **THREE, each NAMED WITH ITS REASON** — `audit_logs` (system rows with no actor, S4c), `api_usage_event… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **The shape for owner-ruled PROD mutations** | **STANDING**: re-derive the population AT EXECUTION TIME (never copy it from the ruling) · prove EVERY … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-06 | **T5 tranche 2** | **Declare, do not migrate** — executes GATE 0.3. `doctorId` is strictly narrower than a practice predic… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **T7 index-name drift** | **The SCHEMA gains explicit `map:` names matching the database's ACTUAL objects. NEVER rename a live DB… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **F-TYPE's `$transaction` class** | **ONE architectural decision, not ~16 annotations.** Type the callback parameter as Prisma's transactio… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **`confidenceScores` Json null** | **Determined ON QA, never reasoned.** `DbNull` vs `JsonNull` are different values with different query … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-07 | **T2's repair is DONE, not pending** | **Corrected against the database.** 71 corrections, all 2026-08-04, 65 originals still wrong — matching… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | **`validateSession` FAILS CLOSED** | **One bounded immediate retry on a DB error, then REFUSE with temporarily-unavailable (503-class) seman… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | **B0 Q1 — mocked `ai_calls` rows** | **SUPPRESS, unchanged from today.** `ai_calls` is a REAL-VENDOR-CALLS-ONLY table and its header states … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | **A provenance column's DEFAULT must never be the TRUSTED value** | **STANDING.** `DEFAULT 'vendor'` is fail-open: any writer that never heard of the column silently asser… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | **B0 Q2 — usage rows MIRROR VENDOR CALLS** | **One row per CALL, not per stage.** L4b's k=3 ensemble emits **3** rows, each with its own request id … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | **B0 Q3 — the mock stays CONTENT-SENSITIVE** | `deterministicMdm`'s sensitivity is **load-bearing for the E/M movement gates** — recorded as a contrac… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | **THE REAPING MODEL — the loop LISTS, a supervised session DESTROYS** | **`shred` stays DENIED to the unattended loop: an unattended destroyer is the wrong risk.** The loop's … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-08 | **The five `@quillmd-test.local` prod accounts — CONTAIN, don't delete** | **Deactivate + revoke sessions, in one guarded transaction; delete nothing.** `isActive=false` on all f… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | **B1-b — `api_usage_events.requestId` goes NULLABLE with a provenance-t… | **(a) NOW, decidable without data:** the column becomes nullable and the CHECK ships in its **SAFE DIRE… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | **The sizing data is GENERATED, not awaited** | One sanctioned prod smoke on the **synthetic** account (standing rules: reset to baseline after, **audi… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | **A push to a branch with required runs MUST check in-flight BY COMMIT … | **Third occurrence of push-cancels-in-flight**, so it stops being advice and becomes a MUST in MASTER.m… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | **FIX-THEN-SMOKE — the capture gap closes BEFORE any measurement** | Thread `readAnthropicRequestId` into `llm-mdm.ts`, `embed.ts` and `whisper-batch.ts`, mirroring `anthro… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | **The Anthropic balance probe is APPROVED — one call, before the smoke** | Explicitly authorised, because the balance is **not discoverable read-only** (no balance API; preflight… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | **`runStaleVisitCleanup` — examine it BEFORE it stops being a no-op** | Named, small, rides with or after B1-b. **(a)** Document its scope and cascade set precisely, and state… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | **B2 — WHICH FAILURE BRANCHES METER, AND WHICH TABLE IS THE BILLING SOU… | **(a) A FAILURE BRANCH METERS IFF IT HOLDS VENDOR-REPORTED UNITS.** Of **14** enumerated failure branch… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-09 | **The durable meter's PROVENANCE REGIME begins at B0-a — no pre-regime … | **A legacy vendor cost stays legacy observability; it never becomes a meter row.** ⚠️ **THE DISTINCTION… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | **B3 — HOW A RATE IS SHAPED, WHEN IT STARTS, AND WHAT AN UNPRICED CALL … | Five decisions, taken together because they are one design. **(a) A RATE IS AN EXACT RATIONAL — `rateMi… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | **B4 step 1 — THE DEEPGRAM METER LABELS BECOME OBSERVATIONS, ON NEW ROW… | `buildDeepgramUsage` hard-coded `operation: 'transcribe_realtime'` and `modelName: 'nova-3-medical'`. B… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | **B4 step 2 — A STAGE-LEVEL MOCK SHORT-CIRCUIT SITS BELOW THE METER, AN… | `entailmentStage` returned all-entailed under `MOCK_AI_CALLS` **above** `modelClient`, so `tm_anchor_en… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | **A DEACTIVATED CREDENTIAL IS REPLACED ONLY WHEN THE CAPABILITY IT EXER… |  | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | **B4 step 3 — THE `judge` STAGE METERS UNDER MOCK, AND THE JUDGEMENT IS… | `callClaudeMdm` returned `null` under `MOCK_AI_CALLS` **before any meter ran**, so `judge` emitted **ze… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-10 | **B4 closing step — A PERMITTED ZERO IS NOT A PASS, AND TWO MORE HARDCO… | Four decisions. **(a) THE GATE DISTINGUISHES *COUNTED* FROM *PERMITTED*, AND EXITS 2 WHEN IT CANNOT TEL… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | **B4's closure — THE ANCHORED DRAFT IS A DIFFERENT NOTE, AND ITS SPANS … | Executes the closure ruling 86 NAMED and did not attempt (*"an anchored `tm_soap_draft` variant on the … | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | **B5 — THE LEDGER'S APPEND-ONLY GUARANTEE HAS EXACTLY ONE HOLE, AND THE… | Five decisions. **(a) APPEND-ONLY IS A TRIGGER, NOT A `REVOKE`.** RELAY's gate says "enforced at the DA… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | **B6 — WHAT AN UNPRICEABLE VISIT COSTS, AND WHY THE WRITER SHIPS UNWIRE… | Five decisions. **(a) A VISIT WHOSE USAGE CANNOT BE *FULLY* PRICED IS NOT CHARGED AT ALL — this is ruli… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | **B7 — AN INBOUND EVENT CARRIES ITS OWN MODE, SO `assertProdDatabase()`… | Five decisions, all made building the Stripe webhook + top-up writer. **(a) THE MODE RULE IS A TWO-SIDE… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | **#93 — B7 step 2 — THE PAYING PARTY IS THE SESSION'S, THE MODE RULE MI… | Five decisions, all made building the Checkout-session creator and the settings door. **(a) THE ROUTE A… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-11 | **#94 — B8 step 1 — ADMISSION JUDGES THE MONEY A DEBIT CAN REACH, AND A… | Five decisions, all made building the fail-closed balance block. **(a) ADMISSION IS JUDGED ON THE *SPEN… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | **#95 — B8 step 2 — THE DEBIT AND THE BLOCK LAND TOGETHER AND SHIP INER… | Five decisions, all made wiring the pipeline seam. **(a) ONE FLAG GOVERNS BOTH SEAMS, AND ITS DEFAULT I… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | **#96 — B7 step 3a — THE PROMO GRANT NEEDED A DRAW ORDER FIRST, AND THE… | Five decisions, all made discovering that the queue's next item could not do what the queue said it wou… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | **#97 — B7 step 3b — A GRANT IS A PROPERTY OF BECOMING A PRACTICE, NOT … | Five decisions, all made discovering that the queue's next item was scoped to a population that stops b… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | **#99 — B7 STEP 3c IS AUTHORIZED IN FULL BY THE OWNER, AND THE POPULATI… | **(a) THE AUTHORIZATION, VERBATIM, BECAUSE A PARAPHRASED MANDATE IS NOT A MANDATE.** The owner's words,… | [`2026-08-04--2026-08-12.md`](rulings/2026-08-04--2026-08-12.md) |
| 2026-08-12 | **#100 — THREE RATIFICATIONS, AND THE PUSH RULE STOPS BEING A RULE** — … | **(a) #99(e)'s THREE FINDINGS ARE RATIFIED, AND THE UNIQUE-VS-CHECK ONE BECOMES A PROCEDURE RATHER THAN… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-12 | **#101 — THE MERGE SIDE GETS THE SAME MECHANISM, AND SCRATCH GETS A NAM… | **(a) THE GAP IS CLOSED BOTH WAYS, AND THE SENTENCE LANDS EVEN THOUGH THE MECHANISM DOES TOO.** #100(b)… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-12 | **#102 — A RULED MUTATION GETS THE DEPLOY'S DECLARATION GATE, AND "EXIS… | **(a) THE FORENSIC CHECK RULING #101's OWNER ORDERED FOUND THE ORDER VIOLATED IN THE RECORD, AND THAT I… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | **#103 — THE INBOX: AN INTER-SESSION CHANNEL THAT DID NOT EXIST, AND TH… | **(a) THE FINDING THAT PRODUCED IT: THERE WAS NO INTER-SESSION CHANNEL AT ALL, AND ITS ABSENCE WAS ASSU… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-12 | **#98 — B8's QA BEHAVIOURAL PROOF — THE DEBT THAT WAS CARRIED FOUR TIME… | Four decisions, all made walking a visit end to end through the real worker with `BILLING_ENFORCED=true… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | **#104 — B8 step 3 — A FAILED VISIT IS FREE, AND THE ITEM SHIPS THE MEA… | Four decisions, all made wiring the failure path. ⚠️ **NUMBER MINTED AS #103, NOT #102, AND HERE IS WHY… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | **#105 — B8 step 3c — A PERMANENT FAILURE IS DISCARDED, SO "fail-fast" … | **THE DECISION: a `permanent` failure whose FAILED state persisted is handed to BullMQ as an `Unrecover… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | **#106 — CUSTOM-TEMPLATE FIDELITY: THE STATICS ARE ASSEMBLED, THE FILE … | Four decisions, taken after a real customer form was uploaded to production, a real transcription run, … | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-13 | **#106(g) — STATICS ARE GUARDED AT THE OUTPUT, NOT AT THE LAYER THAT WR… | **THE CLAUSE: an `always_include` region that code assembled must still be present, BYTE-FOR-BYTE, in t… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | **#107 — #106's DIAGNOSIS IS CORRECTED: THE PARAPHRASE WAS OURS, NOT TH… | **THE CORRECTION: `500 milliseconds` became `0.5 seconds` because OUR OWN CODE rewrote it before the pr… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | **#108 — CI'S PIPELINE SUITES RUN IN THE PRODUCTION FLAG UNIVERSE** — 🔵… | **THE ITEM: the gates that guard the clinical generation path must run in the configuration production … | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | **#109 — THE PRESCRIPTION SAFETY SURFACE IS DELETED, AND THE GATE COMES… | **THE DECISION, in the owner's own terms: the Prescription Safety surface is DELETED, not reskinned.** … | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | **#110 — THE SPECIALTY VOCABULARY BUNDLE MISSES THE SPECIALTIES THAT NE… | **MEASURED, not inferred:** `normalizeSpecialty('ultrasound')` → `'unspecified'` → **0 bundle terms**; … | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | **#112 — A NOTE'S OWN LIST NUMBERS ARE CONTENT, NOT STYLING** — ✅ **OWN… | **THE DECISION: the bytes the note stores — `1. 2. 3.` — are the record. A renderer that discards them … | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | **#113 — ONE BUILDER, ONE TRUTH: THE PDF EXPORT CONVERGES AND `generate… | **MEASURED: four surfaces, three builders.** Pre-sign preview = `generateVisitDocx` → Gotenberg → PDF. … | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | **#114 — THE SIGNED-VIEW DIVERGENCE IS UNEXPLAINED; BOTH PROPOSED MECHA… | **THE OWNER OBSERVED IT AND IT IS REAL:** after signing, the in-app rendering differs from the pre-sign… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | **#117 — THE ATTESTATION FOOTER SHIPS WITH F3, AND DRAFT MARKING IS RES… | **THE RETIRED BUILDER PAINTED IT AND THE CONVERGENCE DROPPED IT.** `pdf-generator.ts:1544` marked `Sign… | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-15 | **#116(c)-CORRECTED — THE GOTENBERG COST IS EVERY NON-SIDECAR ENVIRONME… | **THE DECLARED COST WAS UNDERSTATED.** #116(c) said *"a doctor cannot download a PDF while the sidecar … | [`2026-08-12--2026-08-15.md`](rulings/2026-08-12--2026-08-15.md) |
| 2026-08-14 | **#109(a) — #109's SCOPE IS AMENDED: THE MEDICATION LIST IS RESTORED, R… | **THE CORRECTION: #109 named the SAFETY surface; the component it named had TWO jobs.** Its host headin… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-14 | **#111 — AUTHORIZATION TRAVELS OWNER → SESSION DIRECTLY, NEVER THROUGH … | **THE DECISION: a peer session may carry reasoning, evidence and measurements; it may NEVER carry autho… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | **#115 — THE VISIT DATE IS THE ENCOUNTER'S DATE; `signedAt` BELONGS ONL… | **MEASURED, NOT THEORISED — this is F2's answer to #114.** Both surfaces call `previewVisitDocumentActi… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | **#115-b — `DD:` AND `DT:` ARE DICTATION AND TRANSCRIPTION DATES, AND #… | **FOUND BY THE MANDATORY ADVERSARIAL PASS; THREE OF FOUR INDEPENDENT LENSES CONVERGED ON IT.** `form-on… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | **#116 — F3's CENSUS FOUND FIVE CALLERS WHERE #113 NAMED ONE, AND TWO O… | **THE CENSUS #113 ORDERED, TAKEN BEFORE A LINE CHANGED, AND IT DOES NOT MATCH THE RULING'S OWN FILES CO… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | **#118 — RULING #117 CONTRADICTS ITSELF TWICE; CLAUSE (a) GOVERNS, THE … | Three determinations made building #117's footer, all forced by conflicts INSIDE #117, plus one new fin… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-15 | **#116-b — SITE 3 HAD A SECOND `sizeBytes` CONSUMER, IN AN AUDIT ROW, M… | **FOUND WHILE EXECUTING #116, BY READING THE SITE RATHER THAN THE CENSUS OF IT.** #116 recorded both de… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-16 | **#119 — THE `QUILLMD` WATERMARK IS NOT RESTORED ON THE CONVERGED PDF, … | **FOUND BY DIFFING THE RETIRED BUILDER'S JOB LIST AGAINST THE SURVIVING ONE, WHICH IS #109's OWN METHOD… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-16 | **#120 — THE VANISHED VISIT'S ACTOR IS THE BullMQ CLEANUP CRON, AND THE… | **F3's §2.5 row 5 was VIOLATED — 45 visits declared, 44 measured, hard-deleted with no audit row — and … | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-16 | **#121 — F10's ACCEPTANCE CRITERIA, SET BEFORE THE FIX IS DESIGNED SO I… | **F10 is real and structural:** `deploy-prod.sh:89-91` derives the declaration path from `git rev-parse… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-17 | **#122 — WHEN THE ARCHIVE RENDER BOUND ENGAGES, THE DOCTOR GETS A NAMED… | **F6.3 asked for a bound. A bound implies a TRUNCATION POLICY, and that half is product-shaped rather t… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-17 | **#123 — E/M DOES NOT BELONG ON A PROCEDURE OR OPERATIVE NOTE, AND THE … | **TWO PARTS, BOTH FOUND ON THE OWNER'S OWN EXPORTED PDF.** **(1) SKIN — the E/M "Documentation Level" b… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-17 | **#124 — A REPO-WIDE RUNS-API OUTAGE MUST NOT SHUT THE MERGE AND PUSH D… | **THE QUESTION.** F14-a routed the CITATION door around the repo-wide `/actions/runs` route after it 40… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-18 | **#125 — F12 SPLITS: THE POLICY HALF SHIPS ALONE, AND THE SKIN HALF IS … | **THE QUESTION.** #123 says its two parts *"ship together"*. They cannot, and the reason is #123's own … | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-18 | **#126 — THE NOTE-SHAPE SUPPRESSION MUST NOT HANG ON A LIVE RELATION, A… | **TWO DECISIONS, ONE FROM F12-a's OWN PASS AND ONE FROM THE INDEPENDENT PASS IT OWED.** **(a) THE FALLB… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-17 | **#127 — AUTO-CERTIFICATION BY AI IS THE DEFAULT PATH, AND THE MODEL NE… | **THE RULING: on upload, when the twin compiles with ZERO blocking elements, the AI CONFIRMS ITS OWN PR… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-18 | **#128 — THE COMPUTE LAYER STOPS WRITING AN OFFICE E/M ONTO AN OPERATIV… | **THE QUESTION.** `packages/shared/src/specialties.ts:139-143` states the E/M invariant is enforced at … | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | **#129 — A RETIRED TEMPLATE DOES NOT OVERRULE THE DOCUMENT BEING SIGNED… | **THE QUESTION.** F12-a/F12-c hung the note-shape E/M axis on the TEMPLATE, which suppresses unconditio… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | **#130 — THE OFFICE COUNTERWEIGHT ACCEPTS SPELLINGS OF THE FOUR SOAP CO… | **THE QUESTION.** #126(b) installed the office counterweight: a label set carrying the full SOAP skelet… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | **#131 — `playwright install --with-deps` IS SPLIT INTO ITS TWO HALVES … | **THE QUESTION.** #739 has stalled the gate five times in two days and F12-g's unpark condition (*a gre… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | **#131(b) — THE INSTRUMENT ANSWERED ITS OWN QUESTION ON ITS FIRST RUN, … | ⚠️ **#131 SAYS "TWO CANDIDATES REMAIN". THAT IS NO LONGER TRUE, AND IT STOPPED BEING TRUE ABOUT FOUR MI… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | **#132 — THE NO-PROGRESS KILL SWITCH MEASURES THE LEDGER ON `origin/mai… | **THE QUESTION.** Run `20260818-232127-b1` halted on NO-PROGRESS at `12:44:53Z` having landed **three**… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-19 | **#131(c) — THE BOUNDED WAIT FIRED ITS OWN PREDICTION: THE APT TIMEOUT … | **THE OWED CORRECTION.** Session 04 of run `20260818-232127-b1` closed owing this in as many words: *"#… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-20 | **#133 — THE DOCX RENDERS EVERY MARKDOWN HEADING DEPTH, AND THE GATE TH… | **THE QUESTION.** F6.4 was filed as a TEST defect — *"`export-cleanliness`'s markdown detector is now V… | [`2026-08-14--2026-08-20.md`](rulings/2026-08-14--2026-08-20.md) |
| 2026-08-20 | **#134 — A DEPLOY REFUSES A COMMIT ITS OWN GATE HAS NOT SEEN, AND FAILS… | **THE INCIDENT, MEASURED.** `06:14:42Z` `e2e` created on `7c42d2d7` · `06:15:13Z` `secrets-scan` finish… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-20 | **#135 — F5-d: THE `GSV at the SFJ` REFUSAL IS A NUMERIC-TEXT MISMATCH,… | **REPRODUCED BEFORE ANY FIX, as the ruled acceptance shape (a) requires, and the reproduction REFUTED I… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-20 | **#136 — F5-d(b): THE SHARED DERIVATION SHIPS AS A TIGHTENING, AND THE … | **Implements ruling #135. Four decisions were made inside its ruled direction that are ruling-shaped in… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-21 | **#137 — ROLLBACK TAGS ARE PRUNED BY NAME, NEVER BY `-a`, AND PREFLIGHT… | **THE FINDING THAT PRODUCED IT.** Preflight's Check 2 auto-fix triggered on 2026-08-21 (images reclaima… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-21 | **#138 — `f5c-refute` IS PLAIN-`rm` SCRATCH, AND THE PERMISSION DENIAL … | **THE STATE.** `…/scratchpad/f5c-refute` is a **150M plain directory SNAPSHOT of the repo** — the liabi… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-21 | **#139 — F5-i PART 1 SPLITS INTO 1a / 1b, AND 1a IS TAKEN NOW** — 🟡 **P… | **THE ITEM'S OWN CLOSE CONDITION WAS MADE UNREACHABLE BY ITS OWN PART 2, AND SESSION 01 FILED THAT AGAI… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-22 | **#140 — THE LABEL COLUMN IS RESOLVED FROM EVIDENCE, NOT GUESSED FROM T… | **THE DEFECT THAT PRODUCED IT, found by the loop's adversarial pass over F24-S3 and reproduced by the s… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-23 | **#141 — A CAPTION IS VALIDATED BY SHAPE ACROSS A PARAGRAPH BREAK, AND … | **THE QUESTION.** `captionFor` returned whatever line sat directly above a table header, with no test o… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-23 | **#142 — F24 DOES NOT CLOSE ON THE TABLE-BOUND HALF; THE ACCEPTANCE SEN… | **THE QUESTION.** The addressable census reached **52 of 52 table-bound cells on all three note shapes*… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | **#144 — THE BOUND IDENTITY WIDENS TO NOTE + OVERRIDES; THE FRESHNESS G… | **THE QUESTION.** The mandatory pass refuted F24-S5 (#825, ruling #143). Root cause verified in shipped… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | **#143 — A FORM CONTROL IS ADDRESSED BY A SERVER-ISSUED ORDINAL; AND A … | **THE QUESTION.** #142 opened F24-S5: the 28 enumerated content controls are the whole of F24's remaini… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | **#145 — THE PLACEHOLDER IS EXCLUDED WITHOUT RENUMBERING, AND THE EXCLU… | **THE QUESTION.** #144(d) orders Word's `Choose an item.` excluded from the compiled option set. The ob… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | **#146 — A CANCELLED RUN THAT A RE-RUN ALREADY REPLACED IS NOT A FAILUR… | **THE DEFECT, MEASURED LIVE ON THIS SESSION'S OWN QUEUE HEAD.** `gh-runs.sh cited` counted `status=="co… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-24 | **#147 — F24 CLOSES AT 75/80. THE ACCEPTANCE IS RESTATED AS *EVERY FIEL… | **THE QUESTION.** ITEM B measured the other 28 by replay and the joint census reads **75 of 80** (table… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-25 | **#148 — F8 SLICES. S1 IS THE DECISION SUBSTRATE, IT IS DELIBERATELY UN… | **THE QUESTION.** F8's contract (`docs/foundation/f8-icd-tab-design.md`) specifies a whole tab: a `Note… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-25 | **#149 — THE AMBER RULE GETS ITS SUBSTRATE; THE FOUR DROP EXITS STAY FO… | **THE QUESTION.** F8's contract carries an owner-decided rule — *SHOW, never hide*: a candidate the pip… | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-25 | **#150 — AUTHORITY LIVES IN EXACTLY ONE FILE. `AGENTS.md` § STANDING AU… | **THE QUESTION.** The loop found and NAMED a live contradiction rather than resolving it: `RELAY.md`'s … | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |
| 2026-08-26 | **#151 (PROPOSED — unlanded, refer to it as `feat/f29-orphan-branch-swe… | **THE QUESTION.** Canon's *"AN ENTRY THAT NAMES AN INSTRUMENT VERIFIES THAT INSTRUMENT'S GRANT, IN THE … | [`2026-08-20--2026-08-26.md`](rulings/2026-08-20--2026-08-26.md) |

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
