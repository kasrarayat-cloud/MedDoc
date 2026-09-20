# QuillMD recovery material and independent custody

Prepared 2026-09-20. The real B2 upload/readback and isolated restoration have
passed. Independent custody of the decryption material has **not** been proved.
An extra copy on this VPS, an empty handoff destination, and a successful local
key check do not close that gap. No working key is rotated or removed here.

## What a clean offsite restoration actually needs

| Material | Protected source / identity | Purpose |
| --- | --- | --- |
| Current Fernet backup key | `/opt/meddoc-pro/rebuild/.runtime/backup-secrets/fresh-backup-current-20260917.key`, operator `0600` | Decrypt and authenticate current backup manifests, database dumps and referenced files. This is the essential independent decryption copy. |
| Scoped B2 configuration | `/opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json`, operator `0600` | Retrieve encrypted objects from the existing single bucket and `quillmd-fresh/synthetic/` prefix. Preserve the existing exact `listFiles`, `readFiles`, `writeFiles` scope; no master/provisioning key is needed. |
| Nonsecret selection manifest | Prepared below as `selection-<backup-run-id>.json` | Preserve the run ID, ciphertext manifest SHA-256, region, bucket, prefix, reviewed code revision and pinned database runtime independently of this VPS. |
| Reviewed restore code and dependencies | Private `kasrarayat-cloud/MedDoc` repository, exact revision in selection manifest; `rebuild/requirements.txt`; root-owned qualified MinIO client | The existing restore implementation and locked dependency installation must be available on an authorized recovery host. The manifest records MinIO's required version. |
| Pinned PostgreSQL image | Exact image ID and repository digest in selection manifest | Preinstall the matching Linux image on the recovery host. The restorer requires the local exact image and uses `--pull=never`; it cannot recover an absent runtime by magic. |

On 2026-09-20 the currently qualified PostgreSQL image was
`sha256:1bea307dfb3ee30541a7acf7de14b58bcd6948da98e5d31a04c627c4d35ec64b`,
Linux/amd64, with registry reference
`postgres@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`.
These were read from the installed image. Use the image recorded by the selected
authenticated backup; do not impose this historical identity on future backups.
Access to the private repository and availability of the pinned image are
separate recovery prerequisites. This task does not create another cloud host.

The original application passwords, MFA material and ledger are inside the
encrypted database backup. Restoring this backup does not recover unrelated
VPS projects or automatically reconfigure application service credentials,
domains, TLS, mail delivery or payments. Runtime reports, review ZIPs, outbox,
unreferenced scratch files and service credentials are outside this backup's
referenced-file scope. Preserve operational records separately.

### VPS disk unlock is a different mechanism

- `/etc/quillmd/quillmd-fresh-luks.key`: root `0400`, 64 bytes, unattended slot-0
  unlock of the existing live LUKS volume.
- `/etc/quillmd/quillmd-fresh-luks.recovery-passphrase`: root `0400`, 48 bytes,
  recovery access to that existing volume.

Only metadata was inspected for these two files. Their contents were not read
or copied. Neither can decrypt a Fernet offsite backup. Neither is required to
restore the offsite database/files into a clean isolated PostgreSQL container.
Their independent custody remains a separate surviving-volume recovery control;
this procedure must not delete host copies, alter slots, reboot or lock the
shared host. Earlier backup keys also remain untouched so historical backups
remain usable.

## Prepare the minimal handoff without copying secrets

`rebuild/ops/recovery_kit.py prepare` authenticates the selected encrypted
manifest using the existing current key, reads only the approved public B2
configuration fields into its output, and writes a **nonsecret selection
manifest**. It creates an empty private destination for a returned key. It does
not create a plaintext archive of secrets, call B2, rotate a key or establish
custody. Every destination is exclusive; existing files are preserved. Unsafe
permissions, symlinks and hardlinks are refused.

For the first qualified offsite snapshot:

```bash
rebuild/.venv/bin/python -B rebuild/ops/recovery_kit.py prepare \
  --offsite-report /opt/meddoc-pro/rebuild/.runtime/offsite-checks/20260920-first-roundtrip/offsite-20260920T095332Z-a9da0017.json
```

For a later snapshot, use its actual successful offsite report. Counts are read
from that snapshot's authenticated manifest; no historical row count is imposed.
The helper does not manufacture independent evidence from its input report.
The operator must retain the actual qualified report and run records.

Prepared handoff directory:

```text
/opt/meddoc-pro/rebuild/.runtime/recovery-custody-handoff-20260920/
```

It is operator-owned `0700`; its nonsecret selection and empty
`returned-fresh-backup.key` destination are `0600`. This is preparation on the
VPS, **not an independent recovery kit already delivered**.

The established `age` executable is installed, but no approved owner public
recipient is recorded. Therefore this procedure does not improvise an
encryption recipient, use a VPS-only archive password or leave an unprotected
secret archive. A name resembling a vault in browser cache is not an authorized
QuillMD custody integration.

## The single owner custody action

Have the desktop assistant securely store the two selected protected files
(current Fernet key and scoped B2 configuration) and the selection manifest in
your independently controlled encrypted password manager. Retrieve the saved
Fernet key **from that store**, not from a retained transfer download, and return
it through the established strict-host-key SFTP handoff to:

```text
/opt/meddoc-pro/rebuild/.runtime/recovery-custody-handoff-20260920/returned-fresh-backup.key
```

Supply only the custodian and nonsecret vault-item references as evidence.
Never send the key, passphrases, screenshots of values or private links in chat.
The desktop must preserve private local permissions and avoid terminal output,
transcripts and ordinary Downloads copies. A temporary forced-SFTP grant, if
needed, is prepared by engineering for that transfer and removed after verified
receipt. No transfer access is activated merely by this document. Its starting
directory is not filesystem confinement. The previously removed B2 transfer
grant stays removed until a separately authorized transfer is arranged.

No owner-controlled vault or approved independent destination is currently
available to this server. Preparation can finish while this one custody action
remains pending. A statement that the secret was stored is useful provenance;
successful retrieval and the subsequent restore provide the operational proof.

## Verify the returned copy and perform the actual recovery drill

The helper checks the supplied returned file, authenticates the selected
encrypted manifest and checks the recorded image identity. It refuses the live
key path, a link to that file, a wrong key, an empty file and nonprivate material.
It never reads a fallback live key. A valid key check still reports
`independent_custody_verified=false`: software cannot infer external provenance
from equal key bytes.

```bash
rebuild/.venv/bin/python -B rebuild/ops/recovery_kit.py verify-returned \
  --selection /opt/meddoc-pro/rebuild/.runtime/recovery-custody-handoff-20260920/selection-20260920T095332Z-a9da0017.json \
  --returned-key /opt/meddoc-pro/rebuild/.runtime/recovery-custody-handoff-20260920/returned-fresh-backup.key
```

After actual independent retrieval is recorded, engineering uses the existing
download-only recovery mode with that exact returned file and a **new** private
output directory. Use the selected manifest's actual run ID/hash:

```bash
rebuild/.venv/bin/python -B rebuild/ops/offsite_backup.py \
  --config /opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json \
  --download-run-id BACKUP-RUN-ID \
  --manifest-sha MANIFEST-CIPHERTEXT-SHA256 \
  --key-file /opt/meddoc-pro/rebuild/.runtime/recovery-custody-handoff-20260920/returned-fresh-backup.key \
  --output /opt/meddoc-pro/rebuild/.runtime/offsite-recovery-checks/NEW-EXCLUSIVE-DRILL \
  --execute
```

This command has no local backup or plaintext input and no key fallback. The
live key remains intact but is not an input. A same-VPS drill may use the
existing B2 access credential; report that limitation explicitly. Full
credential recovery additionally requires retrieving the vaulted B2 JSON,
validating and installing it under the protected configuration contract, then
using that recovered configuration. Do not claim that the existing local
credential demonstrates its independent recovery.

Before acceptance, compare every downloaded ciphertext hash and every restored
database/file hash against that backup's authenticated manifest, inspect all
financial/scope invariant results, and verify the exact temporary restore
container is gone. Preserve the failure record before any deliberate retry.
Clean up only the disposable returned handoff and owned test resources after
evidence is preserved; keep the working live keys and independent vault copies.
Neither this drill nor custody acceptance approves public launch or patient data.
