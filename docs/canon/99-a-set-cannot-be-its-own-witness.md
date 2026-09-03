# A SET CANNOT BE ITS OWN WITNESS

**Recorded 2026-09-03, from the final adversarial pass of the #165–#175 arc.**

> **A loop that iterates the set under test deletes its own arm along with the
> member. The witness must come from OUTSIDE the set.**

## The measurement

`CONTENT_CARRIERS` in `compiler.ts` is the fail-closed allowlist of OOXML
elements that can PRINT inside a Word content control. A gate looped over that
very set, placing each member alone in a property block and asserting the
compiler refused it and NAMED it. It reads as exhaustive coverage: every member,
one arm each, no member unwatched.

Measured one member at a time — delete the member from the set, run the suite:

| deleted | suite |
|---|---|
| 23 of the 27 members | **redded NOTHING** |
| `sym`, `fldSimple`, `tab`, `drawing` | redded — and only because OTHER arms hard-code those literals |

⚠️ **THE FOUR THAT REDDED ARE NOT A PARTIAL SUCCESS, THEY ARE THE CONTROL.** The
looping arm caught none of the 27. Four were rescued by unrelated arms that
happened to name a string. Remove those four hard-coded literals and the gate's
coverage of its own set is zero.

## The harm, demonstrated

With `delText` removed from the set:

```
REFUSALS = 0     WARFARIN SURVIVES THE CLEAR = true
```

A doctor's stale drug text sat inside a kept-whole property block, was admitted,
**survived the clear verbatim, and earned counted-blank certification credit.**
Removing `txbxContent` — a text box's entire body — redded **0 of 756**.

## ⚠️ AND A SIZE FLOOR IS THE SAME DEFECT ONE LEVEL UP

The obvious guard against a shrinking list is a floor. `CONTENT_CARRIERS.size
>= 20` on a 27-member set does not stop deletion; it **caps the blast radius at
seven**. Deleting exactly seven dead members at once redded **0 of 756**.

The sibling list `STRUCTURE_KEEP_WHOLE` carried `>= 15` on 17 members, so
removing `permStart`/`permEnd` redded **0** — and the renderer then deletes them
from every cleared control.

A floor derived from the set's own current length is the set witnessing itself
with a smaller number.

## The cure, in two forms

1. **A SECOND list, written from an INDEPENDENT source.** Here:
   `RUN_INNER_CONTENT`, 33 element names transcribed from the OOXML
   `EG_RunInnerContent` schema group, covering 33 of the 43 members. The other
   ten — `r`, `p`, `tbl`, `sdt`, `fldSimple`, `txbxContent`, `oMath`,
   `oMathPara`, `subDoc`, `altChunk` — are block and field constructs, and got
   their own list for the same reason. The schema did not read the code, so a
   deletion from the code cannot delete the assertion.
2. **Or assert the PROPERTY directly** rather than the membership — drive the
   behaviour the member exists to produce, and let the set be an implementation
   detail of that.

## ⚠️ AND ONE ENTRY OF THE NEW LIST WAS REFUTED BY MEASUREMENT AND REMOVED

`w:tc` was on the second list, on the reasoning that a table cell carries
content. It does — but ONLY through `w:p`, which is already a member. A `w:tc`
holding stale text refuses today with `tc` **absent** from the set: **1 refusal,
identical to the `w:tbl` control.**

Asserting it would have pinned a member the code does not need — a spelling
frozen by a gate, which is [canon 72](72-pin-properties-not-spellings.md)'s
shape. Recording the refutation rather than quietly dropping it is
[canon 17](17-record-a-hypothesis-because-it-was-refuted.md): the next author
who reasons *a cell carries content* can look this up instead of re-deriving it.

## Honest limits

- **The second list is a DELETION DETECTOR, not a proof that each member is
  independently NECESSARY.** Several members are reachable only through other
  members that are present, so a neighbour would refuse without them. That is
  [canon 62](62-overlapping-guards-must-not-launder-an-unproved-arm.md) — an arm
  satisfied by a neighbouring guard is not an arm on the member it names.
- It pins the two lists against a SCHEMA, not against Word. An element Word
  renders that the schema group does not list is outside both.
- Nothing here says the looping gate should be deleted. It is a fine
  smoke-and-spelling arm; it is not a witness.

## The generalisable move

**Ask what the arm reads.** If it reads the same object the change edits, it
cannot disagree with the change — it is a mirror, and a mirror is green in both
directions.

The cheap mechanical check, and it costs one suite run per member:

    delete one member -> run the suite -> a green suite is a MISSING ARM
