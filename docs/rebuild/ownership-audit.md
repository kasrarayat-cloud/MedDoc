# Fresh-start ownership audit — 2026-09-17

Read-only evidence collected before retirement. No patient content or secret values were printed. The lead ran preflight `20260917T080133Z` with FIX-AND-GO before delegating this audit. This document is an ownership finding, not a claim that retirement has happened.

## Boundaries and source ownership

- `pwd` and `realpath /opt/meddoc-pro` both resolve to `/opt/meddoc-pro`. All audited application/package directories are real directories, not symlinks. The shared deployment tree stays on main; implementation removal is initially in `/opt/meddoc-pro/.worktrees/quillmd-fresh` pending the repository's PR gate.
- `apps/transcribe-md` is the old doctor application and admin implementation; both `app.quillmd.com` and `admin.quillmd.com` reverse proxy to its service. `apps/meddoc-pro` is its earlier, stopped CRM application.
- `packages/ai`, `packages/auth`, `packages/db`, and `packages/types` are dependencies of those old applications. Marketing has no runtime dependency on any of them. They can be removed from the new worktree together with the old applications.
- Preserve `apps/marketing`, `packages/shared`, and `landing-monolith`. Marketing depends on `@meddoc/shared`. Its Dockerfile currently copies the obsolete workspace manifests: those COPY instructions and the workspace lockfile must be repaired when removing the old applications. Running marketing is independently bundled and will not be changed by worktree edits.
- `services/form-detect` and the Gotenberg font build are old application sidecars, attached only to the old application's converter network. Their live containers can be retired after consumers stop. Existing service source is not itself patient data.
- Root `.env` contains configured OpenAI, Anthropic, Deepgram, Resend, auth, database, and MinIO credential keys. Secret values were neither logged nor copied to documentation. Preserve this file and `/etc/meddoc`. A configured Stripe secret was not found in the inspected root environment.

## Exact live resources

| Resource | Evidence | Decision |
| --- | --- | --- |
| `meddoc-pro-transcribe-md-1` | compose project `meddoc-pro`, service `transcribe-md`, working directory `/opt/meddoc-pro`; localhost 3011 | Retire old application |
| `meddoc-pro-transcribe-md-worker-1` | same project/directory; old app DB, Redis, MinIO clients | Retire old jobs |
| `meddoc-pro-meddoc-pro-1` | old CRM; exited six weeks ago; same database | Remove stopped old container |
| `meddoc-pro-form-detect-1`, `meddoc-pro-gotenberg-1` | only old converter network consumers | Retire old sidecars |
| `meddoc-qa-transcribe-md-1`, `meddoc-qa-transcribe-md-worker-1` | project `meddoc-qa`, old QA app; localhost 9020 | Retire old QA application |
| `meddoc-qa-postgres-1`, `meddoc-qa-minio-1`, `meddoc-qa-redis-1` | only old QA services on `meddoc-qa_default` | Retire old QA dedicated data services |
| `meddoc-qa_qa_pgdata`, `meddoc-qa_qa_minio` | labels identify QA project; mounted only by the above | Delete after their containers stop |
| QA Redis volume `d15ddbc95b32f08874fcc62affd7d1253d116a5c7283a7b53c1dab84caccf4b0` | mounted at `/data` only by `meddoc-qa-redis-1` | Delete after the container stops and mount is rechecked |
| `meddoc-pro-postgres-1` | database `meddoc`, owner `meddoc`, 41 public tables | Preserve service and database shell because of marketing leads; remove explicit old application tables |
| `meddoc-pro-minio-1` | only old application buckets found | Remove only the two verified application buckets; preserve service configuration and useful credentials |
| `meddoc-pro-redis-1` | DB 0 had 104 keys; every non-audit client was old web/worker IP | Clear dedicated DB 0 after old consumers stop; preserve server configuration |
| `meddoc-pro-postgres-backup-1` | dumps database `meddoc`; 20 files in `/backups` | Stop obsolete scheduled dumps before erasure; retain existing mixed marketing/app backups pending narrower adjudication |

Production database metadata: `meddoc` approximately 33 MB; only other non-template database is `postgres`. The sole application connection at audit time was `172.19.0.9`, the old app container. Public table ownership is uniformly `meddoc`. Counts: 198 users, 199 practices, 63 transcribe patients, 74 transcribe visits, zero earlier CRM patients/documents, **7 waitlist entries**. Counts are metadata, not patient records.

`waitlist_entries` is a marketing dependency: marketing `/signup` redirects to the old app's `/waitlist`; all marketing signup CTAs target it. Its seven lead records must remain untouched under the instruction to preserve marketing. It has no outbound foreign keys. Dropping the entire `meddoc` database would destroy this protected data. The new application must not connect to or import this database.

Production MinIO S3 listing found exactly two buckets: `transcribe-md-audio` (4 current objects, 5,728,627 bytes) and `transcribe-md-template-artifacts` (75 current objects, 3,028,174 bytes). No object names/content were printed. The QA data root has those same two bucket names. MinIO system configuration is separate under `.minio.sys` and must remain.

## Preserved shared infrastructure

- `meddoc-pro-marketing-1` is healthy, listening only on localhost 3010. It has no DB, Redis, MinIO or provider environment variables.
- `meddoc-pro-caddy-1`, `meddoc-pro_caddy_config`, `meddoc-pro_caddy_data`, `/opt/meddoc-pro/Caddyfile`, and `meddoc-pro_default` are shared with marketing. Caddy binds **the shared-tree Caddyfile**, not a worktree path.
- System nginx terminates public TLS on 80/443 and proxies QuillMD to localhost 8443. Preserve `/etc/nginx/sites-enabled/quillmd`, `/etc/nginx/sites-available/quillmd`, the staging site, `/etc/letsencrypt`, domain configuration, and `/var/www/quillmd-staging`.
- Production database volume `meddoc-pro_pgdata_encrypted` binds `/mnt/pgdata-encrypted/pgdata`; production MinIO volume `meddoc-pro_minio_data` binds `/mnt/miniodata-encrypted/data`. Both mount on separate encrypted mapper devices. **Removing a Docker volume would not erase the bind-backed data.** Preserve the encrypted services, mounts and keys. Scoped logical data removal is the appropriate boundary here.
- Preserve `pgdata-encrypted.service`, `miniodata-encrypted.service`, `quillmd-postreboot-proof.service`, shared Docker/nginx/cron/SSH, and all other projects.
- Other positively identified projects include VoiceAssist, LeatherERP, Astra Foundation, OpenClaw and DealHunter. `astra-foundation-dev-pg-v1` explicitly belongs to `/home/voiceassistmain/VoiceAssistMain`; its name does not make it part of this rebuild.

## Ambiguous or mixed resources left alone

- `meddoc-pro_pgbackups` contains whole-database backups that may include protected marketing leads. Offsite backups were not inspected; no remote deletion is authorized by this audit's evidence. Preserve the backup credentials.
- `meddoc-pro_pgdata` is an unused pre-encryption volume, but its contents/ownership boundaries were not verified. Likewise unused `meddoc-b017-segment-live1_qa_pgdata`, `meddoc-durable-admission-qa_qa_minio`, and anonymous volumes are outside the exact current-service deletion list.
- Containers `pg-r7-1083`, `wa-1105-pg`, and `lens-w8-a5-concurrency-pg` have no compose ownership labels. Leave them untouched until their owner/active work is identified.
- Existing sibling worktrees and a live shell/sleep pair under `/opt/meddoc-pro/.wt-fl` may belong to another session. Do not terminate them or delete their trees.
- Historical `main` source remains until a reviewed PR lands. This is repository gate preservation, not an old-data migration or an imposed archive. The replacement uses a fresh isolated datastore.

## Verification required after retirement

Re-read container membership, confirm named old containers and dedicated QA volumes are absent, confirm `meddoc.public` contains only `waitlist_entries` with the same seven rows, confirm the two production application buckets are absent, confirm production Redis DB 0 is empty, and verify marketing HTTP health plus preserved Caddy image/mount identity. Public app/admin will need a deliberate maintenance response until the private replacement is promoted; do not point public ingress at the development server.
