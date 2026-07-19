# Template Twin audited rollback fence — evidence manifest v1

Verdict: **TECHNICAL IMPLEMENTATION PASS; INDEPENDENT REVIEW AND PRODUCTION
ROLLBACK REHEARSAL PENDING.** This slice does not make the GA rollback plan or
production release PASS.

## Identity and safety boundary

- Exact base: `90d943e08ddd427e9a1c17022c8fb4fe971adec6`
- Branch: `agent/template-twin-rollback-fence-20260719`
- Isolated worktree:
  `/home/claude/release-programs/meddoc-template-twin-rollback-fence-20260719`
- Preflight: **FIX-AND-GO**,
  `docs/preflight-reports/preflight-20260719T083637Z.md`
- Production mutations: **none**
- PHI/provider use: **none**
- Protected `/opt/meddoc-pro` writes: **none**
- Disposable PostgreSQL containers: `tt-rollback-fence-pg-20260719`,
  `tt-rollback-fence-pg-hardening-20260719`,
  `tt-rollback-fence-pg-final-20260719`, and
  `tt-rollback-fence-pg-exact-20260719`; all removed after verification

The first discarded fresh-database attempt reproduced an existing repository
installation prerequisite: migration `20260505010210` expects the deployment
role `meddoc`. That disposable container was destroyed. A clean replacement
was initialized with the expected role before migration; all 81 migrations
then applied successfully. No failed migration was disguised or edited.

## Verification census

| Gate                                  | Result            | Evidence                                                                                                                                                                                                                                                             |
| ------------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Prisma format                         | PASS              | `prisma format --schema packages/db/prisma/schema.prisma`                                                                                                                                                                                                            |
| Prisma validate                       | PASS              | Schema valid                                                                                                                                                                                                                                                         |
| Prisma generate                       | PASS              | Prisma Client generated                                                                                                                                                                                                                                              |
| Affected unit/static/admin-gate tests | PASS              | 7 files, 98/98 tests                                                                                                                                                                                                                                                 |
| Application TypeScript                | PASS              | `tsc -p apps/transcribe-md/tsconfig.json --noEmit`                                                                                                                                                                                                                   |
| Changed application ESLint            | PASS              | Rollback service, route, rollout gate, and focused tests; zero findings                                                                                                                                                                                              |
| Fresh migration chain                 | PASS              | Clean loopback-only PostgreSQL; 81/81 migrations applied                                                                                                                                                                                                             |
| Migration idempotency                 | PASS              | Second `prisma migrate deploy`: no pending migrations                                                                                                                                                                                                                |
| PostgreSQL rollback-fence proof       | PASS              | `rollback-fence:pg-test`; five transactional outbox events delivered exactly once, final claim blocked, direct enable and fence-metadata tampering blocked, immutable operation history enforced, ordinary structured template unchanged, repeated revoke idempotent |
| Production rollback/restore           | HUMAN/OPS PENDING | This disposable proof is not production backup restore, image swap, queue drain, monitoring, or recovery-time evidence                                                                                                                                               |
| Independent exact-head review         | PENDING           | Implementer cannot approve this slice                                                                                                                                                                                                                                |

The six `P0001` messages emitted during the PostgreSQL proof are expected
assertions from the database triggers. The harness requires the exact global
and practice fence messages plus fence-metadata, immutable-identity,
terminal-transition, and no-delete history messages; a generic database failure
cannot satisfy the gate.

Sanitized proof result:

```json
{
  "status": "PASS",
  "migrations": 81,
  "fenceGeneration": "5",
  "globalGeneration": "12",
  "auditEvents": 5,
  "ordinaryTemplatePreserved": true,
  "repeatedRevokeIdempotent": true,
  "operationHistoryImmutable": true,
  "fenceMetadataImmutable": true,
  "auditDeliveryComplete": true,
  "finalClaimBlocked": true,
  "directEnableBlocked": true,
  "productionMutation": false
}
```

## Artifact SHA-256

| Artifact                                                                                     | SHA-256                                                            |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `packages/db/prisma/migrations/20260719130000_template_twin_rollback_fence_v1/migration.sql` | `01a521782b8cd244a4f637d07bdf8c8aa57f6a52ee85fb037ece23af91f7aad9` |
| `apps/transcribe-md/src/lib/template-twin/rollback-control.ts`                               | `4e4e851f1e2ca1c88e5ed2126568122e3cba5a2eff0a62b62c5cf40bf2ff562e` |
| `apps/transcribe-md/src/app/api/admin/template-twin/rollback/route.ts`                       | `0d8e71eb89c2481e922dccd8c1dd940bd5eb622c588c34a2812d243f83fb8cfc` |
| `packages/db/scripts/template-twin-rollback-fence-pg-test.ts`                                | `5ac62bfba25a65cd7e0693d177518948259e766bb609b81c13189387be1d812d` |
| `docs/runbooks/template-twin-audited-rollback-control.md`                                    | `825a50025c24e79a1bbd020d2d4ec41fad27efea2eba6000137d7d18bba090f6` |
| `docs/preflight-reports/preflight-20260719T083637Z.md`                                       | `c4943f42811bf078873166ddb15d60ee4eec5798bdf3ed751677414c4e9c6026` |

## Remaining acceptance work

An independent reviewer must verify the exact integrated head in a fresh
detached workspace. Operations must then use a restored, data-bearing
disposable environment to rehearse concurrent admission fencing, queue drain,
provider outcome classification, audit delivery, object reconciliation,
immutable bridge-image swap, ordinary physician continuity, cancel-before-
revoke recovery, terminal revoke, roll-forward, and recovery time. Production
use remains forbidden until those gates and the broader human approvals pass.
