# Template Twin rollback fence — fill-lineage immutability v4

Verdict: **TECHNICAL IMPLEMENTATION PASS; INDEPENDENT EXACT-HEAD REVIEW
PENDING.** This additive correction does not authorize a production migration,
deployment, or rollout.

## Exact identity and boundary

- Integrated parent: `1edc68c` (`fix(template-twin): enforce candidate review proof`)
- Additive implementation: `01427c2` (`fix(template-twin): freeze fill lineage identity`)
- Branch: `release/template-twin-ga-20260719`
- Migration:
  `20260719153000_template_twin_fill_identity_immutability_v4`
- Production mutations: **none**
- PHI, real physician documents, and provider egress: **none**
- Protected `/opt/meddoc-pro` writes: **none**

## Finding and correction

The v3 rollback inventory counts a nonterminal Template Twin visit as pinned
only when no fill manifest is attached. Before v4, an unsigned terminal fill
could be reassigned from its original Twin visit by changing `visitId` without
changing fill status. During a prepared rollback this exposed new pinned work
after the drain snapshot and bypassed the v3 status-only fill update trigger.

V4 makes the fill manifest's practice, visit, compiled version, note-template,
and note-template-version identity immutable after insert. Mutable resolution,
review, render, and signing state continues to advance normally. The trigger is
named with the `aaa_` prefix so it fails on the immutable lineage boundary
before broader consistency triggers.

## Verification census

| Gate | Result | Evidence |
| --- | --- | --- |
| Migration shape | PASS | Transactional migration; 2-second lock timeout; 30-second statement timeout; no row rewrite or backfill |
| Focused unit/static contracts | PASS | 2 files, 20/20 tests |
| Prisma format / validate / generate | PASS | Combined 86-migration schema and Prisma Client |
| Application TypeScript | PASS | `tsc --noEmit` from `apps/transcribe-md` |
| Focused ESLint | PASS | Migration contract and PostgreSQL proof harness; zero findings |
| Fresh installation | PASS | Clean loopback-only PostgreSQL 16 database applied 86/86 migrations |
| Prepared-fence PostgreSQL proof | PASS | Exact unsigned `FAILED` fill reassignment rejected with `Template Twin fill identity is immutable`; complete v3 rollback/audit/race harness remained green |
| Data-bearing v3 → v4 upgrade | PASS | 85-migration database reproduced the reassignment, was returned to its original lineage, upgraded to 86, preserved the prepared fence and row, then rejected the same reassignment |
| Ordinary behavior | PASS | Ordinary structured template remained active and unchanged in the full PostgreSQL proof |
| Independent exact-head review | PENDING | Implementer cannot approve this additive correction |

Sanitized fresh-database proof:

```json
{
  "status": "PASS",
  "migrations": 86,
  "fenceGeneration": "5",
  "globalGeneration": "12",
  "auditEvents": 5,
  "ordinaryTemplatePreserved": true,
  "repeatedRevokeIdempotent": true,
  "operationHistoryImmutable": true,
  "operationFenceCouplingEnforced": true,
  "completeOperationAuditHistoryEnforced": true,
  "rolloutSingletonImmutable": true,
  "rollbackTruncateBlocked": true,
  "activeVersionFenceEnforced": true,
  "fenceMetadataImmutable": true,
  "auditDeliveryComplete": true,
  "exactAuditReceiptsImmutable": true,
  "unsignedFillIdentityImmutable": true,
  "concurrentPinnedVisitBlocked": true,
  "finalClaimBlocked": true,
  "directEnableBlocked": true,
  "productionMutation": false
}
```

## Artifact SHA-256

| Artifact | SHA-256 |
| --- | --- |
| `packages/db/prisma/migrations/20260719153000_template_twin_fill_identity_immutability_v4/migration.sql` | `d219429f41628bb4c6f6fc7478897ba68d4e15a7c7a61e4a7c7f6f5f7de736bb` |
| `apps/transcribe-md/src/lib/template-twin/__tests__/rollback-control-migration.test.ts` | `cc05a8986a4cd13018bd56c22e5b6564d3a87eecdbbb0a228ba6f2e46dcd9b18` |
| `packages/db/scripts/template-twin-rollback-fence-pg-test.ts` | `dfe95169dd4a04df2a4796afc64b19748de8a1674814ddcf6ff2ddcc9da2064d` |

The earlier v1-v3 manifests remain historical evidence and are not rewritten.
The complete production rollback plan remains **FAIL** until a fresh independent
review accepts the integrated exact head and Operations proves a production-like
backup restore, queue/provider drain, bridge-image swap, roll-forward, monitoring,
and recovery-time rehearsal.
