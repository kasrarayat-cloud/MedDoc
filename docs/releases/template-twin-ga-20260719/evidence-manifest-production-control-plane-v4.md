# Template Twin production control plane — page access receipt hardening v4

Verdict: **P1 DEFENSIVE REMEDIATION TECHNICALLY PASS; REPOSITORY-WIDE
MIGRATION DRIFT FAIL; FRESH INDEPENDENT EXACT-HEAD REVIEW AND COMBINED
INTEGRATION REQUIRED.** This manifest does not authorize production migration,
deployment, canary, or physician rollout.

## Identity and review boundary

- Additive parent:
  `8195e2170817b0b501b6c769d98f85f70afd69d6`
- Parent review: **REJECT**, P0=0/P1=1/P2=0. The P1 was the
  server-rendered `/admin/template-twin-release` inspection occurring without
  an awaited durable release-control access receipt.
- Additive v4 commit: recorded in the release-program handoff because a commit
  cannot contain its own content-addressed identity
- Branch: `agent/template-twin-control-plane-20260719`
- Isolated worktree:
  `/home/claude/release-programs/meddoc-template-twin-control-plane-20260719`
- Production mutations, provider egress, real documents, and PHI: **none**
- Production credentials read or printed: **none**
- Protected `/opt/meddoc-pro` repository source changes: **none**
- Database migrations, schema, grants, Compose, and runtime rollout behavior:
  **unchanged by v4**

## Remediation contract

- The exact release page obtains request headers, verifies the dedicated admin
  host, authenticates the cookie claim, and completes the fresh database-backed
  SUPER_ADMIN/session/MFA gate before audit or inspection.
- It then awaits a durable `template_twin_audit_outbox` receipt through the
  restricted release-control connection. Only after that promise resolves can
  `inspectTemplateTwinReleaseControl` execute.
- Receipt failure terminates the server-component render through `notFound()`;
  the inspection function and client workbench receive no sensitive state.
- The page helper accepts no caller-selected path, route key, or method. It
  fixes those values to `GET`, `/admin/template-twin-release`, and
  `template-twin:release:page`.
- Actor/practice identifiers are nonblank, untrimmed-control-free, and at most
  191 characters; email snapshots are nullable and at most 320 characters;
  route keys and paths remain capped at 96 and 160 characters. `x-real-ip` is
  accepted only as a valid IP within 64 characters and user agent is capped at
  512 characters.
- Existing API callers retain their `GET`/`POST` and
  `/api/admin/template-twin/` contract. Their fail-closed durable receipt path
  is unchanged in behavior.
- The best-effort layout `void logAudit` remains defense in depth only and is
  not part of the release page's authorization or durable evidence gate.

## Verification census

| Gate | Result | Evidence |
| --- | --- | --- |
| Page success and failure ordering | PASS | Page unit tests prove `host → session/MFA → durable audit → inspect` and prove audit rejection produces `notFound` with zero inspection |
| Exact path/header/input bounds | PASS | Helper tests prove fixed page metadata, invalid/oversized identity rejection before SQL, oversized IP rejection, and 512-character user-agent cap |
| Expanded control-plane unit census | PASS | 12 files, 87/87 tests |
| Full application TypeScript | PASS | `tsc --noEmit` against exact worktree sources with temporary package path mapping; temporary config removed |
| Focused ESLint | PASS | All v4 application and test paths; zero warnings or errors |
| Next 16 production compilation | PASS, COMPILE-ONLY | Contained exact-source Turbopack compile succeeded. A full run using a shared read-only generated Prisma client also completed, but is deliberately not counted as an isolated release build because that client's exact schema provenance is not independently locked |
| Full isolated production build | COMBINED-HEAD PENDING | Release integration must build with an isolated dependency tree and a Prisma client generated from the accepted combined exact schema; v4 did not regenerate or mutate the shared client |
| Resolved Compose isolation | PASS | Synthetic `.env` proof reconfirmed exact APP/WORKER envelopes, blank raw role secrets, restricted admin DSN/environment/volumes/groups, and no sibling/provider/storage leakage; temporary `.env` removed |
| Database role/catalog contract | PASS | Disposable PostgreSQL reports four exact login memberships; release control has outbox INSERT but no raw session SELECT/UPDATE; zero Template Twin functions with a non-exact safe search path |
| Prisma/schema and shell syntax | PASS | Prisma validate, both role scripts `sh -n`, and `git diff --check` |
| Offline staged-file secret scan | PASS | TruffleHog no-verification scan reported zero findings |
| Verified-only staged-file secret scan | PASS | TruffleHog verified-only scan reported zero verified secrets |
| Fresh independent exact-head review | PENDING AT MANIFEST AUTHORING | The implementer cannot approve this remediation |
| Repository-wide migration drift | **FAIL — UNCHANGED BLOCKER** | Standalone v3 datasource-to-schema comparison remains exit 2; the separately reviewed additive schema reconciliation and an empty combined-head diff remain mandatory |
| Human and production gates | HUMAN PENDING | Desktop Word, Clinical Safety, Privacy/Legal, Operations, restore authority, image signing, deployment, and rollout remain outside this slice |

The first local build attempt was rejected before compilation because the clean
worktree's dependency cache is an external symlink, which Next 16 Turbopack
forbids. A contained project-root build then compiled exact sources. Its image
dependency tree carried a stale generated Prisma client and failed on an
unrelated existing model relation during type checking. A read-only shared
client completed the build, but v4 conservatively records only the exact-source
compile result. No Prisma generation was run into shared dependencies.

## Artifact SHA-256

Hashes cover the exact working-tree bytes before the additive v4 commit.

| Artifact | SHA-256 |
| --- | --- |
| `apps/transcribe-md/src/app/admin/template-twin-release/page.tsx` | `bf2d152a59e0309147226dae8ec8f077166bb179a4ec51373ba2b9ec3586a4f6` |
| `apps/transcribe-md/src/app/admin/template-twin-release/__tests__/page.test.tsx` | `47b3641f8b7054b177ac9b7bc8541ff8b02ea3445b05501e219a23fb35232042` |
| `apps/transcribe-md/src/lib/template-twin/release-control-access-audit.ts` | `c7919d00af3abd0e4a933cd6245aed1c3a93ea949cb094faa37add16e4a76162` |
| `apps/transcribe-md/src/lib/template-twin/__tests__/release-control-access-audit.test.ts` | `f98fe6881ebbce5a70fbce5905d1407f6ead7e4c6ddf386bb6cfa91feaf19185` |
| `docs/releases/template-twin-ga-20260719/evidence-manifest-production-control-plane-v3.md` | `4b277eec564e4b9747b44a7f836c296bbb1eb36a2958833930063722daa6ffa8` |

## Integration conditions

Integrate this v4 commit only after the full v1→v4 additive series and the
separately reviewed schema reconciliation are present together. Rerun an
isolated Prisma generate/build, the empty datasource-to-schema comparison,
complete test census, and a fresh detached exact-head review. All human and
production gates remain explicit `HUMAN PENDING` until signed or exercised by
the authorized owner.
