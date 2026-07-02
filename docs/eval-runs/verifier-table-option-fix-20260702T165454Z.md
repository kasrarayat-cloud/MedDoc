# PRE-REGISTRATION — verifier table-row / option-scaffolding pass (feat/structured-templates)

**Committed BEFORE any eval tokens are spent** (protocol per `stabilized-protocol-20260611T201252Z.md` + the #346 method in `verifier-false-positive-fix-20260616T153931Z.md`). This is the pass deferred by `custom-template-qa-20260702T045849Z.md` §8 ("the next lever is the pre-registered verifier-FP process… targeting multi-span aggregate claims + table rows").

## Scope declaration (what changes / what is byte-frozen)

**IN scope (the #346-precedented exemption seam):**
1. `isExemptLine` (04b-anchor-verify.ts) — four additions, all lines that assert NO clinical fact:
   - markdown table **separator** rows (`| --- | --- |`);
   - pipe rows whose non-first cells are ALL scaffolding (empty / — / – / - / N/A / `[not documented]` / `[not addressed]`) — i.e. unfilled fixed-row skeleton lines like `| BP | [not documented] |` and empty-cell rows;
   - **unchecked option** lines (`- [ ] Option`, `* [ ] Option`, bare `[ ] Option`);
   - `[not addressed]` accepted alongside `[not documented]` in the existing placeholder alternation (same non-claim semantics; canonical token remains `[not documented]`).
2. `deterministicStage` — ONE addition outside isExemptLine (named here explicitly): a pipe row is exempt **iff the next line is a separator row** (table header detection requires one-line lookahead).
3. `ANCHOR_GENERATION_ADDENDUM` — generation-side sentences telling the model where structured anchors go (filled rows: after the final `|`; checked options: required; scaffolding: none). Generation-side but verifier-adjacent → inside this eval.

**BYTE-FROZEN (unchanged, verified by diff at ship):** the verbatim substring check; all five deterministic hard overrides (digits / spelled numbers / gloss / process-verb / form-route); negation polarity + subject checks; `ENTAILMENT_SYSTEM`; `ENSEMBLE_LENSES`; the ≥2/3 vote threshold + uncertain→false bias; the fabrication-catch threshold; L6b gate. **Explicitly NOT recovered by this pass** (frozen-override demotions stay demoted): route-column `form_route_unsupported` rows (4 of f4-a's 17), reference-range `digits_unsupported`, mid-line `[not documented]` `negation_mismatch`, unanchored DATA rows (they carry real claims and must keep demoting).

**Safety invariant:** a CHECKED option (`- [x]`) and a FILLED table cell are clinical claims — they get NO new exemption and must still anchor + verify. Canaries below pin this.

## Acceptance rules (pre-committed; ambiguity resolves AGAINST passing)

- **Phase B ($0):** all existing 53 04b canaries + full worker suite green, PLUS 7 new canaries: (a) unchecked option exempt (zero entailment calls); (b) fabricated-option — checked option with no anchor → `no_anchor`, and with a non-transcript anchor → `anchor_not_in_transcript` (BOTH must demote); (c) anchored table data row with dictated digits survives / unanchored data row still demotes; (d) header+separator rows exempt; (e) all-scaffold cell row exempt; (f) `Label: [not addressed]` exempt; (g) a sentence merely containing `[not addressed]` without the label-colon shape is NOT swept.
- **Phase C (cached-draft deterministic A/B, ≈$1):** regenerate anchored L4 drafts ONCE (real Opus, anchors ON) for: the f4-a tables dictation (persisted `rawTextInput`), the ultrasound reflux dictation, the clean-SOAP control, and one structured synthetic (checkbox+table template). Run `runAnchorVerify` BEFORE (04b @ main) vs AFTER (this branch) on the SAME drafts with entailment held approve-all (`MOCK_AI_CALLS=true` short-circuit). **Acceptance: AFTER demotions ⊆ BEFORE for every draft; 0 newly demoted; the recovered set consists EXCLUSIVELY of scaffolding lines** (separators, headers, all-scaffold rows, unchecked options). Any recovered line carrying a clinical claim = FAIL.
- **Phase D (fabrication gate, ≈$2-4):** `primock57-fullchain-fabrication.ts --anchored --cases day1_consultation01,day1_consultation02,day1_consultation03,day1_consultation04` (PRIMOCK_QA_DB_HOST set to the live qa postgres). **Gate-1: GREEN iff majority class-(c) = 0 across all FINAL notes. Gate-2: mean material omissions ≤ 1.5/case AND max ≤ 5 AND judge-unavailable = 0.** One run. No reroll. RED on either gate → STOP, report, do not ship the verifier diff (the schema/L4/render work may ship separately with the exemptions reverted).
- **Iteration budget:** up to 2 fix iterations on the exemption regexes ONLY (never the rubric, never these bounds, never the frozen surfaces), then STOP with attribution.

## Expected effect (falsifiable)

f4-a's 17 demotions → ~12-13 under the deterministic A/B (2 header + 2 separator rows recovered; `[not addressed]`-class rows when present). The 7 unanchored vitals DATA rows and the 5 frozen-override rows must remain demoted in the A/B. (Full end-to-end improvement additionally comes from the constrained-fill generation making rows anchorable — measured separately in the Phase-3 matrix, NOT part of this eval's acceptance.)

## Results (filled AFTER the runs)
- Phase B: [PENDING]
- Phase C: [PENDING]
- Phase D Gate-1: [PENDING] · Gate-2: [PENDING]
