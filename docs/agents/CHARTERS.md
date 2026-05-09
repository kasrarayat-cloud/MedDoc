# QuillMD agent charters

> **Source of truth for agent ownership boundaries.** When the roster
> grows past four, this file decides which agent owns each new concern.
> When two agents fire on the same code path, this file decides whether
> that's intentional (different lenses on the same gap) or duplication
> to refactor.
>
> **Maintenance discipline.** Every PR that adds, retires, or changes
> the scope of an agent updates this file in the same PR. The
> Code Quality / Pattern Auditor's `README.md` references this file by
> path; if you move the file, update the path there too.

## Roster — at a glance

| Agent | Status | Trigger | Catches |
|---|---|---|---|
| [QA Interaction Auditor](#1--qa-interaction-auditor) | **ACTIVE v3.3** | "Run the QA agent" / per-page invocations | UI behavior bugs (orphan dispatchers, "pretend success", parser/renderer mismatches) |
| [AI Pipeline Auditor](#2--ai-pipeline-auditor) | **DORMANT (designed)** | "Run the AI pipeline audit" (post-activation) | AI pipeline drift (cost, quality, coverage, model assignment) |
| [HIPAA Compliance Auditor](#3--hipaa-compliance-auditor) | **DORMANT (staged)** | "Run the HIPAA compliance audit" (post-activation) | Compliance posture drift (§164.308 / §164.310 / §164.312) |
| [Code Quality / Pattern Auditor](#4--code-quality--pattern-auditor) | **ACTIVE on merge of `agent/code-quality-auditor-v1`** | "Run code quality audit on PR #N" / "Audit diff for pattern compliance" / "Code quality audit on `<path>`" | Pattern drift at PR time (design tokens, component patterns, schema rules, BullMQ patterns, server/client boundary, folder layout) |

## Convergence on file structure

The first three agents shipped with slightly different structural
choices:

- QA Interaction Auditor: full-fat — `SKILL.md` + `README.md` + `skills/`
  with five docs + `scripts/` populated with real walkers + `tests/`
  + `fixtures/` with seed JSON.
- AI Pipeline Auditor: design-only — no `SKILL.md` (intentional — the
  agent is dormant; absence of `SKILL.md` means Lead's skill system
  doesn't list it as invocable yet) + `README.md` + `skills/` with
  four design docs + `fixtures/` + `scripts/` as `.gitkeep` placeholders.
- HIPAA Compliance Auditor: design-only — same shape as AI Pipeline
  Auditor. **The most recent of the three; canonicalised here as the
  reference for new agents.**

**Convergence rule going forward.** New agents follow the HIPAA pattern
when designed-but-dormant; promote to the QA pattern (real
`SKILL.md` + populated `scripts/` + `fixtures/`) at activation:

```
.claude/agents/<name>/
├── README.md            (operator-facing)
├── SKILL.md             (skill registration; present iff agent is ACTIVE)
├── fixtures/.gitkeep    (or real fixtures when ACTIVE)
├── scripts/.gitkeep     (or real scripts when ACTIVE)
└── skills/
    ├── activation-criteria.md
    ├── data-sources.md
    ├── finding-classes.md
    └── methodology.md
```

The Code Quality / Pattern Auditor follows this convention with two
additions specific to its role: `rules.md` (the rule library) at
agent root and `samples/<sample-run>.md` for committed real-PR audit
references. New agents should consider similar additions only when
their methodology genuinely needs them.

---

## 1 · QA Interaction Auditor

| Field | Value |
|---|---|
| **Name** | QA Interaction Auditor |
| **Version** | v3.3 |
| **Purpose** | Walks the QuillMD UI clicking every interactive element + verifies each click produces the state change it appears to. Catches feature stubs, orphan event dispatchers, "pretend success" fallbacks, parser/renderer mismatches that pure backend or unit testing miss. |
| **Scope** | `apps/transcribe-md/src/**` (19 routes), `apps/marketing/src/**` (10 routes). Per-page walkers + a `sweep-all.mjs` orchestrator. |
| **Out of scope** | `apps/meddoc-pro/**` (decommissioned per memory + POST_MERGE_TODO §21). Backend-only logic (different audit surface). Visual regression / pixel diffs. E2E flows that require real PHI uploads. |
| **Runtime** | On-demand, per-page or full-site. Real Playwright headless against a dev server with seeded fixtures. Reports written to `docs/qa-reports/<timestamp>.md`. |
| **Trigger phrase** | "Run the QA agent" / "Run a QA sweep" / "Audit the [page name] for UX bugs" / "Walk the [workflow] looking for bugs" / "Run the full site QA sweep" |
| **Activation status** | **ACTIVE v3.3.** No gate — UI surfaces exist immediately. Active since PR #133 (2026-05-05). |
| **File location** | `.claude/agents/qa-interaction-auditor/` |
| **Owner of overlapping concerns** | **OWNS:** UI behavior verification, click-class bug detection, audit-row *runtime emission* during click flows (the §164.312(b) gaps F-09/F-10/F-11 closed by PR #138 were caught here). |

---

## 2 · AI Pipeline Auditor

| Field | Value |
|---|---|
| **Name** | AI Pipeline Auditor |
| **Version** | v1 (design only) |
| **Purpose** | Audits the AI pipeline (transcribe → SOAP → coding → Rx → referral) for cost / quality / coverage / model-assignment drift. Read-only against `transcribe_visits` + `ai_calls` + `audit_logs` + eval results. |
| **Scope** | The AI pipeline only — `apps/transcribe-md/src/worker/layers/**` (L1-L7e), `apps/transcribe-md/src/lib/em-coding/**` (Coding Coach), and the Anthropic / Deepgram / Whisper call sites. Cost data via `ai_calls` table. |
| **Out of scope** | UI behavior. Schema correctness. Compliance posture. Pattern conformance of pipeline source code (that's the Code Quality Auditor). |
| **Runtime** | Nightly (post-activation) + on-demand. Read-only against the database; never reads PHI content; row counts bucketed before reporting. |
| **Trigger phrase** | "Run the AI pipeline audit" |
| **Activation status** | **DORMANT (designed, gated).** Activates when ≥20 visits across ≥3 distinct doctors with `status=READY` exist in `transcribe_visits`. Below threshold the findings would be stylistic rather than behavioral. See `.claude/agents/ai-pipeline-auditor/skills/activation-criteria.md`. |
| **File location** | `.claude/agents/ai-pipeline-auditor/` |
| **Owner of overlapping concerns** | **OWNS:** AI cost/quality/coverage drift, model assignment drift, prompt-cache hit rate analysis, layer-skip correctness across pipeline runs, eval-corpus regression detection. |

---

## 3 · HIPAA Compliance Auditor

| Field | Value |
|---|---|
| **Name** | HIPAA Compliance Auditor |
| **Version** | v1 (design only) |
| **Purpose** | Audits HIPAA compliance posture continuously: §164.308 (administrative — workforce training, contingency plan, vendor BAAs), §164.310 (physical — encryption-at-rest config attestation), §164.312 (technical — access control, audit controls, integrity, auth, transmission security). Read-only against the production system + `audit_logs` + filesystem + container env. **Does NOT read PHI content; counts bucketed; visit IDs short-hashed in reports.** |
| **Scope** | The full QuillMD production posture — runtime state, audit_log emission across the full `AuditAction` enum, encryption configuration (Postgres LUKS, MinIO SSE-S3), vendor BAA dates, MFA on admin accounts, session scoping, transmission security (HSTS, TLS 1.2+, WSS-only). |
| **Out of scope** | Pattern conformance of source code (Code Quality Auditor). UI walking (QA Auditor). AI pipeline drift (AI Pipeline Auditor). Counsel-grade reportability decisions — agent NEVER decides reportability; only flags `ocr_reportable_candidate: true` for findings counsel should review. |
| **Runtime** | Nightly (post-activation) + on-demand. Per-phase activation gating — most phases run today; phases 2 + 3 wait for pilot data. |
| **Trigger phrase** | "Run the HIPAA compliance audit" |
| **Activation status** | **DORMANT (staged).** Phases 0 / 5 / 6 / 7 / 8 / 9 can run today (schema sanity, transmission, encryption, BAAs, encryption posture, reporting). Phases 1 + 4 need ≥3 active accounts (currently met). Phases 2 + 3 (audit controls + integrity) share the same pilot-data threshold as `ai-pipeline-auditor`. See `.claude/agents/hipaa-compliance-auditor/skills/activation-criteria.md`. |
| **File location** | `.claude/agents/hipaa-compliance-auditor/` |
| **Owner of overlapping concerns** | **OWNS:** runtime audit-row correctness (does `LOGIN_FAILED` actually emit a row when a failed login occurs?), audit-log retention windows, BAA expiration, MFA coverage, encryption-at-rest verification, transmission-security verification. |

---

## 4 · Code Quality / Pattern Auditor

| Field | Value |
|---|---|
| **Name** | Code Quality / Pattern Auditor |
| **Version** | v1 (rule library at `agent/code-quality-auditor-v1` head) |
| **Purpose** | Audits PR diffs (and arbitrary file paths) for compliance with QuillMD's actual production conventions — design tokens, component patterns, Prisma schema rules, BullMQ pipeline rules, server/client boundary, folder layout, scope guards. Catches pattern drift that pure typecheck + tests miss. |
| **Scope** | `apps/transcribe-md/**`, `apps/marketing/**`, `packages/**` (only when an in-scope app diff touches a packaged symbol). 27 rules across 8 categories. |
| **Out of scope** | `apps/meddoc-pro/**` (legacy decommissioned). `_design-references/`, `docs/`, `infra/`, top-level `scripts/`, `.claude/` (auditor's own files exempt). Visual / aesthetic correctness (eyes-on review job). AI prompt quality / model choice / cost (AI Pipeline Auditor). Compliance correctness at runtime (HIPAA Auditor). |
| **Runtime** | PR-time (called by Lead during PR review) + on-demand. Read-only against the diff and the rule library's canonical references. Future v1.1 may wire CI hook. |
| **Trigger phrase** | "Run code quality audit on PR #N" / "Audit diff for pattern compliance" / "Code quality audit on `<path>`" |
| **Activation status** | **ACTIVE on merge** of branch `agent/code-quality-auditor-v1`. No gate — pattern auditing's signal is the codebase itself, not runtime data. Read-only; never touches DB / MinIO / production. |
| **File location** | `.claude/agents/code-quality-auditor/` |
| **Owner of overlapping concerns** | **OWNS:** PR-time pattern presence checking (was a `logAudit` call written?), design-token vs hardcoded value detection, server/client boundary directive checking, scope-guard enforcement (no cross-app imports, no `apps/meddoc-pro/**` modifications). |

---

## Cross-agent boundary table (the load-bearing one)

When two agents *could* fire on the same gap, this section says
who owns what. The split is intentional and in every case below;
both findings are correct signals and operators should see both.

### Code Quality ↔ HIPAA (closest neighbour)

The auditors will both fire on the same code path when a PR adds a
PHI-mutating Prisma call without a paired `logAudit`. **The split is
intentional and necessary.**

| Concern | Code Quality | HIPAA | Why split |
|---|---|---|---|
| `prisma.<phi-model>.update(...)` in a diff with no companion `logAudit` call site | **`SCHEMA-001` BLOCK** at PR time | (no finding pre-merge — fires at audit time after the row would have been observed missing) | Code Quality blocks the merge; HIPAA verifies that the merged code actually emits the row at runtime. Code can be written *correctly* (call site present) but *wrong* (row never reaches the table due to a transaction rollback bug). Both findings are valid lenses. |
| Empty / silent `AuditAction` enum value in production | (no finding — pattern is fine) | **P1 finding** at audit time (action emit count = 0 over 30d window) | Pattern auditing can't see runtime emit counts. HIPAA owns this fully. |
| `// audit:exempt` opt-out marker present on a Prisma mutation | **PASS** (Code Quality recognises the marker) | (no finding) | Marker is intentional opt-out for offline contexts (seed scripts, internal cleanup). Code Quality silences itself; HIPAA doesn't audit offline contexts at all. |
| Row written but with bad metadata (PHI in the JSON blob, missing `targetType`, etc.) | **out of scope** — Code Quality doesn't introspect runtime row contents | **P1 / P2 finding** at audit time | Pattern auditing operates on the diff text; runtime row shape is HIPAA's job. |

**Pre-summary (paste into PR descriptions when relevant):** Code Quality
checks pattern *presence* at PR time. HIPAA checks runtime *correctness*
on the live system. Both findings are good — the split is intentional.

### Code Quality ↔ QA Interaction

Zero overlap by design. Code Quality reads the diff; QA walks the
running UI. Different inputs entirely. The findings are complementary:

| Bug class | Caught by |
|---|---|
| Click button, no state change ("pretend success") | QA |
| New component missing `'use client'` directive | Code Quality |
| Audit row promised in code, never emitted at runtime | HIPAA (post-activation) + QA (in click flows) |
| Hardcoded `#9eb5a0` in CSS fallback | Code Quality |
| Modal opens but doesn't render the override prompt | QA |
| New `prisma.transcribeVisit.upsert` without `logAudit` companion | Code Quality (PR-time) + HIPAA (audit-time, if the row never emits) |

### Code Quality ↔ AI Pipeline

Zero overlap by design. AI Pipeline audits prompt content / model
choice / cost / cache-hit rate / eval drift. Code Quality audits diff
shape / pattern conformance. Examples:

| Concern | Owner |
|---|---|
| Layer 4 model assignment is `claude-sonnet-4-6` instead of the spec's `claude-opus-4-7` | AI Pipeline |
| `runLayer4GenerateSoap` file missing the layer-skip pattern | Code Quality (`QUEUE-003` WARN) |
| Anthropic prompt cache miss rate climbing | AI Pipeline |
| New `Queue` instantiation without DLQ wiring | Code Quality (`QUEUE-001` BLOCK) |
| Per-utterance Deepgram confidence threshold drift | AI Pipeline |
| Per-minute jobId idempotency key broken on a new call site | Code Quality (`QUEUE-002` BLOCK) |

### QA ↔ HIPAA

QA fires runtime audit-row checks during UI walks (the §164.312(b)
gaps F-09/F-10/F-11 from PR #138 were caught here). HIPAA fires on
audit-log emission across the full enum on a 30-day window. **Both
findings can fire on the same gap; both are correct.**

QA's check: "I clicked Sign & Send; was a `VISIT_SIGNED` row written
in the next 200ms?"
HIPAA's check: "Is `VISIT_SIGNED` emitted at all in the last 30 days?"

QA catches it first (faster feedback loop); HIPAA backstops.

### QA ↔ AI Pipeline

Zero overlap. QA walks UI; AI Pipeline reads pipeline metrics.

### HIPAA ↔ AI Pipeline

Both read `audit_logs`, but for different signals. HIPAA reads the
emission shape (which actions, what timestamp, what subject). AI
Pipeline reads `ai_calls`-related rows (cost, model used, layer
duration). They share an indexed table, not an audit lens.

---

## Pending agents

Designed-but-not-built. Listed here so future PRs slot them in
without re-litigating the boundary table.

### Performance Auditor (planned)

| Field | Value |
|---|---|
| **Purpose** | Audits cold-path latency, warm-path latency, p95/p99 budgets, BullMQ queue depth, web request waterfall. |
| **Scope** | The web app's request path + worker layer wall-times + Postgres slow-query log. |
| **Out of scope** | AI pipeline cost/quality (AI Pipeline Auditor). UI behavior (QA). Pattern shape (Code Quality). |
| **Trigger phrase** (proposed) | "Run the performance audit" |
| **Activation gate** (proposed) | ≥1 week of production traffic + Sentry performance enabled. |
| **Boundary** | Closest neighbour is AI Pipeline (both touch worker layers). Performance owns wall-time + queue depth; AI Pipeline owns cost + quality. |

### Prompt / Cost Auditor (planned)

| Field | Value |
|---|---|
| **Purpose** | Audits Anthropic / Deepgram / Whisper prompt content + token usage + cache hit rate + model-cost ledger. |
| **Scope** | `apps/transcribe-md/src/worker/layers/**` prompt templates, `packages/ai/**`, `ai_calls` table cost ledger. |
| **Out of scope** | AI quality / coverage drift (AI Pipeline). Pattern shape (Code Quality). |
| **Trigger phrase** (proposed) | "Run the prompt audit" / "Run the cost audit" |
| **Activation gate** (proposed) | Same pilot threshold as AI Pipeline (≥20 visits × ≥3 doctors). |
| **Boundary** | Likely a *sub-agent* of AI Pipeline rather than a peer — the split would be cost/prompt vs. quality/coverage. To be decided at activation. |

---

## Lifecycle policy

- **Activate.** When the gate clears. Update `Activation status` row;
  promote `.gitkeep` placeholders in `scripts/` + `fixtures/` to real
  content; add `SKILL.md` if absent.
- **Retire.** When the agent's coverage is subsumed by another or the
  bug class disappears. Move the agent dir to `.claude/agents/_retired/`
  with the retire date. Keep the README so the institutional context
  doesn't vanish.
- **Boundary disputes.** When two agents can fire on the same gap, one
  PR updates this charter table to make the split explicit. **Don't
  silently let two agents own the same finding** — the operator gets
  duplicate noise and won't trust either.
- **New rule, existing agent.** Agents own their own rule libraries
  (Code Quality → `rules.md`; HIPAA → `skills/finding-classes.md`).
  Adding a rule does not require a charter update unless the rule
  reaches into another agent's territory.

## Maintenance log

- **2026-05-09 — initial publication.** All four agents documented;
  Code Quality / Pattern Auditor activated by merge of
  `agent/code-quality-auditor-v1`. Convergence rule on file structure
  (HIPAA pattern as canonical) recorded. Pending agents listed.
