# Authentication and database-release exact-head closure receipt

Generated: 2026-07-21T06:40:00Z

## Verdict

**IMPLEMENTATION COMMITTED; FRESH INDEPENDENT EXACT-HEAD VERDICTS PENDING;
PRODUCTION RELEASE FAIL.** Exact `50286004` was independently rejected. This
receipt records the additive closure and synthetic implementation-side evidence
for its successor. It authorizes no production migration, deployment, provider
call, credential change, PHI, canary, or physician rollout.

## Immutable identity

- Branch: `fix/template-twin-provider-ownership-b017-v1`
- Rejected parent: `50286004f9bc7f940602206e50b24679ab1c2b38`
- Additive candidate: `25047df1fe095e47610b9e9eda4e25bb2b821d46`
- Git tree: `58c7d400886ad4e745e47c6883ad4ddbba9924b3`
- Binary diff SHA-256, parent to candidate:
  `12ffc87b51e22413cf2bd1ec951e33bfb6952dfeb26bc610f97b84cb0c1a7714`
- Recursive Git tree-listing SHA-256:
  `9fbdfd132e75694cf55e42e38c2203a326345ca87b7b9b6390f73010040e98bc`
- Worktree immediately after commit: clean

## Independent-review handoff

- Neutral bundle:
  `review-handoff-25047df1.bundle`
- Bundle SHA-256:
  `046a26004a77e94836740c30f9be97378201630bce5551e509378d9df5d57334`
- Bundle mode: `0400`
- `git bundle verify`: PASS
- Advertised head: exact candidate above
- Required base: `1be101912f01293de3b8fddae722c823ecc86f29`

The auth/operator and security reviewers must import this bundle into separate
fresh detached workspaces. Neither may rely on this receipt as proof.

## Additive closure

- `docs/POST_MERGE_TODO.md` is explicitly historical and superseded. Its raw
  migration commands were removed, and it is now enumerated by the closed
  database-release documentation contract.
- Actual-PostgreSQL regression source now disables and restores all four
  internal referential-integrity triggers on `auth_tokens`, requiring exact-
  principal rejection while enforcement is disabled and acceptance only after
  restoration.
- Actual-PostgreSQL regression source queues `DROP INDEX CONCURRENTLY` ahead of
  auth-token finalization's `ACCESS EXCLUSIVE` lock, requiring the locked reproof
  to reject while preserving the exact transition guard, then proving safe
  recovery.
- Synthetic cleanup now treats exact-name census, label inspection, deletion,
  and post-delete absence as one fail-closed protocol. Any ambiguity retains
  state and temporary evidence and suppresses `CLEANUP_PASS`.
- TypeScript constructs that Semgrep 1.161/1.164 only partially parsed were
  rewritten without changing runtime behavior. Every main-targeting TypeScript
  file is now parsed by the strict gate.
- All main-targeting trailing whitespace found by the rejected security review
  was removed. Human approval fields remain explicit and unsigned.
- Release status, checklist, and blocker records now name rejected exact head
  `50286004` and preserve every still-open technical and human gate.

## Implementation-side verification

- Full TranscribeMD unit census: **427/427 files and 5,758/5,758 tests PASS**.
- Full MedDoc data-bearing synthetic census: **11/11 files and 103/103 tests
  PASS**.
- One fresh closed synthetic PostgreSQL release environment applied **97/97
  migrations**, completed the segmented release path and principal proofs, and
  emitted provision and hardened cleanup PASS markers.
- Post-cleanup Docker census: zero labeled containers, volumes, or images.
- Closed operator documentation plus synthetic cleanup contracts: **3/3 files
  and 21/21 tests PASS**. Cleanup negative paths alone: **4/4 PASS** under the
  TranscribeMD runner; combined cleanup contracts: **10/10 PASS**.
- Parser-compatibility focused regressions: **3/3 files and 36/36 tests PASS**.
- Standalone TranscribeMD TypeScript: PASS.
- Standalone database script TypeScript under ESNext/Bundler resolution: PASS.
- TranscribeMD Next.js 16.2.6 production build and server-action manifest gate:
  PASS; 30 source and 28 compiled exports classified.
- MedDoc Next.js 16.2.6 production build: PASS.
- Changed-file ESLint: PASS with only the repository's non-failing pages-path
  diagnostic.
- Local and `origin/main` diff whitespace checks: PASS.
- Semgrep 1.161.0 `p/typescript --strict`: **791 scanned, 0 skipped, 0 errors,
  0 findings**.
- Exact `50286004` dependency gate remains **0 critical / 0 high**, with **12
  moderate / 1 low** explicitly retained for final-RC disposition. No dependency
  or lockfile changed in this additive commit; a fresh exact-head audit remains
  assigned to the independent security reviewer.
- Exact `50286004` whole-workspace verified-only secret scan had zero verified
  findings. A fresh exact-head scan remains assigned to the independent security
  reviewer.
- Provider calls: 0. Production writes: 0. PHI: 0.

### Incremental test census

| Suite | Rejected parent `50286004` | Candidate `25047df1` | Delta |
| --- | ---: | ---: | ---: |
| TranscribeMD files | 426 | 427 | +1 |
| TranscribeMD tests | 5,754 | 5,758 | +4 |
| MedDoc files | 11 | 11 | 0 |
| MedDoc tests | 103 | 103 | 0 |

The new committed PostgreSQL adversarial scripts were typechecked but were not
represented as implementation-side live PASS. The independent auth/operator
reviewer must execute them against fresh isolated PostgreSQL 16 and report the
exact-head result.

## Open gates

Fresh detached auth/operator ACCEPT, fresh detached security ACCEPT, PR CI,
production backup/restore and identity authority, immutable deployment images
and rollback rehearsal, credential rotation, desktop Word evidence,
provider-quality evidence, and signed Clinical Safety, Privacy/Legal, and
Operations approvals remain mandatory. Production availability is 0%.

`/opt/meddoc-pro` was not switched, reset, cleaned, stashed, or modified by
this implementation. Its final branch/SHA/status reconciliation remains
required.
