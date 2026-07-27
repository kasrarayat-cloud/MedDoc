# Twin native-WORD GA — master run

Evidence appended per stage. Prod untouched until Stage 9.

## Stage 1 — commit Phase 1 (measurement capability)

Pre-registered eval, run before this commit and unedited to fit the model:

| fixture | expected | got | value+unit | segment | laterality | verdict |
|---|---|---|---|---|---|---|
| dense bilateral reflux | 8 | 8 | 8/8 | 8/8 | 8/8 | PASS |
| post-ablation, MIXED UNITS (mm/cm, ms/seconds) | 4 | 4 | 4/4 | 4/4 | 4/4 | PASS |
| harness dictation | 7 | 7 | 7/7 | 7/7 | 7/7 | PASS |
| SOAP CONTROL (zero measurements) | 0 | 0 | n/a | n/a | n/a | PASS |
| SOAP control: legacy fields populated | - | - | - | - | - | PASS |

**EVAL PASS** — 19/19 at 100% on values AND units, incl. `0.62 cm` and `1800 ms`
preserved exactly as stated.

Sample fact, with a real span:

```json
{"segment":"great saphenous vein at the saphenofemoral junction","laterality":"right",
 "metric":"diameter","value":7,"unit":"millimeters",
 "sourceSpan":"Right great saphenous vein at the saphenofemoral junction: diameter 7 millimeters"}
```

Additive: SOAP fields byte-untouched; only two literal test fixtures needed the
new key; no runtime consumer changed.

## Stage 2 — projector (measurements -> numeric EncounterFacts)

`projectEncounterFacts` now emits a fact per measurement with a real `number`,
real `laterality`, normalized unit, and the `sourceSpan` as the evidence anchor.
`matchMeasurementFact` is untouched — its requirements are simply satisfiable.

Unit normalization lives in the PROJECTOR, not the extractor (asking a model to
convert is asking it to be a calculator):

| stated | normalized |
|---|---|
| 7 millimeters | 7 mm |
| 0.62 centimeters | **6.2 mm** (float noise killed) |
| 2.4 seconds | 2.4 seconds |
| 1800 milliseconds | **1.8 seconds** |
| 900 ms | 0.9 seconds |
| 3 furlongs | passed through untouched — degrades to "no match", never a wrong number |

15 tests. Found and fixed en route: **laterality was not identity-bearing** —
the same 7 mm on the right and left collapsed to ONE factId, which would have let
a right-leg value satisfy a left-leg row. Now part of fact identity.

## Stage 3 — anatomy fold (ADDRESSING only)

Template rows say `GSV at the SFJ`; dictation says `great saphenous vein at the
saphenofemoral junction`. Without a fold every measurement fact missed its row
while looking, in the logs, exactly like missing evidence.

Fold table (code-defined and enumerated; a fuzzy matcher would eventually align
SSV with GSV):

| spoken | folded |
|---|---|
| anterior accessory great saphenous vein | aagsv |
| posterior accessory great saphenous vein | pagsv |
| great saphenous vein | gsv |
| small saphenous vein | ssv |
| saphenofemoral junction | sfj |
| saphenopopliteal junction | spj |
| perforator vein | perforator |

Idempotent; proven NOT to collapse distinct veins. Matching verified both
directions. Evidence rails untouched: a different vein and a different number
are both still refused.

Also widened the segment haystack to include the evidence quote — anatomy is
deliberately kept OUT of concept strings (standing ruling), so the segment's
spoken form lives in the quote. Addressing only.

**507 tests pass, typecheck clean.**

## Stage 4 — registry + constrained proposer

The vocabulary the extractor REALLY emits, from a live run (facts 6 -> 14):

```
[vocab] facts=14
[vocab] assessment                                              n=2 numeric=0 lat={bilateral}
[vocab] exam.vascular                                           n=2 numeric=0 lat={unknown}
[vocab] measurement.diameter                                    n=4 numeric=4 lat={right,left}
[vocab] measurement.reflux_time                                 n=4 numeric=4 lat={right,left}
[vocab] test.bilateral_lower_extremity_venous_duplex_reflux_study.result  n=1 numeric=0 lat={bilateral}
[vocab] test.name                                               n=1 numeric=0 lat={bilateral}
```

**8 numeric facts, correct laterality** — the thing that did not exist before.

Registry in code (`concept-registry.ts`): fixed concepts + a closed set of
patterns (`test.<slug>.result`, `exam.*`, `hpi.*`) + explicit synonyms. The
proposer may now select ONLY from it; an off-registry concept is nulled and the
mapping stays visibly `needs_confirmation`, reported at PROPOSAL time rather
than discovered at certification as phantom missing evidence.

Pinned by test: the three invented concepts that caused the outage
(`test.venous_duplex.gsv_sfj_diameter` etc.) are **rejected**, and no registry
concept may contain anatomy — one concept serves 26 template rows precisely
because it does not name a vein.

## Stage 5 — leg-table addressing: STOPPED, new design question

Not completed, and deliberately not decided unilaterally.

**The situation.** The docx has ONE table (`distinct tableIds among cells = 1`),
26 rows, vein labels that REPEAT — rows 1-13 and 14-26 carry the same labels:

```
  row 1: GSV at the SFJ          row 2: GSV at the Proximal Thigh
  row 3: GSV at the Knee         row 4: GSV Below Knee
  row 5: SSV at the SPJ          ...
```

L4 renders this as TWO markdown tables (Right Leg, Left Leg). `pickTable`
returns one, so only half the cells are ever offered.

**Why "offer both tables" is not safe as-is.** Nothing in the IR row data says
which leg a row belongs to — not the label, not the binding, not a heading.
`matchMeasurementFact` takes laterality FROM the matched fact and the ROW has
no laterality to check against, so offering both tables to all rows would let a
right-leg value satisfy a left-leg row. That is precisely the clinical error the
ambiguity rule exists to prevent, and it would pass silently.

**The open question:** how is an IR row's laterality determined? Options seen
from here, none of them free:
  (a) parse the docx's in-table leg heading rows and stamp laterality onto each
      IR row at COMPILE time (most correct; changes the IR);
  (b) infer from row-block ordering (first N rows = first leg) — cheap, and
      wrong the moment a template orders legs differently;
  (c) require the template to declare it (a compile-time contract).

(a) looks right to me, but it changes the IR and belongs to whoever owns the
compiler contract. Left for a ruling.

## Stages 6-9 — not attempted

Stage 6 (pin reuse) is independent of Stage 5 but has no value without
certification. Stages 7 (certify twice), 8 (real-visit export) and 9 (GA) all
depend on cells filling, which depends on Stage 5.

## Stage 5 — laterality stamped from the document (ruling: option a) ✅

WM_IOV compile, verbatim — the leg read from the document's own heading rows in
document order, never inferred from ordering:

```
[stamp] row  1  right    GSV at the SFJ            [stamp] row 15  left  GSV at the SFJ
[stamp] row  2  right    GSV at the Proximal Thigh [stamp] row 16  left  GSV at the Proximal Thigh
[stamp] row  3  right    GSV at the Knee           [stamp] row 17  left  GSV at the Knee
[stamp] row  4  right    GSV Below Knee            [stamp] row 18  left  GSV Below Knee
[stamp] row  5  right    SSV at the SPJ            [stamp] row 19  left  SSV at the SPJ
[stamp] row  6  right    SSV at the Proximal Calf  [stamp] row 20  left  SSV at the Proximal Calf
[stamp] row  7  right    AAGSV at the SFJ          [stamp] row 21  left  AAGSV at the SFJ
[stamp] row  8  right    AAGSV at the Prox Thigh   [stamp] row 22  left  AAGSV at the Prox Thigh
[stamp] row  9  right    PAGSV at the SFJ          [stamp] row 23  left  PAGSV at the SFJ
[stamp] row 10  right    PAGSV at the Prox Thigh   [stamp] row 24  left  PAGSV at the Prox Thigh
[stamp] rows 11-13 right Saphenous Tributary Vein  [stamp] rows 25-27 left Saphenous Tributary Vein

[stamp] TOTALS {"right":13,"left":13}
[stamp] DETERMINISTIC recompile: true
```

**Fail-closed congruence** in addressing (evidence rails untouched):

| row | fact | outcome |
|---|---|---|
| right | right | fills |
| left | left | fills |
| **left** | **right** | **REFUSED** `laterality_mismatch` |
| **right** | **left** | **REFUSED** `laterality_mismatch` |
| **unknown** | right | **REFUSED** `row_laterality_unknown` |
| right | bilateral | REFUSED `laterality_mismatch` |
| (omitted) | right | fills — legacy callers unconstrained |

7 canaries. The unknown-row rule is the important one: a template with no leg
headings can never silently accept a sided value — filling there would be a
guess wearing a citation.

156 twin/docx tests pass.

## Stage 5.4 — both tables offered ✅

`pickTable` returned one winner, so half the cells were never offered. Now every
candidate table is offered — safe BY CONSTRUCTION, because fail-closed row
laterality means a right-leg value cannot fill a left-leg row. The tables sort
themselves out at the matcher instead of being pre-assigned to legs. A defensive
dedupe keeps a field from taking two resolutions if addressing ever changes.

## Stage 6 — pin content-addressed ✅ (not yet demonstrated)

The pin is now looked up by (encounterSha, templateStructureSha) across compiled
versions and copied onto the current one, instead of being keyed to a row. That
was why "pin REUSED" never appeared: re-uploading the same docx makes a NEW
compiled version every run.

Not demonstrated — Stage 7 did not get far enough to reuse it.

## Stage 7 — CERTIFY: blocked, and correctly

```
[template-twin:mappings] 72/80 proposals were off-registry or unconcepted
                         and are left unconfirmed: ttf_e3e4a4d7…, …
[ga] UNCAUGHT: TemplateTwinLifecycleError: The approved mapping for field 1 is
     incomplete or incompatible.
```

Both behaviours are correct. The registry constraint fired at PROPOSAL time as
designed, and `updateTemplateTwinMappings` then refused to certify mappings that
carry no concept.

**The gap is the registry's CONTENTS, not its design.** It was built from a
single encounter's emissions, so it covers `measurement.*`, `assessment`,
`exam.vascular`, `test.*` — but not the template's metadata fields
(`REFERRING PHYSICIAN`, `ULTRASOUND TECHNOLOGIST`, `MACHINE`, `LOCATION`,
`SIDE OF EXAM`), which is 72 of 80 fields.

### Open question for a ruling

A field whose concept is legitimately outside the extractor's vocabulary can
never fill. The gate requires EVERY field ready, so today that blocks
certification outright. Either:
  (a) grow the registry to cover metadata concepts (`encounter.referring_physician`,
      `test.machine`, `exam.side`) — mostly mechanical, and the proposer would
      then have real concepts to select; or
  (b) certification tolerates permanently-unconcepted fields as attested-blank,
      the way needs-input is already attested.

(a) looks right and is the smaller change, but it widens the vocabulary contract
and belongs with whoever owns it. Stages 8-9 remain blocked behind it.

## Field-class ruling — WM_IOV's 80 fields classified

Counts below are per-template (the raw dump was 3x inflated by three pinned
compiled versions in QA). 52 cells + 28 controls = 80.

### EXTRACTION (registry concept) — 71 fields

| family | n | concept |
|---|---|---|
| measurement cells | **52** | `measurement.diameter` / `measurement.reflux_time` (emitted, verified) |
| clinical indications | 6 | needs empirical dump |
| finding chain "The …" | 8 | needs empirical dump |
| finding chain Left/Right | 4 | needs empirical dump |
| deep venous system L/R | 2 | needs empirical dump |
| side of exam | 1 | needs empirical dump |
| diagnosis | 1 | `assessment` (emitted, verified) |
| technique statement | 1 | needs empirical dump |

### CONTEXT_DEFAULT (deterministic, styleProfile) — 4 fields
referring physician · machine · location · address

### MANUAL (attested-blank, `reason=manual_field`) — 1 field
ultrasound technologist

### VISIT_METADATA — 0 in this template's controls
Patient name / date-of-study are header fields outside the 80.

**The fill floor is satisfiable by extraction alone**: 52 measurement cells
against a ≥10-filled + ≥1-cell floor, with `measurement.*` already proven
emitted and sided. Context defaults and manual are 5 fields total.

## NOT IMPLEMENTED this run — stopped deliberately

The ruling's mechanism (a `sourceType` per mapping; a CONTEXT_DEFAULT provenance
class with its own strict validation mirroring the PRACTICE_DEFAULT checks;
context defaults set through the real settings flow; re-propose; certify twice;
export; GA) was not built.

CONTEXT_DEFAULT is a NEW provenance type on the clinical evidence path — the
same shape of thing as APPROVED_PRACTICE_DEFAULT, which is currently hard-blocked
precisely because its visibility story is unfinished. Adding a second
deterministic-fill provenance class, with its own validation, is safety-critical
work and was not something to start at the end of a long session. The
classification above is the input it needs; the empirical concept dumps for the
six un-dumped pick families are the other.
