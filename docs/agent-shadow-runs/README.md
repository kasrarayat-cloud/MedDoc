# Agent shadow-run reports

> Output path for **shadow-mode** agents. Shadow mode means
> findings are advisory: surfaced for the operator to read +
> decide on, but never wired to block merges, deploys, or
> trigger automated action.

## Directory layout

```
docs/agent-shadow-runs/
├── ai-pipeline/        # ai-pipeline-auditor shadow output
│   └── <UTC-timestamp>.md
└── hipaa-compliance/   # hipaa-compliance-auditor shadow output
    └── <UTC-timestamp>.md
```

## Conventions

- One file per run; filename is the UTC timestamp.
- Format is markdown structured per the agent's
  `methodology.md` phase order.
- Findings preserve their severity (a `BLOCKING_*` in shadow
  is still a `BLOCKING_*` — shadow only relocates the report,
  it never downgrades).
- Phase coverage table at the top of each report shows which
  phases ran vs which emitted `NO_DATA` because their
  activation gate was not met.

## What this directory is NOT

- Not the production audit-report path. Those live at
  `docs/ai-pipeline-audit-reports/` and
  `docs/hipaa-compliance-reports/` and only get populated
  after the agent graduates from shadow.
- Not authoritative for compliance reporting. A shadow report
  is operator-facing intuition; a production report is
  external-audience-facing record.
- Not retained forever. Once a directory accumulates ~30
  reports, group them into per-month subdirs (`2026-05/`,
  `2026-06/`) so the listing stays readable.

## Graduation

Each agent's `skills/activation-criteria.md` defines the four
criteria that must hold before that agent moves from this
shadow path to its production report path. Until then, all
output lands here.
