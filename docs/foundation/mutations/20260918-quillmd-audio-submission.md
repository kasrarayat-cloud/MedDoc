# Ruled act — deterministic audio submission, activated on the private services

**Date:** 2026-09-18 · **Act:** replace the running private release with the reviewed target and restart the three
private services · **Door:** `scripts/run-ruled-mutation.sh` → `scripts/activate-audio-submission.py --execute`

## What is being activated

| | |
| --- | --- |
| running release (services answer this) | `5f8050df5e79c0d7948185850914f1c161fcbc1f` |
| tree HEAD (merged, never deployed) | `8de5dd491de78b4e628364096c50ed68b161ef19` |
| target | the merge commit of this PR, passed as `--target` and checked against `origin/main` |

Two changes ship together and both are judged here: the integrity-and-cleanup milestone that merged as the tree HEAD
and was never activated, and deterministic audio submission. **Saying "I deployed `main`" is not the same claim as
"I judged what I deployed", so the declared set below covers the full range from the RUNNING RELEASE, not from the
tree.**

## The expected delta is EMPTY, and that is stricter than a migration-carrying one

This act carries **no migration**. A migration-carrying activation has a declared delta to judge against, so it can
say *everything except these rows changed, and that was expected*. Here there is no such excuse available: the only
things entitled to change are the running code, the release line in the environment file, and the process identities
of the three restarted services.

### MUST change

1. `QUILLMD_RELEASE_SHA` in the private environment file: `5f8050df…` → the target. **One line, one occurrence**; the
   file's line count must be unchanged, and the activator records a sha256 of the file before and after rather than
   any of its content.
2. `/health/` on `127.0.0.1:9130` and `:9131` reports `release` = the target, `data_mode` = `synthetic-only`.
3. All three services restart: each unit's `ExecMainStartTimestamp` moves, and for the worker the kernel's own record
   of its main process start time moves with it.
4. The shared tree advances from the tree HEAD to the target by fast-forward.

### MUST NOT change — any difference here is THE FINDING

| quantity | value before the act |
| --- | --- |
| tables in `public` | 35 |
| latest applied `core` migration | `0014_encounter_service_date` |
| encounters | 11 |
| finalized documents | 6 |
| jobs | 12 |
| usage rows | 12 |
| provider receipts | 9 |
| audit events | 363 (may only grow, and only from the act's own rows) |
| jobs queued / running / in reconciliation | 0, before and after |

Also byte-identical across the act: every column definition, every constraint, every index, every table's row
fingerprint, the private files and mail inventories, the compiled Word runtime artifact, the retained reports, the
protected containers, and the installed unit files against their reviewed sources.

⚠️ **The audit-event count is the one number allowed to move, and only upward.** It is listed because omitting it
would leave the row nobody checks; a DECREASE, or growth from anything other than this act, is a finding.

## Preconditions the activator refuses without

- the shared tree is `main`, clean, at the tree HEAD, with `origin/main` at the target
- the target is a merged PR into `main`, with a full citation (`scripts/check-citation.sh`)
- the changed-path set from the running release is a subset of the declared set, and **no migration is in it**
- `ffmpeg` and `ffprobe` both resolve to an executable path — the new runtime dependency. ⚠️ **Without ffmpeg the
  application still works**: every recording is submitted exactly as uploaded, unnormalised, which is correct and
  silent. That is precisely why it is verified before the act rather than discovered afterwards.
- a plaintext-free restore proof whose row count matches the live database
- no queued, running or reconciling job — a provider request is never replayed
- the services are up on the recorded running release, synthetic-only
- units, document sandbox, launcher, storage helpers and dependencies are untouched by the range

## If it fails

The activator fails closed: the three services are left **stopped**, the partial result is written to private
evidence, and the lock file is left in place for inspection. Rollback is bounded and does not touch the database:
reset the shared tree to the tree HEAD, restore the release line to `5f8050df…`, and restart. Nothing in this act is
irreversible — there is no schema change and no data write — which is why the strictness here is spent entirely on
proving that nothing changed.

## Verification after the act

Structural only, and no real clinical record is touched: container and unit health, the three revisions read back from
the services themselves, the worker identified by start time, command and cgroup membership rather than by PID, the
billing audit report, administrator access, public maintenance and co-tenant status, and synthetic-only enforcement.
The transcription path is exercised on the synthetic account alone.
