# MFA credential backfill and restore rehearsal

Status: **PASS on disposable synthetic infrastructure; production not authorized**

- Working branch: `fix/template-twin-provider-ownership-b017-v1`
- Committed starting head: `db1cab904ac5c8d6c7f25878f59d71e1b094a223`
- Final implementation head: pending additive commit and exact-head review
- PostgreSQL container: `meddoc-auth-exact-pg-20260719`
- Final source database: `meddoc_auth_mfa_v8b_test_20260720`
- Restored database: `meddoc_auth_mfa_v8b_restore_test_20260720`
- Corpus: reserved synthetic identities only; no PHI and no provider egress

## Reproduced fail-closed defects and additive repairs

1. Prisma rejected a `pg_advisory_xact_lock` result of PostgreSQL type `void` before any row changed. The lock expression now returns a supported text value while preserving global → practice → user ordering.
2. PostgreSQL `TIMESTAMPTZ(6)` values lost microseconds through a JavaScript `Date` round trip, causing an unchanged locked row to be classified as changed. The census, manifest, and locked reread now bind one canonical UTC six-digit timestamp, and the write targets only the already exact-compared `FOR UPDATE` identity.
3. The legacy classifier accepted a 10-byte Base32 secret rejected by otplib. Canonical unpadded Base32 decoding now enforces the same 16–64 decoded-byte guardrails as the authentication verifier.

Each failed apply rolled its transaction back. Rechecks showed plaintext count 1, encrypted count 0, session count 1, pending email-change count 1, and migration-audit count 0 before the corrected rehearsal was started in a fresh database.

## Fresh installation and negative gates

- Fresh install applied exactly 96 migrations.
- Unfinished or rolled-back migrations: 0.
- A deliberately invalid legacy secret produced `BLOCKED_INVALID_STORED_SECRET` with invalid count 1 and no changes.
- After repairing only that synthetic fixture, a separate incomplete enabled enrollment produced `BLOCKED_INCOMPLETE_ENABLED_ENROLLMENT` with incomplete count 1 and no changes.
- After repairing only the incomplete synthetic fixture, the reviewed dry run reported one candidate, zero invalid values, zero incomplete enrollments, and manifest `47dacdbfb63487da2b8fb1aed142f0a9c0c7dfee876f10416dcc5a41303bdf4b`.

## Apply and transactional effects

Apply verdict: `PASS`.

- Updated candidates: 1
- Concurrently changed candidates: 0
- Sessions revoked: 1
- Encrypted secrets after apply: 1
- Plaintext or invalid secrets after apply: 0
- Incomplete enabled enrollments after apply: 0
- Legacy recovery verifiers after apply: 0
- Remaining candidates: 0
- Empty candidate manifest: `4b54fec875b7a30c809c0dcc0fd0675e67457b7e26e635a188d1331a91a93f4e`
- Immutable `MFA_CREDENTIALS_MIGRATED` audit receipts: 1
- Pending email changes cancelled as `ACCOUNT_SECURITY_STATE_CHANGED` with recipient removed: 1

A fresh production-mode process with the external read-only keyring proved: encrypted TOTP verification succeeds, strict-mode plaintext verification fails, and wrong-owner envelope verification fails. No secret, token, ciphertext, verifier, email, or user identifier was printed.

## Backup and restore

- Custom-format dump size: 1,017,774 bytes
- Synthetic dump SHA-256: `39ddf6e0a00745f42760d366093b1757dd91887b826feaef52a70208a0a0ad00`
- Restore completed with `--no-owner --no-acl --exit-on-error` into a new database.
- Restored migrations complete/unresolved: 96/0.
- Restored encrypted row, audit receipt, session revocation, and email cancellation counts matched the source.
- A separate production-mode process verified the restored encrypted TOTP and both plaintext/wrong-owner denials.
- Restored dry run reported encrypted 1, plaintext 0, invalid 0, incomplete 0, legacy recovery 0, candidates 0.

The temporary dump and temporary keyring file were removed after the proof. The two disposable synthetic databases remain for audit/review; neither is staging or production. Production backup/restore authority and production key escrow remain human/operations gates.
