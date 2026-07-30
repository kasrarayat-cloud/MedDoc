# B-017 additive provider-ownership checkpoint

Date: 2026-07-20 UTC

This is an implementation checkpoint, not release acceptance.

- Branch: `fix/template-twin-provider-ownership-b017-v1`
- Commit: `db1cab904ac5c8d6c7f25878f59d71e1b094a223`
- Tree: `aea6476f25001d89db9eca285448f989f0b90a19`
- Parent: `1804fe79d45aa6d3658cd17976cce5caddb09785`
- Scope: provider ownership, synthetic voice admission, pre-provider worker
  census, AI provider adapters, and the additive ownership migration.
- Production effects: none. No PHI/provider egress, push, merge, deployment,
  or production mutation occurred.

## Detached exact-commit verification

The commit was checked in a fresh detached worktree installed from the locked
NPM manifest.

- Prisma format: PASS, no tracked diff.
- Prisma validate: PASS.
- Prisma generate: PASS.
- TranscribeMD TypeScript (`tsc --noEmit`): PASS.
- Provider/synthetic/worker focused set excluding the combined-head static
  contract: 7 files / 112 tests PASS.
- Worker unit directory: 11 files / 114 tests PASS.
- Worker-layer unit directory: 24 files / 331 tests PASS.
- AI adapter focused set: 3 files / 31 tests PASS.
- Changed-file census: 18 files / 280 tests PASS; one stateful integration
  test FAIL.

## Open exact-head failures

1. `upload-certification.integration.test.ts` deterministically reaches the
   terminal failed provider-execution claim on a same-evidence retry instead
   of the intended stale-rollout assertion. The implementation hard-codes
   logical attempt 1 for this provider slot. A server-owned retry/idempotency
   decision and additive regression are required; ambiguity must remain
   fail-closed.
2. The older exact-commit `staging-qa-route-boundary.test.ts` has two static
   assertions that intentionally depend on the still-uncommitted sign and
   combined-boundary tranche. The updated combined-head contract must be
   committed and rerun; this checkpoint is not independently green.

Per release policy, neither failure is waived. The branch remains open for
additive fixes and will require a fresh clean exact-head review.
