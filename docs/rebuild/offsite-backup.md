# Encrypted offsite backup preparation

Prepared 2026-09-17. **No remote destination has been approved/configured and no
offsite upload, download or restore has been performed.** The adapter and its
tests are preparation. The existing local encrypted backup/isolated restore
evidence remains separate.

## Owner input and secure configuration

Use the existing destination decision in [owner-actions.md](owner-actions.md):
an owner-approved private Backblaze B2 bucket for the new synthetic system,
restricted to `quillmd-fresh/synthetic/`. The adapter does not create a bucket,
buy capacity, alter bucket policies, delete anything or enable a schedule.

Supply a standard application key restricted to exactly that one named bucket
and prefix with only `listFiles`, `readFiles` and `writeFiles`. It must lack
`deleteFiles`, `listAllBucketNames`, bucket/key administration and partner
administration. Backblaze's v4 authorization response exposes the actual bucket,
prefix and capability restrictions, which the adapter verifies before its first
upload. [Backblaze authorization API](https://www.backblaze.com/apidocs/b2-authorize-account)

Through protected SSH/SFTP or the existing secret manager, create an
operator-owned `0600` JSON file at:

`/opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json`

Use this exact schema, replacing placeholders securely. Never paste actual keys
in chat, a command line or a tracked file:

```json
{
  "version": 1,
  "endpoint": "https://s3.us-west-004.backblazeb2.com",
  "region": "us-west-004",
  "bucket": "APPROVED-BUCKET-NAME",
  "bucket_id": "APPROVED-24-CHARACTER-HEX-ID",
  "prefix": "quillmd-fresh/synthetic/",
  "application_key_id": "REPLACE-THROUGH-SECURE-CHANNEL",
  "application_key": "REPLACE-THROUGH-SECURE-CHANNEL",
  "owner_approval_reference": "REFERENCE-TO-RECORDED-DESTINATION-APPROVAL",
  "private_bucket_confirmed": true,
  "synthetic_only": true
}
```

Use the bucket's actual endpoint/region and lowercase S3-compatible bucket name.
The endpoint must be the exact HTTPS Backblaze regional endpoint, with no
embedded credentials, additional path, custom port, query or alternate host.
The provider response must agree. Bucket privacy is **owner-confirmed**, because
this key deliberately has no bucket-administration/read-policy capability; the
adapter does not pretend to verify privacy from the key's scope alone.

Keep the encryption key outside both the local backup and downloaded-backup
directories. Store a recovery copy in the owner's separate encrypted vault.
The configuration is not passed to an application service. The application
identity cannot read the operator runtime or backup keys.

## Transport and integrity

The adapter uses the installed root-owned MinIO client, qualified version
`RELEASE.2025-08-13T08-35-41Z`, without changing the shared Python environment.
`mc put --disable-multipart` sends each bounded object; `mc get` downloads each
known object directly. There is no `mirror`, delete, bucket creation or
bucket-listing command. Each command receives a temporary private configuration
directory, not key material in arguments. The child environment excludes
inherited application keys, proxies and `MC_INSECURE`/`MC_DEBUG` overrides.

`MC_REGION` is set explicitly; the
[matching client source](https://raw.githubusercontent.com/minio/mc/7394ce0dd2a80935aded936b09fa12cbb3cb8096/cmd/client-s3.go)
passes it to the S3 client. This avoids relying on region-discovery access.
Backblaze compatibility under the exact restricted key still needs a live test;
failure must not be solved by silently widening permissions. The MinIO
[upload interface](https://min.io/docs/minio/linux/reference/minio-mc/mc-put.html)
provides the existing S3 implementation; QuillMD does not implement S3 signing.

Before any upload, the adapter authenticates the Fernet manifest and every
encrypted object and verifies plaintext size/hash **in memory**. Only these
objects are eligible:

- `database.dump.fernet`
- `objects/<64-character-hash>.fernet`
- `manifest.json.fernet`, uploaded last

Keys, plaintext, `summary.json`, unexpected files, links, duplicate objects and
path traversal are refused. Objects are bounded to the existing backup limits;
the download subprocess also has a file-size limit. No decrypted database or
document is written into transport staging.

The remote layout is:

```text
quillmd-fresh/synthetic/<backup-run-id>/<manifest-ciphertext-sha256>/<encrypted-object>
```

The manifest hash distinguishes different authenticated backups even if a run
name is reused. Retrying an identical upload can create another identical B2
object version; exactly-once remote storage/version allocation is not claimed.
No automatic retry, version deletion or retention mutation is implemented.

The download path reads the remote encrypted manifest, verifies the expected
ciphertext hash, authenticates it with the separate key, and verifies every
downloaded object's ciphertext hash and authenticated plaintext size/hash. A
partial attempt retains an `INCOMPLETE` marker. Existing destination directories
are never overwritten. The downloaded directory is then handed to the existing
`backup_restore.restore` implementation, which restores into a labelled,
networkless container with no published ports, workers or provider credentials,
and compares table/file hashes and invariants. Its owned temporary container is
removed through the existing label guard.

## Operator use after configuration is approved

Commands below contain only paths and nonsecret backup identifiers. Use the
current protected key location; never put the key's value in a command.

Local preparation, with **zero network calls**:

```bash
rebuild/.venv/bin/python rebuild/ops/offsite_backup.py \
  --config /opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json \
  --backup /opt/meddoc-pro/rebuild/.runtime/new-system-backups/BACKUP-RUN-ID \
  --key-file /opt/meddoc-pro/rebuild/.runtime/backup-secrets/KEY-FILE \
  --output /opt/meddoc-pro/rebuild/.runtime/offsite-checks
```

The output directory must already exist, operator-owned `0700`. Add `--execute`
only for the approved remote upload/download and isolated restore. The private
`offsite-<run-id>.json` report separately records transport and restore success,
scope evidence, authenticated manifest identity and incomplete failures. Client
stderr and raw authorization responses are never printed.

Recovery also works without a surviving local backup directory:

```bash
rebuild/.venv/bin/python rebuild/ops/offsite_backup.py \
  --config /opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json \
  --download-run-id BACKUP-RUN-ID \
  --manifest-sha MANIFEST-CIPHERTEXT-SHA256 \
  --key-file /opt/meddoc-pro/rebuild/.runtime/backup-secrets/RECOVERED-KEY-FILE \
  --output /opt/meddoc-pro/rebuild/.runtime/offsite-recovery-checks \
  --execute
```

Retain the nonsecret run ID and manifest ciphertext hash with the owner-controlled
recovery instructions outside the VPS. This recovery mode sends **no uploads**.
It still verifies the same narrowly scoped configuration and authenticates all
downloaded bytes before restoration. A new recovery host needs the reviewed
code/dependencies, qualified MinIO client and pinned PostgreSQL image available
locally before the isolated restore can run. This is recovery of the application
database and files, not automatic replacement of the VPS: supplying the reviewed
release, PostgreSQL runtime/image and other host prerequisites requires an
authorized operator. The restore verifies the recorded image ID with local
`docker image inspect` and uses `--pull=never`; a missing or mismatched image
fails without starting a container. The adapter does not provision a host or pull
images as a hidden recovery step.

## Evidence, gaps and release controls

**16 focused fixture tests pass.** They exercise rejection of broader key scope,
wrong endpoints and prefixes, nonprivate configuration, plaintext/key uploads,
wrong keys, traversal, tampering and overwrite attempts; encrypted fake round
trip, download-only recovery, safe command arguments and handoff of downloaded
ciphertext to a mocked restore adapter also pass. Command-contract checks refuse
an absent/mismatched local restore image and require `--pull=never`. These use an in-memory fake
transport. The mocked restore fixture is not a PostgreSQL backup and never starts
a database. Neither these checks nor the installed client's version establish a
live B2 result.

Remaining work after the destination/key arrive:

1. Verify actual scope and owner bucket-privacy evidence; perform a small real
   synthetic encrypted round trip and isolated restore, retaining its report.
2. Repeat recovery using the separately escrowed key and recorded remote
   identifiers. The adapter always reports `vault_recovery_demonstrated=false`;
   only independent evidence of obtaining that copy can establish escrow.
3. Measure RPO/RTO; schedule the agreed 04:30 UTC daily operation and verified
   failure alerts after the first successful round trip. Neither timer nor
   alert delivery is installed by this preparation.
4. Apply a separately reviewed B2 lifecycle rule for the agreed 30-day history,
   accounting for both hiding and deletion of unique run names. The uploader
   continues to lack delete rights.

Public maintenance and synthetic-only processing remain in force. Approved
patient-data agreements, regions, retention and processing controls are required
before this destination may receive real patient data.
