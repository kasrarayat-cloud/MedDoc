# Worker-role remediation exact-head review receipt

Generated: 2026-07-21T01:27:48Z

## Release identity

- Branch: `fix/template-twin-provider-ownership-b017-v1`
- Rejected parent: `bcf5c0bbc098ec777ab850cc3df4e72070453402`
- Additive exact candidate: `2d9c8f8e41fc0e20279ae3d6a253ec10405bc367`
- Git tree: `669b4483c9f4f66f0fa610c5e9bbb103d7c3df42`
- Binary diff SHA-256, rejected parent to candidate:
  `14e23193466087d619db9ed6ce64f102ebdeaf16775251bdafcc7ecf4a646f12`
- Binary diff SHA-256, `e7b3864` baseline to candidate:
  `94c0d6f7d92dd6419ac3244e15babb5e479b04e869225d1970f3539e886645c9`
- Recursive Git tree-listing SHA-256:
  `6d740c0c145a68bff715a67d0a426104478a6d51daab05323786926c28a8c47b`
- Candidate worktree after commit: clean.

## Rejected-head finding and additive closure

The fresh detached review of `bcf5c0b` returned REJECT for one P1: the clinical
worker called a generic known-role/database-principal validator without first
binding the executable to the exact `transcribe-md-worker` service role.

The additive commit introduces a pure exact-role startup assertion and invokes
it before runtime protocol validation, database proof, and queue construction.
It rejects the six other reviewed service roles, missing/blank/non-exact roles,
unknown roles, and configured wrong roles outside production. Truly
identity-free local development remains supported and the generic database
proof still enforces production/configured identity requirements.

## Candidate verification claims supplied to the fresh reviewer

- Worker/runtime-protocol focus: 2 files / 53 tests PASS.
- Full TranscribeMD unit census: 417 files / 5,614 tests PASS.
- TranscribeMD standalone TypeScript: PASS.
- Changed-file ESLint: PASS.
- Diff whitespace: PASS.
- Exact source-order contract places worker-role assertion before runtime
  protocol, database proof, and main queue construction.

These are implementation-side claims. The replacement SHA was assigned to a
new detached workspace and must receive a new independent verdict.

## Independent exact-head review

- Authentication/runtime replacement review: **scoped ACCEPT**, no P0/P1/P2.
  The reviewer independently passed 26 files / 534 tests, the 26-test shared
  session-authority suite, 2 MedDoc files / 7 tests, both type checks, lint,
  runtime/database censuses, syntax, diff, and clean-worktree checks. The prior
  worker-role P1 is closed.
- Database/infrastructure review: **REJECT**, one P1 inherited from the parent.
  The v9 helper adds seven application function-ACL rows and changes every
  granted boundary manifest, but the frozen runtime contract retained pre-v9
  hashes. A fresh exact-profile runtime therefore rejects the first post-v9
  catalog assertion. Other database gates passed.
- Exact-head verdict: **REJECT**. Regenerate the affected manifests from two
  independent pinned clusters, update the frozen contract, add a clean ordered
  migration/runtime regression, commit additively, and obtain a fresh complete
  detached review.

## Release and preservation boundary

Production remains NOT RELEASED at 0%. No production migration, deployment,
flag change, provider call, credential change, PHI, canary, or physician
rollout occurred.

During the rejected-parent database review, one diagnostic patch briefly
created then removed the reviewer-owned untracked path
`/opt/meddoc-pro/.review-exact-diagnostics.ts`. No tracked/pre-existing path was
reported touched. The lead read-only post-incident observation retained branch
`feat/template-twin-docx-v1`, SHA
`bb1c828189ee95f85136c7ebd79d07e52467782a`, and the prior NUL-status SHA-256
`f2426a8fb327fcc6c5ae5721eb6a5f3823ef723eacc72856636eac81054da461`;
the diagnostic path was absent. Perfect no-write continuity is not claimed.
Final read-only reconciliation remains required.
