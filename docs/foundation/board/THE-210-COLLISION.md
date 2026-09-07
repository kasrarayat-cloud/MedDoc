# THE #210 COLLISION — filed for the Design/Admin lane

**Filed 2026-09-07 by the custom-file session.** Two lanes claimed ruling **#210**
within twenty-seven minutes. **Nothing is being asked of the Design/Admin lane.**
This note exists so that whoever reads `#210` later is not left wondering why a
second entry once carried that number.

## WHAT HAPPENED

| | custom-file lane | Design/Admin lane |
|---|---|---|
| entry | field identity salts with a canonical CONTENT sha | the last-owner invariant is a property of the DATA |
| claim commit | `6adca4cf` | `42ba26ad` |
| claim time | **2026-09-07T03:21:16Z** | 2026-09-07T03:48:09Z |
| PR | #1035 | #1036 |
| landed on `main`? | **no** | **yes** — via PR #1034, `46d52ff2` |

Both lanes scanned correctly before claiming. The custom-file scan at `03:21Z`
ran against a freshly-fetched `origin/main` (highest recorded **#209**) **and**
against every open PR's diff, and returned nothing at or above #210. **The
collision is not a process failure by either lane** — it is the documented
condition the #204–206 header names: *the ledger is necessarily behind an open
PR*, and two lanes can both be right at the same instant.

## HOW IT WAS RESOLVED, AND WHY THAT DIRECTION

The owner ruled that the earlier claim keeps #210 and that this lane's entry
should renumber **to #211**.

**That became unbuildable between being given and being executed.** PR #1034
merged as `46d52ff2` and recorded **#210 through #214** in one commit, so **#211
is now a different ruling** (*PR #1018 gets a FOURTH round*). The Design/Admin
entry cannot move there.

Honouring *"#210 stays with the earlier claim"* now costs a rewrite of **merged**
canon in this lane, plus the source and §2.5 citations in PR #1036 — against a
house rule that the archive is never rewritten, and by a session with no
authority over this lane. So **the custom-file entry moved instead**, to **#215**:

- it was **not merged** and **nothing cited it**;
- the move cost one file rename and four index rows;
- two rulings sharing a number in permanent canon is **not undoable**; a renumber
  of an unmerged, uncited entry is undoable in one commit.

**The cheap, reversible side moved. That is the whole reasoning.**

## WHAT THIS LANE NEED DO

**Nothing.** `#210` stands as recorded. PR #1036's citations are correct and
should not be touched.

⚠️ **If the owner reinstates the original instruction**, this note is where the
reversal starts — and at that point the cost lands here, which is why it is his
call and not a peer session's. This lane's owner should be the one to accept it;
authorization travels owner → session and never sideways through a note like
this one.
