# Code Quality / Pattern Auditor

> **Status: ACTIVE** as of merge of branch `agent/code-quality-auditor-v1`.
> Fourth member of the QuillMD agent roster. Runs at PR time + on demand.

A PR-diff-shaped auditor that enforces QuillMD's *actual* production
conventions — design tokens, component patterns, Prisma schema rules,
BullMQ pipeline patterns, server/client boundary, folder layout, scope
guards. Every rule is grounded in a specific reference file/line in
this codebase; rules without a live anchor are deleted, not preserved.

## Why this agent (not part of the other three)

QuillMD's existing agents catch different bug classes:

- `qa-interaction-auditor` (active v3.3) — walks the UI; click-class
  bugs (orphan dispatchers, "pretend success" fallbacks, parser /
  renderer mismatches).
- `ai-pipeline-auditor` (dormant) — AI pipeline drift (cost / quality
  / coverage / model assignment).
- `hipaa-compliance-auditor` (staged) — compliance posture
  (§164.308 / §164.310 / §164.312).

None catches **pattern drift across the codebase at PR time** — the
class of issue where a diff typechecks, passes tests, passes review,
and ships, but quietly drifts from how the rest of the codebase does
the same thing. PR #176's RxWarningsRail override-modal bridge had been
sitting in this gap for weeks: the modal + server action + audit row
+ sign-API guard all shipped in production, the dev preview at
`/dev/rx-warnings` worked — but the bridge from the production rail
to the modal was never wired. A reviewer reading a PR for behaviour
doesn't catch that. A pattern auditor that knows "every critical Rx
warning needs an `OverrideConfirmModal` mount in the rail file" would.

This agent is that auditor.

## Triad → quartet

```
qa-interaction-auditor       → catches UI behaviour bugs
ai-pipeline-auditor          → catches AI pipeline drift
hipaa-compliance-auditor     → catches compliance posture drift
code-quality-auditor (NEW)   → catches pattern drift at PR time
```

The four agents have explicitly defined boundaries — see
[`docs/agents/CHARTERS.md`](../../../docs/agents/CHARTERS.md). The
closest-neighbour boundary (this agent ↔ HIPAA) is called out in
detail there: this one checks pattern *presence* at PR time, HIPAA
checks runtime *correctness* on the live system.

## Trigger phrases

Lead invokes this agent when Kasra asks any of:

- **"Run code quality audit on PR #N"** — fetches `gh pr diff` and audits.
- **"Audit diff for pattern compliance"** — audits the current
  uncommitted working tree (`git diff` + untracked).
- **"Code quality audit on `<path>`"** — audits a specific file or
  folder, recursive.

Flexible aliases work too: "code quality audit", "pattern audit on
PR #N", "convention check on this diff".

## What it audits (high level)

27 rules across 8 categories. Severity-tiered:

| Category | BLOCK | WARN | NIT |
|---|---|---|---|
| Design tokens | 1 | 2 | 1 |
| React component patterns | 2 | 3 | 1 |
| Prisma / schema | 2 | 1 | 1 |
| BullMQ / pipeline | 2 | 1 | 0 |
| Server / client boundary | 1 | 1 | 1 |
| Folder layout | 1 | 1 | 1 |
| Scope guards | 2 | 0 | 0 |
| Documentation hygiene | 0 | 0 | 2 |
| **Total** | **11** | **9** | **7** |

Full rule definitions in [`rules.md`](rules.md). Methodology in
[`skills/methodology.md`](skills/methodology.md).

## Severity tiers

- **BLOCK** — pattern violation that breaks consistency or risks safety.
  Block merge.
- **WARN** — drift from convention but not breaking. Author should fix
  before merge or get reviewer agreement.
- **NIT** — style preference. Author may ignore.

## Activation gate

**None.** The auditor is read-only against diffs. No PHI access, no
database access, no MinIO access, no production traffic dependency.
Activates on merge.

This is different from `ai-pipeline-auditor` (gated on ≥20 visits ×
≥3 doctors) and `hipaa-compliance-auditor` (staged per-phase
activation). Pattern auditing has no data threshold; the rules
ground in the codebase, not the runtime.

## File layout

Mirrors `hipaa-compliance-auditor` (most-recent agent design, PR #170)
+ adds `rules.md` and `samples/` specific to this agent's needs:

```
.claude/agents/code-quality-auditor/
├── README.md                       (this file — operator-facing)
├── SKILL.md                        (skill registration; ACTIVE)
├── rules.md                        (rule library — Part A deliverable)
├── fixtures/.gitkeep
├── scripts/.gitkeep                (placeholder; agent runs in-process)
├── samples/
│   ├── pr-176-sample-run.md        (real audit on PR #176)
│   └── pr-167-sample-run.md        (real audit on PR #167)
└── skills/
    ├── activation-criteria.md
    ├── data-sources.md
    ├── finding-classes.md
    └── methodology.md
```

## Scope reminder

Auditor reads diffs from `apps/transcribe-md/**` and `apps/marketing/**`
only. `apps/meddoc-pro/**` is **excluded** — legacy decommissioned per
`docs/POST_MERGE_TODO.md §21` and per memory. Any diff line in
`apps/meddoc-pro/**` is silently dropped from the input set; any diff
that *references* `apps/meddoc-pro/**` from inside the in-scope apps
emits `SCOPE-001` BLOCK.

## Hand-off contract

Lead, when invoking this agent:

1. Resolve the input (PR diff, working-tree diff, file path) per the
   trigger phrase.
2. Read [`rules.md`](rules.md) start-to-finish (the rule library +
   anchor-check guard).
3. Read [`skills/methodology.md`](skills/methodology.md) for the
   algorithm.
4. Apply rules in category order against the in-scope diff.
5. Emit the markdown report per the SKILL.md output format.
6. If output capture is requested, write to
   `docs/agent-reports/code-quality/<timestamp>-<pr-or-path>.md`
   (create the dir if missing).

The agent has no separate scripted runner today; it runs in Lead's
process. The `scripts/` dir is a placeholder for future automation
(e.g. a CI hook that calls the agent on every PR).
