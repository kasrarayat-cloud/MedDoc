# Private application OS boundary

Activated and verified 2026-09-17 on release
`688837471efb8b11c57a89e76d585e0ba352e937` (PR1181). Exact merge CI35262434086
and secrets35262434087 passed before the guarded cutover. The design below is
implemented. Private `os-identity-activation.json` records the judged result:
all33table fingerprints,27files and2mail objects preserved,6shared containers
unchanged, no provider requests or schema changes.

Actual doctor/admin/worker processes run as UID996/GID988 with only their private
group, no capabilities and `NoNewPrivs=1`. Each same-PID proof passed9denials
and3state read/write/delete controls. `identity-browser-verification.json`
passed8deployed checks including MFA/replay, session recovery, invitations,
exactly-one welcome grant, upload/export and department/organization isolation.
These invitation/recovery checks used the private outbox, not real email.

The direct file/socket coverage gap is closed by same-PID measurements. The
blocked namespace-entry method remains blocked; no host protection was weakened.

## Diagnosis of the previous coverage gap

The previous verification attempted to enter each running service's mount
namespace from the authorized, constrained Docker maintenance helper. All three
`/proc/<pid>/ns/mnt` opens returned `EACCES` before any application-path test ran.
That result did **not** prove whether service secret access was denied.

Read-only controls established the cause:

- A host process with the service's existing UID opened all three namespace
  handles successfully.
- The helper used Docker's enforcing `docker-default` AppArmor profile. Its
  effective capabilities excluded `CAP_SYS_PTRACE` and `CAP_SYS_ADMIN`.
- Dropping the helper to the same UID and GID as the target still produced
  `EACCES` for all three handles.
- Sanitized kernel records explicitly show AppArmor `ptrace` **read** denials
  from `docker-default` to `unconfined`, for both the previous `nsenter` attempt
  and the new Python control.

The helper therefore has two relevant constraints: the original cross-UID
inspection lacks the required ptrace capability, and the AppArmor profile denies
the read even for the matching-UID control. Namespace entry would additionally
need capabilities the helper intentionally lacks. These controls remain intact;
no privileged container, unconfined profile, Yama change or added capability is
needed. Private evidence is retained in
`rebuild/.runtime/namespace-diagnosis-20260917.json`.

The kernel's namespace-handle inspection uses ptrace access checks; see the
[Linux ptrace documentation](https://man7.org/linux/man-pages/man2/ptrace.2.html).

## Dedicated identity and state ownership

The application identity is the nonlogin system user and group
`quillmd-app`. It must have no operator or Docker group membership. The launcher
checks the real/effective/saved/filesystem UID and GID, supplementary groups,
empty inherited/permitted/effective/bounding/ambient capability sets and
`NoNewPrivs=1` before starting the application.

This addresses an observed weakness in the old unit identity: services running
as `claude` inherited the operator's `users` and `docker` supplementary groups.
An empty `SupplementaryGroups=` property alone did not remove the account's
ordinary group memberships.

Verified ownership:

| Resource | Required ownership and access |
| --- | --- |
| `/var/lib/quillmd` | root, group `quillmd-app`, mode `0710`; application cannot replace child directories |
| `files`, `mail`, `proofs` children | `quillmd-app:quillmd-app`, mode `0700` |
| Application data and proof files | mode `0600` |
| Source and Python environment | Operator-owned; application cannot write |
| Fresh `.env` | Operator-owned `0600`, hidden from application filesystem view; systemd manager supplies environment |
| Operator `.runtime`, backup keys, bootstrap credentials | Operator-owned and inaccessible to application |

Only the three application state directories are writable through the service
policy. Backup and maintenance operations need their separate authorized access
to application-owned files; runtime access to backup or migration credentials
is not part of that arrangement.

## Direct verification in the actual service

Each fixed unit command starts `rebuild/ops/service_launcher.py --surface
doctor|admin|worker`. The launcher executes inside the service's own security
policy and then uses `os.execv()` for the fixed application command. Probe and
application retain the same PID and mount namespace.

Startup fails closed unless these checks pass:

1. Dedicated identity, private supplementary group only, empty capability sets,
   and `NoNewPrivs=1`.
2. Required environment exists, the database account is `quillmd_runtime`, the
   database is `quillmd_fresh`, and the release identity is a full commit SHA.
3. Actual `open()` attempts deny access to shared and fresh environment files,
   operator runtime, bootstrap database secret, synthetic account credentials and
   retained service credentials. No secret bytes are read or printed.
4. A genuine `socket.connect()` to `/run/docker.sock` is denied. No Docker
   request is sent. A regular file-open failure would be an invalid socket test.
5. Attempts to open application source for writing are denied; the probe never
   writes or truncates source.
6. Exclusive synthetic canaries can be written, read back and removed within
   each allowed state directory with `0600` file permissions. Parent and child
   ownership and modes are checked; symlink substitutes are refused.

Missing paths and unexpected errors are **inconclusive**, so they refuse
startup. `EACCES` or `EPERM` proves read/socket denial; `EROFS` is additionally
accepted only for source-write checks. All three service commands are fixed;
the launcher cannot accept an arbitrary program. It sets the surface, managed
environment flag and state root itself because systemd `EnvironmentFile` values
can otherwise override unit `Environment` entries.

On success, sanitized JSON is written to stdout and to the private
`/var/lib/quillmd/proofs/<surface>.json`. It records PID, mount namespace,
release, identity and check outcomes. It contains no credentials, environment
values other than release, provider response, patient content or session data.
Verify each proof's PID against the running unit `MainPID`; a file from a prior
successful startup does not prove the current service. Preserve a copy through
the maintenance identity because these local proof files are application-owned,
not a tamper-proof external audit log.

`ExecStartPre` and transient units would provide weaker evidence: systemd sets up
a separate mount namespace for each command. The same-PID launcher avoids that
gap. See the
[systemd execution specification](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml).

## Evidence and limits

Focused launcher tests cover accidental Docker group inheritance, saved-root
IDs, every capability set, missing-path false passes, readable secret files,
writable source without byte changes, read-only mounts, actual socket-connect
semantics, state modes/symlinks, private canary cleanup, environment overrides,
fixed commands, sanitized failure output, same-process exec ordering and proof
file permissions. These are implementation tests; they do not replace running
the launcher under the installed units.

At document preparation, **13 focused tests passed**. Activation and actual
service results must be recorded in the durable private checkpoint after the
reviewed policy and identity are installed. This document does not claim those
steps have already happened.

External namespace entry remains unavailable by design. Direct in-service probe
results can close the specific file/socket denial coverage gap without changing
that fact. This boundary separates the application from the deployment identity;
it does not isolate the three application processes from each other, replace
department authorization, constrain all provider egress, or constitute an
independent penetration test. Public maintenance and the synthetic-data gate
remain required until their release controls are verified.
