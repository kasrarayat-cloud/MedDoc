# Production backup status publisher — prepared, not installed

2026-09-27. Engineering agent: Astra. Parent host package `fbd93177`; the application and its selected Sonnet model are unchanged by this package. No AWS request, infrastructure purchase, service start, provider call or production database mutation occurred.

## Scope and evidence limits

`publish_operations_status --profile production` now has a production collector. Its existing `ServiceHealth` backup row and admin **Offsite recovery** detail display fixed labels, counts and timestamps. The web process gains no AWS permissions or operator-file access. The private B2 collector remains the default for the private deployment; a production environment explicitly refuses that default.

The read-only AWS collector checks both the exact RDS instance and the EBS state volume in the installed bootstrap receipt. A completed source job must reference an actual encrypted, current recovery point in the pinned source vault; a completed copy job must link that source point to an actual encrypted point in the pinned backup-account vault. Wrong-resource/vault/role identity, incomplete pagination or API failure cannot provide capture coverage. A failed job remains visible even if another job succeeded. `COMPLETED` with missing/non-success `MessageCategory` is an issue, not a clean completion.

RDS recovery evidence is the actual `DescribeDBInstanceAutomatedBackups.RestoreWindow` for the exact source resource, with active status and 35-day retention. The DB-instance and automated-backup latest timestamps must each be between now and 15 minutes ago. The earlier latest timestamp is displayed, and the true earliest timestamp must precede it. No synthetic `now minus retention` window is created. The backup vault must report `Locked=true` and a lock date already reached; governance mode or a cooling-off date does not satisfy this check.

Capture freshness is fixed at 26 hours for daily RDS snapshots and two hours for hourly EBS snapshots. These are monitoring tolerances, not a broader clinical RPO promise. Same-region production and separate backup accounts are supported by this initial operator configuration; a different-region policy needs an explicit reviewed extension.

Even when all capture checks pass, the overall report is **warning**, `healthy=false`, `offsite_recovery_verified=false`, and `outside_host_failure_detection=false`. Its action states that restore drills and delivered alerts require separate evidence. This publisher does not qualify a restore, validate file/database consistency, prove retained-history length, inspect the full retention policy, certify legal coverage or prove delivered SNS/heartbeat alerts. Those launch gates remain in the cutover matrix. AWS Backup remains the V1 backup route; no new logical-backup layer was introduced.

## Concrete installation inputs

On the new approved production target, after the activated profile, bootstrap receipt and runtime application environment have been verified, install root-owned mode-0600 `operator/backup-status.json` under the profile's configuration directory. No symlink, extra keys or shared-readable file is accepted. Fill these fields from the reviewed account configuration, never from an old private environment:

```json
{
  "format": 1,
  "profile_sha256": "FULL_ACTIVATED_PROFILE_SHA256",
  "database_arn": "EXACT_PRODUCTION_RDS_INSTANCE_ARN",
  "database_resource_id": "EXACT_DBI_RESOURCE_ID",
  "state_volume_arn": "EXACT_BOOTSTRAP_RECEIPT_STATE_VOLUME_ARN",
  "kms_key_arn": "EXACT_PRODUCTION_DATA_KEY_ARN",
  "copy_kms_key_arn": "EXACT_BACKUP_ACCOUNT_KEY_ARN",
  "source_vault_arn": "EXACT_PRODUCTION_BACKUP_VAULT_ARN",
  "copy_vault_arn": "EXACT_SEPARATE_ACCOUNT_BACKUP_VAULT_ARN",
  "source_read_role_arn": "EXACT_PRODUCTION_READ_ROLE_ARN",
  "copy_read_role_arn": "EXACT_BACKUP_ACCOUNT_READ_ROLE_ARN"
}
```

The placeholders deliberately fail validation. The data volume must match `state_volume` in `/var/lib/quillmd-bootstrap/receipt.json`; the RDS endpoint/name/port/ARN/resource ID must match the activated profile and AWS response. Source and copy accounts must differ. This is an ongoing operator configuration, not a daily renewable paid admission ticket.

The EC2 operator role needs permission only to assume the two designated read roles for this collector (its existing separately reviewed environment-renderer/SSM permissions are unchanged). Each role trusts only that approved operator role. Session name is fixed; credentials are held in subprocess environments, not arguments or published data. The collector clears inherited AWS configuration, credentials, endpoints and application secrets from each AWS subprocess and validates the assumed caller account/role. No AWS CLI profile or endpoint is accepted from a caller.

Required reads:

| Scope | Required actions | Reviewed resource boundary |
|---|---|---|
| Production read role | `rds:DescribeDBInstances`, `rds:DescribeDBInstanceAutomatedBackups` | Production database; filter and revalidate its immutable resource ID and ARN |
| Production read role | `backup:ListBackupJobs`, `backup:ListCopyJobs`, `backup:ListRecoveryPointsByBackupVault` | Production account/region, exact resources and source vault |
| Backup account read role | `backup:DescribeBackupVault`, `backup:ListRecoveryPointsByBackupVault` | Exact copy vault; no restore, copy, delete or policy-write permission |
| Both role sessions | `sts:GetCallerIdentity` | Confirm expected assumed identity |

Use resource restrictions supported by each action and an approved region/account condition. Account-level list permissions, where the AWS action requires them, still need independent IAM review; the collector's filters are not IAM enforcement. Actual IAM policies, trust, API access and KMS/vault configuration must be verified on the approved account before enabling the timer. No credential or account permission is asserted by this offline work.

## Publisher and cutover sequence

The bootstrap installs and hashes `quillmd-production-operations-status.service` and `.timer` alongside the other prepared units, without enabling or starting them. The root oneshot loads the existing tmpfs application environment, checks the installed release/profile receipt, applies the same production environment checks and pinned CA as the service launcher, then executes only the production publisher. Before collection, the management command verifies the actual Django connection is the exact runtime role/database over `verify-full` TLS with replication role `origin`. It writes only `ServiceHealth` using runtime credentials. AWS reads run under the separate assumed roles.

The existing publication exclusion is bound to the root-only production operator directory:

`/etc/quillmd-production/operator/operations-publication/publication/.activation-publication.lock`

Before an actual cutover/recovery that guards the status row, stop this production timer, wait for its oneshot to finish and acquire that same lock through `ops.activation_exclusion.bind_runtime(profile.operator_directory / 'operations-publication')` and `hold(...)`. Do not use the private B2 installer's timer controls or its private lock. Do not delete a lock to force progress. A deferred publisher collects nothing and leaves the old row aging visibly.

During the authorized production cutover, the operator should first inspect the exact installed configuration and use the root launcher `ops/publish_production_status.py --dry-run` through the prepared managed environment. This performs read-only AWS/database checks but does not publish. Then run the service once; inspect the persisted fixed metadata and admin row before enabling the timer. The five-minute timer preserves existing stale/failed escalation. API errors publish an explicit unknown/failure report and exit nonzero; target-verification failures refuse before writing, so any existing row becomes stale. Rollback disables this timer and retains the row/evidence; it does not install the private publisher on the production target.

The checked-in profile remains unactivated. This package has not been installed or executed on AWS. Root managed environment, account access, the reviewed operator configuration and actual target checks remain deployment prerequisites; a successful mock is not those checks.

## Finite verification and preserved failures

All evidence is under `rebuild/.runtime/aws-backup-status-20260927/`; selected durable copies accompany this report under `docs/rebuild/v1/aws-backup-status-evidence-20260927/`.

- Final collector/launcher/unit offline checks: **13 passed**. Includes positive exact-resource coverage, missing/other-resource/unencrypted copies, stale/future timestamps, completed-with-issues and failed jobs, vault lock, true RDS API shape, wrong identity, unactivated profile, pagination continuation refusal and redaction.
- Existing bootstrap dry-run/refusal class: **5 passed**. Combined earlier log is 17 passes (12 collector checks plus 5 bootstrap checks); the added future-time test subsequently made the collector class 13.
- Production publisher plus existing private publication exclusion and admin status checks: **25 passed**, isolated synthetic PostgreSQL on port 55704. Includes real row publication, failure exit after storing unknown, dry-run, target refusal, explicit profile, lock deferral, missing/stale status and private-path preservation. Static manifest resolution was replaced with plain static-file storage in this synthetic test runner only; this is not served production rendering evidence.
- Source/document diff whitespace checks passed. The full staged check flagged one trailing space emitted by unittest before a subtest failure in the retained raw `rds-future-red.log`; that original evidence was preserved verbatim, not normalized.

Retained first failures: a test-file write used an incorrect relative directory (no product change; `offline-first.log` records the missing test module); the initial publisher test expected a nonexistent `healthy` key in the already-established console projection (`publisher-first.log`, corrected test uses severity); independent root refutation found a fabricated `DBInstance.EarliestRestorableTime` field in the original mock/collector (`rds-real-shape-red.log`), then a future timestamp hidden by `min` (`rds-future-red.log`, both controls failed). Both demonstrated product defects were repaired with focused green reruns. No result was erased or restated as first-pass success.

Official API references consulted 2026-09-27: [RDS automated-backup shape](https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_DBInstanceAutomatedBackup.html), [RDS paginated automated backups](https://docs.aws.amazon.com/cli/latest/reference/rds/describe-db-instance-automated-backups.html), [backup jobs](https://docs.aws.amazon.com/cli/latest/reference/backup/list-backup-jobs.html), [copy jobs](https://docs.aws.amazon.com/cli/latest/reference/backup/list-copy-jobs.html), [recovery points and pagination](https://docs.aws.amazon.com/cli/latest/reference/backup/list-recovery-points-by-backup-vault.html), [vault lock state](https://docs.aws.amazon.com/cli/latest/reference/backup/describe-backup-vault.html).

The lead independently re-ran the documented-shape counterexample after the repair and then the two future-timestamp cases after the second repair: current metadata passed the capture check and both future variants required attention. The finished bounded reread found no further demonstrated issue. The lead's original/after/final probe transcripts remain in the root recovery evidence; this report does not widen that review into live AWS proof.
