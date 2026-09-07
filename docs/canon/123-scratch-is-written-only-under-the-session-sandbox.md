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
