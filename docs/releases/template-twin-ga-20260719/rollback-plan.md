# Template Twin GA production rollback plan

Status: **FAIL — plan exists, complete rehearsal has not passed.**

## Safety model

Rollback is layered: revoke exposure first, then change application images only if
necessary. Never downmigrate, delete immutable clinical/audit evidence, replay an
ambiguous provider outcome, or improvise direct enabling SQL.

## Supported image boundary

Before any Template Twin migration, the preserved pre-release images may be used
only with their exact pre-migration database and queues:

- App: `sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90`
- Worker: `sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e`
- Archive SHA-256: `73bde836cc4983e7803caf2bda605955023e7eb2ad26f045d5b0fb9d87af8b3a`

After any Template Twin migration, those images are forbidden. The only allowed
application rollback target is one independently accepted, immutable,
final-schema-compatible app/worker image pair from one exact SHA. It must
recreate all six long-lived same-artifact services together:

- app image: `transcribe-md`, `template-twin-admin-app`,
  `template-twin-admin-control`;
- worker image: `transcribe-md-worker`,
  `template-twin-audit-dispatcher`, `auth-email-dispatcher`.

The one-shot `db-migrate` service is never part of an application rollback.
Technical head `e7b3864dc6d61d7d36755f59f87909bb7394740d` was rejected for an
incomplete production runtime-identity census. The additive candidate closes
that census across all six runtimes, requires exact database and verifier
profiles, and forces authentication bypasses off during the swap. A read-only
pre-commit audit returned ACCEPT with no P0/P1/P2, but the candidate still
requires an additive SHA and fresh detached exact-head ACCEPT. No accepted
image digests exist.

## Ordered rollback procedure

1. Engage the fresh-`SUPER_ADMIN`, same-origin audited maintenance fence from
   `docs/runbooks/template-twin-audited-rollback-control.md`. Stop if that
   control is unavailable.
2. While current rollout authority is still valid, deactivate every active Twin
   version through the reviewed lifecycle. Then activate
   `TEMPLATE_TWIN_KILL_SWITCH=true` for all six runtime configurations and use
   the audited revoke transaction to disable global and practice rollout.
3. Stop new Twin producers. Drain and classify every Twin visit, synthetic run,
   maintenance job, and provider execution. `IN_FLIGHT` or `UNKNOWN_OUTCOME`
   provider work must be reconciled, never guessed or replayed. Keep immutable
   audit/object maintenance available.
4. Confirm zero active Twin versions, enabled practices, nonterminal Twin
   visits/runs, and unsettled provider executions. Confirm ordinary visits still
   have a valid current provider-ownership and audit path.
5. Verify the target images by immutable ID/digest, exact OCI revision, component
   label, and protocol epoch. Use an operator-owned state directory outside the
   release checkout. Run the checked guard first without mutation:

   ```bash
   scripts/template-twin-runtime-swap.sh \
     --app-image '<immutable-app-ref>' \
     --worker-image '<immutable-worker-ref>' \
     --release-sha '<accepted-40-hex-sha>' \
     --state-dir '<operator-owned-absolute-state-directory>'
   ```

6. Preserve the reported preflight evidence. Repeat the exact command with
   `--execute`. The guard must create a content-addressed mode-`0444` overlay,
   stop all six services before one force-recreate operation, exclude the
   migrator, and verify exact image, container, service, role, database profile,
   verifier profile, authentication-safe flags, epoch, bridge mode, kill switch,
   and health before success.
7. Record the overlay path and SHA-256. Every later Compose operation on these
   services must use the same immutable base file and overlay. Do not edit or
   reconstruct the overlay.
8. Recheck the revoked/drained database and queues, audit and authentication
   email dispatcher database-backed heartbeats, object reconciliation, storage,
   and ordinary physician journeys using reserved synthetic identities only.
9. Leave migrations, lineage/progress rows, source artifacts, certifications,
   signing evidence, audit outbox, provider ledger, and storage ledger intact.

## Authentication and MFA rollback constraints

- After any `qmfa:v1` ciphertext is committed, never roll back to an image that
  understands only plaintext Base32. The rollback image must use the same
  separately escrowed keyring and strict/approved bounded legacy-read semantics.
- A restored pre-backfill backup may contain legacy MFA material. Before reopening
  authentication, reconcile enrollment, recovery-code retirement, session
  revocation, and authentication-email cancellation under the approved
  Privacy/Operations retention decision.
- If authentication-email provider ownership or outcome is ambiguous, stop
  `auth-email-dispatcher`, disable verified sending through protected
  configuration, preserve the outbox and bearer authority, and do not retry an
  ambiguous prepared row. Resume only after reconciliation and approved review.
- Never include a key, key ID, database URL, token, email address, or provider
  identifier in rollback evidence.

## Required rehearsal evidence

- accepted exact-head review and immutable app/worker digests;
- real disposable six-container preflight, swap, health failure, recovery, and
  roll-forward using the retained overlay;
- data-bearing database, Redis/queue, provider-ownership, audit, object, and MFA
  continuity;
- maintenance-fence deactivation/revocation and zero-active proof;
- reserved-synthetic physician and admin smoke tests;
- monitoring/alert delivery, elapsed recovery time, commands, exit codes, exact
  image IDs, and before/after evidence hashes;
- named Operations owner and approved production recovery authority.

No production checkpoint may advance while this plan is **FAIL**.
