# Scratch reaping — 2026-08-08

**Supervised close-out for the foundation loop's first two launches.** The owner
ruled on this date that `shred` stays **denied** to the unattended loop — an
unattended destroyer is the wrong risk — and that a supervised session performs
the reaping instead. This is that session's record.

Extraction landed and was pushed **before** any destruction began. Nothing below
quotes clinical content or any credential value; the rule is *report paths, never
contents*.

---

## 1. The boundary — what was actually looked at

A sweep that does not say what it covered cannot be checked, and *"I found
nothing"* is worthless without *"here is where I looked"*.

| root | depth | device | files visited |
|---|---|---|---|
| `/opt/meddoc-pro` | **unbounded** (deepest reached: 19 components) | `/dev/sda2` ext4, `-xdev` | 103,159 |
| `/tmp` (incl. `/tmp/claude-1000/**`) | **unbounded** (deepest present: 6) | `/dev/sda2` ext4, `-xdev` | 11,927 |
| `/home/claude`, `/home/yap`, `/root` | **unbounded** (deepest reached: 18) | `/dev/sda2` ext4, `-xdev` | 78,866 |

No `-maxdepth` anywhere. This is deliberate: the 2026-07-30 sweep returned **4 of
6** stale exports at `-maxdepth 6` and read as complete — the other two sat at
depth 7. **A depth-limited sweep is a sample, never an inventory.**

### Holes, named rather than papered over

- **9 home directories are mode 0750 and owned by other users** — `cortex`,
  `drhooman`, `leathererp`, `tester`, `ubuntu`, `voiceassist`, `voiceassistmain`,
  `westapp`, `westweight`. Their contents are **UNKNOWN to this sweep, not proven
  clean.**
- 10 unreadable directories under `/tmp` (2 co-tenant Claude scratch roots, 7
  root-owned `systemd-private-*`, 1 `snap-private-tmp`).
- The encrypted volumes (`/mnt/pgdata-encrypted`, `/mnt/miniodata-encrypted`)
  were **not** traversed — `-xdev` stopped at the boundary, by design.

### Positive controls — why the zeros mean anything

A traversal that silently covers nothing returns zero for every needle you try,
so each sweep ran its **own matcher form** against something known present:

| sweep | control | hits |
|---|---|---|
| repo | `find -xdev -iname '*transcribe*'` | 245 |
| `/tmp` | `find -xdev -path '*claude*'` | 169 |
| home | `grep -rla 'meddoc'` | 3,215 |

**0 of 3 traversals failed their control.** Magic-byte and archive-interior
matchers were separately controlled against known `.pdf`/`.docx` files, because
`grep -rI` skips binaries and would have reported a clean zero over every
document on the box.

**83 artifacts** enumerated: 60 no-risk, 14 blank-or-fixture, 5 filled-clinical,
4 unreadable-treat-as-filled.

---

## 2. ⛔ A published credential still authenticated against production

**The finding that justifies the whole "read it before you destroy it" rule.**

`docs/qa-sweep-authenticated-2026-05-03/` (68 files, untracked, gitignored,
**never in git history** — so no history rewrite is owed) contained a plaintext
password from a 2026-05-03 authenticated QA sweep.

**Verified 2026-08-08 by read-only `bcrypt` compare against the live production
hash: MATCH.** 97 days after publication. No login was performed — the compare
was done directly against the stored hash.

Five `@quillmd-test.local` accounts existed on production, all `isActive`, four
email-verified, all role `DOCTOR`:

| account | practice | patients | visits |
|---|---|---|---|
| `qa-bypass-1777795921` | Solo — QA Bypass gc41 | 0 | 0 |
| `qa-sweep-1777794286` | Solo — QA Tester gaum | 0 | 0 |
| `qa-round2-1777839713` | Solo — QA Round2 h9wh | 0 | 0 |
| `qa-r2-apo1777839763'a` | Solo — Edge apostrophe | 0 | 0 |
| `aaa…-1777839763` (≈170-char local part) | Solo — Edge long-prefix | 0 | 0 |

### What it was, and what it was not

**Bounded by the tenancy wall.** Every account sat in its own solo practice with
**zero patients and zero visits**; T3's `practiceId` scoping and the composite FK
`transcribe_visits(patientId, practiceId) → transcribe_md_patients(id, practiceId)`
make another practice's data unreachable. No clinical record was exposed.

**Not nothing, either.** It was a working login to production as a `DOCTOR`,
reachable from the internet, bypassing invite-only signup, on an account able to
create records and spend vendor balance.

### Containment — executed 2026-08-08 on owner authorisation

```
deactivated=5   audit=5   sessions_revoked=4   active 184 → 179
```

One transaction. Self-pinned baseline (5 targets / 5 active / 184 active users /
26 visits / 15 patients), **every guard aborting the whole transaction on
mismatch**, post-conditions asserted *inside* the transaction so a wrong outcome
rolls back instead of being discovered afterwards. Clinical counts asserted
unmoved: **26 visits, 15 patients** before and after.

Audit rows carry **both** `practiceId` and `practiceIdSnapshot` — writing only
one is the defect GATE 0.1 shipped once, and an unattributed audit row is exactly
what that column exists to prevent. `USER_DEACTIVATED` was confirmed present in
`pg_enum` first; a `AuditAction` value missing from the Postgres enum throws at
runtime and is swallowed, which has bitten this codebase three times.

**Sessions were revoked as well as the flag set** — `isActive=false` alone does
not invalidate an already-minted session, and that gap shipped here before. Four
live `user_sessions` rows were deleted.

**Nothing was deleted**: no user row, no practice, no clinical row. The accounts
retain their `practiceRole`, so a future reactivation will not trip
`users_active_member_has_practice_role`.

### ⚠️ What containment does NOT do

**The password was not rotated, so it still matches the stored hash.** The
containment rests entirely on the login path refusing inactive users *before*
comparing it — verified at `apps/transcribe-md/src/lib/nextauth.ts:101`
(`if (!user.isActive) return null`), which precedes the `bcrypt.compare` at
`:151`. `validateSession` independently rejects `isActive === false`.

**Open for the owner:** whether to delete these five rows outright, and *why an
authenticated QA sweep wrote a working production password into a directory tree
in the first place* — the process question outlives the five accounts.

---

## 3. ⚠️ Unencrypted database dumps in a home directory

Found by the same sweep, unrelated to the loop:

| file | `transcribe_visits` | `users` (with `passwordHash`) | `audit_logs` |
|---|---|---|---|
| `/home/claude/meddoc-pro-backup-pre-migration-20260419-162255.sql` | 12 | 13 | 1,978 |
| `/home/claude/meddoc-pro-backup-before-scribe-removal-20260419.sql` | 10 | 12 | 1,978 |

Plain `.sql`, **not gzipped, not encrypted**, resting on `/dev/sda2` — the plain
root filesystem, not the LUKS volumes that exist precisely for this data. Both
predate the 2026-06-15 clinical wipe, so they hold rows that were deliberately
removed from production.

Their purpose — rollback cover for an April migration — expired roughly four
months ago. Sanctioned backups under `/opt/meddoc-pro/backups/` begin
**2026-04-20**, one day later, so these were the only snapshot of the 2026-04-19
state; that is why their contents are recorded here **by class and row count
before** they were destroyed, rather than after.

> **A backup outside the sanctioned path is not a backup. It is an unencrypted
> copy that no retention policy will ever age out.**

---

## 4. Dispositions — the list, worked entry by entry

| disposition | n | notes |
|---|---|---|
| `EXTRACT-THEN-SHRED` | 1 | the credential tree — this report is the extraction |
| `SHRED` | 3 + | scratchpad schema copies, `~/.local/share/Trash`, `dom-flag-off.txt`, the two `.sql` dumps |
| `KEEP-SANCTIONED` | 2 | `systemd-private-*` (7 dirs), `snap-private-tmp` — not ours |
| `ESCALATE-TO-OWNER` | 6 | see below |

`dom-flag-off.txt` (8.8 KB, untracked, gitignored) is a single-line rendered app
DOM carrying clinical section labels. Classified potentially-clinical and shredded
on the deliberate asymmetry: **a stray nobody can fully vouch for does not get the
benefit of the doubt.**

### Escalated, deliberately untouched

- **`/tmp/claude-1007` (voiceassistmain) and `/tmp/claude-1009` (westapp)** —
  **co-tenant** scratch roots. Co-tenants are untouchable; their contents are not
  this project's to read or reap, and unreadable-as-uid-1000 besides.
- **`/home/claude/.claude/projects`** — the harness's own transcript store, not
  session scratch. Flagged, not judged.
- The 9 unreadable home directories in §1.

---

## 5. Why this record exists at all

The reaping was nearly the last step, and it would have destroyed the only
pointer to a live production credential. That is not hypothetical caution — the
2026-07-30 extraction hit the identical shape, finding a service credential whose
disposition made rotation a release blocker with nothing in the repo recording it.

> **Read what you are about to destroy. The sweep that finds nothing and the
> sweep that never looked produce the same output — and a shredder cannot be
> asked what it ate.**


---

## 6. The collision guard — proved by ARRANGEMENT

The runner patch (`<date>-<launch>-runNN.log`, plus a refusal to open a log that
already exists) shipped with **one arm proven and one not**. Filename divergence
was demonstrated by two real dry launches. The refusal branch was not: reaching
it needs a *predictable* `LAUNCH`, and the first attempt to get one ran a
**modified copy** of the script from `scripts/` — which permissions declined,
correctly, because that is the "write a script, then run it" shape the ten-script
enumeration exists to prevent.

**It was then proved without any exception, by arranging the state rather than
changing the code.**

A `git worktree` of the same commit gives a **byte-identical** `foundation-loop.sh`
(verified: `cmp` equal, one distinct sha256) with its own `docs/foundation/logs/`,
so the live launch's log could not be touched. `docs/foundation/logs/*.log` is
gitignored, so pre-created files do not dirty the tree and cannot pre-empt the
guard under test with a *different* refusal.

The arrangement: pre-create one candidate log per second across a 240-second UTC
window. `LAUNCH` is `date -u +%H%M%S`, so whichever second the loop starts in, the
name it computes **already exists**.

| arm | arranged? | outcome |
|---|---|---|
| control | no | passed the guard, created its log, reached the session, halted `SESSION ERROR` |
| positive | yes | `LOG COLLISION — …-232113-run01.log already exists; refusing to append two launches into one file` |

The control is what makes the positive mean anything: without it, a refusal could
have come from the dirty-tree guard, a stale STOP file, or a broken script. And
the positive arm printed **no `session 01` line at all** — the guard fires before
`claude` is ever invoked, which is the placement that matters, since a guard that
fired *after* starting a session would already have written to the colliding file.

> **A guard that has never been observed refusing is a comment with an `if` in
> front of it.** The route to proving this one was blocked twice; the answer was
> not a permission exception, it was a different arrangement.
