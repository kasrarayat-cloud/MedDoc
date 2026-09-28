# Word harness v2.1 on the V1 candidate engine — development set, information only (2026-09-28)

**What this is.** The v2.1 `ticked` check (this directory, unchanged) run on the 40 **development** originals with
the candidate's own detection, instead of the frozen `79a5b2ec6597` detection `info_v21.py` answers. Not a gate,
not the holdout, not native Word, not the app's rendered path. `holdout/` and `qual/` were not opened.

**Driver.** `info_v21.py` copied to scratch with four changes: answer the engine's live `inspect()` output; skip the
frozen-export identity proof (it cannot hold for another engine); register the loaded engine as `word_v3` (the
candidate's `source_policy` imports it by that name); write `dev-results-v21-live.json`. Preserved with both outputs
and logs, hashes in `SHA256SUMS`, at `rebuild/.runtime/v1-full-release-20260928/word-harness-live-20260928/`.

**Positive control.** The same driver on the frozen engine (sha256 `db227329…`) reproduced the published v2.1
figures exactly: live `inspect()` equal to the frozen detection on 40/40, 3,637 fields, and per profile 11 pass /
20 fail / 9 with no ticked questions; 774 / 306 / 52 questions. (The control ran before the one-line module alias
was added; the frozen engine never imports that name.)

**Candidate** `word_v3.py` sha256 `4e2ea03d…` (= `a0bb3a4b`), detection through `inspect()`, i.e. **without** the
rendered layout witness the app uses for column candidates. Ordinary and long profiles are identical.

| | frozen control | candidate |
|---|---:|---:|
| documents pass / fail / no ticked questions | 11 / 20 / 9 | **9 / 22 / 9** |
| questions pass / fail / unverifiable | 774 / 306 / 52 | **768 / 310 / 54** |
| fields proposed | 3,637 | 3,346 |
| fail: no detected field matches | 79 | 224 |
| fail: field refused the label | 218 | 76 |
| fail: read (a box state was wrong) | 9 | 7 |
| fail: whole fill refused (text answer into a protected field) | 0 | 3 |

Every per-document change, with its cause:

- **D11 pass → fail (8 questions):** the printed option is `Positive, Titer:`; both engines name it
  `Positive, Titer`. The frozen engine accepted the ground-truth label through `clean_label`; the candidate's single
  option reader (`c781024d`, F1 HIGH: `clean_label` made `Lt. knee` select `Rt. knee`) accepts only the stored label
  after trimming and case. In the app an answer is chosen from the engine's own options, so this cannot arise there;
  under this harness it is a mapping failure, as declared.
- **D25 pass → fail (A7) and D31 (A1):** the candidate marks a signing area and a guidance-carrying legacy control
  as protected. v1's `answers_for` writes text into every text field, so the base fill is refused and the document's
  questions fail as mapping. In the app such a field cannot be answered.
- **D07 (4 questions):** three have no detected field; A20 is a two-answer question the candidate makes a single
  choice under the structural selection rule (the usefulness loss recorded in `V1-DECISIONS.md`).
- **D28:** 8 questions fail → pass; A11 unverifiable → fail (no field).
- **D03:** 3 questions fail → unverifiable (U+20DD circles outside the glyph table).
- **D10:** fails 118/118 in both. Without the rendered witness the candidate proposes 77 fields to the frozen 226:
  its coded-column candidates wait for layout verification, which this path does not run.

The Word gate (B-W1) is unchanged: this is development-set information on a non-rendered path, and the gate needs
54/60 overall, 18/20 on unseen holdouts and native acceptance, through the app.
