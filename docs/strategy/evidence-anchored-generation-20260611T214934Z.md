# Evidence-Anchored Generation — design + feasibility spike

**Status:** DESIGN + SPIKE ONLY (no build). Decision input: the pre-registered
n=30 measurement (`stabilized-protocol-20260611T201252Z.md` → RED, 28 majority
class-(c), 18 unanimous) characterized the defect as **clinical-register
inference** — L4 asserts unstated negatives, unnamed differentials,
specifications, reframes, and process boilerplate. Five immutable prompt rules
bent the rate but did not break the habit: **prompt-side enforcement is
exhausted; the fix is structural.**

**Decision made (Kasra):** Option 1 (evidence-anchored generation) with Option
3 (per-claim provenance UI) absorbed as its UI half. Option 2
(structured-claims rendering for ROS/Assessment) is the documented fallback if
the spike fails on anchoring reliability.

**The invariant:** every clinical claim in the SERVED note body carries a
deterministically verified transcript anchor. Unanchored claims are NOT
silently dropped — they demote to a labeled **"Suggested by AI — not stated in
this visit"** lane that the doctor can adopt explicitly (adopted claims enter
the note as doctor-attested). Fail-toward-suggestion, never fail-toward-body.

---

## 1. Anchor format — inline markers, stripped at render

L4 emits each clinical claim followed by an inline anchor:

```
Patient reports cramping left lower abdominal pain. ⟦A:"like a muscular cramp ... in my left side below the belly button"⟧
```

- Marker syntax: `⟦A:"<verbatim transcript quote>"⟧` (the `⟦⟧` brackets are
  outside every clinical vocabulary and outside doctors' plausible note text;
  collision-checked against the corpus). Multiple anchors per sentence are
  legal (`⟦A:"…"⟧⟦A:"…"⟧`). An explicitly UNANCHORED suggestion is emitted as
  `⟦S⟧` (the model may propose; the verifier decides — see §2; a missing
  marker entirely is treated as `⟦S⟧`).
- **Why inline, not a structured sidecar:** (a) the existing pipeline is
  markdown-native end to end — L5 critique, the L6 polish + fidelity gate, the
  structure validator, custom note-format rendering, and the editor all
  consume one markdown string; a sidecar (claims JSON + note) reintroduces the
  forced-tool-use shape that broke under Fable and doubles the
  synchronization surface (claim↔text drift). (b) Inline anchors survive
  reordering/rewording by L6 mechanically — the anchor travels with its
  sentence. (c) Deterministic stripping is a regex pass; the render is
  byte-clean.
- **Custom note-formats compose for free:** anchors attach to claims, not to
  sections. `buildSoapSystemPrompt` keeps the template's sections; the
  anchor instruction rides the IMMUTABLE safety layer (`SAFETY.globalRules`),
  so a custom template cannot weaken it. The verifier and stripper operate on
  the final markdown regardless of heading structure.
- **The preview action** (`previewNoteTemplateAction`, synthetic transcript)
  uses the same prompt primitives → anchors are emitted against the synthetic
  transcript and verified/stripped identically. No special-casing.

## 2. Verifier — deterministic, fail-toward-suggestion

Pure function, no model call, unit-testable. For each claim (sentence-level
segmentation on the rendered markdown; headers/list-numbering/structural
lines exempt):

1. **Anchor existence:** every `⟦A:"q"⟧` quote `q` must literally exist in
   the role-labeled transcript under normalization N = lowercase → strip
   punctuation (keep digits + `[unclear in recording]` markers) → collapse
   whitespace. Exact substring match after N; quotes may use `...` ellipses
   joining up to 3 sub-spans, each ≥ 3 tokens, all required to match, in
   transcript order.
2. **Claim-token derivability** from the union of anchored spans:
   - every **digit token** in the claim appears in the spans (doses, vitals,
     ages computed from a stated DOB are exempted ONLY when the claim is
     marked `(calculated)` — mirroring the locked rubric's arithmetic
     allowance, verified by recomputation where parseable);
   - **negation polarity**: claim contains a negation token
     (`no|not|denies|without|negative`) ⇔ at least one span contains one;
   - **clinical-content coverage**: ≥ 60% of the claim's content tokens
     (length ≥ 5, non-stopword, minus a documented connector whitelist —
     "patient", "reports", "documented", section vocabulary) appear in the
     spans by 5-char prefix match (cheap stemming);
   - any anchored span overlapping `[unclear in recording]` contributes
     nothing (marked audio anchors nothing).
3. **Outcome:** all checks pass → claim stays in the body, anchor stripped.
   ANY check fails, anchor missing, `⟦S⟧`, malformed marker, or **any
   verifier exception → demote to the suggestions lane** (the verifier is
   wrapped fail-closed exactly like the L6b gate: error never passes a claim).

Thresholds (0.60 coverage, 5-char prefix, ≤3 sub-spans) are spike-calibrated
constants, documented and test-pinned; tuning them is a measured change, not
a silent one.

## 3. Pipeline placement

```
L3 → L4 (emits anchors) → ANCHOR-VERIFY (deterministic split: body/suggestions)
   → L5 critique (sees the BODY + the transcript — critiques what will be served)
   → L6 polish + L6b fidelity gate (UNCHANGED contract, operates on the body)
   → render: body (anchor-free) + suggestions lane (sidecar column on the visit row)
```

- Verify sits **immediately after L4**, before L5: the critique then audits
  the actual servable body (no wasted critique on claims that will demote),
  and its fixable suggestions can't resurrect demoted content (the L6 gate
  already rejects additive fixes — that contract is **unchanged**; the gate's
  draft-fallback now falls back to the *verified body*, a strictly cleaner
  artifact than today's raw L4 draft).
- Anchors are stripped BEFORE L5/L6 see the text (they see the clean body),
  so no downstream prompt changes are required beyond L4.
- Suggestions persist as a structured JSONB column (`suggestedClaims`:
  `[{text, reason: 'unanchored'|'failed_<check>', section}]`) — never
  concatenated into `soapDraft/soapFinal`.

## 4. ROS-negatives policy

Default: unstated ROS-negatives are exactly the "no vomiting" class → they
demote to suggestions. The doctor adopts the ones they actually elicited.
**Flagged for post-pilot (NOT built):** a doctor-attested "my standard ROS"
setting — a per-doctor declared screening set whose negatives may enter the
body pre-labeled as attested-by-standard-practice. Requires consent UX +
audit semantics; out of scope.

## 5. Review UI (Option 3 absorbed)

- A "Suggested by AI — not stated in this visit" panel under the SOAP editor
  (same visual family as the review banner; amber family, distinct icon).
  Per claim: [Adopt] inserts the text into the note via the existing editor
  edit path → the claim is thereafter DOCTOR-attested (it entered through
  the same mechanism as typing); [Dismiss] removes it. Both audited
  (`SUGGESTION_ADOPTED` / `SUGGESTION_DISMISSED` — additive AuditAction).
- Composes with the existing review banner: the banner reads "N AI
  suggestions await review" when the lane is non-empty (additive
  reviewReason, the `applyAdditiveReviewState` path).
- **Telemetry = the living fabrication monitor:** per-note anchored-claim
  count, demoted count, and (later) adoption rate. A drifting demotion rate
  is the regression alarm the static evals can't be.

## 6. Migration / rollout

- Behind `TRANSCRIBE_MD_EVIDENCE_ANCHORS` (default OFF); the old path stays
  byte-identical until measured. Flag read at L4 build + verifier wiring.
- Eval gate to enable: **the locked stabilized protocol re-run on the same
  n=30** with the flag on — GREEN requires majority class-(c)=0 in served
  BODIES (suggestions lane is, by definition, not the note) + a false-demotion
  rate below the spike-established ceiling.
- Rollout: qa stack → prod flag-on for the dogfood account only (per-practice
  flag) → pilot.

## 7. Honest cost analysis

- **Failure direction:** every error mode (model forgets an anchor, quote
  paraphrased, verifier bug, exception) moves a claim OUT of the note into a
  labeled lane. The note can become sparser than a scribe's ideal — a real
  cost (omission), but the right one for a scribe whose notes are signed
  under a clinician's name: a missing-but-suggestable sentence costs one
  click; a fabricated sentence costs trust, and per the measurement it
  currently happens ~1×/visit.
- **Expected false-demotion sources:** paraphrase anchors (model quotes
  loosely), cross-utterance claims (summary sentences synthesizing 3 spans —
  mitigated by multi-anchor + ellipses), token-coverage misses on heavy
  rewording. The SPIKE measures this rate honestly; if the body turns to
  Swiss cheese, that is a spike FINDING → fall back to Option 2 for
  ROS/Assessment (structured claims rendered from verified entities, free
  prose only for HPI narrative).
- Cost: +0 model calls (anchors ride the existing L4 call; the verifier is
  pure code). Token overhead ≈ +20-35% L4 output tokens (anchors), ~+1-2¢ per
  visit.

## 8. Spike protocol (Phase 2 of this task — go/no-go for the build)

- Script-level, outside the prod path (`scripts/eval/evidence-anchor-spike.ts`,
  CI-excluded). Inputs: the 5 worst offenders by majority-(c) count from the
  n=30 run (ties lexicographic): `day1_consultation03, day1_consultation10,
  day1_consultation14, day3_consultation01, day3_consultation05` — using the
  PERSISTED ASR transcripts from the n=30 artifacts (identical inputs,
  deterministic), real L3 + L4-with-anchors calls, the deterministic verifier
  prototype, single-judge scoring under the locked protocol rubric.
- **Gate:** (1) served-body class-(c) = 0 on all 5; (2) the previously
  measured fabrications appear in the suggestions lane (captured, not
  vanished); (3) false-demotion rate reported honestly (of demoted claims,
  the share a judge finds actually transcript-supported); (4) readability
  excerpt comparison. One spike. No iteration spiral. Fail → Option-2
  counter-scope.
