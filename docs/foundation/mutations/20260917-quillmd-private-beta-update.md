# Declared private beta update and database role hardening — 2026-09-17

Authorization: owner requests continuation of the new QuillMD implementation, repair and verification, backup restoration, private synthetic testing and stronger controls. No reset, migration from the old application, broad cleanup, external subscription, public release or real-patient use is authorized by this declaration.

## Baseline and exact target

The shared tree is clean main at ddc923e873d20c6ec1c9f93a95878039ff323473. Three active quillmd-fresh services run from /opt/meddoc-pro/rebuild; doctor/admin listeners are loopback9130/9131. The fresh database is quillmd_fresh in the pinned quillmd-fresh-postgres container on loopback55438. The preserved container/mount baseline is docs/rebuild/activation-baseline.json. Marketing200, www200, app/admin503 maintenance, pro410.

The target is the full SHA of the reviewed PR merge containing this declaration and scripts/update-private-beta.py. The updater must prove its bytes equal the target, target equals origin/main, target descends from shared HEAD, and CI+secret-scan succeeded on that exact merge SHA. No branch replacement or force reset is allowed.

## Expected changes

1. Gracefully stop exactly the new doctor/admin/worker units before fast-forwarding shared main. Refuse while an unfinished queued/running provider job remains; no automatic provider retry or financial release.
2. Apply only new-system schema migrations0008/0009/0010: payment request idempotency fields; durable sanitized webhook evidence/state; immutable job financial configuration and webhook envelope guards; separate provider resource IDs; canonical provider-family/resource deduplication indexes (including the new system’s earlier message-ID representation). Existing historical IDs/receipts/pricing snapshots are not rewritten or fabricated.
3. Install the reviewed Python code, static assets and exact fresh-unit sandbox updates. Stamp the private release SHA. Restart the same three services. Private health must report the target SHA and synthetic-only mode.
4. Under a separate invocation through this same committed declaration, apply the tested fresh-cluster role split: nonlogin owner; non-superuser runtime without DDL, replication, role creation or ownership; explicit migrator and read-only backup identities. Revoke PUBLIC database/schema rights. Preserve the bootstrap maintenance connection for recovery, privately protected and hidden from app services.
5. Replace only database user/password entries in fresh .env with generated runtime credentials; keep provider credentials, application secret, rates and all other settings byte-for-byte. Hide operational secrets/backups from app service namespaces. Migrations use the separate protected migrator wrapper.
6. Record private sanitized before/after evidence and final synthetic smoke activity. Authentication recovery, invitation revocation, exact-cost evidence labels and payment lifecycle repairs become available. Stripe/email provider completion remains conditional on actual credentials and verified controlled delivery.

## Required invariants and judged checks

- New user, membership, org/department, patient, template/mapping, encounter, wallet, ledger, reservation, usage, provider receipt, job and audit row contents remain identical across the stopped schema/code update, excluding newly added empty resource-ID columns. No new welcome grant or payment allocation comes from deployment.
- Every existing private storage file retains its hash. The new encrypted backup and isolated restore proof must exist before deployment; restore compares table and referenced-file hashes and invariants without provider/network/worker actions.
- Database-role changes alter ownership/grants only. Runtime DML still works; DDL/TRUNCATE/trigger disabling/escalation and immutable record rewrites fail under runtime. Bootstrap recovery remains available. No shared database roles, marketing rows or other projects change.
- Original preserved six container identities, images, mounts and running states remain unchanged. No shared ingress/certificate/domain change; all five public statuses remain as declared.
- After restart, authenticate synthetic doctor/admin, enforce MFA, run only authorized synthetic workflows, and confirm complete exports and new provider billing provenance. Subsequent intentional test rows/usage are separately recorded; they are not misclassified as deployment deltas.

## Failure handling

If schema/code/role verification fails, keep public maintenance. Preserve original new-system database/files and all financial holds/evidence. Do not auto-revert schema, drop data, retry provider requests or grant payment credit. Diagnose exact partial state before another invocation. A service restart may restore the reviewed runtime after its actual schema compatibility is proven. Restore only into an isolated owned test environment unless a separate concrete live restoration is authorized.
