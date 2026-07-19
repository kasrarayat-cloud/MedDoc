# Template Twin GA production rollback plan

Status: **FAIL — plan exists, complete rehearsal has not passed.**

## Safety model

Rollback is layered. The first response is feature revocation; application-image rollback is second. Database objects and immutable clinical/audit evidence are never destructively removed during ordinary rollback.

1. Engage the separately reviewed, audited maintenance fence that blocks new Template Twin admissions without disabling ordinary visits, audit-outbox delivery, or object-ledger reconciliation. This control is not implemented or rehearsed yet, so operational rollback remains blocked.
2. While the current rollout tokens remain valid, deactivate every active Template Twin version through its reviewed physician lifecycle. The current deactivation action cannot run after kill-switch or rollout revocation.
3. Activate the environment kill switch by ensuring `TEMPLATE_TWIN_KILL_SWITCH` is anything other than the exact string `false` in app and worker processes.
4. Use the approved audited rollout mutations to disable affected practices and then the persisted global singleton, advancing each generation. Direct SQL is not an approved operating path.
5. Stop new Template Twin visit and synthetic-test producers and drain their execution queues. Keep audit-outbox delivery and object-ledger reconciliation running. Classify every provider execution lease before changing workers; an ambiguous or unknown outcome must never be replayed.
6. Confirm zero active Template Twin versions, zero enabled practices, zero nonterminal Twin visits or synthetic runs, zero unsettled provider executions, and fail-closed admission/rendering/signing/download, while ordinary visits remain healthy.
7. Before any migration has run, the preserved pre-release image IDs may be used only with the exact pre-migration database and pre-migration queues. After any Template Twin migration, deployment tooling must reject those images.
8. After migration, application rollback may use only the accepted immutable `rollback-compat-v2` bridge built from the final schema and protocol. Its digest is not yet available, so this path remains blocked.
9. Leave migrations, lineage/progress rows, audit outbox, storage ledger, source artifacts, certifications, and signed evidence intact.
10. Verify app health, worker heartbeat, audit delivery, queue state, storage access, and ordinary physician journeys using reserved synthetic identities only. Preserve before/after DB, object, and audit hashes.

## Preserved pre-release images — pre-migration use only

- App: `sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90`
- Worker: `sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e`
- Archive: `/home/claude/release-evidence/meddoc-template-twin-ga-20260719/rollback/pre-release-production-images-20260719T0602Z.tar.gz`
- Archive SHA-256: `73bde836cc4983e7803caf2bda605955023e7eb2ad26f045d5b0fb9d87af8b3a`

The archive contains image config blobs for both exact IDs and passed gzip integrity validation. The images contain source/build artifacts but no runtime environment or production credential injection. Keep the archive outside Git and under mode 0600.

**Do not deploy either preserved image after a Template Twin migration.** Independent rehearsal proved that the old clients and workers are incompatible with the contracted schema, appended audit enums, Template Twin selection/signing contracts, and provider execution ledger.

## Database compatibility requirement

Application rollback after migration is not approved. The independent rehearsal reproduced failures and unsafe behavior in generic template writes, audit reads, ordinary automation/signing, Template Twin selection/signing, queue compatibility, and provider no-replay handling. The old-image hypothesis is rejected rather than merely unproven.

The required post-migration target is an immutable `rollback-compat-v2` bridge that uses the final Prisma schema and enums, writes lineage explicitly, excludes Template Twin from generic lifecycle/resolution, retains Template Twin sign/export rejection and rollout gates, and uses the v2 provider-execution and maintenance-queue protocols while keeping Template Twin UI and admission disabled.

## Rehearsal requirements

- Restore the archived image IDs into a disposable Docker image store and verify their IDs for the pre-migration recovery path only.
- Confirm the deployment guard rejects the preserved images against every post-migration schema/protocol epoch.
- Build the bridge from the final exact SHA and record its immutable app/worker digests.
- Run old→migrated→contracted synthetic data through the bridge and exercise ordinary visit and generic note-template create/edit/delete/version paths with Template Twin disabled.
- Read every appended audit action and prove Template Twin rows are excluded from generic discovery, mutation, activation, and resolution.
- Prove Template Twin signing/export remains rejected without the complete verification-contract-v2 evidence.
- Exercise kill-switch and global/practice generation revocation during concurrent synthetic work.
- Prove the audited maintenance fence, valid-token deactivation, kill-switch, practice/global revocation, and zero-active-version sequence without a direct database mutation.
- Prove provider calls are not replayed for every execution-ledger state; classify or drain visit and synthetic execution queues before the worker swap while audit/object maintenance remains live.
- Prove audit-outbox and object-ledger state remains durable across bridge rollback and roll-forward.
- Record elapsed recovery time, commands, exit codes, image IDs, database phase, and smoke results in the evidence manifest.

No production checkpoint may advance while this plan remains `FAIL`.
