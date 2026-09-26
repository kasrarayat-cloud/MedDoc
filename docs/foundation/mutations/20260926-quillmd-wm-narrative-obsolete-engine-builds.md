# Declaration — remove nine superseded WM narrative Word engine builds, September 26, 2026

Authority: the owner's directive of 2026-09-26, recorded verbatim in
`docs/foundation/rulings/2026-09-26-owner-cleanup-authority.md`.

A disk reclamation inside one session's worktree. **No production file, service, database, document, credential,
backup, rollback image, financial record or provider call is involved.**

## The act

Executed by the owner, from `/opt/meddoc-pro/.worktrees/wm-narrative`, through the ruled-mutation door (this session is
denied `rm -rf`, and narrowing that deny would remove a broad protection):

    bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20260926-quillmd-wm-narrative-obsolete-engine-builds.md -- rm -rf rebuild/.runtime/word-narrative-build-1 rebuild/.runtime/word-narrative-build-2 rebuild/.runtime/word-narrative-build-3 rebuild/.runtime/word-narrative-build-4 rebuild/.runtime/word-narrative-build-5 rebuild/.runtime/word-narrative-build-6 rebuild/.runtime/word-narrative-build-7 rebuild/.runtime/word-narrative-build-8 rebuild/.runtime/word-narrative-build-9

## Verified before this declaration (2026-09-26 ~22:53Z)

- Each of the nine resolves (`realpath -e`) to a real directory at exactly that path inside the worktree's gitignored
  `rebuild/.runtime/`; none is a symlink; all are owned by the session account; built 2026-09-24 05:18–12:02Z.
- Nothing uses them: no running process names them; no script, config, compose file or systemd unit in the checkout,
  the shared tree or `/etc/systemd/system` references them; no committed document cites them. The candidate's engine
  is `word-narrative-build-10` (built from the unchanged `WmAdapter.cs`), used by every test, validation and CI proof.
- Their only record of provenance — each build's `build-proof.json` and `runtime-manifest.json`, 18 files — was copied
  to `rebuild/.runtime/proofs/superseded-word-narrative-builds/build-N/` and hash-matched (18 of 18).

## Expected delta

MUST change:
- the nine directories are gone; their measured size is **1,731 MB** (`du -sBM`: 267 + 8 × 183);
- the root filesystem's used space falls by about that much (baseline 22:53Z: 261,546 MB used, 28,134 MB available,
  90.29%) — co-tenant activity moves the figure by itself, so the comparison is made on the nine paths' size and the
  used-space change together.

MUST NOT change:
- `rebuild/.runtime/word-narrative-build-10/runtime-manifest.json` sha256
  `2a1e4477144207bed04d3f3d38cb3b276cdaf7e450ef7d622f1ee63cd4e0d756`, and its `build-proof.json`
  `9ded38e9e3f0c6271ce2551ef8adaaa8fbb83ecde7b7bfb0d836365b55c0dbca`;
- the preserved proofs: the sha256 of the sorted `sha256sum` listing of
  `rebuild/.runtime/proofs/superseded-word-narrative-builds/` =
  `971d9c74d7b198150fcd8a4465dc6ad5e01866e205c4956179ac51439bcb1431`;
- `rebuild/.runtime/nuget-cache` (331 MB, the offline package cache that reproduces build-10), `publication/`,
  `proofs/`, and every path outside the nine;
- production: the shared tree at `dedac162`, both private services healthy, public maintenance (503).

A difference not listed here is the finding.
