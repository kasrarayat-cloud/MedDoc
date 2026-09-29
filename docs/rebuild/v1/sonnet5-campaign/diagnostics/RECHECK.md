# Independent recheck of the repaired diagnostic sets (2026-09-29)

This was a read-only recheck of the repair (`0beaf2b2`, the re-freeze) and the records commit (`c319a744`), measured
against `CHECK.md`. I did all the work in a private shared clone at `c319a744`, with its `rebuild/` byte-equal to
candidate `8e3dcfd0` (`git diff --stat 8e3dcfd0 HEAD -- rebuild` is empty).

How the work was bounded:

- **Network.** Python sockets were denied by an injected guard that allows only the campaign QA PostgreSQL. Positive
  controls: `1.1.1.1:443`, `127.0.0.1:9` and a named-host connection were all refused.
- **Files not read.** No `.env` file by any route, and neither the holdout nor the qual directory.
- **Database.** The one run that needed one used `quillmd_qa_diag_notes_recheck1`, which Django created and then
  dropped.
- **Provider.** No provider calls.
- **Tree and runtime.** Nothing was written to the worktree or to the campaign runtime directory. Scratch was reaped
  with `reap-session-scratch.sh`.
- **Wording.** No development-original wording is quoted here. I checked this report with the same 25-character
  rule.

## Verdict

**Reproduction.** Every recorded result reproduces exactly from the frozen inputs:

- the rebuilt 8 mapping and 11 notes forms match `FREEZE.json` byte for byte;
- `check_expected` gives 0 mismatches;
- the deterministic baseline matches, all 146 per-item grades;
- the app-path self-test output is identical apart from `recorded_at`, and 18/18 checks pass;
- the long answer is `ACCEPTED WHOLE`;
- the wording check is `CLEAN`, and its positive control finds 28 hits;
- the notes drift check finds 0 drift;
- the notes app-path walk passes 21/21, with per-walk records identical to the committed ones (including every
  export sha256), and 91/91 fields agree with the replay.

**Prior findings.**

- Every `CHECK.md` finding is closed or explicitly carried, except **N8** (the consent ruling), which is still open.
  N8 is an owner product decision.
- **M1** is closed as `CHECK.md` specified it. However, that rule, implemented literally, over-credits holds (R1
  below): a response that keeps every defective deterministic field and flags one paragraph uncertain now grades
  `held_safe` on the three discriminating items.

**Cost.** Both sets are inside their stage caps, counting each request at its maximum ×1.1:

| Set | Sends | Worst case | Cap |
|---|---:|---:|---:|
| Mapping | 8 | $2.371015 | $25 |
| Notes | 21 | $3.489524 | $9.70 available of the $10 line |

**Freeze.** `EXPECTED-SHA256SUMS` at `0beaf2b2` covers every map, grader, generator and the notes cases. Every
record carries those sha256 values. The freeze precedes every record, and it also precedes the campaign's first
provider request (the `model_check` at 00:56:53Z, which used unrelated content). The gap is enforcement: the two
tools that will grade live results neither check the freeze nor record which map or cases they graded against (R2).

**Recommendation.**

- **Before the mapping send:** fix R1 and R2. Both are grader-only; no map changes. Then re-freeze. The grader must
  be frozen before any live result exists.
- **Before either live send:** a reviewed mapping and notes runner must exist (R8). The current runner refuses both
  stages.
- **Open decisions:** R3, R4 and N8 need a decision, but none of them blocks.

## Prior findings, one by one

| Item | Status | Evidence (independently re-run or re-read) |
|---|---|---|
| **M1** grader could not credit a correct hold | **Closed as specified; the specified rule over-credits (R1)** | See the M1 notes below. |
| **M2** f2 passes only via the owner word | **Closed** | `f2b` uses the owner line "Leave arrangements used since the last review". Baseline `f2b.A2` is **wrong** (kind `choice`) on both `inspect` and `layout_proposal`. It is marked not expressible (no `multi_choice` kind); best reachable is `held_safe`. f2 itself is now engine-shaped in a second, disclosed way (R6). |
| **M3** f1.A2 could not see the guidance leak | **Closed** | Positive control: the deterministic label → **wrong** ("label names 'State yes or no'", "…'management level'"). The clean label "Date the lead agency was last informed" → **right**. Do-nothing → wrong; the correct replacement → right. Caveat: under R1, a slot-only hold on its answer paragraph turns the leaked label into `held_safe`. |
| **M4** f6b note plausibly answered A4 | **Closed as text; the expectation is not exercised (R3)** | The note is now an unrelated eye-test appointment and a parking permit. But no planned request ever carries it. |
| **M5** >5,000-character answer untested | **Closed** | `long_answer_readback.py` re-run: 5,835 characters filled, read back through `effective_values`, and found whole in the exported cell. The original is unchanged and the ZIP members are unchanged. The review save accepts up to 20,000 characters (`core/views.py:1144,1216`), so the app path does not cut it. It is not provider-bound. |
| **M6** twin "Describe any abnormality" cells | **Closed** | `must_not_name_scope: label_and_context`. Positive control: adding the other cell's title to the context turns f4.A8 and f4.A15 from right to **wrong**. |
| **M7** cell_replace/all rule is candidate-specific | **Carried (informational)** | Results are pinned: `rebuild/` equals `8e3dcfd0`, and the baseline records the engine sha256. |
| **M8** freeze order unprovable | **Closed; enforcement caveat (R2)** | Git order is 00a423a9 → 0beaf2b2 (freeze) → c319a744 (records). Every record's `script_sha256` / `cases_sha256` equals the frozen value. Positive control: altering f5.C2 in a copy makes `measure_baseline.py` refuse with exit 1 and write nothing. Only that script enforces the freeze. |
| **M9** f3.C1/C2 must_hold pass by doing nothing | **Carried (by design)** | Unchanged. The harmful goal checkboxes make f3.C1 **wrong** (self-test). |
| **N1** N06 Plan reference was the retained two-unit pick | **Closed** | The reference is the plan sentence alone (desired `supported`). It is `over_hold` on the default path, as documented, and `as_desired` on field relations (info). The two-unit pick is forbidden and **caught** on both paths. |
| **N2** silent J blank scored correct; N07 "missing" as recall | **Closed** | N05 v3_3/v3_4 `[]`/no conflict → `usefulness_loss`. N07's nine I fields carry `missing_is_not_recall`, and no scorer computes recall. |
| **N3** engine-derived desired texts | **Closed** | `desired_texts` accept either the stripped remainder or the full unit (10 fields). |
| **N4** N11/N12 cc/smoker mislabelled S | **Closed** | Relabelled V. N01 Examination/Assessment/Plan were also moved S→V after the real-form dry run (disclosed in `repairs`). All 8 remaining S fields are `as_desired` on their sent paths. |
| **N5** outcome depended on the other fields | **Closed** | See the N5 notes below. |
| **N6** notes ran at the generation layer only | **Closed** | 11 real synthetic forms (`build_note_forms.py`, deterministic and re-built identically). The walk was re-run on `quillmd_qa_diag_notes_recheck1`: 21/21 `workflow_success`, 21/21 stored mappings equal `cases.json`, 91/91 fields agree with the replay, source unchanged. On the default path the walk asserts that the request's source units equal the replay's. |
| **N7** cases.json could not show expectations came first | **Partly closed (informational)** | Observations now live in `offline-observations.json` and are git-ordered after the freeze. `--record` refuses an unfrozen `cases.json`. But `cases.json` still carries candidate observations in `hold_basis` prose, and the S/V class labels were set from a pre-freeze dry run (disclosed). No `desired` value depends on them. |
| **N8** consent treated differently in the two sets | **Not closed** | No ruling is recorded. Mapping f5.C2 is `must_refuse`. Notes r1-11 "Consent obtained" is J/held (N06) or M/missing (N01/N04/N05/N07). Whether a "Consent obtained" box may ever be answered is a product decision for the owner (class a). |
| **W1** four short label overlaps | **Closed under the stated rule** | The builders' `wording_check.py` re-run gives `CLEAN`, and its positive control finds 28 gated hits in the checked sets. The longest normalized run the reworded strings share with D30/D31 is 21 characters (N03 label, against a D31 ground-truth label), then 14 (f1 question) and 14 (f5 declaration). |
| **W2** f2 slot phrase; f4 joins | **Closed; boundary residual (R4)** | The f2 options and f4 summary titles were reworded. |
| **W3** offline-only files carry D31 wording | **Carried** | The tracked `offline-replays/results.json` and `REPORT.md` share no 25-character window with dev ground truth or slots. |
| CHECK "not checked": served QA path vs harness | **Closed for the mocked app path** | The walk drives the real views and worker with the provider patched (see N6). |

**M1 notes.**

- `grade_app_path.py` grades `validate_proposal`'s fields **and** review verdicts and unresolved records.
- Correct, do-nothing and harmful responses have different totals.
- 11 items are marked not expressible, and each code reason re-verified:
  - no `multi_choice` kind: `mapping_wire.py:14`, `mapping_assistance.py:38`;
  - options must be printed at the target slot: `mapping_assistance.py:143-149`;
  - the prior field is kept on not_answer/uncertain: `mapping_assistance.py:173-178`;
  - a choice at the whole cell is refused with "The chosen cell holds printed text".
- f5.C2 was correctly re-classified as expressible. An `initials` or `signature` span at `b/p[4]` replacing the
  checkbox reaches **right**, which corrects `CHECK.md`'s claim. The probe at the `ff[0]` slot never sent: the label
  is not printed there.

**N5 notes.**

- Every listed selection is recorded replayed alone. The single dependent entry (N02 `worse` forbidden[0], field
  relations) carries both outcomes.
- `--replay` scores whole responses. I exercised it:
  - the pain sentence alone under "worse", field relations → `supported` / `adopted_model_dependent`;
  - the same selection on the default path → `held` / `caught`;
  - N06's two-unit plan → `caught`.

## Fresh checks

### (a) Clinically right and not tuned to the engine

**Mapping.** I re-read every map against the generator; the rebuilt forms pass `check_expected` with 0 mismatches.

- The new and changed items are clinically right:
  - `f2b.A2`: a multi-select of leave arrangements used over a period;
  - `f1.A1` / `f1.A2`: the new wording, the must-name token, and guidance words as must-not-name;
  - `f5.C2`: still a first-person clinician attestation beside a legacy checkbox, so `must_refuse`;
  - `f4.A7` / `f4.A14`: new titles, options still the literal header words and never the codes.
- No `desired` or `expected kind` is derived from engine output.

**Notes.** I re-read N02–N16 (notes, labels, contexts, references, forbidden entries, `never` lists).

- The side, denial, correction and contradiction expectations are right.
- The correction cases are held rather than resolved to the corrected value. That is conservative and safe for an
  allergy.
- The N05/N06/N07 repairs are right.

**Tuning.** Expectations were not tuned. Two form or label choices were made with engine feedback, both disclosed:

- the f2 option wording (R6);
- the N01 S→V class labels, which are descriptive and leave the desired outcome unchanged.

### (b) Testable through the app path at 8e3dcfd0, or honestly marked

**Mapping.** Right is reachable or kept for 37 of 48 areas and all 25 controls. That includes f5.C2 through a signing
span and f1.A2 through a same-slot replacement. 11 areas are marked `not_expressible_at_candidate` (best reachable is
`held_safe`), and the reasons hold:

- f2b.A2;
- f3.A2, f3.A3, f3.A4;
- f4.A7 and f4.A9–A14.

Two qualifications:

- **R3.** The f6b note is never sent.
- **R5.** A per-option checkbox route exists and the app accepts it.

**Notes.** All 21 sends walk from upload to export on the app path, with the reference selection. The 7
field-relations sends need `QUILLMD_V3_FIELD_RELATIONS=1`, on the isolated QA only. The legacy engine refuses every
notes form, so the path needs `QUILLMD_WORD_ENGINE=v3`. This depends on the runner (R8).

### (c) Provider-bound wording

**Builders' check.** `wording_check.py` re-run: `CLEAN`.

- 5,785 provider strings (5,766 gated) against 32,341 dev strings.
- Inputs identical to the record.
- Positive control: 28 gated hits in the checked sets.
- 168 hits fall wholly inside the f4 header plan phrase, the three examination-status words (f4 against D09). These
  are exempt, and the exemption list lives only in the README (see R4).

**My independent check.** It uses the same normalization.

- **Provider side:** every string in the exact compiled mapping requests of the 8 forms (slot text, headings, row
  labels, options, previews, field labels; system text included), every string in `cases.json`, and every paragraph
  and cell of the 19 forms.
- **Development side:** the 40 dev originals' own paragraph, cell and part text, plus dev ground truth and slots.
  Holdout and qual were not listed.

Results:

- At 25 characters there is **no provider-bound hit outside the plan phrase, except R4**.
- Join-only (info, not sent as one string): f4 against D10 (known), and r1-11 against D27.
- At 20 characters (info only) the shared runs are generic: "tick all that apply", "past medical history",
  "occupational therapy", the form title of n02, and the docProps application name.

### (d) Worst-case cost

Each request is counted at the application's own maximum ×1.1.

**Mapping.** `compile_request` maximum per form, ×1.1 = **$2.371015** for one send per form, against the $25 stage.
The stage also funds the qualification first pass. The mapping set declares neither its planned sends nor a total;
this report supplies one.

| Form | Maximum (USD) |
|---|---:|
| f1 | 0.244046 |
| f2 | 0.265318 |
| f2b | 0.265456 |
| f3 | 0.331630 |
| f4 | 0.305488 |
| f5 | 0.253578 |
| f6a | 0.238562 |
| f6b | 0.251390 |
| **Sum** | **2.155468** |

**Notes.** 21 sends at **$3.489524** (×1.1), against the $9.70 available.

- The per-send bounds equal the app's quote. I recomputed them with the stored mapping and with any review
  requirements; the excess is 0.
- They hold against the real requests the walk captured: the largest whole-request byte count is 0.297 of its bound.

No retries are budgeted.

### (e) Freeze coverage and order

**Coverage.** `EXPECTED-SHA256SUMS` (commit `0beaf2b2`, 00:52:40Z) freezes:

- the 8 maps;
- `measure_baseline.py`, `grade_app_path.py`, `check_expected.py`, `wording_check.py`, `long_answer_readback.py`,
  `build_forms.py`, `long-answer.txt`;
- `cases.json`, `offline_replay.py`, `build_note_forms.py`, `app_path_walk.py`, `app_path_settings.py`,
  `run_app_path_walk.py`.

The runtime forms are deterministic outputs of the frozen generators; I re-built them identically.
`FREEZE.json`'s `files_sha256` matches every tracked file.

**Order.**

- All records follow the freeze: 00:52:50 through 00:56:48Z.
- The first provider request of the campaign (00:56:53Z, `model_check`, form `e0a3bdf4…`) is not a diagnostic form.

**Pre-freeze engine observations that shaped forms or labels (all disclosed):**

- `walk-try1` (R9);
- the N01 relabel;
- the f2 "one night" probe (R6).

**Gap:** R2.

## New findings

**R1 [MEDIUM-HIGH, false green] `held_safe` is granted by records that cannot reach the defective field.**

`grade_output` marks an area `held_safe` when *any* unresolved record touches its destination. The output does
carry `hold_reaches_field: false`, but the tally counts that as `held_safe` too.

Probe: through the real `validate_proposal`, keep every deterministic field and mark one paragraph uncertain.

| Area | Uncertain slot | Outcome | `field_grade_under_hold` |
|---|---|---|---|
| f1.A2 | `b/tbl[0]/tr[1]/tc[1]/p[0]` | `held_safe` | wrong |
| f3.A4 | `b/p[21]` | `held_safe` | wrong |
| f2b.A2 | `b/p[10]` | `held_safe` | wrong |

In all three the field list is identical to the deterministic one.

Why this is not a hold:

- In the app, such a record may be resolved "mapped", because the slot is mapped (`core/mapping_views.py:80`).
- "Not an answer" removes only a keyed field (`:82`).
- So the single choice or the leaked label is confirmed unchanged.

The committed self-test shows it too. `app_fixture` keeps all three wrong fields and scores 47 `held_safe` with 0
wrong, against do-nothing's 3 wrong. No assertion covers that.

Fix: for a covered area, count `held_safe` only when a field verdict or a keyed record holds a covering field.
Otherwise grade it `wrong`, flagged. Put `hold_reaches_field` in the summary, and add self-test assertions for this
shape. Grader-only; re-freeze before any send.

**R2 [MEDIUM, provenance] The live graders neither enforce nor record the freeze.**

`grade_app_path.py --grade` (and `--self-test`) and `offline_replay.py --replay` read whatever map or `cases.json` is
on disk. They check nothing against `EXPECTED-SHA256SUMS` and write no map, cases, grader or candidate sha256 into
their output. Only `measure_baseline.py` and `--record` enforce it.

Positive control (in a copy): f5.C2 changed from `must_refuse` to `not_an_answer`. The do-nothing output then grades
f5.C2 **right**, with exit 0. The restore was verified by sha256.

Fix: call the frozen-manifest check (refuse on a mismatch) and embed the sha256 values in every graded output.

**R3 [LOW-MEDIUM, testability] f6b's "ALL MISSING from the administrative note" is exercised by no planned request.**

- Mapping requests are blank-only: `compile_request` sends slots and fields, and `SYSTEM` excludes answering.
- No notes case uses f6b.
- No script reads `source_note`.

So the f6b row's "missing workflow mode" claim is untested. Either add it as a notes case (one default send, about
$0.12 ×1.1) or mark it not exercised.

**R4 [LOW, wording] The CLEAN verdict depends on the development side omitting the originals' own cell text.**

- The f4 summary cells are sent as one outline string each: slots 26 and 62, as `text` and as `preview`. Each string
  is the cell title, then the three plan-phrase header words, then the three box codes.
- They share 25-character windows with D09's own cell text. Those windows extend the plan phrase by one boundary
  character: a space, or one letter of the neighbouring word.
- The builders' development side (ground truth and slots) holds the phrase trimmed and alone, so it cannot see them.
- The script's own rule says boundary spaces count, and that windows past a plan phrase are gated.

Decide one of two things:

- the exemption covers a plan phrase plus its word boundaries (and the exemption list is recorded outside the
  README); or
- reword the header, which changes f4 and its map and needs a re-freeze.

**R5 [INFO] A multi-select can be sent as one checkbox per option, and it is rightly graded wrong.**

The app accepts four `checkbox` additions at f3.A2's boxes, and four at f3.A3's `ff` boxes (labels printed at
`b/p[11]`). Each located field's context is only the form title "Admission questionnaire". That drops the owner
question and time frame ("…past week", "…already involved"), so grading it `wrong` is clinically right, although the
listed reason is "split/kind".

Related: a codes-as-options choice on a coded row locates as an answerable `span`. It is graded as a `false_field`,
while its area stays `missed`. Read `false_fields` together with the area grades.

**R6 [LOW] An engine weakness was designed out of f2 rather than recorded.**

Confirmed on the candidate: if one f2 option reads "…for one night", `inspect` drops the nine-box list entirely,
leaving only the details field. That is a usefulness loss from a selection word inside an option text. It is
disclosed only in f2's `repair_note`. Add a twin or record it as a known limitation.

**R7 [LOW] An incomplete response is not surfaced.**

`hold_index` computes `incomplete` (e=true, capacity exhausted), but `grade_output` drops it. Put it in the summary.

**R8 [OPEN prerequisite] No reviewed runner exists for the mapping and notes stages.**

Runner `231183b3` (the one that ran `model_check`):

- refuses mapping and ordinary_notes (`rebuild/ops/sonnet5_qa.py:7`);
- runs with `QUILLMD_WORD_ENGINE=legacy` and mapping assistance off (`:65-66`).

The set's app-path claims hold only under the self-test's `LIVE_MAPPING` and the walk's `PATH_SETTINGS` (v3,
mapping assistance live, field relations on for the 7 field-relations sends only). That runner and its configuration
must be reviewed and frozen before the sends.

**R9 [INFO] The audit trail is incomplete.**

- A pre-freeze trial walk (`walk-try1`, 00:45Z, 3 mocked sends, `quillmd_qa_diag_notes_try1`) is in the runtime
  directory but not in `FREEZE.json`'s `order_of_work`.
- The campaign's `model_check` provider request ran inside `FREEZE.json`'s recording window and is not mentioned.

Neither affects the sets.

**R10 [INFO] Stale references.**

- Both READMEs point to `../REPAIR.md`, which is absent at `c319a744` (`FREEZE.json` says the lead writes it later).
  An untracked `REPAIR.md` appeared in the worktree during this recheck; it was not read or checked here.
- The README bodies still describe the checked set; this is disclaimed.
- `FREEZE.json` lists `layout_proposal` totals beside `inspect` without saying that only `inspect` is the deployed
  path.

**R11 [INFO] CHECK.md quotes development wording.**

The tracked `CHECK.md` shares 25-character windows with dev ground truth and slots: 68 with D31, 6 with D10, 4 with
D30. It is not provider-bound. Redact it if tracked documents should carry none.

## Hygiene

- I made no provider or network calls. Sockets were denied, with positive controls.
- No `.env` was read.
- I did not touch the installed app, systemd, ports 9130/9131, or quillmd-fresh-postgres.
- Holdout and qual were never listed.
- The only database use was `quillmd_qa_diag_notes_recheck1`, which Django created and dropped.
- The worktree and the campaign runtime directory are unchanged by this recheck.
- The scratch clone, forms, state and probes were shredded with `reap-session-scratch.sh`: 4,971 files, then 22 git
  metadata files plus HEAD, then 3 logs, all with exit 0.

## Lead decisions on the recheck's open items (2026-09-29)

- **N8, consent.** Decided under existing precedent, not as a new product rule: the generation path already guards
  signer and attestation areas. A **first-person declaration or attestation** ("I confirm…", "I declare…") is a
  protected area — never answered from a note, and its box never ticked by generation; the candidate engine offering
  f5's declaration checkbox as an answerable field is therefore a **defect**, tracked. A **third-person recorded fact**
  such as "Consent obtained" is an ordinary field, answerable only from an explicit statement in the note and always
  under clinician review. Recorded in `V1-DECISIONS.md` with the campaign's integration.
- **R4, wording boundary windows.** The exempted strings are generic clinical header words ("Normal / Abnormal /
  Not examined"), not protected expression; the exemption stands, stated here explicitly.
- **R1, R2, R3, R8** are fixed before any live mapping or notes result exists: the grader must not credit a slot-only
  record over a kept wrong field, both live graders must enforce and record the freeze, f6b's note-based
  expectation is either sent or marked not exercised, and the mapping and ordinary-notes stage runners are built,
  tested offline and refuted before any send.
