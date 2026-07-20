# TranscribeMD MFA secret encryption and migration

Status: technical implementation only. Production key provisioning, database
backfill, recovery-code retirement, and rollback acceptance are human gates.

## Steady-state contract

`users.mfaSecret` stores only a `qmfa:v1` envelope. A random 256-bit data key
encrypts each Base32 TOTP secret with AES-256-GCM. The active keyring key wraps
that data key with a second AES-256-GCM operation. Both layers authenticate the
exact user ID, envelope version, key ID, and layer purpose as AAD. The database
contains the key ID, nonces, wrapped data key, ciphertext, and authentication
tags—never plaintext key material.

The external keyring file has this strict shape:

```json
{
  "version": 1,
  "keys": [
    {
      "id": "reviewed-key-id",
      "keyBase64Url": "<canonical-base64url-encoding-of-exactly-32-random-bytes>"
    }
  ]
}
```

An approved secrets operator must create it outside the repository and any
deployment logs, set ownership to `root:1001`, and mode to exactly `0440`.
`MFA_SECRET_KEYRING_FILE` must be its absolute host path and
`MFA_SECRET_ACTIVE_KEY_ID` must name an entry. Compose bind-mounts that same
path read-only only into `transcribe-md` and `template-twin-admin-app`. The
worker, release-control process, audit dispatcher, email dispatcher, legacy
MedDoc application, and browser receive blank values and no mount.

New enrollment always writes ciphertext. Normal production startup uses
`MFA_SECRET_LEGACY_READ_MODE=strict`; plaintext, wrong-user, unknown-key,
malformed, or tampered values fail closed with a fixed message and no key or
ciphertext logging.

New recovery codes contain 140 unbiased random bits and use versioned
`qmfa-recovery:v2:sha256` verifiers. Unversioned legacy verifiers are rejected.
They cannot be upgraded because the one-way digest cannot acquire entropy;
they must be retired and replaced through a controlled physician recovery-code
regeneration workflow.

## Bounded migration and rehearsal

Do not run this procedure until a disposable restore has proved the backup,
the exact compatible image has passed independent review, and Operations has
accepted the session/email side effects.

1. Make the reviewed keyring available to both app containers. Preserve the
   old and new wrapping keys in the file throughout migration and rollback.
   The CLI also requires explicit `MFA_SECRET_ACTIVE_KEY_ID` and
   `MFA_SECRET_KEYRING_FILE` values before it will inspect a database. It forces
   production validation of an absolute, nonsymlink `root:1001`/`0440` file;
   an unset `NODE_ENV` can never select the development ephemeral-key fallback.
2. Make this envelope-compatible image the rollback target before changing any
   row. An older image that understands only Base32 plaintext is not a valid
   rollback target after backfill.
3. Rehearse against a restored disposable database using synthetic identities.
   Supply that reviewed restore URL only through the dedicated
   `MFA_SECRET_BACKFILL_DATABASE_URL` secret environment variable, then run
   `npm run mfa-secret:backfill -w transcribe-md` with no apply variables. The
   utility rejects an absent dedicated URL and rejects any different ambient
   `DATABASE_URL`; it assigns the dedicated value before constructing the
   database client. It also rejects an absent or invalid external keyring
   before importing that client. It is dry-run by default, queries only
   MFA-bearing or enabled rows, and reports counts/digests only—never IDs,
   emails, secrets, ciphertext, key IDs, file paths, credentials, or database
   diagnostics.
4. Review the exact `candidates`, `candidateManifestSha256`,
   `invalidStoredSecrets`, plaintext, and legacy recovery-verifier counts, plus
   `incompleteEnabledEnrollments`. The manifest is a domain-versioned SHA-256
   review binding over sorted candidate identity and categorical/count state;
   it contains no raw secret, ciphertext, key ID, or verifier value. The latter
   uses one fixed census instant and includes any enabled account with a
   missing/invalid secret or null, invalid, or future verification time. Any
   invalid or incomplete enabled state is a blocker requiring human account
   recovery; apply mode reports counts only, refuses it, and never auto-repairs
   the account.
5. If uninterrupted login during production backfill is required, set all
   three values and recreate both app containers:
   - `MFA_SECRET_LEGACY_READ_MODE=backfill-v1`
   - `MFA_SECRET_LEGACY_READ_UNTIL=<canonical UTC timestamp no more than 24h ahead>`
   - `MFA_SECRET_LEGACY_READ_ATTESTATION=accepted-bounded-mfa-secret-backfill-v1`

   This is the only dual-read mode. It expires automatically; new enrollment
   still writes ciphertext. Omit the mode entirely if a controlled maintenance
   window can keep every login path offline during conversion.

6. Apply only after the dry-run census is approved. Set
   `MFA_SECRET_BACKFILL_APPLY=true`, copy the reviewed candidate count into
   `MFA_SECRET_BACKFILL_EXPECTED_CANDIDATES`, copy the exact lowercase digest
   into `MFA_SECRET_BACKFILL_EXPECTED_MANIFEST_SHA256`, and set
   `MFA_SECRET_BACKFILL_APPLY_ATTESTATION=accepted-reviewed-mfa-secret-backfill-v1`.
   The utility locks one user at a time with two-second lock and ten-second
   statement limits, compares the exact practice, MFA-enabled state,
   verification timestamp, secret, and recovery array from the reviewed
   snapshot, and updates only an unchanged row.
7. Do not suppress database triggers. Changing `mfaSecret` or
   `mfaBackupCodes` advances the existing Template Twin and authentication-email
   authority contracts. Separately and explicitly, each successful row
   transaction deletes every `UserSession` for that user and appends an
   immutable `MFA_CREDENTIALS_MIGRATED` audit receipt; either failure rolls the
   credential update back. The utility reports only the aggregate session
   count. Warn physicians that every affected account must reauthenticate and
   that every legacy recovery code is retired.
8. Apply completes successfully only after a fresh MFA-bearing/enabled census
   finds zero plaintext secrets, zero invalid envelopes, zero incomplete
   enabled enrollments, zero legacy recovery verifiers, and zero concurrently
   changed candidates.
9. Restore `MFA_SECRET_LEGACY_READ_MODE=strict`, blank the deadline and
   attestation, and recreate both app containers. Verify plaintext login denial
   and normal encrypted TOTP/recovery login before ending the window.

The production apply step remains blocked on approved credentials, a reviewed
dry-run count, backup/restore evidence, a compatible rollback image, and named
Operations/Privacy ownership. Codex must not provision the key or execute the
production backfill.

Pre-backfill backups are not remediated by the live-row conversion: they may
still contain plaintext TOTP secrets and unversioned low-entropy recovery-code
verifiers. Operations and Privacy must classify those restore points and
either retain them under the approved legal-hold/retention policy or securely
expire them when that policy permits. Record this as residual sensitive data;
never describe old backups as encrypted by the backfill. After conversion,
create and restore-rehearse a new backup. That rehearsal must prove the MFA
keyring is separately escrowed, access-controlled, recoverable at the restored
application exact SHA, and never embedded in the database backup itself.

## Rotation and rollback

For key rotation, add the new key without removing any existing envelope key,
change only `MFA_SECRET_ACTIVE_KEY_ID`, and recreate both app containers. New
envelopes use the new key; prior envelopes remain decryptable by their embedded
key ID. Retire an old key only after a separately reviewed zero-reference
census and restore rehearsal.

Rollback during or after backfill must use an envelope-compatible image with
the same keyring and legacy-mode semantics. Keep Template Twin disabled if the
application rollback is otherwise necessary. Never roll back to a pre-envelope
image after any ciphertext is committed. If the database itself must be
restored, use the recorded restore point and reconcile post-backup enrollment,
session revocation, recovery-code retirement, and auth-email cancellations
before reopening authentication.
