# Declaration — one bounded encrypted B2 round trip and isolated restore

The owner authorized this operation on 2026-09-20. Preserve the running rebuild,
its records, balances and audit history, synthetic-only operation, public
maintenance, administrator MFA and inactive reviewer access. This declaration
permits no application deployment, provider clinical request, email or purchase.

## Evidence before execution

Repository baseline is `2b100b2e478e99e499844af62d9dab5955209b54`. Doctor/admin
health reports and the unchanged worker process independently preserve application
release `8aa1d1d4efe090d6f0e6e1bf7d594375ddca9940`. Evidence is private under
`rebuild/.runtime/b2-offsite-20260920/`; it contains no new clinical information.

The owner approved private bucket `quillmd-private-backups-20260920`, bucket ID
`e5d31ce87af3b0f0a00a0916`, endpoint
`https://s3.us-west-004.backblazeb2.com`, region `us-west-004`.
The prefix is exactly `quillmd-fresh/synthetic/`. SSE-B2 is owner-confirmed enabled;
Object Lock is disabled and the lifecycle keeps all versions. These are retained
settings, not authority to modify them.

The initial broad key failed the existing guard. The owner reports its revocation
and that of the desktop provisioning key; both subsequently returned401. The
master key was unchanged. Replacement provisioning is complete on the desktop.
No provisioning credential is requested or installed on the VPS.

Before installation independently authenticate the protected replacement with
Native API v4. Require the exact sole bucket, endpoint, prefix, capabilities
`listFiles`, `readFiles`, `writeFiles` and no groups administration. Existing
`offsite_backup.py` already uses v4. Never weaken its checks or add discovery
permissions. Preserve any failed receipt/authentication evidence.

At16:35UTC the owner reports authenticated account totals:0bytes stored against
10GBcap,0bytes downloaded against1GBdailycap. This is owner-desktop evidence, not
a VPS account-wide query. Use it only for this prompt bounded qualification;
reassess if time or intervening activity makes it stale. Do not increase caps.

## Exact allowed delta

Install only the accepted key through the existing protected
`rebuild/.runtime/backup-secrets/b2-offsite.json` contract, claude0600 under0700.
Preserve other configuration. Remove only the specifically recorded temporary
SFTP authorization after verified installation, preserving all other keys and
sessions. Remove only the verified temporary handoff credential files after
successful installation, retaining redacted receipt hashes and history. No SSH
policy change, password unlock, master-key replacement or unrelated cleanup.

Use the existing authenticated historical backup
`20260920T095332Z-a9da0017`:44 encrypted objects,14,422,252bytes total,
35tables225615rows42referenced files. Manifest ciphertext SHA256:
`910153b7d671bbd147ab5a840e5a9e6c7a3f4d8fa3913046c852cfc67c062ace`.
It does not claim to contain later sessions or records. Recheck local sizes and
hashes before execution. No new source snapshot is required for this qualification.

Publish exactly this authenticated encrypted object set under the approved prefix
and the adapter's run/manifest-hash namespace. Publish the encrypted manifest last.
Do not upload plaintext, encryption keys, service credentials, unrelated files or
private operational reports. Expected payload is14,422,252bytes each way,44 PUTs
and44 GETs plus bounded client metadata requests. Use explicit-bucket operations.
No additional backup, retention schedule, delete, hide or bucket-setting operation.

After the reviewed declaration is committed, invoke the existing adapter through
`scripts/run-ruled-mutation.sh`, with absolute protected config, backup, key and
output paths and `--execute`. A prior run without `--execute` is preparation only.
Use an exclusive private output directory and retain every incomplete attempt.
Do not blindly repeat a failed upload: an existing version consumes storage.

The adapter downloads and authenticates every object, compares ciphertext and
plaintext hashes, and restores only to its new isolated Docker container using
the authenticated pinned local PostgreSQL image. Network none, no published ports,
read-only root, memory-limited nonswapping tmpfs; no workers or provider actions.
Require all35table hashes,42file hashes and financial/scope invariants to match.
Never restore over the running database. Explicitly inspect nested cleanup fields
and confirm the exact restore container is absent before claiming cleanup passed.

## Judgment and failure handling

Keep transfer, scope verification, installation, remote upload/readback, isolated
restoration and independent recovery-key custody as separate results. A surviving
local encryption key does not demonstrate independent custody; that gate remains
unverified. Do not destroy or replace any encryption/rollback copy.

No code or runtime change is intended. Follow required PR/CI for this declaration;
documentation alone warrants no application restart. Compare health/revisions,
application/worker/SSH process identities and the exact protected sources after
the operation. Preserve database, files, balances and audit history. Stop on any
unexpected delta, retain evidence and repair within the authorized scope. Do not
claim public release, real-patient approval or independent penetration testing.
