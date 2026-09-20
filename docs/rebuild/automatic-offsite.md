# Automatic encrypted offsite backups — operating and recovery handoff

Prepared 2026-09-20. This adds a guarded daily uploader to the existing encrypted
local capture. The original B2 qualification remains valid and unchanged. New
recurrence is **not enabled by the existence of the bucket or credential**.

## Installed execution contract

- Local capture: existing `quillmd-fresh-backup.timer`, 04:30 UTC.
- Remote stage: `quillmd-fresh-offsite.timer`, selected 05:00 UTC. Installation
  leaves it disabled until current operating-envelope evidence passes.
- Service: `quillmd-fresh-offsite.service`, operator `claude`, no application
  restart, 900-second application deadline / 960-second systemd limit, no swap,
  1 GiB memory limit, private state and mutual exclusion. It does not start another
  local snapshot, prune versions, rotate a key, or perform daily isolated restores.
- Existing monitor: `quillmd-fresh-backup-alerts.timer`, every five minutes.

The engine authenticates the completed local manifest, database dump and files
before network access. It inventories **all versions within the approved prefix**,
counts retained bytes, and publishes the encrypted manifest only after all data
objects have passed SHA-256 and authenticated decryption readback. A partial set
never becomes a complete backup. B2 SHA-1 metadata is not the readback proof.

Each attempted request reserves request and download budgets before I/O. Timeouts
consume their reserved allowance. Provider details and credentials stay out of
status/errors. No automatic redirects, implicit retries, multipart uploads,
broad bucket discovery or deletion are permitted. Progress records survive a
restart; existing matching remote objects are read and reused. An uncertain PUT
whose object cannot be found is refused for operator investigation, not blindly
repeated into another charged version. Keep the attempt and journal intact.

A repeated invocation with no newer local snapshot preserves the old completion
and readback timestamps and does not invent a fresh verification. A stale local
snapshot or remote readback remains visible to monitoring. An interrupted old
snapshot that has become stale requires investigation before the next run; do not
silently clear its uncertainty or claim recovery from partial objects.

## Current evidence and conservative capacity choice

The read-only Native v4 inventory at 17:28:08 UTC on 2026-09-20 observed 44 retained
versions / 14,422,252 bytes inside this prefix, all upload actions and no pagination.
It cannot see objects outside the prefix or establish account-wide caps/usage.
The owner's 16:35 UTC account observation (0 stored / displayed 10 GB cap,
0 downloaded / displayed 1 GB daily cap) is historical, not a new measurement.

Current [Backblaze pricing](https://www.backblaze.com/cloud-storage/pricing)
identifies the first 10 GB as free and Class A/B/C calls as free for pay-as-you-go,
with a monthly egress allowance. The older
[caps help article](https://help.backblaze.com/hc/en-us/articles/217931138-How-to-use-B2-data-caps-alerts)
describes daily free counters. These general pages do not prove this account's
actual caps or allocation. No account settings are changed based on either page.

Engineering selects an initial **1,000,000,000-byte prefix ceiling**,
**100,000,000 response bytes/day**, **500 requests/day**, maximum **900 seconds**
per run, and a **30-hour** local-snapshot freshness requirement. Response budgets
conservatively reserve metadata as well as file payloads. The ceilings are local
safety limits, not new provider permissions or a claim about free usage.
At the measured snapshot size, 1 GB holds at most 69 such sets: 68 additional sets
beyond the current one (980,713,136 bytes), leaving 4,864,612 bytes after all 69.
Actual snapshots vary; each run calculates with actual encrypted lengths and all
retained versions. A 30-day interval at unchanged size adds 432,667,560 bytes.
These are conditional arithmetic, **not established account headroom**.

Keep all versions and existing retention rules. The installed key has no deletion
capability. At a capacity refusal, stop uploads and alert; an owner-approved,
separately reviewed destructive retention policy would be a later task. There is
no automatic pruning promise and no increase in caps, purchases or payment setup.

## Exact missing operating-envelope handoff

The existing bucket and credential need no setup. The owner desktop can read the
current B2 Caps & Alerts/account usage without changing it, record observation
UTC and evidence reference, and confirm that the selected prefix/storage and
request/download budgets are exclusively available to this automation. Account
usage must include other buckets/prefixes and all retained versions. Record the
actual account request/download restrictions and current usage, even if the
account reports free API calls. Do not send account screenshots containing secrets.

Place this **nonsecret but protected** evidence in:

```text
/opt/meddoc-pro/rebuild/.runtime/recovery-custody-handoff-20260920/operating-envelope-evidence.json
```

Owner `claude`, mode `0600`, parent `0700`, using the established secure transfer.
Engineering validates it and installs the following contract at
`/opt/meddoc-pro/rebuild/.runtime/backup-secrets/offsite-policy.json` (0600).
There is no valid policy file until evidence supports it. The preparation template
below deliberately fails validation; unknown amounts and approvals stay unknown.

```json
{
  "version": 1,
  "approved": false,
  "approval_reference": "PENDING actual protected evidence",
  "observed_at": null,
  "valid_until": null,
  "bucket_id": "e5d31ce87af3b0f0a00a0916",
  "prefix": "quillmd-fresh/synthetic/",
  "account_storage_limit_bytes": null,
  "account_storage_used_bytes_at_observation": null,
  "scope_storage_bytes_at_observation": null,
  "scope_storage_ceiling_bytes": 1000000000,
  "exclusive_scope_allocation_confirmed": false,
  "exclusive_daily_budgets_confirmed": false,
  "daily_download_budget_bytes": 100000000,
  "daily_request_budget": 500,
  "max_run_seconds": 900,
  "max_local_age_hours": 30
}
```

Evidence validity is bounded to at most 31 days. Choose a 30-day initial window
only when current account evidence and allocation support it. Expiry refuses
network I/O and is actionable, so it must be renewed from authentic evidence.
Fresh evidence is required after conflicting use or account-cap changes. Never
set approval booleans from an empty-prefix inference or manufacture an observation.

## Engineering activation and rollback

All source and the declaration must pass exact PR/merge CI. From the permanent
main tree, the installer verifies byte identity, source commit, pinned local
privileged helper, application process/configuration invariants and exclusive
unit paths. Installation and activation are separate acts:

```bash
rebuild/.venv/bin/python -B rebuild/ops/install_offsite_schedule.py --expected-commit FULL_REVIEWED_SHA --action install
bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20260920-quillmd-automatic-offsite.md -- rebuild/.venv/bin/python -B rebuild/ops/install_offsite_schedule.py --expected-commit FULL_REVIEWED_SHA --action install --execute
```

After current policy installation, inspect first (zero provider requests). Then
use the same reviewed wrapper with `--action activate --execute`. It requires
policy eligibility under the intended operator, a controlled successful service
run and its immutable complete/readback evidence **before** enabling the timer.
A no-op reusing an older readback is insufficient for initial activation; use the next unprocessed completed local snapshot. Record that first start as a manual service invocation. Later
`LastTriggerUSec` and matching service/attempt records establish actual calendar
execution; `NextElapseUSecRealtime` alone does not prove a scheduled run happened.

Rollback uses the same wrapper and installer with `--action disable --execute`.
It stops/disables only the new offsite units and preserves all remote objects,
credentials, unit files, records and failed attempts. Diagnose before retry.
No change to existing local backup, email timer, application or shared services.

## Monitoring and incident actions

Private `automatic-offsite/status.json` separates last complete remote backup,
last authenticated readback, and last isolated restore with its key source.
Immutable attempt files preserve failure and refusal evidence. Monitor output
separates these from local capture and from outside-host detection/custody.
Prepared pending configuration is actionable but does not send an unsolicited
failure email. Actual failures/refusals and stale enabled work use the approved
Resend recipient with existing idempotency/cooldown rules; fixture routing tests
are labelled as fixtures. Provider acceptance does not establish inbox receipt.

- `policy_missing/invalid/expired`: inspect the protected account evidence and
  policy; keep recurrence disabled until corrected through the reviewed path.
- `capacity_refused/budget_exhausted`: preserve all versions; inspect current
  usage and other consumers. Do not raise caps or clear durable budget counters.
- `remote_uncertain`: preserve active journal; inspect exact object/version and
  provider outcome before any deliberate retry. Never clear uncertainty blindly.
- `remote_corrupt/local_authentication_failed`: retain bytes and prior complete
  sets, check source hashes and correct key. Do not overwrite historical objects.
- `transport_failed/deadline`: inspect redacted attempts; reservations remain
  charged conservatively. Later safe resumption reuses proven remote objects.

The same-VPS monitor cannot report a total VPS outage from outside. The existing
external-heartbeat credential remains separately pending; see
[operational-alerts.md](operational-alerts.md). The existing authorized test alert
has provider-acceptance evidence but still requires human inbox confirmation.

## Independent recovery

Use [recovery-kit.md](recovery-kit.md) for the exact minimal material and the one
owner custody action. A prepared manifest, local key, or local restore is not
independent custody. When an actual vault-retrieved key arrives, authenticate it
without fallback, then perform one download-only isolated restore using that
copy. Compare the chosen backup's own counts/hashes, not historical row counts.
Until that evidence exists the custody-based recovery drill remains pending.
