# RULED MUTATION — clear ONE poisoned note pin

**Target:** `template_twin_compiled_versions` row
`617d6de9-3dd5-462d-bcb8-cda05e2f1753`, the only compiled version in
production, belonging to note template `cmsxip5f9000901nadsggo2l1`
("Venous Duplex Lower Extremities US Report").

**Scope:** the NOTE PIN COLUMNS of that ONE row. Nothing else, ever.

## WHY THIS ROW MUST BE CLEARED

The pin holds a note that does not correspond to its own key. Measured:

| column | value |
|---|---|
| `pinnedNoteEncounterSha256` | `a3b63b2dda4f` — the **new** (F5-c) encounter |
| `pinnedNoteGeneratedAt` | **2026-08-18 23:19:50Z** |
| `pinnedNoteTemplateSha256` | `37813a6031d4` |
| `pinnedNoteModelVersion` | `claude-opus-4-8` |
| `length(pinnedSyntheticNote)` | 2530 |

The note was generated **two days before the encounter it is keyed to existed**.
Its content carries the OLD encounter's marker and **no diameter dictation at
all**. Certification has refused twice against it — 7 fills, then 5 — and the
refusal read as *"your form does not fill"* when the truth is *"the model never
saw this encounter"*.

The corruption was written by two now-fixed defects (`synthetic-test.ts:376`
presence-treated-as-validity, and `:408` one-column-keys-both-pins re-keying),
shipped in `8f46098a` and **live in production since `89429c1b`**. The code can
no longer create this state. **It cannot repair the row it already created** —
`noteKeyMatches` now reads TRUE against the corrupted key, so the stale note
would still be served.

## WHY A MUTATION AND NOT A CODE CHANGE

Nothing in the product clears a pin. Widening the invalidation to "distrust a
key that looks too old" would be a heuristic guarding against a defect that no
longer exists, in the one place whose whole job is to be trustworthy.

## THE ACT

    update template_twin_compiled_versions
       set "pinnedSyntheticNote"       = null,
           "pinnedNoteGeneratedAt"     = null,
           "pinnedNoteModelVersion"    = null,
           "pinnedNoteTemplateSha256"  = null,
           "pinnedNoteEncounterSha256" = null,
           "pinnedSyntheticEntities"   = null,
           "pinnedSyntheticContextText"= null
     where id = '617d6de9-3dd5-462d-bcb8-cda05e2f1753';

⚠️ **THE EXTRACTION PIN GOES TOO, AND DELIBERATELY.** It is keyed by the same
column. Leaving it while nulling the key would recreate the exact class this
mutation exists to end: content whose key does not describe it.

## DECLARED QUANTITIES — asserted after the act

| # | quantity | before | must read after |
|---|---|---|---|
| 1 | rows updated | — | **exactly 1** |
| 2 | `pinnedSyntheticNote` on that row | 2530 chars | **null** |
| 3 | `pinnedNoteEncounterSha256` | `a3b63b2dda4f` | **null** |
| 4 | `pinnedNoteGeneratedAt` | 2026-08-18T23:19:50Z | **null** |
| 5 | `pinnedSyntheticEntities` | present | **null** |
| 6 | compiled versions total | **1** | **1** — no row created or destroyed |
| 7 | `certificationStatus` | NEEDS_CONFIRMATION | **NEEDS_CONFIRMATION** |
| 8 | mappings CERTIFIED / pending | **80 / 0** | **80 / 0** — untouched |
| 9 | visits / signed / patients | 48 / 30 / 35 | **unchanged** |
| 10 | fill manifests | **0** | **0** |

## WHAT THIS IS NOT

- **Not a certification.** It removes a cached proof input. The next
  certification run regenerates the note from the CURRENT encounter, which is
  the entire point.
- **Not clinical data.** `pinnedSyntheticNote` is a SYNTHETIC certification
  artifact generated from `deriveVerificationEncounter` — fictional example data
  by construction, no patient.
- **Not reversible**, which is why it is here rather than in a script somebody
  runs.

## THE FINDING RULE

Any quantity above reading otherwise is THE FINDING. Rows 8 and 9 especially:
this mutation must not touch a mapping or a clinical count.
