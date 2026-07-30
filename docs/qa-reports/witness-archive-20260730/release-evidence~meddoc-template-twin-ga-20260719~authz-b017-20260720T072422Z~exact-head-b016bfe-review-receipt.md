# Exact-head review receipt — b016bfe

Generated: 2026-07-21T07:35:18Z

Production verdict: **NOT RELEASED**. Availability remains **0%**. This
receipt authorizes no production, provider, credential, or PHI-bearing action.

## Immutable identity

- Branch: `fix/template-twin-provider-ownership-b017-v1`
- Exact commit: `b016bfe637e86f9f65ed894adee5871f07e9e526`
- Tree: `738784de34939178b34896b93b35ebf3a7e70665`
- Parent: `3a9151584c295ec168515f8d515c9bd3c7fb8a56`
- Required base: `1be101912f01293de3b8fddae722c823ecc86f29`
- Main-targeting binary-diff SHA-256:
  `6eaefb7cf4f3f11ad3e8168b9e0a8f31b83d763fb0292b6cd4269c56a36d7535`
- Recursive tree-list SHA-256:
  `0d96adc0fdf96ac11c3ccff8060ba6fb791050073237ab9753efc6b883b74fa1`
- Neutral bundle:
  `review-handoff-b016bfe.bundle`
- Bundle SHA-256:
  `cb1df80ed55f20705767187e38a7cc52a85d57b45304bb6ae14ab6e38ebcf849`
- Bundle mode: `0400`
- `git bundle verify`: **PASS**; advertises only the exact commit and requires
  the exact base above.

## Additive rejection closure

The parent security review returned **REJECT** with no P0/P1 and two P2
evidence-document defects. This exact descendant:

1. binds the whole-workspace verified-only scan claim to exact parent
   `3a915158` and states that the descendant receipt is external; and
2. replaces malformed escaped approval blanks with an explicit
   `UNFILLED — HUMAN REQUIRED` marker in all four human approval packets.

The database operator-document contract now enforces exact-SHA scan attribution,
the decision options, explicit unfilled markers for every human field, and the
absence of malformed escaped placeholders.

## Lead-agent exact-head verification

- Full TranscribeMD unit census: **427/427 files, 5,759/5,759 tests PASS**.
- Focused operator-document contract: **1/1 file, 12/12 tests PASS**.
- Fresh closed synthetic database replay: **97/97 migrations PASS**; tenancy
  fixtures seeded and exact-head MedDoc **11/11 files, 103/103 tests PASS**.
  Hardened cleanup passed and the final labeled Docker census is zero
  containers, zero volumes, and zero images. The mode-0600 job environment
  file and its exact temporary directories were deleted after cleanup.
- A preceding direct MedDoc invocation without the required synthetic database
  environment failed at the harness prerequisite (`DATABASE_URL` had no string
  password). It was not treated as product evidence; the closed replay above is
  the valid rerun.
- Exact-head production dependency gate: **0 critical, 0 high, 12 moderate,
  1 low** across 1,195 dependencies. Lower-severity debt remains unaccepted in
  the separate debt register.
- Targeted ESLint with the TranscribeMD configuration: **exit 0**. ESLint
  emitted only its existing pages-directory configuration notice.
- Main-targeting and local diff whitespace: **PASS**.
- Integration worktree after commit: **clean**.

The parent `3a915158` exact-head receipts remain the provenance for its
production builds, TypeScript, Prisma, strict Semgrep, and secret scans. The
`b016bfe` delta changes seven release documents and one operator-document
contract test; it changes no runtime, migration, schema, container, provider,
or production configuration.

## Review state

- Fresh detached authentication/operator review: **REJECT**, no P0/P1 and the
  same single P2 Prettier finding below. Its independent technical gates passed:
  17 files / 248 tests, contract 12/12, strict PostgreSQL 16 HBA, fresh 97-
  migration provision, queued index-drop/finalizer race and recovery, exact-
  principal four-RI-trigger disable/reject/restore plus six-profile baseline,
  v9 synchronization, fail-closed cleanup/absence, and sanitized offline secret
  census. Preserved receipt SHA-256:
  `6d681e956bf694927391396f1845392302e0e264d96f9bf9f661959990e5ceb8`.
- Fresh detached security review: **REJECT**, no P0/P1 and one P2. Prettier
  failed for four of eight additive files while all corresponding parent blobs
  passed. Every other security gate passed, and both prior documentation P2s
  were substantively closed. Sanitized reviewer receipt SHA-256:
  `3ab6a8e310553ce933688532d7430f5d6d3c47923ac03424f98325375c0cb280`.
- Additive formatting closure: exact
  `fc08599533f75dbd7bdf878a9d23595ab83d4be0`; fresh review required.
- PR #371 publication and CI: **PENDING**; this rejected head will not be
  published.
- Desktop Word, Clinical Safety, Privacy/Legal, Operations, credential
  rotation, production backup/restore, immutable image, rollback, deployment,
  and rollout gates remain **HUMAN PENDING** or **FAIL** as recorded in the
  repository checklist.

## Protected worktree

Final read-only observation of `/opt/meddoc-pro` before this commit remained:

- branch `feat/template-twin-docx-v1`;
- commit `bb1c828189ee95f85136c7ebd79d07e52467782a`; and
- NUL-status SHA-256
  `f2426a8fb327fcc6c5ae5721eb6a5f3823ef723eacc72856636eac81054da461`.

Release agents made no writes to that protected worktree.
