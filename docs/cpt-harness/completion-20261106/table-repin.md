# Completion repair: the refutation tables re-pinned once, on the integrated tree

Measured 2026-11-06 by `tools/repin_tables.py` (session scratch; each row read by the test module's own
reader: `c2.dated_both`, the competition tests' `outcome`, the admission test's run, r1's `both`). Nothing
was sent. Every moved row is classified below; each fixture row records the new reading under its
`read` key "completion (integration)", and r1's inline tables were rewritten in place.

## Counts

| rows | table | movement |
|---:|---|---|
| 1 | c2 | corti moved | equal | no new READY |
| 2 | c2 | participant only | equal | NEW READY over pin and base: participant |
| 78 | c2 | participant only | equal | no new READY |
| 75 | c2 | unmoved |
| 44 | c3.admission | moved | equal to Corti selecting it | act not READY |
| 3 | c3.multi | moved | NEW READY over pin and base: 43249 |
| 9 | c3.multi | unmoved |
| 4 | c3.single | corti moved | equal | no new READY |
| 45 | c3.single | participant only | equal | no new READY |
| 28 | c3.single | unmoved |
| 2 | c4.multi | moved | NEW READY over pin and base: 43249 |
| 1 | c4.multi | moved | no new READY |
| 9 | c4.multi | unmoved |
| 49 | c4.single | participant only | equal | no new READY |
| 5 | c4.single | unmoved |
| 7 | r1.R1_L1_1 | participant only | equal | no new READY |
| 2 | r1.R1_L1_2 | participant only | equal | no new READY |
| 6 | r1.R1_L1_3 | participant only | equal | no new READY |
| 5 | r1.R1_L1_4 | participant only | equal | no new READY |
| 8 | r1.R1_L2_1 | participant only | equal | no new READY |
| 1 | r1.R1_L2_1 | unmoved |
| 4 | r1.R1_L2_2 | participant only | equal | no new READY |
| 5 | r1.R1_L2_3 | participant only | equal | no new READY |
| 6 | r1.R1_L2_4 | participant only | equal | no new READY |
| 6 | r1.R1_L2_5 | participant only | equal | no new READY |
| 1 | r1.R1_L2_6 | corti moved | equal | no new READY |
| 3 | r1.R1_L2_6 | participant only | equal | no new READY |
| 5 | r1.R1_L2_7 | participant only | equal | no new READY |
| 4 | r1.R1_L2_8 | participant only | equal | no new READY |
| 6 | r1.R1_L3_1 | unmoved |
| 4 | r1.R1_L3_12 | unmoved |
| 5 | r1.R1_L3_2 | participant only | equal | no new READY |
| 4 | r1.R1_L3_2 | unmoved |
| 4 | r1.R1_L3_3 | unmoved |
| 1 | r1.R1_L3_4 | participant only | equal | no new READY |
| 10 | r1.R1_L3_4 | unmoved |
| 9 | r1.R1_L3_5 | unmoved |
| 8 | r1.R1_L3_6 | unmoved |
| 5 | r1.R1_L3_7 | unmoved |
| 4 | r1.R1_L3_8 | unmoved |
| 6 | r1.R1_L3_9 | unmoved |
| 2 | r1.R1_L5_1 | participant only | equal | no new READY |
| 7 | r1.R1_L5_1 | unmoved |
| 1 | r1.R1_L5_2 | participant only | equal | no new READY |
| 3 | r1.R1_L5_2 | unmoved |
| 32 | r1.R1_L5_3 | participant only | equal | no new READY |
| 1 | r1.R1_L5_3 | unmoved |
| 5 | r1.R1_L5_4 | participant only | equal | no new READY |
| 9 | r1.R1_L5_5 | participant only | equal | no new READY |
| 5 | r1.R1_L5_6 | participant only | equal | no new READY |
| 1 | r1.R1_L5_7 | unmoved |
| 1 | r1.R1_RESIDUAL | corti moved | equal | no new READY |
| 2 | r1.R1_RESIDUAL | participant only | equal | NEW READY over pin and base: participant |
| 6 | r1.R1_RESIDUAL | participant only | equal | no new READY |
| 10 | r1.R1_RESIDUAL | unmoved |

r1 inline edits: 133.

No row reads differently for a participant than for Corti selecting the same passage (no "UNEQUAL" row).

## The rows that needed a reason

| table | row | pin | now | reason |
|---|---|---|---|---|
| c2 | C2-5:C2-5-7a | `["READY", "ALT"]` | `["READY", "READY"]` | the injection is documented ("Injection sites: ... triamcinolone 40 mg", 43236): the participant reads as Corti's READY selection |
| c2 | C2-5:C2-5-7-control | `["READY", "ALT"]` | `["READY", "READY"]` | as C2-5-7a |
| c3.multi | C3-3:f4_doubted_ready:corti 43248 [Possibly the ring was also dilated  | `{"43248": [["HELD", true]], "43249": [["HELD", true]]}` | `{"43248": [["HELD", false]], "43249": [["READY", false]]}` | one balloon dilation done and a doubted or failed Savary dilation: 43249 READY, 43248 held by its own technique question (reconcile.technique_fits); the corpus requires exactly this (F4) |
| c3.multi | C3-3:f4_doubted_ready:corti 43248 [Per the outside report, the ring wa | `{"43248": [["HELD", true]], "43249": [["HELD", true]]}` | `{"43248": [["HELD", false]], "43249": [["READY", false]]}` | one balloon dilation done and a doubted or failed Savary dilation: 43249 READY, 43248 held by its own technique question (reconcile.technique_fits); the corpus requires exactly this (F4) |
| c3.multi | C3-3:f4_doubted_ready:corti 43248 [A Savary dilation was attempted but | `{"43248": [["HELD", true]], "43249": [["HELD", true]]}` | `{"43248": [["HELD", false]], "43249": [["READY", false]]}` | one balloon dilation done and a doubted or failed Savary dilation: 43249 READY, 43248 held by its own technique question (reconcile.technique_fits); the corpus requires exactly this (F4) |
| c4.multi | C4-2:C4-2-3 EGD: two balloon dilations + doubted Savary (corti 43248 o | `{"43248": [["HELD", true]], "43249": [["HELD", true]]}` | `{"43248": [["HELD", false]], "43249": [["READY", false]]}` | as F4: the technique reading tells the balloon dilations from the doubted Savary dilation |
| c4.multi | C4-2:C4-2-3-control (C3-3-4 pinned): one balloon dilation + doubted Sa | `{"43248": [["HELD", true]], "43249": [["HELD", true]]}` | `{"43248": [["HELD", false]], "43249": [["READY", false]]}` | as F4: the technique reading tells the balloon dilations from the doubted Savary dilation |
| r1.R1_RESIDUAL | L1-4a-plain | `["READY", "ALT"]` | `["READY", "READY"]` | a base false READY on Corti's path ("India ink tattoo was requested."), now shared by the participant (one evaluation); the corpus entry R1|L1-4a-plain was FALSE READY at the installed baseline and stays a recorded residual |
| r1.R1_RESIDUAL | L5-6:The food bolus was pushed into the stomach. | `["READY", "ALT"]` | `["READY", "READY"]` | a base READY on Corti's path, shared by the participant; whether a push into the stomach is 43247 is the owner's coding question Q1 |

Corti's own reading moved on six rows, each toward its lens's requirement and never to READY: c2
3b-ctl-plain ("with EMR pending authorization", HELD to EXCL: a plan); c3 C3-1:c31-4:E2 and E2n ("banded
previously") and C3-4-8:d and its control ("Before today's ..."), HELD to EXCL as historical; r1 L2-6
ctl-6 ("is to be injected", HELD to EXCL); r1 RecordedResidual L5-2 (READY to HELD: another role's act).
