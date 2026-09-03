# A GUARD WHOSE ONLY ARM IS REWRITTEN IS DISARMED UNTIL PROVEN OTHERWISE

**Standing 2026-09-03, ruling #175(3). A protocol rule for the mutation matrix.**

> **Every mutation re-runs after ANY arm edit. Editing a test is a change to the
> instrument, and an instrument that changed has not been calibrated.**

## The specimen

A refusal was moved from the renderer to the compiler — a good change, and the
whole point of the ruling that ordered it. Two arms that asserted the *old*,
later refusal were updated to assert the *new*, earlier one.

One of those arms was the **only** arm on a live renderer guard: the rule that a
property container may not hold a `w:r`. Rewritten to assert
`bodyProofs.length === 0`, it became satisfied by the neighbouring compile-time
refusal — so the renderer guard it had been holding was left with nothing
watching it.

**Measured afterwards: deleting that guard reds 0 of 5638.** With it gone, a
`w:sym` inside `<w:sectPr><w:r>` goes from `filled` to a **verified `emptied`
proof with the tick still in the document.**

⚠️ **AND MY OWN COMMENT ON THE REWRITE SAID SO WITHOUT NOTICING:** *"this
document no longer reaches it."* That sentence is the finding. It records that
the arm stopped exercising the guard and does not draw the conclusion.

## Why the matrix did not catch it

The matrix had been run **before** the arm edits, against the old arms. It was
6 of 6. Nothing re-ran it afterwards, because the edits were "just tests" — and
a mutation matrix measures the pair (code, arms). Change either half and the
previous result describes a system that no longer exists.

## The protocol

- **After ANY arm edit, re-run the whole matrix.** Not the mutations that seem
  related — the whole set. The disarmed guard was one nobody was thinking about.
- **When a refusal moves earlier, ask what the later one has left.** Moving a
  check upstream is usually right and usually leaves a downstream guard
  redundant *in the reachable set* while it stays live for every other caller.
- **Say which:** either the guard is genuinely unreachable — record that as an
  honest limit with the reason — or it is reachable and it needs an arm of its
  own, not a shared one.
- ⚠️ **A GREEN MATRIX IS A TIMESTAMP, NOT A PROPERTY.** It says "at that commit,
  with those arms, each mutation redded." It says nothing about the tree after
  the next edit to either side.
