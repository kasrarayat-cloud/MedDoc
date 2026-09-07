# A CONTROL THAT PASSES UNDER THE VERY CONDITION IT EXISTS TO DETECT IS NOT A CONTROL

**2026-09-06. Owner canon, from a night in which this shape was measured FOUR
times in one file, twice inside arms written to close the class.**

A control earns its name by going RED when the thing it watches for is present.
An assertion that stays GREEN under that condition is not a weak control — it is
**not a control**, and it is worse than none, because it occupies the place
where one would go.

## THE FOUR MEASURED INSTANCES, ALL IN ONE FILE, ALL GREEN

| # | the control | the condition it exists to detect | why it passed anyway |
|---|---|---|---|
| 1 | *"THE WRITER REFUSES TOO — the offer and the door agree"* | the door stops refusing | whole-file `toMatch(/unmentionedPolicy === 'omit'/)`, satisfied by **the comment explaining the deletion**. Code-only occurrences after stripping comments: **0** |
| 2 | *"the offer withdraws for an omit field"* | the offer withdraws when it should not | every arm shared one `blankNow` fixture in which the honoured and the refused resolution are **byte-identical** |
| 3 | *"THE DECISION IS NOT TAKEN FROM THE MAPPING"* | a static refusal re-added to the function | the body-slice ended at the first `\n}` and **stopped before the code** |
| 4 | *"THE MATRIX VARIES EVERY INPUT THE MIRROR READS"* | an input held constant | `field.kind` appears in the slice **only inside a comment** |

⚠️ **THE ADVERSARIAL PASS DEMONSTRATED IT RATHER THAN ARGUING IT.** For each, it
re-introduced the defect and ran the suite: **905 tests, 0 failures** with the
regression live. The control run — deleting a clause the arms *can* see — reds
four arms, so the harness was never broken. It simply could not see.

## ⚠️ AND THE SAME ARMS FIRE FALSELY, WHICH IS THE OTHER HALF

A line-prefix comment filter was defeated in both directions on the same night:

- a **loose `/*` block comment** with unprefixed continuation lines survives the
  filter and turns the arm RED with no code change;
- changing **one word inside a comment** in the test file reds the
  derived-dimension arm.

**A control that can be reddened by a comment is measuring the prose, and a
control that can be greened by a comment is measuring the prose. They are the
same defect, and they travel together** — both mean the assertion never located
the code.

## THE TEST, AND IT IS ONE QUESTION

> **Plant the condition. Run it. If it stays green, delete the control — it is
> telling you something false in the place you will look for the truth.**

Not "does this look thorough". Not "did the author reason well". *Make it fail.*

## WHAT TO WRITE INSTEAD

**Derive from the function, or use the parser.** A substring or regex over a
source file is a claim about characters, and prose is characters. Where the
subject is behaviour, **drive the subject**: the door in that file had **zero
executable coverage** and its guards deleted wholesale with **843 tests still
green**, while three whole-file string reads stood in for a test.

⚠️ **AND WIDENING BY HAND CLOSES AN INSTANCE, NEVER THE CLASS.** The matrix in
row 4 had been widened by hand three times, and each time the next held-constant
input walked straight through. Derive the dimensions from what the code reads.
