# CLEARING-BY-DELETION IS A FOUR-TIMES-FALSIFIED INSTRUMENT — THE FIX WAS TO STOP DELETING

**Recorded 2026-09-01, by owner ruling #163.** The sibling of
[canon 75](75-three-falsifications-is-data-about-the-instrument.md), one arc
later and one layer deeper — and where 75 says *escalate instead of building
layer four*, this one records what the answer turned out to BE.

## The rule, and its four falsifications

**"When a field is unfilled, the renderer clears its content."** Reasonable,
obviously desirable, and wrong four times:

| # | layer | what falsified it |
|---|---|---|
| 1 | **paragraph** | a FORMTEXT whose result carries a paragraph mark has its `separate` and `end` in the NEXT `w:p`; the walk saw neither and the stale value survived |
| 2 | **part** | widening the walk let an unbalanced `fldChar` run past its own field and **ERASE unrelated clinical text** — a patient's allergy line, with every guard green |
| 3 | **field balance** | a stray `end` closes the window early; the tail survives anyway |
| 4 | **element type** | `w:sym`, `w:pict`, `w:delText` carry no `w:t` and were cleared at NO scope — a Wingdings ✔ printed for a field the encounter never mentioned, proofed `emptied` |

Layer 2 is the one that matters most: **the repair for layer 1 produced a worse
harm than layer 1**. Leakage became deletion.

⚠️ **AND LAYER 4 WAS NEVER LEGACY-SPECIFIC.** The same glyph survived inside a
plain `w:text` **content control**, proofed `emptied`, `verified: true`. So it
was never a quirk of one binding type — it was the clearing machinery.

## Why no layer five exists

> **A renderer that deletes what it can CLASSIFY will always miss what it
> CANNOT — and every guard built on top inherits exactly that blind spot.**

The byte-equality proof could not see layer 4 because the writer's expectation
carried the same mistake as the writer: output and expectation agreed, exactly,
about a document with a check mark on it. **Two things computed from one wrong
model agree.** That is [canon 76](76-shared-authority-is-shared-blindness.md),
and it is why the proof got stronger while the harm stayed live.

An enumeration of visible elements is a text heuristic wearing a schema's
clothes. The next Word feature that puts a mark on a page — a new drawing
namespace, a content control type nobody here has met — is layer five, and it
arrives without a commit.

## The answer, which is an INVERSION rather than a fix

**STOP DELETING. A null is left UNPATCHED.**

The field keeps the template's own bytes — the doctor's own blank
representation — and thereby earns the ORIGINAL `kind:'blank'` proof through
**source-byte-identity**: the one proof in this programme that has never been
falsified. It becomes *universal across shapes* instead of available only to
fields nothing happened to touch, which is what made consult forms
uncertifiable in the first place.

All four layers retire at once, **by deleting their cause**. Not gated — deleted,
per canon 75's own closing rule, or the next reader repairs the machinery
instead of questioning it.

## And the residue moves to where a human can act

Leftover content in an unfilled field is real and now PRINTS. It is answered at
**COMPILE**, at upload, once:

> *"this field contains leftover content and will print on every note — clean it
> or accept it."*

⚠️ **THE ASYMMETRY IS THE WHOLE DESIGN, AND IT IS THE REASON THIS IS NOT A
RETREAT.** A wrong DELETION is silent, unrecoverable, and removes clinical text
nobody notices is gone. A wrong FLAG is loud, costs a doctor ten seconds, and is
fixed once at the template rather than every time a note renders. Runtime never
deletes what it cannot classify; the detector may over-report freely, because
over-reporting is survivable and over-deleting is not.

**One shape is exempt and BLOCKS instead:** a selection control resting on one of
its own option values is not decoration a doctor might keep — it prints as an
answer nobody gave. Deterministic set membership, nothing to tune.

⚠️ **AND EVEN THAT BLOCKING RULE WAS WRONG ON ITS FIRST TRY, IN THE DIRECTION
ONLY THE REAL FORM COULD SHOW.** Word seeds every dropdown with a first
`listItem` reading "Choose an item.", stored exactly like a real option — so the
rule refused **all 28 dropdowns of the customer's actual template**, converting
the soft case into a hard refusal of their entire form. The synthetic fixture
could not have caught it, because its comboBox rests on a genuine option.
*A rule about real documents is tested against the real document.*
