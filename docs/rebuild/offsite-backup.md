# Encrypted offsite backup preparation

Current continuation: [2026-09-20 setup and recovery handoff](#2026-09-20-setup-and-recovery-handoff).
The dated preparation below is retained; the addendum distinguishes the now
installed local schedule from still-unverified offsite recovery.

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

## 2026-09-20 setup and recovery handoff

### Verified current state

The designated `b2-offsite.json` is absent, and the application `.env` has no
offsite configuration keys. No B2 authorization, upload or download was attempted.
The current known encrypted backup, `20260920T095332Z-a9da0017`, was authenticated
in memory against its existing key: 35 tables, 225,615 rows, 42 referenced files
and 44 encrypted objects. Every recorded ciphertext and plaintext size/hash
matched. This did not write plaintext or restore a database.

Its manifest ciphertext SHA-256 is
`910153b7d671bbd147ab5a840e5a9e6c7a3f4d8fa3913046c852cfc67c062ace`.
The separate completed **local** restore remains the earlier
`20260920T081236Z-04a49ff8` backup, recorded in
`rebuild/.runtime/restore-checks/restore-c965470cd3de6157/verification.json`.
That restore checked 35 tables, 225,581 rows and 42 files in a networkless
container. Neither result is evidence of offsite recovery.

Evidence for this continuation is in
`rebuild/.runtime/operational-recovery-20260920/offsite-preparation.json` and
`offsite-focused-tests.log`. All **18** focused tests passed, including new
checks that preparation never authorizes/transfers/restores and that missing
configuration cannot contact a provider even with `--execute`. Fake transport
and mocked restore tests remain explicitly simulated.

The 04:30 UTC daily **local** backup timer is now installed. Offsite transfer is
not scheduled. The earlier reference to a 30-day lifecycle rule is historical
preparation, **not authorization to change retention**. This handoff creates no
bucket, subscription, lifecycle policy, delete permission or new schedule.

### One exact external setup action

The selected destination is a private Backblaze B2 bucket in the owner's approved
B2 account, requested name **`quillmd-fresh-synthetic-backups`**, with prefix
**`quillmd-fresh/synthetic/`**. This is a requested name, not a claimed existing
or reserved bucket. Use the existing account's regional S3 endpoint; record its
actual endpoint and region. Any billable capacity/account setup needs owner
approval before provisioning. No alternative-provider decision is being asked.

The owner or an authorized B2 account administrator must:

1. In the B2 console's **Buckets** page, select an existing dedicated private
   bucket. If none exists, explicitly approve its provisioning, then use
   **Create a Bucket**, the requested name above, and **Private**. Leave existing
   lifecycle/retention settings unchanged. Record the actual bucket name, ID,
   S3 endpoint and region shown by that account, plus the approval reference.
2. Create a standard key named `quillmd-synthetic-backup`, scoped to **only that
   bucket** and **only `quillmd-fresh/synthetic/`**, with exactly `listFiles`,
   `readFiles`, and `writeFiles`. Do not provide a master/admin key to the VPS.
   The exact capability list can be set through B2's v4 `b2_create_key` API:
   `bucketIds` must contain one approved ID, `namePrefix` the exact prefix,
   and `capabilities` those three values. Its administrative authorization stays
   with the account administrator. Backblaze documents the v4 request and the
   once-only return of the new application secret in
   [Create Key](https://www.backblaze.com/apidocs/b2-create-key).
3. Using protected SSH/SFTP or the established secret manager, install the JSON
   schema above at
   `/opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json`, owned by
   `claude:claude`, mode `0600`. Parent directory must remain `0700`.
   Set `bucket` to the approved actual name, `bucket_id` to its actual ID,
   and endpoint/region to the provider's values. Never paste keys in chat,
   tracked files, terminal arguments, or reports.
4. Through an authenticated file transfer, put a copy of the existing
   `/opt/meddoc-pro/rebuild/.runtime/backup-secrets/fresh-backup-current-20260917.key`
   into the owner's encrypted recovery vault **outside this VPS and the B2
   account**. Keep the run ID, manifest hash, reviewed release and the recovery
   commands below alongside the recovery instructions. Do not regenerate or
   rotate the key for this test. Record who actually controls the vault and how
   it was retrieved; no independent custodian is presumed to exist.

The B2 documentation warns that some S3 integrations require
`listAllBucketNames`; this adapter deliberately addresses known objects and
supplies its region. The first live test must establish compatibility with the
three selected capabilities. A refusal is evidence to investigate, not authority
to widen them. The provider maps `readFiles` to object reads and `writeFiles` to
object uploads, and distinguishes bucket listing permissions in its
[S3 capability reference](https://www.backblaze.com/docs/cloud-storage-s3-compatible-app-keys).

### Exact operator verification after that setup

Run as `claude` from `/opt/meddoc-pro`. These commands contain no secret values.
The retained known backup is the small representative batch; the source files
are read only. The adapter validates the actual scope through the
[v4 authorization response](https://www.backblaze.com/apidocs/b2-authorize-account)
before sending ciphertext.

```bash
install -d -m 0700 /opt/meddoc-pro/rebuild/.runtime/offsite-checks/20260920-first-roundtrip
rebuild/.venv/bin/python -B rebuild/ops/offsite_backup.py \
  --config /opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json \
  --backup /opt/meddoc-pro/rebuild/.runtime/new-system-backups/20260920T095332Z-a9da0017 \
  --key-file /opt/meddoc-pro/rebuild/.runtime/backup-secrets/fresh-backup-current-20260917.key \
  --output /opt/meddoc-pro/rebuild/.runtime/offsite-checks/20260920-first-roundtrip
```

The first command invocation is local validation. When it succeeds, repeat the
same Python command with `--execute`. This uploads encrypted objects, downloads
them to a new isolated directory, authenticates them and restores the downloaded
database/files in the existing networkless verification container. The report
must show `complete`, `transport_verified`, `restore_verified`, matching table
and file hashes, `network: none`, zero provider actions/workers, and no retained
container. A missing `--execute` result or a local restore is not success here.

For the required separate-key recovery, retrieve the vault copy over the secure
channel into
`/opt/meddoc-pro/rebuild/.runtime/backup-secrets/fresh-backup-recovered-20260920.key`
(`claude:claude`, `0600`), and record authentic retrieval evidence without the
key. Then run the download-only test; it cannot reuse the local source bundle:

```bash
install -d -m 0700 /opt/meddoc-pro/rebuild/.runtime/offsite-checks/20260920-vault-recovery
rebuild/.venv/bin/python -B rebuild/ops/offsite_backup.py \
  --config /opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json \
  --download-run-id 20260920T095332Z-a9da0017 \
  --manifest-sha 910153b7d671bbd147ab5a840e5a9e6c7a3f4d8fa3913046c852cfc67c062ace \
  --key-file /opt/meddoc-pro/rebuild/.runtime/backup-secrets/fresh-backup-recovered-20260920.key \
  --output /opt/meddoc-pro/rebuild/.runtime/offsite-checks/20260920-vault-recovery \
  --execute
```

Do not rerun over a partial attempt or overwrite its evidence; inspect it and
choose a new protected output directory for a justified retry. Vault custody is
recorded separately: the adapter intentionally continues to report
`vault_recovery_demonstrated=false` because it cannot know the origin of a local
key file. Neither successful command changes that field by assumption.

On total VPS loss, recovery additionally requires an authorized replacement
operator/host, the reviewed application source and dependencies, the qualified
MinIO client, and the exact PostgreSQL image from the authenticated manifest.
The restore tool will not pull or silently substitute an image. Store those
nonsecret prerequisites outside the VPS with the instructions; this test does
not provision a replacement host. Host-loss recovery remains pending until the
offsite bytes and actual external key copy have both been exercised.
