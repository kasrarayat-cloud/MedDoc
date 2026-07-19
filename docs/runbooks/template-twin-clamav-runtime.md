# Template Twin private ClamAV runtime

Status: technical implementation evidence only. This document does not approve
production malware-scanning operations or close release blocker B-006.

## Runtime boundary

Template uploads are streamed to `clamd` through a Unix-domain socket. The
production and synthetic-QA Compose definitions do not publish or configure a
ClamAV TCP listener. The scanner's dedicated network contains no application,
database, queue, or object-storage service and exists only for outbound
signature updates. A named socket volume is mounted into only two containers:
the scanner and the `transcribe-md` web runtime that accepts template uploads.
It is read-only in the web runtime, mode `0660`, and accessible through the
explicit supplementary scanner group. The worker does not receive the socket.

`transcribe-md` does not depend on scanner health for process startup. Scanner
failure therefore leaves ordinary physician workflows available while Template
Twin admission fails closed with the source still quarantined.

The image is pinned to the Linux/amd64 OCI manifest:

```text
clamav/clamav:1.4.5@sha256:48eaad9644475c2d466ce6d4ba2da892dbd4dcd47713201d31b665364655cc3c
```

It was resolved from the official `clamav/clamav:1.4.5` tag on 2026-07-19 with
`docker manifest inspect --verbose clamav/clamav:1.4.5`. The returned manifest
identifies ClamAV 1.4.5 and OCI config digest
`sha256:c243a8993835735a02dd606540e238647128a39693f9ca90a7627c1e7d7944d2`.
Deployment must pull by the recorded manifest digest, never by the mutable tag
alone. A future engine update requires a new digest record, runtime contract,
and independent review.

## Readiness and bounded work

Official signature files persist in a dedicated production volume. FreshClam
checks hourly. Startup refreshes synchronously when the daily signature file is
older than 48 hours; readiness requires both a responsive private socket and a
daily signature file no older than 48 hours. `FailIfCvdOlderThan 2` provides an
additional engine-side stale-database refusal.

Every successful health check atomically publishes a group-readable readiness
lease beside the socket. The application mount is read-only. Admission checks
that lease before and after each scan, requires a recent health check, verifies
the signature-file age against the configured limit, and binds the lease's
signature version to clamd's own version response. A failed health check removes
the lease; a stopped health-check loop leaves a lease that expires locally in
the application. A responsive socket alone is therefore not admission-ready.

The admission route accepts at most 10 MiB. clamd permits a 12 MiB input stream
and separately bounds expanded scan bytes, individual file size, recursion,
file count, partitions, regular-expression work, queue depth, threads, and scan
time. `AlertExceedsMax yes` makes an exceeded scanner limit a finding rather
than a clean result. Encrypted archives/documents and OLE macros are findings;
the DOCX package inspector applies its separate structural rejection policy
after the malware gate.

The 1536 MiB memory limit and two-thread setting are conservative deployment
defaults, not production capacity evidence. Production concurrency, update
reload behavior, alert delivery, and named operational ownership remain release
gates.

## What the attestation proves

The application constructs an ordered JSON receipt containing engine/signature
versions, exact source SHA-256 and length, verdict, hashed threat name when
present, and scan time. `attestationSha256` is the SHA-256 of those exact JSON
bytes. PostgreSQL now reconstructs the same ordered bytes and rejects any row
whose hash differs. Existing quarantine constraints and certification triggers
bind that consistent receipt to the immutable quarantined object identity.

This hash is an integrity checksum, not a digital signature or MAC. Database
validation proves internal receipt consistency; it cannot independently prove
that clamd executed, that Cisco published a signature, or that the runtime was
not compromised. Scanner authenticity depends on the pinned image, private
socket boundary, controlled signature updater, runtime readiness, immutable
source binding, audit evidence, and production monitoring. Those operational
claims require independent evidence and human ownership.

## Verification

Static configuration and canonical-hash tests run in the focused Template Twin
unit suite. The disposable runtime contract starts only the QA scanner service,
waits for signature-fresh readiness, proves there is no published port, connects
through the read-only socket as the web runtime UID/group, accepts a clean
synthetic string, rejects the standard EICAR test string, and removes its
isolated volumes on exit:

```sh
./scripts/template-twin-clamav-runtime-contract.sh
```

The PostgreSQL contract must run only after the complete migration history has
been applied to a disposable database. It uses a real canonical clean receipt,
proves certification succeeds, and proves a tampered 64-character attestation
is rejected:

```sh
psql "$DISPOSABLE_DATABASE_URL" \
  -f apps/transcribe-md/scripts/template-twin-quarantine-certification-contract.sql
```

Do not place document bytes, credentials, patient-like content, or production
database URLs in either verification path.
