# Template Twin production control plane — hardening evidence manifest v3

Verdict: **TECHNICAL SLICE PASS; REPOSITORY-WIDE MIGRATION DRIFT FAIL;
INDEPENDENT EXACT-HEAD REVIEW AND COMBINED INTEGRATION REQUIRED.** This
manifest does not authorize a production migration, deployment, canary, or
physician rollout. It supersedes the technical acceptance claims in v1 and v2;
those manifests remain immutable records of the two rejected implementations.

## Identity and safety boundary

- Exact base before the control-plane series:
  `1edc68ca767869c9e92896930a329ed78e532229`
- Rejected v1 implementation:
  `734951e6aa95a994c3483caa3307ef5eb598e2c0`
- Self-rejected v2 hardening:
  `7a6723d3e192c30ed0c21fc76321b504a1f5fd89`
- Additive v3 commit: recorded in the release-program handoff because a commit
  cannot contain its own content-addressed identity
- Branch: `agent/template-twin-control-plane-20260719`
- Isolated worktree:
  `/home/claude/release-programs/meddoc-template-twin-control-plane-20260719`
- Production mutations, provider egress, real documents, and PHI: **none**
- Production credentials read or printed: **none**
- Protected `/opt/meddoc-pro` repository source changes: **none**
- Test target: loopback-only disposable PostgreSQL 16 databases, synthetic
  release identities, and synthetic Compose sentinel values

The v3 migration is additive. It preserves default-off rollout, takes the
global advisory and row locks before changing control-plane behavior, and
seeds no release, authority, approval, capability, cohort, metric, key, or
enablement row.

## Corrected trust boundaries

- APP and WORKER receive only their own generic signed runtime envelope;
  source envelope variables and all sibling envelopes resolve blank.
- The dedicated administrative process imports no shared `.env`, provider or
  object-storage credential, raw database password, ordinary runtime DSN,
  malware-scanner volume, or runtime attestation envelope.
- The administrative process authenticates through a narrow exact-session
  verifier and records access in the durable Template Twin audit outbox. Either
  verification or access-audit failure closes the request before its handler.
- Every installed public `template_twin_%` function has an explicit
  `pg_catalog, public, pg_temp` path. Runtime cannot create in `public` or read
  raw authority, metric, or capability evidence.
- SUPER_ADMIN entitlement loss participates in the atomic authority revoke and
  global-disable lifecycle. A live runtime attestation key cannot be revoked
  while exposure remains enabled.
- The separately provisioned `meddoc_release_security` login has only the
  non-login `quillmd_release_security` membership and is the sole service role
  permitted to invoke the atomic authority-revocation procedure.

## Verification census

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh migration chain | PASS | Official `prisma migrate deploy`; 88/88 exact migrations on fresh `template_twin_control_plane_v33_exact_test` |
| Data-bearing upgrade | PASS | Official exact 87→88 deploy on `template_twin_control_plane_v34_data_upgrade_test`; seven release candidates and the one non-revoked candidate preserved; global remained disabled at generation 18; no exposed practice survived |
| Role provisioning and authentication | PASS | Post-migration provisioner created/rotated the fourth restricted login without emitting its password; TCP authentication and exact one-role membership verified |
| PostgreSQL control proof | PASS | Current v3 harness; exact four-login boundary, narrow session verifier, raw-session mutation denial, runtime evidence denial, function-path census, lifecycle/key coupling, seven hostile/revoke lifecycles, final global disable |
| Ten-practice proof | PASS | `TEMPLATE_TWIN_RELEASE_CONTROL_SCALE_PRACTICES=10`; 63 per-run release audit events; final global disabled |
| Maximum cohort proof | PASS | `TEMPLATE_TWIN_RELEASE_CONTROL_SCALE_PRACTICES=10000`; 64 per-run release audit events; final global disabled |
| Focused unit/contract census | PASS | 11 files, 79/79 tests |
| Full app TypeScript against exact worktree packages | PASS | `tsc --noEmit`; temporary path mapping avoided the shared dependency cache's stale package source links and was removed afterward |
| Focused application ESLint | PASS | All v3-changed application/test TypeScript paths; zero warnings or errors |
| Prisma validate | PASS | Prisma 7.8.0 schema valid |
| Compose resolved-secret isolation | PASS | Actual `.env` sentinels proved blank raw role secrets in five services, exact APP/WORKER envelope mapping, no sibling envelope, and minimal admin environment/volumes/groups; the temporary `.env` was deleted |
| Caddy validation | PASS WITH BASELINE WARNINGS | Native Caddy validation returned `Valid configuration`; only pre-existing redundant-header and formatting warnings |
| Shell and diff syntax | PASS | Both role scripts pass `sh -n`; `git diff --check` clean; new security provisioner mode `0755` |
| Repository-wide migration drift | **FAIL** | Exact 88-migration datasource-to-schema comparison exits 2: DB-only `template_twin_lineage_migration_progress`; `note_templates.lineageId` nullable plus missing indexes; rollback/control `updatedAt` default drift; legacy constraint/index-name drift. A separate additive schema reconciliation and empty combined-head diff are mandatory before integration acceptance |
| Offline staged-file secret scan | PASS WITH CLASSIFIED PLACEHOLDER | TruffleHog no-verification scan found one unverified PostgreSQL detector at `.env.production.example:36`, the explicit `CHANGE_ME` runtime example DSN; no other finding |
| Verified-only staged-file secret scan | PASS | TruffleHog verified-only scan reported zero verified secrets |
| Independent exact-head review | PENDING AT MANIFEST AUTHORING | A fresh detached reviewer must verify the entire `1edc68c..v3` series; the implementer cannot approve it |
| Human and production gates | HUMAN PENDING | Desktop Word, Clinical Safety, Privacy/Legal, Operations, restore authority, image signing, deployment, and rollout remain outside this technical slice |

The first v3 harness invocation omitted the ordinary test `DATABASE_URL` while
supplying the isolated control URL. The disposable fixture was explicitly
verified, dropped, recreated, migrated from empty, reprovisioned, and rerun with
both test URLs. That corrected run and the later 10,000-practice exact-code run
passed. Expected PostgreSQL `40001` diagnostics are intentionally losing
serialization contenders; the harness asserts the paired safe final state.

The final exact fresh-install rehearsal initially retained the disposable
cluster's post-migration `meddoc_release_security` login. Migration v2 rejected
that out-of-order state as designed. The fixture role was removed, the database
was recreated from empty, all 88 migrations passed in their documented order,
and the fourth login was then provisioned and authenticated before the harness.

Sanitized maximum-cohort result:

```json
{
  "profile": "template-twin-production-release-control-postgres-v3",
  "synthetic": true,
  "databaseGuard": "passed",
  "migrations": "fresh-deploy-required",
  "directSqlEnableRejected": true,
  "nonOwnerRoleBoundaryRejected": true,
  "signedRuntimeReplicaBarrier": true,
  "signedMonitoringReceipts": true,
  "isolatedAuditDispatcher": true,
  "liveRuntimeKeyRevocationWithoutDisableRejected": true,
  "forgedCapabilityRejected": true,
  "capabilityReplayRejected": true,
  "capabilityReceiptsImmutable": true,
  "releaseEvidenceImmutable": true,
  "races": {
    "advanceAdvance": "exactly-one-winner",
    "globalKillAdvance": "disabled",
    "approvalRevokeAdvance": "rejected-and-disabled",
    "operationalRevokeAdvance": "revoked-and-disabled",
    "criticalGuardrailPass": "revoked-and-disabled"
  },
  "criticalGuardrail": "atomic-revoke-and-disable",
  "authorityLifecycle": "atomic-revoke-and-disable",
  "scalePracticeCount": 10000,
  "releaseAuditEventCount": 64,
  "finalGlobalEnabled": false,
  "fixtureLifecycle": "disposable-database-only"
}
```

## Artifact SHA-256

Hashes cover the exact working-tree bytes before the additive v3 commit.

| Artifact | SHA-256 |
| --- | --- |
| `packages/db/prisma/migrations/20260719164000_template_twin_production_control_plane_hardening_v3/migration.sql` | `0cb370f73aefdc132e60a196e74749376318ea300177a9fb1811778ca2e75bf7` |
| `packages/db/scripts/template-twin-release-control-pg-test.ts` | `a321f0d9470e4725e6389b2f4a57da7f4b4c45ea95de03d2f1f6bdc5541e1043` |
| `packages/auth/src/index.ts` | `09cc762ee1ceeb4347aab024debd26b28a89dcf9203957dfa404d9fbd39bc49c` |
| `apps/transcribe-md/src/lib/admin-api-gate.ts` | `c87dc9595b2a52cd0c9db356b9a0d0081d17e4eff9e7f52a64c60c6a230e92fc` |
| `apps/transcribe-md/src/lib/admin-session-freshness.ts` | `f70ac69da8a99c3f00c3563924b4a5702ad908afdaa9369c49b6f16bf3b05042` |
| `apps/transcribe-md/src/lib/template-twin/release-control-access-audit.ts` | `707fa1dc3e4fe68c43249f37ac6fbb6d2d05f0fb6fc2a07e6f4971d353c722a5` |
| `apps/transcribe-md/src/app/api/admin/template-twin/control-health/route.ts` | `097776db32d35104b08cff27e75420352d7f986ac9ce1ac162b4954441fc49e6` |
| `apps/transcribe-md/src/lib/__tests__/admin-api-gate.test.ts` | `dfadd1272a619b9f69f5c36322be4479f30f592e1833312a3ec4428019d5cdc5` |
| `apps/transcribe-md/src/lib/__tests__/admin-session-freshness.test.ts` | `1242323a8cf6fe27b4f22e1813c6f8e12f976942e828f8be6def198c370d48e9` |
| `apps/transcribe-md/src/lib/template-twin/__tests__/release-control-access-audit.test.ts` | `74063f313d6acc701129935eee6596ec480ce33a694f8498c1e4056190df9060` |
| `apps/transcribe-md/src/lib/template-twin/__tests__/release-control-migration-contract.test.ts` | `b1f51c9264455c757d0b7196ac10f2feb04599066112ae1ca6fcd22e30f1d7ce` |
| `infra/postgres/provision-template-twin-release-security.sh` | `a5c89620c3bea4ef566a803feab39114960598457fbca21ae01438c9660e83bc` |
| `infra/postgres/init-template-twin-roles.sh` | `8334092e6781cb33909c7d50d56a46fbd269255ecedf32e079998321b92d8604` |
| `docker-compose.yml` | `6b979fa6aeba63a685f54dd5d1b4ab65e959d4b21783ca607e44b60c588abbd3` |
| `.env.production.example` | `aa57e377c103c6456cfcfc8dc1d4120efefdb09e4dd1bbe8da9f19ead5608abf` |
| `docs/runbooks/template-twin-production-release-control.md` | `8bf7ce48da8c7c1c1d3f189c5332c50427082c1354204ee0f1b23d76813b6926` |
| `Caddyfile` | `de0a6c48dd2a5f033d4f72de75d277965be0bd8537c6eac9770cf6e10f38d1c3` |
| `apps/transcribe-md/src/lib/template-twin/release-control-db.ts` | `e0fcc5134b73724ed1eba4a6365cccabefd17eb333f25852ca691fa6ee0ead4a` |

## Integration conditions

Integrate v1, v2, and the additive v3 commit only as an inseparable ordered
series; never cherry-pick either rejected predecessor alone. The combined head
must include the separately reviewed schema reconciliation, regenerate Prisma,
produce an empty datasource-to-schema diff, rerun the PostgreSQL function-path
catalog assertion after every later migration, rerun the identical-manifest
base/head census and production builds, and obtain a fresh detached exact-head
`ACCEPT`. All human and production gates remain explicit `HUMAN PENDING` until
signed or exercised by the authorized owner.
