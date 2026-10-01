# QuillMD V1 — implementation and qualification report (2026-10-01)

Private and synthetic throughout. **Not a V1-readiness claim**: real patient data, BAA-covered hosting and the Word
gate remain open. Nothing was deployed; the installed release `dedac162` (Sonnet 4.6, synthetic-only) was not changed
or restarted; model-assisted mapping stays off in every installed profile.

## 1. Candidate, CI, QA build, installed release

| what | state |
|---|---|
| candidate | `v1/release-integration` (draft PR #1291), head `the documentation descendant of `14ed2459` that carries this report`; full CI (six jobs) + secrets-scan green on ``14ed2459` (code identical to this report's commit)` (CI run 36806202297, secrets-scan 36806202211) |
| integrated since `43fcf214` | destination roles (`fix/v1-roles-salvage` 6cd7c1ee), relation floors + question context (`fix/v1-notes-floors` 0e842b0c), single-worker settlement (`fix/v1-settlement-worker` 80932967), retention holds + restore admission (`fix/v1-retention-holds` c7eadf0c), npm advisories (`fix/v1-npm-advisories-20261001`), role-reading reuse (c961850e, 391ff95b), omission hold (f8adebd9, a9a22a93), the L01 browser regression in CI, the CI lane timeout |
| kept unintegrated, pushed | `fix/v1-destination-roles` 4e6b6e8a, `fix/v1-notes-relations` 0bb9fc46, `fix/v1-word-precision` 3b508a21, `fix/v1-mapping-authority` 6ad0451c, `fix/v1-mapping-partial` 48aa5e8d |
| QA build | private copy of the candidate on 127.0.0.1:9140/9141 (loopback; SSH tunnel), QA database, fixture AI, the qualified Word runtime built offline; see §8 |
| installed | `dedac162`, unchanged |

## 2. Tools

DOCX skill, Playwright and pyright-lsp: source, version, scope and one meaningful use each in
`tools-record-20260930.md`. The Playwright reproduction of L01 is now a CI check.

## 3. Word destination authority — before and after

`word-destination-roles-20260930.md` has the design, every round and the residuals. In short:

- **Closed** on the default legacy path: generated text in signing, initials and identity rows (the 17 must-hold
  labels; L01 reproduced on 43fcf214 in the browser, green in CI now). On the model path: additions become review
  items, invalid changes are held individually, dependent changes are held together, order-independent, the request
  is byte-identical; an omitted field or slot is held for review (attempt 24's failure).
- **Declared cost (owner decision, class b)**: about 18 clinical/checklist legacy labels containing 'initial' or
  'signed' are no longer generated (the clinician types them).
- **Open**: 28 pre-existing engine mislabels of signing places (recorded inputs), and the real-form exposure on
  development forms (5 signing areas fillable, 63 fields in consent text) — clinician review remains the backstop.
- v3 note: a date printed on the same line as a signature ('Signature: ____  Date: ____') is treated as an ordinary
  neighbouring answer (positive control PC02) and is filled from a 'Date:' note line.

## 4. Ordinary notes — before and after (freeze / cases.json)

| path | correct | incorrect | unjustifiably held | appropriately held | missing |
|---|---|---|---|---|---|
| default request, 14 retained responses (43fcf214 = integrated) | 7 / 7 | 0 / 0 | 31 / 29 | 15 / 17 | 23 / 23 |
| field relations with reference relations (43fcf214 = integrated) | 23 / 23 | 0 / 0 | 15 / 13 | 17 / 19 | 21 / 21 |

Relations-path exposure with a model calling every other line independent: adverse rows adopted 18 → **2** of 57,
with variants 204 → **26** of 369, frozen leaks 8 → **0**. The usefulness gain requires turning the field-relations
contract on for Sonnet 5, which needs live qualification (a new allowance), a production switch and large-form
handling (`ordinary-notes-floors-20260930.md`). **Usefulness in the default configuration is unchanged; this objective
is not complete.** The subject/time releases that raised the reference score to 32 of 38 were refuted three times
(wrong person, time and side) and are not integrated.

## 5. Affected workflows

- **N13** (retained attempt 020): the response that failed the campaign now adopts with both contradictions held;
  the clinician resolved both, the note finalized, the authenticated DOCX export returned 200 and read back with only
  the two answer paragraphs changed. The historical failure record is untouched (420 evidence/ledger files, same
  sha256 before and after).
- **Six-case matrix** (attempts 18–23, integrated code = 43fcf214): 3 correct, 8 held-correct, 1 over-held (N03
  'Clinic attendance', as in the campaign), 0 unsafe; exports byte-identical to the campaign's for 018/019/021–023.
- **Word walks** (39 per commit, offline, both engines; `int/word-walks`): the only behavioural difference from
  43fcf214 is that the legacy engine no longer writes the notes' 'Patient signature' value into the signature cell.
  Every other export is byte-identical. All 46 exports pass the DOCX validator. Found on both commits (recorded, not
  fixed here): the legacy engine refuses forms with content controls/fields (S1, S2, D10, D30, D31); legacy fill writes
  an empty run into unanswered cells (no visible text); D10 without the layout witness is generated and charged and
  only refused at finalization; D30's 12-fact ordinary case still holds 7 of 12; fixture generation holds every answer
  when a note has an unlabelled line; LibreOffice pagination grows (S3 2 → 3 pages, the signing block split).
  LibreOffice is not native Word.
- **Browser** (CI and QA): browser-tests 15/15, word-authority 11/11 (and the typed-signature control fails as it
  must), WM walk 9/9 with the Word runtime built offline, input workflow 8/8.

## 6. Word qualification

`word-qualification-status-20260930.md`: development strict detection 3 of 33; no unseen cohort opened (N20 capped at
17/20 by `.doc`, overlapping reserved Q20); the census of misses (K1–K15); the precision attempt refuted and kept
unintegrated. Native Word acceptance and an independently authored corpus remain external.

## 7. Paid requests and billing

One authority (`quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk`), no new allowance, no fund transfer, no
renamed stage, no relaxed stop rule (`sonnet5-campaign/stage-accounting-20260930.md`).

| stage | attempts | exposure | remaining | state |
|---|---|---|---|---|
| model_check | 1 | $0.002860 | $4.997140 | passed |
| mapping | 2 | $0.028616 | $24.971384 | failed-2 (attempt 24 refused for an incomplete slot partition; repaired; not reopened — the runner's repair check does not watch the mapping modules) |
| ordinary_notes | 21 | $0.099404 | $9.900596 | failed-3 (no declared send left) |
| **total** | **24** | **$0.130880** | **$39.869120** | 0 open |

Calculated costs; provider billing evidence is not available here (Messages key; usage reports need an Admin key).
**Prepared, not sent (needs the owner):** the smallest notes batch — the 14 retained default cases once on the
field-relations contract (about $0.08 actual at measured rates); a mapping runner whose watched files include the
mapping modules, if a mapping measurement is still wanted.

## 8. Demo

Isolated QA environment on the candidate (§1), reached by `ssh -N -L 9140:127.0.0.1:9140 -L 9141:127.0.0.1:9141`.
Fictional form and notes (typed notes, a missing answer, a contradiction, a signature line that must not land, a
clinician correction, a faithful export, another account refused). Rehearsed end to end: twice on `14ed2459` with a clean demo database, 19/19 checks each (including the on-page reason for a held signing row); the CI browser harnesses passed against a separate throwaway QA database (browser-tests 15/15, word-authority 11/11, WM 9/9). Every answer is
labelled FIXTURE (labelled-line extraction, $0); no replay or live model runs in the served app. Presenter script,
account instructions (no secrets), identities, screenshots, exports and renders:
`rebuild/.runtime/v1-product-20260930/demo/`.

## 9. Other blockers advanced

- **Settlement**: one worker per database (advisory lock, proven with real processes), no settlement of a job that left
  running, late receipts held for an administrator, timeouts refused, operator texts corrected (contract count 92).
- **Retention**: holds journaled (hold before its commit, release after), replayed into a quarantined restore,
  append-only restore admission that re-checks the journal. No retention period introduced.
- **CI**: npm advisories fixed (lockfile only); the Python lanes' timeout raised to 30 minutes after core-1 outgrew 20.

## 10. Remaining blockers

**Engineering**
1. Ordinary-notes usefulness (B-G1): enable and qualify the field-relations contract for Sonnet 5 (production switch,
   large-form batches), then decide the remaining over-holds (default path 31 of 38 withheld).
2. Word engine mislabels of signing places on real forms (28 recorded shapes; 5 signing areas and 63 consent-text
   fields on development forms) — a hold-only review-flag design with its own refutation.
3. Word qualification (B-W1): development strict 3 of 33; `.doc` support; legacy engine refusing content controls
   while v3 stays flag-gated; D10 charged before a refusal at finalization; D30's ordinary holds.
4. Retention: disposal of clinical content, redaction tombstones, backup reconciliation (also need counsel's schedule).
5. Mapping measurement path: the runner's watched files omit the mapping modules.
6. LOW residuals recorded per stream (settlement in-place adjustment of an earlier window; retention NEW-1; notes cost
   2.2× on one long shape; mapping MG/MF test gaps).

**External / owner**
- Owner decisions: the legacy usefulness cost (§3); a notes qualification allowance (§7); whether model-assisted
  mapping is still wanted; billing policy for an empty model classification is now "not charged" (restored).
- BAA-covered hosting and the AWS/Anthropic/Deepgram/backup BAAs; email vendor; live Stripe; native Word acceptance;
  independent penetration test; counsel's retention schedule; an independently authored Word corpus; two-custodian key
  custody and journal custodians; outside heartbeat; provider billing evidence (Admin key or console).

## 11. Evidence

Outside scratch, under `rebuild/.runtime/v1-product-20260930/` (synthetic only): `c/browser` (L01 reproduction),
`c/word-census`, `b/` and `b2/` (every implementation, refutation, repair and verification), `b3/` (settlement,
retention), `int/` (integrated qualification: browser, notes replays, Word walks, cross-stream refutation, cache and
wire refutations, attempt-24 replay), `demo/`. The campaign ledger, evidence and transcripts are under
`rebuild/.runtime/v1-sonnet5-campaign/`. `evidence-manifest-20261001.json` beside this report lists each directory's
file count, size and listing digest, and every export, render and result file with its sha256 (no contents).

## Correction, 2026-10-01 (later the same day)

§5 first said the six-case matrix was "3 correct, 9 held-correct, 1 over-held", which totals 13 although the six
cases have 12 fields. The per-field table behind it (`rebuild/.runtime/v1-product-20260930/int/notes-replay/out/six-matrix.txt`)
has 8 held-correct fields: N13 v3_1/v3_2, N14 v3_1/v3_2, N15 v3_1/v3_2, N16 v3_1/v3_2. The categories are mutually
exclusive and the denominator is 12 fields in 6 cases: correct 3 (N03 v3_1, N10 v3_1, N10 v3_2), held-correct 8,
over-held 1 (N03 v3_2), unsafe 0. The 9 was an addition error in the replay summary that this report copied; the line
above is corrected in place and this note records it. N13's original failed attempt 020 and its repaired replay remain
distinct evidence (the campaign record of attempt 020 is unchanged).

