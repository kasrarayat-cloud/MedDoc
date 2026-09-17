# Declared private application OS identity and state cutover — 2026-09-17

Authorization: the owner directs continuation from release `66acbba`, preserving
the new application and data, completing dedicated OS identity, least privilege
and direct service-boundary verification. This declaration authorizes only that
scoped private cutover. Public maintenance and synthetic-only data remain gates.
No reset, old-system import, broad cleanup, subscription or provider operation
is part of this act.

## Baseline and reviewed target

Baseline shared main is `66acbba70e7f7c02c1b16d6cd71c4ed7d72dd8ff` with active
`quillmd-fresh-doctor`, `quillmd-fresh-admin` and `quillmd-fresh-worker` units.
Private listeners remain loopback `9130` and `9131`. The dedicated database is
`quillmd_fresh` in `quillmd-fresh-postgres`, loopback `55438`, schema through
`core0010`, 33 public tables. New application state is under
`/opt/meddoc-pro/rebuild/.runtime/files` and `mail`.

The execution target is the full SHA of the merged PR containing this declaration
and `scripts/activate-os-identity.py`. The activator must match its reviewed
target bytes, prove a merged PR into main, verify current `origin/main`, a clean
shared main ancestor and successful exact-merge CI citation. A full authenticated
new-system backup and completed isolated restore proof must pass validation
before any stop or mutation. No schema change is permitted in this cutover.

## Expected changes, in order

1. Gracefully stop exactly the three private QuillMD units. Refuse queued/running
   provider jobs; no retries, financial releases or payment credits occur.
2. Capture row hashes and counts for **all 33 public tables**, including every
   current column and `django_migrations`. Capture every file and mail object,
   rejecting links, unusual objects or nonprivate files.
3. Fast-forward shared main to the cited target. Retain its virtual environment,
   deployment configuration, all new database rows and prior private evidence.
   Prove source and Python environment readability using a capability-free,
   networkless read-only helper with unrelated numeric UID/GID `65534:65534`.
   Change permissions **only** within operator-owned `rebuild/staticfiles`:
   directories become `0755`, compiled public CSS/JS, compressed variants and
   `staticfiles.json` become `0644`. Refuse links, unexpected owners/types and
   assets outside the two application and three installed OTP manifest entries. Verify every
   static byte hash and inode before/after; only modes change. Source, private
   environment, application data and backup permissions are not broadened.
4. Through a bounded root helper, create the nonlogin system user/private group
   `quillmd-app` only if absent; refuse any mismatching preexisting account.
   No operator, `users` or Docker group membership is granted.
5. Create `/var/lib/quillmd` as root-owned, private application group, `0710`.
   Copy only the fresh application's `files` and `mail` into exclusive staging
   children, verify all hashes, then atomically rename **within that destination
   filesystem**. New `files`, `mail` and `proofs` roots are application-owned
   `0700`; files are `0600`. The original operator-private copies remain intact
   and become inactive; no data is deleted. This is a storage cutover of the
   current new system, with unchanged database-relative paths.
6. Record the new numeric identity and device/inode identities of the three
   roots in operator-owned `0600` `.runtime/state-identity.json`. This supports
   narrowly scoped maintenance reads without giving the app backup credentials
   or adding the operator to the application group.
7. Install only the three exact reviewed unit files with an atomic replacement
   and reload systemd. Services use the private account, no capabilities,
   manager-loaded fresh environment, hidden operator environment/runtime and
   only three explicitly writable state directories. Root's helper retains
   existing AppArmor/seccomp confinement: no privileged/unconfined mode, new
   capability, host security change or network access.
8. Replace only `QUILLMD_STATE_DIR=/var/lib/quillmd` and the reviewed release SHA
   in fresh `.env`. All other lines, credentials and configured rates remain
   identical; `.env` remains operator-owned `0600` and is hidden from services.
9. Verify all table/file hashes, run the application configuration check and
   start the same units. Their fail-closed launcher tests actual identity,
   capability sets, secret/socket/source-write denial and approved private state
   access, then `exec`s the fixed application in the same PID/namespace.
10. Check health release and synthetic-only mode; compare each proof PID with
    systemd MainPID and actual process UID/GID/groups/capability sets. Recheck
    both real login pages and their manifest-selected CSS: `200`, correct
    content type, actual form/stylesheet presence, complete stylesheet hash.
    These unauthenticated GETs create no user, ledger, provider or audit activity.
    Recheck
    table/file equality, public statuses and protected shared containers.

## Helper scope and preserved resources

The already installed Python helper image is pinned by local image ID. Its host
root bind is read-only. Only `/etc` (account database and the three unit files)
and `/var/lib` (exclusive new QuillMD state root) have writable binds; the helper
code permits no arbitrary paths or commands. Original source state is read-only.
Cross-bind atomic rename is unavailable, which is why verified copy followed by
destination-local rename is explicitly declared.

Preserve the marketing website, root/shared environment, retained useful provider
credentials, old inactive copies of **new-system** state, all prior evidence and
backup keys, PostgreSQL container/volume/database, other projects, shared services,
DNS, certificates and ingress. The six protected container identities, images,
mount identities and running states remain unchanged. Marketing and www stay
`200`, app/admin stay `503` maintenance, retired pro stays `410`.

No historical provider receipt, ledger event, payment, clinical artifact or
welcome credit is inserted, rewritten or removed. No migration from the retired
application is created. Later synthetic workflow checks, if needed, must be
recorded as intentional verification activity after this unchanged-data proof.

## Failure handling and honest coverage

The activator is one-shot. Existing cutover state, lock or result requires
inspection, not an automatic rerun. If a mutation fails, retain all originals,
new copies and evidence, keep the private units stopped, and keep public
maintenance. Record the actual partial state before deciding any next action.
Do not automatically roll back permissions, copy again, drop data, issue provider
requests or alter financial holds. The original state and encrypted backup remain
available for a separately reviewed recovery decision.

The confined external helper's namespace-entry denial remains an intentional
host boundary. Successful same-PID startup evidence closes the specific direct
file/socket-access coverage gap without weakening that boundary. It does not
constitute an independent penetration test or permission to use real patient
data. Retained inactive copies may be considered for a later narrowly scoped
retirement once backup/recovery controls are settled; no such deletion occurs
in this act.
