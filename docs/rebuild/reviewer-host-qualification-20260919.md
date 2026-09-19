# Reviewer access: actual-host qualification — 2026-09-19

## Decision

**Engineering qualification passed for the dedicated project SSH profile. No
external reviewer access is active.** The current shared port22 configuration is
not the qualified reviewer path. No shared SSH policy, application service,
application data, provider configuration or public route was changed.

Actual host attempt3 ran committed fixture `6652cb96` with OpenSSH9.6p1 on this VPS:
**53 focused assertions passed in9.214seconds**. These include setup/preservation
assertions; they are not53 independent penetration tests. The existing20 isolated
SSH regression tests also passed without skips, using their original substituted
ports/UID. Their evidence remains separately labelled.

## What executed on the actual host

| Boundary | Demonstrated result |
| --- | --- |
| Effective configuration | Full shared `sshd -t` and `sshd -T -C` captured for intended `quillmd-reviewer`, loopback source/local address and port22; recursive Include file hashes captured. Complete separate project configs validated for the actual temporary listener context. |
| Identity and authorization | Dedicated synthetic system UID/private group, nologin shell, root-owned home without `.ssh`, root-writable public authorization outside home; exact key file, no key command, certificate CA or principal authorization source. Test keys expire and remain private. Shared22 rejected the project key. |
| Listener and privilege separation | Each daemon's complete owned TCP/TCP6 listening-socket set was exactly its assigned IPv4 loopback listener. Root monitor and account-UID child processes were observed inside separate service cgroups. |
| Application destinations | Actual doctor9130/admin9131 `/health/` responses returned200, synthetic-only and release `dc4eb42ce021e436a3b717eb40edb10ace8e662c`. A third owned TCP target and the unapproved `localhost` spelling were rejected. |
| Other SSH capabilities | Remote TCP forwarding, shell and SFTP rejected. Effective agent/X11/TTY/rc/tun restrictions recorded. Narrowing only the key independently denied admin9131 while doctor9130 still worked; an expired key could not authenticate. |
| Unix destinations/listeners | A functioning owned Unix target and a functioning remote Unix listener were proved with the positive-control profile. Reviewer requests for both were rejected. A client-local Unix listener could reach approved TCP9130, but could not reach the denied TCP target: client socket shape does not bypass destination restrictions. |
| Revocation | Write-ahead event preceded key removal. Key removal blocked new authentication while the existing tunnel still worked. Stopping only the subject service/cgroup closed that tunnel and an SSH-confirmed, already-open data channel. Restart with empty authorization still rejected authentication. |
| Unrelated sessions | The separate control tunnel served health after subject termination with the same client PID/start time. Shared SSH/app service identities, configuration hashes and every pre-existing SSH process identity survived attempt3 unchanged. |
| Cleanup | Both temporary accounts/private groups, root-held keys/runtime directory and project listeners removed; scoped units inactive. A separate read-only follow-up verified all three attempts' cleanup and absence of eight recorded fixture processes. |

The positive-control profile is an instrument, never a reviewer grant. It briefly
used broader forwarding permissions with an expiring root-only key and a
loopback-only listener; probes touched only owned synthetic sockets. It was stopped
and narrowed to TCP9130 with Unix forwarding disabled before establishing the
persistent control tunnel used for revocation.

## Preserved failures and repairs

- Before execution, refutation repaired launcher audit/timeout handling, launch-file
  compatibility, interrupted account tracking, cleanup queries, malformed-response
  serialization, DEBUG2 channel-confirmation logging and exhaustive bind checks.
- Attempt1 failed the Unix positive control because its TCP-only key/server
  `PermitOpen` lists also rejected the Unix target. Cleanup passed. Two unrelated
  preauthentication processes ended; captured journal evidence identifies a failed
  password login/reset. They were not established reviewer or owner sessions.
- Attempt2 still failed that control because `AllowTcpForwarding no` installs a
  shared forwarding deny rule. Cleanup and all pre-existing SSH identities passed.
- The control's initialization was repaired, then attempt3 passed. The reviewer
  profile was unchanged through these repairs. Historical failures remain false
  in their original reports; no result was rewritten.

The observed interaction is explained by OpenSSH's
[forwarding initialization](https://github.com/openssh/openssh-portable/blob/V_9_6_P1/session.c#L319-L334)
and [Unix destination checks](https://github.com/openssh/openssh-portable/blob/V_9_6_P1/channels.c#L4586-L4621).
Source inspection explains the failures; attempt3 supplies execution evidence.

## Evidence and scope limits

Private evidence root: `/opt/meddoc-pro/rebuild/.runtime/reviewer-host-20260919/`.

- `host-attempt3/report.json`: SHA256
  `11ece0ab56db883fa72e564110740589b5e2295237cf5e84ba1880a7bd09c738`.
- `host-attempt3/SHA256-MANIFEST.json`:26 entries independently checked against
  actual files and sizes; effective configurations, journals, client logs and
  append-only events included. Only public keys are retained; private test keys
  were removed. `launch.json` pins exact source/helper/image/commit.
- `host-attempt1/`, `host-attempt2/`, `attempt1-2-diagnosis.json` and pre-execution
  findings preserve failures and their provenance.
- `independent-cleanup-verification.json`: SHA256
  `c944bbfab9658fc73dde5a3eaa42c2e3b0b75bed9533615a0c5b2744e42d77e0`.
- `isolated/report-20260919T192736Z.json` and its raw test log record20 isolated
  tests/zero skips. Four mocked launcher guard checks are separately identified
  in `launcher-guards.json`; they are not host forwarding evidence.

Actual traffic was loopback to temporary project listeners. Effective-policy
output for hypothetical source192.0.2.10 is configuration evidence, not an external
network test. The external reviewer's actual identity, key, source, agreed UTC
window and emergency contact are still required. Engineering must install and
recheck the exact project access path, pin its host key, schedule and verify the
window-end key removal/cgroup cutoff, and verify external reachability before
sharing synthetic application credentials. No shared22 reload is part of this
arrangement. The legacy helper's `revoke` alone does not terminate connections.

This closes the specified host policy/Unix/revocation engineering qualification.
It does not certify an unconfigured external route or future scheduler, constitute
an independent penetration test, or approve public launch/real patient data.
Word acceptance remains closed; no Word review, export regeneration or application
activation was performed for this operations/documentation milestone.
