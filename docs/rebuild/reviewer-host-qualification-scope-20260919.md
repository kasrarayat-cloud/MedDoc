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
