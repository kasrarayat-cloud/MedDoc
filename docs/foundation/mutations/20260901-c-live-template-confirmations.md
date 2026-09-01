# RULED-MUTATION DECLARATION — (c), the live-template confirmations

**Ruling #158, as amended and ratified 2026-08-31.** Written and **committed
before the act**, so its commit timestamp provably precedes the rows.

## The act

35 semantic mappings on compiled version `87223c49-cf2b-4d7f-a905-3e6e595863ad`
(`Gastroenterology Consultation`, note_template `active`) are confirmed
**through the application path** — `updateTemplateTwinMappings` — so
`approvedById` and `approvedAt` are set by the one paired ternary at
`certification-lifecycle.ts:509-510` rather than by a statement that bypasses it.

    bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/<this file> -- \
      npx tsx apps/transcribe-md/scripts/confirm-live-template-mappings.ts --commit

## ⚠️ WHOSE AUTHORITY, AND WHOSE HANDS — the amendment

#158(a) as first written said *"the actor is the MACHINE, carrying the
owner-authorization flags"*. **The schema cannot express that**, measured:
`loadOwnedCompilation` filters `doctorId: actor.userId`; `approvedById` is a FK
to `users`; and there is no machine identity among the 198 rows (192 DOCTOR,
3 ADMIN, 1 STAFF, 2 SUPER_ADMIN). Minting one would weaken an ownership check on
a clinical write path to satisfy a phrasing.

**RATIFIED 2026-08-31 — two questions, two honest answers:**

| question | answered by | value |
|---|---|---|
| under **whose authority** | `approvedById` | the **owning doctor** |
| by **whose hands** | audit metadata + this declaration | the **machine** (`machineConfirmed`, `onOwnerAuthorization`) |

This is the **third** falsification-by-schema-contact in this arc, and it is
named as such: #157's premise about `deriveFieldValueFromFact` was false, its
amendments' premises were false twice more, and #158(a)'s premise about the
actor is false in the same way — *a ruling can be correct in intent and
unimplementable as written, and the measurement is what says so.*

## MUST CHANGE — 35 rows, and nothing else

| quantity | before | after |
|---|---|---|
| mappings `CERTIFIED` on `87223c49` | **0** | **35** |
| `approvedById` = the owning doctor | **0** | **35** |
| `approvedAt` set | **0** | **35** |
| audit rows carrying `machineConfirmed` | **0** | **35** |
| concept or sourceType MOVES | — | **16** — MEASURED by the dry run, not assumed (see below) |

### The per-field plan — realistic mappings, never a blanket substitution (#158(b))

**8 fields gain a real concept (b) made reachable:**

| fields | before | after | why |
|---|---|---|---|
| Tobacco · Alcohol · Recreational drugs · Occupation | **NULL** | `social_history.{smoking,alcohol,drugs,occupation}` | the model proposed exactly these and the proposer **silently nulled** them off-registry — the defect (b) fixes |
| Allergies ×2 | `allergy` | `allergy.substance` | the bare family matches **no fact**; the extractor emits `allergy.substance` |
| medications reviewed ×2 | `medication` | `medication.name` | same |

**8 fields become ATTESTED BLANK (`manual`, concept NULL):** Referring MD ·
Patient · Age · the four `{patient} is a pleasant…` scaffold numbers · Total
minutes. ⚠️ **This is the certification gate's own documented class**, not a
dodge: *"A MANUAL field … carries no clinical concept because there is no
evidence to cite, and it renders BLANK. Requiring a concept there would block
certification on a field that is behaving correctly."* Under `extraction` they
resolve `clinical_concept_unmapped` → **BLOCKING**, and certification is
impossible; nothing about them can produce a value either way.

**19 fields UNCHANGED:** `past_medical_history` ×6, `assessment` ×4, `plan` ×5,
`social_history` ×1 (Marital status), and **`family_history` ×3**. A field this
plan does not name keeps exactly what it has.

⚠️ **THE THREE FAMILY-HISTORY FIELDS ARE UNCHANGED BY DECISION, NOT BY
OVERSIGHT.** An earlier draft of this plan remapped them to
`family_history.condition`. The adversarial pass on (b) then measured what that
concept does when it accumulates — *Mother/Diabetes* + *Father/Hypertension*
render `"Diabetes; Hypertension"`, `supported`, `valid:true`, **zero blocking**,
with the RELATION destroyed — so (b) removed it from the accumulating set.
Remapping these three would therefore turn a patient with two family conditions
into `multiple_distinct_supported_values` → **FIELD_CONFLICT → BLOCKING**, where
today they hold bare `family_history`, match no fact, render blank, and block
nothing.

They move when **relation-binding** lands as a DECLARED COMPOSITION — relative +
condition, template-owned, zero NLP — and not before.

⚠️ **AND THE MOVE COUNT IS MEASURED, NOT BRIEFED.** The figure **16** comes from
the dry run against the post-(b) production runtime. An earlier report of mine
said **19**, and the standing order repeated it back — but 19 counted the
family-history remap this plan has since dropped. *A ruling's QUANTITIES are a
snapshot; matching the measurement to the order is how a false declaration gets
written.* The breakdown reconciles: 4 social-history + 2 allergy + 2 medication
+ 8 attested-blank = **16**, with 19 unchanged = 35.

## MUST NOT CHANGE

| quantity | declared |
|---|---|
| compiled versions | **3** |
| certifications | **1** (this is (c), not (d) — no certificate is minted here) |
| fill manifests | **2** |
| mappings total | **150** |
| mappings `CERTIFIED` **elsewhere** | **115** on the dead template `070090d3`, **80** of them on the venous `617d6de9` — untouched |
| visits · signed · patients · note templates | **54 · 36 · 42 · 14** |
| migrations applied | **111** |
| the enumerated denial reason-token set | unchanged |

## Guards, every one BEFORE any write

field count 35 · every field has a mapping · `certificationStatus` =
`NEEDS_CONFIRMATION` · template `active` · already-approved rows **0** ·
CERTIFIED rows **0**. Any mismatch aborts and writes nothing — *a population
that has moved since this declaration means this declaration describes a
different world.*

## Reversibility, stated honestly

Not a true one-way door: the prior state is `approvedById = NULL`,
`approvedAt = NULL`, `mappingStatus = RECOGNIZED|NEEDS_CONFIRMATION`, and it is
recoverable. The **audit rows are append-only and permanent**. It runs through
the ruled-mutation gate anyway, because #158 named it as one and because the
distinction the gate buys — *the declaration provably preceded the act* — is
worth more than the argument about which door it needed.

## What this does NOT do

**It does not certify.** No certificate row is minted, no synthetic proof is
run, `certificationStatus` is left where `updateTemplateTwinMappings` puts it.
That is **(d)**, and it reports the per-field fill map **before** anything
touches `MIN_CERTIFIED_FILLED_FIELDS` — which stays at **10**. Ruling #159: *the
floor never lowers without its own ruling.*
