# Ruled act — recording stop-on-failure repair, activated on the private services

**Date:** 2026-09-18 · **Act:** replace the running private release with the reviewed target and restart the three
private services · **Door:** `scripts/run-ruled-mutation.sh` → `scripts/activate-recording-repair.py --execute`

## What is being activated

| | |
| --- | --- |
| running release (services answer this) | `cd428f7062d3d624787d927c41130692017d5a84` |
| tree HEAD before the fast-forward | `d45d9f72216132934b99e0c1fa426d1bc4fb532f` |
| target | the merge commit of this PR, passed as `--target` and checked against `origin/main` |

Only this repair is in the range. The previous act shipped, so nothing is riding along unjudged.

## What changes in BEHAVIOUR, which no post-deploy comparison can show

⚠️ **This is the part to read.** Every quantity below is about what did NOT move, and not one of them would notice
the actual change: recordings whose processing fails are now REFUSED where they were previously transcribed from the
unprocessed original. The evidence that this is correct is the test suite and the end-to-end demonstration that
follows the act — not this activation.

1. **The fallback is removed.** Missing or unusable ffmpeg, a timeout, a nonzero exit, an unmeasurable or ambiguous
   artifact, an artifact that decodes to a different length, an artifact too large to send — all now stop before the
   provider. Nothing is charged, and the reservation is released exactly once in the same transaction that writes the
   failure.
2. **A WAV holding more than one `data` chunk is refused at enqueue**, before a job exists and before any hold, like
   a payload holding several audio tracks. Such a file gives three different answers about its own length.
3. **The artifact is decoded, not merely remuxed.** A successful `-c:a copy` proves nothing about whether the frames
   decode; the declared and decoded lengths must now agree within 0.25 s.
4. **`configuration_status` reports `DEEPGRAM_API_KEY` and `ANTHROPIC_API_KEY`** as present/absent. Status only.

## MUST change

1. `QUILLMD_RELEASE_SHA` in the private environment file: `cd428f70…` → the target. One line, one occurrence, line
   count unchanged; recorded by sha256 of the file before and after, never by its content.
2. `/health/` on `127.0.0.1:9130` and `:9131` reports `release` = the target, `data_mode` = `synthetic-only`.
3. All three services restart: each unit's `ExecMainStartTimestamp` moves, and for the worker the kernel's own record
   of its main process start moves with it.

## MUST NOT change — any difference is THE FINDING

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

Also byte-identical across the act: every column, constraint and index; every table's row fingerprint; the private
files and mail inventories; the compiled Word runtime; the retained reports; the protected containers; and the
installed unit files against their reviewed sources.

## Preconditions the activator refuses without

- the shared tree is `main`, clean, **already fast-forwarded to the target**, with the declaration tracked in it
- the target is a merged PR into `main` with a full citation
- the changed-path set from the running release is a subset of the declared set, and **no migration is in it**
- `ffmpeg` and `ffprobe` both resolve — and they matter more than before, because their absence is now a refusal
  rather than a silent downgrade
- a plaintext-free restore proof whose row count matches the live database
- no queued, running or reconciling job
- the services are up on the recorded running release, synthetic-only

## If it fails

Fails closed: the three services are left stopped, the partial result is written to private evidence, and the lock is
left for inspection. Rollback touches no data: reset the tree to `d45d9f72`, restore the release line to `cd428f70…`,
restart. There is no schema change and no data write in this act.

## After the act

A single end-to-end demonstration through the application: one locally synthesized speech sample, uploaded over
authenticated HTTP by a synthetic account, transcribed by the real provider, with the transcript displayed and
downloadable. Its expected records and charges are declared separately before it runs.
