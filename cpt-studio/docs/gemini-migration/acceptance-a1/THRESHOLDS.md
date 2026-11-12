# Acceptance set a1: what is measured and what passes (fixed 2026-11-12, BEFORE any case exists or any measurement)

Owner directive 2026-11-12 (docs/foundation/rulings/2026-10-23-cpt-studio-gi.md): "Measure both wrong READY results and
unnecessary holds. An all-held result cannot pass." These thresholds are the integration owner's, fixed before the cases are
authored or any run is made, and committed with the set's hashes. They change only with a dated, recorded reason. They never
change because a measurement came in.

## Units
- A **code row** is one proposed code on one document in one run.
- Each a1 case states the expected outcome per proposed code: READY (with the act it stands on), HELD (with the one fact to
  resolve), or EXCLUDED. It also lists any acts a reviewer must see.
- Every document runs through the new path with a FRESH Gemini call (labelled fresh). Independent documents and g1 run three
  times; the rest run once.

## Classes (per code row)
- **WRONG READY**: expected HELD or EXCLUDED, actual READY. Also READY on an act other than the expected one, or on wrong facts.
- **WRONG EXCLUSION**: expected READY or HELD, actual EXCLUDED.
- **DROPPED QUESTION**: expected HELD with a question topic, actual HELD with no question on that topic, judged by an
  independent evaluator who reads the question text.
- **UNNECESSARY HOLD**: expected READY, actual HELD.
- **CORRECT**: the outcome matches; a HELD also asks its topic.

## Pass conditions (all must hold)
1. WRONG READY: **0** in every run, on every kind (regression, paraphrase, variant, independent, g1).
2. WRONG EXCLUSION: **0** in every run.
3. DROPPED QUESTION: **0** in every run.
4. UNNECESSARY HOLD:
   - at most **15%** of the READY-expected code rows on the independent documents and g1 together;
   - at most **25%** on the regression, paraphrase and variant cases together;
   - never more than the installed release's own rate (c2e53f8e on the same documents, the same proposals and dates) on any
     kind.
5. NOT ALL-HELD: on every kind, at least **70%** of the READY-expected code rows are READY. (A system that holds everything
   fails here and in 4.)
6. STABILITY: across the three runs of a repeated document, the outcome class of each code row is the same in at least
   **95%** of rows. A row that is WRONG READY in any run fails condition 1, whatever the others give.
7. CONFIDENTIALITY: no provider or model name in any customer-facing text the runs produce (reasons, questions, reports).

## Reporting
Every run reports, per kind and overall:
- the counts of each class, with every WRONG READY, WRONG EXCLUSION, DROPPED QUESTION and UNNECESSARY HOLD listed by case and
  code;
- the installed release's counts on the same rows;
- the Gemini usage (requests, tokens, cost) of the fresh calls.
A failed condition is reported as failed. It is never re-run until it passes without a recorded change to the engine or the
prompt.

## Amendment 1, 2026-11-12: one class gap, label quality, label disputes
Written after the cases were authored and sealed as v1 (2026-11-12T03:42:10Z). It comes before any measurement and before any
prompt change. The integration owner has read no case; this amendment is written from counts and hashes alone. Nothing above it
changes.

### The one unclassified cell
Expected EXCLUDED with actual HELD falls in none of the classes above. It is **SAFE MISMATCH**: counted and listed in every
report, and no pass condition. Every other mismatch is already one of WRONG READY, WRONG EXCLUSION, DROPPED QUESTION or
UNNECESSARY HOLD.

### Why label quality needs more than v1's check
The WRONG READY, WRONG EXCLUSION and DROPPED QUESTION conditions are zero-tolerance, so one wrong label decides a run, in either
direction:
- A label that says READY where the document leaves a required fact open scores a false READY as CORRECT. That is the failure
  this migration exists to stop.
- A label that says HELD or EXCLUDED where the document supports READY scores a right answer as a WRONG READY.

The v1 checker read the author's answers before judging them, and agreed on 209 of 216 cases. A checker that reads the answer
tends to confirm it, so that agreement is not evidence of label quality.

### 1. Blind re-derivation, before the set is used
- **Re-derive.** A coder who did not author or check the set derives every code row from the document and the proposals alone:
  - the outcome;
  - the act a READY stands on;
  - the topic a HELD asks.

  The coder never sees the author's outcomes, rationale, notes, listed acts or sources, the checker's verdicts, or the case's
  kind.
- **Compare.** A script compares the two answers row by row and flags a row when:
  - the outcomes differ; or
  - both say READY and the act quotes do not overlap; or
  - both say HELD and the topics name different facts.
- **Adjudicate.** An adjudicator decides each flagged row. The adjudicator is not the author, the checker, the re-deriver or the
  builder, and decides under ADJUDICATION.md. They read the document and the two answers, labelled only A and B, in an order
  that does not say which is the label. They may find both answers wrong.
- **Record and keep pairs consistent.**
  - A changed label is recorded with its case, code, old and new answer, and the reason.
  - A regression case and its paraphrase must still agree, and its variant must still change the outcome. A pair that no longer
    does is adjudicated again with both documents.
- **Seal v2.** The set is sealed as v2, and v2's hashes are committed before any prompt change. v2 is the set measured.

### 2. Disputes after a measurement
- When a run produces WRONG READY, WRONG EXCLUSION, DROPPED QUESTION or UNNECESSARY HOLD rows, EVERY one of them is adjudicated
  as in 1, never a chosen subset.
- The adjudicator has not authored, checked, re-derived or built.
- A label changes only when the adjudicator finds the document supports the other outcome.
- The run is reported with both the original and the corrected score, and every changed label is listed.

### 3. The builder stays blind
- For a confirmed failure, the builder receives:
  - the case id and the code;
  - the expected and actual classes;
  - a description of the failure class that quotes nothing from the document.
- A fix is shown on cases the builder writes, never on a1 cases.
- If the builder reads an a1 case for any reason, that case is burned:
  - the reading is recorded;
  - the case is removed from the measured set;
  - before the next measurement, it is replaced by a freshly authored case of the same family and kind.

### 4. Too many changes reopen a kind
If more than 5% of any kind's rows change label after v2 is sealed, that kind is re-derived in full before it is used again.
