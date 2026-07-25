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
