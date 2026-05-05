---
id: A05-P0-001
title: MinIO audio bucket — no SSE, on unencrypted root disk (audio PHI plaintext at rest)
domain: HIPAA-technical-safeguards
severity: P0
agent: 05
---

## Issue

The `transcribe-md-audio` MinIO bucket holds every uploaded audio file
and dictation recording — raw doctor-patient audio = PHI under
§160.103. The bytes are stored:

1. **Without MinIO server-side encryption (SSE).** `apps/transcribe-md/
   src/lib/minio.ts:69-80` (`putAudioStream`) calls `client.putObject`
   passing only `Content-Type`. No `ServerSideEncryption`,
   `SSECustomerKey`, or `x-amz-server-side-encryption` header is set.
   The bucket itself is created in `ensureBucket()` (lines 53-65) with
   no policy ApplyServerSideEncryptionByDefault.

2. **On the unencrypted host root disk.** `docker-compose.yml:189-190`
   binds `minio_data` to `/var/lib/docker/volumes/meddoc-pro_minio_data/
   _data`. `lsblk` shows `/dev/sda2 → /` (296G, no LUKS). Only `/dev/
   mapper/pg-encrypted → /mnt/pgdata-encrypted` (974M) is encrypted.
   `docker volume inspect meddoc-pro_minio_data` confirms the
   mountpoint sits on `/`.

Net effect: every `*.webm` audio uploaded by a doctor is plaintext on
sda2.

## Evidence

- `/opt/meddoc-pro/apps/transcribe-md/src/lib/minio.ts:69-80` — putObject
  call without SSE options.
- `/opt/meddoc-pro/docker-compose.yml:189-190` (minio service) and
  `lsblk` / `df -h /var/lib/docker/volumes/meddoc-pro_minio_data` —
  root disk unencrypted.
- `/opt/meddoc-pro/docs/HIPAA_COMPLIANCE.md` — h8 "Mitigated (pending
  operator migration)" but only covers Postgres, not MinIO. The MinIO
  case is invisible in the matrix.

## Risk

- §164.312(a)(2)(iv) — Encryption & decryption: PHI at rest must be
  encrypted (or accepted-risk documented). Audio is the most-sensitive
  PHI surface QuillMD touches; unencrypted disk = breach exposure if
  the VPS is decommissioned, snapshotted by the host, or the disk is
  imaged for forensics.
- VPS host is single-tenant Zap Hosting; loss of physical disk control
  means raw patient audio is exfiltrable.

## Recommended fix

Two paths, both required:

1. **Enable MinIO SSE-S3 default encryption** on the `transcribe-md-audio`
   bucket: `mc encrypt set sse-s3 quillmd-minio/transcribe-md-audio`
   AND set `ApplyServerSideEncryptionByDefault` in the bucket policy so
   every PUT inherits it. Verify with `mc admin info` showing KES /
   built-in KMS configured.

2. **Move the MinIO data volume onto the encrypted LUKS mount.** Same
   pattern as Postgres (h8) — bind-mount `/mnt/pgdata-encrypted/minio`
   (after expanding the loop file from 1 GB to a production size — see
   adjacent finding) or provision a separate LUKS volume for MinIO.
   Update `docker-compose.yml` minio.volumes accordingly.

Add a row to `docs/HIPAA_COMPLIANCE.md` for "h8b — MinIO encryption at
rest". Block Phase 6.2 activation until this is closed; the offsite
encrypted backup doesn't help if the live store is plaintext.
