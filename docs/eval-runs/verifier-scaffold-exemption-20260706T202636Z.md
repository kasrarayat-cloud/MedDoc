# PRE-REGISTRATION — verifier scaffold / anchored-option-carrier exemption

**Committed BEFORE any eval tokens are spent** (protocol per `stabilized-protocol-20260611T201252Z.md` + the #346 method used in `verifier-false-positive-fix-20260616T153931Z.md` and `verifier-table-option-fix-20260702T165454Z.md`). This is the pass deferred by the WM_IOV real-template test (`project_iov_content_controls`): the anchored verifier over-demotes a filled custom-template report.

## Problem (measured on the real WM_IOV venous-duplex template, anchors ON)

With a doctor's custom structured template active, ~half of a correctly-filled imaging report is demoted to the Review lane, leaving the note body half-empty. Two distinct buckets, observed on the real QA stack (`suggestedClaims`):

- **Bucket A — FIXED TEMPLATE BOILERPLATE → `no_anchor`.** Lines that are verbatim from the doctor's template with no dictated content: the TECHNIQUE methodology paragraph, "Clinical correlation with the above findings is required.", the per-leg structural labels "Right Leg:" / "Left Leg:". The model does not anchor them (they are not claims derived from the visit) → `no_anchor` demotion.
- **Bucket B — FILLED CONSTRAINED-CHOICE CARRIERS → `not_entailed`.** Carrier sentences whose `{{one of: …}}` slots were correctly filled from the dictation — e.g. the coherent finding chain *"The great saphenous vein from the saphenofemoral junction to the mid thigh was found to have had previous treatment, however, there has been a recurrence."* The picks are anchored and correct; the LLM entailment judge demotes the whole sentence because the transcript does not entail the fixed connective boilerplate ("was found to have had previous treatment").

Both are a category error: 04b verifies the doctor's PRE-APPROVED TEMPLATE SCAFFOLD against the transcript as if it were free-text clinical assertion. Template scaffold the doctor authored/approved is not a claim to verify — but the SELECTED VALUE inside a slot IS, and must still be grounded.

## Hypothesis

Making 04b **template-scaffold-aware** — (A) exempting exact fixed-scaffold lines, and (B) feeding the LLM judge the *picks-plus-laterality* reduced claim instead of the boilerplate-heavy carrier — recovers the correctly-filled body WITHOUT weakening fabrication catch, because the judge (the strongest catch) still evaluates the actual clinical picks, and every frozen deterministic override still runs unchanged on the full line.

## Scope declaration (what changes / what is byte-frozen)

**IN scope (additive, gated on a template scaffold being supplied):**
1. A new pure preprocessor `buildTemplateScaffold(sections)` → `{ fixedLines: Set<norm>, carriers: [{ segments, matcher }] }`, derived from the resolved template's section `defaultText` (the SAME template generation used):
   - a defaultText line with NO `{{one of}}` marker → a **fixed-scaffold** line (normalized);
   - a line WITH markers → a **carrier**: fixed literals + `{{one of: A|B|C}}` slots, compiled to a normalized matcher whose slot groups are the template's own enumerated options (escaped, longest-first).
2. `deterministicStage(anchoredDraft, transcript, scaffold?)` — TWO new branches, BEFORE the existing no-anchor / anchor / override logic, active only when `scaffold` is supplied:
   - **Bucket A:** an anchor-stripped line whose normalized form exactly equals a `fixedLines` entry → `exemptLines` (scaffold; asserts no patient-specific claim — same class as the existing section-header / `[not documented]` / "No prior study available" exemptions).
   - **Bucket B:** a line that matches a `carriers[].matcher` → still runs the **entire existing override chain on the FULL line unchanged** (anchor-in-transcript, digit, spelled-number, gloss, process-verb, form/route, negation polarity, negation-subject — any firing still demotes exactly as today); if it survives to entailment, it is pushed to `toEntail` with a new optional field `entailText` = the reduced claim (laterality tokens from fixed parts, in order, + the captured picks; connective boilerplate dropped). Display text (`text`) stays the full line.
3. `ClaimRow.entailText?: string`; `entailmentStage` builds each judge CLAIM from `c.entailText ?? c.text` (unchanged when absent).
4. `runAnchorVerify` gains an optional `templateScaffold` input; `04-generate-soap.ts` builds it from the resolved template and passes it (only when a custom template with markers is active).

**BYTE-FROZEN (unchanged; verified by diff at ship):** the verbatim substring / anchor-in-transcript check; all five deterministic hard overrides (digits / spelled numbers / gloss / process-verb / form-route); negation polarity + negation-subject checks; `ENTAILMENT_SYSTEM`; `ENSEMBLE_LENSES`; the k=3 majority-≥2 threshold + fail-closed error handling; `anchorSubSpans`; `isExemptLine`'s existing clauses; the L6b gate. The judge PROMPT and VOTING are untouched; only the CLAIM TEXT for carrier lines changes (a subset of the line's own content).

**Safety invariants (canaries below pin all):**
- a filled slot whose pick is NOT supported by the dictation STILL demotes (the reduced claim is still judged; a wrong pick fails entailment / a frozen override);
- an option that is NOT one of the template's enumerated options never matches a carrier → falls through to the normal full-line path → demoted as today (fabricated option can never be laundered by the carrier path);
- a laterality swap (right findings under the "Left" carrier) STILL demotes (laterality tokens are carried into the reduced claim → the judge rejects them);
- free-text clinical assertions (no scaffold/carrier match) are byte-identical to today;
- with NO `templateScaffold` supplied (every current SOAP/prod path + every existing 04b test) behavior is byte-identical.

## Acceptance rules (pre-committed; ambiguity resolves AGAINST passing)

- **Phase B ($0):** all existing 62 04b canaries green (frozen behavior), full worker suite green, PLUS new canaries — (a) fixed-scaffold line exempt WITH scaffold, and NOT exempt without it; (b) fixed-looking line NOT in the template still verified normally; (c) filled carrier with supported picks → survives, and the judge receives the reduced claim; (d) **fabricated option not in the template → demotes** (no carrier match); (e) **filled slot whose pick contradicts the dictation → demotes**; (f) **laterality swap → demotes**; (g) a carrier whose FULL line trips a frozen override (negation/digit) still demotes with the same reason; (h) `entailText` absent → judge input byte-identical.
- **Phase C (WM_IOV before/after, real Opus, ≈$1):** regenerate the anchored L4 draft ONCE from the WM_IOV template + the dense reflux dictation. Run `runAnchorVerify` BEFORE (04b @ main, no scaffold) vs AFTER (this branch, scaffold supplied) on the SAME draft. **Acceptance: AFTER body is substantially full (the coherent finding chain + the correctly-filled indications/diagnosis/impression picks are in the BODY, not the lane); every line AFTER recovers is a fixed-scaffold line or a carrier whose picks the transcript supports; NO genuinely-unsupported line is recovered.** Report BEFORE→AFTER lane counts.
- **Phase D (fabrication gate, real full-chain, ≈$2–4):** `primock57-fullchain-fabrication.ts --anchored --cases day1_consultation01,day1_consultation02,day1_consultation03,day1_consultation04` (these are STANDARD SOAP notes — no template scaffold supplied — so this proves the frozen path is untouched). **Gate-1 (HARD): GREEN iff majority class-(c) fabrications = 0 across all FINAL notes — ZERO catch regression vs the last certified run. Gate-2: mean material omissions ≤ 1.5/case AND max ≤ 5 AND judge-unavailable = 0.** One run, no reroll.
- **Iteration budget:** up to 2 fix iterations on the scaffold-matcher / reduced-claim construction ONLY (never the rubric, never these bounds, never the frozen surfaces), then STOP with attribution.

## STOP-AND-REPORT condition

If ANY fabrication slips — any Phase-B fabricated-option / contradiction / laterality canary fails to demote, OR Phase D Gate-1 is not GREEN (any majority class-(c) fabrication regression) — **STOP. Do not merge the 04b diff.** The schema/generation work may ship separately with this exemption reverted. Report the slip.

## Results (filled AFTER the runs — one run each, no rerolls)
- **Phase B:** _pending_
- **Phase C (WM_IOV before→after):** _pending_
- **Phase D (fabrication gate):** _pending_
- **VERDICT:** _pending_
