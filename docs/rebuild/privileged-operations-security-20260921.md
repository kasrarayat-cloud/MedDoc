# Internal review of privileged operations — September20–21,2026

This supplement covers the operations added after application97597c29 and their
host privilege boundaries. It advances the independent review package; internal
agent review and synthetic probes do not complete the external penetration test.
Exact fixed/installed revisions, CI and final receipts are recorded in the durable
checkpoint and `internal-security-20260920/FINAL-REPORT.md`. No external reviewer
access is activated by this document.

## Entry points and permitted callers

| Entry point | Effective caller and authority | Input boundary |
| --- | --- | --- |
| install_backup_schedule.helper_command, called by backup/alert/offsite installers | Claude operator; existing Docker membership and sudo Docker permission are root-equivalent. Root helper uses pinned local image and generated reviewed Python after chroot. | Reviewed permanent main, exact source hashes, declaration, fixed operations/paths, before/after host comparison. These prevent mistakes/drift, not malicious root. |
| private_storage read/inventory/select | Operator invokes a nonroot UID996/GID988 helper with no extra groups/capabilities, no network, read-only approved storage bind and daemon logging disabled. | Root/device/inode binding; descriptor-relative nofollow opens, regular single-link0600 files,700directories, owner/size/race checks. Application filenames/data remain untrusted. |
| Local backup and automatic offsite services | Claude under fixed systemd units; operator access includes Docker and protected backup configuration. Application identity is separate. | Completed local backup authentication, restricted remote identity, canonical lock, shared reservations, finite allocation/policy and complete-set publication. |
| Owner-assisted renewal collector/importer | Separate authorized account audit environment; trusted VPS operator imports protected original bytes. Backup worker has no account-wide audit key. | Exact ticket/source/policy/account/scope binding, prepaid ledger, two complete inventories, deadlines, replay state and atomic publication. |
| Doctor/admin/worker | Shared quillmd-app account UID996/GID988; no Docker group, capabilities or privilege gain. | Installed systemd paths hide operator runtime/Docker socket; source remains operator-owned and unwritable. Writable application data is not executable authority for helpers. |

The root helper's `--network none` restricts its network namespace but does not
remove host Unix control sockets exposed by the host bind. Its read-only host
mount plus writable systemd directory is not an OS sandbox against malicious
operator code. Paired harmless host tests showed private-PID chroot systemctl
could not connect, while the current host-PID path could read the existing service
state. Host-PID sharing is functional in this mechanism; it is not itself an
application-reachable exploit. No unrelated namespace or environment was read.

The doctor/admin/worker share one OS identity and application trust domain.
Application process compromise can affect data that identity is authorized to
read; this review does not claim process-level tenant isolation after arbitrary
code execution. The existing route/job/export authorization and MFA proofs remain
separate controls, linked below.

## Demonstrated defect and repair scope

Before the repair, a Docker client timeout could leave its daemon-side helper
running. A pinned, networkless, mount-free synthetic container survived the exact
subprocess timeout pattern; its unique ID was then removed and absence verified.
This is a reachable operational lifetime/cleanup defect, not a demonstrated
application-to-root escalation. Large or stalled application-owned data can
stress the bounded private reader; the trusted root installation path can also
outlive its caller if host operations stall.

The repair makes helper lifetime and cleanup explicit per invocation, bounds
captured output and uses the existing immutable local image. Timeout, interrupted
parent and failed cleanup are distinct failures. Cleanup verifies the exact
invocation/container identity and cannot claim success from a generic name match.
An in-container deadline bounds helper life independently of the client. The
existing systemd action can have its own lifetime: killing the installer cannot
undo or roll back an action already accepted by systemd. Retained operation
receipts and actual service state remain necessary after an interrupted install.

Private reader failures retain a redacted, single-link0600 event at
`rebuild/.runtime/backup-monitor/helper-failure-<invocation-token>.json`, even
when the public error suppresses helper details. It records the owned container,
operation failure and whether cleanup was confirmed; it contains no input or
captured output. For an unconfirmed cleanup, inspect that exact container and its
managed-helper label/image, then use the reviewed identity-checked cleanup path.
Never remove by a broad name pattern or assume a failed Docker query proves
absence. Preserve the event and failed operation receipt before a justified retry.
If the protected event directory is unsafe or publication fails, the operation
still fails explicitly; it cannot report a clean result.

A second demonstrated defect was at the remote metadata boundary: missing
pagination terminator fields were treated as null, allowing an incomplete response
to appear as an empty scope and create upload permits. Explicit field/type/cursor
validation now refuses before capacity admission; genuinely complete empty
inventories still work. A failed refresh invalidates its previous inventory handle.
Both counterexamples and the repair use fixtures, without a B2 request. This is a
failure-safe capacity-admission repair, not evidence that Backblaze returned such a
response or that an application caller can impersonate the provider.

The admission source hash changes, so the existing evidence is rebound through the
reviewed installer with identical policy bytes, observation and expiry. The real
ticket and collector source remain unchanged. Its original issuer revision remains
valid provenance; the VPS import command uses the new installed operations revision.
No account observation is refreshed by this security repair.

## Evidence and limits for the independent reviewer

Actual-host checks read the three current service kernel identities and run
canary probes as that account with cleared groups/capabilities and NoNewPrivileges.
A permitted private canary read/write/delete succeeds; operator canary reads,
Docker socket/CLI, source writes, writable-current-directory executable
substitution and sudo privilege gain refuse. Missing paths or unrelated errors
are not accepted as denial. These new probes run in separate PIDs, without entering
the live service mount namespace; unchanged prior startup evidence supplies the
same-PID service sandbox proof. Do not describe the new probes as code injected
into the live application.

Installed private-storage checks use only an owned synthetic subdirectory and
confirm valid reads plus refusal of symlink/hardlink/FIFO/mode/path substitutions.
No other user's file contents, live key, process environment or clinical data are
needed. Helper lifecycle verification uses isolated labelled containers, including
failure/interruption and concurrent ownership; exact results and remaining
limitations belong in the final private report rather than a guessed test count.

Renewal fixture evidence covers malformed/sized/linked return files, ticket and
collector identity, missing reservations, replay/concurrent policy replacement,
timeout/pagination/scope and fail-closed partial publication. The real September21
ticket is never a negative-test target. Integrity binding is **not a desktop or
provider signature**. The authenticated operator remains responsible for returned
measurement provenance; possessing a file named evidence is insufficient.
Operator-owned private reads retain a same-owner pathname race assumption where
not descriptor-based. Application identity cannot mutate their protected700
ancestors. No new application ingress was demonstrated there; malicious operator
or root already controls the host and is outside this narrower isolation claim.

## Prior applicable proofs and engagement handoff

Reuse [the private-readiness repairs](private-readiness-20260920.md) for unchanged
session revocation, tenant/job/file authorization and recovery cleanup; use the
current checkpoint where older narrative backup status has been superseded.
Reuse [reviewer host qualification](reviewer-host-qualification-20260919.md) for
the tested dedicated SSH access profile and scoped revocation. Reuse the
[independent-key recovery and current operational runbook](offsite-renewal-operations-20260920.md)
for the preserved remote restore and accounting controls. Do not replay provider,
Word, MFA, payment or broad application suites merely to raise test counts.

The external reviewer still needs their actual named identity/public key/source,
agreed UTC window, emergency contact and the existing activation checks. No
identity, tunnel, credentials or review window is created here. Once authorized,
provide this supplement plus sanitized exact-revision evidence; retain raw
operator-private evidence on the VPS. Review targets include command/data
transitions, safe file handling, helper cancellation and daemon failure, evidence
provenance, isolated resource ownership and failed-publication recovery.

Authentic provider-cost reconciliation (including the two historical receipt
gaps), outside-host monitoring and alert receipt, deferred human dictation/newSOAP
native Word acceptance, CPT licensing and patient-data permissions are separate
external dependencies. Configured-rate arithmetic is not invoice reconciliation.
Public maintenance, synthetic-only operation, administrator MFA and inactive
reviewer access remain enforced. No launch approval or whole-host recovery claim.
