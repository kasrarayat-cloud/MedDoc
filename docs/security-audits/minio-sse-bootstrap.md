# MinIO SSE-S3 bootstrap — 2026-05-06

- PR: `feat/minio-sse-s3-finalize` (PR-M)
- Closes: BAA-relevant gap "encryption at rest in object storage" — pre-PR-M
  the only protection for PHI in MinIO was volume-level disk encryption
  (Phase 6.1 LUKS, host filesystem). SSE-S3 adds per-object server-side
  encryption with a rotatable master key.
- Scope: single-tenant pre-pilot. KES (per-object KMS) deferred —
  see "Why not KES" below.

## What landed

- `MINIO_KMS_SECRET_KEY` env var on the `minio` compose service.
  Format: `<key-name>:<base64-32-bytes>`. Value lives only in
  `/opt/meddoc-pro/.env` (gitignored). Master key NAME this PR ships
  with: `quillmd-master-key-1`.
- Bucket-level default SSE-S3 encryption set on the only PHI-bearing
  bucket: `transcribe-md-audio`. Every PUT after the bootstrap is
  encrypted server-side with AES-256, transparently decrypted on GET.
- `mc stat` confirms `Encryption: SSE-S3` on a fresh test object.
- `scripts/minio-enable-sse.sh` (Round 3 PR-C, idempotent) is the
  documented entry point — re-runnable on every restore / fresh deploy.

## Why SSE-S3 (not SSE-KMS)

Round 3 PR-C explicitly chose SSE-S3 over SSE-KMS for this scope. The
rationale (from `scripts/minio-enable-sse.sh` header, preserved here for
durability):

> SSE-S3 is the simpler-but-still-HIPAA-OK choice — keys are managed
> by MinIO itself rather than an external KMS service. SSE-KMS is
> overkill for a single-tenant pre-pilot; revisit when we move to
> multi-tenant or a HIPAA-eligible-cloud BAA mandates customer-managed
> keys.

SSE-S3 with a named master key (`quillmd-master-key-1:<random-32B>`):

- Same AES-256 server-side encryption semantics as SSE-KMS from a BAA
  POV — every object is encrypted at rest with a key the operator
  controls.
- One env var, one bucket-level toggle, no extra container.
- Rotatable via env swap (see "Rotation runbook" below).

## Why not KES (deferred — NAB rationale)

PR-M was originally scoped to add the MinIO Key Encryption Service
(KES) sidecar — full external-KMS posture with mTLS between MinIO
and KES, file-backed master key, KES-managed rotation policies. The
NAB investigation surfaced two reasons to defer KES:

1. **Prior art rejected it.** Round 3 PR-C had already considered +
   documented the SSE-KMS-vs-SSE-S3 tradeoff and chose SSE-S3 for the
   pre-pilot scope. The PR-C script was authored ready to use; it just
   needed `MINIO_KMS_SECRET_KEY` populated to actually run.
2. **Operational debt without justification.** KES adds a fourth
   container to keep healthy, an mTLS cert chain to renew, and a
   master-key file under `infra/kes/` to handle out-of-band. The
   marginal security gain at single-tenant pre-pilot scale is small;
   the operational surface is large.

KES becomes the right answer when one of these flips:

- Multi-tenant deployment where per-tenant keys + audit trails are
  legally required.
- HIPAA-eligible-cloud BAA mandates customer-managed keys (CMK).
- Compliance audit asks for documented external-KMS posture.

When that day comes, KES adoption is a clean swap — `mc encrypt rotate`
re-keys the buckets, and the `MINIO_KMS_SECRET_KEY` env var is replaced
by the `MINIO_KMS_KES_*` chain. Existing objects re-encrypt
incrementally on the natural write cycle (or via a one-shot sweep).

## Master key rotation runbook

Run during a low-traffic maintenance window (worker pause optional —
`mc encrypt rotate` is non-blocking but generates write load).

1. **Generate the next-key value** (host shell, never echoed to chat
   or logs):

   ```bash
   echo "MINIO_KMS_SECRET_KEY=quillmd-master-key-1:<old-b64>,quillmd-master-key-2:$(openssl rand -base64 32)" >> /opt/meddoc-pro/.env.rotate
   ```

   MinIO accepts a comma-separated list — both `-1` and `-2` are
   loaded, so existing objects (encrypted with `-1`) stay readable
   while new PUTs use whichever key the bucket policy points at.

2. **Update the bucket policy to write with the new key:**

   ```bash
   docker compose exec minio mc encrypt set sse-s3 \
     --kms-key quillmd-master-key-2 local/transcribe-md-audio
   ```

3. **Re-encrypt existing objects** (optional, takes longer at scale):

   ```bash
   docker compose exec minio mc encrypt rotate \
     local/transcribe-md-audio --new-key quillmd-master-key-2
   ```

   Or wait for the natural write cycle — once every object has been
   re-PUT (e.g. during a planned re-process of older visits), `-1` is
   no longer referenced.

4. **Verify no object still references `-1`:**

   ```bash
   docker compose exec minio mc stat --recursive local/transcribe-md-audio \
     | grep -E "Encryption|Key" | sort -u
   ```

   Every line should reference `quillmd-master-key-2`.

5. **Deprecate `-1`:** swap `.env`'s `MINIO_KMS_SECRET_KEY` to only
   include `-2` (drop `-1` from the comma-separated list). Recreate
   minio. If any object is still keyed to `-1`, GETs will fail —
   re-add `-1` and re-run step 3 before retrying.

## Legacy objects (pre-PR-M)

SSE-S3 only encrypts NEW PUTs. Objects that landed in
`transcribe-md-audio` before PR-M went live are still on disk in the
clear (volume disk encryption only). The audit bucket today is
nearly empty (T-M12 cleanup is active), so the legacy fleet is small.

Async migration on the next maintenance window:

```bash
# One-shot re-PUT of every object with the SSE-S3 default applied.
# `--md-preserve` keeps Content-Type + custom metadata intact;
# the implicit re-PUT carries the bucket's SSE-S3 default.
docker compose exec minio sh -c '
  mc cp --recursive --md-preserve \
    local/transcribe-md-audio/ /tmp/sse-rewrite/ &&
  mc cp --recursive --md-preserve \
    /tmp/sse-rewrite/ local/transcribe-md-audio/ &&
  rm -rf /tmp/sse-rewrite
'
```

Track via `mc stat --recursive local/transcribe-md-audio | grep Encryption`
— every line should report `SSE-S3` after the sweep.

## Verification log (PR-M ship)

- `docker compose exec -T minio mc encrypt info local/transcribe-md-audio`
  → `Auto encryption 'sse-s3' is enabled`
- Test object PUT/STAT/RM round-trip:
  - PUT `test/pr-m-sse-verify-<UTC>` (39 B fixture)
  - STAT reported `Encryption: SSE-S3`
  - RM cleaned up
- MinIO container healthy post-recreate; uptime resets cleanly.
- Worker (`transcribe-md-worker`) pipeline smoke: existing visits
  process end-to-end with the new bucket policy (PUTs are
  transparently encrypted; GETs are transparently decrypted).

## Things this PR does NOT change

- Worker code: unchanged. Bucket-level default encryption means the
  worker doesn't send per-request encryption headers; MinIO applies
  SSE-S3 transparently.
- Volume-disk encryption: untouched. The `minio_data` docker volume
  still lives on the unencrypted root filesystem (Phase 6.1 LUKS only
  covered postgres). Phase 6.3 (MinIO data dir under
  `/mnt/minio-encrypted`) remains a follow-up.
- Backup encryption: untouched. The offsite-sync flow
  (`infra/minio-offsite-sync.sh`) wraps writes with age encryption
  separately — independent of SSE-S3, complementary.
