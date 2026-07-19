# Template Twin GA production rollback plan

Status: **FAIL — plan exists, complete rehearsal has not passed.**

## Safety model

Rollback is layered. The first response is feature revocation; application-image rollback is second. Database objects and immutable clinical/audit evidence are never destructively removed during ordinary rollback.

1. Activate the environment kill switch by ensuring `TEMPLATE_TWIN_KILL_SWITCH` is anything other than the exact string `false` in app and worker processes.
2. Use the approved audited global rollout mutation to disable the persisted singleton and advance its generation; then disable affected practices. Direct SQL is not an approved operating path.
3. Confirm new admission, rendering, signing, and download claims fail closed, while ordinary visits remain healthy.
4. If application rollback is required, deploy the preserved pre-release image IDs below with `--no-build`; do not rely on mutable `latest` tags.
5. Leave additive migrations, lineage/progress rows, audit outbox, storage ledger, source artifacts, certifications, and signed evidence intact.
6. Verify app health, worker heartbeat, audit delivery, queue state, storage access, and ordinary physician journeys using reserved synthetic identities only.

## Preserved pre-release images

- App: `sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90`
- Worker: `sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e`
- Archive: `/home/claude/release-evidence/meddoc-template-twin-ga-20260719/rollback/pre-release-production-images-20260719T0602Z.tar.gz`
- Archive SHA-256: `73bde836cc4983e7803caf2bda605955023e7eb2ad26f045d5b0fb9d87af8b3a`

The archive contains image config blobs for both exact IDs and passed gzip integrity validation. The images contain source/build artifacts but no runtime environment or production credential injection. Keep the archive outside Git and under mode 0600.

## Database compatibility requirement

Application rollback after the lineage contract is not yet approved. The accepted contract removes the insert-compatibility trigger after setting `note_templates.lineageId` NOT NULL, while the preserved pre-release app predates that column. Before release, an additive exact-head fix or independent database-backed proof must show the preserved app can still perform every ordinary note-template write after contract. Until then, production migration is blocked.

## Rehearsal requirements

- Restore the archived image IDs into a disposable Docker image store and verify their IDs.
- Run the exact preserved images against a synthetic clone upgraded through the final migrations and contract phase.
- Exercise ordinary visit and note-template create/edit/delete paths with Template Twin disabled.
- Exercise kill-switch and global/practice generation revocation during concurrent synthetic work.
- Prove audit-outbox and object-ledger state remains durable across image rollback.
- Record elapsed recovery time, commands, exit codes, image IDs, database phase, and smoke results in the evidence manifest.

No production checkpoint may advance while this plan remains `FAIL`.
