# Data sources — Code Quality / Pattern Auditor

> What the auditor reads and does **not** read. Read-only by design.

## Reads

### 1 · The diff under review
Resolved per the trigger phrase:

| Trigger | Source command |
|---|---|
| "Run code quality audit on PR #N" | `gh pr diff N --repo kasrarayat-cloud/MedDoc` |
| "Audit diff for pattern compliance" | `git diff` + `git diff --cached` + untracked file list |
| "Code quality audit on `<path>`" | `git ls-files <path>` (or recurse if folder); treat the whole file as added lines |

The auditor parses unified-diff hunks into `(file, line, line-content)`
triples. Removed lines are tracked but not scored — rules apply to the
*post-fix* state.

### 2 · The rule library — `rules.md`

Read once per run. The rule library declares each rule's
`canonical_ref` line — a path + line range in this codebase that's the
authoritative source for the pattern the rule enforces. The auditor
opens every `canonical_ref` at run-start and confirms the file + line
range still match the rule's described shape; mismatches emit
`RULE_STALE` BLOCK (against the auditor itself).

### 3 · Canonical references on the working tree

For each rule, the file/line range named in `rules.md`. Examples:

- `apps/transcribe-md/src/app/globals.css:36–97` — `@theme {…}` token block.
- `apps/transcribe-md/src/app/visits/[id]/soap/SoapSection.tsx:65–69` —
  status-pill class map.
- `apps/transcribe-md/src/lib/queue.ts:106–116` — per-minute jobId
  idempotency.
- `packages/db/prisma/schema.prisma:922–974` — `AuditLog` model
  (audit-row pattern reference).

Full list in `rules.md`.

### 4 · Cross-reference symbols

When a rule needs to confirm a symbol exists in a particular file (e.g.
"does this `prisma.patient.update` call have a paired `logAudit` in
the same function body?"), the auditor reads the post-fix file content
of the diffed file. It does NOT read other files in the working tree
beyond canonical references.

## Does NOT read

- **PHI.** No diff line is treated as PHI content; the auditor never
  reads `transcribe_visits`, `patients`, `audit_logs`, MinIO, or any
  runtime data.
- **The database.** Schema-rule grounding is `schema.prisma` (a file
  on disk), not a live DB query.
- **Production runtime state.** No HTTP calls, no Redis, no MinIO, no
  Postgres. The auditor is hermetic to the working tree + the diff.
- **The other agents' state.** Cross-agent referencing is by markdown
  pointer, not by file read at runtime.

## Bytes-on-the-wire reminder

For a typical PR (10–50 files, 200–2000 changed lines), the auditor's
total disk read is bounded by:

- the unified-diff (one round-trip to `gh`)
- `rules.md` (one read)
- the canonical-reference files (≤30 files, capped on the 27 rules)
- the post-fix content of changed files (the diff plus surrounding
  context for symbol cross-checks)

No background scanning, no full-tree walk. A run terminates in
seconds; cost is negligible.

## Output destinations

If the operator requests output capture, the report is written to:

```
docs/agent-reports/code-quality/<timestamp>-<pr-or-path>.md
```

The `agent-reports/code-quality/` directory is created on first
run if missing.

If the operator does NOT request capture (the default for ad-hoc
audits), the report is returned inline in the conversation only and
no file is written. This keeps churn low while still being shareable
with Kasra via copy-paste.
