# YOUR-BLANKS-2 — the panel lists EVERY refused control, not only scaffolded narrative ones

**Filed 2026-09-08 to Design/Admin under ruling #279.** This is the **surface
half of #272**; the custom-file session built the other half and could not build
this one.

> The *"Your blanks"* panel lists **every control whose fill was refused with a
> named reason** — record-derived refusal, ambiguous age, `manual` — **not only
> scaffolded narrative controls**, with a **kind-aware input** (a **number**
> field for age).

## THE TWO HALVES

| half | where | state |
|---|---|---|
| the document RENDERS, blank, with the reason in the manifest | #272 | **built** |
| the doctor can SEE and FILL that blank | **#279 / this** | **open** |

## WHY THE CLAUSE COULD NOT BE BUILT WITH THE OTHER HALF

#272 orders a refused control *"routed to the doctor's own fill (the Your blanks
surface), exactly as a manual field"*. Measured: the panel is gated by
`scaffoldDefaultOfferable`, which requires `scaffolded === true`, a non-empty
`scaffoldText`, and `kind === 'narrative_text'`.

**An age control has no scaffold wording and is not narrative, so it can never
appear there as built.** The ruling's arm was deliverable; its surface clause
was not.

## ⚠️ AND #275's RE-PASS MEASURED THE GAP PRECISELY — TWO SEAMS, EITHER ONE CLOSES IT

Two independent lenses landed on the same chain, and verifying it re-anchored
the defect away from where both of them first pointed.

**Seam A — the reason never leaves the server.**
`apps/transcribe-md/src/actions/preview-visit-document.ts:368-372` projects only

```ts
counts = {
  filled: prepared.manifest.counts.filled,
  needsReview: prepared.manifest.counts.needsReview,
  notMentioned: prepared.manifest.counts.notMentioned,
};
```

Every per-field `reasonCode` the manifest carries is dropped here. `validation`
does not ship either. So `age_timezone_ambiguous` **cannot** reach the client,
and no surface can key on it however it is written.

**Seam B — the caption asserts a CAUSE it cannot support.**
`apps/transcribe-md/src/app/visits/[id]/visit-document-surface.tsx:208-212`:

```tsx
{result.counts.notMentioned > 0
  ? ` · ${result.counts.notMentioned} still blank — nothing dictated for those yet`
  : ''}
```

⚠️ **THE BUCKET IS CORRECT AND THE SENTENCE IS NOT.** Routing a
`not_mentioned` into `notMentioned` is what **#194** mandates, so `ir.ts` is a
correct link in this chain — both lenses first named it as the defect and both
were wrong. What is wrong is a caption that explains the whole bucket with one
cause, when the bucket now contains blanks **nothing can ever dictate**.

> *"A blank labelled 'nobody mentioned it' is a blank the doctor cannot act on —
> they would look for the dictation."* — `resolver/index.ts:61`, the branch's own
> words, describing the state its counts still produce.

## ⚠️ THIS PREDATES #272, AND THE POPULATION IS LARGER THAN THE AGE WORK

Measured: `manual_source_not_filled` and `awaiting_note_selection` **already**
land in that bucket under that caption on `main`. #272 adds a fourth member to
an existing class; it did not create it.

And the largest member is not the ambiguity window at all — **`age_input_absent`
(any patient with no DOB on file)** reaches the identical output, a far bigger
population than the ±26h boundary case. Conversely the diff-introduced share is
*narrower* than it looks: only the timezone-ambiguous case previously filled,
while the no-DOB case previously withheld the document entirely.

**So the fix is worth more than #272 needed** — which is exactly why #279 scopes
it to *"every control refused with a named reason"* rather than to age.

## WHAT MAKES IT SURVIVE THE NEXT REFUSAL TOKEN

Key the panel on **the reason** — *"was this fill refused, and was it named?"* —
never on the field's scaffolding or its kind. The vocabulary is already shared
and, since #275's re-pass, **typed**: `RecordDerivedRefusal` and
`isRecordDerivedRefusal` in `ir.ts`. A panel that reads those inherits every
future token for free; a panel that re-lists them drifts the day one is added.

## ACCEPTANCE

- a control refused with a named reason is **listed**, whatever its `kind`
- the input is **kind-aware** — a number field for age, not a textarea
- the `notMentioned` caption no longer asserts a cause for blanks that have one
  of their own
- `manual_source_not_filled` is listed too — it renders blank and reaches no
  surface today, and it predates the age work
