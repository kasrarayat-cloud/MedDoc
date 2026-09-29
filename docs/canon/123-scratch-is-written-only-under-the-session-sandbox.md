# SCRATCH IS WRITTEN ONLY UNDER THE SESSION SANDBOX — A FILE OUTSIDE IT HAS NO REAPER

**Standing 2026-09-07, from ruling #224.**

The close-out obligation is not discharged by finding a stronger broom. It is
discharged by **never writing the file where nothing can sweep it.**

## THE TWO CORRECT RULES THAT LEAVE A GAP BETWEEN THEM

| | |
|---|---|
| `shred` is **denied outright** | ruling #166 — a permission entry is a command-text **PREFIX**, so no path scope is safe. A grant narrow enough to be safe cannot be written, so it is not written. |
| `scripts/reap-session-scratch.sh` **refuses everything outside `/tmp/claude-1000/`** | that refusal is what stops a traversal argument reaching `.env` |

**Both are right.** And between them:

> **A bare `/tmp` file is unreapable by any granted instrument.**

Measured, on a real leftover:

```
$ bash scripts/reap-session-scratch.sh /tmp/admin5-lock.sql
🔴 REFUSED (outside /tmp/claude-1000/): /tmp/admin5-lock.sql -> /tmp/admin5-lock.sql
```

Inside the sandbox the same door works exactly as advertised — 11,490 files in
one sweep, zero failures, including files inside a `git archive` copy where the
tracked-file check correctly declines to fire.

## THE RULE

> **WRITE SCRATCH ONLY UNDER THE SESSION SANDBOX.** The question *"can I clean
> this up?"* has to be answered **at the moment of creation**, because that is
> the only moment at which the answer can still be changed.

A path chosen carelessly at 03:00 is a permanent artifact at 05:00, and no
amount of care during the sweep recovers it.

## ⚠️ AND DO NOT LAUNDER PAST THE DENY

The obvious move — move the file into the sandbox, then reap it — is **refused.**
It routes around a deliberate deny **while leaving an audit trail that says the
door was used**, which is worse than the file: the next reader sees a clean sweep
and cannot tell that a boundary was stepped over.

**Report the gap. Escalate the file. Leave the deny intact.** An unreapable file
named honestly in a report is a known, bounded item; a laundered one is an
unknown, and the record now lies about it.

## THE GENERALISATION

**This is the write-time half of a class this programme keeps meeting at
sweep time.** A tracked clinical file is a history rewrite, not a `git rm`; a
directory snapshot under `~` is a liability the moment it is made; a bare `/tmp`
file has no reaper the moment it is written. **In every case the expensive
version of the problem was created by one careless path choice, and the cheap
version was available at that instant and never again.**

The sibling entries are about detecting the artifact. This one is about not
manufacturing it.

## ⚠️ AMENDED 2026-09-29 — INSIDE THE SANDBOX IS NOT "MINE": RECORD IT WHEN YOU MAKE IT

The measurement above — *11,490 files in one sweep, zero failures* — is kept,
because it is exactly the shape that failed twice on 2026-09-29. A subagent ran
`find <whole session scratchpad> -type f | xargs bash scripts/reap-session-scratch.sh`
and shredded **30 files other agents had written**; the lead later swept the
same scratchpad with `find … | xargs -0 -n 200 …` in three passes and shredded
**6,537**, the cleanup's own lists and logs included. Zero failures is what a
sweep reports when every per-path check passes, and none of those checks is
OWNERSHIP: the sandbox belongs to one uid and is shared by every agent in it.

So the write-time rule has a second half, answered at the same instant:
**record the file as yours when you create it, and reap only what you recorded.**

    bash scripts/scratch-ledger.sh record --agent <session id> [--retain] <ledger> <file>...
    bash scripts/reap-recorded-scratch.sh [--retained <manifest>]... <ledger>

The ledger and the reaper's log live OUTSIDE the sandbox in a private
directory. The reaper takes only recorded entries and refuses any that changed
path, inode, content, owner or link count, is retained, is tracked by git, or
is held by a live process. It never walks a directory. `reap-session-scratch.sh`
now refuses more than 16 paths in one call, or a `find`/`xargs` driver, unless
`REAP_SESSION_BULK_DECLARATION` says why. **Subagents close out with the
recorded reaper, never with a sweep.**

## ⚠️ CORRECTED 2026-09-29 (later the same day) — THE FIRST REAPER WAS REFUTED ON THIRTEEN COUNTS

The amendment above is kept as written. A refutation pass over it confirmed
thirteen defects, and four of its sentences were wrong in a way that matters:

- **"More than 16 paths in one call, or a find/xargs driver" was a rule about
  process NAMES.** `busybox xargs`, xargs run under another name, and
  `xargs … setsid -f` each fed it 16 paths at a time with no declaration. The
  bound is now counted **across calls** — per ledger for the recorder, per uid
  for `reap-session-scratch.sh` — so at most 16 undeclared paths pass in any 5
  minutes whatever drives them. A declaration now needs 12 **visible**
  characters; twelve spaces had passed.
- **"Record it when you create it" refused every file written afterwards.**
  Record a file once its last write is done, and again after any later write.
- **The reaper trusted any well-formed line.** Every line now carries an HMAC
  under a key the recorder creates beside the ledger; one unbound line refuses
  the whole ledger. Retain is global across the ledger directory, keyed on path
  and on (device, inode, sha256).
- **"Refuses … is tracked by git" failed open.** Git exiting 128, or a file
  inside `.git` or a bare repository, was read as untracked. The old door also
  shredded a file whose inode a local clone shares with its source; it now takes
  only a regular file with one link.

What this entry teaches is unchanged: the answer to *may I destroy this?* is
fixed when the file is made. The correction is that each check written to
enforce it was a claim until something tried to break it.
