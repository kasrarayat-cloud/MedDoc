# QuillMD shared offsite consumers — 2026-09-20

This current operator entry point supersedes the unbudgeted MinIO examples in
older offsite qualification runbooks. Their historical measurements remain
valid history. Do not run their old transport adapter. This document describes
controls, not a claim that a timer or a future provider request has succeeded;
the protected checkpoint records actual installation and execution.

## One live transport and accounting authority

All supported QuillMD B2 consumers use `automatic_offsite.NativeTransport`, the
canonical `rebuild/.runtime/automatic-offsite/execution.lock`, the protected
`backup-secrets/offsite-policy.json`, and the durable shared `budget.json` in that
state directory. An alternate state directory, stale policy, replaced lock,
missing ledger, or different runtime configuration cannot authorize HTTP.
`offsite_backup.authorize`, `McTransport`, its `command` method and its read/write
methods now refuse before network or subprocess work. No second S3 client remains.

| Consumer | Supported entry point | Shared controls |
| --- | --- | --- |
| Daily upload and encrypted readback | Installed `quillmd-fresh-offsite.service` | Canonical policy, lock, budget, authenticated selection, capacity admission and complete-manifest publication |
| Manual upload or retry | Same service, or `automatic_offsite.py run` | Exactly the same engine; no separate upload implementation |
| Scoped metadata check | `offsite_operator.py inventory` | Authorization and every pagination request charged; no object-content downloads |
| Remote download and isolated restore | `offsite_backup.py --download-run-id … --execute` | Same lock and budget held through isolated restore; only the explicitly supplied decryption key |
| External desktop/operator consumption | `offsite_operator.py reserve-external …` | Durable additive reservation, unique evidence reference, no provider request and no credential read |
| Offline preparation and returned-key verification | Existing preparation mode / `recovery_kit.py verify-returned` | No B2 traffic; does not create or refresh provider evidence |

Failed requests, bounded response overrun, uncertain PUTs, and retries consume
reservations. There are no refunds. Restart does not reset the ledger; the v2
ledger retains every day and the exact imported v1 counters. A request that can
span UTC midnight is conservatively reserved against both possible dates. A
failure between durable reservation and HTTP still consumes its reservation.
Never delete, truncate or recreate the ledger to get a green admission check.

The runtime credential cannot delete versions. Inventory includes retained
versions and refuses unfinished uploads before admitting writes. Current stored
versions plus all pending encrypted bytes must fit the reserved prefix ceiling.
The engine publishes the encrypted manifest only after data-object readbacks,
then verifies that manifest. A retry inventories uncertain state and authenticates
existing bytes rather than blindly creating duplicate versions. A missing object
after an uncertain write is an operator investigation, not permission to retry it.
No remote pruning or lifecycle mutation is part of this workflow.

## Commands

Run from `/opt/meddoc-pro` as the existing authorized operator. The systemd service
is preferred for uploads because its runtime and environment controls are already
installed. These commands never print key material:

```bash
rebuild/.venv/bin/python -B rebuild/ops/automatic_offsite.py inspect
rebuild/.venv/bin/python -B rebuild/ops/backup_alerts.py status
rebuild/.venv/bin/python -B rebuild/ops/offsite_operator.py inventory
```

The first two are local, read-only inspections. `inventory` spends shared request
and response allowances, explicitly measures the restricted prefix, and cannot
refresh an account-wide audit. It reports zero unfinished uploads only after the
Native API confirms there are none; an unfinished upload makes the command fail.

Record observed external work and a defensible navigation/response cushion, or
reserve planned outside activity before performing it. Use the actual unique
nonsecret evidence reference and supported bounds; do not copy example numbers
as measurements:

```bash
rebuild/.venv/bin/python -B rebuild/ops/offsite_operator.py reserve-external \
  --requests REQUEST_BOUND --download-bytes RESPONSE_BYTE_BOUND \
  --reference NONSECRET_UNIQUE_EVIDENCE_REFERENCE
```

The command adds to existing consumption under the same lock and current policy.
Duplicate references and negative values are refused. It cannot change provider
caps or grant new allowance. The policy must be valid before any command uses it.
Renewing expired evidence does not reset daily counters.

For a future authorized recovery, first create a new protected output directory,
obtain the selected run ID and manifest ciphertext hash from the retained receipt,
and securely retrieve the decryption key. The key must be outside the output
folder. Preserve the existing independent-key proof; no repeat is needed for this
activation milestone.

```bash
rebuild/.venv/bin/python -B rebuild/ops/offsite_backup.py \
  --config /opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json \
  --download-run-id SELECTED_RUN_ID --manifest-sha SELECTED_MANIFEST_CIPHERTEXT_SHA256 \
  --key-file PROTECTED_EXPLICIT_KEY_FILE --output NEW_PROTECTED_OUTPUT_DIRECTORY \
  --execute
```

The command authenticates remote encrypted bytes, reserves the whole selected
inventory before content downloads, and restores into the existing networkless
isolated adapter. It has no implicit live-key or original-plaintext fallback.
A 900-second workload deadline allows at most 45 additional seconds for cleanup.
The output contains immutable intent and final evidence; a crash retains the
intent and incomplete encrypted set. Cleanup failure is a failed command even if
data verification passed. Inspect the recorded temporary container before exact
cleanup; never target the live database or working backup directories. The
canonical `manual-status.json` lets the installed monitor expose failed or stalled
manual recovery separately from the scheduled-upload history. An overlapping
lock refusal leaves the actual runner's summary intact.

Recovery on a replacement host requires installing the same reviewed controls,
current protected policy and an auditable shared-consumption baseline. This
command does not establish whole-host recovery, offline custody, or recovery
after loss of the Windows vault computer/account.

## Administrative assumptions and renewal

The reserved allocation is `quillmd-fresh/synthetic/` in the existing dedicated
private bucket. The installed worker and the supported commands above are the
known QuillMD writers and readers. The owner may still administer the account:
read-only audits without `listKeys` do not enumerate every credential, and an
operator who can read the runtime credential can technically use another client.
The application service identities cannot read these protected operator secrets.
This is an enforced entry-point policy plus an explicit administrative operating
agreement, not an assertion that root or the account owner is technically barred.

Do not write to this prefix with another client, create unfinished uploads, change
caps, add consumers, or grow non-QuillMD usage without first pausing the timer and
renewing the account/allocation evidence. Account-wide evidence is finite. The
restricted runtime key cannot inspect other buckets/prefixes or renew it unaided.
The owner desktop must repeat complete version and unfinished-part scans before
the installed deadline and pass the resulting nonsecret evidence to the existing
policy installer. Preserve original observation times and the old records;
validation and local serialization do not make an old observation fresh.

When expiry, capacity, an uncertain write, or budget exhaustion refuses work,
keep the previous complete remote backup. Check `backup_alerts.py status`, the
protected attempt record, `active.json`, and the shared ledger. Resolve the exact
cause without widening permissions, deleting retention, raising caps or resetting
counters. Allowance freshness and the first scheduled trigger must overlap.
