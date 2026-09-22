# Continuing offsite backups and account evidence

The September20 controlled encrypted upload/readback and independent-key restore
are preserved. The first daily offsite event is September21 at05:00UTC, after
local04:30. A manual execution or `LastTriggerUSec` persistent stamp is not proof
of a daily firing. Inspect the immutable attempt, systemd invocation journal and
budget together after that event. New attempts retain the systemd invocation ID;
it alone does not establish timer origin. Never label a repaired manual retry as
a scheduled success.

The account-wide observation expires **September21 at20:16:35.867379UTC**.
September22 at05:00 cannot pass without genuine renewal. The restricted worker
cannot renew an account-wide inventory. Automatic backup execution is enabled;
**account evidence renewal still needs separate owner desktop/account access**.
The installed portable collector and importer make that process bounded and
repeatable; they do not make it unattended. A longer local lease would relabel
an old observation, so this milestone retains the24-hour guard.
Collector process tests ran on Linux; this milestone does not claim a real
Windows collector execution or a newly completed account measurement.

## Read status before action

As claude in `/opt/meddoc-pro`, use the operations revision in the durable
checkpoint (the application has its separate installed revision):

```bash
rebuild/.venv/bin/python -B rebuild/ops/backup_alerts.py status
rebuild/.venv/bin/python -B rebuild/ops/offsite_renewal.py status
systemctl list-timers --all quillmd-fresh-offsite.timer --no-pager
journalctl -u quillmd-fresh-offsite.service --since '2 days ago' --no-pager
```

The monitor includes latest complete remote backup, prior independent restore,
actual next run, original observation/expiry, renewal status, current and next-run
UTC budgets and capacity. `current_backup_health` is distinct from continuing
admission. A warning can exit0 because the check executed, while `healthy=false`
and `severity=warning` still need attention. Actual expiry, failed service,
missing/stale backup, partial publication, budget refusal and cleanup failure
remain failures. Approaching expiry alone and ordinary low daily headroom do not
produce repeated incident emails. An uncovered next run or low capacity warrants
one deduplicated actionable alert.

Reservation bytes are conservative response allowances, not provider download
charges. September20's422/98,474,544 remains historical; no retry, crash, timeout
or unconsumed external ticket creates a refund. Future-day reservations remain
charged after rollover and restart. The collector's proposed20/8MiB ticket is
charged to its named day, sharing allowance with scheduled/manual upload,
readback, restore, retry and metadata work. It does not alter provider caps.

## One minimal account-audit handoff

Use the nonsecret ticket path and source revision in the protected final report.
The initial handoff reserves September21 only, ending18:00UTC. Renew before the
current evidence deadline; a result observed earlier has an earlier next deadline.
No returned backup key, runtime-key replacement or SSH grant is needed.

1. On one designated owner desktop/user, obtain **separate account-wide read-only
   audit access**, unrestricted by bucket/prefix, with `listBuckets`/`listFiles`.
   The worker key stays exactly restricted list/read/write on its existing prefix.
   Do not put an audit credential on the VPS or in command arguments, chat or Git.
   Any UI/key-administration work outside the collector needs a separate shared
   reservation **before** the activity; the collector ticket does not grant
   unlimited browser requests or credential administration.
2. Copy the exact nonsecret ticket and reviewed `offsite_account_audit.py` source
   to that desktop's protected directory. Source hash is pinned in the ticket.
   Feed credential JSON with `application_key_id` and `application_key` through a
   secure stdin pipe, e.g. an existing protected vault retrieval. Invoke Python
   with `--ticket TICKET --output NEW_OUTPUT_DIRECTORY --credential-stdin`.
   `NEW_OUTPUT_DIRECTORY` must not exist yet, and its parent must be an existing
   protected directory given as a plain absolute path (a symlink, junction or `..`
   is refused). The collector checks mode 0700 on POSIX only; on Windows it cannot
   verify the ACL, so choose a restricted folder. It creates the directory and
   writes `intent.json` and `account-audit.json` inside it; never pass the JSON
   file's own path. These checks run before the ticket is spent. The ticket is
   spent before the credential is read, so every later refusal spends it
   (credential, collector hash, authentication, scope, timeout, a failed write).
   A refusal during collection prints `"status": "failed"` with a `reason_code`,
   exits 2 and writes a failed `account-audit.json`; the others print one generic
   line and exit 1. The ticket was spent exactly when its `.used.json` marker
   exists in `~/.quillmd-account-audit-spend`. Use a new output name for any
   retry.
   (Corrected 2026-09-22: this step said `NEW_PROTECTED_OUTPUT`, which did not
   say the path is a new directory.) No secret is saved by the collector. Do not
   paste credential literals into a terminal command. The per-user spent-ticket
   registry must remain intact. Copying a ticket to another computer/account to
   evade that registry is outside the authorized consumer model. All replicas
   would need independent budgets.
3. The collector performs two complete matching account inventories. Retained
   versions count even when names repeat. It refuses scope drift, partial pages,
   timeout, auth failure, changed scans or **any unfinished upload/start marker**.
   `b2_list_parts` needs write permission, so read-only access cannot prove a
   nonzero unfinished-part total; refusal preserves the old observation instead.
   See [the provider's capability requirement](https://www.backblaze.com/apidocs/b2-list-parts).
   It makes no object-content download or provider mutation and does not retry.
   Preserve a failed result and request a newly charged ticket before retrying.
4. Return only a verified `account-audit.json` (the collector exited 0) by an
   existing authorized secure channel to a claude0600 regular single-link file
   under a0700 directory. Keep its original bytes. The VPS operator imports with
   the reviewed declaration below. The importer checks issued ticket, exact byte
   hashes, shared reservation, account, scans, sums, deadline, control revision
   and concurrent-policy guard. It creates new evidence with the actual scan
   time+24hours, retains old evidence, and never refunds the prepaid allowance.
   Historical cap observations stay historical; their continued caps rely on the
   existing administrative unchanged-cap rule.
5. A temporary audit credential should be revoked in the owner's authenticated
   interface within separately reserved administration allowance; retain that
   additive result. Collection/import does not invent a revocation check. A
   revoked local key file whose deletion was blocked remains protected; do not
   bypass desktop restrictions or delete vault/working backup keys.

Issue/import commands run on reviewed permanent main, not a worktree:

```bash
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260920-quillmd-offsite-activation.md \
  -- rebuild/.venv/bin/python -B rebuild/ops/offsite_renewal.py issue-ticket \
  --expected-commit EXACT-REVIEWED-OPERATIONS-COMMIT \
  --not-before UTC-START --valid-until UTC-END

bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260920-quillmd-offsite-activation.md \
  -- rebuild/.venv/bin/python -B rebuild/ops/offsite_renewal.py import-result \
  --expected-commit EXACT-REVIEWED-OPERATIONS-COMMIT \
  --ticket-id ISSUED-ID --result PROTECTED-RETURNED-JSON
```

Expired policy may support a prepaid read-only repair ticket after all original
controls validate at its original time; it never authorizes backup traffic.
A partial publication leaves the existing fail-closed marker and protected
intent/result. Inspect and forward-repair against retained candidate/prior bytes;
never remove a marker, rewind the journal or flip booleans to regain admission.
New automatic work resumes only once the actual installed policy validates.

## Capacity, failures and rollback

Latest measured prefix inventory is88 retained versions/28,845,360bytes at
September20 21:52:37UTC; this is not a fresh account-wide total. The1GB reserved
allocation leaves971,154,640bytes at that observation. At the last measured
14,423,108-byte complete set, approximately67 additional same-size sets fit;
this is an estimate, not guaranteed days or capacity for growing data. Every
cycle counts retained versions and pending encrypted objects before upload.
There is no remote pruning permission. On refusal, preserve the previous complete
backup, investigate growth/foreign writers and stop before capacity is exceeded.
Do not change lifecycle or caps to silence an alert.

For failed/partial uploads, inspect the immutable attempt and active transaction;
uncertain PUTs need authenticated inventory/readback under remaining budget.
Do not blindly duplicate versions. Missing/stale local backup requires the local
service/last completed manifest diagnosis before offsite retry. Cleanup failure
retains a failed result even if objects are complete; inspect only identified
scratch resources. Failed renewal preserves the previous observation until its
real expiry; fix scope/access/pagination or return a new legitimate observation.
For source rollback, preserve current journals and evidence, use the scoped
installer disable if admission cannot validate, and review a compatible forward
repair. Reverting ledger or old source alone is not safe rollback.

## Alert and outside-host limits

One existing incident email was provider-accepted. A bounded read of its delivery
record on September20 returned401 with the available credential; no duplicate was
sent. Delivery status and human inbox confirmation remain unavailable. Do not
call acceptance delivery. See the detailed protected report for message identity.

No authorized outside-host endpoint is configured or available through connected
access. [The concrete heartbeat handoff](operational-alerts.md#outside-host-outage-detection--prepared-not-active)
uses one existing owner-controlled check: five-minute period, ten-minute grace,
existing approved recipient, individual secret check URL only. It exposes no
clinical/billing/detail status and leaves public maintenance intact. Qualify a
missing heartbeat on an isolated check; never shut down the shared VPS. Until that
access exists, VPS-local monitoring cannot prove total-host-loss detection.
