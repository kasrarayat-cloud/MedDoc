# Automatic offsite operation and renewal

This supplements the existing recovery runbook. Installation evidence, provider
results, exact installed revisions and timer activation belong in the runtime
checkpoint; the presence of this source document does not assert activation.

The permanent local timer captures at 04:30 UTC. The permanent offsite timer runs
at 05:00 UTC. A controlled service start proves the installed service, not a
scheduled firing. Activation accepts the unchanged, reviewed service and timer
only after an authenticated controlled readback, then verifies systemd's actual
next run. The next run plus the 900-second execution limit and one-minute timer
accuracy window must precede account-evidence expiry. Adoption keeps the original
installation receipt and adds an immutable receipt for the reviewed operations
revision. It does not rewrite unit files or restart the private application.

Read the installed operational view without making provider requests:

```bash
/opt/meddoc-pro/rebuild/.venv/bin/python -B /opt/meddoc-pro/rebuild/ops/backup_alerts.py status
/opt/meddoc-pro/rebuild/.venv/bin/python -B /opt/meddoc-pro/rebuild/ops/automatic_offsite.py inspect
systemctl list-timers quillmd-fresh-backup.timer quillmd-fresh-offsite.timer
```

The view separates the latest completed encrypted remote set and authenticated
readback from the historical isolated restore. A newer backup does not erase the
independent-key proof for the earlier backup; it also does not make that earlier
proof a restore test of the new backup. Shared daily counters are conservative
pre-request reservations, including failures and uncertain transfers, rather than
provider invoices or exact account-wide usage. Scoped capacity is an observation;
room for another backup of the same size is an estimate, not a future-size promise.
The five-minute monitor reads local evidence without polling B2. Remote missing
or altered objects are detected by the next budgeted inventory/readback, whose
failure reaches the monitor; there is no claim of continuous remote inspection.

The account-wide observation ended at **2026-09-20 20:16:35.867379 UTC**. The
proposed installation expires at **2026-09-21 20:16:35.867379 UTC**. Read the actual
installed policy deadline in the view. Renewal requires a fresh authenticated
desktop account-wide inventory, including retained versions and unfinished parts,
and reviewed installation of its evidence and policy. The restricted worker
cannot obtain account-wide inventory or renew that observation unaided. The
monitor warns when the next daily run falls outside the policy window; the
worker independently refuses expired evidence before provider work. Do not extend
timestamps, reset counters or change confirmation flags to clear this condition.

After the fresh nonsecret account audit, operating evidence and provenance have
been imported into a new protected observation directory, use the reviewed policy
installer. Replace the observation directory below with that new directory;
keeping the old observation never extends its validity. The plan has no provider
calls or policy-file changes. Execution validates and publishes the exact policy
and allocation together under the shared lock, preserving prior files and the
entire accounting journal. Use the permanent reviewed main revision and existing
CI/declaration controls:

```bash
cd /opt/meddoc-pro
offsite_revision="$(git rev-parse HEAD)"
offsite_evidence=/opt/meddoc-pro/rebuild/.runtime/offsite-account-evidence/YYYYMMDDTHHMMSSZ
rebuild/.venv/bin/python -B rebuild/ops/install_offsite_policy.py --expected-commit "$offsite_revision" --evidence-directory "$offsite_evidence"
bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20260920-quillmd-offsite-activation.md -- rebuild/.venv/bin/python -B rebuild/ops/install_offsite_policy.py --expected-commit "$offsite_revision" --evidence-directory "$offsite_evidence" --execute
```

If no fresh desktop observation is available by expiry, the monitor becomes red
and new work refuses before provider calls. An enabled timer does not renew
evidence and may remain enabled while its service refuses; use reviewed disable
to pause it. A partial policy publication keeps a fail-closed installation marker
and its intent/result records. Inspect and reconcile the preserved pair before
clearing that marker; deleting it merely to make admission green is not renewal.

For failure, capacity or expiry, inspect the protected automatic-offsite journal
and systemd service result. Keep the prior complete backup and all immutable
versions. A possible partial write remains reserved; diagnose it with the shared
operator tools before retrying. A failed service cannot be treated as healthy just
because an older success record survives. A failed manual isolated restore or
cleanup is visible separately, even if scheduled uploads remain healthy. Preserve
its failure record and confirm all owned temporary processes stopped; do not
report recovery completion while cleanup is unresolved. The worker has no remote
delete permission. Capacity refusal needs a supported capacity decision, not a
pruning command or cap increase.

The existing alert route is the only approved message destination. Acceptance,
provider delivery, and human inbox receipt remain different claims. Do not send
repeated tests to replace an outstanding receipt confirmation. An absent protected
outside-host heartbeat configuration remains an explicit external dependency.
The existing integration handoff in `private-operations-runbook-20260920.md` describes the
fixed endpoint contract; a successful ping alone would still not prove a missed
heartbeat alert or detection of complete host loss.

Safe containment is the installer's reviewed `disable` action under the committed
mutation declaration. It disables only the offsite timer and stops its service,
while retaining the encrypted backups, account evidence, accounting journal,
working keys, original receipts and historical restore proof. It does not need a
working B2 credential or policy. Re-enable only through qualification and the same
reviewed expiry and first-run checks.
