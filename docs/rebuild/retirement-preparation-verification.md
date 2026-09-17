# Retirement preparation verification — 2026-09-17

Completed by the ownership audit agent before any live retirement execution:

- Read-only `python3 scripts/retire-old-quillmd.py` passed against the pinned manifest: exact container identities/mounts, dedicated QA volume consumers, forty dedicated old application tables plus seven protected marketing leads, and marketing HTTP 200.
- `--execute` without the mutation gate's declaration/commit environment refused before inspecting or changing live resources.
- Python script compilation and `git diff --check` passed.
- Removed the two verified old application directories and four dedicated packages from the **fresh worktree only**: 1,654 tracked files, 489,600 deleted lines. Shared main was not edited.
- Changed npm workspaces to `apps/marketing` and `packages/shared`, removed old application npm scripts, and repaired marketing Dockerfile COPY dependencies. The lockfile has zero obsolete application/package workspace records.
- Clean `npm ci --ignore-scripts --no-audit --no-fund` succeeded with 507 packages.
- `npm run build -w marketing` succeeded: Next.js 16.3.4, compilation, TypeScript checks, and all 13 static pages. The existing Sentry `disableLogger` deprecation warning remains; it did not affect the build. The existing shared lockfile already specified Next.js 16.3.4; the preserved marketing source was not upgraded by this task.

The old production/QA application services and data remained untouched by this agent. The lead must review, commit and execute the prepared declaration/script through the mutation gate. `docs/rebuild/retirement-result.json`, if present, is the post-execution evidence; this preparation report is not evidence of deletion.

The repository's old compose and CI files still refer to the old application until separately replaced by the lead; those are not compatibility requirements for the fresh application. Public ingress must not be redirected to the private development server.
