# RULINGS INDEX — every war-room decision, one line each

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

## The index

| Date | Ruling | Verdict, in one line | Full text |
|---|---|---|---|
| 2026-08-04 | **GATE 0.1** — the 12 `MEDDOC_PRO`-only accounts | Excluded from backfill, **deactivated**, rows retained, **no deletion**; owner veto window until the TEAMS migration runs | SPEC §4.1 |
| 2026-08-05 | **GATE 0.1 veto** — the same 12 accounts | **Lapsed; owner confirmed in writing.** Deactivate all 12. ⚠️ SPEC §4.1 says four are `@meddoc.com` with the operator's name; measured, **three** are | RELAY "TEAMS EXIT GATE" §4 |
| 2026-08-04 | **GATE 0.2** — cross-app redirect users | Classify **by where clinical data lives**, not by entitlement; the query runs at migration time, never copied from the doc | SPEC §4.2 |
| 2026-08-04 | **GATE 0.3** — note templates | **PER-DOCTOR in TEAMS v1**; the unique index stays; practice-shared library is **post-TEAMS, flag-gated** | SPEC §4.3 |
| 2026-08-04 | **GATE 0.4** — money | Integer **micro-dollars** ledger-wide; `cost_micro × 3 / 2` in integer math, half-up at the micro-dollar; **cent rounding at display only** | SPEC §4.4 |
| 2026-08-04 | **GATE 0.5** — Resend | **Not metered.** Only per-run vendors produce `UsageEvent`s; the price table gains **PROVENANCE** per rate | SPEC §4.5 |
| 2026-08-05 | **Exit gate 1** — `worker.ts:983` read-after-write | **Accepted for now, ASSIGNED to BILLING B1/B4.** Observability today; becomes an undercharge the moment B6 makes it a billing input | RELAY "TEAMS EXIT GATE" §1 |
| 2026-08-05 | **Exit gate 3** — `audit_logs` as an S4c exclusion | **Carried as a REQUIREMENT on T5/T7**, named by name with the S4c reasoning, so a later tidy-up cannot "fix" it and re-break account deletion | RELAY "TEAMS EXIT GATE" §3 |
| 2026-08-05 | **T3 derivation** | `transcribe_visits.practiceId` derives from the **PATIENT**, not the author — the chart owns the note, so a locum's note files under the chart's practice | RELAY T3 · migration header |
| 2026-08-06 | **T4-b schema drift** — the prescribed fix | **Correction ratified.** Declaring `@@unique([doctorId, encounterType])` would create a FULL unique where Postgres enforces a PARTIAL one, and production already violates the full form. Document the inexpressibility instead | RELAY T4-b drift table |
| 2026-08-06 | **T4 blocker** | **Ratified as a DEPENDENCY, not a missing test.** T4 stays PARTIAL until T5+T6 make the positive gate reachable through the real route | RELAY T4 |
| 2026-08-06 | **§4.1a — WHO MAY SIGN** | **The signer signs as themselves, always; no on-behalf-of.** OWNER and CLINICIAN may sign any UNSIGNED visit in the practice. **TECH is refused BY NAME, server-side, fail-closed.** `signedBy` is never client-supplied | SPEC §4.1a |
| 2026-08-06 | **§4.1b — WHO MAY READ** | **Read is PRACTICE-UNIFORM in v1.** OWNER, CLINICIAN and TECH all read the practice's clinical data; role boundaries live on **ACTIONS, not visibility**. Narrowing TECH is its own designed item (assignment + worklist), never a bolted-on filter | SPEC §4.1b |
| 2026-08-06 | **§4.1c — the interim posture** | **SEE widened, DO did not.** T5 widened reads; every ACTION kept its author conjunct as a placeholder standing exactly where the role check goes. **T6 removes them, by this ruling** | SPEC §4.1c |
| 2026-08-06 | **T6 role vocabulary** | **TWO AXES, NEW FIELD.** Practice role is a new enum `PracticeRole {OWNER, CLINICIAN, TECH}` on the User↔practice edge — **never values added to `UserRole`**, which conflates a clinical axis with a platform-privilege one and cannot express ownership. `UserRole` survives as the legacy platform axis, **do-not-extend** | SPEC §1.2 · `20260806220000_practice_role` |
| 2026-08-06 | **T6 backfill derivation** | Derives from **STRUCTURE, not the legacy label**: an active user with a practice → **OWNER**. Deactivated / practice-less → NULL, and a CHECK says so. Real CLINICIAN/TECH arrive only via T8 invites. ⚠️ The ruling's premise (*"every active user is the sole member"*) was measured FALSE — 18 of 196 are in multi-member practices; the stated rule for them is in the migration header | migration header · RELAY T6 |
| 2026-08-06 | **`SUPER_ADMIN`'s tenant bypass** | **DIES, fail-closed.** No role bypasses the practice wall for clinical reads through the app | SPEC §1.2 · RELAY T6 |
| 2026-08-06 | **A migration must not DOWNGRADE anybody** | **STANDING MIGRATION PRINCIPLE**, generalised from T6's backfill. A backfill mints the capability people already have; narrower assignments arrive via invites and administration, **never a backfill's guess**. ⚠️ Ratified together with the correction that produced it: the T6 ruling's premise (*"every active user is the sole member of their practice"*) was **measured false** — 18 of 196 sit in multi-member practices — and all 196 take OWNER | `20260806220000_practice_role` header · RELAY T6 |
| 2026-08-06 | **Which actions are role-gated** | **SIGNING IS THE SOLE ROLE-GATED ACTION.** Delete / archive / edit are gated by PRACTICE MEMBERSHIP, consistent with §4.1b — role boundaries live on actions, and only `sign` is ruled. Tech-creates/doctor-signs requires every member to prepare work. **Future action-gating gets ruled when a real need names it**, never inferred | SPEC §1.2 · §4.1a · RELAY T6 |
| 2026-08-07 | **No-downgrade applies to REACTIVATION** | Restoring an account sets `OWNER` **only where the row has a practice and no role** — never unconditionally, which would overwrite a real CLINICIAN/TECH assignment with an owner's rights on un-suspension. Corollary of the standing no-downgrade principle | `system-admin/actions.ts` · AGENTS.md |
| 2026-08-07 | **Structural-only prod verification** | Where production's POPULATION cannot exercise a behaviour, prod gets **structural verification only** — no mutation, no synthetic account minted to watch a gate refuse. The behavioural proof lives on the CI/QA seat that exists for it. Reference: prod holds zero TECH users, so the sign gate's three-direction proof stays in QA | RELAY T6 · AGENTS.md |
| 2026-08-07 | **Platform-global `note_templates`** | **NULLABLE + a BICONDITIONAL CHECK**: `(doctorId IS NULL AND practiceId IS NULL) OR (both NOT NULL)`. A template has a practice **iff** it has a doctor — forward closes the derivation gap, reverse forbids an orphaned tenancy claim on platform content. **Sentinel practice REJECTED**: an invented tenant every query must remember is the hand-kept-list failure mode in schema form | SPEC §1.5 · `20260807…_t7_tenancy` |
| 2026-08-07 | **The fail-closed rule's exclusions** | **THREE, each NAMED WITH ITS REASON** — `audit_logs` (system rows with no actor, S4c), `api_usage_events` (same class, telemetry), `note_templates` (platform-global content). A reason-less exclusion is a hole with a label | SPEC §1.5 |
| 2026-08-07 | **The shape for owner-ruled PROD mutations** | **STANDING**: re-derive the population AT EXECUTION TIME (never copy it from the ruling) · prove EVERY abort guard fires · prove the happy path on synthetics · reap to zero residue · transactional with verification before COMMIT. Reference: GATE 0.1's deactivation. **Cite it for BILLING's ruled mutations** — price-table seed, promo grants | `scripts/execute-gate0-deactivation.sql` |
| 2026-08-06 | **T5 tranche 2** | **Declare, do not migrate** — executes GATE 0.3. `doctorId` is strictly narrower than a practice predicate, so migrating templates would WIDEN them | RELAY T5 "TRANCHE 2 EXECUTES GATE 0.3" |
| 2026-08-07 | **T7 index-name drift** | **The SCHEMA gains explicit `map:` names matching the database's ACTUAL objects. NEVER rename a live DB object for a convention's sake** — that is a needless migration over a working index. 8 objects (4 twin indexes + 4 FKs); the other 5 T7 indexes already match Prisma's convention | RELAY "CARRIED OUT OF T7" |
| 2026-08-07 | **F-TYPE's `$transaction` class** | **ONE architectural decision, not ~16 annotations.** Type the callback parameter as Prisma's transaction-client shape — **never `typeof prisma`**, which is the full client, fails the callback overload, and makes TS infer `any[]` from the ARRAY overload. Applied everywhere in one commit | RELAY F-TYPE |
| 2026-08-07 | **`confidenceScores` Json null** | **Determined ON QA, never reasoned.** `DbNull` vs `JsonNull` are different values with different query semantics; production cannot settle it (the reset is always overwritten). Write the bare null through the typed client, read back what landed, then choose | RELAY F-TYPE |
| 2026-08-07 | **T2's repair is DONE, not pending** | **Corrected against the database.** 71 corrections, all 2026-08-04, 65 originals still wrong — matching the SECURITY BLOCK row. ⚠️ Re-running an APPEND-ONLY repair does not no-op: it writes 71 duplicates. The property that makes it safe once makes it unsafe twice | RELAY T2 |
| 2026-08-08 | **`validateSession` FAILS CLOSED** | **One bounded immediate retry on a DB error, then REFUSE with temporarily-unavailable (503-class) semantics — NEVER a 401.** A 401 is a claim about the CREDENTIAL: every client discards the session, so a transient pool blip becomes a re-login for every clinician. A 503 is a claim about the SERVER: the credential survives and the client retries. **Fail-closed and sign-everyone-out are not the same posture.** Reverses both silent fail-opens. Implementation is its own item; size the retry budget from `SESSION_FAILOPEN` counts | RELAY "AUTH FAIL-CLOSED" · `lib/auth.ts` · `packages/auth/src/index.ts` |

## What is NOT in here, deliberately

**Engineering lessons are not rulings.** The canon in `AGENTS.md` — the
write-path sweep, title-narrower-than-measurement, the watched-set diff, scripted
edits proving their application — is how to do the work correctly, not a decision
about what the product is. Mixing them would make this file long enough that
nobody greps it, which is the only way it can fail.

The test is: **could a reasonable person have decided otherwise?** If yes, it is
a ruling and belongs here. If it is simply true, it is a lesson and belongs in
`AGENTS.md`.
