> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **9 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A DELETION IS SCOPED BY WHAT THE COMPONENT **DOES**, NOT BY WHAT THE RULING **CALLS** IT

**Standing 2026-08-14.** A ruling names an INTENT. A component has a JOB LIST.
The two are not the same enumeration, and the gap between them is where a
deletion over-reaches.

> **Before deleting a named surface, enumerate everything the component
> actually renders — then check each job against the ruling. Anything the
> ruling does not name is a decision you are making, not one you were given.**

⚠️ **REFERENCE CASE — ruling #109, "delete the Prescription Safety surface".**
The component it named had two jobs, and its host section's heading toggled
between them in one line:

    {props.rxHasWarnings ? 'Prescription safety' : 'Prescriptions'}

It rendered on `prescriptions OR warnings`. The ruling named the SAFETY job.
Deleting the whole component executed the ruling exactly as written and removed
the drafted MEDICATION LIST with it — the only dedicated card for it — while the
export path went on emitting a `MEDICATIONS` block into five EHR clipboard
formats, the PDF and the DOCX.

**Restored by owner ruling as a read-only list.** The safety surface and both
gate halves stayed deleted.

### ⚠️ AND THE RESTORE HAD THE SAME DEFECT ONE FIELD DOWN, WHICH IS THE HALF WORTH REMEMBERING

The restored card showed drug, strength, sig, quantity and refills — and no
ACTION. `visit-export.ts` appends an uppercase tag to every prescription whose
action is not `new`, so **a STOP ORDER rendered identically to a NEW START while
the signed PDF said `[DISCONTINUE]`.**

Measured on production the moment it was found: **44 of 53 prescription rows
carry a non-`new` action** — continue 33, hold 5, unclear 3, discontinue 2,
increase 1. The common case, not the edge. ⚠️ And `hold` was a value the deleted
component's own type union never listed, so the field is typed as a bare string:
**the wire is the authority, and switching on a closed set silently drops the
member nobody enumerated.**

> **An absent field is content the doctor did not see. A WRONG field is content
> that says the opposite of the record being signed. The second is worse, and
> restoring a surface can introduce it while fixing the first.**

A second divergence in the same pass: the card filtered
`typeof p.drug === 'string'` while the export's payload builder does not, so a
`drug`-less prescription was PRINTED into the signed record and DROPPED from the
card. The card now drops nothing the export prints, and a missing name renders
AS missing — a doctor can act on *"this row has no drug name"* and cannot act on
a row that is not there.

### THE GUARD IS A BICONDITIONAL PLUS FIELD PARITY, AND PRESENCE IS NOT ENOUGH

`gate-exported-medications-are-seen.test.ts` states the invariant as an equality
between the export's emit condition and the display's render condition, plus a
leg asserting the card is actually MOUNTED — **two predicates can agree
perfectly while nothing is on screen.**

⚠️ **THAT VERSION WAS GREEN THROUGHOUT THE ACTION DEFECT.** Presence is exactly
what let it through, so the gate now asserts FIELD PARITY: every action value
production holds plus the ones nobody typed, the tag TEXT itself (*a card
reading "STOPPED" against an export reading `[DISCONTINUE]` is two records*), and
that no row is dropped that the export prints.

⚠️ **AND THE GATE CAUGHT ITS OWN AUTHOR TWICE.** On its first run,
`hasDraftedPrescriptions` read `(blob?.prescriptions?.length ?? 0) > 0`, which
returns TRUE for a malformed `prescriptions: 'nonsense'` (length 8) while the
export's condition returns false. Then the field-parity arm caught the `drug`
filter. **A guard that reddens against its author on first execution is
discriminating rather than agreeing** — that is the strongest evidence a guard
can produce about itself.

### HONEST LIMITS, RECORDED SO THE GATE IS NOT READ WIDER THAN IT IS

- It mirrors **one of three** medication emitters. `pdf-generator.ts` and
  `docx-generator.ts` are unwatched, and docx gates additionally on
  `!data.formOnly` — which is DELIBERATE (form-only exports carry no chrome by
  design) and must not be "fixed".
- The mount leg is a substring scan and is defeated by a conditional render. The
  product has that shape one level up: the whole surface is behind
  `isReviewDocView()`, and the flag-OFF rollback path renders no medications at
  all.
- The mirrored export condition is not byte-faithful on the non-array-truthy
  case: the real export does not return empty there, it THROWS.

