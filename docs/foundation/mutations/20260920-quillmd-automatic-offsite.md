# Declaration — bounded automatic encrypted offsite backups and recovery preparation

Authorized by the owner on 2026-09-20. Baseline repository
`bf95335d058a34a0387393c0cbc43ebc3819d051`; running doctor/admin/worker
`8aa1d1d4efe090d6f0e6e1bf7d594375ddca9940`. Preserve all application records,
balances, historical evidence, public maintenance, synthetic-only operation,
administrator MFA and inactive reviewer access. No application restart or deploy.

## Expected delta

Install only `quillmd-fresh-offsite.service` and `.timer` from reviewed source,
with private state at `rebuild/.runtime/automatic-offsite/`. The proposed calendar
is 05:00 UTC after the existing 04:30 UTC local capture. Leave the existing local
backup and alert units untouched. No local capture, key rotation, key provisioning,
credential transfer, bucket/retention/cap/payment change or deletion is part of
installation. Preserve the exact installed three-capability B2 configuration.

Before advancing source used by the existing alert timer, seed clearly attributed
historical remote/readback/restore evidence from the completed qualification;
record pending configuration and unverified independent custody. The alert script
will pick up reviewed monitoring changes on its next existing invocation. A
prepared, disabled feature must not generate a new unsolicited failure email.
Real failed attempts and stale enabled backups use the already approved recipient.
Use fixture transport for failure routing checks; distinguish it from actual email.

Enable recurrence only after protected policy records a current permitted storage,
download and request envelope and an exclusive allocation within unchanged account
caps. The scoped runtime key cannot establish account-wide caps/usage. Historical
empty-account observations are not current capacity proof. Without sufficient
evidence, install the timer disabled and stop before provider calls. An operator's
manual guarded refusal is not a completed backup or a timer-triggered run.

Eligible activation must first complete one controlled invocation of the installed
service, record verified completion/readback, and then enable its timer. Use the
reviewed installer through `scripts/run-ruled-mutation.sh`; compare existing host
units, protected configuration and application processes before/after. Rollback
only disables/stops the new offsite timer/service; preserve uploaded objects and
all attempt evidence. No other systemd unit or shared service may change.

Runtime scope stays exactly the approved bucket and `quillmd-fresh/synthetic/`.
Upload only authenticated completed local snapshots, with encrypted manifest last.
Reserve request/download allowance before I/O, inventory all retained versions,
refuse capacity overflow, and preserve incomplete attempts for safe resumption.
No pruning: the installed key cannot delete and no retention policy is authorized.
Bound every run to 900 seconds plus systemd shutdown allowance; serialize runs.
A partial upload is never a recoverable complete set. Daily execution performs
SHA-256/authenticated readback; isolated restores remain separately recorded.

## Recovery and verification

Keep backup Fernet decryption material, B2 retrieval credential and VPS disk-unlock
material distinct. Prepare metadata and secure handoff instructions without placing
secrets in source, logs, chat or plaintext documents. Do not claim independent
custody from any second VPS copy. When an actual independently retrieved copy is
available, use it explicitly for a download-only isolated restore, with no fallback
to the live key or original plaintext. Compare that snapshot's own manifest.
Until then, retain prior real restore proof and mark this custody drill pending.

Run focused isolated tests for concurrent entry, interrupted upload/resume,
corrupt/missing objects, wrong key, capacity refusal, monitoring and installer
boundaries. No repeat of the already completed paid/provider campaigns or original
qualification. Follow repository PR/CI and exact source gates before installation.
Keep initial SHA-1 metadata comparison failure: provider values remain unverified;
verified client SHA-256 readback must not be recast as provider SHA-1 verification.

Evidence: `rebuild/.runtime/automatic-offsite-20260920/`; checkpoint updates are
additive. Public launch and whole-host-loss recovery are not approved by this act.
