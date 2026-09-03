# A template whose controls are ALL refused reads as "no fillable fields"

**Filed 2026-09-03, from ruling #175's final adversarial pass (lens B, finding 3).**
**Not fixed in that commit**, because it is not "a shape leaving the admitted
set" and #175(4) permitted no further pass. Recorded here so the next reader
finds it rather than rediscovering it.

## The defect

`#175(2)` built the loud half of #174: a refused control blocks certification
and names itself in the doctor's upload report, so the instruction is *simplify
this control in Word*.

That works while **some** controls survive admission. When **every** control on a
template is refused, the compiled IR has zero fields — and the surface that
handles zero fields predates all of this. It says the document has **no fillable
fields**, which is the opposite instruction: it tells the doctor their file is
the wrong kind of document, when in fact it is exactly the right kind and every
control in it needs one edit.

⚠️ **The two states are indistinguishable to the doctor and opposite in what they
ask of them.** A plain prose document genuinely has no fields. A document with
twenty content controls the compiler refuses has twenty things to fix, and the
list that would say so is suppressed by a count that reached zero.

## Why it is not merely cosmetic

The refusal path was built precisely because *"fail-closed is only half a design;
the other half is telling someone"* (canon 97). A total refusal is the case where
the telling matters MOST — the template is entirely unusable — and it is the one
case where the telling is replaced by a message pointing the wrong way.

## What would close it

The empty-fields surface must distinguish *nothing was found* from *everything
found was refused*, and render the findings list in the second case. The data is
already there: `blockingUnsupportedCount` and `unsupported` are populated on the
compiled version whether or not any field survived — the zero-field branch simply
never consults them.

## What must be true of the fix

- An arm driving a template where **every** control is refused, asserting the
  findings list renders and the "no fillable fields" copy does NOT.
- The mirror arm — a genuinely field-free prose document still says "no fillable
  fields" — so the fix does not simply swap one wrong message for another.
- Both, because this is a split family and a one-sided fix is blind in the
  direction it did not add (canon 34).
