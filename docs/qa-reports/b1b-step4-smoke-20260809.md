# B1-b step 4 — the sanctioned production smoke

**Ruling 73 (2026-08-09):** *the sizing data is GENERATED, not awaited.* One
sanctioned smoke on the **synthetic** account drives real vendor calls through the
live meter and discharges three owed items at once — 1b's sizing
(`ai_calls.requestId IS NULL` frequency on real calls), *the meter is unproven in
production*, and B1-a's capture proven on a live call.

⚠️ **A real doctor's visit is never a smoke target, and this ruling does not
relax that.** The synthetic account is the whole permission.

---

## PART 1 — THE DECLARATION

**Written 2026-08-09T18:2xZ, BEFORE the first write, and committed before the
smoke ran.** The order is the point: a post-hoc check is unfalsifiable, and
`git log` on this file is the proof that every number below predates the evidence
it is judged against.

### Preconditions, all verified before writing this

| precondition | state |
|---|---|
| B1-b steps 1 + 2 live in production | ✅ deployed `d4e33c22` @ 18:18Z, 17 of 17 declaration rows judged |
| the capture gap is CLOSED in the running image | ✅ step 1 threads `llm-mdm.ts`, `embed.ts`, `whisper-batch.ts` — verified in the deployed tree |
| Anthropic balance is NOT exhausted | ✅ step 3 probe returned **HTTP 200** (`claude-haiku-4-5-20251001`, `max_tokens:1`) |
| the fixture is at baseline | ✅ 0 patients, 0 visits |

⚠️ **The blocker recorded at "B1-a CAPTURES THE VENDOR REQUEST ID IN
`anthropic.ts` AND NOWHERE ELSE" is what step 1 fixed and this deploy shipped.**
Running this smoke before that landed would have recorded *our own missing
capture* as the vendor's silence — the measurement would have been false, and
`api_usage_events` has **no deleter anywhere in the tree**, so a contaminated
sample would have polluted the sizing set permanently.

### Baseline, captured 18:2xZ (READ-ONLY, production)

Smoke practice `cmrzqiafm0000pd87qtubsj56` (`quillmd-smoke-practice`),
smoke user `cmrzqiarg0001pd872t815b12` (`smoke-doctor@smoke.quillmd.invalid`):

| quantity | value |
|---|---|
| smoke `transcribe_md_patients` | **0** |
| smoke `transcribe_visits` | **0** |
| smoke `ai_calls` | **487** |
| smoke `api_usage_events` | **451** |
| `audit_logs` for the smoke user | **974** |

Real clinicians' data — everything NOT in the smoke practice:

| quantity | value |
|---|---|
| `transcribe_md_patients` | **15** |
| `transcribe_visits` | **25** |
| visits with `signedAt` NOT NULL | **16** |
| `audit_logs` total (all practices) | **10 616** |

These four reproduce the RELAY's stated smoke baseline exactly
(`487` / `451` / `974`, and prod-wide `15 / 25 / 16`) — re-derived at execution
time rather than copied from the ledger, per the standing rule for owner-ruled
production writes.

### WHAT MUST CHANGE

| # | quantity | expected |
|---|---|---|
| 1 | smoke `transcribe_md_patients` | **0 → 1** |
| 2 | smoke `transcribe_visits` | **0 → 1** |
| 3 | smoke `ai_calls` | **487 → 487 + N**, `N > 0` |
| 4 | smoke `api_usage_events` | **451 → 451 + M**, `M > 0` |
| 5 | `audit_logs` | **may rise; NEVER falls** |

⚠️ **`N` and `M` are declared as bands, not points, and that is deliberate.** A
visit's call count genuinely varies with transcript length and retry behaviour
(the ledger's estimate is ~13–14). Declaring a false precision would manufacture
a finding out of normal variation. **What is declared strictly is the STRUCTURE
below** — and structure is what this smoke exists to measure.

### WHAT MUST NOT CHANGE — the abort guards

| # | quantity | expected | if violated |
|---|---|---|---|
| 6 | `transcribe_md_patients` outside the smoke practice | **15** | **ABORT** |
| 7 | `transcribe_visits` outside the smoke practice | **25** | **ABORT** |
| 8 | visits with `signedAt` outside the smoke practice | **16** | **ABORT** |
| 9 | `audit_logs` for the smoke user | **≥ 974, never down** | **ABORT** |
| 10 | every new `ai_calls` row | `practiceId` = the smoke practice | **ABORT** |
| 11 | every new `api_usage_events` row | `practiceId` = the smoke practice | **ABORT** |

### THE STRUCTURAL ASSERTIONS — what the smoke is actually FOR

| # | assertion | why it is the deliverable |
|---|---|---|
| 12 | **no new `api_usage_events` row has `unitsSource <> 'vendor'`** | this is a REAL run; a `mock` row would mean the mock boundary leaked into production |
| 13 | **no row anywhere violates `api_usage_events_request_id_requires_vendor`** | the CHECK shipped 5 minutes earlier and has never seen a live write |
| 14 | **`ai_calls.requestId` NULL-vs-present, BROKEN DOWN BY `purpose`** | ⚠️ **the deliverable.** A single blended figure hides exactly the per-path variation this whole sequence exists to expose |
| 15 | **`api_usage_events.requestId` NULL-vs-present by `operation`** | the same question on the meter's own table |

⚠️ **Row 14 is the one that decides ruling 72(b).** Whether `vendor ⇒ id` can
become strict — the full biconditional — depends on how often a real vendor call
genuinely yields no id. **Tightening is the allowed direction; loosening a
shipped constraint is the move this whole ordering exists to avoid having to
make.** So a single run that shows 100% present does NOT by itself justify
shipping the strict form — it is one sample, and step (b) is explicitly a
measurement question, not a one-run question.

### CLEANUP

Via **`clean.ts` only** — never a hand-written delete, and **never**
`runStaleVisitCleanup()`, which is not practice-scoped and would delete other
practices' soft-deleted visits.

**Audit rows are left in place** (standing rule). The telemetry rows are the
evidence and are NOT deleted — `ai_calls` survives its visit's deletion
(454+ of the fixture's rows are already orphaned and have persisted 15+ days),
and no deleter of `api_usage_events` exists anywhere in the tree.

### A difference not in these tables IS THE FINDING

Whatever its explanation sounds like after the fact.

---

## PART 2 — THE RESULT

*Written after the run. Everything above predates it; `git log` on this file is
the check on that claim.*

**Ran 2026-08-09T18:4xZ. Visit `cmsm4y2ro00010hqogjeg1x2v`, reached `READY`.**
13 AI calls, 13 meter rows, **$0.49**. Cleaned to baseline immediately after.

### THE DECLARATION, JUDGED — 15 of 15

| # | declared | measured | |
|---|---|---|---|
| 1 | smoke patients 0 → **1** | 1 | ✅ |
| 2 | smoke visits 0 → **1** | 1 | ✅ |
| 3 | smoke `ai_calls` 487 → 487+N, N>0 | **500** (N = **13**) | ✅ |
| 4 | smoke `api_usage_events` 451 → 451+M, M>0 | **464** (M = **13**) | ✅ |
| 5 | `audit_logs` may rise, never falls | 10 616 → **10 619**; smoke user 974 → **977** | ✅ |
| 6 | non-smoke patients **15** | 15 | ✅ |
| 7 | non-smoke visits **25** | 25 | ✅ |
| 8 | non-smoke signed **16** | 16 | ✅ |
| 9 | smoke-user `audit_logs` ≥ 974 | 977 | ✅ |
| 10 | every new `ai_calls` row in the smoke practice | total 1112 → 1125 (+13); **non-smoke 625 → 625** | ✅ |
| 11 | every new `api_usage_events` row in the smoke practice | global 1312 → 1325 (+13); smoke +13 | ✅ |
| 12 | no new row with `unitsSource <> 'vendor'` | global census `vendor\|1325\|0` — **no other bucket exists** | ✅ |
| 13 | nothing violates `…_request_id_requires_vendor` | 0 rows with a NULL id; all `vendor` | ✅ |
| 14 | `ai_calls.requestId` **by purpose** | below | ✅ |
| 15 | `api_usage_events.requestId` **by operation** | below | ✅ |

⚠️ **Row 10 is the abort guard that mattered, and it was checked twice** — inside
the script before and after the run, and again in SQL afterwards. Non-smoke
`ai_calls` sat at **625 both times**. No real clinician's practice was touched by
anything this smoke did.

### ROW 14 — THE DELIVERABLE. `ai_calls.requestId` BY PURPOSE

| purpose | provider | calls | **id present** | id NULL |
|---|---|---|---|---|
| `judge` | anthropic | 1 | **1** | 0 |
| `tm_anchor_entailment` | anthropic | 3 | **3** | 0 |
| `tm_cpt_coding` | anthropic | 1 | **1** | 0 |
| `tm_critique` | anthropic | 1 | **1** | 0 |
| `tm_entities` | anthropic | 1 | **1** | 0 |
| `tm_icd_coding` | anthropic | 1 | **1** | 0 |
| `tm_patient_summary` | anthropic | 1 | **1** | 0 |
| `tm_referrals` | anthropic | 1 | **1** | 0 |
| `tm_rx_drafting` | anthropic | 1 | **1** | 0 |
| `tm_soap_draft` | anthropic | 1 | **1** | 0 |
| `tm_transcribe` | **deepgram** | 1 | **1** | 0 |
| **total** | | **13** | **13** | **0** |

`api_usage_events` is identical row-for-row (13 rows, 13 ids, 0 NULL, every row
`unitsSource='vendor'`), with one naming difference recorded as a finding below.

### WHAT THIS ANSWERS, AND WHAT IT EXPLICITLY DOES NOT

**Three owed items are discharged:**

1. **The meter is no longer unproven in production.** 13 real vendor calls
   produced 13 `api_usage_events` rows, every one `unitsSource='vendor'`, priced
   at **$0.4865** against `ai_calls`' **$0.49**.
2. **B1-a's capture is proven on live calls** — every purpose carries a real
   vendor id.
3. ⚠️ **Step 1's fix is proven in production on the path that motivated it.**
   `judge` — the purpose the ledger recorded as *structurally NULL*, and the one
   `worker.ts` pre-warms on every visit — came back **1 of 1 present**. Before
   step 1 this row would have been NULL, and the sizing number would have
   recorded our own omission as the vendor's silence.

**And ruling 68 is confirmed by observation rather than by argument:**
`tm_anchor_entailment` produced **3 calls and 3 meter rows** — L4b's k=3 ensemble
emitting one row per CALL, exactly as the ruling said, not one per stage.

⚠️ **THIS DOES NOT SETTLE RULING 72(b), AND MUST NOT BE READ AS SETTLING IT.**
The result is **13 of 13, zero NULL** — a perfect score for `vendor ⇒ id` — and
that is precisely the shape of evidence most likely to be over-read. It is **one
visit, one specialty, one input mode, all happy-path**. The declaration said so
before the number existed, deliberately:

> *a single run that shows 100% present does NOT by itself justify shipping the
> strict form — it is one sample, and step (b) is explicitly a measurement
> question.*

**Tightening stays the allowed direction, so there is no cost to waiting and an
unwalkable-back cost to guessing.** What this run establishes is that the
biconditional is *plausible* and that the instrument now measures the right
thing. What it does not establish is the **failure-path** behaviour — and
`ai_calls` still writes NULL on every failure path by design (declared in step 1,
unchanged; that is B2). **Every call in this sample succeeded (13 of 13 `ok`), so
this run contains exactly zero evidence about the case the constraint would have
to survive.**

### Found on the way past

- ⚠️ **`tm_embed` PRODUCED NO ROWS AT ALL.** The ledger's step-2 note predicted
  `embed.ts` would meter on a real run (it short-circuits above `logApiUsage`
  only in MOCK mode). This visit produced **no embedding call on either table**.
  So step 1's threading in `embed.ts` is **still unproven on a live call**, and
  **B4's per-stage coverage gate cannot assume this stage appears in a
  single-visit sample.** Whether the stage is conditional or simply did not
  trigger for this input is not determined here.
- ⚠️ **`whisper-batch.ts` NEVER RAN EITHER** — Deepgram served the transcription
  (`tm_transcribe`). Step 1 touched three files; **this smoke proves one of them
  live** (`llm-mdm.ts`). The other two are proven only at unit level. Recorded
  because "the capture gap is CLOSED" is true of the code and, in production,
  demonstrated for one of three callers.
- ⚠️ **THE SAME CALL IS NAMED DIFFERENTLY IN THE TWO TABLES.** The transcription
  is `ai_calls.purpose = 'tm_transcribe'` and
  `api_usage_events.operation = 'transcribe_realtime'`. Every other stage matches
  exactly. **B4's gate is *per-stage coverage with expected call counts*, so a
  gate that joins the two tables by stage name will silently mis-pair this one**
  — one table reporting a stage the other appears to lack. It is a naming
  divergence, not a data defect, and it is cheapest to fix in the gate's mapping
  rather than by renaming a column with history behind it.
- **Cleanup preserves the evidence — now measured, not argued.** After
  `clean.ts`: patients **0**, visits **0**, and `ai_calls` **500** /
  `api_usage_events` **464** / `audit_logs` **977** all intact. The ledger
  asserted this from the FK layout; it is now an observation.

### ⚠️ THE CHECK IS NOW PROVEN TO REFUSE **IN PRODUCTION**, NOT MERELY PRESENT

Step 2 mutation-proved the constraint **on QA**. On production it had only ever
been *observed in the catalog* — and a constraint that exists is not the same
claim as a constraint that refuses. The smoke could not settle it either: all 13
rows were `(vendor, id present)`, which the CHECK accepts, **so a fully green
smoke is exactly as consistent with a constraint that refuses nothing.**

Proven here, per the canon's sanctioned form — *any write inside a gate that a
constraint is supposed to refuse belongs in `BEGIN … ROLLBACK`, so the attempt is
observable and never consequential*:

| attempt (each in its own transaction, never committed) | result |
|---|---|
| **positive control** — flip a row to `mock` **and** NULL its id | **`UPDATE 1`** — legal, and the write path works |
| **the refusal** — flip the same row to `mock`, **keeping** its id | **`ERROR: violates check constraint "api_usage_events_request_id_requires_vendor"`** |

**Attribution was established BEFORE the attempt, not inferred after it.**
`api_usage_events_units_source_domain` is `unitsSource = ANY('vendor','mock')` —
so `'mock'` is legal to that constraint, and the only constraint the flip can
violate is the one under test. This is the trap the canon records against the
composite-FK proof, where an unrelated `NOT NULL` refused the row first and the
"proof" established nothing: **a refusal is evidence only when you know WHAT
refused.**

**The positive control is what makes the refusal mean something.** Without it, an
`ERROR` is equally consistent with a table that rejects every write. With it, the
only difference between the accepted row and the rejected one is the presence of
the id.

Census before and after both attempts: **`vendor | 1325 | 0`** — identical. No
row was changed, no constraint was touched, and nothing was dropped or re-added.

### Cleanup, as ruled

`clean.ts` only — `cleaned visits=1 patients=1 templates=0`. Fixture verified
back at **0 patients / 0 visits**. Audit rows left in place. `runStaleVisitCleanup()`
was **not** invoked, and must never be used as a cleanup shortcut: it is not
practice-scoped.
