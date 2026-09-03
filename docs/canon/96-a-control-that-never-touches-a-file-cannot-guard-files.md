# A CONTROL THAT NEVER TOUCHES A FILE CANNOT GUARD FILES

**Standing 2026-09-03, ruling #173.**

> **A positive control must be able to fail in the DIMENSION the instrument
> fails in. Exercise the instrument's real input path, not a convenient
> substitute for it.**

## The specimen

A lint was built to stop a recurring test defect — a bare `.find()` on a
non-unique predicate — after the same laundering was found and fixed **four
times in one arc**, the fourth inside the very arm re-armed for the third. It
was built as a mechanism precisely because remembering had failed.

It scanned **line by line** with a single-line regex. Prettier wraps any call
long enough to matter, so:

```
gate files scanned: 55
MISSED  blank-proof.test.ts:94    MISSED  blank-proof.test.ts:127
MISSED  compiler.test.ts:66       MISSED  picks-bridge.test.ts:139
```

**Four live offenders in its own watched directories, and it caught none.** It
reported a clean zero.

## ⚠️ WHY THE ZERO WAS BELIEVED — AND THIS IS THE ENTRY

It had a positive control. Two, in fact:

```ts
expect(KIND_FIND.test("const x = list.find((f) => f.kind === 'filled');")).toBe(true);
expect(KIND_FIND.test('const x = list.find((f) => f.fieldId === id);')).toBe(false);
```

Both pass. Both are **string literals in memory**. They prove the regex matches
a string — never that the regex is wired to file contents, and never that it
survives the line-splitting that actually defeated it.

**Repointing the scan from file CONTENT to file NAMES leaves the gate a total
no-op and both controls still green.**

That is [canon 31](31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md)'s
*control aimed where the answer is predetermined*, committed inside the fix for
[canon 62](62-overlapping-guards-must-not-launder-an-unproved-arm.md).

## The sibling, found the same day

The companion arm asserted that every canon entry has an index row — by
`grep`ping the WHOLE file. One entry is also quoted in the live-rules section,
so **deleting both of its index rows left the arm green**, while its own failure
message said it was checking the index.

Same shape: the assertion named a set the instrument was not reading.

## The practice

- **Plant a real offender in a real file and assert the gate finds it.** The
  control's input must travel the instrument's actual path — filesystem read
  included.
- **Tie the floor to the measured corpus.** `scanned > 10` against a real 55
  let an entire watched directory be deleted silently. A floor is a ratchet: it
  may grow, never shrink unopposed.
- **Anchor a set-membership claim to the set.** Slice the region the assertion
  names before searching it.
- ⚠️ **AND STRIP COMMENTS BEFORE SCANNING SOURCE.** A file documenting a
  forbidden shape quotes that shape; a scanner that reads prose as code reports
  its own documentation as an offence, and the next reader silences the gate
  rather than obeying it. The same defect appeared in an adversarial lens's own
  parser the day before — it matched quotes inside a block comment and returned
  four lines of prose as data.
