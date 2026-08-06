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
| 2026-08-06 | **T5 tranche 2** | **Declare, do not migrate** — executes GATE 0.3. `doctorId` is strictly narrower than a practice predicate, so migrating templates would WIDEN them | RELAY T5 "TRANCHE 2 EXECUTES GATE 0.3" |

## What is NOT in here, deliberately

**Engineering lessons are not rulings.** The canon in `AGENTS.md` — the
write-path sweep, title-narrower-than-measurement, the watched-set diff, scripted
edits proving their application — is how to do the work correctly, not a decision
about what the product is. Mixing them would make this file long enough that
nobody greps it, which is the only way it can fail.

The test is: **could a reasonable person have decided otherwise?** If yes, it is
a ruling and belongs here. If it is simply true, it is a lesson and belongs in
`AGENTS.md`.
