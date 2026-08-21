# F24 — EDITOR PARITY: RECON, BEFORE ANY BUILD

**Owner's spec, his words:** *"the AI must be able to edit everything it shows
me in the Word/PDF."* Three failures on the CERTIFIED template, live.

Recon-first per the standing pattern. **Nothing is built here.** Every claim
below is a FILE:LINE or a measured number, and the zeros are positive-controlled.

---

## (1) WHY THE `SSV at the SPJ` EDIT REFUSED

**`apps/transcribe-md/src/lib/note-table-edit.ts:197`**

    if (headerCells.length !== rowCells.length) return { ok: false, reason: 'ragged_table' };

The doctor-facing string at `:234` is the one he saw: *"That table's header and
its rows don't line up, so I can't tell which column is which."*

**THE EDITOR RESOLVES COLUMNS BY POSITION IN RE-PARSED MARKDOWN.** `:186-187`
takes `cells(lines[header])` and `cells(lines[line])`; `:200-204` finds the
column by matching the header cell TEXT and writes the row at the SAME INDEX.
Its own comment states the failure it is defending against — a header that
omits the row-label column puts every index off by one, *"and the write lands
one column left of the one it then reports back."*

**The refusal is CORRECT for the information it has.** Refusing to guess is
right. The defect is the input: it is reading geometry when the twin holds
semantics.

### THE TWIN-AWARENESS MEASUREMENT — a hard zero, positive-controlled

| file | twin refs (`fieldId`/`template_twin`/`compiledVersion`) | control (`soapFinal`/`table`/`intent`) |
|---|---|---|
| `actions/chat-edit-visit.ts` | **0** | 50 |
| `lib/note-table-edit.ts` | **0** | 31 |
| `lib/chat-edit/intent.ts` | **0** | 14 |

The controls are non-zero on the same matcher, so **the zeros are real absences
and not a broken grep.** The edit path has NO connection to the compiled twin.

---

## (2) THE INPUT SURFACE, AND WHAT IS INVISIBLE

**The editor's entire input surface is `visit.soapFinal`** —
`chat-edit-visit.ts:117` selects it, `:146` passes it as `note`. Nothing else
about the document reaches the model.

**`DATE OF PROCEDURE` is not in `soapFinal`.** It is a native content-control
fill: `template-twin/procedure-date.ts`, driven from `fill-engine.ts:88,169,274`
and `native-export.ts:257`. The export renders it; the editor cannot see it.
**That is exactly the owner's "DATE OF SERVICE not found".**

### CENSUS — the certified template's 80 fields

| | count |
|---|---|
| `narrative_text` | **52** — every one inside a table (`tableId` non-null) |
| `single_select` | **28** — standalone (header/body dropdowns) |
| **total** | **80** |

**The gap is structural, not a missing case:** the editor sees a rendered
markdown note; the document is assembled from the twin's 80 addressable fields
PLUS native metadata fills. Regions invisible today: **header content controls
(the DATE class), footers, and the template's own table structure** — the
editor only ever sees whatever markdown the note happens to carry.

---

## (3) LATERALITY — THE RULING NAMES AN ATTRIBUTE THE IR DOES NOT STORE

⚠️ **Recorded because the ruled direction says "addressing by twin fieldId
(label + laterality + section)", and one third of that tuple is not a field.**

Measured: of the 80 IR fields, **0 carry a `laterality` key.** The field keys
are `fieldId · originalLabel · kind · tableId · displayOrder · rowPrototype ·
allowedOptions · criticality · clinicallyMaterial · detectionStatus ·
labelSource · rendererBinding · required · unknownPolicy`.

**IT IS DERIVED, NOT STORED, AND THE DERIVATION ALREADY SHIPS:**
`verified-note-selection.ts:56` — `fieldLateralityFromLabel(originalLabel)`.

**So the ruled tuple IS constructible from existing primitives** — label =
`originalLabel`, laterality = that function, section = `tableId` +
`displayOrder`. **No new data is required.** This is a note about where to
look, not an objection: anyone building F24 who greps the IR for `laterality`
will find nothing and may wrongly conclude the twin cannot express it.

### AND THIS IS PROBABLY THE OWNER'S FAILURE (3)

His disambiguation flow asked right-leg vs left-leg — correct behaviour, and
the ruling says keep it — then **failed on execution.** Laterality is the axis.

`rowLateralityVerdict` (`bridge-evidence.ts:254-265`) returns
`laterality_mismatch` unless `fact.laterality === rowLaterality`. **On the
owner's own acceptance visit the shipped worker logged NINE of them.** Named as
a LEAD, not a diagnosis — nothing yet ties those nine to his edit attempt.

---

## ⚠️ A COUNT FOUND DURING RECON: `notMentionedCount` MEASURES MORE THAN ITS NAME

`picks-bridge.ts:254-286` routes **five distinct exits** into one bucket:

| exit | what it means |
|---|---|
| `!pick` | the dictation genuinely did not mention it — **benign** |
| `pick.value == null \|\| ''` | empty value |
| `set_aside_not_adopted` | the verifier DEMOTED it, awaiting the clinician |
| `not_an_enumerated_option` | an off-list value |
| `!built` | **the derivation REFUSED it** |

**A refusal is indistinguishable from an absence in that number.** It is the
wrong-quantity class: the name is narrower than what it measures.

**This mattered immediately.** The acceptance visit's fill dropped 25 → 20, and
that delta could NOT be attributed from the counts — the five missing fields
land in the same bucket whether the doctor never said them or the new shared
derivation refused them. **The worker log discriminated where the count could
not:** 9 × `laterality_mismatch`, **0** × `not_an_enumerated_option`, **0** ×
`set_aside_not_adopted`, **0** derivation refusals.

**Filed, not fixed.** The fix is to count the exits separately.

---

## WHAT RECON DOES NOT ESTABLISH

- **Nothing here reproduces the owner's edit.** The diagnosis is by reading the
  shipped code and the shipped logs. The only visit that would reproduce it is
  a real patient's record.
- **The nine `laterality_mismatch` blanks are not tied to his edit attempt.**
  They are from the FILL of that visit. Same axis, unproven connection.
- **No count here says how many of the 80 fields an edit could address today.**
  The editor addresses markdown, not fields; the two sets are not comparable
  without deciding what "addressable" means for a rendered note.

## THE BUILD, WHEN IT STARTS

Per the ruling: resolve edits through the COMPILED TWIN when the visit is
template-bound; address by fieldId; every rendered region addressable; edits to
filled cells update the fill and let the existing regenerate-then-sign path
handle freshness; **signed stays read-only per the freeze.**

⚠️ **The adversarial pass is MANDATORY** — this is a note-editing surface on the
clinical path.
