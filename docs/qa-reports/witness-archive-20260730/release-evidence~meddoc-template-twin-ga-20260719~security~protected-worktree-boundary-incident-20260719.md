# Protected worktree boundary incident

- Date: 2026-07-19 UTC
- Protected worktree: `/opt/meddoc-pro`
- Branch: `feat/template-twin-docx-v1`
- Commit: `bb1c828189ee95f85136c7ebd79d07e52467782a`
- Classification: process-boundary breach, exact restoration verified; no production effect

## What happened

A component agent invoked `apply_patch` with repository-relative paths from the
shared session working directory. Four intended changes for the clean component
worktree were therefore briefly applied under `/opt/meddoc-pro`. The mistake was
detected before commit, push, build, deployment, or production access.

Affected paths:

1. `apps/transcribe-md/src/lib/template-twin/__tests__/certification-lifecycle.test.ts`
2. `apps/transcribe-md/src/lib/template-twin/__tests__/create-draft-orchestration.test.ts`
3. `apps/transcribe-md/src/lib/template-twin/__tests__/upload-certification.integration.test.ts`
4. `apps/transcribe-md/src/worker/note-templates/resolve-active-template.ts`

## Restoration evidence

Each affected file was restored to the exact protected-worktree `HEAD` blob.
Each current file SHA-256 equals the corresponding `git show HEAD:<path>`
SHA-256, and each path is absent from `git status`:

| Path ordinal | SHA-256 |
|---|---|
| 1 | `390471d268ac60ffc0cfd6a8eb342713b99bd114676cda59265835901400e060` |
| 2 | `edab56f424984495049f5999cd633b4116d2df96ce18abd27a68b80a7bec42f1` |
| 3 | `c1e2944b3dff8282e2b8717a4b2f322666ff6d5e9f752de44ed85e909c677d7a` |
| 4 | `abd029580b9cb477c72bbb9f822536572de4e71821a215359957f4f9a2bcf474` |

The lead agent independently captured the protected worktree's full
`git status --porcelain=v2 -z` SHA-256 before the incident and again after
restoration. Both are:

`4279d7ecbb04309cf7db358ea6a9959785d79fdc7a2dc98132ee0982a6d8115d`

This proves the pre-existing dirty-status record is identical and, together
with the per-file HEAD equality, proves exact restoration of the four affected
files. No reset, clean, stash, branch switch, commit, or deployment occurred in
the protected worktree.

## Prevention

All subsequent edits must use absolute paths validated to begin with the
assigned clean worktree under `/home/claude/release-programs/`. Relative
`apply_patch` targets are forbidden for the remaining program. No further
access to `/opt/meddoc-pro` is permitted except a final read-only release
inventory if still required.

## Second incident — reviewer evidence script

- Detected: 2026-07-19T23:22:31Z
- Intended target: a synthetic negative-DOCX evidence script outside the repository
- Mistaken path: `/opt/meddoc-pro/independent-negative-docx.ts`
- Object type: newly created untracked file only

A detached reviewer invoked the raw patch tool without an explicit working
directory while constructing an independent synthetic evidence script. The
tool therefore briefly created the new untracked file above in the protected
worktree. The reviewer immediately deleted exactly that newly created file by
patch, did not read protected source, and reported the boundary error to the
lead agent. No tracked file, pre-existing untracked file, branch, index,
container, or production resource was changed.

The lead agent then performed only the minimum hash-only verification. The
full `git status --porcelain=v2 -z` SHA-256 remained exactly:

`4279d7ecbb04309cf7db358ea6a9959785d79fdc7a2dc98132ee0982a6d8115d`

This equals the pre-incident fingerprint recorded above and confirms that the
protected worktree's pre-existing dirty-status set was preserved exactly. No
further protected-worktree access is authorized except a necessary final
hash-only preservation check.
