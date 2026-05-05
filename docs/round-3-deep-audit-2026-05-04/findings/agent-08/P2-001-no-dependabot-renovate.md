---
id: A08-P2-001
title: No Dependabot / Renovate config — zero automated security update cadence
severity: P2
domain: dependency-hygiene-supply-chain
status: open
---

## Issue

The repo has **no automated dependency-update tooling configured**. There is no
`.github/dependabot.yml`, no `renovate.json`, no `.renovaterc`, no GitHub-app webhook for
dependency PRs. The `.github/` directory contains only:

```
.github/
└── workflows/
    ├── a11y.yml
    ├── nightly-tests.yml
    └── test.yml
```

Dependency bumps are presumably manual. With 1,157 production+dev deps in the lockfile and
8 currently-open `npm audit` findings (see A08-P2-002), this scales poorly.

## Evidence

```bash
$ ls /opt/meddoc-pro/.github/
workflows
$ find /opt/meddoc-pro -maxdepth 4 -name "renovate*" -o -name "dependabot*" 2>/dev/null \
    | grep -v node_modules
(no output)
```

For comparison, `npm outdated --workspaces` lists 30+ packages with available updates
including `@anthropic-ai/sdk` (0.85 → 0.93, fixes a moderate-severity advisory), `prisma`
(7.7 → 7.8), `bullmq` (5.76.1 → 5.76.5, fixes the moderate uuid CVE), and `vitest`. Without
automation, those bumps queue up indefinitely.

## Risk

- **Slow CVE remediation**: when a high-severity advisory drops on `next` or `next-auth` or
  `prisma`, there's no PR waiting on Monday morning — someone has to remember to run
  `npm audit` and craft the upgrade. For a HIPAA-handling app, "we patch when we get around
  to it" is not a defensible posture if a breach investigator asks.
- **Drift accumulates**: every week without automation, the upgrade cliff gets steeper. The
  `apps/scribe` ghost workspace in the lockfile (see A08-P2-003) is a symptom of exactly
  this — manual hygiene that's been deferred.
- **Supply-chain compromise visibility**: Dependabot/Renovate also surface lockfile-only
  diffs (e.g., a transitive package that suddenly has a new maintainer pushing a release).
  Without it, those changes land silently on `npm install`.

## Recommended fix

Add `.github/dependabot.yml` with **at minimum**:

```yaml
version: 2
updates:
  # ── npm (root + every workspace) ──
  - package-ecosystem: "npm"
    directory: "/"
    schedule: { interval: "weekly", day: "monday" }
    open-pull-requests-limit: 10
    groups:
      sentry:        { patterns: ["@sentry/*"] }
      prisma:        { patterns: ["prisma", "@prisma/*"] }
      next:          { patterns: ["next", "next-auth", "eslint-config-next"] }
      tailwind:      { patterns: ["tailwindcss", "@tailwindcss/*", "tailwind-*"] }
      types:         { patterns: ["@types/*"] }
    ignore:
      # next-auth v5 is a beta-only train; bumps need human review (see A08-P1-001).
      - dependency-name: "next-auth"
        update-types: ["version-update:semver-major", "version-update:semver-minor"]
    # Apply across every workspace
    target-branch: "main"
    labels: ["deps", "auto"]

  # ── Docker base images (works only after A08-P1-002 is shipped — Dependabot needs
  #    explicit FROM lines with digests to update) ──
  - package-ecosystem: "docker"
    directory: "/apps/transcribe-md"
    schedule: { interval: "weekly", day: "monday" }
  - package-ecosystem: "docker"
    directory: "/apps/marketing"
    schedule: { interval: "weekly", day: "monday" }
  - package-ecosystem: "docker"
    directory: "/apps/meddoc-pro"
    schedule: { interval: "weekly", day: "monday" }

  # ── GitHub Actions versions (a11y.yml uses actions/checkout@v4 etc.) ──
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "monthly" }
```

Alternatively use Renovate (more granular grouping, lockfile-only updates as separate PRs)
— the Renovate equivalent is `renovate.json` with `"extends": ["config:recommended"]` and
the same ignore rules.

Pair with a **CODEOWNERS** rule so dep PRs route to whoever owns the workspace
(`/packages/auth/* @kasra` etc.).

## Cross-domain hooks

- Agent 09 (CI/CD): the auto-merge rules — typically "patch + green CI = auto-merge, minor
  needs review, major requires explicit approval" — live in the same workflow surface.
- A08-P1-002 (image pinning) blocks the docker ecosystem entries from being useful.
- A08-P2-002 (current `npm audit` findings): once Dependabot is on, those would each become
  a tracked PR.
