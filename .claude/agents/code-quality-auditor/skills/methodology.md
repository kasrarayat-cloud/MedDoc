# Methodology — Code Quality / Pattern Auditor

> Algorithm in execution order. Lead follows this start-to-finish on
> every invocation.

## Operating principle

Read the diff. Apply the rule library against it. Emit a markdown report.
Never auto-fix; never write to runtime systems; never read PHI.

The auditor's authority is the rule library (`rules.md`) — a file in
the same directory as this skill. Each rule grounds in a specific
reference file/line in this codebase. **If a rule's anchor moves and
`rules.md` doesn't track it, the auditor flags itself.** The author
of the diff that moved the anchor owns the `rules.md` update.

## Algorithm

### Phase 0 — Resolve input

Per the trigger phrase the operator used:

| Trigger | Resolution |
|---|---|
| "Run code quality audit on PR #N" | `cd /opt/meddoc-pro && gh pr diff N --repo kasrarayat-cloud/MedDoc > /tmp/audit-input.diff` |
| "Audit diff for pattern compliance" | `cd /opt/meddoc-pro && git diff > /tmp/audit-input.diff && git diff --cached >> /tmp/audit-input.diff && git ls-files --others --exclude-standard >> /tmp/audit-untracked.txt` |
| "Code quality audit on `<path>`" | `cd /opt/meddoc-pro && git diff origin/main HEAD -- <path> > /tmp/audit-input.diff` (or treat the whole file as added if no diff context exists) |

Parse `/tmp/audit-input.diff` into `(file, line, line-content)`
triples. Track removed lines for context only — score the post-fix
state.

### Phase 1 — Scope guard

Before any rule applies:

1. **Drop in-tree files that are out of scope** for content rules:
   - `_design-references/**`
   - `docs/**`
   - `infra/**`
   - top-level `scripts/**`
   - `.claude/**` (the agent's own files — exempt to prevent
     self-BLOCK of its rule library and skills)
2. **Pre-emit `SCOPE-001` BLOCK** for every diff line under
   `apps/meddoc-pro/**`. Drop those lines from the in-scope set
   (so subsequent rules don't false-positive on them).
3. **Pre-scan in-scope files** for `import ... from 'apps/meddoc-pro/...'`
   or other cross-app imports — emit `SCOPE-002` BLOCK.

After Phase 1, the working set is files under
`apps/transcribe-md/**`, `apps/marketing/**`, and `packages/**` (the
last only when an in-scope app diff touches a packaged symbol).

### Phase 2 — Rule-anchor self-check

For every rule in `rules.md`:

1. Open the file named in `canonical_ref`.
2. Confirm the line range named contains content matching the rule's
   declared shape (the rule's "Canonical example" snippet should be
   present at the named lines, fuzzy-match on whitespace).
3. If file missing OR line range no longer matches → emit
   `RULE_STALE` BLOCK against the auditor itself. Continue with the
   remaining rules.

A run with `RULE_STALE` findings still produces a normal report; the
operator sees both the stale-rule list AND the diff findings. The
expectation is that the same PR (or the next one) updates the rule
library.

### Phase 3 — Apply rules in category order

Categories in order: design-tokens → component → schema → BullMQ →
boundary → layout → scope → docs.

Within a category, rules in tier order: BLOCK → WARN → NIT.

For each rule:

- Match its trigger against the in-scope diff.
- For each match, emit a finding (one per line) per the shape in
  [`finding-classes.md`](finding-classes.md).
- Stop after 20 findings per rule per file (avoid spam; the operator
  gets the signal in 3 — anything past 20 hides in the noise). Emit
  one summary line: "rule X had 47 matches in foo.tsx; first 20 shown."

### Phase 4 — Group + emit report

Report structure:

```markdown
# Code Quality Audit — <PR # or path or "working tree">

**Run:** <ISO timestamp>
**Input:** <PR #N · `gh pr diff` SHA / working tree / path>
**Rule library:** `.claude/agents/code-quality-auditor/rules.md` @ <commit SHA>
**In-scope files:** N
**Findings:** X BLOCK · Y WARN · Z NIT

---

## BLOCK · X findings

### <category> · <rule_id> · <count> findings

- **`apps/.../foo.tsx:42`** — <message>
  - Snippet: `<line>`
  - Canonical: `<canonical_ref>`
  - Fix: <fix_hint>

…

## WARN · Y findings

…

## NIT · Z findings

…

## Stale rules

(emitted only when RULE_STALE findings exist; lists each)

---

**Summary:** X BLOCK · Y WARN · Z NIT against N files. Rule library has
26 rules (10 BLOCK / 9 WARN / 7 NIT). Stale: K.
```

### Phase 5 — Persistence (optional)

If the operator's invocation included an output-capture flag (e.g.
"Run code quality audit on PR #176 **and save the report**" or
"Audit PR #176 to docs"), write the report to:

```
docs/agent-reports/code-quality/<timestamp>-<pr-or-path>.md
```

The directory `docs/agent-reports/code-quality/` is created if
missing. Otherwise, return inline only.

## Per-rule application notes

A few rules need extra care:

### `SCHEMA-001` (audit-row presence)

The check is **same-function-body** — the auditor scans the function
containing the Prisma mutation for a `logAudit` call (or a
`recordOverride` / `recordRxWarningOverride` call, which wrap
`logAudit`). False-negative cases the auditor accepts:

- A wrapper that calls Prisma + audit in one call site, like the
  `auditedTransaction()` helper at `apps/transcribe-md/src/lib/audit.ts`
  (if it exists; spot-check). The auditor recognises a call to a
  symbol named `audited*` as wrapping the audit obligation.

False-positive cases the auditor accepts (operator can override):

- A function that explicitly says it does not need an audit row
  (e.g. internal cleanup, bulk maintenance). The auditor recognises
  a `// audit:exempt` comment on the line above the Prisma call as
  an opt-out marker — equivalent of `// eslint-disable-next-line`.
  Use sparingly; the marker is grep-able for review.

Boundary with HIPAA: this rule fires at PR time on **pattern
presence**. HIPAA fires at audit time on **runtime emission** —
both findings are valid signals on the same gap.

### `QUEUE-001` (DLQ wiring)

The check is **module-level** — does the same module file (or one
imported by it) declare a DLQ queue? The auditor scans the file's
imports for `enqueueDlq` / `dlqQueue` / similar; absence is the
finding.

False-negative: if a separate PR moved DLQ wiring to a new module
without re-anchoring this rule, `RULE_STALE` fires first and the
operator updates `rules.md` to point at the new module. Then this
rule's check passes correctly.

### `TOKEN-001` (hardcoded colors)

The auditor's color lookup is built once per run from
`globals.css:36–97`. Hex literals matching exactly (case-insensitive)
fire WARN; the seven allowlist hexes (see rules.md) are silently
skipped. Two values that previously appeared in mockups (`#9eb5a0`
and `#050607`) fire **BLOCK** rather than WARN — they were the
Round-1 mockup mistake we explicitly retired, and any reappearance
is regression.

### `BOUND-001` (env reads in client bundles)

Regex-based: `process.env.<X>` where `<X>` matches `[A-Z_][A-Z0-9_]*`
and does NOT start with `NEXT_PUBLIC_` or equal `NODE_ENV`. Fires
only inside files containing `'use client'` directive.

False-positive case: build-time env that's bundler-substituted before
shipping (e.g. via `process.env.NEXT_PUBLIC_*` or via webpack DefinePlugin).
The auditor accepts a `// build-time-injected` comment on the line
above as an opt-out.

## Failure modes

- **Diff fetch fails** (`gh` rate-limited, network hiccup, PR not
  found). Emit one error finding (severity: ERROR not BLOCK; outside
  the rule taxonomy) and abort the run. Operator retries.
- **`rules.md` parse error.** Emit ERROR; abort. The rule library is
  the only file the auditor needs to compile; a malformed library
  means every finding would be wrong.
- **Many false-positives.** The operator pushes back via PR review
  comment ("ignore TOKEN-001 in this file — intentional"). The
  agent does NOT auto-tune; the rule library is updated by hand,
  by Lead, with citation. False-positive resilience is a future-PR
  improvement.

## Versioning

Rule-library version = the commit SHA of `rules.md` at run time. The
report cites it; comparing reports across two PRs is a string compare
on the SHA + a diff against `rules.md`.

The agent itself doesn't carry a separate semantic version; the
rule-library SHA is the version. v1's first ship is the rules.md
content at branch `agent/code-quality-auditor-v1` head.
