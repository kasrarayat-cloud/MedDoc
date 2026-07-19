# Template Twin production control plane — evidence manifest v1

Verdict: **TECHNICAL SLICE PASS; INDEPENDENT EXACT-HEAD REVIEW, INTEGRATED
BUILD/CI, HUMAN APPROVALS, AND PRODUCTION AUTHORITY PENDING.** This evidence
does not authorize a migration, deployment, canary, or physician rollout.

## Identity and safety boundary

- Exact base: `1edc68ca767869c9e92896930a329ed78e532229`
- Branch: `agent/template-twin-control-plane-20260719`
- Isolated worktree:
  `/home/claude/release-programs/meddoc-template-twin-control-plane-20260719`
- Additive commit: recorded in the release-program handoff because a commit
  cannot include its own content-addressed identity
- Release-program preflight: **FIX-AND-GO** before this delegated slice began
- Production mutations: **none**
- Production credentials read or printed: **none**
- PHI, real physician documents, and provider egress: **none**
- Protected `/opt/meddoc-pro` writes: **none**
- Test database: loopback-only disposable PostgreSQL 16 database whose name
  contains the required `test` marker

The implementation is default-off. The additive migration refuses to apply if
the global or any practice Template Twin flag is enabled or if the audited
rollback fence is not open. It seeds no authority, release, approval, rollout,
or capability row.

## Verification census

| Gate                                      | Result              | Evidence                                                                                                                                                                                                                                                                                                                           |
| ----------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Prisma format                             | PASS                | `prisma format`; exact schema formatted                                                                                                                                                                                                                                                                                            |
| Prisma validate                           | PASS                | Prisma 7.7.0 schema valid                                                                                                                                                                                                                                                                                                          |
| Fresh migration chain                     | PASS                | 86/86 migrations applied to a newly recreated disposable PostgreSQL 16 database                                                                                                                                                                                                                                                    |
| Production control-plane PostgreSQL proof | PASS                | Production service functions and independent sessions exercised direct-SQL rejection, forged/replayed capability rejection, immutable receipts/evidence, all five enable/revoke races, the fixed CANARY/10/25/50/100 rail, post-100 revocation, critical-metric atomic revocation, audit-outbox coverage, and final global disable |
| 1,000-practice scale proof                | PASS                | Same fresh-chain harness with `TEMPLATE_TWIN_RELEASE_CONTROL_SCALE_PRACTICES=1000`; complete rail and terminal safety state passed                                                                                                                                                                                                 |
| Focused application tests                 | PASS                | 9 files, 65/65 tests                                                                                                                                                                                                                                                                                                               |
| Focused ESLint                            | PASS                | Changed admin, API, service, transaction, rollout, rollback, and test paths; zero findings                                                                                                                                                                                                                                         |
| Exact-schema changed-path TypeScript      | PASS                | Changed production, test, and PostgreSQL-harness files compiled against an isolated Prisma Client generated from this exact schema                                                                                                                                                                                                 |
| Ambient full-app TypeScript               | INTEGRATION PENDING | The shared dependency cache contains a stale Prisma Client and reports 241 diagnostic lines; the only changed-path matches are three pre-existing rollback audit enum mismatches absent with the exact generated client. Integration must regenerate Prisma before full-app TypeScript/build.                                      |
| Compose interpolation/config              | PASS                | `docker compose config --quiet` with the committed production example env; only the existing blank MinIO KMS warning was emitted                                                                                                                                                                                                   |
| Diff whitespace                           | PASS                | `git diff --check` after correction                                                                                                                                                                                                                                                                                                |
| Offline staged-patch secret scan          | PASS                | TruffleHog with verification disabled and update checks disabled returned zero findings on the zero-context staged patch. Whole-file scanning separately identified only the repository's pre-existing example PostgreSQL placeholder URL in `.env.production.example`.                                                            |
| Independent exact-head review             | PENDING             | The implementer cannot approve this slice                                                                                                                                                                                                                                                                                          |
| Production deployment/rollback rehearsal  | HUMAN/OPS PENDING   | No production database, object, queue, flag, deployment, or rollback state was changed                                                                                                                                                                                                                                             |

Expected `40001` messages in the PostgreSQL output are losing serialization
contenders. The harness requires their corresponding safe final states and
would fail if both contenders committed or if enablement survived a safety
action.

Sanitized scale result:

```json
{
  "profile": "template-twin-production-release-control-postgres-v1",
  "synthetic": true,
  "databaseGuard": "passed",
  "migrations": "fresh-deploy-required",
  "directSqlEnableRejected": true,
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
  "scalePracticeCount": 1000,
  "releaseAuditEventCount": 55,
  "finalGlobalEnabled": false,
  "fixtureLifecycle": "disposable-database-only"
}
```

## Artifact SHA-256

All values are SHA-256 over exact formatted working-tree bytes immediately
before the additive commit.

| Artifact                                                                                                     | SHA-256                                                            |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `packages/db/prisma/migrations/20260719160000_template_twin_production_control_plane_v1/migration.sql`       | `13e8755bdd90d3ae4de9cdb160018c71de3da1832b8fd6be84c0d200ac0d6bf1` |
| `packages/db/prisma/schema.prisma`                                                                           | `dd7a5328bfacae8421e556c54b43aee9946d26340c74119795c1e03684fd9a60` |
| `apps/transcribe-md/src/lib/template-twin/release-control-contracts.ts`                                      | `72b74d22a57f1c1472319ebba902995a520fcbecb2637a5a012dac18f8ad00cc` |
| `apps/transcribe-md/src/lib/template-twin/release-control.ts`                                                | `4c4151c762f1be21597097694ef51a72138d339c0a62abdc04435995818dd87f` |
| `apps/transcribe-md/src/app/api/admin/template-twin/releases/route.ts`                                       | `754aab768cbe3bd8b2b8a6e466049b57feb2dbbd8bf56a8d65b8c66d2ae39290` |
| `apps/transcribe-md/src/app/admin/template-twin-release/page.tsx`                                            | `32b040415280c11147d82077675f47839fbd932f39eb251db86cf4d261a2bc5d` |
| `apps/transcribe-md/src/app/admin/template-twin-release/_components/TemplateTwinReleaseWorkbench.client.tsx` | `69b5be504e20650abafe1206b1e6b2e4ff65503ad85b60e7f913a1f2fc7b5c95` |
| `apps/transcribe-md/src/lib/admin-api-gate.ts`                                                               | `17f5f76101b60fb0622e7bd2f88f103c4968aa0c458a192267d9106410ada29f` |
| `apps/transcribe-md/src/lib/template-twin/rollout.ts`                                                        | `56d9a392cc3303eb779acb55990a34bbb332b1042798efc08b9eee4edae823d8` |
| `apps/transcribe-md/src/lib/template-twin/rollback-control.ts`                                               | `7741466343a891f5c36304cfbe158e55d3ab88c5373bc0f5c115edbbe06f76af` |
| `apps/transcribe-md/src/lib/db/transaction-retry.ts`                                                         | `5590ac0befd04df4c60692cfe5ade6f48a0cb3732c0ed07783e2239a5a9d14f3` |
| `packages/db/scripts/template-twin-release-control-pg-test.ts`                                               | `82cd2bdbb7f1b0222bf11700100700d15c943108d8c4b81a31a0a849b9f0b376` |
| `apps/transcribe-md/src/app/api/admin/template-twin/releases/__tests__/route.test.ts`                        | `1f74890bc0c8e43dad23d0a4f0edda6e216d4ac2e4b5205a968ecefa5883f7f8` |
| `apps/transcribe-md/src/lib/template-twin/__tests__/release-control-contracts.test.ts`                       | `a1827483f39ac66fe386d4f9145e7a2ed0a0b7b854a6ac45367fbe25a07d375b` |
| `apps/transcribe-md/src/lib/template-twin/__tests__/release-control-migration-contract.test.ts`              | `03fbc24de2aaf01916f17f15051911076b3a7f5fba9796d8b606c9a9ea76dd76` |
| `apps/transcribe-md/src/lib/template-twin/__tests__/rollout-concurrency.test.ts`                             | `7d31aa1de969cdc15173cd8985e814d8b68dfbe9db59c13d7df6545e05f63224` |
| `docs/runbooks/template-twin-production-release-control.md`                                                  | `ff91ca4390d7628b9c64a5aa70ff3e3fde2a1e71724d3f5bf7975a873f1e2b6c` |
| `docker-compose.yml`                                                                                         | `22a76ba01d532e2c9d71af2e85afbace5024daef4c8ebf100618892ab1030518` |
| `.env.production.example`                                                                                    | `add5d5024ce61bd563361e46bada710ae3179973da8f3486720ff9efd7f64dff` |
| `package-lock.json`                                                                                          | `8506c0612be06c74f498587677958bc5d1137749c4a11b725fc8925b323d6b97` |

## Remaining acceptance work

Integration must regenerate Prisma, run the complete identical-manifest
base/head census, builds, infrastructure-backed E2E, vulnerability and secret
gates, and obtain a fresh detached exact-head ACCEPT. Operations must provision
the named authority identities, grant the capability issuer only to the runtime
role, connect aggregate monitoring ingestion, and complete data-bearing restore
and rollback rehearsals. Desktop Word, Clinical Safety, Privacy/Legal, and
Operations remain human gates. No rollout may start while any of those items is
pending.
