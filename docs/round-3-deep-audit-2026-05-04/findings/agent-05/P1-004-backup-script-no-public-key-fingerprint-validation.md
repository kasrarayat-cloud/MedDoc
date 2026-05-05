---
id: A05-P1-004
title: backup-offsite-sync.sh does not validate age public-key fingerprint — silent key-swap = unrecoverable backups
domain: HIPAA-technical-safeguards
severity: P1
agent: 05
---

## Issue

`infra/backup-offsite-sync.sh:160-201` (`ensure_keypair`) and
`upload_encrypted` blindly read `/etc/meddoc/offsite-backup-public.age`
and pass its content to `age --recipient`. There is **no fingerprint
check** against a known-good value.

```bash
# Line 242
age --encrypt --recipient "$(cat "$PUBLIC_KEY")" --output "$enc_path" "$dump_path"
```

Failure modes:

1. **Silent key swap.** If an attacker (or a misguided operator)
   replaces `/etc/meddoc/offsite-backup-public.age` with their own age
   public key, every subsequent backup is encrypted to the attacker.
   The script logs `INFO: encrypting ...` and the backup succeeds —
   nothing alarms.

2. **Fall-through to LOCAL key generation.** Lines 167-201: if
   `$PUBLIC_KEY` is missing, the script auto-generates a NEW keypair
   on the VPS and writes the private key to `/etc/meddoc/offsite-
   backup-private.age`. Comments warn this should "NEVER fire in
   Phase 6.2 production" but the safeguard is a comment, not code.
   Result: a fresh-VPS deploy that forgets to pre-position the offline
   public key produces backups encrypted to a key whose private half
   ALSO lives on the VPS — defeating the whole offsite-with-offline-
   key-custody model.

3. **No comparison to a checked-in fingerprint.** The known-good
   public-key fingerprint should be committed to the repo (it's a
   public key — safe to disclose). On every run, `age-keygen -y`
   the file and compare to the constant. Today neither exists.

The MinIO-side script `infra/minio-offsite-sync.sh:109-116`
(`require_pubkey`) at least fails closed when the file is missing
— but it has the same no-fingerprint-check gap on the present-but-
swapped path.

## Evidence

- `infra/backup-offsite-sync.sh:160-201` — ensure_keypair fall-through
  to local generation.
- `infra/backup-offsite-sync.sh:242` — `cat "$PUBLIC_KEY"` without
  comparison.
- `infra/minio-offsite-sync.sh:109-116` — fails on missing but no
  fingerprint match.
- `docs/RUNBOOK_OFFSITE_BACKUP.md` warns about key custody but does
  not mandate a fingerprint constant.

## Risk

- §164.308(a)(7)(ii)(A) — Data backup plan: backups MUST be
  recoverable. A silently-swapped public key produces blobs that
  cannot be decrypted by the legitimate offline private key — the
  next quarterly restore drill fails AFTER the live data is gone in
  a real DR scenario.
- §164.312(c) — Integrity: tamper resistance includes the encryption-
  key chain.

## Recommended fix

1. **Pin the public-key fingerprint in source.** Add to
   `infra/backup-offsite-sync.sh`:
   ```bash
   readonly EXPECTED_PUBLIC_KEY_FINGERPRINT="age1xxxxxx..."  # full pubkey

   verify_pubkey() {
     local actual
     actual="$(cat "$PUBLIC_KEY")"
     if [[ "$actual" != "$EXPECTED_PUBLIC_KEY_FINGERPRINT" ]]; then
       log "FATAL: public-key mismatch."
       log "  expected: ${EXPECTED_PUBLIC_KEY_FINGERPRINT}"
       log "  actual:   ${actual}"
       exit 1
     fi
   }
   ```
   The fingerprint constant is checked into git; rotation requires a
   code change, which is the correct posture.

2. **Remove the local-generation fall-through entirely.** Replace
   `ensure_keypair` with `require_pubkey` (mirroring the MinIO
   script). If the public key is missing, exit `EX_CONFIG`. The
   "should NEVER fire" comment becomes "CANNOT fire."

3. **Apply the same fingerprint check to `infra/minio-offsite-
   sync.sh`** so both backup paths fail-closed identically.

4. **Add a runbook step** for fingerprint rotation: when the operator
   rotates the offline keypair, they update `EXPECTED_PUBLIC_KEY_
   FINGERPRINT` in the repo, deploy, and copy the new public key to
   `/etc/meddoc/`. The two-step requirement is the integrity guarantee.
