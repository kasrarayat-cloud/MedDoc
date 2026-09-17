# Declared delta: old QuillMD retirement, 2026-09-17

Owner instruction in the current session authorizes a fresh start with **no migration**, removal of verified old application/admin implementation and dedicated data, and no old-system archive requirement. Marketing, other projects, shared VPS services, useful credentials, domains and certificates must survive. This declaration is written before the act and must be committed with the script and pinned manifest before execution through `scripts/run-ruled-mutation.sh`.

Evidence: `docs/rebuild/ownership-audit.md`; exact container IDs/images/mounts: `docs/rebuild/retirement-manifest.json`.

Expected changes:

1. Stop and remove only the ten containers enumerated in `scripts/retire-old-quillmd.py:REMOVE`, all verified old production/QA application, worker, conversion or dedicated QA data services.
2. Remove only `meddoc-qa_qa_pgdata`, `meddoc-qa_qa_minio` and QA Redis volume `d15ddbc95b32f08874fcc62affd7d1253d116a5c7283a7b53c1dab84caccf4b0`, after verifying no container still uses them.
3. In the old production `meddoc` database, delete only the forty explicitly named old application tables and their enum types. Preserve the database itself and `waitlist_entries`, including its seven marketing lead records. Verify their database-internal digest matches before/after. There is no import into the new application.
4. Delete only production MinIO buckets `transcribe-md-audio` and `transcribe-md-template-artifacts`, including all object versions. Preserve MinIO system configuration, encrypted mounts and useful credentials.
5. Clear production Redis DB **0 only**, after the old web/worker consumers stop. Preserve the service.
6. Disable restart and stop `meddoc-pro-postgres-backup-1` to prevent obsolete application dumps. Preserve its configuration, credentials and existing mixed marketing/application backups, whose narrower ownership remains unresolved.

Must not change:

- Running marketing container/image, Caddy container/image/config mount, Caddy volumes, nginx, certificates, DNS, domain control, staging marketing directory, `packages/shared`, `apps/marketing`, `landing-monolith`.
- Any other project's container/image/running state, network, volume, credential or data.
- Production PostgreSQL/MinIO/Redis service identity and encrypted storage infrastructure.
- Existing sibling worktrees and sessions. Shared main source stays unchanged until the fresh branch passes its PR gate.

Baseline: marketing HTTP 200 on `127.0.0.1:3010`; 41 old production public tables; 7 protected marketing leads; 198 old users; 199 practices; 63 transcribe patients; 74 visits; two dedicated production MinIO buckets with 79 current objects; old Redis DB 0 contained 104 keys at audit. Live key counts may expire naturally. Only the explicitly pinned resource set is in scope; no global prune, VPS-wide deletion, remote backup purge, new subscription or cloud provisioning is allowed.

Verification: the retirement script defaults to read-only checks, refuses changed container identities/mounts/table sets/lead baseline, executes only with the committed mutation gate's environment, rechecks protected identities, verifies unchanged marketing leads, absent old containers and buckets, zero old Redis DB 0 keys, and healthy marketing. Result is written to `docs/rebuild/retirement-result.json` after the act. Public old app/admin ingress may return unavailable until a maintenance route is separately installed; the replacement remains private.

Execution from the fresh worktree after lead review and commit:

```bash
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260917-quillmd-fresh-retirement.md \
  -- python3 scripts/retire-old-quillmd.py --execute
```
