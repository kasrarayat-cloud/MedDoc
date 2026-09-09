# TAG-ON-INGEST — the app derives a tagged twin, so a re-upload transfers by tag

**Filed 2026-09-08 under owner ruling, for the upload-and-certified arc. Not
this lane's to build now; it is the case the #274 identity contract leaves open
by design.**

> At first ingest the app derives a **tagged twin** of the doctor's source — a
> deterministic `w:tag` per control — with **the doctor's own bytes untouched
> and stored beside it**. Every later re-upload of the tagged copy then
> transfers by tag.

## WHY IT EXISTS — the measured gap

#274's identity contract is **final** at two keys:

| key | scope |
|---|---|
| `fieldId` | universal and exact — **identical bytes only** |
| `tag` + part + kind | the author's semantic name; survives renumber, rename and insert |

Everything else was tried and deleted, each after a **blocking clinical
defect**: a positional key (round one), a collision that mis-transferred (round
two), a bare `sdtId` (round three), and `sdtId` paired with the label (round
four). The full account is in `ingest-plan.ts`.

**So on CHANGED bytes, a control with no tag re-proposes.** Measured on
`WM IOV Template.docx`:

| | |
|---|---|
| fields | 80 |
| carrying a `w:tag` | **1** |
| carrying an alias | 1 |
| distinct labels | 26 |
| **adjacent pairs sharing a label** | **14** |

⚠️ **79 of 80 controls have no durable identity of any kind.** That is the case
this item exists for: a doctor who edits and re-uploads their own form loses
every certification, and there is nothing in the document to prevent it —
because the document never carried anything to identify its controls by.

## ✅ SETTLED 2026-09-09 — THE MEASUREMENT RAN, AND THE OWNER WAS RIGHT

The re-issue act's recorded measurement, taken from the pinned artifact's
inflated XML before the act and gating nothing:

```
w:tag attributes on the artifact : 53
w:sdt controls on the artifact   : 53
xml parts inflated and scanned   : 13
```

**53 of 53. Every control carries a tag.** The section below argued 18 was the
verifiable floor and 53 unconfirmed; **that was wrong and is kept as written**,
because the correction is the point. What could be proved *from the repository*
was 18; what is true of the artifact is 53.

⚠️ **AND THE `parts` LINE IS WHY THE NUMBER IS TRUSTWORTHY.** An earlier draft of
the census scanned the COMPRESSED package and would have reported **0** — a
`.docx` is a zip, so `<w:tag` lives in deflated bytes. Reporting the count of
inflated XML parts alongside the total is what makes a zero readable as "no
tags" rather than "nothing was opened".

⚠️ **BUT 53 TAGS IS NOT 53 IDENTITIES — AND THAT IS THE FINDING THIS ITEM MUST
CARRY FORWARD.** Measured on the certified version: **53 tags, 35 DISTINCT.**
`plan` appears five times, `impression` four, `past_medical_history` three. A
tag shared by five controls identifies none of them.

> **THE SCOPE THIS CHANGES:** TAG-ON-INGEST is narrower than filed for
> *coverage* — the owner's form needs no derived tags at all — and **wider than
> filed for UNIQUENESS**. A derived tag must be unique per control, which the
> owner's own authored tags are not. Deriving `plan_1 … plan_5` would give the
> form five identities where it has one; that is a product decision about
> whether a re-upload should preserve those five controls' certifications
> individually, and it is the real question this item now asks.

---

## THE ORIGINAL ARGUMENT, KEPT AS WRITTEN AND NOW SUPERSEDED

The ruling states the owner's form is **53/53 tagged**. What is verifiable from
this repository is **18 of 53**:

- `regenerate-consult-form.ts` emits `<w:tag w:val="…"/>` for each of the
  **18 controls it adds** (`EXPECTED_ADDED = 18`) — `ros_gi_heartburn`,
  `exam_lungs`, `telehealth_consent`, and so on.
- The other **35** come from the owner's blank source, whose bytes are **not in
  this repository** (`EXPECTED_SOURCE_CONTROLS = 35`). Their `w:tag` status is
  unknown here. The provenance record's P3 proof says *"`w:sdt` tags balanced"*,
  which is **XML nesting, not `w:tag` attributes** — a near-homograph worth
  naming, because it reads like confirmation and is not.

**What this does and does not change:**

- **It does not touch the re-issue act.** That ingests the *pinned artifact* —
  identical bytes — so all 53 transfer on `fieldId` and no tag is consulted.
- **It does change this item's scope.** If the 35 are untagged, the owner's own
  form has the same gap as WM IOV for a future edited re-upload, and
  TAG-ON-INGEST is needed for it too rather than only for third-party forms.

**One query settles it**, against the compiled version in production:

```sql
select count(*) filter (where rb->>'tag' is not null and rb->>'tag' <> '') as tagged,
       count(*) as total
from template_twin_field_definitions fd,
     lateral (select fd."rendererBinding"::jsonb as rb) x
where fd."compiledVersionId" = '<the certified version>';
```

Until it is run, **treat 18/53 as the floor and 53/53 as unconfirmed.**

## SHAPE, AND THE CONSTRAINTS IT MUST RESPECT

1. **The doctor's bytes are never modified.** The original is stored as it
   arrived; the tagged twin is a *derived* artifact beside it. The store is
   content-addressed and put-once, so both coexist naturally.
2. **The tag is DETERMINISTIC per control**, and must not be derived from
   anything positional — that is the whole lesson of rounds one, three and four.
   Deriving it from position would reintroduce the defect one layer up, where it
   is *harder* to see because it now looks like an author's name.
3. ⚠️ **A DERIVED TAG IS WEAKER EVIDENCE THAN AN AUTHORED ONE, AND THE CODE MUST
   NOT FORGET WHICH IT HAS.** `exam_lungs` written by a human means "this is the
   lungs control". A tag the app minted means "this was the seventh control the
   day we ingested". They must not be indistinguishable at the seam that decides
   whether a certified clinical disposition moves.
4. **The doctor must re-upload the TAGGED copy** for any of this to help — which
   is a product decision about what they are handed and told, not only an
   engineering one.

## ACCEPTANCE

- the doctor's original bytes are byte-identical before and after ingest
- the tagged twin compiles to the same control count and the same order
- a re-upload of the tagged twin after an edit transfers every unmoved control
- **the corpus arm proves it on `WM IOV Template.docx`** — the document where
  1 of 80 carries a tag today — under the same five transformations #274 uses
- an authored tag and a derived tag are distinguishable in the record
