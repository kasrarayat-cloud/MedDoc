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
