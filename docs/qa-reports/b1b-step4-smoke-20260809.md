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

<!-- RESULTS APPENDED BELOW -->
