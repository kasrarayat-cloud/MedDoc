# Round eight on #1018, round five on #1036 — the report that did not exist

**Run 2026-09-07T22:47Z → 23:54Z. Ordered by ruling #260, judged under #254.**
12 refutation lenses (6 per PR), each in a write-sealed sandbox at a pinned SHA;
every finding then put to **3 independent adversarial verifiers** with distinct
angles (reproduce-or-kill · already-handled · classification). **108 agents,
106 completed, 2 verifier calls failed** — both on findings that still carried
two voters, so no finding was decided by fewer than two.

**32 raw findings → 4 refuted by verifier majority → 28 survivors.**

| PR | survivors | CODE | INSTRUMENT | verdict under #254 |
|---|---|---|---|---|
| **#1018** | 8 | **1** | 7 | ⛔ **DRAFT HELD** — not instrument-only |
| **#1036** | 20 | **8** | 12 | ⛔ **DRAFT HELD** — not instrument-only |

⚠️ **THE ROUND DID NOT RELEASE EITHER DRAFT, AND THAT IS THE RESULT — NOT A
FAILURE OF IT.** #254's exit condition is *instrument-only*. Both PRs carry code
defects, so the rule that would have released them does not apply. Two of those
defects were reproduced BY THE ORCHESTRATOR, from scratch, before being believed.

---

## Why this file exists at all

Round eight had already been RUN before this session opened, and its repairs are
on the branch as `78213067`. **Its report does not exist.** The lens sandboxes
were reaped, the session log is gitignored, and what survives is a commit message
asserting what the round found. So the round could not be audited by anybody who
did not run it, and its repairs — which changed the instruments — had never been
examined by anything.

That is the same defect as a ruling that lives only in a transcript. The round
below was therefore re-run in full against the **current** head, and this file is
the artifact.

---

## CONFIRMED BY THE ORCHESTRATOR, not taken on a subagent's word

### 1 · `R5-RACE-1` — two legal concurrent owner demotions DEADLOCK, 10 of 10, at the DEFAULT isolation level

Reproduced independently on the isolated `meddoc-qa` stack with a self-built
fixture (practice with three active owners + one clinician), two connections
synchronised to a common wall-clock instant, ten trials:

```
trial 1..10: deadlock=1  owners_left=2      (every trial)
════ DEADLOCKS: 10/10 | both-demotions-landed: 0/10 ════
ERROR:  deadlock detected
DETAIL: Process 344859 waits for ShareLock on transaction 363552; blocked by process 344860.
```

Both writes are **unambiguously legal** — three owners, demoting one leaves two,
the invariant is nowhere near being touched. One of them is rolled back every
single time. No admin route retries `P2034`, so a real admin sees a 500 and the
write silently did not happen.

⚠️ **This needs no exotic isolation level.** It is READ COMMITTED, the default,
and it is the ordinary product action ADMIN-5 exists to provide.

**Fixture reaped; QA returned to its exact baseline (41 users, 42 practices).**

### 2 · `SF-1` — the insert door stamps the row with one practice and the signing path reads it with another

`set-template-control.ts:848` writes `create: { practiceId }`, where that
`practiceId` is the resolver's **RETURNED** value — `visit.user.practiceId`, the
AUTHOR's practice. The lock one line above correctly re-asserts
`session.user.practiceId`. Traced through every consumer of the table:

| consumer | practice used | source |
|---|---|---|
| preview / fill engine | **author's** | `preview-visit-document.ts:346` |
| **the insert door's WRITE** | **author's** | `set-template-control.ts:848` |
| **sign-time freeze** | **the tenant** | `sign-freeze.ts:105` ← fed `session.user.practiceId` from `sign/route.ts:659` |

⚠️ **AND THE DIVERGENCE IS A DESIGNED PRODUCT STATE, NOT A CORRUPTION.** The
schema says so in terms, at `TranscribeVisit.practiceId`:

> *"T3 — the visit's tenant. **DERIVED FROM THE PATIENT, never from the author.**
> A note belongs to the practice that owns the CHART: **a locum from practice B
> seeing a patient of practice A creates a note in A.** … Both paths agreed on
> all 26 rows at migration time and **NOTHING kept them agreeing**."*

So for a locum the doctor inserts a default, **sees it in the preview**, and the
freeze reads **zero** override rows — signing a document without content the
doctor asserted and watched appear.

⚠️ **THE "58 OF 58" MEASUREMENT IS THE COINCIDENCE, NOT THE DEFENCE.** The door's
own comment already says the equality is *"a property of the data, not of the
code, and exactly the kind of coincidence a guard must not rest on."* It says
that about the LOCK's argument, which #260 ratified as fixed. It does not say it
about **what the row is stamped with**, which is the half still open.

**Not fixed in this pass, deliberately.** Both repairs are one line and they point
in opposite directions — move the WRITE to the tenant, or move the FREEZE to the
author — and choosing between them decides *which practice owns a locum's
corrections*, on the signing path. See OPEN QUESTION below.

---

## #1018 — the seven INSTRUMENT survivors

| id | lens | what the proof cannot see |
|---|---|---|
| `F1` / `TRACER-1` / `FG-1` | matrix · tracer · false-green | **The resolver half is NOT traced.** CLAIM 4 said a Proxy traces both sides; the resolver side is a **member-expression regex over two `indexOf`-anchored byte ranges** of one file. A guard extracted into a helper — *this module's own idiom* — is invisible. Paired control, same guard two spellings: **inline → arm REDS**; **extracted → 50/50 and 892/892 green with a live offered-but-not-honoured lie**. Measured on shipped source: 4 reads inside the regions, **8 reads in the same file outside them**; `practiceDefaultResolution` is called from inside a region and sits wholly outside both |
| `F2` | matrix | **Clause 2 is half-applied.** `dataTypes` come from the compiler's table; `KINDS` is a hand-written literal nothing derives or checks — the same shape as the type list that killed 73.4% of rows |
| `FG-2` | false-green | the `status` column of every `OMIT_LADDER_PRE_CONCEPT` row is behaviourally live and **completely unasserted** — both directions of a flip survive 50/50 and 892/892 |
| `FG-3` | false-green | the fail-closed certification anchor checks the constant names **A** row, never **WHICH** row — repointing it skips the resolver's certification guard for four of five rungs |
| `TRACER-2` | tracer | *"varied"* is satisfied by 3 hand-picked values of an **unbounded** dimension, so a guard on an array's CONTENTS is invisible to both arms |
| `BB-1` | bundle | the only browser-bundle gate measures the **LEAF, not the SURFACE** — the exact 320 KB zod leak it was written after passes green when it lands one file over |

## #1036 — the eight CODE survivors, and what they share

Six of the eight are **one family**: the guard reads a count without holding a
lock that covers the rows the count is about.

| id | shape |
|---|---|
| `R5-RACE-1` | **lock ORDER** — the advisory lock is not the first lock taken, so two legal writes deadlock. *Default isolation. Confirmed by the orchestrator, 10/10.* |
| `MIG-1` `R5-RACE-2` `DOOR-1` | the **INSERT** door takes the advisory lock but no row lock, so at REPEATABLE READ the second writer serialises on the advisory lock and then counts on its **pre-wait snapshot** |
| `MIG-2` `DOOR-2` | `FOR UPDATE` **cannot lock a phantom** — a row a concurrent transaction has not yet made visible is not locked, so `members_left` is computed as 0 on a practice that has just acquired somebody to strand |
| `R5-RACE-3` | the harness's **1-second stagger structurally hides** `R5-RACE-1`: 0/6 deadlocks with the harness's choreography, **11/12 with a simultaneous start** |

⚠️ **THE MIGRATION CLAIMS THE OPPOSITE, IN ITS OWN COMMENT, AT `migration.sql:234`:**
*"So all three isolation levels are now safe, and the two that are not READ
COMMITTED fail LOUDLY rather than silently."* Five findings refute that sentence,
and `MIG-3` observes that **no proof anywhere runs a transaction above READ
COMMITTED** — so the claim was never measured at all.

⚠️ **AND THE ELEVATED LEVELS ARE NOT HYPOTHETICAL HERE.** `Serializable` is used
in five shipped places, including the signing route
(`api/visits/[id]/sign/route.ts:919`), `fill-engine.ts:871` and
`certification-lifecycle.ts:578,961`.

### the twelve INSTRUMENT survivors on #1036

`R5-RACE-4` / `V2` (same defect, two lenses): **`assert_savepoint_semantics` has
no positive control** — it reads 0 whether the lock was released **or never
acquired**, and passes even when the lock call errors outright. That is the
instrument ruling #260 ratified BY NAME as *"re-measured on every run"*: it is
re-measured, and it cannot say NO. · `V1` xmax is a PRESENCE detector, blind to
the lock's scope or strength · `V3` the orphan guard's lock arm asserts presence,
never ORDER — which is exactly what `R5-RACE-1` turns out to be · `V4`
`stripSqlComments` is **still** defeated by NESTED block comments · `V5` the
member-count arm asserts a SUBSET, so a strictly NARROWER predicate satisfies it
· `V6` / `FG-1` / `FG-2` the route arms prove `wouldStrandPractice` is CALLED —
passing it the **wrong user** survives the whole 6219-test suite, and deleting
the refusal branch survives too · `FG-3` neither count-shape arm reads
`practiceId`, so the friendly refusal can be scoped to the wrong practice.

---

## Refuted by verifier majority (2 of 3), recorded so they are not re-found

- *the resolver scopes the certified-twin lookup by the author's practice* (#1036 lens, 2/3 refuted)
- *every SQL arm reads the FIRST occurrence but Postgres applies the LAST* (2/3)
- *the gate binds to one hard-coded historical migration directory* (2/3)
- *no arm reads a DECISION in either trigger function* (2/3)

---

## OPEN QUESTION FOR THE OWNER — `SF-1`, and it is a product decision

**Which practice owns a locum's per-visit form-control corrections?**

Both repairs are one line and they are opposites:

- **(a) move the WRITE to the tenant** — corrections stay with the CHART. Matches
  T3's stated rule and makes the signing path correct as written; the preview and
  fill engine must move with it.
- **(b) move the FREEZE to the author** — corrections follow the DOCTOR. Matches
  the existing decision recorded at `preview-visit-document.ts:344` (*"the visit's
  own doctor, not the requester"*) and is the smaller diff, but it puts a
  non-tenant value on the signing path.

There is no ruled precedent and the two answers give a locum's signed document
different contents, so it is class **(a)** under STANDING AUTHORITY.

---

## What this round did NOT examine

- No production database was touched. The deadlock reproduction ran on the
  isolated `meddoc-qa` stack and its fixture was reaped to an exact baseline.
- `#1036` is **19 commits behind `origin/main`**; the round measured its own head,
  not the merge result. It must be merged forward and re-verified before judgement.
- The two failed verifier calls were on `TRACER-2` and `V5`; both still had two
  voters and neither was decided by a single voice.
