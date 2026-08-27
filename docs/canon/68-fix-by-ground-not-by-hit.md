# FIX BY GROUND, NOT BY HIT

**Ratified 2026-08-27.**

> **A defect's fix covers the MECHANISM'S CLASS, not the nodes the measurement
> happened to exercise.** A scan reports what it met; the mechanism does not
> care what the scan met.

⚠️ **REFERENCE CASE, AND ITS SPECIMEN IS ONE LINE.** The coding panel's contrast
failures had a single mechanism: the panel's **chrome** is transparent up to the
paper ground (`--rounds-paper-1`, #fcfcfa) while using the **dark** text ramp,
whereas its **cards** paint `--rounds-surface-1` themselves, where that ramp is
correct.

The measurement — an axe sweep plus an independent ratio audit, on two visit
states — found **12 failing nodes, all on paper, zero on cards.** A fix scoped to
those twelve would have been complete against the evidence and **wrong**.

**`icd-empty` is the specimen.** It is the *"no codes in this section"* message.
It uses the same token (`--rounds-text-3`) on the same paper ground as four
confirmed failures. It appeared in **no** result, from either instrument, in
either state — because both walk visits had codes in every section, so the
element never rendered.

**It was fixed anyway, and that is the entry.** Not because it was measured, but
because it is on the wrong side of the same boundary. The next doctor to open a
visit where one section is empty would have met a 3.59:1 message that no scan had
ever seen.

## THE PRACTICE

1. **When a defect is found, name its MECHANISM in one sentence** — here: *"panel
   chrome uses the dark ramp on a light ground."* If you cannot write that
   sentence, you have a symptom list, not a diagnosis.
2. **Enumerate the class from the SOURCE, then partition by the mechanism's
   discriminator** — every token use in the file, split by which ground it lands
   on. Not "the lines the tool printed."
3. **State the members you fixed that were never observed failing, and why.** An
   unmeasured fix is the one a reviewer will challenge, so it carries its
   reasoning: *same token, same ground, not exercised by the walk.*

⚠️ **AND THE INVERSE IS EQUALLY THE RULE: DO NOT FIX ACROSS THE BOUNDARY.** The
cards were left completely untouched. Their near-white text is correct *on their
own dark ground*, and "fixing" them to match would have broken a surface that
was passing. **The mechanism defines both what is in and what is out** — a sweep
that recolours every instance of a token, everywhere, is the same error pointed
the other way.
