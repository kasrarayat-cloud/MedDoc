# Owner directive — 2026-09-26 (QuillMD disk reclamation authority)

Unnumbered: proposed on `feat/wm-narrative` (PR #1287). Per the number-claim protocol, a number is claimed only when
this row lands on `main`; until then it is referred to by this file and branch.

Recorded by the receiving session (the WM narrative qualification session) in its first commit acting on it.

## Provenance, stated so it is not read as more than it is

Received in-session on 2026-09-26 at about 22:50Z as text the owner pasted into the session, in answer to that session's
report that the preflight disk gate (90.26%) blocked the WM narrative Stage 1 work. Quoted verbatim below.

## The directive (verbatim)

> This is my explicit owner authorization to reclaim disk space for QuillMD. Do not ask me again to approve routine
> cleanup covered below.
>
> You may delete the nine obsolete Word engine build directories:
> /opt/meddoc-pro/.worktrees/wm-narrative/rebuild/.runtime/word-narrative-build-1
> through word-narrative-build-9.
>
> First recheck that the exact directories are unused and resolve inside that intended location. Preserve build-10 and
> every active dependency.
>
> You also have standing permission to remove verified obsolete QuillMD build artifacts, caches and disposable test
> resources that are not needed by running services, active tasks, rollback or retained evidence. Inspect ownership and
> dependencies before deletion.
>
> Preserve application data, documents, financial history, credentials, backups, required rollback resources and
> original verification evidence. Other tenants' resources are outside this authorization.
>
> Record this authorization and use the approved mutation procedure. If our project-owned permission configuration
> blocks these operations, I authorize a narrowly scoped change through the supported permission mechanism. Preserve
> broader protections; do not bypass enforced restrictions through another API or command.
>
> Measure actual recovered space and rerun preflight. Aim for usable working headroom, rather than merely slipping below
> the threshold.

## How it was applied, and the one limit met

- **The enforced restriction.** `.claude/settings.json` (tracked) denies `Bash(rm -rf:*)`, and a deny outranks any
  allow. A session-side permission change narrow enough to admit only these nine paths does not exist in that mechanism:
  the only change that would admit them is removing or weakening the broad `rm -rf` deny, which the directive says to
  preserve. Reaching the same deletion through another command (`rm -r`, `find -delete`, `git clean`, a root container,
  or a wrapper script whose inner command the deny cannot see) is the bypass the directive forbids. So the deletion is
  the one action this session could not perform; it is declared in
  `docs/foundation/mutations/20260926-quillmd-wm-narrative-obsolete-engine-builds.md` and executed by the owner through
  `scripts/run-ruled-mutation.sh`.
- **Standing permission, as bounded by the directive.** It covers artifacts this session can VERIFY as obsolete and
  remove with a tool sanctioned for that purpose (`scripts/reap-lens-sandbox.sh`, `scripts/reap-session-scratch.sh`).
  Other sessions' worktrees are QuillMD-owned but were NOT treated as obsolete: whether their sessions are finished, and
  whether their ignored files hold verification evidence, cannot be established from here.
