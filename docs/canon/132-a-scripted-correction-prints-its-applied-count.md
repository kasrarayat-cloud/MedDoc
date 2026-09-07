# A SCRIPTED CORRECTION PRINTS ITS APPLIED COUNT AND **REFUSES ON MISMATCH**

**Ratified 2026-09-07.** The sibling of *"a scripted edit PROVES ITS OWN
APPLICATION"* — same defect, in a script that writes to **production data**
rather than to files.

## THE INSTANCE

A script was to correct **ten** of fifty-three semantic mappings before
certifying a clinical template, because the model's proposals were wrong on two
of them: `Past Surgical History` → `past_medical_history`, and
`Marital status` → `social_history.occupation`.

**It applied ZERO.** The workspace row is `{ definitionId, field, mapping }` and
the script read `displayOrder` and `fieldId` off the row rather than off
`.field`, so every lookup returned `undefined` and no correction matched.

**Nothing threw. The script ran to completion and would have certified both
wrong concepts** — printing the patient's MEDICAL history into a SURGICAL
history field, and their OCCUPATION into marital status, in a signed note.

> **It was caught by ONE LINE OF OUTPUT: `manual: 0`.**

## THE RULE

> **A script that applies N corrections states N, measures what it actually
> applied, prints both, and REFUSES when they differ.**

```ts
const expected = Object.keys(CORRECTIONS).length;
const applied  = next.filter(isCorrected).length;
console.log(`corrections expected ${expected} / applied ${applied}`);
if (applied !== expected) throw new Error(`REFUSING — ${applied} of ${expected} applied`);
```

⚠️ **A DRY RUN IS NOT THE CONTROL — THE COUNT IS.** This script HAD a dry-run
mode and the dry run was run. It printed a correct-looking field map and the
silent zero sat one line below it. What made the difference was a number that
could be compared against an expectation, not a human reading a list.

⚠️ **AND THE SHAPE GENERALISES BEYOND SHAPE-MISMATCH.** Any correction keyed by
lookup — a map, a filter, an id match — fails silently when the key is wrong,
and the wrongness is invisible in the output it does produce. The count is the
only thing that distinguishes *"nothing needed correcting"* from *"my key was
wrong"*, and those two readings are opposite.
