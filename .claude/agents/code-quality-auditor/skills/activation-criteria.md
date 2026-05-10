# Activation criteria — Code Quality / Pattern Auditor

> **Status: ACTIVE on merge.** This agent has no activation gate.

## Why no gate

The other three agents in the roster carry activation gates:

- `qa-interaction-auditor` — none (active v3.3); active because the
  underlying signal (UI surfaces) exists immediately.
- `ai-pipeline-auditor` — gated on **≥20 visits across ≥3 distinct
  doctors** with `status=READY`. Below threshold the findings would
  be stylistic rather than behavioural.
- `hipaa-compliance-auditor` — staged per-phase. Phases 0/5/6/7/8/9
  run today; phases 1+4 need ≥3 active accounts; phases 2+3 share the
  same pilot threshold as `ai-pipeline-auditor`.

Pattern auditing's signal is the **codebase itself**, not runtime data.
Every rule grounds in a specific reference file/line in
`apps/transcribe-md/**` or `apps/marketing/**`. Those files exist on
day 0 of merge; no pilot-data threshold applies.

The only signal the auditor *could* drift on is its own anchor list.
The `RULE_STALE` guard (rules.md tail) handles that: at run-start the
auditor dereferences each rule's `canonical_ref` and emits one
`RULE_STALE` BLOCK *against itself* before scoring the diff.

## Risk profile

- **Read-only.** The auditor reads diffs and rule anchors. It never
  writes, never reads PHI content, never touches the database, never
  touches MinIO, never makes outbound network calls.
- **No PHI exposure.** Diff lines are quoted in findings — diffs
  authored against transcribe-md may contain placeholder PHI in
  fixtures. The auditor flags `BLOCK` if it sees a real-looking name
  / date-of-birth / MRN in a non-fixture file (rule `DOC-003` —
  staged for v1.1; not in current rule library to keep the ship list
  tight).
- **No state.** Each invocation is independent. No queue, no cache,
  no learned baseline.

Risk is therefore zero — there is no gate to wait for.

## Operator triggers (recap)

Lead invokes when Kasra asks any of (see SKILL.md for the full list):

- "Run code quality audit on PR #N"
- "Audit diff for pattern compliance"
- "Code quality audit on `<path>`"

Plus aliases ("pattern audit", "convention check", etc.).

## Future activation modes (not yet wired)

- **PR-CI hook.** A GitHub Action could invoke the agent on every PR
  open and post the report as a PR comment. Ships in a follow-up PR
  alongside `scripts/` content; not in v1 to keep the rule library
  the proven-on-real-PRs first.
- **Pre-push hook.** Same agent against `git diff origin/main..HEAD`
  on the developer machine. Same code path; different invocation
  context.

Both modes consume the *same* `rules.md` + `skills/methodology.md`.
Activation order: rule library proven on real PRs (v1, this ship) →
PR-CI hook (v1.1) → optional pre-push hook (v1.2).
