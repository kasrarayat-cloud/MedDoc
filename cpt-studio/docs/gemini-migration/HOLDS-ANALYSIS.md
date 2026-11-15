# CPT Studio design v2: why Fable's READY rows are held, and the general fixes, measured (synthesizer, 2026-11-15)

> **REVISED BY THE JUDGE AFTER REFUTATION (2026-11-15).** Four refutation lenses (false-ready, design, reproduce,
> generality) raised 40 findings; each was re-run on the judge's own copies and decided in `HOLDS-REFUTATIONS.md`.
> Every change below is tagged `[R:<lens>-<id>]`; the text as the synthesizer left it is
> `HOLDS-ANALYSIS-pre-refutation.md` (sha256 9437f4ea). Outcome: **E2, E3 and E4 are REJECTED**, **E1 is NARROWED (E1j)**,
> **E5 is WIDENED (E5j)**, **FX-SCORE is widened**, **FX-EXP-COMPETE is narrowed**, **U6 is withdrawn**, **U2 is
> amended**, and **FX-CAT** joins FX-DEV-MEMBER as an owner question. The measured verdicts are unchanged (E2-E4 changed
> none): 10 notes 8/16 READY recall, 8/16 unnecessary holds; held-out 10/16, 6/16; zero wrong READY and zero wrong
> exclusions everywhere. The judge's paths: `J` = `H/judge`. THE FINAL FIX LIST closes this file.

Synthetic and development material only. No real patient appears anywhere in this file. Nothing was sent to any
provider, no credential file was read and docker was never run. The worktree and the original trees under
`gemini-migration/trees/` were only read. Every edit went into a copy under `build-v2/holds/synth/`. No excluded
directory was opened, and neither were the ten reserved development documents, their expectation entries or the blind
test notes. Disclosures are in section 9.

Paths: `G` = `/home/claude/cpt-studio-completion-20261106/gemini-migration`; `H` = `G/build-v2/holds`; `S` = `H/synth`;
`W` = `/opt/meddoc-pro/.worktrees/cpt-gemini-20261109/cpt-studio/docs/gemini-migration`; `T` =
`G/trees/probe-fable52-v2/cpt-studio/studio/interpretation`. FILE:LINE in `engine/`, `contract/` or `jobs.py` refers
to `T`. The engine and settle code are byte-identical in all eight trees used here: `diff -rq` against
`step8-195e06e90` shows only the prompts, readers, `jsonschema.py`, `claims.py` (CLAIM_BOUND), the pins, settings and
pricing.

## 0. The answer in one table

The owner's directive (D276) asks for every fix to be a general rule over the data model. The analysts' per-note
proposals were merged into nine root-cause groups. Each group was turned into a class rule, or rejected with the reason
stated.

| # | root cause (class) | rows (of the 12 traced) | decision | kind | measured by replay? |
|---|---|---|---|---|---|
| 1 | the replay harness gives C-10 no word runs, unlike the pipeline (D261) | fb10 45330 | **FX-R1**: the harness uses the tree's own `jobs._Integrity` | scorer/harness | yes: 1 release, 2 correct exclusions; cross-reader (Gemini medium) |
| 2 | the scorer counts a READY act only by its anchor, never by a line that retells the act | A-v5 45380 (artifact); A-v3 45386, note8 45386/45390 once released | **FX-SCORE**: AMENDMENT-2 §6 parts 1-2, roles restates/summarizes only; **widened: every event listing the line is one of the code's acts** [R:generality-RG-8]; the role's geometry check stated [R:reproduce-F6] | scorer | yes: 3 rows on 3 batches, Fable and Gemini |
| 3 | two office visit codes proposed for one visit; no member values in the devset | fb10 99214 (base_included, competing, context) | **FX-EXP-COMPETE** (**narrowed to one visit** [R:design-F9][R:generality-RG-9]) + **FX-DEV-MEMBER** (with **FX-CAT** as a required companion, an owner question [R:generality-RG-10][R:false-ready-FR-11]) | expectation / devset | yes |
| 4 | a biopsy that names no lesion is never set apart from a removal when only part of it is elsewhere | fb05 45380 | **E1j** biopsy elsewhere, **the removal's places read with its lesion's places** [R:false-ready-FR-5][R:generality-RG-7] (`coverage.py`, `requirements.py`) | engine | yes: released on F3all and F2high-p2 |
| 5 | an act at an anastomosis is never set apart by place (D34 not wired; `target.anatomy` never claimed for acts) | note8 45386, 45380 | ~~E2~~ **REJECTED** [R:false-ready-FR-1][R:false-ready-FR-2][R:false-ready-FR-4][R:design-F1][R:design-F2][R:design-F3][R:generality-RG-2][R:generality-RG-3]; replacement = Q2 (contract) | - | E2 changed no verdict |
| 6 | a lesion-only statement is set apart only by `distinct_from` | note8 45380 (E19), 45386 (E32) | ~~E3~~ **REJECTED** [R:false-ready-FR-3][R:false-ready-FR-7][R:design-F6][R:generality-RG-5][R:generality-RG-6]; a design question (4.2) | - | E3 changed no verdict |
| 7 | COLFULL ignores an established passage through an ileocolic anastomosis | note8 (latent COLFULL) | ~~E4~~ **REJECTED** [R:design-F4][R:false-ready-FR-8][R:generality-RG-11]; U2 and U3 are the reach's fixes | - | E4 changed no verdict |
| 8 | a doubted statement kind silences every other claim of that statement (the kind cascade) | note8 all five; C2MEM-023 (cause B) | **U1** kind-neutral statement claims and pair controls, with **E5j** as its guard (electrocautery covers hot snare, hot forceps, argon plasma, radiofrequency; a thermal probe or a sphincterotome may be one) [R:generality-RG-1][R:design-F7] | contract (U1), engine (E5j) | U1 no (simulated); E5j yes (0 verdict changes on recordings) |
| 9 | reader readings the instruction leaves open | A-v3 45386; note8 45381, K6; fb10 99214 (em_basis, same_day_em); C2MEM-023 (D) | **U2** (amended [R:false-ready-FR-12]), **U3, U4, U7**, new **U8, U9**; ~~U6~~ **withdrawn** [R:design-F0][R:generality-RG-13] | instruction | no (they need a re-recording) |
| - | design-asked holds kept | C2MEM-023 (A: pass 2's unlisted doubt; C: performer doubt); note8 45381 (faithful place doubt) | no change; open questions | - | - |

**Measured, with every replayable fix together (the final set: FX-R1, FX-SCORE, FX-EXP-COMPETE, FX-DEV-MEMBER,
E1-E5):**

| set | READY recall | unnecessary holds | wrong READY | wrong exclusions |
|---|---|---|---|---|
| 10 notes, before (recorded probe, original tools) | 5/17 (29%) | 11/17 (65%) | 1 (A-v5 45380, the restatement artifact) | 0 |
| 10 notes, after | **8/16 (50%)**; F3all 8/9, F3long 0/7 | **8/16 (50%)** | **0** | **0** |
| held-out batches, before (F2high-p2, D2low, D2medium, D1v, D1w) | 6/17 | 9/17 | 2 (the same artifact twice) | 0 |
| held-out batches, after | **10/16** | **6/16** | **0** | **0** |
| ~~10 notes, final set plus the U1 **simulation** (diagnostic only, never a measurement)~~ | ~~11/16~~ | ~~5/16~~ | 0 | 0 |
| 10 notes, the JUDGE's final set (FX-R1, FX-SCORE widened, FX-EXP-COMPETE narrowed, FX-DEV-MEMBER, E1j, E5j) [R:all] | **8/16 (50%)**; F3all 8/9, F3long 0/7 | **8/16 (50%)** | **0** | **0** |
| held-out batches, the judge's final set | **10/16 (62%)** | **6/16 (38%)** | **0** | **0** |
| 10 notes, the judge's final set plus the U1 simulation (diagnostic only) [R:reproduce-F4] | 8/16; F3long 0/7 | 8/16 | 0 | 0 |

The denominator falls from 17 to 16 because FX-EXP-COMPETE expects B-fb10 99214 HELD. Every replayed row that changed
is listed in section 4 and in `S/runs/rowdiff-base-final.txt`.

**The long notes do not move under replay.** Every hold on them rests on a reading that only a new recording can
change: the kind cascade (U1), the K6 double listing (U2), and the reader causes on C2MEM-023. E2, E3 and E4 remove
holds that sit behind those (note8 45380 drops from 14 held facts to 10, 45386 from 4 to 1, 43249 from 5 to 2). In the
U1 simulation, note8 45380, 45385 and 45386 become READY and correct.

> [R:reproduce-F4][R:design-F4][R:false-ready-FR-1] **Withdrawn.** E2, E3 and E4 are rejected, so the holds behind
> the kind cascade stay. The judge's re-run of KINDSIM2 on the final set (`J/runs/simfinal2`) leaves F3long at 0/7 with
> no wrong READY: note8 45385 is held by `coding_rule:COLFULL` (the reach: U2/U3); 45380 and 45386 by
> `relation:unresolved` (the anastomosis place, Q2, and the lesion-only statements, Q10); 45390 by `relation:unresolved`
> (E35 against E21, which only U1's kind-neutral place pair controls can settle; the simulation does not create them);
> 45381 by design. The long notes need contract and instruction changes recorded again under D277, not engine rules.
> (`[R:all]` marks a change that follows from the decisions as a whole rather than from one finding.)

The acceptance bar (READY recall at least 70%, unnecessary holds at most 15%) is not met by what replay can measure.
It needs U1 and the instruction principles, recorded again under D277's pair testing.

## 1. Method

- **Copies.** Eight base trees were made with `cp -a` (`S/trees/base-{F3all,F3long,F2p2,D2low,D2med,D1v,D1w,step8}`)
  from `probe-fable52-v2`, `-v3`, `probe-fable52`, `probe-d2-low`, `probe-d2-medium`, `probe-jsonmode-medium`,
  `probe-jsonmode-low` and `step8-195e06e90`. `diff -rq` against each source: 0 differences.
  - **D1v/D1w accommodation (not a fix).** Settle refuses on the jsonmode trees because their health pin is unwritten
    (the recorded `devsets/replay-D1v/SUMMARY.json`: `settle_refused`). Their base and fix copies therefore carry the
    provisional pin of `probe-d2-*` (`S/patches/pin_provisional.py`). With it, `base-D1v` is byte-identical to
    `probe-d2-medium` and `base-D1w` to `probe-d2-low`.
- **Edits.** Every edit is a script in `S/patches/` applied by `S/tools/apply.py`. The script asserts each anchor
  occurs exactly once, prints the sha256 before and after, and re-reads the file to check the new text landed. The same
  edit went into every batch's copy, and the patched files are byte-equal across copies (sha256 printed).
- **Baseline.** `S/tools/replay_v2_base.py` differs from `tools/v2/replay_v2.py` only in the v2lib path and in where
  `v2lib.boot` puts its run directories (`S/runs/`). It reproduces every recorded replay byte for byte:
  - F3all 32 files, F3long 8, F2high-p2 24, D2low 16, D2medium 4, 0 differ;
  - every `rows.jsonl` is identical to `devsets/score-*`.
- **Runs.** `S/tools/runset.sh` replays the 7 batches and scores each. `S/tools/rowdiff.py` lists every changed row.
- **Tests.** The `tests.v2` package ran on copies of `step8-195e06e90` through `tools/t.sh`, one suffix per run:
  `holds-synth-base1`, `-full1`, `-full2`, `-final1` and `-attr-*`.

## 2. The groups (root causes), each with its class and decision

### Group 1. The replay harness measures a stricter R1 than the product ships (fb10 45330)

- **Trace** (fb10 analyst, re-verified).
  - `tools/v2/replay_v2.py:167-170` hands assess an `Integrity` whose `word_runs = None`, used at `:311`.
  - The pipeline's R1 is `jobs.py:4249-4259`, whose `word_runs` is `contract/geometry.word_runs`, per DECISIONS
    D261 and its note (`W/DECISIONS.md:15598-15606`, `15658-15665`).
  - Under the harness, the decoy 45331's quote "No biopsies were taken." with its stop is a PARTIAL cover
    (`engine/evaluate.py:1542-1550`), so 45331 stays counted.
  - `combination.base_included` (`engine/combination.py:1290-1325`) then holds 45330.
- **Class.** Whenever a provider quote passes a statement's covering words only by characters that are no letter or
  digit, the harness reads a partial cover where the product reads a citation.
- **Decision.** FX-R1, a harness fix. It is AMENDMENT-2 §5.3 step T, already adopted (D279).

### Group 2. The scorer reads a READY on an act's own sentence as a wrong READY when the expectation quotes a line that retells it

- **Trace.**
  - `tools/v2/score_v2.py:301-303` compares the act's anchors only.
  - `engine/measure.py:278-287` exports only anchor units.
  - The instruction forbids anchoring an act on an impression or summary line (`contract/extract_prompt.py:137-138`).
- **Rows.**
  - A-v5 45380 on F3all, F2high-p2 and D2medium (Gemini medium).
  - The latent cases note8 45386 and 45390 (expected spans in E14's S149 and E21's S141) and A-v3 45386 (S9, E4's
    restatement).
- **Class.** Whenever the expected act span lies on a line that retells the READY act and that no event anchors.
- **Decision.** FX-SCORE: AMENDMENT-2 §6 parts 1-2 (adopted by D279), with one tightening: only roles `restates` and
  `summarizes` count as retelling the act. A title, names_only or refers_back line does not (FINAL-V2 4.7: "a title is
  never a statement").
- **Rejected (D276: per document).**
  - The note8 analyst's `expectations-fd.json` (F-D: extra spans for note8 45386 and 45390).
  - The v3 analyst's `expectations-v3act.json`.
  - AMENDMENT-2 §6 part 3's single-case expectation edit.
  - The general scorer rule replaces all three.

### Group 3. Two office visit codes for one visit, and no member values (fb10 99214: base_included, competing_codes, context_missing)

- **Trace** (fb10 analyst).
  - 99204 and 99214 are proposed for the one visit E1.
  - No v2 rule may read the document's "established patient" (D3, `W/DECISIONS.md:17-19`; FINAL-V2 R6:context
    `W/FINAL-V2.md:1261`), so 99204 stays counted.
  - The two codes hold each other: `combination.is_base`, `engine/combination.py:904-911`, "two E/M codes of one visit
    hold each other".
  - They also compete: D40, `W/DECISIONS.md:226-235`, "CPT Studio never chooses between two codes for one act".
  - The installed c2e53f8e holds both too (`H/fb10/installed-c2e53f8e-F3all.jsonl`).
- **Class.** Whenever a proposal set holds two or more office visit codes for one visit, READY is not the outcome the
  design gives that proposal set. Whenever an E/M case carries no member values, D3's question masks every other cause.
- **Decision.** FX-EXP-COMPETE (expectation rule) and FX-DEV-MEMBER (devset input; AMENDMENT-2 §5.4 step T). The
  em_basis and same_day_em causes are Group 9 (U6).

### Group 4. A biopsy with no lesion beside a removal, with part of the biopsy established elsewhere (fb05 45380)

- **Trace** (fb05 analyst, re-verified on my copies).
  - `coverage.py:1256-1263` `_biopsy`.
  - `_same_lesion` asks `facts.apart_by_place` (`engine/facts.py:1043-1067`), which needs EVERY place pair disjoint.
    The biopsy's `left_colon` contains the removal's `descending_colon` (`engine/anatomy.py:112-119`, `208-215`), so
    the bundling identity is U.
  - Yet the biopsy's `right_colon` is supported, and the pair control "the removal was done in the right colon" was
    rejected (K100).
- **Class.** Whenever a biopsy's lesion slot is empty (no doubt names it), its place list is established, and one of
  its supported places is established apart from EVERY removal it may belong to (disjoint, that removal asked about the
  place by a rejected control, every place control on the biopsy and on those removals rejected), the biopsy is not
  wholly a biopsy of a removed lesion.
- **Decision.** E1.

### Group 5. An act at an anastomosis is never set apart by place (note8 45386, 45380)

- **Trace** (note8 analyst, re-verified).
  - `anatomy.disjoint` returns False for any ALTERED place (`engine/anatomy.py:212`).
  - So E28 and E36 (denials at the splenic flexure and the rectum, every control rejected) pair UNRESOLVED with the
    dilation E14 at the anastomosis. E25 and E36 do the same with the biopsy E13.
  - FINAL-V2 5.1 rows 11 and 51 (`W/FINAL-V2.md:1652`, `1692`) say D34's compared landmark is replaced by
    "`target.anatomy` / `reached_anatomy` with the entry's subtype and joins", and that it "stays over" the pairing
    target row.
  - But `target.anatomy` is claimed only for statements (`engine/requirements.py:753`), never for acts (the ACT rows
    at `:727-745`). Every recorded act's `target.anatomy` therefore settles `unappraised` (note8 E13 and E14: Y1,
    unresolved), and the design's replacement can never place an act.
  - `engine/anatomy.anastomosis_place` (`:235-237`) is defined and called nowhere in `engine/`.
- **Class.** Whenever an event's established place is the anastomosis of an encounter whose one anastomosis entry is
  typed (type and subtype supported, with a D34 place), the target row cannot set that event apart from a statement or
  act at any other place.
- **Decision.** E2, the installed D34 reading (`W/DECISIONS.md:161-170`, made for this very class: "Note #8's 45386
  is held in every run"), kept under D216 rule 3. The pair controls stay on the stored places (P3: a list's
  completeness is read only through rejected controls).
- **Design-faithful complement, not replayable.** Claim an act's `target.anatomy` (one CLAIMED row), so that row 11
  can rest on the act's own appraised entry.
- **Judge: E2 REJECTED** [R:design-F1][R:generality-RG-2]. D34 is a ruling of the never-installed Gemini v1 path
  (`W/DECISIONS.md:161-170`, `:191`); the installed c2e53f8e (D15, `W/DECISIONS.md:67`) has no D34 code and HOLDS note8
  45380 [conflict:biopsy, extent] and 45386 [conflict:dilation, extent] (`H/fb10/installed-c2e53f8e-F3all.jsonl`), so
  rule 3 licenses nothing here. E2 also fails its own class: it counts only a claimed type value
  [R:false-ready-FR-2][R:design-F3]; in D228/D238's own arm it sets a possible statement apart with no control at all
  [R:false-ready-FR-1][R:design-F2][R:generality-RG-3] ("P3 holds through the rejected controls" is false there: two acts
  of one kind get no pair control, `contract/claims.py:2715-2726`); D34's one-side table places the colonic side of a
  right hemicolectomy's ileocolic anastomosis (the transverse colon) on the right colon [R:false-ready-FR-1]; its entry
  guard can never fire for an act [R:false-ready-FR-4]. Its replacement is the complement above, promoted to Q2 and to
  THE FINAL FIX LIST's design items: an act's appraised `target.anatomy`, placed by the entry's subtype AND joins, read
  by pairing, bundling and E1 alike [R:generality-RG-4][R:generality-RG-12].

### Group 6. A lesion-only statement is set apart only by `distinct_from` (note8 45380 via E19, 45386 via E32)

- **Trace.**
  - The single and listed arms (`engine/pairing.py:594-605`, `679-686`; `facts.py:1022-1040`) need `distinct_from`,
    which the reader gives only when the document says so (`extract_prompt.py:99-102`).
  - The lesions' own places are established (L5 neo-terminal ileum, L8 transverse colon, L9 splenic flexure, L10
    descending colon, L3/L4 anastomosis), with their controls rejected.
- **Class.** Whenever a statement names its target by lesion, both lesions' own place lists are established and
  disjoint, and the lesion pair controls are rejected.
- **Decision.** E3, under FINAL-V2 5.1 row 10 (`W/FINAL-V2.md:1651`: "`target.places` and the lesion's places"). It
  extends 4.2's literal `distinct_from`, so it needs a DECISIONS entry.
- **Judge: E3 REJECTED** [R:design-F6][R:false-ready-FR-7][R:false-ready-FR-3][R:generality-RG-5][R:generality-RG-6].
  A reader that splits one lesion into two entries gives them two place words, which are disjoint by construction; that
  split is exactly the failure `distinct_from` guards. E3 also discards a contradicted `distinct_from` (pass 2
  supported "the same lesion"; `_possibly_same` reads only `same_as`, `engine/pairing.py:572-579`) against [R:HO-3]
  (`W/FINAL-V2.md:982-984`), treats a junction's two place words as two lesions (Q07, R08), ignores the act's own place
  (VS11) and leaves the root cause untouched for an act that names no lesion (VS09b/VS09c). Group 6 stays a design
  question: a lesion place pair control ([R:SC-B]) and a lesion-only statement's claimable places, then a ruling on 4.2.

### Group 7. COLFULL ignores an established passage through an ileocolic anastomosis (note8, latent)

- **Trace.**
  - note8 X1: `reached neo_terminal_ileum` is unresolved by K6 (also listed in `device_reached`;
    `contract/consistency.py:636-641`).
  - `reached_anatomy` is silent.
  - `through` Y1 is supported (K3), with Y1's subtype ileocolic supported.
  - `_extent_row` (`engine/assess.py:1215-1253`) reads only reached and reached_anatomy, so it gives U.
- **Class.** Whenever the beyond-point reach is not established while the session's `through` names an entry whose
  subtype is in `COLONOSCOPY_FULL_SUBTYPES`.
- **Judge: E4 REJECTED** [R:design-F4][R:false-ready-FR-8][R:generality-RG-11]. With one anatomy entry `session.through`
  is UNCONTROLLED (D196, `contract/claims.py:1268-1270`, `:1296`) "because the class fit also needs the approach and the
  entry's type, both controlled"; E4 needs neither, so a pass-1 link of the scope's passage to the only listed entry
  (D57's filing) meets COLFULL for a colonoscopy that stopped in the transverse colon (RS05), and an ileotransverse
  bypass with the cecum negated is met too (Q08, R09). It is also NARROW: `through` is supported in 1 of the 6
  recordings of its clinical class. The reach is the instruction's (U2, U3); the original decision below is superseded.
- **Decision.** E4.
  - D38 (`W/DECISIONS.md:203-207`): CPT's extent includes the "small intestine beyond an anastomosis".
  - D44.
  - FINAL-V2 5.1 row 25 (`W/FINAL-V2.md:1666`): the v1 reader judged "extent through an anastomosis".
  - `through` is claimed ("In session {X} the scope passed through anatomy {Y}.", `W/FINAL-V2.md:857`) and G5-checked
    (`:785`).

### Group 8. The kind cascade (note8 all five codes; C2MEM-023 cause B)

- **Trace.**
  - A doubt on a statement's kind makes every statement-phrased claim Unclaimable.KIND (`contract/claims.py:1848-1851`,
    `1861-1864`).
  - The statement's undoubted status, date, place, device and breadth therefore settle unresolved(unappraised)
    (`contract/settle.py:379`, `400`).
  - It becomes a possible statement whose kind covers the whole family (`engine/facts.py:955-975`; FINAL-V2 4.2/4.5
    [R:HO-5]; D191).
  - Nothing can set it apart (`engine/pairing.py:322-325`, `398-420`, `462-466`, `888`, `902`).
  - FINAL-V2 3.2.1 (`W/FINAL-V2.md:824`) asks for those facts to be claimed, but every 3.2.2 statement template names
    `{kind label}`.
- **Class.** Whenever pass 1 doubts a statement's kind.
- **Decision.** U1 (contract; unmeasurable by replay) together with its guard E5 (engine; measured).
  **Judge:** the guard is E5j [R:generality-RG-1][R:design-F7][R:reproduce-F1]: E5 covered two of the electrosurgical
  devices its class names, so an argon plasma act beside "no electrocautery" stayed READY (VR10b, reachable today; the
  installed release holds it, I-VR10b), and U1 as proposed would have left argon plasma unguarded (VR10, JR05).
- **Rejected.** The analysts' W2 (an unestablished kind read as its readings only). It contradicts FINAL-V2 4.2 and
  [R:HO-5], and its own risk input releases 45385 on "The polyp was not removed today." misfiled with a kind doubt.

### Group 9. Reader readings the instruction leaves open, and holds the design asks for

| row | cause | decision |
|---|---|---|
| A-v3 45386 COLFULL | the reach beyond an anastomosis is told in an act's sentence (G5 `extent_inferred`, `contract/geometry.py:660-673`); `reached_anatomy` is defined as the furthest point (`W/FINAL-V2.md:298`, P19 `633-636`; `extract_prompt.py:246-247`; `claims.py:343`) | **U3** (instruction, claim template, G5 on reached_anatomy, design text). Rejected: the single-anastomosis engine inference (v3 W1), because of D57's hazard (`W/DECISIONS.md:496-509`) and P3 |
| note8 K6 | a point the endoscope reached is also listed in `device_reached` | **U2** (E4 covers note8's COLFULL without it) |
| note8 45381 | tattoo target L9 is a finding beside the site; E39 is a one-place "segment"; E29's place is doubted between two segments | **U4** for L9 and the segment. The place doubt is faithful (the words leave two segments), so the remaining question about it is D216 rule 4's one focused question |
| fb10 99214 em_basis, same_day_em | a doubt filed when two bases are stated; `DoubtAbout.VISIT` covers both visit attributes (`contract/extract_schema.py:310`) | ~~U6~~ **withdrawn** [R:design-F0]: no rule can check a visit's level (the contract carries only the basis kind, `contract/types.py:670-673`), so the doubt's hold is the only thing between an over-coded visit and READY. The hold stays (FX-EXP-COMPETE already expects 99214 HELD) |
| C2MEM-023 45390, cause D | a denial of another act's device on this target is not filed | **U7** |
| C2MEM-023 cause A | pass 2 reports as unlisted a sentence pass 1 already doubted. Pass 1's doubts are not in the pass-2 request, and doubted facts are never claimed (`contract/appraise_prompt.py:115-120`). Rule 4 pairs the report with every act (`engine/pairing.py:835-855`), and D231 makes the two codes compete (`engine/combination.py:1001-1030`) | **No engine change.** The c2mem023 analyst's W1 (settle absorbs it) amends FINAL-V2 3.2.6, releases nothing alone because cause C stays, and carries a stated risk; W1b leaves D231's competition. Open question Q3 |
| C2MEM-023 cause C | pass 1 extends "All of the above was done by her previous gastroenterologist" to the procedure section (a performer doubt on E13) | **No change** (D216 rule 4: one focused question). Open question Q4 on which question is asked |

## 3. The fix set: class, justification, exact change, effect, tests, risk

### FX-R1: the replay harness uses the pipeline's own R1 (harness; group 1)

- **Class.** Whenever replay assesses a recording, R1 is the product's: `jobs._Integrity` (word runs per D261).
- **Justification.** D261 and its note. AMENDMENT-2 §5.3 (step T). `replay_v2.py`'s own docstring says "R1 as the
  pipeline hands it in".
- **Change.** `S/tools/replay_v2_r1.py` (diff `S/patches/tool-replay_v2_r1.diff`).
  - Before: `replay_v2.py:167-170` `class Integrity: ... word_runs = None`, and `:311`
    `integrity=Integrity(), provider_status=...`.
  - After: `integrity=pipeline_integrity()`, where `pipeline_integrity()` returns the tree's `studio.jobs._Integrity()`.
- **Effect** (`S/runs/r1only` against `base`).
  - F3all: B-fb10 45330 HELD -> READY (correct). B-fb10 45331 and A-v5 45385 HELD -> EXCLUDED: both expected
    NOT_READY, so both correct.
  - F2high-p2: the same three rows.
  - D2medium (Gemini medium): A-v5 45385 HELD -> EXCLUDED (correct).
  - F3long, D2low, D1v and D1w: unchanged.
  - No wrong READY and no wrong exclusion.
- **G2.**
  - S09a: a denial quoted with its stop is EXCLUDED under the pipeline R1 and HELD under the old one.
  - S09b: a quote running into the next word stays HELD under both. The word runs never extend a cover into another
    word.
- **Tests.** Tools only; `tests.v2` is unaffected.
- **Risk.** A trailing mark that carries meaning, combined with a reader miss (the fb10 analyst's footnote example).
  The product already behaves exactly this way.
  - [R:false-ready-FR-10] Realized on a synthetic input: "No biopsies were taken (?)" filed as an established denial
    is EXCLUDED under the pipeline R1 and held under the old harness (Q10, every tree). Kept: the harness must measure
    the R1 that ships (D261). The reader-side guard is the instruction principle U8 (section 6).

### FX-SCORE: a READY act counts by a line that retells it (scorer; group 2)

- **Class.** Whenever a READY row's act anchors overlap no expected act span X, X still matches when all three hold:
  - (a) X overlaps no event's anchor;
  - (b) exactly one event lists a restatement overlapping X that passes G6's anchored-unit test and whose role is
    `restates` or `summarizes`;
  - (c) that event is one of the code's acts.

  Such a row is `correct`, with kind `restatement`, and is counted in `acts_matched_by_restatement` for first-hand
  review.

  **Judge's class** [R:generality-RG-8][R:reproduce-F6]: (b) and (c) become "at least one event lists a telling
  restatement overlapping X, and EVERY event that lists one is one of the code's acts", so the faithful multi-act
  summary (the impression line every act of the code lists, M7/M7b) counts and a line any other event retells still
  refuses (M2, M5, JM8). The restatement's role claim must also have passed its geometry check (the code already
  required it; now stated). Built as `J/tools/score_v2_s6.py`.
- **Justification.** AMENDMENT-2 §6 parts 1-2 (D279); `extract_prompt.py:137-138`. The role restriction is stricter
  than §6: a title is never a statement (FINAL-V2 4.7).
- **Change.** `S/tools/score_v2_s6.py` (diff `S/patches/tool-score_v2_s6.diff`).
  - Before: `score_v2.py:301-303` `elif expected.get('acts') and not any_overlap(...anchor...): wrong_ready, kind act`.
  - After: the same arm also requires `not by_restatement(export, code, expected['acts'])`.
  - The event table is emulated from the replay's own `inventory.json`. The build implements it as AMENDMENT-2 F9's
    export @2 (`engine/measure.py` adding `events`). `measure.py` is not edited here, so `tests.v2` is untouched.
- **Effect** (`S/runs/scoreonly` against `base`). A-v5 45380 goes from wrong_ready (act) to correct (restatement) on
  F3all, F2high-p2 and D2medium (Gemini medium). Nothing else changes.
- **G2** (`S/g2/measure_rules.py`, all pass):
  - M1 (a summarizing line listed only by the READY act) and M6 (a `restates` line) are correct;
  - M2 (the line listed by two events), M3 (the line is another event's anchor), M4 (a title restatement) and M5 (the
    line listed by an event that is not the code's act) stay wrong_ready.
- **Risk.**
  - AMENDMENT-2 §6's stated limit applies: a summarizing line pass 1 attaches to the wrong act of the same kind, with no
    other event listing it.
  - The rule errs toward refusal. In the U1 simulation (section 5), note8 45390's READY lands on E21, whose summary line
    S141 is also listed by E31, so condition (b) keeps it `wrong_ready` (act). The note8 analyst verified first-hand
    that it is the same act. Such rows need a reviewer's reading, not a looser rule.

### FX-EXP-COMPETE and FX-DEV-MEMBER: the expectation and devset inputs (group 3)

- **Class.**
  - EXP-COMPETE: whenever a document's proposals hold two or more office visit codes, every READY expectation among
    them is HELD with the question `[competing_codes, base_included]`. Office visit codes are the tree catalogue's
    `office_em` base profiles.
  - **Judge** [R:design-F9][R:generality-RG-9]: **for one visit** only, read as "the expected act spans of the
    document's office visit codes all overlap one another"; codes expecting two or more visits keep their expectations
    (`J/tools/devset_rules.py`). RG-9's further claim (a member-entered status makes the other category's code
    inapplicable, so the right one should be READY) is rejected under D40 (`W/DECISIONS.md:226-235`: two E/M codes for
    one visit are held with base_included plus competing_codes, the installed doctrine).
  - **Judge** [R:generality-RG-10][R:false-ready-FR-11]: DEV-MEMBER makes a pre-existing false READY measurable (a lone
    wrong-category visit code READY for an entered status: VE2, M06, and the installed release I-VE2). Its fix, FX-CAT,
    is an owner question in THE FINAL FIX LIST; it must be ruled before an acceptance run enters member values.
  - DEV-MEMBER: every document proposing an office visit code carries the member values the devset author enters from
    the document's own words. The words are recorded with the value and checked to occur in the document.
- **Justification.** D40; `combination.is_base`; D3; AMENDMENT-2 §5.4.
- **Change.** `S/tools/devset_rules.py` and `S/devsets/member-values.json` (B-fb10: setting office, "Seen today in
  the office"; patient status established, "established patient"). Output: `S/devsets/{d3fable,d2cmp,d1}`, where
  `CHANGES.txt` lists every change.
- **Effect** (`S/runs/devonly`).
  - B-fb10 99214 goes from unnecessary_hold to correct on F3all and F2high-p2.
  - `context_missing` leaves 99204 and 99214.
  - No status changes.
- **G2.**
  - Synthetic devset (`S/g2/devset-synth*`):
    - two visit codes -> both HELD-expected;
    - one visit code -> unchanged, with values set;
    - a procedure-only document -> unchanged.
  - Engine:
    - R10: 99213 and 99214 proposed together are held (base_included), as the rule expects;
    - R10b: 99214 alone, with member values and a stated basis and separateness, is READY. The rule leaves a lone visit
      code READY.
- **Risk.** No engine output changes. On this proposal set, the corrected expectation hides fb10's reader-caused holds
  (they stay listed as causes; U6).

### E1: biopsy elsewhere (engine `coverage.py`; group 4)

> **Judge: NARROWED to E1j** [R:false-ready-FR-5][R:generality-RG-7]. E1 read each removal's `target.places` only, so
> a removed lesion established at the biopsy's "elsewhere" place still released (M07, VS04). E1j reads each removal's
> places as its `target.places` TOGETHER WITH its target lesion's established places (FINAL-V2 5.1 row 10), and leaves
> the rule as it was when a removal's lesion claim is neither a supported lesion with established places nor a pure
> silent slot. The read-set gains `_r(Role.LESION, _A.PLACES)` in BUNDLING (P-INDEP). [R:false-ready-FR-6] accepted in
> part: the multi-place junction exposure is named below; no adjacency guard (FINAL-V2 4.13 dropped D58/D77's
> adjacency, and the guard would hold common neighbouring-segment biopsies). Measured in section 4J.

- **Class.** Whenever a biopsy's `target.lesion` is a pure silent slot and its place list is established, the bundling
  rule biopsy_of_removed_lesion is F when one supported place p of the biopsy, for EVERY removal the rule could pair it
  with, meets all of these:
  - the removal's place list is established and all landmarks;
  - p is disjoint from each of the removal's places;
  - the removal was asked about p by a rejected pair control;
  - no place pair control asked of the biopsy or of those removals is unrejected.

  A synthetic whole has no place, so it keeps the old rule.
- **Justification.**
  - FINAL-V2 4.7 bundling identity: "asked | same_as / distinct_from, supported places" (`W/FINAL-V2.md:1425`).
  - 4.11: "a place difference counts only with its pair controls rejected" (`:1558-1560`).
  - D216 rules 2-3 (`W/DECISIONS.md:15453-15459`): a common input, and installed c2e53f8e and v1 both give 45380 READY
    on fb05.
  - The code needs only one specimen elsewhere.
- **Change.** `S/patches/e1_biopsy_elsewhere.py`; `coverage.py` sha256 `6642900f` -> `c1f48ff6`.
  - Before (`coverage.py:1260-1263`):
    ```python
        if Truth.F in (whole_.truth, kind.truth):
            return _FALSE
        return _both(_same_lesion(ask, ask.part, whole), kind, whole_, _single_or_shared(ask, ask.part, whole))
    ```
  - After:
    ```python
        if Truth.F in (whole_.truth, kind.truth):
            return _FALSE
        if _biopsy_elsewhere(ask):  # HOLDS-SYNTH E1
            return _FALSE
        return _both(_same_lesion(ask, ask.part, whole), kind, whole_, _single_or_shared(ask, ask.part, whole))
    ```
  - Plus `_biopsy_elsewhere` (41 lines, `S/patches/final-coverage.diff`): pure silence; `facts_._supported` on the
    biopsy and on every non-F whole; D220's every-control scan; `anatomy.disjoint` with a rejected control for every
    whole.
- **Effect.** B-fb05 45380 goes from unnecessary_hold to READY (correct) on F3all **and on F2high-p2** (Fable under the
  earlier instruction). No other row on any batch changes. No Gemini recording holds the case (D2low's fb05 has no
  pass 2), so the cross-reader evidence for E1 is the G2 set.
- **G2.**
  - Release: S01 (polyp in the transverse colon; biopsies in the proximal and distal colon), R01 (two left-sided
    polyps; random right-colon and left-colon biopsies), R09 (gastric body polyp snared; stomach and duodenum
    biopsies).
  - Hold:
    - S02: two removals together cover both biopsy places;
    - R02: the biopsy names the lesion;
    - R09b: the duodenum control is not rejected;
    - X02: a doubt names the empty lesion slot;
    - X03: the removal's place list is not established.
  - Every release comes from E1 alone (the per-fix columns in section 4c).
- **Tests.** 3 named failures, all of one design fixture, r2d-2 Q2 ("a snare beside a biopsy of two places (EGD)"):
  - `test_properties.PMonoTests.test_the_rulings_accept_their_shapes_alone` (its base 43239 is now READY);
  - `PMonoTests.test_every_single_weakening_of_every_fixture`;
  - `PMonoVerdicts5Tests...under_every_drawn_verdict` (D245_Q2's named release is gone).

  The P-MONO counter (`S/probes/pmono-{base,final}.txt`, 2,858 single weakenings) finds no unnamed release. The only
  difference: "D245 (repair r2d-2's Q2, option (a))" goes from 1 to 0. Landing E1 needs a DECISIONS entry re-pinning
  r2d-2 Q2's base as READY, on D245's own reasoning (`W/DECISIONS.md:15316-15318`).
- **Risk.**
  - X01: a lesion straddling a flexure, biopsied on its transverse side. E1 releases it.
  - X01b shows that the base engine already releases the one-place form of that biopsy, since D58/D77's adjacency was
    dropped (FINAL-V2 4.13). E1 extends that accepted exposure to multi-place biopsies.
  - A pass-2 error that rejects a true control.
  - [R:false-ready-FR-6] The class is every junction, not only flexures (GEJ/cardia, rectum/anal canal: Q06, R06, R07).
    Under E1j a straddling lesion whose places are filed is held (M07, VS04, JS02, JS05, JR02); what remains needs two
    errors: the lesion's extent filed at one segment AND pass 2 rejecting the removal-place control (R07, X01). U9 is
    the reader-side guard.

### E2: D34 in the pairing target row (engine `pairing.py`; group 5)

> **Judge: REJECTED** (section 2, group 5). Counter-inputs, each needs_clarification on base and READY with E2 on the
> judge's copy: Q01, Q02, Q04, Q05, R01, R04, M01, M03, M04 (own arm, no control) [R:false-ready-FR-1]; Q03, Q03d, R03,
> RS02-RS04, RR09 (a second entry possibly an anastomosis not counted) [R:false-ready-FR-2][R:design-F3]; M01, Q03b,
> RS11 (the act's own entry ignored) [R:false-ready-FR-4][R:design-F1]; RR02b (the entry's joins put the anastomosis in
> the denied segment) [R:design-F1]; VX11, VX11c [R:generality-RG-3]. The "Justification" and the "P3 holds through the
> rejected controls" line below are false for the own arm, and X04 is no misfiling: `AnastomosisSubtype` has no
> ileotransverse value, so ileocolic is the correct filing of the commonest case [R:false-ready-FR-1].

- **Class.** Whenever an event's established place set holds `anastomosis`, the disjointness test (only that test)
  compares it as the D34 place (`anatomy.anastomosis_place`) of the encounter's one anastomosis entry, under these
  conditions:
  - exactly one entry has type anastomosis, in any state;
  - its type and subtype are supported;
  - the subtype has a D34 place;
  - the event's session family reaches that place;
  - its `target.anatomy` is not established as another entry.

  The pair controls are still read on the stored places.
- **Justification.** FINAL-V2 5.1 rows 11 and 51; D34; D216 rule 3; `target.anatomy` is not claimed for acts
  (`requirements.py:727-745` against `:753`), so the design's replacement cannot place an act. P3 holds through the
  rejected controls.
- **Change.** `S/patches/e2_d34_target_row.py`, revision 2; diff `S/patches/final-pairing.diff`.
  - Helpers before `_disjoint` (`pairing.py:588`).
  - The listed and segment arm (`:616`) and the own arm (`:675`) compare `_compared(...)` sets.
  - The single arm (`:721`):
    - before: `apart = _apart_by_own_lesion(R, p) or facts_.apart_by_place(R, p.statement, p.act)`;
    - after: `apart = (_apart_by_own_lesion(R, p) or facts_.apart_by_place(R, p.statement, p.act) or
      _apart_by_place_compared(R, p.statement, p.act))`.
  - The D34 arm returns False when D34 changes neither side.
  - **Revision 2's reason.** Revision 1 replaced the single arm's `facts_.apart_by_place` call. That broke
    `test_facts.D220Tests.test_q1_on_a_settled_factset_another_pairs_unrejected_control_holds_the_pair`, which mocks
    that function to show 4.2's earlier reading. Revision 2 keeps the call. Its outputs on all 7 batches are
    byte-identical to revision 1's (69 files compared, 0 differ).
- **Effect.** No verdict changes on any batch. On note8:
  - E13-E25, E13-E36, E14-E28 and E14-E36 become INDEPENDENT by target;
  - held facts: 45380 14 -> 12, 45386 4 -> 2, 43249 5 -> 3, 43239 15 -> 13;
  - 45386's item moves from S106 to S121 (E32).
- **G2.**
  - Release: S03 (dilation at the ileocolic anastomosis; denial in the rectum), R03 (Crohn's: anastomotic dilation and
    biopsies; denials in the sigmoid and the neo-terminal ileum; 45386 and 45380 released).
  - Hold:
    - S04: two anastomosis entries;
    - R04: D57's shape, with the rectum control not rejected;
    - X05: a right-colon place contains the ascending colon;
    - X06: `target.anatomy` names another entry.
- **Tests.** 2 named failures, the committed fixture CK-note8 (step 6c's synthetic filing of GI Note #8):
  - `test_failure_classes.ChecklistTests.test_the_cases` (variant i: the service question `statement_scope` on E3
    disappears);
  - `ResidualTests.test_the_record_is_current` (variant iii: 45380's supporting acts gain E3).

  The probe `S/probes/ck_note8.py` shows why. E3 is the biopsy of the anastomosis and E14 the biopsy denial at the
  splenic flexure. Base: target UNRESOLVED. E2: target INDEPENDENT. This is E2's intended effect; the fixture's pins
  and `RESIDUALS.json` are re-recorded with the ruling.
- **Risk.**
  - X04: D34's known limit. An ileotransverse anastomosis filed as ileocolic is placed on the right colon.
  - A second, unlisted anastomosis, guarded by the controls (R04).

### E3: lesion places set two target lesions apart (engine `pairing.py`; group 6)

> **Judge: REJECTED** (section 2, group 6). Counter-inputs READY with E2+E3 on the judge's copy: R05 (through E2's D34
> mapping) [R:false-ready-FR-3]; Q07, R08 (one polyp under two junction place words, a same-day correction denying the
> removal) [R:false-ready-FR-7]; RS10, RR08 (pass 2 contradicted `distinct_from` and supported "the same lesion")
> [R:design-F6]; VS11 (the act's own place equals the denied lesion's) [R:generality-RG-6]. VS09b, VS09c stay held on
> every tree: the class misses an act that names no lesion [R:generality-RG-5]. The "Risk" line's R06b is the rule's
> central exposure, not a rare one.

- **Class.** In the single and listed/segment arms, two target lesions also count as distinct whenever both lesions'
  own place lists are established and disjoint, an anastomosis compared as E2 places it. Every other condition stays:
  - supported, different lesions;
  - not possibly one lesion;
  - both lesion pair controls present and rejected.

  The own arm (D228/D238) is left out, because no control is required there.
- **Justification.** FINAL-V2 5.1 row 10. It needs a DECISIONS entry (4.2's literal text names `distinct_from`).
- **Change.** `S/patches/e3_lesion_places.py`.
  - `_distinct_by_place` and `_apart_by_lesion_lp` are added.
  - Listed arm (`pairing.py:603`): before `if any(_possibly_same(R, mine, lesion) or not _distinct(R, mine,
    lesion) ...)`; after `... or not (_distinct(...) or _distinct_by_place(R, mine, lesion, p.statement, p.act)) ...`.
  - Single arm (`:682`): before `if not facts_.apart_by_lesion(R, p.statement, p.act):`; after
    `if not _apart_by_lesion_lp(R, p.statement, p.act):`.
- **Effect.** No verdict changes on any batch. On note8, with E2: held facts 45380 -> 10, 45386 -> 1 (only E35 left),
  43239 -> 11, 43249 -> 2.
- **G2.** Release: S05, R05 (a rectal polyp left in place; two others snared). Hold: S06 (the polyp's place not
  stated), R06 (one polyp told twice, a control not rejected), X07 (the snared lesion's place not established), X08
  (overlapping lesion places).
- **Tests.** No failure is attributable to E3: the e23 run fails only E2's two CK-note8 pins.
- **Risk.** R06b: pass 1 splits one polyp into two lesions at disjoint places AND pass 2 rejects both lesion
  controls. The existing place arm already accepts the same exposure when the denial states the place itself.

### E4: COLFULL reads the session's `through` (engine `assess.py`, `requirements.py`; group 7)

> **Judge: REJECTED** (section 2, group 7). Counter-inputs READY with E4 on the judge's copy: RS05, RR05 (an
> uncontrolled one-entry `through`, D196) [R:design-F4]; Q08, R09 (an ileotransverse bypass, the cecum negated)
> [R:false-ready-FR-8]. NARROW: VX08 (Gemini's filing of the same reach) stays held [R:generality-RG-11]. The "Risk"
> line's X09 understates it: the claim it rests on has no control by design.

- **Class.** Whenever COLFULL finds no full reach and no ileocolic `reached_anatomy`, a supported `through` naming an
  entry whose subtype is supported in `COLONOSCOPY_FULL_SUBTYPES` meets it.
- **Justification.** D38, D44, FINAL-V2 5.1 row 25, 3.2.2 (line 857) and G5 (line 785).
- **Change.** `S/patches/e4_colfull_through.py`.
  - `assess.py`, after `:1239-1240`: before, the reached_anatomy arm is followed directly by
    `if stopped and any(...)`. After, the new lines are inserted between them:
    ```python
            passed = _supported_id(facts_.fact(R, session, _A.THROUGH))  # HOLDS-SYNTH E4
            if passed is not None:
                subtype = facts_.fact(R, passed, _A.SUBTYPE)
                if subtype.result is Result.SUPPORTED and subtype.value in catalogue.COLONOSCOPY_FULL_SUBTYPES:
                    return _Row(tag.value, evaluate.Truth.T, session)
    ```
  - `requirements.py:449-450`: COLFULL's read-set gains `_r(_SESSION, _A.THROUGH)` (P-INDEP).
- **Effect.** No recorded row changes. note8's COLFULL hold is latent behind E35. In the U1 simulation, E4 is what
  meets COLFULL there (45385 READY), in place of the instruction fix U2.
- **G2.** Release: S07, R07 (K6 conflict on the neo-terminal ileum; through supported). Hold: S08 and R08 (a colorectal
  anastomosis; reached but not passed), X10 (through unresolved), X11 (a contradicted reach still asks first: D244
  R-K8).
- **Tests.** 1 named failure: `test_requirements.PinTests.test_the_table_and_read_sets_are_pinned_under_the_requirements_
  version`. The read-set changes, so `REQUIREMENTS_VERSION` and its pin move with the ruling.
  `test_assess.IndependenceTests` and `test_properties.IndependenceTests` pass.
- **Risk.** X09: a shared misreading of `through` (pass 1 files it and pass 2 supports a passage that did not happen).
  This is the same verification exposure as any reach.

### E5: electrocautery covers the electrosurgical devices (engine `pairing.py`; U1's guard; group 8)

> **Judge: WIDENED to E5j** [R:generality-RG-1][R:design-F7][R:reproduce-F1]. The code covered hot snare and hot
> forceps only. E5j: `DEVICE_CONTAINS[ELECTROCAUTERY]` = hot snare, hot forceps, argon plasma, radiofrequency (each
> delivers high-frequency current by definition; D222 says so of argon plasma), and a new `DEVICE_MAY_BE`
> (`ELECTROCAUTERY` -> thermal probe, sphincterotome: a heater or bipolar probe; a sphincterotome cuts with or without
> current), read only to keep the technique row UNRESOLVED between two supported devices one of which may be the
> other's kind; it never covers, so a negated electrocautery leaves them possible. **The "Risk" line below is false**
> [R:false-ready-FR-9][R:design-F8][R:reproduce-F2]: the negated arm of `_devices` releases (Q09, R10, RE5neg, Q1/Q2 of
> `e5_probe.py`). The release is definitional and kept, named, and tested (JS10, JR07). Measured in section 4J.

- **Class.** Whenever a statement names electrocautery, it covers acts done with a hot snare or hot forceps.
- **Justification.** FINAL-V2 4.5's technique row (C-16) reads "a device's own kinds" (`DEVICE_CONTAINS`). A hot snare
  and hot forceps are electrosurgical devices, so "no electrocautery was used" cannot set such an act apart.
- **Change.** `S/patches/e5_electrosurgical_devices.py`; `pairing.py:222-225`.
  - Before: `DEVICE_CONTAINS = {SNARE: {COLD_SNARE, HOT_SNARE}, FORCEPS: {COLD_FORCEPS, HOT_FORCEPS}}`.
  - After: adds `Device.ELECTROCAUTERY: frozenset({Device.HOT_SNARE, Device.HOT_FORCEPS})`.
- **Effect.** No verdict changes on all 7 batches; only note8 45382's cause list grows. In the U1 simulation it changes
  note8 45390 from READY (released by the technique row, the wrong reason) to HELD (section 5).
- **G2.**
  - X12 (hold): a hot-snare polypectomy beside a kind-doubted "no cautery" denial at the same site, its device
    established as U1 would let it be. The base engine and E1-E4 give READY: a latent false READY whenever such a
    device is established. E5 gives HELD (conflict:snare).
  - X13 (stays READY): the same with a cold snare.
- **Tests.** 1 named failure: `test_pairing.TableTests.test_device_contains_equals_v1s_by_value`. That test pins
  parity with v1's `relations.DEVICE_CONTAINS`; the new row is the deliberate difference.
- **Risk.** None toward READY: it only adds holds.

## 4. Measurements

### 4a. Both F3 batches (the 10 notes)

Before: the recorded probe (`base` = `devsets/score-F3*`). After: the final set (`S/runs/e5b`).

| batch | before | after |
|---|---|---|
| F3all (8 short notes, 27 rows) | correct 22, unnecessary 4, wrong_ready 1 (artifact); recall 5/10 | correct 26, unnecessary 1; recall 8/9 |
| F3long (2 long notes, 17 rows) | correct 10, unnecessary 7; recall 0/7 | unchanged in verdicts (held facts fewer) |

Every changed row (`S/runs/rowdiff-base-final.txt`):

| row | before -> after | fix |
|---|---|---|
| A-v5 45380 | READY wrong_ready (act) -> READY correct (restatement) | FX-SCORE |
| A-v5 45385 | HELD correct (statement_scope) -> EXCLUDED correct | FX-R1 |
| B-fb05 45380 | HELD unnecessary (reading_unknown) -> READY correct | E1 |
| B-fb10 45330 | HELD unnecessary (base_included) -> READY correct | FX-R1 |
| B-fb10 45331 | HELD correct (statement_scope) -> EXCLUDED correct | FX-R1 |
| B-fb10 99204 | HELD correct; loses context_missing | FX-DEV-MEMBER |
| B-fb10 99214 | READY-expected, HELD unnecessary -> HELD-expected, HELD correct; loses context_missing | FX-EXP-COMPETE, FX-DEV-MEMBER |
| A-note8 43239, 43249, 45380, 45386 | still HELD; item moves to E35's possible statement (S122); held facts 15/5/14/4 -> 11/2/10/1 | E2, E3 |
| A-note8 45382 | still HELD (expected NOT_READY); one more relation cause | E5 |

READY recall: 5/17 -> 8/16. Unnecessary holds: 11/17 -> 8/16. Wrong READY: 1 -> 0. Wrong exclusions: 0 -> 0.

Per fix, each measured alone on top of the measurement fixes (`S/runs/{e1,e2b,e23b,e4,e5b}` against `meas`):
- E1 releases fb05 45380 on F3all and F2high-p2;
- E2 and E3 change held facts only;
- E4 and E5 change nothing.

[R:reproduce-F5] Not so for E5: `S/trees/e5-*` carry E1-E5 (coverage `c1f48ff6`, pairing `2e09cd42`), so `e5b` is the
final set. Measured alone by the reproduce lens and by the judge (`J/runs/e5j`, `e5j2`): note8 45382 gains one cause,
nothing else. [R:reproduce-F3] E2 also changed four C2MEM-023 relations (E25-E14, E28-E15, E34-E14, E34-E15: UNRESOLVED
by timing -> INDEPENDENT by target) and moved note8 43249's item; no scored row. Moot: E2 is rejected.

### 4b. Held-out recordings (G3), each through a copy of the tree that recorded it

| batch (tree) | before | after | changed rows |
|---|---|---|---|
| F2high-p2 (probe-fable52; Fable, earlier instruction; 6 notes) | correct 14, unnecessary 4, wrong_ready 1; recall 3/8 | correct 18, unnecessary 1; recall 6/7 | A-v5 45380 (FX-SCORE), A-v5 45385 EXCLUDED (FX-R1), fb05 45380 READY (E1), fb10 45330 READY and 45331 EXCLUDED (FX-R1), fb10 99204/99214 (FX-EXP, FX-DEV) |
| D2low (probe-d2-low; Gemini low; 4 notes) | correct 6, unnecessary 4 | unchanged | none |
| D2medium (probe-d2-medium; Gemini medium; A-v5) | correct 2, wrong_ready 1 | correct 3 | A-v5 45380 -> correct (restatement); A-v5 45385 -> EXCLUDED (correct) |
| D1v (probe-jsonmode-medium + provisional pin; A-v1) | correct 4; recall 2/2 | unchanged | none |
| D1w (probe-jsonmode-low + provisional pin; A-v1) | correct 3, unnecessary 1 (unlisted) | unchanged | none |

No row became a wrong READY or a wrong exclusion on any held-out batch.

- **Not NARROW.** FX-R1 and FX-SCORE change Gemini rows too (D2medium).
- **NARROW by G3's definition: E1.** It releases one document (fb05) on two Fable recordings (F3all, and F2high-p2
  under the earlier instruction) and nothing on Gemini's, because no Gemini recording holds the case. It justifies
  itself by its class: G2 releases S01, R01 and R09 and holds S02, R02, R09b, X02 and X03. D216 rule 3 supports it too,
  since the installed release gives READY on the input.
- **ENABLING.** E2, E3, E4 and E5 change no verdict on any recording. Each is justified by its class and its G2 inputs.
  [R:all] Judge: E2, E3 and E4 are rejected on their refutations, not on their measurements; E5 is widened to E5j. The
  judge's held-out measurement of the final set is section 4J (identical verdicts).
- **Gemini low's own holds** are a class not traced here: history acts whose status pass 2 qualified as
  history_only, so the status is unresolved and they become possible statements (A-v3, A-v5 and fb02 in D2low), plus
  C-PAIR-4-W2's `geometry_section`. See Q6.

### 4c. G2 inputs outside the 10 notes

> [R:all] The synthesizer's table below is kept as it measured E1-E5. Its E2, E3 and E4 rows test fixes now rejected,
> X04 is no misfiling [R:false-ready-FR-1], X06 uses a state settle never produces [R:false-ready-FR-4], and E5's
> 'hold only' direction is false [R:false-ready-FR-9]. The judge's G2 for the final set (E1j, E5j), and every lens's
> inputs on it, are in section 4J.

- **Inputs.** 10 short, 10 realistic (plus 3 variants) and 14 adversarial or named-risk probes, built from scratch with
  `tests/v2/evaluate_fixtures.py`'s builders (`S/g2/cases.py`; the synthetic sentence of each case is in its
  docstring).
- **Runs.** Each was run on the base engine, each single fix, E1-E4 and the final set (`S/g2/drive.py`,
  `S/g2/{base,e1,e2,e23,e4,full,e5}.json`; table `S/g2/g2-table.txt`).
- **Results.** Every release case is released by its own fix alone, and every hold case is still held under the final
  set. Named risks are reported, not passed.

| id | fix | direction | code | base | E1 | E2 | E2+E3 | E4 | final | final item |
|---|---|---|---|---|---|---|---|---|---|---|
| S01 | E1 | release | 45380 | HELD | READY | HELD | HELD | HELD | READY | - |
| S02 | E1 | hold | 45380 | HELD | HELD | HELD | HELD | HELD | HELD | act_target |
| S03 | E2 | release | 45386 | HELD | HELD | READY | READY | HELD | READY | - |
| S04 | E2 | hold | 45386 | HELD | HELD | HELD | HELD | HELD | HELD | statement_scope |
| S05 | E3 | release | 45385 | HELD | HELD | HELD | READY | HELD | READY | - |
| S06 | E3 | hold | 45385 | HELD | HELD | HELD | HELD | HELD | HELD | statement_scope |
| S07 | E4 | release | 45385 | HELD | HELD | HELD | HELD | READY | READY | - |
| S08 | E4 | hold | 45385 | HELD | HELD | HELD | HELD | HELD | HELD | extent (COLFULL) |
| S09a | FX-R1 | exclude | 45331 | old R1: HELD | | | | | pipeline R1: EXCLUDED | - |
| S09b | FX-R1 | hold | 45331 | HELD | | | | | HELD | statement_scope |
| R01 | E1 | release | 45380 | HELD | READY | HELD | HELD | HELD | READY | - |
| R02 | E1 | hold | 45380 | HELD | HELD | HELD | HELD | HELD | HELD | biopsy_of_removed_lesion |
| R03 | E2 | release | 45386, 45380 | HELD | HELD | READY | READY | HELD | READY | - |
| R04 | E2 | hold | 45386 | HELD | HELD | HELD | HELD | HELD | HELD | statement_scope |
| R05 | E3 | release | 45385 | HELD | HELD | HELD | READY | HELD | READY | - |
| R06 | E3 | hold | 45385 | HELD | HELD | HELD | HELD | HELD | HELD | statement_scope |
| R06b | E3 | named risk | 45385 | HELD | HELD | HELD | READY | HELD | READY | - |
| R07 | E4 | release | 45385 | HELD | HELD | HELD | HELD | READY | READY | - |
| R08 | E4 | hold | 45385 | HELD | HELD | HELD | HELD | HELD | HELD | extent (COLFULL) |
| R09 | E1 | release | 43239 | HELD | READY | HELD | HELD | HELD | READY | - |
| R09b | E1 | hold | 43239 | HELD | HELD | HELD | HELD | HELD | HELD | act_target |
| R10 | FX-EXP | hold | 99214 | HELD | | | | | HELD | base_included |
| R10b | FX-EXP | stays READY | 99214 | READY | | | | | READY | - |
| X01 | E1 | named risk (flexure) | 45380 | HELD | READY | | | | READY | - |
| X01b | E1 | base's own exposure | 45380 | READY | | | | | READY | - |
| X02, X03 | E1 | hold | 45380 | HELD | HELD | | | | HELD | act_target |
| X04 | E2 | named risk (ileotransverse) | 45380 | HELD | | READY | | | READY | - |
| X05, X06 | E2 | hold | 45380, 45386 | HELD | | HELD | | | HELD | statement_scope |
| X07, X08 | E3 | hold | 45385 | HELD | | | HELD | | HELD | statement_scope |
| X09 | E4 | named risk (shared misreading) | 45385 | HELD | | | | READY | READY | - |
| X10, X11 | E4 | hold | 45385 | HELD | | | | HELD | HELD | extent / conflict:examination |
| X12 | E5 | hold | 45385 | **READY** | READY | READY | READY | READY | **HELD** | conflict:snare |
| X13 | E5 | stays READY | 45385 | READY | | | | | READY | - |

The measurement rules have their own G2 inputs: M1-M6 for FX-SCORE, and the synthetic devset for FX-EXP-COMPETE and
FX-DEV-MEMBER (section 3).

### 4d. `tests.v2` (G4)

> [R:all] Superseded for the final set by section 4J (E1j, E5j: five named failures; E1j alone four, E5j alone one).
> The synthesizer's E2 and E4 failures below belong to rejected fixes.

| tree | result | failures |
|---|---|---|
| copy of step8-195e06e90, unmodified (baseline) | **Ran 2496 tests in 442.9s, OK** (`S/tests/base-tests.v2.log`) | none |
| E1-E4, E2 revision 1 | 7 failures | revision 1 broke D220Tests' counterfactual mock; fixed in revision 2 |
| E1-E4, E2 revision 2 | 6 failures (`full2-tests.v2.log`) | the named pins below |
| **final, E1-E5** | **Ran 2496 tests in 391.0s, 7 failures** (`final-tests.v2.log`) | all named, each attributed by a run on single-fix trees (`S/tests/attr-*.log`) |

The seven, and the test each deliberate change amends:
1. `test_properties.PMonoTests.test_the_rulings_accept_their_shapes_alone` (E1: r2d-2 Q2's base is READY).
2. `test_properties.PMonoTests.test_every_single_weakening_of_every_fixture` (E1: D245_Q2 1 -> 0; no unnamed release
   over 2,858 weakenings).
3. `test_properties.PMonoVerdicts5Tests.test_every_single_weakening_under_every_drawn_verdict` (E1: the same fixture's
   DRAWN_RELEASES).
4. `test_failure_classes.ChecklistTests.test_the_cases` (E2: CK-note8 (i) drops the statement_scope question on E3).
5. `test_failure_classes.ResidualTests.test_the_record_is_current` (E2: CK-note8 (iii) 45380 gains supporting act E3;
   RESIDUALS.json).
6. `test_requirements.PinTests.test_the_table_and_read_sets_are_pinned_under_the_requirements_version` (E4: the COLFULL
   read-set).
7. `test_pairing.TableTests.test_device_contains_equals_v1s_by_value` (E5: the v1 parity table).

Attribution runs (the 6 affected modules, 234 tests each):
- e1: 3 failures (1-3);
- e2: 2 (4-5);
- e23: 2 (4-5), so E3 adds none;
- e4: 1 (6);
- E5's (7) appears only on the trees carrying E5.

## 5. The U1 simulation (diagnostic only; never a measurement)

U1 changes the pass-2 request, so replay cannot measure it. The note8 analyst's KINDSIM2 (`S/patches/
sim_fa_kindsim.py`) reads a kind-doubted statement's unappraised facts as pass 2 would have appraised them. It does NOT
create U1's kind-neutral pair controls. On top of the final set (`S/runs/sime5b`, F3all unchanged):

- note8 45380 READY correct (acts E13, E16);
- note8 45385 READY correct (E31; COLFULL met by E4);
- note8 45386 READY correct (restatement, E14);
- note8 45390 HELD: without U1's pair controls the target row cannot set E35 apart from E21;
- note8 45381 HELD (E29's place doubt; E30's contradiction with E20 is by design);
- C2MEM-023 45385 and 45390 HELD (causes A and C).

Without E5 (`S/runs/sim2`), 45390 goes READY by the technique row (E35's electrocautery against E21's hot snare). That
is the wrong reason, and the scorer keeps it `wrong_ready` (act). So **U1 must ship with E5 and with kind-neutral
place pair controls**, and then 45390 can only be set apart by place.

Projected on the 10 notes: recall 11/16, unnecessary holds 5/16, 0 wrong READY, 0 wrong exclusions.

> [R:reproduce-F4] **Withdrawn.** All three note8 releases rested on E4 (without it they are held by COLFULL), and
> 45380/45386 on E2/E3. On the judge's final set (E1j, E5j) the same simulation gives F3long 0/7 and the 10 notes
> 8/16, with no wrong READY (`J/runs/simfinal2`); with no engine fix at all it gives the same 0/7 (`J/runs/simbase`).
> What U1 leaves on note8 is the reach (COLFULL: U2/U3), the anastomosis place and the lesion-only statements
> (`relation:unresolved`: Q2, Q10), and E35 against E21 (U1's own pair controls). U1 still must ship with its guard, now
> E5j (VR10, JR05).

## 6. Instruction and contract fixes (unmeasurable by replay; they need a new recording under D202 and D277)

Each fix below is a general principle with a generic example. None quotes a development note.

- **U1, claims (contract/claims.py; FINAL-V2 3.2.2).**
  - Whenever a statement's kind is doubted, render its status, date relation, own performer, places, lesion, device,
    breadth, targets and segment claims, and its statement-side pair controls, in kind-neutral statement forms. For
    example:
    - "This statement says that the act it names was not done.";
    - "This statement is about the act it names, in the {place}."
  - The kind stays unestablished (D191, HO-5 unchanged).
  - It ships with E5. STATEMENT_TEMPLATES' pin and the pass-2 request bytes change.
- **U2, EXTENT.** "`device_reached` holds only points the endoscope itself never reached. A point the endoscope reached
  goes in `reached`, even when a guidewire, catheter or capsule also reached it. Never list one point in both." Example:
  a wire passed into the jejunum from a scope that stopped in the duodenum: device_reached; a scope that followed the
  wire into the jejunum: reached.
  - [R:false-ready-FR-12] Added, so that an ambiguous reach is never a silent choice (DOUBTS: "Never choose a reading
    silently"): "When the words leave unclear whether the endoscope itself reached a point, list it in `device_reached`
    and add a doubt about `reached`."
- **U3, EXTENT, with its claim and its guard.**
  - Instruction: "`reached_anatomy` names the anatomy entry of an anastomosis or pouch the endoscope itself reached, at
    its furthest point or on its way beyond it, citing the examination's own words that say so." Example: a scope that
    reached a surgical junction and went on into the bowel beyond it.
  - Claim: `claims.py:343` becomes "In session {session} the endoscope itself reached anatomy {anatomy}." D244's shared
    control at `claims.py:1246` is restated as its opposite.
  - Guard: `contract/geometry.py:100` EXTENT_ATTRIBUTES += REACHED_ANATOMY (fail-closed; the v3 analyst measured 0
    changes).
  - Design text: `W/FINAL-V2.md:298`, P19 (`633-636`) and the G5 list (`785`).
  - [R:design] (the lens's UNRESOLVED, recorded): D244 R-ANAT shares one claim because the reached_anatomy control is
    the reach's own sentence (`contract/settle.py:89-100`, `:284-288`); a reworded control shares only if it keeps that
    exact sentence. The build states the wording and re-pins the share.
- **U4, DENIALS and TARGETS.**
  - "A denial confined to one place is single_target with that place in target.places; segment is for a stretch named
    by two different places." Example: nothing was done in the cecum: single_target; nothing between the hepatic
    flexure and the rectum: segment.
  - "An act done beside a lesion to mark or reach it is not done to that lesion: give the place where it was done, and
    leave target.lesion empty unless the document says the act was done to the lesion itself." Example: ink injected a
    few folds beyond a polyp to mark its site.
- **U6 WITHDRAWN** [R:design-F0][R:generality-RG-13]. RU6a ("MDM: low. Total time: 20 minutes.", 99215 proposed),
  filed as U6 prescribes, is READY on every tree; the two-basis doubt holds it (RU6b). No rule can compare a level: the
  contract's `EmBasis` names only the basis kind (`contract/types.py:670-673`) and R6:em_basis reads presence
  (`engine/assess.py:1308-1318`). U6 returns only with level facts and a level rule (owner/design question 5), with no
  basis chosen by position and an example unrelated to any note (fb10's line is "moderate medical decision making; 32
  minutes"). The superseded text follows.
- ~~**U6, VISITS.**~~ "When the document states both a level of medical decision making and a total time for one visit,
  both bases are stated, which is no doubt. Give visit.basis the basis the document says the level rests on, else the
  first it states, and add no doubt about the visit for it. A doubt about the visit is for a basis or a separate
  identifiability the words leave unclear." Example: moderate decision making and 35 minutes, both stated.
- **U7, FACTS (completing AMENDMENT-2 §2.1 item 1, the slot sentence D276 asks to be rewritten generally).** "When a
  sentence says another act's device was not used on this act's target, it denies that other act there. File it also
  as a negated event of that other act's kind with this target, and keep this act's device slot for the device it
  used." Example: a polyp removed with forceps, "no snare was used on it": a negated snare event on that polyp.
- **U8, DOUBTS** [R:false-ready-FR-10]. "A mark of uncertainty inside a denial's own words (a question mark, or a word
  that leaves the denial open) makes its status a doubt, never an established negation." Example: a line that ends
  "no dilation was needed?" files a status doubt.
- **U9, LESIONS** [R:false-ready-FR-6]. "A lesion's places list every segment the lesion lies in or reaches, also
  across a junction; give one place only when the words confine the lesion to it." Example: a flat lesion running from
  one segment over the flexure into the next lists both segments. (E1j reads these places, FINAL-V2 5.1 row 10.)

## 7. Proposals rejected or not carried forward, and why

| proposal | from | why |
|---|---|---|
| expectations-fd.json (note8 45386/45390 spans) | note8 | per document (D276); replaced by FX-SCORE |
| expectations-v3act.json (A-v3 45386 span) | v3 | per document; replaced by FX-SCORE |
| W1, engine single-anastomosis COLFULL inference | v3 | D57's hazard (two anastomoses, one listed: READY where the installed release asks); reads a short list as an absence (P3) |
| V1, D24's silent-lesion reading | fb05 | refuted by pinned design tests (`test_coverage` QF3 and EstablishedBundling) and by risk variants R2, R2b, R7 |
| V2, the per-whole place test | fb05 | releases R7 (two removals covering both biopsy sites); E1 (V3) is its every-whole form |
| W2, a doubted kind read as its readings | c2mem023 | contradicts FINAL-V2 4.2 / [R:HO-5] / P-UNKNOWN-KIND; releases a misfiled-kind denial |
| W1, settle absorbs an unlisted doubt pass 1 filed | c2mem023 | amends 3.2.6's drop rule; releases nothing (cause C stays); risk: a pass-1 doubt narrower than its sentence |
| W1b, unlisted doubt spares an established act | c2mem023 | leaves D231's competition; ignores pass 2's own report |
| F-B as an engine change | note8 | kept as instruction U2; E4 covers note8's COLFULL from an established fact |
| narrowing a back-referring performer doubt | c2mem023 | would drop genuine doubts; D216 rule 4 |
| E2, D34 in the pairing target row | synthesizer | [R:false-ready-FR-1..FR-4][R:design-F1..F3][R:generality-RG-2..RG-4]: void licence (not the installed reading), no control in the own arm, a one-side table that misplaces the commonest anastomosis, a count that drops a doubted second entry; no verdict change on any recording |
| E3, lesion places beside `distinct_from` | synthesizer | [R:design-F6][R:false-ready-FR-3][R:false-ready-FR-7][R:generality-RG-5][R:generality-RG-6]: a lesion split gives disjoint places by construction; discards a contradicted `distinct_from`; no verdict change on any recording |
| E4, COLFULL reads `through` | synthesizer | [R:design-F4][R:false-ready-FR-8][R:generality-RG-11]: an UNCONTROLLED one-entry claim (D196) on a READY path; a bypass releases; NARROW |
| U6, a visit basis chosen without a doubt | synthesizer | [R:design-F0][R:generality-RG-13]: no level rule is possible without level facts; position-dependent |
| the adjacency guard on E1 | false-ready lens (FR-6) | re-introduces D58/D77's adjacency, which FINAL-V2 4.13 dropped; would hold common neighbouring-segment biopsies; the straddling lesion is closed by E1j when its places are filed |
| RG-9's category reading of two visit codes | generality lens | D40: two E/M codes for one visit are held, the installed doctrine |
| fixA-fixD (E2 repaired by joins or both sides) | false-ready lens | still rest on the one-listed-anastomosis inference (Q03b stays released under every variant) and fixD loses note8's own pairs; the design's replacement is an act's appraised `target.anatomy` (Q2) |

## 8. Open questions

- **Q1 (rulings needed before landing).**
  - E1: re-pin r2d-2 Q2's base as READY and remove D245_Q2's named release.
  - E2: D34 in the target row, and CK-note8's pins and RESIDUALS.
  - E3: lesion places beside `distinct_from` (FINAL-V2 4.2).
  - E4: COLFULL's read-set gains `through`; REQUIREMENTS_VERSION and its pin.
  - E5: DEVICE_CONTAINS departs from v1's table.
  - FX-SCORE's role restriction against AMENDMENT-2 §6.
- **Q2 (design).** Claim an act's `target.anatomy` (CLAIMED), so that FINAL-V2 5.1 row 11 works as written and E2 can
  rest on the act's own appraised entry instead of the one-anastomosis reading.
- **Q3 (design).** Pass 2 re-reports a sentence pass 1 already doubted, because doubted facts are never claimed and the
  doubts are not in its request. Could the request show each card's doubted attributes as "doubted, not claimed",
  without weakening independence (FINAL-V2 10, risk 1)?
- **Q4 (question quality).** Row 7's another_occasion exemption (`engine/evaluate.py:821-825`) applies only beside a
  DONE own examination. C2MEM-023's item then becomes the plan E40's question, not the examination's performer.
  D232's "done or not" reading would give the focused question.
- **Q5 (coding rule).** R6:em_basis reads only that a basis is present (`engine/assess.py:1308-1318`). No v2 rule
  compares the visit level with the stated MDM or time, so U6 raises the risk of a READY at a level no basis supports.
  Likewise, a member-entered patient status never excludes the other category's visit codes, though their own
  published definitions demand it.
- **Q6 (held-out class not traced).** Gemini low's history acts that pass 2 qualified as history_only become possible
  statements (D2low), and D1w's unlisted entry. Both are outside the 12 traced rows.
- **Q7 (expectation review).** note8 45390's expected span sits on a summary line that E21 and E31 both list.
  AMENDMENT-2 §6 part 3's report should send it to the development owner. It is not forgiven by rule.
  [R:generality-RG-8] Under the widened FX-SCORE it is still refused: E31 is not one of 45390's acts.

**Judge's revision of the open questions** [R:all]:
- **Q1 now reads:** E1j (re-pin r2d-2 Q2's base as READY; D245_Q2's named release goes; the BUNDLING read-set gains the
  whole's lesion places; REQUIREMENTS_VERSION and its pin move); E5j (DEVICE_CONTAINS departs from v1's table and
  DEVICE_MAY_BE is new); FX-SCORE's widened class against AMENDMENT-2 §6. E2, E3 and E4 need no ruling: they are rejected.
- **Q2 is promoted to the replacement of E2** [R:design-F1][R:generality-RG-2][R:generality-RG-4][R:generality-RG-12]:
  claim an act's `target.anatomy` (CLAIMED), place an anastomosis by its appraised entry's subtype AND joins (FINAL-V2
  5.1 rows 11 and 51), and read that one compared place in pairing, in `coverage._apart` and in E1j, under the pair
  controls that exist in each arm (none is manufactured in D228/D238's own arm).
- **Q5 splits** [R:design-F0][R:generality-RG-10][R:false-ready-FR-11]: (a) FX-CAT, an owner question (THE FINAL FIX
  LIST); (b) a level rule needs level facts the contract does not carry (an MDM level, minutes): a design question, and
  U6's precondition.
- **Q8 (owner)**: D40's hold of two codes for one visit against an acceptance expectation that marks one of them READY.
- **Q9 (owner)**: E1j's junction residual (a lesion reaching a junction, filed at one segment, sampled on both sides,
  with pass 2 rejecting the removal-place control) against re-introducing adjacency.
- **Q10 (design)** [R:design-F6][R:generality-RG-5]: group 6 needs a lesion place pair control ([R:SC-B]) and a
  lesion-only statement's claimable places before any place rule may stand beside `distinct_from` (4.2).

## 9. Disclosures and files

- **Side effects of the instructed tools.**
  - `replay_v2.py` and my copies read the acceptance owner's `DEV-EXCLUSION.sha256` hash list through
    `v2lib.exclusion_hashes`, as designed. I never read or printed it.
  - `tools/t.sh` creates `G/runs/{state,tmp,runq}-holds-synth-*`.
  - My own tools redirect `v2lib.boot`'s run directories to `S/runs/`. Three empty run directories that my first
    devset run made under `G/runs/` were removed with `rmdir`.
- **One stray file, removed.** A misdirected background subshell wrote `pmono-final.txt` (189 bytes, only a Python
  "can't open file" message) into the worktree root at 21:45Z. It was removed with `rm` about a minute later, and a
  `find -newermt '2026-11-15 21:00'` over the worktree (excluding `.git`) and over the original trees lists nothing.
- **Files.** All under `S/`:
  - `patches/`: the edit scripts e1-e5, `pin_provisional.py`, `sim_fa_kindsim.py`, and the diffs `final-*.diff`,
    `fixset-*.diff` (revision 1) and `tool-*.diff`;
  - `tools/`: `apply.py`, `replay_v2_base.py`, `replay_v2_r1.py`, `score_v2_s6.py`, `devset_rules.py`, `runset.sh`,
    `rowdiff.py`, `invsum.py`;
  - `devsets/`: `member-values.json` and the rewritten d3fable, d2cmp and d1;
  - `runs/`: base, meas, r1only, devonly, scoreonly, e1, e2(b), e23(b), e4, e5(b), full(2), sim(2), sime5(b), and the
    rowdiffs;
  - `g2/`: `cases.py`, `drive.py`, `compare.py`, `measure_rules.py`, the results and `g2-table.txt`;
  - `probes/`: `ck_note8.py`, `pmono_counter.py` and their outputs;
  - `tests/`: every `tests.v2` log;
  - `trees/`: about 3.1 GB of copies, reapable once this analysis is judged.
- **Final engine files** (sha256):
  - `coverage.py` c1f48ff6...;
  - `pairing.py` 2e09cd42...;
  - `assess.py` 7e50b3ff...;
  - `requirements.py` 69b91e9a....

  The originals are 6642900f..., 5c1c9447..., 9239dddc... and 312455c7....

**Judge's disclosures and files** [R:all]:
- Everything the judge wrote is under `H` (`HOLDS-REFUTATIONS.md`, this file, `HOLDS-ANALYSIS-pre-refutation.md`) and
  `J`: `trees/` (cp -a copies, each `diff -rq`-checked before its asserted edits; about 3 GB, reapable once judged),
  `patches/` (`j1_e1_lesion_places{,_v2}.py`, `j5_e5_electrosurgical{,_v2}.py`, `judge-final-*.diff`), `tools/` (copies of
  the synthesizer's replay, scorer and devset tools with the run paths redirected to `J/runs`; the scorer and the devset
  rule carry the judge's changes), `devsets/`, `runs/`, `g2/` (`cases_j.py`, its outputs, `g2-table-judge.txt`, the
  synthetic devset `devset-j`), `score/`, `verify/` (each lens's driver and cases re-run), `tests/` (every `tests.v2` log).
- `tools/t.sh` created `G/runs/{state,tmp,runq}-holds-judge-*` (its own design, as the task instructs). `replay_v2_r1.py`
  read the acceptance owner's exclusion hash list through `v2lib.exclusion_hashes`, as designed; I never opened it.
- v1 of E1j and E5j failed `tests.v2` on two named defects of the judge's own (a mypy-strict type check in `_may_be`;
  the whole's lesion places missing from the BUNDLING read-set, caught by P-INDEP); v2 fixes both and is what THE FINAL
  FIX LIST measures. v1's replays and G2 outputs equal v2's (0 rows differ).

## 4J. The judge's measurements of the narrowed set [R:all]

- **Trees.** `J/trees/{base,final2,e1j2,e5j2}-{F3all,F3long,F2p2,D2low,D2med,D1v,D1w,step8}`: `cp -a` of
  `probe-fable52-v2`, `-v3`, `probe-fable52`, `probe-d2-low`, `probe-d2-medium`, `probe-jsonmode-medium`,
  `probe-jsonmode-low` and `step8-195e06e90`, each `diff -rq` 0 against its source before any edit; D1v/D1w carry the
  provisional pin (accommodation, base and fix alike). Edits: `S/patches/e1_biopsy_elsewhere.py`, then
  `J/patches/j1_e1_lesion_places_v2.py` and `J/patches/j5_e5_electrosurgical_v2.py`, through the synthesizer's asserting
  `apply.py`. Final engine sha256 (first 12), byte-equal in all eight trees: coverage `b8113e8ab966`, pairing
  `8cb6c394fab9`, assess `9239dddc258d` (unchanged), requirements `b5511099ff24`. Diffs: `J/patches/judge-final2-*.diff`.
- **Tools.** `J/tools/`: the base run uses `replay_v2_base.py` with the original `score_v2.py` and `G/devsets`; every
  other run uses `replay_v2_r1.py` (FX-R1), `score_v2_s6.py` (FX-SCORE widened) and `J/devsets` (FX-EXP-COMPETE narrowed,
  FX-DEV-MEMBER; equal to the synthesizer's devsets on this material, `cmp`). Every replay exit 0 (`J/runs/*/exits`).
- **Baseline.** The base rows equal the recorded `devsets/score-*/rows.jsonl` byte for byte on F3all, F3long, F2high-p2,
  D2low and D2medium; D1v/D1w equal the synthesizer's base (no recorded rows: settle refused without the pin).

**Both F3 batches and every held-out batch (before = the recorded probe; after = the judge's final set,
`J/runs/rowdiff-base-final2.txt`):**

| batch (tree) | before | after | changed rows |
|---|---|---|---|
| F3all (probe-fable52-v2; 8 notes, 27 rows) | correct 22, unnecessary 4, wrong_ready 1; recall 5/10 | correct 26, unnecessary 1; recall 8/9 | A-v5 45380 correct (restatement, FX-SCORE); A-v5 45385 EXCLUDED, correct (FX-R1); fb05 45380 READY, correct (E1j); fb10 45330 READY, correct, 45331 EXCLUDED, correct (FX-R1); fb10 99214 HELD-expected, 99204/99214 lose context_missing (FX-EXP-COMPETE, FX-DEV-MEMBER) |
| F3long (probe-fable52-v3; 2 notes, 17 rows) | correct 10, unnecessary 7; recall 0/7 | unchanged verdicts | note8 45382 one more `relation:unresolved` (E5j) |
| F2high-p2 (probe-fable52; Fable, earlier instruction) | correct 14, unnecessary 4, wrong_ready 1; recall 3/8 | correct 18, unnecessary 1; recall 6/7 | the same seven rows as F3all |
| D2low (probe-d2-low; Gemini low) | correct 6, unnecessary 4; recall 0/4 | unchanged | none |
| D2medium (probe-d2-medium; Gemini medium) | correct 2, wrong_ready 1; recall 0/1 | correct 3; recall 1/1 | A-v5 45380 (FX-SCORE), A-v5 45385 EXCLUDED (FX-R1) |
| D1v (probe-jsonmode-medium + pin; A-v1) | correct 4; recall 2/2 | unchanged | none |
| D1w (probe-jsonmode-low + pin; A-v1) | correct 3, unnecessary 1; recall 1/2 | unchanged | none |

| set | READY recall | unnecessary holds | wrong READY | wrong exclusions |
|---|---|---|---|---|
| 10 notes, before | 5/17 (29%) | 11/17 (65%) | 1 | 0 |
| **10 notes, the judge's final set** | **8/16 (50%)**; F3all 8/9 (89%), F3long 0/7 | **8/16 (50%)**; F3all 1/9 (11%), F3long 7/7 | **0** | **0** |
| held-out (F2high-p2, D2low, D2medium, D1v, D1w), before | 6/17 (35%) | 9/17 (53%) | 2 | 0 |
| **held-out, the judge's final set** | **10/16 (62%)**: F2p2 6/7, D2low 0/4, D2med 1/1, D1v 2/2, D1w 1/2 | **6/16 (38%)** | **0** | **0** |
| 10 notes, final set plus the U1 simulation (diagnostic) | 8/16; F3long 0/7 | 8/16 | 0 | 0 |

- **Per fix** (each alone on top of the measurement fixes, `J/runs/rowdiff-meas-{e1j2,e5j2}.txt`): E1j releases B-fb05
  45380 on F3all and F2high-p2 and nothing else; E5j adds one cause to note8 45382 and nothing else. v1 and v2 of the
  judge's trees give identical rows (`J/runs/rowdiff-final-final2.txt`: 0 changed).
- **Against the analysis's final set** (`J/runs/rowdiff-synthfinal-judgefinal.txt`): no verdict differs on any batch;
  only note8's held-cause lists (E2/E3 absent).
- **NARROW (G3): E1j**, as E1 was: one document on two Fable recordings; no Gemini recording holds the case with a pass
  2. Its class is carried by G2, including VX10 (Gemini's own pass-1 filing of the fb05 biopsy), released.
  **ENABLING: E5j** (no verdict on any recording; U1's guard), and corrective on a reachable input (VR10b, which the
  installed release holds).

**G2, the judge's inputs** (`J/g2/cases_j.py`, built from scratch with `tests/v2/evaluate_fixtures.py`; 10 SHORT, 10
REALISTIC as the user asked, 3 MORE; the synthetic sentence of each in its docstring; outputs `J/g2/out-*.json`, table
`J/g2/g2-table-judge.txt`; trees base | E1j | E5j | final | the analysis's final):

| id | rule, direction | code | base | E1j | E5j | final | analysis's final |
|---|---|---|---|---|---|---|---|
| JS01 | E1j release (right/left colon biopsies, sigmoid polyp) | 45380 | HELD | READY | HELD | READY | READY |
| JS02 | E1j hold (lesion spans the "elsewhere" segment) | 45380 | HELD | HELD | HELD | HELD | READY |
| JS03 | E1j hold (the snare's lesion is a doubt) | 45380 | HELD | HELD | HELD | HELD | READY |
| JS04 | E1j release (EGD: stomach + duodenum biopsies, antral polyp) | 43239 | HELD | READY | HELD | READY | READY |
| JS05 | E1j hold (the polyp prolapses into the bulb) | 43239 | HELD | HELD | HELD | HELD | READY |
| JS06 | E5j hold (argon plasma beside "no electrocautery ablation") | 45388 | READY | READY | HELD | HELD | READY |
| JS07 | E5j hold (radiofrequency) | 43270 | READY | READY | HELD | HELD | READY |
| JS08 | E5j stays READY (cryotherapy) | 43270 | READY | READY | READY | READY | READY |
| JS09 | E5j hold (thermal probe may be bipolar) | 43255 | READY | READY | HELD | HELD | READY |
| JS10 | E5j release direction (cold polypectomy "without electrocautery" beside "no hot snare") | 45385 | HELD | HELD | READY | READY | READY |
| JR01 | E1j release (two left-sided snares, random right/left biopsies) | 45380 | HELD | READY | HELD | READY | READY |
| JR02 | E1j hold (LST across the splenic flexure, mapping biopsies) | 45380 | HELD | HELD | HELD | HELD | READY |
| JR03 | E1j hold (the polyp's place is a doubt) | 45380 | HELD | HELD | HELD | HELD | READY |
| JR04 | E1j release (EGD: H. pylori and celiac biopsies beside a body polyp) | 43239 | HELD | READY | HELD | READY | READY |
| JR05 | E5j hold (U1's form, argon plasma; the cold snare stays READY) | 45388 | READY | READY | HELD | HELD | READY |
| JR06 | E5j stays READY (clips; "no electrocautery for hemostasis") | 45382 | READY | READY | READY | READY | READY |
| JR07 | E5j release direction (all-of-kind "no hot snare") | 45385 | HELD | HELD | READY | READY | READY |
| JR08 | E5j hold (multipolar thermal probe, "no electrocautery") | 43255 | READY | READY | HELD | HELD | READY |
| JR09 | E1j and E5j together (no interaction) | 45380 | HELD | READY | HELD | READY | READY |
| JR10 | E1j hold (one removal-place control not rejected) | 45380 | HELD | HELD | HELD | HELD | HELD |
| JM01 | E5j hold (sphincterotome may cut with current) | 43262 | READY | READY | HELD | HELD | READY |
| JM02 | E5j: a negated electrocautery leaves a thermal probe possible | 43255 | HELD | HELD | HELD | HELD | HELD |
| JM03 | E1j release (removal with no lesion entry) | 45380 | HELD | READY | HELD | READY | READY |

Every other code of these inputs keeps its base outcome. The last column shows six new counterexamples to the analysis's
E1 (JS02, JS03, JS05, JR02, JR03 READY) and five to its E5 (JS06, JS07, JS09, JR05, JR08, JM01 READY).

**Every lens's inputs on the final set** (`J/verify/out/*-final2-step8.json`; 209 rows): only these move from base:
releases E1j intends (S01, R01, R09, VS01, VS02, VR01b, VX10), E5j's named release direction (Q09, R10, RE5neg), E5j's
holds (X12, VR10, VR10b, VR10c, VX07, RS07, RS08, RR06's 45388), and the named E1j residual (Q06, R06, R07, X01; see
[R:false-ready-FR-6]). Every E2, E3 and E4 counterexample is back to its base hold. The pre-existing READYs M06/VE2
(FX-CAT) and RU6a (U6 withdrawn) are unchanged on every tree. Scorer inputs: M1-M6 ALL PASS, M7/M7b/M7c correct, JM7
counts, JM8-JM10 refuse (`J/score/`). Devset inputs: `J/g2/devset-j` (one visit rewritten; two visits not; procedure
only unchanged).

**`tests.v2` (G4)**, the whole package (2,496 tests) through `tools/t.sh`, a new suffix per run:

| tree (suffix) | result | failures |
|---|---|---|
| unmodified copy of step8-195e06e90 (`holds-judge-base1`) | Ran 2496 tests in 388.3s, **OK** | none |
| final set v1 (`holds-judge-final-1`) | FAILED (failures=15) | the judge's own two defects (5 mypy-strict on `_may_be`; 6 P-INDEP on the missing read-set row) plus the 4 below; fixed in v2 |
| **final set v2 (`holds-judge-final2-1`)** | **Ran 2496 tests in 421.0s, FAILED (failures=5)** | the five named below |
| E1j v2 alone (`holds-judge-e1j2-1`) | Ran 2496 tests in 400.3s, FAILED (failures=4) | 1-4 below
| E5j v2 alone (`holds-judge-e5j2-1`) | Ran 2496 tests in 423.2s, FAILED (failures=1) | 5 below

The five, and the test each deliberate change amends:
1. `test_properties.PMonoTests.test_the_rulings_accept_their_shapes_alone` (E1j: r2d-2 Q2's base 43239 is now READY).
2. `test_properties.PMonoTests.test_every_single_weakening_of_every_fixture` (E1j: "D245 (repair r2d-2's Q2, option
   (a))" 1 -> 0; the P-MONO counter over 2,858 single weakenings finds no other difference and no unnamed release,
   `J/probes/pmono-{base,final2}.txt`).
3. `test_properties.PMonoVerdicts5Tests.test_every_single_weakening_under_every_drawn_verdict` (E1j: the same fixture's
   drawn release).
4. `test_requirements.PinTests.test_the_table_and_read_sets_are_pinned_under_the_requirements_version` (E1j: the
   BUNDLING read-set gains the whole's lesion places; REQUIREMENTS_VERSION and its pin move with the ruling).
5. `test_pairing.TableTests.test_device_contains_equals_v1s_by_value` (E5j: v2's table departs from v1's by value).

## THE FINAL FIX LIST (for the build round) [R:all]

Replay-measurable fixes (each measured on F3all, F3long, every held-out batch, its G2 inputs and `tests.v2`):

**1. E1j, biopsy elsewhere with the removed lesion's places** (engine; owner files `engine/coverage.py`,
`engine/requirements.py`).
- *Class.* Whenever a biopsy's `target.lesion` is a pure silent slot and its place list is established, the bundling
  rule biopsy_of_removed_lesion is F when one supported place p of the biopsy, for EVERY removal the rule could pair it
  with, is disjoint from each of that removal's places (its `target.places` together with its target lesion's
  established places), that removal was asked about p by a rejected pair control, and no place pair control asked of
  the biopsy or of those removals is unrejected. A removal whose lesion claim is neither a supported lesion with
  established places nor a pure silent slot leaves the rule as it was.
- *Justification.* FINAL-V2 4.7 (bundling identity over supported places), 4.11 (a place difference counts only with
  its pair controls rejected), 5.1 row 10 ("`target.places` and the lesion's places"); D216 rules 2-3 (installed
  c2e53f8e READYs fb05 45380, `H/fb05/installed-c2e53f8e-F3all.jsonl`).
- *Exact change.* `S/patches/e1_biopsy_elsewhere.py` (`_biopsy` returns F when `_biopsy_elsewhere(ask)`; the helper),
  then `J/patches/j1_e1_lesion_places_v2.py` (the lesion union and the fail-closed lesion claim in the helper; the
  BUNDLING read-set gains `_r(Role.LESION, _A.PLACES)`). Diffs `J/patches/judge-final2-coverage.diff`,
  `judge-final2-requirements.diff`.
- *Effect.* F3all: B-fb05 45380 HELD -> READY (correct). F3long: none. F2high-p2: B-fb05 45380 HELD -> READY (correct).
  D2low, D2medium, D1v, D1w: none. NARROW by G3, carried by its class (G2 below).
- *G2.* Releases JS01, JS04, JR01, JR04, JR09, JM03, and the lenses' S01, R01, R09, VS01, VS02, VR01b, VX10. Holds JS02,
  JS03, JS05, JR02, JR03, JR10, and M07, VS04, S02, R02, R09b, X02, X03, VR03, VR03b, VX05, M02. Named residual (READY):
  Q06, R06 (argued correct: the samples lie outside the resected lesion's established places), R07, X01 (two errors
  needed; U9).
- *tests.v2.* Failures 1-4 above, each a deliberate change: a DECISIONS entry re-pins r2d-2 Q2's base as READY on
  D245's own reasoning, removes D245_Q2's named release, and moves REQUIREMENTS_VERSION with the read-set.

**2. E5j, electrocautery covers the devices that deliver high-frequency current** (engine; owner file
`engine/pairing.py`).
- *Class.* Whenever a device fact names electrocautery, it covers the hot snare, hot forceps, argon plasma and
  radiofrequency devices (each delivers high-frequency current by definition), so a statement naming electrocautery is
  never set apart by technique from an act done with one of them, and a negated electrocautery excludes them (the
  release direction). A thermal probe and a sphincterotome MAY be electrosurgical: between two supported devices one of
  which may be the other's kind the technique row is UNRESOLVED, and a negated electrocautery never excludes them.
- *Justification.* FINAL-V2 4.5's technique row (C-16: a device's own kinds, DEVICE_CONTAINS); D222 (argon plasma
  delivers high-frequency current); D216 rule 1; the installed release holds VR10b (I-VR10b), so v2's READY there is a
  held-to-READY regression under the owner's amendment of 2026-11-09.
- *Exact change.* `J/patches/j5_e5_electrosurgical_v2.py`: `DEVICE_CONTAINS[ELECTROCAUTERY]` = {hot snare, hot forceps,
  argon plasma, radiofrequency}; `DEVICE_MAY_BE` = {electrocautery: {thermal probe, sphincterotome}}; `_technique_row`
  returns UNRESOLVED instead of INDEPENDENT when `_may_be` holds; `_may_be` reads two supported Device values. Diff
  `J/patches/judge-final2-pairing.diff`.
- *Effect.* No verdict on any batch; note8 45382 gains one cause (F3long). ENABLING (U1's guard) and corrective.
- *G2.* Holds JS06, JS07, JS09, JR05, JR08, JM01, and X12, VR10, VR10b, VR10c, VX07, RS07, RS08, RR06 (45388), APC,
  APC-K. Stays READY: JS08, JR06, X13, K05. Release direction (named, definitional): JS10, JR07, Q09, R10, RE5neg,
  `e5_probe.py` Q1/Q2. No release for a may-be device: JM02.
- *tests.v2.* Failure 5 above: the v1-parity pin is amended to pin v2's table and name the departure.

**3. FX-R1** (harness; `tools/v2/replay_v2.py`; AMENDMENT-2 5.3 step T, D279): unchanged class. Effect: fb10 45330
READY, fb10 45331 and A-v5 45385 EXCLUDED (all correct) on F3all and F2high-p2; A-v5 45385 EXCLUDED on D2medium; none
elsewhere. G2: S09a, S09b, Q10 (the named risk, product behaviour under D261). `tests.v2`: tools only.

**4. FX-SCORE, widened** (scorer; `tools/v2/score_v2.py`, with `engine/measure.py`'s export @2 in the build,
AMENDMENT-2 F9). Class: a READY row whose act anchors overlap no expected act span X still matches X when X overlaps no
event's anchor, at least one event lists a restatement overlapping X whose role is `restates` or `summarizes`, passes
G6's anchored-unit test and whose role claim passed its geometry check, and EVERY event listing such a restatement is
one of the code's acts. Effect: A-v5 45380 wrong_ready -> correct (restatement) on F3all, F2high-p2, D2medium; the
widening changes no recorded row. G2: M1-M6, M7, M7b, M7c, JM7-JM10.

**5. FX-EXP-COMPETE, narrowed** (development expectation; `J/tools/devset_rules.py`). Class: whenever a document's
proposals hold two or more office visit codes whose expected act spans all overlap (one visit), every READY
expectation among them is HELD with `[competing_codes, base_included]` (D40). Effect: B-fb10 99214 READY-expected ->
HELD-expected on F3all and F2high-p2 (one visit); the denominator 17 -> 16. G2: `J/g2/devset-j`.

**6. FX-DEV-MEMBER** (development input; AMENDMENT-2 5.4 step T, D3): unchanged. Effect: fb10 99204/99214 lose
`context_missing` (F3all, F2high-p2); no status change. **Precondition: FX-CAT** (owner question 1) before an acceptance
run enters member values.

Not replay-measurable (each needs a recording under D202 and D277; generic examples, none from a note):

**7. U1** (contract, `contract/claims.py`, FINAL-V2 3.2.2) as section 6 states it, shipped with E5j (not E5).
**8. U2, amended** (instruction: EXTENT) with the doubt route [R:false-ready-FR-12].
**9. U3** (instruction, claim template, G5 guard, design text) with the D244 sharing wording stated [R:design].
**10. U4** and **11. U7** (instruction) as section 6 states them.
**12. U8** (DOUBTS) [R:false-ready-FR-10] and **13. U9** (LESIONS) [R:false-ready-FR-6].

Design items for the build round's design owner (specified, not built):
- **Q2, E2's replacement**: claim an act's `target.anatomy`; place an anastomosis by its appraised entry's subtype and
  joins (FINAL-V2 5.1 rows 11, 51); one compared place for pairing, bundling and E1j; never inside D228/D238's own arm
  without the controls that exist.
- **Q10, group 6**: a lesion place pair control and a lesion-only statement's claimable places, then a ruling on 4.2.
- **Level facts** (an MDM level, minutes) and a level rule: U6's precondition.

Rejected or withdrawn (section 7): E2, E3, E4, U6, the E1 adjacency guard, fixA-fixD.

Owner questions (only the owner can decide; `HOLDS-REFUTATIONS.md` section 5): FX-CAT (a member-entered patient status
holding the other category's visit code, never excluding); D40's two-code hold against the acceptance expectation; E1j's
junction residual against adjacency; and, for the paid test, that what survives refutation measures 8/16 (50%) READY
recall and 8/16 (50%) unnecessary holds on the 10 notes (F3all 89% / 11%; the long notes 0/7), with zero wrong READY and
zero wrong exclusions, so the acceptance bar (70% / 15%) needs U1, U2/U3 and Q2 recorded again.
