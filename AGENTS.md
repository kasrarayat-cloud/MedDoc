<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

<!-- BEGIN:preflight-gate -->
## Pre-flight health check

Before invoking ANY task matching the trigger criteria in the `preflight-health-check` skill, the lead agent MUST run that skill first. Treat its output as a gate:

- 🟢 **GO** — proceed silently (one-line confirmation only).
- 🟡 **FIX-AND-GO** — proceed, mention auto-fixes in final summary.
- 🔴 **BLOCK** — do not start the user's task. Report the blocker and ask the user how to proceed.

Trigger criteria (run preflight first):
- Task spawns 1+ subagents
- Task involves `next build`, `pnpm install`, `docker compose build`, or full-app `tsc --noEmit`
- Task references "Phase X", "Batch X", or "remodel"
- Task writes to multiple component files
- Task runs full test suites
- Task follows the `qa-clinician-remodel` skill

Skip preflight for: single-file reads, single-file edits (<50 lines), read-only queries, git status/log/diff inspection, and already-running QA reports.

Never bypass preflight on a major task. Never prompt the user "run preflight?" — just run it. Output is silent on GO, surfaced fully on FIX-AND-GO or BLOCK. Reports are always written to `docs/preflight-reports/preflight-<UTC-timestamp>.md` for the audit trail.
<!-- END:preflight-gate -->
