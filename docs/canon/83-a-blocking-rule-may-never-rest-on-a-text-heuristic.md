# A BLOCKING RULE MAY NEVER REST ON A TEXT HEURISTIC — ITS ERROR MODE IS "REFUSE THE WHOLE TEMPLATE"

**Recorded 2026-09-02, by owner ruling #164, which retires the rule this entry
is about.** Its sibling is
[canon 75](75-three-falsifications-is-data-about-the-instrument.md) — that entry
is about a heuristic doing SEMANTICS; this one is about what happens when you
wire such a heuristic to a REFUSAL.

## The rule, and both times it fired on the only real form we have

A compile-time rule was built to block a template whose selection control rests
on one of its own option values — a false assertion waiting to print. The
membership test itself is sound: `resting ∈ options`, exact, nothing to tune.
What decides its INPUTS is not.

| version | what it did to `WM IOV Template.docx` |
|---|---|
| first | matched Word's own `"Choose an item."` placeholder → **28 of 28 dropdowns BLOCKED** |
| second, "fixed" | matched the placeholder in **English only** → 0 blocked in `en`, **28 of 28 blocked in fr / de / es** |

Both measured. The second is the one to sit with: the repair for a
refuse-everything bug was another string match, and it refused everything again
the moment the doctor's Word spoke a different language.

Six spellings of one clinical state produced different verdicts — `w:t` vs
`w:sym`, English vs localised, present vs omitted state elements, text vs field
code, content control vs legacy, scalar vs repeating.

## The asymmetry that makes this its own entry

> **A FLAGGING rule's worst case is noise. A BLOCKING rule's worst case is that
> a doctor cannot use their own form.** Identical defect, incomparable cost —
> so a rule wired to a refusal must be held to a standard a rule wired to a
> warning need not be.

The standard: **a blocking rule may rest only on a signal the document
DECLARES** — an element's presence, a flag the authoring tool sets, an
enumerated schema value. Never on matching TEXT, in any language, however
carefully.

⚠️ **AND THE AUTHORITATIVE SIGNAL WAS USUALLY ALREADY IN HAND.** `w:showingPlcHdr`
— Word's own "this control still holds its placeholder" marker — was present on
**28 of 28** affected controls and was passed into the very function that
ignored it in favour of a string match. `w14:checked` was likewise available and
unread. That is [canon 80](80-lsmod-is-silent-about-built-ins.md)'s *ask the
owner of the state* one layer up: the heuristic was not chosen because the
authoritative answer was missing, but because it was easier to reach for.

## The practice

- **Before wiring a rule to a refusal, write down what it matches.** If the
  answer contains a string literal that a human wrote in a natural language, it
  flags; it does not block.
- **Ask what the rule does to the WHOLE population when its input is wrong.** A
  blocking rule that can be wrong about every field at once is one input bug
  away from an outage, and both of this rule's bugs were exactly that shape.
- **Test a blocking rule against the real artifact, in a condition you have not
  arranged.** Both failures were invisible to a synthetic fixture built by the
  author, and both appeared immediately against the customer's actual form.
- **Prefer NOT COUNTING to REFUSING** where the question is "may this satisfy a
  requirement?". #164's replacement does exactly that: a binding whose clearing
  is unproven does not buy a blank proof — no parse, no refusal, and nothing
  that can be wrong about a document.
