# Code Quality Audit — PR #167

**Run:** 2026-05-09T21:35:00Z
**Input:** `gh pr diff 167 --repo kasrarayat-cloud/MedDoc` (720 lines, 4 files)
**Rule library:** `.claude/agents/code-quality-auditor/rules.md` @ `agent/code-quality-auditor-v1` head
**In-scope files:** 1 (3 dropped — `.claude/agents/qa-interaction-auditor/**` is out of scope for content rules)
**Findings:** 1 BLOCK · 0 WARN · 1 NIT

> **Note for reviewer:** PR #167 is "QA agent visit-record walker (v3.3) —
> getUserMedia mock + draft-mode fixture". Three of the four diffed files
> are under `.claude/agents/qa-interaction-auditor/` (the QA agent's own
> scripts + skills/site-map.md) and are dropped from the auditor's input
> set per scope rules. The single in-scope file is the offline seed
> script — and it adds a new `prisma.transcribeVisit.upsert` call without
> an audit-row companion, which is the kind of finding this auditor's
> `SCHEMA-001` rule is designed to surface. **The fix is the
> `// audit:exempt` marker, not refactoring** — see fix hint below.

---

## BLOCK · 1 finding

### Prisma / schema · `SCHEMA-001` · 1 finding

- **`apps/transcribe-md/scripts/seed-qa-fixtures.ts:461–510`** — New `prisma.transcribeVisit.upsert` call without companion `logAudit`.
  - Snippet (truncated):
    ```ts
    await prisma.transcribeVisit.upsert({
      where: { id: FIXTURE_VISIT_IDS.recordDraft },
      update: { … },
      create: { id: …, status: 'QUEUED', inputMode: 'voice_dictation', … },
    });
    ```
  - Canonical: rule `SCHEMA-001` declares `TranscribeVisit` is a
    PHI-bearing model; mutations require a same-function-body
    `logAudit({ action, … })` call.
  - Why BLOCK: at PR-time the auditor sees a Prisma mutation on a
    PHI-bearing model with no audit-row call site. Mechanical rule.
  - **Why it's a false-positive in this case:** seed scripts run
    offline (outside the Next request lifecycle); `logAudit` depends
    on `AsyncLocalStorage` request context that isn't available in
    a `tsx` direct-execution context. Forcing a `logAudit` here
    would crash the seed.
  - **Correct fix:** add `// audit:exempt — offline fixture seed, no
    request context` on the line immediately above the `upsert` call.
    The auditor's methodology recognises `// audit:exempt` as an
    explicit opt-out (per `skills/methodology.md` "Per-rule
    application notes" → `SCHEMA-001`). This re-runs as PASS.

---

## NIT · 1 finding

### React component patterns · `COMP-006` · 1 finding (sub-threshold)

- **`apps/transcribe-md/scripts/seed-qa-fixtures.ts:458–460`** — Inline comment introduces a new fixture but doesn't reference the walker that consumes it.
  - Snippet:
    ```ts
    // v3.3 — record-draft fixture. The /visits/[id]/record page only
    // renders when status === 'QUEUED' (else redirects to /visits/[id]).
    // No SOAP, no transcript, no audio — same shape a freshly-created
    // voice_dictation visit has the moment a doctor lands on it.
    ```
  - Why NIT: the fixture exists *for* `sweep-visit-record.mjs` (added in
    the same PR). Convention is to cross-reference: "consumed by
    `.claude/agents/qa-interaction-auditor/scripts/sweep-visit-record.mjs`".
    Helps the next reader trace the dependency.
  - Fix hint: add one trailing line — "Consumed by
    `.claude/agents/qa-interaction-auditor/scripts/sweep-visit-record.mjs`."

---

## Findings against the diff but no rule fired

- The new key on `FIXTURE_VISIT_IDS` const (`recordDraft: 'qa_fix_visit_record_draft'`)
  follows the existing naming convention (`qa_fix_visit_*`). PASS.
- `prisma.transcribeVisit.upsert` is well-typed against the schema
  (`status: 'QUEUED' as const`, `inputMode: 'voice_dictation' as const`).
  No `as any` casts. PASS.
- All `.claude/agents/qa-interaction-auditor/scripts/lib/media-mocks.mjs`,
  `sweep-visit-record.mjs`, and `skills/site-map.md` changes are out of
  scope per the auditor's scope guard. The QA agent's scripts are tested
  by the QA agent itself; pattern-conformance there is its own
  responsibility, not this auditor's.

---

## Summary

```
1 BLOCK · 0 WARN · 1 NIT against 1 in-scope file.
Rule library: 26 rules (10 BLOCK / 9 WARN / 7 NIT). Stale: 0.
```

**Merge gate.** One BLOCK — the `SCHEMA-001` finding on the seed-script
upsert. The fix is a one-line `// audit:exempt — offline fixture seed, no
request context` comment above the `upsert` call. **No code refactor
required.**

**Reviewer sign-off note.** The fact that the auditor flagged this
correctly is itself a useful signal: the rule fires reliably on Prisma
mutations against PHI-bearing models. The `audit:exempt` marker pattern
becomes part of the seed-script convention going forward — the next
seed-script PR that adds a `prisma.<phi-model>.{create,update}` call
will get the same finding and the same one-line fix.

**Lesson encoded for future PRs.** Seed scripts that introduce
`prisma.transcribeVisit.upsert` / `prisma.patient.upsert` calls should
ship the `audit:exempt` marker upfront. Worth adding to the project's
seed-script template (see `apps/transcribe-md/scripts/seed-qa-fixtures.ts`
header) so new contributors don't get the BLOCK first time.
