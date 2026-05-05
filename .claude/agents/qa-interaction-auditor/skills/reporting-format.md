# Reporting format — bug template, severity, escalation

Every finding is a self-contained block. The agent writes findings as
markdown to stdout (or `docs/qa-reports/<UTC-timestamp>.md` for the full
sweep). No prose outside the blocks. Kasra reads the report top-to-bottom
and decides what to fix; the agent does NOT auto-fix.

## Bug-report template

Each finding is exactly this shape, no preamble:

```markdown
### Finding F-<NN> — <one-line summary>

- **Severity:** P0 | P1 | P2 | P3
- **Pattern:** A (orphan dispatcher) | B (pretend-success fallback) | C (parser/renderer mismatch) | D (other — describe)
- **Page / workflow:** <URL or workflow step name>
- **Element:** <text label> (`file:line`)
- **What the user sees:** <verbatim observed behavior — e.g. "modal closes, success toast fires">
- **What actually happens:** <verbatim verified behavior — e.g. "no Caddy POST fired; no audit row written; soapDraft column unchanged">
- **Evidence:**
  - Caddy log lines: <count>, methods: <POST/PATCH/etc>
  - DB diff: <columns that changed, or `none`>
  - Audit log diff: <action values written, or `none`>
  - Network: <URL + status, or `no network fired`>
- **Recommended fix scope:** <one of: prop wiring | event listener | parser update | server action | escalate to specialist>
- **Escalate to:** <agent name, or `none — fix inline`>
- **Reproduction:**
  ```
  <minimal commands or click sequence the agent ran>
  ```
```

The "Reproduction" block must be runnable. If the bug needs a seeded
visit, name the visit-id so Kasra can re-walk it.

## Severity rubric

The agent picks severity from this table. Don't invent a fourth axis.

| P | Trigger | Examples |
|---|---|---|
| **P0** | Doctor cannot complete the sign-and-send workflow OR loses clinical data OR PHI is exposed OR an audit row that PHI compliance requires is missing. | Sign button no-ops; SOAP edit doesn't persist; Rx warning critical-block bypassed; `VISIT_SIGNED` audit row not written. |
| **P1** | Doctor sees a confusing/wrong UI state but workflow is recoverable, OR a non-critical mutation silently fails, OR a stub-comment marker indicates code that NEVER worked in production. | Bump CTA "pretend success"; orphan dispatcher on a non-critical CTA; Pattern C empty-section render when DB has refusal banner. |
| **P2** | Cosmetic or low-traffic. Page renders, button works, but a label/state/transition is wrong. | Status pill says "Unknown" for a new enum value; tooltip points to old field. |
| **P3** | Maintenance — flagged for cleanup but not user-visible. | Dead `console.log`; stale TODO that's already fixed elsewhere; orphan listener with no dispatcher (the inverse of Bug A — harmless but wasteful). |

### Severity dial-up triggers

Bump severity by one level (P2 → P1, P1 → P0) if any of:

- The element is on the **sign-and-send workflow** (the path every visit
  takes — bugs there hit every doctor).
- The bug **silently swallows clinical data** (doctor types something,
  no error, content gone). Silent data loss > loud failure.
- The bug **bypasses a HIPAA-relevant audit row**. Phase 17 §164.312(b)
  requires the row; missing it isn't cosmetic, it's a compliance gap.
- The bug **affects more than one doctor's data** if it's a server
  action (vs. a single-user UI glitch).

### Severity dial-down triggers

Drop one level if:

- The element is **only reachable in admin/debug UI** that doctors
  don't touch.
- The bug requires an **edge-case input the workflow doesn't produce**
  (e.g. a 10-MB markdown body when the upload limit is 100 KB).
- The "wrong" behavior is **documented as intentional** in a comment
  with a `// no more` / `// previously` / `// pre-fix` qualifier.

## When to flag for a specialist (escalate vs. fix inline)

The agent's job is detection + report. Some findings need a specialist
agent's diagnosis before a fix can be scoped. The agent flags those in
the `Escalate to:` field.

| Symptom | Escalate to | Why |
|---|---|---|
| Wrong/missing AI pipeline output (e.g. L4 SOAP empty, L5 critique fired wrongly, L6 polish destroyed content) | `ai-pipeline-auditor` | Pipeline-stage diagnosis needs L1-L8 model knowledge the QA agent doesn't carry. |
| Backend audit-row missing despite the click firing the network request | `round-3-audit` (or backend specialist) | Could be a missing `prisma.auditLog.create` call in the server action — needs server-side review. |
| RLS / permissions issue (doctor sees another doctor's visit) | `security-auditor` | Authorization boundaries are out of QA agent scope. |
| Pattern C parser/renderer mismatch where the parser is shared (used by EHR export, PDF, clipboard) | `ai-pipeline-auditor` AND `round-3-audit` | Parser fix has to land safely across all output surfaces. |
| Database schema drift (column type changed, migration didn't run) | `migration-specialist` (or surface to Kasra; per memory, migrate dev is blocked — needs hand-write workflow) | Schema diagnosis isn't UI scope. |
| Performance regression (page takes > 5s to settle after click) | Surface to Kasra; no specialist routing | Performance triage needs profiling, not pattern-matching. |

The agent fixes nothing. Even when the finding is clearly inline-fixable
("just pass `onApplyAdditions={handleApplyAdditions}` at the call site"),
the agent reports the recommended fix scope and stops. Kasra ships.

## Bonus-finding section

Static-analysis grep often surfaces bugs unrelated to the requested
workflow. The agent appends those as "Bonus findings" at the bottom of
the report — same template, but with a `**Bonus:** true` field. Kasra
can decide later whether to triage them.

Example bonus-finding header:

```markdown
### Finding F-07 — EM_OVERRIDE_EVENT dispatched but no listener (orphan)

- **Bonus:** true
- **Severity:** P1
- **Pattern:** A
- ...
```

## Report front-matter

When the agent writes a full sweep to a file, it starts with:

```markdown
# QA Interaction Audit — <UTC timestamp>

- Agent: qa-interaction-auditor v1
- Branch: <git rev-parse --abbrev-ref HEAD>
- Commit: <git rev-parse --short HEAD>
- Workflow walked: <"sign-and-send" | "marketing landing" | "all enumerated">
- Test user: <env QA_AUDITOR_EMAIL>
- Visit-id (if applicable): <UUID>
- Findings: <count>  (P0: <n>, P1: <n>, P2: <n>, P3: <n>, Bonus: <n>)

---
```

Then findings in severity order (P0 first), then bonus findings.

## What the report MUST NOT contain

- Speculation about root cause without evidence in the `Evidence:`
  block. "I think the prop is missing" is not a finding; "the prop
  isn't in the JSX at line N + the modal closes without a network
  request" is.
- PHI. The test user is non-PHI by construction; if the agent
  accidentally walks a real visit with PHI, redact the SOAP body /
  patient name / etc. before writing the report.
- Prose about how the agent feels. The agent reports findings, not
  vibes.
- Auto-fix patches. The agent describes the fix; Kasra writes it.

## What the report SHOULD contain

- Verbatim file:line cites. Every claim about code points to a real
  line the reader can open.
- Verbatim observed strings. If the DOM shows "Subjective section is
  empty," quote those four words exactly.
- Verbatim DB column values (truncated to 200 chars if long; full value
  preserved in a referenced fixture file if needed).
- A reproduction the next agent run (or a human) can re-execute.

## Empty-report case

If the sweep produces zero findings, the agent still emits the front-
matter block + "Findings: 0 (P0: 0, P1: 0, P2: 0, P3: 0, Bonus: 0)" +
the line "No bugs found in this sweep — workflow walked end-to-end with
all clicks producing the expected state changes." That's the audit
trail Kasra needs to know the run completed (vs. crashed silently).
