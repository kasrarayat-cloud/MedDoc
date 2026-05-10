# Finding classes — Code Quality / Pattern Auditor

> Three-tier severity. Each tier maps to a clear operator action.

## Severity definitions

| Severity | Meaning | Author / reviewer action |
|---|---|---|
| **BLOCK** | Pattern violation that breaks consistency or risks safety. Examples: server-only import in a `'use client'` file; Prisma model mutating PHI without an audit-row call site; new BullMQ queue without DLQ wiring; cross-app import into the decommissioned `apps/meddoc-pro/`; missing `'use server'` on a server action. | **Block merge.** Author must fix before merging. The auditor is the gate. |
| **WARN** | Drift from established convention but not breaking. Examples: hardcoded color hex when a `--color-linear-*` token exists; deviation from the `RxWarningsRail` state pattern; status-pill rendered via inline ternary instead of the `Record<Status, string>` map. | **Author should fix or get reviewer agreement.** Reviewer comment if it should land as-is. |
| **NIT** | Style preference. Examples: import ordering; comment voice; naming taste; file co-location borderline cases (kebab-case vs PascalCase already inconsistent in production — don't crusade). | **Author may ignore.** Listed for awareness. |

## Why three tiers (not two, not five)

- Two tiers (block / no-block) collapses the WARN signal into a binary —
  reviewers either ignore everything not blocking, or get warning
  fatigue. Production has ~9 conventions that are firmly established
  but not safety-critical; calling them all BLOCK over-fires the gate,
  calling them all NIT under-signals.
- Five tiers (P0/P1/P2/P3/P4) overspecifies. The auditor is a *PR
  reviewer companion*, not a compliance system. The HIPAA Compliance
  Auditor uses P1/P2/P3 because regulatory exposure adds a real fourth
  axis (`ocr_reportable_candidate`); this agent has no analogous
  axis.

Three tiers matches the operator mental model: must fix · should fix ·
might fix.

## Boundary with HIPAA Compliance Auditor severities

HIPAA's P1/P2/P3 carry an `ocr_reportable_candidate` flag; this
auditor's BLOCK/WARN/NIT do not. **A finding emitted by both agents
on the same code path will carry independent severities** — e.g.
the SCHEMA-001 BLOCK from this auditor for missing `logAudit` call
site fires at PR time; the equivalent HIPAA finding fires at audit
time on the live system after the row is observed missing. Operator
sees both; both are correct.

## Per-finding shape

Every finding emits this object (rendered as markdown in the report):

```json
{
  "rule_id": "TOKEN-001",
  "severity": "WARN",
  "category": "design-tokens",
  "file": "apps/transcribe-md/src/components/foo.tsx",
  "line": 42,
  "snippet": "color: '#7AA68C'",
  "message": "Hardcoded sage hex; use var(--color-linear-sage) or text-linear-sage.",
  "canonical_ref": "apps/transcribe-md/src/app/globals.css:70",
  "fix_hint": "Replace #7AA68C with var(--color-linear-sage) (literal CSS) or text-linear-sage (Tailwind utility)."
}
```

Required fields: `rule_id`, `severity`, `category`, `file`, `line`,
`snippet`, `message`, `canonical_ref`, `fix_hint`.

Optional fields: `confidence` (`high` / `medium` / `low` — default
`high`; lower when the rule's regex/heuristic could false-positive),
`related_findings` (other `rule_id`s if this finding is part of a
cluster).

## Special: `RULE_STALE`

A `RULE_STALE` finding is the auditor flagging itself, not the diff.
Severity is always BLOCK. The fix is always: re-anchor the rule by
editing `rules.md` to point at the new line range, or remove the rule
entirely if the pattern has been retired.

```json
{
  "rule_id": "RULE_STALE",
  "severity": "BLOCK",
  "stale_rule": "COMP-003",
  "expected_anchor": "apps/transcribe-md/src/app/visits/[id]/soap/SoapSection.tsx:65-69",
  "observed": "file exists; line range no longer contains STATUS_PILL_CLASS — likely refactored.",
  "fix_hint": "Open SoapSection.tsx, locate the new line range of the status-pill class map, update rules.md COMP-003 canonical_ref."
}
```

The auditor self-flags before scoring the diff. The author of the
diff that *moved* the canonical reference is responsible for the
rules.md update — the auditor surfaces the obligation, doesn't
auto-fix.
