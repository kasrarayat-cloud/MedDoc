# CPT Studio design v2: the judge's decisions on the 40 refutation findings against HOLDS-ANALYSIS.md (2026-11-15)

Synthetic and development material only. No real patient appears here. Nothing was sent to any provider, no credential
file was read, docker was never run and `git -C /opt/meddoc-pro` was never used. The worktree and the original trees under
`gemini-migration/trees/` were only read. Every file I wrote is under `build-v2/holds/` (this file, the revised analysis,
its unchanged copy `HOLDS-ANALYSIS-pre-refutation.md`, and `judge/`), except the run directories `tools/t.sh` itself
creates under `G/runs/` (`state-`, `tmp-`, `runq-holds-judge-*`). No excluded directory, no reserved development document,
no reserved expectation entry and no blind note was opened.

Paths: `G` = `/home/claude/cpt-studio-completion-20261106/gemini-migration`; `H` = `G/build-v2/holds`; `J` = `H/judge`;
`S` = `H/synth`; `W` = `/opt/meddoc-pro/.worktrees/cpt-gemini-20261109/cpt-studio/docs/gemini-migration`; `T` =
`G/trees/step8-195e06e90/cpt-studio/studio/interpretation` (the integrated engine; FILE:LINE in `engine/` and `contract/`
refers to `T` unless a tree is named). "synthfinal" is my own copy of the analysis's final set (E1-E5, built with the
synthesizer's asserted scripts: coverage `c1f48ff6`, pairing `2e09cd42`, assess `7e50b3ff`, requirements `69b91e9a`).

## 1. How every finding was verified

- **Every lens's own inputs, re-run on my own trees.** I copied each lens's driver and cases into `J/verify/<lens>/`
  (the only change: `v2lib.RUNS` points to `J/runs`; `diff` shows 2 changed lines per driver, 0 per cases file) and ran
  them on `J/trees/base-step8` (`cp -a` of step8, `diff -rq` 0) and on `J/trees/synthfinal-step8`. Compared status and
  item per case and code with each lens's recorded outputs (`J/verify/cmp2.py`): false-ready 47 rows 0 differ,
  generality 69/0, synthesizer G2 64/0, design 26 rows 0 differ (its three U6/E5neg probes, recorded by the lens in
  separate files, give the outcomes its notes state). Outputs `J/verify/out/*.json`.
- **Mechanisms read in the code**, each cited below; the pairing traces of Q01, Q03 and R05 re-run with the lens's
  `trace.py` on synthfinal.
- **The installed release** read from its recorded outcomes (`H/fb10/installed-c2e53f8e-F3all.jsonl`) and its archive
  (`G/tools/v2/installed-c2e53f8e/cpt-studio/studio/`: no file contains `compared_landmark` or `ANASTOMOSIS_TYPES`).
- **The narrowed set measured** (section 4): every batch replayed through a copy of the tree that recorded it, the
  judge's G2 inputs (10 short, 10 realistic, 3 more), every lens's inputs on the narrowed trees, and `tests.v2`.

## 2. Decisions in one table

| fix | findings accepted | decision |
|---|---|---|
| E1 biopsy elsewhere | FR-5, RG-7 (accepted); FR-6 (in part) | **NARROWED to E1j**: a removal's places are its `target.places` together with its target lesion's established places (FINAL-V2 5.1 row 10); a removal whose lesion claim is neither supported with established places nor a pure silent slot keeps the rule as it was |
| E2 D34 in the target row | FR-1, FR-2, FR-3, FR-4, F1, F2, F3, RG-2, RG-3, RG-4, RG-12, reproduce F3 | **REJECTED**. Three critical findings, a void licence (D34 is not the installed reading; the installed release holds the very rows), no verdict change on any recording. Its design-faithful replacement is the contract change Q2 (an act's `target.anatomy` claimed; the place read from the appraised entry's subtype and joins) |
| E3 lesion places | FR-3, FR-7, F6, RG-5, RG-6 | **REJECTED**. A reader that splits one lesion into two entries gives them disjoint places by construction, which is the failure `distinct_from` guards; E3 also discards a contradicted `distinct_from` ([R:HO-3]); no verdict change on any recording |
| E4 COLFULL reads `through` | F4, FR-8, RG-11, reproduce F4 | **REJECTED**. It puts D196's UNCONTROLLED one-entry `through` on COLFULL's READY path; a bypass and a stated short reach release; NARROW (1 of 6 recordings); no verdict change on any recording. U2 and U3 are the reach's general fixes |
| E5 electrosurgical devices | RG-1, F7, reproduce F1; FR-9, F8, reproduce F2 | **WIDENED to E5j**: electrocautery covers hot snare, hot forceps, argon plasma and radiofrequency (each delivers high-frequency current by definition, D222); a thermal probe or a sphincterotome MAY be electrosurgical (technique row UNRESOLVED, never covered); the release direction is named and tested |
| FX-R1 | FR-10 (named risk) | kept; the product behaves so (D261) |
| FX-SCORE | RG-8; reproduce F6 | **WIDENED**: X counts when at least one event lists a telling restatement over it and EVERY listing event is one of the code's acts; the role claim's geometry check stays a stated condition |
| FX-EXP-COMPETE | F9; RG-9 (in part) | **NARROWED** to one visit (the expected act spans of the visit codes overlap); RG-9's category argument rejected under D40 |
| FX-DEV-MEMBER | FR-11, RG-10 (pre-existing) | kept as a measurement input; **FX-CAT** (a member-entered patient status holds a visit code of the other published category, never excludes, D5) is a required companion before an acceptance run that enters member values: an owner question, specified, not built |
| U6 | F0, RG-13 | **WITHDRAWN**: the contract carries no MDM level or minutes, so no rule can check a level; U6 would turn the two-basis hold into a READY at an unsupported level |
| U2 | FR-12 | amended: a reach the words leave unclear goes in `device_reached` with a doubt about `reached` |
| U1 | RG-1 | kept, now guarded by E5j |
| new U8, U9 | FR-10, FR-6 | instruction proposals: a doubt mark inside a denial files a status doubt; a lesion's places list every segment it lies in or reaches |

## 3. The findings, one by one

Each entry: what the lens claims; what I re-ran or read; the decision. "Base" is the unmodified step8 engine,
"synthfinal" the analysis's E1-E5, "final" my narrowed set (E1j + E5j).

### Lens false-ready

**FR-1 (critical, E2, own arm with no control; D34's one-side table).** ACCEPTED.
- Re-run: Q01, Q02, Q04, Q05, R01, R04, M01, M03, M04 are needs_clarification on base and READY on synthfinal
  (`J/verify/out/fr-*.json`). Trace Q01 on synthfinal: `pair_controls={}`, `E3 ~ E2: relation=independent row=target
  mode=own`.
- Mechanism: the own arm ends in `facts_.apart_by_controls(..., (), ())` fed `_compared` sets (synthfinal
  `engine/pairing.py:768-769`), and `contract/claims.py:2715-2726` (`_place_identity_pair`) never pairs two acts of one
  kind except two stricture kinds, so no control exists. `ANASTOMOSIS_PLACE` maps ileocolic to RIGHT_COLON
  (`engine/anatomy.py:225`) while after a right hemicolectomy the colonic side is the transverse colon, which
  `PROXIMAL_COLON` contains but RIGHT_COLON does not (`engine/anatomy.py:116-122`). ALTERED exists so that "a difference
  of site is never manufactured" (`engine/anatomy.py:156-158`).
- Q01 is a real false-READY shape: "biopsies from the proximal transverse colon" and "biopsies at the anastomosis
  attempted, unclear whether tissue was obtained" may be one act told twice; the second telling doubts the first.
- Consequence: E2 rejected (not narrowed; see F1 and RG-2 for why no narrowing rests on a licence).

**FR-2 (critical, E2 counts only a claimed value).** ACCEPTED. Q03, Q03d, R03 READY on synthfinal, Q03c held. The count
`facts_.fact(R, entry, _A.TYPE).value is AnatomyType.ANASTOMOSIS` (synthfinal `pairing.py:604`) drops a contradicted type
(value None, its sides the options: `tests/v2/evaluate_fixtures.py:68-71`) against its own docstring (`:601-602`) and
D34 ("several anastomoses ... keep today's ambiguity", `W/DECISIONS.md:168-169`). E2 rejected.

**FR-3 (critical, E3 inherits D34).** ACCEPTED. R05 READY on synthfinal (E2+E3), held on base; trace: lesion controls
rejected, target independent. `_distinct_by_place` compares lesion places through `_compared` (synthfinal
`pairing.py:634-640`). E3 rejected.

**FR-4 (high, E2's entry guard cannot fire for an act).** ACCEPTED. An act's CLAIMED rows carry no TARGET_ANATOMY
(`engine/requirements.py:727-745`, statements at `:753`), so the guard "target.anatomy established as another entry"
(synthfinal `pairing.py:628-630`) never fires for an act, and X06's hold (a SUPPORTED act target.anatomy,
`S/g2/cases.py:438-447`) is a state settle never produces. M01 and Q03b READY on synthfinal. E2 rejected; the
replacement claims the act's target.anatomy (Q2).

**FR-5 (high, E1 reads only the removal's target.places).** ACCEPTED, E1 narrowed. M07 READY on synthfinal; the removed
lesion's own places [hepatic flexure, transverse colon] contradict "done where no removal was". FINAL-V2 5.1 row 10
reads "`target.places` and the lesion's places" (`W/FINAL-V2.md:1651`). E1j adds the target lesion's established places
to each removal's places and fails closed on a lesion claim that is neither supported nor purely silent
(`J/patches/j1_e1_lesion_places_v2.py`). Final: M07 held; my JS02, JS05, JR02 (lesion places), JS03, JR03 (doubted lesion or
lesion place) held on final and READY on synthfinal; fb05 still released (its lesions' places equal their acts' places).

**FR-6 (medium, X01's class at every junction).** ACCEPTED IN PART. Re-run: Q06, R06, R07 READY on synthfinal and on
final. Accepted: E1 widens the base's accepted adjacency exposure from one-place biopsies to multi-place ones, and the
straddling-lesion cases are real. Closed where the lesion's extent is filed, by E1j (FR-5). Not accepted: the junction
adjacency guard. Counter-inputs:
- Q06/R06 themselves: the nodule's established places are [GEJ] only; the cardia samples lie outside the resected
  lesion, and the biopsy code is reportable when any specimen comes from another site, which is the rule E1 rests on.
- The base already releases the one-place form (K02 READY on base); FINAL-V2 4.13 dropped D58/D77's adjacency
  (`W/FINAL-V2.md:1589`).
- D77's adjacency makes consecutive full segments adjacent (`W/DECISIONS.md:1396-1398`), so the guard would also hold
  "sigmoid polypectomy; random biopsies of the sigmoid and the descending colon", an unasked hold on a common input.
- Residual, named: a lesion that reaches a junction but is filed at one segment and sampled on both sides (R07, X01)
  needs two errors (the lesion's place under-filed and pass 2 rejecting the removal-place control). Instruction U9
  addresses the first.

**FR-7 (medium, E3 at a junction).** ACCEPTED. Q07 and R08 READY on synthfinal (E2+E3). Two place words for one polyp
at a junction are disjoint landmarks. E3 rejected.

**FR-8 (medium, E4 and an ileocolic bypass).** ACCEPTED. Q08 and R09 READY on synthfinal: E4 (synthfinal
`engine/assess.py:1241-1245`) ignores a negated cecum and a bypass entry, against D44's premise (`W/DECISIONS.md:236-242`).
E4 rejected.

**FR-9 (low, E5 releases).** ACCEPTED (documentation and tests). Q09 and R10 go needs_clarification to READY under E5
and under E5j. The release is definitional (a hot snare, hot forceps, argon plasma or radiofrequency act cannot be one
done "without electrocautery"), so it is kept, named, and tested (JS10, JR07). A device that MAY be electrosurgical is
never removed by a negated electrocautery (JM02 stays held).

**FR-10 (low, FX-R1 and a trailing doubt mark).** ACCEPTED as a named risk. Q10: pipeline R1 EXCLUDED, old R1 held,
on every tree. This is the product's R1 (D261, `W/DECISIONS.md:15598-15606`); the harness must measure what ships.
No harness change; instruction proposal U8.

**FR-11 (low, pre-existing, Q5 under DEV-MEMBER).** ACCEPTED. M06 (99204 alone, member status established) READY on
base and on every tree. Not caused by the fix set. See RG-10 and FX-CAT.

**FR-12 (low, U2 removes the K6 conflict with no doubt route).** ACCEPTED. U2 gains: "When the words leave unclear
whether the endoscope itself reached a point, list it in `device_reached` and add a doubt about `reached`." (the
DOUBTS clause, probe tree `contract/extract_prompt.py:157-165`).

### Lens design

**F0 (critical, U6 converts the two-basis hold into a READY at an unsupported level).** ACCEPTED, U6 withdrawn.
RU6a 99215 READY and RU6b held on base and every tree. The contract carries only the basis kind (`EmBasis`:
total_time, medical_decision_making, `contract/types.py:670-673`); R6:em_basis reads only that a basis is supported
(`engine/assess.py:1308-1318`). No level rule can be written without new facts, so U6 cannot ship safely in this round.

**F1 (high, E2's licence void; FINAL-V2 5.1 rows 11/51).** ACCEPTED. D34 is a ruling of the Gemini v1 path (S16 round
3, `W/DECISIONS.md:161-170`, `:191`); D15 names c2e53f8e as installed (`W/DECISIONS.md:67`). The installed archive has
no D34 code, and the installed release HOLDS note8 45380 [conflict:biopsy, extent] and 45386 [conflict:dilation,
extent] (`H/fb10/installed-c2e53f8e-F3all.jsonl`, A-note8). Row 11's replacement is "`target.anatomy` /
`reached_anatomy` with the entry's subtype and joins" (`W/FINAL-V2.md:1652`). RR02b (the entry's own joins place the
anastomosis in the transverse colon) and RS11 (X06 in a reachable state) are READY on synthfinal. E2 rejected.

**F2 (high, E2 in D228/D238's no-control arm).** ACCEPTED (same mechanism as FR-1). RS01, RR03, RR03b READY on
synthfinal. FINAL-V2 4.5 [R:HO-3] allows that arm only because pass 2 supported where the act was done
(`W/FINAL-V2.md:1375-1379`); the right colon E2 compares was never appraised.

**F3 (high, a doubted, silent or contradicted second entry).** ACCEPTED (same as FR-2). RS02, RS03, RS04, RR09 READY on
synthfinal; FINAL-V2 4.2's fail-closed doubt arm (`W/FINAL-V2.md:1199-1214`).

**F4 (high, E4 consumes an uncontrolled `through`).** ACCEPTED. `session.through` with one anatomy entry is UNCONTROLLED
(`contract/claims.py:1268-1270`, `:1296`; D196, `W/DECISIONS.md:14375-14376`) "because the class fit also needs the
approach and the entry's type"; E4 needs neither. RS05 ("passed through the colorectal anastomosis ... advanced to the
mid transverse colon", only the ileocolic entry listed) and RR05 READY on synthfinal. The COLFULL row names only
reached, reached_anatomy and the subtype (`W/FINAL-V2.md:1257`). E4 rejected.

**F6 (medium, E3 discards pass 2's same-lesion appraisal).** ACCEPTED. RS10 and RR08 READY on synthfinal:
`distinct_from` is unresolved (pass 2 contradicted it), yet `_possibly_same` reads only `same_as`
(`engine/pairing.py:572-579`), so E3 sets the lesions apart by place, against [R:HO-3] ("pass 2's doubt about a filing
is never discarded", `W/FINAL-V2.md:982-984`). E3 rejected.

**F7 (medium, E5 omits argon plasma and radiofrequency).** ACCEPTED, E5 widened. RS07, RS08 and RR06's 45388 READY on
synthfinal, held on final (conflict:ablation). D222: "argon plasma coagulation delivers high-frequency current"
(`W/DECISIONS.md:15040-15046`).

**F8 (low, E5 releases).** ACCEPTED (as FR-9). RE5neg: base held (conflict:snare), final READY, semantically right.

**F9 (low, FX-EXP-COMPETE wider than "one visit").** ACCEPTED, narrowed (see RG-9).

### Lens reproduce

**F1 (medium, argon plasma beside "no cautery").** ACCEPTED (as RG-1). `J/verify/out/rep-e5probe2-final-step8.json`:
APC and APC-K 45388 needs_clarification [conflict:ablation] on final, READY on base.

**F2 (low, E5's "only adds holds" is false).** ACCEPTED (as FR-9). Q1 and Q2 of `e5_probe.py` READY on final.

**F3 (low, unlisted C2MEM-023 relation changes under E2).** ACCEPTED. Verified in the lens's exports
(`H/refute-reproduce/runs/{meas,e2}/replay-F3long/C-C2MEM-023/r1/export.json`, field relations): E25-E14, E28-E15,
E34-E14, E34-E15 go UNRESOLVED (timing) to INDEPENDENT (target). Moot: E2 is rejected.

**F4 (low, the U1 projection rests on E4 for all three note8 releases).** ACCEPTED. With E4 (and E2, E3) rejected, my
re-run of the analysis's KINDSIM2 simulation on the final set (`J/runs/simfinal2`) gives F3long 0/7, no wrong READY:
note8 45385 is held by `coding_rule:COLFULL`; 45380/45386 by `relation:unresolved` (the anastomosis place and the
lesion-only statements); 45390 by `relation:unresolved` (E35 against E21: U1's own pair controls). The analysis's 11/16 projection
is withdrawn.

**F5 (low, "each measured alone" not true for E5).** ACCEPTED. `S/trees/e5-F3all` carries coverage `c1f48ff6`, pairing
`2e09cd42`, assess `7e50b3ff`, requirements `69b91e9a` (sha256 printed), i.e. the final set. I measured E5j alone
(`J/runs/e5j2`): one cause added to note8 45382, nothing else.

**F6 (low, FX-SCORE's code requires a geometry check its class does not state).** ACCEPTED: the condition is kept and
stated (a credit should rest on a role claim that passed its own checks; it only refuses more). JM9 (my scorer input:
geometry failed) refuses; no recorded row depends on it.

### Lens generality

**RG-1 (critical, E5 covers two of the devices its class names).** ACCEPTED, E5 widened (E5j). VR10b (reachable today:
APC ablation beside an established "No electrocautery ablation was performed in the cecum") is READY on base and
synthfinal and held on final; the installed release holds the same words (I-VR10b, conflict:ablation), so the v2 READY
is a held-to-READY regression under the owner's amendment (`G/tools/v2/README.md:179-180`). VR10 (U1's form) and VR10c
held on final. THERMAL_PROBE and SPHINCTEROTOME are read as possibly electrosurgical, never covered (JS09, JR08, JM01
held on final, READY on base; JM02 stays held: a negated electrocautery does not exclude them).

**RG-2 (high, E2's D216-rule-3 justification).** ACCEPTED (as F1). The code comment at synthfinal `pairing.py:590-591`
("the installed release's mapping.compared_landmark") is false; E2 rejected.

**RG-3 (high, E2 in the own arm).** ACCEPTED (as FR-1/F2). VX11 and VX11c READY on synthfinal; VX11d and VX12 held.

**RG-4 (high, D34 reaches pairing only).** ACCEPTED as a requirement on E2's replacement: one compared place for
pairing, `coverage._apart` and E1 (VS07 held on every tree, VS07b's two readings in one FactSet). Moot for this round.

**RG-5 (high, E3 narrower than group 6's root cause).** ACCEPTED. VS09b, VS09c and VR11's 45380 held on every tree;
claims.py asks an event only about the other's own places and lesions (`contract/claims.py:2481-2500`, `:2532-2543`).
Group 6 needs a contract rule (a lesion-only statement's claimable places) and a ruling on 4.2; E3 rejected.

**RG-6 (medium, E3 ignores the act's own place).** ACCEPTED. VS11 READY on synthfinal. E3 rejected.

**RG-7 (medium, E1 ignores the removed lesion's places).** ACCEPTED (as FR-5). VS04 READY on synthfinal, held on final;
VS04b (the base's one-place form) READY everywhere.

**RG-8 (medium, FX-SCORE refuses the faithful multi-act summary).** ACCEPTED, widened. With my scorer copy
(`J/tools/score_v2_s6.py`): M7 and M7b correct (restatement), M7c correct; the analysis's M1-M6 all keep their verdicts
(`J/score/measure_rules_synth.py`: ALL PASS); my JM7 counts, JM8 (a third, non-act event lists the line), JM9 and JM10
refuse (ALL PASS). No recorded row changes.

**RG-9 (medium, FX-EXP-COMPETE writes the category rule into the expectation).** ACCEPTED IN PART.
- Accepted: the implemented rule fired on any two office visit codes in a document; it now fires only when their
  expected act spans overlap (one visit). Synthetic devset `J/g2/devset-j`: one visit rewritten, two visits not,
  overlapping spans of one visit rewritten, procedure-only unchanged.
- Rejected: the category argument. Counter-input: VE1 itself (99203 + 99213 for one visit, status established). D40
  (`W/DECISIONS.md:226-235`): two E/M codes for one visit are held with base_included plus competing_codes, "the
  installed doctrine (CPT Studio never chooses between two codes for one act)". VE1 is held on base and on every tree,
  and a HELD expectation is the design's outcome for it, whatever the patient status.

**RG-10 (critical, pre-existing, a new-patient code READY for an established patient).** ACCEPTED. VE2 READY on base,
on every tree and in the installed release (I-VE2); `_context_row` reads only that values were entered
(`engine/assess.py:1321-1329`). The catalogue holds no category (`engine/catalogue.py:334-335`: "not a CPT reference, no
descriptor"). Not caused by the fix set and not fixable by replay. Routed as FX-CAT (owner question: a new coding rule
the installed release does not apply; it holds, never excludes, D5) with VE2/M06 as its hold inputs and VE3 as its
READY input.

**RG-11 (low, E4 NARROW).** ACCEPTED; E4 rejected.

**RG-12 (low, E2 never reads target.anatomy).** ACCEPTED; the replacement reads it (Q2).

**RG-13 (low, U6 order-dependent; its example echoes fb10).** ACCEPTED. `G/fresh/inputs/B/fb10.txt:11`: "moderate
medical decision making; 32 minutes"; U6's example "moderate decision making and 35 minutes". U6 is withdrawn (F0); a
reintroduced form records no basis by position and uses an unrelated example.

## 4. Measurements of the narrowed set (details in HOLDS-ANALYSIS.md, sections 4J and THE FINAL FIX LIST)

- Replays (`J/runs/{base,meas,final,e1j,e5j}`): my base replays reproduce the recorded rows byte for byte on F3all,
  F3long, F2high-p2, D2low and D2medium (`cmp` of `rows.jsonl`); D1v/D1w (provisional pin) equal the synthesizer's base.
- Final set (FX-R1, FX-SCORE widened, FX-EXP-COMPETE narrowed, FX-DEV-MEMBER, E1j, E5j): 10 notes READY recall 8/16,
  unnecessary holds 8/16, wrong READY 0, wrong exclusions 0; held-out 10/16, 6/16, 0, 0. Every verdict equals the
  analysis's final set on every batch (E2-E4 changed none); note8's held-cause lists differ only.
- E1j alone releases B-fb05 45380 on F3all and F2high-p2 and nothing else; E5j alone adds one cause to note8 45382.
- G2: the judge's 23 inputs and every lens input, on base, E1j, E5j, final (section 4J of the analysis).
- `tests.v2` (G4), the whole package each time: baseline on an unmodified step8 copy, Ran 2496 tests in 388.3s, OK
  (`J/tests/base-tests.v2.log`). Final set v2: Ran 2496, FAILED (failures=5), every one a named deliberate change: E1j's
  three r2d-2 Q2 pins (PMonoTests x2, PMonoVerdicts5Tests; the P-MONO counter over 2,858 weakenings changes only "D245
  (repair r2d-2's Q2, option (a))" 1 -> 0, no unnamed release) and the requirements read-set pin; E5j's v1-parity table
  pin. E1j alone: 4 failures; E5j alone: 1; they add up to the final five. The judge's v1 trees failed 15: five
  mypy-strict errors in `_may_be` and six P-INDEP failures (the whole's lesion places missing from the BUNDLING
  read-set), both the judge's own defects, fixed in v2; v1 and v2 give identical rows and G2 outcomes.

## 5. Questions only the owner can decide

1. **FX-CAT** (class a/b): may a member-entered patient status hold an office visit code of the other published category
   (99202-99205 new, 99211-99215 established)? The installed release READYs a lone wrong-category code (I-VE2), so this
   adds holds where c2e53f8e READYs, though those READYs are wrong by the codes' descriptors. Recommended: hold with one
   focused question, never exclude (D5).
2. **D40 against the acceptance expectations** (class c): FX-EXP-COMPETE changes only the development expectation. If
   the acceptance expectation marks the right code of a two-code visit READY, the design's D40 hold counts there as an
   unnecessary hold; the doctrine (never choose between two codes for one act) is the owner's to keep or amend.
3. **E1j's junction residual** (class b, a trade): accept that a lesion reaching a junction, filed at one segment and
   sampled on both sides, may release 45380/43239 when pass 2 also rejects the removal-place control, rather than
   re-introducing D58/D77's adjacency (which FINAL-V2 4.13 dropped) and holding common neighbouring-segment biopsies.
4. **The recall gap** (informational, for the owner's paid test): with what survives refutation, replay measures 8/16 on
   the 10 notes and the long notes stay 0/7 even under the U1 simulation. Raising them needs contract and instruction
   changes recorded again under D277 (U1 with E5j, U2/U3, and Q2 for the anastomosis place), not engine rules.
