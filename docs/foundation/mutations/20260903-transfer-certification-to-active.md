# RULED MUTATION — transfer the certified dispositions onto the ACTIVE copy

**Owner-ordered 2026-09-03, under the standing authorization.** Written and
committed **before the act**, which is what the strict gate on a ruled mutation
buys: the commit timestamp provably precedes the rows.

## WHY

The owner's **Gastroenterology Consultation** was certified at `16:06:21Z` on
compiled version `87223c49`. He re-uploaded **the same file** at `16:29:26Z`.
That minted a new note-template row and a new compiled version `9e758c45`, made
it **ACTIVE**, and left the certification stranded on a row that is now
**inactive**. His next visit (`16:31:06Z`) bound to the active, **uncertified**
copy — so the export could not take the twin path at all, which is why he saw
the app's generic header instead of his own.

> **CERTIFICATION KEYED TO A ROW ID, AND THE ROW ID ROTATES ON UPLOAD.**

The product fix — idempotent upload, inheritance by content, auto-certify, and
certification keyed to **content** (source sha + IR sha) rather than a row id —
is ruled and is the next board item. **This mutation is the recovery for the
doctor in front of us, and nothing more.**

⚠️ **AND "DO NOT RE-UPLOAD" IS NOT THE FIX AND WAS NEVER A PRODUCT RULE.** It
was a 20-minute workaround, and it is rejected: a doctor may upload anything, any
time, repeatably.

## THE ACT

    bash scripts/run-ruled-mutation.sh \
      --declaration docs/foundation/mutations/20260903-transfer-certification-to-active.md -- \
      npx tsx apps/transcribe-md/scripts/transfer-certification-to-active.ts --commit

Source of truth: `87223c49` (certified, inactive).
Target: `9e758c45` (active, `NEEDS_CONFIRMATION`).

## ⚠️ WHY TRANSFER RATHER THAN RE-DERIVE — measured, not assumed

`confirm-live-template-mappings.ts` re-derives each disposition from the field's
**current** mapping. On a freshly compiled version that input is the fresh
PROPOSAL, not the confirmed decision, so re-deriving would **not** reproduce what
was certified:

| comparison | result |
|---|---|
| concepts agreeing between the two versions | **31 of 35** |
| sourceTypes agreeing | **27 of 35** |

The 8 sourceType differences are exactly the administrative fields certification
set to `manual`; the concept differences are the sub-concept refinements. So the
certified copy is the source of truth and its rows are copied across.

## WHY THAT IS SOUND — the identity, measured

| dimension | result |
|---|---|
| field count | 35 / 35 |
| match on displayOrder + label + kind | **35** |
| match on **fieldId** | **35** — the ids themselves are identical |
| `structureSha256` | identical |
| `staticContentSha256` | identical |
| owning doctor / practice | identical |

**Only the row id differs.** The transfer is not an approximation; it is the same
field set, addressed by the same ids.

## MUST CHANGE — 12 fields, enumerated

| # | field | before | after |
|---|---|---|---|
| 1 | Referring MD | `NULL/extraction` | `NULL/manual` |
| 2 | Patient | `NULL/extraction` | `NULL/manual` |
| 3 | Age | `NULL/extraction` | `NULL/manual` |
| 6,7,8,9 | narrative stem ×4 | `NULL/extraction` | `NULL/manual` |
| 21,22 | Allergies ×2 | `allergy/extraction` | `allergy.substance/extraction` |
| 25,26 | Medications ×2 | `medication/extraction` | `medication.name/extraction` |
| 65 | Total minutes | `NULL/extraction` | `NULL/manual` |

**8 to `manual`, 4 sub-concept refinements. 23 fields unchanged.**

## MUST NOT CHANGE

- **Every clinical count**: visits 54, signed 36, patients 0 — this mutation
  touches no visit and no note.
- **note_templates rows**: 14. No template is created, deleted or re-activated.
- **The certified source `87223c49`**: still 35 CERTIFIED. It is read, never
  written.
- **Applied migrations**: 111.
- **Field definitions on either version**: 35 / 35. Mappings are updated in
  place; no field is added or removed.

## END-STATE ASSERTIONS — the script refuses unless all three hold

On `9e758c45`: **CERTIFIED mappings = 35**, `approvedById` = the owning doctor
for **35**, `approvedAt` set for **35**.

## GUARDS THAT MUST PASS BEFORE ANYTHING IS WRITTEN

Ten, all asserted in the dry run and re-asserted at commit: both field counts,
source fully certified, **target carrying ZERO certified rows**, identical
fieldId sets, identical structure and static-content shas, same doctor, same
practice, and the target actually being the ACTIVE template.

⚠️ **Plus the runtime registry check.** This transfer writes the sub-concepts
`allergy.substance` and `medication.name`. A runtime whose registry has never
heard of them would write off-registry values that the next compile nulls, so
the script refuses when `REGISTRY_SUBCONCEPTS` is empty. Measured in the runtime
that will perform the act: **4 families — allergy, medication, family_history,
social_history.**

## WHOSE AUTHORITY, WHOSE HANDS — ruling #158, amended 2026-08-31

- `approvedById` answers **under whose authority** → the owning doctor.
- The audit metadata answers **by whose hands** → the machine, via
  `machineConfirmed: true` and `onOwnerAuthorization`, plus
  `transferredFromCompiledVersionId` and a `reason` naming the stranding, so the
  next reader learns why these rows exist without needing this file.

One append-only `TEMPLATE_TWIN_MAPPING_UPDATED` audit row per field: **35**.

## THE FINDING RULE

**A difference this declaration does not name is THE FINDING**, whatever its
explanation sounds like afterwards.

## AFTER THE ACT

The synthetic chain runs **fresh** against the active version and certification
is a separate step — this mutation confirms mappings only and flips nothing.
