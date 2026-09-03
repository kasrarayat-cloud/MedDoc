# ADMIT ONLY WHAT YOU UNDERSTAND; REFUSE LOUDLY WHERE THE DOCTOR CAN ACT

**Standing 2026-09-03, ruling #174 — the terminal rule of a nine-ruling arc.**

> **When you cannot characterise an input, do not accept it and then try to
> prove things about it. Refuse it at the door, by name, to the person who can
> change it.**

## The arc, in one shape

A renderer accepted every content control a doctor's `.docx` contained, then
tried to certify claims about what those controls would render. Six
formulations of the certification guard were falsified; the seventh pass found
four *more* routes:

| what survived | where |
|---|---|
| a Wingdings tick, a drawing, a `w:fldSimple` | inside `w:rPr` / `w:pPr`, copied verbatim |
| a live dropdown list | inside `mc:AlternateContent`, so the type marker was missed |
| a live dropdown list | inside a **second** `w:sdtPr` |
| a run bearing real text | inside the outer `w:sdtPr`, never inspected |

**They looked like four bugs and were one:** admitting shapes nobody had
characterised, and paying for it downstream forever.

⚠️ **AND "A SECOND ELEMENT OF THE SAME NAME" COST THIS CODEBASE THREE SEPARATE
TIMES** — a second `w:sdtContent` rendered a drug name out of a control proofed
`emptied`; a second `w:pPr` defeated the numbering guard; a second `w:sdtPr`
defeated the selection exclusion. Each was fixed where it was found. None of
the fixes generalised, because the question *"is this control a shape we
understand?"* was never asked.

## The rule

**Admission is an allowlist of SHAPES, checked at compile:**

- exactly one of each singleton (`w:sdtPr`, `w:sdtContent`) — duplicates refuse;
- the type marker resolved by **one consistent method** for every marker;
- every property block containing only property nodes, checked recursively.

**A refused control keeps the doctor's text verbatim** as static content and
appears as a per-field finding — *unsupported control structure* — at upload.

## Why the placement is the point

The same refusal at proof time is invisible: a field silently fails to certify
and nobody knows which, or why, or what to change. At **compile** it is a
sentence in the doctor's own upload report, naming the control, while the
document is still in their hands.

> **Fail-closed is only half a design. The other half is telling someone.**

## ⚠️ THE COST IS MEASURED BEFORE THE RULE SHIPS, ALWAYS

A refusal rule that refuses real documents is worse than none, and this arc had
already shipped one: a table-style check that refused **56 of 56** real named
tables because 85.9% of table styles carry `w:basedOn`.

So admission was measured on every real artifact first: **0 of the owner's 35
controls refused, 0 of the customer template's 28** — with a positive control
proving the reader could see a refusal when one existed.

⚠️ **AND ONE AMBIGUOUS NAME IS EXEMPTED BY POSITION, NOT BY NAME.** `w:tab`
inside `w:tabs` is a tab-stop definition — pure formatting, present on 52 real
fields — while `w:tab` inside a run is a tab character. A flat denylist would
have refused all 52. **When a name means two things, disambiguate by where it
sits; never by hoping.**

## The practice

- Write down the shapes you accept. If you cannot, you do not have a spec, you
  have a corpus.
- Put the refusal at the earliest point where a human can act on it.
- Measure the refusal against every real input you have **before** shipping it,
  and report the number.
- ⚠️ **A rule that closes four findings at once is worth more than four fixes,
  and is usually a sign the four were symptoms.** Look for it before patching
  the third one.
