# Template Twin production control plane — hardening evidence manifest v2

Verdict: **TECHNICAL SLICE PASS WITH REPOSITORY-WIDE MIGRATION-DRIFT DEBT;
INDEPENDENT EXACT-HEAD REVIEW AND INTEGRATION REMAIN REQUIRED.** This manifest
does not authorize production migration, deployment, canary, or physician
rollout. It supersedes the technical acceptance claims in v1; v1 remains an
immutable record of the rejected first implementation.

## Identity and safety boundary

- Exact base before the control-plane series:
  `1edc68ca767869c9e92896930a329ed78e532229`
- Rejected first implementation: `734951e6aa95a994c3483caa3307ef5eb598e2c0`
- Additive hardening commit: recorded in the release-program handoff because a
  commit cannot contain its own content-addressed identity
- Branch: `agent/template-twin-control-plane-20260719`
- Isolated worktree:
  `/home/claude/release-programs/meddoc-template-twin-control-plane-20260719`
- Production mutations, provider egress, real documents, and PHI: **none**
- Production credentials read or printed: **none**
- Protected `/opt/meddoc-pro` repository source changes: **none**. The clean
  worktree reused its shared dependency cache; Prisma generation updated only
  generated dependency-cache artifacts.
- Test target: loopback-only disposable PostgreSQL 16 databases with explicit
  `test` names and synthetic operational identities

The v2 migration is additive and refuses a used, enabled, or rollback-fenced
control plane. It seeds no release, authority, approval, capability, cohort,
metric, key, or enablement row.

## Verification census

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh migration chain | PASS | Official `prisma migrate deploy`; 87/87 migrations on independent fresh v26 and v27 databases |
| Expanded PostgreSQL proof | PASS | v26; exact login/group role boundaries, forged/tampered receipts and manifests, signed runtime/metric evidence, revoked keys, all five race classes, lifecycle revocation, isolated dispatcher, exact audit pairing, final global disable |
| Maximum cohort proof | PASS | v27; `TEMPLATE_TWIN_RELEASE_CONTROL_SCALE_PRACTICES=10000`; seven complete hostile/revoke lifecycles, 64 release audit events, final global disabled |
| Focused unit/contract census | PASS | 8 files, 55/55 tests |
| Full app TypeScript against exact worktree packages | PASS | `tsc --noEmit`; temporary path mapping avoided the shared cache's stale `/opt/meddoc-pro/packages/ai` symlink |
| Focused ESLint | PASS | All changed application/worker/test TypeScript paths; zero warnings or errors |
| Prisma format/validate/generate | PASS | Prisma 7.8.0 schema valid and client generated |
| Bootstrap/Compose/Caddy syntax | PASS | `sh -n`, structural Compose interpolation, and Caddy native validation |
| New control-plane schema drift | PASS | No v1/v2 control-plane object appeared in datasource-to-schema drift output |
| Repository-wide migration drift | INTEGRATION DEBT | Fresh database reports older table/nullability/default and legacy constraint-name drift, including `note_templates.lineageId` and `template_twin_lineage_migration_progress`; central release integration must compare and resolve before GA |
| Diff whitespace | PASS | `git diff --check` |
| Offline staged-patch secret scan | PASS WITH CLASSIFIED PLACEHOLDERS | TruffleHog verification-disabled scan found only the explicit `CHANGE_ME...` PostgreSQL example URLs (one added, one removed context line); no credential-like non-placeholder material |
| Verified-only staged-patch secret scan | PASS | TruffleHog verified-only scan: zero verified secrets |
| Independent exact-head review | PENDING AT MANIFEST AUTHORING | A fresh detached reviewer must verify the final additive commit; the implementer cannot approve it |
| Human/production gates | PENDING | Desktop Word, Clinical Safety, Privacy/Legal, Operations, restore authority, image signing, deployment, and rollout remain outside this technical slice |

Expected PostgreSQL `40001` diagnostics are deliberately losing serialization
contenders. The harness asserts the paired safe final state and fails if both
contenders commit or exposure survives a safety action.

Sanitized maximum-cohort result:

```json
{
  "profile": "template-twin-production-release-control-postgres-v2",
  "synthetic": true,
  "databaseGuard": "passed",
  "migrations": "fresh-deploy-required",
  "directSqlEnableRejected": true,
  "nonOwnerRoleBoundaryRejected": true,
  "signedRuntimeReplicaBarrier": true,
  "signedMonitoringReceipts": true,
  "isolatedAuditDispatcher": true,
  "revokedRuntimeKeyFinalClaimRejected": true,
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

Hashes cover the exact formatted working-tree bytes before the additive v2
commit.

| Artifact | SHA-256 |
| --- | --- |
| `packages/db/prisma/migrations/20260719163000_template_twin_production_control_plane_hardening_v2/migration.sql` | `8bc783e6c77cf3fa8e118f6af9d1ed3b74575a48b3769b9fa61930311ebf3f6c` |
| `packages/db/prisma/schema.prisma` | `12a951aadf3c9c0b0d247d803c42f78dc82f6541798f884eccc99aea8053035b` |
| `packages/db/scripts/template-twin-release-control-pg-test.ts` | `4570179b7a9203e7698428d31d32a276d0c261cac36be8a8fdc633dbeb6e4c33` |
| `apps/transcribe-md/src/lib/template-twin/release-control.ts` | `66cac45d3a1d3c5304b27b4200f2ebdea3e8ebae81aaca167b7a9054003980f0` |
| `apps/transcribe-md/src/lib/template-twin/release-control-contracts.ts` | `405f960bee76e89f5b86f08425a2b5fdde66f881278c382400b31b4d9ab587e6` |
| `apps/transcribe-md/src/lib/template-twin/release-control-db.ts` | `e0fcc5134b73724ed1eba4a6365cccabefd17eb333f25852ca691fa6ee0ead4a` |
| `apps/transcribe-md/src/lib/template-twin/runtime-attestation.ts` | `9af9e8da6bea4390f20169b3cb0bbebe89349c0a751198db366e7761ac53f2a2` |
| `apps/transcribe-md/src/lib/template-twin/rollout.ts` | `6c75ae65eb5d929385d8ffebe2b21a97e4703889d26047329c4eb4bfd8800e1b` |
| `apps/transcribe-md/src/lib/runtime-protocol.ts` | `eae53d06f4b97b1f7a8c38d0ab1c062e4631c3cf1a6430ffb435cf4dcaa8df64` |
| `apps/transcribe-md/src/app/api/admin/template-twin/releases/route.ts` | `ce43a1ce5f7f4ce68333d48fbcc8b45bb0ef17d0f090f743e61e7999fd50434a` |
| `apps/transcribe-md/src/app/api/admin/template-twin/release-metrics/route.ts` | `388e19f31e3afb9312bd3cd9e3fc6c103b4ea6dab3cb310b57ddbc3428a8994d` |
| `apps/transcribe-md/src/app/api/health/route.ts` | `592c014a9211f09be302b980af2da40a50e27e44bceadf4bca55004078f06fef` |
| `apps/transcribe-md/src/audit-dispatcher.ts` | `0725be02afe347b5be6b783f6a0f3e99563b41dcfa358a0201e762dfc8e81745` |
| `apps/transcribe-md/src/lib/template-twin/__tests__/release-control-migration-contract.test.ts` | `754c7d30a2be4cada71af40f21f3945ef638f1522d3f58b617bb95e059511fa5` |
| `infra/postgres/init-template-twin-roles.sh` | `8334092e6781cb33909c7d50d56a46fbd269255ecedf32e079998321b92d8604` |
| `docker-compose.yml` | `10898a73a811f87ed8ee033af9a5749ecd3753370ac52bade8c35cfaa612e7cd` |
| `Caddyfile` | `de0a6c48dd2a5f033d4f72de75d277965be0bd8537c6eac9770cf6e10f38d1c3` |
| `.env.production.example` | `6d6917a8876238efd9c738d7f3862780eb5214f51b996e29e6aba4874f05f273` |
| `docs/runbooks/template-twin-production-release-control.md` | `295d8c792e9963a4cfcd231aa6a6046664263acb486793cd90b94f9e509e90f7` |

## Integration conditions

Integrate the rejected v1 commit and this additive v2 commit as an inseparable
series; never cherry-pick v1 alone. Regenerate Prisma in the integration
workspace, resolve the recorded repository-wide migration drift, rerun the
identical-manifest base/head census and production builds, and obtain a fresh
detached exact-head ACCEPT. All human and production gates remain explicit
`HUMAN PENDING` until signed or exercised by the authorized owner.
