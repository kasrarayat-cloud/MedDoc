# Declaration — grant the exclusion directory to the two units that take its lock, September 22, 2026

Two systemd unit files are replaced and one 0700 directory is created. **No migration, no schema
change, no application restart, no provider call, no backup, restore, readback or renewal, and no
change to any credential, policy, mode or identity.**

## Why this exists

`52b28b36` shipped `ops/activation_exclusion.py` and placed its `flock` at
`.runtime/.activation-publication.lock`. Neither unit that takes that lock was granted write
access to the path, and both run `ProtectSystem=strict`.

⚠️ **MEASURED, NOT INFERRED.** From **2026-09-22T07:53:54Z** — seventy-four seconds after the
activation reported `complete` — every five-minute publisher tick raised
`OSError: [Errno 30] Read-only file system` at `activation_exclusion.py:98`. **62 consecutive
failures, zero successes.** `core_servicehealth` is **23,998 seconds stale** at the time of
writing, against its own declared `expected_interval_seconds` of 300.

⚠️ **AND THE PROOF THAT SAID OTHERWISE RAN IN THE WRONG PLACE.** The 08:00:09Z publication that
looked like resumption was run by the operator OUTSIDE the sandbox, so it never executed the
failing path.

⚠️ **AND THE DESIGNED BACKSTOP IS DISABLED BY THE SAME CAUSE.** `backup_alerts.check()` calls
`recover_publication()` inside `except Exception: pass`; the identical EROFS would be swallowed.
It has not fired only because no pause is owed. That is why this act covers **both** units and
not only the one that is visibly broken.

## Bounded change

| what | exactly |
|---|---|
| files replaced in `/etc/systemd/system` | **two**: `quillmd-fresh-operations-publisher.service` and `quillmd-fresh-backup-alerts.service`, root-owned 0644, byte-identical to their reviewed sources in `rebuild/deploy/` |
| the delta in each | **one line**: `ReadWritePaths` gains `/opt/meddoc-pro/rebuild/.runtime/publication`. Nothing else in either file changes |
| directory created | **one**: `.runtime/publication`, mode 0700, owned by the operations identity |
| files relocated into it | the three coordination artifacts — the lock, `publication-deferrals.jsonl`, `publication-timer-pause.json` (absent today) |
| timer files | **unchanged**; both `.timer` units keep their current bytes and enablement links |

**MUST change, and this is the whole purpose:** the publisher resumes. Within one timer period of
the act, `core_servicehealth` key `backup` must show a `published_at` **later than
2026-09-22T08:00:09.984136+00:00**, and the journal must show a tick that does not raise EROFS.

⚠️ **THE ROW'S CONTENT IS EXPECTED TO MOVE, AND ITS `healthy` FLAG IS EXPECTED TO STAY FALSE.**
The publisher owns that row. `healthy=False` is reporting `offsite_policy_renewal_due` — a true
condition about tonight's 19:32:21Z policy expiry, and NOT a symptom of this defect. An act that
turned it green would be hiding something.

## MUST NOT change, each asserted before the act

| quantity | declared value |
|---|---|
| tables | 36 |
| applied migrations | unchanged; head stays `0018_servicehealth` |
| encounters | 29 |
| patients | 4 |
| jobs | 29 |
| ledger entries | 47 |
| payments | 3 |
| usage rows | 29 |
| service-health ROWS | 1 — the row's content moves; the count does not |
| every other systemd unit, override and enablement link | identical |
| the two `.timer` files and their `timers.target.wants` links | identical |
| `User=`, `Group=`, `ProtectSystem=`, `NoNewPrivileges=`, `UMask=` on both services | identical |
| documents, balances, audit history, MFA, synthetic-only, public maintenance | untouched |
| doctor, admin and worker processes | not restarted; PIDs unchanged |
| the served release | stays `52b28b369600549e0ad623fe49bdcd47c2cd44a1` |

⚠️ `core_auditevent` is **1100** and is expected to GROW; it is listed as a moving quantity
rather than omitted, because a count nobody declared cannot be judged either way.

## The grant is the narrowest one that works

Granting `.runtime` itself would buy one lock with write access to the whole evidence tree,
`backup-secrets/` included. Granting the three files individually reviews clean and still fails:
`note_timer_paused` writes a `.tmp` sibling and `os.replace`s it, and `recover_publication`
`unlink`s the marker — both need write on the **parent**. A dedicated directory is the only form
that works, and it is the convention every other ops unit already follows.

## Demonstrated before the act, not asserted

| demonstration | result |
|---|---|
| the guard fails on the units as `52b28b36` shipped them | reverted both, guard FAILED naming the unit and the path |
| the guard passes on the repaired units | restored, guard passed |
| the mutation restored cleanly | both files byte-identical by sha256, printed before and after |
| the predicate is not vacuous | positive control: rejects the shipped `ReadWritePaths` line, accepts a repaired one, ancestor grant counts, sibling grant does not |
| the requirement cannot drift | the guard reads the directory off the module rather than restating it |
| the suite | 873 ops tests pass |

## Rollback

The act is reversible by re-installing the previous unit bytes, which are retained by the
installer's own before-state evidence. The created directory and its contents are left in place
on rollback: an empty coordination directory is inert, and deleting it would destroy the deferral
history it now holds.

**No provider call. No B2 call. No restore drill. No repeat of any paid work.** This is a
filesystem-permission repair to two unit files.
