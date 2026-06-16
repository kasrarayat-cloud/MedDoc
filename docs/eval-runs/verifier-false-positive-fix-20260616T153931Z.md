# Anchored verifier — false-positive fix (verification report)

**Branch:** `fix/verifier-false-positives` · **Date:** 2026-06-16 · **Prod:** untouched (flag `TRANSCRIBE_MD_EVIDENCE_ANCHORS` stays OFF)

## What changed

Two SAFE, mechanical false positives in the anchored verifier's DETERMINISTIC stage
(`apps/transcribe-md/src/worker/layers/04b-anchor-verify.ts`) that were demoting
correctly-dictated content to the suggestions lane:

- **FIX 1 — content-token anchor floor (~L283).** The `≥3 alphanumeric-token` pre-filter
  demoted genuine SHORT anchors that are verbatim in the transcript. Replaced with a
  content-token check (new `ANCHOR_STOPWORDS` set): reject ONLY an all-stopword/all-particle
  (or empty) span. The verbatim substring check on the next line is **byte-unchanged**, so a
  2-content-token anchor still cannot smuggle a quote that isn't literally in the transcript.
- **FIX 2 — `isExemptLine` scope (~L221).** Broadened the `[not documented]` exemption to also
  accept a plain `Label:` prefix (previously bold-label only), and added the canonical ultrasound
  Comparison-negative (`No prior study available for comparison.`) as exempt scaffolding. Both are
  lines with no clinical claim.

**Deliberately untouched (out of scope):** the entailment judge (`ENTAILMENT_SYSTEM`/`ENSEMBLE_LENSES`),
the ≥2/3 vote threshold + "uncertain → false" bias, the verbatim substring check, and every
deterministic HARD OVERRIDE (digit / negation / gloss / process-verb / form-route). The
embellishment catches and judge-conservatism cases were left firing.

## Phase B — deterministic certification (no credits)

- `04b-anchor-verify.test.ts`: **53/53 pass** (44 existing canaries + 9 new). New canaries pin the
  6 recoveries (lungs clear / no edema / continue lisinopril; plain-label `[not documented]`;
  Comparison-negative) AND two safety cases: an all-stopword anchor (`"of the"`) and a short
  FABRICATED anchor (`"severe sepsis"`, not in transcript) BOTH still demote before entailment.
- Full worker-layer suite: **301/301 pass** (22 files) — no collateral breakage.

## Phase C — before/after demotion counts, real Opus drafts (QA reflux + DVT + SOAP-control)

Real anchored drafts generated once (Opus 4.8, flag ON), then `runAnchorVerify` run BEFORE
(stashed 04b) vs AFTER on the SAME cached drafts with entailment held constant (approve-all) to
isolate the deterministic-stage delta.

| Report | BEFORE demoted | AFTER demoted | FP recovered | newly demoted (must be 0) |
|---|---|---|---|---|
| reflux | 2 | **0** | 2 | **0** |
| dvt | 4 | **3** | 1 | **0** |
| soap_control | 1 | **0** | 1 | **0** |

- **Recovered (false positives now in body):** the GSV measurement line `7.2/6.1/4.0 mm + 3.4/2.8 s`
  (BEFORE demoted only because its third sub-span `"SFJ incompetent"` (2 tokens) tripped the floor —
  losing real bilateral measurements); `No prior study available for comparison.` (reflux + dvt);
  `Pulmonary: Lungs clear.` Each recovery passes the **unchanged** verbatim + digit checks.
- **Retained demotions (still firing):** the 3 dvt negation cases (out-of-scope; unchanged).
- **AFTER demotions ⊆ BEFORE for every report; 0 newly demoted.** `filledEmptySections` dropped
  (reflux 1→0, dvt 2→1) because the Comparison sections now correctly retain their scaffolding.

## Phase D — fabrication gate, REAL PriMock57 clinical audio (zero-regression)

4 PriMock cases (day1_consultation01–04): real Deepgram nova-3-medical → L3 entities → raw L4
anchored draft (Opus 4.8, 36–43 anchors each), cached so BEFORE/AFTER see identical drafts.

**Deterministic A/B (BEFORE vs AFTER):**
- **All 4 bodies byte-identical. Demoted-claim TEXT set identical for all 4.**
- The only delta: 2 demotion *reasons* relabeled to be MORE accurate — Microgynon `oral`
  (`anchor_not_in_transcript` → `form_route_unsupported`) and "migraine with aura"
  (`anchor_not_in_transcript` → `process_assertion_unsupported`). Both stay demoted, now caught by
  their substantive overrides (which were not touched) instead of the blunt token-floor.
- **0 claims moved lane→body; 0 newly demoted.** No fabrication reaches the body that didn't before.

**Real k=3 entailment gate (AFTER):** the full catch stack fires across all reason types —
`negation_mismatch` 14, `not_entailed` (entailment judge) 13, `anchor_overlaps_unclear` 8,
`anchor_not_in_transcript` 7, `gloss_unsupported` 4, `process_assertion_unsupported` 2,
`form_route_unsupported` 2, `digits_unsupported` 1. The fabrication-catch machinery is intact and
actively demoting post-fix.

**Conclusion:** Every fabrication caught before is still caught. Zero catch regression on both
synthetic dictations and real clinical audio.

## code-quality-auditor

PASS — **0 BLOCKER · 0 WARN · 1 NIT**. Confirmed: scope is exactly the two fixes + the
`ANCHOR_STOPWORDS` const; the substring check, `ENTAILMENT_SYSTEM`, ≥2/3 threshold, and all HARD
OVERRIDES are byte-unchanged; both regexes are tight and ReDoS-free; tests reuse the established
canary harness. The single NIT (bold-label colon-inside form the template never emits) is "not a
defect — no change requested."

## Disposition

Ship behind the existing flag. **No prod deploy** — `TRANSCRIBE_MD_EVIDENCE_ANCHORS` remains OFF in
production; the change is byte-identical when the flag is off.
