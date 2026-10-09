# Preserve the expired offsite observation and rebind one reviewed control hash

The existing offsite renewal route refuses a stale control-source binding.
Commit `9f24a444faf4edf915272b3c72b857f55fe77afb` changed only the operation
clock default and resolves that clock at construction. Every request still
checks the actual policy expiry. The allocation companion retained the previous
hash; the other six control hashes still match.

The owner's current instruction authorizes completing covered backup preparation
steps. This narrowly scoped repair changes only that companion's one control
hash after exact source proof and complete CI. It preserves the original
companion, prospective intent, policy bytes and expired observation, quotas,
budget ledger, renewal records, failure evidence and running application PIDs.
It neither renews the account observation nor grants provider authority, changes
credentials, sends requests or changes any service or another project.

Expected delta: exactly one atomic replacement of
`rebuild/.runtime/backup-secrets/offsite-allocation.json`, containing only the
recorded hash change below. The original bytes and metadata are retained first
under the protected continuation directory. An unexpected difference refuses.
No automatic reset or rollback follows a partial failure.

After this technical repair, offsite network admission remains `policy_expired`.
A fresh bounded owner-desktop account observation and temporary-key revocation
are separate prerequisites. This declaration approves no expired ticket reuse,
new observation, extra capture, remote upload or restore drill.

<!-- quillmd-offsite-control-rebind-contract-v1 -->
```json
{
  "version": 1,
  "operator_path": "/opt/meddoc-pro/rebuild/.runtime/doctor-acceptance-20261009/backup-soap-review-v1/reviewed-companion-only-rebind-v1.py",
  "operator_sha256": "d04cca301709e0b67411d06a31954e9703fe0a39122289bb2f666834e38133d7",
  "allocation_before_sha256": "a8e8c3e4af1002065f7e34d21e00d19a26db8ac9da42cfb3e02b5e8413fcf84d",
  "allocation_after_sha256": "6fa7333fca3bd8c0e202c956cd4076c090b4af9b6160dfe5b5037aa0ed5c9d7e",
  "policy_sha256": "742f57d226a44fcb2d0b764e9e9febec00458e3dbee92bd9eafa9bb3d96df7b2",
  "source_change_commit": "9f24a444faf4edf915272b3c72b857f55fe77afb",
  "old_control_sha256": "aa4ae4675c38641e415596750e2f4b33fc7b128691f8fa6715e21feb8f8a21e0",
  "new_control_sha256": "a923950de95108a33b746f95a33e64d49bd63079b490c25a96835773fb77f237",
  "no_expiry_extension": true,
  "no_provider_calls": true,
  "no_ledger_change": true
}
```
