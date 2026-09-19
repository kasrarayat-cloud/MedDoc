# Temporary host reviewer-access qualification — scope recorded before execution

Owner authorization: current task explicitly authorizes a temporary project-scoped
synthetic identity, effective-policy/Unix/revocation proof, focused repairs and
removal of test access. This is reversible test provisioning, not application
release, external reviewer access, or a change to shared SSH policy.

- Preserve shared SSH22 configuration, keys, listener and sessions. Preserve
  application services/data/audit, synthetic-only mode and public maintenance.
- Read and hash actual host SSH configuration; inspect complete effective policy
  for intended user/context. Shared22 is not certified by a separate listener.
- Create only absent project synthetic identities `quillmd-reviewer` and
  `quillmd-review-ctl`, with individual groups, inaccessible random passwords,
  noninteractive shells and no default-home authorized keys. Refuse name collisions.
- Normal host privilege separation runs in separate loopback-only transient project
  sshd units. Public keys are root-writable only outside account homes; private
  keys are root-only and temporary. No Include of shared listener directives and
  no shared daemon reload. Pin cryptographic choices to the host's effective values.
- Subject uses the existing prepared policy. Control is an owned synthetic fixture
  for positive Unix forwarding and unrelated-session continuity. Approved subject
  targets are actual app/admin9130/9131. Denied destinations are owned synthetic
  endpoints, never other projects or real host sockets. Only `/health/` is requested.
- Distinguish client-local Unix listeners aimed at approved TCP from prohibited
  server-side Unix paths/listeners. Limit app requests to at most2/second.
- Write revocation intent before removing the subject key; stop only its exact
  transient unit/cgroup. Confirm active-channel closure, reconnection refusal,
  refusal after restart with empty keys, and survival of the control tunnel.
- Each daemon has a short runtime ceiling. `finally` cleanup stops only recorded
  units, removes only recorded keys/runtime fixture and freshly-created identities
  after UID ownership checks. Retain failure/configuration/log/cleanup evidence.
- No application restart/deploy, real provider request, subscription, migration,
  global cleanup or external reviewer account is authorized by this fixture.

The administrative launcher uses the existing Docker-to-systemd root-management
method with a pinned local image and pinned committed fixture. Its short-lived
administrator container permits D-Bus; it does not change host AppArmor profiles,
shared SSH settings or application sandbox controls. Exact execution, failures,
cleanup and remaining gaps must be recorded; prepared configuration is not proof.

## Preserved positive-control failures and fixture correction

Actual `host-attempt1` and `host-attempt2` remain in the private evidence directory;
both stopped at the first Unix positive control and completed scoped cleanup.
Neither failure establishes that the subject's Unix restriction is qualified.

- Attempt1's control retained TCP-only `PermitOpen` and key `permitopen` lists.
  OpenSSH9.6 checks direct Unix destinations against those same lists, so the
  control's owned socket was denied before connection.
- Attempt2 removed those lists but disabled TCP forwarding. OpenSSH9.6's
  authenticated-session initialization uses the TCP forwarding directions to
  initialize shared forwarding permission sets. Disabling TCP also inserted an
  administrative denial into the local permission set used by Unix forwarding.

The corrected **control fixture only** uses `AllowTcpForwarding yes`, `PermitOpen
any`, `PermitListen none`, and no key destination list for the brief Unix positive
controls. Its generated key remains root-only, its listener loopback-only, and
its service has a fixed lifetime. Actual probes target only the recorded owned
synthetic sockets/listener. This broader test policy is never reviewer policy.
The control service is stopped and narrowed to local TCP9130, Unix forwarding
is disabled, and the key gains the matching destination restriction before the
persistent control tunnel used during subject revocation is established.
Subject restrictions, shared SSH configuration and application configuration do
not change.

Source diagnosis: [OpenSSH9.6 session initialization](https://github.com/openssh/openssh-portable/blob/V_9_6_P1/session.c#L319-L334),
[Unix destination permissions](https://github.com/openssh/openssh-portable/blob/V_9_6_P1/channels.c#L4586-L4621),
and [remote Unix permission matching](https://github.com/openssh/openssh-portable/blob/V_9_6_P1/channels.c#L3922-L3932).
The next actual execution supplies the positive-control evidence; source matching
alone does not close this check.
